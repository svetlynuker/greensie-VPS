# Přehled projektů

> **Sekce v nabídce:** `projekty` · **Adresa (routa):** `/projekty` · **Kdo smí otevřít:** kdokoli s právem `projekty` (bez práva se sekce v nabídce vůbec nezobrazí a `GET /matice` vrátí 403 — od 3. 8. 2026, dřív se dala matice bez práva přečíst zadáním adresy)
> **Kód:** frontend `frontend/src/pages/PrehledProjektu.jsx`, backend `backend/app/matice/`

Hlavní přehledová tabulka firmy — **matice**, kde řádky jsou projekty a sloupce jsou úkoly
seskupené do fází. Data se stahují z **Freela**, ale zdrojem pravdy je tato tabulka v appce
(dá se v ní ručně upravovat a doplňovat). Barvy buněk hlídají termíny.

> 📸 SCREENSHOT: celá obrazovka Přehledu projektů — horní lišta, legenda, matice s barevnými buňkami

---

## 🧑 Pro uživatele

### K čemu to slouží
Na jednom místě vidíš **stav všech aktivních projektů**: které úkoly jsou hotové, které ne,
kdy mají termín a kdo je za ně odpovědný. Barvy okamžitě ukážou, co „hoří". Kliknutím do buňky
se úkol edituje. Data si appka umí sama natáhnout z Freela.

### Rozvržení obrazovky
Shora dolů:

1. **Odkaz „← Zpět na rozcestník"** — návrat na úvodní souhrn. Mezi moduly se ale chodí
   **panelem vlevo**, tenhle odkaz je jen zkratka na úvodní stránku.
2. **Horní lišta (nástroje)** — tlačítka pro práci s daty a zobrazením (viz níže). Dá se celá
   skrýt tlačítkem **„Skrýt nástroje ▴ / Zobrazit nástroje ▾"**, aby zbylo víc místa na tabulku.
3. **Legenda termínů** — čtyři barvy a jejich prahy (kdy je co zelené/žluté/oranžové/červené).
4. **Panel skrytých projektů** — objeví se jen když nějaké projekty skryješ (a jen editorům).
5. **Matice** — samotná tabulka projektů × úkolů.

