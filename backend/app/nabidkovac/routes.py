"""API Nabídkovače (SPEC-nabidkovac.md).

KOSTRA: zakládání/editace nabídek, nahrávání dokumentů BEZ zpracování,
správa katalogu technologií a verzovaných výpočtových nastavení. Žádná
výpočetní logika (sizing, PVGIS, ROI, LLM extrakce, generování PDF) tu není.
"""

import re
import unicodedata
from datetime import date, datetime

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import get_db
from app.nabidkovac import peak_shaving, soubory
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


def _varianta_json(v: peak_shaving.Varianta) -> dict:
    return {
        "baterie_id": v.baterie_id,
        "nazev": v.nazev,
        "pocet_kusu": v.pocet_kusu,
        "celkovy_vykon_kw": round(v.celkovy_vykon_kw, 3),
        "celkova_kapacita_kwh": round(v.celkova_kapacita_kwh, 3),
        "cena_celkem_kc": round(v.cena_celkem_kc, 2),
        "nova_rezervovana_kapacita_kw": round(v.nova_rezervovana_kapacita_kw, 2),
        "rocni_uspora_2026_kc": round(v.rocni_uspora_2026, 2),
        "navratnost_roky": (round(v.navratnost_roky, 2) if v.navratnost_roky is not None else None),
        "doporuceno": v.doporuceno,
        "ekonomika_2026": {
            k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.ekonomika_2026.items()
        },
        "ekonomika_2027": v.ekonomika_2027,
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
    profil_kw = [float(r.hodnota_kw) for r in radky]
    mesice = [r.cas.month for r in radky]
    interval_h = _interval_h_z_profilu([r.cas for r in radky])

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
    cena_prekroceni = p2026.get("cena_prekroceni_kc_kw")
    if cena_rezervace is None or cena_prekroceni is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Sazba stara_2026 pro {vstup.distributor}/{vstup.napetova_hladina} nemá "
                "vyplněnou cenu rezervované kapacity nebo pokutu za překročení "
                "(u této kombinace se hodnota teprve dohledává – doplň v adminu)."
            ),
        )

    sazba_2027 = _najdi_sazbu(db, vstup.distributor, vstup.napetova_hladina, "nova_2027", 2027)
    parametry_2027 = sazba_2027.parametry if sazba_2027 is not None else None

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
    )

    popis_json = {
        "typ_reseni": "peak_shaving",
        "vstup": {
            "distributor": vstup.distributor,
            "napetova_hladina": vstup.napetova_hladina,
            "rezervovana_kapacita_kw": vstup.rezervovana_kapacita_kw,
            "interval_h": interval_h,
            "poctu_intervalu": len(profil_kw),
        },
        "sazby": {
            "stara_2026_id": sazba_2026.id,
            "nova_2027_id": (sazba_2027.id if sazba_2027 is not None else None),
            "sazby_2027_k_dispozici": bool(parametry_2027),
        },
        "max_navratnost_roky": max_navratnost,
        "doporucena": (_varianta_json(vysledek.doporucena) if vysledek.doporucena else None),
        # 2.–3. nejlepší varianta pro srovnání (kap. 5) – vítěz je [0].
        "varianty": [_varianta_json(v) for v in vysledek.varianty[:3]],
        "upozorneni": vysledek.upozorneni,
    }
    if not parametry_2027:
        popis_json["upozorneni"] = list(vysledek.upozorneni) + [
            "Ekonomika roku 2027: čeká se na oficiální sazby ERÚ."
        ]

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
