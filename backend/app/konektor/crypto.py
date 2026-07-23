"""Symetrické šifrování tajemství konektoru (Fernet).

Tajemství (Raynet API klíč, Google service-account JSON) se do DB ukládají
zašifrovaná. Šifrovací klíč `KONEKTOR_ENC_KEY` žije jen v `.env` (chmod 600,
mimo git) – ne v databázi. Ztráta klíče = nutnost tajemství znovu zadat.

Design UI: tajemství jsou „write-only“ – z frontendu se dají zadat/přepsat,
ale nikdy se nevrací zpět (Out schéma vrací jen příznak „nastaveno“).
"""

import os

from cryptography.fernet import Fernet, InvalidToken

_fernet: Fernet | None = None


def klic_dostupny() -> bool:
    """Je nastaven a platný šifrovací klíč?"""
    return _ziskej_fernet() is not None


def _ziskej_fernet() -> Fernet | None:
    global _fernet
    if _fernet is not None:
        return _fernet
    klic = os.environ.get("KONEKTOR_ENC_KEY", "").strip()
    if not klic:
        return None
    try:
        _fernet = Fernet(klic.encode())
    except (ValueError, TypeError):
        return None
    return _fernet


def sifruj(text: str) -> str:
    """Zašifruje řetězec. Prázdný vstup vrací prázdný (= „nenastaveno“)."""
    if not text:
        return ""
    f = _ziskej_fernet()
    if f is None:
        raise RuntimeError(
            "Chybí nebo je neplatný KONEKTOR_ENC_KEY v .env – nelze uložit tajemství."
        )
    return f.encrypt(text.encode()).decode()


def desifruj(sifra: str) -> str:
    """Dešifruje řetězec. Prázdný vstup i selhání vrací prázdný řetězec."""
    if not sifra:
        return ""
    f = _ziskej_fernet()
    if f is None:
        return ""
    try:
        return f.decrypt(sifra.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
