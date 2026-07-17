# Rešerše: regulované ceny distribuce VN/VVN (2026) a nová tarifní struktura od 2027

> Součást auditu kalkulátorů 16. 7. 2026 (viz [README](README.md)). Vše níže ověřeno
> primárně z PDF dokumentů ERÚ (cenové výměry, koncepce, manuál). Legenda jistoty:
> ✅ = ověřeno primárním zdrojem (dokument ERÚ), 🟡 = sekundární zdroj, ❌ = nedohledáno / neexistuje.

---

## ČÁST A — Stará struktura, rok 2026

Závazný předpis: **Cenový výměr ERÚ č. 13/2025 z 28. 11. 2025** (Energetický regulační věstník 17/2025), ve znění CV 15/2025 (29. 12. 2025 – pouze vynulování POZE) a CV 1/2026 (28. 4. 2026 – pouze technická úprava bodu 4.34 pro LDS a výkazů, cen RK se nedotýká ✅). PDF: https://eru.gov.cz/sites/default/files/obsah/prilohy/erv172025.pdf (stránka: https://eru.gov.cz/energeticky-regulacni-vestnik-172025)

### A1+A2) Ceny za rezervovanou kapacitu 2026 (bod 4.18 CV 13/2025) ✅

| Distributor | Hladina | Měsíční cena za **roční** RK [Kč/kW/měs] | Měsíční cena za **měsíční** RK [Kč/kW/měs] |
|---|---|---|---|
| **ČEZ Distribuce** | **VVN** | **117,432** | **131,036** |
| **ČEZ Distribuce** | **VN** | **252,565** | **281,823** |
| EG.D | VVN | 110,826 | 122,223 |
| EG.D | VN | 230,551 | 254,260 |
| PREdistribuce | VVN | 129,580 | 143,087 |
| PREdistribuce | VN | 271,093 | 299,351 |

(Ve výměru uvedeno v Kč/MW/měsíc: ČEZ VN 252 565 / 281 823 atd.)

