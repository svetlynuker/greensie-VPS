# -*- coding: utf-8 -*-
"""Vnitřní konzistence čísel v nabídce PRO ZÁKAZNÍKA (revize 26. 7. 2026).

Na rozdíl od `test_sablona_vystup.py` (který jede nad ukázkovým `popis_json`)
tyhle testy poskládají výstup ze SKUTEČNÉHO výpočtu a kontrolují, že si čísla
v jednom dokumentu neodporují. Nabídka je obchodní dokument – když si zákazník
dopočítá návratnost z uvedené investice a úspory a vyjde mu něco jiného, než
co v nabídce stojí, přijde celý dokument o důvěryhodnost.

Konkrétní vada, kterou to hlídá: karta „Roční úspora“ brala celkovou úsporu
proti dnešnímu stavu (tedy včetně úspory z pouhé úpravy sjednané rezervace),
zatímco „Návratnost investice“ se počítala z přínosu baterie → investice ÷
úspora dávalo 2,2 roku, ale nabídka tvrdila 41,7 let.
"""

import calendar

import pytest

from app.nabidkovac import peak_shaving as ps
from app.nabidkovac import sablona_katalog as sk
from app.nabidkovac.routes import _varianta_json

CENA_ROCNI_RK = 3030.78
CENA_MESICNI_RK = 281.823


def _profil_rok():
    """Hodinový profil roku: základ 600 kW, pracovní špička 950, letní 1250."""
    profil, mesice = [], []
    den = 0
    for m in range(1, 13):
        for d in range(1, calendar.monthrange(2025, m)[1] + 1):
            vikend = den % 7 in (5, 6)
            den += 1
            for h in range(24):
                v = 600.0
                if not vikend and 7 <= h < 17:
                    v = 950.0
                if m in (6, 7, 8) and not vikend and 11 <= h < 15:
                    v = 1250.0
                if m == 7 and d == 10 and 12 <= h < 13:
                    v = 1500.0
                profil.append(v)
                mesice.append(m)
    return profil, mesice


@pytest.fixture(scope="module")
def vystup_ps():
    """Skutečný výpočet peak shavingu → popis_json → resolvnutá nabídka."""
    profil, mesice = _profil_rok()
    baterie = ps.Baterie(
        id=1, nazev="BESS 300 kW / 660 kWh", vykon_kw=300.0, kapacita_kwh=660.0,
        cena_kc=4_851_422.0, ucinnost_rt=0.95,
        uzitna_kapacita_kwh=660.0, max_vykon_stridacu_kw=300.0,
    )
    varianta = ps.spocti_variantu(
        baterie, 1, profil, mesice,
        rezervovana_kapacita_kw=1800.0,
        cena_rezervace_kc_kw_rok=CENA_ROCNI_RK,
        cena_prekroceni_kc_kw=ps.pokuta_prekroceni_rk_kc_kw(CENA_MESICNI_RK),
        max_navratnost_roky=5.0, interval_h=1.0,
        cena_mesicni_rk_kc_kw_mesic=CENA_MESICNI_RK,
        rezerva_rk_procenta=5.0,
    )
    vj = _varianta_json(varianta)
    popis = {
        "typ_reseni": "peak_shaving",
        "vstup": {"rezervovana_kapacita_kw": 1800.0},
        "doporucena": vj,
        "varianty": [vj],
    }
    return {
        "hodnoty": sk.resolvni_hodnoty("peak_shaving", popis),
        "tabulka": sk.resolvni_tabulku("peak_shaving", popis),
        "varianta": varianta,
    }


class TestKonzistenceNabidkyPS:
    def test_navratnost_odpovida_investici_dele_uvedenou_usporou(self, vystup_ps):
        h = vystup_ps["hodnoty"]
        investice = h["cena_celkem_kc"]["hodnota"]
        prinos = h["prinos_baterie_2026_kc"]["hodnota"]
        navratnost = h["navratnost_roky"]["hodnota"]
        assert investice > 0 and prinos > 0
        # Přesně tohle si zákazník spočítá na kalkulačce. Tolerance = úroveň,
        # na kterou se čísla v nabídce tisknou (návratnost na 1 desetinu).
        assert navratnost == pytest.approx(investice / prinos, abs=0.05)

    def test_rozpad_uspory_secte_na_celkovou(self, vystup_ps):
        h = vystup_ps["hodnoty"]
        assert h["rocni_uspora_2026_kc"]["hodnota"] == pytest.approx(
            h["uspora_bez_investice_2026_kc"]["hodnota"]
            + h["prinos_baterie_2026_kc"]["hodnota"]
        )

    def test_obe_slozky_uspory_jsou_v_nabidce_k_dispozici(self, vystup_ps):
        # Bez rozpadu nejde vysvětlit, proč je návratnost počítaná jen z části
        # úspory – obě pole proto musí být v katalogu i ve výchozí šabloně.
        klice = sk.platne_klice("peak_shaving")
        assert {"uspora_bez_investice_2026_kc", "prinos_baterie_2026_kc"} <= klice
        blok = next(
            b for b in sk.VYCHOZI_SABLONA["peak_shaving"]["bloky"] if b["id"] == "uspora"
        )
        assert "uspora_bez_investice_2026_kc" in blok["pole"]
        assert "prinos_baterie_2026_kc" in blok["pole"]
        assert blok["viditelny"] is True

    def test_uspora_bez_investice_neni_zaporna(self, vystup_ps):
        assert vystup_ps["hodnoty"]["uspora_bez_investice_2026_kc"]["hodnota"] >= 0

    def test_prvni_rok_tabulky_odpovida_karte_prinosu_baterie(self, vystup_ps):
        # Karta „Úspora díky baterii“ a 1. řádek tabulky „Úspora díky baterii“
        # musí být totéž číslo – dřív se lišily řádově.
        karta = vystup_ps["hodnoty"]["prinos_baterie_2026_kc"]["hodnota_text"]
        tabulka = vystup_ps["tabulka"]["radky"][0][1]
        assert karta == tabulka

    def test_sloupec_rok_je_bez_jednotky(self, vystup_ps):
        assert vystup_ps["tabulka"]["radky"][0][0] == "1"
        assert vystup_ps["tabulka"]["sloupce"][0]["nazev"] == "Rok"

    def test_pocet_mesicu_s_dokupem_je_v_nabidce(self, vystup_ps):
        # Vysvětluje, proč je nová roční rezervace nižší než sražená špička
        # a proč sloupce v grafu v některých měsících přerostou čáru.
        h = vystup_ps["hodnoty"]["dokupy_s_baterii_pocet_mesicu"]
        assert h["hodnota"] is not None
        blok = next(
            b for b in sk.VYCHOZI_SABLONA["peak_shaving"]["bloky"] if b["id"] == "kapacita"
        )
        assert "dokupy_s_baterii_pocet_mesicu" in blok["pole"]

    def test_nabidka_nenese_zadne_interni_cislo(self, vystup_ps):
        # Whitelist drží i po přidání nových polí.
        h = vystup_ps["hodnoty"]
        for zakazany in ("npv_kc", "irr", "naklad_ztrat_baterie", "diskontni_sazba"):
            assert zakazany not in h
