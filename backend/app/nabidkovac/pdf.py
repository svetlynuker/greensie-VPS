"""Nabídka pro zákazníka jako PDF: vyrobit, uložit, propsat na Disk.

Tok je záměrně rozdělený na dvě části:

1. **Vyrobit a uložit (hned, v požadavku).** Prohlížeč pošle hotovou podobu
   papíru, Chromium z ní udělá PDF (`pdf_render`, vlastní proces) a soubor se
   uloží k nabídce. Obchodník ho tím okamžikem má a může ho otevřít.
2. **Propsat na Disk (na pozadí).** Nahrání do složky nabídky jde do fronty
   konektoru. Kdyby to viselo v požadavku, čekal by uživatel na Google — a když
   složka nabídky ještě neexistuje, i na kopii celého vzoru (desítky volání).

Kdyby se to spojilo do jednoho kroku, každé „Uložit do PDF" by trvalo desítky
sekund a při chybě Disku by uživatel nedostal ani PDF, které se povedlo.
"""

import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.nabidkovac import soubory
from app.nabidkovac.models import GenerovanaNabidkaPdf, Nabidka

# app/nabidkovac/pdf.py -> app/nabidkovac -> app -> backend
_KOREN_BACKENDU = Path(__file__).resolve().parents[2]

# Vykreslení jedné nabídky trvá jednotky sekund. Minuta a půl je strop pro
# případ, že Chromium zatuhne — bez něj by zůstal viset proces i požadavek.
TIMEOUT_S = 90

# Papír je text, mm souřadnice a obrázky v data: URI. 40 MB je přes deset
# stránek s fotkami; víc znamená, že něco není v pořádku, a nemá cenu tím
# krmit Chromium.
MAX_HTML_BAJTU = 40 * 1024 * 1024

# Chromium si vezme stovky MB paměti. Na VPS se 4 GB, kde běží i Postgres,
# nesmí vykreslovat dvě nabídky naráz — druhá počká.
_zamek = threading.Lock()

MIME = "application/pdf"
MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def mime_formatu(format: str | None) -> str:
    """MIME podle formátu záznamu. Prázdno = řádek z doby před Excelem, tedy PDF."""
    return MIME_XLSX if format == "xlsx" else MIME


class PdfNedostupne(RuntimeError):
    """Chromium na serveru chybí nebo vykreslení spadlo.

    Vlastní typ, aby endpoint mohl odpovědět srozumitelně („na serveru chybí
    prohlížeč pro tisk") místo obecné pětistovky, se kterou nikdo nic neudělá.
    """


