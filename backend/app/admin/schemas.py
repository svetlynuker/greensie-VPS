from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PravoOut(BaseModel):
    klic: str
    nazev: str


class CiselnikyOut(BaseModel):
    prava: list[PravoOut]


class SkupinaOut(BaseModel):
    id: int
    nazev: str
    prava: list[str]
    pocet_clenu: int = 0


class SkupinaVstup(BaseModel):
    nazev: str
    prava: list[str] = []


class UzivatelOut(BaseModel):
    id: int
    jmeno: str
    email: str
    je_admin: bool = False
    musi_zmenit_heslo: bool = False
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []
    # čas posledního úspěšného přihlášení; None = ještě se nikdy nepřihlásil
    posledni_prihlaseni: Optional[datetime] = None


class UzivatelVstup(BaseModel):
    jmeno: str
    email: str
    je_admin: bool = False
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []


class UzivatelUprava(BaseModel):
    jmeno: str
    email: str
    je_admin: bool = False
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []


class ResetHeslaVstup(BaseModel):
    # když je vyplněné, nastaví se přímo; jinak se vygeneruje náhodné
    nove_heslo: Optional[str] = None


class HesloVysledek(BaseModel):
    """Odpověď po vytvoření uživatele / resetu hesla."""

    uzivatel: UzivatelOut
    heslo: str  # jednorázové heslo k zobrazení adminovi
    email_odeslan: bool = False
    email_poznamka: Optional[str] = None


class PrihlaseniOut(BaseModel):
    """Jeden řádek historie přihlášení."""

    id: int
    cas: datetime
    uzivatel_id: Optional[int] = None
    uzivatel_email: Optional[str] = None
    uzivatel_jmeno: Optional[str] = None
    uspech: bool = False
    duvod: Optional[str] = None
    ip: Optional[str] = None
    zarizeni: Optional[str] = None

    model_config = {"from_attributes": True}


class PrihlaseniPrehled(BaseModel):
    """Historie přihlášení i s krátkým souhrnem nad hlavičkou tabulky."""

    zaznamy: list[PrihlaseniOut] = []
    neuspechy_24h: int = 0
