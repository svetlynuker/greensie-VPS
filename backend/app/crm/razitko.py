"""Podpis stavu jednoho záznamu CRM — z něj prohlížeč pozná, že se něco změnilo.

Stejný princip jako u matice (`app/matice/razitko.py`): počítat na serveru „co
přesně se změnilo od času X“ by znamenalo držet historii a testovat ji, a při
první nepřesnosti by lidem tiše chyběla aktualizace. Podpis je tupý, ale
nemůže lhát — když se liší, klient si detail natáhne znovu.

Kromě času poslední změny jsou v podpisu i počty pod-záznamů (kontakty,
odběrná místa, aktivity, nabídky…). Přidání ani smazání pod-záznamu totiž čas
změny nadřazeného záznamu neposune, takže samotný čas by na ně byl slepý.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crm.models import (
    CrmAktivita,
    CrmProjekt,
    ObchodniPripad,
    Objednavka,
    ObjednavkaPolozka,
    OdberneMisto,
    ProjektKrok,
    Zakaznik,
    ZakaznikKontakt,
)


def _cast(db: Session, model, **filtr) -> str:
    return str(db.query(func.count(model.id)).filter_by(**filtr).scalar() or 0)


def _zaklad(zaznam) -> list[str]:
    zmeneno = getattr(zaznam, "zmeneno_at", None)
    return [
        zmeneno.isoformat() if zmeneno else "-",
        str(getattr(zaznam, "verze", 0) or 0),
    ]


def _model_seznamu(entita: str):
    if entita == "zakaznik":
        return Zakaznik
    if entita == "op":
        return ObchodniPripad
    if entita == "obj":
        return Objednavka
    if entita == "pro":
        return CrmProjekt
    if entita == "nab":
        from app.nabidkovac.models import Nabidka

        return Nabidka
    return None


def razitko_seznamu(db: Session, entita: str) -> str:
    """Podpis stavu celého seznamu — pro kanbany a tabulky.

    Kanban se dosud po cizím přetažení karty neaktualizoval vůbec: data se
    načítala jen na akci uživatele. Tohle mu dá stejný signál, jaký má detail.

    Aby to fungovalo, musí přesun karty posunout `zmeneno_at` — proto endpointy
    měnící stav volají `oznac_zmenu` (viz `crm/routes.py`).
    """
    model = _model_seznamu(entita)
    if model is None:
        return ""
    posledni = db.query(func.max(model.zmeneno_at)).scalar()
    return "|".join(
        [
            posledni.isoformat() if posledni else "-",
            str(db.query(func.count(model.id)).scalar() or 0),
            # Nejvyšší id zachytí vznik záznamu i v případě, že by se hned nato
            # jiný smazal a počet zůstal stejný.
            str(db.query(func.max(model.id)).scalar() or 0),
        ]
    )


def razitko_zaznamu(db: Session, entita: str, zaznam_id: int) -> str:
    """Podpis stavu záznamu. Neexistující záznam → prázdný text."""
    if not zaznam_id:
        return ""

    if entita == "zakaznik":
        z = db.get(Zakaznik, zaznam_id)
        if z is None:
            return ""
        return "|".join(
            [
                *_zaklad(z),
                _cast(db, ZakaznikKontakt, zakaznik_id=z.id),
                _cast(db, OdberneMisto, zakaznik_id=z.id),
                _cast(db, ObchodniPripad, zakaznik_id=z.id),
                # Aktivity na kartě zákazníka (poznámky, schůzky).
                _cast(db, CrmAktivita, entita="zakaznik", zaznam_id=z.id),
            ]
        )

    if entita == "op":
        p = db.get(ObchodniPripad, zaznam_id)
        if p is None:
            return ""
        return "|".join(
            [
                *_zaklad(p),
                _cast(db, CrmAktivita, entita="op", zaznam_id=p.id),
                _cast(db, Objednavka, obchodni_pripad_id=p.id),
            ]
        )

    if entita == "obj":
        o = db.get(Objednavka, zaznam_id)
        if o is None:
            return ""
        return "|".join(
            [
                *_zaklad(o),
                _cast(db, ObjednavkaPolozka, objednavka_id=o.id),
                _cast(db, CrmAktivita, entita="obj", zaznam_id=o.id),
            ]
        )

    if entita == "pro":
        p = db.get(CrmProjekt, zaznam_id)
        if p is None:
            return ""
        # Kroky projektu mění víc lidí a mají vlastní PATCH — proto do podpisu
        # patří i čas jejich poslední změny, ne jen počet.
        posledni_krok = (
            db.query(func.max(ProjektKrok.zmeneno_at)).filter_by(projekt_id=p.id).scalar()
        )
        return "|".join(
            [
                *_zaklad(p),
                _cast(db, ProjektKrok, projekt_id=p.id),
                posledni_krok.isoformat() if posledni_krok else "-",
                _cast(db, CrmAktivita, entita="pro", zaznam_id=p.id),
            ]
        )

    if entita == "nab":
        from app.nabidkovac.models import Nabidka

        n = db.get(Nabidka, zaznam_id)
        return "|".join(_zaklad(n)) if n else ""

    if entita == "kontakt":
        k = db.get(ZakaznikKontakt, zaznam_id)
        return "|".join(_zaklad(k)) if k else ""

    if entita == "om":
        m = db.get(OdberneMisto, zaznam_id)
        return "|".join(_zaklad(m)) if m else ""

    return ""
