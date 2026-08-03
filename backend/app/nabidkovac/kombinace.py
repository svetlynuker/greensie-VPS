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

from . import ppa_tvar


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


def _prvni(*hodnoty: Any) -> Any:
    """První hodnota, která není None (nula je platná, na rozdíl od `or`)."""
    for h in hodnoty:
        if h is not None:
            return h
    return None


def _model_ps(ps: dict) -> str:
    """Který tarifní model peak shavingu se má číst – 2027, jakmile je
    spočítaný (podle něj počítá i nabídkovač), jinak 2026. Náklad, výnos
    i úspora MUSÍ pocházet z jednoho modelu, jinak by jejich rozdíl nesouhlasil."""
    return "2027" if _g(ps, "doporucena", "ekonomika_2027", "status") == "spocitano" else "2026"


def _uspora_ps_rok1(ps: dict) -> float | None:
    """Roční úspora peak shavingu na platbách za kapacitu (bez obchodu a bez
    provozních nákladů). Přednost má model 2027, jinak 2026."""
    if _model_ps(ps) == "2027":
        return _cislo(_g(ps, "doporucena", "ekonomika_2027", "rocni_uspora"))
    return _cislo(
        _prvni(
            _g(ps, "doporucena", "ekonomika_2026", "rocni_uspora"),
            _g(ps, "doporucena", "rocni_uspora_2026_kc"),
        )
    )


def _uspora_ppa_rok1(ppa: dict) -> float | None:
    roky = ppa_tvar.vysledek(ppa).get("roky") or []
    if isinstance(roky, list) and roky and isinstance(roky[0], dict):
        return _cislo(roky[0].get("uspora_klient_kc"))
    return None


def _oam_ps_rok1(ps: dict) -> float | None:
    """Provozní náklady baterie v 1. roce (servis, O&M). Nese je roční
    tabulka výpočtu – nedopočítávají se tu, aby se nemohly rozejít."""
    roky = _g(ps, "doporucena", "roky") or []
    if isinstance(roky, list) and roky and isinstance(roky[0], dict):
        return _cislo(roky[0].get("oam_kc"))
    return None


def rozpad_ps_rok1(ps: dict) -> dict:
    """Náklad a výnos zákazníka z baterie v 1. roce.

    - **výnos** = platba za kapacitu, která odpadne, plus výnos z obchodu
      s elektřinou (v režimu, kde baterie obchoduje),
    - **náklad** = platba za kapacitu po instalaci (včetně ztrát nabíjením)
      plus provoz a servis baterie,
    - **čistý přínos** = rozdíl obojího.

    Rozdíl je z definice přesně `cf_kc` prvního roku roční tabulky, takže
    dlaždice a tabulka pod nimi říkají totéž. Investice do baterie je
    jednorázová, proto stojí mimo tento roční rozpad.
    """
    dop = _g(ps, "doporucena") or {}
    model = _model_ps(ps)
    if model == "2027":
        ek = _g(dop, "ekonomika_2027") or {}
        # `novy_rocni_naklad` už ztráty nabíjením obsahuje (viz peak_shaving.py).
        vynos_kapacita = _cislo(ek.get("soucasny_rocni_naklad"))
        naklad_kapacita = _cislo(ek.get("novy_rocni_naklad"))
    else:
        ek = _g(dop, "ekonomika_2026") or {}
        vynos_kapacita = _cislo(ek.get("soucasny_naklad_celkem"))
        naklad_kapacita = _soucet(
            ek.get("novy_naklad_rezervace"), ek.get("naklad_ztrat_baterie")
        )

    zisk_obchod = _cislo(dop.get("zisk_spot_kc"))
    # Čistý peak shaving neobchoduje – nula by tvrdila, že obchod nic nenese.
    if (dop.get("rezim") or "peak_shaving") == "peak_shaving":
        zisk_obchod = None
    oam = _oam_ps_rok1(ps)

    vynos = _soucet(vynos_kapacita, zisk_obchod)
    naklad = _soucet(naklad_kapacita, oam)
    cisty = (vynos - naklad) if (vynos is not None and naklad is not None) else None

    return {
        "investice_kc": _cislo(dop.get("cena_celkem_kc")),
        "naklad_rok1_kc": naklad,
        "vynos_rok1_kc": vynos,
        "cisty_prinos_rok1_kc": cisty,
        # Dílčí položky, ať je v nabídce vidět, z čeho se náklad a výnos skládá.
        "naklad_kapacita_rok1_kc": naklad_kapacita,
        "provozni_naklad_rok1_kc": oam,
        "vynos_kapacita_rok1_kc": vynos_kapacita,
        "zisk_obchod_rok1_kc": zisk_obchod,
        "model": model,
    }


def rozpad_ppa_rok1(ppa: dict) -> dict:
    """Náklad a výnos zákazníka z elektrárny v 1. roce (viz `ppa_tvar`)."""
    return ppa_tvar.rozpad_rok1(ppa)


