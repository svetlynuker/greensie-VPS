# Metodika výpočtu PPA – v2 (podle `docs/PPA výpočet.xlsx`)

Tenhle dokument je **reverse-engineering vašeho Excelu** `docs/PPA výpočet.xlsx` plus návrh, jak
z něj udělat plnohodnotný výpočet v appce. Nahrazuje ekonomickou část
`docs/METODIKA-ppa-fve.md` (v1) – ta počítala „naivní" investorskou ekonomiku (CAPEX vs. výnos,
payback/NPV/IRR z celého projektu) a **neznala financování**: úvěr, vlastní kapitál, DSCR,
marži při prodeji technologie do SPV, sdílení ani odkupní tabulku. Excel tohle všechno má a je
to jádro reálného obchodu, takže v2 z něj dělá zdroj pravdy.

**Fyzikální část v1 zůstává v platnosti a recykluje se** (simulace výroby kalibrovaná na PVGIS,
párování 15min profilů, degradace) – viz `METODIKA-ppa-fve.md` kap. 4.1–4.3 a
`backend/app/nabidkovac/ppa_fve.py` (`simuluj_vyrobu`, `sparuj`, `korekce_orientace`).

Ceny všude **bez DPH**, energie v MWh tam, kde jsou ceny v Kč/MWh.

---

## 1. Co Excel počítá (ověřeno do haléřů)

Excel má 4 listy:

| List | Co je to |
|---|---|
| `cashflow FVE (15)` | hlavní model: 15letý kontrakt na FVE 300 kWp |
| `pronájem BESS (10)` | baterie jako **pronájem** na 10 let (paušál, ne Kč/kWh) |
| `odkupní tabulka (15)` | za kolik si zákazník může FVE odkoupit v roce 1..15 |
| `odkupní tabulka (10)` | totéž pro 10letou variantu |

Reprodukoval jsem ho v Pythonu a čísla se trefila:

| Kontrola | Excel | Přepočet |
|---|---|---|
| Anuita úvěru (80 % CAPEX, 7,5 % p.a., 180 měs.) | 40 547,52 Kč/měs | 40 547,52 ✅ |
| DSCR rok 1 | 1,32058 | 1,32058 ✅ |
| Zisk po splátkách rok 1 | 155 983 Kč | 155 977 Kč ✅ |
| **IRR vlastních zdrojů** | **12,4252 %** | **12,4245 %** ✅ |
| Odkupní cena rok 5 | 4 401 857 Kč | 4 401 116 Kč (±0,02 %) ✅ |

Zbytkové odchylky jsou tím, že splátkový kalendář v Excelu je poskládaný z ručně
zaokrouhlených měsíčních hodnot – kumulovaně to za 15 let uteče o ~600 Kč. Nový výpočet
počítá přesně.

### 1.1 Struktura obchodu (to nejdůležitější, co v1 chyběla)

```
Greensie nakoupí technologii             →  nákladová cena
Greensie prodá technologii do SPV        →  prodejní cena = nákladová × marže
                                            (FVE marže 1,35 ; BESS marže 1,47)
Obchodník dostane provizi                →  5 % z prodejní ceny (FVE) / 4 % (BESS)
Greensie inkasuje zisk hned              →  prodejní − nákladová − provize
SPV projekt financuje                    →  20 % vlastní kapitál + 80 % bankovní úvěr
```

**Prodejní cena do SPV = CAPEX projektu.** To je číslo, které se financuje a ze kterého se
počítá návratnost – ne nákladová cena. V Excelu:

```
nákladová cena FVE = 13 500 Kč/kWp × 300 kWp = 4 050 000 Kč
prodejní cena (CAPEX) = 4 050 000 × 1,35     = 5 467 500 Kč
provize (5 %)                                =   273 375 Kč
zisk Greensie hned                           = 1 417 500 − 273 375 = 1 144 125 Kč
vlastní kapitál SPV (20 %)                   = 1 093 500 Kč
úvěr (80 %)                                  = 4 374 000 Kč
```

