"""Časové spouštěče automatizace: „5 dní před termínem“, „14 dní beze změny“ (CRM-31).

Jedno vlákno na pozadí, stejný vzor jako `notifikace_scheduler`. Jednou denně
projde pravidla s časovým spouštěčem a najde záznamy, na které dnes sedí.

---- Proč jednou denně, a ne „přesně v ten okamžik“ --------------------------

Časová pravidla stojí na DNECH, ne na hodinách („pět dní před uzavřením“).
Kontrola po minutách by nic nepřidala a znamenala by desítky zbytečných dotazů
za hodinu. Jednou denně po sedmé ráno je i to, co člověk čeká: úkol „zavolat“
má vyskočit ráno, ne v půl třetí v noci.

---- Proč „už nastal“, a ne „nastane právě dnes“ -----------------------------

Kdyby se hledalo `termín − 5 = dnes`, jediný den, kdy server neběžel (nasazení,
restart, výpadek), by pravidlo přeskočil a nikdo by se to nedozvěděl. Proto se
hledá `termín − 5 <= dnes`: pravidlo zabere při prvním probuzení po tom dni.
Že se to nestane podruhé, hlídá běh pravidla (`opakovat="jednou"`), ne datum.

---- Proč to smí běžet ve web procesu ----------------------------------------

Vlákno je vědomě LEHKÉ: jednou za den, jeden dotaz na pravidla, a když žádné
časové pravidlo neexistuje (výchozí stav appky), skončí bez dalšího dotazu.
Záznamy se navíc berou po dávkách s tvrdým stropem. Kdyby přibylo něco těžšího,
patří to do samostatného procesu — ne sem (viz zkušenost s konektory a 502).
"""

import logging
import threading
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.crm import automatizace as engine
from app.crm import automatizace_pole as pole_modul
from app.crm.models import CrmAktivita, CrmPravidlo, CrmStav, CrmStavHistorie
from app.database import SessionLocal

log = logging.getLogger(__name__)

# Jak často se vlákno probouzí (ne jak často pracuje).
KONTROLA_S = 300
# Prodleva po startu, ať se stihne nastartovat zbytek backendu.
START_PRODLEVA_S = 60
# Od kolika hodin se smí pracovat (místní čas serveru).
HODINA_OD = 7
# Klíč, pod kterým si pamatujeme datum posledního běhu.
KLIC_POSLEDNI_BEH = "crm_automatizace_posledni_beh"
# Kolik záznamů nejvýš projde jedno pravidlo za jeden den. Pojistka proti tomu,
# aby špatně napsané pravidlo („0 dní beze změny“) nepřejelo celou databázi.
# Když se strop vyčerpá, zbytek se dodělá zítra a v logu je o tom řádek.
STROP_ZAZNAMU = 200

_stop = threading.Event()
_thread: threading.Thread | None = None


# ---- paměť posledního běhu ---------------------------------------------------
def _precti_posledni_beh(db: Session) -> str:
    from app.nastaveni.models import UzivatelskeNastaveni

    row = (
        db.query(UzivatelskeNastaveni)
        .filter(UzivatelskeNastaveni.klic == KLIC_POSLEDNI_BEH)
        .first()
    )
    return str((row.hodnota or {}).get("den", "")) if row is not None else ""


def _zapis_posledni_beh(db: Session, den: str) -> None:
    from app.auth.models import User
    from app.nastaveni.models import UzivatelskeNastaveni

    row = (
        db.query(UzivatelskeNastaveni)
        .filter(UzivatelskeNastaveni.klic == KLIC_POSLEDNI_BEH)
        .first()
    )
    if row is None:
        # Řádek potřebuje uzivatel_id (FK). Bereme nejnižší id – je to systémový
        # záznam, ne uživatelská volba, a nikde se nezobrazuje.
        prvni = db.query(User).order_by(User.id).first()
        if prvni is None:
            return
        row = UzivatelskeNastaveni(uzivatel_id=prvni.id, klic=KLIC_POSLEDNI_BEH)
        db.add(row)
    row.hodnota = {"den": den}


# ---- hledání záznamů, na které pravidlo dnes sedí ---------------------------
def _otevrene_stavy(db: Session, entita: str) -> list[str]:
    """Klíče stavů, které znamenají „záznam je živý“.

    Uzavřené případy (vyhrané i prohrané) se z časových pravidel vynechávají:
    upomínka „ozvi se, dlouho se nic neděje“ u prohraného případu z loňska je
    přesně ten druh šumu, kvůli kterému lidi automatiku vypnou.
    """
    return [
        s.klic
        for s in db.query(CrmStav).filter(CrmStav.entita == entita, CrmStav.druh == "otevreny")
    ]


def _sloupec_stavu(entita: str) -> str:
    # Nabídka drží obchodní stav v jiném sloupci než stav zpracování výpočtu.
    return "stav_obchodni" if entita == "nab" else "stav"


