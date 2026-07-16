# Kalibrační data výroby FVE pro ČR z PVGIS (JRC)

> Součást auditu kalkulátorů 16. 7. 2026 (viz [README](README.md)). Surová data všech
> měření: [pvgis-data.csv](pvgis-data.csv) (39 řádků, v5.2 + v5.3, roční E_y + SD_y +
> měsíční E_m pro 1 kWp). Určeno ke kalibraci interního modelu výroby v
> `backend/app/nabidkovac/ppa_fve.py` (konstanty `VYCHOZI_MERNY_VYNOS_KWH_KWP`,
> `_MESICNI_VYNOS`, `_ORIENT_TAB`).

## Metodika

- **Zdroj:** PVGIS API **v5.2** (DB PVGIS-SARAH2, satelitní data 2005–2020) a **v5.3** (DB PVGIS-SARAH3, **2005–2023**, produkční verze od 09/2024). Obě verze staženy pro všech 19 konfigurací (celkem 40 volání API), parametry: `peakpower=1`, `loss=14`, `outputformat=json`.
- **Ověření:** hodnoty staženy přímo jako JSON a křížově zkontrolovány přes druhé nezávislé stažení téhož URL — shoda na setinu kWh. Verze v5.2 vs. v5.3 se liší < 1,5 %, poměry orientací se shodují na ±0,003 → čísla jsou robustní.
- **Primární sada = v5.3 (SARAH3)** — novější, zahrnuje slunečnější roky 2021–2023.

---

## A) Regionální rozptyl ročního výnosu (sklon 35°, jih, ztráty 14 %)

| Lokalita | E_y v5.3 (SARAH3) | E_y v5.2 (SARAH2) | vs. střed ČR |
|---|---|---|---|
| Ústí nad Labem (50.66, 14.03) | **1 029** | 1 026 | −2,5 % |
| Střed ČR (49.8, 15.5) | **1 055** | 1 047 | ref. |
| Ostrava (49.82, 18.26) | **1 063** | 1 057 | +0,7 % |
| Praha (50.08, 14.43) | **1 092** | 1 084 | +3,4 % |
| České Budějovice (48.97, 14.47) | **1 095** | 1 081 | +3,8 % |
| Brno (49.20, 16.61) | **1 117** | 1 118 | +5,8 % |
| Břeclav / jižní Morava (48.76, 16.88) | **1 164** | 1 151 | +10,3 % |

- Rozpětí v rámci ČR: **~1 030–1 165 kWh/kWp** (sever/severozápad → jižní Morava), tj. ±6–7 % kolem středu.
- Meziroční variabilita (SD_y z PVGIS, střed ČR): **±59 kWh ≈ ±5,6 %** — jednotlivé roky se od průměru běžně liší o ±6 %.
- PVGIS optimum pro střed ČR (`optimalangles=1`): **sklon 37°, azimut −4°** (E_y 1 056) → předpoklad „35° jih“ je prakticky optimum (rozdíl < 0,1 %).

**→ Interní default 1 000 kWh/kWp je podhodnocený o ~5,5 % vůči středu ČR a o ~16 % vůči jižní Moravě.**

## B) Měsíční profil, střed ČR (49.8, 15.5, 35°, jih)

| Měsíc | E_m v5.3 (kWh/kWp) | Normováno na 1000 | Interní | Δ |
|---|---|---|---|---|
| leden | 32,3 | 30,6 | 26 | **+4,6** |
| únor | 54,7 | 51,8 | 42 | **+9,8** |
| březen | 89,6 | 84,9 | 83 | +1,9 |
| duben | 120,0 | 113,7 | 120 | −6,3 |
| květen | 127,6 | 120,9 | 135 | **−14,1** |
| červen | 129,9 | 123,1 | 132 | −8,9 |
| červenec | 131,5 | 124,6 | 138 | **−13,4** |
| srpen | 121,2 | 114,9 | 120 | −5,1 |
| září | 103,9 | 98,5 | 90 | **+8,5** |
| říjen | 76,0 | 72,0 | 58 | **+14,0** |
| listopad | 37,9 | 36,0 | 30 | +6,0 |
| prosinec | 30,6 | 29,0 | 26 | +3,0 |

**Interní profil je příliš „špičatý“ do léta:** zimní půlrok (říj–bře) reálně tvoří **30,4 %** ročního výnosu, interně jen 26,5 %. Největší chyby: říjen (+24 % relativně), květen a červenec (−10 % relativně). Důvod: reálná data zahrnují letní teplotní ztráty panelů a podzimní/zimní přímou složku, kterou ilustrativní tabulka podceňuje.

## C) Korekční tabulka orientace k_orient (střed ČR, poměr k 35°/jih; azimut = odklon k západu)

**PVGIS v5.3 (doporučené hodnoty):**

| sklon \ azimut | 0° (jih) | 45° (JZ) | 90° (Z) | 180° (S) |
|---|---|---|---|---|
| 0° | 0,85 | 0,85 | 0,85 | 0,85 |
| 15° | 0,95 | 0,92 | 0,84 | 0,72 |
| 35° | 1,00 | 0,94 | 0,80 | 0,54 |
| 60° | 0,94 | 0,87 | 0,70 | 0,34 |

