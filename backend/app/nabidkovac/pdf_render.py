"""Vykreslení HTML na PDF headless Chromiem — spouští se jako VLASTNÍ PROCES.

Čte HTML ze stdin, na stdout vrací bajty PDF. Nic víc; kdo ho volá a proč, je
v `pdf.py`.

---- Proč vlastní proces a ne funkce v backendu ---------------------------

Chromium si při vykreslení vezme stovky MB paměti a VPS má 4 GB, ze kterých
běží i Postgres a stahování pošty. Ve web procesu by to (a) drželo paměť
i po dokončení, (b) při dvou nabídkách naráz appku dotlačilo k 502 — stejný
důvod, proč e-mailový klient běží jako samostatná služba. Jako podproces se
paměť vrátí systému hned, jak PDF odejde.

---- Proč PDF vyrábí prohlížeč, a ne knihovna ------------------------------

Papír nabídky je React: rozvržení v mm, grafy jako SVG, barvy z CSS tokenů.
Kdyby PDF skládala Python knihovna (WeasyPrint), musela by se celá ta sazba
napsat podruhé a od té chvíle by se rozcházela s tím, co obchodník vidí na
obrazovce. Chromium dostane přesně to HTML, které je v prohlížeči, takže PDF
je totožné s náhledem — a `page.pdf()` navíc rovnou tiskne v režimu `print`,
takže platí `@media print` pravidla z `vystup.css`.
"""

import sys


def vykresli(html: str) -> bytes:
    """HTML → bajty PDF (A4, na výšku, s barevnými podklady)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # `--disable-dev-shm-usage`: /dev/shm je na VPS malý a Chromium v něm
        # jinak dojede uprostřed vykreslování. `--no-sandbox`: běžíme pod
        # systémovým uživatelem bez userns; sandbox by proces nespustil.
        prohlizec = p.chromium.launch(
            args=["--disable-dev-shm-usage", "--no-sandbox", "--font-render-hinting=none"]
        )
        try:
            stranka = prohlizec.new_page()
            # `wait_until="load"` čeká i na obrázky. Ty jsou v HTML jako data:
            # URI, takže se nic netahá ze sítě — jen se dokreslí.
            stranka.set_content(html, wait_until="load")
            return stranka.pdf(
                # Rozměr bere z `@page { size: A4 portrait }` v našem CSS;
                # `format` je záloha, kdyby pravidlo z výstupu vypadlo.
                format="A4",
                prefer_css_page_size=True,
                print_background=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
        finally:
            prohlizec.close()


def main() -> int:
    html = sys.stdin.read()
    if not html.strip():
        sys.stderr.write("Prázdné HTML na vstupu.\n")
        return 2
    sys.stdout.buffer.write(vykresli(html))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
