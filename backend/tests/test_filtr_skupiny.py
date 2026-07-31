"""Uložené filtry: skupiny podmínek (CRM-26) a rozvržení sloupců (CRM-28).

Vyhodnocení filtru běží na klientu (`crmFiltry.js`), tady se hlídá jen to, co
je na backendu: že se nové pole **přenese beze ztráty** a že se do JSONB
nedostane, co tam nepatří.
"""

from app.crm.routes_realizace import _ciste_sloupce
from app.crm.schemas import PodminkaFiltru, UlozenyFiltrVstup


def test_podminka_bez_skupiny_zustava_platna():
    """Starší uložené filtry skupinu nemají – nesmí přestat jít načíst."""
    p = PodminkaFiltru(pole="stav", operator="je", hodnota="novy")
    assert p.skupina is None


def test_skupina_se_prenese():
    p = PodminkaFiltru(pole="stav", operator="je", hodnota="novy", skupina=2)
    assert p.model_dump()["skupina"] == 2


def test_filtr_prijme_rozvrzeni_sloupcu():
    v = UlozenyFiltrVstup(nazev="Test", sloupce={"skryte": ["ico"], "poradi": ["nazev", "ico"]})
    assert v.sloupce["skryte"] == ["ico"]


def test_ciste_sloupce_propusti_jen_znama_pole():
    out = _ciste_sloupce({"skryte": ["a"], "poradi": ["a", "b"], "smetí": {"x": 1}})
    assert out == {"skryte": ["a"], "poradi": ["a", "b"]}


def test_ciste_sloupce_zahodi_nesmysly():
    assert _ciste_sloupce(None) == {}
    assert _ciste_sloupce({"skryte": "ne-seznam"}) == {}
    # Prvky, které nejsou text ani číslo, se zahodí – do JSONB patří klíče.
    assert _ciste_sloupce({"skryte": ["a", {"x": 1}, 3]}) == {"skryte": ["a", "3"]}
