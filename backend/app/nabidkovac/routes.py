"""API Nabídkovače (SPEC-nabidkovac.md).

KOSTRA: zakládání/editace nabídek, nahrávání dokumentů BEZ zpracování,
správa katalogu technologií a verzovaných výpočtových nastavení. Žádná
výpočetní logika (sizing, PVGIS, ROI, LLM extrakce, generování PDF) tu není.
"""

import dataclasses
import re
import unicodedata
from datetime import date, datetime
from typing import Optional

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.models import User
from app.crm.models import ObjednavkaPolozka
from app.database import get_db
from app.nabidkovac import (
    excel_ppa,
    katalog_soubory,
    pdf as pdf_modul,
    peak_shaving,
    polozky as polozky_modul,
    ppa_bess,
    ppa_fve,
    ppa_tvar,
    ppa_v2,
    profil_import,
    profil_pokryti,
    sablona_katalog,
    soubory,
    spot_arbitraz,
    spot_ceny,
    vystup_html,
    vystup_obrazky,
)
from app.nabidkovac.models import (
    DISTRIBUTORI,
    NAPETOVE_HLADINY,
    STRUKTURY_TARIFU,
    TYPY_DOKUMENTU,
    TYPY_NABIDKY,
    TYPY_SLOUPCE,
    VYCHOZI_ZDROJ,
    GenerovanaNabidkaPdf,
    KatalogSloupec,
    Nabidka,
    NabidkaDokument,
    NabidkaPolozka,
    NabidkaVystup,
    NavrhovaneReseni,
    SazbaDistributoru,
    SpotrebaProfil,
    Technologie,
    TechnologiePriloha,
    VypocetFronta,
    VypoctovaNastaveni,
    VystupSablona,
)
from app.nabidkovac.permissions import (
    muze_katalog,
    vyzaduj_katalog,
    vyzaduj_nabidkovac,
    vyzaduj_ppa_bess,
)
from app.nabidkovac.schemas import (
    DokumentOut,
    DokumentUprava,
    HromadnaUpravaKatalogu,
    KatalogSloupecOut,
    KatalogSloupecVstup,
    NabidkaDetailOut,
    NabidkaRadekOut,
    NabidkaUprava,
    NabidkaVstup,
    PeakShavingVstup,
    PolozkyOut,
    PolozkySouhrn,
    PolozkyVstup,
    PpaBessVstup,
    PpaVstup,
    PrilohaOut,
    PrilohaUprava,
    ReseniOut,
    SazbaOut,
    SazbaVstup,
    TechnologieOut,
    TechnologieVstup,
    VariantaDetailVstup,
    VypoctovaNastaveniOut,
    VypoctovaNastaveniVstup,
    VystupKonfigurace,
    VystupOut,
    VystupPdfVstup,
    VystupPrvek,
    VystupSablonaOut,
    VystupSablonaVstup,
    VystupSablonaZNabidky,
    VystupSablonySeznam,
)

router = APIRouter(prefix="/nabidkovac", tags=["nabidkovac"])


# ---- pomocné ----
def _iso(dt) -> str | None:
    if isinstance(dt, (datetime, date)):
        return dt.isoformat()
    return None


def _num(x) -> float | None:
    return float(x) if x is not None else None


def _dotaz_baterie_katalog(db: Session, ids: list[int] | None = None):
    """Dotaz na použitelné baterie z katalogu – jeden zdroj pro peak shaving i PPA.

    Filtr (kap. 3.2): typ = baterie, dostupná, s vyplněným výkonem i kapacitou.
    Ten na kW/kWh je zároveň to, co ze simulací drží stranou bateriové KOMPONENTY
    z prodejního ceníku (BMS, kabeláž, racky) – ty tahle čísla nemají.
    `ids` = ruční výběr produktů obchodníkem (prázdné/None = celý katalog).
    Na kladnost čísel a na cenu si volající filtruje sám při mapování.
    """
    dotaz = db.query(Technologie).filter(
        Technologie.typ == "baterie",
        Technologie.aktivni.is_(True),
        Technologie.vykon_kw.isnot(None),
        Technologie.kapacita_kwh.isnot(None),
    )
    if ids:
        dotaz = dotaz.filter(Technologie.id.in_(ids))
    return dotaz


def _produkty_baterie_ppa(
    db: Session, ids: list[int] | None = None
) -> tuple[ppa_v2.ProduktBaterie, ...]:
    """Katalog baterií ve tvaru, ve kterém s ním počítá PPA (a PPA + BESS).

    Jedno místo pro obě cesty – kdyby si každá mapovala sama, jeden modul by po
    změně katalogu počítal s jinou cenou než druhý a nikdo by si toho nevšiml.
    """
    return tuple(
        ppa_v2.ProduktBaterie(
            id=t.id,
            nazev=t.nazev,
            vykon_kw=float(t.vykon_kw),
            kapacita_kwh=float(t.kapacita_kwh),
            # PPA potřebuje NÁKLADOVOU cenu (nabaluje na ni marži BESS), takže
            # přednost má nákupní cena, když ji produkt má. U baterií z ceníku
            # BESS vyplněná není a `cena_kc` v sobě nese dealerskou cenu, což
            # náklad je – viz docstring `ppa_v2.ProduktBaterie`.
            cena_kc=float(
                t.cena_nakup_kc
                if t.cena_nakup_kc is not None and float(t.cena_nakup_kc) > 0
                else (t.cena_kc or 0.0)
            ),
            # Round-trip účinnost z katalogu; chybějící/nesmyslná → default.
            # Toleruje zadání v procentech (stejná normalizace jako u PS).
            ucinnost_rt=peak_shaving.normalizuj_ucinnost_rt(t.ucinnost),
            uzitna_kapacita_kwh=_num((t.extra or {}).get("uzitna_kapacita_kwh")),
            max_vykon_stridacu_kw=_num((t.extra or {}).get("max_vykon_stridacu_kw")),
            # Konfigurace, u kterých ceník dealerskou cenu neuvádí, mají
            # v `cena_kc` doporučenou prodejní cenu – náklad je pak o dealerský
            # diskont nadhodnocený a výpočet to obchodníkovi řekne.
            cena_je_doporucena=(
                (t.cena_nakup_kc is None or float(t.cena_nakup_kc) <= 0)
                and t.cena_kc is not None
                and _num((t.extra or {}).get("doporucena_cena_kc")) is not None
                and abs(float(t.cena_kc) - _num((t.extra or {}).get("doporucena_cena_kc"))) < 0.01
            ),
        )
        for t in _dotaz_baterie_katalog(db, ids).all()
        if float(t.vykon_kw) > 0 and float(t.kapacita_kwh) > 0 and t.cena_kc
    )


def _dokument_out(d: NabidkaDokument) -> DokumentOut:
    return DokumentOut(
        id=d.id,
        typ=d.typ,
        puvodni_nazev=d.puvodni_nazev,
        velikost_bajtu=d.velikost_bajtu,
        stav_zpracovani=d.stav_zpracovani,
        nahrano_at=_iso(d.nahrano_at),
    )


def _nabidka_detail(n: Nabidka, db: Session) -> NabidkaDetailOut:
    """Detail nabídky včetně definic vlastních polí (CRM-04).

    Import CRM modulu je uvnitř funkce schválně: `nabidkovac` je na CRM jinak
    nezávislý a top-level import by udělal kruh (crm/vlastni_pole si naopak
    tahá model Nabidka).
    """
    from app.crm import vlastni_pole as pole_modul

    return NabidkaDetailOut(
        # Pydantic si dicty z `pro_frontend` zvaliduje sám na VlastniPoleOut.
        vlastni_pole=pole_modul.pro_frontend(db, "nab"),
        extra=n.extra or {},
        id=n.id,
        typ=n.typ,
        cislo=n.cislo,
        obchodni_pripad_id=n.obchodni_pripad_id,
        zakaznik_nazev=n.zakaznik_nazev,
        zakaznik_adresa=n.zakaznik_adresa or "",
        zakaznik_gps_lat=_num(n.zakaznik_gps_lat),
        zakaznik_gps_lng=_num(n.zakaznik_gps_lng),
        stav=n.stav,
        vytvoril_jmeno=n.vytvoril.jmeno if n.vytvoril else None,
        vytvoreno_at=_iso(n.vytvoreno_at),
        vypoctova_nastaveni_id=n.vypoctova_nastaveni_id,
        dokumenty=[_dokument_out(d) for d in sorted(n.dokumenty, key=lambda x: x.id)],
        reseni=[
            ReseniOut(
                id=r.id,
                typ_reseni=r.typ_reseni,
                popis_json=r.popis_json or {},
                vybrano_zakaznikem=r.vybrano_zakaznikem,
            )
            for r in sorted(n.reseni, key=lambda x: x.id)
        ],
    )


