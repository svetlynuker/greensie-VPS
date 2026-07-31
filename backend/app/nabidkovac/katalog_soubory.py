"""Přílohy položek katalogu produktů – technické listy, fotky, certifikáty.

Stejný princip jako `soubory.py` u nabídek (soubor na disk, v DB jen cesta),
ale vlastní adresář: přílohy katalogu jsou firemní know-how, které přežije
všechny zakázky, kdežto `nabidka_soubory` jsou data konkrétních obchodů.
Oddělené adresáře znamenají, že se dají zálohovat a přenášet zvlášť.

Adresář se bere z env `KATALOG_UPLOAD_DIR`, jinak spadne na
<kořen repa>/katalog_soubory (je v .gitignore). Struktura:
<UPLOAD_DIR>/<technologie_id>/<uuid>_<nazev>.
"""

import os
import re
import uuid
from pathlib import Path

# app/nabidkovac/katalog_soubory.py -> app/nabidkovac -> app -> backend -> kořen repa
_KOREN_REPA = Path(__file__).resolve().parents[3]

UPLOAD_DIR = Path(
    os.environ.get("KATALOG_UPLOAD_DIR", str(_KOREN_REPA / "katalog_soubory"))
)

# Co jde k položce nahrát. Širší než u nabídek – typicky PDF datasheet,
# fotka produktu, občas výkres nebo tabulka s parametry.
POVOLENE_PRIPONY = {
    ".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".dwg", ".zip",
}

# Druh přílohy odhadnutý z přípony – uživatel ho pak může přepnout.
# Obrázek = foto dokumentace, PDF = technický list, zbytek = jiný.
_DRUH_PODLE_PRIPONY = {
    ".png": "foto", ".jpg": "foto", ".jpeg": "foto", ".webp": "foto", ".gif": "foto",
    ".pdf": "technicky_list",
}

# Obrázky se v prohlížeči zobrazují inline (náhled v kartě položky), ostatní
# se stahují. Bez správného Content-Type by prohlížeč nabízel PDF ke stažení.
MIME_PODLE_PRIPONY = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
}

MAX_BAJTU = 25 * 1024 * 1024  # 25 MB, stejně jako u dokumentů nabídky


def je_povolena(nazev: str) -> bool:
    return os.path.splitext(nazev or "")[1].lower() in POVOLENE_PRIPONY


def odvod_druh(nazev: str) -> str:
    """Druh přílohy podle přípony (fotka / technický list / jiný)."""
    return _DRUH_PODLE_PRIPONY.get(os.path.splitext(nazev or "")[1].lower(), "jiny")


def mime_typ(nazev: str) -> str:
    return MIME_PODLE_PRIPONY.get(
        os.path.splitext(nazev or "")[1].lower(), "application/octet-stream"
    )


def _bezpecny_nazev(nazev: str) -> str:
    """Ořízne cestu a nahradí nebezpečné znaky, ať nelze vylézt z UPLOAD_DIR."""
    zaklad = os.path.basename(nazev or "soubor")
    zaklad = re.sub(r"[^A-Za-z0-9._-]+", "_", zaklad).strip("._") or "soubor"
    return zaklad[:120]


def uloz_soubor(technologie_id: int, puvodni_nazev: str, obsah: bytes) -> str:
    """Uloží obsah a vrátí cestu relativní k UPLOAD_DIR (do DB)."""
    cilova_slozka = UPLOAD_DIR / str(technologie_id)
    cilova_slozka.mkdir(parents=True, exist_ok=True)
    nazev = f"{uuid.uuid4().hex}_{_bezpecny_nazev(puvodni_nazev)}"
    (cilova_slozka / nazev).write_bytes(obsah)
    return f"{technologie_id}/{nazev}"


def cesta_k_souboru(rel_cesta: str) -> Path:
    """Absolutní cesta k příloze. Hlídá, že nevede mimo UPLOAD_DIR.

    `rel_cesta` jde z DB, takže by měla být v pořádku – kontrola je pojistka
    pro případ, že by se do DB dostala cizí hodnota (např. špatnou migrací).
    """
    cil = (UPLOAD_DIR / rel_cesta).resolve()
    if not str(cil).startswith(str(UPLOAD_DIR.resolve())):
        raise ValueError("Cesta k příloze vede mimo úložiště katalogu")
    return cil


def smaz_soubor(rel_cesta: str) -> None:
    """Best-effort smazání souboru z disku (chybu ignorujeme)."""
    try:
        (UPLOAD_DIR / rel_cesta).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
