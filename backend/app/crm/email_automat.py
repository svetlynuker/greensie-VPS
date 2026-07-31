"""Automatika příchozí pošty: pravidla, OOO oznámení, přeposílání.

ROZHODNUTÍ DANA (31. 7. 2026): **appka to dělá sama.** Seznam Email nemá API
ani IMAP příkaz, kterým by šlo OOO nebo přeposílání nastavit zdálky, takže se
nezrcadlí cizí nastavení – je to vlastní funkce. Důsledek, který musí být vidět
v UI: **funguje to jen když běží worker** (`greensie-email.service`).

Volá se **výhradně z workeru**, ne z web procesu. Odeslání OOO odpovědi trvá
sekundy a nesmí zdržovat HTTP požadavek uživatele.

---- Tři pojistky, bez kterých by to byla katastrofa ------------------------
Autoresponder je nejsnadnější způsob, jak si vyrobit nekonečnou smyčku a zaplavit
někomu schránku. Proto:

1. **Neodpovídá se robotům.** Zprávy s `Auto-Submitted`, `Precedence: bulk`,
   `List-Id` a spol. jsou označené `automat=True` už při stažení
   (`email_imap._je_automat`) a automatika je přeskočí. Tohle přikazuje RFC 3834.
2. **Jedné adrese nejvýš jednou za `ODSTUP_OOO_H`.** Drží to tabulka
   `crm_email_auto_odpovedi`. Když mají dva lidé OOO současně, padne to na tomhle.
3. **Stará pošta se neřeší.** Zprávy z prvního stažení schránky mají
   `zpracovano_at` vyplněné rovnou (viz `email_sync`), a navíc se tady přeskočí
   všechno starší než `MAX_STARI_H`. Bez toho by zapnutí OOO rozeslalo odpovědi
   na tři sta měsíc starých zpráv.

Nikdy si sám neodpovídá (vlastní adresa se přeskakuje) a odpověď posílá
s hlavičkou `Auto-Submitted: auto-replied`, aby ji protistrana poznala.

---- Pravidla vs. automatizace CRM -----------------------------------------
Tohle vědomě NEsdílí model s `crm/automatizace.py`. Ta pracuje se záznamy
a stavy pipeline; tady jde o hlavičky zprávy. Jeden model pro obojí by znamenal
podmínky, které u poloviny spouštěčů nedávají smysl.
"""

import logging
import smtplib
import ssl
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from sqlalchemy.orm import Session

from app.crm import email_pool, email_sync
from app.crm.email_imap import ImapChyba
from app.crm.models import (
    CrmEmailAutoOdpoved,
    CrmEmailPravidlo,
    CrmEmailSlozka,
    CrmEmailUcet,
    CrmEmailZprava,
)

_log = logging.getLogger("greensie.email.automat")

# Jedné adrese nejvýš jedna OOO odpověď za tuhle dobu. 24 h je zavedené chování
# poštovních serverů, ne vlastní vynález.
ODSTUP_OOO_H = 24
# Co je starší, automatika neřeší – pojistka proti lavině po zapnutí funkce.
MAX_STARI_H = 48
# Kolik zpráv se zpracuje v jednom cyklu workeru.
DAVKA = 50

POLE_ZPRAVY = ("od", "komu", "predmet", "telo", "ma_prilohy")
OPERATORY = ("obsahuje", "neobsahuje", "je", "zacina", "konci", "ano", "ne")
TYPY_AKCI = ("presun", "oznacit_precteno", "oznacit", "preposlat", "prirad")


def _ted() -> datetime:
    return datetime.now(timezone.utc)


# ---- vyhodnocení podmínek ----------------------------------------------------
def _hodnota_pole(zprava: CrmEmailZprava, pole: str) -> str:
    if pole == "od":
        return f"{zprava.od_jmeno} {zprava.od_adresa}".strip().lower()
    if pole == "komu":
        adresy = [
            (a.get("adresa") or "")
            for a in list(zprava.komu or []) + list(zprava.kopie or [])
            if isinstance(a, dict)
        ]
        return " ".join(adresy).lower()
    if pole == "predmet":
        return (zprava.predmet or "").lower()
    if pole == "telo":
        # Náhled, ne celé tělo: to by se muselo stahovat pro každou zprávu
        # a u pravidel typu „obsahuje objednávka" náhled bohatě stačí.
        return (zprava.vypis or "").lower()
    if pole == "ma_prilohy":
        return "ano" if zprava.ma_prilohy else "ne"
    return ""


