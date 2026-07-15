# Metodika výpočtu – PPA pro FVE (v1, návrh)

Navazuje na `docs/SPEC-nabidkovac.md` a na hotový modul peak shaving
(`docs/METODIKA-peak-shaving.md`, `docs/moduly/peak-shaving.md`). Tohle je čistě
**metodika/vzorce**, ne kód – slouží jako podklad pro další Claude Code prompt, až ji
společně potvrdíme (stejně jako `METODIKA-peak-shaving.md` vznikla dřív než
`peak_shaving.py`). Obsahuje předpoklady, které jsem musel udělat a **potřebují tvoje
potvrzení/opravu** (označeno ⚠️).

Konvence přebírám 1:1 z peak shavingu: české názvy sloupců, `Numeric` na peníze/výkony,
JSONB na flexibilní parametry, idempotentní seed, verzovaná `vypoctova_nastaveni`,
deterministický výpočet bez AI agentů za běhu, ceny **bez DPH**, práva `nabidkovac`
(OZ používá) / `nabidkovac_katalog` (vedení/admin edituje katalog a nastavení), SVG grafy
bez knihovny.

---

## 1. Princip

Greensie (nebo jiný investor) **postaví a vlastní** FVE na střeše/pozemku zákazníka.
Zákazník **nic neinvestuje** – po sjednanou dobu kontraktu (typicky 10–20 let) jen odebírá
elektřinu vyrobenou z FVE za smluvenou **PPA cenu** (Kč/MWh), která je nižší než jeho
současná tržní cena od dodavatele. PPA cena je **indexovaná** – každý rok kontraktu se
navyšuje o dohodnutý index (kap. 4.4).

Nástroj počítá **dvě ekonomiky nad stejnou fyzikou**:

- **(A) Klientovi** se ukazuje jen srovnání „co platí dnes" (celá spotřeba od dodavatele)
  vs. „co by platil s PPA" (samospotřebovaná FVE energie za PPA cenu + zbytek od
  dodavatele). Výstup pro klienta = roční a kumulativní **úspora**.
- **(B) Investorovi (Greensie)** se počítá **návratnost investice** do FVE: CAPEX vs. roční
  výnos z PPA plateb klienta (payback, IRR, NPV). Tohle je interní pohled, který rozhoduje,
  jestli a za jakých podmínek nabídku vůbec dává smysl postavit.

Klíčová odlišnost od peak shavingu: **výroba FVE se nenahrává, appka si ji sama simuluje**
z instalovaného výkonu (kWp), lokality a orientace panelů (kap. 4.1) – obdoba toho, jak dnes
OZ nahrává profil spotřeby. Spotřeba se pořád nahrává (15min profil, existující tabulka
`spotreba_profil`, sloupec `hodnota_kwh`).

**Rozsah v1:** jedna FVE na jedno odběrné místo, jeden roční profil spotřeby, kontrakt s
konstantní roční spotřebou klienta (⚠️ předpoklad, kap. 8). Bez baterie (kombinace PPA +
baterie je samostatné budoucí téma – řešení se stejně ukládají vedle sebe v
`navrhovana_reseni`).

---

## 2. Vstupní data

| Vstup | Zdroj | Poznámka |
|---|---|---|
| 15minutový profil spotřeby (kWh) za min. 1 rok | CSV/XLS nahrané OZ | stejný import jako peak shaving, ale ukládá se **energie kWh** (ne kW) do `spotreba_profil.hodnota_kwh` – viz kap. 3.4 |
| Instalovaný výkon FVE (kWp) | OZ zadá (nebo appka zkouší víc velikostí – kap. 4.7) | vstup do simulace výroby |
| Lokalita (GPS lat/lng nebo kraj) | `nabidky.zakaznik_gps_lat/lng` (už existuje) nebo výběr | určuje měrný výnos + geometrii slunce |
| Sklon panelů (°) a azimut (°, 0 = jih) | OZ zadá | korekce výnosu proti optimu (kap. 4.1) |
| PPA cena rok 1 (Kč/MWh) | OZ zadá (nabízená cena) | eskalovaná indexem (kap. 4.4) |
| Index eskalace PPA (%/rok) | OZ zadá, default z `vypoctova_nastaveni` | pevné % nebo „inflace" (⚠️ kap. 8) |
| Současná cena dodavatele (Kč/MWh) | z faktury (`extrahovana_data_faktury.cena_kwh`) nebo ručně | referenční cena „bez PPA" |
| Index eskalace ceny dodavatele (%/rok) | default z `vypoctova_nastaveni` | ⚠️ předpoklad, kap. 8 |
| Délka kontraktu (roky) | OZ zadá v rozsahu `min/max_delka_kontraktu_roky` | už existuje ve `vypoctova_nastaveni` |
| Režim nákladů na FVE (`cena_kwp` / `komponenty`) | OZ přepne ve výpočtovém pohledu | cena/kWp (zjednodušeně) vs. skutečné náklady po komponentech z katalogu (kap. 3.4) |
| Cena za kWp (Kč/kWp) | **manažerské nastavení** (`vypoctova_nastaveni`) | sazba pro zjednodušený režim (kap. 3.4/4.5) |
| Degradace panelů (%/rok) | default z `vypoctova_nastaveni` (~0,5 %) | kap. 4.2 |
| Účtovat přebytek (prodej do sítě) – zapnout/vypnout | OZ přepne, default z `vypoctova_nastaveni` | volitelné; když vyp., přebytek = 0 Kč (kap. 4.3, 4.5) |
| Cena přebytku (Kč/MWh) | **OZ zadá u každé nabídky** | liší se dle lokality a smlouvy → per-výpočet, ne globální default |
| Max. rezervovaný výkon dodávky do sítě (kW) | OZ zadá (ze smlouvy o připojení) | strop přetoku do DS; **nemusí = výkon FVE**, nadbytek se ořízne (kap. 4.3) |

