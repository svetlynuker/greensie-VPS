# Syntetické testy výpočetních jader (T1–T8)

> Audit 16. 7. 2026. Testy běží přímo nad `ppa_fve.py` a `peak_shaving.py` (moduly jsou
> bez závislostí na DB/FastAPI) na uměle vytvořených profilech — kvantifikují dopady
> nálezů z [peak-shaving.md](peak-shaving.md), [ppa-fve.md](ppa-fve.md) a
> [spolecne-profil-a-data.md](spolecne-profil-a-data.md). Kompletní skript je na konci
> souboru (reprodukovatelné).

**Pozn.:** testy T5–T7 běžely ještě se **starými seed hodnotami** (RK 2 847,72 Kč/kW/rok,
pokuta 1 108 Kč/kW/měs), protože měří chování kódu, ne správnost sazeb. Se správnými
sazbami 2026 (RK 3 030,78 Kč/kW/rok, pokuta 422,73 Kč/kW/měs — viz PS-1/PS-2) vychází
efekt optimalizace RK bez baterie ještě výrazněji (break-even ≈ 7 měsíců s překročením
místo ~2,6).

## Výsledky

### T1 — `kandidatni_velikosti` ignoruje `max_kwp` < 5 (PPA-1)
```
max_kwp=3.0  ->  kandidáti: [1, 2, 3, 4, 5]
Kandidáti nad limit střechy: [4, 5]
```

### T2 — profil kratší než rok (leden–červen) projde tiše (SP-1)
```
Simulovaná výroba 1 kWp za 6 měsíců: 538 kWh (poměrná část led–čvn = 538 z 1000)
'rocni_spotreba_kwh' ve výstupu: 174 810   (reálně jen půlrok – žádné upozornění)
'vyroba_rok1_kwh': 53 800                  → ekonomika z půlročních čísel jako by byla roční
```
(úspory/výnosy ~poloviční, CAPEX plný → payback/NPV/IRR zásadně zkreslené)

### T3 — profil delší než rok (leden 2025 – leden 2026) (SP-1)
```
Výroba 1 kWp za 13 měsíců: 1000 kWh (mělo by být ~1026 = rok + druhý leden)
Lednová výroba (2025): 13,0 kWh — správně 26; lednová energie rozpuštěná do 62 dnů dvou lednů
```

### T4 — letní čas: výroba centrovaná na 12:00 vs. realita ~13:00 SELČ (PPA-3)
```
Roční výroba: model 150 000 kWh vs. posunutá 150 000 kWh (sedí – mění se jen tvar dne)
Samospotřeba, ranní provoz 7–17 h:   model 120 973 vs. 'realita' 119 097 kWh → chyba +1,6 %
Samospotřeba, odpolední provoz 12–22 h: model 92 515 vs. 'realita' 99 492 kWh → chyba −7,0 %
```

### T5 — 2026: optimalizace RK bez baterie = fair baseline (PS-7)
Profil: základ 200 kW, špičky 300 kW (pracovní dny 10–12 h), leden 3 dny 400 kW,
únor 2 dny 380 kW. Současná RK 400 kW. Baterie 100 kW / 220 kWh za 2,0 mil. Kč.
```
Současný stav (RK=400):               1 139 088 Kč/rok (rezervace, pokuty 0)
Optimální RK bez baterie: 300 kW  →   1 053 756 Kč/rok → úspora 85 332 Kč/rok BEZ INVESTICE
Baterie: roční strop T = 300 kW
Úspora dle nástroje (vs. RK=400):       284 772 Kč/rok → návratnost 7,0 let
Úspora vs. OPTIMALIZOVANÉ RK:           199 440 Kč/rok → návratnost 10,0 let
S baterií: optimální RK = 300 = T (u tohoto profilu pod T nemá smysl)
```
→ ~30 % úspory připsané baterii jde získat administrativně zdarma.

