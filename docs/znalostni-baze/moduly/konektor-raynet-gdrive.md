# Konektor Raynet CRM ↔ Google Disk

> **Dlaždice:** `konektor` · **Adresa (routa):** `/konektor` · **Kdo smí otevřít:** kdokoli s právem `konektor` (dlaždici vidí všichni, bez práva je zamčená 🔒; admin ji má vždy)
> **Kód:** frontend `frontend/src/pages/Konektor.jsx`, backend `backend/app/konektor/`

Modul, který **propojuje Raynet CRM s Google Diskem**. Když v Raynetu vznikne zákazník, obchodní případ,
nabídka nebo objednávka, konektor sám založí na sdíleném Disku odpovídající složku (podle vzoru) a zapíše
její odkaz zpět do Raynetu. Soubory přidané na Disk se v Raynetu objeví jako odkazy. **Disk je zdroj obsahu,
Raynet drží jen odkazy.**

> 📸 SCREENSHOT: celá obrazovka Konektoru – karty Nastavení, Ruční test, Import, Synchronizace, Raynet→Disk a panel Logy pod sebou

---

## 🧑 Pro uživatele

### K čemu to slouží
Aby nikdo nemusel ručně zakládat složky pro každou zakázku a přetahovat soubory mezi Raynetem a Diskem.
Konektor to dělá automaticky:

- **Raynet → Disk (struktura):** vznikne firma / obchodní případ / nabídka / objednávka → na Disku se
  založí složka se stejnou strukturou jako vzorová složka „0. vzor" a do Raynetu se doplní odkaz na ni.
- **Disk → Raynet (odkazy):** nahraješ soubor do složky zakázky na Disku → v Raynetu se u obchodního
  případu objeví **odkazový dokument** na ten soubor (Raynet si soubor nekopíruje, jen na něj odkazuje).
- **Raynet → Disk (soubory):** soubor nahraný přímo do modulu Dokumenty v Raynetu se dá stáhnout a přesunout
  na Disk (a v Raynetu se nahradí odkazem).
- **Zrcadlení stromu Disku** do modulu Dokumenty v Raynetu (aby byl v RN vidět celý obsah Disku jako odkazy).

Model synchronizace je postavený tak, aby **Raynet nedržel kopie souborů**, jen odkazy – obsah je vždy na Disku.

### Rozvržení obrazovky
Shora dolů, každá oblast je samostatná karta:

1. **Odkaz „← Zpět na rozcestník"**.
2. **Nadpis „Konektor Raynet ↔ Google Disk"**.
3. **Nastavení konektoru** – všechny přístupy a chování synchronizace + tlačítka *Uložit* a *Test spojení*.
4. **Ruční test – vytvoření složky klienta** + tři diagnostické nástroje (strom vzoru, struktura Dokumentů,
   test odkazu).
5. **Hromadný import z Raynetu** – jednorázově založí složky pro všechna existující data.
6. **Synchronizace Disk → Raynet** – reconcile, push (watch), zrcadlení, sken Dokumentů.
7. **Raynet → Disk (ruční test)** – stažení jednoho dokumentu z Raynetu na Disk.
8. **Logy konektoru** – tabulka provozních záznamů s filtrem a hledáním.

