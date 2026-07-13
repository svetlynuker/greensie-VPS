from fastapi import Depends, HTTPException, status

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_editovat

# muze_editovat je nově řízené právem "editace" (skupina / výjimka / admin);
# re-export kvůli stávajícím importům v routes.py.
__all__ = ["muze_editovat", "vyzaduj_editora"]


def vyzaduj_editora(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo mají právo editovat matici."""
    if not muze_editovat(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na tuto akci nemáš oprávnění (chybí právo editace).",
        )
    return user
