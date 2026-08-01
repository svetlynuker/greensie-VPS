#!/usr/bin/env bash
# ============================================================
#  Greensie – NÁHLED větve pro spolupracovníky
#  Spouštět jako root:
#      sudo bash deploy/nahled.sh                 # vše (kód, data, web, adresa)
#      sudo bash deploy/nahled.sh nazev-vetve     # náhled jiné větve
#      sudo bash deploy/nahled.sh --jen-adresa    # jen vypsat adresu (rychlé)
#
#  Postaví samostatnou instanci appky, na kterou se dá poslat odkaz:
#
#    https://nahled.167-235-254-188.sslip.io
#      ↑ HTTPS od Caddy, bez vstupního hesla — chrání se přihlášením
#        do appky, stejně jako ostrá appka na app.greensie.cz
#
#  Náhled je od ostré appky oddělený ve všem, co může škodit:
#    • vlastní KOPIE databáze (greensie_nahled) — editace se do ostrých dat
#      nepropíšou
#    • BEZ klíčů k Freelu, Google Drive, POHODĚ, SMTP a Anthropicu — nemůže
#      tedy nic zapsat do vnějších systémů ani rozeslat e-maily
#    • vypnutá automatická synchronizace a vyprázdněná fronta úloh konektoru
#    • vlastní SECRET_KEY — přihlášení z náhledu neplatí v ostré appce
#
#  Opakované spuštění je bezpečné: kód i frontend se aktualizují a databáze se
#  přelije znovu z ostré (tedy zahodí, co kdo v náhledu naklikal).
#
#  Zrušení:  sudo bash deploy/nahled-zrusit.sh
# ============================================================
set -euo pipefail

# Skript aktualizuje klon, ze kterého se nejčastěji sám spouští. Bash ale čte
# soubor postupně za běhu, takže by se sám pod rukama přepsal a mohl skončit
# uprostřed. Proto se nejdřív odkopírujeme mimo a pokračujeme z kopie.
if [[ "${GREENSIE_NAHLED_KOPIE:-}" != "1" ]]; then
	KOPIE="$(mktemp /tmp/greensie-nahled-XXXXXX.sh)"
	cp "${BASH_SOURCE[0]}" "${KOPIE}"
	export GREENSIE_NAHLED_KOPIE=1
	exec bash "${KOPIE}" "$@"
fi
trap 'rm -f "$0"' EXIT   # jsme ta kopie v /tmp – po sobě uklidíme

ZDROJ="/home/dan/projects/greensie-app"          # ostrá instalace (odkud se klonuje a bere venv)
KLON="/home/dan/projects/greensie-nahled"        # kód náhledu
WEB="/var/www/greensie-nahled"                   # statický frontend náhledu
SLUZBA="greensie-nahled"
PORT="8001"
DB_ZDROJ="greensie"
DB_NAHLED="greensie_nahled"
DB_UZIVATEL="greensie_user"
DOMENA="nahled.167-235-254-188.sslip.io"
VHOST="/etc/caddy/sites/greensie-nahled.caddy"

# Výchozí větev: ta, na které klon právě stojí — opakované spuštění tak
# náhled obnoví, místo aby ho přehodilo jinam. Když klon ještě není, main.
VETEV="$(git -C "${KLON}" branch --show-current 2>/dev/null || true)"
VETEV="${VETEV:-main}"
JEN_ADRESA=0
for ARG in "$@"; do
	case "${ARG}" in
		--jen-adresa) JEN_ADRESA=1 ;;
		-*) echo "Neznámý přepínač: ${ARG}" >&2; exit 1 ;;
		*) VETEV="${ARG}" ;;
	esac
done

if [[ $EUID -ne 0 ]]; then
	echo "Spusť jako root:  sudo bash deploy/nahled.sh" >&2
	exit 1
fi

if [[ ${JEN_ADRESA} -eq 1 ]]; then
	echo "==> Režim --jen-adresa: přeskakuji kód, databázi i build."
else
	echo "==> Náhled větve: ${VETEV}"
fi

if [[ ${JEN_ADRESA} -eq 0 ]]; then
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
	systemctl stop "${SLUZBA}" 2>/dev/null || true   # ať kopii nedrží otevřené spojení
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
	DB_HESLO="$(grep -oP "(?<=postgresql://${DB_UZIVATEL}:)[^@]+" "${ZDROJ}/.env")"

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
fi

# ---------- 6. Caddy vhost ----------

cat > "${VHOST}" <<EOF
# NÁHLED větve pro spolupracovníky – generuje deploy/nahled.sh.
# Zrušení: sudo bash deploy/nahled-zrusit.sh
${DOMENA} {
	encode zstd gzip

	# POZOR – vstupní heslo tady BÝT NESMÍ. Appka posílá ke každému volání API
	# vlastní hlavičku "Authorization: Bearer <token>", která by údaje vstupního
	# hesla ve stejné hlavičce přepsala. Caddy by je nedostal, vrátil 401 a
	# prohlížeč by uživateli otevřel přihlašovací pop-up, ze kterého se nelze
	# dostat dál (žádné údaje appky do něj nepatří). API si přihlášení hlídá
	# samo tokenem, stejně jako v ostré appce.
	handle_path /api/* {
		reverse_proxy localhost:${PORT}
	}

	# Statický frontend BEZ vstupního hesla — vědomé rozhodnutí z 1. 8. 2026,
	# ne opomenutí. Dvě hesla za sebou (vstupní pop-up + přihlášení do appky)
	# se ukázala jako překážka: pop-up chce jméno i heslo a člověk, který to
	# neví, se nedostane dál. Data chrání přihlášení do appky stejně jako
	# v ostré appce; veřejně je vidět jen přihlašovací obrazovka.
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
for _ in $(seq 1 10); do
	if curl -fsS "http://127.0.0.1:${PORT}/health" > /dev/null 2>&1; then break; fi
	sleep 1
done
STAV_BACKEND="$(curl -fsS "http://127.0.0.1:${PORT}/health" 2>/dev/null || echo 'NEODPOVÍDÁ')"
# API musí projít i BEZ vstupního hesla (jinak by se appka nepřihlásila).
STAV_API="$(curl -fsS "https://${DOMENA}/api/health" 2>/dev/null || echo 'NEPROCHÁZÍ — appka se nepřihlásí!')"
# Frontend musí projít rovnou (vstupní heslo tu záměrně není).
KOD_WEB="$(curl -s -o /dev/null -w '%{http_code}' "https://${DOMENA}/" 2>/dev/null || echo '???')"

cat <<EOF

════════════════════════════════════════════════════════════
 NÁHLED BĚŽÍ

   Adresa:            https://${DOMENA}

 Odkaz stačí poslat — žádné vstupní heslo. Kolegové se rovnou přihlásí
 svým vlastním účtem do appky (účty i hesla jsou z kopie, tedy stejné
 jako v ostré appce).

   Větev:             ${VETEV}
   Databáze:          ${DB_NAHLED} (kopie, ostrá data nedotčená)
   Backend:           port ${PORT}, stav ${STAV_BACKEND}
   API přes web:      ${STAV_API}
   Frontend:          HTTP ${KOD_WEB}  (200 = správně, bez hesla)
   Ostrá appka:       https://app.greensie.cz — nedotčená

 Znovu přelít kopii dat:  sudo bash deploy/nahled.sh
 Jen vypsat adresu:       sudo bash deploy/nahled.sh --jen-adresa
 Zrušit náhled:           sudo bash deploy/nahled-zrusit.sh
════════════════════════════════════════════════════════════
EOF
