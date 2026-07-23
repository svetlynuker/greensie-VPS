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
