"""Šablony e-mailů a poznámek (CRM-32).

Doplňování zástupných symbolů do textu. Symbol je `{{klic}}`; co se nenajde,
**zůstane v textu tak, jak je** — a to je vědomé rozhodnutí: tichým smazáním by
zákazníkovi odešla věta s dírou uprostřed („Dobrý den, ohledně nabídky pro ,"),
zatímco viditelné `{{zakaznik}}` je vidět na první pohled a jde opravit.

Hodnoty se skládají z toho, co je po ruce u záznamu, ze kterého se píše. Když
je něco prázdné (případ bez zákazníka), symbol se taky nechá — prázdné místo
vypadá jako chyba appky, `{{zakaznik}}` jako chybějící údaj.
"""

import re

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmSablona, ObchodniPripad, Objednavka, Zakaznik

VZOR = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")

DRUHY = ("email", "poznamka")

# Co umí šablona doplnit. Text je pro nápovědu v UI — ať člověk nemusí hádat,
# jak se symbol jmenuje.
SYMBOLY = [
    ("zakaznik", "Název firmy"),
    ("kontakt", "Jméno kontaktní osoby (je-li u záznamu)"),
    ("cislo", "Číslo záznamu (OP-26-0301, NAB-26-0007…)"),
    ("nazev", "Název případu / nabídky"),
    ("moje_jmeno", "Tvoje jméno"),
    ("muj_email", "Tvůj e-mail"),
]


def hodnoty(db: Session, entita: str, zaznam_id: int | None, user: User) -> dict:
    """Hodnoty symbolů pro konkrétní záznam. Chybějící se prostě nevyplní."""
    out = {
        "moje_jmeno": user.jmeno or "",
        "muj_email": user.email or "",
    }
    if not entita or zaznam_id is None:
        return {k: v for k, v in out.items() if v}

    if entita == "zakaznik":
        z = db.get(Zakaznik, zaznam_id)
        if z is not None:
            out["zakaznik"] = z.nazev or ""
    elif entita == "op":
        p = db.get(ObchodniPripad, zaznam_id)
        if p is not None:
            out["cislo"] = p.cislo or ""
            out["nazev"] = p.nazev or ""
            if p.zakaznik is not None:
                out["zakaznik"] = p.zakaznik.nazev or ""
    elif entita == "nab":
        from app.nabidkovac.models import Nabidka

        n = db.get(Nabidka, zaznam_id)
        if n is not None:
            out["cislo"] = n.cislo or ""
            out["zakaznik"] = n.zakaznik_nazev or ""
            if n.obchodni_pripad_id:
                p = db.get(ObchodniPripad, n.obchodni_pripad_id)
                if p is not None:
                    out["nazev"] = p.nazev or ""
                    if p.zakaznik is not None:
                        out["zakaznik"] = p.zakaznik.nazev or out["zakaznik"]
    elif entita == "obj":
        o = db.get(Objednavka, zaznam_id)
        if o is not None:
            out["cislo"] = o.cislo or ""
            out["nazev"] = o.nazev or ""
            if o.pripad is not None and o.pripad.zakaznik is not None:
                out["zakaznik"] = o.pripad.zakaznik.nazev or ""

    return {k: v for k, v in out.items() if v}


def doplnil(text: str, hodnoty_symbolu: dict) -> str:
    """Nahradí `{{klic}}` hodnotou; neznámý nebo prázdný symbol nechá být."""

    def nahrad(m: re.Match) -> str:
        hodnota = hodnoty_symbolu.get(m.group(1))
        return hodnota if hodnota else m.group(0)

    return VZOR.sub(nahrad, text or "")


def seznam(db: Session, druh: str | None = None, entita: str | None = None) -> list[CrmSablona]:
    """Šablony k nabídnutí. Prázdná `entita` u šablony = platí všude."""
    q = db.query(CrmSablona).filter(CrmSablona.aktivni.is_(True))
    if druh:
        q = q.filter(CrmSablona.druh == druh)
    if entita:
        q = q.filter(CrmSablona.entita.in_(["", entita]))
    return q.order_by(CrmSablona.poradi, CrmSablona.id).all()
