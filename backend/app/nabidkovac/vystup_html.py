"""Čištění formátovaného textu z nabídkového editoru.

Editor výstupu píše text přímo na papíře (contentEditable), takže do backendu
přitéká HTML – včetně toho, co uživatel vloží z Wordu nebo z webu. Než se to
uloží do DB a znovu vykreslí v prohlížeči, musí projít whitelistem: povolené
tagy, povolené vlastnosti ve `style`, nic jiného.

Vlastní sanitizér na stdlib `HTMLParser` schválně – `bleach` by byla další
závislost k udržování a potřebujeme jen malý pevně daný whitelist. Frontend
čistí tentýž vstup taky (hned při vložení), ale tohle je poslední slovo:
klientovi se nevěří, protože PUT na API může poslat kdokoli s přihlášením.
"""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

# Tagy, které smí projít. Jde o formátování odstavce, nic víc – žádné odkazy
# (nabídka se tiskne), žádné obrázky (ty jsou vlastní druh prvku), žádné
# tabulky (taky vlastní prvek), a hlavně žádné script/style/iframe.
POVOLENE_TAGY = frozenset(
    {"p", "br", "div", "span", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
     "h1", "h2", "h3", "h4"}
)

# Tagy bez koncové značky – nesmí se jim dopisovat </br>.
PRAZDNE_TAGY = frozenset({"br"})

# U těchhle se zahodí i vnitřek. Jinde text nepovoleného tagu schválně
# zachováváme (odstavec z Wordu obalený ve <font> má přijít o formátování,
# ne o obsah), ale u skriptu je „obsah“ zrovna to nebezpečné.
POLYKANE_TAGY = frozenset({"script", "style", "title", "textarea", "noscript"})

# Jediný povolený atribut je `style`, a i v něm jen tyhle vlastnosti. Pořadí
# nehraje roli, kontroluje se po rozpadu na `vlastnost: hodnota`.
POVOLENE_STYLY = frozenset(
    {"color", "background-color", "font-size", "font-weight", "font-style",
     "text-decoration", "text-align", "font-family"}
)

# Hodnota stylu smí být jen barva, rozměr, klíčové slovo nebo název písma.
# Schválně úzké: `url(...)`, `expression(...)` ani `\` se sem nevejdou, takže
# přes style nejde propašovat načtení cizího zdroje.
_HODNOTA_OK = re.compile(r"^[#a-zA-Z0-9 ,.%()\-'\"]+$")
_ZAKAZANE_V_HODNOTE = re.compile(r"url\s*\(|expression|javascript:|@import|/\*", re.I)

# Písmo omezíme na rodiny, které umíme vytisknout – jinak by PDF vypadalo
# na každém počítači jinak.
POVOLENA_PISMA = ("inherit", "sans-serif", "serif", "monospace", "arial",
                  "helvetica", "georgia", "times new roman", "courier new")

MAX_DELKA_HTML = 20_000


def _styl_ok(vlastnost: str, hodnota: str) -> bool:
    if vlastnost not in POVOLENE_STYLY:
        return False
    if not hodnota or len(hodnota) > 120:
        return False
    if _ZAKAZANE_V_HODNOTE.search(hodnota):
        return False
    if not _HODNOTA_OK.match(hodnota):
        return False
    if vlastnost == "font-family":
        # Stačí, aby první rodina v seznamu byla známá; zbytek je fallback.
        prvni = hodnota.split(",")[0].strip().strip("'\"").lower()
        return prvni in POVOLENA_PISMA
    return True


def _vycisti_style(hodnota: str) -> str:
    """Nechá ze `style` jen povolené dvojice. Vrací "" když nezbude nic."""
    kusy = []
    for cast in hodnota.split(";"):
        if ":" not in cast:
            continue
        vlastnost, _, val = cast.partition(":")
        vlastnost = vlastnost.strip().lower()
        val = val.strip()
        if _styl_ok(vlastnost, val):
            kusy.append(f"{vlastnost}: {val}")
    return "; ".join(kusy)


class _Cistic(HTMLParser):
    """Přepíše vstup na povolenou podmnožinu HTML.

    Nepovolený tag se zahodí i s koncovou značkou, ale jeho **text zůstane** –
    když někdo vloží odstavec z Wordu obalený v `<font>`, přijít o obsah by
    bylo horší než přijít o formátování.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # Zásobník otevřených povolených tagů, ať se koncové značky párují
        # a nezavře se něco, co jsme neotevřeli.
        self._otevrene: list[str] = []
        # Kolik úrovní polykaného tagu jsme uvnitř (text se zahazuje).
        self._polykame = 0

    def handle_starttag(self, tag: str, atrs) -> None:
        tag = tag.lower()
        if tag in POLYKANE_TAGY:
            self._polykame += 1
            return
        if self._polykame or tag not in POVOLENE_TAGY:
            return
        styl = ""
        for jmeno, hodnota in atrs:
            if jmeno.lower() == "style" and hodnota:
                styl = _vycisti_style(hodnota)
        atribut = f' style="{escape(styl, quote=True)}"' if styl else ""
        if tag in PRAZDNE_TAGY:
            self.out.append(f"<{tag}{atribut}>")
            return
        self._otevrene.append(tag)
        self.out.append(f"<{tag}{atribut}>")

    def handle_startendtag(self, tag: str, atrs) -> None:
        if tag.lower() in PRAZDNE_TAGY:
            self.out.append(f"<{tag.lower()}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in POLYKANE_TAGY:
            self._polykame = max(0, self._polykame - 1)
            return
        if self._polykame or tag in PRAZDNE_TAGY or tag not in POVOLENE_TAGY:
            return
        if tag not in self._otevrene:
            return
        # Zavřeme i vše, co zůstalo otevřené uvnitř (křížené tagy z Wordu).
        while self._otevrene:
            posledni = self._otevrene.pop()
            self.out.append(f"</{posledni}>")
            if posledni == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._polykame:
            return
        self.out.append(escape(data, quote=False))

    def vysledek(self) -> str:
        while self._otevrene:
            self.out.append(f"</{self._otevrene.pop()}>")
        return "".join(self.out)


def vycisti_html(vstup: str | None) -> str:
    """Vrátí bezpečnou podobu formátovaného textu z editoru.

    Prázdný vstup vrací "" – prvek s prázdným textem je legitimní stav
    (čerstvě položený text, do kterého se ještě nepsalo).
    """
    if not vstup:
        return ""
    text = str(vstup)[:MAX_DELKA_HTML]
    cistic = _Cistic()
    cistic.feed(text)
    cistic.close()
    return cistic.vysledek()


def html_na_text(vstup: str | None) -> str:
    """Holý text bez značek – pro délkové kontroly a vyhledávání."""
    if not vstup:
        return ""
    return re.sub(r"<[^>]*>", "", str(vstup))


MAX_DELKA_HODNOTY = 120


def prosty_text(vstup: str | None, max_delka: int = MAX_DELKA_HODNOTY) -> str:
    """Jednořádkový text bez značek – pro ručně přepsanou hodnotu dlaždice.

    Hodnota se na papíře vykresluje jako text (ne HTML), takže tady nejde
    o whitelist značek jako u odstavců, ale o to, aby v ní neuvízl zlomek
    značky ani konec řádku: dlaždice má jeden řádek a přetečení by uřízl
    `overflow: hidden` papíru.
    """
    if not vstup:
        return ""
    text = re.sub(r"<[^>]*>", "", str(vstup))
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:max_delka]
