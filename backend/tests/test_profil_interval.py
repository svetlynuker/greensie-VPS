# -*- coding: utf-8 -*-
"""Odvození délky intervalu profilu a ošetření vadných hodnot (revize 26. 7. 2026).

Délka intervalu je kritická: profil se ukládá jako činný výkon (kW) a PPA ho
přepočítává na energii násobením právě tímhle číslem. Dřív se brala jen první
dvojice časových značek, takže jediná chybějící hodnota na začátku exportu
zdvojnásobila vykázanou roční spotřebu klienta – a validace pokrytí to
pustila, protože očekávaný počet intervalů počítá z téhož čísla.
"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.nabidkovac.routes import (
    _interval_h_z_profilu,
    _mrizka_profilu_ok,
    _zvaliduj_a_orizni_profil,
    _zvaliduj_indexy,
)
from app.nabidkovac.schemas import PpaVstup


def rok_15min(rok=2025, vynech_indexy=()):
    """15min časové značky celého roku, volitelně bez vybraných indexů."""
    casy = []
    t = datetime(rok, 1, 1)
    i = 0
    while t < datetime(rok + 1, 1, 1):
        if i not in vynech_indexy:
            casy.append(t)
        t += timedelta(minutes=15)
        i += 1
    return casy


class TestIntervalMedian:
    def test_ciste_15min_data(self):
        assert _interval_h_z_profilu(rok_15min()) == pytest.approx(0.25)

    def test_hodinova_data(self):
        casy = [datetime(2025, 1, 1) + timedelta(hours=i) for i in range(8760)]
        assert _interval_h_z_profilu(casy) == pytest.approx(1.0)

    def test_chybejici_druhy_zaznam_neposune_interval(self):
        # Dřív: casy[1] − casy[0] = 0,5 h → veškerá energie ×2.
        casy = rok_15min(vynech_indexy={1})
        assert _interval_h_z_profilu(casy) == pytest.approx(0.25)

    def test_dira_na_zacatku_neposune_interval(self):
        casy = rok_15min(vynech_indexy=set(range(1, 20)))
        assert _interval_h_z_profilu(casy) == pytest.approx(0.25)

    def test_prazdny_a_jednoprvkovy_profil_maji_fallback(self):
        assert _interval_h_z_profilu([]) == pytest.approx(0.25)
        assert _interval_h_z_profilu([datetime(2025, 1, 1)]) == pytest.approx(0.25)

    def test_neserazeny_profil_nezpusobi_negativni_interval(self):
        casy = [datetime(2025, 1, 1, 1), datetime(2025, 1, 1, 0), datetime(2025, 1, 1, 2)]
        assert _interval_h_z_profilu(casy) > 0


class TestMrizkaProfilu:
    def test_ciste_data_nemaji_odchylky(self):
        casy = rok_15min()
        assert _mrizka_profilu_ok(casy, 0.25) == pytest.approx(0.0)

    def test_dira_se_projevi_v_podilu(self):
        casy = rok_15min(vynech_indexy={5, 500, 5000})
        podil = _mrizka_profilu_ok(casy, 0.25)
        assert 0 < podil < 0.01

    def test_prazdny_profil_nepada(self):
        assert _mrizka_profilu_ok([], 0.25) == 0.0
        assert _mrizka_profilu_ok(rok_15min(), 0.0) == 0.0


class TestZaporneHodnoty:
    """Zákazník s vlastní FVE (nebo export se saldem) má v profilu přetoky.

    Záporný odběr dával zápornou samospotřebu, tedy fyzikální nesmysl, který
    tiše podstřeloval úsporu klienta – energetická bilance přitom formálně
    dál platila, takže si toho nešlo všimnout.
    """

    def test_par_zapornych_hodnot_se_srovna_na_nulu_s_upozornenim(self):
        casy = rok_15min()
        hodnoty = [100.0] * len(casy)
        hodnoty[10] = -50.0
        hodnoty[20] = -30.0
        _, ocistene, upozorneni = _zvaliduj_a_orizni_profil(casy, hodnoty, 0.25)
        assert min(ocistene) == 0.0
        assert ocistene[10] == 0.0 and ocistene[20] == 0.0
        assert any("záporných" in u for u in upozorneni)

    def test_mnoho_zapornych_hodnot_je_tvrda_chyba(self):
        # Vypadá to, že se načetlo saldo místo odběru → radši nic nepočítat.
        casy = rok_15min()
        hodnoty = [100.0] * len(casy)
        for i in range(0, len(hodnoty), 20):  # 5 % záporných
            hodnoty[i] = -80.0
        with pytest.raises(HTTPException) as chyba:
            _zvaliduj_a_orizni_profil(casy, hodnoty, 0.25)
        assert chyba.value.status_code == 422
        assert "saldo" in chyba.value.detail

    def test_kladny_profil_projde_bez_upozorneni_na_zaporne(self):
        casy = rok_15min()
        hodnoty = [100.0] * len(casy)
        _, ocistene, upozorneni = _zvaliduj_a_orizni_profil(casy, hodnoty, 0.25)
        assert ocistene == hodnoty
        assert not any("záporných" in u for u in upozorneni)


class TestValidaceIndexu:
    """Indexy se zadávají jako zlomek (0,03 = 3 %/rok).

    Zadání „3“ znamenalo 300 %/rok: po 15 letech cena PPA 590 mld. Kč/MWh a
    kumulovaná „úspora“ klienta −163 bilionů Kč – a nabídka to bez mrknutí
    vytiskla (revize 26. 7. 2026).
    """

    def _vstup(self, **zmeny):
        zaklad = dict(
            cena_ppa_kc_mwh=2200.0, cena_silova_kc_mwh=3500.0, delka_kontraktu_roky=15
        )
        zaklad.update(zmeny)
        return PpaVstup(**zaklad)

    @pytest.mark.parametrize("index", [0.03, 0.0, -0.02, 0.5, -0.5, None])
    def test_rozumny_index_projde(self, index):
        _zvaliduj_indexy(self._vstup(index_ppa_rocni=index))

    @pytest.mark.parametrize("index", [3.0, 100.0, -3.0, 0.51])
    def test_index_v_procentech_je_odmitnut(self, index):
        with pytest.raises(HTTPException) as chyba:
            _zvaliduj_indexy(self._vstup(index_ppa_rocni=index))
        assert chyba.value.status_code == 422
        assert "zlomek" in chyba.value.detail

    @pytest.mark.parametrize(
        "pole,popis",
        [
            ("index_ppa_rocni", "Index PPA"),
            ("index_dodavatel_rocni", "Index ceny dodavatele"),
            ("degradace_rocni", "Roční degradace panelů"),
            ("degradace_rok1", "Degradace prvního roku (LID)"),
        ],
    )
    def test_hlaska_rekne_ktere_pole_je_spatne(self, pole, popis):
        with pytest.raises(HTTPException) as chyba:
            _zvaliduj_indexy(self._vstup(**{pole: 5.0}))
        assert popis in chyba.value.detail
