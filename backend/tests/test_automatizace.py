"""Automatizace CRM (CRM-31) — pravidla „stav X → udělej Y".

Testuje se nad SQLite s náhradními modely (skutečné mají JSONB, které SQLite
nevytvoří), stejný postup jako u auditu. Mechanika spouštění je na konkrétních
sloupcích nezávislá.

Dva případy jsou tu ty, kvůli kterým test existuje:

  * `test_pravidlo_bezi_na_zaznam_jen_jednou` — bez hlídání běhů vyrobí případ
    vrácený z „Vyhráno" do „Vyjednávání" a zpátky DRUHOU objednávku. Na živých
    datech se to pozná až tím, že zákazník dostane dvě objednávky.
  * `test_selhani_akce_nezrusi_predchozi_zmeny` — kdyby se chyba akce řešila
    `db.rollback()`, zahodila by i změnu stavu, kterou právě udělal člověk.
    Přesun v kanbanu by tiše zmizel. Proto savepoint.
"""

import pytest
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    event,
    func,
)
from sqlalchemy.orm import Session, declarative_base

from app.crm import automatizace

Base = declarative_base()


class CrmPravidlo(Base):
    __tablename__ = "crm_pravidla"
    id = Column(Integer, primary_key=True)
    nazev = Column(String)
    aktivni = Column(Boolean, default=True)
    poradi = Column(Integer, default=0)
    spoust_entita = Column(String)
    spoust_stav = Column(String)
    akce = Column(String)
    nastaveni = Column(String)  # v testu se obsah nečte, jen se předává


class CrmPravidloBeh(Base):
    __tablename__ = "crm_pravidlo_behy"
    id = Column(Integer, primary_key=True)
    pravidlo_id = Column(Integer)
    entita = Column(String)
    zaznam_id = Column(Integer)
    vysledek = Column(String, default="hotovo")
    popis = Column(Text, default="")
    spustil_user_id = Column(Integer)
    kdy = Column(DateTime, server_default=func.now())


class CrmAktivita(Base):
    __tablename__ = "crm_aktivity"
    id = Column(Integer, primary_key=True)
    entita = Column(String)
    zaznam_id = Column(Integer)
    druh = Column(String)
    nazev = Column(String, default="")
    text = Column(Text, default="")
    termin = Column(Date)
    vlastnik_user_id = Column(Integer)
    vytvoril_user_id = Column(Integer)


class Pripad(Base):
    """Náhrada obchodního případu — potřebuje jen `id` a stav."""

    __tablename__ = "crm_obchodni_pripady"
    id = Column(Integer, primary_key=True)
    cislo = Column(String, default="OP-26-0301")
    nazev = Column(String, default="Zakázka")
    stav = Column(String, default="novy")
    vlastnik_user_id = Column(Integer)


class _Uzivatel:
    def __init__(self, id=7):
        self.id = id


@pytest.fixture()
def session(monkeypatch):
    # Náhradní modely místo skutečných (JSONB/ARRAY v SQLite nevzniknou).
    monkeypatch.setattr(automatizace, "CrmPravidlo", CrmPravidlo)
    monkeypatch.setattr(automatizace, "CrmPravidloBeh", CrmPravidloBeh)
    monkeypatch.setattr(automatizace, "CrmAktivita", CrmAktivita)

    engine = create_engine("sqlite://")

    # SAVEPOINT nad pysqlite funguje jen s vypnutým implicitním BEGINem
    # (doporučený postup z dokumentace SQLAlchemy). Bez toho by se test
    # savepointu chytal na driveru, ne na testované logice.
    @event.listens_for(engine, "connect")
    def _bez_implicitni_transakce(dbapi_conn, _rec):
        dbapi_conn.isolation_level = None

    @event.listens_for(engine, "begin")
    def _rucni_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _pravidlo(s, akce="test", stav="vyhrano", entita="op"):
    p = CrmPravidlo(
        nazev="Pravidlo",
        aktivni=True,
        poradi=0,
        spoust_entita=entita,
        spoust_stav=stav,
        akce=akce,
        nastaveni="{}",
    )
    s.add(p)
    s.commit()
    return p


def _behy(s):
    return [(b.vysledek, b.popis) for b in s.query(CrmPravidloBeh).order_by(CrmPravidloBeh.id)]


# ---- struktura katalogu ------------------------------------------------------
def test_kazda_akce_ma_vykonavace():
    """Akce v katalogu bez funkce by v nastavení šla vybrat a nikdy by nezabrala."""
    assert set(automatizace.MAPA_AKCI) == set(automatizace.VYKONAVACE)


def test_akce_spoustene_jen_ze_znamych_entit():
    for a in automatizace.AKCE:
        assert a["entity"], f"akce {a['klic']} nemá žádnou spouštěcí entitu"
        for e in a["entity"]:
            assert e in automatizace.SPOUSTECI_ENTITY