**Verdikt k naseedovaným hodnotám v appce:**
- ❗ **237,31 Kč/kW/měsíc NENÍ hodnota 2026, ale 2025.** Ověřeno proti CV č. 11/2024 (věstník 13/2024, zrcadlo na webu PRE: https://www.predistribuce.cz/Files/ceny/cenove-rozhodnuti-eru-c-132024/): ČEZ VN roční RK 2025 = 237 309 Kč/MW/měs ✅. Pro 2026 má být **252,565 Kč/kW/měs** (roční ekvivalent 3 030,78 Kč/kW/rok, nikoli 2 847,72).
- ❗ **VVN není null** – pro ČEZ 2026 je roční RK **117,432 Kč/kW/měs**, měsíční RK 131,036 ✅.
- Pozn.: říjnový návrh výměru (VKP 30. 10. 2025) měl pro ČEZ i EG.D shodné hodnoty s finálem, u PRE se finál lišil — používat jen finální CV 13/2025.

### A3) Jak se počítá překročení — POZOR, tři různé věci ✅

1. **Překročení rezervované KAPACITY** (bod 4.24): platba = **1,5 × měsíční cena za měsíční RK** (přepočtená na kW) **za každý kW nejvyššího překročení** sjednané RK **čtvrthodinovým maximálním odebraným výkonem** v kalendářním měsíci; vyhodnocuje se měsíčně. → ČEZ 2026: **VN 422,73 Kč/kW, VVN 196,55 Kč/kW**.
2. **Překročení rezervovaného PŘÍKONU** (dle smlouvy o připojení; body 4.35/4.36): platba = **4 × měsíční cena za měsíční RK** za každý kW nejvyššího překročení čtvrthodinovým maximem; měsíčně. → ČEZ 2026: **VN 1 127,29 Kč/kW, VVN 524,14 Kč/kW**. (Při současném překročení v předávacím místě i místě připojení se účtuje jen vyšší z plateb.)
3. **Překročení rezervovaného VÝKONU** (bod 4.38) = **dodávka DO sítě** (směr výroba), pevné ceny 2026: **VVN 521, VN 1 108, NN 1 131 Kč/kW/měs** ✅ (potvrzeno i webem ČEZ Distribuce: https://www.cezdistribuce.cz/cs/pro-zakazniky/potrebuji-vyresit/ceny-a-podminky/ceny-pri-prekroceni-rezervovaneho-prikonu-a-vykonu/prekroceni-rezervovaneho-vykonu — „když výrobní zdroj dodá do distribuční sítě vyšší množství elektřiny, než bylo sjednáno“, vyhodnocení dle čtvrthodinového maxima **dodané** elektřiny).

❗ **Nástroj má chybu: seedy 1 108 (VN) a 521 (VVN) jsou ceny za překročení rezervovaného VÝKONU (přetoky do sítě), ne kapacity.** Pro peak shaving (odběrová špička) je relevantní č. 1 (překročení RK, 1,5×), případně č. 2 (překročení příkonu, 4×). Náhoda, že 4× měsíční RK VVN (524) ≈ 521, je matoucí, ale mechanismus je jiný.

Výjimka ✅: cena za překročení RK se neuplatní u provozovatele zařízení pro ukládání elektřiny / výrobce / zákazníka, který nehradí RK podle § 54a odst. 2 vyhlášky o Pravidlech trhu s elektřinou (režim „akumulace 1. kategorie“ dle novely od 1. 10. 2025 🟡 – samostatná baterie pak RK vůbec neplatí).

### A4) Změny RK v průběhu roku ✅ (bod 4.18–4.21)
- Roční a měsíční RK **lze kombinovat** v daném roce.
- Roční RK lze **změnit v průběhu roku** (účtuje se od měsíce, pro který byla změna uplatněna), ale **snížit** ji lze až **po 12 měsících od poslední změny** (nebo při změně zákazníka v předávacím místě).
- Měsíční RK se sjednává **do posledního pracovního dne předchozího měsíce** (u RDS; u smlouvy o sdružených službách do předposledního pracovního dne).

### A5) EG.D a PRE — ano, viz tabulka výše ✅ (stejný výměr platí pro všechny tři RDS; ceny se liší po distributorech).

---

## ČÁST B — Nová tarifní struktura (NTS) od 2027

Primární zdroje (vše ERÚ, publikováno 21.–25. 5. 2026 na https://eru.gov.cz/inovace-tarifni-struktury-v-ramci-prenosove-soustavy-distribucni-soustavy-na-napetovych-hladinach):
- **Informativní podoba cenového výměru** („CV 13/2025 pro rok 2026 podle principů inovace tarifní struktury“): https://eru.gov.cz/sites/default/files/obsah/prilohy/cv-vvn-vn-26-its260521.pdf ✅
- **Koncepce** „Efektivní využívání PS a DS na hladinách VVN a VN…“: https://eru.gov.cz/sites/default/files/obsah/prilohy/efektivni-vyuzivani-siti-vvn-vn260522.pdf ✅
- **Manuál pro zákazníka**: https://eru.gov.cz/sites/default/files/obsah/prilohy/manual-pro-zakaznika260522.pdf ✅
- Kalkulátory (xlsx) pro zákazníky/výrobce/LDS na téže stránce (vhodné pro křížovou validaci nástroje).

### B1) Stav k červenci 2026 ✅
- **Start 1. 1. 2027 platí, neodloženo** (tisková zpráva ERÚ 25. 5. 2026: https://eru.gov.cz/inovace-tarifni-struktury-na-hladinach-vn-vvn-zefektivni-vyuziti-soustav-usetri-az-3-miliardy-rocne; týká se ~25 tis. odběrných míst VN/VVN, očekávané uvolnění ~3,3 GW příkonu, úspora 2–3 mld. Kč/rok).
- Publikovaný výměr je **jen informativní** (závěrečné ustanovení 25.2: „Jedná se pouze o informativní cenový výměr… Principy nabydou účinnosti od 1. ledna 2027 a budou vydány v novém cenovém výměru pro rok 2027.“). **Závazný CV pro 2027 vyjde na podzim 2026** (standardní termín ERÚ ~konec listopadu). **Parametrizace koeficientu akumulace projde veřejnou konzultací v říjnu 2026** ✅.
- Novela vyhlášky č. 408/2015 Sb. (Pravidla trhu) pro NTS je dle koncepce **již přijata** ✅ (od 2027 ruší kategorie výrobců 1/2 na VN/VVN). NN se změna netýká (piloty 2028, šířeji 2030).

### B2) Struktura plateb — model nástroje je SPRÁVNĚ ✅
- Složky se jmenují **„cena za rezervovaný příkon“ (RP)** a **„cena za maximální odebraný výkon“** (= maximální čtvrthodinový elektrický výkon odebraný ze soustavy v kalendářním měsíci).
- Existují **tarify T1 a T2**; bod (4.8) informativního CV: „V každém předávacím místě je za zúčtovací období účtována **vždy nižší ze součtů plateb** z ceny za RP a ceny za max. odebraný výkon podle tarifu T1 nebo T2.“ Volbu provádí provozovatel **automaticky po měsících**, bez součinnosti zákazníka. → vzorec `min(RP×T1_kap + M×T1_šp, RP×T2_kap + M×T2_šp)` odpovídá. Poměr složek: v T1 je cena za maximum 10 % ceny za RP, v T2 obráceně.
- **Naseedované hodnoty nástroje pro ČEZ přesně sedí** s informativním CV (body 4.2 a 4.3), Kč/MW/měs:

| DSO | Hladina | RP T1 | RP T2 | Max T1 | Max T2 | Překročení RP [Kč/kW/měs] |
|---|---|---|---|---|---|---|
| ČEZ | VVN | 96 862 | 11 586 | 9 686 | 115 862 | 387 |
| ČEZ | VN | **190 133** | **22 743** | **19 013** | **227 429** | **761** |
| EG.D | VVN | 87 770 | 10 499 | 8 777 | 104 987 | 351 |
| EG.D | VN | 181 386 | 21 697 | 18 139 | 216 967 | 726 |
| PRE | VVN | 109 073 | 13 047 | 10 907 | 130 470 | 436 |
| PRE | VN | 196 298 | 23 480 | 19 630 | 234 804 | 785 |
| ČEPS (přenos) | – | 95 450 | 11 417 | 9 545 | 114 173 | 382 |

  ⚠️ Jde o **informativní hodnoty „jako by NTS platila v 2026“** – pro 2027 budou v závazném výměru jiné (nástroj je správně označuje jako modelové). Příklad z manuálu ERÚ (VN, RP 350 kW, Pmax 300 kW) používá přesně tato čísla.
- **Pozor na sémantiku RP**: RP **není roční produkt** – je to hodnota **ze smlouvy o připojení** (dlouhodobá). Nelze ji „optimalizovat po měsících“ jako RK; snížení jen změnou smlouvy o připojení (znovu-navýšení zpoplatněno dle přílohy 2 vyhlášky č. 16/2016 Sb.). V lednu 2027 se převezme hodnota ze stávající smlouvy. Při změně RP v průběhu měsíce se účtuje poměrně po dnech (4.10).
- Existuje i **volitelná jednosložková cena za službu sítí** (Kč/MWh; informativně ČEZ VN 5 555,18 / VVN 2 845,96; ČEPS 2 793,55), vhodná při využití RP < 600 h/rok, závazek 12 měsíců.

### B3) Překročení rezervovaného příkonu v NTS ✅
- Pevná cena v Kč/kW/měs přímo ve výměru (tabulka výše; ČEZ VN **761**, VVN **387** — seedy sedí). Vyhodnocení **měsíčně**, „na každý kW **nejvyššího překročení** sjednaného RP **maximálním čtvrthodinovým odebraným výkonem**“. → `max(0, M − RP) × sazba` odpovídá ✅. Účtuje se vedle platby T1/T2 (platba za maximum se počítá z plného M, nekapuje se na RP). Manuál: cena „v obdobné výši jako dříve, uplatňována stejným způsobem“, nově přímo konkrétní hodnotou.

### B4) KRITICKÉ — akumulace v NTS: mechanismus existuje, ale funguje JINAK než v nástroji

Část dvacátá čtvrtá informativního CV (extrahováno doslovně) ✅:

> **Hodnota odebraného výkonu = max(OVst − OVst × Koeficient AKU; 0)** — tj. každá čtvrthodina diagramu odebraného výkonu předávacího místa se násobí (1 − K_AKU).
>
> Koeficient AKU: a) při podílu **množství odebrané a zpětně dodané elektřiny k množství odebrané elektřiny ze soustavy** za zúčtovací období ≤ U1 → K = 0; b) ≥ U2 → K = 1; c) mezi → **K = (podíl − U1)/(U2 − U1)** lineárně.
>
> Předběžné hodnoty: **PS a VVN: U1 = 0,6; U2 = 0,7** · **VN: U1 = 0,6; U2 = 0,75** · **přečerpávací VE: U1 = 0,5; U2 = 0,7**.

Koncepce (str. 9–10) totéž slovně: pod spodní hranicí plná platba za maximální odebraný výkon, nad horní hranicí **platba za maximální odebraný výkon se nehradí vůbec**; **cena za RP se hradí standardně** (bez slevy). Dřívější varianta vázaná na služby výkonové rovnováhy byla opuštěna. Do budoucna ERÚ zvažuje speciální tarif úložišť s flexibilním/negarantovaným příkonem; neslučitelné s provozní podporou z kapacitních mechanismů.

**Porovnání s předpoklady nástroje:**

| Aspekt | Nástroj | ERÚ (návrh) | Verdikt |
|---|---|---|---|
| Prahy U1/U2 | 0,60→0,75 (VN), 0,60→0,70 (VVN) | 0,6/0,75 (VN), 0,6/0,7 (VVN+PS) | ✅ sedí přesně |
| Definice „účinnosti“ | vybitá/nabitá energie **baterie** za měsíc | podíl **zpětně dodané do soustavy / odebrané ze soustavy** elektřiny **za celé předávací (fakturační) místo** za zúčtovací období | ❗ liší se — měří se na elektroměru vůči soustavě, ne uvnitř baterie |
| Na co se sleva uplatní | na složku „špička“ **do výše nabíjecího výkonu baterie** | násobí se **celý čtvrthodinový diagram odebraného výkonu** faktorem (1−K); žádný strop nabíjecím výkonem v návrhu není | ❗ liší se |
| Důsledek pro peak shaving | sleva i pro baterii uvnitř odběru závodu | u odběratele s vlastní spotřebou je podíl zpětně dodané/odebrané ≈ 0 → **K = 0 → žádná sleva**; benefit reálně cílí na samostatná (stand-alone) úložiště a PVE | ❗ zásadní rozdíl |
| Závaznost | – | „předběžná očekávaná hodnota“; **konečná podoba projde VKP v říjnu 2026** (vč. úpravy pro kombinaci s výrobnou) | ⚠️ ještě se může změnit |

Terminologie: výměr používá „Koeficient AKU“; „účinnost“ používá koncepce („dosažená účinnost odvozená od množství elektřiny odebrané a zpětně dodané do soustavy a množství odebrané elektřiny“); média („účinnost odběrného místa“, např. https://www.obnovitelne.cz/clanek/4713/dopad-nove-tarifni-struktury-bateriova-uloziste-se-vyhnou-vysokym-poplatkum 🟡). Pojem „koeficient akumulace“ v dokumentech ERÚ v této podobě nefiguruje.

Dále: volba T1/T2 se posuzuje **až po** úpravě diagramu koeficientem AKU (4.8 + část dvacátá třetí); překročení RP se ale vyhodnocuje z neupraveného měření. Pořadí úprav diagramu: 1) služby výkonové rovnováhy v záporném směru, 2) technologická vlastní spotřeba výroben (§ 53a, koeficienty TVS dle typu zdroje), 3) koeficient AKU.

