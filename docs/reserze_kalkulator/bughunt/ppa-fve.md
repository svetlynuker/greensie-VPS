# Bughunt: PPA pro FVE (`backend/app/nabidkovac/ppa_fve.py` + `routes.py` + `PpaPanel.jsx`)

> Nálezy auditu 16. 7. 2026. Ověřená čísla: [../pvgis-kalibrace-vyroby-fve.md](../pvgis-kalibrace-vyroby-fve.md)
> a [../onsite-ppa-praxe-cr.md](../onsite-ppa-praxe-cr.md), kvantifikace:
> [synteticke-testy.md](synteticke-testy.md). Priority viz [README](README.md).

---

## PPA-1 🐞 P0 — Sweep velikostí překračuje limit střechy `max_kwp` < 5 kWp

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(ppa): sweep velikostí nepřekračuje max_kwp (PPA-1)`
> na větvi `bughunt-opravy-p0`. `max(cap, 5.0)` se aplikuje před `min(cap, max_kwp)`
> (limit střechy je tvrdý); pro `max_kwp < 1` se vrací aspoň `[1]`.
> Testy: `test_ppa_fve.py::TestKandidatniVelikosti`.

**Kde:** `kandidatni_velikosti()` — `cap = max(cap, 5.0)` se aplikuje **až po**
`cap = min(cap, max_kwp)`.

**Důkaz (test T1):** `max_kwp = 3.0` → kandidáti `[1, 2, 3, 4, 5]`; ekonomický výběr pak
může doporučit FVE větší, než se na střechu vejde.

**Náprava:** minimální cap uplatnit před oříznutím limitem:
```python
cap = _MAX_POMER_VYROBA_SPOTREBA * e_spotreba / prod_per_kwp
cap = max(cap, 5.0)
if max_kwp and max_kwp > 0:
    cap = min(cap, max_kwp)
```
(+ zajistit aspoň 1 kandidát, když `max_kwp < 1`; test na to.)

---

## PPA-2 ⚠️ P1 — Kalibrace: měrný výnos, měsíční tabulka a orientace jsou ilustrativní a odchylují se od reality

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(ppa): kalibrace výroby dle PVGIS v5.3 + posun letního času (PPA-2, PPA-3)`
> na větvi `bughunt-opravy-p0`. Výnos 1055, měsíční řada = přesné normované
> hodnoty SARAH3 (Σ = 1000; celočíselná řada z rešerše by sečetla 1001),
> k_orient dle kap. C. Regionalizace dle GPS a PVGIS API = fáze 2.
> Testy: `test_ppa_fve.py::TestKalibraceVyroby`.

**Kde:** `VYCHOZI_MERNY_VYNOS_KWH_KWP = 1000`, `_MESICNI_VYNOS`, `_ORIENT_TAB`
(vše označeno ⚠️ ke kalibraci — kalibrace je teď hotová, viz PVGIS rešerše).

**Odchylky (PVGIS v5.3, reálná oblačnost):**
- roční výnos 35°/jih: **1 055** kWh/kWp střed ČR (1 030 sever – 1 164 jižní Morava)
  → interních 1 000 podhodnocuje o 5–16 %;
- měsíční tabulka moc „letní“: říjen reálně 72 (interně 58, +24 % rel.), květen 121
  (135), červenec 125 (138); zimní půlrok reálně 30,4 % ročního výnosu vs. 26,5 % interně;
- orientace: sever 35° reálně **0,54** (interně 0,66), sever 60° **0,34** (0,50!),
  horizontála **0,85** (0,88), V/Z 35° **0,80** (0,84), strmý jih 60° **0,94** (0,91).

**Dopad:** návrh velikosti, % pokrytí i výnos investora; největší chyba u severních
střech (nadhodnocení skoro o polovinu) a u zimní samospotřeby.

**Náprava:** nasadit doporučené hodnoty z [../pvgis-kalibrace-vyroby-fve.md](../pvgis-kalibrace-vyroby-fve.md)
(kap. „Doporučené hodnoty k nasazení“): výnos 1 055 (ideálně regionalizace dle GPS
interpolací tabulky A), měsíční řadu 31/52/85/114/121/123/125/115/98/72/36/29,
tabulku k_orient dle kap. C. Surová data: [../pvgis-data.csv](../pvgis-data.csv).
Fáze 2: PVGIS API za runtime z GPS (s cache, fallback na interní model).

---

