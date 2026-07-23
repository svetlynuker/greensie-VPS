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
    VYCHOZI_KONTEJNER_NABIDKY,
    VYCHOZI_KONTEJNER_OBJEDNAVKY,
    VYCHOZI_KONTEJNER_OP,
    KonektorClientFolderMap,
    KonektorDriveChangeState,
    KonektorDriveChannel,
    KonektorEntityFolder,
    KonektorFileMap,
    KonektorJobQueue,
    KonektorNastaveni,
    KonektorTreeMirror,
)
from app.konektor.raynet_klient import RaynetClient, dms_bezpecny_nazev

# entita → (Raynet resource, typ úlohy, klíč id v payloadu) pro hromadný import
_IMPORT_PLAN = (
    ("company", "novy_klient", "company_id"),
    ("deal", "novy_deal", "deal_id"),
    ("offer", "nova_nabidka", "offer_id"),
    ("order", "nova_objednavka", "order_id"),
)


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


def _kfg_kontejnery(n: KonektorNastaveni) -> tuple[str, str, str]:
    """Názvy kontejnerů (OP, nabídky, objednávky) – s fallbackem na výchozí."""
    return (
        (n.kontejner_op or VYCHOZI_KONTEJNER_OP).strip(),
        (n.kontejner_nabidky or VYCHOZI_KONTEJNER_NABIDKY).strip(),
        (n.kontejner_objednavky or VYCHOZI_KONTEJNER_OBJEDNAVKY).strip(),
    )


def _najdi_podslozku(drive: DriveClient, parent_id: str, nazev: str) -> dict | None:
    """Najde podsložku daného názvu (case-insensitive, ořezané mezery)."""
    cil = (nazev or "").strip().lower()
    for f in drive.list_children(parent_id):
        if f.get("mimeType") == FOLDER_MIME and (f.get("name") or "").strip().lower() == cil:
            return f
    return None


def _jedina_podslozka(drive: DriveClient, parent_id: str) -> dict | None:
    """Vzor uvnitř kontejneru = jeho (první) podsložka, nebo None když žádná není."""
    slozky = [f for f in drive.list_children(parent_id) if f.get("mimeType") == FOLDER_MIME]
    slozky.sort(key=lambda x: x.get("name", ""))
    return slozky[0] if slozky else None


def _kontejner_ze_slozky(drive: DriveClient, ef: KonektorEntityFolder, klic: str, nazev: str) -> str | None:
    """ID kontejneru uvnitř složky `ef` – přednostně z uloženého ID (ověří, že
    existuje a není v koši), jinak dohledá podle názvu. Tím je odolný vůči
    přejmenování kontejneru lidmi v konkrétní klientské složce."""
    ulozene = (ef.kontejnery or {}).get(klic) if ef.kontejnery else None
    if ulozene:
        try:
            f = drive.get_file(ulozene)
            if not f.get("trashed"):
                return ulozene
        except Exception:  # noqa: BLE001 - přejmenování řeší fallback níže
            pass
    nalez = _najdi_podslozku(drive, ef.drive_folder_id, nazev)
    return nalez["id"] if nalez else None


def _vzor_op(drive: DriveClient, n: KonektorNastaveni) -> dict | None:
    """Vzorová složka OP v globálním „0. vzor“ (jediná podsložka kontejneru OP)."""
    kop, _, _ = _kfg_kontejnery(n)
    kont = _najdi_podslozku(drive, n.google_vzor_folder_id, kop)
    return _jedina_podslozka(drive, kont["id"]) if kont else None


