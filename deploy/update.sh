#!/usr/bin/env bash
# ============================================================
#  Greensie – nasazení nové verze (po úpravách kódu)
#  Spouštět jako root:  sudo bash deploy/update.sh
# ============================================================
set -euo pipefail

PROJEKT="/home/dan/projects/greensie-app"
WEB="/var/www/greensie"
VENV="${PROJEKT}/backend/venv"

# Instalace Python závislostí backendu do venv, který používá služba
# greensie-backend. NEMAZAT: bez tohohle kroku po git pullu, který přidá nový
# balíček do requirements.txt (např. xlrd/openpyxl u peak shavingu, PR #6),
# backend po restartu spadne na ImportError a musí se doinstalovávat ručně.
# pip install je idempotentní – už nainstalované balíčky jen přeskočí.
echo "==> Instaluji Python závislosti backendu do venv…"
sudo -u dan bash -c "'${VENV}/bin/pip' install -r '${PROJEKT}/backend/requirements.txt'"

# Headless Chromium pro tisk nabídky do PDF. NEMAZAT: `pip install playwright`
# přinese jen knihovnu, samotný prohlížeč se stahuje tímhle příkazem a bez něj
# skončí „Uložit do PDF" chybou 503. Obojí je idempotentní – když je Chromium
# ve správné verzi stažené, příkaz jen skončí.
#
# Písma jsou stejně povinná jako prohlížeč: na čistém serveru žádná nejsou
# a Chromium by nabídku vysázel do prázdna. Liberation Sans má shodné metriky
# s Arialem, takže PDF zlomí řádky tam, kde je zlomil editor v prohlížeči.
echo "==> Instaluji písma a Chromium pro tisk PDF…"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  fonts-liberation fonts-dejavu-core
sudo -u dan bash -c "'${VENV}/bin/playwright' install chromium"
# Systémové knihovny, které Chromium potřebuje (libnss3, libasound2…). Běží jako
# root, protože instaluje balíčky; `--with-deps` samo zavolá apt.
"${VENV}/bin/playwright" install-deps chromium

# npm install PŘED buildem – stejný důvod: když PR přidá nový npm balíček do
# package.json, build by bez něj spadl. npm install je taky idempotentní.
echo "==> Instaluji npm závislosti frontendu…"
sudo -u dan bash -c "cd '${PROJEKT}/frontend' && npm install"

echo "==> Building frontend…"
sudo -u dan bash -c "cd ${PROJEKT}/frontend && npm run build"

echo "==> Kopíruji nový frontend do ${WEB}…"
rm -rf "${WEB:?}"/*
cp -r "${PROJEKT}/frontend/dist/." "${WEB}/"
chown -R caddy:caddy "${WEB}"

echo "==> Restartuji backend…"
systemctl restart greensie-backend

# Stahování pošty (e-mailový klient, CRM-33) běží jako VLASTNÍ služba, ne uvnitř
# backendu — pomalé IMAP volání ve web procesu dokáže appku dotlačit k 502.
# NEMAZAT: bez tohohle kroku by se po git pullu, který změní kód workeru,
# restartoval jen backend a pošta by dál běžela ze staré verze. Kopie jednotky
# je tu ze stejného důvodu jako u Caddyfile — aby platila verze z repa.
echo "==> Nasazuji a restartuji službu e-mailu…"
cp "${PROJEKT}/deploy/greensie-email.service" /etc/systemd/system/greensie-email.service
systemctl daemon-reload
systemctl enable greensie-email >/dev/null
systemctl restart greensie-email

# Konfiguraci Caddy je nutné nasadit ze repa, ne jen reloadovat. NEMAZAT:
# `systemctl reload caddy` načte /etc/caddy/Caddyfile — kdyby se sem nová verze
# nezkopírovala, reload by vrátil STAROU konfiguraci a změna vhostu z repa
# (např. přidání domény app.greensie.cz) by se ztratila.
# Validace běží nad souborem v repu ještě PŘED kopií, aby chybný Caddyfile
# nepřepsal funkční konfiguraci na serveru.
echo "==> Nasazuji konfiguraci Caddy…"
caddy validate --config "${PROJEKT}/deploy/Caddyfile" --adapter caddyfile
cp "${PROJEKT}/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy

echo "HOTOVO. Nová verze běží na https://app.greensie.cz"
echo "     Stav stahování pošty:  systemctl status greensie-email"