### Jak číst matici
- **Řádek = projekt.** Vlevo jeho název (proklik do Freela), termín a ukazatel „hotové fáze".
- **Sloupec = úkol.** Úkoly jsou seskupené pod **fázemi** (to-do listy z Freela, např. „SOP").
- **Buňka = stav úkolu u projektu:**
  - **✓ Hotovo** — úkol je dokončený (zelené pozadí).
  - **⏳ Nehotovo** — úkol běží; barva podle termínu (zelená → žlutá → oranžová → červená).
  - **tečka `·`** (prázdná) — úkol u tohoto projektu neexistuje / nemá stav.
  - V buňce se pod stavem ukazuje **termín**, **odpovědná osoba** a **poznámka** (pokud jsou vyplněné).

> 📸 SCREENSHOT: detail několika buněk — hotová (zelená ✓), nehotová po termínu (červená ⏳), prázdná (tečka)

### Barvy termínů a jak se počítají
Barva se řídí číslem **d = dnes − termín** (ve dnech):
- **záporné** d = jsme **před** termínem, **kladné** = jsme **po** termínu.
- Prahy jsou v legendě a dají se změnit (viz „Legenda" níže). Výchozí nastavení:

| Barva | Význam | Výchozí prah (d) |
|---|---|---|
| 🟢 zelená | v termínu | d ≤ −4 (víc než 4 dny do termínu) |
| 🟡 žlutá | blíží se | −3 až 0 |
| 🟠 oranžová | po termínu | 1 až 3 |
| 🔴 červená | hodně po | d ≥ 4 |

Barva **řádku projektu** i **souhrnu fáze** se počítá z nejzazšího termínu jejích úkolů;
když je celá fáze/projekt hotová, je zelená.

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = všichni, kdo modul otevřou · **(editor)** = jen s právem `editace`
· **(admin)** = jen supersprávce.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **Skrýt / Zobrazit nástroje** | horní lišta | Schová nebo ukáže tlačítka v liště (víc místa na tabulku) | vše |
| **↻ Načíst z Freelo** | horní lišta | Otevře dialog stažení dat z Freela (viz „Načtení z Freela") | admin |
| **+ Projekt** | horní lišta | Přidá ručně nový projekt (název + nepovinný termín) | editor |
| **+ Sloupec** | horní lišta | Přidá ručně nový úkol/sloupec (fáze + název úkolu) | editor |
| **📁 Spárovat s Diskem** | horní lišta | Hromadně dohledá u projektů složku dokumentů na Google Disku podle čísla OP v názvu | editor |
| **Fáze: Sbalit vše / Rozbalit vše** | horní lišta | Sbalí/rozbalí všechny fáze (sbalená fáze = jeden souhrnný sloupec „termín · hotovo") | vše |
| **Zobrazení ▾** | horní lišta | Rozbalí panel se zaškrtávátky — které fáze a úkoly zobrazit/skrýt (osobní, ukládá se) | vše |
| **Zobrazit vše** | horní lišta | Zruší všechna osobní skrytí fází a úkolů | vše |
| **Počítadlo** | vpravo v liště | Kolik je projektů / fází / úkolů (a kolik skrytých) | vše |
| **Vstupní pole v legendě** | legenda | Nastaví prahy barev (dny) — viz „Legenda" | editor (ostatní jen čtou) |
| **Uložit prahy** | legenda | Uloží změněné prahy barev (platí pro všechny) | editor |
| **Buňka v tabulce** | matice | Klik otevře dialog editace úkolu | editor (ostatním se dialog neotevře) |
| **⋮⋮ (úchyt řádku)** | první sloupec | Táhnutím změníš pořadí projektů (osobní) | vše |
| **Záhlaví fáze** | matice | Klik sbalí/rozbalí fázi; táhnutím ji přesuneš (osobní pořadí) | vše |
| **Záhlaví úkolu** | matice | Táhnutím přesuneš úkol v rámci fáze (osobní pořadí) | vše |
| **👁 oko** | v záhlaví fáze/úkolu | Skryje danou fázi/úkol ze zobrazení (vrátíš přes „Zobrazení" / „Zobrazit vše") | vše |
| **název projektu (odkaz)** | sloupec Projekt | Otevře projekt ve Freelu (nový panel) | vše (pokud má projekt URL) |
| **💰 Finance** | sloupec Projekt | Přejde na Přehled financí filtrovaný na tento projekt | jen kdo smí otevřít Finance |
| **📁 Dokumenty** | sloupec Projekt | Otevře složku dokumentů projektu na Google Disku | vše (když je odkaz) |
| **✎ (u Dokumentů)** | sloupec Projekt | Ručně upraví/smaže odkaz na složku dokumentů | editor |
| **📁 přidat odkaz** | sloupec Projekt | Ručně vloží odkaz na složku, když se nenašel automaticky | editor |
| **× skrýt řádek** | sloupec Projekt | Skryje celý projekt z tabulky (obnovíš přes panel „Skryté projekty") | editor |

> 📸 SCREENSHOT: horní lišta s popisky jednotlivých tlačítek

#### Osobní vs. společné nastavení
- **Osobní** (vidíš jen ty, přenáší se mezi tvými zařízeními přes přihlášení): skrytí fází/úkolů
  („Zobrazení", oko), pořadí projektů/fází/úkolů (drag & drop). Ukládá se do tvého profilu.
- **Společné** (platí pro všechny): prahy barev, obsah buněk, skrytí celého projektu („× skrýt řádek"),
  přidané projekty a sloupce.

### Dialog editace buňky
Otevře se klikem do buňky (jen editor). Obsahuje:

| Pole | Co dělá |
|---|---|
| **Stav** | výběr: *— (prázdné / neexistuje)* / *Nehotovo* / *Hotovo* |
| **Termín** | datum termínu úkolu (kalendář) |
| **Odpovědná osoba** | jméno (volný text) |
| **Poznámka** | volný text; **žije jen v appce a Freelo ji nikdy nepřepíše** |
| **Otevřít úkol ve Freelu ↗** | odkaz na úkol ve Freelu (jen když je buňka napojená na Freelo) |
| **Hotovo** | zavře okno; **neukládá** — změny jsou uložené už průběžně |

**Ukládá se to samo (od 6. 8. 2026).** Tlačítko „Uložit" tu už není: každé pole se
uloží samo — u textu asi půl sekundy po dopsání, u výběru stavu a data hned. Vlevo dole
je vidět stav (*Ukládám… / Uloženo v 14:32 / Neuloženo*). Zavření okna čekající změnu
ještě odešle, takže se posledních pár znaků neztratí.

Ukládá se **jen to pole, které jsi změnil**. Dřív se posílala celá buňka naráz, takže dva
lidé v jedné buňce si navzájem přepsali i pole, kterých se nedotkli — nejčastěji poznámku,
a bez jakékoli hlášky.

**Když do stejného pole mezitím zapsal někdo jiný**, appka nic nepřepíše a zeptá se:
ukáže, kdo a co změnil, a nabídne *Přepsat mojí hodnotou* / *Nechat jejich*.

> ⚠️ Prázdné pole je platná hodnota (= vymazat). Protože se ukládá průběžně, jsou
> v databázi i rozepsané a nedokončené hodnoty — to je normální stav, ne chyba.

> ⚠️ **Změna stavu se propíše zpět do Freela**, pokud je buňka napojená na Freelo úkol a je zapnutý
> „zápis stavu do Freela" (výchozí ano). Když zápis do Freela selže, **stav se neuloží** a uvidíš chybu —
> je to tak schválně, aby ho příští synchronizace nepřepsala zpátky.

> 📸 SCREENSHOT: dialog editace buňky s vyplněnými poli

### Načtení z Freela (dialog)
Otevře tlačítko **↻ Načíst z Freelo** (jen admin). Nabízí dvě volby:

- **Přepsat vše z Freela** — aktualizuje i ručně upravené úkoly (stav, termín, osoba). **Poznámky zůstávají.**
- **Načíst bez přepsání** — doplní jen **nové** úkoly a projekty; existující (i ručně upravené) nechá být.

V obou případech: **úkoly, které Freelo nemá, se nemažou** a **poznámky se nikdy nepřepisují**.

> 📸 SCREENSHOT: dialog „Načíst z Freela" se dvěma volbami

### Kdo tu je se mnou
V horní liště vedle názvu **„Přehled projektů"** jsou kolečka s iniciálami lidí, kteří mají
pohled právě otevřený. Když někdo edituje konkrétní buňku, řekne to popisek u kolečka
(*„Jméno — edituje: podpis SOP – OP-26-099"*) a **ta buňka má v tabulce zelený rámeček
a tečku**. Je to schválně vidět dřív, než do buňky klikneš — dohodnout se je vždycky lepší
než řešit kolizi potom.

Kolečko zmizí samo do půl minuty po tom, co člověk stránku zavře (nebo si přepne na jinou
záložku — appka pak přestane hlásit, že se dívá).

**Změny od ostatních se dotahují samy** — do několika sekund, bez obnovování stránky.
Platí to i pro to, co mezitím natáhla automatická synchronizace z Freela. Pole, které máš
právě rozepsané, ti aktualizace nikdy nepřepíše.

### Jak na…
- **Označit úkol jako hotový:** klik do buňky → Stav = *Hotovo*. Uloží se samo. (Pokud je úkol
  napojený na Freelo, dokončí se i tam.)
- **Nastavit termín/osobu:** klik do buňky → vyplň Termín / Odpovědná osoba. Uloží se samo.
- **Přidat projekt, který není ve Freelu:** *+ Projekt* → název (klidně s číslem OP) a případně termín.
- **Přidat nový úkol napříč projekty:** *+ Sloupec* → zadej fázi a název úkolu (vznikne nový sloupec).
- **Uklidit si přehled:** *Zobrazení ▾* odškrtej fáze/úkoly, které nechceš vidět; táhnutím si srovnej pořadí.
  Tohle je jen tvoje a nikomu jinému se to nezmění.
- **Skrýt projekt všem:** *× skrýt řádek* u projektu; obnovíš v panelu „Skryté projekty" odkazem *obnovit*.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Sekci **Přehled projektů** uvidí v panelu vlevo jen ten, kdo má právo `projekty` — bez něj tam položka vůbec není.
- **Čtení matice** (`GET /matice`) může každý přihlášený uživatel, kdo modul otevře.
- **Editace** (buňky, přidání projektu/sloupce, prahy barev, skrytí projektu, odkazy na Disk, párování,
  ruční načtení z Freela) vyžaduje právo **`editace`** — v kódu strážce `vyzaduj_editora`.
  Bez něj se editační tlačítka **nezobrazí** a dialog buňky se neotevře.
- **↻ Načíst z Freelo** je navíc omezené jen na **supersprávce** (`uzivatel.je_admin`) — běžný editor
  ho v liště nevidí, i když jinak edituje.
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky). Viz paměť projektu
  a `backend/app/auth/permissions.py`.

### Automatická synchronizace z Freela
Kromě ručního tlačítka umí server stahovat data z Freela **sám na pozadí**. Nastavuje se v
**Admin nastavení** (endpointy `GET/PUT /matice/sync-nastaveni`, jen admin; plánovač
`backend/app/matice/scheduler.py`). Volby (tabulka `nastaveni_synchronizace`, jeden řádek `id=1`):

| Volba | Výchozí | Význam |
|---|---|---|
| `auto_zapnuto` | zapnuto | zda plánovač vůbec běží |
| `interval_min` | 60 | jak často (v minutách; minimum 5) |
| `sync_stav` | zapnuto | přepisovat stav úkolů podle Freela |
| `zapis_stav_do_freela` | zapnuto | obousměrně: změnu stavu v appce zapsat zpět do Freela |
| `sync_nove_ukoly` | zapnuto | zakládat nové úkoly/sloupce z Freela |
| `sync_nove_projekty` | zapnuto | zakládat nové projekty z Freela |
| `sync_terminy` | vypnuto | přepisovat termíny podle Freela |
| `sync_osoby` | vypnuto | přepisovat odpovědné osoby podle Freela |

**Pravidlo:** zapnuté pole = „Freelo vyhrává" a přepíše i ručně zadanou hodnotu; vypnuté pole zůstane
beze změny. **Poznámka se nepřepisuje NIKDY.** U posledního běhu se ukládá čas a výsledek
(`posledni_beh`, `posledni_vysledek`).

### Napojení na okolní systémy
- **Freelo** — zdroj úkolů a projektů. Čte aktivní projekty a jejich úkoly; volitelně zapisuje zpět
  stav úkolu (dokončit/aktivovat). Přístup přes `FREELO_EMAIL` + `FREELO_API_KEY` z `.env`
  (`backend/app/matice/freelo.py`).
- **Google Disk** — proklik na složku dokumentů projektu. `disk_url` se plní automaticky **párováním
  přes číslo OP** z názvu projektu (`backend/app/matice/disk_parovani.py`), nebo ručně (pak
  `disk_rucni=True` a auto-párování ho už nepřepíše). `raynet_deal_id` = jednou spárovaný obchodní případ.
- **Přehled financí** — proklik „💰 Finance" vede na `/finance?projekt=<id>`.

### Jak to funguje uvnitř (stručně technicky)
- **Datový model** (`backend/app/matice/models.py`):
  - `projekty` — projekt (`nazev`, `url`, `termin`, `freelo_id`, `rucni`, `skryty`, `poradi`,
    `disk_url`, `disk_rucni`, `raynet_deal_id`).
  - `sloupce` — úkol/sloupec (`label` unikátní, `faze`, `nazev`, `rucni`, `poradi`). Fáze = seskupení
    sloupců podle pole `faze`.
  - `bunky` — průsečík projekt × sloupec (`stav` `done`/`todo`/`None`, `termin`, `osoba`, `poznamka`,
    `url`, `freelo_task_id`, `upraveno_rucne`). Unikát na dvojici (projekt, sloupec).
    Od 6. 8. 2026 navíc `zmeneno_at`, `zmenil_id`, `verze` — kdo a kdy naposledy změnil.
    `projekty` mají `zmeneno_at` taky.
  - `pritomnost` (`backend/app/pritomnost/models.py`) — kdo má co otevřené: jeden řádek na
    dvojici (uživatel, entita), obnovovaný tikem z prohlížeče.
  - `nastaveni_barev` — globální prahy barev, jeden řádek `id=1`.
  - `nastaveni_synchronizace` — globální nastavení auto-sync, jeden řádek `id=1`.
- **API** (`backend/app/matice/routes.py`, prefix `/matice`):
  - `GET /matice` — celá matice (fáze, projekty, buňky, barvy, `muze_editovat`).
  - `PUT /matice/bunka` — uložení/založení celé buňky (upsert). Frontend ho už nepoužívá,
    zůstává kvůli zpětné kompatibilitě; **nové věci na něj nestavět** (přepisuje i pole,
    kterých se člověk nedotkl).
  - `PATCH /matice/bunka` — uložení **jednoho pole** (`pole`, `hodnota`, `puvodni`). Základ
    automatického ukládání. Když se `puvodni` neshoduje s tím, co je v DB, vrací **409**
    s `{zprava, pole, aktualni, kdo, kdy}` a **nic nepřepíše**. `puvodni: null` = přepiš
    bez kontroly (člověk kolizi potvrdil). Volitelný zápis stavu do Freela jako u `PUT`.
  - `GET /matice/razitko` — podpis stavu matice (`backend/app/matice/razitko.py`). Změní-li
    se proti tomu, co klient drží, načte si `GET /matice` znovu. Běžně přichází rovnou
    v odpovědi na tik přítomnosti, takže se nevolá dvakrát.
  - `POST /matice/projekt`, `POST /matice/sloupec` — ruční přidání.
  - `PUT /matice/projekt/{id}/zobrazeni` — skrýt/obnovit projekt.
  - `PUT /matice/projekt/{id}/disk`, `POST /matice/disk/sparovat` — odkazy na Disk a párování.
  - `PUT /matice/barvy` — prahy barev.
  - `POST /matice/freelo/nacist` — ruční synchronizace (`rezim` = `prepsat` / `bez_prepsani`).
  - `GET/PUT /matice/sync-nastaveni` — nastavení auto-sync (jen admin).
- **Přítomnost** (`backend/app/pritomnost/`, prefix `/pritomnost`):
  - `POST /pritomnost/tik` — „jsem tady, mám otevřené tohle"; v odpovědi vrací seznam
    přítomných **a razítko změn**. Prohlížeč tiká každých 8 s a jen když je záložka vidět.
  - `POST /pritomnost/odchod` — zavření stránky (jen aby kolečko zmizelo hned; nedoručený
    odchod vyprší sám za 25 s).
  - Přítomný = kdo tikl v posledních 25 s (`sluzba.OKNO_S`). Zavřená záložka zmizí sama —
    kdyby se místo toho párovalo „přišel/odešel", každý spadlý prohlížeč by nechal ducha.
  - Které moduly to umí, je v `pritomnost/registr.py` — jeden řádek na modul (právo + funkce
    razítka). Neznámý typ endpoint odmítne (400), aby seznam přítomných nešel obejít bez práva.
- **Klíčové soubory:** `routes.py` (API + jádro `proved_synchronizaci`), `models.py` (tabulky),
  `freelo.py` (volání Freela), `disk_parovani.py` (párování s Diskem), `scheduler.py` (plánovač),
  `schemas.py` (vstupy/výstupy), `permissions.py` (`muze_editovat`, `vyzaduj_editora`).
  `bunka_pole.py` (ukládání po polích + kontrola kolize), `razitko.py` (podpis stavu + `oznac_zmenu`).
  Frontend: `pages/PrehledProjektu.jsx` + dialogy `components/BunkaDialog.jsx`, `FreeloDialog.jsx`,
  `PridatDialog.jsx`, `ZobrazeniDropdown.jsx`, dále `hooks/useAutosave.js`,
  `hooks/usePritomnost.js` a `components/Pritomni.jsx`, `components/StavUlozeni.jsx`
  (obojí je společné, počítá se s použitím v dalších modulech).
- **Proč razítko a ne seznam rozdílů:** matice je jeden malý dotaz, takže se natáhne celá.
  Počítat „co přesně se změnilo od času X" by znamenalo držet historii změn — a při první
  nepřesnosti by lidem tiše chyběla aktualizace. Podpis je tupý, ale nemůže lhát.
- **Proč se kolize hlídá hodnotou, ne verzí:** `verze` roste i při změně jiného pole, takže
  by appka hlásila kolizi u věcí, které si vzájemně nevadí. Porovnává se proto hodnota, se
  kterou člověk začal psát (`puvodni`).
- **`oznac_zmenu` musí volat i automat:** synchronizace z Freela a párování s Diskem ho volají
  taky (bez uživatele → „automatická synchronizace"). Kdyby ne, razítko by se nezměnilo
  a lidé by koukali na stará data, dokud stránku sami neobnoví.

### Časté potíže / co dělat, když…
- **„Zápis stavu do Freela selhal"** při ukládání buňky → Freelo API nedostupné nebo úkol už ve Freelu
  neexistuje. Stav se **záměrně neuloží**. Zkus znovu; když trvá, dočasně vypni „zápis stavu do Freela"
  v Admin nastavení nebo prověř `FREELO_API_KEY`.
- **„Načtení z Freela selhalo"** (chyba 502) → problém se spojením/klíčem k Freelu.
- **Ručně upravená data zmizela po synchronizaci** → někdo pustil „Přepsat vše z Freela" nebo je
  zapnuté `sync_stav`/`sync_terminy`/`sync_osoby`. Poznámky nikdy nemizí; ostatní pole ano, když je
  daný přepis zapnutý.
- **Projekt nemá odkaz na Dokumenty** → automatické párování nenašlo číslo OP v názvu; vlož odkaz ručně
  (*📁 přidat odkaz*), tím se uzamkne (`disk_rucni`) proti přepsání.
- **„Neuloženo" u editace buňky** → poslední pokus o uložení selhal (spadlá síť, vypršené
  přihlášení, chyba Freela u změny stavu). Text chyby je vedle. Okno **nezavírej**, dokud
  nezmizí — zavřením se čekající změna sice ještě odešle, ale když selže i to, je ztracená.
- **„Mezitím to změnil někdo jiný"** → do stejného pole zapsal jiný člověk (nebo automatická
  synchronizace). Nic se nepřepsalo; vyber *Přepsat mojí hodnotou* nebo *Nechat jejich*.
- **Kolečko člověka nezmizelo, i když už odešel** → mizí do 25 s; když má počítač uspaný
  s otevřenou záložkou, zmizí taky (skrytá záložka přestane hlásit přítomnost).

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Editace se nemaže z Freela:** úkoly a projekty, které ve Freelu nejsou, appka **nikdy nemaže** —
  matice je nadmnožina Freela.
- **`upraveno_rucne`** na buňce označuje ručně editované buňky; slouží jako ochrana záměru při
  synchronizaci (pole existuje, přesnou roli při každém režimu synchronizace ještě prověřit v kódu).
- Ruční tlačítko „Načíst z Freela" natahuje **nové projekty i úkoly vždy** (`nove_projekty=True`,
  `nove_ukoly=True`); liší se jen v tom, zda přepíše existující hodnoty (`prepsat` vs. `bez_prepsani`).
- **Sbalená fáze** se v tabulce zobrazí jako jeden souhrnný sloupec „termín · hotovo" s procentuální lištou.
- Prázdný odkaz v „✎ upravit odkaz" **smaže** ruční odkaz a projekt se vrátí do automatického párování.

## Odkazy
- Kód backend: `backend/app/matice/` · frontend: `frontend/src/pages/PrehledProjektu.jsx`
- Paměť projektu: Pohled 1 / matice (viz `MEMORY.md` → greensie-app-projekt)
- Související: [Proklik na složku dokumentů](../../moduly/) (párování přes číslo OP, Freelo ↔ konektor)
