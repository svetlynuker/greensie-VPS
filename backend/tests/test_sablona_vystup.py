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

# Peak shaving se spočítaným rokem 2027 (nová tarifní struktura) a s obchodem
# na spotu – přesně ta sada, kterou nabídkovač zobrazuje jako výchozí.
PS_2027 = {
    "typ_reseni": "peak_shaving",
    "vstup": {"rezervovana_kapacita_kw": 250.0, "rezim": "kombinace"},
    "doporucena": {
        **PS["doporucena"],
        "rezim": "kombinace",
        "navratnost_2027": 6.4,
        "zisk_spot_kc": 180000.0,
        "ekonomika_2027": {
            "status": "spocitano",
            "soucasny_rocni_naklad": 1100000.0,
            "novy_rocni_naklad": 640000.0,
            "rocni_uspora": 460000.0,
            "rp_soucasny_kw": 300.0,
            "rp_novy_kw": 210.0,
            # interní rozpad – do nabídky nesmí:
            "prinos_baterie": 380000.0,
            "naklad_ztrat_baterie": 25000.0,
        },
        "ekonomika_spot": {"zisk_kc": 180000.0, "naklad_opotrebeni_kc": 40000.0},
        "graf": {
            "mesice": [1, 2],
            "bez_baterie_kw": [240, 250],
            "s_baterii_2026_kw": [180, 180],
            "s_baterii_2027_kw": [150, 160],
            "rp_soucasna_kw": 250.0,
            "rp_nova_kw": 190.0,
            "rp_soucasna_2027_kw": 300.0,
            "rp_nova_2027_kw": 210.0,
        },
    },
}


def txt(hodnoty: dict, klic: str) -> str:
    """Text hodnoty s běžnými mezerami – formátování sází pevné mezery (NBSP),
    v asertech je ale nečitelné."""
    return hodnoty[klic]["hodnota_text"].replace(sk.NBSP, " ")


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

    def test_ps_vysledky_2027_jsou_v_nabidce(self):
        # Nabídkovač zobrazuje jako výchozí model 2027 – nabídka ho musí umět taky.
        h = sk.resolvni_hodnoty("peak_shaving", PS_2027)
        assert txt(h, "soucasny_naklad_2027_kc") == "1 100 000 Kč"
        assert txt(h, "novy_naklad_2027_kc") == "640 000 Kč"
        assert txt(h, "rocni_uspora_2027_kc") == "460 000 Kč"
        assert txt(h, "rezervovany_prikon_kw") == "300 kW"
        assert txt(h, "novy_rezervovany_prikon_kw") == "210 kW"
        assert txt(h, "navratnost_2027_roky") == "6,4 let"

    def test_ps_bez_sazeb_2027_zustane_pomlcka(self):
        # Bez oficiálních sazeb ERÚ pole 2027 zůstanou prázdná (v tisku se skryjí).
        h = sk.resolvni_hodnoty("peak_shaving", PS)
        assert h["rocni_uspora_2027_kc"]["hodnota"] is None
        assert txt(h, "rocni_uspora_2027_kc") == "—"
        # …a čísla roku 2026 se tím nerozbijí
        assert txt(h, "rocni_uspora_2026_kc") == "620 000 Kč"

    def test_ps_obchod_na_spotu(self):
        h = sk.resolvni_hodnoty("peak_shaving", PS_2027)
        assert txt(h, "zisk_spot_kc") == "180 000 Kč"
        assert h["rezim"]["hodnota_text"] == "Srážení špiček + obchod s elektřinou"

    def test_ps_cisty_peak_shaving_obchod_neukazuje(self):
        # Bez obchodního režimu není co ukázat – ne nula, ale prázdno.
        h = sk.resolvni_hodnoty("peak_shaving", PS)
        assert h["zisk_spot_kc"]["hodnota"] is None
        assert h["rezim"]["hodnota"] is None

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
        assert sk.graf_pro_typ("peak_shaving", {}) is None

    def test_ps_graf_bez_2027_kresli_model_2026(self):
        g = sk.graf_pro_typ("peak_shaving", PS)
        assert g["rok_modelu"] == 2026
        assert g["s_baterii_kw"] == [180, 180]
        assert g["popis_soucasna"] == "rezervovaná kapacita nyní"

    def test_ps_graf_s_2027_kresli_totez_co_nabidkovac(self):
        # Panel při spočítané ekonomice 2027 kreslí řadu 2027 a čáry
        # rezervovaného příkonu – nabídka musí kreslit totéž.
        g = sk.graf_pro_typ("peak_shaving", PS_2027)
        assert g["rok_modelu"] == 2027
        assert g["s_baterii_kw"] == [150, 160]
        assert g["rp_soucasna_zobrazena_kw"] == 300.0
        assert g["rp_nova_zobrazena_kw"] == 210.0
        assert g["popis_soucasna"] == "rezervovaný příkon nyní"
        assert g["popis_nova"] == "rezervovaný příkon po instalaci"

    def test_ps_graf_nemeni_ulozeny_popis(self):
        # Normalizace nesmí přepsat `popis_json` řešení.
        puvodni = dict(PS_2027["doporucena"]["graf"])
        sk.graf_pro_typ("peak_shaving", PS_2027)
        assert PS_2027["doporucena"]["graf"] == puvodni


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

    def test_ps_predloha_ma_bloky_2027_i_obchod(self):
        ids = [b["id"] for b in sk.vychozi_sablona("peak_shaving")["bloky"]]
        assert "uspora_2027" in ids and "obchod" in ids

    def test_kopie_je_nezavisla(self):
        a = sk.vychozi_sablona("ppa")
        a["bloky"].clear()
        b = sk.vychozi_sablona("ppa")
        assert b["bloky"]  # mutace kopie neovlivní další volání


