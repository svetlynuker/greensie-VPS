# Nasazení nové verze

> **Typ:** provozní / serverový dokument · **Prostředí:** produkční VPS (Hetzner)
> **Kdo to dělá:** Dan nebo Claude (od 30. 7. 2026 je na serveru `sudo` bez hesla) · **Kód:** `deploy/update.sh`, `deploy/Caddyfile`, `deploy/greensie-backend.service`,
> náhled větve: `deploy/nahled.sh`, `deploy/nahled-zrusit.sh`, `deploy/greensie-nahled.service`

Jak dostat novou verzi kódu na produkci — tj. z odladěného a slitého (merged) kódu na GitHubu
udělat běžící appku na adrese **https://app.greensie.cz**.

Nasazení má **dva kroky, které jdou po sobě**:

1. **Stáhnout nový kód** z gitu na server (`git pull`).
2. **Nasadit ho** skriptem `deploy/update.sh` (nainstaluje závislosti, sestaví frontend, restartuje služby).

> ⚠️ **Nejdůležitější úskalí celého dokumentu:** `deploy/update.sh` **sám kód z gitu nestahuje.**
> Sestaví a nasadí přesně to, co zrovna leží na disku serveru. Když před ním zapomeneš na `git pull`,
> proženeš celým procesem **starou verzi** a příznakem to nijak nepoznáš — skript doběhne „HOTOVO",
> ale na webu bude pořád to staré. **Vždy nejdřív `git pull`, pak `update.sh`.**

---

## Postup krok za krokem

Všechno běží na serveru (přihlaš se přes SSH). Projekt je v `~/projects/greensie-app`
(= `/home/dan/projects/greensie-app`).

### 1. Stáhni nový kód z gitu

```bash
cd ~/projects/greensie-app
git checkout main
git pull
```

- `git checkout main` — ujistí se, že jsi na hlavní větvi (produkce jede z `main`).
- `git pull` — stáhne poslední slité změny z GitHubu.