### 1.2 Úvěr

Anuitní, měsíční splátka, **splatnost = délka kontraktu**:

```
r_m   = úroková_sazba_p.a. / 12                    # Excel: 7,5 % / 12 = 0,625 % / měs
n     = délka_kontraktu_roky × 12                  # Excel: 15 × 12 = 180
splátka_měsíční = úvěr × r_m / (1 − (1 + r_m)^(−n))
splátka_roční   = splátka_měsíční × 12
```

### 1.3 Roční výnosy a náklady SPV

```
výroba_t        = výroba_rok1 × (1 − degradace)^(t−1)        # degradace 0,5 %/rok
prodej_zákazník_t = výroba_t × podíl_samospotřeby × cena_PPA_t
prodej_sdílení_t  = výroba_t × podíl_sdílení      × cena_sdílení_t
bateriové_služby_t = paušál_měsíční × 12                      # v FVE listu 0
zdroje_t        = prodej_zákazník_t + prodej_sdílení_t + bateriové_služby_t − servis_t
```

Excel hodnoty: `podíl_samospotřeby = 0,78`, `podíl_sdílení = 0,17`, `cena_PPA rok 1 = 2 470
Kč/MWh`, `cena_sdílení rok 1 = 1 800 Kč/MWh`, `servis = 25 000 Kč/rok` (fixní, neindexuje se).

> ⚠️ **0,78 + 0,17 = 0,95** – zbývajících 5 % výroby se nikde nezpeněží. V Excelu jsou to ruční
> čísla; v appce se **samospotřeba i přebytek spočítají z reálného 15min profilu** (kap. 3.2),
> takže tenhle 5% zbytek se musí vysvětlit jako parametr (ztráta ve sdílení / ořez /
> nealokovaná energie) – viz otevřený bod 5.

### 1.4 Indexace ceny – skokově, každé 3 roky

Tohle Excel dělá jinak, než v1 předpokládala (v1: geometricky každý rok). Excel má nad tabulkou
řádek „změna" a hodnotu 3 % vepsanou **jen v letech 4, 7 a 10** – cena tedy drží 3 roky plochá
a pak skočí:

```
rok 1–3   2 470 Kč/MWh
rok 4–6   2 544,10        (+3 %)
rok 7–9   2 620,42        (+3 %)
rok 10–15 2 699,04        (+3 %)
```

Indexuje se **stejným krokem i cena sdílení**. Každý skok je samostatně editovatelný (v Excelu
je pro roky 13 a 15 formule připravená, ale hodnota nevyplněná = 0 %). Návrh do appky:
parametr `indexace_kroky = {rok: procento}` s defaultem „+3 % v letech 4, 7, 10, 13, 16, 19",
plus jednoduchý přepínač „indexovat každý rok o X %" pro srovnání.

### 1.5 DSCR – bankovní kovenant

```
DSCR_t = zdroje_t / splátka_roční
```

V Excelu vychází 1,3069 – 1,3817. **DSCR je tvrdý limit banky**: pod ~1,25–1,30 projekt
nefinancuje. Proto je to v novém výpočtu jedna ze dvou podmínek, které určují cenu PPA.

### 1.6 Výnos investora

```
zisk_po_splátkách_t = zdroje_t − splátka_roční
CF_vlastního_kapitálu = [ −vlastní_kapitál, zisk_po_splátkách_1, …, zisk_po_splátkách_N ]
IRR = IRR(CF_vlastního_kapitálu)                  # Excel: 12,4252 %
```

Pozor na rozdíl proti v1: **IRR se počítá na vlastní kapitál** (1 093 500 Kč), ne na celý CAPEX.
Proto vychází 12,4 % – páka úvěru výnos vlastního kapitálu zvedá.

### 1.7 Odkupní tabulka

