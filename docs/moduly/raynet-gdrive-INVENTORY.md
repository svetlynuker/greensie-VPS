# INVENTORY.md — Fáze 0, konektor RAYNET CRM ↔ Google Drive

> Výstup Fáze 0 (kap. 5 specu). Inventura cílového serveru, rozhodnutí reuse/instalovat, ověření Raynet API a otevřené otázky. **Nic se zatím neinstaluje ani neprogramuje — čeká se na schválení zadavatelem.**
>
> Datum inventury: 2026-07-23 · Server: `Greensie-app` (Debian 12) · Uživatel: `dan`

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
| **S1** | Runtime | Node ≥ 20 **nebo** PHP ≥ 8.1 | ✅ | **Node v24.18.0** + npm 11.16.0; Python 3.11.2 (FastAPI stack). PHP/composer **není**. | **REUSE Node v24** (viz rozhodnutí R1 níže — návrh, ke schválení). Nic neinstalovat. |
| **S2** | Databáze | relační DB pro stav/mapování | ✅ | **PostgreSQL 15.18** běží, `127.0.0.1:5432`, `postgresql@15-main` active. | **REUSE Postgres** → nová vyhrazená DB `raynet_gdrive_sync` + omezený uživatel. Žádný nový engine, žádné SQLite. |
| **S3** | Veřejné HTTPS | příchozí webhooky, 443, platný TLS | ✅ | **Caddy v2.11.4** (systemd, běží 9+ dní), poslouchá `:80` a `:443`, auto Let's Encrypt. Importuje `/etc/caddy/sites/*.caddy`. nginx/traefik/apache **není**. | **REUSE Caddy** → přidat nový vhost jako samostatný soubor do `/etc/caddy/sites/`. Nespouštět druhou proxy. |
| **S4** | Veřejná doména | subdoména s A/AAAA | ✅ | `*.167-235-254-188.sslip.io` řeší wildcard na IP serveru — subdoménu netřeba zřizovat. | Pro MVP **REUSE sslip.io** (např. `raynet-sync.167-235-254-188.sslip.io`). Pro produkci zvážit vlastní `raynet-sync.greensie.cz` (viz otevřená otázka Q7). |
| **S5** | Scheduler | obnova watch + reconcile | ✅ | **systemd 252** (timery), `atd` běží. cron prázdný. | **REUSE systemd timer** (renew-drive-watch denně, reconcile á 15 min). |
| **S6** | Process mgmt | trvalý běh + restart | ✅ | **systemd** — vzory `tlakova-crm.service`, `greensie-backend.service` (Restart=always). Docker/pm2 **není**. | **REUSE systemd unit** dle vzoru tlakova-crm (User=dan, EnvironmentFile, NoNewPrivileges, PrivateTmp). |
| **S7** | Správa tajemství | API klíče, SA JSON | ✅ | Bez vaultu; systemd credentials k dispozici. Precedent: `.env` přes `EnvironmentFile=`. | `.env` (chmod 600) + SA JSON (chmod 600) mimo web root, oboje do `.gitignore`. |
| **S8** | Odchozí síť | HTTPS na Raynet a Google | ✅ | `app.raynetcrm.com` → HTTP 302 (dosažitelný), `www.googleapis.com` → HTTP 404 (dosažitelný, očekávaná odpověď rootu). | OK, firewall nic neblokuje. Ověřit i `app.raynet.cz` dle zvolené instance (Q3). |
| **S9** | Fronta (volitelné) | serializace + retry | ⚠️ | **Redis není.** | Dle pravidel reuse **nevytahovat Redis kvůli tomuhle** → **DB-backed `job_queue`** tabulka (kap. 7 specu). |
| **S10** | Git + build | verzování, build | ✅ | Git je (repo greensie-app, aktivní větve), npm 11 pro build. | REUSE. Konektor jako samostatný adresář/modul v repu. |

**Legenda:** ✅ je a vhodné · ⚠️ chybí, ale řešeno fallbackem dle pravidel · ❌ chybí kriticky (žádné takové)

---

## 3. Zvolený runtime a DB (návrh k rozhodnutí)

