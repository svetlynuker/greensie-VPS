from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.database import get_db
from app.logy.models import Log
from app.logy.schemas import LogOut, SmazaniVysledek

router = APIRouter(prefix="/logy", tags=["logy"])


def vyzaduj_pravo_logy(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí otevřít dlaždici Logy (admin ji má vždy)."""
    if not muze_otevrit(user, "logy"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na zobrazení logů nemáš oprávnění.",
        )
    return user


@router.get("", response_model=list[LogOut])
def seznam_logu(
    user: User = Depends(vyzaduj_pravo_logy),
    db: Session = Depends(get_db),
    typ: str | None = Query(None, description="filtr: provoz / audit / chyba"),
    hledej: str | None = Query(None, description="hledá v cestě, popisu a e-mailu uživatele"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[Log]:
    """Vrátí poslední záznamy (od nejnovějších) s volitelnými filtry."""
    dotaz = db.query(Log)
    if typ in ("provoz", "audit", "chyba"):
        dotaz = dotaz.filter(Log.typ == typ)
    if hledej:
        vzor = f"%{hledej.strip()}%"
        dotaz = dotaz.filter(
            or_(
                Log.cesta.ilike(vzor),
                Log.popis.ilike(vzor),
                Log.uzivatel_email.ilike(vzor),
            )
        )
    radky = dotaz.order_by(Log.cas.desc(), Log.id.desc()).limit(limit).all()
    # Detail chyby (traceback) může obsahovat interní cesty i citlivá data –
    # necháme ho vidět jen supersprávci. Ostatním ho z odpovědi odebereme.
    # (Session je autoflush=False a nekomitujeme, takže se změna neuloží do DB.)
    if not user.je_admin:
        for r in radky:
            r.detail = None
    return radky


@router.delete("", response_model=SmazaniVysledek)
def smaz_logy(
    _user: User = Depends(vyzaduj_pravo_logy),
    db: Session = Depends(get_db),
    starsi_nez_dni: int | None = Query(
        None, ge=0, description="smaže záznamy starší než N dní; bez parametru smaže vše"
    ),
) -> SmazaniVysledek:
    """Ruční pročištění logu (automaticky se nic nemaže)."""
    dotaz = db.query(Log)
    if starsi_nez_dni is not None:
        hranice = datetime.now(timezone.utc) - timedelta(days=starsi_nez_dni)
        dotaz = dotaz.filter(Log.cas < hranice)
    pocet = dotaz.delete(synchronize_session=False)
    db.commit()
    return SmazaniVysledek(smazano=pocet)