> 📸 SCREENSHOT: karta „Nastavení konektoru" rozbalená se sekcemi Raynet CRM / Google Drive / Sken Dokumentů / Chování

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(konektor)** = každý, kdo modul otevře (má právo `konektor`; admin vždy). Uvnitř
stránky se práva dál **nedělí** – kdo Konektor otevře, vidí a smí všechno na něm (viz „Práva" níže).

#### Karta „Nastavení konektoru" — sekce Raynet CRM

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Instance** | název raynetové instance (subdoména) | Identifikuje účet Raynetu (hlavička `X-Instance-Name`) | konektor |
| **API uživatel** | e-mail API uživatele Raynetu | Uživatelské jméno pro přihlášení k API (Basic auth) | konektor |
| **Base URL API** | adresa Raynet API | Kam se volá API (výchozí `https://app.raynet.cz/api/v2/`) | konektor |
| **Kód pole – odkaz u firmy** | kód vlastního pole (typ odkaz) u company | Sem konektor zapíše odkaz na složku zákazníka | konektor |
| **Kód pole – odkaz u obch. případu (1)** | kód vlastního pole u obch. případu | Sem zapíše odkaz na složku OP | konektor |
| **Kód pole – odkaz u obch. případu (2)** | druhé vlastní pole u obch. případu | Zapíše se do něj tentýž odkaz (OP má dvě pole) | konektor |
| **Kód pole – odkaz u nabídky** | kód vlastního pole u nabídky | Sem zapíše odkaz na složku nabídky | konektor |
| **Kód pole – odkaz u objednávky** | kód vlastního pole u objednávky | Sem zapíše odkaz na složku objednávky | konektor |
| **Webhook token (X-RAYNETCRM-TToken)** | sdílené tajemství pro ověření příchozích webhooků | Musí sedět s tokenem nastaveným v Raynet webhooku, jinak se webhook odmítne | konektor |
| **API klíč** | tajemství pro přístup k Raynet API | **Write-only** – zadává se, ukládá šifrovaně, zpět se nezobrazí (viz níže) | konektor |

#### Karta „Nastavení konektoru" — sekce Google Drive

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **ID Shared Drive** | identifikátor sdíleného disku | Určí, na kterém Shared Drive se zakládají složky | konektor |
| **Kořenová složka – ID (volitelné)** | ID složky uvnitř Shared Drivu | Kam se zakládají složky zákazníků; prázdné = kořen Shared Drivu | konektor |
| **Vzorová složka „0. vzor" – ID** | ID složky se vzorem struktury | Podle ní se kopíruje struktura nové zakázky | konektor |
| **Kontejner – obchodní případy** | název složky ve vzoru pro OP | Kam ve struktuře patří obchodní případy (výchozí „1. Obchodní Případy") | konektor |
| **Kontejner – nabídky (v OP)** | název složky pro nabídky uvnitř OP | Kam patří nabídky (výchozí „1. nabídky") | konektor |
| **Kontejner – objednávky (v OP)** | název složky pro objednávky uvnitř OP | Kam patří objednávky (výchozí „5. objednávky") | konektor |
| **Zdroj pro Dokumenty (DMS) – ID složky** | ID zdrojové složky na Disku | Její obsah se zrcadlí do modulu Dokumenty v RN; prázdné = zrcadlení vypnuto | konektor |
| **Impersonovaný uživatel (delegace, volitelné)** | e-mail uživatele Workspace | Service account jedná „jako" tento uživatel (domain-wide delegation) | konektor |
| **Service-account JSON** | přístupový klíč Google service accountu | **Write-only** – vloží se JSON, uloží šifrovaně, zpět se nezobrazí | konektor |

#### Karta „Nastavení konektoru" — sekce Sken Dokumentů (Raynet → Disk)

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Automaticky skenovat nové soubory v RN Dokumentech** | přepínač | Zapne pravidelný sken modulu Dokumenty v RN | konektor |
| **Časy skenu (HH:MM, čárkou)** | plánované časy (Praha) | Kdy sken proběhne (výchozí `08:00,20:00`) | konektor |
| **Poslední sken** | informativní údaj | Kdy sken naposledy proběhl | konektor |
| **Přesouvat nové soubory z RN na Disk** | přepínač | ⚠️ Nové soubory z RN po ověření **smaže z RN** a nahradí odkazem na Disk | konektor |

> ⚠️ Přesun je ve výchozím stavu **vypnutý** a zapíná se vědomě. Při **prvním** běhu si konektor stávající
> soubory zapamatuje jako „staré" (baseline) a nepřesouvá je – přesouvají se jen soubory přidané potom.

#### Karta „Nastavení konektoru" — sekce Chování synchronizace

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Model synchronizace** | výběr | *Odkazy (doporučeno)* = RN drží jen odkazy; *Zrcadlení kopií* = kopíruje obsah | konektor |
| **Politika mazání** | výběr | *Koš + reconcile (doporučeno)* nebo *Nemazat odkazy* | konektor |
| **Reconcile interval (min)** | číslo (min. 5) | Jak často se automaticky stahují změny z Disku | konektor |
| **Úroveň logování** | výběr | Kolik detailů se loguje (debug/info/warn/error) | konektor |
| **Šablona podsložek (čárkou)** | seznam názvů | Podsložky, které se založí u zakázky bez vzoru | konektor |
| **Plné zrcadlení stromu Disku do modulu Dokumenty** | přepínač | Zapne zrcadlení celého stromu do RN Dokumentů | konektor |
| **Zapnout automatickou synchronizaci** | přepínač | Zapne plánovač: periodický reconcile + obnovu push kanálu | konektor |
| **Uložit nastavení** | tlačítko | Uloží všechna pole (tajemství jen pokud je vyplníš) | konektor |
| **Test spojení** | tlačítko | Ověří spojení s Raynetem i Google Diskem dle uložených tajemství | konektor |
| **Naposledy proběhlo** | informativní údaj | Čas a výsledek posledního automatického běhu | konektor |

> 📸 SCREENSHOT: výsledek „Test spojení" – dva řádky (Raynet ✓, Google Drive ✓) se zelenými fajfkami

#### Karta „Ruční test" a diagnostika

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **ID company v Raynetu** + **Vytvořit složku** | vstup a tlačítko | Spustí založení složky zákazníka ručně (test bez čekání na webhook) | konektor |
| **Vypsat strom vzoru** | tlačítko | Vypíše strukturu vzorové složky „0. vzor" (ověření, že konektor vidí správný vzor) | konektor |
| **Načíst strukturu Dokumentů z RN** | tlačítko | Načte kořen modulu Dokumenty z Raynetu (diagnostika před zrcadlením) | konektor |
| **Zkusit odkaz v Dokumentech (test)** | tlačítko | Zkusí v RN Dokumentech založit testovací složku a odkaz (po ověření smaž v Raynetu) | konektor |

#### Karta „Hromadný import z Raynetu"

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Spočítat rozsah** | tlačítko | Jen zjistí, kolik je v RN firem / OP / nabídek / objednávek (nic nezakládá) | konektor |
| **Spustit import** | tlačítko | Po potvrzení zařadí do fronty úlohy pro všechna existující data (běží na pozadí) | konektor |

#### Karta „Synchronizace Disk → Raynet"

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Spustit reconcile teď** | tlačítko | Hned stáhne změny z Disku a promítne je do RN jako odkazy | konektor |
| **Zapnout / Vypnout push (watch)** | přepínací tlačítko | Zapne/vypne okamžité upozornění z Google Disku (push místo čekání na interval) | konektor |
| **Zrcadlit strom do Dokumentů** | tlačítko | Zařadí zrcadlení celého stromu Disku do RN Dokumentů (na pozadí) | konektor |
| **Skenovat Dokumenty teď** | tlačítko | Zařadí sken RN Dokumentů (RN → Disk) hned, bez čekání na naplánovanou hodinu | konektor |
| **stav push** | informativní text | „Push aktivní, platí do …" / „Push neaktivní" | konektor |

#### Karta „Raynet → Disk (ruční test)"

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **ID dokumentu v Raynetu** | vstup | Který dokument z RN se má stáhnout | konektor |
| **ID company (nepovinné)** | vstup | Doplní firmu, když ji konektor z dokumentu nezjistí | konektor |
| **Stáhnout na Disk** | tlačítko | Stáhne dokument z RN a nahraje do složky klienta na Disku | konektor |

#### Panel „Logy konektoru"

| Prvek | Co to je | Co udělá | Kdo vidí |
|---|---|---|---|
| **Filtr úrovně** | výběr | Vše / Info / Varování / Chyby / Debug | konektor |
| **Hledat** | pole | Hledá ve zprávě a v názvu události | konektor |
| **Obnovovat (5 s)** | přepínač | Automatické obnovování tabulky | konektor |
| **Obnovit** | tlačítko | Načte logy teď | konektor |
| **Vyčistit** | tlačítko | Po potvrzení **smaže všechny** logy konektoru (nelze vrátit) | konektor |

> 📸 SCREENSHOT: panel Logy – tabulka Čas / Úroveň (barevné štítky) / Událost / Zpráva s filtrem nahoře

### Jak zadat tajemství (a proč se zpět nezobrazí)
Tajemství jsou **Raynet API klíč** a **Google service-account JSON**. Fungují jako „write-only":

- Vyplníš je v příslušném poli a dáš **Uložit nastavení**. Uloží se do databáze **šifrovaně**.
- Zpět se **nikdy nezobrazí** – u pole se ukáže jen značka **„✓ nastaven"** a placeholder „•••••••• (vyplň
  jen pro změnu)". Server posílá do prohlížeče jen příznak, že tajemství existuje, ne jeho hodnotu.
- **Prázdné pole při ukládání = neměnit.** Stávající hodnota zůstane. Přepíšeš ji jen tím, že vyplníš novou.
- Tajemství jde uložit jen tehdy, když je na serveru správně nastavený šifrovací klíč `KONEKTOR_ENC_KEY`
  (viz „Pro admina"). Jinak uložení tajemství skončí chybou.

### Jak na…
- **První nastavení:** vyplň sekci Raynet (instance, API uživatel, base URL, kódy polí, API klíč) a sekci
  Google (ID Shared Drive, vzorová složka, service-account JSON, případně impersonovaný uživatel) → **Uložit**
  → **Test spojení** (obě služby musí být ✓).
- **Ověřit, že vidím správný vzor:** karta Ruční test → **Vypsat strom vzoru**.
- **Otestovat založení složky, než pustím ostrý provoz:** Ruční test → zadej *ID company* → **Vytvořit složku**;
  výsledek nabídne odkaz „otevřít na Disku".
- **Založit složky pro všechna stávající data v Raynetu:** karta Import → **Spočítat rozsah** (kolik toho je)
  → **Spustit import** (potvrdíš, běží na pozadí, průběh sleduj v Logu).
- **Zapnout okamžité promítání souborů z Disku do RN:** karta Synchronizace → **Zapnout push (watch)**.
  Bez push se změny stahují periodicky podle „Reconcile intervalu" (musí být zapnutá automatická synchronizace).
- **Zrcadlit celý Disk do RN Dokumentů:** karta Synchronizace → **Zrcadlit strom do Dokumentů** (dlouhý běh,
  na pozadí, výsledek v Logu pod událostí „zrcadleni").
- **Přesouvat soubory z RN na Disk:** v Nastavení zapni „Přesouvat nové soubory z RN na Disk", ulož; první
  sken jen zapamatuje staré soubory, přesouvat začne až ty přidané potom.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Konektor** vidí v rozcestníku **všichni**, ale bez práva `konektor` je **zamčená** (🔒).
- **Všechny chráněné endpointy** konektoru (nastavení, logy, test spojení, ruční akce, import, reconcile,
  watch, zrcadlení, sken) hlídá jeden strážce `vyzaduj_pravo_konektor`, který volá `muze_otevrit(user, "konektor")`.
  Uvnitř stránky se práva **dál nedělí** – kdo Konektor otevře, může na něm cokoli (včetně zadání tajemství).
- **Supersprávce** (`uzivatel.je_admin`) má právo `konektor` vždy.
- **Webhookové endpointy jsou veřejné (bez JWT)** – volají je Raynet a Google. Ověřují se vlastním
  mechanismem: Raynet sdíleným tokenem v hlavičce, Google `channel tokenem` (viz níže).
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky), klíč práva `konektor` je
  v `backend/app/auth/permissions.py`.

### Potřebné externí přístupy (dodává zadavatel)
- **Raynet:** název instance, API uživatel, **API klíč** (Nastavení → Pro vývojáře → API klíče; vyžaduje
  tarif Professional a výš). Auth = HTTP Basic (uživatel : API klíč) + hlavička `X-Instance-Name`.
- **Google Workspace:** **service account** s **domain-wide delegation** a scope `https://www.googleapis.com/auth/drive`,
  soubory ve **Shared Drive** (ne osobní My Drive). Do konektoru se vloží service-account **JSON** a **ID Shared Drive**;
  volitelně e-mail uživatele k **impersonaci** (delegace).
- **Vlastní pole v Raynetu** (typ odkaz/URL) u company, obchodního případu (dvě), nabídky a objednávky – jejich
  **kódy** se zadají v Nastavení. Bez nich se odkaz nemá kam zapsat.
- **Webhooky v Raynetu** (Nastavení → Pro vývojáře) směřované na `/api/konektor/webhooks/raynet` se stejným
  tokenem, jaký je v poli „Webhook token".

### Šifrovací klíč a další proměnné v `.env`
- **`KONEKTOR_ENC_KEY`** – Fernet klíč, kterým se šifrují tajemství (Raynet API klíč, Google SA JSON) v DB.
  Žije jen v `.env` (chmod 600, mimo git), ne v databázi. **Ztráta klíče = nutnost zadat tajemství znovu.**
  Bez platného klíče nejdou tajemství uložit. Kód: `backend/app/konektor/crypto.py`.
- **`KONEKTOR_WEBHOOK_SECRET`** – token, kterým Google značí push notifikace (`X-Goog-Channel-Token`);
  konektor ho kontroluje u příchozího Drive push.
- **`PUBLIC_BASE_URL`** (alt. `APP_URL`) – veřejná adresa appky, ze které se sestaví adresa Drive push
  endpointu (`…/api/konektor/webhooks/drive`).

### Napojení na okolní systémy
- **Raynet CRM** – čtení záznamů, zápis odkazu do vlastních polí, zakládání/mazání odkazových dokumentů,
  stahování obsahu souborů, správa modulu Dokumenty. Klient `backend/app/konektor/raynet_klient.py`.
  Respektuje **denní API limit** (429 → `RateLimitError`, sken/zrcadlení se bezpečně přeruší); před drahým
  full-scanem se navíc kontroluje zbývající budget přes hlavičku `X-RateLimit-Remaining`.
- **Google Drive** – service account (Drive API v3): kopírování stromu, tvorba/hledání složek, upload,
  `changes.list`, push kanály (`files.watch`). Klient `backend/app/konektor/google_klient.py`.

### Jak to funguje uvnitř (stručně technicky)

**Datový model** (`backend/app/konektor/models.py`, prefix `konektor_`):
- `konektor_nastaveni` – jednořádková konfigurace (`id=1`): přístupy Raynet/Google (tajemství šifrovaně
  v `raynet_api_key_enc`, `google_sa_json_enc`), kódy polí, kontejnery, chování synchronizace, nastavení
  skenu Dokumentů (`dms_sken_*`, `dms_presun_zapnuto`, `dms_baseline`), stav posledního běhu.
- `konektor_log` – provozní/chybový log (oddělený od obecné tabulky `logy`). Do zprávy ani kontextu se
  **nikdy nedostane tajemství ani obsah dokumentů**. Čistí se jen ručně z UI.
- `konektor_entity_folder` – mapování Raynet záznam (company/deal/offer/order) → jeho složka na Disku
  (+ uložená ID kontejnerů kvůli odolnosti vůči přejmenování).
- `konektor_file_map` – mapování dokument (Raynet) ↔ soubor na Disku (+ `last_synced_source` pro echo suppression).
- `konektor_tree_mirror` – zrcadlení stromu Disku do modulu Dokumenty (Flow C).
- `konektor_client_folder_map` – starší mapování company → složka (používá směr RN→Disk).
- `konektor_drive_channels`, `konektor_drive_change_state` – push kanály a uložený page token pro `changes.list`.
- `konektor_processed_events` – idempotence příchozích událostí.
- `konektor_job_queue` – DB fronta úloh (webhook rychle zařadí, worker zpracuje).

**API** (`backend/app/konektor/routes.py`, prefix `/konektor`):
- `GET /konektor/nastaveni` — načte nastavení (tajemství jen jako příznak „nastaveno").
- `PUT /konektor/nastaveni` — uloží nastavení; prázdné tajemství = neměnit.
- `GET /konektor/logy` — výpis logů (filtr `uroven`, `hledej`, `limit`).
- `DELETE /konektor/logy` — smaže všechny logy.
- `POST /konektor/test-spojeni` — ověří spojení s Raynetem i Google.
- `POST /konektor/webhooks/raynet` — **veřejný**; příjem Raynet webhooku (ověří token, zařadí úlohu).
- `POST /konektor/webhooks/drive` — **veřejný**; příjem Google Drive push (ověří channel token, zařadí reconcile/dms).
- `POST /konektor/klient/{company_id}/slozka` — ruční Flow A pro danou company.
- `POST /konektor/vzor/strom` — diagnostika: strom vzorové složky.
- `POST /konektor/dokumenty/nahled` — diagnostika: struktura modulu Dokumenty v RN.
- `POST /konektor/dokumenty/test-odkaz` — diagnostika: test založení odkazu v Dokumentech.
- `POST /konektor/import/rozsah` — spočítá rozsah dat v Raynetu.
- `POST /konektor/import` — zařadí hromadný import do fronty.
- `POST /konektor/dokument/{document_id}/na-disk` — ruční Flow B (RN → Disk) pro dokument.
- `POST /konektor/reconcile` — ruční reconcile (Disk → Raynet).
- `POST /konektor/zrcadlit` — zařadí zrcadlení stromu do Dokumentů.
- `POST /konektor/dms-sken` — zařadí sken Dokumentů (RN → Disk).
- `GET /konektor/watch`, `POST /konektor/watch`, `DELETE /konektor/watch` — stav / registrace / zrušení push kanálu.

**Toky (Flow):**
- **Flow A (FR1):** vznik company/deal/offer/order → složka na Disku podle vzoru „0. vzor" + zpětný odkaz do RN.
- **Flow B – Disk → Raynet (FR2a):** `changes.list` → nové soubory ve složkách OP → odkazové dokumenty v RN;
  smazané/koš → odkaz se odebere.
- **Flow B – Raynet → Disk (FR2b):** dokument nahraný v RN → stažení → upload do složky klienta (značka
  `origin=raynet` proti smyčce).
- **Flow C – zrcadlení do Dokumentů (FR3):** obsah zdrojové složky Disku → složky + odkazy v modulu Dokumenty.
- **Sken Dokumentů (RN → Disk):** detekce/přesun fyzických souborů z RN Dokumentů na Disk (bezpečné pořadí:
  stáhnout → ověřit → nahrát → ověřit → teprve smazat v RN → vložit odkaz).

**Scheduler / watch / webhooky** (`backend/app/konektor/scheduler.py`, `fronta.py`):
- Worker běží jako **jedno vlákno** (probouzí se á 5 s): bere splatné úlohy z DB fronty a zpracovává je
  **sekvenčně** (souběžnost vůči Raynetu = 1, drží limit spojení). Chyby → retry s exponenciálním backoffem
  (max 6 pokusů), pak `failed`. Vlákno nikdy nespadne.
- Kromě fronty periodicky spouští **reconcile** (dle intervalu, jen když je automatika zapnutá), **obnovu
  push kanálu** a **sken Dokumentů** v naplánované časy (Europe/Prague).
- **Webhooky přes Caddy `/api`:** příchozí webhooky jdou na stávající greensie vhost přes reverse proxy
  `/api/*` → `127.0.0.1:8000`, tj. `POST /api/konektor/webhooks/raynet` a `/api/konektor/webhooks/drive`.
  **Žádný nový Caddy vhost ani systemd unit** – reuse existující infrastruktury.

**Klíčové soubory:**
- Backend: `routes.py` (API + webhooky), `logika.py` (všechny toky), `models.py` (tabulky),
  `schemas.py` (vstup/výstup, ochrana tajemství), `crypto.py` (Fernet šifrování),
  `raynet_klient.py`, `google_klient.py` (klienti), `scheduler.py` (worker + plánovač),
  `fronta.py` (zařazení úloh), `logger.py` (zápis do `konektor_log`).
- Frontend: `frontend/src/pages/Konektor.jsx` (celá stránka), funkce v `frontend/src/api.js`
  (`konektor*`), routa `/konektor` v `frontend/src/App.jsx`, právo/dlaždice v `backend/app/auth/permissions.py`.

### Časté potíže / co dělat, když…
- **„Chybí nebo je neplatný KONEKTOR_ENC_KEY"** při ukládání tajemství → v `.env` chybí/je neplatný Fernet
  klíč. Bez něj tajemství nejdou uložit; ostatní pole ano.
- **Test spojení hlásí „API klíč není nastaven" / „service-account JSON není nastaven"** → tajemství ještě
  nebyla uložena (nebo se ztratil `KONEKTOR_ENC_KEY` a dešifrování vrací prázdno) – zadej je znovu.
- **„Překročen limit požadavků Raynetu (429)"** → vyčerpán denní API limit. Sken/zrcadlení se bezpečně
  přeruší a zkusí po resetu; baseline ani přesun se při přerušení neprovedou.
- **Webhook z Raynetu se odmítá (v logu „neplatný token")** → token v poli „Webhook token" nesedí s tokenem
  nastaveným v Raynet webhooku; log vypíše názvy přijatých hlaviček pro diagnostiku.
- **Reconcile píše „inicializováno" a nic nevytvořil** → první běh jen začne sledovat změny od teď (historie
  se zpětně nezpracovává, řeší ji volitelná migrace F7).
- **Ruční akce vrací 502** → chyba při volání Raynetu/Google (např. neexistující ID, nedostupné API) – detail
  je v hlášce a v Logu.
- **Import běží dlouho** → zpracovává se sekvenčně na pozadí; je idempotentní, co už složku má, se přeskočí,
  dá se pustit i opakovaně.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Stav MVP:** F0–F3 označeno jako hotovo (2026-07-23), v kódu jsou navíc hotové i F4 (RN→Disk), F5 (zrcadlení)
  a rozpracované F6 (zpevnění). Ověřeno **bez reálných přístupů** (import/migrace, chráněné endpointy, parsery,
  dedup, build). Zdroj: `raynet-gdrive-INVENTORY.md` sekce 8.
- **TO VERIFY / čeká na přístupy:** reálné akceptační testy A1–A4, zachycení skutečného **payloadu Raynet
  webhooku**, přesný tvar **odkazového dokumentu** v Raynetu, přesné **kódy vlastních polí** company/OP/nabídky/
  objednávky a tvar detailu dokumentu (RN→Disk). Parsery jsou psané tolerantně a doladí se po zadání přístupů.
  Konektor je proto **blokovaný na dodání přístupů** (Raynet API klíč, Google SA JSON + delegace + ID Shared Drive).
- **Práva uvnitř stránky se nedělí:** doporučení specu „správu tajemství omezit jen na `je_admin`" zatím **není
  v kódu** – tajemství smí zadat každý s právem `konektor`. Kdyby to vadilo, je to úprava strážce v `routes.py`.
- **Ruční tlačítka nejsou omezena na admina** (na rozdíl od modulu Přehled projektů, kde „Načíst z Freela"
  smí jen admin). Zde má vše, kdo otevře Konektor.
- **Model synchronizace „mirror"** (zrcadlení kopií) je v nastavení volitelný, ale hlavní toky jsou postavené
  na modelu **odkazů** – „mirror" použití v kódu ještě prověřit.
- **Přesun RN → Disk maže originál v RN** – zapínat vědomě; ochranu tvoří baseline (staré soubory) a bezpečné
  pořadí kroků (smaže se až po ověřené kopii na Disku).

## Odkazy
- Kód backend: `backend/app/konektor/` · frontend: `frontend/src/pages/Konektor.jsx`
- Technický spec: [`docs/moduly/raynet-gdrive-konektor-spec.md`](../../moduly/raynet-gdrive-konektor-spec.md)
- Inventura a stav fází: `docs/moduly/raynet-gdrive-INVENTORY.md`
- Paměť projektu: Konektor Raynet↔GDrive (viz `MEMORY.md`)
