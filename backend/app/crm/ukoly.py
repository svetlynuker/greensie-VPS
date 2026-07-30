"""Moje úkoly napříč celým CRM.

Aktivita s termínem, která není hotová, je úkol (viz `CrmAktivita`). Úkoly ale
leží u zákazníků, případů, nabídek, objednávek i projektů — takže bez tohohle
soupisu je člověk vidí jen tak, že proklikává jednotlivé záznamy. Tenhle modul
je jedno místo, kde se soupis skládá, aby ho endpoint `/crm/ukoly` i souhrn na
Rozcestníku počítaly stejně.

Dvě věci, které se snadno rozbijí:

1. `dni` je KLADNÉ, když je úkol po termínu (dnes − termín). Stejnou konvenci
   používá souhrn z matice (`dashboard.UkolRadek.dni`) a frontend na ni má
   hotový popisovač `popisDnu()`. Neotáčet.
2. Právo `crm_vse` se tu záměrně neuplatňuje. „Moje úkoly" jsou vždycky jen
   moje — i pro vedení, které jinak vidí všechny záznamy. Kdyby se filtr
   pustil přes `omez_na_moje`, vedení by tu mělo úkoly celé firmy.

Názvy záznamů se dotahují jedním dotazem na entitu (ne v cyklu), protože
úkolů může být napříč firmou hodně a N+1 by se tu projevilo hned.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmAktivita, CrmProjekt, ObchodniPripad, Objednavka, Zakaznik
from app.crm.schemas import UkolOut
from app.nabidkovac.models import Nabidka

# Entita aktivity → model záznamu, sloupec s lidským názvem a cesta ve frontendu.
# U entit bez obrazovky detailu vede cesta na seznam (lepší než mrtvý odkaz).
#
# Používá to i kalendář (`crm/kalendar.py`) — je to jediná mapa „na co odkazuje
# aktivita", takže nová entita se doplňuje jen tady.
ENTITY = {
    "zakaznik": (Zakaznik, "nazev", "/zakaznici/detail/{id}"),
    "op": (ObchodniPripad, "nazev", "/pripady/detail/{id}"),
    "nab": (Nabidka, "zakaznik_nazev", "/nabidkovac/nabidka/{id}"),
    "obj": (Objednavka, None, "/objednavky"),
    "pro": (CrmProjekt, None, "/projekty/detail/{id}"),
}


def popisy_zaznamu(db: Session, entita: str, ids: set[int]) -> dict[int, str]:
    """id → lidský popis záznamu („Firma s.r.o.", „OP-26-0301 · Střecha")."""
    zaznam = ENTITY.get(entita)
    if zaznam is None or not ids:
        return {}
    model, sloupec_nazvu, _ = zaznam

    ma_cislo = hasattr(model, "cislo")
    out: dict[int, str] = {}
    for row in db.query(model).filter(model.id.in_(ids)).all():
        casti = []
        if ma_cislo and getattr(row, "cislo", None):
            casti.append(str(row.cislo))
        if sloupec_nazvu and getattr(row, sloupec_nazvu, None):
            casti.append(str(getattr(row, sloupec_nazvu)))
        out[row.id] = " · ".join(casti) if casti else f"#{row.id}"
    return out


def cesta_zaznamu(entita: str, zaznam_id: int) -> str:
    zaznam = ENTITY.get(entita)
    if zaznam is None:
        return ""
    return zaznam[2].format(id=zaznam_id)


def moje_ukoly(db: Session, user: User, limit: int | None = None) -> list[UkolOut]:
    """Nehotové úkoly s termínem, které patří přihlášenému uživateli.

    Řazeno podle termínu — nejstarší (nejvíc po termínu) první. `limit` je pro
    souhrn na Rozcestníku, který má být přehled, ne seznam.
    """
    q = (
        db.query(CrmAktivita)
        .filter(
            CrmAktivita.vlastnik_user_id == user.id,
            CrmAktivita.stav == "naplanovano",
            CrmAktivita.termin.isnot(None),
        )
        .order_by(CrmAktivita.termin.asc())
    )
    if limit is not None:
        q = q.limit(limit)
    radky = q.all()
    if not radky:
        return []

    # Jeden dotaz na entitu, ne na řádek. Aktivity bez entity (soukromé
    # události) se přeskočí — nemají u čeho viset.
    podle_entity: dict[str, set[int]] = {}
    for a in radky:
        if a.entita and a.zaznam_id:
            podle_entity.setdefault(a.entita, set()).add(a.zaznam_id)
    popisy = {e: popisy_zaznamu(db, e, ids) for e, ids in podle_entity.items()}

    def popis(a: CrmAktivita) -> str:
        if a.soukroma or not a.entita:
            return "Soukromá událost"
        return popisy.get(a.entita, {}).get(a.zaznam_id, f"#{a.zaznam_id}")

    dnes = date.today()
    return [
        UkolOut(
            id=a.id,
            entita=a.entita,
            zaznam_id=a.zaznam_id,
            druh=a.druh,
            nazev=a.nazev or "",
            text=a.text or "",
            termin=a.termin.isoformat() if a.termin else None,
            zacatek=a.zacatek.isoformat() if a.zacatek else None,
            delka_min=a.delka_min,
            stav=a.stav,
            vysledek=a.vysledek or "",
            soukroma=bool(a.soukroma),
            ucastnici=list(a.ucastnici or []),
            vlastnik_user_id=a.vlastnik_user_id,
            vlastnik_jmeno=(a.vlastnik.jmeno if a.vlastnik else None),
            vytvoril_jmeno=(a.vytvoril.jmeno if a.vytvoril else None),
            vytvoreno_at=(a.vytvoreno_at.isoformat() if a.vytvoreno_at else None),
            zaznam_nazev=popis(a),
            cesta=cesta_zaznamu(a.entita, a.zaznam_id) if a.entita else "",
            dni=(dnes - a.termin).days,
        )
        for a in radky
    ]


def pocty(db: Session, user: User) -> tuple[int, int, int]:
    """(po termínu, dnes, celkem) — čísla do KPI dlaždic na Rozcestníku."""
    zaklad = db.query(CrmAktivita).filter(
        CrmAktivita.vlastnik_user_id == user.id,
        CrmAktivita.stav == "naplanovano",
        CrmAktivita.termin.isnot(None),
    )
    dnes = date.today()
    return (
        zaklad.filter(CrmAktivita.termin < dnes).count(),
        zaklad.filter(CrmAktivita.termin == dnes).count(),
        zaklad.count(),
    )
