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
# počet opakování jednotlivých Drive volání při přechodných chybách
# (HTTP 5xx a rate-limit) – klient je opakuje s exponenciálním backoffem
DRIVE_RETRY = 5


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
            .execute(num_retries=DRIVE_RETRY)
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
            .execute(num_retries=DRIVE_RETRY)
        )
        return vysledek.get("files", [])

    def find_folder(self, name: str, parent_id: str) -> dict | None:
        """Najde podsložku daného jména pod parentem (nebo None)."""
        for f in self.list_children(parent_id):
            if f.get("mimeType") == FOLDER_MIME and f.get("name") == name:
                return f
        return None

    def copy_file(self, file_id: str, dest_parent_id: str, new_name: str | None = None) -> dict:
        """Zkopíruje soubor do cílové složky (Drive `files.copy`)."""
        body: dict = {"parents": [dest_parent_id]}
        if new_name:
            body["name"] = new_name
        return (
            self.service.files()
            .copy(fileId=file_id, body=body, fields="id,name,webViewLink", supportsAllDrives=True)
            .execute(num_retries=DRIVE_RETRY)
        )

    def _copy_children(self, src_id: str, dest_id: str, skip_ids: set[str]) -> None:
        """Rekurzivně zkopíruje obsah složky (složky nově vytvoří, soubory zkopíruje)."""
        for ch in self.list_children(src_id):
            if ch["id"] in skip_ids:
                continue
            if ch.get("mimeType") == FOLDER_MIME:
                nova = self.create_folder(ch.get("name", ""), dest_id)
                self._copy_children(ch["id"], nova["id"], skip_ids)
            else:
                self.copy_file(ch["id"], dest_id, ch.get("name"))

    def copy_tree(
        self, src_folder_id: str, dest_parent_id: str, new_name: str, skip_ids: set[str] | None = None
    ) -> dict:
        """Zkopíruje celý strom složky pod cíl a přejmenuje kořen na `new_name`.

        Google Drive neumí zkopírovat složku jedním voláním – kopíruje se
        rekurzivně (složky se zakládají, soubory kopírují). `skip_ids` = ID
        podpoložek, které se do kopie NEmají zahrnout (typicky vzorové
        podsložky, které se berou centrálně z „0. vzor“). Vrací {id,name,webViewLink}
        nové kořenové složky.
        """
        skip = set(skip_ids or ())
        root = self.create_folder(new_name, dest_parent_id)
        self._copy_children(src_folder_id, root["id"], skip)
        return root

    def strom(self, folder_id: str, hloubka: int = 0, max_hloubka: int = 8) -> list[str]:
        """Rekurzivně vypíše strom složky jako řádky s odsazením (diagnostika vzoru).

        Složky mají prefix „[D]“, soubory „[F]“. Slouží k zjištění přesných
        názvů a vnoření vzorové struktury bez ručního opisování z Disku.
        """
        radky: list[str] = []
        deti = sorted(self.list_children(folder_id), key=lambda x: x.get("name", ""))
        for f in deti:
            je_slozka = f.get("mimeType") == FOLDER_MIME
            radky.append(f"{'  ' * hloubka}{'[D]' if je_slozka else '[F]'} {f.get('name', '')}")
            if je_slozka and hloubka < max_hloubka:
                radky.extend(self.strom(f["id"], hloubka + 1, max_hloubka))
        return radky

    def upload_file(
        self,
        name: str,
        parent_id: str,
        data: bytes,
        mime: str = "application/octet-stream",
        app_properties: dict | None = None,
    ) -> dict:
        """Nahraje soubor do složky. `app_properties` slouží k echo suppression
        (origin=raynet → Disk→Raynet směr ho pak přeskočí)."""
        from googleapiclient.http import MediaInMemoryUpload

        body = {"name": name, "parents": [parent_id]}
        if app_properties:
            body["appProperties"] = app_properties
        media = MediaInMemoryUpload(data, mimetype=mime, resumable=False)
        return (
            self.service.files()
            .create(body=body, media_body=media, fields="id,name,webViewLink", supportsAllDrives=True)
            .execute(num_retries=DRIVE_RETRY)
        )

    def get_file(self, file_id: str) -> dict:
        """Detail souboru vč. rodičů a příznaku trashed."""
        return (
            self.service.files()
            .get(
                fileId=file_id,
                fields="id,name,mimeType,webViewLink,parents,trashed,md5Checksum,appProperties,size",
                supportsAllDrives=True,
            )
            .execute(num_retries=DRIVE_RETRY)
        )

    # ---- inkrementální změny (changes.list) ----
    def get_start_page_token(self, drive_id: str) -> str:
        vysledek = (
            self.service.changes()
            .getStartPageToken(driveId=drive_id, supportsAllDrives=True)
            .execute(num_retries=DRIVE_RETRY)
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
                .execute(num_retries=DRIVE_RETRY)
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
            .execute(num_retries=DRIVE_RETRY)
        )

    def stop_channel(self, channel_id: str, resource_id: str) -> None:
        self.service.channels().stop(body={"id": channel_id, "resourceId": resource_id}).execute(num_retries=DRIVE_RETRY)


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
        drive = service.drives().get(driveId=shared_drive_id).execute(num_retries=DRIVE_RETRY)
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
