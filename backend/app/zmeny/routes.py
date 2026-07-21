"""Přehled změn (Pohled 3).

Ukáže, co se v projektech za zvolené období pohnulo – kolik úkolů se splnilo,
kolik spadlo do prodlení a kolik je v prodlení teď. Počítá se jako čistý rozdíl
dvou „fotek“ stavu (snímek k datu OD vs. snímek/živý stav k datu DO).

Sledujeme jen dimenzi hotovo/nehotovo; prodlení se dopočítává ze stavu + termínu
vůči danému dni (prodlení = úkol je todo a jeho termín je v minulosti).
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.database import get_db
from app.matice.models import Bunka, Projekt, Sloupec
from app.zmeny import snapshot
from app.zmeny.schemas import ProjektZmeny, Souhrn, UkolZmena, ZmenyOut

router = APIRouter(prefix="/zmeny", tags=["zmeny"])


def vyzaduj_pravo_zmeny(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí otevřít dlaždici Přehled změn (vedení+, admin vždy)."""
    if not muze_otevrit(user, "zmeny"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Přehled změn nemáš oprávnění.",
        )
    return user


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Neplatné datum: {s}")


def _date_str(d: date | None) -> str | None:
    return d.isoformat() if isinstance(d, date) else None


def _je_v_prodleni(stav, termin, ke_dni: date) -> bool:
    """Prodlení = úkol je nehotový a jeho termín už je v minulosti (vůči ke_dni)."""
    return stav == "todo" and termin is not None and termin < ke_dni


@router.get("", response_model=ZmenyOut)
def prehled_zmen(
    _user: User = Depends(vyzaduj_pravo_zmeny),
    db: Session = Depends(get_db),
    od: str | None = Query(None, description="začátek období YYYY-MM-DD; prázdné = od začátku"),
    do: str | None = Query(None, description="konec období YYYY-MM-DD; prázdné = dnes"),
) -> ZmenyOut:
    dnes = date.today()
    sledovano_od = snapshot.nejstarsi_den(db)

    # --- hranice období ---
    do_datum = _parse_date(do) or dnes
    if do_datum > dnes:
        do_datum = dnes  # do budoucnosti nemá smysl, konec je nejpozději dnes
    # bez „od“ bereme úplný začátek sledování; když ještě nic nemáme, období je prázdné
    od_datum = _parse_date(od) or sledovano_od or dnes
    if od_datum > do_datum:
        od_datum = do_datum

    # --- stav na začátku a na konci období ---
    stav_od, _ = snapshot.snimek_ke_dni(db, od_datum)
    if do_datum >= dnes:
        stav_do = snapshot.ziv_stav(db)  # dnešek = živý aktuální stav
    else:
        stav_do, _ = snapshot.snimek_ke_dni(db, do_datum)

    # --- metadata buněk (projekt, fáze/úkol, odkaz) ---
    bunky = db.query(Bunka.id, Bunka.projekt_id, Bunka.sloupec_id, Bunka.url).all()
    bunka_meta = {b.id: b for b in bunky}
    sloupce = {s.id: s for s in db.query(Sloupec).all()}
    projekty = {
        p.id: p
        for p in db.query(Projekt).filter(Projekt.skryty == False).all()  # noqa: E712
    }

    # --- agregace po projektech ---
    per_projekt: dict[int, ProjektZmeny] = {}

    def _radek(projekt_id: int) -> ProjektZmeny | None:
        if projekt_id not in projekty:
            return None
        if projekt_id not in per_projekt:
            p = projekty[projekt_id]
            per_projekt[projekt_id] = ProjektZmeny(id=p.id, nazev=p.nazev, url=p.url or "")
        return per_projekt[projekt_id]

    def _ukol(bunka, termin) -> UkolZmena:
        s = sloupce.get(bunka.sloupec_id)
        return UkolZmena(
            ukol=s.label if s else "",
            faze=s.faze if s else "",
            nazev=s.nazev if s else "",
            termin=_date_str(termin),
            url=bunka.url or "",
        )

    for bunka_id in set(stav_od) | set(stav_do):
        bunka = bunka_meta.get(bunka_id)
        if bunka is None:
            continue
        radek = _radek(bunka.projekt_id)
        if radek is None:
            continue

        stav_start, termin_start = stav_od.get(bunka_id, (None, None))
        stav_end, termin_end = stav_do.get(bunka_id, (None, None))

        prodleni_start = _je_v_prodleni(stav_start, termin_start, od_datum)
        prodleni_end = _je_v_prodleni(stav_end, termin_end, do_datum)

        if stav_start == "todo" and stav_end == "done":
            radek.splneno += 1
            radek.detail_splneno.append(_ukol(bunka, termin_end))
        if prodleni_end and not prodleni_start:
            radek.spadlo_do_prodleni += 1
            radek.detail_spadlo.append(_ukol(bunka, termin_end))
        if prodleni_end:
            radek.aktualne_v_prodleni += 1
            radek.detail_prodleni.append(_ukol(bunka, termin_end))

    # jen projekty s pohybem
    radky = [
        r
        for r in per_projekt.values()
        if r.splneno or r.spadlo_do_prodleni or r.aktualne_v_prodleni
    ]
    radky.sort(
        key=lambda r: (
            -r.aktualne_v_prodleni,
            -r.spadlo_do_prodleni,
            -r.splneno,
            r.nazev.lower(),
        )
    )

    souhrn = Souhrn(
        splneno=sum(r.splneno for r in radky),
        spadlo_do_prodleni=sum(r.spadlo_do_prodleni for r in radky),
        aktualne_v_prodleni=sum(r.aktualne_v_prodleni for r in radky),
    )

    return ZmenyOut(
        od=_date_str(od_datum),
        do=_date_str(do_datum),
        sledovano_od=_date_str(sledovano_od),
        souhrn=souhrn,
        projekty=radky,
    )
