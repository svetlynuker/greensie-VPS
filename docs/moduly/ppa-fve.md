# PPA pro FVE – kompletní implementační souhrn

Souhrn modulu **PPA pro FVE** v Nabídkovači appky Greensie. Metodika (zdroj pravdy pro
vzorce) je v `docs/METODIKA-ppa-fve.md`; tenhle dokument popisuje **hotovou implementaci** –
co dělá, jak počítá, jaké má parametry, API, frontend a otevřené body.

**Princip:** Greensie (investor) postaví a vlastní FVE, klient nic neinvestuje a po dobu
kontraktu odebírá vyrobenou elektřinu za sjednanou (indexovanou) PPA cenu. Appka počítá dvě
ekonomiky nad stejnou fyzikou – **klientovi** ukazuje úsporu (dnes vs. s PPA), **investorovi**
návratnost (payback, IRR, NPV). Výrobu FVE si appka **sama simuluje** (nenahrává se), spotřeba
se bere z nahraného 15min profilu. Velikost FVE **navrhuje appka sama podle nejlepší
ekonomiky**. Všechny ceny **bez DPH**, výpočet je čistě deterministický.

Stav: nasazeno na produkci (`https://167-235-254-188.sslip.io`).

---

## 1. Přehled toku dat

1. OZ založí nabídku typu `ppa`, nahraje XLS/CSV s **15min profilem spotřeby** (stejný import
   jako peak shaving – činný výkon kW).
2. **Zpracování profilu** naparsuje soubor do `spotreba_profil` (kW po 15 min).
3. OZ zadá parametry FVE a PPA: sklon a azimut panelů, PPA cenu (Kč/MWh), cenu současného
   dodavatele (Kč/MWh), délku kontraktu; volitelně limit střechy (`max_kwp`), ruční výkon,
   přepínač režimu CAPEX a prodej přebytku + jeho cenu. **Velikost kWp OZ nezadává** – navrhne
   ji appka.
4. **Výpočet** (`POST …/ppa/vypocet`):
   - spotřeba se přepočte z kW na kWh (× délka intervalu),
   - simuluje se výroba FVE pro 1 kWp a dosadí do 15min průběhu spotřeby,
   - appka vyzkouší řadu velikostí, pro každou spočítá ekonomiku a vybere nejlepší (nejvyšší
     NPV / nejkratší návratnost), se zohledněním prodeje přebytku,
   - výsledek se uloží do `navrhovana_reseni.popis_json` (`typ_reseni = ppa`).
5. **Panel nabídky** zobrazí: navrženou velikost + **% pokrytí spotřeby z FVE**, ekonomiku
   investora, měsíční graf výroba vs. spotřeba, tabulku po letech a srovnání velikostí. Vstupy
   se předvyplní z posledního výpočtu, takže jde libovolně **přepočítávat**.

---

## 2. Datový model

**Bez nové tabulky a bez migrace.** Výroba je deterministická z parametrů, proto se
nepersistuje (recompute při výpočtu; do `popis_json` jdou měsíční agregáty). Modul využívá
existující tabulky:

- **`spotreba_profil`** – 15min profil spotřeby (`cas`, `hodnota_kw`, `zdroj_dokument_id`).
  PPA čte `hodnota_kw` a přepočítává na energii `kWh = kW × interval_h`.
- **`navrhovana_reseni`** – výstup výpočtu v `popis_json` (`typ_reseni = ppa`). Každý výpočet
  přidá nový řádek; panel načítá poslední.
- **`vypoctova_nastaveni.parametry`** (JSONB, verzované) – manažerské defaulty PPA. Klíče:

  | Klíč | Význam | Pozn. |
  |---|---|---|
  | `ppa_cena_fve_kc_kwp` | cena za kWp (zjednodušený CAPEX) | default 25 000 |
  | `ppa_ostatni_naklady_kc_kwp` | BOS (montáž/konstrukce) pro komponentový CAPEX | default 0 |
  | `ppa_merny_vynos_kwh_kwp` | měrný výnos FVE | default 1000; **pojistka 100–2000** |
  | `ppa_index_ceny_rocni` | roční eskalace PPA ceny | default 0,03 |
  | `ppa_index_dodavatel_rocni` | roční eskalace ceny dodavatele | default = index PPA |
  | `ppa_index_prebytek_rocni` | roční eskalace ceny přebytku | default 0 |
  | `ppa_degradace_rocni` | degradace panelů | default 0,005 |
  | `ppa_oam_kc_kwp_rok` | provozní náklady investora | default 0 |
  | `ppa_diskontni_sazba` | diskont pro NPV/IRR | default 0,05 |

  Spravuje se v adminu (právo `nabidkovac_katalog`); uložení = nová verze (staré zůstávají).