## PPA-3 ⚠️ P1 — Letní čas: výroba centrovaná na 12:00 místního času, reálně ~13:00 SELČ

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(ppa): kalibrace výroby dle PVGIS v5.3 + posun letního času (PPA-2, PPA-3)`
> na větvi `bughunt-opravy-p0`. V okně SELČ (poslední neděle března 02:00 –
> poslední neděle října 03:00) se tvar dne vyhodnocuje v `g(t − 1 h)` → letní
> špička výroby ~13:00 lokálního času. Jemnější korekce (délka, časová rovnice,
> ±15 min) zůstávají vědomě zanedbané. Testy: `test_ppa_fve.py::TestLetniCas`.

**Kde:** `simuluj_vyrobu()` — `t_h` z lokálních časových značek, solární okno centrované
na 12:00 (`_slunecni_okno`).

**Důkaz (test T4):** chyba samospotřeby **+1,6 %** u ranního provozu (7–17 h), ale
**−7,0 %** u odpoledního provozu (12–22 h) — model „vyrábí“ o hodinu dřív, než slunce
reálně svítí.

**Náprava:** v okně letního času (poslední neděle v březnu – poslední neděle v říjnu)
vyhodnocovat tvar `g(t − 1 h)`; čistší varianta: počítat geometrii v UTC + korekce
délky (λ − 15°) × 4 min a času (equation of time) — viz PVGIS rešerše kap. D2.

---

## PPA-4 ⚠️ P1 — Degradace: chybí LID prvního roku

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(ppa): LID prvního roku v degradaci (PPA-4)`
> na větvi `bughunt-opravy-p0`. `f(t) = (1 − LID) × (1 − d)^(t−1)`; parametr
> `ppa_degradace_rok1` v manažerském nastavení, default 0,02 (PERC; rozhodnuto),
> TOPCon 0,01 ručně. Headline metriky i graf ukazují rok 1 včetně LID.
> Testy: `test_ppa_fve.py::TestDegradaceLid`.

**Kde:** `VYCHOZI_DEGRADACE_ROCNI = 0.005`, `spocti_ppa()` — `(1−d)^(t−1)`.

**Co je špatně:** plochých 0,5 %/rok ignoruje pokles prvního roku (LID): PERC typicky
−1,5 až −3 %, TOPCon ~−1 %. Nadhodnocuje výrobu (a výnos investora) po celou dobu kontraktu.

**Náprava:** parametr `ppa_degradace_rok1` (default −2 % PERC / −1 % TOPCon; manažerské
nastavení), pak −0,5 %/rok: `f(t) = (1 − d1) × (1 − d)^(t−1)` pro t ≥ 1.

---

## PPA-5 ⚠️ P1 — Úspora klienta: „cena dodavatele“ nezahrnuje vyhnutelné regulované složky (rozhodnuto: rozložit vstup)

> ✅ **Vyřešeno 16. 7. 2026** — commit `fix(ppa): rozklad ceny dodavatele na silovou + vyhnutelné regulované (PPA-5)`
> na větvi `bughunt-opravy-p0`. Vstup `cena_silova_kc_mwh` (OZ, eskaluje se
> indexem dodavatele) + `vyhnutelne_regulovane_kc_mwh` (default 260 Kč/MWh
> z manažerského nastavení, eskalace samostatně default 0, POZE oddělený
> parametr default 0). Úspora = SS × (silová + regulované − PPA). Výstup nese
> rozklad + `uspora_zahrnuje`; daň z elektřiny symetricky mimo; u výroben
> > 30 kW upozornění na registraci u celní správy. FE panel má nové pole,
> starší uložené výsledky se předvyplní z původního klíče.
> Testy: `test_ppa_fve.py::TestRozkladCenyDodavatele`.

**Kde:** `spocti_ppa()` — `uspora = SS × (cena_dod − cena_ppa)`; FE placeholder
„silová složka, např. 4000“ (`PpaPanel.jsx`).

**Co je špatně:** samospotřeba za elektroměrem se vyhne kromě silové elektřiny i
variabilním regulovaným platbám. Pro VN 2026 (bez DPH):

| Složka | Kč/MWh | Šetří se? |
|---|---|---|
| Použití sítí VN (ČEZ/EG.D/PRE) | ~83–106 | ✅ |
| Systémové služby | 164,24 | ✅ |
| POZE | 0 (2026; dřív až 495 — parametr) | ✅ (0) |
| Daň z elektřiny | 28,30 | ❌ u FVE > 30 kW (PPA dodávka jí podléhá taky) |
| OTE, RK, jistič, fixy | — | ❌ (nejsou za MWh) |

Se zadanou jen silovou cenou se úspora podhodnocuje o **~250–270 Kč/MWh** (≈ 8–10 %);
kdyby OZ zadal celou koncovou cenu, naopak by se nadhodnotila o fixní složky a daň.

**Náprava (rozhodnuto 16. 7. 2026):** rozložit vstup na dvě pole:
1. `cena_silova_kc_mwh` (zadává OZ, eskaluje se indexem dodavatele),
2. `vyhnutelne_regulovane_kc_mwh` (default ~250–270 z manažerského nastavení; eskalace
   samostatný parametr, default 0; POZE jako oddělený parametr default 0).
Úspora klienta = SS × (silová + regulované − PPA cena). Do výstupu příznak, co
srovnání obsahuje. Pozn.: daň z elektřiny nechat mimo obě strany (symetrická);
u investora zmínit registrační povinnost u celní správy (výrobna > 30 kW).

