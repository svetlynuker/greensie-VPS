"""Pydantic schémata CRM. Literály musí odpovídat enumům v `crm/models.py`."""

from typing import Literal, Optional

from pydantic import BaseModel

TypZakaznika = Literal["lead", "klient"]
EntitaCrm = Literal["op", "nab", "obj", "pro"]
DruhStavu = Literal["otevreny", "vyhra", "prohra"]
KategorieOp = Literal["prodej", "ppa", "peak_shaving"]
DruhAktivity = Literal["poznamka", "telefon", "email", "schuzka", "ukol"]


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
EntitaPole = Literal["zakaznik", "op"]
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
    kategorie: list[KategorieOp] = []
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
    id: int
    entita: str
    zaznam_id: int
    druh: DruhAktivity
    text: str = ""
    termin: Optional[str] = None
    hotovo: bool = False
    vlastnik_jmeno: Optional[str] = None
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None


class AktivitaVstup(BaseModel):
    druh: DruhAktivity = "poznamka"
    text: str = ""
    termin: Optional[str] = None
    vlastnik_user_id: Optional[int] = None


class AktivitaUprava(BaseModel):
    text: Optional[str] = None
    termin: Optional[str] = None
    hotovo: Optional[bool] = None


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
