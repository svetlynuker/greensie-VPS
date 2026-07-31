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
from app.crm import automatizace as automatizace_modul
from app.crm import ciselne_rady
from app.crm import fakturace as fakturace_modul
from app.crm import kategorie as kategorie_modul
from app.crm import projekty_kroky as kroky_modul
from app.crm import stavy as stavy_modul
from app.crm import notifikace as notifikace_modul
from app.crm import vlastni_pole as pole_modul
from app.crm.models import (
    ENTITY_FILTRU,
    STAVY_KROKU,
    CrmUlozenyFiltr,
    CrmProjekt,
    CrmStav,
    CrmStavHistorie,
    Objednavka,
    ObjednavkaPolozka,
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
from app.finance.models import STAVY_FAKTURY, VYCHOZI_STAV as VYCHOZI_STAV_FAKTURY, Faktura
from app.nabidkovac import polozky as polozky_modul
from app.nabidkovac.permissions import muze_katalog
from app.nabidkovac.schemas import PolozkyVstup
from app.crm.schemas import (
    FakturaOut,
    FakturaVstup,
    FakturaceOut,
    FakturaceSouhrn,
    KrokOut,
    KrokUprava,
    KrokVstup,
    ObjednavkaDetailOut,
    ObjednavkaRadekOut,
    ObjednavkaVstup,
    ObjednavkaZmenaStavuVstup,
    SplatkovaSablonaOut,
    SplatkyZeSablonyVstup,
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
    UlozenyFiltrOut,
    UlozenyFiltrVstup,
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
    soucet = polozky_modul.souhrn(list(o.polozky))
    return ObjednavkaDetailOut(
        **zaklad,
        extra_text={},
        popis=o.popis or "",
        duvod_zruseni=o.duvod_zruseni or "",
        vlastnik_user_id=o.vlastnik_user_id,
        spoluvlastnici=list(o.spoluvlastnici or []),
        extra=pole_modul.s_vypocty(db, "obj", o, o.extra),
        vlastni_pole=[VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, "obj")],
        projekt_id=projekt.id if projekt is not None else None,
        projekt_cislo=projekt.cislo if projekt is not None else "",
        muze_editovat=True,
        cena_rucni=bool(o.cena_rucni),
        soucet_polozek_kc=soucet["bez_dph"] if o.polozky else None,
        fakturace=FakturaceSouhrn(**fakturace_modul.souhrn(list(o.faktury), o.cena_kc)),
    )


def _srovnej_cenu_objednavky(o: Objednavka) -> None:
    """Po změně rozpisu přepíše cenu objednávky součtem – pokud není ruční.

    Rozhodnutí Dana z 31. 7. 2026: cena se počítá ze součtu položek, ale ruční
    přepis (dohodnutá sleva „za kulatých 2,4 mil.“) má přednost a appka pak
    jen ukáže, o kolik se od součtu liší.
    """
    if o.cena_rucni:
        return
    o.cena_kc = polozky_modul.souhrn(list(o.polozky))["bez_dph"] if o.polozky else None


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

    # CRM-08: rozpis z nabídky se PŘEKLOPÍ (zkopíruje), ne naváže – objednávka
    # je obchodní dokument a nesmí se měnit, když někdo přepočítá nabídku.
    if nabidka is not None and nabidka.polozky:
        for p in nabidka.polozky:
            db.add(polozky_modul.kopiruj(p, ObjednavkaPolozka, objednavka_id=o.id))
        db.flush()
        db.refresh(o)
        # Cena ze součtu rozpisu; ruční zůstane jen tehdy, když ji obchodník
        # při zakládání vyplnil jinou.
        soucet = polozky_modul.souhrn(list(o.polozky))["bez_dph"]
        if vstup.cena_kc is None:
            o.cena_kc = soucet
            o.cena_rucni = False
        else:
            o.cena_rucni = abs(float(vstup.cena_kc) - soucet) > 0.5
    else:
        # Bez rozpisu je cena vždycky ruční (opsaná z výpočtu nebo od člověka) –
        # jinak by ji první uložení prázdného rozpisu přepsalo na nic.
        o.cena_rucni = o.cena_kc is not None

    db.add(
        CrmStavHistorie(
            entita="obj", zaznam_id=o.id, ze_stavu=None, do_stavu=stav, zmenil_user_id=user.id
        )
    )
    # CRM-31: pravidla navěšená na „vznikla nová objednávka“.
    automatizace_modul.po_vzniku(db, "obj", o, user)
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
    # Jen nově přibylí vlastníci – viz notifikace.ohlas_prirazeni.
    drivejsi = {o.vlastnik_user_id, *(o.spoluvlastnici or [])}
    pribyli = [i for i in [vlastnik, *spolu] if i and i not in drivejsi]
    o.nazev = (vstup.nazev or "").strip()
    o.popis = vstup.popis or ""
    # Cena z formuláře je ruční zásah – kromě případu, kdy se rovná součtu
    # rozpisu (uživatel ji nesahal, jen odeslal formulář, kde byla předvyplněná).
    soucet = polozky_modul.souhrn(list(o.polozky))["bez_dph"] if o.polozky else None
    o.cena_kc = vstup.cena_kc
    if vstup.cena_rucni is not None:
        o.cena_rucni = vstup.cena_rucni
    elif o.polozky:
        o.cena_rucni = vstup.cena_kc is not None and abs((vstup.cena_kc or 0) - (soucet or 0)) > 0.5
    o.datum_podpisu = _datum(vstup.datum_podpisu, "datum podpisu")
    o.datum_dodani = _datum(vstup.datum_dodani, "datum dodání")
    o.vlastnik_user_id = vlastnik
    o.spoluvlastnici = spolu
    o.extra = pole_modul.zpracuj(db, "obj", vstup.extra)
    notifikace_modul.ohlas_prirazeni(
        db, user, f"{o.cislo} · {o.nazev}".strip(" ·"), "/objednavky", pribyli
    )
    # CRM-31: změna pole (např. doplněné datum podpisu). Před commitem — viz
    # `po_zmene_poli`.
    automatizace_modul.po_zmene_poli(db, "obj", o, user)
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
        notifikace_modul.ohlas_zmenu_stavu(
            db, user, f"{o.cislo} · {o.nazev}".strip(" ·"), "/objednavky",
            novy.nazev, o.vlastnik_user_id, o.spoluvlastnici,
        )
        # CRM-31: typicky „objednávka podepsaná → projekt ze šablony".
        automatizace_modul.po_zmene_stavu(db, "obj", o, novy.klic, user)
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


# ==================== ROZPIS POLOŽEK OBJEDNÁVKY (CRM-08) ====================
def _objednavka_pro_polozky(db: Session, objednavka_id: int, user: User) -> Objednavka:
    o = db.get(Objednavka, objednavka_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Objednávka neexistuje")
    _vidi_pripad(db, o.obchodni_pripad_id, user)
    return o


def _rozpis_out(o: Objednavka, user: User) -> dict:
    s_nakupem = muze_katalog(user)
    return {
        "polozky": [polozky_modul.polozka_out(p, s_nakupem) for p in o.polozky],
        "souhrn": polozky_modul.souhrn(list(o.polozky)),
        "vidi_nakup": s_nakupem,
        # Frontend podle toho pozná, jestli smí přepsat cenu objednávky.
        "cena_kc": _num(o.cena_kc),
        "cena_rucni": bool(o.cena_rucni),
    }


@router.get("/objednavky/{objednavka_id}/polozky")
def rozpis_objednavky(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    return _rozpis_out(_objednavka_pro_polozky(db, objednavka_id, user), user)


@router.put("/objednavky/{objednavka_id}/polozky")
def uloz_rozpis_objednavky(
    objednavka_id: int,
    vstup: PolozkyVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Uloží celý rozpis objednávky a srovná cenu (pokud není ruční)."""
    o = _objednavka_pro_polozky(db, objednavka_id, user)
    if not muze_katalog(user):
        for radek in vstup.polozky:
            radek.nakup_jednotkovy = None

    polozky_modul.uloz_rozpis(
        db,
        vstup,
        list(o.polozky),
        lambda: ObjednavkaPolozka(objednavka_id=objednavka_id, nazev=""),
    )
    db.flush()
    db.refresh(o)
    _srovnej_cenu_objednavky(o)
    db.commit()
    db.refresh(o)
    return _rozpis_out(o, user)


@router.post("/objednavky/{objednavka_id}/polozky/z-katalogu")
def pridej_polozky_objednavky(
    objednavka_id: int,
    ids: list[int],
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Přidá na konec rozpisu položky vybrané z katalogu (množství 1)."""
    from app.nabidkovac.models import Technologie

    o = _objednavka_pro_polozky(db, objednavka_id, user)
    if not ids:
        return _rozpis_out(o, user)

    nalezene = {t.id: t for t in db.query(Technologie).filter(Technologie.id.in_(ids)).all()}
    dalsi = max((p.poradi for p in o.polozky), default=-1) + 1
    for i, tid in enumerate(ids):
        t = nalezene.get(tid)
        if t is None:
            continue
        p = ObjednavkaPolozka(
            objednavka_id=objednavka_id, nazev=t.nazev, poradi=dalsi + i, mnozstvi=1
        )
        polozky_modul.napln_z_katalogu(p, t)
        db.add(p)

    db.flush()
    db.refresh(o)
    _srovnej_cenu_objednavky(o)
    db.commit()
    db.refresh(o)
    return _rozpis_out(o, user)


@router.post("/objednavky/{objednavka_id}/polozky/z-nabidky")
def prekloop_rozpis_z_nabidky(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Dotáhne rozpis z nabídky, ze které objednávka vznikla.

    Existuje pro případ, kdy rozpis vznikl na nabídce až PO založení
    objednávky. Ke stávajícímu rozpisu se položky přidají za, nic se nemaže –
    zahodit cizí práci bez zeptání by bylo horší než duplicitní řádek.
    """
    o = _objednavka_pro_polozky(db, objednavka_id, user)
    if not o.nabidka_id:
        raise HTTPException(
            status_code=422, detail="Objednávka nevznikla z nabídky – není odkud rozpis vzít."
        )
    from app.nabidkovac.models import Nabidka

    nabidka = db.get(Nabidka, o.nabidka_id)
    if nabidka is None or not nabidka.polozky:
        raise HTTPException(status_code=422, detail="Nabídka žádný rozpis položek nemá.")

    dalsi = max((p.poradi for p in o.polozky), default=-1) + 1
    for i, p in enumerate(nabidka.polozky):
        kopie = polozky_modul.kopiruj(p, ObjednavkaPolozka, objednavka_id=o.id)
        kopie.poradi = dalsi + i
        db.add(kopie)

    db.flush()
    db.refresh(o)
    _srovnej_cenu_objednavky(o)
    db.commit()
    db.refresh(o)
    return _rozpis_out(o, user)


# ==================== FAKTURACE OBJEDNÁVKY (CRM-09) =========================
def _faktura_out(f: Faktura) -> FakturaOut:
    return FakturaOut(
        id=f.id,
        poradi=f.poradi,
        nazev=f.nazev or "",
        stav=f.stav,
        castka=_num(f.castka),
        podil_procent=_num(f.podil_procent),
        termin=_iso(f.termin),
        variabilni_symbol=f.variabilni_symbol,
        poznamka=f.poznamka or "",
        pohoda_potvrzeno=bool(f.pohoda_potvrzeno),
        pohoda_datum_vystaveni=_iso(f.pohoda_datum_vystaveni),
        pohoda_datum_zaplaceni=_iso(f.pohoda_datum_zaplaceni),
        po_terminu=fakturace_modul.po_terminu(f),
    )


def _fakturace_out(o: Objednavka) -> FakturaceOut:
    faktury = sorted(o.faktury, key=lambda f: (f.poradi, f.id))
    return FakturaceOut(
        faktury=[_faktura_out(f) for f in faktury],
        souhrn=FakturaceSouhrn(**fakturace_modul.souhrn(faktury, o.cena_kc)),
        cena_objednavky_kc=_num(o.cena_kc),
    )


@router.get("/splatkove-sablony", response_model=list[SplatkovaSablonaOut])
def splatkove_sablony(user: User = Depends(vyzaduj_pripady)):
    """Předvolby splátkových kalendářů (100 % / 50-50 / 30-40-30)."""
    return [SplatkovaSablonaOut(**s) for s in fakturace_modul.sablony_pro_frontend()]


@router.get("/objednavky/{objednavka_id}/faktury", response_model=FakturaceOut)
def faktury_objednavky(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    return _fakturace_out(_objednavka_pro_polozky(db, objednavka_id, user))


@router.post("/objednavky/{objednavka_id}/faktury", response_model=FakturaceOut)
def pridej_fakturu(
    objednavka_id: int,
    vstup: FakturaVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Přidá jednu fakturu ručně (bez šablony)."""
    o = _objednavka_pro_polozky(db, objednavka_id, user)
    stav = vstup.stav or VYCHOZI_STAV_FAKTURY
    if stav not in STAVY_FAKTURY:
        raise HTTPException(status_code=422, detail=f"Neznámý stav faktury: {stav}")

    f = Faktura(
        crm_objednavka_id=o.id,
        poradi=max((x.poradi for x in o.faktury), default=0) + 1,
        nazev=(vstup.nazev or "").strip(),
        stav=stav,
        castka=vstup.castka,
        podil_procent=vstup.podil_procent,
        termin=_datum(vstup.termin, "termín faktury"),
        variabilni_symbol=(vstup.variabilni_symbol or "").strip() or None,
        poznamka=vstup.poznamka or "",
    )
    db.add(f)
    db.commit()
    db.refresh(o)
    return _fakturace_out(o)


@router.post("/objednavky/{objednavka_id}/faktury/ze-sablony", response_model=FakturaceOut)
def rozepis_splatky(
    objednavka_id: int,
    vstup: SplatkyZeSablonyVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Rozepíše cenu objednávky do splátek podle předvolby (CRM-09).

    Bez ceny to nemá co dělit – objednávka bez ceny dostane splátky s prázdnými
    částkami, což je horší než jasná chyba.
    """
    o = _objednavka_pro_polozky(db, objednavka_id, user)
    if o.cena_kc is None:
        raise HTTPException(
            status_code=422,
            detail="Objednávka nemá cenu – splátky není z čeho spočítat. Doplň cenu nebo rozpis položek.",
        )
    try:
        fakturace_modul.zaloz_ze_sablony(
            db, o, vstup.sablona, _datum(vstup.prvni_termin, "první termín"), vstup.nahradit
        )
    except ValueError as chyba:
        raise HTTPException(status_code=422, detail=str(chyba))
    db.commit()
    db.refresh(o)
    return _fakturace_out(o)


@router.post("/objednavky/{objednavka_id}/faktury/prepocitat", response_model=FakturaceOut)
def prepocitej_faktury(
    objednavka_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Srovná částky nevystavených faktur s aktuální cenou objednávky.

    Nikdy neběží samo – vystavená faktura je doklad a měnit ji za zády by byla
    ta nejhorší možná „chytrost“.
    """
    o = _objednavka_pro_polozky(db, objednavka_id, user)
    upraveno = fakturace_modul.prepocti_podle_podilu(list(o.faktury), o.cena_kc)
    if upraveno:
        db.commit()
        db.refresh(o)
    return _fakturace_out(o)


@router.put("/faktury/{faktura_id}", response_model=FakturaceOut)
def uprav_fakturu(
    faktura_id: int,
    vstup: FakturaVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    f = db.get(Faktura, faktura_id)
    if f is None or f.crm_objednavka_id is None:
        raise HTTPException(status_code=404, detail="Faktura objednávky neexistuje")
    o = _objednavka_pro_polozky(db, f.crm_objednavka_id, user)

    if vstup.stav is not None:
        if vstup.stav not in STAVY_FAKTURY:
            raise HTTPException(status_code=422, detail=f"Neznámý stav faktury: {vstup.stav}")
        f.stav = vstup.stav
    f.nazev = (vstup.nazev or "").strip()
    f.castka = vstup.castka
    f.podil_procent = vstup.podil_procent
    f.termin = _datum(vstup.termin, "termín faktury")
    f.variabilni_symbol = (vstup.variabilni_symbol or "").strip() or None
    f.poznamka = vstup.poznamka or ""
    # Ruční zásah má přednost před automatikou z Freela/Pohody – stejné
    # pravidlo jako u faktur Freelo projektů (viz finance/routes.py).
    f.upraveno_rucne = True
    db.commit()
    db.refresh(o)
    return _fakturace_out(o)


@router.delete("/faktury/{faktura_id}", response_model=FakturaceOut)
def smaz_fakturu(
    faktura_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    f = db.get(Faktura, faktura_id)
    if f is None or f.crm_objednavka_id is None:
        raise HTTPException(status_code=404, detail="Faktura objednávky neexistuje")
    o = _objednavka_pro_polozky(db, f.crm_objednavka_id, user)
    if f.stav in ("vystaveno", "zaplaceno"):
        raise HTTPException(
            status_code=409,
            detail="Vystavenou ani zaplacenou fakturu smazat nejde – přepni ji na „nefakturuje“.",
        )
    db.delete(f)
    db.commit()
    db.refresh(o)
    return _fakturace_out(o)


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
        extra=pole_modul.s_vypocty(db, "pro", p, p.extra),
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

    # CRM-31: pravidla navěšená na „vznikl nový projekt“.
    automatizace_modul.po_vzniku(db, "pro", p, user)
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
    drivejsi = {p.vlastnik_user_id, *(p.spoluvlastnici or [])}
    pribyli = [i for i in [vlastnik, *spolu] if i and i not in drivejsi]
    puvodni_zahajeni = p.zahajeni
    p.nazev = (vstup.nazev or "").strip()
    p.popis = vstup.popis or ""
    p.zahajeni = _datum(vstup.zahajeni, "zahájení")
    p.predani = _datum(vstup.predani, "předání")
    p.freelo_projekt_id = vstup.freelo_projekt_id
    p.vlastnik_user_id = vlastnik
    p.spoluvlastnici = spolu
    p.extra = pole_modul.zpracuj(db, "pro", vstup.extra)
    notifikace_modul.ohlas_prirazeni(
        db, user, f"{p.cislo} · {p.nazev}".strip(" ·"), f"/projekty/detail/{p.id}", pribyli
    )
    db.flush()
    if p.zahajeni != puvodni_zahajeni:
        kroky_modul.prepocitej_terminy(db, p)
    # CRM-31: změna pole (typicky posunuté předání).
    automatizace_modul.po_zmene_poli(db, "pro", p, user)
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
        notifikace_modul.ohlas_zmenu_stavu(
            db, user, f"{p.cislo} · {p.nazev}".strip(" ·"), f"/projekty/detail/{p.id}",
            novy.nazev, p.vlastnik_user_id, p.spoluvlastnici,
        )
        automatizace_modul.po_zmene_stavu(db, "pro", p, novy.klic, user)
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
    # Kategorie se validují proti tabulce, ne proti konstantě (CRM-03) – jinak
    # by se šablona nedala navěsit na kategorii, kterou si vedení přidalo samo.
    platne = kategorie_modul.platne_klice(db)
    neznama = [k for k in (vstup.kategorie or []) if k not in platne]
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


# ======================= KOMBINACE OPATŘENÍ ==================================
# Spojení hotové PPA a peak shaving nabídky téhož případu do jedné nabídky pro
# zákazníka, který chce obojí. NIC SE NEPOČÍTÁ – viz `nabidkovac/kombinace.py`.
@router.get("/pripady/{pripad_id}/kombinace-zdroje")
def zdroje_kombinace(
    pripad_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Které nabídky případu se dají spojit + jestli už kombinace existuje.

    Nabídka je použitelná jen se SPOČÍTANÝM řešením – z prázdné nabídky není co
    spojovat, a kdyby ji UI nabídlo, vznikla by kombinace bez čísel.
    """
    from app.nabidkovac.models import Nabidka, NavrhovaneReseni

    _vidi_pripad(db, pripad_id, user)
    nabidky = (
        db.query(Nabidka)
        .filter(Nabidka.obchodni_pripad_id == pripad_id)
        .order_by(Nabidka.id.desc())
        .all()
    )

    def _polozky(typ: str) -> list[dict]:
        out = []
        for n in nabidky:
            if n.typ != typ:
                continue
            reseni = [r for r in (n.reseni or []) if r.typ_reseni == typ]
            out.append(
                {
                    "id": n.id,
                    "cislo": n.cislo or f"#{n.id}",
                    "spocitana": len(reseni) > 0,
                    "vytvoreno_at": _iso(n.vytvoreno_at),
                }
            )
        return out

    kombinace = [
        {
            "id": n.id,
            "cislo": n.cislo or f"#{n.id}",
            "spojeno_at": _g_spojeno(n),
        }
        for n in nabidky
        if n.typ == "kombinace"
    ]
    return {
        "ppa": _polozky("ppa"),
        "peak_shaving": _polozky("peak_shaving"),
        "kombinace": kombinace,
    }


def _g_spojeno(n) -> str | None:
    """Kdy byla kombinace naposledy spojena (ze zdrojů uložených v řešení)."""
    for r in sorted(n.reseni or [], key=lambda x: x.id, reverse=True):
        if r.typ_reseni == "kombinace":
            return ((r.popis_json or {}).get("zdroje") or {}).get("spojeno_at")
    return None


@router.post("/pripady/{pripad_id}/kombinace")
def spoj_nabidky(
    pripad_id: int,
    vstup: dict,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Spojí PPA a peak shaving nabídku do nabídky typu `kombinace`.

    `nabidka_id` ve vstupu = existující kombinace, kterou se má AKTUALIZOVAT
    (jinak se založí nová). Aktualizace je vědomý krok obchodníka: kombinace se
    sama nepřepočítává, aby bylo dohledatelné, s jakými čísly nabídka odešla.
    """
    from app.nabidkovac import kombinace as kombinace_modul
    from app.nabidkovac.models import Nabidka, NavrhovaneReseni

    pripad = _vidi_pripad(db, pripad_id, user)
    ppa_id = vstup.get("ppa_nabidka_id")
    ps_id = vstup.get("ps_nabidka_id")
    if not ppa_id or not ps_id:
        raise HTTPException(
            status_code=422, detail="Vyber PPA nabídku i nabídku na peak shaving."
        )

    def _nabidka_se_resenim(nid: int, typ: str):
        n = db.get(Nabidka, nid)
        if n is None or n.obchodni_pripad_id != pripad.id or n.typ != typ:
            raise HTTPException(
                status_code=422,
                detail=f"Nabídka #{nid} k tomuto případu jako {typ} nepatří.",
            )
        reseni = (
            db.query(NavrhovaneReseni)
            .filter(
                NavrhovaneReseni.nabidka_id == n.id,
                NavrhovaneReseni.typ_reseni == typ,
            )
            .order_by(NavrhovaneReseni.id.desc())
            .first()
        )
        if reseni is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Nabídka {n.cislo or n.id} nemá spočítané řešení – nejdřív spusť "
                    "výpočet, jinak by kombinace byla bez čísel."
                ),
            )
        return n, reseni

    ppa_n, ppa_r = _nabidka_se_resenim(int(ppa_id), "ppa")
    ps_n, ps_r = _nabidka_se_resenim(int(ps_id), "peak_shaving")

    popis = kombinace_modul.slouceny_popis(
        ppa_r.popis_json or {},
        ps_r.popis_json or {},
        ppa_nabidka_id=ppa_n.id,
        ps_nabidka_id=ps_n.id,
        ppa_cislo=ppa_n.cislo or "",
        ps_cislo=ps_n.cislo or "",
    )

    cilova_id = vstup.get("nabidka_id")
    if cilova_id:
        k = db.get(Nabidka, int(cilova_id))
        if k is None or k.obchodni_pripad_id != pripad.id or k.typ != "kombinace":
            raise HTTPException(status_code=404, detail="Kombinovaná nabídka neexistuje")
    else:
        k = Nabidka(
            typ="kombinace",
            cislo=ciselne_rady.dalsi_cislo(db, "nab"),
            obchodni_pripad_id=pripad.id,
            zakaznik_nazev=(pripad.zakaznik.nazev if pripad.zakaznik is not None else ""),
            zakaznik_adresa=ppa_n.zakaznik_adresa or ps_n.zakaznik_adresa or "",
            zakaznik_gps_lat=ppa_n.zakaznik_gps_lat,
            zakaznik_gps_lng=ppa_n.zakaznik_gps_lng,
            stav="spocitano",
            vytvoril_user_id=user.id,
        )
        db.add(k)
        db.flush()

    # Nové spojení = nové řešení. Starší se nemažou, takže je dohledatelné,
    # co se posílalo dřív (stejně jako u přepočtů PPA/peak shavingu).
    db.add(
        NavrhovaneReseni(nabidka_id=k.id, typ_reseni="kombinace", popis_json=popis)
    )
    k.stav = "spocitano"
    db.commit()
    db.refresh(k)
    return {
        "id": k.id,
        "cislo": k.cislo,
        "typ": k.typ,
        "souhrn": popis["souhrn"],
        "zdroje": popis["zdroje"],
    }


# ==================== MIGRACE STARÝCH NABÍDEK ================================
@router.post("/migrace/stare-nabidky")
def migruj_stare_nabidky(
    nasucho: bool = Query(default=True),
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Dohledá nabídky z doby před CRM a zavěsí je na zákazníka a případ.

    Nabídky vzniklé přímo v nabídkovači nemají číslo ani obchodní případ, takže
    v přehledech visí jako `#21` bez zákazníka. Tahle operace pro každou z nich:
      1. najde nebo založí **klienta** podle jména z nabídky (dedup, case-insensitive),
      2. založí **obchodní případ** s kategorií podle typu nabídky,
      3. nabídku k případu zavěsí a doplní jí **číslo** z řady.

    `nasucho=true` (výchozí) nic nemění – jen vrátí, co by se stalo. Skutečná
    migrace je nevratná, takže se nesmí spustit omylem jedním kliknutím.

    Nabídky **bez jména zákazníka** se přeskočí: nemají kam patřit a zakládat
    pro ně prázdné klienty by jen zaneslo evidenci. Vypíšou se, ať je Dan může
    dořešit ručně.
    """
    from app.crm.models import Zakaznik
    from app.nabidkovac.models import Nabidka

    sirotci = (
        db.query(Nabidka)
        .filter(Nabidka.obchodni_pripad_id.is_(None))
        .order_by(Nabidka.id)
        .all()
    )

    # Existující klienti pro dedup podle jména (case-insensitive).
    podle_jmena = {
        (z.nazev or "").strip().lower(): z
        for z in db.query(Zakaznik).all()
        if (z.nazev or "").strip()
    }
    stav_obj = stavy_modul.vychozi_klic(db, "op")

    plan: list[dict] = []
    preskoceno: list[dict] = []
    novi_zakaznici: dict[str, Zakaznik] = {}

    for n in sirotci:
        jmeno = (n.zakaznik_nazev or "").strip()
        if not jmeno:
            preskoceno.append(
                {"id": n.id, "cislo": n.cislo or "", "typ": n.typ,
                 "duvod": "nabídka nemá jméno zákazníka"}
            )
            continue

        klic = jmeno.lower()
        existujici = podle_jmena.get(klic)
        zakaznik = existujici or novi_zakaznici.get(klic)

        if not nasucho:
            if zakaznik is None:
                zakaznik = Zakaznik(
                    typ="klient",  # nabídka už mu byla dělaná, tedy ne lead
                    nazev=jmeno,
                    adresa_ulice=(n.zakaznik_adresa or "").strip(),
                    gps_lat=n.zakaznik_gps_lat,
                    gps_lng=n.zakaznik_gps_lng,
                    # Vlastníkem je autor nabídky, ne ten, kdo migraci spustil –
                    # jinak by všechny staré zakázky spadly vedení.
                    vlastnik_user_id=n.vytvoril_user_id,
                    vytvoril_user_id=n.vytvoril_user_id or user.id,
                )
                db.add(zakaznik)
                db.flush()
                novi_zakaznici[klic] = zakaznik

            # Typ nabídky → kategorie případu, která na ten výpočet míří
            # (kategorie jsou konfigurovatelné, viz CRM-03).
            klic_kategorie = kategorie_modul.klic_podle_typu_nabidky(db, n.typ)
            kategorie = [klic_kategorie] if klic_kategorie else []
            pripad = ObchodniPripad(
                cislo=ciselne_rady.dalsi_cislo(db, "op"),
                zakaznik_id=zakaznik.id,
                nazev=f"Migrováno z nabídky {n.cislo or f'#{n.id}'}",
                kategorie=kategorie,
                stav=stav_obj,
                vlastnik_user_id=n.vytvoril_user_id,
                vytvoril_user_id=n.vytvoril_user_id or user.id,
            )
            db.add(pripad)
            db.flush()
            db.add(
                CrmStavHistorie(
                    entita="op", zaznam_id=pripad.id, ze_stavu=None,
                    do_stavu=stav_obj, zmenil_user_id=user.id,
                )
            )
            n.obchodni_pripad_id = pripad.id
            if not n.cislo:
                n.cislo = ciselne_rady.dalsi_cislo(db, "nab")
            plan.append(
                {"nabidka_id": n.id, "cislo": n.cislo, "typ": n.typ,
                 "zakaznik": jmeno, "pripad": pripad.cislo,
                 "zakaznik_novy": klic in novi_zakaznici}
            )
        else:
            plan.append(
                {"nabidka_id": n.id, "cislo": n.cislo or "(doplní se)", "typ": n.typ,
                 "zakaznik": jmeno, "pripad": "(vytvoří se)",
                 "zakaznik_novy": zakaznik is None}
            )
            if zakaznik is None:
                novi_zakaznici[klic] = None  # jen pro počítání v náhledu

    if not nasucho:
        db.commit()

    return {
        "nasucho": nasucho,
        "nabidek_bez_pripadu": len(sirotci),
        "zpracovano": len(plan),
        "novych_zakazniku": sum(1 for x in plan if x["zakaznik_novy"]),
        "preskoceno": preskoceno,
        "plan": plan,
    }


# ==================== IMPORT Z RAYNETU =======================================
@router.post("/import/raynet")
def import_z_raynetu(
    nasucho: bool = Query(default=True),
    limit_firem: int | None = Query(default=None),
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Natáhne klienty a obchodní případy z Raynetu (jednosměrně, idempotentně).

    Používá přístup, který už má nastavený konektor – žádné další heslo se
    nezadává. `nasucho=true` (výchozí) nic nezapisuje, jen spočítá, co by se
    stalo; skutečný import je nevratný.

    Před spuštěním se kontroluje **denní limit API callů** Raynetu: import čte
    stránkované výpisy (ne detail po detailu), ale u stovek záznamů se to sečte
    a vyčerpat limit uprostřed by nechalo data rozpůlená.
    """
    from app.crm import import_raynet
    from app.konektor.logika import NastaveniNepripraveno, vytvor_klienty
    from app.konektor.models import KonektorNastaveni

    nastaveni = db.query(KonektorNastaveni).first()
    if nastaveni is None:
        raise HTTPException(
            status_code=422,
            detail="Konektor na Raynet není nastavený – doplň přístupy v sekci Konektor.",
        )
    try:
        raynet, _drive = vytvor_klienty(nastaveni)
    except NastaveniNepripraveno as e:
        raise HTTPException(status_code=422, detail=f"Přístup k Raynetu není hotový: {e}")

    zbyva = raynet.zbyva_api()
    if zbyva is not None and zbyva < 200:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Raynet má dnes jen {zbyva} zbývajících API callů. Import by se nedokončil – "
                "zkus to zítra, limit se resetuje."
            ),
        )

    try:
        vysledek = import_raynet.importuj(
            db, raynet, user, nasucho=nasucho, limit_firem=limit_firem
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Raynet odpověděl chybou: {e}")

    vysledek["zbyvalo_api_callu"] = zbyva
    return vysledek


# ==================== UŽIVATELSKÉ FILTRY =====================================
# Definice filtru se ukládá tady; SAMO FILTROVÁNÍ dělá frontend nad načtenými
# řádky. Seznamy vracejí stovky záznamů (445 klientů, 210 případů), takže je to
# okamžité a bez round-tripu – a hlavně se tím nemusí psát generátor SQL
# z uživatelských podmínek, což je klasický zdroj chyb a děr. Až budou desetitisíce
# záznamů, filtr se přesune na server; formát podmínek je na to připravený.
@router.get("/filtry/{entita}", response_model=list[UlozenyFiltrOut])
def seznam_filtru(
    entita: str,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Moje filtry + ty, které někdo nasdílel."""
    if entita not in ENTITY_FILTRU:
        raise HTTPException(status_code=422, detail=f"Neznámá entita filtru: {entita}")
    filtry = (
        db.query(CrmUlozenyFiltr)
        .filter(
            CrmUlozenyFiltr.entita == entita,
            or_(
                CrmUlozenyFiltr.vlastnik_user_id == user.id,
                CrmUlozenyFiltr.sdileny.is_(True),
            ),
        )
        .order_by(CrmUlozenyFiltr.poradi, CrmUlozenyFiltr.nazev)
        .all()
    )
    return [_filtr_out(f, user) for f in filtry]


def _ciste_sloupce(vstup: dict | None) -> dict:
    """Rozvržení tabulky uložené s filtrem (CRM-28).

    Pouštíme jen `skryte` a `poradi` jako seznamy klíčů — jsou to data z UI,
    a ukládat, co přijde, by z JSONB udělalo skládku. Klíče se NEOVĚŘUJÍ proti
    sloupcům: vlastní pole se mažou a přidávají, takže platnost klíče se
    posuzuje až při vykreslení (neznámý se prostě ignoruje).
    """
    vstup = vstup or {}
    out: dict = {}
    for klic in ("skryte", "poradi"):
        hodnota = vstup.get(klic)
        if isinstance(hodnota, list):
            out[klic] = [str(x) for x in hodnota if isinstance(x, (str, int))]
    return out


def _filtr_out(f: CrmUlozenyFiltr, user: User) -> UlozenyFiltrOut:
    return UlozenyFiltrOut(
        id=f.id,
        entita=f.entita,
        nazev=f.nazev,
        podminky=f.podminky or [],
        razeni=f.razeni or [],
        sloupce=f.sloupce or {},
        sdileny=bool(f.sdileny),
        vychozi=bool(f.vychozi),
        poradi=f.poradi,
        vlastnik_user_id=f.vlastnik_user_id,
        vlastnik_jmeno=_jmeno(f.vlastnik),
        muj=f.vlastnik_user_id == user.id,
    )


def _zrus_jine_vychozi(db: Session, entita: str, user_id: int, kromě: int | None = None) -> None:
    """Výchozí filtr může být jen jeden na entitu a uživatele – jinak by appka
    nevěděla, který po otevření sekce použít."""
    q = db.query(CrmUlozenyFiltr).filter(
        CrmUlozenyFiltr.entita == entita,
        CrmUlozenyFiltr.vlastnik_user_id == user_id,
        CrmUlozenyFiltr.vychozi.is_(True),
    )
    if kromě is not None:
        q = q.filter(CrmUlozenyFiltr.id != kromě)
    for f in q.all():
        f.vychozi = False


@router.post("/filtry/{entita}", response_model=UlozenyFiltrOut)
def uloz_filtr(
    entita: str,
    vstup: UlozenyFiltrVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    if entita not in ENTITY_FILTRU:
        raise HTTPException(status_code=422, detail=f"Neznámá entita filtru: {entita}")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Filtr potřebuje název.")
    if not vstup.podminky and not vstup.razeni:
        raise HTTPException(
            status_code=422,
            detail="Prázdný filtr nemá co dělat – přidej aspoň jednu podmínku nebo řazení.",
        )
    if (
        db.query(CrmUlozenyFiltr.id)
        .filter(
            CrmUlozenyFiltr.entita == entita,
            CrmUlozenyFiltr.vlastnik_user_id == user.id,
            CrmUlozenyFiltr.nazev == nazev,
        )
        .first()
    ):
        raise HTTPException(status_code=409, detail="Filtr s tímhle názvem už máš.")

    if vstup.vychozi:
        _zrus_jine_vychozi(db, entita, user.id)
    f = CrmUlozenyFiltr(
        entita=entita,
        nazev=nazev,
        podminky=[p.model_dump() for p in vstup.podminky],
        razeni=[r.model_dump() for r in vstup.razeni],
        sloupce=_ciste_sloupce(vstup.sloupce),
        sdileny=bool(vstup.sdileny),
        vychozi=bool(vstup.vychozi),
        vlastnik_user_id=user.id,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return _filtr_out(f, user)


@router.put("/filtry/{filtr_id}", response_model=UlozenyFiltrOut)
def uprav_filtr(
    filtr_id: int,
    vstup: UlozenyFiltrVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Upravit smí jen autor. Nasdílený cizí filtr si ostatní mohou použít, ale
    ne přepsat – jinak by si ho lidé navzájem měnili pod rukama."""
    f = db.get(CrmUlozenyFiltr, filtr_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Filtr neexistuje")
    if f.vlastnik_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Tenhle filtr patří někomu jinému. Ulož si ho jako vlastní kopii.",
        )
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Filtr potřebuje název.")
    if vstup.vychozi:
        _zrus_jine_vychozi(db, f.entita, user.id, kromě=f.id)
    f.nazev = nazev
    f.podminky = [p.model_dump() for p in vstup.podminky]
    f.razeni = [r.model_dump() for r in vstup.razeni]
    f.sloupce = _ciste_sloupce(vstup.sloupce)
    f.sdileny = bool(vstup.sdileny)
    f.vychozi = bool(vstup.vychozi)
    db.commit()
    db.refresh(f)
    return _filtr_out(f, user)


@router.delete("/filtry/{filtr_id}")
def smaz_filtr(
    filtr_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    f = db.get(CrmUlozenyFiltr, filtr_id)
    if f is None:
        raise HTTPException(status_code=404, detail="Filtr neexistuje")
    if f.vlastnik_user_id != user.id:
        raise HTTPException(status_code=403, detail="Cizí filtr smazat nelze.")
    db.delete(f)
    db.commit()
    return {"ok": True}
