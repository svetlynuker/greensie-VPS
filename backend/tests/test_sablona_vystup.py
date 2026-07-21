# -*- coding: utf-8 -*-
"""Testy katalogu nabídkové šablony (`app/nabidkovac/sablona_katalog.py`).

Modul je bez závislosti na DB/FastAPI – testuje se přímo nad ukázkovými
`popis_json`. Klíčová vlastnost k ověření: do nabídky se dostanou POUZE
zákaznická data (whitelist), interní čísla nikdy.
"""

import pytest

from app.nabidkovac import sablona_katalog as sk


# ---- ukázkové popis_json (výřez reálné struktury z routes.py) ----
PPA = {
    "typ_reseni": "ppa",
    "vysledek": {
        "kwp": 142.4,
        "rocni_spotreba_kwh": 240000.0,
        "vyroba_rok1_kwh": 150000.0,
        "samospotreba_rok1_kwh": 120000.0,
        "pokryti_spotreby_fve": 0.63,
        "delka_kontraktu_roky": 15,
        "vyhnutelna_cena_rok1_kc_mwh": 3200.0,
        "souhrn_klient": {"uspora_kum_kc": 1234567.0},
        # interní – NESMÍ se dostat do nabídky:
        "capex_kc": 3800000.0,
        "npv_kc": 900000.0,
        "irr": 0.11,
        "navratnost_roky": 8.5,
        "roky": [
            {"rok": 1, "cena_ppa_kc_mwh": 2100.0, "cena_dodavatel_kc_mwh": 3200.0,
             "uspora_klient_kc": 98000.0, "uspora_klient_kum_kc": 98000.0,
             "vynos_ppa_kc": 250000.0},
            {"rok": 2, "cena_ppa_kc_mwh": 2163.0, "cena_dodavatel_kc_mwh": 3296.0,
             "uspora_klient_kc": 101000.0, "uspora_klient_kum_kc": 199000.0,
             "vynos_ppa_kc": 255000.0},
        ],
        "graf": {"mesice": [1, 2], "spotreba_kwh": [1, 2], "vyroba_kwh": [1, 2]},
    },
}

PS = {
    "typ_reseni": "peak_shaving",
    "vstup": {"rezervovana_kapacita_kw": 250.0},
    "doporucena": {
        "nazev": "BESS 100/215",
        "pocet_kusu": 2,
        "celkovy_vykon_kw": 200.0,
        "celkova_kapacita_kwh": 430.0,
        "cena_celkem_kc": 5400000.0,
        "strop_kw": 180.0,
        "nova_rezervovana_kapacita_kw": 190.0,
        "rocni_uspora_2026_kc": 620000.0,
        "navratnost_roky": 8.7,
        "ekonomika_2026": {
            "soucasny_naklad_celkem": 900000.0,
            # interní:
            "prinos_baterie": 400000.0,
            "naklad_ztrat_baterie": 30000.0,
        },
        # interní:
        "npv_kc": 1200000.0,
        "irr": 0.09,
        "roky": [
            {"rok": 1, "prinos_kc": 620000.0, "cf_kum_kc": -4780000.0, "oam_kc": 20000.0},
            {"rok": 2, "prinos_kc": 615000.0, "cf_kum_kc": -4165000.0, "oam_kc": 20000.0},
        ],
        "graf": {"mesice": [1, 2], "bez_baterie_kw": [240, 250], "s_baterii_2026_kw": [180, 180]},
    },
}


class TestKatalogNeobsahujeInterni:
    """POJISTKA: katalog nabízí jen zákaznická pole, interní klíče v něm nejsou."""

    INTERNI = {"capex_kc", "npv_kc", "irr", "navratnost_investor", "koeficient_zisku",
               "prinos_baterie", "naklad_ztrat_baterie", "diskontni_sazba", "oam_kc"}

    def test_ppa_katalog_bez_internich(self):
        klice = sk.platne_klice("ppa")
        assert not (klice & self.INTERNI)
        assert "kwp" in klice and "uspora_kum_kc" in klice

    def test_ps_katalog_bez_internich(self):
        klice = sk.platne_klice("peak_shaving")
        assert not (klice & self.INTERNI)
        assert "rocni_uspora_2026_kc" in klice and "celkova_kapacita_kwh" in klice

    def test_ppa_navratnost_investora_neni_zakaznicka(self):
        # Návratnost investora u PPA je interní – nesmí být v katalogu.
        assert "navratnost_roky" not in sk.platne_klice("ppa")

    def test_resolver_nikdy_nevrati_interni_klic(self):
        h = sk.resolvni_hodnoty("ppa", PPA)
        assert "capex_kc" not in h and "npv_kc" not in h and "irr" not in h


