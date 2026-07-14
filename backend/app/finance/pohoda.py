"""Klient Pohoda API – KOSTRA (napojení zatím není aktivní).

Toto je nová integrace, kterou appka zatím neměla. Struktura kopíruje styl
`matice/freelo.py` (modulové funkce, jen čtení, přístupy z .env). Reálná HTTP
volání se doplní, až bude známý typ nasazení Pohody (typicky tzv. mServer –
lokální XML rozhraní Pohody) a přístupové údaje.

Do .env (na serveru, je v .gitignore) se přidají proměnné:
    POHODA_URL    – adresa API (mServer), např. http://127.0.0.1:1234/xml
    POHODA_LOGIN  – přihlašovací jméno k mServeru
    POHODA_HESLO  – heslo k mServeru
    POHODA_ICO    – IČO firmy, na kterou se dotaz váže

Dokud tyhle proměnné nejsou vyplněné, appka funguje s ručním nastavováním
stavů faktur a synchronizace se chová jako "vypnutá".

Párování: faktura z Pohody se spáruje s naší fakturou přes shodu variabilního
symbolu (viz Faktura.variabilni_symbol), který se ručně zapisuje do Freela.
Pohoda je zdroj pravdy jen o tom, že faktura byla vystavena/zaplacena –
nikdy do ní nezapisujeme.
"""

import os

# Proměnné, které musí být v .env, aby se dala Pohoda použít.
POVINNE_ENV = ("POHODA_URL", "POHODA_LOGIN", "POHODA_HESLO", "POHODA_ICO")


def je_nakonfigurovano() -> bool:
    """True, jen když jsou v .env vyplněné všechny přístupy k Pohodě."""
    return all(os.environ.get(k) for k in POVINNE_ENV)


def nacti_faktury_dle_vs(variabilni_symboly: list[str]) -> dict[str, dict]:
    """Vrátí stav faktur z Pohody namapovaný podle variabilního symbolu.

    Cílový tvar (až bude napojení hotové):
        { "2026001": {"vystaveno": True, "zaplaceno": False,
                       "datum_vystaveni": "2026-01-15", "datum_zaplaceni": None} }

    Zatím jen kostra – reálné XML volání na mServer se doplní později.
    """
    if not je_nakonfigurovano():
        return {}

    # TODO: sestavit XML dotaz (listInvoiceRequest) na POHODA_URL, HTTP Basic
    # auth (POHODA_LOGIN/POHODA_HESLO), hlavička STW-Application/ICO, a z odpovědi
    # vytáhnout faktury a jejich stav. Do té doby nic nevracíme.
    raise NotImplementedError(
        "Pohoda: reálné volání API zatím není implementováno – čeká na "
        "dodání typu nasazení a přístupů."
    )
