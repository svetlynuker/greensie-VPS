"""Ukládání záznamů CRM po jednotlivých polích (automatické ukládání).

Proč to existuje: dosavadní `PUT /crm/zakaznici/{id}` a spol. přepisují CELÝ
záznam z formuláře, kde jsou nevyplněná pole prázdná. Dva lidé nad jednou
kartou si tedy navzájem přepíšou i pole, kterých se ani nedotkli — a u vlastních
polí (`extra`) je to ještě horší: `vlastni_pole.zpracuj()` staví nový slovník,
takže chybějící klíč se uložením SMAŽE. Autosave nad takovým endpointem by
z tiché ztráty dat udělal pravidlo.

Tenhle modul proto ukládá právě jedno pole, slučuje `extra` se stavem
v databázi a před zápisem kontroluje, že se hodnota od načtení nezměnila
(`puvodni`). Když ano, zápis se zastaví a člověk dostane na výběr — stejný
princip jako u matice (`app/matice/bunka_pole.py`).

Tři rozhodnutí, která nejsou zřejmá:

1. **Whitelist polí.** Generický endpoint bez seznamu povolených polí by
   dovolil přepsat cokoli, co je na modelu — vlastníka záznamu, `raynet_id`,
   příznaky. Povolená jsou jen pole, která člověk skutečně píše do formuláře.
   Stav, vlastnictví a mazání sem NEPATŘÍ: mají vedlejší efekty (automatizace,
   notifikace, povinná pole) a zůstávají na potvrzovací akci.

2. **Typ se bere z modelu**, ne z druhého seznamu — `_na_hodnotu()` čte typ
   sloupce SQLAlchemy. Druhý seznam typů by se rozešel s prvním.

3. **Rozepsaný stav není chyba.** Prázdná hodnota je legitimní (vymazání)
   a povinná vlastní pole se při ukládání po polích nevynucují — jinak by
   autosave u rozpracovaného záznamu vracel 422 a nefungoval vůbec. Povinnost
   se hlídá tam, kde na ní záleží: při přechodu stavu (`povinna_pole.py`).
"""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.crm import vlastni_pole as pole_modul
from app.crm.models import (
    CrmProjekt,
    ObchodniPripad,
    Objednavka,
    OdberneMisto,
    Zakaznik,
    ZakaznikKontakt,
)

# Klíč vlastního pole ve tvaru „extra:dotace“. Stejná předpona, jakou používá
# audit (`extra:`) i seznamy na frontendu.
PREDPONA_VLASTNI = "extra:"


class Konflikt(Exception):
    """Hodnotu mezitím změnil někdo jiný — nepřepisujeme, ptáme se."""

    def __init__(self, *, pole: str, aktualni: str, zmenil_id: int | None, zmeneno_at):
        super().__init__(f"Pole {pole} mezitím změnil někdo jiný")
        self.pole = pole
        self.aktualni = aktualni
        self.zmenil_id = zmenil_id
        self.zmeneno_at = zmeneno_at


class Nepovolene(Exception):
    """Neznámá entita nebo pole, které se přes autosave měnit nesmí."""


@dataclass(frozen=True)
class Entita:
    """Jeden druh záznamu, který se dá ukládat po polích."""

    klic: str
    model: type
    pravo: str
    # Whitelist sloupců, které smí měnit automatické ukládání.
    pole: tuple[str, ...]
    popis: str
    # Klíč pro vlastní pole (`vlastni_pole.MODELY`) nebo None, když je nemá.
    vlastni: str | None = None
    # Entita pro automatizaci „změní se pole“ (CRM-31) nebo None.
    automatizace: str | None = None
    # Ověření přístupu ke konkrétnímu záznamu: (db, zaznam, user) → nic, nebo
    # HTTPException 404. Viz `_pristup_*` níž.
    overit_pristup: Callable[[Session, object, object], None] | None = None