- Existující sloupce `vypoctova_nastaveni`: `koeficient_zisku`, `min/max_delka_kontraktu_roky`
  (zatím se v PPA výpočtu přímo nepoužívají – rezerva pro dopočet ceny z marže, viz otevřené body).

---

## 3. Výpočtová logika — `backend/app/nabidkovac/ppa_fve.py`

Čistě deterministický modul bez závislosti na DB/FastAPI (jako `peak_shaving.py`). Konstanty:
interval `0,25 h`, měrný výnos `1000` kWh/kWp, degradace `0,5 %/rok`, cena FVE `25 000` Kč/kWp,
šířka ČR `49,8°`, horní mez velikosti `3× roční spotřeba`.

### 3.1 Simulace výroby FVE (`simuluj_vyrobu`)
Roční výnos `E_rok = kWp × měrný_výnos × korekce_orientace(azimut, sklon)`. Rozpuštění:
- **po měsících** dle tabulky (kWh/kWp/měsíc při ročním výnosu 1000):
  led 26, úno 42, bře 83, dub 120, kvě 135, čvn 132, čvc 138, srp 120, zář 90, říj 58, lis 30, pro 26 (Σ = 1000);
- **měsíc na dny** podle počtu dní přítomných v profilu;
- **den na intervaly** clear-sky křivkou ze solární geometrie:
  ```
  δ   = 23,45° × sin(360°·(284+n)/365)            # deklinace, n = den v roce
  ω_s = arccos(−tan(φ)·tan(δ))                     # φ = zeměpisná šířka
  t_východ = 12 − ω_s/15 ;  t_západ = 12 + ω_s/15  # solární čas
  g(t) = max(0, sin(π·(t−t_východ)/(t_západ−t_východ)))
  V_i  = E_den · g(t_i) / Σ_den g                  # kWh za interval
  ```
- **korekce orientace** `k_orient(azimut, sklon)` – bilineární interpolace tabulky (jih+35° = 1,00; V/Z+35° ≈ 0,84; sever ≈ 0,50). ⚠️ ilustrativní hodnoty ke kalibraci.

Výroba je **lineární v kWp** → pro sweep se simuluje jednou pro 1 kWp a jen se škáluje.

### 3.2 Degradace (kap. 4.2 metodiky)
Rok `t`: `V_t = V_1 × (1 − degradace)^(t−1)`. Spárování se počítá znovu každý rok (min() je
nelineární).

### 3.3 Spárování výroby a spotřeby (`sparuj`) — samospotřeba / přetok / ořez / dokup
Pořadí toku v každém intervalu: nejdřív samospotřeba, pak přetok do sítě omezený rezervovaným
výkonem dodávky, zbytek ořez:
```
samospotreba_i = min(V_i, S_i)
prebytek_i     = max(0, V_i − S_i)
export_i       = min(prebytek_i, P_rez × interval_h)   # P_rez = rez. výkon dodávky (kW)
orez_i         = prebytek_i − export_i                 # nad P_rez → propadá (0 Kč)
dokup_i        = max(0, S_i − V_i)
```
`P_rez` prázdné/0 = neomezeno. Ořez **neovlivňuje samospotřebu** (ta je lokální).

### 3.4 Ekonomika po letech (`spocti_ppa`)
Ceny se eskalují geometricky (rok 1 = základ). Klient:
```
úspora_t = (samospotřeba_t / 1000) × (cena_dodavatel_t − cena_ppa_t)   # Kč
```
Investor:
```
CAPEX
výnos_t = (samospotřeba_t/1000)·cena_ppa_t  [+ (export_t/1000)·cena_přebytku_t, když se přebytek prodává]
cf_t    = výnos_t − O&M                        # O&M = ppa_oam_kc_kwp_rok × kWp
cf_kum_t = (Σ cf) − CAPEX
payback  = nejmenší t s cf_kum_t ≥ 0 (lin. interpolace)
NPV      = −CAPEX + Σ cf_t/(1+r)^t
IRR      = r, kde NPV = 0 (bisekce)
```
Prodej přebytku vstupuje **jen do výnosu investora** a jen když je zapnutý; ořezaná energie
nikdy nevýnosí.

