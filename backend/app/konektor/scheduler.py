"""Worker konektoru – zpracování DB fronty úloh na pozadí.

Jedno vlákno (vzor matice.scheduler): probouzí se každých pár sekund, vezme
splatné pending úlohy a zpracuje je sekvenčně. Sekvenční běh v jednom vlákně
drží souběžnost vůči Raynetu na 1 (limit 4 spojení tím bezpečně dodržíme).

Chyby úloh se řeší retry s exponenciálním backoffem; po vyčerpání pokusů
úloha přejde do `failed`. Vlákno samo nikdy nespadne (chyby polkne).
"""

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.konektor.logger import zaloguj
from app.konektor.logika import NastaveniNepripraveno
from app.konektor.models import KonektorJobQueue, KonektorNastaveni

KONTROLA_S = 5  # jak často worker kontroluje frontu
START_PRODLEVA_S = 10  # počkat po startu, než se rozběhne zbytek backendu
MAX_POKUSU = 6
DAVKA = 10  # kolik úloh zpracovat v jednom cyklu
WATCH_KONTROLA_S = 300  # jak často kontrolovat/obnovovat push kanál

_stop = threading.Event()
_thread: threading.Thread | None = None
_dalsi_watch_kontrola: datetime | None = None


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def _backoff_s(attempts: int) -> int:
    """Exponenciální backoff s horní hranicí 1 h."""
    return min(60 * (2 ** attempts), 3600)


def _zpracuj_job(db: Session, job: KonektorJobQueue) -> None:
    """Vykoná jednu úlohu podle typu. Chyba probublá k retry logice."""
    from app.konektor.logika import (
        zpracuj_drive_zmeny,
        zpracuj_novy_klient,
        zpracuj_raynet_dokument,
        zrcadli_strom,
    )

    if job.typ == "novy_klient":
        zpracuj_novy_klient(db, int(job.payload["company_id"]))
    elif job.typ == "drive_zmeny":
        zpracuj_drive_zmeny(db)
    elif job.typ == "raynet_dokument":
        zpracuj_raynet_dokument(db, str(job.payload["document_id"]), job.payload.get("company_id"))
    elif job.typ == "zrcadleni":
        zrcadli_strom(db)
    else:
        raise RuntimeError(f"Neznámý typ úlohy: {job.typ}")


def _tik() -> None:
    db = SessionLocal()
    try:
        jobs = (
            db.query(KonektorJobQueue)
            .filter(KonektorJobQueue.status == "pending", KonektorJobQueue.run_after <= _ted())
            .order_by(KonektorJobQueue.run_after)
            .limit(DAVKA)
            .all()
        )
        for job in jobs:
            job_id = job.id
            try:
                _zpracuj_job(db, job)
                job.status = "done"
                job.last_error = None
                db.commit()
            except NastaveniNepripraveno as e:
                # bez přístupů nemá smysl opakovat – úlohu odložíme jako hotovou
                db.rollback()
                job = db.get(KonektorJobQueue, job_id)
                if job is not None:
                    job.status = "done"
                    job.last_error = f"Přeskočeno – {e}"
                    db.commit()
                zaloguj(db, "info", "job", f"Úloha {job.typ} #{job_id} přeskočena: {e}", {"job_id": job_id})
            except Exception as e:  # noqa: BLE001 - úlohu nesmí shodit celý worker
                db.rollback()
                job = db.get(KonektorJobQueue, job_id)  # po rollbacku znovu načíst
                if job is None:
                    continue
                job.attempts += 1
                job.last_error = str(e)[:2000]
                trvale = job.attempts >= MAX_POKUSU
                if trvale:
                    job.status = "failed"
                else:
                    job.run_after = _ted() + timedelta(seconds=_backoff_s(job.attempts))
                db.commit()
                zaloguj(
                    db,
                    "error" if trvale else "warn",
                    "job",
                    (
                        f"Úloha {job.typ} #{job.id} selhala natrvalo: {e}"
                        if trvale
                        else f"Úloha {job.typ} #{job.id} selhala (pokus {job.attempts}), zkusím znovu: {e}"
                    ),
                    {"job_id": job.id, "attempts": job.attempts},
                )
    finally:
        db.close()


def _mozna_reconcile() -> None:
    """Periodický reconcile (changes.list) dle intervalu, jen když je automatika
    zapnutá. Stav se drží v KonektorNastaveni.posledni_beh/posledni_vysledek."""
    from app.konektor.logika import zpracuj_drive_zmeny

    db = SessionLocal()
    try:
        n = db.get(KonektorNastaveni, 1)
        if n is None or not n.auto_zapnuto:
            return
        ted = _ted()
        if n.posledni_beh is not None:
            dalsi = n.posledni_beh + timedelta(minutes=max(5, n.reconcile_interval_min))
            if ted < dalsi:
                return
        try:
            v = zpracuj_drive_zmeny(db)
            if v.get("inicializace"):
                n.posledni_vysledek = "Sledování změn inicializováno (od teď)."
            else:
                n.posledni_vysledek = (
                    f"OK – vytvořeno {v['vytvoreno']}, aktualizováno {v['aktualizovano']}, "
                    f"smazáno {v['smazano']}"
                )
        except NastaveniNepripraveno as e:
            n.posledni_vysledek = f"Čeká na přístupy: {e}"
        except Exception as e:  # noqa: BLE001
            db.rollback()
            n = db.get(KonektorNastaveni, 1)
            n.posledni_vysledek = f"Chyba: {e}"
        n.posledni_beh = _ted()
        db.commit()
    finally:
        db.close()


def _mozna_obnov_watch() -> None:
    """Obnova push kanálu, jen když je automatika zapnutá. Throttluje se."""
    global _dalsi_watch_kontrola
    ted = _ted()
    if _dalsi_watch_kontrola is not None and ted < _dalsi_watch_kontrola:
        return
    _dalsi_watch_kontrola = ted + timedelta(seconds=WATCH_KONTROLA_S)

    from app.konektor.logika import obnov_watch_pokud_treba

    db = SessionLocal()
    try:
        n = db.get(KonektorNastaveni, 1)
        if n is None or not n.auto_zapnuto:
            return
        try:
            obnov_watch_pokud_treba(db)
        except NastaveniNepripraveno:
            pass
        except Exception:  # noqa: BLE001 - obnova watch nesmí shodit worker
            db.rollback()
    finally:
        db.close()


def _smycka() -> None:
    if _stop.wait(START_PRODLEVA_S):
        return
    while not _stop.is_set():
        for krok in (_tik, _mozna_reconcile, _mozna_obnov_watch):
            try:
                krok()
            except Exception:  # noqa: BLE001 - vlákno nesmí nikdy spadnout
                pass
        _stop.wait(KONTROLA_S)


def spust_worker() -> None:
    """Nastartuje worker vlákno (idempotentní)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_smycka, name="konektor-worker", daemon=True)
    _thread.start()


def zastav_worker() -> None:
    _stop.set()
