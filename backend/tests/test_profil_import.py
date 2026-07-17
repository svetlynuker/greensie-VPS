# -*- coding: utf-8 -*-
"""Testy importu profilu – deduplikace časů (audit SP-2)."""

from datetime import datetime

from app.nabidkovac.profil_import import deduplikuj_casy


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
