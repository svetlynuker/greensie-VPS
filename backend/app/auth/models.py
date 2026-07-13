import enum

from pydantic import BaseModel
from sqlalchemy import Column, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


class Role(str, enum.Enum):
    admin = "admin"
    zamestnanec = "zamestnanec"
    vedeni = "vedeni"


class Skupina(Base):
    """Skupina uživatelů kvůli právům. Definuje se v Admin nastavení.

    `prava` je seznam klíčů z katalogu práv (viz permissions.PRAVA), např.
    ["projekty", "finance", "editace"]. Uživatel dědí práva své skupiny.
    """

    __tablename__ = "skupiny"

    id = Column(Integer, primary_key=True, index=True)
    nazev = Column(String, unique=True, nullable=False)
    prava = Column(ARRAY(String), nullable=False, default=list, server_default="{}")

    clenove = relationship("User", back_populates="skupina")


class User(Base):
    __tablename__ = "uzivatele"

    id = Column(Integer, primary_key=True, index=True)
    jmeno = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    heslo_hash = Column(String, nullable=False)
    role = Column(Enum(Role, name="role"), nullable=False)
    # skupina, do které uživatel patří (dědí její práva). Nepovinné.
    skupina_id = Column(
        Integer, ForeignKey("skupiny.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # individuální výjimky z práv nad rámec skupiny, např. "finance" pro
    # konkrétního zaměstnance (viz Přehled financí v SPEC.md)
    extra_prava = Column(ARRAY(String), nullable=False, default=list, server_default="{}")

    skupina = relationship("Skupina", back_populates="clenove")


class LoginRequest(BaseModel):
    email: str
    heslo: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DlazdiceOut(BaseModel):
    klic: str
    nazev: str
    muze_otevrit: bool  # False = dlaždice se ukáže, ale je zamčená


class UserOut(BaseModel):
    id: int
    jmeno: str
    email: str
    role: Role


class MeOut(BaseModel):
    uzivatel: UserOut
    dlazdice: list[DlazdiceOut]
    muze_editovat: bool  # smí editovat matici (Přehled projektů)
