"""Spotové (day-ahead) ceny elektřiny – uložení, seed a napárování na profil.

Ceny jsou vstupem pro režimy „Kombinace" a „SPOT" peak shaving kalkulátoru
(rešerše: `docs/reserze_kalkulator/spot-arbitraz-cr-2025.md`). Modul drží
všechno, co souvisí s **daty**; ekonomika a optimalizace jsou v `spot_arbitraz.py`.

Dvě věci, které tu stojí za pozornost:

1. **Granularita.** Denní trh v ČR přešel na 15minutové obchodní intervaly
   1. 10. 2025; do té doby byly ceny hodinové. V DB se drží tak, jak je vydal
   trh (`interval_min`), a na čtvrthodiny se rozpadají až při čtení – jinak by
   se data zbytečně čtyřnásobila a nešlo by poznat, co je skutečná cena.

2. **Rok profilu ≠ rok cen.** Profil odběru zákazníka je typicky z jiného roku
   než referenční ceny. Páruje se proto **podle typu dne** (měsíc + den v týdnu),
   ne podle kalendářního data – jinak by pracovní den zákazníka mohl dostat ceny
   nedělního sedla a výsledek by byl náhodný (viz `ceny_pro_casy`).
"""

from __future__ import annotations

import csv
import datetime
import gzip
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.nabidkovac.models import SpotovaCena

# Trh, ze kterého ceny jsou. Zatím jediný; klíč je v datech kvůli budoucímu
# vnitrodennímu trhu (ten je mimo scope – viz rešerše kap. 9).
TRH_DAM_CZ = "dam_cz"

# Časová zóna, ve které žijí profily odběru (naive lokální čas z XLS exportu
# distributora) i obchodní intervaly trhu.
ZONA = ZoneInfo("Europe/Prague")

CESTA_DATA = Path(__file__).resolve().parent / "data"

# Interval, na který se ceny rozpadají (profily odběru jsou 15minutové vždy).
INTERVAL_MIN = 15


@dataclass
class RadaCen:
    """Rozpadnutá řada cen jednoho roku, připravená k párování na profil.

    `podle_dne` = {datum → {(hodina, minuta) → cena Kč/MWh}}; `dny_dle_typu` =
    {(měsíc, den v týdnu) → [data]} pro párování profilu z jiného roku.
    """

    rok: int
    trh: str
    podle_dne: dict[datetime.date, dict[tuple[int, int], float]]
    dny_dle_typu: dict[tuple[int, int], list[datetime.date]]

    @property
    def pocet_intervalu(self) -> int:
        return sum(len(v) for v in self.podle_dne.values())


# ----------------------------------------------------------------- ukládání
def uloz_do_db(db: Session, ceny: list[tuple[int, int, float]], zona: str = "CZ",
               kurzy: dict[datetime.date, float] | None = None,
               trh: str = TRH_DAM_CZ, zdroj: str = "energy-charts") -> int:
    """Uloží `[(unix_s, interval_min, cena_eur_mwh)]` do `spotove_ceny`.

    Idempotentně (`ON CONFLICT` na `(trh, cas_utc)` = přepíše cenu). Bez kurzů
    se Kč nedopočítávají – ty přidává `seed_z_datovych_souboru`, které je má
    v datovém souboru.
    """
    if not ceny:
        return 0
    radky = []
    for unix_s, interval_min, eur in ceny:
        cas = datetime.datetime.fromtimestamp(unix_s, datetime.timezone.utc)
        kc = None
        if kurzy is not None:
            kc = eur * kurzy.get(cas.date(), 0.0)
        radky.append(
            {
                "trh": trh,
                "cas_utc": cas,
                "interval_min": interval_min,
                "cena_eur_mwh": eur,
                "cena_kc_mwh": kc,
                "zdroj": zdroj,
            }
        )
    return _vloz_radky(db, radky)


def _vloz_radky(db: Session, radky: list[dict]) -> int:
    """Hromadný upsert po dávkách (35 tis. řádků na rok).

    Klíč je `(trh, cas_utc)` – opakovaný import stejného roku ceny přepíše
    (třeba když se přepočítají kurzem, který ČNB dodatečně opravila).
    """
    for i in range(0, len(radky), 2000):
        davka = radky[i : i + 2000]
        prikaz = pg_insert(SpotovaCena).values(davka)
        db.execute(
            prikaz.on_conflict_do_update(
                index_elements=[SpotovaCena.trh, SpotovaCena.cas_utc],
                set_={
                    "interval_min": prikaz.excluded.interval_min,
                    "cena_eur_mwh": prikaz.excluded.cena_eur_mwh,
                    "cena_kc_mwh": prikaz.excluded.cena_kc_mwh,
                    "zdroj": prikaz.excluded.zdroj,
                },
            )
        )
    db.commit()
    return len(radky)


def datove_soubory() -> list[Path]:
    """Přiložené datové soubory cen (`spot_dam_cz_<rok>.csv.gz`)."""
    if not CESTA_DATA.is_dir():
        return []
    return sorted(CESTA_DATA.glob("spot_dam_*_*.csv.gz"))


