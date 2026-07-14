"""Práva pro dlaždici Nabídkovač (SPEC-nabidkovac.md, kap. 3).

Nezavádíme žádný nový mechanismus rolí – využíváme existující katalog práv
(auth/permissions.PRAVA), stejně jako to dělá Přehled financí:

- "nabidkovac"          → vidí dlaždici a vytváří/edituje nabídky (OZ, vedení, admin).
- "nabidkovac_katalog"  → edituje katalog technologií a výpočtová nastavení (jen vedení, admin).

"OZ" (obchodní zástupce) = skupina v Admin nastavení s právem "nabidkovac".
"""

from fastapi import Depends, HTTPException, status

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit


def muze_nabidkovac(user: User) -> bool:
    """Smí uživatel používat Nabídkovač (vytvářet/upravovat nabídky)?"""
    return muze_otevrit(user, "nabidkovac")


def muze_katalog(user: User) -> bool:
    """Smí uživatel editovat katalog technologií a výpočtová nastavení?"""
    return muze_otevrit(user, "nabidkovac_katalog")


def vyzaduj_nabidkovac(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo mají právo na Nabídkovač."""
    if not muze_nabidkovac(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Nabídkovač nemáš oprávnění.",
        )
    return user


def vyzaduj_katalog(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí editovat katalog / výpočtová nastavení."""
    if not muze_katalog(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na editaci katalogu a výpočtů nemáš oprávnění (jen vedení/admin).",
        )
    return user
