# Metodika výpočtu – Peak shaving (v1, návrh)

Navazuje na `docs/SPEC-nabidkovac.md`. Tohle je čistě **metodika/vzorce**, ne kód – slouží jako podklad pro další Claude Code prompt, až ji společně potvrdíme. Obsahuje i pár předpokladů, které jsem musel udělat a **potřebují tvoje potvrzení/opravu** (označeno ⚠️).

---

## 1. Princip

Zákazník platí distributorovi za **rezervovanou kapacitu** (sjednaný max. příkon/výkon, Kč/kW/rok) a pokud ji v daném měsíci překročí, platí navíc **pokutu za překročení** (Kč/kW, podle nejvyššího naměřeného 15minutového překročení v tom měsíci). Baterie srazí špičky odběru, takže:

- (a) se sníží nebo úplně zmizí měsíční překročení → ušetří se pokuty,
- (b) jde nasmlouvat nižší rezervovaná kapacita natrvalo → ušetří se roční paušál.

Nástroj má pro daného zákazníka najít z katalogu baterii (a případně počet kusů), která přinese nejrychlejší návratnost investice.

**Rozsah: peak shaving řešíme jen pro zákazníky na VN a VVN, ne na NN** (potvrzeno). Důvod je i praktický, ne jen byznysový: od 1. 1. 2027 mění ERÚ celou strukturu zpoplatnění kapacity na VN/VVN (viz kap. 4.6) – u NN se nic podobného zatím neděje (reforma tam přijde nejdřív 2028–2030, a i pak jen postupně), takže NN mimo scope zjednodušuje i dřívější rozhodnutí o zobrazování let 2026/2027.

---

## 2. Vstupní data

| Vstup | Zdroj | Poznámka |
|---|---|---|
| 15minutový profil odběru (kW) za min. 1 rok | CSV nahrané OZ | jednotná struktura (potvrzeno dřív) |
| Distributor (ČEZ Distribuce / EG.D / PRE distribuce) | OZ vybere | určuje sazby |
| Napěťová hladina (VN/VVN – NN appka pro peak shaving nenabízí) | OZ vybere/odvodí se z profilu | sazby se liší podle hladiny i podle roku (viz 4.6) |
| Aktuální sjednaná rezervovaná kapacita (kW) | OZ zadá ručně | z faktury, zatím bez automatické extrakce |
| Katalog baterií (výkon kW, kapacita kWh, cena) | tabulka `technologie` | typ = `baterie` |

---

## 3. Doplnění datového modelu

Do `SPEC-nabidkovac.md` (kap. 4) je potřeba přidat:

### 3.1 Nová tabulka `sazby_distributoru`

Musí unést **dvě různé tarifní struktury** (2026 vs. 2027, viz kap. 4.6) – proto ne pevné sloupce pro ceny, ale typ struktury + flexibilní JSONB s parametry dané struktury (stejný princip jako `vypoctova_nastaveni`).

- `id`
- `distributor` (`cez`, `egd`, `pre`)
- `napetova_hladina` (`vn`, `vvn`) – NN se nezavádí, appka pro NN peak shaving nenabízí
- `struktura_tarifu` (`stara_2026` / `nova_2027`)
- `parametry` (JSONB):
  - pro `stara_2026`: `{cena_rezervovana_kapacita_kc_kw_rok, cena_prekroceni_kc_kw}`
  - pro `nova_2027`: `{t1_kapacita_kc_kw_mesic, t1_spicka_kc_kw_mesic, t2_kapacita_kc_kw_mesic, t2_spicka_kc_kw_mesic, sazba_prekroceni_kc_kw_mesic}` – naplněno modelovými/informativními hodnotami (viz kap. 4.6), s příznakem `je_modelovy_odhad = true`, dokud ERÚ nevydá závazné cenové rozhodnutí (listopad 2026)
- `platne_od`, `platne_do` (sazby se mění každý rok, potřebujeme historii kvůli zpětné dohledatelnosti)

**Dohledáno pro `stara_2026`, všechny ceny bez DPH:**

