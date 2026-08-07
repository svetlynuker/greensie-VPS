"""Katalog dat pro nabídkovou šablonu + výchozí předlohy + resolver hodnot.

Sem patří JEDINÁ pojistka „do nabídky jen zákaznická data" (viz zadání Dana,
volba: v editoru jen zákaznická pole). Funguje na principu WHITELISTU:

- `_POLE_PPA` / `_POLE_PS` vyjmenovávají POUZE zákaznická pole. Ke každému
  poli patří extraktor (funkce), který hodnotu vytáhne z `popis_json`
  konkrétního `NavrhovaneReseni`. Interní čísla (CAPEX, NPV, IRR, marže,
  náklady/výnosy investora) tu extraktor NEMAJÍ, takže je resolver nikdy
  nevrátí a editor je ani nenabídne. I kdyby uložená konfigurace odkazovala
  na neznámý klíč, resolver ho přeskočí a `PUT` ho odmítne (schvalování v
  routes.py přes `platne_klice`).

Formátování na čísla se dělá tady (čeština: mezera po tisících, desetinná
čárka), ať frontend jen zobrazuje hotový text – stejný princip jako jinde
v appce, kde backend posílá připravená data.
"""

from __future__ import annotations

from typing import Any, Callable

from . import kombinace as kombinace_modul
from . import ppa_tvar


# ---- Formátování čísel (čeština) --------------------------------------------
NBSP = " "


def _cislo(x: float, des: int = 0) -> str:
    """Číslo česky: tisíce oddělené pevnou mezerou, desetinná čárka."""
    s = f"{x:,.{des}f}"  # 1,234,567.8 (en styl)
    return s.replace(",", NBSP).replace(".", ",")


def _fmt(hodnota: Any, format: str) -> str:
    """Převede surovou hodnotu na hezký český text podle typu formátu."""
    if hodnota is None:
        return "—"
    if format == "text":
        return str(hodnota)
    try:
        h = float(hodnota)
    except (TypeError, ValueError):
        return str(hodnota)
    if format == "penize":  # Kč, celé
        return f"{_cislo(round(h))}{NBSP}Kč"
    if format == "penize_mwh":  # Kč/MWh, celé
        return f"{_cislo(round(h))}{NBSP}Kč/MWh"
    if format == "vykon_kwp":  # kWp, 1 desetinné
        return f"{_cislo(h, 1)}{NBSP}kWp"
    if format == "vykon_kw":  # kW, celé
        return f"{_cislo(round(h))}{NBSP}kW"
    if format == "kapacita_kwh":  # kWh, 1 desetinné
        return f"{_cislo(h, 1)}{NBSP}kWh"
    if format == "energie_mwh":  # vstup v kWh → MWh, 1 desetinné
        return f"{_cislo(h / 1000.0, 1)}{NBSP}MWh"
    if format == "procento":  # podíl 0–1 → %
        return f"{_cislo(h * 100.0, 0)}{NBSP}%"
    if format == "roky":  # doba, 1 desetinné, „roku/let" neřešíme (číslo + roky)
        return f"{_cislo(h, 1)}{NBSP}let"
    if format == "roky_cele":
        return f"{_cislo(round(h))}{NBSP}let"
    if format == "pocet":
        return f"{_cislo(round(h))}{NBSP}ks"
    if format == "stupne":
        return f"{_cislo(round(h))}{NBSP}°"
    return _cislo(h, 1)


# ---- Bezpečné čtení z popis_json --------------------------------------------
def _g(d: Any, *cesta: str) -> Any:
    """Bezpečně projde vnořený dict podle klíčů; při chybějícím klíči vrátí None."""
    cur = d
    for k in cesta:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _prvni(*hodnoty: Any) -> Any:
    """První hodnota, která není None (nula je platná hodnota, na rozdíl od `or`)."""
    for h in hodnoty:
        if h is not None:
            return h
    return None


def _pv(popis: dict, *cesta: str) -> Any:
    """Čtení z výsledku PPA přes sjednocení verzí (`ppa_tvar`).

    Nabídky PPA existují ve dvou tvarech (starší `vysledek`, novější
    `bez_baterie`/`s_baterii` → `po_delkach`). Extraktory tu rozdíl neřeší –
    jinak by se stalo, co se stalo po nasazení v2: nabídka se tiskla prázdná.
    """
    return _g(ppa_tvar.vysledek(popis), *cesta)


def _mwh_na_kwh(hodnota: Any) -> Any:
    """MWh → kWh, protože formát `energie_mwh` čeká vstup v kWh.

    PPA + BESS drží energie v MWh (tak je má i panel), PPA v kWh. Než měnit
    formát, je čistší převést hodnotu – formát `energie_mwh` používají všechny
    tři existující typy a přepisovat ho by znamenalo sáhnout do nich.
    """
    if hodnota is None:
        return None
    try:
        return float(hodnota) * 1000.0
    except (TypeError, ValueError):
        return None


def _prvni_rok(popis: dict, klic: str) -> Any:
    """Hodnota z prvního roku ekonomiky PPA (`roky[0][klic]`)."""
    roky = _pv(popis, "roky")
    if isinstance(roky, list) and roky and isinstance(roky[0], dict):
        return roky[0].get(klic)
    return None


# ---- Definice pole šablony ---------------------------------------------------
class Pole:
    """Jedno zobrazitelné (zákaznické) pole nabídky.

    `extraktor(popis_json) -> hodnota|None`. `format` řídí český zápis.
    `nazev` je výchozí popisek (uživatel si ho v editoru může přepsat).
    `skupina` řídí, pod kterou sekci pole spadne v paletě editoru.
    """

    def __init__(
        self,
        klic: str,
        nazev: str,
        format: str,
        extraktor: Callable[[dict], Any],
        skupina: str = "Ostatní",
    ):
        self.klic = klic
        self.nazev = nazev
        self.format = format
        self.extraktor = extraktor
        self.skupina = skupina

    def slovnik(self) -> dict:
        """Podoba pro frontend (bez extraktoru)."""
        return {
            "klic": self.klic,
            "nazev": self.nazev,
            "format": self.format,
            "skupina": self.skupina,
        }


# ---- PPA: katalog zákaznických polí -----------------------------------------
# `skupina` = sekce v paletě editoru (pořadí sekcí = pořadí prvního výskytu).
_S_ELEKTRARNA = "Elektrárna"
_S_SPOTREBA = "Spotřeba a pokrytí"
_S_CENA = "Cena a kontrakt"
_S_USPORA = "Úspora"

def _ppa_rozpad(p: dict, klic: str) -> Any:
    """Položka rozpadu na náklad a výnos elektrárny (viz `ppa_tvar`)."""
    return ppa_tvar.rozpad_rok1(p).get(klic)


_POLE_PPA: list[Pole] = [
    Pole("kwp", "Velikost elektrárny", "vykon_kwp", lambda p: _pv(p, "kwp"),
         _S_ELEKTRARNA),
    Pole("vyroba_rok1_kwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _pv(p, "vyroba_rok1_kwh"), _S_ELEKTRARNA),
    Pole("sklon_st", "Sklon panelů", "stupne", lambda p: _pv(p, "sklon_st"),
         _S_ELEKTRARNA),
    Pole("azimut_st", "Orientace panelů (azimut)", "stupne",
         lambda p: _pv(p, "azimut_st"), _S_ELEKTRARNA),
    Pole("rocni_spotreba_kwh", "Vaše roční spotřeba", "energie_mwh",
         lambda p: _pv(p, "rocni_spotreba_kwh"), _S_SPOTREBA),
    Pole("samospotreba_rok1_kwh", "Přímo spotřebováno z elektrárny", "energie_mwh",
         lambda p: _pv(p, "samospotreba_rok1_kwh"), _S_SPOTREBA),
    Pole("pokryti_spotreby_fve", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _pv(p, "pokryti_spotreby_fve"), _S_SPOTREBA),
    Pole("delka_kontraktu_roky", "Doba kontraktu", "roky_cele",
         lambda p: _pv(p, "delka_kontraktu_roky"), _S_CENA),
    Pole("cena_ppa_rok1_kc_mwh", "Cena elektřiny z elektrárny (1. rok)", "penize_mwh",
         lambda p: _prvni_rok(p, "cena_ppa_kc_mwh"), _S_CENA),
    Pole("vyhnutelna_cena_rok1_kc_mwh", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _pv(p, "vyhnutelna_cena_rok1_kc_mwh"), _S_CENA),
    # Náklad a výnos elektrárny: co za elektřinu zaplatíte nám proti tomu, co
    # byste za ni zaplatili dodavateli. Rozdíl = úspora o řádek níž.
    Pole("naklad_rok1_kc", "Platba za elektřinu z elektrárny (1. rok)", "penize",
         lambda p: _ppa_rozpad(p, "naklad_rok1_kc"), _S_USPORA),
    Pole("vynos_rok1_kc", "Cena téže elektřiny od dodavatele (1. rok)", "penize",
         lambda p: _ppa_rozpad(p, "vynos_rok1_kc"), _S_USPORA),
    Pole("investice_zakaznika_kc", "Vaše investice", "penize",
         lambda p: _ppa_rozpad(p, "investice_kc"), _S_USPORA),
    Pole("uspora_rok1_kc", "Úspora v 1. roce", "penize",
         lambda p: _prvni_rok(p, "uspora_klient_kc"), _S_USPORA),
    Pole("uspora_kum_kc", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _pv(p, "souhrn_klient", "uspora_kum_kc"), _S_USPORA),
]

# Sloupce roční tabulky PPA (jen zákaznické). Pořadí = pořadí sloupců.
_TABULKA_PPA = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "cena_ppa_kc_mwh", "nazev": "Cena z elektrárny", "format": "penize_mwh"},
    {"klic": "cena_dodavatel_kc_mwh", "nazev": "Vaše dnešní cena", "format": "penize_mwh"},
    {"klic": "uspora_klient_kc", "nazev": "Úspora v roce", "format": "penize"},
    {"klic": "uspora_klient_kum_kc", "nazev": "Úspora celkem", "format": "penize"},
]


