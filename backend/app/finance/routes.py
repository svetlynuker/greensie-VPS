from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import get_db
from app.finance import pohoda
from app.finance.models import VYCHOZI_POCET_FAKTUR, VYCHOZI_STAV, Faktura
from app.finance.permissions import muze_finance, vyzaduj_finance
from app.finance.schemas import (
    FakturaOut,
    FakturaVstup,
    FinanceOut,
    ObjednavkaFinanceOut,
    PohodaVysledek,
    ProjektFinanceOut,
)
from app.matice.models import Projekt

router = APIRouter(prefix="/finance", tags=["finance"])


# ---- pomocné ----
def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Neplatné datum: {s}")


def _date_str(d):
    return d.isoformat() if isinstance(d, date) else None


def _faktura_out(f: Faktura) -> FakturaOut:
    return FakturaOut(
        id=f.id,
        poradi=f.poradi,
        stav=f.stav,
        castka=float(f.castka) if f.castka is not None else None,
        termin=_date_str(f.termin),
        poznamka=f.poznamka or "",
        variabilni_symbol=f.variabilni_symbol,
        pohoda_potvrzeno=f.pohoda_potvrzeno,
        pohoda_datum_vystaveni=_date_str(f.pohoda_datum_vystaveni),
        pohoda_datum_zaplaceni=_date_str(f.pohoda_datum_zaplaceni),
        upraveno_rucne=f.upraveno_rucne,
    )


def _zaloz_vychozi_faktury(db: Session, projekt_id: int) -> None:
    """Projektu bez faktur založí výchozí počet prázdných (Faktura 1..3)."""
    for i in range(1, VYCHOZI_POCET_FAKTUR + 1):
        db.add(Faktura(projekt_id=projekt_id, poradi=i, stav=VYCHOZI_STAV))


# ---- čtení celé matice financí ----
@router.get("", response_model=FinanceOut)
def nacti_finance(user: User = Depends(vyzaduj_finance), db: Session = Depends(get_db)):
    projekty = db.query(Projekt).order_by(Projekt.poradi, Projekt.id).all()

    # Projektům, které ještě žádnou fakturu nemají, doplň výchozí 3 (lazy –
    # stejný princip jako u řádku barev v Pohledu 1).
    # Filtr na `projekt_id` je podstatný: od CRM-09 žijí v téže tabulce i
    # faktury CRM objednávek a ty do matice Freelo projektů nepatří.
    def _nacti_faktury_projektu() -> dict[int, list[Faktura]]:
        mapa: dict[int, list[Faktura]] = {}
        for f in db.query(Faktura).filter(Faktura.projekt_id.isnot(None)).all():
            mapa.setdefault(f.projekt_id, []).append(f)
        return mapa

    faktury_dle_projektu = _nacti_faktury_projektu()

    zmena = False
    for p in projekty:
        if not faktury_dle_projektu.get(p.id):
            _zaloz_vychozi_faktury(db, p.id)
            zmena = True
    if zmena:
        db.commit()
        faktury_dle_projektu = _nacti_faktury_projektu()

    projekty_out = []
    max_faktur = 0
    for p in projekty:
        fakt = sorted(faktury_dle_projektu.get(p.id, []), key=lambda x: x.poradi)
        max_faktur = max(max_faktur, len(fakt))
        projekty_out.append(
            ProjektFinanceOut(
                id=p.id,
                nazev=p.nazev,
                url=p.url,
                termin=_date_str(p.termin),
                faktury=[_faktura_out(f) for f in fakt],
            )
        )

    objednavky_out, max_faktur_obj = _objednavky_s_fakturami(db)

    return FinanceOut(
        muze_editovat=muze_finance(user),
        max_faktur=max_faktur,
        projekty=projekty_out,
        objednavky=objednavky_out,
        max_faktur_objednavek=max_faktur_obj,
    )


def _objednavky_s_fakturami(db: Session) -> tuple[list[ObjednavkaFinanceOut], int]:
    """CRM objednávky, které už mají rozepsané faktury (CRM-09).

    Objednávky BEZ faktur se sem záměrně nedávají – Přehled financí je o
    penězích, ne o seznamu zakázek. Prázdné faktury se objednávkám ani
    nezakládají automaticky (na rozdíl od Freelo projektů): splátkový kalendář
    se u nové zakázky rozepisuje vědomě, tlačítkem na kartě objednávky.

    Právo: kdo má `finance`, vidí čísla všech objednávek. Je to obrazovka pro
    vedení a účtárnu, kde je smyslem vidět firmu celou; osmičlenná firma tu
    nemá co skrývat před tím, kdo dělá fakturaci.
    """
    from app.crm.models import Objednavka
    from app.crm.stavy import seznam as seznam_stavu

    faktury_dle_objednavky: dict[int, list[Faktura]] = {}
    for f in db.query(Faktura).filter(Faktura.crm_objednavka_id.isnot(None)).all():
        faktury_dle_objednavky.setdefault(f.crm_objednavka_id, []).append(f)
    if not faktury_dle_objednavky:
        return [], 0

    nazvy_stavu = {s.klic: s.nazev for s in seznam_stavu(db, "obj")}
    objednavky = (
        db.query(Objednavka)
        .filter(Objednavka.id.in_(faktury_dle_objednavky.keys()))
        .order_by(Objednavka.cislo.desc())
        .all()
    )

    out: list[ObjednavkaFinanceOut] = []
    max_faktur = 0
    for o in objednavky:
        fakt = sorted(faktury_dle_objednavky.get(o.id, []), key=lambda x: x.poradi)
        max_faktur = max(max_faktur, len(fakt))
        zakaznik = ""
        if o.pripad is not None and o.pripad.zakaznik is not None:
            zakaznik = o.pripad.zakaznik.nazev
        out.append(
            ObjednavkaFinanceOut(
                id=o.id,
                cislo=o.cislo,
                nazev=o.nazev or "",
                zakaznik_nazev=zakaznik,
                cena_kc=float(o.cena_kc) if o.cena_kc is not None else None,
                stav_nazev=nazvy_stavu.get(o.stav, o.stav),
                faktury=[_faktura_out(f) for f in fakt],
            )
        )
    return out, max_faktur


