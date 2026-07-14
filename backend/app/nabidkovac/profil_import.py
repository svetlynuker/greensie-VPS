"""Načtení 15minutového profilu odběru z nahraného souboru (peak shaving).

Vstupem je typicky XLS export „PND" z portálu distributora (list `export`,
sloupce `Datum` + `Profil +A [kW]` + `Status`, ~34 944 řádků na rok), případně
XLSX nebo CSV se stejnou logikou. Výstupem je seznam dvojic (čas, kW), který
plní tabulku `spotreba_profil`, nad níž pak počítá jádro peak shavingu.

Bere se ČINNÝ výkon `+A [kW]` (odběr), ne jalový (Ri/Rc). Hlavička se hledá
dynamicky, ať to snese drobné odchylky exportu (pořadí/prázdné úvodní řádky).
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


def _najdi_sloupce(radek: list) -> tuple[int, int]:
    """Z hlavičky najde index sloupce s činným výkonem (kW) a příslušného data.

    Preferuje `+A ... kW` (činný odběr); jinak první sloupec s „kW". Datum bere
    z nejbližšího sloupce nalevo obsahujícího „datum"/„čas", jinak o jeden vlevo.
    Vyhodí ValueError, když sloupec s výkonem není → řádek to není hlavička.
    """
    nizke = [str(h).strip().lower() for h in radek]
    kw_idx = None
    for i, h in enumerate(nizke):
        if "+a" in h and "kw" in h:
            kw_idx = i
            break
    if kw_idx is None:
        for i, h in enumerate(nizke):
            if "kw" in h:
                kw_idx = i
                break
    if kw_idx is None:
        raise ValueError("nenalezen sloupec s činným výkonem (kW)")

    datum_idx = None
    for i in range(kw_idx - 1, -1, -1):
        if "datum" in nizke[i] or "čas" in nizke[i] or "cas" in nizke[i]:
            datum_idx = i
            break
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