---

## PPA-6 ⚠️ P1 — Ekonomika investora: defaulty přikrášlují (O&M 0, diskont 5 %, bez výměny střídače)

**Kde:** manažerské defaulty (`ppa_oam_kc_kwp_rok` 0, `ppa_diskontni_sazba` 0,05);
`spocti_ppa()` nemá jednorázové náklady v průběhu kontraktu.

**Benchmarky (viz PPA rešerše):** O&M 1–2 % CAPEX/rok (~250–500 Kč/kWp/rok vč. pojištění,
revizí, monitoringu); WACC investora ~6–9 % → diskont default 7–8 %; výměna střídače
~rok 10–15 (~5–10 % CAPEX).

**Náprava:** změnit defaulty v manažerském nastavení (O&M ~350 Kč/kWp/rok, diskont 7,5 %),
přidat volitelnou položku `ppa_vymena_stridace = {rok, kc_kwp}` do cash flow; O&M
volitelně eskalovat inflací. Ve výstupu nechat viditelné, které nákladové položky jsou
zapnuté (princip „příznaky předpokladů“ z metodiky už existuje).

---

## PPA-7 ℹ️ P2 — Přebytky: cena a trend

**Kde:** `prebytek_cena_kc_mwh` (zadává OZ), `ppa_index_prebytek_rocni` default 0.

**Kontext z rešerše:** zachycená cena FVE ≈ 55–70 % spotové base (**~1 300–1 700 Kč/MWh**)
a klesá; 348 záporných hodin v 2025, jaro 2026 rekordy. Default „neúčtovat“ je správně
konzervativní.

**Náprava:** při zapnutém prodeji validovat zadanou cenu proti pásmu (varování mimo
800–2 000 Kč/MWh); do nápovědy OZ doplnit vodítko; zvážit záporný default trendu
(index −2 až −5 %/rok) nebo aspoň upozornění. Alternativa přebytků: sdílení přes EDC
na další OPM klienta (fáze 2/3).

---

## PPA-8 ℹ️ P2 — Prezentace: záporné NPV bez varování, chybí sanity-check PPA ceny

**Kde:** `routes.py` (žádný flag), `PpaPanel.jsx` (NPV se jen zobrazí).

**Náprava:**
1. `doporuceno = npv_kc > 0` (obdoba peak shavingu) + hláška „PPA se při těchto
   parametrech investorovi nevyplatí“.
2. Sanity-check PPA ceny proti pásmu trhu 1 600–2 600 Kč/MWh a proti vyhnutelné ceně
   klienta (PPA cena ≥ vyhnutelná cena → klient nešetří nic → varování).
3. Upozornění na riziko poklesu spotřeby (výnos investora je úměrný samospotřebě;
   reálné smlouvy řeší take-or-pay) — volitelný citlivostní parametr „pokles spotřeby %/rok“.

---

## PPA-9 ℹ️ P3 — CAPEX škála a vazba na překročení rezervovaného výkonu

1. **CAPEX podle velikosti:** jednotná cena/kWp zkresluje sweep (velké FVE reálně
   ~18–25 tis. Kč/kWp, malé ~28–35 tis.). Náprava: tabulka cena/kWp po pásmech velikosti
   v manažerském nastavení (`capex_fn` už je funkce kWp, změna je lokální).
2. **Strop přetoku:** model tvrdě ořezává export nad `rezervovany_vykon_dodavky_kw` —
   to odpovídá správně nastavené výkonové regulaci střídače. Pro úplnost: skutečná
   penalizace za překročení rezervovaného výkonu je 1 108 (VN) / 521 (VVN) Kč/kW/měs
   (viz ERÚ rešerše A3.3) — hodí se jako upozornění, proč je ořez nutný, ne jako výnosová
   příležitost.
3. **Komponentový CAPEX:** `ceil(kwp / invertor_kw)` dimenzuje AC 1:1 k DC; reálné
   DC/AC ratio bývá 1,1–1,3 → mírně konzervativní. Nechat, případně parametr.

---

## Poznámky — co je v pořádku (ověřeno)

- Vzorec úspory `SS × (cena_dod − PPA)` je standard trhu (ČEZ ESCO, E.ON, TEDOM,
  GreenBuddies) — jen s korekcí PPA-5.
- Indexace PPA X %/rok odpovídá praxi (TEDOM: CPI ČSÚ; ČEZ ESCO: fix); default eskalace
  dodavatele zvážit ~2–2,5 % (inflace) místo = PPA index — forwardy CAL-27/28 rostou jen mírně.
- Ekonomický výběr velikosti (max NPV, sekundárně payback) je korektní přístup;
  `sparuj()` (samospotřeba → export → ořez) odpovídá metodice i realitě BTM instalace.
- Payback s lineární interpolací, NPV, IRR bisekcí — matematicky v pořádku (ověřeno testy).
- Linearita výroby v kWp + jednorázová simulace 1 kWp pro sweep — správné a rychlé.