### T6 — 2027: RP fixně = roční strop vs. optimalizovaný RP (PS-4/PS-7; seed ČEZ VN, bez AKU)
```
Měsíční maxima po baterii: leden 300, únor 280, ostatní 208 kW
RP dle nástroje = 300 kW → roční náklad 666 302 Kč
Optimální RP    = 208 kW → roční náklad 649 945 Kč → rozdíl 16 358 Kč/rok
```
(Pozn.: po zjištění, že RP je ze smlouvy o připojení — PS-4 — je „optimalizace RP“
jednosměrné rozhodnutí; test ukazuje citlivost, ne doporučení.)

### T7 — vliv účinnosti baterie (PS-5)
Profil se špičkami 2× denně (9–11 a 13–15 h, 350 kW nad základem 200 kW), baterie 80 kW/160 kWh:
```
Min. strop bez ztrát: 273,3 kW | s round-trip 88 %: 276,4 kW (Δ +3,1 kW)
Δ nákladu rezervace: ~8 700 Kč/rok (malé)
Procyklovaná energie: 80 037 kWh/rok nabito
Ztráty při 88 % RT: ~10 914 kWh/rok → při 3 000 Kč/MWh ≈ 32 742 Kč/rok  ← chybí v ekonomice
```

### T8 — sanity kontroly interních tabulek (informativní)
```
Součet měsíční tabulky výnosu: 1000 ✓
k_orient(0°, 35°) = 1,000 ✓ | k_orient(90°, 35°) = 0,840 | k_orient(180°, 35°) = 0,660
k_orient(0°, 0°) = 0,880 | k_orient(−45°, 25°) = 0,950   (bilineární interpolace funguje;
hodnoty samotné viz kalibrace PVGIS — PPA-2)
```

## Jak spustit

```bash
# Windows, bez venv (moduly nemají závislosti); UTF-8 kvůli české konzoli
PYTHONIOENCODING=utf-8 python synteticke_testy.py
```

## Skript

