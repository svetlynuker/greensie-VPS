"""Tenká fasáda nad Google Drive API v3 (service account + Shared Drive).

Auth (dle D2): service account s domain-wide delegation, soubory ve Shared
Drive. Scope `drive`. Volitelně impersonace uživatele (subject) přes delegaci.

Google knihovny se importují až uvnitř funkcí (lazy), aby jejich případná
nepřítomnost neshodila start celé aplikace.

Ve F1 využíváme jen `test_spojeni()`. Operace pro tvorbu složek, upload,
list, changes a watch přibudou v dalších fázích.
"""

import json

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _build_service(sa_json_str: str, subject_email: str | None = None):
    """Sestaví Drive API klienta ze service-account JSON (řetězec)."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    info = json.loads(sa_json_str)
    creds = service_account.Credentials.from_service_account_info(info, scopes=[DRIVE_SCOPE])
    if subject_email:
        # domain-wide delegation: jednáme jménem konkrétního uživatele
        creds = creds.with_subject(subject_email)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def test_spojeni(
    sa_json_str: str,
    shared_drive_id: str,
    subject_email: str | None = None,
) -> tuple[bool, str]:
    """Ověří přístup ke Shared Drive (drives.get)."""
    if not sa_json_str:
        return False, "Chybí service-account JSON."
    if not shared_drive_id:
        return False, "Chybí ID Shared Drive."
    try:
        json.loads(sa_json_str)
    except json.JSONDecodeError:
        return False, "Service-account JSON není platný JSON."

    try:
        service = _build_service(sa_json_str, subject_email or None)
        drive = service.drives().get(driveId=shared_drive_id).execute()
        nazev = drive.get("name", shared_drive_id)
        return True, f"Spojení OK – Shared Drive „{nazev}“."
    except Exception as e:  # noqa: BLE001 - chybu chceme ukázat uživateli čitelně
        from googleapiclient.errors import HttpError

        if isinstance(e, HttpError):
            kod = e.resp.status if e.resp is not None else "?"
            if kod == 404:
                return False, "Shared Drive nenalezen (404) – zkontroluj ID a sdílení se service accountem."
            if kod in (401, 403):
                return False, (
                    f"Přístup odmítnut ({kod}) – service account nemá přístup ke Shared Drive "
                    "nebo není zapnutá delegace."
                )
            return False, f"Google chyba: HTTP {kod}."
        return False, f"Google chyba: {e}"
