from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import LoginRequest, MeOut, Token, User, UserOut
from app.auth.permissions import (
    get_current_user,
    over_heslo,
    viditelne_dlazdice,
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
        uzivatel=UserOut(id=user.id, jmeno=user.jmeno, email=user.email, role=user.role),
        dlazdice=viditelne_dlazdice(user),
    )