```python
# -*- coding: utf-8 -*-
"""Syntetické testy výpočetních jader ppa_fve.py a peak_shaving.py.

Moduly se načítají přímo ze souborů (jsou bez závislostí na DB/FastAPI),
takže není potřeba venv ani instalace balíčků.
"""
import importlib.util
import sys
from datetime import datetime, timedelta

BACKEND = r"backend\app\nabidkovac"  # cesta od kořene repa


def load(name):
    spec = importlib.util.spec_from_file_location(name, rf"{BACKEND}\{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses (py3.12+) vyžadují modul v sys.modules
    spec.loader.exec_module(mod)
    return mod


ppa = load("ppa_fve")
ps = load("peak_shaving")

INTERVAL = 0.25


def rok_casy(rok=2025, mesice=None):
    """15min časové značky pro daný rok (volitelně jen vybrané měsíce)."""
    out = []
    t = datetime(rok, 1, 1)
    konec = datetime(rok + 1, 1, 1)
    while t < konec:
        if mesice is None or t.month in mesice:
            out.append(t)
        t += timedelta(minutes=15)
    return out


def kancelarsky_profil(casy, den_kw=100.0, noc_kw=15.0):
    """Pracovní dny 7–17 h vysoký odběr, jinak nízký (kW)."""
    prof = []
    for c in casy:
        pracovni = c.weekday() < 5
        spicka = 7 <= c.hour < 17
        prof.append(den_kw if (pracovni and spicka) else noc_kw)
    return prof


def dst_je(c):
    """Přibližné okno letního času 2025: 30.3. 02:00 – 26.10. 03:00."""
    return datetime(2025, 3, 30, 2) <= c < datetime(2025, 10, 26, 3)


print("=" * 78)
print("T1: kandidatni_velikosti ignoruje max_kwp < 5 (cap = max(cap, 5.0))")
print("=" * 78)
casy = rok_casy()
spotreba_kwh = [k * INTERVAL for k in kancelarsky_profil(casy, den_kw=3.0, noc_kw=1.0)]
base1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
kand = ppa.kandidatni_velikosti(casy, spotreba_kwh, base1, max_kwp=3.0, pocet=30)
print(f"  max_kwp=3.0  ->  kandidáti: {kand}")
print(f"  Kandidáti nad limit střechy: {[k for k in kand if k > 3.0]}")

print()
print("=" * 78)
print("T2: profil kratší než rok (jen leden–červen) – čísla označená jako 'roční'")
print("=" * 78)
casy6 = rok_casy(mesice={1, 2, 3, 4, 5, 6})
prof6 = kancelarsky_profil(casy6)
spotreba6 = [k * INTERVAL for k in prof6]
base1_6 = ppa.simuluj_vyrobu(casy6, 1.0, 49.8, 35, 0)
vyroba_1kwp_6m = sum(base1_6)
print(f"  Simulovaná výroba 1 kWp za 6 měsíců: {vyroba_1kwp_6m:.0f} kWh "
      f"(model by měl mít roční ~1000, poměrná část led–čvn = {sum([26,42,83,120,135,132]):.0f})")
vstup = ppa.VstupPPA(
    kwp=100.0, lat=49.8, sklon_st=35, azimut_st=0,
    cena_ppa_kc_mwh=2500, index_ppa_rocni=0.03,
    cena_dodavatel_kc_mwh=3500, index_dodavatel_rocni=0.03,
    delka_kontraktu_roky=15, degradace_rocni=0.005,
    capex_kc=100 * 25000, prebytek_uctovat=False, prebytek_cena_kc_mwh=0,
    index_prebytek_rocni=0, rezervovany_vykon_dodavky_kw=None,
    oam_kc_kwp_rok=0, diskontni_sazba=0.05,
)
r6 = ppa.spocti_ppa(vstup, casy6, spotreba6, [x * 100 for x in base1_6])
print(f"  'rocni_spotreba_kwh' ve výstupu: {r6['rocni_spotreba_kwh']:.0f} "
      f"(reálně jen půlrok – nikde žádné upozornění)")
print(f"  'vyroba_rok1_kwh': {r6['vyroba_rok1_kwh']:.0f}  → ekonomika je počítaná "
      f"z půlročních čísel jako by byla roční")

print()
print("=" * 78)
print("T3: profil delší než rok (leden 2025 – leden 2026, 13 měsíců)")
print("=" * 78)
casy13 = rok_casy(2025) + rok_casy(2026, mesice={1})
base1_13 = ppa.simuluj_vyrobu(casy13, 1.0, 49.8, 35, 0)
print(f"  Výroba 1 kWp za 13 měsíců: {sum(base1_13):.0f} kWh (mělo by být ~1026 = rok + druhý leden)")
led25 = sum(v for v, c in zip(base1_13, casy13) if c.year == 2025 and c.month == 1)
print(f"  Lednová výroba (2025) v 13měsíčním profilu: {led25:.1f} kWh — správně 26 kWh; "
      f"lednová energie se rozpustila do 62 dnů dvou lednů")

print()
print("=" * 78)
print("T4: letní čas – výroba centrovaná na 12:00 místního času vs. realita (~13:00)")
print("=" * 78)
prof_kw = kancelarsky_profil(casy)  # 100 kW 7–17 h
spotreba_kwh4 = [k * INTERVAL for k in prof_kw]
kwp = 150.0
vyroba_model = [x * kwp for x in ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)]
# „Realita“: v letním čase je solární poledne ~13:00 místního času → tvar
# vyhodnotit v (t − 1 h).
casy_shift = [c - timedelta(hours=1) if dst_je(c) else c for c in casy]
vyroba_real = [x * kwp for x in ppa.simuluj_vyrobu(casy_shift, 1.0, 49.8, 35, 0)]
b_model = ppa.sparuj(vyroba_model, spotreba_kwh4, None, INTERVAL)
b_real = ppa.sparuj(vyroba_real, spotreba_kwh4, None, INTERVAL)
print(f"  Roční výroba: model {b_model.vyroba_kwh:.0f} kWh vs. posunutá {b_real.vyroba_kwh:.0f} kWh (musí sedět)")
print(f"  Samospotřeba: model {b_model.samospotreba_kwh:.0f} kWh vs. 'realita' {b_real.samospotreba_kwh:.0f} kWh"
      f"  → chyba {100 * (b_model.samospotreba_kwh / b_real.samospotreba_kwh - 1):+.1f} %")
prof_odp = [100.0 if (c.weekday() < 5 and 12 <= c.hour < 22) else 15.0 for c in casy]
sp_odp = [k * INTERVAL for k in prof_odp]
bm = ppa.sparuj(vyroba_model, sp_odp, None, INTERVAL)
br = ppa.sparuj(vyroba_real, sp_odp, None, INTERVAL)
print(f"  Odpolední zátěž (12–22 h): model {bm.samospotreba_kwh:.0f} vs. 'realita' {br.samospotreba_kwh:.0f} kWh"
      f"  → chyba {100 * (bm.samospotreba_kwh / br.samospotreba_kwh - 1):+.1f} %")

print()
print("=" * 78)
print("T5: 2026 – optimalizace rezervované kapacity BEZ baterie (poctivá atribuce)")
print("=" * 78)
CENA_REZ = 2847.72   # Kč/kW/rok (PŮVODNÍ seed ČEZ VN; správně 2026 = 3030,78 – viz PS-1)
CENA_PREKR = 1108.0  # Kč/kW/měs (PŮVODNÍ seed; správně překročení RK = 422,73 – viz PS-2)
profil5, mesice5 = [], []
for c in casy:
    kw = 200.0
    if c.weekday() < 5 and 10 <= c.hour < 12:
        kw = 300.0
        if c.month == 1 and c.day in (7, 8, 9):
            kw = 400.0
        if c.month == 2 and c.day in (11, 12):
            kw = 380.0
    profil5.append(kw)
    mesice5.append(c.month)

RC_SOUC = 400.0
rez, pokuty = ps.vychozi_rocni_naklad_2026(profil5, mesice5, RC_SOUC, CENA_REZ, CENA_PREKR)
print(f"  Současný stav (RC=400): rezervace {rez:,.0f} + pokuty {pokuty:,.0f} = {rez + pokuty:,.0f} Kč/rok")

nejlepsi = None
for rc in range(150, 401):
    r_, p_ = ps.vychozi_rocni_naklad_2026(profil5, mesice5, float(rc), CENA_REZ, CENA_PREKR)
    if nejlepsi is None or r_ + p_ < nejlepsi[1]:
        nejlepsi = (rc, r_ + p_)
rc_opt, naklad_opt = nejlepsi
print(f"  Optimální RC bez baterie: {rc_opt} kW → náklad {naklad_opt:,.0f} Kč/rok "
      f"→ úspora {rez + pokuty - naklad_opt:,.0f} Kč/rok BEZ JAKÉKOLI INVESTICE")

VYK, KAP, CENA_BAT = 100.0, 220.0, 2_000_000.0
T = ps.min_udrzitelny_strop(profil5, VYK, KAP)
ek = ps.ekonomika_2026(profil5, mesice5, RC_SOUC, CENA_REZ, CENA_PREKR, T)
print(f"  Baterie {VYK:.0f} kW/{KAP:.0f} kWh: roční strop T = {T:.1f} kW")
print(f"  Úspora dle nástroje (vs. RC=400):    {ek.rocni_uspora:,.0f} Kč/rok → návratnost {CENA_BAT / ek.rocni_uspora:.1f} let")
uspora_fer = naklad_opt - T * CENA_REZ
print(f"  Úspora baterie vs. OPTIMALIZOVANÉ RC: {uspora_fer:,.0f} Kč/rok → návratnost {CENA_BAT / uspora_fer:.1f} let")

nej_bat = None
profil_po = [min(p, T) for p in profil5]
for rc in range(150, int(T) + 2):
    r_, p_ = ps.vychozi_rocni_naklad_2026(profil_po, mesice5, float(rc), CENA_REZ, CENA_PREKR)
    if nej_bat is None or r_ + p_ < nej_bat[1]:
        nej_bat = (rc, r_ + p_)
print(f"  S baterií: optimální RC = {nej_bat[0]} kW (vs. T={T:.0f}) → náklad {nej_bat[1]:,.0f} "
      f"vs. {T * CENA_REZ:,.0f} Kč/rok dle nástroje")

print()
print("=" * 78)
print("T6: 2027 – RP fixně = roční strop vs. optimalizovaný RP (seed ČEZ VN)")
print("=" * 78)
P2027 = {
    "t1_kapacita_kc_kw_mesic": 190.133,
    "t1_spicka_kc_kw_mesic": 19.013,
    "t2_kapacita_kc_kw_mesic": 22.743,
    "t2_spicka_kc_kw_mesic": 227.429,
    "sazba_prekroceni_kc_kw_mesic": 761.0,
    "u1_ucinnost": 0.60,
    "u2_ucinnost": 0.75,
}
po_mes = ps.mesicni_maxima_po_baterii(profil5, mesice5, VYK, KAP)
print("  Měsíční maxima po baterii:", {m: round(v) for m, v in sorted(po_mes.items())})
naklad_nastroj, *_ = ps._rocni_naklad_2027(T, po_mes, P2027)
nej27 = None
for rp in range(100, int(max(po_mes.values())) + 5):
    c, *_ = ps._rocni_naklad_2027(float(rp), po_mes, P2027)
    if nej27 is None or c < nej27[1]:
        nej27 = (rp, c)
print(f"  RP dle nástroje = {T:.0f} kW → roční náklad (bez AKU) {naklad_nastroj:,.0f} Kč")
print(f"  Optimální RP    = {nej27[0]} kW → roční náklad (bez AKU) {nej27[1]:,.0f} Kč "
      f"→ rozdíl {naklad_nastroj - nej27[1]:,.0f} Kč/rok")

print()
print("=" * 78)
print("T7: vliv účinnosti baterie na udržitelný strop + cena ztrát")
print("=" * 78)


def min_strop_se_ztratami(profil_kw, vykon_kw, kapacita_kwh, eta_rt=0.88, interval_h=0.25):
    """Kopie simulace se ztrátami: nabíjení ukládá jen eta_rt podílu energie."""
    def udrzitelny(strop):
        soc = kapacita_kwh
        for odber in profil_kw:
            if odber > strop:
                potreba = odber - strop
                dod = min(potreba, vykon_kw, soc / interval_h if interval_h > 0 else 0.0)
                if dod + 1e-9 < potreba:
                    return False
                soc -= dod * interval_h
            else:
                rezerva = min(strop - odber, vykon_kw)
                soc = min(kapacita_kwh, soc + rezerva * interval_h * eta_rt)
        return True

    lo, hi = 0.0, max(profil_kw)
    if not udrzitelny(hi):
        return hi
    while hi - lo > 0.01:
        mid = (lo + hi) / 2
        if udrzitelny(mid):
            hi = mid
        else:
            lo = mid
    return hi


profil7 = []
for c in casy:
    kw = 200.0
    if c.weekday() < 5 and (9 <= c.hour < 11 or 13 <= c.hour < 15):
        kw = 350.0
    profil7.append(kw)
T_bez = ps.min_udrzitelny_strop(profil7, 80.0, 160.0)
T_se = min_strop_se_ztratami(profil7, 80.0, 160.0, eta_rt=0.88)
nab, vyb = ps.energie_pri_stropu(profil7, T_bez, 80.0, 160.0)
print(f"  Min. strop bez ztrát: {T_bez:.1f} kW | s round-trip 88 %: {T_se:.1f} kW (Δ {T_se - T_bez:+.1f} kW)")
print(f"  Δ nákladu rezervace při Δ stropu: {(T_se - T_bez) * CENA_REZ:,.0f} Kč/rok")
print(f"  Procyklovaná energie (bez ztrát): nabito {nab:,.0f} kWh/rok")
ztraty_kwh = nab * (1 / 0.88 - 1)
print(f"  Ztráty při 88 % RT: ~{ztraty_kwh:,.0f} kWh/rok → při 3 000 Kč/MWh ≈ {ztraty_kwh * 3:,.0f} Kč/rok")

print()
print("=" * 78)
print("T8: kontrola měsíční tabulky výnosu a korekce orientace")
print("=" * 78)
print(f"  Součet měsíční tabulky: {sum(ppa._MESICNI_VYNOS.values()):.0f} (má být 1000)")
for az, sk in [(0, 35), (90, 35), (0, 0), (180, 35), (-45, 25)]:
    print(f"  k_orient(azimut={az:>4}, sklon={sk:>2}) = {ppa.korekce_orientace(az, sk):.3f}")
```
