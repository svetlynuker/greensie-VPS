"""Registr entit, u kterých appka sleduje přítomnost a změny.

Přidat další modul = jeden řádek tady:

- `pravo` — klíč z `auth/permissions.PRAVA`. Kdo nesmí modul otevřít, nesmí
  ani vidět, kdo v něm je. Bez toho by byl seznam přítomných dírou v právech.
- `razitko` — funkce `(db, entita_id)`, která vrátí krátký podpis stavu. Klient
  ho porovnává s tím, co drží; při změně si data načte znovu.
- `pristup` — nepovinná funkce `(db, user, entita_id)`, která ověří přístup ke
  KONKRÉTNÍMU záznamu. U matice není potřeba (kdo ji smí otevřít, vidí ji
  celou), ale CRM má druhou vrstvu viditelnosti: bez práva `crm_vse` vidí
  člověk jen svoje záznamy. Bez tohohle ověření by se dalo zkoušením ID
  zjistit, že cizí případ existuje a kdo na něm pracuje — přesně to, čemu
  brání 404 místo 403 v `crm/pristup.py`.

Neznámý typ endpoint odmítne — jinak by si každý mohl do tabulky psát vlastní
kategorie a nikdo by nevěděl, co v ní je.
"""

from typing import Callable

from sqlalchemy.orm import Session

from app.auth.models import User


def _razitko_matice(db: Session, entita_id: str) -> str:
    # Import až tady, aby modul přítomnosti nezáležel na modulu matice
    # (a nevznikl kruh, když si matice jednou vyžádá přítomnost).
    from app.matice.razitko import razitko_matice

    # Matice je jedna tabulka pro všechny — `entita_id` u ní nemá význam.
    return razitko_matice(db)


def _razitko_crm(entita: str) -> Callable[[Session, str], str]:
    def fn(db: Session, entita_id: str) -> str:
        from app.crm.razitko import razitko_zaznamu

        try:
            cislo = int(entita_id)
        except (TypeError, ValueError):
            return ""
        return razitko_zaznamu(db, entita, cislo)

    return fn


def _razitko_seznamu(entita: str) -> Callable[[Session, str], str]:
    def fn(db: Session, entita_id: str) -> str:
        from app.crm.razitko import razitko_seznamu

        return razitko_seznamu(db, entita)

    return fn


def _pristup_crm(entita: str) -> Callable[[Session, User, str], bool]:
    """Vidí uživatel konkrétní záznam CRM?

    Pravidla se neopisují — použije se `Entita.overit_pristup` z
    `crm/pole_zaznamu.py`, tedy tatáž kontrola jako u ukládání. Ta vyhazuje
    HTTPException (404), takže ji tu jen převedeme na ano/ne.
    """

    def fn(db: Session, user: User, entita_id: str) -> bool:
        from fastapi import HTTPException

        from app.crm.pole_zaznamu import ENTITY as CRM_ENTITY

        popis = CRM_ENTITY.get(entita)
        if popis is None:
            return False
        try:
            cislo = int(entita_id)
        except (TypeError, ValueError):
            return False
        zaznam = db.get(popis.model, cislo)
        if zaznam is None:
            return False
        if popis.overit_pristup is None:
            return True
        try:
            popis.overit_pristup(db, zaznam, user)
        except HTTPException:
            return False
        return True

    return fn


ENTITY: dict[str, dict[str, object]] = {
    "matice": {"pravo": "projekty", "razitko": _razitko_matice},
    # CRM. Právo odpovídá gate funkcím v `crm/pristup.py`: zákazníci, kontakty
    # a odběrná místa jedou pod „zakaznici“, případy, objednávky a projekty pod
    # „obchodni_pripady“.
    "crm_zakaznik": {
        "pravo": "zakaznici",
        "razitko": _razitko_crm("zakaznik"),
        "pristup": _pristup_crm("zakaznik"),
    },
    "crm_kontakt": {
        "pravo": "zakaznici",
        "razitko": _razitko_crm("kontakt"),
        "pristup": _pristup_crm("kontakt"),
    },
    "crm_om": {
        "pravo": "zakaznici",
        "razitko": _razitko_crm("om"),
        "pristup": _pristup_crm("om"),
    },
    "crm_op": {
        "pravo": "obchodni_pripady",
        "razitko": _razitko_crm("op"),
        "pristup": _pristup_crm("op"),
    },
    "crm_obj": {
        "pravo": "obchodni_pripady",
        "razitko": _razitko_crm("obj"),
        "pristup": _pristup_crm("obj"),
    },
    "crm_pro": {
        "pravo": "obchodni_pripady",
        "razitko": _razitko_crm("pro"),
        "pristup": _pristup_crm("pro"),
    },
    "crm_nab": {
        "pravo": "nabidkovac",
        "razitko": _razitko_crm("nab"),
        "pristup": _pristup_crm("nab"),
    },
    # Seznamy a kanbany. `entita_id` se nepoužívá — razítko je za celý seznam.
    # Přítomnost se tu nezobrazuje (kolečko „pět lidí je v seznamu“ je šum),
    # jde jen o to, aby se obrazovka sama aktualizovala po cizí změně.
    "crm_seznam_zakaznik": {"pravo": "zakaznici", "razitko": _razitko_seznamu("zakaznik")},
    "crm_seznam_op": {"pravo": "obchodni_pripady", "razitko": _razitko_seznamu("op")},
    "crm_seznam_obj": {"pravo": "obchodni_pripady", "razitko": _razitko_seznamu("obj")},
    "crm_seznam_pro": {"pravo": "obchodni_pripady", "razitko": _razitko_seznamu("pro")},
    "crm_seznam_nab": {"pravo": "nabidkovac", "razitko": _razitko_seznamu("nab")},
}


def pravo_pro(entita_typ: str) -> str | None:
    zapis = ENTITY.get(entita_typ)
    return zapis["pravo"] if zapis else None  # type: ignore[return-value]


def ma_pristup(db: Session, user: User, entita_typ: str, entita_id: str) -> bool:
    """Smí uživatel vidět konkrétní záznam? Bez zapsané funkce platí „ano“.

    Prázdné `entita_id` znamená „celý modul“ (matice, kanban) — tam se
    per-záznamová kontrola nedělá, na to je modulové právo.
    """
    zapis = ENTITY.get(entita_typ)
    if not zapis or not entita_id:
        return True
    fn = zapis.get("pristup")
    if fn is None:
        return True
    return bool(fn(db, user, entita_id))  # type: ignore[operator]


def razitko(db: Session, entita_typ: str, entita_id: str = "") -> str:
    """Podpis stavu entity. `entita_id` rozlišuje jednotlivé záznamy.

    U modulu, který se zobrazuje celý naráz (matice), se `entita_id` ignoruje.
    U CRM je naopak nutné: dva lidé v detailech dvou různých zákazníků nemají
    proč navzájem přenačítat obrazovku.
    """
    zapis = ENTITY.get(entita_typ)
    if not zapis:
        return ""
    fn: Callable[[Session, str], str] = zapis["razitko"]  # type: ignore[assignment]
    return fn(db, entita_id)
