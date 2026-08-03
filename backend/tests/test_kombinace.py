# -*- coding: utf-8 -*-
"""Testy kombinace opatření a sjednocení tvaru PPA (`kombinace.py`, `ppa_tvar.py`).

Dvě věci, které se tu hlídají především:

1. **Nabídka nesmí zmlknout, když se změní tvar výpočtu.** Po přechodu PPA na
   verzi 2 četl katalog pořád starý klíč `vysledek`, takže se tištěná PPA
   nabídka vysázela prázdná („—" ve všech polích) a kombinace tvrdila, že
   elektrárna nešetří nic. Testy proto jedou nad OBĚMA tvary.
2. **Náklad, výnos a čistý přínos musí sedět na korunu.** Když se rozejdou,
   zákazník dostane nabídku, kde dlaždice nesouhlasí s tabulkou pod nimi.
"""

from app.nabidkovac import kombinace as k
from app.nabidkovac import ppa_tvar
from app.nabidkovac import sablona_katalog as sk


# ---- ukázková data ----------------------------------------------------------
# PPA ve starším tvaru (v1): hotový výsledek rovnou pod `vysledek`.
PPA_V1 = {
    "typ_reseni": "ppa",
    "vysledek": {
        "kwp": 142.4,
        "delka_kontraktu_roky": 15,
        "vyroba_rok1_kwh": 150000.0,
        "rocni_spotreba_kwh": 240000.0,
        "samospotreba_rok1_kwh": 120000.0,
        "pokryti_spotreby_fve": 0.5,
        "vyhnutelna_cena_rok1_kc_mwh": 3200.0,
        "souhrn_klient": {"uspora_kum_kc": 1234567.0},
        "roky": [
            {
                "rok": 1,
                "cena_ppa_kc_mwh": 2100.0,
                "cena_dodavatel_kc_mwh": 3200.0,
                "samospotreba_kwh": 120000.0,
                "uspora_klient_kc": 132000.0,
                "uspora_klient_kum_kc": 132000.0,
            },
            {
                "rok": 2,
                "cena_ppa_kc_mwh": 2163.0,
                "cena_dodavatel_kc_mwh": 3296.0,
                "samospotreba_kwh": 119000.0,
                "uspora_klient_kc": 134827.0,
                "uspora_klient_kum_kc": 266827.0,
            },
        ],
        "graf": {"mesice": [1, 2], "vyroba_kwh": [1, 2]},
    },
}


def _varianta(delka: int, kwp: float, cena_ppa: float) -> dict:
    return {
        "delka_kontraktu_roky": delka,
        "kwp": kwp,
        "cena_ppa_kc_mwh": cena_ppa,
        "cena_vyhnutelna_kc_mwh": 3200.0,
        "uspora_kumulativni_kc": 900000.0,
        "energie": {
            "spotreba_mwh": 240.0,
            "vyroba_rok1_mwh": 150.0,
            "samospotreba_mwh": 120.0,
            "pokryti_spotreby_fve": 0.5,
        },
        "roky_klient": [
            {
                "rok": 1,
                "cena_ppa_kc_mwh": cena_ppa,
                "cena_vyhnutelna_kc_mwh": 3200.0,
                "samospotreba_mwh": 120.0,
                "najem_baterie_kc": 0.0,
                "uspora_kc": (3200.0 - cena_ppa) * 120.0,
                "uspora_kumulativni_kc": (3200.0 - cena_ppa) * 120.0,
            },
        ],
        "graf": {"mesice": [1, 2], "vyroba_kwh": [1, 2]},
    }


# PPA v novém tvaru (v2): varianty podle technologie a délky kontraktu.
PPA_V2 = {
    "typ_reseni": "ppa",
    "verze": 2,
    "vstup": {"s_baterii": False, "sklon_st": 35, "azimut_st": 0},
    "bez_baterie": {
        "kwp": 359.0,
        "po_delkach": [_varianta(10, 359.0, 2100.0), _varianta(15, 359.0, 2000.0)],
    },
    "s_baterii": {
        "kwp": 400.0,
        "po_delkach": [_varianta(10, 400.0, 2300.0)],
    },
}