**Pokuta za překročení – vypadá to na jednotnou celostátní regulovanou sazbu (stanovuje ERÚ, ne jednotliví distributoři), stejná čísla vyšla nezávisle pro ČEZ i EG.D:**
- VN: **1 108 Kč/kW/měsíc**
- VVN: **521 Kč/kW/měsíc**
- Účtuje se dle nejvyšší naměřené 15minutové hodnoty překročení v daném měsíci. ⚠️ Nemám nezávisle potvrzeno, že je to stejné i u PRE distribuce – je to sice regulovaná cena (tzn. pravděpodobně ano), ale doporučuju před nasazením ověřit.

**Rezervovaná kapacita (roční sjednání) – tady se distributoři liší, protože odráží náklady jejich vlastní sítě:**
| Distributor | VN | VVN |
|---|---|---|
| ČEZ Distribuce | 237,31 Kč/kW/měsíc (potvrzeno, přímý zdroj) – appka na tohle jde spustit hned | – nedohledáno |
| PRE distribuce | 170,12 Kč/kW/měsíc (nalezeno přes vyhledávání, ne z přímého PDF – ⚠️ doporučuju ověřit) | 69,76 Kč/kW/měsíc (stejně) |
| EG.D | – nepodařilo se spolehlivě dohledat (PDF ceníky se přes web nedaly strojově přečíst) | – nedohledáno |

Jak jsme se domluvili: jedeme naostro zatím **jen s ČEZ Distribuce**, ostatní řádky zůstanou v tabulce prázdné/needitované, dokud je kolega nedoplní přes admin rozhraní.

### 3.2 Úprava `technologie`
Pro `typ = baterie` musí být vyplněné **obě** pole zároveň: `vykon_kw` (kolik kW umí okamžitě dodat) i `kapacita_kwh` (kolik energie pojme) – ne jen jedno z nich, jak bylo původně navrženo jako "buď/nebo".

---

## 4. Algoritmus

### 4.1 Zjištění současného stavu (bez baterie)
Z ročního profilu spočítat pro každý kalendářní měsíc nejvyšší 15minutovou hodnotu. Kde je vyšší než sjednaná rezervovaná kapacita, je to překročení = `(měsíční_max - rezervovaná_kapacita)`. Součet `překročení_kW × cena_prekroceni_kc_kw` přes všechny měsíce = **současná roční cena za překročení**. K tomu současná roční cena za rezervaci = `rezervovaná_kapacita × cena_rezervovana_kapacita_kc_kw_rok`. Součet = **výchozí roční náklad**, se kterým se bude porovnávat stav s baterií.

### 4.2 Simulace baterie (pro danou variantu: konkrétní produkt z katalogu × počet kusů 1, 2, 3...)
Pro zvolený **cílový strop** `T` (kandidát na novou rezervovanou kapacitu) projet celý rok interval po intervalu (15 min, dle granularity vstupních dat):

- Pokud `odběr > T`: baterie dodává `min(odběr − T, celkový_výkon_kW)`. Odečte se odpovídající energie z aktuálního stavu nabití (kWh za 15 min = kW × 0,25 h). Pokud baterii dojde kapacita dřív, než odběr klesne pod `T`, cíl `T` se pro tuhle variantu **nepodařilo udržet** → zkusit vyšší `T`.
- Pokud `odběr ≤ T`: baterie se dobíjí, max. rychlostí = celkový výkon kW (potvrzeno: nabíjecí výkon = vybíjecí výkon, jedno pole v katalogu), omezená zbývající volnou kapacitou a rozdílem `T − odběr` (nedobíjí se z ničeho navíc, jen z rezervy pod stropem).
- Kapacita a účinnost se pro v1 berou 1:1 (bez ztrát, bez DoD limitu) – zjednodušení, které jsme si odsouhlasili.
- Všechny peněžní výpočty (rezervace, překročení, cena baterie) jsou **bez DPH** (potvrzeno).

### 4.3 Hledání minimální dosažitelné rezervované kapacity
Pro danou variantu baterie binárním vyhledáváním najít nejnižší `T`, při kterém simulace z 4.2 projde celý rok bez jediného překročení. To je **navrhovaná nová rezervovaná kapacita** pro tuhle variantu baterie.

### 4.4 Roční úspora dané varianty
`úspora = výchozí_roční_náklad (4.1) − (T × cena_rezervovana_kapacita_kc_kw_rok)` (po baterii je díky 4.3 překročení nulové, takže odpadá i pokuta).

