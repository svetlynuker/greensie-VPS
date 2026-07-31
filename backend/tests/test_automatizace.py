"""Automatizace CRM (CRM-31) — motor pravidel „KDYŽ / POKUD / PAK".

Testuje se nad SQLite s náhradními modely (skutečné mají JSONB, které SQLite
nevytvoří), stejný postup jako u auditu. Mechanika spouštění je na konkrétních
sloupcích nezávislá.

Případy, kvůli kterým tenhle test existuje:

  * `test_pravidlo_bezi_na_zaznam_jen_jednou` — bez hlídání běhů vyrobí případ
    vrácený z „Vyhráno" do „Vyjednávání" a zpátky DRUHOU objednávku. Na živých
    datech se to pozná až tím, že zákazník dostane dvě objednávky.
  * `test_selhani_kroku_nezrusi_predchozi_zmeny` — kdyby se chyba akce řešila
    `db.rollback()`, zahodila by i změnu stavu, kterou právě udělal člověk.
    Přesun v kanbanu by tiše zmizel. Proto savepoint.
  * `test_smycka_se_zastavi` — od chvíle, kdy umí pravidlo měnit stav, se dvě
    pravidla můžou spouštět navzájem. Bez pojistky by to zacyklilo request.
  * `test_nanecisto_nic_neposle` — suchý běh, kterému by proklouzl e-mail, je
    horší než žádný suchý běh: člověk mu přestane věřit.
"""

