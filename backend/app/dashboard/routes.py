"""Souhrn pro úvodní stránku (Rozcestník).

Jeden dotaz, který složí čísla ze všech modulů, na které má uživatel právo.
Nic nepočítá znovu jinak než příslušný modul: „nehotový úkol" je stav "todo"
(stejně jako v Přehledu změn), „neuhrazená faktura" je ta, která není
zaplacená ani označená jako nefakturovaná (stejně jako v Přehledu financí).

Sekce bez práva se nevrací vůbec (None) — frontend je pak nekreslí, takže se
uživatel nedozví ani to, že existují. Odpovídá to skrývání položek v nabídce.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.dashboard.schemas import (
    DashboardOut,
    FinanceSouhrn,
    NabidkySouhrn,
    ProjektySouhrn,
    UkolRadek,
)
from app.database import get_db
from app.finance.models import Faktura
from app.matice.models import Bunka, Projekt, Sloupec
from app.nabidkovac.models import Nabidka

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Kolik dní dopředu se ještě považuje za „blíží se termín".
OKNO_BLIZI_SE_DNI = 14
# Kolik řádků nejvýš poslat do výpisů (dashboard má být přehled, ne seznam).
LIMIT_VYPISU = 6
# Faktura, kterou nemá smysl počítat mezi neuhrazené.
STAVY_MIMO_NEUHRAZENE = ("zaplaceno", "nefakturuje")


def _souhrn_projektu(db: Session, dnes: date) -> ProjektySouhrn:
    aktivni = db.query(func.count(Projekt.id)).filter(Projekt.skryty.is_(False)).scalar() or 0

    # Nehotové úkoly jen na projektech, které jsou v matici vidět.
    zaklad = (
        db.query(Bunka)
        .join(Projekt, Bunka.projekt_id == Projekt.id)
        .filter(Projekt.skryty.is_(False), Bunka.stav == "todo")
    )

    po_terminu = zaklad.filter(Bunka.termin.isnot(None), Bunka.termin < dnes).count()
    blizi_se = zaklad.filter(
        Bunka.termin.isnot(None),
        Bunka.termin >= dnes,
        Bunka.termin <= dnes + timedelta(days=OKNO_BLIZI_SE_DNI),
    ).count()
    bez_terminu = zaklad.filter(Bunka.termin.is_(None)).count()

    return ProjektySouhrn(
        aktivni=aktivni,
        po_terminu=po_terminu,
        blizi_se=blizi_se,
        bez_terminu=bez_terminu,
    )


def _vypis_ukolu(db: Session, dnes: date, po_terminu: bool) -> list[UkolRadek]:
    """Nehotové úkoly po termínu (nejstarší první), nebo ty, co se blíží."""
    q = (
        db.query(Bunka, Projekt, Sloupec)
        .join(Projekt, Bunka.projekt_id == Projekt.id)
        .join(Sloupec, Bunka.sloupec_id == Sloupec.id)
        .filter(Projekt.skryty.is_(False), Bunka.stav == "todo", Bunka.termin.isnot(None))
    )
    if po_terminu:
        q = q.filter(Bunka.termin < dnes).order_by(Bunka.termin.asc())
    else:
        q = q.filter(
            Bunka.termin >= dnes,
            Bunka.termin <= dnes + timedelta(days=OKNO_BLIZI_SE_DNI),
        ).order_by(Bunka.termin.asc())

    return [
        UkolRadek(
            projekt_id=projekt.id,
            projekt_nazev=projekt.nazev,
            ukol=sloupec.nazev,
            termin=bunka.termin.isoformat() if bunka.termin else None,
            osoba=bunka.osoba or "",
            dni=(dnes - bunka.termin).days,
        )
        for bunka, projekt, sloupec in q.limit(LIMIT_VYPISU).all()
    ]


def _souhrn_financi(db: Session, dnes: date) -> FinanceSouhrn:
    neuhrazene = (
        db.query(Faktura)
        .join(Projekt, Faktura.projekt_id == Projekt.id)
        .filter(Projekt.skryty.is_(False), Faktura.stav.notin_(STAVY_MIMO_NEUHRAZENE))
        .all()
    )

    neuhrazeno_kc = 0.0
    po_splatnosti_kc = 0.0
    po_splatnosti_pocet = 0
    nejstarsi_dni: int | None = None

    for f in neuhrazene:
        castka = float(f.castka) if f.castka is not None else 0.0
        neuhrazeno_kc += castka
        if f.termin is not None and f.termin < dnes:
            po_splatnosti_pocet += 1
            po_splatnosti_kc += castka
            dni = (dnes - f.termin).days
            if nejstarsi_dni is None or dni > nejstarsi_dni:
                nejstarsi_dni = dni

    return FinanceSouhrn(
        neuhrazeno_kc=neuhrazeno_kc,
        neuhrazeno_pocet=len(neuhrazene),
        po_splatnosti_pocet=po_splatnosti_pocet,
        po_splatnosti_kc=po_splatnosti_kc,
        nejstarsi_dni=nejstarsi_dni,
    )


def _souhrn_nabidek(db: Session, dnes: date) -> NabidkySouhrn:
    celkem = db.query(func.count(Nabidka.id)).scalar() or 0
    hotove = db.query(func.count(Nabidka.id)).filter(Nabidka.stav == "hotovo").scalar() or 0
    nove = (
        db.query(func.count(Nabidka.id))
        .filter(Nabidka.vytvoreno_at >= dnes - timedelta(days=30))
        .scalar()
        or 0
    )
    return NabidkySouhrn(
        celkem=celkem,
        rozpracovane=celkem - hotove,
        hotove=hotove,
        nove_30_dni=nove,
    )


@router.get("", response_model=DashboardOut)
def dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardOut:
    dnes = date.today()
    out = DashboardOut()

    if muze_otevrit(user, "projekty"):
        out.projekty = _souhrn_projektu(db, dnes)
        out.po_terminu = _vypis_ukolu(db, dnes, po_terminu=True)
        out.blizi_se = _vypis_ukolu(db, dnes, po_terminu=False)

    if muze_otevrit(user, "finance"):
        out.finance = _souhrn_financi(db, dnes)

    if muze_otevrit(user, "nabidkovac"):
        out.nabidky = _souhrn_nabidek(db, dnes)

    return out
