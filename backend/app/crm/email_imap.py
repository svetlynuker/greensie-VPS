"""Nízkoúrovňový IMAP klient – čtení a úpravy pošty na serveru (Seznam.cz).

Postavené na `imaplib` ze standardní knihovny: žádná nová závislost do
requirements. Vyšší patra (co se kdy stahuje, co se ukládá do DB) jsou
v `email_sync.py`; tady je jen „jak se se serverem mluví".

---- Proč heslo od schránky, a ne token -------------------------------------
Seznam Email nemá OAuth ani „hesla pro aplikace" – IMAP i SMTP jsou trvale
zapnuté a přihlašuje se **přímo heslem od schránky**. Nedá se to obejít,
takže heslo v appce být musí; ukládá se zašifrovaně (`app/crypto.py`) a nikdy
se nevrací do frontendu. Kdo si heslo na Seznamu změní, musí ho přepsat i tady.

---- Názvy složek jsou zakódované ------------------------------------------
IMAP posílá jména složek v „modified UTF-7" (RFC 3501 §5.1.3), takže Odeslané
přijdou jako `Odesl&AOE-n&AOk-`. V DB proto držíme **obojí**: `imap_nazev`
(surový, tím se se serverem mluví) a `nazev` (rozluštěný, ten vidí člověk).
Míchat je dohromady je klasická chyba – operace se surovým názvem funguje
vždycky, s rozluštěným jen u složek bez diakritiky.

---- Co se nikdy nesmí stát -------------------------------------------------
Nic v tomhle modulu nemaže poštu na serveru a nestahuje zprávy s příznakem
`\\Seen`: všude se používá `BODY.PEEK[...]` místo `BODY[...]`. Kdyby appka při
synchronizaci odškrtala nepřečtenou poštu, člověk by o ni v mobilu přišel.
"""

import base64
import email
import email.utils
import html as html_modul
import imaplib
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message

# Seznam.cz. Přepisovatelné u účtu, ale tohle je výchozí pro 99 % případů.
VYCHOZI_IMAP_HOST = "imap.seznam.cz"
VYCHOZI_IMAP_PORT = 993
VYCHOZI_SMTP_HOST = "smtp.seznam.cz"
# 587 + STARTTLS, ne 465: Hetzner blokuje odchozí port 465 (i 25) – ověřeno,
# spojení timeoutuje. Viz i `app/mailer.py`, kde je to ze stejného důvodu.
VYCHOZI_SMTP_PORT = 587

# Strop pro jeden příkaz: víc UID v jednom FETCH server odmítne nebo utne.
DAVKA_UID = 100
# Kolik znaků náhledu si držíme v seznamu zpráv (aby se nemusel tahat text).
DELKA_VYPISU = 200
# Pojistka proti obřím zprávám – tělo nad tímhle se stáhne jen zkráceně.
MAX_TELO_B = 2 * 1024 * 1024

imaplib._MAXLINE = max(imaplib._MAXLINE, 1_000_000)


class ImapChyba(Exception):
    """Chyba komunikace se schránkou – text je určený uživateli."""


# ---- modified UTF-7 (RFC 3501) ----------------------------------------------
def dekoduj_nazev(nazev: str) -> str:
    """`Odesl&AOE-n&AOk-` → `Odeslané`. Co se nepodaří, vrací beze změny.

    Nerozluštěný název je pořád lepší než výjimka: složka se ukáže ošklivě,
    ale appka funguje dál.
    """
    if "&" not in nazev:
        return nazev
    vysledek: list[str] = []
    i = 0
    while i < len(nazev):
        if nazev[i] != "&":
            vysledek.append(nazev[i])
            i += 1
            continue
        konec = nazev.find("-", i + 1)
        if konec < 0:
            # neuzavřená sekvence – zbytek bereme jako text
            vysledek.append(nazev[i:])
            break
        kus = nazev[i + 1 : konec]
        if kus == "":
            vysledek.append("&")  # „&-" je escapovaný ampersand
        else:
            b64 = kus.replace(",", "/")
            b64 += "=" * (-len(b64) % 4)
            try:
                vysledek.append(base64.b64decode(b64).decode("utf-16-be"))
            except Exception:  # noqa: BLE001 - nerozluštěné vrátíme, jak přišlo
                vysledek.append(nazev[i : konec + 1])
        i = konec + 1
    return "".join(vysledek)