def _plati_podminka(zprava: CrmEmailZprava, podminka: dict) -> bool:
    pole = str(podminka.get("pole") or "").strip()
    operator = str(podminka.get("operator") or "obsahuje").strip()
    hodnota = str(podminka.get("hodnota") or "").strip().lower()
    if pole not in POLE_ZPRAVY:
        return False

    skutecnost = _hodnota_pole(zprava, pole)

    if pole == "ma_prilohy":
        # U příznaku je „hodnota" zbytečná – operátor sám říká ano/ne.
        return skutecnost == ("ano" if operator in ("ano", "obsahuje", "je") else "ne")

    if not hodnota:
        return False
    if operator == "obsahuje":
        return hodnota in skutecnost
    if operator == "neobsahuje":
        return hodnota not in skutecnost
    if operator == "je":
        return skutecnost.strip() == hodnota
    if operator == "zacina":
        return skutecnost.strip().startswith(hodnota)
    if operator == "konci":
        return skutecnost.strip().endswith(hodnota)
    return False


def pravidlo_sedi(zprava: CrmEmailZprava, pravidlo: CrmEmailPravidlo) -> bool:
    """Platí pravidlo na tuhle zprávu?

    Pravidlo **bez podmínek nesedí na nic**. Prázdné podmínky by jinak znamenaly
    „platí vždy" a nedopsané pravidlo by začalo přehazovat celou schránku.
    """
    podminky = list(pravidlo.podminky or [])
    if not podminky:
        return False
    vysledky = [_plati_podminka(zprava, p) for p in podminky if isinstance(p, dict)]
    if not vysledky:
        return False
    return all(vysledky) if (pravidlo.spojka or "a") == "a" else any(vysledky)


# ---- provedení akcí ----------------------------------------------------------
def _proved_akce(
    db: Session, ucet: CrmEmailUcet, zprava: CrmEmailZprava, pravidlo: CrmEmailPravidlo
) -> tuple[list[str], bool]:
    """Vykoná akce pravidla. Vrací (co se stalo, zpráva už není ve složce)."""
    popis: list[str] = []
    zmizela = False

    for akce in list(pravidlo.akce or []):
        if not isinstance(akce, dict):
            continue
        typ = str(akce.get("typ") or "").strip()

        if typ == "oznacit_precteno":
            if not zprava.precteno:
                email_sync.nastav_precteno(db, zprava, True)
            popis.append("označeno jako přečtené")

        elif typ == "oznacit":
            if not zprava.oznaceno:
                email_sync.nastav_oznaceno(db, zprava, True)
            popis.append("označeno vlaječkou")

        elif typ == "prirad":
            zakaznik_id = akce.get("zakaznik_id")
            if zakaznik_id:
                zprava.zakaznik_id = int(zakaznik_id)
                popis.append("přiřazeno k firmě")

        elif typ == "preposlat":
            komu = str(akce.get("komu") or "").strip()
            if komu:
                posli_preposlani(db, ucet, zprava, komu)
                popis.append(f"přeposláno na {komu}")

        elif typ == "presun":
            cil_id = akce.get("slozka_id")
            cil = (
                db.query(CrmEmailSlozka)
                .filter(CrmEmailSlozka.id == int(cil_id), CrmEmailSlozka.ucet_id == ucet.id)
                .first()
                if cil_id
                else None
            )
            if cil is not None and cil.id != zprava.slozka_id:
                # Přesun musí být POSLEDNÍ: zpráva se z cache smaže (v cílové
                # složce dostane nové UID), takže další akce by sahaly na
                # neexistující řádek.
                nazev = cil.nazev
                email_sync.presun_zpravu(db, zprava, cil)
                popis.append(f"přesunuto do „{nazev}“")
                zmizela = True
                break

    return popis, zmizela


def _serad_akce(pravidlo: CrmEmailPravidlo) -> list[dict]:
    """Přesun až nakonec – po něm zpráva v cache není a nic dalšího už nejde."""
    akce = [a for a in (pravidlo.akce or []) if isinstance(a, dict)]
    return sorted(akce, key=lambda a: 1 if str(a.get("typ")) == "presun" else 0)


