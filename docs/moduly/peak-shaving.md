# Peak shaving – kompletní implementační souhrn (archiv)

Souhrn celé práce na peak shaving kalkulátoru v Nabídkovači appky Greensie.
Navazuje na `docs/METODIKA-peak-shaving.md` a promptové zadání
(`PROMPT-peak-shaving-2027.md`, `PROMPT-peak-shaving-aku-a-grafy.md`).

**Rozsah:** peak shaving jen pro **VN/VVN** (NN appka nenabízí). Naostro
**ČEZ, EG.D i PRE** (sazby 2026 všech tří RDS z CV ERÚ č. 13/2025 — audit
16. 7. 2026, bughunt PS-1). Všechny ceny **bez DPH**. Výpočet je čistě
deterministický (žádní AI agenti za běhu).

Stav: nasazeno na produkci (`https://app.greensie.cz`), poslední krok
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
  Od auditu SP-2 s **unique constraintem `(nabidka_id, cas)`** (na existující DB
  ho doplní `_lehka_migrace()` vč. deduplikace „poslední vyhrává“); zpracování
  profilu nahrazuje **celý** profil nabídky (dřív se dva soubory tiše sečetly)
  a duplicitní lokální časy z podzimního přechodu času slučuje na maximum.
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

### 4.1b Validace pokrytí roku — `app/nabidkovac/profil_pokryti.py` (bughunt SP-1)
Před výpočtem (peak shaving i PPA) se profil zkontroluje a případně ořízne:
- **delší než rok** (nebo >12 kombinací rok×měsíc) → automaticky se použije
  posledních **12 celých kalendářních měsíců** (upozornění ve výstupu),
- **nepoužitelný jako roční** → HTTP 422 s vysvětlením: rozsah < 350 dní,
  chybějící kalendářní měsíce, překrývající se okrajové měsíce, díry > 2 %
  intervalů (z rozsahu časů × granularita).

Bez toho půlroční profil tiše vyráběl „roční“ ekonomiku (poloviční úspory
proti plnému CAPEXu) a 13měsíční profil rozpouštěl lednovou výrobu do 62 dnů
(bughunt testy T2/T3).

### 4.2 Simulace baterie (kap. 4.2 + ztráty, bughunt PS-5)
Projezd profilu po 15min intervalech pro daný **strop `T`**, se ztrátami
(η_ch = η_dis = √RT; **RT default 0,88 AC-AC**, hodnota z katalogového sloupce
`technologie.ucinnost` má přednost — normalizace toleruje zadání v procentech):
- **odběr > T:** baterie dodá na AC straně `min(odběr − T, výkon, soc × η_dis / Δt)`;
  ze zásoby ubývá `dodávka/η_dis`. Když nestačí, strop `T` je **neudržitelný**.
- **odběr ≤ T:** baterie se dobíjí `min(T − odběr, výkon)` ze sítě, do zásoby se
  uloží `příkon × η_ch`; omezeno volnou kapacitou (jen z rezervy pod stropem).
- Počáteční nabití = **plná využitelná baterie** (zjednodušení v1).
- **Využitelná kapacita = jmenovitá × 0,85** (SOC okno 10–95 %). EOL derating
  (×0,8) a vlastní spotřeba PCS (~1 %) se zatím neaplikují (volitelné, fáze 2).

Funkce `energie_pri_stropu()` sčítá **nabito/vybito na AC straně** (grafy +
ocenění ztrát). **Cena ztrát cyklování** = `nabito × (1 − RT) × cena energie`
(`ps_cena_energie_kc_mwh`, default 3 000 Kč/MWh bez DPH, OZ může přepsat
u výpočtu) — snižuje roční úsporu 2026 i 2027 (v roce 2027 z měsíčních
simulací; srážení po měsících cykluje víc energie).

### 4.3 Minimální udržitelný strop a sjednávaná RK (kap. 4.3 + bughunt PS-6)
Binární hledání nejnižšího `T` v `[0, roční_maximum]`, při kterém simulace
projde celý rok bez překročení. Udržitelnost je monotónní v `T`. Výsledek =
**fyzický strop** (`strop_kw`), který baterie drží.

