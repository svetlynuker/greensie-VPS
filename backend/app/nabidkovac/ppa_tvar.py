"""Jednotný tvar výsledku PPA nabídky – jediné místo, kde se potkávají dvě verze.

Nabídky PPA se ukládají ve dvou tvarech:

- **v1** (`ppa_fve.py`): `popis_json["vysledek"]` = rovnou hotový výsledek,
- **v2** (`ppa_v2.py`): `popis_json["bez_baterie"|"s_baterii"]["po_delkach"]`
  = pole variant, ze kterých si obchodník na obrazovce vybírá.

Nabídková vrstva (katalog polí, tisk) i kombinace opatření čtou výsledek jen
přes tenhle modul, takže se o verzi nemusí starat a nemůže se stát, že by nová
verze výpočtu tiše vypnula čísla v nabídce. Přesně to se stalo mezi 30. 7. a
3. 8. 2026: po přechodu na v2 byla tištěná PPA nabídka prázdná (všech 12 polí
„—") a kombinace tvrdila, že elektrárna nešetří nic.

Výběr varianty je schválně TOTOŽNÝ s panelem v nabídkovači (`PpaPanel.jsx`):
varianta podle `vstup.s_baterii`, jinak první dostupná, a z ní první nabízená
délka kontraktu. Kdyby se pravidla lišila, nabídka by tiskla jiná čísla, než
jaká obchodník viděl na obrazovce, a nikdo by nepoznal proč.
"""

from typing import Any


def _g(d: Any, *cesta: str) -> Any:
    """Bezpečně projde vnořený dict; při chybějícím klíči vrátí None."""
    cur = d
    for k in cesta:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _num(x: Any) -> float | None:
    """Číslo, nebo None. Nula je platná hodnota, prázdno není nula."""
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _prvni(*hodnoty: Any) -> Any:
    for h in hodnoty:
        if h is not None:
            return h
    return None


def _kwh(mwh: Any) -> float | None:
    c = _num(mwh)
    return c * 1000.0 if c is not None else None


def zvolena_varianta(popis: dict) -> dict | None:
    """Varianta + délka kontraktu, které patří do nabídky (jen tvar v2).

    Veřejná, protože ji kromě tisku potřebuje i export do Excelu – oba výstupy
    vznikají jedním kliknutím a musely by jinak ukázat každý jinou variantu.
    """
    s_baterii = bool(_g(popis, "vstup", "s_baterii"))
    poradi = ("s_baterii", "bez_baterie") if s_baterii else ("bez_baterie", "s_baterii")
    for klic in poradi:
        blok = popis.get(klic)
        if not isinstance(blok, dict):
            continue
        delky = blok.get("po_delkach")
        if isinstance(delky, list) and delky and isinstance(delky[0], dict):
            # `kwp` je na bloku (společné pro všechny délky), ve variantě bývá taky.
            return {**delky[0], "kwp": _prvni(delky[0].get("kwp"), blok.get("kwp"))}
    return None


