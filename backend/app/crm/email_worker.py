"""Stahování pošty na pozadí – **samostatný proces**, ne vlákno ve webu.

ROZHODNUTÍ DANA (31. 7. 2026): e-mail běží jako vlastní systemd služba
(`greensie-email.service`), ne uvnitř backendu. Důvod je zkušenost s konektorem:
pomalé volání cizí služby uvnitř web procesu dokáže appku dotlačit k 502.
IMAP je na tohle ještě horší kandidát než HTTP – jeden FETCH velké schránky
trvá desítky sekund a Seznam občas neodpoví vůbec.

Praktický důsledek: appka a stahování pošty se restartují nezávisle. Když
worker neběží, appka funguje dál, jen se pošta nestahuje sama (a v UI je vidět
čas posledního stažení, aby to nebylo tiché).

---- Jak se spouští --------------------------------------------------------
    venv/bin/python -m app.crm.email_worker          # ručně, pro ladění
    systemctl start greensie-email                    # na produkci

---- Dvě rychlosti ---------------------------------------------------------
Doručená pošta se kontroluje často (`INTERVAL_INBOX_S`), zbytek složek jen
občas (`INTERVAL_PLNY_S`). Bez tohohle rozdělení by se každou minutu procházelo
dvacet složek kvůli jedné nové zprávě, což je zbytečná zátěž na nás i na Seznam.

IMAP IDLE (server sám oznámí novou zprávu) by bylo hezčí, ale `imaplib`
v Pythonu 3.11 ho neumí a psát si vlastní implementaci kvůli minutové úspoře
nemá smysl. Až appka poběží na 3.13+, dá se to doplnit bez zásahu do zbytku.

---- Vlákno nikdy nespadne -------------------------------------------------
Každý krok má vlastní `try`. Chyba jedné schránky nesmí zastavit ostatní ani
shodit celou smyčku – jinak by jedno špatné heslo zastavilo poštu všem.
"""

import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

from app.crm.email_imap import ImapChyba
from app.crm.models import CrmEmailUcet
from app.database import SessionLocal

# Jak často se kontroluje Doručená pošta. Minuta je kompromis: člověk to bere
# jako „hned", a přitom to je 60 spojení na schránku za hodinu, což je slušné.
INTERVAL_INBOX_S = int(os.environ.get("EMAIL_INTERVAL_INBOX_S", "60"))
# Jak často se projdou všechny složky (odeslané, vlastní složky, archiv).
INTERVAL_PLNY_S = int(os.environ.get("EMAIL_INTERVAL_PLNY_S", "900"))
# Po startu chvíli počkat – při restartu serveru se rozjíždí i databáze.
START_PRODLEVA_S = int(os.environ.get("EMAIL_START_PRODLEVA_S", "5"))
# Po kolikáté chybě za sebou se schránka odloží (špatné heslo nemá smysl zkoušet
# každou minutu – Seznam by nás mohl začít blokovat).
CHYB_PRO_ODLOZENI = 3
ODLOZENI_MIN = 30

_stop = threading.Event()
_log = logging.getLogger("greensie.email")

# Kolik chyb za sebou která schránka nasbírala a dokdy je odložená.
_chyby: dict[int, int] = {}
_odlozeno_do: dict[int, datetime] = {}


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def _aktivni_ucty(db) -> list[CrmEmailUcet]:
    return (
        db.query(CrmEmailUcet)
        .filter(CrmEmailUcet.aktivni.is_(True), CrmEmailUcet.sync_zapnuto.is_(True))
        .filter(CrmEmailUcet.heslo_sifra != "")
        .order_by(CrmEmailUcet.id)
        .all()
    )


def _je_odlozeny(ucet_id: int) -> bool:
    do_kdy = _odlozeno_do.get(ucet_id)
    if do_kdy is None:
        return False
    if _ted() >= do_kdy:
        _odlozeno_do.pop(ucet_id, None)
        _chyby[ucet_id] = 0
        return False
    return True


def _zapis_chybu(ucet_id: int, adresa: str, chyba: Exception) -> None:
    pocet = _chyby.get(ucet_id, 0) + 1
    _chyby[ucet_id] = pocet
    if pocet >= CHYB_PRO_ODLOZENI:
        _odlozeno_do[ucet_id] = _ted() + timedelta(minutes=ODLOZENI_MIN)
        _log.warning(
            "Schránka %s selhala %d× za sebou – odkládám na %d min. Poslední chyba: %s",
            adresa, pocet, ODLOZENI_MIN, chyba,
        )
    else:
        _log.warning("Schránka %s: %s (pokus %d)", adresa, chyba, pocet)


# Poslední ohlášená chyba databáze – ať se tatáž hláška neopakuje každý cyklus.
_posledni_chyba_db: str = ""


def _ohlas_chybu_db(chyba: Exception) -> None:
    """Krátká hláška místo celého SQL dumpu, a jen když se text změní.

    Dvě věci, které to řeší. Za prvé: tabulky e-mailu vznikají při startu
    **backendu** (`create_all`), a tahle služba může naběhnout dřív – pak by
    do journalu každou minutu spadl několikakilobajtový SELECT, ve kterém se
    skutečné problémy ztratí. Za druhé: opakovaná tatáž chyba nenese žádnou
    novou informaci, stačí ohlásit změnu stavu.
    """
    global _posledni_chyba_db
    text = str(chyba)
    if "does not exist" in text and "crm_email_" in text:
        strucne = (
            "Tabulky e-mailu v databázi ještě nejsou. Vzniknou při startu backendu "
            "(greensie-backend) – do té doby se čeká."
        )
    else:
        strucne = f"Databáze není dostupná: {text.splitlines()[0][:300]}"
    if strucne == _posledni_chyba_db:
        return
    _posledni_chyba_db = strucne
    _log.warning("%s", strucne)


