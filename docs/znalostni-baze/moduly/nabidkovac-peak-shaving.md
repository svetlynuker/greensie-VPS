# Nabídkovač – kalkulátor Peak shaving

> **Kde to je:** uvnitř modulu **Nabídkovač**, v detailu nabídky **typu `peak_shaving`** (jen pro **VN/VVN**, na NN appka peak shaving nenabízí)
> **Kdo smí otevřít:** kdokoli s právem `nabidkovac` (OZ, vedení, admin) · sazby distributorů a výpočtová nastavení edituje jen `nabidkovac_katalog` (vedení/admin)
> **Kód:** frontend `frontend/src/components/PeakShavingPanel.jsx` (+ `components/GrafOdberu.jsx`, admin `pages/NabidkovacKatalog.jsx`), backend `backend/app/nabidkovac/` (jádro `peak_shaving.py`)

Kalkulátor, který z **15minutového profilu odběru** spočítá, jaká bateriová úložiště (peak shaving) klientovi na VN/VVN nejvíc snížíme platby distributorovi za rezervovanou kapacitu – a za jak dlouho se investice vrátí. Ekonomiku počítá pro **dnešní tarif (2026)** i pro **novou strukturu ERÚ (2027, zatím modelový odhad)** a doporučí konkrétní baterii z katalogu.

> 📸 SCREENSHOT: celý panel „Peak shaving – výpočet" v detailu nabídky – od načtení profilu přes vstupy až po výsledek

---

## 🧑 Pro uživatele

### K čemu to slouží
Velcí odběratelé na **VN/VVN** platí distributorovi nejen za spotřebovanou energii, ale i za **rezervovanou kapacitu (RK)** – tedy za výkon, který si u sítě „zamluví". Když jim odběr občas vyskočí (krátké špičky), musí mít sjednanou vysokou RK a draho ji platí celý rok, i když ji využijí jen pár hodin.

**Peak shaving** = baterie, která tyhle špičky „ustřihne": když odběr překročí zvolený strop, baterie dodá zbytek ze svých zásob, takže síť špičku nevidí. Klient pak může mít sjednanou nižší RK a ušetří. Tento kalkulátor spočítá, **o kolik nižší RK baterie umožní**, **kolik to ušetří za rok** a **za jak dlouho se baterie zaplatí**.

Fakta a čísla čerpá tento návod z technického souhrnu; ekonomické vzorce jsou tu popsané lidsky, přesné odvození viz [technický souhrn peak shavingu](../../moduly/peak-shaving.md).

