"""Tenká fasáda nad RAYNET CRM REST API.

Auth (ověřeno v dokumentaci, viz INVENTORY sekce 4): HTTP Basic
(uživatel : API klíč) + hlavička `X-Instance-Name`. Base URL dle instance,
u českých typicky `https://app.raynet.cz/api/v2/`.

Ve F1 využíváme jen `test_spojeni()`. Operace pro FR1/FR2/FR3 (company,
document, file/attachment, webhook) přibudou v dalších fázích.
"""

import requests


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
        self, company_id: int, name: str, url_value: str, timeout: int = 20
    ) -> int:
        """Vytvoří v Raynetu odkazový dokument na soubor na Disku. Vrací jeho id.

        TO VERIFY: přesný tvar PUT /document/document/ (pole pro URL a relaci na
        company) není zdokumentovaný. Tělo je nejlepší odhad podle konvencí
        Raynetu; po ověření reálným voláním se upraví.
        """
        endpoint = f"{self.base_url}document/document/"
        telo = {
            "name": name,
            "url": url_value,
            "company": {"id": company_id},
        }
        r = requests.put(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), json=telo, timeout=timeout
        )
        data = self._over_odpoved(r, f"Vytvoření odkazového dokumentu pro company {company_id}")
        return int(data.get("id")) if isinstance(data, dict) and data.get("id") is not None else 0

    def delete_document(self, document_id: str, timeout: int = 20) -> None:
        """Smaže dokument v Raynetu (DELETE /document/{id}/)."""
        endpoint = f"{self.base_url}document/{document_id}/"
        r = requests.delete(
            endpoint, auth=(self.api_user, self.api_key), headers=self._headers(), timeout=timeout
        )
        self._over_odpoved(r, f"Smazání dokumentu {document_id}")
