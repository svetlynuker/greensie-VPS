from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Projekt(Base):
    __tablename__ = "projekty"

    id = Column(Integer, primary_key=True, index=True)
    freelo_id = Column(Integer, unique=True, nullable=True, index=True)
    nazev = Column(String, nullable=False)
    url = Column(String, nullable=False, default="", server_default="")
    termin = Column(Date, nullable=True)
    rucni = Column(Boolean, nullable=False, default=False, server_default="false")
    skryty = Column(Boolean, nullable=False, default=False, server_default="false")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    bunky = relationship("Bunka", back_populates="projekt", cascade="all, delete-orphan")


class Sloupec(Base):
    __tablename__ = "sloupce"

    id = Column(Integer, primary_key=True, index=True)
    label = Column(String, unique=True, nullable=False, index=True)
    faze = Column(String, nullable=False, default="", server_default="")
    nazev = Column(String, nullable=False)
    rucni = Column(Boolean, nullable=False, default=False, server_default="false")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    bunky = relationship("Bunka", back_populates="sloupec", cascade="all, delete-orphan")


class Bunka(Base):
    __tablename__ = "bunky"
    __table_args__ = (UniqueConstraint("projekt_id", "sloupec_id", name="uq_bunka_projekt_sloupec"),)

    id = Column(Integer, primary_key=True, index=True)
    projekt_id = Column(Integer, ForeignKey("projekty.id", ondelete="CASCADE"), nullable=False, index=True)
    sloupec_id = Column(Integer, ForeignKey("sloupce.id", ondelete="CASCADE"), nullable=False, index=True)

    stav = Column(String, nullable=True)  # "done" | "todo" | None
    termin = Column(Date, nullable=True)
    osoba = Column(String, nullable=False, default="", server_default="")
    poznamka = Column(Text, nullable=False, default="", server_default="")
    url = Column(String, nullable=False, default="", server_default="")
    freelo_task_id = Column(Integer, nullable=True)
    # True = buňka byla ručně upravena v appce → má přednost při načtení z Freela
    upraveno_rucne = Column(Boolean, nullable=False, default=False, server_default="false")

    projekt = relationship("Projekt", back_populates="bunky")
    sloupec = relationship("Sloupec", back_populates="bunky")


class NastaveniBarev(Base):
    """Globální prahy barevných úrovní termínů (jeden řádek, id=1).

    Konvence dnů: d = dnes - termín. Záporné = před termínem, kladné = po termínu.
    Každá úroveň má od/do (včetně); None = otevřený konec.
    Výchozí hodnoty odpovídají původní logice prototypu.
    """

    __tablename__ = "nastaveni_barev"

    id = Column(Integer, primary_key=True)
    # v termínu (zelená): d <= zelena_do
    zelena_od = Column(Integer, nullable=True, default=None)
    zelena_do = Column(Integer, nullable=True, default=-4)
    # blíží se (žlutá)
    zluta_od = Column(Integer, nullable=True, default=-3)
    zluta_do = Column(Integer, nullable=True, default=0)
    # po termínu (oranžová)
    oranzova_od = Column(Integer, nullable=True, default=1)
    oranzova_do = Column(Integer, nullable=True, default=3)
    # hodně po (červená): d >= cervena_od
    cervena_od = Column(Integer, nullable=True, default=4)
    cervena_do = Column(Integer, nullable=True, default=None)


class NastaveniSynchronizace(Base):
    """Globální nastavení automatické synchronizace z Freela (jeden řádek, id=1).

    Určuje, zda a jak často server sám stahuje data z Freela a která pole
    buněk se při synchronizaci přepisují. Zapnuté pole = Freelo vyhrává a
    přepíše i ručně zadanou hodnotu; vypnuté pole zůstane beze změny.
    Poznámka (`poznamka` na buňce) se nepřepisuje NIKDY.
    """

    __tablename__ = "nastaveni_synchronizace"

    id = Column(Integer, primary_key=True)
    # plánovaná synchronizace na serveru
    auto_zapnuto = Column(Boolean, nullable=False, default=True, server_default="true")
    interval_min = Column(Integer, nullable=False, default=60, server_default="60")
    # co se synchronizuje (Freelo → tabulka)
    sync_stav = Column(Boolean, nullable=False, default=True, server_default="true")
    # obousměrně: zápis změny stavu z tabulky zpět do Freela (tabulka → Freelo)
    zapis_stav_do_freela = Column(Boolean, nullable=False, default=True, server_default="true")
    sync_nove_ukoly = Column(Boolean, nullable=False, default=True, server_default="true")
    sync_nove_projekty = Column(Boolean, nullable=False, default=True, server_default="true")
    sync_terminy = Column(Boolean, nullable=False, default=False, server_default="false")
    sync_osoby = Column(Boolean, nullable=False, default=False, server_default="false")
    # informativní stav posledního běhu
    posledni_beh = Column(DateTime, nullable=True)
    posledni_vysledek = Column(Text, nullable=False, default="", server_default="")
