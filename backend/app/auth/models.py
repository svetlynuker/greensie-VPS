from pydantic import BaseModel
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship

from app.database import Base


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
    # supersprávce = plný přístup ke všemu (nelze se vyřadit z Admin nastavení)
    je_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    # po vytvoření / resetu hesla si uživatel musí při přihlášení zvolit nové
    musi_zmenit_heslo = Column(Boolean, nullable=False, default=False, server_default="false")
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
    je_admin: bool = False


class MeOut(BaseModel):
    uzivatel: UserOut
    dlazdice: list[DlazdiceOut]
    muze_editovat: bool  # smí editovat matici (Přehled projektů)
    prava: list[str] = []  # efektivní práva uživatele (klíče z permissions.PRAVA)
    musi_zmenit_heslo: bool = False


class ZmenaHeslaVstup(BaseModel):
    nove_heslo: str
