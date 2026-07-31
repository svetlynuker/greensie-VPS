"""Oblíbené a naposledy otevřené záznamy (CRM-37).

Rychlý návrat k tomu, s čím člověk zrovna pracuje. Zobrazuje se v globálním
hledání (Ctrl+K) hned po otevření, dokud se nezačne psát — je to místo, kam
už dnes lidé chodí hledat záznam podle názvu.

---- Dvě věci, na kterých to stojí ----

1. **Historie se ořezává při zápisu, ne při čtení.** Kdyby se jen přidávalo,
   tabulka by rostla donekonečna a „naposledy otevřené" by byl archiv. Držíme
   posledních `MAX_HISTORIE` na uživatele; oblíbené se do limitu nepočítají
   a nikdy se nesmažou samy.
2. **Názvy se dotahují až při čtení** (přes `ukoly.popisy_zaznamu`), ne že by
   se ukládaly s odkazem. Kdyby se uložil název, po přejmenování firmy by
   v historii svítil starý — a člověk by klikal na něco, co už se jinak jmenuje.
   Záznam, který mezitím zmizel, se při čtení prostě přeskočí.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmOblibene
from app.crm.ukoly import ENTITY, cesta_zaznamu, popisy_zaznamu

# Kolik naposledy otevřených se pamatuje na uživatele (oblíbené mimo limit).
MAX_HISTORIE = 15
# Kolik se jich vrací do UI.
LIMIT_VYPISU = 8


def zaznamenej(db: Session, user: User, entita: str, zaznam_id: int) -> None:
    """Zapíše otevření záznamu. Nikdy nevyhodí výjimku ani nedělá commit —
    volá se z detailu, kde je to vedlejší efekt, ne účel požadavku."""
    if entita not in ENTITY or not zaznam_id:
        return
    row = (
        db.query(CrmOblibene)
        .filter(
            CrmOblibene.uzivatel_id == user.id,
            CrmOblibene.entita == entita,
            CrmOblibene.zaznam_id == zaznam_id,
        )
        .first()
    )
    if row is None:
        row = CrmOblibene(uzivatel_id=user.id, entita=entita, zaznam_id=zaznam_id)
        db.add(row)
    # `onupdate` se bez změny sloupce nespustí, proto se čas zapisuje ručně.
    row.otevreno_at = datetime.now(timezone.utc)
    db.flush()
    _orez_historii(db, user.id)


def _orez_historii(db: Session, uzivatel_id: int) -> None:
    prebytek = (
        db.query(CrmOblibene)
        .filter(
            CrmOblibene.uzivatel_id == uzivatel_id,
            CrmOblibene.oblibene.is_(False),
        )
        .order_by(CrmOblibene.otevreno_at.desc())
        .offset(MAX_HISTORIE)
        .all()
    )
    for row in prebytek:
        db.delete(row)


def prepni_oblibene(db: Session, user: User, entita: str, zaznam_id: int, hodnota: bool) -> bool:
    """Přišpendlí nebo odšpendlí záznam. Vrací výsledný stav."""
    if entita not in ENTITY:
        return False
    row = (
        db.query(CrmOblibene)
        .filter(
            CrmOblibene.uzivatel_id == user.id,
            CrmOblibene.entita == entita,
            CrmOblibene.zaznam_id == zaznam_id,
        )
        .first()
    )
    if row is None:
        row = CrmOblibene(uzivatel_id=user.id, entita=entita, zaznam_id=zaznam_id)
        db.add(row)
    row.oblibene = bool(hodnota)
    # Odšpendlený záznam zůstává v historii — člověk ho měl otevřený, jen ho
    # nechce mít přišpendlený. Ořez se o něj postará stejně jako o ostatní.
    db.commit()
    return bool(hodnota)


def _slozeni(db: Session, rows: list[CrmOblibene]) -> list[dict]:
    """Doplní názvy a cesty; položky, jejichž záznam zmizel, vypadnou."""
    podle_entity: dict[str, set[int]] = {}
    for r in rows:
        podle_entity.setdefault(r.entita, set()).add(r.zaznam_id)
    nazvy = {e: popisy_zaznamu(db, e, ids) for e, ids in podle_entity.items()}

    out = []
    for r in rows:
        nazev = nazvy.get(r.entita, {}).get(r.zaznam_id)
        if not nazev:
            continue  # záznam už neexistuje
        out.append(
            {
                "entita": r.entita,
                "zaznam_id": r.zaznam_id,
                "nazev": nazev,
                "cesta": cesta_zaznamu(r.entita, r.zaznam_id),
                "oblibene": bool(r.oblibene),
            }
        )
    return out


def seznam(db: Session, user: User) -> dict:
    """{oblibene: [...], nedavne: [...]} pro nabídku v hledání."""
    vse = (
        db.query(CrmOblibene)
        .filter(CrmOblibene.uzivatel_id == user.id)
        .order_by(CrmOblibene.otevreno_at.desc())
        .all()
    )
    slozene = _slozeni(db, vse)
    return {
        "oblibene": [x for x in slozene if x["oblibene"]][:LIMIT_VYPISU],
        # Přišpendlené se v „naposledy" neopakují – byly by tam dvakrát.
        "nedavne": [x for x in slozene if not x["oblibene"]][:LIMIT_VYPISU],
    }


def je_oblibeny(db: Session, user: User, entita: str, zaznam_id: int) -> bool:
    row = (
        db.query(CrmOblibene.oblibene)
        .filter(
            CrmOblibene.uzivatel_id == user.id,
            CrmOblibene.entita == entita,
            CrmOblibene.zaznam_id == zaznam_id,
        )
        .first()
    )
    return bool(row[0]) if row else False
