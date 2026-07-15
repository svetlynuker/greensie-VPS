"""Výpočetní jádro PPA pro FVE (METODIKA-ppa-fve.md, kap. 4).

Čistě deterministický výpočet (žádní AI agenti – viz kap. 1 SPEC-nabidkovac.md),
bez závislosti na DB a FastAPI – stejně jako `peak_shaving.py`. Pracuje jen se
seznamy 15minutových hodnot (časy + spotřeba v kWh) a čísly z nastavení, aby šel
snadno testovat i volat z různých míst. Napojení na DB/API řeší routes.py.

Pokrývá metodiku:
- kap. 4.1 – simulace výroby FVE (měrný výnos × korekce orientace × měsíční
  rozdělení × clear-sky denní křivka ze solární geometrie),
- kap. 4.2 – degradace panelů po letech kontraktu,
- kap. 4.3 – spárování výroby a spotřeby (samospotřeba / přetok / ořez / dokup),
- kap. 4.4 – ekonomika klienta po letech (eskalace cen PPA i dodavatele),
- kap. 4.5 – ekonomika investora (CAPEX dvěma režimy, výnos, payback, IRR, NPV).

Všechny peněžní hodnoty jsou bez DPH.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

# Granularita vstupních dat (fallback, když ji nejde odvodit z časových značek).
VYCHOZI_INTERVAL_H = 0.25

# Výchozí měrný výnos ČR, jižní orientace, optimální sklon ~35° (kap. 4.1).
# ⚠️ Ilustrativní default k potvrzení/kalibraci – reálné rozpětí ČR ~950–1080.
VYCHOZI_MERNY_VYNOS_KWH_KWP = 1000.0

# Výchozí roční degradace panelů (kap. 4.2).
VYCHOZI_DEGRADACE_ROCNI = 0.005

# Výchozí cena za kWp pro zjednodušený režim CAPEX (kap. 3.4/4.5).
# ⚠️ Orientační odhad k potvrzení.
VYCHOZI_CENA_FVE_KC_KWP = 25000.0

# Zeměpisná šířka středu ČR – fallback, když nabídka nemá GPS (kap. 4.1).
VYCHOZI_LAT = 49.8

# Cílová míra samospotřeby pro automatický návrh velikosti FVE (kap. 4.7).
# Návrh = největší kWp, u něhož se ještě aspoň tento podíl výroby přímo spotřebuje
# (= nejlepší pokrytí spotřeby bez velkého plýtvání přebytkem). Laditelné.
VYCHOZI_CIL_MIRA_SAMOSPOTREBY = 0.80

# Horní mez hledání velikosti: násobek roční spotřeby, který výroba nepřekročí
# (ochrana proti absurdně velké FVE u ryze denní zátěže).
_MAX_POMER_VYROBA_SPOTREBA = 3.0

# Měsíční rozdělení ročního výnosu pro ČR – kWh/kWp/měsíc při ročním výnosu 1000
# (METODIKA kap. 4.1). ⚠️ Ilustrativní, součet = 1000; ke kalibraci.
_MESICNI_VYNOS = {
    1: 26.0, 2: 42.0, 3: 83.0, 4: 120.0, 5: 135.0, 6: 132.0,
    7: 138.0, 8: 120.0, 9: 90.0, 10: 58.0, 11: 30.0, 12: 26.0,
}
_SUMA_MESICNI = sum(_MESICNI_VYNOS.values())  # = 1000

# Korekce orientace k_orient(azimut, sklon), METODIKA kap. 4.1. Řádky = sklon,
# sloupce = |azimut| (0 = jih, 45 = JV/JZ, 90 = V/Z, 180 = sever). Bilineární
# interpolace mezi uzly. ⚠️ Ilustrativní hodnoty, kalibrovat proti PVGIS.
_ORIENT_SKLONY = [0, 15, 35, 60]
_ORIENT_AZIMUTY = [0, 45, 90, 180]
_ORIENT_TAB = {
    0: [0.88, 0.88, 0.88, 0.88],
    15: [0.96, 0.94, 0.88, 0.80],
    35: [1.00, 0.96, 0.84, 0.66],
    60: [0.91, 0.86, 0.72, 0.50],
}


# ----------------------------------------------------- korekce orientace
def _interp1(x: float, xs: list, ys: list) -> float:
    """Lineární interpolace ys(x) na uzlech xs (mimo rozsah = krajní hodnota)."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def korekce_orientace(azimut_st: float, sklon_st: float) -> float:
    """Bilineární interpolace faktoru orientace z tabulky (kap. 4.1).

    Azimut je symetrický kolem jihu (východ i západ = |azimut|). Vrací číslo
    v (0;1], = 1,0 pro jih a sklon ~35°.
    """
    a = abs(azimut_st) % 360
    if a > 180:
        a = 360 - a
    # Nejdřív interpoluj po sklonu (pro každý azimutový sloupec), pak po azimutu.
    pri_sklonu = []
    for j in range(len(_ORIENT_AZIMUTY)):
        ys = [_ORIENT_TAB[s][j] for s in _ORIENT_SKLONY]
        pri_sklonu.append(_interp1(sklon_st, _ORIENT_SKLONY, ys))
    return _interp1(a, _ORIENT_AZIMUTY, pri_sklonu)