# ---- OOO a přeposílání -------------------------------------------------------
def _ooo_plati_dnes(ucet: CrmEmailUcet, dnes: date) -> bool:
    if not ucet.ooo_zapnuto:
        return False
    if ucet.ooo_od and dnes < ucet.ooo_od:
        return False
    if ucet.ooo_do and dnes > ucet.ooo_do:
        return False
    return True


def _uz_odpovezeno(db: Session, ucet: CrmEmailUcet, adresa: str) -> bool:
    zaznam = (
        db.query(CrmEmailAutoOdpoved)
        .filter(CrmEmailAutoOdpoved.ucet_id == ucet.id, CrmEmailAutoOdpoved.adresa == adresa)
        .first()
    )
    if zaznam is None:
        return False
    odeslano = zaznam.odeslano_at
    if odeslano is not None and odeslano.tzinfo is None:
        odeslano = odeslano.replace(tzinfo=timezone.utc)
    return odeslano is not None and (_ted() - odeslano) < timedelta(hours=ODSTUP_OOO_H)


def _zapis_odpoved(db: Session, ucet: CrmEmailUcet, adresa: str) -> None:
    zaznam = (
        db.query(CrmEmailAutoOdpoved)
        .filter(CrmEmailAutoOdpoved.ucet_id == ucet.id, CrmEmailAutoOdpoved.adresa == adresa)
        .first()
    )
    if zaznam is None:
        db.add(CrmEmailAutoOdpoved(ucet_id=ucet.id, adresa=adresa, odeslano_at=_ted()))
    else:
        zaznam.odeslano_at = _ted()


def smi_ooo_odpovedet(
    db: Session, ucet: CrmEmailUcet, zprava: CrmEmailZprava, dnes: date | None = None
) -> tuple[bool, str]:
    """Smí na tuhle zprávu odejít OOO odpověď? Vrací (ano/ne, důvod).

    Vytažené zvlášť, aby se to dalo testovat bez SMTP – právě tyhle podmínky
    rozhodují o tom, jestli si appka nevyrobí nekonečnou smyčku.
    """
    dnes = dnes or _ted().date()
    if not _ooo_plati_dnes(ucet, dnes):
        return False, "OOO není zapnuté nebo neplatí pro dnešek"
    if zprava.smer != "prichozi":
        return False, "není příchozí"
    if zprava.automat:
        return False, "strojová pošta (robot, newsletter, odraz)"
    adresa = (zprava.od_adresa or "").strip().lower()
    if not adresa:
        return False, "bez odesílatele"
    if adresa == (ucet.adresa or "").strip().lower():
        return False, "zpráva od sebe sama"
    if _uz_odpovezeno(db, ucet, adresa):
        return False, f"téhle adrese už odpověď odešla (do {ODSTUP_OOO_H} h se neopakuje)"
    return True, ""


def posli_ooo(db: Session, ucet: CrmEmailUcet, zprava: CrmEmailZprava) -> bool:
    """Odešle OOO odpověď, pokud smí. Vrací True, když opravdu odešla."""
    smi, _duvod = smi_ooo_odpovedet(db, ucet, zprava)
    if not smi:
        return False

    predmet = (ucet.ooo_predmet or "").strip() or "Automatická odpověď"
    if zprava.predmet:
        predmet = f"{predmet}: {zprava.predmet}"

    msg = EmailMessage()
    msg["From"] = _odesilatel(ucet)
    msg["To"] = zprava.od_adresa
    msg["Subject"] = predmet[:255]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=ucet.adresa.rsplit("@", 1)[-1])
    if zprava.message_id:
        msg["In-Reply-To"] = zprava.message_id
        msg["References"] = zprava.message_id
    # Aby protistrana poznala robota a neodpovídala zpátky (RFC 3834).
    msg["Auto-Submitted"] = "auto-replied"
    msg["X-Auto-Response-Suppress"] = "All"
    msg["Precedence"] = "auto_reply"
    msg.set_content((ucet.ooo_text or "").strip() or "Momentálně nejsem k zastižení.")

    _posli(ucet, msg, [zprava.od_adresa])
    _zapis_odpoved(db, ucet, (zprava.od_adresa or "").strip().lower())
    _log.info("OOO odpověď odeslána na %s (schránka %s)", zprava.od_adresa, ucet.adresa)
    return True


