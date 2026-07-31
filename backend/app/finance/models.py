from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base

# Povolené stavy faktury. Držíme je i tady, aby je backend mohl validovat.
# Barvy/ikony k nim patří na frontend (Pohled 2), tady jen holá pravda o stavu.
STAVY_FAKTURY = ("potreba_vystavit", "vystaveno", "zaplaceno", "nefakturuje")
VYCHOZI_STAV = "potreba_vystavit"
# Kolik prázdných faktur se projektu založí, když ještě žádnou nemá.
VYCHOZI_POCET_FAKTUR = 3

# Předvolené splátkové kalendáře pro fakturaci CRM objednávky (CRM-09).
# Klíč → (popisek, [(název splátky, podíl v procentech), …]). Podíly musí
# dát dohromady 100 – hlídá to test i backend při zakládání.
SPLATKOVE_SABLONY: dict[str, dict] = {
    "jednou": {
        "nazev": "Jednou fakturou (100 %)",
        "splatky": [("Faktura", 100)],
    },
    "50_50": {
        "nazev": "Záloha 50 % + doplatek 50 %",
        "splatky": [("Záloha", 50), ("Doplatek", 50)],
    },
    "30_40_30": {
        "nazev": "30 % záloha + 40 % průběžná + 30 % doplatek",
        "splatky": [("Záloha", 30), ("Průběžná fakturace", 40), ("Doplatek", 30)],
    },
}


class Faktura(Base):
    """Jedna faktura – buď Freelo projektu (Pohled 2), nebo CRM objednávky.

    Na rozdíl od Pohledu 1 nejsou "sloupce" sdílené napříč projekty: každý
    projekt má vlastní seznam faktur (Faktura 1, 2, 3…) a jejich počet se
    může lišit. Sloupec "Faktura N" v tabulce = faktura s poradi=N daného
    projektu.

    DVA MOŽNÍ RODIČE (CRM-09, 31. 7. 2026). Faktura visí buď na `projekt_id`
    (starý svět – projekt z Freela, tabulka `projekty`), nebo na
    `crm_objednavka_id` (nový svět – CRM objednávka). Právě jeden z nich musí
    být vyplněný, hlídá to `ck_faktura_prave_jeden_rodic`.

    Proč jedna tabulka a ne `crm_faktury` zvlášť (rozhodl Dan 31. 7. 2026):
    párování s POHODOU přes variabilní symbol je napsané jednou a Přehled
    financí zůstává jedna obrazovka. Kdyby byly tabulky dvě, mělo by vedení
    peníze na dvou místech a sync by se psal dvakrát.
    """

    __tablename__ = "faktury"
    __table_args__ = (
        # Dřív tu byl UniqueConstraint(projekt_id, poradi). S nullable rodičem
        # by nedělal nic (NULL se v UNIQUE neporovnává), takže se z něj staly
        # dva částečné indexy – jeden pro každý typ rodiče.
        Index(
            "uq_faktura_projekt_poradi",
            "projekt_id",
            "poradi",
            unique=True,
            postgresql_where=text("projekt_id IS NOT NULL"),
        ),
        Index(
            "uq_faktura_objednavka_poradi",
            "crm_objednavka_id",
            "poradi",
            unique=True,
            postgresql_where=text("crm_objednavka_id IS NOT NULL"),
        ),
        CheckConstraint(
            "(projekt_id IS NULL) <> (crm_objednavka_id IS NULL)",
            name="ck_faktura_prave_jeden_rodic",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    projekt_id = Column(
        Integer, ForeignKey("projekty.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Faktura CRM objednávky (nový řetěz objednávka → faktura → zaplaceno).
    crm_objednavka_id = Column(
        Integer, ForeignKey("crm_objednavky.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # 1, 2, 3… = "Faktura 1/2/3" v rámci daného projektu / objednávky
    poradi = Column(Integer, nullable=False, default=1, server_default="1")

    # Popisek splátky („Záloha“, „Doplatek“). U Freelo projektů zůstává prázdný
    # – tam se faktury pojmenovávají pořadím.
    nazev = Column(String, nullable=False, default="", server_default="")
    # Podíl z ceny objednávky v procentech, pokud faktura vznikla ze šablony.
    # Slouží k přepočtu, když se cena objednávky později změní; přepočet je
    # vždy na tlačítko, nikdy automatický (vystavenou fakturu měnit nesmíme).
    podil_procent = Column(Numeric(5, 2), nullable=True)

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
    objednavka = relationship("Objednavka", back_populates="faktury")