### R1 — Runtime: **Node.js v24** (doporučeno)
Server hostuje jak Python (greensie-app), tak Node (tlakova-crm), takže obojí je „domácí". Pro **tento** konektor navrhuji **Node.js**:
- Google `googleapis` je v Node prvotřídní, výborně udržovaná knihovna (Drive API v3, push kanály, service account).
- Node v24 už je nainstalované; existuje osvědčený vzor Node systemd služby (`tlakova-crm`).
- Raynet je čisté REST/JSON — jazykově neutrální, žádná výhoda pro Python.

**Alternativa (Python/FastAPI):** konzistence s hlavním stackem greensie-app (stejný jazyk, sdílený tým, sdílený venv vzor). Nevýhoda: Google klient v Pythonu je použitelný, ale méně pohodlný pro push/watch. → **rozhodnutí nechávám na zadavateli (otevřená otázka Q1).**

### R2 — Databáze: **PostgreSQL 15** (reuse)
Vyhrazená DB `raynet_gdrive_sync` + role s právy jen na ni. Schéma dle kap. 7 specu (Postgres dialekt beze změn). **Pozn.:** založení DB/role vyžaduje `sudo -u postgres psql` (dan má sudo přes heslo) — provede se na začátku F1 se schválením, jde o krok „k doinstalování/nastavení" níže.

### R3 — Veřejné HTTPS: **reuse Caddy**
Nový vhost jako soubor `/etc/caddy/sites/raynet-sync.caddy`, reverse_proxy na lokální port konektoru (např. `127.0.0.1:8010`), veřejně jen `/webhooks/*` a `/healthz`. Caddy vyřeší TLS automaticky. Zápis do `/etc/caddy/` vyžaduje sudo.

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

Instalace nových balíků: **žádná není nutná pro runtime** (Node, Postgres, Caddy, systemd — vše je). Následující kroky jsou **konfigurační** a vyžadují sudo — provedou se až po schválení, na začátku F1:

| # | Akce | Nástroj | Proč | Vyžaduje |
|---|------|---------|------|----------|
| 1 | Založit DB `raynet_gdrive_sync` + omezenou roli | `sudo -u postgres psql` | vyhrazený stav konektoru (S2) | sudo (heslo) |
| 2 | Přidat vhost `/etc/caddy/sites/raynet-sync.caddy` + reload Caddy | sudo, `caddy reload` | veřejné HTTPS pro webhooky (S3) | sudo |
| 3 | Vytvořit systemd unit `raynet-gdrive-sync.service` + timery | sudo | trvalý běh + scheduler (S5/S6) | sudo |
| 4 | npm závislosti konektoru (`googleapis`, HTTP framework, pg driver…) | npm (lokálně v adresáři modulu) | běh konektoru | — (bez sudo) |
| 5 | Adresář na tajemství (`/etc/raynet-gdrive-sync/` nebo v repu mimo git) pro `.env` + SA JSON, chmod 600 | sudo/mkdir | bezpečnost (S7) | dle umístění |

> **Nové systémové balíky (apt): 0.** Vše kritické je reuse. npm balíky jsou lokální závislosti modulu, ne systémová instalace.

---

## 6. Externí přístupy (dodá zadavatel — kap. 4)

Zatím **chybí, blokuje F1+**:
- Raynet: název instance, API uživatel, **API klíč** (tarif Professional+); potvrzení base URL (`.cz` vs `.com`).
- Google (dle D2): buď **service account JSON** + domain-wide delegation + **ID Shared Drive**, nebo **OAuth client_id/secret + refresh_token**.
- Definice šablony podsložek a název vlastního pole company pro odkaz na Drive.

---

## 7. Bezpečnostní stav

- Pracuji na větvi `raynet-gdrive-konektor` (mimo `main`). ✅
- `.env` a service-account JSON půjdou do `.gitignore`, chmod 600, mimo web root. (Nastaví se ve F1.)
- DB uživatel jen na vyhrazenou DB; Google scope jen `drive`; Raynet API uživatel s minimem práv.
- Před destruktivními akcemi (drop DB, přepis configu) se ptám.
