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


class TestVychoziPredloha:
    """Předloha v modelu v2: pevné A4 stránky a prvky na mm souřadnicích."""

    def _prvky(self, konfigurace: dict) -> list[dict]:
        """Všechny prvky napříč stránkami včetně dětí kontejnerů."""
        out = []

        def projdi(prvky):
            for p in prvky:
                out.append(p)
                projdi(p.get("deti") or [])

        for s in konfigurace["stranky"]:
            projdi(s["prvky"])
        return out

    def test_predloha_ma_stranky_a_prvky(self):
        s = sk.vychozi_sablona("ppa")
        assert s["verze"] == 2
        assert len(s["stranky"]) >= 1
        druhy = {p["druh"] for p in self._prvky(s)}
        assert {"text", "kontejner", "udaj", "graf"} <= druhy

    def test_predloha_projde_schematem(self):
        from app.nabidkovac.schemas import VystupKonfigurace

        for typ in sk.PODPOROVANE_TYPY:
            VystupKonfigurace(**sk.vychozi_sablona(typ))

    def test_vsechna_pole_ve_vychozi_jsou_v_katalogu(self):
        # Výchozí předloha nesmí odkazovat na neexistující/interní pole.
        for typ in sk.PODPOROVANE_TYPY:
            s = sk.vychozi_sablona(typ)
            for p in self._prvky(s):
                if p["druh"] == "udaj":
                    assert p["klic"] in sk.platne_klice(typ), (typ, p["id"])
                elif p["druh"] == "tabulka":
                    assert set(p["pole"]) <= sk.platne_sloupce(typ), (typ, p["id"])

    def test_nic_nepretece_pres_zapati(self):
        # Předloha se má po otevření vejít – jinak by obchodníka hned vítalo
        # červené varování o přetečení.
        for typ in sk.PODPOROVANE_TYPY:
            for s in sk.vychozi_sablona(typ)["stranky"]:
                for p in s["prvky"]:
                    assert p["y"] + p["vyska"] <= sk.OBSAH_DO_MM + 1, (typ, p["id"])
                    assert p["y"] >= sk.OBSAH_OD_MM - 1, (typ, p["id"])

    def test_prvky_se_neprekryvaji(self):
        # Generátor skládá sekce pod sebe; překryv by znamenal chybu v odhadu.
        for typ in sk.PODPOROVANE_TYPY:
            for s in sk.vychozi_sablona(typ)["stranky"]:
                serazene = sorted(s["prvky"], key=lambda p: p["y"])
                for a, b in zip(serazene, serazene[1:]):
                    assert a["y"] + a["vyska"] <= b["y"] + 0.01, (typ, a["id"], b["id"])

    def test_ps_predloha_ma_sekce_2027_i_obchod(self):
        ids = {p["id"] for p in self._prvky(sk.vychozi_sablona("peak_shaving"))}
        assert "uspora_2027" in ids and "obchod" in ids

    def test_dlazdice_stoji_vedle_sebe(self):
        # Klíčové údaje mají být v mřížce, ne pod sebou na celou šířku.
        klicove = next(
            p
            for p in self._prvky(sk.vychozi_sablona("peak_shaving"))
            if p["id"] == "klicove"
        )
        assert klicove["druh"] == "kontejner"
        assert klicove["styl"]["sloupce"] == 3
        assert len(klicove["deti"]) == 5

    def test_kopie_je_nezavisla(self):
        a = sk.vychozi_sablona("ppa")
        a["stranky"].clear()
        assert sk.vychozi_sablona("ppa")["stranky"]


