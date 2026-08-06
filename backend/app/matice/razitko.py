"""Podpis stavu matice — z něj prohlížeč pozná, že se něco změnilo.

Proč podpis a ne seznam rozdílů: matice má řádově stovky buněk, takže její
načtení je jeden malý dotaz. Počítat na serveru „co přesně se změnilo od času
X“ by znamenalo držet historii změn a testovat ji — a při první nepřesnosti
by lidem tiše chyběla aktualizace. Podpis je tupý, ale nemůže lhát: když se
liší, klient si prostě natáhne matici znovu.
"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.matice.models import Bunka, Projekt, Sloupec


def oznac_zmenu(obj, uzivatel_id: int | None = None) -> None:
    """Zapíše na záznam „kdy a kdo“ a posune verzi.

    Volá se u KAŽDÉ změny, která má být vidět ostatním — včetně synchronizace
    z Freela. Kdyby to Freelo přeskočilo, razítko by se nezměnilo a lidé by
    koukali na stará data, dokud stránku sami neobnoví.
    """
    obj.zmeneno_at = datetime.now(timezone.utc)
    if hasattr(obj, "zmenil_id"):
        obj.zmenil_id = uzivatel_id
    if hasattr(obj, "verze"):
        obj.verze = (obj.verze or 0) + 1


def razitko_matice(db: Session) -> str:
    """Krátký text, který se změní při jakékoli změně obsahu matice.

    Kromě času poslední změny jsou v podpisu i počty řádků — smazání projektu
    ani úbytek buněk čas poslední změny neposune (smazaný řádek už nikde
    není), takže samotný čas by na ně byl slepý.
    """
    posledni_bunka = db.query(func.max(Bunka.zmeneno_at)).scalar()
    posledni_projekt = db.query(func.max(Projekt.zmeneno_at)).scalar()
    casy = [c for c in (posledni_bunka, posledni_projekt) if c is not None]
    posledni = max(casy).isoformat() if casy else "-"

    return "|".join(
        [
            posledni,
            str(db.query(func.count(Bunka.id)).scalar() or 0),
            str(db.query(func.count(Projekt.id)).scalar() or 0),
            str(db.query(func.count(Sloupec.id)).scalar() or 0),
        ]
    )
