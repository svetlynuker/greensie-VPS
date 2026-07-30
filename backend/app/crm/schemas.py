"""Pydantic schémata CRM. Literály musí odpovídat enumům v `crm/models.py`."""

from typing import Any, Literal, Optional

from pydantic import BaseModel

TypZakaznika = Literal["lead", "klient"]
EntitaCrm = Literal["op", "nab", "obj", "pro"]
DruhStavu = Literal["otevreny", "vyhra", "prohra"]
# Kategorie případu ZÁMĚRNĚ není Literal – je to konfigurovatelný seznam
# v tabulce `crm_kategorie` (CRM-03). Validuje se proti DB, ne typem.
# Sada se drží předlohy kalendáře (Úkol, Schůzka, Událost, Telefonát, Dopis);
# `poznamka` a `email` jsou navíc — viz DRUHY_AKTIVITY v models.py.
DruhAktivity = Literal[
    "ukol", "schuzka", "udalost", "telefon", "dopis", "email", "poznamka"
]
PrioritaAktivity = Literal["nizka", "stredni", "vysoka"]
# Naplánováno → realizováno / nekonalo se. Enum je tu na místě (na rozdíl od
# kategorií případu): stavy aktivity nejsou konfigurovatelné, protože na nich
# stojí výpis „moje úkoly" a statistika činnosti.
StavAktivity = Literal["naplanovano", "realizovano", "nekonalo_se"]


# ---- stavy pipeline ----------------------------------------------------------
class StavOut(BaseModel):
    id: int
    entita: EntitaCrm
    klic: str
    nazev: str
    poradi: int
    barva: str = ""
    druh: DruhStavu


class StavVstup(BaseModel):
    nazev: str
    barva: str = ""
    druh: DruhStavu = "otevreny"
    poradi: Optional[int] = None


class StavyPoradi(BaseModel):
    """Nové pořadí sloupců kanbanu – seznam id ve výsledném pořadí."""

    poradi: list[int]


# ---- číselné řady -----------------------------------------------------------
class RadaOut(BaseModel):
    entita: EntitaCrm
    rok: int
    prefix: str
    sirka: int
    dalsi_cislo: int
    pouzito: int
    ukazka: str  # jak bude vypadat příští číslo


class RadaVstup(BaseModel):
    sirka: Optional[int] = None
    dalsi_cislo: Optional[int] = None


# ---- vlastní (admin definovaná) pole ----------------------------------------
EntitaPole = Literal["zakaznik", "op", "obj", "pro"]
TypPole = Literal["text", "dlouhy_text", "cislo", "datum", "ano_ne", "vyber"]


class VlastniPoleOut(BaseModel):
    id: int
    entita: EntitaPole
    klic: str
    nazev: str
    typ: TypPole
    volby: list[str] = []
    napoveda: str = ""
    povinne: bool = False
    v_seznamu: bool = False
    poradi: int = 0


class VlastniPoleVstup(BaseModel):
    nazev: str
    typ: TypPole = "text"
    volby: list[str] = []
    napoveda: str = ""
    povinne: bool = False
    v_seznamu: bool = False
    poradi: Optional[int] = None


class VlastniPoleUprava(BaseModel):
    """Úprava pole. `typ` měnit lze, `klic` nikdy – drží ho uložené hodnoty."""

    nazev: Optional[str] = None
    typ: Optional[TypPole] = None
    volby: Optional[list[str]] = None
    napoveda: Optional[str] = None
    povinne: Optional[bool] = None
    v_seznamu: Optional[bool] = None
    poradi: Optional[int] = None


class VlastniPolePoradi(BaseModel):
    poradi: list[int]


# ---- kontakty ---------------------------------------------------------------
class KontaktOut(BaseModel):
    id: int
    jmeno: str
    funkce: str = ""
    email: str = ""
    telefon: str = ""
    hlavni: bool = False
    poznamka: str = ""


class KontaktVstup(BaseModel):
    jmeno: str
    funkce: str = ""
    email: str = ""
    telefon: str = ""
    hlavni: bool = False
    poznamka: str = ""