class TestNactiKonfiguraci:
    """Uložené rozvržení se bere jen v modelu v2; cokoli staršího dostane
    výchozí předlohu (Dan zvolil čistý start, staré se nemigruje)."""

    def test_verze2_se_vrati_beze_zmeny(self):
        ulozena = sk.vychozi_sablona("ppa")
        ulozena["stranky"][0]["prvky"][0]["html"] = "<p>moje</p>"
        k, je_vychozi = sk.nacti_konfiguraci("ppa", ulozena)
        assert je_vychozi is False
        assert k["stranky"][0]["prvky"][0]["html"] == "<p>moje</p>"

    def test_stary_model_dostane_predlohu(self):
        stara = {"bloky": [{"id": "uvod", "druh": "text", "nadpis": "Úvod"}]}
        k, je_vychozi = sk.nacti_konfiguraci("ppa", stara)
        assert je_vychozi is True
        assert k["verze"] == 2 and k["stranky"]

    def test_prazdna_konfigurace_dostane_predlohu(self):
        for prazdna in (None, {}, {"stranky": []}):
            k, je_vychozi = sk.nacti_konfiguraci("ppa", prazdna)
            assert je_vychozi is True and k["stranky"]

    def test_je_verze2(self):
        assert sk.je_verze2({"verze": 2}) is True
        assert sk.je_verze2({"bloky": []}) is False
        assert sk.je_verze2(None) is False