### 4.5 Návratnost a výběr
`návratnost_let = cena_baterie_celkem (počet_kusů × cena_kc) / úspora`. Spočítat pro všechny kombinace (každý produkt v katalogu typu `baterie` × rozumný rozsah počtu kusů, např. 1–5, dokud přírůstek nedává smysl) a vybrat variantu s **nejkratší návratností** (potvrzeno dřív).

Pokud žádná varianta nedosáhne návratnosti do **5 let** (výchozí hodnota pole `max_navratnost_roky_peak_shaving` ve `vypoctova_nastaveni`, editovatelné vedením/adminem), nástroj vrátí nejlepší nalezenou variantu, ale označenou jako "nedoporučeno" – nezmizí úplně, jen se OZ jasně ukáže, že návratnost přesahuje firemní práh.

### 4.6 Rok 2026 vs. 2027 (tarifní reforma ERÚ na VN/VVN)

Od 1. 1. 2027 mění ERÚ způsob zpoplatnění kapacity na VN a VVN (týká se ~25 000 velkoodběratelů, NN se to netýká). Je to jiná **struktura** výpočtu, ne jen jiná čísla do stejného vzorce:

- **2026 (`stara_2026`, popsáno v kap. 4.1–4.5):** rezervovaná kapacita (Kč/kW/rok) + pokuta za měsíční překročení.
- **2027 (`nova_2027`):** stará platba za "rezervovanou kapacitu" i její překročení úplně mizí. Nahrazuje ji dvousložkový model: **rezervovaný příkon** (RP, hodnota ze smlouvy o připojení) a **naměřené maximum** (M, nejvyšší čtvrthodinový odběr za daný měsíc). ERÚ zavádí **dva tarify, T1 a T2** – T1 má drahý paušál (RP) a levnou špičku (M), T2 má levný paušál a drahou špičku. **Zákazník si tarif nevybírá** – distributor spočítá oba a každý měsíc automaticky vyfakturuje ten levnější (ověřeno nezávisle, viz Zdroje). Navíc zůstává **penalizace za překročení sjednaného RP** – pokud naměřené M přesáhne RP, platí se extra sankce ve výši 4× sazba T1-kapacita.

  **Modelové/informativní hodnoty (bez DPH), zdroj: informativní cenový výměr ERÚ, ověřeno nezávisle proti veřejnému příkladu na Volteon.cz – čísla sedí na desítky korun, ale nejsou finální, ERÚ vydá závazné cenové rozhodnutí až v listopadu 2026:**

  | Hladina | Tarif | Sazba za RP (Kč/kW/měsíc) | Sazba za M (Kč/kW/měsíc) |
  |---|---|---|---|
  | VN | T1 | 190,133 | 19,013 |
  | VN | T2 | 22,743 | 227,429 |
  | VVN | T1 | 96,862 | 9,686 |
  | VVN | T2 | 11,586 | 115,862 |

  Penalizace za překročení RP (4× T1-kapacita): **VN 761 Kč/kW/měsíc**, **VVN 387 Kč/kW/měsíc**.

  **Vzorec pro měsíční náklad:** `min(RP × T1_kapacita + M × T1_špička, RP × T2_kapacita + M × T2_špička) + max(0, M − RP) × sazba_prekroceni`. Roční náklad 2027 = součet za 12 měsíců.

  **Baterie a simulace se nemusí přeprogramovávat.** Protože RP je v obou tarifech zpoplatněné kladně, je vždy výhodné mít RP co nejnižší, dokud se tím nespustí penalizace za překročení – takže platí přesně stejná logika jako v kap. 4.3: baterie hledá **minimální udržitelné `T`** (nová RP), při kterém M nikdy nepřekročí `T`. Pro rok 2027 se stejný výsledek simulace (nová RP + měsíční maxima po baterii) jen dosadí do vzorce výše místo do vzorce z kap. 4.4. Žádná nová fyzika baterie, jen jiný přepočet na Kč.

  ⚠️ Do finálního cenového rozhodnutí ERÚ (listopad 2026) appka u roku 2027 zobrazí tahle čísla jako **"modelový odhad, ne finální cena"** – jakmile ERÚ vydá závazné hodnoty, stačí přepsat řádek v `sazby_distributoru`, žádná přestavba kódu.

### 4.7 Vysvětlení T1/T2 pro OZ a zákazníka

I když si zákazník tarif nevybírá, appka pro rok 2027 v `popis_json` uvede i **kolik měsíců v roce (po nasazení baterie) vyjde levněji T1 a kolik T2**, plus jednoduché vysvětlení, které OZ může zákazníkovi říct:

