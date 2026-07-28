#!/usr/bin/env bash
# ============================================================
#  Greensie – NÁHLED větve pro spolupracovníky
#  Spouštět jako root:  sudo bash deploy/nahled.sh [větev]
#
#  Postaví samostatnou instanci appky, na kterou se dá poslat odkaz:
#
#    https://nahled.167-235-254-188.sslip.io
#      ↑ HTTPS od Caddy, na vstupu společné heslo (vypíše se na konci)
#
#  Náhled je od ostré appky oddělený ve všem, co může škodit:
#    • vlastní KOPIE databáze (greensie_nahled) — editace se do ostrých dat
#      nepropíšou
#    • BEZ klíčů k Freelu, Google Drive, POHODĚ, SMTP a Anthropicu — nemůže
#      tedy nic zapsat do vnějších systémů ani rozeslat e-maily
#    • vypnutá automatická synchronizace a vyprázdněná frontá úloh konektoru
#    • vlastní SECRET_KEY — přihlášení z náhledu neplatí v ostré appce
#
#  Opakované spuštění je bezpečné: kód i frontend se aktualizují, databáze se
#  přelije znovu z ostré (tedy zahodí, co kdo v náhledu naklikal) a vstupní
#  heslo zůstane stejné.
#
#  Zrušení:  sudo bash deploy/nahled-zrusit.sh
# ============================================================
set -euo pipefail

VETEV="${1:-worktree-crm-layout-redesign}"

ZDROJ="/home/dan/projects/greensie-app"          # ostrá instalace (odkud se klonuje a bere venv)
KLON="/home/dan/projects/greensie-nahled"        # kód náhledu
WEB="/var/www/greensie-nahled"                   # statický frontend náhledu
VENV="${ZDROJ}/backend/venv"
SLUZBA="greensie-nahled"
PORT="8001"
DB_ZDROJ="greensie"
DB_NAHLED="greensie_nahled"
DB_UZIVATEL="greensie_user"
DOMENA="nahled.167-235-254-188.sslip.io"
VHOST="/etc/caddy/sites/greensie-nahled.caddy"
HESLO_SOUBOR="/etc/greensie-nahled.heslo"        # ať se heslo mezi běhy nemění

if [[ $EUID -ne 0 ]]; then
	echo "Spusť jako root:  sudo bash deploy/nahled.sh" >&2
	exit 1
fi

echo "==> Náhled větve: ${VETEV}"

# ---------- 1. Kód náhledu ----------
if [[ -d "${KLON}/.git" ]]; then
	echo "==> Aktualizuji klon v ${KLON}…"
	sudo -u dan git -C "${KLON}" fetch --quiet origin "${VETEV}"
	sudo -u dan git -C "${KLON}" checkout --quiet -B "${VETEV}" "origin/${VETEV}"
else
	echo "==> Klonuji větev do ${KLON}…"
	sudo -u dan git clone --quiet --branch "${VETEV}" "${ZDROJ}" "${KLON}"
	# Origin ať míří na GitHub, aby fetch tahal z něj, ne z lokální kopie.
	PUVODNI_ORIGIN="$(sudo -u dan git -C "${ZDROJ}" remote get-url origin)"
	sudo -u dan git -C "${KLON}" remote set-url origin "${PUVODNI_ORIGIN}"
fi

# ---------- 2. Kopie databáze ----------
echo "==> Vytvářím kopii databáze ${DB_ZDROJ} → ${DB_NAHLED}…"
sudo -u postgres psql -q -c "DROP DATABASE IF EXISTS ${DB_NAHLED};"
sudo -u postgres createdb -O "${DB_UZIVATEL}" "${DB_NAHLED}"
sudo -u postgres pg_dump "${DB_ZDROJ}" | sudo -u postgres psql -q "${DB_NAHLED}"

echo "==> Zneškodňuji v kopii vše, co sahá do vnějších systémů…"
sudo -u postgres psql -q "${DB_NAHLED}" <<'SQL'
-- Automatická synchronizace z Freela: v náhledu nikdy.
UPDATE nastaveni_synchronizace SET auto_zapnuto = false;
-- Fronta úloh konektoru: ať worker nezpracuje nic, co míří na Google Drive.
TRUNCATE konektor_job_queue;
-- Registrované Drive kanály (webhooky) v náhledu nemají co dělat.
TRUNCATE konektor_drive_channels;
SQL