> Pokud `git pull` hlásí konflikt nebo „local changes", na serveru někdo/něco ručně sáhlo do souborů.
> **Needituj kód na serveru** — vyřeš to (viz „Poznámky a úskalí") a teprve pak pokračuj.

### 2. Spusť nasazovací skript

```bash
sudo bash deploy/update.sh
```

- `sudo` **už nechce heslo** (pravidlo `NOPASSWD` v `/etc/sudoers.d/greensie-claude`, nastaveno
  30. 7. 2026) — skript tedy může spustit i Claude. Zasahuje do `/var/www` a systemd služeb, proto to
  `sudo` potřebuje.
- Skript je „ukecaný": vypisuje, u kterého kroku je (`==> …`). Poslední řádek je
  `HOTOVO. Nová verze běží na https://app.greensie.cz`.
- Skript má `set -euo pipefail` — při **jakékoli chybě se okamžitě zastaví** a HOTOVO se nevypíše.
  Když HOTOVO nevidíš, nasazení **neproběhlo celé** (viz „Rollback").

### 3. Ověř, že nová verze běží

Viz sekce [„Jak ověřit nasazení"](#jak-ověřit-nasazení) níže.

---

## Co přesně `deploy/update.sh` udělá

Skript běží jako root, ale kroky, které mají patřit uživateli `dan` (venv, node_modules, build),
spouští přes `sudo -u dan`, aby soubory nezůstaly vlastněné rootem. Proměnné ve skriptu:
`PROJEKT=/home/dan/projects/greensie-app`, `WEB=/var/www/greensie`, `VENV=$PROJEKT/backend/venv`.

Kroky v tomto pořadí:

1. **Python závislosti backendu** — `pip install -r backend/requirements.txt` do venv
   (`backend/venv`), který používá služba `greensie-backend`. Běží pod `dan`.
   `pip install` je idempotentní: už nainstalované balíčky přeskočí, dotáhne jen nové.
   *Proč to tu je:* když nová verze přidá do `requirements.txt` balíček (např. `xlrd`/`openpyxl`),
   bez tohohle kroku by backend po restartu spadl na `ImportError`.
2. **npm závislosti frontendu** — `npm install` ve složce `frontend` (pod `dan`, taky idempotentní).
   *Proč PŘED buildem:* když nová verze přidá npm balíček do `package.json`, build by bez něj spadl.
3. **Build frontendu** — `npm run build` ve `frontend` (Vite). Vytvoří statické soubory ve
   `frontend/dist/`.
4. **Nasazení frontendu** — vymaže obsah `/var/www/greensie` (`rm -rf`) a nakopíruje tam čerstvý
   obsah `frontend/dist/`. Nastaví vlastníka `caddy:caddy` (Caddy tyhle soubory servíruje).
5. **Restart backendu** — `systemctl restart greensie-backend` (uvicorn + FastAPI na `127.0.0.1:8000`).
   Tímto se natáhne nový Python kód a proběhnou startup migrace (`create_all` + lehká migrace + seed).
6. **Reload Caddy** — `systemctl reload caddy` (načte konfiguraci; frontend už je vyměněný z kroku 4).
7. **Výpis „HOTOVO"** s produkční adresou.

> Užitečná vlastnost pořadí: **web se maže (`rm -rf`) až v kroku 4, tedy až PO úspěšném buildu.**
> Když build (krok 3) spadne, skript se kvůli `set -e` zastaví ještě před mazáním — **živý web
> zůstane nedotčený** na staré verzi. Rozbitý build ti tedy web neshodí.

---

## Jak ověřit nasazení

### Rychlá kontrola z prohlížeče / curlem

- Otevři **https://app.greensie.cz** a projdi změnu, kvůli které ses nasazoval.
  (Občas je potřeba tvrdý refresh `Ctrl+Shift+R`, aby prohlížeč nezobrazil starý frontend z cache.)
- **Health check backendu** — přes Caddy (ten `/api` odřízne a pošle na backend):

```bash
curl -s https://app.greensie.cz/api/health
```

Očekávaný výstup: `{"stav":"ok"}`. Případně backend napřímo na serveru:

```bash
curl -s http://127.0.0.1:8000/health
```

### Stav služeb

```bash
systemctl status greensie-backend
systemctl status caddy
```

U backendu chceš vidět `active (running)` a čerstvý čas ve `since` (odpovídá právě provedenému
restartu). Kdyby padal dokola, uvidíš `activating (auto-restart)` nebo počítadlo restartů
(služba má `Restart=always`, `RestartSec=3` — po pádu se sama zkouší nahodit).

### Logy služby (když něco nesedí)

```bash
journalctl -u greensie-backend -n 100 --no-pager     # posledních 100 řádků
journalctl -u greensie-backend -f                    # sledovat živě (Ctrl+C ukončí)
journalctl -u caddy -n 100 --no-pager                # log Caddy (proxy, HTTPS certifikát)
```

Nejčastější příčiny pádu backendu po restartu jsou v logu vidět hned: `ImportError`
(chybí Python balíček — viz krok 1), `KeyError` na chybějící `DATABASE_URL`/`SECRET_KEY`
v `.env`, nebo nedostupná databáze.

---

## Rollback / když se něco pokazí

**Zásada:** nasazení = „stáhnout kód + nasadit". Rollback je totéž, jen se vrátíš na starší kód
a znovu pustíš `update.sh`.

### Když spadl `update.sh` uprostřed

- HOTOVO se nevypsalo → přečti poslední `==>` řádek, u kterého skončil, a chybovou hlášku.
  - Spadl **před kopírováním webu** (kroky 1–3, typicky pip/npm/build) → **živý web pořád jede
    starou verzi**, nic se nestihlo přepsat. Oprav příčinu (chyba v `requirements.txt` /
    `package.json` / buildu) a spusť `sudo bash deploy/update.sh` znovu.
  - Spadl **při restartu backendu** (krok 5) → frontend je už nový, ale backend nemusí běžet.
    Zkontroluj `journalctl -u greensie-backend` a stav služby.

### Vrácení na předchozí verzi kódu

```bash
cd ~/projects/greensie-app
git log --oneline -n 10        # najdi hash poslední funkční verze (merge commit na main)
git checkout <hash>            # dočasně přepni na tu verzi (odpojená HEAD)
sudo bash deploy/update.sh     # nasaď starou verzi
```

Až bude oprava na GitHubu hotová, vrať se zpět: `git checkout main && git pull` a nasaď znovu
(sekce „Postup krok za krokem").

### Ruční restart bez celého nasazení

Když je kód i frontend v pořádku a jen potřebuješ „šťouchnout" do služeb:

```bash
sudo systemctl restart greensie-backend
sudo systemctl reload caddy
```

---

## Náhled větve pro spolupracovníky

Někdy je potřeba **ukázat kolegům rozdělanou práci** (větev, která ještě není slitá do `main`), aniž by
se sáhlo na ostrou appku. Na to je `deploy/nahled.sh`: postaví **druhou, samostatnou instanci** appky
na vlastní adrese, se **kopií databáze** a **bez klíčů k vnějším systémům**.

```bash
cd ~/projects/greensie-app
sudo bash deploy/nahled.sh                  # náhled výchozí větve (ta ve skriptu)
sudo bash deploy/nahled.sh nazev-vetve      # náhled konkrétní větve
sudo bash deploy/nahled.sh --jen-adresa     # jen vypíše adresu a heslo (nic nepřestavuje)
```

Na konci skript vypíše rámeček s **adresou, uživatelským jménem a vstupním heslem** — to je to, co se
posílá kolegům. Adresa je `https://nahled.<IP-serveru>.sslip.io` (doména se nekupuje, `sslip.io` ji
odvodí z IP; HTTPS certifikát si Caddy dotáhne sám).

### Jak se ke náhledu dostane kolega

1. Otevře odkaz → prohlížeč se zeptá na **vstupní heslo** (uživatel `nahled`, heslo z výpisu skriptu).
   Tohle heslo je **společné pro všechny** a chrání jen to, aby náhled nikdo nenašel náhodou.
2. Pak se přihlásí **svým vlastním účtem do appky** — účty i hesla jsou z kopie databáze, tedy stejné
   jako v ostré appce.

### Čím je náhled oddělený od ostré appky

| Co | Ostrá appka | Náhled |
|---|---|---|
| Adresa | `app.greensie.cz` | `nahled.<IP>.sslip.io` (+ vstupní heslo, `noindex`) |
| Kód | `/home/dan/projects/greensie-app` (větev `main`) | `/home/dan/projects/greensie-nahled` (zvolená větev) |
| Databáze | `greensie` | `greensie_nahled` — **kopie**, editace se do ostrých dat nepropíšou |
| Služba (systemd) | `greensie-backend`, port 8000 | `greensie-nahled`, port 8001 |
| Statický frontend | `/var/www/greensie` | `/var/www/greensie-nahled` |
| Klíče k Freelu, Disku, POHODĚ, SMTP, Anthropicu | v `.env` | **záměrně chybí** → náhled nemůže nic zapsat navenek ani rozeslat e-maily |
| Automatická synchronizace | zapnutá | v kopii **vypnutá** (`auto_zapnuto = false`), fronta úloh konektoru a Drive kanály vyprázdněné |
| Přihlašovací token | vlastní `SECRET_KEY` | vlastní `SECRET_KEY` → přihlášení z náhledu v ostré appce neplatí |

Náhled **sdílí s ostrou instalací jen Python venv** (`greensie-app/backend/venv`) — závislosti jsou
stejné a `update.sh` ho udržuje aktuální. Kód se bere z náhledového klonu.

### Opakované spuštění a zrušení

**Znovu spustit je bezpečné:** kód i frontend se aktualizují, databáze se **přelije znovu z ostré**
(tedy se zahodí, co kdo v náhledu naklikal) a vstupní heslo zůstane stejné (drží se
v `/etc/greensie-nahled.heslo`).

**Zrušení:**

```bash
sudo bash deploy/nahled-zrusit.sh
```

Odstraní adresu, službu, statický frontend, kopii databáze i vstupní heslo. Ostré appky se to nijak
netýká. **Klon kódu** v `/home/dan/projects/greensie-nahled` zůstane (může tam být rozdělaná práce) —
smaž ho ručně (`rm -rf /home/dan/projects/greensie-nahled`), když ho nepotřebuješ.

### Kontrola, že náhled běží správně

Skript si to zkontroluje sám a vypíše to ve rámečku, ručně:

```bash
curl -s http://127.0.0.1:8001/health                      # backend náhledu → {"stav":"ok"}
curl -s https://nahled.<IP>.sslip.io/api/health           # API MUSÍ projít i bez vstupního hesla
curl -s -o /dev/null -w '%{http_code}\n' https://nahled.<IP>.sslip.io/   # frontend → 401 (heslo drží)
systemctl status greensie-nahled
journalctl -u greensie-nahled -n 100 --no-pager
```

> ⚠️ **Proč `/api` nesmí být za vstupním heslem:** appka posílá ke každému volání API hlavičku
> `Authorization: Bearer <token>`, která by údaje vstupního (basic auth) hesla ve stejné hlavičce
> přepsala. Caddy by je nedostal, vrátil 401 a prohlížeč by uživateli otevřel přihlašovací pop-up,
> ze kterého se nedá dostat dál. Vhost proto heslem chrání **jen statický frontend**; API si přihlášení
> hlídá samo tokenem, stejně jako v ostré appce.

---

## Poznámky a úskalí (k ověření / nezřejmé)

- **`update.sh` nestahuje kód z gitu.** Zopakováno schválně — je to nejčastější zdroj „nasadil jsem,
  ale na webu je pořád stará verze". Pořadí je vždy: `git checkout main && git pull`, teprve pak
  `sudo bash deploy/update.sh`.
- **Neupravuj kód přímo na serveru.** Server je jen „příjemce" gitu. Ruční změny v souborech způsobí,
  že `git pull` skončí konfliktem nebo si přepíšeš vlastní změny. Vše se mění přes GitHub a slévá do `main`.
- **`.env` se nenasazuje.** Leží v kořeni repozitáře, je v `.gitignore` a `update.sh` se ho netýká.
  Novou/změněnou proměnnou prostředí (`DATABASE_URL`, `SECRET_KEY`, klíče integrací) je nutné do
  `.env` na serveru doplnit ručně a pak restartovat backend. **Tajemství nikde nevypisuj a necommituj.**
- **Migrace databáze** běží automaticky při startu backendu (v `backend/app/main.py`:
  `create_all` + lehká `ALTER TABLE … ADD COLUMN IF NOT EXISTS` + seed sazeb). `create_all`
  ale **nepřidává sloupce do existujících tabulek** — složitější změny schématu je potřeba řešit
  zvlášť, ne jen restartem. (Detaily viz doc o databázi, až vznikne.)
- **Cache prohlížeče:** po nasazení nového frontendu občas přetrvá starý; tvrdý refresh
  (`Ctrl+Shift+R`) to spolehlivě obejde.
- **`sudo` už nechce heslo:** od 30. 7. 2026 má `dan` pravidlo `NOPASSWD: ALL`
  (`/etc/sudoers.d/greensie-claude`), takže nasazení dotáhne do konce i Claude, bez asistence.
  Skript ale pořád **není** zamýšlený jako CI nasazení — nasadí přesně to, co zrovna leží na disku,
  včetně necommitnutých změn. Před spuštěním se vždy koukni na `git status`.
- **První HTTPS po výměně/instalaci** může chvíli trvat, než si Caddy dotáhne certifikát
  (Let's Encrypt) — u běžného `update.sh` (jen `reload`) se to netýká, certifikát už existuje.
- **Náhled: nové spuštění zahodí, co v něm kdo naklikal.** `nahled.sh` databázi náhledu vždy přelije
  z ostré. Když kolega v náhledu něco rozdělal, nespouštěj skript znovu — na aktualizaci jen adresy a
  hesla je `--jen-adresa`.
- **Náhled si `nahled.sh` sám odkopíruje do `/tmp` a pokračuje z kopie.** Skript totiž aktualizuje
  klon, ze kterého se často sám spouští; bash čte soubor postupně za běhu, takže by se pod rukama
  přepsal a mohl skončit uprostřed. Kopie se po sobě uklidí sama.
- **Výchozí větev je zadrátovaná ve skriptu** (proměnná `VETEV`). Bez argumentu tedy postavíš náhled
  té větve, ne aktuálně odbaveného `main` — větev radši uveď: `sudo bash deploy/nahled.sh moje-vetev`.
- **Náhled potřebuje ostrou instalaci.** Bere z ní venv, heslo k databázi z `.env` a data pro kopii.
  Není to samostatné prostředí, které by přežilo bez `greensie-app`.

## Odkazy

- Prostředí a architektura serveru: [`server/architektura-prostredi.md`](architektura-prostredi.md)
  (VPS, FastAPI + React + PostgreSQL, Caddy, tok požadavků)
- Skripty a konfigurace: `deploy/update.sh`, `deploy/install.sh` (jednorázová instalace),
  `deploy/greensie-backend.service` (systemd), `deploy/Caddyfile` (reverzní proxy + HTTPS)
- Náhled větve: `deploy/nahled.sh`, `deploy/nahled-zrusit.sh`, `deploy/greensie-nahled.service`
- Technická specifikace: `docs/server-spec.md` → kap. 2 „Architektura a nasazení"