def _pristup_dle_aktivit(entita_klic: str) -> Callable[[Session, object, object], None]:
    """Použije pravidla, která už v CRM platí pro aktivity a audit.

    Nevymýšlí se tu druhá sada pravidel: `_over_pristup_k_zaznamu` řeší i to,
    že objednávka, projekt a nabídka vlastníka nemají a práva dědí z obchodního
    případu — a že nabídka bez případu patří jen `crm_vse`. Dvě kopie stejného
    pravidla by se rozešly a jedna z nich by pouštěla dál, než má.
    """

    def fn(db: Session, zaznam, user) -> None:
        from app.crm.routes import _over_pristup_k_zaznamu

        _over_pristup_k_zaznamu(db, entita_klic, zaznam.id, user)

    return fn


def _model_nabidky() -> type:
    """Model nabídky. Import uvnitř funkce — nabídkovač a CRM se navzájem
    neimportují na úrovni modulu (stejný zvyk jako v `crm/routes.py`)."""
    from app.nabidkovac.models import Nabidka

    return Nabidka


def _pristup_pres_zakaznika(db: Session, zaznam, user) -> None:
    """Kontaktní osoba vlastníka nemá — právo dědí od svého zákazníka."""
    from app.crm.pristup import vyzaduj_zaznam

    vyzaduj_zaznam(db.get(Zakaznik, zaznam.zakaznik_id), user, "Zákazník")


# Pozn.: `stav`, `duvod_prohry`, `duvod_zruseni`, vlastnictví, `kategorie`
# (multiselect s validací) ani `hlavni` u kontaktu tu schválně nejsou — každé
# z nich má vedlejší efekt na jiné záznamy nebo spouští automatizaci, takže
# patří na vědomé potvrzení, ne na ukládání za pochodu.
ENTITY: dict[str, Entita] = {
    "zakaznik": Entita(
        klic="zakaznik",
        model=Zakaznik,
        pravo="zakaznici",
        popis="Zákazník",
        pole=(
            "nazev",
            "ico",
            "dic",
            "adresa_ulice",
            "adresa_mesto",
            "adresa_psc",
            "adresa_stat",
            "gps_lat",
            "gps_lng",
            "web",
            "telefon",
            "email",
            "zdroj",
            "poznamka",
        ),
        vlastni="zakaznik",
        overit_pristup=_pristup_dle_aktivit("zakaznik"),
    ),
    "kontakt": Entita(
        klic="kontakt",
        model=ZakaznikKontakt,
        pravo="zakaznici",
        popis="Kontaktní osoba",
        pole=("jmeno", "funkce", "email", "telefon", "poznamka"),
        overit_pristup=_pristup_pres_zakaznika,
    ),
    "om": Entita(
        klic="om",
        model=OdberneMisto,
        pravo="zakaznici",
        popis="Odběrné místo",
        pole=(
            "nazev",
            "adresa_ulice",
            "adresa_mesto",
            "adresa_psc",
            "distributor",
            "napetova_hladina",
            "rezervovana_kapacita_kw",
            "rezervovany_prikon_kw",
            "poznamka",
        ),
        vlastni="om",
        overit_pristup=_pristup_dle_aktivit("om"),
    ),
    "op": Entita(
        klic="op",
        model=ObchodniPripad,
        pravo="obchodni_pripady",
        popis="Obchodní případ",
        pole=("nazev", "popis", "hodnota_kc", "pravdepodobnost", "predpokladane_uzavreni"),
        vlastni="op",
        automatizace="op",
        overit_pristup=_pristup_dle_aktivit("op"),
    ),
    "obj": Entita(
        klic="obj",
        model=Objednavka,
        pravo="obchodni_pripady",
        popis="Objednávka",
        pole=("nazev", "popis", "cena_kc", "datum_podpisu", "datum_dodani"),
        vlastni="obj",
        automatizace="obj",
        overit_pristup=_pristup_dle_aktivit("obj"),
    ),
    "pro": Entita(
        klic="pro",
        model=CrmProjekt,
        pravo="obchodni_pripady",
        popis="Projekt",
        pole=("nazev", "popis", "zahajeni", "predani"),
        vlastni="pro",
        automatizace="pro",
        overit_pristup=_pristup_dle_aktivit("pro"),
    ),
    "nab": Entita(
        klic="nab",
        model=_model_nabidky(),
        pravo="nabidkovac",
        popis="Nabídka",
        # Jen blok „Údaje zákazníka“ v detailu nabídky. Vstupy výpočtu (profil
        # spotřeby, sazby, parametry PPA/BESS) sem NEPATŘÍ: nabídka se z nich
        # přepočítává do verzí, takže je ukládá až tlačítko „Spočítat“.
        pole=("zakaznik_nazev", "zakaznik_adresa", "zakaznik_gps_lat", "zakaznik_gps_lng"),
        vlastni="nab",
        automatizace="nab",
        overit_pristup=_pristup_dle_aktivit("nab"),
    ),
}


