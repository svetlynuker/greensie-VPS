# Logy

> **Dlaždice:** `logy` · **Adresa (routa):** `/logy` · **Kdo smí otevřít:** kdokoli s právem `logy` (dlaždici vidí všichni, bez práva je zamčená 🔒; supersprávce má vždy)
> **Kód:** frontend `frontend/src/pages/Logy.jsx`, backend `backend/app/logy/`

Přehled **systémových a aplikačních záznamů** appky — kdo co dělal (audit), jak server odpovídal
(provoz) a kde spadl (chyby). Slouží hlavně pro dohled a řešení problémů: každý požadavek na backend
se sem propíše jako jeden řádek. Záznamy se **nemažou samy** — čistí je ručně jen člověk s právem na Logy.

> 📸 SCREENSHOT: celá obrazovka Logů — nadpis s počtem záznamů, ovládací panel (filtr, hledání, auto-obnova, tlačítka), tabulka záznamů

---

## 🧑 Pro uživatele

### K čemu to slouží
Na jednom místě vidíš **historii dění v appce**. Když něco přestane fungovat nebo se ptáš „kdo tohle
změnil / kdy se to naposílalo z Freela / proč to hází chybu", podíváš se sem. Každý řádek říká
**kdy** se něco stalo, **kdo** to vyvolal, **jaký** to byl druh akce, **co** to bylo (metoda + cesta,
případně čitelný popis), jak to **dopadlo** (stavový kód) a jak dlouho to **trvalo**. U chyb je navíc
schovaný technický detail (jen pro supersprávce).

### Rozvržení obrazovky
Shora dolů:

