"""Slučovací okno auditu (autosave po polích).

Autosave ukládá pole při každém opuštění, takže napsání „Technicplast“ pošle
několik uložení téhož pole za sebou. Bez slučování by v historii byly řádky
„Tech“ → „Technic“ → „Technicpl“ a výpis (`audit.zaznamy`, limit 100) by po
jednom odpoledni psaní neobsahoval nic užitečného.

Testuje se nad SQLite s náhradními modely, stejně jako `test_audit.py`:
skutečné CRM modely mají JSONB a ARRAY, které SQLite nevytvoří. Tabulka
uživatelů tu není vůbec potřeba — `zmenil_user_id` je pro slučování jen číslo,
podle kterého se rozlišuje, kdo změnu udělal.

Nejdůležitější případy:
  * `test_jiny_clovek_ma_vlastni_radek` — sloučení nesmí přivlastnit cizí
    změnu, jinak by v logu stálo, že cenu snížil ten, kdo pak opravil telefon,
  * `test_zmena_a_vraceni_zpet_radek_smaze` — po A → B → A nemá v historii
    zůstat „změnil z Praha na Praha“,
  * `test_stara_hodnota_zustava_z_prvniho_zapisu` — přepsat při sloučení
    i `stara` je nejsnazší chyba a ztratila by to jediné, kvůli čemu log je:
    z čeho se hodnota měnila.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, DateTime, Integer, Numeric, String, create_engine, func
from sqlalchemy.orm import Session, declarative_base

from app.crm import audit

Base = declarative_base()

DAN = 7
JANA = 9


class Zakaznik(Base):  # jméno třídy musí sedět s audit.SLEDOVANE
    __tablename__ = "zakaznici"
    id = Column(Integer, primary_key=True)
    nazev = Column(String)
    mesto = Column(String)
    hodnota_kc = Column(Numeric(14, 2))


class CrmAudit(Base):
    """Náhrada za skutečný model — `kdy` se plní stejně (`now()` v UTC)."""

    __tablename__ = "crm_audit"
    id = Column(Integer, primary_key=True)
    entita = Column(String)
    zaznam_id = Column(Integer)
    druh = Column(String, default="zmena")
    pole = Column(String, default="")
    stara = Column(String, default="")
    nova = Column(String, default="")
    zmenil_user_id = Column(Integer)
    kdy = Column(DateTime, server_default=func.now())


@pytest.fixture()
def session(monkeypatch):
    import app.crm.models as modely

    monkeypatch.setattr(modely, "CrmAudit", CrmAudit, raising=False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit.zapni()
    audit.aktualni_uzivatel_id.set(DAN)
    with Session(engine) as s:
        yield s


def _zakaznik(session, **hodnoty) -> Zakaznik:
    z = Zakaznik(**hodnoty)
    session.add(z)
    session.commit()
    return z


def _zmeny(session) -> list[CrmAudit]:
    return (
        session.query(CrmAudit)
        .filter(CrmAudit.druh == "zmena")
        .order_by(CrmAudit.id)
        .all()
    )


def _posun_do_minulosti(session, sekund: int) -> None:
    """Posune existující řádky auditu do minulosti — simulace uplynulého času.

    Čeká se reálných pět minut jen v nočních můrách; posunout `kdy` je totéž
    a testy zůstanou rychlé. `CrmAudit` není ve `SLEDOVANE`, takže se tahle
    úprava sama nezaloguje.
    """
    kdy = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=sekund)
    for radek in session.query(CrmAudit).all():
        radek.kdy = kdy
    session.commit()


def test_dve_zmeny_v_okne_jsou_jeden_radek(session):
    """Psaní „Technicplast“ po znacích je JEDNA změna, ne tři řádky."""
    z = _zakaznik(session, nazev="Tech")

    z.nazev = "Technic"
    session.commit()
    z.nazev = "Technicplast"
    session.commit()

    zmeny = _zmeny(session)
    assert len(zmeny) == 1
    assert (zmeny[0].pole, zmeny[0].stara, zmeny[0].nova) == ("nazev", "Tech", "Technicplast")


def test_stara_hodnota_zustava_z_prvniho_zapisu(session):
    """Sloučení posouvá jen `nova`. `stara` drží, ZE ČEHO se to začalo měnit."""
    z = _zakaznik(session, hodnota_kc=2500000)

    z.hodnota_kc = 2000000
    session.commit()
    z.hodnota_kc = 1900000
    session.commit()

    zmeny = _zmeny(session)
    assert len(zmeny) == 1
    assert (zmeny[0].stara, zmeny[0].nova) == ("2500000", "1900000")


def test_zmena_po_uplynuti_okna_je_novy_radek(session):
    """Ráno jedna cena, po obědě jiná — to jsou dvě samostatná rozhodnutí."""
    z = _zakaznik(session, nazev="Tech")

    z.nazev = "Technic"
    session.commit()
    _posun_do_minulosti(session, audit.OKNO_SLOUCENI_S + 60)

    z.nazev = "Technicplast"
    session.commit()

    zmeny = _zmeny(session)
    assert len(zmeny) == 2
    assert [(x.stara, x.nova) for x in zmeny] == [
        ("Tech", "Technic"),
        ("Technic", "Technicplast"),
    ]


def test_jine_pole_ma_vlastni_radek(session):
    """Slučuje se podle pole — jinak by se v logu ztratilo, co se změnilo."""
    z = _zakaznik(session, nazev="Tech", mesto="Praha")

    z.nazev = "Technicplast"
    session.commit()
    z.mesto = "Brno"
    session.commit()

    zmeny = _zmeny(session)
    assert [(x.pole, x.stara, x.nova) for x in zmeny] == [
        ("nazev", "Tech", "Technicplast"),
        ("mesto", "Praha", "Brno"),
    ]


def test_jiny_clovek_ma_vlastni_radek(session):
    """Cizí změnu si nikdo přivlastnit nesmí, ani když je pole a čas stejný."""
    z = _zakaznik(session, nazev="Tech")

    z.nazev = "Technic"
    session.commit()

    audit.aktualni_uzivatel_id.set(JANA)
    z.nazev = "Technicplast"
    session.commit()

    zmeny = _zmeny(session)
    assert len(zmeny) == 2
    # Danův řádek zůstal, jak byl — Jana ho nepřepsala.
    assert (zmeny[0].zmenil_user_id, zmeny[0].stara, zmeny[0].nova) == (DAN, "Tech", "Technic")
    assert (zmeny[1].zmenil_user_id, zmeny[1].stara, zmeny[1].nova) == (
        JANA,
        "Technic",
        "Technicplast",
    )


def test_zmena_a_vraceni_zpet_radek_smaze(session):
    """A → B → A v okně: v historii nemá být „změnil z Praha na Praha“."""
    z = _zakaznik(session, mesto="Praha")

    z.mesto = "Brno"
    session.commit()
    z.mesto = "Praha"
    session.commit()

    assert _zmeny(session) == []
    # Smazal se jen řádek změny, vznik záznamu v historii zůstává.
    assert session.query(CrmAudit).filter(CrmAudit.druh == "vznik").count() == 1


def test_vraceni_zpet_po_uplynuti_okna_se_zaloguje(session):
    """Mimo okno je návrat na původní hodnotu samostatné rozhodnutí, ne omyl."""
    z = _zakaznik(session, mesto="Praha")

    z.mesto = "Brno"
    session.commit()
    _posun_do_minulosti(session, audit.OKNO_SLOUCENI_S + 60)

    z.mesto = "Praha"
    session.commit()

    assert [(x.stara, x.nova) for x in _zmeny(session)] == [("Praha", "Brno"), ("Brno", "Praha")]


def test_vznik_se_neslucuje(session):
    """Do řádku „vznik“ se změna nepřilepí, ani kdyby čtveřice souhlasila."""
    z = _zakaznik(session, nazev="Firma")
    # Uměle podstrčený „vznik“ se stejnou čtveřicí (entita, záznam, pole,
    # autor) jako chystaná změna — naivní hledání bez podmínky na druh by si
    # ho vzalo a smazalo tím informaci o založení záznamu.
    session.add(
        CrmAudit(
            entita="zakaznik",
            zaznam_id=z.id,
            druh="vznik",
            pole="nazev",
            stara="Firma",
            nova="Firma",
            zmenil_user_id=DAN,
        )
    )
    session.commit()

    z.nazev = "Firma s.r.o."
    session.commit()

    vzniky = session.query(CrmAudit).filter(CrmAudit.druh == "vznik").all()
    assert len(vzniky) == 2  # automatický při založení + podstrčený
    assert all(v.nova in ("", "Firma") for v in vzniky)
    assert [(x.stara, x.nova) for x in _zmeny(session)] == [("Firma", "Firma s.r.o.")]


def test_vznik_neprepise_vraceni_zpet(session):
    """A → B → A smaže jen svůj řádek změny, „vznik“ se nikdy nemaže."""
    z = _zakaznik(session, nazev="Firma")

    z.nazev = "Jiná"
    session.commit()
    z.nazev = "Firma"
    session.commit()

    assert _zmeny(session) == []
    assert session.query(CrmAudit).filter(CrmAudit.druh == "vznik").count() == 1


def test_smazani_se_neslucuje(session):
    """Smazání záznamu je jednorázová událost, nikdy se s ničím nespojuje."""
    z = _zakaznik(session, nazev="Firma")
    z.nazev = "Firma s.r.o."
    session.commit()

    session.delete(z)
    session.commit()

    druhy = [x.druh for x in session.query(CrmAudit).order_by(CrmAudit.id).all()]
    assert druhy.count("smazani") == 1
    assert druhy.count("zmena") == 1


def test_slouceni_posune_cas_na_ted(session):
    """Okno se počítá od POSLEDNÍHO psaní, aby se dlouhá úprava nerozsekla."""
    z = _zakaznik(session, nazev="Tech")
    z.nazev = "Technic"
    session.commit()
    # Skoro na konci okna — další úprava se ještě vejde a čas se posune.
    _posun_do_minulosti(session, audit.OKNO_SLOUCENI_S - 30)

    z.nazev = "Technicp"
    session.commit()
    z.nazev = "Technicplast"
    session.commit()

    zmeny = _zmeny(session)
    assert len(zmeny) == 1
    assert (zmeny[0].stara, zmeny[0].nova) == ("Tech", "Technicplast")


def test_okno_je_pet_minut(session):
    """Hodnota je vědomé rozhodnutí, ne náhoda — hlídá se, aby se nehnula."""
    assert audit.OKNO_SLOUCENI_S == 300


def test_technicka_pole_ze_zmena_mixinu_se_neloguji():
    """`zmeneno_at`, `zmenil_id` a `verze` do historie změn NEPATŘÍ.

    Mění se při každém uložení, takže by u každé úpravy stály v historii tři
    řádky navíc („verze: 0 → 2“) a to podstatné by se v nich utopilo. Zjištěno
    při ověřování nasazení 6. 8. 2026 — v auditu testovacího zápisu to byly
    jediné viditelné změny, protože samotný text si slučovací okno sloučilo.
    """
    for pole in ("zmeneno_at", "zmenil_id", "verze"):
        assert pole in audit.IGNOROVANA_POLE, pole