PS = {
    "typ_reseni": "peak_shaving",
    "vstup": {"rezervovana_kapacita_kw": 410.0},
    "doporucena": {
        "nazev": "BESS 100 kW / 330 kWh",
        "celkovy_vykon_kw": 100.0,
        "celkova_kapacita_kwh": 330.0,
        "cena_celkem_kc": 2000000.0,
        "nova_rezervovana_kapacita_kw": 232.0,
        "rezim": "kombinace",
        "zisk_spot_kc": 115000.0,
        "navratnost_2027": 6.7,
        "rocni_uspora_2026_kc": 398000.0,
        "ekonomika_2026": {
            "soucasny_naklad_celkem": 1242000.0,
            "novy_naklad_rezervace": 844000.0,
            "naklad_ztrat_baterie": 0.0,
            "rocni_uspora": 398000.0,
        },
        "ekonomika_2027": {
            "status": "spocitano",
            "soucasny_rocni_naklad": 1000000.0,
            "novy_rocni_naklad": 820000.0,
            "rocni_uspora": 180000.0,
        },
        "roky": [
            {"rok": 1, "prinos_kc": 295000.0, "oam_kc": 40000.0, "cf_kc": 255000.0},
            {"rok": 2, "prinos_kc": 290000.0, "oam_kc": 40000.0, "cf_kc": 250000.0},
        ],
        "graf": {"mesice": [1, 2], "bez_baterie_kw": [400, 410]},
    },
}


class TestSjednoceniTvaruPpa:
    """Starší i novější tvar výsledku musí dát tatáž čísla."""

    def test_v1_se_bere_beze_zmeny(self):
        assert ppa_tvar.vysledek(PPA_V1)["kwp"] == 142.4

    def test_v2_se_premapuje_na_stejne_klice(self):
        v = ppa_tvar.vysledek(PPA_V2)
        assert v["kwp"] == 359.0
        assert v["delka_kontraktu_roky"] == 10
        # MWh z v2 se převádí na kWh, ve kterých počítá zbytek nabídky.
        assert v["vyroba_rok1_kwh"] == 150000.0
        assert v["rocni_spotreba_kwh"] == 240000.0
        assert v["samospotreba_rok1_kwh"] == 120000.0
        assert v["roky"][0]["cena_dodavatel_kc_mwh"] == 3200.0
        assert v["roky"][0]["uspora_klient_kc"] == 132000.0

    def test_sklon_a_azimut_se_doplni_ze_vstupu(self):
        # v2 je ve výsledku nenese – bez doplnění by v nabídce chyběly.
        v = ppa_tvar.vysledek(PPA_V2)
        assert v["sklon_st"] == 35
        assert v["azimut_st"] == 0

    def test_varianta_s_baterii_kdyz_ji_zakaznik_chce(self):
        popis = {**PPA_V2, "vstup": {**PPA_V2["vstup"], "s_baterii": True}}
        assert ppa_tvar.vysledek(popis)["kwp"] == 400.0

    def test_prazdny_vstup_nespadne(self):
        for x in (None, {}, {"vstup": {}}, "nesmysl", {"bez_baterie": {"po_delkach": []}}):
            assert ppa_tvar.vysledek(x) == {}


class TestRozpadElektrarny:
    def test_vynos_minus_naklad_je_uspora(self):
        for popis in (PPA_V1, PPA_V2):
            r = ppa_tvar.rozpad_rok1(popis)
            assert round(r["vynos_rok1_kc"] - r["naklad_rok1_kc"], 2) == round(
                r["cisty_prinos_rok1_kc"], 2
            )

    def test_naklad_je_odebrana_energie_krat_cena_ppa(self):
        r = ppa_tvar.rozpad_rok1(PPA_V1)
        assert round(r["naklad_rok1_kc"], 2) == round(120.0 * 2100.0, 2)

    def test_investice_je_nula_ne_prazdno(self):
        # U PPA zákazník neinvestuje – prázdné pole by v nabídce vypadalo jako
        # chybějící údaj, přitom je to hlavní prodejní argument.
        assert ppa_tvar.rozpad_rok1(PPA_V2)["investice_kc"] == 0.0

    def test_nespocitana_nabidka_nevymysli_cisla(self):
        r = ppa_tvar.rozpad_rok1({})
        assert r["naklad_rok1_kc"] is None
        assert r["vynos_rok1_kc"] is None