### 3.5 CAPEX – dva režimy (`rezim_capex`)
- **`cena_kwp`** (default): `CAPEX = kWp × ppa_cena_fve_kc_kwp`.
- **`komponenty`**: poskládá z katalogu `technologie` – nejlevnější dostupný panel (`fve_panel`)
  a invertor (`invertor`) dle ceny/kW, počet = zaokrouhleno nahoru na pokrytí kWp, plus BOS
  `kWp × ppa_ostatni_naklady_kc_kwp`. Rozpad je ve výstupu.

### 3.6 Návrh velikosti = ekonomický výběr (`kandidatni_velikosti` + `vyber_velikost`)
1. Vygeneruje řadu velikostí (rovnoměrný krok od malé FVE po `3× roční spotřeba`, příp.
   omezeno `max_kwp`; ~30 kandidátů).
2. Pro každou spočítá kompletní ekonomiku (CAPEX per velikost + `spocti_ppa`).
3. Vybere **nejvyšší NPV**, sekundárně **nejkratší návratnost**; vrací i 2.–3. variantu.

Výběr **respektuje prodej přebytku**: bez prodeje větší FVE dává přebytek zadarmo → optimum je
menší; s prodejem za dobrou cenu se posune výš. Ruční `instalovany_vykon_kwp` sweep přeskočí a
počítá jen tu velikost.

> **Fyzický strop u „nesolární" zátěže:** když klient odebírá hlavně večer/v noci, samospotřeba
> z FVE je omezená (bez baterie i velká FVE pokryje jen menší část spotřeby, zbytek je přebytek).
> Ekonomický výběr to zohlední a nenavrhne předimenzovanou FVE, pokud se přebytek neprodává.
> Alternativní režim „největší kWp s mírou samospotřeby ≥ cíl" je v kódu (`navrhni_kwp`), ale
> výchozí je ekonomický výběr.

### 3.7 Data pro graf (`_graf_mesicni`)
Měsíční agregáty rok 1: spotřeba, výroba, samospotřeba, přetok, ořez, dokup.

### 3.8 Headline metriky
- `pokryti_spotreby_fve` = samospotřeba / roční spotřeba (**% spotřeby krytý z FVE**),
- `mira_samospotreby` = samospotřeba / výroba,
- `pomer_vyroba_spotreba` = výroba / spotřeba.

---

## 4. API (`backend/app/nabidkovac/routes.py`, prefix `/nabidkovac`)

| Metoda / cesta | Právo | Popis |
|---|---|---|
| `GET /nabidky/{id}/ppa/profil-souhrn` | nabidkovac | počet/rozsah/roční spotřeba (MWh) profilu |
| `POST /nabidky/{id}/ppa/vypocet` | nabidkovac | spustí výpočet, uloží do `navrhovana_reseni` |
| `POST /dokumenty/{id}/zpracuj-profil` | nabidkovac | naparsuje XLS/CSV → `spotreba_profil` (sdíleno s peak shavingem) |

**Vstup výpočtu** (`PpaVstup`): `sklon_st`, `azimut_st`, `cena_ppa_kc_mwh`,
`cena_dodavatel_kc_mwh`, `delka_kontraktu_roky`; volitelně `instalovany_vykon_kwp` (ruční
override), `max_kwp`, `rezim_capex`, `prebytek_uctovat`, `prebytek_cena_kc_mwh`,
`rezervovany_vykon_dodavky_kw`, `index_ppa_rocni`, `index_dodavatel_rocni`, `degradace_rocni`.

Route: načte profil, doplní defaulty z manažerského nastavení (`_ppa_param`), **ošetří
nereálný měrný výnos** (mimo 100–2000 → default 1000 + upozornění), určí lokalitu (GPS nabídky,
fallback 49,8°), sestaví `capex_fn(kwp)` a šablonu vstupu, a buď spustí ekonomický sweep, nebo
počítá ruční velikost.

**Výstup `popis_json`:** `vstup` (vč. `navrzeno_automaticky`, `metoda_navrhu`), `vysledek`
(kompletní ekonomika + `roky[]` + `graf`), `varianty` (top 4 velikosti pro srovnání),
`upozorneni`.

---

## 5. Frontend (`frontend/src`)

