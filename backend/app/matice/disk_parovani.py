"""Párování projektů (z Freela) na jejich složku dokumentů na Google Disku.

Most vede přes číslo obchodního případu (OP), které je unikátní a je součástí
názvu projektu (konvence „OP-26-0223 – něco"):

    Freelo projekt  →  číslo OP z názvu  →  složka OP na Disku (z konektoru)
                    →  podsložka „6. projekt"  →  odkaz uložený na projekt

Složku OP nehledáme na Disku naslepo – konektor už pro každý obchodní případ
(Raynet `deal`) drží její ID a URL v `konektor_entity_folder`. Stačí najít
záznam, jehož název začíná stejným číslem OP, a v té složce dohledat podsložku
„6. projekt" (jediné volání Drive API na projekt).

Ruční odkaz (`projekt.disk_rucni == True`) párování NIKDY nepřepíše.
"""

import re

from sqlalchemy.orm import Session

from app.konektor import crypto
from app.konektor.google_klient import FOLDER_MIME, DriveClient
from app.konektor.models import KonektorEntityFolder, KonektorNastaveni
from app.matice.models import Projekt

# Číslo OP v názvu, tolerantně: „OP-26-0223", „op-26-99"… (velikost písmen nehraje
# roli, počet číslic za druhou pomlčkou je proměnný). Bereme první výskyt.
OP_REGEX = re.compile(r"OP-\d{2,}-\d+", re.IGNORECASE)

# Název podsložky pod složkou OP, na kterou vede proklik. Hledá se
# case-insensitive, takže „6. Projekt" i „6. projekt" projde.
NAZEV_PODSLOZKY_PROJEKTY = "6. projekt"


def vytahni_op(nazev: str) -> str | None:
    """Vytáhne číslo OP z názvu projektu (velkými písmeny), nebo None."""
    m = OP_REGEX.search(nazev or "")
    return m.group(0).upper() if m else None


def _drive_z_nastaveni(n: KonektorNastaveni) -> DriveClient | None:
    """Sestaví jen Drive klienta z nastavení konektoru (Raynet nepotřebujeme).

    Vrací None, když chybí service-account JSON nebo ID Shared Drive.
    """
    sa_json = crypto.desifruj(n.google_sa_json_enc)
    if not sa_json or not n.google_shared_drive_id:
        return None
    return DriveClient(sa_json, n.google_subject_email or None)


def _najdi_ef_op(db: Session, op_cislo: str) -> KonektorEntityFolder | None:
    """Najde složku obchodního případu podle čísla OP.

    Filtrujeme prefixem v DB (`name ILIKE 'OP-26-0223%'`) a pak přesně ověříme
    číslo vytažené z názvu, aby prefix nechytil delší číslo (OP-26-0223 vs.
    OP-26-02234). Číslo OP je unikátní → očekáváme max. jeden zásah.
    """
    kandidati = (
        db.query(KonektorEntityFolder)
        .filter(
            KonektorEntityFolder.entity == "deal",
            KonektorEntityFolder.name.ilike(f"{op_cislo}%"),
        )
        .all()
    )
    for ef in kandidati:
        if vytahni_op(ef.name) == op_cislo:
            return ef
    return None


def _najdi_podslozku_ci(drive: DriveClient, parent_id: str, nazev: str) -> dict | None:
    """Case-insensitive hledání podsložky daného názvu (ořezané mezery)."""
    cil = (nazev or "").strip().lower()
    for f in drive.list_children(parent_id):
        if f.get("mimeType") == FOLDER_MIME and (f.get("name") or "").strip().lower() == cil:
            return f
    return None


def sparuj_projekt(db: Session, projekt: Projekt, drive: DriveClient) -> bool:
    """Zkusí projektu nastavit `disk_url` (odkaz na „6. projekt" pod jeho OP).

    Vrací True, když se odkaz nově nastavil. Ruční odkaz nepřepisuje. Volající
    zajišťuje commit. Jednotlivé kroky, které selžou (chybí OP v názvu, OP není
    v konektoru, chybí podsložka), vrací False a projekt zůstane nespárovaný –
    příští běh to zkusí znovu.
    """
    if projekt.disk_rucni:
        return False
    op = vytahni_op(projekt.nazev)
    if not op:
        return False
    ef = _najdi_ef_op(db, op)
    if ef is None:
        return False
    # zapamatujeme spárovaný obchodní případ i bez nalezené podsložky
    projekt.raynet_deal_id = ef.entity_id
    pod = _najdi_podslozku_ci(drive, ef.drive_folder_id, NAZEV_PODSLOZKY_PROJEKTY)
    if pod is None:
        return False
    url = pod.get("webViewLink") or ""
    if not url:
        return False
    projekt.disk_url = url
    return True


def sparuj_vsechny(db: Session, *, jen_nesparovane: bool = True) -> dict:
    """Spáruje projekty s Diskem hromadně. Vrací souhrn pro UI.

    - `jen_nesparovane=True` (default): jen projekty bez odkazu – levné, vhodné
      po každé synchronizaci z Freela.
    - `jen_nesparovane=False`: přepočítá i projekty, které už odkaz mají
      (kromě ručních) – pro tlačítko „přepárovat" po přesunu složek.

    Ruční odkazy (`disk_rucni`) se vždy přeskočí. Chyba jednotlivého projektu
    dávku neshodí. Klíč `chyba` je vyplněný jen, když párování vůbec nemohlo
    proběhnout (konektor/Drive nenastaven).
    """
    n = db.get(KonektorNastaveni, 1)
    if n is None:
        return {"zpracovano": 0, "nalezeno": 0, "chyba": "Konektor není nastaven."}
    drive = _drive_z_nastaveni(n)
    if drive is None:
        return {
            "zpracovano": 0,
            "nalezeno": 0,
            "chyba": "Google Drive není v konektoru nastaven (service account / Shared Drive).",
        }

    q = db.query(Projekt).filter(Projekt.disk_rucni.is_(False))
    if jen_nesparovane:
        q = q.filter((Projekt.disk_url == "") | (Projekt.disk_url.is_(None)))
    projekty = q.all()

    nalezeno = 0
    for p in projekty:
        try:
            if sparuj_projekt(db, p, drive):
                nalezeno += 1
        except Exception:  # noqa: BLE001 - jeden projekt nesmí shodit celou dávku
            # chyba z Drive volání je HTTP (ne DB) → session zůstává v pořádku,
            # rozpracované změny ostatních projektů zachováme a jen přeskočíme
            continue
    db.commit()
    return {"zpracovano": len(projekty), "nalezeno": nalezeno, "chyba": None}
