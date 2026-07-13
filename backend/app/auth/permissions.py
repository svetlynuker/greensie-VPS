import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.auth.models import DlazdiceOut, Role, User
from app.database import get_db

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_heslo(heslo: str) -> str:
    return pwd_context.hash(heslo)


def over_heslo(heslo: str, heslo_hash: str) -> bool:
    return pwd_context.verify(heslo, heslo_hash)


def vytvor_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    chyba_prihlaseni = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Neplatné nebo vypršelé přihlášení",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise chyba_prihlaseni
    except JWTError:
        raise chyba_prihlaseni

    user = db.get(User, int(user_id))
    if user is None:
        raise chyba_prihlaseni
    return user


# ---- Dlaždice rozcestníku a kdo je smí vidět ----
# "role": None znamená, že dlaždici vidí kdokoliv přihlášený.
# "extra_pravo": klíč v poli extra_prava uživatele, který dává přístup i mimo roli.
TILES = [
    {"klic": "projekty", "nazev": "Přehled projektů", "role": None, "extra_pravo": None},
    {"klic": "finance", "nazev": "Přehled financí", "role": Role.vedeni, "extra_pravo": "financie"},
    {"klic": "zmeny", "nazev": "Přehled změn", "role": None, "extra_pravo": None},
]


def muze_videt_dlazdici(user: User, dlazdice: dict) -> bool:
    if dlazdice["role"] is None:
        return True
    if user.role == dlazdice["role"]:
        return True
    if dlazdice["extra_pravo"] and dlazdice["extra_pravo"] in (user.extra_prava or []):
        return True
    return False


def viditelne_dlazdice(user: User) -> list[DlazdiceOut]:
    return [
        DlazdiceOut(klic=d["klic"], nazev=d["nazev"])
        for d in TILES
        if muze_videt_dlazdici(user, d)
    ]
