"""API Nabídkovače (SPEC-nabidkovac.md).

KOSTRA: zakládání/editace nabídek, nahrávání dokumentů BEZ zpracování,
správa katalogu technologií a verzovaných výpočtových nastavení. Žádná
výpočetní logika (sizing, PVGIS, ROI, LLM extrakce, generování PDF) tu není.
"""

import dataclasses
import re
import unicodedata
from datetime import date, datetime

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import get_db
from app.nabidkovac import peak_shaving, ppa_fve, profil_import, profil_pokryti, soubory
from app.nabidkovac.models import (
    DISTRIBUTORI,
    NAPETOVE_HLADINY,
    STRUKTURY_TARIFU,
    TYPY_DOKUMENTU,
    TYPY_NABIDKY,
    TYPY_SLOUPCE,
    KatalogSloupec,
    Nabidka,
    NabidkaDokument,
    NavrhovaneReseni,
    SazbaDistributoru,
    SpotrebaProfil,
    Technologie,
    VypoctovaNastaveni,
)
from app.nabidkovac.permissions import vyzaduj_katalog, vyzaduj_nabidkovac
from app.nabidkovac.schemas import (
    DokumentOut,
    KatalogSloupecOut,
    KatalogSloupecVstup,
    NabidkaDetailOut,
    NabidkaRadekOut,
    NabidkaUprava,
    NabidkaVstup,
    PeakShavingVstup,
    PpaVstup,
    ReseniOut,
    SazbaOut,
    SazbaVstup,
    TechnologieOut,
    TechnologieVstup,
    VypoctovaNastaveniOut,
    VypoctovaNastaveniVstup,
)

router = APIRouter(prefix="/nabidkovac", tags=["nabidkovac"])


# ---- pomocné ----
def _iso(dt) -> str | None:
    if isinstance(dt, (datetime, date)):
        return dt.isoformat()
    return None


def _num(x) -> float | None:
    return float(x) if x is not None else None


def _dokument_out(d: NabidkaDokument) -> DokumentOut:
    return DokumentOut(
        id=d.id,
        typ=d.typ,
        puvodni_nazev=d.puvodni_nazev,
        velikost_bajtu=d.velikost_bajtu,
        stav_zpracovani=d.stav_zpracovani,
        nahrano_at=_iso(d.nahrano_at),
    )