class TestSchemaPrvku:
    """Meze modelu: papír je A4 a vnoření je jednoúrovňové."""

    def test_vychozi_prvek(self):
        from app.nabidkovac.schemas import VystupPrvek

        p = VystupPrvek(id="a", druh="text")
        assert p.viditelny and p.auto_vyska and p.styl.sloupce == 1

    def test_kontejner_v_kontejneru_neprojde(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupPrvek

        with pytest.raises(ValidationError):
            VystupPrvek(
                id="a",
                druh="kontejner",
                deti=[{"id": "b", "druh": "kontejner"}],
            )

    def test_prvek_v_kontejneru_projde(self):
        from app.nabidkovac.schemas import VystupPrvek

        k = VystupPrvek(id="a", druh="kontejner", deti=[{"id": "b", "druh": "text"}])
        assert k.deti[0].druh == "text"

    def test_souradnice_mimo_papir_neprojdou(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupPrvek

        for spatna in (-500, 5000):
            with pytest.raises(ValidationError):
                VystupPrvek(id="a", druh="text", x=spatna)

    def test_nulova_sirka_neprojde(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupPrvek

        with pytest.raises(ValidationError):
            VystupPrvek(id="a", druh="text", sirka=0)

    def test_barva_musi_byt_hex_nebo_prazdna(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupStyl

        assert VystupStyl(pozadi="").pozadi == ""
        assert VystupStyl(pozadi="#ff0000").pozadi == "#ff0000"
        for spatna in ("red", "#fff", "javascript:x", "#gggggg"):
            with pytest.raises(ValidationError):
                VystupStyl(pozadi=spatna)

    def test_konfigurace_chce_verzi_2(self):
        from pydantic import ValidationError

        from app.nabidkovac.schemas import VystupKonfigurace

        assert VystupKonfigurace().verze == 2
        with pytest.raises(ValidationError):
            VystupKonfigurace(verze=1)


class TestPojistkaKonfigurace:
    """POJISTKA „jen zákaznická data" musí platit i pro prvky uvnitř
    kontejnerů – jinak by se interní číslo propašovalo o úroveň níž."""

    def _konfigurace(self, *prvky):
        from app.nabidkovac.schemas import VystupKonfigurace

        return VystupKonfigurace(
            stranky=[{"id": "s1", "prvky": [{"id": f"p{i}", **p} for i, p in enumerate(prvky)]}]
        )

    def test_dlazdice_se_zakaznickym_polem_projde(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci(
            "peak_shaving",
            self._konfigurace({"druh": "udaj", "klic": "rocni_uspora_2027_kc"}),
        )

    def test_dlazdice_s_internim_cislem_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        for interni in ("npv_kc", "irr", "prinos_baterie", "capex_kc"):
            with pytest.raises(HTTPException) as e:
                _over_konfiguraci(
                    "peak_shaving", self._konfigurace({"druh": "udaj", "klic": interni})
                )
            assert e.value.status_code == 422

    def test_interni_cislo_v_kontejneru_taky_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException) as e:
            _over_konfiguraci(
                "peak_shaving",
                self._konfigurace(
                    {"druh": "kontejner", "deti": [{"id": "x", "druh": "udaj", "klic": "npv_kc"}]}
                ),
            )
        assert e.value.status_code == 422

    def test_dlazdice_bez_klice_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException) as e:
            _over_konfiguraci("peak_shaving", self._konfigurace({"druh": "udaj"}))
        assert e.value.status_code == 422

    def test_pole_z_jineho_typu_reseni_neprojde(self):
        # PPA pole v peak shavingu (a naopak) – šablony se mezi typy nepřenášejí.
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException):
            _over_konfiguraci("peak_shaving", self._konfigurace({"druh": "udaj", "klic": "kwp"}))
        with pytest.raises(HTTPException):
            _over_konfiguraci("ppa", self._konfigurace({"druh": "udaj", "klic": "zisk_spot_kc"}))

    def test_sloupec_tabulky_mimo_whitelist_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException):
            _over_konfiguraci(
                "peak_shaving", self._konfigurace({"druh": "tabulka", "pole": ["oam_kc"]})
            )

    def test_text_a_grafika_pojistku_nepotrebuji(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci(
            "peak_shaving",
            self._konfigurace(
                {"druh": "text", "html": "<p>cokoli</p>"},
                {"druh": "cara"},
                {"druh": "obdelnik"},
                {"druh": "cislo_stranky"},
            ),
        )

    def test_predloha_projde_vlastni_pojistkou(self):
        from app.nabidkovac.routes import _over_konfiguraci
        from app.nabidkovac.schemas import VystupKonfigurace

        for typ in sk.PODPOROVANE_TYPY:
            _over_konfiguraci(typ, VystupKonfigurace(**sk.vychozi_sablona(typ)))


class TestSanitizaceHtml:
    """Formátovaný text z papíru se čistí whitelistem – i uvnitř kontejnerů."""

    def test_vycisti_cely_strom(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci
        from app.nabidkovac.schemas import VystupKonfigurace

        k = VystupKonfigurace(
            stranky=[
                {
                    "id": "s1",
                    "prvky": [
                        {
                            "id": "k",
                            "druh": "kontejner",
                            "html": "<h2>Nadpis</h2><script>zlo()</script>",
                            "deti": [
                                {
                                    "id": "t",
                                    "druh": "text",
                                    "html": '<p onclick="zlo()">Text</p>',
                                }
                            ],
                        }
                    ],
                }
            ]
        )
        c = _sanituj_konfiguraci(k)
        kontejner = c.stranky[0].prvky[0]
        assert kontejner.html == "<h2>Nadpis</h2>"
        assert kontejner.deti[0].html == "<p>Text</p>"

    def test_puvodni_model_zustane_nedotceny(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci
        from app.nabidkovac.schemas import VystupKonfigurace

        k = VystupKonfigurace(
            stranky=[{"id": "s1", "prvky": [{"id": "t", "druh": "text", "html": "<b>a"}]}]
        )
        _sanituj_konfiguraci(k)
        assert k.stranky[0].prvky[0].html == "<b>a"


class TestVystupHtmlWhitelist:
    """Vlastní sanitizér (`vystup_html`) – poslední slovo před uložením."""

    def test_formatovani_projde(self):
        from app.nabidkovac.vystup_html import vycisti_html

        vstup = '<p style="text-align: center">Ahoj <strong>světe</strong> <em>a</em></p>'
        assert vycisti_html(vstup) == vstup

    def test_script_zmizi_i_s_obsahem(self):
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html("<script>alert(1)</script><p>text</p>") == "<p>text</p>"
        assert "alert" not in vycisti_html("<style>x{}</style><p>a</p>")

    def test_atributy_krome_stylu_zmizi(self):
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html('<p onclick="zlo()" class="x">a</p>') == "<p>a</p>"

    def test_odkaz_prijde_o_znacku_ale_ne_o_text(self):
        # Vložený odstavec z webu má přijít o formátování, ne o obsah.
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html('<a href="http://zlo.cz">klikni</a>') == "klikni"

    def test_nebezpecne_styly_zmizi(self):
        from app.nabidkovac.vystup_html import vycisti_html

        for zly in (
            '<span style="background: url(http://zlo.cz/x)">a</span>',
            '<span style="width: expression(alert(1))">a</span>',
            '<span style="position: fixed">a</span>',
        ):
            assert "style" not in vycisti_html(zly)

    def test_cizi_pismo_se_zahodi(self):
        # Písmo omezené na to, co umíme vytisknout – jinak PDF vypadá jinde jinak.
        from app.nabidkovac.vystup_html import vycisti_html

        assert "font-family" not in vycisti_html(
            '<span style="font-family: Comic Sans MS">a</span>'
        )
        assert "font-family" in vycisti_html('<span style="font-family: Arial">a</span>')

    def test_nezavrene_tagy_se_dozavrou(self):
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html("<p><b>text") == "<p><b>text</b></p>"

    def test_prazdny_vstup(self):
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html(None) == "" and vycisti_html("") == ""

    def test_delka_je_omezena(self):
        from app.nabidkovac.vystup_html import MAX_DELKA_HTML, vycisti_html

        assert len(vycisti_html("a" * (MAX_DELKA_HTML * 2))) <= MAX_DELKA_HTML

    def test_ostre_zavorky_v_textu_se_escapuji(self):
        from app.nabidkovac.vystup_html import vycisti_html

        assert vycisti_html("<p>5 < 7 & 8 > 3</p>") == "<p>5 &lt; 7 &amp; 8 &gt; 3</p>"


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


# ---- ukázkový popis_json pro PPA + BESS (jen část s baterií) ----
# Ostatní bloky (`po_delkach`, `rezimy`) tu schválně nejsou: extraktory na ně
# sahají přes `_pb`/`_pb_d`, které při chybějícím bloku vrátí None, takže
# vzorek zůstane malý a testuje se to, o co jde – popis modulu baterie.
PPA_BESS = {
    "typ_reseni": "ppa_bess",
    "elektrarna": {"kwp": 300.0, "vyroba_mwh": 320.0},
    "baterie": {
        "nazev": "BESS 100/215",
        "pocet_kusu": 2,
        "kapacita_kwh": 430.0,
        "vykon_kw": 200.0,
        "najem_kc_mesic": 45000.0,
        "doba_najmu_roky": 10,
        # interní – do nabídky nesmí:
        "capex_kc": 5400000.0,
        "nakladova_cena_kc": 4200000.0,
    },
}


class TestPpaBessModulBaterie:
    """Nabídka PPA + BESS musí umět říct, JAKÁ baterie se navrhuje.

    Katalog typu `ppa_bess` vznikl bez označení modulu a počtu kusů, takže
    baterii popisoval jen kapacitou a výkonem – v nabídce pak po modulu
    nezůstalo nic, i když ho výpočet ukládá.
    """

    def test_katalog_ma_modul_i_pocet(self):
        klice = sk.platne_klice("ppa_bess")
        assert "baterie_nazev" in klice and "baterie_pocet_kusu" in klice

    def test_katalog_nema_ceny_baterie(self):
        # Nákladová cena a CAPEX baterie leží ve stejném bloku popisu jako
        # název – tím spíš musí zůstat mimo katalog.
        klice = sk.platne_klice("ppa_bess")
        assert "capex_kc" not in klice and "nakladova_cena_kc" not in klice

    def test_resolver_vrati_nazev_a_pocet(self):
        h = sk.resolvni_hodnoty("ppa_bess", PPA_BESS)
        assert h["baterie_nazev"]["hodnota"] == "BESS 100/215"
        assert txt(h, "baterie_nazev") == "BESS 100/215"
        assert txt(h, "baterie_pocet_kusu") == "2 ks"

    def test_rucne_zadana_baterie_se_popise_parametry(self):
        # Ručně zadaná baterie nemá název produktu. Kdyby se vzal jen ten,
        # dlaždice „Modul baterie" by u takové nabídky v PDF beze slova zmizela.
        h = sk.resolvni_hodnoty(
            "ppa_bess",
            {"typ_reseni": "ppa_bess", "baterie": {"kapacita_kwh": 430.0, "vykon_kw": 200.0}},
        )
        assert txt(h, "baterie_nazev") == "Bateriové úložiště 200 kW / 430,0 kWh"

    def test_bez_baterie_zustane_pomlcka(self):
        # Nabídka bez baterie (`baterie: null`) nesmí spadnout – pole zůstane
        # prázdné a v tisku se samo nevykreslí.
        h = sk.resolvni_hodnoty("ppa_bess", {"typ_reseni": "ppa_bess", "baterie": None})
        assert h["baterie_nazev"]["hodnota"] is None
        assert txt(h, "baterie_nazev") == "—"

    def test_vychozi_predloha_modul_ukazuje(self):
        klice = {
            p["klic"]
            for s in sk.vychozi_sablona("ppa_bess")["stranky"]
            for prvek in s["prvky"]
            for p in [prvek, *(prvek.get("deti") or [])]
            if p["druh"] == "udaj"
        }
        assert "baterie_nazev" in klice


class TestPocetRucnichHodnot:
    """Ručně přepsaná hodnota je jediné místo, kde nabídka smí říkat jiné číslo
    než výpočet – musí být spočitatelná, aby o ní šlo dát vědět."""

    def _konfigurace(self, *prvky):
        return {
            "verze": 2,
            "stranky": [
                {"id": "s1", "prvky": [{"id": f"p{i}", **p} for i, p in enumerate(prvky)]}
            ],
        }

    def test_pocita_dlazdice_s_rucni_hodnotou(self):
        k = self._konfigurace(
            {"druh": "udaj", "klic": "kwp", "rucni_hodnota": "142 kWp"},
            {"druh": "udaj", "klic": "vyroba_mwh"},
        )
        assert sk.pocet_rucnich_hodnot(k) == 1

    def test_pocita_i_v_kontejneru(self):
        # Dlaždice v předloze leží uvnitř kontejnerů – bez rekurze by se
        # počítadlo dívalo do prázdna.
        k = self._konfigurace(
            {
                "druh": "kontejner",
                "deti": [
                    {"id": "a", "druh": "udaj", "klic": "kwp", "rucni_hodnota": "1"},
                    {"id": "b", "druh": "udaj", "klic": "vyroba_mwh", "rucni_hodnota": "2"},
                ],
            }
        )
        assert sk.pocet_rucnich_hodnot(k) == 2

    def test_same_mezery_se_nepocitaji(self):
        k = self._konfigurace({"druh": "udaj", "klic": "kwp", "rucni_hodnota": "   "})
        assert sk.pocet_rucnich_hodnot(k) == 0

    def test_jiny_druh_se_nepocita(self):
        k = self._konfigurace({"druh": "text", "rucni_hodnota": "nesmysl"})
        assert sk.pocet_rucnich_hodnot(k) == 0

    def test_snese_prazdno_i_stary_model(self):
        assert sk.pocet_rucnich_hodnot(None) == 0
        assert sk.pocet_rucnich_hodnot({}) == 0
        assert sk.pocet_rucnich_hodnot({"bloky": [{"druh": "udaj"}]}) == 0

    def test_predloha_zadnou_rucni_hodnotu_nema(self):
        for typ in sk.PODPOROVANE_TYPY:
            assert sk.pocet_rucnich_hodnot(sk.vychozi_sablona(typ)) == 0


class TestRucniHodnotaSanitizace:
    """Ruční hodnota se na papíře vykresluje jako text, ne HTML – a jen
    u dlaždice. Obojí musí platit i pro data poslaná přímo na API."""

    def _prvek(self, **kw):
        from app.nabidkovac.schemas import VystupKonfigurace

        return VystupKonfigurace(stranky=[{"id": "s1", "prvky": [{"id": "p", **kw}]}])

    def test_znacky_se_odstrani(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci

        k = _sanituj_konfiguraci(
            self._prvek(druh="udaj", klic="kwp", rucni_hodnota="<b>142</b> kWp")
        )
        assert k.stranky[0].prvky[0].rucni_hodnota == "142 kWp"

    def test_zlomy_radku_se_slouci(self):
        # Dlaždice má jeden řádek; zlom by na papíře uřízl `overflow: hidden`.
        from app.nabidkovac.routes import _sanituj_konfiguraci

        k = _sanituj_konfiguraci(
            self._prvek(druh="udaj", klic="kwp", rucni_hodnota="142\n\tkWp")
        )
        assert k.stranky[0].prvky[0].rucni_hodnota == "142 kWp"

    def test_u_jineho_druhu_se_zahodi(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci

        k = _sanituj_konfiguraci(self._prvek(druh="text", rucni_hodnota="142"))
        assert k.stranky[0].prvky[0].rucni_hodnota == ""

    def test_cisti_i_v_kontejneru(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci
        from app.nabidkovac.schemas import VystupKonfigurace

        k = _sanituj_konfiguraci(
            VystupKonfigurace(
                stranky=[
                    {
                        "id": "s1",
                        "prvky": [
                            {
                                "id": "k",
                                "druh": "kontejner",
                                "deti": [
                                    {
                                        "id": "d",
                                        "druh": "udaj",
                                        "klic": "kwp",
                                        "rucni_hodnota": "<i>1</i>",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            )
        )
        assert k.stranky[0].prvky[0].deti[0].rucni_hodnota == "1"

    def test_delka_je_omezena(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self._prvek(druh="udaj", klic="kwp", rucni_hodnota="x" * 200)

    def test_prezije_cestu_pres_ulozeni(self):
        # Cesta, po které hodnota v provozu jde: PUT → sanitizace → `model_dump`
        # do JSON sloupce → čtení zpět. Kdyby se pole na kterémkoli kroku
        # ztratilo, přepis by po uložení tiše zmizel.
        from app.nabidkovac.routes import _sanituj_konfiguraci

        ulozeno = _sanituj_konfiguraci(
            self._prvek(druh="udaj", klic="kwp", rucni_hodnota="142 kWp")
        ).model_dump()
        assert ulozeno["stranky"][0]["prvky"][0]["rucni_hodnota"] == "142 kWp"
        k, je_vychozi = sk.nacti_konfiguraci("ppa", ulozeno)
        assert je_vychozi is False
        assert sk.pocet_rucnich_hodnot(k) == 1

    def test_rucni_hodnota_neobejde_whitelist_klicu(self):
        # POJISTKA: ruční hodnota mění jen to, co se vytiskne, ne to, co se smí
        # do nabídky vložit. Interní klíč musí padnout dál na 422.
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException) as e:
            _over_konfiguraci(
                "peak_shaving",
                self._prvek(druh="udaj", klic="npv_kc", rucni_hodnota="900 000 Kč"),
            )
        assert e.value.status_code == 422


class TestProstyText:
    def test_zahodi_znacky_a_slouci_mezery(self):
        from app.nabidkovac.vystup_html import prosty_text

        assert prosty_text("  <span>1  200</span>\nKč ") == "1 200 Kč"

    def test_prazdny_vstup(self):
        from app.nabidkovac.vystup_html import prosty_text

        assert prosty_text(None) == "" and prosty_text("") == ""

    def test_delka(self):
        from app.nabidkovac.vystup_html import MAX_DELKA_HODNOTY, prosty_text

        assert len(prosty_text("a" * 500)) == MAX_DELKA_HODNOTY


class TestRegistrTabulek:
    """Od 7. 8. 2026 má typ řešení víc tabulek – prvek na papíře říká, kterou
    ukazuje (`tabulka_klic`). Prázdný klíč musí dál znamenat roční tabulku,
    jinak by se rozvržení uložená dřív vykreslila prázdná."""

    def test_kazdy_typ_ma_rocni_tabulku(self):
        for typ in sk.PODPOROVANE_TYPY:
            assert sk.TABULKA_VYCHOZI in sk.platne_tabulky(typ), typ

    def test_odkup_jen_tam_kde_se_pocita(self):
        # Peak shaving ani kombinace odkup elektrárny nemají – nabízet ho tam
        # by znamenalo tabulku, která zůstane navždy prázdná.
        assert "odkup" in sk.platne_tabulky("ppa")
        assert "odkup" in sk.platne_tabulky("ppa_bess")
        assert "odkup" not in sk.platne_tabulky("peak_shaving")
        assert "odkup" not in sk.platne_tabulky("kombinace")

    def test_odkupni_sloupce_jsou_jen_zakaznicke(self):
        sloupce = sk.platne_sloupce("ppa", "odkup")
        assert sloupce == {"rok", "odkupni_cena_kc"}
        for interni in ("zustatek_uveru_kc", "poplatek_predcasne_splaceni_kc", "zisk_spv_kc"):
            assert interni not in sloupce

    def test_bez_klice_jsou_sloupce_rocni_tabulky(self):
        assert sk.platne_sloupce("ppa") == sk.platne_sloupce("ppa", sk.TABULKA_VYCHOZI)

    def test_neznama_tabulka_spadne_na_rocni(self):
        # Resolver nesmí spadnout na klíči, který v katalogu není – validaci
        # dělá `PUT`, tisk má pořád něco vykreslit.
        assert sk.platne_sloupce("ppa", "vymyslena") == sk.platne_sloupce("ppa")

    def test_katalog_nese_tabulky_pro_editor(self):
        katalog = sk.katalog_pro_frontend("ppa_bess")
        klice = {t["klic"] for t in katalog["tabulky"]}
        assert klice == {"roky", "odkup"}
        # Roční sloupce zůstávají zvlášť – editor podle nich kreslí prvky
        # uložené bez `tabulka_klic`.
        assert katalog["tabulka_sloupce"]

    def test_kazda_tabulka_ma_nazev_a_sloupce(self):
        for typ in sk.PODPOROVANE_TYPY:
            for t in sk.katalog_pro_frontend(typ)["tabulky"]:
                assert t["nazev"] and t["sloupce"], (typ, t["klic"])


class TestOdkupniTabulkaVNabidce:
    """Odkup elektrárny po letech na papíře: PPA čte svou variantu, PPA + BESS
    zvolenou délku kontraktu. Interní čísla se do tabulky nesmí dostat."""

    PPA_V2 = {
        "typ_reseni": "ppa",
        "vstup": {"s_baterii": False},
        "bez_baterie": {
            "po_delkach": [
                {
                    "delka_roky": 15,
                    "kwp": 300.0,
                    "roky_klient": [{"rok": 1, "cena_ppa_kc_mwh": 2100.0}],
                    "odkupni_tabulka": [
                        {
                            "rok": 1,
                            "odkupni_cena_kc": 10_222_492.05,
                            # interní – v tabulce nesmí být:
                            "zustatek_uveru_kc": 8_137_307.1,
                            "poplatek_predcasne_splaceni_kc": 406_865.36,
                            "zisk_spv_kc": 1_678_319.59,
                        },
                        {"rok": 2, "odkupni_cena_kc": 9_800_000.0},
                    ],
                }
            ]
        },
    }

    PPA_BESS = {
        "typ_reseni": "ppa_bess",
        "po_delkach": [
            {
                "delka_roky": 10,
                "odkupni_tabulka": [{"rok": 1, "odkupni_cena_kc": 5_000_000.0}],
            },
            {
                "delka_roky": 20,
                "odkupni_tabulka": [
                    {"rok": 1, "odkupni_cena_kc": 12_000_000.0},
                    {"rok": 2, "odkupni_cena_kc": 11_500_000.0},
                ],
            },
        ],
    }

    def test_ppa_tabulka_ma_rok_a_cenu(self):
        t = sk.resolvni_tabulku("ppa", self.PPA_V2, tabulka="odkup")
        assert [s["klic"] for s in t["sloupce"]] == ["rok", "odkupni_cena_kc"]
        assert t["nazev"] == "Odkup elektrárny po letech"
        assert len(t["radky"]) == 2
        # Rok je jen číslo – jednotka („let") patří do názvu sloupce, ne do buňky.
        assert t["radky"][0][0] == "1"
        assert t["radky"][0][1].replace(sk.NBSP, " ") == "10 222 492 Kč"

    def test_ppa_tabulka_neobsahuje_interni_cisla(self):
        t = sk.resolvni_tabulku("ppa", self.PPA_V2, tabulka="odkup")
        vse = " ".join(x for radek in t["radky"] for x in radek)
        for interni in ("8 137 307", "406 865", "1 678 319"):
            assert interni not in vse.replace(sk.NBSP, " ")

    def test_ppa_bess_bere_zvolenou_delku(self):
        # Bez volby se ukazuje nejdelší kontrakt – tabulka musí být z téže
        # délky jako dlaždice, jinak si nabídka odporuje.
        nejdelsi = sk.resolvni_tabulku("ppa_bess", self.PPA_BESS, tabulka="odkup")
        assert len(nejdelsi["radky"]) == 2
        kratsi = sk.resolvni_tabulku("ppa_bess", self.PPA_BESS, 10, "odkup")
        assert len(kratsi["radky"]) == 1
        assert kratsi["radky"][0][1].replace(sk.NBSP, " ") == "5 000 000 Kč"

    def test_bez_dat_zustane_prazdna(self):
        # Starší nabídka odkupní tabulku nemá (výpočet ji tehdy neukládal) –
        # blok se v tisku sám neukáže, místo aby spadl.
        for popis in (None, {}, {"typ_reseni": "ppa"}):
            t = sk.resolvni_tabulku("ppa", popis, tabulka="odkup")
            assert t["radky"] == []

    def test_u_typu_bez_odkupu_je_prazdna(self):
        t = sk.resolvni_tabulku("peak_shaving", PS, tabulka="odkup")
        # Neznámý klíč spadne na roční tabulku – ta u peak shavingu data má.
        assert [s["klic"] for s in t["sloupce"]] == ["rok", "prinos_kc", "cf_kum_kc"]

    def test_resolvni_tabulky_vrati_vsechny(self):
        tabulky = sk.resolvni_tabulky("ppa", self.PPA_V2)
        assert set(tabulky) == {"roky", "odkup"}
        assert tabulky["odkup"]["radky"]

    def test_rocni_tabulka_zustala_beze_zmeny(self):
        # Zavedení registru nesmí posunout to, co nabídky tisknou dnes.
        t = sk.resolvni_tabulku("peak_shaving", PS)
        assert [s["klic"] for s in t["sloupce"]] == ["rok", "prinos_kc", "cf_kum_kc"]
        assert len(t["radky"]) == 2


class TestPojistkaTabulek:
    """`PUT` musí odmítnout neznámou tabulku i sloupec z jiné tabulky."""

    def _tabulka(self, **kw):
        from app.nabidkovac.schemas import VystupKonfigurace

        return VystupKonfigurace(
            stranky=[{"id": "s1", "prvky": [{"id": "t", "druh": "tabulka", **kw}]}]
        )

    def test_odkupni_tabulka_projde(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci(
            "ppa_bess",
            self._tabulka(tabulka_klic="odkup", pole=["rok", "odkupni_cena_kc"]),
        )

    def test_bez_klice_projde_jako_dosud(self):
        from app.nabidkovac.routes import _over_konfiguraci

        _over_konfiguraci("peak_shaving", self._tabulka(pole=["rok", "prinos_kc"]))

    def test_neznama_tabulka_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException) as e:
            _over_konfiguraci("ppa", self._tabulka(tabulka_klic="vymyslena", pole=["rok"]))
        assert e.value.status_code == 422

    def test_odkup_u_typu_bez_odkupu_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException):
            _over_konfiguraci(
                "peak_shaving", self._tabulka(tabulka_klic="odkup", pole=["rok"])
            )

    def test_sloupec_z_jine_tabulky_neprojde(self):
        # `prinos_kc` je sloupec roční tabulky; v odkupní by zůstal prázdný.
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        with pytest.raises(HTTPException):
            _over_konfiguraci(
                "ppa_bess", self._tabulka(tabulka_klic="odkup", pole=["cisty_prinos_kc"])
            )

    def test_interni_sloupec_odkupu_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_konfiguraci

        for interni in ("zustatek_uveru_kc", "zisk_spv_kc", "poplatek_predcasne_splaceni_kc"):
            with pytest.raises(HTTPException) as e:
                _over_konfiguraci("ppa", self._tabulka(tabulka_klic="odkup", pole=[interni]))
            assert e.value.status_code == 422

    def test_klic_tabulky_se_u_jineho_druhu_zahodi(self):
        from app.nabidkovac.routes import _sanituj_konfiguraci
        from app.nabidkovac.schemas import VystupKonfigurace

        k = _sanituj_konfiguraci(
            VystupKonfigurace(
                stranky=[
                    {"id": "s1", "prvky": [{"id": "t", "druh": "text", "tabulka_klic": "odkup"}]}
                ]
            )
        )
        assert k.stranky[0].prvky[0].tabulka_klic == ""
