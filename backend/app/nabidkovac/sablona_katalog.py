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
    """

    def __init__(self, klic: str, nazev: str, format: str, extraktor: Callable[[dict], Any]):
        self.klic = klic
        self.nazev = nazev
        self.format = format
        self.extraktor = extraktor

    def slovnik(self) -> dict:
        """Podoba pro frontend (bez extraktoru)."""
        return {"klic": self.klic, "nazev": self.nazev, "format": self.format}


# ---- PPA: katalog zákaznických polí -----------------------------------------
_POLE_PPA: list[Pole] = [
    Pole("kwp", "Velikost elektrárny", "vykon_kwp", lambda p: _g(p, "vysledek", "kwp")),
    Pole("rocni_spotreba_kwh", "Vaše roční spotřeba", "energie_mwh",
         lambda p: _g(p, "vysledek", "rocni_spotreba_kwh")),
    Pole("vyroba_rok1_kwh", "Roční výroba elektrárny", "energie_mwh",
         lambda p: _g(p, "vysledek", "vyroba_rok1_kwh")),
    Pole("samospotreba_rok1_kwh", "Přímo spotřebováno z elektrárny", "energie_mwh",
         lambda p: _g(p, "vysledek", "samospotreba_rok1_kwh")),
    Pole("pokryti_spotreby_fve", "Pokrytí spotřeby z elektrárny", "procento",
         lambda p: _g(p, "vysledek", "pokryti_spotreby_fve")),
    Pole("delka_kontraktu_roky", "Doba kontraktu", "roky_cele",
         lambda p: _g(p, "vysledek", "delka_kontraktu_roky")),
    Pole("cena_ppa_rok1_kc_mwh", "Cena elektřiny z elektrárny (1. rok)", "penize_mwh",
         lambda p: _prvni_rok(p, "cena_ppa_kc_mwh")),
    Pole("vyhnutelna_cena_rok1_kc_mwh", "Vaše dnešní cena elektřiny", "penize_mwh",
         lambda p: _g(p, "vysledek", "vyhnutelna_cena_rok1_kc_mwh")),
    Pole("uspora_rok1_kc", "Úspora v 1. roce", "penize",
         lambda p: _prvni_rok(p, "uspora_klient_kc")),
    Pole("uspora_kum_kc", "Celková úspora za dobu kontraktu", "penize",
         lambda p: _g(p, "vysledek", "souhrn_klient", "uspora_kum_kc")),
    Pole("sklon_st", "Sklon panelů", "stupne", lambda p: _g(p, "vysledek", "sklon_st")),
    Pole("azimut_st", "Orientace panelů (azimut)", "stupne",
         lambda p: _g(p, "vysledek", "azimut_st")),
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


_POLE_PS: list[Pole] = [
    Pole("nazev", "Navržená baterie", "text", lambda p: _dop(p, "nazev")),
    Pole("pocet_kusu", "Počet kusů", "pocet", lambda p: _dop(p, "pocet_kusu")),
    Pole("celkovy_vykon_kw", "Výkon baterie", "vykon_kw", lambda p: _dop(p, "celkovy_vykon_kw")),
    Pole("celkova_kapacita_kwh", "Kapacita baterie", "kapacita_kwh",
         lambda p: _dop(p, "celkova_kapacita_kwh")),
    Pole("cena_celkem_kc", "Investice do baterie", "penize", lambda p: _dop(p, "cena_celkem_kc")),
    Pole("rezervovana_kapacita_kw", "Současná rezervovaná kapacita", "vykon_kw",
         lambda p: _g(p, "vstup", "rezervovana_kapacita_kw")),
    Pole("nova_rezervovana_kapacita_kw", "Nová rezervovaná kapacita", "vykon_kw",
         lambda p: _dop(p, "nova_rezervovana_kapacita_kw")),
    Pole("strop_kw", "Špičku snížíme na", "vykon_kw", lambda p: _dop(p, "strop_kw")),
    Pole("soucasny_naklad_celkem", "Dnešní roční náklad za rezervaci", "penize",
         lambda p: _dop(p, "ekonomika_2026", "soucasny_naklad_celkem")),
    Pole("rocni_uspora_2026_kc", "Roční úspora", "penize",
         lambda p: _dop(p, "rocni_uspora_2026_kc")),
    Pole("navratnost_roky", "Návratnost investice", "roky",
         lambda p: _dop(p, "navratnost_roky")),
]

# Sloupce roční tabulky peak shavingu (jen zákaznické).
_TABULKA_PS = [
    {"klic": "rok", "nazev": "Rok", "format": "roky_cele"},
    {"klic": "prinos_kc", "nazev": "Úspora v roce", "format": "penize"},
    {"klic": "cf_kum_kc", "nazev": "Kumulativně vč. investice", "format": "penize"},
]


# ---- Rejstřík podle typu řešení ---------------------------------------------
_POLE = {"ppa": _POLE_PPA, "peak_shaving": _POLE_PS}
_TABULKA = {"ppa": _TABULKA_PPA, "peak_shaving": _TABULKA_PS}

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
    else:
        radky_zdroj = _dop(popis, "roky") or []
    radky = []
    if isinstance(radky_zdroj, list):
        for r in radky_zdroj:
            if not isinstance(r, dict):
                continue
            radky.append([_fmt(r.get(s["klic"]), s["format"]) for s in sloupce])
    return {"sloupce": sloupce, "radky": radky}


def graf_pro_typ(typ: str, popis_json: dict | None) -> dict | None:
    """Surová data grafu pro daný typ (PPA výroba/spotřeba, PS měsíční maxima).
    Frontend podle `typ_reseni` vybere správnou grafovou komponentu."""
    popis = popis_json or {}
    if typ == "ppa":
        return _g(popis, "vysledek", "graf")
    # peak shaving: graf doporučené varianty, fallback na graf na nejvyšší úrovni
    return _dop(popis, "graf") or _g(popis, "graf")


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
             "nadpis": "Vaše úspora",
             "pole": ["soucasny_naklad_celkem", "rocni_uspora_2026_kc",
                      "navratnost_roky"]},
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

DRUHY_BLOKU = ("hlavicka", "text", "udaje", "graf", "tabulka")


def vychozi_sablona(typ: str) -> dict:
    """Vrátí kopii výchozí předlohy pro daný typ (nová nabídka startuje odtud)."""
    import copy

    return copy.deepcopy(VYCHOZI_SABLONA.get(typ, {"bloky": []}))
