"""Odesílání pošty z **vlastní** schránky člověka (SMTP) + kopie do Odeslaných.

Jak se to liší od `app/mailer.py`: ten posílá z **firemní** schránky
`automat@greensie.cz` a slouží systémovým zprávám (přístupy, notifikace). Tady
píše konkrétní člověk ze své adresy, takže zákazník vidí odesílatele, se kterým
opravdu mluví, a odpověď mu přijde do jeho schránky, ne do automatu.

---- Tři věci, které se musí stát dohromady ---------------------------------
1. **Odeslat přes SMTP.** Port 587 + STARTTLS (Hetzner blokuje 465 i 25).
2. **Uložit kopii do Odeslaných na IMAPu.** Bez tohohle kroku by odeslaná pošta
   chyběla v mobilu i na webu Seznamu a člověk by netušil, co z appky odešlo.
   Selhání kopie ale **není chyba odeslání** – zpráva už je u příjemce a tvrdit
   „neodesláno" by bylo horší než chybějící kopie.
3. **Zapsat do CRM jako aktivitu.** Kvůli tomu je e-mail v CRM: na kartě firmy
   má být vidět, co jí odešlo, aniž by to někdo přepisoval.

---- Vláknování odpovědí ---------------------------------------------------
Odpověď nese `In-Reply-To` a `References` původní zprávy. Bez nich poštovní
klienti příjemce odpověď nespojí s původní zprávou a konverzace se rozsype na
samostatné maily.
"""

import html as html_modul
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import adresar, email_pool, email_sync
from app.crm.email_imap import ImapChyba
from app.crm.models import (
    CrmAktivita,
    CrmEmailUcet,
    CrmEmailZprava,
)

# Strop na jednu zprávu včetně příloh. Seznam odmítá zprávy nad ~20 MB, takže
# je čestnější to říct dopředu než nechat člověka čekat na chybu serveru.
MAX_ZPRAVA_B = 18 * 1024 * 1024
MAX_PRILOH = 20


class SmtpChyba(Exception):
    """Chyba odesílání – text je určený uživateli."""


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def _odesilatel(ucet: CrmEmailUcet, user: User) -> str:
    """`Jan Novák <jan@greensie.cz>`. Jméno z účtu, jinak z appky."""
    jmeno = (ucet.jmeno_odesilatele or "").strip() or (user.jmeno or "").strip()
    return formataddr((jmeno, ucet.adresa)) if jmeno else ucet.adresa


def _adresy_ze_textu(surove) -> list[str]:
    """Rozseká `a@b.cz, c@d.cz` (nebo seznam) na platné adresy."""
    if isinstance(surove, str):
        kusy = surove.replace(";", ",").split(",")
    else:
        kusy = list(surove or [])
    vysledek: list[str] = []
    for kus in kusy:
        adresa = str(kus or "").strip()
        # Povolíme i „Jméno <adresa>" – vytáhneme jen tu adresu v ostrých.
        if "<" in adresa and ">" in adresa:
            adresa = adresa[adresa.rfind("<") + 1 : adresa.rfind(">")].strip()
        if "@" in adresa and adresa not in vysledek:
            vysledek.append(adresa)
    return vysledek


def sestav_zpravu(
    ucet: CrmEmailUcet,
    user: User,
    komu: list[str],
    predmet: str,
    telo: str,
    kopie: list[str] | None = None,
    skryta_kopie: list[str] | None = None,
    odpoved_na: CrmEmailZprava | None = None,
    prilohy: list[dict] | None = None,
    profil=None,
) -> EmailMessage:
    """Postaví MIME zprávu.

    `profil` je `UzivatelProfil` odesílatele. Když je vyplněný a podpis zapnutý,
    zpráva odejde jako **multipart/alternative** s HTML podpisem (a textovou
    variantou téhož). Bez profilu se použije prostý textový podpis schránky.
    """
    msg = EmailMessage()
    msg["From"] = _odesilatel(ucet, user)
    msg["To"] = ", ".join(komu)
    if kopie:
        msg["Cc"] = ", ".join(kopie)
    # Bcc se do hlaviček NEDÁVÁ – jen do obálky při odeslání. Kdyby tam bylo,
    # skrytá kopie by skrytá nebyla (a to je celý její smysl).
    msg["Subject"] = predmet
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=ucet.adresa.rsplit("@", 1)[-1])

    if odpoved_na is not None and odpoved_na.message_id:
        msg["In-Reply-To"] = odpoved_na.message_id
        # `References` má nést celé vlákno; máme jen předchůdce, což klientům
        # na spojení odpovědi stačí.
        predchozi = (odpoved_na.in_reply_to or "").strip()
        msg["References"] = (
            f"{predchozi} {odpoved_na.message_id}".strip() if predchozi else odpoved_na.message_id
        )

    # ---- tělo: text vždy, HTML když je podpis z profilu ---------------------
    # Zpráva odchází jako multipart/alternative (text + HTML). Textová část
    # není formalita: klient, který HTML nezobrazí, by jinak dostal prázdno.
    html_podpis = ""
    text_podpis = ""
    if profil is not None and getattr(profil, "podpis_zapnuty", False):
        from app.crm import email_podpis

        html_podpis = email_podpis.sestav_html(profil, ucet.adresa)
        text_podpis = email_podpis.sestav_text(profil, ucet.adresa)

    if html_podpis:
        # HTML podpis z profilu vyhrává nad prostým textovým podpisem schránky.
        # Přidávat oba by znamenalo dva podpisy pod sebou.
        msg.set_content(_spoj_text(telo, text_podpis))
        msg.add_alternative(_html_telo(telo, html_podpis), subtype="html")
    else:
        msg.set_content(_pridej_podpis(telo, ucet.podpis))

    for p in prilohy or []:
        obsah = p.get("obsah") or b""
        if not obsah:
            continue
        mime = (p.get("mime") or "application/octet-stream").split("/", 1)
        hlavni = mime[0] or "application"
        podtyp = mime[1] if len(mime) > 1 else "octet-stream"
        msg.add_attachment(
            obsah, maintype=hlavni, subtype=podtyp, filename=p.get("nazev") or "priloha"
        )
    return msg


