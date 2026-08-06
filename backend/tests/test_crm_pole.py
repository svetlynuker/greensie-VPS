"""Ukládání záznamů CRM po jednotlivých polích (automatické ukládání).

Testuje se `app.crm.pole_zaznamu` nad obyčejnými objekty (`Zakaznik()`,
`ObchodniPripad()`) — bez databáze, stejně jako u matice
(`tests/test_bunka_pole.py`). Celá logika je čistě nad instancí: kontrola
whitelistu, převod textu na hodnotu podle typu sloupce, sloučení `extra`
a kontrola kolize. SQLite by tu navíc ani nešla použít — modely CRM mají
sloupce `JSONB` a `ARRAY(...)`, které se do SQLite nepřeloží
(`CompileError`), takže `Zakaznik.__table__.create` spadne.

Čtyři věci, na kterých tenhle soubor stojí:

- **Whitelist je bezpečnostní jádro.** Jeden generický endpoint bez seznamu
  povolených polí by dovolil přepsat cokoli, co je na modelu — vlastníka
  záznamu, stav, `raynet_id`. Proto se tady vyjmenovaně kontroluje, že
  `stav`, vlastnictví, `duvod_prohry` ani `kategorie` neprojdou.

- **Sloučení vlastních polí.** `vlastni_pole.zpracuj()` staví NOVÝ slovník,
  takže naivní zápis jednoho vlastního pole by ostatních dvacet z `extra`
  smazal. Tohle je nejdůležitější test celého souboru.

- **Čísla se porovnávají číselně.** Databáze vrátí `1500000.00`, prohlížeč
  pošle `1500000`. Textovým porovnáním by člověk dostal hlášku o kolizi
  tam, kde se nic nezměnilo — a naučil by se ji odklikávat.

- **Rozepsaný stav není chyba.** Prázdná hodnota se ukládá (vymazání),
  jen tam, kde by ji databáze odmítla (NOT NULL číslo, datum), padne
  čitelný `ValueError` místo chyby z databáze.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

# Modely CRM mají vazby na modely jiných modulů (`Objednavka` → `Faktura`,
# ta dál na `Projekt`). SQLAlchemy je hledá podle jména při první konfiguraci
# mapperů, a ta se spustí už při vzniku PRVNÍHO objektu — bez těchto importů
# spadne i `ObchodniPripad()` na „name 'Faktura' is not defined“. V aplikaci
# je za registraci zodpovědný `app/main.py`, ten se ale v testech importovat
# nesmí (na produkčním `.env` by zmigroval produkční databázi).
import app.auth.models  # noqa: F401 - registrace modelů
import app.finance.models  # noqa: F401 - registrace modelů
import app.matice.models  # noqa: F401 - registrace modelů
import app.nabidkovac.models  # noqa: F401 - registrace modelů
from app.crm import vlastni_pole
from app.crm.models import ObchodniPripad, OdberneMisto, Zakaznik, ZakaznikKontakt
from app.crm.pole_zaznamu import (
    ENTITY,
    PREDPONA_VLASTNI,
    Konflikt,
    Nepovolene,
    _na_hodnotu,
    _stejne,
    entita,
    hodnota_textem,
    na_text,
    oznac_zmenu,
    over_pole,
    zapis_pole,
    zkontroluj_kolizi,
    zkontroluj_whitelist,
)
from app.crm.razitko import razitko_zaznamu

OP = ENTITY["op"]
ZAK = ENTITY["zakaznik"]
OM = ENTITY["om"]
KONTAKT = ENTITY["kontakt"]


def _pripad(**kw):
    """Vyplněný obchodní případ jako výchozí stav — ať je na čem poznat přepsání."""
    zaklad = {
        "nazev": "Rekonstrukce osvětlení",
        "popis": "zápis z první schůzky",
        # Přesně tak, jak hodnotu vrátí databáze ze sloupce Numeric(14, 2).
        "hodnota_kc": Decimal("1500000.00"),
        "pravdepodobnost": 50,
        "predpokladane_uzavreni": date(2026, 12, 31),
        "verze": 3,
        "extra": {"dotace": "OPTAK", "cislo_smlouvy": "S-2026-11"},
    }
    zaklad.update(kw)
    return ObchodniPripad(**zaklad)


# ---- 1. whitelist odpovídá modelům ------------------------------------------
def test_whitelist_zna_jen_existujici_sloupce():
    """Překlep ve whitelistu by se projevil až za běhu jako „pole nelze měnit“
    u něčeho, co na obrazovce evidentně je. Tady spadne hned."""
    assert zkontroluj_whitelist() == []


def test_registr_obsahuje_vsechny_entity_crm():
    """Každá obrazovka s automatickým ukládáním musí být v registru — jinak na
    ní autosave vrací „neznámá entita“ a políčka se tiše neukládají."""
    assert {"zakaznik", "kontakt", "om", "op", "obj", "pro"} <= set(ENTITY)
    assert entita("op").model is ObchodniPripad
    assert entita("zakaznik").model is Zakaznik
    assert entita("kontakt").model is ZakaznikKontakt
    assert entita("om").model is OdberneMisto


def test_kazda_entita_ma_pravo_i_kontrolu_pristupu():
    """Zápis bez práva a bez kontroly konkrétního záznamu by z autosave udělal
    obchvat celého CRM: znám id, přepíšu cizí případ."""
    for klic, e in ENTITY.items():
        assert e.pravo, f"entita {klic} nemá právo na modul"
        assert e.pole, f"entita {klic} nemá žádné povolené pole"
        assert callable(e.overit_pristup), f"entita {klic} nekontroluje přístup k záznamu"


# ---- 10. neznámá entita ------------------------------------------------------
def test_neznama_entita_je_nepovolena():
    """Klíč entity chodí z URL — cokoli mimo registr musí skončit odmítnutím,
    ne výjimkou z hloubky kódu (endpoint z `Nepovolene` dělá 422)."""
    with pytest.raises(Nepovolene):
        entita("neexistuje")
    with pytest.raises(Nepovolene):
        entita("")


# ---- 2. whitelist jako bezpečnostní hranice ---------------------------------
def test_over_pole_pusti_povolena_pole():
    for pole in OP.pole:
        over_pole(OP, pole)  # nesmí vyhodit nic
    over_pole(ZAK, "nazev")
    over_pole(KONTAKT, "email")


@pytest.mark.parametrize(
    "pole",
    [
        # Stav spouští automatizaci a povinná pole — patří na vědomé potvrzení.
        "stav",
        # Vlastnictví rozhoduje o tom, KDO záznam vidí. Přes autosave by si
        # kdokoli mohl přepsat cizí případ na sebe (nebo ho sobě odebrat).
        "vlastnik_user_id",
        "spoluvlastnici",
        # Důvod prohry se vyplňuje se stavem, ne samostatně.
        "duvod_prohry",
        # Kategorie je multiselect s validací (rozhoduje o druhu nabídky).
        "kategorie",
        # Most na složky Disku a Freelo — přepsáním by se rozpadlo párování.
        "raynet_code",
        "raynet_id",
        # Číslo z číselné řady je viditelné ID, mění se jen řadou.
        "cislo",
        "zakaznik_id",
        # A samozřejmě pole, které na modelu vůbec není.
        "neexistujici_pole",
        "__class__",
    ],
)
def test_over_pole_odmitne_vse_mimo_whitelist(pole):
    """Jádro bezpečnosti: jeden generický endpoint bez whitelistu by dovolil
    přepsat kterýkoli sloupec modelu, včetně vlastnictví a příznaků."""
    with pytest.raises(Nepovolene):
        over_pole(OP, pole)


# ---- 3. vlastní pole --------------------------------------------------------
def test_over_pole_pusti_vlastni_pole_u_entity_ktera_je_ma():
    """Vlastní pole zakládá admin za běhu, takže jejich klíče whitelist znát
    nemůže — pouští se celá předpona a klíč se ověří až proti definicím v DB."""
    assert PREDPONA_VLASTNI == "extra:"
    over_pole(OP, "extra:cokoli")
    over_pole(OP, "extra:dotace")
    over_pole(ZAK, "extra:ic_matky")
    over_pole(OM, "extra:ean")


def test_over_pole_odmitne_vlastni_pole_u_entity_bez_nich():
    """Kontaktní osoba vlastní pole nemá — zápis do `extra` by spadl na tom,
    že sloupec na modelu není."""
    assert KONTAKT.vlastni is None
    with pytest.raises(Nepovolene):
        over_pole(KONTAKT, "extra:x")


def test_over_pole_odmitne_predponu_bez_klice():
    with pytest.raises(Nepovolene):
        over_pole(OP, "extra:")


# ---- 4. hodnota jako text ---------------------------------------------------
def test_na_text_prevede_vsechny_typy_tak_jak_je_vidi_prohlizec():
    assert na_text(None) == ""
    assert na_text("") == ""
    assert na_text("Praha") == "Praha"
    assert na_text(True) == "1"
    assert na_text(False) == ""  # nezaškrtnuto = prázdno, ne „False“
    assert na_text(date(2026, 12, 31)) == "2026-12-31"
    assert na_text(datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)) == "2026-12-31"
    assert na_text(50) == "50"


def test_na_text_cisla_bez_zbytecnych_nul_a_bez_exponentu():
    """`1500000.00` z databáze i `1.5E+6` z `normalize()` by se v prohlížeči
    porovnávaly špatně — do políčka patří `1500000`."""
    assert na_text(Decimal("1500000.00")) == "1500000"
    assert na_text(Decimal("0.00")) == "0"
    assert na_text(Decimal("1.50")) == "1.5"
    assert na_text(Decimal("50.05")) == "50.05"
    assert na_text(Decimal("-2.10")) == "-2.1"


# ---- 5. porovnání dvou textových podob --------------------------------------
def test_stejne_porovnava_cisla_cislene():
    """POINTA: databáze vrátí `1500000.00`, prohlížeč pošle `1500000`. Kdyby se
    to porovnávalo textově, člověk by dostal hlášku o kolizi tam, kde se nic
    nezměnilo — a naučil by se ji odklikávat i tam, kde na ní záleží."""
    assert _stejne("1500000", "1500000.00") is True
    assert _stejne("1.5", "1,5") is True  # desetinná čárka z české klávesnice
    assert _stejne("0", "0.0") is True


def test_stejne_pozna_skutecny_rozdil():
    assert _stejne("1", "2") is False
    assert _stejne("Praha", "praha") is False  # velikost písmen JE změna
    assert _stejne("", "0") is False  # vymazáno není nula
    assert _stejne("Praha", "") is False


# ---- 6. text z formuláře → hodnota pro sloupec ------------------------------
def test_na_hodnotu_text_a_cele_cislo():
    assert _na_hodnotu(ZAK, "nazev", "  Technicplast s.r.o.  ") == "Technicplast s.r.o."
    assert _na_hodnotu(OP, "pravdepodobnost", "80") == 80
    assert _na_hodnotu(OP, "pravdepodobnost", " 0 ") == 0


def test_na_hodnotu_numeric_snese_ceskou_carku_i_mezeru():
    """Lidé čísla píšou, jak jsou zvyklí — „1 500,5“ nesmí skončit chybou."""
    assert _na_hodnotu(OM, "rezervovana_kapacita_kw", "250") == Decimal("250")
    assert _na_hodnotu(OM, "rezervovana_kapacita_kw", "1,5") == Decimal("1.5")
    assert _na_hodnotu(OM, "rezervovana_kapacita_kw", "1 500") == Decimal("1500")
    assert _na_hodnotu(OM, "rezervovana_kapacita_kw", "1 500,25") == Decimal("1500.25")


def test_na_hodnotu_datum():
    assert _na_hodnotu(OP, "predpokladane_uzavreni", "2026-12-31") == date(2026, 12, 31)
    # Čas za datem prohlížeč občas pošle; bere se prvních deset znaků.
    assert _na_hodnotu(OP, "predpokladane_uzavreni", "2026-12-31T23:59") == date(2026, 12, 31)


def test_na_hodnotu_bool():
    """Zaškrtávátko posílá „1“ / „ano“, odškrtnuté nepošle nic. Prázdno tady
    tedy NENÍ mazání, ale „ne“ — proto se Boolean řeší před kontrolou prázdna.

    (`hlavni` ve whitelistu není — má vedlejší efekt na ostatní kontakty.
    Tady se testuje jen převod podle typu sloupce, ten na whitelistu nezávisí.)
    """
    assert _na_hodnotu(KONTAKT, "hlavni", "1") is True
    assert _na_hodnotu(KONTAKT, "hlavni", "ano") is True
    assert _na_hodnotu(KONTAKT, "hlavni", "true") is True
    assert _na_hodnotu(KONTAKT, "hlavni", "") is False
    assert _na_hodnotu(KONTAKT, "hlavni", "ne") is False
    assert _na_hodnotu(KONTAKT, "hlavni", None) is False


def test_prazdna_hodnota_u_nullable_sloupce_je_none():
    """Vymazání čísla i data je legitimní — sloupec to dovoluje."""
    assert _na_hodnotu(OP, "hodnota_kc", "") is None
    assert _na_hodnotu(OP, "pravdepodobnost", "   ") is None
    assert _na_hodnotu(OP, "predpokladane_uzavreni", "") is None
    assert _na_hodnotu(ZAK, "gps_lat", "") is None
    assert _na_hodnotu(OP, "hodnota_kc", None) is None


def test_prazdna_hodnota_u_not_null_textu_je_prazdny_retezec():
    """Povinný název se dá „vyprázdnit“ — jinak by autosave u rozepsaného
    záznamu vracel chybu při každém smazání textu."""
    assert _na_hodnotu(ZAK, "nazev", "") == ""
    assert _na_hodnotu(OP, "popis", "") == ""
    assert _na_hodnotu(ZAK, "ico", None) == ""


def test_prazdne_cislo_v_not_null_sloupci_padne_citelne():
    """Prázdno do NOT NULL čísla/data by spadlo až na databázi (IntegrityError
    z commitu, kde už není poznat které pole). Tady padne čitelná hláška.

    `verze` a `vytvoreno_at` se přes autosave zapsat nedají (nejsou ve
    whitelistu) — testuje se převod podle typu, ne průchodnost endpointu.
    """
    with pytest.raises(ValueError):
        _na_hodnotu(OP, "verze", "")
    with pytest.raises(ValueError):
        _na_hodnotu(OP, "vytvoreno_at", "  ")


def test_nesmyslna_hodnota_padne_na_valueerror():
    """Endpoint z `ValueError` udělá 422 s hláškou, kterou člověk pochopí."""
    with pytest.raises(ValueError):
        _na_hodnotu(OP, "pravdepodobnost", "abc")
    with pytest.raises(ValueError):
        _na_hodnotu(OP, "hodnota_kc", "abc")
    with pytest.raises(ValueError):
        # Český zápis data prohlížeč neposílá, ale ruční požadavek ho poslat může.
        _na_hodnotu(OP, "predpokladane_uzavreni", "31.12.2026")
    with pytest.raises(ValueError):
        _na_hodnotu(OP, "predpokladane_uzavreni", "2026-02-31")


# ---- 7. zápis do sloupce ----------------------------------------------------
def test_zapis_pole_nesahne_na_ostatni_pole():
    """Uloží se jen to jedno pole; zbytek záznamu zůstane, jak byl. Původní
    `PUT` posílal celý formulář, takže druhý člověk přepsal i pole, kterých
    se ani nedotkl."""
    p = _pripad()
    zapis_pole(None, OP, p, pole="nazev", hodnota="Rekonstrukce kotelny", uzivatel_id=7)

    assert p.nazev == "Rekonstrukce kotelny"
    assert p.popis == "zápis z první schůzky"
    assert p.hodnota_kc == Decimal("1500000.00")
    assert p.pravdepodobnost == 50
    assert p.predpokladane_uzavreni == date(2026, 12, 31)
    assert p.extra == {"dotace": "OPTAK", "cislo_smlouvy": "S-2026-11"}


def test_zapis_pole_zapise_kdo_kdy_a_posune_verzi():
    p = _pripad()
    pred = datetime.now(timezone.utc)

    zapis_pole(None, OP, p, pole="hodnota_kc", hodnota="2 000 000", uzivatel_id=7)

    assert p.hodnota_kc == Decimal("2000000")
    assert p.verze == 4
    assert p.zmenil_id == 7
    assert p.zmeneno_at >= pred


def test_oznac_zmenu_zacina_na_jednicce_i_u_noveho_zaznamu():
    """Nový záznam má `verze` None (default platí až při insertu)."""
    p = ObchodniPripad()
    oznac_zmenu(p, None)
    assert p.verze == 1
    assert p.zmenil_id is None


def test_prazdna_hodnota_pole_vymaze():
    p = _pripad()
    zapis_pole(None, OP, p, pole="predpokladane_uzavreni", hodnota="", uzivatel_id=7)
    assert p.predpokladane_uzavreni is None
    assert hodnota_textem(OP, p, "predpokladane_uzavreni") == ""

    # None z formuláře se bere jako prázdno, ne jako chyba.
    zapis_pole(None, OP, p, pole="popis", hodnota=None, uzivatel_id=7)
    assert p.popis == ""


def test_rucni_cena_objednavky_se_priznakem_uzamkne():
    """Ručně přepsaná cena má přednost před součtem rozpisu — jinak by ji
    přepočet položek smazal, aniž by bylo poznat proč."""
    obj_e = ENTITY["obj"]
    o = obj_e.model(nazev="Dodávka", cena_kc=None, cena_rucni=False, verze=1)

    zapis_pole(None, obj_e, o, pole="cena_kc", hodnota="990000", uzivatel_id=7)
    assert o.cena_kc == Decimal("990000")
    assert o.cena_rucni is True

    # Vymazání ceny příznak vrátí — od teď zase platí součet rozpisu.
    zapis_pole(None, obj_e, o, pole="cena_kc", hodnota="", uzivatel_id=7)
    assert o.cena_kc is None
    assert o.cena_rucni is False


# ---- 8. vlastní pole se SLUČUJÍ, ne přepisují -------------------------------
def _definice(klic, typ="text", nazev=None, volby=(), vzorec=""):
    """Náhrada `CrmVlastniPole` — definice polí jsou v databázi, kterou tenhle
    soubor nemá (JSONB/ARRAY do SQLite nejdou)."""
    return SimpleNamespace(
        klic=klic,
        nazev=nazev or klic,
        typ=typ,
        volby=list(volby),
        vzorec=vzorec,
        povinne=False,
    )


DEFINICE_OP = [
    _definice("dotace"),
    _definice("cislo_smlouvy"),
    _definice("uspora_kc", typ="cislo"),
    _definice("podpis_do", typ="datum"),
    _definice("marze", typ="cislo", vzorec="hodnota_kc - uspora_kc"),
]


@pytest.fixture()
def s_definicemi(monkeypatch):
    """Podstrčí definice vlastních polí místo dotazu do databáze.

    Monkeypatch míří na `seznam()`, ne na `zpracuj_jedno()` — testovat chceme
    skutečnou funkci včetně toho, jak zachází s prázdnou hodnotou, neznámým
    klíčem a výpočtovým polem. `seznam()` je její jediný dotaz do DB.
    """
    monkeypatch.setattr(vlastni_pole, "seznam", lambda db, ent: DEFINICE_OP)


def test_zapis_vlastniho_pole_ostatni_klice_necha_byt(s_definicemi):
    """NEJDŮLEŽITĚJŠÍ TEST SOUBORU. `vlastni_pole.zpracuj()` staví nový
    slovník, takže naivní implementace autosave by při uložení JEDNOHO
    vlastního pole ostatní vlastní pole záznamu SMAZALA — tiše, bez chyby,
    a poznalo by se to až tím, že v kartě chybí data."""
    p = _pripad(extra={"dotace": "OPTAK", "cislo_smlouvy": "S-2026-11", "uspora_kc": 12000.0})

    zapis_pole(None, OP, p, pole="extra:dotace", hodnota="NZÚ", uzivatel_id=7)

    assert p.extra == {"dotace": "NZÚ", "cislo_smlouvy": "S-2026-11", "uspora_kc": 12000.0}
    # Sloupce se zápisem do `extra` dotknout nesmí.
    assert p.nazev == "Rekonstrukce osvětlení"
    assert p.verze == 4
    assert p.zmenil_id == 7


def test_zapis_vlastniho_pole_zaklada_i_do_prazdneho_extra(s_definicemi):
    p = _pripad(extra=None)
    zapis_pole(None, OP, p, pole="extra:dotace", hodnota="OPTAK", uzivatel_id=7)
    assert p.extra == {"dotace": "OPTAK"}


def test_novy_slovnik_aby_si_toho_sqlalchemy_vsimla(s_definicemi):
    """Změna UVNITŘ slovníku JSONB je SQLAlchemy neviditelná, dokud se atribut
    nepřiřadí znovu — jinak by se uložení tiše neprovedlo."""
    puvodni = {"dotace": "OPTAK"}
    p = _pripad(extra=puvodni)

    zapis_pole(None, OP, p, pole="extra:dotace", hodnota="NZÚ", uzivatel_id=7)

    assert p.extra is not puvodni
    assert puvodni == {"dotace": "OPTAK"}


def test_prazdna_hodnota_vlastni_pole_klic_odebere_a_ostatni_necha(s_definicemi):
    p = _pripad(extra={"dotace": "OPTAK", "cislo_smlouvy": "S-2026-11"})

    zapis_pole(None, OP, p, pole="extra:dotace", hodnota="", uzivatel_id=7)

    assert p.extra == {"cislo_smlouvy": "S-2026-11"}
    # Druhé vymazání téhož klíče nesmí spadnout (prohlížeč pošle autosave víckrát).
    zapis_pole(None, OP, p, pole="extra:dotace", hodnota="", uzivatel_id=7)
    assert p.extra == {"cislo_smlouvy": "S-2026-11"}


def test_je_prazdna_hodnota():
    assert vlastni_pole.je_prazdna_hodnota(None) is True
    assert vlastni_pole.je_prazdna_hodnota("") is True
    assert vlastni_pole.je_prazdna_hodnota("   ") is True
    assert vlastni_pole.je_prazdna_hodnota("x") is False
    # Nula ani „ne“ prázdné nejsou — to je vyplněná odpověď.
    assert vlastni_pole.je_prazdna_hodnota(0) is False
    assert vlastni_pole.je_prazdna_hodnota(False) is False


def test_zpracuj_jedno_ocisti_hodnotu_podle_typu(s_definicemi):
    assert vlastni_pole.zpracuj_jedno(None, "op", "uspora_kc", "12 000,5") == (True, 12000.5)
    assert vlastni_pole.zpracuj_jedno(None, "op", "podpis_do", "2026-12-31") == (
        True,
        "2026-12-31",
    )
    assert vlastni_pole.zpracuj_jedno(None, "op", "dotace", "  OPTAK  ") == (True, "OPTAK")


def test_zpracuj_jedno_neuklada_nezname_ani_vypoctove_pole(s_definicemi):
    """Neznámý klíč (smazané pole, cizí data) se zahazuje bez chyby — formulář
    ze starší otevřené stránky by jinak nešel uložit vůbec. Výpočtové pole
    se do `extra` neukládá, počítá se při zobrazení."""
    assert vlastni_pole.zpracuj_jedno(None, "op", "neznamy_klic", "x") == (False, None)
    assert vlastni_pole.zpracuj_jedno(None, "op", "marze", "999") == (False, None)


def test_nezname_vlastni_pole_ostatni_hodnoty_nesmaze(s_definicemi):
    """Regrese: „nemám co uložit“ nesmí znamenat „ulož prázdno“."""
    p = _pripad(extra={"dotace": "OPTAK"})
    zapis_pole(None, OP, p, pole="extra:neznamy_klic", hodnota="x", uzivatel_id=7)
    assert p.extra == {"dotace": "OPTAK"}


def test_hodnota_textem_cte_vlastni_pole_z_extra():
    """U vlastních polí se čte přímo z `extra`, ne z výstupu s dopočty —
    na výpočtovém poli by kontrola kolize hlásila rozdíl pořád."""
    p = _pripad(extra={"dotace": "OPTAK", "uspora_kc": 12000.0})
    assert hodnota_textem(OP, p, "extra:dotace") == "OPTAK"
    assert hodnota_textem(OP, p, "extra:uspora_kc") == "12000.0"
    assert hodnota_textem(OP, p, "extra:nevyplneno") == ""
    assert hodnota_textem(OP, p, "nazev") == "Rekonstrukce osvětlení"
    assert hodnota_textem(OP, p, "hodnota_kc") == "1500000"


# ---- 9. kontrola kolize -----------------------------------------------------
def test_kontrola_kolize_projde_kdyz_puvodni_odpovida():
    p = _pripad()
    zkontroluj_kolizi(OP, p, pole="nazev", puvodni="Rekonstrukce osvětlení")
    zkontroluj_kolizi(OP, p, pole="predpokladane_uzavreni", puvodni="2026-12-31")
    zkontroluj_kolizi(OP, p, pole="pravdepodobnost", puvodni="50")


def test_kontrola_kolize_neprotestuje_kvuli_zapisu_cisla():
    """POINTA: databáze drží `1500000.00`, prohlížeč poslal `1500000`. Falešná
    hláška o kolizi je horší než žádná — člověk si na ni zvykne."""
    p = _pripad()
    zkontroluj_kolizi(OP, p, pole="hodnota_kc", puvodni="1500000")
    zkontroluj_kolizi(OP, p, pole="hodnota_kc", puvodni="1500000.00")
    zkontroluj_kolizi(OP, p, pole="hodnota_kc", puvodni="1500000,000")


def test_kontrola_kolize_vyhodi_konflikt_a_rekne_kdo():
    """Hodnotu mezitím změnil někdo jiný → nepřepisujeme, ptáme se. V hlášce
    musí být poznat KDO a CO tam je teď, jinak se člověk nemá jak rozhodnout."""
    p = _pripad(nazev="přejmenoval to kolega", zmenil_id=9)

    with pytest.raises(Konflikt) as chyba:
        zkontroluj_kolizi(OP, p, pole="nazev", puvodni="Rekonstrukce osvětlení")

    k = chyba.value
    assert k.pole == "nazev"
    assert k.aktualni == "přejmenoval to kolega"
    assert k.zmenil_id == 9


def test_kontrola_kolize_hlida_i_vlastni_pole():
    p = _pripad(extra={"dotace": "NZÚ"}, zmenil_id=9)

    with pytest.raises(Konflikt) as chyba:
        zkontroluj_kolizi(OP, p, pole="extra:dotace", puvodni="OPTAK")

    assert chyba.value.aktualni == "NZÚ"


def test_puvodni_none_kontrolu_preskoci():
    """Tvrdý přepis po tom, co člověk v hlášce o kolizi potvrdil „přepiš“."""
    p = _pripad(nazev="cizí text")
    zkontroluj_kolizi(OP, p, pole="nazev", puvodni=None)  # nesmí vyhodit nic
    zapis_pole(None, OP, p, pole="nazev", hodnota="moje verze", uzivatel_id=7)
    assert p.nazev == "moje verze"


def test_kolize_pozna_i_vymazani_hodnoty():
    """Prázdno vs. hodnota je taky kolize — jinak by se vymazání cizí hodnoty
    přepsalo bez dotazu."""
    p = _pripad(nazev="")
    with pytest.raises(Konflikt):
        zkontroluj_kolizi(OP, p, pole="nazev", puvodni="Rekonstrukce osvětlení")


# ---- razítko: jen část, která databázi nepotřebuje --------------------------
# `razitko_zaznamu` se u zákazníka, případu, objednávky a projektu otestovat
# nedá — počítá pod-záznamy dotazy do DB a tabulky CRM se v SQLite založit
# nedají (JSONB, ARRAY). U kontaktu, odběrného místa a nabídky ale stačí jedno
# `db.get()`, takže se dá podstrčit náhrada session a podpis opravdu porovnat.
class _JedenZaznam:
    """Náhrada session pro razítko: umí jen vrátit připravený záznam."""

    def __init__(self, zaznam=None):
        self._zaznam = zaznam

    def get(self, model, id_):
        return self._zaznam


def test_razitko_nezname_entity_je_prazdne():
    """Neznámý klíč nesmí padnout — klient se ptá na to, co má v adrese."""
    assert razitko_zaznamu(None, "neco-vymysleneho", 5) == ""


def test_razitko_bez_id_je_prazdne():
    """Prázdné/nulové ID = není na co se dívat. Databáze se ani nesáhne
    (`db=None` by na dotazu spadlo)."""
    assert razitko_zaznamu(None, "zakaznik", 0) == ""
    assert razitko_zaznamu(None, "op", None) == ""


def test_razitko_neexistujiciho_zaznamu_je_prazdne():
    assert razitko_zaznamu(_JedenZaznam(None), "kontakt", 88) == ""


def test_razitko_se_zmeni_pri_zmene_zaznamu():
    """Podpis je tupý, ale nesmí lhát: po zápisu do záznamu musí být jiný,
    jinak si klient data nenatáhne a člověk kouká na cizí přepsanou hodnotu."""
    k = ZakaznikKontakt(id=88, jmeno="Bohuš", zmeneno_at=None, verze=0)
    pred = razitko_zaznamu(_JedenZaznam(k), "kontakt", 88)

    zapis_pole(None, KONTAKT, k, pole="jmeno", hodnota="Alena", uzivatel_id=7)
    po = razitko_zaznamu(_JedenZaznam(k), "kontakt", 88)

    assert pred != po
    # V podpisu je čas poslední změny a verze — obojí `oznac_zmenu` posunul.
    assert po.startswith(k.zmeneno_at.isoformat())
    assert po.endswith("|1")
