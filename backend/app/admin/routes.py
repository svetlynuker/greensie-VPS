from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.models import Skupina, User
from app.auth.permissions import (
    PRAVA,
    VSECHNA_PRAVA,
    hash_heslo,
    vygeneruj_heslo,
    vyzaduj_admina,
)
from app.database import get_db
from app.mailer import email_nastaven, email_pristupu, posli_email
from app.admin.schemas import (
    CiselnikyOut,
    HesloVysledek,
    PravoOut,
    ResetHeslaVstup,
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
    return [p["klic"] for p in PRAVA if p["klic"] in set(prava)]


def _over_skupina(db: Session, skupina_id):
    if skupina_id is not None and db.get(Skupina, skupina_id) is None:
        raise HTTPException(status_code=422, detail="Skupina neexistuje")


def _pocet_adminu(db: Session) -> int:
    return db.query(User).filter(User.je_admin.is_(True)).count()


def _uzivatel_out(u: User) -> UzivatelOut:
    return UzivatelOut(
        id=u.id,
        jmeno=u.jmeno,
        email=u.email,
        je_admin=u.je_admin,
        musi_zmenit_heslo=u.musi_zmenit_heslo,
        skupina_id=u.skupina_id,
        extra_prava=list(u.extra_prava or []),
    )


def _skupina_out(s: Skupina) -> SkupinaOut:
    return SkupinaOut(
        id=s.id, nazev=s.nazev, prava=list(s.prava or []), pocet_clenu=len(s.clenove)
    )


def _posli_pristup(u: User, heslo: str) -> tuple[bool, str | None]:
    """Pokus o odeslání přihlašovacích údajů e-mailem (best-effort)."""
    if not email_nastaven():
        return False, "E-mail se neodeslal – SMTP zatím není nastaven (doplň SMTP_HESLO v .env)."
    try:
        predmet, telo = email_pristupu(u.jmeno, heslo)
        posli_email(u.email, predmet, telo)
        return True, None
    except Exception as e:  # noqa: BLE001 - chybu jen oznámíme, akci nerušíme
        return False, f"E-mail se nepodařilo odeslat: {e}"


# ---- číselníky ----
@router.get("/ciselniky", response_model=CiselnikyOut)
def ciselniky():
    return CiselnikyOut(prava=[PravoOut(klic=p["klic"], nazev=p["nazev"]) for p in PRAVA])


# ---- uživatelé ----
@router.get("/uzivatele", response_model=list[UzivatelOut])
def seznam_uzivatelu(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.jmeno, User.id).all()
    return [_uzivatel_out(u) for u in users]


@router.post("/uzivatele", response_model=HesloVysledek)
def pridej_uzivatele(vstup: UzivatelVstup, db: Session = Depends(get_db)):
    email = vstup.email.strip().lower()
    jmeno = vstup.jmeno.strip()
    if not jmeno:
        raise HTTPException(status_code=422, detail="Jméno je povinné")
    if not email:
        raise HTTPException(status_code=422, detail="E-mail je povinný")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Uživatel s tímto e-mailem už existuje")
    _over_skupina(db, vstup.skupina_id)
    prava = _over_prava(vstup.extra_prava)

    heslo = vygeneruj_heslo()
    u = User(
        jmeno=jmeno,
        email=email,
        heslo_hash=hash_heslo(heslo),
        je_admin=vstup.je_admin,
        musi_zmenit_heslo=True,
        skupina_id=vstup.skupina_id,
        extra_prava=prava,
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    odeslan, poznamka = _posli_pristup(u, heslo)
    return HesloVysledek(
        uzivatel=_uzivatel_out(u), heslo=heslo, email_odeslan=odeslan, email_poznamka=poznamka
    )


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

    # pojistka: nesmíme odebrat práva supersprávce poslednímu adminovi
    if u.je_admin and not vstup.je_admin and _pocet_adminu(db) <= 1:
        raise HTTPException(
            status_code=409, detail="Nelze odebrat supersprávce poslednímu adminovi."
        )

    u.jmeno = jmeno
    u.email = email
    u.je_admin = vstup.je_admin
    u.skupina_id = vstup.skupina_id
    u.extra_prava = prava

    db.commit()
    db.refresh(u)
    return _uzivatel_out(u)


@router.post("/uzivatele/{uzivatel_id}/reset-hesla", response_model=HesloVysledek)
def reset_hesla(uzivatel_id: int, vstup: ResetHeslaVstup, db: Session = Depends(get_db)):
    u = db.get(User, uzivatel_id)
    if u is None:
        raise HTTPException(status_code=404, detail="Uživatel neexistuje")

    if vstup.nove_heslo is not None and vstup.nove_heslo.strip():
        heslo = vstup.nove_heslo.strip()
        if len(heslo) < 6:
            raise HTTPException(status_code=422, detail="Heslo musí mít alespoň 6 znaků.")
    else:
        heslo = vygeneruj_heslo()

    u.heslo_hash = hash_heslo(heslo)
    u.musi_zmenit_heslo = True  # po resetu si uživatel zvolí vlastní heslo
    db.commit()
    db.refresh(u)

    odeslan, poznamka = _posli_pristup(u, heslo)
    return HesloVysledek(
        uzivatel=_uzivatel_out(u), heslo=heslo, email_odeslan=odeslan, email_poznamka=poznamka
    )


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
    if u.je_admin and _pocet_adminu(db) <= 1:
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
    db.delete(s)
    db.commit()
    return {"smazano": skupina_id}
