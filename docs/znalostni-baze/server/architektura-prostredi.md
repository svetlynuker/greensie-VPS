# Architektura a prostředí serveru

> **Sekce:** Server a provoz · **Co to je:** provozní dokument o tom, kde a jak appka běží
> **Zdroje pravdy:** `deploy/Caddyfile`, `deploy/greensie-backend.service`, `deploy/install.sh`,
> `deploy/update.sh`, `backend/app/main.py`, `backend/app/database.py`, `backend/requirements.txt`

Tenhle dokument popisuje **serverovou/provozní stránku** Greensie app: z čeho se aplikace skládá,
kde běží, jak k ní teče požadavek z prohlížeče a jaké procesy a služby ji drží naživu. Je určený
adminovi a údržbě. Návody k jednotlivým modulům (dlaždicím) jsou ve složce
[`../moduly/`](../moduly/).

> 📸 SCREENSHOT: přihlašovací obrazovka na veřejné adrese https://167-235-254-188.sslip.io

---

## Přehled: co appka je a z čeho se skládá

Greensie app je **interní firemní webová aplikace** (za přihlášením). Skládá se ze tří hlavních
technických částí:

- **Frontend** — React (Vite). Jednostránková aplikace (SPA), která se sestaví (`npm run build`)
  do statických souborů v `frontend/dist/` a servíruje se jako obyčejné HTML/JS/CSS.
- **Backend** — FastAPI (Python 3) běžící pod **uvicornem**. Poskytuje REST API. V produkci
  poslouchá jen na `127.0.0.1:8000` (dovnitř serveru), navenek není přímo vidět.
- **Databáze** — **PostgreSQL**. Backend k ní přistupuje přes SQLAlchemy 2.0 + ovladač `psycopg2`.

Frontend s backendem nikdy nemluví napřímo — vždy přes společnou vstupní bránu (reverzní proxy
Caddy, viz níže).

### Kde to běží

| Věc | Hodnota |
|---|---|
| Poskytovatel | Hetzner VPS |
| Operační systém | Debian 12 |
| Uživatel, pod kterým appka běží | `dan` |
| Kořen projektu (git repo) | `~/projects/greensie-app` (`/home/dan/projects/greensie-app`) |
| Veřejná adresa | `https://167-235-254-188.sslip.io` |

**Proč taková adresa:** `sslip.io` je služba, která pro jakoukoli IP adresu vrátí doménu ve tvaru
`<ip-s-pomlckami>.sslip.io`. Díky tomu má server platné doménové jméno bez kupování domény, a Caddy
si k němu umí zdarma vytáhnout HTTPS certifikát od Let's Encrypt. IP serveru je tedy
**167.235.254.188** (v adrese zapsaná s pomlčkami místo teček).

---

## Tok požadavku (jak se web dostane k uživateli)

**Produkce:**

```
        https://167-235-254-188.sslip.io   (HTTPS 443, certifikát Let's Encrypt)
                        │
                        ▼
             ┌────────────────────┐
 prohlížeč ─▶│       CADDY        │  reverzní proxy, komprese (zstd/gzip)
             └─────────┬──────────┘
                       │
        ┌──────────────┴───────────────┐
        │ cesta /api/*                  │ všechny ostatní cesty
        │ handle_path (odřízne "/api")  │ handle
        ▼                               ▼
 ┌───────────────────┐        ┌──────────────────────────┐
 │ BACKEND (FastAPI) │        │ statický frontend         │
 │ uvicorn           │        │ root: /var/www/greensie   │
 │ 127.0.0.1:8000    │        │ try_files → /index.html   │
 └─────────┬─────────┘        └──────────────────────────┘
           │ SQLAlchemy + psycopg2
           ▼
    ┌──────────────┐
    │  PostgreSQL  │
    └──────────────┘
```