# ---- Peak shaving: katalog zákaznických polí --------------------------------
def _dop(p: dict, *cesta: str) -> Any:
    """Zkratka do doporučené (vítězné) varianty peak shavingu."""
    return _g(p, "doporucena", *cesta)


def _uspora_2027(p: dict) -> Any:
    """Roční úspora modelu 2027 – stejné pořadí zdrojů jako panel v nabídkovači
    (starší uložené výsledky mají jen `rocni_uspora`)."""
    return _prvni(
        _dop(p, "ekonomika_2027", "rocni_uspora_bez_aku"),
        _dop(p, "ekonomika_2027", "rocni_uspora"),
    )


# Názvy režimů baterie pro zákazníka. Drží se `REZIMY` v panelu i na backendu
# (`spot_arbitraz.REZIMY`), jen popsané řečí nabídky.
_REZIM_NAZVY = {
    "peak_shaving": "Srážení špiček odběru",
    "kombinace": "Srážení špiček + obchod s elektřinou",
    "spot": "Obchod s elektřinou",
}


def _rezim_nazev(p: dict) -> Any:
    rezim = _dop(p, "rezim") or _g(p, "vstup", "rezim")
    return _REZIM_NAZVY.get(rezim) if rezim else None


def _zisk_obchodu(p: dict) -> Any:
    """Roční výnos z obchodování. U čistého peak shavingu se neobchoduje –
    vrací None (pole se pak v tisku vůbec neukáže, místo nuly)."""
    rezim = _dop(p, "rezim") or _g(p, "vstup", "rezim") or "peak_shaving"
    if rezim == "peak_shaving":
        return None
    return _prvni(_dop(p, "zisk_spot_kc"), _dop(p, "ekonomika_spot", "zisk_kc"))


_S_RESENI = "Navržené řešení"
_S_KAPACITA = "Rezervovaná kapacita"
_S_USPORA_2026 = "Úspora 2026"
_S_USPORA_2027 = "Úspora od 2027"
_S_OBCHOD = "Obchod s elektřinou"

_POLE_PS: list[Pole] = [
    Pole("nazev", "Navržená baterie", "text", lambda p: _dop(p, "nazev"), _S_RESENI),
    Pole("pocet_kusu", "Počet kusů", "pocet", lambda p: _dop(p, "pocet_kusu"), _S_RESENI),
    Pole("celkovy_vykon_kw", "Výkon baterie", "vykon_kw",
         lambda p: _dop(p, "celkovy_vykon_kw"), _S_RESENI),
    Pole("celkova_kapacita_kwh", "Kapacita baterie", "kapacita_kwh",
         lambda p: _dop(p, "celkova_kapacita_kwh"), _S_RESENI),
    Pole("cena_celkem_kc", "Investice do baterie", "penize",
         lambda p: _dop(p, "cena_celkem_kc"), _S_RESENI),
    Pole("rezervovana_kapacita_kw", "Současná rezervovaná kapacita", "vykon_kw",
         lambda p: _g(p, "vstup", "rezervovana_kapacita_kw"), _S_KAPACITA),
    Pole("nova_rezervovana_kapacita_kw", "Nová rezervovaná kapacita", "vykon_kw",
         lambda p: _dop(p, "nova_rezervovana_kapacita_kw"), _S_KAPACITA),
    Pole("strop_kw", "Špičku snížíme na", "vykon_kw", lambda p: _dop(p, "strop_kw"),
         _S_KAPACITA),
    # Model 2026 = platba za rezervovanou kapacitu. Rok je v názvu schválně:
    # od 2027 platí jiná tarifní struktura a čísla se liší (viz pole níž).
    Pole("soucasny_naklad_celkem", "Dnešní roční náklad za rezervaci (2026)", "penize",
         lambda p: _dop(p, "ekonomika_2026", "soucasny_naklad_celkem"), _S_USPORA_2026),
    Pole("rocni_uspora_2026_kc", "Roční úspora (2026)", "penize",
         lambda p: _dop(p, "rocni_uspora_2026_kc"), _S_USPORA_2026),
    Pole("navratnost_roky", "Návratnost investice (2026)", "roky",
         lambda p: _dop(p, "navratnost_roky"), _S_USPORA_2026),
    # Model od 2027 (nová tarifní struktura ERÚ) – přesně ta čísla, která
    # nabídkovač ukazuje jako výchozí. Bez oficiálních sazeb ERÚ zůstanou
    # prázdná (`ekonomika_2027.status != "spocitano"`) a v tisku se skryjí.
    Pole("rezervovany_prikon_kw", "Současný rezervovaný příkon", "vykon_kw",
         lambda p: _dop(p, "ekonomika_2027", "rp_soucasny_kw"), _S_USPORA_2027),
    Pole("novy_rezervovany_prikon_kw", "Rezervovaný příkon po instalaci", "vykon_kw",
         lambda p: _prvni(_dop(p, "ekonomika_2027", "rp_novy_kw"),
                          _dop(p, "ekonomika_2027", "rezervovana_kapacita_kw")),
         _S_USPORA_2027),
    Pole("soucasny_naklad_2027_kc", "Dnešní roční náklad (tarify od 2027)", "penize",
         lambda p: _dop(p, "ekonomika_2027", "soucasny_rocni_naklad"), _S_USPORA_2027),
    Pole("novy_naklad_2027_kc", "Roční náklad s baterií (od 2027)", "penize",
         lambda p: _dop(p, "ekonomika_2027", "novy_rocni_naklad"), _S_USPORA_2027),
    Pole("rocni_uspora_2027_kc", "Roční úspora (od 2027)", "penize", _uspora_2027,
         _S_USPORA_2027),
    Pole("navratnost_2027_roky", "Návratnost investice (od 2027)", "roky",
         lambda p: _prvni(_dop(p, "navratnost_2027"), _dop(p, "navratnost_2027_konzerv")),
         _S_USPORA_2027),
    # Obchodování na spotu (režim Kombinace/Spot). U čistého peak shavingu
    # zůstane prázdné, takže se blok v tisku sám neukáže.
    Pole("rezim", "Provozní režim baterie", "text", _rezim_nazev, _S_OBCHOD),
    Pole("zisk_spot_kc", "Roční výnos z obchodu s elektřinou", "penize", _zisk_obchodu,
         _S_OBCHOD),
]

# Sloupce roční tabulky peak shavingu (jen zákaznické).
_TABULKA_PS = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "prinos_kc", "nazev": "Úspora v roce", "format": "penize"},
    {"klic": "cf_kum_kc", "nazev": "Kumulativně vč. investice", "format": "penize"},
]


# ---- Kombinace opatření: PPA + peak shaving v jedné nabídce ------------------
# Kombinace NIC NEPOČÍTÁ – čte hotové výsledky obou nabídek, které jsou
# v `popis_json` pod klíči `ppa` a `peak_shaving`. Extraktory proto míří o jednu
# úroveň hlouběji než u samostatných nabídek, ale jinak jsou to tytéž cesty.
_S_K_ELEKTRARNA = "Elektrárna (PPA)"
_S_K_BATERIE = "Baterie (peak shaving)"
_S_K_SPOLU = "Dohromady"


def _kppa(p: dict, *cesta: str):
    """Výsledek PPA nabídky uvnitř kombinace – přes sjednocení verzí."""
    return _g(ppa_tvar.vysledek(_g(p, "ppa")), *cesta)


def _kppa_rok1(p: dict, klic: str):
    """Hodnota z prvního roku ekonomiky PPA uvnitř kombinace."""
    roky = _kppa(p, "roky")
    if isinstance(roky, list) and roky and isinstance(roky[0], dict):
        return roky[0].get(klic)
    return None


