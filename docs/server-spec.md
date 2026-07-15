# Server-spec – kompletní technická specifikace aplikace Greensie

> Vygenerováno automatickou analýzou celého repozitáře. Popisuje **všechny funkce, vzhled i výpočtové matice** aplikace.
> Verze dokumentu odpovídá stavu kódu k 15. 7. 2026. Všechny peněžní hodnoty ve výpočtech jsou **bez DPH**.

## Obsah

1. [Přehled aplikace](#1-přehled-aplikace)
2. [Architektura a nasazení](#2-architektura-a-nasazení)
3. [Autentizace a systém oprávnění](#3-autentizace-a-systém-oprávnění)
4. [Modul Matice – Přehled projektů (Pohled 1)](#4-modul-matice--přehled-projektů-pohled-1)
5. [Modul Finance – Přehled financí (Pohled 2)](#5-modul-finance--přehled-financí-pohled-2)
6. [Modul Nabídkovač – jádro](#6-modul-nabídkovač--jádro)
7. [Výpočetní jádro: Peak shaving](#7-výpočetní-jádro-peak-shaving)
8. [Výpočetní jádro: PPA pro FVE](#8-výpočetní-jádro-ppa-pro-fve)
9. [Uživatelská nastavení](#9-uživatelská-nastavení)
10. [Administrace (uživatelé, skupiny, práva)](#10-administrace-uživatelé-skupiny-práva)
11. [Frontend – vzhled a UI funkce](#11-frontend--vzhled-a-ui-funkce)
12. [Souhrn číselníků / enumů](#12-souhrn-číselníků--enumů)
13. [Otevřené body, nedodělky a rizika](#13-otevřené-body-nedodělky-a-rizika)

---

## 1. Přehled aplikace

Greensie je interní firemní aplikace pro firmu zabývající se fotovoltaikou a energetikou. Sdružuje pod jedno přihlášení několik dříve oddělených nástrojů:

- **Přehled projektů (Pohled 1)** – maticová tabulka projektů a jejich úkolů/fází, jednosměrně synchronizovaná z projektového nástroje **Freelo**.
- **Přehled financí (Pohled 2)** – maticová tabulka faktur k projektům, s připraveným (zatím neaktivním) napojením na účetní systém **POHODA**.
- **Nabídkovač** – nástroj pro obchodní zástupce (OZ) na tvorbu zákaznických nabídek na **PPA kontrakty, prodej FVE a peak shaving**, včetně kompletních ekonomických výpočtů.
- **Admin nastavení** – správa uživatelů, skupin a oprávnění.

Celá aplikace je za přihlášením. Rozcestník zobrazuje dlaždice modulů podle práv uživatele (nepovolené citlivé dlaždice se skryjí úplně).

**Technologické jádro:** FastAPI (Python 3) backend + PostgreSQL + React 19 (Vite) frontend, servírované přes Caddy s automatickým HTTPS. Externí integrace: Freelo (čtení projektů/úkolů), POHODA (kostra), SMTP Seznam.cz (odesílání přístupových údajů). Do budoucna připraveno napojení na CRM Raynet.

### Členění backendu

```
backend/app/
├── main.py            # vstupní bod, registrace routerů, startup migrace + seed
├── database.py        # SQLAlchemy engine, session, Base
├── mailer.py          # odesílání e-mailů přes SMTP
├── auth/              # uživatelé, skupiny, práva, JWT autentizace
├── admin/             # správa uživatelů a skupin (jen admin)
├── nastaveni/         # uživatelské preference (vzhled, pohledy)
├── matice/            # Pohled 1 – projekty/sloupce/buňky + Freelo
├── finance/           # Pohled 2 – faktury + POHODA + pravidla
└── nabidkovac/        # Nabídkovač – katalog, nabídky, výpočty
    ├── peak_shaving.py # výpočetní jádro peak shavingu
    └── ppa_fve.py      # výpočetní jádro PPA/FVE
```

---

## 2. Architektura a nasazení

Aplikace se skládá ze čtyř hlavních částí:

- **React frontend** (`frontend/`) – SPA sestavená Vite do statických souborů (`frontend/dist/`), servírovaná Caddym.
- **FastAPI backend** (`backend/`, `app.main:app`) – REST API pod uvicornem na portu `8000`, v produkci navázaný jen na `127.0.0.1`.
- **PostgreSQL** – relační databáze, přístup přes SQLAlchemy 2.0 + `psycopg2`.
- **Caddy** – reverzní proxy: HTTPS (Let's Encrypt), servírování frontendu, přesměrování `/api/*` na backend.

### Tok požadavků (produkce)

```
                          https://167-235-254-188.sslip.io
                                       │
                                       ▼  (HTTPS 443, Let's Encrypt)
                          ┌────────────────────────────┐
     prohlížeč   ───────▶ │           CADDY            │
     (React SPA)          │      (reverzní proxy)      │
                          └──────────────┬─────────────┘
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             │ cesta /api/*                       │ ostatní cesty       │
             │ handle_path (odřízne /api)         │ handle              │
             ▼                                    ▼                     │
   ┌──────────────────────┐            ┌──────────────────────────┐    │
   │  BACKEND (FastAPI)    │            │  Statický frontend        │    │
   │  uvicorn 127.0.0.1:8000│           │  root: /var/www/greensie  │    │
   │  systemd: greensie-    │           │  try_files → /index.html  │    │
   │  backend.service       │           └──────────────────────────┘    │
   └───────────┬───────────┘                                            │
               │ SQLAlchemy + psycopg2 (DATABASE_URL)                    │
               ▼                                                         │
   ┌──────────────────────┐        ┌──────────────────────────┐         │
   │     PostgreSQL       │        │  SMTP (Seznam.cz)         │◀────────┘
   │  postgresql.service  │        │  smtp.seznam.cz:587       │  odesílání
   └──────────────────────┘        └──────────────────────────┘  e-mailů
```

Ve vývoji roli Caddy přebírá dev server Vite (port `5173`), který přeposílá `/api` na `http://localhost:8000` (`frontend/vite.config.js`). Frontend tak volá API stejnou cestou (`/api/...`) ve vývoji i v produkci.

### Startup logika (`backend/app/main.py`)

Při každém spuštění backendu se v tomto pořadí provede:

1. **Import a registrace modelů** – importy modelů (`# noqa: F401`) zaregistrují ORM modely do `Base.metadata` před `create_all`.
2. **`Base.metadata.create_all(bind=engine)`** – vytvoří chybějící tabulky (nepřidává sloupce do existujících).
3. **`_lehka_migrace()`** – idempotentní `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`:
   - `uzivatele`: přidá `skupina_id` (FK → `skupiny(id)`, `ON DELETE SET NULL`), `je_admin BOOLEAN NOT NULL DEFAULT false`, `musi_zmenit_heslo BOOLEAN NOT NULL DEFAULT false`.
   - **Přechod ze starého systému rolí:** pokud existuje starý sloupec `role`, nastaví `je_admin = true` všem s `role='admin'` a zruší povinnost sloupce `role` (`DROP NOT NULL`).
   - `technologie`: přidá `extra JSONB NOT NULL DEFAULT '{}'` (hodnoty vlastních sloupců katalogu).
   - `sazby_distributoru`: přidá `je_modelovy_odhad BOOLEAN NOT NULL DEFAULT false`.
4. **`_seed_sazby()`** – idempotentně naplní `sazby_distributoru` výchozími daty **ČEZ** (viz [kap. 6.5](#65-seed-data-sazby-distributorů)). Vkládá jen chybějící řádky, ruční úpravy nepřepíše.
5. **Vytvoření `FastAPI(title="Greensie")` + CORS** – povolené originy `http://localhost:5173` (vývoj) a `https://167-235-254-188.sslip.io` (produkce); `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`.
6. **Registrace routerů:** `auth`, `matice`, `finance`, `nabidkovac`, `nastaveni`, `admin`.
7. **Health check** – `GET /health` → `{"stav": "ok"}`.

### Databáze (`backend/app/database.py`)

- PostgreSQL přes SQLAlchemy 2.0 + `psycopg2`.
- `.env` se načítá z **kořene repozitáře** přes `python-dotenv`.
- `DATABASE_URL` je **povinná** (bez ní backend spadne s `KeyError`).
- `SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)`; `get_db()` je FastAPI dependency (generátor, session se v `finally` vždy zavře).
- `Base = declarative_base()` – z ní dědí všechny modely.

### Odesílání e-mailů (`backend/app/mailer.py`)

Transakční e-maily přes SMTP, výchozí poskytovatel **Seznam.cz** (`automat@greensie.cz`). Žádné údaje v kódu – vše z `.env`.

- `_cfg()` čte `SMTP_HOST` (default `smtp.seznam.cz`), `SMTP_PORT` (default `587` STARTTLS; `465` = implicitní SSL), `SMTP_USER` (default `automat@greensie.cz`), `SMTP_HESLO` (bez něj se e-maily neodesílají), `SMTP_ODESILATEL` (default = `SMTP_USER`), `APP_URL` (default produkční adresa).
- **Hetzner blokuje odchozí porty 465 i 25** → proto výchozí 587 STARTTLS.
- `email_nastaven()` – `True` jen když je vyplněné `SMTP_HESLO`.
- `posli_email(komu, predmet, telo)` – dle portu `SMTP_SSL` (465) nebo `SMTP` + `starttls()` (587), `login()`, `timeout=20 s`.
- `email_pristupu(jmeno, heslo)` – e-mail s přihlašovacím odkazem a jednorázovým heslem pro nového uživatele.

### Klíčové závislosti (`backend/requirements.txt`)

| Balíček | Verze | Účel |
|---|---|---|
| `fastapi` | 0.111.0 | webový framework |
| `uvicorn[standard]` | 0.30.1 | ASGI server |
| `sqlalchemy` | 2.0.30 | ORM |
| `psycopg2-binary` | 2.9.9 | ovladač PostgreSQL |
| `python-jose[cryptography]` | 3.3.0 | JWT tokeny |
| `passlib` + `bcrypt` | 1.7.4 / 4.0.1 | hashování hesel |
| `python-dotenv` | 1.0.1 | načítání `.env` |
| `requests` | 2.32.3 | HTTP klient (Freelo) |
| `python-multipart` | 0.0.9 | upload souborů |
| `pydantic` | 2.7.4 | validace / schémata |
| `xlrd` / `openpyxl` | 2.0.2 / 3.1.5 | čtení `.xls` / `.xlsx` (import profilu) |

### Nasazení

- **systemd** (`deploy/greensie-backend.service`): služba `greensie-backend`, startuje po `network.target` + `postgresql.service`, běží pod uživatelem `dan`, `ExecStart` = `backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`, `Restart=always`, `RestartSec=3`.
- **Caddy** (`deploy/Caddyfile`): doména `167-235-254-188.sslip.io` (sslip.io → IP 167.235.254.188), automatický Let's Encrypt certifikát, `encode zstd gzip`, `handle_path /api/*` → `reverse_proxy localhost:8000` (odřízne prefix `/api`), zbytek → statický frontend (`root /var/www/greensie`, `try_files {path} /index.html` kvůli SPA routingu).
- **`deploy/install.sh`** (jednorázově, root): zastaví dev servery, nainstaluje Caddy, nakopíruje frontend do `/var/www/greensie`, nasadí Caddyfile (`caddy validate` + restart), nasadí systemd službu, nastaví `ufw` (porty 22/80/443), zkontroluje stav. Neřeší venv/pip/build.
- **`deploy/update.sh`** (nová verze, root): `pip install -r requirements.txt`, `npm install`, `npm run build`, kopie `dist/` do `/var/www/greensie`, `systemctl restart greensie-backend`, `systemctl reload caddy`.

### Konfigurace přes `.env`

Leží v kořeni repozitáře, je v `.gitignore`. `.gitignore` dále vylučuje `venv/`, `node_modules/`, `__pycache__/`, `*.pyc`, `nabidka_soubory/`.

| Proměnná | Povinná | Výchozí | Použití |
|---|---|---|---|
| `DATABASE_URL` | **ano** | — | připojení k PostgreSQL |
| `SECRET_KEY` | **ano** | — | podpisový klíč JWT |
| `FREELO_EMAIL`, `FREELO_API_KEY` | pro Freelo | — | Basic auth Freelo API |
| `SMTP_HOST/PORT/USER/HESLO/ODESILATEL` | pro e-maily | viz mailer | SMTP |
| `APP_URL` | ne | produkční adresa | odkaz v e-mailu |
| `POHODA_URL/LOGIN/HESLO/ICO` | pro Pohodu | — | mServer XML (zatím kostra) |
| `NABIDKOVAC_UPLOAD_DIR` | ne | `<kořen>/nabidka_soubory` | úložiště nahraných souborů |

---

## 3. Autentizace a systém oprávnění

Definováno v `app/auth/`. Systém nepoužívá pevné role, ale kombinaci **skupin**, **individuálních výjimek** (`extra_prava`) a příznaku **supersprávce** (`je_admin`).

### 3.1 Datové modely

#### Tabulka `skupiny` (`Skupina`)

| Sloupec | Typ | Vlastnosti | Popis |
|---|---|---|---|
| `id` | Integer, PK | | |
| `nazev` | String | unique, not null | Název skupiny (unikátní) |
| `prava` | ARRAY(String) | not null, default `[]` | Klíče práv z katalogu `PRAVA` |

Vztah `clenove` → `User`. Smazání skupiny díky `ondelete="SET NULL"` uživatele nesmaže, jen jim vynuluje `skupina_id`.

#### Tabulka `uzivatele` (`User`)

| Sloupec | Typ | Vlastnosti | Výchozí | Popis |
|---|---|---|---|---|
| `id` | Integer, PK | | | |
| `jmeno` | String | not null | | |
| `email` | String | unique, index, not null | | přihlašovací jméno |
| `heslo_hash` | String | not null | | bcrypt hash |
| `je_admin` | Boolean | not null | `false` | supersprávce – plný přístup |
| `musi_zmenit_heslo` | Boolean | not null | `false` | nucená změna po vytvoření/resetu |
| `skupina_id` | Integer FK → `skupiny.id` (SET NULL) | index, nullable | `NULL` | dědí práva skupiny |
| `extra_prava` | ARRAY(String) | not null | `[]` | individuální výjimky nad rámec skupiny |

### 3.2 Katalog dlaždic a práv (`permissions.py`)

**Dlaždice** (`DLAZDICE`) – uvidí je vždy všichni, otevření řídí právo se stejným klíčem:

| Klíč | Název |
|---|---|
| `projekty` | Přehled projektů |
| `finance` | Přehled financí |
| `zmeny` | Přehled změn |
| `nabidkovac` | Nabídkovač |
| `admin` | Admin nastavení |

**Práva** (`PRAVA`):

| Klíč | Název |
|---|---|
| `projekty` | Otevřít Přehled projektů |
| `finance` | Otevřít Přehled financí |
| `zmeny` | Otevřít Přehled změn |
| `nabidkovac` | Nabídkovač – vytvářet/upravovat nabídky (OZ) |
| `nabidkovac_katalog` | Nabídkovač – editace katalogu a výpočtů (vedení) |
| `admin` | Otevřít Admin nastavení |
| `editace` | Editace matice (Přehled projektů) |

> Role „OZ" není samostatný koncept – je to skupina s právem `nabidkovac`. Editace katalogu technologií a výpočtů je pod samostatným právem `nabidkovac_katalog`.

### 3.3 Výpočet efektivních práv

`prava_uzivatele(user)`:
- když `user.je_admin` → **všechna práva** (`VSECHNA_PRAVA`);
- jinak sjednocení `user.extra_prava` a práv jeho skupiny (`user.skupina.prava`, pokud skupinu má).

Pomocné funkce: `muze_otevrit(user, klic)`, `muze_editovat(user)` (právo `editace`), `dlazdice_pro(user)`.

### 3.4 Autentizace (JWT)

- **Hashování:** passlib `CryptContext(schemes=["bcrypt"])`. `hash_heslo` / `over_heslo`.
- **Generování hesla:** `vygeneruj_heslo(delka=10)` z `secrets.choice` nad sadou bez záměnných znaků (`abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789` – bez 0/O, 1/l/I).
- **Token:** JWT (`python-jose`), algoritmus `HS256`, klíč z `SECRET_KEY`, platnost **8 hodin** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60*8`). Payload `{"sub": str(user.id)}`.
- **Přenos:** `OAuth2PasswordBearer(tokenUrl="/auth/login")` – Bearer token v hlavičce `Authorization`. Stateless (žádná serverová session).
- **Dependency:** `get_current_user` (dekóduje token, načte uživatele; chyba → `401`), `vyzaduj_admina` (jen kdo smí otevřít admin; jinak `403`).

### 3.5 Endpointy `auth` (prefix `/auth`)

| Metoda + cesta | Popis | Vstup | Výstup | Oprávnění |
|---|---|---|---|---|
| `POST /auth/login` | Přihlášení | `LoginRequest` (email, heslo) | `Token` (access_token, bearer) | veřejné |
| `GET /auth/me` | Info o uživateli, jeho dlaždice a práva | token | `MeOut` (uzivatel, dlazdice, muze_editovat, prava, musi_zmenit_heslo) | přihlášený |
| `PUT /auth/heslo` | Změna vlastního hesla | `ZmenaHeslaVstup` (nove_heslo) | `{"stav": "ok"}` | přihlášený |

`PUT /auth/heslo`: heslo se `strip()`, min. 6 znaků (jinak `422`), nastaví `heslo_hash` a `musi_zmenit_heslo=False`.

### 3.6 Skript `create_user.py`

CLI skript (`python -m scripts.create_user`) s argumenty `--jmeno`, `--email`, `--heslo`, `--role`, `--extra-pravo`.

> ⚠️ **Skript je nekonzistentní s aktuálním modelem a nefunguje.** Importuje `Role` a používá sloupec `role`, které už v modelu `User` neexistují (nahradily je `je_admin`/`skupina_id`/`extra_prava`). Import `Role` skončí `ImportError`. Před použitím je nutné skript aktualizovat.

---

## 4. Modul Matice – Přehled projektů (Pohled 1)

Modul `matice` je jádro Pohledu 1: tabulkový přehled stavu úkolů napříč projekty s jednosměrnou synchronizací z Freela.

**Co „matice" znamená:**
- **Řádky = projekty** (`Projekt`).
- **Sloupce = úkoly** (`Sloupec`), organizované do **fází** (`faze`) = skupin sloupců.
- **Buňky** (`Bunka`) v průsečíku projekt × sloupec nesou stav, termín, osobu, poznámku a odkaz do Freela. Klíč buňky v API: `"projektId||sloupecId"`.
- **Nastavení barev** (`NastaveniBarev`) = globální jednořádkový konfig prahů barev termínů.

### 4.1 Datové modely

#### `projekty` (`Projekt`)

| Sloupec | Typ | Null | Výchozí | Popis |
|---|---|---|---|---|
| `id` | Integer PK | ne | auto | |
| `freelo_id` | Integer, unique, index | ano | — | ID ve Freelu; `NULL` u ručních |
| `nazev` | String | ne | — | |
| `url` | String | ne | `""` | odkaz do Freela |
| `termin` | Date | ano | — | termín projektu |
| `rucni` | Boolean | ne | `false` | přidán ručně |
| `skryty` | Boolean | ne | `false` | skryt ze zobrazení |
| `poradi` | Integer | ne | `0` | pořadí řádku |

Vztah `bunky` s `cascade="all, delete-orphan"`.

#### `sloupce` (`Sloupec`)

| Sloupec | Typ | Null | Výchozí | Popis |
|---|---|---|---|---|
| `id` | Integer PK | ne | auto | |
| `label` | String, unique, index | ne | — | identifikátor `"fáze - název"` nebo jen `"název"` |
| `faze` | String | ne | `""` | název fáze (skupiny); prázdné = bez fáze |
| `nazev` | String | ne | — | název úkolu |
| `rucni` | Boolean | ne | `false` | přidán ručně |
| `poradi` | Integer | ne | `0` | pořadí |

#### `bunky` (`Bunka`)

| Sloupec | Typ | Null | Výchozí | Popis |
|---|---|---|---|---|
| `id` | Integer PK | ne | auto | |
| `projekt_id` | Integer FK → `projekty.id` (CASCADE), index | ne | — | |
| `sloupec_id` | Integer FK → `sloupce.id` (CASCADE), index | ne | — | |
| `stav` | String | ano | — | `"done"` / `"todo"` / `None` |
| `termin` | Date | ano | — | |
| `osoba` | String | ne | `""` | řešitel |
| `poznamka` | Text | ne | `""` | jen v appce, z Freela se nikdy nemaže |
| `url` | String | ne | `""` | odkaz na úkol |
| `freelo_task_id` | Integer | ano | — | |
| `upraveno_rucne` | Boolean | ne | `false` | ručně upravená buňka |

Constraint `uq_bunka_projekt_sloupec` (max. jedna buňka na průsečík).

#### `nastaveni_barev` (`NastaveniBarev`)

Jeden řádek s pevným `id=1`. Konvence: `d = dnes − termín` (dny), záporné = před termínem.

| Sloupec | Výchozí | Význam |
|---|---|---|
| `zelena_od` / `zelena_do` | `None` / `-4` | zelená (v termínu): `d ≤ -4` |
| `zluta_od` / `zluta_do` | `-3` / `0` | žlutá (blíží se): `-3 … 0` |
| `oranzova_od` / `oranzova_do` | `1` / `3` | oranžová (po termínu): `1 … 3` |
| `cervena_od` / `cervena_do` | `4` / `None` | červená (hodně po): `d ≥ 4` |

### 4.2 Endpointy (prefix `/matice`)

Oprávnění: čtení = `get_current_user`; editace = `vyzaduj_editora` (právo `editace`, jinak `403`).

| Metoda + cesta | Funkce | Popis | Oprávnění |
|---|---|---|---|
| `GET /matice` | `nacti_matici` | Celá matice: fáze, projekty, buňky, barvy | přihlášený |
| `PUT /matice/bunka` | `uloz_bunku` | Upsert buňky (nastaví `upraveno_rucne=True`) | editor |
| `POST /matice/projekt` | `pridej_projekt` | Ruční projekt (`rucni=True`) | editor |
| `PUT /matice/projekt/{id}/zobrazeni` | `nastav_zobrazeni_projektu` | Skrýt/obnovit projekt | editor |
| `POST /matice/sloupec` | `pridej_sloupec` | Ruční sloupec (`label` = `"faze - nazev"`; duplicita → `409`) | editor |
| `PUT /matice/barvy` | `uloz_barvy` | Globální prahy barev | editor |
| `POST /matice/freelo/nacist` | `nacti_z_freela` | Jednosměrná synchronizace z Freela | editor |

`GET /matice` vrací `MaticeOut`: `muze_editovat`, `faze` (seskupené dle prvního výskytu), `projekty` (řazeno `poradi, id`), `bunky` (mapa klíč → `BunkaOut`), `barvy`. Termíny se formátují přes `_date_str`, parsují přes `_parse_date` (neplatné → `422`).

### 4.3 Integrace Freelo (`freelo.py`)

Freelo je projektový/úkolový nástroj; integrace je **výhradně čtecí** (appka do Freela nikdy nezapisuje).

- Base URL `https://api.freelo.io/v1`, HTTP Basic auth (`FREELO_EMAIL`, `FREELO_API_KEY`), povinná hlavička `User-Agent: "Greensie app (daniel.lupinek@greensie.cz)"`, timeout 30 s.
- `_get(path, params)` – GET přes `requests`, `raise_for_status()`, chyba `"error"` v JSON → `RuntimeError`.
- `nacti_aktivni_projekty()` – `GET all-projects` (stránkuje), filtruje `state.state == "active"`, mapuje `freelo_id`, `nazev`, `url`.
- `nacti_ukoly(projekt_freelo_ids)` – `GET all-tasks` s opakovaným `projects_ids[]`; mapuje `faze` (← `tasklist.name`), `label` (`"faze - nazev"`), `stav` (`"done"` když `state.state == "finished"`, jinak `"todo"`), `termin`, `osoba`, `url`, `freelo_task_id`.

**Mapování Freelo → matice** (v `nacti_z_freela`):
- **Projekt** párován podle `freelo_id` (upsert – aktualizuje `nazev`, `url`).
- **Sloupec** párován podle `label`; nový label → nový sloupec.
- **Buňka** párována podle dvojice `projekt_id + sloupec_id`.

**Režimy načtení** (`FreeloVstup.rezim`):
- `"prepsat"` – existující buňky se přepíšou daty z Freela (`stav`, `termin`, `osoba`, `url`, `freelo_task_id`, `upraveno_rucne=False`), **kromě `poznamka`, která se nikdy nepřepisuje**;
- `"bez_prepsani"` – existující buňky se nemění, doplní se jen nové.

Vrací `FreeloVysledek`: počet projektů, nových sloupců, nových a přepsaných buněk.

> ⚠️ **Poznámka k `upraveno_rucne`:** příznak je udržován (True při ruční editaci, False při přepisu z Freela), ale v aktuální logice `nacti_z_freela` se v režimu `prepsat` přepisují i ručně upravené buňky – příznak se zatím nevyhodnocuje jako ochrana proti přepisu.

---

## 5. Modul Finance – Přehled financí (Pohled 2)

Modul `finance` obsluhuje pro každý projekt (z modulu `matice`) seznam faktur, jejich stavy a připravenou (zatím neaktivní) integraci na POHODU. Přísně oddělené od Pohledu 1.

### 5.1 Tabulka `faktury` (`Faktura`)

| Sloupec | Typ | Null | Výchozí | Popis |
|---|---|---|---|---|
| `id` | Integer PK | ne | | |
| `projekt_id` | Integer FK → `projekty.id` (CASCADE), index | ne | | |
| `poradi` | Integer | ne | `1` | „Faktura 1/2/3" |
| `stav` | String | ne | `"potreba_vystavit"` | viz `STAVY_FAKTURY` |
| `castka` | Numeric(12,2) | ano | | |
| `termin` | Date | ano | | |
| `poznamka` | Text | ne | `""` | |
| `variabilni_symbol` | String, index | ano | | párovací klíč na Pohodu |
| `freelo_faze` | String | ano | | fáze spouštějící fakturu (připraveno) |
| `freelo_task_id` | Integer | ano | | |
| `pohoda_potvrzeno` | Boolean | ne | `false` | |
| `pohoda_datum_vystaveni` | Date | ano | | |
| `pohoda_datum_zaplaceni` | Date | ano | | |
| `upraveno_rucne` | Boolean | ne | `false` | ruční úprava → přednost před automatikou |

Constraint `uq_faktura_projekt_poradi`. Konstanty: `STAVY_FAKTURY`, `VYCHOZI_STAV = "potreba_vystavit"`, `VYCHOZI_POCET_FAKTUR = 3`.

### 5.2 Endpointy (prefix `/finance`)

Všechny vyžadují `vyzaduj_finance` (právo `finance`, jinak `403`).

| Metoda + cesta | Funkce | Popis | Side-efekty |
|---|---|---|---|
| `GET /finance` | `nacti_finance` | Celá matice financí | **Lazy zakládání** – projektům bez faktur založí 3 prázdné |
| `PUT /finance/faktura/{id}` | `uloz_fakturu` | Editace faktury | **Vždy `upraveno_rucne=True`** |
| `POST /finance/projekt/{id}/faktura` | `pridej_fakturu` | Přidá fakturu (`poradi = max+1`) | |
| `DELETE /finance/faktura/{id}` | `smaz_fakturu` | Smaže fakturu | |
| `POST /finance/pohoda/synchronizovat` | `synchronizuj_pohodu` | Spáruje faktury s Pohodou dle VS | viz níže |

`GET /finance` vrací `FinanceOut`: `muze_editovat`, `max_faktur` (= max počet faktur napříč projekty, určuje šířku tabulky), `projekty[]`.

### 5.3 Integrace POHODA (`pohoda.py`) – KOSTRA

**Reálné napojení není implementované.** Pohoda je zamýšlena jako zdroj pravdy jen o tom, že faktura byla vystavena/zaplacena – **nikdy se do ní nezapisuje**.

- Povinné `.env`: `POHODA_URL` (mServer XML), `POHODA_LOGIN`, `POHODA_HESLO`, `POHODA_ICO`.
- `je_nakonfigurovano()` – `True` jen když jsou všechny 4 vyplněné.
- `nacti_faktury_dle_vs(vs_list)` – má vrátit stavy faktur dle VS; dnes: nenakonfigurováno → `{}`, jinak `NotImplementedError` (XML volání `listInvoiceRequest` je TODO).

**Logika `synchronizuj_pohodu`:**
1. Nenakonfigurováno → `PohodaVysledek(aktivni=False, ...)`, nic nemění.
2. Jinak vybere faktury s `variabilni_symbol IS NOT NULL`, zavolá `nacti_faktury_dle_vs`.
3. Pro každou spárovanou fakturu: `pohoda_potvrzeno=True`, doplní data; **jen když `upraveno_rucne=False`**: `zaplaceno` → `stav="zaplaceno"`, jinak `vystaveno` → `stav="vystaveno"`.

### 5.4 Fakturační pravidla (`pravidla.py`) – NO-OP

`navrhni_stavy(projekt, faktury, freelo_ukoly)` je záměrně prázdná (vrací `None`). Logika „kdy se má co fakturovat" se bude dopisovat iterativně. Klíčové pravidlo: faktura s `upraveno_rucne=True` se nikdy nepřepisuje.

### 5.5 Odvozené hodnoty a číselník

- `max_faktur = max(len(faktury))` přes projekty.
- `dalsi_poradi = nejvyssi_poradi + 1`.
- Určení stavu z Pohody: priorita `zaplaceno` > `vystaveno`.

**Stavy faktury** (`STAVY_FAKTURY`): `potreba_vystavit` (výchozí), `vystaveno`, `zaplaceno`, `nefakturuje`.

---

## 6. Modul Nabídkovač – jádro

Největší modul (router `/nabidkovac`). Slouží OZ k tvorbě nabídek na FVE, PPA a peak shaving. Tato kapitola pokrývá datové jádro, API, soubory, import profilu, seed a číselníky; vlastní výpočetní jádra jsou v [kap. 7](#7-výpočetní-jádro-peak-shaving) a [8](#8-výpočetní-jádro-ppa-pro-fve).

**Dvě úrovně oprávnění:** `vyzaduj_nabidkovac` (právo `nabidkovac` – OZ, vedení, admin) a `vyzaduj_katalog` (právo `nabidkovac_katalog` – jen vedení/admin). Čtení katalogu/sazeb je pod `nabidkovac`, editace pod `nabidkovac_katalog`.

### 6.1 Datové modely

Modul je „kostra" – zakládá tabulky a vztahy; některá pole (extrakce faktur, PDF generování) zatím zůstávají prázdná.

#### `technologie` (`Technologie`) – katalog

| Sloupec | Typ | Popis |
|---|---|---|
| `id` | Integer PK | |
| `typ` | String | z `TYPY_TECHNOLOGIE` |
| `nazev` / `model` | String | model default `""` |
| `vykon_kw` | Numeric(12,3) | panel/invertor |
| `kapacita_kwh` | Numeric(12,3) | baterie |
| `cena_kc` | Numeric(12,2) | CAPEX jednotky |
| `ucinnost` | Numeric(6,4) | 0–1, volitelné |
| `dostupnost` | Boolean, default `true` | zda se nabízí ve výpočtech |
| `extra` | JSONB, default `{}` | hodnoty vlastních sloupců |
| `raynet_id`, `synchronizovano_at` | | budoucí sync Raynet |
| `vytvoreno_at`/`aktualizovano_at` | DateTime(tz) | `now()` / `onupdate` |
| `vytvoril_user_id` | FK → uzivatele (SET NULL) | |

Baterie při validaci potřebuje `vykon_kw` i `kapacita_kwh` kladné.

#### `katalog_sloupce` (`KatalogSloupec`) – vlastní sloupce

`id`, `klic` (unique, strojový klíč do `extra`, neměnný), `nazev`, `typ` (z `TYPY_SLOUPCE`, default `text`), `poradi`, `vytvoreno_at`, `vytvoril_user_id`. Smazání jen skryje hodnoty; osiřelé klíče v `extra` nevadí.

#### `vypoctova_nastaveni` (`VypoctovaNastaveni`) – verzovaná

Žádný řádek se nepřepisuje; každá změna = nový řádek s vyšší `verze`. Aktuální = nejvyšší verze.

`id`, `verze` (index, max+1), `platne_od`, `koeficient_zisku` (Numeric(8,4)), `min_delka_kontraktu_roky`, `max_delka_kontraktu_roky`, `parametry` (JSONB), `vytvoril_user_id`, `vytvoreno_at`.

Klíče v `parametry` (čteny v `routes.py`): `max_navratnost_roky_peak_shaving`, `ppa_cena_fve_kc_kwp`, `ppa_ostatni_naklady_kc_kwp`, `ppa_oam_kc_kwp_rok`, `ppa_diskontni_sazba` (default 0.05), `ppa_merny_vynos_kwh_kwp`, `ppa_index_prebytek_rocni`, `ppa_index_ceny_rocni` (default 0.03), `ppa_index_dodavatel_rocni`, `ppa_degradace_rocni`.

#### `nabidky` (`Nabidka`) – hlavní záznam

`id`, `typ` (z `TYPY_NABIDKY`), `zakaznik_nazev`/`zakaznik_adresa` (default `""`), `zakaznik_gps_lat`/`zakaznik_gps_lng` (Numeric(9,6), pro PVGIS), `stav` (default `koncept`), `vytvoril_user_id` (SET NULL, index), `vytvoreno_at`/`aktualizovano_at`, `vypoctova_nastaveni_id` (FK, verze nastavení při výpočtu). Vztahy: `dokumenty`, `reseni` (cascade delete-orphan).

#### `nabidka_dokumenty` (`NabidkaDokument`)

`id`, `nabidka_id` (CASCADE), `typ` (z `TYPY_DOKUMENTU`), `soubor_cesta` (relativní k `UPLOAD_DIR`), `puvodni_nazev`, `velikost_bajtu`, `stav_zpracovani` (default `nahrano`), `nahral_user_id`, `nahrano_at`.

#### `spotreba_profil` (`SpotrebaProfil`) – 15min diagram

`id`, `nabidka_id` (CASCADE, index), `cas` (DateTime(tz), index), `hodnota_kwh` (spotřeba PPA/prodej), `hodnota_kw` (výkon/max peak shaving), `zdroj_dokument_id` (SET NULL). Cca 35 040 řádků/rok/zákazník. Import plní `hodnota_kw`; PPA si energii dopočítává `kWh = kW × interval_h`.

#### `extrahovana_data_faktury` (`ExtrahovanaDataFaktury`) – LLM extrakce (zatím neplněno)

`id`, `nabidka_id`, `dokument_id`, `dodavatel_text`, `cena_kwh`, `rocni_spotreba_kwh`, `rezervovany_prikon_kw`, `zkontrolovano_ok` (default `false`, brána proti počítání nad nedůvěryhodnými daty), `upravil_user_id`, `upraveno_at`, `surova_extrakce_json` (raw LLM).

#### `sazby_distributoru` (`SazbaDistributoru`)

Dvě tarifní struktury (2026 vs. 2027) → místo pevných cen `struktura_tarifu` + flexibilní `parametry` (JSONB).

`id`, `distributor` (z `DISTRIBUTORI`, index), `napetova_hladina` (z `NAPETOVE_HLADINY`), `struktura_tarifu` (z `STRUKTURY_TARIFU`), `parametry` (JSONB, NULL = struktura připravená bez cen), `platne_od`/`platne_do` (Date), `je_modelovy_odhad` (default `false`), `poznamka`, časové značky, `vytvoril_user_id`. Constraint `uq_sazba_distributor_hladina_struktura_od`.

Obsah `parametry`:
- **stara_2026**: `cena_rezervovana_kapacita_kc_kw_rok`, `cena_prekroceni_kc_kw`.
- **nova_2027**: `t1_kapacita_kc_kw_mesic`, `t1_spicka_kc_kw_mesic`, `t2_kapacita_kc_kw_mesic`, `t2_spicka_kc_kw_mesic`, `sazba_prekroceni_kc_kw_mesic`, prahy AKU `u1_ucinnost`, `u2_ucinnost`.

#### `navrhovana_reseni` (`NavrhovaneReseni`)

`id`, `nabidka_id` (CASCADE), `typ_reseni` (z `TYPY_NABIDKY`), `popis_json` (JSONB – celý výsledek výpočtu), `vybrano_zakaznikem` (NULL = nerozhodnuto), `vytvoreno_at`.

#### `generovane_nabidky_pdf` (`GenerovanaNabidkaPdf`) – zatím neimplementováno

`id`, `nabidka_id` (CASCADE), `reseni_id` (SET NULL), `soubor_cesta`, `vygeneroval_user_id`, `vygenerovano_at`.

### 6.2 Endpointy (prefix `/nabidkovac`)

**Nabídky:**

| Metoda + cesta | Popis | Oprávnění |
|---|---|---|
| `GET /nabidky` | Seznam (filtr `?typ=`), řazeno `vytvoreno_at desc` | nabidkovac |
| `POST /nabidky` | Založí nabídku (stav `koncept`) | nabidkovac |
| `GET /nabidky/{id}` | Detail vč. dokumentů a řešení | nabidkovac |
| `PUT /nabidky/{id}` | Úprava zákazníka + volitelně stav | nabidkovac |
| `DELETE /nabidky/{id}` | Smaže nabídku + soubory z disku | nabidkovac |

**Dokumenty** (jen uložení, bez zpracování):

| Metoda + cesta | Popis | Oprávnění |
|---|---|---|
| `POST /nabidky/{id}/dokumenty` | Upload (multipart: `typ`, `soubor`) | nabidkovac |
| `DELETE /dokumenty/{id}` | Smaže dokument + soubor | nabidkovac |

Validace: `typ` z `TYPY_DOKUMENTU`, přípona z `POVOLENE_PRIPONY[typ]`, prázdný → `422`, > `MAX_BAJTU` (25 MB) → `422`.

**Katalog technologií:** `GET /technologie` (čtení – nabidkovac), `POST`/`PUT /technologie/{id}`/`DELETE` (katalog). Validace `_over_technologii`, `extra` čistí `_zpracuj_extra`.

**Vlastní sloupce:** `GET /katalog-sloupce` (nabidkovac), `POST`/`PUT`/`DELETE` (katalog). Klíč generuje `_uniq_klic` (bez diakritiky, `[a-z0-9_]`, kolize → `_2`, `_3`).

**Výpočtová nastavení:** `GET /vypoctova-nastaveni` (historie, `verze desc`), `POST` (nová verze = max+1) – obojí katalog.

**Sazby distributorů:** `GET /sazby` (nabidkovac), `POST`/`PUT`/`DELETE` (katalog; IntegrityError na unique → `409`). Validace `_over_sazbu`, data `_parse_datum`.

**Profil spotřeby:**

| Metoda + cesta | Popis |
|---|---|
| `GET /nabidky/{id}/peak-shaving/profil-souhrn` | `{pocet, od, do, max_kw}` |
| `POST /dokumenty/{id}/zpracuj-profil` | Naparsuje soubor do `spotreba_profil` (idempotentní; stav → `extrahovano`/`chyba_extrakce`) |
| `GET /nabidky/{id}/ppa/profil-souhrn` | `{pocet, od, do, interval_h, rocni_spotreba_mwh}` |

**Výpočty:**

| Metoda + cesta | Popis | Side-efekty |
|---|---|---|
| `POST /nabidky/{id}/peak-shaving/vypocet` | Výpočet PS → `navrhovana_reseni` | `typ_reseni=peak_shaving`, `vypoctova_nastaveni_id`=aktuální, stav → `spocitano` |
| `POST /nabidky/{id}/ppa/vypocet` | PPA výpočet → `navrhovana_reseni` | `typ_reseni=ppa`, stav → `spocitano` |

### 6.3 Import profilu odběru (`profil_import.py`)

Načítá 15min profil odběru z nahraného souboru (typicky XLS export „PND" z portálu distributora).

**Formáty** (dle přípony v `nacti_profil`): `.xls` (xlrd, list 0), `.xlsx` (openpyxl, `read_only`, `data_only`), `.csv` (`utf-8-sig`, autodetekce oddělovače přes `csv.Sniffer`); jiná → `ValueError`.

**Parsování:**
1. `_najdi_sloupce` hledá hlavičku dynamicky – preferuje sloupec s `+a` i `kw` (činný odběr), jinak první s `kw`.
2. Sloupec s datem: nejbližší nalevo s `datum`/`čas`/`cas`.
3. `_parse_datum` zkouší formáty `%d.%m.%Y %H:%M:%S`, `%d.%m.%Y %H:%M`, `%Y-%m-%d %H:%M:%S`, ISO...
4. `_to_float` toleruje mezery a desetinnou čárku.
5. Nečitelné řádky se přeskočí; prázdný výsledek → `ValueError`.

Bere se **činný výkon `+A [kW]`**, ne jalový. **Žádná agregace** – vrací `(čas, kW)` v 15min rozlišení, ukládá 1:1 do `spotreba_profil.hodnota_kw`. Délka intervalu se v routách odvozuje z prvních dvou značek (`_interval_h_z_profilu`, fallback 0,25 h).

### 6.4 Práce se soubory (`soubory.py`)

- `UPLOAD_DIR` z `NABIDKOVAC_UPLOAD_DIR`, jinak `<kořen>/nabidka_soubory` (v `.gitignore`).
- `uloz_soubor` – podsložka per nabídka, jméno `<uuid4.hex>_<bezpečný_název>`, do DB relativní cesta.
- `_bezpecny_nazev` – `basename`, jen `[A-Za-z0-9._-]`, max 120 znaků (brání path traversal).
- `smaz_soubor` – best-effort `unlink(missing_ok=True)`.
- `MAX_BAJTU = 25 MB`. `POVOLENE_PRIPONY`: `faktura_pdf` → `.pdf`; `spotreba_csv` → `.csv/.xlsx/.xls`; `jiny` → `.pdf/.csv/.xlsx/.xls/.png/.jpg/.jpeg`.

### 6.5 Seed data (sazby distributorů)

`seed_sazby(db)` idempotentně naplní `sazby_distributoru`. Naostro se plní **jen ČEZ Distribuce** (EG.D a PRE se doplní přes admin, až budou čísla ověřená).

Konstanty: `_PLATNE_OD_2026 = 2026-01-01`, pokuty ERÚ `_POKUTA_VN = 1108.0`, `_POKUTA_VVN = 521.0`, `_REZERVACE_CEZ_VN_ROK = 237,31 × 12 = 2847,72`.

| Distributor | Hladina | Struktura | Klíčové parametry | Model. odhad |
|---|---|---|---|---|
| cez | vn | stara_2026 | rezervace=2847.72, prekroceni=1108.0 | ne |
| cez | vvn | stara_2026 | rezervace=None (nedohledáno), prekroceni=521.0 | ne |
| cez | vn | nova_2027 | t1_kap=190.133, t1_špič=19.013, t2_kap=22.743, t2_špič=227.429, prekr=761.0, u1=0.60, u2=0.75 | ano |
| cez | vvn | nova_2027 | t1_kap=96.862, t1_špič=9.686, t2_kap=11.586, t2_špič=115.862, prekr=387.0, u1=0.60, u2=0.70 | ano |

Rezervovaná kapacita se ukládá jako roční sazba (× 12); pokuta jako Kč/kW za měsíc překročení. Penalizace 2027 ≈ 4× T1 kapacita. `_BACKFILL_KLICE = (u1_ucinnost, u2_ucinnost)` – u existujících řádků jen doplní chybějící prahy AKU, ceny nikdy nepřepíše.

### 6.6 Odvozené výpočty v jádru modulu

- `_interval_h_z_profilu` = `(casy[1] − casy[0]).total_seconds() / 3600` (fallback 0,25 h).
- `_profil_spotreby_kwh`: `spotreba_kwh = hodnota_kw × interval_h`.
- `rocni_spotreba_mwh = sum(spotreba_kwh) / 1000`.
- Výběr platné sazby: `_plati_pro_rok` (dle `platne_od.year` / `platne_do.year`), `_najdi_sazbu` (řazení `platne_od desc`, první platná).
- Priorita PPA parametrů: **vstup > nastavení > kódový default**. Default indexu dodavatele = index PPA.
- Pojistka měrného výnosu: mimo `100–2000` kWh/kWp → default 1000 + upozornění.
- Přechody stavů: upload → `data_nahrana`; výpočet → `spocitano`.

---

## 7. Výpočetní jádro: Peak shaving

Soubor `backend/app/nabidkovac/peak_shaving.py` (622 řádků). Deterministický, bez DB/FastAPI – pracuje jen se seznamy 15min hodnot a čísly z nastavení. Peníze bez DPH.

### 7.1 Co peak shaving řeší

Odběratel na VN/VVN platí distributorovi **rezervovanou kapacitu** (sjednaný příkon, Kč/kW) a **pokutu za překročení** (dle nejvyššího 15min výkonu v měsíci). Bateriové úložiště ořezává špičku: když odběr překročí strop `T`, baterie dodá rozdíl, takže do sítě jde jen `T`. Tím lze snížit sjednanou kapacitu a eliminovat pokuty.

Dva tarifní modely: **2026** (`stara_2026`, jednosložkový) a **2027** (`nova_2027`, dvousložkový T1/T2, zatím modelový odhad ERÚ).

### 7.2 Vstupy a výstupy

**Vstupy:** `profil_kw` (15min činný odběr, kW), `mesice` (1–12 pro každou hodnotu), `rezervovana_kapacita_kw`, sazby z `sazby_distributoru`, katalog baterií (`vykon_kw`, `kapacita_kwh`, `cena_kc`), `max_navratnost_roky` (default 5), `max_pocet_kusu` (default 5), `interval_h` (default 0,25).

**Výstupy** (`VysledekPeakShaving`): `varianty` (nejlepší za produkt), `doporucena` (nejrychlejší návratnost), `upozorneni`. Každá `Varianta` nese novou rezervovanou kapacitu, roční úsporu 2026, ekonomiku 2026 i 2027 a **tři návratnosti** (2026, 2027 optimistická se slevou AKU, 2027 konzervativní bez AKU).

### 7.3 Konstanty

| Konstanta | Hodnota | Význam |
|---|---|---|
| `VYCHOZI_INTERVAL_H` | `0.25` | 15 min |
| `VYCHOZI_MAX_NAVRATNOST_ROKY` | `5.0` | práh doporučení |
| `VYCHOZI_MAX_POCET_KUSU` | `5` | max kusů baterie |
| `_BINARNI_TOLERANCE_KW` | `0.01` | tolerance hledání stropu |
| `u1_ucinnost` / `u2_ucinnost` | `0.60` / `0.75` | prahy Koeficientu AKU (fallback) |

Fyzikální zjednodušení (v1): kapacita 1:1 bez ztrát, žádný limit DoD, počáteční SoC = plná baterie.

### 7.4 Simulace baterie

**`_max_udrzitelny_vyboj`** – max výkon, který baterie dodá celý interval:
```
z_energie = soc_kwh / interval_h            (kW)
max_vyboj = min(vykon_kw, z_energie)        (kW)
```

**`strop_je_udrzitelny`** – projede profil, vrátí zda baterie strop `T` udrží (počáteční `soc = kapacita_kwh`):
```
nad stropem (odber > T):
    potreba = odber − T
    dodavka = min(potreba, _max_udrzitelny_vyboj(...))
    když dodavka + 1e−9 < potreba: → False
    soc −= dodavka × interval_h
pod stropem (odber ≤ T):
    rezerva = min(T − odber, vykon_kw)
    soc = min(kapacita_kwh, soc + rezerva × interval_h)
```
Dobíjí se jen z rezervy pod stropem. Bez baterie: udržitelné jen když profil strop nikdy nepřekročí.

**`min_udrzitelny_strop`** – binární hledání nejnižšího udržitelného `T` (předpoklad monotónnosti):
```
horni = max(profil_kw) ;  dolni = 0
while horni − dolni > 0,01:
    stred = (horni + dolni) / 2
    když strop_je_udrzitelny(stred): horni = stred
    jinak:                            dolni = stred
return horni
```
Výsledek = **navrhovaná nová rezervovaná kapacita**.

**`energie_pri_stropu`** – stejná simulace, ale sčítá `(nabito_kwh, vybito_kwh)` pro Koeficient AKU a grafy.

**`_mesicni_maxima`** – `{měsíc: nejvyšší 15min odběr}`.

### 7.5 Ekonomika 2026 (`stara_2026`)

```
naklad_rezervace  = rezervovana_kapacita_kw × cena_rezervace_kc_kw_rok
naklad_prekroceni = Σ_měsíce max(0, mesicni_max − rezervovana_kapacita_kw) × cena_prekroceni_kc_kw
soucasny_naklad   = naklad_rezervace + naklad_prekroceni

novy_naklad = nova_rezervovana_kapacita × cena_rezervace_kc_kw_rok    # po baterii žádné překročení
rocni_uspora = soucasny_naklad − novy_naklad
```

### 7.6 Ekonomika 2027 (`nova_2027`) – dvousložkový tarif

Klíče (Kč/kW/měsíc): `t1_kapacita`, `t1_spicka`, `t2_kapacita`, `t2_spicka`. Chybí-li → `{"status": "ceka_na_sazby_eru"}`.

**Koeficient AKU** (`_koeficient_aku`) – ⚠️ nepotvrzený optimistický předpoklad; sleva na „špičku" dle účinnosti (`vybito/nabito`):
```
koef = 0                       když ucinnost ≤ U1
     = (ucinnost−U1)/(U2−U1)   když U1 < ucinnost < U2
     = 1                       když ucinnost ≥ U2
```
Prahy U1=0,60, U2=0,75 (VN) / 0,70 (VVN). V bezztrátovém v1 modelu vyjde účinnost ≈ 1 → plná sleva.

**Měsíční náklad** (`_mesicni_naklad_2027`) – sleva jen na část krytou výkonem baterie:
```
M_kryto  = min(mesicni_max, nabijeci_vykon)
M_zbytek = mesicni_max − M_kryto
spicka_Tx = M_zbytek × tx_spicka + M_kryto × tx_spicka × (1 − koef)
cx = rp × tx_kapacita + spicka_Tx
zaklad = min(c1, c2)          # distributor ex post vybere levnější tarif
penalizace = max(0, mesicni_max − rp) × sazba_prekroceni     (default 0)
mesicni_naklad = zaklad + penalizace
```

**Roční náklad** (`_rocni_naklad_2027`) = součet přes měsíce + počty měsíců T1/T2.

**Srážení maxim** (`mesicni_maxima_po_baterii`) – v 2027 se platí za měsíční maximum M, takže baterie sráží špičku každého měsíce (samostatný `min_udrzitelny_strop` pro data měsíce). Rezervovaná kapacita zůstává jedna roční hodnota.

**Kompletní ekonomika** (`ekonomika_2027`) – vrací dva scénáře: optimistický `rocni_uspora` (s AKU) a konzervativní `rocni_uspora_bez_aku`, plus `prumerna_ucinnost` (ořez na max 1,0), `prumerny_koeficient_aku`, `pocet_mesicu_t1/t2`, `predpoklad_aku_neoverovany: true`.

### 7.7 Graf a výběr varianty

**`graf_maxima`** – měsíčně tři řady: `bez_baterie_kw`, `s_baterii_2026_kw` = `min(raw, roční strop)`, `s_baterii_2027_kw` = per-měsíční sražené maximum.

**Návratnost** (`_navratnost`): `cena_celkem / uspora` (roky); úspora ≤ 0 → `None`.

**`spocti_variantu`** – pro produkt × počet kusů škáluje `vykon`, `kapacita`, `cena`, spočítá `min_udrzitelny_strop`, ekonomiku 2026 i 2027 a tři návratnosti (2026 řídí výběr). `doporuceno` = návratnost ≤ práh.

**`vyber_reseni`** – pro každý produkt zkouší 1..N kusů, řadí podle nejkratší návratnosti (`_radici_klic`: kladná úspora `(0, navratnost)`, jinak `(1, ∞)`). Optimalizace: jakmile přidání kusu návratnost nezlepší, hledání pro produkt se ukončí (`break`).

---

## 8. Výpočetní jádro: PPA pro FVE

Soubor `backend/app/nabidkovac/ppa_fve.py` (631 řádků). Investor (Greensie) postaví a vlastní FVE, klient neinvestuje a odebírá elektřinu za sjednanou (indexovanou) PPA cenu. Modul počítá **klientovi** úsporu a **investorovi** návratnost (payback, IRR, NPV, cashflow). Výrobu si appka sama simuluje; velikost FVE navrhuje sama podle nejlepší ekonomiky.

### 8.1 Vstupy a výstupy

**Vstupy** (`VstupPPA`): `kwp`, `lat`, `sklon_st`, `azimut_st`, `cena_ppa_kc_mwh` + `index_ppa_rocni`, `cena_dodavatel_kc_mwh` + `index_dodavatel_rocni`, `delka_kontraktu_roky`, `degradace_rocni`, `capex_kc` (+ `capex_rozpad`), prodej přebytku, `rezervovany_vykon_dodavky_kw`, `oam_kc_kwp_rok`, `diskontni_sazba`, `merny_vynos_kwh_kwp`, `interval_h`; dále `casy` a `spotreba_kwh` (15min profil).

**Výstupy** (`spocti_ppa` → `popis_json`): navržená velikost, měrný výnos, korekce orientace, CAPEX + rozpad, roční/kumulativní úspora klienta, výnos investora, payback/IRR/NPV, `roky[]` (cashflow po letech), měsíční graf, headline metriky pokrytí.

### 8.2 Konstanty a pojistky

| Konstanta | Hodnota | Význam |
|---|---|---|
| `VYCHOZI_INTERVAL_H` | `0.25` | 15 min |
| `VYCHOZI_MERNY_VYNOS_KWH_KWP` | `1000.0` | ČR, jih, ~35° (⚠️ ilustrativní) |
| `VYCHOZI_DEGRADACE_ROCNI` | `0.005` | 0,5 %/rok |
| `VYCHOZI_CENA_FVE_KC_KWP` | `25000.0` | zjednodušený CAPEX |
| `VYCHOZI_LAT` | `49.8` | střed ČR |
| `VYCHOZI_CIL_MIRA_SAMOSPOTREBY` | `0.80` | pro `navrhni_kwp` |
| `_MAX_POMER_VYROBA_SPOTREBA` | `3.0` | max velikost = 3× roční spotřeba |

Pojistka měrného výnosu (v routes): mimo `100–2000` kWh/kWp → default 1000 + upozornění.

**Měsíční rozdělení výnosu** `_MESICNI_VYNOS` (kWh/kWp/měsíc při ročním 1000, součet = 1000):

| led | úno | bře | dub | kvě | čvn | čvc | srp | zář | říj | lis | pro |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 26 | 42 | 83 | 120 | 135 | 132 | 138 | 120 | 90 | 58 | 30 | 26 |

**Korekce orientace** `_ORIENT_TAB` (řádky = sklon, sloupce = |azimut|; jih + 35° = 1,00):

| sklon \ azimut | 0° | 45° | 90° | 180° |
|---|---|---|---|---|
| 0° | 0,88 | 0,88 | 0,88 | 0,88 |
| 15° | 0,96 | 0,94 | 0,88 | 0,80 |
| 35° | **1,00** | 0,96 | 0,84 | 0,66 |
| 60° | 0,91 | 0,86 | 0,72 | 0,50 |

`korekce_orientace` – bilineární interpolace (azimut symetrický: `a = abs(azimut) mod 360`, `a>180 → 360−a`).

### 8.3 Simulace výroby

**Sluneční okno** (`_slunecni_okno`) pro den `n`, šířku `φ`:
```
δ = 23,45° × sin(360° × (284 + n) / 365)      # deklinace
x = −tan(φ) × tan(δ) → ořez [−1, 1]            # polární den/noc
ω_s = arccos(x)                                 # hodinový úhel
t_vychod = 12 − ω_s/15 ;  t_zapad = 12 + ω_s/15
```

**Tvar produkce** (`_tvar_produkce`) – clear-sky zvonovina:
```
g(t) = sin(π × (t − t_vychod) / (t_zapad − t_vychod))   pro t v (t_vychod, t_zapad)
     = 0                                                 jinak
```

**Výroba** (`simuluj_vyrobu`) – rok 1:
```
E_rok = kwp × merny_vynos × korekce_orientace
frakce_měsíc = _MESICNI_VYNOS[měsíc] / 1000
E_den = E_rok × frakce_měsíc / počet_dní_v_měsíci
V_i = E_den × g(t_i) / Σ_den g(t)               # kWh/interval
```
Výroba je lineární v kWp → pro sweep se simuluje jednou pro 1 kWp a škáluje.

**Degradace** (v `spocti_ppa` pro rok `t`): `f = (1 − degradace_rocni)^(t−1)`, `vyroba_t = vyroba1 × f`. Spárování se počítá znovu každý rok (kvůli nelineárnímu `min()`).

### 8.4 Spárování výroby a spotřeby (`sparuj`)

Pořadí toku: samospotřeba → přetok omezený rezervovaným výkonem → ořez:
```
strop_e = rezervovany_vykon_dodavky_kw × interval_h    (None/0 = neomezeno)
samospotreba_i = min(V_i, S_i)
prebytek_i     = V_i − samospotreba_i
export_i       = min(prebytek_i, strop_e)
orez_i         = prebytek_i − strop_e
dokup_i        = S_i − samospotreba_i
```
Vrací `Bilance` (roční součty). Ořez neovlivňuje samospotřebu.

### 8.5 Ekonomika po letech (`spocti_ppa`)

Eskalace cen (rok 1 = základ):
```
cena_ppa_t = cena_ppa_kc_mwh       × (1 + index_ppa_rocni)^(t−1)
cena_dod_t = cena_dodavatel_kc_mwh × (1 + index_dodavatel_rocni)^(t−1)
cena_pre_t = prebytek_cena_kc_mwh  × (1 + index_prebytek_rocni)^(t−1)
```

**Klient (úspora):**
```
uspora_t = (samospotreba_t / 1000) × (cena_dod_t − cena_ppa_t)     (Kč)
```

**Investor (cashflow):**
```
vynos_ppa = (samospotreba_t / 1000) × cena_ppa_t
vynos_pre = (export_t / 1000) × cena_pre_t          (jen když prebytek_uctovat)
oam       = oam_kc_kwp_rok × kwp
cf_t      = vynos_ppa + vynos_pre − oam
```
Kumulativní CF startuje z `−capex_kc`.

### 8.6 Ekonomické ukazatele

**Prostá návratnost** (`_payback_roky`) – nejmenší rok s kumulativním CF ≥ 0, lineární interpolace uvnitř roku; nevrátí-li se → `None`.

**NPV** (`_npv`):
```
NPV = −capex + Σ_{t=1..N} cf_t / (1 + r)^t          (r = diskontní sazba)
```

**IRR** (`_irr`) – bisekce na `[−0,9; 1,0]`, hledá `r` s `NPV(r)=0`; když se znaménko na krajích nemění → `None`; jinak 100 iterací, tolerance `1e−6`.

### 8.7 CAPEX

**Zjednodušený** (`cena_kwp`, default): `CAPEX = kwp × cena_fve_kc_kwp` (default 25 000).

**Komponentový** (`capex_komponenty`) – nejlevnější panel a invertor z katalogu (dle Kč/kW):
```
pocet_panelu    = ceil(kwp / panel.vykon_kw)
pocet_invertoru = ceil(kwp / invertor.vykon_kw)
CAPEX = pocet_panelu × panel.cena + pocet_invertoru × invertor.cena + kwp × ostatni_kc_kwp
```
Chybí-li panel/invertor, složka = 0 + `{"chybi": True}` v rozpadu.

### 8.8 Headline metriky

```
pokryti_spotreby_fve  = samospotreba_rok1 / rocni_spotreba     (headline)
mira_samospotreby     = samospotreba_rok1 / vyroba_rok1
mira_sobestacnosti    = samospotreba_rok1 / rocni_spotreba
pomer_vyroba_spotreba = vyroba_rok1 / rocni_spotreba
mira_orezu            = orez_rok1 / vyroba_rok1
```

### 8.9 Návrh velikosti FVE

**Ekonomický výběr** (výchozí):
- `kandidatni_velikosti` – řada kWp: `cap = min(3 × roční_spotřeba / prod_per_kwp, max_kwp)`, `krok = round(cap / pocet)` (pocet default 40), unikátní celá kWp.
- `vyber_velikost` – pro každou velikost dopočítá CAPEX, spustí `spocti_ppa` (škáluje z 1 kWp), seřadí podle `_skore_ekonomiky = (−npv_kc, navratnost nebo ∞)` → primárně nejvyšší NPV, pak nejkratší návratnost. Respektuje prodej přebytku.

**Alternativní** (`navrhni_kwp`, není výchozí) – největší kWp, u něhož se aspoň `cil_mira_samospotreby` (0,80) výroby přímo spotřebuje; binární hledání (40 iterací).

**Graf** (`_graf_mesicni`) – měsíční agregáty rok 1 (spotřeba, výroba, samospotřeba, export, ořez, dokup), jen měsíce s nenulovou spotřebou/výrobou.

---

## 9. Uživatelská nastavení

Modul `nastaveni` (prefix `/nastaveni`) ukládá uživatelské preference (klíč → JSON hodnota), aby se přenášely mezi zařízeními (vzhled: motiv, velikost textu; konfigurace Pohledu 1: skryté fáze/úkoly, pořadí).

### Tabulka `uzivatelska_nastaveni` (`UzivatelskeNastaveni`)

`id`, `uzivatel_id` (FK → `uzivatele`, CASCADE, index), `klic` (String), `hodnota` (JSON). Constraint `uq_nastaveni_uzivatel_klic`.

### Endpointy

| Metoda + cesta | Popis | Výstup |
|---|---|---|
| `GET /nastaveni` | Všechna nastavení uživatele | `{klíč: hodnota}` |
| `PUT /nastaveni/{klic}` | Upsert jednoho nastavení | `{klic: hodnota}` |

Obojí vyžaduje přihlášení.

---

## 10. Administrace (uživatelé, skupiny, práva)

Modul `admin` (prefix `/admin`, celý router `dependencies=[Depends(vyzaduj_admina)]` – vyžaduje právo `admin` nebo `je_admin`).

Pomocné funkce: `_over_prava` (klíče z `VSECHNA_PRAVA`, jinak `422`), `_over_skupina`, `_pocet_adminu`, `_posli_pristup` (best-effort e-mail; akce se kvůli e-mailu neruší).

### Endpointy

| Metoda + cesta | Popis | Klíčové pojistky |
|---|---|---|
| `GET /admin/ciselniky` | Katalog práv pro UI | |
| `GET /admin/uzivatele` | Seznam uživatelů | |
| `POST /admin/uzivatele` | Nový uživatel + vygenerované heslo | duplicitní e-mail → `409`; `musi_zmenit_heslo=True`; e-mail s údaji |
| `PUT /admin/uzivatele/{id}` | Úprava uživatele | kolize e-mailu → `409`; nelze odebrat posledního admina → `409` |
| `POST /admin/uzivatele/{id}/reset-hesla` | Reset hesla | volitelné `nove_heslo` (min. 6) nebo náhodné; `musi_zmenit_heslo=True` |
| `DELETE /admin/uzivatele/{id}` | Smazání | nelze sám sebe → `409`; nelze posledního admina → `409` |
| `GET /admin/skupiny` | Seznam skupin (+ `pocet_clenu`) | |
| `POST /admin/skupiny` | Nová skupina | duplicitní název → `409` |
| `PUT /admin/skupiny/{id}` | Úprava skupiny | kolize názvu → `409` |
| `DELETE /admin/skupiny/{id}` | Smazání skupiny | uživatelům se vynuluje `skupina_id` (SET NULL) |

`HesloVysledek` vrací i plaintext heslo k zobrazení adminovi (+ `email_odeslan`, `email_poznamka`).

---

## 11. Frontend – vzhled a UI funkce

### 11.1 Technologický stack

Záměrně minimalistický – jen tři runtime knihovny:
- **React 19** (`react`, `react-dom`),
- **React Router 7** (`react-router-dom`),
- **Vite 8** (build + dev server), **oxlint** (linter).

**Co v projektu není:** žádná knihovna na grafy, UI framework, stav ani formuláře. Grafy jsou ručně kreslené SVG (komentář: „deploy nedělá `npm install`, tak držíme nulové závislosti"). Styling = čisté CSS + inline styly. API přes nativní `fetch`.

Start v `main.jsx`: načte styly, inicializuje motiv (`initTheme()`) a velikost textu (`initVelikost()`) před vykreslením (aby neproblikla špatná varianta).

### 11.2 Routing (`App.jsx`, `BrowserRouter`)

Kromě `/` (Login) jsou všechny cesty chráněné `VyzadujePrihlaseni` (ověří token, jinak přesměruje na login). Uvnitř stránek další kontrola práv (`me.prava`).

| Cesta | Stránka | Účel |
|---|---|---|
| `/` | `Login` | Přihlášení (jediná veřejná) |
| `/zmena-hesla` | `ZmenaHesla` | Vynucená změna jednorázového hesla |
| `/rozcestnik` | `Rozcestnik` | Rozcestník dlaždic |
| `/projekty` | `PrehledProjektu` | Matice projektů (Pohled 1) |
| `/finance` | `PrehledFinanci` | Matice faktur (Pohled 2) |
| `/nabidkovac` | `Nabidkovac` | Rozcestník tří linií |
| `/nabidkovac/katalog` | `NabidkovacKatalog` | Katalog + výpočtová nastavení |
| `/nabidkovac/nabidka/:id` | `NabidkaDetail` | Detail nabídky |
| `/nabidkovac/:typ` | `NabidkovacSekce` | Seznam nabídek linie |
| `/admin` | `AdminNastaveni` | Správa uživatelů/skupin/práv |

### 11.3 Stránky

- **Login / ZmenaHesla** – vystředěná karta `fm-card`, zelené tečkové logo. Login stahuje uložený vzhled z DB (`synchronizujVzhled`) a směruje na změnu hesla nebo rozcestník.
- **Rozcestnik** – responzivní mřížka dlaždic (`Tile`). Zamčené dlaždice mají 🔒 + video; dlaždice bez práva u citlivých modulů se zcela skryjí (`SKRYT_BEZ_PRAVA`).
- **PrehledProjektu (Pohled 1)** – matice `fm-matrix` (dvouúrovňová hlavička s fázemi). Funkce: barevné termíny (konfigurovatelné prahy v legendě), editace buněk (`BunkaDialog`), načtení z Freela (`FreeloDialog`), přidání projektu/sloupce (`PridatDialog`), sbalení/rozbalení fází (souhrn termín + „X/Y úkolů" + proužek), skrývání/řazení (drag&drop, `ZobrazeniDropdown`, ukládání do DB), proklik na finance (💰), progres bary, sticky levé sloupce.
- **PrehledFinanci (Pohled 2)** – stejný vzhled, sloupce = faktury. Stav **vždy barva + ikona + text** (uživatel je barvoslepý), + částka, VS, termín, „✓ Pohoda". `FakturaDialog`, „Synchronizovat s Pohodou", „+ faktura". Proklik z Pohledu 1 (`?projekt=ID`) naskroluje + problikne (`fm-fa-flash`).
- **Nabidkovac** – tři dlaždice linií (PPA / Prodej / Peak shaving, konstanta `PODSEKCE`) + „⚙ Katalog a výpočty".
- **NabidkovacSekce** – tabulka `nb-table` (Zákazník, Stav, Vytvořil, Datum), oranžové upozornění `nb-warn`, „+ Nová nabídka".
- **NabidkaDetail** – karty Zákazník (+ GPS), Podklady (`DokumentUpload`), Navržená řešení (`PeakShavingPanel` / `PpaPanel`).
- **NabidkovacKatalog** – Katalog technologií (`TechEditor`, `SloupecEditor`), Výpočtová nastavení (verzovaný formulář), Sazby distributorů (`SazbaEditor`, podpora „čeká se na ERÚ" + modelový odhad).
- **AdminNastaveni** – Uživatelé (`HesloVysledekModal` s „Kopírovat údaje"), Skupiny (`SkupinaEditor`), výběr práv (`PravaVyber`).

### 11.4 Klíčové komponenty

- **`Layout`** – hlavička: logo, `VelikostTextu`, `ThemeToggle`, jméno, „Odhlásit".
- **`Tile`** – dlaždice rozcestníku (hover zelený rám, zamčená 🔒).
- **`GrafOdberu`** – SVG: měsíční maxima odběru bez/s baterií + čárkované linie rezervované kapacity.
- **`GrafVyrobaSpotreba`** – stohovaný sloupcový SVG: výroba vs. spotřeba (samospotřeba/dokup/přetok/ořez), MWh.
- **`PpaPanel`** / **`PeakShavingPanel`** – kalkulátory (profil, parametry, výpočet, výsledky, grafy, tabulky).
- **`DokumentUpload`** – drag&drop zóna `nb-drop`.
- **Dialogy** (`BunkaDialog`, `FakturaDialog`, `FreeloDialog`, `PridatDialog`) – jednotné: tmavé poloprůhledné pozadí (`rgba(31,41,51,.45)`, `fixed inset:0`), bílá karta, zavření mimo, Zrušit/Uložit.

### 11.5 Design systém a vzhled

**Paleta** (CSS proměnné `--fm-*` v `global.css`): značková **Greensie zelená** `--fm-brand: #2f9e44`, pozadí `--fm-bg: #f4f6f5`, karty bílé, text `--fm-text: #1f2933`. Dojem: čistý, světlý, firemní, přehledný – bílé karty s jemným stínem, zaoblené rohy 8–16 px.

**Motiv** (`theme.js` + `ThemeToggle`): `data-theme="dark"` na kořeni jen přepíše `--fm-*` (tmavá `#12161a`/`#1b2126`, zelená `#40c057`). Ukládá se do `localStorage` (rychlý start) i DB (přenos zařízení).

**Velikost textu** (`velikost.js` + `VelikostTextu`): Malé/Střední/Velké přes CSS `zoom` na kořeni (základ 14 px; střední ×16/14; velké ×18/14). `localStorage` + DB.

**„Pohledy"** (`pohled1.css`, `pohled2.css`): „Pohled 1" = Přehled projektů, „Pohled 2" = Přehled financí. `pohled2.css` `@import`uje `pohled1.css`. `fm-matrix` se sticky hlavičkami i levými sloupci, dvouúrovňová hlavička (`fm-grp`), barevné termínové úrovně (`fm-lvl-green/yellow/orange/red`), progres proužky, legenda nahoře. **Zásada: stav se nikdy nespoléhá jen na barvu** – vždy + ikona + text (barvoslepost).

**Nabídkovač** (`nabidkovac.css`): namespace `nb-*` nad `--fm-*`, obsah `max-width: 1100px` vystředěný. Dlaždice `nb-tile`, tabulky `nb-table`, štítky `nb-badge`, formuláře `nb-pole`/`nb-form-grid`, oranžové `nb-warn` (nehotové funkce).

**Typografie:** systémové bezpatkové písmo, základ 14 px, řádkování 1,4. Responzivní grid/flex, tabulky se rolují v `fm-scroll`/`nb-scroll`.

### 11.6 Komunikace s API (`api.js`)

- Base URL relativní `"/api"` (Caddy směruje na backend).
- JWT v `localStorage` pod `greensie_token`; `getToken()` / `logout()`.
- Centrální `zavolej(cesta, moznosti)` – přidá `Content-Type: application/json` + `Authorization: Bearer <token>`, z chyby vytáhne `detail` a vyhodí `Error` (komponenty dle textu odhlásí / vrátí na rozcestník).
- Upload (`nabidkaNahrajDokument`) posílá `FormData` (bez `Content-Type`).
- Exportuje funkce po doménách: auth (`login`, `nactiMe`, `zmenHeslo`), matice (`nactiMatici`, `ulozBunku`, `nacistZFreela`, ...), finance, nabídkovač, nastavení (`nactiNastaveni`, `ulozNastaveni`), admin.

---

## 12. Souhrn číselníků / enumů

Definované jako modulové n-tice, zrcadlené jako Pydantic `Literal`.

| Enum | Modul | Hodnoty | Výchozí |
|---|---|---|---|
| stav buňky | matice | `done`, `todo`, `None` | — |
| režim Freelo | matice | `prepsat`, `bez_prepsani` | — |
| barevná pásma | matice | zelená / žlutá / oranžová / červená (prahy ve dnech) | viz 4.1 |
| stav faktury | finance | `potreba_vystavit`, `vystaveno`, `zaplaceno`, `nefakturuje` | `potreba_vystavit` |
| `TYPY_TECHNOLOGIE` | nabidkovac | `fve_panel`, `invertor`, `baterie`, `jina` | — |
| `TYPY_NABIDKY` | nabidkovac | `ppa`, `prodej`, `peak_shaving` | — |
| `STAVY_NABIDKY` | nabidkovac | `koncept`, `data_nahrana`, `zkontrolovano_oz`, `spocitano`, `hotovo` | `koncept` |
| `TYPY_DOKUMENTU` | nabidkovac | `faktura_pdf`, `spotreba_csv`, `jiny` | — |
| `STAVY_ZPRACOVANI` | nabidkovac | `nahrano`, `extrahovano`, `chyba_extrakce`, `rucne_doplneno` | `nahrano` |
| `DISTRIBUTORI` | nabidkovac | `cez`, `egd`, `pre` (naostro jen `cez`) | — |
| `NAPETOVE_HLADINY` | nabidkovac | `vn`, `vvn` | — |
| `STRUKTURY_TARIFU` | nabidkovac | `stara_2026`, `nova_2027` | — |
| `TYPY_SLOUPCE` | nabidkovac | `text`, `cislo` | `text` |
| `RezimCapex` | nabidkovac | `cena_kwp`, `komponenty` | `cena_kwp` |
| práva (`PRAVA`) | auth | `projekty`, `finance`, `zmeny`, `nabidkovac`, `nabidkovac_katalog`, `admin`, `editace` | — |

---

## 13. Otevřené body, nedodělky a rizika

Přehled částí, které jsou v kódu jako kostra nebo mají známá omezení:

1. **POHODA integrace** – kostra; `nacti_faktury_dle_vs` vyhodí `NotImplementedError`. Skutečné XML volání `listInvoiceRequest` na mServer je TODO.
2. **Fakturační pravidla** (`pravidla.py`) – no-op; logika „kdy fakturovat" se dopisuje iterativně.
3. **Skript `create_user.py`** – ⚠️ **nefunkční** (importuje neexistující `Role`, používá zrušený sloupec `role`). Nutná aktualizace na `je_admin`/`skupina_id`/`extra_prava`.
4. **`upraveno_rucne` v matici** – příznak se udržuje, ale `nacti_z_freela` v režimu `prepsat` přepíše i ručně upravené buňky (příznak zatím není pojistkou proti přepisu). Poznámka (`poznamka`) je ale vždy chráněná.
5. **Koeficient AKU (peak shaving 2027)** – ⚠️ nepotvrzený optimistický předpoklad; v bezztrátovém v1 modelu vychází plná sleva. Výsledky nést s příznakem `predpoklad_aku_neoverovany: true`.
6. **Sazby `nova_2027`** – modelový odhad (`je_modelovy_odhad=True`); ERÚ vydá závazné ceny ~11/2026.
7. **Model baterie (v1)** – zjednodušený: kapacita 1:1 bez ztrát, žádný limit DoD, počáteční SoC = plná.
8. **Měrný výnos FVE** – výchozí 1000 kWh/kWp je ilustrativní (reálně ~950–1080); simulace výroby je clear-sky model, ne PVGIS.
9. **EG.D a PRE** – v seedu nejsou; doplní se přes admin až po ověření čísel.
10. **LLM extrakce faktur** (`extrahovana_data_faktury`) a **generování PDF nabídek** (`generovane_nabidky_pdf`) – tabulky připravené, funkce zatím neimplementovány.
11. **Raynet CRM** – pole `raynet_id`/`synchronizovano_at` připravena, sync se nepoužívá.
12. **Pohled 3 (Přehled změn)** – dle `docs/SPEC.md` zatím koncept, není implementován.