1. Prohlížeč jde na `https://167-235-254-188.sslip.io`.
2. Požadavek přijme **Caddy** (webový server / reverzní proxy) na portu 443. Caddy zajišťuje HTTPS
   (sám si obnovuje certifikát od Let's Encrypt) a komprimuje odpovědi (`encode zstd gzip`).
3. Caddy se rozhodne podle cesty (`deploy/Caddyfile`):
   - **Cesta začíná `/api/`** → pošle ji na backend (`reverse_proxy localhost:8000`). Blok
     `handle_path /api/*` přitom **odřízne prefix `/api`**, takže `/api/auth/login` dorazí do
     FastAPI jako `/auth/login`. (Proto mají routery v kódu prefixy bez `/api` — `/auth`, `/matice`, …)
   - **Jakákoli jiná cesta** → servíruje **statický frontend** z adresáře `/var/www/greensie`.
     Pravidlo `try_files {path} /index.html` zajistí, že když uživatel obnoví stránku na
     vnitřní adrese appky (React Router, např. `/projekty`), Caddy vrátí `index.html` a routing
     dořeší frontend — místo chyby 404.
4. Backend zpracuje API požadavek a přes SQLAlchemy/`psycopg2` mluví s PostgreSQL.

**Vývoj (lokálně):** roli Caddy přebírá **dev server Vite** (port `5173`), který přeposílá `/api`
na `http://localhost:8000` (nastavení v `frontend/vite.config.js`). Frontend tak volá API stejnou
cestou (`/api/...`) ve vývoji i v produkci — jen bránu dělá jednou Vite, jednou Caddy.

> 📸 SCREENSHOT: diagram toku požadavku (prohlížeč → Caddy → backend/frontend → PostgreSQL)

---

## Procesy a služby

Na serveru běží nezávisle na sobě:

- **`greensie-backend`** — služba **systemd** (`deploy/greensie-backend.service`), která drží
  backend naživu.
  - Startuje **po** `network.target` a `postgresql.service` (`Wants=postgresql.service`), aby DB
    byla připravená dřív než backend.
  - Běží pod uživatelem/skupinou `dan`, pracovní adresář `.../backend`.
  - Spouštěcí příkaz: `backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`.
    **Bez `--reload`** — v produkci se nesleduje změna souborů (to je jen vývojová věc).
  - `Restart=always`, `RestartSec=3` — když backend spadne, systemd ho po 3 s znovu nastartuje.
  - `WantedBy=multi-user.target` → **autostart** po rebootu serveru.
- **`caddy`** — služba webového serveru (nainstalovaná z oficiálního repozitáře Caddy), spuštěná a
  povolená (`systemctl enable`) při instalaci. Servíruje frontend a proxuje `/api`.
- **`postgresql`** — databázová služba.

Uvicorn běží **jednoprocesově** (bez explicitního počtu workerů). Na pozadí navíc backend spouští
dvě vlastní vlákna (viz startup události v `main.py`): **plánovač synchronizace z Freela**
(modul matice) a **worker fronty úloh konektoru** (Raynet ↔ Google Drive).

### Firewall

Instalační skript nastavuje **ufw** a povoluje jen tři porty:

| Port | K čemu |
|---|---|
| `22/tcp` | SSH (správa serveru) |
| `80/tcp` | HTTP (Caddy — přesměrování na HTTPS a ověření certifikátu) |
| `443/tcp` | HTTPS (veřejný web) |

Port backendu `8000` **není** ve firewallu otevřený a backend stejně poslouchá jen na
`127.0.0.1` — zvenčí je tedy nedostupný, chodí se k němu výhradně přes Caddy.

### Proč je frontend v `/var/www` a ne v domovském adresáři

Statický frontend se kopíruje do `/var/www/greensie` a vlastní ho uživatel **`caddy`**
(`chown -R caddy:caddy`). Servíruje ho totiž proces Caddy, který nemá přístup do `/home/dan`
(domovský adresář `dan` má typicky práva `700`, tedy jen pro majitele). Kdyby frontend zůstal
někde pod `/home/dan/...`, Caddy by na soubory „neviděl". Proto je build mimo repo, v
`/var/www/greensie`, kam Caddy dosáhne.

---

## Adresářová struktura repa

```
greensie-app/
├── backend/
│   ├── app/
│   │   ├── main.py         # vstupní bod: routery, CORS, migrace, seed, health, startup vlákna
│   │   ├── database.py     # SQLAlchemy engine, SessionLocal, Base, get_db()
│   │   ├── mailer.py       # odesílání e-mailů přes SMTP
│   │   ├── auth/           # uživatelé, skupiny, práva, JWT přihlášení
│   │   ├── admin/          # správa uživatelů a skupin (jen admin)
│   │   ├── nastaveni/      # uživatelské preference (vzhled, pohledy)
│   │   ├── matice/         # Přehled projektů (Pohled 1) + Freelo
│   │   ├── finance/        # Přehled financí (Pohled 2) + Pohoda (kostra)
│   │   ├── nabidkovac/     # Nabídkovač: katalog, nabídky, výpočty (peak shaving, PPA/FVE)
│   │   ├── zmeny/          # Přehled změn (denní snímky)
│   │   ├── logy/           # záznam požadavků (middleware) + prohlížení
│   │   └── konektor/       # konektor Raynet ↔ Google Drive
│   ├── requirements.txt    # Python závislosti (verze zamčené)
│   └── venv/               # Python virtuální prostředí (mimo git)
├── frontend/
│   ├── src/                # React zdroje (pages/, components/, styles/, api.js, App.jsx…)
│   ├── dist/               # sestavený build (mimo git; kopíruje se do /var/www/greensie)
│   └── vite.config.js      # dev server + proxy /api → :8000
├── deploy/
│   ├── Caddyfile               # konfigurace Caddy
│   ├── greensie-backend.service# systemd jednotka backendu
│   ├── install.sh              # jednorázová instalace produkce
│   └── update.sh               # nasazení nové verze
├── docs/                   # dokumentace, znalostní báze, specifikace
└── .env                    # tajná konfigurace (mimo git; NEČTE se do dokumentace)
```

---

## Backendové moduly (co který dělá)

Každý modul je vlastní balíček v `backend/app/` a registruje svůj router v `main.py`. Prefix je
cesta v API (Caddy před ni v produkci přidává `/api`).

| Modul | Prefix API | Jednou větou |
|---|---|---|
| **auth** | `/auth` | Přihlášení (JWT), info o přihlášeném uživateli a jeho právech, změna vlastního hesla. |
| **matice** | `/matice` | Přehled projektů — matice projektů × úkolů/fází, čtení i zápis, synchronizace z Freela. |
| **finance** | `/finance` | Přehled financí — faktury k projektům a jejich stavy, připravené (neaktivní) napojení na Pohodu. |
| **nabidkovac** | `/nabidkovac` | Nabídkovač pro obchodní zástupce — katalog technologií, nabídky a ekonomické výpočty (peak shaving, PPA/FVE). |
| **zmeny** | `/zmeny` | Přehled změn — denní snímky stavu a porovnání, co se mezi dvěma dny změnilo. |
| **nastaveni** | `/nastaveni` | Uživatelské preference (vzhled, téma, uložené pohledy). |
| **logy** | `/logy` | Záznam příchozích požadavků přes middleware a jejich prohlížení. |
| **admin** | `/admin` | Správa uživatelů, skupin a práv — celý router je za `vyzaduj_admina` (jen supersprávce). |
| **konektor** | `/konektor` | Konektor Raynet ↔ Google Drive — párování obchodních případů se složkami na Disku (běží na pozadí přes worker). |

Kromě routerů `main.py` při startu:
1. importuje modely a přes `Base.metadata.create_all` **vytvoří chybějící tabulky**;
2. spustí **`_lehka_migrace()`** — idempotentní `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, které
   doplní nové sloupce do už existujících tabulek (`create_all` je sám nepřidá);
3. naplní **seed data** (`_seed_sazby`, `_seed_baterie`) — idempotentně, ruční úpravy nepřepisuje;
4. nastaví **CORS** (povolené originy jen `http://localhost:5173` a `https://167-235-254-188.sslip.io`);
5. přidá logovací middleware a vystaví **`GET /health`** → `{"stav": "ok"}` (kontrola, že backend žije).

---

## Konfigurace přes proměnné prostředí (`.env`)

Backend čte konfiguraci z proměnných prostředí; `python-dotenv` je při startu načte ze souboru
`.env` v **kořeni repa** (`backend/app/database.py`). Soubor `.env` je mimo git a **jeho hodnoty
se do dokumentace zásadně nevypisují.** Níže jsou jen **názvy** proměnných, které kód používá
(zjištěné z `os.getenv` / `os.environ`) — nikoli jejich obsah:

| Proměnná | Používá modul | K čemu (podle kódu) |
|---|---|---|
| `DATABASE_URL` | database | **Povinná.** Připojení k PostgreSQL (bez ní backend spadne). |
| `SECRET_KEY` | auth | Podpisový klíč pro JWT tokeny. |
| `FREELO_EMAIL`, `FREELO_API_KEY` | matice | Přihlášení k Freelo API (čtení projektů/úkolů). |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_HESLO`, `SMTP_ODESILATEL` | mailer | Odesílání e-mailů přes SMTP. |
| `APP_URL` | mailer | Odkaz na appku vkládaný do e-mailů. |
| `NABIDKOVAC_UPLOAD_DIR` | nabidkovac | Adresář pro nahrané soubory (jinak `<kořen>/nabidka_soubory`). |
| `KONEKTOR_ENC_KEY` | konektor | Šifrování uložených tajemství konektoru. |
| `KONEKTOR_WEBHOOK_SECRET` | konektor | Ověření příchozích webhooků. |
| `PUBLIC_BASE_URL` | konektor | Veřejná adresa serveru pro sestavení URL webhooku. |

> Pozn.: Pohoda (`POHODA_*`) je v kódu jako kostra; tyto proměnné se v `backend/app/` aktuálně
> přes `os.getenv`/`os.environ` nenačítají — viz „Poznámky a úskalí".

---

## Nasazení (stručně, detail jinde)

- **`deploy/install.sh`** (jednorázově, jako root): zastaví dev servery, nainstaluje Caddy,
  nakopíruje frontend do `/var/www/greensie`, nasadí Caddyfile (`caddy validate` + restart),
  nasadí a povolí systemd službu backendu, nastaví ufw (22/80/443) a zkontroluje stav. **Neřeší**
  vytvoření venv, `pip install` ani build frontendu.
- **`deploy/update.sh`** (nová verze, jako root): `pip install -r requirements.txt` do venv,
  `npm install` + `npm run build`, kopie `dist/` do `/var/www/greensie`, `systemctl restart
  greensie-backend`, `systemctl reload caddy`.

Podrobný postup nasazení je v [nasazeni.md](nasazeni.md).

---

## Poznámky a úskalí (k ověření / nezřejmé)

- **Adresa je vázaná na IP.** Doména `167-235-254-188.sslip.io` je odvozená od IP serveru. Při
  změně IP (nový VPS) je nutné upravit adresu v `deploy/Caddyfile` i v seznamu povolených CORS
  originů v `backend/app/main.py`, jinak přestane fungovat HTTPS i volání API.
- **Backend běží jednoprocesově** (uvicorn bez `--workers`). Při vyšší zátěži může blokovat — viz
  poznámka v paměti projektu o plánu vyčlenit konektory do samostatných procesů (kvůli chybám 502).
- **`.env` musí být v kořeni repa**, ne v `backend/`. Cesta se počítá relativně z
  `backend/app/database.py` o tři úrovně výš. Když soubor chybí nebo nemá `DATABASE_URL`, backend
  při startu spadne (systemd ho pak stále dokola restartuje).
- **Frontend vlastní `caddy`, ne `dan`.** Po ručním nakopírování buildu je potřeba zachovat
  `chown -R caddy:caddy /var/www/greensie`, jinak Caddy soubory neservíruje.
- **Hetzner blokuje odchozí porty 25 a 465** (podle `mailer.py` je proto výchozí SMTP port 587
  STARTTLS) — potvrzeno v `docs/server-spec.md`, v tomto dokumentu nezávisle neověřeno z kódu portů.
- **Pohoda:** modul `finance` má integraci na Pohodu jako kostru; `docs/server-spec.md` zmiňuje
  proměnné `POHODA_URL/LOGIN/HESLO/ICO`, ale v aktuálním kódu `backend/app/` se přes
  `os.getenv`/`os.environ` nenačítají — buď je čtení jinde, nebo zatím není zapojené. **K ověření.**
- **Verze OS a poskytovatel** (Hetzner VPS, Debian 12) vycházejí ze zadání a paměti projektu,
  ne přímo z kódu v repu — pokud je potřeba jistota, ověřit na serveru (`hostnamectl`, `lsb_release`).

## Odkazy

- Konfigurace: [konfigurace.md](konfigurace.md) — databáze, `.env`, e-maily (SMTP)
- Nasazení: [nasazeni.md](nasazeni.md) — `deploy/install.sh`, `deploy/update.sh`, Caddy, systemd
- Práva a skupiny: [prava-a-skupiny.md](prava-a-skupiny.md) — uživatelé, skupiny, role
- Kód: `deploy/Caddyfile`, `deploy/greensie-backend.service`, `deploy/install.sh`,
  `deploy/update.sh`, `backend/app/main.py`, `backend/app/database.py`, `backend/requirements.txt`
- Technický souhrn: `docs/server-spec.md` (kap. 1–2)