def zakoduj_nazev(nazev: str) -> str:
    """`Odeslané` → `Odesl&AOE-n&AOk-`. Potřeba jen při zakládání složky."""
    vysledek: list[str] = []
    beh: list[str] = []

    def sesyp() -> None:
        if not beh:
            return
        surove = "".join(beh).encode("utf-16-be")
        vysledek.append("&" + base64.b64encode(surove).decode().rstrip("=").replace("/", ",") + "-")
        beh.clear()

    for znak in nazev:
        if znak == "&":
            sesyp()
            vysledek.append("&-")
        elif 0x20 <= ord(znak) <= 0x7E:
            sesyp()
            vysledek.append(znak)
        else:
            beh.append(znak)
    sesyp()
    return "".join(vysledek)


# ---- parsování hlaviček ------------------------------------------------------
def _text_hlavicky(surove: str | None) -> str:
    """Rozluští MIME kódování hlavičky (`=?utf-8?B?…?=`) na čitelný text."""
    if not surove:
        return ""
    kusy: list[str] = []
    try:
        for hodnota, kodovani in decode_header(surove):
            if isinstance(hodnota, bytes):
                kusy.append(hodnota.decode(kodovani or "utf-8", errors="replace"))
            else:
                kusy.append(hodnota)
    except Exception:  # noqa: BLE001 - rozbitou hlavičku vrátíme, jak přišla
        return surove
    # Nové řádky ve předmětu rozbíjejí seznam zpráv na jeden řádek.
    return " ".join("".join(kusy).split())


def _adresy(zprava: Message, pole: str) -> list[dict]:
    """`To`/`Cc` → [{jmeno, adresa}]. Adresy bez zavináče zahazuje."""
    surove = zprava.get_all(pole)
    if not surove:
        return []
    vysledek: list[dict] = []
    for jmeno, adresa in email.utils.getaddresses([str(s) for s in surove]):
        adresa = (adresa or "").strip()
        if "@" not in adresa:
            continue
        vysledek.append({"jmeno": _text_hlavicky(jmeno), "adresa": adresa.lower()})
    return vysledek


def _datum(zprava: Message) -> datetime:
    """Datum zprávy v UTC. Chybějící nebo rozbité nahradí „teď"."""
    surove = zprava.get("Date")
    if surove:
        try:
            dt = email.utils.parsedate_to_datetime(str(surove))
            if dt is not None:
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _prvni_adresa(zprava: Message, pole: str = "From") -> tuple[str, str]:
    seznam = _adresy(zprava, pole)
    if not seznam:
        return "", ""
    return seznam[0]["jmeno"], seznam[0]["adresa"]


def hlavicky_ze_zpravy(zprava: Message) -> dict:
    """Z MIME zprávy vytáhne to, co potřebuje seznam pošty."""
    od_jmeno, od_adresa = _prvni_adresa(zprava, "From")
    return {
        "message_id": (str(zprava.get("Message-ID")) or "").strip()[:998],
        "in_reply_to": (str(zprava.get("In-Reply-To") or "")).strip()[:998],
        "od_jmeno": od_jmeno,
        "od_adresa": od_adresa,
        "komu": _adresy(zprava, "To"),
        "kopie": _adresy(zprava, "Cc"),
        "odpovedet_na": _prvni_adresa(zprava, "Reply-To")[1],
        "predmet": _text_hlavicky(str(zprava.get("Subject") or "")),
        "datum_at": _datum(zprava),
        # Auto-Submitted / Precedence: podle nich se pozná robot – OOO odpověď
        # se na takovou poštu posílat nesmí (viz email_automat.py).
        "automat": _je_automat(zprava),
    }


def _je_automat(zprava: Message) -> bool:
    """Je zpráva strojová (newsletter, autoresponder, mailing list)?

    Rozhoduje o tom, jestli na ni smí odejít OOO odpověď. RFC 3834 říká, že
    autoresponder nesmí odpovídat na `Auto-Submitted: auto-*` ani na poštu
    z mailing listu – jinak si dva roboti začnou psát navzájem.
    """
    auto = str(zprava.get("Auto-Submitted") or "").strip().lower()
    if auto and auto != "no":
        return True
    precedence = str(zprava.get("Precedence") or "").strip().lower()
    if precedence in {"bulk", "junk", "list", "auto_reply"}:
        return True
    for hlavicka in ("List-Id", "List-Unsubscribe", "List-Post", "X-Auto-Response-Suppress"):
        if zprava.get(hlavicka):
            return True
    # Prázdný odesílatel = odraz nedoručitelnosti (bounce).
    if not _prvni_adresa(zprava, "From")[1]:
        return True
    return False


