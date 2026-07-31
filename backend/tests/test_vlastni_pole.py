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