# ---- zákazníci --------------------------------------------------------------
class ZakaznikRadekOut(BaseModel):
    """Řádek v seznamu leadů/klientů."""

    id: int
    typ: TypZakaznika
    nazev: str
    ico: str = ""
    adresa_mesto: str = ""
    telefon: str = ""
    email: str = ""
    vlastnik_jmeno: Optional[str] = None
    pocet_pripadu: int = 0
    vytvoreno_at: Optional[str] = None
    # Vlastní pole označená „v seznamu", už naformátovaná k zobrazení.
    extra_text: dict = {}


class ZakaznikDetailOut(BaseModel):
    id: int
    typ: TypZakaznika
    nazev: str
    ico: str = ""
    dic: str = ""
    adresa_ulice: str = ""
    adresa_mesto: str = ""
    adresa_psc: str = ""
    adresa_stat: str = ""
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    web: str = ""
    telefon: str = ""
    email: str = ""
    zdroj: str = ""
    poznamka: str = ""
    vlastnik_user_id: Optional[int] = None
    vlastnik_jmeno: Optional[str] = None
    spoluvlastnici: list[int] = []
    raynet_id: Optional[int] = None
    konvertovan_at: Optional[str] = None
    vytvoreno_at: Optional[str] = None
    kontakty: list[KontaktOut] = []
    extra: dict = {}
    vlastni_pole: list[VlastniPoleOut] = []
    muze_editovat: bool = True


class ZakaznikVstup(BaseModel):
    nazev: str
    typ: TypZakaznika = "lead"
    ico: str = ""
    dic: str = ""
    adresa_ulice: str = ""
    adresa_mesto: str = ""
    adresa_psc: str = ""
    adresa_stat: str = "Česko"
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    web: str = ""
    telefon: str = ""
    email: str = ""
    zdroj: str = ""
    poznamka: str = ""
    # Vlastníka smí nastavit jen ten, kdo vidí všechny záznamy; jinak se
    # ignoruje a vlastníkem je autor (viz routes).
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    # Hodnoty vlastních polí {klic: hodnota}; neznámé klíče backend zahodí.
    extra: dict = {}


class AresOut(BaseModel):
    """Návrh údajů z ARESu + varování na možný duplikát."""

    nazev: str = ""
    ico: str = ""
    dic: str = ""
    adresa_ulice: str = ""
    adresa_mesto: str = ""
    adresa_psc: str = ""
    adresa_stat: str = ""
    duplikat_id: Optional[int] = None
    duplikat_nazev: Optional[str] = None


# ---- obchodní případy -------------------------------------------------------
class PripadRadekOut(BaseModel):
    id: int
    cislo: str
    nazev: str = ""
    zakaznik_id: int
    zakaznik_nazev: str = ""
    kategorie: list[str] = []
    stav: str
    stav_nazev: str = ""
    hodnota_kc: Optional[float] = None
    pravdepodobnost: Optional[int] = None
    predpokladane_uzavreni: Optional[str] = None
    vlastnik_jmeno: Optional[str] = None
    raynet_code: str = ""
    vytvoreno_at: Optional[str] = None
    extra_text: dict = {}


class PripadDetailOut(PripadRadekOut):
    popis: str = ""
    duvod_prohry: str = ""
    uzavreno_at: Optional[str] = None
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    raynet_id: Optional[int] = None
    # Nabídky, které k případu patří (zatím vazba přes nabídkovač – doplní
    # se v druhé dávce). Držíme pole už teď, ať frontend nemusí měnit tvar.
    nabidky: list[dict] = []
    extra: dict = {}
    vlastni_pole: list[VlastniPoleOut] = []
    muze_editovat: bool = True


class PripadVstup(BaseModel):
    zakaznik_id: int
    nazev: str = ""
    popis: str = ""
    # Volný seznam klíčů, ne Literal: kategorie jsou od 30. 7. 2026 data
    # v `crm_kategorie` (vedení si přidá „Servis"), takže enum ve schématu by
    # novou kategorii odmítl už na vstupu. Validace proti tabulce je v routes
    # (`_over_kategorie`) a vrací čitelnou chybu s neznámým klíčem.
    kategorie: list[str] = []
    hodnota_kc: Optional[float] = None
    pravdepodobnost: Optional[int] = None
    predpokladane_uzavreni: Optional[str] = None  # ISO datum
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    # Raynetí číslo existujícího případu – kvůli koexistenci (párování složek
    # na Disku). U případů založených v appce zůstává prázdné.
    raynet_code: str = ""
    extra: dict = {}