def _zaznamy_podle_pole(db: Session, pravidlo: CrmPravidlo, dnes: date) -> list:
    """Záznamy, kterým už nastal den `datum v poli + posun`."""
    model = pole_modul.model_entity(pravidlo.spoust_entita)
    nastaveni = pravidlo.cas_nastaveni or {}
    klic = str(nastaveni.get("pole") or "")
    posun = int(nastaveni.get("posun_dni") or 0)
    if model is None or not klic:
        return []

    # Mez pro sloupec: hledáme `pole + posun <= dnes`, tedy `pole <= dnes - posun`.
    mez = dnes - timedelta(days=posun)

    if klic.startswith(pole_modul.PREDPONA_VLASTNI):
        # Vlastní pole je text v JSONB – porovnání dat nechávám na Pythonu,
        # protože přetypování v SQL by spadlo na jednom křivě vyplněném řádku.
        vybrane = _zive_zaznamy(db, pravidlo, model)
        return [
            z
            for z in vybrane
            if (d := pole_modul.na_datum(pole_modul.hodnota(z, klic))) is not None and d <= mez
        ]

    sloupec = getattr(model, klic, None)
    if sloupec is None:
        return []
    return _zive_zaznamy(db, pravidlo, model, sloupec.isnot(None), sloupec <= mez)


def _zive_zaznamy(db: Session, pravidlo: CrmPravidlo, model, *filtry) -> list:
    """Otevřené záznamy entity s uplatněnými filtry a stropem."""
    q = db.query(model)
    stavy = _otevrene_stavy(db, pravidlo.spoust_entita)
    sloupec_stavu = getattr(model, _sloupec_stavu(pravidlo.spoust_entita), None)
    if stavy and sloupec_stavu is not None:
        q = q.filter(sloupec_stavu.in_(stavy))
    for f in filtry:
        q = q.filter(f)
    return q.order_by(model.id).limit(STROP_ZAZNAMU + 1).all()


def _zaznamy_necinne(db: Session, pravidlo: CrmPravidlo, dnes: date) -> list:
    """Záznamy, se kterými se N dní nic nedělo.

    „Nic se nedělo“ znamená obojí: neuložila se změna záznamu **a** nepřibyla
    aktivita. Kdyby se koukalo jen na `aktualizovano_at`, upomínka by chodila
    i na případ, kde obchodník včera zapsal hovor — a to je zpráva, po které
    člověk automatiku vypne.
    """
    model = pole_modul.model_entity(pravidlo.spoust_entita)
    dni = int((pravidlo.cas_nastaveni or {}).get("dni") or 0)
    if model is None or dni < 1:
        return []
    mez = datetime.combine(dnes - timedelta(days=dni), datetime.min.time())

    sloupec = getattr(model, "aktualizovano_at", None) or getattr(model, "vytvoreno_at", None)
    if sloupec is None:
        return []
    kandidati = _zive_zaznamy(db, pravidlo, model, sloupec <= mez)
    if not kandidati:
        return []

    # Poslední aktivita u nalezených záznamů – jedním dotazem, ne dotazem na
    # každý záznam zvlášť.
    from sqlalchemy import func as sa_func

    posledni = dict(
        db.query(CrmAktivita.zaznam_id, sa_func.max(CrmAktivita.vytvoreno_at))
        .filter(
            CrmAktivita.entita == pravidlo.spoust_entita,
            CrmAktivita.zaznam_id.in_([z.id for z in kandidati]),
        )
        .group_by(CrmAktivita.zaznam_id)
        .all()
    )
    out = []
    for z in kandidati:
        kdy = posledni.get(z.id)
        if kdy is not None and kdy.replace(tzinfo=None) > mez:
            continue
        out.append(z)
    return out


def _zaznamy_ve_stavu(db: Session, pravidlo: CrmPravidlo, dnes: date) -> list:
    """Záznamy, které leží ve svém současném stavu déle než N dní."""
    from sqlalchemy import func as sa_func

    model = pole_modul.model_entity(pravidlo.spoust_entita)
    dni = int((pravidlo.cas_nastaveni or {}).get("dni") or 0)
    if model is None or dni < 1:
        return []
    mez = datetime.combine(dnes - timedelta(days=dni), datetime.min.time())

    kandidati = _zive_zaznamy(db, pravidlo, model)
    if not kandidati:
        return []
    # Kdy záznam naposled někam přešel. Bez řádku v historii (starý import) se
    # bere datum vzniku – jinak by se pravidlo takového záznamu nikdy nechytlo.
    prechody = dict(
        db.query(CrmStavHistorie.zaznam_id, sa_func.max(CrmStavHistorie.zmeneno_at))
        .filter(
            CrmStavHistorie.entita == pravidlo.spoust_entita,
            CrmStavHistorie.zaznam_id.in_([z.id for z in kandidati]),
        )
        .group_by(CrmStavHistorie.zaznam_id)
        .all()
    )
    out = []
    for z in kandidati:
        kdy = prechody.get(z.id) or getattr(z, "vytvoreno_at", None)
        if kdy is None:
            continue
        if kdy.replace(tzinfo=None) <= mez:
            out.append(z)
    return out


