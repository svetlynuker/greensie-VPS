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
    KonektorEntityFolder,
    KonektorFileMap,
    KonektorNastaveni,
    KonektorTreeMirror,
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


def _nazev(data: dict, fallback: str) -> str:
    """Čitelný název záznamu (tolerantně dle běžných polí)."""
    return (data.get("name") or data.get("companyName") or data.get("subject") or fallback).strip()


def _bezpecny_nazev(s: str) -> str:
    """Očistí název složky – Drive nemá rád lomítka."""
    return s.replace("/", "-").strip() or "beze-jmena"


def _nazev_s_cislem(data: dict, record_id: int) -> str:
    """Kombinace číslo + název pro nabídku/objednávku (dle zadavatele)."""
    cislo = (
        data.get("code")
        or data.get("number")
        or data.get("offerNumber")
        or data.get("orderNumber")
        or str(record_id)
    )
    nazev = data.get("name") or data.get("subject") or ""
    zaklad = f"{cislo} - {nazev}".strip(" -") or f"zaznam-{record_id}"
    return _bezpecny_nazev(zaklad)


def _vazba_id(data: dict, klic: str) -> int | None:
    """Vytáhne id navázaného záznamu (deal.company, offer.deal …), tolerantně."""
    rel = data.get(klic)
    if isinstance(rel, dict) and rel.get("id") is not None:
        try:
            return int(rel["id"])
        except (ValueError, TypeError):
            return None
    alt = data.get(f"{klic}Id")
    try:
        return int(alt) if alt is not None else None
    except (ValueError, TypeError):
        return None


def _slozka_pro_typ(n: KonektorNastaveni, klic: str) -> str:
    """Najde v šabloně podsložek tu pro daný typ (nabídky/objednávky)."""
    for s in _podslozky(n):
        if klic in s.lower():
            return s
    return "01_Nabídky" if klic == "nabíd" else "02_Objednávky"


def _najdi_ef(db: Session, entity: str, entity_id: int) -> KonektorEntityFolder | None:
    return (
        db.query(KonektorEntityFolder)
        .filter(KonektorEntityFolder.entity == entity, KonektorEntityFolder.entity_id == entity_id)
        .first()
    )


def _zapis_odkaz(raynet: RaynetClient, resource: str, record_id: int, kody: list[str], url: str) -> tuple[bool, str]:
    """Zapíše URL do zadaných vlastních polí. Vrací (ok, zpráva) – nekritické."""
    kody = [k for k in kody if k]
    if not kody:
        return True, "bez pole"
    try:
        raynet.set_custom_fields(resource, record_id, {k: url for k in kody})
        return True, "odkaz zapsán"
    except Exception as e:  # noqa: BLE001
        return False, f"odkaz NEzapsán: {e}"


def zajisti_slozku_zakaznika(db: Session, raynet: RaynetClient, drive: DriveClient, n: KonektorNastaveni, company_id: int) -> KonektorEntityFolder:
    """Vrátí složku zákazníka; vytvoří ji (+ zapíše odkaz), pokud chybí."""
    ef = _najdi_ef(db, "company", company_id)
    if ef is not None:
        return ef
    company = raynet.get_record("company", company_id)
    nazev = _nazev(company, f"Zákazník {company_id}")
    root = drive.create_folder(_bezpecny_nazev(f"{nazev} [{company_id}]"), n.google_shared_drive_id)
    ef = KonektorEntityFolder(
        entity="company", entity_id=company_id,
        drive_folder_id=root["id"], drive_folder_url=root.get("webViewLink", ""), name=nazev,
    )
    db.add(ef)
    db.commit()
    ok, zprava = _zapis_odkaz(raynet, "company", company_id, [n.raynet_company_drive_field], ef.drive_folder_url)
    zaloguj(db, "info" if ok else "warn", "novy_klient",
            f"Vytvořena složka zákazníka „{nazev}“; {zprava}.",
            {"company_id": company_id, "drive_folder_id": ef.drive_folder_id})
    return ef