def test_vychozi_pravidla_miri_na_existujici_akce_a_stavy():
    """Výchozí pravidla musí trefit klíče z výchozí sady stavů.

    Překlep by znamenal pravidlo, které se v nastavení tváří funkčně, ale
    nikdy se nespustí — a nikdo by nepoznal proč.
    """
    from app.crm.stavy import VYCHOZI_STAVY

    for p in automatizace.VYCHOZI_PRAVIDLA:
        assert p["akce"] in automatizace.MAPA_AKCI
        klice = {s["klic"] for s in VYCHOZI_STAVY[p["spoust_entita"]]}
        assert p["spoust_stav"] in klice, f"{p['nazev']}: stav {p['spoust_stav']} neexistuje"
        # A akce musí umět pracovat od té entity, na které pravidlo visí.
        assert p["spoust_entita"] in automatizace.MAPA_AKCI[p["akce"]]["entity"]


def test_vychozi_pravidla_jsou_vypnuta():
    """Automatika se po nasazení nesmí rozjet sama — zapíná ji člověk."""
    from app.crm.models import CrmPravidlo as Skutecne

    assert Skutecne.__tablename__ == "crm_pravidla"
    # seed zakládá `aktivni=False`; kdyby se to změnilo, začne appka po deployi
    # zakládat objednávky, aniž o tom kdokoli ví.
    import inspect

    zdroj = inspect.getsource(automatizace.seed_pravidla)
    assert "aktivni=False" in zdroj


# ---- spouštění --------------------------------------------------------------
def test_pravidlo_zapise_beh_i_poznamku(session):
    pravidlo = _pravidlo(session)
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p, u: "Založena objednávka OBJ-26-0001"
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)

    assert hotove == ["Založena objednávka OBJ-26-0001"]
    assert _behy(session) == [("hotovo", "Založena objednávka OBJ-26-0001")]
    # Poznámka v aktivitách je to místo, kde si člověk přečte, co appka udělala.
    poznamky = session.query(CrmAktivita).all()
    assert len(poznamky) == 1
    assert poznamky[0].druh == "poznamka"
    assert pravidlo.nazev in poznamky[0].text


def test_pravidlo_bezi_na_zaznam_jen_jednou(session):
    """Případ vrácený zpátky a znovu vyhraný nesmí vyrobit druhou objednávku."""
    _pravidlo(session)
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p, u: "Založena objednávka"
    try:
        prvni = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
        druhy = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)

    assert prvni == ["Založena objednávka"]
    assert druhy == [], "pravidlo se u téhož záznamu spustilo dvakrát"
    assert len(_behy(session)) == 1
    # Jiný záznam se ale spustit musí – limit je na záznam, ne na pravidlo.
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p, u: "Založena objednávka"
    try:
        jiny = automatizace.po_zmene_stavu(session, "op", Pripad(id=2), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)
    assert jiny == ["Založena objednávka"]


def test_vypnute_pravidlo_se_nespusti(session):
    p = _pravidlo(session)
    p.aktivni = False
    session.commit()
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p_, u: "Nemělo proběhnout"
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)
    assert hotove == []
    assert _behy(session) == []


def test_jiny_stav_pravidlo_nespusti(session):
    _pravidlo(session, stav="vyhrano")
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p, u: "Nemělo proběhnout"
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "prohrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)
    assert hotove == []


def test_preskoceni_se_zaloguje(session):
    """„Nic se nestalo" musí být v logu vidět, jinak to vypadá jako nefunkční pravidlo."""
    _pravidlo(session)
    automatizace.VYKONAVACE["test"] = lambda db, e, z, p, u: ""
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)
    assert hotove == []
    assert [v for v, _ in _behy(session)] == ["preskoceno"]


def test_selhani_akce_nezrusi_predchozi_zmeny(session):
    """Klíčový případ: chyba automatiky nesmí zahodit přesun, který udělal člověk.

    Simuluje endpoint: nejdřív se změní stav (jako `zmen_stav_pripadu`), pak se
    volá automatika. Když akce spadne, změna stavu musí přežít a commit projít.
    """
    _pravidlo(session)
    pripad = Pripad(id=1, stav="novy")
    session.add(pripad)
    session.commit()

    pripad.stav = "vyhrano"  # to, co udělal člověk v kanbanu

    def _spadne(db, e, z, p, u):
        # Akce nastihne něco zapsat a pak selže – přesně případ, kdy je session
        # rozbitá a naivní ošetření by muselo volat rollback.
        db.add(CrmAktivita(entita="op", zaznam_id=1, druh="ukol", nazev="půl práce"))
        db.flush()
        raise RuntimeError("šablona neexistuje")

    automatizace.VYKONAVACE["test"] = _spadne
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)

    assert hotove == []
    session.commit()  # commit endpointu nesmí spadnout
    session.expire_all()
    assert session.get(Pripad, 1).stav == "vyhrano", "změna stavu se ztratila"
    # Polovičatá práce spadlé akce se zahodila…
    assert session.query(CrmAktivita).filter(CrmAktivita.druh == "ukol").count() == 0
    # …ale chyba je v logu, aby ji šlo najít.
    assert [v for v, _ in _behy(session)] == ["chyba"]