class PripadUprava(PripadVstup):
    zakaznik_id: Optional[int] = None  # při úpravě nepovinné (zákazník se nemění)


class ZmenaStavuVstup(BaseModel):
    """Přesun v kanbanu. `duvod_prohry` je povinný u stavu druhu „prohra"."""

    stav: str
    duvod_prohry: str = ""


# ---- nabídky (obchodní pipeline) --------------------------------------------
class NabidkaRadekOut(BaseModel):
    """Řádek/dlaždice v sekci Nabídky. Obsah výpočtu tu není – jen to, co
    obchod potřebuje k rozhodnutí, co s nabídkou dál."""

    id: int
    cislo: str = ""
    typ: str  # ppa / prodej / peak_shaving
    stav: str  # obchodní stav (klíč do crm_stavy, entita "nab")
    stav_nazev: str = ""
    stav_zpracovani: str = ""  # stav výpočtu – jiná osa než obchodní stav
    spocitana: bool = False
    zakaznik_nazev: str = ""
    pripad_id: Optional[int] = None
    pripad_cislo: str = ""
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None


class NabidkaKanbanSloupec(BaseModel):
    stav: StavOut
    zaznamy: list[NabidkaRadekOut] = []
    pocet: int = 0


class NabidkaKanbanOut(BaseModel):
    entita: str = "nab"
    sloupce: list[NabidkaKanbanSloupec] = []


class NabidkaZmenaStavuVstup(BaseModel):
    stav: str


# ---- aktivity ---------------------------------------------------------------
class AktivitaOut(BaseModel):
    """Aktivita v logu práce i v kalendáři.

    `entita`/`zaznam_id` jsou nepovinné kvůli soukromým událostem (dovolená,
    doktor) — ty klienta nemají. `stav` nahradil dřívější boolean `hotovo`,
    aby se odlišila proběhlá schůzka od zrušené.
    """

    id: int
    entita: Optional[str] = None
    zaznam_id: Optional[int] = None
    druh: DruhAktivity
    nazev: str = ""
    text: str = ""
    termin: Optional[str] = None  # den
    zacatek: Optional[str] = None  # den + hodina (kalendář); prázdné = celodenní
    delka_min: Optional[int] = None
    konec: Optional[str] = None  # poslední den vícedenní aktivity
    priorita: PrioritaAktivity = "stredni"
    misto: str = ""
    kategorie_id: Optional[int] = None
    kategorie_nazev: str = ""
    kategorie_barva: str = ""
    stav: StavAktivity = "naplanovano"
    vysledek: str = ""
    soukroma: bool = False
    ucastnici: list[int] = []
    vlastnik_user_id: Optional[int] = None
    vlastnik_jmeno: Optional[str] = None
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None


class KategorieOut(BaseModel):
    """Kategorie případu. `typ_nabidky` prázdný = ke kategorii výpočet není,
    takže se u ní nenabízí tlačítko „+ nabídka" (viz `crm/kategorie.py`)."""

    id: int
    klic: str
    nazev: str
    popis: str = ""
    poradi: int = 0
    typ_nabidky: str = ""
    aktivni: bool = True


class KategorieVstup(BaseModel):
    nazev: str
    popis: str = ""
    typ_nabidky: str = ""
    poradi: Optional[int] = None
    aktivni: Optional[bool] = None


class UkolOut(AktivitaOut):
    """Úkol ve výpisu „moje úkoly" — aktivita plus to, u čeho vlastně visí.

    Bez `zaznam_nazev` a `cesta` by výpis napříč CRM byl seznam textů bez
    kontextu: člověk vidí „zavolat kvůli ceně" a nepozná komu ani kam kliknout.
    `dni` je kladné, když je úkol po termínu (viz `crm/ukoly.py`).
    """

    zaznam_nazev: str = ""
    cesta: str = ""
    dni: int = 0


