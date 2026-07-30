"""API objednávek, projektů a šablon projektových kroků.

Oddělené od `crm/routes.py`, který už byl dost dlouhý – tady je celá druhá
polovina řetězce: přijatá nabídka → objednávka → projekt s kroky.

DVĚ PRAVIDLA, KTERÁ SE PROLÍNAJÍ VŠÍM:

1. **Projekt nesmí vzniknout samostatně** (zadání Dana). Vždy z objednávky nebo
   z obchodního případu – proto je `obchodni_pripad_id` povinné a při zakládání
   z objednávky se dopočítá z ní.
2. **Viditelnost** se řídí obchodním případem, ke kterému záznam patří.
   Objednávka ani projekt nemají vlastní „soukromí" – jsou to části téže
   zakázky, takže kdo vidí případ, vidí i je.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import ciselne_rady
from app.crm import projekty_kroky as kroky_modul
from app.crm import stavy as stavy_modul
from app.crm import vlastni_pole as pole_modul
from app.crm.models import (
    KATEGORIE_OP,
    STAVY_KROKU,
    CrmProjekt,
    CrmStav,
    CrmStavHistorie,
    Objednavka,
    ObchodniPripad,
    ProjektKrok,
    ProjektSablona,
    ProjektSablonaKrok,
)
from app.crm.pristup import (
    muze_vse,
    vyzaduj_nastaveni,
    vyzaduj_pripady,
)
from app.crm.schemas import (
    KrokOut,
    KrokUprava,
    KrokVstup,
    ObjednavkaDetailOut,
    ObjednavkaRadekOut,
    ObjednavkaVstup,
    ObjednavkaZmenaStavuVstup,
    ProjektDetailOut,
    ProjektRadekOut,
    ProjektUprava,
    ProjektVstup,
    ProjektZmenaStavuVstup,
    SablonaKrokOut,
    SablonaKrokVstup,
    SablonaOut,
    SablonaVstup,
    StavOut,
    VlastniPoleOut,
)
from app.database import get_db

router = APIRouter(prefix="/crm", tags=["crm-realizace"])


# ---- pomocné ----------------------------------------------------------------
def _iso(x) -> str | None:
    return x.isoformat() if x is not None else None


def _num(x) -> float | None:
    return float(x) if x is not None else None


def _jmeno(u: User | None) -> str | None:
    return u.jmeno if u is not None else None


def _datum(hodnota: str | None, pole: str) -> date | None:
    if hodnota is None or str(hodnota).strip() == "":
        return None
    try:
        return date.fromisoformat(str(hodnota)[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Pole {pole} není platné datum (YYYY-MM-DD).")


def _vidi_pripad(db: Session, pripad_id: int, user: User) -> ObchodniPripad:
    """Případ, na který uživatel vidí – jinak 404 (viz `pristup.vyzaduj_zaznam`)."""
    p = db.get(ObchodniPripad, pripad_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Obchodní případ neexistuje")
    if not muze_vse(user):
        if p.vlastnik_user_id != user.id and user.id not in list(p.spoluvlastnici or []):
            raise HTTPException(status_code=404, detail="Obchodní případ neexistuje")
    return p


def _omez_podle_pripadu(q, model, user: User):
    """Filtr viditelnosti pro objednávky/projekty – přes jejich případ."""
    if muze_vse(user):
        return q
    moje = (
        q.session.query(ObchodniPripad.id)
        .filter(
            or_(
                ObchodniPripad.vlastnik_user_id == user.id,
                ObchodniPripad.spoluvlastnici.any(user.id),
            )
        )
        .subquery()
    )
    return q.filter(model.obchodni_pripad_id.in_(q.session.query(moje.c.id)))


def _mapa_stavu(db: Session, entita: str) -> dict[str, CrmStav]:
    return {s.klic: s for s in stavy_modul.seznam(db, entita)}


def _stav_out(s: CrmStav) -> StavOut:
    return StavOut(
        id=s.id, entita=s.entita, klic=s.klic, nazev=s.nazev,
        poradi=s.poradi, barva=s.barva or "", druh=s.druh,
    )


def _vlastnictvi(db: Session, vstup, user: User, zaznam=None):
    """Vlastníka smí přepsat jen ten, kdo vidí všechny záznamy (jako u případů)."""
    spolu = [i for i in dict.fromkeys(vstup.spoluvlastnici or [])]
    nalezeni = {i for (i,) in db.query(User.id).filter(User.id.in_(spolu)).all()} if spolu else set()
    spolu = [i for i in spolu if i in nalezeni]
    if muze_vse(user) and getattr(vstup, "vlastnik_user_id", None) is not None:
        vlastnik = vstup.vlastnik_user_id
    elif zaznam is not None:
        vlastnik = zaznam.vlastnik_user_id
    else:
        vlastnik = user.id
    return vlastnik, [i for i in spolu if i != vlastnik]


# ============================ OBJEDNÁVKY ====================================
def _objednavka_radek(
    db: Session, o: Objednavka, mapa: dict[str, CrmStav], extra_text: dict | None = None
) -> ObjednavkaRadekOut:
    from app.nabidkovac.models import Nabidka

    stav = mapa.get(o.stav)
    nabidka = db.get(Nabidka, o.nabidka_id) if o.nabidka_id else None
    ma_projekt = (
        db.query(CrmProjekt.id).filter(CrmProjekt.objednavka_id == o.id).first() is not None
    )
    return ObjednavkaRadekOut(
        id=o.id,
        cislo=o.cislo,
        nazev=o.nazev or "",
        pripad_id=o.obchodni_pripad_id,
        pripad_cislo=o.pripad.cislo if o.pripad is not None else "",
        zakaznik_nazev=(
            o.pripad.zakaznik.nazev
            if o.pripad is not None and o.pripad.zakaznik is not None
            else ""
        ),
        nabidka_id=o.nabidka_id,
        nabidka_cislo=(nabidka.cislo or "") if nabidka is not None else "",
        cena_kc=_num(o.cena_kc),
        datum_podpisu=_iso(o.datum_podpisu),
        datum_dodani=_iso(o.datum_dodani),
        stav=o.stav,
        stav_nazev=stav.nazev if stav is not None else o.stav,
        vlastnik_jmeno=_jmeno(o.vlastnik),
        ma_projekt=ma_projekt,
        vytvoreno_at=_iso(o.vytvoreno_at),
        extra_text=extra_text or {},
    )


def _objednavka_detail(db: Session, o: Objednavka, user: User) -> ObjednavkaDetailOut:
    zaklad = _objednavka_radek(db, o, _mapa_stavu(db, "obj")).model_dump()
    zaklad.pop("extra_text", None)
    projekt = db.query(CrmProjekt).filter(CrmProjekt.objednavka_id == o.id).first()
    return ObjednavkaDetailOut(
        **zaklad,
        extra_text={},
        popis=o.popis or "",
        duvod_zruseni=o.duvod_zruseni or "",
        vlastnik_user_id=o.vlastnik_user_id,
        spoluvlastnici=list(o.spoluvlastnici or []),
        extra=o.extra or {},
        vlastni_pole=[VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, "obj")],
        projekt_id=projekt.id if projekt is not None else None,
        projekt_cislo=projekt.cislo if projekt is not None else "",
        muze_editovat=True,
    )


def _cena_z_nabidky(db: Session, nabidka_id: int | None) -> float | None:
    """Vytáhne z posledního řešení nabídky cenu, kterou má smysl dát na objednávku.

    Peak shaving má investici do baterie (`doporucena.cena_celkem_kc`). PPA je
    investice Greensie, ne zákazníka – tam cenu nedoplňujeme, protože zákazník
    platí za dodanou elektřinu, ne za elektrárnu. Když nic nenajdeme, vrátíme
    None a obchodník cenu doplní ručně; hádat by bylo horší.
    """
    if nabidka_id is None:
        return None
    from app.nabidkovac.models import NavrhovaneReseni

    reseni = (
        db.query(NavrhovaneReseni)
        .filter(NavrhovaneReseni.nabidka_id == nabidka_id)
        .order_by(NavrhovaneReseni.id.desc())
        .first()
    )
    if reseni is None:
        return None
    popis = reseni.popis_json or {}
    if reseni.typ_reseni == "peak_shaving":
        hodnota = (popis.get("doporucena") or {}).get("cena_celkem_kc")
        try:
            return float(hodnota) if hodnota is not None else None
        except (TypeError, ValueError):
            return None
    return None


@router.get("/objednavky", response_model=list[ObjednavkaRadekOut])
def seznam_objednavek(
    hledat: str | None = Query(default=None),
    pripad_id: int | None = Query(default=None),
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    q = db.query(Objednavka)
    if pripad_id is not None:
        q = q.filter(Objednavka.obchodni_pripad_id == pripad_id)
    if hledat:
        vzor = f"%{hledat.strip()}%"
        q = q.filter(or_(Objednavka.cislo.ilike(vzor), Objednavka.nazev.ilike(vzor)))
    q = _omez_podle_pripadu(q, Objednavka, user)
    objednavky = q.order_by(Objednavka.cislo.desc()).all()
    mapa = _mapa_stavu(db, "obj")
    texty = pole_modul.hodnoty_pro_seznam(db, "obj", objednavky)
    return [_objednavka_radek(db, o, mapa, texty.get(o.id)) for o in objednavky]


@router.get("/objednavky/kanban")
def kanban_objednavek(
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    q = _omez_podle_pripadu(db.query(Objednavka), Objednavka, user)
    objednavky = q.order_by(Objednavka.cislo.desc()).all()
    seznam_stavu = stavy_modul.seznam(db, "obj")
    mapa = {s.klic: s for s in seznam_stavu}
    texty = pole_modul.hodnoty_pro_seznam(db, "obj", objednavky)

    koše: dict[str, list] = {s.klic: [] for s in seznam_stavu}
    for o in objednavky:
        klic = o.stav if o.stav in koše else (seznam_stavu[0].klic if seznam_stavu else None)
        if klic:
            koše[klic].append(o)

    return {
        "entita": "obj",
        "sloupce": [
            {
                "stav": _stav_out(s).model_dump(),
                "zaznamy": [
                    _objednavka_radek(db, o, mapa, texty.get(o.id)).model_dump()
                    for o in koše.get(s.klic, [])
                ],
                "pocet": len(koše.get(s.klic, [])),
                "soucet_kc": sum(float(o.cena_kc) for o in koše.get(s.klic, []) if o.cena_kc)
                or None,
            }
            for s in seznam_stavu
        ],
    }


@router.post("/objednavky", response_model=ObjednavkaDetailOut)
def zaloz_objednavku(
    vstup: ObjednavkaVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Založí objednávku – obvykle z přijaté nabídky, jejíž cenu převezme.

    Případ se dá určit buď přímo, nebo se dopočítá z nabídky; bez jednoho z toho
    by objednávka visela ve vzduchu a nešla dohledat u zákazníka.
    """
    from app.nabidkovac.models import Nabidka

    nabidka = db.get(Nabidka, vstup.nabidka_id) if vstup.nabidka_id else None
    if nabidka is None and vstup.nabidka_id:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")

    pripad_id = vstup.obchodni_pripad_id or (nabidka.obchodni_pripad_id if nabidka else None)
    if pripad_id is None:
        raise HTTPException(
            status_code=422,
            detail="Objednávka musí patřit k obchodnímu případu (vyber případ nebo nabídku).",
        )
    pripad = _vidi_pripad(db, pripad_id, user)

    vlastnik, spolu = _vlastnictvi(db, vstup, user)
    cena = vstup.cena_kc if vstup.cena_kc is not None else _cena_z_nabidky(db, vstup.nabidka_id)
    stav = stavy_modul.vychozi_klic(db, "obj")

    o = Objednavka(
        cislo=ciselne_rady.dalsi_cislo(db, "obj"),
        obchodni_pripad_id=pripad.id,
        nabidka_id=vstup.nabidka_id,
        nazev=(vstup.nazev or "").strip() or (pripad.nazev or ""),
        popis=vstup.popis or "",
        cena_kc=cena,
        datum_podpisu=_datum(vstup.datum_podpisu, "datum podpisu"),
        datum_dodani=_datum(vstup.datum_dodani, "datum dodání"),
        stav=stav,
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        extra=pole_modul.zpracuj(db, "obj", vstup.extra),
        vytvoril_user_id=user.id,
    )
    db.add(o)
    db.flush()
    db.add(
        CrmStavHistorie(
            entita="obj", zaznam_id=o.id, ze_stavu=None, do_stavu=stav, zmenil_user_id=user.id
        )
    )
    db.commit()
    db.refresh(o)
    return _objednavka_detail(db, o, user)