def _dekoduj_cast(cast: Message) -> str:
    """Tělo jedné části jako text (respektuje charset, chyby nahradí)."""
    try:
        surove = cast.get_payload(decode=True)
    except Exception:  # noqa: BLE001
        return ""
    if surove is None:
        return ""
    charset = cast.get_content_charset() or "utf-8"
    try:
        return surove.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return surove.decode("utf-8", errors="replace")


def telo_ze_zpravy(zprava: Message) -> dict:
    """Rozebere zprávu na text, HTML a seznam příloh.

    Vrací `{"text", "html", "prilohy": [{nazev, mime, velikost, cislo_casti}]}`.
    `cislo_casti` je cesta v MIME struktuře (`2.1`) – tou se příloha později
    stáhne jedním FETCH bez tahání celé zprávy znovu.
    """
    text_kusy: list[str] = []
    html_kusy: list[str] = []
    prilohy: list[dict] = []

    def projdi(cast: Message, cesta: str) -> None:
        mime = (cast.get_content_type() or "").lower()
        dispozice = str(cast.get("Content-Disposition") or "").lower()
        nazev_prilohy = cast.get_filename()

        if cast.is_multipart():
            for i, pod in enumerate(cast.get_payload() or [], start=1):
                if isinstance(pod, Message):
                    projdi(pod, f"{cesta}.{i}" if cesta else str(i))
            return

        je_priloha = "attachment" in dispozice or bool(nazev_prilohy)
        if je_priloha:
            try:
                velikost = len(cast.get_payload(decode=True) or b"")
            except Exception:  # noqa: BLE001
                velikost = 0
            prilohy.append(
                {
                    "nazev": _text_hlavicky(nazev_prilohy) or f"priloha-{cesta or '1'}",
                    "mime": mime or "application/octet-stream",
                    "velikost": velikost,
                    "cislo_casti": cesta or "1",
                    # Obrázek vložený do těla (cid:) není „příloha" v očích
                    # člověka – nemá se počítat do sponky u zprávy.
                    "vlozeny": "inline" in dispozice and bool(cast.get("Content-ID")),
                }
            )
            return

        if mime == "text/plain":
            text_kusy.append(_dekoduj_cast(cast))
        elif mime == "text/html":
            html_kusy.append(_dekoduj_cast(cast))

    projdi(zprava, "")
    return {
        "text": "\n".join(k for k in text_kusy if k).strip(),
        "html": "\n".join(k for k in html_kusy if k).strip(),
        "prilohy": prilohy,
    }


def vypis_z_tela(text: str, html: str) -> str:
    """Krátký náhled do seznamu zpráv. Z HTML odstraní značky."""
    zdroj = text
    if not zdroj and html:
        bez_hlavy = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", html)
        zdroj = re.sub(r"(?s)<[^>]+>", " ", bez_hlavy)
        # `html.unescape` zvládne i číselné entity (`&#283;`), na které by ruční
        # výčet nestačil – a v náhledu je jich plno (newslettery).
        zdroj = html_modul.unescape(zdroj).replace("\xa0", " ")
    return " ".join(zdroj.split())[:DELKA_VYPISU]


# ---- parsování odpovědí serveru ---------------------------------------------
_RE_LIST = re.compile(rb'^\((?P<flags>[^)]*)\)\s+(?:"(?P<delim>[^"]*)"|NIL)\s+(?P<nazev>.+)$')
_RE_UIDVALIDITY = re.compile(rb"UIDVALIDITY\s+(\d+)", re.IGNORECASE)
_RE_UID = re.compile(rb"UID\s+(\d+)")
_RE_FLAGS = re.compile(rb"FLAGS\s+\(([^)]*)\)", re.IGNORECASE)

