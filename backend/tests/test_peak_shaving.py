# -*- coding: utf-8 -*-
"""Testy výpočetního jádra peak shavingu (`app/nabidkovac/peak_shaving.py`).

Modul je bez závislostí na DB/FastAPI – testuje se přímo nad syntetickými
profily (inspirace: docs/reserze_kalkulator/bughunt/synteticke-testy.md).
"""

import pytest

from app.nabidkovac import peak_shaving as ps


# ---------------------------------------------------------------- PS-2: pokuty
class TestPokutaPrekroceniRk:
    """Bod 4.24 CV ERÚ: překročení RK = 1,5× měsíční cena za měsíční RK."""

    def test_odvozeni_z_mesicni_rk_cez_2026(self):
        # ČEZ 2026 (CV 13/2025): VN 281,823 → 422,73; VVN 131,036 → 196,55.
        assert ps.pokuta_prekroceni_rk_kc_kw(281.823) == pytest.approx(422.7345)
        assert ps.pokuta_prekroceni_rk_kc_kw(131.036) == pytest.approx(196.554)

    def test_nasobek_je_15(self):
        assert ps.NASOBEK_POKUTY_PREKROCENI_RK == 1.5
        assert ps.pokuta_prekroceni_rk_kc_kw(100.0) == pytest.approx(150.0)

    def test_vychozi_rocni_naklad_uctuje_prekroceni_po_mesicich(self):
        # Leden: maxima 180 kW (překročení 60), únor: 150 kW (překročení 30).
        profil = [100.0, 180.0, 100.0, 150.0]
        mesice = [1, 1, 2, 2]
        pokuta = ps.pokuta_prekroceni_rk_kc_kw(281.823)
        rez, prekr = ps.vychozi_rocni_naklad_2026(profil, mesice, 120.0, 3030.78, pokuta)
        assert rez == pytest.approx(120.0 * 3030.78)
        assert prekr == pytest.approx((60.0 + 30.0) * pokuta)

    def test_bez_prekroceni_zadna_pokuta(self):
        profil = [100.0, 110.0]
        mesice = [1, 2]
        rez, prekr = ps.vychozi_rocni_naklad_2026(
            profil, mesice, 120.0, 3030.78, ps.pokuta_prekroceni_rk_kc_kw(281.823)
        )
        assert prekr == 0.0


# ------------------------------------------------------ PS-3: model 2027 bez AKU
# Sazby ČEZ VN z informativního CV ERÚ (5/2026), Kč/kW/měsíc.
P2027_CEZ_VN = {
    "t1_kapacita_kc_kw_mesic": 190.133,
    "t1_spicka_kc_kw_mesic": 19.013,
    "t2_kapacita_kc_kw_mesic": 22.743,
    "t2_spicka_kc_kw_mesic": 227.429,
    "sazba_prekroceni_kc_kw_mesic": 761.0,
    "u1_ucinnost": 0.60,
    "u2_ucinnost": 0.75,
}

# Dva měsíce po 8 intervalech: leden konstantně 100 kW, únor konstantně 200 kW.
PROFIL_2M = [100.0] * 8 + [200.0] * 8
MESICE_2M = [1] * 8 + [2] * 8


class TestEkonomika2027BezAku:
    """Rozhodnutí PS-3: sleva AKU pro BTM baterii bez exportu neexistuje (K=0)."""

    def test_mesicni_naklad_je_min_z_tarifu_bez_slevy(self):
        c, tarif = ps._mesicni_naklad_2027(100.0, 80.0, P2027_CEZ_VN)
        t1 = 100.0 * 190.133 + 80.0 * 19.013
        t2 = 100.0 * 22.743 + 80.0 * 227.429
        assert c == pytest.approx(min(t1, t2))
        assert tarif == ("t1" if t1 <= t2 else "t2")

    def test_penalizace_za_prekroceni_rp(self):
        t1 = 100.0 * 190.133 + 120.0 * 19.013
        t2 = 100.0 * 22.743 + 120.0 * 227.429
        c, _ = ps._mesicni_naklad_2027(100.0, 120.0, P2027_CEZ_VN)
        assert c == pytest.approx(min(t1, t2) + 20.0 * 761.0)

    def test_vystup_neobsahuje_aku_pole(self):
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 200.0, 150.0, 60.0, 1000.0, P2027_CEZ_VN)
        assert ek["status"] == "spocitano"
        for klic in (
            "prumerny_koeficient_aku",
            "prumerna_ucinnost",
            "predpoklad_aku_neoverovany",
            "novy_rocni_naklad_bez_aku",
            "rocni_uspora_bez_aku",
        ):
            assert klic not in ek
        assert ek["rocni_uspora"] == pytest.approx(
            ek["soucasny_rocni_naklad"] - ek["novy_rocni_naklad"]
        )
        assert ek["pocet_mesicu_t1"] + ek["pocet_mesicu_t2"] == 2

    def test_novy_naklad_odpovida_srazenym_maximum_bez_slevy(self):
        vykon, kapacita = 60.0, 1000.0
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 200.0, 150.0, vykon, kapacita, P2027_CEZ_VN)
        po_mesicich = ps.mesicni_maxima_po_baterii(PROFIL_2M, MESICE_2M, vykon, kapacita)
        ocekavany, _, _ = ps._rocni_naklad_2027(150.0, po_mesicich, P2027_CEZ_VN)
        assert ek["novy_rocni_naklad"] == pytest.approx(ocekavany)

    def test_varianta_nese_jedinou_navratnost_2027(self):
        baterie = ps.Baterie(id=1, nazev="Test 60/120", vykon_kw=60.0, kapacita_kwh=120.0, cena_kc=1_000_000.0)
        v = ps.spocti_variantu(
            baterie,
            1,
            PROFIL_2M,
            MESICE_2M,
            200.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            parametry_2027=P2027_CEZ_VN,
        )
        assert v.navratnost_2027 is not None
        assert not hasattr(v, "navratnost_2027_optim")
        assert not hasattr(v, "navratnost_2027_konzerv")
        assert "prumerny_koeficient_aku" not in v.ekonomika_2027


