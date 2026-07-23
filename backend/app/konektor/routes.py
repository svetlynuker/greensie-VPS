"""HTTP vrstva konektoru RAYNET ↔ Google Drive.

Chráněné endpointy (jen s právem „konektor“): čtení/zápis nastavení, logy,
test spojení. Webhook endpointy jsou VEŘEJNÉ (bez JWT) – volají je Raynet a
Google, ověřují se vlastním mechanismem (sdílené tajemství / channel token).
Ve F1 webhooky payload jen bezpečně zalogují (zachycení reálného tvaru).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.database import get_db
from app.konektor import crypto, google_klient
from app.konektor.logger import zaloguj
from app.konektor.models import KonektorLog, KonektorNastaveni
from app.konektor.raynet_klient import RaynetClient
from app.konektor.schemas import (
    KonektorLogOut,
    KonektorNastaveniOut,
    KonektorNastaveniVstup,
    SluzbaStav,
    TestSpojeniVysledek,
)

router = APIRouter(prefix="/konektor", tags=["konektor"])

POVOLENE_MODELY = {"links", "mirror"}
POVOLENE_UROVNE = {"debug", "info", "warn", "error"}


def vyzaduj_pravo_konektor(user: User = Depends(get_current_user)) -> User:
    """Povolí jen ty, kdo smí otevřít dlaždici Konektor (admin ji má vždy)."""
    if not muze_otevrit(user, "konektor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na konektor nemáš oprávnění.",
        )
    return user


# ---- jednořádkové nastavení (vzor matice.ziskej_sync_nastaveni) ----
def ziskej_nastaveni(db: Session) -> KonektorNastaveni:
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        n = KonektorNastaveni(id=1)
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


def _nastaveni_out(n: KonektorNastaveni) -> KonektorNastaveniOut:
    return KonektorNastaveniOut(
        raynet_instance=n.raynet_instance,
        raynet_api_user=n.raynet_api_user,
        raynet_base_url=n.raynet_base_url,
        raynet_company_drive_field=n.raynet_company_drive_field,
        raynet_api_key_nastaven=bool(n.raynet_api_key_enc),
        google_shared_drive_id=n.google_shared_drive_id,
        google_subject_email=n.google_subject_email,
        google_sa_json_nastaven=bool(n.google_sa_json_enc),
        sync_model=n.sync_model,
        template_subfolders=n.template_subfolders,
        delete_policy=n.delete_policy,
        fr3_plne_zrcadleni=n.fr3_plne_zrcadleni,
        auto_zapnuto=n.auto_zapnuto,
        reconcile_interval_min=n.reconcile_interval_min,
        log_level=n.log_level,
        posledni_beh=n.posledni_beh,
        posledni_vysledek=n.posledni_vysledek or "",
    )


@router.get("/nastaveni", response_model=KonektorNastaveniOut)
def nacti_nastaveni(
    _user: User = Depends(vyzaduj_pravo_konektor),
    db: Session = Depends(get_db),
):
    return _nastaveni_out(ziskej_nastaveni(db))


@router.put("/nastaveni", response_model=KonektorNastaveniOut)
def uloz_nastaveni(
    vstup: KonektorNastaveniVstup,
    _user: User = Depends(vyzaduj_pravo_konektor),
    db: Session = Depends(get_db),
):
    if vstup.sync_model not in POVOLENE_MODELY:
        raise HTTPException(status_code=422, detail="Neplatný model synchronizace.")
    if vstup.log_level not in POVOLENE_UROVNE:
        raise HTTPException(status_code=422, detail="Neplatná úroveň logování.")
    if vstup.reconcile_interval_min < 5:
        raise HTTPException(status_code=422, detail="Interval musí být alespoň 5 minut.")

    # tajemství jde uložit jen s platným šifrovacím klíčem
    meni_tajemstvi = bool((vstup.raynet_api_key or "").strip()) or bool((vstup.google_sa_json or "").strip())
    if meni_tajemstvi and not crypto.klic_dostupny():
        raise HTTPException(
            status_code=500,
            detail="Chybí nebo je neplatný KONEKTOR_ENC_KEY v .env – tajemství nelze uložit.",
        )

    n = ziskej_nastaveni(db)
    n.raynet_instance = vstup.raynet_instance.strip()
    n.raynet_api_user = vstup.raynet_api_user.strip()
    n.raynet_base_url = vstup.raynet_base_url.strip()
    n.raynet_company_drive_field = vstup.raynet_company_drive_field.strip()
    n.google_shared_drive_id = vstup.google_shared_drive_id.strip()
    n.google_subject_email = vstup.google_subject_email.strip()
    n.sync_model = vstup.sync_model
    n.template_subfolders = vstup.template_subfolders.strip()
    n.delete_policy = vstup.delete_policy.strip() or "trash_reconcile"
    n.fr3_plne_zrcadleni = vstup.fr3_plne_zrcadleni
    n.auto_zapnuto = vstup.auto_zapnuto
    n.reconcile_interval_min = vstup.reconcile_interval_min
    n.log_level = vstup.log_level

    # Tajemství: None/"" = neměnit; neprázdné = zašifrovat a přepsat.
    if (vstup.raynet_api_key or "").strip():
        n.raynet_api_key_enc = crypto.sifruj(vstup.raynet_api_key.strip())
    if (vstup.google_sa_json or "").strip():
        n.google_sa_json_enc = crypto.sifruj(vstup.google_sa_json.strip())

    db.commit()
    db.refresh(n)
    return _nastaveni_out(n)


@router.get("/logy", response_model=list[KonektorLogOut])
def seznam_logu(
    _user: User = Depends(vyzaduj_pravo_konektor),
    db: Session = Depends(get_db),
    uroven: str | None = Query(None, description="filtr: debug / info / warn / error"),
    hledej: str | None = Query(None, description="hledá ve zprávě a události"),
    limit: int = Query(200, ge=1, le=2000),
) -> list[KonektorLog]:
    dotaz = db.query(KonektorLog)
    if uroven in POVOLENE_UROVNE:
        dotaz = dotaz.filter(KonektorLog.uroven == uroven)
    if hledej:
        vzor = f"%{hledej.strip()}%"
        dotaz = dotaz.filter(or_(KonektorLog.zprava.ilike(vzor), KonektorLog.udalost.ilike(vzor)))
    return dotaz.order_by(KonektorLog.cas.desc(), KonektorLog.id.desc()).limit(limit).all()


@router.delete("/logy")
def smaz_logy(
    _user: User = Depends(vyzaduj_pravo_konektor),
    db: Session = Depends(get_db),
):
    pocet = db.query(KonektorLog).delete(synchronize_session=False)
    db.commit()
    return {"smazano": pocet}


@router.post("/test-spojeni", response_model=TestSpojeniVysledek)
def test_spojeni(
    _user: User = Depends(vyzaduj_pravo_konektor),
    db: Session = Depends(get_db),
):
    """Ověří spojení s Raynetem i Google Drive dle aktuálně uložených tajemství."""
    n = ziskej_nastaveni(db)

    # Raynet
    api_key = crypto.desifruj(n.raynet_api_key_enc)
    if not api_key:
        raynet = SluzbaStav(ok=False, zprava="Raynet API klíč není nastaven.")
    else:
        klient = RaynetClient(n.raynet_instance, n.raynet_api_user, api_key, n.raynet_base_url)
        ok, zprava = klient.test_spojeni()
        raynet = SluzbaStav(ok=ok, zprava=zprava)

    # Google
    sa_json = crypto.desifruj(n.google_sa_json_enc)
    if not sa_json:
        google = SluzbaStav(ok=False, zprava="Google service-account JSON není nastaven.")
    else:
        ok, zprava = google_klient.test_spojeni(
            sa_json, n.google_shared_drive_id, n.google_subject_email or None
        )
        google = SluzbaStav(ok=ok, zprava=zprava)

    zaloguj(
        db,
        uroven="info" if (raynet.ok and google.ok) else "warn",
        udalost="test_spojeni",
        zprava=f"Test spojení – Raynet: {raynet.zprava} | Google: {google.zprava}",
        kontext={"raynet_ok": raynet.ok, "google_ok": google.ok},
    )
    return TestSpojeniVysledek(raynet=raynet, google=google)


# ---- Webhooky (VEŘEJNÉ, bez JWT) ----
async def _telo_jako_text(request: Request) -> str:
    """Vrátí tělo požadavku jako text (JSON nebo raw), bezpečně a bez pádu."""
    try:
        raw = await request.body()
    except Exception:  # noqa: BLE001
        return ""
    return raw.decode("utf-8", errors="replace")


@router.post("/webhooks/raynet")
async def webhook_raynet(request: Request, db: Session = Depends(get_db)):
    """Příjem Raynet webhooku. Ve F1 payload jen zalogujeme (zachycení tvaru)."""
    telo = await _telo_jako_text(request)
    zaloguj(
        db,
        uroven="info",
        udalost="webhook_raynet",
        zprava=f"Přijat Raynet webhook: {telo}",
        kontext={"content_type": request.headers.get("content-type")},
    )
    return {"prijato": True}


@router.post("/webhooks/drive")
async def webhook_drive(request: Request, db: Session = Depends(get_db)):
    """Příjem Google Drive push notifikace (hlavičky X-Goog-*)."""
    stav = request.headers.get("x-goog-resource-state")
    kanal = request.headers.get("x-goog-channel-id")
    zaloguj(
        db,
        uroven="info",
        udalost="webhook_drive",
        zprava=f"Přijat Google Drive push – stav={stav}, kanál={kanal}",
        kontext={
            "resource_state": stav,
            "channel_id": kanal,
            "resource_id": request.headers.get("x-goog-resource-id"),
        },
    )
    return {"prijato": True}
