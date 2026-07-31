"""Půjčovna IMAP spojení – jedno otevřené spojení na schránku, ne na klik.

DŮVOD, PROČ TOHLE EXISTUJE: nové IMAP spojení k Seznamu stojí TLS handshake
plus LOGIN, dohromady zhruba půl až jednu a půl sekundy. Bez půjčovny by tolik
trvalo **každé** otevření zprávy, odškrtnutí přečteno i přesun do složky –
appka by působila jako webový formulář, ne jako poštovní klient. Se sdíleným
spojením jsou tyhle operace v desítkách milisekund.

---- Jak to funguje ---------------------------------------------------------
Na účet se drží nejvýš jedno spojení a **zámek**. Kdo si spojení půjčí, drží
zámek – dvě vlákna si nikdy nemluví do jednoho socketu. To je tvrdý požadavek
IMAP protokolu, ne opatrnost: příkazy a odpovědi se páruji přes tag a dvě
vlákna v jednom spojení si odpovědi rozeberou navzájem.

Serializace na účet je v pořádku, protože jeden účet = jeden člověk, který
kliká po jedné. Serializovat se tím nedá celá appka – různé účty jdou paralelně.

---- Kdy se spojení zahazuje ------------------------------------------------
* Po `NECINNOST_S` bez použití (server ho zavře sám, typicky po 10–30 min).
* Při jakékoli chybě – rozpadlé spojení se nedá „opravit", jen vyhodit.

Volající tedy nemusí řešit, jestli je spojení ještě živé. Musí ale počítat
s tím, že se první příkaz může protáhnout o znovupřipojení.

---- Kde se to NEPOUŽÍVÁ ----------------------------------------------------
Plná synchronizace (`email_sync.synchronizuj_ucet`) si bere spojení vlastní:
běží ve workeru mimo web proces, trvá desítky sekund a nemá držet zámek, pod
kterým by čekal člověk klikající v appce.
"""

import threading
import time

from app.crm.email_imap import ImapChyba, ImapSpojeni

# Po téhle době nečinnosti spojení zahodíme sami. Seznam zavírá nečinné IMAP
# spojení dřív, než je náš timeout – lepší se odpojit vědomě než čekat na chybu.
NECINNOST_S = 240
# Jak dlouho se čeká na uvolnění spojení jiným vláknem, než to vzdáme. Delší
# čekání by drželo HTTP požadavek; kratší by shazovalo běžné dvojkliky.
CEKANI_NA_ZAMEK_S = 45


class _Drzak:
    """Spojení jedné schránky + zámek, který hlídá výhradní použití."""

    __slots__ = ("zamek", "spojeni", "pouzito_v")

    def __init__(self) -> None:
        self.zamek = threading.Lock()
        self.spojeni: ImapSpojeni | None = None
        self.pouzito_v: float = 0.0


_drzaky: dict[int, _Drzak] = {}
_zamek_mapy = threading.Lock()


def _drzak(ucet_id: int) -> _Drzak:
    with _zamek_mapy:
        d = _drzaky.get(ucet_id)
        if d is None:
            d = _Drzak()
            _drzaky[ucet_id] = d
        return d


class PujcenaSchranka:
    """Kontextový manažer: `with pujc(ucet) as s: s.vyber(...)`.

    Uvnitř bloku je spojení výhradně tvoje. Po opuštění bloku zůstane otevřené
    pro dalšího – **kromě** případu, kdy uvnitř nastala chyba; to se zahodí.
    """

    def __init__(self, ucet, heslo: str):
        self._ucet_id = int(ucet.id)
        self._ucet = ucet
        self._heslo = heslo
        self._d = _drzak(self._ucet_id)
        self._drzim_zamek = False

    def __enter__(self) -> ImapSpojeni:
        if not self._d.zamek.acquire(timeout=CEKANI_NA_ZAMEK_S):
            raise ImapChyba(
                "Schránka je zaneprázdněná jinou operací. Zkus to za chvíli znovu."
            )
        self._drzim_zamek = True
        try:
            self._d.spojeni = self._ziv_spojeni()
            self._d.pouzito_v = time.monotonic()
            return self._d.spojeni
        except BaseException:
            # Nepodařilo se připojit – zámek nesmí zůstat zamčený navždy.
            self._uvolni(zahodit=True)
            raise

    def __exit__(self, typ, _hodnota, _stopa):
        # Chyba uvnitř bloku = spojení je v neznámém stavu (nedočtená odpověď,
        # rozpadlé TLS). Opravit se nedá, jen zahodit.
        self._uvolni(zahodit=typ is not None)
        return False

    def _ziv_spojeni(self) -> ImapSpojeni:
        """Vrátí použitelné spojení – existující, nebo nové."""
        s = self._d.spojeni
        if s is not None:
            if time.monotonic() - self._d.pouzito_v > NECINNOST_S:
                _zavri(s)
                s = None
            else:
                try:
                    # NOOP je jediný spolehlivý test, že socket ještě žije.
                    s._prikaz("noop")
                except Exception:  # noqa: BLE001 - mrtvé spojení nahradíme novým
                    _zavri(s)
                    s = None
        if s is None:
            s = ImapSpojeni(
                self._ucet.imap_host, self._ucet.imap_port, self._ucet.adresa, self._heslo
            )
            s.pripoj()
        return s

    def _uvolni(self, zahodit: bool) -> None:
        if zahodit and self._d.spojeni is not None:
            _zavri(self._d.spojeni)
            self._d.spojeni = None
        if self._drzim_zamek:
            self._drzim_zamek = False
            self._d.zamek.release()


def _zavri(s: ImapSpojeni) -> None:
    try:
        s.odpoj()
    except Exception:  # noqa: BLE001 - zavírání nesmí nikdy vyhodit výjimku
        pass


def pujc(ucet, heslo: str) -> PujcenaSchranka:
    """Půjčí spojení ke schránce. Použij výhradně jako kontextový manažer."""
    if not heslo:
        raise ImapChyba(
            "Ke schránce není uložené heslo – zadej ho znovu v nastavení e-mailu."
        )
    return PujcenaSchranka(ucet, heslo)


def zahod(ucet_id: int) -> None:
    """Zavře a zapomene spojení schránky.

    Volá se po změně hesla nebo serveru: staré spojení je přihlášené starými
    údaji a dál by fungovalo, takže by se změna „neprojevila" až do restartu.
    """
    with _zamek_mapy:
        d = _drzaky.pop(int(ucet_id), None)
    if d is None:
        return
    # O zámek se čeká jen chvíli – když ho někdo drží, spojení dozavírá sám tím,
    # že jsme držák vyhodili z mapy a nikdo další ho nedostane.
    if d.zamek.acquire(timeout=5):
        try:
            if d.spojeni is not None:
                _zavri(d.spojeni)
                d.spojeni = None
        finally:
            d.zamek.release()


def zahod_vse() -> None:
    """Zavře všechna spojení – při vypínání appky."""
    with _zamek_mapy:
        ids = list(_drzaky.keys())
    for ucet_id in ids:
        zahod(ucet_id)
