"""Byznys logika konektoru – Flow A (FR1): nový klient → struktura složek.

Sestaví klienty z uloženého (dešifrovaného) nastavení, vytvoří na Disku
kořenovou složku klienta s podsložkami dle šablony, uloží mapování a zapíše
odkaz zpět do vlastního pole company v Raynetu.

Idempotence: pokud už mapování pro company existuje, složky se znovu netvoří.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.konektor import crypto
from app.konektor.google_klient import FOLDER_MIME, DriveClient
from app.konektor.logger import zaloguj
from app.konektor.models import (
    KonektorClientFolderMap,
    KonektorDriveChangeState,
    KonektorDriveChannel,
    KonektorFileMap,
    KonektorNastaveni,
)
from app.konektor.raynet_klient import RaynetClient


class NastaveniNepripraveno(RuntimeError):
    """Chybí přístupy/konfigurace nutná pro běh synchronizace."""


def _podslozky(n: KonektorNastaveni) -> list[str]:
    return [s.strip() for s in (n.template_subfolders or "").split(",") if s.strip()]


def vytvor_klienty(n: KonektorNastaveni) -> tuple[RaynetClient, DriveClient]:
    """Sestaví Raynet i Drive klienta z nastavení, nebo vyhodí NastaveniNepripraveno."""
    api_key = crypto.desifruj(n.raynet_api_key_enc)
    sa_json = crypto.desifruj(n.google_sa_json_enc)
    chybi = []
    if not (n.raynet_instance and n.raynet_api_user and api_key):
        chybi.append("Raynet přístup")
    if not sa_json:
        chybi.append("Google service-account JSON")
    if not n.google_shared_drive_id:
        chybi.append("ID Shared Drive")
    if chybi:
        raise NastaveniNepripraveno("Chybí: " + ", ".join(chybi))

    raynet = RaynetClient(n.raynet_instance, n.raynet_api_user, api_key, n.raynet_base_url)
    drive = DriveClient(sa_json, n.google_subject_email or None)
    return raynet, drive


def _nazev_klienta(data: dict, company_id: int) -> str:
    # TO VERIFY přesný název pole v detailu company; bereme tolerantně.
    return (data.get("name") or data.get("companyName") or f"Company {company_id}").strip()


def zpracuj_novy_klient(db: Session, company_id: int) -> dict:
    """Vytvoří složku klienta + podsložky a zapíše odkaz do Raynetu.

    Vrací slovník s výsledkem. Idempotentní: existující mapování nepřetváří.
    Případné chyby probublají volajícímu (worker je zaloguje a zkusí znovu).
    """
    existujici = db.get(KonektorClientFolderMap, company_id)
    if existujici is not None:
        zaloguj(
            db, "info", "novy_klient",
            f"Klient {company_id} už má složku – přeskočeno.",
            {"company_id": company_id, "drive_folder_id": existujici.drive_folder_id},
        )
        return {"skip": True, "drive_folder_id": existujici.drive_folder_id}

    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)

    company = raynet.get_company(company_id)
    nazev = _nazev_klienta(company, company_id)

    # kořenová složka klienta ve Shared Drive
    root = drive.create_folder(f"{nazev} [{company_id}]", n.google_shared_drive_id)
    root_id = root["id"]
    root_url = root.get("webViewLink", "")

    for sub in _podslozky(n):
        drive.create_folder(sub, root_id)

    mapping = KonektorClientFolderMap(
        raynet_company_id=company_id,
        drive_folder_id=root_id,
        drive_folder_url=root_url,
        client_name=nazev,
    )
    db.add(mapping)
    db.commit()

    # zpětný odkaz do vlastního pole company (nekritické – když selže, zalogujeme)
    odkaz_ok = True
    odkaz_zprava = "odkaz zapsán"
    try:
        raynet.set_company_drive_field(company_id, n.raynet_company_drive_field, root_url)
    except Exception as e:  # noqa: BLE001
        odkaz_ok = False
        odkaz_zprava = f"odkaz NEzapsán: {e}"

    zaloguj(
        db,
        "info" if odkaz_ok else "warn",
        "novy_klient",
        f"Vytvořena složka klienta „{nazev}“ ({len(_podslozky(n))} podsložek); {odkaz_zprava}.",
        {"company_id": company_id, "drive_folder_id": root_id, "odkaz_ok": odkaz_ok},
    )
    return {"drive_folder_id": root_id, "drive_folder_url": root_url, "odkaz_ok": odkaz_ok}


# =================== Flow B: Disk → Raynet (FR2a) ===================
def _resolve_company(drive: DriveClient, file: dict, root_index: dict, cache: dict) -> int | None:
    """Zjistí, kterému klientovi soubor patří – jde přes rodiče až ke kořenové
    složce klienta (drive_folder_id v client_folder_map). None = mimo klienty."""
    to_visit = list(file.get("parents") or [])
    seen: set[str] = set()
    depth = 0
    while to_visit and depth < 30:
        depth += 1
        pid = to_visit.pop(0)
        if pid in root_index:
            return root_index[pid]
        if pid in cache:
            if cache[pid] is not None:
                return cache[pid]
            continue
        if pid in seen:
            continue
        seen.add(pid)
        try:
            rodic = drive.get_file(pid)
        except Exception:  # noqa: BLE001 - nedostupný rodič nezastaví ostatní
            cache[pid] = None
            continue
        cache[pid] = None
        to_visit.extend(rodic.get("parents") or [])
    return None


def zpracuj_drive_zmeny(db: Session) -> dict:
    """Načte změny ze Shared Drive a promítne je do Raynetu jako odkazové dokumenty.

    Model odkazů (D1): Disk je zdroj obsahu, Raynet drží jen odkaz. Složky a
    vlastní zápisy konektoru (appProperties.origin=='raynet') se přeskakují.
    Idempotence: stav sledujeme přes uložený page token; už namapované soubory
    se znovu nevytvářejí.
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)

    stav = db.get(KonektorDriveChangeState, 1)
    if stav is None:
        stav = KonektorDriveChangeState(id=1, page_token="")
        db.add(stav)
        db.commit()

    if not stav.page_token:
        # první spuštění: začneme sledovat od teď (nevytváříme odkazy zpětně –
        # historii řeší volitelná migrace F7)
        stav.page_token = drive.get_start_page_token(n.google_shared_drive_id)
        db.commit()
        zaloguj(db, "info", "reconcile", "Sledování změn Disku inicializováno (od teď).",
                {"page_token_set": True})
        return {"inicializace": True, "vytvoreno": 0, "smazano": 0, "aktualizovano": 0}

    zmeny, novy_token = drive.list_changes(stav.page_token, n.google_shared_drive_id)

    mapy = db.query(KonektorClientFolderMap).all()
    root_index = {m.drive_folder_id: m.raynet_company_id for m in mapy}
    cache: dict = {}

    vytvoreno = smazano = aktualizovano = 0

    for ch in zmeny:
        file = ch.get("file")
        file_id = ch.get("fileId")

        # smazání / přesun do koše → odeber odkaz v Raynetu
        if ch.get("removed") or (file and file.get("trashed")):
            fm = db.query(KonektorFileMap).filter(KonektorFileMap.drive_file_id == file_id).first()
            if fm and fm.state != "trashed":
                if fm.raynet_document_id:
                    try:
                        raynet.delete_document(fm.raynet_document_id)
                    except Exception as e:  # noqa: BLE001
                        zaloguj(db, "warn", "sync_smazani",
                                f"Odkaz v Raynetu se nepodařilo smazat: {e}", {"drive_file_id": file_id})
                fm.state = "trashed"
                db.commit()
                smazano += 1
            continue

        if not file or file.get("mimeType") == FOLDER_MIME:
            continue  # složky řeší až FR3 (zrcadlení stromu)
        if (file.get("appProperties") or {}).get("origin") == "raynet":
            continue  # echo suppression – náš vlastní zápis

        company_id = _resolve_company(drive, file, root_index, cache)
        if company_id is None:
            continue  # soubor mimo klientské složky

        url = file.get("webViewLink", "")
        name = file.get("name", "")
        fm = db.query(KonektorFileMap).filter(KonektorFileMap.drive_file_id == file["id"]).first()

        if fm and fm.raynet_document_id and fm.state == "active":
            # už namapováno – jen osvěžíme metadata (odkaz se nemění)
            fm.drive_file_url = url
            fm.file_name = name
            fm.last_synced_source = "drive"
            db.commit()
            aktualizovano += 1
            continue

        doc_id = raynet.create_link_document(company_id, name, url)
        if fm is None:
            fm = KonektorFileMap(drive_file_id=file["id"])
            db.add(fm)
        fm.raynet_company_id = company_id
        fm.raynet_document_id = str(doc_id)
        fm.drive_file_url = url
        fm.file_name = name
        fm.last_synced_source = "drive"
        fm.state = "active"
        db.commit()
        vytvoreno += 1

    stav.page_token = novy_token
    db.commit()

    zaloguj(
        db, "info", "reconcile",
        f"Změny Disku zpracovány – vytvořeno {vytvoreno}, aktualizováno {aktualizovano}, smazáno {smazano}.",
        {"vytvoreno": vytvoreno, "aktualizovano": aktualizovano, "smazano": smazano, "zmen": len(zmeny)},
    )
    return {"vytvoreno": vytvoreno, "aktualizovano": aktualizovano, "smazano": smazano, "zmen": len(zmeny)}