import pytest
from sqlalchemy import (
    JSON,
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
from app.crm import automatizace_akce

Base = declarative_base()


class CrmPravidlo(Base):
    __tablename__ = "crm_pravidla"
    id = Column(Integer, primary_key=True)
    nazev = Column(String)
    aktivni = Column(Boolean, default=True)
    poradi = Column(Integer, default=0)
    spoust_entita = Column(String)
    spoust_typ = Column(String, default="stav")
    spoust_stav = Column(String, default="")
    spoust_pole = Column(String, default="")
    cas_nastaveni = Column(JSON, default=dict)
    podminky = Column(JSON, default=dict)
    kroky = Column(JSON, default=list)
    opakovat = Column(String, default="jednou")
    akce = Column(String, nullable=True)
    nastaveni = Column(JSON, default=dict)


class CrmPravidloBeh(Base):
    __tablename__ = "crm_pravidlo_behy"
    id = Column(Integer, primary_key=True)
    pravidlo_id = Column(Integer)
    entita = Column(String)
    zaznam_id = Column(Integer)
    klic_behu = Column(String, default="")
    vysledek = Column(String, default="hotovo")
    popis = Column(Text, default="")
    spoustec = Column(String, default="")
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
    hodnota_kc = Column(Integer)
    vlastnik_user_id = Column(Integer)


class _Uzivatel:
    def __init__(self, id=7):
        self.id = id
        self.jmeno = "Tester"
        self.email = "tester@greensie.cz"


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


def _pravidlo(
    s,
    akce="test",
    stav="vyhrano",
    entita="op",
    kroky=None,
    podminky=None,
    opakovat="jednou",
    spoust_typ="stav",
):
    p = CrmPravidlo(
        nazev="Pravidlo",
        aktivni=True,
        poradi=0,
        spoust_entita=entita,
        spoust_typ=spoust_typ,
        spoust_stav=stav,
        kroky=kroky if kroky is not None else [{"akce": akce, "nastaveni": {}}],
        podminky=podminky or {},
        opakovat=opakovat,
    )
    s.add(p)
    s.commit()
    return p


def _behy(s):
    return [(b.vysledek, b.popis) for b in s.query(CrmPravidloBeh).order_by(CrmPravidloBeh.id)]


def _vykonavac(klic, funkce):
    """Dočasně zaregistruje testovací akci. Vrací context manager."""

    class _Docasne:
        def __enter__(self):
            automatizace.VYKONAVACE[klic] = funkce
            return funkce

        def __exit__(self, *_a):
            automatizace.VYKONAVACE.pop(klic, None)

    return _Docasne()


# ---- struktura katalogu ------------------------------------------------------
def test_kazda_akce_ma_vykonavace():
    """Akce v katalogu bez funkce by v nastavení šla vybrat a nikdy by nezabrala."""
    assert set(automatizace.MAPA_AKCI) == set(automatizace.VYKONAVACE)


def test_akce_spoustene_jen_ze_znamych_entit():
    for a in automatizace.AKCE:
        assert a["entity"], f"akce {a['klic']} nemá žádnou spouštěcí entitu"
        for e in a["entity"]:
            assert e in automatizace.SPOUSTECI_ENTITY


def test_kazdy_spoustec_ma_smysl():
    """Spouštěč bez obsluhy by šel v UI vybrat a pravidlo by nikdy nezabralo."""
    obsluhovane = {"stav", "vznik", "pole", "cas", "rucne"}
    assert {s["klic"] for s in automatizace.SPOUSTECE} == obsluhovane


def test_vychozi_pravidla_miri_na_existujici_akce_a_stavy():
    """Výchozí pravidla musí trefit klíče z výchozí sady stavů.

    Překlep by znamenal pravidlo, které se v nastavení tváří funkčně, ale
    nikdy se nespustí — a nikdo by nepoznal proč.
    """
    from app.crm.stavy import VYCHOZI_STAVY

    for p in automatizace.VYCHOZI_PRAVIDLA:
        klice = {s["klic"] for s in VYCHOZI_STAVY[p["spoust_entita"]]}
        assert p["spoust_stav"] in klice, f"{p['nazev']}: stav {p['spoust_stav']} neexistuje"
        for krok in p["kroky"]:
            assert krok["akce"] in automatizace.MAPA_AKCI
            # A akce musí umět pracovat od té entity, na které pravidlo visí.
            assert p["spoust_entita"] in automatizace.MAPA_AKCI[krok["akce"]]["entity"]


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
    with _vykonavac("test", lambda db, k, n: "Založena objednávka OBJ-26-0001"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())

    assert hotove == ["Založena objednávka OBJ-26-0001"]
    assert _behy(session) == [("hotovo", "Založena objednávka OBJ-26-0001")]
    # Poznámka v aktivitách je to místo, kde si člověk přečte, co appka udělala.
    poznamky = session.query(CrmAktivita).all()
    assert len(poznamky) == 1
    assert poznamky[0].druh == "poznamka"
    assert pravidlo.nazev in poznamky[0].text


def test_beh_si_pamatuje_cim_se_spustil(session):
    """V logu musí být poznat, jestli to udělal kanban, nebo noční plánovač."""
    _pravidlo(session)
    with _vykonavac("test", lambda db, k, n: "Hotovo"):
        automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    beh = session.query(CrmPravidloBeh).one()
    assert beh.spoustec == "stav"


def test_pravidlo_bezi_na_zaznam_jen_jednou(session):
    """Případ vrácený zpátky a znovu vyhraný nesmí vyrobit druhou objednávku."""
    _pravidlo(session)
    with _vykonavac("test", lambda db, k, n: "Založena objednávka"):
        prvni = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
        druhy = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())

        assert prvni == ["Založena objednávka"]
        assert druhy == [], "pravidlo se u téhož záznamu spustilo dvakrát"
        assert len(_behy(session)) == 1
        # Jiný záznam se ale spustit musí – limit je na záznam, ne na pravidlo.
        jiny = automatizace.po_zmene_stavu(session, "op", Pripad(id=2), "vyhrano", _Uzivatel())
    assert jiny == ["Založena objednávka"]


def test_opakovatelne_pravidlo_bezi_znovu(session):
    """U „změní se pole“ je opakování to, co člověk čeká — jednou by bylo k ničemu."""
    _pravidlo(session, opakovat="vzdy")
    with _vykonavac("test", lambda db, k, n: "Provedeno"):
        prvni = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
        druhy = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert prvni == ["Provedeno"]
    assert druhy == ["Provedeno"]
    assert len(_behy(session)) == 2