- **T1 (drahý paušál, levná špička)** – typicky vyjde levněji v měsících, kdy provoz jede naplno a naměřené maximum se blíží sjednanému rezervovanému příkonu (orientačně nad ~80 % využití RP).
- **T2 (levný paušál, drahá špička)** – vyjde levněji v měsících s utlumeným provozem nebo když si zákazník drží velkou rezervu "pro jistotu" a maximum je výrazně pod RP.

Baterie tím, že vyhlazuje odběr blíž ke zvolenému RP, typicky tlačí zákazníka směrem k T1 (a zároveň umožňuje mít nižší RP, takže i T1 vyjde levněji než bez baterie).

### 4.8 Koeficient AKU – sleva pro bateriová úložiště (⚠️ nepotvrzený předpoklad, optimistický odhad)

ERÚ zavádí pro bateriová úložiště na VN/VVN dodatečnou slevu na složku za naměřené maximum (M), aby reforma nezničila ekonomiku akumulace. Mechanismus je nezávisle potvrzený (Petr Foitl, Solar Global/AKU-BAT, přímo se podílel na vyjednání), ale **přesná metodika výpočtu "účinnosti odběrného místa" pro čistě peak-shavingovou baterii bez exportu do sítě není ověřená** – bereme ji jako optimistický předpoklad, dokud to neprojdeme s manuálem ERÚ.

**Prahy (potvrzeno nezávisle, VN):**
- U1 = 60 % účinnost → sleva 0 %
- U2 = 75 % účinnost (VN) / 70 % účinnost (VVN) → sleva 100 %
- Mezi U1 a U2 sleva roste lineárně.
- Sleva se uplatňuje **jen do výše nabíjecího výkonu baterie** (zbytek naměřeného maxima nad tímto výkonem se platí za plnou sazbu).

**Předpoklad (nepotvrzeno, bereme jako optimistický odhad):** účinnost = poměr energie vybité baterií (kryjící špičky) k energii nabité do baterie **v daném měsíci**, tedy `ucinnost_mesic = energie_vybito_kwh / energie_nabito_kwh` – přímo ze simulace baterie (kap. 4.2), žádná nová fyzika navíc.

```
koeficient_aku = 0                                                    když ucinnost ≤ U1
koeficient_aku = (ucinnost − U1) / (U2 − U1)                          když U1 < ucinnost < U2
koeficient_aku = 1                                                    když ucinnost ≥ U2

M_kryto_baterii = min(M, celkovy_nabijeci_vykon_baterie)
M_zbytek = M − M_kryto_baterii

nakl_spicka_T1 = M_zbytek × T1_špička + M_kryto_baterii × T1_špička × (1 − koeficient_aku)
nakl_spicka_T2 = M_zbytek × T2_špička + M_kryto_baterii × T2_špička × (1 − koeficient_aku)

mesicni_naklad = min(RP × T1_kapacita + nakl_spicka_T1, RP × T2_kapacita + nakl_spicka_T2) + max(0, M − RP) × sazba_prekroceni
```

Do `sazby_distributoru.parametry` (`nova_2027`) přibývají pole `u1_ucinnost` (0,60) a `u2_ucinnost` (0,75 pro VN, 0,70 pro VVN). Výstup (`popis_json`) u roku 2027 dostane i `predpoklad_aku_neoverovany: true` a měsíční průměrnou účinnost/slevu, ať OZ vidí, jak moc na tomhle předpokladu nabídka staví.

**Další zjištění, zatím mimo scope v1:**
- Od 2028 podmínka pro čerpání slevy na VN/VVN: zákazník musí přijmout **negarantovaný (flexibilní) rezervovaný příkon** – distributor smí v krizi nabíjení baterie na dálku omezit. Stojí za zmínku OZ zákazníkovi, ale nepočítáme s tím ve vzorci.
- Kombinace se službami výkonové rovnováhy (SVR) – zvýšený odběr při poskytování záporné regulační energie se nezapočítává do zpoplatněného maxima. Vyžaduje samostatnou certifikaci/účast na trhu s flexibilitou, do peak shaving v1 nedáváme.

---

## 5. Výstup (`navrhovana_reseni`, `typ_reseni = peak_shaving`)

