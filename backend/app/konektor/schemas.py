"""Pydantic schémata konektoru.

Zásada tajemství: `...Out` (GET) NIKDY nevrací hodnoty tajemství, jen příznak
`*_nastaven`. `...Vstup` (PUT) přijímá tajemství volitelně – None/prázdné
znamená „neměnit stávající hodnotu“.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class KonektorNastaveniOut(BaseModel):
    # Raynet (bez klíče – jen příznak, zda je nastaven)
    raynet_instance: str = ""
    raynet_api_user: str = ""
    raynet_base_url: str = ""
    raynet_company_drive_field: str = ""
    raynet_deal_drive_field: str = ""
    raynet_deal_drive_field2: str = ""
    raynet_offer_drive_field: str = ""
    raynet_order_drive_field: str = ""
    raynet_webhook_token: str = ""
    raynet_api_key_nastaven: bool = False
    # Google (bez JSON – jen příznak)
    google_shared_drive_id: str = ""
    google_root_folder_id: str = ""
    google_subject_email: str = ""
    google_sa_json_nastaven: bool = False
    # chování
    sync_model: str = "links"
    template_subfolders: str = ""
    delete_policy: str = "trash_reconcile"
    fr3_plne_zrcadleni: bool = True
    auto_zapnuto: bool = False
    reconcile_interval_min: int = 15
    log_level: str = "info"
    # stav
    posledni_beh: Optional[datetime] = None
    posledni_vysledek: str = ""


class KonektorNastaveniVstup(BaseModel):
    raynet_instance: str = ""
    raynet_api_user: str = ""
    raynet_base_url: str = ""
    raynet_company_drive_field: str = ""
    raynet_deal_drive_field: str = ""
    raynet_deal_drive_field2: str = ""
    raynet_offer_drive_field: str = ""
    raynet_order_drive_field: str = ""
    raynet_webhook_token: str = ""
    google_shared_drive_id: str = ""
    google_root_folder_id: str = ""
    google_subject_email: str = ""
    sync_model: str = "links"
    template_subfolders: str = ""
    delete_policy: str = "trash_reconcile"
    fr3_plne_zrcadleni: bool = True
    auto_zapnuto: bool = False
    reconcile_interval_min: int = 15
    log_level: str = "info"
    # tajemství – None/"" = neměnit stávající hodnotu v DB
    raynet_api_key: Optional[str] = None
    google_sa_json: Optional[str] = None


class SluzbaStav(BaseModel):
    ok: bool
    zprava: str


class TestSpojeniVysledek(BaseModel):
    raynet: SluzbaStav
    google: SluzbaStav


class KonektorLogOut(BaseModel):
    id: int
    cas: datetime
    uroven: str
    udalost: Optional[str] = None
    zprava: str
    kontext: Optional[dict] = None

    class Config:
        from_attributes = True