Kolik zákazník zaplatí, když chce elektrárnu odkoupit po roce `t`. Logika: cena se odvozuje od
**fiktivního úvěru na 100 % CAPEX** (jako by se nic nefinancovalo vlastním kapitálem), aby
zákazník platil „zbývající hodnotu" celé technologie:

```
zůstatek_100_t  = zůstatek fiktivního úvěru na celý CAPEX po t letech   (stejná sazba i splatnost)
poplatek_t      = zůstatek_100_1 × sazba_poplatku × t     # sazba 0,5 % (15 let) / 1,0 % (10 let)
odkupní_cena_t  = zůstatek_100_t + poplatek_t
```

Kolik na odkupu vydělá SPV:

```
zůstatek_reálný_t = zůstatek skutečného úvěru (80 % CAPEX) po t letech
poplatek_předčasné_splacení_t = zůstatek_reálný_t × 5 %
zisk_SPV_t = odkupní_cena_t − zůstatek_reálný_t − poplatek_předčasné_splacení_t
```

Příklad z Excelu (15 let): odkup v roce 1 = 5 289 190 Kč, zisk SPV 868 779 Kč; odkup v roce 14 =
952 663 Kč, zisk SPV 461 928 Kč; v roce 15 už 0.

### 1.8 Baterie = pronájem, ne cena za kWh

List `pronájem BESS (10)`. Baterie se **nezahrnuje do ceny za kWh** – zákazník platí měsíční
nájem:

```
nájem_měsíční = marže + splátka_úvěru_měsíční + EMS_měsíční
              = 4 500  + 11 158              + 1 300      = 16 958 Kč/měs
nájem_roční   = 16 958 × 12 = 203 496 Kč
náklady SPV   = EMS 1 300 × 12 + servis 12 000 = 27 600 Kč/rok
zdroje        = 203 496 − 27 600 = 175 896 Kč
DSCR          = 175 896 / 133 896 = 1,3137
zisk po splátkách = 42 000 Kč/rok  (= marže 4 500 × 12 − servis 12 000)
```

CAPEX baterie: nákladová 800 000 Kč (BESS 100 kW / 200 kWh) × marže 1,47 = 1 176 000 Kč,
provize 4 % = 47 040 Kč, vlastní kapitál 20 % = 235 200 Kč, IRR 12,22 %.

> Pozor: čísla v listu `odkupní tabulka (10)` odpovídají CAPEX 1 400 000 Kč (ne 1 176 000) –
> je to zjevně jiný, starší příklad. Vzorce jsou stejné, jen vstupy jiné.

---

## 2. Co chce Dan navíc (inverzní úloha)

Excel je „dopředný": zadáš kWp + cenu PPA + délku a vypadne DSCR/IRR. Nový výpočet má být
**obrácený**:

| Vstup | Zdroj |
|---|---|
| 15minutový odběrový diagram (rok) | nahraný soubor (už existuje – `spotreba_profil`) |
| **Silová složka** ceny, kterou zákazník platí dnes (Kč/MWh) | zadá OZ / z faktury |
| **Vyhnutelné regulované složky** (Kč/MWh) | manažerské nastavení, default 260 |
| Napěťová hladina: **VN** (NN jen jako budoucí volba, zatím prázdná) | výběr |
| Cílová míra samospotřeby (default **80 %**, editovatelná) | nastavení |
| Baterie ano/ne (**vždy volitelná**) | přepínač |
| DSCR min a IRR cíl | **manažerské nastavení** |

| Výstup | |
|---|---|
| **Ideální velikost FVE (kWp)** | z diagramu a cíle samospotřeby |
| **Cena za vyrobenou kWh, kterou PPA prodá zákazníkovi** | dopočtená z ekonomiky, pro každou délku |
| **Nabídka délek kontraktu 10 / 15 / 20 let** | s cenou, slevou, DSCR a IRR – vybírá obchodník |

### 2.1 Co PPA nahrazuje (rozhodnuto 29. 7. 2026)

