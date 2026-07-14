"""Uložení nahraných souborů na disk (kap. 5 SPEC – jen uložení, bez zpracování).

Adresář se bere z env NABIDKOVAC_UPLOAD_DIR, jinak spadne na
<kořen repa>/nabidka_soubory (je v .gitignore). Soubory se ukládají do
podsložky per nabídka: <UPLOAD_DIR>/<nabidka_id>/<uuid>_<nazev>.
"""

import os
import re
import uuid
from pathlib import Path

# app/nabidkovac/soubory.py -> app/nabidkovac -> app -> backend -> kořen repa
_KOREN_REPA = Path(__file__).resolve().parents[3]

UPLOAD_DIR = Path(
    os.environ.get("NABIDKOVAC_UPLOAD_DIR", str(_KOREN_REPA / "nabidka_soubory"))
)

# Povolené přípony podle typu dokumentu (kap. 5 SPEC: PDF faktura, CSV spotřeba).
POVOLENE_PRIPONY = {
    "faktura_pdf": {".pdf"},
    "spotreba_csv": {".csv", ".xlsx", ".xls"},
    "jiny": {".pdf", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"},
}

MAX_BAJTU = 25 * 1024 * 1024  # 25 MB


def _bezpecny_nazev(nazev: str) -> str:
    """Ořízne cestu a nahradí nebezpečné znaky, ať nelze vylézt z UPLOAD_DIR."""
    zaklad = os.path.basename(nazev or "soubor")
    zaklad = re.sub(r"[^A-Za-z0-9._-]+", "_", zaklad).strip("._") or "soubor"
    return zaklad[:120]


def uloz_soubor(nabidka_id: int, puvodni_nazev: str, obsah: bytes) -> str:
    """Uloží obsah a vrátí cestu relativní k UPLOAD_DIR (do DB)."""
    cilova_slozka = UPLOAD_DIR / str(nabidka_id)
    cilova_slozka.mkdir(parents=True, exist_ok=True)
    nazev = f"{uuid.uuid4().hex}_{_bezpecny_nazev(puvodni_nazev)}"
    (cilova_slozka / nazev).write_bytes(obsah)
    return f"{nabidka_id}/{nazev}"


def smaz_soubor(rel_cesta: str) -> None:
    """Best-effort smazání souboru z disku (chybu ignorujeme)."""
    try:
        (UPLOAD_DIR / rel_cesta).unlink(missing_ok=True)
    except OSError:
        pass