class AktivitaVstup(BaseModel):
    druh: DruhAktivity = "poznamka"
    nazev: str = ""
    text: str = ""
    termin: Optional[str] = None  # ISO den
    # Čas začátku ve formátu „09:30". Prázdný = celodenní (úkol bez hodiny).
    # Posílá se zvlášť od dne, aby si UI nemuselo skládat ISO datetime.
    cas: Optional[str] = None
    delka_min: Optional[int] = None
    konec: Optional[str] = None
    priorita: PrioritaAktivity = "stredni"
    misto: str = ""
    kategorie_id: Optional[int] = None
    vlastnik_user_id: Optional[int] = None
    ucastnici: list[int] = []


class AktivitaUprava(BaseModel):
    """Částečná úprava — pošle se jen to, co se mění (`None` = neměnit).

    Proto `stav` a `vysledek` zvlášť: „označit jako realizované a napsat, co
    z toho vyšlo" je nejčastější úprava v kalendáři a nemá přepisovat popis.
    """

    nazev: Optional[str] = None
    text: Optional[str] = None
    termin: Optional[str] = None
    cas: Optional[str] = None
    delka_min: Optional[int] = None
    konec: Optional[str] = None
    priorita: Optional[PrioritaAktivity] = None
    misto: Optional[str] = None
    # -1 znamená „zruš kategorii"; None = neměnit. Bez téhle domluvy by se
    # kategorie nedala odebrat, protože None už znamená „nech to být".
    kategorie_id: Optional[int] = None
    stav: Optional[StavAktivity] = None
    vysledek: Optional[str] = None
    ucastnici: Optional[list[int]] = None


class KategorieAktivityOut(BaseModel):
    """Barevný štítek aktivity. Pozor: NENÍ to `KategorieOut` (ta patří
    obchodnímu případu a říká, do kterého výpočtu míří)."""

    id: int
    nazev: str
    barva: str = "#7b8794"
    poradi: int = 0
    aktivni: bool = True


class KategorieAktivityVstup(BaseModel):
    nazev: str
    barva: str = "#7b8794"
    poradi: Optional[int] = None
    aktivni: Optional[bool] = None


# ---- kalendář ---------------------------------------------------------------
class UdalostVstup(BaseModel):
    """Nová událost zakládaná z kalendáře.

    Liší se od `AktivitaVstup` tím, že si nese, čeho se týká: klik do mřížky
    ještě neví, jestli půjde o schůzku u klienta, nebo o soukromý blok. Buď se
    pošle `entita` + `zaznam_id` (obojí, nebo nic), nebo `soukroma=True`.
    """

    druh: DruhAktivity = "schuzka"
    nazev: str
    text: str = ""
    termin: str  # ISO den, povinný — událost bez data v kalendáři nemá místo
    cas: Optional[str] = None  # „09:30"; prázdné = celodenní
    delka_min: Optional[int] = None
    konec: Optional[str] = None  # ISO den; vyplněné = vícedenní
    priorita: PrioritaAktivity = "stredni"
    misto: str = ""
    kategorie_id: Optional[int] = None
    stav: StavAktivity = "naplanovano"
    vysledek: str = ""
    entita: Optional[str] = None
    zaznam_id: Optional[int] = None
    soukroma: bool = False
    vlastnik_user_id: Optional[int] = None
    ucastnici: list[int] = []


class KalendarUdalostOut(BaseModel):
    """Jedna událost v kalendáři — a to, kolik se o ní smí prozradit.

    `muze_detail=False` znamená, že uživatel vidí jen obsazený čas: `nazev` je
    „Soukromá událost" nebo „Obsazeno" a obsahová pole jsou prázdná už
    z backendu. Schovávat je až v prohlížeči by nestačilo — v odpovědi API by
    si je přečetl kdokoli (viz `crm/kalendar.py`).
    """

    id: int
    druh: DruhAktivity
    nazev: str = ""
    text: str = ""
    vysledek: str = ""
    stav: StavAktivity = "naplanovano"
    termin: Optional[str] = None
    zacatek: Optional[str] = None
    delka_min: int = 30
    cely_den: bool = False
    konec: Optional[str] = None
    vicedenni: bool = False
    priorita: PrioritaAktivity = "stredni"
    misto: str = ""
    kategorie_nazev: str = ""
    kategorie_barva: str = ""
    soukroma: bool = False
    entita: Optional[str] = None
    zaznam_id: Optional[int] = None
    zaznam_nazev: str = ""
    cesta: str = ""
    ucastnici: list[int] = []
    vlastnik_user_id: Optional[int] = None
    vlastnik_jmeno: Optional[str] = None
    muze_detail: bool = True