class TestRozpadBaterie:
    def test_naklad_je_kapacita_plus_provoz(self):
        r = k.rozpad_ps_rok1(PS)
        assert r["naklad_rok1_kc"] == 820000.0 + 40000.0

    def test_vynos_je_odpadla_platba_plus_obchod(self):
        r = k.rozpad_ps_rok1(PS)
        assert r["vynos_rok1_kc"] == 1000000.0 + 115000.0

    def test_cisty_prinos_sedi_s_rocni_tabulkou(self):
        # Rozdíl výnosu a nákladu musí být přesně `cf_kc` prvního roku,
        # jinak dlaždice říká něco jiného než tabulka pod ní.
        r = k.rozpad_ps_rok1(PS)
        assert r["cisty_prinos_rok1_kc"] == PS["doporucena"]["roky"][0]["cf_kc"]

    def test_bez_sazeb_2027_se_pocita_model_2026(self):
        ps = {
            **PS,
            "doporucena": {
                **PS["doporucena"],
                "ekonomika_2027": {"status": "ceka_na_sazby_eru"},
            },
        }
        r = k.rozpad_ps_rok1(ps)
        assert r["model"] == "2026"
        assert r["vynos_kapacita_rok1_kc"] == 1242000.0
        assert r["naklad_kapacita_rok1_kc"] == 844000.0

    def test_cisty_peak_shaving_obchod_nevykazuje(self):
        # V režimu bez obchodování by nula tvrdila, že obchod nic nenese.
        ps = {**PS, "doporucena": {**PS["doporucena"], "rezim": "peak_shaving"}}
        r = k.rozpad_ps_rok1(ps)
        assert r["zisk_obchod_rok1_kc"] is None
        assert r["vynos_rok1_kc"] == 1000000.0


class TestSouhrnKombinace:
    def test_soucty_sedi_na_korunu(self):
        s = k.souhrn(PPA_V2, PS)
        assert s["spolu_naklad_rok1_kc"] == (
            s["ppa_naklad_rok1_kc"] + s["ps_naklad_rok1_kc"]
        )
        assert s["spolu_vynos_rok1_kc"] == (
            s["ppa_vynos_rok1_kc"] + s["ps_vynos_rok1_kc"]
        )
        assert round(s["spolu_vynos_rok1_kc"] - s["spolu_naklad_rok1_kc"], 2) == round(
            s["cisty_prinos_rok1_celkem_kc"], 2
        )
        assert round(
            s["ppa_cisty_prinos_rok1_kc"] + s["ps_cisty_prinos_rok1_kc"], 2
        ) == round(s["cisty_prinos_rok1_celkem_kc"], 2)

    def test_elektrarna_z_noveho_tvaru_neni_prazdna(self):
        # Regrese: dokud se četl klíč `vysledek`, byla tu None a nabídka
        # tvrdila, že elektrárna nešetří nic.
        s = k.souhrn(PPA_V2, PS)
        assert s["uspora_ppa_rok1_kc"] == 132000.0
        assert s["delka_kontraktu_roky"] == 10

    def test_investice_je_jen_baterie(self):
        # PPA je bez investice, takže veškerá investice kombinace je baterie.
        s = k.souhrn(PPA_V2, PS)
        assert s["investice_zakaznika_kc"] == 2000000.0
        assert s["ppa_investice_kc"] == 0.0

    def test_navratnosti_jsou_dve_ruzna_cisla(self):
        s = k.souhrn(PPA_V2, PS)
        assert s["navratnost_baterie_roky"] == 6.7
        assert s["navratnost_kombinace_roky"] == round(
            2000000.0 / s["cisty_prinos_rok1_celkem_kc"], 2
        )

    def test_chybejici_zdroj_nevyrobi_nuly(self):
        s = k.souhrn({}, {})
        assert s["cisty_prinos_rok1_celkem_kc"] is None
        assert s["navratnost_kombinace_roky"] is None


class TestSpolecnaTabulka:
    def test_bere_cisty_prinos_baterie_po_provozu(self):
        radky = k.spolecna_tabulka(PPA_V2, PS)
        assert radky[0]["uspora_ps_kc"] == 255000.0  # cf_kc, ne prinos_kc

    def test_soucet_a_kumulativ(self):
        radky = k.spolecna_tabulka(PPA_V2, PS)
        assert radky[0]["uspora_celkem_kc"] == (
            radky[0]["uspora_ppa_kc"] + radky[0]["uspora_ps_kc"]
        )
        assert radky[1]["uspora_kum_kc"] == (
            radky[0]["uspora_celkem_kc"] + radky[1]["uspora_celkem_kc"]
        )

    def test_starsi_vysledek_bez_cf_se_neztrati(self):
        ps = {
            **PS,
            "doporucena": {
                **PS["doporucena"],
                "roky": [{"rok": 1, "prinos_kc": 295000.0}],
            },
        }
        assert k.spolecna_tabulka(PPA_V2, ps)[0]["uspora_ps_kc"] == 295000.0