### B5) Konkrétní čísla NTS
Viz tabulka v B2 (kompletní pro ČEPS + 5 DSO vč. UCED Chomutov a SV servisní) + překročení + jednosložkové ceny. Vše z informativního CV ✅; závazné hodnoty 2027 vyjdou v CV na podzim 2026.

---

## Shrnutí doporučených oprav nástroje
1. **Stará struktura 2026, ČEZ VN**: roční RK 237,31 → **252,565 Kč/kW/měs** (3 030,78 Kč/kW/rok); doplnit měsíční RK 281,823. Hodnota 237,31 je rok 2025.
2. **VVN doplnit**: roční RK **117,432**, měsíční 131,036 Kč/kW/měs.
3. **Překročení ve staré struktuře přepracovat**: 1 108/521 jsou ceny za překročení rezervovaného **výkonu** (dodávka do sítě). Pro odběr: překročení RK = **1,5 × měsíční cena měsíční RK** (VN 422,73; VVN 196,55 Kč/kW), překročení příkonu = **4 ×** (VN 1 127,29; VVN 524,14 Kč/kW).
4. **NTS T1/T2 + překročení**: hodnoty i vzorec min() + max(0, M−RP) jsou správně (zdrojem je informativní CV ERÚ, 5/2026).
5. **NTS akumulace přepsat**: koeficient se počítá z toku na předávacím místě (zpětně dodaná/odebraná), sleva násobí celý diagram (1−K) a snižuje jen platbu za maximální odebraný výkon; pro baterii uvnitř odběru závodu bez přetoků vychází sleva nulová. Prahy U1/U2 ponechat, označit jako předběžné (VKP 10/2026, závazně v CV pro 2027).

