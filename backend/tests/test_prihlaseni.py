"""Historie přihlášení — zápis pokusů a odvozené přehledy.

Testuje se nad SQLite s reálným modelem `Prihlaseni` (má jen běžné typy, takže
ho SQLite vytvoří). Nejdůležitější případ je `test_neznamy_ucet_neuklada_email`:
do pole s e-mailem si člověk občas napíše heslo a naivní implementace by ho
uložila natrvalo do bezpečnostní evidence, kterou nikdo nemaže.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.logy.models import Prihlaseni
from app.logy.prihlaseni import (
    pocet_neuspechu,
    popis_zarizeni,
    posledni_prihlaseni,
    zaznamenej_prihlaseni,
)

CHROME_WIN = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


class FalesnyRequest:
    """Náhrada za Starlette Request — stačí hlavičky a klient."""

    def __init__(self, hlavicky=None, ip="10.0.0.9"):
        self.headers = hlavicky or {}
        self.client = type("K", (), {"host": ip})()


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Prihlaseni.__table__.create(engine)
    with Session(engine) as s:
        yield s


def test_uspesne_prihlaseni_ulozi_kdo_odkud_a_cim(db):
    zaznamenej_prihlaseni(
        db,
        request=FalesnyRequest({"user-agent": CHROME_WIN}),
        uspech=True,
        uzivatel_id=1,
        uzivatel_email="dan@greensie.cz",
        uzivatel_jmeno="Daniel Lupínek",
    )
    z = db.query(Prihlaseni).one()
    assert z.uspech is True
    assert z.uzivatel_email == "dan@greensie.cz"
    assert z.uzivatel_jmeno == "Daniel Lupínek"
    assert z.ip == "10.0.0.9"
    assert z.zarizeni == "Chrome na Windows"


def test_neznamy_ucet_neuklada_email(db):
    """U neznámého účtu se surový vstup neukládá — mohlo by to být heslo."""
    zaznamenej_prihlaseni(
        db,
        request=FalesnyRequest(),
        uspech=False,
        duvod="neznámý účet",
    )
    z = db.query(Prihlaseni).one()
    assert z.uzivatel_email is None
    assert z.uzivatel_id is None
    assert z.duvod == "neznámý účet"


def test_ip_bere_posledni_prvek_x_forwarded_for(db):
    """Za proxy je pravá IP poslední; dřívější prvky si klient může podvrhnout."""
    zaznamenej_prihlaseni(
        db,
        request=FalesnyRequest({"x-forwarded-for": "1.2.3.4, 89.24.0.1"}),
        uspech=True,
        uzivatel_id=1,
    )
    assert db.query(Prihlaseni).one().ip == "89.24.0.1"


def test_zapis_nesmi_shodit_prihlaseni(db):
    """Když evidence selže, přihlášení musí projít dál (chyba se spolkne)."""

    class RozbityRequest:
        @property
        def headers(self):
            raise RuntimeError("rozbité hlavičky")

    zaznamenej_prihlaseni(db, request=RozbityRequest(), uspech=True, uzivatel_id=1)
    assert db.query(Prihlaseni).count() == 0


def test_posledni_prihlaseni_bere_jen_uspesna(db):
    stary = datetime.now(timezone.utc) - timedelta(days=3)
    db.add_all(
        [
            Prihlaseni(uzivatel_id=1, uspech=True, cas=stary),
            Prihlaseni(uzivatel_id=1, uspech=False, cas=datetime.now(timezone.utc)),
            Prihlaseni(uzivatel_id=2, uspech=False, cas=datetime.now(timezone.utc)),
        ]
    )
    db.commit()
    mapa = posledni_prihlaseni(db, [1, 2, 3])
    # uživatel 1 má poslední ÚSPĚŠNÉ před třemi dny, ne dnešní nezdar
    assert mapa[1].date() == stary.date()
    # kdo se nikdy nepřihlásil, v mapě není (2 má jen nezdar, 3 nic)
    assert 2 not in mapa and 3 not in mapa


def test_pocet_neuspechu_jen_za_okno(db):
    db.add_all(
        [
            Prihlaseni(uspech=False, cas=datetime.now(timezone.utc) - timedelta(hours=2)),
            Prihlaseni(uspech=False, cas=datetime.now(timezone.utc) - timedelta(days=5)),
            Prihlaseni(uspech=True, cas=datetime.now(timezone.utc)),
        ]
    )
    db.commit()
    assert pocet_neuspechu(db, 24) == 1


@pytest.mark.parametrize(
    "ua,ceka",
    [
        (CHROME_WIN, "Chrome na Windows"),
        (SAFARI_IPHONE, "Safari na iPhonu"),
        ("Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0", "Firefox na Linuxu"),
        # Edge se hlásí i jako Chrome — musí vyhrát to užší
        (CHROME_WIN + " Edg/126.0.0.0", "Edge na Windows"),
        (None, None),
        ("", None),
    ],
)
def test_popis_zarizeni(ua, ceka):
    assert popis_zarizeni(ua) == ceka