class KalendarOut(BaseModel):
    """Týden v kalendáři. `od`/`do` posílá backend zpátky schválně — UI si tak
    nemusí samo počítat, na které pondělí dotaz vlastně spadl."""

    od: str
    do: str
    udalosti: list[KalendarUdalostOut] = []


# ---- kanban -----------------------------------------------------------------
class KanbanSloupec(BaseModel):
    stav: StavOut
    zaznamy: list[PripadRadekOut] = []
    pocet: int = 0
    soucet_kc: Optional[float] = None


class KanbanOut(BaseModel):
    entita: EntitaCrm
    sloupce: list[KanbanSloupec] = []


# ---- souhrn pro uživatele ---------------------------------------------------
class UzivatelVolbaOut(BaseModel):
    """Uživatel do výběru vlastníka / spoluvlastníků."""

    id: int
    jmeno: str


# ---- objednávky --------------------------------------------------------------
class ObjednavkaRadekOut(BaseModel):
    id: int
    cislo: str
    nazev: str = ""
    pripad_id: int
    pripad_cislo: str = ""
    zakaznik_nazev: str = ""
    nabidka_id: Optional[int] = None
    nabidka_cislo: str = ""
    cena_kc: Optional[float] = None
    datum_podpisu: Optional[str] = None
    datum_dodani: Optional[str] = None
    stav: str
    stav_nazev: str = ""
    vlastnik_jmeno: Optional[str] = None
    ma_projekt: bool = False
    vytvoreno_at: Optional[str] = None
    extra_text: dict = {}


class ObjednavkaDetailOut(ObjednavkaRadekOut):
    popis: str = ""
    duvod_zruseni: str = ""
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    extra: dict = {}
    vlastni_pole: list[VlastniPoleOut] = []
    projekt_id: Optional[int] = None
    projekt_cislo: str = ""
    muze_editovat: bool = True


class ObjednavkaVstup(BaseModel):
    """Založení objednávky. `nabidka_id` = z které nabídky vzniká (nepovinné,
    ale obvyklé – převezme se z ní cena)."""

    obchodni_pripad_id: Optional[int] = None
    nabidka_id: Optional[int] = None
    nazev: str = ""
    popis: str = ""
    cena_kc: Optional[float] = None
    datum_podpisu: Optional[str] = None
    datum_dodani: Optional[str] = None
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    extra: dict = {}


class ObjednavkaZmenaStavuVstup(BaseModel):
    stav: str
    duvod_zruseni: str = ""


# ---- projekty ----------------------------------------------------------------
class KrokOut(BaseModel):
    id: int
    nazev: str
    popis: str = ""
    poradi: int
    stav: str
    delka_dni: int = 1
    zavisi_na_id: Optional[int] = None
    zavisi_na_nazev: str = ""
    termin: Optional[str] = None
    termin_rucne: bool = False
    hotovo_at: Optional[str] = None
    odpovedny_user_id: Optional[int] = None
    odpovedny_jmeno: Optional[str] = None
    # Může se na kroku začít pracovat (předchůdce hotový)?
    dostupny: bool = True
    po_terminu: bool = False


class KrokVstup(BaseModel):
    nazev: str
    popis: str = ""
    delka_dni: int = 1
    zavisi_na_id: Optional[int] = None
    termin: Optional[str] = None
    odpovedny_user_id: Optional[int] = None


class KrokUprava(BaseModel):
    nazev: Optional[str] = None
    popis: Optional[str] = None
    stav: Optional[str] = None
    delka_dni: Optional[int] = None
    zavisi_na_id: Optional[int] = None
    termin: Optional[str] = None
    odpovedny_user_id: Optional[int] = None


