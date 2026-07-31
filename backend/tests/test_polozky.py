"""Testy rozpisu položek nabídky a objednávky (CRM-08).

Hlídají tři věci, na kterých stojí důvěra v čísla:
1. součet položek se rovná tomu, co appka ukáže (zaokrouhlení po řádcích),
2. sleva se počítá z jednotkové ceny, ne z řádku,
3. nákupní ceny a marže se bez práva na katalog do odpovědi vůbec nedostanou.
"""

from decimal import Decimal
from types import SimpleNamespace

from app.nabidkovac import polozky


def _p(**kw):
    """Položka jako prostý objekt – výpočet nepotřebuje DB ani SQLAlchemy."""
    zaklad = dict(
        id=1, poradi=0, technologie_id=None, kod="", nazev="Panel", popis="",
        jednotka="ks", mnozstvi=1, cena_jednotkova=None, nakup_jednotkovy=None,
        sleva_procent=0, sazba_dph=None,
    )
    zaklad.update(kw)
    return SimpleNamespace(**zaklad)


def test_radek_bez_slevy():
    r = polozky.radek_soucty(_p(mnozstvi=10, cena_jednotkova=4500, sazba_dph=Decimal("0.21")))
    assert r["bez_dph"] == Decimal("45000.00")
    assert r["dph"] == Decimal("9450.00")
    assert r["s_dph"] == Decimal("54450.00")


def test_sleva_se_pocita_z_jednotkove_ceny():
    """10 ks po 4 500 Kč se slevou 10 % = 40 500, ne 45 000 − 10 %."""
    r = polozky.radek_soucty(_p(mnozstvi=10, cena_jednotkova=4500, sleva_procent=10))
    assert r["cena_po_sleve"] == Decimal("4050.00")
    assert r["bez_dph"] == Decimal("40500.00")


def test_zaokrouhleni_po_radcich_sedi_se_souctem():
    """Tři řádky s haléřovým zbytkem: součet musí sedět na to, co se ukáže."""
    radky = [_p(mnozstvi=3, cena_jednotkova=Decimal("33.335")) for _ in range(3)]
    s = polozky.souhrn(radky)
    # Každý řádek 100.005 → 100.01 (HALF_UP), tři řádky = 300.03.
    assert s["bez_dph"] == 300.03


def test_souhrn_scita_dph_i_marzi():
    radky = [
        _p(mnozstvi=2, cena_jednotkova=1000, nakup_jednotkovy=600, sazba_dph=Decimal("0.21")),
        _p(mnozstvi=1, cena_jednotkova=500, nakup_jednotkovy=500, sazba_dph=Decimal("0.12")),
    ]
    s = polozky.souhrn(radky)
    assert s["bez_dph"] == 2500.0
    assert s["dph"] == 480.0  # 420 + 60
    assert s["s_dph"] == 2980.0
    assert s["nakup_celkem"] == 1700.0
    assert s["marze_kc"] == 800.0
    assert s["marze_procent"] == 32.0  # 800 / 2500


def test_bez_nakupu_se_marze_nehlasi():
    """Bez nákupní ceny nesmí vyjít 100% marže – to by bylo klamavé číslo."""
    s = polozky.souhrn([_p(mnozstvi=1, cena_jednotkova=1000)])
    assert s["nakup_celkem"] is None
    assert s["marze_kc"] is None
    assert s["marze_procent"] is None


def test_prazdny_rozpis():
    s = polozky.souhrn([])
    assert s == {
        "pocet": 0, "bez_dph": 0.0, "dph": 0.0, "s_dph": 0.0,
        "nakup_celkem": None, "marze_kc": None, "marze_procent": None,
    }


def test_bez_prava_na_katalog_se_nakup_neposila():
    p = _p(mnozstvi=1, cena_jednotkova=1000, nakup_jednotkovy=600)
    bez = polozky.polozka_out(p, s_nakupem=False)
    assert "nakup_jednotkovy" not in bez and "marze_kc" not in bez
    s = polozky.polozka_out(p, s_nakupem=True)
    assert s["nakup_jednotkovy"] == 600.0 and s["marze_kc"] == 400.0


def test_napln_z_katalogu_bere_snapshot():
    tech = SimpleNamespace(
        id=7, kod="PAN-450", nazev="Panel 450 Wp", jednotka="ks",
        cena_kc=Decimal("4500"), cena_nakup_kc=Decimal("3100"), sazba_dph=Decimal("0.21"),
    )
    p = _p(nazev="")
    polozky.napln_z_katalogu(p, tech)
    assert (p.technologie_id, p.kod, p.nazev) == (7, "PAN-450", "Panel 450 Wp")
    assert p.cena_jednotkova == Decimal("4500")
    assert p.nakup_jednotkovy == Decimal("3100")


def test_kopie_do_objednavky_prenese_i_nakup():
    """Objednávka musí umět spočítat marži i po smazání nabídky."""
    zdroj = _p(mnozstvi=3, cena_jednotkova=100, nakup_jednotkovy=70, sleva_procent=5, poradi=2)
    kopie = polozky.kopiruj(zdroj, SimpleNamespace, objednavka_id=42)
    assert kopie.objednavka_id == 42
    assert kopie.nakup_jednotkovy == 70
    assert kopie.sleva_procent == 5
    assert kopie.poradi == 2