**Sjednávaná RK = strop × (1 + rezerva)** — strop je nalezen s dokonalou
znalostí jednoho historického roku; rezerva (default **5 %**, manažerský
parametr `ps_rezerva_rk_procenta`) kryje meziroční variabilitu profilu,
servis/výpadek baterie a o chlup jinou zimu. Ekonomika platí za sjednanou RK,
graf ukazuje strop (sražená maxima) i RK (čára rezervace).

### 4.4 Ekonomika 2026 s fair baseline (`stara_2026`, kap. 4.1–4.4 + bughunt PS-7)
```
pokuta_kc_kw           = 1,5 × cena_mesicni_rk_kc_kw_mesic          (bod 4.24 výměru, PS-2)
náklad_rezervace_před  = aktuální_RK × cena_rezervovana_kapacita_kc_kw_rok
náklad_překročení_před = Σ_měsíce max(0, měsíční_max − aktuální_RK) × pokuta_kc_kw
současný_náklad        = náklad_rezervace_před + náklad_překročení_před

# Fair baseline (PS-7): optimální KOMBINACE roční + měsíční RK bez baterie.
# Měsíční dokup (1× měsíční sazba) je vždy levnější než pokuta (1,5×) →
# v optimu se pokuty neplatí. C(R) je po částech lineární → grid-search
# přes unikátní měsíční maxima (cílová maxima × (1 + rezerva RK)).
C(R) = R × roční_sazba + Σ_m max(0, M_m − R) × měsíční_sazba
náklad_optimální_bez_baterie = min_R C(R)          nad historickými maximy × (1+rezerva)
náklad_baseline_bez_investice = min(současný_náklad, náklad_optimální_bez_baterie)
úspora_bez_investice = současný_náklad − náklad_baseline_bez_investice

# S baterií: tentýž optimalizátor nad maximy sraženými na strop baterie.
náklad_s_baterií = min_R C(R)                      nad min(M_m, strop) × (1+rezerva)
přínos_baterie   = náklad_baseline_bez_investice − náklad_s_baterií − ztráty_cyklování
roční_úspora_2026 = úspora_bez_investice + přínos_baterie
```

> **Oprava 27. 7. 2026 — baseline nesmí být dražší než „nedělat nic".** Optimalizace
> nese bezpečnostní rezervu nad naměřená maxima (PS-6), současný náklad ji nenese (je to
> naměřený fakt). U zákazníka, který dnes vědomě riskuje pokuty, proto umí optimalizovaná
> RK vyjít **dráž** než dnešní stav — a „úspora hned bez investice" pak vycházela záporně
> (u nabídky „hydra": RK 339 kW, maxima 310–372 kW → optimalizace 1 094 091 Kč vs. dnešní
> 1 079 431 Kč, tj. −14 660 Kč). Zároveň se přínos baterie počítal proti nafouknutému
> základu. Nově je baseline **levnější z {nechat RK jak je, přeoptimalizovat ji}**
> (`naklad_baseline_bez_investice`), takže úspora bez investice nikdy nevyjde záporná
> a přínos baterie se měří proti tomu, co zákazník reálně udělá, když nic nekoupí.
> Celková roční úspora se nemění, jen se přerozdělí mezi obě složky (u „hydry" přínos
> baterie z 98 371 na 83 711 Kč, tj. na celou roční úsporu). UI to vysvětlí poznámkou
> pod řádkem „Úspora hned bez investice".
**Návratnost baterie i výběr varianty se počítá z PŘÍNOSU BATERIE** (rozhodnuto
16. 7. 2026) — úspora z pouhého snížení RK je prodejní artefakt „audit RK
zdarma“ a klient ji získá bez investice. `nova_rezervovana_kapacita_kw` je
roční složka kombinace s baterií (+ případné měsíční dokupy, počty ve
výstupu). Použitá sazba pokuty se pro dohledatelnost ukládá do výstupu
(`sazby.cena_prekroceni_kc_kw_pouzita` + `pokuta_odvozena_z_mesicni_rk`);
do upozornění jde poznámka o pravidlech změn RK (snížení roční RK až po 12
měsících, měsíční RK do konce předchozího měsíce).

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