# -------------------------------------------------------- solární geometrie
def _slunecni_okno(den_v_roce: int, lat_deg: float) -> tuple[float, float]:
    """Solární čas východu a západu Slunce pro daný den v roce a šířku (kap. 4.1)."""
    dekl = 23.45 * math.sin(math.radians(360.0 * (284 + den_v_roce) / 365.0))
    fi = math.radians(lat_deg)
    de = math.radians(dekl)
    x = -math.tan(fi) * math.tan(de)
    x = max(-1.0, min(1.0, x))  # ošetření polárního dne/noci (v ČR nenastává)
    ws = math.degrees(math.acos(x))
    return 12.0 - ws / 15.0, 12.0 + ws / 15.0


def _tvar_produkce(t_h: float, t_vychod: float, t_zapad: float) -> float:
    """Clear-sky tvar produkce v solárním čase t (kap. 4.1): sinusová zvonovina."""
    if t_zapad <= t_vychod or t_h <= t_vychod or t_h >= t_zapad:
        return 0.0
    return math.sin(math.pi * (t_h - t_vychod) / (t_zapad - t_vychod))


def simuluj_vyrobu(
    casy: list[datetime],
    kwp: float,
    lat_deg: float,
    sklon_st: float,
    azimut_st: float,
    merny_vynos_kwh_kwp: float = VYCHOZI_MERNY_VYNOS_KWH_KWP,
) -> list[float]:
    """Simulace výroby FVE (rok 1, bez degradace) zarovnaná na časy `casy` (kap. 4.1).

    Roční výnos `E_rok = kWp × měrný_výnos × korekce_orientace` se rozdělí po
    měsících (tabulka `_MESICNI_VYNOS`), měsíc na dny (podle počtu dní přítomných
    v profilu) a den na intervaly clear-sky křivkou. Vrací kWh za interval.
    """
    n = len(casy)
    if n == 0 or kwp <= 0:
        return [0.0] * n

    e_rok = kwp * merny_vynos_kwh_kwp * korekce_orientace(azimut_st, sklon_st)

    # Kolik různých dní profil obsahuje v každém měsíci (pro rozpuštění E_měsíc).
    dny_v_mesici: dict[int, set] = {}
    for c in casy:
        dny_v_mesici.setdefault(c.month, set()).add((c.year, c.timetuple().tm_yday))

    # Tvar produkce pro každý interval + součet tvaru v rámci dne (na normalizaci).
    tvar = [0.0] * n
    klic_dne: list[tuple] = [None] * n  # type: ignore[list-item]
    soucet_dne: dict[tuple, float] = {}
    for i, c in enumerate(casy):
        yday = c.timetuple().tm_yday
        t_vychod, t_zapad = _slunecni_okno(yday, lat_deg)
        t_h = c.hour + c.minute / 60.0 + c.second / 3600.0
        g = _tvar_produkce(t_h, t_vychod, t_zapad)
        tvar[i] = g
        kd = (c.year, yday)
        klic_dne[i] = kd
        soucet_dne[kd] = soucet_dne.get(kd, 0.0) + g

    out = [0.0] * n
    for i, c in enumerate(casy):
        frakce = _MESICNI_VYNOS[c.month] / _SUMA_MESICNI
        pocet_dni = len(dny_v_mesici[c.month]) or 1
        e_den = e_rok * frakce / pocet_dni
        s = soucet_dne[klic_dne[i]]
        out[i] = (e_den * tvar[i] / s) if s > 0 else 0.0
    return out


