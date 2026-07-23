# Znalostní báze Greensie app

Kompletní návody na obsluhu appky a dokumentace serveru — **modul po modulu, políčko po políčku**.
Cílem je, aby kdokoli (uživatel, admin i budoucí vývojář) pochopil, k čemu každý prvek slouží
a jak appka funguje, bez pročítání kódu.

> **Stav:** rozjeté (pilot). Hotový je modul [Přehled projektů](moduly/prehled-projektu.md).
> Ostatní moduly se doplňují podle stejné [šablony](_sablona-modulu.md).

---

## Jak je to organizované

Každý **modul** (= dlaždice v rozcestníku appky) má jeden soubor ve složce [`moduly/`](moduly/).
Uvnitř je návod rozdělený na dvě roviny:

- **🧑 Pro uživatele** — co která obrazovka, pole a tlačítko dělá a jak na běžné úkoly.
- **🛠 Pro admina / provoz** — práva, nastavení, napojení na okolní systémy, řešení potíží,
  a stručně „jak to funguje uvnitř" (datový model, API, klíčové soubory).

Serverová a provozní dokumentace (VPS, nasazení, databáze, e-maily, práva) bude ve složce
`server/` — zatím se připravuje.

## Obsah

### Moduly (dlaždice appky)
- [x] [**Přehled projektů**](moduly/prehled-projektu.md) — matice projektů z Freela, barvy termínů, buňky
- [ ] Přehled financí — faktury, napojení na Pohodu
- [ ] Přehled změn — denní snímky stavu, porovnání
- [ ] Nabídkovač — katalog, sekce, detail nabídky, PDF výstup
  - [ ] Peak shaving (kalkulátor) — viz i technický popis [`docs/moduly/peak-shaving.md`](../moduly/peak-shaving.md)
  - [ ] PPA pro FVE (kalkulátor) — viz i technický popis [`docs/moduly/ppa-fve.md`](../moduly/ppa-fve.md)
- [ ] Konektor Raynet ↔ Google Drive — viz i technický spec [`docs/moduly/raynet-gdrive-konektor-spec.md`](../moduly/raynet-gdrive-konektor-spec.md)
- [ ] Logy
- [ ] Admin nastavení — uživatelé, skupiny, práva
- [ ] Přihlášení a změna hesla
- [ ] Společné prvky — layout, přepínač tématu, velikost textu

### Server a provoz (připravuje se)
- [ ] Prostředí a architektura (VPS, FastAPI + React + PostgreSQL)
- [ ] Nasazení nové verze (`deploy/update.sh`, Caddy, systemd)
- [ ] Databáze a `.env`
- [ ] E-maily (SMTP)
- [ ] Práva, skupiny a role

---

## Tři výstupní vrstvy z jednoho zdroje

Tyhle Markdown soubory jsou **zdroj pravdy**. Počítáme s tím, že z nich vzniknou další formy:

1. **Znalostní báze v repu (tyto soubory)** — čte a udržuje se v editoru / na GitHubu.
   Slouží zároveň jako referenční poznámky při vývoji.
2. **Nápověda přímo v appce** — návody se zobrazí v prohlížeči u ruky uživatelů (plánováno).
3. **Interaktivní vyhledávatelný dokument (HTML) se screenshoty** — forma se doladí (plánováno).

Aby to šlo, drží se obsah v čistém Markdownu a screenshoty se odkazují přes značky (viz níže).

## Konvence psaní

- **Jeden soubor na modul**, název v kebab-case podle dlaždice (`prehled-projektu.md`).
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
