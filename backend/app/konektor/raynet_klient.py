"""Tenká fasáda nad RAYNET CRM REST API.

Auth (ověřeno v dokumentaci, viz INVENTORY sekce 4): HTTP Basic
(uživatel : API klíč) + hlavička `X-Instance-Name`. Base URL dle instance,
u českých typicky `https://app.raynet.cz/api/v2/`.

Ve F1 využíváme jen `test_spojeni()`. Operace pro FR1/FR2/FR3 (company,
document, file/attachment, webhook) přibudou v dalších fázích.
"""

import requests

# Interní kód entity → skutečný název REST endpointu Raynetu.
# V konektoru používáme krátké kódy (deal/order), Raynet API má ale
# /businessCase/ a /salesOrder/ (company a offer se shodují).
_RESOURCE_ENDPOINT = {
    "company": "company",
    "deal": "businessCase",
    "offer": "offer",
    "order": "salesOrder",
}


class RaynetClient:
    def __init__(self, instance: str, api_user: str, api_key: str, base_url: str):
        self.instance = (instance or "").strip()
        self.api_user = (api_user or "").strip()
        self.api_key = (api_key or "").strip()
        # sjednotíme na tvar končící „/“, ať se dá spolehlivě skládat cesta
        self.base_url = (base_url or "").strip().rstrip("/") + "/"

    def _headers(self) -> dict:
        return {"X-Instance-Name": self.instance, "Accept": "application/json"}

    def test_spojeni(self, timeout: int = 15) -> tuple[bool, str]:
        """Ověří přístup lehkým dotazem (GET /company/?limit=1)."""
        if not (self.instance and self.api_user and self.api_key):
            return False, "Chybí instance, API uživatel nebo API klíč."
        url = self.base_url + "company/?limit=1"
        try:
            r = requests.get(
                url, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout
            )
        except requests.RequestException as e:
            return False, f"Raynet nedostupný: {e}"

        if r.status_code == 200:
            return True, "Spojení s Raynetem OK."
        if r.status_code == 401:
            return False, "Přihlášení selhalo (401) – zkontroluj uživatele, API klíč a instanci."
        if r.status_code in (402, 403):
            return False, (
                f"Přístup odmítnut ({r.status_code}) – možná chybí tarif Professional+ "
                "nebo API uživatel nemá práva."
            )
        if r.status_code == 429:
            return False, "Překročen limit požadavků Raynetu (429) – zkus to za chvíli."
        return False, f"Neočekávaná odpověď Raynetu: HTTP {r.status_code}."

    # ---- operace pro FR1 (Flow A) ----
    def _over_odpoved(self, r: requests.Response, kontext: str) -> dict:
        """Vrátí `data` z odpovědi, nebo vyhodí RuntimeError s čitelnou zprávou.

        Raynet vrací obálku {"success": bool, "data": ...} (ověřeno v dokumentaci).
        """
        if r.status_code == 429:
            raise RuntimeError(f"{kontext}: překročen limit požadavků Raynetu (429).")
        if r.status_code >= 400:
            raise RuntimeError(f"{kontext}: HTTP {r.status_code} – {r.text[:300]}")
        try:
            telo = r.json()
        except ValueError:
            raise RuntimeError(f"{kontext}: odpověď není JSON.")
        # success bývá bool i řetězec "true" – bereme oboje
        uspech = telo.get("success")
        if uspech in (False, "false"):
            raise RuntimeError(f"{kontext}: Raynet vrátil success=false ({telo}).")
        return telo.get("data", {})

    # ---- obecné operace pro hierarchii (company/deal/offer/order) ----
    def get_record(self, resource: str, record_id: int, timeout: int = 20) -> dict:
        """Detail záznamu daného typu (GET /{endpoint}/{id}/). Vrací `data`.

        `resource` je interní kód (company/deal/offer/order); na skutečný
        Raynet endpoint se přeloží přes `_RESOURCE_ENDPOINT`.
        """
        endpoint = _RESOURCE_ENDPOINT.get(resource, resource)
        url = f"{self.base_url}{endpoint}/{record_id}/"
        r = requests.get(url, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout)
        return self._over_odpoved(r, f"Načtení {resource} {record_id}")

    def list_ids(self, resource: str, page_size: int = 50, timeout: int = 30) -> list[int]:
        """Vrátí ID všech záznamů daného typu (stránkuje přes offset/limit).

        Řídí se `totalCount` z obálky; fallback na „poslední stránka je kratší
        než limit“. Slouží k hromadnému importu existujících dat z Raynetu.
        """
        endpoint = _RESOURCE_ENDPOINT.get(resource, resource)
        ids: list[int] = []
        offset = 0
        while True:
            url = f"{self.base_url}{endpoint}/?offset={offset}&limit={page_size}"
            r = requests.get(url, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout)
            if r.status_code >= 400:
                raise RuntimeError(f"Výpis {resource}: HTTP {r.status_code} – {r.text[:200]}")
            try:
                telo = r.json()
            except ValueError:
                raise RuntimeError(f"Výpis {resource}: odpověď není JSON.")
            radky = telo.get("data") or []
            for row in radky:
                if isinstance(row, dict) and row.get("id") is not None:
                    ids.append(int(row["id"]))
            if not radky:
                break
            offset += len(radky)
            total = telo.get("totalCount")
            if total is not None:
                if offset >= int(total):
                    break
            elif len(radky) < page_size:
                break
        return ids

    def set_custom_fields(self, resource: str, record_id: int, fields: dict, timeout: int = 20) -> dict:
        """Zapíše vlastní pole záznamu (POST /{resource}/{id}/ s customFields).

        `fields` = {kod_pole: hodnota, …}. Prázdné kódy se vynechají.
        """
        fields = {k: v for k, v in fields.items() if k}
        if not fields:
            return {}
        endpoint = _RESOURCE_ENDPOINT.get(resource, resource)
        url = f"{self.base_url}{endpoint}/{record_id}/"
        telo = {"customFields": fields}
        r = requests.post(
            url, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        return self._over_odpoved(r, f"Zápis vlastních polí do {resource} {record_id}")

    def get_company(self, company_id: int, timeout: int = 20) -> dict:
        """Načte detail company (GET /company/{id}/). Vrací `data` objekt."""
        url = f"{self.base_url}company/{company_id}/"
        r = requests.get(url, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout)
        return self._over_odpoved(r, f"Načtení company {company_id}")

    def set_company_drive_field(
        self, company_id: int, field_code: str, url_value: str, timeout: int = 20
    ) -> dict:
        """Zapíše odkaz na Drive složku do vlastního pole company.

        Modify = POST /company/{id}/ s tělem {"customFields": {kod: hodnota}}
        (tvar customFields ověřen v dokumentaci; přesný kód pole = TO VERIFY
        v UI podle konkrétní instance).
        """
        if not field_code:
            raise RuntimeError("Není nastaven kód vlastního pole pro odkaz na Disk.")
        url = f"{self.base_url}company/{company_id}/"
        telo = {"customFields": {field_code: url_value}}
        r = requests.post(
            url, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        return self._over_odpoved(r, f"Zápis odkazu do company {company_id}")

    # ---- operace pro FR2a (Flow B, Disk → Raynet) ----
    def create_link_document(
        self,
        name: str,
        url_value: str,
        company_id: int | None = None,
        deal_id: int | None = None,
        timeout: int = 20,
    ) -> int:
        """Vytvoří v Raynetu odkazový dokument na soubor na Disku. Vrací jeho id.

        Naváže na company a/nebo deal dle zadaných id. TO VERIFY: přesný tvar
        PUT /document/document/ (pole pro URL a relaci) není zdokumentovaný –
        tělo je nejlepší odhad, po ověření reálným voláním se upraví.
        """
        endpoint = f"{self.base_url}document/document/"
        telo: dict = {"name": name, "url": url_value}
        if company_id is not None:
            telo["company"] = {"id": company_id}
        if deal_id is not None:
            telo["deal"] = {"id": deal_id}
        r = requests.put(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        data = self._over_odpoved(r, "Vytvoření odkazového dokumentu")
        return int(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else 0

    def delete_document(self, document_id: str, timeout: int = 20) -> None:
        """Smaže dokument v Raynetu (DELETE /document/{id}/)."""
        endpoint = f"{self.base_url}document/{document_id}/"
        r = requests.delete(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout
        )
        self._over_odpoved(r, f"Smazání dokumentu {document_id}")

    # ---- operace pro FR3 (Flow C, zrcadlení stromu do modulu Dokumenty) ----
    def list_document_folders(self, parent_id: str | None = None, timeout: int = 30) -> dict | list:
        """Výpis složek a souborů v modulu Dokumenty/DMS (GET /dms/).

        Modul Dokumenty má v API prefix `/dms/` (ne `/document/`). Bez
        `parent_id` vrací kořen. Slouží k diagnostice reálného tvaru dat
        (názvy polí: id, name, parent, typ, případně url…). Vrací `data`.
        """
        url = f"{self.base_url}dms/"
        if parent_id:
            url += f"?folderId={parent_id}"
        r = requests.get(url, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout)
        return self._over_odpoved(r, "Výpis Dokumentů (DMS)")

    def create_document_folder(self, name: str, parent_id: str | None = None, timeout: int = 20) -> int:
        """Vytvoří složku v modulu Dokumenty (PUT /dms/folder/). Vrací id.

        Pole: `name`, `parent` (integer id nadřazené složky, nullable).
        Když parent_id None, vznikne v kořeni.
        """
        endpoint = f"{self.base_url}dms/folder/"
        telo: dict = {"name": name}
        if parent_id:
            telo["parent"] = int(parent_id)
        r = requests.put(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        data = self._over_odpoved(r, f"Vytvoření složky dokumentů „{name}“")
        return int(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else 0

    def put_dms_document(self, telo: dict, timeout: int = 20) -> dict:
        """Odešle syrové tělo na PUT /dms/document/ (vytvoření dokumentu). Vrací `data`."""
        endpoint = f"{self.base_url}dms/document/"
        r = requests.put(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        return self._over_odpoved(r, "Vytvoření dokumentu v DMS")

    def create_dms_link(self, name: str, url_value: str, folder_id: str | int | None = None, timeout: int = 20) -> dict:
        """Vytvoří v modulu Dokumenty (DMS) položku typu ODKAZ (pole `link` = objekt).

        Model odkazů: soubor zůstává na Disku, DMS drží jen odkaz. `folder_id`
        = id nadřazené složky v DMS. Tvar `link` objektu ověřen diagnostikou.
        """
        telo: dict = {"name": name, "link": {"url": url_value}}
        if folder_id:
            telo["folder"] = int(folder_id)
        return self.put_dms_document(telo, timeout=timeout)

    def create_link_document_in_folder(
        self, name: str, url_value: str, parent_id: str, timeout: int = 20
    ) -> int:
        """Vytvoří odkazový dokument v dané složce dokumentů (pro zrcadlení stromu).

        TO VERIFY tvar (url + parent).
        """
        endpoint = f"{self.base_url}document/document/"
        telo = {"name": name, "url": url_value, "parent": {"id": parent_id}}
        r = requests.put(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        data = self._over_odpoved(r, f"Vytvoření odkazu ve stromu „{name}“")
        return int(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else 0

    # ---- operace pro FR2b (Flow B, Raynet → Disk) ----
    def get_document(self, document_id: str, timeout: int = 20) -> dict:
        """Detail dokumentu/přílohy (GET /document/{id}/). Vrací `data`."""
        endpoint = f"{self.base_url}document/{document_id}/"
        r = requests.get(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout
        )
        return self._over_odpoved(r, f"Načtení dokumentu {document_id}")

    def download_document_body(self, file_id: str, timeout: int = 60) -> bytes:
        """Stáhne binární obsah souboru.

        TO VERIFY: přesná cesta pro „downloading body of file“ není
        zdokumentovaná – použit nejlepší odhad `/file/{id}/download`. Po ověření
        se upraví (případně přes downloadUrl z get_document).
        """
        endpoint = f"{self.base_url}file/{file_id}/download"
        r = requests.get(
            endpoint,
            auth=(self.api_user, self.api_key),
            headers={"X-Instance-Name": self.instance},
            timeout=timeout,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Stažení obsahu souboru {file_id}: HTTP {r.status_code}")
        return r.content