# =================== Flow B: Raynet → Disk (FR2b) ===================
def zpracuj_raynet_dokument(db: Session, document_id: str, company_id: int | None = None) -> dict:
    """Stáhne dokument nahraný v Raynetu a nahraje ho do složky klienta na Disku.

    Echo suppression: dokumenty, které konektor sám vytvořil (jsou ve file_map
    jako raynet_document_id), se přeskočí – jinak by vznikla smyčka s Flow B
    (Disk→Raynet). Na Disk se soubor značí appProperties.origin='raynet'.

    TO VERIFY: tvar detailu dokumentu (name, company, fileId) a endpoint stažení
    obsahu – parser je tolerantní, doladí se po ověření reálným voláním.
    """
    # náš vlastní odkazový dokument? → nestahovat zpět (echo suppression)
    nas = (
        db.query(KonektorFileMap)
        .filter(KonektorFileMap.raynet_document_id == str(document_id))
        .first()
    )
    if nas is not None:
        zaloguj(db, "info", "raynet_dokument",
                f"Dokument {document_id} pochází od konektoru – přeskočeno.", {"document_id": document_id})
        return {"skip": True}

    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)

    doc = raynet.get_document(document_id)
    name = doc.get("name") or doc.get("fileName") or f"dokument-{document_id}"
    cid = company_id
    if cid is None:
        rel = doc.get("company")
        if isinstance(rel, dict):
            cid = rel.get("id")
        cid = cid or doc.get("companyId")
    if cid is None:
        zaloguj(db, "warn", "raynet_dokument",
                f"Dokument {document_id} nemá určenou company – přeskočeno.", {"document_id": document_id})
        return {"skip": True, "duvod": "bez company"}

    mapping = db.get(KonektorClientFolderMap, int(cid))
    if mapping is None:
        zaloguj(db, "warn", "raynet_dokument",
                f"Klient {cid} nemá složku na Disku – dokument {document_id} přeskočen.",
                {"document_id": document_id, "company_id": cid})
        return {"skip": True, "duvod": "klient bez složky"}

    file_id = doc.get("fileId") or document_id
    data = raynet.download_document_body(str(file_id))
    nahrany = drive.upload_file(
        name, mapping.drive_folder_id, data, app_properties={"origin": "raynet"}
    )

    fm = KonektorFileMap(
        drive_file_id=nahrany["id"],
        raynet_company_id=int(cid),
        raynet_document_id=str(document_id),
        drive_file_url=nahrany.get("webViewLink", ""),
        file_name=name,
        last_synced_source="raynet",
        state="active",
    )
    db.add(fm)
    db.commit()
    zaloguj(db, "info", "raynet_dokument",
            f"Dokument „{name}“ z Raynetu nahrán do složky klienta {cid}.",
            {"document_id": document_id, "company_id": cid, "drive_file_id": nahrany["id"]})
    return {"drive_file_id": nahrany["id"], "drive_file_url": nahrany.get("webViewLink", "")}