# Speciální složky. Server je značí příznakem, ale Seznam u části složek
# neposílá nic – proto je záložní poznávání podle názvu (česky i anglicky).
PRIZNAK_DRUH = {
    "\\inbox": "inbox",
    "\\sent": "odeslane",
    "\\drafts": "koncepty",
    "\\trash": "kos",
    "\\junk": "spam",
    "\\archive": "archiv",
}
NAZEV_DRUH = {
    "inbox": "inbox",
    "doručená pošta": "inbox",
    "odeslané": "odeslane",
    "sent": "odeslane",
    "koncepty": "koncepty",
    "rozepsané": "koncepty",
    "drafts": "koncepty",
    "koš": "kos",
    "trash": "kos",
    "spam": "spam",
    "junk": "spam",
    "hromadné": "spam",
    "archiv": "archiv",
    "archive": "archiv",
}
# V jakém pořadí se složky ukazují v panelu (co není v seznamu, jde na konec).
PORADI_DRUHU = ["inbox", "koncepty", "odeslane", "spam", "kos", "archiv", "vlastni"]


def druh_slozky(nazev: str, priznaky: list[str]) -> str:
    for p in priznaky:
        druh = PRIZNAK_DRUH.get(p.lower())
        if druh:
            return druh
    return NAZEV_DRUH.get(nazev.strip().lower(), "vlastni")


def _rozparsuj_nazev(surove: bytes) -> str:
    text = surove.decode("utf-8", errors="replace").strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        text = text[1:-1]
    return text.replace('\\"', '"')