def _v2_na_jednotny(varianta: dict, vstup: dict) -> dict:
    """Přemapuje výsledek v2 na tvar v1, ve kterém ho čtou extraktory katalogu."""
    energie = varianta.get("energie") or {}

    roky: list[dict] = []
    for r in varianta.get("roky_klient") or []:
        if not isinstance(r, dict):
            continue
        roky.append(
            {
                "rok": r.get("rok"),
                "cena_ppa_kc_mwh": r.get("cena_ppa_kc_mwh"),
                # v1 mu říká „cena dodavatele", v2 „vyhnutelná cena" – je to
                # totéž číslo (co by zákazník zaplatil bez elektrárny).
                "cena_dodavatel_kc_mwh": r.get("cena_vyhnutelna_kc_mwh"),
                "samospotreba_kwh": _kwh(r.get("samospotreba_mwh")),
                "najem_baterie_kc": r.get("najem_baterie_kc"),
                "uspora_klient_kc": r.get("uspora_kc"),
                "uspora_klient_kum_kc": r.get("uspora_kumulativni_kc"),
            }
        )

    return {
        "kwp": varianta.get("kwp"),
        "delka_kontraktu_roky": varianta.get("delka_kontraktu_roky"),
        # Sklon a azimut jsou u v2 jen na vstupu – výsledek je nenese.
        "sklon_st": vstup.get("sklon_st"),
        "azimut_st": vstup.get("azimut_st"),
        "rocni_spotreba_kwh": _kwh(energie.get("spotreba_mwh")),
        "vyroba_rok1_kwh": _kwh(energie.get("vyroba_rok1_mwh")),
        "samospotreba_rok1_kwh": _kwh(energie.get("samospotreba_mwh")),
        "pokryti_spotreby_fve": energie.get("pokryti_spotreby_fve"),
        "vyhnutelna_cena_rok1_kc_mwh": varianta.get("cena_vyhnutelna_kc_mwh"),
        "souhrn_klient": {"uspora_kum_kc": varianta.get("uspora_kumulativni_kc")},
        # Navržená/zadaná baterie tak, jak ji nese varianta v2 (název produktu
        # z katalogu, kapacita, výkon, nákladová cena, nájem). v1 ji nemá, tam
        # zůstane None.
        "baterie": varianta.get("baterie"),
        "roky": roky,
        # Za kolik si zákazník elektrárnu odkoupí v roce t. Nese ji varianta
        # v2 (per délka kontraktu); v1 ji nepočítal, tam zůstane prázdná
        # a blok s tabulkou se v nabídce sám neukáže.
        "odkupni_tabulka": varianta.get("odkupni_tabulka") or [],
        "graf": varianta.get("graf"),
    }


def vysledek(popis_json: Any) -> dict:
    """Výsledek PPA v jednotném tvaru, ať je uložený v1 nebo v2.

    Nikdy nevyhazuje výjimku – u nespočítané nebo poškozené nabídky vrátí
    prázdný dict a pole nabídky zůstanou prázdná (v tisku „—").
    """
    if not isinstance(popis_json, dict):
        return {}
    stary = popis_json.get("vysledek")
    if isinstance(stary, dict):
        return stary
    varianta = zvolena_varianta(popis_json)
    if varianta is None:
        return {}
    return _v2_na_jednotny(varianta, popis_json.get("vstup") or {})


def rozpad_rok1(popis_json: Any) -> dict:
    """Náklad a výnos zákazníka z elektrárny v 1. roce.

    - **výnos** = co by za tutéž elektřinu zaplatil dodavateli (dnešní
      vyhnutelná cena × odebraná energie),
    - **náklad** = co za ni zaplatí nám (cena PPA × odebraná energie) plus
      nájem baterie, pokud je součástí řešení,
    - **čistý přínos** = úspora, kterou počítá sám výpočet.

    Náklad se počítá přímo z ceny PPA – to je částka, kterou zákazník podle
    smlouvy opravdu zaplatí, takže musí sedět na korunu. Výnos se pak dopočítá
    jako náklad plus úspora z výpočtu; kdyby se počítal také z ceny (odebraná
    energie × dnešní cena), lišil by se o jednotky korun kvůli zaokrouhlení
    uložených hodnot a rozdíl obou dlaždic by nesouhlasil s úsporou.

    Investice zákazníka je u PPA nulová – to není chybějící údaj, ale podstata
    nabídky, proto se vrací 0.
    """
    roky = vysledek(popis_json).get("roky")
    r = roky[0] if isinstance(roky, list) and roky and isinstance(roky[0], dict) else {}

    samospotreba_kwh = _num(r.get("samospotreba_kwh"))
    cena_ppa = _num(r.get("cena_ppa_kc_mwh"))
    cena_dodavatel = _num(r.get("cena_dodavatel_kc_mwh"))
    najem = _num(r.get("najem_baterie_kc")) or 0.0
    cisty = _num(r.get("uspora_klient_kc"))

    mwh = samospotreba_kwh / 1000.0 if samospotreba_kwh is not None else None
    naklad = mwh * cena_ppa + najem if (mwh is not None and cena_ppa is not None) else None
    if naklad is not None and cisty is not None:
        vynos = naklad + cisty
    elif mwh is not None and cena_dodavatel is not None:
        vynos = mwh * cena_dodavatel
    else:
        vynos = None

    return {
        "investice_kc": 0.0,
        "naklad_rok1_kc": naklad,
        "vynos_rok1_kc": vynos,
        "cisty_prinos_rok1_kc": cisty,
    }
