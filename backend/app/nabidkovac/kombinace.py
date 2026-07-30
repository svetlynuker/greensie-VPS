"""Kombinace opatření: spojení hotové PPA a peak shaving nabídky do jedné.

Modul NIC NEPOČÍTÁ. Bere dva už spočítané výsledky a skládá z nich třetí pohled
pro zákazníka, který chce obojí naráz. Proto se tu nenajde žádný sizing ani
ekonomika – jen sečtení a společná roční tabulka.

VĚCNÁ VÝHRADA, KTEROU JE POTŘEBA ZNÁT (a která je vidět i v nabídce):
oba výpočty běžely nad *původním* profilem spotřeby. FVE z PPA přes den sráží
odběr ze sítě, takže po její instalaci budou reálné špičky nižší a baterie
navržená nad původním profilem může být předimenzovaná. Úspory se nesčítají
dvakrát za totéž – PPA šetří na ceně energie (Kč/MWh), peak shaving na
rezervované kapacitě (Kč/kW) – ale dimenzování baterie by přesně vzato mělo
vycházet z profilu po odečtení výroby FVE. Přepočet by byl nový výpočet, což
tento modul záměrně nedělá.

Snapshot vs. živé čtení: spojení se ukládá jako `NavrhovaneReseni` typu
`kombinace`, protože celá výstupní vrstva (editor, tisk) čte poslední řešení
nabídky. Když se zdrojová nabídka přepočítá, kombinace se NEAKTUALIZUJE sama –
je na obchodníkovi ji spojit znovu (tlačítko „Aktualizovat ze zdrojů"). Tím je
zároveň dohledatelné, s jakými čísly nabídka odešla zákazníkovi.
"""

from datetime import datetime
from typing import Any


def _g(d: Any, *cesta: str) -> Any:
    """Bezpečné čtení zanořeného klíče."""
    x = d
    for k in cesta:
        if not isinstance(x, dict):
            return None
        x = x.get(k)
    return x


def _cislo(x: Any) -> float | None:
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _soucet(*hodnoty: Any) -> float | None:
    """Součet, který přeskočí nevyplněné. Když není ani jedna hodnota, vrátí
    None – nula by tvrdila, že úspora je nulová, což není totéž jako „nevíme"."""
    cisla = [c for c in (_cislo(h) for h in hodnoty) if c is not None]
    return sum(cisla) if cisla else None


def _uspora_ps_rok1(ps: dict) -> float | None:
    """Roční úspora peak shavingu. Přednost má model 2027, protože podle něj
    nabídkovač počítá, jakmile jsou sazby k dispozici; jinak 2026."""
    return _cislo(
        _g(ps, "doporucena", "ekonomika_2027", "rocni_uspora_bez_aku")
        or _g(ps, "doporucena", "ekonomika_2027", "rocni_uspora")
        or _g(ps, "doporucena", "rocni_uspora_2026_kc")
    )


def _uspora_ppa_rok1(ppa: dict) -> float | None:
    roky = _g(ppa, "vysledek", "roky") or []
    if isinstance(roky, list) and roky and isinstance(roky[0], dict):
        return _cislo(roky[0].get("uspora_klient_kc"))
    return None


def spolecna_tabulka(ppa: dict, ps: dict) -> list[dict]:
    """Roční tabulka obou opatření vedle sebe + kumulativní součet.

    Roky se berou podle DELŠÍ řady (typicky PPA kontrakt): u peak shavingu se
    po skončení jeho řady doplní nula, protože baterie dál šetří – ale my
    nemáme čím to podložit, takže se radši nepočítá nic, než aby se čísla
    vymýšlela. Chybějící hodnota se v tabulce ukáže jako prázdná.
    """
    ppa_roky = _g(ppa, "vysledek", "roky") or []
    ps_roky = _g(ps, "doporucena", "roky") or []

    def _mapa(radky: list, klic: str) -> dict[int, float]:
        out: dict[int, float] = {}
        for r in radky if isinstance(radky, list) else []:
            if not isinstance(r, dict):
                continue
            rok = r.get("rok")
            hodnota = _cislo(r.get(klic))
            if rok is not None and hodnota is not None:
                try:
                    out[int(rok)] = hodnota
                except (TypeError, ValueError):
                    continue
        return out

    ppa_uspory = _mapa(ppa_roky, "uspora_klient_kc")
    ps_uspory = _mapa(ps_roky, "prinos_kc")
    vsechny_roky = sorted(set(ppa_uspory) | set(ps_uspory))

    tabulka: list[dict] = []
    kumulativ = 0.0
    for rok in vsechny_roky:
        u_ppa = ppa_uspory.get(rok)
        u_ps = ps_uspory.get(rok)
        celkem = _soucet(u_ppa, u_ps)
        if celkem is not None:
            kumulativ += celkem
        tabulka.append(
            {
                "rok": rok,
                "uspora_ppa_kc": u_ppa,
                "uspora_ps_kc": u_ps,
                "uspora_celkem_kc": celkem,
                "uspora_kum_kc": kumulativ if celkem is not None else None,
            }
        )
    return tabulka


