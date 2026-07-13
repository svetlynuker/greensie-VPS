from typing import Optional

from pydantic import BaseModel

from app.auth.models import Role


class PravoOut(BaseModel):
    klic: str
    nazev: str


class CiselnikyOut(BaseModel):
    prava: list[PravoOut]
    role: list[str]


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
    role: Role
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []


class UzivatelVstup(BaseModel):
    jmeno: str
    email: str
    heslo: str
    role: Role = Role.zamestnanec
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []


class UzivatelUprava(BaseModel):
    jmeno: str
    email: str
    role: Role
    skupina_id: Optional[int] = None
    extra_prava: list[str] = []
    # nové heslo – nepovinné; prázdné = neměnit
    heslo: Optional[str] = None
