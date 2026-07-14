from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base

# Povolené stavy faktury. Držíme je i tady, aby je backend mohl validovat.
# Barvy/ikony k nim patří na frontend (Pohled 2), tady jen holá pravda o stavu.
STAVY_FAKTURY = ("potreba_vystavit", "vystaveno", "zaplaceno", "nefakturuje")
VYCHOZI_STAV = "potreba_vystavit"
# Kolik prázdných faktur se projektu založí, když ještě žádnou nemá.
VYCHOZI_POCET_FAKTUR = 3


class Faktura(Base):
    """Jedna faktura jednoho projektu (Pohled 2 – Přehled financí).

    Na rozdíl od Pohledu 1 nejsou "sloupce" sdílené napříč projekty: každý
    projekt má vlastní seznam faktur (Faktura 1, 2, 3…) a jejich počet se
    může lišit. Sloupec "Faktura N" v tabulce = faktura s poradi=N daného
    projektu.

    Vztah na Projekt (tabulka `projekty` z modulu matice) je definovaný jen
    tady – do Pohledu 1 se finance záměrně nemíchají.
    """

    __tablename__ = "faktury"
    __table_args__ = (
        UniqueConstraint("projekt_id", "poradi", name="uq_faktura_projekt_poradi"),
    )

    id = Column(Integer, primary_key=True, index=True)
    projekt_id = Column(
        Integer, ForeignKey("projekty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 1, 2, 3… = "Faktura 1/2/3" v rámci daného projektu
    poradi = Column(Integer, nullable=False, default=1, server_default="1")

    stav = Column(String, nullable=False, default=VYCHOZI_STAV, server_default=VYCHOZI_STAV)
    castka = Column(Numeric(12, 2), nullable=True)
    termin = Column(Date, nullable=True)
    poznamka = Column(Text, nullable=False, default="", server_default="")

    # Párovací klíč na Pohodu – tentýž variabilní/specifický symbol, který se
    # ručně zapisuje do Freela. Přes shodu VS spárujeme fakturu z Pohody.
    variabilni_symbol = Column(String, nullable=True, index=True)

    # Odkaz na fázi/úkol ve Freelu, který fakturu "spouští" (např. podpis SOD).
    # Přesná pravidla se dolaďují iterativně, viz finance/pravidla.py.
    freelo_faze = Column(String, nullable=True)
    freelo_task_id = Column(Integer, nullable=True)

    # Co potvrdila Pohoda (napojení zatím není aktivní – plní se až po sync).
    pohoda_potvrzeno = Column(Boolean, nullable=False, default=False, server_default="false")
    pohoda_datum_vystaveni = Column(Date, nullable=True)
    pohoda_datum_zaplaceni = Column(Date, nullable=True)

    # True = stav byl ručně upraven v appce → má přednost před automatikou
    # (Freelo/Pohoda). Stejný princip jako upraveno_rucne u buněk Pohledu 1.
    upraveno_rucne = Column(Boolean, nullable=False, default=False, server_default="false")

    projekt = relationship("Projekt")
