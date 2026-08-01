"""API e-mailového klienta – `/crm/emaily/*`.

Vlastní modul, ne přílepek do `crm/routes.py`: ten má 4 000 řádků a e-mail je
samostatná obrazovka s vlastním datovým modelem. Router má **vlastní prefix
`/crm/emaily`**, takže nemůže kolidovat s ničím existujícím (past, na kterou
už appka jednou naletěla – viz `tests/test_kolize_cest.py`).

---- Kdo vidí čí poštu -----------------------------------------------------
Schránka patří člověku, ne firmě. Do cizí pošty proto **nevidí nikdo** –
ani vedení s právem `crm_vse`, ani supersprávce. Každý endpoint si účet hledá
přes `_muj_ucet(db, user)`, nikdy podle ID z parametru. To je jediná pojistka,
která tohle drží: jakmile by se účet bral z URL, dala by se cizí schránka
otevřít hádáním čísla.

Zprávy se hledají vždycky s `ucet_id == muj_ucet.id`, takže ani ID zprávy
z cizí schránky nic neodemkne (vrací 404, ne 403 – cizí pošta se nemá
projevit ani svou existencí).

---- Blokující IMAP v HTTP požadavku ---------------------------------------
Otevření zprávy, přečteno a přesun sahají na IMAP přímo v požadavku. Je to
vědomé: musí to být okamžité a jde o jeden příkaz nad **už otevřeným**
spojením z půjčovny (`email_pool`). Dlouhé věci – plná synchronizace schránky
– dělá worker mimo web proces (`email_worker.py`), protože právě ty by
uvázaný web proces dotlačily k 502.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import crypto
from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.crm import adresar, email_pool, email_smtp, email_sync, pristup
from app.crm.email_imap import (
    VYCHOZI_IMAP_HOST,
    VYCHOZI_IMAP_PORT,
    VYCHOZI_SMTP_HOST,
    VYCHOZI_SMTP_PORT,
    ImapChyba,
    otestuj_pripojeni,
)
from app.crm.models import (
    CrmEmailPravidlo,
    CrmEmailPriloha,
    CrmEmailSlozka,
    CrmEmailUcet,
    CrmEmailZprava,
    ObchodniPripad,
    Zakaznik,
)
from app.crm.novinky import ma_novinky
from app.crm.schemas import (
    EmailAdresaOut,
    EmailHistorieOut,
    EmailHromadneOut,
    EmailHromadneVstup,
    EmailKZaznamuOut,
    EmailVazbaVstup,
    EmailAutomatikaVstup,
    EmailPravidloOut,
    EmailPravidloVstup,
    EmailOdeslanoOut,
    EmailPsaniOut,
    EmailNaseptavacOut,
    EmailPresunVstup,
    EmailPrilohaOut,
    EmailPriznakVstup,
    EmailSlozkaOut,
    EmailSyncOut,
    EmailTestOut,
    EmailUcetOut,
    EmailUcetVstup,
    EmailZpravaDetailOut,
    EmailZpravaOut,
    EmailZpravyOut,
)
from app.database import get_db

router = APIRouter(prefix="/crm/emaily", tags=["crm-emaily"])

# Kolik zpráv na stránku. Padesát je „obrazovka a půl" – dost, aby se scrollovalo
# plynule, málo, aby odpověď zůstala pod stovkami kilobajtů.
NA_STRANU = 50
MAX_NA_STRANU = 200


# ---- práva -------------------------------------------------------------------
def vyzaduj_emaily(user: User = Depends(get_current_user)) -> User:
    """Právo `emaily` + přepínač novinek (funkce se zkouší interně).

    404 místo 403 stejně jako v `novinky.py`: kdo funkci nemá vidět, pro toho
    neexistuje – jinak by se lidé ptali, proč e-mail nemají.
    """
    if not ma_novinky(user) or not muze_otevrit(user, "emaily"):
        raise HTTPException(status_code=404, detail="Nenalezeno")
    return user


def _muj_ucet(db: Session, user: User, povinny: bool = True) -> CrmEmailUcet | None:
    """Schránka přihlášeného člověka. **Nikdy se nebere ID z parametru.**"""
    ucet = (
        db.query(CrmEmailUcet)
        .filter(CrmEmailUcet.user_id == user.id)
        .order_by(CrmEmailUcet.id)
        .first()
    )
    if ucet is None and povinny:
        raise HTTPException(
            status_code=404,
            detail="Nemáš připojenou žádnou schránku. Nastav ji v Nastavení e-mailu.",
        )
    return ucet


def _moje_zprava(db: Session, user: User, zprava_id: int) -> CrmEmailZprava:
    """Zpráva z **mojí** schránky, jinak 404."""
    ucet = _muj_ucet(db, user)
    zprava = (
        db.query(CrmEmailZprava)
        .filter(CrmEmailZprava.id == zprava_id, CrmEmailZprava.ucet_id == ucet.id)
        .first()
    )
    if zprava is None:
        raise HTTPException(status_code=404, detail="Zpráva neexistuje")
    return zprava


def _moje_slozka(db: Session, user: User, slozka_id: int) -> CrmEmailSlozka:
    ucet = _muj_ucet(db, user)
    slozka = (
        db.query(CrmEmailSlozka)
        .filter(CrmEmailSlozka.id == slozka_id, CrmEmailSlozka.ucet_id == ucet.id)
        .first()
    )
    if slozka is None:
        raise HTTPException(status_code=404, detail="Složka neexistuje")
    return slozka


# ---- převody na výstup -------------------------------------------------------
def _cas(hodnota: datetime | date | None) -> str | None:
    return hodnota.isoformat() if hodnota is not None else None


def ucet_out(ucet: CrmEmailUcet | None) -> EmailUcetOut | None:
    """Účet pro frontend. Heslo se nevrací nikdy – jen příznak, že je uložené."""
    if ucet is None:
        return None
    return EmailUcetOut(
        id=ucet.id,
        adresa=ucet.adresa,
        nazev=ucet.nazev,
        jmeno_odesilatele=ucet.jmeno_odesilatele,
        imap_host=ucet.imap_host,
        imap_port=ucet.imap_port,
        smtp_host=ucet.smtp_host,
        smtp_port=ucet.smtp_port,
        heslo_nastaveno=bool(ucet.heslo_sifra),
        aktivni=ucet.aktivni,
        sync_zapnuto=ucet.sync_zapnuto,
        prvni_sync_pocet=ucet.prvni_sync_pocet,
        podpis=ucet.podpis,
        stav=ucet.stav,
        posledni_sync_at=_cas(ucet.posledni_sync_at),
        posledni_chyba=ucet.posledni_chyba,
        klic_dostupny=crypto.klic_dostupny(),
        ooo_zapnuto=ucet.ooo_zapnuto,
        ooo_od=_cas(ucet.ooo_od),
        ooo_do=_cas(ucet.ooo_do),
        ooo_predmet=ucet.ooo_predmet,
        ooo_text=ucet.ooo_text,
        preposilani_zapnuto=ucet.preposilani_zapnuto,
        preposilani_komu=ucet.preposilani_komu,
        preposilani_nechat_kopii=ucet.preposilani_nechat_kopii,
    )


def _adresy_out(surove) -> list[EmailAdresaOut]:
    vysledek: list[EmailAdresaOut] = []
    for a in surove or []:
        if isinstance(a, dict):
            vysledek.append(
                EmailAdresaOut(jmeno=a.get("jmeno") or "", adresa=a.get("adresa") or "")
            )
    return vysledek


def zprava_out(zprava: CrmEmailZprava, nazvy: dict | None = None) -> EmailZpravaOut:
    nazvy = nazvy or {}
    return EmailZpravaOut(
        id=zprava.id,
        slozka_id=zprava.slozka_id,
        uid=zprava.uid,
        od_jmeno=zprava.od_jmeno,
        od_adresa=zprava.od_adresa,
        komu=_adresy_out(zprava.komu),
        kopie=_adresy_out(zprava.kopie),
        predmet=zprava.predmet,
        datum_at=_cas(zprava.datum_at) or "",
        smer=zprava.smer,
        precteno=zprava.precteno,
        oznaceno=zprava.oznaceno,
        zodpovezeno=zprava.zodpovezeno,
        ma_prilohy=zprava.ma_prilohy,
        velikost=zprava.velikost,
        vypis=zprava.vypis,
        zakaznik_id=zprava.zakaznik_id,
        zakaznik_nazev=nazvy.get(("z", zprava.zakaznik_id), ""),
        pripad_id=zprava.pripad_id,
        pripad_cislo=nazvy.get(("p", zprava.pripad_id), ""),
    )


def _nazvy_vazeb(db: Session, zpravy: list[CrmEmailZprava]) -> dict:
    """Názvy firem a čísla případů pro dávku zpráv – jedním dotazem, ne v cyklu."""
    z_ids = {z.zakaznik_id for z in zpravy if z.zakaznik_id}
    p_ids = {z.pripad_id for z in zpravy if z.pripad_id}
    nazvy: dict = {}
    if z_ids:
        for zid, nazev in db.query(Zakaznik.id, Zakaznik.nazev).filter(Zakaznik.id.in_(z_ids)):
            nazvy[("z", zid)] = nazev
    if p_ids:
        for pid, cislo in db.query(ObchodniPripad.id, ObchodniPripad.cislo).filter(
            ObchodniPripad.id.in_(p_ids)
        ):
            nazvy[("p", pid)] = cislo
    return nazvy


# ---- nastavení schránky ------------------------------------------------------
@router.get("/ucet", response_model=EmailUcetOut | None)
def moje_schranka(user: User = Depends(vyzaduj_emaily), db: Session = Depends(get_db)):
    """Moje připojená schránka, nebo `null`, když ještě žádná není."""
    return ucet_out(_muj_ucet(db, user, povinny=False))


@router.put("/ucet", response_model=EmailUcetOut)
def uloz_schranku(
    vstup: EmailUcetVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Založí nebo upraví moji schránku.

    Heslo je nepovinné: kdo mění jen podpis, nemusí ho opisovat znovu
    (`heslo=None` = nechat uložené). Prázdný řetězec naopak heslo **smaže** –
    to je vědomé „odpojit, ale nastavení nechat".
    """
    adresa = (vstup.adresa or "").strip().lower()
    if "@" not in adresa:
        raise HTTPException(status_code=422, detail="Vyplň platnou e-mailovou adresu schránky.")

    ucet = _muj_ucet(db, user, povinny=False)
    novy = ucet is None
    if novy:
        ucet = CrmEmailUcet(user_id=user.id, adresa=adresa)
        db.add(ucet)

    ucet.adresa = adresa
    ucet.nazev = (vstup.nazev or "").strip()
    ucet.jmeno_odesilatele = (vstup.jmeno_odesilatele or "").strip()
    ucet.imap_host = (vstup.imap_host or VYCHOZI_IMAP_HOST).strip()
    ucet.imap_port = int(vstup.imap_port or VYCHOZI_IMAP_PORT)
    ucet.smtp_host = (vstup.smtp_host or VYCHOZI_SMTP_HOST).strip()
    ucet.smtp_port = int(vstup.smtp_port or VYCHOZI_SMTP_PORT)
    ucet.aktivni = bool(vstup.aktivni)
    ucet.sync_zapnuto = bool(vstup.sync_zapnuto)
    # Strop 2000: víc zpráv při prvním připojení znamená minuty čekání a nikdo
    # tak hluboko v appce nehledá (na starou poštu je web Seznamu).
    ucet.prvni_sync_pocet = max(20, min(2000, int(vstup.prvni_sync_pocet or 300)))
    ucet.podpis = vstup.podpis or ""

    if vstup.heslo is not None:
        heslo = vstup.heslo.strip()
        if heslo and not crypto.klic_dostupny():
            raise HTTPException(
                status_code=422,
                detail=(
                    "Na serveru chybí šifrovací klíč (APP_ENC_KEY nebo KONEKTOR_ENC_KEY "
                    "v .env) – bez něj se heslo ke schránce nedá bezpečně uložit."
                ),
            )
        ucet.heslo_sifra = crypto.sifruj(heslo) if heslo else ""
        # Staré spojení je přihlášené starým heslem a dál by fungovalo – změna
        # by se „neprojevila" až do restartu appky.
        if not novy:
            email_pool.zahod(ucet.id)
        ucet.stav = "nenastaveno" if not heslo else ucet.stav
        ucet.posledni_chyba = ""

    db.commit()
    db.refresh(ucet)
    return ucet_out(ucet)


