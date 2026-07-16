# Peak shaving – kompletní implementační souhrn (archiv)

Souhrn celé práce na peak shaving kalkulátoru v Nabídkovači appky Greensie.
Navazuje na `docs/METODIKA-peak-shaving.md` a promptové zadání
(`PROMPT-peak-shaving-2027.md`, `PROMPT-peak-shaving-aku-a-grafy.md`).

**Rozsah:** peak shaving jen pro **VN/VVN** (NN appka nenabízí). Naostro
**ČEZ, EG.D i PRE** (sazby 2026 všech tří RDS z CV ERÚ č. 13/2025 — audit
16. 7. 2026, bughunt PS-1). Všechny ceny **bez DPH**. Výpočet je čistě
deterministický (žádní AI agenti za běhu).

Stav: nasazeno na produkci (`https://167-235-254-188.sslip.io`), poslední krok
(PR #9 – návratnost dle modelů) se nasazuje ručně přes `deploy/update.sh`.

---

## 1. Přehled toku dat

1. OZ založí nabídku typu `peak_shaving`, nahraje XLS/CSV s 15minutovým profilem odběru.
2. **Zpracování profilu** naparsuje soubor do tabulky `spotreba_profil` (kW po 15 min).
3. OZ zadá **distributora**, **napěťovou hladinu** (VN/VVN) a **aktuální sjednanou rezervovanou kapacitu** (kW z faktury).
4. **Výpočet** projede katalog baterií, pro každou najde nejnižší udržitelnou rezervovanou kapacitu, spočítá ekonomiku 2026 i 2027, vybere variantu s nejkratší návratností.
5. Výsledek se uloží do `navrhovana_reseni.popis_json` a zobrazí v panelu nabídky (ekonomika obou let, návratnost dle modelů, grafy odběru).

---

## 2. Datový model (PostgreSQL)

Migrace běží při startu appky: `Base.metadata.create_all` + `_lehka_migrace()`
v `backend/app/main.py` (přidává sloupce do existujících tabulek přes
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Seed sazeb je idempotentní.

### 2.1 `sazby_distributoru` (nová) — `app/nabidkovac/models.py`
Nese dvě různé tarifní struktury (2026 vs. 2027) přes flexibilní JSONB.

| sloupec | typ | poznámka |
|---|---|---|
| `id` | int PK | |
| `distributor` | str | `cez` / `egd` / `pre` |
| `napetova_hladina` | str | `vn` / `vvn` (NN se nezavádí) |
| `struktura_tarifu` | str | `stara_2026` / `nova_2027` |
| `parametry` | JSONB (nullable) | ceny dle struktury; `NULL` = „čeká na sazby ERÚ“ |
| `platne_od`, `platne_do` | date | historie sazeb (dohledatelnost) |
| `je_modelovy_odhad` | bool | `true` u nova_2027 (nezávazný odhad) |
| `poznamka` | text | zdroj/ověření |
| `vytvoreno_at`, `aktualizovano_at`, `vytvoril_user_id` | | |

Unikátní klíč: `(distributor, napetova_hladina, struktura_tarifu, platne_od)`.

**Obsah `parametry`:**
- `stara_2026`: `cena_rezervovana_kapacita_kc_kw_rok`, `cena_mesicni_rk_kc_kw_mesic`
  (pokuta za překročení RK se odvozuje 1,5× — PS-2; starší klíč
  `cena_prekroceni_kc_kw` jen jako fallback ručních sazeb)
- `nova_2027`: `t1_kapacita_kc_kw_mesic`, `t1_spicka_kc_kw_mesic`, `t2_kapacita_kc_kw_mesic`, `t2_spicka_kc_kw_mesic`, `sazba_prekroceni_kc_kw_mesic`, `u1_ucinnost`, `u2_ucinnost` (prahy AKU: předběžné, v modelu se neaplikují — PS-3)

### 2.2 `technologie` (upravená)
- Pro `typ = baterie` musí být vyplněné **obě** pole: `vykon_kw` (nabíjecí = vybíjecí výkon) i `kapacita_kwh`. Validace v API.
- Nový sloupec `extra` (JSONB) = hodnoty vlastních (admin definovaných) sloupců katalogu.

### 2.3 `katalog_sloupce` (nová) — vlastní sloupce katalogu
`id`, `klic` (unikátní, odvozený z názvu bez diakritiky, neměnný), `nazev`,
`typ` (`text`/`cislo`), `poradi`. Hodnoty žijí v `technologie.extra[klic]`.

### 2.4 Použité existující tabulky
- `spotreba_profil` — 15min profil (`cas`, `hodnota_kw`, `zdroj_dokument_id`).
- `navrhovana_reseni` — výstup výpočtu v `popis_json` (`typ_reseni = peak_shaving`).
- `vypoctova_nastaveni.parametry.max_navratnost_roky_peak_shaving` — práh nedoporučené návratnosti (výchozí **5 let**).

---

## 3. Naseedovaná data (ČEZ + EG.D + PRE) — `app/nabidkovac/seed.py`

Vše bez DPH. Zdroj 2026: **finální CV ERÚ č. 13/2025 (ERV 17/2025), bod 4.18**
(audit 16. 7. 2026, bughunt PS-1 — původní seed měl ČEZ VN hodnotu roku 2025
a VVN chybělo). Seed je idempotentní; do už existujících řádků navíc:
- doplní chybějící klíče (`u1_ucinnost`, `u2_ucinnost`,
  `cena_mesicni_rk_kc_kw_mesic`) bez přepsání vyplněných hodnot,
- cíleně opraví přesně známé chybné hodnoty z dřívějších seedů
  (`_BACKFILL_OPRAVY`: ČEZ VN 2 847,72 → 3 030,78; ČEZ VVN `null` → 1 409,18)
  s dovětkem o zdroji do poznámky — ruční úpravy adminem nikdy nepřepíše.

### 3.1 `stara_2026` (ostrá čísla, platnost 2026-01-01 – 2026-12-31)
| DSO | Hladina | roční RK [Kč/kW/rok] | `cena_mesicni_rk_kc_kw_mesic` | pokuta za překročení RK (odvozená 1,5×) |
|---|---|---|---|---|
| ČEZ | VN | **3 030,78** (= 252,565 × 12) | 281,823 | 422,73 |
| ČEZ | VVN | **1 409,18** (= 117,432 × 12) | 131,036 | 196,55 |
| EG.D | VN | 2 766,61 (= 230,551 × 12) | 254,260 | 381,39 |
| EG.D | VVN | 1 329,91 (= 110,826 × 12) | 122,223 | 183,33 |
| PRE | VN | 3 253,12 (= 271,093 × 12) | 299,351 | 449,03 |
| PRE | VVN | 1 554,96 (= 129,580 × 12) | 143,087 | 214,63 |

> **Pozn. k jednotce:** výměr uvádí Kč/kW/**měsíc**; klíč `*_kc_kw_rok` je roční
> sazba (vzorec kap. 4.1 násobí jednou) → ukládá se ×12 z měsíční ceny za
> **roční** RK. `cena_mesicni_rk_kc_kw_mesic` je cena jiného produktu —
> **měsíční** RK.
> **Pozn. k pokutě (bughunt PS-2):** pokuta za překročení RK se v sazebníku
> **nedrží jako samostatné číslo** — výpočet ji odvozuje jako **1,5× měsíční
> cena měsíční RK** (bod 4.24 výměru, `peak_shaving.pokuta_prekroceni_rk_kc_kw`),
> aby se při roční aktualizaci sazeb nemohla rozjet. Původní seed hodnoty
> 1 108/521 Kč/kW/měs byly ceny za překročení rezervovaného **výkonu** (dodávka
> do sítě, bod 4.38) — backfill je z produkční DB cíleně odstraňuje. Starší klíč
> `cena_prekroceni_kc_kw` funguje už jen jako fallback ručně založených sazeb
> (výstup pak nese upozornění).

### 3.2 `nova_2027` (MODELOVÝ ODHAD, `je_modelovy_odhad = true`, platné od 2027-01-01)
Čísla z **informativního CV ERÚ k NTS (5/2026)** — nejsou finální, závazný
výměr pro 2027 vyjde ~11/2026 (pak se založí nový řádek s novým `platne_od`).

| DSO | Hladina | T1 kapacita | T1 špička | T2 kapacita | T2 špička | překročení RP | U1 | U2 |
|---|---|---|---|---|---|---|---|---|
| ČEZ | VN | 190,133 | 19,013 | 22,743 | 227,429 | 761 | 0,60 | 0,75 |
| ČEZ | VVN | 96,862 | 9,686 | 11,586 | 115,862 | 387 | 0,60 | 0,70 |
| EG.D | VN | 181,386 | 18,139 | 21,697 | 216,967 | 726 | 0,60 | 0,75 |
| EG.D | VVN | 87,770 | 8,777 | 10,499 | 104,987 | 351 | 0,60 | 0,70 |
| PRE | VN | 196,298 | 19,630 | 23,480 | 234,804 | 785 | 0,60 | 0,75 |
| PRE | VVN | 109,073 | 10,907 | 13,047 | 130,470 | 436 | 0,60 | 0,70 |

Vše Kč/kW/měsíc. Cena za překročení RP je v NTS pevná hodnota přímo z výměru
(už ne odvozovaná 4× T1). Prahy U1/U2 jsou předběžné (VKP ERÚ 10/2026).

---

## 4. Výpočtová logika — `app/nabidkovac/peak_shaving.py`

Konstanty: interval `0,25 h`, max. počet kusů baterie `5`, tolerance binárního
hledání `0,01 kW`, výchozí práh návratnosti `5 let`.

### 4.1 Import profilu — `app/nabidkovac/profil_import.py`
Parsuje **XLS** (list `export`, sloupec `Datum` ve formátu `DD.MM.RRRR HH:MM:SS`,
sloupec `Profil +A [kW]` = **činný odběr**), i **XLSX/CSV**. Hlavička se hledá
dynamicky. Výstup: seznam `(čas, kW)` → `spotreba_profil` (bulk insert,
idempotentně). Interval se odvodí z časových značek (fallback 0,25 h).
Knihovny: `xlrd`, `openpyxl` (v `requirements.txt`).

### 4.2 Simulace baterie (kap. 4.2)
Projezd profilu po 15min intervalech pro daný **strop `T`**:
- **odběr > T:** baterie dodá `min(odběr − T, výkon, dostupná_energie)`. Když nestačí, strop `T` je **neudržitelný**.
- **odběr ≤ T:** baterie se dobíjí `min(T − odběr, výkon)`, omezeno volnou kapacitou (jen z rezervy pod stropem).
- Počáteční nabití = **plná baterie** (zjednodušení v1).
- Kapacita/účinnost **1:1 bez ztrát**, bez DoD limitu (v1).

Funkce `energie_pri_stropu()` navíc sčítá **nabito/vybito** (pro Koeficient AKU a grafy) – nemění fyziku simulace.

### 4.3 Minimální udržitelná rezervovaná kapacita (kap. 4.3)
Binární hledání nejnižšího `T` v `[0, roční_maximum]`, při kterém simulace
projde celý rok bez překročení. Udržitelnost je monotónní v `T`. Výsledek =
**navrhovaná nová rezervovaná kapacita**.

### 4.4 Ekonomika 2026 (`stara_2026`, kap. 4.1–4.4)
```
pokuta_kc_kw           = 1,5 × cena_mesicni_rk_kc_kw_mesic          (bod 4.24 výměru, PS-2)
náklad_rezervace_před  = aktuální_RP × cena_rezervovana_kapacita_kc_kw_rok
náklad_překročení_před = Σ_měsíce max(0, měsíční_max − aktuální_RP) × pokuta_kc_kw
současný_náklad        = náklad_rezervace_před + náklad_překročení_před

nový_náklad            = T × cena_rezervovana_kapacita_kc_kw_rok    (po baterii je překročení 0)
roční_úspora_2026      = současný_náklad − nový_náklad
```
Použitá sazba pokuty se pro dohledatelnost ukládá do výstupu
(`sazby.cena_prekroceni_kc_kw_pouzita` + `pokuta_odvozena_z_mesicni_rk`).

### 4.5 Ekonomika 2027 (`nova_2027`, kap. 4.6 + 4.8)
Dvousložkový tarif, každý měsíc se ex post použije **levnější** z T1/T2.
Zákazník tarif nevybírá, určuje ho distributor podle skutečné spotřeby.

**Měsíční náklad:**
```
měsíční_náklad = min(RP × T1_kapacita + M × T1_špička,
                     RP × T2_kapacita + M × T2_špička)
               + max(0, M − RP) × sazba_prekroceni
roční_náklad_2027 = Σ přes 12 měsíců
```
kde `M` = naměřené měsíční maximum, `RP` = rezervovaný příkon.

**Dva scénáře (RP je vždy JEDNA roční hodnota – rezervaci na síti nelze měnit po měsících):**
- **Bez peak shavingu:** `RP` = aktuální sjednaná, `M` = naměřené měsíční maximum z profilu.
- **S peak shavingem:** `RP` = nová (min. udržitelný strop pro celý rok), `M` = **měsíční maximum po baterii sražené co nejhlouběji v každém měsíci** (kap. 4.6 „srážej co to dá“ – per měsíc se hledá nejnižší udržitelný strop; mění se jen `M`, ne `RP`).

> **Klíčová oprava během vývoje:** původně (dle promptu) baterie 2027 srážela jen na jeden roční strop → v letních měsících nedělala nic a úspora vycházela nízká. Přepnuto na per-měsíční srážení `M` dle metodiky 4.6 → úspora 2027 výrazně vyšší. Rezervovaná kapacita zůstává jedna roční hodnota.

### 4.6 Koeficient AKU — ❌ neaplikuje se (vyřešeno auditem, bughunt PS-3)
ERÚ (část 24 informativního CV) definuje koeficient AKU z podílu **zpětně
dodané elektřiny do soustavy / odebrané elektřiny ze soustavy za celé předávací
místo a zúčtovací období** (K = 0 pod U1, lineárně do 1 mezi U1–U2; sleva
násobí celý čtvrthodinový diagram odebraného výkonu a snižuje jen platbu za
maximální odebraný výkon). **Peak-shavingová baterie uvnitř odběru závodu nic
zpětně nedodává → podíl ≈ 0 → K = 0 → žádná sleva.** Benefit cílí na
samostatná úložiště a přečerpávací elektrárny.

Dřívější optimistická větev (účinnost = vybito/nabito baterie ≈ 1 → plná
sleva) byla **strukturálně mylná a byla odstraněna** — jediný model 2027 je
dřívější „konzervativní bez AKU“. Prahy `u1_ucinnost`/`u2_ucinnost` v sazebníku
zůstávají (předběžné hodnoty, VKP ERÚ 10/2026) pro případné budoucí použití
u míst s velkým exportem (kombinace PPA + baterie, fáze 2).

### 4.7 Výběr varianty a návratnost (kap. 4.5)
- Pro každý produkt z katalogu (`typ = baterie`, dostupný, s výkonem i kapacitou) × počet kusů 1–5.
- Kus s celkovým výkonem/kapacitou/cenou = jednotka × počet.
- Vybere se nejlepší počet kusů (přidání kusu, které už nezlepší návratnost, ukončí hledání).
- **Výběr vítěze řídí návratnost dle modelu 2026** (potvrzený tarif).
- Práh: pokud nejlepší varianta má návratnost > `max_navratnost_roky_peak_shaving` (výchozí 5 let), vrátí se stejně, ale označená `doporuceno = false`.

**Návratnost = cena_baterie_celkem / roční_úspora_daného_modelu** (`None`, když úspora ≤ 0). Zobrazují se **dvě návratnosti**:
| Model | Základ (roční úspora) |
|---|---|
| **2026** | úspora 2026 (řídí výběr varianty) |
| **2027** | úspora 2027 (jediný model — bez slevy AKU, viz 4.6 / bughunt PS-3) |

Starší uložené výsledky nesou pole `navratnost_2027_optim`/`navratnost_2027_konzerv`
a `*_bez_aku` — FE u nich zobrazuje konzervativní hodnoty.

### 4.8 Data pro grafy (`graf_maxima`)
Měsíční maxima odběru: `bez_baterie` (naměřené), `s_baterii_2026` (= min(raw, roční strop)),
`s_baterii_2027` (per-měsíční sražené maximum) + čáry `rp_soucasna` a `rp_nova`.

---

## 5. API (prefix `/nabidkovac`, přes Caddy `/api`) — `app/nabidkovac/routes.py`

| Metoda / cesta | Právo | Popis |
|---|---|---|
| `GET /sazby` | nabidkovac | přehled sazeb |
| `POST/PUT/DELETE /sazby[/{id}]` | nabidkovac_katalog | správa sazeb (vedení/admin) |
| `GET /katalog-sloupce` | nabidkovac | vlastní sloupce katalogu |
| `POST/PUT/DELETE /katalog-sloupce[/{id}]` | nabidkovac_katalog | správa sloupců |
| `GET/POST/PUT/DELETE /technologie[/{id}]` | katalog vidí všichni, edituje katalog | + validace baterií, `extra` |
| `POST /dokumenty/{id}/zpracuj-profil` | nabidkovac | naparsuje XLS/CSV → `spotreba_profil` |
| `GET /nabidky/{id}/peak-shaving/profil-souhrn` | nabidkovac | počet/rozsah/špička profilu |
| `POST /nabidky/{id}/peak-shaving/vypocet` | nabidkovac | spustí výpočet, uloží do `navrhovana_reseni` |

**Vstup výpočtu:** `{ distributor, napetova_hladina, rezervovana_kapacita_kw }`.
**Výstup `popis_json`:** `vstup`, `sazby` (id + příznaky), `max_navratnost_roky`,
`doporucena` (varianta), `varianty` (top 3), `graf`, `upozorneni`. Každá varianta
nese `ekonomika_2026`, `ekonomika_2027` (vč. AKU polí) a tři návratnosti.

---

## 6. Frontend (`frontend/src`)

- **`pages/NabidkovacKatalog.jsx`** (admin, právo `nabidkovac_katalog`): katalog technologií (samostatné sloupce Výkon/Kapacita, správa vlastních sloupců), výpočtová nastavení, **editor sazeb distributorů** (pole dle struktury – stara_2026 / T1,T2,penalizace,U1,U2 pro nova_2027; přepínače „čeká na sazby ERÚ“ a „modelový odhad“).
- **`components/PeakShavingPanel.jsx`** (OZ, v detailu nabídky typu peak_shaving): načtení profilu, zadání distributora/hladiny/rezervace, spuštění výpočtu, výsledek – ekonomika 2026 a 2027 vedle sebe (popisky „Roční náklad bez / s peak shavingem“), sleva AKU + upozornění, **tabulka tří návratností**, srovnání variant.
- **`components/GrafOdberu.jsx`**: lehký **SVG graf bez knihovny** (projekt žádnou grafovou nemá; deploy nedělá `npm install`). Sloupce bez/s baterií + čárkované čáry rezervace.
- **`components/PeakShavingPanel.jsx`** vykresluje dva grafy (2026, 2027).
- **`api.js`**: helpery `sazby*`, `katalogSloupec*`, `peakShavingVypocet`, `profilZpracuj`, `peakShavingProfilSouhrn`.

---

## 7. Nasazení

- **Bez CI.** Produkce běží z checkoutu `/home/dan/projects/greensie-app`.
- Postup: merge PR → `git pull origin main` v checkoutu → `sudo bash deploy/update.sh` (build frontendu do `/var/www/greensie`, restart `greensie-backend` + reload Caddy).
- Backend: systemd `greensie-backend`, uvicorn na `127.0.0.1:8000`. Frontend: Caddy z `/var/www/greensie`. Veřejně: `https://167-235-254-188.sslip.io`.
- **`update.sh` nedělá `pip install`** → `xlrd`/`openpyxl` byly doinstalované ručně do venv (a jsou v `requirements.txt` pro čistý build).
- DB migrace + seed běží při startu backendu (idempotentně).

---

## 8. Otevřené body / předpoklady k ověření

1. ~~**Definice účinnosti pro Koeficient AKU**~~ → vyřešeno (bughunt PS-3, 16. 7. 2026): dle ERÚ se počítá z toku na předávacím místě; pro BTM baterii bez exportu K = 0 → sleva odstraněna z modelu. Znovu vyhodnotit po VKP ERÚ (10/2026) pro místa s velkým exportem.
2. **Sazby 2027** – modelový odhad, ne finální ceny ERÚ (rozhodnutí ~11/2026). Označeno `je_modelovy_odhad`.
3. ~~**EG.D a PRE** – sazby nedoplněny~~ → doplněno seedem z CV 13/2025 (bughunt PS-1, 16. 7. 2026).
4. ~~**ČEZ VVN rezervovaná kapacita 2026** – nedohledáno~~ → doplněno (117,432 Kč/kW/měs, bughunt PS-1).
5. **Jednotka rezervace 2026** – uložena ročně (252,565 × 12 = 3 030,78 pro ČEZ VN); ověřit očekávanou jednotku v admin poli.
6. **Počáteční nabití baterie** v simulaci = plná (zjednodušení v1).
7. **15min detail měsíce v grafu** – ponecháno jako „later“.
8. Od 2028 podmínka slevy: negarantovaný (flexibilní) rezervovaný příkon – zatím mimo scope.

---

## 9. Historie PR

| PR | Obsah | Stav |
|---|---|---|
| #5 | Tabulka `sazby_distributoru`, výpočetní jádro 2026, výstup, admin FE sazeb, rozdělení výkon/kapacita + vlastní sloupce katalogu | merged + deploy |
| #6 | OZ výpočet v nabídce + import XLS profilu (`spotreba_profil`) | merged + deploy |
| #7 | Rok 2027 – dvousložková struktura T1/T2, `je_modelovy_odhad`, seed ČEZ 2027 | merged + deploy |
| #8 | 2027 srážení per měsíc (metodika 4.6) + přejmenování popisků; Koeficient AKU; grafy odběru | merged + deploy |
| #9 | Návratnost podle modelů (2026 / 2027 optimistický / konzervativní) | merged, deploy ručně |

---

## 10. Klíčové soubory

```
backend/app/nabidkovac/
  models.py         – tabulky (sazby_distributoru, katalog_sloupce, technologie.extra …)
  schemas.py        – pydantic schémata
  routes.py         – API (sazby, sloupce, profil, výpočet)
  peak_shaving.py   – VÝPOČETNÍ JÁDRO (simulace, ekonomika 2026/2027, AKU, návratnosti, graf)
  profil_import.py  – parser XLS/XLSX/CSV profilu
  seed.py           – seed sazeb ČEZ (2026 + 2027) + backfill U1/U2
backend/app/main.py – create_all + _lehka_migrace + seed při startu
frontend/src/
  pages/NabidkovacKatalog.jsx      – admin (katalog, nastavení, sazby)
  components/PeakShavingPanel.jsx  – OZ panel výpočtu + výsledek
  components/GrafOdberu.jsx        – SVG graf
  api.js                           – API helpery
```
