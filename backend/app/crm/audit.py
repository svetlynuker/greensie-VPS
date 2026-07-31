"""Audit log změn záznamů CRM (CRM-12).

Sbírá se **automaticky** přes událost SQLAlchemy `before_flush`, ne voláním
v endpointech. Je to zásadní rozdíl: ruční `zaloguj(...)` v každém endpointu
je věc, která se u desátého endpointu vynechá a nikdo si toho nevšimne, dokud
v logu něco nechybí — což je zrovna u auditu k ničemu.

---- Kdo změnu udělal ----------------------------------------------------

V události nemáme přístup k requestu, takže uživatele nese `contextvar`, kterou
nastaví autentizace (`auth.permissions.get_current_user`). Contextvar je na to
správný nástroj: drží hodnotu per úloha, takže dva souběžné requesty si ji
navzájem nepřepíšou (na rozdíl od globální proměnné).

Když uživatel není (migrace, skript, plánovač), zapíše se změna bez autora —
pořád je cennější než žádný záznam.

---- Co se NELOGUJE a proč ------------------------------------------------

  * technická pole (`aktualizovano_at`, `vytvoreno_at`) — mění se pokaždé a
    zaplevelila by log natolik, že by v něm nešlo nic najít,
  * tabulky samotného provozu (audit, notifikace, historie stavů, oblíbené) —
    logovat log je nekonečná smyčka a notifikace nejsou uživatelská data,
  * změna z prázdna na prázdno (`None` → `""`), kterou dělá ORM při ukládání
    nevyplněného formuláře.

Stav se neloguje taky — má vlastní, bohatší historii (`crm_stav_historie`)
a v UI by se pak každá změna zobrazila dvakrát.
"""

import logging
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# Uživatel aktuálního requestu. Nastavuje `get_current_user`, čte událost.
aktualni_uzivatel_id: ContextVar[int | None] = ContextVar("audit_uzivatel_id", default=None)

# Model → klíč entity v logu. Co tu není, se neloguje (aktivity, kroky projektu
# a číselníky mají vlastní historii nebo je jejich změna bezvýznamná).
SLEDOVANE: dict[str, str] = {
    "Zakaznik": "zakaznik",
    "ObchodniPripad": "op",
    "Objednavka": "obj",
    "CrmProjekt": "pro",
    "OdberneMisto": "om",
    "Nabidka": "nab",
}

# Pole, která se nikdy nelogují — technická nebo s vlastní historií.
IGNOROVANA_POLE = {
    "vytvoreno_at",
    "aktualizovano_at",
    "uzavreno_at",
    "konvertovan_at",
    "stav",  # má `crm_stav_historie`
    "stav_obchodni",
    "extra",  # vlastní pole se logují po klíčích, viz `_zmeny_extra`
}

# Lidské názvy nejčastějších polí. Co tu není, se ukáže jako klíč — pořád
# čitelnější než nic, a doplnit se dá kdykoli.
NAZVY_POLI = {
    "nazev": "název",
    "popis": "popis",
    "ico": "IČO",
    "dic": "DIČ",
    "email": "e-mail",
    "telefon": "telefon",
    "hodnota_kc": "hodnota",
    "cena_kc": "cena",
    "pravdepodobnost": "pravděpodobnost",
    "predpokladane_uzavreni": "předpokládané uzavření",
    "datum_podpisu": "datum podpisu",
    "datum_dodani": "datum dodání",
    "zahajeni": "zahájení",
    "predani": "předání",
    "vlastnik_user_id": "vlastník",
    "spoluvlastnici": "spoluvlastníci",
    "duvod_prohry": "důvod prohry",
    "duvod_zruseni": "důvod zrušení",
    "zakaznik_id": "zákazník",
    "odberne_misto_id": "odběrné místo",
    "raynet_code": "číslo v Raynetu",
    "typ": "typ",
    "kategorie": "kategorie",
}


def nazev_pole(klic: str) -> str:
    return NAZVY_POLI.get(klic, klic.replace("_", " "))


def _text(hodnota) -> str:
    """Hodnota do logu. Prázdné jako prázdný řetězec, ať se v UI neřeší None."""
    if hodnota is None:
        return ""
    if isinstance(hodnota, bool):
        return "ano" if hodnota else "ne"
    if isinstance(hodnota, Decimal):
        cislo = float(hodnota)
        return str(int(cislo)) if cislo == int(cislo) else f"{cislo:.2f}"
    if isinstance(hodnota, float):
        return str(int(hodnota)) if hodnota == int(hodnota) else f"{hodnota:.2f}"
    if isinstance(hodnota, (datetime, date)):
        return hodnota.isoformat()[:19]
    if isinstance(hodnota, (list, tuple)):
        return ", ".join(_text(x) for x in hodnota)
    return str(hodnota)


def _zmeny_extra(stara: dict | None, nova: dict | None) -> list[tuple[str, str, str]]:
    """Vlastní pole (JSONB `extra`) se logují po klíčích, ne jako celý slovník.

    Jinak by v logu bylo „extra: {…} → {…}" a nikdo by nepoznal, co se změnilo.
    """
    stara = stara or {}
    nova = nova or {}
    out = []
    for klic in sorted(set(stara) | set(nova)):
        a, b = _text(stara.get(klic)), _text(nova.get(klic))
        if a != b:
            out.append((f"extra:{klic}", a, b))
    return out


