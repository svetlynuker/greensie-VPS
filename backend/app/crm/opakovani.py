"""Opakované aktivity: generování termínů a hromadné změny nad sérií.

Zadání Dana (30. 7. 2026): denně, v pracovní dny, týdně, měsíčně a vlastní
(číslem počet dní mezi opakováními, např. 14). Opakování má povinný konec —
datum, nebo počet — a úprava jedné události ze série se ptá, jestli platí pro
tuhle, pro tuhle a další, nebo pro celou sérii.

---- Kde jsou v opakování pasti -------------------------------------------

1. **Měsíční opakování 31. dne.** Únor 31. nemá. Termín se proto v takovém
   měsíci posune na jeho POSLEDNÍ den, ne na 1. března — „poslední den měsíce"
   je to, co člověk od „31." čeká, a hlavně se tím nerozsype pořadí (jinak by
   březnová instance vyšla dřív než únorová).
2. **Pracovní dny.** Krok není „+1 den", ale „další pracovní den", jinak by
   série se startem v pátek vygenerovala sobotu a nedělí a ty by se musely
   filtrovat až potom (a chybělo by jich N na konci).
3. **Konec série.** Bez povinného konce by šlo vyrobit nekonečnou sérii; strop
   `MAX_INSTANCI` je druhá pojistka, aby jedno kliknutí neudělalo tisíce řádků.
"""

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.crm.models import (
    FREKVENCE_OPAKOVANI,
    CrmAktivita,
    CrmSerieAktivit,
)

# Strop na jednu sérii. Dva roky týdenní porady = 104 instancí, dva roky
# pracovních dnů = ~520. Pět set je hranice, za kterou už jde spíš o omyl.
MAX_INSTANCI = 520
# Jak daleko dopředu smí série sahat, když je zadaný jen počet.
MAX_ROKU = 2


def _dalsi_pracovni(d: date) -> date:
    """Posune datum na nejbližší pracovní den (víkend přeskočí)."""
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _o_mesic(zaklad: date, kolik: int, den_v_mesici: int) -> date:
    """Datum o `kolik` měsíců dál, se zachovaným dnem v měsíci.

    Když cílový měsíc takový den nemá (31. 2.), použije se jeho poslední den.
    """
    mesic_celkem = zaklad.month - 1 + kolik
    rok = zaklad.year + mesic_celkem // 12
    mesic = mesic_celkem % 12 + 1
    posledni = monthrange(rok, mesic)[1]
    return date(rok, mesic, min(den_v_mesici, posledni))


def over_pravidlo(frekvence: str, interval_dni: int | None, do_data, pocet) -> None:
    """Ověří pravidlo opakování. Vyhazuje ValueError s čitelnou zprávou."""
    if frekvence not in FREKVENCE_OPAKOVANI:
        raise ValueError(
            f"Neznámá frekvence opakování: {frekvence}. "
            f"Povolené: {', '.join(FREKVENCE_OPAKOVANI)}."
        )
    if frekvence == "vlastni" and (not interval_dni or interval_dni < 1):
        raise ValueError("U vlastního opakování zadej počet dní mezi opakováními (aspoň 1).")
    if not do_data and not pocet:
        raise ValueError(
            "Opakování musí mít konec — vyplň datum, do kdy se má opakovat, "
            "nebo počet opakování."
        )
    if pocet is not None and pocet < 1:
        raise ValueError("Počet opakování musí být aspoň 1.")


def termíny(
    start: date,
    frekvence: str,
    interval_dni: int | None = None,
    do_data: date | None = None,
    pocet: int | None = None,
) -> list[date]:
    """Seznam termínů série včetně prvního (= `start`).

    Vrací nejvýš `MAX_INSTANCI` termínů a nejdál `MAX_ROKU` dopředu — obojí je
    pojistka proti překlepu v počtu, ne funkční omezení.
    """
    over_pravidlo(frekvence, interval_dni, do_data, pocet)

    strop_datum = min(
        do_data or date(start.year + MAX_ROKU, start.month, start.day),
        date(start.year + MAX_ROKU, start.month, start.day),
    )
    strop_pocet = min(pocet or MAX_INSTANCI, MAX_INSTANCI)

    prvni = _dalsi_pracovni(start) if frekvence == "pracovni_dny" else start
    out: list[date] = []
    i = 0
    kurzor = prvni
    while len(out) < strop_pocet and kurzor <= strop_datum:
        out.append(kurzor)
        i += 1
        if frekvence == "denne":
            kurzor = prvni + timedelta(days=i)
        elif frekvence == "pracovni_dny":
            kurzor = _dalsi_pracovni(kurzor + timedelta(days=1))
        elif frekvence == "tydne":
            kurzor = prvni + timedelta(weeks=i)
        elif frekvence == "mesicne":
            kurzor = _o_mesic(prvni, i, prvni.day)
        else:  # vlastni
            kurzor = prvni + timedelta(days=(interval_dni or 1) * i)
    return out


def popis_pravidla(s: CrmSerieAktivit) -> str:
    """Lidský popis pravidla do detailu aktivity („každý týden do 31.12.2026")."""
    zaklad = {
        "denne": "každý den",
        "pracovni_dny": "každý pracovní den",
        "tydne": "každý týden",
        "mesicne": "každý měsíc",
        "vlastni": f"každých {s.interval_dni or '?'} dní",
    }.get(s.frekvence, s.frekvence)
    if s.do_data:
        return f"{zaklad} do {s.do_data.strftime('%-d.%-m.%Y')}"
    if s.pocet:
        return f"{zaklad}, {s.pocet}×"
    return zaklad


def instance_serie(
    db: Session, serie_id: int, od_data: date | None = None
) -> list[CrmAktivita]:
    """Aktivity série; `od_data` omezí na tu a další (rozsah „tuto a další").

    Řadí se podle termínu, aby „další" znamenalo skutečně další v čase, ne podle
    id — přesunutá instance by jinak vypadla z pořadí.
    """
    q = db.query(CrmAktivita).filter(CrmAktivita.serie_id == serie_id)
    if od_data is not None:
        q = q.filter(CrmAktivita.termin >= od_data)
    return q.order_by(CrmAktivita.termin, CrmAktivita.id).all()


def dotcene(db: Session, a: CrmAktivita, rozsah: str) -> list[CrmAktivita]:
    """Které aktivity zasáhne úprava/smazání podle zvoleného rozsahu.

    Aktivita bez série (nebo rozsah „jen tuhle") vrací jen sebe — díky tomu
    volající nemusí řešit, jestli jde o sérii.
    """
    if a.serie_id is None or rozsah == "jen_tuhle":
        return [a]
    if rozsah == "tuto_a_dalsi":
        return instance_serie(db, a.serie_id, od_data=a.termin)
    return instance_serie(db, a.serie_id)