def _rok_ze_jmena(cesta: Path) -> int | None:
    zaklad = cesta.name.removesuffix(".csv.gz")
    try:
        return int(zaklad.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return None


def seed_z_datovych_souboru(db: Session, jen_rok: int | None = None) -> int:
    """Naseeduje ceny z přiložených CSV.gz (idempotentně, bez internetu).

    Volá se při startu appky. Když už jsou ceny daného roku v DB v plném počtu,
    soubor se přeskočí – seed tak nezdržuje každý restart (35 tis. řádků na rok).
    """
    vlozeno = 0
    for cesta in datove_soubory():
        rok = _rok_ze_jmena(cesta)
        if rok is None or (jen_rok is not None and rok != jen_rok):
            continue
        with gzip.open(cesta, "rt", encoding="utf-8", newline="") as f:
            radky_csv = list(csv.DictReader(f, delimiter=";"))
        if not radky_csv:
            continue
        hotovo = db.scalar(
            select(func.count(SpotovaCena.id)).where(
                SpotovaCena.trh == TRH_DAM_CZ,
                SpotovaCena.cas_utc >= _hranice_roku(rok),
                SpotovaCena.cas_utc < _hranice_roku(rok + 1),
            )
        )
        if (hotovo or 0) >= len(radky_csv):
            continue
        radky = [
            {
                "trh": TRH_DAM_CZ,
                "cas_utc": datetime.datetime.fromtimestamp(
                    int(r["unix_s"]), datetime.timezone.utc
                ),
                "interval_min": int(r["interval_min"]),
                "cena_eur_mwh": float(r["eur_mwh"]),
                "cena_kc_mwh": float(r["kc_mwh"]),
                "zdroj": f"energy-charts+ČNB ({cesta.name})",
            }
            for r in radky_csv
        ]
        vlozeno += _vloz_radky(db, radky)
    return vlozeno


# ------------------------------------------------------------------- čtení
def _hranice_roku(rok: int) -> datetime.datetime:
    """Začátek roku v lokálním čase, převedený do UTC (pro filtr v DB)."""
    return datetime.datetime(rok, 1, 1, tzinfo=ZONA).astimezone(datetime.timezone.utc)


# Kolik intervalů musí rok mít, aby se považoval za použitelný. Rok cen má
# 8 760 hodinových / 35 040 čtvrthodinových obchodních intervalů; 5 000 je
# hranice „je toho dost na roční simulaci", ne exaktní kontrola pokrytí.
MIN_INTERVALU_ROKU = 5000


def dostupne_roky(db: Session, trh: str = TRH_DAM_CZ) -> list[int]:
    """Roky, pro které jsou v DB použitelné ceny (dle lokálního času).

    Záměrně bez databázových funkcí na časové zóny – rozsah se zjistí z min/max
    a počty se dopočítají obyčejnými filtry, takže na dialektu nezáleží.
    """
    hranice = db.execute(
        select(func.min(SpotovaCena.cas_utc), func.max(SpotovaCena.cas_utc)).where(
            SpotovaCena.trh == trh
        )
    ).one()
    od, do = hranice
    if od is None or do is None:
        return []
    roky: list[int] = []
    for rok in range(od.astimezone(ZONA).year, do.astimezone(ZONA).year + 1):
        pocet = db.scalar(
            select(func.count(SpotovaCena.id)).where(
                SpotovaCena.trh == trh,
                SpotovaCena.cena_kc_mwh.isnot(None),
                SpotovaCena.cas_utc >= _hranice_roku(rok),
                SpotovaCena.cas_utc < _hranice_roku(rok + 1),
            )
        )
        if (pocet or 0) >= MIN_INTERVALU_ROKU:
            roky.append(rok)
    return roky


def nacti_rok(db: Session, rok: int, trh: str = TRH_DAM_CZ) -> RadaCen:
    """Načte ceny roku a rozpadne je na čtvrthodiny v lokálním čase.

    Hodinová cena (data do 30. 9. 2025) se replikuje na 4 čtvrthodiny – v rámci
    obchodního intervalu je cena konstantní, takže tím nevzniká žádná nová
    informace, jen společná granularita s profilem odběru.
    """
    radky = db.execute(
        select(SpotovaCena.cas_utc, SpotovaCena.interval_min, SpotovaCena.cena_kc_mwh)
        .where(
            SpotovaCena.trh == trh,
            SpotovaCena.cena_kc_mwh.isnot(None),
            SpotovaCena.cas_utc >= _hranice_roku(rok),
            SpotovaCena.cas_utc < _hranice_roku(rok + 1),
        )
        .order_by(SpotovaCena.cas_utc)
    ).all()
    return _rada_z_radku(
        [(r.cas_utc, int(r.interval_min), float(r.cena_kc_mwh)) for r in radky], rok, trh
    )


def _rada_z_radku(
    radky: list[tuple[datetime.datetime, int, float]], rok: int, trh: str
) -> RadaCen:
    """Rozpadne obchodní intervaly na čtvrthodiny lokálního času.

    Klíčem v rámci dne je `(hodina, minuta)`. Při podzimním přechodu času se
    hodina 2:00–3:00 odehraje dvakrát, takže druhý výskyt ten první přepíše –
    z roku se tím ztratí jedna hodina (4 z 35 040 intervalů, 0,01 %). Je to
    záměr: profily odběru mají stejnou nejednoznačnost a appka je slučuje
    obdobně (viz `_lehka_migrace` k `spotreba_profil`), a párování podle času
    dne je proti tomu jednodušší i čitelnější než rozlišovat opakování.
    """
    podle_dne: dict[datetime.date, dict[tuple[int, int], float]] = {}
    for cas_utc, interval_min, kc in radky:
        if cas_utc.tzinfo is None:
            cas_utc = cas_utc.replace(tzinfo=datetime.timezone.utc)
        pocet = max(1, interval_min // INTERVAL_MIN)
        for k in range(pocet):
            lokalni = (cas_utc + datetime.timedelta(minutes=k * INTERVAL_MIN)).astimezone(ZONA)
            if lokalni.year != rok:
                continue
            podle_dne.setdefault(lokalni.date(), {})[(lokalni.hour, lokalni.minute)] = kc
    dny_dle_typu: dict[tuple[int, int], list[datetime.date]] = {}
    for den in sorted(podle_dne):
        dny_dle_typu.setdefault((den.month, den.weekday()), []).append(den)
    return RadaCen(rok=rok, trh=trh, podle_dne=podle_dne, dny_dle_typu=dny_dle_typu)


# ------------------------------------------------------- párování na profil
def _odpovidajici_den(den: datetime.date, rada: RadaCen) -> datetime.date | None:
    """Den v roce cen, který nejlépe odpovídá dni profilu.

    Kritérium: **stejný měsíc a stejný den v týdnu** (aby pracovní den dostal
    ceny pracovního dne a víkend víkendové – rozdíl je průměrně 240 Kč/MWh
    a hlavně jiný tvar dne), a z těch nejblíž stejnému dni v měsíci. Když by
    kombinace chyběla (děravá data), spadne se na nejbližší den v měsíci.
    """
    kandidati = rada.dny_dle_typu.get((den.month, den.weekday()))
    if not kandidati:
        kandidati = [d for d in rada.podle_dne if d.month == den.month]
    if not kandidati:
        kandidati = sorted(rada.podle_dne)
    if not kandidati:
        return None
    return min(kandidati, key=lambda d: abs(d.day - den.day))


def ceny_pro_casy(casy: list[datetime.datetime], rada: RadaCen) -> tuple[list[float], dict]:
    """Ke každému času profilu přiřadí cenu Kč/MWh; vrací (ceny, souhrn).

    Když je profil ze stejného roku jako ceny, sedne mapování 1:1. Jinak se
    každý den profilu spáruje s odpovídajícím dnem roku cen (viz
    `_odpovidajici_den`) a v rámci dne se bere stejná čtvrthodina; u chybějící
    (přechod letního času) nejbližší dostupná.

    Souhrn nese, co se dělo, ať to jde napsat do upozornění výpočtu:
    `rok_cen`, `stejny_rok`, `chybejici_intervaly`, `parovano_dnu`.
    """
    ceny: list[float] = []
    cache_dne: dict[datetime.date, dict[tuple[int, int], float]] = {}
    chybejici = 0
    parovano_dnu: set[datetime.date] = set()
    stejny_rok = all(c.year == rada.rok for c in casy) if casy else False

    for cas in casy:
        den = cas.date()
        mapa = cache_dne.get(den)
        if mapa is None:
            if stejny_rok and den in rada.podle_dne:
                mapa = rada.podle_dne[den]
            else:
                zdroj = _odpovidajici_den(den, rada)
                mapa = rada.podle_dne.get(zdroj, {}) if zdroj is not None else {}
                if zdroj is not None:
                    parovano_dnu.add(den)
            cache_dne[den] = mapa
        klic = (cas.hour, cas.minute - cas.minute % INTERVAL_MIN)
        cena = mapa.get(klic)
        if cena is None:
            cena = _nejblizsi_v_dni(mapa, klic)
            if cena is None:
                chybejici += 1
                cena = 0.0
        ceny.append(cena)

    return ceny, {
        "rok_cen": rada.rok,
        "trh": rada.trh,
        "stejny_rok": stejny_rok,
        "chybejici_intervaly": chybejici,
        "parovano_dnu": len(parovano_dnu),
        "intervalu_v_cenach": rada.pocet_intervalu,
    }


def _nejblizsi_v_dni(
    mapa: dict[tuple[int, int], float], klic: tuple[int, int]
) -> float | None:
    """Nejbližší dostupná čtvrthodina v rámci dne (díry, přechod času)."""
    if not mapa:
        return None
    cil = klic[0] * 60 + klic[1]
    nejlepsi = min(mapa, key=lambda k: abs(k[0] * 60 + k[1] - cil))
    return mapa[nejlepsi]
