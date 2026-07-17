# Rešerše kalkulátorů (PPA FVE + Peak shaving)

Podklady z auditu výpočetní logiky Nabídkovače provedeného **16. 7. 2026** (kontrola
`backend/app/nabidkovac/ppa_fve.py` a `peak_shaving.py` + 4 webové rešerše s primárními
zdroji + syntetické testy). Slouží jako **zdroj ověřených čísel a metodik** pro opravy
a další vývoj kalkulátorů.

## Obsah

| Soubor | Co obsahuje |
|---|---|
| [eru-sazby-2026-a-nts-2027.md](eru-sazby-2026-a-nts-2027.md) | Ověřené regulované ceny distribuce VN/VVN 2026 (cenový výměr ERÚ 13/2025) + nová tarifní struktura od 2027 vč. koeficientu AKU — **primární zdroje (PDF ERÚ)** |
| [pvgis-kalibrace-vyroby-fve.md](pvgis-kalibrace-vyroby-fve.md) | Kalibrační data výroby FVE pro ČR z PVGIS API (měrný výnos, měsíční profil, korekce orientace, degradace, letní čas) |
| [pvgis-data.csv](pvgis-data.csv) | Surová data všech 39 PVGIS měření (v5.2 + v5.3; roční E_y, SD_y a měsíční E_m pro 1 kWp) |
| [onsite-ppa-praxe-cr.md](onsite-ppa-praxe-cr.md) | Praxe on-site PPA v ČR: vyhnutelné regulované platby při samospotřebě, struktura smluv, tržní benchmarky (PPA ceny, CAPEX, O&M, přebytky, diskont) |
| [peak-shaving-metodiky-dimenzovani.md](peak-shaving-metodiky-dimenzovani.md) | Jak se peak shaving modeluje jinde: ztráty/DoD/degradace, bezpečnostní rezervy, optimalizace RK, řízení, value stacking, ekonomika, literatura |
| [bughunt/](bughunt/README.md) | **Odhalené chyby a návrhy nápravy** (prioritizované P0–P3) |

## Klíčová data k hlídání

- **říjen 2026** — veřejná konzultace ERÚ k parametrizaci koeficientu AKU (NTS).
- **~listopad 2026** — závazný cenový výměr ERÚ pro rok 2027 → přepsat modelové seedy
  `nova_2027` na ostré hodnoty.
- Ověřit obsah změnového výměru **CV 3/2026** (19. 6. 2026) — rešerše ho nedohledala
  v detailu (pravděpodobně se RK netýká): https://eru.gov.cz/cenove-vymery

## Jak rešerše vznikly

Čtyři paralelní výzkumní agenti (Claude) s webovým vyhledáváním; klíčová čísla ověřená
**primárními zdroji** (PDF cenových výměrů ERÚ, informativní výměr NTS, koncepce a manuál
ERÚ, PVGIS API v5.2/v5.3). U každého tvrzení je uvedena míra jistoty a URL zdroje.
Reporty jsou uložené doslovně tak, jak je agenti odevzdali (bez dodatečných úprav čísel).