# ================= Nabídky =================
@router.get("/nabidky", response_model=list[NabidkaRadekOut])
def seznam_nabidek(
    typ: str | None = None,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Seznam nabídek (volitelně filtr podle podsekce `typ`)."""
    if typ is not None and typ not in TYPY_NABIDKY:
        raise HTTPException(status_code=422, detail=f"Neznámý typ nabídky: {typ}")
    q = db.query(Nabidka)
    if typ is not None:
        q = q.filter(Nabidka.typ == typ)
    nabidky = q.order_by(Nabidka.vytvoreno_at.desc(), Nabidka.id.desc()).all()
    return [
        NabidkaRadekOut(
            id=n.id,
            typ=n.typ,
            zakaznik_nazev=n.zakaznik_nazev or "(bez názvu)",
            stav=n.stav,
            vytvoril_jmeno=n.vytvoril.jmeno if n.vytvoril else None,
            vytvoreno_at=_iso(n.vytvoreno_at),
        )
        for n in nabidky
    ]


@router.post("/nabidky", response_model=NabidkaDetailOut)
def zaloz_nabidku(
    vstup: NabidkaVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Založí nový záznam nabídky (stav = koncept) a vrátí detail k vyplnění.

    Číslo NAB-RR-NNNN přiděluje číselná řada CRM, aby každá nabídka měla
    viditelné ID, i když vznikla přímo v nabídkovači (bez obchodního případu).
    """
    if vstup.typ not in TYPY_NABIDKY:
        raise HTTPException(status_code=422, detail=f"Neznámý typ nabídky: {vstup.typ}")
    from app.crm.ciselne_rady import dalsi_cislo as dalsi_cislo_crm

    n = Nabidka(
        typ=vstup.typ,
        cislo=dalsi_cislo_crm(db, "nab"),
        zakaznik_nazev=(vstup.zakaznik_nazev or "").strip(),
        vytvoril_user_id=user.id,
    )
    db.add(n)
    db.flush()
    # CRM-31: pravidla navěšená na „vznikla nová nabídka“.
    from app.crm import automatizace as automatizace_modul

    automatizace_modul.po_vzniku(db, "nab", n, user)
    db.commit()
    db.refresh(n)
    return _nabidka_detail(n, db)


@router.get("/nabidky/{nabidka_id}", response_model=NabidkaDetailOut)
def detail_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _nabidka_detail(n, db)


@router.put("/nabidky/{nabidka_id}", response_model=NabidkaDetailOut)
def uprav_nabidku(
    nabidka_id: int,
    vstup: NabidkaUprava,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    n.zakaznik_nazev = (vstup.zakaznik_nazev or "").strip()
    n.zakaznik_adresa = (vstup.zakaznik_adresa or "").strip()
    n.zakaznik_gps_lat = vstup.zakaznik_gps_lat
    n.zakaznik_gps_lng = vstup.zakaznik_gps_lng
    if vstup.stav is not None:
        n.stav = vstup.stav
    if vstup.extra is not None:
        from app.crm import vlastni_pole as pole_modul

        n.extra = pole_modul.zpracuj(db, "nab", vstup.extra)
    # CRM-31: změna pole nabídky (např. doplněný zákazník).
    from app.crm import automatizace as automatizace_modul

    automatizace_modul.po_zmene_poli(db, "nab", n, user)
    db.commit()
    db.refresh(n)
    return _nabidka_detail(n, db)


@router.delete("/nabidky/{nabidka_id}")
def smaz_nabidku(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    # smažeme i soubory z disku (DB řádky padnou přes cascade)
    for d in n.dokumenty:
        soubory.smaz_soubor(d.soubor_cesta)
    db.delete(n)
    db.commit()
    return {"smazano": nabidka_id}


# ---- dokumenty (jen uložení, bez zpracování – kap. 5 SPEC) ----
@router.post("/nabidky/{nabidka_id}/dokumenty", response_model=DokumentOut)
async def nahraj_dokument(
    nabidka_id: int,
    typ: Optional[str] = Form(None),
    soubor: UploadFile = File(...),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Nahraje dokument k nabídce. NEZPRACOVÁVÁ ho – jen uloží soubor a založí
    záznam se stavem "nahrano". Extrakce/parsování přijde v dalších promptech.

    Typ dokumentu je volitelný: když nepřijde (nebo přijde "auto"), odvodí se
    z přípony souboru – uživatel tak nemusí před nahráním nic vybírat.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")

    if typ in (None, "", "auto"):
        typ = soubory.odvod_typ(soubor.filename or "")
        if typ is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Typ souboru se nepodařilo rozpoznat. Povolené formáty: "
                    f"{', '.join(soubory.VSECHNY_PRIPONY)}."
                ),
            )
    elif typ not in TYPY_DOKUMENTU:
        raise HTTPException(status_code=422, detail=f"Neznámý typ dokumentu: {typ}")

    pripona = Path(soubor.filename or "").suffix.lower()
    povolene = soubory.POVOLENE_PRIPONY.get(typ, set())
    if pripona not in povolene:
        raise HTTPException(
            status_code=422,
            detail=f"Nepovolená přípona {pripona or '(žádná)'}. Povoleno: {', '.join(sorted(povolene))}",
        )

    obsah = await soubor.read()
    if not obsah:
        raise HTTPException(status_code=422, detail="Prázdný soubor.")
    if len(obsah) > soubory.MAX_BAJTU:
        raise HTTPException(
            status_code=422,
            detail=f"Soubor je příliš velký (max {soubory.MAX_BAJTU // (1024 * 1024)} MB).",
        )

    rel_cesta = soubory.uloz_soubor(nabidka_id, soubor.filename or "soubor", obsah)
    d = NabidkaDokument(
        nabidka_id=nabidka_id,
        typ=typ,
        soubor_cesta=rel_cesta,
        puvodni_nazev=soubor.filename or "soubor",
        velikost_bajtu=len(obsah),
        stav_zpracovani="nahrano",
        nahral_user_id=user.id,
    )
    db.add(d)
    # nahrání dokumentů posune koncept do stavu "data nahrána"
    if n.stav == "koncept":
        n.stav = "data_nahrana"
    db.commit()
    db.refresh(d)

    # Profil spotřeby zpracujeme HNED. Dřív se čekalo na ruční kliknutí
    # v panelu výpočtu, což znamenalo, že OZ nahrál diagram, viděl u něj
    # „čeká na zpracování“ a nabídka se pak počítala bez dat spotřeby
    # (nahlásil Dan 31. 7. 2026). Selhání parsování nesmí shodit celé
    # nahrání — soubor je uložený a dokument dostane stav `chyba_extrakce`,
    # takže se dá přeoznačit typ nebo nahrát jiný export.
    if typ == "spotreba_csv":
        try:
            _zpracuj_profil_dokumentu(db, d)
        except HTTPException:
            db.rollback()
            d.stav_zpracovani = "chyba_extrakce"
            db.commit()
        db.refresh(d)
    return _dokument_out(d)


@router.patch("/dokumenty/{dokument_id}", response_model=DokumentOut)
def uprav_dokument(
    dokument_id: int,
    vstup: DokumentUprava,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Přepne typ už nahraného dokumentu (když automat podle přípony minul).

    Hlídá se stejný whitelist přípon jako při nahrání – např. PDF nejde
    označit za profil spotřeby.
    """
    d = db.get(NabidkaDokument, dokument_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Dokument neexistuje")

    pripona = Path(d.soubor_cesta).suffix.lower()
    povolene = soubory.POVOLENE_PRIPONY.get(vstup.typ, set())
    if pripona not in povolene:
        raise HTTPException(
            status_code=422,
            detail=f"Soubor {pripona} nelze označit jako tenhle typ (povoleno: {', '.join(sorted(povolene))}).",
        )

    d.typ = vstup.typ
    db.commit()
    db.refresh(d)
    return _dokument_out(d)


@router.delete("/dokumenty/{dokument_id}")
def smaz_dokument(
    dokument_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    d = db.get(NabidkaDokument, dokument_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Dokument neexistuje")
    soubory.smaz_soubor(d.soubor_cesta)
    db.delete(d)
    db.commit()
    return {"smazano": dokument_id}


# ================= Katalog produktů =================
def _priloha_out(p: TechnologiePriloha) -> PrilohaOut:
    return PrilohaOut(
        id=p.id,
        druh=p.druh,
        puvodni_nazev=p.puvodni_nazev,
        popis=p.popis or "",
        velikost_bajtu=p.velikost_bajtu,
        nahrano_at=_iso(p.nahrano_at),
        je_obrazek=katalog_soubory.mime_typ(p.puvodni_nazev).startswith("image/"),
    )


def _plati_dnes(t: Technologie, dnes: date | None = None) -> bool:
    """Je položka v platnosti k dnešku? Prázdná mez = neomezeno."""
    dnes = dnes or date.today()
    if t.platnost_od and t.platnost_od > dnes:
        return False
    if t.platnost_do and t.platnost_do < dnes:
        return False
    return True


def _technologie_out(t: Technologie, s_nakupem: bool = False) -> TechnologieOut:
    """Položka katalogu pro API.

    `s_nakupem=False` (bez práva `nabidkovac_katalog`) znamená, že se nákupní
    cena ani marže do odpovědi nedostanou vůbec – rozhodnutí Dana z 31. 7. 2026.
    """
    out = TechnologieOut(
        id=t.id,
        typ=t.typ,
        nazev=t.nazev,
        model=t.model or "",
        kod=t.kod,
        kategorie=t.kategorie or "",
        jednotka=t.jednotka or "ks",
        popis=t.popis or "",
        vykon_kw=_num(t.vykon_kw),
        kapacita_kwh=_num(t.kapacita_kwh),
        cena_kc=_num(t.cena_kc),
        sazba_dph=_num(t.sazba_dph),
        ucinnost=_num(t.ucinnost),
        platnost_od=_iso(t.platnost_od),
        platnost_do=_iso(t.platnost_do),
        zdroj=t.zdroj or VYCHOZI_ZDROJ,
        aktivni=t.aktivni,
        plati_dnes=_plati_dnes(t),
        raynet_id=t.raynet_id,
        extra=t.extra or {},
        prilohy=[_priloha_out(p) for p in sorted(t.prilohy, key=lambda x: x.id)],
    )
    if s_nakupem:
        out.cena_nakup_kc = _num(t.cena_nakup_kc)
        if t.cena_kc is not None and t.cena_nakup_kc is not None:
            out.marze_kc = float(t.cena_kc - t.cena_nakup_kc)
            if t.cena_kc:
                out.marze_procent = round(
                    float((t.cena_kc - t.cena_nakup_kc) / t.cena_kc * 100), 1
                )
    return out


def _zpracuj_extra(db: Session, extra_vstup: dict | None) -> dict:
    """Očistí hodnoty vlastních sloupců: nechá jen definované sloupce a u typu
    `cislo` převede na číslo (prázdné → klíč se vynechá). Neznámé klíče zahodí."""
    if not extra_vstup:
        return {}
    sloupce = {s.klic: s.typ for s in db.query(KatalogSloupec).all()}
    out: dict = {}
    for klic, hodnota in extra_vstup.items():
        if klic not in sloupce:
            continue  # sloupec neexistuje (např. mezitím smazaný) → ignoruj
        if hodnota is None or (isinstance(hodnota, str) and hodnota.strip() == ""):
            continue  # prázdná hodnota se neukládá
        if sloupce[klic] == "cislo":
            try:
                out[klic] = float(str(hodnota).replace(",", "."))
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail=f"Sloupec '{klic}' je číselný, ale '{hodnota}' není číslo.",
                )
        else:
            out[klic] = str(hodnota).strip()
    return out


def _over_technologii(vstup: TechnologieVstup) -> str:
    """Validace vstupu katalogu. Vrací očištěný název.

    Kap. 3.2 METODIKY: pro `typ = baterie` musí být vyplněná OBĚ pole zároveň –
    `vykon_kw` (okamžitý výkon) i `kapacita_kwh` (energie) – ne jen jedno z nich.
    Peak shaving bez obou čísel počítat nejde (simulace potřebuje výkon i kapacitu).

    Výjimka pro ceníkové položky (CRM-08): baterie z prodejního ceníku
    (`zdroj != bess_cenik`) jsou komponenty typu „BMS Growatt“, ke kterým výkon
    ani kapacita neexistují a do simulace nikdy nevstoupí. Kdyby se u nich obojí
    vynucovalo, nešly by naimportovat – a lidé by je začali psát jako „jiná“.
    """
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název je povinný")
    if vstup.typ == "baterie" and (vstup.zdroj or VYCHOZI_ZDROJ) == "bess_cenik":
        if not vstup.vykon_kw or vstup.vykon_kw <= 0 or not vstup.kapacita_kwh or vstup.kapacita_kwh <= 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    "U baterie z ceníku BESS musí být vyplněný výkon (kW) i kapacita "
                    "(kWh) – obojí kladné (METODIKA kap. 3.2). Bez nich by nešel "
                    "spočítat peak shaving."
                ),
            )
    if vstup.platnost_od and vstup.platnost_do and vstup.platnost_od > vstup.platnost_do:
        raise HTTPException(
            status_code=422, detail="Platnost „do“ nesmí být dřív než platnost „od“."
        )
    return nazev


def _cistY_kod(kod: Optional[str]) -> Optional[str]:
    """Prázdný kód se ukládá jako NULL – jinak by unikátní index spadl na
    druhé položce bez kódu."""
    ocisteny = (kod or "").strip()
    return ocisteny or None


def _datum(hodnota: Optional[str]) -> date | None:
    """ISO datum z frontendu na `date`. Prázdno = None."""
    if not hodnota:
        return None
    try:
        return date.fromisoformat(hodnota[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Neplatné datum: {hodnota}")


def _naplni_technologii(t: Technologie, vstup: TechnologieVstup, db: Session, nazev: str) -> None:
    """Přepíše položku katalogu daty z formuláře (sdílí přidání i úprava)."""
    t.typ = vstup.typ
    t.nazev = nazev
    t.model = (vstup.model or "").strip()
    t.kod = _cistY_kod(vstup.kod)
    t.kategorie = (vstup.kategorie or "").strip()
    t.jednotka = (vstup.jednotka or "ks").strip() or "ks"
    t.popis = (vstup.popis or "").strip()
    t.vykon_kw = vstup.vykon_kw
    t.kapacita_kwh = vstup.kapacita_kwh
    t.cena_kc = vstup.cena_kc
    t.cena_nakup_kc = vstup.cena_nakup_kc
    t.sazba_dph = vstup.sazba_dph
    t.ucinnost = vstup.ucinnost
    t.platnost_od = _datum(vstup.platnost_od)
    t.platnost_do = _datum(vstup.platnost_do)
    t.aktivni = vstup.aktivni
    t.extra = _zpracuj_extra(db, vstup.extra)


@router.get("/technologie", response_model=list[TechnologieOut])
def seznam_technologii(
    jen_aktivni: bool = Query(False, description="Vrátit jen aktivní a platné položky"),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Katalog vidí každý s právem na Nabídkovač; editovat smí jen katalogové právo.

    `jen_aktivni=true` používá výběr položky do nabídky – tam nemá smysl nabízet
    vyřazené zboží ani ceník, který ještě neplatí.
    """
    dotaz = db.query(Technologie).options(selectinload(Technologie.prilohy))
    if jen_aktivni:
        dotaz = dotaz.filter(Technologie.aktivni.is_(True))
    ts = dotaz.order_by(Technologie.kategorie, Technologie.nazev, Technologie.id).all()
    if jen_aktivni:
        ts = [t for t in ts if _plati_dnes(t)]
    s_nakupem = muze_katalog(user)
    return [_technologie_out(t, s_nakupem) for t in ts]


@router.get("/technologie/kategorie", response_model=list[str])
def seznam_kategorii(
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Kategorie, které se v katalogu skutečně používají – pro filtr a našeptávač.

    Není to číselník: kategorie je volný text na položce, tenhle endpoint jen
    ukáže, co už někdo napsal, aby nevznikly „Střídače“ a „stridace“ vedle sebe.
    """
    radky = (
        db.query(Technologie.kategorie)
        .filter(Technologie.kategorie != "")
        .distinct()
        .order_by(Technologie.kategorie)
        .all()
    )
    return [k for (k,) in radky]


@router.post("/technologie", response_model=TechnologieOut)
def pridej_technologii(
    vstup: TechnologieVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    nazev = _over_technologii(vstup)
    t = Technologie(typ=vstup.typ, nazev=nazev, zdroj=vstup.zdroj or VYCHOZI_ZDROJ)
    _naplni_technologii(t, vstup, db, nazev)
    t.vytvoril_user_id = user.id
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Kód „{vstup.kod}“ už v katalogu existuje."
        )
    db.refresh(t)
    return _technologie_out(t, True)


@router.put("/technologie/{technologie_id}", response_model=TechnologieOut)
def uprav_technologii(
    technologie_id: int,
    vstup: TechnologieVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    t = db.get(Technologie, technologie_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Položka katalogu neexistuje")
    nazev = _over_technologii(vstup)
    _naplni_technologii(t, vstup, db, nazev)
    # `zdroj` se úpravou nemění – je to informace o původu záznamu, ne pole
    # k vyplnění. Přepnutím by baterie z ceníku BESS tiše vypadla ze simulace.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Kód „{vstup.kod}“ už v katalogu existuje."
        )
    db.refresh(t)
    return _technologie_out(t, True)


@router.post("/technologie/hromadne")
def hromadna_uprava_katalogu(
    vstup: HromadnaUpravaKatalogu,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Zapnout/vypnout nebo přeřadit označené položky (CRM-08).

    Vzniklo kvůli 244 naimportovaným položkám – vyřadit celou kategorii
    z ceníku by jinak byla desítka kliknutí.
    """
    if not vstup.ids:
        return {"upraveno": 0}
    if vstup.aktivni is None and vstup.kategorie is None:
        raise HTTPException(status_code=422, detail="Není co změnit.")
    ts = db.query(Technologie).filter(Technologie.id.in_(vstup.ids)).all()
    for t in ts:
        if vstup.aktivni is not None:
            t.aktivni = vstup.aktivni
        if vstup.kategorie is not None:
            t.kategorie = vstup.kategorie.strip()
    db.commit()
    return {"upraveno": len(ts)}


@router.delete("/technologie/{technologie_id}")
def smaz_technologii(
    technologie_id: int,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Smaže položku i s přílohami.

    Položku, která visí na nějaké nabídce nebo objednávce, smazat nejde –
    rozpis by přišel o vazbu do katalogu (snapshot názvu a ceny by sice
    zůstal, ale ztratil by se technický list a historie). Místo mazání se
    taková položka vypíná zaškrtávátkem „Aktivní“.
    """
    t = db.get(Technologie, technologie_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Položka katalogu neexistuje")

    pouziti = (
        db.query(NabidkaPolozka).filter(NabidkaPolozka.technologie_id == technologie_id).count()
        + db.query(ObjednavkaPolozka)
        .filter(ObjednavkaPolozka.technologie_id == technologie_id)
        .count()
    )
    if pouziti:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Položka je použitá v {pouziti} rozpisech nabídek/objednávek. "
                "Smazat ji nejde – odškrtni „Aktivní“, ať se dál nenabízí."
            ),
        )

    for p in list(t.prilohy):
        katalog_soubory.smaz_soubor(p.soubor_cesta)
    db.delete(t)
    db.commit()
    return {"smazano": technologie_id}


# ---- Přílohy položky katalogu (technický list, foto, certifikát) ----
@router.post("/technologie/{technologie_id}/prilohy", response_model=list[PrilohaOut])
async def nahraj_prilohy(
    technologie_id: int,
    soubory_vstup: list[UploadFile] = File(..., alias="soubory"),
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Nahraje k položce jeden nebo víc souborů najednou.

    Víc souborů schválně: k jedné baterii patří datasheet, prohlášení o shodě
    a pár fotek, a nikdo je nebude nahrávat po jednom.
    """
    t = db.get(Technologie, technologie_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Položka katalogu neexistuje")

    vytvorene: list[TechnologiePriloha] = []
    for soubor in soubory_vstup:
        nazev = soubor.filename or "soubor"
        if not katalog_soubory.je_povolena(nazev):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Soubor „{nazev}“ má nepodporovanou příponu. Povolené: "
                    + ", ".join(sorted(katalog_soubory.POVOLENE_PRIPONY))
                ),
            )
        obsah = await soubor.read()
        if len(obsah) > katalog_soubory.MAX_BAJTU:
            raise HTTPException(
                status_code=413,
                detail=f"Soubor „{nazev}“ je větší než 25 MB.",
            )
        cesta = katalog_soubory.uloz_soubor(technologie_id, nazev, obsah)
        p = TechnologiePriloha(
            technologie_id=technologie_id,
            druh=katalog_soubory.odvod_druh(nazev),
            puvodni_nazev=nazev,
            soubor_cesta=cesta,
            velikost_bajtu=len(obsah),
            nahral_user_id=user.id,
        )
        db.add(p)
        vytvorene.append(p)

    db.commit()
    for p in vytvorene:
        db.refresh(p)
    return [_priloha_out(p) for p in vytvorene]


@router.get("/prilohy/{priloha_id}/soubor")
def stahni_prilohu(
    priloha_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Vydá soubor přílohy. Obrázky a PDF inline (náhled), zbytek ke stažení."""
    p = db.get(TechnologiePriloha, priloha_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Příloha neexistuje")
    try:
        cesta = katalog_soubory.cesta_k_souboru(p.soubor_cesta)
    except ValueError:
        raise HTTPException(status_code=404, detail="Soubor přílohy nenalezen")
    if not cesta.exists():
        raise HTTPException(status_code=404, detail="Soubor přílohy nenalezen")

    mime = katalog_soubory.mime_typ(p.puvodni_nazev)
    inline = mime.startswith("image/") or mime == "application/pdf"
    return FileResponse(
        path=str(cesta),
        media_type=mime,
        filename=p.puvodni_nazev,
        content_disposition_type="inline" if inline else "attachment",
    )


@router.patch("/prilohy/{priloha_id}", response_model=PrilohaOut)
def uprav_prilohu(
    priloha_id: int,
    vstup: PrilohaUprava,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Přepnutí druhu (automat podle přípony minul) nebo doplnění popisku."""
    p = db.get(TechnologiePriloha, priloha_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Příloha neexistuje")
    if vstup.druh is not None:
        p.druh = vstup.druh
    if vstup.popis is not None:
        p.popis = vstup.popis.strip()
    db.commit()
    db.refresh(p)
    return _priloha_out(p)


@router.delete("/prilohy/{priloha_id}")
def smaz_prilohu(
    priloha_id: int,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    p = db.get(TechnologiePriloha, priloha_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Příloha neexistuje")
    katalog_soubory.smaz_soubor(p.soubor_cesta)
    db.delete(p)
    db.commit()
    return {"smazano": priloha_id}


# ================= Rozpis položek nabídky (CRM-08) =================
def _polozky_out(polozky: list, s_nakupem: bool) -> PolozkyOut:
    """Rozpis + souhrn v jednom. Souhrn počítá backend – viz `polozky.py`."""
    return PolozkyOut(
        polozky=[polozky_modul.polozka_out(p, s_nakupem) for p in polozky],
        souhrn=PolozkySouhrn(**polozky_modul.souhrn(polozky)),
        vidi_nakup=s_nakupem,
    )


@router.get("/nabidky/{nabidka_id}/polozky", response_model=PolozkyOut)
def rozpis_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _polozky_out(list(n.polozky), muze_katalog(user))


@router.put("/nabidky/{nabidka_id}/polozky", response_model=PolozkyOut)
def uloz_rozpis_nabidky(
    nabidka_id: int,
    vstup: PolozkyVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Uloží celý rozpis nabídky (CRM-08).

    Rozpis smí upravit každý, kdo smí na nabídku – je to obchodní práce OZ,
    ne správa ceníku. Nákupní ceny přitom mění jen ten, kdo je vidí.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if not muze_katalog(user):
        # Bez práva na katalog se nákupní ceny ignorují, ať je nejde přepsat
        # podvrženým požadavkem (v UI je stejně nikdo takový nevidí).
        for radek in vstup.polozky:
            radek.nakup_jednotkovy = None

    polozky_modul.uloz_rozpis(
        db,
        vstup,
        list(n.polozky),
        lambda: NabidkaPolozka(nabidka_id=nabidka_id, nazev=""),
    )
    db.commit()
    db.refresh(n)
    return _polozky_out(list(n.polozky), muze_katalog(user))


@router.post("/nabidky/{nabidka_id}/polozky/z-katalogu", response_model=PolozkyOut)
def pridej_polozky_z_katalogu(
    nabidka_id: int,
    ids: list[int],
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Přidá na konec rozpisu položky vybrané z katalogu (množství 1).

    Ceny a název se přeberou jako snapshot – pozdější změna ceníku nabídkou
    nehne (viz `polozky.napln_z_katalogu`).
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if not ids:
        return _polozky_out(list(n.polozky), muze_katalog(user))

    nalezene = {t.id: t for t in db.query(Technologie).filter(Technologie.id.in_(ids)).all()}
    dalsi_poradi = max((p.poradi for p in n.polozky), default=-1) + 1
    for i, tid in enumerate(ids):
        t = nalezene.get(tid)
        if t is None:
            continue
        p = NabidkaPolozka(nabidka_id=nabidka_id, nazev=t.nazev, poradi=dalsi_poradi + i, mnozstvi=1)
        polozky_modul.napln_z_katalogu(p, t)
        db.add(p)

    db.commit()
    db.refresh(n)
    return _polozky_out(list(n.polozky), muze_katalog(user))


# ================= Vlastní sloupce katalogu =================
def _sloupec_out(s: KatalogSloupec) -> KatalogSloupecOut:
    return KatalogSloupecOut(id=s.id, klic=s.klic, nazev=s.nazev, typ=s.typ, poradi=s.poradi)


def _uniq_klic(db: Session, nazev: str) -> str:
    """Odvodí strojový klíč z názvu (bez diakritiky, [a-z0-9_]) a zajistí unikátnost."""
    zaklad = unicodedata.normalize("NFKD", nazev).encode("ascii", "ignore").decode()
    zaklad = re.sub(r"[^a-zA-Z0-9]+", "_", zaklad).strip("_").lower()
    if not zaklad:
        zaklad = "sloupec"
    existujici = {k for (k,) in db.query(KatalogSloupec.klic).all()}
    if zaklad not in existujici:
        return zaklad
    i = 2
    while f"{zaklad}_{i}" in existujici:
        i += 1
    return f"{zaklad}_{i}"


@router.get("/katalog-sloupce", response_model=list[KatalogSloupecOut])
def seznam_sloupcu(
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Definice vlastních sloupců katalogu (řazeno dle pořadí, pak názvu)."""
    ss = (
        db.query(KatalogSloupec)
        .order_by(KatalogSloupec.poradi, KatalogSloupec.nazev, KatalogSloupec.id)
        .all()
    )
    return [_sloupec_out(s) for s in ss]


@router.post("/katalog-sloupce", response_model=KatalogSloupecOut)
def pridej_sloupec(
    vstup: KatalogSloupecVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název sloupce je povinný")
    if vstup.typ not in TYPY_SLOUPCE:
        raise HTTPException(status_code=422, detail=f"Neznámý typ sloupce: {vstup.typ}")
    s = KatalogSloupec(
        klic=_uniq_klic(db, nazev),
        nazev=nazev,
        typ=vstup.typ,
        poradi=vstup.poradi,
        vytvoril_user_id=user.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sloupec_out(s)


@router.put("/katalog-sloupce/{sloupec_id}", response_model=KatalogSloupecOut)
def uprav_sloupec(
    sloupec_id: int,
    vstup: KatalogSloupecVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Přejmenování / změna typu / pořadí. `klic` zůstává (drží vazbu na hodnoty)."""
    s = db.get(KatalogSloupec, sloupec_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Sloupec neexistuje")
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název sloupce je povinný")
    if vstup.typ not in TYPY_SLOUPCE:
        raise HTTPException(status_code=422, detail=f"Neznámý typ sloupce: {vstup.typ}")
    s.nazev = nazev
    s.typ = vstup.typ
    s.poradi = vstup.poradi
    db.commit()
    db.refresh(s)
    return _sloupec_out(s)


@router.delete("/katalog-sloupce/{sloupec_id}")
def smaz_sloupec(
    sloupec_id: int,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Smaže definici sloupce. Hodnoty v Technologie.extra zůstanou jako osiřelé
    klíče (neškodí, jen se nezobrazují) – nepřepisujeme kvůli tomu celý katalog."""
    s = db.get(KatalogSloupec, sloupec_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Sloupec neexistuje")
    db.delete(s)
    db.commit()
    return {"smazano": sloupec_id}


# ================= Výpočtová nastavení (verzovaná) =================
def _nastaveni_out(v: VypoctovaNastaveni) -> VypoctovaNastaveniOut:
    return VypoctovaNastaveniOut(
        id=v.id,
        verze=v.verze,
        platne_od=_iso(v.platne_od),
        koeficient_zisku=_num(v.koeficient_zisku),
        min_delka_kontraktu_roky=v.min_delka_kontraktu_roky,
        max_delka_kontraktu_roky=v.max_delka_kontraktu_roky,
        parametry=v.parametry or {},
        vytvoreno_at=_iso(v.vytvoreno_at),
    )


@router.get("/vypoctova-nastaveni", response_model=list[VypoctovaNastaveniOut])
def seznam_nastaveni(
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Historie verzí (nejnovější první). Aktuální = první v seznamu."""
    vs = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).all()
    return [_nastaveni_out(v) for v in vs]


@router.post("/vypoctova-nastaveni", response_model=VypoctovaNastaveniOut)
def uloz_nastaveni(
    vstup: VypoctovaNastaveniVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Uloží NOVOU verzi (stará se nikdy nepřepisuje – viz kap. 4.2 SPEC)."""
    posledni = (
        db.query(VypoctovaNastaveni.verze).order_by(VypoctovaNastaveni.verze.desc()).first()
    )
    dalsi_verze = (posledni[0] + 1) if posledni else 1
    v = VypoctovaNastaveni(
        verze=dalsi_verze,
        koeficient_zisku=vstup.koeficient_zisku,
        min_delka_kontraktu_roky=vstup.min_delka_kontraktu_roky,
        max_delka_kontraktu_roky=vstup.max_delka_kontraktu_roky,
        parametry=vstup.parametry or {},
        vytvoril_user_id=user.id,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return _nastaveni_out(v)


# ================= Sazby distributorů (peak shaving, METODIKA kap. 3.1) =================
def _sazba_out(s: SazbaDistributoru) -> SazbaOut:
    return SazbaOut(
        id=s.id,
        distributor=s.distributor,
        napetova_hladina=s.napetova_hladina,
        struktura_tarifu=s.struktura_tarifu,
        parametry=s.parametry,  # může být None (nova_2027 čeká na sazby ERÚ)
        platne_od=_iso(s.platne_od),
        platne_do=_iso(s.platne_do),
        je_modelovy_odhad=bool(s.je_modelovy_odhad),
        poznamka=s.poznamka or "",
    )


def _parse_datum(hodnota: str, pole: str) -> date:
    try:
        return date.fromisoformat(hodnota)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Neplatné datum v poli {pole}: {hodnota!r}")


def _over_sazbu(vstup: SazbaVstup) -> None:
    """Základní validace číselníků. Konkrétní ceny (parametry) necháváme volné –
    stara_2026 se plní ručně, nova_2027 zůstává None, dokud ERÚ nezveřejní sazby."""
    if vstup.distributor not in DISTRIBUTORI:
        raise HTTPException(status_code=422, detail=f"Neznámý distributor: {vstup.distributor}")
    if vstup.napetova_hladina not in NAPETOVE_HLADINY:
        raise HTTPException(
            status_code=422, detail=f"Neznámá napěťová hladina: {vstup.napetova_hladina}"
        )
    if vstup.struktura_tarifu not in STRUKTURY_TARIFU:
        raise HTTPException(
            status_code=422, detail=f"Neznámá struktura tarifu: {vstup.struktura_tarifu}"
        )


@router.get("/sazby", response_model=list[SazbaOut])
def seznam_sazeb(
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Přehled sazeb (vidí každý s právem na Nabídkovač – OZ podle nich vybírá
    distributora/hladinu). Editace je pod katalogovým právem (vedení/admin)."""
    ss = (
        db.query(SazbaDistributoru)
        .order_by(
            SazbaDistributoru.distributor,
            SazbaDistributoru.napetova_hladina,
            SazbaDistributoru.struktura_tarifu,
            SazbaDistributoru.platne_od.desc(),
        )
        .all()
    )
    return [_sazba_out(s) for s in ss]


@router.post("/sazby", response_model=SazbaOut)
def pridej_sazbu(
    vstup: SazbaVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    """Založí sazbu (kap. 6–7 – takhle kolega doplní EG.D/PRE a časem i sazby 2027)."""
    _over_sazbu(vstup)
    platne_od = _parse_datum(vstup.platne_od, "platne_od")
    platne_do = _parse_datum(vstup.platne_do, "platne_do") if vstup.platne_do else None
    s = SazbaDistributoru(
        distributor=vstup.distributor,
        napetova_hladina=vstup.napetova_hladina,
        struktura_tarifu=vstup.struktura_tarifu,
        parametry=vstup.parametry,
        platne_od=platne_od,
        platne_do=platne_do,
        je_modelovy_odhad=vstup.je_modelovy_odhad,
        poznamka=(vstup.poznamka or "").strip(),
        vytvoril_user_id=user.id,
    )
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Sazba s touto kombinací distributor/hladina/struktura a datem "
                "platnosti už existuje (uprav ji, nebo změň datum platnosti)."
            ),
        )
    db.refresh(s)
    return _sazba_out(s)


@router.put("/sazby/{sazba_id}", response_model=SazbaOut)
def uprav_sazbu(
    sazba_id: int,
    vstup: SazbaVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    s = db.get(SazbaDistributoru, sazba_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Sazba neexistuje")
    _over_sazbu(vstup)
    s.distributor = vstup.distributor
    s.napetova_hladina = vstup.napetova_hladina
    s.struktura_tarifu = vstup.struktura_tarifu
    s.parametry = vstup.parametry
    s.platne_od = _parse_datum(vstup.platne_od, "platne_od")
    s.platne_do = _parse_datum(vstup.platne_do, "platne_do") if vstup.platne_do else None
    s.je_modelovy_odhad = vstup.je_modelovy_odhad
    s.poznamka = (vstup.poznamka or "").strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Sazba s touto kombinací distributor/hladina/struktura a datem "
                "platnosti už existuje."
            ),
        )
    db.refresh(s)
    return _sazba_out(s)


@router.delete("/sazby/{sazba_id}")
def smaz_sazbu(
    sazba_id: int,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    s = db.get(SazbaDistributoru, sazba_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Sazba neexistuje")
    db.delete(s)
    db.commit()
    return {"smazano": sazba_id}


# ================= Profil spotřeby (načtení z nahraného souboru) =================
def _profil_souhrn(db: Session, nabidka_id: int) -> dict:
    """Souhrn načteného 15min profilu nabídky (počet, rozsah, max) pro UI."""
    radky = (
        db.query(SpotrebaProfil.cas, SpotrebaProfil.hodnota_kw)
        .filter(SpotrebaProfil.nabidka_id == nabidka_id, SpotrebaProfil.hodnota_kw.isnot(None))
        .all()
    )
    if not radky:
        return {"pocet": 0}
    casy = [r[0] for r in radky]
    hodnoty = [float(r[1]) for r in radky]
    return {
        "pocet": len(radky),
        "od": _iso(min(casy)),
        "do": _iso(max(casy)),
        "max_kw": round(max(hodnoty), 2),
    }


@router.get("/nabidky/{nabidka_id}/peak-shaving/profil-souhrn")
def profil_souhrn(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _profil_souhrn(db, nabidka_id)


def _zpracuj_profil_dokumentu(db: Session, d: NabidkaDokument) -> dict:
    """Naparsuje soubor dokumentu do `spotreba_profil` jeho nabídky.

    „Poslední vyhrává“ (audit SP-2): nahradí se CELÝ dosavadní profil nabídky
    (i z jiných dokumentů) – dřív se mazaly jen řádky ze stejného dokumentu
    a dva různé soubory se tiše sečetly do dvojnásobné spotřeby. Duplicitní
    časy uvnitř souboru (podzimní přechod času) se slučují před vkladem,
    unikátnost (nabidka_id, cas) jistí i DB constraint.

    Vytažené z endpointu, aby se profil dal zpracovat i automaticky hned po
    nahrání souboru (viz `nahraj_dokument`) – čekání na ruční kliknutí bylo
    zdrojem nabídek, které se počítaly bez dat spotřeby.
    """
    if d.typ not in ("spotreba_csv", "jiny"):
        raise HTTPException(
            status_code=422, detail="Tenhle dokument není profil spotřeby (nahraj CSV/XLS se spotřebou)."
        )
    cesta = soubory.UPLOAD_DIR / d.soubor_cesta
    pripona = Path(d.soubor_cesta).suffix.lower()
    try:
        body = profil_import.nacti_profil(str(cesta), pripona)
    except FileNotFoundError:
        raise HTTPException(status_code=422, detail="Soubor se nepodařilo najít na disku.")
    except ValueError as e:
        d.stav_zpracovani = "chyba_extrakce"
        db.commit()
        raise HTTPException(status_code=422, detail=f"Zpracování profilu selhalo: {e}")

    body, pocet_duplicit = profil_import.deduplikuj_casy(body)

    db.query(SpotrebaProfil).filter(
        SpotrebaProfil.nabidka_id == d.nabidka_id,
    ).delete(synchronize_session=False)
    db.bulk_insert_mappings(
        SpotrebaProfil,
        [
            {"nabidka_id": d.nabidka_id, "cas": cas, "hodnota_kw": kw, "zdroj_dokument_id": d.id}
            for cas, kw in body
        ],
    )
    d.stav_zpracovani = "extrahovano"
    db.commit()
    out = {"dokument_id": d.id, **_profil_souhrn(db, d.nabidka_id)}
    if pocet_duplicit:
        out["slouceno_duplicitnich_radku"] = pocet_duplicit
    return out


@router.post("/nabidky/{nabidka_id}/dokumenty/{dokument_id}/zpracuj-profil")
def zpracuj_profil(
    nabidka_id: int,
    dokument_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Naparsuje nahraný soubor s 15min profilem (XLS/XLSX/CSV) do `spotreba_profil`.

    Nabídka je v cestě schválně, i když by se dala odvodit z dokumentu: dřív šlo
    poslat id dokumentu PATŘÍCÍHO JINÉ NABÍDCE a profil se zapsal do ní (a předchozí
    profil té nabídky se přitom smazal, „poslední vyhrává“). Přesně to se stalo,
    když frontend omylem poslal id nabídky místo id dokumentu — většinou to skončilo
    404, ale při shodě čísel by se ticho přepsala cizí data. Teď se příslušnost
    ověřuje a nesoulad je 422.
    """
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    d = db.get(NabidkaDokument, dokument_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Dokument neexistuje")
    if d.nabidka_id != nabidka_id:
        raise HTTPException(
            status_code=422,
            detail="Tenhle dokument patří jiné nabídce — profil by se zapsal do cizích dat.",
        )
    return _zpracuj_profil_dokumentu(db, d)


# ================= Peak shaving – výpočet (METODIKA kap. 4–5) =================
def _plati_pro_rok(sazba: SazbaDistributoru, rok: int) -> bool:
    """Platí sazba pro daný rok? (platne_od.rok <= rok <= platne_do.rok, je-li do)."""
    if sazba.platne_od.year > rok:
        return False
    if sazba.platne_do is not None and sazba.platne_do.year < rok:
        return False
    return True


def _najdi_sazbu(
    db: Session, distributor: str, hladina: str, struktura: str, rok: int
) -> SazbaDistributoru | None:
    """Vybere sazbu dané struktury platnou pro rok (nejnovější podle platne_od)."""
    kandidati = (
        db.query(SazbaDistributoru)
        .filter(
            SazbaDistributoru.distributor == distributor,
            SazbaDistributoru.napetova_hladina == hladina,
            SazbaDistributoru.struktura_tarifu == struktura,
        )
        .order_by(SazbaDistributoru.platne_od.desc())
        .all()
    )
    for s in kandidati:
        if _plati_pro_rok(s, rok):
            return s
    return None


def _interval_h_z_profilu(casy: list[datetime]) -> float:
    """Odvodí délku intervalu (h) z prvních dvou časových značek; fallback 0,25 h."""
    if len(casy) >= 2:
        delta = (casy[1] - casy[0]).total_seconds() / 3600.0
        if delta > 0:
            return delta
    return peak_shaving.VYCHOZI_INTERVAL_H


def _zvaliduj_a_orizni_profil(
    casy: list[datetime],
    hodnoty: list[float],
    interval_h: float,
    pro_peak_shaving: bool = False,
) -> tuple[list[datetime], list[float], list[str]]:
    """Ochrana ročních výpočtů před neúplným/přesahujícím profilem (SP-1).

    Profil delší než rok ořízne na posledních 12 celých měsíců (s upozorněním
    do výstupu); profil, který ani potom není použitelný jako roční (málo dní,
    chybějící měsíce, díry > 2 %), shodí na HTTP 422 – radši žádné číslo než
    sebejistě špatná „roční“ ekonomika (bughunt testy T2/T3).

    S `pro_peak_shaving=True` se toleruje „rok a kousek“ s překrývajícími se
    okrajovými měsíci – ořízne se na klouzavé okno posledního roku a kontroluje
    se pokrytí po číslech měsíce (peak shaving bere měsíční maxima). PPA volá
    bez přepínače (přísný režim – energii sčítá, překryv by ji zdvojnásobil).
    """
    casy, hodnoty, orezano = profil_pokryti.orizni_na_posledni_rok(
        casy, hodnoty, interval_h, pro_peak_shaving=pro_peak_shaving
    )
    ok, duvod = profil_pokryti.zkontroluj_pokryti(
        casy, interval_h, pro_peak_shaving=pro_peak_shaving
    )
    if not ok:
        raise HTTPException(status_code=422, detail=f"Profil spotřeby nelze použít: {duvod}")
    upozorneni: list[str] = []
    if orezano:
        upozorneni.append(
            "Profil byl delší než rok – pro výpočet se použilo posledních 12 celých "
            f"měsíců ({min(casy).strftime('%m/%Y')}–{max(casy).strftime('%m/%Y')})."
        )
    return casy, hodnoty, upozorneni


def _varianta_json(v: peak_shaving.Varianta) -> dict:
    return {
        "baterie_id": v.baterie_id,
        "nazev": v.nazev,
        "pocet_kusu": v.pocet_kusu,
        "celkovy_vykon_kw": round(v.celkovy_vykon_kw, 3),
        "celkova_kapacita_kwh": round(v.celkova_kapacita_kwh, 3),
        # Simulace jede na využitelné kapacitě (SOC okno) a se ztrátami (PS-5).
        "vyuzitelna_kapacita_kwh": round(v.vyuzitelna_kapacita_kwh, 3),
        "ucinnost_rt": round(v.ucinnost_rt, 4),
        "cena_celkem_kc": round(v.cena_celkem_kc, 2),
        # Fyzický strop simulace vs. roční složka optimální RK (PS-6/PS-7).
        "strop_kw": round(v.strop_kw, 2),
        "rezerva_rk_procenta": round(v.rezerva_rk_procenta, 2),
        "nova_rezervovana_kapacita_kw": round(v.nova_rezervovana_kapacita_kw, 2),
        # Rozpad úspory (PS-7): audit RK zdarma + přínos baterie.
        "uspora_bez_investice_2026_kc": round(v.uspora_bez_investice_2026, 2),
        "prinos_baterie_2026_kc": round(v.prinos_baterie_2026, 2),
        "rocni_uspora_2026_kc": round(v.rocni_uspora_2026, 2),
        "navratnost_roky": (round(v.navratnost_roky, 2) if v.navratnost_roky is not None else None),
        # Návratnost podle modelů (2026 / 2027 – jediný model bez slevy AKU, PS-3).
        "navratnost_2026": (round(v.navratnost_2026, 2) if v.navratnost_2026 is not None else None),
        "navratnost_2027": (
            round(v.navratnost_2027, 2) if v.navratnost_2027 is not None else None
        ),
        # Reálná návratnost z kombinovaného cash flow – řídí `doporuceno`.
        "payback_roky": (round(v.payback_roky, 2) if v.payback_roky is not None else None),
        # NPV na horizontu životnosti (PS-8/PS-9) – řídí výběr vítěze.
        "npv_kc": round(v.npv_kc, 2),
        "irr": round(v.irr, 4) if v.irr is not None else None,
        "npv_horizont_roky": v.npv_horizont_roky,
        "npv_pouzit_model_2027": v.npv_pouzit_model_2027,
        # Rozpis cash flow po letech (hodnoty zaokrouhluje už _roky_cash_flow).
        "roky": v.roky,
        "doporuceno": v.doporuceno,
        # Obě varianty základu NPV – FE mezi nimi přepíná bez přepočtu.
        "zaklad_npv": v.zaklad_npv,
        "npv_varianty": {
            klic: {
                "npv_kc": round(x["npv_kc"], 2),
                "irr": round(x["irr"], 4) if x["irr"] is not None else None,
                "payback_roky": (
                    round(x["payback_roky"], 2) if x["payback_roky"] is not None else None
                ),
                "doporuceno": x["doporuceno"],
                "pouzit_model_2027": x["pouzit_model_2027"],
                "roky": x["roky"],
            }
            for klic, x in (v.npv_varianty or {}).items()
        },
        "ekonomika_2026": {
            k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.ekonomika_2026.items()
        },
        "ekonomika_2027": {
            k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.ekonomika_2027.items()
        },
        # Obchodování na spotu (None u čistého peak shavingu).
        "rezim": v.rezim,
        "zisk_spot_kc": round(v.zisk_spot_kc, 2),
        "ekonomika_spot": v.ekonomika_spot,
    }


def _profil_pro_peak_shaving_s_casy(
    db: Session, nabidka_id: int
) -> tuple[list[datetime], list[float], float, list[str]]:
    """Jako `_profil_pro_peak_shaving`, ale vrací i časové značky.

    Ekonomice stačí čísla měsíců, graf průběhu ale potřebuje přesný čas každého
    intervalu (osa X, proklik na událost) – proto tahle varianta.
    """
    radky = (
        db.query(SpotrebaProfil)
        .filter(
            SpotrebaProfil.nabidka_id == nabidka_id,
            SpotrebaProfil.hodnota_kw.isnot(None),
        )
        .order_by(SpotrebaProfil.cas)
        .all()
    )
    if not radky:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nabídka nemá nahraný 15min profil odběru (kW). Nahrání/parsování "
                "CSV se řeší samostatně – bez profilu nejde peak shaving počítat."
            ),
        )
    casy_profilu = [r.cas for r in radky]
    profil_kw = [float(r.hodnota_kw) for r in radky]
    interval_h = _interval_h_z_profilu(casy_profilu)
    # Validace pokrytí roku + případné oříznutí na posledních 12 měsíců (SP-1).
    # pro_peak_shaving=True: toleruje „rok a kousek“ s překrývajícími se okraji.
    casy_profilu, profil_kw, upozorneni_profilu = _zvaliduj_a_orizni_profil(
        casy_profilu, profil_kw, interval_h, pro_peak_shaving=True
    )
    return casy_profilu, profil_kw, interval_h, upozorneni_profilu


def _profil_pro_peak_shaving(
    db: Session, nabidka_id: int
) -> tuple[list[float], list[int], float, list[str]]:
    """Načte 15min profil nabídky pro peak shaving → (kW, měsíce, interval_h, upozornění)."""
    casy, profil_kw, interval_h, upozorneni = _profil_pro_peak_shaving_s_casy(db, nabidka_id)
    return profil_kw, [c.month for c in casy], interval_h, upozorneni


# Kolika nejlepším variantám se graf + citlivost počítá rovnou při výpočtu.
# Zbytek se dopočítá až na vyžádání (jedna varianta ≈ 0,2 s, všech 84 ≈ 15 s).
POCET_VARIANT_S_GRAFEM = 3


def _prubeh_spot(
    db: Session,
    casy: list[datetime],
    profil_kw: list[float],
    mesice: list[int],
    interval_h: float,
    vykon_kw: float,
    kapacita_kwh: float,
    ucinnost: float,
    vj: dict,
    popis: dict,
) -> tuple[dict, list[float] | None, list[str]]:
    """Průběh baterie pro nitkový graf v režimech Kombinace/SPOT.

    Bere **stropy a parametry z uloženého výsledku** (`ekonomika_spot`), ne
    z aktuálního nastavení – graf tak ukazuje přesně to chování, ze kterého
    vyšla uložená ekonomika. Když ceny nejde načíst (např. se vyhodil rok
    z databáze), spadne se na čistě peak-shavingový průběh s upozorněním.
    """
    ek_spot = vj.get("ekonomika_spot") or {}
    upozorneni: list[str] = []
    rok_cen = (ek_spot.get("info_cen") or {}).get("rok_cen")
    roky = spot_ceny.dostupne_roky(db)
    if not roky:
        return (
            peak_shaving.prubeh_baterie(
                profil_kw, float(vj["strop_kw"]), vykon_kw, kapacita_kwh, interval_h, ucinnost
            ),
            None,
            ["Spotové ceny nejsou v databázi – graf ukazuje jen srážení špiček."],
        )
    if rok_cen not in roky:
        upozorneni.append(
            f"Ceny roku {rok_cen} už v databázi nejsou – graf jede na roce {max(roky)}, "
            "takže se může lišit od uložené ekonomiky."
        )
        rok_cen = max(roky)
    ceny, _ = spot_ceny.ceny_pro_casy(casy, spot_ceny.nacti_rok(db, int(rok_cen)))

    stropy = {
        int(m["mesic"]): float(m["strop_kw"])
        for m in (ek_spot.get("mesice") or [])
        if m.get("strop_kw") is not None
    }
    opotrebeni = float(ek_spot.get("opotrebeni_kc_mwh") or 0.0)
    p = spot_arbitraz.prubeh_roku(
        ceny,
        profil_kw,
        mesice,
        [c.toordinal() for c in casy],
        stropy,
        vykon_kw,
        kapacita_kwh,
        spot_arbitraz.nastaveni_z_json(ek_spot.get("nastaveni")),
        opotrebeni,
        interval_h,
        ucinnost,
    )
    return p, ceny, upozorneni


def _spot_kontext(
    db: Session,
    casy_profilu: list[datetime],
    mesice: list[int],
    vstup: PeakShavingVstup,
    ps_param,
) -> tuple[object | None, list[str]]:
    """Sestaví kontext pro obchodování na spotu (ceny + parametry).

    Ceny se načtou z `spotove_ceny` (seed z přiložených dat při startu appky)
    a napárují na časy profilu. Rok cen se bere ze vstupu, jinak z manažerského
    nastavení `spot_referencni_rok`, jinak nejnovější dostupný. Když ceny
    v databázi nejsou vůbec, vrací `None` a výpočet spadne na čistý peak
    shaving s upozorněním – radši nabídka bez obchodu než nabídka z ničeho.
    """
    upozorneni: list[str] = []
    roky = spot_ceny.dostupne_roky(db)
    if not roky:
        return None, [
            "Spotové ceny nejsou v databázi – obchodování se nepočítá. Naimportuj je "
            "skriptem `python -m scripts.import_spot_ceny --z-csv --do-db`."
        ]
    rok = vstup.spot_referencni_rok or int(ps_param("spot_referencni_rok", 0)) or max(roky)
    if rok not in roky:
        upozorneni.append(
            f"Spotové ceny roku {rok} nejsou k dispozici – použit nejbližší dostupný rok."
        )
        rok = min(roky, key=lambda r: abs(r - rok))
    rada = spot_ceny.nacti_rok(db, rok)
    ceny, info = spot_ceny.ceny_pro_casy(casy_profilu, rada)
    if not info["stejny_rok"]:
        upozorneni.append(
            f"Profil odběru je z jiného roku než ceny ({rok}) – dny se párovaly podle "
            f"měsíce a dne v týdnu ({info['parovano_dnu']} dnů), aby pracovní dny "
            "dostaly ceny pracovních dnů."
        )
    if info["chybejici_intervaly"]:
        upozorneni.append(
            f"U {info['chybejici_intervaly']} intervalů profilu se nenašla spotová cena "
            "(použita nula) – zkontroluj rozsah nahraných cen."
        )

    max_export = vstup.max_export_kw
    nastaveni_spot = spot_arbitraz.NastaveniSpot(
        marze_nakup_kc_mwh=ps_param("spot_marze_nakup_kc_mwh", spot_arbitraz.VYCHOZI_MARZE_KC_MWH),
        marze_prodej_kc_mwh=ps_param(
            "spot_marze_prodej_kc_mwh", spot_arbitraz.VYCHOZI_MARZE_KC_MWH
        ),
        regulovane_nakup_kc_mwh=ps_param(
            "spot_regulovane_nakup_kc_mwh", spot_arbitraz.VYCHOZI_REGULOVANE_NAKUP_KC_MWH
        ),
        regulovane_prodej_kc_mwh=ps_param(
            "spot_regulovane_prodej_kc_mwh", spot_arbitraz.VYCHOZI_REGULOVANE_PRODEJ_KC_MWH
        ),
        dan_z_elektriny_kc_mwh=ps_param(
            "spot_dan_z_elektriny_kc_mwh", spot_arbitraz.VYCHOZI_DAN_Z_ELEKTRINY_KC_MWH
        ),
        cyklu_zivotnosti=int(
            ps_param("spot_cyklu_zivotnosti", spot_arbitraz.VYCHOZI_CYKLU_ZIVOTNOSTI)
        ),
        max_cyklu_rok=(ps_param("spot_max_cyklu_rok", 0.0) or None),
        umoznit_export=(max_export is None or max_export > 0),
        max_export_kw=(float(max_export) if max_export else None),
        bezpecnostni_rezerva_procenta=ps_param(
            "spot_bezpecnostni_rezerva_procenta",
            spot_arbitraz.VYCHOZI_BEZPECNOSTNI_REZERVA_PROCENTA,
        ),
    )
    kontext = spot_arbitraz.Kontext(
        ceny_kc_mwh=ceny,
        mesice=mesice,
        dny=[c.toordinal() for c in casy_profilu],
        nastaveni=nastaveni_spot,
        info_cen=info,
    )
    return kontext, upozorneni


def _detail_varianty(
    vj: dict,
    profil_kw: list[float],
    mesice: list[int],
    interval_h: float,
    rezervovana_kapacita_kw: float,
) -> dict:
    """Dopočítá graf měsíčních maxim + citlivost stropu (PS-10) pro variantu.

    Pracuje nad JSON podobou varianty (`_varianta_json`), takže se dá zavolat
    i dodatečně nad už uloženým řešením.
    """
    graf = peak_shaving.graf_maxima(
        profil_kw,
        mesice,
        vj["celkovy_vykon_kw"],
        vj["vyuzitelna_kapacita_kwh"],
        vj["strop_kw"],
        interval_h,
        vj["ucinnost_rt"],
    )
    # Referenční čáry grafu. Rok 2026 se platí z rezervované kapacity (RK),
    # rok 2027 z rezervovaného příkonu (RP) ze smlouvy o připojení – jsou to
    # jiná čísla z jiných optimalizací, takže graf nese obě sady a frontend
    # kreslí tu, která patří k zobrazenému roku (dřív kreslil vždy RK, i když
    # sloupce byly z modelu 2027 – oprava 27. 7. 2026).
    graf["rp_soucasna_kw"] = round(rezervovana_kapacita_kw, 2)
    graf["rp_nova_kw"] = round(vj["nova_rezervovana_kapacita_kw"], 2)
    ek27 = vj.get("ekonomika_2027") or {}
    if ek27.get("status") == "spocitano":
        graf["rp_soucasna_2027_kw"] = _num(ek27.get("rp_soucasny_kw"))
        graf["rp_nova_2027_kw"] = _num(ek27.get("rp_novy_kw"))
    return {
        "graf": graf,
        "citlivost_stropu": peak_shaving.citlivost_stropu(
            profil_kw,
            vj["celkovy_vykon_kw"],
            vj["vyuzitelna_kapacita_kwh"],
            vj["strop_kw"],
            vj["rezerva_rk_procenta"],
            interval_h,
            vj["ucinnost_rt"],
        ),
    }


@router.post("/nabidky/{nabidka_id}/peak-shaving/vypocet")
def spocti_peak_shaving(
    nabidka_id: int,
    vstup: PeakShavingVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Spustí výpočet peak shavingu a uloží výsledek do `navrhovana_reseni`.

    Postup dle METODIKY kap. 4–5:
    1. načte 15min profil odběru z `spotreba_profil` dané nabídky,
    2. najde sazby distributora (stara_2026 pro výběr varianty, nova_2027 pro info),
    3. projede katalog baterií × počty kusů, vybere nejrychlejší návratnost,
    4. uloží `NavrhovaneReseni` (typ_reseni = peak_shaving) s ekonomikou 2026 i 2027.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if vstup.rezervovana_kapacita_kw <= 0:
        raise HTTPException(status_code=422, detail="Rezervovaná kapacita musí být kladná.")

    # 1) profil odběru (kW) z uložené časové řady. Časy potřebujeme i kvůli
    # napárování spotových cen (režimy Kombinace/SPOT).
    casy_profilu, profil_kw, interval_h, upozorneni_profilu = (
        _profil_pro_peak_shaving_s_casy(db, nabidka_id)
    )
    mesice = [c.month for c in casy_profilu]

    # 2) sazby (stara_2026 povinná pro výběr; nova_2027 volitelná – jen info)
    sazba_2026 = _najdi_sazbu(db, vstup.distributor, vstup.napetova_hladina, "stara_2026", 2026)
    if sazba_2026 is None or not sazba_2026.parametry:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Chybí sazba stara_2026 pro {vstup.distributor}/{vstup.napetova_hladina}. "
                "Doplň ji v adminu (sazby distributorů)."
            ),
        )
    p2026 = sazba_2026.parametry
    cena_rezervace = p2026.get("cena_rezervovana_kapacita_kc_kw_rok")
    if cena_rezervace is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Sazba stara_2026 pro {vstup.distributor}/{vstup.napetova_hladina} nemá "
                "vyplněnou cenu rezervované kapacity – doplň ji v adminu."
            ),
        )

    # Pokuta za překročení RK se ODVOZUJE z měsíční RK (bod 4.24 výměru:
    # 1,5× měsíční cena měsíční RK), ne ze samostatného čísla v sazebníku –
    # audit 16. 7. 2026, PS-2. Starší klíč cena_prekroceni_kc_kw slouží jen
    # jako fallback pro ručně založené sazby bez měsíční RK.
    upozorneni_sazeb: list[str] = []
    cena_mesicni_rk = p2026.get("cena_mesicni_rk_kc_kw_mesic")
    if cena_mesicni_rk is not None:
        cena_prekroceni = peak_shaving.pokuta_prekroceni_rk_kc_kw(float(cena_mesicni_rk))
        pokuta_odvozena = True
    elif p2026.get("cena_prekroceni_kc_kw") is not None:
        cena_prekroceni = float(p2026["cena_prekroceni_kc_kw"])
        pokuta_odvozena = False
        upozorneni_sazeb.append(
            "Sazba nemá vyplněnou měsíční RK – pokuta za překročení převzata "
            "ze staršího pole sazebníku. Doplň měsíční RK v adminu (pokuta se "
            "pak správně odvodí jako 1,5× měsíční RK dle bodu 4.24 výměru)."
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Sazba stara_2026 pro {vstup.distributor}/{vstup.napetova_hladina} nemá "
                "vyplněnou měsíční RK (Kč/kW/měsíc) – bez ní nejde odvodit pokuta "
                "za překročení (1,5× měsíční RK). Doplň ji v adminu."
            ),
        )

    # Rok 2027 (nová struktura ERÚ) jen pro VN/VVN – NN appka pro peak shaving
    # nenabízí (kap. 1), takže na NN se nova_2027 nikdy neaplikuje.
    sazba_2027 = None
    parametry_2027 = None
    je_modelovy_2027 = False
    if vstup.napetova_hladina in ("vn", "vvn"):
        sazba_2027 = _najdi_sazbu(db, vstup.distributor, vstup.napetova_hladina, "nova_2027", 2027)
        if sazba_2027 is not None:
            parametry_2027 = sazba_2027.parametry
            je_modelovy_2027 = bool(sazba_2027.je_modelovy_odhad)

    # 3) katalog baterií (typ=baterie, aktivní, s výkonem i kapacitou – kap. 3.2).
    # `baterie_ids` ve vstupu = OZ si ručně vybral, které produkty počítat
    # (prázdné/None = celý katalog). Tentýž dotaz používá i návrh baterie u PPA.
    tech = _dotaz_baterie_katalog(db, vstup.baterie_ids).all()
    if vstup.baterie_ids and not tech:
        raise HTTPException(
            status_code=422,
            detail=(
                "Žádná z vybraných baterií není použitelná (musí být dostupná a mít "
                "vyplněný výkon, kapacitu i cenu). Vyber jiné, nebo počítej celý katalog."
            ),
        )
    baterie = [
        peak_shaving.Baterie(
            id=t.id,
            nazev=t.nazev,
            vykon_kw=float(t.vykon_kw),
            kapacita_kwh=float(t.kapacita_kwh),
            cena_kc=float(t.cena_kc) if t.cena_kc is not None else 0.0,
            # Round-trip účinnost z katalogu; chybějící/nesmyslná → default
            # 0,88 (audit PS-5). Toleruje zadání v procentech.
            ucinnost_rt=peak_shaving.normalizuj_ucinnost_rt(t.ucinnost),
            # Nové parametry z ceníku BESS (Technologie.extra) – užitná kapacita
            # a reálný AC výkon střídačů na kus. Chybí-li, výpočet spadne na
            # jmenovité hodnoty (viz Baterie).
            uzitna_kapacita_kwh=_num((t.extra or {}).get("uzitna_kapacita_kwh")),
            max_vykon_stridacu_kw=_num((t.extra or {}).get("max_vykon_stridacu_kw")),
            # Počet cyklů životnosti pro náklad opotřebení (režimy Kombinace/
            # SPOT). Chybí-li u produktu, použije se admin default.
            cyklu_zivotnosti=(
                int(_num((t.extra or {}).get("cyklu_zivotnosti")))
                if _num((t.extra or {}).get("cyklu_zivotnosti"))
                else None
            ),
        )
        for t in tech
        if float(t.vykon_kw) > 0 and float(t.kapacita_kwh) > 0 and t.cena_kc
    ]

    # práh nedoporučené návratnosti z aktuální verze výpočtových nastavení (kap. 4.5)
    aktualni_nastaveni = (
        db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    )
    max_navratnost = peak_shaving.VYCHOZI_MAX_NAVRATNOST_ROKY
    if aktualni_nastaveni is not None and aktualni_nastaveni.parametry:
        max_navratnost = float(
            aktualni_nastaveni.parametry.get(
                "max_navratnost_roky_peak_shaving", peak_shaving.VYCHOZI_MAX_NAVRATNOST_ROKY
            )
        )

    # Cena energie pro ocenění ztrát baterie (audit PS-5): vstup OZ má
    # přednost, jinak manažerské nastavení, jinak kódový default.
    cena_energie = vstup.cena_energie_kc_mwh
    if cena_energie is None and aktualni_nastaveni is not None and aktualni_nastaveni.parametry:
        cena_energie = aktualni_nastaveni.parametry.get("ps_cena_energie_kc_mwh")
    if cena_energie is None:
        cena_energie = peak_shaving.VYCHOZI_CENA_ENERGIE_KC_MWH

    # Rezerva sjednané RK nad nalezený strop (audit PS-6), default 5 %.
    rezerva_rk = None
    if aktualni_nastaveni is not None and aktualni_nastaveni.parametry:
        rezerva_rk = aktualni_nastaveni.parametry.get("ps_rezerva_rk_procenta")
    if rezerva_rk is None:
        rezerva_rk = peak_shaving.VYCHOZI_REZERVA_RK_PROCENTA

    # NPV parametry (audit PS-8/PS-9): diskont, horizont, O&M, degradace úspor.
    def _ps_param(klic: str, default: float) -> float:
        if aktualni_nastaveni is not None and aktualni_nastaveni.parametry:
            hodnota = aktualni_nastaveni.parametry.get(klic)
            if hodnota is not None:
                try:
                    return float(hodnota)
                except (TypeError, ValueError):
                    pass
        return default

    npv_nastaveni = peak_shaving.NastaveniNpv(
        diskontni_sazba=_ps_param("ps_diskontni_sazba", peak_shaving.VYCHOZI_PS_DISKONT),
        horizont_roky=int(_ps_param("ps_horizont_npv_roky", peak_shaving.VYCHOZI_PS_HORIZONT_ROKY)),
        oam_procenta_capex_rok=_ps_param(
            "ps_oam_procenta_capex_rok", peak_shaving.VYCHOZI_PS_OAM_PROCENTA_CAPEX
        ),
        degradace_uspor_procenta_rok=_ps_param(
            "ps_degradace_uspor_procenta_rok", peak_shaving.VYCHOZI_PS_DEGRADACE_USPOR_PROCENTA
        ),
    )

    # 3b) spotové ceny pro režimy Kombinace/SPOT. Načtou se JEDNOU za výpočet
    # a napárují na časy profilu – varianty si pak kontext jen půjčují.
    spot_kontext = None
    upozorneni_spot: list[str] = []
    if vstup.rezim in (spot_arbitraz.REZIM_KOMBINACE, spot_arbitraz.REZIM_SPOT):
        spot_kontext, upozorneni_spot = _spot_kontext(
            db, casy_profilu, mesice, vstup, _ps_param
        )

    # 4) výpočet (kap. 4.2–4.6)
    vysledek = peak_shaving.vyber_reseni(
        baterie_katalog=baterie,
        profil_kw=profil_kw,
        mesice=mesice,
        rezervovana_kapacita_kw=vstup.rezervovana_kapacita_kw,
        cena_rezervace_kc_kw_rok=float(cena_rezervace),
        cena_prekroceni_kc_kw=float(cena_prekroceni),
        max_navratnost_roky=max_navratnost,
        interval_h=interval_h,
        parametry_2027=parametry_2027,
        je_modelovy_2027=je_modelovy_2027,
        cena_energie_kc_mwh=float(cena_energie),
        rezerva_rk_procenta=float(rezerva_rk),
        rezervovany_prikon_kw=(
            float(vstup.rezervovany_prikon_kw) if vstup.rezervovany_prikon_kw else None
        ),
        uvazovat_snizeni_rp=bool(vstup.uvazovat_snizeni_rp),
        cena_mesicni_rk_kc_kw_mesic=(
            float(cena_mesicni_rk) if cena_mesicni_rk is not None else None
        ),
        npv_nastaveni=npv_nastaveni,
        max_vykon_stridace_kw=(
            float(vstup.max_vykon_stridace_kw) if vstup.max_vykon_stridace_kw else None
        ),
        rezim=vstup.rezim,
        spot_kontext=spot_kontext,
    )

    # Upozornění k modelu 2027 (audit PS-4).
    upozorneni_rp: list[str] = []
    if parametry_2027:
        if not vstup.rezervovany_prikon_kw:
            upozorneni_rp.append(
                "Rezervovaný příkon ze smlouvy o připojení nebyl zadán – model 2027 "
                "používá současnou rezervovanou kapacitu. Skutečný RP bývá vyšší, "
                "náklad 2027 tak může být podhodnocený."
            )
        if vstup.uvazovat_snizeni_rp:
            upozorneni_rp.append(
                "Model 2027 předpokládá snížení rezervovaného příkonu na novou RK – "
                "jde o jednosměrnou změnu smlouvy o připojení (zpětné navýšení je "
                "zpoplatněno dle přílohy 2 vyhlášky č. 16/2016 Sb.)."
            )
            # RP se v NTS sjednává jednou na celý rok (žádné měsíční dokupy),
            # takže vědomé překročení je smluvní riziko, ne jen položka nákladu.
            dop_2027 = (
                vysledek.doporucena.ekonomika_2027 if vysledek.doporucena is not None else {}
            ) or {}
            if dop_2027.get("mesicu_s_prekrocenim_rp"):
                upozorneni_rp.append(
                    f"Doporučená varianta počítá s RP {dop_2027['rp_novy_kw']:.0f} kW pod "
                    f"nejvyšší měsíční špičkou: v {dop_2027['mesicu_s_prekrocenim_rp']} měsíci/ích "
                    f"se platí překročení za {dop_2027['naklad_prekroceni_rp']:,.0f} Kč, protože "
                    "12× nižší kapacitní složka to převáží. RP se v NTS drží celý rok – ověř, "
                    "že překročení smlouva o připojení připouští.".replace(",", " ")
                )
    if vysledek.doporucena is not None and vysledek.doporucena.uspora_bez_investice_2026 > 0:
        upozorneni_rp.append(
            "Úspora bez investice předpokládá úpravu sjednané RK: roční RK lze snížit "
            "až po 12 měsících od poslední změny, měsíční RK se sjednává do posledního "
            "pracovního dne předchozího měsíce (body 4.18–4.21 výměru)."
        )

    popis_json = {
        "typ_reseni": "peak_shaving",
        "vstup": {
            "distributor": vstup.distributor,
            "napetova_hladina": vstup.napetova_hladina,
            "rezervovana_kapacita_kw": vstup.rezervovana_kapacita_kw,
            "cena_energie_kc_mwh": float(cena_energie),
            "rezervovany_prikon_kw": vstup.rezervovany_prikon_kw,
            "uvazovat_snizeni_rp": bool(vstup.uvazovat_snizeni_rp),
            "max_vykon_stridace_kw": vstup.max_vykon_stridace_kw,
            # Režim baterie (peak_shaving / kombinace / spot) a parametry obchodu.
            "rezim": vstup.rezim,
            "spot_referencni_rok": (
                spot_kontext.info_cen.get("rok_cen") if spot_kontext is not None else None
            ),
            "max_export_kw": vstup.max_export_kw,
            # Ruční výběr baterií (prázdné = celý katalog) – FE ho předvyplní
            # při dalším výpočtu, ať OZ nemusí klikat znovu.
            "baterie_ids": list(vstup.baterie_ids) if vstup.baterie_ids else None,
            "interval_h": interval_h,
            "poctu_intervalu": len(profil_kw),
        },
        "sazby": {
            "stara_2026_id": sazba_2026.id,
            "nova_2027_id": (sazba_2027.id if sazba_2027 is not None else None),
            "sazby_2027_k_dispozici": bool(parametry_2027),
            "sazby_2027_modelovy_odhad": je_modelovy_2027,
            # Transparentnost pokuty (PS-2): jaká sazba se použila a odkud je.
            "cena_prekroceni_kc_kw_pouzita": round(float(cena_prekroceni), 4),
            "pokuta_odvozena_z_mesicni_rk": pokuta_odvozena,
        },
    }

    # Všechny spočítané varianty pro srovnání (kap. 5) – vítěz je [0], řazeno
    # dle NPV. Ukládáme kompletní seznam, ať jde manažersky rozhodnout i mimo
    # TOP 3; graf a citlivost se ale předpočítají jen pro prvních pár variant
    # (u 84 produktů ceníku by dopočet pro všechny přidal ~15 s výpočtu).
    # Zbytku se graf dopočítá až na kliknutí – endpoint /varianta-detail.
    varianty_json = []
    for poradi, v in enumerate(vysledek.varianty):
        vj = _varianta_json(v)
        if poradi < POCET_VARIANT_S_GRAFEM:
            vj.update(
                _detail_varianty(
                    vj, profil_kw, mesice, interval_h, vstup.rezervovana_kapacita_kw
                )
            )
        varianty_json.append(vj)

    popis_json.update(
        {
            "max_navratnost_roky": max_navratnost,
            "doporucena": varianty_json[0] if varianty_json else None,
            "varianty": varianty_json,
            "upozorneni": upozorneni_profilu
            + list(vysledek.upozorneni)
            + upozorneni_sazeb
            + upozorneni_rp
            + upozorneni_spot
            + (
                list((vysledek.doporucena.ekonomika_spot or {}).get("upozorneni", []))
                if vysledek.doporucena is not None
                else []
            ),
        }
    )
    if not parametry_2027:
        popis_json["upozorneni"] = popis_json["upozorneni"] + [
            "Ekonomika roku 2027: čeká se na oficiální sazby ERÚ."
        ]

    # Zpětná kompatibilita FE: graf a citlivost doporučené varianty i na
    # nejvyšší úrovni (starší uložené výsledky je mají jen tady).
    if varianty_json:
        popis_json["graf"] = varianty_json[0]["graf"]
        popis_json["citlivost_stropu"] = varianty_json[0]["citlivost_stropu"]

    reseni = NavrhovaneReseni(
        nabidka_id=nabidka_id,
        typ_reseni="peak_shaving",
        popis_json=popis_json,
    )
    db.add(reseni)
    # výpočet proběhl → zapiš referenci na použitou verzi nastavení a posuň stav
    if aktualni_nastaveni is not None:
        n.vypoctova_nastaveni_id = aktualni_nastaveni.id
    if n.stav in ("koncept", "data_nahrana", "zkontrolovano_oz"):
        n.stav = "spocitano"
    db.commit()
    db.refresh(reseni)

    return {"reseni_id": reseni.id, "popis_json": popis_json}


@router.post("/nabidky/{nabidka_id}/peak-shaving/varianta-detail")
def dopocti_variantu(
    nabidka_id: int,
    vstup: VariantaDetailVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Dopočítá graf měsíčních maxim + citlivost pro variantu mimo TOP 3.

    Při výpočtu se předpočítají jen první `POCET_VARIANT_S_GRAFEM` varianty
    (dopočet pro celý ceník by přidal ~15 s). Když si obchodník rozklikne
    variantu z plného srovnání, dopočítá se na vyžádání a uloží do řešení,
    takže podruhé je hned k dispozici.
    """
    reseni = (
        db.query(NavrhovaneReseni)
        .filter(
            NavrhovaneReseni.nabidka_id == nabidka_id,
            NavrhovaneReseni.typ_reseni == "peak_shaving",
        )
        .order_by(NavrhovaneReseni.id.desc())
        .first()
    )
    if reseni is None:
        raise HTTPException(status_code=404, detail="Nabídka nemá spočítaný peak shaving.")

    popis = dict(reseni.popis_json or {})
    varianty = list(popis.get("varianty") or [])
    if not 0 <= vstup.index < len(varianty):
        raise HTTPException(status_code=422, detail="Varianta s tímhle pořadím ve výsledku není.")

    vj = dict(varianty[vstup.index])
    if vj.get("graf") and vj.get("citlivost_stropu"):
        return {"index": vstup.index, "graf": vj["graf"], "citlivost_stropu": vj["citlivost_stropu"]}

    # Starší uložené výsledky nemusí nést parametry potřebné pro simulaci.
    if any(vj.get(k) is None for k in ("celkovy_vykon_kw", "vyuzitelna_kapacita_kwh", "strop_kw")):
        raise HTTPException(
            status_code=422,
            detail="Tenhle výsledek je ze starší verze výpočtu – spusť „Spočítat peak shaving“ znovu.",
        )

    profil_kw, mesice, interval_h, _ = _profil_pro_peak_shaving(db, nabidka_id)
    rezervovana_kapacita_kw = float((popis.get("vstup") or {}).get("rezervovana_kapacita_kw") or 0)
    detail = _detail_varianty(vj, profil_kw, mesice, interval_h, rezervovana_kapacita_kw)

    vj.update(detail)
    varianty[vstup.index] = vj
    popis["varianty"] = varianty
    reseni.popis_json = popis  # nový objekt → SQLAlchemy uloží změnu JSONB
    db.commit()

    return {"index": vstup.index, **detail}


# ---------------- průběh v čase (nitkový graf 15min simulace) ----------------
def _useky_stropu(stropy_kw: list[float]) -> list[dict]:
    """Slepí strop po intervalech do souvislých úseků (model 2027 sráží po měsících).

    Frontend z toho kreslí schodovitou čáru stropu bez toho, aby musel dostat
    35 040 čísel navíc.
    """
    useky: list[dict] = []
    for i, s in enumerate(stropy_kw):
        if useky and abs(useky[-1]["strop_kw"] - s) < 1e-6:
            useky[-1]["do_index"] = i
        else:
            useky.append({"od_index": i, "do_index": i, "strop_kw": round(s, 2)})
    return useky


@router.get("/nabidky/{nabidka_id}/peak-shaving/prubeh")
def peak_shaving_prubeh(
    nabidka_id: int,
    varianta: int = Query(0, ge=0, description="Pořadí varianty ve výsledku (0 = doporučená)"),
    rok: int = Query(2026, description="Model 2026 (roční strop) nebo 2027 (srážení po měsících)"),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Rozepsaná 15min simulace pro nitkový graf průběhu (odběr / síť / baterie / SOC).

    Do uloženého řešení se průběh neukládá – je to ~35 tisíc hodnot na variantu
    a rok, takže by JSONB nabídky nafoukl. Počítá se na vyžádání (jedna
    simulace nad profilem ≈ desetiny sekundy) ze stejné fyziky jako ekonomika
    (`peak_shaving._krok_simulace`), aby se čísla v grafu a v tabulkách
    nemohla rozejít.

    Model se řídí přepínačem roku ve výsledku:
    - 2026 – baterie drží jeden roční strop (kap. 4.3),
    - 2027 – v každém měsíci sráží špičku, jak hluboko to jde (kap. 4.6).
    """
    reseni = (
        db.query(NavrhovaneReseni)
        .filter(
            NavrhovaneReseni.nabidka_id == nabidka_id,
            NavrhovaneReseni.typ_reseni == "peak_shaving",
        )
        .order_by(NavrhovaneReseni.id.desc())
        .first()
    )
    if reseni is None:
        raise HTTPException(status_code=404, detail="Nabídka nemá spočítaný peak shaving.")

    popis = dict(reseni.popis_json or {})
    varianty = list(popis.get("varianty") or [])
    if not 0 <= varianta < len(varianty):
        raise HTTPException(status_code=422, detail="Varianta s tímhle pořadím ve výsledku není.")
    vj = dict(varianty[varianta])
    if any(vj.get(k) is None for k in ("celkovy_vykon_kw", "vyuzitelna_kapacita_kwh", "strop_kw")):
        raise HTTPException(
            status_code=422,
            detail="Tenhle výsledek je ze starší verze výpočtu – spusť „Spočítat peak shaving“ znovu.",
        )

    casy, profil_kw, interval_h, upozorneni = _profil_pro_peak_shaving_s_casy(db, nabidka_id)
    mesice = [c.month for c in casy]
    vykon = float(vj["celkovy_vykon_kw"])
    kapacita = float(vj["vyuzitelna_kapacita_kwh"])
    ucinnost = float(vj.get("ucinnost_rt") or peak_shaving.VYCHOZI_UCINNOST_RT)

    # Strop(y), na kterých simulace jede – přesně dle modelu zvoleného roku.
    # 2027 sráží každý měsíc zvlášť (a i simulaci startuje po měsících, stejně
    # jako ekonomika), 2026 drží jeden roční strop přes celý rok.
    # V obchodních režimech (Kombinace/SPOT) jde průběh ze SPOTOVÉ simulace se
    # stropy, které rozhodovací vrstva zvolila – jinak by graf ukazoval jiné
    # chování baterie, než na jakém stojí uložená ekonomika. Přepínač roku na
    # něj nemá vliv: stropy jsou dané výsledkem, ne modelem tarifu.
    ek_spot = vj.get("ekonomika_spot") or None
    ceny_prubehu: list[float] | None = None
    if ek_spot:
        p, ceny_prubehu, upozorneni_spot = _prubeh_spot(
            db, casy, profil_kw, mesice, interval_h, vykon, kapacita, ucinnost, vj, popis
        )
        upozorneni = list(upozorneni) + upozorneni_spot
    elif rok == 2027:
        stropy_mesicu = peak_shaving.mesicni_maxima_po_baterii(
            profil_kw, mesice, vykon, kapacita, interval_h, ucinnost
        )
        p = peak_shaving.prubeh_po_mesicich(
            profil_kw, mesice, stropy_mesicu, vykon, kapacita, interval_h, ucinnost
        )
    else:
        p = peak_shaving.prubeh_baterie(
            profil_kw, float(vj["strop_kw"]), vykon, kapacita, interval_h, ucinnost
        )

    vstup = popis.get("vstup") or {}
    rk_soucasna = _num(vstup.get("rezervovana_kapacita_kw"))
    ek27 = vj.get("ekonomika_2027") or {}
    if rok == 2027:
        rk_nova = _num(ek27.get("rp_novy_kw")) if ek27.get("status") == "spocitano" else None
        rk_soucasna_ref = _num(ek27.get("rp_soucasny_kw")) or rk_soucasna
        popisek_soucasna = "rezervovaný příkon nyní"
        popisek_nova = "rezervovaný příkon po instalaci"
    else:
        rk_nova = _num(vj.get("nova_rezervovana_kapacita_kw"))
        rk_soucasna_ref = rk_soucasna
        popisek_soucasna = "sjednaná rezervace nyní"
        popisek_nova = "nová rezervovaná kapacita"

    udalosti = peak_shaving.udalosti_prubehu(
        profil_kw,
        p["site_kw"],
        p["baterie_kw"],
        p["soc_pct"],
        mesice,
        interval_h,
        rk_soucasna_kw=rk_soucasna_ref,
        rk_nova_kw=rk_nova,
    )
    for u in udalosti:
        u["cas"] = _iso(casy[u["index"]])

    zaklad = casy[0]
    ztraty_kwh = p["nabito_kwh"] * (1.0 - ucinnost)
    return {
        "varianta_index": varianta,
        "rok": rok,
        "varianta": {
            "nazev": vj.get("nazev"),
            "pocet_kusu": vj.get("pocet_kusu"),
            "celkovy_vykon_kw": vj.get("celkovy_vykon_kw"),
            "celkova_kapacita_kwh": vj.get("celkova_kapacita_kwh"),
            "vyuzitelna_kapacita_kwh": vj.get("vyuzitelna_kapacita_kwh"),
            "ucinnost_rt": round(ucinnost, 4),
        },
        # Osa X: základ + offsety v minutách (drží se i při dírách a přechodu času).
        "od": _iso(zaklad),
        "do": _iso(casy[-1]),
        "interval_min": round(interval_h * 60),
        "pocet": len(profil_kw),
        "casy_min": [int(round((c - zaklad).total_seconds() / 60)) for c in casy],
        "odber_kw": [round(x, 2) for x in profil_kw],
        "site_kw": [round(x, 2) for x in p["site_kw"]],
        "baterie_kw": [round(x, 2) for x in p["baterie_kw"]],
        "soc_pct": [round(x, 1) for x in p["soc_pct"]],
        "useky_stropu": _useky_stropu(p["stropy_kw"]),
        # Obchodní režimy: cena, podle které se baterie rozhodovala, a rozpad
        # výkonu na srážení špičky vs. obchod. U čistého peak shavingu None,
        # takže FE ty pásy prostě nevykreslí.
        "cena_kc_mwh": ([round(x, 1) for x in ceny_prubehu] if ceny_prubehu else None),
        "baterie_ps_kw": (
            [round(x, 2) for x in p["baterie_ps_kw"]] if "baterie_ps_kw" in p else None
        ),
        "baterie_obchod_kw": (
            [round(x, 2) for x in p["baterie_obchod_kw"]] if "baterie_obchod_kw" in p else None
        ),
        "rezim": vj.get("rezim") or "peak_shaving",
        "referencni": {
            "rk_soucasna_kw": round(rk_soucasna_ref, 2) if rk_soucasna_ref else None,
            "rk_nova_kw": round(rk_nova, 2) if rk_nova else None,
            "popisek_soucasna": popisek_soucasna,
            "popisek_nova": popisek_nova,
        },
        "souhrn": {
            "nabito_kwh": round(p["nabito_kwh"], 1),
            "vybito_kwh": round(p["vybito_kwh"], 1),
            "ztraty_kwh": round(ztraty_kwh, 1),
            "max_odber_kw": round(max(profil_kw), 2) if profil_kw else None,
            "max_site_kw": round(max(p["site_kw"]), 2) if p["site_kw"] else None,
        },
        "udalosti": udalosti,
        "upozorneni": upozorneni,
    }


# ================= PPA pro FVE – výpočet (METODIKA-ppa-fve.md kap. 4–5) =================
def _profil_spotreby_kwh(db: Session, nabidka_id: int) -> tuple[list, list[float], float]:
    """Načte 15min profil nabídky a vrátí (časy, spotřeba_kwh, interval_h).

    Profil je uložený jako činný výkon (kW) ve `spotreba_profil.hodnota_kw`
    (společné s peak shavingem). PPA počítá s energií, proto se každý interval
    přepočte na kWh = kW × interval_h (METODIKA kap. 2/3.4, otevřený bod 11).
    """
    radky = (
        db.query(SpotrebaProfil)
        .filter(
            SpotrebaProfil.nabidka_id == nabidka_id,
            SpotrebaProfil.hodnota_kw.isnot(None),
        )
        .order_by(SpotrebaProfil.cas)
        .all()
    )
    casy = [r.cas for r in radky]
    interval_h = _interval_h_z_profilu(casy)
    spotreba_kwh = [float(r.hodnota_kw) * interval_h for r in radky]
    return casy, spotreba_kwh, interval_h


def _ppa_param(nastaveni, klic: str, default: float) -> float:
    """Přečte PPA parametr z manažerského nastavení (JSONB `parametry`) s fallbackem."""
    if nastaveni is not None and nastaveni.parametry:
        hodnota = nastaveni.parametry.get(klic)
        if hodnota is not None:
            try:
                return float(hodnota)
            except (TypeError, ValueError):
                pass
    return default


# Pozn.: varianty velikostí se do popis_json ukládají KOMPLETNÍ (vč. roků
# a grafu), aby FE uměl překreslit detail po kliknutí na řádek srovnání.
# Starší uložené výsledky mají jen kompaktní souhrn – FE to rozlišuje podle
# přítomnosti pole `roky`.


@router.get("/nabidky/{nabidka_id}/ppa/profil-souhrn")
def ppa_profil_souhrn(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Souhrn profilu spotřeby pro PPA (počet, rozsah, roční spotřeba v MWh)."""
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        return {"pocet": 0}
    return {
        "pocet": len(casy),
        "od": _iso(min(casy)),
        "do": _iso(max(casy)),
        "interval_h": interval_h,
        "rocni_spotreba_mwh": round(sum(spotreba_kwh) / 1000.0, 2),
    }


@router.get("/nabidky/{nabidka_id}/ppa/prubeh")
def ppa_prubeh(
    nabidka_id: int,
    varianta: str = Query("bez_baterie", pattern="^(bez_baterie|s_baterii)$"),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """15min průběh výroby a spotřeby pro nitkový graf (obdoba peak shavingu).

    Do uloženého řešení se průběh neukládá – je to ~35 tisíc hodnot na variantu,
    což by JSONB nabídky nafouklo. Počítá se na vyžádání ze **stejné fyziky jako
    ekonomika** (`ppa_v2.toky_energie`), aby se graf a tabulky nemohly rozejít.
    """
    reseni = (
        db.query(NavrhovaneReseni)
        .filter(
            NavrhovaneReseni.nabidka_id == nabidka_id,
            NavrhovaneReseni.typ_reseni == "ppa",
        )
        .order_by(NavrhovaneReseni.id.desc())
        .first()
    )
    if reseni is None:
        raise HTTPException(status_code=404, detail="Nabídka nemá spočítané PPA.")
    popis = dict(reseni.popis_json or {})
    if popis.get("verze") != 2:
        raise HTTPException(
            status_code=422,
            detail="Uložený výpočet je ze starší verze – spusť „Spočítat PPA“ znovu.",
        )
    blok = popis.get(varianta)
    if not blok:
        raise HTTPException(status_code=422, detail="Tuhle variantu výsledek neobsahuje.")

    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        raise HTTPException(status_code=422, detail="Nabídka nemá nahraný profil spotřeby.")
    casy, spotreba_kwh, _ = _zvaliduj_a_orizni_profil(casy, spotreba_kwh, interval_h)

    vst = popis.get("vstup") or {}
    kwp = float(blok.get("kwp") or 0.0)
    if kwp <= 0:
        raise HTTPException(status_code=422, detail="Výsledek neobsahuje velikost FVE.")

    vyroba = ppa_v2.simuluj_vyrobu(
        casy,
        kwp,
        float(vst.get("lat_deg") or ppa_v2.VYCHOZI_LAT),
        float(vst.get("sklon_st") or 35.0),
        float(vst.get("azimut_st") or 0.0),
        float(vst.get("merny_vynos_kwh_kwp") or ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP),
    )

    # Baterie: parametry z uložené varianty (kapacita/výkon), ať průběh odpovídá
    # tomu, na čem stojí uložená ekonomika.
    baterie = None
    prvni = (blok.get("po_delkach") or [{}])[0]
    bat = prvni.get("baterie")
    if varianta == "s_baterii" and bat and bat.get("kapacita_kwh"):
        # `dod` a účinnost z uložené varianty (u katalogové baterie se liší od
        # defaultů) – jinak by graf pracoval s jinak velkou baterií než ekonomika.
        # Starší uložené výpočty je nemají → spadne se na defaulty jako dřív.
        baterie = ppa_v2.Baterie(
            kapacita_kwh=float(bat["kapacita_kwh"]),
            vykon_kw=float(bat.get("vykon_kw") or 0.0),
            ucinnost_round_trip=float(
                bat.get("ucinnost_round_trip") or ppa_v2.VYCHOZI_UCINNOST_ROUND_TRIP
            ),
            dod=float(bat.get("dod") or ppa_v2.VYCHOZI_DOD),
            produkt_id=bat.get("produkt_id"),
            produkt_nazev=bat.get("nazev"),
            pocet_kusu=int(bat.get("pocet_kusu") or 1),
        )

    rez = vst.get("rezervovany_vykon_dodavky_kw")
    p = ppa_v2.prubeh_15min(
        vyroba, spotreba_kwh, baterie, float(rez) if rez else None, interval_h
    )

    zaklad = min(casy)
    return {
        "varianta": varianta,
        "kwp": kwp,
        "od": _iso(zaklad),
        "do": _iso(max(casy)),
        "interval_min": round(interval_h * 60),
        "pocet": len(casy),
        "casy_min": [int(round((c - zaklad).total_seconds() / 60)) for c in casy],
        **p,
        "baterie": (
            {
                "kapacita_kwh": baterie.kapacita_kwh,
                "vykon_kw": baterie.vykon_kw,
                "nazev": baterie.produkt_nazev,
                "pocet_kusu": baterie.pocet_kusu,
            }
            if baterie
            else None
        ),
        "referencni": {
            "rezervovany_vykon_dodavky_kw": float(rez) if rez else None,
        },
    }


@router.post("/nabidky/{nabidka_id}/ppa/vypocet")
def spocti_ppa(
    nabidka_id: int,
    vstup: PpaVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Spustí PPA výpočet (v2) a uloží výsledek do `navrhovana_reseni` (typ_reseni = ppa).

    Postup dle `docs/METODIKA-ppa-v2.md` kap. 3:
    1. načte 15min profil spotřeby (kW → kWh) z `spotreba_profil`,
    2. navrhne velikost FVE z cíle samospotřeby (a případného stropu),
    3. pro každou nabízenou délku kontraktu dopočítá **nejnižší cenu PPA**,
       která projde bankou (DSCR) i investorem (cílové IRR),
    4. uloží výsledek vč. tabulky po letech a odkupní tabulky.

    Cenu PPA ani délku kontraktu OZ nezadává – to je proti v1 obrácené.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if vstup.cena_silova_kc_mwh <= 0:
        raise HTTPException(
            status_code=422,
            detail="Zadej silovou složku ceny, kterou zákazník platí dnes (Kč/MWh).",
        )
    if vstup.max_kwp is not None and vstup.max_kwp <= 0:
        raise HTTPException(status_code=422, detail="Strop velikosti FVE (kWp) musí být kladný.")

    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nabídka nemá nahraný 15min profil spotřeby. Nahraj a načti profil "
                "(sekce Podklady), bez něj nejde PPA počítat."
            ),
        )

    # Validace pokrytí roku + případné oříznutí na posledních 12 měsíců (SP-1) –
    # bez ní by se půlroční data prohlásila za „roční spotřebu“ (bughunt T2/T3).
    casy, spotreba_kwh, upozorneni = _zvaliduj_a_orizni_profil(casy, spotreba_kwh, interval_h)

    # ---- manažerské nastavení → ekonomické parametry (METODIKA kap. 4)
    nastaveni = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    parametry = ppa_v2.parametry_z_nastaveni(
        nastaveni.parametry if nastaveni is not None else None
    )
    merny_vynos = _ppa_param(
        nastaveni, "ppa_merny_vynos_kwh_kwp", ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP
    )
    if merny_vynos <= 0:
        upozorneni.append(
            f"Měrný výnos v nastavení je {merny_vynos:g} kWh/kWp – "
            f"použita výchozí hodnota {ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP:g}."
        )
        merny_vynos = ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP

    cil = vstup.cil_mira_samospotreby
    if cil is None:
        cil = _ppa_param(nastaveni, "ppa_cil_mira_samospotreby", ppa_v2.VYCHOZI_CIL_MIRA_SAMOSPOTREBY)
    if not (0 < cil <= 1):
        raise HTTPException(
            status_code=422, detail="Cíl samospotřeby musí být v rozmezí 0–100 %."
        )
    regulovane = vstup.vyhnutelne_regulovane_kc_mwh
    if regulovane is None:
        regulovane = _ppa_param(
            nastaveni, "ppa_vyhnutelne_regulovane_kc_mwh", ppa_v2.VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH
        )
    min_sleva = _ppa_param(nastaveni, "ppa_min_sleva", ppa_v2.VYCHOZI_MIN_SLEVA)

    # Lokalita – GPS zákazníka, jinak střed ČR.
    lat = ppa_v2.VYCHOZI_LAT
    if n.zakaznik_gps_lat is not None:
        lat = float(n.zakaznik_gps_lat)
    else:
        upozorneni.append(
            f"Nabídka nemá GPS – použita výchozí šířka {ppa_v2.VYCHOZI_LAT}° (střed ČR). "
            "Doplň GPS zákazníka pro přesnější simulaci výroby."
        )

    # Baterie: buď zadaná ručně, nebo (kapacita = None) se navrhne velikost
    # z přebytku FVE a na ni se vybere konkrétní produkt z katalogu baterií –
    # tentýž katalog, ze kterého čerpá peak shaving. Katalogová cena je nákladová
    # cena BESS, takže varianta pak má i CAPEX a její čísla jsou platná.
    baterie_katalog: tuple[ppa_v2.ProduktBaterie, ...] = ()
    if vstup.s_baterii and not vstup.baterie_kapacita_kwh:
        baterie_katalog = _produkty_baterie_ppa(db)

    baterie = None
    if vstup.s_baterii and vstup.baterie_kapacita_kwh:
        kap = float(vstup.baterie_kapacita_kwh)
        vyk = float(vstup.baterie_vykon_kw) if vstup.baterie_vykon_kw else kap * ppa_v2.VYCHOZI_C_RATE
        baterie = ppa_v2.Baterie(
            kapacita_kwh=kap,
            vykon_kw=vyk,
            nakladova_cena_kc=float(vstup.baterie_nakladova_cena_kc or 0.0),
        )
        if not vstup.baterie_nakladova_cena_kc:
            upozorneni.append(
                "Nákladová cena baterie není zadaná – varianta s baterií počítá jen "
                "s pronájmem bez CAPEX baterie, čísla nejsou platná."
            )

    delky = vstup.nabizene_delky_roky or list(ppa_v2.VYCHOZI_NABIZENE_DELKY_ROKY)
    delky = sorted({int(d) for d in delky if int(d) > 0})
    if not delky:
        raise HTTPException(status_code=422, detail="Zadej aspoň jednu délku kontraktu.")

    vstup_calc = ppa_v2.VstupPPA2(
        casy=casy,
        spotreba_kwh=spotreba_kwh,
        cena_silova_kc_mwh=float(vstup.cena_silova_kc_mwh),
        hladina=vstup.hladina,
        cil_mira_samospotreby=float(cil),
        vyhnutelne_regulovane_kc_mwh=float(regulovane),
        cena_exportu_kc_mwh=(
            float(vstup.cena_exportu_kc_mwh) if vstup.cena_exportu_kc_mwh is not None else None
        ),
        s_baterii=bool(vstup.s_baterii),
        baterie=baterie,
        baterie_katalog=baterie_katalog,
        lat_deg=lat,
        sklon_st=float(vstup.sklon_st),
        azimut_st=float(vstup.azimut_st),
        merny_vynos_kwh_kwp=float(merny_vynos),
        max_kwp=float(vstup.max_kwp) if vstup.max_kwp else None,
        rezervovany_vykon_dodavky_kw=(
            float(vstup.rezervovany_vykon_dodavky_kw) if vstup.rezervovany_vykon_dodavky_kw else None
        ),
        nabizene_delky_roky=tuple(delky),
        min_sleva=float(min_sleva),
        interval_h=interval_h,
        parametry=parametry,
    )

    try:
        vysledek = ppa_v2.spocti_ppa2(vstup_calc)
    except ppa_v2.NepodporovanaHladina as e:
        raise HTTPException(status_code=422, detail=str(e))
    if vysledek.get("chyba"):
        raise HTTPException(status_code=422, detail=vysledek["chyba"])
    if not vysledek.get("bez_baterie") and not vysledek.get("s_baterii"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Pro zadané hodnoty nelze elektrárnu navrhnout – zkontroluj profil "
                "spotřeby, cíl samospotřeby a strop velikosti."
            ),
        )

    # Daň z elektřiny nad 30 kW (informativně, stejně jako u v1).
    hlavni = vysledek.get("bez_baterie") or vysledek.get("s_baterii")
    if (hlavni or {}).get("kwp", 0) > 30:
        upozorneni.append(
            "Výrobna nad 30 kW: dodávka z PPA podléhá dani z elektřiny (28,30 Kč/MWh) stejně "
            "jako dnešní dodávka – v úspoře se proto daň nesrovnává (symetrická). Investor "
            "(Greensie) má registrační povinnost u celní správy."
        )
    upozorneni.append(
        "Výnos investora je úměrný skutečné samospotřebě klienta – pokles spotřeby během "
        "kontraktu výnos snižuje (reálné smlouvy to řeší minimálním odběrem / take-or-pay)."
    )
    # Upozornění z výpočtu (cena za export, strop, baterie…) se přidají za ta z profilu.
    upozorneni.extend(vysledek.get("upozorneni") or [])

    popis_json = {
        "typ_reseni": "ppa",
        # Verze tvaru výsledku. FE podle ní pozná starší (v1) uložené výpočty,
        # které mají úplně jiná pole, a nabídne přepočet místo rozbité tabulky.
        "verze": 2,
        "vstup": {
            **(vysledek.get("vstup") or {}),
            "poctu_intervalu": len(casy),
            "s_baterii": bool(vstup.s_baterii),
        },
        "bez_baterie": vysledek.get("bez_baterie"),
        "s_baterii": vysledek.get("s_baterii"),
        "upozorneni": upozorneni,
    }

    reseni = NavrhovaneReseni(nabidka_id=nabidka_id, typ_reseni="ppa", popis_json=popis_json)
    db.add(reseni)
    if nastaveni is not None:
        n.vypoctova_nastaveni_id = nastaveni.id
    if n.stav in ("koncept", "data_nahrana", "zkontrolovano_oz"):
        n.stav = "spocitano"
    db.commit()
    db.refresh(reseni)
    return {"reseni_id": reseni.id, "popis_json": popis_json}


# ============================== PPA + BESS ==============================
@router.get("/nabidky/{nabidka_id}/ppa-bess/profil-souhrn")
def ppa_bess_profil_souhrn(
    nabidka_id: int,
    user: User = Depends(vyzaduj_ppa_bess),
    db: Session = Depends(get_db),
):
    """Souhrn nahraného profilu.

    Stejný tvar jako u PPA, tedy **včetně roční spotřeby v MWh** – panel ji
    zobrazuje. Souhrn z peak shavingu (`_profil_souhrn`) ji nemá a v UI by se
    místo čísla objevilo „None MWh".
    """
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        return {"pocet": 0}
    return {
        "pocet": len(casy),
        "od": _iso(min(casy)),
        "do": _iso(max(casy)),
        "interval_h": interval_h,
        "rocni_spotreba_mwh": round(sum(spotreba_kwh) / 1000.0, 2),
        "max_kw": round(max(spotreba_kwh) / interval_h, 2) if interval_h > 0 else None,
    }


@router.get("/nabidky/{nabidka_id}/ppa-bess/prubeh")
def ppa_bess_prubeh(
    nabidka_id: int,
    rezim: str = Query("kombinace"),
    user: User = Depends(vyzaduj_ppa_bess),
    db: Session = Depends(get_db),
):
    """15min průběh pro nitkový graf – dopočítá se z uloženého řešení.

    Do `popis_json` se neukládá (~35 tis. hodnot na řadu). Stropy se berou
    z uloženého výsledku, takže graf ukazuje **tentýž** dispatch, ze kterého
    vyšla ekonomika – ne nový, spočítaný jinak.
    """
    if rezim not in ppa_bess.REZIMY:
        raise HTTPException(status_code=422, detail=f"Neznámý režim baterie: {rezim}")
    reseni = _posledni_reseni(db, nabidka_id, "ppa_bess")
    if reseni is None:
        raise HTTPException(status_code=422, detail="Nabídka ještě není spočítaná.")
    popis = reseni.popis_json or {}
    blok = next((r for r in (popis.get("rezimy") or []) if r.get("rezim") == rezim), None)
    if blok is None:
        raise HTTPException(status_code=422, detail="Uložený výpočet tenhle režim neobsahuje.")

    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        raise HTTPException(status_code=422, detail="Nabídka nemá nahraný profil spotřeby.")
    casy, spotreba_kwh, _ = _zvaliduj_a_orizni_profil(casy, spotreba_kwh, interval_h)

    n = db.get(Nabidka, nabidka_id)
    vstup_ulozeny = popis.get("vstup") or {}
    kwp = float((popis.get("elektrarna") or {}).get("kwp") or 0.0)
    lat = float(n.zakaznik_gps_lat) if (n and n.zakaznik_gps_lat is not None) else ppa_v2.VYCHOZI_LAT
    nastaveni = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    merny_vynos = _ppa_param(
        nastaveni, "ppa_merny_vynos_kwh_kwp", ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP
    )
    vynos = merny_vynos if merny_vynos > 0 else ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP
    # Výroba se musí skládat stejně jako při výpočtu, jinak by graf ukazoval jiný
    # tvar než ekonomika: u ručně zadaných polí se sčítá po polích, u navržené
    # velikosti jde o jednu orientaci.
    ulozena_pole = (popis.get("elektrarna") or {}).get("pole") or []
    if ulozena_pole:
        vyroba_kwh = [0.0] * len(casy)
        for f in ulozena_pole:
            dil = ppa_v2.simuluj_vyrobu(
                casy,
                float(f.get("kwp") or 0.0),
                lat,
                float(f.get("sklon_st") or 35.0),
                float(f.get("azimut_st") or 0.0),
                vynos,
            )
            for i, x in enumerate(dil):
                vyroba_kwh[i] += x
    else:
        vyroba_kwh = [
            kwp * x
            for x in ppa_v2.simuluj_vyrobu(
                casy,
                1.0,
                lat,
                float(vstup_ulozeny.get("sklon_st") or 35.0),
                float(vstup_ulozeny.get("azimut_st") or 0.0),
                vynos,
            )
        ]

    bat_json = popis.get("baterie") or None
    baterie = None
    if bat_json:
        baterie = ppa_v2.Baterie(
            kapacita_kwh=float(bat_json.get("kapacita_kwh") or 0.0),
            vykon_kw=float(bat_json.get("vykon_kw") or 0.0),
            ucinnost_round_trip=float(
                bat_json.get("ucinnost_round_trip") or ppa_v2.VYCHOZI_UCINNOST_ROUND_TRIP
            ),
            dod=float(bat_json.get("dod") or ppa_v2.VYCHOZI_DOD),
        )
    stropy = {int(m["mesic"]): float(m["strop_kw"]) for m in (blok.get("mesice") or [])}

    prubeh = ppa_bess.prubeh_15min(
        spotreba_kwh,
        vyroba_kwh,
        [c.month for c in casy],
        baterie,
        stropy,
        interval_h,
        rezervovany_vykon_dodavky_kw=vstup_ulozeny.get("rezervovany_vykon_dodavky_kw"),
        rezim=rezim,
    )
    prubeh["od"] = _iso(casy[0]) if casy else None
    prubeh["casy_min"] = [
        int(round((c - casy[0]).total_seconds() / 60.0)) for c in casy
    ]
    prubeh["rezim"] = rezim
    prubeh["referencni"] = {
        "rezervovany_prikon_kw": vstup_ulozeny.get("rezervovany_prikon_kw")
        or vstup_ulozeny.get("rezervovana_kapacita_kw"),
    }
    return prubeh


def sestav_vstup_ppa_bess(db: Session, nabidka_id: int, vstup: PpaBessVstup):
    """Z požadavku panelu složí vstup výpočtu PPA + BESS.

    Vytažené z endpointu schválně: **stejnou funkci volá i worker na pozadí**
    (`app/nabidkovac/vypocet_worker.py`). Kdyby si worker vstup skládal sám,
    počítal by po změně manažerského nastavení nebo sazebníku s jinými čísly než
    appka — a nikdo by si toho nevšiml, protože obojí by „vyšlo".

    Vrací `(vstup_calc, upozorneni, nastaveni, sazba_2027)`. Validační chyby
    hlásí jako `HTTPException`, takže se z endpointu i z workeru chovají stejně.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if vstup.cena_silova_kc_mwh <= 0:
        raise HTTPException(
            status_code=422,
            detail="Zadej silovou složku ceny, kterou zákazník platí dnes (Kč/MWh).",
        )
    if vstup.rezervovana_kapacita_kw <= 0:
        raise HTTPException(
            status_code=422,
            detail="Zadej rezervovanou kapacitu (kW) – bez ní se nedá ocenit srážení špiček.",
        )
    if vstup.max_kwp is not None and vstup.max_kwp <= 0:
        raise HTTPException(
            status_code=422, detail="Strop velikosti elektrárny (kWp) musí být kladný."
        )
    if vstup.napetova_hladina not in ("vn", "vvn"):
        raise HTTPException(
            status_code=422,
            detail=(
                "PPA + BESS zatím počítáme jen na VN a VVN – na NN není nakalibrovaná "
                "ani výroba, ani tarifní struktura."
            ),
        )

    casy, spotreba_kwh, interval_h = _profil_spotreby_kwh(db, nabidka_id)
    if not casy:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nabídka nemá nahraný 15min profil spotřeby. Nahraj a načti profil "
                "(sekce Podklady), bez něj nejde PPA + BESS počítat."
            ),
        )
    casy, spotreba_kwh, upozorneni = _zvaliduj_a_orizni_profil(casy, spotreba_kwh, interval_h)

    # ---- manažerské nastavení
    nastaveni = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    parametry_json = nastaveni.parametry if nastaveni is not None else None
    parametry = ppa_v2.parametry_z_nastaveni(parametry_json)
    parametry_bess = ppa_bess.parametry_z_nastaveni(parametry_json)

    merny_vynos = _ppa_param(
        nastaveni, "ppa_merny_vynos_kwh_kwp", ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP
    )
    if merny_vynos <= 0:
        merny_vynos = ppa_v2.VYCHOZI_MERNY_VYNOS_KWH_KWP

    cil = vstup.cil_mira_samospotreby
    if cil is None:
        cil = _ppa_param(
            nastaveni, "ppa_cil_mira_samospotreby", ppa_v2.VYCHOZI_CIL_MIRA_SAMOSPOTREBY
        )
    if not (0 < cil <= 1):
        raise HTTPException(status_code=422, detail="Cíl samospotřeby musí být v rozmezí 0–100 %.")

    regulovane = vstup.vyhnutelne_regulovane_kc_mwh
    if regulovane is None:
        regulovane = _ppa_param(
            nastaveni,
            "ppa_vyhnutelne_regulovane_kc_mwh",
            ppa_v2.VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH,
        )
    rezerva_rk = _ppa_param(
        nastaveni, "ps_rezerva_rk_procenta", peak_shaving.VYCHOZI_REZERVA_RK_PROCENTA
    )

    # ---- sazby NTS 2027 (jen vn/vvn, stejně jako u peak shavingu)
    sazba_2027 = _najdi_sazbu(db, vstup.distributor, vstup.napetova_hladina, "nova_2027", 2027)
    parametry_2027 = dict(sazba_2027.parametry or {}) if sazba_2027 is not None else None
    je_modelovy_2027 = bool(sazba_2027.je_modelovy_odhad) if sazba_2027 is not None else True

    # ---- lokalita
    lat = ppa_v2.VYCHOZI_LAT
    if n.zakaznik_gps_lat is not None:
        lat = float(n.zakaznik_gps_lat)
    else:
        upozorneni.append(
            f"Nabídka nemá GPS – použita výchozí šířka {ppa_v2.VYCHOZI_LAT}° (střed ČR). "
            "Doplň GPS zákazníka pro přesnější simulaci výroby."
        )

    # ---- baterie: ruční zadání má přednost před katalogem
    baterie = None
    baterie_katalog: tuple[ppa_v2.ProduktBaterie, ...] = ()
    if vstup.baterie_kapacita_kwh and vstup.baterie_vykon_kw:
        if vstup.baterie_kapacita_kwh <= 0 or vstup.baterie_vykon_kw <= 0:
            raise HTTPException(
                status_code=422, detail="Kapacita i výkon baterie musí být kladné."
            )
        baterie = ppa_v2.Baterie(
            kapacita_kwh=float(vstup.baterie_kapacita_kwh),
            vykon_kw=float(vstup.baterie_vykon_kw),
            ucinnost_round_trip=(
                peak_shaving.normalizuj_ucinnost_rt(vstup.baterie_ucinnost_rt)
                if vstup.baterie_ucinnost_rt is not None
                else ppa_v2.VYCHOZI_UCINNOST_ROUND_TRIP
            ),
            dod=(
                float(vstup.baterie_vyuzitelny_podil)
                if vstup.baterie_vyuzitelny_podil
                else ppa_v2.VYCHOZI_DOD
            ),
            nakladova_cena_kc=float(vstup.baterie_nakladova_cena_kc or 0.0),
        )
    elif vstup.baterie_kapacita_kwh or vstup.baterie_vykon_kw:
        raise HTTPException(
            status_code=422,
            detail=(
                "U ruční baterie zadej kapacitu i výkon – jen jedno z toho k simulaci "
                "nestačí."
            ),
        )
    else:
        baterie_katalog = _produkty_baterie_ppa(db, vstup.baterie_ids)

    vstup_calc = ppa_bess.VstupPpaBess(
        casy=casy,
        spotreba_kwh=spotreba_kwh,
        cena_silova_kc_mwh=float(vstup.cena_silova_kc_mwh),
        rezervovana_kapacita_kw=float(vstup.rezervovana_kapacita_kw),
        rezervovany_prikon_kw=(
            float(vstup.rezervovany_prikon_kw) if vstup.rezervovany_prikon_kw else None
        ),
        hladina="VVN" if vstup.napetova_hladina == "vvn" else "VN",
        parametry_2027=parametry_2027,
        je_modelovy_odhad_2027=je_modelovy_2027,
        vyhnutelne_regulovane_kc_mwh=float(regulovane),
        cil_mira_samospotreby=float(cil),
        cena_exportu_kc_mwh=vstup.cena_exportu_kc_mwh,
        max_kwp=vstup.max_kwp,
        rezervovany_vykon_dodavky_kw=vstup.rezervovany_vykon_dodavky_kw,
        lat_deg=lat,
        sklon_st=vstup.sklon_st,
        azimut_st=vstup.azimut_st,
        pole=tuple(
            ppa_bess.PoleFve(
                kwp=float(f.kwp), sklon_st=float(f.sklon_st), azimut_st=float(f.azimut_st)
            )
            for f in (vstup.pole or ())
            if f.kwp and float(f.kwp) > 0
        ),
        merny_vynos_kwh_kwp=merny_vynos,
        baterie=baterie,
        baterie_katalog=baterie_katalog,
        najem_kc_mesic_rucne=(
            float(vstup.baterie_najem_kc_mesic)
            if vstup.baterie_najem_kc_mesic is not None
            else None
        ),
        nabizene_delky_roky=tuple(
            vstup.nabizene_delky_roky or ppa_v2.VYCHOZI_NABIZENE_DELKY_ROKY
        ),
        rezerva_rk_procenta=rezerva_rk,
        interval_h=interval_h,
        parametry=parametry,
        parametry_bess=parametry_bess,
    )
    return vstup_calc, upozorneni, nastaveni, sazba_2027


@router.post("/nabidky/{nabidka_id}/ppa-bess/vypocet")
def spocti_ppa_bess(
    nabidka_id: int,
    vstup: PpaBessVstup,
    user: User = Depends(vyzaduj_ppa_bess),
    db: Session = Depends(get_db),
):
    """Spustí výpočet PPA + BESS a uloží výsledek (typ_reseni = ppa_bess).

    Proti PPA v2 přidává ocenění kilowattů, takže potřebuje sazby NTS 2027
    ze sazebníku. Když pro danou hladinu a distributora nejsou, výpočet
    proběhne, ale přínos na výkonu chybí a je to v upozorněních – místo aby
    se tipovalo.

    **Synchronní cesta**: počítá se jedna baterie (ruční zadání, nebo návrh
    z katalogu heuristikou) ve třech režimech, tedy sekundy. Prohledání celého
    katalogu jde do fronty (`/ppa-bess/katalog`), protože 168 konfigurací nad
    ročním diagramem trvá skoro dvě minuty a to by web proces neunesl.
    """
    vstup_calc, upozorneni, nastaveni, sazba_2027 = sestav_vstup_ppa_bess(
        db, nabidka_id, vstup
    )
    n = db.get(Nabidka, nabidka_id)

    vysledek = ppa_bess.spocti_ppa_bess(vstup_calc)
    if vysledek.get("chyba"):
        raise HTTPException(status_code=422, detail=vysledek["chyba"])

    upozorneni.extend(vysledek.get("upozorneni") or [])
    popis_json = {**vysledek, "upozorneni": upozorneni}
    popis_json["vstup"] = {
        **(vysledek.get("vstup") or {}),
        "distributor": vstup.distributor,
        "napetova_hladina": vstup.napetova_hladina,
        "sazba_2027_id": sazba_2027.id if sazba_2027 is not None else None,
    }

    reseni = NavrhovaneReseni(
        nabidka_id=nabidka_id, typ_reseni="ppa_bess", popis_json=popis_json
    )
    db.add(reseni)
    if nastaveni is not None:
        n.vypoctova_nastaveni_id = nastaveni.id
    if n.stav in ("koncept", "data_nahrana", "zkontrolovano_oz"):
        n.stav = "spocitano"
    db.commit()
    db.refresh(reseni)
    return {"reseni_id": reseni.id, "popis_json": popis_json}


@router.post("/nabidky/{nabidka_id}/ppa-bess/katalog")
def zarad_ppa_bess_katalog(
    nabidka_id: int,
    vstup: PpaBessVstup,
    user: User = Depends(vyzaduj_ppa_bess),
    db: Session = Depends(get_db),
):
    """Zařadí prohledání celého katalogu baterií do fronty na pozadí.

    Vrací se hned, výpočet odbaví `greensie-vypocty`. Vstup se **zvaliduje už
    tady** (přes `sestav_vstup_ppa_bess`), aby se chyba v zadání ohlásila
    okamžitě a ne až za dvě minuty jako spadlá úloha.

    Když už pro nabídku úloha čeká nebo běží, druhá se nezařadí — vrátí se ta
    stávající. Jinak by dvě kliknutí spustila dva stejné výpočty a soutěžila
    o tatáž jádra.
    """
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    # Validace vstupu (a tím i profilu, sazeb a nastavení) na místě.
    sestav_vstup_ppa_bess(db, nabidka_id, vstup)

    bezici = (
        db.query(VypocetFronta)
        .filter(
            VypocetFronta.nabidka_id == nabidka_id,
            VypocetFronta.typ == "ppa_bess_katalog",
            VypocetFronta.stav.in_(("ceka", "bezi")),
        )
        .order_by(VypocetFronta.id.desc())
        .first()
    )
    if bezici is not None:
        return _uloha_out(bezici, jiz_bezela=True)

    uloha = VypocetFronta(
        nabidka_id=nabidka_id,
        typ="ppa_bess_katalog",
        vstup_json=vstup.model_dump(mode="json"),
        stav="ceka",
        zprava="Ve frontě",
        zadal_user_id=user.id,
    )
    db.add(uloha)
    db.commit()
    db.refresh(uloha)
    return _uloha_out(uloha)


@router.get("/nabidky/{nabidka_id}/ppa-bess/katalog/stav")
def stav_ppa_bess_katalog(
    nabidka_id: int,
    user: User = Depends(vyzaduj_ppa_bess),
    db: Session = Depends(get_db),
):
    """Stav poslední úlohy prohledání katalogu (panel se na to ptá v intervalu).

    Vrací i `sluzba_bezi`: když worker neběží, úloha zůstane ve stavu „čeká"
    navěky a panel to musí říct, ne točit kolečko donekonečna.
    """
    uloha = (
        db.query(VypocetFronta)
        .filter(
            VypocetFronta.nabidka_id == nabidka_id,
            VypocetFronta.typ == "ppa_bess_katalog",
        )
        .order_by(VypocetFronta.id.desc())
        .first()
    )
    if uloha is None:
        return {"uloha": None, "sluzba_bezi": _vypocty_sluzba_bezi()}
    return {"uloha": _uloha_out(uloha), "sluzba_bezi": _vypocty_sluzba_bezi()}


def _uloha_out(u: VypocetFronta, jiz_bezela: bool = False) -> dict:
    """Úloha z fronty pro UI."""
    return {
        "id": u.id,
        "stav": u.stav,
        "zprava": u.zprava or "",
        "hotovo_variant": u.hotovo_variant,
        "celkem_variant": u.celkem_variant,
        "reseni_id": u.reseni_id,
        "chyba": u.chyba,
        "pokusu": u.pokusu,
        "vytvoreno_at": _iso(u.vytvoreno_at),
        "zahajeno_at": _iso(u.zahajeno_at),
        "dokonceno_at": _iso(u.dokonceno_at),
        "prohledano_konfiguraci": (u.vysledek_json or {}).get("prohledano_konfiguraci"),
        "jiz_bezela": jiz_bezela,
    }


def _vypocty_sluzba_bezi() -> bool:
    """Běží služba `greensie-vypocty`?

    Bez ní se zařazené úlohy nikdy neodbaví. Panel to musí ukázat, jinak by
    obchodník čekal na výsledek, který nikdy nepřijde. Když se stav zjistit
    nedá (jiný systém, chybějící systemctl), hlásí se `True` – radši nechat
    ukazatel běžet než tvrdit, že služba neběží, když o tom nic nevíme.
    """
    import shutil
    import subprocess

    if shutil.which("systemctl") is None:
        return True
    try:
        hotovo = subprocess.run(
            ["systemctl", "is-active", "greensie-vypocty"],
            capture_output=True, text=True, timeout=3,
        )
        return hotovo.stdout.strip() == "active"
    except Exception:
        return True


# ================= Nabídková šablona / výstup (PDF pro zákazníka) =================
def _posledni_reseni(db: Session, nabidka_id: int, typ_reseni: str) -> NavrhovaneReseni | None:
    """Nejnovější spočítané řešení daného typu (podle něj se plní hodnoty)."""
    return (
        db.query(NavrhovaneReseni)
        .filter(
            NavrhovaneReseni.nabidka_id == nabidka_id,
            NavrhovaneReseni.typ_reseni == typ_reseni,
        )
        .order_by(NavrhovaneReseni.id.desc())
        .first()
    )


def _vystup_out(db: Session, n: Nabidka, typ_reseni: str, vychozi: bool = False) -> VystupOut:
    """Sestaví kompletní podklad pro náhled/editor: konfigurace (uložená nebo
    výchozí) + katalog dostupných polí + resolvnuté zákaznické hodnoty.

    `vychozi=True` vynutí kódovou předlohu i tehdy, když je něco uloženo
    (tlačítko „Obnovit výchozí“ – uloží se až na explicitní Uložit)."""
    ulozeny = (
        db.query(NabidkaVystup)
        .filter(NabidkaVystup.nabidka_id == n.id, NabidkaVystup.typ_reseni == typ_reseni)
        .first()
    )
    if not vychozi and ulozeny is not None and ulozeny.konfigurace_json:
        # Uložené rozvržení se bere, jen když je v modelu v2 (stránky + prvky
        # v mm). Cokoli staršího dostane výchozí předlohu – původní záznam
        # v DB zůstává, dokud ho obchodník nepřepíše tlačítkem Uložit.
        konfigurace, je_vychozi = sablona_katalog.nacti_konfiguraci(
            typ_reseni, ulozeny.konfigurace_json
        )
    else:
        konfigurace = sablona_katalog.vychozi_sablona(typ_reseni)
        je_vychozi = True

    reseni = _posledni_reseni(db, n.id, typ_reseni)
    popis = reseni.popis_json if reseni is not None else None

    return VystupOut(
        typ_reseni=typ_reseni,
        existuje_reseni=reseni is not None,
        je_vychozi=je_vychozi,
        konfigurace=konfigurace,
        katalog=sablona_katalog.katalog_pro_frontend(typ_reseni),
        zakaznik={
            "nazev": n.zakaznik_nazev or "",
            "adresa": n.zakaznik_adresa or "",
            "datum": _iso(datetime.now()),
        },
        hodnoty=sablona_katalog.resolvni_hodnoty(typ_reseni, popis),
        tabulka=sablona_katalog.resolvni_tabulku(typ_reseni, popis),
        graf=sablona_katalog.graf_pro_typ(typ_reseni, popis),
    )


def _over_konfiguraci(typ_reseni: str, konfigurace: VystupKonfigurace) -> None:
    """POJISTKA „jen zákaznická data“: každé pole/sloupec/dlaždice musí být
    v katalogu daného typu, jinak 422. Platí pro uloženou šablonu nabídky i pro
    pojmenovanou šablonu – obojí končí ve stejném vykreslení."""
    povolena_pole = sablona_katalog.platne_klice(typ_reseni)
    povolene_sloupce = sablona_katalog.platne_sloupce(typ_reseni)

    def over_prvek(prvek) -> None:
        if prvek.druh == "udaj":
            if prvek.klic not in povolena_pole:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Údaj '{prvek.klic}' není mezi povolenými zákaznickými údaji "
                        f"pro {typ_reseni} – do nabídky ho vložit nelze."
                    ),
                )
        elif prvek.druh == "tabulka":
            for klic in prvek.pole:
                if klic not in povolene_sloupce:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Sloupec '{klic}' není mezi povolenými sloupci tabulky "
                            f"pro {typ_reseni}."
                        ),
                    )
        for dite in prvek.deti:
            over_prvek(dite)

    for stranka in konfigurace.stranky:
        for prvek in stranka.prvky:
            over_prvek(prvek)


def _sanituj_konfiguraci(konfigurace: VystupKonfigurace) -> VystupKonfigurace:
    """Pročistí formátovaný text ve všech prvcích.

    Editor píše text přímo na papíře, takže do `html` teče, co uživatel
    naformátoval nebo vložil odjinud. Whitelist tagů a stylů drží
    `vystup_html` – tady se jen projde strom. Vrací novou konfiguraci,
    vstupní model zůstává nedotčený.
    """

    def vycisti(prvek: VystupPrvek) -> VystupPrvek:
        return prvek.model_copy(
            update={
                "html": vystup_html.vycisti_html(prvek.html),
                "deti": [vycisti(d) for d in prvek.deti],
            }
        )

    return konfigurace.model_copy(
        update={
            "stranky": [
                s.model_copy(update={"prvky": [vycisti(p) for p in s.prvky]})
                for s in konfigurace.stranky
            ]
        }
    )


def _over_typ_reseni(typ_reseni: str) -> None:
    if typ_reseni not in sablona_katalog.PODPOROVANE_TYPY:
        raise HTTPException(
            status_code=422,
            detail=f"Šablona výstupu není podporovaná pro typ: {typ_reseni}",
        )


@router.get("/nabidky/{nabidka_id}/vystup/{typ_reseni}", response_model=VystupOut)
def detail_vystupu(
    nabidka_id: int,
    typ_reseni: str,
    vychozi: bool = False,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Podklad pro editor i tiskový náhled nabídky (konfigurace + hodnoty).
    `vychozi=1` vrátí kódovou předlohu i při uložené šabloně."""
    _over_typ_reseni(typ_reseni)
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _vystup_out(db, n, typ_reseni, vychozi=vychozi)


@router.put("/nabidky/{nabidka_id}/vystup/{typ_reseni}", response_model=VystupOut)
def uloz_vystup(
    nabidka_id: int,
    typ_reseni: str,
    vstup: VystupKonfigurace,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Uloží šablonu výstupu nabídky. POJISTKA „jen zákaznická data“: každé
    pole/sloupec musí být v katalogu daného typu, jinak 422 – interní klíč
    (CAPEX, NPV, marže…) se do konfigurace nedostane. Formátovaný text projde
    whitelistem značek, ať se do PDF nedostane nic než formátování."""
    _over_typ_reseni(typ_reseni)
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")

    _over_konfiguraci(typ_reseni, vstup)

    konfigurace = _sanituj_konfiguraci(vstup).model_dump()
    zaznam = (
        db.query(NabidkaVystup)
        .filter(NabidkaVystup.nabidka_id == n.id, NabidkaVystup.typ_reseni == typ_reseni)
        .first()
    )
    if zaznam is None:
        zaznam = NabidkaVystup(
            nabidka_id=n.id,
            typ_reseni=typ_reseni,
            konfigurace_json=konfigurace,
            vytvoril_user_id=user.id,
        )
        db.add(zaznam)
    else:
        zaznam.konfigurace_json = konfigurace
    db.commit()
    return _vystup_out(db, n, typ_reseni)


# ---------------- obrázky vložené do výstupu ----------------
# Obrázek se nahraje zvlášť a do konfigurace se uloží jen jeho cesta. Tím se
# rozvržení drží malé (JSON v DB) a stejný obrázek může být na papíře vícekrát.


@router.post("/nabidky/{nabidka_id}/vystup-obrazky")
async def nahraj_obrazek_vystupu(
    nabidka_id: int,
    soubor: UploadFile = File(...),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Nahraje obrázek pro vložení do nabídky. Vrací cestu do konfigurace."""
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")

    nazev = soubor.filename or "obrazek"
    if not vystup_obrazky.je_povolena(nazev):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Soubor „{nazev}“ není obrázek. Povolené: "
                + ", ".join(sorted(vystup_obrazky.POVOLENE_PRIPONY))
            ),
        )
    obsah = await soubor.read()
    if len(obsah) > vystup_obrazky.MAX_BAJTU:
        raise HTTPException(status_code=413, detail=f"Obrázek „{nazev}“ je větší než 10 MB.")
    if not obsah:
        raise HTTPException(status_code=422, detail="Soubor je prázdný.")

    cesta = vystup_obrazky.uloz(nabidka_id, nazev, obsah)
    return {"cesta": cesta, "nazev": nazev, "velikost_bajtu": len(obsah)}


@router.get("/vystup-obrazky/{cesta:path}")
def vydej_obrazek_vystupu(
    cesta: str,
    user: User = Depends(vyzaduj_nabidkovac),
):
    """Vydá nahraný obrázek. Cesta chodí od klienta, proto ta kontrola tvaru."""
    try:
        soubor = vystup_obrazky.cesta_k_obrazku(cesta)
    except ValueError:
        raise HTTPException(status_code=404, detail="Obrázek nenalezen")
    if not soubor.exists():
        raise HTTPException(status_code=404, detail="Obrázek nenalezen")
    return FileResponse(
        path=str(soubor),
        media_type=vystup_obrazky.mime_typ(cesta),
        content_disposition_type="inline",
    )


# ---------------- nabídka pro zákazníka jako PDF ----------------
# Papír vykresluje React (mm souřadnice, SVG grafy, barvy z CSS tokenů), takže
# jediná podoba, která se dá vytisknout beze ztráty, je ta z prohlížeče. Klient
# proto pošle hotové HTML papíru včetně stylů a obrázků v data: URI a server
# z něj Chromiem udělá PDF. Kdyby si server sazbu skládal sám, byl by to druhý
# renderer, který se s tím v editoru začne rozcházet.


def _pdf_out(z: GenerovanaNabidkaPdf) -> dict:
    return {
        "id": z.id,
        "nazev": z.nazev or f"nabidka-{z.nabidka_id}.pdf",
        "typ_reseni": z.typ_reseni or "",
        # "pdf" = nabídka pro zákazníka, "xlsx" = interní model. UI je odlišuje
        # ikonou i popiskem, aby nikdo neposlal klientovi marže.
        "format": z.format or "pdf",
        "vygenerovano_at": _iso(z.vygenerovano_at),
        "vygeneroval_jmeno": getattr(z.vygeneroval, "jmeno", None) if z.vygeneroval else None,
        "disk_url": z.disk_url or "",
        # Dokud PDF nemá kopii na Disku, běží (nebo spadla) fronta. UI podle
        # toho píše „propisuje se na Disk…" místo mrtvého odkazu.
        "na_disku": bool(z.disk_file_id),
    }


@router.get("/nabidky/{nabidka_id}/pdf")
def seznam_pdf_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Vygenerovaná PDF nabídky, nejnovější první.

    Historie zůstává celá: nabídka se přepočítá a vytiskne víckrát a musí být
    poznat, co přesně zákazník dostal a kdy.
    """
    if db.get(Nabidka, nabidka_id) is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    radky = (
        db.query(GenerovanaNabidkaPdf)
        .filter(GenerovanaNabidkaPdf.nabidka_id == nabidka_id)
        .order_by(GenerovanaNabidkaPdf.vygenerovano_at.desc(), GenerovanaNabidkaPdf.id.desc())
        .all()
    )
    return [_pdf_out(z) for z in radky]


@router.post("/nabidky/{nabidka_id}/vystup/{typ_reseni}/pdf")
def vyrob_pdf_nabidky(
    nabidka_id: int,
    typ_reseni: str,
    vstup: VystupPdfVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Z HTML papíru udělá PDF, uloží ho k nabídce a propíše na Disk.

    Nahrání na Disk běží na pozadí (fronta konektoru) — jinak by uživatel čekal
    na Google a při nabídce bez složky i na kopii celého vzoru. PDF má hned,
    odkaz na Disk se doplní během několika sekund.
    """
    _over_typ_reseni(typ_reseni)
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if not (vstup.html or "").strip():
        raise HTTPException(status_code=422, detail="Prázdný podklad pro PDF.")
    try:
        data = pdf_modul.vyrob(vstup.html)
    except pdf_modul.PdfNedostupne as e:
        # 503, ne 500: appka je v pořádku, jen tahle služba teď neumí odpovědět.
        raise HTTPException(status_code=503, detail=str(e))
    kdy = datetime.now()
    zaznam = pdf_modul.uloz(db, n, typ_reseni, data, user.id, "pdf", kdy)
    # U PPA vzniká zároveň interní výpočtový model. Chyba tady nesmí sebrat PDF,
    # které už je hotové – Excel se pak dá dogenerovat tlačítkem zvlášť.
    if typ_reseni == "ppa":
        try:
            _vyrob_xlsx(db, n, user.id, kdy)
        except HTTPException:
            pass
    return _pdf_out(zaznam)


def _vyrob_xlsx(
    db: Session, n: Nabidka, user_id: int | None, kdy: datetime | None = None
) -> GenerovanaNabidkaPdf:
    """Interní PPA model do Excelu – ze stejné varianty, jakou tiskne PDF."""
    reseni = _posledni_reseni(db, n.id, "ppa")
    popis = (reseni.popis_json if reseni is not None else None) or {}
    varianta = ppa_tvar.zvolena_varianta(popis)
    if not varianta:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nabídka nemá spočítané PPA v aktuálním tvaru (v2). Přepočítej ji, "
                "pak půjde vyexportovat i výpočtový Excel."
            ),
        )
    nastaveni = (
        db.get(VypoctovaNastaveni, n.vypoctova_nastaveni_id)
        if n.vypoctova_nastaveni_id
        else None
    )
    if nastaveni is None:
        nastaveni = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    parametry = ppa_v2.parametry_z_nastaveni(
        nastaveni.parametry if nastaveni is not None else None
    )
    kdy = kdy or datetime.now()

    baterie = varianta.get("baterie") or {}
    popis_baterie = (
        f"s baterií {baterie.get('kapacita_kwh'):.0f} kWh"
        if varianta.get("s_baterii") and baterie.get("kapacita_kwh")
        else "bez baterie"
    )
    hlavicka = {
        "titulek": f"PPA výpočet – {n.cislo or f'nabídka {n.id}'}",
        "podtitulek": (
            f"{n.zakaznik_nazev or 'zákazník neuveden'} · FVE "
            f"{float(varianta.get('kwp') or 0):.0f} kWp {popis_baterie} · kontrakt na "
            f"{varianta.get('delka_kontraktu_roky')} let"
        ),
        "vygenerovano": f"Interní model, vygenerováno {kdy:%d. %m. %Y} z Greensie app",
        # Kontrakt běží od roku následujícího po výpočtu – v roce 0 se staví.
        "prvni_rok": kdy.year + 1,
    }
    data = excel_ppa.sestav(hlavicka, varianta, popis.get("vstup") or {}, parametry)
    return pdf_modul.uloz(db, n, "ppa", data, user_id, "xlsx", kdy)


@router.post("/nabidky/{nabidka_id}/vystup/ppa/xlsx")
def vyrob_xlsx_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Vyrobí jen výpočtový Excel (bez tisku PDF) a propíše ho na Disk.

    Normálně vzniká spolu s PDF; tohle je pro případ, že si ho někdo chce
    vygenerovat po přepočtu znovu, aniž by tiskl nabídku pro zákazníka.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _pdf_out(_vyrob_xlsx(db, n, user.id))


@router.get("/nabidka-pdf/{pdf_id}/soubor")
def vydej_pdf_nabidky(
    pdf_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Vydá vygenerovaný soubor (PDF k prohlédnutí, Excel ke stažení)."""
    z = db.get(GenerovanaNabidkaPdf, pdf_id)
    if z is None:
        raise HTTPException(status_code=404, detail="Soubor neexistuje")
    cesta = soubory.UPLOAD_DIR / z.soubor_cesta
    if not cesta.exists():
        raise HTTPException(status_code=404, detail="Soubor na serveru chybí.")
    return FileResponse(
        path=str(cesta),
        media_type=pdf_modul.mime_formatu(z.format),
        filename=z.nazev or cesta.name,
        # Excel prohlížeč nezobrazí – inline by z něj udělalo prázdnou záložku.
        content_disposition_type="inline" if z.format != "xlsx" else "attachment",
    )


# ---------------- pojmenované šablony rozvržení nabídky ----------------
# `NabidkaVystup` je rozvržení jedné nabídky. Tady jsou šablony napříč
# nabídkami: obchodník si vyladí vizuál, uloží ho pod názvem a příště jen
# vybere. Ukládá se POUZE rozvržení – čísla se vždy berou z řešení té nabídky,
# do které se šablona použije, takže se nemohou přenést data jiného zákazníka.
POCET_SABLON_Z_NABIDEK = 20


def _sablona_out(s: VystupSablona, typ_reseni: str) -> VystupSablonaOut:
    pouzitelna = sablona_katalog.je_verze2(s.konfigurace_json)
    return VystupSablonaOut(
        id=s.id,
        nazev=s.nazev,
        # Konfigurace ze starého modelu se do schématu v2 nevejde a vyjde
        # z ní prázdný dokument. Nevadí – u nepoužitelné šablony ji nikdo
        # nepoužije, jde jen o to, aby šablona šla vypsat a smazat.
        konfigurace=s.konfigurace_json if pouzitelna else {},
        aktualizovano_at=_iso(s.aktualizovano_at),
        pouzitelna=pouzitelna,
    )


@router.get("/vystup-sablony/{typ_reseni}", response_model=VystupSablonySeznam)
def seznam_vystup_sablon(
    typ_reseni: str,
    krome_nabidky: int | None = Query(None, description="ID nabídky, kterou zrovna edituju"),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Co si jde vybrat jako šablonu: pojmenované šablony + rozvržení už
    hotových nabídek stejného typu řešení (nejnovější první).

    Rozvržení z jiných nabídek se nabízí jen v modelu v2 – starší (plochý
    seznam bloků v mřížce 12 sloupců) by nový editor neuměl otevřít a
    obchodníkovi by vyprázdnil papír.

    Pojmenované šablony se vracejí všechny, ale ty staré mají
    `pouzitelna=False`. Editor je nenabídne k použití, jen k smazání –
    kdyby se odfiltrovaly úplně, uvízly by v databázi bez cesty ven.
    """
    _over_typ_reseni(typ_reseni)
    sablony = (
        db.query(VystupSablona)
        .filter(VystupSablona.typ_reseni == typ_reseni)
        .order_by(VystupSablona.nazev)
        .all()
    )
    dotaz = (
        db.query(NabidkaVystup, Nabidka)
        .join(Nabidka, Nabidka.id == NabidkaVystup.nabidka_id)
        .filter(NabidkaVystup.typ_reseni == typ_reseni)
        .order_by(NabidkaVystup.aktualizovano_at.desc())
    )
    if krome_nabidky is not None:
        dotaz = dotaz.filter(NabidkaVystup.nabidka_id != krome_nabidky)
    z_nabidek = []
    for vystup, nabidka in dotaz.limit(POCET_SABLON_Z_NABIDEK).all():
        if not sablona_katalog.je_verze2(vystup.konfigurace_json):
            continue
        datum = _iso(vystup.aktualizovano_at) or ""
        popis = nabidka.zakaznik_nazev or f"Nabídka #{nabidka.id}"
        z_nabidek.append(
            VystupSablonaZNabidky(
                nabidka_id=nabidka.id,
                nazev=f"{popis} ({datum[:10]})" if datum else popis,
                konfigurace=vystup.konfigurace_json,
            )
        )
    return VystupSablonySeznam(
        sablony=[_sablona_out(s, typ_reseni) for s in sablony],
        nabidky=z_nabidek,
    )


@router.post("/vystup-sablony/{typ_reseni}", response_model=VystupSablonaOut)
def uloz_vystup_sablonu(
    typ_reseni: str,
    vstup: VystupSablonaVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Uloží rozvržení pod názvem. Stejný název v rámci typu řešení se přepíše
    (obchodník tím šablonu aktualizuje). Whitelist polí platí stejně jako
    u šablony nabídky."""
    _over_typ_reseni(typ_reseni)
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Šablona musí mít název.")
    if len(nazev) > 120:
        raise HTTPException(status_code=422, detail="Název šablony je moc dlouhý (max 120 znaků).")
    _over_konfiguraci(typ_reseni, vstup.konfigurace)
    konfigurace = _sanituj_konfiguraci(vstup.konfigurace).model_dump()

    zaznam = (
        db.query(VystupSablona)
        .filter(VystupSablona.typ_reseni == typ_reseni, VystupSablona.nazev == nazev)
        .first()
    )
    if zaznam is None:
        zaznam = VystupSablona(
            nazev=nazev,
            typ_reseni=typ_reseni,
            konfigurace_json=konfigurace,
            vytvoril_user_id=user.id,
        )
        db.add(zaznam)
    else:
        zaznam.konfigurace_json = konfigurace
    db.commit()
    db.refresh(zaznam)
    return _sablona_out(zaznam, typ_reseni)


@router.delete("/vystup-sablony/{typ_reseni}/{sablona_id}")
def smaz_vystup_sablonu(
    typ_reseni: str,
    sablona_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Smaže pojmenovanou šablonu. Nabídky, které z ní vznikly, to neovlivní –
    mají vlastní kopii rozvržení."""
    _over_typ_reseni(typ_reseni)
    zaznam = (
        db.query(VystupSablona)
        .filter(VystupSablona.id == sablona_id, VystupSablona.typ_reseni == typ_reseni)
        .first()
    )
    if zaznam is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    db.delete(zaznam)
    db.commit()
    return {"smazano": True}
