"""Plánovač automatické synchronizace z Freela.

Jedno vlákno na pozadí, které se probouzí každou minutu a když je automatika
zapnutá a od posledního běhu uplynul nastavený interval, stáhne data z Freela
do matice podle voleb v `nastaveni_synchronizace`.

Předpoklad: backend běží v jednom procesu (uvicorn bez workerů navíc) → běží
jen jeden plánovač. Chyby se zapisují do `posledni_vysledek`, nikdy neshodí app.
"""

import threading
from datetime import datetime, timedelta

from app.database import SessionLocal

# jak často vlákno kontroluje, zda je čas synchronizovat (ne interval samotné synchronizace)
KONTROLA_S = 60
# krátká prodleva po startu, ať se stihne nastartovat zbytek backendu
START_PRODLEVA_S = 30

_stop = threading.Event()
_thread: threading.Thread | None = None


def _mozna_synchronizuj() -> None:
    # importy uvnitř kvůli cyklu (routes.py importuje modely, my importujeme routes)
    from app.matice.routes import proved_synchronizaci, ziskej_sync_nastaveni

    db = SessionLocal()
    try:
        n = ziskej_sync_nastaveni(db)
        if not n.auto_zapnuto:
            return

        ted = datetime.utcnow()
        if n.posledni_beh is not None:
            dalsi_beh = n.posledni_beh + timedelta(minutes=max(5, n.interval_min))
            if ted < dalsi_beh:
                return  # ještě není čas

        try:
            vysledek = proved_synchronizaci(
                db,
                nove_projekty=n.sync_nove_projekty,
                nove_ukoly=n.sync_nove_ukoly,
                prepis_stav=n.sync_stav,
                prepis_terminy=n.sync_terminy,
                prepis_osoby=n.sync_osoby,
            )
            n.posledni_vysledek = (
                f"OK – projektů {vysledek.projektu}, nových sloupců {vysledek.sloupcu}, "
                f"nových buněk {vysledek.bunek_novych}, přepsaných {vysledek.bunek_prepsanych}"
            )
        except Exception as e:  # noqa: BLE001 - chybu jen zaznamenáme, app nerušíme
            db.rollback()
            n = ziskej_sync_nastaveni(db)
            n.posledni_vysledek = f"Chyba: {e}"

        n.posledni_beh = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def _smycka() -> None:
    if _stop.wait(START_PRODLEVA_S):
        return
    while not _stop.is_set():
        try:
            _mozna_synchronizuj()
        except Exception:  # noqa: BLE001 - vlákno nesmí nikdy spadnout
            pass
        _stop.wait(KONTROLA_S)


def spust_planovac() -> None:
    """Nastartuje vlákno plánovače (idempotentní)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_smycka, name="freelo-sync", daemon=True)
    _thread.start()


def zastav_planovac() -> None:
    _stop.set()