# -------------------------------------------- automatický návrh velikosti FVE
def _mira_samospotreby_pri_kwp(vyroba_1kwp: list[float], spotreba_kwh: list[float], kwp: float) -> float:
    """Míra samospotřeby (samospotřeba/výroba) pro danou velikost (kap. 4.7).

    Výroba je lineární v kWp, samospotřeba `Σ min(kWp·V_i, S_i)` ne – proto se
    počítá napřímo. Klesá s rostoucím kWp (víc přebytku).
    """
    v_celkem = 0.0
    ss = 0.0
    for v1, s in zip(vyroba_1kwp, spotreba_kwh):
        v = kwp * v1
        v_celkem += v
        ss += v if v < s else s
    return (ss / v_celkem) if v_celkem > 0 else 1.0


def navrhni_kwp(
    casy: list[datetime],
    spotreba_kwh: list[float],
    lat_deg: float,
    sklon_st: float,
    azimut_st: float,
    merny_vynos_kwh_kwp: float = VYCHOZI_MERNY_VYNOS_KWH_KWP,
    cil_mira_samospotreby: float = VYCHOZI_CIL_MIRA_SAMOSPOTREBY,
    max_kwp: float | None = None,
) -> float:
    """Navrhne velikost FVE (kWp) tak, aby výroba co nejlépe pokrývala spotřebu (kap. 4.7).

    Cíl: největší FVE, u níž se ještě aspoň `cil_mira_samospotreby` výroby přímo
    spotřebuje. Míra samospotřeby monotónně klesá v kWp, takže se hledá binárně
    přechod přes cíl. `max_kwp` (limit střechy/připojení) horní mez ještě sníží.
    Výsledek se zaokrouhlí na celé kWp (min. 1).
    """
    if not casy:
        return 0.0
    vyroba_1kwp = simuluj_vyrobu(casy, 1.0, lat_deg, sklon_st, azimut_st, merny_vynos_kwh_kwp)
    prod_per_kwp = sum(vyroba_1kwp)
    e_spotreba = sum(spotreba_kwh)
    if prod_per_kwp <= 0 or e_spotreba <= 0:
        return 0.0

    hi = _MAX_POMER_VYROBA_SPOTREBA * e_spotreba / prod_per_kwp
    if max_kwp and max_kwp > 0:
        hi = min(hi, max_kwp)
    if hi <= 0:
        return 0.0

    # Když i při horní mezi zůstává míra nad cílem (ryze denní zátěž / malý strop),
    # ber horní mez – větší už jít nemá smysl / nelze.
    if _mira_samospotreby_pri_kwp(vyroba_1kwp, spotreba_kwh, hi) >= cil_mira_samospotreby:
        return max(1.0, round(hi))

    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _mira_samospotreby_pri_kwp(vyroba_1kwp, spotreba_kwh, mid) >= cil_mira_samospotreby:
            lo = mid
        else:
            hi = mid
    return max(1.0, round(lo))


