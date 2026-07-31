"""Vlastní (admin definovaná) pole – hlídání tří seznamů, které se musí shodovat.

Přidání entity je jednořádková změna na třech místech a zapomenout na jedno
z nich se nijak neprojeví při nasazení – projeví se to až prvním polem, které
tam admin založí:

  * chybí v `EntitaPole` (schemas)  → endpoint spadne na 500 při skládání odpovědi,
  * chybí v `MODELY` (vlastni_pole) → mazání pole tiše tvrdí „0 záznamů má hodnotu".

Tenhle test proto porovnává `ENTITY_VLASTNICH_POLI` s oběma. Přesně tak vznikla
chyba u odběrných míst (CRM-46): entita v seznamu byla, ve schématu ne.
"""

from typing import get_args

from app.crm.models import ENTITY_VLASTNICH_POLI, TYPY_VLASTNIHO_POLE
from app.crm.schemas import EntitaPole, TypPole, VlastniPoleOut
from app.crm.vlastni_pole import MODELY


def test_schema_zna_vsechny_entity():
    assert set(get_args(EntitaPole)) == set(ENTITY_VLASTNICH_POLI)


def test_schema_zna_vsechny_typy():
    assert set(get_args(TypPole)) == set(TYPY_VLASTNIHO_POLE)


def test_kazda_entita_ma_model_se_sloupcem_extra():
    assert set(MODELY) == set(ENTITY_VLASTNICH_POLI)
    for entita, model in MODELY.items():
        assert hasattr(model, "extra"), f"model entity '{entita}' nemá sloupec extra"


def test_odpoved_jde_slozit_pro_kazdou_entitu():
    """Regrese: dřív se `entita='om'` do odpovědi nevešla a endpoint padal."""
    for entita in ENTITY_VLASTNICH_POLI:
        out = VlastniPoleOut(id=1, entita=entita, klic="pole", nazev="Pole", typ="text")
        assert out.entita == entita


# ---- výpočtová pole a podmíněná viditelnost (CRM-34, CRM-33) -----------------
class _Pole:
    """Minimální náhrada CrmVlastniPole pro testy viditelnosti."""

    def __init__(self, zavislost_pole="", zavislost_hodnota=""):
        self.zavislost_pole = zavislost_pole
        self.zavislost_hodnota = zavislost_hodnota


def test_vzorec_spocita_rozdil():
    from app.crm.vlastni_pole import spocitej

    assert spocitej("cena - nakup", {"cena": 100, "nakup": 30}) == 70


def test_vzorec_deleni_nulou_konci_pomlckou():
    """Chyba ve výpočtu nesmí shodit zobrazení záznamu — vrací se None."""
    from app.crm.vlastni_pole import spocitej

    assert spocitej("a / b", {"a": 5, "b": 0}) is None


def test_vzorec_neumi_volat_funkce():
    """Ochrana: do vzorce se nesmí dostat nic než aritmetika."""
    from app.crm.vlastni_pole import spocitej

    assert spocitej("__import__('os').system('ls')", {}) is None
    assert spocitej("open('/etc/passwd')", {}) is None


def test_over_vzorec_odmitne_nezname_pole():
    import pytest
    from fastapi import HTTPException

    from app.crm.vlastni_pole import over_vzorec

    with pytest.raises(HTTPException):
        over_vzorec("cena - neexistuje", {"cena"})


def test_over_vzorec_pusti_platny():
    from app.crm.vlastni_pole import over_vzorec

    assert over_vzorec(" Cena - Nakup ", {"cena", "nakup"}) == "cena - nakup"


def test_viditelnost_bez_podminky_je_vzdy():
    from app.crm.vlastni_pole import viditelne

    assert viditelne(_Pole(), {}) is True


def test_viditelnost_podle_hodnoty():
    from app.crm.vlastni_pole import viditelne

    pole = _Pole("kategorie", "ppa")
    assert viditelne(pole, {"kategorie": "PPA"}) is True  # velikost písmen nerozhoduje
    assert viditelne(pole, {"kategorie": "prodej"}) is False
    assert viditelne(pole, {}) is False


def test_viditelnost_nad_seznamem_hodnot():
    """Kategorie případu je seznam — stačí, když podmínku splní jedna z nich."""
    from app.crm.vlastni_pole import viditelne

    pole = _Pole("kategorie", "ppa")
    assert viditelne(pole, {"kategorie": ["prodej", "PPA"]}) is True
    assert viditelne(pole, {"kategorie": ["prodej"]}) is False


def test_pole_se_sklada_na_jednom_miste():
    """Regrese z 31. 7. 2026: POST skládal odpověď ručně, takže nové sloupce
    (skupina, vzorec, podmínka) se uložily, ale vracely se prázdné."""
    import inspect

    from app.crm import routes, vlastni_pole

    # `_pole_out` musí delegovat, ne stavět VlastniPoleOut po položkách.
    zdroj = inspect.getsource(routes._pole_out)
    assert "jedno_pro_frontend" in zdroj

    # A tvar musí obsahovat všechny sloupce, které model má.
    klice = set(vlastni_pole.jedno_pro_frontend.__doc__ and {} or {})  # jen pro čitelnost
    from app.crm.schemas import VlastniPoleOut

    ocekavane = set(VlastniPoleOut.model_fields)
    class _P:
        id = 1; entita = "op"; klic = "k"; nazev = "N"; typ = "text"; volby = []
        napoveda = ""; povinne = False; v_seznamu = False; poradi = 0
        skupina = ""; zavislost_pole = ""; zavislost_hodnota = ""; vzorec = ""
    klice = set(vlastni_pole.jedno_pro_frontend(_P()))
    assert ocekavane <= klice, f"chybí ve výstupu: {ocekavane - klice}"