**Rezervovaný příkon (bughunt PS-4):** RP je hodnota **ze smlouvy o připojení**
(dlouhodobá, typicky ≥ RK; v lednu 2027 se převezme ze smlouvy) — není to roční
produkt jako RK. OZ ho může zadat (nepovinné pole); bez něj se použije současná
RK s upozorněním, že skutečný RP bývá vyšší.

> **Oprava 27. 7. 2026 — symetrie rezervy v baseline 2027.** Baseline (optimalizace RP bez
> baterie) se hledala nad naměřenými maximy **bez rezervy**, zatímco scénář s baterií nad
> maximy × (1 + rezerva) → baseline byla umělé levnější a přínos baterie systematicky
> podhodnocený (u „hydry" baseline RP 366 kW / 921 864 Kč místo 384 kW / 954 485 Kč, tj.
> přínos baterie o 32,6 tis. Kč/rok nižší). Nově se rezerva uplatní na **volbu RP** v obou
> scénářích stejně, náklad se ale počítá nad **skutečnými** maximy — složka „špička" se
> platí za naměřené `M`, ne za sjednanou hodnotu. Stejně jako u roku 2026 je baseline
> `min(nechat RP ze smlouvy, optimalizovat)`.

**Dva scénáře:**
- **Bez peak shavingu:** `RP` = zadaný rezervovaný příkon (fallback současná RK), `M` = naměřené měsíční maximum z profilu.
- **S peak shavingem:** `RP` = **stejný** (bez změny smlouvy — přínos baterie je jen na složce „maximální odebraný výkon“, poctivý default); s přepínačem „uvažovat snížení RP“ se RP **optimalizuje** (`optimalizuj_rp_2027` nad měsíčními maximy po baterii × faktor rezervy) — jednosměrné rozhodnutí, zpětné navýšení je zpoplatněno dle přílohy 2 vyhlášky č. 16/2016 Sb. `M` = **měsíční maximum po baterii sražené co nejhlouběji v každém měsíci** (kap. 4.6 „srážej co to dá“).

> **Oprava 27. 7. 2026 — symetrie optimalizace RP.** Scénář s baterií dosazoval RP natvrdo
> na celoroční strop + rezervu, zatímco baseline bez baterie se optimalizovala. Protože
> `přínos baterie = baseline − scénář s baterií`, byl přínos baterie **systematicky
> podhodnocený**. Nově se ve scénáři se snížením RP použije tentýž optimalizátor, takže RP
> smí klesnout i **pod nejvyšší měsíční maximum**, když je penalizace za překročení levnější
> než 12× kapacitní složka navíc. Snížit RP o 1 kW ušetří `12 × kapacitní sazba` za rok,
> překročení stojí `sazba_prekroceni` za každý měsíc, kdy nastane → na sazbách ČEZ VN se
> to v měsících T1 vyplatí, dokud je RP překročeno nejvýš 3× do roka (2 282 / 761), na T2
> nikdy (273 / 761). Výstup nese `rp_optimalizovan`, `mesicu_s_prekrocenim_rp` a
> `naklad_prekroceni_rp`; UI to ukazuje řádkem „… z toho vědomé překročení RP" a
> upozorněním. Bez zaškrtnutého snížení RP se chování nemění.
>
> Modelový dopad (profil s jednou zimní špičkou, BESS 300/1320, RP ze smlouvy 1600 kW):
> RP 1600 → 1082 kW, překročení v 1 měsíci za 227 tis. Kč, ale náklad s PS klesne
> o 371 tis. Kč/rok → přínos baterie 2027 z **−88 tis.** na **+283 tis. Kč/rok**,
> návratnost 2027 z 19,8 na 9,8 roku.

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

