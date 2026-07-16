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
