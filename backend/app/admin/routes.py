from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import Role, Skupina, User
from app.auth.permissions import PRAVA, VSECHNA_PRAVA, hash_heslo, vyzaduj_admina
from app.database import get_db
from app.admin.schemas import (
    CiselnikyOut,
    PravoOut,
    SkupinaOut,
    SkupinaVstup,
    UzivatelOut,
    UzivatelUprava,
    UzivatelVstup,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(vyzaduj_admina)])


# ---- pomocné ----
def _over_prava(prava: list[str]) -> list[str]:
    neznama = [p for p in prava if p not in VSECHNA_PRAVA]
    if neznama:
        raise HTTPException(status_code=422, detail=f"Neznámá práva: {', '.join(neznama)}")
    # deduplikace při zachování pořadí katalogu
    return [p["klic"] for p in PRAVA if p["klic"] in set(prava)]


def _over_skupina(db: Session, skupina_id):
    if skupina_id is not None and db.get(Skupina, skupina_id) is None:
        raise HTTPException(status_code=422, detail="Skupina neexistuje")


def _pocet_adminu(db: Session) -> int:
    return db.query(User).filter(User.role == Role.admin).count()


def _uzivatel_out(u: User) -> UzivatelOut:
    return UzivatelOut(
        id=u.id,
        jmeno=u.jmeno,
        email=u.email,
        role=u.role,
        skupina_id=u.skupina_id,
        extra_prava=list(u.extra_prava or []),
    )


def _skupina_out(s: Skupina) -> SkupinaOut:
    return SkupinaOut(
        id=s.id, nazev=s.nazev, prava=list(s.prava or []), pocet_clenu=len(s.clenove)
    )


# ---- číselníky (katalog práv a rolí pro UI) ----
@router.get("/ciselniky", response_model=CiselnikyOut)
def ciselniky():
    return CiselnikyOut(
        prava=[PravoOut(klic=p["klic"], nazev=p["nazev"]) for p in PRAVA],
        role=[r.value for r in Role],
    )


# ---- uživatelé ----
@router.get("/uzivatele", response_model=list[UzivatelOut])
def seznam_uzivatelu(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.jmeno, User.id).all()
    return [_uzivatel_out(u) for u in users]


@router.post("/uzivatele", response_model=UzivatelOut)
def pridej_uzivatele(vstup: UzivatelVstup, db: Session = Depends(get_db)):
    email = vstup.email.strip().lower()
    jmeno = vstup.jmeno.strip()
    if not jmeno:
        raise HTTPException(status_code=422, detail="Jméno je povinné")
    if not email:
        raise HTTPException(status_code=422, detail="E-mail je povinný")
    if not vstup.heslo:
        raise HTTPException(status_code=422, detail="Heslo je povinné")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Uživatel s tímto e-mailem už existuje")
    _over_skupina(db, vstup.skupina_id)
    prava = _over_prava(vstup.extra_prava)

    u = User(
        jmeno=jmeno,
        email=email,
        heslo_hash=hash_heslo(vstup.heslo),
        role=vstup.role,
        skupina_id=vstup.skupina_id,
        extra_prava=prava,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return _uzivatel_out(u)


@router.put("/uzivatele/{uzivatel_id}", response_model=UzivatelOut)
def uprav_uzivatele(uzivatel_id: int, vstup: UzivatelUprava, db: Session = Depends(get_db)):
    u = db.get(User, uzivatel_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Uživatel neexistuje")

    email = vstup.email.strip().lower()
    jmeno = vstup.jmeno.strip()
    if not jmeno:
        raise HTTPException(status_code=422, detail="Jméno je povinné")
    if not email:
        raise HTTPException(status_code=422, detail="E-mail je povinný")
    jiny = db.query(User).filter(User.email == email, User.id != uzivatel_id).first()
    if jiny:
        raise HTTPException(status_code=409, detail="Jiný uživatel s tímto e-mailem už existuje")
    _over_skupina(db, vstup.skupina_id)
    prava = _over_prava(vstup.extra_prava)

    # pojistka: nesmíme degradovat posledního admina
    if u.role == Role.admin and vstup.role != Role.admin and _pocet_adminu(db) <= 1:
        raise HTTPException(
            status_code=409, detail="Nelze odebrat roli poslednímu adminovi."
        )

    u.jmeno = jmeno
    u.email = email
    u.role = vstup.role
    u.skupina_id = vstup.skupina_id
    u.extra_prava = prava
    if vstup.heslo:
        u.heslo_hash = hash_heslo(vstup.heslo)

    db.commit()
    db.refresh(u)
    return _uzivatel_out(u)


@router.delete("/uzivatele/{uzivatel_id}")
def smaz_uzivatele(
    uzivatel_id: int,
    admin: User = Depends(vyzaduj_admina),
    db: Session = Depends(get_db),
):
    u = db.get(User, uzivatel_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Uživatel neexistuje")
    if u.id == admin.id:
        raise HTTPException(status_code=409, detail="Nemůžeš smazat sám sebe.")
    if u.role == Role.admin and _pocet_adminu(db) <= 1:
        raise HTTPException(status_code=409, detail="Nelze smazat posledního admina.")
    db.delete(u)
    db.commit()
    return {"smazano": uzivatel_id}


# ---- skupiny ----
@router.get("/skupiny", response_model=list[SkupinaOut])
def seznam_skupin(db: Session = Depends(get_db)):
    skupiny = db.query(Skupina).order_by(Skupina.nazev, Skupina.id).all()
    return [_skupina_out(s) for s in skupiny]


@router.post("/skupiny", response_model=SkupinaOut)
def pridej_skupinu(vstup: SkupinaVstup, db: Session = Depends(get_db)):
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název skupiny je povinný")
    if db.query(Skupina).filter(Skupina.nazev == nazev).first():
        raise HTTPException(status_code=409, detail="Skupina s tímto názvem už existuje")
    prava = _over_prava(vstup.prava)
    s = Skupina(nazev=nazev, prava=prava)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _skupina_out(s)


@router.put("/skupiny/{skupina_id}", response_model=SkupinaOut)
def uprav_skupinu(skupina_id: int, vstup: SkupinaVstup, db: Session = Depends(get_db)):
    s = db.get(Skupina, skupina_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Skupina neexistuje")
    nazev = vstup.nazev.strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název skupiny je povinný")
    jina = db.query(Skupina).filter(Skupina.nazev == nazev, Skupina.id != skupina_id).first()
    if jina:
        raise HTTPException(status_code=409, detail="Jiná skupina s tímto názvem už existuje")
    s.nazev = nazev
    s.prava = _over_prava(vstup.prava)
    db.commit()
    db.refresh(s)
    return _skupina_out(s)


@router.delete("/skupiny/{skupina_id}")
def smaz_skupinu(skupina_id: int, db: Session = Depends(get_db)):
    s = db.get(Skupina, skupina_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Skupina neexistuje")
    # členům se skupina_id díky ON DELETE SET NULL vynuluje samo
    db.delete(s)
    db.commit()
    return {"smazano": skupina_id}
