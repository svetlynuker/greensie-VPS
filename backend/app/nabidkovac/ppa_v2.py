"""Výpočet PPA v2 – model podle `docs/PPA výpočet.xlsx`, včetně inverzní úlohy.

Zdroj pravdy pro vzorce: `docs/METODIKA-ppa-v2.md`.

Proti v1 (`ppa_fve.py`) přidává to, co reálný obchod má a v1 neznala:

* **prodej technologie do SPV s marží** – financuje se prodejní cena, ne nákladová,
* **financování** – 20 % vlastní kapitál + 80 % anuitní úvěr se splatností = délka kontraktu,
* **DSCR** – bankovní kovenant, tvrdý limit financovatelnosti,
* **IRR vlastního kapitálu** (ne celého projektu) – páka úvěru výnos zvedá,
* **skokovou indexaci** ceny každé 3 roky (v1 měla geometrickou po roce),
* **sdílení přebytku** jako druhý výnosový tok,
* **odkupní tabulku** (za kolik si zákazník technologii odkoupí v roce t),
* **baterii jako pronájem** (paušál Kč/měsíc, ne cena za kWh),
* **inverzní úlohu**: z 15min diagramu a ceny, kterou zákazník platí dnes, dopočítá
  velikost FVE, cenu PPA za kWh a ideální délku kontraktu.

Fyzikální část (simulace výroby kalibrovaná na PVGIS, párování profilů) se recykluje
z v1 – viz `ppa_fve.simuluj_vyrobu` / `sparuj`.

Modul je čistě výpočetní: pracuje jen se seznamy čísel a dataclassy, nezná DB ani
FastAPI (stejná konvence jako `peak_shaving.py`). Ceny bez DPH.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import NamedTuple, Sequence
from datetime import datetime

from .ppa_fve import (
    VYCHOZI_INTERVAL_H,
    VYCHOZI_LAT,
    VYCHOZI_MERNY_VYNOS_KWH_KWP,
    Bilance,
    simuluj_vyrobu,
    sparuj,
)

# --------------------------------------------------------------------------- defaulty
# Hodnoty odvozené z `docs/PPA výpočet.xlsx` (list `cashflow FVE (15)` a
# `pronájem BESS (10)`) – viz METODIKA-ppa-v2.md kap. 4. Přepisovatelné
# z `vypoctova_nastaveni.parametry`.

VYCHOZI_NAKLADOVA_CENA_KC_KWP = 13_500.0
VYCHOZI_MARZE_FVE = 1.35
VYCHOZI_MARZE_BESS = 1.47
VYCHOZI_PROVIZE_FVE = 0.05
VYCHOZI_PROVIZE_BESS = 0.04
VYCHOZI_PODIL_VLASTNIHO_KAPITALU = 0.20
VYCHOZI_UROKOVA_SAZBA = 0.075
VYCHOZI_DSCR_MIN = 1.30
VYCHOZI_IRR_CIL = 0.125
VYCHOZI_SERVIS_KC_ROK = 25_000.0
VYCHOZI_DEGRADACE_ROCNI = 0.005
VYCHOZI_INDEXACE_KROK = 0.03
VYCHOZI_INDEXACE_PERIODA_ROKY = 3
# Za přetok (export / sdílení) se **defaultně neinkasuje nic** – rozhodnuto s Danem
# 29. 7. 2026. Konzervativní: dokud není výkup nebo sdílení opravdu sjednané, nesmí
# nafukovat ekonomiku. Excel počítal 1 800 Kč/MWh, to je teď jen orientační hodnota.
VYCHOZI_CENA_EXPORTU_KC_MWH = 0.0
EXCEL_CENA_EXPORTU_KC_MWH = 1_800.0  # hodnota z `PPA výpočet.xlsx`, pro reprodukci v testech
VYCHOZI_CIL_MIRA_SAMOSPOTREBY = 0.80
VYCHOZI_MIN_SLEVA = 0.10
# Délky kontraktu, které se zákazníkovi nabízejí. Výpočet **nedoporučuje** jednu z nich –
# vrací všechny tři s cenou a slevou a vybírá obchodník (rozhodnuto s Danem 29. 7. 2026).
VYCHOZI_NABIZENE_DELKY_ROKY = (10, 15, 20)
# Část regulovaných složek (použití sítí ap.), kterou PPA na VN ušetří, protože energie
# neprochází distribuční soustavou. Přičítá se k silové složce → vyhnutelná cena.
VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH = 260.0

VYCHOZI_BESS_MARZE_KC_MESIC = 4_500.0
VYCHOZI_BESS_EMS_KC_MESIC = 1_300.0
VYCHOZI_BESS_SERVIS_KC_ROK = 12_000.0

VYCHOZI_ODKUP_POPLATEK_ROCNI = 0.005
VYCHOZI_ODKUP_POPLATEK_PREDCASNE = 0.05

# Baterie – technické defaulty (dispatch, kap. 3.1 metodiky)
VYCHOZI_UCINNOST_ROUND_TRIP = 0.90
VYCHOZI_DOD = 0.90
VYCHOZI_C_RATE = 0.5  # výkon = kapacita × C-rate, když se velikost navrhuje automaticky

# Katalogové baterie: podíl kapacity, se kterým se reálně pracuje (SOC okno).
# Záměrně stejná hodnota jako `peak_shaving.PODIL_VYUZITELNE_KAPACITY` – tentýž
# produkt nesmí u PPA vyjít jinak velký než u peak shavingu.
PODIL_VYUZITELNE_KAPACITY_KATALOG = 0.85
# Kolik kusů jednoho produktu se zkouší poskládat (jako u peak shavingu).
VYCHOZI_MAX_POCET_KUSU = 5

# Horní mez pro bisekci ceny PPA (Kč/MWh) – nad tím už nabídka nemá smysl.
_MAX_CENA_PPA_KC_MWH = 50_000.0
# Horní mez sweepu velikosti FVE jako násobek roční spotřeby (jako v1).
_MAX_POMER_VYROBA_SPOTREBA = 3.0

HLADINY = ("VN", "NN")


class NepodporovanaHladina(ValueError):
    """NN zatím není nakalibrovaná – volba v UI je, výpočet ji odmítne (kap. 2.1)."""


# --------------------------------------------------------------------------- financování
def anuita_mesicni(uver_kc: float, sazba_rocni: float, delka_roky: int) -> float:
    """Měsíční anuitní splátka úvěru (metodika kap. 1.2).

    `splátka = úvěr × r / (1 − (1 + r)^(−n))`, kde `r` je měsíční sazba a `n` počet
    měsíců. Pro nulovou sazbu degeneruje na lineární umořování.
    """
    n = int(round(delka_roky * 12))
    if uver_kc <= 0 or n <= 0:
        return 0.0
    r = sazba_rocni / 12.0
    if r <= 0:
        return uver_kc / n
    return uver_kc * r / (1.0 - (1.0 + r) ** (-n))


def zustatek_uveru(uver_kc: float, sazba_rocni: float, delka_roky: int, po_mesicich: int) -> float:
    """Zůstatek úvěru po `po_mesicich` splátkách (analyticky, bez iterace kalendáře).

    `B_m = P·(1+r)^m − PMT·((1+r)^m − 1)/r`. Používá se v odkupní tabulce
    (metodika kap. 1.7) pro reálný úvěr i pro fiktivní úvěr na 100 % CAPEX.
    """
    n = int(round(delka_roky * 12))
    m = max(0, min(int(po_mesicich), n))
    if uver_kc <= 0 or n <= 0:
        return 0.0
    r = sazba_rocni / 12.0
    pmt = anuita_mesicni(uver_kc, sazba_rocni, delka_roky)
    if r <= 0:
        return max(0.0, uver_kc - pmt * m)
    faktor = (1.0 + r) ** m
    return max(0.0, uver_kc * faktor - pmt * (faktor - 1.0) / r)


def irr(cashflow: list[float]) -> float | None:
    """IRR z cash-flow, kde `cashflow[0]` je rok 0 (investice, záporně).

    Bisekce na intervalu (−0,99; 10>. Vrací None, když NPV nemění znaménko (např.
    projekt je ziskový za každé sazby nebo naopak nikdy).
    """
    if len(cashflow) < 2:
        return None

    def npv(r: float) -> float:
        return sum(c / (1.0 + r) ** i for i, c in enumerate(cashflow))

    # Horní mez schválně vysoko: u velmi ziskových variant (sweep ceny při hledání
    # minimální ceny PPA) může IRR přesáhnout stovky procent a úzký bracket by
    # vrátil None.
    lo, hi = -0.99, 1_000.0
    n_lo, n_hi = npv(lo), npv(hi)
    if n_lo == 0:
        return lo
    if n_hi == 0:
        return hi
    if (n_lo > 0) == (n_hi > 0):
        return None
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if (npv(mid) > 0) == (n_lo > 0):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def npv(cashflow: list[float], diskont: float) -> float:
    """NPV cash-flow, kde `cashflow[0]` je rok 0."""
    return sum(c / (1.0 + diskont) ** i for i, c in enumerate(cashflow))


# --------------------------------------------------------------------------- indexace
def ceny_po_letech(
    cena_rok1: float,
    delka_roky: int,
    krok: float = VYCHOZI_INDEXACE_KROK,
    perioda_roky: int = VYCHOZI_INDEXACE_PERIODA_ROKY,
    kroky_rucne: dict[int, float] | None = None,
) -> list[float]:
    """Cena pro roky 1..N se **skokovou** indexací (metodika kap. 1.4).

    Excel drží cenu 3 roky plochou a pak skočí o `krok` (roky 4, 7, 10, …), tedy
    `cena_t = cena_1 × (1 + krok)^((t−1) // perioda)`.

    `kroky_rucne = {rok: procento}` přebije periodický režim a použije se přesně
    zadaná sada skoků (Excel má každý skok editovatelný zvlášť; použije se
    v testech na reprodukci Excelu, kde jsou vyplněné jen roky 4, 7 a 10).
    """
    n = max(0, int(delka_roky))
    if kroky_rucne is not None:
        out: list[float] = []
        cena = cena_rok1
        for t in range(1, n + 1):
            if t in kroky_rucne:
                cena *= 1.0 + kroky_rucne[t]
            out.append(cena)
        return out
    p = max(1, int(perioda_roky))
    return [cena_rok1 * (1.0 + krok) ** ((t - 1) // p) for t in range(1, n + 1)]


# --------------------------------------------------------------------------- baterie
@dataclass
class Baterie:
    """Bateriové úložiště – technické parametry pro dispatch (metodika kap. 3.1)."""

    kapacita_kwh: float
    vykon_kw: float
    ucinnost_round_trip: float = VYCHOZI_UCINNOST_ROUND_TRIP
    dod: float = VYCHOZI_DOD
    nakladova_cena_kc: float = 0.0
    # Konkrétní produkt z katalogu, když se baterie navrhla z něj. `None` =
    # ruční zadání obchodníkem nebo holá heuristika (kapacita bez produktu).
    produkt_id: int | None = None
    produkt_nazev: str | None = None
    pocet_kusu: int = 1
    # Nákladová cena je odhad z doporučené prodejní ceny (viz `ProduktBaterie`).
    cena_je_doporucena: bool = False

    @property
    def vyuzitelna_kapacita_kwh(self) -> float:
        return max(0.0, self.kapacita_kwh * self.dod)


@dataclass
class ProduktBaterie:
    """Jeden produkt z katalogu `technologie` (typ = baterie).

    Stejná data, ze kterých čerpá peak shaving (`peak_shaving.Baterie`) – PPA má
    vlastní typ jen proto, že si z nich skládá `Baterie` pro svůj dispatch.

    `cena_kc` je **nákladová** cena pro Greensie: marže a provize BESS se na ni
    v ekonomice teprve nabalují (metodika kap. 1.1). Že je to opravdu náklad,
    a ne cena pro zákazníka, plyne ze zdroje dat – ceník
    `docs/importy/pricelist-Simulační matice-2026-07-17.xlsx` vydává dodavatel
    a `baterie_seed` do `Technologie.cena_kc` mapuje jeho sloupec „dealer price
    CZK / prodejní cena reálná", tedy cenu, za kterou nakupuje dealer (Greensie);
    doporučená prodejní cena pro zákazníka je zvlášť v `extra.doporucena_cena_kc`
    a je o dealerský diskont vyšší (v ceníku shodně 1/0,9). Pozor: samo pole
    `Technologie.cena_kc` je v modelu vedené jako „prodejní cena bez DPH" a jinde
    v appce (položky nabídky, peak shaving) se tak i používá – u BESS produktů
    z ceníku v něm ale je dealerská cena.
    """

    id: int
    nazev: str
    vykon_kw: float
    kapacita_kwh: float
    cena_kc: float
    ucinnost_rt: float = VYCHOZI_UCINNOST_ROUND_TRIP
    uzitna_kapacita_kwh: float | None = None
    max_vykon_stridacu_kw: float | None = None
    # U konfigurací, kde ceník dealerskou cenu neuvádí (2 MW a víc), seed vzal
    # doporučenou prodejní cenu. Nákladová cena je tam pak nadhodnocená o
    # dealerský diskont, což se hlásí obchodníkovi v upozorněních.
    cena_je_doporucena: bool = False


def baterie_z_produktu(produkt: ProduktBaterie, pocet_kusu: int = 1) -> Baterie:
    """Katalogový produkt × počet kusů → `Baterie` pro dispatch a ekonomiku.

    Derivace je záměrně shodná s `peak_shaving.spocti_variantu`: jmenovitá
    kapacita × počet kusů jde do `kapacita_kwh`, ale simulace pracuje jen
    s **využitelnou** částí – užitná kapacita z katalogu (fallback jmenovitá)
    × počet kusů × 0,85 (SOC okno). Protože PPA počítá využitelnou kapacitu
    jako `kapacita_kwh × dod`, dopočítá se `dod` tak, aby dala tentýž výsledek.
    Výkon je součet přes kusy, zastropovaný reálným výkonem střídačů z katalogu
    (ten je uvedený na kus).
    """
    pocet = max(1, int(pocet_kusu))
    jmenovita = max(0.0, produkt.kapacita_kwh) * pocet
    zaklad = produkt.uzitna_kapacita_kwh
    if not zaklad or zaklad <= 0:
        zaklad = produkt.kapacita_kwh
    vyuzitelna = max(0.0, zaklad) * pocet * PODIL_VYUZITELNE_KAPACITY_KATALOG
    vykon = max(0.0, produkt.vykon_kw) * pocet
    if produkt.max_vykon_stridacu_kw and produkt.max_vykon_stridacu_kw > 0:
        vykon = min(vykon, produkt.max_vykon_stridacu_kw * pocet)
    ucinnost = produkt.ucinnost_rt if 0 < produkt.ucinnost_rt <= 1 else VYCHOZI_UCINNOST_ROUND_TRIP
    return Baterie(
        kapacita_kwh=jmenovita,
        vykon_kw=vykon,
        ucinnost_round_trip=ucinnost,
        dod=(vyuzitelna / jmenovita) if jmenovita > 0 else 0.0,
        nakladova_cena_kc=max(0.0, produkt.cena_kc) * pocet,
        produkt_id=produkt.id,
        produkt_nazev=produkt.nazev,
        pocet_kusu=pocet,
        cena_je_doporucena=produkt.cena_je_doporucena,
    )


def vyber_baterii_z_katalogu(
    katalog: Sequence[ProduktBaterie],
    cilova_vyuzitelna_kwh: float,
    cilovy_vykon_kw: float = 0.0,
    max_pocet_kusu: int = VYCHOZI_MAX_POCET_KUSU,
) -> Baterie | None:
    """Nejvhodnější produkt × počet kusů z katalogu na navrženou velikost.

    Pravidlo je třístupňové – kapacita sama nestačí, protože katalog obsahuje
    i konfigurace s velkou kapacitou a malým výkonem (1 650 kWh / 150 kW), do
    kterých se denní přebytek FVE nestihne uložit:

    1. kombinace, které pokryjí **kapacitu i výkon** → nejlevnější z nich,
    2. jinak kombinace, které pokryjí kapacitu → nejlevnější (volající ohlásí,
       že výkon je nižší, než heuristika navrhla),
    3. jinak největší dosažitelná kapacita (katalog na návrh nestačí).

    Při shodě ceny vyhrává menší kapacita, ať se nekupuje víc, než je potřeba.
    Vrací `None`, jen když v katalogu není žádný použitelný produkt (nebo je cíl
    nulový); volající pak zůstane u holé heuristiky.
    """
    if cilova_vyuzitelna_kwh <= 0:
        return None
    kandidati: list[Baterie] = []
    for produkt in katalog:
        if produkt.kapacita_kwh <= 0 or produkt.vykon_kw <= 0 or produkt.cena_kc <= 0:
            continue
        for pocet in range(1, max(1, int(max_pocet_kusu)) + 1):
            kandidati.append(baterie_z_produktu(produkt, pocet))
    if not kandidati:
        return None

    # `produkt_id` a `pocet_kusu` v klíči jsou jen deterministický tie-break, ať
    # se při shodných cenách nevybírá podle pořadí v databázi.
    def klic(b: Baterie) -> tuple:
        return (b.nakladova_cena_kc, b.vyuzitelna_kapacita_kwh, b.pocet_kusu, b.produkt_id or 0)

    doost_kapacity = [
        b for b in kandidati if b.vyuzitelna_kapacita_kwh >= cilova_vyuzitelna_kwh - 1e-9
    ]
    if doost_kapacity:
        doost_obojiho = [b for b in doost_kapacity if b.vykon_kw >= cilovy_vykon_kw - 1e-9]
        return min(doost_obojiho or doost_kapacity, key=klic)
    return max(
        kandidati,
        key=lambda b: (b.vyuzitelna_kapacita_kwh, -b.nakladova_cena_kc, -(b.produkt_id or 0)),
    )


class Tok(NamedTuple):
    """Toky energie v jednom intervalu (kWh), `soc_kwh` = stav baterie na konci.

    Pojmenovaná položka místo prostého n-tice, aby šlo přidat další veličinu bez
    přepisování všech volajících.
    """

    vyroba: float
    spotreba: float
    samospotreba: float
    export: float
    orez: float
    dokup: float
    soc_kwh: float


def toky_energie(
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    baterie: Baterie | None,
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
):
    """Generátor toků energie po intervalech – `Tok` za každý interval
    (metodika kap. 3.1, bod 4).

    Greedy dispatch, deterministický: v každém intervalu se nejdřív spotřebuje
    výroba přímo, přebytek se **nabíjí** do baterie (do volné kapacity a výkonu),
    deficit se **vybíjí** z baterie, a co zbyde z přebytku, teče do sítě (do
    rezervovaného výkonu dodávky, zbytek se ořízne).

    Ztráty v baterii se nikde nezpeněží – `samospotřeba` obsahuje jen energii, která
    reálně dorazila k zákazníkovi, takže `SS/V` účinnost baterie zohledňuje.
    Bez baterie (nebo s nulovou) se chová jako přímé párování.

    Sdílí ho roční bilance (`sparuj_s_baterii`) i měsíční data pro graf
    (`graf_mesicni`), aby dispatch existoval na jednom místě.
    """
    strop_e = None
    if rezervovany_vykon_dodavky_kw and rezervovany_vykon_dodavky_kw > 0:
        strop_e = rezervovany_vykon_dodavky_kw * interval_h

    ma_baterii = (
        baterie is not None and baterie.vyuzitelna_kapacita_kwh > 0 and baterie.vykon_kw > 0
    )
    if ma_baterii:
        kapacita = baterie.vyuzitelna_kapacita_kwh
        # Round-trip účinnost se rozdělí symetricky na nabíjení a vybíjení.
        eta = math.sqrt(max(0.0, min(1.0, baterie.ucinnost_round_trip)))
        limit_e = baterie.vykon_kw * interval_h
    soc = 0.0

    for v, s in zip(vyroba_kwh, spotreba_kwh):
        samo = v if v < s else s
        prebytek = v - samo
        deficit = s - samo

        if ma_baterii:
            if prebytek > 0 and soc < kapacita:
                # Kolik lze do baterie dostat: výkon, volná kapacita (po ztrátě) i přebytek.
                nabij = min(prebytek, limit_e, (kapacita - soc) / eta if eta > 0 else 0.0)
                if nabij > 0:
                    soc += nabij * eta
                    prebytek -= nabij
            elif deficit > 0 and soc > 0:
                # Vybíjení krytí deficitu – `vybij` je energie dodaná zákazníkovi.
                vybij = min(deficit, limit_e, soc * eta)
                if vybij > 0:
                    soc -= vybij / eta if eta > 0 else 0.0
                    deficit -= vybij
                    samo += vybij

        exp = orez = 0.0
        if prebytek > 0:
            if strop_e is not None and prebytek > strop_e:
                exp = strop_e
                orez = prebytek - strop_e
            else:
                exp = prebytek
        yield Tok(v, s, samo, exp, orez, deficit, soc)


def sparuj_s_baterii(
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    baterie: Baterie | None,
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> Bilance:
    """Roční energetická bilance (volitelně s baterií) – součet `toky_energie`.

    Bez baterie se chová shodně s `ppa_fve.sparuj`.
    """
    if baterie is None or baterie.vyuzitelna_kapacita_kwh <= 0 or baterie.vykon_kw <= 0:
        return sparuj(vyroba_kwh, spotreba_kwh, rezervovany_vykon_dodavky_kw, interval_h)

    sp = vy = ss = exp = orez = dokup = 0.0
    for t in toky_energie(
        vyroba_kwh, spotreba_kwh, baterie, rezervovany_vykon_dodavky_kw, interval_h
    ):
        vy += t.vyroba
        sp += t.spotreba
        ss += t.samospotreba
        exp += t.export
        orez += t.orez
        dokup += t.dokup
    return Bilance(sp, vy, ss, exp, orez, dokup)


def graf_mesicni(
    casy: list[datetime],
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    baterie: Baterie | None,
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> dict:
    """Měsíční agregáty pro graf výroba vs. spotřeba (metodika kap. 6.1).

    Tvar odpovídá tomu, co čeká komponenta `GrafVyrobaSpotreba.jsx`: pro každý
    měsíc spotřeba rozdělená na samospotřebu a dokup, a výroba rozdělená na
    samospotřebu, přetok do sítě a ořez.
    """
    mesice = list(range(1, 13))
    nula = {m: 0.0 for m in mesice}
    sp, vy, ss, ex, orz, dk = (dict(nula) for _ in range(6))
    for c, t in zip(
        casy,
        toky_energie(
            vyroba_kwh, spotreba_kwh, baterie, rezervovany_vykon_dodavky_kw, interval_h
        ),
    ):
        m = c.month
        vy[m] += t.vyroba
        sp[m] += t.spotreba
        ss[m] += t.samospotreba
        ex[m] += t.export
        orz[m] += t.orez
        dk[m] += t.dokup
    r2 = lambda d: [round(d[m], 2) for m in mesice]  # noqa: E731
    return {
        "mesice": mesice,
        "spotreba_kwh": r2(sp),
        "vyroba_kwh": r2(vy),
        "samospotreba_kwh": r2(ss),
        "export_kwh": r2(ex),
        "orez_kwh": r2(orz),
        "dokup_kwh": r2(dk),
    }


def prubeh_15min(
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    baterie: Baterie | None,
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> dict:
    """15min řady pro nitkový graf průběhu – ve **kW** (jako u peak shavingu).

    Vrací spotřebu, výrobu a jejich rozpad: co se spotřebuje na místě, co teče
    do sítě, co se ořízne a co se dokupuje. U varianty s baterií i stav nabití
    v procentech využitelné kapacity.

    Počítá se ze stejného generátoru `toky_energie` jako roční bilance i měsíční
    graf, takže se čísla v grafu a v tabulkách nemohou rozejít.
    """
    delitel = interval_h if interval_h > 0 else VYCHOZI_INTERVAL_H
    kap = baterie.vyuzitelna_kapacita_kwh if baterie else 0.0

    sp: list[float] = []
    vy: list[float] = []
    ss: list[float] = []
    ex: list[float] = []
    orz: list[float] = []
    dk: list[float] = []
    soc: list[float] = []
    for t in toky_energie(
        vyroba_kwh, spotreba_kwh, baterie, rezervovany_vykon_dodavky_kw, interval_h
    ):
        sp.append(round(t.spotreba / delitel, 2))
        vy.append(round(t.vyroba / delitel, 2))
        ss.append(round(t.samospotreba / delitel, 2))
        ex.append(round(t.export / delitel, 2))
        orz.append(round(t.orez / delitel, 2))
        dk.append(round(t.dokup / delitel, 2))
        if kap > 0:
            soc.append(round(100.0 * t.soc_kwh / kap, 1))
    return {
        "spotreba_kw": sp,
        "vyroba_kw": vy,
        "samospotreba_kw": ss,
        "pretok_kw": ex,
        "orez_kw": orz,
        "dokup_kw": dk,
        "soc_pct": soc or None,
        "souhrn": {
            "max_spotreba_kw": max(sp) if sp else None,
            "max_vyroba_kw": max(vy) if vy else None,
            "max_pretok_kw": max(ex) if ex else None,
        },
    }


def navrhni_baterii(
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    casy: list[datetime],
    c_rate: float = VYCHOZI_C_RATE,
    dod: float = VYCHOZI_DOD,
) -> Baterie:
    """Heuristický návrh velikosti baterie z denního přebytku (metodika kap. 3.4).

    Kapacita = **medián denního přebytku** (co by šlo přes den uložit a večer vydat),
    výkon = kapacita × `c_rate`. Medián místo maxima, ať pár extrémních dní
    nenafoukne baterii, která pak většinu roku stojí. Kapacita se zvětší o `1/dod`,
    aby využitelná část odpovídala spočítanému přebytku.
    """
    po_dnech: dict[tuple, float] = {}
    for c, v, s in zip(casy, vyroba_kwh, spotreba_kwh):
        kd = (c.year, c.timetuple().tm_yday)
        po_dnech[kd] = po_dnech.get(kd, 0.0) + max(0.0, v - s)
    kladne = sorted(x for x in po_dnech.values() if x > 0)
    if not kladne:
        return Baterie(0.0, 0.0, dod=dod)
    median = kladne[len(kladne) // 2]
    kapacita = median / max(0.01, dod)
    return Baterie(
        kapacita_kwh=round(kapacita, 1),
        vykon_kw=round(kapacita * c_rate, 1),
        dod=dod,
    )


# --------------------------------------------------------------------------- parametry
@dataclass
class ParametryEkonomiky:
    """Ekonomické parametry PPA – defaulty z Excelu (metodika kap. 4)."""

    nakladova_cena_kc_kwp: float = VYCHOZI_NAKLADOVA_CENA_KC_KWP
    marze_fve: float = VYCHOZI_MARZE_FVE
    marze_bess: float = VYCHOZI_MARZE_BESS
    provize_fve: float = VYCHOZI_PROVIZE_FVE
    provize_bess: float = VYCHOZI_PROVIZE_BESS
    podil_vlastniho_kapitalu: float = VYCHOZI_PODIL_VLASTNIHO_KAPITALU
    urokova_sazba: float = VYCHOZI_UROKOVA_SAZBA
    dscr_min: float = VYCHOZI_DSCR_MIN
    irr_cil: float = VYCHOZI_IRR_CIL
    servis_kc_rok: float = VYCHOZI_SERVIS_KC_ROK
    degradace_rocni: float = VYCHOZI_DEGRADACE_ROCNI
    indexace_krok: float = VYCHOZI_INDEXACE_KROK
    indexace_perioda_roky: int = VYCHOZI_INDEXACE_PERIODA_ROKY
    # Cena za přetok do sítě (výkup / sdílení). **Default 0 = za přetoky se
    # neinkasuje nic.** Závisí na lokalitě a smlouvě, takže se zadává u konkrétní
    # nabídky přes `VstupPPA2.cena_exportu_kc_mwh`.
    cena_exportu_kc_mwh: float = VYCHOZI_CENA_EXPORTU_KC_MWH
    indexovat_export: bool = True
    # Jaká část exportovaného přebytku se reálně zpeněží. Excel má
    # 78 % samospotřeba / 17 % sdílení, tj. ~0,77 přebytku (5 % výroby nikde) –
    # otevřený bod 5 metodiky. Default 1,0 = zpeněží se celý export.
    podil_zpenezitelneho_prebytku: float = 1.0
    bess_marze_kc_mesic: float = VYCHOZI_BESS_MARZE_KC_MESIC
    bess_ems_kc_mesic: float = VYCHOZI_BESS_EMS_KC_MESIC
    bess_servis_kc_rok: float = VYCHOZI_BESS_SERVIS_KC_ROK
    odkup_poplatek_rocni: float = VYCHOZI_ODKUP_POPLATEK_ROCNI
    odkup_poplatek_predcasne_splaceni: float = VYCHOZI_ODKUP_POPLATEK_PREDCASNE
    diskontni_sazba: float = VYCHOZI_UROKOVA_SAZBA


def _param(parametry: dict | None, klic: str, default: float) -> float:
    """Přečte PPA parametr z manažerského nastavení (JSONB `parametry`) s fallbackem."""
    if parametry:
        hodnota = parametry.get(klic)
        if hodnota is not None:
            try:
                return float(hodnota)
            except (TypeError, ValueError):
                pass
    return default


def parametry_z_nastaveni(parametry: dict | None) -> ParametryEkonomiky:
    """Manažerské nastavení (`vypoctova_nastaveni.parametry`) → ekonomické parametry.

    Je to jedno místo pro výpočet i pro export do Excelu. Kdyby si každý skládal
    parametry sám, sešit by po změně nastavení počítal s jinými čísly než appka
    a nikdo by si toho nevšiml.
    """
    return ParametryEkonomiky(
        nakladova_cena_kc_kwp=_param(
            parametry, "ppa_nakladova_cena_kc_kwp", VYCHOZI_NAKLADOVA_CENA_KC_KWP
        ),
        marze_fve=_param(parametry, "ppa_marze_fve", VYCHOZI_MARZE_FVE),
        marze_bess=_param(parametry, "ppa_marze_bess", VYCHOZI_MARZE_BESS),
        provize_fve=_param(parametry, "ppa_provize_fve", VYCHOZI_PROVIZE_FVE),
        provize_bess=_param(parametry, "ppa_provize_bess", VYCHOZI_PROVIZE_BESS),
        podil_vlastniho_kapitalu=_param(
            parametry, "ppa_podil_vlastniho_kapitalu", VYCHOZI_PODIL_VLASTNIHO_KAPITALU
        ),
        urokova_sazba=_param(parametry, "ppa_urokova_sazba", VYCHOZI_UROKOVA_SAZBA),
        dscr_min=_param(parametry, "ppa_dscr_min", VYCHOZI_DSCR_MIN),
        irr_cil=_param(parametry, "ppa_irr_cil", VYCHOZI_IRR_CIL),
        servis_kc_rok=_param(parametry, "ppa_servis_kc_rok", VYCHOZI_SERVIS_KC_ROK),
        degradace_rocni=_param(parametry, "ppa_degradace_rocni", VYCHOZI_DEGRADACE_ROCNI),
        indexace_krok=_param(parametry, "ppa_indexace_krok", VYCHOZI_INDEXACE_KROK),
        indexace_perioda_roky=int(
            _param(parametry, "ppa_indexace_perioda_roky", VYCHOZI_INDEXACE_PERIODA_ROKY)
        ),
        cena_exportu_kc_mwh=_param(
            parametry, "ppa_cena_exportu_kc_mwh", VYCHOZI_CENA_EXPORTU_KC_MWH
        ),
        podil_zpenezitelneho_prebytku=_param(
            parametry, "ppa_podil_zpenezitelneho_prebytku", 1.0
        ),
        bess_marze_kc_mesic=_param(
            parametry, "ppa_bess_marze_kc_mesic", VYCHOZI_BESS_MARZE_KC_MESIC
        ),
        bess_ems_kc_mesic=_param(parametry, "ppa_bess_ems_kc_mesic", VYCHOZI_BESS_EMS_KC_MESIC),
        bess_servis_kc_rok=_param(
            parametry, "ppa_bess_servis_kc_rok", VYCHOZI_BESS_SERVIS_KC_ROK
        ),
        odkup_poplatek_rocni=_param(
            parametry, "ppa_odkup_poplatek_rocni", VYCHOZI_ODKUP_POPLATEK_ROCNI
        ),
        odkup_poplatek_predcasne_splaceni=_param(
            parametry, "ppa_odkup_poplatek_predcasne", VYCHOZI_ODKUP_POPLATEK_PREDCASNE
        ),
    )


@dataclass
class Projekt:
    """Financovaný projekt – kolik stojí, kolik se půjčí a jaká je splátka."""

    nakladova_cena_kc: float
    capex_kc: float  # prodejní cena do SPV = to, co se financuje
    provize_kc: float
    zisk_greensie_kc: float  # marže po provizi, inkasovaná hned
    vlastni_kapital_kc: float
    uver_kc: float
    splatka_mesicni_kc: float
    splatka_rocni_kc: float
    delka_roky: int


def sestav_projekt(
    nakladova_cena_kc: float,
    marze: float,
    provize: float,
    delka_roky: int,
    p: ParametryEkonomiky,
) -> Projekt:
    """Z nákladové ceny udělá financovaný projekt (metodika kap. 1.1 a 1.2)."""
    capex = nakladova_cena_kc * marze
    provize_kc = capex * provize
    vlastni = capex * p.podil_vlastniho_kapitalu
    uver = capex - vlastni
    pmt = anuita_mesicni(uver, p.urokova_sazba, delka_roky)
    return Projekt(
        nakladova_cena_kc=nakladova_cena_kc,
        capex_kc=capex,
        provize_kc=provize_kc,
        zisk_greensie_kc=capex - nakladova_cena_kc - provize_kc,
        vlastni_kapital_kc=vlastni,
        uver_kc=uver,
        splatka_mesicni_kc=pmt,
        splatka_rocni_kc=pmt * 12.0,
        delka_roky=int(delka_roky),
    )


# --------------------------------------------------------------------------- cashflow
@dataclass
class RokCashflow:
    """Jeden rok kontraktu – to, co má Excel ve sloupci (metodika kap. 1.3–1.6)."""

    rok: int
    vyroba_mwh: float
    samospotreba_mwh: float
    sdileni_mwh: float
    cena_ppa_kc_mwh: float
    cena_exportu_kc_mwh: float
    prodej_zakaznik_kc: float
    prodej_sdileni_kc: float
    najem_baterie_kc: float
    provozni_naklady_kc: float
    zdroje_kc: float
    splatka_kc: float
    dscr: float | None
    zisk_po_splatkach_kc: float


@dataclass
class Cashflow:
    """Výsledek dopředného výpočtu pro dané kWp / cenu / délku."""

    roky: list[RokCashflow]
    vlastni_kapital_kc: float
    capex_kc: float
    splatka_rocni_kc: float
    dscr_min: float | None
    irr: float | None
    npv_kc: float
    cf_vlastniho_kapitalu: list[float]
    zisk_greensie_kc: float
    provize_kc: float


def spocti_cashflow(
    vyroba_rok1_mwh: float,
    podil_samospotreby: float,
    podil_sdileni: float,
    cena_ppa_rok1_kc_mwh: float,
    projekt: Projekt,
    p: ParametryEkonomiky,
    najem_baterie_kc_rok: float = 0.0,
    provozni_naklady_kc_rok: float | None = None,
    indexacni_kroky_rucne: dict[int, float] | None = None,
) -> Cashflow:
    """Dopředný výpočet cash-flow po letech (metodika kap. 1.3–1.6).

    `podil_samospotreby` a `podil_sdileni` jsou podíly **z výroby** (v Excelu ruční
    0,78 a 0,17; v appce se berou ze spárování reálného 15min profilu).
    `najem_baterie_kc_rok` je výnos z pronájmu baterie (Excel řádek „bateriové
    služby"); `provozni_naklady_kc_rok` default = servis FVE.
    """
    n = projekt.delka_roky
    naklady = p.servis_kc_rok if provozni_naklady_kc_rok is None else provozni_naklady_kc_rok
    ceny_ppa = ceny_po_letech(
        cena_ppa_rok1_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne
    )
    if p.indexovat_export:
        ceny_exp = ceny_po_letech(
            p.cena_exportu_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne
        )
    else:
        ceny_exp = [p.cena_exportu_kc_mwh] * n

    roky: list[RokCashflow] = []
    cf = [-projekt.vlastni_kapital_kc]
    for t in range(1, n + 1):
        vyroba = vyroba_rok1_mwh * (1.0 - p.degradace_rocni) ** (t - 1)
        ss = vyroba * podil_samospotreby
        sd = vyroba * podil_sdileni
        prodej_z = ss * ceny_ppa[t - 1]
        prodej_s = sd * ceny_exp[t - 1]
        zdroje = prodej_z + prodej_s + najem_baterie_kc_rok - naklady
        dscr = (zdroje / projekt.splatka_rocni_kc) if projekt.splatka_rocni_kc > 0 else None
        zisk = zdroje - projekt.splatka_rocni_kc
        roky.append(
            RokCashflow(
                rok=t,
                vyroba_mwh=vyroba,
                samospotreba_mwh=ss,
                sdileni_mwh=sd,
                cena_ppa_kc_mwh=ceny_ppa[t - 1],
                cena_exportu_kc_mwh=ceny_exp[t - 1],
                prodej_zakaznik_kc=prodej_z,
                prodej_sdileni_kc=prodej_s,
                najem_baterie_kc=najem_baterie_kc_rok,
                provozni_naklady_kc=naklady,
                zdroje_kc=zdroje,
                splatka_kc=projekt.splatka_rocni_kc,
                dscr=dscr,
                zisk_po_splatkach_kc=zisk,
            )
        )
        cf.append(zisk)

    dscr_hodnoty = [r.dscr for r in roky if r.dscr is not None]
    return Cashflow(
        roky=roky,
        vlastni_kapital_kc=projekt.vlastni_kapital_kc,
        capex_kc=projekt.capex_kc,
        splatka_rocni_kc=projekt.splatka_rocni_kc,
        dscr_min=min(dscr_hodnoty) if dscr_hodnoty else None,
        irr=irr(cf),
        npv_kc=npv(cf, p.diskontni_sazba),
        cf_vlastniho_kapitalu=cf,
        zisk_greensie_kc=projekt.zisk_greensie_kc,
        provize_kc=projekt.provize_kc,
    )


# --------------------------------------------------------------------------- inverzní úloha: cena
@dataclass
class MinimalniCena:
    """Nejnižší cena PPA, se kterou projekt projde bankou i investorem."""

    cena_kc_mwh: float
    cena_z_dscr_kc_mwh: float
    cena_z_irr_kc_mwh: float | None
    limitujici: str  # 'dscr' | 'irr' | 'nedosazitelne'


def cena_ppa_z_dscr(
    vyroba_rok1_mwh: float,
    podil_samospotreby: float,
    podil_sdileni: float,
    projekt: Projekt,
    p: ParametryEkonomiky,
    najem_baterie_kc_rok: float = 0.0,
    provozni_naklady_kc_rok: float | None = None,
    indexacni_kroky_rucne: dict[int, float] | None = None,
) -> float:
    """Nejnižší cena PPA rok 1, při které `DSCR_t ≥ dscr_min` pro každý rok.

    Řeší se **analyticky**, ne bisekcí: `zdroje_t` jsou v ceně lineární, takže pro
    každý rok stačí cenu vyjádřit a vzít maximum přes roky (nejtěsnější rok
    rozhoduje).
    """
    n = projekt.delka_roky
    if n <= 0 or projekt.splatka_rocni_kc <= 0 or podil_samospotreby <= 0 or vyroba_rok1_mwh <= 0:
        return 0.0
    naklady = p.servis_kc_rok if provozni_naklady_kc_rok is None else provozni_naklady_kc_rok
    faktory = ceny_po_letech(1.0, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne)
    if p.indexovat_export:
        ceny_exp = ceny_po_letech(
            p.cena_exportu_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne
        )
    else:
        ceny_exp = [p.cena_exportu_kc_mwh] * n

    potreba = 0.0
    for t in range(1, n + 1):
        vyroba = vyroba_rok1_mwh * (1.0 - p.degradace_rocni) ** (t - 1)
        ss = vyroba * podil_samospotreby
        if ss <= 0:
            continue
        # dscr_min × splátka = ss × cena_1 × faktor_t + sdílení + nájem − náklady
        zbytek = vyroba * podil_sdileni * ceny_exp[t - 1] + najem_baterie_kc_rok - naklady
        cena_1 = (p.dscr_min * projekt.splatka_rocni_kc - zbytek) / (ss * faktory[t - 1])
        potreba = max(potreba, cena_1)
    return max(0.0, potreba)


def cena_ppa_z_irr(
    vyroba_rok1_mwh: float,
    podil_samospotreby: float,
    podil_sdileni: float,
    projekt: Projekt,
    p: ParametryEkonomiky,
    najem_baterie_kc_rok: float = 0.0,
    provozni_naklady_kc_rok: float | None = None,
    indexacni_kroky_rucne: dict[int, float] | None = None,
) -> float | None:
    """Nejnižší cena PPA rok 1, při které `IRR vlastního kapitálu ≥ irr_cil`.

    Řeší se **analyticky**, ne bisekcí přes IRR: podmínka `IRR ≥ irr_cil` je pro
    cash-flow s jednou změnou znaménka ekvivalentní `NPV při diskontu irr_cil ≥ 0`,
    a NPV je v ceně lineární. Vyhne se tím i tomu, že IRR u extrémních cen vyletí
    mimo rozumný bracket.

    Vrací None, když ani stropní cena `_MAX_CENA_PPA_KC_MWH` nestačí (typicky
    projekt bez samospotřeby, kde cena nemá na co působit).
    """
    n = projekt.delka_roky
    if n <= 0:
        return None
    naklady = p.servis_kc_rok if provozni_naklady_kc_rok is None else provozni_naklady_kc_rok
    faktory = ceny_po_letech(1.0, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne)
    if p.indexovat_export:
        ceny_exp = ceny_po_letech(
            p.cena_exportu_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky, indexacni_kroky_rucne
        )
    else:
        ceny_exp = [p.cena_exportu_kc_mwh] * n

    r = p.irr_cil
    # NPV(cena) = koef × cena + zbytek ; hledá se nejmenší cena, kde NPV ≥ 0.
    koef = 0.0
    zbytek = -projekt.vlastni_kapital_kc
    for t in range(1, n + 1):
        diskont = (1.0 + r) ** t
        vyroba = vyroba_rok1_mwh * (1.0 - p.degradace_rocni) ** (t - 1)
        koef += vyroba * podil_samospotreby * faktory[t - 1] / diskont
        pevne = (
            vyroba * podil_sdileni * ceny_exp[t - 1]
            + najem_baterie_kc_rok
            - naklady
            - projekt.splatka_rocni_kc
        )
        zbytek += pevne / diskont

    if koef <= 0:
        # Cena nemá na co působit (nulová samospotřeba) – buď to vyjde bez ní, nebo nikdy.
        return 0.0 if zbytek >= 0 else None
    cena = max(0.0, -zbytek / koef)
    return cena if cena <= _MAX_CENA_PPA_KC_MWH else None


def minimalni_cena_ppa(
    vyroba_rok1_mwh: float,
    podil_samospotreby: float,
    podil_sdileni: float,
    projekt: Projekt,
    p: ParametryEkonomiky,
    najem_baterie_kc_rok: float = 0.0,
    provozni_naklady_kc_rok: float | None = None,
    indexacni_kroky_rucne: dict[int, float] | None = None,
) -> MinimalniCena:
    """Nejnižší cena PPA splňující **obě** podmínky (metodika kap. 3.2).

    `cena = max(cena_z_DSCR, cena_z_IRR)` – banka i investor musí projít současně.
    """
    args = (
        vyroba_rok1_mwh,
        podil_samospotreby,
        podil_sdileni,
        projekt,
        p,
        najem_baterie_kc_rok,
        provozni_naklady_kc_rok,
        indexacni_kroky_rucne,
    )
    c_dscr = cena_ppa_z_dscr(*args)
    c_irr = cena_ppa_z_irr(*args)
    if c_irr is None:
        return MinimalniCena(c_dscr, c_dscr, None, "nedosazitelne")
    if c_irr > c_dscr:
        return MinimalniCena(c_irr, c_dscr, c_irr, "irr")
    return MinimalniCena(c_dscr, c_dscr, c_irr, "dscr")


# --------------------------------------------------------------------------- odkupní tabulka
@dataclass
class RokOdkupu:
    rok: int
    odkupni_cena_kc: float
    zustatek_uveru_kc: float
    poplatek_predcasne_splaceni_kc: float
    zisk_spv_kc: float


def odkupni_tabulka(projekt: Projekt, p: ParametryEkonomiky) -> list[RokOdkupu]:
    """Za kolik si zákazník technologii odkoupí v roce t (metodika kap. 1.7).

    Odkupní cena se odvozuje od **fiktivního úvěru na 100 % CAPEX** (zákazník platí
    zbývající hodnotu celé technologie, ne jen zbytek reálného úvěru) plus
    kumulativní poplatek. Zisk SPV = odkupní cena − reálný zůstatek − poplatek za
    předčasné splacení.
    """
    n = projekt.delka_roky
    if n <= 0:
        return []
    zustatek_100_rok1 = zustatek_uveru(projekt.capex_kc, p.urokova_sazba, n, 12)
    poplatek_1 = zustatek_100_rok1 * p.odkup_poplatek_rocni

    out: list[RokOdkupu] = []
    for t in range(1, n + 1):
        z100 = zustatek_uveru(projekt.capex_kc, p.urokova_sazba, n, t * 12)
        zreal = zustatek_uveru(projekt.uver_kc, p.urokova_sazba, n, t * 12)
        cena = z100 + poplatek_1 * t
        poplatek_pred = zreal * p.odkup_poplatek_predcasne_splaceni
        out.append(
            RokOdkupu(
                rok=t,
                odkupni_cena_kc=cena,
                zustatek_uveru_kc=zreal,
                poplatek_predcasne_splaceni_kc=poplatek_pred,
                zisk_spv_kc=cena - zreal - poplatek_pred,
            )
        )
    return out


# --------------------------------------------------------------------------- velikost FVE
def _mira_samospotreby(
    vyroba_1kwp: list[float],
    spotreba_kwh: list[float],
    kwp: float,
    baterie: Baterie | None,
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> float:
    """Míra samospotřeby `SS/V` pro danou velikost (volitelně s baterií)."""
    if kwp <= 0:
        return 1.0
    vyroba = [kwp * v for v in vyroba_1kwp]
    b = sparuj_s_baterii(vyroba, spotreba_kwh, baterie, rezervovany_vykon_dodavky_kw, interval_h)
    return (b.samospotreba_kwh / b.vyroba_kwh) if b.vyroba_kwh > 0 else 1.0


def navrhni_kwp_na_cil(
    vyroba_1kwp: list[float],
    spotreba_kwh: list[float],
    cil_mira_samospotreby: float = VYCHOZI_CIL_MIRA_SAMOSPOTREBY,
    baterie: Baterie | None = None,
    rezervovany_vykon_dodavky_kw: float | None = None,
    interval_h: float = VYCHOZI_INTERVAL_H,
    max_kwp: float | None = None,
) -> float:
    """Největší FVE, u níž se ještě aspoň `cil_mira_samospotreby` výroby spotřebuje.

    Míra samospotřeby v kWp monotónně klesá (malá FVE se spotřebuje celá, velká
    přetéká) → binární hledání přechodu přes cíl (metodika kap. 3.1). Baterie míru
    zvedá, takže při stejném cíli vyjde **větší** elektrárna.
    """
    prod_per_kwp = sum(vyroba_1kwp)
    e_spotreba = sum(spotreba_kwh)
    if prod_per_kwp <= 0 or e_spotreba <= 0:
        return 0.0

    hi = _MAX_POMER_VYROBA_SPOTREBA * e_spotreba / prod_per_kwp
    if max_kwp and max_kwp > 0:
        hi = min(hi, max_kwp)
    if hi <= 0:
        return 0.0

    def na_cele_kwp(x: float) -> float:
        """Zaokrouhlí na celé kWp, ale **nikdy nad strop**.

        Zaokrouhlení nahoru by strop překročilo (střecha na 35,5 kWp nesmí dát
        36 kWp), proto se nad stropem zaokrouhluje dolů. Když je strop pod 1 kWp,
        vrací 0 – volající to vyhodnotí jako „nedá se postavit".
        """
        v = max(1.0, round(x))
        if max_kwp and max_kwp > 0 and v > max_kwp:
            v = float(math.floor(max_kwp))
        return v

    args = (baterie, rezervovany_vykon_dodavky_kw, interval_h)
    # I při horní mezi drží cíl (ryze denní zátěž nebo nízký strop) → ber horní mez.
    if _mira_samospotreby(vyroba_1kwp, spotreba_kwh, hi, *args) >= cil_mira_samospotreby:
        return na_cele_kwp(hi)

    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2.0
        if _mira_samospotreby(vyroba_1kwp, spotreba_kwh, mid, *args) >= cil_mira_samospotreby:
            lo = mid
        else:
            hi = mid
    return na_cele_kwp(lo)


# --------------------------------------------------------------------------- orchestrace
@dataclass
class VstupPPA2:
    """Vstupy výpočtu – to, co zadává OZ (metodika kap. 2)."""

    casy: list[datetime]
    spotreba_kwh: list[float]
    # Silová složka, kterou zákazník platí dnes (Kč/MWh) – to, co PPA nahrazuje.
    cena_silova_kc_mwh: float
    hladina: str = "VN"
    cil_mira_samospotreby: float = VYCHOZI_CIL_MIRA_SAMOSPOTREBY
    # Vyhnutelné regulované složky (Kč/MWh) – přičítají se k silové, protože
    # samospotřebovaná energie neprochází distribucí. Rozhodnuto: PPA nahrazuje
    # silovou složku + část za použití sítí (metodika kap. 2.1).
    vyhnutelne_regulovane_kc_mwh: float = VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH
    # Cena za přetok do sítě (Kč/MWh) u téhle nabídky. `None` = vzít z nastavení
    # (kde je default 0 = za přetoky se neinkasuje nic). Liší se dle lokality
    # a smlouvy o výkupu/sdílení, proto se zadává per nabídku.
    cena_exportu_kc_mwh: float | None = None
    s_baterii: bool = True
    baterie: Baterie | None = None  # None + s_baterii → navrhne se z katalogu
    # Katalog baterií (`technologie`, typ = baterie) – tentýž zdroj, ze kterého
    # čerpá peak shaving. Když je prázdný, návrh zůstane u holé heuristiky bez
    # ceny a varianta se označí jako neplatná (chybí CAPEX).
    baterie_katalog: tuple[ProduktBaterie, ...] = ()
    lat_deg: float = VYCHOZI_LAT
    sklon_st: float = 35.0
    azimut_st: float = 0.0
    merny_vynos_kwh_kwp: float = VYCHOZI_MERNY_VYNOS_KWH_KWP
    max_kwp: float | None = None
    rezervovany_vykon_dodavky_kw: float | None = None
    # Nabízené délky kontraktu – vrací se všechny, výběr je na obchodníkovi.
    nabizene_delky_roky: tuple[int, ...] = VYCHOZI_NABIZENE_DELKY_ROKY
    min_sleva: float = VYCHOZI_MIN_SLEVA
    interval_h: float | None = None  # None → odvodí se z časů
    parametry: ParametryEkonomiky = field(default_factory=ParametryEkonomiky)


def _kc(hodnota: float) -> str:
    """Částka s mezerou jako oddělovačem tisíců – pro texty upozornění."""
    return f"{hodnota:,.0f}".replace(",", " ")


def _odvod_interval_h(casy: list[datetime]) -> float:
    """Délka intervalu profilu v hodinách (z prvních dvou časů, fallback 0,25 h)."""
    if len(casy) < 2:
        return VYCHOZI_INTERVAL_H
    delta = (casy[1] - casy[0]).total_seconds() / 3600.0
    return delta if delta > 0 else VYCHOZI_INTERVAL_H


def _najem_baterie_kc_mesic(projekt_bess: Projekt, p: ParametryEkonomiky) -> float:
    """Měsíční nájem baterie = marže + splátka úvěru + EMS (metodika kap. 1.8)."""
    if projekt_bess.capex_kc <= 0:
        return 0.0
    return p.bess_marze_kc_mesic + projekt_bess.splatka_mesicni_kc + p.bess_ems_kc_mesic


def spocti_variantu(
    vstup: VstupPPA2,
    vyroba_1kwp: list[float],
    kwp: float,
    baterie: Baterie | None,
    delka_roky: int,
    interval_h: float,
) -> dict:
    """Kompletní ekonomika jedné varianty (dané kWp, baterie a délky kontraktu).

    Vrací slovník připravený k serializaci do `navrhovana_reseni.popis_json`.
    """
    # Cena za přetok zadaná u nabídky přebíjí hodnotu z nastavení (default 0).
    p = vstup.parametry
    if vstup.cena_exportu_kc_mwh is not None:
        p = replace(p, cena_exportu_kc_mwh=max(0.0, vstup.cena_exportu_kc_mwh))
    vyroba = [kwp * v for v in vyroba_1kwp]
    bilance = sparuj_s_baterii(
        vyroba, vstup.spotreba_kwh, baterie, vstup.rezervovany_vykon_dodavky_kw, interval_h
    )
    if bilance.vyroba_kwh <= 0:
        return {}

    podil_ss = bilance.samospotreba_kwh / bilance.vyroba_kwh
    podil_sdil = (
        bilance.export_kwh / bilance.vyroba_kwh
    ) * max(0.0, min(1.0, p.podil_zpenezitelneho_prebytku))

    projekt_fve = sestav_projekt(kwp * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, delka_roky, p)
    projekt_bess = sestav_projekt(
        baterie.nakladova_cena_kc if baterie else 0.0, p.marze_bess, p.provize_bess, delka_roky, p
    )
    najem_mesicni = _najem_baterie_kc_mesic(projekt_bess, p)
    najem_rocni = najem_mesicni * 12.0

    # Sloučený projekt: financuje se FVE i baterie, splátky i náklady se sčítají.
    projekt = Projekt(
        nakladova_cena_kc=projekt_fve.nakladova_cena_kc + projekt_bess.nakladova_cena_kc,
        capex_kc=projekt_fve.capex_kc + projekt_bess.capex_kc,
        provize_kc=projekt_fve.provize_kc + projekt_bess.provize_kc,
        zisk_greensie_kc=projekt_fve.zisk_greensie_kc + projekt_bess.zisk_greensie_kc,
        vlastni_kapital_kc=projekt_fve.vlastni_kapital_kc + projekt_bess.vlastni_kapital_kc,
        uver_kc=projekt_fve.uver_kc + projekt_bess.uver_kc,
        splatka_mesicni_kc=projekt_fve.splatka_mesicni_kc + projekt_bess.splatka_mesicni_kc,
        splatka_rocni_kc=projekt_fve.splatka_rocni_kc + projekt_bess.splatka_rocni_kc,
        delka_roky=delka_roky,
    )
    naklady_rocni = p.servis_kc_rok
    if projekt_bess.capex_kc > 0:
        naklady_rocni += p.bess_servis_kc_rok + p.bess_ems_kc_mesic * 12.0

    vyroba_rok1_mwh = bilance.vyroba_kwh / 1000.0
    minc = minimalni_cena_ppa(
        vyroba_rok1_mwh, podil_ss, podil_sdil, projekt, p, najem_rocni, naklady_rocni
    )
    cf = spocti_cashflow(
        vyroba_rok1_mwh, podil_ss, podil_sdil, minc.cena_kc_mwh, projekt, p, najem_rocni, naklady_rocni
    )

    # Ekonomika zákazníka: co ušetří na samospotřebované energii, minus nájem baterie.
    # Vyhnutelná cena = silová složka + vyhnutelné regulované (energie neprochází
    # distribucí). Zbytek ceny zákazník platí dál z obou stran, takže se do srovnání
    # nedává – jinak by se sleva nadhodnotila.
    cena_vyhnutelna = vstup.cena_silova_kc_mwh + max(0.0, vstup.vyhnutelne_regulovane_kc_mwh)
    ceny_zakaznika = ceny_po_letech(
        cena_vyhnutelna, delka_roky, p.indexace_krok, p.indexace_perioda_roky
    )
    sleva = (1.0 - minc.cena_kc_mwh / cena_vyhnutelna) if cena_vyhnutelna > 0 else None

    roky_klient: list[dict] = []
    uspora_kum = 0.0
    for r in cf.roky:
        cz = ceny_zakaznika[r.rok - 1]
        uspora = r.samospotreba_mwh * (cz - r.cena_ppa_kc_mwh) - najem_rocni
        uspora_kum += uspora
        roky_klient.append(
            {
                "rok": r.rok,
                "cena_vyhnutelna_kc_mwh": round(cz, 2),
                "cena_ppa_kc_mwh": round(r.cena_ppa_kc_mwh, 2),
                "samospotreba_mwh": round(r.samospotreba_mwh, 3),
                "najem_baterie_kc": round(najem_rocni, 2),
                "uspora_kc": round(uspora, 2),
                "uspora_kumulativni_kc": round(uspora_kum, 2),
            }
        )

    return {
        "kwp": round(kwp, 1),
        "delka_kontraktu_roky": delka_roky,
        "s_baterii": bool(baterie and baterie.kapacita_kwh > 0),
        "baterie": (
            {
                "produkt_id": baterie.produkt_id,
                "nazev": baterie.produkt_nazev,
                "pocet_kusu": baterie.pocet_kusu,
                "z_katalogu": baterie.produkt_id is not None,
                "kapacita_kwh": round(baterie.kapacita_kwh, 1),
                # Se kterou částí kapacity simulace opravdu pracuje (SOC okno).
                "vyuzitelna_kapacita_kwh": round(baterie.vyuzitelna_kapacita_kwh, 1),
                "vykon_kw": round(baterie.vykon_kw, 1),
                # `dod` i účinnost se ukládají, aby graf průběhu šel dopočítat
                # z uložené varianty a nerozešel se s ekonomikou.
                "dod": round(baterie.dod, 4),
                "ucinnost_round_trip": round(baterie.ucinnost_round_trip, 4),
                "nakladova_cena_kc": baterie.nakladova_cena_kc,
                "najem_kc_mesic": round(najem_mesicni, 2),
            }
            if baterie and baterie.kapacita_kwh > 0
            else None
        ),
        "cena_ppa_kc_mwh": round(minc.cena_kc_mwh, 2),
        "cena_ppa_kc_kwh": round(minc.cena_kc_mwh / 1000.0, 4),
        "cena_limituje": minc.limitujici,
        "cena_z_dscr_kc_mwh": round(minc.cena_z_dscr_kc_mwh, 2),
        "cena_z_irr_kc_mwh": round(minc.cena_z_irr_kc_mwh, 2) if minc.cena_z_irr_kc_mwh else None,
        "cena_vyhnutelna_kc_mwh": round(cena_vyhnutelna, 2),
        "cena_exportu_kc_mwh": round(p.cena_exportu_kc_mwh, 2),
        "sleva_zakaznikovi": round(sleva, 4) if sleva is not None else None,
        "energie": {
            "spotreba_mwh": round(bilance.spotreba_kwh / 1000.0, 3),
            "vyroba_rok1_mwh": round(vyroba_rok1_mwh, 3),
            "samospotreba_mwh": round(bilance.samospotreba_kwh / 1000.0, 3),
            "export_mwh": round(bilance.export_kwh / 1000.0, 3),
            "orez_mwh": round(bilance.orez_kwh / 1000.0, 3),
            "dokup_mwh": round(bilance.dokup_kwh / 1000.0, 3),
            "mira_samospotreby": round(podil_ss, 4),
            "podil_exportu": round(podil_sdil, 4),
            "pokryti_spotreby_fve": round(
                bilance.samospotreba_kwh / bilance.spotreba_kwh, 4
            )
            if bilance.spotreba_kwh > 0
            else None,
        },
        "financovani": {
            "nakladova_cena_kc": round(projekt.nakladova_cena_kc, 2),
            "capex_kc": round(projekt.capex_kc, 2),
            "provize_kc": round(projekt.provize_kc, 2),
            "zisk_greensie_kc": round(projekt.zisk_greensie_kc, 2),
            "vlastni_kapital_kc": round(projekt.vlastni_kapital_kc, 2),
            "uver_kc": round(projekt.uver_kc, 2),
            "splatka_mesicni_kc": round(projekt.splatka_mesicni_kc, 2),
            "splatka_rocni_kc": round(projekt.splatka_rocni_kc, 2),
            "provozni_naklady_kc_rok": round(naklady_rocni, 2),
        },
        "vysledek_investora": {
            "dscr_min": round(cf.dscr_min, 4) if cf.dscr_min is not None else None,
            "irr": round(cf.irr, 5) if cf.irr is not None else None,
            "npv_kc": round(cf.npv_kc, 2),
        },
        "roky_investor": [
            {
                "rok": r.rok,
                "vyroba_mwh": round(r.vyroba_mwh, 3),
                "samospotreba_mwh": round(r.samospotreba_mwh, 3),
                "sdileni_mwh": round(r.sdileni_mwh, 3),
                "cena_ppa_kc_mwh": round(r.cena_ppa_kc_mwh, 2),
                "prodej_zakaznik_kc": round(r.prodej_zakaznik_kc, 2),
                "prodej_sdileni_kc": round(r.prodej_sdileni_kc, 2),
                "najem_baterie_kc": round(r.najem_baterie_kc, 2),
                "provozni_naklady_kc": round(r.provozni_naklady_kc, 2),
                "zdroje_kc": round(r.zdroje_kc, 2),
                "splatka_kc": round(r.splatka_kc, 2),
                "dscr": round(r.dscr, 4) if r.dscr is not None else None,
                "zisk_po_splatkach_kc": round(r.zisk_po_splatkach_kc, 2),
            }
            for r in cf.roky
        ],
        "roky_klient": roky_klient,
        "uspora_kumulativni_kc": round(uspora_kum, 2),
        "graf": graf_mesicni(
            vstup.casy,
            vyroba,
            vstup.spotreba_kwh,
            baterie,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
        ),
        "odkupni_tabulka": [
            {
                "rok": o.rok,
                "odkupni_cena_kc": round(o.odkupni_cena_kc, 2),
                "zustatek_uveru_kc": round(o.zustatek_uveru_kc, 2),
                "poplatek_predcasne_splaceni_kc": round(o.poplatek_predcasne_splaceni_kc, 2),
                "zisk_spv_kc": round(o.zisk_spv_kc, 2),
            }
            for o in odkupni_tabulka(projekt, p)
        ],
    }


def spocti_ppa2(vstup: VstupPPA2) -> dict:
    """Hlavní vstupní bod – inverzní úloha (metodika kap. 3).

    Postup: velikost FVE z cíle samospotřeby (z **výroby**, jako v Excelu) → pro každou
    nabízenou délku kontraktu nejnižší cena PPA, která projde bankou (DSCR) i investorem
    (IRR).

    Délku kontraktu výpočet **nedoporučuje** – vrací všechny nabízené délky
    (default 10/15/20 let) s cenou a slevou a výběr nechává na obchodníkovi
    (rozhodnuto 29. 7. 2026). Vrací obě varianty technologie (bez baterie i s baterií)
    a upozornění.
    """
    if vstup.hladina not in HLADINY:
        raise NepodporovanaHladina(f"Neznámá napěťová hladina: {vstup.hladina!r}")
    if vstup.hladina == "NN":
        raise NepodporovanaHladina(
            "Hladina NN zatím není nakalibrovaná – v tuhle chvíli počítáme jen VN."
        )
    if not vstup.casy or not vstup.spotreba_kwh:
        return {"chyba": "Chybí 15minutový odběrový diagram."}
    if vstup.cena_silova_kc_mwh <= 0:
        return {"chyba": "Chybí silová složka ceny, kterou zákazník platí dnes."}

    interval_h = vstup.interval_h or _odvod_interval_h(vstup.casy)
    vyroba_1kwp = simuluj_vyrobu(
        vstup.casy, 1.0, vstup.lat_deg, vstup.sklon_st, vstup.azimut_st, vstup.merny_vynos_kwh_kwp
    )

    upozorneni: list[str] = []
    delky = sorted({int(n) for n in vstup.nabizene_delky_roky if int(n) > 0})

    def varianta_pro(baterie: Baterie | None) -> dict | None:
        kwp = navrhni_kwp_na_cil(
            vyroba_1kwp,
            vstup.spotreba_kwh,
            vstup.cil_mira_samospotreby,
            baterie,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
            vstup.max_kwp,
        )
        if kwp <= 0:
            return None
        # Omezil velikost strop (střecha / připojení), nebo cíl samospotřeby? Když
        # strop, je míra samospotřeby nad cílem – elektrárna je menší, než by šlo.
        bez_stropu = navrhni_kwp_na_cil(
            vyroba_1kwp,
            vstup.spotreba_kwh,
            vstup.cil_mira_samospotreby,
            baterie,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
            None,
        )
        omezeno_stropem = bool(vstup.max_kwp and kwp < bez_stropu - 1e-9)
        po_delkach = []
        for n in delky:
            v = spocti_variantu(vstup, vyroba_1kwp, kwp, baterie, n, interval_h)
            if v:
                po_delkach.append(v)
        if not po_delkach:
            return None
        return {
            "kwp": kwp,
            "kwp_bez_stropu": bez_stropu,
            "omezeno_max_kwp": omezeno_stropem,
            "po_delkach": po_delkach,
        }

    bez = varianta_pro(None)

    baterie = None
    if vstup.s_baterii:
        baterie = vstup.baterie
        if baterie is None and bez is not None:
            # Heuristika: velikost se navrhne z denního přebytku FVE, která by vyšla
            # bez baterie – pak se s ní velikost FVE dopočítá znovu (kap. 3.4).
            vyroba_bez = [bez["kwp"] * v for v in vyroba_1kwp]
            navrh = navrhni_baterii(vyroba_bez, vstup.spotreba_kwh, vstup.casy)
            baterie = navrh
            # Heuristika dá jen kapacitu a výkon, ne cenu – bez CAPEX není varianta
            # platná. Konkrétní produkt se proto vybere z katalogu baterií, ze
            # kterého čerpá i peak shaving; katalogová cena je nákladová cena BESS.
            cil = navrh.vyuzitelna_kapacita_kwh
            if cil > 0 and vstup.baterie_katalog:
                z_katalogu = vyber_baterii_z_katalogu(
                    vstup.baterie_katalog, cil, navrh.vykon_kw
                )
                if z_katalogu is not None:
                    baterie = z_katalogu
                    if z_katalogu.cena_je_doporucena:
                        upozorneni.append(
                            f"U baterie {z_katalogu.produkt_nazev} ceník neuvádí dealerskou cenu, "
                            "takže nákladová cena vychází z doporučené prodejní – je tím "
                            "nadhodnocená o dealerský diskont (v ceníku 10 %) a nájem baterie "
                            "vychází vyšší, než jaký by šlo nabídnout. Doplň skutečnou nákupní "
                            "cenu do katalogu, nebo baterii zadej ručně."
                        )
                    if z_katalogu.vyuzitelna_kapacita_kwh < cil - 1e-9:
                        upozorneni.append(
                            f"Největší baterie v katalogu ({z_katalogu.produkt_nazev} × "
                            f"{z_katalogu.pocet_kusu}, {z_katalogu.vyuzitelna_kapacita_kwh:.0f} kWh "
                            f"využitelných) nepokryje navrženou velikost {cil:.0f} kWh – varianta "
                            "počítá s menší baterií, samospotřeba tak může být nižší."
                        )
                    elif z_katalogu.vykon_kw < navrh.vykon_kw - 1e-9:
                        upozorneni.append(
                            f"Vybraná baterie {z_katalogu.produkt_nazev} × {z_katalogu.pocet_kusu} "
                            f"má výkon {z_katalogu.vykon_kw:.0f} kW, návrh chtěl "
                            f"{navrh.vykon_kw:.0f} kW – kapacitu pokryje, ale z přebytku FVE se "
                            "nabíjí pomaleji, takže samospotřeba je nižší. V katalogu není "
                            "výkonnější konfigurace, která by velikost pokryla."
                        )
                else:
                    upozorneni.append(
                        "V katalogu není žádná použitelná baterie (potřebuje výkon, kapacitu "
                        "i cenu), takže se navrhla jen velikost bez ceny – doplň produkty "
                        "do katalogu, nebo zadej baterii ručně."
                    )
            elif cil > 0:
                upozorneni.append(
                    "Katalog baterií je prázdný, navrhla se jen velikost bez ceny – doplň "
                    "produkty do katalogu, nebo zadej baterii ručně."
                )
        # Kontrola platí pro navrženou i pro ručně zadanou baterii: bez CAPEX
        # baterie chybí v modelu jak investice, tak nájem, ale samospotřebu
        # baterie zvedá – varianta pak tvrdí úsporu, která po zaplacení baterie
        # zmizí. Dřív se hlásilo jen u heuristického návrhu, takže baterie zadaná
        # obchodníkem s nulovou cenou prošla bez varování (NAB-26-0026).
        if (
            baterie is not None
            and baterie.nakladova_cena_kc <= 0
            and baterie.kapacita_kwh > 0
        ):
            upozorneni.append(
                "Nákladová cena baterie není zadaná – varianta s baterií počítá "
                "jen s pronájmem bez CAPEX baterie, čísla nejsou platná."
            )
    s_bat = varianta_pro(baterie) if (baterie and baterie.kapacita_kwh > 0) else None

    # Upozornění se vyhodnocují nad variantou bez baterie (nebo s baterií, když FVE
    # samotná nevyšla). Sleva se posuzuje na **nejdelším** kontraktu – ten dává největší
    # slevu, takže když neprojde ani on, nemá nabídka smysl v žádné délce.
    referencni = bez or s_bat
    if referencni:
        nejdelsi = max(referencni["po_delkach"], key=lambda v: v["delka_kontraktu_roky"])
        nejlepsi_sleva = max(
            (v["sleva_zakaznikovi"] for v in referencni["po_delkach"] if v["sleva_zakaznikovi"] is not None),
            default=None,
        )
        if nejlepsi_sleva is None or nejlepsi_sleva < vstup.min_sleva:
            upozorneni.append(
                f"Nabídka nedává obchodní smysl: ani při {nejdelsi['delka_kontraktu_roky']}letém "
                f"kontraktu není sleva zákazníkovi vyšší než {(nejlepsi_sleva or 0) * 100:.1f} %, "
                f"minimum je {vstup.min_sleva * 100:.0f} %. Typicky drahá technologie nebo "
                "zákazník s už levnou elektřinou."
            )
        if any(v.get("cena_limituje") == "nedosazitelne" for v in referencni["po_delkach"]):
            upozorneni.append(
                f"Cílové IRR {vstup.parametry.irr_cil * 100:.1f} % není u některé délky dosažitelné "
                "ani při stropní ceně – tam cena vychází jen z DSCR."
            )
        if nejdelsi["energie"]["orez_mwh"] > 0:
            upozorneni.append(
                f"Rezervovaný výkon dodávky ořezává {nejdelsi['energie']['orez_mwh']:.1f} MWh/rok "
                "přebytku, který se nezpeněží."
            )
        if referencni.get("omezeno_max_kwp"):
            upozorneni.append(
                f"Velikost FVE drží **strop {_kc(vstup.max_kwp or 0)} kWp**, ne cíl samospotřeby – "
                f"bez stropu by vyšlo {_kc(referencni['kwp_bez_stropu'])} kWp. Míra samospotřeby je "
                f"proto nad cílem ({nejdelsi['energie']['mira_samospotreby'] * 100:.1f} % místo "
                f"{vstup.cil_mira_samospotreby * 100:.0f} %) a elektrárna pokryje menší část spotřeby."
            )
    if bez and s_bat:
        # Srovnává se délka s délkou – baterie může vyjít lépe u dlouhého kontraktu
        # a hůř u krátkého, takže jedno souhrnné srovnání by problém zamaskovalo.
        u_bez = {v["delka_kontraktu_roky"]: v["uspora_kumulativni_kc"] for v in bez["po_delkach"]}
        horsi = [
            v["delka_kontraktu_roky"]
            for v in s_bat["po_delkach"]
            if v["delka_kontraktu_roky"] in u_bez
            and v["uspora_kumulativni_kc"] < u_bez[v["delka_kontraktu_roky"]]
        ]
        if horsi:
            delky_text = ", ".join(f"{n} let" for n in sorted(horsi))
            upozorneni.append(
                f"U kontraktu na {delky_text} je s baterií kumulativní úspora zákazníka **nižší** "
                "než bez ní – nájem baterie převáží přínos vyšší samospotřeby. Tenhle výpočet "
                "baterii započítává jen posun přebytku FVE do večera; úspory z peak shavingu "
                "(rezervovaná kapacita) ani z bateriových služeb v něm nejsou – ty řeší samostatný "
                "modul. Baterii nabízej jen společně s nimi."
            )
    if vstup.vyhnutelne_regulovane_kc_mwh <= 0:
        upozorneni.append(
            "Vyhnutelné regulované složky jsou nastavené na 0 – porovnává se jen silová "
            "složka, takže sleva je podhodnocená. Na VN PPA ušetří i část za použití sítí."
        )
    cena_exp = (
        vstup.cena_exportu_kc_mwh
        if vstup.cena_exportu_kc_mwh is not None
        else vstup.parametry.cena_exportu_kc_mwh
    )
    if cena_exp <= 0:
        prebytek = referencni["po_delkach"][0]["energie"]["export_mwh"] if referencni else 0.0
        upozorneni.append(
            f"Za přetoky se **neinkasuje nic** (výchozí nastavení) – {_kc(prebytek)} MWh/rok "
            "přebytku propadá bez výnosu. Cena PPA je proto vyšší, než kdyby byl sjednaný "
            "výkup nebo sdílení. Až cenu za export budeš mít, zadej ji."
        )
    elif vstup.parametry.podil_zpenezitelneho_prebytku >= 1.0:
        upozorneni.append(
            f"Počítá se, že celý přebytek se zpeněží za {_kc(cena_exp)} Kč/MWh. Excel počítal "
            "jen ~77 % přebytku (78 % samospotřeba / 17 % sdílení) – k potvrzení."
        )

    return {
        "vstup": {
            "hladina": vstup.hladina,
            "cena_silova_kc_mwh": vstup.cena_silova_kc_mwh,
            "vyhnutelne_regulovane_kc_mwh": vstup.vyhnutelne_regulovane_kc_mwh,
            "cena_vyhnutelna_kc_mwh": vstup.cena_silova_kc_mwh
            + max(0.0, vstup.vyhnutelne_regulovane_kc_mwh),
            "cena_exportu_kc_mwh": cena_exp,
            "cil_mira_samospotreby": vstup.cil_mira_samospotreby,
            "min_sleva": vstup.min_sleva,
            "sklon_st": vstup.sklon_st,
            "azimut_st": vstup.azimut_st,
            "lat_deg": vstup.lat_deg,
            "merny_vynos_kwh_kwp": vstup.merny_vynos_kwh_kwp,
            "interval_h": interval_h,
            "rezervovany_vykon_dodavky_kw": vstup.rezervovany_vykon_dodavky_kw,
            "max_kwp": vstup.max_kwp,
            "nabizene_delky_roky": delky,
            # DSCR i IRR jsou manažerské nastavení – v odpovědi je vidět, s čím se
            # počítalo, ať je nabídka dohledatelná.
            "dscr_min": vstup.parametry.dscr_min,
            "irr_cil": vstup.parametry.irr_cil,
        },
        "bez_baterie": bez,
        "s_baterii": s_bat,
        "upozorneni": upozorneni,
    }
