# -*- coding: utf-8 -*-
"""Kontrakt mezi manažerským nastavením PPA v adminu a backendem.

Nastavení PPA je seznam klíčů v `frontend/src/pages/NabidkovacKatalog.jsx`
(`PPA_POLE`), který se ukládá do `vypoctova_nastaveni.parametry`, a backend je
čte přes `_ppa_param(nastaveni, "klic", default)` v `routes.py`.

Tyhle dva seznamy se mohou tiše rozejít a **nic nespadne** – vedení uloží
hodnotu, kterou nikdo nečte, a výpočet dál jede na defaultu. Tenhle test to
hlídá: každý klíč nabídnutý v adminu musí backend opravdu číst.
"""

import re
from pathlib import Path

KOREN = Path(__file__).resolve().parents[2]
ROUTES = KOREN / "backend" / "app" / "nabidkovac" / "routes.py"
PPA_V2 = KOREN / "backend" / "app" / "nabidkovac" / "ppa_v2.py"
KATALOG = KOREN / "frontend" / "src" / "pages" / "NabidkovacKatalog.jsx"


def klice_ktere_backend_cte() -> set[str]:
    """Klíče čtené z manažerského nastavení.

    Ekonomické parametry skládá `ppa_v2.parametry_z_nastaveni` (sdílí ji výpočet
    i export do Excelu), zbytek (měrný výnos, cíl samospotřeby…) čte routes.py
    přímo. Prohledávají se obě místa – jinak by se test rozbil při každém
    přesunu, aniž by se kontrakt s adminem změnil.
    """
    klice: set[str] = set()
    # `_ppa_param(nastaveni, "klic"` v routes.py – i přes zalomení řádku
    klice |= set(
        re.findall(r'_ppa_param\(\s*nastaveni,\s*"([^"]+)"', ROUTES.read_text(encoding="utf-8"), re.S)
    )
    # `_param(parametry, "klic"` v ppa_v2.py
    klice |= set(
        re.findall(r'_param\(\s*parametry,\s*"([^"]+)"', PPA_V2.read_text(encoding="utf-8"), re.S)
    )
    return klice


def klice_nabizene_v_adminu() -> set[str]:
    """Klíče ze seznamu `PPA_POLE` v admin stránce."""
    zdroj = KATALOG.read_text(encoding="utf-8")
    blok = re.search(r"const PPA_POLE = \[(.*?)\n\];", zdroj, re.S)
    assert blok, "V NabidkovacKatalog.jsx nejde najít seznam PPA_POLE"
    return set(re.findall(r'klic:\s*"([^"]+)"', blok.group(1)))


def test_admin_nenabizi_klic_ktery_nikdo_necte():
    """Nastavení, které se nikde nečte, je past – vedení ho uloží a nic se nestane."""
    admin = klice_nabizene_v_adminu()
    backend = klice_ktere_backend_cte()
    mrtve = sorted(admin - backend)
    assert not mrtve, (
        "Admin nabízí PPA nastavení, které backend nečte: "
        + ", ".join(mrtve)
        + ". Buď je začni čítat v routes.py, nebo je z PPA_POLE smaž."
    )


def test_admin_nabizi_klicove_parametry():
    """Co si Dan vyžádal mít editovatelné, musí v adminu být (DSCR, IRR, cena za export)."""
    admin = klice_nabizene_v_adminu()
    for klic in ("ppa_dscr_min", "ppa_irr_cil", "ppa_cena_exportu_kc_mwh"):
        assert klic in admin, f"V nastavení chybí {klic}"


def test_backend_cte_vsechny_ekonomicke_parametry():
    """Každé pole `ParametryEkonomiky` má jít nastavit, ať nezůstane zadrátované.

    Výjimky jsou vědomé: `indexovat_export` je bool (JSONB drží čísla) a
    `diskontni_sazba` se u v2 nepoužívá pro rozhodování (jen informativní NPV).
    """
    from app.nabidkovac import ppa_v2

    vyjimky = {"indexovat_export", "diskontni_sazba"}
    backend = klice_ktere_backend_cte()
    chybi = [
        pole
        for pole in ppa_v2.ParametryEkonomiky.__dataclass_fields__
        if pole not in vyjimky and f"ppa_{pole}" not in backend
    ]
    # `odkup_poplatek_predcasne_splaceni` je v nastavení zkrácené na
    # `ppa_odkup_poplatek_predcasne`, ať se klíč vejde do UI.
    chybi = [p for p in chybi if p != "odkup_poplatek_predcasne_splaceni"]
    assert not chybi, "Tyhle ekonomické parametry nejde nastavit: " + ", ".join(chybi)