1. **Odkaz „← Zpět na rozcestník"** — návrat na hlavní rozcestník appky.
2. **Nadpis „Logy"** a vedle něj **počítadlo** — kolik záznamů je právě zobrazeno a čas poslední
   aktualizace (např. „300 záznamů · aktualizováno 14:23:05").
3. **Ovládací panel** (karta) — filtr druhu, pole hledání, zaškrtávátko automatického obnovování,
   tlačítko „Obnovit teď" a vpravo „Vyčistit vše".
4. **Tabulka záznamů** — sloupce Čas, Uživatel, Druh, Akce, Stav, Doba. Řádky od nejnovějších.

### Jak číst záznam
Jeden řádek = jedna událost na serveru. Sloupce:

- **Čas** — kdy se to stalo (přepočteno do českého času prohlížeče; v databázi je uloženo v UTC).
- **Uživatel** — e-mail toho, kdo akci vyvolal (z přihlašovacího tokenu). Když je akce anonymní
  nebo se uživatele nepodařilo zjistit, je tu pomlčka „—".
- **Druh** — barevný odznak podle typu záznamu:

  | Odznak | Druh (`typ`) | Co to znamená |
  |---|---|---|
  | **Provoz** (šedý) | `provoz` | čtení dat (GET/HEAD) — běžný provoz serveru |
  | **Akce** (firemní barva) | `audit` | změnová akce (POST/PUT/PATCH/DELETE) — „kdo co udělal" |
  | **Chyba** (červený) | `chyba` | pád serveru (stavový kód 500 a výš) |

- **Akce** — čitelný **popis** (tučně, např. „Editace buňky matice"), pokud pro danou cestu existuje;
  za ním vždy **metoda a cesta** požadavku (např. `PUT /matice/bunka`). U chybových řádků je tu navíc
  červený odkaz **„▸ detail chyby"** — klik řádek rozbalí a ukáže technický výpis (viz níže).
- **Stav** — HTTP stavový kód, barevně: zelený 2xx (OK), žlutý 4xx (zamítnuto/špatný vstup),
  červený 5xx (chyba serveru). Pomlčka „—", když kód není.
- **Doba** — jak dlouho vyřízení trvalo v milisekundách (např. „42 ms").

> 📸 SCREENSHOT: pár řádků tabulky — provozní (šedý), auditní (barevný), chybový (červený s odkazem „detail chyby")

### Detail chyby (rozbalení řádku)
U řádků druhu **Chyba** je řádek klikací. Klik ho rozbalí a pod ním se ukáže **technický výpis
(traceback)** v rámečku. Znovu klik detail skryje. Tento detail **vidí jen supersprávce** — ostatním
se v odpovědi ze serveru vůbec neposílá, takže u nich není co rozbalit (řádek je bez odkazu „detail chyby").

> 📸 SCREENSHOT: rozbalený chybový řádek s výpisem tracebacku

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = každý, kdo modul otevře (má právo `logy`) · **(admin)** = jen
supersprávce (`je_admin`).

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **Filtr druhu** (rozbalovací seznam) | ovládací panel | Omezí tabulku na jeden druh: *Vše* / *Jen akce (kdo co udělal)* = `audit` / *Jen chyby* = `chyba` / *Jen provoz (načítání)* = `provoz` | vše |
| **Hledat** (pole) | ovládací panel | Fulltext přes **cestu, popis a e-mail uživatele**; hledá se až 400 ms po dopsání (ne po každém úhozu) | vše |
| **Automaticky obnovovat (5 s)** (zaškrtávátko) | ovládací panel | Když je zaškrtnuté (výchozí **ano**), tabulka se sama načte znovu každých 5 sekund | vše |
| **Obnovit teď** (tlačítko) | ovládací panel | Okamžitě načte záznamy znovu podle aktuálního filtru a hledání | vše |
| **Vyčistit vše** (červené tlačítko) | vpravo v panelu | Po potvrzení **smaže úplně všechny** záznamy logu (nevratné) | vše (kdo má právo `logy`) |
| **Klik na chybový řádek** | tabulka | Rozbalí/skryje detail chyby (traceback) — jen u řádků s detailem | admin (jen jemu se detail posílá) |

> ⚠️ **„Vyčistit vše" maže vše a nevratně.** Appka se před smazáním zeptá potvrzovacím dialogem
> („Opravdu smazat VŠECHNY záznamy logu? Tuto akci nelze vrátit."), ale zpět už se nic nevrátí.

> 📸 SCREENSHOT: ovládací panel s popisky jednotlivých prvků

### Kolik záznamů se ukáže
Stránka si při každém načtení stáhne **posledních 300** záznamů (od nejnovějších). Stránkování
(„další strana") tu **není** — starší záznamy nad rámec limitu se prostě nezobrazí. Když jich chceš
vidět víc konkrétního druhu, použij **filtr** nebo **hledání**, které limit uplatní až po zúžení.

### Jak na…
- **Zjistit, kdo něco změnil:** Filtr = *Jen akce* → do hledání napiš část cesty (např. `matice`)
  nebo e-mail dotyčného. Ve sloupci Akce uvidíš čitelný popis a čas.
- **Najít chybu:** Filtr = *Jen chyby* → klikni na červený řádek a rozbal detail (jen admin).
- **Sledovat dění naživo:** nech zaškrtnuté „Automaticky obnovovat (5 s)" — tabulka se sama obnovuje.
- **Zklidnit obrazovku:** odškrtni auto-obnovu a používej „Obnovit teď", až když chceš.
- **Uklidit staré záznamy:** „Vyčistit vše" (smaže všechno). Chytřejší pročištění „jen starší než N dní"
  umí API, ale tlačítko v UI pro něj **není** (viz Poznámky).

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Logy** vidí v rozcestníku **všichni**, ale bez práva `logy` je **zamčená** (🔒).
- **Otevření a čtení logů i mazání** vyžaduje právo **`logy`** — na backendu strážce
  `vyzaduj_pravo_logy` (volá `muze_otevrit(user, "logy")`). Platí pro `GET /logy` i `DELETE /logy`.
  Kdo právo nemá, dostane 403 („Na zobrazení logů nemáš oprávnění.").
- **Detail chyby (traceback)** se posílá **jen supersprávci** (`user.je_admin`). Ostatním ho server
  z odpovědi odstraní (`r.detail = None`) — protože může obsahovat interní cesty a citlivá data.
  Odebrání se neukládá do DB (session je autoflush=False a neкomituje se).
- Frontendová routa `/logy` je chráněná jen `VyzadujePrihlaseni` (stačí být přihlášen); **skutečnou
  kontrolu práva dělá backend** — bez práva `logy` vrátí API 403 a stránka ukáže chybu.
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky), viz
  `backend/app/auth/permissions.py`.

### Co všechno se loguje a odkud
Dva zdroje zápisu:

1. **Middleware `LogovaciMiddleware`** (`backend/app/logy/middleware.py`, registrace v
   `backend/app/main.py`) — zaznamená **každý** požadavek na backend automaticky. Přiřadí druh:
   - stavový kód ≥ 500 → `chyba` (u neošetřené výjimky uloží i traceback do `detail`),
   - jinak metoda POST/PUT/PATCH/DELETE → `audit` (změnová akce),
   - jinak (GET/HEAD) → `provoz`.

   Zjistí uživatele z Bearer tokenu, IP klienta (za proxy Caddy bere **poslední** prvek
   `X-Forwarded-For`), dobu zpracování a k vybraným cestám doplní **čitelný popis** (tabulka `_POPISY`).
   Zápis běží **až po odeslání odpovědi** jako background úloha ve vlákně, aby neblokoval server a
   nedržel druhé DB spojení z poolu. **Logování nikdy neshodí požadavek** (vše v try/except).

2. **Ruční audit `zaznamenej_audit`** (`backend/app/logy/audit.py`) — pro případy, kdy middleware
   nezná kontext. Zatím ho volá jen **přihlášení** (`backend/app/auth/routes.py`): úspěšné
   („Přihlášení: <jméno>"), neúspěšné se známým účtem („Neúspěšné přihlášení: <e-mail>") i neúspěšné
   s neznámým účtem („Neúspěšné přihlášení (neznámý účet)"). Přihlášení (`/auth/login`) je totiž z
   automatického logování vyňaté (viz níže), protože token teprve vzniká — zapisuje se samo, i se jménem.

**Cesty, které se NElogují** (aby se přehled nezaplevelil sám sebou):
- metoda `OPTIONS` (CORS preflight),
- prefixy `/logy` (jinak by čtení logů při auto-obnově plodilo nové logy donekonečna), `/health`
  (zdravotní kontrola), `/konektor/logy` (konektor má vlastní log),
- přesně `/auth/login` (řeší si ruční audit sám).

**Kdo tedy zapisuje do logů:** prakticky celá appka přes middleware — mimo jiné matice/Přehled
projektů, finance (POHODA), nabídkovač, admin (správa uživatelů a skupin) a **konektor Raynet↔Disk**
(webhooky, nastavení, test spojení mají v `_POPISY` čitelné popisy). Pozor: **konektor má i vlastní
oddělený log** na `/konektor/logy` (jiná tabulka, jiná stránka) — sem do `/logy` jdou jen jeho HTTP
požadavky přes middleware, ne jeho interní běhové záznamy.

### Úrovně / druhy záznamu
Modul nemá klasické úrovně (DEBUG/INFO/WARN), ale **tři druhy** (`typ`): `provoz`, `audit`, `chyba`
(viz tabulka výše). „Závažnost" navíc čteš ze **stavového kódu** (barevně 2xx/4xx/5xx).

### Retence / čištění
**Automatická retence není — nic se nemaže samo.** Záznamy se drží, dokud je někdo ručně nesmaže:
- `DELETE /logy` bez parametru → smaže **vše** (to dělá tlačítko „Vyčistit vše").
- `DELETE /logy?starsi_nez_dni=N` → smaže jen záznamy starší než N dní (v UI zatím **není tlačítko**).

Proti bobtnání DB chrání jen **ořez délky** textových polí při zápisu (funkce `orez` v `models.py`):
popis 500, cesta 1000, e-mail 320, detail (traceback) 20000, IP 100, metoda 10 znaků.

### Datový model
Tabulka **`logy`** (`backend/app/logy/models.py`, třída `Log`), jeden řádek = jedna událost:

| Pole | Typ | Význam |
|---|---|---|
| `id` | int | primární klíč |
| `cas` | datetime (UTC, indexováno) | čas vzniku události; řadí se podle něj sestupně |
| `uzivatel_id` | int / null | kdo akci vyvolal (z tokenu); u anonymních prázdné |
| `uzivatel_email` | str / null | **kopie** e-mailu uživatele (záměrně **bez cizího klíče**, aby řádek zůstal čitelný i po smazání uživatele) |
| `metoda` | str / null | HTTP metoda (GET, POST, PUT…) |
| `cesta` | str / null (indexováno) | cesta požadavku (např. `/matice/bunka`) |
| `status_kod` | int / null | výsledný HTTP kód |
| `doba_ms` | int / null | doba zpracování v ms |
| `typ` | str (indexováno) | druh: `provoz` (výchozí) / `audit` / `chyba` |
| `popis` | str / null | čitelný český popis akce (může chybět) |
| `detail` | text / null | traceback — jen u druhu `chyba`; posílá se jen adminovi |
| `ip` | str / null | IP klienta (pokud ji lze zjistit) |

Skládání záznamu je na jednom místě (`vytvor_zaznam`), aby délkové meze platily pro middleware i
ruční audit stejně.

### API
Router prefix `/logy` (`backend/app/logy/routes.py`), obojí chráněné `vyzaduj_pravo_logy`:

| Metoda + cesta | Účel | Parametry |
|---|---|---|
| `GET /logy` | Vrátí poslední záznamy od nejnovějších | `typ` (`provoz`/`audit`/`chyba`), `hledej` (fulltext v cestě/popisu/e-mailu, ilike), `limit` (1–2000, výchozí 200; frontend posílá 300) |
| `DELETE /logy` | Ruční pročištění | `starsi_nez_dni` (≥0; bez něj smaže vše); vrací `{ smazano: <počet> }` |

Frontend volá přes `nactiLogy({ typ, hledej, limit })` a `smazLogy(starsiNezDni)`
(`frontend/src/api.js`).

### Klíčové soubory
- Backend: `backend/app/logy/models.py` (tabulka + `vytvor_zaznam`/`orez`), `routes.py` (API + strážce
  práva), `schemas.py` (`LogOut`, `SmazaniVysledek`), `middleware.py` (automatický zápis + `_POPISY`),
  `audit.py` (ruční `zaznamenej_audit`). Registrace: `backend/app/main.py`
  (`app.add_middleware(LogovaciMiddleware)`, router). Práva: `backend/app/auth/permissions.py`
  (`muze_otevrit`, `DLAZDICE`/`PRAVA` klíč `logy`). Volající audit: `backend/app/auth/routes.py`.
- Frontend: `frontend/src/pages/Logy.jsx`, routa v `frontend/src/App.jsx` (`/logy`),
  API v `frontend/src/api.js`.

### Časté potíže / co dělat, když…
- **„Chyba: … nemáš oprávnění" / prázdná stránka s chybou** → uživatel nemá právo `logy`. Přidej ho
  v Admin nastavení (skupina nebo výjimka).
- **U chyby chybí „detail chyby"** → detail (traceback) se posílá **jen supersprávci**; běžný editor
  ho neuvidí, i když Logy otevře. Není to chyba.
- **Logů rychle přibývá / DB roste** → nemají automatickou retenci. Použij „Vyčistit vše", nebo přes
  API `DELETE /logy?starsi_nez_dni=N` smaž jen staré.
- **Nevidím starší záznamy** → stránka ukazuje jen posledních 300, bez stránkování. Zúži filtrem/hledáním.
- **Chybí interní běh konektoru** → ten je v samostatném logu `/konektor/logy` (jiná stránka/tabulka),
  ne tady.
- **Čas nesedí** → v DB je UTC, na obrazovce se přepočítává na místní čas prohlížeče.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Žádné stránkování ani volba limitu v UI** — frontend natvrdo žádá 300 nejnovějších. Kdo chce víc,
  musí volat API s vyšším `limit` (max 2000) ručně.
- **Mazání „starší než N dní" nemá tlačítko** — schopnost je v API (`starsi_nez_dni`), ale UI nabízí
  jen „Vyčistit vše". Chytřejší pročištění jde zatím jen přes API.
- **Nejsou klasické úrovně logu** (DEBUG/INFO/WARN/ERROR) — jen tři druhy (`provoz`/`audit`/`chyba`)
  plus barva podle HTTP kódu.
- **Audit se ručně zapisuje zatím jen u přihlášení.** Ostatní „auditní" řádky vznikají odvozeně z
  middleware (změnová metoda → `audit`), ne cíleným auditním voláním. Čitelný popis mají jen cesty
  vyjmenované v `_POPISY`; ostatní změnové akce se uloží jen jako metoda + cesta.
- **Auto-obnova každých 5 s** může být za slabšího připojení znát; jde vypnout zaškrtávátkem.
- **IP za proxy:** appka bere poslední prvek `X-Forwarded-For` (přidává ho Caddy); dřívější prvky by
  si klient mohl podvrhnout. Mimo proxy bere `request.client.host`.
- **`uzivatel_email` je kopie bez cizího klíče** — řádek zůstane čitelný i po smazání uživatele, ale
  e-mail se u historických řádků nepřejmenuje, když uživatel později e-mail změní.

## Odkazy
- Kód backend: `backend/app/logy/` · frontend: `frontend/src/pages/Logy.jsx`, `frontend/src/api.js`
- Práva a dlaždice: `backend/app/auth/permissions.py` (klíč `logy`), registrace middleware
  `backend/app/main.py`
- Související: Konektor Raynet ↔ Disk má **vlastní** log na `/konektor/logy` (viz modul Konektor) —
  nezaměňovat s tímto obecným logem.
