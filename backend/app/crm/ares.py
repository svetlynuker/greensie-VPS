"""Doplnění firmy z ARESu podle IČO (veřejný registr MF ČR).

Proč: OZ zakládá leada z vizitky nebo z telefonu. Opisovat název, adresu a DIČ
ručně je zdroj překlepů, a překlep v názvu firmy se pak objeví na nabídce
u zákazníka. IČO je osm číslic, které si člověk přečte správně; zbytek dotáhne
registr.

Endpoint je veřejný a bez klíče. Selhání (nedostupnost, neznámé IČO) NIKDY
nesmí zablokovat založení zákazníka – vrací se chyba a uživatel vyplní ručně.
"""

import re

import requests

ARES_URL = "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}"
TIMEOUT_S = 8


class AresChyba(Exception):
    """Nepodařilo se dotáhnout data – volající to hlásí jako varování, ne pád."""


def normalizuj_ico(ico: str) -> str:
    """Vytáhne z uživatelského vstupu osm číslic (lidé píší „CZ 123 456 78")."""
    cisla = re.sub(r"\D", "", str(ico or ""))
    return cisla.zfill(8) if 0 < len(cisla) <= 8 else cisla


def je_platne_ico(ico: str) -> bool:
    """Kontrolní součet IČO (modulo 11) – odchytí překlep bez dotazu do ARESu."""
    ico = normalizuj_ico(ico)
    if len(ico) != 8 or not ico.isdigit():
        return False
    soucet = sum(int(ico[i]) * (8 - i) for i in range(7))
    zbytek = soucet % 11
    if zbytek == 0:
        kontrolni = 1
    elif zbytek == 1:
        kontrolni = 0
    else:
        kontrolni = 11 - zbytek
    return kontrolni == int(ico[7])


def _adresa(sidlo: dict) -> dict:
    """Rozpadne sídlo z ARESu na pole, která drží `Zakaznik`.

    ARES posílá i složenou `textovaAdresa`; skládáme ale z dílů, protože
    appka potřebuje město a PSČ zvlášť (adresa jde do nabídky i do geokódování).
    """
    ulice = (sidlo.get("nazevUlice") or "").strip()
    cislo_domovni = sidlo.get("cisloDomovni")
    cislo_orientacni = sidlo.get("cisloOrientacni")
    cislo = str(cislo_domovni) if cislo_domovni else ""
    if cislo_orientacni:
        cislo = f"{cislo}/{cislo_orientacni}" if cislo else str(cislo_orientacni)
    # Obce bez uličního systému mají jen číslo domovní a název obce.
    radek = " ".join(x for x in [ulice, cislo] if x).strip()
    if not radek:
        radek = (sidlo.get("nazevCastiObce") or "").strip()
    return {
        "adresa_ulice": radek,
        "adresa_mesto": (sidlo.get("nazevObce") or "").strip(),
        "adresa_psc": str(sidlo.get("psc") or "").strip(),
        "adresa_stat": (sidlo.get("nazevStatu") or "Česko").strip(),
    }


def najdi_podle_ico(ico: str) -> dict:
    """Vrátí {nazev, ico, dic, adresa_*} z ARESu, nebo vyhodí `AresChyba`."""
    ico_n = normalizuj_ico(ico)
    if not je_platne_ico(ico_n):
        raise AresChyba("IČO nemá platný kontrolní součet – zkontroluj číslice.")

    try:
        odpoved = requests.get(ARES_URL.format(ico=ico_n), timeout=TIMEOUT_S)
    except requests.RequestException as e:
        raise AresChyba(f"ARES je nedostupný ({e.__class__.__name__}). Vyplň údaje ručně.") from e

    if odpoved.status_code == 404:
        raise AresChyba(f"IČO {ico_n} v ARESu není.")
    if odpoved.status_code != 200:
        raise AresChyba(f"ARES odpověděl {odpoved.status_code}. Vyplň údaje ručně.")

    try:
        data = odpoved.json()
    except ValueError as e:
        raise AresChyba("ARES vrátil nečitelnou odpověď.") from e

    out = {
        "nazev": (data.get("obchodniJmeno") or "").strip(),
        "ico": ico_n,
        # DIČ ARES posílá jen u plátců DPH; prázdné není chyba.
        "dic": (data.get("dic") or "").strip(),
    }
    out.update(_adresa(data.get("sidlo") or {}))
    return out