def posli_preposlani(
    db: Session, ucet: CrmEmailUcet, zprava: CrmEmailZprava, komu: str
) -> bool:
    """Přepošle zprávu dál. Tělo se kvůli tomu dotáhne z IMAPu.

    Přílohy se nepřenášejí – musely by se stáhnout a poslat znovu, což u velké
    zprávy znamená desítky sekund v cyklu workeru. V textu je na to upozornění.
    """
    cil = (komu or "").strip()
    if "@" not in cil:
        return False
    if cil.lower() == (ucet.adresa or "").strip().lower():
        # Přeposílání sám sobě = nekonečná smyčka. Nikdy.
        _log.warning("Přeposílání na vlastní adresu %s zablokováno.", cil)
        return False
    if zprava.automat:
        # Přeposílat newslettery a odrazy nedoručení nemá smysl a zahltí to cíl.
        return False

    try:
        zprava = email_sync.stahni_telo(db, zprava)
    except ImapChyba:
        db.rollback()

    telo = zprava.telo_text or zprava.vypis or ""
    hlavicka = (
        "---------- Přeposláno automaticky z Greensie ----------\n"
        f"Od: {zprava.od_jmeno or ''} <{zprava.od_adresa}>\n"
        f"Datum: {zprava.datum_at.strftime('%d.%m.%Y %H:%M') if zprava.datum_at else ''}\n"
        f"Předmět: {zprava.predmet or ''}\n"
    )
    pozn = (
        "\n[Původní zpráva měla přílohy. Automatické přeposlání je nepřenáší.]\n"
        if zprava.ma_prilohy
        else ""
    )

    msg = EmailMessage()
    msg["From"] = _odesilatel(ucet)
    msg["To"] = cil
    msg["Subject"] = f"Fwd: {zprava.predmet or '(bez předmětu)'}"[:255]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=ucet.adresa.rsplit("@", 1)[-1])
    # Označit jako strojové – jinak by protistrana s OOO odpověděla zpátky.
    msg["Auto-Submitted"] = "auto-forwarded"
    # Aby odpověď šla původnímu odesílateli, ne do naší schránky.
    if zprava.od_adresa:
        msg["Reply-To"] = zprava.od_adresa
    msg.set_content(f"{hlavicka}{pozn}\n{telo}\n")

    _posli(ucet, msg, [cil])
    _log.info("Zpráva %s přeposlána na %s", zprava.id, cil)
    return True


def _odesilatel(ucet: CrmEmailUcet) -> str:
    jmeno = (ucet.jmeno_odesilatele or "").strip()
    return formataddr((jmeno, ucet.adresa)) if jmeno else ucet.adresa


def _posli(ucet: CrmEmailUcet, msg: EmailMessage, komu: list[str]) -> None:
    """Odeslání přes SMTP schránky. Port 465 = SSL, jinak STARTTLS."""
    heslo = email_sync.heslo_uctu(ucet)
    if not heslo:
        raise RuntimeError("Ke schránce není uložené heslo.")
    ctx = ssl.create_default_context()
    host, port = ucet.smtp_host, int(ucet.smtp_port or 587)
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
            s.login(ucet.adresa, heslo)
            s.send_message(msg, from_addr=ucet.adresa, to_addrs=komu)
    else:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(ucet.adresa, heslo)
            s.send_message(msg, from_addr=ucet.adresa, to_addrs=komu)


