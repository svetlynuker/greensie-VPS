from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import LoginRequest, MeOut, Token, User, UserOut, ZmenaHeslaVstup
from app.auth.permissions import (
    dlazdice_pro,
    get_current_user,
    hash_heslo,
    muze_editovat,
    over_heslo,
    prava_uzivatele,
    vytvor_access_token,
)
from app.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(udaje: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == udaje.email).first()
    if user is None or not over_heslo(udaje.heslo, user.heslo_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávný e-mail nebo heslo",
        )
    token = vytvor_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(
        uzivatel=UserOut(id=user.id, jmeno=user.jmeno, email=user.email, je_admin=user.je_admin),
        dlazdice=dlazdice_pro(user),
        muze_editovat=muze_editovat(user),
        prava=sorted(prava_uzivatele(user)),
        musi_zmenit_heslo=user.musi_zmenit_heslo,
    )


@router.put("/heslo")
def zmen_heslo(
    vstup: ZmenaHeslaVstup,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Změna vlastního hesla (mj. povinná po prvním přihlášení)."""
    nove = (vstup.nove_heslo or "").strip()
    if len(nove) < 6:
        raise HTTPException(status_code=422, detail="Heslo musí mít alespoň 6 znaků.")
    user.heslo_hash = hash_heslo(nove)
    user.musi_zmenit_heslo = False
    db.commit()
    return {"stav": "ok"}
