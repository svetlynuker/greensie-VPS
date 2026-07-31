"""Podmínky pravidel a katalog polí (CRM-31, `automatizace_pole.py`).

Podmínka je to, co odděluje „pravidlo pro FVE" od „pravidla pro peak shaving".
Když se vyhodnotí špatně, appka udělá něco jiného, než je v pravidle napsáno —
a nikdo si toho nevšimne, protože se nic nerozbije.

Dvě zásady, které tady mají svůj test:

  * **Nevyhodnotitelná podmínka = nesplněná.** Pravidlo, kterému nerozumíme,
    nemá zakládat objednávky. Tichý „nic se nestalo" se dá dohledat v logu,
    tichý „udělalo se to omylem" ne.
  * **Kontroluje se při ukládání.** Podmínka na neexistující pole nebo úkol bez
    názvu se nemá dát uložit; za běhu už není koho se zeptat.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.crm import automatizace
from app.crm import automatizace_pole as pole_modul


class _Zaznam:
    """Cokoli s atributy — vyhodnocení podmínek na ORM nezávisí."""

    def __init__(self, **kw):
        self.extra = {}
        for k, v in kw.items():
            setattr(self, k, v)


class _FakeDb:
    """Minimum pro kontrolu pravidla: `get` na šablonu a dotaz na uživatele.

    Vlastní pole se tváří jako prázdná — testy podmínek stojí na pevných polích
    a dotaz na `CrmVlastniPole` by potřeboval celou databázi.
    """

    def __init__(self, sablony=(3,), uzivatele=(7,), stavy=("vyhrano", "novy")):
        self._sablony = set(sablony)
        self._uzivatele = set(uzivatele)
        self.stavy = set(stavy)

    def get(self, model, ident):
        try:
            cislo = int(ident)
        except (TypeError, ValueError):
            return None
        # Rozlišujeme podle modelu: `over_krok` se ptá jednou na šablonu,
        # jednou na uživatele, a odpověď „existuje“ musí sedět na to správné.
        znami = self._uzivatele if getattr(model, "__name__", "") == "User" else self._sablony
        return object() if cislo in znami else None

    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def order_by(self, *_a, **_k):
        return self

    def all(self):
        return []

    def first(self):
        return (7,) if self._uzivatele else None


@pytest.fixture()
def db():
    return _FakeDb()


@pytest.fixture()
def stavy_existuji(monkeypatch):
    """Stavy pipeline bereme jako existující — testujeme podmínky, ne číselník."""
    monkeypatch.setattr(automatizace.stavy_modul, "najdi", lambda db, e, k: object())


# ---- katalog polí ------------------------------------------------------------
def test_kazde_pole_ma_operatory():
    """Pole bez operátorů by v UI šlo vybrat a pak by nebylo z čeho srovnávat."""
    for entita, pole in pole_modul.POLE.items():
        for p in pole:
            assert p["typ"] in pole_modul.OPERATORY, f"{entita}.{p['klic']}: typ {p['typ']}"
            assert p["nazev"], f"{entita}.{p['klic']} nemá název"


def test_stav_a_vlastnik_se_nedaji_prepsat_jako_pole():
    """Obojí má vlastní akci, která navíc zapíše historii a pošle notifikaci.

    Kdyby šly přepsat jako obyčejné pole, vznikl by záznam, který v historii
    „nikam nepřešel", a nový vlastník by se to nedozvěděl.
    """
    for entita, pole in pole_modul.POLE.items():
        for p in pole:
            if p["klic"] in ("stav", "stav_obchodni", "vlastnik_user_id"):
                assert not p["zapis"], f"{entita}.{p['klic']} je zapisovatelné"


def test_cislo_zaznamu_se_neda_prepsat():
    """Číslo přiděluje číselná řada; ruční přepis by rozbil jednoznačnost."""
    for entita, pole in pole_modul.POLE.items():
        for p in pole:
            if p["klic"] == "cislo":
                assert not p["zapis"], f"{entita}.cislo je zapisovatelné"


# ---- čtení hodnot ------------------------------------------------------------
def test_hodnota_vlastniho_pole(db):
    z = _Zaznam(extra={"dotace": "ano"})
    assert pole_modul.hodnota(z, "extra.dotace") == "ano"
    assert pole_modul.hodnota(z, "extra.chybi") is None


def test_hodnota_zakaznika_z_relace_i_ze_sloupce():
    """Případ má zákazníka přes relaci, nabídka ve vlastním sloupci — jedno pole."""
    z_relace = _Zaznam(zakaznik=_Zaznam(nazev="Pekárna Novák"))
    z_sloupec = _Zaznam(zakaznik_nazev="Mlékárna Jih")
    assert pole_modul.hodnota(z_relace, "zakaznik_nazev") == "Pekárna Novák"
    assert pole_modul.hodnota(z_sloupec, "zakaznik_nazev") == "Mlékárna Jih"


def test_nezaskrtnuto_neni_prazdne():
    """„Ne" je platná odpověď, ne chybějící údaj — jinak by „je prázdné" lhalo."""
    assert pole_modul.je_prazdna(False) is False
    assert pole_modul.je_prazdna(None) is True
    assert pole_modul.je_prazdna("") is True
    assert pole_modul.je_prazdna([]) is True
    assert pole_modul.je_prazdna(0) is False


# ---- vyhodnocení podmínek ----------------------------------------------------
def _pod(pole, operator, hodnota=None, spojka="vse"):
    p = {"pole": pole, "operator": operator}
    if hodnota is not None:
        p["hodnota"] = hodnota
    return {"spojka": spojka, "polozky": [p]}


def test_prazdne_podminky_plati_vzdy(db):
    plati, duvod = pole_modul.vyhodnot(db, "op", _Zaznam(), None)
    assert plati and duvod == ""


def test_cislo_vetsi_nez(db):
    z = _Zaznam(hodnota_kc=Decimal("750000"))
    assert pole_modul.vyhodnot(db, "op", z, _pod("hodnota_kc", "vetsi", "500000"))[0]
    assert not pole_modul.vyhodnot(db, "op", z, _pod("hodnota_kc", "vetsi", "900000"))[0]


def test_cislo_s_carkou_i_teckou(db):
    """Člověk napíše „0,5", appka to nesmí vyhodnotit jako nulu."""
    z = _Zaznam(pravdepodobnost=Decimal("0.5"))
    assert pole_modul.vyhodnot(db, "op", z, _pod("pravdepodobnost", "je", "0,5"))[0]


