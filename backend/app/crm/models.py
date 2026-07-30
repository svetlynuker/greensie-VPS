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
ENTITY_VLASTNICH_POLI = ("zakaznik", "op", "obj", "pro")

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


# ---- Objednávky a projekty --------------------------------------------------
# Stavy kroku projektu. Držíme je zvlášť od stavů entit (`crm_stavy`), protože
# krok je drobnost uvnitř projektu – konfigurovat pro něj pipeline by byla
# zbytečná složitost.
STAVY_KROKU = ("ceka", "probiha", "hotovo", "preskoceno")


class Objednavka(Base):
    """Objednávka – potvrzená zakázka, ze které se rozjíždí realizace.

    Vzniká z PŘIJATÉ nabídky (proto `nabidka_id`), takže si od ní může vzít
    cenu a nemusí se nic opisovat. Nabídku ale nedrží jako cizí klíč natvrdo
    s CASCADE: kdyby se nabídka smazala, objednávka musí zůstat – je to
    obchodní dokument, ne pohled na výpočet.

    `cena_kc` je snapshot, ne odkaz do výpočtu. Cena na objednávce je to, na čem
    se strany dohodly; kdyby se pak přepočítala nabídka, objednávka se tím
    měnit nesmí.
    """

    __tablename__ = "crm_objednavky"

    id = Column(Integer, primary_key=True, index=True)
    cislo = Column(String, nullable=False, unique=True, index=True)
    obchodni_pripad_id = Column(
        Integer, ForeignKey("crm_obchodni_pripady.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    # Ze které nabídky objednávka vznikla (informativní, SET NULL při smazání).
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="SET NULL"), nullable=True, index=True
    )

    nazev = Column(String, nullable=False, default="", server_default="")
    popis = Column(Text, nullable=False, default="", server_default="")
    cena_kc = Column(Numeric(14, 2), nullable=True)
    datum_podpisu = Column(Date, nullable=True)
    datum_dodani = Column(Date, nullable=True)

    stav = Column(String, nullable=False, index=True)  # klíč do crm_stavy, entita "obj"
    duvod_zruseni = Column(String, nullable=False, default="", server_default="")
    uzavreno_at = Column(DateTime(timezone=True), nullable=True)

    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    spoluvlastnici = Column(ARRAY(Integer), nullable=False, default=list, server_default="{}")
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    pripad = relationship("ObchodniPripad")
    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])


class CrmProjekt(Base):
    """Realizační projekt. Vzniká JEN z objednávky nebo z obchodního případu.

    Samostatně vzniknout nesmí (zadání Dana) – proto je `obchodni_pripad_id`
    povinný. Číslo kopíruje případ (`PRO-26-0301` k `OP-26-0301`), aby je lidé
    párovali očima; druhý projekt téhož případu má suffix `-2`.

    POZOR na dvojí význam slova „projekt": tabulka `projekty` (modul matice) je
    projekt z **Freela** s maticí úkolů. Tenhle je CRM záznam realizace.
    `freelo_projekt_id` je most mezi nimi – appka má Freelo postupně nahradit,
    do té doby žijí vedle sebe a párují se přes číslo OP.
    """

    __tablename__ = "crm_projekty"

    id = Column(Integer, primary_key=True, index=True)
    cislo = Column(String, nullable=False, unique=True, index=True)
    obchodni_pripad_id = Column(
        Integer, ForeignKey("crm_obchodni_pripady.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    objednavka_id = Column(
        Integer, ForeignKey("crm_objednavky.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Vazba na projekt z Freela (tabulka `projekty`) – koexistence, viz docstring.
    freelo_projekt_id = Column(
        Integer, ForeignKey("projekty.id", ondelete="SET NULL"), nullable=True, index=True
    )

    nazev = Column(String, nullable=False, default="", server_default="")
    popis = Column(Text, nullable=False, default="", server_default="")
    stav = Column(String, nullable=False, index=True)  # klíč do crm_stavy, entita "pro"

    zahajeni = Column(Date, nullable=True)
    predani = Column(Date, nullable=True)  # plánované předání
    uzavreno_at = Column(DateTime(timezone=True), nullable=True)

    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    spoluvlastnici = Column(ARRAY(Integer), nullable=False, default=list, server_default="{}")
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    pripad = relationship("ObchodniPripad")
    objednavka = relationship("Objednavka")
    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])
    kroky = relationship(
        "ProjektKrok", back_populates="projekt", cascade="all, delete-orphan"
    )


class ProjektSablona(Base):
    """Šablona projektových kroků – „takhle u nás vypadá FVE realizace".

    Vedení si nachystá posloupnost kroků s odstupy a návaznostmi; na projektu
    se pak jedním kliknutím rozbalí do konkrétních úkolů s termíny. Bez šablon
    by každý projekt někdo psal ručně a pokaždé jinak.
    """

    __tablename__ = "crm_projekt_sablony"

    id = Column(Integer, primary_key=True, index=True)
    nazev = Column(String, nullable=False, unique=True)
    popis = Column(Text, nullable=False, default="", server_default="")
    # Pro kterou kategorii zakázky se šablona nabízí (prázdné = pro všechny).
    kategorie = Column(ARRAY(String), nullable=False, default=list, server_default="{}")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )

    kroky = relationship(
        "ProjektSablonaKrok", back_populates="sablona", cascade="all, delete-orphan"
    )


