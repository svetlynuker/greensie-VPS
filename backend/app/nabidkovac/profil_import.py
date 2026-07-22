"""Načtení 15minutového profilu odběru z nahraného souboru (peak shaving).

Vstupem je typicky XLS export „PND" z portálu distributora (list `export`,
sloupce `Datum` + `Profil +A [kW]` + `Status`, ~34 944 řádků na rok), případně
XLSX nebo CSV se stejnou logikou. Výstupem je seznam dvojic (čas, kW), který
plní tabulku `spotreba_profil`, nad níž pak počítá jádro peak shavingu.

Bere se ČINNÝ VÝKON v kW (odběr), ne energie ani jalovina. Export PRE má jiný
tvar než PND – vedle sloupce `Činný - výkon [kW]` nese i `Činná - spotřeba [kWh]`
a čas jako `Počátek/Konec intervalu` (žádný sloupec „Datum"). Sloupec `[kWh]`
obsahuje podřetězec „kw", takže se dřív omylem načetla energie místo výkonu
(hodnoty ×4 nafouknuté) – proto se energie [kWh] a jalovina [kVAr] z výběru
výslovně vylučují. Hlavička se hledá dynamicky, ať to snese drobné odchylky
exportu (pořadí/prázdné úvodní řádky).
"""

from __future__ import annotations

import csv as _csv
from datetime import datetime

# Formáty data, se kterými se v exportech setkáváme (PND: DD.MM.RRRR HH:MM:SS).
_FORMATY_DATA = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_datum(v) -> datetime | None:
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    if not s:
        return None
    for f in _FORMATY_DATA:
        try:
            return datetime.strptime(s, f)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


# Klíčová slova hlavičky časového sloupce. PRE nemá „Datum", jen
# „Počátek/Konec intervalu" – bereme POČÁTEK čtvrthodiny (konec ignorujeme).
_DATUM_KLICE = ("počátek", "pocatek", "začátek", "zacatek", "datum", "čas", "cas", "interval")


def _je_sloupec_vykonu_kw(h: str) -> bool:
    """Hlavička činného výkonu v kW? Vyloučí energii [kWh] i jalovinu [kVAr].

    `[kWh]` obsahuje podřetězec „kw", takže bez tohoto vyloučení se u PRE
    exportu načte sloupec spotřeby v kWh místo výkonu v kW (hodnoty ×4).
    """
    return "kw" in h and "kwh" not in h and "kvar" not in h


def _najdi_sloupce(radek: list) -> tuple[int, int]:
    """Z hlavičky najde index sloupce s činným výkonem (kW) a příslušného data.

    Výkon: preferuje `+A … kW` (PND), pak `… výkon … kW` (PRE), pak první
    sloupec s kW – vždy jen skutečný výkon (energie [kWh] ani jalovina [kVAr]
    se neberou). Datum: nejbližší sloupec nalevo s datovým klíčovým slovem,
    s předností „počátku" intervalu před „koncem"; fallback o jeden vlevo.
    Vyhodí ValueError, když sloupec s výkonem není → řádek to není hlavička.
    """
    nizke = [str(h).strip().lower() for h in radek]
    kw_idx = None
    for i, h in enumerate(nizke):
        if "+a" in h and _je_sloupec_vykonu_kw(h):
            kw_idx = i
            break
    if kw_idx is None:
        for i, h in enumerate(nizke):
            if "výkon" in h and _je_sloupec_vykonu_kw(h):
                kw_idx = i
                break
    if kw_idx is None:
        for i, h in enumerate(nizke):
            if _je_sloupec_vykonu_kw(h):
                kw_idx = i
                break
    if kw_idx is None:
        raise ValueError("nenalezen sloupec s činným výkonem (kW)")

    # Datum: kandidáti nalevo od výkonu; přednost počátku intervalu, jinak
    # první, který není „konec", jinak první kandidát, jinak o sloupec vlevo.
    kandidati = [i for i in range(kw_idx) if any(k in nizke[i] for k in _DATUM_KLICE)]
    datum_idx = next(
        (i for i in kandidati if any(k in nizke[i] for k in ("počátek", "pocatek", "začátek", "zacatek"))),
        None,
    )
    if datum_idx is None:
        datum_idx = next((i for i in kandidati if "konec" not in nizke[i]), None)
    if datum_idx is None and kandidati:
        datum_idx = kandidati[0]
    if datum_idx is None:
        datum_idx = kw_idx - 1 if kw_idx > 0 else 0
    return datum_idx, kw_idx


