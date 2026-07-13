from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user
from app.database import get_db
from app.nastaveni.models import UzivatelskeNastaveni
from app.nastaveni.schemas import NastaveniVstup

router = APIRouter(prefix="/nastaveni", tags=["nastaveni"])


@router.get("")
def nacti_nastaveni(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Vrátí všechna nastavení přihlášeného uživatele jako {klíč: hodnota}."""
    rows = (
        db.query(UzivatelskeNastaveni)
        .filter(UzivatelskeNastaveni.uzivatel_id == user.id)
        .all()
    )
    return {r.klic: r.hodnota for r in rows}


@router.put("/{klic}")
def uloz_nastaveni(
    klic: str,
    vstup: NastaveniVstup,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Uloží (upsert) jedno nastavení přihlášeného uživatele."""
    row = (
        db.query(UzivatelskeNastaveni)
        .filter(
            UzivatelskeNastaveni.uzivatel_id == user.id,
            UzivatelskeNastaveni.klic == klic,
        )
        .first()
    )
    if row is None:
        row = UzivatelskeNastaveni(uzivatel_id=user.id, klic=klic)
        db.add(row)
    row.hodnota = vstup.hodnota
    db.commit()
    return {klic: vstup.hodnota}
