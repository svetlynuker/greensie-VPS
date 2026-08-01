"""HTML podpis do odchozí pošty – generuje se z profilu uživatele.

Předloha je `docs/moduly/email/greensie_podpis_generator_9.html` (samostatný
generátor, ze kterého si lidé podpis kopírovali do Outlooku a Seznamu). Tady je
tatáž vizuální podoba přenesená na server, aby se podpis **skládal sám** z toho,
co má člověk vyplněné v profilu, a nemusel se nikam kopírovat.

---- Tři vědomé odchylky od předlohy ---------------------------------------
1. **Ikony sociálních sítí vypadly.** V předloze se kreslily v prohlížeči přes
   `<canvas>` do base64 PNG. Na serveru není canvas a Dan je 1. 8. 2026 označil
   za nepotřebné. Kdyby se měly vrátit, patří sem jako hotové obrázky na webu
   (jako logo a ikonky kontaktů), ne jako generovaná grafika.
2. **Adresy obrázků jdou přímo na web Greensie.** Předloha měla odkazy přes
   `ci3.googleusercontent.com/...#https://...` — to je Gmailí obrázková proxy
   a mimo Gmail je nespolehlivá. Používá se to, co bylo v předloze za `#`,
   tedy skutečný zdroj.
3. **Telefon je proklik `tel:`.** V předloze byl jen text; Dan chtěl telefon,
   e-mail i web interaktivní.

---- Proč tabulky a inline styly -------------------------------------------
Protože to čtou poštovní klienti, ne prohlížeč. Outlook renderuje HTML přes
Word: `flexbox`, `grid` ani `<style>` v hlavičce nefungují spolehlivě. Layout
tabulkou a styly v atributu `style` jsou u podpisů standard, ne zaostalost.
"""

import html
import re

# Obrázky na webu Greensie. Poštovní klient si je stáhne sám – proto tu nejsou
# jako přílohy: podpis s pěti přílohami by u každé zprávy ukazoval sponku.
LOGO_URL = "https://www.greensie-fotovoltaika.cz/wp-content/uploads/logo_greensie.png"
IKONA_TELEFON = "https://www.greensie-fotovoltaika.cz/wp-content/uploads/phone-icon-dark-2x.png"
IKONA_EMAIL = "https://www.greensie-fotovoltaika.cz/wp-content/uploads/email-icon-dark-2x.png"
IKONA_WEB = "https://www.greensie-fotovoltaika.cz/wp-content/uploads/link-icon-dark-2x.png"

WEB_ADRESA = "https://www.greensie.cz/"
WEB_POPISEK = "www.greensie.cz"
ZELENA = "rgb(114,193,70)"


def _e(text: str) -> str:
    """Escapuje text do HTML. Jméno s `&` nebo `<` nesmí rozbít podpis."""
    return html.escape(str(text or ""), quote=True)


def cislice_telefonu(surove: str) -> str:
    """Z libovolného zápisu vytáhne devět číslic českého čísla.

    `+420 773 492 029`, `773492029` i `00420773492029` dají totéž. Ukládá se
    devět číslic, předvolba se doplňuje až při vykreslení – jinak by se v datech
    míchaly tři různé zápisy téhož čísla.
    """
    d = re.sub(r"\D", "", surove or "")
    if d.startswith("00420"):
        d = d[5:]
    elif d.startswith("420") and len(d) > 9:
        d = d[3:]
    if d.startswith("0") and len(d) > 9:
        d = d[1:]
    return d[:9]


def formatuj_telefon(surove: str) -> str:
    """`773492029` → `+420 773 492 029`. Prázdné vrací prázdné."""
    d = cislice_telefonu(surove)
    if not d:
        return ""
    trojice = [d[i : i + 3] for i in range(0, len(d), 3)]
    return "+420 " + " ".join(trojice)


def telefon_pro_odkaz(surove: str) -> str:
    """`773492029` → `+420773492029` pro `tel:` (bez mezer, s předvolbou)."""
    d = cislice_telefonu(surove)
    return f"+420{d}" if d else ""


def cele_jmeno(profil) -> str:
    """`Daniel Lupínek` z křestního a příjmení. Prázdné, když není nic."""
    if profil is None:
        return ""
    return " ".join(x for x in [(profil.jmeno or "").strip(), (profil.prijmeni or "").strip()] if x)


def profil_je_vyplneny(profil) -> bool:
    """Má profil dost na to, aby se dal podpis složit?

    Stačí jméno. Bez něj by podpis byl jen logo a odkaz na web, což je horší
    než žádný podpis – vypadalo by to jako chyba.
    """
    return bool(profil is not None and cele_jmeno(profil))


