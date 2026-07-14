from fastapi import Depends, HTTPException, status

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit

# Přehled financí vidí jen Rosťa + skupina "vedení". Řídí to existující právo
# "finance" (viz auth/permissions.PRAVA) – přiděluje se skupině nebo jako
# individuální výjimka uživateli. Žádný nový mechanismus se nezavádí.


def muze_finance(user: User) -> bool:
    """Smí uživatel vidět/editovat Přehled financí?"""
    return muze_otevrit(user, "finance")


def vyzaduj_finance(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo mají právo na Přehled financí."""
    if not muze_finance(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Přehled financí nemáš oprávnění.",
        )
    return user
