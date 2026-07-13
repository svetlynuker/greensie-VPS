import enum

from pydantic import BaseModel
from sqlalchemy import Column, Enum, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY

from app.database import Base


class Role(str, enum.Enum):
    admin = "admin"
    zamestnanec = "zamestnanec"
    vedeni = "vedeni"


class User(Base):
    __tablename__ = "uzivatele"

    id = Column(Integer, primary_key=True, index=True)
    jmeno = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    heslo_hash = Column(String, nullable=False)
    role = Column(Enum(Role, name="role"), nullable=False)
    # individuální výjimky z práv nad rámec role, např. "financie" pro
    # konkrétního zaměstnance (viz Přehled financí v SPEC.md)
    extra_prava = Column(ARRAY(String), nullable=False, default=list, server_default="{}")


class LoginRequest(BaseModel):
    email: str
    heslo: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DlazdiceOut(BaseModel):
    klic: str
    nazev: str


class UserOut(BaseModel):
    id: int
    jmeno: str
    email: str
    role: Role


class MeOut(BaseModel):
    uzivatel: UserOut
    dlazdice: list[DlazdiceOut]