def sestav_html(profil, email: str) -> str:
    """HTML podpis. Vrací prázdný řetězec, když není z čeho skládat.

    `email` je adresa schránky, ze které se odesílá — ne adresa odvozená ze
    jména. Kdo píše z jiné schránky, má mít v podpisu tu, na kterou mu přijde
    odpověď.
    """
    if not profil_je_vyplneny(profil):
        return ""

    jmeno = _e(cele_jmeno(profil))
    funkce = (profil.funkce or "").strip()
    telefon_text = formatuj_telefon(profil.telefon)
    telefon_odkaz = telefon_pro_odkaz(profil.telefon)
    adresa = _e((email or "").strip())
    pozdrav = (profil.pozdrav or "").strip()

    # Zelená linka je pod posledním řádkem hlavičky: bez funkce pod jménem,
    # s funkcí až pod ní. Jinak by čára visela uprostřed jména a funkce.
    ramecek_jmena = "" if funkce else f"border-bottom:2px solid {ZELENA};"

    blok_pozdravu = (
        f'<p style="text-align:left;margin:0 0 16px 0;">'
        f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        f'color:rgb(0,0,0);">{_e(pozdrav)}</span></p>'
        if pozdrav
        else ""
    )

    blok_funkce = (
        f'<div style="text-align:left;line-height:24px;margin:0;padding-bottom:4px;'
        f'border-bottom:2px solid {ZELENA};font-size:14px;">'
        f'<span style="font-family:Arial,Helvetica,sans-serif;color:rgb(0,0,0);">'
        f"{_e(funkce)}</span></div>"
        if funkce
        else ""
    )

    radky = []
    if telefon_text:
        radky.append(
            _radek_kontaktu(
                IKONA_TELEFON,
                "tel",
                f'<a href="tel:{_e(telefon_odkaz)}" style="color:rgb(0,0,0);'
                f'text-decoration:none;">{_e(telefon_text)}</a>',
            )
        )
    if adresa:
        radky.append(
            _radek_kontaktu(
                IKONA_EMAIL,
                "e-mail",
                f'<a href="mailto:{adresa}" style="color:rgb(0,0,0);'
                f'text-decoration:none;">{adresa}</a>',
            )
        )
    radky.append(
        _radek_kontaktu(
            IKONA_WEB,
            "web",
            f'<a href="{WEB_ADRESA}" target="_blank" rel="noopener noreferrer" '
            f'style="color:rgb(0,0,0);text-decoration:none;">{WEB_POPISEK}</a>',
        )
    )

    return (
        f"{blok_pozdravu}"
        '<div style="background-color:rgb(255,255,255);">'
        '<table border="0" cellspacing="0" cellpadding="0" style="text-align:left;">'
        "<tbody><tr>"
        '<td style="text-align:center;vertical-align:middle;">'
        f'<img src="{LOGO_URL}" width="100" alt="Greensie" '
        'style="width:100px;max-width:130px;display:block;border:0;"></td>'
        '<td style="width:15px;"></td>'
        '<td style="text-align:left;vertical-align:middle;">'
        f'<h2 style="text-align:left;line-height:24px;margin:0;padding-bottom:4px;'
        f"{ramecek_jmena}font-family:Arial,Helvetica,sans-serif;font-size:18px;"
        f'font-weight:bold;color:rgb(0,0,0);">{jmeno}</h2>'
        f"{blok_funkce}"
        '<table border="0" cellspacing="0" cellpadding="0" style="text-align:left;'
        'line-height:1;"><tbody>'
        f"{''.join(radky)}"
        "</tbody></table>"
        "</td></tr></tbody></table></div>"
    )


def _radek_kontaktu(ikona: str, popis: str, obsah: str) -> str:
    return (
        "<tr>"
        '<td style="vertical-align:middle;width:26px;height:28px;">'
        f'<img src="{ikona}" alt="{popis}" width="18" '
        'style="width:18px;display:block;border:0;"></td>'
        '<td style="line-height:1;height:28px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;'
        f'color:rgb(0,0,0);">{obsah}</div></td>'
        "</tr>"
    )


def sestav_text(profil, email: str) -> str:
    """Textová podoba téhož podpisu – pro klienty, které HTML nezobrazí.

    Není to náhradní řešení navíc: každá zpráva odchází jako text i HTML
    (multipart/alternative). Kdyby textová část podpis neměla, člověk se
    starým klientem by dostal zprávu bez podpisu.
    """
    if not profil_je_vyplneny(profil):
        return ""
    radky = []
    pozdrav = (profil.pozdrav or "").strip()
    if pozdrav:
        radky += [pozdrav, ""]
    radky.append(cele_jmeno(profil))
    funkce = (profil.funkce or "").strip()
    if funkce:
        radky.append(funkce)
    radky.append("Greensie s.r.o.")
    telefon = formatuj_telefon(profil.telefon)
    if telefon:
        radky.append(telefon)
    if (email or "").strip():
        radky.append(email.strip())
    radky.append(WEB_POPISEK)
    return "\n".join(radky)


def pracovni_adresa(profil) -> str:
    """`Daniel Lupínek` → `daniel.lupinek@greensie.cz`.

    Předloha tímhle vyplňovala e-mail v podpisu. Tady se **nepoužívá** pro
    samotný podpis (tam patří adresa schránky, na kterou přijde odpověď), ale
    hodí se v nastavení jako nápověda „takhle by tvoje adresa měla vypadat".
    """
    import unicodedata

    def bez_diakritiky(s: str) -> str:
        rozlozeno = unicodedata.normalize("NFD", s or "")
        cisty = "".join(z for z in rozlozeno if not unicodedata.combining(z))
        return re.sub(r"[^a-z]", "", cisty.lower())

    if profil is None:
        return ""
    casti = [
        bez_diakritiky(profil.jmeno or ""),
        bez_diakritiky(profil.prijmeni or ""),
    ]
    casti = [c for c in casti if c]
    return ".".join(casti) + "@greensie.cz" if casti else ""
