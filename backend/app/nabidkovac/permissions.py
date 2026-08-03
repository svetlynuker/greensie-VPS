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


def muze_export(user: User) -> bool:
    """Smí uživatel odnést data z appky v souboru?"""
    return muze_otevrit(user, "export")


def vyzaduj_export(user: User = Depends(get_current_user)) -> User:
    """Právo `export` — navíc k právu na modul, ne místo něj.

    Bydlí tady, i když se používá i mimo nabídkovač (CSV seznamů v CRM): je to
    jediné právo na „soubor odchází z appky" a rozkopírovat ho do dvou modulů
    by znamenalo dvě definice téhož, které se časem rozejdou.

    Proč vlastní právo: vidět záznam na obrazovce a odnést si celý seznam
    v souboru jsou dvě různé věci. Kdo má právo na modul, na data se podívat
    smí; jestli si je smí vzít s sebou, je samostatné rozhodnutí.
    """
    if not muze_export(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na export dat nemáš oprávnění.",
        )
    return user