class TestDoplneneBloky:
    """Nové bloky předlohy se musí objevit i ve starších uložených nabídkách,
    aniž by se přepsaly texty, které si k nim OZ napsal."""

    ULOZENA = {
        "bloky": [
            {"id": "hlavicka", "druh": "hlavicka", "viditelny": True, "nadpis": "Moje nabídka"},
            {"id": "uvod", "druh": "text", "viditelny": True, "nadpis": "Úvod",
             "text": "Vlastní text obchodníka."},
            {"id": "uspora", "druh": "udaje", "viditelny": True, "nadpis": "Úspora",
             "pole": ["rocni_uspora_2026_kc"]},
            {"id": "zaver", "druh": "text", "viditelny": False, "nadpis": "Závěr", "text": "…"},
        ]
    }

    def test_doplni_chybejici_bloky(self):
        k = sk.doplnene_bloky("peak_shaving", self.ULOZENA)
        ids = [b["id"] for b in k["bloky"]]
        assert "uspora_2027" in ids and "obchod" in ids and "graf" in ids

    def test_neprepise_vlastni_texty_ani_viditelnost(self):
        k = sk.doplnene_bloky("peak_shaving", self.ULOZENA)
        podle_id = {b["id"]: b for b in k["bloky"]}
        assert podle_id["uvod"]["text"] == "Vlastní text obchodníka."
        assert podle_id["hlavicka"]["nadpis"] == "Moje nabídka"
        assert podle_id["zaver"]["viditelny"] is False
        assert podle_id["uspora"]["pole"] == ["rocni_uspora_2026_kc"]

    def test_vlozi_na_misto_z_predlohy(self):
        # V předloze jde `uspora_2027` hned za `uspora` – tam má přijít i tady.
        ids = [b["id"] for b in sk.doplnene_bloky("peak_shaving", self.ULOZENA)["bloky"]]
        assert ids.index("uspora_2027") == ids.index("uspora") + 1
        assert ids.index("obchod") == ids.index("uspora_2027") + 1
        # a `zaver`, který si OZ vypnul, zůstává na svém místě (poslední)
        assert ids[-1] == "zaver"

    def test_nic_nechybi_nic_se_nemeni(self):
        vychozi = sk.vychozi_sablona("peak_shaving")
        assert sk.doplnene_bloky("peak_shaving", vychozi)["bloky"] == vychozi["bloky"]

    def test_prazdna_konfigurace_da_predlohu(self):
        assert sk.doplnene_bloky("peak_shaving", None)["bloky"] == \
            sk.vychozi_sablona("peak_shaving")["bloky"]
        assert sk.doplnene_bloky("peak_shaving", {"bloky": []})["bloky"]

    def test_doplnene_pole_jsou_ve_whitelistu(self):
        # Pojistka: doplněné bloky nesmí odkazovat na pole, které PUT odmítne.
        for typ in sk.PODPOROVANE_TYPY:
            k = sk.doplnene_bloky(typ, {"bloky": [{"id": "hlavicka", "druh": "hlavicka",
                                                   "viditelny": True}]})
            for b in k["bloky"]:
                if b["druh"] == "udaje":
                    assert set(b.get("pole") or []) <= sk.platne_klice(typ), (typ, b["id"])
                elif b["druh"] == "tabulka":
                    assert set(b.get("pole") or []) <= sk.platne_sloupce(typ), (typ, b["id"])


