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

Přepínač `pro_peak_shaving`
--------------------------
Peak shaving pracuje s měsíčními MAXIMY sdruženými podle ČÍSLA měsíce (1–12),
ne podle roku – překryv okrajových měsíců (dva neúplné stejné měsíce z dvou let)
mu proto nevadí, obě části se sešijí do jednoho měsíce. S `pro_peak_shaving=True`
proto ořezání i kontrola tolerují „rok a kousek“ (export od půlky měsíce do
půlky téhož měsíce o rok později): ořízne se na klouzavé okno posledního roku
a kontroluje se pokrytí každého čísla měsíce zvlášť. PPA (které energii SČÍTÁ,
takže překryv = dvojí započtení) zůstává na výchozím přísném režimu.
"""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import datetime, timedelta

# Tolerance délky ročního profilu ve dnech (rozsah min(cas)–max(cas)).
MIN_DNI_ROKU = 350.0
MAX_DNI_ROKU = 380.0

# Délka klouzavého okna (dny) pro peak-shaving fallback, když nejde sestavit
# 12 celých kalendářních měsíců (viz `orizni_na_posledni_rok`).
DNI_KLOUZAVE_OKNO = 366

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
    pro_peak_shaving: bool = False,
) -> tuple[list[datetime], list[float], bool]:
    """Profil delší než rok ořízne na posledních 12 celých kalendářních měsíců.

    Aktivuje se, když rozsah přesahuje `MAX_DNI_ROKU` nebo profil zasahuje do
    více než 12 kalendářních měsíců (rok+1 den = dva „ledny“ – bughunt T3).
    Za „celý“ se bere měsíc s ≥ 90 % očekávaných intervalů.

    Není-li celých měsíců aspoň 12 (typicky export „od půlky měsíce do půlky
    téhož měsíce o rok později“ – dva neúplné stejné měsíce), chování závisí na
    `pro_peak_shaving`: ve výchozím (PPA) režimu se vrací profil beze změny a
    chybu popíše `zkontroluj_pokryti`; s `pro_peak_shaving=True` se ořízne na
    klouzavé okno posledního roku (`DNI_KLOUZAVE_OKNO` dní od nejnovějšího
    záznamu) – překrývající se okrajové měsíce se pak sešijí přes číslo měsíce.
    Vrací (časy, hodnoty, ořezáno?).
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
    if len(cele_mesice) >= 12:
        vybrane = set(cele_mesice[-12:])
        dvojice = [(c, h) for c, h in zip(casy, hodnoty) if (c.year, c.month) in vybrane]
        return [c for c, _ in dvojice], [h for _, h in dvojice], True

    if not pro_peak_shaving:
        return casy, hodnoty, False

    # Peak-shaving fallback: klouzavé okno posledního roku od nejnovějšího
    # záznamu. Okrajové neúplné měsíce (stejné číslo z dvou let) se ve výpočtu
    # sešijí do jednoho měsíce, takže překryv nevadí a maximum zůstane platné.
    hranice = max(casy) - timedelta(days=DNI_KLOUZAVE_OKNO)
    dvojice = [(c, h) for c, h in zip(casy, hodnoty) if c >= hranice]
    orezano = len(dvojice) < len(casy)
    return [c for c, _ in dvojice], [h for _, h in dvojice], orezano


def zkontroluj_pokryti(
    casy: list[datetime],
    interval_h: float = VYCHOZI_INTERVAL_H,
    pro_peak_shaving: bool = False,
) -> tuple[bool, str | None]:
    """Ověří, že profil je použitelný jako roční. Vrací (ok, důvod chyby).

    Kontroluje rozsah 350–380 dní, přítomnost všech 12 kalendářních měsíců,
    max. 12 kombinací rok×měsíc (žádné dva ledny) a podíl děr < 2 %
    (očekávaný počet intervalů z rozsahu časů a granularity).

    S `pro_peak_shaving=True` se místo toho ověřuje pokrytí každého čísla měsíce
    zvlášť (`_zkontroluj_pokryti_peak_shaving`) – překryv okrajových měsíců je
    povolený, protože peak shaving bere měsíční maxima.
    """
    if not casy:
        return False, "Profil je prázdný."

    if pro_peak_shaving:
        return _zkontroluj_pokryti_peak_shaving(casy, interval_h)

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


def _zkontroluj_pokryti_peak_shaving(
    casy: list[datetime], interval_h: float
) -> tuple[bool, str | None]:
    """Kontrola pokrytí pro peak shaving: každé z 12 čísel měsíce má dost dat.

    Peak shaving počítá měsíční MAXIMA sdružená podle čísla měsíce (1–12), ne
    podle roku. Proto se místo striktního rozsahu 350–380 dní a zákazu dvou
    stejných měsíců ověřuje, že každé číslo měsíce je zastoupené a pokryté aspoň
    z 90 %. Pokrytí se počítá přes unikátní vnitroměsíční sloty (den, hodina,
    minuta) napříč roky, takže dva neúplné okrajové měsíce (např. dva půlené
    července z dvou let) se sešijí do jednoho plného měsíce.
    """
    sloty_mesice: dict[int, set[tuple[int, int, int]]] = {}
    roky_mesice: dict[int, set[int]] = {}
    for c in casy:
        sloty_mesice.setdefault(c.month, set()).add((c.day, c.hour, c.minute))
        roky_mesice.setdefault(c.month, set()).add(c.year)

    chybi = sorted(set(range(1, 13)) - set(sloty_mesice))
    if chybi:
        return False, (
            "V profilu chybí data za měsíce: "
            + ", ".join(str(m) for m in chybi)
            + ". Peak shaving potřebuje všech 12 kalendářních měsíců."
        )

    if interval_h <= 0:
        return True, None

    for m in range(1, 13):
        # Očekávané sloty podle nejdelší varianty měsíce v datech (únor 28/29).
        dny = max(calendar.monthrange(rok, m)[1] for rok in roky_mesice[m])
        ocekavane = dny * 24.0 / interval_h
        podil = len(sloty_mesice[m]) / ocekavane if ocekavane > 0 else 1.0
        if podil < _MIN_PODIL_CELEHO_MESICE:
            return False, (
                f"Měsíc {m} má jen ~{podil:.0%} dat (potřeba ≥ "
                f"{_MIN_PODIL_CELEHO_MESICE:.0%}). Peak shaving z něj nespočítá "
                "spolehlivé měsíční maximum – zkontroluj úplnost exportu."
            )

    return True, None