def _vzor_polozky(drive: DriveClient, n: KonektorNastaveni, klic: str) -> dict | None:
    """Vzor nabídky/objednávky v globálním vzoru: 0.vzor → kont.OP → vzor OP →
    kont.nabídek/objednávek → jeho jediná podsložka. None = bez vzoru (prostá složka)."""
    vzor_op = _vzor_op(drive, n)
    if vzor_op is None:
        return None
    _, knab, kobj = _kfg_kontejnery(n)
    nazev_kont = knab if klic == "nabidky" else kobj
    kont = _najdi_podslozku(drive, vzor_op["id"], nazev_kont)
    return _jedina_podslozka(drive, kont["id"]) if kont else None


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
    """Vrátí složku zákazníka; vytvoří ji (+ zapíše odkaz), pokud chybí.

    Je-li nastaven vzor („0. vzor“), zkopíruje se celá jeho struktura a kořen
    se přejmenuje na „název [id]“. Vzorová složka OP se do kopie NEzahrne
    (kontejner OP zůstane prázdný, vzor se bere centrálně z „0. vzor“).
    """
    ef = _najdi_ef(db, "company", company_id)
    if ef is not None:
        return ef
    company = raynet.get_record("company", company_id)
    nazev = _nazev(company, f"Zákazník {company_id}")
    parent = n.google_root_folder_id or n.google_shared_drive_id
    nazev_slozky = _bezpecny_nazev(f"{nazev} [{company_id}]")
    kontejnery = None

    if n.google_vzor_folder_id:
        kop, _, _ = _kfg_kontejnery(n)
        # do kopie klienta nezahrneme vzorovou složku OP (bere se z „0. vzor“)
        skip: set[str] = set()
        vzor_op = _vzor_op(drive, n)
        if vzor_op:
            skip.add(vzor_op["id"])
        root = drive.copy_tree(n.google_vzor_folder_id, parent, nazev_slozky, skip)
        kont_op = _najdi_podslozku(drive, root["id"], kop)
        if kont_op:
            kontejnery = {"op": kont_op["id"]}
    else:
        root = drive.create_folder(nazev_slozky, parent)

    ef = KonektorEntityFolder(
        entity="company", entity_id=company_id,
        drive_folder_id=root["id"], drive_folder_url=root.get("webViewLink", ""),
        name=nazev, kontejnery=kontejnery,
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

    # název složky = číslo OP (Raynet `code`, např. OP-26-0223) + název
    nazev = _nazev_s_cislem(deal, deal_id)
    kop, knab, kobj = _kfg_kontejnery(n)
    kontejnery = None

    if n.google_vzor_folder_id:
        vzor_op = _vzor_op(drive, n)
        if vzor_op is None:
            raise RuntimeError("Ve vzoru „0. vzor“ chybí vzorová složka obchodního případu.")
        cil_kont_op = _kontejner_ze_slozky(drive, zak, "op", kop)
        if cil_kont_op is None:
            raise RuntimeError(f"Ve složce klienta chybí kontejner „{kop}“.")
        # vzorové složky objednávek do kopie OP nezahrneme (berou se z „0. vzor“)
        skip: set[str] = set()
        vzor_obj = _vzor_polozky(drive, n, "objednavky")
        if vzor_obj:
            skip.add(vzor_obj["id"])
        op = drive.copy_tree(vzor_op["id"], cil_kont_op, nazev, skip)
        knab_kopie = _najdi_podslozku(drive, op["id"], knab)
        kobj_kopie = _najdi_podslozku(drive, op["id"], kobj)
        kontejnery = {
            "nabidky": knab_kopie["id"] if knab_kopie else None,
            "objednavky": kobj_kopie["id"] if kobj_kopie else None,
        }
    else:
        op = drive.create_folder(nazev, zak.drive_folder_id)
        for sub in _podslozky(n):
            drive.create_folder(sub, op["id"])

    ef = KonektorEntityFolder(
        entity="deal", entity_id=deal_id,
        drive_folder_id=op["id"], drive_folder_url=op.get("webViewLink", ""),
        name=nazev, kontejnery=kontejnery,
    )
    db.add(ef)
    db.commit()
    ok, zprava = _zapis_odkaz(
        raynet, "deal", deal_id, [n.raynet_deal_drive_field, n.raynet_deal_drive_field2], ef.drive_folder_url
    )
    zaloguj(db, "info" if ok else "warn", "novy_deal",
            f"Vytvořena složka obch. případu „{nazev}“; {zprava}.",
            {"deal_id": deal_id, "company_id": company_id, "drive_folder_id": ef.drive_folder_id})
    return ef


def _zpracuj_zaznam_pod_op(db, n, raynet, drive, entity: str, resource: str, record_id: int, pole_kod: str) -> dict:
    """Nabídka/objednávka: vlastní složka v příslušném kontejneru pod OP + odkaz.

    Kontejner (nabídky/objednávky) se hledá v OP složce – přednostně přes
    uložené ID, jinak podle názvu. Je-li ve vzoru pro daný typ vzorová složka
    (jediná podsložka kontejneru), zkopíruje se; jinak vznikne prostá složka.
    """
    if _najdi_ef(db, entity, record_id) is not None:
        return {"skip": True}
    zaznam = raynet.get_record(resource, record_id)
    # vazba na obch. případ – Raynet ji v detailu nabídky/objednávky vede pod
    # názvem `businessCase`; tolerantně zkusíme i `deal`.
    deal_id = _vazba_id(zaznam, "businessCase") or _vazba_id(zaznam, "deal")
    if deal_id is None:
        raise RuntimeError(f"{resource} {record_id} nemá navázaný obchodní případ (deal).")
    op_ef = zajisti_slozku_op(db, raynet, drive, n, deal_id)

    _, knab, kobj = _kfg_kontejnery(n)
    klic, nazev_kont = ("nabidky", knab) if entity == "offer" else ("objednavky", kobj)
    cil_kont = _kontejner_ze_slozky(drive, op_ef, klic, nazev_kont)
    if cil_kont is None:
        # fallback: vytvoř kontejner přímo v OP složce (starý režim bez vzoru)
        vytvoreny = drive.create_folder(nazev_kont, op_ef.drive_folder_id)
        cil_kont = vytvoreny["id"]

    nazev = _nazev_s_cislem(zaznam, record_id)
    vzor = _vzor_polozky(drive, n, klic) if n.google_vzor_folder_id else None
    if vzor is not None:
        slozka = drive.copy_tree(vzor["id"], cil_kont, nazev)
    else:
        slozka = drive.create_folder(nazev, cil_kont)

    ef = KonektorEntityFolder(
        entity=entity, entity_id=record_id,
        drive_folder_id=slozka["id"], drive_folder_url=slozka.get("webViewLink", ""), name=nazev,
    )
    db.add(ef)
    db.commit()
    ok, zprava = _zapis_odkaz(raynet, resource, record_id, [pole_kod], ef.drive_folder_url)
    zaloguj(db, "info" if ok else "warn", f"novy_{entity}",
            f"Vytvořena složka „{nazev}“ v „{nazev_kont}“; {zprava}.",
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
    return _zpracuj_zaznam_pod_op(db, n, raynet, drive, "offer", "offer", offer_id, n.raynet_offer_drive_field)


def zpracuj_nova_objednavka(db: Session, order_id: int) -> dict:
    """Vznik objednávky → podsložka v 02_Objednávky pod OP + odkaz do pole objednávky."""
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    return _zpracuj_zaznam_pod_op(db, n, raynet, drive, "order", "order", order_id, n.raynet_order_drive_field)


# =================== Hromadný import existujících dat z Raynetu ===================
def spocitej_rozsah(db: Session) -> dict:
    """Zjistí, kolik firem/OP/nabídek/objednávek je v Raynetu (náhled před importem)."""
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, _ = vytvor_klienty(n)
    rozsah = {resource: len(raynet.list_ids(resource)) for resource, _, _ in _IMPORT_PLAN}
    zaloguj(db, "info", "import", f"Rozsah v Raynetu: {rozsah}", rozsah)
    return rozsah


def naplan_import(db: Session) -> dict:
    """Zařadí do fronty úlohy pro všechny existující záznamy v Raynetu.

    Worker je zpracuje sekvenčně (respektuje limit spojení) a idempotentně –
    co už složku má, přeskočí. Lze spouštět opakovaně (dogeneruje jen chybějící).
    Pořadí (firmy → OP → nabídky → objednávky) je jen orientační; nadřazené
    složky si každá úroveň v případě potřeby dohledá/vytvoří sama.
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, _ = vytvor_klienty(n)

    souhrn: dict = {}
    for resource, typ, klic in _IMPORT_PLAN:
        ids = raynet.list_ids(resource)
        for rid in ids:
            db.add(KonektorJobQueue(typ=typ, payload={klic: rid}, status="pending"))
        db.commit()  # commit po každé entitě (jedna dávka)
        souhrn[resource] = len(ids)

    celkem = sum(souhrn.values())
    zaloguj(db, "info", "import",
            f"Hromadný import zařazen do fronty ({celkem} úloh): {souhrn}.", souhrn)
    return {"zarazeno": souhrn, "celkem": celkem}


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


# =================== Flow C: zrcadlení do modulu Dokumenty (DMS, FR3) ===================
DMS_KOREN_PATH = "/Dokumenty"  # prefix cest v modulu Dokumenty


def _dms_najdi_polozku(raynet: RaynetClient, dms_path: str | None, nazev_ocisteny: str, je_slozka: bool) -> dict | None:
    """Najde v DMS složce (dané cestou `dms_path`, None=kořen) položku daného
    typu a názvu. Řídí se skutečným stavem v Raynetu (ne uloženými id) → odolné
    vůči smazání i duplicitám. Vrací {'id', 'path'}, nebo None když neexistuje.
    """
    try:
        data = raynet.list_document_folders(dms_path)
    except Exception:  # noqa: BLE001 - nedostupný výpis → chováme se jako „nenalezeno“
        return None
    typ = "Folder" if je_slozka else "Document"
    for it in (data or []):
        if isinstance(it, dict) and it.get("type") == typ and (it.get("name") or "") == nazev_ocisteny:
            try:
                return {"id": int(it.get("id")), "path": it.get("path")}
            except (ValueError, TypeError):
                return None
    return None


def zrcadli_strom(db: Session) -> dict:
    """Zrcadlí OBSAH zdrojové složky na Disku do modulu Dokumenty (DMS) v Raynetu.

    Zdroj = `google_dms_zdroj_folder_id`; zrcadlí se jeho podsložky a jejich
    potomci (ne zdrojová složka samotná). Podsložky → složky v Dokumentech
    (`PUT /dms/folder/`), soubory → odkazy na Disk (`PUT /dms/document/`,
    pole link). Soubory ležící přímo v kořeni zdroje se přeskočí (DMS dokument
    musí být ve složce). Idempotentní přes tree_mirror – opakované spuštění jen
    doplní nové položky (mazání/přejmenování zatím neřeší).
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)

    zdroj = (n.google_dms_zdroj_folder_id or "").strip()
    if not zdroj:
        raise NastaveniNepripraveno("Není nastavena zdrojová složka pro zrcadlení do Dokumentů.")

    vytvoreno_slozek = vytvoreno_souboru = preskoceno = chyb = 0
    posledni_log = 0
    # fronta: (drive_folder_id, dms_path, dms_parent_id) – zpracováváme OBSAH
    # drive_folder_id do DMS složky s cestou dms_path a id dms_parent_id.
    # Kořen: dms_path=None (výpis přes GET /dms/), dms_parent_id=None.
    fronta: list[tuple[str, str | None, int | None]] = [(zdroj, None, None)]
    navstivene: set[str] = set()

    while fronta:
        drive_folder_id, dms_path, dms_parent = fronta.pop()
        if drive_folder_id in navstivene:
            continue
        navstivene.add(drive_folder_id)
        zaklad_path = dms_path or DMS_KOREN_PATH  # pro sestavení cest potomků

        for child in drive.list_children(drive_folder_id):
            nazev = child.get("name", "")
            ocisteny = dms_bezpecny_nazev(nazev)
            if child.get("mimeType") == FOLDER_MIME:
                # najdi-nebo-vytvoř: řídíme se skutečným stavem v DMS (ne uloženými id)
                nalez = _dms_najdi_polozku(raynet, dms_path, ocisteny, je_slozka=True)
                if nalez is not None:
                    dms_id = nalez["id"]
                    child_path = nalez.get("path") or f"{zaklad_path}/{ocisteny}"
                else:
                    try:
                        dms_id = raynet.create_document_folder(nazev, dms_parent)
                    except Exception as e:  # noqa: BLE001 - jedna vadná složka nezastaví celek
                        chyb += 1
                        zaloguj(db, "warn", "zrcadleni",
                                f"Složku „{nazev}“ se nepodařilo vytvořit v Dokumentech: {e}",
                                {"path": zaklad_path})
                        continue  # přeskočíme i její potomky
                    child_path = f"{zaklad_path}/{ocisteny}"
                    vytvoreno_slozek += 1
                fronta.append((child["id"], child_path, int(dms_id)))
            else:
                if dms_parent is None:
                    preskoceno += 1  # soubor přímo v kořeni zdroje – nemá kam (DMS chce složku)
                    continue
                if _dms_najdi_polozku(raynet, dms_path, ocisteny, je_slozka=False) is not None:
                    continue  # odkaz už v této složce existuje
                try:
                    raynet.create_dms_link(nazev, child.get("webViewLink", ""), dms_parent)
                    vytvoreno_souboru += 1
                except Exception as e:  # noqa: BLE001
                    chyb += 1
                    zaloguj(db, "warn", "zrcadleni",
                            f"Odkaz „{nazev}“ se nepodařilo vytvořit v Dokumentech: {e}",
                            {"path": zaklad_path})

        # průběžný log – ať je vidět, že běh pokračuje (u velkých stromů)
        hotovo = vytvoreno_slozek + vytvoreno_souboru
        if hotovo - posledni_log >= 25:
            posledni_log = hotovo
            zaloguj(db, "info", "zrcadleni",
                    f"Zrcadlení běží – složek {vytvoreno_slozek}, odkazů {vytvoreno_souboru}, "
                    f"fronta {len(fronta)}…",
                    {"slozek": vytvoreno_slozek, "souboru": vytvoreno_souboru, "fronta": len(fronta)})

    zaloguj(
        db, "info", "zrcadleni",
        f"Zrcadlení do Dokumentů hotovo – nových složek {vytvoreno_slozek}, "
        f"odkazů {vytvoreno_souboru}"
        + (f", přeskočeno souborů v kořeni {preskoceno}" if preskoceno else "")
        + (f", chyb {chyb}" if chyb else "") + ".",
        {"slozek": vytvoreno_slozek, "souboru": vytvoreno_souboru, "preskoceno": preskoceno, "chyb": chyb},
    )
    return {"slozek": vytvoreno_slozek, "souboru": vytvoreno_souboru, "preskoceno": preskoceno, "chyb": chyb}


# =================== Disk → RN Dokumenty (okamžitě přes watch) ===================
def _segmenty_v_master(drive: DriveClient, file: dict, master_id: str, cache: dict) -> list[str] | None:
    """Názvy Disk složek od master folderu (bez něj) k rodičovské složce souboru.

    Vrací seznam segmentů (shora dolů), nebo None když soubor není v master
    podstromu. Rodiče se cachují, ať se stejná složka nedotazuje opakovaně.
    """
    parents = file.get("parents") or []
    pid = parents[0] if parents else None
    retez: list[str] = []
    depth = 0
    while pid and depth < 40:
        depth += 1
        if pid == master_id:
            return list(reversed(retez))
        info = cache.get(pid)
        if info is None:
            try:
                info = drive.get_file(pid)
            except Exception:  # noqa: BLE001 - nedostupný rodič → bereme jako mimo
                return None
            cache[pid] = info
        if info.get("trashed"):
            return None
        retez.append(info.get("name", ""))
        p = info.get("parents") or []
        pid = p[0] if p else None
    return None


def zrcadli_zmeny_dms(db: Session) -> dict:
    """Disk → RN Dokumenty OKAMŽITĚ: promítne změny v master folderu do modulu
    Dokumenty jako odkazy. Čte Drive changes (jen změněné položky, ne full-scan)
    s vlastním page tokenem (KonektorDriveChangeState id=2). Volá se z watch push.

    Echo suppression: soubory nahrané naším RN→Disk přesunem (origin=raynet) se
    přeskočí. Idempotence: odkaz se nevytvoří, pokud už v cílové složce je.
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    master = (n.google_dms_zdroj_folder_id or "").strip()
    if not master:
        return {"skip": "bez master složky"}
    raynet, drive = vytvor_klienty(n)

    stav = db.get(KonektorDriveChangeState, 2)
    if stav is None:
        stav = KonektorDriveChangeState(id=2, page_token="")
        db.add(stav)
        db.commit()
    if not stav.page_token:
        stav.page_token = drive.get_start_page_token(n.google_shared_drive_id)
        db.commit()
        zaloguj(db, "info", "dms_zmeny", "Sledování změn pro Dokumenty inicializováno (od teď).")
        return {"inicializace": True}

    zmeny, novy = drive.list_changes(stav.page_token, n.google_shared_drive_id)
    cache: dict = {}
    vytvoreno = 0
    for ch in zmeny:
        file = ch.get("file")
        if ch.get("removed") or not file or file.get("trashed"):
            continue
        if file.get("mimeType") == FOLDER_MIME:
            continue
        if (file.get("appProperties") or {}).get("origin") == "raynet":
            continue  # náš vlastní přesun – neduplikovat odkaz
        segmenty = _segmenty_v_master(drive, file, master, cache)
        if segmenty is None:
            continue  # soubor mimo master podstrom

        # zajisti DMS složky po cestě (find-or-create, řízeno path)
        dms_parent: int | None = None
        dms_path: str | None = None
        for seg_name in segmenty:
            seg = dms_bezpecny_nazev(seg_name)
            nalez = _dms_najdi_polozku(raynet, dms_path, seg, je_slozka=True)
            if nalez is not None:
                dms_parent = nalez["id"]
                dms_path = nalez.get("path") or f"{dms_path or DMS_KOREN_PATH}/{seg}"
            else:
                dms_parent = raynet.create_document_folder(seg_name, dms_parent)
                dms_path = f"{dms_path or DMS_KOREN_PATH}/{seg}"
        if dms_parent is None:
            continue  # soubor přímo v master root – DMS dokument musí být ve složce

        nazev = file.get("name", "")
        if _dms_najdi_polozku(raynet, dms_path, dms_bezpecny_nazev(nazev), je_slozka=False) is not None:
            continue  # odkaz už existuje
        raynet.create_dms_link(nazev, file.get("webViewLink", ""), dms_parent)
        vytvoreno += 1

    stav.page_token = novy
    db.commit()
    if vytvoreno:
        zaloguj(db, "info", "dms_zmeny",
                f"Disk → Dokumenty: vytvořeno {vytvoreno} nových odkazů.",
                {"vytvoreno": vytvoreno, "zmen": len(zmeny)})
    return {"vytvoreno": vytvoreno, "zmen": len(zmeny)}


# =================== RN Dokumenty → Disk (sken) ===================
def _dms_cesta_na_disk(drive: DriveClient, master_id: str, dms_path: str | None) -> str:
    """Vrátí id Disk složky (v master folderu) odpovídající RN cestě `dms_path`.

    Cestu spáruje po segmentech: pro každý segment (očištěný RN název) najde na
    Disku podsložku, jejíž očištěný název odpovídá; chybějící dotvoří. Kořen
    Dokumentů (`/Dokumenty` nebo prázdné) = přímo master folder.
    """
    if not dms_path:
        return master_id
    segmenty = [s for s in dms_path.split("/") if s]
    if segmenty and segmenty[0].strip().lower() == "dokumenty":
        segmenty = segmenty[1:]
    parent = master_id
    for seg in segmenty:
        nalez = None
        for f in drive.list_children(parent):
            if f.get("mimeType") == FOLDER_MIME and dms_bezpecny_nazev(f.get("name", "")) == seg:
                nalez = f
                break
        if nalez is None:
            nalez = drive.create_folder(seg, parent)
        parent = nalez["id"]
    return parent


def dms_sken(db: Session) -> dict:
    """Sken modulu Dokumenty (RN → Disk).

    Projde strom Dokumentů a najde FYZICKÉ soubory (mají `file`, nikoli `link` –
    náš odkaz se přeskočí, echo suppression).

    - Přesun VYPNUTÝ (`dms_presun_zapnuto=False`): jen DETEKCE – nahlásí počet.
    - Přesun ZAPNUTÝ, baseline zatím nenastavena: zaznamená stávající soubory
      jako baseline („staré, neřešit") a NIC nepřesune.
    - Přesun ZAPNUTÝ, baseline existuje: soubory mimo baseline přesune na Disk
      a v RN nahradí odkazem. Pořadí je bezpečné: stáhnout → ověřit velikost →
      nahrát na Disk → ověřit velikost na Disku → teprve pak smazat v RN →
      vložit odkaz. Když cokoli selže, originál v RN zůstane.
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        raise NastaveniNepripraveno("Nastavení konektoru neexistuje.")
    raynet, drive = vytvor_klienty(n)
    master = (n.google_dms_zdroj_folder_id or "").strip()

    # --- 1) projít strom a nasbírat fyzické soubory (s cestou jejich složky) ---
    calls = slozky = 0
    fyzicke: list[dict] = []
    stack: list[str | None] = [None]
    navstivene: set = set()
    while stack:
        path = stack.pop()
        if path in navstivene:
            continue
        navstivene.add(path)
        calls += 1
        try:
            data = raynet.list_document_folders(path)
        except Exception:  # noqa: BLE001 - nedostupnou složku přeskočíme
            continue
        for it in (data or []):
            if not isinstance(it, dict):
                continue
            if it.get("type") == "Folder":
                slozky += 1
                if it.get("path"):
                    stack.append(it["path"])
            elif it.get("type") == "Document" and it.get("file") and not it.get("link"):
                fyzicke.append({
                    "doc_id": it.get("id"),
                    "file_id": (it.get("file") or {}).get("id"),
                    "name": it.get("name"),
                    "path": path,  # cesta složky, ve které dokument leží
                })

    # --- 2) režim detekce ---
    if not n.dms_presun_zapnuto:
        zaloguj(db, "info", "dms_sken",
                f"Sken Dokumentů (detekce): {slozky} složek ({calls} API callů), "
                f"fyzických souborů: {len(fyzicke)}. Přesun je vypnutý.",
                {"slozky": slozky, "cally": calls, "fyzickych": len(fyzicke)})
        return {"slozky": slozky, "cally": calls, "fyzickych": len(fyzicke), "presun": False}

    # --- 3) inicializace baseline (stávající soubory se nepřesouvají) ---
    if n.dms_baseline is None:
        n.dms_baseline = [f["doc_id"] for f in fyzicke]
        db.commit()
        zaloguj(db, "info", "dms_sken",
                f"Přesun zapnut – baseline nastavena ({len(fyzicke)} stávajících souborů se nebude "
                f"přesouvat). Přesouvat se budou jen soubory přidané od teď.",
                {"baseline": len(fyzicke)})
        return {"slozky": slozky, "cally": calls, "baseline_nastaveno": len(fyzicke)}

    # --- 4) přesun nových souborů (mimo baseline) ---
    baseline = set(n.dms_baseline or [])
    presunuto = chyb = 0
    for f in fyzicke:
        if f["doc_id"] in baseline or not f.get("file_id"):
            continue
        try:
            detail = raynet.get_dms_document(f["doc_id"])
            dms_folder_id = (detail.get("folder") or {}).get("id")
            obsah, fn, ct, sz = raynet.stahni_soubor(f["file_id"])          # stáhnout (+ověří velikost)
            disk_folder = _dms_cesta_na_disk(drive, master, f["path"])       # cílová Disk složka (1:1)
            nahrany = drive.upload_file(
                f["name"], disk_folder, obsah,
                mime=ct or "application/octet-stream", app_properties={"origin": "raynet"},
            )
            g = drive.get_file(nahrany["id"])                                # ověřit velikost NA DISKU
            if g.get("size") is not None and int(g["size"]) != len(obsah):
                raise RuntimeError(f"velikost na Disku {g.get('size')} ≠ {len(obsah)} – originál v RN ponechán")
            raynet.smaz_dms_dokument(f["doc_id"])                            # teprve teď smazat originál
            if dms_folder_id:
                raynet.create_dms_link(f["name"], nahrany.get("webViewLink", ""), dms_folder_id)
            presunuto += 1
            zaloguj(db, "info", "dms_sken",
                    f"Přesunut soubor „{f['name']}“ na Disk a v RN nahrazen odkazem.",
                    {"doc_id": f["doc_id"], "drive_file_id": nahrany["id"], "path": f["path"]})
        except Exception as e:  # noqa: BLE001 - selhání jednoho souboru nezastaví ostatní
            chyb += 1
            zaloguj(db, "warn", "dms_sken",
                    f"Přesun souboru „{f['name']}“ selhal (originál v RN ponechán): {e}",
                    {"doc_id": f["doc_id"]})

    zaloguj(db, "info", "dms_sken",
            f"Sken Dokumentů hotov: {slozky} složek ({calls} API callů), přesunuto {presunuto}"
            + (f", chyb {chyb}" if chyb else "") + ".",
            {"slozky": slozky, "cally": calls, "presunuto": presunuto, "chyb": chyb})
    return {"slozky": slozky, "cally": calls, "presunuto": presunuto, "chyb": chyb}


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
