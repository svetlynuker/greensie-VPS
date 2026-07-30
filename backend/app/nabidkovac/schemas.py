"""Pydantic schémata Nabídkovače. Literaly musí odpovídat enumům v models.py."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

TypNabidky = Literal["ppa", "prodej", "peak_shaving", "kombinace"]
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


class DokumentUprava(BaseModel):
    """Ruční přepnutí typu už nahraného dokumentu (automat podle přípony minul)."""

    typ: TypDokumentu


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
# Co má baterie dělat (drží se `spot_arbitraz.REZIMY`).
RezimBaterie = Literal["peak_shaving", "kombinace", "spot"]


class PeakShavingVstup(BaseModel):
    """Vstupy, které OZ zadá/vybere (METODIKA kap. 2). Profil odběru se čte
    z uložené tabulky `spotreba_profil` dané nabídky.

    Výběr varianty se řídí ekonomikou roku 2026 (jediné dnes známé sazby);
    ekonomika 2027 se do výstupu přidává zvlášť (kap. 5) a dokud ERÚ nezveřejní
    sazby, zobrazí se u ní „čeká se na oficiální sazby ERÚ“."""

    distributor: Distributor
    napetova_hladina: NapetovaHladina
    rezervovana_kapacita_kw: float
    # Cena energie pro ocenění ztrát baterie, Kč/MWh bez DPH (audit PS-5);
    # prázdné = manažerské nastavení `ps_cena_energie_kc_mwh` (default 3000).
    cena_energie_kc_mwh: Optional[float] = None
    # Rezervovaný příkon ze smlouvy o připojení – pro model 2027 (audit PS-4).
    # Prázdné = fallback na současnou RK (s upozorněním ve výstupu).
    rezervovany_prikon_kw: Optional[float] = None
    # Uvažovat snížení RP na novou RK v modelu 2027 (jednosměrné rozhodnutí –
    # zpětné navýšení je zpoplatněno dle přílohy 2 vyhlášky č. 16/2016 Sb.).
    uvazovat_snizeni_rp: bool = False
    # Ruční override max. AC výkonu střídače (kW) – u modulárních baterií
    # roste kapacita s počtem kusů, ale výkon bývá omezen sdíleným/pevným
    # střídačem (PCS). Prázdné = počítá se jen ze štítkového výkonu produktu.
    max_vykon_stridace_kw: Optional[float] = None
    # Ruční výběr baterií z katalogu (id z `technologie`). Prázdné/None =
    # počítá se celý dostupný katalog. Zúžení výběr zrychlí a zpřehlední.
    baterie_ids: Optional[list[int]] = None

    # Co má baterie dělat (viz spot_arbitraz.REZIMY):
    #  - `peak_shaving` (výchozí) – jen sráží špičky, dnešní chování,
    #  - `kombinace` – sráží špičky a ve zbytku obchoduje na spotovém trhu,
    #  - `spot` – jen obchoduje (rezervovaná kapacita zůstává, jak je).
    rezim: RezimBaterie = "peak_shaving"
    # Rok referenčních spotových cen; prázdné = manažerské nastavení
    # `spot_referencni_rok`, jinak nejnovější rok v DB.
    spot_referencni_rok: Optional[int] = None
    # Limit dodávky do sítě (kW). Prázdné = výkon baterie. 0 = bez dodávky
    # (baterie jen posouvá vlastní spotřebu).
    max_export_kw: Optional[float] = None


class VariantaDetailVstup(BaseModel):
    """Pořadí varianty ve srovnání, které se má dopočítat (0 = doporučená)."""

    index: int


# ---- PPA pro FVE výpočet (METODIKA-ppa-fve.md, kap. 2/4) ----
RezimCapex = Literal["cena_kwp", "komponenty"]


class PpaVstup(BaseModel):
    """Vstupy PPA výpočtu (METODIKA-ppa-v2.md kap. 2).

    Proti v1 se zadání **obrátilo**: OZ nezadává cenu PPA ani délku kontraktu –
    appka je dopočítá z ekonomiky (nejnižší cena, která projde bankou i
    investorem) pro každou nabízenou délku. OZ zadává, co zákazník platí dnes,
    cíl samospotřeby a případná omezení.

    Volitelná pole (None) se v routes.py doplní z manažerského nastavení
    (`vypoctova_nastaveni`) nebo z kódových defaultů. Profil spotřeby se čte
    z `spotreba_profil` dané nabídky.
    """

    # Napěťová hladina. NN je připravená volba, ale výpočet ji zatím odmítne.
    hladina: Literal["VN", "NN"] = "VN"

    # Silová složka ceny, kterou zákazník platí dnes – to, co PPA nahrazuje.
    cena_silova_kc_mwh: float
    # Vyhnutelné regulované složky (za použití sítí ap.); default z nastavení (~260).
    vyhnutelne_regulovane_kc_mwh: Optional[float] = None

    # Cíl míry samospotřeby – podíl **z výroby** (jako v Excelu), default 0,80.
    cil_mira_samospotreby: Optional[float] = None

    # Cena za přetok do sítě. Default z nastavení, kde je 0 = za přetoky se
    # neinkasuje nic (dokud není sjednaný výkup/sdílení).
    cena_exportu_kc_mwh: Optional[float] = None

    # Strop velikosti FVE (střecha / rezervovaný výkon připojení).
    max_kwp: Optional[float] = None

    sklon_st: float = 35.0
    azimut_st: float = 0.0  # 0 = jih, ±90 = V/Z, 180 = sever
    rezervovany_vykon_dodavky_kw: Optional[float] = None

    # Baterie je vždy volitelná varianta. Když se kapacita nezadá, navrhne se
    # heuristicky z denního přebytku.
    s_baterii: bool = False
    baterie_kapacita_kwh: Optional[float] = None
    baterie_vykon_kw: Optional[float] = None
    baterie_nakladova_cena_kc: Optional[float] = None

    # Délky kontraktu, které se zákazníkovi nabídnou (default 10/15/20).
    nabizene_delky_roky: Optional[list[int]] = None


# ---- Nabídková šablona / výstup (viz sablona_katalog.py) ----
# Typy řešení, pro které existuje nabídková šablona (viz sablona_katalog).
# "kombinace" spojuje PPA a peak shaving do jednoho dokumentu.
TypReseniVystup = Literal["ppa", "peak_shaving", "kombinace"]
# `udaj` = jedna dlaždice s hodnotou (tahá se z palety), `zlom` = ruční zlom
# stránky. `udaje` (celý blok s několika poli) zůstává kvůli starším nabídkám.
DruhBloku = Literal["hlavicka", "text", "udaje", "udaj", "graf", "tabulka", "zlom"]

# Šířka prvku v mřížce papíru: 12 sloupců = celá šířka. Editor nabízí 3/4/6/8/12.
SIRKA_PLNA = 12


class VystupBlok(BaseModel):
    """Jeden prvek nabídky.

    `pole` se používá u druhů udaje/tabulka, `klic` u druhu udaj (jedna
    dlaždice). `sirka` je šířka v mřížce papíru (12 = celá) – prvky se skládají
    do řádků po 12 sloupcích, takže dvě dlaždice po 6 stojí vedle sebe.
    Starší uložené nabídky `sirka` nemají a dostanou celou šířku jako dřív.
    """

    id: str
    druh: DruhBloku
    viditelny: bool = True
    nadpis: str = ""
    text: str = ""
    pole: list[str] = []
    klic: str = ""
    sirka: int = Field(default=SIRKA_PLNA, ge=1, le=SIRKA_PLNA)


class VystupKonfigurace(BaseModel):
    bloky: list[VystupBlok] = []


class VystupSablonaOut(BaseModel):
    """Pojmenovaná šablona rozvržení (bez zákaznických čísel)."""

    id: int
    nazev: str
    konfigurace: VystupKonfigurace
    aktualizovano_at: Optional[str] = None


class VystupSablonaZNabidky(BaseModel):
    """Rozvržení převzaté z jiné nabídky – „udělej to jako tehdy"."""

    nabidka_id: int
    nazev: str
    konfigurace: VystupKonfigurace


class VystupSablonySeznam(BaseModel):
    sablony: list[VystupSablonaOut] = []
    nabidky: list[VystupSablonaZNabidky] = []


class VystupSablonaVstup(BaseModel):
    nazev: str
    konfigurace: VystupKonfigurace


class VystupOut(BaseModel):
    """Vše, co frontend potřebuje k vykreslení náhledu i editoru."""

    typ_reseni: TypReseniVystup
    existuje_reseni: bool
    je_vychozi: bool  # True = ještě neuloženo, jede se z výchozí předlohy
    konfigurace: VystupKonfigurace
    katalog: dict = {}  # dostupná pole + sloupce tabulky pro editor
    zakaznik: dict = {}  # nazev/adresa/datum pro hlavičku
    hodnoty: dict[str, Any] = {}  # {klic: {nazev, format, hodnota, hodnota_text}}
    tabulka: dict = {}  # {sloupce, radky}
    graf: Optional[dict] = None  # surová data grafu (dle typ_reseni)
