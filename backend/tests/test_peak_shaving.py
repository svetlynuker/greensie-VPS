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
