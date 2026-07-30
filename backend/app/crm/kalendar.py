"""Kalendář aktivit: čas, viditelnost cizích událostí a týdenní rozsahy.

Kalendář nekreslí jen aktivity — kreslí i to, co člověk vidět NEMÁ, jako
obsazený čas. Proto je tady jedno místo, které rozhoduje, kolik se o cizí
události prozradí, a jedno místo, které řeší čas. Kdyby se pravidla
viditelnosti psala v routes u každého endpointu, dřív nebo později by jedno
místo prozradilo víc než ostatní.

---- Viditelnost (zadání Dana, 30. 7. 2026) ----------------------------------

| Situace                                   | Co se pošle             |
|-------------------------------------------|-------------------------|
| moje událost                              | celý detail             |
| cizí SOUKROMÁ                             | jen blok „Soukromá…"    |
| cizí běžná, jsem účastník                 | celý detail             |
| cizí běžná, mám `crm_vse` (vedení, admin) | celý detail             |
| cizí běžná, jsem OZ a nejsem účastník     | jen blok „Obsazeno"     |

Dvě věci, které z toho snadno vypadnou:

1. **Soukromou událost nevidí ani vedení, ani admin.** Je to jediné místo v CRM,
   kde `crm_vse` nestačí — a je to schválně: dovolená a doktor nejsou firemní
   data. Vedení vidí jen obsazený čas, aby vědělo, kdy člověk nemůže.
2. **Blok se nesmí posílat s obsahem.** Neposílá se text, výsledek ani zákazník
   — schovat je až v prohlížeči by znamenalo, že si je kdokoli přečte
   v odpovědi API.

---- Čas ---------------------------------------------------------------------

`termin` je den, `zacatek` je hodina (viz docstring `CrmAktivita`). Jediné
místo, které to drží v souladu, je `srovnej_termin()` — volá se při každém
uložení aktivity.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from app.auth.models import User
from app.crm.models import CrmAktivita
from app.crm.pristup import muze_vse

# Jak dlouho trvá aktivita, když délku nikdo nezadal. Podle druhu, protože
# telefonát na hodinu by v kalendáři zabral místo, které není potřeba.
VYCHOZI_DELKA_MIN = {
    "telefon": 15,
    "email": 15,
    "dopis": 15,
    "schuzka": 60,
    "udalost": 60,  # porada, školení — plánuje se na hodiny, ne na minuty
    "ukol": 30,
    "poznamka": 30,
}
VYCHOZI_DELKA_JINE = 30

# Co se pošle místo obsahu u události, kterou člověk vidět nemá.
POPIS_SOUKROMA = "Soukromá událost"
POPIS_OBSAZENO = "Obsazeno"


def vychozi_delka(druh: str) -> int:
    return VYCHOZI_DELKA_MIN.get(druh, VYCHOZI_DELKA_JINE)


def srovnej_termin(a: CrmAktivita) -> None:
    """Dopočítá `termin` ze `zacatek` a doplní chybějící délku.

    Proč to musí být na jednom místě: `termin` (den) je zdroj pravdy pro výpis
    „moje úkoly" i pro Rozcestník, kdežto `zacatek` (hodina) potřebuje jen
    kalendář. Kdyby si je někdo nastavil rozdílně, událost by v kalendáři byla
    ve čtvrtek a v úkolech ve středu — a nikdo by nepoznal, který údaj lže.
    """
    if a.zacatek is not None:
        a.termin = a.zacatek.date()
        if not a.delka_min or a.delka_min <= 0:
            a.delka_min = vychozi_delka(a.druh)


def zacatek_tydne(den: date) -> date:
    """Pondělí týdne, do kterého datum padá (týden v ČR začíná pondělím)."""
    return den - timedelta(days=(den.weekday()))


def rozsah_tydne(den: date) -> tuple[date, date]:
    """(pondělí, nedělě) týdne, do kterého datum padá."""
    po = zacatek_tydne(den)
    return po, po + timedelta(days=6)


def v_rozsahu(q: Query, od: date, do: date) -> Query:
    """Omezí dotaz na aktivity, které do rozsahu dnů zasahují.

    Filtruje se podle `termin`, ne podle `zacatek` — právě proto se `termin`
    dopočítává. Díky tomu se do kalendáře dostanou i celodenní úkoly, které
    hodinu nemají, a nemusí se skládat dva dotazy.

    Pozor na VÍCEDENNÍ aktivity: školení od pátku do středy začíná před
    zobrazeným týdnem, ale do něj zasahuje. Proto se nehledá „termín v okně",
    ale „interval se s oknem překrývá" — jinak by týdenní pohled takovou
    aktivitu neukázal a člověk by si naplánoval schůzku doprostřed školení.
    """
    return q.filter(
        CrmAktivita.termin.isnot(None),
        CrmAktivita.termin <= do,
        func.coalesce(CrmAktivita.konec, CrmAktivita.termin) >= od,
    )


def muze_menit(a: CrmAktivita, user: User) -> bool:
    """Smí uživatel aktivitu upravit (přesunout, uzavřít, smazat)?

    Stejné pravidlo jako pro vidění detailu: vlastník, autor, účastník, nebo
    kdo má `crm_vse` — a u soukromé události jen ti první tři. Vedení tak může
    podřízenému přesunout schůzku, ale ne hrabat mu do dovolené.

    Je to schválně jediné pravidlo pro čtení i zápis: kdyby se rozdělila,
    vznikl by stav „vidím detail, ale nemůžu s ním nic udělat", který v UI
    nejde vysvětlit.
    """
    return _cely_detail(a, user)


def _cely_detail(a: CrmAktivita, user: User) -> bool:
    """Smí tenhle uživatel vidět obsah události, nebo jen obsazený čas?"""
    if a.vlastnik_user_id == user.id or a.vytvoril_user_id == user.id:
        return True
    if user.id in list(a.ucastnici or []):
        return True
    # Soukromou událost `crm_vse` NEODEMYKÁ — jediná výjimka v celém CRM.
    if a.soukroma:
        return False
    return muze_vse(user)


def pro_uzivatele(a: CrmAktivita, user: User) -> dict:
    """Aktivita připravená pro kalendář daného uživatele.

    Vrací slovník, ze kterého se skládá `KalendarUdalostOut`. U události, na
    kterou uživatel nemá nárok, se obsah vůbec NEPŘENÁŠÍ — pošle se jen čas,
    délka a komu patří (jméno je potřeba, protože se srovnávají kalendáře víc
    lidí a bez jména by se bloky nedaly rozřadit).
    """
    zaklad = {
        "id": a.id,
        "zacatek": a.zacatek.isoformat() if a.zacatek else None,
        "termin": a.termin.isoformat() if a.termin else None,
        "delka_min": a.delka_min or vychozi_delka(a.druh),
        "cely_den": a.zacatek is None,
        "konec": a.konec.isoformat() if a.konec else None,
        # Vícedenní = má konec, který je po termínu. Kalendář z toho kreslí pruh
        # v řádku „vícedenní" místo dlaždice v mřížce hodin.
        "vicedenni": bool(a.konec and a.termin and a.konec > a.termin),
        "priorita": a.priorita or "stredni",
        "vlastnik_user_id": a.vlastnik_user_id,
        "vlastnik_jmeno": (a.vlastnik.jmeno if a.vlastnik else None),
    }

    if not _cely_detail(a, user):
        return {
            **zaklad,
            "druh": "poznamka",  # neutrální — druh sám prozrazuje, co se děje
            "nazev": POPIS_SOUKROMA if a.soukroma else POPIS_OBSAZENO,
            "text": "",
            "vysledek": "",
            "stav": a.stav,
            # Ani místo a štítek se u bloku neposílají – adresa schůzky
            # prozrazuje, kde a s kým člověk je.
            "misto": "",
            "kategorie_nazev": "",
            "kategorie_barva": "",
            "soukroma": a.soukroma,
            "entita": None,
            "zaznam_id": None,
            "zaznam_nazev": "",
            "cesta": "",
            "ucastnici": [],
            "muze_detail": False,
        }

    return {
        **zaklad,
        "druh": a.druh,
        # U starších aktivit, které vznikly před kalendářem, název není —
        # použije se začátek textu, ať dlaždice není prázdná.
        "nazev": a.nazev or (a.text or "").strip().split("\n")[0][:80],
        "text": a.text or "",
        "vysledek": a.vysledek or "",
        "stav": a.stav,
        "misto": a.misto or "",
        "kategorie_nazev": (a.kategorie.nazev if a.kategorie else ""),
        "kategorie_barva": (a.kategorie.barva if a.kategorie else ""),
        "soukroma": a.soukroma,
        "entita": a.entita,
        "zaznam_id": a.zaznam_id,
        # Odkaz na záznam doplňuje `udalosti_pro()` jedním dotazem na entitu.
        # Výchozí prázdno tu MUSÍ být: soukromá událost žádný záznam nemá,
        # takže by u ní klíč jinak chyběl a skládání odpovědi by spadlo.
        "zaznam_nazev": "",
        "cesta": "",
        "ucastnici": list(a.ucastnici or []),
        "muze_detail": True,
    }


def viditelne_pro(db: Session, user: User, user_ids: list[int]) -> Query:
    """Dotaz na aktivity vybraných lidí, které se smí do kalendáře dostat.

    Vrací i cizí události, ke kterým uživatel nemá detail — právě proto, aby
    v kalendáři bylo vidět obsazené místo. Kolik se z nich prozradí, řeší
    `pro_uzivatele()`; tenhle dotaz jen vybírá řádky.

    Cizí SOUKROMÉ události se nevyfiltrují ani tady: „kdy nemůže" je informace,
    kterou vedení i kolega při hledání termínu potřebují. Prozradí se z nich
    ale jen čas.
    """
    q = db.query(CrmAktivita)
    if not user_ids:
        return q.filter(False)
    return q.filter(
        or_(
            CrmAktivita.vlastnik_user_id.in_(user_ids),
            *([CrmAktivita.ucastnici.any(user.id)] if user.id in user_ids else []),
        )
    )


def udalosti_pro(db: Session, user: User, radky: list[CrmAktivita]) -> list[dict]:
    """Seznam aktivit → události pro kalendář, včetně odkazu na záznam.

    Odkazy se dotahují jedním dotazem na entitu (mapa `ukoly.ENTITY`), a to
    **až po** rozhodnutí o viditelnosti: u události, ze které se posílá jen
    obsazený čas, by název zákazníka prozradil přesně to, co se má schovat.
    """
    from app.crm import ukoly as ukoly_modul

    hotove = [pro_uzivatele(a, user) for a in radky]

    # Které záznamy je vůbec potřeba pojmenovat (jen ty s detailem).
    podle_entity: dict[str, set[int]] = {}
    for u in hotove:
        if u["muze_detail"] and u["entita"] and u["zaznam_id"]:
            podle_entity.setdefault(u["entita"], set()).add(u["zaznam_id"])
    popisy = {
        e: ukoly_modul.popisy_zaznamu(db, e, ids) for e, ids in podle_entity.items()
    }

    for u in hotove:
        if u["muze_detail"] and u["entita"] and u["zaznam_id"]:
            u["zaznam_nazev"] = popisy.get(u["entita"], {}).get(
                u["zaznam_id"], f"#{u['zaznam_id']}"
            )
            u["cesta"] = ukoly_modul.cesta_zaznamu(u["entita"], u["zaznam_id"])
    return hotove


def datum_a_cas(den: date, cas_text: str | None) -> datetime | None:
    """„2026-08-03" + „09:30" → datetime. Bez času vrací None (celodenní)."""
    if not cas_text:
        return None
    try:
        h, m = (int(x) for x in str(cas_text).split(":")[:2])
    except (TypeError, ValueError):
        return None
    return datetime.combine(den, time(hour=h, minute=m))