def vyrob(html: str) -> bytes:
    """HTML papíru → bajty PDF. Vykresluje podproces (viz `pdf_render`)."""
    data = html.encode("utf-8")
    if len(data) > MAX_HTML_BAJTU:
        raise PdfNedostupne(
            f"Podklad pro PDF je moc velký ({len(data) // (1024 * 1024)} MB). "
            "Zmenši vložené obrázky."
        )
    with _zamek:
        try:
            beh = subprocess.run(
                [sys.executable, "-m", "app.nabidkovac.pdf_render"],
                input=data,
                capture_output=True,
                cwd=str(_KOREN_BACKENDU),
                timeout=TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            raise PdfNedostupne(
                "Vykreslení PDF trvalo přes minutu a půl a bylo přerušeno. "
                "Zkus to znovu, nebo nabídku rozdělit na méně stránek."
            ) from None

    if beh.returncode != 0 or not beh.stdout:
        chyba = (beh.stderr or b"").decode("utf-8", "replace").strip()
        # Typický případ na neaktualizovaném serveru: chybí playwright nebo
        # stažený Chromium. Poznáme to a řekneme, co s tím.
        if "playwright" in chyba.lower() or "executable doesn" in chyba.lower():
            raise PdfNedostupne(
                "Na serveru chybí prohlížeč pro tisk PDF (playwright + Chromium). "
                "Spusť deploy/update.sh, ten ho doinstaluje."
            )
        raise PdfNedostupne(f"Vykreslení PDF spadlo: {chyba[-400:] or 'bez výstupu'}")
    return beh.stdout


def nazev_souboru(
    nabidka: Nabidka,
    typ_reseni: str,
    kdy: datetime | None = None,
    pripona: str = ".pdf",
) -> str:
    """Jméno souboru: `NAB-26-0007_ppa_2026-08-03.pdf`.

    Číslo nabídky je vepředu, protože podle něj se soubor hledá na Disku i ve
    schránce zákazníka. Datum na konci proto, že jedna nabídka se přepočítá
    a vytiskne víckrát a starší verze musí zůstat rozeznatelné.

    Excel k téže nabídce dostane **stejné jméno, jen jinou příponu** – tak si je
    obchodník na Disku spáruje na první pohled.
    """
    kdy = kdy or datetime.now()
    zaklad = nabidka.cislo or f"nabidka-{nabidka.id}"
    return f"{zaklad}_{typ_reseni}_{kdy:%Y-%m-%d}{pripona}"


def uloz(
    db: Session,
    nabidka: Nabidka,
    typ_reseni: str,
    data: bytes,
    user_id: int | None,
    format: str = "pdf",
    kdy: datetime | None = None,
) -> GenerovanaNabidkaPdf:
    """Uloží vygenerovaný soubor k nabídce a zařadí jeho nahrání na Disk do fronty.

    `kdy` se předává, aby PDF a Excel z jednoho kliknutí dostaly stejné datum
    v názvu i těsně před půlnocí.
    """
    from app.konektor import fronta

    nazev = nazev_souboru(nabidka, typ_reseni, kdy, f".{format}")
    cesta = soubory.uloz_soubor(nabidka.id, nazev, data)
    zaznam = GenerovanaNabidkaPdf(
        nabidka_id=nabidka.id,
        typ_reseni=typ_reseni,
        format=format,
        nazev=nazev,
        soubor_cesta=cesta,
        vygeneroval_user_id=user_id,
    )
    db.add(zaznam)
    db.commit()
    db.refresh(zaznam)

    # Nahrání na Disk je práce pro worker (viz docstring modulu). Chyba tady
    # nesmí sebrat PDF, které už je uložené.
    try:
        fronta.zarad(db, "nabidka_pdf_na_disk", {"pdf_id": zaznam.id})
    except Exception:  # noqa: BLE001
        db.rollback()
    return zaznam


def nahraj_na_disk(db: Session, pdf_id: int) -> dict:
    """Nahraje uložené PDF do složky nabídky na Disku (úloha z fronty).

    Složku nabídky si v případě potřeby nechá vytvořit — proto to běží tady
    a ne v požadavku: u nabídky bez složky je to kopie celého vzoru.
    """
    from app.crm.models import ObchodniPripad, Zakaznik
    from app.konektor import crm_slozky

    zaznam = db.get(GenerovanaNabidkaPdf, pdf_id)
    if zaznam is None or zaznam.disk_file_id:
        return {"skip": True}  # smazané PDF nebo už nahrané
    nabidka = db.get(Nabidka, zaznam.nabidka_id)
    if nabidka is None or not nabidka.obchodni_pripad_id:
        # Nabídka z nabídkovače bez obchodního případu nemá na Disku své místo.
        return {"skip": True}
    pripad = db.get(ObchodniPripad, nabidka.obchodni_pripad_id)
    if pripad is None:
        return {"skip": True}
    zakaznik = db.get(Zakaznik, pripad.zakaznik_id)
    if zakaznik is None:
        return {"skip": True}

    cesta = soubory.UPLOAD_DIR / zaznam.soubor_cesta
    if not cesta.exists():
        return {"skip": True}

    ef = crm_slozky.zajisti_slozku_nabidky(db, nabidka, pripad, zakaznik)
    soubor = crm_slozky.nahraj(
        db, ef, None, zaznam.nazev or cesta.name, cesta.read_bytes(), mime_formatu(zaznam.format)
    )
    zaznam.disk_file_id = soubor.get("id") or ""
    zaznam.disk_url = soubor.get("url") or ""
    db.commit()
    return {"disk_file_id": zaznam.disk_file_id, "disk_url": zaznam.disk_url}