def _nabidka_detail(n: Nabidka) -> NabidkaDetailOut:
    return NabidkaDetailOut(
        id=n.id,
        typ=n.typ,
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
    """Založí nový záznam nabídky (stav = koncept) a vrátí detail k vyplnění."""
    if vstup.typ not in TYPY_NABIDKY:
        raise HTTPException(status_code=422, detail=f"Neznámý typ nabídky: {vstup.typ}")
    n = Nabidka(
        typ=vstup.typ,
        zakaznik_nazev=(vstup.zakaznik_nazev or "").strip(),
        vytvoril_user_id=user.id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return _nabidka_detail(n)


@router.get("/nabidky/{nabidka_id}", response_model=NabidkaDetailOut)
def detail_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    return _nabidka_detail(n)


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
    db.commit()
    db.refresh(n)
    return _nabidka_detail(n)


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
    typ: str = Form(...),
    soubor: UploadFile = File(...),
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Nahraje dokument k nabídce. NEZPRACOVÁVÁ ho – jen uloží soubor a založí
    záznam se stavem "nahrano". Extrakce/parsování přijde v dalších promptech.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if typ not in TYPY_DOKUMENTU:
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


# ================= Katalog technologií =================
def _technologie_out(t: Technologie) -> TechnologieOut:
    return TechnologieOut(
        id=t.id,
        typ=t.typ,
        nazev=t.nazev,
        model=t.model or "",
        vykon_kw=_num(t.vykon_kw),
        kapacita_kwh=_num(t.kapacita_kwh),
        cena_kc=_num(t.cena_kc),
        ucinnost=_num(t.ucinnost),
        dostupnost=t.dostupnost,
        raynet_id=t.raynet_id,
        extra=t.extra or {},
    )


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
    """
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název je povinný")
    if vstup.typ == "baterie":
        if not vstup.vykon_kw or vstup.vykon_kw <= 0 or not vstup.kapacita_kwh or vstup.kapacita_kwh <= 0:
            raise HTTPException(
                status_code=422,
                detail=(
                    "U baterie musí být vyplněný výkon (kW) i kapacita (kWh) – "
                    "obojí kladné (METODIKA kap. 3.2)."
                ),
            )
    return nazev


@router.get("/technologie", response_model=list[TechnologieOut])
def seznam_technologii(
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Katalog vidí každý s právem na Nabídkovač; editovat smí jen katalogové právo."""
    ts = db.query(Technologie).order_by(Technologie.typ, Technologie.nazev, Technologie.id).all()
    return [_technologie_out(t) for t in ts]


@router.post("/technologie", response_model=TechnologieOut)
def pridej_technologii(
    vstup: TechnologieVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    nazev = _over_technologii(vstup)
    t = Technologie(
        typ=vstup.typ,
        nazev=nazev,
        model=(vstup.model or "").strip(),
        vykon_kw=vstup.vykon_kw,
        kapacita_kwh=vstup.kapacita_kwh,
        cena_kc=vstup.cena_kc,
        ucinnost=vstup.ucinnost,
        dostupnost=vstup.dostupnost,
        extra=_zpracuj_extra(db, vstup.extra),
        vytvoril_user_id=user.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _technologie_out(t)


@router.put("/technologie/{technologie_id}", response_model=TechnologieOut)
def uprav_technologii(
    technologie_id: int,
    vstup: TechnologieVstup,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    t = db.get(Technologie, technologie_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Technologie neexistuje")
    nazev = _over_technologii(vstup)
    t.typ = vstup.typ
    t.nazev = nazev
    t.model = (vstup.model or "").strip()
    t.vykon_kw = vstup.vykon_kw
    t.kapacita_kwh = vstup.kapacita_kwh
    t.cena_kc = vstup.cena_kc
    t.ucinnost = vstup.ucinnost
    t.dostupnost = vstup.dostupnost
    t.extra = _zpracuj_extra(db, vstup.extra)
    db.commit()
    db.refresh(t)
    return _technologie_out(t)


@router.delete("/technologie/{technologie_id}")
def smaz_technologii(
    technologie_id: int,
    user: User = Depends(vyzaduj_katalog),
    db: Session = Depends(get_db),
):
    t = db.get(Technologie, technologie_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Technologie neexistuje")
    db.delete(t)
    db.commit()
    return {"smazano": technologie_id}


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


@router.post("/dokumenty/{dokument_id}/zpracuj-profil")
def zpracuj_profil(
    dokument_id: int,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Naparsuje nahraný soubor s 15min profilem (XLS/XLSX/CSV) do `spotreba_profil`.

    „Poslední vyhrává“ (audit SP-2): nahradí se CELÝ dosavadní profil nabídky
    (i z jiných dokumentů) – dřív se mazaly jen řádky ze stejného dokumentu
    a dva různé soubory se tiše sečetly do dvojnásobné spotřeby. Duplicitní
    časy uvnitř souboru (podzimní přechod času) se slučují před vkladem,
    unikátnost (nabidka_id, cas) jistí i DB constraint.
    """
    d = db.get(NabidkaDokument, dokument_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Dokument neexistuje")
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

    # „Poslední vyhrává" – zahoď celý předchozí profil nabídky a vlož nový
    # (bulk kvůli objemu ~35 tis. řádků).
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
    casy: list[datetime], hodnoty: list[float], interval_h: float
) -> tuple[list[datetime], list[float], list[str]]:
    """Ochrana ročních výpočtů před neúplným/přesahujícím profilem (SP-1).

    Profil delší než rok ořízne na posledních 12 celých měsíců (s upozorněním
    do výstupu); profil, který ani potom není použitelný jako roční (málo dní,
    chybějící měsíce, díry > 2 %), shodí na HTTP 422 – radši žádné číslo než
    sebejistě špatná „roční“ ekonomika (bughunt testy T2/T3).
    """
    casy, hodnoty, orezano = profil_pokryti.orizni_na_posledni_rok(casy, hodnoty, interval_h)
    ok, duvod = profil_pokryti.zkontroluj_pokryti(casy, interval_h)
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
        # Fyzický strop simulace vs. sjednávaná RK se rezervou (PS-6).
        "strop_kw": round(v.strop_kw, 2),
        "rezerva_rk_procenta": round(v.rezerva_rk_procenta, 2),
        "nova_rezervovana_kapacita_kw": round(v.nova_rezervovana_kapacita_kw, 2),
        "rocni_uspora_2026_kc": round(v.rocni_uspora_2026, 2),
        "navratnost_roky": (round(v.navratnost_roky, 2) if v.navratnost_roky is not None else None),
        # Návratnost podle modelů (2026 / 2027 – jediný model bez slevy AKU, PS-3).
        "navratnost_2026": (round(v.navratnost_2026, 2) if v.navratnost_2026 is not None else None),
        "navratnost_2027": (
            round(v.navratnost_2027, 2) if v.navratnost_2027 is not None else None
        ),
        "doporuceno": v.doporuceno,
        "ekonomika_2026": {
            k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.ekonomika_2026.items()
        },
        "ekonomika_2027": {
            k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.ekonomika_2027.items()
        },
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

    # 1) profil odběru (kW) z uložené časové řady
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
    casy_profilu, profil_kw, upozorneni_profilu = _zvaliduj_a_orizni_profil(
        casy_profilu, profil_kw, interval_h
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

    # 3) katalog baterií (typ=baterie, dostupné, s výkonem i kapacitou – kap. 3.2)
    tech = (
        db.query(Technologie)
        .filter(
            Technologie.typ == "baterie",
            Technologie.dostupnost.is_(True),
            Technologie.vykon_kw.isnot(None),
            Technologie.kapacita_kwh.isnot(None),
        )
        .all()
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
    )

    popis_json = {
        "typ_reseni": "peak_shaving",
        "vstup": {
            "distributor": vstup.distributor,
            "napetova_hladina": vstup.napetova_hladina,
            "rezervovana_kapacita_kw": vstup.rezervovana_kapacita_kw,
            "cena_energie_kc_mwh": float(cena_energie),
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
        "max_navratnost_roky": max_navratnost,
        "doporucena": (_varianta_json(vysledek.doporucena) if vysledek.doporucena else None),
        # 2.–3. nejlepší varianta pro srovnání (kap. 5) – vítěz je [0].
        "varianty": [_varianta_json(v) for v in vysledek.varianty[:3]],
        "upozorneni": upozorneni_profilu + list(vysledek.upozorneni) + upozorneni_sazeb,
    }
    if not parametry_2027:
        popis_json["upozorneni"] = popis_json["upozorneni"] + [
            "Ekonomika roku 2027: čeká se na oficiální sazby ERÚ."
        ]

    # Data pro grafy odběru (bez baterie vs. s baterií) – pro doporučenou variantu.
    if vysledek.doporucena is not None:
        d = vysledek.doporucena
        graf = peak_shaving.graf_maxima(
            profil_kw,
            mesice,
            d.celkovy_vykon_kw,
            d.vyuzitelna_kapacita_kwh,
            d.strop_kw,
            interval_h,
            d.ucinnost_rt,
        )
        graf["rp_soucasna_kw"] = round(vstup.rezervovana_kapacita_kw, 2)
        graf["rp_nova_kw"] = round(d.nova_rezervovana_kapacita_kw, 2)
        popis_json["graf"] = graf

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


def _ppa_varianta_souhrn(r: dict) -> dict:
    """Kompaktní souhrn jedné velikosti pro srovnání variant (bez těžkých polí)."""
    return {
        "kwp": r.get("kwp"),
        "capex_kc": r.get("capex_kc"),
        "pokryti_spotreby_fve": r.get("pokryti_spotreby_fve"),
        "mira_samospotreby": r.get("mira_samospotreby"),
        "vyroba_rok1_kwh": r.get("vyroba_rok1_kwh"),
        "navratnost_roky": r.get("navratnost_roky"),
        "npv_kc": r.get("npv_kc"),
        "irr": r.get("irr"),
    }


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


@router.post("/nabidky/{nabidka_id}/ppa/vypocet")
def spocti_ppa(
    nabidka_id: int,
    vstup: PpaVstup,
    user: User = Depends(vyzaduj_nabidkovac),
    db: Session = Depends(get_db),
):
    """Spustí PPA výpočet a uloží výsledek do `navrhovana_reseni` (typ_reseni = ppa).

    Postup dle METODIKY kap. 4–5:
    1. načte 15min profil spotřeby (kW → kWh) z `spotreba_profil`,
    2. simuluje výrobu FVE (kWp + lokalita + sklon/azimut),
    3. spáruje výrobu se spotřebou, spočítá ekonomiku klienta i investora po letech,
    4. uloží `NavrhovaneReseni` s ekonomikou a daty pro graf.
    """
    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if vstup.instalovany_vykon_kwp is not None and vstup.instalovany_vykon_kwp <= 0:
        raise HTTPException(status_code=422, detail="Ruční výkon FVE (kWp) musí být kladný.")
    if vstup.delka_kontraktu_roky <= 0:
        raise HTTPException(status_code=422, detail="Délka kontraktu musí být kladná.")

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

    # Manažerské nastavení (defaulty PPA) – aktuální verze.
    nastaveni = db.query(VypoctovaNastaveni).order_by(VypoctovaNastaveni.verze.desc()).first()
    cena_fve_kc_kwp = _ppa_param(nastaveni, "ppa_cena_fve_kc_kwp", ppa_fve.VYCHOZI_CENA_FVE_KC_KWP)
    ostatni_kc_kwp = _ppa_param(nastaveni, "ppa_ostatni_naklady_kc_kwp", 0.0)
    # Defaulty ekonomiky investora (audit PPA-6): O&M 350 Kč/kWp/rok,
    # diskont 7,5 % (dřívější 0/5 % přikrášlovaly výnos).
    oam_kc_kwp_rok = _ppa_param(nastaveni, "ppa_oam_kc_kwp_rok", ppa_fve.VYCHOZI_OAM_KC_KWP_ROK)
    diskont = _ppa_param(nastaveni, "ppa_diskontni_sazba", ppa_fve.VYCHOZI_DISKONTNI_SAZBA)
    vymena_rok = int(_ppa_param(nastaveni, "ppa_vymena_stridace_rok", 0.0))
    vymena_kc_kwp = _ppa_param(nastaveni, "ppa_vymena_stridace_kc_kwp", 0.0)
    merny_vynos = _ppa_param(nastaveni, "ppa_merny_vynos_kwh_kwp", ppa_fve.VYCHOZI_MERNY_VYNOS_KWH_KWP)
    # Pojistka proti překlepu: měrný výnos FVE v ČR je ~800–1100 kWh/kWp/rok.
    # Mimo rozumný rozsah (např. omylem zadaná 1) by zkreslil návrh velikosti → default.
    if not (100.0 <= merny_vynos <= 2000.0):
        upozorneni.append(
            f"Měrný výnos v nastavení ({merny_vynos:g} kWh/kWp) je mimo reálný rozsah – "
            f"použita výchozí hodnota {ppa_fve.VYCHOZI_MERNY_VYNOS_KWH_KWP:g}. "
            "Oprav ho v Katalogu a výpočtech (PPA nastavení)."
        )
        merny_vynos = ppa_fve.VYCHOZI_MERNY_VYNOS_KWH_KWP
    index_prebytek = _ppa_param(nastaveni, "ppa_index_prebytek_rocni", 0.0)

    # Indexy / degradace: vstup má přednost, jinak nastavení, jinak kódový default.
    index_ppa = vstup.index_ppa_rocni
    if index_ppa is None:
        index_ppa = _ppa_param(nastaveni, "ppa_index_ceny_rocni", 0.03)
    index_dod = vstup.index_dodavatel_rocni
    if index_dod is None:
        # Default = stejný jako PPA index (METODIKA kap. 4.4 – ať srovnání není zkreslené).
        index_dod = _ppa_param(nastaveni, "ppa_index_dodavatel_rocni", index_ppa)
    degradace = vstup.degradace_rocni
    if degradace is None:
        degradace = _ppa_param(nastaveni, "ppa_degradace_rocni", ppa_fve.VYCHOZI_DEGRADACE_ROCNI)
    # LID – degradace prvního roku (audit PPA-4): −2 % PERC / −1 % TOPCon.
    degradace_rok1 = vstup.degradace_rok1
    if degradace_rok1 is None:
        degradace_rok1 = _ppa_param(nastaveni, "ppa_degradace_rok1", ppa_fve.VYCHOZI_DEGRADACE_ROK1)

    # Vyhnutelné regulované složky (audit PPA-5): vstup má přednost, jinak
    # manažerské nastavení; POZE a eskalace regulovaných jen z nastavení.
    vyhnutelne_regulovane = vstup.vyhnutelne_regulovane_kc_mwh
    if vyhnutelne_regulovane is None:
        vyhnutelne_regulovane = _ppa_param(
            nastaveni,
            "ppa_vyhnutelne_regulovane_kc_mwh",
            ppa_fve.VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH,
        )
    index_regulovane = _ppa_param(nastaveni, "ppa_index_regulovane_rocni", 0.0)
    poze = _ppa_param(nastaveni, "ppa_poze_kc_mwh", 0.0)

    # Lokalita: GPS z nabídky, fallback střed ČR.
    lat = ppa_fve.VYCHOZI_LAT
    if n.zakaznik_gps_lat is not None:
        lat = float(n.zakaznik_gps_lat)
    else:
        upozorneni.append(
            f"Nabídka nemá GPS – použita výchozí šířka {ppa_fve.VYCHOZI_LAT}° (střed ČR). "
            "Doplň GPS zákazníka pro přesnější simulaci výroby."
        )

    # Cena přebytku – validace (potřeba i pro sweep velikostí).
    prebytek_cena = vstup.prebytek_cena_kc_mwh
    if vstup.prebytek_uctovat and (prebytek_cena is None or prebytek_cena <= 0):
        raise HTTPException(
            status_code=422,
            detail="Účtování přebytku je zapnuté, ale chybí cena přebytku (Kč/MWh).",
        )
    if prebytek_cena is None:
        prebytek_cena = 0.0

    # CAPEX jako funkce velikosti (kap. 3.4) – potřeba pro ekonomický sweep i override.
    if vstup.rezim_capex == "komponenty":
        tech = (
            db.query(Technologie)
            .filter(
                Technologie.dostupnost.is_(True),
                Technologie.vykon_kw.isnot(None),
                Technologie.cena_kc.isnot(None),
            )
            .all()
        )
        panely = [
            ppa_fve.Komponenta(t.id, t.typ, t.nazev, float(t.vykon_kw), float(t.cena_kc))
            for t in tech
            if t.typ == "fve_panel" and float(t.vykon_kw) > 0 and float(t.cena_kc) > 0
        ]
        invertory = [
            ppa_fve.Komponenta(t.id, t.typ, t.nazev, float(t.vykon_kw), float(t.cena_kc))
            for t in tech
            if t.typ == "invertor" and float(t.vykon_kw) > 0 and float(t.cena_kc) > 0
        ]
        if not panely and not invertory:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Komponentový režim: v katalogu chybí panely i invertory s cenou. "
                    "Doplň je v Katalogu, nebo přepni na režim „cena za kWp“."
                ),
            )
        if not panely:
            upozorneni.append("V katalogu není použitelný FVE panel – panely nejsou v CAPEX započítány.")
        if not invertory:
            upozorneni.append("V katalogu není použitelný invertor – invertory nejsou v CAPEX započítány.")

        def capex_fn(kwp: float):
            return ppa_fve.capex_komponenty(kwp, panely, invertory, ostatni_kc_kwp)
    else:
        def capex_fn(kwp: float):
            c = kwp * cena_fve_kc_kwp
            return c, {"rezim": "cena_kwp", "cena_kc_kwp": cena_fve_kc_kwp, "celkem_kc": round(c, 2)}

        upozorneni.append("CAPEX je odhad z ceny za kWp (manažerské nastavení), ne skutečné náklady.")

    # Šablona ekonomických vstupů (kWp a CAPEX se doplní pro každou velikost zvlášť).
    sablona = ppa_fve.VstupPPA(
        kwp=0.0,
        lat=lat,
        sklon_st=float(vstup.sklon_st),
        azimut_st=float(vstup.azimut_st),
        cena_ppa_kc_mwh=float(vstup.cena_ppa_kc_mwh),
        index_ppa_rocni=float(index_ppa),
        cena_silova_kc_mwh=float(vstup.cena_silova_kc_mwh),
        index_dodavatel_rocni=float(index_dod),
        vyhnutelne_regulovane_kc_mwh=float(vyhnutelne_regulovane),
        index_regulovane_rocni=float(index_regulovane),
        poze_kc_mwh=float(poze),
        delka_kontraktu_roky=int(vstup.delka_kontraktu_roky),
        degradace_rocni=float(degradace),
        degradace_rok1=float(degradace_rok1),
        capex_kc=0.0,
        prebytek_uctovat=bool(vstup.prebytek_uctovat),
        prebytek_cena_kc_mwh=float(prebytek_cena),
        index_prebytek_rocni=float(index_prebytek),
        rezervovany_vykon_dodavky_kw=(
            float(vstup.rezervovany_vykon_dodavky_kw) if vstup.rezervovany_vykon_dodavky_kw else None
        ),
        oam_kc_kwp_rok=float(oam_kc_kwp_rok),
        diskontni_sazba=float(diskont),
        merny_vynos_kwh_kwp=float(merny_vynos),
        interval_h=interval_h,
        vymena_stridace_rok=vymena_rok,
        vymena_stridace_kc_kwp=float(vymena_kc_kwp),
    )

    # Velikost FVE: ruční override, jinak ekonomický sweep (kap. 4.7 – režim
    # „nejlepší ekonomika“: pro škálu velikostí vybere nejvyšší NPV / nejkratší
    # návratnost, se zohledněním prodeje přebytku).
    max_kwp = float(vstup.max_kwp) if vstup.max_kwp else None
    navrzeno_automaticky = vstup.instalovany_vykon_kwp is None
    base1 = ppa_fve.simuluj_vyrobu(
        casy, 1.0, lat, float(vstup.sklon_st), float(vstup.azimut_st), merny_vynos
    )
    metoda_navrhu = "rucne"
    varianty: list[dict] = []
    if navrzeno_automaticky:
        kandidati = ppa_fve.kandidatni_velikosti(casy, spotreba_kwh, base1, max_kwp, pocet=30)
        if not kandidati:
            raise HTTPException(
                status_code=422,
                detail="Nepodařilo se navrhnout velikost FVE (zkontroluj profil spotřeby).",
            )
        vsechny = ppa_fve.vyber_velikost(sablona, casy, spotreba_kwh, kandidati, capex_fn, base1)
        vysledek = vsechny[0]
        metoda_navrhu = "ekonomicky"
        varianty = [_ppa_varianta_souhrn(r) for r in vsechny[:4]]
    else:
        kwp = float(vstup.instalovany_vykon_kwp)
        capex, rozpad = capex_fn(kwp)
        vstup_calc = dataclasses.replace(sablona, kwp=kwp, capex_kc=float(capex), capex_rozpad=rozpad)
        vysledek = ppa_fve.spocti_ppa(vstup_calc, casy, spotreba_kwh, [x * kwp for x in base1])

    if vysledek.get("mira_orezu", 0) >= 0.05:
        upozorneni.append(
            f"Rezervovaný výkon dodávky ořezává {round(vysledek['mira_orezu'] * 100)} % výroby – "
            "část přebytku se nevyužije."
        )
    if navrzeno_automaticky and not vstup.prebytek_uctovat:
        upozorneni.append(
            "Velikost vybrána podle ekonomiky bez prodeje přebytku – přebytek se nezapočítává do "
            "výnosu, proto vychází menší FVE. Zapnutím prodeje přebytku se optimum posune výš."
        )
    if (vysledek.get("kwp") or 0) > 30:
        upozorneni.append(
            "Výrobna nad 30 kW: dodávka z PPA podléhá dani z elektřiny (28,30 Kč/MWh) stejně "
            "jako dnešní dodávka – v úspoře se proto daň nesrovnává (symetrická). Investor "
            "(Greensie) má registrační povinnost u celní správy."
        )

    # Sanity-checky a doporučení (audit PPA-8).
    if not (1600.0 <= float(vstup.cena_ppa_kc_mwh) <= 2600.0):
        upozorneni.append(
            f"PPA cena {vstup.cena_ppa_kc_mwh:g} Kč/MWh je mimo obvyklé pásmo trhu "
            "1600–2600 Kč/MWh – zkontroluj zadání."
        )
    vyhnutelna_cena = float(vstup.cena_silova_kc_mwh) + float(vyhnutelne_regulovane) + float(poze)
    if float(vstup.cena_ppa_kc_mwh) >= vyhnutelna_cena:
        upozorneni.append(
            f"PPA cena je ≥ vyhnutelné ceně klienta ({vyhnutelna_cena:g} Kč/MWh) – "
            "klient by na PPA nešetřil nic."
        )
    if not vysledek.get("doporuceno", True):
        upozorneni.append(
            "PPA se při těchto parametrech investorovi nevyplatí (záporné NPV při "
            f"diskontu {float(diskont) * 100:g} %)."
        )
    upozorneni.append(
        "Výnos investora je úměrný skutečné samospotřebě klienta – pokles spotřeby během "
        "kontraktu výnos snižuje (reálné smlouvy to řeší minimálním odběrem / take-or-pay)."
    )

    popis_json = {
        "typ_reseni": "ppa",
        "vstup": {
            "instalovany_vykon_kwp": vysledek.get("kwp"),
            "navrzeno_automaticky": navrzeno_automaticky,
            "metoda_navrhu": metoda_navrhu,
            "max_kwp": max_kwp,
            "sklon_st": vstup.sklon_st,
            "azimut_st": vstup.azimut_st,
            "cena_ppa_kc_mwh": vstup.cena_ppa_kc_mwh,
            "cena_silova_kc_mwh": vstup.cena_silova_kc_mwh,
            "vyhnutelne_regulovane_kc_mwh": float(vyhnutelne_regulovane),
            "delka_kontraktu_roky": vstup.delka_kontraktu_roky,
            "rezim_capex": vstup.rezim_capex,
            "prebytek_uctovat": vstup.prebytek_uctovat,
            "rezervovany_vykon_dodavky_kw": vstup.rezervovany_vykon_dodavky_kw,
            "interval_h": interval_h,
            "poctu_intervalu": len(casy),
        },
        "vysledek": vysledek,
        "varianty": varianty,
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