def test_prazdne_cislo_neni_nula(db):
    """Nevyplněná hodnota nesmí projít podmínkou „menší než"."""
    z = _Zaznam(hodnota_kc=None)
    assert not pole_modul.vyhodnot(db, "op", z, _pod("hodnota_kc", "mensi", "100"))[0]
    assert pole_modul.vyhodnot(db, "op", z, _pod("hodnota_kc", "prazdne"))[0]


def test_datum_pred_a_po(db):
    z = _Zaznam(predpokladane_uzavreni=date(2026, 8, 15))
    assert pole_modul.vyhodnot(db, "op", z, _pod("predpokladane_uzavreni", "pred", "2026-09-01"))[0]
    assert pole_modul.vyhodnot(db, "op", z, _pod("predpokladane_uzavreni", "po", "2026-08-01"))[0]
    assert not pole_modul.vyhodnot(db, "op", z, _pod("predpokladane_uzavreni", "pred", "2026-01-01"))[0]


def test_text_obsahuje_nezalezi_na_velikosti_pismen(db):
    z = _Zaznam(nazev="FVE Pekárna Novák")
    assert pole_modul.vyhodnot(db, "op", z, _pod("nazev", "obsahuje", "pekárna"))[0]
    assert not pole_modul.vyhodnot(db, "op", z, _pod("nazev", "obsahuje", "peak"))[0]


def test_kategorie_obsahuje_nektere(db):
    z = _Zaznam(kategorie=["ppa", "servis"])
    assert pole_modul.vyhodnot(db, "op", z, _pod("kategorie", "obsahuje_nektere", ["ppa"]))[0]
    assert not pole_modul.vyhodnot(
        db, "op", z, _pod("kategorie", "obsahuje_nektere", ["peak_shaving"])
    )[0]
    assert pole_modul.vyhodnot(
        db, "op", z, _pod("kategorie", "neobsahuje_zadne", ["peak_shaving"])
    )[0]


