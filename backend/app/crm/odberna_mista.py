"""Odběrná místa zákazníka – validace, přístup a předání parametrů do výpočtu.

Odběrné místo je most mezi CRM a nabídkovačem. Drží čtyři věci, které OZ dosud
vypisoval ručně do každého peak shaving výpočtu (distributor, napěťová hladina,
rezervovaná kapacita, rezervovaný příkon) a polohu provozovny pro výpočet výroby
FVE. K místu se pak nahrávají 15minutové diagramy odběru (`CrmDiagram`).

PRÁVA se dědí ze zákazníka, ne z místa: místo nemá vlastníka, protože kdo vidí
firmu, má vidět i její provozovny. Proto každá funkce, která místo dohledává,
kontroluje přístup k jeho zákazníkovi (`vyzaduj_zaznam`).

JEDNO POLE, DVĚ OBRAZOVKY. Stejný seznam se ukazuje na kartě klienta i na kartě
obchodního případu – u případu jako místa jeho zákazníka, s vyznačením toho,
kterého se případ týká (`ObchodniPripad.odberne_misto_id`). Proto se přístup
řeší jednou funkcí `zaznam_a_zakaznik` pro obě entity: kdyby měla každá
obrazovka vlastní cestu, dřív nebo později se jedna z nich zapomene ohlídat.
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import ObchodniPripad, OdberneMisto, Zakaznik
from app.crm.pristup import vyzaduj_zaznam

# Obrazovky, ze kterých se odběrná místa spravují.
ENTITY_MIST = ("zakaznik", "op")

# Délka EAN odběrného místa v ČR (18 číslic, prefix 859). Prefix se schválně
# NEVALIDUJE – appka nemá důvod odmítnout zahraniční odběr, a kdyby OZ zadal
# EAN dodávky (859...) místo odběru, appka to nepozná ani z prefixu.
EAN_DELKA = 18


def normalizuj_ean(ean: str | None) -> str:
    """Odstraní mezery a spojovníky (z portálů se EAN kopíruje po skupinách).

    Prázdný EAN je v pořádku – u leadu, kde se teprve zjišťuje, kde vlastně
    odebírá, by povinný EAN znamenal, že místo nejde založit vůbec.
    """
    cisty = (ean or "").replace(" ", "").replace("-", "").strip()
    if not cisty:
        return ""
    if not cisty.isdigit() or len(cisty) != EAN_DELKA:
        raise HTTPException(
            status_code=422,
            detail=f"EAN odběrného místa musí mít {EAN_DELKA} číslic (zadáno: {len(cisty)}).",
        )
    return cisty


def over_duplicitni_ean(db: Session, zakaznik_id: int, ean: str, krome_id: int | None = None):
    """Dvě místa téhož zákazníka nesmí mít stejný EAN.

    Kontroluje se jen v rámci zákazníka, ne globálně: tentýž EAN se legitimně
    objeví u dvou firem, když se provozovna prodá nebo když ji appka vede pod
    leadem i pod klientem, ze kterého se lead stal. Globální zákaz by v takové
    situaci zablokoval založení místa bez možnosti to obejít.
    """
    if not ean:
        return
    q = db.query(OdberneMisto).filter(
        OdberneMisto.zakaznik_id == zakaznik_id, OdberneMisto.ean == ean
    )
    if krome_id is not None:
        q = q.filter(OdberneMisto.id != krome_id)
    if q.first() is not None:
        raise HTTPException(
            status_code=422, detail=f"Odběrné místo s EAN {ean} už u tohoto zákazníka je."
        )


def over_distribuci(distributor: str, napetova_hladina: str) -> tuple[str, str]:
    """Zkontroluje distributora a hladinu proti seznamům nabídkovače.

    Prázdné hodnoty projdou – místo se zakládá i ve chvíli, kdy OZ ještě nemá
    fakturu a neví, kdo místo distribuuje. Vyplněná hodnota ale musí být ta,
    se kterou umí počítat peak shaving; jinak by se chyba objevila až u výpočtu.
    """
    from app.nabidkovac.models import DISTRIBUTORI, NAPETOVE_HLADINY

    d = (distributor or "").strip().lower()
    h = (napetova_hladina or "").strip().lower()
    if d and d not in DISTRIBUTORI:
        raise HTTPException(
            status_code=422, detail=f"Neznámý distributor: {distributor}. Známe {', '.join(DISTRIBUTORI)}."
        )
    if h and h not in NAPETOVE_HLADINY:
        raise HTTPException(
            status_code=422,
            detail=f"Neznámá napěťová hladina: {napetova_hladina}. Známe {', '.join(NAPETOVE_HLADINY)}.",
        )
    return d, h


def zaznam_a_zakaznik(
    db: Session, entita: str, zaznam_id: int, user: User
) -> tuple[Zakaznik, ObchodniPripad | None]:
    """Vrátí (zákazník, případ-nebo-None) pro obrazovku, ze které se místa čtou.

    Vždy jde přes `vyzaduj_zaznam`, takže cizí záznam skončí 404 a přes odběrná
    místa nejde obejít viditelnost záznamů.
    """
    if entita == "zakaznik":
        z = vyzaduj_zaznam(db.get(Zakaznik, zaznam_id), user, "Zákazník")
        return z, None
    if entita == "op":
        p = vyzaduj_zaznam(db.get(ObchodniPripad, zaznam_id), user, "Obchodní případ")
        # Zákazníka případu bereme bez další kontroly práv: kdo vidí případ,
        # musí vidět i firmu, které patří – jinak by karta případu nešla složit.
        return db.get(Zakaznik, p.zakaznik_id), p
    raise HTTPException(
        status_code=422,
        detail="Odběrná místa se vedou u zákazníka nebo u obchodního případu.",
    )


def vyzaduj_misto(db: Session, misto_id: int, user: User) -> OdberneMisto:
    """Dohledá místo a ověří přístup přes jeho zákazníka."""
    m = db.get(OdberneMisto, misto_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Odběrné místo neexistuje")
    vyzaduj_zaznam(db.get(Zakaznik, m.zakaznik_id), user, "Zákazník")
    return m


def seznam(db: Session, zakaznik_id: int) -> list[OdberneMisto]:
    """Místa zákazníka – aktivní první, pak podle názvu.

    Neaktivní se nezahazují, jen padají na konec: nabídky, které z místa už
    počítaly, na něj pořád odkazují a musí zůstat dohledatelné.
    """
    return (
        db.query(OdberneMisto)
        .filter(OdberneMisto.zakaznik_id == zakaznik_id)
        .order_by(OdberneMisto.aktivni.desc(), OdberneMisto.nazev)
        .all()
    )


def pocet_diagramu(db: Session, misto_id: int) -> int:
    """Kolik diagramů na místě visí (etapa 2 – tabulka může chybět)."""
    try:
        from app.crm.models import CrmDiagram
    except ImportError:  # pragma: no cover – dokud diagramy nejsou nasazené
        return 0
    return db.query(CrmDiagram).filter(CrmDiagram.odberne_misto_id == misto_id).count()


def parametry_pro_vypocet(m: OdberneMisto) -> dict:
    """Co z místa umí nabídkovač předvyplnit.

    Vrací jen vyplněné hodnoty. Nula ani prázdný řetězec se neposílají, aby
    předvyplnění nepřepsalo to, co OZ v panelu zadal ručně, hodnotou „nevíme".
    """
    out: dict = {}
    if m.distributor:
        out["distributor"] = m.distributor
    if m.napetova_hladina:
        out["napetova_hladina"] = m.napetova_hladina
    if m.rezervovana_kapacita_kw is not None:
        out["rezervovana_kapacita_kw"] = float(m.rezervovana_kapacita_kw)
    if m.rezervovany_prikon_kw is not None:
        out["rezervovany_prikon_kw"] = float(m.rezervovany_prikon_kw)
    if m.gps_lat is not None and m.gps_lng is not None:
        out["gps_lat"] = float(m.gps_lat)
        out["gps_lng"] = float(m.gps_lng)
    return out


def adresa_textem(m: OdberneMisto) -> str:
    """Adresa místa na jeden řádek (pro seznamy a nabídku)."""
    casti = [m.adresa_ulice, " ".join(x for x in (m.adresa_psc, m.adresa_mesto) if x)]
    return ", ".join(c.strip() for c in casti if c and c.strip())
