"""API Nabídkovače (SPEC-nabidkovac.md).

KOSTRA: zakládání/editace nabídek, nahrávání dokumentů BEZ zpracování,
správa katalogu technologií a verzovaných výpočtových nastavení. Žádná
výpočetní logika (sizing, PVGIS, ROI, LLM extrakce, generování PDF) tu není.
"""

from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import get_db
from app.nabidkovac import soubory
from app.nabidkovac.models import (
    TYPY_DOKUMENTU,
    TYPY_NABIDKY,
    Nabidka,
    NabidkaDokument,
    Technologie,
    VypoctovaNastaveni,
)
from app.nabidkovac.permissions import vyzaduj_katalog, vyzaduj_nabidkovac
from app.nabidkovac.schemas import (
    DokumentOut,
    NabidkaDetailOut,
    NabidkaRadekOut,
    NabidkaUprava,
    NabidkaVstup,
    ReseniOut,
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
    )


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
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název je povinný")
    t = Technologie(
        typ=vstup.typ,
        nazev=nazev,
        model=(vstup.model or "").strip(),
        vykon_kw=vstup.vykon_kw,
        kapacita_kwh=vstup.kapacita_kwh,
        cena_kc=vstup.cena_kc,
        ucinnost=vstup.ucinnost,
        dostupnost=vstup.dostupnost,
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
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název je povinný")
    t.typ = vstup.typ
    t.nazev = nazev
    t.model = (vstup.model or "").strip()
    t.vykon_kw = vstup.vykon_kw
    t.kapacita_kwh = vstup.kapacita_kwh
    t.cena_kc = vstup.cena_kc
    t.ucinnost = vstup.ucinnost
    t.dostupnost = vstup.dostupnost
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