class ProjektSablonaKrok(Base):
    """Krok v šabloně. Návaznost se drží jako POŘADÍ předchůdce, ne cizí klíč.

    Důvod: šablona se kopíruje do projektu, kde vzniknou nové řádky s novými id.
    Kdyby se závislost držela přes id řádku šablony, po kopii by nesouhlasila.
    Pořadí přežije kopii i přeskládání šablony.
    """

    __tablename__ = "crm_projekt_sablona_kroky"

    id = Column(Integer, primary_key=True, index=True)
    sablona_id = Column(
        Integer, ForeignKey("crm_projekt_sablony.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    nazev = Column(String, nullable=False)
    popis = Column(Text, nullable=False, default="", server_default="")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    # Kolik dní krok trvá (na dopočet termínů) a na kterém kroku závisí
    # (pořadí předchůdce; NULL = jde se od zahájení projektu).
    delka_dni = Column(Integer, nullable=False, default=1, server_default="1")
    zavisi_na_poradi = Column(Integer, nullable=True)

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sablona = relationship("ProjektSablona", back_populates="kroky")


class ProjektKrok(Base):
    """Konkrétní krok (úkol) projektu.

    `zavisi_na_id` je skutečný cizí klíč mezi kroky jednoho projektu – tady už
    id existují, takže návaznost může být přesná. Dokud předchůdce není hotový,
    krok se drží ve stavu „čeká" a jeho termín se dopočítává od data, kdy
    předchůdce doopravdy skončí (viz `projekty_kroky.prepocitej_terminy`).
    """

    __tablename__ = "crm_projekt_kroky"

    id = Column(Integer, primary_key=True, index=True)
    projekt_id = Column(
        Integer, ForeignKey("crm_projekty.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nazev = Column(String, nullable=False)
    popis = Column(Text, nullable=False, default="", server_default="")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    stav = Column(String, nullable=False, default="ceka", server_default="ceka")  # STAVY_KROKU
    delka_dni = Column(Integer, nullable=False, default=1, server_default="1")
    zavisi_na_id = Column(
        Integer, ForeignKey("crm_projekt_kroky.id", ondelete="SET NULL"), nullable=True
    )

    termin = Column(Date, nullable=True)  # dopočítaný, nebo ručně přepsaný
    termin_rucne = Column(Boolean, nullable=False, default=False, server_default="false")
    hotovo_at = Column(DateTime(timezone=True), nullable=True)
    odpovedny_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    projekt = relationship("CrmProjekt", back_populates="kroky")
    odpovedny = relationship("User", foreign_keys=[odpovedny_user_id])