### 4.7 Výběr varianty: NPV na horizontu životnosti (kap. 4.5 + bughunt PS-8/PS-9)
- Pro každý produkt z katalogu (`typ = baterie`, dostupný, s výkonem i kapacitou) × počet kusů 1–5.
- Kus s celkovým výkonem/kapacitou/cenou = jednotka × počet.
- Vybere se nejlepší počet kusů (přidání kusu, které už nezlepší řadicí klíč, ukončí hledání).
- **Výběr vítěze řídí NPV na horizontu životnosti**, celý horizont na modelu
  2027 (rozhodnuto 27. 7. 2026 — co se dnes nabízí, se instaluje a spouští už
  v NTS, takže rok na tarifu 2026 nikdo neodžije; model 2026 zůstává jen jako
  informativní srovnání a jako fallback, když sazby 2027 nejsou v sazebníku):
  ```
  CF_rok = základ(model 2027, bez AKU) × (1 − degradace_úspor)^(rok−1) − O&M
  NPV    = −cena + Σ CF_k / (1 + diskont)^k          (NPV/IRR sdílené s PPA modulem)
  ```
  **Základ CF si volí OZ přepínačem v UI** (`ZAKLADY_NPV`, výstup nese obě sady
  v `npv_varianty`, takže přepnutí nic nepřepočítává):
  | Základ | Co počítá | Kdy dává smysl |
  |---|---|---|
  | `uspora` (výchozí) | celá roční úspora 2027 proti dnešnímu stavu | ekonomika projektu jako celku („dnešní faktura → faktura po instalaci"), včetně úspory ze souběžné úpravy RK/RP |
  | `prinos_baterie` | jen přínos baterie proti bezinvestiční baseline (PS-7) | přísnější pohled na samotnou investici — co přinese baterie nad rámec toho, co jde získat i bez ní |

  Rozdíl obou základů = „úspora hned bez investice". Na nabídce „hydra"
  (BESS 100/330 za 1,5 mil. Kč, RP 560 kW ze smlouvy): `uspora` → NPV +421 tis.
  Kč, IRR 14,1 %, reálná návratnost 5,1 roku; `prinos_baterie` → NPV −386 tis.
  Kč, IRR 1,7 %, reálná návratnost 9,1 roku. Volba mění i pořadí variant
  a odznak „nedoporučeno" — pořadí ze serveru odpovídá výchozímu základu,
  po přepnutí ho FE přeřadí podle téhož klíče (NPV, tie-break reálná návratnost).
  Defaulty (rozhodnuto 16. 7. 2026, manažerské nastavení): diskont **8 %**
  (`ps_diskontni_sazba`), horizont **10 let** (`ps_horizont_npv_roky`), O&M
  **2 % CAPEX/rok** (`ps_oam_procenta_capex_rok`), degradace úspor
  **1,5 %/rok** (`ps_degradace_uspor_procenta_rok`). Bez sazeb 2027 se
  konzervativně použije model 2026 pro celý horizont (příznak
  `npv_pouzit_model_2027`, u obou základů). Dokud platí modelový odhad NTS,
  je NPV modelové.
- Práh: pokud nejlepší varianta má **reálnou** návratnost > `max_navratnost_roky_peak_shaving`
  (výchozí 5 let), vrátí se stejně, ale označená `doporuceno = false`.

**Prostá návratnost = cena_baterie_celkem / přínos_daného_modelu** (`None`, když
přínos ≤ 0) — zobrazuje se doplňkově (PS-9). Dvě návratnosti:
| Model | Základ |
|---|---|
| **2026** | **přínos baterie** proti optimalizované RK (PS-7) |
| **2027** | úspora 2027 (jediný model — bez slevy AKU, viz 4.6 / bughunt PS-3) |

**Reálná návratnost (`payback_roky`)** = rok, kdy kumulované CF z NPV modelu poprvé
pokryje investici (lineární interpolace v rámci roku); `None` = v horizontu se nevrátí.
Počítá se pro oba základy zvlášť (`npv_varianty[…]["payback_roky"]`).

> **`None` se od 28. 7. 2026 v UI neukazuje jako „nevrátí se".** Frontend
> (`navratnostKZobrazeni` v `PeakShavingPanel.jsx`) číslo dopočítá **za horizont**: dělí
> nepokrytý zbytek investice cash flow dalších let, které dál klesá stejným tempem jako
> mezi posledními dvěma roky rozpisu, a zobrazí ho s vlnovkou (`~14,24 let`). Když je CF
> posledního roku nekladné (úspora nepokryje O&M) nebo klesající řada na zbytek nikdy
> nestačí, ukáže prostou návratnost s poznámkou „(prostá)". Backend se tím **nemění** — je to
> jen zobrazení a do NPV, prahu doporučení ani výběru varianty nevstupuje.

> **Oprava 27. 7. 2026 — doporučení nesmí viset na jednom roce.** Práh se poměřoval
> s prostou návratností **modelu 2026**, takže varianta s výbornou ekonomikou 2027
> a slabým rokem 2026 vyšla „nedoporučeno" — a naopak si OZ nemohl srovnat, proč se
> vítěz vybírá dle NPV, ale doporučuje dle roku 2026. Nově rozhoduje `payback_roky`
> z **téhož cash flow, ze kterého se počítá NPV** (celý horizont NTS 2027, včetně O&M
> a degradace úspor). Je to konzistentní s řádkem ◄ v tabulce „Ekonomika po letech".
>
> Pozor na rozdíl proti prosté návratnosti: u „hydry" (BESS 100/330 za 1,5 mil. Kč,
> RP 560 kW ze smlouvy) dává prostá návratnost 2027 **4,5 roku**, ale reálně
> **5,1 roku** — prostá návratnost ignoruje O&M (30 tis. Kč/rok = 9 % úspory)
> i degradaci úspor.