Interní vs. PVGIS — největší odchylky:
- **Sever je výrazně nadhodnocený:** 35°/S interně 0,66 vs. reálně **0,54**; 60°/S interně 0,50 vs. reálně **0,34** (chyba +48 % relativně!).
- **Strmý jih je podhodnocený:** 60°/J interně 0,91 vs. reálně **0,94** (fasády/ploty jsou lepší, než model tvrdí).
- Vodorovná plocha: 0,88 → **0,85**; východ/západ při 35°: 0,84 → **0,80**.
- **Symetrie V/Z:** východní strana je o ~1 p. b. lepší (JV 0,950 vs. JZ 0,940; V 0,811 vs. Z 0,797 — chladnější dopoledne). Symetrická aproximace je OK; přesnější je průměr JV+JZ ≈ 0,95 a V+Z ≈ 0,80.

## D) Doplňkové poznatky

**1. Degradace krystalických panelů**
- Terénní data NREL (Jordan & Kurtz, „Photovoltaic Degradation Rates — An Analytical Review“; Compendium 2016): **medián 0,5–0,6 %/rok**, průměr ~0,8 %/rok; první rok je horší (medián až ~1,3 %/rok) kvůli LID.
- First-year LID: p-type PERC typicky **1,5–3 %** (běžně ~2 %), n-type TOPCon **~1 %** (odolnost vůči B-O defektům). Záruční standard: 98–99 % po 1. roce, pak lineárně **0,40 % (TOPCon) / 0,45–0,55 % (PERC) ročně** → 87,4 % po 25–30 letech.
- **Doporučení pro model:** rok 1: −2 % (PERC) / −1 % (TOPCon); roky 2+: −0,5 %/rok (medián), konzervativně −0,55 %.

**2. Posun solárního poledne vůči SEČ/SELČ**
- SEČ (UTC+1) odpovídá poledníku 15° v. d., který ČR přímo protíná → korekce délky je malá: Praha (14,43°) +2 min, západ ČR (Aš, 12,1°) +12 min, východ (Jablunkov, 18,9°) **−15 min**; napříč ČR se poledne posouvá o **~27 minut**.
- Časová rovnice přidává −14 min (pol. února) až +16 min (zač. listopadu); v červenci ≈ −6 min. Solární poledne v Praze: **11:46–12:16 SEČ** dle sezóny; v létě ≈ 12:08 SEČ = **13:08 SELČ**.
- **Dopad na 15min profil:** v letním čase je špička výroby kolem **13:00 SELČ**, tj. posun o ~4 čtvrthodiny proti naivnímu „poledni“. Doporučení: počítat sluneční geometrii v UTC a na SEČ/SELČ převádět až na výstupu; pozor na dny přechodu času (92/100 čtvrthodin dle konvence OTE).

**3. PVGIS a oblačnost**
- Ano, PVGIS je **all-sky (reálné počasí), ne clear-sky**: SARAH2/3 jsou satelitní databáze, kde „prvním krokem výpočtu je odhad vlivu oblačnosti na sluneční záření ze satelitních snímků“ (dokumentace JRC). Výstupy PVcalc jsou dlouhodobé průměry reálných hodinových dat 2005–2023.
- PVGIS TMY (samostatný nástroj) vybírá reprezentativní měsíce z reálných let dle ISO 15927-4 — také včetně oblačnosti. Hodnoty tedy **nezahrnují degradaci** (platí pro novou instalaci) a nezohledňují sníh/stínění horizontu budovami.

---

## Doporučené hodnoty k nasazení

1. **Měrný roční výnos (35°, jih, ztráty 14 %):** default **1 055 kWh/kWp** (střed ČR); ideálně regionalizovat interpolací, min. však tabulkou A (1 030 sever → 1 165 jižní Morava). U nabídek uvádět ±6 % meziroční nejistotu.
2. **Měsíční rozdělení (na 1 000 kWh):** led 31 / úno 52 / bře 85 / dub 114 / kvě 121 / čvn 123 / čvc 125 / srp 115 / zář 98 / říj 72 / lis 36 / pro 29 (celkem 1 000).
3. **k_orient:** nasadit tabulku C výše (nejkritičtější opravy: sever 0,54 resp. 0,34; strmý jih 0,94; horizontála 0,85).
4. **Degradace:** rok 1 −2 %/−1 % dle technologie, dále −0,5 %/rok.

## Zdroje

- PVGIS API v5.2/v5.3 PVcalc (JRC): `https://re.jrc.ec.europa.eu/api/v5_3/PVcalc?lat=49.8&lon=15.5&peakpower=1&loss=14&angle=35&aspect=0&outputformat=json` (analogicky ostatní konfigurace)
- [PVGIS — zdroje dat a metody výpočtu (JRC)](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/pvgis-data-sources-calculation-methods_en) — all-sky satelitní data, vliv oblačnosti
- [PVGIS 5.3 release notes](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-releases/pvgis-53_en) — SARAH3, 2005–2023
- [PVGIS TMY generátor](https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/pvgis-tools/pvgis-typical-meteorological-year-tmy-generator_en) — ISO 15927-4
- [NREL: Photovoltaic Degradation Rates — An Analytical Review (Jordan & Kurtz)](https://docs.nlr.gov/docs/fy12osti/51664.pdf) · [NREL: Compendium of Photovoltaic Degradation Rates](https://research-hub.nrel.gov/en/publications/compendium-of-photovoltaic-degradation-rates-2) · [NREL: Understanding LID of c-Si Solar Cells](https://docs.nlr.gov/docs/fy12osti/54200.pdf)
- Přehledy záručních degradací výrobců: [SurgePV — Solar Panel Warranty Comparison](https://www.surgepv.com/blog/solar-panel-warranty-comparison), [energy-solutions.co — Degradation Rates 2026 (NREL analýza)](https://energy-solutions.co/articles/sub/solar-panel-degradation-rates-2026)
