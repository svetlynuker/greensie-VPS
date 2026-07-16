# -*- coding: utf-8 -*-
"""Testy výpočetního jádra PPA pro FVE (`app/nabidkovac/ppa_fve.py`).

Modul je bez závislostí na DB/FastAPI – testuje se přímo (inspirace:
docs/reserze_kalkulator/bughunt/synteticke-testy.md).
"""

from datetime import datetime, timedelta

import pytest

from app.nabidkovac import ppa_fve as ppa


def den_casy(rok, mesic, den):
    """15min časové značky jednoho dne."""
    t = datetime(rok, mesic, den)
    return [t + timedelta(minutes=15 * i) for i in range(96)]


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


# ------------------------------------------- PPA-2: kalibrace výroby dle PVGIS
class TestKalibraceVyroby:
    """Hodnoty z PVGIS v5.3 (SARAH3), střed ČR – pvgis-kalibrace-vyroby-fve.md."""

    def test_merny_vynos_stred_cr(self):
        assert ppa.VYCHOZI_MERNY_VYNOS_KWH_KWP == 1055.0

    def test_mesicni_tabulka_sedi_s_pvgis_a_secte_1000(self):
        assert sum(ppa._MESICNI_VYNOS.values()) == pytest.approx(1000.0)
        assert ppa._MESICNI_VYNOS[10] == 72.0  # říjen: dřív 58 (+24 % rel. chyba)
        assert ppa._MESICNI_VYNOS[5] == 120.9  # květen: dřív 135 (moc „letní")
        # zimní půlrok (říj–bře) = 30,4 % ročního výnosu dle SARAH3
        zima = sum(ppa._MESICNI_VYNOS[m] for m in (10, 11, 12, 1, 2, 3))
        assert zima / 1000.0 == pytest.approx(0.304, abs=0.002)

    @pytest.mark.parametrize(
        "azimut,sklon,k",
        [
            (0, 35, 1.00),
            (180, 35, 0.54),  # sever: dřív 0,66 (nadhodnocení ~+22 %)
            (180, 60, 0.34),  # strmý sever: dřív 0,50 (+48 % rel.!)
            (0, 0, 0.85),  # horizontála: dřív 0,88
            (90, 35, 0.80),  # V/Z: dřív 0,84
            (0, 60, 0.94),  # strmý jih: dřív 0,91
            (45, 35, 0.94),
        ],
    )
    def test_korekce_orientace_dle_pvgis(self, azimut, sklon, k):
        assert ppa.korekce_orientace(azimut, sklon) == pytest.approx(k)

    def test_korekce_orientace_symetrie_vychod_zapad(self):
        assert ppa.korekce_orientace(-90, 35) == ppa.korekce_orientace(90, 35)

    def test_rocni_vyroba_odpovida_mernemu_vynosu(self):
        casy = []
        t = datetime(2025, 1, 1)
        while t < datetime(2026, 1, 1):
            casy.append(t)
            t += timedelta(minutes=15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        assert sum(vyroba) == pytest.approx(1055.0, rel=1e-6)


# --------------------------------------------------- PPA-3: posun letního času
class TestLetniCas:
    def test_okno_letniho_casu_2025(self):
        # 2025: přechody 30. 3. a 26. 10.
        assert not ppa._je_letni_cas(datetime(2025, 3, 30, 1, 45))
        assert ppa._je_letni_cas(datetime(2025, 3, 30, 2, 0))
        assert ppa._je_letni_cas(datetime(2025, 10, 26, 2, 45))
        assert not ppa._je_letni_cas(datetime(2025, 10, 26, 3, 0))
        assert not ppa._je_letni_cas(datetime(2025, 1, 15, 12, 0))
        assert ppa._je_letni_cas(datetime(2025, 7, 15, 12, 0))

    def test_letni_spicka_vyroby_je_ve_13_hodin(self):
        casy = den_casy(2025, 7, 15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        spicka = casy[vyroba.index(max(vyroba))]
        assert spicka.hour == 13 and spicka.minute == 0

    def test_zimni_spicka_vyroby_je_ve_12_hodin(self):
        casy = den_casy(2025, 1, 15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        spicka = casy[vyroba.index(max(vyroba))]
        assert spicka.hour == 12 and spicka.minute == 0

    def test_posun_nemeni_denni_energii(self):
        # Normalizace tvaru dne zachovává energii – posun jen přesouvá v čase.
        letni = sum(ppa.simuluj_vyrobu(den_casy(2025, 7, 15), 1.0, 49.8, 35, 0))
        assert letni > 0
        # celý červenec v jednodenním profilu = E_měsíc/počet dní v profilu;
        # den má nenulovou energii a součet tvaru je normovaný
        casy2 = den_casy(2025, 7, 15) + den_casy(2025, 7, 16)
        vyroba2 = ppa.simuluj_vyrobu(casy2, 1.0, 49.8, 35, 0)
        assert sum(vyroba2[:96]) == pytest.approx(sum(vyroba2[96:]), rel=1e-9)
