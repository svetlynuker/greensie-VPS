"""Denní souhrn úkolů (CRM-10).

Jedno vlákno na pozadí, stejný vzor jako `matice.scheduler` a `konektor.scheduler`.
Jednou za den (ráno) projde nehotové úkoly a pošle každému jeho souhrn:
co má dnes a co je po termínu.

---- Proč souhrn, a ne notifikace u každého úkolu -----------------------------

Pět úkolů = pět e-mailů = člověk si notifikace vypne a už se nikdy nezapnou.
Jeden e-mail „máš 3 úkoly na dnes a 2 po termínu" je zpráva, kterou si někdo
opravdu přečte.

---- Proč se to hlídá přes `posledni_beh`, ne přes „je 7 hodin" ---------------

Backend se restartuje při každém nasazení. Kdyby se souhrn posílal „když je
právě 7:00", při restartu v 7:00 by se poslal dvakrát, a při restartu v 6:59
vůbec. Proto se pamatuje datum posledního běhu v `uzivatelska_nastaveni`
(systémový řádek, uživatel_id nejnižšího admina) a posílá se jednou za den,
při prvním probuzení po zvolené hodině.

Pozor na [[konektory-samostatne-procesy]]: tohle vlákno je vědomě LEHKÉ (jeden
dotaz denně), takže může běžet ve web procesu. Kdyby přibylo něco těžšího,
patří to ven, ne sem.
"""

import logging
import threading
from datetime import date, datetime

from app.database import SessionLocal

log = logging.getLogger(__name__)

# Jak často se vlákno probouzí (ne jak často posílá).
KONTROLA_S = 300
# Prodleva po startu, ať se stihne nastartovat zbytek backendu.
START_PRODLEVA_S = 60
# Od kolika hodin se smí posílat ranní souhrn (místní čas serveru).
HODINA_OD = 7
# Klíč, pod kterým si pamatujeme datum posledního rozeslání.
KLIC_POSLEDNI_BEH = "crm_notifikace_posledni_souhrn"

_stop = threading.Event()
_thread: threading.Thread | None = None


def _precti_posledni_beh(db) -> str:
    from app.nastaveni.models import UzivatelskeNastaveni

    row = (
        db.query(UzivatelskeNastaveni)
        .filter(UzivatelskeNastaveni.klic == KLIC_POSLEDNI_BEH)
        .first()
    )
    return str((row.hodnota or {}).get("den", "")) if row is not None else ""


def _zapis_posledni_beh(db, den: str) -> None:
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


def posli_denni_souhrny(db) -> int:
    """Rozešle souhrn úkolů. Vrací počet lidí, kterým něco odešlo."""
    from app.auth.models import User
    from app.crm import notifikace as notifikace_modul
    from app.crm import ukoly as ukoly_modul

    dnes = date.today()
    posláno = 0
    for u in db.query(User).order_by(User.id).all():
        ukoly = ukoly_modul.moje_ukoly(db, u)
        if not ukoly:
            continue
        # `dni` je kladné, když je úkol po termínu (konvence z ukoly.py).
        po_terminu = [x for x in ukoly if x.dni > 0]
        na_dnes = [x for x in ukoly if x.dni == 0]

        if po_terminu:
            nejstarsi = max(x.dni for x in po_terminu)
            notifikace_modul.posli(
                db,
                u,
                "ukol_po_terminu",
                f"{len(po_terminu)}× úkol po termínu",
                f"Nejdéle čeká úkol „{po_terminu[0].nazev or 'bez názvu'}“ "
                f"({nejstarsi} dní po termínu). Otevři si Můj den a projdi je.",
                "/muj-den",
            )
            posláno += 1
        if na_dnes:
            notifikace_modul.posli(
                db,
                u,
                "ukol_dnes",
                f"Dnes tě čeká {len(na_dnes)}× úkol",
                "; ".join((x.nazev or "bez názvu") for x in na_dnes[:5])
                + ("…" if len(na_dnes) > 5 else ""),
                "/muj-den",
            )
            posláno += 1

    _zapis_posledni_beh(db, dnes.isoformat())
    db.commit()
    return posláno


def _mozna_posli() -> None:
    ted = datetime.now()
    if ted.hour < HODINA_OD:
        return
    db = SessionLocal()
    try:
        if _precti_posledni_beh(db) == ted.date().isoformat():
            return  # dnes už odešlo
        pocet = posli_denni_souhrny(db)
        if pocet:
            log.info("Denní souhrn úkolů rozeslán (%s zpráv)", pocet)
    except Exception:  # noqa: BLE001 - plánovač nikdy nesmí shodit app
        log.warning("Denní souhrn úkolů selhal", exc_info=True)
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
        _mozna_posli()
        if _stop.wait(KONTROLA_S):
            return


def spust_planovac() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_smycka, name="crm-notifikace", daemon=True)
    _thread.start()


def zastav_planovac() -> None:
    _stop.set()
