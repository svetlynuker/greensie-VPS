"""Import spotových (day-ahead) cen elektřiny do appky.

Spouštět z adresáře backend/ (s aktivním venv):
    python -m scripts.import_spot_ceny --rok 2025 --csv        # vytvoří datový soubor
    python -m scripts.import_spot_ceny --rok 2025 --do-db      # nahraje do DB
    python -m scripts.import_spot_ceny --z-csv --do-db         # nahraje přiložená data

Zdroje (viz docs/reserze_kalkulator/spot-arbitraz-cr-2025.md):
- ceny: api.energy-charts.info (day-ahead česká nabídková zóna, EUR/MWh) –
  ověřeno proti OTE, rozdíl 0,00 EUR/MWh,
- kurz: denní kurzy ČNB (EUR) – převod na Kč/MWh se dělá kurzem dne dodávky,
  stejně jako OTE zúčtovává.

Appce stačí datový soubor `app/nabidkovac/data/spot_dam_cz_<rok>.csv.gz`, takže
produkce nemusí při seedu chodit na internet. Stahování je potřeba jen když se
přidává nový rok.
"""
import argparse
import csv
import datetime
import gzip
import io
import json
import urllib.request
from pathlib import Path

CESTA_DATA = Path(__file__).resolve().parent.parent / "app" / "nabidkovac" / "data"

URL_CENY = "https://api.energy-charts.info/price?bzn={zona}&start={start}&end={end}"
URL_KURZY = (
    "https://www.cnb.cz/cs/financni-trhy/devizovy-trh/kurzy-devizoveho-trhu/"
    "kurzy-devizoveho-trhu/rok.txt?rok={rok}"
)


def _stahni(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=180) as odpoved:  # noqa: S310 (pevné URL)
        return odpoved.read()


def stahni_kurzy_eur(rok: int) -> dict[datetime.date, float]:
    """Denní kurzy EUR z ČNB (`Datum|…|1 EUR|…`, desetinná čárka)."""
    text = _stahni(URL_KURZY.format(rok=rok)).decode("utf-8")
    radky = [r for r in text.splitlines() if r.strip()]
    hlavicka = radky[0].split("|")
    idx = hlavicka.index("1 EUR")
    out: dict[datetime.date, float] = {}
    for radek in radky[1:]:
        casti = radek.split("|")
        den = datetime.datetime.strptime(casti[0], "%d.%m.%Y").date()
        out[den] = float(casti[idx].replace(",", "."))
    return out


def stahni_ceny(rok: int, zona: str = "CZ") -> list[tuple[int, int, float]]:
    """Day-ahead ceny roku → [(unix_s, interval_min, cena_eur_mwh)].

    Zdroj vrací hodinové hodnoty do 30. 9. 2025 a 15minutové od 1. 10. 2025
    (přechod SDAC na 15min obchodní intervaly). Interval se odvozuje z rozdílu
    časových značek, poslední bod dědí interval předchozího.
    """
    surova = json.loads(
        _stahni(
            URL_CENY.format(
                zona=zona,
                start=f"{rok}-01-01",
                end=f"{rok + 1}-01-02",  # okraj kvůli časové zóně
            )
        )
    )
    casy = surova["unix_seconds"]
    ceny = surova["price"]
    out: list[tuple[int, int, float]] = []
    for i, (cas, cena) in enumerate(zip(casy, ceny)):
        if cena is None:
            continue
        if i + 1 < len(casy):
            interval_s = casy[i + 1] - cas
        else:
            interval_s = out[-1][1] * 60 if out else 3600
        out.append((int(cas), max(15, int(round(interval_s / 60))), float(cena)))
    return out


def _kurz_dne(kurzy: dict[datetime.date, float], den: datetime.date) -> float:
    """Kurz dne; o víkendech a svátcích ČNB nekótuje → poslední předchozí."""
    hledany = den
    for _ in range(10):
        if hledany in kurzy:
            return kurzy[hledany]
        hledany -= datetime.timedelta(days=1)
    if kurzy:
        return kurzy[min(kurzy)]
    raise ValueError("Nemám žádné kurzy ČNB.")


def cesta_csv(rok: int, zona: str = "CZ") -> Path:
    return CESTA_DATA / f"spot_dam_{zona.lower()}_{rok}.csv.gz"


def zapis_csv(rok: int, zona: str = "CZ") -> Path:
    """Stáhne rok a uloží ho jako `spot_dam_cz_<rok>.csv.gz`.

    Sloupce: `unix_s;interval_min;eur_mwh;kc_mwh`. Ukládají se **skutečné
    intervaly zdroje** (hodinové i čtvrthodinové) – rozpad na čtvrthodiny řeší
    až appka, aby se v datech nic needuplikovalo.
    """
    ceny = stahni_ceny(rok, zona)
    kurzy = stahni_kurzy_eur(rok)
    CESTA_DATA.mkdir(parents=True, exist_ok=True)
    cesta = cesta_csv(rok, zona)
    buf = io.StringIO()
    zapis = csv.writer(buf, delimiter=";", lineterminator="\n")
    zapis.writerow(["unix_s", "interval_min", "eur_mwh", "kc_mwh"])
    for unix_s, interval_min, eur in ceny:
        den = datetime.datetime.fromtimestamp(unix_s, datetime.timezone.utc).date()
        kurz = _kurz_dne(kurzy, den)
        zapis.writerow([unix_s, interval_min, f"{eur:.4f}", f"{eur * kurz:.4f}"])
    with gzip.open(cesta, "wt", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    return cesta


def main():
    parser = argparse.ArgumentParser(description="Import spotových cen elektřiny")
    parser.add_argument("--rok", type=int, help="rok ke stažení (např. 2025)")
    parser.add_argument("--zona", default="CZ", help="nabídková zóna (default CZ)")
    parser.add_argument(
        "--csv", action="store_true", help="stáhnout a uložit datový soubor CSV.gz"
    )
    parser.add_argument(
        "--z-csv", action="store_true", help="importovat z přiloženého CSV.gz (bez internetu)"
    )
    parser.add_argument("--do-db", action="store_true", help="nahrát ceny do tabulky spotove_ceny")
    args = parser.parse_args()

    if args.csv:
        if not args.rok:
            parser.error("--csv vyžaduje --rok")
        cesta = zapis_csv(args.rok, args.zona)
        print(f"Uloženo: {cesta} ({cesta.stat().st_size / 1024:.0f} kB)")

    if args.do_db:
        # Import až tady, ať `--csv` funguje i bez nastavené databáze.
        from app.database import SessionLocal
        from app.nabidkovac import spot_ceny

        db = SessionLocal()
        try:
            if args.rok and not args.z_csv:
                pocet = spot_ceny.uloz_do_db(db, stahni_ceny(args.rok, args.zona), args.zona)
            else:
                pocet = spot_ceny.seed_z_datovych_souboru(db, jen_rok=args.rok)
            print(f"Do DB uloženo/aktualizováno {pocet} intervalů.")
        finally:
            db.close()


if __name__ == "__main__":
    main()
