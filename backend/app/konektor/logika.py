"""Byznys logika konektoru – Flow A (FR1): nový klient → struktura složek.

Sestaví klienty z uloženého (dešifrovaného) nastavení, vytvoří na Disku
kořenovou složku klienta s podsložkami dle šablony, uloží mapování a zapíše
odkaz zpět do vlastního pole company v Raynetu.

Idempotence: pokud už mapování pro company existuje, složky se znovu netvoří.
"""

from sqlalchemy.orm import Session

from app.konektor import crypto
from app.konektor.google_klient import DriveClient
from app.konektor.logger import zaloguj
from app.konektor.models import KonektorClientFolderMap, KonektorNastaveni
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