# ---------- 3. Prostředí (bez klíčů k vnějším systémům) ----------
echo "==> Skládám .env náhledu (bez API klíčů)…"
SECRET="$(openssl rand -hex 32)"
DB_HESLO="$(grep -oP '(?<=postgresql://'"${DB_UZIVATEL}"':)[^@]+' "${ZDROJ}/.env")"

cat > "${KLON}/.env" <<EOF
# Prostředí NÁHLEDU – generuje deploy/nahled.sh, needitovat ručně.
# Záměrně tu NEJSOU klíče k Freelu, Google Drive, POHODĚ, SMTP ani Anthropicu:
# náhled tak nemůže zapsat nic do vnějších systémů ani rozeslat e-maily.
DATABASE_URL=postgresql://${DB_UZIVATEL}:${DB_HESLO}@localhost:5432/${DB_NAHLED}
SECRET_KEY=${SECRET}
EOF
chown dan:dan "${KLON}/.env"
chmod 600 "${KLON}/.env"

# ---------- 4. Frontend ----------
echo "==> Instaluji npm závislosti a buildím frontend…"
sudo -u dan bash -c "cd '${KLON}/frontend' && npm install --silent && npm run build"

echo "==> Kopíruji frontend do ${WEB}…"
mkdir -p "${WEB}"
rm -rf "${WEB:?}"/*
cp -r "${KLON}/frontend/dist/." "${WEB}/"
chown -R caddy:caddy "${WEB}"

# ---------- 5. Služba backendu ----------
echo "==> Nasazuji službu ${SLUZBA} (port ${PORT})…"
cp "${KLON}/deploy/greensie-nahled.service" "/etc/systemd/system/${SLUZBA}.service"
systemctl daemon-reload
systemctl enable --quiet "${SLUZBA}"
systemctl restart "${SLUZBA}"

# ---------- 6. Caddy vhost s heslem na vstupu ----------
if [[ -f "${HESLO_SOUBOR}" ]]; then
	HESLO="$(cat "${HESLO_SOUBOR}")"
	echo "==> Používám dosavadní vstupní heslo (${HESLO_SOUBOR})."
else
	HESLO="$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-12)"
	printf '%s' "${HESLO}" > "${HESLO_SOUBOR}"
	chmod 600 "${HESLO_SOUBOR}"
	echo "==> Vygeneroval jsem nové vstupní heslo."
fi
HASH="$(caddy hash-password --plaintext "${HESLO}")"

cat > "${VHOST}" <<EOF
# NÁHLED větve pro spolupracovníky – generuje deploy/nahled.sh.
# Zrušení: sudo bash deploy/nahled-zrusit.sh
${DOMENA} {
	encode zstd gzip

	# Společné heslo na vstupu, ať náhled netrčí do internetu volně.
	# Uživatelské jméno: nahled
	basic_auth {
		nahled ${HASH}
	}

	handle_path /api/* {
		reverse_proxy localhost:${PORT}
	}

	handle {
		root * ${WEB}
		try_files {path} /index.html
		file_server
	}

	header {
		Strict-Transport-Security "max-age=31536000"
		X-Robots-Tag "noindex, nofollow"
	}
}
EOF

echo "==> Kontroluji a nasazuji konfiguraci Caddy…"
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload caddy

# ---------- 7. Kontrola ----------
echo "==> Kontrola…"
for i in $(seq 1 10); do
	if curl -fsS "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then break; fi
	sleep 1
done
STAV_BACKEND="$(curl -fsS "http://127.0.0.1:${PORT}/health" 2>/dev/null || echo 'NEODPOVÍDÁ')"

cat <<EOF

════════════════════════════════════════════════════════════
 NÁHLED BĚŽÍ

   Adresa:            https://${DOMENA}
   Uživatel:          nahled
   Vstupní heslo:     ${HESLO}

 Kolegové zadají tohle heslo a pak se přihlásí svým vlastním
 účtem do appky (účty jsou z kopie, hesla stejná jako v ostré).

   Větev:             ${VETEV}
   Databáze:          ${DB_NAHLED} (kopie, ostrá data nedotčená)
   Backend:           port ${PORT}, stav ${STAV_BACKEND}
   Ostrá appka:       https://app.greensie.cz — nedotčená

 Znovu přelít kopii dat:  sudo bash deploy/nahled.sh
 Zrušit náhled:           sudo bash deploy/nahled-zrusit.sh
════════════════════════════════════════════════════════════
EOF