def _spoj_text(telo: str, podpis: str) -> str:
    """Textová část: napsaný text + textová podoba podpisu, oddělené `--`."""
    text = (telo or "").rstrip()
    if not podpis:
        return text + "\n"
    return f"{text}\n\n--\n{podpis}\n"


def _html_telo(telo: str, podpis_html: str) -> str:
    """HTML část: napsaný text (escapovaný) + HTML podpis.

    Text se **escapuje** a teprve pak se zalomení řádků převedou na `<br>`.
    Kdyby se vkládal syrový, stačilo by napsat do e-mailu `<b>` a rozbil by
    zbytek zprávy — a hůř, dalo by se tudy do odchozí pošty propašovat cizí HTML.
    """
    bezpecny = html_modul.escape(telo or "", quote=False).replace("\r\n", "\n")
    odstavce = bezpecny.replace("\n", "<br>")
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        f'color:rgb(0,0,0);line-height:1.5;">{odstavce}</div>'
        f'<div style="margin-top:18px;">{podpis_html}</div>'
    )


def _pridej_podpis(telo: str, podpis: str) -> str:
    """Přidá podpis, pokud ho člověk už nemá v textu (šablony ho mívají)."""
    text = (telo or "").rstrip()
    podpis = (podpis or "").strip()
    if not podpis:
        return text + "\n"
    # Hrubá, ale spolehlivá kontrola: první řádek podpisu už v textu je.
    prvni_radek = podpis.splitlines()[0].strip()
    if prvni_radek and prvni_radek in text:
        return text + "\n"
    return f"{text}\n\n--\n{podpis}\n"