Starší uložené výsledky nesou pole `navratnost_2027_optim`/`navratnost_2027_konzerv`
a `*_bez_aku` — FE u nich zobrazuje konzervativní hodnoty.

### 4.7b Citlivost stropu (bughunt PS-10)
Levná bootstrap alternativa walk-forward validace (ta by chtěla ≥ 2 roky dat,
SP-1 profil ořezává na 12 měsíců): profil doporučené varianty se přeškáluje
**±5 %** a znovu se najde udržitelný strop. Výkon baterie se s rokem neškáluje
→ při špičkách +5 % roste strop typicky o **víc** než 5 %; výstup
(`citlivost_stropu`) hlásí, jestli horní scénář pokryje rezerva RK (PS-6).
FE to zobrazuje jako větu pod ekonomikou.

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
| `GET /nabidky/{id}/peak-shaving/prubeh?varianta=&rok=` | nabidkovac | rozepsaná 15min simulace pro nitkový graf (neukládá se) |

**Vstup výpočtu:** `{ distributor, napetova_hladina, rezervovana_kapacita_kw }`
(+ volitelně `cena_energie_kc_mwh`, `rezervovany_prikon_kw`, `uvazovat_snizeni_rp`).
**Výstup `popis_json`:** `vstup`, `sazby` (id + příznaky + použitá pokuta),
`max_navratnost_roky`, `doporucena` (varianta), `varianty` (top 3 — **každá
s vlastním `graf` a `citlivost_stropu`**, aby šel detail přepínat kliknutím ve
FE), `graf`/`citlivost_stropu` doporučené i na nejvyšší úrovni (zpětná
kompatibilita), `upozorneni`. Každá varianta nese `ekonomika_2026` (s rozpadem
úspory), `ekonomika_2027`, NPV/IRR a návratnosti.

**Průběh v čase (`/prubeh`)** – podklad pro nitkový graf. Do `popis_json` se
záměrně **neukládá** (35 040 hodnot × 4 řady na variantu a rok by nafouklo
JSONB nabídky); počítá se na vyžádání ze stejné fyziky jako ekonomika
(`peak_shaving._krok_simulace`), celý rok trvá ~0,1 s. Odpověď: `od`,
`interval_min`, `casy_min` (offsety v minutách – přežijí díry i přechod času),
`odber_kw`, `site_kw`, `baterie_kw` (+ vybíjí / − nabíjí), `soc_pct`,
`useky_stropu` (schodovitý strop – 2027 sráží po měsících), `referencni`
(čáry RK/RP), `souhrn` (nabito/vybito/ztráty) a `udalosti`. Cca 1,2 MB JSON,
gzipem (`GZipMiddleware` v `main.py`) ~250 kB.
**Model roku:** 2026 = jedna průběžná simulace na ročním stropu; 2027 =
`prubeh_po_mesicich`, tedy měsíc po měsíci s vlastním stropem a startem od plné
baterie – přesně jak počítá `ekonomika_2027` (jinak by graf na začátku měsíce
ukazoval překročení, které v ekonomice není).
**Události** (`peak_shaving.udalosti_prubehu`): roční a měsíční maxima/minima
odběru i odběru ze sítě, nejsilnější vybití/nabití, nejnižší SOC, nejdelší
souvislé vybíjení a překročení sjednané rezervace. Každá nese `index` do
profilu, takže FE umí na okamžik skočit (zoom).