---

## 3. Doplnění datového modelu

Do `models.py` (a `SPEC-nabidkovac.md`) přibude analogicky k peak shavingu. Migrace běží při
startu (`create_all` + `_lehka_migrace()`), seed idempotentní.

### 3.1 Nová tabulka `profil_vyroby_fve`

Mirror `spotreba_profil`, ale drží **simulovaný** profil výroby (rok 1, před degradací).
Držíme ho uložený kvůli reprodukovatelnosti a grafům; degradace za další roky se dopočítává
analyticky (kap. 4.2), takže neukládáme profil pro každý rok kontraktu.

- `id`
- `nabidka_id` (FK, `ondelete="CASCADE"`)
- `cas` (timestamp, zarovnaný na kalendářní mřížku profilu spotřeby – kap. 4.3)
- `hodnota_kwh` (Numeric – vyrobená energie za interval)
- `parametry_simulace_json` (JSONB – kWp, sklon, azimut, měrný výnos, verze koeficientů; ať
  je dohledatelné, z čeho profil vznikl)

⚠️ **Předpoklad k potvrzení:** stejná úvaha o objemu jako u `spotreba_profil` (SPEC 4.5) –
~35 040 řádků/rok. Alternativa: profil neukládat a jen deterministicky přepočítat z
parametrů při každém dotazu (uložit jen 12 měsíčních agregátů do `popis_json`). Navrhuji
**uložit** (konzistence s peak shavingem, snadné grafy), ale je to na potvrzení.

### 3.2 Rozšíření `vypoctova_nastaveni.parametry` (JSONB) – ekonomické defaulty PPA

Bez migrace (stejný princip jako `max_navratnost_roky_peak_shaving`). Editovatelné jen
vedením/adminem, verzovaně. Navrhované klíče (vše výchozí hodnoty, OZ je u konkrétní nabídky
může přepsat):

- `ppa_index_ceny_rocni` (default např. 0,03 = 3 %/rok)
- `ppa_index_dodavatel_rocni` (default např. 0,03) ⚠️ kap. 8
- `ppa_degradace_rocni` (default 0,005 = 0,5 %/rok)
- `ppa_cena_fve_kc_kwp` (**cena za kWp** pro zjednodušený režim CAPEX – kap. 3.4/4.5)
- `ppa_ostatni_naklady_kc_kwp` (BOS – montáž/konstrukce/kabeláž pro komponentový režim, Kč/kWp) ⚠️ kap. 3.4
- `ppa_oam_kc_kwp_rok` (provozní náklady, default např. 0 nebo ~200 Kč/kWp/rok) ⚠️ kap. 8
- `ppa_diskontni_sazba` (pro NPV/IRR, default např. 0,05)
- `ppa_prebytek_uctovat` (bool, default `false` – **potvrzeno vypnuto**) – zapnout prodej přebytku do sítě (kap. 4.3, 4.5)
- `ppa_index_prebytek_rocni` (eskalace ceny přebytku %/rok, default 0 = drží se plochá) ⚠️ kap. 8

Per-nabídku (ne globální default – závisí na konkrétní lokalitě / smlouvě o připojení):
- `prebytek_cena_kc_mwh` – výkupní/tržní cena za exportovaný přetok. **OZ zadá u každé
  nabídky** (liší se dle lokality a smlouvy), proto se nedrží jako globální default (kap. 4.5).
- `rezervovany_vykon_dodavky_kw` – strop přetoku do distribuční soustavy (kap. 4.3). `null` /
  0 = neomezeno (limituje jen výkon FVE).
- `koeficient_zisku`, `min_delka_kontraktu_roky`, `max_delka_kontraktu_roky` – **už existují**
  jako sloupce `vypoctova_nastaveni` (kap. 4.6)

### 3.3 Koeficienty simulace výroby (kap. 4.1)

