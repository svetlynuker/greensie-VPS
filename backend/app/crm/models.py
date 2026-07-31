"""Datový model CRM: Zákazníci → Obchodní případy → (Nabídky → Objednávky → Projekty).

Proč vlastní modul a ne rozšíření nabídkovače: nabídkovač je *výpočetní*
nástroj (sizing, ROI, tisk). CRM je evidence, do které nabídka patří jako
jeden z artefaktů obchodního případu. Držíme to oddělené, aby se výpočty
daly měnit bez zásahu do evidence a naopak.

KOEXISTENCE S RAYNETEM (rozhodnutí Dana, 30. 7. 2026): appka Raynet postupně
nahradí, ale zatím běží obojí. Proto každá entita, která má v Raynetu
protějšek, nese `raynet_id` a případy navíc `raynet_code`. Důvod není
„pro pořádek“: na Raynetí čísle obchodního případu (`code`, např. OP-26-0223)
stojí dva existující mechanismy – konektor podle něj pojmenovává složky na
Google Disku a `matice/disk_parovani.py` podle něj páruje Freelo projekty
s jejich složkou dokumentů. Kdyby appka Raynetí číslo zahodila a nahradila
vlastním, obojí by se rozbilo. Vlastní číslo appky (`cislo`) a Raynetí číslo
(`raynet_code`) tedy žijí vedle sebe; párování na Disk vždy používá to
Raynetí, dokud Raynet nezmizí.

PRÁVA NA ZÁZNAMY: každá entita má `vlastnik_user_id` + `spoluvlastnici`.
Kdo nemá právo `crm_vse`, vidí jen záznamy, kde je vlastníkem nebo
spoluvlastníkem (viz `crm/pristup.py`). Žádná hierarchie rolí se nezavádí –
„vedení vidí vše“ = skupina s právem `crm_vse`.
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
#
# POZOR: tohle už NENÍ zdroj pravdy. Kategorie jsou od 30. 7. 2026 data
# v tabulce `crm_kategorie` (vedení si je spravuje samo, stejně jako stavy
# pipeline) – tady zůstávají jen jako výchozí sada pro seed a jako fallback,
# kdyby byla tabulka prázdná. Validace i výpisy čtou DB, viz `crm/kategorie.py`.
KATEGORIE_OP = ("prodej", "ppa", "peak_shaving")

# Druhy aktivit. Sada se drží předlohy kalendáře z Raynetu (Úkol, Schůzka,
# Událost, Telefonát, Dopis), aby se lidem po přechodu nezměnil slovník.
#
# Dva rozdíly proti té předloze, oba schválně:
#   * `poznamka` zůstává navíc – je to záznam do historie BEZ plánování
#     („volal, chce to po dovolené“), který se do kalendáře nekreslí. Log práce
#     na kartě zákazníka na něm stojí.
#   * `email` zůstává vedle `dopis`: dopis je fyzická pošta (a v CRM se hlídá
#     kvůli doporučeným zásilkám), e-mail je něco jiného.
DRUHY_AKTIVITY = ("ukol", "schuzka", "udalost", "telefon", "dopis", "email", "poznamka")

# Priorita aktivity — tři stupně jako v předloze (šipka dolů / – / !).
PRIORITY_AKTIVITY = ("nizka", "stredni", "vysoka")

# Frekvence opakování aktivity (zadání Dana 30. 7. 2026).
#   denne         → každý den
#   pracovni_dny  → po–pá, víkend se přeskočí
#   tydne         → stejný den v týdnu
#   mesicne       → stejné číslo v měsíci (viz `opakovani.py`, kde je řešeno,
#                   co s 31. dnem v měsíci, který ho nemá)
#   vlastni       → každých N dní (`interval_dni`), třeba 14
FREKVENCE_OPAKOVANI = ("denne", "pracovni_dny", "tydne", "mesicne", "vlastni")

# Na co se vztahuje úprava nebo smazání události, která patří do série.
ROZSAHY_SERIE = ("jen_tuhle", "tuto_a_dalsi", "celou_serii")

# Stav aktivity. Nahradil boolean `hotovo`, protože ten neumí rozlišit schůzku,
# která proběhla, od schůzky, kterou zákazník zrušil — a obojí pod jedním
# „hotovo“ by znehodnotilo každou statistiku aktivity OZ.
#   naplanovano  → čeká, počítá se do „moje úkoly“
#   realizovano  → proběhlo, `vysledek` říká s jakým výsledkem
#   nekonalo_se  → nekonalo se, `vysledek` říká proč
STAVY_AKTIVITY = ("naplanovano", "realizovano", "nekonalo_se")
# Stavy, kterými je aktivita uzavřená (nepočítá se do nedokončených úkolů).
STAVY_UZAVRENE = ("realizovano", "nekonalo_se")

# Obrazovky, na které smí admin přidávat vlastní pole. Rozšíření o další
# entitu = přidat klíč sem, její model do `vlastni_pole.MODELY` (entita musí
# mít sloupec `extra`) a klíč do `EntitaPole` ve `schemas.py` – jinak se pole
# založí, ale endpoint spadne při skládání odpovědi. Hlídá to
# `tests/test_vlastni_pole.py`.
ENTITY_VLASTNICH_POLI = ("zakaznik", "op", "obj", "pro", "om", "nab")

# Datový typ vlastního pole. Dan chtěl „textová pole“; typy navíc stojí skoro
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


class CrmNastaveni(Base):
    """Firemní nastavení CRM — jeden řádek (id=1).

    Zatím drží jen naši adresu pro tlačítko „U nás“ u místa konání schůzky.
    Vlastní tabulka, a ne konstanta v kódu: adresa se mění (přestěhování) a je
    to údaj firmy, ne uživatele, takže nepatří do `uzivatelska_nastaveni`.

    Jeden řádek je schválně — je to konfigurace, ne seznam. `nacti()`
    v `nastaveni_crm.py` ho vyrobí, když ještě není.
    """

    __tablename__ = "crm_nastaveni"

    id = Column(Integer, primary_key=True, index=True)
    nase_adresa = Column(String, nullable=False, default="", server_default="")
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmSerieAktivit(Base):
    """Pravidlo opakování pro sérii aktivit („porada každý čtvrtek“).

    ---- Proč se instance MATERIALIZUJÍ -------------------------------------
    Série se při založení rozepíše do skutečných řádků `crm_aktivity`, místo aby
    se dopočítávala při každém dotazu. Důvody:

      * jedna porada z série se běžně přesune nebo zruší — nad vypočítanými
        instancemi by to znamenalo vést seznam výjimek a slepovat ho při každém
        čtení kalendáře,
      * aktivita ze série se má chovat jako každá jiná: dá se u ní zapsat
        výsledek, navěsit na klienta, přetáhnout myší. Virtuální instance by
        musela nejdřív „zhmotnět“, což je krok, který nikdo nechce vysvětlovat.

    Cena je počet řádků, a proto má opakování POVINNÝ konec (`do_data` nebo
    `pocet`) a strop `MAX_INSTANCI` v `opakovani.py`.

    `frekvence` je jedna z `FREKVENCE_OPAKOVANI`; `interval_dni` má význam jen
    u „vlastni“ (každých N dní).
    """

    __tablename__ = "crm_serie_aktivit"

    id = Column(Integer, primary_key=True, index=True)
    frekvence = Column(String, nullable=False)
    interval_dni = Column(Integer, nullable=True)  # jen pro frekvenci "vlastni"
    # Konec série. Vyplněné je vždy jedno z dvou — validace je v `opakovani.py`.
    do_data = Column(Date, nullable=True)
    pocet = Column(Integer, nullable=True)

    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrmKategorieAktivity(Base):
    """Barevný štítek aktivity („Porada“, „Servis“, „Reklamace“).

    POZOR na jméno: tohle NENÍ `CrmKategorie` (ta říká, do kterého výpočtu míří
    obchodní případ). Tady jde o barevné škatulky v kalendáři, kterými si firma
    tříditelně označuje aktivity — v předloze je to sekce „KATEGORIE“ v panelu
    filtrů a barevné tečky ve výběru u nové aktivity.

    Proč vlastní tabulka a ne výčet v kódu: stejný důvod jako u stavů pipeline —
    přidání kategorie je práce pro vedení, ne pro programátora. A protože se
    kategorií filtruje, musí mít stabilní `id`, na které se odkáže uložený filtr.

    `barva` je hex, ne token appky: uživatel si ji vybírá z palety a je to jeho
    volba, ne stavová barva (u té by tokeny byly správně kvůli tmavému režimu).
    Čitelnost textu na štítku se dopočítává ze svítivosti (frontend).
    """

    __tablename__ = "crm_kategorie_aktivit"
    __table_args__ = (UniqueConstraint("nazev", name="uq_crm_kategorie_aktivity_nazev"),)

    id = Column(Integer, primary_key=True, index=True)
    nazev = Column(String, nullable=False)
    barva = Column(String, nullable=False, default="#7b8794", server_default="#7b8794")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")
    aktivni = Column(Boolean, nullable=False, default=True, server_default="true")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class CrmKategorie(Base):
    """Kategorie obchodního případu – konfigurovatelná, ne zadrátovaná v kódu.

    Do 30. 7. 2026 to byla trojice v konstantě (`prodej`/`ppa`/`peak_shaving`)
    na dvou místech (backend + frontend), zatímco stavy pipeline i vlastní pole
    si vedení spravovalo samo. Tahle tabulka tu nekonzistenci ruší: „Servis“
    nebo „Dotace“ přidá vedení v nastavení, bez programátora.

    `typ_nabidky` je to podstatné pole. Kategorie totiž řídí, do kterého
    VÝPOČTU nabídkovače případ míří (tlačítko „+ PPA“ na kartě případu zakládá
    nabídku typu `ppa`). Kategorie, ke které žádný výpočet neexistuje, má tohle
    pole prázdné a tlačítko se u ní nenabídne – jinak by appka slibovala
    výpočet, který neumí. Hodnota musí být jedna z `TYPY_NABIDKY`.

    `aktivni=False` kategorii schová z nabídky u NOVÝCH případů, ale nechá ji
    zobrazovat u těch, které ji už mají. Mazání kategorie, kterou někdo používá,
    by z historických případů udělalo záznamy s nečitelným klíčem.
    """

    __tablename__ = "crm_kategorie"
    __table_args__ = (UniqueConstraint("klic", name="uq_crm_kategorie_klic"),)

    id = Column(Integer, primary_key=True, index=True)
    # Strojový klíč – drží se v `ObchodniPripad.kategorie` a v `Nabidka.typ`,
    # takže se NIKDY nepřepisuje (přejmenovat lze jen `nazev`).
    klic = Column(String, nullable=False)
    nazev = Column(String, nullable=False)
    popis = Column(String, nullable=False, default="", server_default="")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")
    # Prázdné = kategorie bez výpočtu (např. servis). Jinak klíč z TYPY_NABIDKY.
    typ_nabidky = Column(String, nullable=False, default="", server_default="")
    aktivni = Column(Boolean, nullable=False, default=True, server_default="true")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


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
    # Klíče polí, které musí být vyplněné, aby se záznam do tohoto stavu dostal
    # (CRM-30). Prázdné = bez podmínek. Seznam, ne pevné sloupce, protože jde
    # o „jakékoli pole včetně budoucích“ — viz `povinna_pole.py`.
    povinna_pole = Column(ARRAY(String), nullable=False, default=list, server_default="{}")

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
    nepotřebuju“. Přidání sloupce do schématu by znamenalo migraci a nasazení,
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

    # CRM-33: nadpis skupiny, pod který pole patří. Prázdné = „Doplňující údaje".
    # Je to text, ne cizí klíč do tabulky skupin: skupina nemá žádné vlastní
    # chování ani nastavení, takže by to byla tabulka o jednom sloupci a navíc
    # by se musela uklízet, když z ní vypadne poslední pole.
    skupina = Column(String, nullable=False, default="", server_default="")

    # CRM-33: pole se ukáže, jen když má záznam tuhle hodnotu ve `zavislost_pole`.
    # Obojí prázdné = pole je vidět vždycky.
    zavislost_pole = Column(String, nullable=False, default="", server_default="")
    zavislost_hodnota = Column(String, nullable=False, default="", server_default="")

    # CRM-34: výraz výpočtového pole („cena - nakup"). Neprázdný = pole se
    # nevyplňuje, ale počítá; do `extra` se neukládá (počítá se při zobrazení),
    # aby v datech nebyla zastaralá kopie výsledku.
    vzorec = Column(String, nullable=False, default="", server_default="")

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
    odberna_mista = relationship(
        "OdberneMisto", back_populates="zakaznik", cascade="all, delete-orphan"
    )


class OdberneMisto(Base):
    """Odběrné místo zákazníka – kde se elektřina odebírá a čím je zasmluvněná.

    Proč vlastní entita a ne pár polí na zákazníkovi: jedna firma má běžně víc
    provozoven a každá má svůj EAN, svého distributora, svou napěťovou hladinu
    a svou rezervovanou kapacitu. Právě na tyhle čtyři věci se váže celý výpočet
    peak shavingu, a 15minutový diagram odběru patří k MÍSTU, ne k firmě ani
    k nabídce – proto na něj visí `CrmDiagram`.

    Co se tím odemklo: hodnoty, které OZ dnes vypisuje ručně do každého výpočtu
    (distributor, hladina, rezervovaná kapacita) i GPS pro výpočet výroby FVE
    se dají předvyplnit z místa. GPS je tu schválně vlastní a ne přebíraná ze
    zákazníka: FVE se staví na provozovně, kdežto adresa firmy je fakturační
    (klidně sídlo účetní v jiném kraji).

    Práva se nedědí přes vlastní vlastníka, ale přes zákazníka: kdo vidí firmu,
    vidí i její odběrná místa. Vlastní vlastník by znamenal, že se místo dá
    „ztratit" pod zákazníkem, kterého uživatel vidí.
    """

    __tablename__ = "crm_odberna_mista"

    id = Column(Integer, primary_key=True, index=True)
    zakaznik_id = Column(
        Integer, ForeignKey("crm_zakaznici.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nazev = Column(String, nullable=False)  # „Hala Kolín", „Sídlo – Praha 9"

    # EAN odběrného místa (18 znaků, v ČR začíná 859). Nepovinný – u leadu ho
    # OZ ještě nemá. Index kvůli hledání „ke kterému místu patří tenhle diagram".
    ean = Column(String, nullable=False, default="", server_default="", index=True)

    adresa_ulice = Column(String, nullable=False, default="", server_default="")
    adresa_mesto = Column(String, nullable=False, default="", server_default="")
    adresa_psc = Column(String, nullable=False, default="", server_default="")
    # Poloha PROVOZOVNY (ne fakturační adresy) – vstup pro výpočet výroby FVE.
    gps_lat = Column(Numeric(9, 6), nullable=True)
    gps_lng = Column(Numeric(9, 6), nullable=True)

    # Distribuční parametry místa. Prázdné = ještě nezjištěno; hodnoty drží
    # nabídkovač (`nabidkovac.models.DISTRIBUTORI` / `NAPETOVE_HLADINY`), tady
    # jsou jako text, aby CRM nemuselo importovat modely nabídkovače.
    distributor = Column(String, nullable=False, default="", server_default="")
    napetova_hladina = Column(String, nullable=False, default="", server_default="")
    rezervovana_kapacita_kw = Column(Numeric(12, 3), nullable=True)
    rezervovany_prikon_kw = Column(Numeric(12, 3), nullable=True)

    poznamka = Column(Text, nullable=False, default="", server_default="")
    # Vypnuté místo (odprodaná provozovna) se nenabízí k novým nabídkám, ale
    # zůstává i s diagramy kvůli historii už odeslaných nabídek.
    aktivni = Column(Boolean, nullable=False, default=True, server_default="true")

    # Hodnoty vlastních (admin definovaných) polí – viz `CrmVlastniPole`.
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    zakaznik = relationship("Zakaznik", back_populates="odberna_mista")
    diagramy = relationship(
        "CrmDiagram", back_populates="odberne_misto", cascade="all, delete-orphan"
    )


class CrmDiagram(Base):
    """15minutový diagram odběru nahraný k odběrnému místu (CRM-46, etapa 2).

    Diagram patří MÍSTU, ne nabídce: OZ ho stáhne z portálu distributora jednou
    a použije ho pro všechny nabídky té provozovny. Dřív visel na nabídce
    (`nabidka_dokumenty` + `spotreba_profil`), takže se tentýž soubor nahrával
    ke každé nabídce znovu.

    SOUBOR SE PARSUJE HNED při nahrání a souhrn (`obdobi_od`…`max_kw`) se uloží
    sem. Důvod: dokud se parsovalo až na kliknutí v panelu výpočtu, dal se nahrát
    nepoužitelný export a poznalo se to teprve u výpočtu — nebo vůbec, a nabídka
    se spočítala bez dat spotřeby (nahlásil Dan 31. 7. 2026). Souhrn je zároveň
    to, co se ukazuje v seznamu, aby OZ viděl, že soubor pokrývá celý rok.

    Samotná časová řada se sem NEKOPÍRUJE. Zůstává uložený soubor a při použití
    pro nabídku se z něj naplní `spotreba_profil` té nabídky — nabídka si tak
    drží čísla, se kterými odešla zákazníkovi (rozhodnutí Dana 31. 7. 2026),
    a novější diagram jí je nepřepíše sám.
    """

    __tablename__ = "crm_diagramy"

    id = Column(Integer, primary_key=True, index=True)
    odberne_misto_id = Column(
        Integer, ForeignKey("crm_odberna_mista.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # U kterého případu byl diagram nahraný. Jen informace „odkud přišel“ —
    # použitelný je pro všechny případy toho zákazníka, proto SET NULL.
    obchodni_pripad_id = Column(
        Integer, ForeignKey("crm_obchodni_pripady.id", ondelete="SET NULL"), nullable=True
    )

    soubor_cesta = Column(String, nullable=False)  # relativní k UPLOAD_DIR
    puvodni_nazev = Column(String, nullable=False, default="", server_default="")
    velikost_bajtu = Column(Integer, nullable=True)
    popis = Column(String, nullable=False, default="", server_default="")

    # "zpracovano" = řada se načetla a souhrn níž platí; "chyba" = soubor zůstal
    # uložený, ale přečíst se nedal (`chyba_text` říká proč).
    stav = Column(String, nullable=False, default="zpracovano", server_default="zpracovano")
    chyba_text = Column(Text, nullable=False, default="", server_default="")

    # Souhrn z parsování. Bez časové zóny – „místní čas“, stejně jako profil.
    obdobi_od = Column(DateTime(timezone=False), nullable=True)
    obdobi_do = Column(DateTime(timezone=False), nullable=True)
    pocet_intervalu = Column(Integer, nullable=True)
    interval_min = Column(Integer, nullable=True)  # 15 (u hodinových exportů 60)
    spotreba_mwh = Column(Numeric(14, 3), nullable=True)
    max_kw = Column(Numeric(12, 3), nullable=True)

    nahral_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    nahrano_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    odberne_misto = relationship("OdberneMisto", back_populates="diagramy")


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
    Podle kategorie tlačítko „Vytvořit nabídku“ pozná, do kterého výpočtu
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

    # Kterého odběrného místa se případ týká. Nepovinné: u případu, kde se ještě
    # neví, kam se bude stavět, se nechá prázdné, a u nabídky bez peak shavingu
    # (třeba jen dotaz na cenu) není potřeba vůbec. Když je vyplněné, nabídka si
    # z místa vezme diagram i distribuční parametry. SET NULL, ne CASCADE –
    # smazané místo nesmí odnést celý obchodní případ.
    odberne_misto_id = Column(
        Integer, ForeignKey("crm_odberna_mista.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kategorie = Column(ARRAY(String), nullable=False, default=list, server_default="{}")
    # Klíč do CrmStav (entita="op"). Ne FK, protože stavy se dají mazat a
    # historie záznamů by se tím rozpadla; klíč je stabilní text.
    stav = Column(String, nullable=False, index=True)

    hodnota_kc = Column(Numeric(14, 2), nullable=True)
    pravdepodobnost = Column(Integer, nullable=True)  # 0–100 %, pro forecast
    predpokladane_uzavreni = Column(Date, nullable=True)
    # Vyplňuje se při přesunu do stavu druhu „prohra“ – bez důvodu prohry
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
    """Poznámka, aktivita (telefon, e-mail, schůzka, úkol) nebo událost v kalendáři.

    Jedna generická tabulka pro všechny entity CRM (`entita` + `zaznam_id`).
    Tohle je věc, kvůli které OZ v appce zůstane – bez logu práce a dalšího
    kroku s termínem si stejně povede zápisky vedle.

    ---- Datum a čas: `termin` je den, `zacatek` je hodina -------------------
    Rozdělení, na kterém stojí kalendář, a snadno se poplete:

      * `termin` (datum) je **den**, na který aktivita patří. Vyplněný termín
        dělá z aktivity úkol a stojí na něm výpis „moje úkoly“ i Rozcestník.
      * `zacatek` (datum + čas) je **konkrétní hodina** pro kalendářní mřížku.
        Nepovinný: úkol „zavolat ve čtvrtek“ hodinu mít nemusí.

    PRAVIDLO, které drží obojí pohromadě: když je vyplněný `zacatek`, `termin`
    se z něj vždy dopočítá (viz `kalendar.srovnej_termin`). Díky tomu zůstává
    `termin` jediným zdrojem pravdy pro „kterého dne se to má stát“ a nic, co
    filtruje podle termínu, se kalendářem nerozbije.

    Aktivita bez `zacatek`, ale s `termin`, je v kalendáři **celodenní** pruh.
    Aktivita bez obojího je jen zápis do historie a v kalendáři není.

    ---- Stav místo dřívějšího `hotovo` -------------------------------------
    `stav` je jedna z `STAVY_AKTIVITY`: naplánováno → realizováno / nekonalo se.
    Nahradil boolean `hotovo`, protože ten neumí rozlišit schůzku, která
    proběhla, od schůzky, kterou zákazník zrušil – a obojí schované pod
    „hotovo“ by rozbilo každou statistiku aktivity. `vysledek` říká, co z
    aktivity vyšlo (nebo proč se nekonala).

    ---- Soukromá událost ---------------------------------------------------
    `soukroma=True` je osobní blok v kalendáři (dovolená, doktor). Nemá klienta,
    proto jsou `entita` i `zaznam_id` nepovinné. Cizí soukromou událost nevidí
    **ani vedení, ani admin** – jen obsazený čas, viz `kalendar.pro_uzivatele`.
    """

    __tablename__ = "crm_aktivity"

    id = Column(Integer, primary_key=True, index=True)
    # Čeho se aktivita týká. Nepovinné kvůli soukromým událostem – ty klienta
    # ani případ nemají a mít pro ně druhou tabulku by znamenalo dva kalendáře.
    entita = Column(String, nullable=True, index=True)  # jedna z ENTITY_AKTIVIT
    zaznam_id = Column(Integer, nullable=True, index=True)
    druh = Column(String, nullable=False, default="poznamka", server_default="poznamka")
    # Krátký titulek do dlaždice v kalendáři. `text` je delší popis/poznámka –
    # v mřížce po hodinách se dlouhý text nemá kam vejít.
    nazev = Column(String, nullable=False, default="", server_default="")
    text = Column(Text, nullable=False, default="", server_default="")

    termin = Column(Date, nullable=True)  # den (vyplněno = je to úkol)
    # Hodina pro kalendářní mřížku. ZÁMĚRNĚ **bez časové zóny**, na rozdíl od
    # ostatních časů v appce: je to „místní čas firmy“, ne okamžik na časové
    # ose. Firma pracuje v jedné zóně a tohle zjednodušení odstraňuje dvě chyby,
    # které by jinak vznikly – server i DB běží v UTC, takže:
    #   * TIMESTAMPTZ by čas 9:00 poslal prohlížeči jako 9:00 UTC a ten by
    #     v Praze zobrazil 11:00 (uživatel zadal jedno, viděl druhé),
    #   * `termin` se dopočítává z `zacatek.date()` – u půlnočních hodin by
    #     převod přes UTC posunul den o jeden dozadu.
    # Kdyby firma někdy pracovala ve víc zónách, tohle je místo, kde začít.
    zacatek = Column(DateTime, nullable=True)
    delka_min = Column(Integer, nullable=True)  # jak dlouho trvá
    # Poslední den vícedenní aktivity (školení, dovolená přes týden). Prázdné =
    # jednodenní. V kalendáři se z toho kreslí pruh v řádku „vícedenní“;
    # ukládá se jako DEN, ne konec s hodinou, protože vícedenní věci se plánují
    # „od pondělí do středy“, ne „do středy 17:30“.
    konec = Column(Date, nullable=True)

    # Priorita z předlohy (nízká / střední / vysoká). Řídí jen zobrazení —
    # vykřičník na dlaždici, ať je na první pohled vidět, co nepočká.
    priorita = Column(
        String, nullable=False, default="stredni", server_default="stredni"
    )
    # Místo konání jako volný text (adresa nebo „u nás“, „online“). Ne cizí klíč
    # na adresu zákazníka: schůzka bývá i jinde než na jeho sídle.
    misto = Column(String, nullable=False, default="", server_default="")
    kategorie_id = Column(
        Integer,
        ForeignKey("crm_kategorie_aktivit.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Série opakování, ze které aktivita vznikla. SET NULL schválně: když se
    # smaže pravidlo, jednotlivé aktivity zůstanou — jsou to platné záznamy
    # v historii a nemají zmizet kvůli úklidu pravidla.
    serie_id = Column(
        Integer, ForeignKey("crm_serie_aktivit.id", ondelete="SET NULL"), nullable=True, index=True
    )

    stav = Column(
        String, nullable=False, default="naplanovano", server_default="naplanovano", index=True
    )
    vysledek = Column(Text, nullable=False, default="", server_default="")
    hotovo_at = Column(DateTime(timezone=True), nullable=True)  # kdy se uzavřela

    soukroma = Column(Boolean, nullable=False, default=False, server_default="false")

    # Komu úkol patří (výchozí = kdo ho vytvořil).
    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Další lidé na schůzce. Stejný vzor jako `spoluvlastnici` u případu:
    # účastník vidí detail události, i když není vlastník.
    ucastnici = Column(ARRAY(Integer), nullable=False, default=list, server_default="{}")
    vytvoril_user_id = Column(Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    vlastnik = relationship("User", foreign_keys=[vlastnik_user_id])
    vytvoril = relationship("User", foreign_keys=[vytvoril_user_id])
    kategorie = relationship("CrmKategorieAktivity")
    serie = relationship("CrmSerieAktivit")


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
    # True = cenu někdo přepsal ručně (dohodnutá sleva „za kulatých 2,4 mil.“)
    # a součet položek ji už nepřepíše. Appka pak jen ukazuje, o kolik se liší.
    # Rozhodl Dan 31. 7. 2026: součet položek, ale ruční přepis má přednost.
    cena_rucni = Column(Boolean, nullable=False, default=False, server_default="false")
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
    polozky = relationship(
        "ObjednavkaPolozka",
        back_populates="objednavka",
        cascade="all, delete-orphan",
        order_by="ObjednavkaPolozka.poradi, ObjednavkaPolozka.id",
    )
    faktury = relationship(
        "Faktura",
        back_populates="objednavka",
        cascade="all, delete-orphan",
        order_by="Faktura.poradi, Faktura.id",
    )


class ObjednavkaPolozka(Base):
    """Řádek rozpisu objednávky (CRM-08).

    Sloupce jsou schválně stejné jako u `NabidkaPolozka` – při potvrzení
    nabídky se rozpis PŘEKLOPÍ (zkopíruje), ne naváže. Objednávka je obchodní
    dokument: kdyby ukazovala živý rozpis nabídky, změnil by se jí obsah pod
    rukama, kdykoli někdo přepočítá nabídku. Stejná úvaha stojí za snapshotem
    `Objednavka.cena_kc`.
    """

    __tablename__ = "crm_objednavka_polozky"

    id = Column(Integer, primary_key=True, index=True)
    objednavka_id = Column(
        Integer, ForeignKey("crm_objednavky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    technologie_id = Column(
        Integer, ForeignKey("technologie.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kod = Column(String, nullable=False, default="", server_default="")
    nazev = Column(String, nullable=False)
    popis = Column(Text, nullable=False, default="", server_default="")
    jednotka = Column(String, nullable=False, default="ks", server_default="ks")

    mnozstvi = Column(Numeric(12, 3), nullable=False, default=1, server_default="1")
    cena_jednotkova = Column(Numeric(12, 2), nullable=True)
    nakup_jednotkovy = Column(Numeric(12, 2), nullable=True)
    sleva_procent = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    sazba_dph = Column(Numeric(5, 4), nullable=True)

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    objednavka = relationship("Objednavka", back_populates="polozky")


class CrmProjekt(Base):
    """Realizační projekt. Vzniká JEN z objednávky nebo z obchodního případu.

    Samostatně vzniknout nesmí (zadání Dana) – proto je `obchodni_pripad_id`
    povinný. Číslo kopíruje případ (`PRO-26-0301` k `OP-26-0301`), aby je lidé
    párovali očima; druhý projekt téhož případu má suffix `-2`.

    POZOR na dvojí význam slova „projekt“: tabulka `projekty` (modul matice) je
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
    """Šablona projektových kroků – „takhle u nás vypadá FVE realizace“.

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
    krok se drží ve stavu „čeká“ a jeho termín se dopočítává od data, kdy
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


# Entity, nad kterými jdou stavět uživatelské filtry (seznamy i kanbany).
# „kalendar“ je tu navíc proti seznamům: kalendář ukládá stav svého panelu
# (uživatelé, typy, kategorie, přepínače) do TÉŽE tabulky, takže sdílení filtru
# a výchozí pohled fungují bez druhého mechanismu. Podmínky u něj nemají formát
# pole/operátor/hodnota — je to jedna položka s JSON stavem, viz Kalendar.jsx.
ENTITY_FILTRU = ("zakaznik", "op", "nab", "obj", "pro", "kalendar")

# Operátory podmínek. Držíme je jako data, protože je zná i frontend (crm_filtry.js)
# a musí se shodovat – jinak by uložený filtr znamenal jinde něco jiného.
OPERATORY_FILTRU = (
    "obsahuje",
    "neobsahuje",
    "je",
    "neni",
    "je_jeden_z",
    "vetsi",
    "mensi",
    "mezi",
    "je_prazdne",
    "neni_prazdne",
)


class CrmUlozenyFiltr(Base):
    """Uživatelský filtr nad seznamem/kanbanem – víc podmínek a víceúrovňové řazení.

    Proč vlastní tabulka a ne jen stav v prohlížeči: filtr typu „moje otevřené
    PPA případy nad milion, řazené podle termínu“ si člověk staví jednou a chce
    ho mít i zítra a na jiném počítači. A vedení potřebuje umět takový pohled
    **nasdílet** ostatním (`sdileny`).

    `podminky` = [{pole, operator, hodnota}], vyhodnocuje se jako AND. Víc
    podmínek nad stejným polem se tím chová jako zúžení (rozsah), což je přesně
    to, co lidé od „víceúrovňového“ filtru čekají.

    `razeni` = [{pole, smer}] v pořadí priority: první je hlavní klíč, další
    rozhodují při shodě.

    Uloženo jako JSONB, protože sada polí se u každé entity liší a bude se
    rozšiřovat (i vlastními polemi) – pevné sloupce by znamenaly migraci při
    každé změně.
    """

    __tablename__ = "crm_ulozene_filtry"
    __table_args__ = (
        UniqueConstraint("entita", "vlastnik_user_id", "nazev", name="uq_crm_filtr_nazev"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)  # jedna z ENTITY_FILTRU
    nazev = Column(String, nullable=False)
    podminky = Column(JSONB, nullable=False, default=list, server_default="[]")
    razeni = Column(JSONB, nullable=False, default=list, server_default="[]")
    # CRM-28: rozvržení tabulky uložené s filtrem – {"skryte": [...], "poradi": [...]}.
    # Prázdné = filtr rozvržení neřeší a zůstane to, co má uživatel nastavené.
    sloupce = Column(JSONB, nullable=False, default=dict, server_default="{}")

    # Autor filtru. NULL by znamenalo „nikoho“, což nechceme – filtr vždy někomu
    # patří a jen sdílený je vidět i ostatním.
    vlastnik_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sdileny = Column(Boolean, nullable=False, default=False, server_default="false")
    # Filtr, který se má po otevření sekce použít sám.
    vychozi = Column(Boolean, nullable=False, default=False, server_default="false")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    vlastnik = relationship("User")


class CrmNotifikace(Base):
    """Notifikace v appce — to, co visí pod zvonečkem (CRM-10).

    Proč vlastní tabulka a ne jen e-mail: e-mail si člověk odklikne a ztratí se
    v poště, zatímco tady zůstane, dokud ho nepřečte, a dá se dohledat zpětně.
    E-mail je jen druhý kanál téže události — řídí ho volba uživatele
    (CRM-36, `crm/notifikace.py`).

    `cesta` je adresa ve FRONTENDU (`/pripady/detail/12`), ne celé URL. Doménu
    si domyslí e-mail z `APP_URL`; kdyby tu byla natvrdo, notifikace z náhledu
    by odkazovaly na produkci.

    Záznam se schválně **neváže cizím klíčem na entitu**, které se týká: úkol,
    případ i nabídka mohou zmizet, ale zpráva „tohle ti bylo přiřazeno" má
    v historii zůstat. Mrtvý odkaz je menší zlo než mazání historie.
    """

    __tablename__ = "crm_notifikace"

    id = Column(Integer, primary_key=True, index=True)
    uzivatel_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Klíč z `notifikace.UDALOSTI` – podle něj se pozná, co uživatel vypnul.
    udalost = Column(String, nullable=False, index=True)
    predmet = Column(String, nullable=False, default="", server_default="")
    text = Column(Text, nullable=False, default="", server_default="")
    cesta = Column(String, nullable=False, default="", server_default="")

    precteno_at = Column(DateTime(timezone=True), nullable=True)
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    uzivatel = relationship("User")


class CrmSablona(Base):
    """Šablona e-mailu nebo poznámky (CRM-32).

    Vzniklo to kvůli tomu, že OZ píše pořád dokola totéž („posílám nabídku",
    „ozvu se příští týden"). Šablona je proto **předvyplnění, ne uzamčení** —
    po vložení se text normálně edituje.

    Zástupné symboly (`{{zakaznik}}`, `{{cislo}}`, `{{moje_jmeno}}`…) doplňuje
    `crm/sablony.py`. Neznámý symbol se **nechává v textu**, ať je vidět, že se
    nedoplnil — tiché smazání by poslalo zákazníkovi větu s dírou.
    """

    __tablename__ = "crm_sablony"

    id = Column(Integer, primary_key=True, index=True)
    druh = Column(String, nullable=False, index=True)  # "email" | "poznamka"
    nazev = Column(String, nullable=False)
    predmet = Column(String, nullable=False, default="", server_default="")
    telo = Column(Text, nullable=False, default="", server_default="")
    # Kde se šablona nabízí: klíč entity ("op", "nab"…) nebo prázdné = všude.
    entita = Column(String, nullable=False, default="", server_default="")
    aktivni = Column(Boolean, nullable=False, default=True, server_default="true")
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmOblibene(Base):
    """Oblíbený a naposledy otevřený záznam (CRM-37).

    Jedna tabulka pro obojí, rozlišené příznakem `oblibene`: je to tentýž pár
    (uživatel, záznam) a dvě tabulky by znamenaly dvě místa, kde po smazání
    záznamu zůstávají osiřelé řádky.

    ---- Proč se to nedrží v prohlížeči ----
    „Naposledy otevřené" má smysl hlavně tehdy, když si člověk sedne k jinému
    počítači nebo pokračuje druhý den. localStorage by obojí ztratil právě
    v tu chvíli, kdy je to potřeba.

    Bez cizího klíče na entitu (stejně jako `CrmNotifikace`): záznam může
    zmizet a odkaz zůstane mrtvý, což je menší zlo než mazat historii. Neplatné
    položky se zahazují až při čtení, kdy se dotahují názvy.
    """

    __tablename__ = "crm_oblibene"
    __table_args__ = (
        UniqueConstraint("uzivatel_id", "entita", "zaznam_id", name="uq_crm_oblibene"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uzivatel_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entita = Column(String, nullable=False)  # klíč z ukoly.ENTITY
    zaznam_id = Column(Integer, nullable=False)
    # True = přišpendlené uživatelem; False = jen prošel kolem (historie).
    oblibene = Column(Boolean, nullable=False, default=False, server_default="false")
    otevreno_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmAudit(Base):
    """Kdo co kdy změnil (CRM-12).

    Historie stavů (`crm_stav_historie`) odpovídá „jak se to hýbalo v pipeline",
    tohle odpovídá na „kdo změnil cenu z 2,5 na 1,9 milionu". Jeden řádek na
    **jedno pole**, ne na uložení formuláře — jinak by v zápisu bylo „změněno 9
    polí" a nikdo by nepoznal které.

    ---- Proč se to sbírá automaticky, ne voláním v endpointech ----
    Zápis obstarává SQLAlchemy událost (`crm/audit.py`), takže se zaloguje
    i změna z místa, na které se při psaní auditu zapomnělo. Ruční volání
    v každém endpointu je přesně ta věc, která se u desátého endpointu vynechá
    a nikdo si toho nevšimne, dokud něco nechybí.

    `stara`/`nova` jsou TEXT, ne původní typ: log se jen čte a zobrazuje, takže
    společný tvar je cennější než přesný typ. `None` a prázdno se ukládá jako
    prázdný řetězec, aby se v UI nemuselo řešit obojí.
    """

    __tablename__ = "crm_audit"

    id = Column(Integer, primary_key=True, index=True)
    entita = Column(String, nullable=False, index=True)
    zaznam_id = Column(Integer, nullable=False, index=True)
    # "zmena" | "vznik" | "smazani" – vznik a smazání nemají pole ani hodnoty.
    druh = Column(String, nullable=False, default="zmena", server_default="zmena")
    pole = Column(String, nullable=False, default="", server_default="")
    stara = Column(Text, nullable=False, default="", server_default="")
    nova = Column(Text, nullable=False, default="", server_default="")
    zmenil_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kdy = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    zmenil = relationship("User")
