"""Vlastní (admin definovaná) pole na obrazovkách CRM.

Řeší situaci „od teď chceme u obchodního případu sledovat ještě tenhle údaj":
admin pole přidá v UI, aniž by se měnilo schéma nebo nasazoval kód. Definice
polí drží `CrmVlastniPole`, hodnoty JSONB sloupec `extra` daného záznamu –
stejný princip, jaký už appka používá pro vlastní sloupce katalogu technologií.

Co tenhle modul zajišťuje:
  * strojový `klic` z názvu (bez diakritiky, unikátní v rámci entity, neměnný),
  * očištění a typovou kontrolu hodnot při ukládání (neznámé klíče se zahodí),
  * čitelný výpis hodnoty pro seznamy a detail.

Proč se neznámé klíče zahazují místo chyby: pole mohl někdo mezitím smazat
a formulář odeslaný ze starší otevřené stránky by pak nešel uložit vůbec.
"""

import re
import unicodedata
from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crm.models import (
    ENTITY_VLASTNICH_POLI,
    TYPY_VLASTNIHO_POLE,
    CrmVlastniPole,
    ObchodniPripad,
    OdberneMisto,
    Zakaznik,
)

# Entita → model, na kterém žije `extra`. Přidání další obrazovky = jeden řádek
# (a klíč v ENTITY_VLASTNICH_POLI).
MODELY = {"zakaznik": Zakaznik, "op": ObchodniPripad, "om": OdberneMisto}

# Lidské názvy typů pro chybová hlášení.
NAZVY_TYPU = {
    "text": "text",
    "dlouhy_text": "delší text",
    "cislo": "číslo",
    "datum": "datum",
    "ano_ne": "ano/ne",
    "vyber": "výběr ze seznamu",
}


def over_entitu(entita: str) -> str:
    if entita not in ENTITY_VLASTNICH_POLI:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Na entitu '{entita}' vlastní pole přidávat nelze. "
                f"Podporované: {', '.join(ENTITY_VLASTNICH_POLI)}."
            ),
        )
    return entita


def over_typ(typ: str) -> str:
    if typ not in TYPY_VLASTNIHO_POLE:
        raise HTTPException(status_code=422, detail=f"Neznámý typ pole: {typ}")
    return typ


def uniq_klic(db: Session, entita: str, nazev: str) -> str:
    """Strojový klíč z názvu, unikátní v rámci entity.

    „Číslo smlouvy ČEZ" → `cislo_smlouvy_cez`. Při kolizi se přidá číslovka,
    ať dvě stejně pojmenovaná pole nepřepíšou jedno druhému hodnoty.
    """
    zaklad = unicodedata.normalize("NFKD", nazev).encode("ascii", "ignore").decode()
    zaklad = re.sub(r"[^a-zA-Z0-9]+", "_", zaklad).strip("_").lower() or "pole"
    klic = zaklad
    i = 2
    while (
        db.query(CrmVlastniPole.id)
        .filter(CrmVlastniPole.entita == entita, CrmVlastniPole.klic == klic)
        .first()
    ):
        klic = f"{zaklad}_{i}"
        i += 1
    return klic


def seznam(db: Session, entita: str) -> list[CrmVlastniPole]:
    """Pole entity v pořadí, v jakém se mají zobrazit."""
    return (
        db.query(CrmVlastniPole)
        .filter(CrmVlastniPole.entita == entita)
        .order_by(CrmVlastniPole.poradi, CrmVlastniPole.id)
        .all()
    )


def _hodnota_cislo(pole: CrmVlastniPole, hodnota) -> float:
    try:
        return float(str(hodnota).replace(" ", "").replace(",", "."))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422,
            detail=f"Pole „{pole.nazev}“ je číselné, ale „{hodnota}“ není číslo.",
        )


def _hodnota_datum(pole: CrmVlastniPole, hodnota) -> str:
    try:
        return date.fromisoformat(str(hodnota)[:10]).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Pole „{pole.nazev}“ je datum – čekám formát YYYY-MM-DD.",
        )


def _hodnota_ano_ne(hodnota) -> bool:
    if isinstance(hodnota, bool):
        return hodnota
    return str(hodnota).strip().lower() in ("1", "true", "ano", "on", "yes")


def _hodnota_vyber(pole: CrmVlastniPole, hodnota) -> str:
    text = str(hodnota).strip()
    volby = list(pole.volby or [])
    if volby and text not in volby:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Pole „{pole.nazev}“ má na výběr jen: {', '.join(volby)}. "
                f"„{text}“ mezi nimi není."
            ),
        )
    return text


