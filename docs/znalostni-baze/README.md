# Znalostní báze Greensie app

Kompletní návody na obsluhu appky a dokumentace serveru — **modul po modulu, políčko po políčku**.
Cílem je, aby kdokoli (uživatel, admin i budoucí vývojář) pochopil, k čemu každý prvek slouží
a jak appka funguje, bez pročítání kódu.

> **Stav:** kompletní — všechny moduly appky i serverová/provozní sekce. Tyhle soubory zároveň
> **napřímo pohánějí nápovědu v appce** (sekce *Manuál* a ikona „?"), takže úprava textu se po
> nasazení hned projeví uživatelům. Nové moduly se přidávají podle [šablony](_sablona-modulu.md).
> Zbývá doplnit screenshoty (zatím placeholdery `📸 SCREENSHOT`) a ověřit body označené
> v sekcích „Poznámky a úskalí".

---

## Jak je to organizované

Každý **modul** (= sekce v nabídce vlevo) má jeden soubor ve složce [`moduly/`](moduly/).
Uvnitř je návod rozdělený na dvě roviny:

- **🧑 Pro uživatele** — co která obrazovka, pole a tlačítko dělá a jak na běžné úkoly.
- **🛠 Pro admina / provoz** — práva, nastavení, napojení na okolní systémy, řešení potíží,
  a stručně „jak to funguje uvnitř" (datový model, API, klíčové soubory).

Serverová a provozní dokumentace (VPS, nasazení, konfigurace, práva) je ve složce
[`server/`](server/).

## Obsah

### Moduly (sekce appky)
- [x] [**Zákazníci a Obchodní případy (CRM)**](moduly/crm.md) — leady a klienti, pipeline s kanbanem, čísla OP/NAB, práva na záznamy, ARES
- [x] [**Přehled projektů**](moduly/prehled-projektu.md) — matice projektů z Freela, barvy termínů, buňky
- [x] [**Přehled financí**](moduly/prehled-financi.md) — faktury, napojení na Pohodu
- [x] [**Přehled změn**](moduly/prehled-zmen.md) — denní snímky stavu, net-rozdíl dvou fotek
- [x] [**Nabídkovač**](moduly/nabidkovac.md) — produktové linie, katalog, detail nabídky, PDF výstup
  - [x] [Peak shaving](moduly/nabidkovac-peak-shaving.md) (kalkulátor) — viz i technický popis [`docs/moduly/peak-shaving.md`](../moduly/peak-shaving.md)
  - [x] [PPA pro FVE](moduly/nabidkovac-ppa-fve.md) (kalkulátor) — viz i technický popis [`docs/moduly/ppa-fve.md`](../moduly/ppa-fve.md)
- [x] [**Konektor Raynet ↔ Google Disk**](moduly/konektor-raynet-gdrive.md) — viz i technický spec [`docs/moduly/raynet-gdrive-konektor-spec.md`](../moduly/raynet-gdrive-konektor-spec.md)
- [x] [**Logy**](moduly/logy.md)
- [x] [**Admin nastavení**](moduly/admin-nastaveni.md) — uživatelé, skupiny, práva
- [x] [**Přihlášení a změna hesla**](moduly/prihlaseni-zmena-hesla.md) — login, nucená změna, úvodní souhrn
- [x] [**Manuál (nápověda v appce)**](moduly/manual.md) — sekce *Manuál*, hledání, ikona „?", jak texty vznikají
- [x] [**Společné prvky**](moduly/spolecne-prvky.md) — layout, přepínač tématu, velikost textu

### Server a provoz
- [x] [**Prostředí a architektura**](server/architektura-prostredi.md) (VPS, FastAPI + React + PostgreSQL, Caddy)
- [x] [**Nasazení nové verze**](server/nasazeni.md) (`deploy/update.sh`, Caddy, systemd)
- [x] [**Konfigurace**](server/konfigurace.md) — databáze, `.env`, e-maily (SMTP)
- [x] [**Práva, skupiny a role**](server/prava-a-skupiny.md)

---

## Výstupní vrstvy z jednoho zdroje

Tyhle Markdown soubory jsou **zdroj pravdy**. Vystupují ve dvou formách:

1. **Znalostní báze v repu (tyto soubory)** — hotové. Čte a udržuje se v editoru / na GitHubu,
   slouží zároveň jako referenční poznámky při vývoji.
2. **Nápověda přímo v appce** — hotové. Sekce **Manuál** vykresluje tytéž soubory jako HTML,
   umí v nich hledat a ikona **„?"** v horní liště otevře návod k té stránce, na které uživatel
   právě je. Viz [návod k modulu Manuál](moduly/manual.md).
   ⚠️ **Nová stránka se v appce sama neobjeví** — musí se přidat do seznamu `STRANKY`
   v `backend/app/manual/routes.py`.
3. **Screenshoty** v návodech — zbývá doplnit (značky `📸 SCREENSHOT` jsou v textech připravené).

Aby to šlo, drží se obsah v čistém Markdownu a screenshoty se odkazují přes značky (viz níže).

## Konvence psaní

- **Jeden soubor na modul**, název v kebab-case podle sekce (`prehled-projektu.md`).
- Piš tak, aby to pochopil i **nováček** — vysvětluj i „samozřejmosti".
- U každého ovládacího prvku uveď: **co to je → co to udělá → kdo to vidí** (podle práv).
- **Screenshoty** označuj značkou, ať se dají později hromadně doplnit:
  `> 📸 SCREENSHOT: <popis co má být na obrázku>`
- Odkazuj na **konkrétní soubory v kódu** (`frontend/src/pages/…`, `backend/app/…`), ať je návod dohledatelný.
- Sekci **„Poznámky a úskalí"** drž aktuální — sem patří to, co je nezřejmé, modelové nebo k ověření.
- Rozlišuj **role**: většina prvků je vidět jen s určitým právem (nejčastěji `editace`) — vždy to uveď.

## Vztah k `docs/moduly/`

Složka [`docs/moduly/`](../moduly/) obsahuje **technické implementační souhrny** (vzorce, datové toky,
rozhodnutí) — píší se pro vývojáře/údržbu. Tahle znalostní báze je **návodová** (jak to ovládat a
funguje z pohledu obsluhy). Kde se to hodí, na technický popis jen odkazujeme, abychom nezdvojovali.
