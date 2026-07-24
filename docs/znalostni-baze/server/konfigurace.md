# Konfigurace: proměnné prostředí, databáze, e-maily

> **Rovina:** server / provoz · **Kód:** `backend/app/database.py`, `backend/app/main.py`, `backend/app/mailer.py`
> **Pro koho:** admin / správce serveru (VPS)

Provozní dokument, který shrnuje, **jak se aplikace konfiguruje**: přes soubor `.env`
(proměnné prostředí), jak se připojuje k **databázi PostgreSQL** a jak posílá **e-maily** přes SMTP.
Fakta jsou vytažená z kódu; kde je něco nezřejmé nebo modelové, je to v sekci „Poznámky a úskalí".

> ⚠️ **`.env` se nikdy neverzuje ani nevypisuje.** Soubor je v `.gitignore` (řádek `.env`)
> a leží v **kořeni repa** (`backend/app/database.py` ho načítá přes `load_dotenv` z cesty
> `…/kořen/.env`). V této dokumentaci uvádíme **jen názvy proměnných a jejich účel — nikdy hodnoty**.

---

## Proměnné prostředí (`.env`)

Aplikace čte konfiguraci z proměnných prostředí (na serveru z `.env`). Rozlišuj dva způsoby čtení v kódu:

- `os.environ["NÁZEV"]` — **povinná** proměnná. Když chybí, aplikace **spadne při startu**
  (např. `DATABASE_URL`, `SECRET_KEY`).
- `os.environ.get("NÁZEV", "výchozí")` — **nepovinná**; když chybí, použije se výchozí hodnota z kódu.

### Jádro aplikace

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `DATABASE_URL` | Připojovací řetězec k PostgreSQL (SQLAlchemy `create_engine`). | **Ano** | — (bez ní start selže) |
| `SECRET_KEY` | Tajný klíč pro podpis přihlašovacích **JWT tokenů** (`HS256`, `backend/app/auth/permissions.py`). | **Ano** | — (bez ní start selže) |
| `APP_URL` | Veřejná adresa aplikace — vkládá se do e-mailů (přihlašovací odkaz) a používá jako fallback pro konektor. | Ne | `https://167-235-254-188.sslip.io` |

### E-maily (SMTP) — viz `backend/app/mailer.py`

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `SMTP_HESLO` | Heslo poštovní schránky. **Bez něj se e-maily neposílají** (funkce jen tiše nic neodešle / vyhodí chybu). | Ne¹ | `""` (prázdné = neposílat) |
| `SMTP_HOST` | Adresa SMTP serveru. | Ne | `smtp.seznam.cz` |
| `SMTP_PORT` | Port SMTP serveru (587 = STARTTLS, 465 = implicitní SSL). | Ne | `587` |
| `SMTP_USER` | Přihlašovací jméno schránky (login). | Ne | `automat@greensie.cz` |
| `SMTP_ODESILATEL` | Adresa v hlavičce `From`. | Ne | = hodnota `SMTP_USER` |

> ¹ `SMTP_HESLO` není povinné pro start aplikace, ale **je nutné, aby e-maily fungovaly**.
> Bez něj funkce `email_nastaven()` vrátí `False` a odesílání se přeskočí (best-effort — viz níže).

### Freelo (Přehled projektů) — viz `backend/app/matice/freelo.py`

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `FREELO_EMAIL` | Přihlašovací e-mail k Freelo API. | Ano pro Freelo² | — |
| `FREELO_API_KEY` | API klíč k Freelo API. | Ano pro Freelo² | — |

> ² Čtou se přes `os.environ[...]`, takže **jakmile se volá synchronizace s Freelem** a proměnné
> chybí, operace selže. Pro běh appky bez synchronizace nejsou nutné.

### Konektor Raynet ↔ Google Drive — viz `backend/app/konektor/`

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `KONEKTOR_ENC_KEY` | **Šifrovací klíč (Fernet)** pro tajemství konektoru (Raynet API klíč, Google service-account JSON) — ta se do DB ukládají **zašifrovaná**. Klíč žije jen v `.env`, ne v DB. | Ano pro konektor³ | — (bez něj nelze uložit ani přečíst tajemství) |
| `KONEKTOR_WEBHOOK_SECRET` | Token pro ověření push notifikací z Google Drive (`X-Goog-Channel-Token`). | Ne | `""` |
| `PUBLIC_BASE_URL` | Veřejná URL pro adresu webhook endpointu; když chybí, použije se `APP_URL`, jinak vestavěná výchozí. | Ne | fallback → `APP_URL` → `https://167-235-254-188.sslip.io` |