class ProjektRadekOut(BaseModel):
    id: int
    cislo: str
    nazev: str = ""
    pripad_id: int
    pripad_cislo: str = ""
    zakaznik_nazev: str = ""
    objednavka_cislo: str = ""
    stav: str
    stav_nazev: str = ""
    zahajeni: Optional[str] = None
    predani: Optional[str] = None
    vlastnik_jmeno: Optional[str] = None
    # Souhrn kroků: kolik hotovo, nejbližší termín, kolik po termínu
    kroku: int = 0
    hotovo: int = 0
    procent: int = 0
    nejblizsi_termin: Optional[str] = None
    po_terminu: int = 0
    freelo_projekt_id: Optional[int] = None
    vytvoreno_at: Optional[str] = None
    extra_text: dict = {}


class ProjektDetailOut(ProjektRadekOut):
    popis: str = ""
    objednavka_id: Optional[int] = None
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    extra: dict = {}
    vlastni_pole: list[VlastniPoleOut] = []
    kroky_seznam: list[KrokOut] = []
    muze_editovat: bool = True


class ProjektVstup(BaseModel):
    """Projekt vzniká JEN z objednávky nebo z případu – proto je vždy potřeba
    jedno z nich (viz kontrola v routes)."""

    obchodni_pripad_id: Optional[int] = None
    objednavka_id: Optional[int] = None
    nazev: str = ""
    popis: str = ""
    zahajeni: Optional[str] = None
    predani: Optional[str] = None
    sablona_id: Optional[int] = None  # rozbalit kroky podle šablony
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    extra: dict = {}


class ProjektUprava(BaseModel):
    nazev: str = ""
    popis: str = ""
    zahajeni: Optional[str] = None
    predani: Optional[str] = None
    freelo_projekt_id: Optional[int] = None
    vlastnik_user_id: Optional[int] = None
    spoluvlastnici: list[int] = []
    extra: dict = {}


class ProjektZmenaStavuVstup(BaseModel):
    stav: str


# ---- šablony projektových kroků ---------------------------------------------
class SablonaKrokOut(BaseModel):
    id: int
    nazev: str
    popis: str = ""
    poradi: int
    delka_dni: int = 1
    zavisi_na_poradi: Optional[int] = None


class SablonaKrokVstup(BaseModel):
    nazev: str
    popis: str = ""
    delka_dni: int = 1
    zavisi_na_poradi: Optional[int] = None


class SablonaOut(BaseModel):
    id: int
    nazev: str
    popis: str = ""
    kategorie: list[str] = []
    kroky: list[SablonaKrokOut] = []


class SablonaVstup(BaseModel):
    nazev: str
    popis: str = ""
    kategorie: list[str] = []


# ---- uživatelské filtry ------------------------------------------------------
EntitaFiltru = Literal["zakaznik", "op", "nab", "obj", "pro"]
OperatorFiltru = Literal[
    "obsahuje", "neobsahuje", "je", "neni", "je_jeden_z",
    "vetsi", "mensi", "mezi", "je_prazdne", "neni_prazdne",
]
SmerRazeni = Literal["asc", "desc"]


class PodminkaFiltru(BaseModel):
    pole: str
    operator: OperatorFiltru
    # Hodnota může být text, číslo, seznam (je_jeden_z) nebo dvojice (mezi).
    hodnota: Any = None


class RazeniFiltru(BaseModel):
    pole: str
    smer: SmerRazeni = "asc"


class UlozenyFiltrOut(BaseModel):
    id: int
    entita: EntitaFiltru
    nazev: str
    podminky: list[PodminkaFiltru] = []
    razeni: list[RazeniFiltru] = []
    sdileny: bool = False
    vychozi: bool = False
    poradi: int = 0
    vlastnik_user_id: int
    vlastnik_jmeno: Optional[str] = None
    muj: bool = True  # smí ho volající upravit?


class UlozenyFiltrVstup(BaseModel):
    nazev: str
    podminky: list[PodminkaFiltru] = []
    razeni: list[RazeniFiltru] = []
    sdileny: bool = False
    vychozi: bool = False