def souhrn(ppa: dict, ps: dict) -> dict:
    """Klíčová čísla kombinace pro zákazníka."""
    investice = _cislo(_g(ps, "doporucena", "cena_celkem_kc"))
    u_ppa = _uspora_ppa_rok1(ppa)
    u_ps = _uspora_ps_rok1(ps)
    tabulka = spolecna_tabulka(ppa, ps)
    kum = tabulka[-1]["uspora_kum_kc"] if tabulka else None

    return {
        # PPA je bez počáteční investice zákazníka, takže veškerá investice
        # kombinace je baterie. Nula by tady byla zavádějící, proto se PPA
        # v součtu vůbec neobjevuje.
        "investice_zakaznika_kc": investice,
        "uspora_ppa_rok1_kc": u_ppa,
        "uspora_ps_rok1_kc": u_ps,
        "uspora_rok1_celkem_kc": _soucet(u_ppa, u_ps),
        "uspora_kum_celkem_kc": kum,
        # Návratnost se vztahuje POUZE k investici do baterie – vázat ji na
        # celkovou úsporu včetně PPA by tvrdilo, že se baterie zaplatí i z toho,
        # co ušetří elektrárna. To by nebyla pravda.
        "navratnost_baterie_roky": _cislo(
            _g(ps, "doporucena", "navratnost_2027")
            or _g(ps, "doporucena", "navratnost_2027_konzerv")
            or _g(ps, "doporucena", "navratnost_roky")
        ),
        "delka_kontraktu_roky": _cislo(_g(ppa, "vysledek", "delka_kontraktu_roky")),
    }


def slouceny_popis(
    ppa_popis: dict,
    ps_popis: dict,
    ppa_nabidka_id: int,
    ps_nabidka_id: int,
    ppa_cislo: str = "",
    ps_cislo: str = "",
) -> dict:
    """Složí `popis_json` řešení typu `kombinace`.

    Struktura schválně obsahuje CELÉ zdrojové výsledky (`ppa`, `peak_shaving`):
    katalog polí kombinace z nich čte stejnými cestami jako u samostatných
    nabídek, takže se nemusí duplikovat extraktory. `zdroje` drží, z čeho
    kombinace vznikla a kdy – aby šlo dohledat, s jakými čísly nabídka odešla.
    """
    return {
        "ppa": ppa_popis or {},
        "peak_shaving": ps_popis or {},
        "souhrn": souhrn(ppa_popis or {}, ps_popis or {}),
        "roky": spolecna_tabulka(ppa_popis or {}, ps_popis or {}),
        "zdroje": {
            "ppa_nabidka_id": ppa_nabidka_id,
            "ppa_cislo": ppa_cislo,
            "ps_nabidka_id": ps_nabidka_id,
            "ps_cislo": ps_cislo,
            "spojeno_at": datetime.now().isoformat(),
        },
        # Text, který se ukáže obchodníkovi i v nabídce – viz výhrada v docstringu.
        "upozorneni": (
            "Obě opatření jsou spočítaná nad původním profilem spotřeby. "
            "Fotovoltaika přes den snižuje odběr ze sítě, takže skutečné špičky "
            "po její instalaci mohou být nižší a baterie může být navržená "
            "s rezervou. Úspory se nesčítají dvakrát za totéž (elektrárna šetří "
            "na ceně energie, baterie na rezervované kapacitě)."
        ),
    }