def _kps(p: dict, *cesta: str):
    return _g(p, "peak_shaving", *cesta)


def _ksouhrn(p: dict, klic: str):
    """Hodnota ze souhrnu kombinace.

    Počítá se ze ZDROJŮ uložených v kombinaci, ne z uloženého `souhrn`.
    Důvod je stejný jako u společné tabulky: starší spojení mají u elektrárny
    `null` (v době spojení se četla špatným klíčem – viz `ppa_tvar`) a jejich
    součty tedy obsahují jen baterii. Zdrojové výsledky jsou přitom zmrazené
    v témže popisu, takže jde pořád o tentýž snapshot, jen správně přečtený –
    a obchodník nemusí kvůli tomu ručně aktualizovat každou starší kombinaci.

    Uložený souhrn slouží jako záloha pro případ, že by zdroje chyběly.
    """
    hodnota = _dopocteny_souhrn(p).get(klic)
    if hodnota is not None:
        return hodnota
    return _g(p, "souhrn", klic)


def _dopocteny_souhrn(p: dict) -> dict:
    """Souhrn kombinace spočítaný ze zdrojů uvnitř popisu (nikdy nevyhodí)."""
    try:
        return kombinace_modul.souhrn(_g(p, "ppa") or {}, _g(p, "peak_shaving") or {})
    except Exception:
        return {}


_POLE_KOMBINACE: list[Pole] = [
    # --- elektrárna z PPA nabídky ---
    Pole("ppa_kwp", "Velikost elektrárny", "vykon_kwp",
         lambda p: _kppa(p, "kwp"), _S_K_ELEKTRARNA),
    Pole("ppa_vyroba_rok1_kwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _kppa(p, "vyroba_rok1_kwh"), _S_K_ELEKTRARNA),
    Pole("ppa_pokryti", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _kppa(p, "pokryti_spotreby_fve"), _S_K_ELEKTRARNA),
    Pole("ppa_cena_rok1", "Cena elektřiny z elektrárny (1. rok)", "penize_mwh",
         lambda p: _kppa_rok1(p, "cena_ppa_kc_mwh"), _S_K_ELEKTRARNA),
    Pole("ppa_dnesni_cena", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _kppa(p, "vyhnutelna_cena_rok1_kc_mwh"), _S_K_ELEKTRARNA),
    Pole("delka_kontraktu_roky", "Doba kontraktu", "roky_cele",
         lambda p: _ksouhrn(p, "delka_kontraktu_roky"), _S_K_ELEKTRARNA),
    # Náklad, výnos a čistý přínos elektrárny. Investice je nula – to není
    # chybějící údaj, ale podstata PPA, takže se ukazuje jako plnohodnotné číslo.
    Pole("ppa_investice", "Investice do elektrárny", "penize",
         lambda p: _ksouhrn(p, "ppa_investice_kc"), _S_K_ELEKTRARNA),
    Pole("ppa_naklad_rok1", "Roční náklad: platba za elektřinu", "penize",
         lambda p: _ksouhrn(p, "ppa_naklad_rok1_kc"), _S_K_ELEKTRARNA),
    Pole("ppa_vynos_rok1", "Roční výnos: cena téže elektřiny od dodavatele",
         "penize", lambda p: _ksouhrn(p, "ppa_vynos_rok1_kc"), _S_K_ELEKTRARNA),
    Pole("ppa_cisty_prinos_rok1", "Čistý přínos elektrárny (1. rok)", "penize",
         lambda p: _ksouhrn(p, "ppa_cisty_prinos_rok1_kc"), _S_K_ELEKTRARNA),

    # --- baterie z peak shaving nabídky ---
    Pole("ps_nazev", "Navržená baterie", "text",
         lambda p: _kps(p, "doporucena", "nazev"), _S_K_BATERIE),
    Pole("ps_vykon_kw", "Výkon baterie", "vykon_kw",
         lambda p: _kps(p, "doporucena", "celkovy_vykon_kw"), _S_K_BATERIE),
    Pole("ps_kapacita_kwh", "Kapacita baterie", "kapacita_kwh",
         lambda p: _kps(p, "doporucena", "celkova_kapacita_kwh"), _S_K_BATERIE),
    Pole("ps_rezervovana_kapacita", "Současná rezervovaná kapacita", "vykon_kw",
         lambda p: _kps(p, "vstup", "rezervovana_kapacita_kw"), _S_K_BATERIE),
    Pole("ps_nova_rezervovana", "Nová rezervovaná kapacita", "vykon_kw",
         lambda p: _kps(p, "doporucena", "nova_rezervovana_kapacita_kw"), _S_K_BATERIE),
    Pole("ps_investice", "Investice do baterie", "penize",
         lambda p: _ksouhrn(p, "ps_investice_kc"), _S_K_BATERIE),
    Pole("ps_naklad_rok1", "Roční náklad: kapacita a provoz", "penize",
         lambda p: _ksouhrn(p, "ps_naklad_rok1_kc"), _S_K_BATERIE),
    Pole("ps_vynos_rok1", "Roční výnos: odpadlá platba a obchod", "penize",
         lambda p: _ksouhrn(p, "ps_vynos_rok1_kc"), _S_K_BATERIE),
    Pole("ps_cisty_prinos_rok1", "Čistý přínos baterie (1. rok)", "penize",
         lambda p: _ksouhrn(p, "ps_cisty_prinos_rok1_kc"), _S_K_BATERIE),
    # Dílčí položky – ať je v nabídce vidět, z čeho se náklad a výnos skládá.
    Pole("ps_vynos_kapacita_rok1", "Dnešní platba za kapacitu (odpadne)", "penize",
         lambda p: _ksouhrn(p, "ps_vynos_kapacita_rok1_kc"), _S_K_BATERIE),
    Pole("ps_naklad_kapacita_rok1", "Platba za kapacitu po instalaci", "penize",
         lambda p: _ksouhrn(p, "ps_naklad_kapacita_rok1_kc"), _S_K_BATERIE),
    Pole("ps_provozni_naklad_rok1", "Provoz a servis baterie (ročně)", "penize",
         lambda p: _ksouhrn(p, "ps_provozni_naklad_rok1_kc"), _S_K_BATERIE),
    Pole("ps_zisk_obchod_rok1", "Roční výnos z obchodu s elektřinou", "penize",
         lambda p: _ksouhrn(p, "ps_zisk_obchod_rok1_kc"), _S_K_BATERIE),

    # --- dohromady (počítá `nabidkovac/kombinace.py`) ---
    Pole("investice_zakaznika", "Vaše investice", "penize",
         lambda p: _ksouhrn(p, "investice_zakaznika_kc"), _S_K_SPOLU),
    Pole("spolu_naklad_rok1", "Roční náklady obou opatření", "penize",
         lambda p: _ksouhrn(p, "spolu_naklad_rok1_kc"), _S_K_SPOLU),
    Pole("spolu_vynos_rok1", "Roční výnosy obou opatření", "penize",
         lambda p: _ksouhrn(p, "spolu_vynos_rok1_kc"), _S_K_SPOLU),
    Pole("cisty_prinos_rok1_celkem", "Čistý přínos celkem (1. rok)", "penize",
         lambda p: _ksouhrn(p, "cisty_prinos_rok1_celkem_kc"), _S_K_SPOLU),
    Pole("uspora_ppa_rok1", "Úspora z elektrárny (1. rok)", "penize",
         lambda p: _ksouhrn(p, "uspora_ppa_rok1_kc"), _S_K_SPOLU),
    Pole("uspora_ps_rok1", "Úspora z baterie na platbách za kapacitu (1. rok)",
         "penize", lambda p: _ksouhrn(p, "uspora_ps_rok1_kc"), _S_K_SPOLU),
    Pole("uspora_rok1_celkem", "Celková úspora v 1. roce", "penize",
         lambda p: _ksouhrn(p, "uspora_rok1_celkem_kc"), _S_K_SPOLU),
    Pole("uspora_kum_celkem", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _ksouhrn(p, "uspora_kum_celkem_kc"), _S_K_SPOLU),
    Pole("navratnost_baterie", "Návratnost investice do baterie", "roky",
         lambda p: _ksouhrn(p, "navratnost_baterie_roky"), _S_K_SPOLU),
    # Návratnost z přínosu OBOU opatření – jiné číslo než návratnost baterie.
    # Ve výchozí předloze schválně není: baterie se nezaplatí z toho, co ušetří
    # elektrárna, takže tohle pole patří do nabídky jen vědomě.
    Pole("navratnost_kombinace", "Návratnost investice z celkového přínosu",
         "roky", lambda p: _ksouhrn(p, "navratnost_kombinace_roky"), _S_K_SPOLU),
]

# Společná roční tabulka – obě opatření vedle sebe a součet. Sloupce nesou
# ČISTÝ přínos (u baterie po odečtení provozu), aby se tabulka nerozcházela
# s dlaždicemi „čistý přínos" nad ní.
_TABULKA_KOMBINACE = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "uspora_ppa_kc", "nazev": "Přínos elektrárny", "format": "penize"},
    {"klic": "uspora_ps_kc", "nazev": "Přínos baterie", "format": "penize"},
    {"klic": "uspora_celkem_kc", "nazev": "Celkem v roce", "format": "penize"},
    {"klic": "uspora_kum_kc", "nazev": "Celkem kumulativně", "format": "penize"},
]


