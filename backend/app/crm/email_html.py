"""Čištění HTML z editoru a jeho převod na čistý text.

Tělo zprávy se od zavedení formátovacího editoru posílá jako HTML. To znamená
dvě povinnosti, které nejdou obejít:

1. **Vyčistit ho na serveru.** Ne proto, že by uživatel chtěl škodit — ale
   protože do editoru se vkládá text z Wordu, z webu a z jiných mailů, a s ním
   přilétá všechno od `<script>` po `<o:p>` a kilometry `mso-` stylů. Prohlížeč
   se čistit dá požádat, ale spolehnout se na něj nelze: požadavek jde přes
   HTTP a kdokoli s tokenem může poslat cokoli.
2. **Vyrobit textovou variantu.** Každá zpráva odchází jako text i HTML; kdyby
   textová část chyběla nebo byla prázdná, klient bez HTML by dostal nic.

---- Proč vlastní čistička a ne knihovna ------------------------------------
Do requirements se kvůli tomuhle nepřidává závislost (`bleach` a spol.).
Rozsah je úzký a známý: povolený seznam značek, které dávají v e-mailu smysl.
Parsuje se `html.parser` ze standardní knihovny, ne regulárními výrazy —
regulárkou se HTML čistit nedá a je to klasický zdroj děr.

---- Princip: co není dovoleno, je zakázáno --------------------------------
Whitelist, ne blacklist. Neznámá značka se zahodí (obsah se zachová),
neznámý atribut taky. Blacklist by znamenal, že každá nová vymyšlenost
projde, dokud si jí někdo nevšimne.
"""

import re
from html import escape
from html.parser import HTMLParser

# Značky, které v e-mailu dávají smysl a klienti je umí. Cokoli mimo seznam se
# zahodí, ale jeho **obsah zůstane** – smazat text kvůli neznámé obálce by bylo
# horší než ztráta formátování.
POVOLENE_ZNACKY = {
    "p", "br", "div", "span", "b", "strong", "i", "em", "u", "s", "strike", "del",
    "ul", "ol", "li", "a", "blockquote", "h1", "h2", "h3", "h4", "hr",
    "table", "thead", "tbody", "tr", "td", "th", "img", "font", "sub", "sup",
    "pre", "code",
}

# Značky, které se zahazují **i s obsahem**. `<script>` je zřejmý; `<style>`
# proto, že styly v hlavičce stejně půlka klientů zahodí a Word jich vkládá
# desítky kilobajtů.
ZNACKY_I_S_OBSAHEM = {"script", "style", "head", "title", "iframe", "object", "embed", "applet"}

# Značky bez uzavíracího tagu.
PRAZDNE_ZNACKY = {"br", "hr", "img"}

# Atributy povolené globálně a pak zvlášť pro konkrétní značky.
GLOBALNI_ATRIBUTY = {"style", "title", "dir"}
ATRIBUTY_ZNACKY = {
    "a": {"href", "target", "rel"},
    "img": {"src", "alt", "width", "height"},
    "table": {"width", "border", "cellpadding", "cellspacing", "align", "bgcolor"},
    "td": {"width", "height", "align", "valign", "colspan", "rowspan", "bgcolor"},
    "th": {"width", "height", "align", "valign", "colspan", "rowspan", "bgcolor"},
    "tr": {"align", "valign", "bgcolor"},
    "font": {"color", "face", "size"},
    "ol": {"start", "type"},
    "ul": {"type"},
    "div": {"align"},
    "p": {"align"},
    "h1": {"align"}, "h2": {"align"}, "h3": {"align"}, "h4": {"align"},
}

# Vlastnosti v `style`, které projdou. Zbytek (hlavně `position`, `mso-*`
# a Wordovské nesmysly) se zahodí.
POVOLENE_STYLY = {
    "color", "background-color", "background", "font-size", "font-family",
    "font-weight", "font-style", "font-variant", "text-decoration",
    "text-decoration-line", "text-align", "text-indent", "line-height",
    "margin", "margin-top", "margin-bottom", "margin-left", "margin-right",
    "padding", "padding-top", "padding-bottom", "padding-left", "padding-right",
    "border", "border-top", "border-bottom", "border-left", "border-right",
    "border-color", "border-width", "border-style", "border-collapse",
    "list-style-type", "list-style-position", "width", "height", "max-width",
    "min-width", "vertical-align", "display", "white-space", "letter-spacing",
}

# Schémata odkazů, která smí ven. `javascript:` a `data:` v odkazu jsou útok.
POVOLENA_SCHEMATA = ("http://", "https://", "mailto:", "tel:", "#")
# U obrázků navíc `data:image/…` (vložený obrázek) a `cid:` (příloha ve zprávě).
POVOLENA_SCHEMATA_OBRAZKU = ("http://", "https://", "data:image/", "cid:")

