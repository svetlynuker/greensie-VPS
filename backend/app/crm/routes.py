"""API CRM: Zákazníci (leady/klienti), Obchodní případy, aktivity, nastavení.

Dvě věci, které se prolínají všemi endpointy:

1. VIDITELNOST ZÁZNAMŮ. Každý seznam jde přes `pristup.omez_na_moje`, každý
   detail přes `pristup.vyzaduj_zaznam`. Kdo nemá právo `crm_vse`, vidí jen
   svoje záznamy a cizí pro něj neexistují (404, ne 403 – viz `pristup.py`).

2. KOEXISTENCE S RAYNETEM. Případ může nést Raynetí číslo (`raynet_code`)
   vedle vlastního (`cislo`). Appka si čísluje sama, ale Raynetí kód nikdy
   nepřepisuje – stojí na něm párování složek na Disku a Freelo projektů.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.crm import ares as ares_modul
from app.crm import (
    ciselne_rady,
    kategorie as kategorie_modul,
    nabidky_pipeline,
    stavy as stavy_modul,
    ukoly as ukoly_modul,
    vlastni_pole as pole_modul,
)
from app.crm.models import (
    DRUHY_AKTIVITY,
    DRUHY_STAVU,
    ENTITY_AKTIVIT,
    ENTITY_CRM,
    KATEGORIE_OP,
    TYPY_ZAKAZNIKA,
    CiselnaRada,
    CrmAktivita,
    CrmKategorie,
    CrmStav,
    CrmStavHistorie,
    CrmVlastniPole,
    ObchodniPripad,
    Zakaznik,
    ZakaznikKontakt,
)
from app.crm.pristup import (
    muze_vse,
    omez_na_moje,
    smi_menit,
    vidi_zaznam,
    vychozi_vlastnik,
    vyzaduj_nastaveni,
    vyzaduj_pripady,
    vyzaduj_zakazniky,
    vyzaduj_zaznam,
)
from app.crm.schemas import (
    AktivitaOut,
    AktivitaUprava,
    AktivitaVstup,
    AresOut,
    KanbanOut,
    KanbanSloupec,
    NabidkaKanbanOut,
    NabidkaKanbanSloupec,
    NabidkaRadekOut,
    NabidkaZmenaStavuVstup,
    KontaktOut,
    KontaktVstup,
    PripadDetailOut,
    PripadRadekOut,
    PripadUprava,
    PripadVstup,
    KategorieOut,
    KategorieVstup,
    RadaOut,
    RadaVstup,
    StavOut,
    StavVstup,
    StavyPoradi,
    UkolOut,
    UzivatelVolbaOut,
    VlastniPoleOut,
    VlastniPolePoradi,
    VlastniPoleUprava,
    VlastniPoleVstup,
    ZakaznikDetailOut,
    ZakaznikRadekOut,
    ZakaznikVstup,
    ZmenaStavuVstup,
)
from app.database import get_db

router = APIRouter(prefix="/crm", tags=["crm"])


def vyzaduj_nabidkovac_crm(user: User = Depends(get_current_user)) -> User:
    """Sekce Nabídky jede pod stávajícím právem Nabídkovače.

    Kdo smí nabídky vytvářet, smí je i vidět v přehledu – zavádět kvůli
    seznamu další právo by katalog jen zaplevelilo.
    """
    if not muze_otevrit(user, "nabidkovac"):
        raise HTTPException(
            status_code=403, detail="Na Nabídky nemáš oprávnění (Nabídkovač)."
        )
    return user


# ---- pomocné ----------------------------------------------------------------
def _iso(x) -> str | None:
    return x.isoformat() if x is not None else None


def _num(x) -> float | None:
    return float(x) if x is not None else None


def _parse_datum(hodnota: str | None, pole: str) -> date | None:
    """ISO datum z frontendu (prázdné = nevyplněno)."""
    if hodnota is None or str(hodnota).strip() == "":
        return None
    try:
        return date.fromisoformat(str(hodnota)[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Pole {pole} není platné datum (YYYY-MM-DD).")


def _jmeno(u: User | None) -> str | None:
    return u.jmeno if u is not None else None


def _over_uzivatele(db: Session, ids: list[int]) -> list[int]:
    """Ponechá jen existující uživatele (spoluvlastníci ze zastaralého UI)."""
    if not ids:
        return []
    nalezeni = {i for (i,) in db.query(User.id).filter(User.id.in_(set(ids))).all()}
    return [i for i in dict.fromkeys(ids) if i in nalezeni]


def _vlastnictvi(db: Session, vstup, user: User, zaznam=None) -> tuple[int | None, list[int]]:
    """Určí vlastníka a spoluvlastníky podle práv volajícího.

    Vlastníka smí přepsat jen ten, kdo vidí všechny záznamy (vedení/admin) –
    jinak by si mohl OZ „přehodit" záznam na kolegu a sám o něj přijít, nebo
    naopak přebrat cizí. Běžný uživatel je vlastníkem toho, co založí.
    """
    spolu = _over_uzivatele(db, list(vstup.spoluvlastnici or []))
    if muze_vse(user) and vstup.vlastnik_user_id is not None:
        vlastnik = vstup.vlastnik_user_id
        if not db.query(User.id).filter(User.id == vlastnik).first():
            raise HTTPException(status_code=422, detail="Zvolený vlastník neexistuje.")
    elif zaznam is not None:
        vlastnik = zaznam.vlastnik_user_id  # úprava bez práva měnit vlastníka
    else:
        vlastnik = vychozi_vlastnik(user)
    return vlastnik, [i for i in spolu if i != vlastnik]


# ---- uživatelé do výběru ----------------------------------------------------
@router.get("/uzivatele", response_model=list[UzivatelVolbaOut])
def seznam_uzivatelu(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Uživatelé pro výběr vlastníka / spoluvlastníků."""
    lidi = db.query(User).order_by(User.jmeno).all()
    return [UzivatelVolbaOut(id=u.id, jmeno=u.jmeno) for u in lidi]


