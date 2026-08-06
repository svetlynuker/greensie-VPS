from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.models import (
    LoginRequest,
    MeOut,
    ProfilOut,
    ProfilVstup,
    Token,
    User,
    UserOut,
    UzivatelProfil,
    ZmenaHeslaVstup,
)
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
from app.logy.audit import zaznamenej_audit
from app.logy.prihlaseni import zaznamenej_prihlaseni

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(udaje: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == udaje.email).first()
    if user is None or not over_heslo(udaje.heslo, user.heslo_hash):
        # Neúspěšné přihlášení zaznamenáme kvůli auditu. Surový vstup ukládáme
        # jen když e-mail patří existujícímu uživateli – u neznámého účtu se
        # do pole e-mail mohlo omylem napsat heslo, to nesmíme uložit natrvalo.
        if user is not None:
            zaznamenej_audit(
                db,
                f"Neúspěšné přihlášení: {user.email}",
                uzivatel_id=user.id,
                uzivatel_email=user.email,
                metoda="POST",
                cesta="/auth/login",
                status_kod=status.HTTP_401_UNAUTHORIZED,
            )
            zaznamenej_prihlaseni(
                db,
                request=request,
                uspech=False,
                uzivatel_id=user.id,
                uzivatel_email=user.email,
                uzivatel_jmeno=user.jmeno,
                duvod="špatné heslo",
            )
        else:
            zaznamenej_audit(
                db,
                "Neúspěšné přihlášení (neznámý účet)",
                metoda="POST",
                cesta="/auth/login",
                status_kod=status.HTTP_401_UNAUTHORIZED,
            )
            zaznamenej_prihlaseni(
                db,
                request=request,
                uspech=False,
                duvod="neznámý účet",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nesprávný e-mail nebo heslo",
        )
    token = vytvor_access_token({"sub": str(user.id)})
    zaznamenej_audit(
        db,
        f"Přihlášení: {user.jmeno}",
        uzivatel_id=user.id,
        uzivatel_email=user.email,
        metoda="POST",
        cesta="/auth/login",
        status_kod=200,
    )
    zaznamenej_prihlaseni(
        db,
        request=request,
        uspech=True,
        uzivatel_id=user.id,
        uzivatel_email=user.email,
        uzivatel_jmeno=user.jmeno,
    )
    return Token(access_token=token)


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(
        uzivatel=UserOut(
            id=user.id,
            jmeno=user.jmeno,
            email=user.email,
            je_admin=user.je_admin,
            skupina=user.skupina.nazev if user.skupina is not None else None,
        ),
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


# ---- profil pro e-mailový podpis (CRM-33) ------------------------------------
def _profil_nebo_novy(db: Session, user: User) -> UzivatelProfil:
    """Profil uživatele; když ještě není, založí ho předvyplněný.

    Předvyplnění z `User.jmeno`: appka celé jméno zná, takže po prvním otevření
    karty už je rozdělené na křestní a příjmení a člověk jen dopíše telefon.
    Rozdělí se na první mezeře — u dvou příjmení („Novák Dvořák") to zařadí
    zbytek do příjmení, což je správně častěji než opak.
    """
    profil = db.query(UzivatelProfil).filter(UzivatelProfil.user_id == user.id).first()
    if profil is not None:
        return profil
    casti = (user.jmeno or "").strip().split(" ", 1)
    profil = UzivatelProfil(
        user_id=user.id,
        jmeno=casti[0] if casti and casti[0] else "",
        prijmeni=casti[1].strip() if len(casti) > 1 else "",
    )
    db.add(profil)
    db.commit()
    db.refresh(profil)
    return profil


def _adresa_v_podpisu(db: Session, user: User) -> str:
    """Adresa, která půjde do podpisu: schránka uživatele, jinak účet v appce.

    Schránka má přednost schválně — do podpisu patří adresa, na kterou přijde
    odpověď, ne ta, kterou se člověk hlásí do appky (může být jiná).
    """
    from app.crm.models import CrmEmailUcet

    ucet = (
        db.query(CrmEmailUcet)
        .filter(CrmEmailUcet.user_id == user.id)
        .order_by(CrmEmailUcet.id)
        .first()
    )
    return (ucet.adresa if ucet is not None else user.email) or ""


def _profil_out(db: Session, user: User, profil: UzivatelProfil) -> ProfilOut:
    from app.crm import email_podpis

    adresa = _adresa_v_podpisu(db, user)
    return ProfilOut(
        jmeno=profil.jmeno,
        prijmeni=profil.prijmeni,
        telefon=profil.telefon,
        funkce=profil.funkce,
        pozdrav=profil.pozdrav,
        podpis_zapnuty=profil.podpis_zapnuty,
        podpis_html=email_podpis.sestav_html(profil, adresa),
        podpis_text=email_podpis.sestav_text(profil, adresa),
        navrh_adresy=email_podpis.pracovni_adresa(profil),
        adresa_v_podpisu=adresa,
        pripraveny=email_podpis.profil_je_vyplneny(profil),
    )


@router.get("/profil", response_model=ProfilOut)
def nacti_profil(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Můj profil pro podpis, včetně hotového náhledu podpisu."""
    return _profil_out(db, user, _profil_nebo_novy(db, user))


@router.put("/profil", response_model=ProfilOut)
def uloz_profil(
    vstup: ProfilVstup,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uloží profil. Vrací rovnou přegenerovaný podpis, ať se náhled shoduje.

    Telefon se normalizuje na devět číslic — do pole se dá napsat cokoli
    („+420 773 492 029", „773492029"), ale v datech je jeden tvar. Jinak by
    se tentýž člověk v exportech objevil pod třemi různými čísly.
    """
    from app.crm import email_podpis

    profil = _profil_nebo_novy(db, user)
    profil.jmeno = (vstup.jmeno or "").strip()
    profil.prijmeni = (vstup.prijmeni or "").strip()
    profil.telefon = email_podpis.cislice_telefonu(vstup.telefon)
    profil.funkce = (vstup.funkce or "").strip()
    profil.pozdrav = (vstup.pozdrav or "").strip()
    profil.podpis_zapnuty = bool(vstup.podpis_zapnuty)
    db.commit()
    db.refresh(profil)
    return _profil_out(db, user, profil)