def _puvodni_radek(session: Session, obj):
    """Hodnoty, jak jsou teď v databázi — tedy PŘED tímhle uložením.

    Čte se přes `session.connection()`, ne přes ORM: `session.get()` by vrátil
    tentýž objekt z identity map, který už změny obsahuje, takže by nebylo
    s čím porovnávat. Surový SELECT v `before_flush` běží ještě před zápisem,
    takže vidí původní stav.

    Proč ne jednodušší `attrs[...].history`: po commitu jsou atributy
    vyexpirované a SQLAlchemy si starou hodnotu nepamatuje. Audit by pak
    u každé změny hlásil „z prázdna na X" — a informace „z čeho se to změnilo",
    kvůli které log existuje, by chyběla přesně tam, kde je potřeba.
    """
    from sqlalchemy import select

    tabulka = obj.__table__
    zaznam_id = getattr(obj, "id", None)
    if zaznam_id is None:
        return None
    return (
        session.connection()
        .execute(select(tabulka).where(tabulka.c.id == zaznam_id))
        .mappings()
        .first()
    )


def _zaznamy_zmen(session: Session, obj) -> list[tuple[str, str, str]]:
    """(pole, stará, nová) pro sloupce, které se opravdu změnily."""
    puvodni = _puvodni_radek(session, obj)
    if puvodni is None:
        return []

    stav = inspect(obj)
    out: list[tuple[str, str, str]] = []
    for atribut in stav.mapper.column_attrs:
        klic = atribut.key
        sloupec = atribut.expression.key  # název sloupce v tabulce
        if sloupec not in puvodni:
            continue
        stara = puvodni[sloupec]
        nova = getattr(obj, klic, None)

        if klic == "extra":
            out.extend(_zmeny_extra(stara, nova))
            continue
        if klic in IGNOROVANA_POLE:
            continue

        a, b = _text(stara), _text(nova)
        if a == b:
            continue  # beze změny, nebo jen kosmetický rozdíl (None vs. "")
        out.append((klic, a, b))
    return out


def _pridej(session: Session, entita: str, zaznam_id, druh: str, pole="", stara="", nova=""):
    from app.crm.models import CrmAudit

    session.add(
        CrmAudit(
            entita=entita,
            # U nově vzniklého záznamu ještě id není – doplní se po flush níž.
            zaznam_id=zaznam_id or 0,
            druh=druh,
            pole=pole,
            stara=stara[:2000],
            nova=nova[:2000],
            zmenil_user_id=aktualni_uzivatel_id.get(),
        )
    )


def _before_flush(session: Session, kontext, instance):  # noqa: ARG001
    from app.crm.models import CrmAudit

    try:
        for obj in session.dirty:
            entita = SLEDOVANE.get(type(obj).__name__)
            if entita is None or not session.is_modified(obj, include_collections=False):
                continue
            for pole, stara, nova in _zaznamy_zmen(session, obj):
                _pridej(session, entita, getattr(obj, "id", None), "zmena", pole, stara, nova)

        for obj in session.deleted:
            entita = SLEDOVANE.get(type(obj).__name__)
            if entita is None:
                continue
            _pridej(session, entita, getattr(obj, "id", None), "smazani")

        # Vznik se loguje bez polí – co v záznamu je, ukáže sám záznam. Řádek
        # je tu proto, aby log začínal „vytvořil X dne Y" a nekřičel prázdnem.
        for obj in session.new:
            if isinstance(obj, CrmAudit):
                continue
            entita = SLEDOVANE.get(type(obj).__name__)
            if entita is None:
                continue
            _zapisy_vzniku.setdefault(id(session), []).append((obj, entita))
    except Exception:  # noqa: BLE001 - audit nikdy nesmí shodit uložení
        log.warning("Audit selhal při skládání změn", exc_info=True)


# Vznik se dá zapsat až po flush, kdy má záznam id. Držíme ho stranou podle
# session, protože `after_flush` už novou instanci v `session.new` nemá.
_zapisy_vzniku: dict[int, list] = {}


def _after_flush(session: Session, kontext):  # noqa: ARG001
    cekajici = _zapisy_vzniku.pop(id(session), [])
    if not cekajici:
        return
    from app.crm.models import CrmAudit

    try:
        for obj, entita in cekajici:
            if getattr(obj, "id", None) is None:
                continue
            session.add(
                CrmAudit(
                    entita=entita,
                    zaznam_id=obj.id,
                    druh="vznik",
                    pole="",
                    stara="",
                    nova="",
                    zmenil_user_id=aktualni_uzivatel_id.get(),
                )
            )
    except Exception:  # noqa: BLE001
        log.warning("Audit selhal při zápisu vzniku", exc_info=True)


def zapni() -> None:
    """Zapne sběr. Volá se jednou při startu (`app.main`)."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)
    if not event.contains(Session, "after_flush", _after_flush):
        event.listen(Session, "after_flush", _after_flush)


def zaznamy(db: Session, entita: str, zaznam_id: int, limit: int = 100) -> list:
    from app.crm.models import CrmAudit

    return (
        db.query(CrmAudit)
        .filter(CrmAudit.entita == entita, CrmAudit.zaznam_id == zaznam_id)
        .order_by(CrmAudit.id.desc())
        .limit(limit)
        .all()
    )
