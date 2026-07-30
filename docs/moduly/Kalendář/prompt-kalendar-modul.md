# Prompt: Modul kalendáře (týdenní pohled + přidání aktivity + detail události)

> Zkopíruj tento prompt do svého kódovacího agenta. Popisuje **přesně vzhled a chování** našeho modulu kalendáře.
> Použij **náš existující stack a design systém** (komponenty, tokeny, barvy, ikony, typografii, spacing) — níže popsané barvy a rozměry ber jako referenci vzhledu z návrhu, ne jako hardcoded hodnoty. Rozhraní je celé v **češtině**.

---

## Zadání

Vytvoř modul kalendáře se třemi stavy/obrazovkami:

1. **Základní týdenní pohled** (výchozí)
2. **Modal pro přidání aktivity** (otevře se kliknutím na prázdné pole v mřížce nebo na zelené tlačítko „+")
3. **Popover s detailem události** (otevře se kliknutím na existující aktivitu v mřížce)

Jde o kalendář uvnitř CRM. Aktivity jsou navázané na klienty/kontakty. Design je čistý, vzdušný, se zaoblenými rohy, jemnými stíny a světlým pozadím.

---

## 1) Základní týdenní pohled

### Rozvržení stránky
Dvousloupcový layout: vlevo úzký **postranní panel s filtry** (cca 280 px), vpravo hlavní **plocha kalendáře**.

### Horní lišta kalendáře (nad mřížkou)
Zleva doprava:
- Tlačítko **„Moje filtry"** s ikonou uživatele a šipkou dolů (rozbalovací) — světlé, s rámečkem, zaoblené.
- Segment **„Dnes"** — výrazně zelené vyplněné tlačítko, po stranách šipky `‹` a `›` pro předchozí/následující týden.
- Uprostřed **titulek období**: „29. týden – Červenec 2026" (číslo ISO týdne + měsíc + rok).
- Vpravo přepínač zobrazení **„Týden"** se šipkou dolů (volby min. Den / Týden / Měsíc).
- Tlačítko **„…"** (kontextové menu).
- Kruhové zelené tlačítko **„+"** vpravo (přidání nové aktivity).

### Mřížka týdne
- Sedm sloupců dnů s hlavičkami: **PO 13, ÚT 14, ST 15, ČT 16, PÁ 17, SO 18, NE 19** (zkratka dne + číslo dne).
- Zcela vlevo úzký sloupec s časovou osou.
- Nad hodinovými řádky samostatný řádek **„vícedenní"** (celodenní / vícedenní aktivity).
- Časové řádky odshora: `0:00`, `7:00`, `7:00`, `8:00`, `9:00` … až `19:00`, `23:59` (pozn.: horní část dne je zkomprimovaná — noční hodiny 0:00–7:00 zabírají jeden zúžený blok, dále běží hodinu po hodině; poslední řádek je `23:59`).
- Jemné vodorovné a svislé linky mřížky, neutrální šedá.
- Kliknutí na prázdnou buňku otevře modal pro přidání aktivity s předvyplněným datem a časem podle místa kliknutí.

### Událost v mřížce
- Vykreslená jako zaoblený barevný blok umístěný podle času začátku, výška podle trvání.
- Obsahuje **ikonu typu**, čas a název, případně jméno klienta.
- Barva bloku odpovídá **typu aktivity / kategorii** (viz níže). Příklad z návrhu: telefonát „9:00 zavolat po dovolený, Petr" — světle **růžový** blok s ikonou telefonu.
- Kliknutím se otevře popover s detailem (viz sekce 3).

### Postranní panel s filtry (vlevo)
Odshora:

1. **Mini měsíční kalendář**
   - Titulek „Červenec 2026" se šipkami `‹ ›`.
   - Hlavička dnů: Po Út St Čt Pá So Ne.
   - Mřížka dat včetně přesahů z předchozího/dalšího měsíce (šedě).
   - **Aktuálně zobrazený týden** podbarvený jemně zeleně (řádek 13–19).
   - **Dnešní den** (30) ve zvýrazněném šedém/tmavém kroužku.
   - Kliknutím na den se hlavní kalendář přesune na daný týden.

2. Přepínač záložek **„FILTRY" / „NENAPLÁNOVÁNO"**.

3. Sekce **„UŽIVATELÉ"** (sbalovací, se šipkou) s tlačítkem „+".
   - Položka uživatele s barevným kruhovým avatarem: „Daniel Lupínek" + šipka dolů.

4. Sekce **„TYP AKTIVITY"** — seznam typů, každý s ikonou:
   - **Úkol** (ikona zaškrtávacího políčka)
   - **Schůzka** (ikona bloku/šálku)
   - **Událost** (ikona kalendáře)
   - **Telefonát** (ikona telefonu)
   - **Dopis** (ikona obálky)
   - Fungují jako přepínatelné filtry viditelnosti.

5. Sekce **„ZOBRAZENÍ AKTIVIT"** — dva přepínače (toggle switch):
   - „Schovat realizované"
   - „Zobrazit i zrušené"

6. Sekce **„KATEGORIE"** (sbalovací) — seznam barevných kategorií jako filtry.

### Ostatní
- Vpravo dole plovoucí boční tlačítka (např. „PODPORA") — volitelné, dle našeho standardu.

---

## 2) Modal — přidání / editace aktivity

Otevírá se přes celou obrazovku s tmavým poloprůhledným pozadím (overlay). Vlevo zůstává vidět **náhledový mini denní pruh** (den s vytvářenou aktivitou, navigace `‹ ÚT 4.8. ›`), samotný formulář je v bílé kartě vpravo od něj.

### Hlavička modalu
- Velký nadpis-placeholder **„Doplňte předmět schůzky"** (šedě) — je to zároveň editovatelné pole pro název; text se mění podle zvoleného typu aktivity.
- Vpravo nahoře **„×"** pro zavření.

### Přepínač typu aktivity (řada ikon)
Pět tlačítek vedle sebe, aktivní je zvýrazněné (v návrhu **„Schůzka"** — modrý rámeček/aktivní stav):
Úkol (checkbox) · **Schůzka** (aktivní) · Událost (kalendář) · Telefonát (telefon) · Dopis (obálka).

### Blok „PRIORITA" (vpravo od typů)
Tři volby vedle sebe: šipka dolů (nízká) · **–** (střední, aktivní) · **!** (vysoká).

### Řádek termínu
- **DATUM** — pole s hodnotou „4.8.2026" + ikona kalendáře pro výběr.
- **ZAČÁTEK** — „9:00" se šipkami nahoru/dolů.
- **TRVÁNÍ** — dropdown „30 minut" (+ přepínač celodenní).
- Odkaz **„PŘIDAT PŘIPOMENUTÍ"** (modrý text).

### MÍSTO KONÁNÍ
- Textové pole s placeholderem „Doplňte adresu nebo jiné označení" (ikona špendlíku).
- Vedle tlačítko/odkaz **„U NÁS"** (rychlé vyplnění naší adresy).

### KATEGORIE
- Dropdown „– Vyberte kategorii –" s řadou barevných teček (paleta kategorií) vlevo.

### OTÁZKY K PROJEDNÁNÍ
- Víceřádkové textové pole (textarea).

### Zaškrtávací volby
- ☐ „Schůzka už proběhla"
- ☐ „Soukromá aktivita – bez vazby na klienta"

### Pravý sloupec modalu
- **„KDO SE ZÚČASTNÍ"**
  - Karta účastníka: avatar + „Daniel Lupínek" + role „Vlastník".
  - Kruhové **„+ Přidat účastníka"**.
- **„ČEHO SE TO TÝKÁ"**
  - Kruhové **„+ Přidat další kontext"** (navázání na klienta / obchodní případ).

### Patička modalu
- **„ULOŽIT & OTEVŘÍT"** — zelené vyplněné tlačítko.
- **„ULOŽIT"** — modré vyplněné tlačítko.
- Vpravo dole ikona **zámku** (soukromí/viditelnost).

---

## 3) Popover — detail události

Malá plovoucí karta se stínem a zaoblenými rohy, ukotvená u příslušné události v mřížce.

### Hlavička
- Vlevo kruhová ikona typu (v návrhu **oranžová** ikona kalendáře pro typ „Událost").
- Nadpis **„Porada obchodu"**.
- Pod ním **štítek** s ikonou domečku: „Greensie" (navázaný subjekt/firma).
- Vpravo nahoře ikona **tužky** (editovat) a **„×"** (zavřít).

### Tělo (řádky s ikonami)
- 🟧 barevný čtvereček + název „Porada obchodu".
- 🕐 termín: **„3.8.2026 10:00 – 11:00"**.
- 📍 adresa: „Bedřichovská 2183/16, Praha 8, 182 00, Česká republika".
- 👤 účastníci: organizátor **„Pavel Bureš"** → (šipka) seznam zúčastněných: „Ing. Michael Jílek, Tomáš Jančuk, Michal Šimon, Daniel Lupínek, Vladislav Váňa, …" — dlouhý seznam se **scrolluje** uvnitř karty.

### Patička (akční lišta)
Čtyři akce vedle sebe:
- **„MÁM HOTOVO"** — zelené, ikona zaškrtnutí.
- **„ZRUŠIT"** — ikona „×".
- **„PŘESUNOUT"** — ikona kalendáře (změna termínu).
- **„…"** — další akce.

---

## Barvy, typografie a interakce (reference z návrhu)

- **Primární akce / zvýraznění: zelená** (tlačítka „Dnes", „+", „Uložit & otevřít", „Mám hotovo", zvýraznění aktuálního týdne).
- **Sekundární akce: modrá** (odkazy, „Uložit").
- Barvy aktivit podle typu/kategorie: telefonát **růžová**, událost **oranžová** — obecně každý typ/kategorie má vlastní pastelovou barvu bloku.
- Pozadí světle šedé/bílé, karty bílé, jemné stíny, výrazně **zaoblené rohy** (pilulkovité prvky a tlačítka).
- Nadpisy sekcí v postranním panelu: malá velká písmena (UPPERCASE), tyrkysová/modrošedá.
- Ikony tenké, liniové (line icons).
- Interakce: hover stavy na buňkách mřížky a tlačítkách, přetahování (drag) událostí pro přesun/změnu trvání, klik na prázdno = nová aktivita, klik na aktivitu = detail popover, klik na tužku v popoveru = otevření modalu v režimu editace.

## Funkční požadavky
- Navigace týdny (Dnes / ‹ / ›) synchronně mění hlavní mřížku, titulek i mini kalendář.
- Přepínač Den / Týden / Měsíc mění rozvržení mřížky.
- Filtry v postranním panelu (uživatelé, typy, kategorie, zobrazení realizovaných/zrušených) okamžitě filtrují viditelné aktivity.
- Aktivity mají typ, prioritu, termín (datum + začátek + trvání / celodenní), místo, kategorii, účastníky, navázaný subjekt, poznámky, stav (naplánováno / realizováno / zrušeno) a příznak soukromé aktivity.
- „Vícedenní" řádek zobrazuje celodenní a přes více dní táhnoucí se aktivity.

## Co dodržet
- Vše česky, přesně s texty labelů a tlačítek uvedenými výše.
- Použij **náš** design systém a komponenty — barvy/rozměry výše jsou vodítko vzhledu, ne závazné hodnoty.
- Responzivně a přístupně (klávesnice, ARIA) podle našich standardů.