def test_vypnute_pravidlo_se_nespusti(session):
    p = _pravidlo(session)
    p.aktivni = False
    session.commit()
    with _vykonavac("test", lambda db, k, n: "Nemělo proběhnout"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == []
    assert _behy(session) == []


def test_jiny_stav_pravidlo_nespusti(session):
    _pravidlo(session, stav="vyhrano")
    with _vykonavac("test", lambda db, k, n: "Nemělo proběhnout"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "prohrano", _Uzivatel())
    assert hotove == []


def test_spoustec_vzniku_nereaguje_na_stav(session):
    """Pravidlo „když záznam vznikne“ se nesmí spustit při přesunu v kanbanu."""
    _pravidlo(session, spoust_typ="vznik", stav="")
    with _vykonavac("test", lambda db, k, n: "Nemělo proběhnout"):
        pri_stavu = automatizace.po_zmene_stavu(
            session, "op", Pripad(id=1), "vyhrano", _Uzivatel()
        )
        pri_vzniku = automatizace.po_vzniku(session, "op", Pripad(id=2), _Uzivatel())
    assert pri_stavu == []
    assert pri_vzniku == ["Nemělo proběhnout"]


def test_preskoceni_se_zaloguje(session):
    """„Nic se nestalo" musí být v logu vidět, jinak to vypadá jako nefunkční pravidlo."""
    _pravidlo(session)
    with _vykonavac("test", lambda db, k, n: ""):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == []
    assert [v for v, _ in _behy(session)] == ["preskoceno"]


# ---- řetěz kroků -------------------------------------------------------------
def test_kroky_bezi_v_poradi(session):
    """„Založ projekt a pošli e-mail" je jeden postup, ne dvě pravidla."""
    _pravidlo(
        session,
        kroky=[
            {"akce": "prvni", "nastaveni": {}},
            {"akce": "druhy", "nastaveni": {}},
            {"akce": "treti", "nastaveni": {}},
        ],
    )
    with _vykonavac("prvni", lambda db, k, n: "A"), _vykonavac(
        "druhy", lambda db, k, n: "B"
    ), _vykonavac("treti", lambda db, k, n: "C"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == ["A", "B", "C"]
    # Jeden běh se všemi kroky, ne tři – je to jedno pravidlo.
    assert len(_behy(session)) == 1
    assert "A; B; C" in _behy(session)[0][1]


def test_chyba_jednoho_kroku_nezastavi_ostatni(session):
    """Po spadlém e-mailu má zbytek postupu doběhnout — projekt už stejně vznikl."""

    def _spadne(db, k, n):
        raise RuntimeError("SMTP nedostupné")

    _pravidlo(
        session,
        kroky=[
            {"akce": "prvni", "nastaveni": {}},
            {"akce": "rozbity", "nastaveni": {}},
            {"akce": "treti", "nastaveni": {}},
        ],
    )
    with _vykonavac("prvni", lambda db, k, n: "A"), _vykonavac(
        "rozbity", _spadne
    ), _vykonavac("treti", lambda db, k, n: "C"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == ["A", "C"]
    vysledek, popis = _behy(session)[0]
    # Uspělo něco → „hotovo“, ale v popisu musí být vidět, co selhalo.
    assert vysledek == "hotovo"
    assert "selhalo" in popis


def test_krok_dostane_svoje_nastaveni(session):
    """Dva kroky téže akce s jinými parametry — nesmí si je poplést."""
    videne = []
    _pravidlo(
        session,
        kroky=[
            {"akce": "test", "nastaveni": {"za_dni": 3}},
            {"akce": "test", "nastaveni": {"za_dni": 10}},
        ],
    )

    def _zapamatuj(db, k, n):
        videne.append(n.get("za_dni"))
        return f"úkol za {n.get('za_dni')}"

    with _vykonavac("test", _zapamatuj):
        automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert videne == [3, 10]


# ---- podmínky ----------------------------------------------------------------
def test_nesplnene_podminky_pravidlo_nespusti(session):
    """Bez tohohle by pravidlo pro FVE zakládalo projekty i u peak shavingu."""
    _pravidlo(
        session,
        podminky={
            "spojka": "vse",
            "polozky": [{"pole": "hodnota_kc", "operator": "vetsi", "hodnota": "500000"}],
        },
    )
    with _vykonavac("test", lambda db, k, n: "Provedeno"):
        maly = automatizace.po_zmene_stavu(
            session, "op", Pripad(id=1, hodnota_kc=100_000), "vyhrano", _Uzivatel()
        )
        velky = automatizace.po_zmene_stavu(
            session, "op", Pripad(id=2, hodnota_kc=900_000), "vyhrano", _Uzivatel()
        )
    assert maly == []
    assert velky == ["Provedeno"]


def test_nesplnene_podminky_u_jednou_nezablokuji_priste(session):
    """Podmínky dnes neplatí, zítra ano — pravidlo musí dostat druhou šanci.

    Kdyby se „nesplněno" zapsalo jako běh, `opakovat="jednou"` by pravidlo na
    ten záznam už nikdy nepustilo. Případ za milion by tak zůstal bez objednávky
    jenom proto, že se přes „Vyhráno" mihnul dřív, než měl vyplněnou hodnotu.
    """
    _pravidlo(
        session,
        podminky={
            "spojka": "vse",
            "polozky": [{"pole": "hodnota_kc", "operator": "neprazdne"}],
        },
    )
    pripad = Pripad(id=1, hodnota_kc=None)
    with _vykonavac("test", lambda db, k, n: "Provedeno"):
        prvni = automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())
        pripad.hodnota_kc = 750_000
        druhy = automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())
    assert prvni == []
    assert druhy == ["Provedeno"]


# ---- selhání a transakce -----------------------------------------------------
def test_selhani_kroku_nezrusi_predchozi_zmeny(session):
    """Klíčový případ: chyba automatiky nesmí zahodit přesun, který udělal člověk.

    Simuluje endpoint: nejdřív se změní stav (jako `zmen_stav_pripadu`), pak se
    volá automatika. Když akce spadne, změna stavu musí přežít a commit projít.
    """
    _pravidlo(session)
    pripad = Pripad(id=1, stav="novy")
    session.add(pripad)
    session.commit()

    pripad.stav = "vyhrano"  # to, co udělal člověk v kanbanu

    def _spadne(db, k, n):
        # Akce nastihne něco zapsat a pak selže – přesně případ, kdy je session
        # rozbitá a naivní ošetření by muselo volat rollback.
        db.add(CrmAktivita(entita="op", zaznam_id=1, druh="ukol", nazev="půl práce"))
        db.flush()
        raise RuntimeError("šablona neexistuje")

    with _vykonavac("test", _spadne):
        hotove = automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())

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

    def _spadne(db, k, n):
        db.add(CrmAktivita(entita="op", zaznam_id=1, druh="ukol", nazev="půl práce"))
        db.flush()
        raise RuntimeError("chyba akce")

    try:
        with _vykonavac("test", _spadne):
            automatizace.po_zmene_stavu(session, "op", pripad, "vyhrano", _Uzivatel())
    finally:
        session.autoflush = True

    session.commit()
    session.expire_all()
    assert session.get(Pripad, 1).stav == "vyhrano", "změna stavu se ztratila v savepointu"