def test_vlastnik_je_jedno_z(db):
    """Uživatel se srovnává jako text – v podmínce je id, ve sloupci číslo."""
    z = _Zaznam(vlastnik_user_id=7)
    assert pole_modul.vyhodnot(db, "op", z, _pod("vlastnik_user_id", "je_jedno_z", ["7", "9"]))[0]
    assert not pole_modul.vyhodnot(db, "op", z, _pod("vlastnik_user_id", "je_jedno_z", ["9"]))[0]


def test_spojka_vse_a_cokoli(db):
    z = _Zaznam(hodnota_kc=Decimal("100000"), nazev="FVE Novák")
    obe = {
        "spojka": "vse",
        "polozky": [
            {"pole": "hodnota_kc", "operator": "vetsi", "hodnota": "500000"},
            {"pole": "nazev", "operator": "obsahuje", "hodnota": "FVE"},
        ],
    }
    assert not pole_modul.vyhodnot(db, "op", z, obe)[0]
    aspon_jedna = dict(obe, spojka="cokoli")
    assert pole_modul.vyhodnot(db, "op", z, aspon_jedna)[0]


def test_neexistujici_pole_je_nesplnena_podminka(db):
    """Admin smazal vlastní pole — pravidlo má přestat brát, ne začít brát na všechno."""
    plati, duvod = pole_modul.vyhodnot(db, "op", _Zaznam(), _pod("extra.smazane", "je", "x"))
    assert not plati
    assert "smazane" in duvod


def test_duvod_rika_ktera_podminka_selhala(db):
    """Bez důvodu by v logu bylo jen „nic se nestalo" a nikdo by nevěděl proč."""
    z = _Zaznam(hodnota_kc=Decimal("1000"))
    plati, duvod = pole_modul.vyhodnot(db, "op", z, _pod("hodnota_kc", "vetsi", "500000"))
    assert not plati
    assert "Hodnota" in duvod


# ---- kontrola podmínek při ukládání ------------------------------------------
def test_podminka_na_neexistujici_pole_neprojde(db):
    with pytest.raises(ValueError):
        pole_modul.over_podminky(
            db, "op", {"polozky": [{"pole": "neexistuje", "operator": "je", "hodnota": "x"}]}
        )


def test_podminka_s_cizim_operatorem_neprojde(db):
    """„Obsahuje" u čísla by porovnávalo texty — a překvapilo by to."""
    with pytest.raises(ValueError):
        pole_modul.over_podminky(
            db, "op", {"polozky": [{"pole": "hodnota_kc", "operator": "obsahuje", "hodnota": "5"}]}
        )


def test_podminka_bez_hodnoty_neprojde(db):
    with pytest.raises(ValueError):
        pole_modul.over_podminky(
            db, "op", {"polozky": [{"pole": "hodnota_kc", "operator": "vetsi"}]}
        )


def test_podminka_prazdne_hodnotu_nechce(db):
    """U „je prázdné" se hodnota nezadává — a nesmí být povinná."""
    ciste = pole_modul.over_podminky(
        db, "op", {"polozky": [{"pole": "hodnota_kc", "operator": "prazdne"}]}
    )
    assert ciste["polozky"] == [{"pole": "hodnota_kc", "operator": "prazdne"}]


def test_cislo_v_podmince_musi_byt_cislo(db):
    with pytest.raises(ValueError):
        pole_modul.over_podminky(
            db,
            "op",
            {"polozky": [{"pole": "hodnota_kc", "operator": "vetsi", "hodnota": "hodně"}]},
        )


# ---- zápis hodnoty pole ------------------------------------------------------
def test_zapis_prevede_typ(db):
    z = _Zaznam(hodnota_kc=None, predpokladane_uzavreni=None)
    pole_modul.zapis(db, "op", z, "hodnota_kc", "750000")
    pole_modul.zapis(db, "op", z, "predpokladane_uzavreni", "2026-09-01")
    assert z.hodnota_kc == Decimal("750000")
    assert z.predpokladane_uzavreni == date(2026, 9, 1)


