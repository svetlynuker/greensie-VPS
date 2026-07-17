# Rešerše: On-site PPA (behind-the-meter FVE) v ČR — metodika a benchmarky 2025/2026

> Součást auditu kalkulátorů 16. 7. 2026 (viz [README](README.md)). Míra jistoty u každého
> bloku: ✅ vysoká (primární zdroj — cenový výměr/zákon), 🟡 střední (sekundární zdroj),
> 🔶 nízká (triangulace/odhad).

---

## 1. KRITICKÉ — čemu se VN odběratel vyhne samospotřebou za elektroměrem

Samospotřeba z FVE za předávacím místem (behind-the-meter) snižuje **odebrané množství ze sítě (MWh)**, ale **nemění rezervovanou kapacitu, rezervovaný příkon ani fixní měsíční platby**. Vyhnuté složky jsou proto jen ty účtované **za MWh odebranou ze soustavy**:

### (a) Cena za použití sítí VN (variabilní složka distribuce) ✅
Zdroj: Cenové rozhodnutí ERÚ č. 11/2024, bod 4.42 ([PDF věstníku na predistribuce.cz](https://www.predistribuce.cz/Files/ceny/cenove-rozhodnuti-eru-c-132024/)) a návrh cenového výměru pro 2026 ([eru.gov.cz PDF](https://eru.gov.cz/sites/default/files/obsah/prilohy/cveru2026vvn-vn251030vkp.pdf), finál = výměr č. 13/2025):

| Distributor | VN 2025 (Kč/MWh) | VN 2026 (Kč/MWh, návrh z 30.10.2025) |
|---|---|---|
| ČEZ Distribuce | **87,41** | **106,22** |
| EG.D | **79,91** | **98,61** |
| PREdistribuce | **44,50** | **83,14** |
| (VVN pro srovnání, ČEZ) | 45,35 | 69,76 |

Pozn.: hodnoty 2026 jsou z návrhu výměru 13/2025 do veřejného konzultačního procesu; finální výměr (vydán 27. 11. 2025, [tisková zpráva ERÚ](https://eru.gov.cz/eru-vydal-cenove-vymery-kterymi-stanovi-regulovane-ceny-elektriny-plynu-na-rok-2026-0)) se může o jednotky % lišit — doporučuji přečíst finální PDF na [eru.gov.cz/cenove-vymery](https://eru.gov.cz/cenove-vymery). Meziroční nárůst ceny za použití sítí je způsoben dražším krytím ztrát.

### (b) POZE — nejdůležitější a nejčastěji špatně modelovaná položka ✅

**Právní stav (zákon č. 165/2012 Sb., § 28 a § 28a, znění k 1. 1. 2025,** [konsolidované znění PDF, ČEZ Distribuce](https://www.cezdistribuce.cz/file/edee/distribuce/legislativa/sb_2012_165_2025-01-01.pdf)):
- U **VVN/VN se POZE platí z rezervovaného příkonu** (Kč/MW/měsíc), u NN z jističe (Kč/A/měsíc) — **nikoli z MWh**.
- **Strop (maximální platba)**: 495 Kč/MWh × celkové **odebrané** množství z přenosové/distribuční soustavy (§ 28a odst. 2). Platí se tedy `min(sazba × rezervovaný příkon; 495 × odběr ze sítě)`.
- **Lokální spotřeba (za elektroměrem) složku POZE od 1. 1. 2022 NEHRADÍ** — povinnost výrobce platit POZE z lokální spotřeby (dřívější režim s výjimkou do 30 kW) byla zrušena novelou č. 382/2021 Sb.; v aktuálním § 28/§ 28a žádná taková povinnost není (ověřeno v konsolidovaném znění). Elektřina z on-site FVE spotřebovaná klientem tedy POZE nezatěžuje, a to bez ohledu na výkon výrobny. To je změna oproti stavu do 2021, kdy se POZE z lokální spotřeby u výroben nad 30 kW platilo.

**Sazby:**
- 2025 (CR 11/2024, bod 5.1.1): **115 880,79 Kč/MW/měsíc** (VVN/VN); NN 84,70 Kč/A/měsíc; strop 495 Kč/MWh.
- 2026: v listopadovém výměru ještě 60 035,08 Kč/MW/měsíc (návrh), ale **změnovým cenovým výměrem z 29. 12. 2025 byla složka POZE pro odběratele snížena na NULU** — vláda 16. 12. 2025 rozhodla hradit podporu plně ze státního rozpočtu ([ERÚ — změnový výměr](https://eru.gov.cz/eru-vydal-zmenovy-cenovy-vymer-kterym-upravuje-regulovane-ceny-na-rok-2026), [usetreno.cz](https://www.usetreno.cz/clanky/eru-cenove-rozhodnuti-2026/)). Průměrná regulovaná cena VN tím klesla z 1 427 (2025) na **1 128 Kč/MWh (−21 %)**.

**Dopad na kalkulačku — marginální úspora POZE na samospotřebovanou MWh:**
- **2025**: záleží na využití rezervovaného příkonu. Zlomový bod = 115 880,79 × 12 / 495 = **2 809 hodin/rok**. Pokud klientův roční odběr / rezervovaný příkon < 2 809 h (běžné u jedno-/dvousměnných provozů), platí přes strop → **každá samospotřebovaná MWh šetří 495 Kč**. Při vyšším využití platí z kapacity → **marginální úspora 0 Kč/MWh**.
- **2026**: **0 Kč/MWh** pro všechny.
- **2027+**: nejisté — o dotaci ze státního rozpočtu rozhoduje vláda každoročně usnesením do 30. 9. (§ 28 odst. 3). Konzervativní model: POZE úspora = 0; optimistický: max 495 Kč/MWh při nízkém využití příkonu. Doporučuji v kalkulačce parametrizovat.

### (c) Cena za systémové služby ✅
Účtuje se **ke každé MWh dopravené soustavou** zákazníkovi (bod 3.1.1 výměru) → samospotřebou plně vyhnutá:
- **2025: 170,92 Kč/MWh** (CR 11/2024; potvrzuje [energie.cz](https://www.energie.cz/regulovane-slozky-cen-energii-pro-rok-2025/))
- **2026: 164,24 Kč/MWh** (návrh výměru 13/2025; finál potvrzen jako „levnější“ v TZ ERÚ)

### (d) Daň z elektřiny — POZOR, u >30 kW se NEUŠETŘÍ 🟡
Sazba **28,30 Kč/MWh** (zákon č. 261/2007 Sb., část 47). Od 1. 1. 2024 (konsolidační balíček, z. 349/2023) je osvobozena jen **ekologicky šetrná elektřina vyrobená a spotřebovaná v odběrném místě z výrobny do 30 kW** ([kalkulator.cz FAQ](https://www.kalkulator.cz/faq/otazka/29/dan-elektrina), [portal.pohoda.cz](https://portal.pohoda.cz/dane-ucetnictvi-mzdy/ostatni-dane/ekologicke-dane/dan-z-elektriny/)). U on-site PPA s výrobnou nad 30 kW je dodávka klientovi (konečnému spotřebiteli) **předmětem daně** — investor se registruje u celní správy a daň odvádí ([SolidSun blog](https://www.solidsun.cz/blog/spotrebni-dan-z-elektriny-u-fotovoltaiky-prehledne-informace-pro-provozovatele-fve); ten uvádí limit 50 kW — rozpor se zněním zákona, doporučuji ověřit u celní správy, převažující výklad je 30 kW). **Čistá úspora klienta na dani = 0** (daň platí v ceně ze sítě i v PPA dodávce) — kalkulačka ji nesmí počítat do úspory, resp. musí být symetricky na obou stranách.

### (e) Poplatek OTE / nesíťová infrastruktura ✅
Od 2024 **fixní Kč/odběrné místo/měsíc, nikoli za MWh** → samospotřebou se nešetří nic. 2025: OTE 2,26 + 0,99, EDC 5,20, + poplatek ERÚ (celkem 10,84 Kč/měs bez DPH). 2026 (návrh): OTE 1,61 + 1,38, EDC 5,88 + ERÚ. **Marginální úspora 0 Kč/MWh.**

### Souhrn — celková vyhnutá platba NAD rámec silové elektřiny (VN odběratel, bez DPH)

| Složka | 2025 | 2026 |
|---|---|---|
| Použití sítí VN | 44,50–87,41 | ~83–106 |
| Systémové služby | 170,92 | 164,24 |
| POZE | **0 nebo 495** (dle využití příkonu, strop) | **0** |
| Daň z elektřiny (FVE >30 kW) | 0 | 0 |
| OTE/nesíťová infr., rezerv. kapacita, jistič | 0 | 0 |
| **Celkem regulované** | **215–258** (bez POZE) až **710–753** (s POZE) | **~247–270** |

+ hlavní položka úspory = **silová elektřina vč. marže dodavatele** (viz bod 3d). Pokud kalkulačka počítá „cena od dodavatele“ jako kompletní koncovou cenu vč. všech regulovaných složek, **nadhodnocuje úsporu** (o fixní složky, OTE, v 2026 o POZE, o daň) — správně je porovnávat jen s „vyhnutelnou“ částí ceny.

---

## 2. Struktura on-site PPA smluv v ČR 🟡

Prakticky všichni velcí hráči nabízejí model „FVE bez investice / za korunu“:

- **Co PPA cena pokrývá**: CAPEX+financování+O&M+pojištění+marži investora; klient platí **jen za skutečně odebranou (samospotřebovanou) MWh** ([GreenBuddies](https://www.greenbuddies.eu/site/power-purchase-agreement-ppa): „elektrárna zůstává v našem vlastnictví… platíte pouze za odebranou energii za garantovanou cenu nižší než od stávajícího dodavatele“; veškerý provoz a údržbu nese investor). ČEZ ESCO: fixní cena za MWh **včetně záruk původu** ([cezesco.cz](https://www.cezesco.cz/en/products/ppa)).
- **Indexace**: veřejně doložená praxe = **inflace ČSÚ (CPI)** — [TEDOM energie](https://www.tedomenergie.cz/fotovoltaika/fotovoltaika-bez-vlastni-investice/): cena „neměnná, ovlivnit ji může pouze meziroční výše inflace dle ČSÚ“. ČEZ ESCO deklaruje „fixed price per MWh for the duration“ (12 let typicky). Pevné % p.a. (1,5–2,5 %) se v nabídkách vyskytuje, ale veřejně ho nikdo nepublikuje 🔶. Parametrizace „X %/rok“ je tržně konformní; default vázat na CPI ~2–2,5 %.
- **Délka**: 15–25 let standard ([E.ON](https://www.eon.cz/byznys-energie/energie-bez-investice-stale-vice-firem-zacina-vyuzivat-ppa/) 15–25; TEDOM 20 let, odkup po 20 letech za 1 000 Kč, možnost dřívějšího odkupu po 6 letech za předem danou cenu; ČEZ ESCO typicky 12; jiní 15 let s odkupem za 1 Kč).
- **Přebytky**: patří investorovi (jeho výrobna) — prodává je obchodníkovi/na spot, nebo se **sdílí přes EDC** na další odběrná místa klienta (registrace skupin sdílení od 1. 8. 2024, max 5 výrobních EAN na OPM; [edc-cr.cz](https://www.edc-cr.cz/pro-verejnost/nase-temata/sdileni-elektriny/)). E.ON explicitně říká, že nejlepší ekonomika je u klientů, kteří spotřebují vše na místě. V modelu „platba za odebranou MWh“ přebytky klienta nezatěžují — ověřit ale ve smlouvách take-or-pay klauzule.
- **Licence výrobce**: drží **investor** (vlastník výrobny). Od 1. 8. 2025 (Lex OZE III) je bez licence možný provoz do 100 kW, ale **jen pokud nejde o podnikání — prodej elektřiny klientovi = podnikání → licence vždy** ([ERÚ](https://eru.gov.cz/licence-na-fotovoltaiku)).
- **Odchylka**: za odběrné místo klienta nese dál jeho dodavatel/subjekt zúčtování (FVE jen snižuje odběr); za přetoky do sítě odpovídá investor — řeší smlouvou s obchodníkem, který přebírá odpovědnost za odchylku 🟡.

---

## 3. Tržní benchmarky 2025/2026

### (a) On-site PPA cena pro C&I 🟡/🔶
- Utility-scale/off-site solar PPA CZ: **60–75 EUR/MWh** (7–10 let, kontrakty z 2024 pro dodávky od 2025; [vyhodna-energie.cz](https://www.vyhodna-energie.cz/blog/13/dodavatele-elektricke-energie/ppa-kontrakt-power-purchase-agreement)). Evropský průměr podepsaných solárních PPA Q3 2025: **34,25 EUR/MWh** (LevelTen/[PV-Tech](https://www.pv-tech.org/european-solar-ppa-prices-fall-below-35-mwh-q3-2025/)) — pozor, to je pay-as-produced utility-scale, ne on-site.
- **C&I (100 kW–1 MW) on-site PPA** v sousedních zemích 2026: DE **65–85**, PL **60–78**, AT **65–82 EUR/MWh** ([Solar Data Atlas](https://www.solardataatlas.com/en/data-solar-ppa-prices-europe), data LevelTen Q4 2025 + Pexapark; ČR v datasetu chybí).
- ČR on-site: veřejná čísla neexistují; triangulací (LCOE střešní C&I ~730–1 100 Kč/MWh dle [PKV](https://www.pkv.cz/en/blog/vyplati-se-fotovoltaika-vypocet-navratnosti-2024) + marže + srovnání s vyhnutelnou cenou ~2 700–3 500 Kč/MWh) vychází tržní pásmo **cca 1 600–2 600 Kč/MWh (≈65–105 EUR/MWh)** s indexací 🔶. Sanity check pro kalkulačku: PPA cena musí ležet mezi LCOE investora a vyhnutelnou cenou klienta.

### (b) CAPEX střešní C&I FVE 🟡
- **Nad 100 kWp: 25–35 Kč/Wp** (= 25 000–35 000 Kč/kWp) — [ČESKÉSTAVBY.cz, 2025](https://www.ceskestavby.cz/clanky/montovana-hala-a-fotovoltaika-kolik-kwp-unese-strecha-a-kdy-se-fve-skutecne-vyplati-36199.html); modelový příklad 200 kWp = 6 mil. Kč (30 Kč/Wp), výroba 1 000 kWh/kWp.
- PKV (2024, firemní kontext): **~22 000 Kč/kWp**.
- Domácnosti/do 50 kWp: 35 000–50 000 Kč/kWp ([Schlieger](https://schlieger.cz/blog/cena-fotovoltaiky-2025-kolik-zaplatite-za-instalaci/), [czechobserver](https://czechobserver.com/blog/fotovoltaika-navratnost-cena-dotace/)).
- Orientační škála pro kalkulačku 🔶: **50 kWp ≈ 28–35 tis. Kč/kWp; 200 kWp ≈ 24–30 tis.; 1 MWp ≈ 18–25 tis. Kč/kWp** (bez baterie, bez DPH). Dotace RES+ (30 % FVE / 50 % akumulace, [silektro k výzvě RES+ 1/2025](https://silektro.cz/fotovoltaicke-elektrarny/dotace/vyzva-res-c-1-2024-fotovoltaicke-elektrarny-10-kw-5-mw-s-vlastni-spotrebou)) a bezúročný úvěr NRB (do 3 mil. Kč; program 15. 9. 2025 pozastaven — vyčerpán) CAPEX efektivně snižují.

### (c) O&M 🔶
Veřejné benchmarky pro C&I chudé: malé FVE ~5 000–10 000 Kč/rok komplet ([solarkalkulacka](https://www.solarkalkulacka.cz/blog/fotovoltaika-na-klic-cena-2026)); revize à 4 roky 1 500–5 000 Kč; monitoring ~1 200 Kč/rok; nad 100 kWp individuálně. Rozumný model: **1–2 % CAPEX/rok, tj. ~250–500 Kč/kWp/rok** vč. pojištění, čištění, revizí a náhradních dílů (triangulace; mezinárodní utility benchmark ~8–12 EUR/kWp/rok).

### (d) Silová elektřina pro firmy 2026 🟡
- Spot OTE (base, roční průměry, [SpotMeter](https://www.spotmeter.cz/spotove-ceny)): 2023 ≈ 2 420; 2024 ≈ **2 140**; 2025 ≈ **2 400**; 2026 YTD (198 dní) ≈ **2 590 Kč/MWh** (≈ 96–105 EUR/MWh). Spot 2025 meziročně +15 % ([TZB-info](https://www.tzb-info.cz/ceny-paliv-a-energii/29401-spotovy-trh-s-elektrinou-v-roce-2025-vice-zapornych-hodin-presto-mezirocne-o-15-drazsi)).
- Forwardy PXE k červenci 2026: **CAL-2027 ≈ 100–111 EUR/MWh, CAL-2028 ≈ 91 EUR/MWh** ([kurzy.cz prognóza](https://zpravy.kurzy.cz/866635-prognoza-vyvoje-cen-energii-ve-trech-scenarich/), [e15](https://www.e15.cz/cena-elektriny-burza-graf-aktualne), [PXE](https://pxe.cz/cs/komoditni-trh/parc/kurzovni-listek)).
- Koncová silová cena pro firmy (fix): typicky **~2 800–3 500 Kč/MWh** (PKV uvádí ~3 000 Kč/MWh) 🟡. Pro srovnání s PPA používat **silovou cenu + vyhnuté regulované složky z bodu 1**, ne celkovou fakturu.

### (e) Přebytky / capture price 🟡
- Výkup přebytků 2025/26: fix **300–1 300 Kč/MWh** (PP 1 200 Kč/MWh), nebo **spot minus poplatek** (měsíční poplatky 39–472 Kč, případně % ze spotu) ([kupnisila.cz](https://www.kupnisila.cz/vykup-elektriny-z-fotovoltaiky-vykupni-ceny/)).
- Záporné ceny: 2024 = 315 h; **2025 = 348 h** (1 293 čtvrthodinových intervalů; od 10/2025 čtvrthodinové obchodování); minimum −5 599,90 Kč/MWh (TZB-info). 2026: leden–duben **4 % času záporně/nula**, konec dubna až **−489 EUR/MWh** v ČR ([obnovitelne.cz, 8. 5. 2026](https://www.obnovitelne.cz/clanek/4637/zaporne-ceny-opet-zauradovaly-elektrina-stala-temer-500-eur-za-mwh)); reportován i první záporný týdenní průměr realizační ceny FVE (−8,56 EUR/MWh, květen 2026) 🔶.
- Capture rate solárů: DE 2023 73 % → 2024 (I–X) **60 %** ([GEM Energy Analytics](https://gemenergyanalytics.substack.com/p/solar-capture-rates-in-2024)), 2025e ~66 % base 92,7 EUR ([Solar Data Atlas](https://www.solardataatlas.com/en/insights/solar-ppa-prices-europe)). ČR nemá veřejné číslo; trh je cenově svázán s DE → pro model přebytků použít **capture rate 55–70 % spotové base**, tj. při base ~2 400 Kč/MWh zachycená cena FVE **≈ 1 300–1 700 Kč/MWh**, s klesajícím trendem 🔶.

---

## 4. Jak to počítají ostatní poskytovatelé 🟡

| Poskytovatel | Model | Co je veřejné |
|---|---|---|
| **ČEZ ESCO** | „FVE za korunu“ (on-site PPA) + off-site PPA (pay-as-produced/pay-as-contracted) | splácení platbami za spotřebovanou zelenou elektřinu; typicky 12 let, fix vč. záruk původu; ~10 MW projektů „za 1 Kč“ ([cez.cz TZ](https://www.cez.cz/cs/pro-media/tiskove-zpravy/cez-esco-uzavrelo-svuj-prvni-off-site-ppa-kontrakt-na-dodavky-elektriny-z-konkretni-fotovoltaiky.-zakaznikem-jsou-trinecke-zelezarny-209049), [cezesco.cz](https://www.cezesco.cz/en/products/ppa)) |
| **E.ON/EG.D** | on-site PPA (referenční projekt AGC) | 15–25 let, fixace Kč/MWh dle předpokládané spotřeby; úsporu prezentují vs. „méně předvídatelná cena ze sítě“ ([eon.cz](https://www.eon.cz/byznys-energie/energie-bez-investice-stale-vice-firem-zacina-vyuzivat-ppa/)) |
| **TEDOM energie** | provozní model (2 varianty: spot / PPA) | 20 let, **indexace jen o inflaci ČSÚ**, odkup za 1 000 Kč po 20 letech, výstup po 6 letech; zdůrazňují, že na samospotřebu „nejsou vázány distribuční a další regulované poplatky“ ([tedomenergie.cz](https://www.tedomenergie.cz/fotovoltaika/fotovoltaika-bez-vlastni-investice/)) |
| **GreenBuddies** | on-site PPA | FVE v majetku GB, klient platí jen odebranou energii, „garantovaná cena nižší než od stávajícího dodavatele“, O&M nese GB ([greenbuddies.eu](https://www.greenbuddies.eu/site/power-purchase-agreement-ppa)) |
| **Solidsun (ESCO), Columbus, PP, Sunnywatt** | ESCO/PPA + výkup | úspora prezentována vs. aktuální ceník dodavatele; baterie nabízejí všichni jako doplněk (peak-shaving); konkrétní kalkulačky nezveřejňují |

Vzorec „úspora = samospotřeba × (cena dodavatele − PPA cena)“ je **standard trhu**; nikdo veřejně nepublikuje eskalaci ceny dodavatele — poctivější nástroje (interně) modelují růst ceny dodavatele 2–3 %/rok nebo dle forwardů. Kombinace s baterií se nabízí, ale do PPA ceny se většinou nepromítá — účtuje se zvlášť (služba peak-shaving) 🔶.

## 5. Diskontní sazba / IRR investora 🟡/🔶

- Regulatorní kotva: přiměřenost podpory = **IRR 8,4–10,6 %** (zákon 165/2012, § 30 — interval pro prověřování starých FVE; ukazuje, co ČR považuje za přiměřený výnos solární investice).
- AURES II (2019): utility-scale PV WACC DE 2,5–4,0 % nom.; po 2022 +100–150 b.b. ([Solar Data Atlas WACC](https://www.solardataatlas.com/en/data-solar-wacc-europe)); ČR bývá o 1–2 p.b. výš.
- Financování v ČR: banky konzervativní, chtějí zajištěné příjmy (PPA) ([solarninovinky.cz](https://www.solarninovinky.cz/modernizace-starsich-fotovoltaickych-elektraren-jak-zustat-ekonomicky-zivotaschopni-i-po-roce-2030/)); NRB bezúročné úvěry do 3 mil. Kč (vyčerpáno 9/2025).
- **Praktické pásmo pro C&I on-site PPA investora 2025/26: nominální WACC ~6–9 %, požadované equity IRR ~8–12 %** (triangulace 🔶). Pro kalkulačku doporučen default diskont 7–8 % nominálně, citlivost 6–10 %.

---

## Klíčové dopady pro kalkulačku (shrnutí)

1. **„Cena od dodavatele“ v rozdílu musí být jen vyhnutelná část**: silová elektřina + použití sítí VN (~83–106 Kč/MWh 2026) + systémové služby (164,24) — nikoliv plná koncová cena. Jinak se úspora nadhodnocuje o fixní platby (RK, jistič, OTE) a o daň.
2. **POZE**: 2026 = 0; 2025 = 495 Kč/MWh jen při využití rezervovaného příkonu < ~2 809 h/rok, jinak 0. Do budoucna parametr (default 0). Lokální spotřeba POZE nehradí (od 2022).
3. **Daň z elektřiny (28,30 Kč/MWh)** u FVE >30 kW není úsporou — PPA dodávka jí podléhá také.
4. Indexace PPA X %/rok odpovídá praxi (TEDOM: CPI; ČEZ ESCO: fix) — přidat i eskalaci ceny dodavatele jako samostatný parametr, jinak se srovnání za 15–20 let vychýlí.
5. Přebytky: patří investorovi; zachycená cena FVE ≈ 55–70 % spotové base a klesá (2025: 348 záporných hodin; jaro 2026 rekordy) — pro výnosy investora z přetoků počítat konzervativně (~1 300–1 700 Kč/MWh, s trendem dolů), případně sdílení přes EDC na další OPM klienta.
6. DPH: u plátců neutrální — počítat vše bez DPH.

Hlavní nejistoty: finální hodnoty výměru 13/2025 (rešerše měla návrh z 30. 10. 2025, odchylka finálu bývá do jednotek %), přesný výkonový limit osvobození od daně z elektřiny (30 vs 50 kW — převažuje 30 kW), CZ on-site PPA ceny a WACC (jen triangulace — trh čísla nepublikuje).