class TestNabidkaCteObaTvary:
    """Katalog nabídky nad reálnými tvary – co se vysází zákazníkovi."""

    def test_ppa_v2_nabidka_neni_prazdna(self):
        # Hlavní regrese: takhle se tiskla nabídka bez jediného čísla.
        hodnoty = sk.resolvni_hodnoty("ppa", PPA_V2)
        prazdne = [kl for kl, v in hodnoty.items() if v["hodnota"] is None]
        assert prazdne == []
        assert sk.graf_pro_typ("ppa", PPA_V2) is not None
        assert len(sk.resolvni_tabulku("ppa", PPA_V2)["radky"]) == 1

    def test_ppa_v1_nabidka_funguje_dal(self):
        hodnoty = sk.resolvni_hodnoty("ppa", PPA_V1)
        assert hodnoty["kwp"]["hodnota"] == 142.4
        assert len(sk.resolvni_tabulku("ppa", PPA_V1)["radky"]) == 2

    def test_kombinace_ma_vsechna_pole(self):
        popis = k.slouceny_popis(PPA_V2, PS, ppa_nabidka_id=1, ps_nabidka_id=2)
        hodnoty = sk.resolvni_hodnoty("kombinace", popis)
        prazdne = [kl for kl, v in hodnoty.items() if v["hodnota"] is None]
        assert prazdne == []

    def test_dlazdice_a_tabulka_rikaji_totez(self):
        popis = k.slouceny_popis(PPA_V2, PS, ppa_nabidka_id=1, ps_nabidka_id=2)
        hodnoty = sk.resolvni_hodnoty("kombinace", popis)
        radek1 = k.spolecna_tabulka(PPA_V2, PS)[0]
        assert hodnoty["ppa_cisty_prinos_rok1"]["hodnota"] == radek1["uspora_ppa_kc"]
        assert hodnoty["ps_cisty_prinos_rok1"]["hodnota"] == radek1["uspora_ps_kc"]
        assert (
            hodnoty["cisty_prinos_rok1_celkem"]["hodnota"] == radek1["uspora_celkem_kc"]
        )

    def test_starsi_kombinace_se_dopocita_ze_zdroju(self):
        # Spojení uložená před opravou mají v souhrnu u elektrárny `null`.
        # Nesmí zůstat prázdná – zdroje jsou přitom uložené s nimi.
        popis = k.slouceny_popis(PPA_V2, PS, ppa_nabidka_id=1, ps_nabidka_id=2)
        popis["souhrn"] = {"uspora_ppa_rok1_kc": None, "uspora_rok1_celkem_kc": 180000.0}
        popis["roky"] = [{"rok": 1, "uspora_ppa_kc": None, "uspora_ps_kc": 295000.0}]
        hodnoty = sk.resolvni_hodnoty("kombinace", popis)
        assert hodnoty["uspora_ppa_rok1"]["hodnota"] == 132000.0
        assert sk.resolvni_tabulku("kombinace", popis)["radky"][0][1] != "—"


class TestNoveDlazdiceNejsouInterni:
    """Nová pole nesmí prolomit pojistku „do nabídky jen zákaznická data"."""

    def test_katalog_nenabizi_interni_klice(self):
        interni = {"capex_kc", "npv_kc", "irr", "marze", "zisk_greensie_kc",
                   "nakladova_cena_kc", "provize_kc", "prinos_baterie"}
        assert not (sk.platne_klice("kombinace") & interni)

    def test_pole_ve_vychozi_predloze_existuji(self):
        klice = sk.platne_klice("kombinace")
        pouzite = set()

        def projdi(prvky):
            for p in prvky:
                pouzite.update(p.get("pole") or [])
                projdi(p.get("deti") or [])

        for stranka in sk.vychozi_sablona("kombinace")["stranky"]:
            projdi(stranka["prvky"])
        assert pouzite <= klice | sk.platne_sloupce("kombinace")