Fyzikální koeficienty (měsíční rozdělení výnosu, měrný výnos ČR, korekce orientace) navrhuji
držet jako **konstanty v kódu** (analogicky `VYCHOZI_INTERVAL_H` apod. v `peak_shaving.py`) s
možností přepsat je přes `vypoctova_nastaveni.parametry` – nejsou to komerční sazby, které by
se měnily po distributorech. Nezavádím kvůli nim samostatnou tabulku (na rozdíl od
`sazby_distributoru`, které se liší per distributor a mění se ročně).

### 3.4 Náklady na FVE – dva režimy řízené přepínačem

CAPEX (náklad na postavení FVE) se počítá jedním ze dvou režimů. **Přepínač `rezim_capex`
volí OZ ve výpočtovém pohledu** (zadání nabídky), sazby k němu jsou v **manažerském nastavení**
(`vypoctova_nastaveni`, edituje jen vedení/admin – právo `nabidkovac_katalog`):

- **`cena_kwp` (zjednodušeně, default):**
  ```
  CAPEX = navržené_kWp × ppa_cena_fve_kc_kwp
  ```
  `ppa_cena_fve_kc_kwp` = **cena za kWp z manažerského nastavení**. Rychlé, nezávisí na
  úplnosti katalogu.

- **`komponenty` (skutečné náklady):** appka navrhne elektrárnu **po komponentech z katalogu
  `technologie`** (analogie výběru baterie u peak shavingu) a CAPEX sečte z jejich cen:
  ```
  pocet_panelu   = ceil(navržené_kWp / panel.vykon_kw)          # panel typu fve_panel
  CAPEX_panely   = pocet_panelu × panel.cena_kc
  CAPEX_invertory= Σ vybraných invertorů (typ = invertor) pokrývajících kWp   # dle DC/AC poměru
  CAPEX_ostatni  = navržené_kWp × ppa_ostatni_naklady_kc_kwp    # konstrukce/kabeláž/montáž (BOS)
  CAPEX          = CAPEX_panely + CAPEX_invertory + CAPEX_ostatni
  ```
  Výběr komponent: který panel/invertor z katalogu použít (nejlevnější dostupný daného typu,
  nebo výběr OZ) potvrdíme při implementaci. „Ostatní náklady" (montáž, konstrukce, kabeláž =
  BOS) katalog typicky nemá po položkách → doplňkový přepočet `ppa_ostatni_naklady_kc_kwp`
  z manažerského nastavení; ⚠️ jestli je součástí skutečných nákladů, nebo se do katalogu
  přidá jako položka `typ = jina`, je otevřený bod (kap. 8).

Výstup nese `rezim_capex` a rozpad CAPEX, ať je v nabídce vidět, jak se k číslu došlo.
Katalog už `typ = fve_panel` i `typ = invertor` má (`vykon_kw`, `cena_kc`); komponentový režim
závisí na tom, že jsou v katalogu naplněné.

### 3.5 Výstup `navrhovana_reseni`

Beze změny schématu – `typ_reseni = ppa`, výsledek do `popis_json` (kap. 5).

---

## 4. Algoritmus

Výpočetní jádro navrhuji jako nový modul `ppa_fve.py` (obdoba `peak_shaving.py`): bez
závislosti na DB/FastAPI, pracuje jen se seznamy 15min hodnot a čísly z nastavení. Napojení
řeší `routes.py`.

### 4.1 Simulace výroby FVE (roční profil, rok 1)

Cíl: z (kWp, lokalita, sklon, azimut) vyrobit 15min profil výroby zarovnaný na stejnou
kalendářní mřížku jako profil spotřeby.

**Krok 1 – roční výnos (kWh/rok):**
```
E_rok = kWp × merny_vynos_kwh_kwp(lokalita) × k_orient(azimut, sklon)
```
- `merny_vynos_kwh_kwp` – referenční měrný výnos pro ČR, jižní orientace, optimální sklon
  ~35°. Navrhuji **default 1000 kWh/kWp/rok** (⚠️ reálné rozpětí ČR ~950 severozápad – ~1080
  jižní Morava; v1 jedna editovatelná konstanta, zpřesnění podle GPS/kraje = otevřený bod).
- `k_orient` ∈ (0;1], = 1,0 pro jih + sklon 30–40°. Korekční tabulka (⚠️ ilustrativní hodnoty
  k kalibraci proti PVGIS/standardním tabulkám):

  | Azimut \ Sklon | 0° (rovina) | 15° | 30–40° | 60° |
  |---|---|---|---|---|
  | Jih (0°) | 0,88 | 0,96 | **1,00** | 0,91 |
  | JV/JZ (±45°) | 0,88 | 0,94 | 0,96 | 0,86 |
  | V/Z (±90°) | 0,88 | 0,88 | 0,84 | 0,72 |
  | Sever (180°) | 0,88 | 0,80 | 0,66 | 0,50 |

  Mezilehlé hodnoty bilineární interpolací. (Pro rovinu je azimut irelevantní → jedna
  hodnota.)

**Krok 2 – rozdělení do měsíců** dle typického profilu ČR (⚠️ ilustrativní, kalibrovat):

