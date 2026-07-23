"""Zápis do provozního logu konektoru (`konektor_log`).

Best-effort: pokud by zápis selhal, nikdy neshodí vlastní akci (obalený
try/except), stejně jako logy.audit u obecného logu.
"""

from sqlalchemy.orm import Session

from app.konektor.models import MAX_UDALOST, MAX_ZPRAVA, KonektorLog, orez


def zaloguj(
    db: Session,
    uroven: str,
    udalost: str,
    zprava: str,
    kontext: dict | None = None,
) -> None:
    """Zapíše jeden řádek do konektor_log. Chybu potichu spolkne.

    Pozor: `kontext` nesmí obsahovat tajemství ani obsah dokumentů.
    """
    try:
        db.add(
            KonektorLog(
                uroven=uroven,
                udalost=orez(udalost, MAX_UDALOST),
                zprava=orez(zprava, MAX_ZPRAVA) or "",
                kontext=kontext,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - logování nesmí shodit vlastní akci
        db.rollback()
