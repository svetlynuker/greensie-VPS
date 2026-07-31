"""API CRM: Zákazníci (leady/klienti), Obchodní případy, aktivity, nastavení.

Dvě věci, které se prolínají všemi endpointy:

1. VIDITELNOST ZÁZNAMŮ. Každý seznam jde přes `pristup.omez_na_moje`, každý
   detail přes `pristup.vyzaduj_zaznam`. Kdo nemá právo `crm_vse`, vidí jen
   svoje záznamy a cizí pro něj neexistují (404, ne 403 – viz `pristup.py`).

2. KOEXISTENCE S RAYNETEM. Případ může nést Raynetí číslo (`raynet_code`)
   vedle vlastního (`cislo`). Appka si čísluje sama, ale Raynetí kód nikdy
   nepřepisuje – stojí na něm párování složek na Disku a Freelo projektů.
"""

import re
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.crm import ares as ares_modul
from app.crm import audit as audit_modul
from app.crm.novinky import vyzaduj_novinky
from app.crm import mapa as mapa_modul
from app.crm import (
    ciselne_rady,
    hledani as hledani_modul,
    timeline as timeline_modul,
    hromadne as hromadne_modul,
    povinna_pole as povinna_pole_modul,
    nastaveni_crm,
    statistiky as statistiky_modul,
    kalendar,
    opakovani as opakovani_modul,
    diagramy as diagramy_modul,
    kategorie as kategorie_modul,
    nabidky_pipeline,
    notifikace as notifikace_modul,
    oblibene as oblibene_modul,
    odberna_mista as om_modul,
    sablony as sablony_modul,
    stavy as stavy_modul,
    ukoly as ukoly_modul,
    vlastni_pole as pole_modul,
)
from app.crm.models import (
    DRUHY_AKTIVITY,
    DRUHY_STAVU,
    ROZSAHY_SERIE,
    STAVY_AKTIVITY,
    STAVY_UZAVRENE,
    ENTITY_AKTIVIT,
    ENTITY_CRM,
    KATEGORIE_OP,
    TYPY_ZAKAZNIKA,
    CiselnaRada,
    CrmAktivita,
    CrmDiagram,
    CrmKategorie,
    CrmKategorieAktivity,
    CrmProjekt,
    CrmSablona,
    CrmSerieAktivit,
    CrmStav,
    CrmStavHistorie,
    CrmVlastniPole,
    ObchodniPripad,
    Objednavka,
    OdberneMisto,
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
    AuditOut,
    MapaBodOut,
    AktivitaUprava,
    AktivitaVstup,
    AresOut,
    DiagramOut,
    EmailOut,
    EmailVstup,
    HromadnaAktivitaVstup,
    HromadnyStavVstup,
    HromadnyVlastnikVstup,
    KalendarOut,
    KalendarUdalostOut,
    KanbanOut,
    KanbanSloupec,
    KategorieAktivityOut,
    KategorieAktivityVstup,
    KategorieOut,
    KategorieVstup,
    KontaktOut,
    KontaktVstup,
    NabidkaKanbanOut,
    NabidkaKanbanSloupec,
    NabidkaRadekOut,
    NabidkaZmenaStavuVstup,
    NastaveniNotifikaciOut,
    NastaveniNotifikaciVstup,
    NotifikaceOut,
    NotifikacePrectenoVstup,
    NotifikaceSouhrnOut,
    OblibeneOut,
    OblibeneVstup,
    OdbernaMistaOut,
    OdberneMistoOut,
    OdberneMistoPripaduVstup,
    OdberneMistoVstup,
    PripadDetailOut,
    PripadRadekOut,
    PripadUprava,
    PripadVstup,
    RadaOut,
    RadaVstup,
    SablonaOut,
    SablonaTextuOut,
    SablonaTextuVstup,
    SablonaPouzitiOut,
    SablonaVstup,
    SablonyOut,
    StavOut,
    StavVstup,
    StavyPoradi,
    SymbolOut,
    UdalostOut,
    UdalostVstup,
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
        extra=pole_modul.s_vypocty(db, "zakaznik", z, z.extra),
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


def dny_ve_fazi(db: Session, entita: str, zaznamy: list) -> dict[int, int]:
    """{id: kolik dní záznam visí v aktuálním stavu} — jedním dotazem (CRM-44).

    Bere se poslední zápis v `crm_stav_historie`; případ, který stav nikdy
    neměnil, se počítá od založení. Bez fallbacku na založení by čerstvě
    vzniklé případy hlásily 0 dní i po měsíci, což je horší než nic.
    """
    if not zaznamy:
        return {}
    ids = [z.id for z in zaznamy]
    posledni: dict[int, object] = {}
    for h in (
        db.query(CrmStavHistorie)
        .filter(CrmStavHistorie.entita == entita, CrmStavHistorie.zaznam_id.in_(ids))
        .order_by(CrmStavHistorie.id)
        .all()
    ):
        posledni[h.zaznam_id] = h.zmeneno_at

    dnes = datetime.now()
    out: dict[int, int] = {}
    for z in zaznamy:
        od = posledni.get(z.id) or getattr(z, "vytvoreno_at", None)
        if od is None:
            out[z.id] = 0
            continue
        # Časy z DB můžou mít časovou zónu, `datetime.now()` ne — porovnáváme
        # holá data, jinak Python vyhodí „can't subtract offset-naive…".
        od_bez_zony = od.replace(tzinfo=None) if getattr(od, "tzinfo", None) else od
        out[z.id] = max(0, (dnes - od_bez_zony).days)
    return out


def _pripad_radek(
    p: ObchodniPripad,
    stav_nazvy: dict[str, CrmStav],
    extra_text: dict | None = None,
    dni: int = 0,
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
        dni_ve_fazi=dni,
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
    misto = db.get(OdberneMisto, p.odberne_misto_id) if p.odberne_misto_id else None
    return PripadDetailOut(
        **zaklad,
        popis=p.popis or "",
        duvod_prohry=p.duvod_prohry or "",
        uzavreno_at=_iso(p.uzavreno_at),
        vlastnik_user_id=p.vlastnik_user_id,
        spoluvlastnici=list(p.spoluvlastnici or []),
        raynet_id=p.raynet_id,
        odberne_misto_id=p.odberne_misto_id,
        odberne_misto_nazev=misto.nazev if misto is not None else "",
        nabidky=_nabidky_pripadu(db, p.id),
        extra_text={},
        extra=pole_modul.s_vypocty(db, "op", p, p.extra),
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
    dni = dny_ve_fazi(db, "op", pripady)
    return [_pripad_radek(p, mapa, extra_texty.get(p.id), dni.get(p.id, 0)) for p in pripady]


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
    dni = dny_ve_fazi(db, "op", pripady)

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
                zaznamy=[
                    _pripad_radek(p, mapa, extra_texty.get(p.id), dni.get(p.id, 0))
                    for p in v_koši
                ],
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
    # Kdo je na případu NOVĚ – jen jim se ozve „máš to na starost" (CRM-10).
    # Porovnává se před přepsáním; bez toho by notifikace chodila po každém
    # uložení, i když se vlastníci nezměnili.
    drivejsi = {p.vlastnik_user_id, *(p.spoluvlastnici or [])}
    pribyli = [i for i in [vlastnik, *spolu] if i and i not in drivejsi]
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

    notifikace_modul.ohlas_prirazeni(
        db, user, f"{p.cislo} · {p.nazev}".strip(" ·"), f"/pripady/detail/{p.id}", pribyli
    )
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

    # CRM-30: pole povinná pro přechod do cílového stavu. Hlídá se PŘECHOD,
    # ne uložení — případ se zakládá rozpracovaný a nutit cenu hned při vzniku
    # by lidi jen otravovalo (psali by tam nuly).
    chybi = povinna_pole_modul.chybejici(db, p, novy.klic)
    if chybi:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Do stavu {novy.nazev} nejde přejít, dokud nevyplníš: "
                + ", ".join(chybi)
                + "."
            ),
        )

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
        notifikace_modul.ohlas_zmenu_stavu(
            db,
            user,
            f"{p.cislo} · {p.nazev}".strip(" ·"),
            f"/pripady/detail/{p.id}",
            novy.nazev,
            p.vlastnik_user_id,
            p.spoluvlastnici,
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
def _nabidka_radek(
    db: Session, n, stav_mapa: dict[str, CrmStav], extra_text: dict | None = None
) -> NabidkaRadekOut:
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
        extra_text=extra_text or {},
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
    texty = pole_modul.hodnoty_pro_seznam(db, "nab", nabidky)
    radky = [_nabidka_radek(db, n, mapa, texty.get(n.id)) for n in nabidky]
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
    texty = pole_modul.hodnoty_pro_seznam(db, "nab", nabidky)

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
            zaznamy=[
                _nabidka_radek(db, n, mapa, texty.get(n.id)) for n in koše.get(s.klic, [])
            ],
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
    texty = pole_modul.hodnoty_pro_seznam(db, "nab", [n])
    return _nabidka_radek(db, n, _mapa_stavu(db, "nab"), texty.get(n.id))


# ---- aktivity a poznámky ----------------------------------------------------
def _over_pristup_k_zaznamu(db: Session, entita: str, zaznam_id: int, user: User) -> None:
    """Aktivity se řídí právy nadřazeného záznamu, ne vlastními.

    Nabídka, objednávka ani projekt vlastníka nemají — visí na obchodním
    případu, takže se práva odvozují od něj. Nabídka bez případu (ta, co vznikla
    v nabídkovači před CRM) je výjimka: dostane se k ní jen `crm_vse`, protože
    nikomu nepatří a nechceme, aby se „nikomu nepatřící" data zjevila všem.
    """
    # Nabídka se importuje lokálně stejně jako na dalších místech tohoto modulu
    # (nabídkovač a CRM se navzájem neimportují na úrovni modulu).
    from app.nabidkovac.models import Nabidka

    # Odběrné místo nemá aktivity, ale audit ano — a práva dědí ze zákazníka
    # (kdo vidí firmu, vidí i její provozovny, viz CRM-46).
    if entita == "om":
        misto = db.get(OdberneMisto, zaznam_id)
        if misto is None:
            raise HTTPException(status_code=404, detail="Odběrné místo neexistuje")
        vyzaduj_zaznam(db.get(Zakaznik, misto.zakaznik_id), user, "Zákazník")
        return

    if entita not in ENTITY_AKTIVIT:
        raise HTTPException(status_code=422, detail=f"Neznámá entita: {entita}")

    if entita == "zakaznik":
        vyzaduj_zaznam(db.get(Zakaznik, zaznam_id), user, "Zákazník")
        return
    if entita == "op":
        vyzaduj_zaznam(db.get(ObchodniPripad, zaznam_id), user, "Obchodní případ")
        return

    model, popis = {
        "nab": (Nabidka, "Nabídka"),
        "obj": (Objednavka, "Objednávka"),
        "pro": (CrmProjekt, "Projekt"),
    }[entita]
    zaznam = db.get(model, zaznam_id)
    if zaznam is None:
        raise HTTPException(status_code=404, detail=f"{popis} neexistuje")
    if zaznam.obchodni_pripad_id is None:
        if not muze_vse(user):
            raise HTTPException(status_code=404, detail=f"{popis} neexistuje")
        return
    vyzaduj_zaznam(
        db.get(ObchodniPripad, zaznam.obchodni_pripad_id), user, "Obchodní případ"
    )


def _popis_serie(a: CrmAktivita) -> str:
    """Lidský popis opakování („každý týden do 31.12.2026"), nebo prázdno."""
    return opakovani_modul.popis_pravidla(a.serie) if a.serie is not None else ""


def _over_rozsah(rozsah: str) -> str:
    if rozsah not in ROZSAHY_SERIE:
        raise HTTPException(
            status_code=422,
            detail=f"Neznámý rozsah změny: {rozsah}. Povolené: {', '.join(ROZSAHY_SERIE)}.",
        )
    return rozsah


def _vyzaduj_aktivitu(db: Session, aktivita_id: int, user: User) -> CrmAktivita:
    """Najde aktivitu a ověří, že s ní uživatel smí něco dělat.

    Nahradilo to samostatné `_over_pristup_k_zaznamu(a.entita, ...)`, které
    u SOUKROMÉ události padalo na „Neznámá entita: None" — soukromá aktivita
    žádný záznam nemá, takže ji nešlo upravit ani smazat.

    Kontroluje se obojí: přístup k nadřazenému záznamu (když existuje)
    a nárok na aktivitu samotnou (`kalendar.muze_menit`). Bez druhé kontroly by
    OZ mohl přesunout kolegovi schůzku u klienta, kterého oba vidí.
    """
    a = db.get(CrmAktivita, aktivita_id)
    if a is None:
        raise HTTPException(status_code=404, detail="Aktivita neexistuje")
    if a.entita and a.zaznam_id:
        _over_pristup_k_zaznamu(db, a.entita, a.zaznam_id, user)
    if not kalendar.muze_menit(a, user):
        # 404, ne 403 — cizí soukromá aktivita se nemá projevit ani existencí.
        raise HTTPException(status_code=404, detail="Aktivita neexistuje")
    return a


def _aktivita_out(a: CrmAktivita) -> AktivitaOut:
    return AktivitaOut(
        id=a.id,
        entita=a.entita,
        zaznam_id=a.zaznam_id,
        druh=a.druh,
        nazev=a.nazev or "",
        text=a.text or "",
        termin=_iso(a.termin),
        zacatek=_iso(a.zacatek),
        delka_min=a.delka_min,
        konec=_iso(a.konec),
        priorita=a.priorita or "stredni",
        misto=a.misto or "",
        kategorie_id=a.kategorie_id,
        kategorie_nazev=(a.kategorie.nazev if a.kategorie else ""),
        kategorie_barva=(a.kategorie.barva if a.kategorie else ""),
        stav=a.stav,
        vysledek=a.vysledek or "",
        soukroma=bool(a.soukroma),
        ucastnici=list(a.ucastnici or []),
        serie_id=a.serie_id,
        serie_popis=_popis_serie(a),
        vlastnik_user_id=a.vlastnik_user_id,
        vlastnik_jmeno=_jmeno(a.vlastnik),
        vytvoril_jmeno=_jmeno(a.vytvoril),
        vytvoreno_at=_iso(a.vytvoreno_at),
    )


def _over_kategorii_aktivity(db: Session, kategorie_id: int | None) -> int | None:
    """Barevný štítek aktivity. Chybu z modulu přeloží na čitelnou 422."""
    try:
        return kategorie_modul.over_kategorii_aktivity(db, kategorie_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


def _over_ucastniky(db: Session, ids: list[int]) -> list[int]:
    """Ověří, že účastníci existují, a zahodí duplicity."""
    unikatni = list(dict.fromkeys(ids or []))
    if not unikatni:
        return []
    nalezeni = {u for (u,) in db.query(User.id).filter(User.id.in_(unikatni)).all()}
    chybi = [i for i in unikatni if i not in nalezeni]
    if chybi:
        raise HTTPException(
            status_code=422,
            detail=f"Účastník s id {', '.join(map(str, chybi))} neexistuje.",
        )
    return unikatni


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
        # Naplánované nahoře, pak nejnovější – OZ řeší, co ho tlačí.
        # `stav` řadí abecedně: naplanovano < nekonalo_se < realizovano, což
        # náhodou dává přesně požadované pořadí (čekající první).
        .order_by(CrmAktivita.stav, CrmAktivita.vytvoreno_at.desc())
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

    den = _parse_datum(vstup.termin, "termín")
    a = CrmAktivita(
        entita=entita,
        zaznam_id=zaznam_id,
        druh=vstup.druh,
        nazev=(vstup.nazev or "").strip(),
        text=text,
        termin=den,
        zacatek=kalendar.datum_a_cas(den, vstup.cas) if den else None,
        delka_min=vstup.delka_min,
        konec=_parse_datum(vstup.konec, "konec"),
        priorita=vstup.priorita,
        misto=(vstup.misto or "").strip(),
        kategorie_id=_over_kategorii_aktivity(db, vstup.kategorie_id),
        vlastnik_user_id=vlastnik,
        ucastnici=_over_ucastniky(db, vstup.ucastnici),
        vytvoril_user_id=user.id,
    )
    kalendar.srovnej_termin(a)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _aktivita_out(a)


@router.patch("/aktivity/{aktivita_id}", response_model=AktivitaOut)
def uprav_aktivitu(
    aktivita_id: int,
    vstup: AktivitaUprava,
    rozsah: str = Query(
        default="jen_tuhle",
        description="U aktivity ze série: jen_tuhle / tuto_a_dalsi / celou_serii",
    ),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Úprava aktivity. U série `rozsah` říká, koho se změna dotkne.

    DATUM se hromadně nemění nikdy — u „tuto a další" i „celou sérii" by přesun
    na jeden konkrétní den slil všechny instance do jednoho dne a série by
    přestala být série. Hromadně se mění ČAS, délka, obsah a lidé; datum jen
    u „jen tuhle" (jednorázový přesun porady na pátek).
    """
    a = _vyzaduj_aktivitu(db, aktivita_id, user)
    _over_rozsah(rozsah)
    # Ostatní instance série (bez té právě upravované). Zjišťuje se PŘED
    # změnou termínu — po ní by „tuto a další" bralo jiný výřez.
    dalsi = [x for x in opakovani_modul.dotcene(db, a, rozsah) if x.id != a.id]

    if vstup.nazev is not None:
        a.nazev = vstup.nazev.strip()
    if vstup.text is not None:
        text = vstup.text.strip()
        if not text:
            raise HTTPException(status_code=422, detail="Text aktivity nesmí být prázdný.")
        a.text = text
    if vstup.termin is not None:
        a.termin = _parse_datum(vstup.termin, "termín")
    # Čas se posílá zvlášť od dne. Prázdný string = „zruš hodinu, ať je to
    # celodenní"; None = neměnit.
    if vstup.cas is not None:
        a.zacatek = kalendar.datum_a_cas(a.termin, vstup.cas) if a.termin else None
    if vstup.delka_min is not None:
        a.delka_min = vstup.delka_min
    if vstup.konec is not None:
        # Prázdný string = „zruš vícedenní rozsah".
        a.konec = _parse_datum(vstup.konec, "konec")
    if vstup.priorita is not None:
        a.priorita = vstup.priorita
    if vstup.misto is not None:
        a.misto = vstup.misto.strip()
    if vstup.kategorie_id is not None:
        # -1 je domluvené „odeber kategorii" (None už znamená „neměnit").
        a.kategorie_id = (
            None if vstup.kategorie_id < 0 else _over_kategorii_aktivity(db, vstup.kategorie_id)
        )
    if vstup.ucastnici is not None:
        a.ucastnici = _over_ucastniky(db, vstup.ucastnici)
    if vstup.stav is not None:
        if vstup.stav not in STAVY_AKTIVITY:
            raise HTTPException(status_code=422, detail=f"Neznámý stav aktivity: {vstup.stav}")
        a.stav = vstup.stav
        # Datum uzavření drží stav sám: vrácení do „naplánováno" ho musí smazat,
        # jinak by u čekající aktivity zůstalo, kdy prý byla hotová.
        a.hotovo_at = datetime.now() if vstup.stav in STAVY_UZAVRENE else None
    if vstup.vysledek is not None:
        a.vysledek = vstup.vysledek.strip()
    kalendar.srovnej_termin(a)

    # Přenesení změn na zbytek série. Výsledek a stav se přenášejí schválně
    # taky: „zrušit celou sérii porad, protože se šéf vrací až v září" je
    # legitimní a jinak by to znamenalo odklikat každou zvlášť.
    for x in dalsi:
        if vstup.nazev is not None:
            x.nazev = a.nazev
        if vstup.text is not None:
            x.text = a.text
        if vstup.cas is not None:
            # Datum si každá instance drží svoje, mění se jen hodina.
            x.zacatek = kalendar.datum_a_cas(x.termin, vstup.cas) if x.termin else None
        if vstup.delka_min is not None:
            x.delka_min = a.delka_min
        if vstup.priorita is not None:
            x.priorita = a.priorita
        if vstup.misto is not None:
            x.misto = a.misto
        if vstup.kategorie_id is not None:
            x.kategorie_id = a.kategorie_id
        if vstup.ucastnici is not None:
            x.ucastnici = list(a.ucastnici or [])
        if vstup.stav is not None:
            x.stav = a.stav
            x.hotovo_at = a.hotovo_at
        if vstup.vysledek is not None:
            x.vysledek = a.vysledek
        kalendar.srovnej_termin(x)

    db.commit()
    db.refresh(a)
    return _aktivita_out(a)


@router.delete("/aktivity/{aktivita_id}")
def smaz_aktivitu(
    aktivita_id: int,
    rozsah: str = Query(
        default="jen_tuhle",
        description="U aktivity ze série: jen_tuhle / tuto_a_dalsi / celou_serii",
    ),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Smaže aktivitu; u série podle `rozsah`.

    Pravidlo série se maže až s poslední instancí — dokud aspoň jedna zbývá,
    musí zůstat, aby se u ní dal vypsat popis opakování.
    """
    a = _vyzaduj_aktivitu(db, aktivita_id, user)
    _over_rozsah(rozsah)
    serie_id = a.serie_id
    smazat = opakovani_modul.dotcene(db, a, rozsah)
    if len(smazat) > 1:
        for x in smazat:
            db.delete(x)
        db.commit()
        # Zbylo něco ze série? Když ne, uklidí se i pravidlo.
        if serie_id and not opakovani_modul.instance_serie(db, serie_id):
            serie = db.get(CrmSerieAktivit, serie_id)
            if serie is not None:
                db.delete(serie)
                db.commit()
        return {"ok": True, "smazano": len(smazat)}
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
        povinna_pole=list(s.povinna_pole or []),
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


def _over_povinna_pole(db: Session, klice: list[str]) -> list[str]:
    """Zahodí klíče, které neodpovídají žádnému poli.

    Pole se dá smazat (vlastní pole), takže by v nastavení stavu jinak zůstal
    klíč, který nikdo nevyplní — a případ by nešlo posunout nikdy.
    """
    platne = {p["klic"] for p in povinna_pole_modul.dostupna_pole(db)}
    return [k for k in dict.fromkeys(klice or []) if k in platne]


@router.get("/stavy-pole")
def seznam_poli_pro_povinnost(
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Co všechno lze u stavu označit jako povinné (systémová + vlastní pole).

    Skládá se za běhu, takže vlastní pole se v nabídce objeví hned, jak vzniknou.
    """
    return povinna_pole_modul.dostupna_pole(db)


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
    if vstup.povinna_pole is not None:
        s.povinna_pole = _over_povinna_pole(db, vstup.povinna_pole)
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


# ---- timeline zákazníka (CRM-18) --------------------------------------------
@router.get("/timeline/zakaznik/{zakaznik_id}")
def timeline_zakaznika(
    zakaznik_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Celý děj u zákazníka na jedné chronologické ose.

    Slévá aktivity, vznik případů, nabídek, objednávek a projektů a změny stavů.
    Dnes je to rozsypané do záložek a člověk si děj skládá v hlavě.
    """
    z = vyzaduj_zaznam(db.get(Zakaznik, zakaznik_id), user, "Zákazník")
    return {"udalosti": timeline_modul.pro_zakaznika(db, user, z)}


# ---- globální hledání (CRM-24) ----------------------------------------------
@router.get("/hledat")
def globalni_hledani(
    q: str = Query(default="", description="Hledaný text (aspoň 2 znaky)"),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Jedno pole pro zákazníky, případy, nabídky, objednávky i projekty.

    Každá entita jde přes filtr viditelnosti — bez toho by hledání bylo obchvat
    práv a nejjednodušší způsob, jak zjistit, na čem pracují ostatní.
    """
    return hledani_modul.hledej(db, user, q)


# ---- hromadné akce nad seznamem (CRM-19) ------------------------------------
# Práva se kontrolují u KAŽDÉHO záznamu zvlášť (seznam ID jde z prohlížeče),
# cizí se přeskočí a vrátí v `preskoceno` — ne aby celá dávka spadla.

@router.post("/hromadne/vlastnik")
def hromadne_vlastnik(
    vstup: HromadnyVlastnikVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Přehodí vybrané záznamy na jiného člověka (odchod, dovolená)."""
    try:
        return hromadne_modul.zmen_vlastnika(
            db, vstup.entita, vstup.ids, user, vstup.vlastnik_user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/hromadne/stav")
def hromadne_stav(
    vstup: HromadnyStavVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Posune vybrané případy do stejné fáze. U prohry vyžaduje důvod — jinak by
    tohle byla zadní vrátka pro prohry bez důvodu a rozpad důvodů proher
    v Přehledu obchodu by přestal mít smysl."""
    try:
        return hromadne_modul.zmen_stav(
            db, vstup.ids, user, vstup.stav, vstup.duvod_prohry
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/hromadne/aktivita")
def hromadne_aktivita(
    vstup: HromadnaAktivitaVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Založí aktivitu každému vybranému záznamu; `retez` je naskládá za sebe.

    Vrací `plan` — kdo dostal jaký čas. UI ho ukáže jako potvrzení, protože deset
    omylem naplánovaných telefonátů se maže po jednom.
    """
    den = _parse_datum(vstup.termin, "termín")
    if den is None:
        raise HTTPException(status_code=422, detail="Datum je povinné.")
    if not (vstup.nazev or "").strip():
        raise HTTPException(status_code=422, detail="Název aktivity je povinný.")
    if not vstup.ids:
        raise HTTPException(status_code=422, detail="Nevybral jsi žádný záznam.")
    try:
        return hromadne_modul.naplanuj_aktivity(
            db,
            vstup.entita,
            vstup.ids,
            user,
            vstup.druh,
            vstup.nazev.strip(),
            den,
            vstup.cas,
            vstup.delka_min,
            vstup.retez,
            vstup.vlastnik_user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ---- dokumenty na Disku (CRM-05) --------------------------------------------
# Jeden pár endpointů pro zákazníka i případ — práva a překlad chyb tak žijí na
# jednom místě. Zakládání je POST (mění stav na Disku), čtení GET.

def _slozka_zaznam(db: Session, entita: str, zaznam_id: int, user: User):
    """Ověří přístup a vrátí (klíč entity konektoru, záznam, zákazník)."""
    from app.konektor.crm_slozky import ENTITA_OP, ENTITA_ZAKAZNIK

    if entita == "zakaznik":
        z = vyzaduj_zaznam(db.get(Zakaznik, zaznam_id), user, "Zákazník")
        return ENTITA_ZAKAZNIK, z, z
    if entita == "op":
        p = vyzaduj_zaznam(db.get(ObchodniPripad, zaznam_id), user, "Obchodní případ")
        return ENTITA_OP, p, db.get(Zakaznik, p.zakaznik_id)
    raise HTTPException(
        status_code=422, detail="Složku lze vést jen u zákazníka nebo obchodního případu."
    )


@router.get("/slozka/{entita}/{zaznam_id}")
def slozka_zaznamu(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Odkaz na složku na Disku a její obsah.

    Když složka není, vrací `existuje: false` — appka ji nezakládá sama, protože
    u případu, který za dva dny skončí jako „nezajímavé", by na Disku zůstala
    prázdná složka, kterou nikdo neuklidí (rozhodnutí Dana).

    Obsah se čte z Disku při každém zobrazení. Kopie v naší DB by tvrdila, že
    tam soubor je, i když ho někdo mezitím smazal.
    """
    from app.konektor import crm_slozky

    klic, _, _ = _slozka_zaznam(db, entita, zaznam_id, user)
    ef = crm_slozky.najdi_slozku(db, klic, zaznam_id)
    if ef is None:
        return {"existuje": False, "url": "", "nazev": "", "soubory": []}
    try:
        soubory = crm_slozky.soubory(db, ef)
        chyba = ""
    except Exception as e:  # noqa: BLE001 – odkaz má fungovat i když výpis ne
        soubory, chyba = [], str(e)
    return {
        "existuje": True,
        "url": ef.drive_folder_url or "",
        "nazev": ef.name or "",
        "soubory": soubory,
        "chyba": chyba,
    }


@router.get("/slozka/{entita}/{zaznam_id}/obsah")
def obsah_slozky_zaznamu(
    entita: str,
    zaznam_id: int,
    folder_id: str | None = Query(default=None, description="Podsložka; prázdné = koren"),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Obsah složky nebo její podsložky + cesta pro drobečkovou navigaci.

    `folder_id` prochází z prohlížeče, takže se vždy ověří, že požadovaná složka
    patří pod záznam. Bez toho by si kdokoli mohl vyžádat obsah libovolné složky
    na firemním Disku — třeba mezd (viz `crm_slozky.je_pod_slozkou`).
    """
    from app.konektor import crm_slozky

    klic, _, _ = _slozka_zaznam(db, entita, zaznam_id, user)
    ef = crm_slozky.najdi_slozku(db, klic, zaznam_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="Záznam ještě nemá složku na Disku.")
    try:
        return crm_slozky.obsah_slozky(db, ef, folder_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Disk neodpověděl: {e}")


@router.post("/slozka/{entita}/{zaznam_id}/soubor")
async def nahraj_do_slozky(
    entita: str,
    zaznam_id: int,
    soubor: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Nahraje soubor na Disk do složky záznamu (nebo její podsložky).

    Soubor NEUKLÁDÁME u sebe ani po cestě — projde do Disku a v appce zůstane
    jen odkaz. Dvě kopie téhož dokumentu by znamenaly, že nikdo neví, která je
    ta platná.
    """
    from app.konektor import crm_slozky

    klic, _, _ = _slozka_zaznam(db, entita, zaznam_id, user)
    ef = crm_slozky.najdi_slozku(db, klic, zaznam_id)
    if ef is None:
        raise HTTPException(status_code=404, detail="Záznam ještě nemá složku na Disku.")

    data = await soubor.read()
    if not data:
        raise HTTPException(status_code=422, detail="Soubor je prázdný.")
    # Strop kvůli tomu, že se soubor drží celý v paměti procesu. Větší věci
    # (fotodokumentace z realizace) patří na Disk přímo — appka není přenosová
    # trubka a při 502 z Hetzneru by se stejně nedonesly.
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Soubor je větší než 25 MB — nahraj ho prosím přímo na Disk.",
        )
    try:
        return crm_slozky.nahraj(
            db, ef, folder_id, soubor.filename or "soubor", data, soubor.content_type or ""
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Disk soubor nepřijal: {e}")


@router.post("/slozka/{entita}/{zaznam_id}")
def zaloz_slozku_zaznamu(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Založí složku na Disku (kopií vzoru) a vrátí na ni odkaz.

    Trvá to několik sekund a desítky volání na Disk, proto se to spouští
    tlačítkem. Chyba se hlásí konkrétně — tichý polovytvořený strom složek by
    byl horší než chybová zpráva.
    """
    from app.konektor import crm_slozky
    from app.konektor.logika import NastaveniNepripraveno

    klic, zaznam, zakaznik = _slozka_zaznam(db, entita, zaznam_id, user)
    if zakaznik is None:
        raise HTTPException(status_code=422, detail="Případ nemá navázaného zákazníka.")
    try:
        if klic == crm_slozky.ENTITA_ZAKAZNIK:
            n = crm_slozky._nastaveni(db)
            ef = crm_slozky.zajisti_slozku_zakaznika(
                db, crm_slozky._drive_klient(n), n, zakaznik
            )
        else:
            ef = crm_slozky.zajisti_slozku_pripadu(db, zaznam, zakaznik)
    except NastaveniNepripraveno as e:
        raise HTTPException(status_code=409, detail=f"Konektor na Disk není připravený: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Disk odmítl založení složky: {e}")
    return {"existuje": True, "url": ef.drive_folder_url or "", "nazev": ef.name or ""}


# ---- statistiky obchodu (grafy pro vedení) ----------------------------------
@router.get("/statistiky")
def statistiky_obchodu(
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Souhrny pro dashboard: funnel, forecast, důvody proher a KPI.

    Všechno naráz jedním dotazem — dashboard by jinak dělal pět kol na server
    a „otevřený případ" by se dal definovat na pěti místech jinak.

    Viditelnost je stejná jako v seznamech: OZ vidí svoje čísla, vedení
    (`crm_vse`) čísla firmy. Díky tomu souhrn nad tabulkou a graf nad ním
    vždycky souhlasí.
    """
    fc = statistiky_modul.forecast(db, user)[0]
    return {
        "souhrn": statistiky_modul.souhrn(db, user),
        "funnel": statistiky_modul.funnel(db, user),
        "forecast": fc["mesice"],
        "forecast_bez_terminu": fc["bez_terminu"],
        "duvody_proher": statistiky_modul.duvody_proher(db, user),
    }


@router.get("/muj-den")
def muj_den(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Co člověka dnes tlačí (CRM-16).

    Vedle vlastních úkolů přidává dvě věci, které jinak nikdo nehlídá: případy,
    kde se dlouho nic nestalo, a nabídky odeslané bez reakce. Prahy jsou různé
    schválně — u nabídky je týden bez odpovědi signál, u případu v pipeline ne.
    """
    dnes = date.today()
    ukoly = ukoly_modul.moje_ukoly(db, user)
    return {
        "po_terminu": [u for u in ukoly if u.dni > 0],
        "dnes": [u for u in ukoly if u.dni == 0],
        "nadchazejici": [u for u in ukoly if u.dni < 0][:8],
        "zanedbane_pripady": statistiky_modul.zanedbane_pripady(db, user),
        "nabidky_bez_reakce": statistiky_modul.nabidky_bez_reakce(db, user),
        "prahy": {
            "pripad_dni": statistiky_modul.TICHO_PRIPAD_DNI,
            "nabidka_dni": statistiky_modul.TICHO_NABIDKA_DNI,
        },
        "dnes_datum": dnes.isoformat(),
    }


# ---- kalendář ---------------------------------------------------------------
@router.get("/kalendar", response_model=KalendarOut)
def kalendar_rozsah(
    od: str | None = Query(default=None, description="ISO den; výchozí = pondělí tohoto týdne"),
    do: str | None = Query(default=None, description="ISO den; výchozí = neděle téhož týdne"),
    uzivatele: str | None = Query(
        default=None, description="ID oddělená čárkou; výchozí = jen přihlášený"
    ),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Události v rozsahu dnů pro vybrané lidi.

    Bez parametrů vrací aktuální týden přihlášeného uživatele. `uzivatele`
    slouží ke srovnávání kalendářů — z cizích událostí se ale posílá jen tolik,
    kolik dovolují pravidla v `crm/kalendar.py` (soukromé cizí události nevidí
    ani vedení).
    """
    dnes = date.today()
    zacatek = _parse_datum(od, "od") or kalendar.zacatek_tydne(dnes)
    konec = _parse_datum(do, "do") or (zacatek + timedelta(days=6))
    if konec < zacatek:
        raise HTTPException(status_code=422, detail="Konec rozsahu je před začátkem.")
    # Strop kvůli tomu, aby si nikdo omylem nevyžádal roky dat do jedné odpovědi.
    if (konec - zacatek).days > 92:
        raise HTTPException(status_code=422, detail="Rozsah je nejvýš 92 dní.")

    if uzivatele:
        try:
            ids = [int(x) for x in uzivatele.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Neplatný seznam uživatelů.")
    else:
        ids = [user.id]
    # Cizí kalendář si smí přidat každý – jen z něj neuvidí obsah, viz
    # `kalendar.pro_uzivatele`. Kdyby se přidávání zakázalo, nešlo by hledat
    # společný termín schůzky.

    q = kalendar.v_rozsahu(kalendar.viditelne_pro(db, user, ids), zacatek, konec)
    radky = q.order_by(CrmAktivita.termin, CrmAktivita.zacatek).all()
    return KalendarOut(
        od=zacatek.isoformat(),
        do=konec.isoformat(),
        udalosti=[KalendarUdalostOut(**u) for u in kalendar.udalosti_pro(db, user, radky)],
    )


@router.post("/kalendar/udalost", response_model=AktivitaOut)
def pridej_udalost(
    vstup: UdalostVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Nová událost z kalendáře — s klientem/případem, nebo soukromá.

    Proč vlastní endpoint místo `POST /aktivity/{entita}/{id}`: událost
    zakládaná kliknutím do mřížky nemusí mít žádný záznam (soukromá) a naopak
    může mít vybraný jen jeden ze tří (klient / případ / nabídka). Entita
    v cestě by tohle neumožnila.
    """
    if vstup.druh not in DRUHY_AKTIVITY:
        raise HTTPException(status_code=422, detail=f"Neznámý druh aktivity: {vstup.druh}")

    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název události je povinný.")

    den = _parse_datum(vstup.termin, "termín")
    if den is None:
        raise HTTPException(status_code=422, detail="Datum události je povinné.")

    # Soukromá událost nemá k čemu patřit; u ostatních je záznam nepovinný,
    # ale když se pošle, musí na něj mít uživatel právo.
    entita = (vstup.entita or "").strip() or None
    zaznam_id = vstup.zaznam_id
    if vstup.soukroma:
        entita, zaznam_id = None, None
    elif entita and zaznam_id:
        if entita not in ENTITY_AKTIVIT:
            raise HTTPException(status_code=422, detail=f"Neznámá entita: {entita}")
        _over_pristup_k_zaznamu(db, entita, zaznam_id, user)
    elif entita or zaznam_id:
        raise HTTPException(
            status_code=422,
            detail="U navázané události musí být vybraný typ i konkrétní záznam.",
        )

    vlastnik = vstup.vlastnik_user_id or user.id
    if not db.query(User.id).filter(User.id == vlastnik).first():
        raise HTTPException(status_code=422, detail="Zvolený řešitel neexistuje.")

    a = CrmAktivita(
        entita=entita,
        zaznam_id=zaznam_id,
        druh=vstup.druh,
        nazev=nazev,
        text=(vstup.text or "").strip(),
        termin=den,
        zacatek=kalendar.datum_a_cas(den, vstup.cas),
        delka_min=vstup.delka_min,
        konec=_parse_datum(vstup.konec, "konec"),
        priorita=vstup.priorita,
        misto=(vstup.misto or "").strip(),
        kategorie_id=_over_kategorii_aktivity(db, vstup.kategorie_id),
        stav=vstup.stav,
        vysledek=(vstup.vysledek or "").strip(),
        soukroma=bool(vstup.soukroma),
        vlastnik_user_id=vlastnik,
        ucastnici=_over_ucastniky(db, vstup.ucastnici),
        vytvoril_user_id=user.id,
    )
    kalendar.srovnej_termin(a)
    db.add(a)

    # Opakování: založí se pravidlo a série se rozepíše do skutečných řádků.
    # Materializace (ne dopočítávání za běhu) je vysvětlená v `CrmSerieAktivit` —
    # jedna porada z série se běžně přesouvá a musí se chovat jako každá jiná
    # aktivita.
    if vstup.opakovani is not None:
        try:
            do_data = _parse_datum(vstup.opakovani.do_data, "do data")
            opakovani_modul.over_pravidlo(
                vstup.opakovani.frekvence,
                vstup.opakovani.interval_dni,
                do_data,
                vstup.opakovani.pocet,
            )
            dny = opakovani_modul.termíny(
                den,
                vstup.opakovani.frekvence,
                interval_dni=vstup.opakovani.interval_dni,
                do_data=do_data,
                pocet=vstup.opakovani.pocet,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        serie = CrmSerieAktivit(
            frekvence=vstup.opakovani.frekvence,
            interval_dni=vstup.opakovani.interval_dni,
            do_data=do_data,
            pocet=vstup.opakovani.pocet,
            vytvoril_user_id=user.id,
        )
        db.add(serie)
        db.flush()
        a.serie_id = serie.id
        # U pracovních dnů se první termín mohl posunout z víkendu na pondělí —
        # zadaná aktivita proto musí převzít termín z generátoru, ne ten původní.
        if dny:
            a.termin = dny[0]
            a.zacatek = kalendar.datum_a_cas(dny[0], vstup.cas)
            kalendar.srovnej_termin(a)
        for dalsi in dny[1:]:
            kopie = CrmAktivita(
                entita=a.entita,
                zaznam_id=a.zaznam_id,
                druh=a.druh,
                nazev=a.nazev,
                text=a.text,
                termin=dalsi,
                zacatek=kalendar.datum_a_cas(dalsi, vstup.cas),
                delka_min=a.delka_min,
                priorita=a.priorita,
                misto=a.misto,
                kategorie_id=a.kategorie_id,
                soukroma=a.soukroma,
                vlastnik_user_id=a.vlastnik_user_id,
                ucastnici=list(a.ucastnici or []),
                vytvoril_user_id=user.id,
                serie_id=serie.id,
            )
            kalendar.srovnej_termin(kopie)
            db.add(kopie)

    db.commit()
    db.refresh(a)
    return _aktivita_out(a)


# ---- nastavení: barevné kategorie aktivit (štítky v kalendáři) --------------
def _kategorie_aktivity_out(k: CrmKategorieAktivity) -> KategorieAktivityOut:
    return KategorieAktivityOut(
        id=k.id,
        nazev=k.nazev,
        barva=k.barva or "#7b8794",
        poradi=k.poradi,
        aktivni=bool(k.aktivni),
    )


def _over_barvu(barva: str) -> str:
    """Barva jde do CSS, takže sem nesmí propadnout nic jiného než #rrggbb."""
    b = (barva or "").strip() or "#7b8794"
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", b):
        raise HTTPException(
            status_code=422, detail=f"Barva musí být ve formátu #rrggbb, přišlo: {b}"
        )
    return b.lower()


@router.get("/nastaveni")
def nacti_nastaveni_crm(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Firemní nastavení CRM. Čtení stačí běžné právo — adresu potřebuje
    tlačítko „U nás" u každé schůzky."""
    n = nastaveni_crm.nacti(db)
    return {"nase_adresa": n.nase_adresa or ""}


@router.put("/nastaveni")
def uloz_nastaveni_crm(
    vstup: dict,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    n = nastaveni_crm.nacti(db)
    if "nase_adresa" in vstup:
        n.nase_adresa = str(vstup["nase_adresa"] or "").strip()
    db.commit()
    return {"nase_adresa": n.nase_adresa or ""}


@router.get("/kategorie-aktivit", response_model=list[KategorieAktivityOut])
def seznam_kategorii_aktivit(
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Štítky pro kalendář. Čtení stačí běžné právo — filtruje se jimi."""
    return [_kategorie_aktivity_out(k) for k in kategorie_modul.seznam_aktivit(db)]


@router.post("/kategorie-aktivit", response_model=KategorieAktivityOut)
def pridej_kategorii_aktivity(
    vstup: KategorieAktivityVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kategorie je povinný.")
    if db.query(CrmKategorieAktivity.id).filter(CrmKategorieAktivity.nazev == nazev).first():
        raise HTTPException(status_code=409, detail="Kategorie s tímto názvem už existuje.")
    poradi = vstup.poradi
    if poradi is None:
        poradi = int(db.query(func.max(CrmKategorieAktivity.poradi)).scalar() or 0) + 1
    k = CrmKategorieAktivity(
        nazev=nazev,
        barva=_over_barvu(vstup.barva),
        poradi=poradi,
        aktivni=True if vstup.aktivni is None else bool(vstup.aktivni),
    )
    db.add(k)
    db.commit()
    db.refresh(k)
    return _kategorie_aktivity_out(k)


@router.put("/kategorie-aktivit/{kategorie_id}", response_model=KategorieAktivityOut)
def uprav_kategorii_aktivity(
    kategorie_id: int,
    vstup: KategorieAktivityVstup,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    k = db.get(CrmKategorieAktivity, kategorie_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie neexistuje")
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Název kategorie je povinný.")
    k.nazev = nazev
    k.barva = _over_barvu(vstup.barva)
    if vstup.aktivni is not None:
        k.aktivni = bool(vstup.aktivni)
    if vstup.poradi is not None:
        k.poradi = vstup.poradi
    db.commit()
    db.refresh(k)
    return _kategorie_aktivity_out(k)


@router.delete("/kategorie-aktivit/{kategorie_id}")
def smaz_kategorii_aktivity(
    kategorie_id: int,
    user: User = Depends(vyzaduj_nastaveni),
    db: Session = Depends(get_db),
):
    """Smaže štítek. Aktivity, které ho měly, zůstanou — jen bez štítku
    (cizí klíč je SET NULL). Mazání se proto nezakazuje: štítek není nositelem
    významu záznamu, na rozdíl od kategorie obchodního případu."""
    k = db.get(CrmKategorieAktivity, kategorie_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Kategorie neexistuje")
    pocet = (
        db.query(func.count(CrmAktivita.id))
        .filter(CrmAktivita.kategorie_id == kategorie_id)
        .scalar()
    )
    db.delete(k)
    db.commit()
    return {"ok": True, "aktivit_bez_kategorie": int(pocet or 0)}


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


def _klice_pro_vzorec(db: Session, entita: str, kromě_id: int | None = None) -> set[str]:
    """Co smí vzorec (CRM-34) použít: číselná vlastní pole + pár pevných sloupců.

    Sebe sama do vzorce nepustíme (`kromě_id`) — pole odkazující na vlastní
    výsledek by se počítalo donekonečna.
    """
    klice = set(pole_modul.zdroje_vzorce())
    for p in pole_modul.seznam(db, entita):
        if p.typ == "cislo" and p.id != kromě_id and not (p.vzorec or "").strip():
            klice.add(p.klic)
    return klice


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
        skupina=(vstup.skupina or "").strip(),
        zavislost_pole=(vstup.zavislost_pole or "").strip(),
        zavislost_hodnota=(vstup.zavislost_hodnota or "").strip(),
        vzorec=pole_modul.over_vzorec(vstup.vzorec, _klice_pro_vzorec(db, entita)),
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
    if vstup.skupina is not None:
        pole.skupina = vstup.skupina.strip()
    if vstup.zavislost_pole is not None:
        pole.zavislost_pole = vstup.zavislost_pole.strip()
    if vstup.zavislost_hodnota is not None:
        pole.zavislost_hodnota = vstup.zavislost_hodnota.strip()
    if vstup.vzorec is not None:
        pole.vzorec = pole_modul.over_vzorec(
            vstup.vzorec, _klice_pro_vzorec(db, pole.entita, kromě_id=pole.id)
        )
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


# ---- odběrná místa (CRM-46) --------------------------------------------------
# Jeden pár endpointů pro kartu klienta i kartu obchodního případu — stejně jako
# u složek na Disku. Odběrné místo patří VŽDY zákazníkovi; u případu je to jen
# druhý vchod do téhož seznamu, plus vazba „tohoto místa se případ týká".
# Právo je `zakaznici`, protože odběrné místo je vlastnost firmy; kdo vidí
# případ, má v CRM i právo na zákazníky (viz tabulka práv v Dodelavky_CRM.md).


def _diagram_out(db: Session, d) -> DiagramOut:
    dnu = None
    if d.obdobi_od is not None and d.obdobi_do is not None:
        dnu = max(1, round((d.obdobi_do - d.obdobi_od).total_seconds() / 86400))
    uz = db.get(User, d.nahral_user_id) if d.nahral_user_id else None
    return DiagramOut(
        id=d.id,
        odberne_misto_id=d.odberne_misto_id,
        puvodni_nazev=d.puvodni_nazev or "",
        popis=d.popis or "",
        velikost_bajtu=d.velikost_bajtu,
        stav=d.stav,
        chyba_text=d.chyba_text or "",
        obdobi_od=_iso(d.obdobi_od),
        obdobi_do=_iso(d.obdobi_do),
        pocet_intervalu=d.pocet_intervalu,
        interval_min=d.interval_min,
        spotreba_mwh=float(d.spotreba_mwh) if d.spotreba_mwh is not None else None,
        max_kw=float(d.max_kw) if d.max_kw is not None else None,
        dnu=dnu,
        nahral_jmeno=_jmeno(uz),
        nahrano_at=_iso(d.nahrano_at),
    )


def _misto_out(
    db: Session, m: OdberneMisto, vybrane_id: int | None = None, zakaznik_nazev: str = ""
) -> OdberneMistoOut:
    diagramy = (
        db.query(CrmDiagram)
        .filter(CrmDiagram.odberne_misto_id == m.id)
        .order_by(CrmDiagram.obdobi_do.desc().nullslast(), CrmDiagram.id.desc())
        .all()
    )
    return OdberneMistoOut(
        id=m.id,
        zakaznik_id=m.zakaznik_id,
        zakaznik_nazev=zakaznik_nazev,
        nazev=m.nazev,
        ean=m.ean or "",
        adresa_ulice=m.adresa_ulice or "",
        adresa_mesto=m.adresa_mesto or "",
        adresa_psc=m.adresa_psc or "",
        adresa_text=om_modul.adresa_textem(m),
        gps_lat=float(m.gps_lat) if m.gps_lat is not None else None,
        gps_lng=float(m.gps_lng) if m.gps_lng is not None else None,
        distributor=m.distributor or "",
        napetova_hladina=m.napetova_hladina or "",
        rezervovana_kapacita_kw=(
            float(m.rezervovana_kapacita_kw) if m.rezervovana_kapacita_kw is not None else None
        ),
        rezervovany_prikon_kw=(
            float(m.rezervovany_prikon_kw) if m.rezervovany_prikon_kw is not None else None
        ),
        poznamka=m.poznamka or "",
        aktivni=bool(m.aktivni),
        extra=pole_modul.s_vypocty(db, "om", m, m.extra),
        diagramu=len(diagramy),
        diagramy=[_diagram_out(db, d) for d in diagramy],
        vybrane_pro_pripad=(vybrane_id is not None and m.id == vybrane_id),
    )


def _napln_misto(db: Session, m: OdberneMisto, vstup: OdberneMistoVstup) -> OdberneMisto:
    """Přepíše pole místa ze vstupu (společné pro zakládání i úpravu)."""
    nazev = (vstup.nazev or "").strip()
    if not nazev:
        raise HTTPException(status_code=422, detail="Odběrné místo musí mít název.")

    ean = om_modul.normalizuj_ean(vstup.ean)
    om_modul.over_duplicitni_ean(db, m.zakaznik_id, ean, krome_id=m.id)
    distributor, hladina = om_modul.over_distribuci(vstup.distributor, vstup.napetova_hladina)

    m.nazev = nazev
    m.ean = ean
    m.adresa_ulice = (vstup.adresa_ulice or "").strip()
    m.adresa_mesto = (vstup.adresa_mesto or "").strip()
    m.adresa_psc = (vstup.adresa_psc or "").strip()
    m.gps_lat = vstup.gps_lat
    m.gps_lng = vstup.gps_lng
    m.distributor = distributor
    m.napetova_hladina = hladina
    m.rezervovana_kapacita_kw = vstup.rezervovana_kapacita_kw
    m.rezervovany_prikon_kw = vstup.rezervovany_prikon_kw
    m.poznamka = (vstup.poznamka or "").strip()
    m.aktivni = bool(vstup.aktivni)
    m.extra = pole_modul.zpracuj(db, "om", vstup.extra)
    return m


@router.get("/odberna-mista/{entita}/{zaznam_id}", response_model=OdbernaMistaOut)
def seznam_odbernych_mist(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Odběrná místa zákazníka — z karty klienta i z karty obchodního případu.

    U případu se vrací místa jeho zákazníka a `vybrane_id` říká, kterého se
    případ týká. Tím je „stejné pole na obou obrazovkách" jeden zdroj pravdy:
    co OZ založí u případu, vidí i na kartě klienta a použijí to i další
    případy téže firmy.
    """
    z, pripad = om_modul.zaznam_a_zakaznik(db, entita, zaznam_id, user)
    if z is None:
        raise HTTPException(status_code=404, detail="Zákazník neexistuje")
    vybrane_id = pripad.odberne_misto_id if pripad is not None else None
    mista = om_modul.seznam(db, z.id)
    return OdbernaMistaOut(
        zakaznik_id=z.id,
        zakaznik_nazev=z.nazev,
        mista=[_misto_out(db, m, vybrane_id, z.nazev) for m in mista],
        vybrane_id=vybrane_id,
        vlastni_pole=[VlastniPoleOut(**p) for p in pole_modul.pro_frontend(db, "om")],
        muze_editovat=smi_menit(pripad if pripad is not None else z, user),
    )


@router.post("/odberna-mista/{entita}/{zaznam_id}", response_model=OdberneMistoOut)
def zaloz_odberne_misto(
    entita: str,
    zaznam_id: int,
    vstup: OdberneMistoVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Založí odběrné místo u zákazníka.

    Když se zakládá z karty obchodního případu a případ ještě žádné místo
    nemá, rovnou se mu přiřadí — OZ zakládá místo právě proto, že ho pro ten
    případ potřebuje, a druhé kliknutí by byl jen obřad. Když už případ místo
    má, vazba se nepřepisuje (to je vědomé rozhodnutí, ne vedlejší efekt).
    """
    z, pripad = om_modul.zaznam_a_zakaznik(db, entita, zaznam_id, user)
    if z is None:
        raise HTTPException(status_code=404, detail="Zákazník neexistuje")
    if not smi_menit(pripad if pripad is not None else z, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto záznamu nemáš právo.")

    m = OdberneMisto(zakaznik_id=z.id, nazev="", vytvoril_user_id=user.id)
    _napln_misto(db, m, vstup)
    db.add(m)
    db.flush()
    if pripad is not None and pripad.odberne_misto_id is None:
        pripad.odberne_misto_id = m.id
    db.commit()
    db.refresh(m)
    return _misto_out(db, m, pripad.odberne_misto_id if pripad is not None else None, z.nazev)


@router.put("/odberna-mista/{misto_id}", response_model=OdberneMistoOut)
def uprav_odberne_misto(
    misto_id: int,
    vstup: OdberneMistoVstup,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    m = om_modul.vyzaduj_misto(db, misto_id, user)
    z = db.get(Zakaznik, m.zakaznik_id)
    if not smi_menit(z, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto zákazníka nemáš právo.")
    _napln_misto(db, m, vstup)
    db.commit()
    db.refresh(m)
    return _misto_out(db, m, None, z.nazev if z is not None else "")


@router.delete("/odberna-mista/{misto_id}")
def smaz_odberne_misto(
    misto_id: int,
    potvrzeno: bool = Query(default=False, description="Bez potvrzení se jen vypíše, co smazání odnese"),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Smaže odběrné místo. Bez `potvrzeno=true` jen řekne, co by se stalo.

    Náhled nasucho je tu proto, že s místem odejdou i jeho diagramy — a ty
    OZ stahoval z portálu distributora, což je hodinová práce a čekání na
    přístupy. Případy, které místo používaly, se jen odpojí (nemažou se).
    """
    m = om_modul.vyzaduj_misto(db, misto_id, user)
    z = db.get(Zakaznik, m.zakaznik_id)
    if not smi_menit(z, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto zákazníka nemáš právo.")

    diagramu = om_modul.pocet_diagramu(db, m.id)
    pripadu = (
        db.query(ObchodniPripad).filter(ObchodniPripad.odberne_misto_id == m.id).count()
    )
    if not potvrzeno:
        return {
            "smazano": False,
            "nazev": m.nazev,
            "diagramu": diagramu,
            "pripadu": pripadu,
            "co_se_stane": (
                f"Smaže se odběrné místo „{m.nazev}“ včetně {diagramu} nahraných diagramů. "
                f"Obchodní případy ({pripadu}) zůstanou, jen se jim vazba na místo zruší."
            ),
        }
    db.delete(m)
    db.commit()
    return {"smazano": True, "id": misto_id, "diagramu": diagramu, "pripadu": pripadu}


@router.put("/pripady/{pripad_id}/odberne-misto", response_model=OdbernaMistaOut)
def nastav_odberne_misto_pripadu(
    pripad_id: int,
    vstup: OdberneMistoPripaduVstup,
    user: User = Depends(vyzaduj_pripady),
    db: Session = Depends(get_db),
):
    """Přiřadí případu odběrné místo (nebo vazbu zruší hodnotou `null`).

    Místo musí patřit zákazníkovi případu — jinak by nabídka počítala z diagramu
    cizí firmy, což je chyba, kterou by na výsledku nikdo nepoznal.
    """
    p = vyzaduj_zaznam(db.get(ObchodniPripad, pripad_id), user, "Obchodní případ")
    if not smi_menit(p, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto případu nemáš právo.")

    if vstup.odberne_misto_id is None:
        p.odberne_misto_id = None
    else:
        m = db.get(OdberneMisto, vstup.odberne_misto_id)
        if m is None or m.zakaznik_id != p.zakaznik_id:
            raise HTTPException(
                status_code=422,
                detail="Odběrné místo patří jinému zákazníkovi, než je na tomto případu.",
            )
        p.odberne_misto_id = m.id
    db.commit()
    return seznam_odbernych_mist("op", p.id, user, db)


# ---- diagramy odběru u odběrného místa (CRM-46, etapa 2) ---------------------
# Diagram patří MÍSTU, ne nabídce: stáhne se z portálu distributora jednou
# a použije se pro všechny nabídky té provozovny. Parsuje se hned při nahrání,
# takže se v seznamu pozná nepoužitelný export dřív, než na něm někdo postaví
# výpočet (viz `crm/diagramy.py`).


# POZOR na tvar cesty: `/odberna-mista/{misto_id}/diagramy` by kolidovalo
# s `/odberna-mista/{entita}/{zaznam_id}` výš (obě mají dva segmenty, `entita`
# je text). FastAPI by upload namapoval na zakládání místa a vrátil nesmyslnou
# validační chybu — na náhledu se to projevilo jako 500 při nahrání souboru.
# Proto nahrávání jde přes `/diagramy/misto/{misto_id}`, kde je literál první.
@router.post("/diagramy/misto/{misto_id}", response_model=DiagramOut)
async def nahraj_diagram(
    misto_id: int,
    soubor: UploadFile = File(...),
    popis: str = Form(default=""),
    obchodni_pripad_id: int | None = Form(default=None),
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Nahraje 15minutový diagram k odběrnému místu a hned ho naparsuje.

    Když se soubor přečíst nedá, nahrání NESELŽE: diagram se uloží se stavem
    „chyba“ a důvodem, aby OZ viděl, co je špatně, a nemusel export stahovat
    z portálu znovu.
    """
    m = om_modul.vyzaduj_misto(db, misto_id, user)
    z = db.get(Zakaznik, m.zakaznik_id)
    if not smi_menit(z, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto zákazníka nemáš právo.")

    if obchodni_pripad_id is not None:
        p = db.get(ObchodniPripad, obchodni_pripad_id)
        if p is None or p.zakaznik_id != m.zakaznik_id:
            raise HTTPException(
                status_code=422, detail="Obchodní případ patří jinému zákazníkovi."
            )

    data = await soubor.read()
    d = diagramy_modul.nahraj(
        db,
        m,
        soubor.filename or "diagram",
        data,
        user.id,
        pripad_id=obchodni_pripad_id,
        popis=popis,
    )
    return _diagram_out(db, d)


@router.get("/diagramy/{diagram_id}/soubor")
def stahni_diagram(
    diagram_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Stažení původního souboru – ať OZ nemusí zpátky do portálu distributora."""
    from fastapi.responses import FileResponse

    from app.nabidkovac import soubory as soubory_modul

    d = diagramy_modul.vyzaduj_diagram(db, diagram_id)
    m = om_modul.vyzaduj_misto(db, d.odberne_misto_id, user)  # kontrola práv přes zákazníka
    cesta = soubory_modul.UPLOAD_DIR / d.soubor_cesta
    if not cesta.exists():
        raise HTTPException(status_code=404, detail="Soubor diagramu už na disku není.")
    return FileResponse(
        str(cesta),
        filename=d.puvodni_nazev or f"diagram-{m.nazev}",
        media_type="application/octet-stream",
    )


@router.delete("/diagramy/{diagram_id}")
def smaz_diagram(
    diagram_id: int,
    user: User = Depends(vyzaduj_zakazniky),
    db: Session = Depends(get_db),
):
    """Smaže diagram i jeho soubor.

    Profily nabídek, které z něj počítaly, ZŮSTÁVAJÍ: nabídka si drží čísla,
    se kterými odešla zákazníkovi, a nemá se změnit tím, že někdo uklidil
    podklad.
    """
    d = diagramy_modul.vyzaduj_diagram(db, diagram_id)
    m = om_modul.vyzaduj_misto(db, d.odberne_misto_id, user)
    z = db.get(Zakaznik, m.zakaznik_id)
    if not smi_menit(z, user):
        raise HTTPException(status_code=403, detail="Na úpravu tohoto zákazníka nemáš právo.")
    diagramy_modul.smaz(db, d)
    return {"smazano": diagram_id}


@router.post("/nabidky/{nabidka_id}/pouzij-diagram/{diagram_id}")
def pouzij_diagram_pro_nabidku(
    nabidka_id: int,
    diagram_id: int,
    user: User = Depends(vyzaduj_nabidkovac_crm),
    db: Session = Depends(get_db),
):
    """Zapíše řadu z diagramu do profilu spotřeby nabídky.

    Tohle je ta „kopie", na které stojí rozhodnutí Dana: nabídka si drží svá
    čísla. Novější diagram se do už spočítané nabídky nedostane sám — je na
    obchodníkovi ho použít znovu.

    Diagram musí patřit zákazníkovi, pod kterým nabídka visí. Bez té kontroly
    by šlo nabídce podstrčit odběr cizí firmy a na výsledku by to nikdo nepoznal.
    """
    from app.nabidkovac.models import Nabidka

    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    d = diagramy_modul.vyzaduj_diagram(db, diagram_id)
    m = om_modul.vyzaduj_misto(db, d.odberne_misto_id, user)

    if n.obchodni_pripad_id is None:
        raise HTTPException(
            status_code=422,
            detail=(
                "Nabídka není navázaná na obchodní případ, takže nejde ověřit, "
                "že diagram patří témuž zákazníkovi. Nahraj profil přímo k nabídce."
            ),
        )
    p = vyzaduj_zaznam(db.get(ObchodniPripad, n.obchodni_pripad_id), user, "Obchodní případ")
    if p.zakaznik_id != m.zakaznik_id:
        raise HTTPException(
            status_code=422,
            detail="Diagram patří jinému zákazníkovi než nabídka.",
        )

    vysledek = diagramy_modul.pouzij_pro_nabidku(db, d, nabidka_id)
    # Nahrané podklady posunou koncept dál – stejně jako nahrání dokumentu.
    if n.stav == "koncept":
        n.stav = "data_nahrana"
    # GPS provozovny doplníme jen když na nabídce žádná není. Výroba FVE se
    # počítá z polohy MÍSTA, ne z fakturační adresy firmy — ale vyplněnou
    # hodnotu nepřepisujeme, mohl ji tam někdo dát ručně a přesněji.
    if n.zakaznik_gps_lat is None and n.zakaznik_gps_lng is None:
        if m.gps_lat is not None and m.gps_lng is not None:
            n.zakaznik_gps_lat = m.gps_lat
            n.zakaznik_gps_lng = m.gps_lng
            vysledek["gps_doplneno"] = True
    db.commit()
    vysledek["odberne_misto"] = m.nazev
    vysledek["parametry_mista"] = om_modul.parametry_pro_vypocet(m)
    return vysledek


@router.get("/nabidky/{nabidka_id}/odberna-mista", response_model=OdbernaMistaOut)
def odberna_mista_nabidky(
    nabidka_id: int,
    user: User = Depends(vyzaduj_nabidkovac_crm),
    db: Session = Depends(get_db),
):
    """Odběrná místa (a jejich diagramy) použitelná pro tuhle nabídku.

    Panel výpočtu z toho nabídne „vzít diagram z odběrného místa". Nabídka bez
    obchodního případu vrací prázdný seznam, ne chybu: nabídkovač jde pořád
    otevřít samostatně jako výpočtový nástroj a tam se profil nahrává k nabídce.

    Právo je Nabídkovač (ne Zákazníci): kdo smí nabídku počítat, musí vidět
    podklady jejího případu. Viditelnost samotného případu se stejně ověřuje
    přes `vyzaduj_zaznam`, takže cizí zakázka se přes tuhle cestu neotevře.
    """
    from app.nabidkovac.models import Nabidka

    n = db.get(Nabidka, nabidka_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Nabídka neexistuje")
    if n.obchodni_pripad_id is None:
        return OdbernaMistaOut(zakaznik_id=0, zakaznik_nazev="", mista=[], muze_editovat=False)
    p = vyzaduj_zaznam(db.get(ObchodniPripad, n.obchodni_pripad_id), user, "Obchodní případ")
    return seznam_odbernych_mist("op", p.id, user, db)


# ---- notifikace: zvoneček (CRM-10) ------------------------------------------
def _notifikace_out(n) -> NotifikaceOut:
    return NotifikaceOut(
        id=n.id,
        udalost=n.udalost,
        predmet=n.predmet or "",
        text=n.text or "",
        cesta=n.cesta or "",
        precteno=n.precteno_at is not None,
        vytvoreno_at=_iso(n.vytvoreno_at),
    )


@router.get("/notifikace", response_model=NotifikaceSouhrnOut)
def seznam_notifikaci(
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Zvoneček: posledních pár zpráv včetně přečtených + počet nepřečtených.

    Právo se tu nekontroluje schválně — notifikace jsou vždycky jen moje
    a přijdou i na věci mimo CRM (např. přiřazení projektu).
    """
    zaznamy = notifikace_modul.posledni(db, user.id)
    neprectenych = sum(1 for n in zaznamy if n.precteno_at is None)
    return NotifikaceSouhrnOut(
        neprectenych=neprectenych,
        zaznamy=[_notifikace_out(n) for n in zaznamy],
    )


@router.post("/notifikace/precteno")
def oznac_notifikace_precteno(
    vstup: NotifikacePrectenoVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    pocet = notifikace_modul.oznac_precteno(db, user.id, vstup.ids)
    return {"ok": True, "oznaceno": pocet}


# ---- notifikace: volba, co chci dostávat (CRM-36) ---------------------------
@router.get("/notifikace/nastaveni", response_model=NastaveniNotifikaciOut)
def nastaveni_notifikaci(
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    from app.mailer import email_nastaven

    return NastaveniNotifikaciOut(
        udalosti=[UdalostOut(**u) for u in notifikace_modul.UDALOSTI],
        volby=notifikace_modul.volby(db, user.id),
        email_funguje=email_nastaven(),
    )


@router.put("/notifikace/nastaveni", response_model=NastaveniNotifikaciOut)
def uloz_nastaveni_notifikaci(
    vstup: NastaveniNotifikaciVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    from app.mailer import email_nastaven

    ulozene = notifikace_modul.uloz_volby(db, user.id, vstup.volby)
    return NastaveniNotifikaciOut(
        udalosti=[UdalostOut(**u) for u in notifikace_modul.UDALOSTI],
        volby=ulozene,
        email_funguje=email_nastaven(),
    )


# ---- šablony e-mailů a poznámek (CRM-32) ------------------------------------
# Cesta je `/crm/sablony-textu`, NE `/crm/sablony` — tu už zabraly ŠABLONY
# PROJEKTOVÝCH KROKŮ v routes_realizace.py. Obě jsou pod stejným routerem, takže
# stejná cesta by tiše přebila tu, která se registruje později (pořadí
# include_router v main.py), a rozbila by projektové šablony.
def _sablona_textu_out(s) -> SablonaTextuOut:
    return SablonaTextuOut(
        id=s.id,
        druh=s.druh,
        nazev=s.nazev,
        predmet=s.predmet or "",
        telo=s.telo or "",
        entita=s.entita or "",
        aktivni=bool(s.aktivni),
        poradi=s.poradi,
    )


@router.get("/sablony-textu", response_model=SablonyOut)
def seznam_sablon(
    druh: str | None = Query(default=None),
    entita: str | None = Query(default=None),
    vse: bool = Query(default=False),
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Šablony k použití. `vse=true` vrací i vypnuté – pro obrazovku správy."""
    if vse:
        q = db.query(CrmSablona)
        if druh:
            q = q.filter(CrmSablona.druh == druh)
        polozky = q.order_by(CrmSablona.druh, CrmSablona.poradi, CrmSablona.id).all()
    else:
        polozky = sablony_modul.seznam(db, druh, entita)
    return SablonyOut(
        sablony=[_sablona_textu_out(s) for s in polozky],
        symboly=[SymbolOut(klic=k, popis=p) for k, p in sablony_modul.SYMBOLY],
    )


@router.get("/sablony-textu/{sablona_id}/pouzit", response_model=SablonaPouzitiOut)
def pouzij_sablonu(
    sablona_id: int,
    entita: str = Query(default=""),
    zaznam_id: int | None = Query(default=None),
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Text šablony s doplněnými symboly. Co se nedoplní, zůstane jako `{{klic}}`."""
    s = db.get(CrmSablona, sablona_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    hodnoty = sablony_modul.hodnoty(db, entita, zaznam_id, user)
    return SablonaPouzitiOut(
        predmet=sablony_modul.doplnil(s.predmet, hodnoty),
        telo=sablony_modul.doplnil(s.telo, hodnoty),
    )


@router.post("/sablony-textu", response_model=SablonaTextuOut)
def pridej_sablonu(
    vstup: SablonaTextuVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    if vstup.druh not in sablony_modul.DRUHY:
        raise HTTPException(status_code=422, detail=f"Neznámý druh šablony: {vstup.druh}")
    if not vstup.nazev.strip():
        raise HTTPException(status_code=422, detail="Šablona musí mít název.")
    s = CrmSablona(
        druh=vstup.druh,
        nazev=vstup.nazev.strip(),
        predmet=vstup.predmet.strip(),
        telo=vstup.telo,
        entita=vstup.entita.strip(),
        aktivni=vstup.aktivni,
        poradi=vstup.poradi,
        vytvoril_user_id=user.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sablona_textu_out(s)


@router.put("/sablony-textu/{sablona_id}", response_model=SablonaTextuOut)
def uprav_sablonu(
    sablona_id: int,
    vstup: SablonaTextuVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    s = db.get(CrmSablona, sablona_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    if vstup.druh not in sablony_modul.DRUHY:
        raise HTTPException(status_code=422, detail=f"Neznámý druh šablony: {vstup.druh}")
    s.druh = vstup.druh
    s.nazev = vstup.nazev.strip()
    s.predmet = vstup.predmet.strip()
    s.telo = vstup.telo
    s.entita = vstup.entita.strip()
    s.aktivni = vstup.aktivni
    s.poradi = vstup.poradi
    db.commit()
    db.refresh(s)
    return _sablona_textu_out(s)


@router.delete("/sablony-textu/{sablona_id}")
def smaz_sablonu(
    sablona_id: int,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    s = db.get(CrmSablona, sablona_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Šablona neexistuje")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ---- odeslání e-mailu z appky (CRM-10) --------------------------------------
@router.post("/email", response_model=EmailOut)
def posli_email_z_appky(
    vstup: EmailVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Pošle e-mail zákazníkovi a **zapíše ho k záznamu jako aktivitu**.

    Zápis do logu komunikace je vlastní důvod, proč se maily posílají z appky
    a ne z Outlooku: jinak nikdo nedohledá, co už zákazníkovi odešlo.
    Aktivita se ukládá **až po úspěšném odeslání** — záznam „odesláno" u něčeho,
    co neodešlo, je horší než žádný záznam.

    Odesílatelem je **firemní schránka**, ne osobní; v podpisu je jméno autora,
    aby zákazník věděl, s kým mluví. Vlastní schránky by znamenaly ukládat
    hesla lidí, což nechceme.
    """
    from app.mailer import email_nastaven, posli_email

    komu = (vstup.komu or "").strip()
    if "@" not in komu:
        raise HTTPException(status_code=422, detail="Vyplň platnou e-mailovou adresu příjemce.")
    predmet = (vstup.predmet or "").strip()
    if not predmet:
        raise HTTPException(status_code=422, detail="E-mail musí mít předmět.")
    telo = (vstup.telo or "").strip()
    if not telo:
        raise HTTPException(status_code=422, detail="E-mail nemůže být prázdný.")
    if not email_nastaven():
        raise HTTPException(
            status_code=422,
            detail="Odesílání e-mailů není nastavené (chybí SMTP_HESLO v .env na serveru).",
        )

    podpis = f"\n\n--\n{user.jmeno or ''}\nGreensie s.r.o.".rstrip()
    try:
        posli_email(komu, predmet, f"{telo}{podpis}")
    except Exception as e:  # noqa: BLE001 - chybu chce uživatel vidět, ne v logu
        raise HTTPException(status_code=502, detail=f"E-mail se nepodařilo odeslat: {e}")

    aktivita_id = None
    if vstup.entita and vstup.zaznam_id:
        _over_pristup_k_zaznamu(db, vstup.entita, vstup.zaznam_id, user)
        a = CrmAktivita(
            entita=vstup.entita,
            zaznam_id=vstup.zaznam_id,
            druh="email",
            nazev=f"Odesláno: {predmet}",
            text=f"Komu: {komu}\n\n{telo}",
            stav="realizovano",
            vlastnik_user_id=user.id,
            vytvoril_user_id=user.id,
        )
        db.add(a)
        db.flush()
        aktivita_id = a.id
        # Potvrzení „opravdu to odešlo" – u nabídky je to jediná zpětná vazba,
        # že si zákazník má co otevřít.
        if vstup.entita == "nab":
            notifikace_modul.posli(
                db,
                user,
                "nabidka_odeslana",
                f"Nabídka odešla na {komu}",
                predmet,
                f"/nabidkovac/nabidka/{vstup.zaznam_id}",
            )
        db.commit()

    return EmailOut(ok=True, aktivita_id=aktivita_id)


# ---- oblíbené a naposledy otevřené (CRM-37) ---------------------------------
@router.get("/oblibene", response_model=OblibeneOut)
def seznam_oblibenych(
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Přišpendlené a naposledy otevřené záznamy pro nabídku v hledání."""
    return OblibeneOut(**oblibene_modul.seznam(db, user))


@router.post("/oblibene/{entita}/{zaznam_id}")
def prepni_oblibeny(
    entita: str,
    zaznam_id: int,
    vstup: OblibeneVstup,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Přišpendlí nebo odšpendlí záznam.

    Přístup se tu neověřuje přes `vyzaduj_zaznam`: špendlík je jen ukazatel do
    seznamu, sám nic neodemyká. Kdyby si někdo přišpendlil cizí záznam, po
    kliknutí ho stejně nepustí dovnitř detail.
    """
    stav = oblibene_modul.prepni_oblibene(db, user, entita, zaznam_id, vstup.oblibene)
    return {"ok": True, "oblibene": stav}


@router.post("/oblibene/{entita}/{zaznam_id}/otevreno")
def zaznamenej_otevreni(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Zápis do historie „naposledy otevřené".

    Volá se z detailu při načtení. Chyba se schválně polyká — je to vedlejší
    efekt prohlížení a nesmí kvůli němu spadnout otevření karty.
    """
    try:
        oblibene_modul.zaznamenej(db, user, entita, zaznam_id)
        db.commit()
    except Exception:  # noqa: BLE001 - historie je doplněk, ne součást detailu
        db.rollback()
        return {"ok": False}
    return {"ok": True}


# ---- audit log (CRM-12) ------------------------------------------------------
@router.get("/audit/{entita}/{zaznam_id}", response_model=list[AuditOut])
def historie_zmen(
    entita: str,
    zaznam_id: int,
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Kdo co kdy u záznamu změnil.

    Přístup se ověřuje přes `_over_pristup_k_zaznamu` — log ukazuje hodnoty
    záznamu, takže kdo na záznam nevidí, nesmí vidět ani jeho historii.
    """
    _over_pristup_k_zaznamu(db, entita, zaznam_id, user)
    return [
        AuditOut(
            id=a.id,
            druh=a.druh,
            pole=a.pole or "",
            pole_nazev=audit_modul.nazev_pole(a.pole) if a.pole else "",
            stara=a.stara or "",
            nova=a.nova or "",
            kdo=_jmeno(a.zmenil),
            kdy=_iso(a.kdy),
        )
        for a in audit_modul.zaznamy(db, entita, zaznam_id)
    ]


# ---- mapa zákazníků a projektů (CRM-20) -------------------------------------
@router.get("/mapa", response_model=list[MapaBodOut])
def body_na_mapu(
    user: User = Depends(vyzaduj_novinky),
    db: Session = Depends(get_db),
):
    """Zákazníci se souřadnicemi. Kdo nemá `crm_vse`, vidí jen svoje."""
    return [MapaBodOut(**b) for b in mapa_modul.body(db, user)]