> ³ **Ztráta `KONEKTOR_ENC_KEY` = nutnost všechna tajemství konektoru zadat znovu.** Tajemství jsou
> v UI „write-only" (dají se zadat/přepsat, ale nikdy nevrátit zpět; UI ukazuje jen příznak „nastaveno").

### Finance / Pohoda — viz `backend/app/finance/pohoda.py`

Všechny čtyři jsou v kódu vedené jako `POVINNE_ENV` — teprve když jsou **všechny vyplněné**,
považuje se napojení na Pohodu za nastavené.

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `POHODA_URL` | Adresa API mServeru Pohody (např. `…/xml`). | Ano pro Pohodu | — |
| `POHODA_LOGIN` | Přihlašovací jméno k mServeru. | Ano pro Pohodu | — |
| `POHODA_HESLO` | Heslo k mServeru. | Ano pro Pohodu | — |
| `POHODA_ICO` | IČO firmy, na kterou se dotaz váže. | Ano pro Pohodu | — |

### Nabídkovač

| Proměnná | K čemu slouží | Povinná? | Výchozí (v kódu) |
|---|---|---|---|
| `NABIDKOVAC_UPLOAD_DIR` | Složka pro nahrané soubory nabídkovače. | Ne | `<kořen repa>/nabidka_soubory` |

---

## Databáze (PostgreSQL)

### Jak se aplikace připojuje
- Používá se **PostgreSQL** přes **SQLAlchemy**. Připojení vzniká v `backend/app/database.py`:
  `engine = create_engine(DATABASE_URL)`, session přes `SessionLocal` (`get_db()` je závislost pro endpointy).
- `DATABASE_URL` se bere z `.env` (přes `load_dotenv`) — **je povinná**, bez ní appka nenastartuje.

### Tvorba tabulek (`create_all`)
- Při startu se v `backend/app/main.py` volá `Base.metadata.create_all(bind=engine)`.
  To **vytvoří chybějící tabulky** podle modelů (modely se musí naimportovat **před** `create_all`,
  proto jsou nahoře v `main.py` importy `… models  # noqa: F401 - registrace modelů`).

### „Lehká migrace" (přidávání sloupců do existujících tabulek)
- **Zásadní omezení:** `create_all` **nepřidá nový sloupec do už existující tabulky** — umí jen
  vytvořit tabulku, která ještě není. Když tedy do modelu přibude sloupec, u nasazené (existující)
  tabulky se sám neobjeví.
- Řeší to funkce **`_lehka_migrace()`** v `main.py` (volá se hned po `create_all`). Spouští ručně
  psané, **idempotentní** příkazy typu:

  ```sql
  ALTER TABLE <tabulka> ADD COLUMN IF NOT EXISTS <sloupec> <typ> ...
  ```

- Díky `IF NOT EXISTS` je bezpečné to pouštět opakovaně při každém startu. Takto se dodávají např.
  sloupce `uzivatele.skupina_id / je_admin / musi_zmenit_heslo`, `projekty.disk_url / disk_rucni /
  raynet_deal_id`, řada sloupců `konektor_nastaveni.dms_*` a další.
- **Není to plnohodnotný migrační nástroj** (žádné Alembic verze) — jde o cílené `ADD COLUMN`
  a pár `ALTER COLUMN`. Odstranění nebo přejmenování sloupce takto neřešíme.

### Oprávnění databázového uživatele
- Aby `create_all` a `_lehka_migrace()` fungovaly, musí mít DB uživatel z `DATABASE_URL` právo
  zakládat objekty ve schématu `public`. Na novějším PostgreSQL (14+) je někdy potřeba to explicitně
  přidělit:

  ```sql
  GRANT CREATE ON SCHEMA public TO <db_uzivatel>;
  ```

  Bez toho start selže na chybě oprávnění při tvorbě tabulek.

