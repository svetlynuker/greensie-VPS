from fastapi import Depends, HTTPException, status

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_editovat, muze_otevrit

# muze_editovat je nově řízené právem "editace" (skupina / výjimka / admin);
# re-export kvůli stávajícím importům v routes.py.
__all__ = ["muze_editovat", "vyzaduj_editora", "vyzaduj_projekty"]


def vyzaduj_projekty(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí otevřít Přehled projektů (právo `projekty`).

    Čtení matice bylo dřív jen za přihlášením, zatímco dlaždice i položka
    v nabídce se schovávaly za právem `projekty`. Kdo právo neměl, matici si
    stejně přečetl zadáním adresy — schovaná nabídka není kontrola přístupu.
    """
    if not muze_otevrit(user, "projekty"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Přehled projektů nemáš oprávnění.",
        )
    return user


def vyzaduj_editora(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo mají právo editovat matici."""
    if not muze_editovat(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na tuto akci nemáš oprávnění (chybí právo editace).",
        )
    return user