def spolecna_tabulka(ppa: dict, ps: dict) -> list[dict]:
    """Roční tabulka obou opatření vedle sebe + kumulativní součet.

    Roky se berou podle DELŠÍ řady (typicky PPA kontrakt): u peak shavingu se
    po skončení jeho řady doplní nula, protože baterie dál šetří – ale my
    nemáme čím to podložit, takže se radši nepočítá nic, než aby se čísla
    vymýšlela. Chybějící hodnota se v tabulce ukáže jako prázdná.

    U baterie se bere `cf_kc` = přínos PO odečtení provozu a servisu, ne
    `prinos_kc` před ním. Tabulka tak říká totéž co dlaždice „čistý přínos
    baterie"; dokud se četl `prinos_kc`, lišila se od nich o roční O&M.
    """
    ppa_roky = ppa_tvar.vysledek(ppa).get("roky") or []
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
    ps_uspory = _mapa(ps_roky, "cf_kc")
    if not ps_uspory:
        # Starší uložené výsledky `cf_kc` nemají – ať tabulka není prázdná.
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
    """Klíčová čísla kombinace pro zákazníka.

    Vedle úspor nese i rozpad na NÁKLAD a VÝNOS každé technologie zvlášť
    a jejich součet, aby šlo v nabídce ukázat, co která technologie stojí
    a co přináší. Napříč celým souhrnem platí jedno pravidlo:

        výnos − náklad = čistý přínos

    Roční položky se sčítají mezi sebou, investice zvlášť – jednorázová
    investice do baterie a roční platby nepatří do jednoho součtu.
    """
    r_ppa = rozpad_ppa_rok1(ppa)
    r_ps = rozpad_ps_rok1(ps)

    investice = r_ps.get("investice_kc")
    u_ppa = _uspora_ppa_rok1(ppa)
    u_ps = _uspora_ps_rok1(ps)
    tabulka = spolecna_tabulka(ppa, ps)
    kum = tabulka[-1]["uspora_kum_kc"] if tabulka else None

    cisty_ppa = r_ppa.get("cisty_prinos_rok1_kc")
    cisty_ps = r_ps.get("cisty_prinos_rok1_kc")
    cisty_celkem = _soucet(cisty_ppa, cisty_ps)
    naklad_celkem = _soucet(r_ppa.get("naklad_rok1_kc"), r_ps.get("naklad_rok1_kc"))
    vynos_celkem = _soucet(r_ppa.get("vynos_rok1_kc"), r_ps.get("vynos_rok1_kc"))

    return {
        # PPA je bez počáteční investice zákazníka, takže veškerá investice
        # kombinace je baterie. Nula by tady byla zavádějící, proto se PPA
        # v součtu vůbec neobjevuje.
        "investice_zakaznika_kc": investice,
        "uspora_ppa_rok1_kc": u_ppa,
        "uspora_ps_rok1_kc": u_ps,
        "uspora_rok1_celkem_kc": _soucet(u_ppa, u_ps),
        "uspora_kum_celkem_kc": kum,
        # --- rozpad na náklad a výnos: elektrárna ---
        # Investice do elektrárny je nula, ne chybějící údaj – to je podstata
        # PPA a v nabídce je to prodejní argument, takže se ukazuje.
        "ppa_investice_kc": r_ppa.get("investice_kc"),
        "ppa_naklad_rok1_kc": r_ppa.get("naklad_rok1_kc"),
        "ppa_vynos_rok1_kc": r_ppa.get("vynos_rok1_kc"),
        "ppa_cisty_prinos_rok1_kc": cisty_ppa,
        # --- rozpad na náklad a výnos: baterie ---
        "ps_investice_kc": investice,
        "ps_naklad_rok1_kc": r_ps.get("naklad_rok1_kc"),
        "ps_vynos_rok1_kc": r_ps.get("vynos_rok1_kc"),
        "ps_cisty_prinos_rok1_kc": cisty_ps,
        "ps_naklad_kapacita_rok1_kc": r_ps.get("naklad_kapacita_rok1_kc"),
        "ps_provozni_naklad_rok1_kc": r_ps.get("provozni_naklad_rok1_kc"),
        "ps_vynos_kapacita_rok1_kc": r_ps.get("vynos_kapacita_rok1_kc"),
        "ps_zisk_obchod_rok1_kc": r_ps.get("zisk_obchod_rok1_kc"),
        # --- dohromady ---
        "spolu_naklad_rok1_kc": naklad_celkem,
        "spolu_vynos_rok1_kc": vynos_celkem,
        "cisty_prinos_rok1_celkem_kc": cisty_celkem,
        # Návratnost se vztahuje POUZE k investici do baterie – vázat ji na
        # celkovou úsporu včetně PPA by tvrdilo, že se baterie zaplatí i z toho,
        # co ušetří elektrárna. To by nebyla pravda.
        "navratnost_baterie_roky": _cislo(
            _prvni(
                _g(ps, "doporucena", "navratnost_2027"),
                _g(ps, "doporucena", "navratnost_2027_konzerv"),
                _g(ps, "doporucena", "navratnost_roky"),
            )
        ),
        # Návratnost počítaná z přínosu OBOU opatření. Je to jiné číslo než
        # návratnost baterie a v nabídce se ukáže jen tehdy, když si ji tam
        # obchodník vědomě vloží – proto není ve výchozí předloze.
        "navratnost_kombinace_roky": (
            round(investice / cisty_celkem, 2)
            if investice and cisty_celkem and cisty_celkem > 0
            else None
        ),
        "delka_kontraktu_roky": _cislo(
            ppa_tvar.vysledek(ppa).get("delka_kontraktu_roky")
        ),
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
