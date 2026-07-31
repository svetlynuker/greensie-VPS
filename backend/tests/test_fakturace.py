"""Testy fakturace CRM objednávky (CRM-09).

Nejdůležitější je rozdělení ceny do splátek: součet splátek se MUSÍ rovnat
ceně objednávky na haléř, jinak by v účetnictví zůstávaly chybějící koruny.
"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.crm import fakturace


def _f(**kw):
    zaklad = dict(
        id=1, poradi=1, nazev="", stav="potreba_vystavit", castka=None,
        podil_procent=None, termin=None,
    )
    zaklad.update(kw)
    return SimpleNamespace(**zaklad)


# ---- rozdělení ceny do splátek ----
def test_pulka_pulka():
    assert fakturace.rozdel_castku(2_400_000, [50, 50]) == [
        Decimal("1200000.00"),
        Decimal("1200000.00"),
    ]


def test_tretiny_sedi_na_haler():
    """Klasická past: 3× 33,33 % z milionu chybí desetikoruna."""
    castky = fakturace.rozdel_castku(1_000_000, [33.33, 33.33, 33.34])
    assert sum(castky) == Decimal("1000000")


def test_posledni_splatka_bere_zbytek():
    castky = fakturace.rozdel_castku(Decimal("100.01"), [30, 40, 30])
    assert sum(castky) == Decimal("100.01")
    assert castky[-1] != castky[0]  # zbytek sedl na poslední


# ---- po termínu ----
def test_po_terminu_i_nevystavena():
    """Faktura, kterou nikdo nevystavil a termín utekl, JE problém."""
    vcera = date.today() - timedelta(days=1)
    assert fakturace.po_terminu(_f(termin=vcera, stav="potreba_vystavit"))
    assert fakturace.po_terminu(_f(termin=vcera, stav="vystaveno"))


def test_zaplacena_a_nefakturovana_nikdy_nejsou_po_terminu():
    vcera = date.today() - timedelta(days=1)
    assert not fakturace.po_terminu(_f(termin=vcera, stav="zaplaceno"))
    assert not fakturace.po_terminu(_f(termin=vcera, stav="nefakturuje"))
    assert not fakturace.po_terminu(_f(termin=None))


# ---- souhrn ----
def test_souhrn_vyfakturovano_a_zaplaceno():
    faktury = [
        _f(id=1, castka=Decimal("300000"), stav="zaplaceno"),
        _f(id=2, castka=Decimal("400000"), stav="vystaveno"),
        _f(id=3, castka=Decimal("300000"), stav="potreba_vystavit"),
    ]
    s = fakturace.souhrn(faktury, Decimal("1000000"))
    assert s["pocet"] == 3
    assert s["vyfakturovano_kc"] == 700000.0
    assert s["zaplaceno_kc"] == 300000.0
    assert s["zbyva_fakturovat_kc"] == 0.0
    assert s["nesedi_soucet"] is False


def test_souhrn_pozna_ze_soucet_nesedi():
    faktury = [_f(castka=Decimal("500000"), stav="potreba_vystavit")]
    s = fakturace.souhrn(faktury, Decimal("1000000"))
    assert s["zbyva_fakturovat_kc"] == 500000.0
    assert s["nesedi_soucet"] is True


def test_nefakturuje_se_do_souctu_nepocita():
    faktury = [
        _f(id=1, castka=Decimal("1000000"), stav="zaplaceno"),
        _f(id=2, castka=Decimal("50000"), stav="nefakturuje"),
    ]
    s = fakturace.souhrn(faktury, Decimal("1000000"))
    assert s["pocet"] == 1
    assert s["zbyva_fakturovat_kc"] == 0.0
    assert s["nesedi_soucet"] is False


def test_bez_ceny_objednavky_se_zbytek_nehada():
    s = fakturace.souhrn([_f(castka=Decimal("100"))], None)
    assert s["zbyva_fakturovat_kc"] is None
    assert s["nesedi_soucet"] is False


def test_korunova_tolerance():
    """Rozdíl do koruny (zaokrouhlení podílů) se za nesoulad nepovažuje."""
    faktury = [_f(castka=Decimal("999999.50"), stav="potreba_vystavit")]
    assert fakturace.souhrn(faktury, Decimal("1000000"))["nesedi_soucet"] is False


# ---- přepočet podle podílů ----
def test_prepocet_sahne_jen_na_nevystavene():
    faktury = [
        _f(id=1, stav="vystaveno", podil_procent=Decimal("30"), castka=Decimal("300000")),
        _f(id=2, stav="potreba_vystavit", podil_procent=Decimal("70"), castka=Decimal("700000")),
    ]
    upraveno = fakturace.prepocti_podle_podilu(faktury, Decimal("2000000"))
    assert upraveno == 1
    assert faktury[0].castka == Decimal("300000")  # vystavená se nemění
    assert faktury[1].castka == Decimal("1400000")


def test_prepocet_bez_podilu_nedela_nic():
    faktury = [_f(stav="potreba_vystavit", podil_procent=None, castka=Decimal("100"))]
    assert fakturace.prepocti_podle_podilu(faktury, Decimal("999")) == 0
    assert faktury[0].castka == Decimal("100")


def test_sablony_maji_sto_procent():
    """Každá předvolba musí dát dohromady 100 % – jinak by zakázka nebyla
    pokrytá fakturami a nikdo by si toho nevšiml."""
    for sablona in fakturace.sablony_pro_frontend():
        soucet = sum(s["podil_procent"] for s in sablona["splatky"])
        assert soucet == 100, f"{sablona['klic']} má {soucet} %"


def test_prepocet_vsech_sedi_na_haler():
    """Když se přepočítávají všechny splátky 100 %, součet musí sednout."""
    faktury = [
        _f(id=1, stav="potreba_vystavit", podil_procent=Decimal("33.33")),
        _f(id=2, stav="potreba_vystavit", podil_procent=Decimal("33.33")),
        _f(id=3, stav="potreba_vystavit", podil_procent=Decimal("33.34")),
    ]
    fakturace.prepocti_podle_podilu(faktury, Decimal("1000000"))
    assert sum(f.castka for f in faktury) == Decimal("1000000")
