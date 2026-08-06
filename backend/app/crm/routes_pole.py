"""Endpoint pro ukládání záznamů CRM po jednotlivých polích (autosave).

Jeden generický endpoint místo PATCHe u každé entity: logika je pro všechny
stejná (whitelist → kontrola kolize → zápis → dopočty) a rozepsat ji šestkrát
znamená pět míst, kde se na kontrolu kolize zapomene.

Vlastní router s prefixem `/crm/zaznam`, aby se cesty nemohly potkat
s existujícími `/crm/...` (kolize cest v CRM už dvakrát tiše rozbila funkční
obrazovku — hlídá to `tests/test_kolize_cest.py`).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.crm import automatizace as automatizace_modul
from app.crm import pole_zaznamu as pole_modul
from app.crm import razitko as razitko_modul
from app.database import get_db

router = APIRouter(prefix="/crm/zaznam", tags=["crm-pole"])


class PolePatch(BaseModel):
    pole: str
    # Prázdný text = vymazat hodnotu. Rozepsaný obsah je při automatickém
    # ukládání normální stav, ne chyba.
    hodnota: str = ""
    # Hodnota, kterou prohlížeč zobrazoval před editací. None = „ulož bez
    # kontroly“ (člověk kolizi viděl a potvrdil).
    puvodni: str | None = None
    # True = člověk pole opustil, hodnota je usazená. Teprve tehdy se spouští
    # automatizace „změní se pole“ — viz komentář v `uloz_pole`.
    usazeno: bool = False


def _jmeno(db: Session, uzivatel_id: int | None) -> str:
    if not uzivatel_id:
        return ""
    u = db.get(User, uzivatel_id)
    return u.jmeno if u else ""


def _detail(db: Session, e: pole_modul.Entita, zaznam, user: User):
    """Celý záznam po uložení.

    Vrací se schválně celý, ne jen uložené pole: server dopočítává věci za
    klientovými zády (cena objednávky, termíny navazujících kroků, výpočtová
    vlastní pole). Kdyby si prohlížeč tyhle hodnoty nepřepsal, hlásil by při
    dalším stisku falešnou kolizi.
    """
    # Import až tady — `routes.py` i `routes_realizace.py` jsou velké moduly
    # a import na úrovni souboru by udělal kruh přes sdílené pomocné funkce.
    if e.klic == "zakaznik":
        from app.crm.routes import _zakaznik_detail

        return _zakaznik_detail(zaznam, user, db)
    if e.klic == "kontakt":
        from app.crm.models import Zakaznik
        from app.crm.routes import _kontakt_detail

        return _kontakt_detail(db, zaznam, db.get(Zakaznik, zaznam.zakaznik_id), user)
    if e.klic == "om":
        from app.crm.routes import _misto_out

        return _misto_out(db, zaznam)
    if e.klic == "op":
        from app.crm.routes import _pripad_detail

        return _pripad_detail(db, zaznam, user)
    if e.klic == "obj":
        from app.crm.routes_realizace import _objednavka_detail

        return _objednavka_detail(db, zaznam, user)
    if e.klic == "pro":
        from app.crm.routes_realizace import _projekt_detail

        return _projekt_detail(db, zaznam, user)
    if e.klic == "nab":
        from app.nabidkovac.routes import _nabidka_detail

        return _nabidka_detail(zaznam, db)
    raise HTTPException(status_code=500, detail=f"Chybí výstup pro entitu {e.klic}")


@router.patch("/{entita}/{zaznam_id}/pole")
def uloz_pole(
    entita: str,
    zaznam_id: int,
    vstup: PolePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uloží jedno pole záznamu CRM.

    Vrací celý aktualizovaný záznam. Když do pole mezitím zapsal někdo jiný,
    vrací **409** s tím, kdo a co změnil, a NIC nepřepíše.
    """
    try:
        e = pole_modul.entita(entita)
        pole_modul.over_pole(e, vstup.pole)
    except pole_modul.Nepovolene as chyba:
        raise HTTPException(status_code=422, detail=str(chyba))

    if not muze_otevrit(user, e.pravo):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Na {e.popis.lower()} nemáš oprávnění.",
        )

    zaznam = db.get(e.model, zaznam_id)
    if zaznam is None:
        raise HTTPException(status_code=404, detail=f"{e.popis} neexistuje")

    # Viditelnost po jednotlivých záznamech (`crm_vse` / vlastník; objednávka,
    # projekt i nabídka ji dědí z obchodního případu). Vrací 404, ne 403 —
    # cizí záznam se nemá projevit ani svou existencí.
    if e.overit_pristup:
        e.overit_pristup(db, zaznam, user)

    try:
        pole_modul.zkontroluj_kolizi(e, zaznam, pole=vstup.pole, puvodni=vstup.puvodni)
    except pole_modul.Konflikt as k:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "zprava": "Mezitím to změnil někdo jiný.",
                "pole": k.pole,
                "aktualni": k.aktualni,
                "kdo": _jmeno(db, k.zmenil_id) or ("automat" if k.zmeneno_at else ""),
                "kdy": k.zmeneno_at.isoformat() if k.zmeneno_at else None,
            },
        )

    try:
        pole_modul.zapis_pole(
            db, e, zaznam, pole=vstup.pole, hodnota=vstup.hodnota, uzivatel_id=user.id
        )
    except ValueError as chyba:
        raise HTTPException(status_code=422, detail=str(chyba))
    except HTTPException:
        # Typová kontrola vlastního pole (`vlastni_pole`) hlásí 422 sama.
        raise

    # CRM-31: pravidla navěšená na změnu pole umí poslat e-mail nebo založit
    # záznam. Při ukládání za pochodu by se spustila nad každou nedopsanou
    # mezihodnotou — pravidlo „změní se hodnota → založ objednávku“ by zabralo
    # nad „1“ místo nad „1 500 000“. Proto se spouští jen když člověk pole
    # opustil. Musí to být PŘED commitem: po něm SQLAlchemy zahodí historii
    # atributů a nebylo by z čeho poznat, co se změnilo.
    if vstup.usazeno and e.automatizace:
        automatizace_modul.po_zmene_poli(db, e.automatizace, zaznam, user)

    db.commit()
    db.refresh(zaznam)

    return {
        "zaznam": _detail(db, e, zaznam, user),
        "pole": vstup.pole,
        "zmenil": _jmeno(db, getattr(zaznam, "zmenil_id", None)),
        "zmeneno_at": (
            zaznam.zmeneno_at.isoformat() if getattr(zaznam, "zmeneno_at", None) else None
        ),
        "verze": getattr(zaznam, "verze", 0) or 0,
        "razitko": razitko_modul.razitko_zaznamu(db, e.klic, zaznam.id),
    }


@router.get("/{entita}/{zaznam_id}/razitko")
def nacti_razitko(
    entita: str,
    zaznam_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Podpis stavu záznamu — pro obrazovky, které jen kontrolují změny.

    Běžně přijde razítko rovnou v odpovědi na `POST /pritomnost/tik`, takže se
    nikde nevolá dvakrát.
    """
    try:
        e = pole_modul.entita(entita)
    except pole_modul.Nepovolene as chyba:
        raise HTTPException(status_code=422, detail=str(chyba))
    if not muze_otevrit(user, e.pravo):
        raise HTTPException(status_code=403, detail=f"Na {e.popis.lower()} nemáš oprávnění.")

    zaznam = db.get(e.model, zaznam_id)
    if zaznam is None:
        raise HTTPException(status_code=404, detail=f"{e.popis} neexistuje")
    if e.overit_pristup:
        e.overit_pristup(db, zaznam, user)

    return {"razitko": razitko_modul.razitko_zaznamu(db, e.klic, zaznam.id)}
