# Bughunt: společné — profil spotřeby a integrita dat

> Nálezy auditu 16. 7. 2026. Týkají se obou modulů (PPA i peak shaving), protože oba
> čtou stejnou tabulku `spotreba_profil` přes `routes.py`. Kvantifikace:
> [synteticke-testy.md](synteticke-testy.md). Priority viz [README](README.md).

---

## SP-1 ⛔ P0 — Žádná kontrola pokrytí roku: neúplný profil tiše vyrábí nesmyslnou „roční“ ekonomiku

**Kde:** `routes.py` — `spocti_peak_shaving()` i `spocti_ppa()` berou z DB všechno, co
tam je; `ppa_fve.spocti_ppa()` označí `sum(spotreba_kwh)` jako `rocni_spotreba_kwh`;
`peak_shaving.vychozi_rocni_naklad_2026()` sčítá pokuty jen přes měsíce přítomné v profilu.

**Důkaz (testy T2/T3):**
- Půlroční profil (leden–červen): PPA vydá „roční spotřebu“ 175 MWh (reálně půlroční),
  výrobu 53,8 MWh — úspory/výnosy jsou poloviční, ale CAPEX plný → payback/NPV/IRR
  zásadně zkreslené. Peak shaving: roční platba za RK vs. pokuty jen za 6 měsíců.
- 13měsíční profil (leden 2025 – leden 2026): `simuluj_vyrobu()` rozpustí lednovou
  energii do **62 dnů dvou lednů** → lednová výroba 13 kWh/kWp místo 26; celková výroba
  za 13 měsíců = roční výnos (chybí energie druhého ledna). Bilance výroba vs. spotřeba
  je systematicky vychýlená.

**Náprava:**
1. Ve výpočetních route validovat pokrytí: rozsah časů ~350–380 dní, počet intervalů
   ~33 600–36 000 (při 15 min), počet přítomných kalendářních měsíců = 12, děr < ~2 %.
2. Mimo toleranci → HTTP 422 s vysvětlením (tvrdá chyba; případně manažerský přepínač
   „povolit s varováním“).
3. Profil delší než rok: automaticky oříznout na posledních 12 celých měsíců (a říct to
   ve výstupu).
4. `profil-souhrn` endpointy už vrací od/do/počet — frontend může varovat ještě před
   výpočtem.

---

## SP-2 ⛔ P0 — Duplicitní profily se sčítají (chybí unique constraint / filtr zdroje)

**Kde:** `models.py` — `SpotrebaProfil` má jen indexy, žádný unique na
`(nabidka_id, cas)`; `routes.py` čte **všechny** řádky nabídky
(`zpracuj_profil()` maže jen řádky ze *stejného* dokumentu).

**Scénář:** OZ nahraje a zpracuje dva soubory s profilem (nový export, oprava, omylem
dvakrát) → tabulka obsahuje obě sady; výpočty vidí zdvojenou (proloženou) spotřebu:
PPA má 2× „roční spotřebu“, peak shaving simuluje dvojité intervaly (dvojnásobná doba
vybíjení baterie na špičce), `_interval_h_z_profilu()` může z duplicitních časů odvodit
fallback.

**Náprava (jedna z, ideálně obě):**
1. Číst profil jen z **posledního úspěšně zpracovaného dokumentu**
   (`zdroj_dokument_id = max`), a/nebo při zpracování nového dokumentu smazat profil
   z předchozích dokumentů téže nabídky (změna idempotence: „poslední vyhrává“).
2. DB pojistka: unique constraint na `(nabidka_id, cas)` — pozor na existující duplicitní
   data při migraci a na DST podzimní přechod (duplicitní lokální hodina v exportech,
   viz SP-3).

---

## SP-3 ⚠️ P1 — Odvození intervalu z prvních dvou vzorků + přechody času

**Kde:** `routes.py` — `_interval_h_z_profilu()`: `casy[1] − casy[0]`, fallback 0,25 h.

**Rizika:** díra nebo duplicita hned na začátku profilu → špatný interval pro celý
výpočet (kWh = kW × interval!); podzimní přechod času má v lokálním čase duplicitní
hodinu (v exportu OTE konvence 92/100 čtvrthodin), jarní zase díru.

**Náprava:** interval = **medián** rozdílů po sobě jdoucích časů (O(n)); při >2 %
intervalů s odchylkou od mediánu přidat upozornění do výstupu.

---

## SP-4 ℹ️ P2 — Import ignoruje sloupec `Status` a nevaliduje hodnoty

**Kde:** `profil_import.py` — bere `Datum` + `Profil +A [kW]`, sloupec `Status`
(měřeno/odhad/náhradní hodnota v PND exportech) se nečte; záporné hodnoty a extrémní
outliery se nefiltrují.

**Náprava:** volitelně číst `Status` a reportovat podíl neměřených hodnot (upozornění
do výstupu, ne blokace); hodnoty < 0 → 0 s upozorněním (odběr `+A` nemá být záporný);
outlier check (např. > 5× 99. percentil) jen jako varování. Formát čísel a dynamické
hledání hlavičky jsou jinak vyřešené dobře.

---

## Poznámky — co je v pořádku

- Přepočet kW → kWh přes skutečný interval (`hodnota_kw × interval_h`) je pro 15min
  průměrované PND profily korektní.
- Idempotence zpracování v rámci jednoho dokumentu (smaž + vlož) funguje.
- Formáty XLS/XLSX/CSV, česká desetinná čárka, dynamická hlavička — robustní.
