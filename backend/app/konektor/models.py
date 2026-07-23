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

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.database import Base

# výchozí podsložky POD OBCHODNÍM PŘÍPADEM (potvrzeno se zadavatelem)
VYCHOZI_PODSLOZKY = "01_Nabídky,02_Objednávky,03_Fotky,04_Dokumenty"
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
    # kódy vlastních polí (typ odkaz/URL) pro proklik na složku na Disku.
    # U obchodního případu jsou dvě pole – zapisují se obě stejným odkazem.
    raynet_company_drive_field = Column(String, nullable=False, default="", server_default="")
    raynet_deal_drive_field = Column(String, nullable=False, default="", server_default="")
    raynet_deal_drive_field2 = Column(String, nullable=False, default="", server_default="")
    raynet_offer_drive_field = Column(String, nullable=False, default="", server_default="")
    raynet_order_drive_field = Column(String, nullable=False, default="", server_default="")
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


class KonektorClientFolderMap(Base):
    """Mapování klient (Raynet company) ↔ kořenová složka klienta na Disku.

    Datový model dle specu kap. 7 (client_folder_map), prefix `konektor_`.
    """

    __tablename__ = "konektor_client_folder_map"

    raynet_company_id = Column(BigInteger, primary_key=True)
    drive_folder_id = Column(String, nullable=False)
    drive_folder_url = Column(String, nullable=False, default="", server_default="")
    client_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_ted)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_ted, onupdate=_ted)


class KonektorEntityFolder(Base):
    """Mapování Raynet záznam → jeho složka na Disku, pro všechny úrovně
    hierarchie (company / deal / offer / order).

    Nahrazuje původní client_folder_map (jen company) – hierarchie zákazník →
    obchodní případ → nabídka/objednávka potřebuje mapovat všechny úrovně.
    """

    __tablename__ = "konektor_entity_folder"
    __table_args__ = (
        UniqueConstraint("entity", "entity_id", name="uq_konektor_entity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    entity = Column(String, nullable=False)  # 'company' | 'deal' | 'offer' | 'order'
    entity_id = Column(BigInteger, nullable=False)
    drive_folder_id = Column(String, nullable=False, index=True)
    drive_folder_url = Column(String, nullable=False, default="", server_default="")
    name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_ted)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_ted, onupdate=_ted)


class KonektorFileMap(Base):
    """Mapování dokument (Raynet) ↔ soubor na Disku (spec kap. 7, file_map)."""

    __tablename__ = "konektor_file_map"

    id = Column(Integer, primary_key=True, index=True)
    raynet_company_id = Column(BigInteger, nullable=True, index=True)
    raynet_document_id = Column(String, nullable=True, unique=True)  # ID odkaz. dokumentu (TO VERIFY tvar)
    drive_file_id = Column(String, nullable=False, unique=True)
    drive_file_url = Column(String, nullable=False, default="", server_default="")
    file_name = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)  # jen pro Model B (zrcadlení)
    last_synced_source = Column(String, nullable=True)  # 'drive' | 'raynet' (echo suppression)
    state = Column(String, nullable=False, default="active", server_default="active")  # active|trashed
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_ted, onupdate=_ted)


class KonektorDriveChannel(Base):
    """Google Drive push kanál (kvůli obnově; spec kap. 7, drive_channels)."""

    __tablename__ = "konektor_drive_channels"

    channel_id = Column(String, primary_key=True)
    resource_id = Column(String, nullable=False)
    expiration = Column(DateTime(timezone=True), nullable=False)
    page_token = Column(String, nullable=True)


class KonektorDriveChangeState(Base):
    """Uložený page token pro changes.list (spec kap. 7, jeden řádek id=1)."""

    __tablename__ = "konektor_drive_change_state"

    id = Column(Integer, primary_key=True)
    page_token = Column(String, nullable=False, default="", server_default="")


class KonektorTreeMirror(Base):
    """Zrcadlení stromu Disku do modulu Dokumenty v Raynetu (FR3, Flow C).

    Mapuje položku na Disku (složku i soubor) na její protějšek v Raynet
    Dokumentech. Odděleno od file_map (FR2a k company) – FR3 je celkový obraz
    obsahu Disku ve stromu. `drive_id` unikátní → brání duplicitám.
    """

    __tablename__ = "konektor_tree_mirror"

    drive_id = Column(String, primary_key=True)
    raynet_id = Column(String, nullable=False)
    je_slozka = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_ted, onupdate=_ted)


class KonektorProcessedEvent(Base):
    """Idempotence příchozích událostí (spec kap. 7, processed_events).

    Klíč = hash zdroje+typu+id+revize; duplicitní doručení se zahodí.
    """

    __tablename__ = "konektor_processed_events"

    event_key = Column(String, primary_key=True)
    processed_at = Column(DateTime(timezone=True), nullable=False, default=_ted)


class KonektorJobQueue(Base):
    """Fronta úloh v DB (fallback bez Redis, spec kap. 7 + S9).

    Webhook rychle zařadí úlohu a vrátí 200; worker ji zpracuje idempotentně
    s retry/backoff (respektuje limit 4 souběžných spojení Raynetu).
    """

    __tablename__ = "konektor_job_queue"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False)  # např. "novy_klient"
    payload = Column(JSONB, nullable=False)
    run_after = Column(DateTime(timezone=True), nullable=False, default=_ted, index=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String, nullable=False, default="pending", index=True)  # pending|done|failed
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_ted)


# Horní meze délky textů (ochrana DB před obřími řádky).
MAX_ZPRAVA = 4000
MAX_UDALOST = 100


def orez(hodnota, max_delka: int):
    """Ořízne text na maximální délku (None nechá být)."""
    if hodnota is None:
        return None
    s = str(hodnota)
    return s if len(s) <= max_delka else s[:max_delka] + "…"
