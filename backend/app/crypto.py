"""Symetrické šifrování tajemství appky (Fernet) – společné pro všechny moduly.

Vzniklo vytažením `konektor/crypto.py` na úroveň appky: e-mailový klient
potřebuje ukládat **hesla ke schránkám lidí**, což je totéž tajemství jako
Raynetí API klíč, jen citlivější. Dvě různé implementace šifrování v jedné
appce jsou past – jedna se opraví, druhá ne.

Klíč se bere z `.env` v tomto pořadí:

  1. `APP_ENC_KEY`       – nový, společný pro celou appku,
  2. `KONEKTOR_ENC_KEY`  – původní klíč konektoru.

Fallback na konektorový klíč je schválně: na produkci už existuje a funguje,
takže e-mail nemusí čekat na nový záznam v `.env`. Až se `APP_ENC_KEY` doplní,
musí to být **tentýž klíč**, jinak se dřív zašifrovaná tajemství přestanou
dešifrovat (dešifrování nespadne, jen vrátí prázdno – viz `desifruj`).

Design UI se dědí z konektoru: tajemství jsou „write-only". Z frontendu se
dají zadat nebo přepsat, ale nikdy se nevracejí zpět – Out schéma vrací jen
příznak „nastaveno". Heslo od schránky, které by šlo z appky přečíst, by byl
únik cizí osobní pošty, ne jen konfigurace.
"""

import os

from cryptography.fernet import Fernet, InvalidToken

# Pořadí = priorita. Nový klíč vyhrává, konektorový je záloha.
PROMENNE_KLICE = ("APP_ENC_KEY", "KONEKTOR_ENC_KEY")

_fernet: Fernet | None = None
_klic_zdroj: str = ""


def _ziskej_fernet() -> Fernet | None:
    global _fernet, _klic_zdroj
    if _fernet is not None:
        return _fernet
    for promenna in PROMENNE_KLICE:
        klic = os.environ.get(promenna, "").strip()
        if not klic:
            continue
        try:
            _fernet = Fernet(klic.encode())
        except (ValueError, TypeError):
            # Neplatný klíč zkusíme přeskočit – druhá proměnná může být v pořádku.
            continue
        _klic_zdroj = promenna
        return _fernet
    return None


def klic_dostupny() -> bool:
    """Je nastaven a platný šifrovací klíč? (Bez něj se tajemství nedají uložit.)"""
    return _ziskej_fernet() is not None


def zdroj_klice() -> str:
    """Ze které proměnné klíč pochází – pro diagnostiku v nastavení."""
    _ziskej_fernet()
    return _klic_zdroj


def sifruj(text: str) -> str:
    """Zašifruje řetězec. Prázdný vstup vrací prázdný (= „nenastaveno")."""
    if not text:
        return ""
    f = _ziskej_fernet()
    if f is None:
        raise RuntimeError(
            "Chybí nebo je neplatný šifrovací klíč v .env "
            f"({' nebo '.join(PROMENNE_KLICE)}) – nelze uložit tajemství."
        )
    return f.encrypt(text.encode()).decode()


def desifruj(sifra: str) -> str:
    """Dešifruje řetězec. Prázdný vstup i selhání vrací prázdný řetězec.

    Selhání se **nevyhazuje jako výjimka** schválně: chybějící klíč nebo
    tajemství zašifrované jiným klíčem nesmí shodit stránku nastavení – jinak
    by se to nedalo ani opravit. Volající pozná problém tím, že dostane
    prázdno, a ohlásí „schránka potřebuje znovu zadat heslo".
    """
    if not sifra:
        return ""
    f = _ziskej_fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(sifra.encode()).decode()
    except (InvalidToken, ValueError):
        return ""


def _zapomen_klic() -> None:
    """Jen pro testy – zahodí načtený klíč, aby se přečetl znovu z prostředí."""
    global _fernet, _klic_zdroj
    _fernet = None
    _klic_zdroj = ""
