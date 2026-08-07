"""Pydantic schémata Nabídkovače. Literaly musí odpovídat enumům v models.py."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Definice vlastních polí spravuje CRM (jedna obrazovka pro všechny entity),
# takže i nabídka posílá stejný tvar – jinak by frontend měl dvě varianty
# téhož a `VlastniPoleVstupy` by je musela rozlišovat.
from app.crm.schemas import VlastniPoleOut

TypNabidky = Literal["ppa", "prodej", "peak_shaving", "kombinace", "ppa_bess"]
StavNabidky = Literal["koncept", "data_nahrana", "zkontrolovano_oz", "spocitano", "hotovo"]
TypTechnologie = Literal["fve_panel", "invertor", "baterie", "jina"]
ZdrojPolozky = Literal["rucne", "bess_cenik", "raynet_import"]
DruhPrilohy = Literal["technicky_list", "foto", "certifikat", "jiny"]
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
    # Číslo z řady CRM a případ, pod který nabídka patří. V modelu to bylo od
    # zavedení CRM, ale detail to neposílal — takže frontend nepoznal, jestli má
    # nabídka zákazníka s odběrnými místy, nebo je to samostatný výpočet.
    cislo: Optional[str] = None
    obchodni_pripad_id: Optional[int] = None
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
    # Vlastní pole nabídky (CRM-04): definice i hodnoty jdou spolu s detailem,
    # ať frontend nemusí na druhý dotaz jen kvůli tomu, co má vykreslit.
    vlastni_pole: list[VlastniPoleOut] = []
    extra: dict = {}
    # Kolik dlaždic v uloženém rozvržení nabídky má ručně přepsanou hodnotu.
    # Patří to i sem, ne jen do editoru: kdo nabídku posílá zákazníkovi, má
    # vidět, že v ní jsou čísla, která nepocházejí z výpočtu.
    vystup_rucnich_hodnot: int = 0


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
    # Hodnoty vlastních polí. `None` = formulář je neposlal (starší klient nebo
    # jiné volání) a `extra` se nesahá; `{}` = uživatel je vyprázdnil. Bez toho
    # rozlišení by každé uložení stavu smazalo doplňující údaje.
    extra: Optional[dict] = None


# ---- Katalog produktů (dřív „katalog technologií“, CRM-08) ----
class PrilohaOut(BaseModel):
    """Soubor u položky katalogu – technický list, foto, certifikát."""

    id: int
    druh: DruhPrilohy
    puvodni_nazev: str
    popis: str = ""
    velikost_bajtu: Optional[int] = None
    nahrano_at: Optional[str] = None
    # True u obrázků – frontend z nich dělá náhledy místo odkazu ke stažení.
    je_obrazek: bool = False


class PrilohaUprava(BaseModel):
    druh: Optional[DruhPrilohy] = None
    popis: Optional[str] = None


class TechnologieOut(BaseModel):
    id: int
    typ: TypTechnologie
    nazev: str
    model: str = ""
    kod: Optional[str] = None
    kategorie: str = ""
    jednotka: str = "ks"
    popis: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    sazba_dph: Optional[float] = None
    ucinnost: Optional[float] = None
    platnost_od: Optional[str] = None
    platnost_do: Optional[str] = None
    zdroj: ZdrojPolozky = "rucne"
    aktivni: bool = True
    # Platí ceník k dnešku? Dopočítává backend z platnosti, ať se to nemusí
    # počítat na třech místech ve frontendu.
    plati_dnes: bool = True
    raynet_id: Optional[str] = None
    # Hodnoty vlastních sloupců katalogu ({klic_sloupce: hodnota}).
    extra: dict = {}
    prilohy: list[PrilohaOut] = []
    # Nákupní cena a marže jen pro právo `nabidkovac_katalog`; ostatním se
    # neposílají vůbec (zůstávají None), ne že by se jen skryly ve frontendu.
    cena_nakup_kc: Optional[float] = None
    marze_kc: Optional[float] = None
    marze_procent: Optional[float] = None


class TechnologieVstup(BaseModel):
    typ: TypTechnologie
    nazev: str
    model: str = ""
    kod: Optional[str] = None
    kategorie: str = ""
    jednotka: str = "ks"
    popis: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    cena_nakup_kc: Optional[float] = None
    sazba_dph: Optional[float] = None
    ucinnost: Optional[float] = None
    platnost_od: Optional[str] = None
    platnost_do: Optional[str] = None
    zdroj: Optional[ZdrojPolozky] = None
    aktivni: bool = True
    extra: dict = {}


class HromadnaUpravaKatalogu(BaseModel):
    """Zapnout/vypnout nebo přeřadit víc položek najednou.

    Vzniklo kvůli importu 244 položek: bez toho by vyřazení celé kategorie
    z ceníku znamenalo 40 kliknutí.
    """

    ids: list[int]
    aktivni: Optional[bool] = None
    kategorie: Optional[str] = None


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


# ---- PPA + BESS (METODIKA-ppa-bess.md, viz nabidkovac/ppa_bess.py) ----
class PpaBessPoleFve(BaseModel):
    """Jedno pole elektrárny s vlastní orientací a výkonem.

    Jméno je schválně dlouhé: v `app/**/schemas.py` se nesmí sejít dvě pydantic
    třídy stejného jména (hlídá `tests/test_kolize_cest.py`), a „PoleFve" by se
    o to samo koledovalo.
    """

    kwp: float
    sklon_st: float = 35.0
    azimut_st: float = 0.0  # 0 = jih, −90 = východ, +90 = západ
    # Nákladová cena za kWp jen pro tohle pole; prázdné = z manažerského
    # nastavení. Jedno pole umí být výrazně dražší (kotvení, delší trasy).
    cena_kc_kwp: Optional[float] = None
    # Východ-západní konstrukce: zadá se jednou a rozloží se na dvě pole 50/50.
    # `azimut_st` se pak bere jako osa (0 = klasické V/Z, tedy −90 a +90).
    rozdelit_vychod_zapad: bool = False


class PpaBessVstup(BaseModel):
    """Vstupy výpočtu PPA+BESS.

    Proti `PpaVstup` přidává to, co je potřeba k ocenění kilowattů (rezervovaná
    kapacita, rezervovaný příkon, distributor), a ruční zadání baterie včetně
    ceny nebo sjednaného nájmu. Profil spotřeby se čte z `spotreba_profil`.

    Volitelná pole (None) doplní `routes.py` z manažerského nastavení nebo
    z kódových defaultů.
    """

    # --- co je potřeba vždy
    distributor: Distributor
    napetova_hladina: NapetovaHladina
    # Rezervovaná kapacita z distribuční smlouvy (kW).
    rezervovana_kapacita_kw: float
    # Silová složka, kterou zákazník platí dnes (Kč/MWh).
    cena_silova_kc_mwh: float
    # Strop velikosti elektrárny (střecha / pozemek / připojení).
    max_kwp: Optional[float] = None

    # --- rezervovaný příkon ze smlouvy o připojení; prázdné = fallback na RK
    rezervovany_prikon_kw: Optional[float] = None

    # --- ceny a doplňky
    vyhnutelne_regulovane_kc_mwh: Optional[float] = None
    cil_mira_samospotreby: Optional[float] = None
    cena_exportu_kc_mwh: Optional[float] = None
    rezervovany_vykon_dodavky_kw: Optional[float] = None

    # --- orientace elektrárny
    # Použije se, když se velikost navrhuje (tj. `pole` je prázdné).
    sklon_st: float = 35.0
    azimut_st: float = 0.0  # 0 = jih, ±90 = V/Z, 180 = sever
    # Rozpad na pole („na jih 200 kWp, na východ 100, na západ 100"). Když je
    # vyplněný, velikost se NENAVRHUJE – je daná součtem výkonů, a `max_kwp`
    # ani cíl samospotřeby ji už neovlivní.
    pole: Optional[list[PpaBessPoleFve]] = None

    # --- baterie: buď ručně, nebo z katalogu
    # Ruční zadání má přednost. Kapacita a výkon jsou povinné, účinnost
    # a využitelný podíl kapacity (SOC okno) mají default.
    baterie_kapacita_kwh: Optional[float] = None
    baterie_vykon_kw: Optional[float] = None
    baterie_ucinnost_rt: Optional[float] = None
    baterie_vyuzitelny_podil: Optional[float] = None
    # Cena: nákladová (z ní se nájem dopočítá) a/nebo sjednaný nájem (vezme se,
    # jak je). Když jsou obě, výpočet ukáže, jak se rozcházejí.
    baterie_nakladova_cena_kc: Optional[float] = None
    baterie_najem_kc_mesic: Optional[float] = None
    # Na kolik let se baterie pronajímá a financuje (default 10). Nezávisí na
    # délce kontraktu na elektrárnu – delší nájem znamená nižší měsíční platbu,
    # ale pozdější odkup.
    baterie_doba_najmu_roky: Optional[int] = None
    # Zúžení katalogu, když se baterie nezadává ručně (id z `technologie`).
    baterie_ids: Optional[list[int]] = None

    # --- ostatní
    nabizene_delky_roky: Optional[list[int]] = None


# ---- Nabídková šablona / výstup (viz sablona_katalog.py) ----
# Typy řešení, pro které existuje nabídková šablona (viz sablona_katalog).
# "kombinace" spojuje PPA a peak shaving do jednoho dokumentu.
TypReseniVystup = Literal["ppa", "peak_shaving", "kombinace", "ppa_bess"]
# Druhy prvků, které jdou položit na papír.
#   kontejner     – rámeček, uvnitř kterého prvky stojí pod sebou
#   text          – formátovaný odstavec (HTML, čistí se přes vystup_html)
#   udaj          – jedna dlaždice s hodnotou z výpočtu
#   graf, tabulka – data řešení
#   obrazek       – nahraný soubor
#   cara, obdelnik, cislo_stranky – grafické drobnosti
DruhPrvku = Literal[
    "kontejner", "text", "udaj", "graf", "tabulka",
    "obrazek", "cara", "obdelnik", "cislo_stranky",
]

# Papír je natvrdo A4 na výšku. Souřadnice prvků jsou v milimetrech vůči
# levému hornímu rohu rodiče (stránky nebo kontejneru).
A4_SIRKA_MM = 210.0
A4_VYSKA_MM = 297.0

# Meze proti nesmyslným/škodlivým konfiguracím. Prvek smí kus přesahovat
# (editor na to upozorní), ale ne skončit kilometr za papírem.
MIN_SOURADNICE_MM = -100.0
MAX_SOURADNICE_MM = 400.0
MAX_STRANEK = 50
MAX_PRVKU_NA_STRANCE = 300
MAX_DETI_KONTEJNERU = 100

# Barva je buď prázdná (= průhledné/zděděné), nebo #rrggbb.
_BARVA = r"^(#[0-9a-fA-F]{6})?$"


class VystupStyl(BaseModel):
    """Vzhled prvku. Prázdná barva znamená „nekreslit“, ne černou."""

    pozadi: str = Field(default="", pattern=_BARVA)
    barva_ramecku: str = Field(default="", pattern=_BARVA)
    sirka_ramecku: float = Field(default=0, ge=0, le=10)  # mm
    zaobleni: float = Field(default=0, ge=0, le=40)  # mm
    odsazeni: float = Field(default=4, ge=0, le=40)  # mm, vnitřní okraj
    mezera: float = Field(default=4, ge=0, le=40)  # mm mezi dětmi kontejneru
    pruhlednost: float = Field(default=1, ge=0, le=1)
    # Kolik dětí vedle sebe uvnitř kontejneru. 1 = pod sebou (výchozí),
    # víc = mřížka, aby dlaždice s údaji stály v řadě jako dřív.
    sloupce: int = Field(default=1, ge=1, le=6)


class VystupPrvek(BaseModel):
    """Jeden prvek na papíře.

    Prvek leží buď přímo na stránce (pak platí `x`/`y`), nebo v kontejneru –
    tam se souřadnice ignorují a prvky stojí pod sebou v pořadí, v jakém jsou
    v `deti`. Kontejner do kontejneru nepatří (hlídá validátor níž): jedna
    úroveň vnoření stačí a chová se předvídatelně při tažení.
    """

    id: str = Field(min_length=1, max_length=64)
    druh: DruhPrvku
    viditelny: bool = True

    x: float = Field(default=0, ge=MIN_SOURADNICE_MM, le=MAX_SOURADNICE_MM)
    y: float = Field(default=0, ge=MIN_SOURADNICE_MM, le=MAX_SOURADNICE_MM)
    sirka: float = Field(default=60, gt=0, le=MAX_SOURADNICE_MM)
    vyska: float = Field(default=20, gt=0, le=MAX_SOURADNICE_MM)
    # True = výška se řídí obsahem (text, kontejner), uložená `vyska` je jen
    # poslední naměřená hodnota pro odhad přetečení.
    auto_vyska: bool = True
    z: int = Field(default=0, ge=0, le=9999)  # pořadí vrstev v rámci rodiče
    zamceno: bool = False

    styl: VystupStyl = VystupStyl()

    html: str = ""  # jen druh text; sanitizuje se při ukládání
    klic: str = Field(default="", max_length=64)  # druh udaj
    pole: list[str] = []  # druh tabulka: vybrané sloupce
    # Druh tabulka: kterou tabulku prvek ukazuje (`sablona_katalog._TABULKY`).
    # Prázdné = roční vývoj úspory, aby rozvržení uložená před zavedením druhé
    # tabulky (odkup elektrárny) fungovala dál bez migrace.
    tabulka_klic: str = Field(default="", max_length=32)
    obrazek: str = Field(default="", max_length=255)  # relativní cesta v úložišti
    popis: str = Field(default="", max_length=255)  # alt text obrázku
    # Druh udaj: ručně přepsaná hodnota. Prázdné = tiskne se to, co spočítal
    # výpočet; neprázdné má přednost. Whitelist klíčů tím neztrácí smysl (klíč
    # musí být dál z katalogu), ale číslo na papíře už nemusí odpovídat
    # výsledku – proto se přepis v editoru zvlášť značí a počítá se, kolik
    # jich nabídka má (viz `pocet_rucnich_hodnot`).
    rucni_hodnota: str = Field(default="", max_length=120)

    deti: list["VystupPrvek"] = []

    @field_validator("deti")
    @classmethod
    def _hlidej_vnoreni(cls, deti: list["VystupPrvek"]) -> list["VystupPrvek"]:
        if len(deti) > MAX_DETI_KONTEJNERU:
            raise ValueError(f"Kontejner smí mít nejvýš {MAX_DETI_KONTEJNERU} prvků.")
        for dite in deti:
            if dite.druh == "kontejner":
                raise ValueError("Kontejner nelze vložit do jiného kontejneru.")
        return deti


class VystupStranka(BaseModel):
    """Jedna pevná A4 na výšku."""

    id: str = Field(min_length=1, max_length=64)
    prvky: list[VystupPrvek] = []

    @field_validator("prvky")
    @classmethod
    def _hlidej_pocet(cls, prvky: list[VystupPrvek]) -> list[VystupPrvek]:
        if len(prvky) > MAX_PRVKU_NA_STRANCE:
            raise ValueError(f"Na stránce smí být nejvýš {MAX_PRVKU_NA_STRANCE} prvků.")
        return prvky


class VystupPas(BaseModel):
    """Opakující se pruh (hlavička/zápatí) – pevný, jen zap/vyp a obsah."""

    zobrazit: bool = True
    text: str = Field(default="", max_length=500)


class VystupVodoznak(BaseModel):
    zobrazit: bool = True
    pruhlednost: float = Field(default=0.07, ge=0, le=0.5)


class VystupKonfigurace(BaseModel):
    """Celý dokument nabídky: pevné A4 stránky s volně umístěnými prvky.

    `verze` odděluje tenhle model od původního plochého seznamu bloků
    v mřížce 12 sloupců. Starší uložené konfigurace se nemigrují – v době
    přepisu byly v provozu jen tři a Dan zvolil čistý start; cokoli bez
    `verze: 2` se zahodí a nahradí výchozí předlohou (viz sablona_katalog).
    """

    verze: Literal[2] = 2
    stranky: list[VystupStranka] = []
    hlavicka: VystupPas = VystupPas()
    zapati: VystupPas = VystupPas()
    vodoznak: VystupVodoznak = VystupVodoznak()
    # Délka kontraktu, kterou nabídka ukazuje. Týká se typů, které počítají víc
    # délek naráz (dnes `ppa_bess`): bez ní se vezme nejdelší nabízená, protože
    # má největší slevu. Ukládá se s rozvržením, aby volba u nabídky zůstala.
    delka_kontraktu_roky: Optional[int] = None

    @field_validator("delka_kontraktu_roky")
    @classmethod
    def _hlidej_delku(cls, delka: Optional[int]) -> Optional[int]:
        if delka is not None and not (1 <= delka <= 40):
            raise ValueError("Délka kontraktu musí být 1–40 let.")
        return delka

    @field_validator("stranky")
    @classmethod
    def _hlidej_stranky(cls, stranky: list[VystupStranka]) -> list[VystupStranka]:
        if len(stranky) > MAX_STRANEK:
            raise ValueError(f"Nabídka smí mít nejvýš {MAX_STRANEK} stránek.")
        return stranky


class VystupSablonaOut(BaseModel):
    """Pojmenovaná šablona rozvržení (bez zákaznických čísel).

    `pouzitelna=False` znamená šablonu z původního modelu (plochý seznam bloků
    v mřížce 12 sloupců). Nový editor ji otevřít neumí, ale v seznamu zůstává,
    aby ji šlo aspoň smazat – jinak by v databázi uvízla navždy.
    """

    id: int
    nazev: str
    konfigurace: VystupKonfigurace
    aktualizovano_at: Optional[str] = None
    pouzitelna: bool = True


class VystupSablonaZNabidky(BaseModel):
    """Rozvržení převzaté z jiné nabídky – „udělej to jako tehdy“."""

    nabidka_id: int
    nazev: str
    konfigurace: VystupKonfigurace


class VystupSablonySeznam(BaseModel):
    sablony: list[VystupSablonaOut] = []
    nabidky: list[VystupSablonaZNabidky] = []


class VystupSablonaVstup(BaseModel):
    nazev: str
    konfigurace: VystupKonfigurace


class VystupPdfVstup(BaseModel):
    """Podklad pro tisk: hotová podoba papíru z prohlížeče.

    Posílá se celý dokument (styly + papír + obrázky v data: URI), protože papír
    vykresluje React a jediné místo, kde existuje ve finální podobě, je
    prohlížeč. Server ho nerozebírá — pouze předá Chromiu k vytištění, a to
    v izolovaném procesu bez sítě, takže obsah nikam dál neteče.
    """

    html: str


class VystupOut(BaseModel):
    """Vše, co frontend potřebuje k vykreslení náhledu i editoru."""

    typ_reseni: TypReseniVystup
    existuje_reseni: bool
    je_vychozi: bool  # True = ještě neuloženo, jede se z výchozí předlohy
    konfigurace: VystupKonfigurace
    katalog: dict = {}  # dostupná pole + sloupce tabulky pro editor
    zakaznik: dict = {}  # nazev/adresa/datum pro hlavičku
    hodnoty: dict[str, Any] = {}  # {klic: {nazev, format, hodnota, hodnota_text}}
    tabulka: dict = {}  # roční tabulka {nazev, sloupce, radky} – pro prvky bez klíče
    tabulky: dict[str, Any] = {}  # {tabulka_klic: {nazev, sloupce, radky}}
    graf: Optional[dict] = None  # surová data grafu (dle typ_reseni)
    # Délky kontraktu, mezi kterými se u tohohle typu dá vybírat. Prázdné =
    # typ víc délek nepočítá a přepínač se v editoru neukáže.
    nabizene_delky_roky: list[int] = []
    # Kolik dlaždic má ručně přepsanou hodnotu (viz VystupPrvek.rucni_hodnota).
    # Počítá server, ať editor i detail nabídky mluví o témže čísle.
    rucnich_hodnot: int = 0


# ---- Rozpis položek nabídky / objednávky (CRM-08) ----
class PolozkaVstup(BaseModel):
    """Jeden řádek rozpisu při ukládání.

    `id` je vyplněné u řádku, který už v DB existuje (aktualizuje se), prázdné
    u nového. Ukládá se celý rozpis najednou, ne řádek po řádku – editor je
    tabulka a člověk v ní přeskládá víc věcí naráz.

    `technologie_id` je jen odkaz do katalogu; název a ceny se ukládají tak,
    jak přijdou z formuláře (snapshot), takže položka mimo katalog projde
    stejnou cestou.
    """

    id: Optional[int] = None
    technologie_id: Optional[int] = None
    kod: str = ""
    nazev: str
    popis: str = ""
    jednotka: str = "ks"
    mnozstvi: float = 1
    cena_jednotkova: Optional[float] = None
    nakup_jednotkovy: Optional[float] = None
    sleva_procent: float = 0
    sazba_dph: Optional[float] = None


class PolozkyVstup(BaseModel):
    """Celý rozpis. Pořadí řádků = pořadí v seznamu."""

    polozky: list[PolozkaVstup] = []


class PolozkySouhrn(BaseModel):
    pocet: int = 0
    bez_dph: float = 0
    dph: float = 0
    s_dph: float = 0
    nakup_celkem: Optional[float] = None
    marze_kc: Optional[float] = None
    marze_procent: Optional[float] = None


class PolozkyOut(BaseModel):
    """Rozpis + spočítaný souhrn. Souhrn počítá backend, ať se čísla v appce
    a na tiskové nabídce nemůžou rozejít zaokrouhlením v JavaScriptu."""

    polozky: list[dict] = []
    souhrn: PolozkySouhrn
    # True, jen když volající smí vidět nákupní ceny (právo katalogu).
    vidi_nakup: bool = False
