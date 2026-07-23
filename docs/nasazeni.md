# Provoz a nasazení appky Greensie

Stručný popis, jak appka běží na produkčním VPS a jak nasadit novou verzi.
Doplňuje `SPEC.md` kap. 6 (technické prostředí).

## Kde co běží

- **Server:** Hetzner VPS (Debian 12), uživatel `dan`, projekt v
  `/home/dan/projects/greensie-app` (git repo napojený na GitHub přes SSH).
- **Backend (FastAPI/uvicorn):** běží jako **systemd služba `greensie-backend`**
  na `127.0.0.1:8000`.
  - Unit: `/etc/systemd/system/greensie-backend.service` (šablona v repu:
    `deploy/greensie-backend.service`).
  - `User=dan`, `WorkingDirectory=/home/dan/projects/greensie-app/backend`,
    spouští `backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`.
  - `Restart=always` (po pádu se sám nahodí za 3 s).
  - Stav / log / restart:
    ```bash
    systemctl status greensie-backend
    journalctl -u greensie-backend -f
    sudo systemctl restart greensie-backend
    ```
- **Frontend (statický build):** servíruje **Caddy** z `/var/www/greensie`
  (vlastník `caddy:caddy` – uživatel `dan` sem **nezapíše**, kopírování dělá
  `deploy/update.sh` pod rootem). Caddy zároveň funguje jako reverzní proxy a
  přeposílá `/api/*` na backend `127.0.0.1:8000`.
  - Config: `/etc/caddy/Caddyfile` (šablona v repu: `deploy/Caddyfile`).
  - Appka je dostupná na `https://167-235-254-188.sslip.io`.
- **Databáze:** PostgreSQL (`localhost:5432`, DB `greensie`). Přístup a klíče
  jsou v `/home/dan/projects/greensie-app/.env` (mimo git).

## Databázové migrace

Nepoužívá se Alembic. Při startu backendu se v `app/main.py` volá
`Base.metadata.create_all(...)`, které **jen doplní chybějící tabulky**
(existující nechá být), a funkce `_lehka_migrace()` idempotentně doplní
chybějící sloupce na tabulce `uzivatele`. Nová tabulka/model se aktivuje
zaregistrováním v `app/main.py` – přidání tabulek je bezpečné (nemaže data).

Sloupce do **existující** tabulky `create_all` nepřidá – takové změny se
řeší přes `ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...` v `_lehka_migrace`.

## Nasazení nové verze

1. **Stáhnout kód** (jako `dan`):
   ```bash
   cd /home/dan/projects/greensie-app
   git pull --ff-only origin main
   ```
2. **Závislosti** (jen když se změnily):
   ```bash
   # backend:
   backend/venv/bin/pip install -r backend/requirements.txt
   # frontend:
   (cd frontend && npm ci)
   ```
3. **Build + kopírování frontendu + restart služeb** – to vyžaduje **root**
   (zápis do `/var/www/greensie` vlastněného `caddy` a `systemctl`/`caddy reload`).
   Spouští se jedním skriptem:
   ```bash
   sudo bash deploy/update.sh
   ```
   `deploy/update.sh` provede: `npm run build` (jako dan) → smaže a nakopíruje
   `frontend/dist` do `/var/www/greensie` → `chown caddy:caddy` → `systemctl
   restart greensie-backend` (tím proběhne i případná migrace nových tabulek)
   → `systemctl reload caddy`.

> **Pozn.:** backend a frontend je potřeba nasazovat **společně**. `/auth/me`
> vrací seznam dlaždic včetně nových; kdyby běžel nový backend se starým
> frontendem, mohla by se objevit nefunkční dlaždice. `deploy/update.sh` obojí
> řeší v jednom kroku.

## Citlivé údaje (`.env`)

Nikdy se necommitují (jsou v `.gitignore`). Kromě přístupů k DB a
Freelu/Pohodě je připravená proměnná `ANTHROPIC_API_KEY=` (zatím prázdná –
placeholder pro budoucí LLM extrakci faktur v Nabídkovači) a volitelná
`NABIDKOVAC_UPLOAD_DIR` (kam se ukládají nahrané dokumenty; default
`<kořen repa>/nabidka_soubory`).
