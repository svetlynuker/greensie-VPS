"""Testy záložky „Firma" (údaje o nás jako o Greensie) — části bez DB.

Co se tady hlídá a proč právě to:

* **Whitelist ukládaných polí.** `nastaveni_crm.uloz` přebírá jen pole ze svého
  seznamu. Kdyby do `FirmaVstup` přibylo políčko a do seznamu ne, formulář by ho
  poslal, server odpověděl 200 a hodnota by se tiše zahodila — uživatel by si
  myslel, že má IBAN uložený, a on nikde. Nic nespadne, takže to musí hlídat test.

* **Sloupce modelu vs. whitelist.** Druhá strana téže pasti: nový sloupec
  v `CrmNastaveni`, který se zapomene do whitelistu, nejde vyplnit vůbec.

* **Skládání adresy.** `nase_adresa` je jeden řádek pro tlačítko „U nás" u místa
  konání schůzky a dopočítává se ze sídla. Kdyby se skládala špatně, rozbije se
  funkce, která s Firmou na první pohled nesouvisí.
"""

from types import SimpleNamespace

from app.crm import nastaveni_crm
from app.crm.models import CrmNastaveni
from app.crm.schemas import FirmaVstup


# Sloupce, které se z formuláře MĚNIT NESMÍ: klíč, dopočítaný řádek adresy
# a značka poslední úpravy (tu si nastavuje databáze sama).
NEEDITOVATELNE = {"id", "nase_adresa", "aktualizovano_at"}


def _pole_modelu() -> set[str]:
    return {s.name for s in CrmNastaveni.__table__.columns} - NEEDITOVATELNE


def test_vsechna_pole_formulare_jde_ulozit():
    """Co formulář umí poslat, to `uloz` musí přebrat — jinak se to tiše zahodí."""
    whitelist = set(nastaveni_crm.TEXTOVA_POLE) | set(nastaveni_crm.LOGICKA_POLE)
    z_formulare = set(FirmaVstup.model_fields)
    chybi = sorted(z_formulare - whitelist)
    assert not chybi, (
        "Tahle pole formuláře „Firma“ se při uložení zahodí – doplň je do "
        f"TEXTOVA_POLE nebo LOGICKA_POLE v nastaveni_crm.py: {chybi}"
    )


def test_kazdy_sloupec_firmy_jde_vyplnit():
    """Nový sloupec v `CrmNastaveni` musí jít vyplnit formulářem i uložit."""
    whitelist = set(nastaveni_crm.TEXTOVA_POLE) | set(nastaveni_crm.LOGICKA_POLE)
    sloupce = _pole_modelu()
    assert not sorted(sloupce - whitelist), (
        "Tyhle sloupce firmy nejde uložit – chybí ve whitelistu nastaveni_crm.py: "
        f"{sorted(sloupce - whitelist)}"
    )
    assert not sorted(sloupce - set(FirmaVstup.model_fields)), (
        "Tyhle sloupce firmy nejde zadat – chybí ve schématu FirmaVstup: "
        f"{sorted(sloupce - set(FirmaVstup.model_fields))}"
    )


def test_whitelist_nepusti_systemova_pole():
    """Do konfigurace se nesmí dát přepsat klíč ani značka poslední úpravy."""
    whitelist = set(nastaveni_crm.TEXTOVA_POLE) | set(nastaveni_crm.LOGICKA_POLE)
    assert not (whitelist & NEEDITOVATELNE)


def test_slozena_adresa_dava_jeden_radek():
    n = SimpleNamespace(
        adresa_ulice="Křižíkova 148/34",
        adresa_psc="186 00",
        adresa_mesto="Praha 8",
    )
    assert nastaveni_crm.slozena_adresa(n) == "Křižíkova 148/34, 186 00 Praha 8"


def test_slozena_adresa_zvlada_chybejici_dily():
    """Lead-like stav: vyplněné je jen město. Nesmí vzniknout „, Praha“."""
    n = SimpleNamespace(adresa_ulice="", adresa_psc="", adresa_mesto="Praha")
    assert nastaveni_crm.slozena_adresa(n) == "Praha"

    prazdna = SimpleNamespace(adresa_ulice="", adresa_psc="", adresa_mesto="")
    assert nastaveni_crm.slozena_adresa(prazdna) == ""


def test_telefon_z_profilu_dostane_predvolbu():
    """Profil drží devět číslic (kvůli podpisu); v seznamu má být čitelné číslo."""
    assert nastaveni_crm._telefon("123456789") == "+420 123 456 789"
    # Cokoli jiného než devět číslic se nechává, jak je – radši surové číslo než
    # špatně poskládaná předvolba.
    assert nastaveni_crm._telefon("+420 123 456 789") == "+420 123 456 789"
    assert nastaveni_crm._telefon("") == ""
