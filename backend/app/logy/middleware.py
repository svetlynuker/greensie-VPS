"""Odposlech (middleware), který zaznamená každý požadavek na backend.

Pro každý požadavek zapíše jeden řádek do tabulky `logy`: kdo (z tokenu),
co volal (metoda + cesta), jak to dopadlo (stavový kód), jak dlouho to
trvalo a jestli nastala chyba. Tím jsou pokryté „provoz serveru“ i „chyby“
naráz; změnové akce (POST/PUT/DELETE) se značí jako „audit“.

Zásady:
- Logování NIKDY neshodí požadavek – veškerý zápis je obalený try/except.
- Zápis do databáze běží ve vlákně (run_in_threadpool), aby neblokoval server.
- Některé cesty se nelogují (viz NELOGOVAT), ať se přehled nezaplevelí sám sebou.
"""

import re
import time
import traceback

from jose import jwt
from starlette.background import BackgroundTask, BackgroundTasks
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth.models import User
from app.auth.permissions import ALGORITHM, SECRET_KEY
from app.database import SessionLocal
from app.logy.models import vytvor_zaznam

# Cesty, které se NElogují: preflight (OPTIONS) řeší metoda níže; zdravotní
# kontrola, čtení samotných logů (jinak by se log donekonečna plevelil při
# obnovování stránky) a přihlášení (to si zapisuje samo, i se jménem).
NELOGOVAT_PREFIXY = ("/logy", "/health", "/konektor/logy")
NELOGOVAT_PRESNE = {"/auth/login"}

# Čitelné popisy vybraných akcí. Klíč = (metoda, regulární výraz na cestu).
# Když nic nesedí, popis zůstane prázdný a v přehledu se ukáže metoda + cesta.
_POPISY = [
    ("PUT", re.compile(r"^/auth/heslo$"), "Změna vlastního hesla"),
    ("PUT", re.compile(r"^/matice/bunka$"), "Editace buňky matice"),
    ("POST", re.compile(r"^/matice/projekt$"), "Přidání projektu"),
    ("PUT", re.compile(r"^/matice/projekt/\d+/zobrazeni$"), "Změna zobrazení projektu"),
    ("POST", re.compile(r"^/matice/sloupec$"), "Přidání úkolu (sloupce)"),
    ("PUT", re.compile(r"^/matice/barvy$"), "Změna nastavení barev"),
    ("PUT", re.compile(r"^/matice/sync-nastaveni$"), "Změna nastavení synchronizace"),
    ("POST", re.compile(r"^/matice/freelo/nacist$"), "Načtení dat z Freela"),
    ("POST", re.compile(r"^/admin/uzivatele$"), "Přidání uživatele"),
    ("PUT", re.compile(r"^/admin/uzivatele/\d+$"), "Úprava uživatele"),
    ("DELETE", re.compile(r"^/admin/uzivatele/\d+$"), "Smazání uživatele"),
    ("POST", re.compile(r"^/admin/uzivatele/\d+/reset-hesla$"), "Reset hesla uživatele"),
    ("POST", re.compile(r"^/admin/skupiny$"), "Přidání skupiny"),
    ("PUT", re.compile(r"^/admin/skupiny/\d+$"), "Úprava skupiny"),
    ("DELETE", re.compile(r"^/admin/skupiny/\d+$"), "Smazání skupiny"),
    ("POST", re.compile(r"^/finance/pohoda/synchronizovat$"), "Synchronizace s POHODA"),
    ("POST", re.compile(r"^/nabidkovac/nabidky$"), "Založení nabídky"),
    ("DELETE", re.compile(r"^/nabidkovac/nabidky/\d+$"), "Smazání nabídky"),
    ("PUT", re.compile(r"^/konektor/nastaveni$"), "Změna nastavení konektoru"),
    ("POST", re.compile(r"^/konektor/test-spojeni$"), "Test spojení konektoru"),
    ("POST", re.compile(r"^/konektor/webhooks/raynet$"), "Webhook z Raynetu"),
    ("POST", re.compile(r"^/konektor/webhooks/drive$"), "Google Drive push"),
]


