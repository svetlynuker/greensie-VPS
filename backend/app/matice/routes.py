from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user
from app.database import get_db
from app.matice import freelo
from app.matice.models import Bunka, NastaveniBarev, NastaveniSynchronizace, Projekt, Sloupec
from app.matice.permissions import muze_editovat, vyzaduj_editora
from app.matice.schemas import (
    BarvyOut,
    BunkaOut,
    BunkaVstup,
    FazeOut,
    FreeloVstup,
    FreeloVysledek,
    MaticeOut,
    ProjektOut,
    ProjektVstup,
    SloupecVstup,
    SyncNastaveniOut,
    SyncNastaveniVstup,
    UkolOut,
    ZobrazeniVstup,
)
from app.auth.permissions import vyzaduj_admina

router = APIRouter(prefix="/matice", tags=["matice"])


# ---- pomocné ----
def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Neplatné datum: {s}")


def _date_str(d):
    return d.isoformat() if isinstance(d, date) else None


def _ziskej_barvy(db: Session) -> NastaveniBarev:
    barvy = db.get(NastaveniBarev, 1)
    if barvy is None:
        barvy = NastaveniBarev(id=1)
        db.add(barvy)
        db.commit()
        db.refresh(barvy)
    return barvy


def _barvy_out(b: NastaveniBarev) -> BarvyOut:
    return BarvyOut(
        zelena_od=b.zelena_od, zelena_do=b.zelena_do,
        zluta_od=b.zluta_od, zluta_do=b.zluta_do,
        oranzova_od=b.oranzova_od, oranzova_do=b.oranzova_do,
        cervena_od=b.cervena_od, cervena_do=b.cervena_do,
    )


