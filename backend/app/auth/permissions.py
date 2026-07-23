import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.auth.models import DlazdiceOut, User
from app.database import get_db

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_heslo(heslo: str) -> str:
    return pwd_context.hash(heslo)


# Znaky bez záměnných dvojic (0/O, 1/l/I) kvůli čitelnosti jednorázového hesla.
_HESLO_ZNAKY = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def vygeneruj_heslo(delka: int = 10) -> str:
    """Vytvoří náhodné jednorázové heslo (pro nové uživatele / reset)."""
    return "".join(secrets.choice(_HESLO_ZNAKY) for _ in range(delka))


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


# ---- Katalog dlaždic a práv ----
# Dlaždice = položky rozcestníku. Uvidí je VŽDY všichni; jestli je uživatel
# smí OTEVŘÍT, řídí právo se stejným klíčem (viz muze_otevrit).
DLAZDICE = [
    {"klic": "projekty", "nazev": "Přehled projektů"},
    {"klic": "finance", "nazev": "Přehled financí"},
    {"klic": "zmeny", "nazev": "Přehled změn"},
    {"klic": "nabidkovac", "nazev": "Nabídkovač"},
    {"klic": "admin", "nazev": "Admin nastavení"},
    {"klic": "logy", "nazev": "Logy"},
    {"klic": "konektor", "nazev": "Konektor Raynet ↔ Disk"},
]

# Katalog přidělitelných práv (skupinám i jednotlivcům). Otevírací práva mají
# stejný klíč jako dlaždice; ostatní jsou akční práva.
#
# Role OZ (obchodní zástupce) se do stávajícího modelu zavádí BEZ nového
# konceptu role: "OZ" je běžná skupina (Admin nastavení) s právem
# "nabidkovac". Úprava katalogu technologií a výpočtových nastavení je pod
# samostatným právem "nabidkovac_katalog" (jen vedení/admin). Stejný princip
# jako u "finance" – nic v existujících pohledech se nemění.
PRAVA = [
    {"klic": "projekty", "nazev": "Otevřít Přehled projektů"},
    {"klic": "finance", "nazev": "Otevřít Přehled financí"},
    {"klic": "zmeny", "nazev": "Otevřít Přehled změn"},
    {"klic": "nabidkovac", "nazev": "Nabídkovač – vytvářet/upravovat nabídky (OZ)"},
    {"klic": "nabidkovac_katalog", "nazev": "Nabídkovač – editace katalogu a výpočtů (vedení)"},
    {"klic": "admin", "nazev": "Otevřít Admin nastavení"},
    {"klic": "editace", "nazev": "Editace matice (Přehled projektů)"},
    {"klic": "logy", "nazev": "Otevřít Logy (provoz, chyby, audit)"},
    {"klic": "konektor", "nazev": "Otevřít Konektor Raynet ↔ Google Drive (nastavení, logy)"},
]

VSECHNA_PRAVA = {p["klic"] for p in PRAVA}


def prava_uzivatele(user: User) -> set[str]:
    """Efektivní práva uživatele: supersprávce má vše, jinak skupina + výjimky."""
    if user.je_admin:
        return set(VSECHNA_PRAVA)
    prava = set(user.extra_prava or [])
    if user.skupina is not None:
        prava |= set(user.skupina.prava or [])
    return prava


def muze_otevrit(user: User, klic: str) -> bool:
    """Smí uživatel otevřít danou dlaždici?"""
    return klic in prava_uzivatele(user)


def muze_editovat(user: User) -> bool:
    """Smí uživatel editovat matici (Přehled projektů)?"""
    return "editace" in prava_uzivatele(user)


def dlazdice_pro(user: User) -> list[DlazdiceOut]:
    """Všechny dlaždice + příznak, zda je uživatel smí otevřít."""
    prava = prava_uzivatele(user)
    return [
        DlazdiceOut(klic=d["klic"], nazev=d["nazev"], muze_otevrit=d["klic"] in prava)
        for d in DLAZDICE
    ]


def vyzaduj_admina(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí otevřít Admin nastavení."""
    if not muze_otevrit(user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Admin nastavení nemáš oprávnění.",
        )
    return user