def zajisti_slozku_op(db: Session, raynet: RaynetClient, drive: DriveClient, n: KonektorNastaveni, deal_id: int) -> KonektorEntityFolder:
    """Vrátí složku obchodního případu; vytvoří ji (+ podsložky + odkaz), pokud chybí.
    Zajistí i nadřazenou složku zákazníka."""
    ef = _najdi_ef(db, "deal", deal_id)
    if ef is not None:
        return ef
    deal = raynet.get_record("deal", deal_id)
    company_id = _vazba_id(deal, "company")
    if company_id is None:
        raise RuntimeError(f"Obchodní případ {deal_id} nemá navázanou firmu (company).")
    zak = zajisti_slozku_zakaznika(db, raynet, drive, n, company_id)

    nazev = _nazev(deal, f"Obchodní případ {deal_id}")
    op = drive.create_folder(_bezpecny_nazev(f"{nazev} [{deal_id}]"), zak.drive_folder_id)
    ef = KonektorEntityFolder(
        entity="deal", entity_id=deal_id,
        drive_folder_id=op["id"], drive_folder_url=op.get("webViewLink", ""), name=nazev,
    )
    db.add(ef)
    db.commit()
    for sub in _podslozky(n):
        drive.create_folder(sub, op["id"])
    ok, zprava = _zapis_odkaz(
        raynet, "deal", deal_id, [n.raynet_deal_drive_field, n.raynet_deal_drive_field2], ef.drive_folder_url
    )
    zaloguj(db, "info" if ok else "warn", "novy_deal",
            f"Vytvořena složka obch. případu „{nazev}“ ({len(_podslozky(n))} podsložek); {zprava}.",
            {"deal_id": deal_id, "company_id": company_id, "drive_folder_id": ef.drive_folder_id})
    return ef


def _zpracuj_zaznam_pod_op(db, n, raynet, drive, entity: str, resource: str, record_id: int, klic_typu: str, pole_kod: str) -> dict:
    """Společná logika pro nabídku/objednávku: podsložka pod OP + odkaz do pole."""
    if _najdi_ef(db, entity, record_id) is not None:
        return {"skip": True}
    zaznam = raynet.get_record(resource, record_id)
    deal_id = _vazba_id(zaznam, "deal")
    if deal_id is None:
        raise RuntimeError(f"{resource} {record_id} nemá navázaný obchodní případ (deal).")
    op = zajisti_slozku_op(db, raynet, drive, n, deal_id)

    typ_nazev = _slozka_pro_typ(n, klic_typu)
    typ_slozka = drive.find_folder(typ_nazev, op.drive_folder_id) or drive.create_folder(typ_nazev, op.drive_folder_id)
    nazev = _nazev_s_cislem(zaznam, record_id)
    podslozka = drive.create_folder(nazev, typ_slozka["id"])
    ef = KonektorEntityFolder(
        entity=entity, entity_id=record_id,
        drive_folder_id=podslozka["id"], drive_folder_url=podslozka.get("webViewLink", ""), name=nazev,
    )
    db.add(ef)
    db.commit()
    ok, zprava = _zapis_odkaz(raynet, resource, record_id, [pole_kod], ef.drive_folder_url)
    zaloguj(db, "info" if ok else "warn", f"novy_{entity}",
            f"Vytvořena složka „{nazev}“ v {typ_nazev}; {zprava}.",
            {f"{entity}_id": record_id, "deal_id": deal_id, "drive_folder_id": ef.drive_folder_id})
    return {"drive_folder_id": ef.drive_folder_id, "drive_folder_url": ef.drive_folder_url, "odkaz_ok": ok}


def zpracuj_novy_klient(db: Session, company_id: int) -> dict:
    """Flow A – vznik zákazníka → složka zákazníka (bez podsložek; ty jsou pod OP)."""
    if _najdi_ef(db, "company", company_id) is not None:
        return {"skip": True}
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    ef = zajisti_slozku_zakaznika(db, raynet, drive, n, company_id)
    return {"drive_folder_id": ef.drive_folder_id, "drive_folder_url": ef.drive_folder_url}


def zpracuj_novy_deal(db: Session, deal_id: int) -> dict:
    """Vznik obchodního případu → složka OP + 4 podsložky (+ složka zákazníka)."""
    if _najdi_ef(db, "deal", deal_id) is not None:
        return {"skip": True}
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    ef = zajisti_slozku_op(db, raynet, drive, n, deal_id)
    return {"drive_folder_id": ef.drive_folder_id, "drive_folder_url": ef.drive_folder_url}


def zpracuj_nova_nabidka(db: Session, offer_id: int) -> dict:
    """Vznik nabídky → podsložka v 01_Nabídky pod OP + odkaz do pole nabídky."""
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    return _zpracuj_zaznam_pod_op(db, n, raynet, drive, "offer", "offer", offer_id, "nabíd", n.raynet_offer_drive_field)