# =================== Google Drive push (watch) ===================
def webhook_token() -> str:
    """Token, kterým Google značí push notifikace (X-Goog-Channel-Token)."""
    return os.environ.get("KONEKTOR_WEBHOOK_SECRET", "")


def public_base_url() -> str:
    """Veřejná základní URL appky (pro adresu push endpointu)."""
    return (
        os.environ.get("PUBLIC_BASE_URL")
        or os.environ.get("APP_URL")
        or "https://167-235-254-188.sslip.io"
    ).rstrip("/")


def drive_webhook_address() -> str:
    return f"{public_base_url()}/api/konektor/webhooks/drive"


def _ms_na_datetime(ms) -> datetime:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (ValueError, TypeError):
        return datetime.now(timezone.utc) + timedelta(days=7)


def registruj_watch(db: Session) -> dict:
    """Zaregistruje Google Drive push kanál na náš webhook. Vrací info o kanálu."""
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    _, drive = vytvor_klienty(n)

    stav = db.get(KonektorDriveChangeState, 1)
    if stav is None:
        stav = KonektorDriveChangeState(id=1, page_token="")
        db.add(stav)
        db.commit()
    if not stav.page_token:
        stav.page_token = drive.get_start_page_token(n.google_shared_drive_id)
        db.commit()

    channel_id = "konektor-" + secrets.token_hex(8)
    resp = drive.watch_changes(
        stav.page_token, n.google_shared_drive_id, channel_id, drive_webhook_address(), webhook_token()
    )
    kanal = KonektorDriveChannel(
        channel_id=channel_id,
        resource_id=resp.get("resourceId", ""),
        expiration=_ms_na_datetime(resp.get("expiration")),
        page_token=stav.page_token,
    )
    db.add(kanal)
    db.commit()
    zaloguj(db, "info", "watch", f"Zaregistrován push kanál {channel_id}.",
            {"channel_id": channel_id, "expiration": kanal.expiration.isoformat()})
    return {"channel_id": channel_id, "expiration": kanal.expiration.isoformat()}