| měs | led | úno | bře | dub | kvě | čvn | čvc | srp | zář | říj | lis | pro |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| kWh/kWp (z 1000) | 26 | 42 | 83 | 120 | 135 | 132 | 138 | 120 | 90 | 58 | 30 | 26 |

Měsíční podíl = hodnota / 1000. `E_měsíc = E_rok × podíl_měsíc`.

**Krok 3 – rozdělení dne (denní křivka, clear-sky):** pro daný den v roce `n` a zeměpisnou
šířku `φ`:
```
δ   = 23,45° × sin(360° × (284 + n) / 365)          # deklinace Slunce
ω_s = arccos(−tan(φ) × tan(δ))                       # hodinový úhel východu/západu (°)
t_východ = 12 − ω_s/15 ;  t_západ = 12 + ω_s/15      # solární čas (h)
g(t) = max(0, sin(π × (t − t_východ) / (t_západ − t_východ)))   # tvar produkce
```
Energie intervalu `i` (solární čas `t_i`) daného dne:
```
V_i = E_den × g(t_i) / Σ_j g(t_j)      # E_den = E_měsíc / počet_dní_v_měsíci
```
Tím vznikne 15min (nebo hodinový) profil, jehož roční součet = `E_rok`.

⚠️ **Zjednodušení v1:** clear-sky zvonovina bez denní proměnlivosti počasí – reálná výroba je
„zubatější", ale pro odhad **samospotřeby** (kap. 4.3) na měsíční/roční úrovni to stačí; na
15min špičky se to hodí hůř. Solární vs. hodinový čas (posun ~+1 h, letní čas) je detail
k ošetření při implementaci (⚠️ kap. 8).

**Rozlišení:** navrhuji počítat **hodinově** (8 760 hodnot – levné, PVGIS-kompatibilní) a pro
párování s 15min spotřebou hodnotu hodiny rovnoměrně rozdělit na 4 čtvrthodiny (`V_15 =
V_hod/4`). Alternativa 15min přímo je taky OK; volbu potvrdíme.

**Zdroj dat – rozhodnutí:** v1 **interní model výše** (deterministický, nulové závislosti,
v duchu appky). PVGIS API (hodinová data typického roku z GPS + orientace) jako přesnější v2
= otevřený bod (kap. 8) – pozor, běh za runtime na externí službě je proti dosavadní filosofii
appky.

### 4.2 Degradace panelů po letech kontraktu

Výroba v roce `t` (t = 1..N):
```
faktor_degradace(t) = (1 − d)^(t−1)          # d = ppa_degradace_rocni, default 0,005
V_i,t = V_i,1 × faktor_degradace(t)
```
První rok bez degradace. Profil rok 1 se ukládá, další roky = jen přeškálování (žádné nové
uložení). ⚠️ Zvážit „rok 0" degradaci (LID, ~1–2 % hned první rok) – v1 zanedbáno, k potvrzení.

### 4.3 Spárování výroby a spotřeby (samospotřeba, přebytek, dokup)

Oba profily zarovnané na stejnou kalendářní mřížku (výroba se generuje pro `cas` každého
intervalu spotřeby – kap. 4.1). Pořadí toku energie v každém intervalu `i`: **nejdřív
samospotřeba** (lokální, neteče do sítě), **pak přetok do sítě** až do rezervovaného výkonu
dodávky, **zbytek se ořízne** (fyzicky neexportuje, výnos = 0).

`P_rez` = `rezervovany_vykon_dodavky_kw` (kW), `interval_h` = délka intervalu (0,25 h).
Přepočet výkonového stropu na energii intervalu: `P_rez × interval_h` (kWh).
```
samospotreba_i = min(V_i, S_i)                        # co klient reálně spotřebuje z FVE
prebytek_i     = max(0, V_i − S_i)                    # potenciální přetok (energie navíc)
export_i       = min(prebytek_i, P_rez × interval_h)  # přetok omezený rez. výkonem dodávky
orez_i         = prebytek_i − export_i                # co se do rez. výkonu nevejde → ořez
dokup_i        = max(0, S_i − V_i)                    # co klient dokoupí ze sítě
```
Když `P_rez` není zadaný (neomezeno), platí `export_i = prebytek_i`, `orez_i = 0`. **Ořez
neovlivňuje samospotřebu** (ta je lokální, před exportem) – limituje jen to, co jde do sítě.

**Příklad (čísla ze zadání), 15min interval `interval_h = 0,25`:** FVE 250 kWp v daném
intervalu vyrábí **180 kW**, spotřeba **50 kW**, `P_rez = 100 kW`.
```
V_i = 180 × 0,25 = 45 kWh ;  S_i = 50 × 0,25 = 12,5 kWh
samospotreba_i = min(45; 12,5) = 12,5 kWh   → 50 kW kryje klient sám
prebytek_i     = 45 − 12,5     = 32,5 kWh   → 130 kW by chtělo do sítě
export_i       = min(32,5; 100 × 0,25) = min(32,5; 25) = 25 kWh   → do sítě jen 100 kW
orez_i         = 32,5 − 25     = 7,5 kWh    → 30 kW se ořízne (nevyužije)
```

