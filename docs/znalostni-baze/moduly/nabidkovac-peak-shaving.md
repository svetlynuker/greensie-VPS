# Nabídkovač – kalkulátor Peak shaving

> **Kde to je:** uvnitř modulu **Nabídkovač**, v detailu nabídky **typu `peak_shaving`** (jen pro **VN/VVN**, na NN appka peak shaving nenabízí)
> **Kdo smí otevřít:** kdokoli s právem `nabidkovac` (OZ, vedení, admin) · sazby distributorů a výpočtová nastavení edituje jen `nabidkovac_katalog` (vedení/admin)
> **Kód:** frontend `frontend/src/components/PeakShavingPanel.jsx` (+ `components/GrafOdberu.jsx`, `components/GrafPrubehu.jsx`, admin `pages/NabidkovacKatalog.jsx`), backend `backend/app/nabidkovac/` (jádro `peak_shaving.py`)

Kalkulátor, který z **15minutového profilu odběru** spočítá, jaká bateriová úložiště (peak shaving) klientovi na VN/VVN nejvíc snížíme platby distributorovi za rezervovanou kapacitu – a za jak dlouho se investice vrátí. Ekonomiku, NPV i doporučení počítá na **nové struktuře ERÚ (2027, zatím modelový odhad)** – co se dnes nabízí, se instaluje a spouští už v ní. Dnešní tarif (2026) zůstává jen jako informativní srovnání „co by to bylo teď". Výsledkem je doporučená konkrétní baterie z katalogu.

> 📸 SCREENSHOT: pracovní stůl kalkulátoru – vlevo panel se vstupy, vpravo hlavní čísla, karty variant a záložky výsledku

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

### Rozvržení panelu — „pracovní stůl"
Panel je rozdělený **na dva sloupce**: vlevo úzký panel se **všemi vstupy**, vpravo **výsledek**.
Levý panel je „přilepený" — při čtení výsledku dole neuhne z obrazu, takže jde přepsat
rezervovanou kapacitu a hned vedle sledovat, co to udělalo s návratností.
Na úzké obrazovce (do 1150 px) se panel přesune nad výsledek a přestane být přilepený.

**Levý panel – vstupy výpočtu** (čtyři číslované sekce):

1. **Profil odběru.** Nahraný soubor se spotřebou se tlačítkem „načte" (naparsuje) do appky.
   Nad tlačítky vidíš stav: kolik intervalů se načetlo, od kdy do kdy a jaká je špička.
2. **Odběrné místo.** Distributor, napěťová hladina, rezervovaná kapacita, rezervovaný příkon,
   snížení příkonu a max. výkon střídače. Jednotky (kW) jsou uvnitř políček.
   Ručně zadané hodnoty se **pamatují u nabídky** – když se do ní vrátíš (i po zavření prohlížeče),
   jsou předvyplněné podle posledního výpočtu, resp. podle toho, co jsi naposled psal.
   Nejsou zamčené: cokoli přepíšeš, přepsané zůstane.
3. **Co má baterie dělat.** Tři režimy – *Peak shaving*, *Kombinace*, *Spot* (viz níž).
   U obchodních režimů se navíc nabídne pole *Max. dodávka do sítě*.
4. **Baterie do výpočtu.** Celý katalog, nebo ruční výběr produktů.

V patičce panelu je tlačítko **Spočítat peak shaving** a pod ním **kontrolní seznam** — u každé
podmínky výpočtu ✓ nebo `!` s tím, co ještě chybí. Zakázané tlačítko tak nikdy není bez vysvětlení.

**Pravý sloupec – výsledek** (objeví se po výpočtu):

- **hlavička** s vybranou variantou, odznakem *doporučeno / nedoporučeno* a **přepínači zobrazení**
  (rok, základ návratnosti) — platí pro celý pravý sloupec,
- **dlaždice s hlavními čísly** (KPI): úspora, reálná návratnost, NPV, nová rezervace, investice,
- **Varianty k rozhodnutí** — karty vedle sebe (nejvhodnější podle NPV a nejlevnější),
- **záložky**: *Ekonomika* · *Obchod na spotu* (jen v obchodních režimech) · *Grafy odběru* · *Srovnání variant* · *Po letech*.

Záložky nahradily jednu dlouhou rolovací stránku. Dřív bylo srovnání variant až na jejím konci,
ale klik na řádek přepisoval čísla o dvě obrazovky výš, takže tu změnu nebylo vidět.

> 📸 SCREENSHOT: pracovní stůl – vlevo panel vstupů s kontrolním seznamem, vpravo dlaždice a karty variant

### Ovládací prvky a vstupní pole – políčko po políčku
Legenda „kdo vidí": **(vše)** = každý, kdo nabídku otevře (má právo `nabidkovac`) · **(admin katalogu)** = mění se jen v Katalogu s právem `nabidkovac_katalog`.

