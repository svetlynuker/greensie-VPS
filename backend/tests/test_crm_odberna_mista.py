"""Odběrná místa (CRM-46) – validace a překlad do vstupů výpočtu.

Testuje se to, co jde bez databáze: normalizace EAN, kontrola distributora
a hladiny proti seznamům nabídkovače a převod místa na parametry, které si
z něj předvyplní peak shaving a PPA. Zbytek (duplicita EAN v rámci zákazníka,
viditelnost přes zákazníka) žije nad Postgresem – ARRAY/JSONB sloupce CRM
v SQLite nefungují, takže se to sem nedá vejít bez celé testovací DB.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.crm import odberna_mista as om


def _misto(**kwargs):
    """Odběrné místo jako holý objekt – funkce níž na ORM instanci nestojí."""
    zaklad = dict(
        nazev="Hala Kolín",
        ean="",
        adresa_ulice="",
        adresa_mesto="",
        adresa_psc="",
        gps_lat=None,
        gps_lng=None,
        distributor="",
        napetova_hladina="",
        rezervovana_kapacita_kw=None,
        rezervovany_prikon_kw=None,
    )
    zaklad.update(kwargs)
    return SimpleNamespace(**zaklad)


class TestEan:
    def test_prazdny_projde(self):
        """Lead, u kterého se teprve zjišťuje, kde odebírá, musí jít založit."""
        assert om.normalizuj_ean("") == ""
        assert om.normalizuj_ean(None) == ""
        assert om.normalizuj_ean("   ") == ""

    def test_mezery_a_spojovniky_se_odstrani(self):
        """Z portálu distributora se EAN kopíruje po skupinách."""
        assert om.normalizuj_ean("859 182 400 100 123 456") == "859182400100123456"
        assert om.normalizuj_ean("859-182-400-100-123-456") == "859182400100123456"

    def test_spatna_delka_je_chyba(self):
        with pytest.raises(HTTPException) as e:
            om.normalizuj_ean("85918240010012")
        assert e.value.status_code == 422
        assert "18" in e.value.detail

    def test_necislice_je_chyba(self):
        with pytest.raises(HTTPException):
            om.normalizuj_ean("85918240010012345X")

    def test_zahranicni_prefix_projde(self):
        """Prefix se nevaliduje schválně – appka nemá důvod odmítnout cizí EAN."""
        assert om.normalizuj_ean("123456789012345678") == "123456789012345678"


class TestDistribuce:
    def test_prazdne_projde(self):
        """Místo se zakládá i bez faktury, kdy distributor ještě není známý."""
        assert om.over_distribuci("", "") == ("", "")

    def test_normalizuje_na_mala(self):
        assert om.over_distribuci("CEZ", "VN") == ("cez", "vn")

    def test_neznamy_distributor(self):
        with pytest.raises(HTTPException) as e:
            om.over_distribuci("eon", "vn")
        assert e.value.status_code == 422

    def test_neznama_hladina(self):
        """NN peak shaving neumí – kdyby prošlo, chyba by vyskočila až u výpočtu."""
        with pytest.raises(HTTPException):
            om.over_distribuci("cez", "nn")


class TestParametryProVypocet:
    def test_prazdne_misto_neposila_nic(self):
        """Nevyplněné hodnoty se neposílají, aby nepřepsaly to, co OZ zadal ručně."""
        assert om.parametry_pro_vypocet(_misto()) == {}

    def test_posle_vyplnene(self):
        p = om.parametry_pro_vypocet(
            _misto(
                distributor="egd",
                napetova_hladina="vn",
                rezervovana_kapacita_kw=250,
                rezervovany_prikon_kw=300,
            )
        )
        assert p == {
            "distributor": "egd",
            "napetova_hladina": "vn",
            "rezervovana_kapacita_kw": 250.0,
            "rezervovany_prikon_kw": 300.0,
        }

    def test_nula_se_posila(self):
        """Nula je platná hodnota (odpojené místo), jen None znamená „nevíme“."""
        p = om.parametry_pro_vypocet(_misto(rezervovana_kapacita_kw=0))
        assert p["rezervovana_kapacita_kw"] == 0.0

    def test_gps_jen_kdyz_je_oboji(self):
        """Půlka souřadnice je horší než žádná – PPA by počítal výrobu jinde."""
        assert om.parametry_pro_vypocet(_misto(gps_lat=50.02)) == {}
        p = om.parametry_pro_vypocet(_misto(gps_lat=50.02, gps_lng=15.2))
        assert p == {"gps_lat": 50.02, "gps_lng": 15.2}


class TestAdresaTextem:
    def test_slozi_ulici_psc_mesto(self):
        m = _misto(adresa_ulice="Průmyslová 12", adresa_psc="280 02", adresa_mesto="Kolín")
        assert om.adresa_textem(m) == "Průmyslová 12, 280 02 Kolín"

    def test_jen_mesto(self):
        assert om.adresa_textem(_misto(adresa_mesto="Kolín")) == "Kolín"

    def test_prazdna(self):
        assert om.adresa_textem(_misto()) == ""


def test_entity_mist_pokryva_obe_obrazovky():
    """Kdyby ze seznamu vypadl „op“, karta případu by přišla o celé pole."""
    assert set(om.ENTITY_MIST) == {"zakaznik", "op"}