@router.post("/ucet/test", response_model=EmailTestOut)
def otestuj_schranku(
    vstup: EmailUcetVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Zkusí se přihlásit a vypsat složky, aniž by cokoli uložila.

    Testuje se **zadanými** údaji, ne uloženými: smysl tlačítka je zjistit, jestli
    to, co má člověk právě napsané ve formuláři, funguje. Když heslo ve formuláři
    není, vezme se uložené (úprava hostu u fungující schránky).
    """
    heslo = (vstup.heslo or "").strip()
    if not heslo:
        ucet = _muj_ucet(db, user, povinny=False)
        heslo = email_sync.heslo_uctu(ucet) if ucet is not None else ""
    if not heslo:
        return EmailTestOut(ok=False, zprava="Zadej heslo ke schránce, jinak se nedá připojit.")

    adresa = (vstup.adresa or "").strip().lower()
    if "@" not in adresa:
        return EmailTestOut(ok=False, zprava="Vyplň platnou e-mailovou adresu schránky.")

    try:
        vysledek = otestuj_pripojeni(
            (vstup.imap_host or VYCHOZI_IMAP_HOST).strip(),
            int(vstup.imap_port or VYCHOZI_IMAP_PORT),
            adresa,
            heslo,
        )
    except ImapChyba as e:
        return EmailTestOut(ok=False, zprava=str(e))
    return EmailTestOut(
        ok=True,
        zprava=(
            f"Připojeno. Schránka má {vysledek['pocet_slozek']} složek "
            f"a {vysledek['zprav_v_doruceni']} zpráv v Doručené poště."
        ),
        pocet_slozek=vysledek["pocet_slozek"],
        zprav_v_doruceni=vysledek["zprav_v_doruceni"],
        slozky=vysledek["slozky"],
    )


@router.delete("/ucet")
def odpoj_schranku(user: User = Depends(vyzaduj_emaily), db: Session = Depends(get_db)):
    """Odpojí schránku a zahodí nacachovanou poštu.

    Na serveru se **nemaže nic** – appka je jen okno do schránky. Odpojením se
    ruší jen to, co si appka stáhla k sobě.
    """
    ucet = _muj_ucet(db, user)
    email_pool.zahod(ucet.id)
    db.delete(ucet)  # kaskádou padnou složky, zprávy, přílohy i pravidla
    db.commit()
    return {"ok": True}


# ---- složky ------------------------------------------------------------------
@router.get("/slozky", response_model=list[EmailSlozkaOut])
def slozky(user: User = Depends(vyzaduj_emaily), db: Session = Depends(get_db)):
    ucet = _muj_ucet(db, user)
    seznam = (
        db.query(CrmEmailSlozka)
        .filter_by(ucet_id=ucet.id)
        .order_by(CrmEmailSlozka.poradi, CrmEmailSlozka.nazev)
        .all()
    )
    return [
        EmailSlozkaOut(
            id=s.id,
            nazev=s.nazev,
            druh=s.druh,
            poradi=s.poradi,
            celkem=s.celkem,
            nepreectenych=s.nepreectenych,
            sync_zapnuto=s.sync_zapnuto,
            posledni_sync_at=_cas(s.posledni_sync_at),
        )
        for s in seznam
    ]


@router.post("/slozky/{slozka_id}/sync-prepnout", response_model=EmailSlozkaOut)
def prepnout_sync_slozky(
    slozka_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Zapne/vypne stahování jedné složky (Spam a Koš jsou vypnuté zvlášť)."""
    slozka = _moje_slozka(db, user, slozka_id)
    slozka.sync_zapnuto = not slozka.sync_zapnuto
    db.commit()
    return EmailSlozkaOut(
        id=slozka.id,
        nazev=slozka.nazev,
        druh=slozka.druh,
        poradi=slozka.poradi,
        celkem=slozka.celkem,
        nepreectenych=slozka.nepreectenych,
        sync_zapnuto=slozka.sync_zapnuto,
        posledni_sync_at=_cas(slozka.posledni_sync_at),
    )


# ---- synchronizace -----------------------------------------------------------
@router.post("/sync", response_model=EmailSyncOut)
def synchronizuj(
    jen_inbox: bool = Query(False, description="Jen Doručená pošta (rychlé obnovení)"),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Ruční „Zkontrolovat poštu".

    Běžné stahování dělá worker na pozadí; tohle je pro člověka, který nechce
    čekat na další cyklus. Držet to jako jediný způsob synchronizace by nešlo –
    plný průběh trvá desítky sekund a uvázal by web proces.
    """
    ucet = _muj_ucet(db, user)
    try:
        vysledek = email_sync.synchronizuj_ucet(db, ucet, jen_inbox=jen_inbox)
    except ImapChyba as e:
        raise HTTPException(status_code=502, detail=str(e))
    return EmailSyncOut(
        ok=True,
        nove=vysledek["nove"],
        zmenene=vysledek["zmenene"],
        smazane=vysledek["smazane"],
        trvani_s=vysledek.get("trvani_s", 0),
        zprava=(
            f"Nových zpráv: {vysledek['nove']}." if vysledek["nove"] else "Žádná nová pošta."
        ),
    )


# ---- seznam zpráv ------------------------------------------------------------
@router.get("/zpravy", response_model=EmailZpravyOut)
def zpravy(
    slozka_id: int | None = Query(None, description="Prázdné = Doručená pošta"),
    hledat: str = Query("", description="Hledá v předmětu, odesílateli a náhledu"),
    jen_neprectene: bool = False,
    jen_oznacene: bool = False,
    zakaznik_id: int | None = None,
    strana: int = Query(1, ge=1),
    na_stranu: int = Query(NA_STRANU, ge=1, le=MAX_NA_STRANU),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Seznam zpráv – z DB, ne z IMAPu (proto je to okamžité).

    Hledá se jen v tom, co je nacachované (předmět, odesílatel, náhled). Fulltext
    v tělech by znamenal stáhnout celou schránku; na hlubší hledání je web
    Seznamu a to je čestnější, než dělat, že hledáme všude.
    """
    ucet = _muj_ucet(db, user)

    q = db.query(CrmEmailZprava).filter(CrmEmailZprava.ucet_id == ucet.id)
    if slozka_id is not None:
        _moje_slozka(db, user, slozka_id)  # ověření, že složka je moje
        q = q.filter(CrmEmailZprava.slozka_id == slozka_id)
    elif zakaznik_id is None:
        # Výchozí pohled je Doručená pošta. Bez tohohle by se míchala i odeslaná
        # pošta a spam do jednoho seznamu.
        inbox = email_sync.slozka_druhu(db, ucet.id, "inbox")
        if inbox is not None:
            q = q.filter(CrmEmailZprava.slozka_id == inbox.id)

    if zakaznik_id is not None:
        q = q.filter(CrmEmailZprava.zakaznik_id == zakaznik_id)
    if jen_neprectene:
        q = q.filter(CrmEmailZprava.precteno.is_(False))
    if jen_oznacene:
        q = q.filter(CrmEmailZprava.oznaceno.is_(True))

    dotaz = (hledat or "").strip()
    if dotaz:
        vzor = f"%{dotaz}%"
        q = q.filter(
            or_(
                CrmEmailZprava.predmet.ilike(vzor),
                CrmEmailZprava.od_adresa.ilike(vzor),
                CrmEmailZprava.od_jmeno.ilike(vzor),
                CrmEmailZprava.vypis.ilike(vzor),
            )
        )

    celkem = q.with_entities(func.count(CrmEmailZprava.id)).scalar() or 0
    seznam = (
        q.order_by(CrmEmailZprava.datum_at.desc(), CrmEmailZprava.id.desc())
        .offset((strana - 1) * na_stranu)
        .limit(na_stranu)
        .all()
    )
    nazvy = _nazvy_vazeb(db, seznam)
    return EmailZpravyOut(
        zpravy=[zprava_out(z, nazvy) for z in seznam],
        celkem=celkem,
        strana=strana,
        na_stranu=na_stranu,
    )


@router.get("/zpravy/{zprava_id}", response_model=EmailZpravaDetailOut)
def zprava(
    zprava_id: int,
    oznacit_precteno: bool = Query(True, description="Otevřením označit jako přečtené"),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Otevřená zpráva – tělo se dotáhne z IMAPu při prvním otevření.

    `oznacit_precteno` je zapnuté, protože to je chování, které lidé od poštovního
    klienta čekají. Nastavuje se **i na serveru**, aby se přečtená zpráva
    neukazovala jako nová v mobilu.
    """
    z = _moje_zprava(db, user, zprava_id)
    try:
        z = email_sync.stahni_telo(db, z)
        if oznacit_precteno and not z.precteno:
            email_sync.nastav_precteno(db, z, True)
    except ImapChyba as e:
        # Hlavičky v DB jsou, jen tělo chybí – ukázat aspoň to je lepší než chyba
        # přes celou obrazovku. Chybu si člověk přečte v místě těla.
        db.rollback()
        z = _moje_zprava(db, user, zprava_id)
        detail = _detail_out(db, z)
        detail.telo_text = f"[Tělo zprávy se nepodařilo stáhnout: {e}]"
        return detail
    return _detail_out(db, z)


def _detail_out(db: Session, z: CrmEmailZprava) -> EmailZpravaDetailOut:
    nazvy = _nazvy_vazeb(db, [z])
    zaklad = zprava_out(z, nazvy)
    prilohy = (
        db.query(CrmEmailPriloha)
        .filter_by(zprava_id=z.id)
        .order_by(CrmEmailPriloha.id)
        .all()
    )
    return EmailZpravaDetailOut(
        **zaklad.model_dump(),
        telo_text=z.telo_text,
        telo_html=z.telo_html,
        odpovedet_na=z.odpovedet_na,
        prilohy=[
            EmailPrilohaOut(
                id=p.id, nazev=p.nazev, mime=p.mime, velikost=p.velikost, vlozeny=p.vlozeny
            )
            for p in prilohy
        ],
    )


# ---- změny stavu zprávy ------------------------------------------------------
@router.post("/zpravy/{zprava_id}/priznaky", response_model=EmailZpravaOut)
def zmen_priznaky(
    zprava_id: int,
    vstup: EmailPriznakVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Přečteno / vlaječka – zapisuje se **i na Seznam**, ne jen do appky."""
    z = _moje_zprava(db, user, zprava_id)
    try:
        if vstup.precteno is not None and vstup.precteno != z.precteno:
            email_sync.nastav_precteno(db, z, vstup.precteno)
        if vstup.oznaceno is not None and vstup.oznaceno != z.oznaceno:
            email_sync.nastav_oznaceno(db, z, vstup.oznaceno)
    except ImapChyba as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))
    return zprava_out(z, _nazvy_vazeb(db, [z]))


@router.post("/zpravy/{zprava_id}/presun")
def presun(
    zprava_id: int,
    vstup: EmailPresunVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Přesune zprávu do jiné složky na serveru (sortování do složek ručně)."""
    z = _moje_zprava(db, user, zprava_id)
    cil = _moje_slozka(db, user, vstup.slozka_id)
    try:
        email_sync.presun_zpravu(db, z, cil)
    except ImapChyba as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True, "presunuto_do": cil.nazev}


@router.delete("/zpravy/{zprava_id}")
def do_kose(
    zprava_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Přesune zprávu do Koše. **Natrvalo nemaže nic** – to se dělá na Seznamu.

    Nevratné mazání appka schválně neumí: smazat cizí poštu omylem kliknutím
    v CRM je horší než nutnost dojít do Koše na webu Seznamu.
    """
    z = _moje_zprava(db, user, zprava_id)
    kos = email_sync.slozka_druhu(db, z.ucet_id, "kos")
    if kos is None:
        raise HTTPException(
            status_code=422,
            detail="Schránka nemá složku Koš, takže není kam zprávu přesunout.",
        )
    if kos.id == z.slozka_id:
        raise HTTPException(
            status_code=422,
            detail="Zpráva už v Koši je. Nevratné smazání udělej na webu Seznamu.",
        )
    try:
        email_sync.presun_zpravu(db, z, kos)
    except ImapChyba as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=str(e))
    return {"ok": True}


# ---- přílohy -----------------------------------------------------------------
@router.get("/prilohy/{priloha_id}")
def stahni_prilohu(
    priloha_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Stáhne přílohu z IMAPu a pošle ji rovnou dál (nikde se neukládá).

    Obsah příloh se do DB neukládá schválně – schránka s pěti roky pošty má
    příloh na gigabajty a databáze appky není archiv pošty.
    """
    ucet = _muj_ucet(db, user)
    priloha = (
        db.query(CrmEmailPriloha)
        .join(CrmEmailZprava, CrmEmailPriloha.zprava_id == CrmEmailZprava.id)
        .filter(CrmEmailPriloha.id == priloha_id, CrmEmailZprava.ucet_id == ucet.id)
        .first()
    )
    if priloha is None:
        raise HTTPException(status_code=404, detail="Příloha neexistuje")
    z = db.get(CrmEmailZprava, priloha.zprava_id)
    slozka = db.get(CrmEmailSlozka, z.slozka_id)

    try:
        with email_sync.pujcene(ucet) as s:
            s.vyber(slozka.imap_nazev)
            surova = s.priloha(z.uid, priloha.cislo_casti)
    except ImapChyba as e:
        raise HTTPException(status_code=502, detail=str(e))

    obsah = _dekoduj_prilohu(surova, priloha.mime)
    from urllib.parse import quote

    return Response(
        content=obsah,
        media_type=priloha.mime or "application/octet-stream",
        headers={
            # RFC 5987: názvy s diakritikou musí jít přes filename*, jinak je
            # prohlížeč zkomolí nebo soubor pojmenuje podle URL.
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(priloha.nazev or 'priloha')}"
            )
        },
    )


def _dekoduj_prilohu(surova: bytes, mime: str) -> bytes:
    """Rozkóduje část zprávy (base64 / quoted-printable) na skutečný obsah.

    IMAP posílá část tak, jak leží ve zprávě – tedy typicky v base64. Hlavička
    s `Content-Transfer-Encoding` k nám ale nedorazí, takže se část zabalí do
    minimální zprávy a nechá rozebrat `email`. Když to nevyjde, pošle se obsah,
    jak přišel: poškozený soubor je lepší než chyba 500.
    """
    import email as email_modul

    text = surova.decode("ascii", errors="ignore").strip()
    if not text:
        return surova
    # Base64 poznáme podle abecedy; quoted-printable podle `=XX`.
    import re as re_modul

    if re_modul.fullmatch(r"[A-Za-z0-9+/=\s]+", text):
        kodovani = "base64"
    elif "=" in text and re_modul.search(r"=[0-9A-F]{2}", text):
        kodovani = "quoted-printable"
    else:
        return surova
    try:
        zabalene = email_modul.message_from_string(
            f"Content-Type: {mime or 'application/octet-stream'}\n"
            f"Content-Transfer-Encoding: {kodovani}\n\n{text}"
        )
        obsah = zabalene.get_payload(decode=True)
        return obsah if obsah else surova
    except Exception:  # noqa: BLE001
        return surova


# ---- adresář -----------------------------------------------------------------
@router.get("/adresar", response_model=list[EmailNaseptavacOut])
def naseptavac(
    dotaz: str = Query("", alias="q", description="Část jména, firmy nebo adresy"),
    limit: int = Query(adresar.LIMIT_NASEPTAVACE, ge=1, le=50),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Našeptávač adres z CRM pro políčko „Komu".

    Adresář se nikde neduplikuje – je to pohled na zákazníky, jejich kontaktní
    osoby a uživatele appky. Kopie by znamenala, že se adresa opraví na kartě
    firmy a v našeptávači zůstane stará.
    """
    return [
        EmailNaseptavacOut(**polozka)
        for polozka in adresar.naseptavac(db, user, dotaz, limit=limit)
    ]


# ---- psaní a odesílání (dávka E2) --------------------------------------------
@router.get("/zpravy/{zprava_id}/odpoved", response_model=EmailPsaniOut)
def priprav_odpoved(
    zprava_id: int,
    vsem: bool = Query(False, description="Odpovědět všem (příjemci do kopie)"),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Předvyplní okno odpovědi včetně citace původní zprávy.

    Tělo musí být stažené, jinak by citace byla prázdná – proto se případně
    dotáhne (u zprávy, kterou člověk otevřel, už stažené je, takže to nic nestojí).
    """
    z = _moje_zprava(db, user, zprava_id)
    ucet = _muj_ucet(db, user)
    try:
        z = email_sync.stahni_telo(db, z)
    except ImapChyba:
        # Bez těla se dá odpovědět taky – jen bez citace. Lepší než chyba.
        db.rollback()
        z = _moje_zprava(db, user, zprava_id)
    return EmailPsaniOut(**email_smtp.priprav_odpoved(z, vsem, ucet.adresa))


@router.get("/zpravy/{zprava_id}/preposlani", response_model=EmailPsaniOut)
def priprav_preposlani(
    zprava_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Předvyplní okno přeposlání. Přílohy se nepřenášejí (viz email_smtp)."""
    z = _moje_zprava(db, user, zprava_id)
    try:
        z = email_sync.stahni_telo(db, z)
    except ImapChyba:
        db.rollback()
        z = _moje_zprava(db, user, zprava_id)
    return EmailPsaniOut(**email_smtp.priprav_preposlani(z))


@router.post("/odeslat", response_model=EmailOdeslanoOut)
async def odeslat(
    komu: str = Form(..., description="Adresy oddělené čárkou"),
    predmet: str = Form(...),
    # Prostý text. Nepovinný, když přijde `telo_html` z formátovacího editoru –
    # textová varianta se pak odvodí z HTML na serveru.
    telo: str = Form(""),
    telo_html: str = Form("", description="Tělo z formátovacího editoru"),
    kopie: str = Form(""),
    skryta_kopie: str = Form(""),
    odpoved_na_id: int | None = Form(None),
    zakaznik_id: int | None = Form(None),
    pripad_id: int | None = Form(None),
    prilohy: list[UploadFile] = File(default=[]),
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Odešle zprávu z **mojí** schránky.

    Jde to jako `multipart/form-data`, ne JSON, kvůli přílohám – base64 v JSONu
    by nafoukl požadavek o třetinu a musel by se skládat v prohlížeči.

    Přílohy se načtou do paměti: jsou omezené stropem `MAX_ZPRAVA_B` (18 MB),
    takže to nemůže sežrat server, a streamovat je do SMTP by znamenalo vlastní
    skládání MIME.
    """
    ucet = _muj_ucet(db, user)

    nactene: list[dict] = []
    for f in prilohy or []:
        if not f or not f.filename:
            continue
        obsah = await f.read()
        if not obsah:
            continue
        nactene.append(
            {"nazev": f.filename, "mime": f.content_type or "application/octet-stream",
             "obsah": obsah}
        )

    try:
        vysledek = email_smtp.odesli(
            db, ucet, user,
            komu=komu, predmet=predmet, telo=telo, telo_html=telo_html,
            kopie=kopie, skryta_kopie=skryta_kopie,
            odpoved_na_id=odpoved_na_id,
            prilohy=nactene,
            zakaznik_id=zakaznik_id,
            pripad_id=pripad_id,
        )
    except email_smtp.SmtpChyba as e:
        db.rollback()
        # 422 u chyb, které opraví uživatel (adresa, předmět, heslo);
        # 502 u chyb serveru. Rozlišuje se podle textu, protože jinak by se
        # musely zavádět dva typy výjimek pro totéž.
        raise HTTPException(status_code=502, detail=str(e))

    # Odeslaná zpráva se v seznamu objeví, až se složka Odeslané stáhne. Kdo
    # zprávu právě poslal, čeká ji tam hned – proto ji dotáhneme rovnou.
    if vysledek["kopie_ulozena"]:
        odeslane = email_sync.slozka_druhu(db, ucet.id, "odeslane")
        if odeslane is not None and odeslane.sync_zapnuto:
            try:
                with email_sync.pujcene(ucet) as s:
                    email_sync.synchronizuj_slozku(db, s, odeslane)
            except ImapChyba:
                # Objeví se při dalším cyklu workeru – není to chyba odeslání.
                db.rollback()

    return EmailOdeslanoOut(**vysledek)


# ---- pravidla, OOO a přeposílání (dávka E4) ----------------------------------
POPIS_POLE = {
    "od": "odesílatel", "komu": "příjemce", "predmet": "předmět",
    "telo": "text", "ma_prilohy": "příloha",
}
POPIS_OPERATORU = {
    "obsahuje": "obsahuje", "neobsahuje": "neobsahuje", "je": "je přesně",
    "zacina": "začíná na", "konci": "končí na", "ano": "je", "ne": "není",
}
POPIS_AKCI = {
    "presun": "přesunout do složky", "oznacit_precteno": "označit jako přečtené",
    "oznacit": "označit vlaječkou", "preposlat": "přeposlat", "prirad": "přiřadit k firmě",
}


def _popis_pravidla(db: Session, p: CrmEmailPravidlo) -> str:
    """Pravidlo česky na jeden řádek – v seznamu je to čitelnější než JSON."""
    spojka = " a zároveň " if (p.spojka or "a") == "a" else " nebo "
    casti = []
    for podminka in p.podminky or []:
        if not isinstance(podminka, dict):
            continue
        pole = POPIS_POLE.get(podminka.get("pole"), podminka.get("pole") or "?")
        op = POPIS_OPERATORU.get(podminka.get("operator"), podminka.get("operator") or "")
        hodnota = podminka.get("hodnota") or ""
        casti.append(f"{pole} {op} „{hodnota}“" if hodnota else f"{pole} {op}")
    kdyz = spojka.join(casti) if casti else "(žádná podmínka – pravidlo neběží)"

    akce_popis = []
    for akce in p.akce or []:
        if not isinstance(akce, dict):
            continue
        typ = POPIS_AKCI.get(akce.get("typ"), akce.get("typ") or "?")
        if akce.get("typ") == "presun" and akce.get("slozka_id"):
            slozka = db.get(CrmEmailSlozka, int(akce["slozka_id"]))
            typ = f"přesunout do „{slozka.nazev}“" if slozka else "přesunout do složky"
        elif akce.get("typ") == "preposlat" and akce.get("komu"):
            typ = f"přeposlat na {akce['komu']}"
        akce_popis.append(typ)
    pak = ", ".join(akce_popis) if akce_popis else "(žádná akce)"
    return f"Když {kdyz} → {pak}."


def _pravidlo_out(db: Session, p: CrmEmailPravidlo) -> EmailPravidloOut:
    return EmailPravidloOut(
        id=p.id,
        nazev=p.nazev,
        aktivni=p.aktivni,
        poradi=p.poradi,
        spojka=p.spojka,
        podminky=list(p.podminky or []),
        akce=list(p.akce or []),
        zastavit_dalsi=p.zastavit_dalsi,
        pocet_pouziti=p.pocet_pouziti,
        posledni_pouziti_at=_cas(p.posledni_pouziti_at),
        popis=_popis_pravidla(db, p),
    )


def _moje_pravidlo(db: Session, user: User, pravidlo_id: int) -> CrmEmailPravidlo:
    ucet = _muj_ucet(db, user)
    p = (
        db.query(CrmEmailPravidlo)
        .filter(CrmEmailPravidlo.id == pravidlo_id, CrmEmailPravidlo.ucet_id == ucet.id)
        .first()
    )
    if p is None:
        raise HTTPException(status_code=404, detail="Pravidlo neexistuje")
    return p


@router.get("/pravidla", response_model=list[EmailPravidloOut])
def pravidla(user: User = Depends(vyzaduj_emaily), db: Session = Depends(get_db)):
    ucet = _muj_ucet(db, user)
    seznam = (
        db.query(CrmEmailPravidlo)
        .filter_by(ucet_id=ucet.id)
        .order_by(CrmEmailPravidlo.poradi, CrmEmailPravidlo.id)
        .all()
    )
    return [_pravidlo_out(db, p) for p in seznam]


@router.post("/pravidla", response_model=EmailPravidloOut)
def pridej_pravidlo(
    vstup: EmailPravidloVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    ucet = _muj_ucet(db, user)
    _over_pravidlo(vstup)
    p = CrmEmailPravidlo(ucet_id=ucet.id, nazev=(vstup.nazev or "").strip() or "Pravidlo")
    _napln_pravidlo(p, vstup)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _pravidlo_out(db, p)


@router.put("/pravidla/{pravidlo_id}", response_model=EmailPravidloOut)
def uprav_pravidlo(
    pravidlo_id: int,
    vstup: EmailPravidloVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    p = _moje_pravidlo(db, user, pravidlo_id)
    _over_pravidlo(vstup)
    p.nazev = (vstup.nazev or "").strip() or p.nazev
    _napln_pravidlo(p, vstup)
    db.commit()
    db.refresh(p)
    return _pravidlo_out(db, p)


@router.post("/pravidla/{pravidlo_id}/prepni", response_model=EmailPravidloOut)
def prepni_pravidlo(
    pravidlo_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    p = _moje_pravidlo(db, user, pravidlo_id)
    p.aktivni = not p.aktivni
    db.commit()
    db.refresh(p)
    return _pravidlo_out(db, p)


@router.delete("/pravidla/{pravidlo_id}")
def smaz_pravidlo(
    pravidlo_id: int,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    p = _moje_pravidlo(db, user, pravidlo_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


def _over_pravidlo(vstup: EmailPravidloVstup) -> None:
    """Pravidlo bez podmínky nebo bez akce je past – neběželo by, nebo by
    přehazovalo všechno. Radši to odmítneme hned."""
    if not vstup.podminky:
        raise HTTPException(
            status_code=422,
            detail="Pravidlo musí mít aspoň jednu podmínku, jinak by se nespustilo nikdy.",
        )
    if not vstup.akce:
        raise HTTPException(
            status_code=422, detail="Pravidlo musí mít aspoň jednu akci – jinak nic nedělá."
        )
    for a in vstup.akce:
        if a.typ == "presun" and not a.slozka_id:
            raise HTTPException(status_code=422, detail="U přesunu vyber cílovou složku.")
        if a.typ == "preposlat" and "@" not in (a.komu or ""):
            raise HTTPException(
                status_code=422, detail="U přeposlání vyplň platnou e-mailovou adresu."
            )


def _napln_pravidlo(p: CrmEmailPravidlo, vstup: EmailPravidloVstup) -> None:
    p.aktivni = bool(vstup.aktivni)
    p.poradi = int(vstup.poradi or 100)
    p.spojka = vstup.spojka
    p.podminky = [x.model_dump() for x in vstup.podminky]
    p.akce = [x.model_dump() for x in vstup.akce]
    p.zastavit_dalsi = bool(vstup.zastavit_dalsi)


@router.put("/automatika", response_model=EmailUcetOut)
def uloz_automatiku(
    vstup: EmailAutomatikaVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """OOO oznámení a automatické přeposílání.

    Obojí dělá **appka sama** – Seznam to zdálky nastavit neumí. Funguje to
    tedy jen když běží worker (`greensie-email.service`).
    """
    ucet = _muj_ucet(db, user)

    if vstup.ooo_zapnuto and not (vstup.ooo_text or "").strip():
        raise HTTPException(
            status_code=422, detail="Napiš text oznámení – prázdnou odpověď posílat nebudeme."
        )
    komu = (vstup.preposilani_komu or "").strip().lower()
    if vstup.preposilani_zapnuto:
        if "@" not in komu:
            raise HTTPException(
                status_code=422, detail="Vyplň platnou adresu, kam se má pošta přeposílat."
            )
        if komu == (ucet.adresa or "").strip().lower():
            # Přeposílání sám sobě je nekonečná smyčka – nikdy to nepovolíme.
            raise HTTPException(
                status_code=422,
                detail="Přeposílat na vlastní adresu nejde – vznikla by nekonečná smyčka.",
            )

    ucet.ooo_zapnuto = bool(vstup.ooo_zapnuto)
    ucet.ooo_od = _na_datum(vstup.ooo_od)
    ucet.ooo_do = _na_datum(vstup.ooo_do)
    ucet.ooo_predmet = (vstup.ooo_predmet or "").strip()
    ucet.ooo_text = vstup.ooo_text or ""
    ucet.preposilani_zapnuto = bool(vstup.preposilani_zapnuto)
    ucet.preposilani_komu = komu
    ucet.preposilani_nechat_kopii = bool(vstup.preposilani_nechat_kopii)
    db.commit()
    db.refresh(ucet)
    return ucet_out(ucet)


def _na_datum(hodnota: str | None) -> date | None:
    if not hodnota:
        return None
    try:
        return date.fromisoformat(str(hodnota)[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Neplatné datum: {hodnota}")


# ---- hromadné akce nad vybranými zprávami ------------------------------------
@router.post("/hromadne", response_model=EmailHromadneOut)
def hromadne(
    vstup: EmailHromadneVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Jedna akce nad víc zprávami najednou (přečteno, vlaječka, přesun, koš).

    Zpracovává se **po jedné**, ne jedním IMAP příkazem na celý výběr. Důvod:
    vybrané zprávy můžou být z různých složek a IMAP pracuje vždy nad jednou
    otevřenou složkou. Za cenu pár desítek milisekund navíc to funguje i pro
    výběr napříč pohledy.

    Když jedna zpráva selže, ostatní se dokončí a v odpovědi je počet
    neúspěchů — hromadná akce nemá padat celá kvůli jedné přesunuté zprávě.
    """
    ucet = _muj_ucet(db, user)
    ids = list(dict.fromkeys(vstup.ids or []))[:500]
    if not ids:
        raise HTTPException(status_code=422, detail="Nevybral jsi žádnou zprávu.")

    cil = None
    if vstup.akce == "presun":
        if not vstup.slozka_id:
            raise HTTPException(status_code=422, detail="Vyber složku, kam se má přesunout.")
        cil = _moje_slozka(db, user, vstup.slozka_id)
    elif vstup.akce == "do_kose":
        cil = email_sync.slozka_druhu(db, ucet.id, "kos")
        if cil is None:
            raise HTTPException(
                status_code=422, detail="Schránka nemá složku Koš, není kam přesunout."
            )

    zpracovano, selhalo = 0, 0
    for zprava_id in ids:
        z = (
            db.query(CrmEmailZprava)
            .filter(CrmEmailZprava.id == zprava_id, CrmEmailZprava.ucet_id == ucet.id)
            .first()
        )
        if z is None:
            selhalo += 1
            continue
        try:
            if vstup.akce in ("precteno", "neprecteno"):
                chtene = vstup.akce == "precteno"
                if z.precteno != chtene:
                    email_sync.nastav_precteno(db, z, chtene)
            elif vstup.akce in ("oznacit", "odznacit"):
                chtene = vstup.akce == "oznacit"
                if z.oznaceno != chtene:
                    email_sync.nastav_oznaceno(db, z, chtene)
            elif cil is not None:
                if z.slozka_id == cil.id:
                    continue  # už tam je, není co dělat
                email_sync.presun_zpravu(db, z, cil)
            zpracovano += 1
        except ImapChyba:
            db.rollback()
            selhalo += 1

    popisy = {
        "precteno": "označeno jako přečtené",
        "neprecteno": "označeno jako nepřečtené",
        "oznacit": "označeno vlaječkou",
        "odznacit": "vlaječka odebrána",
        "presun": f"přesunuto do „{cil.nazev}“" if cil else "přesunuto",
        "do_kose": "přesunuto do koše",
    }
    zprava = f"{zpracovano} {popisy.get(vstup.akce, 'zpracováno')}."
    if selhalo:
        zprava += f" {selhalo} se nepodařilo."
    return EmailHromadneOut(ok=True, zpracovano=zpracovano, selhalo=selhalo, zprava=zprava)


# ---- historie komunikace na kartě zákazníka / případu ------------------------
def vyzaduj_emaily_ctenar(user: User = Depends(get_current_user)) -> User:
    """Pro čtení historie na kartě stačí novinky – vlastní schránku mít nemusí.

    Kdyby se vyžadovalo právo `emaily`, kolega bez připojené schránky by na
    kartě zákazníka historii komunikace neviděl. A právě o to celé jde.
    """
    if not ma_novinky(user):
        raise HTTPException(status_code=404, detail="Nenalezeno")
    return user


@router.get("/historie/{entita}/{zaznam_id}", response_model=EmailHistorieOut)
def historie_komunikace(
    entita: str,
    zaznam_id: int,
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(vyzaduj_emaily_ctenar),
    db: Session = Depends(get_db),
):
    """Pošta napojená na zákazníka („zakaznik") nebo obchodní případ („op").

    POZOR na viditelnost: tohle je **jediné místo, kde se cizí pošta ukazuje**.
    Zpráva se sem dostane jen tehdy, když se její adresa přesně shodovala se
    záznamem v CRM — osobní pošta od neznámých adres se do CRM nedostane vůbec.
    Kdo záznam vidět nesmí, nedostane ani historii (kontroluje se přes
    `pristup.vyzaduj_zaznam`, stejně jako u zbytku karty).

    Obsah zprávy se odsud **nevrací** — jen hlavička a náhled. Kdo chce číst
    celou zprávu, musí být majitel schránky a otevřít si ji v E-mailu.
    """
    from app.crm.models import CrmEmailVazba, ZakaznikKontakt

    if entita == "zakaznik":
        zaznam = pristup.vyzaduj_zaznam(db.get(Zakaznik, zaznam_id), user, "Zákazník")
        podminka = CrmEmailVazba.zakaznik_id == zaznam.id
    elif entita == "op":
        pripad = db.get(ObchodniPripad, zaznam_id)
        if pripad is None:
            raise HTTPException(status_code=404, detail="Případ neexistuje")
        pristup.vyzaduj_zaznam(db.get(Zakaznik, pripad.zakaznik_id), user, "Zákazník")
        # U případu bereme i poštu firmy bez konkrétního případu – jinak by
        # karta případu byla prázdná, dokud někdo nepřiřadí ručně.
        podminka = (CrmEmailVazba.pripad_id == pripad.id) | (
            (CrmEmailVazba.zakaznik_id == pripad.zakaznik_id)
            & (CrmEmailVazba.pripad_id.is_(None))
        )
    else:
        raise HTTPException(status_code=422, detail="Neznámý typ záznamu.")

    q = (
        db.query(CrmEmailVazba, CrmEmailZprava, CrmEmailUcet)
        .join(CrmEmailZprava, CrmEmailVazba.zprava_id == CrmEmailZprava.id)
        .join(CrmEmailUcet, CrmEmailZprava.ucet_id == CrmEmailUcet.id)
        .filter(podminka, CrmEmailVazba.skryta.is_(False))
        .order_by(CrmEmailZprava.datum_at.desc())
    )
    celkem = q.count()
    radky = q.limit(limit).all()

    kontakty = {
        k.id: k.jmeno
        for k in db.query(ZakaznikKontakt).filter(
            ZakaznikKontakt.id.in_([v.kontakt_id for v, _z, _u in radky if v.kontakt_id] or [0])
        )
    }
    cisla = {
        p.id: p.cislo
        for p in db.query(ObchodniPripad).filter(
            ObchodniPripad.id.in_([v.pripad_id for v, _z, _u in radky if v.pripad_id] or [0])
        )
    }
    jmena = {
        u.id: (u.jmeno or u.email)
        for u in db.query(User).filter(
            User.id.in_([u.user_id for _v, _z, u in radky] or [0])
        )
    }

    return EmailHistorieOut(
        celkem=celkem,
        zpravy=[
            EmailKZaznamuOut(
                id=z.id,
                predmet=z.predmet,
                od_jmeno=z.od_jmeno,
                od_adresa=z.od_adresa,
                komu=_adresy_out(z.komu),
                datum_at=_cas(z.datum_at) or "",
                smer=z.smer,
                vypis=z.vypis,
                ma_prilohy=z.ma_prilohy,
                kdo=jmena.get(ucet.user_id, ""),
                moje=ucet.user_id == user.id,
                kontakt_jmeno=kontakty.get(v.kontakt_id, ""),
                pripad_cislo=cisla.get(v.pripad_id, ""),
            )
            for v, z, ucet in radky
        ],
    )


@router.post("/zpravy/{zprava_id}/vazba")
def uprav_vazbu(
    zprava_id: int,
    vstup: EmailVazbaVstup,
    user: User = Depends(vyzaduj_emaily),
    db: Session = Depends(get_db),
):
    """Ruční napojení zprávy na firmu, nebo její schování z historie.

    Schování **nemaže** vazbu, jen ji označí — smazaná by ji automatika při
    příští synchronizaci vyrobila znovu a zpráva by se na kartu vrátila.
    """
    from app.crm.models import CrmEmailVazba

    z = _moje_zprava(db, user, zprava_id)

    if vstup.skryt:
        pocet = (
            db.query(CrmEmailVazba)
            .filter(CrmEmailVazba.zprava_id == z.id)
            .update({"skryta": True, "zdroj": "rucne"}, synchronize_session=False)
        )
        db.commit()
        return {"ok": True, "skryto": pocet}

    if not vstup.zakaznik_id:
        raise HTTPException(status_code=422, detail="Vyber firmu, ke které zprávu připojit.")
    zakaznik = pristup.vyzaduj_zaznam(db.get(Zakaznik, vstup.zakaznik_id), user, "Zákazník")

    vazba = (
        db.query(CrmEmailVazba)
        .filter(
            CrmEmailVazba.zprava_id == z.id,
            CrmEmailVazba.zakaznik_id == zakaznik.id,
        )
        .first()
    )
    if vazba is None:
        vazba = CrmEmailVazba(zprava_id=z.id, zakaznik_id=zakaznik.id, kdy=z.datum_at)
        db.add(vazba)
    vazba.pripad_id = vstup.pripad_id
    vazba.zdroj = "rucne"
    vazba.skryta = False
    if z.zakaznik_id is None:
        z.zakaznik_id = zakaznik.id
    db.commit()
    return {"ok": True}