PPA nahrazuje **silovou složku + část regulovaných** složek (za použití sítí), protože
samospotřebovaná energie neprochází distribuční soustavou:

```
cena_vyhnutelná = cena_silová + vyhnutelné_regulované      # default 260 Kč/MWh
sleva_zákazníkovi = 1 − cena_PPA / cena_vyhnutelná
```

Zbytek ceny (neodvratitelné regulované složky, daň) zákazník platí dál z obou stran, takže do
srovnání nevstupuje – jinak by se sleva nadhodnotila. Vstupem je proto **silová složka**, ne
celková cena z faktury; kdyby OZ zadal celkovou cenu, sleva by vyšla opticky lepší, než je.

### 2.2 Napěťová hladina VN vs. NN

U VN je struktura regulovaných složek jiná než u NN (jiná cena za použití sítí, jiná
rezervovaná kapacita). Řešení: **enum `hladina` = `VN` | `NN`**, sazby v manažerském nastavení
per hladina, `NN` zatím prázdné – volba v UI je, ale výpočet ji odmítne
(`NepodporovanaHladina`).

---

## 3. Navržený algoritmus

Tři fáze: velikost → cena → délka. Každá staví na té předchozí.

### 3.1 Fáze A – velikost FVE z cíle samospotřeby

1. Simuluj výrobu **pro 1 kWp** na 15min mřížce profilu spotřeby (recyklace `simuluj_vyrobu`,
   měrný výnos 1055 kWh/kWp kalibrovaný na PVGIS, korekce orientace, clear-sky denní křivka,
   letní čas). Výroba je v kWp lineární → stačí škálovat.
2. Pro kandidátní `kWp` spočítej **míru samospotřeby** = `SS / V`, kde
   `SS = Σ min(V_i, S_i)`, `V = Σ V_i` (kap. 4.3 v1).
3. `SS/V` **monotónně klesá** s rostoucím kWp (malá FVE se spotřebuje celá, velká přetéká) →
   binárním hledáním najdi **největší kWp, kde `SS/V ≥ cíl`** (default 0,80).
4. S baterií: baterie zvýší `SS/V`, takže při stejném cíli **umožní větší FVE**. Dispatch
   (greedy, jednoduchý a deterministický, v duchu peak shavingu):
   ```
   pro každý interval i:
       přebytek = max(0, V_i − S_i)
       deficit  = max(0, S_i − V_i)
       nabij  = min(přebytek, volná_kapacita, P_max × interval_h) × η_nabíjení
       vybij  = min(deficit,  dostupná_energie, P_max × interval_h) × η_vybíjení
       SS_i = min(V_i, S_i) + vybij_pokrytá_část
   ```
   Kapacita = `kapacita_kwh × DoD`, účinnost round-trip default 0,90.

