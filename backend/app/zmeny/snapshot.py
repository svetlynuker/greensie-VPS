"""Snímkování stavu matice pro Přehled změn.

Jednou denně uložíme „fotku“ stavu všech buněk (hotovo/nehotovo + termín).
Porovnáním dvou fotek (nebo fotky a živého stavu) spočítáme, co se za období
pohnulo. Tady je jen práce s daty; samotný výpočet rozdílů je v routes.py.
"""

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.matice.models import Bunka
from app.zmeny.models import StavSnapshot


def _dnes() -> date:
    return date.today()


def sejmi_snimek(db: Session, den: date | None = None) -> int:
    """Uloží snímek dnešního stavu, pokud pro daný den ještě neexistuje.

    Snímkujeme jen buňky s vyplněným stavem (todo/done) – prázdné buňky
    (stav None) žádný úkol nepředstavují. Idempotentní: druhé volání ve stejný
    den nic nepřidá. Vrací počet uložených řádků (0 = už bylo hotové).
    """
    den = den or _dnes()
    uz_je = db.query(StavSnapshot.id).filter(StavSnapshot.den == den).first()
    if uz_je is not None:
        return 0

    bunky = (
        db.query(Bunka.id, Bunka.stav, Bunka.termin)
        .filter(Bunka.stav.in_(("done", "todo")))
        .all()
    )
    for b in bunky:
        db.add(StavSnapshot(den=den, bunka_id=b.id, stav=b.stav, termin=b.termin))
    db.commit()
    return len(bunky)


def nejstarsi_den(db: Session) -> date | None:
    """Nejstarší den, ke kterému máme snímek (= „od začátku“). None = žádný."""
    return db.query(func.min(StavSnapshot.den)).scalar()


def ziv_stav(db: Session) -> dict[int, tuple]:
    """Živý aktuální stav buněk: {bunka_id: (stav, termin)} (jen s vyplněným stavem)."""
    bunky = (
        db.query(Bunka.id, Bunka.stav, Bunka.termin)
        .filter(Bunka.stav.in_(("done", "todo")))
        .all()
    )
    return {b.id: (b.stav, b.termin) for b in bunky}


def snimek_ke_dni(db: Session, cil: date) -> tuple[dict[int, tuple], date | None]:
    """Stav buněk k danému dni z nejbližšího staršího/rovného snímku.

    Vrací ({bunka_id: (stav, termin)}, skutecny_den). Když k datu ani dřív
    žádný snímek není (ptáme se před začátkem sledování), vrátí ({}, None).
    """
    skutecny_den = (
        db.query(func.max(StavSnapshot.den))
        .filter(StavSnapshot.den <= cil)
        .scalar()
    )
    if skutecny_den is None:
        return {}, None
    radky = (
        db.query(StavSnapshot.bunka_id, StavSnapshot.stav, StavSnapshot.termin)
        .filter(StavSnapshot.den == skutecny_den)
        .all()
    )
    return {r.bunka_id: (r.stav, r.termin) for r in radky}, skutecny_den
