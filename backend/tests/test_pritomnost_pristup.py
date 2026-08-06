"""Přítomnost: druhá vrstva kontroly — smí ten člověk vidět TENHLE záznam?

POINTA CELÉHO SOUBORU: seznam přítomných i razítko se ptají na konkrétní
`entita_id`. Modulové právo (`obchodni_pripady`) na to nestačí — bez práva
`crm_vse` vidí člověk v CRM jen svoje záznamy. Kdyby endpoint přítomnosti
kontroloval jen právo na modul, dalo by se zkoušením ID zjistit, že cizí
obchodní případ existuje a kdo na něm právě pracuje: odpověď „na případu 412
je Alena“ prozradí i to, že případ 412 vůbec je, i kdo ho vede. Přesně tomu
brání 404 místo 403 v `crm/pristup.py` — a `ma_pristup` je totéž pravidlo
přenesené na přítomnost.

Pravidla se přitom neopisují: `registr._pristup_crm` použije
`Entita.overit_pristup` z `crm/pole_zaznamu.py`, tedy tutéž kontrolu jako
ukládání a audit. Dvě kopie stejného pravidla by se rozešly a jedna z nich
by pouštěla dál, než má — proto se tady testuje i to, co z toho vyplývá
(dědění práv od zákazníka a od obchodního případu).

Testuje se bez databáze:

- uživatel je lehký objekt — `prava_uzivatele()` čte jen `je_admin`,
  `extra_prava` a `skupina` (stejný postup jako `tests/test_prava_prirazovani.py`);
  `User.__table__.create` na SQLite spadne kvůli postgresovému ARRAY,
- `db` je náhrada s metodou `get()` — jediné, co kontroly potřebují. Navíc si
  pamatuje dotazy, takže je na čem ukázat, že se u „celého modulu“ do
  databáze vůbec nechodí.
"""

from types import SimpleNamespace

# Bez těchhle importů se nezkonfigurují mappery a spadne i vznik obyčejného
# `ObchodniPripad()` — modely CRM mají vazby do jiných modulů (`Faktura`,
# `Projekt`). V aplikaci je registruje `app/main.py`, který se v testech
# importovat nesmí (na produkčním `.env` by zmigroval produkční databázi).
import app.auth.models  # noqa: F401 - registrace modelů
import app.finance.models  # noqa: F401 - registrace modelů
import app.matice.models  # noqa: F401 - registrace modelů
import app.nabidkovac.models  # noqa: F401 - registrace modelů
from app.crm.models import ObchodniPripad, Zakaznik, ZakaznikKontakt
from app.nabidkovac.models import Nabidka
from app.pritomnost import registr

CIZI = 41  # id uživatele, který na případu nedělá
MUJ = 7  # id vlastníka


def _uzivatel(id_, admin=False, extra=(), skupina_prava=None):
    skupina = None if skupina_prava is None else SimpleNamespace(prava=list(skupina_prava))
    return SimpleNamespace(id=id_, je_admin=admin, extra_prava=list(extra), skupina=skupina)


class _FalesnaDB:
    """Náhrada session: kontroly přístupu z ní volají jen `db.get(model, id)`."""

    def __init__(self, *zaznamy):
        self._data = {(type(z), z.id): z for z in zaznamy}
        self.dotazy: list[tuple[str, object]] = []

    def get(self, model, id_):
        self.dotazy.append((model.__name__, id_))
        return self._data.get((model, id_))


class _ZakazanaDB:
    """Databáze, která při jakémkoli dotazu spadne — na důkaz, že se nesáhne."""

    def get(self, model, id_):  # pragma: no cover - volání je právě to, co testujeme
        raise AssertionError("databáze se tady dotazovat nemá")


def _op(id_=412, vlastnik=MUJ, spoluvlastnici=()):
    return ObchodniPripad(id=id_, vlastnik_user_id=vlastnik, spoluvlastnici=list(spoluvlastnici))