> **Pozn.:** cíl je definovaný jako `SS / výroba` (tak to má Excel: `C7 = 0,78`,
> „samospotřeba nominálně" = `výroba × 0,78`). **Ne** jako pokrytí spotřeby (`SS / spotřeba`) –
> to je jiné číslo a dalo by úplně jinou elektrárnu. Viz otevřený bod 1.

### 3.2 Fáze B – cena PPA z požadované ekonomiky

Pro dané `kWp` a délku `N`:

```
CAPEX          = kWp × nákladová_cena_kč_kWp × marže_FVE        (+ baterie, pokud je)
vlastní_kapitál = CAPEX × podíl_vlastního_kapitálu              # 20 %
úvěr            = CAPEX − vlastní_kapitál                       # 80 %
splátka_roční   = anuita(úvěr, sazba, N)
```

Podíly `podíl_samospotřeby = SS/V` a `podíl_sdílení = přebytek_zpeněžitelný/V` se vezmou
**z fáze A** (reálný profil), ne ručně.

Cena PPA rok 1 se hledá tak, aby byly splněné **obě** podmínky:

```
(1) DSCR_t ≥ DSCR_min       pro každý rok t = 1..N        # default 1,30 (banka)
(2) IRR(CF_vlastního_kapitálu) ≥ IRR_cíl                  # default 12,5 % (Excel má 12,43 %)
```

Obě se dají vyřešit **analyticky**, bez iterace – `zdroje_t` i NPV jsou v ceně lineární:

```
(1) z DSCR:  cena_1 ≥ (DSCR_min × splátka − sdílení_t − nájem + náklady) / (SS_t × index_t)
             … a vezme se maximum přes roky (nejtěsnější rok rozhoduje)
(2) z IRR:   podmínka „IRR ≥ IRR_cíl" je pro cash-flow s jednou změnou znaménka
             ekvivalentní „NPV při diskontu IRR_cíl ≥ 0"; NPV je v ceně lineární,
             takže cena_1 = −zbytek / koeficient
```

Analytické řešení je nejen rychlejší, ale i robustnější než bisekce přes IRR – u velmi
vysokých cen IRR vyletí do stovek procent a numerické hledání by na rozsahu selhalo.
Vezme se

```
cena_PPA_rok1 = max(cena_z_DSCR, cena_z_IRR)
```

Nejnižší cena, kterou lze zákazníkovi nabídnout, aniž by projekt přestal být financovatelný
a výnosný. Následuje kontrola obchodní smysluplnosti:

```
sleva_zákazníkovi = 1 − cena_PPA_rok1 / cena_zákazníka_dnes
```

Když je sleva menší než `min_sleva` (default 10 %) nebo negativní → **nabídka nedává smysl**
a výpočet to zahlásí jako upozornění (typicky: příliš drahá technologie, moc krátký kontrakt,
nebo zákazník má už teď levnou elektřinu).

### 3.3 Fáze C – délky kontraktu (rozhodnuto 29. 7. 2026)

Delší kontrakt → nižší roční splátka → nižší potřebná cena PPA → větší sleva zákazníkovi, ale
delší závazek. Výpočet **jednu délku nedoporučuje** – spočítá všechny nabízené a výběr nechá
na obchodníkovi, protože závisí na tom, co je konkrétní zákazník ochotný podepsat:

```
pro N v nabízené_délky (default 10, 15, 20):
    spočítej cena_PPA_rok1(N), sleva_zákazníkovi(N), DSCR(N), IRR(N)
```

Výstup je tabulka `N → cena Kč/kWh → sleva → DSCR → IRR → kumulativní úspora`. Příklad
z reálného běhu (VN, 1 073 MWh/rok, silová 3 500 Kč/MWh, FVE 526 kWp):

| Délka | Cena PPA | Sleva | DSCR | IRR | Limituje | Úspora zákazníka celkem |
|---|---|---|---|---|---|---|
| 10 let | 2,838 Kč/kWh | 24,5 % | 1,30 | 13,10 % | DSCR | 4 148 594 Kč |
| 15 let | 2,140 Kč/kWh | 43,1 % | 1,31 | 12,50 % | IRR | 11 053 032 Kč |
| 20 let | 1,827 Kč/kWh | 51,4 % | 1,32 | 12,50 % | IRR | 17 815 200 Kč |

Sloupec „limituje" ukazuje, která podmínka cenu drží: u krátkého kontraktu je vysoká splátka,
takže rozhoduje **banka** (DSCR); u dlouhého je splátka nízká a rozhoduje **investor** (IRR).

Zůstává jen kontrola smysluplnosti: když ani nejdelší kontrakt nedá slevu aspoň `min_sleva`
(default 10 %), výpočet zahlásí, že nabídka nedává obchodní smysl.

### 3.4 Baterie – vždy jako volitelná varianta

Podle Excelu se baterie **neúčtuje v Kč/kWh, ale měsíčním nájmem**:

```
nájem_měsíční = marže_měsíční + splátka_úvěru_baterie_měsíční + EMS_měsíční
```

Výpočet proto vždy vrací **dvě varianty**: „FVE" a „FVE + baterie". U varianty s baterií:

- větší FVE (baterie zvedne samospotřebu, viz 3.1 bod 4),
- CAPEX = FVE + baterie, každé se svou marží (1,35 / 1,47),
- výnos = platby za kWh (FVE) + nájem baterie (paušál),
- pro zákazníka se srovnává **celková roční platba** (kWh × cena PPA + nájem) proti tomu, co
  platí dnes – jinak by nájem baterie zmizel a sleva by byla opticky lepší, než je.

> ⚠️ **Zjištění z prvního běhu na realistickém profilu (VN, 1 073 MWh/rok, 3 500 Kč/MWh):**
> varianta s baterií vyšla pro zákazníka **horší** – kumulativní úspora 2,9 mil. Kč proti
> 4,3 mil. Kč bez baterie. Nájem baterie (~200 tis. Kč/rok) převáží přínos vyšší
> samospotřeby (FVE 623 kWp místo 526 kWp, pokrytí spotřeby 49 % místo 41 %).
>
> Není to chyba výpočtu, ale **důsledek toho, co se počítá**: baterie tady vydělává jen
> posunem přebytku FVE do večera. Reálná hodnota baterie je hlavně v **peak shavingu**
> (úspora na rezervované kapacitě) a **bateriových službách** (Excel má pro ně samostatný
> řádek „bateriové služby") – a ty v PPA modelu nejsou, protože je řeší jiný modul.
> Výpočet proto tuhle situaci **hlásí jako upozornění**: baterii nabízet jen v kombinaci
> s peak shavingem, ne jako samostatný přílepek k PPA. Sloučení obou modelů do jedné
> nabídky je logický další krok (otevřený bod 6).

### 3.5 Odkupní tabulka

Dopočítává se pro doporučenou variantu podle kap. 1.7 – tabulka `rok → odkupní cena → zisk SPV`
na celou dobu kontraktu.

---

## 4. Parametry a jejich defaulty

Do `vypoctova_nastaveni.parametry` (JSONB, edituje vedení/admin – právo `nabidkovac_katalog`).
Hodnoty odvozené z Excelu:

| Parametr | Default | Odkud |
|---|---|---|
| `ppa_nakladova_cena_kc_kwp` | 13 500 | Excel `cashflow FVE` D34 |
| `ppa_marze_fve` | 1,35 | Excel E32 |
| `ppa_marze_bess` | 1,47 | Excel `pronájem BESS` E36 |
| `ppa_provize_fve` | 0,05 | Excel F35 |
| `ppa_provize_bess` | 0,04 | Excel F36 |
| `ppa_podil_vlastniho_kapitalu` | 0,20 | Excel B24 / C29 |
| `ppa_urokova_sazba` | 0,075 | odvozeno ze splátkového kalendáře |
| `ppa_dscr_min` | 1,30 | Excel vychází 1,31–1,38; **povinně editovatelné v nastavení** |
| `ppa_irr_cil` | 0,125 | Excel 12,43 %; **povinně editovatelné v nastavení** |
| `ppa_servis_kc_rok` | 25 000 | Excel C12 |
| `ppa_degradace_rocni` | 0,005 | Excel `*0,995` |
| `ppa_indexace_krok` | 0,03 | Excel I3/L3/O3 |
| `ppa_indexace_perioda_roky` | 3 | Excel (roky 4, 7, 10) |
| `ppa_cena_exportu_kc_mwh` | **0** | ⚠️ úmyslně jinak než Excel (1 800) – viz kap. 4.1 |
| `ppa_cil_mira_samospotreby` | 0,80 | zadání (Excel má 0,78); počítá se **z výroby** |
| `ppa_vyhnutelne_regulovane_kc_mwh` | 260 | vyhnutelná část regulovaných na VN (kap. 2.1) |
| `ppa_min_sleva_zakaznikovi` | 0,10 | mez pro hlášku „nedává obchodní smysl" |
| `ppa_nabizene_delky_roky` | 10, 15, 20 | rozhodnuto 29. 7. 2026 (kap. 3.3) |
| `ppa_bess_marze_kc_mesic` | 4 500 | Excel `pronájem BESS` D23 |
| `ppa_bess_ems_kc_mesic` | 1 300 | Excel B10 |
| `ppa_bess_servis_kc_rok` | 12 000 | Excel B11 |
| `ppa_odkup_poplatek_rocni` | 0,005 | Excel B33 (15 let); 0,01 u 10 let |
| `ppa_odkup_poplatek_predcasne_splaceni` | 0,05 | Excel B40 |

### 4.1 Za přetoky se defaultně neinkasuje nic (rozhodnuto 29. 7. 2026)

Excel počítá s prodejem přebytku za 1 800 Kč/MWh. To je ale **výnos, který ve skutečnosti
nemusí existovat** – dokud není sjednaný výkup nebo sdílení, přebytek propadá. Appka proto
má **default 0 Kč** a cenu za export se zadává u konkrétní nabídky
(`VstupPPA2.cena_exportu_kc_mwh`), protože závisí na lokalitě a smlouvě.

Důsledek je podstatný: bez druhého výnosového toku musí cenu pokrýt sám zákazník, takže
**cena PPA vyjde vyšší**. Na modelovém případu (526 kWp, 15 let) je to 2 577 Kč/MWh při
nulové ceně za export proti 2 139 Kč/MWh při 1 800 Kč/MWh.

Cena za export vstupuje do výsledku **lineárně a se stejným sklonem** u podmínky z DSCR
i z IRR (sklon = `podíl_exportu / míra_samospotřeby`), takže platí exaktně:

```
cena_PPA(cena_exportu) = cena_PPA(0) − (podíl_exportu / míra_samospotřeby) × cena_exportu
```

Roční „zdroje" jsou na ceně za export **invariantní** (pokles platby zákazníka přesně
vyrovná výnos z exportu), takže se nemění ani DSCR, ani IRR, ani která podmínka cenu drží.
Ověřeno proti enginu na strojovou přesnost – využívá toho náhledová stránka.

### 4.2 Strop velikosti FVE

`VstupPPA2.max_kwp` omezí elektrárnu na zadanou hodnotu (střecha, rezervovaný výkon
připojení). Výstup nese `omezeno_max_kwp` a `kwp_bez_stropu`, a když strop velikost srazí,
výpočet to **hlásí jako upozornění** – míra samospotřeby je pak nad cílem a elektrárna
pokryje menší část spotřeby, než by šlo.

> **Opraveno (nalezeno testem):** zaokrouhlení na celé kWp probíhalo *až po* zastropování,
> takže strop 35,5 kWp vracel elektrárnu 36 kWp. Nad stropem se teď zaokrouhluje dolů;
> strop pod 1 kWp vrací 0 („nedá se postavit"). Pojistka:
> `test_neceločíselný_strop_se_nepřekročí`.

---

## 5. Otevřené body

### ✅ Rozhodnuto 29. 7. 2026

1. **Cíl samospotřeby (80 %)** = `SS / výroba`, jak to má Excel (`C7 = 0,78`). **Ne**
   `SS / spotřeba`. Pozor na důsledek: pokrytí spotřeby z FVE pak vychází výrazně nižší
   (v testovacím případě 41 %), protože bez baterie nelze víc spotřebovat na místě.
2. **Vyhnutelná cena** = silová složka + část regulovaných (za použití sítí), viz kap. 2.1.
   Vstupem je silová složka, regulované jsou parametr (default 260 Kč/MWh).
3. **Délka kontraktu** – nedoporučuje se, nabízí se 10 / 15 / 20 let, vybírá obchodník
   (kap. 3.3).
4. **DSCR min a IRR cíl** – oboje **editovatelné v manažerském nastavení**, ne konstanty
   v kódu. Defaulty z Excelu (1,30 / 12,5 %) jsou jen výchozí hodnoty.

### ⚠️ Zbývá potvrdit

5. **Sdílení** – v Excelu 17 % výroby za 1 800 Kč/MWh, přičemž 78 + 17 = 95 % (5 % nikde).
   Co je těch 5 %? A má se v appce sdílet **celý** přebytek z profilu, nebo jen část (a jaká
   pravidla / limit)? Teď se počítá celý export a výpočet u toho hlásí upozornění; parametr
   `podil_zpenezitelneho_prebytku` to umí zkrátit (Excel odpovídá ~0,77).
6. **Baterie** – potvrdit, že se zákazníkovi účtuje **měsíčním nájmem** (ne v ceně za kWh;
   tak to má Excel a tak je to implementované), a jak se určuje velikost baterie. Teď: buď ji
   zadá OZ, nebo se navrhne heuristicky z mediánu denního přebytku. Souvisí s tím zjištění
   z kap. 3.4 – bez peak shavingu baterie zákazníkovi úsporu spíš zhoršuje.
7. **Cena za kWp 13 500 Kč a marže 1,35 / 1,47** – jsou to aktuální čísla, nebo jen stav
   z doby vzniku Excelu? Jdou přímo do CAPEX, takže ovlivní všechno.

---

## 6. Stav implementace

### ✅ Hotovo

1. **`backend/app/nabidkovac/ppa_v2.py`** – výpočetní jádro, čistě funkce nad seznamy čísel
   (bez DB/FastAPI), jako `peak_shaving.py`: anuita a zůstatek úvěru analyticky, DSCR,
   IRR i NPV vlastního kapitálu, skoková indexace, odkupní tabulka, greedy dispatch baterie,
   návrh velikosti FVE binárním hledáním, analytické řešení ceny PPA z DSCR i z IRR, sweep
   délek kontraktu a výběr ideální délky.
2. **`backend/tests/test_ppa_v2.py`** – 79 testů, z toho reprodukce Excelu jako regresní
   pojistka: `cashflow FVE (15)` (anuita 40 547,52 Kč; DSCR 1,32058; IRR 12,4252 %),
   `odkupní tabulka (15)` a `pronájem BESS (10)`. Zbytek testuje vlastnosti, na kterých
   algoritmus stojí (monotonie míry samospotřeby v kWp, monotonie ceny v délce kontraktu,
   energetická bilance baterie, odmítnutí NN).

Ověřeno i na realistickém ročním 15min profilu (35 040 intervalů, 1 073 MWh, VN, silová
3 500 Kč/MWh): výpočet proběhne za **0,5 s** a vrátí FVE 526 kWp plus tabulku tří délek
kontraktu (viz kap. 3.3).

### ⏳ Zbývá

3. **Napojení** – `routes.py` endpoint + `schemas.py` vstup, výsledek do `navrhovana_reseni`
   (`typ_reseni = ppa`), stejným způsobem jako v1. Parametry z `vypoctova_nastaveni` (kap. 4).
4. **UI** – panel se vstupy (diagram, cena dnes, hladina, cíl samospotřeby, baterie ano/ne),
   výstup: 3 headline čísla (kWp / Kč/kWh / roky), tabulka po letech, tabulka délek kontraktu,
   odkupní tabulka, graf výroba vs. spotřeba (recyklace `GrafVyrobaSpotreba.jsx`).
5. **Migrace v1 → v2** – v1 `spocti_ppa` nechat běžet, dokud v2 neprojde ověřením na reálné
   nabídce; pak v1 ekonomiku odstranit a fyzikální část ponechat jako sdílenou.
6. **Sloučení s peak shavingem** – aby baterie v nabídce vydělávala i na rezervované kapacitě
   a bateriových službách (viz zjištění v kap. 3.4).

Otevřené body z kap. 5 jsou v kódu **parametry s defaultem podle Excelu**, ne zadrátované
předpoklady – odpověď na ně tedy znamená jen změnu čísla v nastavení, ne přepis výpočtu.