- **`components/PpaPanel.jsx`** (OZ, detail nabídky typu `ppa`): načtení profilu, zadání
  parametrů FVE/PPA, přepínač režimu CAPEX, prodej přebytku + cena, rez. výkon dodávky; výsledek
  – navržená velikost + zvýrazněné **% pokrytí spotřeby z FVE**, dlaždice payback/IRR/NPV/úspora
  klienta, tabulka **Srovnání velikostí**, měsíční graf, tabulka po letech. **Vstupy se
  předvyplní z posledního výpočtu** → jde libovolně přepočítávat a měnit hodnoty.
- **`components/GrafVyrobaSpotreba.jsx`**: lehký **SVG graf bez knihovny** – dvojice sloupců
  na měsíc (spotřeba = samospotřeba + dokup; výroba = samospotřeba + přetok + ořez).
- **`pages/NabidkaDetail.jsx`**: pro `typ = ppa` renderuje `PpaPanel`.
- **`pages/NabidkovacKatalog.jsx`**: admin – blok **PPA pro FVE** ve výpočtových nastaveních
  (cena/kWp, BOS, měrný výnos, indexy, O&M, diskont), se zachováním ostatních klíčů `parametry`.
- **`api.js`**: `ppaVypocet`, `ppaProfilSouhrn` (+ sdílené `profilZpracuj`).

---

## 6. Nasazení
Stejné jako zbytek appky (bez CI). Merge PR → `git pull origin main` v produkčním checkoutu →
`sudo bash deploy/update.sh` (build frontendu do `/var/www/greensie`, restart `greensie-backend`,
reload Caddy). Modul nepřidal Python závislosti ani DB migrace. Manažerské PPA parametry se
nastavují v adminu (jsou to data, ne kód – změna se projeví bez deploye).

---

## 7. Otevřené body / předpoklady k ověření (⚠️)
1. **Koeficienty výroby** (měrný výnos 1000, měsíční rozdělení, tabulka orientace) jsou
   ilustrativní – kalibrovat pro ČR, ideálně po krajích / z GPS (příp. PVGIS).
2. **Cena za kWp / O&M** – doplnit reálné hodnoty do manažerského nastavení.
3. **„Cena dodavatele"** – jen silová složka vs. vč. distribuce; a jak eskalovat.
4. **Prodej přebytku** – default vypnuto; cena se zadává u nabídky.
5. **Konstantní spotřeba** přes roky kontraktu (v1 předpoklad).
6. **Uložení profilu výroby** – zatím recompute (bez tabulky `profil_vyroby_fve`).
7. **Dopočet PPA ceny z marže** (`koeficient_zisku`) a **vícevariantní kombinace** (PPA +
   baterie) – neimplementováno.
8. **Fyzikální detaily** – solární vs. letní čas, degradace roku 0 (LID) – zjednodušeno.

---

## 8. Klíčové soubory
```
backend/app/nabidkovac/
  ppa_fve.py    – VÝPOČETNÍ JÁDRO (simulace výroby, spárování, ekonomika, ekonomický výběr velikosti, CAPEX)
  schemas.py    – PpaVstup
  routes.py     – API (…/ppa/vypocet, …/ppa/profil-souhrn) + doplnění defaultů a pojistky
frontend/src/
  components/PpaPanel.jsx           – OZ panel výpočtu + výsledek + srovnání velikostí
  components/GrafVyrobaSpotreba.jsx – SVG graf výroba vs. spotřeba
  pages/NabidkaDetail.jsx           – napojení panelu pro typ=ppa
  pages/NabidkovacKatalog.jsx       – admin PPA nastavení
  api.js                            – ppaVypocet, ppaProfilSouhrn
docs/METODIKA-ppa-fve.md            – metodika (zdroj vzorců)
```

---

## 9. Historie PR
| PR | Obsah | Stav |
|---|---|---|
| #12 | Metodika + první implementace (jádro, API, panel, graf, admin, auto-návrh dle samospotřeby) | merged + deploy |
| #13 | Návrh velikosti podle nejlepší ekonomiky (sweep NPV/návratnost, varianty) | merged + deploy |
| #14 | Pojistka proti nereálnému měrnému výnosu (100–2000 → default + upozornění) | otevřeno |
| (tento) | Předvyplnění vstupů panelu z posledního výpočtu (umožní přepočítávat) | v přípravě |