# ---- celý modul vs. konkrétní záznam ----------------------------------------
def test_prazdne_id_znamena_cely_modul_a_prochazi():
    """Matice a kanban se zobrazují celé — tam platí modulové právo a per-záznamová
    kontrola nemá co kontrolovat. Databáze se přitom vůbec nesmí dotazovat."""
    kdokoli = _uzivatel(CIZI)
    assert registr.ma_pristup(_ZakazanaDB(), kdokoli, "crm_op", "") is True
    assert registr.ma_pristup(_ZakazanaDB(), kdokoli, "matice", "") is True


def test_entita_bez_zapsane_funkce_pristup_prochazi():
    """U matice není druhá vrstva potřeba: kdo ji smí otevřít, vidí ji celou.
    Chybějící `pristup` proto znamená „ano“, ne „ne“ — jinak by se nový modul
    po přidání do registru tiše nezobrazoval nikomu."""
    assert "pristup" not in registr.ENTITY["matice"]
    assert registr.ma_pristup(_ZakazanaDB(), _uzivatel(CIZI), "matice", "1||2") is True


# ---- obchodní případ: vlastník / spoluvlastník / crm_vse --------------------
def test_cizi_pripad_clovek_bez_prava_crm_vse_nevidi():
    """Tohle je ta ochrana: bez ní by šlo zkoušením ID zjistit, že cizí případ
    existuje a kdo na něm dělá."""
    db = _FalesnaDB(_op(vlastnik=MUJ))
    assert registr.ma_pristup(db, _uzivatel(CIZI), "crm_op", "412") is False
    # a opravdu se na ten záznam ptal, takže „False“ není z jiného důvodu
    assert ("ObchodniPripad", 412) in db.dotazy


def test_vlastnik_svuj_pripad_vidi():
    db = _FalesnaDB(_op(vlastnik=MUJ))
    assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_op", "412") is True


def test_spoluvlastnik_pripad_vidi():
    """Spoluvlastníci existují kvůli zástupům (dovolená) a tandemu OZ + technik."""
    db = _FalesnaDB(_op(vlastnik=MUJ, spoluvlastnici=[CIZI, 9]))
    assert registr.ma_pristup(db, _uzivatel(CIZI), "crm_op", "412") is True


def test_pravo_crm_vse_vidi_i_cizi_pripad():
    """Vedení vidí vše. Právo může přijít ze skupiny i z individuální výjimky —
    obojí musí fungovat stejně, jinak by „přidělil jsem právo“ neplatilo."""
    db = _FalesnaDB(_op(vlastnik=MUJ))
    ze_skupiny = _uzivatel(CIZI, skupina_prava=["obchodni_pripady", "crm_vse"])
    vyjimkou = _uzivatel(CIZI, extra=["crm_vse"])
    assert registr.ma_pristup(db, ze_skupiny, "crm_op", "412") is True
    assert registr.ma_pristup(db, vyjimkou, "crm_op", "412") is True


def test_superspravce_vidi_vse():
    db = _FalesnaDB(_op(vlastnik=MUJ))
    assert registr.ma_pristup(db, _uzivatel(CIZI, admin=True), "crm_op", "412") is True


def test_neexistujici_id_je_false_i_pro_vlastnika():
    """Neexistující záznam se chová jako neviditelný — endpoint z toho udělá 404,
    takže se z odpovědi nedá poznat rozdíl mezi „není“ a „není tvůj“."""
    db = _FalesnaDB(_op(id_=412, vlastnik=MUJ))
    assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_op", "999") is False


def test_necislene_id_je_false_a_databaze_se_nedotazuje():
    """`entita_id` chodí z prohlížeče jako text. Nesmysl musí skončit „ne“,
    ne výjimkou z `int()` — to by byla 500 na každém pokusu."""
    db = _FalesnaDB(_op(vlastnik=MUJ))
    for nesmysl in ("abc", "1||2", "12x", " ", "-"):
        assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_op", nesmysl) is False
    assert db.dotazy == []