_RE_NEBEZPECNA_HODNOTA = re.compile(r"(javascript|vbscript|expression|behavior)\s*:", re.I)
_RE_MSO = re.compile(r"^(mso-|-ms-|panose)", re.I)


def _bezpecna_url(url: str, obrazek: bool = False) -> str:
    """Vrací URL, nebo prázdno, když je schéma nepřípustné."""
    cista = (url or "").strip().replace("\x00", "")
    # Bílé znaky uvnitř schématu (`java\nscript:`) jsou klasický obcházecí trik.
    bez_mezer = re.sub(r"\s+", "", cista).lower()
    if _RE_NEBEZPECNA_HODNOTA.search(bez_mezer):
        return ""
    povolena = POVOLENA_SCHEMATA_OBRAZKU if obrazek else POVOLENA_SCHEMATA
    if bez_mezer.startswith(povolena):
        return cista
    # Relativní adresa nemá v e-mailu kam vést – zahodíme ji.
    return ""


def _cisty_styl(styl: str) -> str:
    """Ze `style` nechá jen povolené vlastnosti s neškodnými hodnotami."""
    kusy = []
    for deklarace in (styl or "").split(";"):
        if ":" not in deklarace:
            continue
        vlastnost, _, hodnota = deklarace.partition(":")
        vlastnost = vlastnost.strip().lower()
        hodnota = hodnota.strip()
        if not vlastnost or not hodnota:
            continue
        if _RE_MSO.match(vlastnost) or vlastnost not in POVOLENE_STYLY:
            continue
        if _RE_NEBEZPECNA_HODNOTA.search(hodnota) or "url(" in hodnota.lower():
            continue
        kusy.append(f"{vlastnost}:{hodnota}")
    return ";".join(kusy)