---

## 6. Frontend (`frontend/src`)

- **`pages/NabidkovacKatalog.jsx`** (admin, právo `nabidkovac_katalog`): katalog technologií (samostatné sloupce Výkon/Kapacita, správa vlastních sloupců), výpočtová nastavení, **editor sazeb distributorů** (pole dle struktury – stara_2026 / T1,T2,penalizace,U1,U2 pro nova_2027; přepínače „čeká na sazby ERÚ“ a „modelový odhad“).
- **`components/PeakShavingPanel.jsx`** (OZ, v detailu nabídky typu peak_shaving): načtení profilu, zadání distributora/hladiny/rezervace (+ RP a snížení RP), spuštění výpočtu, výsledek – KPI s rozpadem úspory a NPV, ekonomika 2026 (fair baseline) a 2027 vedle sebe, návratnosti dle modelů, citlivost stropu, srovnání variant. **Kliknutím na řádek srovnání se celý detail (KPI, ekonomika, grafy, citlivost) překreslí pro danou variantu** (◄ = zobrazená; starší uložené výsledky mají grafy jen pro doporučenou).
- **`components/GrafOdberu.jsx`**: lehký **SVG graf bez knihovny** (projekt žádnou grafovou nemá). Sloupce bez/s baterií + čárkované čáry rezervace.
- **`components/GrafPrubehu.jsx`** (+ čistá vrstva `components/grafPrubehuData.js`): **nitkový graf průběhu** – celý rok po 15 minutách se zoomem až na jednotlivé čtvrthodiny. Bez grafové knihovny, ve dvou vrstvách: **`<canvas>`** kreslí datové řady a mřížku, **`<svg>`** nad ním popisky, referenční čáry, značky událostí a interaktivní plochy. (Původně bylo všechno v SVG, jenže jedno překreslení znamenalo předat prohlížeči ~150 kB textu cest k naparsování – zoom a posun znatelně zadrhávaly. Canvas + slévání vstupů do jednoho překreslení na snímek (`requestAnimationFrame`) to srovnalo; DOM na jedno vykreslení spadl ze 131 kB na 7 kB.) Barvy canvas čte z CSS tokenů přes `getComputedStyle` a znovu je načte při přepnutí tmavého režimu i kompenzace červeno-zelené vady. Celoroční řady si stáhne jednou a při každé změně přiblížení je slije do ~900 košů (min/max/průměr) – špička tak nezmizí zaokrouhlením a při plném přiblížení pásmo splyne s nitkou a jsou vidět přesné hodnoty. Tři pásy nad sebou (odběr/síť, výkon baterie ±, stav nabití) + přehledová lišta s výřezem; ovládání kolečkem, tažením (výběr), Shift+tažením (posun), dvojklikem (oddálení) a tlačítky Rok/Měsíc/Týden/Den. Vypsané události (roční/měsíční extrémy, chování baterie, překročení) se filtrují po kategoriích a klikem se na ně graf přiblíží.
- **`components/PeakShavingPanel.jsx`** vykresluje graf měsíčních maxim (dle přepínače roku) a pod ním na vyžádání průběh v čase (cache podle varianty a roku).
- **`api.js`**: helpery `sazby*`, `katalogSloupec*`, `peakShavingVypocet`, `profilZpracuj`, `peakShavingProfilSouhrn`, `peakShavingPrubeh`.

---

## 7. Nasazení

- **Bez CI.** Produkce běží z checkoutu `/home/dan/projects/greensie-app`.
- Postup: merge PR → `git pull origin main` v checkoutu → `sudo bash deploy/update.sh` (build frontendu do `/var/www/greensie`, restart `greensie-backend` + reload Caddy).
- Backend: systemd `greensie-backend`, uvicorn na `127.0.0.1:8000`. Frontend: Caddy z `/var/www/greensie`. Veřejně: `https://app.greensie.cz`.
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
