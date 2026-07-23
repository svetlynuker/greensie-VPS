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


FOLDER_MIME = "application/vnd.google-apps.folder"


class DriveClient:
    """Fasáda nad Google Drive API v3 pro Shared Drive.

    Drží sestavený `service`. Všechny volání používají `supportsAllDrives=True`
    (Shared Drive). Ve F2 využíváme jen tvorbu složek.
    """

    def __init__(self, sa_json_str: str, subject_email: str | None = None):
        self.service = _build_service(sa_json_str, subject_email or None)

    def create_folder(self, name: str, parent_id: str) -> dict:
        """Vytvoří složku pod parent_id. Vrací {id, name, webViewLink}."""
        metadata = {"name": name, "mimeType": FOLDER_MIME, "parents": [parent_id]}
        return (
            self.service.files()
            .create(body=metadata, fields="id,name,webViewLink", supportsAllDrives=True)
            .execute()
        )

    def list_children(self, parent_id: str) -> list[dict]:
        """Vypíše (nesmazané) přímé potomky složky."""
        q = f"'{parent_id}' in parents and trashed=false"
        vysledek = (
            self.service.files()
            .list(
                q=q,
                fields="files(id,name,mimeType,webViewLink)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
                pageSize=1000,
            )
            .execute()
        )
        return vysledek.get("files", [])

    def find_folder(self, name: str, parent_id: str) -> dict | None:
        """Najde podsložku daného jména pod parentem (nebo None)."""
        for f in self.list_children(parent_id):
            if f.get("mimeType") == FOLDER_MIME and f.get("name") == name:
                return f
        return None

    def get_file(self, file_id: str) -> dict:
        """Detail souboru vč. rodičů a příznaku trashed."""
        return (
            self.service.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,webViewLink,parents,trashed,md5Checksum,appProperties",
                supportsAllDrives=True,
            )
            .execute()
        )

    # ---- inkrementální změny (changes.list) ----
    def get_start_page_token(self, drive_id: str) -> str:
        vysledek = (
            self.service.changes()
            .getStartPageToken(driveId=drive_id, supportsAllDrives=True)
            .execute()
        )
        return vysledek.get("startPageToken", "")

    def list_changes(self, page_token: str, drive_id: str) -> tuple[list[dict], str]:
        """Vrátí (změny, nový_page_token). Prochází všechny stránky změn."""
        zmeny: list[dict] = []
        token = page_token
        novy_token = page_token
        while token:
            vysledek = (
                self.service.changes()
                .list(
                    pageToken=token,
                    driveId=drive_id,
                    spaces="drive",
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    fields=(
                        "nextPageToken,newStartPageToken,"
                        "changes(fileId,removed,file(id,name,mimeType,webViewLink,parents,trashed,appProperties))"
                    ),
                    pageSize=200,
                )
                .execute()
            )
            zmeny.extend(vysledek.get("changes", []))
            if vysledek.get("nextPageToken"):
                token = vysledek["nextPageToken"]
            else:
                novy_token = vysledek.get("newStartPageToken", token)
                break
        return zmeny, novy_token

    # ---- push kanály (files/changes.watch) ----
    def watch_changes(self, page_token: str, drive_id: str, channel_id: str, address: str, token: str, ttl_s: int = 604800) -> dict:
        """Zaregistruje push kanál na změny Shared Drive → `address` (náš webhook)."""
        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": address,
            "token": token,
            "expiration": None,  # necháme na Google (max ~ týden), řídíme obnovou
        }
        return (
            self.service.changes()
            .watch(
                pageToken=page_token,
                driveId=drive_id,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                body=body,
            )
            .execute()
        )

    def stop_channel(self, channel_id: str, resource_id: str) -> None:
        self.service.channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute()


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
