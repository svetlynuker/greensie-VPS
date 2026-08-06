from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.database import get_db
from app.pritomnost import registr, sluzba
from app.pritomnost.schemas import PritomnyOut, TikOut, TikVstup

router = APIRouter(prefix="/pritomnost", tags=["pritomnost"])


def _overy(db: Session, user: User, vstup: TikVstup) -> None:
    """Ověří entitu, právo na modul a přístup ke konkrétnímu záznamu."""
    pravo = registr.pravo_pro(vstup.entita_typ)
    if pravo is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Neznámý typ entity: {vstup.entita_typ}",
        )
    if not muze_otevrit(user, pravo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na tento modul nemáš oprávnění.",
        )
    # Druhá vrstva: v CRM vidí člověk bez práva `crm_vse` jen svoje záznamy.
    # Odpověď je 404, ne 403 — cizí záznam se nemá projevit ani svou existencí,
    # jinak by se zkoušením ID dalo zjistit, co firma vede a kdo na tom pracuje.
    if not registr.ma_pristup(db, user, vstup.entita_typ, vstup.entita_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Záznam neexistuje")


@router.post("/tik", response_model=TikOut)
def tik(
    vstup: TikVstup,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ohlásí „jsem tady“ a vrátí, kdo tu je ještě a jaké je razítko změn.

    Jeden požadavek dělá obojí schválně: prohlížeč tak nepotřebuje druhý
    dotaz na aktualizace a synchronizace nestojí ani jedno spojení navíc.
    """
    _overy(db, user, vstup)

    sluzba.zapis_tik(
        db,
        uzivatel_id=user.id,
        entita_typ=vstup.entita_typ,
        entita_id=vstup.entita_id,
        pole=vstup.pole,
    )
    sluzba.uklid(db)
    db.commit()

    lidi = sluzba.precti_pritomne(
        db, entita_typ=vstup.entita_typ, entita_id=vstup.entita_id
    )
    return TikOut(
        pritomni=[
            PritomnyOut(
                uzivatel_id=c["uzivatel_id"],
                jmeno=c["jmeno"],
                pole=c["pole"],
                ja=c["uzivatel_id"] == user.id,
            )
            for c in lidi
        ],
        razitko=registr.razitko(db, vstup.entita_typ, vstup.entita_id),
    )


@router.post("/odchod")
def odchod(
    vstup: TikVstup,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Odhlásí přítomnost při zavření stránky (aby kolečko zmizelo hned).

    Není to nutné — nedoručený odchod vyprší sám za `sluzba.OKNO_S`.
    """
    _overy(db, user, vstup)
    sluzba.odhlas(
        db,
        uzivatel_id=user.id,
        entita_typ=vstup.entita_typ,
        entita_id=vstup.entita_id,
    )
    db.commit()
    return {"ok": True}