def entita(klic: str) -> Entita:
    e = ENTITY.get(klic)
    if e is None:
        raise Nepovolene(f"Neznámá entita: {klic}")
    return e


def zkontroluj_whitelist() -> list[str]:
    """Ověří, že každé pole ve whitelistu na modelu skutečně existuje.

    Překlep by se jinak projevil až za běhu jako „pole nelze měnit“ u něčeho,
    co evidentně existuje. Volá to test, ne aplikace.
    """
    chyby = []
    for e in ENTITY.values():
        sloupce = {c.key for c in sa_inspect(e.model).columns}
        for p in e.pole:
            if p not in sloupce:
                chyby.append(f"{e.klic}.{p}")
        if e.vlastni and "extra" not in sloupce:
            chyby.append(f"{e.klic}.extra")
    return chyby


# ---- převody hodnot ----
def _sloupec(e: Entita, pole: str):
    return sa_inspect(e.model).columns[pole]


def na_text(hodnota) -> str:
    """Hodnota tak, jak ji vidí prohlížeč. Nevyplněno je vždy prázdný text."""
    if hodnota is None:
        return ""
    if isinstance(hodnota, bool):
        return "1" if hodnota else ""
    if isinstance(hodnota, (date, datetime)):
        return hodnota.isoformat()[:10]
    if isinstance(hodnota, Decimal):
        # Bez exponentu a bez zbytečných nul: „1500000.00“ i „1.5E+6“ by se
        # v prohlížeči porovnávaly špatně (viz `_stejne`).
        return format(hodnota.normalize(), "f")
    return str(hodnota)


def _stejne(a: str, b: str) -> bool:
    """Rovnají se dvě textové podoby hodnoty?

    Čísla se porovnávají číselně: databáze vrátí `1500000.00`, prohlížeč pošle
    `1500000` — textově se to nerovná a člověk by dostal hlášku o kolizi tam,
    kde se nic nezměnilo.
    """
    if a == b:
        return True
    try:
        return Decimal(a.replace(",", ".")) == Decimal(b.replace(",", "."))
    except (InvalidOperation, AttributeError, ValueError):
        return False


def _na_hodnotu(e: Entita, pole: str, text: str):
    """Text z formuláře → hodnota pro sloupec. Typ se bere z modelu."""
    sloupec = _sloupec(e, pole)
    typ = sloupec.type
    prazdno = text is None or str(text).strip() == ""

    if isinstance(typ, Boolean):
        return str(text).strip().lower() in ("1", "true", "ano", "on")

    if prazdno:
        if sloupec.nullable:
            return None
        # NOT NULL text (např. povinný název) se dá „vyprázdnit“ jen na prázdný
        # řetězec; číslo ani datum ne — to by spadlo až na databázi.
        if isinstance(typ, (Integer, Numeric, Date, DateTime)):
            raise ValueError(f"Pole „{pole}“ nemůže zůstat prázdné.")
        return ""

    text = str(text).strip()
    if isinstance(typ, Integer):
        try:
            return int(text)
        except ValueError:
            raise ValueError(f"„{text}“ není celé číslo.")
    if isinstance(typ, Numeric):
        try:
            return Decimal(text.replace(" ", "").replace(",", "."))
        except InvalidOperation:
            raise ValueError(f"„{text}“ není číslo.")
    if isinstance(typ, (Date, DateTime)):
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"„{text}“ není datum ve tvaru RRRR-MM-DD.")
    return text


# ---- čtení a kontrola ----
def je_vlastni(pole: str) -> bool:
    return pole.startswith(PREDPONA_VLASTNI)