def _radky_xls(cesta: str):
    import xlrd

    wb = xlrd.open_workbook(cesta)
    sh = wb.sheet_by_index(0)
    for r in range(sh.nrows):
        yield [sh.cell_value(r, c) for c in range(sh.ncols)]


def _radky_xlsx(cesta: str):
    import openpyxl

    wb = openpyxl.load_workbook(cesta, read_only=True, data_only=True)
    sh = wb.active
    for row in sh.iter_rows(values_only=True):
        yield list(row)


def _radky_csv(cesta: str):
    with open(cesta, newline="", encoding="utf-8-sig") as fh:
        vzorek = fh.read(4096)
        fh.seek(0)
        try:
            dialekt = _csv.Sniffer().sniff(vzorek, delimiters=";,\t")
        except _csv.Error:
            dialekt = _csv.excel
        for row in _csv.reader(fh, dialekt):
            yield row


def nacti_profil(cesta: str, pripona: str) -> list[tuple[datetime, float]]:
    """Načte profil ze souboru → seznam (čas, kW). Vyhodí ValueError při chybě formátu."""
    pripona = (pripona or "").lower()
    if pripona == ".xls":
        radky = _radky_xls(cesta)
    elif pripona == ".xlsx":
        radky = _radky_xlsx(cesta)
    elif pripona == ".csv":
        radky = _radky_csv(cesta)
    else:
        raise ValueError(f"nepodporovaná přípona profilu: {pripona or '(žádná)'}")

    radky = iter(radky)
    datum_idx = kw_idx = None
    for row in radky:
        try:
            datum_idx, kw_idx = _najdi_sloupce(row)
            break
        except ValueError:
            continue
    if kw_idx is None:
        raise ValueError("nepodařilo se najít hlavičku se sloupci Datum a Profil +A [kW]")

    body: list[tuple[datetime, float]] = []
    for row in radky:
        if kw_idx >= len(row) or datum_idx >= len(row):
            continue
        cas = _parse_datum(row[datum_idx])
        hod = _to_float(row[kw_idx])
        if cas is None or hod is None:
            continue
        body.append((cas, hod))

    if not body:
        raise ValueError("soubor neobsahuje žádné použitelné 15min hodnoty odběru")
    return body


def deduplikuj_casy(
    body: list[tuple[datetime, float]],
) -> tuple[list[tuple[datetime, float]], int]:
    """Sloučí řádky se shodným časem – z duplicit zůstane nejvyšší kW (SP-2).

    Podzimní přechod času má v lokálním čase duplicitní hodinu 02:00–03:00
    (v exportech OTE konvence 92/100 čtvrthodin) → 4 duplicitní čtvrthodiny
    ročně jsou legitimní; výrazně víc obvykle znamená dvakrát vložený rozsah.
    Maximum (místo součtu) volíme konzervativně: nezdvojí energii a nepodstřelí
    špičku. Vrací (body v pořadí prvního výskytu, počet sloučených řádků).
    """
    podle_casu: dict[datetime, float] = {}
    poradi: list[datetime] = []
    for cas, kw in body:
        if cas in podle_casu:
            podle_casu[cas] = max(podle_casu[cas], kw)
        else:
            podle_casu[cas] = kw
            poradi.append(cas)
    return [(c, podle_casu[c]) for c in poradi], len(body) - len(poradi)