def test_dve_pravidla_na_stejnem_stavu_bezi_obe(session):
    _pravidlo(session, akce="prvni")
    _pravidlo(session, akce="druha")
    with _vykonavac("prvni", lambda db, k, n: "A"), _vykonavac("druha", lambda db, k, n: "B"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == ["A", "B"]


def test_selhani_prvniho_pravidla_nezastavi_druhe(session):
    """Jedno rozbité pravidlo nesmí vypnout automatiku jako celek."""
    _pravidlo(session, akce="rozbite")
    _pravidlo(session, akce="funkcni")

    def _spadne(db, k, n):
        raise RuntimeError("chyba")

    with _vykonavac("rozbite", _spadne), _vykonavac("funkcni", lambda db, k, n: "B"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == ["B"]
    assert [v for v, _ in _behy(session)] == ["chyba", "hotovo"]


# ---- ochrana proti smyčce ----------------------------------------------------
def test_smycka_se_zastavi(session):
    """Dvě pravidla, která se spouštějí navzájem, nesmí zacyklit request.

    Bez pojistky by „A přesune do stavu X" a „X přesune do stavu A" běhaly
    dokola, dokud request nespadne na rekurzi — a člověk by přitom jen přetáhl
    kartu v kanbanu.
    """
    _pravidlo(session, akce="tam", stav="realizace")
    _pravidlo(session, akce="zpet", stav="predani")
    pocty = {"tam": 0, "zpet": 0}

    def _tam(db, kontext, n):
        pocty["tam"] += 1
        automatizace.po_zmene_stavu(db, "op", kontext.zaznam, "predani", kontext.user, rodic=kontext)
        return "→ předání"

    def _zpet(db, kontext, n):
        pocty["zpet"] += 1
        automatizace.po_zmene_stavu(
            db, "op", kontext.zaznam, "realizace", kontext.user, rodic=kontext
        )
        return "→ realizace"

    with _vykonavac("tam", _tam), _vykonavac("zpet", _zpet):
        automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "realizace", _Uzivatel())

    # Každé pravidlo nejvýš jednou za řetěz – to je ta silnější ze dvou pojistek.
    assert pocty == {"tam": 1, "zpet": 1}


def test_hloubka_retezu_je_omezena(session):
    """I když se pravidla neopakují, řetěz nesmí být nekonečný.

    Každý stav má vlastní pravidlo, takže ochrana „jedno pravidlo jednou za
    řetěz“ tady nezabere — utnout to musí `MAX_HLOUBKA`.
    """
    hloubky = []
    _pravidlo(session, akce="dal", stav="start")
    for i in range(1, 10):
        _pravidlo(session, akce="dal", stav=f"stav{i}")

    def _dal(db, kontext, n):
        hloubky.append(kontext.hloubka)
        automatizace.po_zmene_stavu(
            db, "op", kontext.zaznam, f"stav{len(hloubky)}", kontext.user, rodic=kontext
        )
        return "krok"

    with _vykonavac("dal", _dal):
        automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "start", _Uzivatel())

    assert hloubky, "řetěz se nespustil vůbec"
    assert max(hloubky) <= automatizace.MAX_HLOUBKA
    assert len(hloubky) <= automatizace.MAX_HLOUBKA + 1