Roční agregáty (rok `t`, s degradovanou výrobou dle 4.2):
```
E_spotreba = Σ_i S_i                         # konstantní přes roky (⚠️ předpoklad)
V_t        = Σ_i V_i,t
SS_t       = Σ_i min(V_i,t, S_i)             # samospotřeba
PRE_t      = V_t − SS_t                      # přebytek celkem (potenciální)
EXP_t      = Σ_i export_i,t                  # skutečně exportováno do sítě (≤ PRE_t)
OREZ_t     = PRE_t − EXP_t                   # ořez (nad rezervovaným výkonem dodávky)
IMP_t      = E_spotreba − SS_t               # dokup ze sítě
```
`min()` je nelineární, proto se `SS_t`/`EXP_t` **počítají znovu každý rok** s degradovaným
profilem (levné – stejná smyčka). Ukazatele: míra samospotřeby `SS_t/V_t`, míra soběstačnosti
`SS_t/E_spotreba`, míra ořezu `OREZ_t/V_t`.

**Nakládání s přebytkem `PRE_t` – nyní podporováno jako volitelný prodej (kap. 4.5):**
- když `ppa_prebytek_uctovat = false` (default): přebytek se neúčtuje, `EXP_t` nepřináší
  výnos (konzervativní, čísla se nenafukují nepotvrzeným výkupem),
- když `ppa_prebytek_uctovat = true`: exportovaná část `EXP_t` se prodává do sítě za
  `prebytek_cena_kc_mwh` (zadaná OZ) → **výnos investorovi** (klientovi ne). Ořezaná část `OREZ_t`
  vždy propadá (0 Kč) bez ohledu na přepínač.

⚠️ **Zůstává k potvrzení:** default přepínače (navrhuji vypnuto), výše ceny přebytku a zda ji
eskalovat (`ppa_index_prebytek_rocni`, kap. 8). Jiné modely (sdílení, agregátor, virtuální
baterie) jsou mimo v1.

### 4.4 Ekonomika klienta po letech

Ceny se eskalují geometricky (rok 1 = základ):
```
cena_ppa_t = cena_ppa_1 × (1 + i_ppa)^(t−1)          # Kč/MWh, i_ppa = ppa_index_ceny_rocni
cena_dod_t = cena_dod_1 × (1 + i_dod)^(t−1)          # Kč/MWh, i_dod = ppa_index_dodavatel_rocni
```
Roční náklad klienta (energie v kWh → /1000 na MWh):
```
naklad_bez_t = (E_spotreba / 1000) × cena_dod_t                          # dnešní stav
naklad_s_t   = (SS_t / 1000) × cena_ppa_t + (IMP_t / 1000) × cena_dod_t   # s PPA
uspora_t     = naklad_bez_t − naklad_s_t
             = (SS_t / 1000) × (cena_dod_t − cena_ppa_t)                  # zjednodušení
uspora_kumulativni_t = Σ_{k=1..t} uspora_k
```
Úspora klienta = **samospotřebovaná energie × (cena dodavatele − PPA cena)**. Protože PPA cena
< cena dodavatele, je kladná; dokup `IMP_t` se ruší (klient ho platí tak jako tak). To je
jádro nabídky pro klienta.

⚠️ **Předpoklady k potvrzení:**
- cenu dodavatele lze **eskalovat i zafixovat** (`i_dod`); default navrhuji stejný jako PPA
  index (aby srovnání nebylo opticky ovlivněné). Reálný odhad růstu cen silové elektřiny je
  citlivý – bereme jako parametr, ne fakt.
- „cena dodavatele" = jen silová složka, nebo i distribuce/poplatky? PPA typicky nahrazuje
  jen **silovou elektřinu**, distribuci klient platí dál z obou stran → měla by se z porovnání
  vypustit (jinak úsporu podhodnotíme/nadhodnotíme). **Potřebuju potvrdit, co `cena_dod`
  obsahuje.**

### 4.5 Ekonomika investora (Greensie)

```
CAPEX             = dle rezim_capex (kap. 3.4):            # cena_kwp: kWp × ppa_cena_fve_kc_kwp
                                                           # komponenty: součet položek z katalogu
cena_prebytek_t   = prebytek_cena_kc_mwh × (1 + i_prebytek)^(t−1)   # cena zadaná OZ; i_prebytek default 0

vynos_ppa_t       = (SS_t / 1000) × cena_ppa_t             # platby klienta za samospotřebu z FVE
vynos_prebytek_t  = ppa_prebytek_uctovat ? (EXP_t / 1000) × cena_prebytek_t : 0
                                                           # prodej EXPORTOVANÉ části do sítě (4.3)
vynos_t           = vynos_ppa_t + vynos_prebytek_t         # celkový roční výnos
oam_t             = ppa_oam_kc_kwp_rok × kWp               # provoz/údržba ⚠️ kap. 8
cf_t              = vynos_t − oam_t                        # roční cash-flow
cf_kumulativni_t  = (Σ_{k=1..t} cf_k) − CAPEX             # kumulovaně, po odečtení investice
```
Do výnosu z přebytku vstupuje **jen `EXP_t`** (co reálně prošlo do sítě), ne `PRE_t` – ořez
`OREZ_t` daný rezervovaným výkonem dodávky nepřináší nic. Rezervovaný výkon dodávky tak přímo
strope, kolik lze z přebytku zpeněžit.
**Návratnost (payback):** nejmenší `t`, kde `cf_kumulativni_t ≥ 0` (s lineární interpolací
uvnitř roku pro desetinnou hodnotu, obdoba návratnosti u peak shavingu).