### Než začneš – co potřebuješ
1. **Založenou nabídku typu `peak_shaving`** (zakládá se v Nabídkovači – viz [Nabídkovač](nabidkovac.md)).
2. **15minutový profil odběru** klienta jako soubor **XLS / XLSX / CSV** – export z portálu distributora. Musí pokrývat **zhruba celý rok** (viz „Časté potíže").
3. **Fakturu** klienta, ze které opíšeš **sjednanou rezervovanou kapacitu (kW)**.
4. (Volitelně) **smlouvu o připojení** kvůli rezervovanému příkonu – pro model 2027.

### Rozvržení panelu
Panel je rozdělený do tří kroků shora dolů:

1. **Krok 1 – Profil odběru.** Nahraný soubor se spotřebou se tlačítkem „načte" (naparsuje) do appky. Nad tlačítkem vidíš stav: kolik intervalů se načetlo, od kdy do kdy a jaká je špička.
2. **Krok 2 – Parametry odběrného místa.** Formulář: distributor, napěťová hladina, rezervovaná kapacita a volitelná pole. Dole tlačítko **Spočítat peak shaving**.
3. **Krok 3 – Výsledek.** Objeví se po výpočtu: přepínač roku, dlaždice s hlavními čísly (KPI), návratnost dle modelů, ekonomika 2026 vs. 2027 vedle sebe, graf měsíčních maxim, citlivost návrhu, rozpis po letech a srovnání variant.

> 📸 SCREENSHOT: tři kroky panelu s očíslovanými popisky (profil / parametry / výsledek)

### Ovládací prvky a vstupní pole – políčko po políčku
Legenda „kdo vidí": **(vše)** = každý, kdo nabídku otevře (má právo `nabidkovac`) · **(admin katalogu)** = mění se jen v Katalogu s právem `nabidkovac_katalog`.

| Prvek | Kde | Co to je → co ovlivní | Kdo vidí |
|---|---|---|---|
| **Načíst profil: `<název souboru>`** | krok 1 | Tlačítko pro každý nahraný podklad (typ „spotřeba" nebo „jiný"). Klik naparsuje 15min profil do appky. **Nahrazuje celý dosavadní profil nabídky** (poslední vyhrává). Bez načteného profilu nejde počítat. | vše |
| **Distributor** | krok 2 | Výběr provozovatele distribuční soustavy: **ČEZ Distribuce / EG.D / PRE distribuce**. Určuje, které sazby se do výpočtu použijí. | vše |
| **Napěťová hladina** | krok 2 | **VN** nebo **VVN**. Spolu s distributorem vybírá sazbu. (NN appka nenabízí.) | vše |
| **Sjednaná rezervovaná kapacita (kW)** | krok 2 | Kolik RK má klient **dnes sjednáno** – opsat **z faktury**. Je to výchozí stav, proti kterému se počítá úspora. Povinné, musí být > 0. | vše |
| **Rezervovaný příkon (kW, volit.)** | krok 2 | Hodnota **ze smlouvy o připojení** (dlouhodobá, bývá ≥ RK). Používá se v modelu **2027**. Když ho nevyplníš, dosadí se současná RK a výstup upozorní, že skutečný příkon bývá vyšší. | vše |
| **Max. výkon střídače (kW, volit.)** | krok 2 | Ruční strop AC výkonu baterie. Hodí se u modulárních baterií, kde s počtem kusů roste kapacita, ale výkon drží sdílený střídač (PCS). Prázdné = neomezuje. | vše |
| **„V modelu 2027 uvažovat snížení rezervovaného příkonu…"** (zaškrtávátko) | krok 2 | Když zaškrtneš, model 2027 počítá s **poníženým** rezervovaným příkonem (na novou kapacitu). Je to **jednosměrná změna smlouvy o připojení** – zpětné navýšení je zpoplatněné. Ve výchozím stavu vypnuto (poctivý default bez změny smlouvy). | vše |
| **Spočítat peak shaving** | krok 2 | Spustí výpočet. Aktivní, jen když je **načtený profil**, **kladná RK** a **existují sazby 2026** pro zvolenou kombinaci distributor/hladina. | vše |
| **Zobrazit rok: 2026 / 2027** (přepínač) | krok 3, výsledek | Přepíná, pro který rok se ukazují dlaždice, návratnost, graf a sloupec ve srovnání variant. **2027 je výchozí**; když ekonomika 2027 chybí (nejsou sazby), tlačítko 2027 je zakázané a vše spadne na 2026. | vše |
| **Řádek ve „Srovnání variant"** | krok 3, tabulka | Klik na řádek **překreslí celý detail** (dlaždice, ekonomika, grafy, citlivost) pro danou variantu. `◄` = právě zobrazená, první řádek = doporučená. | vše |

> 📸 SCREENSHOT: formulář parametrů odběrného místa s vyplněnými poli a tlačítkem „Spočítat peak shaving"

> ℹ️ **Cena energie pro ocenění ztrát** (3 000 Kč/MWh bez DPH) se v tomto panelu **nezadává** – je to manažerské nastavení v Katalogu (viz „Pro admina"). API ho umí přijmout, ale formulář ho nenabízí.

### Co znamená stav profilu (krok 1)
- **„✅ Načteno N intervalů, DD.MM.RRRR – DD.MM.RRRR, špička X kW"** – profil je v pořádku a připravený k výpočtu. Špička = nejvyšší 15min hodnota odběru v celém profilu.
- **„Profil zatím není načtený."** – soubor jsi ještě nenačetl (nebo se nenačetl). Klikni na tlačítko „Načíst profil".
- **„⚠️ Nejdřív nahraj soubor se spotřebou"** – v nabídce není žádný vhodný podklad; nahraj ho v sekci Podklady výše (viz [Nabídkovač](nabidkovac.md)).

### Co znamenají výstupní hodnoty (krok 3)

#### Dlaždice (KPI) – hlavní čísla na první pohled
Ukazují se pro rok zvolený přepínačem:

| Dlaždice | Co znamená |
|---|---|
| **Roční úspora (rok)** | Kolik klient ušetří za rok. U 2026 je pod tím rozpad „z toho bez investice X" (viz níže). U 2027 je to modelový odhad NTS. |
| **Návratnost (rok)** | Za kolik let se baterie zaplatí. Počítá se z **přínosu baterie**, ne z celkové úspory (viz upozornění níže). Vedle je práh doporučení. |
| **Nová rez. kapacita** (rok 2026) | Jaká RK bude po instalaci baterie sjednaná. Pod tím fyzický „strop" baterie a rezerva. |
| **Rezervovaný příkon** (rok 2027) | Rezervovaný příkon v modelu 2027 (případně jeho snížení, když je zaškrtnuté). |
| **Baterie** | Doporučená baterie a počet kusů, její celkový výkon / kapacita a cena. |
| **NPV (N let)** | Čistá současná hodnota investice na horizontu (default 10 let), případně IRR. **Právě NPV řídí výběr doporučené varianty.** |

> ⚠️ **Proč se návratnost počítá jen z „přínosu baterie" a ne z celé úspory:** část úspory klient získá i **bez investice** – stačí si u distributora zoptimalizovat sjednanou RK (tzv. „audit RK zdarma"). Do návratnosti baterie se proto započítává jen to, co přinese **navíc sama baterie**. Dlaždice „Roční úspora 2026" proto rozlišuje „z toho bez investice X".

#### Návratnost investice dle modelu
Malá tabulka se dvěma řádky:
- **Model 2026 (dnešní tarif)** – návratnost podle dnes platných sazeb. **Podle něj se řídí výběr varianty.**
- **Model 2027 (nová struktura ERÚ)** – návratnost podle odhadu nové tarifní struktury. **Modelový odhad, ne finální cena** (závazný výměr ERÚ vyjde ~11/2026). Sleva „AKU" se na peak-shavingovou baterii **nevztahuje** (baterie uvnitř odběru nic nevrací do sítě).

#### Ekonomika – porovnání let (dvě karty vedle sebe)
Aktivní (zvýrazněná) je karta roku podle přepínače.

**Rok 2026** ukazuje rozpad:
- **Roční náklad dnes (RK …)** – co klient za RK platí teď.
- **Optimalizace RK bez baterie** – nejlevnější kombinace roční + měsíční RK, které lze dosáhnout **bez investice** (jen chytrým sjednáním).
- **Úspora hned bez investice** – rozdíl obou předchozích řádků.
- **Náklad s baterií** (+ případné ztráty cyklování baterie).
- **Přínos baterie** – co přidá sama baterie navíc.
- **Celková roční úspora** – součet obojího.

**Rok 2027** (dvousložkový tarif T1/T2):
- **Roční náklad dnes (RP …)**, **Optimalizace RP bez baterie**, **Úspora hned bez investice**, **Náklad s peak shavingem**, **Přínos baterie**, **Roční úspora**.
- **Měsíců na tarifu T1 / T2** – kolikrát za rok vyšel levněji který tarif. Zákazník tarif **nevybírá**, distributor ho každý měsíc určí sám podle skutečné spotřeby. (**T1** = dražší paušál + levná špička → sedí provozu naplno u příkonu; **T2** = levný paušál + drahá špička → sedí utlumenému provozu.)
- **Rezervovaný příkon (RP)** – případně jeho snížení, pokud je zaškrtnuté.

> 📸 SCREENSHOT: dvě karty „Rok 2026" a „Rok 2027" vedle sebe s rozpadem úspory

#### Graf „Odběr ze sítě – měsíční maxima"
Sloupcový graf po měsících:
- **modrý sloupec „bez baterie"** = naměřené měsíční maximum odběru,
- **zelený sloupec „s baterií"** = maximum po srážce baterií (u 2026 držení jednoho ročního stropu, u 2027 srážení po měsících co nejhlouběji),
- **čárkovaná čára „rezervace nyní"** = dnešní sjednaná RK,
- **čárkovaná čára „rezervace nová"** = RK/RP po instalaci.

Najetím myší na sloupec se ukáže přesná hodnota. Graf se překreslí podle přepínače roku i podle vybrané varianty.

> 📸 SCREENSHOT: graf měsíčních maxim se čtyřmi prvky legendy (bez baterie / s baterií / rezervace nyní / rezervace nová)

#### Citlivost návrhu
Věta pod grafem: co by se stalo, kdyby byl profil o **±5 %** silnější/slabší – jestli by nasazená rezerva RK zvládla i „silnější rok", nebo by hrozily měsíční dokupy/pokuty. Je to rychlá kontrola, jak moc je návrh „na hraně".

#### Ekonomika po letech
Tabulka rok po roce na celém horizontu (default 10 let): tarif toho roku, přínos baterie, O&M (údržba), cash-flow roku, kumulovaná úspora a kumulované cash-flow. Řádek označený `◄` = rok, kdy se investice **poprvé vrátí**. Poslední hodnota „Kum. disk. CF" = NPV varianty.

#### Srovnání variant
Tabulka všech zvažovaných baterií (top varianty). První řádek = doporučená (dle NPV). Kliknutím na jiný řádek se celý výše popsaný detail přepočítá pro tu variantu. Varianta nad prahem návratnosti nese odznak **„nedoporučeno"**.

### Jak na…
- **Spočítat peak shaving od nuly:** nahraj profil v Podkladech → v kroku 1 klikni **Načíst profil** → v kroku 2 vyber **distributora** a **hladinu**, opiš **RK z faktury** → **Spočítat peak shaving**.
- **Zohlednit model 2027 se snížením příkonu:** vyplň **Rezervovaný příkon** ze smlouvy, zaškrtni **„uvažovat snížení RP"**, spočítej a přepni nahoře na **2027**.
- **Porovnat víc baterií:** po výpočtu klikej na řádky ve **Srovnání variant** – detail se pro každou překreslí.
- **Omezit výkon u modulární baterie:** vyplň **Max. výkon střídače** (kW) podle sdíleného PCS a přepočítej.
- **Vyměnit profil za novější:** nahraj nový soubor a klikni **Načíst profil** – starý profil se **celý** nahradí.

---

## 🛠 Pro admina / provoz

### Práva – kdo co vidí a smí
- Celý panel Peak shaving vidí a spouští každý s právem **`nabidkovac`** (strážce `vyzaduj_nabidkovac`). Uvnitř panelu **není** režim „jen pro čtení" – kdo nabídku otevře, může i počítat.
- **Sazby distributorů** a **výpočtová nastavení** (parametry níže) se editují jen v **Katalogu a výpočtech** (`pages/NabidkovacKatalog.jsx`) s právem **`nabidkovac_katalog`** (vedení/admin; strážce `vyzaduj_katalog`).
- Práva se spravují v modulu **Admin nastavení**. Viz `backend/app/nabidkovac/permissions.py`.

### Sazby distributorů (bez DPH)
Sazby jsou naseedované a editovatelné v Katalogu. Zdroj 2026: **finální CV ERÚ č. 13/2025**. **Všechny ceny bez DPH.**

**Struktura `stara_2026` (ostrá čísla, platnost 2026):**

| DSO | Hladina | Roční RK [Kč/kW/rok] | Měsíční RK [Kč/kW/měs] | Pokuta za překročení (odvozená 1,5× měs. RK) |
|---|---|---|---|---|
| ČEZ | VN | 3 030,78 | 281,823 | 422,73 |
| ČEZ | VVN | 1 409,18 | 131,036 | 196,55 |
| EG.D | VN | 2 766,61 | 254,260 | 381,39 |
| EG.D | VVN | 1 329,91 | 122,223 | 183,33 |
| PRE | VN | 3 253,12 | 299,351 | 449,03 |
| PRE | VVN | 1 554,96 | 143,087 | 214,63 |

> Roční RK se ukládá jako **12× měsíční sazba** (výměr uvádí Kč/kW/měsíc). **Pokuta za překročení RK se nedrží jako samostatné číslo** – výpočet ji odvozuje jako **1,5× měsíční RK** (bod 4.24 výměru), aby se při roční aktualizaci nemohla „rozjet". Starší pole `cena_prekroceni_kc_kw` slouží jen jako fallback ručně založených sazeb.

**Struktura `nova_2027` (MODELOVÝ ODHAD, `je_modelovy_odhad = true`):** dvousložkový tarif T1/T2 (kapacita + špička v Kč/kW/měs), pevná sazba za překročení RP a prahy U1/U2 pro (zatím neaplikovanou) slevu AKU. Čísla z informativního CV ERÚ k NTS – **nejsou finální**, závazný výměr vyjde ~11/2026. Konkrétní hodnoty viz [technický souhrn, kap. 3.2](../../moduly/peak-shaving.md).

V editoru sazeb (Katalog) jsou navíc přepínače **„čeká na sazby ERÚ"** (parametry = NULL) a **„modelový odhad"**.

### Parametry výpočtu a jejich zdroj
Konstanty jsou v `peak_shaving.py`; manažerské parametry ve **výpočtových nastaveních** (`vypoctova_nastaveni.parametry`, editace v Katalogu):

| Parametr | Klíč / konstanta | Výchozí | Význam |
|---|---|---|---|
| Interval profilu | konstanta | 0,25 h | délka jednoho kroku (odvozuje se z časů, fallback 15 min) |
| Max. počet kusů baterie | konstanta | 5 | kolik kusů jednoho typu se zkouší |
| Účinnost baterie RT (AC-AC) | `technologie.ucinnost` / default | 0,88 | round-trip účinnost; z katalogu má přednost |
| Využitelná kapacita | konstanta | 85 % jmenovité | SOC okno 10–95 % |
| Rezerva RK nad stropem | `ps_rezerva_rk_procenta` | 5 % | polštář na meziroční variabilitu, servis, jinou zimu |
| Cena energie (ocenění ztrát) | `ps_cena_energie_kc_mwh` | 3 000 Kč/MWh | oceňuje ztráty cyklování; snižuje úsporu |
| Práh doporučené návratnosti | `max_navratnost_roky_peak_shaving` | 5 let | nad ním se varianta označí „nedoporučeno" |
| Diskontní sazba (NPV) | `ps_diskontni_sazba` | 8 % | pro NPV/IRR |
| Horizont NPV | `ps_horizont_npv_roky` | 10 let | délka ekonomiky po letech |
| O&M (údržba) | `ps_oam_procenta_capex_rok` | 2 % CAPEX/rok | provozní náklady |
| Degradace úspor | `ps_degradace_uspor_procenta_rok` | 1,5 %/rok | pokles přínosu baterie v čase |

Podrobné vzorce (simulace baterie, fair baseline 2026, dvousložkový tarif 2027, NPV/IRR, koeficient AKU) viz [technický souhrn kap. 4](../../moduly/peak-shaving.md).

### Datový model (PostgreSQL)
- **`spotreba_profil`** – 15min profil odběru (`nabidka_id`, `cas`, `hodnota_kw`, `zdroj_dokument_id`). Unique `(nabidka_id, cas)`. Zpracování profilu **nahrazuje celý** profil nabídky (poslední vyhrává), duplicitní časy z podzimního přechodu času slučuje na maximum.
- **`sazby_distributoru`** – sazby dle `distributor` × `napetova_hladina` × `struktura_tarifu` (`stara_2026`/`nova_2027`); ceny v JSONB `parametry` (NULL = „čeká na sazby ERÚ"), historie přes `platne_od`/`platne_do`, příznak `je_modelovy_odhad`.
- **`technologie`** – katalog; pro `typ = baterie` musí mít **oba** parametry `vykon_kw` i `kapacita_kwh` (validace v API); vlastní sloupce v JSONB `extra`.
- **`katalog_sloupce`** – definice vlastních (admin) sloupců katalogu.
- **`navrhovana_reseni`** – výstup výpočtu v `popis_json` (`typ_reseni = peak_shaving`).
- **`vypoctova_nastaveni`** – manažerské parametry (viz tabulka výše).

### API (prefix `/nabidkovac`, přes Caddy `/api`)
| Metoda / cesta | Právo | Popis |
|---|---|---|
| `POST /dokumenty/{id}/zpracuj-profil` | `nabidkovac` | naparsuje XLS/XLSX/CSV → `spotreba_profil` (nahradí celý profil) |
| `GET /nabidky/{id}/peak-shaving/profil-souhrn` | `nabidkovac` | počet intervalů, rozsah (od/do), špička `max_kw` |
| `POST /nabidky/{id}/peak-shaving/vypocet` | `nabidkovac` | spustí výpočet, uloží do `navrhovana_reseni` |
| `GET /sazby` | `nabidkovac` | přehled sazeb (načítá i panel pro validaci) |
| `POST/PUT/DELETE /sazby[/{id}]` | `nabidkovac_katalog` | správa sazeb |
| `GET/POST/PUT/DELETE /katalog-sloupce`, `/technologie` | čte `nabidkovac`, edituje `nabidkovac_katalog` | katalog + vlastní sloupce |

**Vstup výpočtu:** `{ distributor, napetova_hladina, rezervovana_kapacita_kw }` + volitelně `cena_energie_kc_mwh`, `rezervovany_prikon_kw`, `uvazovat_snizeni_rp`, `max_vykon_stridace_kw`.
**Výstup (`popis_json`):** `vstup`, `sazby`, `max_navratnost_roky`, `doporucena`, `varianty` (top 3, každá s vlastním grafem a citlivostí), `graf`, `citlivost_stropu`, `upozorneni`. Každá varianta nese `ekonomika_2026`, `ekonomika_2027`, NPV/IRR a návratnosti.

### Klíčové soubory
```
backend/app/nabidkovac/
  peak_shaving.py    – VÝPOČETNÍ JÁDRO (simulace, ekonomika 2026/2027, NPV, graf)
  profil_import.py   – parser XLS/XLSX/CSV profilu
  profil_pokryti.py  – validace/oříznutí pokrytí roku (SP-1)
  seed.py            – seed sazeb ČEZ/EG.D/PRE (2026 + 2027)
  routes.py          – API (profil, výpočet, sazby, katalog)
  models.py          – tabulky · schemas.py – vstupy/výstupy · permissions.py – práva
backend/app/main.py  – create_all + _lehka_migrace + seed při startu
frontend/src/
  components/PeakShavingPanel.jsx  – panel výpočtu + výsledek (OZ)
  components/GrafOdberu.jsx        – SVG graf měsíčních maxim (bez knihovny)
  pages/NabidkovacKatalog.jsx      – admin: sazby, katalog, výpočtová nastavení
  api.js                           – helpery peakShavingVypocet, profilZpracuj, peakShavingProfilSouhrn, sazby*
```

### Časté potíže / co dělat, když…
- **„Profil spotřeby nelze použít: …" (chyba 422)** → profil není použitelný jako roční: rozsah < 350 dní, chybí kalendářní měsíce, díry > 2 % intervalů, nebo překrývající se okrajové měsíce. Nahraj úplnější roční export. (Profil delší než rok se automaticky ořízne na posledních 12 celých měsíců s upozorněním.)
- **„Zpracování profilu selhalo: …" (chyba 422)** → špatný formát souboru. Parser čeká XLS s listem `export` a sloupci `Datum` (`DD.MM.RRRR HH:MM:SS`) a `Profil +A [kW]`, nebo odpovídající XLSX/CSV. Zkontroluj, že jde o **15min profil činného odběru** z portálu distributora.
- **„Tenhle dokument není profil spotřeby"** → podklad má špatný typ; načítat lze jen dokumenty typu „spotřeba" (`spotreba_csv`) nebo „jiný".
- **Tlačítko „Spočítat" je šedé** → chybí načtený profil, RK není kladná, nebo pro zvolenou kombinaci distributor/hladina **nejsou vyplněné sazby 2026**. Panel na chybějící sazby upozorní žlutou hláškou – doplň je v Katalogu.
- **„Chybí sazba stara_2026 pro …" (422)** → sazba je NULL („čeká na sazby ERÚ") nebo neexistuje. Doplň v Katalogu (sazby distributorů).
- **Přepínač „2027" je zakázaný** → pro danou kombinaci nejsou spočítané sazby 2027; zobrazí se jen 2026.
- **„Výpočet nenašel použitelnou variantu"** → v katalogu nejsou dostupné baterie s vyplněným výkonem i kapacitou, nebo žádná neustojí špičky. Doplň/zkontroluj katalog technologií.
- **Grafy/rozpis chybí u alternativní varianty** → starší uložené výsledky mají grafy jen pro doporučenou variantu; spusť „Spočítat peak shaving" znovu.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **2027 je modelový odhad, ne cena.** Dokud nevyjde závazný výměr ERÚ (~11/2026), jsou všechna čísla 2027 nezávazná (`je_modelovy_odhad`). Výběr doporučené varianty se řídí modelem **2026**.
- **Sleva „koeficient AKU" se neaplikuje** – peak-shavingová baterie uvnitř odběru nic nevrací do sítě, takže dle definice ERÚ vychází nulová. Prahy U1/U2 v sazebníku jsou předběžné a nechané pro budoucí použití (místa s velkým exportem).
- **Návratnost ≠ celková úspora.** Do návratnosti se počítá jen **přínos baterie** proti optimalizované RK; „audit RK zdarma" je prodejní bonus, který klient dostane i bez investice.
- **Cena energie pro ztráty** je jen manažerské nastavení (default 3 000 Kč/MWh bez DPH); panel OZ ji nezadává, i když ji API umí přijmout.
- **Počáteční nabití baterie** v simulaci = plná (zjednodušení v1). EOL derating a vlastní spotřeba PCS se zatím neaplikují.
- **Poznámka k načítání profilu:** načtení **nahradí celý** profil nabídky napříč dokumenty (poslední vyhrává) – ne jen řádky z daného souboru.
- Komponenta `PeakShavingPanel.jsx` importuje z komponent jen `GrafOdberu.jsx` (žádný `CvdToggle`); barvy grafu řeší CSS tokeny `--c-*` kvůli tmavému režimu a kompenzaci červeno-zelené vady.

## Odkazy
- Technický souhrn (odvození vzorců, seed, historie PR): [`docs/moduly/peak-shaving.md`](../../moduly/peak-shaving.md)
- Nadřazený modul: [Nabídkovač](nabidkovac.md)
- Kód backend: `backend/app/nabidkovac/` (jádro `peak_shaving.py`) · frontend: `frontend/src/components/PeakShavingPanel.jsx`, `GrafOdberu.jsx`, `pages/NabidkovacKatalog.jsx`, `api.js`