# ---- spojení -----------------------------------------------------------------
class ImapSpojeni:
    """Jedno IMAP spojení. Používej jako kontextový manažer.

    Spojení je drahé (TLS handshake + LOGIN ~0,5 s), takže se v rámci jedné
    synchronizace drží otevřené a projdou se přes něj všechny složky.
    """

    def __init__(self, host: str, port: int, uzivatel: str, heslo: str):
        self.host = host or VYCHOZI_IMAP_HOST
        self.port = int(port or VYCHOZI_IMAP_PORT)
        self.uzivatel = uzivatel
        self.heslo = heslo
        self._m: imaplib.IMAP4_SSL | None = None
        self._vybrana: str | None = None

    # -- životní cyklus --------------------------------------------------------
    def __enter__(self) -> "ImapSpojeni":
        self.pripoj()
        return self

    def __exit__(self, *_):
        self.odpoj()
        return False

    def pripoj(self) -> None:
        if not self.heslo:
            raise ImapChyba("Ke schránce není uložené heslo – zadej ho v nastavení e-mailu.")
        try:
            self._m = imaplib.IMAP4_SSL(self.host, self.port, timeout=30)
        except Exception as e:  # noqa: BLE001 - síť, DNS, TLS…
            raise ImapChyba(f"Nepodařilo se připojit k {self.host}:{self.port} – {e}")
        try:
            self._m.login(self.uzivatel, self.heslo)
        except imaplib.IMAP4.error as e:
            self.odpoj()
            raise ImapChyba(
                "Schránka odmítla přihlášení. Zkontroluj adresu a heslo "
                f"(u Seznamu se přihlašuje celou adresou). Server odpověděl: {e}"
            )

    def odpoj(self) -> None:
        if self._m is None:
            return
        try:
            if self._vybrana is not None:
                self._m.close()
        except Exception:  # noqa: BLE001 - zavírání nesmí přebít původní chybu
            pass
        try:
            self._m.logout()
        except Exception:  # noqa: BLE001
            pass
        self._m = None
        self._vybrana = None

    @property
    def m(self) -> imaplib.IMAP4_SSL:
        if self._m is None:
            raise ImapChyba("Spojení se schránkou není otevřené.")
        return self._m

    def _prikaz(self, jmeno: str, *args):
        """Zavolá IMAP příkaz a ohlídá, že odpověď je OK."""
        try:
            stav, data = getattr(self.m, jmeno)(*args)
        except imaplib.IMAP4.abort as e:
            raise ImapChyba(f"Schránka spojení ukončila ({jmeno}): {e}")
        except imaplib.IMAP4.error as e:
            raise ImapChyba(f"Schránka odmítla příkaz {jmeno}: {e}")
        except Exception as e:  # noqa: BLE001 - timeout, rozpadlé TLS…
            raise ImapChyba(f"Chyba spojení se schránkou ({jmeno}): {e}")
        if stav != "OK":
            raise ImapChyba(f"Schránka odpověděla {stav} na {jmeno}.")
        return data

    # -- složky ---------------------------------------------------------------
    def slozky(self) -> list[dict]:
        """Všechny složky schránky: `{imap_nazev, nazev, druh, oddelovac}`."""
        data = self._prikaz("list")
        vysledek: list[dict] = []
        for radek in data or []:
            if radek is None:
                continue
            # Server může poslat i dvojici (bytes, bytes) u literálového názvu.
            if isinstance(radek, tuple):
                radek = b" ".join(x for x in radek if isinstance(x, bytes))
            if not isinstance(radek, bytes):
                continue
            shoda = _RE_LIST.match(radek.strip())
            if shoda is None:
                continue
            priznaky = shoda.group("flags").decode("ascii", errors="replace").split()
            if "\\Noselect" in priznaky or "\\NonExistent" in priznaky:
                continue  # kontejner, který nejde otevřít
            imap_nazev = _rozparsuj_nazev(shoda.group("nazev"))
            nazev = dekoduj_nazev(imap_nazev)
            vysledek.append(
                {
                    "imap_nazev": imap_nazev,
                    "nazev": nazev,
                    "druh": druh_slozky(nazev, priznaky),
                    "oddelovac": (shoda.group("delim") or b".").decode("ascii", errors="replace"),
                }
            )
        # INBOX musí být vždycky, i kdyby ho LIST nevrátil.
        if not any(s["druh"] == "inbox" for s in vysledek):
            vysledek.insert(
                0, {"imap_nazev": "INBOX", "nazev": "Doručená pošta", "druh": "inbox", "oddelovac": "."}
            )
        return vysledek

    def _uvozovky(self, imap_nazev: str) -> str:
        """Název složky pro příkaz – v uvozovkách kvůli mezerám."""
        return '"' + imap_nazev.replace("\\", "\\\\").replace('"', '\\"') + '"'

    def vyber(self, imap_nazev: str, jen_cteni: bool = True) -> dict:
        """Otevře složku. Vrací `{pocet, uidvalidity}`.

        `jen_cteni=True` je výchozí schválně: synchronizace nesmí sáhnout na
        příznaky. Kdo chce měnit, řekne si o to.

        POZOR – `imaplib` **nemá metodu `examine`**, i když IMAP příkaz EXAMINE
        existuje. Read-only otevření se dělá přes `select(mailbox, readonly=True)`,
        která EXAMINE pošle sama. Volání `examine` skončí na `AttributeError`
        („Unknown IMAP4 command"), a protože se název příkazu dřív skládal do
        proměnné, neodhalila to ani statická kontrola názvů. Proto se tu jméno
        příkazu **nesmí skládat dynamicky** (hlídá `test_email_klient.py`).
        """
        data = self._prikaz("select", self._uvozovky(imap_nazev), jen_cteni)
        self._vybrana = imap_nazev
        try:
            pocet = int(data[0]) if data and data[0] else 0
        except (TypeError, ValueError):
            pocet = 0
        uidvalidity = 0
        try:
            odpoved = self.m.response("UIDVALIDITY")[1]
            for kus in odpoved or []:
                if isinstance(kus, bytes):
                    shoda = _RE_UIDVALIDITY.search(kus)
                    if shoda:
                        uidvalidity = int(shoda.group(1))
                        break
        except Exception:  # noqa: BLE001 - bez UIDVALIDITY se dá žít (0 = neznámé)
            pass
        return {"pocet": pocet, "uidvalidity": uidvalidity}

    def zaloz_slozku(self, nazev: str) -> str:
        """Vytvoří složku (název se zakóduje). Vrací surový IMAP název."""
        imap_nazev = zakoduj_nazev(nazev)
        self._prikaz("create", self._uvozovky(imap_nazev))
        return imap_nazev

    # -- hledání a stahování --------------------------------------------------
    def uidy(self, kriterium: str = "ALL") -> list[int]:
        """UID SEARCH. `kriterium` je surové IMAP hledání (`UID 120:*`)."""
        data = self._prikaz("uid", "SEARCH", None, kriterium)
        if not data or not data[0]:
            return []
        try:
            return sorted(int(x) for x in data[0].split())
        except ValueError:
            return []

    def uidy_nad(self, posledni_uid: int) -> list[int]:
        """Nové zprávy od posledně. `UID n:*` vrací i `n` samotné – odfiltruje se."""
        od = max(1, int(posledni_uid or 0) + 1)
        return [u for u in self.uidy(f"UID {od}:*") if u >= od]

    def hlavicky(self, uidy: list[int]) -> list[dict]:
        """Hlavičky + příznaky pro dané UID. Tělo netahá (PEEK, jen HEADER)."""
        vysledek: list[dict] = []
        for davka in _po_davkach(uidy, DAVKA_UID):
            data = self._prikaz(
                "uid", "FETCH", ",".join(str(u) for u in davka),
                "(FLAGS RFC822.SIZE BODY.PEEK[HEADER])",
            )
            vysledek.extend(self._rozparsuj_fetch(data))
        return vysledek

    def priznaky(self, uidy: list[int]) -> dict[int, list[str]]:
        """Jen příznaky – tímhle jede „živá kontrola přečtení"."""
        vysledek: dict[int, list[str]] = {}
        for davka in _po_davkach(uidy, DAVKA_UID * 5):
            data = self._prikaz("uid", "FETCH", ",".join(str(u) for u in davka), "(FLAGS)")
            for radek in data or []:
                surove = radek[0] if isinstance(radek, tuple) else radek
                if not isinstance(surove, bytes):
                    continue
                uid_shoda = _RE_UID.search(surove)
                flag_shoda = _RE_FLAGS.search(surove)
                if uid_shoda is None:
                    continue
                priznaky = (
                    flag_shoda.group(1).decode("ascii", errors="replace").split()
                    if flag_shoda
                    else []
                )
                vysledek[int(uid_shoda.group(1))] = priznaky
        return vysledek

    def _rozparsuj_fetch(self, data) -> list[dict]:
        """Z odpovědi FETCH vytáhne (uid, příznaky, surová hlavička/zpráva)."""
        vysledek: list[dict] = []
        for radek in data or []:
            if not isinstance(radek, tuple) or len(radek) < 2:
                continue
            popis, obsah = radek[0], radek[1]
            if not isinstance(popis, bytes) or not isinstance(obsah, (bytes, bytearray)):
                continue
            uid_shoda = _RE_UID.search(popis)
            if uid_shoda is None:
                continue
            flag_shoda = _RE_FLAGS.search(popis)
            priznaky = (
                flag_shoda.group(1).decode("ascii", errors="replace").split() if flag_shoda else []
            )
            try:
                zprava = email.message_from_bytes(bytes(obsah))
            except Exception:  # noqa: BLE001 - rozbitou zprávu přeskočíme
                continue
            polozka = hlavicky_ze_zpravy(zprava)
            polozka["uid"] = int(uid_shoda.group(1))
            polozka["priznaky"] = priznaky
            polozka["velikost"] = _velikost_z_popisu(popis)
            vysledek.append(polozka)
        return vysledek

    def zprava(self, uid: int) -> dict:
        """Celá zpráva: hlavičky + text + HTML + seznam příloh.

        `BODY.PEEK[]` schválně – otevření v appce označí zprávu přečtenou
        explicitně (`nastav_priznak`), ne jako vedlejší efekt stahování.
        """
        data = self._prikaz("uid", "FETCH", str(uid), "(FLAGS RFC822.SIZE BODY.PEEK[])")
        for radek in data or []:
            if not isinstance(radek, tuple) or len(radek) < 2:
                continue
            popis, obsah = radek[0], radek[1]
            if not isinstance(obsah, (bytes, bytearray)):
                continue
            surove = bytes(obsah)
            try:
                zprava = email.message_from_bytes(surove)
            except Exception as e:  # noqa: BLE001
                raise ImapChyba(f"Zprávu se nepodařilo přečíst: {e}")
            polozka = hlavicky_ze_zpravy(zprava)
            polozka.update(telo_ze_zpravy(zprava))
            flag_shoda = _RE_FLAGS.search(popis) if isinstance(popis, bytes) else None
            polozka["priznaky"] = (
                flag_shoda.group(1).decode("ascii", errors="replace").split() if flag_shoda else []
            )
            polozka["uid"] = uid
            polozka["velikost"] = len(surove)
            polozka["surova"] = surove if len(surove) <= MAX_TELO_B else b""
            return polozka
        raise ImapChyba(f"Zpráva UID {uid} ve složce není – pravděpodobně ji někdo přesunul.")

    def priloha(self, uid: int, cislo_casti: str) -> bytes:
        """Stáhne jednu část zprávy (přílohu) bez tahání celé zprávy."""
        data = self._prikaz("uid", "FETCH", str(uid), f"(BODY.PEEK[{cislo_casti}])")
        for radek in data or []:
            if isinstance(radek, tuple) and len(radek) >= 2 and isinstance(radek[1], (bytes, bytearray)):
                surove = bytes(radek[1])
                # Server posílá část zakódovanou tak, jak je ve zprávě – dekóduje
                # se podle Content-Transfer-Encoding, který sem ale nedorazí.
                # Proto část zabalíme do minimální zprávy a necháme rozebrat.
                return surove
        raise ImapChyba("Přílohu se nepodařilo stáhnout.")

    # -- změny na serveru -----------------------------------------------------
    def nastav_priznak(self, imap_nazev: str, uidy: list[int], priznak: str, zapnout: bool) -> None:
        """Přidá/odebere příznak (`\\Seen`, `\\Flagged`) – zápis zpět na Seznam."""
        if not uidy:
            return
        self.vyber(imap_nazev, jen_cteni=False)
        operace = "+FLAGS" if zapnout else "-FLAGS"
        for davka in _po_davkach(uidy, DAVKA_UID):
            self._prikaz("uid", "STORE", ",".join(str(u) for u in davka), operace, f"({priznak})")

    def presun(self, imap_nazev: str, uidy: list[int], cil_imap_nazev: str) -> None:
        """Přesune zprávy do jiné složky (MOVE, jinak COPY + \\Deleted)."""
        if not uidy:
            return
        self.vyber(imap_nazev, jen_cteni=False)
        seznam = ",".join(str(u) for u in uidy)
        cil = self._uvozovky(cil_imap_nazev)
        schopnosti = getattr(self.m, "capabilities", ()) or ()
        if "MOVE" in {str(c).upper() for c in schopnosti}:
            self._prikaz("uid", "MOVE", seznam, cil)
            return
        # Starší server: zkopírovat, označit ke smazání, uklidit.
        self._prikaz("uid", "COPY", seznam, cil)
        self._prikaz("uid", "STORE", seznam, "+FLAGS", "(\\Deleted)")
        try:
            self._prikaz("expunge")
        except ImapChyba:
            # Neuklizené kopie jsou lepší než spadlý přesun – uklidí se příště.
            pass

    def uloz_zpravu(self, imap_nazev: str, surova: bytes, precteno: bool = True) -> None:
        """APPEND – uloží odeslanou zprávu do složky Odeslané na serveru.

        Bez tohohle kroku by odeslaná pošta chyběla v mobilu i na webu Seznamu
        a člověk by netušil, co z appky odešlo.
        """
        priznaky = "(\\Seen)" if precteno else None
        try:
            stav, _ = self.m.append(self._uvozovky(imap_nazev), priznaky, None, surova)
        except Exception as e:  # noqa: BLE001
            raise ImapChyba(f"Kopii do složky {imap_nazev} se nepodařilo uložit: {e}")
        if stav != "OK":
            raise ImapChyba(f"Schránka odmítla uložit kopii do {imap_nazev} ({stav}).")


def _velikost_z_popisu(popis: bytes) -> int:
    shoda = re.search(rb"RFC822\.SIZE\s+(\d+)", popis, re.IGNORECASE)
    return int(shoda.group(1)) if shoda else 0


def _po_davkach(polozky: list, velikost: int):
    for i in range(0, len(polozky), velikost):
        yield polozky[i : i + velikost]


def otestuj_pripojeni(host: str, port: int, uzivatel: str, heslo: str) -> dict:
    """Zkusí se přihlásit a vypsat složky. Pro tlačítko „Otestovat" v nastavení."""
    with ImapSpojeni(host, port, uzivatel, heslo) as s:
        slozky = s.slozky()
        inbox = next((x for x in slozky if x["druh"] == "inbox"), None)
        pocet = s.vyber(inbox["imap_nazev"])["pocet"] if inbox else 0
    return {
        "ok": True,
        "pocet_slozek": len(slozky),
        "zprav_v_doruceni": pocet,
        "slozky": [s["nazev"] for s in slozky],
    }
