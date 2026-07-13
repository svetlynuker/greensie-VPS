from fastapi import Depends, HTTPException, status

from app.auth.models import Role, User
from app.auth.permissions import get_current_user

ROLE_EDITORU = {Role.admin, Role.vedeni}


def muze_editovat(user: User) -> bool:
    return user.role in ROLE_EDITORU


def vyzaduj_editora(user: User = Depends(get_current_user)) -> User:
    """Povolí jen adminy a vedení – editace matice a nastavení barev."""
    if not muze_editovat(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na tuto akci nemáš oprávnění (jen admin nebo vedení).",
        )
    return user