class _Cistic(HTMLParser):
    """Projde HTML a poskládá nové, ve kterém je jen to, co je na seznamu."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.kusy: list[str] = []
        # Kolik úrovní zahazované značky (i s obsahem) jsme uvnitř.
        self._hloubka_zahozeni = 0
        # Zásobník otevřených povolených značek, aby se správně uzavřely.
        self._otevrene: list[str] = []

    # -- značky ---------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in ZNACKY_I_S_OBSAHEM:
            self._hloubka_zahozeni += 1
            return
        if self._hloubka_zahozeni:
            return
        if tag not in POVOLENE_ZNACKY:
            return  # obálku zahodíme, obsah proteče dál

        atributy = self._cisté_atributy(tag, attrs)
        # Obrázek, kterému čištění zahodilo `src` (nepovolené schéma), by
        # v mailu byl prázdný rámeček s křížkem – radši ho zahodit celý.
        if tag == "img" and not atributy.get("src"):
            return
        if tag == "a":
            # Odkaz z mailu se má otevřít v novém okně a bez předání refereru.
            atributy.setdefault("target", "_blank")
            atributy.setdefault("rel", "noopener noreferrer")

        zapis = "".join(f' {k}="{escape(v, quote=True)}"' for k, v in atributy.items() if v)
        if tag in PRAZDNE_ZNACKY:
            self.kusy.append(f"<{tag}{zapis}>")
        else:
            self.kusy.append(f"<{tag}{zapis}>")
            self._otevrene.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if self._hloubka_zahozeni or tag not in POVOLENE_ZNACKY:
            return
        atributy = self._cisté_atributy(tag, attrs)
        zapis = "".join(f' {k}="{escape(v, quote=True)}"' for k, v in atributy.items() if v)
        self.kusy.append(f"<{tag}{zapis}>")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ZNACKY_I_S_OBSAHEM:
            self._hloubka_zahozeni = max(0, self._hloubka_zahozeni - 1)
            return
        if self._hloubka_zahozeni or tag not in POVOLENE_ZNACKY or tag in PRAZDNE_ZNACKY:
            return
        if tag in self._otevrene:
            # Uzavřeme i vše, co zůstalo otevřené uvnitř (rozbité HTML z Wordu).
            while self._otevrene:
                posledni = self._otevrene.pop()
                self.kusy.append(f"</{posledni}>")
                if posledni == tag:
                    break

    def handle_data(self, data):
        if self._hloubka_zahozeni:
            return
        self.kusy.append(escape(data, quote=False))

    # Komentáře pryč – Word jich vkládá spoustu a `<!--[if mso]>` umí zlobit.
    def handle_comment(self, data):
        return

    def _cisté_atributy(self, tag: str, attrs) -> dict:
        povolene = GLOBALNI_ATRIBUTY | ATRIBUTY_ZNACKY.get(tag, set())
        vysledek: dict[str, str] = {}
        for jmeno, hodnota in attrs:
            jmeno = (jmeno or "").lower()
            hodnota = hodnota or ""
            # `on*` (onclick, onerror…) nikdy, ani kdyby se dostaly na seznam.
            if jmeno.startswith("on") or jmeno not in povolene:
                continue
            if jmeno == "href":
                hodnota = _bezpecna_url(hodnota)
            elif jmeno == "src":
                hodnota = _bezpecna_url(hodnota, obrazek=True)
            elif jmeno == "style":
                hodnota = _cisty_styl(hodnota)
            elif _RE_NEBEZPECNA_HODNOTA.search(hodnota):
                continue
            if hodnota:
                vysledek[jmeno] = hodnota
        return vysledek

    def vysledek(self) -> str:
        # Doavřít, co zůstalo otevřené.
        while self._otevrene:
            self.kusy.append(f"</{self._otevrene.pop()}>")
        return "".join(self.kusy)


def vycisti(html: str) -> str:
    """Vrátí HTML jen s povolenými značkami, atributy a styly."""
    if not (html or "").strip():
        return ""
    c = _Cistic()
    try:
        c.feed(html)
        c.close()
    except Exception:  # noqa: BLE001 - rozbité HTML nesmí shodit odeslání
        # Když se parsování rozsype, radši pošleme text bez formátování než nic.
        return escape(na_text(html), quote=False).replace("\n", "<br>")
    return c.vysledek().strip()


# ---- převod na čistý text ----------------------------------------------------
# `li` tu schválně NENÍ: zalomení před odrážku přidává `_RE_LI`, jinak by
# mezi položkami seznamu vznikl prázdný řádek navíc.
_RE_BLOK = re.compile(r"(?i)</(p|div|h[1-4]|tr|blockquote|pre|ul|ol|table)\s*>")
_RE_BR = re.compile(r"(?i)<br\s*/?>")
_RE_LI = re.compile(r"(?i)<li[^>]*>")
_RE_ZNACKA = re.compile(r"<[^>]+>")
_RE_PRAZDNE_RADKY = re.compile(r"\n{3,}")


def na_text(html: str) -> str:
    """HTML → čitelný text pro `text/plain` část zprávy.

    Není to dokonalý převod a ani nemá být: jde o to, aby příjemce se starým
    klientem přečetl obsah. Odrážky dostanou pomlčku, bloky se oddělí řádkem,
    u odkazů se za text doplní adresa (jinak by v textové verzi zmizela).
    """
    if not (html or "").strip():
        return ""
    t = html
    # Zahodit obsah značek, které nenesou text.
    t = re.sub(r"(?is)<(script|style|head|title)[^>]*>.*?</\1\s*>", " ", t)
    # Odkaz: „popisek (adresa)", ale jen když se liší – jinak dvakrát totéž.
    def _odkaz(m):
        url = m.group(1).strip()
        popis = _RE_ZNACKA.sub("", m.group(2)).strip()
        if not popis:
            return url
        if url.startswith("mailto:") and url[7:] == popis:
            return popis
        if url.rstrip("/") == popis.rstrip("/"):
            return popis
        return f"{popis} ({url})"

    t = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a\s*>', _odkaz, t)
    t = _RE_LI.sub("\n- ", t)
    t = _RE_BR.sub("\n", t)
    t = _RE_BLOK.sub("\n", t)
    t = _RE_ZNACKA.sub("", t)

    from html import unescape

    t = unescape(t).replace("\xa0", " ")
    # Uklidit mezery na koncích řádků a víc než dva prázdné řádky za sebou.
    t = "\n".join(r.rstrip() for r in t.splitlines())
    t = _RE_PRAZDNE_RADKY.sub("\n\n", t)
    return t.strip()


def je_prazdne(html: str) -> bool:
    """Je tělo prakticky prázdné? (`<p><br></p>` z editoru = prázdno.)"""
    return not na_text(html).strip()


def citace_html(od: str, kdy: str, telo_html: str) -> str:
    """Původní zpráva jako citace pod odpovědí – odsazený blok se svislou linkou.

    Tak to dělá každý poštovní klient a příjemce to pozná na první pohled.
    Obsah se čistí stejně jako všechno ostatní: citovaná zpráva přišla zvenčí.
    """
    hlavicka = escape(f"{kdy} {od} napsal(a):", quote=False)
    return (
        f'<div style="margin-top:16px;">{hlavicka}</div>'
        '<blockquote style="margin:8px 0 0 0;padding-left:12px;'
        'border-left:2px solid #c4cdc7;color:#4b5852;">'
        f"{vycisti(telo_html)}"
        "</blockquote>"
    )