**NPV a IRR** (diskontní sazba `r = ppa_diskontni_sazba`):
```
NPV = −CAPEX + Σ_{t=1..N} cf_t / (1 + r)^t
IRR = r*, pro které NPV = 0        # numericky (bisekce/Newton), obdoba binárního hledání v PS
```

⚠️ **Otevřené body:** O&M (fixní Kč/kWp/rok vs. % z CAPEX; default v1 klidně 0 s jasným
štítkem), pojištění, nájem střechy/pozemku, náklad na výměnu invertoru ~v roce 10–12,
inflace nákladů. Navrhuji je držet jako parametry s konzervativními defaulty a v UI označit,
které jsou zapnuté.

### 4.6 Cena PPA a minimální délka kontraktu (`koeficient_zisku`)

Dva režimy (navrhuji v1 podpořit režim A, B nechat jako otevřený bod):

- **Režim A – cena zadaná OZ (default):** OZ zadá nabízenou PPA cenu, appka spočítá payback/
  IRR investora (4.5) a **minimální délku kontraktu** `N_min` = payback rok (nejmenší `t`,
  kde `cf_kumulativni_t ≥ 0`). `min/max_delka_kontraktu_roky` ohraničují přípustný rozsah.

- **Režim B – cena dopočtená z marže (⚠️ k upřesnění):** definuj cenu výroby (LCOE)
  ```
  cena_vyroby_kc_mwh = CAPEX / (Σ_{t=1..N} SS_t / 1000)     # náklad na 1 MWh dodané FVE energie
  ```
  a odvoď PPA cenu z `koeficient_zisku`:
  ```
  cena_ppa_1 = cena_vyroby_kc_mwh × koeficient_zisku        # jedna z možných definic marže
  ```
  ⚠️ Přesná definice `koeficient_zisku` (násobek ceny výroby? cílová kumulovaná marže investora
  za dobu kontraktu? cílová IRR?) **není jednoznačná** – komentář u pole ve `vypoctova_nastaveni`
  ji popisuje jako „rozdíl cena výroby vs. cena pro zákazníka × koeficient zisku". Potřebuju od
  tebe závaznou definici, než tenhle režim zdrátujeme.

### 4.7 Výběr / doporučení varianty

Obdoba kap. 4.7 peak shavingu (výběr baterie). Pokud OZ zadá **jeden** kWp, spočítá se jen ta
varianta. Pokud má appka nabídnout víc velikostí, navrhuji generovat kandidáty:

- podle **pokrytí spotřeby**: kWp tak, aby `E_rok` odpovídalo ~50 / 70 / 90 / 110 % roční
  spotřeby, nebo
- pevná řada kWp (např. krok 10 kWp do fyzického limitu střechy, který OZ zadá).

**Kritérium doporučení (⚠️ k potvrzení):** dvě rozumné metriky jdou proti sobě –
1. **nejkratší payback investora** (kap. 4.5) – finanční optimum Greensie,
2. **nejvyšší míra samospotřeby** `SS/V` – větší FVE vyrábí víc, ale roste přebytek, který
   (default 4.3) nikdo neplatí → klesá efektivita každého kWp.

Navrhuji **default: nejkratší payback investora při kladné úspoře klienta**, a v UI ukázat
i 2.–3. nejlepší variantu pro srovnání (jako u peak shavingu), ať má OZ o čem s klientem
mluvit. Práh nedoporučené návratnosti = obdoba `max_navratnost_roky_peak_shaving`, navrhuji
nový klíč `ppa_max_navratnost_roky` (nebo vázat na `max_delka_kontraktu_roky`). **Potvrdit
kritérium a práh.**

---

## 5. Výstup (`navrhovana_reseni`, `typ_reseni = ppa`)

`popis_json` (obdoba peak shavingu – `vstup`, `doporucena`, `varianty`, `graf`, `upozorneni`):

- `vstup`: kWp, lokalita, sklon, azimut, cena_ppa_1, indexy, cena_dod_1, délka_kontraktu,
  `rezim_capex`, degradace, `prebytek_uctovat`, `prebytek_cena_kc_mwh`, `rezervovany_vykon_dodavky_kw`.
