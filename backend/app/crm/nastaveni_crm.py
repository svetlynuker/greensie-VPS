"""Firemní nastavení CRM (jeden řádek).

Oddělené od uživatelských nastavení schválně: tohle jsou údaje FIRMY (naše
adresa), které vidí a mění vedení, ne osobní volby jednotlivce.
"""

from sqlalchemy.orm import Session

from app.crm.models import CrmNastaveni


def nacti(db: Session) -> CrmNastaveni:
    """Vrátí konfigurační řádek; když ještě není, vyrobí ho.

    Díky tomu nemusí volající řešit „co když je tabulka prázdná" a nastavení
    nepotřebuje seed při startu appky.
    """
    n = db.get(CrmNastaveni, 1)
    if n is None:
        n = CrmNastaveni(id=1, nase_adresa="")
        db.add(n)
        db.commit()
        db.refresh(n)
    return n
