"""Ukládání buňky matice po jednotlivých polích.

Testuje se `app.matice.bunka_pole` nad obyčejným objektem `Bunka()` — bez DB.
Celá logika je čistě nad instancí (kontrola, převod, zápis), takže SQLite by tu
jen přidala tabulky a cizí klíče a nic nezkontrolovala.

Dvě věci, které tenhle soubor hlídá především:

- `zapis_pole` sáhne JEN na jedno pole. Původní `PUT /matice/bunka` posílal
  celou buňku, takže druhý člověk přepsal i pole, kterých se nedotkl.
- `zkontroluj_kolizi` zastaví zápis, když se hodnota v DB mezitím změnila —
  a v hlášce musí být poznat KDO, jinak se člověk nemá podle čeho rozhodnout.
"""

from datetime import date, datetime, timezone

import pytest

from app.matice.bunka_pole import (
    Konflikt,
    datum_text,
    hodnota_textem,
    parse_datum,
    zapis_pole,
    zkontroluj_kolizi,
)
from app.matice.models import Bunka


def _bunka(**kw):
    """Vyplněná buňka jako výchozí stav — ať je na čem poznat přepsání."""
    zaklad = {
        "stav": "todo",
        "termin": date(2026, 5, 20),
        "osoba": "Bohuš",
        "poznamka": "čeká na revizi",
        "verze": 3,
    }
    zaklad.update(kw)
    return Bunka(**zaklad)


def test_zapis_pole_nesahne_na_ostatni_pole():
    """Uloží se jen to jedno pole; zbytek buňky zůstane, jak byl."""
    b = _bunka()
    zapis_pole(b, pole="poznamka", hodnota="revize hotová", uzivatel_id=7)

    assert b.poznamka == "revize hotová"
    assert b.stav == "todo"
    assert b.termin == date(2026, 5, 20)
    assert b.osoba == "Bohuš"


def test_zapis_pole_zapise_kdo_kdy_a_posune_verzi():
    b = _bunka()
    pred = datetime.now(timezone.utc)

    zapis_pole(b, pole="osoba", hodnota="Alena", uzivatel_id=7)

    assert b.osoba == "Alena"
    assert b.verze == 4
    assert b.zmenil_id == 7
    assert b.zmeneno_at >= pred
    # ruční úprava má přednost při načtení z Freela — jinak by ji sync přepsal
    assert b.upraveno_rucne is True


def test_verze_zacina_na_jednicce_i_u_nove_bunky():
    """Nová buňka má `verze` None (default platí až při insertu)."""
    b = Bunka()
    zapis_pole(b, pole="poznamka", hodnota="první", uzivatel_id=None)
    assert b.verze == 1
    assert b.zmenil_id is None


def test_kontrola_kolize_projde_kdyz_puvodni_odpovida():
    b = _bunka()
    # None se neposílá — prohlížeč zobrazoval přesně tyhle hodnoty
    zkontroluj_kolizi(b, pole="poznamka", puvodni="čeká na revizi")
    zkontroluj_kolizi(b, pole="stav", puvodni="todo")
    zkontroluj_kolizi(b, pole="termin", puvodni="2026-05-20")
    zkontroluj_kolizi(b, pole="osoba", puvodni="Bohuš")


def test_kontrola_kolize_vyhodi_konflikt_a_rekne_kdo():
    """Hodnota se mezitím změnila → nepřepisujeme, ptáme se."""
    b = _bunka(poznamka="mezitím to změnil někdo jiný", zmenil_id=9)

    with pytest.raises(Konflikt) as chyba:
        zkontroluj_kolizi(b, pole="poznamka", puvodni="čeká na revizi")

    k = chyba.value
    assert k.pole == "poznamka"
    assert k.aktualni == "mezitím to změnil někdo jiný"
    assert k.zmenil_id == 9


def test_puvodni_none_kontrolu_preskoci():
    """Tvrdý přepis po tom, co člověk v hlášce o kolizi potvrdil „přepiš“."""
    b = _bunka(poznamka="cizí text")
    zkontroluj_kolizi(b, pole="poznamka", puvodni=None)  # nesmí vyhodit nic
    zapis_pole(b, pole="poznamka", hodnota="moje verze", uzivatel_id=7)
    assert b.poznamka == "moje verze"


def test_prazdna_hodnota_je_platna_a_znamena_vymazani():
    """Automatické ukládání nutně zapisuje i nedokončené (prázdné) hodnoty."""
    b = _bunka()

    zapis_pole(b, pole="termin", hodnota="", uzivatel_id=7)
    assert b.termin is None
    assert hodnota_textem(b, "termin") == ""

    zapis_pole(b, pole="stav", hodnota="", uzivatel_id=7)
    assert b.stav is None
    assert hodnota_textem(b, "stav") == ""

    # None z formuláře se bere jako prázdno, ne jako chyba
    zapis_pole(b, pole="poznamka", hodnota=None, uzivatel_id=7)
    assert b.poznamka == ""
    assert hodnota_textem(b, "poznamka") == ""


def test_neplatna_hodnota_i_nezname_pole_vyhodi_valueerror():
    b = _bunka()
    with pytest.raises(ValueError):
        zapis_pole(b, pole="stav", hodnota="hotovo", uzivatel_id=7)
    with pytest.raises(ValueError):
        zapis_pole(b, pole="termin", hodnota="31.12.2026", uzivatel_id=7)
    with pytest.raises(ValueError):
        zapis_pole(b, pole="url", hodnota="https://freelo", uzivatel_id=7)
    with pytest.raises(ValueError):
        hodnota_textem(b, "url")
    # neplatný zápis nesmí buňku zmrzačit napůl
    assert b.stav == "todo"
    assert b.termin == date(2026, 5, 20)


def test_termin_se_uklada_jako_datum():
    b = _bunka(termin=None)
    zapis_pole(b, pole="termin", hodnota="2026-12-31", uzivatel_id=7)

    assert b.termin == date(2026, 12, 31)
    assert datum_text(b.termin) == "2026-12-31"
    assert hodnota_textem(b, "termin") == "2026-12-31"
    # čas za datem prohlížeč občas pošle; bere se prvních deset znaků
    assert parse_datum("2026-12-31T23:59:00") == date(2026, 12, 31)
    assert parse_datum("") is None
    assert datum_text(None) is None