# ---- PPA + BESS: katalog zákaznických polí ----------------------------------
# Tvar výsledku je jiný než u PPA i peak shavingu: `rezimy` (tři varianty, co má
# baterie dělat) × `po_delkach` (tři délky kontraktu). Zákaznická nabídka ukazuje
# **doporučený režim** a **nejdelší nabízený kontrakt** – ten má největší slevu,
# a nabídka má prodávat. Když obchodník chce jinou délku, přepočítá si nabídku
# s jinou sadou `nabizene_delky_roky`.
#
# Investorská čísla (CAPEX, úroky, IRR, DSCR, zisk Greensie, marže) tu extraktor
# NEMAJÍ, takže je resolver zákazníkovi nikdy nevrátí a editor je ani nenabídne –
# stejná zásada jako u PPA.
_S_PB_ELEKTRARNA = "Elektrárna"
_S_PB_BATERIE = "Baterie"
_S_PB_SPICKY = "Špičky a rezervovaný příkon"
_S_PB_CENA = "Cena a kontrakt"
_S_PB_USPORA = "Vaše úspora"


def _pb_rezim(popis: dict) -> dict:
    """Doporučený režim baterie (fallback na první, kdyby příznak chyběl)."""
    rezimy = _g(popis, "rezimy")
    if not isinstance(rezimy, list) or not rezimy:
        return {}
    for r in rezimy:
        if isinstance(r, dict) and r.get("doporuceny"):
            return r
    prvni = rezimy[0]
    return prvni if isinstance(prvni, dict) else {}


def _s_volbou_delky(popis_json: dict | None, delka: int | None) -> dict:
    """Kopie popisu s vloženou volbou délky kontraktu.

    Kopie schválně: `popis_json` je uložený výsledek výpočtu a resolver ho nesmí
    měnit (hlídá to test `test_kopie_je_nezavisla`). Bez volby se vrací původní
    dict, takže se nic nekopíruje zbytečně.
    """
    popis = popis_json or {}
    if delka is None:
        return popis
    return {**popis, KLIC_VOLBA_DELKY: delka}


#: Klíč, pod kterým resolver vloží do kopie popisu délku kontraktu zvolenou
#: v editoru výstupu. Extraktory jsou lambdy `(popis) -> hodnota`, takže volbu
#: nelze předat parametrem, aniž by se změnila signatura všech tří existujících
#: typů. Podtržítko říká, že to není součást uloženého výsledku výpočtu.
KLIC_VOLBA_DELKY = "_vybrana_delka_roky"


def _pb_delka(popis: dict) -> dict:
    """Kontrakt, který nabídka ukazuje.

    Přednost má délka zvolená v editoru výstupu (`KLIC_VOLBA_DELKY`). Bez volby
    se vezme **nejdelší** nabízená – má největší slevu a nabídka má prodávat.
    Neznámá délka spadne na nejdelší, ať se nabídka nerozbije, když se sada
    nabízených délek po přepočtu změní.
    """
    delky = _g(popis, "po_delkach")
    if not isinstance(delky, list) or not delky:
        return {}
    platne = [d for d in delky if isinstance(d, dict)]
    if not platne:
        return {}
    volba = popis.get(KLIC_VOLBA_DELKY)
    if volba is not None:
        vybrana = [d for d in platne if d.get("delka_roky") == volba]
        if vybrana:
            return vybrana[0]
    return max(platne, key=lambda d: d.get("delka_roky") or 0)


def _pb(popis: dict, *cesta: str) -> Any:
    """Hodnota z doporučeného režimu (`rezimy[doporuceny]`)."""
    return _g(_pb_rezim(popis), *cesta)


def _pb_d(popis: dict, *cesta: str) -> Any:
    """Hodnota z nejdelšího kontraktu (`po_delkach[nejdelší]`)."""
    return _g(_pb_delka(popis), *cesta)


def _pb_d_1kc(popis: dict, *cesta: str) -> Any:
    """Hodnota z varianty „odkup za 1 Kč" u zobrazované délky kontraktu.

    Vrací `None`, když varianta u té délky neexistuje – tedy když kontrakt
    nepřežije nájem baterie a k odkupu vůbec nedojde. Pole se pak v nabídce
    nevykreslí, místo aby ukázalo nulu jako spočítanou hodnotu.
    """
    varianta = (_pb_delka(popis) or {}).get("odkup_1kc")
    return _g(varianta, *cesta) if isinstance(varianta, dict) else None


def _pb_nazev_baterie(popis: dict) -> Any:
    """Označení navržené baterie pro nabídku.

    Z katalogu je to název produktu. Ručně zadaná baterie žádný nemá
    (`produkt_nazev=None`) a nabídka by o modulu mlčela, i když je baterie
    spočítaná – proto se v takovém případě popis složí z parametrů. Zákazník
    má v nabídce vidět, co dostane, ne prázdné místo.
    """
    baterie = _g(popis, "baterie")
    if not isinstance(baterie, dict):
        return None
    nazev = baterie.get("nazev")
    if nazev:
        return nazev
    casti = []
    vykon = baterie.get("vykon_kw")
    kapacita = baterie.get("kapacita_kwh")
    if vykon is not None:
        casti.append(f"{_cislo(round(float(vykon)))}{NBSP}kW")
    if kapacita is not None:
        casti.append(f"{_cislo(float(kapacita), 1)}{NBSP}kWh")
    return f"Bateriové úložiště {' / '.join(casti)}" if casti else None


def _pb_prinos(popis: dict, klic: str) -> Any:
    """Přínos přepočtený na zobrazovanou délku kontraktu.

    Rozpad přínosu se v jádru počítá pro každou délku zvlášť
    (`prinos_po_delkach`), protože cena PPA se s délkou mění. Bez tohohle
    přepočtu by dlaždice v nabídce tvrdily jiné číslo než tabulka pod nimi.
    """
    delka = (_pb_delka(popis) or {}).get("delka_roky")
    po_delkach = _pb(popis, "prinos_po_delkach")
    if isinstance(po_delkach, dict) and delka is not None:
        zapis = po_delkach.get(str(delka))
        if isinstance(zapis, dict) and klic in zapis:
            return zapis.get(klic)
    return _pb(popis, "prinos", klic)


