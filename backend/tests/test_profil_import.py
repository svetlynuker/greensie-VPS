# -*- coding: utf-8 -*-
"""Testy importu profilu – detekce sloupců, hodina 24 a deduplikace časů (audit SP-2)."""

from datetime import datetime

import pytest

from app.nabidkovac.profil_import import _najdi_sloupce, _parse_datum, deduplikuj_casy


def test_pnd_hlavicka_bere_cinny_vykon():
    # PND export ČEZ/EG.D: Datum | Profil +A [kW] | Status | Datum | +Ri [kVAr] | ...
    hlavicka = ["Datum", "Profil +A [kW]", "Status", "Datum", "Profil +Ri [kVAr]", "Status"]
    assert _najdi_sloupce(hlavicka) == (0, 1)


def test_msv_sloupec_spotreba_v_kw_je_vykon():
    # „Spotřeba [kw]" je činný odběr v kW (ne kWh) – bereme ho.
    hlavicka = ["Datum", "Spotřeba [kw]", "Status", "Datum", "Přetoky [kw]", "Status"]
    assert _najdi_sloupce(hlavicka) == (0, 1)


def test_pre_bere_vykon_kw_ne_spotrebu_kwh():
    # PRE export: čas jako Počátek/Konec intervalu, vedle sebe spotřeba [kWh]
    # a výkon [kW]. Musíme vzít VÝKON (kW), ne energii (kWh), a jako čas
    # POČÁTEK intervalu (ne konec).
    hlavicka = [
        "Počátek intervalu",
        "Konec intervalu",
        "859182400300013392 - Činná - spotřeba [kWh]",
        "859182400300013392 - Činný - výkon [kW]",
        "859182400300013392 - Induktivní - spotřeba [kVAr]",
        "859182400300013392 - Kapacitní - spotřeba [kVAr]",
    ]
    assert _najdi_sloupce(hlavicka) == (0, 3)


def test_jalovina_kvar_se_nebere_jako_vykon():
    # Když je k dispozici jen jalovina [kVAr], sloupec výkonu není → chyba.
    with pytest.raises(ValueError):
        _najdi_sloupce(["Datum", "Profil +Ri [kVAr]", "Status"])


# --------------------------------------------------------- hodina 24 (PND konec dne)
def test_hodina_24_je_midnight_nasledujiciho_dne():
    # PND ukončuje den značkou „24:00:00". Bez převodu se řádek zahodí a
    # z profilu zmizí 365 intervalů ročně (~1 %) – viz NAB-26-0026.
    assert _parse_datum("30.06.2026 24:00:00") == datetime(2026, 7, 1, 0, 0)


def test_hodina_24_prelom_mesice_i_roku():
    assert _parse_datum("31.12.2025 24:00:00") == datetime(2026, 1, 1, 0, 0)
    assert _parse_datum("28.02.2026 24:00:00") == datetime(2026, 3, 1, 0, 0)
    # přestupný rok: 2024 má 29. února
    assert _parse_datum("28.02.2024 24:00:00") == datetime(2024, 2, 29, 0, 0)


def test_hodina_24_ve_vsech_podporovanych_formatech():
    ocekavano = datetime(2026, 7, 1, 0, 0)
    assert _parse_datum("30.06.2026 24:00:00") == ocekavano
    assert _parse_datum("30.06.2026 24:00") == ocekavano
    assert _parse_datum("2026-06-30 24:00:00") == ocekavano
    assert _parse_datum("2026-06-30 24:00") == ocekavano
    assert _parse_datum("2026-06-30T24:00:00") == ocekavano


def test_bezne_casy_zustavaji_nedotcene():
    # Regrese: převod hodiny 24 nesmí sáhnout na nic jiného.
    assert _parse_datum("01.07.2025 00:15:00") == datetime(2025, 7, 1, 0, 15)
    assert _parse_datum("01.07.2025 23:45:00") == datetime(2025, 7, 1, 23, 45)
    assert _parse_datum("2025-07-01 12:00:00") == datetime(2025, 7, 1, 12, 0)
    assert _parse_datum(datetime(2025, 7, 1, 6, 30)) == datetime(2025, 7, 1, 6, 30)


def test_cislo_24_v_datu_neposouva_den():
    # Den 24 v datu ani rok 2024 nesmí spustit posun – vzor míří jen na hodinu.
    assert _parse_datum("24.06.2026 10:15:00") == datetime(2026, 6, 24, 10, 15)
    assert _parse_datum("24.06.2024 24:00:00") == datetime(2024, 6, 25, 0, 0)
    assert _parse_datum("2024-06-24 08:00:00") == datetime(2024, 6, 24, 8, 0)


def test_nesmyslny_cas_zustava_neplatny():
    assert _parse_datum("30.06.2026 25:00:00") is None
    assert _parse_datum("") is None
    assert _parse_datum("naměřená data OK") is None


def test_hodina_24_s_nenulovymi_minutami():
    # PND to nedělá, ale kdyby: 24:15 dne D je 00:15 dne D+1.
    assert _parse_datum("30.06.2026 24:15:00") == datetime(2026, 7, 1, 0, 15)


def test_bez_duplicit_vraci_puvodni_body():
    body = [
        (datetime(2025, 1, 1, 0, 0), 10.0),
        (datetime(2025, 1, 1, 0, 15), 12.0),
    ]
    out, duplicit = deduplikuj_casy(body)
    assert out == body
    assert duplicit == 0


def test_dst_duplicitni_hodina_se_slouci_na_maximum():
    # Podzimní přechod času: 02:00–03:00 se v lokálním čase opakuje.
    t = datetime(2025, 10, 26, 2, 0)
    body = [
        (datetime(2025, 10, 26, 1, 45), 90.0),
        (t, 100.0),
        (datetime(2025, 10, 26, 2, 15), 95.0),
        (t, 110.0),  # druhý průchod stejnou lokální hodinou
        (datetime(2025, 10, 26, 2, 15), 80.0),
        (datetime(2025, 10, 26, 3, 0), 85.0),
    ]
    out, duplicit = deduplikuj_casy(body)
    assert duplicit == 2
    hodnoty = dict(out)
    assert hodnoty[t] == 110.0  # maximum, ne součet ani první výskyt
    assert hodnoty[datetime(2025, 10, 26, 2, 15)] == 95.0
    # pořadí prvního výskytu zůstává
    assert [c for c, _ in out] == [
        datetime(2025, 10, 26, 1, 45),
        t,
        datetime(2025, 10, 26, 2, 15),
        datetime(2025, 10, 26, 3, 0),
    ]


def test_dvakrat_vlozeny_rozsah_se_neseteze():
    # Dva identické bloky (omylem dvakrát vložený export) → jedna sada, kW se nesčítá.
    blok = [(datetime(2025, 1, 1, 0, 0), 10.0), (datetime(2025, 1, 1, 0, 15), 12.0)]
    out, duplicit = deduplikuj_casy(blok + blok)
    assert out == blok
    assert duplicit == 2
