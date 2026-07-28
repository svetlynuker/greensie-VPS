#!/usr/bin/env bash
# ============================================================
#  Greensie – zrušení náhledu (deploy/nahled.sh)
#  Spouštět jako root:  sudo bash deploy/nahled-zrusit.sh
#
#  Odstraní adresu, službu, statický frontend, kopii databáze a vstupní heslo.
#  Ostré appky na app.greensie.cz se to nijak netýká.
#
#  Klon kódu v /home/dan/projects/greensie-nahled se NEMAŽE (může tam být
#  rozdělaná práce) — smaž ho ručně, když ho nepotřebuješ:
#      rm -rf /home/dan/projects/greensie-nahled
# ============================================================
set -euo pipefail

WEB="/var/www/greensie-nahled"
SLUZBA="greensie-nahled"
VHOST="/etc/caddy/sites/greensie-nahled.caddy"
DB_NAHLED="greensie_nahled"
HESLO_SOUBOR="/etc/greensie-nahled.heslo"

if [[ $EUID -ne 0 ]]; then
	echo "Spusť jako root:  sudo bash deploy/nahled-zrusit.sh" >&2
	exit 1
fi

echo "==> Zastavuji službu ${SLUZBA}…"
systemctl disable --quiet --now "${SLUZBA}" 2>/dev/null || true
rm -f "/etc/systemd/system/${SLUZBA}.service"
systemctl daemon-reload

echo "==> Odstraňuji adresu z Caddy…"
rm -f "${VHOST}"
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy

echo "==> Mažu statický frontend ${WEB}…"
rm -rf "${WEB}"

echo "==> Mažu kopii databáze ${DB_NAHLED}…"
sudo -u postgres psql -q -c "DROP DATABASE IF EXISTS ${DB_NAHLED};"

echo "==> Mažu vstupní heslo…"
rm -f "${HESLO_SOUBOR}"

cat <<EOF

Náhled zrušen. Ostrá appka na https://app.greensie.cz je nedotčená.
Klon kódu zůstal v /home/dan/projects/greensie-nahled (smaž ručně, když nemá cenu).
EOF