def test_zapis_vlastniho_pole_vytvori_novy_slovnik():
    """JSONB se nesleduje po prvcích — mutace původního slovníku by se neuložila."""
    db = _FakeDb()
    z = _Zaznam(extra={"stare": "1"})
    puvodni = z.extra

    class _SVlastnim(_FakeDb):
        pass

    # Vlastní pole musí být v katalogu, jinak `zapis` odmítne. Podstrčíme definici.
    import app.crm.automatizace_pole as m

    puvodni_definice = m.definice
    m.definice = lambda _db, _e, klic: (
        {"klic": klic, "nazev": "Dotace", "typ": "text", "zapis": True}
        if klic == "extra.dotace"
        else puvodni_definice(_db, _e, klic)
    )
    try:
        m.zapis(db, "op", z, "extra.dotace", "ano")
    finally:
        m.definice = puvodni_definice

    assert z.extra == {"stare": "1", "dotace": "ano"}
    assert z.extra is not puvodni, "extra se změnilo mutací, do databáze by se to nedostalo"


def test_nezapisovatelne_pole_odmitne(db):
    with pytest.raises(ValueError):
        pole_modul.zapis(db, "op", _Zaznam(stav="novy"), "stav", "vyhrano")


def test_zapis_nesmyslneho_cisla_odmitne(db):
    with pytest.raises(ValueError):
        pole_modul.zapis(db, "op", _Zaznam(hodnota_kc=None), "hodnota_kc", "hodně")


# ---- kontrola celého pravidla ------------------------------------------------
def _vstup(**kw):
    zaklad = {
        "spoust_entita": "op",
        "spoust_typ": "stav",
        "spoust_stav": "vyhrano",
        "kroky": [{"akce": "objednavka", "nastaveni": {}}],
        "opakovat": "jednou",
    }
    zaklad.update(kw)
    return zaklad


def test_pravidlo_bez_kroku_neprojde(db, stavy_existuji):
    """Pravidlo bez kroků by nic nedělalo a v seznamu by mátlo."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(db, _vstup(kroky=[]))


def test_neznama_akce_neprojde(db, stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(db, _vstup(kroky=[{"akce": "neexistuje", "nastaveni": {}}]))


def test_akce_od_spatne_entity_neprojde(db, stavy_existuji):
    """„Založ objednávku" jde jen od případu — od projektu by nemělo co dělat."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db, _vstup(spoust_entita="pro", spoust_stav="dokonceno")
        )


def test_ukol_bez_nazvu_neprojde(db, stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db,
            _vstup(
                spoust_entita="nab",
                spoust_stav="odeslana",
                kroky=[{"akce": "ukol", "nastaveni": {"za_dni": 7}}],
            ),
        )


def test_ukol_ocisti_parametry(db, stavy_existuji):
    ciste = automatizace.over_pravidlo(
        db,
        _vstup(
            spoust_entita="nab",
            spoust_stav="odeslana",
            kroky=[
                {
                    "akce": "ukol",
                    "nastaveni": {
                        "za_dni": "7",
                        "nazev": "  Zavolat  ",
                        "text": "",
                        "komu_user_id": 7,
                    },
                }
            ],
        ),
    )
    n = ciste["kroky"][0]["nastaveni"]
    assert n["za_dni"] == 7
    assert n["nazev"] == "Zavolat"
    assert n["komu_user_id"] == 7


def test_zaporny_odklad_se_srovna_na_nulu(db, stavy_existuji):
    ciste = automatizace.over_pravidlo(
        db,
        _vstup(
            spoust_entita="nab",
            spoust_stav="odeslana",
            kroky=[{"akce": "ukol", "nastaveni": {"za_dni": -5, "nazev": "Hned"}}],
        ),
    )
    assert ciste["kroky"][0]["nastaveni"]["za_dni"] == 0