def _cyklus(jen_inbox: bool) -> None:
    """Jeden průběh přes všechny aktivní schránky."""
    from app.crm import email_sync

    db = SessionLocal()
    try:
        ucty = _aktivni_ucty(db)
    except Exception as e:  # noqa: BLE001 - nedostupná DB nesmí shodit worker
        db.rollback()
        db.close()
        _ohlas_chybu_db(e)
        return

    global _posledni_chyba_db
    _posledni_chyba_db = ""

    for ucet in ucty:
        if _stop.is_set():
            break
        if _je_odlozeny(ucet.id):
            continue
        try:
            vysledek = email_sync.synchronizuj_ucet(db, ucet, jen_inbox=jen_inbox)
            _chyby[ucet.id] = 0
            if vysledek["nove"] or vysledek["zmenene"] or vysledek["smazane"]:
                _log.info(
                    "%s: nových %d, změněných %d, zmizelých %d (%.1f s)",
                    ucet.adresa, vysledek["nove"], vysledek["zmenene"],
                    vysledek["smazane"], vysledek.get("trvani_s", 0),
                )
            # Automatika (pravidla, OOO, přeposílání) přijde v dávce E4 – tady
            # bude její jediné volání, aby běžela mimo web proces jako sync.
            _zpracuj_automatiku(db, ucet)
        except ImapChyba as e:
            db.rollback()
            _zapis_chybu(ucet.id, ucet.adresa, e)
        except Exception as e:  # noqa: BLE001 - jedna schránka nesmí zastavit ostatní
            db.rollback()
            _log.exception("Neočekávaná chyba u schránky %s: %s", ucet.adresa, e)
            _zapis_chybu(ucet.id, ucet.adresa, e)
    db.close()


def _zpracuj_automatiku(db, ucet: CrmEmailUcet) -> None:
    """Pravidla, OOO a přeposílání nad nově staženými zprávami.

    Volá se **jen odsud**, nikdy z web procesu: odeslání OOO odpovědi trvá
    sekundy a nesmí zdržovat HTTP požadavek uživatele.
    """
    from app.crm import email_automat

    try:
        pocty = email_automat.zpracuj_nove(db, ucet)
    except Exception as e:  # noqa: BLE001 - automatika nesmí zastavit stahování
        db.rollback()
        _log.warning("Automatika u %s selhala: %s", ucet.adresa, e)
        return
    if pocty["pravidel"] or pocty["ooo"] or pocty["preposlano"]:
        _log.info(
            "%s: pravidel %d, OOO odpovědí %d, přeposláno %d",
            ucet.adresa, pocty["pravidel"], pocty["ooo"], pocty["preposlano"],
        )


def _smycka() -> None:
    if _stop.wait(START_PRODLEVA_S):
        return
    posledni_plny = 0.0
    _log.info(
        "Worker e-mailu běží (Doručená každých %d s, všechny složky každých %d s).",
        INTERVAL_INBOX_S, INTERVAL_PLNY_S,
    )
    while not _stop.is_set():
        nyni = time.monotonic()
        plny = (nyni - posledni_plny) >= INTERVAL_PLNY_S
        try:
            _cyklus(jen_inbox=not plny)
        except Exception as e:  # noqa: BLE001 - smyčka nesmí nikdy spadnout
            _log.exception("Chyba v cyklu workeru: %s", e)
        if plny:
            posledni_plny = nyni
        _stop.wait(INTERVAL_INBOX_S)
    _log.info("Worker e-mailu končí.")


def zastav(*_args) -> None:
    _stop.set()


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("EMAIL_LOG_UROVEN", "INFO").upper(),
        # systemd si čas loguje sám, takže tady jen úroveň a text.
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    # Bez tohohle by `systemctl stop` čekal na timeout a killoval proces.
    signal.signal(signal.SIGTERM, zastav)
    signal.signal(signal.SIGINT, zastav)

    # VŠECHNY modely se musí zaregistrovat, ne jen ty, které worker sám používá.
    # SQLAlchemy inicializuje mappery jako celek: `Objednavka` z CRM se odkazuje
    # na `Faktura` z modulu finance, takže bez jejího importu spadne úplně první
    # dotaz na „name 'Faktura' is not defined" – a to i u dotazu na schránky,
    # který s fakturami nemá nic společného. Web proces tenhle problém nemá,
    # protože `app.main` importuje všechno.
    from app.auth import models as _auth_models  # noqa: F401
    from app.finance import models as _finance_models  # noqa: F401
    from app.konektor import models as _konektor_models  # noqa: F401
    from app.matice import models as _matice_models  # noqa: F401
    from app.nabidkovac import models as _nabidkovac_models  # noqa: F401
    from app.nastaveni import models as _nastaveni_models  # noqa: F401
    from app.crm import models as _crm_models  # noqa: F401

    try:
        _smycka()
    finally:
        from app.crm import email_pool

        email_pool.zahod_vse()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