def odesli(
    db: Session,
    ucet: CrmEmailUcet,
    user: User,
    komu,
    predmet: str,
    telo: str,
    kopie=None,
    skryta_kopie=None,
    odpoved_na_id: int | None = None,
    prilohy: list[dict] | None = None,
    zakaznik_id: int | None = None,
    pripad_id: int | None = None,
) -> dict:
    """Odešle zprávu, uloží kopii do Odeslaných a zapíše aktivitu do CRM.

    Vrací `{"ok", "aktivita_id", "kopie_ulozena", "poznamka"}`. `poznamka` je
    neprázdná, když se něco nepodstatného nepovedlo (typicky kopie do Odeslaných)
    – uživatel to má vidět, ale nemá to vypadat jako selhání odeslání.
    """
    komu_a = _adresy_ze_textu(komu)
    kopie_a = _adresy_ze_textu(kopie)
    skryta_a = _adresy_ze_textu(skryta_kopie)
    if not komu_a:
        raise SmtpChyba("Vyplň aspoň jednoho příjemce s platnou e-mailovou adresou.")
    predmet = (predmet or "").strip()
    if not predmet:
        raise SmtpChyba("E-mail musí mít předmět.")
    if not (telo or "").strip():
        raise SmtpChyba("E-mail nemůže být prázdný.")
    if len(prilohy or []) > MAX_PRILOH:
        raise SmtpChyba(f"Najednou jde poslat nejvýš {MAX_PRILOH} příloh.")

    heslo = email_sync.heslo_uctu(ucet)
    if not heslo:
        raise SmtpChyba(
            "Ke schránce není uložené heslo – zadej ho v Nastavení schránky, "
            "jinak se nedá odesílat."
        )

    odpoved_na = None
    if odpoved_na_id:
        odpoved_na = (
            db.query(CrmEmailZprava)
            .filter(CrmEmailZprava.id == odpoved_na_id, CrmEmailZprava.ucet_id == ucet.id)
            .first()
        )

    # Profil odesílatele = zdroj HTML podpisu. Načítá se tady, ne ve
    # `sestav_zpravu`, aby ta zůstala bez dotazů do DB a šla testovat samotná.
    from app.auth.models import UzivatelProfil

    profil = (
        db.query(UzivatelProfil).filter(UzivatelProfil.user_id == user.id).first()
    )

    msg = sestav_zpravu(
        ucet, user, komu_a, predmet, telo,
        kopie=kopie_a, skryta_kopie=skryta_a, odpoved_na=odpoved_na, prilohy=prilohy,
        profil=profil,
    )
    surova = msg.as_bytes()
    if len(surova) > MAX_ZPRAVA_B:
        raise SmtpChyba(
            f"Zpráva má {len(surova) // (1024 * 1024)} MB včetně příloh, "
            "což poštovní server odmítne. Pošli velké soubory odkazem na Disk."
        )

    _posli_smtp(ucet, heslo, msg, komu_a + kopie_a + skryta_a)

    poznamky: list[str] = []

    # ---- kopie do Odeslaných -------------------------------------------------
    # Selhání tady NENÍ selhání odeslání: zpráva už je u příjemce.
    kopie_ulozena = False
    odeslane = email_sync.slozka_druhu(db, ucet.id, "odeslane")
    if odeslane is None:
        poznamky.append("Schránka nemá složku Odeslané, kopie se neuložila.")
    else:
        try:
            with email_pool.pujc(ucet, heslo) as s:
                s.uloz_zpravu(odeslane.imap_nazev, surova, precteno=True)
            kopie_ulozena = True
        except ImapChyba as e:
            poznamky.append(f"Zpráva odešla, ale kopie do Odeslaných se neuložila: {e}")

    # ---- zápis do CRM --------------------------------------------------------
    if zakaznik_id is None and pripad_id is None:
        vazba = adresar.dohledaj_podle_adresy(db, komu_a[0])
        zakaznik_id = vazba["zakaznik_id"]
        pripad_id = vazba["pripad_id"]

    aktivita_id = _zapis_aktivitu(
        db, user, predmet, telo, komu_a, zakaznik_id, pripad_id
    )
    db.commit()

    return {
        "ok": True,
        "aktivita_id": aktivita_id,
        "kopie_ulozena": kopie_ulozena,
        "zakaznik_id": zakaznik_id,
        "pripad_id": pripad_id,
        "poznamka": " ".join(poznamky),
    }


def _posli_smtp(ucet: CrmEmailUcet, heslo: str, msg: EmailMessage, obalka: list[str]) -> None:
    """Vlastní odeslání. Port 465 = implicitní SSL, jinak STARTTLS.

    `obalka` obsahuje i skryté kopie – ty jsou v obálce, ne v hlavičkách.
    """
    ctx = ssl.create_default_context()
    host, port = ucet.smtp_host, int(ucet.smtp_port or 587)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
                s.login(ucet.adresa, heslo)
                s.send_message(msg, from_addr=ucet.adresa, to_addrs=obalka)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.ehlo()
                s.starttls(context=ctx)
                s.ehlo()
                s.login(ucet.adresa, heslo)
                s.send_message(msg, from_addr=ucet.adresa, to_addrs=obalka)
    except smtplib.SMTPAuthenticationError:
        raise SmtpChyba(
            "Poštovní server odmítl přihlášení. Zkontroluj heslo ke schránce "
            "v Nastavení schránky (u Seznamu se přihlašuje celou adresou)."
        )
    except smtplib.SMTPRecipientsRefused as e:
        adresy = ", ".join(str(a) for a in (e.recipients or {}))
        raise SmtpChyba(f"Server odmítl příjemce: {adresy}")
    except (TimeoutError, OSError) as e:
        # Nejčastější reálná příčina na tomhle serveru: port 465, který Hetzner
        # blokuje. Stojí za to to rovnou napovědět, jinak se to hledá dlouho.
        napoveda = (
            " Zkus port 587 v Nastavení schránky → Pokročilé – port 465 je na tomhle "
            "serveru blokovaný." if port == 465 else ""
        )
        raise SmtpChyba(f"Nepodařilo se spojit s {host}:{port} – {e}.{napoveda}")
    except smtplib.SMTPException as e:
        raise SmtpChyba(f"Poštovní server zprávu nepřijal: {e}")