class TestMrizkaAPolozky:
    """Nové vlastnosti prvku: šířka v mřížce a dlaždice s jednou hodnotou."""

    def test_blok_ma_vychozi_sirku_celou(self):
        from app.nabidkovac.schemas import SIRKA_PLNA, VystupBlok

        b = VystupBlok(id="a", druh="text")
        assert b.sirka == SIRKA_PLNA and b.klic == ""

    def test_starsi_ulozena_konfigurace_projde(self):
        # Bloky bez `sirka`/`klic` (uložené před mřížkou) musí zůstat platné.
        from app.nabidkovac.schemas import VystupKonfigurace

        k = VystupKonfigurace(
            bloky=[{"id": "uvod", "druh": "text", "viditelny": True, "nadpis": "Úvod"}]
        )
        assert k.bloky[0].sirka == 12

    def test_sirka_mimo_rozsah_neprojde(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupBlok

        for spatna in (0, -3, 13, 100):
            with pytest.raises(ValidationError):
                VystupBlok(id="a", druh="udaj", klic="nazev", sirka=spatna)

    def test_druhy_bloku_znaji_dlazdici_i_zlom(self):
        from app.nabidkovac.schemas import VystupBlok

        assert VystupBlok(id="a", druh="udaj", klic="nazev").druh == "udaj"
        assert VystupBlok(id="z", druh="zlom").druh == "zlom"


class TestPojistkaKonfigurace:
    """POJISTKA „jen zákaznická data" musí platit i pro dlaždice (druh `udaj`)
    a pro pojmenované šablony – obojí končí ve stejném vykreslení."""

    def _konfigurace(self, **kw):
        from app.nabidkovac.schemas import VystupKonfigurace

        return VystupKonfigurace(bloky=[{"id": "x", "viditelny": True, **kw}])

    def test_dlazdice_se_zakaznickym_polem_projde(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci("peak_shaving", self._konfigurace(druh="udaj", klic="rocni_uspora_2027_kc"))

    def test_dlazdice_s_internim_cislem_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        for interni in ("npv_kc", "irr", "prinos_baterie", "capex_kc"):
            with pytest.raises(HTTPException) as e:
                _over_konfiguraci("peak_shaving", self._konfigurace(druh="udaj", klic=interni))
            assert e.value.status_code == 422

    def test_dlazdice_bez_klice_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException) as e:
            _over_konfiguraci("peak_shaving", self._konfigurace(druh="udaj"))
        assert e.value.status_code == 422

    def test_pole_z_jineho_typu_reseni_neprojde(self):
        # PPA pole v peak shavingu (a naopak) – šablony se mezi typy nepřenášejí.
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException):
            _over_konfiguraci("peak_shaving", self._konfigurace(druh="udaj", klic="kwp"))
        with pytest.raises(HTTPException):
            _over_konfiguraci("ppa", self._konfigurace(druh="udaj", klic="zisk_spot_kc"))

    def test_zlom_a_text_pojistku_nepotrebuji(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci("peak_shaving", self._konfigurace(druh="zlom"))
        _over_konfiguraci("peak_shaving", self._konfigurace(druh="text", text="cokoli"))


class TestSkupinyVPalete:
    def test_kazde_pole_ma_skupinu(self):
        for typ in sk.PODPOROVANE_TYPY:
            for p in sk.katalog_pro_frontend(typ)["pole"]:
                assert p.get("skupina"), (typ, p["klic"])

    def test_pole_stejne_skupiny_jdou_po_sobe(self):
        # Paleta seskupuje podle pořadí z katalogu – rozházené skupiny by se
        # v editoru zobrazily dvakrát.
        for typ in sk.PODPOROVANE_TYPY:
            videne = []
            for p in sk.katalog_pro_frontend(typ)["pole"]:
                if not videne or videne[-1] != p["skupina"]:
                    videne.append(p["skupina"])
            assert len(videne) == len(set(videne)), (typ, videne)

    def test_doplnene_bloky_zachovaji_sirku_a_klic(self):
        ulozena = {
            "bloky": [
                {"id": "hlavicka", "druh": "hlavicka", "viditelny": True},
                {"id": "d1", "druh": "udaj", "klic": "rocni_uspora_2026_kc", "sirka": 4,
                 "viditelny": True},
            ]
        }
        k = sk.doplnene_bloky("peak_shaving", ulozena)
        dlazdice = next(b for b in k["bloky"] if b["id"] == "d1")
        assert dlazdice["sirka"] == 4 and dlazdice["klic"] == "rocni_uspora_2026_kc"
