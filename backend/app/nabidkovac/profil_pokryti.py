"""Kontrola pokrytí 15min profilu před ročním výpočtem (audit 16. 7. 2026, SP-1).

Oba kalkulátory (peak shaving i PPA) prohlašují součty/maxima z profilu za
ROČNÍ ekonomiku. Neúplný profil (půlrok) nebo profil delší než rok (13 měsíců
s dvěma ledny) proto tiše vyráběl nesmyslná čísla – viz bughunt SP-1, testy
T2/T3. Tenhle modul je čistá logika bez DB/FastAPI:

- `orizni_na_posledni_rok()` – profil delší než rok (nebo zasahující do více
  než 12 kalendářních měsíců) ořízne na posledních 12 CELÝCH měsíců,
- `zkontroluj_pokryti()` – ověří, že zbylý profil je použitelný jako roční
  (350–380 dní, všech 12 měsíců, díry < 2 %); vrací lidsky čitelný důvod.

Routes na neprošlou kontrolu odpovídají HTTP 422 (tvrdá chyba – radši žádné
číslo než sebejistě špatné).
"""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import datetime

# Tolerance délky ročního profilu ve dnech (rozsah min(cas)–max(cas)).
MIN_DNI_ROKU = 350.0
MAX_DNI_ROKU = 380.0

# Maximální tolerovaný podíl chybějících intervalů (děr) v profilu.
MAX_PODIL_DER = 0.02

# Měsíc se počítá jako „celý“, když má aspoň tento podíl očekávaných intervalů.
_MIN_PODIL_CELEHO_MESICE = 0.9

VYCHOZI_INTERVAL_H = 0.25


def _ocekavane_intervaly_mesice(rok: int, mesic: int, interval_h: float) -> float:
    dny = calendar.monthrange(rok, mesic)[1]
    return dny * 24.0 / interval_h if interval_h > 0 else 0.0


def _rozsah_dni(casy: list[datetime]) -> float:
    return (max(casy) - min(casy)).total_seconds() / 86400.0


def orizni_na_posledni_rok(
    casy: list[datetime],
    hodnoty: list[float],
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> tuple[list[datetime], list[float], bool]:
    """Profil delší než rok ořízne na posledních 12 celých kalendářních měsíců.

    Aktivuje se, když rozsah přesahuje `MAX_DNI_ROKU` nebo profil zasahuje do
    více než 12 kalendářních měsíců (rok+1 den = dva „ledny“ – bughunt T3).
    Za „celý“ se bere měsíc s ≥ 90 % očekávaných intervalů; není-li celých
    měsíců aspoň 12, vrací se profil beze změny (chybu popíše
    `zkontroluj_pokryti`). Vrací (časy, hodnoty, ořezáno?).
    """
    if not casy:
        return casy, hodnoty, False
    pocty = Counter((c.year, c.month) for c in casy)
    if _rozsah_dni(casy) <= MAX_DNI_ROKU and len(pocty) <= 12:
        return casy, hodnoty, False

    cele_mesice = [
        rm
        for rm in sorted(pocty)
        if pocty[rm] >= _MIN_PODIL_CELEHO_MESICE * _ocekavane_intervaly_mesice(*rm, interval_h)
    ]
    if len(cele_mesice) < 12:
        return casy, hodnoty, False

    vybrane = set(cele_mesice[-12:])
    dvojice = [(c, h) for c, h in zip(casy, hodnoty) if (c.year, c.month) in vybrane]
    return [c for c, _ in dvojice], [h for _, h in dvojice], True


def zkontroluj_pokryti(
    casy: list[datetime],
    interval_h: float = VYCHOZI_INTERVAL_H,
) -> tuple[bool, str | None]:
    """Ověří, že profil je použitelný jako roční. Vrací (ok, důvod chyby).

    Kontroluje rozsah 350–380 dní, přítomnost všech 12 kalendářních měsíců,
    max. 12 kombinací rok×měsíc (žádné dva ledny) a podíl děr < 2 %
    (očekávaný počet intervalů z rozsahu časů a granularity).
    """
    if not casy:
        return False, "Profil je prázdný."

    dni = _rozsah_dni(casy)
    priblizne_mesicu = dni / 30.4
    if dni < MIN_DNI_ROKU:
        return False, (
            f"Profil pokrývá jen {dni:.0f} dní (~{priblizne_mesicu:.0f} měsíců). "
            "Roční ekonomika potřebuje souvislých ~12 měsíců (350–380 dní) "
            "15min dat – nahraj roční export z portálu distributora."
        )
    if dni > MAX_DNI_ROKU:
        return False, (
            f"Profil pokrývá {dni:.0f} dní (přes rok) a nepodařilo se ho oříznout "
            "na posledních 12 celých měsíců – zkontroluj úplnost dat po měsících."
        )

    mesice_v_roce = {c.month for c in casy}
    if len(mesice_v_roce) < 12:
        chybi = sorted(set(range(1, 13)) - mesice_v_roce)
        return False, (
            "V profilu chybí data za měsíce: "
            + ", ".join(str(m) for m in chybi)
            + ". Roční ekonomika potřebuje všech 12 kalendářních měsíců."
        )

    kombinaci = len({(c.year, c.month) for c in casy})
    if kombinaci > 12:
        return False, (
            f"Profil zasahuje do {kombinaci} kalendářních měsíců (na okrajích se "
            "měsíce překrývají – např. dva neúplné července). Dodej souvislých "
            "12 celých měsíců."
        )

    if interval_h > 0:
        ocekavane = dni * 24.0 / interval_h + 1.0
        podil_der = max(0.0, 1.0 - len(casy) / ocekavane)
        if podil_der > MAX_PODIL_DER:
            return False, (
                f"V profilu chybí ~{podil_der:.1%} intervalů (tolerance "
                f"{MAX_PODIL_DER:.0%}). Zkontroluj export – díry v datech "
                "zkreslují roční součty i měsíční maxima."
            )

    return True, None
