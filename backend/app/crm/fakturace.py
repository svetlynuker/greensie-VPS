"""Fakturace CRM objednávky – řetěz objednávka → faktura → zaplaceno (CRM-09).

Faktury žijí v tabulce `faktury` sdílené s Přehledem financí (Pohled 2).
Rozdíl je jen v rodiči: starý svět má `projekt_id` (projekt z Freela), nový
`crm_objednavka_id`. Jedna tabulka je vědomé rozhodnutí Dana z 31. 7. 2026 –
párování s POHODOU přes variabilní symbol se tak píše jednou a vedení má
peníze na jedné obrazovce.

Co tenhle modul dělá: skládá souhrn (vyfakturováno / zaplaceno / zbývá) a umí
rozepsat cenu objednávky do splátek podle předvolby. Vlastní API je
v `routes_realizace.py`.
"""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.finance.models import SPLATKOVE_SABLONY, Faktura

# Stavy, které znamenají „peníze jsou naúčtované" a „peníze dorazily".
STAVY_VYFAKTUROVANO = ("vystaveno", "zaplaceno")
STAV_ZAPLACENO = "zaplaceno"
# Faktura, kterou se rozhodli nefakturovat, nesmí kazit součty.
STAV_NEFAKTURUJE = "nefakturuje"

_HALERE = Decimal("0.01")


def _dec(x) -> Decimal:
    if x is None:
        return Decimal("0")
    return x if isinstance(x, Decimal) else Decimal(str(x))


def po_terminu(f: Faktura, dnes: date | None = None) -> bool:
    """Faktura po splatnosti, která ještě není zaplacená.

    Počítá se i faktura, která ještě nebyla vystavena – právě ta je problém:
    termín utekl a nikdo ji nevystavil.
    """
    if f.stav in (STAV_ZAPLACENO, STAV_NEFAKTURUJE) or f.termin is None:
        return False
    return f.termin < (dnes or date.today())


def souhrn(faktury: list[Faktura], cena_objednavky) -> dict:
    """Sečte fakturaci objednávky.

    `zbyva_fakturovat_kc` je cena objednávky minus všechny rozepsané faktury
    (i ty, které ještě nikdo nevystavil) – to je číslo, které obchodník
    potřebuje: „mám celou zakázku pokrytou fakturami?“. Když objednávka cenu
    nemá, vrací se None místo záporného nesmyslu.
    """
    vyfakturovano = Decimal("0")
    zaplaceno = Decimal("0")
    rozepsano = Decimal("0")
    prosle = Decimal("0")

    for f in faktury:
        if f.stav == STAV_NEFAKTURUJE:
            continue
        castka = _dec(f.castka)
        rozepsano += castka
        if f.stav in STAVY_VYFAKTUROVANO:
            vyfakturovano += castka
        if f.stav == STAV_ZAPLACENO:
            zaplaceno += castka
        if po_terminu(f):
            prosle += castka

    cena = _dec(cena_objednavky) if cena_objednavky is not None else None
    zbyva = None if cena is None else (cena - rozepsano).quantize(_HALERE)
    # Korunová tolerance: rozdělení 100 % na třetiny nikdy nevyjde na haléř.
    nesedi = bool(cena is not None and faktury and abs(zbyva) > Decimal("1"))

    return {
        "pocet": len([f for f in faktury if f.stav != STAV_NEFAKTURUJE]),
        "vyfakturovano_kc": float(vyfakturovano),
        "zaplaceno_kc": float(zaplaceno),
        "zbyva_fakturovat_kc": float(zbyva) if zbyva is not None else None,
        "po_terminu_kc": float(prosle),
        "nesedi_soucet": nesedi,
    }


def rozdel_castku(cena, podily: list[float]) -> list[Decimal]:
    """Rozdělí cenu podle procent tak, aby součet seděl na haléř.

    Poslední splátka dostane zbytek – jinak by 3× 33,33 % z milionu dalo
    999 990 Kč a chyběla by desetikoruna, kterou by pak někdo hledal
    v účetnictví.
    """
    celkem = _dec(cena)
    castky: list[Decimal] = []
    rozdano = Decimal("0")
    for i, podil in enumerate(podily):
        if i == len(podily) - 1:
            castka = celkem - rozdano
        else:
            castka = (celkem * _dec(podil) / Decimal("100")).quantize(
                _HALERE, rounding=ROUND_HALF_UP
            )
            rozdano += castka
        castky.append(castka)
    return castky


