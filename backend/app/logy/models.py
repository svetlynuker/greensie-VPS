from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


def _ted() -> datetime:
    """Aktuální čas v UTC (ukládáme jako timezone-aware)."""
    return datetime.now(timezone.utc)


class Log(Base):
    """Jeden záznam do provozního / auditního logu.

    Vzniká automaticky pro každý požadavek na backend (viz logy.middleware),
    případně ručně u vybraných akcí (viz logy.audit). Záznamy se NEMAŽOU
    automaticky – uchovávají se, dokud je admin ručně nesmaže (DELETE /logy).

    Uživatel se ukládá jako id + e-mail (kopie), aby řádek zůstal čitelný
    i po smazání uživatele – proto zde záměrně NENÍ cizí klíč na `uzivatele`.
    """

    __tablename__ = "logy"

    id = Column(Integer, primary_key=True, index=True)
    # čas vzniku události (UTC), index kvůli řazení „od nejnovějších“
    cas = Column(DateTime(timezone=True), nullable=False, default=_ted, index=True)
    # kdo akci vyvolal (z přihlašovacího tokenu); u nepřihlášených je prázdné
    uzivatel_id = Column(Integer, nullable=True, index=True)
    uzivatel_email = Column(String, nullable=True)
    # HTTP metoda a cesta požadavku, např. "PUT" a "/matice/bunka"
    metoda = Column(String, nullable=True)
    cesta = Column(String, nullable=True, index=True)
    # výsledný stavový kód (200 = OK, 403 = zakázáno, 500 = chyba serveru…)
    status_kod = Column(Integer, nullable=True)
    # jak dlouho vyřízení trvalo, v milisekundách
    doba_ms = Column(Integer, nullable=True)
    # druh záznamu: "provoz" (čtení), "audit" (změna dat), "chyba" (pád serveru)
    typ = Column(String, nullable=False, default="provoz", index=True)
    # čitelný český popis akce (např. „Editace buňky matice“); nemusí být vyplněn
    popis = Column(String, nullable=True)
    # detail chyby (traceback) – jen u typu "chyba"
    detail = Column(Text, nullable=True)
    # IP adresa klienta (pokud ji lze zjistit)
    ip = Column(String, nullable=True)


# Horní meze délky ukládaných textů. Chrání DB před obřími řádky (např. když by
# někdo poslal víceMB text do pole, které se dostane do logu) – viz audit apod.
MAX_POPIS = 500
MAX_CESTA = 1000
MAX_EMAIL = 320  # nejdelší platný e-mail dle RFC
MAX_DETAIL = 20000
MAX_IP = 100
MAX_METODA = 10


def orez(hodnota, max_delka: int):
    """Ořízne text na maximální délku (None nechá být)."""
    if hodnota is None:
        return None
    s = str(hodnota)
    return s if len(s) <= max_delka else s[:max_delka] + "…"


def vytvor_zaznam(**pole) -> "Log":
    """Vytvoří `Log` s bezpečně oříznutými textovými poli.

    Jediné místo, které skládá záznam – používá ho middleware i ruční audit,
    takže délkové meze platí pro všechny zápisy stejně.
    """
    return Log(
        uzivatel_id=pole.get("uzivatel_id"),
        uzivatel_email=orez(pole.get("uzivatel_email"), MAX_EMAIL),
        metoda=orez(pole.get("metoda"), MAX_METODA),
        cesta=orez(pole.get("cesta"), MAX_CESTA),
        status_kod=pole.get("status_kod"),
        doba_ms=pole.get("doba_ms"),
        typ=pole.get("typ", "provoz"),
        popis=orez(pole.get("popis"), MAX_POPIS),
        detail=orez(pole.get("detail"), MAX_DETAIL),
        ip=orez(pole.get("ip"), MAX_IP),
    )