- `doporucena` a `varianty` (top 3), každá varianta:
  - `kwp`, `capex_kc`, `capex_rozpad` (dle režimu: cena_kwp × kWp, nebo panely/invertory/ostatní
    z katalogu vč. počtu kusů), `merny_vynos_kwh_kwp`, `k_orient`, `vyroba_rok1_kwh`,
  - `mira_samospotreby`, `mira_sobestacnosti`, `mira_orezu` (rok 1),
  - `export_rok1_kwh`, `orez_rok1_kwh`,
  - `navratnost_roky`, `irr`, `npv_kc`, `min_delka_kontraktu_roky`,
  - `roky[]` – pole po letech (viz kap. 6),
  - `souhrn_klient`: kumulativní úspora klienta za dobu kontraktu,
  - `souhrn_investor`: kumulativní CF, payback.
- `upozorneni`: seznam hlášek (chybějící cena dodavatele, přebytek se neúčtuje, výrazný ořez
  kvůli nízkému rezervovanému výkonu dodávky, O&M = 0, cena z faktury nezkontrolovaná apod.) –
  stejný princip jako u peak shavingu.
- příznaky předpokladů: `prebytek_uctovat`, `rezervovany_vykon_dodavky_kw`, `oam_zapnuto`,
  `cena_dod_obsahuje` (silová vs. vč. distribuce) – ať je v nabídce jasně vidět, na čem čísla
  stojí (obdoba `je_modelovy_odhad` / `predpoklad_aku_neoverovany` u peak shavingu).

---

## 6. Data pro grafy a tabulky

### 6.1 Graf výroby vs. spotřeby (měsíční) – komponenta obdoba `GrafOdberu.jsx`

SVG bez knihovny. Pro každý z 12 měsíců (rok 1):
```
graf = {
  mesice: [1..12],
  spotreba_kwh:      [...],   # Σ S_i v měsíci
  vyroba_kwh:        [...],   # Σ V_i v měsíci
  samospotreba_kwh:  [...],   # Σ min(V_i,S_i) v měsíci
  export_kwh:        [...],   # Σ export_i (přetok do sítě, ≤ rez. výkon dodávky)
  orez_kwh:          [...],   # Σ orez_i (nad rez. výkonem dodávky)
  dokup_kwh:         [...],   # spotreba − samospotreba
}
```
Vizuál: pro každý měsíc dva sloupce – **spotřeba** (z toho barevně odlišená samospotřeba
z FVE vs. dokup ze sítě) a **výroba** (rozdělená na samospotřeba / **přetok do sítě** /
**ořez**). Legenda: samospotřeba / dokup / přetok do sítě / ořez. Ořez zviditelní, kolik
výroby padá kvůli nízkému rezervovanému výkonu dodávky. Volitelně druhý graf – **typický
letní vs. zimní den** (15min křivka
výroby přes spotřebu), ať je vidět denní souběh; navrhuji jako „later" (obdoba 15min detailu
u peak shavingu, který zůstal na potom).

### 6.2 Tabulka úspory a návratnosti po letech

Řádek na každý rok kontraktu `t = 1..N`:

| Rok | Výroba (kWh) | Samospotřeba (kWh) | Přetok do sítě (kWh) | Ořez (kWh) | Cena PPA (Kč/MWh) | Cena dodav. (Kč/MWh) | Úspora klienta (Kč) | Kum. úspora klienta (Kč) | Výnos PPA (Kč) | Výnos přetok (Kč) | CF investora (Kč) | Kum. CF investora (Kč) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

Sloupec „Výnos přetok" je nulový, když je prodej přebytku vypnutý. Zvýrazněný **rok
návratnosti** (kde kum. CF investora poprvé ≥ 0). Pod tabulkou souhrn: CAPEX, payback, IRR,
NPV, kumulativní úspora klienta, celkový přetok vs. ořez za dobu kontraktu.

---

## 7. Rozhodnuto (business rámec – neřeším jako otevřené)

1. FVE staví a **vlastní investor (Greensie)**, klient neinvestuje. ✅
2. Klientovi se ukazuje **jen srovnání dnes vs. s PPA**; návratnost se počítá **investorovi**. ✅
3. Výroba FVE se **simuluje** z kWp + lokalita + sklon/azimut, nenahrává se. ✅
4. PPA cena je **indexovaná/eskalovaná** po letech, ne fixní. ✅
5. Výstupy: **měsíční graf výroba vs. spotřeba** + **tabulka roční/kumulativní úspory a
   návratnosti** po celou dobu kontraktu. ✅
6. Ceny bez DPH, práva `nabidkovac` / `nabidkovac_katalog`, deterministický výpočet, SVG grafy
   bez knihovny (konvence převzaté z peak shavingu). ✅
7. **Přebytek lze prodat do sítě** – volitelný přepínač účtování přebytku (**default vypnuto**)
   + cena přebytku zadaná OZ u každé nabídky, omezené **max. rezervovaným výkonem dodávky do
   sítě** (nadbytek nad stropem se ořízne). Výnos z prodeje jde investorovi. ✅

---

