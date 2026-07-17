"""Výpočetní jádro Peak shaving (METODIKA-peak-shaving.md, kap. 4).

Čistě deterministický výpočet (žádní AI agenti – viz kap. 1 SPEC-nabidkovac.md).
Modul je záměrně bez závislosti na DB a FastAPI: pracuje jen s prostými
seznamy 15minutových hodnot odběru (kW) a čísly ze sazebníku, aby šel snadno
testovat i volat z různých míst. Napojení na DB/API řeší routes.py.

Klíčové vzorce a rozhodnutí přebíráme z metodiky (+ audit 16. 7. 2026):
- kap. 4.1 – výchozí roční náklad (rezervace + pokuty za překročení),
- kap. 4.2 – simulace baterie po 15min intervalech; od auditu PS-5 se
  ztrátami (η_ch = η_dis = √RT, default RT 0,88) a využitelnou kapacitou
  (SOC okno 10–95 % ≈ ×0,85 jmenovité),
- kap. 4.3 – binární hledání nejnižšího udržitelného stropu T,
- kap. 4.4/4.5 – roční úspora (po odečtu ceny ztrát cyklování), návratnost,
  výběr nejrychlejší varianty,
- kap. 4.6 – struktura roku 2027 (srážej co to dá + min(sazba A, B)).

Všechny peněžní hodnoty jsou bez DPH (kap. 6 bod 2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Granularita vstupních dat: 15 min = 0,25 h. Použije se, když ji nejde
# odvodit z časových značek profilu (kap. 4.2 – "dle granularity vstupních dat").
VYCHOZI_INTERVAL_H = 0.25

# Účinnost baterie (audit PS-5, rozhodnuto 16. 7. 2026): AC-AC round-trip
# default 0,88; hodnota z katalogu (`technologie.ucinnost`) má přednost.
# V simulaci se dělí symetricky η_ch = η_dis = √RT.
VYCHOZI_UCINNOST_RT = 0.88

# Využitelné SOC okno 10–95 % jmenovité kapacity (audit PS-5) – simulace
# pracuje s využitelnou kapacitou = jmenovitá × tento podíl. EOL derating
# (×0,8) se zatím neaplikuje (kryje ho zčásti rezerva RK, PS-6).
PODIL_VYUZITELNE_KAPACITY = 0.85

# Výchozí cena energie pro ocenění ztrát baterie (silová + variabilní
# distribuce), Kč/MWh bez DPH; manažerský parametr `ps_cena_energie_kc_mwh`.
VYCHOZI_CENA_ENERGIE_KC_MWH = 3000.0

# Rezerva sjednané RK nad nalezený strop (audit PS-6, rozhodnuto 16. 7. 2026):
# strop je nalezen s dokonalou znalostí jednoho historického roku – meziroční
# variabilita, servis baterie nebo jiná zima znamenají překročení. Praxe
# 5–15 %; default 5 % (manažerský parametr `ps_rezerva_rk_procenta`).
VYCHOZI_REZERVA_RK_PROCENTA = 5.0

# NPV ekonomika baterie (audit PS-8/PS-9, rozhodnuto 16. 7. 2026): baterie
# kupovaná v H2 2026 prožije životnost v NTS 2027+ → cash flow = rok 1 přínos
# dle modelu 2026, roky 2+ dle modelu 2027 (bez AKU); vítěz se řadí dle NPV.
VYCHOZI_PS_DISKONT = 0.08
VYCHOZI_PS_HORIZONT_ROKY = 10
VYCHOZI_PS_OAM_PROCENTA_CAPEX = 2.0  # O&M % z CAPEX za rok
VYCHOZI_PS_DEGRADACE_USPOR_PROCENTA = 1.5  # pokles přínosu %/rok (degradace baterie)

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
def normalizuj_ucinnost_rt(hodnota) -> float:
    """Round-trip účinnost z katalogu → číslo 0–1 (audit PS-5).

    Toleruje zadání v procentech (88 → 0,88). Hodnoty mimo reálné pásmo
    AC-AC účinnosti (0,5–1,0) nahradí defaultem – radši rozumný default než
    nesmyslná fyzika z překlepu.
    """
    if hodnota is None:
        return VYCHOZI_UCINNOST_RT
    try:
        rt = float(hodnota)
    except (TypeError, ValueError):
        return VYCHOZI_UCINNOST_RT
    if rt > 1.0:
        rt = rt / 100.0
    if not (0.5 <= rt <= 1.0):
        return VYCHOZI_UCINNOST_RT
    return rt


def _eta_jednosmerna(ucinnost_rt: float) -> float:
    """η_ch = η_dis = √RT (symetrické dělení round-trip účinnosti)."""
    return math.sqrt(max(0.0, min(1.0, ucinnost_rt)))


def _max_udrzitelny_vyboj(
    soc_kwh: float, vykon_kw: float, interval_h: float, eta_dis: float = 1.0
) -> float:
    """Max. okamžitý AC výkon (kW), který baterie zvládne dodat po celý interval.

    Omezuje ho štítkový výkon i zbývající energie: z uložených `soc` kWh jde
    na AC stranu jen `soc × η_dis` (ztráty vybíjení, audit PS-5).
    """
    z_energie = (soc_kwh * eta_dis) / interval_h if interval_h > 0 else 0.0
    return min(vykon_kw, z_energie)


def strop_je_udrzitelny(
    profil_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    pocatecni_soc_kwh: float | None = None,
    ucinnost_rt: float = 1.0,
) -> bool:
    """Projede profil interval po intervalu a řekne, jestli baterie udrží strop.

    Implementace kap. 4.2 + ztráty (audit PS-5): nad stropem baterie dodává
    `min(odběr − T, výkon)` na AC straně – ze zásoby ubývá `dodávka/η_dis`;
    pokud jí dojde energie dřív, než odběr klesne pod strop, strop se neudrží
    → False. Pod stropem se dobíjí max. výkonem, omezeně volnou kapacitou
    a rozdílem `T − odběr` (jen z rezervy pod stropem) – do zásoby se uloží
    `příkon × η_ch`. `ucinnost_rt = 1.0` odpovídá dřívějšímu bezztrátovému
    modelu; `kapacita_kwh` je VYUŽITELNÁ kapacita (SOC okno řeší volající).

    Počáteční stav nabití: defaultně plná (využitelná) baterie – předpokládáme,
    že baterii lze před špičkou nabít; nejde-li strop udržet ani s plnou
    baterií, nejde vůbec. Explicitně se dá přepsat.
    """
    if vykon_kw <= 0 or kapacita_kwh <= 0:
        # Bez baterie se udrží jen strop, který profil nikdy nepřekročí.
        return all(odber <= strop_kw for odber in profil_kw)

    eta = _eta_jednosmerna(ucinnost_rt)
    soc = kapacita_kwh if pocatecni_soc_kwh is None else pocatecni_soc_kwh
    for odber in profil_kw:
        if odber > strop_kw:
            potreba = odber - strop_kw
            dodavka = min(potreba, _max_udrzitelny_vyboj(soc, vykon_kw, interval_h, eta))
            if dodavka + 1e-9 < potreba:
                return False  # baterie nestačí → strop se neudrží
            soc -= dodavka * interval_h / eta if eta > 0 else soc
        else:
            # Dobíjení jen z rezervy pod stropem (T − odběr), max. výkonem.
            rezerva = min(strop_kw - odber, vykon_kw)
            soc = min(kapacita_kwh, soc + rezerva * interval_h * eta)
    return True


def min_udrzitelny_strop(
    profil_kw: list[float],
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = 1.0,
) -> float:
    """Kap. 4.3: binárně najde nejnižší strop T, který baterie udrží celý rok.

    Udržitelnost je monotónní v T (vyšší strop = méně vybíjení a víc prostoru
    na dobíjení), takže binární hledání je korektní i se ztrátami. Horní mez =
    celoroční maximum (to jde vždy, i bez baterie). Vrací navrhovaný fyzický
    strop odběru pro danou variantu baterie.
    """
    if not profil_kw:
        return 0.0
    horni = max(profil_kw)
    dolni = 0.0
    # Když ani celoroční maximum není udržitelné (nemělo by nastat), vrať ho.
    if not strop_je_udrzitelny(
        profil_kw, horni, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt=ucinnost_rt
    ):
        return horni
    while horni - dolni > _BINARNI_TOLERANCE_KW:
        stred = (horni + dolni) / 2
        if strop_je_udrzitelny(
            profil_kw, stred, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt=ucinnost_rt
        ):
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
    ucinnost_rt: float = 1.0,
) -> tuple[float, float]:
    """Projede profil na daném stropu a vrátí (nabito_kwh, vybito_kwh) na AC straně.

    Stejná simulace jako `strop_je_udrzitelny` (kap. 4.2 + ztráty PS-5), jen
    navíc sčítá energii odebranou ze sítě na nabíjení (`nabito`) a dodanou do
    odběru (`vybito`) – potřeba pro grafy a ocenění ztrát. Nemění fyziku
    simulace, jen ji „odposlouchává". Ztráty ≈ `nabito × (1 − RT)`.
    """
    if vykon_kw <= 0 or kapacita_kwh <= 0:
        return (0.0, 0.0)
    eta = _eta_jednosmerna(ucinnost_rt)
    soc = kapacita_kwh if pocatecni_soc_kwh is None else pocatecni_soc_kwh
    nabito = 0.0
    vybito = 0.0
    for odber in profil_kw:
        if odber > strop_kw:
            dodavka = min(
                odber - strop_kw, _max_udrzitelny_vyboj(soc, vykon_kw, interval_h, eta)
            )
            e_ac = dodavka * interval_h
            soc -= e_ac / eta if eta > 0 else soc
            vybito += e_ac
        else:
            rezerva = min(strop_kw - odber, vykon_kw)
            # Odběr ze sítě omezí volná kapacita (uloží se jen η_ch podílu).
            e_ac = min(rezerva * interval_h, (kapacita_kwh - soc) / eta if eta > 0 else 0.0)
            soc = min(kapacita_kwh, soc + e_ac * eta)
            nabito += e_ac
    return (nabito, vybito)


# ------------------------------------------------- měsíční agregace profilu
def _mesicni_maxima(profil_kw: list[float], mesice: list[int]) -> dict[int, float]:
    """Nejvyšší 15min hodnota odběru v každém kalendářním měsíci (kap. 4.1)."""
    out: dict[int, float] = {}
    for odber, m in zip(profil_kw, mesice):
        if m not in out or odber > out[m]:
            out[m] = odber
    return out


# ------------------------------------- optimalizace RK bez baterie (PS-7)
@dataclass
class OptimalizaceRk:
    """Nejlevnější kombinace roční + měsíční RK pro daná měsíční maxima."""

    rocni_rk_kw: float
    naklad_kc: float
    dokupy_kw: dict[int, float]  # měsíc → dokoupená měsíční RK (kW)


def optimalizuj_rk(
    mesicni_maxima: dict[int, float],
    cena_rezervace_kc_kw_rok: float,
    cena_mesicni_rk_kc_kw_mesic: float,
) -> OptimalizaceRk:
    """Fair baseline (audit PS-7): optimální RK bez investice do baterie.

    ERÚ umožňuje kombinovat roční a měsíční RK (bod 4.18–4.21 výměru).
    Měsíční dokup stojí 1× měsíční sazbu, pokuta za překročení 1,5× → v optimu
    se překročení vždy pokryje měsíční RK a žádné pokuty se neplatí. Náklad
    `C(R) = R × roční_sazba + Σ_m max(0, M_m − R) × měsíční_sazba` je po
    částech lineární v R → optimum leží v některém měsíčním maximu (nebo 0);
    stačí projít unikátní maxima (grid-search dle auditu).
    """
    if not mesicni_maxima:
        return OptimalizaceRk(rocni_rk_kw=0.0, naklad_kc=0.0, dokupy_kw={})

    def naklad(r: float) -> float:
        dokupy = sum(max(0.0, m - r) for m in mesicni_maxima.values())
        return r * cena_rezervace_kc_kw_rok + dokupy * cena_mesicni_rk_kc_kw_mesic

    kandidati = sorted({0.0, *mesicni_maxima.values()})
    nejlepsi_r = min(kandidati, key=naklad)
    dokupy = {
        m: round(max(0.0, maximum - nejlepsi_r), 2)
        for m, maximum in mesicni_maxima.items()
        if maximum - nejlepsi_r > 1e-9
    }
    return OptimalizaceRk(
        rocni_rk_kw=nejlepsi_r, naklad_kc=naklad(nejlepsi_r), dokupy_kw=dokupy
    )


# ----------------------------------------------------- ekonomika roku 2026
@dataclass
class Ekonomika2026:
    """Roční náklady/úspora pro tarif `stara_2026` (kap. 4.1–4.4 + PS-5/6/7).

    Fair baseline (audit PS-7): úspora se rozpadá na „úsporu bez investice“
    (jen optimalizace RK proti dnešní, často předimenzované RK) a „přínos
    baterie“ (proti optimalizované RK). `naklad_ztrat_baterie` (PS-5) snižuje
    přínos baterie. Rezerva RK (PS-6) je promítnutá v obou optimalizacích
    (cílová maxima × (1 + rezerva)).
    """

    # Dnešní stav (RK zadaná OZ, pokuty za překročení dle profilu).
    soucasny_naklad_rezervace: float
    soucasny_naklad_prekroceni: float
    soucasny_naklad_celkem: float
    # Fair baseline: optimální kombinace roční + měsíční RK bez baterie.
    naklad_optimalni_bez_baterie: float
    optimalni_rk_bez_baterie_kw: float
    dokupy_bez_baterie_pocet_mesicu: int
    uspora_bez_investice: float
    # S baterií: optimální kombinace RK nad maximy sraženými na strop.
    novy_naklad_rezervace: float
    nova_rezervovana_kapacita_kw: float  # roční složka kombinace s baterií
    dokupy_s_baterii_pocet_mesicu: int
    naklad_ztrat_baterie: float
    prinos_baterie: float
    # Celková úspora vs. dnešní stav (= úspora bez investice + přínos baterie).
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
    strop_kw: float,
    cena_mesicni_rk_kc_kw_mesic: float | None = None,
    rezerva_rk_procenta: float = 0.0,
    naklad_ztrat_baterie: float = 0.0,
) -> Ekonomika2026:
    """Ekonomika 2026 s fair baseline (kap. 4.1–4.4 + audit PS-7).

    1. Dnešní stav: RK zadaná OZ + pokuty za překročení (kap. 4.1).
    2. Fair baseline: optimální kombinace roční + měsíční RK nad historickými
       maximy (bez investice) → „úspora hned bez investice“.
    3. S baterií: tentýž optimalizátor nad maximy sraženými na strop baterie
       → „přínos baterie“ = baseline − náklad s baterií − ztráty cyklování.

    Rezerva RK (PS-6) navyšuje cílová maxima obou optimalizací (strop je
    z jednoho historického roku). Chybí-li měsíční sazba RK, odvodí se
    z pokuty (pokuta = 1,5× měsíční RK dle bodu 4.24).
    """
    rez, prekr = vychozi_rocni_naklad_2026(
        profil_kw,
        mesice,
        rezervovana_kapacita_kw,
        cena_rezervace_kc_kw_rok,
        cena_prekroceni_kc_kw,
    )
    soucasny_celkem = rez + prekr

    if cena_mesicni_rk_kc_kw_mesic is None:
        cena_mesicni_rk_kc_kw_mesic = cena_prekroceni_kc_kw / NASOBEK_POKUTY_PREKROCENI_RK

    faktor_rezervy = 1.0 + max(0.0, rezerva_rk_procenta) / 100.0
    raw = _mesicni_maxima(profil_kw, mesice)

    opt_bez = optimalizuj_rk(
        {m: maximum * faktor_rezervy for m, maximum in raw.items()},
        cena_rezervace_kc_kw_rok,
        cena_mesicni_rk_kc_kw_mesic,
    )
    opt_s = optimalizuj_rk(
        {m: min(maximum, strop_kw) * faktor_rezervy for m, maximum in raw.items()},
        cena_rezervace_kc_kw_rok,
        cena_mesicni_rk_kc_kw_mesic,
    )

    uspora_bez_investice = soucasny_celkem - opt_bez.naklad_kc
    prinos_baterie = opt_bez.naklad_kc - opt_s.naklad_kc - naklad_ztrat_baterie
    return Ekonomika2026(
        soucasny_naklad_rezervace=rez,
        soucasny_naklad_prekroceni=prekr,
        soucasny_naklad_celkem=soucasny_celkem,
        naklad_optimalni_bez_baterie=opt_bez.naklad_kc,
        optimalni_rk_bez_baterie_kw=opt_bez.rocni_rk_kw,
        dokupy_bez_baterie_pocet_mesicu=len(opt_bez.dokupy_kw),
        uspora_bez_investice=uspora_bez_investice,
        novy_naklad_rezervace=opt_s.naklad_kc,
        nova_rezervovana_kapacita_kw=opt_s.rocni_rk_kw,
        dokupy_s_baterii_pocet_mesicu=len(opt_s.dokupy_kw),
        naklad_ztrat_baterie=naklad_ztrat_baterie,
        prinos_baterie=prinos_baterie,
        rocni_uspora=uspora_bez_investice + prinos_baterie,
    )


def naklad_ztrat_baterie_kc(
    nabito_kwh: float, ucinnost_rt: float, cena_energie_kc_mwh: float
) -> float:
    """Roční cena energie ztracené cyklováním baterie (audit PS-5).

    Z energie odebrané ze sítě na nabíjení se do odběru vrátí jen podíl RT →
    ztráty = `nabito × (1 − RT)`, oceněné cenou energie (silová + variabilní
    distribuce, Kč/MWh bez DPH).
    """
    return nabito_kwh * (1.0 - max(0.0, min(1.0, ucinnost_rt))) * cena_energie_kc_mwh / 1000.0


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
    ucinnost_rt: float = 1.0,
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
        m: min_udrzitelny_strop(vals, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt)
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
    ucinnost_rt: float = 1.0,
    cena_energie_kc_mwh: float = 0.0,
) -> dict:
    """Ekonomika roku 2027 (nová dvousložková struktura ERÚ, METODIKA kap. 4.6).

    - Bez peak shavingu: RP = aktuální sjednaná kapacita, M = naměřené měsíční maximum.
    - S peak shavingem: RP = nová (roční, jedna hodnota = min. udržitelný strop pro
      celý rok), M = měsíční maximum PO baterii, sražené co nejhlouběji v každém
      měsíci (kap. 4.6 „srážej co to dá“). RP se přes rok nemění – mění se jen M.

    Rezervovaný příkon (audit PS-4): RP je hodnota ZE SMLOUVY O PŘIPOJENÍ
    (dlouhodobá, typicky ≥ RK; v lednu 2027 se převezme ze smlouvy) – volající
    dosazuje za `rezervovana_kapacita_kw` skutečný RP (nebo RK jako fallback)
    a za `nova_rezervovana_kapacita_kw` RP scénáře s PS: bez snížení smlouvy
    STEJNÝ RP (přínos baterie je pak jen na složce „maximální odebraný výkon"
    – poctivý default), se snížením novou RK.

    Sleva „Koeficient AKU" se NEuplatňuje – dle definice ERÚ vychází pro
    peak-shavingovou baterii uvnitř odběru (bez exportu do soustavy) K = 0
    (audit 16. 7. 2026, PS-3). Jediný model 2027 = dřívější „konzervativní".

    Ztráty baterie (audit PS-5): per-měsíční srážení cykluje víc energie než
    roční strop – náklad ztrát se počítá z měsíčních simulací
    (`nabito × (1 − RT) × cena energie`) a snižuje roční úsporu.

    Dokud ERÚ nezveřejní závazné sazby (parametry chybí), vrací se status
    "ceka_na_sazby_eru" a appka místo čísel ukáže hlášku.
    """
    if not parametry or any(parametry.get(k) is None for k in KLICE_2027):
        return {"status": "ceka_na_sazby_eru"}

    # Bez peak shavingu (RP = aktuální sjednaná, M = naměřené maximum).
    raw = _mesicni_maxima(profil_kw, mesice)
    soucasny, _, _ = _rocni_naklad_2027(rezervovana_kapacita_kw, raw, parametry)

    # S peak shavingem: po měsících srazit M co nejhlouběji (kap. 4.6)
    # + sečíst nabíjení pro ocenění ztrát (PS-5).
    po_mesicich: dict[int, list[float]] = {}
    for odber, m in zip(profil_kw, mesice):
        po_mesicich.setdefault(m, []).append(odber)
    mesicni_po: dict[int, float] = {}
    nabito_celkem = 0.0
    for m, vals in po_mesicich.items():
        strop_m = min_udrzitelny_strop(vals, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt)
        mesicni_po[m] = strop_m
        nabito, _ = energie_pri_stropu(
            vals, strop_m, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt=ucinnost_rt
        )
        nabito_celkem += nabito
    novy, poc_t1, poc_t2 = _rocni_naklad_2027(nova_rezervovana_kapacita_kw, mesicni_po, parametry)
    naklad_ztrat = naklad_ztrat_baterie_kc(nabito_celkem, ucinnost_rt, cena_energie_kc_mwh)

    return {
        "status": "spocitano",
        "soucasny_rocni_naklad": soucasny,
        "novy_rocni_naklad": novy + naklad_ztrat,
        "naklad_ztrat_baterie": naklad_ztrat,
        "rocni_uspora": soucasny - novy - naklad_ztrat,
        # RP obou scénářů (audit PS-4): hodnota ze smlouvy o připojení
        # (příp. fallback RK) a RP scénáře s PS (bez/se snížením smlouvy).
        "rp_soucasny_kw": rezervovana_kapacita_kw,
        "rp_novy_kw": nova_rezervovana_kapacita_kw,
        # Zpětná kompatibilita FE: RP použitý ve scénáři s PS.
        "rezervovana_kapacita_kw": nova_rezervovana_kapacita_kw,
        "pocet_mesicu_t1": poc_t1,
        "pocet_mesicu_t2": poc_t2,
        "je_modelovy_odhad": bool(je_modelovy_odhad),
    }


def citlivost_stropu(
    profil_kw: list[float],
    vykon_kw: float,
    kapacita_kwh: float,
    strop_kw: float,
    rezerva_rk_procenta: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = 1.0,
    procenta: float = 5.0,
) -> dict:
    """Citlivost stropu na meziroční variabilitu profilu (audit PS-10).

    Levná bootstrap alternativa walk-forward validace (na tu by byly potřeba
    ≥ 2 roky dat): profil se přeškáluje ±X % (aproximace „jiného roku“ –
    špičky rostou zhruba proporčně, výkon a kapacita baterie ne) a znovu se
    najde udržitelný strop. Vrací i příznak, jestli horní scénář pokryje
    rezerva RK (PS-6) – výkon baterie se s rokem neškáluje, takže strop při
    špičkách +5 % typicky roste VÍC než o 5 %.
    """
    faktor = procenta / 100.0
    strop_minus = min_udrzitelny_strop(
        [p * (1.0 - faktor) for p in profil_kw], vykon_kw, kapacita_kwh, interval_h, ucinnost_rt
    )
    strop_plus = min_udrzitelny_strop(
        [p * (1.0 + faktor) for p in profil_kw], vykon_kw, kapacita_kwh, interval_h, ucinnost_rt
    )
    strop_s_rezervou = strop_kw * (1.0 + max(0.0, rezerva_rk_procenta) / 100.0)
    return {
        "procenta": procenta,
        "strop_minus_kw": round(strop_minus, 2),
        "strop_plus_kw": round(strop_plus, 2),
        "strop_s_rezervou_kw": round(strop_s_rezervou, 2),
        "rezerva_pokryje_horni_scenar": strop_plus <= strop_s_rezervou + _BINARNI_TOLERANCE_KW,
    }


def graf_maxima(
    profil_kw: list[float],
    mesice: list[int],
    vykon_kw: float,
    kapacita_kwh: float,
    rocni_strop_kw: float,
    interval_h: float = VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = 1.0,
) -> dict:
    """Data pro graf měsíčních maxim odběru: bez baterie vs. s baterií (kap. B promptu).

    `bez_baterie` = naměřené měsíční maximum z profilu (stejné pro oba roky).
    `s_baterii_2026` = maximum po baterii při držení ročního stropu (M = min(raw, T)).
    `s_baterii_2027` = maximum po baterii při srážení co to dá po měsících (kap. 4.6).
    """
    raw = _mesicni_maxima(profil_kw, mesice)
    per_mesic = mesicni_maxima_po_baterii(
        profil_kw, mesice, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt
    )
    ms = sorted(raw)
    return {
        "mesice": ms,
        "bez_baterie_kw": [round(raw[m], 2) for m in ms],
        "s_baterii_2026_kw": [round(min(raw[m], rocni_strop_kw), 2) for m in ms],
        "s_baterii_2027_kw": [round(per_mesic[m], 2) for m in ms],
    }


# ---------------------------------------------- výběr varianty (kap. 4.5)
@dataclass
class NastaveniNpv:
    """Parametry NPV ekonomiky baterie (audit PS-9); vše z manažerského nastavení."""

    diskontni_sazba: float = VYCHOZI_PS_DISKONT
    horizont_roky: int = VYCHOZI_PS_HORIZONT_ROKY
    oam_procenta_capex_rok: float = VYCHOZI_PS_OAM_PROCENTA_CAPEX
    degradace_uspor_procenta_rok: float = VYCHOZI_PS_DEGRADACE_USPOR_PROCENTA


def _npv_baterie(
    cena_kc: float,
    prinos_2026_kc: float,
    prinos_2027_kc: float | None,
    n: NastaveniNpv,
) -> tuple[float, float | None, list[float], bool]:
    """NPV/IRR baterie na horizontu životnosti (audit PS-8/PS-9).

    Cash flow: rok 1 = přínos dle modelu 2026 (tarif platí do konce 2026),
    roky 2+ = přínos dle modelu 2027 (NTS). Bez sazeb 2027 se konzervativně
    použije model 2026 pro celý horizont (a příznak to hlásí). Přínos klesá
    degradací úspor, O&M = % z CAPEX ročně. NPV/IRR sdílí vzorce s PPA modulem.
    Vrací (npv, irr, cash_flow, pouzit_model_2027).
    """
    from app.nabidkovac.ppa_fve import _irr, _npv  # sdílené finanční vzorce (PS-9)

    pouzit_2027 = prinos_2027_kc is not None
    oam = cena_kc * max(0.0, n.oam_procenta_capex_rok) / 100.0
    degradace = max(0.0, n.degradace_uspor_procenta_rok) / 100.0
    cf: list[float] = []
    for rok in range(1, max(1, n.horizont_roky) + 1):
        zaklad = prinos_2026_kc if (rok == 1 or not pouzit_2027) else prinos_2027_kc
        cf.append(zaklad * (1.0 - degradace) ** (rok - 1) - oam)
    return _npv(cf, cena_kc, n.diskontni_sazba), _irr(cf, cena_kc), cf, pouzit_2027


def _roky_cash_flow(
    cena_kc: float,
    cf: list[float],
    n: NastaveniNpv,
    pouzit_2027: bool,
) -> list[dict]:
    """Rozpis cash flow po letech pro FE tabulku (stejný vzor jako u PPA).

    Vychází z cash flow z `_npv_baterie` (přínos po degradaci − O&M). Řádek
    nese i kumulace: `uspora_kum_kc` = Σ CF (kolik celkem přinese),
    `cf_kum_kc` = −investice + Σ CF (přechod přes nulu = reálná návratnost
    vč. degradace a O&M) a `cf_kum_disk_kc` = průběh diskontovaného CF
    (poslední řádek = NPV varianty).
    """
    oam = cena_kc * max(0.0, n.oam_procenta_capex_rok) / 100.0
    uspora_kum = 0.0
    cf_kum = -cena_kc
    cf_kum_disk = -cena_kc
    radky: list[dict] = []
    for rok, cf_rok in enumerate(cf, start=1):
        uspora_kum += cf_rok
        cf_kum += cf_rok
        cf_kum_disk += cf_rok / ((1.0 + n.diskontni_sazba) ** rok)
        radky.append(
            {
                "rok": rok,
                # Rok 1 jede na tarifu 2026 (platí do konce roku), dál NTS 2027;
                # bez sazeb 2027 konzervativně model 2026 celý horizont.
                "model": "2027" if (rok > 1 and pouzit_2027) else "2026",
                "prinos_kc": round(cf_rok + oam, 2),
                "oam_kc": round(oam, 2),
                "cf_kc": round(cf_rok, 2),
                "uspora_kum_kc": round(uspora_kum, 2),
                "cf_kum_kc": round(cf_kum, 2),
                "cf_kum_disk_kc": round(cf_kum_disk, 2),
            }
        )
    return radky


@dataclass
class Baterie:
    """Jeden produkt z katalogu `technologie` (typ = baterie).

    `ucinnost_rt` = AC-AC round-trip účinnost 0–1 (sloupec `technologie.ucinnost`,
    fallback 0,88 – audit PS-5).
    """

    id: int
    nazev: str
    vykon_kw: float
    kapacita_kwh: float
    cena_kc: float
    ucinnost_rt: float = VYCHOZI_UCINNOST_RT


@dataclass
class Varianta:
    """Konkrétní kombinace produkt × počet kusů a její ekonomika."""

    baterie_id: int
    nazev: str
    pocet_kusu: int
    celkovy_vykon_kw: float
    celkova_kapacita_kwh: float
    # Využitelná kapacita = jmenovitá × SOC okno (audit PS-5) – s tou simulace počítá.
    vyuzitelna_kapacita_kwh: float
    ucinnost_rt: float
    cena_celkem_kc: float
    # Fyzický strop odběru, který baterie drží (výsledek simulace)…
    strop_kw: float
    # …rezerva nad strop (PS-6) a roční složka optimální kombinace RK
    # s baterií (PS-7; k ní se v dokupových měsících sjednává měsíční RK).
    rezerva_rk_procenta: float
    nova_rezervovana_kapacita_kw: float
    # Rozpad úspory 2026 (audit PS-7): bez investice vs. přínos baterie.
    uspora_bez_investice_2026: float
    prinos_baterie_2026: float
    rocni_uspora_2026: float  # celkem vs. dnešní stav
    navratnost_roky: float | None  # None = přínos ≤ 0 (nekonečná návratnost)
    # Návratnost podle jednotlivých modelů (kap. 4.5/4.6). Od PS-7 se počítá
    # z PŘÍNOSU BATERIE (proti optimalizované RK), ne z celkové úspory.
    navratnost_2026: float | None  # dle přínosu baterie 2026
    navratnost_2027: float | None  # dle úspory 2027 (jediný model, bez slevy AKU – PS-3)
    # NPV na horizontu životnosti (audit PS-8/PS-9) – řídí výběr vítěze.
    npv_kc: float
    irr: float | None
    npv_horizont_roky: int
    npv_pouzit_model_2027: bool
    # Rozpis cash flow po letech pro FE tabulku (viz _roky_cash_flow).
    roky: list[dict]
    ekonomika_2026: dict
    ekonomika_2027: dict
    doporuceno: bool

    def _radici_klic(self) -> tuple:
        # Vítěze řadí NPV na horizontu životnosti (PS-8: tarif 2026 platí jen
        # do konce roku); prostá návratnost je jen sekundární tie-break.
        return (
            -self.npv_kc,
            self.navratnost_roky if self.navratnost_roky is not None else float("inf"),
        )


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
    cena_energie_kc_mwh: float = VYCHOZI_CENA_ENERGIE_KC_MWH,
    rezerva_rk_procenta: float = VYCHOZI_REZERVA_RK_PROCENTA,
    rezervovany_prikon_kw: float | None = None,
    uvazovat_snizeni_rp: bool = False,
    cena_mesicni_rk_kc_kw_mesic: float | None = None,
    npv_nastaveni: NastaveniNpv | None = None,
    max_vykon_stridace_kw: float | None = None,
) -> Varianta:
    """Spočítá jednu variantu (produkt × počet kusů): kap. 4.2–4.6 + PS-4…9.

    `max_vykon_stridace_kw` (ruční OZ override): u modulárních baterií roste
    kapacita s počtem kusů, ale AC výkon bývá omezen sdíleným/pevným
    střídačem (PCS) – bez zadání se počítá jen ze štítkového výkonu produktu.
    """
    vykon = baterie.vykon_kw * pocet_kusu
    if max_vykon_stridace_kw is not None and max_vykon_stridace_kw > 0:
        vykon = min(vykon, max_vykon_stridace_kw)
    kapacita = baterie.kapacita_kwh * pocet_kusu
    # Simulace jede na využitelné kapacitě (SOC okno 10–95 %) a se ztrátami
    # dle round-trip účinnosti produktu (audit PS-5).
    kapacita_uzitecna = kapacita * PODIL_VYUZITELNE_KAPACITY
    ucinnost = baterie.ucinnost_rt
    cena = baterie.cena_kc * pocet_kusu

    novy_strop = min_udrzitelny_strop(profil_kw, vykon, kapacita_uzitecna, interval_h, ucinnost)
    nabito_2026, _ = energie_pri_stropu(
        profil_kw, novy_strop, vykon, kapacita_uzitecna, interval_h, ucinnost_rt=ucinnost
    )
    ztraty_2026 = naklad_ztrat_baterie_kc(nabito_2026, ucinnost, cena_energie_kc_mwh)
    ek = ekonomika_2026(
        profil_kw,
        mesice,
        rezervovana_kapacita_kw,
        cena_rezervace_kc_kw_rok,
        cena_prekroceni_kc_kw,
        novy_strop,
        cena_mesicni_rk_kc_kw_mesic=cena_mesicni_rk_kc_kw_mesic,
        rezerva_rk_procenta=rezerva_rk_procenta,
        naklad_ztrat_baterie=ztraty_2026,
    )
    # Výběr varianty i doporučení řídí PŘÍNOS BATERIE proti optimalizované RK
    # (fair baseline, rozhodnuto 16. 7. 2026) – úspora z pouhého snížení RK
    # se bateriím nepřipisuje.
    navratnost = _navratnost(cena, ek.prinos_baterie)

    # Rok 2027 (audit PS-4): baseline RP = hodnota ze smlouvy o připojení
    # (fallback = současná RK); scénář s PS drží STEJNÝ RP (přínos jen na
    # složce „maximální odebraný výkon"), snížení RP jen na explicitní přání –
    # je to jednosměrná změna smlouvy o připojení. Cíl snížení = fyzický strop
    # + rezerva (v NTS neexistují měsíční dokupy RK).
    strop_s_rezervou = novy_strop * (1.0 + max(0.0, rezerva_rk_procenta) / 100.0)
    rp_soucasny = rezervovany_prikon_kw if rezervovany_prikon_kw else rezervovana_kapacita_kw
    rp_novy = strop_s_rezervou if uvazovat_snizeni_rp else rp_soucasny
    ek_2027 = ekonomika_2027(
        profil_kw,
        mesice,
        rp_soucasny,
        rp_novy,
        vykon,
        kapacita_uzitecna,
        parametry_2027,
        je_modelovy_2027,
        interval_h,
        ucinnost_rt=ucinnost,
        cena_energie_kc_mwh=cena_energie_kc_mwh,
    )

    # Návratnost dle modelu 2027 (jediný model – bez slevy AKU, PS-3).
    if ek_2027.get("status") == "spocitano":
        prinos_2027 = ek_2027.get("rocni_uspora", 0.0)
        navratnost_2027 = _navratnost(cena, prinos_2027)
    else:
        prinos_2027 = None
        navratnost_2027 = None

    # NPV na horizontu životnosti (PS-8/PS-9): rok 1 = model 2026, dál 2027.
    nast_npv = npv_nastaveni or NastaveniNpv()
    npv, irr, cf, npv_pouzit_2027 = _npv_baterie(cena, ek.prinos_baterie, prinos_2027, nast_npv)

    doporuceno = navratnost is not None and navratnost <= max_navratnost_roky
    return Varianta(
        baterie_id=baterie.id,
        nazev=baterie.nazev,
        pocet_kusu=pocet_kusu,
        celkovy_vykon_kw=vykon,
        celkova_kapacita_kwh=kapacita,
        vyuzitelna_kapacita_kwh=kapacita_uzitecna,
        ucinnost_rt=ucinnost,
        cena_celkem_kc=cena,
        strop_kw=novy_strop,
        rezerva_rk_procenta=max(0.0, rezerva_rk_procenta),
        nova_rezervovana_kapacita_kw=ek.nova_rezervovana_kapacita_kw,
        uspora_bez_investice_2026=ek.uspora_bez_investice,
        prinos_baterie_2026=ek.prinos_baterie,
        rocni_uspora_2026=ek.rocni_uspora,
        navratnost_roky=navratnost,
        navratnost_2026=navratnost,
        navratnost_2027=navratnost_2027,
        npv_kc=npv,
        irr=irr,
        npv_horizont_roky=nast_npv.horizont_roky,
        npv_pouzit_model_2027=npv_pouzit_2027,
        roky=_roky_cash_flow(cena, cf, nast_npv, npv_pouzit_2027),
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
    cena_energie_kc_mwh: float = VYCHOZI_CENA_ENERGIE_KC_MWH,
    rezerva_rk_procenta: float = VYCHOZI_REZERVA_RK_PROCENTA,
    rezervovany_prikon_kw: float | None = None,
    uvazovat_snizeni_rp: bool = False,
    cena_mesicni_rk_kc_kw_mesic: float | None = None,
    npv_nastaveni: NastaveniNpv | None = None,
    max_vykon_stridace_kw: float | None = None,
) -> VysledekPeakShaving:
    """Kap. 4.5 + PS-8/PS-9: projede produkty × počty kusů, vítěze řadí dle NPV.

    Pro každý produkt zkoušíme počty kusů 1..N a bereme jen ten nejlepší počet
    (další kusy už jen prodražují – přírůstek úspory je omezený tím, že strop
    nemůže klesnout pod fyzikální minimum profilu). Vítěz = nejvyšší NPV na
    horizontu životnosti (rok 1 model 2026, roky 2+ model 2027); prostá
    návratnost z přínosu baterie je sekundární tie-break a řídí práh
    `max_navratnost_roky` (nedosažení prahu variantu neskryje, jen ji označí
    `doporuceno = False` – kap. 4.5).
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
                cena_energie_kc_mwh,
                rezerva_rk_procenta,
                rezervovany_prikon_kw,
                uvazovat_snizeni_rp,
                cena_mesicni_rk_kc_kw_mesic,
                npv_nastaveni,
                max_vykon_stridace_kw,
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
