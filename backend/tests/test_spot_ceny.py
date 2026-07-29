# -*- coding: utf-8 -*-
"""Testy práce se spotovými cenami (`app/nabidkovac/spot_ceny.py`).

Testuje se to, co nezávisí na databázi: rozpad obchodních intervalů na
čtvrthodiny (do 30. 9. 2025 byly ceny hodinové) a napárování cen na profil
odběru, který bývá z jiného roku.
"""

import csv
import datetime
import gzip

import pytest

from app.nabidkovac import spot_ceny


def _utc(rok, mesic, den, hodina=0, minuta=0):
    return datetime.datetime(rok, mesic, den, hodina, minuta, tzinfo=datetime.timezone.utc)


def _rada_hodinova(rok=2025, dnu=7, cena_zaklad=2000.0):
    """Řada hodinových cen: cena = základ + hodina × 100 (poznat, co kam sedlo)."""
    radky = []
    zacatek = _utc(rok, 1, 1) - datetime.timedelta(hours=1)  # 1. 1. 00:00 lokálně
    for den in range(dnu):
        for hodina in range(24):
            radky.append(
                (zacatek + datetime.timedelta(days=den, hours=hodina), 60, cena_zaklad + hodina * 100)
            )
    return spot_ceny._rada_z_radku(radky, rok, spot_ceny.TRH_DAM_CZ)


class TestRozpadIntervalu:
    """Hodinová cena se replikuje na čtvrthodiny, 15min zůstává."""

    def test_hodinova_cena_da_ctyri_ctvrthodiny(self):
        rada = spot_ceny._rada_z_radku(
            [(_utc(2025, 6, 15, 10, 0), 60, 1500.0)], 2025, spot_ceny.TRH_DAM_CZ
        )
        den = rada.podle_dne[datetime.date(2025, 6, 15)]
        # 10:00 UTC = 12:00 v Praze (letní čas).
        assert den[(12, 0)] == 1500.0
        assert den[(12, 15)] == 1500.0
        assert den[(12, 30)] == 1500.0
        assert den[(12, 45)] == 1500.0
        assert len(den) == 4

    def test_ctvrthodinova_cena_zustava_jedna(self):
        rada = spot_ceny._rada_z_radku(
            [(_utc(2025, 11, 3, 8, 15), 15, 2500.0)], 2025, spot_ceny.TRH_DAM_CZ
        )
        den = rada.podle_dne[datetime.date(2025, 11, 3)]
        assert den == {(9, 15): 2500.0}  # zimní čas = UTC+1

    def test_zimni_a_letni_cas_se_lisi_o_hodinu(self):
        leto = spot_ceny._rada_z_radku(
            [(_utc(2025, 7, 1, 12, 0), 60, 1000.0)], 2025, spot_ceny.TRH_DAM_CZ
        )
        zima = spot_ceny._rada_z_radku(
            [(_utc(2025, 1, 15, 12, 0), 60, 1000.0)], 2025, spot_ceny.TRH_DAM_CZ
        )
        assert (14, 0) in leto.podle_dne[datetime.date(2025, 7, 1)]
        assert (13, 0) in zima.podle_dne[datetime.date(2025, 1, 15)]

    def test_ceny_jineho_roku_se_zahodi(self):
        """Okrajové intervaly (posun zóny) nesmí zaplevelit sousední rok."""
        rada = spot_ceny._rada_z_radku(
            [(_utc(2024, 12, 31, 23, 0), 60, 999.0), (_utc(2025, 6, 1, 10, 0), 60, 1.0)],
            2025,
            spot_ceny.TRH_DAM_CZ,
        )
        # 31. 12. 2024 23:00 UTC = 1. 1. 2025 00:00 v Praze → patří do 2025.
        assert datetime.date(2025, 1, 1) in rada.podle_dne
        assert all(d.year == 2025 for d in rada.podle_dne)

    def test_index_dnu_dle_typu(self):
        rada = _rada_hodinova(dnu=14)
        # 1. 1. 2025 byla středa → ve dnech 1–14 jsou dvě středy.
        stredy = rada.dny_dle_typu[(1, 2)]
        assert stredy == [datetime.date(2025, 1, 1), datetime.date(2025, 1, 8)]

    def test_pocet_intervalu(self):
        rada = _rada_hodinova(dnu=2)
        assert rada.pocet_intervalu == 2 * 24 * 4


class TestOdpovidajiciDen:
    """Profil z jiného roku se páruje podle typu dne, ne podle data."""

    def test_stejny_den_v_tydnu_ma_prednost(self):
        rada = _rada_hodinova(dnu=28)
        # 15. 1. 2026 je čtvrtek; v lednu 2025 jsou čtvrtky 2., 9., 16., 23.
        zdroj = spot_ceny._odpovidajici_den(datetime.date(2026, 1, 15), rada)
        assert zdroj.weekday() == 3
        assert zdroj == datetime.date(2025, 1, 16)  # nejblíž 15. dni měsíce

    def test_vikend_dostane_vikend(self):
        rada = _rada_hodinova(dnu=28)
        # 4. 1. 2026 je nedělní den.
        zdroj = spot_ceny._odpovidajici_den(datetime.date(2026, 1, 4), rada)
        assert zdroj.weekday() == 6

    def test_chybejici_mesic_padne_na_nejblizsi_den(self):
        rada = _rada_hodinova(dnu=7)  # jen první lednový týden
        zdroj = spot_ceny._odpovidajici_den(datetime.date(2026, 8, 15), rada)
        assert zdroj is not None
        assert zdroj.month == 1