HLEDACE = {
    "pole": _zaznamy_podle_pole,
    "necinnost": _zaznamy_necinne,
    "ve_stavu": _zaznamy_ve_stavu,
}


def kandidati(db: Session, pravidlo: CrmPravidlo, dnes: date | None = None) -> list:
    """Záznamy, na které časové pravidlo dnes sedí (bez ohledu na už proběhlé běhy).

    Veřejné kvůli UI: v nastavení se u pravidla ukazuje „teď by sedělo na 4
    záznamy", aby člověk nemusel čekat do rána, jestli si pravidlo napsal dobře.
    """
    zaklad = str((pravidlo.cas_nastaveni or {}).get("zaklad") or "")
    hledac = HLEDACE.get(zaklad)
    if hledac is None:
        return []
    try:
        return hledac(db, pravidlo, dnes or date.today())
    except Exception:  # noqa: BLE001 - špatně napsané pravidlo nesmí shodit plánovač
        log.warning("Automatizace: hledání záznamů pro pravidlo %s selhalo", pravidlo.id, exc_info=True)
        return []


# ---- denní běh ---------------------------------------------------------------
def zpracuj_casova_pravidla(db: Session, dnes: date | None = None) -> int:
    """Projde časová pravidla a spustí je, kde sedí. Vrací počet provedení.

    Commit je po každém pravidle, ne na konci: kdyby patnácté pravidlo spadlo
    na chybě v databázi, prvních čtrnáct už má být uložených. Zároveň to drží
    transakce krátké, takže noční běh neblokuje ranní práci v appce.
    """
    dnes = dnes or date.today()
    pravidla = (
        db.query(CrmPravidlo)
        .filter(CrmPravidlo.aktivni.is_(True), CrmPravidlo.spoust_typ == "cas")
        .order_by(CrmPravidlo.poradi, CrmPravidlo.id)
        .all()
    )
    if not pravidla:
        return 0

    celkem = 0
    for pravidlo in pravidla:
        nalezene = kandidati(db, pravidlo, dnes)
        if len(nalezene) > STROP_ZAZNAMU:
            log.warning(
                "Automatizace: pravidlo %s („%s“) sedí na víc než %s záznamů, "
                "zbytek se dodělá zítra",
                pravidlo.id,
                pravidlo.nazev,
                STROP_ZAZNAMU,
            )
            nalezene = nalezene[:STROP_ZAZNAMU]

        provedeno = 0
        for zaznam in nalezene:
            if engine.uz_bezelo(db, pravidlo, pravidlo.spoust_entita, zaznam.id):
                continue
            kontext = engine.Kontext(
                entita=pravidlo.spoust_entita,
                zaznam=zaznam,
                # Časové pravidlo nespustil žádný člověk. `None` je správně:
                # podepsat běh náhodným adminem by v historii záznamu lhalo.
                user=None,
                pravidlo=pravidlo,
                spoustec="cas",
            )
            if engine.spust_pravidlo(db, pravidlo, kontext):
                provedeno += 1
        if provedeno:
            celkem += provedeno
            log.info(
                "Automatizace: pravidlo „%s“ zabralo na %s záznamech", pravidlo.nazev, provedeno
            )
        try:
            db.commit()
        except Exception:  # noqa: BLE001 - jedno rozbité pravidlo nesmí zastavit ostatní
            log.warning("Automatizace: uložení běhu pravidla %s selhalo", pravidlo.id, exc_info=True)
            db.rollback()

    _zapis_posledni_beh(db, dnes.isoformat())
    db.commit()
    return celkem


def _mozna_zpracuj() -> None:
    ted = datetime.now()
    if ted.hour < HODINA_OD:
        return
    db = SessionLocal()
    try:
        if _precti_posledni_beh(db) == ted.date().isoformat():
            return  # dnes už proběhlo
        pocet = zpracuj_casova_pravidla(db)
        if pocet:
            log.info("Automatizace: časová pravidla provedena (%s záznamů)", pocet)
    except Exception:  # noqa: BLE001 - plánovač nikdy nesmí shodit app
        log.warning("Automatizace: denní běh selhal", exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


def _smycka() -> None:
    if _stop.wait(START_PRODLEVA_S):
        return
    while not _stop.is_set():
        _mozna_zpracuj()
        if _stop.wait(KONTROLA_S):
            return


def spust_planovac() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_smycka, name="crm-automatizace", daemon=True)
    _thread.start()


def zastav_planovac() -> None:
    _stop.set()
