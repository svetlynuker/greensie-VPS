"""Logika přítomnosti („kdo má tuhle věc zrovna otevřenou“).

Oddělené od endpointů schválně: takhle se dá celé chování otestovat nad SQLite
bez HTTP vrstvy. Endpointy v `routes.py` jen doplní práva a commit.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.pritomnost.models import Pritomnost

# Kdo tikl dřív než před `OKNO_S` sekundami, už se za přítomného nepočítá.
# Musí být pohodlně větší než tikací interval prohlížeče (8 s), jinak by lidé
# ze seznamu problikávali při každém zdržení sítě.
OKNO_S = 25

# Po téhle době se řádek zahodí úplně (úklid při tiku). Menší hodnota by nic
# nezkazila, ale ani nepomohla — tabulka má řádově tolik řádků, kolik je
# přihlášených lidí.
UKLID_S = 600


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Dorovná naive datetime na UTC.

    Postgres vrací `kdy` s časovou zónou, SQLite (testy) bez ní. Bez tohohle
    by porovnání naive a aware času skončilo TypeError — a to až v testu,
    ne v produkci, což je nejhorší kombinace.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def zapis_tik(
    db: Session,
    *,
    uzivatel_id: int,
    entita_typ: str,
    entita_id: str = "",
    pole: str = "",
    nyni: datetime | None = None,
) -> Pritomnost:
    """Založí nebo obnoví přítomnost. Necommituje — to dělá volající."""
    nyni = nyni or _ted()
    zaznam = (
        db.query(Pritomnost)
        .filter(
            Pritomnost.uzivatel_id == uzivatel_id,
            Pritomnost.entita_typ == entita_typ,
            Pritomnost.entita_id == entita_id,
        )
        .first()
    )
    if zaznam is None:
        zaznam = Pritomnost(
            uzivatel_id=uzivatel_id,
            entita_typ=entita_typ,
            entita_id=entita_id,
        )
        db.add(zaznam)
        try:
            db.flush()
        except IntegrityError:
            # Dvě záložky téhož člověka mohou tiknout naráz a obě projít
            # kontrolou výš. Unikátní index to zachytí; pak už jen obnovíme
            # existující řádek, místo aby tik skončil chybou.
            db.rollback()
            zaznam = (
                db.query(Pritomnost)
                .filter(
                    Pritomnost.uzivatel_id == uzivatel_id,
                    Pritomnost.entita_typ == entita_typ,
                    Pritomnost.entita_id == entita_id,
                )
                .first()
            )
            if zaznam is None:  # pragma: no cover - nemělo by nastat
                raise
    zaznam.pole = pole or ""
    zaznam.kdy = nyni
    return zaznam


def odhlas(
    db: Session, *, uzivatel_id: int, entita_typ: str, entita_id: str = ""
) -> None:
    """Smaže přítomnost (zavření stránky). Nepovinné — okno `OKNO_S` to zvládne samo."""
    db.query(Pritomnost).filter(
        Pritomnost.uzivatel_id == uzivatel_id,
        Pritomnost.entita_typ == entita_typ,
        Pritomnost.entita_id == entita_id,
    ).delete(synchronize_session=False)


def precti_pritomne(
    db: Session,
    *,
    entita_typ: str,
    entita_id: str = "",
    nyni: datetime | None = None,
) -> list[dict]:
    """Kdo je právě na dané entitě — seřazeno podle jména.

    Filtr času je záměrně v Pythonu, ne v SQL: řádků je málo (jeden na
    přihlášeného člověka) a porovnání aware/naive času se mezi Postgresem
    a SQLite chová jinak.
    """
    nyni = nyni or _ted()
    mez = nyni - timedelta(seconds=OKNO_S)
    radky = (
        db.query(Pritomnost, User.jmeno)
        .join(User, User.id == Pritomnost.uzivatel_id)
        .filter(
            Pritomnost.entita_typ == entita_typ,
            Pritomnost.entita_id == entita_id,
        )
        .all()
    )
    lidi = [
        {"uzivatel_id": p.uzivatel_id, "jmeno": jmeno, "pole": p.pole or ""}
        for p, jmeno in radky
        if (_aware(p.kdy) or nyni) >= mez
    ]
    lidi.sort(key=lambda c: (c["jmeno"] or "").lower())
    return lidi


def uklid(db: Session, *, nyni: datetime | None = None) -> int:
    """Zahodí dávno neobnovené řádky. Vrací počet smazaných."""
    nyni = nyni or _ted()
    mez = nyni - timedelta(seconds=UKLID_S)
    stare = [p.id for p in db.query(Pritomnost).all() if (_aware(p.kdy) or nyni) < mez]
    if not stare:
        return 0
    db.query(Pritomnost).filter(Pritomnost.id.in_(stare)).delete(synchronize_session=False)
    return len(stare)