| Prvek | Kde | Co to je → co ovlivní | Kdo vidí |
|---|---|---|---|
| **Načíst profil: `<název souboru>`** | vstupy, sekce 1 | Tlačítko pro každý nahraný podklad (typ „spotřeba" nebo „jiný"). Klik naparsuje 15min profil do appky. **Nahrazuje celý dosavadní profil nabídky** (poslední vyhrává). Bez načteného profilu nejde počítat. | vše |
| **Distributor** | vstupy, sekce 2 | Výběr provozovatele distribuční soustavy: **ČEZ Distribuce / EG.D / PRE distribuce**. Určuje, které sazby se do výpočtu použijí. | vše |
| **Napěťová hladina** | vstupy, sekce 2 | **VN** nebo **VVN**. Spolu s distributorem vybírá sazbu. (NN appka nenabízí.) | vše |
| **Sjednaná rezervovaná kapacita (kW)** | vstupy, sekce 2 | Kolik RK má klient **dnes sjednáno** – opsat **z faktury**. Je to výchozí stav, proti kterému se počítá úspora. Řídí celý model **2026**. Povinné, musí být > 0. | vše |
| **Rezervovaný příkon (kW, volit.)** | vstupy, sekce 2 | Hodnota **ze smlouvy o připojení** (dlouhodobá, bývá výrazně ≥ RK). Řídí celý model **2027**. Necháš-li prázdné, počítá se **RP = RK** – appka to napíše pod políčkem i v tabulce 2027 a přidá upozornění. Není to neutrální volba: skutečný RP bývá vyšší, takže náklad 2027 i úspora vyjdou podhodnocené (viz „RK vs. RP" níže). | vše |
| **Max. výkon střídače (kW, volit.)** | vstupy, sekce 2 | Ruční strop AC výkonu baterie. Hodí se u modulárních baterií, kde s počtem kusů roste kapacita, ale výkon drží sdílený střídač (PCS). Prázdné = neomezuje. | vše |
| **„V modelu 2027 uvažovat snížení rezervovaného příkonu…"** (zaškrtávátko) | vstupy, sekce 2 | Když zaškrtneš, model 2027 hledá **nejlevnější RP** – stejným optimalizátorem jako u varianty bez baterie. RP proto může skončit i **pod nejvyšší měsíční špičkou**, pokud se v tom měsíci vyplatí zaplatit překročení (viz „Vědomé překročení RP" níže). Je to **jednosměrná změna smlouvy o připojení** – zpětné navýšení je zpoplatněné. Ve výchozím stavu vypnuto (poctivý default bez změny smlouvy). | vše |
| **Baterie do výpočtu: Všechny / Jen ručně vybrané** (přepínač) | vstupy, sekce 3 | *Všechny* = celý dostupný katalog (výchozí). *Jen ručně vybrané* rozbalí seznam s hledáním a zaškrtávátky – počítají se pak jen označené produkty, což výpočet zrychlí. Tlačítka *Označit zobrazené* / *Zrušit výběr*. | vše |
| **Spočítat peak shaving** | patička vstupů | Spustí výpočet. Pod tlačítkem je **kontrolní seznam**, který u nesplněné podmínky řekne, co chybí. Aktivní, jen když je **načtený profil**, **kladná RK**, **existují sazby 2026** pro zvolenou kombinaci distributor/hladina a (při ručním výběru) je **označená aspoň jedna baterie**. | vše |
| **Zobrazit rok: 2026 / 2027** (přepínač) | hlavička výsledku | Přepíná, pro který rok se ukazují dlaždice, prostá návratnost, graf a sloupec ve srovnání variant. **2027 je výchozí**; když ekonomika 2027 chybí (nejsou sazby), tlačítko 2027 je zakázané a vše spadne na 2026. Pozor: ekonomika, NPV i doporučení jedou vždy na modelu 2027 — karta 2026 je jen informativní srovnání „co by to bylo dnes". | vše |
| **Počítat návratnost z: Celá úspora / Jen přínos baterie** (přepínač) | hlavička výsledku | Volí, z čeho se počítá **NPV, reálná návratnost a doporučení** (viz „Dvě čtení návratnosti" níže). Obě varianty jsou spočítané dopředu, přepnutí **nic nepřepočítává** — okamžitě se překreslí dlaždice NPV, řádek „Reálně", tabulka po letech, odznaky „nedoporučeno" i pořadí ve srovnání variant. Volba se pamatuje v prohlížeči. Výchozí je **Celá úspora**. | vše |
| **Karta ve „Variantách k rozhodnutí"** | výsledek, pod dlaždicemi | Dvě karty vedle sebe, každá vítěz jiného kritéria: **◆ Nejvhodnější** (nejvyšší NPV – ta doporučená) a **Nejlevnější** (nejnižší investice). Klik kartu vybere a překreslí celý výsledek. Vítěz se hledá nezávisle na řazení tabulky. Pruh dole = NPV proti nejlepší variantě. Když oba vítězové padnou na tutéž baterii, karty se skryjí. | vše |
| **Řádek ve „Srovnání variant"** | záložka Srovnání variant | Klik na řádek **překreslí celý výsledek** (dlaždice, karty, ekonomika, grafy, citlivost) pro danou variantu. `◄` = právě zobrazená. | vše |
| **Záložky výsledku** | nad výsledkem | *Ekonomika* (dvě karty roků + tři čísla návratnosti) · *Grafy odběru* (měsíční maxima, citlivost, průběh v čase) · *Srovnání variant* (tabulka) · *Po letech* (rozpis horizontu). Přepnutí nic nepřepočítává. | vše |
| **Záhlaví sloupce ve srovnání** | záložka Srovnání variant | Klik **seřadí** tabulku podle toho sloupce (druhý klik obrátí směr): baterie (abecedně), výkon, nová rezervace, úspora, cena, návratnost, NPV. Prázdné hodnoty padají na konec. Odkaz *zpět na doporučené pořadí* vrátí výchozí řazení dle NPV. | vše |
| **Zobrazit všechny (N)** | záložka Srovnání variant | Rozbalí srovnání z 3 nejlepších na **celý spočítaný katalog** (řazeno dle NPV) – pro manažerské rozhodnutí. Zpět tlačítkem *Jen 3 nejlepší*. | vše |

> 📸 SCREENSHOT: formulář parametrů odběrného místa s vyplněnými poli a tlačítkem „Spočítat peak shaving"

#### Rezervovaná kapacita vs. rezervovaný příkon – nejčastější záměna
Nejsou to varianty téhož čísla, jsou to **dvě různé hodnoty, které platí současně**, a každá krmí jiný rok. Vyplňuj proto **obě**.

| | Rezervovaná kapacita (RK) | Rezervovaný příkon (RP) |
|---|---|---|
| **Co to je** | roční distribuční **produkt** – co si klient každý rok sjednává | **technický limit přípojky** ze smlouvy o připojení |
| **Kde to najdeš** | na **faktuře** za distribuci (Kč/kW/rok) | ve **smlouvě o připojení** |
| **Typická hodnota** | nižší – klient ji drží u sebe co nejtěsněji | výrazně vyšší než RK |
| **Jak se mění** | každý rok (snížení až po 12 měsících od poslední změny), lze dokupovat měsíční RK | **jednosměrně** – zpětné navýšení je zpoplatněné (příloha 2 vyhlášky 16/2016 Sb.) |
| **Když se překročí** | pokuta 1,5× měsíční sazba | sazba za překročení dle NTS |
| **Řídí v appce** | celý model **2026**, KPI „Nová rez. kapacita", čáry v grafu měsíčních maxim v režimu 2026 | celý model **2027**, KPI „Rezervovaný příkon", čáry v grafu v režimu 2027 |

RP existuje i dnes – jen se za něj dnes neplatí distribuční složka (platí se za RK). Od NTS 2027 se to překlopí: kapacitní složka se počítá z **RP**, k tomu se platí naměřené měsíční maximum, a roční/měsíční produkt „rezervovaná kapacita" v dnešní podobě odpadá.

> ⚠️ **Prázdné políčko RP zkazí i výběr baterie, ne jen kartu 2027.** NPV a reálná návratnost, podle kterých se vybírá vítěz a doporučení, počítají rok 1 na tarifu 2026 a roky 2–10 v NTS 2027. Na reálné nabídce (RK 339 kW, špičky 310–372 kW) se změnou samotného políčka RP z „nezadáno" (→ 339) na skutečných 560 kW posunulo NPV z **−540 tis. na +188 tis. Kč** a reálná návratnost z „nevrátí se" na **6,0 let**. Nezadaný RP tedy vypadá jako opatrný odhad, ale je to nejhorší možný: RP = RK znamená „přípojka nemá vůbec žádnou rezervu".

> ℹ️ **Cena energie pro ocenění ztrát** (3 000 Kč/MWh bez DPH) se v tomto panelu **nezadává** – je to manažerské nastavení v Katalogu (viz „Pro admina"). API ho umí přijmout, ale formulář ho nenabízí.

### Co znamená stav profilu (sekce 1 vstupů)
- **„✅ Načteno N intervalů, DD.MM.RRRR – DD.MM.RRRR, špička X kW"** – profil je v pořádku a připravený k výpočtu. Špička = nejvyšší 15min hodnota odběru v celém profilu.
- **„Profil zatím není načtený."** – soubor jsi ještě nenačetl (nebo se nenačetl). Klikni na tlačítko „Načíst profil".
- **„⚠️ Nejdřív nahraj soubor se spotřebou"** – v nabídce není žádný vhodný podklad; nahraj ho ve sbalené sekci Podklady nad stolem (viz [Nabídkovač](nabidkovac.md)).

### Tři režimy – co má baterie dělat (sekce 3 vstupů)

Baterie umí kromě srážení špiček ještě **obchodovat na spotovém trhu**: nakoupit
elektřinu v hodinách, kdy je levná, a v drahých ji vydat. V Česku byl v roce 2025
rozdíl mezi nejlevnější a nejdražší čtvrthodinou dne v polovině dnů větší než
**3 000 Kč/MWh**, takže je z čeho vydělávat.

| Režim | Co baterie dělá | Kdy ho zvolit |
|---|---|---|
| **Peak shaving** (výchozí) | Jen sráží špičky a šetří na platbě za výkon. | Standardní nabídka; klient nechce nebo nemůže obchodovat. |
| **Kombinace** | Sráží špičky a ve zbytku obchoduje. Model si **u každého měsíce sám vybere**, co vydělá víc. | Nejčastější volba – vytěží baterii naplno. |
| **Spot** | Baterie jen obchoduje, rezervovaná kapacita zůstává jak je. | Plochý profil, kde není co srážet — baterie se pak platí jen z obchodu. |

**Kombinace nikdy nevyjde horší než čistý peak shaving.** Model začíná u dnešního
chování (srazit špičku co nejhlouběji) a strop pustí výš jen tam, kde obchod
vydělá víc, než stojí vyšší platba za výkon — typicky v měsících, jejichž maximum
neurčuje roční rezervaci (u testovacího profilu to byly jarní a podzimní měsíce,
kdežto v zimě model držel strop dole).

**Špičky mají vždy přednost.** Baterie si nejdřív odloží energii na sražení všech
špiček, které v následujících hodinách přijdou, a teprve zbytek kapacity a výkonu
smí obchodovat. Navíc si drží rezervu (výchozí 10 % kapacity) na to, že skutečný
odběr bude jiný než plánovaný. Nabíjení nikdy nezvedne měsíční maximum — takže si
baterie obchodem nemůže sama prodražit platbu za výkon.

**Max. dodávka do sítě (kW).** Prázdné = výkon baterie, **0 = baterie do sítě nedodává**
a jen posouvá vlastní spotřebu. Vybít do vlastní spotřeby je totiž **cennější než
prodat**: klient se vyhne celé nákupní ceně včetně distribuce, kdežto za dodávku
dostane jen spotovou cenu mínus marži obchodníka. U velkého odběru proto model do
sítě téměř nedodává. Pozor: dodávka do sítě potřebuje licenci a rezervovaný výkon
pro dodávku — to kalkulátor neřeší, jen na to upozorní.

### Co znamenají výstupní hodnoty

#### Dlaždice (KPI) – hlavní čísla na první pohled
Ukazují se pro rok zvolený přepínačem:

| Dlaždice | Co znamená |
|---|---|
| **Roční úspora (rok)** | Kolik klient ušetří za rok. Pod tím rozpad „z toho X i bez investice" (viz níže). U 2027 je to modelový odhad NTS. |
| **Reálná návratnost** | Kdy investice naskočí do plusu **včetně O&M a degradace úspor**. **Tohle číslo rozhoduje o doporučení** a mění se přepínačem „Návratnost z". V podtitulku je pro srovnání prostá návratnost („cena ÷ úspora jednoho roku"), která O&M ani stárnutí nezná. Podrobně v sekci **🔑 Tři čísla návratnosti** hned pod touhle tabulkou. Nikdy tu nestojí „nevrátí se" — viz „Vždycky je vidět číslo" níž. |
| **NPV (N let)** | Čistá současná hodnota investice na horizontu (default 10 let), případně IRR. **Právě NPV řídí výběr doporučené varianty.** |
| **Nová rez. kapacita** (rok 2026) | Jaká RK bude po instalaci baterie sjednaná. Pod tím fyzický „strop" baterie a rezerva. |
| **Rezervovaný příkon** (rok 2027) | Rezervovaný příkon v modelu 2027 (případně jeho snížení, když je zaškrtnuté). |
| **Investice** | Cena vybrané varianty bez DPH; pod tím celkový výkon / kapacita baterie. Který produkt a kolik kusů je v nadpisu výsledku nad dlaždicemi. |

#### 🔑 Tři čísla návratnosti a jak spolu souvisejí
Nejčastější zádrhel při čtení výsledku: appka ukazuje **tři různé návratnosti** a všechny jsou správně – jen každá odpovídá na jinou otázku. Tady je celý řetěz na jednom reálném příkladu (**nabídka VRL**, BESS 100 kW / 330 kWh za 1 500 000 Kč, roční úspora 2027 **394 419 Kč**):

| Číslo | Kde ho vidíš | Jak se počítá | Co v něm **není** |
|---|---|---|---|
| **3,8 roku** — prostá návratnost | podtitulek dlaždice „Návratnost", řádek *Model 2027* v tabulce návratností | `1 500 000 ÷ 394 419` | provozní náklady (O&M), stárnutí baterie; **vždy** počítá z celé úspory → přepínačem se nemění |
| **4,23 roku** — reálná, volba *Celá úspora* | velké číslo v dlaždici „Návratnost", řádek *Reálně*, řádek ◄ v tabulce po letech | z 394 419 Kč/rok se odečte **O&M 30 000 Kč/rok** (2 % z ceny) a úspora každý rok klesne o **1,5 %** (degradace); po 4 letech je nasčítáno 1 422 529 Kč, zbylých 77 471 Kč přijde během 5. roku | — (to je „hotové" číslo) |
| **7,12 roku** — reálná, volba *Jen přínos baterie* | totéž po přepnutí přepínače | stejný výpočet, ale ze základu **251 977 Kč/rok** místo 394 419 | úspora **142 442 Kč/rok**, kterou klient dostane i bez baterie (snížením rezervovaného příkonu z 600 na 294 kW) |

