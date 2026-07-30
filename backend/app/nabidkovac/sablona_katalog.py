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


def _prvni_rok(popis: dict, klic: str) -> Any:
    """Hodnota z prvního roku ekonomiky PPA (`vysledek.roky[0][klic]`)."""
    roky = _g(popis, "vysledek", "roky")
    if isinstance(roky, list) and roky:
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

_POLE_PPA: list[Pole] = [
    Pole("kwp", "Velikost elektrárny", "vykon_kwp", lambda p: _g(p, "vysledek", "kwp"),
         _S_ELEKTRARNA),
    Pole("vyroba_rok1_kwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _g(p, "vysledek", "vyroba_rok1_kwh"), _S_ELEKTRARNA),
    Pole("sklon_st", "Sklon panelů", "stupne", lambda p: _g(p, "vysledek", "sklon_st"),
         _S_ELEKTRARNA),
    Pole("azimut_st", "Orientace panelů (azimut)", "stupne",
         lambda p: _g(p, "vysledek", "azimut_st"), _S_ELEKTRARNA),
    Pole("rocni_spotreba_kwh", "Vaše roční spotřeba", "energie_mwh",
         lambda p: _g(p, "vysledek", "rocni_spotreba_kwh"), _S_SPOTREBA),
    Pole("samospotreba_rok1_kwh", "Přímo spotřebováno z elektrárny", "energie_mwh",
         lambda p: _g(p, "vysledek", "samospotreba_rok1_kwh"), _S_SPOTREBA),
    Pole("pokryti_spotreby_fve", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _g(p, "vysledek", "pokryti_spotreby_fve"), _S_SPOTREBA),
    Pole("delka_kontraktu_roky", "Doba kontraktu", "roky_cele",
         lambda p: _g(p, "vysledek", "delka_kontraktu_roky"), _S_CENA),
    Pole("cena_ppa_rok1_kc_mwh", "Cena elektřiny z elektrárny (1. rok)", "penize_mwh",
         lambda p: _prvni_rok(p, "cena_ppa_kc_mwh"), _S_CENA),
    Pole("vyhnutelna_cena_rok1_kc_mwh", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _g(p, "vysledek", "vyhnutelna_cena_rok1_kc_mwh"), _S_CENA),
    Pole("uspora_rok1_kc", "Úspora v 1. roce", "penize",
         lambda p: _prvni_rok(p, "uspora_klient_kc"), _S_USPORA),
    Pole("uspora_kum_kc", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _g(p, "vysledek", "souhrn_klient", "uspora_kum_kc"), _S_USPORA),
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
    return _g(p, "ppa", *cesta)


def _kps(p: dict, *cesta: str):
    return _g(p, "peak_shaving", *cesta)


def _ksouhrn(p: dict, klic: str):
    return _g(p, "souhrn", klic)


_POLE_KOMBINACE: list[Pole] = [
    # --- elektrárna z PPA nabídky ---
    Pole("ppa_kwp", "Velikost elektrárny", "vykon_kwp",
         lambda p: _kppa(p, "vysledek", "kwp"), _S_K_ELEKTRARNA),
    Pole("ppa_vyroba_rok1_kwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _kppa(p, "vysledek", "vyroba_rok1_kwh"), _S_K_ELEKTRARNA),
    Pole("ppa_pokryti", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _kppa(p, "vysledek", "pokryti_spotreby_fve"), _S_K_ELEKTRARNA),
    Pole("ppa_cena_rok1", "Cena elektřiny z elektrárny (1. rok)", "penize_mwh",
         lambda p: (_kppa(p, "vysledek", "roky") or [{}])[0].get("cena_ppa_kc_mwh")
         if isinstance(_kppa(p, "vysledek", "roky"), list) and _kppa(p, "vysledek", "roky")
         else None, _S_K_ELEKTRARNA),
    Pole("ppa_dnesni_cena", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _kppa(p, "vysledek", "vyhnutelna_cena_rok1_kc_mwh"), _S_K_ELEKTRARNA),
    Pole("delka_kontraktu_roky", "Doba kontraktu", "roky_cele",
         lambda p: _ksouhrn(p, "delka_kontraktu_roky"), _S_K_ELEKTRARNA),

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

    # --- dohromady (počítá `nabidkovac/kombinace.py`) ---
    Pole("investice_zakaznika", "Vaše investice", "penize",
         lambda p: _ksouhrn(p, "investice_zakaznika_kc"), _S_K_SPOLU),
    Pole("uspora_ppa_rok1", "Úspora z elektrárny (1. rok)", "penize",
         lambda p: _ksouhrn(p, "uspora_ppa_rok1_kc"), _S_K_SPOLU),
    Pole("uspora_ps_rok1", "Úspora z baterie (1. rok)", "penize",
         lambda p: _ksouhrn(p, "uspora_ps_rok1_kc"), _S_K_SPOLU),
    Pole("uspora_rok1_celkem", "Celková úspora v 1. roce", "penize",
         lambda p: _ksouhrn(p, "uspora_rok1_celkem_kc"), _S_K_SPOLU),
    Pole("uspora_kum_celkem", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _ksouhrn(p, "uspora_kum_celkem_kc"), _S_K_SPOLU),
    Pole("navratnost_baterie", "Návratnost investice do baterie", "roky",
         lambda p: _ksouhrn(p, "navratnost_baterie_roky"), _S_K_SPOLU),
]

# Společná roční tabulka – obě opatření vedle sebe a součet.
_TABULKA_KOMBINACE = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "uspora_ppa_kc", "nazev": "Úspora z elektrárny", "format": "penize"},
    {"klic": "uspora_ps_kc", "nazev": "Úspora z baterie", "format": "penize"},
    {"klic": "uspora_celkem_kc", "nazev": "Celkem v roce", "format": "penize"},
    {"klic": "uspora_kum_kc", "nazev": "Celkem kumulativně", "format": "penize"},
]


# ---- Rejstřík podle typu řešení ---------------------------------------------
_POLE = {"ppa": _POLE_PPA, "peak_shaving": _POLE_PS, "kombinace": _POLE_KOMBINACE}
_TABULKA = {
    "ppa": _TABULKA_PPA,
    "peak_shaving": _TABULKA_PS,
    "kombinace": _TABULKA_KOMBINACE,
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
def resolvni_hodnoty(typ: str, popis_json: dict | None) -> dict[str, dict]:
    """Vrátí mapu {klic: {nazev, format, hodnota, hodnota_text}} pro všechna
    zákaznická pole daného typu. Chybějící hodnoty mají `hodnota=None` a
    `hodnota_text="—"` (v náhledu se ukážou jako zástupné)."""
    popis = popis_json or {}
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


def resolvni_tabulku(typ: str, popis_json: dict | None) -> dict:
    """Vrátí roční tabulku {sloupce:[...], radky:[[text,...],...]} – jen
    zákaznické sloupce. PPA čte `vysledek.roky`, peak shaving `doporucena.roky`."""
    popis = popis_json or {}
    sloupce = _TABULKA.get(typ, [])
    if typ == "ppa":
        radky_zdroj = _g(popis, "vysledek", "roky") or []
    elif typ == "kombinace":
        # Kombinace má společnou tabulku složenou z obou zdrojů (viz
        # `nabidkovac/kombinace.spolecna_tabulka`).
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


def graf_pro_typ(typ: str, popis_json: dict | None) -> dict | None:
    """Surová data grafu pro daný typ (PPA výroba/spotřeba, PS měsíční maxima).
    Frontend podle `typ_reseni` vybere správnou grafovou komponentu.

    U kombinace vrací OBA grafy pod klíči `ppa` a `peak_shaving` – nabídka na
    obojí má ukázat elektrárnu i špičky, ne si jedno vybrat."""
    popis = popis_json or {}
    if typ == "kombinace":
        ppa_graf = _g(popis, "ppa", "vysledek", "graf")
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
        return _g(popis, "vysledek", "graf")
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

VYCHOZI_SABLONA: dict[str, dict] = {
    "ppa": {
        "bloky": [
            {"id": "hlavicka", "druh": "hlavicka", "viditelny": True,
             "nadpis": "Nabídka dodávky elektřiny z fotovoltaické elektrárny",
             "text": "Řešení PPA – bez počáteční investice"},
            {"id": "uvod", "druh": "text", "viditelny": True,
             "nadpis": "Co vám nabízíme", "text": _UVOD_PPA},
            {"id": "klicove", "druh": "udaje", "viditelny": True,
             "nadpis": "Klíčové údaje",
             "pole": ["kwp", "vyroba_rok1_kwh", "pokryti_spotreby_fve",
                      "delka_kontraktu_roky", "cena_ppa_rok1_kc_mwh",
                      "vyhnutelna_cena_rok1_kc_mwh"]},
            {"id": "uspora", "druh": "udaje", "viditelny": True,
             "nadpis": "Vaše úspora",
             "text": "Kolik ušetříte oproti současné ceně elektřiny.",
             "pole": ["uspora_rok1_kc", "uspora_kum_kc"]},
            {"id": "graf", "druh": "graf", "viditelny": True,
             "nadpis": "Výroba elektrárny vs. vaše spotřeba (rok 1)"},
            {"id": "tabulka", "druh": "tabulka", "viditelny": False,
             "nadpis": "Vývoj úspory po letech",
             "pole": ["rok", "cena_ppa_kc_mwh", "cena_dodavatel_kc_mwh",
                      "uspora_klient_kc", "uspora_klient_kum_kc"]},
            {"id": "zaver", "druh": "text", "viditelny": True,
             "nadpis": "Závěrem", "text": _ZAVER_PPA},
        ]
    },
    "peak_shaving": {
        "bloky": [
            {"id": "hlavicka", "druh": "hlavicka", "viditelny": True,
             "nadpis": "Nabídka bateriového úložiště (peak shaving)",
             "text": "Snížení rezervované kapacity a plateb distributorovi"},
            {"id": "uvod", "druh": "text", "viditelny": True,
             "nadpis": "Co vám nabízíme", "text": _UVOD_PS},
            {"id": "klicove", "druh": "udaje", "viditelny": True,
             "nadpis": "Navržené řešení",
             "pole": ["nazev", "pocet_kusu", "celkovy_vykon_kw",
                      "celkova_kapacita_kwh", "cena_celkem_kc"]},
            {"id": "kapacita", "druh": "udaje", "viditelny": True,
             "nadpis": "Snížení rezervované kapacity",
             "text": "Baterie sráží špičky, takže vám stačí nižší sjednaná kapacita.",
             "pole": ["rezervovana_kapacita_kw", "nova_rezervovana_kapacita_kw",
                      "strop_kw"]},
            {"id": "uspora", "druh": "udaje", "viditelny": True,
             "nadpis": "Vaše úspora v roce 2026",
             "pole": ["soucasny_naklad_celkem", "rocni_uspora_2026_kc",
                      "navratnost_roky"]},
            # Bloky níž se v tisku samy skryjí, když pro ně data nejsou:
            # 2027 bez oficiálních sazeb ERÚ, obchod u čistého peak shavingu.
            {"id": "uspora_2027", "druh": "udaje", "viditelny": True,
             "nadpis": "Vaše úspora podle nových tarifů (od roku 2027)",
             "text": "Od roku 2027 se platí i za naměřenou špičku odběru, takže baterie "
                     "ušetří jinou částku než letos – uvádíme ji zvlášť.",
             "pole": ["rezervovany_prikon_kw", "novy_rezervovany_prikon_kw",
                      "soucasny_naklad_2027_kc", "novy_naklad_2027_kc",
                      "rocni_uspora_2027_kc", "navratnost_2027_roky"]},
            {"id": "obchod", "druh": "udaje", "viditelny": True,
             "nadpis": "Obchod s elektřinou",
             "text": "Když baterie nemusí srážet špičku, může nakupovat elektřinu levně "
                     "a dodávat ji zpět dráž. Tohle je odhad ročního výnosu.",
             "pole": ["rezim", "zisk_spot_kc"]},
            {"id": "graf", "druh": "graf", "viditelny": True,
             "nadpis": "Měsíční špičky odběru – dnes vs. s baterií"},
            {"id": "tabulka", "druh": "tabulka", "viditelny": False,
             "nadpis": "Vývoj úspory po letech",
             "pole": ["rok", "prinos_kc", "cf_kum_kc"]},
            {"id": "zaver", "druh": "text", "viditelny": True,
             "nadpis": "Závěrem", "text": _ZAVER_PS},
        ]
    },
}

_UVOD_KOMB = (
    "Děkujeme za váš zájem o kombinaci dvou opatření: fotovoltaické elektrárny "
    "na vaší střeše a bateriového úložiště pro srážení špiček odběru. Elektrárnu "
    "postavíme a plně zainvestujeme my a vy z ní odebíráte elektřinu levněji, "
    "než platíte dnes. Baterie navíc sníží vaše platby distributorovi za "
    "rezervovanou kapacitu. Obě opatření se doplňují a fungují vedle sebe."
)
_ZAVER_KOMB = (
    "Tato nabídka je nezávazná a slouží jako orientační přehled obou opatření. "
    "Rádi vám kdykoli vysvětlíme jednotlivé údaje a připravíme konečné řešení "
    "na míru. Kontaktujte nás – těšíme se na spolupráci."
)

VYCHOZI_SABLONA["kombinace"] = {
    "bloky": [
        {"id": "hlavicka", "druh": "hlavicka", "viditelny": True,
         "nadpis": "Nabídka kombinace opatření: elektrárna + baterie",
         "text": "Fotovoltaika bez investice a baterie pro srážení špiček"},
        {"id": "uvod", "druh": "text", "viditelny": True,
         "nadpis": "Co vám nabízíme", "text": _UVOD_KOMB},
        {"id": "spolu", "druh": "udaje", "viditelny": True,
         "nadpis": "Dohromady",
         "text": "Co vám obě opatření přinesou společně.",
         "pole": ["investice_zakaznika", "uspora_rok1_celkem", "uspora_kum_celkem",
                  "navratnost_baterie"]},
        {"id": "elektrarna", "druh": "udaje", "viditelny": True,
         "nadpis": "Fotovoltaická elektrárna",
         "pole": ["ppa_kwp", "ppa_vyroba_rok1_kwh", "ppa_pokryti", "delka_kontraktu_roky",
                  "ppa_cena_rok1", "ppa_dnesni_cena", "uspora_ppa_rok1"]},
        {"id": "baterie", "druh": "udaje", "viditelny": True,
         "nadpis": "Bateriové úložiště",
         "pole": ["ps_nazev", "ps_vykon_kw", "ps_kapacita_kwh",
                  "ps_rezervovana_kapacita", "ps_nova_rezervovana", "uspora_ps_rok1"]},
        {"id": "graf", "druh": "graf", "viditelny": True,
         "nadpis": "Výroba elektrárny a špičky odběru"},
        {"id": "tabulka", "druh": "tabulka", "viditelny": True,
         "nadpis": "Vývoj úspory po letech",
         "pole": ["rok", "uspora_ppa_kc", "uspora_ps_kc", "uspora_celkem_kc",
                  "uspora_kum_kc"]},
        {"id": "zaver", "druh": "text", "viditelny": True,
         "nadpis": "Závěrem", "text": _ZAVER_KOMB},
    ]
}

DRUHY_BLOKU = ("hlavicka", "text", "udaje", "graf", "tabulka")


def vychozi_sablona(typ: str) -> dict:
    """Vrátí kopii výchozí předlohy pro daný typ (nová nabídka startuje odtud)."""
    import copy

    return copy.deepcopy(VYCHOZI_SABLONA.get(typ, {"bloky": []}))


def doplnene_bloky(typ: str, konfigurace: dict | None) -> dict:
    """Doplní do uložené konfigurace bloky, které předloha zná a ona ještě ne.

    Když do předlohy přibude blok (třeba úspora podle tarifů od 2027), starší
    uložené nabídky by ho bez tohohle nikdy neukázaly – OZ by musel *Obnovit
    výchozí* a přišel by o vlastní texty. Bloky se vkládají na místo, kam patří
    v předloze (za nejbližší předchozí známý blok), a nic existujícího se
    nepřepisuje. Ukládá se to až na explicitní *Uložit*.
    """
    import copy

    vychozi = VYCHOZI_SABLONA.get(typ, {}).get("bloky", [])
    bloky = list((konfigurace or {}).get("bloky") or [])
    if not bloky:
        return vychozi_sablona(typ)
    znama = {b.get("id") for b in bloky}
    kotva: str | None = None  # poslední blok předlohy, který konfigurace zná
    for vb in vychozi:
        if vb["id"] in znama:
            kotva = vb["id"]
            continue
        kam = len(bloky)
        if kotva is not None:
            kam = next(
                (i + 1 for i, b in enumerate(bloky) if b.get("id") == kotva), len(bloky)
            )
        else:
            kam = 0
        bloky.insert(kam, copy.deepcopy(vb))
        znama.add(vb["id"])
        kotva = vb["id"]
    out = dict(konfigurace or {})
    out["bloky"] = bloky
    return out