class TestResolverHodnot:
    def test_ppa_formatovani(self):
        h = sk.resolvni_hodnoty("ppa", PPA)
        assert h["kwp"]["hodnota_text"] == "142,4 kWp"
        assert h["pokryti_spotreby_fve"]["hodnota_text"] == "63 %"
        assert h["vyroba_rok1_kwh"]["hodnota_text"] == "150,0 MWh"
        assert h["uspora_kum_kc"]["hodnota_text"] == "1 234 567 Kč"
        assert h["delka_kontraktu_roky"]["hodnota_text"] == "15 let"
        # cena PPA rok 1 se bere z prvního roku
        assert h["cena_ppa_rok1_kc_mwh"]["hodnota_text"] == "2 100 Kč/MWh"
        assert h["uspora_rok1_kc"]["hodnota_text"] == "98 000 Kč"

    def test_ps_formatovani(self):
        h = sk.resolvni_hodnoty("peak_shaving", PS)
        assert h["nazev"]["hodnota_text"] == "BESS 100/215"
        assert h["pocet_kusu"]["hodnota_text"] == "2 ks"
        assert h["celkovy_vykon_kw"]["hodnota_text"] == "200 kW"
        assert h["celkova_kapacita_kwh"]["hodnota_text"] == "430,0 kWh"
        assert h["rezervovana_kapacita_kw"]["hodnota_text"] == "250 kW"
        assert h["nova_rezervovana_kapacita_kw"]["hodnota_text"] == "190 kW"
        assert h["rocni_uspora_2026_kc"]["hodnota_text"] == "620 000 Kč"

    def test_chybejici_hodnota_je_pomlcka(self):
        h = sk.resolvni_hodnoty("ppa", {})  # prázdný popis
        assert h["kwp"]["hodnota"] is None
        assert h["kwp"]["hodnota_text"] == "—"

    def test_resolver_snese_none(self):
        h = sk.resolvni_hodnoty("ppa", None)
        assert h["kwp"]["hodnota_text"] == "—"


class TestTabulka:
    def test_ppa_tabulka_jen_zakaznicke_sloupce(self):
        t = sk.resolvni_tabulku("ppa", PPA)
        klice = {s["klic"] for s in t["sloupce"]}
        assert "vynos_ppa_kc" not in klice  # investor sloupec pryč
        assert klice == {"rok", "cena_ppa_kc_mwh", "cena_dodavatel_kc_mwh",
                         "uspora_klient_kc", "uspora_klient_kum_kc"}
        assert len(t["radky"]) == 2
        assert t["radky"][0][0] == "1 let"  # rok
        assert "Kč" in t["radky"][0][3]

    def test_ps_tabulka(self):
        t = sk.resolvni_tabulku("peak_shaving", PS)
        assert len(t["radky"]) == 2
        # cf_kum_kc záporné v 1. roce (vč. investice)
        assert "-" in t["radky"][0][2] or "−" in t["radky"][0][2] or t["radky"][0][2].startswith("-")


class TestGraf:
    def test_ppa_graf(self):
        g = sk.graf_pro_typ("ppa", PPA)
        assert g is not None and g["mesice"] == [1, 2]

    def test_ps_graf_z_doporucene(self):
        g = sk.graf_pro_typ("peak_shaving", PS)
        assert g is not None and "bez_baterie_kw" in g

    def test_graf_chybi(self):
        assert sk.graf_pro_typ("ppa", {}) is None


class TestVychoziSablona:
    def test_ppa_ma_bloky(self):
        s = sk.vychozi_sablona("ppa")
        assert s["bloky"]
        druhy = {b["druh"] for b in s["bloky"]}
        assert {"hlavicka", "text", "udaje", "graf"} <= druhy

    def test_vsechna_pole_ve_vychozi_jsou_v_katalogu(self):
        # Výchozí předloha nesmí odkazovat na neexistující/interní pole.
        for typ in sk.PODPOROVANE_TYPY:
            s = sk.vychozi_sablona(typ)
            pole_klice = sk.platne_klice(typ)
            sloupce_klice = sk.platne_sloupce(typ)
            for b in s["bloky"]:
                if b["druh"] == "udaje":
                    assert set(b["pole"]) <= pole_klice, (typ, b["id"])
                elif b["druh"] == "tabulka":
                    assert set(b["pole"]) <= sloupce_klice, (typ, b["id"])

    def test_kopie_je_nezavisla(self):
        a = sk.vychozi_sablona("ppa")
        a["bloky"].clear()
        b = sk.vychozi_sablona("ppa")
        assert b["bloky"]  # mutace kopie neovlivní další volání