# ---- čtení celé matice ----
@router.get("", response_model=MaticeOut)
def nacti_matici(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projekty = db.query(Projekt).order_by(Projekt.poradi, Projekt.id).all()
    sloupce = db.query(Sloupec).order_by(Sloupec.poradi, Sloupec.id).all()
    bunky = db.query(Bunka).all()

    # fáze = seskupené sloupce, pořadí dle prvního výskytu
    faze_map: dict[str, list[UkolOut]] = {}
    poradi_fazi: list[str] = []
    for s in sloupce:
        if s.faze not in faze_map:
            faze_map[s.faze] = []
            poradi_fazi.append(s.faze)
        faze_map[s.faze].append(UkolOut(sloupec_id=s.id, label=s.label, nazev=s.nazev))

    faze = [FazeOut(todo=f, ukoly=faze_map[f]) for f in poradi_fazi]

    bunky_out = {
        f"{b.projekt_id}||{b.sloupec_id}": BunkaOut(
            stav=b.stav,
            termin=_date_str(b.termin),
            osoba=b.osoba,
            poznamka=b.poznamka,
            url=b.url,
        )
        for b in bunky
    }

    return MaticeOut(
        muze_editovat=muze_editovat(user),
        faze=faze,
        projekty=[
            ProjektOut(
                id=p.id, nazev=p.nazev, url=p.url, termin=_date_str(p.termin), rucni=p.rucni, skryty=p.skryty
            )
            for p in projekty
        ],
        bunky=bunky_out,
        barvy=_barvy_out(_ziskej_barvy(db)),
    )


# ---- editace buňky (upsert) ----
@router.put("/bunka", response_model=BunkaOut)
def uloz_bunku(
    vstup: BunkaVstup,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    if db.get(Projekt, vstup.projekt_id) is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    if db.get(Sloupec, vstup.sloupec_id) is None:
        raise HTTPException(status_code=404, detail="Sloupec neexistuje")

    bunka = (
        db.query(Bunka)
        .filter(Bunka.projekt_id == vstup.projekt_id, Bunka.sloupec_id == vstup.sloupec_id)
        .first()
    )
    if bunka is None:
        bunka = Bunka(projekt_id=vstup.projekt_id, sloupec_id=vstup.sloupec_id)
        db.add(bunka)

    bunka.stav = vstup.stav
    bunka.termin = _parse_date(vstup.termin)
    bunka.osoba = vstup.osoba or ""
    bunka.poznamka = vstup.poznamka or ""
    bunka.upraveno_rucne = True

    db.commit()
    db.refresh(bunka)
    return BunkaOut(
        stav=bunka.stav,
        termin=_date_str(bunka.termin),
        osoba=bunka.osoba,
        poznamka=bunka.poznamka,
        url=bunka.url,
    )


# ---- ruční projekt ----
@router.post("/projekt", response_model=ProjektOut)
def pridej_projekt(
    vstup: ProjektVstup,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název projektu je povinný")
    max_poradi = db.query(Projekt).count()
    p = Projekt(
        nazev=nazev,
        url="",
        termin=_parse_date(vstup.termin),
        rucni=True,
        poradi=max_poradi,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProjektOut(
        id=p.id, nazev=p.nazev, url=p.url, termin=_date_str(p.termin), rucni=p.rucni, skryty=p.skryty
    )


# ---- skrytí / obnovení projektu ze zobrazení ----
@router.put("/projekt/{projekt_id}/zobrazeni", response_model=ProjektOut)
def nastav_zobrazeni_projektu(
    projekt_id: int,
    vstup: ZobrazeniVstup,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    p = db.get(Projekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    p.skryty = vstup.skryty
    db.commit()
    db.refresh(p)
    return ProjektOut(
        id=p.id, nazev=p.nazev, url=p.url, termin=_date_str(p.termin), rucni=p.rucni, skryty=p.skryty
    )


# ---- ruční sloupec (úkol) ----
@router.post("/sloupec", response_model=UkolOut)
def pridej_sloupec(
    vstup: SloupecVstup,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    faze = vstup.faze.strip()
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název úkolu je povinný")
    label = f"{faze} - {nazev}" if faze else nazev
    if db.query(Sloupec).filter(Sloupec.label == label).first():
        raise HTTPException(status_code=409, detail="Takový sloupec už existuje")
    max_poradi = db.query(Sloupec).count()
    s = Sloupec(label=label, faze=faze, nazev=nazev, rucni=True, poradi=max_poradi)
    db.add(s)
    db.commit()
    db.refresh(s)
    return UkolOut(sloupec_id=s.id, label=s.label, nazev=s.nazev)


# ---- nastavení barev ----
@router.put("/barvy", response_model=BarvyOut)
def uloz_barvy(
    vstup: BarvyOut,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    b = _ziskej_barvy(db)
    for pole, hodnota in vstup.model_dump().items():
        setattr(b, pole, hodnota)
    db.commit()
    db.refresh(b)
    return _barvy_out(b)


# ---- synchronizace z Freela (sdílené jádro) ----
def proved_synchronizaci(
    db: Session,
    *,
    nove_projekty: bool,
    nove_ukoly: bool,
    prepis_stav: bool,
    prepis_terminy: bool,
    prepis_osoby: bool,
) -> FreeloVysledek:
    """Stáhne data z Freela a promítne je do matice podle zapnutých voleb.

    - `nove_projekty` / `nove_ukoly` — zakládat nové projekty / úkoly (buňky+sloupce).
    - `prepis_*` — u EXISTUJÍCÍ buňky přepsat dané pole hodnotou z Freela
      (vypnuté pole zůstane beze změny). Poznámka se nepřepisuje NIKDY.

    Volá se ručně z endpointu i automaticky z plánovače. Chyby Freela probublají
    ven (volající je ošetří). Na konci commituje.
    """
    fr_projekty = freelo.nacti_aktivni_projekty()
    fr_ukoly = freelo.nacti_ukoly([p["freelo_id"] for p in fr_projekty])

    # projekty (upsert dle freelo_id; nové jen když nove_projekty)
    projekt_dle_freelo: dict[int, Projekt] = {}
    poradi_p = db.query(Projekt).count()
    for fp in fr_projekty:
        p = db.query(Projekt).filter(Projekt.freelo_id == fp["freelo_id"]).first()
        if p is None:
            if not nove_projekty:
                continue
            p = Projekt(freelo_id=fp["freelo_id"], nazev=fp["nazev"], url=fp["url"], poradi=poradi_p)
            poradi_p += 1
            db.add(p)
        else:
            p.nazev = fp["nazev"]
            p.url = fp["url"]
        projekt_dle_freelo[fp["freelo_id"]] = p
    db.flush()

    # sloupce (dle labelu; nové jen když nove_ukoly)
    sloupec_dle_labelu: dict[str, Sloupec] = {s.label: s for s in db.query(Sloupec).all()}
    poradi_s = len(sloupec_dle_labelu)
    pocet_novych_sloupcu = 0
    for u in fr_ukoly:
        if u["label"] not in sloupec_dle_labelu:
            if not nove_ukoly:
                continue
            s = Sloupec(label=u["label"], faze=u["faze"], nazev=u["ukol_nazev"], poradi=poradi_s)
            poradi_s += 1
            pocet_novych_sloupcu += 1
            db.add(s)
            sloupec_dle_labelu[u["label"]] = s
    db.flush()

    # buňky
    novych = 0
    prepsanych = 0
    for u in fr_ukoly:
        p = projekt_dle_freelo.get(u["projekt_freelo_id"])
        s = sloupec_dle_labelu.get(u["label"])
        if p is None or s is None:
            continue
        bunka = (
            db.query(Bunka).filter(Bunka.projekt_id == p.id, Bunka.sloupec_id == s.id).first()
        )
        if bunka is None:
            if not nove_ukoly:
                continue
            bunka = Bunka(projekt_id=p.id, sloupec_id=s.id)
            db.add(bunka)
            bunka.stav = u["stav"]
            bunka.termin = _parse_date(u["termin"])
            bunka.osoba = u["osoba"]
            bunka.url = u["url"]
            bunka.freelo_task_id = u["freelo_task_id"]
            bunka.upraveno_rucne = False
            novych += 1
        else:
            # url + freelo_task_id jsou čistá Freelo metadata (odkaz na úkol) →
            # držíme je aktuální vždy, nepočítá se to jako přepis hodnoty.
            bunka.url = u["url"]
            bunka.freelo_task_id = u["freelo_task_id"]
            zmeneno = False
            if prepis_stav:
                bunka.stav = u["stav"]
                zmeneno = True
            if prepis_terminy:
                bunka.termin = _parse_date(u["termin"])
                zmeneno = True
            if prepis_osoby:
                bunka.osoba = u["osoba"]
                zmeneno = True
            # poznámku (jen v appce) NIKDY nepřepisujeme/nemažeme
            if zmeneno:
                prepsanych += 1

    db.commit()
    return FreeloVysledek(
        projektu=len(fr_projekty),
        sloupcu=pocet_novych_sloupcu,
        bunek_novych=novych,
        bunek_prepsanych=prepsanych,
    )


# ---- ruční načtení z Freela (tlačítko v pohledu) ----
@router.post("/freelo/nacist", response_model=FreeloVysledek)
def nacti_z_freela(
    vstup: FreeloVstup,
    user: User = Depends(vyzaduj_editora),
    db: Session = Depends(get_db),
):
    # "prepsat" = přepíše všechna pole; "bez_prepsani" = doplní jen nové úkoly/projekty
    prepsat = vstup.rezim == "prepsat"
    try:
        return proved_synchronizaci(
            db,
            nove_projekty=True,
            nove_ukoly=True,
            prepis_stav=prepsat,
            prepis_terminy=prepsat,
            prepis_osoby=prepsat,
        )
    except Exception as e:  # noqa: BLE001 - chybu chceme ukázat uživateli
        raise HTTPException(status_code=502, detail=f"Načtení z Freela selhalo: {e}")


# ---- nastavení automatické synchronizace ----
def ziskej_sync_nastaveni(db: Session) -> NastaveniSynchronizace:
    n = db.get(NastaveniSynchronizace, 1)
    if n is None:
        n = NastaveniSynchronizace(id=1)
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


def _sync_out(n: NastaveniSynchronizace) -> SyncNastaveniOut:
    return SyncNastaveniOut(
        auto_zapnuto=n.auto_zapnuto,
        interval_min=n.interval_min,
        sync_stav=n.sync_stav,
        sync_nove_ukoly=n.sync_nove_ukoly,
        sync_nove_projekty=n.sync_nove_projekty,
        sync_terminy=n.sync_terminy,
        sync_osoby=n.sync_osoby,
        posledni_beh=n.posledni_beh.isoformat() if n.posledni_beh else None,
        posledni_vysledek=n.posledni_vysledek or "",
    )


@router.get("/sync-nastaveni", response_model=SyncNastaveniOut)
def nacti_sync_nastaveni(
    user: User = Depends(vyzaduj_admina),
    db: Session = Depends(get_db),
):
    return _sync_out(ziskej_sync_nastaveni(db))


@router.put("/sync-nastaveni", response_model=SyncNastaveniOut)
def uloz_sync_nastaveni(
    vstup: SyncNastaveniVstup,
    user: User = Depends(vyzaduj_admina),
    db: Session = Depends(get_db),
):
    if vstup.interval_min < 5:
        raise HTTPException(status_code=422, detail="Interval musí být alespoň 5 minut.")
    n = ziskej_sync_nastaveni(db)
    n.auto_zapnuto = vstup.auto_zapnuto
    n.interval_min = vstup.interval_min
    n.sync_stav = vstup.sync_stav
    n.sync_nove_ukoly = vstup.sync_nove_ukoly
    n.sync_nove_projekty = vstup.sync_nove_projekty
    n.sync_terminy = vstup.sync_terminy
    n.sync_osoby = vstup.sync_osoby
    db.commit()
    db.refresh(n)
    return _sync_out(n)
