"""Odesílání e-mailů přes SMTP (výchozí = Seznam.cz, schránka automat@greensie.cz).

Konfigurace přes .env (žádné údaje v kódu):
  SMTP_HOST        (výchozí smtp.seznam.cz)
  SMTP_PORT        (výchozí 465, SSL)
  SMTP_USER        (výchozí automat@greensie.cz)
  SMTP_HESLO       (heslo schránky – BEZ něj se e-maily neposílají)
  SMTP_ODESILATEL  (výchozí = SMTP_USER)
  APP_URL          (adresa appky pro přihlašovací odkaz)
"""

import os
import smtplib
import ssl
from email.message import EmailMessage

VYCHOZI_APP_URL = "https://167-235-254-188.sslip.io"


def app_url() -> str:
    return os.environ.get("APP_URL", VYCHOZI_APP_URL).rstrip("/")


def _cfg() -> dict:
    user = os.environ.get("SMTP_USER", "automat@greensie.cz")
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.seznam.cz"),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "user": user,
        "heslo": os.environ.get("SMTP_HESLO", ""),
        "odesilatel": os.environ.get("SMTP_ODESILATEL", user),
    }


def email_nastaven() -> bool:
    """True, pokud je v .env vyplněné heslo schránky (jinak se e-maily neposílají)."""
    return bool(_cfg()["heslo"])


def posli_email(komu: str, predmet: str, telo: str) -> None:
    c = _cfg()
    if not c["heslo"]:
        raise RuntimeError("SMTP není nastaven (chybí SMTP_HESLO v .env).")
    msg = EmailMessage()
    msg["Subject"] = predmet
    msg["From"] = c["odesilatel"]
    msg["To"] = komu
    msg.set_content(telo)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(c["host"], c["port"], context=ctx, timeout=20) as s:
        s.login(c["user"], c["heslo"])
        s.send_message(msg)


def email_pristupu(jmeno: str, heslo: str) -> tuple[str, str]:
    """Sestaví předmět a tělo e-mailu s přihlašovacími údaji."""
    predmet = "Přístup do aplikace Greensie"
    telo = (
        f"Dobrý den, {jmeno},\n\n"
        "byl vám vytvořen účet v aplikaci Greensie.\n\n"
        f"Přihlašovací odkaz: {app_url()}\n"
        f"Jednorázové heslo: {heslo}\n\n"
        "Po prvním přihlášení budete vyzváni ke změně hesla.\n\n"
        "Tento e-mail je odeslán automaticky, neodpovídejte na něj."
    )
    return predmet, telo
