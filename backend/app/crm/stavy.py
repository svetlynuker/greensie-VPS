"""Výchozí stavy pipeline pro obchodní případ, nabídku, objednávku a projekt.

Stavy jsou DATA, ne kód: kanban kreslí sloupce podle tabulky `crm_stavy`,
takže přidání nebo přejmenování fáze je práce pro vedení v nastavení CRM.
Tady jsou jen výchozí sady, kterými se prázdná tabulka naseeduje – aby appka
po nasazení fungovala bez ručního zakládání.

`druh` řídí chování:
  otevreny → případ je živý, počítá se do pipeline
  vyhra    → uzavírá případ (a u obchodního případu smí vzniknout objednávka)
  prohra   → uzavírá případ a vynucuje důvod prohry
"""

from sqlalchemy.orm import Session

from app.crm.models import CrmStav

# Barvy držíme jako tokeny appky (viz global.css), ne hex – aby stavy
# respektovaly světlý/tmavý režim a režim pro barvoslepé.
VYCHOZI_STAVY: dict[str, list[dict]] = {
    "op": [
        {"klic": "novy", "nazev": "Nový", "druh": "otevreny", "barva": "info"},
        {"klic": "kvalifikace", "nazev": "Kvalifikace", "druh": "otevreny", "barva": "info"},
        {"klic": "podklady", "nazev": "Sběr podkladů", "druh": "otevreny", "barva": "warn"},
        {"klic": "nabidka", "nazev": "Nabídka odeslána", "druh": "otevreny", "barva": "warn"},
        {"klic": "vyjednavani", "nazev": "Vyjednávání", "druh": "otevreny", "barva": "warn"},
        {"klic": "vyhrano", "nazev": "Vyhráno", "druh": "vyhra", "barva": "ok"},
        {"klic": "prohrano", "nazev": "Prohráno", "druh": "prohra", "barva": "crit"},
    ],
    "nab": [
        {"klic": "koncept", "nazev": "Koncept", "druh": "otevreny", "barva": "info"},
        {"klic": "ke_kontrole", "nazev": "Ke kontrole", "druh": "otevreny", "barva": "info"},
        {"klic": "odeslana", "nazev": "Odeslána", "druh": "otevreny", "barva": "warn"},
        {"klic": "prijata", "nazev": "Přijata", "druh": "vyhra", "barva": "ok"},
        {"klic": "zamitnuta", "nazev": "Zamítnuta", "druh": "prohra", "barva": "crit"},
    ],
    "obj": [
        {"klic": "pripravena", "nazev": "Připravená", "druh": "otevreny", "barva": "info"},
        {"klic": "odeslana", "nazev": "Odeslána zákazníkovi", "druh": "otevreny", "barva": "warn"},
        {"klic": "podepsana", "nazev": "Podepsaná", "druh": "vyhra", "barva": "ok"},
        {"klic": "zrusena", "nazev": "Zrušená", "druh": "prohra", "barva": "crit"},
    ],
    "pro": [
        {"klic": "priprava", "nazev": "Příprava", "druh": "otevreny", "barva": "info"},
        {"klic": "realizace", "nazev": "Realizace", "druh": "otevreny", "barva": "warn"},
        {"klic": "predani", "nazev": "Předání", "druh": "otevreny", "barva": "warn"},
        {"klic": "dokonceno", "nazev": "Dokončeno", "druh": "vyhra", "barva": "ok"},
        {"klic": "zastaveno", "nazev": "Zastaveno", "druh": "prohra", "barva": "crit"},
    ],
}


def seed_stavy(db: Session) -> None:
    """Naplní chybějící stavy (idempotentní – existující se nepřepisují).

    Doplňuje po entitách: když vedení smaže sloupec kanbanu, seed ho nevrátí
    (jinak by se mazání nedalo provést). Doplní se jen entita, která nemá
    ŽÁDNÝ stav – typicky po nasazení nebo po přidání nové entity.
    """
    for entita, sada in VYCHOZI_STAVY.items():
        existuje = db.query(CrmStav.id).filter(CrmStav.entita == entita).first()
        if existuje is not None:
            continue
        for poradi, s in enumerate(sada):
            db.add(
                CrmStav(
                    entita=entita,
                    klic=s["klic"],
                    nazev=s["nazev"],
                    poradi=poradi,
                    barva=s.get("barva", ""),
                    druh=s["druh"],
                )
            )
    db.commit()


def seznam(db: Session, entita: str) -> list[CrmStav]:
    """Stavy entity v pořadí kanbanu."""
    return (
        db.query(CrmStav)
        .filter(CrmStav.entita == entita)
        .order_by(CrmStav.poradi, CrmStav.id)
        .all()
    )


def vychozi_klic(db: Session, entita: str) -> str:
    """Klíč prvního stavu (do něj padá nově založený záznam).

    Fallback na klíč z kódové sady, kdyby tabulka byla prázdná – nový záznam
    se nikdy nesmí založit bez stavu, protože by v kanbanu zmizel.
    """
    prvni = seznam(db, entita)
    if prvni:
        return prvni[0].klic
    sada = VYCHOZI_STAVY.get(entita) or []
    return sada[0]["klic"] if sada else "novy"


def najdi(db: Session, entita: str, klic: str) -> CrmStav | None:
    return (
        db.query(CrmStav)
        .filter(CrmStav.entita == entita, CrmStav.klic == klic)
        .first()
    )


def je_druhu(db: Session, entita: str, klic: str, druh: str) -> bool:
    """Je daný stav zadaného druhu (výhra/prohra/otevřený)?"""
    s = najdi(db, entita, klic)
    return s is not None and s.druh == druh