# ---- dědění práv: kontakt od zákazníka, nabídka od případu ------------------
def test_kontakt_dedi_viditelnost_od_zakaznika():
    """Kontaktní osoba vlastníka nemá — kontroluje se zákazník, pod kterého
    patří. Bez toho by se přes kontakty dalo obejít celé omezení na svoje
    záznamy (jméno a telefon cizího klienta je citlivější než jeho karta)."""
    zakaznik = Zakaznik(id=5, vlastnik_user_id=MUJ, spoluvlastnici=[])
    kontakt = ZakaznikKontakt(id=88, zakaznik_id=5)
    db = _FalesnaDB(zakaznik, kontakt)

    assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_kontakt", "88") is True
    assert registr.ma_pristup(db, _uzivatel(CIZI), "crm_kontakt", "88") is False


def test_nabidka_dedi_viditelnost_od_obchodniho_pripadu():
    """Nabídka vlastníka nemá — visí na případu, takže se práva berou od něj."""
    nabidka = Nabidka(id=300, obchodni_pripad_id=412)
    db = _FalesnaDB(nabidka, _op(id_=412, vlastnik=MUJ))

    assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_nab", "300") is True
    assert registr.ma_pristup(db, _uzivatel(CIZI), "crm_nab", "300") is False


def test_nabidka_bez_pripadu_patri_jen_pravu_crm_vse():
    """Nabídky z nabídkovače před CRM nemají případ ani vlastníka. „Nikomu
    nepatřící“ data se nesmí zjevit všem — vidí je jen `crm_vse`."""
    db = _FalesnaDB(Nabidka(id=301, obchodni_pripad_id=None))

    assert registr.ma_pristup(db, _uzivatel(MUJ), "crm_nab", "301") is False
    assert registr.ma_pristup(db, _uzivatel(MUJ, extra=["crm_vse"]), "crm_nab", "301") is True


# ---- neznámý typ zastaví modulové právo, ne tahle funkce --------------------
def test_neznamy_typ_zastavi_pravo_na_modul():
    """`ma_pristup` u neznámého typu vrací True — odmítá ho `pravo_pro()`, které
    vrátí None, a endpoint bez práva požadavek nepustí. Kdyby se to obrátilo,
    každý nový modul by musel mít funkci `pristup`, nebo by nefungoval."""
    assert registr.pravo_pro("neco-vymysleneho") is None
    assert registr.ma_pristup(_ZakazanaDB(), _uzivatel(MUJ), "neco-vymysleneho", "1") is True


# ---- razítko: co jde bez databáze ------------------------------------------
def test_razitko_crm_snese_necislene_id():
    """Razítko chodí ze stejné adresy jako přítomnost, takže musí snést i
    nesmyslné ID — prázdný podpis znamená „není co přenačítat“."""
    assert registr.razitko(_ZakazanaDB(), "crm_op", "abc") == ""
    assert registr.razitko(_ZakazanaDB(), "crm_zakaznik", "") == ""
    assert registr.razitko(_ZakazanaDB(), "neco-vymysleneho", "1") == ""


def test_kazda_entita_v_registru_ma_pravo_i_razitko():
    """Zapsat entitu bez práva by z ní udělalo dírku: seznam přítomných (nebo
    razítko, ze kterého je vidět počet záznamů) by se vrátil komukoli
    přihlášenému."""
    for typ, zapis in registr.ENTITY.items():
        assert zapis.get("pravo"), f"entita {typ} nemá právo"
        assert callable(zapis.get("razitko")), f"entita {typ} nemá razítko"


def test_kazdy_detail_crm_ma_i_kontrolu_zaznamu():
    """Entity CRM s konkrétním záznamem musí mít druhou vrstvu. Razítka celých
    seznamů (`crm_seznam_*`) ji nemají a mít nemůžou — nejsou o jednom
    záznamu; tam viditelnost řeší samotný obsah seznamu."""
    for typ, zapis in registr.ENTITY.items():
        if typ.startswith("crm_") and not typ.startswith("crm_seznam_"):
            assert callable(zapis.get("pristup")), f"entita {typ} nemá kontrolu záznamu"
