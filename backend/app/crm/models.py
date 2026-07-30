"""Datový model CRM: Zákazníci → Obchodní případy → (Nabídky → Objednávky → Projekty).

Proč vlastní modul a ne rozšíření nabídkovače: nabídkovač je *výpočetní*
nástroj (sizing, ROI, tisk). CRM je evidence, do které nabídka patří jako
jeden z artefaktů obchodního případu. Držíme to oddělené, aby se výpočty
daly měnit bez zásahu do evidence a naopak.

KOEXISTENCE S RAYNETEM (rozhodnutí Dana, 30. 7. 2026): appka Raynet postupně
nahradí, ale zatím běží obojí. Proto každá entita, která má v Raynetu
protějšek, nese `raynet_id` a případy navíc `raynet_code`. Důvod není
„pro pořádek": na Raynetí čísle obchodního případu (`code`, např. OP-26-0223)
stojí dva existující mechanismy – konektor podle něj pojmenovává složky na
Google Disku a `matice/disk_parovani.py` podle něj páruje Freelo projekty
s jejich složkou dokumentů. Kdyby appka Raynetí číslo zahodila a nahradila
vlastním, obojí by se rozbilo. Vlastní číslo appky (`cislo`) a Raynetí číslo
(`raynet_code`) tedy žijí vedle sebe; párování na Disk vždy používá to
Raynetí, dokud Raynet nezmizí.

PRÁVA NA ZÁZNAMY: každá entita má `vlastnik_user_id` + `spoluvlastnici`.
Kdo nemá právo `crm_vse`, vidí jen záznamy, kde je vlastníkem nebo
spoluvlastníkem (viz `crm/pristup.py`). Žádná hierarchie rolí se nezavádí –
„vedení vidí vše" = skupina s právem `crm_vse`.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship

from app.database import Base

# ---- Povolené hodnoty enumů -------------------------------------------------

# Zákazník je JEDEN záznam se příznakem, ne dvě tabulky. Konverze leadu na
# klienta je změna příznaku – kdyby to byly dvě tabulky, konverze by znamenala
# kopii záznamu a ztrátu vazeb (aktivity, případy) na původní lead.
TYPY_ZAKAZNIKA = ("lead", "klient")

# Entity, které mají číselnou řadu, konfigurovatelné stavy a kanban.
# Držíme je jako klíče, protože stavy i řady jsou generické tabulky (jedna
# tabulka pro všechny entity), ne čtyři téměř identické.
ENTITY_CRM = ("op", "nab", "obj", "pro")

# Entity, ke kterým lze psát aktivity/poznámky (zákazník i případ).
ENTITY_AKTIVIT = ("zakaznik", "op", "nab", "obj", "pro")

# Druh stavu řídí chování kanbanu a statistik: otevřený = počítá se do
# pipeline, výhra/prohra = uzavírá případ (a u prohry se ptáme na důvod).
DRUHY_STAVU = ("otevreny", "vyhra", "prohra")

# Kategorie obchodního případu = do kterého nabídkového okna případ směřuje.
# Schválně SEZNAM, ne jedna hodnota: případ může mít PPA i peak shaving
# současně (a právě z toho vznikne kombinovaná nabídka).
KATEGORIE_OP = ("prodej", "ppa", "peak_shaving")

# Druhy aktivit (Raynet-like log práce s zákazníkem).
DRUHY_AKTIVITY = ("poznamka", "telefon", "email", "schuzka", "ukol")

# Obrazovky, na které smí admin přidávat vlastní pole. Rozšíření o další
# entitu = přidat klíč sem a její model do `vlastni_pole.MODELY` (entita musí
# mít sloupec `extra`).
ENTITY_VLASTNICH_POLI = ("zakaznik", "op")

# Datový typ vlastního pole. Dan chtěl „textová pole"; typy navíc stojí skoro
# nic a ušetří pozdější práci (datum se dá řadit, ano/ne filtrovat, výběr
# nepustí do dat překlepy).
TYPY_VLASTNIHO_POLE = ("text", "dlouhy_text", "cislo", "datum", "ano_ne", "vyber")


class CiselnaRada(Base):
    """Číselná řada viditelných ID: OP-26-0301, NAB-26-0007…

    Jeden řádek na (entita, rok) – řada se každý rok sama restartuje, protože
    rok je součástí klíče i formátu čísla. `dalsi_cislo` se posouvá atomicky
    (SELECT … FOR UPDATE, viz `ciselne_rady.py`), takže dva OZ zakládající
    případ ve stejnou sekundu nedostanou stejné číslo.

    `sirka` je nastavitelná schválně: Raynet čísluje na čtyři místa
    (OP-26-0223). Kdyby appka začala od OP-26-001, vznikla by dvě různá čísla
    se stejným prefixem a člověk by netušil, které je které. Proto default 4
    a `dalsi_cislo` se dá v nastavení posunout nad nejvyšší Raynetí číslo.
    """

    __tablename__ = "crm_ciselne_rady"
    __table_args__ = (UniqueConstraint("entita", "rok", name="uq_crm_rada_entita_rok"),)

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)  # jedna z ENTITY_CRM
    rok = Column(Integer, nullable=False)  # dvojčíslí roku (26 = 2026)
    prefix = Column(String, nullable=False)  # "OP" / "NAB" / "OBJ" / "PRO"
    sirka = Column(Integer, nullable=False, default=4, server_default="4")
    dalsi_cislo = Column(Integer, nullable=False, default=1, server_default="1")
    # Od jakého čísla řada začala. Bez tohohle by u řady posunuté kvůli Raynetu
    # (start 301) vypadalo, že už vydala 300 čísel – a nikdo by nepoznal, jestli
    # se start ještě smí měnit.
    pocatek = Column(Integer, nullable=False, default=1, server_default="1")

    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmStav(Base):
    """Stav entity v pipeline – konfigurovatelný, ne zadrátovaný v kódu.

    Kanban vykresluje sloupce právě podle těchto řádků (`poradi`), takže
    přidání fáze je práce pro vedení v nastavení, ne pro programátora.
    `druh` rozlišuje otevřené stavy od výhry/prohry; u prohry se pak vynucuje
    důvod, jinak by statistika pipeline nedávala smysl.
    """

    __tablename__ = "crm_stavy"
    __table_args__ = (UniqueConstraint("entita", "klic", name="uq_crm_stav_entita_klic"),)

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)  # jedna z ENTITY_CRM
    klic = Column(String, nullable=False)  # strojový klíč (neměnný, drží se v záznamech)
    nazev = Column(String, nullable=False)  # co vidí člověk ve kanbanu
    poradi = Column(Integer, nullable=False, default=0, server_default="0")
    barva = Column(String, nullable=False, default="", server_default="")  # token nebo hex
    druh = Column(String, nullable=False, default="otevreny", server_default="otevreny")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrmStavHistorie(Base):
    """Kdo, kdy a odkud kam přesunul záznam v kanbanu.

    Jedna generická tabulka pro všechny entity (`entita` + `zaznam_id`), ne
    čtyři téměř stejné. Bez téhle historie by nešlo zjistit, jak dlouho případ
    visel v které fázi – a to je hlavní analytická hodnota pipeline. Aktuální
    stav je v samotném záznamu, tady je jen jeho dráha.
    """

    __tablename__ = "crm_stav_historie"

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)
    zaznam_id = Column(Integer, nullable=False, index=True)
    ze_stavu = Column(String, nullable=True)  # NULL = založení záznamu
    do_stavu = Column(String, nullable=False)
    zmenil_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    zmeneno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    zmenil = relationship("User")


class CrmVlastniPole(Base):
    """Vlastní (admin definované) pole na obrazovce – bez zásahu do kódu.

    Vzniklo z reálné potřeby: „rozhodneme se sledovat parametr, který dnes
    nepotřebuju". Přidání sloupce do schématu by znamenalo migraci a nasazení,
    takže se to řeší stejně jako vlastní sloupce katalogu technologií
    (`KatalogSloupec`): DEFINICE pole žije tady, HODNOTY v JSONB `extra` daného
    záznamu pod klíčem `klic`.

    `klic` je strojový, odvozený z názvu a **neměnný** – drží ho uložené
    hodnoty, takže jeho změnou by se data odpojila. Přejmenovat se dá `nazev`.

    Smazání pole hodnoty **nemaže**, jen je přestane zobrazovat: osiřelé klíče
    v JSONB nevadí a omylem smazané pole se dá vrátit, aniž by data zmizela.
    """

    __tablename__ = "crm_vlastni_pole"
    __table_args__ = (
        UniqueConstraint("entita", "klic", name="uq_crm_vlastni_pole_entita_klic"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)  # ENTITY_VLASTNICH_POLI
    klic = Column(String, nullable=False)
    nazev = Column(String, nullable=False)
    typ = Column(String, nullable=False, default="text", server_default="text")
    # Volby pro typ `vyber` (pořadí = pořadí v rozbalovací nabídce).
    volby = Column(ARRAY(String), nullable=False, default=list, server_default="{}")
    napoveda = Column(String, nullable=False, default="", server_default="")
    povinne = Column(Boolean, nullable=False, default=False, server_default="false")
    # Ukázat i jako sloupec v seznamu/tabulce, ne jen v detailu záznamu.
    v_seznamu = Column(Boolean, nullable=False, default=False, server_default="false")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )


class Zakaznik(Base):
    """Lead nebo klient – jeden záznam, `typ` rozhoduje, v kterém pohledu je.

    `konvertovan_at` drží okamžik, kdy se z leadu stal klient (typicky při
    první výhře obchodního případu). Historie leadu tím zůstává, protože se
    záznam nekopíruje.
    """

    __tablename__ = "crm_zakaznici"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False, default="lead", server_default="lead", index=True)

    nazev = Column(String, nullable=False)
    # IČO se needituje na unikátní: smí být prázdné (lead bez IČO) a duplicitu
    # řešíme varováním při zakládání, ne tvrdým zákazem (dvě provozovny,
    # přejmenovaná firma…). Index je kvůli hledání duplicit a ARES doplňování.
    ico = Column(String, nullable=False, default="", server_default="", index=True)
    dic = Column(String, nullable=False, default="", server_default="")

    adresa_ulice = Column(String, nullable=False, default="", server_default="")
    adresa_mesto = Column(String, nullable=False, default="", server_default="")
    adresa_psc = Column(String, nullable=False, default="", server_default="")
    adresa_stat = Column(String, nullable=False, default="Česko", server_default="Česko")
    # GPS se propíše do nabídky (PPA potřebuje polohu pro výpočet výroby FVE).
    gps_lat = Column(Numeric(9, 6), nullable=True)
    gps_lng = Column(Numeric(9, 6), nullable=True)

    web = Column(String, nullable=False, default="", server_default="")
    telefon = Column(String, nullable=False, default="", server_default="")
    email = Column(String, nullable=False, default="", server_default="")
    zdroj = Column(String, nullable=False, default="", server_default="")  # odkud lead přišel
    poznamka = Column(Text, nullable=False, default="", server_default="")

    # Hodnoty vlastních (admin definovaných) polí – mapa {klic_pole: hodnota}.
    # Definice drží `CrmVlastniPole`; tady jsou jen hodnoty tohoto záznamu.
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    # Práva na záznamy – viz docstring modulu.
    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    spoluvlastnici = Column(ARRAY(Integer), nullable=False, default=list, server_default="{}")

    # Koexistence s Raynetem (zatím obojí, appka ho postupně nahradí).
    raynet_id = Column(BigInteger, nullable=True, index=True)
    raynet_synchronizovano_at = Column(DateTime(timezone=True), nullable=True)

    konvertovan_at = Column(DateTime(timezone=True), nullable=True)
    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])
    kontakty = relationship(
        "ZakaznikKontakt", back_populates="zakaznik", cascade="all, delete-orphan"
    )
    pripady = relationship("ObchodniPripad", back_populates="zakaznik")


class ZakaznikKontakt(Base):
    """Kontaktní osoba u zákazníka. `hlavni` = koho appka nabídne první."""

    __tablename__ = "crm_zakaznik_kontakty"

    id = Column(Integer, primary_key=True, index=True)
    zakaznik_id = Column(
        Integer, ForeignKey("crm_zakaznici.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jmeno = Column(String, nullable=False)
    funkce = Column(String, nullable=False, default="", server_default="")
    email = Column(String, nullable=False, default="", server_default="")
    telefon = Column(String, nullable=False, default="", server_default="")
    hlavni = Column(Boolean, nullable=False, default=False, server_default="false")
    poznamka = Column(Text, nullable=False, default="", server_default="")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    zakaznik = relationship("Zakaznik", back_populates="kontakty")


class ObchodniPripad(Base):
    """Obchodní případ – zastřešuje nabídky, objednávku a projekt jedné zakázky.

    `cislo` je viditelné ID z číselné řady appky (OP-26-0301). `raynet_code`
    je Raynetí číslo téhož případu, pokud existuje – na něm stojí párování
    složek na Disku, takže se nesmí zahodit (viz docstring modulu).

    `kategorie` je seznam: případ může být PPA i peak shaving současně.
    Podle kategorie tlačítko „Vytvořit nabídku" pozná, do kterého výpočtu
    poslat OZ; při víc kategoriích nebo prázdné se zeptá.
    """

    __tablename__ = "crm_obchodni_pripady"

    id = Column(Integer, primary_key=True, index=True)
    cislo = Column(String, nullable=False, unique=True, index=True)
    zakaznik_id = Column(
        Integer, ForeignKey("crm_zakaznici.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nazev = Column(String, nullable=False, default="", server_default="")
    popis = Column(Text, nullable=False, default="", server_default="")

    kategorie = Column(ARRAY(String), nullable=False, default=list, server_default="{}")
    # Klíč do CrmStav (entita="op"). Ne FK, protože stavy se dají mazat a
    # historie záznamů by se tím rozpadla; klíč je stabilní text.
    stav = Column(String, nullable=False, index=True)

    hodnota_kc = Column(Numeric(14, 2), nullable=True)
    pravdepodobnost = Column(Integer, nullable=True)  # 0–100 %, pro forecast
    predpokladane_uzavreni = Column(Date, nullable=True)
    # Vyplňuje se při přesunu do stavu druhu „prohra" – bez důvodu prohry
    # nemá statistika pipeline smysl.
    duvod_prohry = Column(String, nullable=False, default="", server_default="")
    uzavreno_at = Column(DateTime(timezone=True), nullable=True)

    # Hodnoty vlastních (admin definovaných) polí – viz `CrmVlastniPole`.
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    spoluvlastnici = Column(ARRAY(Integer), nullable=False, default=list, server_default="{}")

    # Koexistence s Raynetem – `raynet_code` je most na složky Disku a Freelo.
    raynet_id = Column(BigInteger, nullable=True, index=True)
    raynet_code = Column(String, nullable=False, default="", server_default="", index=True)

    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    zakaznik = relationship("Zakaznik", back_populates="pripady")
    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])


class CrmAktivita(Base):
    """Poznámka nebo aktivita (telefon, e-mail, schůzka, úkol) u záznamu.

    Jedna generická tabulka pro všechny entity CRM (`entita` + `zaznam_id`).
    Tohle je věc, kvůli které OZ v appce zůstane – bez logu práce a dalšího
    kroku s termínem si stejně povede zápisky vedle.

    `termin` + `hotovo` dělají z aktivity úkol. Nedokončené úkoly po termínu
    se dají vypsat napříč zákazníky, aniž by se zaváděl další modul.
    """

    __tablename__ = "crm_aktivity"

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)  # jedna z ENTITY_AKTIVIT
    zaznam_id = Column(Integer, nullable=False, index=True)
    druh = Column(String, nullable=False, default="poznamka", server_default="poznamka")
    text = Column(Text, nullable=False, default="", server_default="")

    termin = Column(Date, nullable=True)  # vyplněno = je to úkol
    hotovo = Column(Boolean, nullable=False, default=False, server_default="false")
    hotovo_at = Column(DateTime(timezone=True), nullable=True)

    # Komu úkol patří (výchozí = kdo ho vytvořil).
    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])
    vytvoril = relationship("User", foreign_keys=[vytvoril_user_id])
