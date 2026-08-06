"""Přítomnost — „kdo má tuhle věc zrovna otevřenou“.

Testuje se `app.pritomnost.sluzba` nad SQLite in-memory, bez HTTP vrstvy.
Nejdůležitější případ je `test_kdo_tikl_pred_minutou_uz_neni_pritomny`: celá
konstrukce stojí na tom, že přítomnost VYPRŠÍ sama. Kdyby se člověk ze seznamu
odebíral jen při zavření stránky, každý spadlý prohlížeč nebo utržená síť by
v matici nechali ducha, který tam navěky „edituje“ buňku.

Tabulku `uzivatele` tu zakládáme ručním SQL: `User` má sloupec `extra_prava`
typu postgresového ARRAY, který se do SQLite vůbec nepřeloží (`CompileError`),
takže `User.__table__.create` použít nejde. Pro join na jméno stačí id a jméno.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.pritomnost import registr, sluzba
from app.pritomnost.models import Pritomnost

# Pevný čas místo „teď“: okna se počítají v sekundách a test, který závisí na
# rychlosti stroje, by občas padal bez viny kódu.
TED = datetime(2026, 8, 6, 10, 0, 0, tzinfo=timezone.utc)

LIDI = [(1, "Bohuš Novák"), (2, "Alena Malá"), (3, "Cyril Zeman")]


def _v_utc(dt):
    """Dorovná čas z DB na UTC.

    SQLite vrací `DateTime(timezone=True)` bez zóny (naive), Postgres se zónou.
    Bez tohohle by srovnání s pevným časem testu spadlo na TypeError.
    """
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as spoj:
        spoj.execute(
            text("CREATE TABLE uzivatele (id INTEGER PRIMARY KEY, jmeno TEXT NOT NULL)")
        )
        for uid, jmeno in LIDI:
            spoj.execute(
                text("INSERT INTO uzivatele (id, jmeno) VALUES (:id, :jmeno)"),
                {"id": uid, "jmeno": jmeno},
            )
    Pritomnost.__table__.create(engine)
    with Session(engine) as s:
        yield s


def test_tik_zaklada_a_druhy_tik_jen_obnovi(db):
    """Dva tiky téhož člověka na tutéž věc = pořád jeden řádek, novější čas."""
    sluzba.zapis_tik(
        db, uzivatel_id=1, entita_typ="matice", entita_id="1||2", pole="stav", nyni=TED
    )
    db.commit()

    pozdeji = TED + timedelta(seconds=9)
    sluzba.zapis_tik(
        db,
        uzivatel_id=1,
        entita_typ="matice",
        entita_id="1||2",
        pole="poznamka",
        nyni=pozdeji,
    )
    db.commit()

    radek = db.query(Pritomnost).one()  # one() = spadne, kdyby řádky byly dva
    assert _v_utc(radek.kdy) == pozdeji
    # `pole` se přepíše na to, co má člověk rozevřené teď
    assert radek.pole == "poznamka"


def test_precti_pritomne_vraci_jen_okno(db):
    """V seznamu je ten, kdo tikl v posledních `OKNO_S` sekundách."""
    sluzba.zapis_tik(
        db,
        uzivatel_id=1,
        entita_typ="matice",
        entita_id="1||2",
        nyni=TED - timedelta(seconds=5),
    )
    sluzba.zapis_tik(
        db,
        uzivatel_id=2,
        entita_typ="matice",
        entita_id="1||2",
        pole="termin",
        nyni=TED,
    )
    db.commit()

    lidi = sluzba.precti_pritomne(db, entita_typ="matice", entita_id="1||2", nyni=TED)
    # řazení podle jména: Alena před Bohušem
    assert [c["jmeno"] for c in lidi] == ["Alena Malá", "Bohuš Novák"]
    assert [c["pole"] for c in lidi] == ["termin", ""]


def test_kdo_tikl_pred_minutou_uz_neni_pritomny(db):
    """Zavřená záložka musí ze seznamu zmizet sama — to je jádro věci."""
    assert sluzba.OKNO_S < 60, "test počítá s tím, že 60 s je mimo okno"
    sluzba.zapis_tik(
        db,
        uzivatel_id=1,
        entita_typ="matice",
        entita_id="1||2",
        nyni=TED - timedelta(seconds=60),
    )
    db.commit()

    # řádek v tabulce pořád je (maže ho až úklid), ale za přítomného se nepočítá
    assert db.query(Pritomnost).count() == 1
    assert sluzba.precti_pritomne(db, entita_typ="matice", entita_id="1||2", nyni=TED) == []


def test_pritomnost_je_oddelena_po_entitach(db):
    """Tik na jedné buňce se nesmí objevit u jiné."""
    sluzba.zapis_tik(
        db, uzivatel_id=1, entita_typ="matice", entita_id="1||2", nyni=TED
    )
    db.commit()

    assert len(sluzba.precti_pritomne(db, entita_typ="matice", entita_id="1||2", nyni=TED)) == 1
    assert sluzba.precti_pritomne(db, entita_typ="matice", entita_id="9||9", nyni=TED) == []
    # ani „celý modul“ (prázdné entita_id) není totéž jako konkrétní buňka
    assert sluzba.precti_pritomne(db, entita_typ="matice", nyni=TED) == []


def test_odhlas_smaze_radek(db):
    sluzba.zapis_tik(db, uzivatel_id=1, entita_typ="matice", entita_id="1||2", nyni=TED)
    sluzba.zapis_tik(db, uzivatel_id=2, entita_typ="matice", entita_id="1||2", nyni=TED)
    db.commit()

    sluzba.odhlas(db, uzivatel_id=1, entita_typ="matice", entita_id="1||2")
    db.commit()

    zbylo = db.query(Pritomnost).all()
    assert [p.uzivatel_id for p in zbylo] == [2]


def test_uklid_zahodi_jen_stare_radky(db):
    """Úklid maže dávno neobnovené řádky, čerstvé se nesmí dotknout."""
    sluzba.zapis_tik(
        db,
        uzivatel_id=1,
        entita_typ="matice",
        entita_id="1||2",
        nyni=TED - timedelta(seconds=sluzba.UKLID_S + 60),
    )
    sluzba.zapis_tik(
        db,
        uzivatel_id=2,
        entita_typ="matice",
        entita_id="1||2",
        nyni=TED - timedelta(seconds=5),
    )
    db.commit()

    assert sluzba.uklid(db, nyni=TED) == 1
    db.commit()
    assert [p.uzivatel_id for p in db.query(Pritomnost).all()] == [2]
    # druhý úklid už nemá co dělat
    assert sluzba.uklid(db, nyni=TED) == 0


def test_registr_vaze_entitu_na_pravo():
    """Seznam přítomných nesmí obejít práva: každá entita má svoje právo."""
    assert registr.pravo_pro("matice") == "projekty"
    # neznámý typ = None → endpoint ho odmítne, místo aby ho pustil bez kontroly
    assert registr.pravo_pro("neco-vymysleneho") is None
    assert registr.razitko(db=None, entita_typ="neco-vymysleneho") == ""
