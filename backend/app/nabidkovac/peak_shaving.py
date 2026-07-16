"""Výpočetní jádro Peak shaving (METODIKA-peak-shaving.md, kap. 4).

Čistě deterministický výpočet (žádní AI agenti – viz kap. 1 SPEC-nabidkovac.md).
Modul je záměrně bez závislosti na DB a FastAPI: pracuje jen s prostými
seznamy 15minutových hodnot odběru (kW) a čísly ze sazebníku, aby šel snadno
testovat i volat z různých míst. Napojení na DB/API řeší routes.py.

Klíčové vzorce a rozhodnutí přebíráme 1:1 z metodiky:
- kap. 4.1 – výchozí roční náklad (rezervace + pokuty za překročení),
- kap. 4.2 – simulace baterie po 15min intervalech (nabíjení = vybíjení,
  kapacita 1:1 bez ztrát a bez DoD limitu – odsouhlasené zjednodušení v1),
- kap. 4.3 – binární hledání nejnižší udržitelné rezervované kapacity T,
- kap. 4.4/4.5 – roční úspora, návratnost, výběr nejrychlejší varianty,
- kap. 4.6 – struktura roku 2027 (srážej co to dá + min(sazba A, B)).

Všechny peněžní hodnoty jsou bez DPH (kap. 6 bod 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Granularita vstupních dat: 15 min = 0,25 h. Použije se, když ji nejde
# odvodit z časových značek profilu (kap. 4.2 – "dle granularity vstupních dat").
VYCHOZI_INTERVAL_H = 0.25

# Výchozí práh nedoporučené návratnosti (kap. 4.5, bod 3 v kap. 6). Reálně se
# bere z vypoctova_nastaveni.parametry["max_navratnost_roky_peak_shaving"],
# tohle je fallback, když parametr chybí.
VYCHOZI_MAX_NAVRATNOST_ROKY = 5.0

# Rozsah počtu kusů baterie, který se zkouší pro každý produkt (kap. 4.5:
# "rozumný rozsah počtu kusů, např. 1–5").
VYCHOZI_MAX_POCET_KUSU = 5

# Tolerance binárního hledání T v kW (kap. 4.3). 0,01 kW je hluboko pod
# přesností, se kterou se sjednává rezervovaná kapacita.
_BINARNI_TOLERANCE_KW = 0.01

# Překročení rezervované kapacity (bod 4.24 CV ERÚ): platba = 1,5× měsíční
# cena za MĚSÍČNÍ rezervovanou kapacitu za každý kW nejvyššího čtvrthodinového
# překročení v kalendářním měsíci.
NASOBEK_POKUTY_PREKROCENI_RK = 1.5


def pokuta_prekroceni_rk_kc_kw(cena_mesicni_rk_kc_kw_mesic: float) -> float:
    """Sazba pokuty za překročení RK (Kč/kW/měsíc) odvozená z měsíční RK.

    Bod 4.24 cenového výměru ERÚ: 1,5× měsíční cena za měsíční RK. Odvozuje se
    výpočtem (ne samostatným číslem v sazebníku), aby se při roční aktualizaci
    sazeb nemohla rozjet od cen RK (audit 16. 7. 2026, bughunt PS-2).
    """
    return NASOBEK_POKUTY_PREKROCENI_RK * cena_mesicni_rk_kc_kw_mesic


# ------------------------------------------------------------------ simulace
def _max_udrzitelny_vyboj(soc_kwh: float, vykon_kw: float, interval_h: float) -> float:
    """Max. okamžitý výkon (kW), který baterie zvládne dodat po celý interval.

    Omezuje ho jak štítkový výkon, tak zbývající energie (nesmí se vybít pod 0).
    """
    z_energie = soc_kwh / interval_h if interval_h > 0 else 0.0
    return min(vykon_kw, z_energie)


def strop_je_udrzitelny(
    profil_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    pocatecni_soc_kwh: float | None = None,
) -> bool:
    """Projede profil interval po intervalu a řekne, jestli baterie udrží strop.

    Implementace kap. 4.2: nad stropem baterie dodává `min(odběr − T, výkon)`
    (omezeno stavem nabití); pokud jí dojde energie dřív, než odběr klesne pod
    strop, strop se neudrží → False. Pod stropem se dobíjí max. výkonem,
    omezeně volnou kapacitou a rozdílem `T − odběr` (jen z rezervy pod stropem,
    ne z ničeho navíc).

    Počáteční stav nabití: defaultně plná baterie (kap. 4.2 zavádí zjednodušení
    1:1 bez ztrát; předpokládáme, že baterii lze před špičkou nabít – nejde-li
    strop udržet ani s plnou baterií, nejde vůbec). Explicitně se dá přepsat.
    """
    if vykon_kw <= 0 or kapacita_kwh <= 0:
        # Bez baterie se udrží jen strop, který profil nikdy nepřekročí.
        return all(odber <= strop_kw for odber in profil_kw)

    soc = kapacita_kwh if pocatecni_soc_kwh is None else pocatecni_soc_kwh
    for odber in profil_kw:
        if odber > strop_kw:
            potreba = odber - strop_kw
            dodavka = min(potreba, _max_udrzitelny_vyboj(soc, vykon_kw, interval_h))
            if dodavka + 1e-9 < potreba:
                return False  # baterie nestačí → strop se neudrží
            soc -= dodavka * interval_h
        else:
            # Dobíjení jen z rezervy pod stropem (T − odběr), max. výkonem.
            rezerva = min(strop_kw - odber, vykon_kw)
            soc = min(kapacita_kwh, soc + rezerva * interval_h)
    return True


def min_udrzitelny_strop(
    profil_kw: list[float],
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> float:
    """Kap. 4.3: binárně najde nejnižší strop T, který baterie udrží celý rok.

    Udržitelnost je monotónní v T (vyšší strop = méně vybíjení a víc prostoru
    na dobíjení), takže binární hledání je korektní. Horní mez = celoroční
    maximum (to jde vždy, i bez baterie). Vrací navrhovanou novou rezervovanou
    kapacitu pro danou variantu baterie.
    """
    if not profil_kw:
        return 0.0
    horni = max(profil_kw)
    dolni = 0.0
    # Když ani celoroční maximum není udržitelné (nemělo by nastat), vrať ho.
    if not strop_je_udrzitelny(profil_kw, horni, vykon_kw, kapacita_kwh, interval_h):
        return horni
    while horni - dolni > _BINARNI_TOLERANCE_KW:
        stred = (horni + dolni) / 2
        if strop_je_udrzitelny(profil_kw, stred, vykon_kw, kapacita_kwh, interval_h):
            horni = stred
        else:
            dolni = stred
    return horni


def energie_pri_stropu(
    profil_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    pocatecni_soc_kwh: float | None = None,
) -> tuple[float, float]:
    """Projede profil na daném stropu a vrátí (nabito_kwh, vybito_kwh).

    Stejná simulace jako `strop_je_udrzitelny` (kap. 4.2), jen navíc sčítá
    energii nabitou a vybitou – potřeba pro grafy a ocenění ztrát baterie.
    Nemění fyziku simulace, jen ji „odposlouchává".
    """
    if vykon_kw <= 0 or kapacita_kwh <= 0:
        return (0.0, 0.0)
    soc = kapacita_kwh if pocatecni_soc_kwh is None else pocatecni_soc_kwh
    nabito = 0.0
    vybito = 0.0
    for odber in profil_kw:
        if odber > strop_kw:
            dodavka = min(odber - strop_kw, _max_udrzitelny_vyboj(soc, vykon_kw, interval_h))
            e = dodavka * interval_h
            soc -= e
            vybito += e
        else:
            rezerva = min(strop_kw - odber, vykon_kw)
            e = min(rezerva * interval_h, kapacita_kwh - soc)
            soc += e
            nabito += e
    return (nabito, vybito)


# ------------------------------------------------- měsíční agregace profilu
def _mesicni_maxima(profil_kw: list[float], mesice: list[int]) -> dict[int, float]:
    """Nejvyšší 15min hodnota odběru v každém kalendářním měsíci (kap. 4.1)."""
    out: dict[int, float] = {}
    for odber, m in zip(profil_kw, mesice):
        if m not in out or odber > out[m]:
            out[m] = odber
    return out


# ----------------------------------------------------- ekonomika roku 2026
@dataclass
class Ekonomika2026:
    """Roční náklady/úspora pro tarif `stara_2026` (kap. 4.1–4.4)."""

    soucasny_naklad_rezervace: float
    soucasny_naklad_prekroceni: float
    soucasny_naklad_celkem: float
    novy_naklad_rezervace: float
    nova_rezervovana_kapacita_kw: float
    rocni_uspora: float


def vychozi_rocni_naklad_2026(
    profil_kw: list[float],
    mesice: list[int],
    rezervovana_kapacita_kw: float,
    cena_rezervace_kc_kw_rok: float,
    cena_prekroceni_kc_kw: float,
) -> tuple[float, float]:
    """Kap. 4.1: (roční cena za rezervaci, roční cena za překročení) bez baterie.

    Překročení se účtuje dle nejvyšší 15min hodnoty v daném měsíci, sazba
    `cena_prekroceni_kc_kw` se aplikuje na každý měsíc zvlášť a sečte přes rok.
    """
    naklad_rezervace = rezervovana_kapacita_kw * cena_rezervace_kc_kw_rok
    naklad_prekroceni = 0.0
    for mesicni_max in _mesicni_maxima(profil_kw, mesice).values():
        prekroceni = mesicni_max - rezervovana_kapacita_kw
        if prekroceni > 0:
            naklad_prekroceni += prekroceni * cena_prekroceni_kc_kw
    return naklad_rezervace, naklad_prekroceni


def ekonomika_2026(
    profil_kw: list[float],
    mesice: list[int],
    rezervovana_kapacita_kw: float,
    cena_rezervace_kc_kw_rok: float,
    cena_prekroceni_kc_kw: float,
    nova_rezervovana_kapacita_kw: float,
) -> Ekonomika2026:
    """Složí výchozí náklad (4.1) a náklad po baterii (4.4) do jedné struktury.

    Po baterii je díky kap. 4.3 překročení nulové → nový náklad = jen rezervace
    na navrhované kapacitě T.
    """
    rez, prekr = vychozi_rocni_naklad_2026(
        profil_kw,
        mesice,
        rezervovana_kapacita_kw,
        cena_rezervace_kc_kw_rok,
        cena_prekroceni_kc_kw,
    )
    soucasny_celkem = rez + prekr
    novy = nova_rezervovana_kapacita_kw * cena_rezervace_kc_kw_rok
    return Ekonomika2026(
        soucasny_naklad_rezervace=rez,
        soucasny_naklad_prekroceni=prekr,
        soucasny_naklad_celkem=soucasny_celkem,
        novy_naklad_rezervace=novy,
        nova_rezervovana_kapacita_kw=nova_rezervovana_kapacita_kw,
        rocni_uspora=soucasny_celkem - novy,
    )


# ----------------------------------------------------- ekonomika roku 2027
# Klíče parametrů struktury `nova_2027` (dvousložkový tarif ERÚ, vše Kč/kW/měsíc).
KLICE_2027 = (
    "t1_kapacita_kc_kw_mesic",
    "t1_spicka_kc_kw_mesic",
    "t2_kapacita_kc_kw_mesic",
    "t2_spicka_kc_kw_mesic",
)


def _mesicni_naklad_2027(rp_kw: float, mesicni_max_kw: float, p: dict) -> tuple[float, str]:
    """Náklad za jeden měsíc v modelu 2027 + který tarif vyšel levněji (kap. 4.6).

    `min(RP×T1_kap + M×T1_špička, RP×T2_kap + M×T2_špička)` + penalizace za
    překročení RP. Sleva „Koeficient AKU" se NEaplikuje: dle definice ERÚ (část
    24 informativního CV) se koeficient počítá z podílu zpětně dodané / odebrané
    elektřiny ZA CELÉ PŘEDÁVACÍ MÍSTO – peak-shavingová baterie uvnitř odběru
    nic zpětně nedodává → podíl ≈ 0 → K = 0 → žádná sleva (audit 16. 7. 2026,
    bughunt PS-3; rozhodnuto). Prahy U1/U2 zůstávají v sazebníku pro případné
    budoucí použití u míst s velkým exportem (po VKP ERÚ 10/2026).
    """
    t1 = rp_kw * p["t1_kapacita_kc_kw_mesic"] + mesicni_max_kw * p["t1_spicka_kc_kw_mesic"]
    t2 = rp_kw * p["t2_kapacita_kc_kw_mesic"] + mesicni_max_kw * p["t2_spicka_kc_kw_mesic"]
    if t1 <= t2:
        zaklad, tarif = t1, "t1"
    else:
        zaklad, tarif = t2, "t2"
    penalizace = max(0.0, mesicni_max_kw - rp_kw) * float(p.get("sazba_prekroceni_kc_kw_mesic", 0.0))
    return zaklad + penalizace, tarif


def _rocni_naklad_2027(rp_kw: float, mesicni_maxima: dict[int, float], p: dict) -> tuple[float, int, int]:
    """Roční náklad 2027 = součet přes 12 měsíců; vrací i počty měsíců T1/T2."""
    naklad = 0.0
    poc_t1 = poc_t2 = 0
    for m in mesicni_maxima.values():
        c, tarif = _mesicni_naklad_2027(rp_kw, m, p)
        naklad += c
        if tarif == "t1":
            poc_t1 += 1
        else:
            poc_t2 += 1
    return naklad, poc_t1, poc_t2


def mesicni_maxima_po_baterii(
    profil_kw: list[float],
    mesice: list[int],
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> dict[int, float]:
    """Kap. 4.6 „srážej co to dá": pro každý měsíc nejnižší udržitelné maximum.

    V roce 2027 se platí přímo za naměřené měsíční maximum (M), takže baterie sráží
    špičku každého měsíce tak hluboko, jak to fyzicky zvládne (max. výkon/kapacita) –
    ne jen na jeden roční strop. Rezervovaná kapacita (RP) se tím NEMĚNÍ: zůstává
    jedna roční hodnota (nelze měnit sjednanou rezervaci na síti po měsících), tady
    jde jen o naměřené maximum M, které tvoří cenovou složku „špička".
    """
    po_mesicich: dict[int, list[float]] = {}
    for odber, m in zip(profil_kw, mesice):
        po_mesicich.setdefault(m, []).append(odber)
    return {
        m: min_udrzitelny_strop(vals, vykon_kw, kapacita_kwh, interval_h)
        for m, vals in po_mesicich.items()
    }


def ekonomika_2027(
    profil_kw: list[float],
    mesice: list[int],
    rezervovana_kapacita_kw: float,
    nova_rezervovana_kapacita_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    parametry: dict | None,
    je_modelovy_odhad: bool = True,
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> dict:
    """Ekonomika roku 2027 (nová dvousložková struktura ERÚ, METODIKA kap. 4.6).

    - Bez peak shavingu: RP = aktuální sjednaná kapacita, M = naměřené měsíční maximum.
    - S peak shavingem: RP = nová (roční, jedna hodnota = min. udržitelný strop pro
      celý rok), M = měsíční maximum PO baterii, sražené co nejhlouběji v každém
      měsíci (kap. 4.6 „srážej co to dá“). RP se přes rok nemění – mění se jen M.

    Sleva „Koeficient AKU" se NEuplatňuje – dle definice ERÚ vychází pro
    peak-shavingovou baterii uvnitř odběru (bez exportu do soustavy) K = 0
    (audit 16. 7. 2026, PS-3). Jediný model 2027 = dřívější „konzervativní".

    Dokud ERÚ nezveřejní závazné sazby (parametry chybí), vrací se status
    "ceka_na_sazby_eru" a appka místo čísel ukáže hlášku.
    """
    if not parametry or any(parametry.get(k) is None for k in KLICE_2027):
        return {"status": "ceka_na_sazby_eru"}

    # Bez peak shavingu (RP = aktuální sjednaná, M = naměřené maximum).
    raw = _mesicni_maxima(profil_kw, mesice)
    soucasny, _, _ = _rocni_naklad_2027(rezervovana_kapacita_kw, raw, parametry)

    # S peak shavingem: po měsících srazit M co nejhlouběji (kap. 4.6).
    mesicni_po = mesicni_maxima_po_baterii(profil_kw, mesice, vykon_kw, kapacita_kwh, interval_h)
    novy, poc_t1, poc_t2 = _rocni_naklad_2027(nova_rezervovana_kapacita_kw, mesicni_po, parametry)

    return {
        "status": "spocitano",
        "soucasny_rocni_naklad": soucasny,
        "novy_rocni_naklad": novy,
        "rocni_uspora": soucasny - novy,
        # RP je jedna roční hodnota (nemění se po měsících) – shodná s novou
        # rezervovanou kapacitou z roku 2026.
        "rezervovana_kapacita_kw": nova_rezervovana_kapacita_kw,
        "pocet_mesicu_t1": poc_t1,
        "pocet_mesicu_t2": poc_t2,
        "je_modelovy_odhad": bool(je_modelovy_odhad),
    }


def graf_maxima(
    profil_kw: list[float],
    mesice: list[int],
    vykon_kw: float,
    kapacita_kwh: float,
    rocni_strop_kw: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> dict:
    """Data pro graf měsíčních maxim odběru: bez baterie vs. s baterií (kap. B promptu).

    `bez_baterie` = naměřené měsíční maximum z profilu (stejné pro oba roky).
    `s_baterii_2026` = maximum po baterii při držení ročního stropu (M = min(raw, T)).
    `s_baterii_2027` = maximum po baterii při srážení co to dá po měsících (kap. 4.6).
    """
    raw = _mesicni_maxima(profil_kw, mesice)
    per_mesic = mesicni_maxima_po_baterii(profil_kw, mesice, vykon_kw, kapacita_kwh, interval_h)
    ms = sorted(raw)
    return {
        "mesice": ms,
        "bez_baterie_kw": [round(raw[m], 2) for m in ms],
        "s_baterii_2026_kw": [round(min(raw[m], rocni_strop_kw), 2) for m in ms],
        "s_baterii_2027_kw": [round(per_mesic[m], 2) for m in ms],
    }


# ---------------------------------------------- výběr varianty (kap. 4.5)
@dataclass
class Baterie:
    """Jeden produkt z katalogu `technologie` (typ = baterie)."""

    id: int
    nazev: str
    vykon_kw: float
    kapacita_kwh: float
    cena_kc: float


@dataclass
class Varianta:
    """Konkrétní kombinace produkt × počet kusů a její ekonomika."""

    baterie_id: int
    nazev: str
    pocet_kusu: int
    celkovy_vykon_kw: float
    celkova_kapacita_kwh: float
    cena_celkem_kc: float
    nova_rezervovana_kapacita_kw: float
    rocni_uspora_2026: float
    navratnost_roky: float | None  # None = úspora ≤ 0 (nekonečná návratnost)
    # Návratnost podle jednotlivých modelů (kap. 4.5/4.6):
    navratnost_2026: float | None  # dle úspory 2026 (= navratnost_roky, výběr varianty)
    navratnost_2027: float | None  # dle úspory 2027 (jediný model, bez slevy AKU – PS-3)
    ekonomika_2026: dict
    ekonomika_2027: dict
    doporuceno: bool

    def _radici_klic(self) -> tuple:
        # Řadíme podle nejkratší návratnosti; varianty bez kladné úspory
        # (navratnost None) padají na konec.
        if self.navratnost_roky is None:
            return (1, float("inf"))
        return (0, self.navratnost_roky)


@dataclass
class VysledekPeakShaving:
    """Kompletní výstup výpočtu pro jednu nabídku (kap. 5)."""

    varianty: list[Varianta] = field(default_factory=list)
    doporucena: Varianta | None = None
    upozorneni: list[str] = field(default_factory=list)


def _navratnost(cena_celkem: float, uspora: float) -> float | None:
    """Kap. 4.5: návratnost v letech. Nekladná úspora → None (nevrátí se)."""
    if uspora <= 0:
        return None
    return cena_celkem / uspora


def spocti_variantu(
    baterie: Baterie,
    pocet_kusu: int,
    profil_kw: list[float],
    mesice: list[int],
    rezervovana_kapacita_kw: float,
    cena_rezervace_kc_kw_rok: float,
    cena_prekroceni_kc_kw: float,
    max_navratnost_roky: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    parametry_2027: dict | None = None,
    je_modelovy_2027: bool = True,
) -> Varianta:
    """Spočítá jednu variantu (produkt × počet kusů): kap. 4.2–4.6."""
    vykon = baterie.vykon_kw * pocet_kusu
    kapacita = baterie.kapacita_kwh * pocet_kusu
    cena = baterie.cena_kc * pocet_kusu

    novy_strop = min_udrzitelny_strop(profil_kw, vykon, kapacita, interval_h)
    ek = ekonomika_2026(
        profil_kw,
        mesice,
        rezervovana_kapacita_kw,
        cena_rezervace_kc_kw_rok,
        cena_prekroceni_kc_kw,
        novy_strop,
    )
    navratnost = _navratnost(cena, ek.rocni_uspora)

    # Rok 2027: RP zůstává roční (novy_strop = min. udržitelný strop pro celý rok),
    # ale měsíční maxima M se sráží co nejhlouběji v každém měsíci (kap. 4.6).
    ek_2027 = ekonomika_2027(
        profil_kw,
        mesice,
        rezervovana_kapacita_kw,
        novy_strop,
        vykon,
        kapacita,
        parametry_2027,
        je_modelovy_2027,
        interval_h,
    )

    # Návratnost dle modelu 2027 (jediný model – bez slevy AKU, PS-3).
    if ek_2027.get("status") == "spocitano":
        navratnost_2027 = _navratnost(cena, ek_2027.get("rocni_uspora", 0.0))
    else:
        navratnost_2027 = None

    doporuceno = navratnost is not None and navratnost <= max_navratnost_roky
    return Varianta(
        baterie_id=baterie.id,
        nazev=baterie.nazev,
        pocet_kusu=pocet_kusu,
        celkovy_vykon_kw=vykon,
        celkova_kapacita_kwh=kapacita,
        cena_celkem_kc=cena,
        nova_rezervovana_kapacita_kw=novy_strop,
        rocni_uspora_2026=ek.rocni_uspora,
        navratnost_roky=navratnost,
        navratnost_2026=navratnost,
        navratnost_2027=navratnost_2027,
        ekonomika_2026=ek.__dict__,
        ekonomika_2027=ek_2027,
        doporuceno=doporuceno,
    )


def vyber_reseni(
    baterie_katalog: list[Baterie],
    profil_kw: list[float],
    mesice: list[int],
    rezervovana_kapacita_kw: float,
    cena_rezervace_kc_kw_rok: float,
    cena_prekroceni_kc_kw: float,
    max_navratnost_roky: float = VYCHOZI_MAX_NAVRATNOST_ROKY,
    max_pocet_kusu: int = VYCHOZI_MAX_POCET_KUSU,
    interval_h: float = VYCHOZI_INTERVAL_H,
    parametry_2027: dict | None = None,
    je_modelovy_2027: bool = True,
) -> VysledekPeakShaving:
    """Kap. 4.5: projede všechny produkty × počty kusů a vybere nejrychlejší návratnost.

    Pro každý produkt zkoušíme počty kusů 1..N a bereme jen ten nejlepší počet
    (další kusy už jen prodražují – přírůstek úspory je omezený tím, že strop
    nemůže klesnout pod fyzikální minimum profilu). Vítěz = nejkratší návratnost.
    Pokud ani nejlepší varianta nedosáhne prahu `max_navratnost_roky`, vrátí se
    stejně, ale s `doporuceno = False` (kap. 4.5 – "nezmizí, jen nedoporučeno").
    """
    vysledek = VysledekPeakShaving()
    if not profil_kw:
        vysledek.upozorneni.append("Chybí profil spotřeby – není z čeho počítat.")
        return vysledek
    if not baterie_katalog:
        vysledek.upozorneni.append("V katalogu není žádná použitelná baterie.")
        return vysledek

    nejlepsi_za_produkt: list[Varianta] = []
    for baterie in baterie_katalog:
        nejlepsi: Varianta | None = None
        for pocet in range(1, max_pocet_kusu + 1):
            v = spocti_variantu(
                baterie,
                pocet,
                profil_kw,
                mesice,
                rezervovana_kapacita_kw,
                cena_rezervace_kc_kw_rok,
                cena_prekroceni_kc_kw,
                max_navratnost_roky,
                interval_h,
                parametry_2027,
                je_modelovy_2027,
            )
            if nejlepsi is None or v._radici_klic() < nejlepsi._radici_klic():
                nejlepsi = v
            else:
                # Přidání kusu už návratnost nezlepšilo → další kusy nemají smysl.
                break
        if nejlepsi is not None:
            nejlepsi_za_produkt.append(nejlepsi)

    nejlepsi_za_produkt.sort(key=lambda v: v._radici_klic())
    vysledek.varianty = nejlepsi_za_produkt
    if nejlepsi_za_produkt:
        vysledek.doporucena = nejlepsi_za_produkt[0]
        if not vysledek.doporucena.doporuceno:
            vysledek.upozorneni.append(
                f"Nejlepší nalezená varianta má návratnost přes {max_navratnost_roky:g} let "
                "(firemní práh) – označeno jako nedoporučeno."
            )
    return vysledek
