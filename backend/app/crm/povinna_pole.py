"""Povinná pole podle stavu pipeline (CRM-30).

Zadání Dana: „jakékoliv editovatelné pole, stávající nebo i budoucí, musí být
možné označit jako povinné" — a nastavuje se to u každého stavu zvlášť.

---- Jak je zajištěné to „i budoucí" --------------------------------------

Seznam polí se nedrží jako výčet v UI, ale skládá se:

  * SYSTÉMOVÁ pole z jedné deklarace níž (`POLE`). Nové pole na případu = jeden
    řádek tady, nikde jinde.
  * VLASTNÍ pole (ta, co si admin přidá) se berou z `crm_vlastni_pole` za běhu,
    takže se v nabídce objeví hned, jak vzniknou — bez zásahu do kódu.

`prazdne()` proto nesmí předpokládat, jak pole vypadá: hodnota může být číslo,
datum, seznam (kategorie) i JSONB (`extra`). Kontrola se dělá podle typu, ne
podle názvu.

---- Proč se hlídá až PŘECHOD, ne uložení --------------------------------

Případ se zakládá rozpracovaný — nutit cenu hned při vzniku by lidi jen otravovalo
a psali by tam nuly. Pravidlo se uplatní teprve, když se případ posouvá dál, což
je moment, kdy už se ta informace vážně čeká.
"""

from sqlalchemy.orm import Session

from app.crm.models import CrmStav, CrmVlastniPole, ObchodniPripad

# Systémová pole případu, která lze označit jako povinná.
# `klic` je co se ukládá do `crm_stavy.povinna_pole`; nové pole = jeden řádek.
POLE: list[dict] = [
    {"klic": "nazev", "nazev": "Název případu", "typ": "text"},
    {"klic": "popis", "nazev": "Popis", "typ": "text"},
    {"klic": "kategorie", "nazev": "Kategorie", "typ": "seznam"},
    {"klic": "hodnota_kc", "nazev": "Hodnota (Kč)", "typ": "cislo"},
    {"klic": "pravdepodobnost", "nazev": "Pravděpodobnost", "typ": "cislo"},
    {"klic": "predpokladane_uzavreni", "nazev": "Předpokládané uzavření", "typ": "datum"},
    {"klic": "raynet_code", "nazev": "Raynetí číslo", "typ": "text"},
    # Vazby — nejsou to políčka, ale „nepustit dál bez…" se u nich čeká stejně.
    {"klic": "_ma_nabidku", "nazev": "Aspoň jedna nabídka", "typ": "vazba"},
    {"klic": "_ma_kontakt", "nazev": "Kontaktní osoba u zákazníka", "typ": "vazba"},
]


def dostupna_pole(db: Session) -> list[dict]:
    """Co všechno lze u stavu označit jako povinné (systémová + vlastní pole)."""
    vlastni = (
        db.query(CrmVlastniPole)
        .filter(CrmVlastniPole.entita == "op")
        .order_by(CrmVlastniPole.poradi, CrmVlastniPole.id)
        .all()
    )
    return POLE + [
        {"klic": f"extra:{p.klic}", "nazev": p.nazev, "typ": p.typ, "vlastni": True}
        for p in vlastni
    ]


def _prazdne(hodnota) -> bool:
    """Je hodnota prázdná? Musí zvládnout text, číslo, datum i seznam.

    Pozor na nulu a nulovou pravděpodobnost: `0` je vyplněná hodnota, ne prázdno.
    Naivní `if not hodnota` by u ceny 0 Kč tvrdil, že chybí.
    """
    if hodnota is None:
        return True
    if isinstance(hodnota, str):
        return not hodnota.strip()
    if isinstance(hodnota, (list, tuple, set, dict)):
        return len(hodnota) == 0
    return False


def chybejici(db: Session, pripad: ObchodniPripad, novy_stav: str) -> list[str]:
    """Lidské názvy polí, která pro přechod do `novy_stav` chybí.

    Prázdný seznam = přechod je v pořádku. Vrací NÁZVY, ne klíče — jde to přímo
    do chybové zprávy pro uživatele.
    """
    stav = (
        db.query(CrmStav)
        .filter(CrmStav.entita == "op", CrmStav.klic == novy_stav)
        .first()
    )
    pozadovane = list((stav.povinna_pole if stav is not None else None) or [])
    if not pozadovane:
        return []

    popisky = {p["klic"]: p["nazev"] for p in dostupna_pole(db)}
    chybi: list[str] = []
    for klic in pozadovane:
        if klic == "_ma_nabidku":
            from app.nabidkovac.models import Nabidka

            ma = (
                db.query(Nabidka.id)
                .filter(Nabidka.obchodni_pripad_id == pripad.id)
                .first()
                is not None
            )
            if not ma:
                chybi.append(popisky.get(klic, klic))
            continue
        if klic == "_ma_kontakt":
            from app.crm.models import ZakaznikKontakt

            ma = (
                db.query(ZakaznikKontakt.id)
                .filter(ZakaznikKontakt.zakaznik_id == pripad.zakaznik_id)
                .first()
                is not None
            )
            if not ma:
                chybi.append(popisky.get(klic, klic))
            continue
        if klic.startswith("extra:"):
            hodnota = (pripad.extra or {}).get(klic[6:])
        else:
            hodnota = getattr(pripad, klic, None)
        if _prazdne(hodnota):
            chybi.append(popisky.get(klic, klic))
    return chybi