# ============================================================ kontrakt s panelem
def test_vysledek_ma_vsechna_pole_ktera_panel_cte():
    """Panel `PpaPanel.jsx` čte konkrétní cesty ve `popis_json`.

    Když se v `ppa_v2` pole přejmenuje, backend nespadne – v UI se jen všude
    objeví „—“, což se snadno přehlédne. Tenhle test to zachytí.
    """
    from datetime import datetime, timedelta

    from app.nabidkovac import ppa_v2 as ppa

    casy, spotreba = [], []
    t0 = datetime(2026, 1, 1)
    for i in range(2880):  # 30 dní po 15 min
        c = t0 + timedelta(minutes=15 * i)
        casy.append(c)
        spotreba.append((30.0 if 7 <= c.hour < 18 else 5.0) * 0.25)

    v = ppa.spocti_ppa2(
        ppa.VstupPPA2(
            casy=casy,
            spotreba_kwh=spotreba,
            cena_silova_kc_mwh=3500.0,
            s_baterii=True,
            baterie=ppa.Baterie(200.0, 100.0, nakladova_cena_kc=800_000.0),
        )
    )

    for klic in ("dscr_min", "irr_cil", "cena_exportu_kc_mwh", "cena_vyhnutelna_kc_mwh",
                 "cil_mira_samospotreby", "cena_silova_kc_mwh"):
        assert klic in v["vstup"], f"vstup.{klic}"

    for varianta in ("bez_baterie", "s_baterii"):
        blok = v[varianta]
        assert blok is not None, varianta
        for klic in ("kwp", "omezeno_max_kwp", "kwp_bez_stropu", "po_delkach"):
            assert klic in blok, f"{varianta}.{klic}"

        for x in blok["po_delkach"]:
            for klic in ("delka_kontraktu_roky", "cena_ppa_kc_kwh", "cena_ppa_kc_mwh",
                         "cena_vyhnutelna_kc_mwh", "cena_exportu_kc_mwh", "sleva_zakaznikovi",
                         "cena_limituje", "uspora_kumulativni_kc", "roky_investor",
                         "roky_klient", "odkupni_tabulka", "graf", "energie",
                         "financovani", "vysledek_investora"):
                assert klic in x, f"{varianta}.po_delkach[].{klic}"

            for klic in ("spotreba_mwh", "vyroba_rok1_mwh", "samospotreba_mwh", "export_mwh",
                         "orez_mwh", "dokup_mwh", "mira_samospotreby", "pokryti_spotreby_fve"):
                assert klic in x["energie"], f"energie.{klic}"
            for klic in ("nakladova_cena_kc", "capex_kc", "provize_kc", "zisk_greensie_kc",
                         "vlastni_kapital_kc", "uver_kc", "splatka_mesicni_kc"):
                assert klic in x["financovani"], f"financovani.{klic}"
            for klic in ("dscr_min", "irr"):
                assert klic in x["vysledek_investora"], f"vysledek_investora.{klic}"
            for klic in ("rok", "vyroba_mwh", "samospotreba_mwh", "cena_ppa_kc_mwh",
                         "prodej_zakaznik_kc", "prodej_sdileni_kc", "zdroje_kc",
                         "splatka_kc", "dscr", "zisk_po_splatkach_kc"):
                assert klic in x["roky_investor"][0], f"roky_investor[].{klic}"
            for klic in ("rok", "cena_vyhnutelna_kc_mwh", "cena_ppa_kc_mwh", "samospotreba_mwh",
                         "najem_baterie_kc", "uspora_kc", "uspora_kumulativni_kc"):
                assert klic in x["roky_klient"][0], f"roky_klient[].{klic}"
            for klic in ("rok", "odkupni_cena_kc", "zustatek_uveru_kc",
                         "poplatek_predcasne_splaceni_kc", "zisk_spv_kc"):
                assert klic in x["odkupni_tabulka"][0], f"odkupni_tabulka[].{klic}"
            for klic in ("mesice", "spotreba_kwh", "vyroba_kwh", "samospotreba_kwh",
                         "export_kwh", "orez_kwh", "dokup_kwh"):
                assert klic in x["graf"], f"graf.{klic}"

    assert v["s_baterii"]["po_delkach"][0]["baterie"]["najem_kc_mesic"] > 0
