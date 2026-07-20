# -*- coding: utf-8 -*-
"""Testy kontroly pokrytí profilu (audit SP-1, bughunt testy T2/T3)."""

from datetime import datetime, timedelta

from app.nabidkovac import profil_pokryti as pp

INTERVAL = 0.25


def rok_casy(rok=2025, mesice=None):
    """15min časové značky pro daný rok (volitelně jen vybrané měsíce)."""
    out = []
    t = datetime(rok, 1, 1)
    konec = datetime(rok + 1, 1, 1)
    while t < konec:
        if mesice is None or t.month in mesice:
            out.append(t)
        t += timedelta(minutes=15)
    return out


def test_cely_rok_projde():
    casy = rok_casy()
    ok, duvod = pp.zkontroluj_pokryti(casy, INTERVAL)
    assert ok, duvod


def test_pulrocni_profil_neprojde_a_rekne_proc():
    casy = rok_casy(mesice={1, 2, 3, 4, 5, 6})
    ok, duvod = pp.zkontroluj_pokryti(casy, INTERVAL)
    assert not ok
    assert "dní" in duvod  # hlásí krátké pokrytí, ne jen obecnou chybu


def test_prazdny_profil_neprojde():
    ok, duvod = pp.zkontroluj_pokryti([], INTERVAL)
    assert not ok


def test_diry_nad_2_procenta_neprojdou():
    casy = rok_casy()
    proridle = [c for i, c in enumerate(casy) if i % 33 != 0]  # ~3 % děr
    ok, duvod = pp.zkontroluj_pokryti(proridle, INTERVAL)
    assert not ok
    assert "interval" in duvod


def test_diry_do_2_procent_projdou():
    casy = rok_casy()
    proridle = [c for i, c in enumerate(casy) if i % 100 != 0]  # 1 % děr
    ok, duvod = pp.zkontroluj_pokryti(proridle, INTERVAL)
    assert ok, duvod


def test_13mesicni_profil_se_orizne_na_poslednich_12_mesicu():
    # Bughunt T3: leden 2025 – leden 2026 rozpouštěl lednovou energii do 62 dnů.
    casy = rok_casy(2025) + rok_casy(2026, mesice={1})
    hodnoty = [1.0] * len(casy)
    casy2, hodnoty2, orezano = pp.orizni_na_posledni_rok(casy, hodnoty, INTERVAL)
    assert orezano is True
    assert min(casy2) == datetime(2025, 2, 1)  # leden 2025 vypadl
    assert max(casy2).year == 2026 and max(casy2).month == 1
    assert len({(c.year, c.month) for c in casy2}) == 12
    assert len(hodnoty2) == len(casy2)
    ok, duvod = pp.zkontroluj_pokryti(casy2, INTERVAL)
    assert ok, duvod


def test_dvoulety_profil_se_orizne_na_posledni_rok():
    casy = rok_casy(2024) + rok_casy(2025)
    hodnoty = list(range(len(casy)))
    casy2, hodnoty2, orezano = pp.orizni_na_posledni_rok(casy, hodnoty, INTERVAL)
    assert orezano is True
    assert min(casy2).year == 2025
    # hodnoty zůstávají spárované s časy
    assert hodnoty2[0] == len(rok_casy(2024))


def test_rocni_profil_se_neorezava():
    casy = rok_casy()
    hodnoty = [1.0] * len(casy)
    casy2, hodnoty2, orezano = pp.orizni_na_posledni_rok(casy, hodnoty, INTERVAL)
    assert orezano is False
    assert casy2 is casy and hodnoty2 is hodnoty


def _casy_od_do(zacatek, konec):
    """15min časové značky v intervalu [zacatek, konec)."""
    out = []
    t = zacatek
    while t < konec:
        out.append(t)
        t += timedelta(minutes=15)
    return out


def test_prekryvajici_se_okrajove_mesice_neprojdou():
    # Výchozí (PPA) režim. 12,2 měsíce: 15. 7. 2025 – 20. 7. 2026 (dva neúplné
    # července) – nejde oříznout na 12 celých měsíců (celých je jen 11); PPA
    # energii sčítá, takže překryv musí zůstat zakázaný.
    casy = _casy_od_do(datetime(2025, 7, 15), datetime(2026, 7, 20))
    hodnoty = [1.0] * len(casy)
    casy2, _, orezano = pp.orizni_na_posledni_rok(casy, hodnoty, INTERVAL)
    assert orezano is False
    ok, duvod = pp.zkontroluj_pokryti(casy2, INTERVAL)
    assert not ok
    assert "13" in duvod or "měsíc" in duvod


def test_peak_shaving_prekryvajici_okraje_se_orizne_a_projde():
    # Stejný „rok a kousek“ s neúplnými okraji: pro peak shaving se ořízne na
    # klouzavý rok a projde (dva neúplné července se sešijí do jednoho měsíce).
    casy = _casy_od_do(datetime(2025, 7, 15), datetime(2026, 7, 20))
    hodnoty = [1.0] * len(casy)
    casy2, hodnoty2, orezano = pp.orizni_na_posledni_rok(
        casy, hodnoty, INTERVAL, pro_peak_shaving=True
    )
    assert orezano is True
    assert len(hodnoty2) == len(casy2)
    assert {c.month for c in casy2} == set(range(1, 13))
    ok, duvod = pp.zkontroluj_pokryti(casy2, INTERVAL, pro_peak_shaving=True)
    assert ok, duvod


def test_peak_shaving_dvoulety_projde():
    # 24 celých měsíců: standardní větev vezme posledních 12 celých (rok 2025).
    casy = rok_casy(2024) + rok_casy(2025)
    hodnoty = [1.0] * len(casy)
    casy2, _, orezano = pp.orizni_na_posledni_rok(
        casy, hodnoty, INTERVAL, pro_peak_shaving=True
    )
    assert orezano is True
    assert min(casy2).year == 2025
    ok, duvod = pp.zkontroluj_pokryti(casy2, INTERVAL, pro_peak_shaving=True)
    assert ok, duvod


def test_peak_shaving_cely_rok_projde():
    ok, duvod = pp.zkontroluj_pokryti(rok_casy(), INTERVAL, pro_peak_shaving=True)
    assert ok, duvod


def test_peak_shaving_pulrok_neprojde():
    # Chybí druhá polovina roku – peak shaving potřebuje všech 12 měsíců.
    casy = rok_casy(mesice={1, 2, 3, 4, 5, 6})
    ok, duvod = pp.zkontroluj_pokryti(casy, INTERVAL, pro_peak_shaving=True)
    assert not ok
    assert "chybí" in duvod


def test_peak_shaving_skoro_prazdny_mesic_neprojde():
    # Červenec skoro bez dat (jen 1. 7.) – nespolehlivé měsíční maximum.
    casy = [c for c in rok_casy() if not (c.month == 7 and c.day > 1)]
    ok, duvod = pp.zkontroluj_pokryti(casy, INTERVAL, pro_peak_shaving=True)
    assert not ok
    assert "7" in duvod