def klic_vlastniho(pole: str) -> str:
    return pole[len(PREDPONA_VLASTNI) :]


def over_pole(e: Entita, pole: str) -> None:
    if je_vlastni(pole):
        if not e.vlastni:
            raise Nepovolene(f"{e.popis} vlastní pole nemá.")
        if not klic_vlastniho(pole):
            raise Nepovolene("Chybí klíč vlastního pole.")
        return
    if pole not in e.pole:
        raise Nepovolene(
            f"Pole „{pole}“ se přes automatické ukládání měnit nedá ({e.popis})."
        )


def hodnota_textem(e: Entita, zaznam, pole: str) -> str:
    """Aktuální hodnota pole v databázi jako text.

    U vlastních polí se čte přímo z `extra`, NE z výstupu se zápočtem
    (`s_vypocty`) — ten dopočítává výpočtová pole, která v databázi nejsou,
    a kontrola kolize by na nich hlásila rozdíl pořád.
    """
    if je_vlastni(pole):
        return na_text((zaznam.extra or {}).get(klic_vlastniho(pole)))
    return na_text(getattr(zaznam, pole))


def zkontroluj_kolizi(e: Entita, zaznam, *, pole: str, puvodni: str | None) -> None:
    """Ověří, že v databázi je pořád to, co měl člověk na obrazovce.

    `puvodni=None` znamená „ulož bez kontroly“ — použije se, až člověk v hlášce
    o kolizi potvrdí, že chce svou hodnotu.
    """
    if puvodni is None:
        return
    aktualni = hodnota_textem(e, zaznam, pole)
    if not _stejne(aktualni, puvodni):
        raise Konflikt(
            pole=pole,
            aktualni=aktualni,
            zmenil_id=getattr(zaznam, "zmenil_id", None),
            zmeneno_at=getattr(zaznam, "zmeneno_at", None),
        )


# ---- zápis ----
def oznac_zmenu(zaznam, uzivatel_id: int | None) -> None:
    """Kdo a kdy naposledy změnil + posun verze (pro razítko a hlášku o kolizi)."""
    zaznam.zmeneno_at = datetime.now(timezone.utc)
    if hasattr(zaznam, "zmenil_id"):
        zaznam.zmenil_id = uzivatel_id
    if hasattr(zaznam, "verze"):
        zaznam.verze = (zaznam.verze or 0) + 1


def zapis_pole(
    db: Session, e: Entita, zaznam, *, pole: str, hodnota: str | None, uzivatel_id: int | None
) -> None:
    """Zapíše jedno pole. Necommituje — to dělá endpoint.

    Neplatná hodnota vyhodí ValueError (endpoint z ní udělá 422 s čitelnou
    hláškou). Prázdná hodnota chybou NENÍ, jen se pole vymaže.
    """
    hodnota = hodnota if hodnota is not None else ""

    if je_vlastni(pole):
        klic = klic_vlastniho(pole)
        ulozit, cista = pole_modul.zpracuj_jedno(db, e.vlastni or "", klic, hodnota)
        # Sloučení se stavem v databázi. Nový slovník je tu nutnost, ne styl:
        # SQLAlchemy si změnu uvnitř JSONB slovníku nevšimne, dokud se atribut
        # nepřiřadí znovu.
        soucasne = dict(zaznam.extra or {})
        if ulozit:
            soucasne[klic] = cista
        else:
            soucasne.pop(klic, None)
        zaznam.extra = soucasne
    else:
        setattr(zaznam, pole, _na_hodnotu(e, pole, hodnota))
        _po_zapisu(db, e, zaznam, pole)

    oznac_zmenu(zaznam, uzivatel_id)


def _po_zapisu(db: Session, e: Entita, zaznam, pole: str) -> None:
    """Dopočty, které musí následovat po zápisu konkrétního pole."""
    if e.klic == "obj" and pole == "cena_kc":
        # Ručně přepsaná cena má přednost před součtem rozpisu. Na rozdíl od
        # `PUT` tu není heuristika „rovná se součtu, takže ji nesahal“ — přes
        # ukládání po polích přijde jen to, co člověk skutečně napsal.
        zaznam.cena_rucni = zaznam.cena_kc is not None