# -------------------------------------------- spárování výroby a spotřeby
@dataclass
class Bilance:
    """Roční energetická bilance (kWh) po spárování (kap. 4.3)."""

    spotreba_kwh: float
    vyroba_kwh: float
    samospotreba_kwh: float
    export_kwh: float  # skutečně do sítě (≤ rezervovaný výkon dodávky)
    orez_kwh: float  # přebytek nad rezervovaným výkonem dodávky (propadá)
    dokup_kwh: float  # dokup ze sítě


def sparuj(
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> Bilance:
    """Interval po intervalu spočítá samospotřebu / přetok / ořez / dokup (kap. 4.3).

    Pořadí toku: nejdřív samospotřeba (lokální), pak přetok do sítě omezený
    rezervovaným výkonem dodávky (`export = min(přebytek, P_rez × interval_h)`),
    zbytek se ořízne. `rezervovany_vykon_dodavky_kw` None/0 = neomezeno.
    """
    strop_e = None
    if rezervovany_vykon_dodavky_kw and rezervovany_vykon_dodavky_kw > 0:
        strop_e = rezervovany_vykon_dodavky_kw * interval_h

    sp = vy = ss = exp = orez = dokup = 0.0
    for v, s in zip(vyroba_kwh, spotreba_kwh):
        vy += v
        sp += s
        samo = v if v < s else s
        ss += samo
        prebytek = v - samo
        if prebytek > 0:
            if strop_e is not None and prebytek > strop_e:
                exp += strop_e
                orez += prebytek - strop_e
            else:
                exp += prebytek
        dokup += s - samo
    return Bilance(sp, vy, ss, exp, orez, dokup)


def _graf_mesicni(
    mesice: list[int],
    vyroba_kwh: list[float],
    spotreba_kwh: list[float],
    rezervovany_vykon_dodavky_kw: float | None,
    interval_h: float,
) -> dict:
    """Měsíční agregace pro graf výroba vs. spotřeba (kap. 6.1), rok 1."""
    strop_e = None
    if rezervovany_vykon_dodavky_kw and rezervovany_vykon_dodavky_kw > 0:
        strop_e = rezervovany_vykon_dodavky_kw * interval_h

    agg = {m: {"sp": 0.0, "vy": 0.0, "ss": 0.0, "exp": 0.0, "orez": 0.0, "dok": 0.0} for m in range(1, 13)}
    for m, v, s in zip(mesice, vyroba_kwh, spotreba_kwh):
        a = agg[m]
        a["sp"] += s
        a["vy"] += v
        samo = v if v < s else s
        a["ss"] += samo
        prebytek = v - samo
        if prebytek > 0:
            if strop_e is not None and prebytek > strop_e:
                a["exp"] += strop_e
                a["orez"] += prebytek - strop_e
            else:
                a["exp"] += prebytek
        a["dok"] += s - samo

    ms = [m for m in range(1, 13) if agg[m]["sp"] > 0 or agg[m]["vy"] > 0]
    return {
        "mesice": ms,
        "spotreba_kwh": [round(agg[m]["sp"], 1) for m in ms],
        "vyroba_kwh": [round(agg[m]["vy"], 1) for m in ms],
        "samospotreba_kwh": [round(agg[m]["ss"], 1) for m in ms],
        "export_kwh": [round(agg[m]["exp"], 1) for m in ms],
        "orez_kwh": [round(agg[m]["orez"], 1) for m in ms],
        "dokup_kwh": [round(agg[m]["dok"], 1) for m in ms],
    }


# ------------------------------------------------ ekonomika (payback/NPV/IRR)
def _payback_roky(cf_rok: list[float], capex: float) -> float | None:
    """Rok návratnosti investora – nejmenší t s kum. CF ≥ 0, s interpolací (kap. 4.5)."""
    kum = -capex
    for t, cf in enumerate(cf_rok, start=1):
        predchozi = kum
        kum += cf
        if kum >= 0:
            if predchozi < 0 and cf > 0:
                return (t - 1) + (-predchozi) / cf
            return float(t - 1) if predchozi >= 0 else float(t)
    return None


def _npv(cf_rok: list[float], capex: float, r: float) -> float:
    """NPV při diskontní sazbě r (kap. 4.5)."""
    npv = -capex
    for t, cf in enumerate(cf_rok, start=1):
        npv += cf / ((1 + r) ** t)
    return npv


def _irr(cf_rok: list[float], capex: float) -> float | None:
    """IRR bisekcí na [-0,9; 1,0] (kap. 4.5). None, když v intervalu nemění znaménko."""
    lo, hi = -0.9, 1.0
    f_lo = _npv(cf_rok, capex, lo)
    f_hi = _npv(cf_rok, capex, hi)
    if abs(f_lo) < 1e-6:
        return lo
    if f_lo * f_hi > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        f = _npv(cf_rok, capex, mid)
        if abs(f) < 1e-6:
            return mid
        if f_lo * f < 0:
            hi = mid
        else:
            lo, f_lo = mid, f
    return (lo + hi) / 2


# ----------------------------------------------------------- CAPEX (kap. 3.4)
@dataclass
class Komponenta:
    """Položka katalogu použitelná pro komponentový CAPEX (fve_panel / invertor)."""

    id: int
    typ: str
    nazev: str
    vykon_kw: float
    cena_kc: float


def capex_komponenty(
    kwp: float,
    panely: list[Komponenta],
    invertory: list[Komponenta],
    ostatni_kc_kwp: float,
) -> tuple[float, dict]:
    """CAPEX poskládaný z nejlevnějších komponent katalogu (kap. 3.4, režim `komponenty`).

    Vybere nejlevnější dostupný panel a invertor (dle ceny za kW). Počet =
    zaokrouhleno nahoru na pokrytí kWp. BOS (montáž/konstrukce/kabeláž) =
    `kWp × ostatni_kc_kwp`. Vrací (CAPEX, rozpad). Když chybí panel/invertor,
    dá do rozpadu `chybi` a tu složku počítá jako 0.
    """
    rozpad: dict = {"rezim": "komponenty"}
    capex = 0.0

    def _nejlevnejsi(polozky: list[Komponenta]) -> Komponenta | None:
        pouzitelne = [k for k in polozky if k.vykon_kw > 0 and k.cena_kc > 0]
        return min(pouzitelne, key=lambda k: k.cena_kc / k.vykon_kw) if pouzitelne else None

    panel = _nejlevnejsi(panely)
    if panel is not None:
        pocet = math.ceil(kwp / panel.vykon_kw)
        cena = pocet * panel.cena_kc
        capex += cena
        rozpad["panely"] = {"nazev": panel.nazev, "pocet": pocet, "cena_kc": round(cena, 2)}
    else:
        rozpad["panely"] = {"chybi": True}

    invertor = _nejlevnejsi(invertory)
    if invertor is not None:
        pocet = math.ceil(kwp / invertor.vykon_kw)
        cena = pocet * invertor.cena_kc
        capex += cena
        rozpad["invertory"] = {"nazev": invertor.nazev, "pocet": pocet, "cena_kc": round(cena, 2)}
    else:
        rozpad["invertory"] = {"chybi": True}

    ostatni = kwp * (ostatni_kc_kwp or 0.0)
    capex += ostatni
    rozpad["ostatni"] = {"cena_kc": round(ostatni, 2), "kc_kwp": ostatni_kc_kwp or 0.0}
    rozpad["celkem_kc"] = round(capex, 2)
    return capex, rozpad


# --------------------------------------------------------------- hlavní vstup
@dataclass
class VstupPPA:
    """Vstupy PPA výpočtu (METODIKA kap. 2). Route je poskládá z nabídky + nastavení."""

    kwp: float
    lat: float
    sklon_st: float
    azimut_st: float
    cena_ppa_kc_mwh: float
    index_ppa_rocni: float
    cena_dodavatel_kc_mwh: float
    index_dodavatel_rocni: float
    delka_kontraktu_roky: int
    degradace_rocni: float
    capex_kc: float
    prebytek_uctovat: bool
    prebytek_cena_kc_mwh: float
    index_prebytek_rocni: float
    rezervovany_vykon_dodavky_kw: float | None
    oam_kc_kwp_rok: float
    diskontni_sazba: float
    capex_rozpad: dict | None = None
    merny_vynos_kwh_kwp: float = VYCHOZI_MERNY_VYNOS_KWH_KWP
    interval_h: float = VYCHOZI_INTERVAL_H


def spocti_ppa(vstup: VstupPPA, casy: list[datetime], spotreba_kwh: list[float]) -> dict:
    """Kompletní PPA výpočet pro jednu FVE (METODIKA kap. 4). Vrací popis_json.

    Simuluje výrobu (kap. 4.1), rok po roce aplikuje degradaci (4.2), spáruje se
    spotřebou (4.3), spočítá ekonomiku klienta (4.4) i investora (4.5) a data pro
    graf (6.1). Výběr velikosti FVE tu není – počítá se pro zadané `kwp`.
    """
    n = len(casy)
    v = vstup
    vyroba1 = simuluj_vyrobu(casy, v.kwp, v.lat, v.sklon_st, v.azimut_st, v.merny_vynos_kwh_kwp)
    k_or = korekce_orientace(v.azimut_st, v.sklon_st)
    mesice = [c.month for c in casy]
    e_spotreba = sum(spotreba_kwh)

    bil1 = sparuj(vyroba1, spotreba_kwh, v.rezervovany_vykon_dodavky_kw, v.interval_h)

    roky = []
    uspora_kum = 0.0
    cf_rok: list[float] = []
    for t in range(1, max(1, v.delka_kontraktu_roky) + 1):
        f = (1.0 - v.degradace_rocni) ** (t - 1)
        vyroba_t = [x * f for x in vyroba1] if t > 1 else vyroba1
        bil = sparuj(vyroba_t, spotreba_kwh, v.rezervovany_vykon_dodavky_kw, v.interval_h)

        cena_ppa_t = v.cena_ppa_kc_mwh * (1 + v.index_ppa_rocni) ** (t - 1)
        cena_dod_t = v.cena_dodavatel_kc_mwh * (1 + v.index_dodavatel_rocni) ** (t - 1)
        cena_pre_t = v.prebytek_cena_kc_mwh * (1 + v.index_prebytek_rocni) ** (t - 1)

        # Klient: úspora = samospotřeba × (cena dodavatele − PPA cena) (kap. 4.4).
        uspora_t = (bil.samospotreba_kwh / 1000.0) * (cena_dod_t - cena_ppa_t)
        uspora_kum += uspora_t

        # Investor: výnos z PPA + volitelně z prodeje přetoku, minus O&M (kap. 4.5).
        vynos_ppa = (bil.samospotreba_kwh / 1000.0) * cena_ppa_t
        vynos_pre = (bil.export_kwh / 1000.0) * cena_pre_t if v.prebytek_uctovat else 0.0
        oam = v.oam_kc_kwp_rok * v.kwp
        cf = vynos_ppa + vynos_pre - oam
        cf_rok.append(cf)

        roky.append(
            {
                "rok": t,
                "vyroba_kwh": round(bil.vyroba_kwh, 1),
                "samospotreba_kwh": round(bil.samospotreba_kwh, 1),
                "export_kwh": round(bil.export_kwh, 1),
                "orez_kwh": round(bil.orez_kwh, 1),
                "dokup_kwh": round(bil.dokup_kwh, 1),
                "cena_ppa_kc_mwh": round(cena_ppa_t, 2),
                "cena_dodavatel_kc_mwh": round(cena_dod_t, 2),
                "uspora_klient_kc": round(uspora_t, 2),
                "uspora_klient_kum_kc": round(uspora_kum, 2),
                "vynos_ppa_kc": round(vynos_ppa, 2),
                "vynos_prebytek_kc": round(vynos_pre, 2),
                "cf_investor_kc": round(cf, 2),
            }
        )

    # Kumulativní CF investora (po odečtení CAPEX) do řádků.
    kum = -v.capex_kc
    for r in roky:
        kum += r["cf_investor_kc"]
        r["cf_kum_investor_kc"] = round(kum, 2)

    navratnost = _payback_roky(cf_rok, v.capex_kc)
    npv = _npv(cf_rok, v.capex_kc, v.diskontni_sazba)
    irr = _irr(cf_rok, v.capex_kc)

    vyroba_rok1 = bil1.vyroba_kwh
    graf = _graf_mesicni(mesice, vyroba1, spotreba_kwh, v.rezervovany_vykon_dodavky_kw, v.interval_h)

    return {
        "kwp": round(v.kwp, 2),
        "lat": round(v.lat, 4),
        "sklon_st": v.sklon_st,
        "azimut_st": v.azimut_st,
        "merny_vynos_kwh_kwp": round(v.merny_vynos_kwh_kwp, 1),
        "k_orient": round(k_or, 3),
        "capex_kc": round(v.capex_kc, 2),
        "capex_rozpad": v.capex_rozpad,
        "delka_kontraktu_roky": v.delka_kontraktu_roky,
        "rocni_spotreba_kwh": round(e_spotreba, 1),
        "vyroba_rok1_kwh": round(vyroba_rok1, 1),
        "samospotreba_rok1_kwh": round(bil1.samospotreba_kwh, 1),
        "export_rok1_kwh": round(bil1.export_kwh, 1),
        "orez_rok1_kwh": round(bil1.orez_kwh, 1),
        "mira_samospotreby": round(bil1.samospotreba_kwh / vyroba_rok1, 3) if vyroba_rok1 > 0 else 0.0,
        "mira_sobestacnosti": round(bil1.samospotreba_kwh / e_spotreba, 3) if e_spotreba > 0 else 0.0,
        # Headline % – jaký podíl spotřeby klienta pokryje FVE (= míra soběstačnosti).
        "pokryti_spotreby_fve": round(bil1.samospotreba_kwh / e_spotreba, 3) if e_spotreba > 0 else 0.0,
        # Poměr roční výroby k roční spotřebě (informativní, kap. 6).
        "pomer_vyroba_spotreba": round(vyroba_rok1 / e_spotreba, 3) if e_spotreba > 0 else 0.0,
        "mira_orezu": round(bil1.orez_kwh / vyroba_rok1, 3) if vyroba_rok1 > 0 else 0.0,
        "prebytek_uctovat": v.prebytek_uctovat,
        "prebytek_cena_kc_mwh": round(v.prebytek_cena_kc_mwh, 2),
        "rezervovany_vykon_dodavky_kw": v.rezervovany_vykon_dodavky_kw,
        "index_ppa_rocni": v.index_ppa_rocni,
        "index_dodavatel_rocni": v.index_dodavatel_rocni,
        "navratnost_roky": round(navratnost, 2) if navratnost is not None else None,
        "irr": round(irr, 4) if irr is not None else None,
        "npv_kc": round(npv, 2),
        "diskontni_sazba": v.diskontni_sazba,
        "souhrn_klient": {"uspora_kum_kc": round(uspora_kum, 2)},
        "souhrn_investor": {
            "cf_kum_kc": round(kum, 2),
            "payback_roky": round(navratnost, 2) if navratnost is not None else None,
        },
        "roky": roky,
        "graf": graf,
    }