def zpracuj(db: Session, entita: str, vstup: dict | None) -> dict:
    """Očistí hodnoty vlastních polí před uložením do `extra`.

    - neznámé klíče (smazané pole, cizí data) se zahodí,
    - prázdná hodnota se neukládá vůbec (klíč z JSONB vypadne),
    - typ se zkontroluje a hodnota převede do kanonické podoby,
    - u povinného pole se prázdná hodnota odmítne.
    """
    definice = {p.klic: p for p in seznam(db, entita)}
    vstup = vstup or {}
    out: dict = {}

    for klic, hodnota in vstup.items():
        pole = definice.get(klic)
        if pole is None:
            continue
        je_prazdna = hodnota is None or (isinstance(hodnota, str) and hodnota.strip() == "")
        if je_prazdna:
            continue
        if pole.typ == "cislo":
            out[klic] = _hodnota_cislo(pole, hodnota)
        elif pole.typ == "datum":
            out[klic] = _hodnota_datum(pole, hodnota)
        elif pole.typ == "ano_ne":
            out[klic] = _hodnota_ano_ne(hodnota)
        elif pole.typ == "vyber":
            out[klic] = _hodnota_vyber(pole, hodnota)
        else:  # text, dlouhy_text
            out[klic] = str(hodnota).strip()

    # Povinná pole až nakonec – ať hláška padne na to, co uživatel opravdu
    # nevyplnil, a ne na typovou chybu jiného pole.
    chybi = [
        p.nazev
        for p in definice.values()
        # U ano/ne je „ne" plnohodnotná odpověď, takže povinnost nekontrolujeme
        # (jinak by povinné ano/ne znamenalo „musíš zaškrtnout").
        if p.povinne and p.typ != "ano_ne" and klic_chybi(out, p.klic)
    ]
    if chybi:
        raise HTTPException(
            status_code=422,
            detail=f"Vyplň povinná pole: {', '.join(chybi)}.",
        )
    return out


def klic_chybi(hodnoty: dict, klic: str) -> bool:
    hodnota = hodnoty.get(klic)
    return hodnota is None or (isinstance(hodnota, str) and hodnota.strip() == "")


def text_hodnoty(pole: CrmVlastniPole, hodnota) -> str:
    """Hodnota k zobrazení (seznam, detail, tisk). Prázdná → pomlčka."""
    if hodnota is None or (isinstance(hodnota, str) and hodnota.strip() == ""):
        return "—"
    if pole.typ == "ano_ne":
        return "Ano" if _hodnota_ano_ne(hodnota) else "Ne"
    if pole.typ == "datum":
        try:
            d = date.fromisoformat(str(hodnota)[:10])
            return f"{d.day}.{d.month}.{d.year}"
        except ValueError:
            return str(hodnota)
    if pole.typ == "cislo":
        try:
            cislo = float(hodnota)
        except (TypeError, ValueError):
            return str(hodnota)
        # Celá čísla bez desetinné části (1500 místo 1500.0).
        if cislo == int(cislo):
            return f"{int(cislo):,}".replace(",", " ")
        return f"{cislo:,.2f}".replace(",", " ").replace(".", ",")
    return str(hodnota)


def pro_frontend(db: Session, entita: str) -> list[dict]:
    """Definice polí pro UI (formulář, sloupce seznamu)."""
    return [
        {
            "id": p.id,
            "entita": p.entita,
            "klic": p.klic,
            "nazev": p.nazev,
            "typ": p.typ,
            "volby": list(p.volby or []),
            "napoveda": p.napoveda or "",
            "povinne": bool(p.povinne),
            "v_seznamu": bool(p.v_seznamu),
            "poradi": p.poradi,
        }
        for p in seznam(db, entita)
    ]


def hodnoty_pro_seznam(db: Session, entita: str, zaznamy: list) -> dict[int, dict]:
    """Hodnoty polí označených `v_seznamu` pro řádky tabulky – {id: {klic: text}}.

    Definice se čtou jednou pro celý seznam, ne pro každý řádek zvlášť.
    """
    pole_v_seznamu = [p for p in seznam(db, entita) if p.v_seznamu]
    if not pole_v_seznamu:
        return {}
    out: dict[int, dict] = {}
    for z in zaznamy:
        extra = z.extra or {}
        out[z.id] = {p.klic: text_hodnoty(p, extra.get(p.klic)) for p in pole_v_seznamu}
    return out
