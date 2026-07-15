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

echo "==> Restartuji Caddy…"
systemctl reload caddy

echo "HOTOVO. Nová verze běží na https://167-235-254-188.sslip.io"