def _popis_akce(metoda: str, cesta: str) -> str | None:
    for m, vzor, popis in _POPISY:
        if m == metoda and vzor.match(cesta):
            return popis
    return None


def _uzivatel_z_tokenu(auth_hlavicka: str | None) -> int | None:
    """Vytáhne id uživatele z Bearer tokenu; při jakémkoli problému vrátí None."""
    if not auth_hlavicka or not auth_hlavicka.lower().startswith("bearer "):
        return None
    token = auth_hlavicka[7:].strip()
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub is not None else None
    except Exception:  # noqa: BLE001 - neplatný/prošlý token = prostě neznámý uživatel
        return None


def _zapis_log(**pole) -> None:
    """Uloží řádek do DB. Doplní e-mail uživatele a chybu potichu spolkne."""
    db = SessionLocal()
    try:
        uzivatel_id = pole.get("uzivatel_id")
        if uzivatel_id is not None:
            u = db.get(User, uzivatel_id)
            pole["uzivatel_email"] = u.email if u is not None else None
        db.add(vytvor_zaznam(**pole))
        db.commit()
    except Exception:  # noqa: BLE001 - logování nesmí shodit request
        db.rollback()
    finally:
        db.close()


class LogovaciMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cesta = request.url.path
        # co nelogujeme, jen propustíme dál
        if (
            request.method == "OPTIONS"
            or cesta in NELOGOVAT_PRESNE
            or any(cesta.startswith(p) for p in NELOGOVAT_PREFIXY)
        ):
            return await call_next(request)

        uzivatel_id = _uzivatel_z_tokenu(request.headers.get("authorization"))
        # Za reverzní proxy (Caddy) je skutečná IP klienta POSLEDNÍ prvek
        # X-Forwarded-For – ten přidává proxy. Dřívější prvky si může klient
        # podvrhnout, proto bereme ten poslední, ne první.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ip = xff.split(",")[-1].strip()
        else:
            ip = request.client.host if request.client else None
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            # neošetřená výjimka = pád serveru (500) → zaznamenáme s detailem a pošleme dál
            doba_ms = int((time.perf_counter() - start) * 1000)
            try:
                await run_in_threadpool(
                    _zapis_log,
                    uzivatel_id=uzivatel_id,
                    metoda=request.method,
                    cesta=cesta,
                    status_kod=500,
                    doba_ms=doba_ms,
                    typ="chyba",
                    popis=_popis_akce(request.method, cesta),
                    detail=traceback.format_exc(),
                    ip=ip,
                )
            except Exception:  # noqa: BLE001 - ani chyba logu nesmí přebít původní chybu
                pass
            raise

        doba_ms = int((time.perf_counter() - start) * 1000)
        status_kod = response.status_code
        if status_kod >= 500:
            typ = "chyba"
        elif request.method in ("POST", "PUT", "PATCH", "DELETE"):
            typ = "audit"  # změnová akce = „kdo co udělal“
        else:
            typ = "provoz"  # čtení (GET/HEAD)

        # Zápis logu odložíme jako background úlohu, která proběhne AŽ PO
        # odeslání odpovědi. Tou dobou je DB spojení požadavku už uvolněné,
        # takže si zápis nedrží druhé spojení z poolu souběžně (jinak by za
        # zátěže hrozilo vyčerpání poolu). Sync funkci spustí Starlette ve vlákně.
        ukol = BackgroundTask(
            _zapis_log,
            uzivatel_id=uzivatel_id,
            metoda=request.method,
            cesta=cesta,
            status_kod=status_kod,
            doba_ms=doba_ms,
            typ=typ,
            popis=_popis_akce(request.method, cesta),
            ip=ip,
        )
        if response.background is None:
            response.background = ukol
        else:
            # zachovat případnou existující background úlohu endpointu
            spojene = BackgroundTasks()
            spojene.tasks.append(response.background)
            spojene.tasks.append(ukol)
            response.background = spojene

        return response