def test_zmena_stavu_prezije_i_bez_autoflushe(session):
    """Tentýž případ s VYPNUTÝM autoflushem — chování nesmí záviset na něm.

    Automatika běží uvnitř `zmen_stav_*`, kde je změna stavu v session ještě
    neflushnutá. Kdyby se na autoflush spoléhala, `no_autoflush` u volajícího
    (nebo `autoflush=False` na session) by z toho udělal tichou ztrátu přesunu
    v kanbanu. Proto se flushuje explicitně před savepointem.
    """
    _pravidlo(session)
    pripad = Pripad(id=1, stav="novy")
    session.add(pripad)
    session.commit()
    session.autoflush = False
    pripad.stav = "vyhrano"

    def _spadne(db, e, z, p, u):
        db.add(CrmAktivita(entita="op", zaznam_id=1, druh="ukol", nazev="půl práce"))
        db.flush()
        raise RuntimeError("chyba akce")

    automatizace.VYKONAVACE["test"] = _spadne
    try:
        automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("test", None)
        session.autoflush = True

    session.commit()
    session.expire_all()
    assert session.get(Pripad, 1).stav == "vyhrano", "změna stavu se ztratila v savepointu"


def test_dve_pravidla_na_stejnem_stavu_bezi_obe(session):
    _pravidlo(session, akce="prvni")
    _pravidlo(session, akce="druha")
    automatizace.VYKONAVACE["prvni"] = lambda db, e, z, p, u: "A"
    automatizace.VYKONAVACE["druha"] = lambda db, e, z, p, u: "B"
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("prvni", None)
        automatizace.VYKONAVACE.pop("druha", None)
    assert hotove == ["A", "B"]


def test_selhani_prvniho_pravidla_nezastavi_druhe(session):
    """Jedno rozbité pravidlo nesmí vypnout automatiku jako celek."""
    _pravidlo(session, akce="rozbite")
    _pravidlo(session, akce="funkcni")

    def _spadne(db, e, z, p, u):
        raise RuntimeError("chyba")

    automatizace.VYKONAVACE["rozbite"] = _spadne
    automatizace.VYKONAVACE["funkcni"] = lambda db, e, z, p, u: "B"
    try:
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    finally:
        automatizace.VYKONAVACE.pop("rozbite", None)
        automatizace.VYKONAVACE.pop("funkcni", None)
    assert hotove == ["B"]
    assert [v for v, _ in _behy(session)] == ["chyba", "hotovo"]


# ---- ověřování pravidla při ukládání ----------------------------------------
class _FakeDb:
    """Minimum pro `over_pravidlo`: dotaz na uživatele a `get` na šablonu."""

    def __init__(self, uzivatele=(7,), sablony=(3,)):
        self._uzivatele = set(uzivatele)
        self._sablony = set(sablony)

    def get(self, _model, ident):
        return object() if ident in self._sablony else None

    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return (7,) if self._uzivatele else None


@pytest.fixture()
def _stavy_existuji(monkeypatch):
    monkeypatch.setattr(automatizace.stavy_modul, "najdi", lambda db, e, k: object())


def test_neznama_akce_neprojde(_stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(_FakeDb(), "op", "vyhrano", "neexistuje", {})


def test_akce_od_spatne_entity_neprojde(_stavy_existuji):
    """„Založ objednávku" jde jen od případu — od projektu by nemělo co dělat."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(_FakeDb(), "pro", "dokonceno", "objednavka", {})


def test_ukol_bez_nazvu_neprojde(_stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(_FakeDb(), "nab", "odeslana", "ukol", {"za_dni": 7})


def test_ukol_ocisti_parametry(_stavy_existuji):
    ciste = automatizace.over_pravidlo(
        _FakeDb(),
        "nab",
        "odeslana",
        "ukol",
        {"za_dni": "7", "nazev": "  Zavolat  ", "text": "", "komu_user_id": 7},
    )
    assert ciste["za_dni"] == 7
    assert ciste["nazev"] == "Zavolat"
    assert ciste["komu_user_id"] == 7


def test_zaporny_odklad_se_srovna_na_nulu(_stavy_existuji):
    ciste = automatizace.over_pravidlo(
        _FakeDb(), "nab", "odeslana", "ukol", {"za_dni": -5, "nazev": "Hned"}
    )
    assert ciste["za_dni"] == 0


def test_neexistujici_sablona_neprojde(_stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            _FakeDb(sablony=()), "obj", "podepsana", "projekt", {"sablona_id": 99}
        )


def test_projekt_bez_sablony_projde(_stavy_existuji):
    """Bez zvolené šablony se vybírá podle kategorie případu — je to platná volba."""
    assert automatizace.over_pravidlo(_FakeDb(), "obj", "podepsana", "projekt", {}) == {}


def test_neexistujici_stav_neprojde(monkeypatch):
    monkeypatch.setattr(automatizace.stavy_modul, "najdi", lambda db, e, k: None)
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(_FakeDb(), "op", "neexistuje", "objednavka", {})
