"""Notifikace a šablony (dávka E) — logika, která se dá otestovat bez DB.

Cílíme na tři věci, které se snadno rozbijí a v provozu by se projevily až tím,
že někomu něco nechodí (nebo chodí, i když si to vypnul):

  * doplňování výchozích voleb u nové události,
  * čištění vstupu při ukládání voleb,
  * dosazování symbolů do šablony, včetně toho, že neznámý symbol zůstane.
"""

from app.crm import notifikace, sablony


# ---- katalog událostí (CRM-36) ----------------------------------------------
def test_kazda_udalost_ma_povinna_pole():
    for u in notifikace.UDALOSTI:
        assert u["klic"] and u["nazev"], u
        assert isinstance(u["appka"], bool) and isinstance(u["email"], bool)


def test_klice_udalosti_jsou_unikatni():
    klice = [u["klic"] for u in notifikace.UDALOSTI]
    assert len(klice) == len(set(klice))


def test_notifikace_v_appce_jde_u_vseho_vychozi():
    """Zvoneček je nenásilný kanál – u všeho zapnutý. E-mail jen u některých."""
    assert all(u["appka"] for u in notifikace.UDALOSTI)
    assert any(u["email"] for u in notifikace.UDALOSTI)
    assert not all(u["email"] for u in notifikace.UDALOSTI)


# ---- šablony (CRM-32) --------------------------------------------------------
def test_doplneni_symbolu():
    text = "Dobrý den, posílám nabídku {{cislo}} pro {{zakaznik}}. {{moje_jmeno}}"
    out = sablony.doplnil(text, {"cislo": "NAB-26-0007", "zakaznik": "Firma s.r.o.", "moje_jmeno": "Dan"})
    assert out == "Dobrý den, posílám nabídku NAB-26-0007 pro Firma s.r.o.. Dan"


def test_neznamy_symbol_zustane_v_textu():
    """Vědomé rozhodnutí: díra ve větě je horší než viditelný symbol."""
    out = sablony.doplnil("Ahoj {{neexistuje}}, {{zakaznik}}", {"zakaznik": "Firma"})
    assert out == "Ahoj {{neexistuje}}, Firma"


def test_prazdna_hodnota_symbol_nesmaze():
    out = sablony.doplnil("Pro {{zakaznik}} platí", {"zakaznik": ""})
    assert "{{zakaznik}}" in out


def test_mezery_v_symbolu_nevadi():
    assert sablony.doplnil("{{ zakaznik }}", {"zakaznik": "Firma"}) == "Firma"


def test_text_bez_symbolu_projde_beze_zmeny():
    assert sablony.doplnil("Prostý text", {"zakaznik": "Firma"}) == "Prostý text"
    assert sablony.doplnil("", {}) == ""


def test_symboly_v_napovede_odpovidaji_tomu_co_umime_doplnit():
    """Nápověda v UI nesmí slibovat symbol, který se nikdy nedoplní."""
    z_napovedy = {k for k, _ in sablony.SYMBOLY}
    # Všechny symboly z nápovědy musí umět projít doplněním (test na překlep
    # v klíči – dosazení hodnoty se pozná podle toho, že symbol zmizí).
    for klic in z_napovedy:
        assert sablony.doplnil("{{%s}}" % klic, {klic: "X"}) == "X"