_POLE_PPA_BESS: list[Pole] = [
    # --- elektrárna
    Pole("kwp", "Velikost elektrárny", "vykon_kwp",
         lambda p: _g(p, "elektrarna", "kwp"), _S_PB_ELEKTRARNA),
    Pole("vyroba_mwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _mwh_na_kwh(_g(p, "elektrarna", "vyroba_mwh")), _S_PB_ELEKTRARNA),
    Pole("samospotreba_mwh", "Spotřebováno z elektrárny", "energie_mwh",
         lambda p: _mwh_na_kwh(_pb(p, "energie", "samospotreba_mwh")), _S_PB_ELEKTRARNA),
    Pole("pokryti_spotreby", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _pb(p, "energie", "pokryti_spotreby"), _S_PB_ELEKTRARNA),
    Pole("mira_samospotreby", "Podíl výroby spotřebovaný na místě", "procento",
         lambda p: _pb(p, "energie", "mira_samospotreby"), _S_PB_ELEKTRARNA),
    # --- baterie
    # Který modul se navrhuje a kolik kusů. Do katalogu to při vzniku typu
    # `ppa_bess` nikdo nedal, takže nabídka umělá baterii popsat jen čísly –
    # kapacitou a výkonem – a označení modulu z ní vypadlo, i když ho výpočet
    # ukládá (`ppa_bess`: baterie.nazev / pocet_kusu).
    Pole("baterie_nazev", "Modul baterie", "text", _pb_nazev_baterie, _S_PB_BATERIE),
    Pole("baterie_pocet_kusu", "Počet modulů", "pocet",
         lambda p: _g(p, "baterie", "pocet_kusu"), _S_PB_BATERIE),
    Pole("baterie_kapacita_kwh", "Kapacita baterie", "kapacita_kwh",
         lambda p: _g(p, "baterie", "kapacita_kwh"), _S_PB_BATERIE),
    Pole("baterie_vykon_kw", "Výkon baterie", "vykon_kw",
         lambda p: _g(p, "baterie", "vykon_kw"), _S_PB_BATERIE),
    Pole("baterie_najem_kc_mesic", "Nájem baterie (měsíčně)", "penize",
         lambda p: _g(p, "baterie", "najem_kc_mesic"), _S_PB_BATERIE),
    Pole("baterie_doba_najmu_roky", "Doba nájmu baterie", "roky_cele",
         lambda p: _g(p, "baterie", "doba_najmu_roky"), _S_PB_BATERIE),
    Pole("baterie_odkup_kc", "Odkupní cena baterie po nájmu", "penize",
         lambda p: _pb_d(p, "odkupni_cena_baterie_kc"), _S_PB_BATERIE),
    # Varianta „odkup za korunu": zbytková hodnota není doplatek na konci, ale
    # je rozpuštěná do nájmu. Na papíře se nabízí buď jedna varianta, nebo
    # druhá – proto jsou to samostatná pole, ne přepis těch výše.
    Pole("baterie_najem_1kc_kc_mesic", "Nájem baterie s odkupem za 1 Kč (měsíčně)",
         "penize", lambda p: _g(p, "baterie", "najem_odkup_1kc_kc_mesic"),
         _S_PB_BATERIE),
    Pole("baterie_odkup_1kc_kc", "Odkupní cena baterie po nájmu (varianta za 1 Kč)",
         "penize", lambda p: _pb_d_1kc(p, "odkupni_cena_baterie_kc"), _S_PB_BATERIE),
    # --- špičky
    Pole("rp_soucasny_kw", "Dnešní rezervovaný příkon", "vykon_kw",
         lambda p: _pb(p, "ekonomika_vykonu", "rp_soucasny_kw"), _S_PB_SPICKY),
    Pole("rp_novy_kw", "Rezervovaný příkon po instalaci", "vykon_kw",
         lambda p: _pb(p, "ekonomika_vykonu_se_snizenim", "rp_novy_kw"), _S_PB_SPICKY),
    Pole("maximum_bez_baterie_kw", "Dnešní špička odběru", "vykon_kw",
         lambda p: _pb(p, "vykon", "maximum_bez_baterie_kw"), _S_PB_SPICKY),
    Pole("maximum_po_baterii_kw", "Špička odběru s baterií", "vykon_kw",
         lambda p: _pb(p, "vykon", "maximum_po_baterii_kw"), _S_PB_SPICKY),
    Pole("sraz_kw", "O kolik baterie špičku srazí", "vykon_kw",
         lambda p: _pb(p, "vykon", "sraz_kw"), _S_PB_SPICKY),
    # --- cena a kontrakt
    Pole("delka_roky", "Doba kontraktu", "roky_cele",
         lambda p: _pb_d(p, "delka_roky"), _S_PB_CENA),
    Pole("cena_ppa_kc_mwh", "Cena elektřiny z elektrárny", "penize_mwh",
         lambda p: _pb_d(p, "cena_ppa_kc_mwh"), _S_PB_CENA),
    Pole("cena_zakaznika_kc_mwh", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _g(p, "vstup", "cena_zakaznika_kc_mwh"), _S_PB_CENA),
    Pole("sleva", "Sleva proti dnešní ceně", "procento",
         lambda p: _pb_d(p, "sleva"), _S_PB_CENA),
    # --- úspora
    Pole("uspora_z_energie_kc", "Úspora na ceně elektřiny (1. rok)", "penize",
         lambda p: _pb_prinos(p, "z_energie_kc"), _S_PB_USPORA),
    Pole("uspora_z_vykonu_kc", "Úspora na platbách za výkon (1. rok)", "penize",
         lambda p: _pb(p, "prinos", "z_vykonu_se_snizenim_rp_kc"), _S_PB_USPORA),
    Pole("najem_baterie_rocne_kc", "Nájem baterie (ročně)", "penize",
         lambda p: _pb(p, "prinos", "najem_baterie_kc"), _S_PB_USPORA),
    Pole("uspora_rok1_kc", "Čistá úspora v 1. roce", "penize",
         lambda p: _pb_d(p, "uspora_rok1_kc"), _S_PB_USPORA),
    Pole("uspora_celkem_kc", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _pb_d(p, "uspora_celkem_kc"), _S_PB_USPORA),
]

# Sloupce roční tabulky PPA + BESS (jen zákaznické – žádné DSCR ani splátky).
_TABULKA_PPA_BESS = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "cena_ppa_kc_mwh", "nazev": "Cena z elektrárny", "format": "penize_mwh"},
    {"klic": "uspora_energie_kc", "nazev": "Úspora na elektřině", "format": "penize"},
    {"klic": "uspora_vykon_kc", "nazev": "Úspora na výkonu", "format": "penize"},
    {"klic": "najem_baterie_kc", "nazev": "Nájem baterie", "format": "penize"},
    {"klic": "cisty_prinos_kc", "nazev": "Čistá úspora", "format": "penize"},
]


# ---- Rejstřík podle typu řešení ---------------------------------------------
_POLE = {
    "ppa": _POLE_PPA,
    "peak_shaving": _POLE_PS,
    "kombinace": _POLE_KOMBINACE,
    "ppa_bess": _POLE_PPA_BESS,
}
_TABULKA = {
    "ppa": _TABULKA_PPA,
    "peak_shaving": _TABULKA_PS,
    "kombinace": _TABULKA_KOMBINACE,
    "ppa_bess": _TABULKA_PPA_BESS,
}

PODPOROVANE_TYPY = tuple(_POLE.keys())


def _mapa_poli(typ: str) -> dict[str, Pole]:
    return {p.klic: p for p in _POLE.get(typ, [])}


def platne_klice(typ: str) -> set[str]:
    """Klíče polí, které smí konfigurace obsahovat (whitelist pro `PUT`)."""
    return set(_mapa_poli(typ).keys())


def platne_sloupce(typ: str) -> set[str]:
    """Klíče sloupců tabulky, které smí konfigurace obsahovat."""
    return {s["klic"] for s in _TABULKA.get(typ, [])}


def katalog_pro_frontend(typ: str) -> dict:
    """Katalog dostupných polí + sloupců tabulky pro editor (bez extraktorů)."""
    return {
        "pole": [p.slovnik() for p in _POLE.get(typ, [])],
        "tabulka_sloupce": list(_TABULKA.get(typ, [])),
    }


# ---- Resolver hodnot ---------------------------------------------------------
def resolvni_hodnoty(
    typ: str, popis_json: dict | None, delka_kontraktu_roky: int | None = None
) -> dict[str, dict]:
    """Vrátí mapu {klic: {nazev, format, hodnota, hodnota_text}} pro všechna
    zákaznická pole daného typu. Chybějící hodnoty mají `hodnota=None` a
    `hodnota_text="—"` (v náhledu se ukážou jako zástupné).

    `delka_kontraktu_roky` je volba z editoru výstupu – týká se typů, které
    počítají víc délek naráz (`ppa_bess`). Vkládá se do **kopie** popisu, aby se
    uložený výsledek výpočtu nezměnil.
    """
    popis = _s_volbou_delky(popis_json, delka_kontraktu_roky)
    out: dict[str, dict] = {}
    for pole in _POLE.get(typ, []):
        try:
            hodnota = pole.extraktor(popis)
        except Exception:
            hodnota = None
        out[pole.klic] = {
            "nazev": pole.nazev,
            "format": pole.format,
            "hodnota": hodnota,
            "hodnota_text": _fmt(hodnota, pole.format),
        }
    return out


def resolvni_tabulku(
    typ: str, popis_json: dict | None, delka_kontraktu_roky: int | None = None
) -> dict:
    """Vrátí roční tabulku {sloupce:[...], radky:[[text,...],...]} – jen
    zákaznické sloupce. PPA čte svůj výsledek, peak shaving `doporucena.roky`.

    `delka_kontraktu_roky` funguje stejně jako u `resolvni_hodnoty` – tabulka
    musí být z TÉŽE délky jako dlaždice, jinak si čísla v nabídce odporují.
    """
    popis = _s_volbou_delky(popis_json, delka_kontraktu_roky)
    sloupce = _TABULKA.get(typ, [])
    if typ == "ppa":
        radky_zdroj = _pv(popis, "roky") or []
    elif typ == "ppa_bess":
        # Roky zákazníka z nejdelšího kontraktu – ze stejné délky, ze které se
        # čtou dlaždice, jinak by si tabulka a dlaždice odporovaly.
        radky_zdroj = _pb_d(popis, "roky") or []
    elif typ == "kombinace":
        # Společná tabulka se skládá ze ZDROJŮ uložených v kombinaci, ne
        # z uloženého `roky`. Jsou to tatáž zmrazená data, jen přečtená
        # aktuální logikou – jinak by tabulka ukazovala jiná čísla než
        # dlaždice nad ní (starší spojení mají u elektrárny `null` a
        # u baterie přínos před odečtením provozu).
        try:
            radky_zdroj = kombinace_modul.spolecna_tabulka(
                _g(popis, "ppa") or {}, _g(popis, "peak_shaving") or {}
            )
        except Exception:
            radky_zdroj = []
        if not radky_zdroj:
            radky_zdroj = _g(popis, "roky") or []
    else:
        radky_zdroj = _dop(popis, "roky") or []
    radky = []
    if isinstance(radky_zdroj, list):
        for r in radky_zdroj:
            if not isinstance(r, dict):
                continue
            radky.append([_fmt(r.get(s["klic"]), s["format"]) for s in sloupce])
    return {"sloupce": sloupce, "radky": radky}


