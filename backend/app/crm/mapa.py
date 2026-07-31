"""Body na mapu zákazníků a projektů (CRM-20).

GPS už v datech je (z ARESu i z Raynetu), jen se nikde nekreslila. U FVE se
hodí na plánování obchůzek („co máme v okolí, když už tam jedeme") a na
posouzení lokality.

---- Které souřadnice se berou -------------------------------------------

Přednost má **odběrné místo**, ne adresa firmy: FVE se staví na provozovně,
zatímco adresa v obchodním rejstříku bývá fakturační a klidně na druhém konci
republiky (viz CRM-46). Teprve když provozovna GPS nemá, použije se firma.

Bod nese i to, co u něj v okolí je — otevřené případy a běžící projekty —
protože právě kvůli tomu se člověk na mapu dívá.
"""

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmProjekt, CrmStav, ObchodniPripad, OdberneMisto, Zakaznik
from app.crm.pristup import omez_na_moje


def _cislo(x):
    return float(x) if x is not None else None


def body(db: Session, user: User) -> list[dict]:
    """Zákazníci se souřadnicemi + souhrn toho, co u nich běží."""
    zakaznici = omez_na_moje(db.query(Zakaznik), Zakaznik, user).all()
    if not zakaznici:
        return []
    ids = [z.id for z in zakaznici]

    # Provozovny: jedna firma jich může mít víc, bereme první se souřadnicemi.
    mista: dict[int, OdberneMisto] = {}
    for m in (
        db.query(OdberneMisto)
        .filter(
            OdberneMisto.zakaznik_id.in_(ids),
            OdberneMisto.gps_lat.isnot(None),
            OdberneMisto.gps_lng.isnot(None),
        )
        .order_by(OdberneMisto.id)
        .all()
    ):
        mista.setdefault(m.zakaznik_id, m)

    # Otevřené případy a projekty na zákazníka – dvě agregace, ne dotaz v cyklu.
    otevrene_stavy = {
        s.klic for s in db.query(CrmStav).filter(CrmStav.entita == "op", CrmStav.druh == "otevreny")
    }
    pripadu: dict[int, int] = {}
    pripad_zakaznik: dict[int, int] = {}
    for p in db.query(ObchodniPripad).filter(ObchodniPripad.zakaznik_id.in_(ids)).all():
        pripad_zakaznik[p.id] = p.zakaznik_id
        if p.stav in otevrene_stavy:
            pripadu[p.zakaznik_id] = pripadu.get(p.zakaznik_id, 0) + 1

    projektu: dict[int, int] = {}
    for pr in db.query(CrmProjekt).all():
        zak = pripad_zakaznik.get(pr.obchodni_pripad_id)
        if zak is not None:
            projektu[zak] = projektu.get(zak, 0) + 1

    out = []
    for z in zakaznici:
        misto = mista.get(z.id)
        lat = _cislo(misto.gps_lat) if misto else _cislo(z.gps_lat)
        lng = _cislo(misto.gps_lng) if misto else _cislo(z.gps_lng)
        if lat is None or lng is None:
            continue  # bez souřadnic není co kreslit
        out.append(
            {
                "zakaznik_id": z.id,
                "nazev": z.nazev,
                "typ": z.typ,
                "lat": lat,
                "lng": lng,
                # Odkud souřadnice jsou – v UI se to hodí vědět, protože
                # fakturační adresa firmy může být jinde než stavba.
                "zdroj": "provozovna" if misto else "adresa firmy",
                "misto_nazev": misto.nazev if misto else "",
                "mesto": (misto.adresa_mesto if misto else z.adresa_mesto) or "",
                "otevrenych_pripadu": pripadu.get(z.id, 0),
                "projektu": projektu.get(z.id, 0),
            }
        )
    return out
