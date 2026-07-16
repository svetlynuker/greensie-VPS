# -*- coding: utf-8 -*-
"""Testy výpočetního jádra PPA pro FVE (`app/nabidkovac/ppa_fve.py`).

Modul je bez závislostí na DB/FastAPI – testuje se přímo (inspirace:
docs/reserze_kalkulator/bughunt/synteticke-testy.md).
"""

from app.nabidkovac import ppa_fve as ppa


# --------------------------------------------------- PPA-1: limit max_kwp
class TestKandidatniVelikosti:
    """Bughunt PPA-1 (test T1): sweep nesmí překročit limit střechy max_kwp."""

    # kandidatni_velikosti používá jen součty řad – stačí jednoprvkové seznamy.
    BASE_1KWP = [1000.0]  # kWh/kWp/rok
    SPOTREBA = [3000.0]  # kWh/rok → surový strop sweeper = 3× 3000/1000 = 9 kWp

    def test_max_kwp_pod_5_je_tvrdy_limit(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=3.0)
        assert kandidati == [1, 2, 3]
        assert all(k <= 3.0 for k in kandidati)

    def test_bez_limitu_se_pouzije_pomer_ke_spotrebe(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=None)
        assert max(kandidati) == 9
        assert min(kandidati) >= 1

    def test_mala_spotreba_ma_sweep_aspon_do_5_kwp(self):
        # surový strop 3×1000/1000 = 3 kWp → minimální rozsah sweepu je 5 kWp.
        kandidati = ppa.kandidatni_velikosti([], [1000.0], self.BASE_1KWP, max_kwp=None)
        assert max(kandidati) == 5

    def test_limit_pod_1_kwp_vrati_aspon_jednoho_kandidata(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=0.5)
        assert kandidati == [1]

    def test_prazdna_spotreba_nema_kandidaty(self):
        assert ppa.kandidatni_velikosti([], [0.0], self.BASE_1KWP) == []