def _graf_ps_k_zobrazeni(graf: dict, popis: dict) -> dict:
    """Doplní grafu peak shavingu řadu a referenční čáry toho modelu, který
    ukazuje nabídkovač – aby graf v nabídce nebyl jiný než ten na obrazovce.

    Nabídkovač zobrazuje model **2027**, jakmile je ekonomika 2027 spočítaná
    (jinak spadne na 2026). Rok rozhoduje o obojím:
    - sloupce „s baterií": 2027 sráží špičku po měsících, 2026 drží roční strop,
    - referenční čáry: 2026 = rezervovaná kapacita, 2027 = rezervovaný příkon.
    Starší uložené výsledky nesou jen sadu 2026, pak zůstane 2026.
    """
    ek27 = _dop(popis, "ekonomika_2027") or {}
    je2027 = ek27.get("status") == "spocitano" and graf.get("s_baterii_2027_kw") is not None
    out = dict(graf)  # kopie: `popis_json` se nesmí měnit
    if je2027:
        out["rok_modelu"] = 2027
        out["s_baterii_kw"] = graf.get("s_baterii_2027_kw")
        out["rp_soucasna_zobrazena_kw"] = _prvni(
            graf.get("rp_soucasna_2027_kw"), ek27.get("rp_soucasny_kw"), graf.get("rp_soucasna_kw")
        )
        out["rp_nova_zobrazena_kw"] = _prvni(
            graf.get("rp_nova_2027_kw"),
            ek27.get("rp_novy_kw"),
            ek27.get("rezervovana_kapacita_kw"),
            graf.get("rp_nova_kw"),
        )
        out["popis_soucasna"] = "rezervovaný příkon nyní"
        out["popis_nova"] = "rezervovaný příkon po instalaci"
    else:
        out["rok_modelu"] = 2026
        out["s_baterii_kw"] = graf.get("s_baterii_2026_kw")
        out["rp_soucasna_zobrazena_kw"] = graf.get("rp_soucasna_kw")
        out["rp_nova_zobrazena_kw"] = graf.get("rp_nova_kw")
        out["popis_soucasna"] = "rezervovaná kapacita nyní"
        out["popis_nova"] = "nová rezervovaná kapacita"
    return out


def graf_pro_typ(
    typ: str, popis_json: dict | None, delka_kontraktu_roky: int | None = None
) -> dict | None:
    """Surová data grafu pro daný typ (PPA výroba/spotřeba, PS měsíční maxima).
    Frontend podle `typ_reseni` vybere správnou grafovou komponentu.

    U kombinace vrací OBA grafy pod klíči `ppa` a `peak_shaving` – nabídka na
    obojí má ukázat elektrárnu i špičky, ne si jedno vybrat."""
    popis = popis_json or {}
    if typ == "kombinace":
        ppa_graf = _kppa(popis, "graf")
        ps_zdroj = _g(popis, "peak_shaving") or {}
        ps_graf = _dop(ps_zdroj, "graf") or _g(ps_zdroj, "graf")
        return {
            "kombinace": True,
            "ppa": ppa_graf,
            "peak_shaving": (
                _graf_ps_k_zobrazeni(ps_graf, ps_zdroj) if isinstance(ps_graf, dict) else None
            ),
        }
    if typ == "ppa":
        return _pv(popis, "graf")
    if typ == "ppa_bess":
        # Elektrárna proti spotřebě z doporučeného režimu. Tvar je shodný s PPA
        # (`GrafVyrobaSpotreba`), takže frontend použije tutéž komponentu.
        graf = _pb(popis, "graf")
        return graf if isinstance(graf, dict) else None
    # peak shaving: graf doporučené varianty, fallback na graf na nejvyšší úrovni
    graf = _dop(popis, "graf") or _g(popis, "graf")
    if not isinstance(graf, dict):
        return None
    return _graf_ps_k_zobrazeni(graf, popis)


# ---- Výchozí předlohy --------------------------------------------------------
# Bloky: druh ∈ {hlavicka, text, udaje, graf, tabulka}. `viditelny` = ve výstupu.
# `pole` u udaje/tabulka = klíče z katalogu. Texty jsou editovatelné „povídání".
_UVOD_PPA = (
    "Děkujeme za váš zájem o dodávku elektřiny z fotovoltaické elektrárny. "
    "Elektrárnu na vaší střeše postavíme a plně zainvestujeme my – vy neplatíte "
    "žádnou počáteční investici. Následně od nás odebíráte vyrobenou elektřinu "
    "za cenu nižší, než platíte dnes, po celou dobu kontraktu."
)
_ZAVER_PPA = (
    "Tato nabídka je nezávazná a slouží jako orientační přehled. Rádi vám "
    "kdykoli vysvětlíme jednotlivé údaje a připravíme konečnou smlouvu na míru. "
    "Kontaktujte nás – těšíme se na spolupráci."
)
_UVOD_PS = (
    "Děkujeme za váš zájem o bateriové úložiště pro snížení špiček odběru "
    "(peak shaving). Baterie ořezává krátké špičky vašeho odběru, díky čemuž "
    "můžete snížit sjednanou rezervovanou kapacitu a platit distributorovi méně "
    "– bez omezení vašeho běžného provozu."
)
_ZAVER_PS = (
    "Tato nabídka je nezávazná a slouží jako orientační přehled. Rádi vám "
    "kdykoli vysvětlíme jednotlivé údaje a připravíme konečné řešení na míru. "
    "Kontaktujte nás – těšíme se na spolupráci."
)

_UVOD_KOMB = (
    "Děkujeme za váš zájem o kombinaci dvou opatření: fotovoltaické elektrárny "
    "na vaší střeše a bateriového úložiště pro srážení špiček odběru. Elektrárnu "
    "postavíme a plně zainvestujeme my a vy z ní odebíráte elektřinu levněji, "
    "než platíte dnes. Baterie navíc sníží vaše platby distributorovi za "
    "rezervovanou kapacitu. Obě opatření se doplňují a fungují vedle sebe."
)
_UVOD_PB = (
    "Děkujeme za váš zájem o dodávku elektřiny z fotovoltaické elektrárny "
    "s bateriovým úložištěm. Elektrárnu i baterii postavíme a plně zainvestujeme "
    "my – vy neplatíte žádnou počáteční investici. Z elektrárny pak odebíráte "
    "elektřinu levněji, než platíte dnes, a baterie k tomu srazí vaše špičky "
    "odběru, takže ušetříte i na platbách distributorovi za rezervovaný příkon. "
    "Baterii máte v nájmu za pevnou měsíční částku a po jeho skončení si ji "
    "můžete odkoupit."
)
_ZAVER_PB = (
    "Tato nabídka je nezávazná a slouží jako orientační přehled. Úspora na "
    "platbách za výkon vychází z tarifní struktury platné od roku 2027 a "
    "z vašeho naměřeného odběru za poslední rok. Rádi vám kdykoli vysvětlíme "
    "jednotlivé údaje a připravíme konečnou smlouvu na míru."
)
_ZAVER_KOMB = (
    "Tato nabídka je nezávazná a slouží jako orientační přehled obou opatření. "
    "Rádi vám kdykoli vysvětlíme jednotlivé údaje a připravíme konečné řešení "
    "na míru. Kontaktujte nás – těšíme se na spolupráci."
)


# ---- Rozvržení výchozí předlohy (model v2) -----------------------------------
# Papír je natvrdo A4 na výšku a prvky na něm leží na milimetrových
# souřadnicích. Předlohu proto nepíšeme ručně po souřadnicích – popíšeme
# sekce a rozvržení dopočítá generátor níž: skládá je pod sebe a jakmile by
# sekce přetekla přes spodní mez, založí novou stránku.
#
# Hodnoty odpovídají CSS v `frontend/src/styles/vystup.css`: 16 mm boční
# okraje, nahoře pruh se značkou, dole kontaktní zápatí.
OKRAJ_BOK_MM = 16.0
OBSAH_SIRKA_MM = 210.0 - 2 * OKRAJ_BOK_MM  # 178
OBSAH_OD_MM = 34.0  # pod pruhem se značkou
OBSAH_DO_MM = 266.0  # nad zápatím
MEZERA_SEKCI_MM = 7.0

# Odhady výšek. Nemusí sedět na milimetr – prvky s `auto_vyska` si po
# vykreslení výšku dopočítají v prohlížeči; tohle jen rozmisťuje předlohu,
# aby po otevření vypadala složeně a ne na sobě.
_VYSKA_RADKU_MM = 4.6
_ZNAKU_NA_RADEK = 96
_VYSKA_NADPISU_MM = 9.0
_VYSKA_DLAZDICE_MM = 24.0
_VYSKA_GRAFU_MM = 82.0
_VYSKA_RADKU_TABULKY_MM = 7.0