def sablony_pro_frontend() -> list[dict]:
    """Předvolby splátek pro výběr v UI."""
    return [
        {
            "klic": klic,
            "nazev": data["nazev"],
            "splatky": [{"nazev": n, "podil_procent": p} for n, p in data["splatky"]],
        }
        for klic, data in SPLATKOVE_SABLONY.items()
    ]


def zaloz_ze_sablony(
    db: Session,
    objednavka,
    klic_sablony: str,
    prvni_termin: date | None,
    nahradit: bool,
) -> list[Faktura]:
    """Rozepíše cenu objednávky do splátek podle předvolby.

    `nahradit=True` smaže dosud NEVYSTAVENÉ faktury a rozepíše je znovu.
    Vystavené a zaplacené se nemažou nikdy – to už je doklad, ne plán.
    """
    sablona = SPLATKOVE_SABLONY.get(klic_sablony)
    if sablona is None:
        raise ValueError(f"Neznámá šablona splátek: {klic_sablony}")

    stavajici = list(objednavka.faktury)
    if nahradit:
        for f in stavajici:
            if f.stav == "potreba_vystavit":
                db.delete(f)
        stavajici = [f for f in stavajici if f.stav != "potreba_vystavit"]

    podily = [p for _, p in sablona["splatky"]]
    castky = rozdel_castku(objednavka.cena_kc, podily) if objednavka.cena_kc else [None] * len(podily)

    dalsi_poradi = max((f.poradi for f in stavajici), default=0) + 1
    nove: list[Faktura] = []
    for i, ((nazev, podil), castka) in enumerate(zip(sablona["splatky"], castky)):
        f = Faktura(
            crm_objednavka_id=objednavka.id,
            poradi=dalsi_poradi + i,
            nazev=nazev,
            podil_procent=podil,
            castka=castka,
            # Splátky po měsíci od prvního termínu – běžný splátkový kalendář
            # u realizace. Kdo to má jinak, termíny přepíše.
            termin=(prvni_termin + timedelta(days=30 * i)) if prvni_termin else None,
        )
        db.add(f)
        nove.append(f)
    return nove


def prepocti_podle_podilu(faktury: list[Faktura], cena_objednavky) -> int:
    """Přepočítá částky faktur podle uložených podílů (změnila se cena).

    Sahá jen na faktury ve stavu „potřeba vystavit“ – vystavenou fakturu
    appka měnit nesmí, i kdyby se cena objednávky změnila. Vrací počet
    upravených řádků.
    """
    upravitelne = [
        f for f in faktury if f.stav == "potreba_vystavit" and f.podil_procent is not None
    ]
    if not upravitelne or cena_objednavky is None:
        return 0

    # Každá faktura dostane svůj podíl z NOVÉ ceny – stejně, jako když vznikla.
    # Nedopočítává se zbytek po vystavených fakturách: kdyby už byla záloha
    # vystavená na starou cenu, appka to radši ukáže jako „součet nesedí“, než
    # aby ticho dorovnala doplatek a nikdo si změny nevšiml.
    #
    # Pozor: nejde použít `rozdel_castku` po jedné faktuře – ta poslední
    # splátce dává celý zbytek, takže by každá dostala plnou cenu. Zbytkové
    # haléře se dorovnají na poslední upravitelné faktuře níž.
    celkem = _dec(cena_objednavky)
    for f in upravitelne:
        f.castka = (celkem * _dec(f.podil_procent) / Decimal("100")).quantize(
            _HALERE, rounding=ROUND_HALF_UP
        )

    # Když jsou upravitelné VŠECHNY faktury a jejich podíly dávají 100 %,
    # musí součet sednout na haléř – dorovná se na poslední.
    if len(upravitelne) == len(faktury):
        soucet_podilu = sum(_dec(f.podil_procent) for f in upravitelne)
        if soucet_podilu == Decimal("100"):
            rozdil = celkem - sum(_dec(f.castka) for f in upravitelne)
            upravitelne[-1].castka = _dec(upravitelne[-1].castka) + rozdil

    return len(upravitelne)