**Jak to číst:**

| Otázka klienta | Číslo, kterým odpovíš |
|---|---|
| „Za jak dlouho se mi vrátí celý projekt (nová rezervace + baterie), i s provozem?" | **4,23 roku** |
| „A kdybych si tu rezervaci snížil sám – za jak dlouho se vrátí ta baterie?" | **7,12 roku** |
| „Kolik to zhruba je, od oka?" | 3,8 roku (ale nezmiňuj to jako slib – nezná O&M) |

> ⚠️ **O doporučení („nedoporučeno" / práh 5 let) rozhoduje vždy to reálné číslo**, ne prostá návratnost. Proto může varianta s prostou návratností 3,8 roku vyjít jako nedoporučená – reálně je na 7,12 letech.

> 💡 Rozdíl mezi 4,23 a 7,12 je celý v tom, **komu připíšeš úsporu z úpravy rezervace**. Když ji děláte v rámci projektu, patří do ekonomiky projektu (4,23). Když si ji klient umí zařídit sám, poctivější je ukázat, co přidá samotná baterie (7,12).

#### Dvě čtení návratnosti – přepínač „Počítat návratnost z"
Část úspory klient získá i **bez investice** – stačí si u distributora zoptimalizovat sjednanou rezervaci (tzv. „audit RK zdarma"). Otázka „vyplácí se baterie?" má proto dvě legitimní odpovědi a appka počítá **obě** – přepínačem v hlavičce výsledku si vybíráš, která řídí NPV, reálnou návratnost, odznaky „nedoporučeno" i pořadí variant.

| Volba | Co počítá | Kdy ji použít |
|---|---|---|
| **Celá úspora** (výchozí) | celý rozdíl proti dnešnímu stavu – „dnešní faktura → faktura po instalaci", včetně úspory ze souběžné úpravy rezervace | když se klientovi prodává **projekt jako celek** a úpravu rezervace děláte v rámci něj |
| **Jen přínos baterie** | jen to, co přinese sama baterie nad rámec toho, co jde získat i bez investice | když chceš vědět, jestli se vyplácí **samotná investice** – přísnější a obhajitelnější před klientem, který si rezervaci umí snížit sám |

Rozdíl obou = řádek „Úspora hned bez investice" v kartě roku. Dvě reálné nabídky pro srovnání:

| Nabídka | Volba | Základ (Kč/rok) | NPV | IRR | Reálná návratnost | Doporučeno |
|---|---|---|---|---|---|---|
| **VRL** (BESS 100/330, RP 600 kW) | Celá úspora | 394 419 | **+797 146 Kč** | — | 4,23 roku | ✅ ano |
| | Jen přínos baterie | 251 977 | −105 154 Kč | — | 7,12 roku | ❌ ne |
| **hydra** (BESS 100/330, RP 560 kW) | Celá úspora | 334 995 | **+420 727 Kč** | 14,1 % | 5,09 roku | ❌ těsně ne |
| | Jen přínos baterie | 207 600 | −386 261 Kč | 1,7 % | 9,07 roku | ❌ ne |

Obě čísla jsou pokaždé správně – liší se tím, co počítáš jako zásluhu baterie. Všimni si, že volba umí překlopit i odznak „doporučeno" (VRL) a u obou nabídek mění NPV z kladného na záporné.

> ℹ️ Přepnutí **nic nepřepočítává** (obě sady spočetl server dopředu) a **nemění uložený výsledek** – je to jen způsob zobrazení. Volba se pamatuje v prohlížeči, ne u nabídky.

#### Tabulka „Tři čísla návratnosti"
V záložce *Ekonomika*, pod kartami roků. Tři řádky, nejdůležitější první:
- **Reálná (celý horizont v NTS 2027)** – zvýrazněný první řádek, **tohle číslo rozhoduje o doporučení.** Vychází ze stejného cash flow jako NPV (včetně O&M a degradace úspor), takže je delší než prostá návratnost, a odpovídá řádku ◄ v tabulce „Ekonomika po letech". V popisce je vidět, z jakého základu se počítá (celá úspora / přínos baterie) – to se mění přepínačem v hlavičce.
- **Prostá 2027** – „cena ÷ roční úspora 2027". **Modelový odhad, ne finální cena** (závazný výměr ERÚ vyjde ~11/2026). Sleva „AKU" se na peak-shavingovou baterii **nevztahuje** (baterie uvnitř odběru nic nevrací do sítě).
- **Prostá 2026** – jen **informativně**, do rozhodování nevstupuje. Co se dnes nabízí, se instaluje a spouští už v NTS 2027, takže rok na starém tarifu nikdo neodžije.

Pod tabulkou je sbalený blok **ⓘ Proč se čísla liší** — celé metodické vysvětlení včetně tarifů T1/T2. Dřív byl tenhle text rozepsaný drobným písmem mezi čísly, což u desátého výpočtu spíš zdržovalo.

##### Vždycky je vidět číslo (od 28. 7. 2026)
Server počítá reálnou návratnost jen do horizontu NPV (default 10 let). Co se v něm nevrátí, nemá
`payback_roky` a appka tam dřív psala **„nevrátí se"** — což se před klientem nedalo použít.
Nově je na tom místě vždycky číslo:

| Zápis | Co znamená | Odkud je |
|---|---|---|
| `6,12 let` | reálná návratnost | spočítal server v horizontu |
| `~14,24 let` | **dopočet za horizont modelu** — vlnovka říká, že je to odhad | chybějící část investice se dělí cash flow dalších let, které dál klesá stejným tempem jako na konci rozpisu (degradace úspor) |
| `12,4 let (prostá)` | reálná návratnost **neexistuje** ani teoreticky, protože roční úspora nepokryje ani provozní náklady (O&M) | poslední záchrana: prostá návratnost, která O&M ani degradaci nezná |

Najetím myší na číslo se ukáže vysvětlení. **Dopočet za horizont je orientační** — ceny distribuce
po roce 2036 nikdo nezná a tempo degradace je modelové. Na výběr varianty ani na odznak
„nedoporučeno" tenhle dopočet **nemá vliv**: o obojím pořád rozhoduje NPV a práh, který takové
varianty stejně odmítne (jsou hluboko nad ním).

#### Ekonomika – porovnání let (dvě karty vedle sebe)
V záložce *Ekonomika*. Vlevo je **2027** (ten rozhoduje, odznak *rozhoduje*), vpravo **2026** (odznak *informativní*). Zvýrazněná (rámečkem) je karta roku podle přepínače.

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
- **… z toho vědomé překročení RP** – objeví se, jen když optimalizace zvolila RP pod nejvyšší měsíční špičkou (viz níže).

##### Vědomé překročení RP (jen model 2027, jen se zaškrtnutým snížením)
V NTS se rezervovaný příkon sjednává **jednou na celý rok** – žádné měsíční dokupy jako v 2026 neexistují. Zaplatí se `RP × kapacitní sazba` **každý měsíc**, k tomu naměřené měsíční maximum × špičková sazba, a když maximum přeleze RP, ještě sazba za překročení.

Z toho plyne, že u profilu s jednou vybočující špičkou bývá levnější nastavit RP **pod ni** a v tom jednom měsíci překročení zaplatit: snížení RP o 1 kW ušetří **12× kapacitní sazbu** za rok, zatímco překročení stojí sazbu jen za ten měsíc, kdy nastane. Na modelových sazbách ČEZ VN to znamená, že v měsících na tarifu **T1** se snížení vyplatí, dokud je RP překročeno **nejvýš 3× do roka**; na **T2** se nevyplatí nikdy (kapacitní složka je tam příliš levná).

Optimalizace tohle hledá sama a řádek *… z toho vědomé překročení RP* ukáže, v kolika měsících s tím počítá a za kolik. Ve výsledku se navíc objeví upozornění s konkrétním RP a částkou.

> ⚠️ **Ověř smlouvu o připojení.** Model počítá jen s cenou překročení podle sazebníku. Že překročení RP je technicky i smluvně přípustné, appka posoudit neumí – to je na obchodníkovi.

> 📸 SCREENSHOT: dvě karty „Rok 2026" a „Rok 2027" vedle sebe s rozpadem úspory

#### Graf „Odběr ze sítě – měsíční maxima"
Sloupcový graf po měsících:
- **modrý sloupec „bez baterie"** = naměřené měsíční maximum odběru,
- **zelený sloupec „s baterií"** = maximum po srážce baterií (u 2026 držení jednoho ročního stropu, u 2027 srážení po měsících co nejhlouběji),
- **čárkované čáry** = sjednaná hodnota dnes a po instalaci, **v jednotkách zobrazeného roku**:
  - rok **2026** → „rezervovaná kapacita nyní" / „nová rezervovaná kapacita" (RK),
  - rok **2027** → „rezervovaný příkon nyní" / „rezervovaný příkon po instalaci" (RP).

Najetím myší na sloupec se ukáže přesná hodnota. Graf se překreslí podle přepínače roku i podle vybrané varianty.

> ℹ️ **Proč jsou ty dvě nové hodnoty různé.** Nová **RK** (rok 2026) = fyzický strop baterie + bezpečnostní rezerva (default 5 %). Nové **RP** (rok 2027) může být klidně **nižší**: v NTS se kapacitní složka platí 12× za rok, takže se vyplatí posadit RP i pod nejvyšší měsíční špičku a v jednom dvou měsících zaplatit překročení. Na nabídce „hydra" tak vyšla nová RK **328 kW**, ale nové RP **291 kW** – obojí správně, jen pro jiný tarif. Do 27. 7. 2026 graf kreslil vždy RK, i když byly sloupce z modelu 2027, takže to vypadalo jako rozpor mezi grafem a tabulkou.

> 📸 SCREENSHOT: graf měsíčních maxim se čtyřmi prvky legendy (bez baterie / s baterií / sjednaná hodnota nyní / po instalaci)

#### Graf „Průběh v čase" (nitkový graf)
Zatímco graf měsíčních maxim ukazuje **výsledek**, tenhle ukazuje **děj**: co se v odběrném místě odehrává minutu po minutě celý rok. Otevřeš ho tlačítkem **„Zobrazit průběh v čase"** (načítá se na vyžádání – je to celoroční 15minutová simulace, pár vteřin).

Graf má tři pásy nad sebou a společnou časovou osu:
- **horní pás – odběr (kW):** šedá nitka = odběr **bez baterie** (co by teklo ze sítě dnes), zelená nitka = odběr **ze sítě po instalaci baterie**. Rozdíl mezi nimi je přesně to, co baterie v tu chvíli kryje. Tečkovaná čára = strop, který baterie drží, čárkované čáry = sjednaná rezervace dnes a po instalaci.
- **prostřední pás – výkon baterie (kW):** nad nulou baterie **vybíjí** (kryje špičku), pod nulou se **nabíjí** ze sítě.
- **spodní pás – stav nabití (%):** kolik energie v baterii zbývá. Když se blíží nule ve chvíli špičky, je návrh na hraně.

**Přiblížení (zoom).** Začíná se na celém roce. Přibližovat jde čtyřmi způsoby:
- **kolečkem myši** (přibližuje k místu, kde máš kurzor),
- **tažením myši** vybereš výsek, který se roztáhne přes celý graf,
- **tlačítky Rok / Měsíc / Týden / Den / 6 hodin / 15 min**,
- **klikem do přehledové lišty** dole (celý rok v malém, zvýrazněný obdélník = co je právě vidět).

Posouvat jde šipkami **← →** nebo tažením se **Shiftem**, dvojklik oddálí, **Celý rok** vrátí výchozí pohled. Pod grafem je vždy napsáno, jaký úsek koukáš a **kolik času představuje jeden bod** – při plném přiblížení „15 min (přesné hodnoty)".

> **Proč nejde přehlédnout špičku.** Při pohledu na celý rok se do jednoho bodu grafu vejde skoro celý den, takže se nekreslí jen průměr, ale i **pásmo od minima po maximum** (světlejší plocha kolem nitky). Špička tak zůstane vidět i z dálky – přiblížením se pásmo zužuje, až při 15 minutách splyne s nitkou a čteš přesné naměřené hodnoty. Najetím myší se ukáže bublina s hodnotami pod kurzorem.

**Události.** Pod grafem je seznam vypíchnutých okamžiků roku – **kliknutím na řádek se graf přiblíží přesně na ten moment**:
- **Špičky** – roční a měsíční maximum odběru (bez baterie i po baterii; to druhé je hodnota, za kterou se v daném měsíci platí),
- **Sedla** – roční a měsíční minima (výchozí je vypnuté, ať seznam nezahltí),
- **Baterie** – nejsilnější vybíjení a nabíjení, nejhlubší vybití (nejnižší stav nabití) a nejdelší souvislé vybíjení,
- **Překročení** – měsíce, kdy odběr ze sítě přesáhl sjednanou rezervaci (nejdražší okamžiky roku).

Kategorie se zapínají a vypínají tlačítky s barevnou tečkou; zapnuté události se zároveň kreslí jako body přímo v grafu.

Graf respektuje přepínač roku: **2026** ukazuje držení jednoho ročního stropu, **2027** srážení špičky zvlášť v každém měsíci (proto se v něm tečkovaný strop mění po měsících). Při přepnutí roku nebo kliknutí na jinou variantu se simulace přepočítá.

> 📸 SCREENSHOT: nitkový graf přiblížený na jeden zimní den – špička ráno, zelená nitka sražená na strop, pod ní vybíjení baterie a klesající stav nabití

#### Citlivost návrhu
V záložce *Grafy odběru*, pod grafem měsíčních maxim: co by se stalo, kdyby byl profil o **±5 %** silnější/slabší – jestli by nasazená rezerva RK zvládla i „silnější rok", nebo by hrozily měsíční dokupy/pokuty. Je to rychlá kontrola, jak moc je návrh „na hraně".

#### Průběh v čase a spotová cena
V obchodních režimech přidá nitkový graf **čtvrtý pás se spotovou cenou** (Kč/MWh,
modrá) — je z něj vidět, proč se baterie zachovala tak, jak se zachovala: nabíjí
v cenovém sedle, vybíjí ve špičce. Pás se dá vypnout zaškrtávátkem v legendě, a když
je v datech záporná cena (v roce 2025 se to stalo 323 hodin), zobrazí se i nulová
čára. V bublině u kurzoru je navíc rozpad **„z toho špička / obchod"** — kolik
kilowattů šlo na srážení špičky a kolik na obchod.

Graf jede ze **stejné simulace jako ekonomika**, ne z peak-shavingového modelu:
čísla v grafu a v tabulkách se tedy nemohou rozejít. Přepínač roku (2026/2027) na
průběh v obchodních režimech nemá vliv — stropy jsou dané výsledkem výpočtu.

#### Obchod na spotu (záložka — jen v režimech Kombinace a SPOT)
Tři karty, které odpovídají na otázku „kde ty peníze vlastně jsou":

1. **Co obchod přinesl.** Vyhnutý nákup a dodávka do sítě mínus opotřebení baterie
   obchodními cykly = zisk za rok. Poslední řádek říká, kolik by obchod přinesl, kdyby
   měl peak shaving **absolutní prioritu** — rozdíl je to, co model vydělal tím, že
   v některých měsících špičku vědomě pustil výš.
2. **Energie.** Kolik se nabilo ze sítě, kolik se vybilo do vlastní spotřeby, kolik
   se dodalo do sítě a kolik cyklů to znamenalo. U velkého odběru bývá dodávka do
   sítě nulová — vyhnutý nákup je cennější.
3. **Rozhodnutí po měsících.** Pro každý měsíc cílový strop, nejnižší udržitelný strop,
   naměřené maximum bez baterie, zisk obchodu a počet cyklů. Kde je cílový strop
   vyšší než nejnižší udržitelný, je odznak **„strop puštěn výš"** — tam model
   usoudil, že obchod vydělá víc než úspora na platbě za výkon. Typicky jde
   o měsíce, jejichž maximum roční rezervaci neurčuje.

**Jak to klientovi vysvětlit:** „V zimě baterie sráží špičky, protože tím určujete
sjednanou rezervaci na celý rok. V letních měsících, kde je vaše maximum tak jako tak
nižší, ji pustíme obchodovat — to vydělá víc než pár kilowattů rezervace, které
byste stejně neušetřili."

#### Ekonomika po letech (záložka)
Tabulka rok po roce na celém horizontu (default 10 let): tarif toho roku, přínos baterie, O&M (údržba), cash-flow roku, kumulovaná úspora a kumulované cash-flow. Řádek označený `◄` = rok, kdy se investice **poprvé vrátí**. Poslední hodnota „Kum. disk. CF" = NPV varianty.

#### Varianty k rozhodnutí (karty pod dlaždicemi)
Tabulka srovnání odpovídá na otázku „která je nejlepší podle NPV". Tyhle karty odpovídají na otázky, které klade zákazník:

| Karta | Kritérium | Kdy ji nabídnout |
|---|---|---|
| **◆ Nejvhodnější** | nejvyšší NPV | výchozí doporučení — nejlepší ekonomika na horizontu |
| **Nejlevnější** | nejnižší investice | když klienta limituje rozpočet, ne návratnost |

Klik na kartu ji vybere a překreslí celý výsledek. Vítěz se hledá **nezávisle na řazení tabulky** — když si ji seřadíš po svém, karty se nemění. Pruh dole ukazuje NPV varianty proti nejlepší; u záporného NPV je pruh nulový. Když nejvyšší NPV a nejnižší cena padnou na tutéž baterii (nebo je použitelná jen jedna varianta), karty se skryjí — není co srovnávat.

> Kritérium **„největší osekání špiček"** tu bylo do 28. 7. 2026, ale ukázalo se jako nepoužitelné: nejnižší rezervace sama o sobě nic neříká, jen vždycky ukázala na nejdražší baterii v katalogu.

#### Srovnání variant (záložka)
Tabulka zvažovaných baterií. První řádek = doporučená (dle NPV). Kliknutím na jiný řádek se celý výsledek přepočítá pro tu variantu — čísla jsou nad tabulkou, takže je změna hned vidět (dřív byla tabulka na konci dlouhé stránky a přepisovala čísla mimo obraz). Varianta, jejíž **reálná** návratnost přeleze firemní práh, nese odznak **„nedoporučeno"** – i když prostá návratnost 2027 vypadá pod prahem. Do 27. 7. 2026 rozhodovala jen prostá návratnost modelu 2026, takže dobrá ekonomika 2027 na odznak neměla vliv.

Výchozí zobrazení jsou **3 nejlepší varianty**, ale spočítané jsou všechny baterie, které šly do výpočtu (jedna nejlepší konfigurace počtu kusů za produkt). Tlačítkem **„Zobrazit všechny (N)"** v hlavičce tabulky rozbalíš celý seznam – pro manažerské rozhodnutí, kdy nejde jen o nejvyšší NPV (dostupnost, preferovaný dodavatel, velikost investice). Zpátky se přepneš tlačítkem **„Jen 3 nejlepší"**.

**Řazení:** klikem na záhlaví sloupce si tabulku seřadíš podle vlastního kritéria (druhý klik obrátí směr) – třeba podle nejnižší ceny nebo nejrychlejší návratnosti místo NPV. Ve zkráceném zobrazení pak vidíš 3 nejlepší **podle zvoleného kritéria**. Odkazem *zpět na doporučené pořadí* se vrátíš k řazení dle NPV.

> Graf měsíčních maxim a citlivost se předpočítají jen pro 3 nejlepší varianty (u celého ceníku by to k výpočtu přidalo ~15 s). U ostatních se dopočítají **až po kliknutí na řádek** – chvilku to trvá („Počítám graf pro tuhle variantu…") a pak už se to uloží k nabídce.

### Jak na…
- **Spočítat peak shaving od nuly:** nahraj profil v Podkladech → vlevo v sekci 1 klikni **Načíst profil** → v sekci 2 vyber **distributora** a **hladinu**, opiš **RK z faktury** → **Spočítat peak shaving**.
- **Zohlednit model 2027 se snížením příkonu:** vyplň **Rezervovaný příkon** ze smlouvy, zaškrtni **„uvažovat snížení RP"**, spočítej a přepni nahoře na **2027**. (Bez vyplněného RP se dosadí RK a celý model 2027 vyjde podhodnocený – viz „RK vs. RP" výše.)
- **Porovnat víc baterií:** hned pod dlaždicemi jsou **karty variant** (nejvhodnější podle NPV a nejlevnější) – klik na kartu překreslí výsledek. Kdo chce vidět celý katalog, přepne na záložku **Srovnání variant** a klikne na **„Zobrazit všechny (N)"**.
- **Počítat jen vybrané baterie:** v sekci 3 vstupů přepni na **Jen ručně vybrané**, v seznamu zaškrtni produkty (jde v nich hledat) a spočítej. Výběr se pamatuje do dalšího výpočtu.
- **Seřadit srovnání po svém:** klikni na záhlaví sloupce (cena, návratnost, výkon…) – druhý klik obrátí směr, odkaz *zpět na doporučené pořadí* vrátí NPV.
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
| Práh doporučené návratnosti | `max_navratnost_roky_peak_shaving` | 5 let | poměřuje se s **reálnou** návratností (rok 1 tarif 2026, dál NTS 2027, vč. O&M a degradace); nad ním se varianta označí „nedoporučeno" |
| Diskontní sazba (NPV) | `ps_diskontni_sazba` | 8 % | pro NPV/IRR |
| Horizont NPV | `ps_horizont_npv_roky` | 10 let | délka ekonomiky po letech |
| O&M (údržba) | `ps_oam_procenta_capex_rok` | 2 % CAPEX/rok | provozní náklady |
| Degradace úspor | `ps_degradace_uspor_procenta_rok` | 1,5 %/rok | pokles přínosu baterie v čase |

**Obchodování na spotu** (režimy Kombinace/SPOT) – vlastní sekce v záložce Peak shaving:

| Parametr | Klíč | Výchozí | Význam |
|---|---|---|---|
| Marže obchodníka – nákup | `spot_marze_nakup_kc_mwh` | 200 Kč/MWh | o kolik je nákup dražší než spot (**marže není naše, ale obchodníkova**) |
| Marže obchodníka – prodej | `spot_marze_prodej_kc_mwh` | 200 Kč/MWh | o kolik je prodej levnější než spot |
| Regulované složky za odebranou MWh | `spot_regulovane_nakup_kc_mwh` | 260 Kč/MWh | použití sítí + systémové služby + POZE; stejná hodnota jako u PPA |
| Složky za dodanou MWh | `spot_regulovane_prodej_kc_mwh` | 0 | dodávka do sítě distribuci neplatí |
| Daň z elektřiny | `spot_dan_z_elektriny_kc_mwh` | 0 | u akumulace je otázka osvobození (28,30 Kč/MWh) – **k ověření** |
| Cyklů životnosti baterie | `spot_cyklu_zivotnosti` | 6 000 | fallback, když produkt nemá vlastní hodnotu v katalogu |
| Limit obchodních cyklů za rok | `spot_max_cyklu_rok` | 0 = bez limitu | pojistka kvůli záruce; náklad opotřebení počet cyklů reguluje sám |
| Rezerva kapacity pro peak shaving | `spot_bezpecnostni_rezerva_procenta` | 10 % | polštář na to, že skutečný odběr bude jiný než plánovaný |
| Referenční rok spotových cen | `spot_referencni_rok` | 0 = nejnovější | který rok cen se použije |

V **katalogu produktů** je navíc sloupec **„Cyklů životnosti"** – z něj a z ceny baterie
se počítá **náklad opotřebení** (Kč za MWh proteklou baterií). Je to nejcitlivější
číslo celého obchodního modelu: u 2h baterie za 7 mil. Kč s 6 000 cykly ukrojí
z hodnoty obchodu polovinu (742 → 362 Kč/kWh/rok).

Podrobné vzorce (simulace baterie, fair baseline 2026, dvousložkový tarif 2027, NPV/IRR, koeficient AKU, obchodní režimy) viz [technický souhrn kap. 4](../../moduly/peak-shaving.md) a [rešerši spotových cen](../../reserze_kalkulator/spot-arbitraz-cr-2025.md).

### Datový model (PostgreSQL)
- **`spotreba_profil`** – 15min profil odběru (`nabidka_id`, `cas`, `hodnota_kw`, `zdroj_dokument_id`). Unique `(nabidka_id, cas)`. Zpracování profilu **nahrazuje celý** profil nabídky (poslední vyhrává), duplicitní časy z podzimního přechodu času slučuje na maximum.
- **`sazby_distributoru`** – sazby dle `distributor` × `napetova_hladina` × `struktura_tarifu` (`stara_2026`/`nova_2027`); ceny v JSONB `parametry` (NULL = „čeká na sazby ERÚ"), historie přes `platne_od`/`platne_do`, příznak `je_modelovy_odhad`.
- **`technologie`** – katalog; pro `typ = baterie` musí mít **oba** parametry `vykon_kw` i `kapacita_kwh` (validace v API); vlastní sloupce v JSONB `extra`.
- **`katalog_sloupce`** – definice vlastních (admin) sloupců katalogu.
- **`navrhovana_reseni`** – výstup výpočtu v `popis_json` (`typ_reseni = peak_shaving`).
- **`vypoctova_nastaveni`** – manažerské parametry (viz tabulka výše).
- **`spotove_ceny`** – ceny denního trhu (`trh`, `cas_utc`, `interval_min`, `cena_eur_mwh`, `cena_kc_mwh`, `zdroj`), unique `(trh, cas_utc)`. Rok 2025 se **seeduje při startu** z přiloženého souboru `backend/app/nabidkovac/data/spot_dam_cz_2025.csv.gz`, takže produkce nechodí na internet. Další rok přidá `python -m scripts.import_spot_ceny --rok 2026 --csv` (stáhne ceny + kurzy ČNB a vytvoří datový soubor) a `--z-csv --do-db` (nahraje do DB). Ceny se drží v granularitě trhu (hodinové do 30. 9. 2025, od 1. 10. 2025 čtvrthodinové) a na 15 minut se rozpadají až při čtení.

### API (prefix `/nabidkovac`, přes Caddy `/api`)
| Metoda / cesta | Právo | Popis |
|---|---|---|
| `POST /dokumenty/{id}/zpracuj-profil` | `nabidkovac` | naparsuje XLS/XLSX/CSV → `spotreba_profil` (nahradí celý profil) |
| `GET /nabidky/{id}/peak-shaving/profil-souhrn` | `nabidkovac` | počet intervalů, rozsah (od/do), špička `max_kw` |
| `POST /nabidky/{id}/peak-shaving/vypocet` | `nabidkovac` | spustí výpočet, uloží do `navrhovana_reseni` |
| `GET /nabidky/{id}/peak-shaving/prubeh` | `nabidkovac` | 15min průběh pro nitkový graf (na vyžádání, neukládá se) |
| `GET /sazby` | `nabidkovac` | přehled sazeb (načítá i panel pro validaci) |
| `POST/PUT/DELETE /sazby[/{id}]` | `nabidkovac_katalog` | správa sazeb |
| `GET/POST/PUT/DELETE /katalog-sloupce`, `/technologie` | čte `nabidkovac`, edituje `nabidkovac_katalog` | katalog + vlastní sloupce |

**Vstup výpočtu:** `{ distributor, napetova_hladina, rezervovana_kapacita_kw }` + volitelně `cena_energie_kc_mwh`, `rezervovany_prikon_kw`, `uvazovat_snizeni_rp`, `max_vykon_stridace_kw`, `baterie_ids` (ruční výběr produktů z katalogu; prázdné = celý katalog), `rezim` (`peak_shaving` / `kombinace` / `spot`, výchozí `peak_shaving`), `spot_referencni_rok`, `max_export_kw` (0 = bez dodávky do sítě).
**Výstup (`popis_json`):** `vstup`, `sazby`, `max_navratnost_roky`, `doporucena`, `varianty` (**všechny** spočítané varianty seřazené dle NPV; `graf` a `citlivost_stropu` nese jen první trojice), `graf`, `citlivost_stropu`, `upozorneni`. Každá varianta nese `ekonomika_2026`, `ekonomika_2027`, NPV/IRR a návratnosti; v obchodních režimech navíc `rezim`, `zisk_spot_kc` a `ekonomika_spot` (rozpad zisku, energetická bilance, počet cyklů a **rozhodnutí po měsících** – zvolený strop vs. nejnižší udržitelný).

**Průběh v čase:** `GET /nabidky/{id}/peak-shaving/prubeh?varianta=N&rok=2026|2027` vrátí rozepsanou 15minutovou simulaci (odběr, odběr ze sítě, výkon baterie ±, stav nabití), schodovitý strop, referenční čáry, souhrn energií a seznam událostí. **Neukládá se** do řešení (~35 000 hodnot na variantu a rok) – počítá se na vyžádání (~0,1 s) ze stejné fyziky jako ekonomika. Odpověď má ~1,2 MB, gzipem (`GZipMiddleware`) ~250 kB. Volá ji FE po otevření sekce „Průběh v čase".

**Dopočet varianty:** `POST /nabidky/{id}/peak-shaving/varianta-detail` s `{ "index": N }` (pořadí ve `varianty`) dopočítá graf + citlivost pro variantu mimo první trojici a uloží je do řešení. Volá ho FE při kliknutí na řádek srovnání.

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
  components/PeakShavingPanel.jsx  – pracovní stůl: vstupy + výsledek (OZ)
  styles/global.css                – celé sdílené rozvržení (gs-desk, gs-panel, gs-step,
                                     gs-varianta, gs-seg, gs-tabs, gs-meta, gs-chk, gs-unit,
                                     gs-table, gs-pill…) — vzor pro ostatní moduly
  styles/nabidkovac.css            – jen zbytky specifické pro nabídkovač (hlavička zákazníka,
                                     sbalené podklady, ruční výběr baterií)
  components/GrafOdberu.jsx        – SVG graf měsíčních maxim (bez knihovny)
  components/GrafPrubehu.jsx       – nitkový graf průběhu se zoomem rok → 15 min (bez knihovny)
  pages/NabidkovacKatalog.jsx      – admin: sazby, katalog, výpočtová nastavení
  api.js                           – helpery peakShavingVypocet, profilZpracuj, peakShavingProfilSouhrn, peakShavingPrubeh, sazby*
```

### Časté potíže / co dělat, když…
- **„Profil spotřeby nelze použít: …" (chyba 422)** → profil není použitelný jako roční: rozsah < 350 dní, chybí kalendářní měsíce, díry > 2 % intervalů, nebo překrývající se okrajové měsíce. Nahraj úplnější roční export. (Profil delší než rok se automaticky ořízne na posledních 12 celých měsíců s upozorněním.)
- **„Zpracování profilu selhalo: …" (chyba 422)** → špatný formát souboru. Parser čeká XLS s listem `export` a sloupci `Datum` (`DD.MM.RRRR HH:MM:SS`) a `Profil +A [kW]`, nebo odpovídající XLSX/CSV. Zkontroluj, že jde o **15min profil činného odběru** z portálu distributora.
- **„Tenhle dokument není profil spotřeby"** → podklad má špatný typ; načítat lze jen dokumenty typu „spotřeba" (`spotreba_csv`) nebo „jiný".
- **Tlačítko „Spočítat" je šedé** → přečti **kontrolní seznam pod tlačítkem**: řádek s `!` říká, co chybí (profil, kladná RK, sazby 2026 pro zvolenou kombinaci distributor/hladina, nebo aspoň jedna zaškrtnutá baterie při ručním výběru). Sazby se doplňují v Katalogu a výpočtech.
- **„Chybí sazba stara_2026 pro …" (422)** → sazba je NULL („čeká na sazby ERÚ") nebo neexistuje. Doplň v Katalogu (sazby distributorů).
- **Přepínač „2027" je zakázaný** → pro danou kombinaci nejsou spočítané sazby 2027; zobrazí se jen 2026.
- **„Výpočet nenašel použitelnou variantu"** → v katalogu nejsou dostupné baterie s vyplněným výkonem i kapacitou, nebo žádná neustojí špičky. Doplň/zkontroluj katalog technologií.
- **Grafy/rozpis chybí u alternativní varianty** → u variant mimo 3 nejlepší se graf dopočítá až po kliknutí (chvíli to trvá). Když se ani pak neobjeví, je výsledek ze starší verze výpočtu – spusť „Spočítat peak shaving" znovu.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Návratnost se nikdy neukáže jako „nevrátí se".** Backend dál posílá `payback_roky = null`, když se investice v horizontu NPV nevrátí — frontend (`navratnostKZobrazeni` v `PeakShavingPanel.jsx`) místo toho číslo **dopočítá za horizont** z klesajícího cash flow posledních let a označí ho vlnovkou. Když ani to nejde (roční CF je nekladné, tedy úspora nepokryje O&M), ukáže se prostá návratnost s poznámkou „(prostá)". Je to **zobrazovací vrstva** — do NPV, prahu doporučení ani do výběru varianty tenhle dopočet nevstupuje. Řazení srovnání podle návratnosti ale používá stejné číslo, které je v řádku vidět, jinak by varianty s odhadem padaly bez důvodu na konec.
- **Rozvržení „pracovní stůl" je vzor pro ostatní moduly.** Panel se 28. 7. 2026 překlopil z jedné svislé roláky (vstupy roztržené mezi tři karty, výsledek ~2500 px pod nimi) na dva sloupce se záložkami. Všechny sdílené části leží v `global.css` jako `gs-*` — od 28. 7. 2026 tam je i layout stolu (`gs-desk`, `gs-panel`, `gs-step`…), protože ho používá i PPA a prodej. Inventář prvků je ve [Společných prvcích](spolecne-prvky.md).
- **Detail nabídky musí být široký.** `.nb-app.siroky` zvedá šířku obsahu na 1560 px – při původních 1100 px by se dva sloupce nikdy nevešly a stůl by se pořád zalamoval pod sebe.
- **Karta „Podklady" a údaje zákazníka jsou v detailu nabídky sbalené.** Rozbalí se samy jen u čerstvě založené nabídky (chybí název zákazníka, resp. žádné dokumenty). Profil odběru se načítá ve vstupech výpočtu, takže do Podkladů se chodí prakticky jen při zakládání.
- **2027 je modelový odhad, ne cena.** Dokud nevyjde závazný výměr ERÚ (~11/2026), jsou všechna čísla 2027 nezávazná (`je_modelovy_odhad`). Výběr doporučené varianty se řídí modelem **2026**.
- **Sleva „koeficient AKU" se neaplikuje** – peak-shavingová baterie uvnitř odběru nic nevrací do sítě, takže dle definice ERÚ vychází nulová. Prahy U1/U2 v sazebníku jsou předběžné a nechané pro budoucí použití (místa s velkým exportem).
- **Návratnost ≠ celková úspora.** Do návratnosti se počítá jen **přínos baterie** proti optimalizované RK; „audit RK zdarma" je prodejní bonus, který klient dostane i bez investice.
- **Rezervace pod špičkou – 2026 vs. 2027 se řeší jinak.** V **2026** se roční RK běžně nastaví pod celoroční špičku a v překročených měsících se **dokoupí měsíční RK** (1× měsíční sazba); platit místo toho pokutu (1,5×) se nikdy nevyplatí, takže s ní optimalizace nepočítá. Model ale předpokládá, že se dokup stihne sjednat **dopředu** (do posledního pracovního dne předchozího měsíce). V **2027** dokupy neexistují – jediná páka je zvolit RP jednou správně, a tam se místo dokupu platí **sazba za překročení**; optimalizace to zohledňuje jen se zaškrtnutým snížením RP.
- **Cena energie pro ztráty** je jen manažerské nastavení (default 3 000 Kč/MWh bez DPH); panel OZ ji nezadává, i když ji API umí přijmout.
- **Počáteční nabití baterie** v simulaci = plná (zjednodušení v1). EOL derating a vlastní spotřeba PCS se zatím neaplikují.
- **Poznámka k načítání profilu:** načtení **nahradí celý** profil nabídky napříč dokumenty (poslední vyhrává) – ne jen řádky z daného souboru.
- Komponenta `PeakShavingPanel.jsx` importuje z komponent `GrafOdberu.jsx` a `GrafPrubehu.jsx` (žádný `CvdToggle`); barvy grafů řeší CSS tokeny `--c-*` kvůli tmavému režimu a kompenzaci červeno-zelené vady.
- Nitkový graf průběhu si celoroční řady stahuje jednou a slévá je do košů (jeden na pixel šířky, min/max/průměr) až v prohlížeči – zoom je proto okamžitý, bez dalšího volání serveru. Datové řady kreslí **canvas** (`grafPrubehuData.js`), popisky a interakce leží v SVG nad ním; všechny vstupy (kolečko, tažení, pohyb myši) se slévají do jednoho překreslení na snímek. Čistě SVG verze při zoomu zadrhávala – každé překreslení znamenalo ~150 kB textu cest do DOM. Model 2027 se simuluje **po měsících se startem od plné baterie**, stejně jako `ekonomika_2027`; kdyby se simuloval průběžně, ukazoval by graf na začátku měsíce překročení stropu, které v ekonomice není.

## Odkazy
- Technický souhrn (odvození vzorců, seed, historie PR): [`docs/moduly/peak-shaving.md`](../../moduly/peak-shaving.md)
- Nadřazený modul: [Nabídkovač](nabidkovac.md)
- Kód backend: `backend/app/nabidkovac/` (jádro `peak_shaving.py`) · frontend: `frontend/src/components/PeakShavingPanel.jsx`, `GrafOdberu.jsx`, `GrafPrubehu.jsx`, `pages/NabidkovacKatalog.jsx`, `api.js`