# ---- editace faktury ----
@router.put("/faktura/{faktura_id}", response_model=FakturaOut)
def uloz_fakturu(
    faktura_id: int,
    vstup: FakturaVstup,
    user: User = Depends(vyzaduj_finance),
    db: Session = Depends(get_db),
):
    f = db.get(Faktura, faktura_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Faktura neexistuje")
    if f.crm_objednavka_id is not None:
        # Faktura CRM objednávky se edituje na kartě objednávky, kde platí
        # práva CRM. Přes Přehled financí by ji mohl měnit i ten, kdo na
        # zakázku nevidí – proto sem nepatří.
        raise HTTPException(
            status_code=409,
            detail="Tahle faktura patří CRM objednávce – uprav ji na kartě objednávky.",
        )

    f.stav = vstup.stav
    f.castka = vstup.castka
    f.termin = _parse_date(vstup.termin)
    f.poznamka = vstup.poznamka or ""
    vs = (vstup.variabilni_symbol or "").strip()
    f.variabilni_symbol = vs or None
    f.upraveno_rucne = True

    db.commit()
    db.refresh(f)
    return _faktura_out(f)


# ---- přidání další faktury projektu ----
@router.post("/projekt/{projekt_id}/faktura", response_model=FakturaOut)
def pridej_fakturu(
    projekt_id: int,
    user: User = Depends(vyzaduj_finance),
    db: Session = Depends(get_db),
):
    if db.get(Projekt, projekt_id) is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    nejvyssi = (
        db.query(Faktura.poradi)
        .filter(Faktura.projekt_id == projekt_id)
        .order_by(Faktura.poradi.desc())
        .first()
    )
    dalsi_poradi = (nejvyssi[0] + 1) if nejvyssi else 1
    f = Faktura(projekt_id=projekt_id, poradi=dalsi_poradi, stav=VYCHOZI_STAV)
    db.add(f)
    db.commit()
    db.refresh(f)
    return _faktura_out(f)


# ---- smazání faktury ----
@router.delete("/faktura/{faktura_id}")
def smaz_fakturu(
    faktura_id: int,
    user: User = Depends(vyzaduj_finance),
    db: Session = Depends(get_db),
):
    f = db.get(Faktura, faktura_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Faktura neexistuje")
    if f.crm_objednavka_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Tahle faktura patří CRM objednávce – smaž ji na kartě objednávky.",
        )
    db.delete(f)
    db.commit()
    return {"stav": "smazano"}


# ---- synchronizace s Pohodou (zatím napojení není aktivní) ----
@router.post("/pohoda/synchronizovat", response_model=PohodaVysledek)
def synchronizuj_pohodu(
    user: User = Depends(vyzaduj_finance),
    db: Session = Depends(get_db),
):
    if not pohoda.je_nakonfigurovano():
        return PohodaVysledek(
            aktivni=False,
            zprava=(
                "Napojení na Pohodu zatím není nakonfigurované. Doplň přístupy "
                "(POHODA_URL, POHODA_LOGIN, POHODA_HESLO, POHODA_ICO) do .env."
            ),
        )

    # Napojení existuje → spáruj faktury podle variabilního symbolu.
    faktury = db.query(Faktura).filter(Faktura.variabilni_symbol.isnot(None)).all()
    vs_seznam = [f.variabilni_symbol for f in faktury]
    stav_dle_vs = pohoda.nacti_faktury_dle_vs(vs_seznam)

    sparovanych = 0
    for f in faktury:
        info = stav_dle_vs.get(f.variabilni_symbol)
        if not info:
            continue
        f.pohoda_potvrzeno = True
        f.pohoda_datum_vystaveni = _parse_date(info.get("datum_vystaveni"))
        f.pohoda_datum_zaplaceni = _parse_date(info.get("datum_zaplaceni"))
        # Automatika nepřepisuje ruční úpravu.
        if not f.upraveno_rucne:
            if info.get("zaplaceno"):
                f.stav = "zaplaceno"
            elif info.get("vystaveno"):
                f.stav = "vystaveno"
        sparovanych += 1

    db.commit()
    return PohodaVysledek(
        aktivni=True,
        zprava=f"Spárováno {sparovanych} faktur podle variabilního symbolu.",
        sparovanych=sparovanych,
    )