`popis_json` bude obsahovat: doporučený produkt + počet kusů, nová navrhovaná rezervovaná kapacita/rezervovaný příkon, cena baterie, návratnost v letech, a **zvlášť ekonomiku pro rok 2026 a rok 2027** (současný roční náklad, nový roční náklad, roční úspora za každý rok, u 2027 navíc příznak `je_modelovy_odhad` a rozpad počtu měsíců na T1 vs. T2 z kap. 4.7). OZ uvidí i 2.–3. nejlepší variantu pro srovnání (ne jen vítěze), ať má o čem s zákazníkem mluvit.

---

## 6. Rozhodnuto (shrnutí)

1. Nabíjecí výkon = vybíjecí výkon, jedno pole v katalogu. ✅
2. Všechny ceny bez DPH. ✅
3. Práh nedoporučené návratnosti: **5 let**, výchozí hodnota v `vypoctova_nastaveni`, editovatelná vedením/adminem. ✅
4. **Peak shaving pouze pro VN/VVN, appka to pro NN vůbec nenabízí.** ✅
5. **Rozjíždíme naostro jen s ČEZ Distribuce** (2026, `stara_2026`) – EG.D a PRE zůstávají v tabulce prázdné, doplní se přes admin rozhraní, až budou čísla ověřená. ✅
6. **Struktura roku 2027 (`nova_2027`) je naplněná modelovými/informativními hodnotami** (dvousložkový T1/T2 model + penalizace za překročení RP, kap. 4.6) – nezávisle ověřeno proti veřejnému příkladu (Volteon.cz), čísla sedí přesně. Appka je označí jako `je_modelovy_odhad = true`, dokud nevyjde závazné cenové rozhodnutí ERÚ (očekáváno listopad 2026) – pak stačí přepsat řádek v tabulce. ✅
7. **Koeficient AKU (kap. 4.8) se zahrnuje jako optimistický odhad**, s příznakem `predpoklad_aku_neoverovany = true` – mechanismus slevy je potvrzený nezávisle, ale výpočet "účinnosti" pro čistě peak-shavingovou baterii je nepotvrzený předpoklad, dokud to neprojdeme s oficiálním manuálem ERÚ. ✅

## 7. Zbývá doplnit před ostrým nasazením

- **VN/VVN sazby EG.D pro rok 2026** – nedohledáno.
- **PRE VN/VVN pro rok 2026** – dohledáno, ale jen přes vyhledávání (ne přímý PDF), doporučuju ověřit.
- **Potvrdit, že pokuta za překročení (1 108/521 Kč/kW) je opravdu jednotná napříč všemi třemi distributory** – vypadá to tak (je to regulovaná cena ERÚ), potvrzeno nezávisle pro ČEZ i EG.D, PRE neověřeno.
- **Finální (nemodelové) sazby T1/T2 pro rok 2027** – čekáme na závazné cenové rozhodnutí ERÚ, očekáváno listopad 2026. Modelové hodnoty už appka má a jsou nezávisle ověřené, takže appka může fungovat i v mezidobí – jen s jasným "modelový odhad" štítkem u roku 2027.
- Tvoje modelové hodnoty se zatím vztahují jen na **ČEZ Distribuce** – nevím, jestli T1/T2 sazby pro rok 2027 budou stejné napříč distributory (u roku 2026 se rezervovaná kapacita mezi distributory lišila, takže bych to nepředpokládal automaticky ani tady). Až budeš mít modelová čísla i pro EG.D/PRE, doplníme je stejným způsobem.
- **Definice "účinnosti odběrného místa" pro Koeficient AKU (kap. 4.8)** – potřeba ověřit v "Manuál pro zákazníka" nebo "Cenový výměr VVN VN 2026" (oba PDF na eru.gov.cz, odkaz v sekci Zdroje). Konkrétně jestli se pro čistě peak-shavingovou baterii bez exportu do sítě počítá interní cyklování (nabito/vybito v rámci baterie), nebo jestli je nutný fyzický export přes elektroměr do distribuční sítě. Já se k těm PDF nedostanu (nejdou strojově přečíst a eru.gov.cz je mimo síťový allowlist mého sandboxu) – potřebuju od tebe/kolegy buď zkopírovaný text z PDF, nebo jen potvrzení, že interní cyklování stačí.