@router.get("/objednavky/{objednavka_id}", response_model=ObjednavkaDetailOut)
def detail_objednavky(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    o = db.get(Objednavka, objednavka_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")
    _vidi_pripad(db, o.obchodni_pripad_id, user)
    return _objednavka_detail(db, o, user)


@router.put("/objednavky/{objednavka_id}", response_model=ObjednavkaDetailOut)
def uprav_objednavku(
    objednavka_id: int,
    vstup: ObjednavkaVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    o = db.get(Objednavka, objednavka_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")
    _vidi_pripad(db, o.obchodni_pripad_id, user)

    vlastnik, spolu = _vlastnictvi(db, vstup, user, zaznam=o)
    o.nazev = (vstup.nazev or "").strip()
    o.popis = vstup.popis or ""
    o.cena_kc = vstup.cena_kc
    o.datum_podpisu = _datum(vstup.datum_podpisu, "datum podpisu")
    o.datum_dodani = _datum(vstup.datum_dodani, "datum dodání")
    o.vlastnik_user_id = vlastnik
    o.spoluvlastnici = spolu
    o.extra = pole_modul.zpracuj(db, "obj", vstup.extra)
    db.commit()
    db.refresh(o)
    return _objednavka_detail(db, o, user)


@router.post("/objednavky/{objednavka_id}/stav", response_model=ObjednavkaDetailOut)
def zmen_stav_objednavky(
    objednavka_id: int,
    vstup: ObjednavkaZmenaStavuVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Přesun objednávky. U zrušení se vyžaduje důvod – stejná logika jako
    u prohraného případu: bez důvodu je statistika k ničemu."""
    o = db.get(Objednavka, objednavka_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")
    _vidi_pripad(db, o.obchodni_pripad_id, user)

    novy = stavy_modul.najdi(db, "obj", vstup.stav)
    if novy is None:
        raise HTTPException(status_code=422, detail=f"Stav '{vstup.stav}' neexistuje.")
    duvod = (vstup.duvod_zruseni or "").strip()
    if novy.druh == "prohra" and not duvod and not (o.duvod_zruseni or "").strip():
        raise HTTPException(status_code=422, detail="U zrušené objednávky uveď důvod.")

    puvodni = o.stav
    o.stav = novy.klic
    if duvod:
        o.duvod_zruseni = duvod
    o.uzavreno_at = datetime.now() if novy.druh in ("vyhra", "prohra") else None
    if novy.druh == "vyhra":
        o.duvod_zruseni = ""
    if puvodni != novy.klic:
        db.add(
            CrmStavHistorie(
                entita="obj", zaznam_id=o.id, ze_stavu=puvodni,
                do_stavu=novy.klic, zmenil_user_id=user.id,
            )
        )
    db.commit()
    db.refresh(o)
    return _objednavka_detail(db, o, user)


@router.delete("/objednavky/{objednavka_id}")
def smaz_objednavku(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Objednávku s projektem smazat nelze – projekt by osiřel a přišel by
    o vazbu na to, z čeho realizace vznikla."""
    o = db.get(Objednavka, objednavka_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")
    _vidi_pripad(db, o.obchodni_pripad_id, user)
    pocet = db.query(func.count(CrmProjekt.id)).filter(CrmProjekt.objednavka_id == o.id).scalar()
    if int(pocet or 0) > 0:
        raise HTTPException(
            status_code=409, detail="Z objednávky vznikl projekt – nejdřív smaž projekt."
        )
    db.query(CrmStavHistorie).filter(
        CrmStavHistorie.entita == "obj", CrmStavHistorie.zaznam_id == o.id
    ).delete(synchronize_session=False)
    db.delete(o)
    db.commit()
    return {"ok": True}


# ============================== PROJEKTY ====================================
def _krok_out(k: ProjektKrok, mapa: dict[int, ProjektKrok]) -> KrokOut:
    predchudce = mapa.get(k.zavisi_na_id) if k.zavisi_na_id else None
    return KrokOut(
        id=k.id,
        nazev=k.nazev,
        popis=k.popis or "",
        poradi=k.poradi,
        stav=k.stav,
        delka_dni=k.delka_dni,
        zavisi_na_id=k.zavisi_na_id,
        zavisi_na_nazev=predchudce.nazev if predchudce is not None else "",
        termin=_iso(k.termin),
        termin_rucne=bool(k.termin_rucne),
        hotovo_at=_iso(k.hotovo_at),
        odpovedny_user_id=k.odpovedny_user_id,
        odpovedny_jmeno=_jmeno(k.odpovedny),
        dostupny=kroky_modul.dostupny(k, mapa),
        po_terminu=bool(
            k.termin and k.stav not in ("hotovo", "preskoceno") and k.termin < date.today()
        ),
    )


def _projekt_radek(
    p: CrmProjekt, mapa: dict[str, CrmStav], extra_text: dict | None = None
) -> ProjektRadekOut:
    stav = mapa.get(p.stav)
    s = kroky_modul.souhrn(p)
    return ProjektRadekOut(
        id=p.id,
        cislo=p.cislo,
        nazev=p.nazev or "",
        pripad_id=p.obchodni_pripad_id,
        pripad_cislo=p.pripad.cislo if p.pripad is not None else "",
        zakaznik_nazev=(
            p.pripad.zakaznik.nazev
            if p.pripad is not None and p.pripad.zakaznik is not None
            else ""
        ),
        objednavka_cislo=p.objednavka.cislo if p.objednavka is not None else "",
        stav=p.stav,
        stav_nazev=stav.nazev if stav is not None else p.stav,
        zahajeni=_iso(p.zahajeni),
        predani=_iso(p.predani),
        vlastnik_jmeno=_jmeno(p.vlastnik),
        kroku=s["kroku"],
        hotovo=s["hotovo"],
        procent=s["procent"],
        nejblizsi_termin=s["nejblizsi_termin"],
        po_terminu=s["po_terminu"],
        freelo_projekt_id=p.freelo_projekt_id,
        vytvoreno_at=_iso(p.vytvoreno_at),
        extra_text=extra_text or {},
    )


def _projekt_detail(db: Session, p: CrmProjekt, user: User) -> ProjektDetailOut:
    zaklad = _projekt_radek(p, _mapa_stavu(db, "pro")).model_dump()
    zaklad.pop("extra_text", None)
    kroky = sorted(p.kroky or [], key=lambda k: (k.poradi, k.id))
    mapa_kroku = {k.id: k for k in kroky}
    return ProjektDetailOut(
        **zaklad,
        extra_text={},
        popis=p.popis or "",
        objednavka_id=p.objednavka_id,
        vlastnik_user_id=p.vlastnik_user_id,
        spoluvlastnici=list(p.spoluvlastnici or []),
        extra=p.extra or {},
        vlastni_pole=[VlastniPoleOut(**x) for x in pole_modul.pro_frontend(db, "pro")],
        kroky_seznam=[_krok_out(k, mapa_kroku) for k in kroky],
        muze_editovat=True,
    )


@router.get("/projekty", response_model=list[ProjektRadekOut])
def seznam_projektu(
    hledat: str | None = Query(default=None),
    pripad_id: int | None = Query(default=None),
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    q = db.query(CrmProjekt)
    if pripad_id is not None:
        q = q.filter(CrmProjekt.obchodni_pripad_id == pripad_id)
    if hledat:
        vzor = f"%{hledat.strip()}%"
        q = q.filter(or_(CrmProjekt.cislo.ilike(vzor), CrmProjekt.nazev.ilike(vzor)))
    q = _omez_podle_pripadu(q, CrmProjekt, user)
    projekty = q.order_by(CrmProjekt.cislo.desc()).all()
    mapa = _mapa_stavu(db, "pro")
    texty = pole_modul.hodnoty_pro_seznam(db, "pro", projekty)
    return [_projekt_radek(p, mapa, texty.get(p.id)) for p in projekty]


@router.get("/projekty/kanban")
def kanban_projektu(
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    q = _omez_podle_pripadu(db.query(CrmProjekt), CrmProjekt, user)
    projekty = q.order_by(CrmProjekt.cislo.desc()).all()
    seznam_stavu = stavy_modul.seznam(db, "pro")
    mapa = {s.klic: s for s in seznam_stavu}
    texty = pole_modul.hodnoty_pro_seznam(db, "pro", projekty)

    koše: dict[str, list] = {s.klic: [] for s in seznam_stavu}
    for p in projekty:
        klic = p.stav if p.stav in koše else (seznam_stavu[0].klic if seznam_stavu else None)
        if klic:
            koše[klic].append(p)

    return {
        "entita": "pro",
        "sloupce": [
            {
                "stav": _stav_out(s).model_dump(),
                "zaznamy": [
                    _projekt_radek(p, mapa, texty.get(p.id)).model_dump()
                    for p in koše.get(s.klic, [])
                ],
                "pocet": len(koše.get(s.klic, [])),
            }
            for s in seznam_stavu
        ],
    }


@router.post("/projekty", response_model=ProjektDetailOut)
def zaloz_projekt(
    vstup: ProjektVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Založí projekt Z OBJEDNÁVKY nebo Z PŘÍPADU – samostatně vzniknout nesmí.

    Číslo kopíruje případ (`PRO-26-0301` k `OP-26-0301`); druhý projekt téhož
    případu dostane suffix, jinak by dvě realizace nesly stejné číslo.
    Volitelně se hned rozbalí šablona kroků a dopočítají termíny.
    """
    objednavka = db.get(Objednavka, vstup.objednavka_id) if vstup.objednavka_id else None
    if vstup.objednavka_id and objednavka is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")

    pripad_id = vstup.obchodni_pripad_id or (
        objednavka.obchodni_pripad_id if objednavka is not None else None
    )
    if pripad_id is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Projekt nelze založit samostatně – musí vzniknout z objednávky "
                "nebo z obchodního případu."
            ),
        )
    pripad = _vidi_pripad(db, pripad_id, user)

    pocet_existujicich = (
        db.query(func.count(CrmProjekt.id))
        .filter(CrmProjekt.obchodni_pripad_id == pripad.id)
        .scalar()
    )
    vlastnik, spolu = _vlastnictvi(db, vstup, user)
    stav = stavy_modul.vychozi_klic(db, "pro")

    p = CrmProjekt(
        cislo=ciselne_rady.cislo_projektu(db, pripad, int(pocet_existujicich or 0)),
        obchodni_pripad_id=pripad.id,
        objednavka_id=vstup.objednavka_id,
        nazev=(vstup.nazev or "").strip() or (pripad.nazev or ""),
        popis=vstup.popis or "",
        stav=stav,
        zahajeni=_datum(vstup.zahajeni, "zahájení") or date.today(),
        predani=_datum(vstup.predani, "předání"),
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        extra=pole_modul.zpracuj(db, "pro", vstup.extra),
        vytvoril_user_id=user.id,
    )
    db.add(p)
    db.flush()
    db.add(
        CrmStavHistorie(
            entita="pro", zaznam_id=p.id, ze_stavu=None, do_stavu=stav, zmenil_user_id=user.id
        )
    )

    if vstup.sablona_id:
        sablona = db.get(ProjektSablona, vstup.sablona_id)
        if sablona is None:
            raise HTTPException(status_code=404, detail="Šablona neexistuje")
        kroky_modul.rozbal_sablonu(db, p, sablona)
        db.refresh(p)
        kroky_modul.prepocitej_terminy(db, p)

    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.get("/projekty/{projekt_id}", response_model=ProjektDetailOut)
def detail_projektu(
    projekt_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    return _projekt_detail(db, p, user)


@router.put("/projekty/{projekt_id}", response_model=ProjektDetailOut)
def uprav_projekt(
    projekt_id: int,
    vstup: ProjektUprava,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Úprava projektu. Změna zahájení PŘEPOČÍTÁ termíny kroků – v tom je celá
    hodnota návazností: posun startu se propíše do celé realizace."""
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)

    vlastnik, spolu = _vlastnictvi(db, vstup, user, zaznam=p)
    puvodni_zahajeni = p.zahajeni
    p.nazev = (vstup.nazev or "").strip()
    p.popis = vstup.popis or ""
    p.zahajeni = _datum(vstup.zahajeni, "zahájení")
    p.predani = _datum(vstup.predani, "předání")
    p.freelo_projekt_id = vstup.freelo_projekt_id
    p.vlastnik_user_id = vlastnik
    p.spoluvlastnici = spolu
    p.extra = pole_modul.zpracuj(db, "pro", vstup.extra)
    db.flush()
    if p.zahajeni != puvodni_zahajeni:
        kroky_modul.prepocitej_terminy(db, p)
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.post("/projekty/{projekt_id}/stav", response_model=ProjektDetailOut)
def zmen_stav_projektu(
    projekt_id: int,
    vstup: ProjektZmenaStavuVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    novy = stavy_modul.najdi(db, "pro", vstup.stav)
    if novy is None:
        raise HTTPException(status_code=422, detail=f"Stav '{vstup.stav}' neexistuje.")
    puvodni = p.stav
    p.stav = novy.klic
    p.uzavreno_at = datetime.now() if novy.druh in ("vyhra", "prohra") else None
    if puvodni != novy.klic:
        db.add(
            CrmStavHistorie(
                entita="pro", zaznam_id=p.id, ze_stavu=puvodni,
                do_stavu=novy.klic, zmenil_user_id=user.id,
            )
        )
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.post("/projekty/{projekt_id}/sablona/{sablona_id}", response_model=ProjektDetailOut)
def pouzij_sablonu(
    projekt_id: int,
    sablona_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Rozbalí šablonu do kroků projektu (přidává, existující kroky nemaže)."""
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    sablona = db.get(ProjektSablona, sablona_id)
    if sablona is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    kroky_modul.rozbal_sablonu(db, p, sablona)
    db.refresh(p)
    kroky_modul.prepocitej_terminy(db, p)
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.delete("/projekty/{projekt_id}")
def smaz_projekt(
    projekt_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    db.query(CrmStavHistorie).filter(
        CrmStavHistorie.entita == "pro", CrmStavHistorie.zaznam_id == p.id
    ).delete(synchronize_session=False)
    db.delete(p)  # kroky odejdou s ním (cascade)
    db.commit()
    return {"ok": True}


# ---- kroky projektu ---------------------------------------------------------
@router.post("/projekty/{projekt_id}/kroky", response_model=ProjektDetailOut)
def pridej_krok(
    projekt_id: int,
    vstup: KrokVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = db.get(CrmProjekt, projekt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Projekt neexistuje")
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kroku je povinný.")

    posledni = (
        db.query(func.max(ProjektKrok.poradi)).filter(ProjektKrok.projekt_id == p.id).scalar()
    )
    rucni_termin = _datum(vstup.termin, "termín")
    k = ProjektKrok(
        projekt_id=p.id,
        nazev=nazev,
        popis=vstup.popis or "",
        poradi=int(posledni or -1) + 1,
        delka_dni=max(1, int(vstup.delka_dni or 1)),
        zavisi_na_id=vstup.zavisi_na_id,
        termin=rucni_termin,
        termin_rucne=rucni_termin is not None,
        odpovedny_user_id=vstup.odpovedny_user_id,
    )
    db.add(k)
    db.flush()
    db.refresh(p)
    kroky_modul.prepocitej_terminy(db, p)
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.patch("/kroky/{krok_id}", response_model=ProjektDetailOut)
def uprav_krok(
    krok_id: int,
    vstup: KrokUprava,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Úprava kroku. Dokončení kroku PŘEPOČÍTÁ termíny navazujících – to je
    jádro celé věci: když se krok zdrží, posunou se kroky za ním."""
    k = db.get(ProjektKrok, krok_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Krok neexistuje")
    p = db.get(CrmProjekt, k.projekt_id)
    _vidi_pripad(db, p.obchodni_pripad_id, user)

    if vstup.nazev is not None:
        nazev = vstup.nazev.strip()
        if not nazev:
            raise HTTPException(status_code=422, detail="Název kroku nesmí být prázdný.")
        k.nazev = nazev
    if vstup.popis is not None:
        k.popis = vstup.popis
    if vstup.delka_dni is not None:
        k.delka_dni = max(1, int(vstup.delka_dni))
    if vstup.zavisi_na_id is not None:
        # Krok nesmí záviset sám na sobě – vznikl by cyklus a termín by nešel spočítat.
        if vstup.zavisi_na_id == k.id:
            raise HTTPException(status_code=422, detail="Krok nemůže navazovat sám na sebe.")
        k.zavisi_na_id = vstup.zavisi_na_id or None
    if vstup.termin is not None:
        novy_termin = _datum(vstup.termin, "termín")
        k.termin = novy_termin
        # Prázdný termín = vrátit krok do automatického dopočtu.
        k.termin_rucne = novy_termin is not None
    if vstup.odpovedny_user_id is not None:
        k.odpovedny_user_id = vstup.odpovedny_user_id or None
    if vstup.stav is not None:
        if vstup.stav not in STAVY_KROKU:
            raise HTTPException(status_code=422, detail=f"Neznámý stav kroku: {vstup.stav}")
        k.stav = vstup.stav
        k.hotovo_at = datetime.now() if vstup.stav in ("hotovo", "preskoceno") else None

    db.flush()
    db.refresh(p)
    kroky_modul.prepocitej_terminy(db, p)
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


@router.delete("/kroky/{krok_id}", response_model=ProjektDetailOut)
def smaz_krok(
    krok_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    k = db.get(ProjektKrok, krok_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Krok neexistuje")
    p = db.get(CrmProjekt, k.projekt_id)
    _vidi_pripad(db, p.obchodni_pripad_id, user)
    # Kroky, které na mazaném závisely, se odvěsí (SET NULL by řešila DB, ale
    # chceme mít i v session čistý stav pro přepočet).
    for jiny in p.kroky or []:
        if jiny.zavisi_na_id == k.id:
            jiny.zavisi_na_id = None
    db.delete(k)
    db.flush()
    db.refresh(p)
    kroky_modul.prepocitej_terminy(db, p)
    db.commit()
    db.refresh(p)
    return _projekt_detail(db, p, user)


# ---- šablony projektových kroků ---------------------------------------------
def _sablona_out(s: ProjektSablona) -> SablonaOut:
    return SablonaOut(
        id=s.id,
        nazev=s.nazev,
        popis=s.popis or "",
        kategorie=list(s.kategorie or []),
        kroky=[
            SablonaKrokOut(
                id=k.id, nazev=k.nazev, popis=k.popis or "", poradi=k.poradi,
                delka_dni=k.delka_dni, zavisi_na_poradi=k.zavisi_na_poradi,
            )
            for k in sorted(s.kroky, key=lambda x: (x.poradi, x.id))
        ],
    )


@router.get("/sablony", response_model=list[SablonaOut])
def seznam_sablon(
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Šablony kroků. Čtení stačí právo na případy – vybírá se z nich při
    zakládání projektu; měnit je smí jen `crm_nastaveni`."""
    return [
        _sablona_out(s) for s in db.query(ProjektSablona).order_by(ProjektSablona.nazev).all()
    ]


@router.post("/sablony", response_model=SablonaOut)
def pridej_sablonu(
    vstup: SablonaVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název šablony je povinný.")
    neznama = [k for k in (vstup.kategorie or []) if k not in KATEGORIE_OP]
    if neznama:
        raise HTTPException(status_code=422, detail=f"Neznámá kategorie: {', '.join(neznama)}")
    if db.query(ProjektSablona.id).filter(ProjektSablona.nazev == nazev).first():
        raise HTTPException(status_code=409, detail="Šablona s tímto názvem už existuje.")
    s = ProjektSablona(
        nazev=nazev, popis=vstup.popis or "", kategorie=list(vstup.kategorie or []),
        vytvoril_user_id=user.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sablona_out(s)


@router.post("/sablony/{sablona_id}/kroky", response_model=SablonaOut)
def pridej_krok_sablony(
    sablona_id: int,
    vstup: SablonaKrokVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    s = db.get(ProjektSablona, sablona_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kroku je povinný.")
    posledni = (
        db.query(func.max(ProjektSablonaKrok.poradi))
        .filter(ProjektSablonaKrok.sablona_id == s.id)
        .scalar()
    )
    db.add(
        ProjektSablonaKrok(
            sablona_id=s.id,
            nazev=nazev,
            popis=vstup.popis or "",
            poradi=int(posledni or -1) + 1,
            delka_dni=max(1, int(vstup.delka_dni or 1)),
            zavisi_na_poradi=vstup.zavisi_na_poradi,
        )
    )
    db.commit()
    db.refresh(s)
    return _sablona_out(s)


@router.delete("/sablony/kroky/{krok_id}", response_model=SablonaOut)
def smaz_krok_sablony(
    krok_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    k = db.get(ProjektSablonaKrok, krok_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Krok šablony neexistuje")
    s = db.get(ProjektSablona, k.sablona_id)
    # Kroky, které na mazaném závisely (podle pořadí), se odvěsí.
    for jiny in s.kroky:
        if jiny.zavisi_na_poradi == k.poradi:
            jiny.zavisi_na_poradi = None
    db.delete(k)
    db.commit()
    db.refresh(s)
    return _sablona_out(s)


@router.delete("/sablony/{sablona_id}")
def smaz_sablonu(
    sablona_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Smaže šablonu. Projekty, které z ní vznikly, zůstávají nedotčené –
    kroky se do nich zkopírovaly, nejsou na šablonu navázané."""
    s = db.get(ProjektSablona, sablona_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    db.delete(s)
    db.commit()
    return {"ok": True}
