# Přehled projektů

> **Dlaždice:** `projekty` · **Adresa (routa):** `/projekty` · **Kdo smí otevřít:** kdokoli s právem `projekty` (dlaždici vidí všichni, bez práva je zamčená 🔒)
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

1. **Odkaz „← Zpět na rozcestník"** — návrat na hlavní rozcestník appky.
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
| **Zrušit / Uložit** | zavře bez uložení / uloží změny |

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

### Jak na…
- **Označit úkol jako hotový:** klik do buňky → Stav = *Hotovo* → Uložit. (Pokud je napojený na Freelo,
  dokončí se i tam.)
- **Nastavit termín/osobu:** klik do buňky → vyplň Termín / Odpovědná osoba → Uložit.
- **Přidat projekt, který není ve Freelu:** *+ Projekt* → název (klidně s číslem OP) a případně termín.
- **Přidat nový úkol napříč projekty:** *+ Sloupec* → zadej fázi a název úkolu (vznikne nový sloupec).
- **Uklidit si přehled:** *Zobrazení ▾* odškrtej fáze/úkoly, které nechceš vidět; táhnutím si srovnej pořadí.
  Tohle je jen tvoje a nikomu jinému se to nezmění.
- **Skrýt projekt všem:** *× skrýt řádek* u projektu; obnovíš v panelu „Skryté projekty" odkazem *obnovit*.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Přehled projektů** vidí v rozcestníku **všichni**, ale bez práva `projekty` je **zamčená** (🔒).
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
  - `nastaveni_barev` — globální prahy barev, jeden řádek `id=1`.
  - `nastaveni_synchronizace` — globální nastavení auto-sync, jeden řádek `id=1`.
- **API** (`backend/app/matice/routes.py`, prefix `/matice`):
  - `GET /matice` — celá matice (fáze, projekty, buňky, barvy, `muze_editovat`).
  - `PUT /matice/bunka` — uložení/založení buňky (upsert); volitelný zápis stavu do Freela.
  - `POST /matice/projekt`, `POST /matice/sloupec` — ruční přidání.
  - `PUT /matice/projekt/{id}/zobrazeni` — skrýt/obnovit projekt.
  - `PUT /matice/projekt/{id}/disk`, `POST /matice/disk/sparovat` — odkazy na Disk a párování.
  - `PUT /matice/barvy` — prahy barev.
  - `POST /matice/freelo/nacist` — ruční synchronizace (`rezim` = `prepsat` / `bez_prepsani`).
  - `GET/PUT /matice/sync-nastaveni` — nastavení auto-sync (jen admin).
- **Klíčové soubory:** `routes.py` (API + jádro `proved_synchronizaci`), `models.py` (tabulky),
  `freelo.py` (volání Freela), `disk_parovani.py` (párování s Diskem), `scheduler.py` (plánovač),
  `schemas.py` (vstupy/výstupy), `permissions.py` (`muze_editovat`, `vyzaduj_editora`).
  Frontend: `pages/PrehledProjektu.jsx` + dialogy `components/BunkaDialog.jsx`, `FreeloDialog.jsx`,
  `PridatDialog.jsx`, `ZobrazeniDropdown.jsx`.

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