# ---- hlavní vstup (volá worker) ----------------------------------------------
def zpracuj_nove(db: Session, ucet: CrmEmailUcet) -> dict:
    """Projde nezpracované příchozí zprávy: pravidla → OOO → přeposílání.

    Volá se **z workeru**, nikdy z web procesu. Každá zpráva se zpracuje nejvýš
    jednou (`zpracovano_at`) – i když některá akce selže. Opakovat pokus po
    chybě by u odesílání znamenalo riziko, že odpověď odejde dvakrát, a to je
    horší než neodeslaná odpověď.
    """
    hranice = _ted() - timedelta(hours=MAX_STARI_H)
    zpravy = (
        db.query(CrmEmailZprava)
        .filter(
            CrmEmailZprava.ucet_id == ucet.id,
            CrmEmailZprava.zpracovano_at.is_(None),
            CrmEmailZprava.smer == "prichozi",
        )
        .order_by(CrmEmailZprava.datum_at)
        .limit(DAVKA)
        .all()
    )
    if not zpravy:
        return {"zpracovano": 0, "pravidel": 0, "ooo": 0, "preposlano": 0}

    pravidla = (
        db.query(CrmEmailPravidlo)
        .filter(CrmEmailPravidlo.ucet_id == ucet.id, CrmEmailPravidlo.aktivni.is_(True))
        .order_by(CrmEmailPravidlo.poradi, CrmEmailPravidlo.id)
        .all()
    )

    pocty = {"zpracovano": 0, "pravidel": 0, "ooo": 0, "preposlano": 0}

    for zprava in zpravy:
        zprava_id = zprava.id
        datum = zprava.datum_at
        if datum is not None and datum.tzinfo is None:
            datum = datum.replace(tzinfo=timezone.utc)

        # Stará pošta se jen odškrtne – neodpovídá se na ni ani nepřeposílá.
        if datum is not None and datum < hranice:
            zprava.zpracovano_at = _ted()
            pocty["zpracovano"] += 1
            db.commit()
            continue

        zmizela = False
        try:
            zmizela = _uplatni_pravidla(db, ucet, zprava, pravidla, pocty)
        except Exception as e:  # noqa: BLE001 - jedna zpráva nesmí zastavit ostatní
            db.rollback()
            _log.warning("Pravidla u zprávy %s selhala: %s", zprava_id, e)

        if not zmizela:
            zprava = db.get(CrmEmailZprava, zprava_id)
            if zprava is None:
                continue
            try:
                if posli_ooo(db, ucet, zprava):
                    pocty["ooo"] += 1
            except Exception as e:  # noqa: BLE001
                db.rollback()
                _log.warning("OOO odpověď u zprávy %s selhala: %s", zprava_id, e)

            zprava = db.get(CrmEmailZprava, zprava_id)
            if zprava is not None and ucet.preposilani_zapnuto and ucet.preposilani_komu:
                try:
                    if posli_preposlani(db, ucet, zprava, ucet.preposilani_komu):
                        pocty["preposlano"] += 1
                        if not ucet.preposilani_nechat_kopii:
                            kos = email_sync.slozka_druhu(db, ucet.id, "kos")
                            if kos is not None and kos.id != zprava.slozka_id:
                                email_sync.presun_zpravu(db, zprava, kos)
                                zmizela = True
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    _log.warning("Přeposlání zprávy %s selhalo: %s", zprava_id, e)

        # Odškrtnout i po chybě: opakovaný pokus by mohl poslat odpověď dvakrát.
        if not zmizela:
            zprava = db.get(CrmEmailZprava, zprava_id)
            if zprava is not None:
                zprava.zpracovano_at = _ted()
        pocty["zpracovano"] += 1
        db.commit()

    return pocty


def _uplatni_pravidla(
    db: Session,
    ucet: CrmEmailUcet,
    zprava: CrmEmailZprava,
    pravidla: list[CrmEmailPravidlo],
    pocty: dict,
) -> bool:
    """Projde pravidla v pořadí. Vrací True, když zpráva zmizela ze složky."""
    for pravidlo in pravidla:
        if not pravidlo_sedi(zprava, pravidlo):
            continue
        pravidlo.akce = _serad_akce(pravidlo)
        popis, zmizela = _proved_akce(db, ucet, zprava, pravidlo)
        pravidlo.pocet_pouziti = (pravidlo.pocet_pouziti or 0) + 1
        pravidlo.posledni_pouziti_at = _ted()
        pocty["pravidel"] += 1
        if popis:
            _log.info("Pravidlo „%s“: %s", pravidlo.nazev, ", ".join(popis))
        db.commit()
        if zmizela:
            return True
        # „Stop processing more rules" jako v Outlooku – bez toho by zpráva
        # propadla i pravidly, která už platit nemají.
        if pravidlo.zastavit_dalsi:
            return False
    return False
