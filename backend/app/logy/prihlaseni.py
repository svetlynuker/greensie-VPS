"""Zápis a čtení historie přihlášení (tabulka `prihlaseni`).

Zapisuje se u každého pokusu o přihlášení — úspěšného i neúspěšného. Zápis je
„best-effort": kdyby selhal, přihlášení nikdy neshodí (obalený try/except),
protože evidence nesmí rozbít vlastní přístup do appky.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.logy.models import (
    MAX_EMAIL,
    MAX_IP,
    Prihlaseni,
    orez,
)

MAX_ZARIZENI = 120
MAX_USER_AGENT = 500
MAX_DUVOD = 200
MAX_JMENO = 200

# Rozpoznání prohlížeče a systému z hlavičky User-Agent. Nejde o přesnou
# detekci — stačí, aby v přehledu bylo poznat „to jsem já z kanceláře" proti
# „to je někdo cizí". Pořadí je důležité: Edge i Chrome se hlásí jako Chrome
# a Safari se hlásí ve všech, proto se hledá od nejužšího k nejobecnějšímu.
_PROHLIZECE = [
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Chrome/", "Chrome"),
    ("Firefox/", "Firefox"),
    ("Safari/", "Safari"),
]

_SYSTEMY = [
    ("Android", "Androidu"),
    ("iPhone", "iPhonu"),
    ("iPad", "iPadu"),
    ("Windows", "Windows"),
    ("Mac OS X", "Macu"),
    ("Macintosh", "Macu"),
    ("Linux", "Linuxu"),
]


def popis_zarizeni(user_agent: str | None) -> str | None:
    """Z hlavičky User-Agent udělá čitelné „Chrome na Windows"."""
    if not user_agent:
        return None
    prohlizec = next((n for vzor, n in _PROHLIZECE if vzor in user_agent), None)
    system = next((n for vzor, n in _SYSTEMY if vzor in user_agent), None)
    if prohlizec and system:
        return f"{prohlizec} na {system}"
    return prohlizec or system


def ip_klienta(request) -> str | None:
    """IP klienta za reverzní proxy (Caddy).

    Skutečná IP je POSLEDNÍ prvek X-Forwarded-For — ten přidává proxy.
    Dřívější prvky si může klient podvrhnout. Stejné pravidlo jako
    v logovacím middleware; u historie přihlášení na tom záleží víc,
    protože podle IP se pozná cizí pokus.
    """
    if request is None:
        return None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else None


def zaznamenej_prihlaseni(
    db: Session,
    *,
    request=None,
    uspech: bool,
    uzivatel_id: int | None = None,
    uzivatel_email: str | None = None,
    uzivatel_jmeno: str | None = None,
    duvod: str | None = None,
) -> None:
    """Zapíše jeden pokus o přihlášení. Chybu potichu spolkne.

    `uzivatel_email` se vyplňuje jen u známého účtu. U neúspěchu na neznámý
    e-mail se surový vstup NEUKLÁDÁ — do pole s e-mailem se dá omylem napsat
    heslo a to by tu pak zůstalo natrvalo (stejná zásada jako v auditu).
    """
    try:
        user_agent = request.headers.get("user-agent") if request is not None else None
        db.add(
            Prihlaseni(
                uspech=bool(uspech),
                uzivatel_id=uzivatel_id,
                uzivatel_email=orez(uzivatel_email, MAX_EMAIL),
                uzivatel_jmeno=orez(uzivatel_jmeno, MAX_JMENO),
                duvod=orez(duvod, MAX_DUVOD),
                ip=orez(ip_klienta(request), MAX_IP),
                zarizeni=orez(popis_zarizeni(user_agent), MAX_ZARIZENI),
                user_agent=orez(user_agent, MAX_USER_AGENT),
            )
        )
        db.commit()
    except Exception:  # noqa: BLE001 - evidence nesmí shodit přihlášení
        db.rollback()


def posledni_prihlaseni(db: Session, uzivatele_id: list[int]) -> dict[int, datetime]:
    """Ke každému id vrátí čas posledního ÚSPĚŠNÉHO přihlášení (kdo se nikdy
    nepřihlásil, v mapě prostě není)."""
    from sqlalchemy import func

    if not uzivatele_id:
        return {}
    radky = (
        db.query(Prihlaseni.uzivatel_id, func.max(Prihlaseni.cas))
        .filter(
            Prihlaseni.uspech.is_(True),
            Prihlaseni.uzivatel_id.in_(uzivatele_id),
        )
        .group_by(Prihlaseni.uzivatel_id)
        .all()
    )
    return {uid: cas for uid, cas in radky if uid is not None}


def pocet_neuspechu(db: Session, hodin: int = 24) -> int:
    """Kolik neúspěšných pokusů bylo za posledních N hodin (varovný ukazatel)."""
    hranice = datetime.now(timezone.utc) - timedelta(hours=hodin)
    return (
        db.query(Prihlaseni)
        .filter(Prihlaseni.uspech.is_(False), Prihlaseni.cas >= hranice)
        .count()
    )
