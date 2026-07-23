# INVENTORY.md — Fáze 0, konektor RAYNET CRM ↔ Google Drive

> Výstup Fáze 0 (kap. 5 specu). Inventura cílového serveru, rozhodnutí reuse/instalovat, ověření Raynet API a otevřené otázky. **Nic se zatím neinstaluje ani neprogramuje — čeká se na schválení zadavatelem.**
>
> Datum inventury: 2026-07-23 · Server: `Greensie-app` (Debian 12) · Uživatel: `dan`

---

## 0. Potvrzená rozhodnutí zadavatele (2026-07-23)

| Otázka | Rozhodnutí |
|---|---|
| **Architektura / runtime (R1)** | **Konektor jako modul uvnitř greensie-app (Python/FastAPI + React)** — NE samostatná Node.js služba. Jeden proces, jedna DB, jednotná auth/práva/logy, webhooky přes stávající Caddy `/api`. |
| **Config + logy** | **Spravované přímo ve frontendu greensie-app** (nová dlaždice/stránka „Konektor"), dle vzoru admin nastavení + modulu Logy. |
| **Tajemství (Raynet klíč, Google SA JSON)** | **Editovatelná z UI, write-only, uložená šifrovaně v DB** (nikdy se nezobrazí zpět). Vyžaduje šifrovací klíč v `.env`. |
| D1 — model synchronizace | **Odkazy** (Model A) — Disk = zdroj obsahu, Raynet drží URL |
| D2 — Google účet | **Workspace + Shared Drive** — service account + domain-wide delegation |
| FR3 — rozsah | **Plné zrcadlení stromu** složek + odkazových dokumentů do Raynet Dokumentů |

> **Pozn.:** Rozhodnutí R1 se během F0 změnilo z Node.js na Python-modul právě kvůli požadavku na správu configu + logů přímo ve frontendu greensie-app. Odchylka od původního specu (kap. 3, S1) je vědomá a zdůvodněná níže (sekce 3).

**Stále čeká na zadavatele (blokuje start F1):**
- Raynet: instance, API uživatel, API klíč (Professional+), potvrzení base URL (`app.raynet.cz` vs `.com`).
- Google Workspace: service account JSON + zapnutá domain-wide delegation + **ID Shared Drive**.
- Šablona podsložek (default `01_Nabídky, 02_Smlouvy, 03_Faktury, 04_Ostatní`) + název vlastního pole company pro odkaz na Drive.
- Potvrzení politiky mazání (default koš + reconcile).

---

## 1. Souhrn serveru

| Vlastnost | Zjištěno |
|-----------|----------|
| OS | Debian GNU/Linux 12 (bookworm), x86_64 |
| Kernel | 6.1.0-48-amd64 |
| Uživatel | `dan` (uid 1000), ve skupině `sudo` (sudo **vyžaduje heslo** — ne NOPASSWD) |
| Veřejná IP | `167.235.254.188` |
| Doména | `167-235-254-188.sslip.io` (wildcard přes sslip.io — `*.167-235-254-188.sslip.io` → tato IP) |
| CPU / RAM | 2 jádra / 3,8 GB (volných ~2,1 GB), **žádný swap** |
| Disk `/` | 75 GB, volných 67 GB (8 % využito) |

**Na serveru už běží dvě aplikace** (důležité pro reuse):
- `greensie-backend.service` — hlavní projekt: **Python FastAPI/uvicorn** na `127.0.0.1:8000`, venv, `After=postgresql.service`. Frontend = statický React v `/var/www/greensie`.
- `tlakova-crm.service` — **Node.js** aplikace (SQLite), `ExecStart=/usr/bin/node server.js`, běží jako `User=dan`. → **existuje osvědčený precedent Node.js systemd služby na tomto serveru.**

---

## 2. Tabulka S1–S10: požadováno vs. nalezeno vs. rozhodnutí

| # | Schopnost | Požadavek | Stav | Nalezeno | Rozhodnutí |
|---|-----------|-----------|:----:|----------|------------|
| **S1** | Runtime | Node ≥ 20 **nebo** PHP ≥ 8.1 | ✅ | **Node v24.18.0**; **Python 3.11.2** (FastAPI stack greensie-app). PHP/composer **není**. | **REUSE Python** — konektor = modul greensie-app (R1). Node se nepoužije. Nic neinstalovat. |
| **S2** | Databáze | relační DB pro stav/mapování | ✅ | **PostgreSQL 15.18** běží, `127.0.0.1:5432`, `postgresql@15-main` active. | **REUSE stávající greensie DB** → tabulky `konektor_*` (R2). Žádná nová DB, žádný nový engine. |
| **S3** | Veřejné HTTPS | příchozí webhooky, 443, platný TLS | ✅ | **Caddy v2.11.4** (systemd), poslouchá `:80`/`:443`, auto Let's Encrypt, existující vhost greensie `/api/*` → `:8000`. | **REUSE stávající vhost** — webhooky přes `/api/konektor/webhooks/*`. **Bez nového vhostu.** |
| **S4** | Veřejná doména | subdoména s A/AAAA | ✅ | `167-235-254-188.sslip.io` už slouží greensie-app. | **REUSE stávající domény** — webhook URL = `https://167-235-254-188.sslip.io/api/konektor/webhooks/...`. |
| **S5** | Scheduler | obnova watch + reconcile | ✅ | **systemd 252**; navíc greensie-app má **vzor background vlákna** (`matice/scheduler.py`, á 60 s čte nastavení z DB). | **REUSE background vlákno** v FastAPI (renew-watch, reconcile) — dle vzoru matice. Bez samostatného timeru. |
| **S6** | Process mgmt | trvalý běh + restart | ✅ | **systemd** — konektor poběží uvnitř existující `greensie-backend.service` (Restart=always). | **REUSE `greensie-backend.service`.** Žádný nový unit. |
| **S7** | Správa tajemství | API klíče, SA JSON | ✅ | Bez vaultu; precedent `.env` přes `python-dotenv`. | Tajemství **šifrovaně v DB** (R4), write-only z UI. Šifrovací klíč `KONEKTOR_ENC_KEY` v `.env` (chmod 600, `.gitignore`). |
| **S8** | Odchozí síť | HTTPS na Raynet a Google | ✅ | `app.raynetcrm.com` → HTTP 302 (dosažitelný), `www.googleapis.com` → HTTP 404 (dosažitelný, očekávaná odpověď rootu). | OK, firewall nic neblokuje. Ověřit i `app.raynet.cz` dle zvolené instance (Q3). |
| **S9** | Fronta (volitelné) | serializace + retry | ⚠️ | **Redis není.** | Dle pravidel reuse **nevytahovat Redis kvůli tomuhle** → **DB-backed `job_queue`** tabulka (kap. 7 specu). |
| **S10** | Git + build | verzování, build | ✅ | Git je (repo greensie-app, aktivní větve), npm 11 pro build. | REUSE. Konektor jako samostatný adresář/modul v repu. |

**Legenda:** ✅ je a vhodné · ⚠️ chybí, ale řešeno fallbackem dle pravidel · ❌ chybí kriticky (žádné takové)

---

## 3. Zvolená architektura, runtime a DB (rozhodnuto)

### R1 — Runtime: **Python modul uvnitř greensie-app** (rozhodnuto)
Konektor **není** samostatná služba, ale nový balíček `backend/app/konektor/` ve stávající FastAPI aplikaci + stránka `frontend/src/pages/Konektor.jsx`. Důvody:
- Zadavatel chce config i logy spravovat přímo ve frontendu greensie-app → konektor patří dovnitř aplikace.
- greensie-app má hotovou veškerou potřebnou infrastrukturu: modulární vzor `app/<modul>/`, systém práv/dlaždic, DB logy + stránku Logy, vzor „jednořádkové nastavení + poslední běh" (`NastaveniSynchronizace` + karta), scheduler na pozadí (vlákno á 60 s čte nastavení z DB).
- Jeden runtime, jeden deploy (stávající `greensie-backend.service`), jedna DB, jednotná autentizace/práva/audit — nulová duplicita.
- Google klient: `google-api-python-client` (Drive API v3, push kanály, service account) — plně dostačuje.

**Odchylka od specu (kap. 3, S1):** spec předpokládal samostatnou službu; požadavek na integrované UI ji činí zbytečnou a křehčí. Node se nepoužije.

### R2 — Databáze: **stávající greensie DB, tabulky modulu `konektor`** (reuse)
Konektor přidá vlastní tabulky (prefix `konektor_*`) do **stávající greensie databáze** — ne samostatná DB `raynet_gdrive_sync`. Důvod: FastAPI má jeden connection pool a tabulky musí být čitelné ve stejné DB pro UI. Tvorba schématu přes `create_all` + ruční „lehká migrace" (`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) dle vzoru `main.py` — **žádný nový DB engine ani DB, žádný Alembic.** Datový model specu (kap. 7) se přenese do SQLAlchemy modelů (`konektor_client_folder_map`, `konektor_file_map`, `konektor_processed_events`, `konektor_drive_channels`, `konektor_change_state`, `konektor_job_queue`) + nově `konektor_nastaveni` (jednořádkové) a `konektor_log`.

### R3 — Veřejné HTTPS: **reuse stávajícího Caddy vhostu greensie** (bez nového vhostu)
Webhooky půjdou na stávající doménu greensie přes existující reverse_proxy `/api/*` → `127.0.0.1:8000`: `POST /api/konektor/webhooks/raynet`, `POST /api/konektor/webhooks/drive`. **Žádný nový Caddy vhost ani systemd unit.** Pozor: webhook endpointy musí být v FastAPI vyňaty z JWT auth (ověřují se vlastním sdíleným tajemstvím / Google channel tokenem, ne přihlášeným uživatelem).

### R4 — Tajemství: **šifrovaně v DB, write-only z UI** (rozhodnuto)
Raynet API klíč a Google SA JSON se zadávají z UI, ukládají šifrovaně (symetricky, `cryptography`/Fernet) do `konektor_nastaveni` a nikdy se nevrací zpět (UI ukazuje jen „nastaveno ✓/✗" + tlačítko Test připojení). **Šifrovací klíč** (`KONEKTOR_ENC_KEY`) žije v `.env` (chmod 600, mimo git) — ne v DB. Bez něj nelze tajemství dešifrovat (rotace = nutnost znovu zadat).

---

## 4. Ověření Raynet API (kap. 9 — řešení TO VERIFY)

Ověřeno v `https://app.raynetcrm.com/api/doc/index-en.html`.

| Bod | Zjištění | Dopad |
|-----|----------|-------|
| **Auth** | HTTP Basic (`user:api-key`) + hlavička `X-Instance-Name: <instance>` (alternativně `X-Instance-Id` nebo `Authorization: Bearer`). TLS 1.2+ povinné. | ✅ Potvrzeno — přesně dle očekávání ve specu. |
| **Base URL** | `.com` = `https://app.raynetcrm.com/api/v2/`, ale **existuje i `https://app.raynet.cz/api/v2/`**. Greensie je česká firma → instance je pravděpodobně na `.cz`. | ⚠️ Ověřit správnou base URL dle instance (Q3). |
| **Company (FR1)** | `GET /company/`, `PUT /company/` (create), `GET /company/{id}/`, `POST /company/{id}/` (modify), `GET /company/ext/{extId}/`. | ✅ Čtení i zápis (vč. custom fieldu) proveditelné. |
| **Custom field pro odkaz** | Custom fieldy se v detailu company vrací jako systémové klíče typu `Cislo_klie_cd702`. Konfigurace přes `GET /customfield/`. | ✅ Kód pole zjistíme z `GET /company/{id}/` nebo `/customfield/` po vytvoření pole v Raynetu (Q5). |
| **Dokumenty (FR2/FR3)** | `GET /document/` (list složek/souborů), `PUT /document/` (create folder), `PUT /document/document/` (create document), `GET/POST/DELETE /document/{id}/`. | ✅ **Umí vytvářet složky i dokumenty** — dobré pro FR3 zrcadlení. |
| **Odkazový dokument (URL) — Model A** | Dokumentace zmiňuje „link-type documents", ale **přesné schéma pole pro URL se přes automatický fetch nepodařilo plně vytáhnout.** | ⚠️ **TO VERIFY reálným voláním** po dodání přístupů (nebo dotazem na podporu). Nevymýšlím pole. |
| **Stažení binárního obsahu (Raynet→Disk, F4)** | API obsahuje operaci **„downloading body of file"** (+ meta data, image). Přílohy: `POST /file/` (upload), `PUT /attachment/`, `DELETE /attachment/{id}/`. | ✅ **Stažení obsahu je možné** → směr Raynet→Disk (F4) je proveditelný. Přesný endpoint path ověřit při F4. |
| **Webhooky** | Správa přes API: `GET /webhook/`, `PUT /webhook/` (create), `POST /webhook/{id}/`, `DELETE /webhook/{id}/`. | ✅ Registrace webhooku i přes API. **Payload a zabezpečení (secret/signature/IP) se z docs plně nevytáhly** → **zachytit reálný payload při F1** (dle kap. 9 specu). |
| **Rate limit** | 24 000 req/den (default), **4 souběžná spojení**, překročení → HTTP 429. Hlavičky `X-Ratelimit-*`. | ⚠️ Fronta musí omezit souběžnost na ≤ 4 a respektovat 429 (kap. 12). |
| **Tarif** | Endpointy dokumentů vyžadují tarif Professional+. | ⚠️ Ověřit tarif instance (Q3) — jinak FR2/FR3 nemusí být dostupné. |

**Shrnutí:** Raynet API pokrývá FR1 (company + custom field), FR2 obousměrně (documents + download body of file), i FR3 (documents/folders). Zbývající TO VERIFY = přesné schéma odkazového dokumentu a webhook payload — obojí se ověří reálným voláním, ne dohadem.

---

## 5. Co je potřeba doinstalovat / nastavit — KE SCHVÁLENÍ

Rozhodnutí postavit konektor jako modul greensie-app **odstranilo** potřebu nové DB, nového systemd unitu i nového Caddy vhostu. Zbývá minimum:

| # | Akce | Nástroj | Proč | Vyžaduje |
|---|------|---------|------|----------|
| 1 | Python balíčky do stávajícího venv: `google-api-python-client`, `google-auth`, `cryptography` (Fernet) | `pip` v `backend/venv` | Google Drive klient + šifrování tajemství | — (bez sudo) |
| 2 | Přidat `KONEKTOR_ENC_KEY` (a případně `KONEKTOR_WEBHOOK_SECRET`) do `.env` | editace `.env` | šifrování tajemství, ověření webhooků (R4, S7) | — (chmod 600 už je) |
| 3 | Ověřit/nastavit GRANT pro `greensie_user` na nové tabulky (dědí se z DB) | `psql` | tabulky `konektor_*` (S2) | typicky netřeba sudo |

> **Nové systémové balíky (apt): 0. Nové systemd unity: 0. Nové Caddy vhosty: 0. Nové DB: 0.** Vše je reuse stávající greensie-app infrastruktury. Přibývají jen 3 Python knihovny do existujícího venv a 1–2 řádky do `.env`.

---

## 5b. Integrace UI a config/logy do greensie-app (dle vzorů v kódu)

**Backend** — nový balíček `backend/app/konektor/`:
- `models.py` — tabulky `konektor_*` (kap. 7 specu) + `konektor_nastaveni` (jednořádkové, vzor `matice/models.py` `NastaveniSynchronizace`) + `konektor_log` (vzor `logy/models.py` `Log`).
- `schemas.py` — dvojice Out/Vstup (vzor `matice/schemas.py` `SyncNastaveniOut/Vstup`); tajemství jen ve Vstup (write-only), v Out jen boolean „nastaveno".
- `routes.py` — `APIRouter(prefix="/konektor")`, guard `vyzaduj_pravo_konektor()` (vzor `logy/routes.py`); webhook endpointy bez JWT (vlastní ověření). GET/PUT `/konektor/nastaveni`, GET `/konektor/logy`, `POST /konektor/test-spojeni`.
- `crypto.py` — Fernet helper (šifrování/dešifrování tajemství klíčem `KONEKTOR_ENC_KEY`).
- `scheduler.py` — background vlákno (reconcile, renew-watch) dle `matice/scheduler.py`.
- Registrace: import modelů + `include_router` v `main.py`; nový klíč `"konektor"` do `PRAVA`/`DLAZDICE` v `auth/permissions.py`.

**Frontend**:
- `src/pages/Konektor.jsx` — stránka: karta Nastavení (vzor `SynchronizaceKarta` v `AdminNastaveni.jsx`) + panel Logy (vzor `Logy.jsx`, filtr + auto-refresh).
- `src/api.js` — sekce `// ---- Konektor ----` (`konektorNastaveni`, `konektorUlozNastaveni`, `konektorLogy`, `konektorTestSpojeni`).
- `App.jsx` route `/konektor`, dlaždice v `Rozcestnik.jsx` (`TRASY`/`IKONY`/`PODTITULY`), SVG case v `Ikona.jsx`. UI přes `fm-card`/`fm-btn` a CSS proměnné (žádná nová UI knihovna).

---

## 6. Externí přístupy (dodá zadavatel — kap. 4)

Zatím **chybí, blokuje F1+**:
- Raynet: název instance, API uživatel, **API klíč** (tarif Professional+); potvrzení base URL (`.cz` vs `.com`).
- Google (dle D2): buď **service account JSON** + domain-wide delegation + **ID Shared Drive**, nebo **OAuth client_id/secret + refresh_token**.
- Definice šablony podsložek a název vlastního pole company pro odkaz na Drive.

---

## 7. Bezpečnostní stav

- Pracuji na větvi `raynet-gdrive-konektor` (mimo `main`). ✅
- Tajemství **šifrovaně v DB** (Fernet), write-only z UI, nikdy se nevrací do frontendu; šifrovací klíč `KONEKTOR_ENC_KEY` jen v `.env` (chmod 600, `.gitignore`).
- **Webhook endpointy** (`/api/konektor/webhooks/*`) jsou veřejné (bez JWT) → musí mít vlastní ověření: Raynet sdílené tajemství/hlavička (nebo IP allowlist — `TO VERIFY`), Google `X-Goog-Channel-Token`.
- Přístup ke stránce Konektor jen s právem `konektor` (dlaždice zamčená bez něj); správa tajemství ideálně jen pro `je_admin`.
- Google scope jen `drive` (ideálně omezený na daný Shared Drive); Raynet API uživatel s minimem práv.
- Logy nesmí obsahovat tajemství ani obsah dokumentů (platí pro `konektor_log`).
- Před destruktivními akcemi (drop tabulek, přepis configu) se ptám.

---

## 8. Aktualizovaný plán prací (fáze) — přizpůsobený Python-modulu

MVP = **F0–F3**. Po každé fázi akceptační test (kap. 16 specu).

- **F0 — Inventura** (tento dokument) — ✅ HOTOVO.
- **F1 — Skeleton modulu:** ✅ HOTOVO. Balíček `app/konektor/`, právo/dlaždice `konektor`, stránka `Konektor.jsx` (Nastavení + Logy), `crypto.py`, šifrovaná write-only tajemství z UI, `POST /konektor/test-spojeni`, webhooky. Zbývá zachytit reálný payload Raynet webhooku (až s přístupy).
- **F2 — Flow A (FR1):** ✅ HOTOVO. company.created → složka + podsložky + zpětný odkaz; DB fronta + worker; ruční trigger. Akceptace A1 čeká na přístupy.
- **F3 — Flow B směr Disk→Raynet (FR2a):** ✅ HOTOVO. changes.list + odkazové dokumenty + koš; push watch (registrace/obnova); periodický i ruční reconcile. Akceptace A2, A4 čeká na přístupy.
- **F4 — Flow B směr Raynet→Disk (FR2b):** ⏳ stažení obsahu (`download body of file`) → upload na Disk. Akceptace A3.
- **F5 — Flow C (FR3):** plné zrcadlení stromu do Raynet Dokumentů.
- **F6 — Zpevnění:** echo suppression, idempotence, reconcile, rate-limit (≤ 4 spojení), doladění UI/logů. Akceptace A5, A6.
- **F7 (volitelná) — Migrace historie** existujících klientů.

> **MVP (F0–F3) hotovo 2026-07-23.** Ověřeno bez reálných přístupů (import/migrace, chráněné endpointy 401, webhooky, parsery, dedup, build). Reálné akceptační testy A1–A4, zachycení webhook payloadu a doladění `TO VERIFY` tvarů (odkazový dokument v `/document/document/`, název pole company, webhook payload) proběhnou po zadání přístupů v UI. Šifrovací klíč `KONEKTOR_ENC_KEY` a `KONEKTOR_WEBHOOK_SECRET` jsou v `.env` (chmod 600).
