"""Audit log (CRM-12) — sběr změn přes událost SQLAlchemy.

Testuje se nad SQLite s náhradními modely: skutečné CRM modely mají JSONB
a ARRAY, které SQLite nevytvoří, ale mechanika auditu je na konkrétních
sloupcích nezávislá.

Nejdůležitější případ je `test_stara_hodnota_prezije_expiraci`. Naivní
implementace přes `attrs[...].history` projde všemi ostatními testy a selže
právě na něm — po commitu jsou atributy vyexpirované, takže by log u každé
změny tvrdil „z prázdna na X". Tím by ztratil to jediné, kvůli čemu existuje:
z čeho se hodnota změnila.
"""

import pytest
from sqlalchemy import Column, Integer, Numeric, String, create_engine
from sqlalchemy.orm import Session, declarative_base

from app.crm import audit

Base = declarative_base()


class Zakaznik(Base):  # jméno třídy musí sedět s audit.SLEDOVANE
    __tablename__ = "zakaznici"
    id = Column(Integer, primary_key=True)
    nazev = Column(String)
    ico = Column(String)
    hodnota_kc = Column(Numeric(14, 2))
    aktualizovano_at = Column(String)


class CrmAudit(Base):
    __tablename__ = "crm_audit"
    id = Column(Integer, primary_key=True)
    entita = Column(String)
    zaznam_id = Column(Integer)
    druh = Column(String, default="")
    pole = Column(String, default="")
    stara = Column(String, default="")
    nova = Column(String, default="")
    zmenil_user_id = Column(Integer)


@pytest.fixture()
def session(monkeypatch):
    import app.crm.models as modely

    monkeypatch.setattr(modely, "CrmAudit", CrmAudit, raising=False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    audit.zapni()
    audit.aktualni_uzivatel_id.set(7)
    with Session(engine) as s:
        yield s


def _log(s):
    return [(a.druh, a.pole, a.stara, a.nova) for a in s.query(CrmAudit).order_by(CrmAudit.id)]


def test_vznik_se_zaloguje(session):
    session.add(Zakaznik(nazev="Firma"))
    session.commit()
    assert ("vznik", "", "", "") in _log(session)


def test_stara_hodnota_prezije_expiraci(session):
    """Případ ze zadání: „kdo změnil cenu z 2,5 na 1,9 mil.".

    Mezi uložením a změnou je commit, takže atributy jsou vyexpirované —
    přesně situace, ve které se stará hodnota nejsnáz ztratí.
    """
    z = Zakaznik(nazev="Firma", hodnota_kc=2500000)
    session.add(z)
    session.commit()

    z.hodnota_kc = 1900000
    session.commit()

    zmeny = [x for x in _log(session) if x[0] == "zmena"]
    assert ("zmena", "hodnota_kc", "2500000", "1900000") in zmeny


def test_nastaveni_stejne_hodnoty_neni_zmena(session):
    z = Zakaznik(nazev="Firma", ico="123")
    session.add(z)
    session.commit()

    z.ico = "123"
    z.nazev = "Firma s.r.o."
    session.commit()

    zmeny = [x for x in _log(session) if x[0] == "zmena"]
    assert [x[1] for x in zmeny] == ["nazev"]


def test_technicka_pole_se_nelogují(session):
    z = Zakaznik(nazev="Firma")
    session.add(z)
    session.commit()

    z.aktualizovano_at = "2026-07-31"
    session.commit()

    assert [x for x in _log(session) if x[0] == "zmena"] == []


def test_smazani_se_zaloguje(session):
    z = Zakaznik(nazev="Firma")
    session.add(z)
    session.commit()
    session.delete(z)
    session.commit()

    assert any(x[0] == "smazani" for x in _log(session))


def test_zapise_se_kdo(session):
    session.add(Zakaznik(nazev="Firma"))
    session.commit()
    assert session.query(CrmAudit).first().zmenil_user_id == 7


def test_bez_prihlaseneho_uzivatele_se_zmena_stejne_zapise(session):
    """Skript nebo plánovač autora nemá — záznam bez autora je pořád cennější
    než žádný."""
    audit.aktualni_uzivatel_id.set(None)
    session.add(Zakaznik(nazev="Firma"))
    session.commit()
    assert session.query(CrmAudit).first().zmenil_user_id is None


def test_nesledovany_model_se_neloguje(session):
    """Do logu patří jen entity ze SLEDOVANE — jinak by se logoval i log."""
    assert "CrmAudit" not in audit.SLEDOVANE


# ---- formátování hodnot ------------------------------------------------------
def test_text_hodnoty():
    assert audit._text(None) == ""
    assert audit._text(True) == "ano"
    assert audit._text(False) == "ne"
    assert audit._text(1500000.0) == "1500000"
    assert audit._text(["a", "b"]) == "a, b"


def test_vlastni_pole_se_logují_po_klicich():
    """Celý slovník by v logu byl nečitelný — zajímá nás, KTERÝ údaj se změnil."""
    zmeny = audit._zmeny_extra({"cislo_smlouvy": "A1"}, {"cislo_smlouvy": "A2", "nove": "x"})
    assert ("extra:cislo_smlouvy", "A1", "A2") in zmeny
    assert ("extra:nove", "", "x") in zmeny


# ---- viditelnost novinek (rozhodnutí Dana 31. 7. 2026) -----------------------
def test_novinky_zatim_jen_pro_adminy():
    """Kdo má práva, vidí dál svoje obrazovky — ale čerstvé funkce zatím ne.

    Až se to bude otevírat, mění se jediná funkce (`ma_novinky`); endpointy
    ani frontend se sahat nemusí.
    """
    from types import SimpleNamespace

    from app.crm.novinky import ma_novinky

    assert ma_novinky(SimpleNamespace(je_admin=True)) is True
    assert ma_novinky(SimpleNamespace(je_admin=False)) is False


# ---- dny ve fázi (CRM-44) ----------------------------------------------------
def test_dny_ve_fazi_pocita_od_posledni_zmeny(monkeypatch):
    """Případ bez historie se počítá od založení — jinak by čerstvě vzniklý
    případ hlásil 0 dní i po měsíci."""
    from datetime import datetime, timedelta
    from types import SimpleNamespace

    from app.crm import routes

    pred_mesicem = datetime.now() - timedelta(days=30)
    zaznam = SimpleNamespace(id=1, vytvoreno_at=pred_mesicem)

    class FalesnyDotaz:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return []  # žádná historie

    db = SimpleNamespace(query=lambda *a, **k: FalesnyDotaz())
    assert routes.dny_ve_fazi(db, "op", [zaznam])[1] == 30