# ---- ARES -------------------------------------------------------------------
@router.get("/ares/{ico}", response_model=AresOut)
def ares_lookup(
    ico: str,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Návrh údajů firmy z ARESu + upozornění, že už takového zákazníka vedeme.

    Duplicitu hlásíme napříč VŠEMI zákazníky, i cizími – jinak by dva OZ
    založili tutéž firmu dvakrát a nikdo by to nezjistil. Vrací se jen název,
    ne obsah cizího záznamu.
    """
    try:
        data = ares_modul.najdi_podle_ico(ico)
    except ares_modul.AresChyba as e:
        raise HTTPException(status_code=422, detail=str(e))

    out = AresOut(**data)
    duplikat = (
        db.query(Zakaznik)
        .filter(Zakaznik.ico == data["ico"], Zakaznik.ico != "")
        .first()
    )
    if duplikat is not None:
        out.duplikat_id = duplikat.id
        out.duplikat_nazev = duplikat.nazev
    return out


# ---- zákazníci --------------------------------------------------------------
def _zakaznik_radek(
    z: Zakaznik, pocet_pripadu: int = 0, extra_text: dict | None = None
) -> ZakaznikRadekOut:
    return ZakaznikRadekOut(
        id=z.id,
        typ=z.typ,
        nazev=z.nazev,
        ico=z.ico or "",
        adresa_mesto=z.adresa_mesto or "",
        telefon=z.telefon or "",
        email=z.email or "",
        vlastnik_jmeno=_jmeno(z.vlastnik),
        pocet_pripadu=pocet_pripadu,
        vytvoreno_at=_iso(z.vytvoreno_at),
        extra_text=extra_text or {},
    )


def _zakaznik_detail(z: Zakaznik, user: User, db: Session) -> ZakaznikDetailOut:
    return ZakaznikDetailOut(
        id=z.id,
        typ=z.typ,
        nazev=z.nazev,
        ico=z.ico or "",
        dic=z.dic or "",
        adresa_ulice=z.adresa_ulice or "",
        adresa_mesto=z.adresa_mesto or "",
        adresa_psc=z.adresa_psc or "",
        adresa_stat=z.adresa_stat or "",
        gps_lat=_num(z.gps_lat),
        gps_lng=_num(z.gps_lng),
        web=z.web or "",
        telefon=z.telefon or "",
        email=z.email or "",
        zdroj=z.zdroj or "",
        poznamka=z.poznamka or "",
        vlastnik_user_id=z.vlastnik_user_id,
        vlastnik_jmeno=_jmeno(z.vlastnik),
        spoluvlastnici=list(z.spoluvlastnici or []),
        raynet_id=z.raynet_id,
        konvertovan_at=_iso(z.konvertovan_at),
        vytvoreno_at=_iso(z.vytvoreno_at),
        kontakty=[
            KontaktOut(
                id=k.id,
                jmeno=k.jmeno,
                funkce=k.funkce or "",
                email=k.email or "",
                telefon=k.telefon or "",
                hlavni=bool(k.hlavni),
                poznamka=k.poznamka or "",
            )
            # Hlavní kontakt první, pak podle jména – ať OZ nemusí hledat.
            for k in sorted(z.kontakty, key=lambda k: (not k.hlavni, k.jmeno or ""))
        ],
        extra=z.extra or {},
        vlastni_pole=[VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, "zakaznik")],
        muze_editovat=smi_menit(z, user),
    )


@router.get("/zakaznici", response_model=list[ZakaznikRadekOut])
def seznam_zakazniku(
    typ: str | None = Query(default=None),
    hledat: str | None = Query(default=None),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Leady nebo klienti (podle `typ`), profiltrované právy na záznamy."""
    if typ is not None and typ not in TYPY_ZAKAZNIKA:
        raise HTTPException(status_code=422, detail=f"Neznámý typ zákazníka: {typ}")

    q = db.query(Zakaznik)
    if typ is not None:
        q = q.filter(Zakaznik.typ == typ)
    if hledat:
        vzor = f"%{hledat.strip()}%"
        q = q.filter(
            or_(
                Zakaznik.nazev.ilike(vzor),
                Zakaznik.ico.ilike(vzor),
                Zakaznik.adresa_mesto.ilike(vzor),
                Zakaznik.email.ilike(vzor),
            )
        )
    q = omez_na_moje(q, Zakaznik, user)
    zakaznici = q.order_by(Zakaznik.nazev).all()

    # Počty případů jedním dotazem, ne N+1 (seznam může mít stovky řádků).
    pocty = dict(
        db.query(ObchodniPripad.zakaznik_id, func.count(ObchodniPripad.id))
        .group_by(ObchodniPripad.zakaznik_id)
        .all()
    )
    # Vlastní pole označená „v seznamu" – definice se čtou jednou pro celý
    # seznam, ne pro každý řádek.
    extra_texty = pole_modul.hodnoty_pro_seznam(db, "zakaznik", zakaznici)
    return [
        _zakaznik_radek(z, int(pocty.get(z.id, 0)), extra_texty.get(z.id))
        for z in zakaznici
    ]


@router.post("/zakaznici", response_model=ZakaznikDetailOut)
def zaloz_zakaznika(
    vstup: ZakaznikVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název zákazníka je povinný.")

    ico = ares_modul.normalizuj_ico(vstup.ico) if vstup.ico else ""
    vlastnik, spolu = _vlastnictvi(db, vstup, user)
    extra = pole_modul.zpracuj(db, "zakaznik", vstup.extra)

    z = Zakaznik(
        typ=vstup.typ,
        nazev=nazev,
        ico=ico,
        dic=(vstup.dic or "").strip(),
        adresa_ulice=(vstup.adresa_ulice or "").strip(),
        adresa_mesto=(vstup.adresa_mesto or "").strip(),
        adresa_psc=(vstup.adresa_psc or "").strip(),
        adresa_stat=(vstup.adresa_stat or "Česko").strip(),
        gps_lat=vstup.gps_lat,
        gps_lng=vstup.gps_lng,
        web=(vstup.web or "").strip(),
        telefon=(vstup.telefon or "").strip(),
        email=(vstup.email or "").strip(),
        zdroj=(vstup.zdroj or "").strip(),
        poznamka=vstup.poznamka or "",
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        extra=extra,
        vytvoril_user_id=user.id,
        konvertovan_at=datetime.now() if vstup.typ == "klient" else None,
    )
    db.add(z)
    db.commit()
    db.refresh(z)
    return _zakaznik_detail(z, user, db)


@router.get("/zakaznici/{zakaznik_id}", response_model=ZakaznikDetailOut)
def detail_zakaznika(
    zakaznik_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    return _zakaznik_detail(z, user, db)


@router.put("/zakaznici/{zakaznik_id}", response_model=ZakaznikDetailOut)
def uprav_zakaznika(
    zakaznik_id: int,
    vstup: ZakaznikVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název zákazníka je povinný.")

    puvodni_typ = z.typ
    vlastnik, spolu = _vlastnictvi(db, vstup, user, zaznam=z)

    z.typ = vstup.typ
    z.nazev = nazev
    z.ico = ares_modul.normalizuj_ico(vstup.ico) if vstup.ico else ""
    z.dic = (vstup.dic or "").strip()
    z.adresa_ulice = (vstup.adresa_ulice or "").strip()
    z.adresa_mesto = (vstup.adresa_mesto or "").strip()
    z.adresa_psc = (vstup.adresa_psc or "").strip()
    z.adresa_stat = (vstup.adresa_stat or "Česko").strip()
    z.gps_lat = vstup.gps_lat
    z.gps_lng = vstup.gps_lng
    z.web = (vstup.web or "").strip()
    z.telefon = (vstup.telefon or "").strip()
    z.email = (vstup.email or "").strip()
    z.zdroj = (vstup.zdroj or "").strip()
    z.poznamka = vstup.poznamka or ""
    z.vlastnik_user_id = vlastnik
    z.spoluvlastnici = spolu
    z.extra = pole_modul.zpracuj(db, "zakaznik", vstup.extra)
    # Okamžik konverze zapisujeme jen při skutečném přechodu lead → klient.
    if puvodni_typ == "lead" and z.typ == "klient" and z.konvertovan_at is None:
        z.konvertovan_at = datetime.now()

    db.commit()
    db.refresh(z)
    return _zakaznik_detail(z, user, db)


@router.post("/zakaznici/{zakaznik_id}/konvertuj", response_model=ZakaznikDetailOut)
def konvertuj_na_klienta(
    zakaznik_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Lead → klient. Záznam se nekopíruje, jen se přepne příznak, takže
    aktivity i obchodní případy leadu zůstávají navázané."""
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    if z.typ != "klient":
        z.typ = "klient"
        z.konvertovan_at = datetime.now()
        db.commit()
        db.refresh(z)
    return _zakaznik_detail(z, user, db)


@router.delete("/zakaznici/{zakaznik_id}")
def smaz_zakaznika(
    zakaznik_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Smaže zákazníka. Zákazníka s obchodními případy smazat NELZE – jinak by
    zmizela historie zakázek; nejdřív se musí smazat/přepojit případy."""
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    pocet = db.query(func.count(ObchodniPripad.id)).filter(
        ObchodniPripad.zakaznik_id == z.id
    ).scalar()
    if int(pocet or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Zákazník má {int(pocet)} obchodních případů – nejdřív je smaž nebo přepoj.",
        )
    # Aktivity zákazníka nejsou vázané cizím klíčem (jedna tabulka pro všechny
    # entity), takže je mažeme ručně, ať po záznamu nezůstanou sirotci.
    db.query(CrmAktivita).filter(
        CrmAktivita.entita == "zakaznik", CrmAktivita.zaznam_id == z.id
    ).delete(synchronize_session=False)
    db.delete(z)
    db.commit()
    return {"ok": True}


# ---- kontaktní osoby --------------------------------------------------------
@router.post("/zakaznici/{zakaznik_id}/kontakty", response_model=ZakaznikDetailOut)
def pridej_kontakt(
    zakaznik_id: int,
    vstup: KontaktVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    jmeno = (vstup.jmeno or "").strip()
    if not jmeno:
        raise HTTPException(status_code=422, detail="Jméno kontaktu je povinné.")
    if vstup.hlavni:
        # Hlavní kontakt může být jen jeden – ostatní se přepnou na běžné.
        for k in z.kontakty:
            k.hlavni = False
    db.add(
        ZakaznikKontakt(
            zakaznik_id=z.id,
            jmeno=jmeno,
            funkce=(vstup.funkce or "").strip(),
            email=(vstup.email or "").strip(),
            telefon=(vstup.telefon or "").strip(),
            hlavni=bool(vstup.hlavni),
            poznamka=vstup.poznamka or "",
        )
    )
    db.commit()
    db.refresh(z)
    return _zakaznik_detail(z, user, db)


@router.put("/kontakty/{kontakt_id}", response_model=ZakaznikDetailOut)
def uprav_kontakt(
    kontakt_id: int,
    vstup: KontaktVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    k = db.get(ZakaznikKontakt, kontakt_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kontakt neexistuje")
    z = vyzaduj_zaznam(db.get(Zakaznik, k.zakaznik_id), user, "Zákazník")

    jmeno = (vstup.jmeno or "").strip()
    if not jmeno:
        raise HTTPException(status_code=422, detail="Jméno kontaktu je povinné.")
    if vstup.hlavni:
        for jiny in z.kontakty:
            if jiny.id != k.id:
                jiny.hlavni = False
    k.jmeno = jmeno
    k.funkce = (vstup.funkce or "").strip()
    k.email = (vstup.email or "").strip()
    k.telefon = (vstup.telefon or "").strip()
    k.hlavni = bool(vstup.hlavni)
    k.poznamka = vstup.poznamka or ""
    db.commit()
    db.refresh(z)
    return _zakaznik_detail(z, user, db)


@router.delete("/kontakty/{kontakt_id}", response_model=ZakaznikDetailOut)
def smaz_kontakt(
    kontakt_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    k = db.get(ZakaznikKontakt, kontakt_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kontakt neexistuje")
    z = vyzaduj_zaznam(db.get(Zakaznik, k.zakaznik_id), user, "Zákazník")
    db.delete(k)
    db.commit()
    db.refresh(z)
    return _zakaznik_detail(z, user, db)


# ---- obchodní případy -------------------------------------------------------
def _mapa_stavu(db: Session, entita: str) -> dict[str, CrmStav]:
    return {s.klic: s for s in stavy_modul.seznam(db, entita)}


def _pripad_radek(
    p: ObchodniPripad, stav_nazvy: dict[str, CrmStav], extra_text: dict | None = None
) -> PripadRadekOut:
    stav = stav_nazvy.get(p.stav)
    return PripadRadekOut(
        id=p.id,
        cislo=p.cislo,
        nazev=p.nazev or "",
        zakaznik_id=p.zakaznik_id,
        zakaznik_nazev=p.zakaznik.nazev if p.zakaznik is not None else "",
        kategorie=list(p.kategorie or []),
        stav=p.stav,
        # Smazaný stav necháváme čitelný jako klíč, ať záznam nezmizí z UI.
        stav_nazev=stav.nazev if stav is not None else p.stav,
        hodnota_kc=_num(p.hodnota_kc),
        pravdepodobnost=p.pravdepodobnost,
        predpokladane_uzavreni=_iso(p.predpokladane_uzavreni),
        vlastnik_jmeno=_jmeno(p.vlastnik),
        raynet_code=p.raynet_code or "",
        vytvoreno_at=_iso(p.vytvoreno_at),
        extra_text=extra_text or {},
    )


def _nabidky_pripadu(db: Session, pripad_id: int) -> list[dict]:
    """Nabídky navázané na případ (čte se z nabídkovače – ten je zdroj pravdy
    o výpočtech, CRM si jejich obsah nekopíruje)."""
    from app.nabidkovac.models import Nabidka

    nabidky = (
        db.query(Nabidka)
        .filter(Nabidka.obchodni_pripad_id == pripad_id)
        .order_by(Nabidka.id.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "cislo": n.cislo or "",
            "typ": n.typ,
            "stav": n.stav,
            "vytvoreno_at": _iso(n.vytvoreno_at),
            "pocet_reseni": len(n.reseni or []),
        }
        for n in nabidky
    ]


def _pripad_detail(db: Session, p: ObchodniPripad, user: User) -> PripadDetailOut:
    zaklad = _pripad_radek(p, _mapa_stavu(db, "op")).model_dump()
    zaklad.pop("extra_text", None)  # v detailu se posílají surové hodnoty + definice
    return PripadDetailOut(
        **zaklad,
        popis=p.popis or "",
        duvod_prohry=p.duvod_prohry or "",
        uzavreno_at=_iso(p.uzavreno_at),
        vlastnik_user_id=p.vlastnik_user_id,
        spoluvlastnici=list(p.spoluvlastnici or []),
        raynet_id=p.raynet_id,
        nabidky=_nabidky_pripadu(db, p.id),
        extra_text={},
        extra=p.extra or {},
        vlastni_pole=[VlastniPoleOut(**vp) for vp in pole_modul.pro_frontend(db, "op")],
        muze_editovat=smi_menit(p, user),
    )


def _over_kategorie(db: Session, kategorie: list[str]) -> list[str]:
    """Ověří klíče proti tabulce kategorií (ne proti konstantě – viz CRM-03).

    Vypnuté kategorie projdou schválně: případ, který ji už nese, musí zůstat
    uložitelný, i když ji vedení mezitím schovalo z nabídky.
    """
    platne = kategorie_modul.platne_klice(db)
    neznama = [k for k in kategorie if k not in platne]
    if neznama:
        raise HTTPException(
            status_code=422, detail=f"Neznámá kategorie případu: {', '.join(neznama)}"
        )
    return list(dict.fromkeys(kategorie))


@router.get("/pripady", response_model=list[PripadRadekOut])
def seznam_pripadu(
    stav: str | None = Query(default=None),
    zakaznik_id: int | None = Query(default=None),
    hledat: str | None = Query(default=None),
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    q = db.query(ObchodniPripad).join(Zakaznik, ObchodniPripad.zakaznik_id == Zakaznik.id)
    if stav:
        q = q.filter(ObchodniPripad.stav == stav)
    if zakaznik_id is not None:
        q = q.filter(ObchodniPripad.zakaznik_id == zakaznik_id)
    if hledat:
        vzor = f"%{hledat.strip()}%"
        q = q.filter(
            or_(
                ObchodniPripad.cislo.ilike(vzor),
                ObchodniPripad.nazev.ilike(vzor),
                ObchodniPripad.raynet_code.ilike(vzor),
                Zakaznik.nazev.ilike(vzor),
            )
        )
    q = omez_na_moje(q, ObchodniPripad, user)
    pripady = q.order_by(ObchodniPripad.cislo.desc()).all()
    mapa = _mapa_stavu(db, "op")
    extra_texty = pole_modul.hodnoty_pro_seznam(db, "op", pripady)
    return [_pripad_radek(p, mapa, extra_texty.get(p.id)) for p in pripady]


@router.get("/pripady/kanban", response_model=KanbanOut)
def kanban_pripadu(
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Případy rozdělené do sloupců podle stavů (pořadí = pořadí stavů).

    Případy ve stavu, který už neexistuje (vedení sloupec smazalo), spadnou do
    prvního sloupce – aby se neztratily z dohledu, dokud je někdo nepřesune.
    """
    q = omez_na_moje(db.query(ObchodniPripad), ObchodniPripad, user)
    pripady = q.order_by(ObchodniPripad.cislo.desc()).all()
    seznam_stavu = stavy_modul.seznam(db, "op")
    mapa = {s.klic: s for s in seznam_stavu}
    extra_texty = pole_modul.hodnoty_pro_seznam(db, "op", pripady)

    koše: dict[str, list[ObchodniPripad]] = {s.klic: [] for s in seznam_stavu}
    for p in pripady:
        klic = p.stav if p.stav in koše else (seznam_stavu[0].klic if seznam_stavu else None)
        if klic is None:
            continue
        koše[klic].append(p)

    sloupce = []
    for s in seznam_stavu:
        v_koši = koše.get(s.klic, [])
        soucet = sum(float(p.hodnota_kc) for p in v_koši if p.hodnota_kc is not None)
        sloupce.append(
            KanbanSloupec(
                stav=StavOut(
                    id=s.id,
                    entita=s.entita,
                    klic=s.klic,
                    nazev=s.nazev,
                    poradi=s.poradi,
                    barva=s.barva or "",
                    druh=s.druh,
                ),
                zaznamy=[_pripad_radek(p, mapa, extra_texty.get(p.id)) for p in v_koši],
                pocet=len(v_koši),
                soucet_kc=soucet if soucet else None,
            )
        )
    return KanbanOut(entita="op", sloupce=sloupce)


@router.post("/pripady", response_model=PripadDetailOut)
def zaloz_pripad(
    vstup: PripadVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Založí obchodní případ s vlastním číslem z řady (OP-RR-NNNN).

    Číslo se přiděluje ve stejné transakci jako záznam – když uložení spadne,
    číslo se nespotřebuje a v řadě nevznikne díra.
    """
    z = vyzaduj_zaznam(db.get(Zakaznik, vstup.zakaznik_id), user, "Zákazník")
    kategorie = _over_kategorie(db, list(vstup.kategorie or []))
    vlastnik, spolu = _vlastnictvi(db, vstup, user)

    extra = pole_modul.zpracuj(db, "op", vstup.extra)
    cislo = ciselne_rady.dalsi_cislo(db, "op")
    stav = stavy_modul.vychozi_klic(db, "op")

    p = ObchodniPripad(
        cislo=cislo,
        zakaznik_id=z.id,
        nazev=(vstup.nazev or "").strip(),
        popis=vstup.popis or "",
        kategorie=kategorie,
        stav=stav,
        hodnota_kc=vstup.hodnota_kc,
        pravdepodobnost=vstup.pravdepodobnost,
        predpokladane_uzavreni=_parse_datum(vstup.predpokladane_uzavreni, "předpokládané uzavření"),
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        raynet_code=(vstup.raynet_code or "").strip().upper(),
        extra=extra,
        vytvoril_user_id=user.id,
    )
    db.add(p)
    db.flush()
    # Založení je první bod dráhy případu – bez něj by v historii chyběl start.
    db.add(
        CrmStavHistorie(
            entita="op", zaznam_id=p.id, ze_stavu=None, do_stavu=stav, zmenil_user_id=user.id
        )
    )
    db.commit()
    db.refresh(p)
    return _pripad_detail(db, p, user)


@router.get("/pripady/{pripad_id}", response_model=PripadDetailOut)
def detail_pripadu(
    pripad_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    return _pripad_detail(db, p, user)


@router.put("/pripady/{pripad_id}", response_model=PripadDetailOut)
def uprav_pripad(
    pripad_id: int,
    vstup: PripadUprava,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    if vstup.zakaznik_id is not None and vstup.zakaznik_id != p.zakaznik_id:
        # Přepojení na jiného zákazníka smí jen ten, kdo na nového vidí.
        novy = vyzaduj_zaznam(db.get(Zakaznik, vstup.zakaznik_id), user, "Zákazník")
        p.zakaznik_id = novy.id

    vlastnik, spolu = _vlastnictvi(db, vstup, user, zaznam=p)
    p.nazev = (vstup.nazev or "").strip()
    p.popis = vstup.popis or ""
    p.kategorie = _over_kategorie(db, list(vstup.kategorie or []))
    p.hodnota_kc = vstup.hodnota_kc
    p.pravdepodobnost = vstup.pravdepodobnost
    p.predpokladane_uzavreni = _parse_datum(
        vstup.predpokladane_uzavreni, "předpokládané uzavření"
    )
    p.vlastnik_user_id = vlastnik
    p.spoluvlastnici = spolu
    p.extra = pole_modul.zpracuj(db, "op", vstup.extra)
    # Raynetí kód se dá doplnit (dohledání staré zakázky), ale nikdy se
    # nepřepisuje na prázdno – je to most na složky Disku.
    novy_kod = (vstup.raynet_code or "").strip().upper()
    if novy_kod:
        p.raynet_code = novy_kod

    db.commit()
    db.refresh(p)
    return _pripad_detail(db, p, user)


@router.post("/pripady/{pripad_id}/stav", response_model=PripadDetailOut)
def zmen_stav_pripadu(
    pripad_id: int,
    vstup: ZmenaStavuVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Přesun případu v kanbanu. Zapisuje historii a hlídá důvod prohry.

    Prohra bez důvodu je odmítnutá schválně: bez důvodů proher nemá statistika
    pipeline žádnou vypovídací hodnotu a dodatečně už si to nikdo nepamatuje.
    """
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    novy = stavy_modul.najdi(db, "op", vstup.stav)
    if novy is None:
        raise HTTPException(status_code=422, detail=f"Stav '{vstup.stav}' neexistuje.")
    if p.stav == novy.klic and not vstup.duvod_prohry:
        return _pripad_detail(db, p, user)

    duvod = (vstup.duvod_prohry or "").strip()
    if novy.druh == "prohra" and not duvod and not (p.duvod_prohry or "").strip():
        raise HTTPException(
            status_code=422,
            detail="U prohraného případu je potřeba uvést důvod prohry.",
        )

    puvodni = p.stav
    p.stav = novy.klic
    if duvod:
        p.duvod_prohry = duvod
    if novy.druh in ("vyhra", "prohra"):
        p.uzavreno_at = datetime.now()
        if novy.druh == "vyhra":
            p.duvod_prohry = ""
            # První výhra dělá z leadu klienta – jinak by v Klientech chyběly
            # firmy, se kterými už reálně obchodujeme.
            z = db.get(Zakaznik, p.zakaznik_id)
            if z is not None and z.typ == "lead":
                z.typ = "klient"
                z.konvertovan_at = datetime.now()
    else:
        p.uzavreno_at = None

    if puvodni != novy.klic:
        db.add(
            CrmStavHistorie(
                entita="op",
                zaznam_id=p.id,
                ze_stavu=puvodni,
                do_stavu=novy.klic,
                zmenil_user_id=user.id,
            )
        )
    db.commit()
    db.refresh(p)
    return _pripad_detail(db, p, user)


@router.post("/pripady/{pripad_id}/nabidka")
def vytvor_nabidku_z_pripadu(
    pripad_id: int,
    vstup: dict,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Založí nabídku pod obchodním případem a předá jí údaje zákazníka.

    Tohle je cesta, kterou má OZ chodit: zákazníka ani adresu už do nabídky
    nevyplňuje ručně (opisování = překlepy v dokumentu pro zákazníka), přenesou
    se z karty klienta. GPS jde s tím, protože ji potřebuje výpočet PPA.

    `typ` musí přijít z volajícího: když má případ jedinou kategorii, UI ji
    předvyplní; při víc kategoriích nebo žádné se OZ zeptá (zadání Dana).
    """
    from app.nabidkovac.models import TYPY_NABIDKY, Nabidka

    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    typ = str(vstup.get("typ") or "").strip()
    if typ not in TYPY_NABIDKY:
        raise HTTPException(
            status_code=422,
            detail=f"Neznámý typ nabídky: {typ or '(nevyplněno)'}",
        )
    # Nabídkovač má vlastní právo (OZ) – bez něj by šlo přes CRM obejít.
    if not muze_otevrit(user, "nabidkovac"):
        raise HTTPException(
            status_code=403, detail="Na vytváření nabídek nemáš oprávnění (Nabídkovač)."
        )

    z = db.get(Zakaznik, p.zakaznik_id)
    adresa = ", ".join(
        x for x in [(z.adresa_ulice or ""), (z.adresa_psc or ""), (z.adresa_mesto or "")] if x
    ) if z is not None else ""

    n = Nabidka(
        typ=typ,
        cislo=ciselne_rady.dalsi_cislo(db, "nab"),
        obchodni_pripad_id=p.id,
        zakaznik_nazev=(z.nazev if z is not None else "") or "",
        zakaznik_adresa=adresa,
        zakaznik_gps_lat=z.gps_lat if z is not None else None,
        zakaznik_gps_lng=z.gps_lng if z is not None else None,
        vytvoril_user_id=user.id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "cislo": n.cislo, "typ": n.typ}


@router.get("/pripady/{pripad_id}/historie")
def historie_pripadu(
    pripad_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Dráha případu fázemi – kdo, kdy, odkud kam."""
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    radky = (
        db.query(CrmStavHistorie)
        .filter(CrmStavHistorie.entita == "op", CrmStavHistorie.zaznam_id == p.id)
        .order_by(CrmStavHistorie.zmeneno_at, CrmStavHistorie.id)
        .all()
    )
    mapa = _mapa_stavu(db, "op")

    def _nazev(klic: str | None) -> str | None:
        if klic is None:
            return None
        s = mapa.get(klic)
        return s.nazev if s is not None else klic

    return [
        {
            "id": r.id,
            "ze_stavu": _nazev(r.ze_stavu),
            "do_stavu": _nazev(r.do_stavu),
            "zmenil_jmeno": _jmeno(r.zmenil),
            "zmeneno_at": _iso(r.zmeneno_at),
        }
        for r in radky
    ]


@router.delete("/pripady/{pripad_id}")
def smaz_pripad(
    pripad_id: int,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    # Historie i aktivity nejsou vázané cizím klíčem (generické tabulky),
    # takže je mažeme ručně – jinak by po případu zůstali sirotci.
    db.query(CrmStavHistorie).filter(
        CrmStavHistorie.entita == "op", CrmStavHistorie.zaznam_id == p.id
    ).delete(synchronize_session=False)
    db.query(CrmAktivita).filter(
        CrmAktivita.entita == "op", CrmAktivita.zaznam_id == p.id
    ).delete(synchronize_session=False)
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---- nabídky: obchodní pipeline a sekce Nabídky -----------------------------
# Nabídky zůstávají v tabulce nabídkovače (ten je zdroj pravdy o výpočtech);
# CRM jim přidává obchodní stav a pohled „co je odesláno a co viselo".
def _nabidka_radek(db: Session, n, stav_mapa: dict[str, CrmStav]) -> NabidkaRadekOut:
    klic = nabidky_pipeline.stav_nabidky(db, n)
    stav = stav_mapa.get(klic)
    pripad = n.obchodni_pripad_id and db.get(ObchodniPripad, n.obchodni_pripad_id)
    return NabidkaRadekOut(
        id=n.id,
        cislo=n.cislo or "",
        typ=n.typ,
        stav=klic,
        stav_nazev=stav.nazev if stav is not None else klic,
        stav_zpracovani=n.stav or "",
        spocitana=nabidky_pipeline.je_spocitana(n),
        # Zákazník: přednost má karta klienta z případu, protože je aktuální;
        # u nabídek bez případu zůstává text zapsaný v nabídce.
        zakaznik_nazev=(
            pripad.zakaznik.nazev
            if pripad is not None and pripad.zakaznik is not None
            else (n.zakaznik_nazev or "")
        ),
        pripad_id=pripad.id if pripad is not None else None,
        pripad_cislo=pripad.cislo if pripad is not None else "",
        vytvoril_jmeno=_jmeno(n.vytvoril),
        vytvoreno_at=_iso(n.vytvoreno_at),
    )


@router.get("/nabidky", response_model=list[NabidkaRadekOut])
def seznam_nabidek_crm(
    stav: str | None = Query(default=None),
    typ: str | None = Query(default=None),
    hledat: str | None = Query(default=None),
    user: User = Depends(vyzaduj_nabidkovac_crm),
    db: Session = Depends(get_db),
):
    """Nabídky napříč případy – obchodní přehled, ne výpočet."""
    from app.nabidkovac.models import Nabidka

    q = db.query(Nabidka)
    if typ:
        q = q.filter(Nabidka.typ == typ)
    if hledat:
        vzor = f"%{hledat.strip()}%"
        q = q.filter(
            or_(Nabidka.cislo.ilike(vzor), Nabidka.zakaznik_nazev.ilike(vzor))
        )
    q = nabidky_pipeline.omez_na_moje(q, user)
    nabidky = q.order_by(Nabidka.id.desc()).all()

    mapa = _mapa_stavu(db, "nab")
    radky = [_nabidka_radek(db, n, mapa) for n in nabidky]
    # Filtr podle stavu až tady: starší nabídky stav v DB nemají a dopočítává
    # se jim první stav pipeline, takže v SQL by se nechytily.
    if stav:
        radky = [r for r in radky if r.stav == stav]
    return radky


@router.get("/nabidky/kanban", response_model=NabidkaKanbanOut)
def kanban_nabidek(
    user: User = Depends(vyzaduj_nabidkovac_crm),
    db: Session = Depends(get_db),
):
    """Nabídky rozdělené do sloupců podle obchodních stavů."""
    from app.nabidkovac.models import Nabidka

    q = nabidky_pipeline.omez_na_moje(db.query(Nabidka), user)
    nabidky = q.order_by(Nabidka.id.desc()).all()
    seznam_stavu = stavy_modul.seznam(db, "nab")
    mapa = {s.klic: s for s in seznam_stavu}

    koše: dict[str, list] = {s.klic: [] for s in seznam_stavu}
    for n in nabidky:
        klic = nabidky_pipeline.stav_nabidky(db, n)
        # Nabídka ve smazaném stavu spadne do prvního sloupce, ať nezmizí z dohledu.
        if klic not in koše and seznam_stavu:
            klic = seznam_stavu[0].klic
        if klic in koše:
            koše[klic].append(n)

    sloupce = [
        NabidkaKanbanSloupec(
            stav=_stav_out(s),
            zaznamy=[_nabidka_radek(db, n, mapa) for n in koše.get(s.klic, [])],
            pocet=len(koše.get(s.klic, [])),
        )
        for s in seznam_stavu
    ]
    return NabidkaKanbanOut(sloupce=sloupce)


@router.post("/nabidky/{nabidka_id}/stav", response_model=NabidkaRadekOut)
def zmen_stav_nabidky(
    nabidka_id: int,
    vstup: NabidkaZmenaStavuVstup,
    user: User = Depends(vyzaduj_nabidkovac_crm),
    db: Session = Depends(get_db),
):
    """Přesun nabídky v obchodní pipeline (odeslána, přijata, zamítnuta…).

    Zapisuje historii, aby šlo zjistit, jak dlouho nabídka u zákazníka visela.
    Stav obchodního případu se NEMĚNÍ automaticky: přijatá nabídka ještě není
    podepsaná objednávka a předbíhat rozhodnutí obchodníka by bylo horší než
    nechat ho případ posunout sám.
    """
    from app.nabidkovac.models import Nabidka

    n = db.get(Nabidka, nabidka_id)
    if n is None or not nabidky_pipeline.vidi_nabidku(db, n, user):
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")

    novy = stavy_modul.najdi(db, "nab", vstup.stav)
    if novy is None:
        raise HTTPException(status_code=422, detail=f"Stav '{vstup.stav}' neexistuje.")

    puvodni = nabidky_pipeline.stav_nabidky(db, n)
    if puvodni != novy.klic:
        n.stav_obchodni = novy.klic
        db.add(
            CrmStavHistorie(
                entita="nab",
                zaznam_id=n.id,
                ze_stavu=puvodni,
                do_stavu=novy.klic,
                zmenil_user_id=user.id,
            )
        )
        db.commit()
        db.refresh(n)
    return _nabidka_radek(db, n, _mapa_stavu(db, "nab"))


# ---- aktivity a poznámky ----------------------------------------------------
def _over_pristup_k_zaznamu(db: Session, entita: str, zaznam_id: int, user: User) -> None:
    """Aktivity se řídí právy nadřazeného záznamu, ne vlastními."""
    if entita not in ENTITY_AKTIVIT:
        raise HTTPException(status_code=422, detail=f"Neznámá entita: {entita}")
    if entita == "zakaznik":
        vyzaduj_zaznam(db.get(Zakaznik, zaznam_id), user, "Zákazník")
    elif entita == "op":
        vyzaduj_zaznam(db.get(ObchodniPripad, zaznam_id), user, "Obchodní případ")
    else:
        # nab/obj/pro přijdou v druhé dávce – do té doby na ně aktivity nepatří
        raise HTTPException(
            status_code=422, detail=f"Aktivity pro '{entita}' zatím nejsou k dispozici."
        )


def _aktivita_out(a: CrmAktivita) -> AktivitaOut:
    return AktivitaOut(
        id=a.id,
        entita=a.entita,
        zaznam_id=a.zaznam_id,
        druh=a.druh,
        text=a.text or "",
        termin=_iso(a.termin),
        hotovo=bool(a.hotovo),
        vlastnik_jmeno=_jmeno(a.vlastnik),
        vytvoril_jmeno=_jmeno(a.vytvoril),
        vytvoreno_at=_iso(a.vytvoreno_at),
    )


@router.get("/aktivity/{entita}/{zaznam_id}", response_model=list[AktivitaOut])
def seznam_aktivit(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    _over_pristup_k_zaznamu(db, entita, zaznam_id, user)
    radky = (
        db.query(CrmAktivita)
        .filter(CrmAktivita.entita == entita, CrmAktivita.zaznam_id == zaznam_id)
        # Nedokončené úkoly nahoře, pak nejnovější – OZ řeší, co ho tlačí.
        .order_by(CrmAktivita.hotovo, CrmAktivita.vytvoreno_at.desc())
        .all()
    )
    return [_aktivita_out(a) for a in radky]


@router.post("/aktivity/{entita}/{zaznam_id}", response_model=AktivitaOut)
def pridej_aktivitu(
    entita: str,
    zaznam_id: int,
    vstup: AktivitaVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    _over_pristup_k_zaznamu(db, entita, zaznam_id, user)
    if vstup.druh not in DRUHY_AKTIVITY:
        raise HTTPException(status_code=422, detail=f"Neznámý druh aktivity: {vstup.druh}")
    text = (vstup.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Text aktivity je povinný.")

    vlastnik = vstup.vlastnik_user_id or user.id
    if not db.query(User.id).filter(User.id == vlastnik).first():
        raise HTTPException(status_code=422, detail="Zvolený řešitel neexistuje.")

    a = CrmAktivita(
        entita=entita,
        zaznam_id=zaznam_id,
        druh=vstup.druh,
        text=text,
        termin=_parse_datum(vstup.termin, "termín"),
        vlastnik_user_id=vlastnik,
        vytvoril_user_id=user.id,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _aktivita_out(a)


@router.patch("/aktivity/{aktivita_id}", response_model=AktivitaOut)
def uprav_aktivitu(
    aktivita_id: int,
    vstup: AktivitaUprava,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    a = db.get(CrmAktivita, aktivita_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivita neexistuje")
    _over_pristup_k_zaznamu(db, a.entita, a.zaznam_id, user)

    if vstup.text is not None:
        text = vstup.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Text aktivity nesmí být prázdný.")
        a.text = text
    if vstup.termin is not None:
        a.termin = _parse_datum(vstup.termin, "termín")
    if vstup.hotovo is not None:
        a.hotovo = bool(vstup.hotovo)
        a.hotovo_at = datetime.now() if vstup.hotovo else None
    db.commit()
    db.refresh(a)
    return _aktivita_out(a)


@router.delete("/aktivity/{aktivita_id}")
def smaz_aktivitu(
    aktivita_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    a = db.get(CrmAktivita, aktivita_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivita neexistuje")
    _over_pristup_k_zaznamu(db, a.entita, a.zaznam_id, user)
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.get("/ukoly", response_model=list[UkolOut])
def moje_ukoly(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Nedokončené úkoly s termínem, které patří přihlášenému uživateli.

    Napříč zákazníky, případy, nabídkami, objednávkami i projekty – aby OZ
    nemusel proklikávat záznamy, aby zjistil, co má dnes udělat. Skládání
    soupisu (včetně názvu záznamu a cesty pro proklik) je v `crm/ukoly.py`,
    ať ho souhrn na Rozcestníku počítá stejně.
    """
    return ukoly_modul.moje_ukoly(db, user)


# ---- nastavení: stavy pipeline ----------------------------------------------
def _stav_out(s: CrmStav) -> StavOut:
    return StavOut(
        id=s.id,
        entita=s.entita,
        klic=s.klic,
        nazev=s.nazev,
        poradi=s.poradi,
        barva=s.barva or "",
        druh=s.druh,
    )


def _over_entitu(entita: str) -> str:
    if entita not in ENTITY_CRM:
        raise HTTPException(status_code=422, detail=f"Neznámá entita: {entita}")
    return entita


def _klic_ze_nazvu(db: Session, entita: str, nazev: str) -> str:
    """Strojový klíč z názvu stavu (bez diakritiky, unikátní v rámci entity)."""
    import re
    import unicodedata

    zaklad = unicodedata.normalize("NFKD", nazev).encode("ascii", "ignore").decode()
    zaklad = re.sub(r"[^a-zA-Z0-9]+", "_", zaklad).strip("_").lower() or "stav"
    klic = zaklad
    i = 2
    while db.query(CrmStav.id).filter(CrmStav.entita == entita, CrmStav.klic == klic).first():
        klic = f"{zaklad}_{i}"
        i += 1
    return klic


@router.get("/stavy/{entita}", response_model=list[StavOut])
def seznam_stavu(
    entita: str,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Stavy entity (čtení stačí právo na sekci – kanban je z nich složený)."""
    return [_stav_out(s) for s in stavy_modul.seznam(db, _over_entitu(entita))]


@router.post("/stavy/{entita}", response_model=StavOut)
def pridej_stav(
    entita: str,
    vstup: StavVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    _over_entitu(entita)
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název stavu je povinný.")
    if vstup.druh not in DRUHY_STAVU:
        raise HTTPException(status_code=422, detail=f"Neznámý druh stavu: {vstup.druh}")

    poradi = vstup.poradi
    if poradi is None:
        posledni = (
            db.query(func.max(CrmStav.poradi)).filter(CrmStav.entita == entita).scalar()
        )
        poradi = int(posledni or 0) + 1
    s = CrmStav(
        entita=entita,
        klic=_klic_ze_nazvu(db, entita, nazev),
        nazev=nazev,
        poradi=poradi,
        barva=(vstup.barva or "").strip(),
        druh=vstup.druh,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _stav_out(s)


@router.put("/stavy/{stav_id}", response_model=StavOut)
def uprav_stav(
    stav_id: int,
    vstup: StavVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Přejmenování / přebarvení stavu. `klic` se NEMĚNÍ – drží ho záznamy
    i historie, takže jeho změna by je odpojila."""
    s = db.get(CrmStav, stav_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Stav neexistuje")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název stavu je povinný.")
    if vstup.druh not in DRUHY_STAVU:
        raise HTTPException(status_code=422, detail=f"Neznámý druh stavu: {vstup.druh}")
    s.nazev = nazev
    s.barva = (vstup.barva or "").strip()
    s.druh = vstup.druh
    if vstup.poradi is not None:
        s.poradi = vstup.poradi
    db.commit()
    db.refresh(s)
    return _stav_out(s)


@router.put("/stavy/{entita}/poradi", response_model=list[StavOut])
def zmen_poradi_stavu(
    entita: str,
    vstup: StavyPoradi,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Nové pořadí sloupců kanbanu (seznam id ve výsledném pořadí)."""
    _over_entitu(entita)
    stavy = {s.id: s for s in stavy_modul.seznam(db, entita)}
    for poradi, sid in enumerate(vstup.poradi):
        s = stavy.get(sid)
        if s is not None:
            s.poradi = poradi
    db.commit()
    return [_stav_out(s) for s in stavy_modul.seznam(db, entita)]


@router.delete("/stavy/{stav_id}")
def smaz_stav(
    stav_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Smaže sloupec kanbanu. Nelze smazat stav, ve kterém něco je – jinak by
    záznamy skončily ve „ztraceném" stavu bez sloupce."""
    s = db.get(CrmStav, stav_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Stav neexistuje")
    if s.entita == "op":
        pocet = (
            db.query(func.count(ObchodniPripad.id))
            .filter(ObchodniPripad.stav == s.klic)
            .scalar()
        )
        if int(pocet or 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"Ve stavu {s.nazev} je {int(pocet)} případů – nejdřív je přesuň.",
            )
    if len(stavy_modul.seznam(db, s.entita)) <= 1:
        raise HTTPException(status_code=409, detail="Poslední stav smazat nelze.")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---- nastavení: kategorie obchodního případu --------------------------------
def _kategorie_out(k: CrmKategorie) -> KategorieOut:
    return KategorieOut(
        id=k.id,
        klic=k.klic,
        nazev=k.nazev,
        popis=k.popis or "",
        poradi=k.poradi,
        typ_nabidky=k.typ_nabidky or "",
        aktivni=bool(k.aktivni),
    )


def _over_typ_nabidky(typ: str) -> str:
    """Prázdné = kategorie bez výpočtu. Jinak to musí být typ, který nabídkovač
    zná – jinak by tlačítko na kartě případu zakládalo nabídku, kterou žádný
    výpočet neumí otevřít."""
    typ = (typ or "").strip()
    if typ and typ not in kategorie_modul.TYPY_NABIDKY_PRO_KATEGORII:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Neznámý typ nabídky: {typ}. "
                f"Povolené: {', '.join(kategorie_modul.TYPY_NABIDKY_PRO_KATEGORII)} "
                "(nebo prázdné, pokud ke kategorii výpočet není)."
            ),
        )
    return typ


@router.get("/kategorie", response_model=list[KategorieOut])
def seznam_kategorii(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Kategorie případu. Čtení stačí běžné právo na CRM – vybírá se z nich
    ve formuláři případu a kreslí se z nich tlačítka „+ nabídka"."""
    return [_kategorie_out(k) for k in kategorie_modul.seznam(db)]


@router.post("/kategorie", response_model=KategorieOut)
def pridej_kategorii(
    vstup: KategorieVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kategorie je povinný.")
    typ = _over_typ_nabidky(vstup.typ_nabidky)

    poradi = vstup.poradi
    if poradi is None:
        posledni = db.query(func.max(CrmKategorie.poradi)).scalar()
        poradi = int(posledni or 0) + 1
    k = CrmKategorie(
        klic=kategorie_modul.klic_ze_nazvu(db, nazev),
        nazev=nazev,
        popis=(vstup.popis or "").strip(),
        poradi=poradi,
        typ_nabidky=typ,
        aktivni=True if vstup.aktivni is None else bool(vstup.aktivni),
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return _kategorie_out(k)


# POZOR na pořadí definic: `/kategorie/poradi` musí být PŘED
# `/kategorie/{kategorie_id}`, jinak by ho FastAPI namatchovalo jako id
# a požadavek by skončil na „poradi není číslo".
@router.put("/kategorie/poradi", response_model=list[KategorieOut])
def zmen_poradi_kategorii(
    vstup: StavyPoradi,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Nové pořadí (seznam id ve výsledném pořadí) – řídí, v jakém sledu se
    kategorie nabízejí ve formuláři a na kartě případu."""
    podle_id = {k.id: k for k in kategorie_modul.seznam(db)}
    for poradi, kid in enumerate(vstup.poradi):
        k = podle_id.get(kid)
        if k is not None:
            k.poradi = poradi
    db.commit()
    return [_kategorie_out(k) for k in kategorie_modul.seznam(db)]


@router.put("/kategorie/{kategorie_id}", response_model=KategorieOut)
def uprav_kategorii(
    kategorie_id: int,
    vstup: KategorieVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Přejmenování a přepnutí výpočtu. `klic` se NEMĚNÍ – nesou ho uložené
    případy i typ nabídky, takže by se jeho změnou odpojily."""
    k = db.get(CrmKategorie, kategorie_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie neexistuje")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kategorie je povinný.")
    k.nazev = nazev
    k.popis = (vstup.popis or "").strip()
    k.typ_nabidky = _over_typ_nabidky(vstup.typ_nabidky)
    if vstup.aktivni is not None:
        k.aktivni = bool(vstup.aktivni)
    if vstup.poradi is not None:
        k.poradi = vstup.poradi
    db.commit()
    db.refresh(k)
    return _kategorie_out(k)


@router.delete("/kategorie/{kategorie_id}")
def smaz_kategorii(
    kategorie_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Smaže kategorii, kterou nikdo nepoužívá.

    Když ji případy mají, mazání se odmítne a nabídne se vypnutí (`aktivni`):
    smazaná kategorie by z historických případů udělala záznamy se strojovým
    klíčem, který nikdo nepřeloží.
    """
    k = db.get(CrmKategorie, kategorie_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie neexistuje")

    pocet = (
        db.query(func.count(ObchodniPripad.id))
        .filter(ObchodniPripad.kategorie.any(k.klic))
        .scalar()
    )
    if int(pocet or 0) > 0:
        n = int(pocet)
        kolik = "1 případ" if n == 1 else f"{n} případy" if n < 5 else f"{n} případů"
        raise HTTPException(
            status_code=409,
            detail=(
                f"Kategorii {k.nazev} má {kolik}. Smazat ji nelze – "
                "vypni ji, ať se nenabízí u nových případů."
            ),
        )
    db.delete(k)
    db.commit()
    return {"ok": True}


# ---- nastavení: vlastní pole na obrazovkách ---------------------------------
def _pole_out(pole: CrmVlastniPole) -> VlastniPoleOut:
    return VlastniPoleOut(
        id=pole.id,
        entita=pole.entita,
        klic=pole.klic,
        nazev=pole.nazev,
        typ=pole.typ,
        volby=list(pole.volby or []),
        napoveda=pole.napoveda or "",
        povinne=bool(pole.povinne),
        v_seznamu=bool(pole.v_seznamu),
        poradi=pole.poradi,
    )


# „Rozhodneme se sledovat parametr, který dnes nepotřebuju" – admin si pole
# přidá sám, bez migrace a nasazení. Definice tady, hodnoty v `extra` záznamu.
@router.get("/vlastni-pole/{entita}", response_model=list[VlastniPoleOut])
def seznam_vlastnich_poli(
    entita: str,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Definice polí dané obrazovky.

    Čtení stačí běžné právo na CRM – formulář i seznam se z toho vykreslují
    každému. Měnit je smí jen `crm_nastaveni`.
    """
    pole_modul.over_entitu(entita)
    return [VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, entita)]


@router.post("/vlastni-pole/{entita}", response_model=VlastniPoleOut)
def pridej_vlastni_pole(
    entita: str,
    vstup: VlastniPoleVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    pole_modul.over_entitu(entita)
    pole_modul.over_typ(vstup.typ)
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název pole je povinný.")

    volby = [v.strip() for v in (vstup.volby or []) if v and v.strip()]
    if vstup.typ == "vyber" and not volby:
        raise HTTPException(
            status_code=422,
            detail="U pole typu „výběr ze seznamu“ vypiš aspoň jednu volbu.",
        )

    poradi = vstup.poradi
    if poradi is None:
        posledni = (
            db.query(func.max(CrmVlastniPole.poradi))
            .filter(CrmVlastniPole.entita == entita)
            .scalar()
        )
        poradi = int(posledni or 0) + 1

    pole = CrmVlastniPole(
        entita=entita,
        klic=pole_modul.uniq_klic(db, entita, nazev),
        nazev=nazev,
        typ=vstup.typ,
        volby=volby,
        napoveda=(vstup.napoveda or "").strip(),
        povinne=bool(vstup.povinne),
        v_seznamu=bool(vstup.v_seznamu),
        poradi=poradi,
        vytvoril_user_id=user.id,
    )
    db.add(pole)
    db.commit()
    db.refresh(pole)
    return _pole_out(pole)


@router.put("/vlastni-pole/{pole_id}", response_model=VlastniPoleOut)
def uprav_vlastni_pole(
    pole_id: int,
    vstup: VlastniPoleUprava,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Úprava pole. `klic` se NEMĚNÍ – drží ho uložené hodnoty v `extra`,
    takže jeho změnou by se data odpojila od definice."""
    pole = db.get(CrmVlastniPole, pole_id)
    if pole is None:
        raise HTTPException(status_code=404, detail="Pole neexistuje")

    if vstup.nazev is not None:
        nazev = vstup.nazev.strip()
        if not nazev:
            raise HTTPException(status_code=422, detail="Název pole je povinný.")
        pole.nazev = nazev
    if vstup.typ is not None:
        pole_modul.over_typ(vstup.typ)
        pole.typ = vstup.typ
    if vstup.volby is not None:
        pole.volby = [v.strip() for v in vstup.volby if v and v.strip()]
    if pole.typ == "vyber" and not list(pole.volby or []):
        raise HTTPException(
            status_code=422,
            detail="U pole typu „výběr ze seznamu“ musí zůstat aspoň jedna volba.",
        )
    if vstup.napoveda is not None:
        pole.napoveda = vstup.napoveda.strip()
    if vstup.povinne is not None:
        pole.povinne = bool(vstup.povinne)
    if vstup.v_seznamu is not None:
        pole.v_seznamu = bool(vstup.v_seznamu)
    if vstup.poradi is not None:
        pole.poradi = vstup.poradi

    db.commit()
    db.refresh(pole)
    return _pole_out(pole)


@router.put("/vlastni-pole/{entita}/poradi", response_model=list[VlastniPoleOut])
def zmen_poradi_poli(
    entita: str,
    vstup: VlastniPolePoradi,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Nové pořadí polí ve formuláři (seznam id ve výsledném pořadí)."""
    pole_modul.over_entitu(entita)
    mapa = {p.id: p for p in pole_modul.seznam(db, entita)}
    for poradi, pid in enumerate(vstup.poradi):
        p = mapa.get(pid)
        if p is not None:
            p.poradi = poradi
    db.commit()
    return [VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, entita)]


@router.delete("/vlastni-pole/{pole_id}")
def smaz_vlastni_pole(
    pole_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Smaže definici pole. Uložené hodnoty se NEMAŽOU – jen se přestanou
    zobrazovat. Osiřelé klíče v JSONB nevadí, a když se pole smaže omylem,
    dají se data vrátit tím, že se pole založí znovu se stejným klíčem.

    Kolik záznamů hodnotu má, vracíme v odpovědi – ať je po smazání vidět,
    o kolika datech se mlčí.
    """
    pole = db.get(CrmVlastniPole, pole_id)
    if pole is None:
        raise HTTPException(status_code=404, detail="Pole neexistuje")

    model = pole_modul.MODELY.get(pole.entita)
    s_hodnotou = 0
    if model is not None:
        s_hodnotou = sum(
            1 for (extra,) in db.query(model.extra).all() if (extra or {}).get(pole.klic) is not None
        )
    db.delete(pole)
    db.commit()
    return {"ok": True, "zaznamu_s_hodnotou": s_hodnotou, "klic": pole.klic}


# ---- nastavení: číselné řady ------------------------------------------------
@router.get("/rady", response_model=list[RadaOut])
def seznam_rad(
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Řady aktuálního roku + ukázka, jak bude vypadat příští číslo."""
    rok = ciselne_rady.aktualni_rok()
    out: list[RadaOut] = []
    for entita in ENTITY_CRM:
        rada = (
            db.query(CiselnaRada)
            .filter(CiselnaRada.entita == entita, CiselnaRada.rok == rok)
            .first()
        )
        if rada is None:
            prefix = ciselne_rady.PREFIXY[entita]
            sirka = ciselne_rady.VYCHOZI_SIRKA
            dalsi = 1
        else:
            prefix, sirka, dalsi = rada.prefix, int(rada.sirka), int(rada.dalsi_cislo)
        out.append(
            RadaOut(
                entita=entita,
                rok=rok,
                prefix=prefix,
                sirka=sirka,
                dalsi_cislo=dalsi,
                pouzito=ciselne_rady.pocet_pouzitych(db, entita, rok),
                ukazka=ciselne_rady.formatuj(prefix, rok, dalsi, sirka),
            )
        )
    return out


@router.put("/rady/{entita}", response_model=RadaOut)
def uprav_radu(
    entita: str,
    vstup: RadaVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Posun startu řady nebo změna šířky čísla.

    Typický důvod: srovnat řadu s Raynetem, aby appka nezačala vydávat čísla,
    která už Raynet použil. Zpátky posunout jde jen nad nejvyšší vydané číslo –
    jinak by vznikla duplicita viditelných ID.
    """
    _over_entitu(entita)
    rok = ciselne_rady.aktualni_rok()
    rada = (
        db.query(CiselnaRada)
        .filter(CiselnaRada.entita == entita, CiselnaRada.rok == rok)
        .with_for_update()
        .first()
    )
    if rada is None:
        rada = CiselnaRada(
            entita=entita,
            rok=rok,
            prefix=ciselne_rady.PREFIXY[entita],
            sirka=ciselne_rady.VYCHOZI_SIRKA,
            dalsi_cislo=1,
        )
        db.add(rada)
        db.flush()

    if vstup.sirka is not None:
        if not 1 <= int(vstup.sirka) <= 8:
            raise HTTPException(status_code=422, detail="Šířka čísla musí být 1–8.")
        rada.sirka = int(vstup.sirka)
    if vstup.dalsi_cislo is not None:
        nove = int(vstup.dalsi_cislo)
        if nove < 1:
            raise HTTPException(status_code=422, detail="Další číslo musí být aspoň 1.")
        if nove < int(rada.dalsi_cislo):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Řada už vydala čísla do {int(rada.dalsi_cislo) - 1}. "
                    "Zpět jít nelze, vznikla by duplicitní ID."
                ),
            )
        rada.dalsi_cislo = nove
    db.commit()
    db.refresh(rada)
    return RadaOut(
        entita=entita,
        rok=rok,
        prefix=rada.prefix,
        sirka=int(rada.sirka),
        dalsi_cislo=int(rada.dalsi_cislo),
        pouzito=ciselne_rady.pocet_pouzitych(db, entita, rok),
        ukazka=ciselne_rady.formatuj(
            rada.prefix, rok, int(rada.dalsi_cislo), int(rada.sirka)
        ),
    )


@router.get("/rady/{entita}/navrh-startu")
def navrh_startu(
    entita: str,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Doporučený start řady podle nejvyššího známého Raynetího čísla.

    Kvůli koexistenci: dokud běží Raynet, appka by měla čísla vydávat NAD jeho
    nejvyšším, aby se stejné ID neobjevilo dvakrát s jiným obsahem.
    """
    _over_entitu(entita)
    if entita != "op":
        return {"entita": entita, "navrh": None, "duvod": "Raynetí čísla známe jen u případů."}
    nejvyssi = ciselne_rady.nejvyssi_raynet_cislo(db)
    if nejvyssi is None:
        return {
            "entita": entita,
            "navrh": None,
            "duvod": "Žádné Raynetí číslo případu se nenašlo (ani v CRM, ani ve složkách konektoru).",
        }
    return {
        "entita": entita,
        "navrh": ciselne_rady.doporuceny_start(nejvyssi),
        "duvod": (
            f"Nejvyšší Raynetí číslo letos je {nejvyssi}. Necháváme rezervu do další "
            "stovky, aby si obě řady během koexistence nezkřížily cestu."
        ),
    }
