# Bughunt: Peak shaving (`backend/app/nabidkovac/peak_shaving.py` + `seed.py` + `routes.py`)

> Nálezy auditu 16. 7. 2026. Ověřená čísla: [../eru-sazby-2026-a-nts-2027.md](../eru-sazby-2026-a-nts-2027.md),
> metodická doporučení: [../peak-shaving-metodiky-dimenzovani.md](../peak-shaving-metodiky-dimenzovani.md),
> kvantifikace: [synteticke-testy.md](synteticke-testy.md). Priority viz [README](README.md).

---

## PS-1 ⛔ P0 — Sazby 2026 v seedu jsou hodnoty roku 2025 (a VVN chybí zbytečně)

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(peak-shaving): sazby RK 2026 dle CV 13/2025 + EG.D a PRE (PS-1)`
> na větvi `bughunt-opravy-p0`. Seed nese všech 6 kombinací DSO × hladina (roční
> i měsíční RK dle ERV 17/2025) + nova_2027 pro EG.D/PRE z informativního CV;
> `_BACKFILL_OPRAVY` cíleně přepíše 2 847,72 → 3 030,78 a doplní VVN 1 409,18
> (jen přesnou shodu s chybnou hodnotou, ruční úpravy admina nechává).
> Testy: `backend/tests/test_seed_sazby.py`. Mechanismus pokut řeší PS-2.

**Kde:** `seed.py` (`_REZERVACE_CEZ_VN_ROK = 237.31 × 12`, VVN `None`).

**Co je špatně:** 237,31 Kč/kW/měs je cena z cenového rozhodnutí ERÚ č. 11/2024 **pro rok
2025**. Pro rok 2026 platí finální cenový výměr č. 13/2025 (ERV 17/2025):

| Distributor | VN roční RK | VN měsíční RK | VVN roční RK | VVN měsíční RK |
|---|---|---|---|---|
| ČEZ | **252,565** | 281,823 | **117,432** | 131,036 |
| EG.D | 230,551 | 254,260 | 110,826 | 122,223 |
| PRE | 271,093 | 299,351 | 129,580 | 143,087 |

(Kč/kW/měsíc, bez DPH; roční ekvivalent ČEZ VN = 3 030,78 Kč/kW/rok, ne 2 847,72.)

**Dopad:** podhodnocení úspory z každého sraženého kW o ~6 % (VN) + úplně chybějící VVN
výpočty u ČEZ.

**Náprava:**
1. Opravit seed ČEZ (VN + VVN) na hodnoty 2026, poznámku se zdrojem (ERV 17/2025).
2. Doplnit řádky EG.D a PRE (hodnoty výše — všechny z téhož výměru).
3. Do `parametry` přidat klíč `cena_mesicni_rk_kc_kw_mesic` (potřeba pro PS-2 i PS-7).
4. Pozor na idempotenci seedu: existující řádky se nepřepisují → oprava vyžaduje buď
   migraci/ruční úpravu v adminu na produkci, nebo verzovaný seed (nový `platne_od`).

---

## PS-2 ⛔ P0 — Záměna mechanismu pokut: použité ceny platí pro překročení rezervovaného VÝKONU (směr do sítě), ne KAPACITY

**Kde:** `seed.py` (`_POKUTA_VN = 1108`, `_POKUTA_VVN = 521`), používá
`vychozi_rocni_naklad_2026()` v `peak_shaving.py`.

**Co je špatně:** 1 108/521 Kč/kW/měs jsou dle bodu 4.38 výměru ceny za překročení
**rezervovaného výkonu** = když výrobna dodá do sítě víc, než má sjednáno. Pro odběrovou
špičku (peak shaving) platí bod 4.24: **překročení rezervované kapacity = 1,5× měsíční
cena za měsíční RK za každý kW nejvyššího čtvrthodinového překročení v měsíci**:

- ČEZ 2026: **VN 422,73 Kč/kW/měs, VVN 196,55 Kč/kW/měs** (= 1,5 × 281,823 / 131,036).
- (Samostatná věc je překročení rezervovaného *příkonu* ze smlouvy o připojení = 4× MRK,
  ČEZ VN 1 127,29 / VVN 524,14 Kč/kW/měs.)

**Dopad:** pokuty v baseline scénáři nadhodnocené ~2,6× → nadhodnocená úspora u klientů,
kteří dnes RK překračují; a špatné trade-offy pro jakoukoli optimalizaci výše RK (PS-7).

**Náprava:** cenu pokuty nepřidávat jako samostatné číslo, ale **počítat z měsíční MRK**
(`1.5 × cena_mesicni_rk`), ať se při roční aktualizaci sazeb nemůže rozjet. Sazby za
překročení rezervovaného výkonu (1 108/521) se hodí jinam — viz PPA-9 (strop přetoku).

---

## PS-3 ⛔ P0 — Koeficient AKU: špatná definice „účinnosti“ (rozhodnuto: přepsat dle ERÚ)

**Kde:** `peak_shaving.py` — `_koeficient_aku()`, `energie_pri_stropu()`, použití v
`ekonomika_2027()`; seed klíče `u1_ucinnost`/`u2_ucinnost`.

**Co je špatně:** nástroj počítá účinnost = vybitá/nabitá energie **baterie** za měsíc
(v bezztrátovém modelu ≈ 1 → plná sleva). ERÚ (část 24 informativního výměru NTS) ale
definuje koeficient AKU z podílu **zpětně dodané elektřiny do soustavy / odebrané
elektřiny ze soustavy za celé předávací místo a zúčtovací období**:

- K = 0 pro podíl ≤ U1; K = 1 pro podíl ≥ U2; lineárně mezi (U1/U2 = 0,6/0,75 VN,
  0,6/0,7 VVN — tyto prahy v seedu sedí).
- Sleva násobí **celý čtvrthodinový diagram odebraného výkonu** faktorem (1−K) a snižuje
  jen platbu za **maximální odebraný výkon** (RP se platí vždy plně). Žádné omezení
  nabíjecím výkonem baterie v návrhu není.
- **Peak-shavingová baterie uvnitř odběru závodu nic zpětně nedodává → podíl ≈ 0 →
  K = 0 → žádná sleva.** Benefit cílí na samostatná úložiště a přečerpávací elektrárny.

**Dopad:** „2027 optimistický (se slevou AKU)“ scénář je pro tento use-case strukturálně
mylný (ne jen optimistický) — ukazuje slevu až 100 % na složce špičky, na kterou klient
nemá nárok.

**Náprava (rozhodnuto 16. 7. 2026):**
1. Odstranit optimistickou větev (dnešní „konzervativní bez AKU“ se stane jediným
   modelem 2027) — tj. `navratnost_2027_optim`, `prumerny_koeficient_aku`,
   `predpoklad_aku_neoverovany` a FE zobrazení slevy.
2. Volitelně (fáze 2): počítat K dle ERÚ z bilance předávacího místa — dává smysl jen
   u míst s velkým exportem (velká FVE: zpětně dodáno ≥ 60 % odebraného), typicky
   kombinace PPA + baterie. Vyhodnotit po veřejné konzultaci ERÚ (říjen 2026).
3. Prahy U1/U2 v datech ponechat (sedí), označit „předběžné do CV 2027“.

---

## PS-4 ⚠️ P1 — Model 2027: RP není rezervovaná kapacita (chybí vstup)

**Kde:** `routes.py` → `ekonomika_2027()` — jako RP se dosazuje `vstup.rezervovana_kapacita_kw`;
scénář „s PS“ používá RP = nový roční strop.

**Co je špatně:** rezervovaný příkon je hodnota **ze smlouvy o připojení** (dlouhodobá,
typicky ≥ RK; v lednu 2027 se převezme ze smlouvy). Není to roční produkt jako RK:
snížení = změna smlouvy o připojení, zpětné navýšení je zpoplatněno (příloha 2 vyhlášky
č. 16/2016 Sb.). Baseline 2027 s RP = současná RK podhodnocuje platbu za RP; scénář
„s PS“ s RP = strop mlčky předpokládá, že klient smlouvu o připojení sníží.

**Náprava:**
1. Nový vstup `rezervovany_prikon_kw` (ze smlouvy o připojení) — použít v obou scénářích 2027.
2. Přepínač „uvažovat snížení RP na X kW“ (default vypnuto) + upozornění na jednosměrnost.
3. Bez snížení RP je přínos baterie v 2027 jen na složce „maximální odebraný výkon“
   (srážení M) — to je poctivý default.
4. Doplňkově: kontrola výhodnosti volitelné jednosložkové ceny (Kč/MWh) při využití
   RP < 600 h/rok.

---

## PS-5 ⚠️ P1 — Ztráty, SOC okno a degradace baterie nejsou v simulaci ani ekonomice

**Kde:** `strop_je_udrzitelny()`, `energie_pri_stropu()` (kapacita 1:1, bez ztrát, bez
DoD, počáteční SOC = plná), `_navratnost()`.

**Dopad (kvantifikováno, viz testy T7):** na udržitelný strop mají ztráty malý vliv
(+3 kW při RT 88 % na testovacím profilu), ale **cena ztracené energie chybí v cash flow**
(~12 % procyklované energie; na testu ~33 tis. Kč/rok při denním cyklování). Bez EOL
deratingu (×0,8) navíc baterie v druhé polovině životnosti nalezený strop neudrží.

**Náprava:**
1. Simulace: nabíjení `soc += (T − odběr) × η_ch × dt`, vybíjení `soc −= dodávka/η_dis × dt`;
   η z katalogu — **sloupec `technologie.ucinnost` už existuje a peak shaving ho ignoruje**
   (default AC-AC 0,88 → η_ch = η_dis = √0,88).
2. SOC okno 10–95 % (využitelná kapacita = 0,85×jmenovitá), volitelně EOL derating ×0,8
   pro dimenzování.
3. Ekonomika: náklad ztrát = nabito × (1/RT − 1) × cena energie (silová + variabilní
   distribuce) + volitelně vlastní spotřeba systému (~1 % výkonu PCS trvale).

---

## PS-6 ⚠️ P1 — Nová RK = přesně nalezené minimum, bez rezervy

**Kde:** `min_udrzitelny_strop()` → `nova_rezervovana_kapacita_kw` bez úprav.

**Co je špatně:** strop je nalezen s dokonalou znalostí jednoho historického roku.
Meziroční variabilita profilu, výpadek/servis baterie nebo o chlup jiná zima znamenají
překročení. Praxe: rezerva 5–15 % (Flowbox uvádí 10–20 %); studie: perfect-foresight
dimenzování je ex post ztrátové u ~50 % odběrných míst.

**Náprava:** `RK_sjednaná = strop × (1 + rezerva)`, default rezerva 5–10 % v manažerském
nastavení; do výstupu citlivost („RK o 5 % níž: úspora +X Kč, riziko pokut +Y“).
Volitelně percentilový režim (strop drží 95.–99. percentil dní, zbytek oceněn pokutou
1,5× MRK).

---

## PS-7 ⚠️ P2 — Atribuce úspory: baseline je současná (často předimenzovaná) RK (rozhodnuto: přidat fair baseline)

**Kde:** `ekonomika_2026()` — `soucasny_naklad` z `vstup.rezervovana_kapacita_kw`.

**Co je špatně:** část „úspory baterie“ jde získat zadarmo administrativním snížením RK.
Test T5: úspora dle nástroje 285 tis. Kč/rok (návratnost 7,0 let), z toho 85 tis. Kč/rok
dosažitelných bez investice → poctivá návratnost baterie 10,0 let. Se správnou pokutou
(PS-2, 422,73 Kč/kW) je break-even snížení RK ≈ 7 měsíců s překročením → optimální RK
bez baterie leží ~u mediánu měsíčních maxim. ERÚ navíc umožňuje kombinovat roční +
měsíční RK (sezónnost) — další úspora bez investice.

**Náprava (rozhodnuto 16. 7. 2026):**
1. Optimalizátor RK bez baterie: grid-search přes kandidátní RK (unikátní hodnoty
   měsíčních maxim), náklad = 12×roční sazba×RK + Σ max(0, M_m − RK) × 1,5×MRK;
   rozšíření o kombinaci roční RK + měsíční RK pro vybrané měsíce (O(n) přes měsíce).
2. Výstup: „úspora hned bez investice“ (nový prodejní artefakt — audit RK zdarma)
   a „přínos baterie“ = náklad(optimální RK bez baterie) − náklad(optimální RK s baterií).
3. Tentýž optimalizátor spustit i na profil po baterii (i s baterií může být výhodné
   nechat 1–2 měsíce v pokutě).

---

## PS-8 ⚠️ P2 — Výběr vítěze řídí tarif 2026, který platí jen do konce roku 2026

**Kde:** `vyber_reseni()` / `Varianta._radici_klic()` — řadí podle `navratnost_roky`
(= model 2026).

**Co je špatně:** baterie kupovaná v H2 2026 prožije celou životnost v NTS 2027+.
Rozhodovat vítěze podle tarifu s ~půlroční zbývající platností je zpětné.

**Náprava:** ekonomiku počítat na horizontu životnosti (10–15 let): zbytek 2026 stará
struktura + roky 2027+ NTS (po PS-3 bez AKU); vítěz dle NPV (viz PS-9). Do vydání
závazného výměru 2027 označovat „modelový odhad“ (mechanismus `je_modelovy_odhad` už
existuje a funguje dobře).

---

## PS-9 ⚠️ P2 — Prostá návratnost bez diskontu, O&M, degradace a životnosti

**Kde:** `_navratnost()` = cena/úspora; žádné O&M, diskont, degradace úspor, životnost.

**Dopad:** diskontovaná návratnost vychází typicky o 30–60 % delší než prostá; výběr
„nejkratší prostá návratnost“ navíc systematicky preferuje nejmenší baterii.

**Náprava:** NPV cash flow (diskont default 8 %, horizont 10–15 let, O&M 1,5–2,5 %
CAPEX/rok, degradace úspor ~1,5–2 %/rok, ztráty z PS-5); výběr varianty dle NPV,
prostou návratnost zobrazit doplňkově. PPA modul už `_npv`/`_irr` má — lze sdílet.

---

## PS-10 ℹ️ P2 — Robustnost stropu: jednoletá historie, žádná validace

**Kde:** celé jádro pracuje s jedním rokem profilu.

**Náprava:** podpora ≥ 2 let profilu (walk-forward: strop z roku 1 vyhodnotit na roce 2,
reportovat selhané měsíce a jejich cenu); levná alternativa: bootstrap škálování špiček
±5–10 % a report citlivosti. Souvisí s validací pokrytí (SP-1).

---

## Drobnosti (nice-to-have)

- `vyber_reseni()`: greedy ukončení přidávání kusů („další kus už nezlepšil“) může minout
  nemonotónní zlepšení (vzácné; případně dohledat všech 1–5 kusů bez `break`).
- `graf_maxima()`: `s_baterii_2026 = min(raw, strop)` je jen vizualizační aproximace —
  po zavedení ztrát (PS-5) použít skutečná maxima ze simulace.
- Penalizace „odběr zcela bez sjednané RK = 2× MRK“ (bod 4.24 výměru) — okrajový případ,
  do modelu netřeba, ale nezaměňovat s 1,5×.
- Od 1. 10. 2025 samostatná úložiště („akumulace 1. kategorie“) RK neplatí — jiný
  business case, netýká se BTM peak shavingu, ale hodí se vědět při dotazech klientů.
