# Nasazení nové verze

> **Typ:** provozní / serverový dokument · **Prostředí:** produkční VPS (Hetzner)
> **Kdo to dělá:** Dan (má na serveru `sudo`) · **Kód:** `deploy/update.sh`, `deploy/Caddyfile`, `deploy/greensie-backend.service`

Jak dostat novou verzi kódu na produkci — tj. z odladěného a slitého (merged) kódu na GitHubu
udělat běžící appku na adrese **https://167-235-254-188.sslip.io**.

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

- `sudo` si **vyžádá heslo** — spouští ho Dan sám (skript zasahuje do `/var/www` a systemd služeb).
- Skript je „ukecaný": vypisuje, u kterého kroku je (`==> …`). Poslední řádek je
  `HOTOVO. Nová verze běží na https://167-235-254-188.sslip.io`.
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

- Otevři **https://167-235-254-188.sslip.io** a projdi změnu, kvůli které ses nasazoval.
  (Občas je potřeba tvrdý refresh `Ctrl+Shift+R`, aby prohlížeč nezobrazil starý frontend z cache.)
- **Health check backendu** — přes Caddy (ten `/api` odřízne a pošle na backend):

```bash
curl -s https://167-235-254-188.sslip.io/api/health
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
- **`sudo` a heslo:** skript spouští Dan interaktivně (zadá heslo). Není zamýšlený jako plně
  automatické/CI nasazení.
- **První HTTPS po výměně/instalaci** může chvíli trvat, než si Caddy dotáhne certifikát
  (Let's Encrypt) — u běžného `update.sh` (jen `reload`) se to netýká, certifikát už existuje.

## Odkazy

- Prostředí a architektura serveru: [`server/architektura-prostredi.md`](architektura-prostredi.md)
  (VPS, FastAPI + React + PostgreSQL, Caddy, tok požadavků)
- Skripty a konfigurace: `deploy/update.sh`, `deploy/install.sh` (jednorázová instalace),
  `deploy/greensie-backend.service` (systemd), `deploy/Caddyfile` (reverzní proxy + HTTPS)
- Technická specifikace: `docs/server-spec.md` → kap. 2 „Architektura a nasazení"
