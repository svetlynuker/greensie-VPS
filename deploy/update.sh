#!/usr/bin/env bash
# ============================================================
#  Greensie – nasazení nové verze (po úpravách kódu)
#  Spouštět jako root:  sudo bash deploy/update.sh
# ============================================================
set -euo pipefail

PROJEKT="/home/dan/projects/greensie-app"
WEB="/var/www/greensie"

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
