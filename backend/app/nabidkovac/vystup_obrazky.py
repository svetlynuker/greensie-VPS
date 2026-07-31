"""Obrázky vložené do nabídkového výstupu – fotky realizací, schémata, loga.

Vlastní adresář, ne `nabidka_soubory`: tam jsou vstupní podklady zakázky
(faktury, křivky spotřeby), kdežto tohle jsou grafické prvky vysázené do
nabídky. Oddělené složky znamenají, že se dají zálohovat a čistit zvlášť
a že se omylem nesmaže obrázek, na kterém stojí hotová nabídka.

Adresář se bere z env `VYSTUP_OBRAZKY_DIR`, jinak spadne na
<kořen repa>/vystup_obrazky. Struktura: <UPLOAD_DIR>/<nabidka_id>/<uuid>_<nazev>.

Do DB se neukládá nic – cesta k obrázku je součástí konfigurace výstupu
(prvek druhu `obrazek`), takže obrázek žije a umírá s rozvržením nabídky.
"""

import os
import re
import uuid
from pathlib import Path

# app/nabidkovac/vystup_obrazky.py -> app/nabidkovac -> app -> backend -> kořen repa
_KOREN_REPA = Path(__file__).resolve().parents[3]

UPLOAD_DIR = Path(
    os.environ.get("VYSTUP_OBRAZKY_DIR", str(_KOREN_REPA / "vystup_obrazky"))
)

# Jen rastr a SVG. Žádné PDF ani archivy – tohle se vkládá do <img> a musí to
# jít vytisknout.
POVOLENE_PRIPONY = {".png", ".jpg", ".jpeg", ".webp", ".svg"}

MIME_PODLE_PRIPONY = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}

# Obrázek do nabídky nepotřebuje být větší – 10 MB je fotka z mobilu s rezervou.
MAX_BAJTU = 10 * 1024 * 1024

# Cesta v konfiguraci musí vypadat přesně takhle: <čísla>/<uuid>_<jméno>.
# Kontroluje se při ukládání i při výdeji, aby přes ni nešlo sáhnout jinam.
_TVAR_CESTY = re.compile(r"^\d+/[A-Za-z0-9._-]+$")


def je_povolena(nazev: str) -> bool:
    return os.path.splitext(nazev or "")[1].lower() in POVOLENE_PRIPONY


def mime_typ(nazev: str) -> str:
    return MIME_PODLE_PRIPONY.get(
        os.path.splitext(nazev or "")[1].lower(), "application/octet-stream"
    )


def _bezpecny_nazev(nazev: str) -> str:
    """Ořízne cestu a nahradí nebezpečné znaky, ať nelze vylézt z UPLOAD_DIR."""
    zaklad = os.path.basename(nazev or "obrazek")
    zaklad = re.sub(r"[^A-Za-z0-9._-]+", "_", zaklad).strip("._") or "obrazek"
    return zaklad[:120]


def uloz(nabidka_id: int, puvodni_nazev: str, obsah: bytes) -> str:
    """Uloží obrázek a vrátí cestu relativní k UPLOAD_DIR (jde do konfigurace)."""
    cilova_slozka = UPLOAD_DIR / str(nabidka_id)
    cilova_slozka.mkdir(parents=True, exist_ok=True)
    nazev = f"{uuid.uuid4().hex}_{_bezpecny_nazev(puvodni_nazev)}"
    (cilova_slozka / nazev).write_bytes(obsah)
    return f"{nabidka_id}/{nazev}"


def cesta_k_obrazku(rel_cesta: str) -> Path:
    """Absolutní cesta k obrázku.

    Hlídá tvar i to, že výsledek nevede mimo úložiště. Cesta chodí z klienta
    (je součástí konfigurace, kterou posílá prohlížeč), takže se jí nesmí
    věřit ani trochu – `../../etc/passwd` musí skončit chybou, ne souborem.
    """
    if not rel_cesta or not _TVAR_CESTY.match(rel_cesta):
        raise ValueError("Neplatná cesta k obrázku")
    koren = UPLOAD_DIR.resolve()
    cil = (koren / rel_cesta).resolve()
    if not cil.is_relative_to(koren):
        raise ValueError("Cesta k obrázku vede mimo úložiště")
    return cil


def smaz(rel_cesta: str) -> None:
    """Best-effort smazání (chybu ignorujeme – obrázek mohl zmizet dřív)."""
    try:
        cesta_k_obrazku(rel_cesta).unlink(missing_ok=True)
    except (OSError, ValueError):
        pass
