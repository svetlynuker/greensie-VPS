# Technický spec: Konektor RAYNET CRM ↔ Google Drive

> **Pro koho:** tento dokument je zadání pro Claude Code běžící na cílovém serveru (VPS). Je psaný tak, aby ho šlo vzít, provést **Fázi 0 (inventura serveru)** a pak postupně implementovat.
>
> **Jazyk kódu:** implementace v angličtině (identifikátory, logy), tento spec v češtině.
>
> **Zásada:** maximálně **využij, co už na serveru je** (databáze, runtime, reverzní proxy, scheduler, fronta). Nic neinstaluj, dokud neproběhne inventura a neexistuje jasný důvod, že vhodný nástroj chybí.

---

## 0. Než začneš — přečti si tohle

1. Neprogramuj hned. Nejdřív proveď **Fázi 0 (kap. 5)** a vytvoř `INVENTORY.md` — soupis „požadováno vs. dostupné vs. rozhodnutí (reuse/instalovat)".
2. Pak si nech od zadavatele potvrdit **Otevřené otázky (kap. 18)** a **externí přístupy (kap. 4)**.
3. Teprve potom stav podle **plánu prací (kap. 17)**, po fázích, s testem po každé fázi.
4. Kde je v textu **`TO VERIFY`**, znamená to, že přesné chování Raynet API si musíš ověřit v jeho dokumentaci (`https://app.raynetcrm.com/api/doc/index-en.html`) nebo dotazem na podporu — nevymýšlej endpointy.

---

## 1. Účel a funkční požadavky

Konektor propojuje RAYNET CRM a Google Drive tak, aby dokumentace ke klientům žila na Disku a v Raynetu byla dostupná a provázaná.

**FR1 — Nový klient → struktura složek**
Při vzniku nového klienta (company/account) v Raynetu se na Disku automaticky vytvoří složka klienta s definovanou podstrukturou. Odkaz na tuto složku se zapíše zpět ke klientovi v Raynetu.

**FR2 — Obousměrná synchronizace dokumentů**
Soubor přidaný do složky klienta na Disku se objeví u klienta v Raynetu. Soubor nahraný přes Raynet se propíše do odpovídající složky na Disku. Viz **designové rozhodnutí D1** (model odkazů vs. zrcadlení kopií).

**FR3 — Zobrazení „celého disku" v modulu Dokumenty**
V modulu Dokumenty v Raynetu se zrcadlí stromová struktura složek z Disku (jako složky + odkazové dokumenty), aby uživatel viděl obsah Disku uvnitř Raynetu.

**Mimo rozsah (non-goals)**
- Editace souborů uvnitř Raynetu (soubory se editují na Disku).
- Synchronizace obsahu Google-nativních dokumentů (Docs/Sheets) jako binárek — pouze odkazy.
- Migrace historických dat (řeší se jednorázově, viz kap. 17, volitelná fáze).

---

## 2. Klíčová designová rozhodnutí

**D1 — Model synchronizace dokumentů (výchozí: odkazy).**
- **Model A – Odkazy (DOPORUČENO, výchozí):** Disk je jediné úložiště obsahu. Raynet drží jen odkaz (URL / napojený Drive soubor). Odpadají konflikty verzí, duplicita a limit 50 MB v Raynetu.
- **Model B – Zrcadlení kopií:** fyzická kopie na obou stranách. Vyžaduje hashování obsahu, řešení konfliktů (last-writer-wins nebo conflict-copy) a potlačení smyček. Víc práce, křehčí. Implementuj jen pokud to zadavatel výslovně chce.

**D2 — Úložiště na straně Google (výchozí: Shared Drive + service account).**
- **Google Workspace:** service account s **domain-wide delegation**, soubory ve **Shared Drive** (vlastní organizace, ne osobní My Drive → čisté vlastnictví a kvóty).
- **Osobní Google účet (bez Workspace):** OAuth klient + dlouhodobý **refresh token** servisního uživatele, složky v My Drive. Pozor na kvóty a vlastnictví.

