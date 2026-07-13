#!/usr/bin/env bash
# ============================================================
#  Greensie – jednorázová instalace produkčního nasazení
#  Spouštět jako root:  sudo bash deploy/install.sh
# ============================================================
set -euo pipefail

PROJEKT="/home/dan/projects/greensie-app"
WEB="/var/www/greensie"

echo "==> 1/7  Zastavuji vývojové servery (vite, ruční uvicorn)…"
pkill -u dan -f 'node.*vite' 2>/dev/null || true
pkill -u dan -f 'uvicorn app.main' 2>/dev/null || true
sleep 1

echo "==> 2/7  Instaluji webový server Caddy…"
if ! command -v caddy >/dev/null 2>&1; then
	apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
		| gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
	curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
		> /etc/apt/sources.list.d/caddy-stable.list
	apt-get update
	apt-get install -y caddy
else
	echo "    Caddy už je nainstalovaný, přeskakuji."
fi

echo "==> 3/7  Kopíruji hotový frontend do ${WEB}…"
mkdir -p "${WEB}"
rm -rf "${WEB:?}"/*
cp -r "${PROJEKT}/frontend/dist/." "${WEB}/"
chown -R caddy:caddy "${WEB}"

echo "==> 4/7  Nasazuji konfiguraci Caddy…"
cp "${PROJEKT}/deploy/Caddyfile" /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl restart caddy
systemctl enable caddy >/dev/null 2>&1 || true

echo "==> 5/7  Nasazuji backend jako službu na pozadí…"
cp "${PROJEKT}/deploy/greensie-backend.service" /etc/systemd/system/greensie-backend.service
systemctl daemon-reload
systemctl enable greensie-backend >/dev/null 2>&1 || true
systemctl restart greensie-backend

echo "==> 6/7  Nastavuji firewall (SSH + web)…"
if command -v ufw >/dev/null 2>&1; then
	ufw allow 22/tcp   >/dev/null
	ufw allow 80/tcp   >/dev/null
	ufw allow 443/tcp  >/dev/null
	ufw --force enable >/dev/null
else
	echo "    ufw není nainstalován – instaluji…"
	apt-get install -y ufw
	ufw allow 22/tcp   >/dev/null
	ufw allow 80/tcp   >/dev/null
	ufw allow 443/tcp  >/dev/null
	ufw --force enable >/dev/null
fi

echo "==> 7/7  Kontrola stavu…"
sleep 2
systemctl --no-pager --lines=0 status greensie-backend | head -4 || true
systemctl --no-pager --lines=0 status caddy | head -4 || true

echo ""
echo "============================================================"
echo "  HOTOVO. Appka poběží na:"
echo "     https://167-235-254-188.sslip.io"
echo "  (první načtení HTTPS může trvat 10-30 s, než Caddy získá"
echo "   certifikát – pak už je to okamžité.)"
echo "============================================================"