def _zapis_aktivitu(
    db: Session,
    user: User,
    predmet: str,
    telo: str,
    komu: list[str],
    zakaznik_id: int | None,
    pripad_id: int | None,
) -> int | None:
    """Zapíše odeslání jako aktivitu k firmě nebo případu.

    Případ vyhrává nad firmou: konkrétnější záznam je užitečnější. Když není
    ani jedno, aktivita se nezakládá – aktivita bez záznamu by nikde nebyla
    vidět a jen by zabírala.
    """
    if pripad_id:
        entita, zaznam_id = "op", pripad_id
    elif zakaznik_id:
        entita, zaznam_id = "zakaznik", zakaznik_id
    else:
        return None

    a = CrmAktivita(
        entita=entita,
        zaznam_id=zaznam_id,
        druh="email",
        nazev=f"Odesláno: {predmet}"[:255],
        text=f"Komu: {', '.join(komu)}\n\n{telo}",
        stav="realizovano",
        vlastnik_user_id=user.id,
        vytvoril_user_id=user.id,
    )
    db.add(a)
    db.flush()
    return a.id


# ---- příprava odpovědi a přeposlání -----------------------------------------
def _citace(zprava: CrmEmailZprava) -> str:
    """Původní zpráva odsazená `> ` – to, co dělá každý poštovní klient."""
    zdroj = zprava.telo_text or ""
    if not zdroj and zprava.telo_html:
        from app.crm.email_imap import vypis_z_tela

        zdroj = vypis_z_tela("", zprava.telo_html)
    kdy = zprava.datum_at.strftime("%d.%m.%Y %H:%M") if zprava.datum_at else ""
    kdo = zprava.od_jmeno or zprava.od_adresa
    hlavicka = f"{kdy} {kdo} <{zprava.od_adresa}> napsal(a):"
    citovane = "\n".join(f"> {r}" for r in zdroj.splitlines())
    return f"\n\n{hlavicka}\n{citovane}\n"


def priprav_odpoved(zprava: CrmEmailZprava, vsem: bool, moje_adresa: str) -> dict:
    """Předvyplnění okna „Odpovědět" / „Odpovědět všem".

    `Reply-To` má přednost před odesílatelem – tak si to odesílatel přál.
    Vlastní adresa se z příjemců vyhazuje: odpovídat sám sobě nechce nikdo.
    """
    komu = [(zprava.odpovedet_na or zprava.od_adresa or "").strip()]
    kopie: list[str] = []
    if vsem:
        moje = (moje_adresa or "").lower()
        for a in list(zprava.komu or []) + list(zprava.kopie or []):
            adresa = (a.get("adresa") or "").strip().lower() if isinstance(a, dict) else ""
            if adresa and adresa != moje and adresa not in komu and adresa not in kopie:
                kopie.append(adresa)

    predmet = zprava.predmet or ""
    if not predmet.lower().startswith("re:"):
        predmet = f"Re: {predmet}"
    return {
        "komu": [k for k in komu if k],
        "kopie": kopie,
        "predmet": predmet,
        "telo": _citace(zprava),
        "odpoved_na_id": zprava.id,
        "zakaznik_id": zprava.zakaznik_id,
        "pripad_id": zprava.pripad_id,
    }


def priprav_preposlani(zprava: CrmEmailZprava) -> dict:
    """Předvyplnění okna „Přeposlat" – bez příjemce, s celým původním textem.

    Přílohy se **nepřenášejí**: musely by se stáhnout z IMAPu a poslat znovu,
    což u desetimegové zprávy znamená minutu čekání v okně. Kdo je potřebuje,
    stáhne si je a připojí – a v textu je na to upozornění.
    """
    predmet = zprava.predmet or ""
    if not predmet.lower().startswith(("fwd:", "fw:")):
        predmet = f"Fwd: {predmet}"
    mel_prilohy = bool(zprava.ma_prilohy)
    hlavicka = (
        "\n\n---------- Přeposlaná zpráva ----------\n"
        f"Od: {zprava.od_jmeno or ''} <{zprava.od_adresa}>\n"
        f"Datum: {zprava.datum_at.strftime('%d.%m.%Y %H:%M') if zprava.datum_at else ''}\n"
        f"Předmět: {zprava.predmet or ''}\n"
        f"Komu: {', '.join((a.get('adresa') or '') for a in (zprava.komu or []) if isinstance(a, dict))}\n"
    )
    telo = zprava.telo_text or ""
    if not telo and zprava.telo_html:
        from app.crm.email_imap import vypis_z_tela

        telo = vypis_z_tela("", zprava.telo_html)
    pozn = (
        "\n[Pozor: původní zpráva měla přílohy. Přeposláním se nepřenesou – "
        "stáhni si je a připoj ručně.]\n" if mel_prilohy else ""
    )
    return {
        "komu": [],
        "kopie": [],
        "predmet": predmet,
        "telo": f"{hlavicka}{pozn}\n{telo}\n",
        "odpoved_na_id": None,
        "zakaznik_id": None,
        "pripad_id": None,
    }
