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
    ("stav", "Název stavu, ve kterém záznam je"),
    ("vlastnik", "Jméno vlastníka záznamu"),
    ("hodnota", "Hodnota případu / cena objednávky"),
    ("odkaz", "Odkaz na záznam v appce"),
    ("moje_jmeno", "Tvoje jméno"),
    ("muj_email", "Tvůj e-mail"),
]

# Kde záznam bydlí ve frontendu. Používá symbol `{{odkaz}}` a automatizace,
# která posílá e-maily na pozadí (tam není odkud cestu vzít).
# Objednávka nemá vlastní stránku detailu, otevírá se ze seznamu.
CESTY = {
    "op": "/pripady/detail/{id}",
    "pro": "/projekty/detail/{id}",
    "nab": "/nabidkovac/nabidka/{id}",
    "obj": "/objednavky",
    "zakaznik": "/zakaznici/detail/{id}",
}


def cesta_zaznamu(entita: str, zaznam_id: int | None) -> str:
    """Cesta na detail záznamu ve frontendu (bez domény)."""
    vzor = CESTY.get(entita or "")
    if not vzor:
        return ""
    return vzor.format(id=zaznam_id) if zaznam_id is not None else ""


def _cislo_lidsky(x) -> str:
    """Peníze pro text e-mailu: „1 250 000 Kč", ne „1250000.00"."""
    if x is None:
        return ""
    try:
        cele = int(round(float(x)))
    except (TypeError, ValueError):
        return ""
    return f"{cele:,}".replace(",", " ") + " Kč"


def _stav_nazev(db: Session, entita: str, klic: str | None) -> str:
    """Lidský název stavu. Do textu pro zákazníka nepatří klíč „vyhrano"."""
    if not klic:
        return ""
    from app.crm import stavy as stavy_modul

    s = stavy_modul.najdi(db, entita, klic)
    return s.nazev if s is not None else str(klic)


def hodnoty(db: Session, entita: str, zaznam_id: int | None, user: User) -> dict:
    """Hodnoty symbolů pro konkrétní záznam. Chybějící se prostě nevyplní.

    `user` může být `None` — automatika posílá e-maily i z nočního plánovače,
    kde žádný přihlášený člověk není. Symboly `{{moje_jmeno}}` a `{{muj_email}}`
    pak zůstanou nedoplněné, což je správně: appka se nemá podepsat cizím jménem.
    """
    out = {
        "moje_jmeno": (user.jmeno or "") if user is not None else "",
        "muj_email": (user.email or "") if user is not None else "",
    }
    if not entita or zaznam_id is None:
        return {k: v for k, v in out.items() if v}

    from app.mailer import app_url

    cesta = cesta_zaznamu(entita, zaznam_id)
    if cesta:
        out["odkaz"] = f"{app_url()}{cesta}"

    if entita == "zakaznik":
        z = db.get(Zakaznik, zaznam_id)
        if z is not None:
            out["zakaznik"] = z.nazev or ""
    elif entita == "op":
        p = db.get(ObchodniPripad, zaznam_id)
        if p is not None:
            out["cislo"] = p.cislo or ""
            out["nazev"] = p.nazev or ""
            out["stav"] = _stav_nazev(db, "op", p.stav)
            out["hodnota"] = _cislo_lidsky(p.hodnota_kc)
            if p.vlastnik is not None:
                out["vlastnik"] = p.vlastnik.jmeno or p.vlastnik.email or ""
            if p.zakaznik is not None:
                out["zakaznik"] = p.zakaznik.nazev or ""
    elif entita == "nab":
        from app.nabidkovac.models import Nabidka

        n = db.get(Nabidka, zaznam_id)
        if n is not None:
            out["cislo"] = n.cislo or ""
            out["zakaznik"] = n.zakaznik_nazev or ""
            out["stav"] = _stav_nazev(db, "nab", n.stav_obchodni)
            if n.obchodni_pripad_id:
                p = db.get(ObchodniPripad, n.obchodni_pripad_id)
                if p is not None:
                    out["nazev"] = p.nazev or ""
                    out["hodnota"] = _cislo_lidsky(p.hodnota_kc)
                    if p.vlastnik is not None:
                        out["vlastnik"] = p.vlastnik.jmeno or p.vlastnik.email or ""
                    if p.zakaznik is not None:
                        out["zakaznik"] = p.zakaznik.nazev or out["zakaznik"]
    elif entita == "obj":
        o = db.get(Objednavka, zaznam_id)
        if o is not None:
            out["cislo"] = o.cislo or ""
            out["nazev"] = o.nazev or ""
            out["stav"] = _stav_nazev(db, "obj", o.stav)
            out["hodnota"] = _cislo_lidsky(o.cena_kc)
            if o.vlastnik is not None:
                out["vlastnik"] = o.vlastnik.jmeno or o.vlastnik.email or ""
            if o.pripad is not None and o.pripad.zakaznik is not None:
                out["zakaznik"] = o.pripad.zakaznik.nazev or ""
    elif entita == "pro":
        # Projekt tady dřív nebyl (šablony se psaly jen z případu a nabídky).
        # Automatizace ho potřebuje: „projekt dokončen → e-mail zákazníkovi".
        from app.crm.models import CrmProjekt

        pr = db.get(CrmProjekt, zaznam_id)
        if pr is not None:
            out["cislo"] = pr.cislo or ""
            out["nazev"] = pr.nazev or ""
            out["stav"] = _stav_nazev(db, "pro", pr.stav)
            if pr.vlastnik is not None:
                out["vlastnik"] = pr.vlastnik.jmeno or pr.vlastnik.email or ""
            if pr.pripad is not None:
                out["hodnota"] = _cislo_lidsky(pr.pripad.hodnota_kc)
                if pr.pripad.zakaznik is not None:
                    out["zakaznik"] = pr.pripad.zakaznik.nazev or ""

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