def test_neexistujici_sablona_neprojde(stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            _FakeDb(sablony=()),
            _vstup(
                spoust_entita="obj",
                spoust_stav="podepsana",
                kroky=[{"akce": "projekt", "nastaveni": {"sablona_id": 99}}],
            ),
        )


def test_projekt_bez_sablony_projde(db, stavy_existuji):
    """Bez zvolené šablony se vybírá podle kategorie případu — je to platná volba."""
    ciste = automatizace.over_pravidlo(
        db,
        _vstup(
            spoust_entita="obj",
            spoust_stav="podepsana",
            kroky=[{"akce": "projekt", "nastaveni": {}}],
        ),
    )
    assert ciste["kroky"][0]["nastaveni"] == {}


def test_neexistujici_stav_neprojde(db, monkeypatch):
    monkeypatch.setattr(automatizace.stavy_modul, "najdi", lambda db_, e, k: None)
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(db, _vstup(spoust_stav="neexistuje"))


def test_zprava_bez_textu_i_sablony_neprojde(db, stavy_existuji):
    """E-mail bez předmětu i těla by odešel prázdný."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db, _vstup(kroky=[{"akce": "email", "nastaveni": {"komu": "vlastnik"}}])
        )


def test_email_na_nesmyslnou_adresu_neprojde(db, stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db,
            _vstup(
                kroky=[
                    {
                        "akce": "email",
                        "nastaveni": {
                            "komu": "adresa",
                            "adresa": "tohle není mail",
                            "predmet": "Ahoj",
                        },
                    }
                ]
            ),
        )


def test_notifikace_na_napsanou_adresu_neprojde(db, stavy_existuji):
    """Notifikace v appce nemá kam na e-mailovou adresu jít — volba tam nepatří."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db,
            _vstup(
                kroky=[
                    {
                        "akce": "notifikace",
                        "nastaveni": {"komu": "adresa", "adresa": "a@b.cz", "predmet": "Ahoj"},
                    }
                ]
            ),
        )


def test_prilis_mnoho_kroku_neprojde(db, stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db, _vstup(kroky=[{"akce": "poznamka", "nastaveni": {"telo": "x"}}] * 11)
        )


# ---- časový spouštěč ---------------------------------------------------------
def test_casovy_spoustec_potrebuje_datumove_pole(db, stavy_existuji):
    """Od textového pole se dny počítat nedají."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db,
            _vstup(
                spoust_typ="cas",
                cas_nastaveni={"zaklad": "pole", "pole": "nazev", "posun_dni": -5},
            ),
        )


def test_casovy_spoustec_podle_data_projde(db, stavy_existuji):
    ciste = automatizace.over_pravidlo(
        db,
        _vstup(
            spoust_typ="cas",
            cas_nastaveni={
                "zaklad": "pole",
                "pole": "predpokladane_uzavreni",
                "posun_dni": "-5",
            },
        ),
    )
    assert ciste["cas_nastaveni"] == {
        "zaklad": "pole",
        "pole": "predpokladane_uzavreni",
        "posun_dni": -5,
    }
    # Spouštěč není „stav“, takže cílový stav se neukládá – jinak by v seznamu
    # svítila věta „→ Vyhráno“ u pravidla, které na stav vůbec nereaguje.
    assert ciste["spoust_stav"] == ""


def test_necinnost_nula_dni_neprojde(db, stavy_existuji):
    """„0 dní beze změny" by sedělo na každý záznam v databázi."""
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(
            db, _vstup(spoust_typ="cas", cas_nastaveni={"zaklad": "necinnost", "dni": 0})
        )


def test_spoustec_pole_potrebuje_existujici_pole(db, stavy_existuji):
    with pytest.raises(ValueError):
        automatizace.over_pravidlo(db, _vstup(spoust_typ="pole", spoust_pole="neexistuje"))


def test_spoustec_pole_projde(db, stavy_existuji):
    ciste = automatizace.over_pravidlo(
        db, _vstup(spoust_typ="pole", spoust_pole="hodnota_kc", opakovat="vzdy")
    )
    assert ciste["spoust_pole"] == "hodnota_kc"
    assert ciste["opakovat"] == "vzdy"