# ---- suchý běh ---------------------------------------------------------------
def test_nanecisto_nic_neposle(session):
    """Náhled nesmí odeslat e-mail — ten se z internetu nevrátí.

    Kontroluje se to na katalogu akcí, ne na jedné funkci: každá akce, která
    komunikuje ven, se musí podívat na `kontext.nanecisto`. Nová akce, která na
    to zapomene, shodí tenhle test.
    """
    import inspect

    for klic in ("email", "notifikace"):
        zdroj = inspect.getsource(automatizace.VYKONAVACE[klic])
        assert "nanecisto" in zdroj, f"akce „{klic}“ neřeší suchý běh"


def test_nanecisto_nezapise_beh(session):
    """Zkoušení pravidla nesmí zaplevelit log běhů ani ho označit za proběhlé."""
    pravidlo = _pravidlo(session)
    pripad = Pripad(id=1)
    session.add(pripad)
    session.commit()

    with _vykonavac("test", lambda db, k, n: "Založena objednávka"):
        kroky = automatizace.spust_rucne(session, pravidlo, pripad, _Uzivatel(), nanecisto=True)

    assert kroky == ["Založena objednávka"]
    assert _behy(session) == [], "suchý běh zapsal běh do logu"
    assert session.query(CrmAktivita).count() == 0, "suchý běh zapsal poznámku"


def test_rucni_spusteni_zapise_beh(session):
    """Ruční spuštění je běh jako každý jiný — musí být v logu vidět."""
    pravidlo = _pravidlo(session, spoust_typ="rucne", stav="")
    pripad = Pripad(id=1)
    session.add(pripad)
    session.commit()

    with _vykonavac("test", lambda db, k, n: "Provedeno"):
        kroky = automatizace.spust_rucne(session, pravidlo, pripad, _Uzivatel())

    assert kroky == ["Provedeno"]
    assert [(v, b) for v, b in _behy(session)] == [("hotovo", "Provedeno")]
    assert session.query(CrmPravidloBeh).one().spoustec == "rucne"


# ---- staré pravidlo (jedna akce) ---------------------------------------------
def test_stare_pravidlo_bez_kroku_dal_funguje(session):
    """Řádek z první dávky (akce + nastavení) musí fungovat i bez překlopení.

    Migrace ho při nasazení přepíše do `kroky`, ale spoléhat se jen na ni by
    znamenalo, že pravidlo mezi nasazením a migrací tiše nedělá nic.
    """
    p = CrmPravidlo(
        nazev="Staré",
        aktivni=True,
        spoust_entita="op",
        spoust_typ="stav",
        spoust_stav="vyhrano",
        kroky=[],
        akce="test",
        nastaveni={"za_dni": 5},
    )
    session.add(p)
    session.commit()

    videne = []
    with _vykonavac("test", lambda db, k, n: videne.append(n) or "Provedeno"):
        hotove = automatizace.po_zmene_stavu(session, "op", Pripad(id=1), "vyhrano", _Uzivatel())
    assert hotove == ["Provedeno"]
    assert videne == [{"za_dni": 5}]


# ---- popisy pro UI -----------------------------------------------------------
def test_kazda_akce_ma_popis_v_katalogu():
    """Bez popisu si člověk v nastavení nevybere — a vybere špatně."""
    for a in automatizace.AKCE:
        assert a["nazev"] and a["popis"], f"akce {a['klic']} nemá popis"
    for s in automatizace.SPOUSTECE:
        assert s["nazev"] and s["popis"], f"spouštěč {s['klic']} nemá popis"


def test_prijemci_zprav_jsou_znami():
    """Volba adresáta, kterou akce neumí obsloužit, by tiše nic neposlala."""
    klice = {p["klic"] for p in automatizace_akce.PRIJEMCI}
    assert klice == {"vlastnik", "spoluvlastnici", "konkretni", "adresa"}
