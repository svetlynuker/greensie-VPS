"""Pydantic schémata Nabídkovače. Literaly musí odpovídat enumům v models.py."""

from typing import Literal, Optional

from pydantic import BaseModel

TypNabidky = Literal["ppa", "prodej", "peak_shaving"]
StavNabidky = Literal["koncept", "data_nahrana", "zkontrolovano_oz", "spocitano", "hotovo"]
TypTechnologie = Literal["fve_panel", "invertor", "baterie", "jina"]
TypDokumentu = Literal["faktura_pdf", "spotreba_csv", "jiny"]
StavZpracovani = Literal["nahrano", "extrahovano", "chyba_extrakce", "rucne_doplneno"]
Distributor = Literal["cez", "egd", "pre"]
NapetovaHladina = Literal["vn", "vvn"]
StrukturaTarifu = Literal["stara_2026", "nova_2027"]


# ---- Nabídky ----
class DokumentOut(BaseModel):
    id: int
    typ: TypDokumentu
    puvodni_nazev: str
    velikost_bajtu: Optional[int] = None
    stav_zpracovani: StavZpracovani
    nahrano_at: Optional[str] = None


class ReseniOut(BaseModel):
    id: int
    typ_reseni: TypNabidky
    popis_json: dict = {}
    vybrano_zakaznikem: Optional[bool] = None


class NabidkaRadekOut(BaseModel):
    """Řádek v seznamu nabídek dané podsekce (zákazník, stav, vytvořil, datum)."""

    id: int
    typ: TypNabidky
    zakaznik_nazev: str
    stav: StavNabidky
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None


class NabidkaDetailOut(BaseModel):
    id: int
    typ: TypNabidky
    zakaznik_nazev: str
    zakaznik_adresa: str = ""
    zakaznik_gps_lat: Optional[float] = None
    zakaznik_gps_lng: Optional[float] = None
    stav: StavNabidky
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None
    vypoctova_nastaveni_id: Optional[int] = None
    dokumenty: list[DokumentOut] = []
    reseni: list[ReseniOut] = []


class NabidkaVstup(BaseModel):
    """Založení nové nabídky. Zákazníka lze doplnit hned, nebo až v detailu."""

    typ: TypNabidky
    zakaznik_nazev: str = ""


class NabidkaUprava(BaseModel):
    zakaznik_nazev: str = ""
    zakaznik_adresa: str = ""
    zakaznik_gps_lat: Optional[float] = None
    zakaznik_gps_lng: Optional[float] = None
    stav: Optional[StavNabidky] = None


# ---- Katalog technologií ----
class TechnologieOut(BaseModel):
    id: int
    typ: TypTechnologie
    nazev: str
    model: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    ucinnost: Optional[float] = None
    dostupnost: bool = True
    raynet_id: Optional[str] = None
    # Hodnoty vlastních sloupců katalogu ({klic_sloupce: hodnota}).
    extra: dict = {}


class TechnologieVstup(BaseModel):
    typ: TypTechnologie
    nazev: str
    model: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    ucinnost: Optional[float] = None
    dostupnost: bool = True
    extra: dict = {}


# ---- Vlastní sloupce katalogu ----
TypSloupce = Literal["text", "cislo"]


class KatalogSloupecOut(BaseModel):
    id: int
    klic: str
    nazev: str
    typ: TypSloupce
    poradi: int = 0


class KatalogSloupecVstup(BaseModel):
    nazev: str
    typ: TypSloupce = "text"
    poradi: int = 0


# ---- Výpočtová nastavení (verzovaná) ----
class VypoctovaNastaveniOut(BaseModel):
    id: int
    verze: int
    platne_od: Optional[str] = None
    koeficient_zisku: Optional[float] = None
    min_delka_kontraktu_roky: Optional[int] = None
    max_delka_kontraktu_roky: Optional[int] = None
    parametry: dict = {}
    vytvoreno_at: Optional[str] = None


