"""Razítko matice — signál pro prohlížeč, že má načíst nová data.

Razítko se posílá s každým tikem přítomnosti. Klient si ho pamatuje a při
změně si matici natáhne znovu. Proto se musí umět dvě protichůdné věci: změnit
se po JAKÉKOLI změně obsahu (jinak lidé koukají na stará data) a nezměnit se,
když se nezměnilo nic (jinak by si appka tahala matici při každém tiku, tedy
každých osm sekund).

Tabulku `uzivatele` zakládáme ručním SQL — `User` má sloupec `extra_prava`
typu postgresového ARRAY, který SQLite neumí přeložit. Existovat ale musí,
protože `bunky.zmenil_id` na ni má cizí klíč.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.matice.models import Bunka, Projekt, Sloupec
from app.matice.razitko import oznac_zmenu, razitko_matice


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as spoj:
        spoj.execute(
            text("CREATE TABLE uzivatele (id INTEGER PRIMARY KEY, jmeno TEXT NOT NULL)")
        )
        spoj.execute(text("INSERT INTO uzivatele (id, jmeno) VALUES (7, 'Bohuš Novák')"))
    for tabulka in (Projekt.__table__, Sloupec.__table__, Bunka.__table__):
        tabulka.create(engine)

    with Session(engine) as s:
        s.add(Projekt(id=1, nazev="Technicplast", url="", rucni=True))
        s.add(Sloupec(id=1, label="kolaudace", nazev="Kolaudace", faze="realizace"))
        s.commit()
        s.add(Bunka(id=1, projekt_id=1, sloupec_id=1, stav="todo"))
        s.commit()
        yield s


def test_razitko_se_zmeni_po_zmene_bunky(db):
    pred = razitko_matice(db)

    bunka = db.get(Bunka, 1)
    oznac_zmenu(bunka, 7)
    db.commit()

    assert razitko_matice(db) != pred


def test_razitko_se_zmeni_po_pridani_projektu(db):
    """Nový projekt bez `zmeneno_at` musí razítko posunout přes počty řádků.

    Právě kvůli tomuhle jsou v podpisu počty a ne jen čas poslední změny:
    přidání i smazání řádku čas nikam neposune.
    """
    pred = razitko_matice(db)

    db.add(Projekt(id=2, nazev="Nový projekt", url="", rucni=True))
    db.commit()

    assert razitko_matice(db) != pred


def test_dve_cteni_bez_zmeny_daji_stejne_razitko(db):
    """Jinak by si prohlížeč natahoval matici při každém tiku."""
    assert razitko_matice(db) == razitko_matice(db)
