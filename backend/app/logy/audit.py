"""Ruční zápis do auditního logu pro vybrané akce.

Většinu událostí zaznamená automaticky middleware (viz logy.middleware).
Tento pomocník je pro případy, kdy middleware nezná potřebný kontext –
typicky přihlášení, kde uživatel v tokenu ještě není (token teprve vzniká).

Zápis je „best-effort“: pokud by se nepovedl, akci nikdy neshodí (obalený
try/except), protože logování nesmí rozbít vlastní funkci aplikace.
"""

from sqlalchemy.orm import Session

from app.logy.models import vytvor_zaznam


def zaznamenej_audit(
    db: Session,
    popis: str,
    *,
    uzivatel_id: int | None = None,
    uzivatel_email: str | None = None,
    metoda: str | None = None,
    cesta: str | None = None,
    status_kod: int | None = None,
) -> None:
    """Zapíše jeden auditní záznam s čitelným popisem. Chybu potichu spolkne."""
    try:
        db.add(
            vytvor_zaznam(
                typ="audit",
                popis=popis,
                uzivatel_id=uzivatel_id,
                uzivatel_email=uzivatel_email,
                metoda=metoda,
                cesta=cesta,
                status_kod=status_kod,
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - logování nesmí shodit vlastní akci
        db.rollback()