# ------------------------------------------------------- PS-5: ztráty baterie
class TestZtratyBaterie:
    def test_normalizace_ucinnosti(self):
        assert ps.normalizuj_ucinnost_rt(None) == 0.88
        assert ps.normalizuj_ucinnost_rt(0.92) == 0.92
        assert ps.normalizuj_ucinnost_rt(88) == 0.88  # zadáno v procentech
        assert ps.normalizuj_ucinnost_rt(1.2) == 0.88  # nesmysl → default
        assert ps.normalizuj_ucinnost_rt(0.3) == 0.88  # nereálně nízké → default
        assert ps.normalizuj_ucinnost_rt("nesmysl") == 0.88

    def test_strop_se_ztratami_je_vyssi_nez_bezztraty(self):
        # T7: dvě špičky denně, mezi nimi krátké okno na dobití.
        profil = []
        for den in range(5):
            profil += [200.0] * 36 + [350.0] * 8 + [200.0] * 8 + [350.0] * 8 + [200.0] * 36
        bez = ps.min_udrzitelny_strop(profil, 80.0, 160.0, ucinnost_rt=1.0)
        se_ztratami = ps.min_udrzitelny_strop(profil, 80.0, 160.0, ucinnost_rt=0.88)
        assert se_ztratami > bez

    def test_energeticka_bilance_nabito_vybito(self):
        # Vybije se 25 kWh AC na špičce, pak se plně dobije: nabito = vybito/RT.
        profil = [150.0, 150.0] + [50.0] * 96
        nabito, vybito = ps.energie_pri_stropu(
            profil, 100.0, 80.0, 100.0, interval_h=0.25, ucinnost_rt=0.88
        )
        assert vybito == pytest.approx(25.0)
        assert nabito == pytest.approx(25.0 / 0.88, rel=1e-6)

    def test_naklad_ztrat(self):
        # 10 MWh nabito při RT 0,88 a 3000 Kč/MWh → 10 000 × 0,12 × 3 = 3 600 Kč.
        assert ps.naklad_ztrat_baterie_kc(10_000.0, 0.88, 3000.0) == pytest.approx(3600.0)
        assert ps.naklad_ztrat_baterie_kc(10_000.0, 1.0, 3000.0) == 0.0

    def test_varianta_pocita_s_vyuzitelnou_kapacitou_a_ztratami(self):
        # Špička na začátku, pak base load pod stropem → baterie se po vybití
        # dobíjí ze sítě a ztráty cyklování mají nenulovou cenu.
        profil = [200.0] * 4 + [100.0] * 12
        mesice = [1] * 8 + [2] * 8
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=120.0, cena_kc=1_000_000.0, ucinnost_rt=0.88
        )
        v = ps.spocti_variantu(
            baterie,
            1,
            profil,
            mesice,
            200.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            cena_energie_kc_mwh=3000.0,
        )
        assert v.vyuzitelna_kapacita_kwh == pytest.approx(120.0 * 0.85)
        assert v.ucinnost_rt == 0.88
        ek = v.ekonomika_2026
        assert ek["naklad_ztrat_baterie"] > 0
        assert ek["rocni_uspora"] == pytest.approx(
            ek["soucasny_naklad_celkem"] - ek["novy_naklad_rezervace"] - ek["naklad_ztrat_baterie"]
        )

    def test_bezztratovy_rezim_odpovida_puvodnimu_chovani(self):
        profil = [100.0, 180.0, 100.0, 150.0]
        strop = ps.min_udrzitelny_strop(profil, 50.0, 100.0, ucinnost_rt=1.0)
        nabito, vybito = ps.energie_pri_stropu(profil, strop, 50.0, 100.0, ucinnost_rt=1.0)
        assert nabito >= 0 and vybito >= 0
        assert ps.naklad_ztrat_baterie_kc(nabito, 1.0, 3000.0) == 0.0