def zrus_watch(db: Session) -> dict:
    """Zastaví a smaže všechny push kanály."""
    n = db.get(KonektorNastaveni, 1)
    kanaly = db.query(KonektorDriveChannel).all()
    if kanaly and n is not None:
        try:
            _, drive = vytvor_klienty(n)
            for ch in kanaly:
                try:
                    drive.stop_channel(ch.channel_id, ch.resource_id)
                except Exception:  # noqa: BLE001 - kanál mohl už expirovat
                    pass
        except NastaveniNepripraveno:
            pass
    pocet = len(kanaly)
    for ch in kanaly:
        db.delete(ch)
    db.commit()
    zaloguj(db, "info", "watch", f"Zrušeno push kanálů: {pocet}.", {"zruseno": pocet})
    return {"zruseno": pocet}


def obnov_watch_pokud_treba(db: Session) -> dict:
    """Obnoví push kanál, pokud žádný není nebo nejnovější brzy expiruje.

    Volá se z workeru jen když je automatika zapnutá.
    """
    ted = datetime.now(timezone.utc)
    nejnovejsi = (
        db.query(KonektorDriveChannel).order_by(KonektorDriveChannel.expiration.desc()).first()
    )
    if nejnovejsi is not None and nejnovejsi.expiration > ted + timedelta(hours=24):
        return {"obnoveno": False}
    zrus_watch(db)
    registruj_watch(db)
    return {"obnoveno": True}


def stav_watch(db: Session) -> dict:
    """Informace o aktuálním push kanálu pro UI."""
    nejnovejsi = (
        db.query(KonektorDriveChannel).order_by(KonektorDriveChannel.expiration.desc()).first()
    )
    if nejnovejsi is None:
        return {"aktivni": False, "expiration": None}
    return {"aktivni": True, "channel_id": nejnovejsi.channel_id, "expiration": nejnovejsi.expiration.isoformat()}