**Hlavní zdroje**: [CV 13/2025 finál (ERV 17/2025)](https://eru.gov.cz/sites/default/files/obsah/prilohy/erv172025.pdf) · [informativní CV dle NTS](https://eru.gov.cz/sites/default/files/obsah/prilohy/cv-vvn-vn-26-its260521.pdf) · [koncepce NTS](https://eru.gov.cz/sites/default/files/obsah/prilohy/efektivni-vyuzivani-siti-vvn-vn260522.pdf) · [manuál pro zákazníka](https://eru.gov.cz/sites/default/files/obsah/prilohy/manual-pro-zakaznika260522.pdf) · [stránka ERÚ k ITS](https://eru.gov.cz/inovace-tarifni-struktury-v-ramci-prenosove-soustavy-distribucni-soustavy-na-napetovych-hladinach) · [TZ ERÚ 25. 5. 2026](https://eru.gov.cz/inovace-tarifni-struktury-na-hladinach-vn-vvn-zefektivni-vyuziti-soustav-usetri-az-3-miliardy-rocne) · [CV 11/2024 pro 2025 (zrcadlo PRE)](https://www.predistribuce.cz/Files/ceny/cenove-rozhodnuti-eru-c-132024/) · [ČEZ – překročení rez. výkonu](https://www.cezdistribuce.cz/cs/pro-zakazniky/potrebuji-vyresit/ceny-a-podminky/ceny-pri-prekroceni-rezervovaneho-prikonu-a-vykonu/prekroceni-rezervovaneho-vykonu) · [změnový CV 15/2025 (POZE=0)](https://eru.gov.cz/eru-vydal-zmenovy-cenovy-vymer-kterym-upravuje-regulovane-ceny-na-rok-2026) · [CV 1/2026 (ERV 2/2026)](https://eru.gov.cz/sites/default/files/obsah/prilohy/erv022026.pdf) · sekundárně [obnovitelne.cz k bateriím](https://www.obnovitelne.cz/clanek/4713/dopad-nove-tarifni-struktury-bateriova-uloziste-se-vyhnou-vysokym-poplatkum), [TZB-info k NTS](https://energetika.tzb-info.cz/energeticka-politika/29276-nova-tarifni-struktura-2027-v-hlavni-roli-prubehove-mereni-a-flexibilita).

Nedohledáno ❌: obsah změnového CV 3/2026 (19. 6. 2026, elektro) — s vysokou pravděpodobností se netýká RK (šlo by o mediálně sledovanou změnu), doporučuji ale před nasazením zkontrolovat na https://eru.gov.cz/cenove-vymery; a rozbor SVSE k NTS (web svse.cz se v prohledaných výsledcích neobjevil).
