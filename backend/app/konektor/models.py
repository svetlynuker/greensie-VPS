"""Datové modely konektoru RAYNET CRM ↔ Google Drive.

Ve F1 (skeleton) používáme jen dvě tabulky:
- `konektor_nastaveni` – jednořádková konfigurace (id=1), vzor viz
  matice.NastaveniSynchronizace. Tajemství (Raynet API klíč, Google
  service-account JSON) se ukládají ŠIFROVANĚ (viz konektor.crypto) a nikdy
  se nevrací do frontendu.
- `konektor_log` – provozní/chybový log konektoru (oddělený od obecné tabulky
  `logy`, protože jde o jinou doménu – běh synchronizace, ne HTTP requesty).

Provozní tabulky pro vlastní synchronizaci (mapování složek/souborů, fronta,
Drive push kanály) přibudou až ve fázích F2/F3, kdy se začnou používat.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base

# výchozí šablona podsložek klienta (potvrdí/upraví se v UI, kap. 4 specu)
VYCHOZI_PODSLOZKY = "01_Nabídky,02_Smlouvy,03_Faktury,04_Ostatní"
# výchozí base URL Raynet API pro české instance (viz INVENTORY, ověření API)
VYCHOZI_RAYNET_URL = "https://app.raynet.cz/api/v2/"


def _ted() -> datetime:
    """Aktuální čas v UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class KonektorNastaveni(Base):
    """Globální nastavení konektoru (jeden řádek, id=1).

    Rozděleno na: přístupy (Raynet, Google – tajemství šifrovaně), chování
    synchronizace a informativní stav posledního běhu.
    """

    __tablename__ = "konektor_nastaveni"

    id = Column(Integer, primary_key=True)

    # ---- Raynet přístupy ----
    raynet_instance = Column(String, nullable=False, default="", server_default="")
    raynet_api_user = Column(String, nullable=False, default="", server_default="")
    raynet_base_url = Column(String, nullable=False, default=VYCHOZI_RAYNET_URL, server_default=VYCHOZI_RAYNET_URL)
    # kód vlastního pole u company, kam se zapíše odkaz na Drive složku (TO VERIFY)
    raynet_company_drive_field = Column(String, nullable=False, default="", server_default="")
    # Raynet API klíč – ŠIFROVANĚ (Fernet), prázdné = nenastaveno
    raynet_api_key_enc = Column(Text, nullable=False, default="", server_default="")

    # ---- Google přístupy (Workspace + Shared Drive, service account) ----
    google_shared_drive_id = Column(String, nullable=False, default="", server_default="")
    # e-mail uživatele k impersonaci přes domain-wide delegation (volitelné)
    google_subject_email = Column(String, nullable=False, default="", server_default="")
    # service-account JSON – ŠIFROVANĚ (Fernet), prázdné = nenastaveno
    google_sa_json_enc = Column(Text, nullable=False, default="", server_default="")

    # ---- Chování synchronizace ----
    sync_model = Column(String, nullable=False, default="links", server_default="links")  # links | mirror
    template_subfolders = Column(Text, nullable=False, default=VYCHOZI_PODSLOZKY, server_default=VYCHOZI_PODSLOZKY)
    delete_policy = Column(String, nullable=False, default="trash_reconcile", server_default="trash_reconcile")
    fr3_plne_zrcadleni = Column(Boolean, nullable=False, default=True, server_default="true")
    auto_zapnuto = Column(Boolean, nullable=False, default=False, server_default="false")
    reconcile_interval_min = Column(Integer, nullable=False, default=15, server_default="15")
    log_level = Column(String, nullable=False, default="info", server_default="info")  # debug|info|warn|error

    # ---- Informativní stav posledního běhu ----
    posledni_beh = Column(DateTime(timezone=True), nullable=True)
    posledni_vysledek = Column(Text, nullable=False, default="", server_default="")


class KonektorLog(Base):
    """Jeden řádek provozního/chybového logu konektoru.

    Odděleno od obecné tabulky `logy` (ta loguje HTTP requesty). Sem píše
    vlastní logika konektoru: webhooky, testy spojení, běhy synchronizace.
    Logy se NEMAŽOU automaticky – čistí je uživatel z UI.
    Do `zprava`/`kontext` se NIKDY nesmí dostat tajemství ani obsah dokumentů.
    """

    __tablename__ = "konektor_log"

    id = Column(Integer, primary_key=True, index=True)
    cas = Column(DateTime(timezone=True), nullable=False, default=_ted, index=True)
    # úroveň: debug | info | warn | error
    uroven = Column(String, nullable=False, default="info", index=True)
    # krátký kód události, např. "webhook_raynet", "test_spojeni", "sync_slozka"
    udalost = Column(String, nullable=True, index=True)
    # čitelný český popis
    zprava = Column(Text, nullable=False, default="", server_default="")
    # strukturovaný kontext bez tajemství (id záznamů, počty, hlavičky…)
    kontext = Column(JSONB, nullable=True)


# Horní meze délky textů (ochrana DB před obřími řádky).
MAX_ZPRAVA = 4000
MAX_UDALOST = 100


def orez(hodnota, max_delka: int):
    """Ořízne text na maximální délku (None nechá být)."""
    if hodnota is None:
        return None
    s = str(hodnota)
    return s if len(s) <= max_delka else s[:max_delka] + "…"