def _vyska_textu(text: str, s_nadpisem: bool) -> float:
    radku = max(1, -(-len(text) // _ZNAKU_NA_RADEK))  # zaokrouhlení nahoru
    return radku * _VYSKA_RADKU_MM + (_VYSKA_NADPISU_MM if s_nadpisem else 0) + 3


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _html_text(nadpis: str | None, text: str | None) -> str:
    """Formátovaný obsah textového prvku – nadpis a odstavec, jak je uvidí
    obchodník v editoru (a smí je tam přepsat i přeformátovat)."""
    kusy = []
    if nadpis:
        kusy.append(f"<h2>{_escape(nadpis)}</h2>")
    if text:
        kusy.append(f"<p>{_escape(text)}</p>")
    return "".join(kusy)


def _styl(**kw) -> dict:
    """Styl prvku s výchozími hodnotami shodnými se schématem."""
    zaklad = {
        "pozadi": "",
        "barva_ramecku": "",
        "sirka_ramecku": 0,
        "zaobleni": 0,
        "odsazeni": 4,
        "mezera": 4,
        "pruhlednost": 1,
        "sloupce": 1,
    }
    zaklad.update(kw)
    return zaklad


def _prvek(id_: str, druh: str, **kw) -> dict:
    """Prvek s kompletní sadou polí, ať předloha projde schématem beze změn."""
    p = {
        "id": id_,
        "druh": druh,
        "viditelny": True,
        "x": OKRAJ_BOK_MM,
        "y": OBSAH_OD_MM,
        "sirka": OBSAH_SIRKA_MM,
        "vyska": 20.0,
        "auto_vyska": True,
        "z": 0,
        "zamceno": False,
        "styl": _styl(),
        "html": "",
        "klic": "",
        "pole": [],
        "obrazek": "",
        "popis": "",
        "deti": [],
    }
    p.update(kw)
    return p


def _sekce_nadpis(id_: str, nadpis: str, podnadpis: str) -> tuple[dict, float]:
    html = f"<h1>{_escape(nadpis)}</h1>"
    if podnadpis:
        html += f'<p style="color: #6a7570">{_escape(podnadpis)}</p>'
    vyska = 13.0 + (6.0 if podnadpis else 0)
    return _prvek(id_, "text", html=html, vyska=vyska, auto_vyska=True), vyska


def _sekce_text(id_: str, nadpis: str, text: str) -> tuple[dict, float]:
    vyska = _vyska_textu(text, bool(nadpis))
    return _prvek(id_, "text", html=_html_text(nadpis, text), vyska=vyska), vyska


def _sekce_dlazdice(
    id_: str, nadpis: str, uvod: str, klice: list[str], sloupce: int
) -> tuple[dict, float]:
    """Kontejner s dlaždicemi údajů. Nadpis kontejneru je jeho `html`,
    dlaždice jsou děti a tečou do mřížky o `sloupce` sloupcích."""
    radku = max(1, -(-len(klice) // sloupce))
    vnitrni_sirka = (OBSAH_SIRKA_MM - 2 * 4 - (sloupce - 1) * 4) / sloupce
    deti = [
        _prvek(
            f"{id_}-{k}",
            "udaj",
            klic=k,
            sirka=vnitrni_sirka,
            vyska=_VYSKA_DLAZDICE_MM,
            auto_vyska=False,
            styl=_styl(pozadi="#f4f6f5", zaobleni=2, odsazeni=3),
        )
        for k in klice
    ]
    html = _html_text(nadpis, uvod)
    vyska_hlavicky = (
        (_VYSKA_NADPISU_MM if nadpis else 0)
        + (_vyska_textu(uvod, False) if uvod else 0)
    )
    vyska = 8 + vyska_hlavicky + radku * _VYSKA_DLAZDICE_MM + (radku - 1) * 4
    kontejner = _prvek(
        id_,
        "kontejner",
        html=html,
        vyska=vyska,
        auto_vyska=True,
        styl=_styl(sloupce=sloupce, odsazeni=4, mezera=4),
        deti=deti,
    )
    return kontejner, vyska


def _sekce_graf(id_: str, nadpis: str) -> tuple[dict, float]:
    vyska = _VYSKA_GRAFU_MM + (_VYSKA_NADPISU_MM if nadpis else 0)
    kontejner = _prvek(
        id_,
        "kontejner",
        html=_html_text(nadpis, None),
        vyska=vyska,
        auto_vyska=True,
        deti=[
            _prvek(
                f"{id_}-obsah",
                "graf",
                sirka=OBSAH_SIRKA_MM - 8,
                vyska=_VYSKA_GRAFU_MM,
                auto_vyska=False,
            )
        ],
    )
    return kontejner, vyska


def _sekce_tabulka(
    id_: str, nadpis: str, sloupce: list[str], viditelny: bool
) -> tuple[dict, float]:
    vyska_tab = 10 * _VYSKA_RADKU_TABULKY_MM
    vyska = vyska_tab + (_VYSKA_NADPISU_MM if nadpis else 0) + 8
    kontejner = _prvek(
        id_,
        "kontejner",
        viditelny=viditelny,
        html=_html_text(nadpis, None),
        vyska=vyska,
        auto_vyska=True,
        deti=[
            _prvek(
                f"{id_}-obsah",
                "tabulka",
                pole=list(sloupce),
                sirka=OBSAH_SIRKA_MM - 8,
                vyska=vyska_tab,
                auto_vyska=True,
            )
        ],
    )
    return kontejner, vyska


# Popis předlohy: seznam sekcí, ze kterých generátor poskládá stránky.
# ("nadpis"|"text"|"dlazdice"|"graf"|"tabulka", id, …parametry)
def _slozky(typ: str) -> list[tuple]:
    if typ == "ppa":
        return [
            ("nadpis", "hlavicka", "Nabídka dodávky elektřiny z fotovoltaické elektrárny",
             "Řešení PPA – bez počáteční investice"),
            ("text", "uvod", "Co vám nabízíme", _UVOD_PPA),
            ("dlazdice", "klicove", "Klíčové údaje", "",
             ["kwp", "vyroba_rok1_kwh", "pokryti_spotreby_fve",
              "delka_kontraktu_roky", "cena_ppa_rok1_kc_mwh",
              "vyhnutelna_cena_rok1_kc_mwh"], 3),
            ("dlazdice", "uspora", "Vaše úspora",
             "Kolik ušetříte oproti současné ceně elektřiny.",
             ["uspora_rok1_kc", "uspora_kum_kc"], 2),
            ("graf", "graf", "Výroba elektrárny vs. vaše spotřeba (rok 1)"),
            ("tabulka", "tabulka", "Vývoj úspory po letech",
             ["rok", "cena_ppa_kc_mwh", "cena_dodavatel_kc_mwh",
              "uspora_klient_kc", "uspora_klient_kum_kc"], False),
            ("text", "zaver", "Závěrem", _ZAVER_PPA),
        ]
    if typ == "peak_shaving":
        return [
            ("nadpis", "hlavicka", "Nabídka bateriového úložiště (peak shaving)",
             "Snížení rezervované kapacity a plateb distributorovi"),
            ("text", "uvod", "Co vám nabízíme", _UVOD_PS),
            ("dlazdice", "klicove", "Navržené řešení", "",
             ["nazev", "pocet_kusu", "celkovy_vykon_kw",
              "celkova_kapacita_kwh", "cena_celkem_kc"], 3),
            ("dlazdice", "kapacita", "Snížení rezervované kapacity",
             "Baterie sráží špičky, takže vám stačí nižší sjednaná kapacita.",
             ["rezervovana_kapacita_kw", "nova_rezervovana_kapacita_kw", "strop_kw"], 3),
            ("dlazdice", "uspora", "Vaše úspora v roce 2026", "",
             ["soucasny_naklad_celkem", "rocni_uspora_2026_kc", "navratnost_roky"], 3),
            ("dlazdice", "uspora_2027",
             "Vaše úspora podle nových tarifů (od roku 2027)",
             "Od roku 2027 se platí i za naměřenou špičku odběru, takže baterie "
             "ušetří jinou částku než letos – uvádíme ji zvlášť.",
             ["rezervovany_prikon_kw", "novy_rezervovany_prikon_kw",
              "soucasny_naklad_2027_kc", "novy_naklad_2027_kc",
              "rocni_uspora_2027_kc", "navratnost_2027_roky"], 3),
            ("dlazdice", "obchod", "Obchod s elektřinou",
             "Když baterie nemusí srážet špičku, může nakupovat elektřinu levně "
             "a dodávat ji zpět dráž. Tohle je odhad ročního výnosu.",
             ["rezim", "zisk_spot_kc"], 2),
            ("graf", "graf", "Měsíční špičky odběru – dnes vs. s baterií"),
            ("tabulka", "tabulka", "Vývoj úspory po letech",
             ["rok", "prinos_kc", "cf_kum_kc"], False),
            ("text", "zaver", "Závěrem", _ZAVER_PS),
        ]
    if typ == "ppa_bess":
        return [
            ("nadpis", "hlavicka",
             "Nabídka dodávky elektřiny z elektrárny s bateriovým úložištěm",
             "PPA + BESS – bez počáteční investice"),
            ("text", "uvod", "Co vám nabízíme", _UVOD_PB),
            ("dlazdice", "klicove", "Navržené řešení", "",
             ["kwp", "vyroba_mwh", "baterie_nazev", "baterie_pocet_kusu",
              "baterie_kapacita_kwh", "baterie_vykon_kw",
              "delka_roky", "baterie_najem_kc_mesic"], 3),
            ("dlazdice", "cena", "Cena elektřiny",
             "Z elektrárny odebíráte elektřinu levněji, než platíte dnes.",
             ["cena_zakaznika_kc_mwh", "cena_ppa_kc_mwh", "sleva"], 3),
            ("dlazdice", "spicky", "Snížení špiček odběru",
             "Baterie sráží krátké špičky, takže vám stačí nižší rezervovaný "
             "příkon a platíte distributorovi méně.",
             ["maximum_bez_baterie_kw", "maximum_po_baterii_kw", "sraz_kw",
              "rp_soucasny_kw", "rp_novy_kw"], 3),
            ("dlazdice", "uspora", "Vaše úspora",
             "Úspora má dvě části: levnější elektřinu z elektrárny a nižší platby "
             "za výkon. Od součtu se odečítá nájem baterie.",
             ["uspora_z_energie_kc", "uspora_z_vykonu_kc", "najem_baterie_rocne_kc",
              "uspora_rok1_kc", "uspora_celkem_kc"], 3),
            ("graf", "graf", "Výroba elektrárny vs. vaše spotřeba"),
            ("tabulka", "tabulka", "Vývoj úspory po letech",
             ["rok", "cena_ppa_kc_mwh", "uspora_energie_kc", "uspora_vykon_kc",
              "najem_baterie_kc", "cisty_prinos_kc"], False),
            ("text", "zaver", "Závěrem", _ZAVER_PB),
        ]
    if typ == "kombinace":
        return [
            ("nadpis", "hlavicka", "Nabídka kombinace opatření: elektrárna + baterie",
             "Fotovoltaika bez investice a baterie pro srážení špiček"),
            ("text", "uvod", "Co vám nabízíme", _UVOD_KOMB),
            ("dlazdice", "spolu", "Dohromady",
             "Co vám obě opatření přinesou společně.",
             ["investice_zakaznika", "uspora_rok1_celkem", "uspora_kum_celkem",
              "navratnost_baterie"], 2),
            ("dlazdice", "elektrarna", "Fotovoltaická elektrárna", "",
             ["ppa_kwp", "ppa_vyroba_rok1_kwh", "ppa_pokryti", "delka_kontraktu_roky",
              "ppa_cena_rok1", "ppa_dnesni_cena", "uspora_ppa_rok1"], 3),
            ("dlazdice", "elektrarna_ekonomika", "Elektrárna: co stojí a co přináší",
             "Za elektřinu z elektrárny platíte místo dodavateli nám, a to méně. "
             "Rozdíl obou plateb je váš čistý přínos.",
             ["ppa_investice", "ppa_naklad_rok1", "ppa_vynos_rok1",
              "ppa_cisty_prinos_rok1"], 2),
            ("dlazdice", "baterie", "Bateriové úložiště", "",
             ["ps_nazev", "ps_vykon_kw", "ps_kapacita_kwh",
              "ps_rezervovana_kapacita", "ps_nova_rezervovana", "uspora_ps_rok1"], 3),
            ("dlazdice", "baterie_ekonomika", "Baterie: co stojí a co přináší",
             "Baterie se pořizuje jednorázově. Ročně pak snižuje platbu za "
             "kapacitu a může vydělávat obchodem s elektřinou; proti tomu stojí "
             "platba za novou kapacitu a náklady na provoz.",
             ["ps_investice", "ps_naklad_rok1", "ps_vynos_rok1",
              "ps_cisty_prinos_rok1"], 2),
            ("dlazdice", "soucet", "Obě technologie dohromady",
             "Součet nákladů a výnosů obou opatření v prvním roce.",
             ["spolu_naklad_rok1", "spolu_vynos_rok1", "cisty_prinos_rok1_celkem"], 3),
            ("graf", "graf", "Výroba elektrárny a špičky odběru"),
            ("tabulka", "tabulka", "Vývoj úspory po letech",
             ["rok", "uspora_ppa_kc", "uspora_ps_kc", "uspora_celkem_kc",
              "uspora_kum_kc"], True),
            ("text", "zaver", "Závěrem", _ZAVER_KOMB),
        ]
    return []


def _postav_predlohu(typ: str) -> dict:
    """Poskládá sekce pod sebe na A4 stránky."""
    stranky: list[dict] = [{"id": "s1", "prvky": []}]
    y = OBSAH_OD_MM
    for slozka in _slozky(typ):
        druh = slozka[0]
        if druh == "nadpis":
            prvek, vyska = _sekce_nadpis(slozka[1], slozka[2], slozka[3])
        elif druh == "text":
            prvek, vyska = _sekce_text(slozka[1], slozka[2], slozka[3])
        elif druh == "dlazdice":
            prvek, vyska = _sekce_dlazdice(
                slozka[1], slozka[2], slozka[3], slozka[4], slozka[5]
            )
        elif druh == "graf":
            prvek, vyska = _sekce_graf(slozka[1], slozka[2])
        elif druh == "tabulka":
            prvek, vyska = _sekce_tabulka(slozka[1], slozka[2], slozka[3], slozka[4])
        else:
            continue

        # Nevejde se na zbytek stránky? Založ novou. Sekce se nikdy netrhá –
        # nadpis a jeho obsah patří k sobě.
        if y + vyska > OBSAH_DO_MM and stranky[-1]["prvky"]:
            stranky.append({"id": f"s{len(stranky) + 1}", "prvky": []})
            y = OBSAH_OD_MM

        prvek["y"] = round(y, 1)
        prvek["z"] = len(stranky[-1]["prvky"])
        stranky[-1]["prvky"].append(prvek)
        y += vyska + MEZERA_SEKCI_MM

    return {
        "verze": 2,
        "stranky": stranky,
        "hlavicka": {"zobrazit": True, "text": ""},
        "zapati": {"zobrazit": True, "text": ""},
        "vodoznak": {"zobrazit": True, "pruhlednost": 0.07},
    }


def vychozi_sablona(typ: str) -> dict:
    """Výchozí předloha pro daný typ – nová nabídka startuje odtud."""
    return _postav_predlohu(typ)


def je_verze2(konfigurace: dict | None) -> bool:
    """Pozná uloženou konfiguraci v novém modelu (stránky + prvky v mm)."""
    return bool(konfigurace) and konfigurace.get("verze") == 2


def nacti_konfiguraci(typ: str, ulozene: dict | None) -> tuple[dict, bool]:
    """Vrátí (konfigurace, je_vychozi) pro editor i tisk.

    Konfigurace ze starého modelu (plochý seznam bloků v mřížce 12 sloupců)
    se nemigruje – v době přepisu byly v provozu tři a Dan zvolil čistý start.
    Bez `verze: 2` se tedy vrací výchozí předloha, uložený záznam zůstane
    v DB nedotčený, dokud ho obchodník nepřepíše tlačítkem *Uložit*.
    """
    if je_verze2(ulozene):
        return ulozene, False
    return vychozi_sablona(typ), True


def pocet_rucnich_hodnot(konfigurace: dict | None) -> int:
    """Kolik dlaždic v rozvržení má ručně přepsanou hodnotu.

    Je to jediná věc v nabídce, která smí říkat jiné číslo než výpočet, takže
    o ní musí být vidět, že tam je – v editoru i mimo něj (detail nabídky).
    Nepočítá se, jestli je prvek `viditelny`: schovaná ruční hodnota se pořád
    může vrátit jedním kliknutím a pro upozornění je to tentýž případ.
    """
    if not isinstance(konfigurace, dict):
        return 0
    pocet = 0
    for stranka in konfigurace.get("stranky") or []:
        if not isinstance(stranka, dict):
            continue
        for prvek in stranka.get("prvky") or []:
            if not isinstance(prvek, dict):
                continue
            for kandidat in [prvek, *(prvek.get("deti") or [])]:
                if not isinstance(kandidat, dict):
                    continue
                if kandidat.get("druh") == "udaj" and str(
                    kandidat.get("rucni_hodnota") or ""
                ).strip():
                    pocet += 1
    return pocet