## 8. Otevřené body / předpoklady k ověření (⚠️)

1. **Prodej přebytku** (kap. 4.3/4.5) – funkce hotová a rozhodnutá: přepínač
   `ppa_prebytek_uctovat` **default vypnuto** (potvrzeno), cena `prebytek_cena_kc_mwh` zadaná OZ
   u každé nabídky, strop `rezervovany_vykon_dodavky_kw`. Zbývá jen drobnost: zda cenu přebytku
   po letech eskalovat (`ppa_index_prebytek_rocni`, default 0 = plochá).
2. **Co obsahuje „cena dodavatele"** (kap. 4.4) – jen silová elektřina, nebo i distribuce/
   poplatky? PPA typicky nahrazuje jen silovou složku. Ovlivní to výši úspory zásadně.
3. **Index eskalace ceny dodavatele** (kap. 4.4) – jaká výchozí hodnota, fixovat vs.
   eskalovat? Citlivý předpoklad, teď parametr s defaultem = PPA index.
4. **Definice `koeficient_zisku`** a zda dělat režim B (dopočet PPA ceny z marže, kap. 4.6).
   Bez jednoznačné definice zdrátuju jen režim A (cena zadaná OZ).
5. **Kritérium doporučené varianty** (kap. 4.7) – nejkratší payback investora vs. míra
   samospotřeby; a práh nedoporučené návratnosti pro PPA.
6. **Zdroj simulace výroby** (kap. 4.1) – stačí interní model (default 1000 kWh/kWp, měsíční
   koeficienty, korekce orientace, clear-sky denní křivka), nebo chceme PVGIS? Interní model
   = nulové závislosti, ale koeficienty a tabulka orientace jsou **ilustrativní k kalibraci**
   (potřebuju potvrdit/dodat reálné hodnoty pro ČR, případně po krajích).
7. **CAPEX FVE** (kap. 3.4/4.5) – oba režimy rozhodnuté: přepínač `rezim_capex` volí OZ mezi
   zjednodušeným (cena/kWp z manažerského nastavení) a komponentovým (poskládání z katalogu).
   K potvrzení: orientační **cena za kWp** pro zjednodušený režim; a u komponentového režimu
   pravidlo výběru panelu/invertoru z katalogu + jestli BOS (montáž/konstrukce) řešit
   přepočtem `ppa_ostatni_naklady_kc_kwp`, nebo položkou `typ = jina` v katalogu.
8. **O&M a další náklady investora** (kap. 4.5) – O&M (Kč/kWp/rok nebo % CAPEX), výměna
   invertoru, pojištění, nájem střechy. Které zapnout v v1 a s jakými defaulty?
9. **Konstantní spotřeba klienta** přes roky kontraktu (kap. 4.3) – v1 předpoklad; chceme
   umět zadat růst/pokles spotřeby?
10. **Uložení profilu výroby** (kap. 3.1) – ukládat 15min profil rok 1 (jako spotřebu), nebo
    jen přepočítávat z parametrů + ukládat měsíční agregáty?
11. **Import spotřeby v kWh** (kap. 2/3.4) – peak shaving importuje činný výkon kW; PPA
    potřebuje energii kWh za interval (kW × 0,25 h, nebo přímo kWh sloupec z exportu).
    Potvrdit formát vstupního souboru pro PPA.
12. **Solární vs. hodinový/letní čas** a **degradace roku 0 (LID)** (kap. 4.1/4.2) – drobné,
    ale ať na ně při implementaci nezapomeneme.

---

## 9. Shrnutí – na co konkrétně potřebuju tvou odpověď

Než půjdeme do implementace (PR po PR, jako u peak shavingu), potřebuju rozhodnout hlavně:

1. **Přebytek FVE** – vyřešeno: prodej hotový, default vypnuto, cena se zadává u každé nabídky.
   Zbývá jen drobnost, zda cenu přebytku po letech eskalovat. (bod 1)
2. **„Cena dodavatele"** – jen silová složka, nebo vč. distribuce? A jak eskalovat cenu
   dodavatele. (body 2, 3)
3. **Simulace výroby** – stačí interní model, nebo chceš PVGIS? A prosím reálné hodnoty
   měrného výnosu / orientační tabulky pro ČR (moje jsou ilustrativní). (bod 6)
4. **Náklady na FVE** – přepínač cena/kWp vs. komponenty z katalogu je hotový; potřebuju
   orientační **cenu za kWp** (zjednodušený režim) + pravidlo výběru komponent a **O&M**. (body 7, 8)
5. **`koeficient_zisku`** – závazná definice a jestli dělat dopočet PPA ceny z marže (režim B),
   nebo v1 jen cena zadaná OZ (režim A). (bod 4)
6. **Kritérium doporučené varianty** a práh návratnosti pro PPA. (bod 5)

Zbytek (uložení profilu, formát importu kWh, konstantní spotřeba, letní čas, LID) jsou menší
implementační detaily – navrhl jsem u nich default, stačí když je potvrdíš nebo opravíš.