def zpracuj_nova_objednavka(db: Session, order_id: int) -> dict:
    """Vznik objednávky → podsložka v 02_Objednávky pod OP + odkaz do pole objednávky."""
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    return _zpracuj_zaznam_pod_op(db, n, raynet, drive, "order", "order", order_id, "objedn", n.raynet_order_drive_field)


# =================== Flow B: Disk → Raynet (FR2a) ===================
def _resolve_deal(drive: DriveClient, file: dict, root_index: dict, cache: dict) -> int | None:
    """Zjistí, kterému obchodnímu případu soubor patří – jde přes rodiče až ke
    složce obch. případu (drive_folder_id dealu v entity_folder). None = mimo."""
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

    # kotvy = složky obchodních případů; soubor v podsložce se přiřadí svému dealu
    mapy = (
        db.query(KonektorEntityFolder).filter(KonektorEntityFolder.entity == "deal").all()
    )
    root_index = {m.drive_folder_id: m.entity_id for m in mapy}
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

        deal_id = _resolve_deal(drive, file, root_index, cache)
        if deal_id is None:
            continue  # soubor mimo složky obchodních případů

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

        doc_id = raynet.create_link_document(name, url, deal_id=deal_id)
        if fm is None:
            fm = KonektorFileMap(drive_file_id=file["id"])
            db.add(fm)
        # do raynet_company_id ukládáme id obch. případu (evidence navázání)
        fm.raynet_company_id = deal_id
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


# =================== Flow C: zrcadlení stromu (FR3) ===================
def _zajisti_mirror_slozku(
    db: Session, raynet: RaynetClient, drive_id: str, name: str, raynet_parent: str | None
) -> str:
    """Vrátí raynet_id zrcadlené složky; vytvoří ji, pokud ještě neexistuje."""
    m = db.get(KonektorTreeMirror, drive_id)
    if m is not None:
        return m.raynet_id
    rid = str(raynet.create_document_folder(name, raynet_parent))
    db.add(KonektorTreeMirror(drive_id=drive_id, raynet_id=rid, je_slozka=True))
    db.commit()
    return rid


def zrcadli_strom(db: Session) -> dict:
    """Zrcadlí strom Shared Drive do modulu Dokumenty v Raynetu (FR3).

    Složky → složky, soubory → odkazové dokumenty. Idempotentní přes
    tree_mirror (opakované spuštění jen doplní nové položky). Full walk se
    spouští na vyžádání; inkrementální údržba je zjednodušená (znovu-spuštění).
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)

    root_drive = n.google_shared_drive_id
    root_raynet = _zajisti_mirror_slozku(db, raynet, root_drive, "Google Disk", None)

    vytvoreno_slozek = vytvoreno_souboru = 0
    fronta = [(root_drive, root_raynet)]
    navstivene: set[str] = set()

    while fronta:
        drive_folder_id, raynet_parent = fronta.pop()
        if drive_folder_id in navstivene:
            continue
        navstivene.add(drive_folder_id)

        for child in drive.list_children(drive_folder_id):
            cid = child["id"]
            existuje = db.get(KonektorTreeMirror, cid)
            if child.get("mimeType") == FOLDER_MIME:
                if existuje is None:
                    rid = str(raynet.create_document_folder(child.get("name", ""), raynet_parent))
                    db.add(KonektorTreeMirror(drive_id=cid, raynet_id=rid, je_slozka=True))
                    db.commit()
                    vytvoreno_slozek += 1
                else:
                    rid = existuje.raynet_id
                fronta.append((cid, rid))
            else:
                if existuje is not None:
                    continue
                did = str(
                    raynet.create_link_document_in_folder(
                        child.get("name", ""), child.get("webViewLink", ""), raynet_parent
                    )
                )
                db.add(KonektorTreeMirror(drive_id=cid, raynet_id=did, je_slozka=False))
                db.commit()
                vytvoreno_souboru += 1

    zaloguj(
        db, "info", "zrcadleni",
        f"Zrcadlení stromu hotovo – nových složek {vytvoreno_slozek}, souborů {vytvoreno_souboru}.",
        {"slozek": vytvoreno_slozek, "souboru": vytvoreno_souboru},
    )
    return {"slozek": vytvoreno_slozek, "souboru": vytvoreno_souboru}


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