Doporučuju, ať EG.D/PRE 2026 doplní kolega, co s ceníky běžně pracuje – přímo z PDF, které jsou v sekci Zdroje níže. Já se k nim dál nedostanu (web nástroje PDF spolehlivě nepřečtou), klidně ale projdu čísla s tebou, až je budeš mít po ruce.

---

## 8. Zdroje

- [Ceny při překročení rezervovaného příkonu a výkonu – ČEZ Distribuce](https://www.cezdistribuce.cz/cs/pro-zakazniky/potrebuji-vyresit/ceny-a-podminky/ceny-pri-prekroceni-rezervovaneho-prikonu-a-vykonu)
- [Ceník služeb ČEZ Distribuce, platnost od 1. 2. 2026 (PDF)](https://www.cezdistribuce.cz/file/edee/distribuce/ceniky/cenik_sluzeb_01022026.pdf)
- [Účtování překročení rezervovaného výkonu – EG.D](https://www.egd.cz/uctovani-prekroceni-rezervovaneho-vykonu)
- [EG.D – distribuční ceníky a sazby elektřiny](https://www.egd.cz/distribucni-ceniky-sazby-elektriny)
- [EG.D – ceník distribuce EE 2026, kategorie C/firmy (PDF)](https://www.egd.cz/sites/default/files/2026-01/egd_cenik_distribuce_ee_c_2026.pdf)
- [EG.D – brožura přehled sazeb a cen 2026 (PDF)](https://www.egd.cz/sites/default/files/2026-01/egd_brozura_distribuce_ee_c_2026.pdf)
- [PREdistribuce – Změna rezervované kapacity](https://www.predistribuce.cz/cs/potrebuji-zaridit/zakaznici/zmena-rezervovane-kapacity/)
- [Energetický regulační věstník, částka 13/2024 (ERÚ, regulované ceny)](https://eru.gov.cz/sites/default/files/obsah/prilohy/erv132024.pdf)

**K tarifní reformě 2027:**
- [Inovace tarifní struktury na hladinách VN a VVN od roku 2027 – ERÚ](https://eru.gov.cz/inovace-tarifni-struktury-v-ramci-prenosove-soustavy-distribucni-soustavy-na-napetovych-hladinach)
- [Nová tarifní struktura 2027: v hlavní roli průběhové měření a flexibilita – TZB-info](https://energetika.tzb-info.cz/energeticka-politika/29276-nova-tarifni-struktura-2027-v-hlavni-roli-prubehove-mereni-a-flexibilita)
- [Tarifní reforma 2027: Jedna čtvrthodina rozhodne o ceně distribuce – TZB-info](https://energetika.tzb-info.cz/134756-tarifni-reforma-2027-jedna-ctvrthodina-rozhodne-o-cene-distribuce)
- [Platby za distribuci elektřiny se budou měnit. Nejprve podnikům, později domácnostem – Ekonomický deník](https://ekonomickydenik.cz/platby-distribuce-elektriny-menit-podniky/)
- [Ušetříte, nebo budete platit? Nová Tarifní Struktura pro VN a VVN 2027 – Volteon (nezávislé ověření modelových čísel a mechaniky T1/T2)](https://www.volteon.cz/blog/chytre-rizeni-4/usetrite-nebo-budete-platit-nova-tarifni-struktura-pro-vn-a-vvn-2027-41)
- [Co už víme: Inovace tarifní struktury na hladinách VN a VVN – Svaz průmyslu a dopravy ČR (odkaz na oficiální ERÚ kalkulátor)](https://www.spcr.cz/co-uz-vime-inovace-tarifni-struktury-na-hladinach-vn-vvn)
- [Inovace tarifní struktury – ERÚ, oficiální kalkulátor a manuál (obsahuje i "Manuál pro zákazníka" a "Cenový výměr VVN VN 2026" PDF – nešlo strojově přečíst, doporučuju stáhnout a projít ručně)](https://eru.gov.cz/inovace-tarifni-struktury-v-ramci-prenosove-soustavy-distribucni-soustavy-na-napetovych-hladinach)
- [Dopad nové tarifní struktury: Bateriová úložiště se vyhnou vysokým poplatkům – Petr Foitl, Solar Global/AKU-BAT (zdroj ke koeficientu AKU, kap. 4.8)](https://www.obnovitelne.cz/clanek/4713/dopad-nove-tarifni-struktury-bateriova-uloziste-se-vyhnou-vysokym-poplatkum)