**D3 — Zdroj pravdy = Google Drive.** Při nejednoznačnosti vyhrává stav na Disku.

**D4 — Události, ne jen polling.** Raynet webhooky + Google Drive push (`files.watch`) s periodickým `changes.list` jako pojistkou.

---

## 3. Předpoklady na serveru (co MUSÍ být k dispozici)

Toto je vstupní checklist. Ve Fázi 0 každou položku ověř a zapiš do `INVENTORY.md` stav: **✅ je / ⚠️ je, ale nevhodné / ❌ chybí** + rozhodnutí.

| # | Schopnost | Požadavek | Preferovaný reuse | Fallback |
|---|-----------|-----------|-------------------|----------|
| S1 | Runtime | Node.js LTS ≥ 20 **nebo** PHP ≥ 8.1 | to, co už na serveru běží a tým umí | doinstalovat Node LTS |
| S2 | Databáze | relační DB pro mapování a stav | existující **PostgreSQL/MySQL/MariaDB** → vlastní schéma/DB `raynet_gdrive_sync` | **SQLite** soubor (stačí pro nízký objem) |
| S3 | Veřejné HTTPS | příchozí webhooky z Raynetu i Googlu (443, platný TLS cert) | existující **nginx/Caddy/Traefik** → nový vhost/route | instalovat **Caddy** (automatické Let's Encrypt) |
| S4 | Veřejná doména/subdoména | např. `raynet-sync.mojefirma.cz` s A/AAAA záznamem | existující DNS | zřídit subdoménu |
| S5 | Scheduler | obnova Drive watch kanálů + reconcile job | existující **systemd timer / cron** | systemd timer |
| S6 | Process management | služba běží trvale a restartuje se | existující **systemd / Docker / pm2** | systemd unit |
| S7 | Správa tajemství | bezpečné uložení API klíčů a service-account JSON | existující vault / **systemd credentials** / soubor `.env` s `chmod 600` | `.env` mimo web root, `chmod 600` |
| S8 | Odchozí síť | HTTPS na `app.raynetcrm.com` a `*.googleapis.com` | — | povolit ve firewallu |
| S9 | Fronta úloh (volitelné) | serializace a retry | existující **Redis** (BullMQ apod.) | **DB-backed** job tabulka (kap. 7) |
| S10 | Git + build | verzování a build závislostí | existující | doinstalovat |

**Pravidla reuse (dodržet):**
- Máš-li běžící Postgres/MySQL → **nezakládej nový DB engine**, vytvoř vyhrazenou databázi/schéma a uživatele s právy jen na ně.
- Máš-li nginx/Caddy → **přidej vhost**, nespouštěj druhý reverzní proxy.
- Máš-li Redis → použij ho na frontu; jinak **nevytahuj Redis kvůli tomuhle**, stačí DB fronta.
- Volba runtime (S1): pokud na serveru běží PHP stack, zvaž PHP (Raynet má referenčního REST klienta v PHP). Pokud Node, jdi do Node (Google `googleapis` knihovna je prvotřídní). Nerozšiřuj zbytečně počet jazyků na serveru.

---

## 4. Externí předpoklady (dodá zadavatel, mimo server)

- **Raynet:** název instance, API uživatel, **API klíč** (Nastavení → Pro vývojáře → API klíče). Vyžaduje tarif **Professional a výš**. `TO VERIFY`: zda daný tarif zpřístupňuje endpointy pro dokumenty/přílohy (kap. 9).
- **Google – dle D2:** buď **service account JSON** + zapnutá delegace + **ID Shared Drive**, nebo **OAuth client_id/secret + refresh_token** servisního účtu.
- **Doména** pro webhook endpointy (S4) a možnost nastavit DNS.
- Definice **šablony podsložek** klienta (výchozí: `01_Nabídky`, `02_Smlouvy`, `03_Faktury`, `04_Ostatní` — potvrdit/upravit).
- Název **vlastního pole** u company v Raynetu pro odkaz na Drive složku (vytvořit v Raynetu, `TO VERIFY` název a kód pole přes API).

---

## 5. Fáze 0 — Inventura serveru (první, co uděláš)

Spusť diagnostiku a vytvoř `INVENTORY.md`. Níže orientační příkazy (uprav dle OS; nespoléhej na to, že všechny existují):

```bash
# OS a základ
cat /etc/os-release; uname -a; whoami; id

# Runtime
node -v 2>/dev/null; npm -v 2>/dev/null
php -v 2>/dev/null; composer --version 2>/dev/null

# Databáze (co běží a poslouchá)
command -v psql && psql --version; pg_isready 2>/dev/null
command -v mysql && mysql --version; command -v mariadb && mariadb --version
ss -ltnp | grep -E '5432|3306' 2>/dev/null
systemctl list-units --type=service --state=running | grep -Ei 'postgre|mysql|maria|redis' 2>/dev/null

# Reverzní proxy / web server
command -v nginx && nginx -v; command -v caddy && caddy version
command -v traefik && traefik version
ss -ltnp | grep -E ':80|:443' 2>/dev/null

# Fronta
command -v redis-cli && redis-cli ping 2>/dev/null

# Scheduler a proces management
systemctl --version 2>/dev/null | head -1
crontab -l 2>/dev/null; command -v docker && docker ps 2>/dev/null; command -v pm2 && pm2 ls 2>/dev/null

# Odchozí konektivita
curl -sS -o /dev/null -w "raynet:%{http_code}\n" https://app.raynetcrm.com/ 2>/dev/null
curl -sS -o /dev/null -w "google:%{http_code}\n" https://www.googleapis.com/ 2>/dev/null

# Volné zdroje
df -h /; free -m
```

**Výstup `INVENTORY.md` musí obsahovat:** tabulku S1–S10 (požadováno vs. nalezeno vs. rozhodnutí reuse/instalovat), zvolený runtime a DB, jak se vyřeší veřejné HTTPS (reuse proxy vs. nová), a seznam věcí, které je potřeba doinstalovat — **ke schválení zadavatelem před instalací**.

---

## 6. Architektura

```
        Raynet CRM                         Google Drive (Shared Drive)
            │  webhook (změna záznamu)          │  push (files.watch) + changes.list
            ▼                                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │   Reverzní proxy (reuse: nginx/Caddy) — TLS, /webhooks/*   │
   └───────────────────────────────────────────────────────────┘
            │                                   │
            ▼                                   ▼
   ┌───────────────────────────────────────────────────────────┐
   │  Konektor (S6 služba)                                      │
   │  - HTTP vrstva: /webhooks/raynet, /webhooks/drive, /healthz│
   │  - Worker: fronta úloh (Redis nebo DB), retry/backoff      │
   │  - Klienti: RaynetClient, DriveClient                      │
   │  - Reconciler + Watch-renewer (scheduler S5)               │
   └───────────────────────────────────────────────────────────┘
            │
            ▼
   ┌───────────────────────────────────────────────────────────┐
   │  DB (reuse): mapování, stav sync, idempotence, fronta      │
   └───────────────────────────────────────────────────────────┘
```

Komponenty:
- **HTTP vrstva** — přijímá webhooky, rychle je ověří, zařadí do fronty, vrátí 2xx.
- **Worker** — zpracovává úlohy idempotentně, s retry a backoff.
- **RaynetClient / DriveClient** — tenké fasády nad oběma API.
- **Reconciler** — periodicky dorovná stav (pojistka proti zmeškaným událostem).
- **Watch-renewer** — obnovuje expirující Drive push kanály.

---

## 7. Datový model

Vytvoř ve vyhrazené DB (S2). SQL je ilustrační (Postgres dialekt; u SQLite uprav typy).

```sql
-- Mapování klient ↔ složka na Disku
CREATE TABLE client_folder_map (
  raynet_company_id   BIGINT PRIMARY KEY,
  drive_folder_id     TEXT NOT NULL,
  drive_folder_url    TEXT NOT NULL,
  client_name         TEXT,
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);

-- Mapování dokument ↔ soubor na Disku
CREATE TABLE file_map (
  id                  BIGSERIAL PRIMARY KEY,
  raynet_company_id   BIGINT REFERENCES client_folder_map(raynet_company_id),
  raynet_document_id  TEXT,               -- ID záznamu/odkazu v Raynetu (TO VERIFY tvar)
  drive_file_id       TEXT,               -- ID souboru na Disku
  drive_file_url      TEXT,
  content_hash        TEXT,               -- jen pro Model B (zrcadlení)
  last_synced_source  TEXT,              -- 'raynet' | 'drive'  (echo suppression)
  state               TEXT DEFAULT 'active', -- active | trashed
  updated_at          TIMESTAMPTZ DEFAULT now(),
  UNIQUE (drive_file_id),
  UNIQUE (raynet_document_id)
);

-- Idempotence příchozích událostí
CREATE TABLE processed_events (
  event_key   TEXT PRIMARY KEY,     -- hash zdroje+typu+id+revize
  processed_at TIMESTAMPTZ DEFAULT now()
);

-- Google Drive push kanály (kvůli obnově)
CREATE TABLE drive_channels (
  channel_id   TEXT PRIMARY KEY,
  resource_id  TEXT NOT NULL,
  expiration   TIMESTAMPTZ NOT NULL,
  page_token   TEXT
);

-- Uložený startPageToken pro changes.list
CREATE TABLE drive_change_state (
  id           INT PRIMARY KEY DEFAULT 1,
  page_token   TEXT NOT NULL
);

-- Fronta úloh (fallback, pokud není Redis)
CREATE TABLE job_queue (
  id           BIGSERIAL PRIMARY KEY,
  type         TEXT NOT NULL,
  payload      JSONB NOT NULL,
  run_after    TIMESTAMPTZ DEFAULT now(),
  attempts     INT DEFAULT 0,
  status       TEXT DEFAULT 'pending',  -- pending | done | failed
  last_error   TEXT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## 8. Endpointy konektoru

- `POST /webhooks/raynet` — příjem Raynet webhooku. Ověř původ (kap. 13), ulož jako job, vrať `200` rychle.
- `POST /webhooks/drive` — příjem Google push notifikace (hlavičky `X-Goog-Channel-ID`, `X-Goog-Resource-State`, `X-Goog-Resource-ID`). Ověř `channel token`, zařaď `drive.changes` job, vrať `200`.
- `GET /healthz` — liveness/readiness (DB ping, stav watch kanálů).
- Interní (scheduler, ne veřejné): `reconcile`, `renew-drive-watch`.

---

## 9. Integrace RAYNET (ověřit a použít)

**Auth (očekávaný vzor — `TO VERIFY` v dokumentaci):** REST/JSON, base URL `https://app.raynetcrm.com/api/v2/`. HTTP Basic (uživatel : API klíč) + hlavička s názvem instance (`X-Instance-Name`). Ve Fázi „integrace" ověř přesné názvy hlaviček přímo v `https://app.raynetcrm.com/api/doc/index-en.html`.

**Potřebné operace:**
- **Company** — číst detail (`GET /company/{id}/`), reagovat na vznik. Zápis odkazu na Drive složku do vlastního pole (`PUT/POST` custom field). `TO VERIFY` kód vlastního pole.
- **Dokumenty / přílohy** — `TO VERIFY` (klíčové pro FR2 směr Raynet→Disk):
  - zda existuje endpoint knihovny Dokumentů / příloh u company,
  - zda umí **vytvořit odkazový záznam** (URL) — potřeba pro Model A,
  - zda umí **stáhnout binární obsah** souboru nahraného v Raynetu — potřeba pro propsání Raynet→Disk.
  - Pokud stažení obsahu přes API nejde, směr Raynet→Disk se u nahrávek omezí; Disk→Raynet a FR1/FR3 tím nejsou dotčeny. Tuto skutečnost zapiš do `INVENTORY.md` a eskaluj zadavateli.

**Webhooky Raynet:** konfigurují se v Nastavení → Pro vývojáře. Fungují na událostech vytvoření/změny/smazání záznamu. Ve Fázi 0/1 zaregistruj testovací webhook na `POST /webhooks/raynet` a **zachyť reálný payload** — podle něj postav parser (nespoléhej na dohad struktury).

---

## 10. Integrace Google Drive

**Auth (dle D2):** service account + delegace + Shared Drive, nebo OAuth refresh token. Scope: `https://www.googleapis.com/auth/drive`.

**Operace (Drive API v3):**
- `files.create` (mimeType `application/vnd.google-apps.folder`) — vytvoření složek; `parents` = ID nadřazené složky; `supportsAllDrives=true`.
- `files.create` s uploadem — nahrání souboru (směr Raynet→Disk, Model B / archiv).
- `files.list` — výpis obsahu složky (`q="'{folderId}' in parents and trashed=false"`, `includeItemsFromAllDrives=true`, `supportsAllDrives=true`).
- `files.get` (`fields=id,name,webViewLink,parents,md5Checksum,trashed`).
- `changes.getStartPageToken` + `changes.list` — inkrementální změny (pojistka + hlavní detekce, když push zmešká).
- `files.watch` — push notifikace na endpoint `/webhooks/drive`; kanál má expiraci → viz obnova.

**Obnova watch:** kanály expirují (řádově dny). Scheduler (S5) je obnovuje před expirací; `drive_channels` drží `expiration`. K tomu vždy periodický `changes.list` jako záchrana.

---

## 11. Toky — detailní logika (pseudokód)

**Flow A — nový klient → složky (FR1)**
```
on raynet webhook (company.created):
  if event already in processed_events: return
  company = RaynetClient.getCompany(id)
  root = createFolder(name=`${company.name} [${id}]`, parent=SHARED_DRIVE_ROOT)
  for sub in TEMPLATE_SUBFOLDERS: createFolder(sub, parent=root)
  save client_folder_map(id, root.id, root.webViewLink, company.name)
  RaynetClient.setCompanyDriveField(id, root.webViewLink)   # TO VERIFY pole
  registerDriveWatch(folderId=root.id)                      # aby se hlídal obsah
  mark processed_events
```

**Flow B — dokumenty obousměrně (FR2), Model A (odkazy)**
```
# Disk -> Raynet
on drive push (change in klientské složce):
  changes = DriveClient.changes.list(savedPageToken)
  for ch in changes:
     if ch.file.trashed: RaynetClient.removeLink(map.raynet_document_id); file_map.state='trashed'
     elif new/updated:
        company = resolveCompanyByFolder(ch.file.parents)
        if last_synced_source == 'raynet' and unchanged: skip   # echo suppression
        docId = RaynetClient.upsertLinkDocument(company, name=ch.file.name, url=ch.file.webViewLink)
        upsert file_map(company, docId, ch.file.id, url, last_synced_source='drive')
  save new pageToken

# Raynet -> Disk
on raynet webhook (document/attachment added):    # jen pokud to API umožňuje, kap. 9
  if source marker == this connector: skip          # echo suppression
  bin = RaynetClient.downloadDocument(docId)         # TO VERIFY
  folder = client_folder_map[company].drive_folder_id
  f = DriveClient.upload(bin, name, parent=folder, appProperties={origin:'raynet'})
  (Model A) RaynetClient.replaceWithLink(docId, f.webViewLink)   # volitelné
  upsert file_map(..., last_synced_source='raynet')
```

**Flow C — zrcadlení celého disku do Dokumentů (FR3)**
```
initial + on drive change:
  walk Shared Drive tree (files.list rekurzivně)
  mirror do Raynet Dokumentů: složky -> složky, soubory -> odkazové dokumenty (URL=webViewLink)
  udržuj přes stejný changes.list stream jako Flow B
  (volitelně) jen kořenový odkaz na Shared Drive, pokud plné zrcadlení není žádoucí
```

---

## 12. Robustnost: smyčky, idempotence, konflikty

- **Echo suppression:** každý zápis, který dělá konektor, označ původem — na Disku `appProperties.origin='raynet'`, v `file_map.last_synced_source`. Protistranný watcher pak vlastní změny ignoruje.
- **Idempotence:** každou příchozí událost identifikuj klíčem (`source+type+id+revize`) a ulož do `processed_events`; duplicity zahoď.
- **Konflikty (Model B):** porovnávej `content_hash` / `md5Checksum`; při kolizi vyhrává Disk (D3) nebo vytvoř `…(conflict).ext` — potvrdit zadavatelem.
- **Mazání:** výchozí politika **koš + reconcile**, ne tvrdý delete. Smazání na Disku → odkaz v Raynetu se odebere/označí; smazání v Raynetu neodstraní soubor na Disku (Disk = zdroj pravdy).
- **Rate limity / retry:** fronta s exponenciálním backoff, respektuj `429`/`5xx`, omez souběžnost.
- **Reconcile:** periodicky (např. každých 15 min) projdi `changes.list` od uloženého tokenu a dorovnej, co push zmeškal.

---

## 13. Bezpečnost

- **Ověření webhooků:** Raynet — ověř sdílené tajemství/hlavičku nebo allowlist IP (`TO VERIFY` možnosti). Google — kontroluj `X-Goog-Channel-Token`, který sis nastavil při `files.watch`.
- **Tajemství (S7):** API klíč a service-account JSON mimo web root, práva `600`, nikdy do gitu. `.env` v `.gitignore`.
- **Least privilege:** DB uživatel jen na vyhrazenou DB; Google scope jen `drive` (ideálně omezený na daný Shared Drive); Raynet API uživatel jen s nutnými právy.
- **TLS:** povinné na webhook endpointech (reuse proxy / Caddy auto-cert).
- **Logy:** nesmí obsahovat tajemství ani celý obsah dokumentů.

---

## 14. Konfigurace (příklad `.env`)

```
# Raynet
RAYNET_INSTANCE=mojefirma
RAYNET_API_USER=api@mojefirma.cz
RAYNET_API_KEY=***
RAYNET_COMPANY_DRIVE_FIELD=customField_XX   # TO VERIFY

# Google
GOOGLE_AUTH_MODE=service_account            # nebo oauth
GOOGLE_SA_JSON_PATH=/etc/raynet-sync/sa.json
GOOGLE_SHARED_DRIVE_ID=***
# nebo pro oauth:
# GOOGLE_CLIENT_ID=...  GOOGLE_CLIENT_SECRET=...  GOOGLE_REFRESH_TOKEN=...

# Konektor
PUBLIC_BASE_URL=https://raynet-sync.mojefirma.cz
SYNC_MODEL=links                            # links | mirror
TEMPLATE_SUBFOLDERS=01_Nabidky,02_Smlouvy,03_Faktury,04_Ostatni
DB_URL=postgres://user:pass@localhost:5432/raynet_gdrive_sync
QUEUE_BACKEND=db                            # db | redis
REDIS_URL=redis://localhost:6379            # jen když redis
DRIVE_WEBHOOK_TOKEN=***                     # náhodné, kontroluje se u push
```

---

## 15. Nasazení

- Služba jako **systemd unit** (nebo Docker, dle S6), auto-restart.
- Reverzní proxy: přidej vhost/route pro `PUBLIC_BASE_URL` → lokální port služby; jen `/webhooks/*` a `/healthz` veřejně.
- Scheduler (S5): timer/cron na `renew-drive-watch` (např. denně) a `reconcile` (např. každých 15 min).
- Migrace DB skriptem (kap. 7). Rollback = drop vyhrazené DB.
- Runbook: jak obnovit watch ručně, jak přehrát reconcile, kde jsou logy.

---

## 16. Testování a akceptace

- **Unit:** parsery webhook payloadů, echo suppression, mapování, idempotence.
- **Integrační (nejdřív na testovací Raynet instanci a testovacím Shared Drive):** reálné volání API v sandboxu.
- **Akceptační scénáře:**
  - A1: vytvoř klienta v Raynetu → vznikne složka + podsložky + odkaz u klienta.
  - A2: nahraj soubor do složky na Disku → do pár minut je odkaz u klienta v Raynetu.
  - A3: (pokud API umožní) nahraj dokument v Raynetu → objeví se soubor ve složce na Disku.
  - A4: přejmenuj/smaž soubor na Disku → odpovídající změna odkazu v Raynetu.
  - A5: ověř, že vlastní zápis konektoru **nespustí** zpětnou smyčku.
  - A6: shoď push, počkej na reconcile → stav se dorovná.
- **Verifikace:** po každé fázi spusť příslušný scénář; smyčky a idempotenci testuj cíleně (dvojité doručení stejné události).

---

## 17. Plán prací (fáze)

- **F0 — Inventura (kap. 5):** `INVENTORY.md`, rozhodnutí reuse/instalovat, schválení.
- **F1 — Skeleton:** služba + DB migrace + auth k Raynetu a Googlu + `/healthz`. Zachyť reálné payloady webhooků.
- **F2 — Flow A (FR1):** složky + zpětný odkaz. Akceptace A1.
- **F3 — Flow B, směr Disk→Raynet (FR2a):** push + changes.list + odkazové dokumenty. Akceptace A2, A4.
- **F4 — Flow B, směr Raynet→Disk (FR2b):** dle výsledku ověření kap. 9. Akceptace A3.
- **F5 — Flow C (FR3):** zrcadlení stromu / kořenový odkaz. 
- **F6 — Zpevnění:** echo/idempotence/reconcile/rate-limit, bezpečnost, runbook. Akceptace A5, A6.
- **F7 (volitelná) — Migrace historie:** jednorázové dorovnání existujících klientů a souborů.

Doporučené první dodání (MVP): **F0–F3**.

---

## 18. Otevřené otázky k potvrzení (před F1)

1. **Model D1:** odkazy (výchozí) vs. zrcadlení kopií?
2. **Google účet (D2):** Workspace (service account + Shared Drive) nebo osobní účet (OAuth refresh token)?
3. **Raynet dokumenty přes API (kap. 9):** umí API vytvořit odkazový dokument a stáhnout obsah? (rozhoduje o F4)
4. **Šablona podsložek** a **název vlastního pole** pro odkaz na Disk.
5. **Politika mazání** (koš+reconcile výchozí) a chování při konfliktu (Model B).
6. **Rozsah FR3:** plné zrcadlení stromu, nebo stačí kořenový odkaz na Shared Drive?

---

## Příloha — rychlé ověřovací příkazy pro API (po dodání přístupů)

```bash
# Raynet – ověř auth a základní čtení (uprav dle přesného auth v dokumentaci)
curl -u "$RAYNET_API_USER:$RAYNET_API_KEY" \
     -H "X-Instance-Name: $RAYNET_INSTANCE" \
     "https://app.raynetcrm.com/api/v2/company/?limit=1"

# Google – ověř přístup ke Shared Drive (přes vygenerovaný access token)
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
     "https://www.googleapis.com/drive/v3/files?corpora=drive&driveId=$GOOGLE_SHARED_DRIVE_ID&includeItemsFromAllDrives=true&supportsAllDrives=true&pageSize=1"
```

> Přesné tvary Raynet endpointů/hlaviček a dostupnost operací s dokumenty **ověř v** `https://app.raynetcrm.com/api/doc/index-en.html` a případně u podpory Raynetu, než na nich postavíš F3/F4.
