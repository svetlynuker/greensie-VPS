"""Registr entit, u kterých appka sleduje přítomnost a změny.

Přidat další modul = jeden řádek tady:

- `pravo` — klíč z `auth/permissions.PRAVA`. Kdo nesmí modul otevřít, nesmí
  ani vidět, kdo v něm je. Bez toho by byl seznam přítomných dírou v právech.
- `razitko` — funkce, která vrátí krátký podpis stavu modulu. Klient ho
  porovnává s tím, co drží; při změně si data načte znovu.

Neznámý typ endpoint odmítne — jinak by si každý mohl do tabulky psát vlastní
kategorie a nikdo by nevěděl, co v ní je.
"""

from typing import Callable

from sqlalchemy.orm import Session


def _razitko_matice(db: Session) -> str:
    # Import až tady, aby modul přítomnosti nezáležel na modulu matice
    # (a nevznikl kruh, když si matice jednou vyžádá přítomnost).
    from app.matice.razitko import razitko_matice

    return razitko_matice(db)


ENTITY: dict[str, dict[str, object]] = {
    "matice": {"pravo": "projekty", "razitko": _razitko_matice},
}


def pravo_pro(entita_typ: str) -> str | None:
    zapis = ENTITY.get(entita_typ)
    return zapis["pravo"] if zapis else None  # type: ignore[return-value]


def razitko(db: Session, entita_typ: str) -> str:
    zapis = ENTITY.get(entita_typ)
    if not zapis:
        return ""
    fn: Callable[[Session], str] = zapis["razitko"]  # type: ignore[assignment]
    return fn(db)
