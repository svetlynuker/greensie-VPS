from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, func
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
    profil = relationship(
        "UzivatelProfil", back_populates="uzivatel", uselist=False,
        cascade="all, delete-orphan",
    )


class UzivatelProfil(Base):
    """Osobní údaje pro **e-mailový podpis** – jeden řádek na uživatele.

    ---- Proč vlastní tabulka a ne sloupce v `uzivatele` -------------------
    Kvůli `User.jmeno`. To drží **celé jméno** („Daniel Lupínek") a zobrazuje se
    napříč celou appkou – v liště, u vlastníků záznamů, v iniciálách. Kdybych
    vedle něj přidal `prijmeni`, význam `jmeno` by se tiše změnil na „křestní"
    a všude by se začalo ukazovat půl jména. Profil je proto vedle: `jmeno` tady
    je křestní, `User.jmeno` zůstává celé a nikdo se nemusí dohadovat, které je které.

    ---- Co je povinné ----------------------------------------------------
    Nic. Prázdný profil znamená „podpis se negeneruje" – appka pak spadne zpět
    na prostý textový podpis u schránky. `funkce` je volitelná i při vyplněném
    profilu: bez ní se podpis vykreslí bez řádku s funkcí (rozhodnutí Dana,
    1. 8. 2026), ne s prázdným místem.
    """

    __tablename__ = "uzivatel_profil"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("uzivatele.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Křestní jméno a příjmení zvlášť: podpis je skládá jinak než appka
    # (a z nich se odvozuje i pracovní adresa jmeno.prijmeni@greensie.cz).
    jmeno = Column(String, nullable=False, default="", server_default="")
    prijmeni = Column(String, nullable=False, default="", server_default="")
    # Devět číslic bez předvolby; „+420" se doplňuje až při vykreslení.
    telefon = Column(String, nullable=False, default="", server_default="")
    # Volitelná. Prázdná = podpis bez řádku s funkcí.
    funkce = Column(String, nullable=False, default="", server_default="")

    # Úvodní pozdrav nad podpisem. Prázdný = bez pozdravu; šablona ho má jako
    # přepínač, tady stačí prázdné pole (jedno políčko místo dvou).
    pozdrav = Column(String, nullable=False, default="S pozdravem", server_default="S pozdravem")
    # Vypnutý podpis = odchozí pošta jede bez něj (a použije se textový podpis
    # u schránky, pokud je vyplněný).
    podpis_zapnuty = Column(Boolean, nullable=False, default=True, server_default="true")

    upraveno_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    uzivatel = relationship("User", back_populates="profil")


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
    # název skupiny, do které uživatel patří — ukazuje se u jeho jména v liště
    skupina: str | None = None


class MeOut(BaseModel):
    uzivatel: UserOut
    dlazdice: list[DlazdiceOut]
    muze_editovat: bool  # smí editovat matici (Přehled projektů)
    prava: list[str] = []  # efektivní práva uživatele (klíče z permissions.PRAVA)
    musi_zmenit_heslo: bool = False


class ZmenaHeslaVstup(BaseModel):
    nove_heslo: str


class ProfilVstup(BaseModel):
    """Karta „Podpis do e-mailu" v osobním nastavení.

    Nic není povinné. Prázdné jméno = podpis se negeneruje, `funkce` je
    volitelná i u vyplněného profilu (podpis pak nemá řádek s funkcí).
    """

    jmeno: str = ""
    prijmeni: str = ""
    telefon: str = ""
    funkce: str = ""
    pozdrav: str = "S pozdravem"
    podpis_zapnuty: bool = True


class ProfilOut(BaseModel):
    jmeno: str = ""
    prijmeni: str = ""
    # Devět číslic bez předvolby, tak jak se ukládají.
    telefon: str = ""
    funkce: str = ""
    pozdrav: str = ""
    podpis_zapnuty: bool = True
    # Spočtené hodnoty pro UI – ať je frontend nemusí odvozovat podruhé.
    podpis_html: str = ""
    podpis_text: str = ""
    # „Takhle by tvoje pracovní adresa měla vypadat" – jen nápověda.
    navrh_adresy: str = ""
    # Adresa, která se v podpisu opravdu použije (schránka, nebo účet appky).
    adresa_v_podpisu: str = ""
    # Je profil dost vyplněný na to, aby podpis vznikl?
    pripraveny: bool = False