class VypoctovaNastaveniVstup(BaseModel):
    """Uložení = založení NOVÉ verze (stará se nepřepisuje)."""

    koeficient_zisku: Optional[float] = None
    min_delka_kontraktu_roky: Optional[int] = None
    max_delka_kontraktu_roky: Optional[int] = None
    parametry: dict = {}


# ---- Sazby distributorů (peak shaving, METODIKA kap. 3.1) ----
class SazbaOut(BaseModel):
    id: int
    distributor: Distributor
    napetova_hladina: NapetovaHladina
    struktura_tarifu: StrukturaTarifu
    # None = struktura připravená, ceny ještě nejsou (typicky nova_2027).
    parametry: Optional[dict] = None
    platne_od: Optional[str] = None
    platne_do: Optional[str] = None
    je_modelovy_odhad: bool = False
    poznamka: str = ""


class SazbaVstup(BaseModel):
    """Založení/úprava sazby přes admin (kap. 6–7). `parametry=None` u nova_2027,
    dokud ERÚ nezveřejní čísla. `je_modelovy_odhad` = nezávazný odhad (2027)."""

    distributor: Distributor
    napetova_hladina: NapetovaHladina
    struktura_tarifu: StrukturaTarifu
    parametry: Optional[dict] = None
    platne_od: str  # ISO datum (YYYY-MM-DD)
    platne_do: Optional[str] = None
    je_modelovy_odhad: bool = False
    poznamka: str = ""


# ---- Peak shaving výpočet (METODIKA kap. 4–5) ----
class PeakShavingVstup(BaseModel):
    """Vstupy, které OZ zadá/vybere (METODIKA kap. 2). Profil odběru se čte
    z uložené tabulky `spotreba_profil` dané nabídky.

    Výběr varianty se řídí ekonomikou roku 2026 (jediné dnes známé sazby);
    ekonomika 2027 se do výstupu přidává zvlášť (kap. 5) a dokud ERÚ nezveřejní
    sazby, zobrazí se u ní „čeká se na oficiální sazby ERÚ“."""

    distributor: Distributor
    napetova_hladina: NapetovaHladina
    rezervovana_kapacita_kw: float


# ---- PPA pro FVE výpočet (METODIKA-ppa-fve.md, kap. 2/4) ----
RezimCapex = Literal["cena_kwp", "komponenty"]


class PpaVstup(BaseModel):
    """Vstupy PPA výpočtu, které OZ zadá ve výpočtovém pohledu (METODIKA kap. 2).

    Volitelná pole (None) se v routes.py doplní z manažerského nastavení
    (`vypoctova_nastaveni`) nebo z kódových defaultů. Profil spotřeby se čte
    z `spotreba_profil` dané nabídky (činný výkon kW → energie kWh × interval).
    """

    sklon_st: float = 35.0
    azimut_st: float = 0.0  # 0 = jih, ±90 = V/Z, 180 = sever
    cena_ppa_kc_mwh: float
    cena_dodavatel_kc_mwh: float
    delka_kontraktu_roky: int

    # Velikost FVE navrhuje appka sama (kap. 4.7). `instalovany_vykon_kwp` je
    # volitelný ruční override; `max_kwp` = limit střechy/připojení pro auto-návrh.
    instalovany_vykon_kwp: Optional[float] = None
    max_kwp: Optional[float] = None

    # Volitelné – default z nastavení / kódu.
    index_ppa_rocni: Optional[float] = None
    index_dodavatel_rocni: Optional[float] = None
    degradace_rocni: Optional[float] = None
    # LID – degradace 1. roku (audit PPA-4); default z nastavení (−2 % PERC).
    degradace_rok1: Optional[float] = None

    # Náklady na FVE (kap. 3.4) – přepínač + volitelný přetok.
    rezim_capex: RezimCapex = "cena_kwp"
    prebytek_uctovat: bool = False
    prebytek_cena_kc_mwh: Optional[float] = None
    rezervovany_vykon_dodavky_kw: Optional[float] = None