### Pozor na verze knihoven pro hesla
- Hašování hesel běží přes **passlib** s **bcrypt** (`CryptContext(schemes=["bcrypt"])`
  v `backend/app/auth/permissions.py`).
- **`passlib==1.7.4` vyžaduje `bcrypt==4.0.1`.** Novější `bcrypt` (4.1+) mění vnitřní rozhraní
  a passlib 1.7.4 na něm padá (chyba při čtení verze bcryptu). Obě verze jsou proto **připnuté**
  v `backend/requirements.txt` — nezvedej je nezávisle na sobě.

---

## E-maily (SMTP)

Odesílání řeší `backend/app/mailer.py`. Používá se pro **rozeslání přístupových údajů** nově
založeným uživatelům (jednorázové heslo + přihlašovací odkaz).

### Výchozí nastavení
- **Odesílatel:** `automat@greensie.cz` (schránka na Seznamu; `SMTP_USER` / `SMTP_ODESILATEL`).
- **Server:** `smtp.seznam.cz`, port **587**, **STARTTLS** (submission port).
- Konfiguraci lze celou přepsat proměnnými `SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_ODESILATEL`
  (viz tabulka výše).

### Jak se volí zabezpečení podle portu
- **Port 587** → naváže se prosté spojení a povýší přes `STARTTLS` (výchozí, doporučené).
- **Port 465** → implicitní SSL (`SMTP_SSL`) hned od začátku.

> ⚠️ **Hetzner (VPS) blokuje odchozí porty 465 i 25.** Proto varianta **465/SSL na VPS nefunguje**
> a používá se výhradně **587/STARTTLS**. Nechávej `SMTP_PORT=587`.

### Best-effort — akce se kvůli e-mailu neruší
- Když **chybí `SMTP_HESLO`**, e-mail se **neodešle**. Funkce `email_nastaven()` vrátí `False`;
  přímé volání `posli_email()` vyhodí `RuntimeError("SMTP není nastaven …")`.
- Odesílání je proto koncipované jako **best-effort**: samotná operace (např. založení uživatele)
  **proběhne i tak** a jen se neodešle notifikační e-mail. Admin pak musí přihlašovací údaje předat ručně.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **`.env` v kořeni repa, ne v `backend/`.** `database.py` ho hledá o tři úrovně výš
  (`parent.parent.parent / ".env"`). Na to pozor při ruční editaci na serveru.
- **Vestavěná výchozí URL** `https://167-235-254-188.sslip.io` je v kódu na dvou místech
  (`mailer.py` a `konektor/logika.py`) jako fallback, když není `APP_URL` / `PUBLIC_BASE_URL`.
  Po přechodu na vlastní doménu je vhodné `APP_URL` nastavit, ať odkazy v e-mailech sedí.
- **`SMTP_HESLO` bez startovní kontroly:** aplikace nastartuje i bez něj, chyba se projeví až
  při pokusu o odeslání. Doporučeno ověřit `email_nastaven()` po nasazení.
- **`GRANT CREATE ON SCHEMA public`** není v kódu — je to provozní krok na straně DB serveru;
  přesnou nutnost ověřit podle verze PostgreSQL a nastavení DB uživatele.
- **Migrace nejsou verzované (bez Alembic).** Přidávání sloupců je ruční v `_lehka_migrace()`;
  složitější změny schématu je nutné dělat obezřetně a idempotentně.

## Odkazy
- Prostředí a architektura: [`server/architektura-prostredi.md`](architektura-prostredi.md) *(připravuje se)*
- Nasazení nové verze: [`server/nasazeni.md`](nasazeni.md) *(připravuje se)*
- Přihlášení a změna hesla (kde se hesla haší a e-mailují): [`moduly/prihlaseni-zmena-hesla.md`](../moduly/prihlaseni-zmena-hesla.md) *(připravuje se)*
- Kód: `backend/app/database.py`, `backend/app/main.py` (`_lehka_migrace`), `backend/app/mailer.py`,
  `backend/app/auth/permissions.py`, `backend/app/matice/freelo.py`, `backend/app/konektor/crypto.py`,
  `backend/app/finance/pohoda.py`