class TestCenyProCasy:
    """Napárování řady cen na časy profilu."""

    def _casy(self, rok, mesic, den, pocet=96):
        zacatek = datetime.datetime(rok, mesic, den)
        return [zacatek + datetime.timedelta(minutes=15 * i) for i in range(pocet)]

    def test_stejny_rok_sedne_jeden_k_jednomu(self):
        rada = _rada_hodinova(dnu=7)
        casy = self._casy(2025, 1, 2)
        ceny, info = spot_ceny.ceny_pro_casy(casy, rada)
        assert info["stejny_rok"] is True
        assert info["chybejici_intervaly"] == 0
        assert info["parovano_dnu"] == 0
        # Cena je 2000 + hodina × 100 → v 00:00 lokálně = 2000.
        assert ceny[0] == pytest.approx(2000.0)
        assert ceny[4] == pytest.approx(2100.0)  # 01:00

    def test_jiny_rok_se_paruje_podle_typu_dne(self):
        rada = _rada_hodinova(dnu=28)
        casy = self._casy(2026, 1, 15)
        ceny, info = spot_ceny.ceny_pro_casy(casy, rada)
        assert info["stejny_rok"] is False
        assert info["parovano_dnu"] == 1
        assert info["chybejici_intervaly"] == 0
        assert len(ceny) == len(casy)
        assert ceny[0] == pytest.approx(2000.0)

    def test_kazdy_cas_dostane_cenu(self):
        rada = _rada_hodinova(dnu=28)
        casy = self._casy(2026, 1, 15, pocet=96 * 3)
        ceny, info = spot_ceny.ceny_pro_casy(casy, rada)
        assert len(ceny) == 96 * 3
        assert all(c > 0 for c in ceny)
        assert info["parovano_dnu"] == 3

    def test_prazdna_rada_hlasi_chybejici_intervaly(self):
        prazdna = spot_ceny._rada_z_radku([], 2025, spot_ceny.TRH_DAM_CZ)
        casy = self._casy(2025, 1, 2, pocet=4)
        ceny, info = spot_ceny.ceny_pro_casy(casy, prazdna)
        assert ceny == [0.0, 0.0, 0.0, 0.0]
        assert info["chybejici_intervaly"] == 4

    def test_chybejici_ctvrthodina_vezme_nejblizsi(self):
        # Den s jedinou cenou v 10:00 – profil chce 15:00.
        rada = spot_ceny._rada_z_radku(
            [(_utc(2025, 6, 15, 8, 0), 15, 1234.0)], 2025, spot_ceny.TRH_DAM_CZ
        )
        casy = [datetime.datetime(2025, 6, 15, 15, 0)]
        ceny, info = spot_ceny.ceny_pro_casy(casy, rada)
        assert ceny == [1234.0]
        assert info["chybejici_intervaly"] == 0

    def test_prazdny_seznam_casu(self):
        rada = _rada_hodinova()
        ceny, info = spot_ceny.ceny_pro_casy([], rada)
        assert ceny == []
        assert info["stejny_rok"] is False


class TestDatoveSoubory:
    """Přiložená data pro seed bez internetu."""

    def test_rok_2025_je_prilozeny(self):
        soubory = spot_ceny.datove_soubory()
        assert any(s.name == "spot_dam_cz_2025.csv.gz" for s in soubory)

    def test_rok_ze_jmena(self):
        soubory = {s.name: spot_ceny._rok_ze_jmena(s) for s in spot_ceny.datove_soubory()}
        assert soubory["spot_dam_cz_2025.csv.gz"] == 2025

    def test_data_2025_maji_ocekavany_tvar(self):
        cesta = next(
            s for s in spot_ceny.datove_soubory() if s.name == "spot_dam_cz_2025.csv.gz"
        )
        with gzip.open(cesta, "rt", encoding="utf-8", newline="") as f:
            radky = list(csv.DictReader(f, delimiter=";"))
        assert len(radky) > 15_000
        assert set(radky[0]) == {"unix_s", "interval_min", "eur_mwh", "kc_mwh"}
        # Denní trh přešel na 15minutové intervaly 1. 10. 2025 – v datech tedy
        # musí být obojí granularita.
        intervaly = {r["interval_min"] for r in radky}
        assert intervaly == {"15", "60"}
        # Kurz ČNB 2025 se držel kolem 25 Kč/EUR.
        pomery = [
            float(r["kc_mwh"]) / float(r["eur_mwh"])
            for r in radky[:200]
            if abs(float(r["eur_mwh"])) > 1
        ]
        assert 23.0 < sum(pomery) / len(pomery) < 26.0

    def test_data_2025_pokryvaji_cely_rok(self):
        cesta = next(
            s for s in spot_ceny.datove_soubory() if s.name == "spot_dam_cz_2025.csv.gz"
        )
        with gzip.open(cesta, "rt", encoding="utf-8", newline="") as f:
            radky = list(csv.DictReader(f, delimiter=";"))
        rada = spot_ceny._rada_z_radku(
            [
                (
                    datetime.datetime.fromtimestamp(int(r["unix_s"]), datetime.timezone.utc),
                    int(r["interval_min"]),
                    float(r["kc_mwh"]),
                )
                for r in radky
            ],
            2025,
            spot_ceny.TRH_DAM_CZ,
        )
        # 365 dní × 96 čtvrthodin = 35 040 mínus opakovaná hodina podzimního
        # přechodu času, kterou mapování podle času dne sloučí (viz
        # `_rada_z_radku`).
        assert rada.pocet_intervalu == 35_036
        assert len(rada.podle_dne) == 365
