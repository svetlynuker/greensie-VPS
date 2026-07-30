# Manuál (nápověda v appce)

> **Sekce v nabídce:** `manual` (skupina *Nápověda*) · **Adresa (routa):** `/manual`
> **Kdo smí otevřít:** **každý přihlášený** — nepotřebuje žádné právo
> **Kód:** frontend `frontend/src/pages/Manual.jsx`, `frontend/src/styles/manual.css`,
> backend `backend/app/manual/routes.py` · **Obsah:** `docs/znalostni-baze/`

Manuál je **tahle znalostní báze zobrazená přímo v appce**. Uživatel nemusí nikam na GitHub ani
otevírat soubory — návody má u ruky v prohlížeči, může v nich hledat a z každé stránky se přes
ikonu **„?"** dostane přímo na návod k tomu, co má právě na obrazovce.

> 📸 SCREENSHOT: celá obrazovka Manuálu — vlevo hledání a seznam stránek po kategoriích, vpravo text návodu

---

## 🧑 Pro uživatele

### K čemu to slouží

Odpovídá na „co je tohle políčko" a „jak se dělá tamto" bez toho, aby se člověk musel někoho ptát.
Obsahuje **návod ke každému modulu appky** (políčko po políčku, včetně toho, kdo co vidí podle práv)
a navíc **serverovou/provozní sekci** pro admina.

### Jak se do Manuálu dostanu

Třemi cestami:

1. **Nabídka vlevo** → skupina *Nápověda* → **Manuál**. Otevře se první stránka (Úvod).
2. **Ikona „?" v horní liště** → otevře **návod k té stránce, na které právě jsi** (ne obecný začátek).
   Na samotném Manuálu se ikona neukazuje.
3. **Uživatelské menu vpravo nahoře** → *Manuál*.

### Rozvržení obrazovky

Obrazovka je rozdělená na dva pruhy:

- **Vlevo (panel)** — odkaz **← Rozcestník**, pod ním **hledání** a pak **seznam všech stránek**
  rozdělený do kategorií: *Úvod*, *Moduly*, *Server a provoz*.
- **Vpravo (obsah)** — text vybraného návodu (nadpisy, tabulky, ukázky kódu). Při přepnutí stránky
  se obsah odroluje zpátky nahoru.

### Ovládací prvky — políčko po políčku

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Rozcestník** | vlevo nahoře | Zpátky na úvodní stránku appky | vše |
| **Hledat v manuálu…** | vlevo | Filtruje seznam stránek na ty, kde se výraz vyskytuje (v názvu **nebo v textu**), a v otevřené stránce **žlutě podbarví nalezená slova**. Pole je po otevření Manuálu hned aktivní, dá se tedy psát bez klikání. | vše |
| **Informace pod hledáním** | vlevo | *„Nalezeno na N stránkách"*, nebo *„Nic nenalezeno"* | vše |
| **Název stránky v seznamu** | vlevo | Otevře návod vpravo; aktivní stránka je zvýrazněná | vše |
| **Odkazy uvnitř textu** | vpravo | Odkaz na jiný návod se otevře **rovnou v Manuálu**; odkaz mimo znalostní bázi se otevře v **nové kartě** | vše |

Hledání **nekouká na diakritiku ani velikost písmen** — „prehled", „Přehled" i „PREHLED" najdou totéž.
Uvnitř ukázek kódu se hledaný výraz nepodbarvuje (aby se nerozbily příkazy k opsání).

### Jak na…

- **Najít nápovědu k tomu, co mám na obrazovce:** ikona **„?"** v horní liště. Otevře přímo správnou
  stránku (např. z Peak shavingu návod k peak shavingu, ne obecný o Nabídkovači).
- **Najít, kde se něco nastavuje:** otevři Manuál a napiš pojem do hledání (např. „RK", „záruka",
  „Pohoda"). Seznam vlevo se zúží na stránky, kde to je.
- **Poslat kolegovi odkaz na konkrétní návod:** otevři stránku a zkopíruj adresu z prohlížeče —
  má v sobě `?stranka=<id>` (např. `/manual?stranka=nabidkovac-peak-shaving`), takže se otevře
  přímo ta stránka.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí

Manuál **žádné právo nevyžaduje** (`vzdy: true` v `frontend/src/navigace.js`, na backendu jen
`get_current_user`) — stejně jako Rozcestník ho vidí každý přihlášený. Obsah se **nefiltruje podle
práv**: i uživatel bez práva na modul si přečte jeho návod včetně serverové sekce. Je to záměr
(návody nejsou tajné), ale je dobré o tom vědět.

Kdo nemá právo na žádný modul, je po přihlášení poslán právě do Manuálu
(`prvniDostupnaCesta` v `navigace.js`).

### Kde se bere obsah

Backend čte **Markdown soubory přímo z repa** — `docs/znalostni-baze/` (cesta se odvozuje od umístění
`routes.py`, ne z konfigurace). **Zdroj pravdy je tedy jeden**: tentýž soubor čte GitHub i appka.
Soubory se čtou **při každém požadavku**, není potřeba nic buildit ani restartovat backend — po
`git pull` na serveru se změna projeví hned.

**Které stránky se zobrazí, určuje pevný seznam `STRANKY`** v `backend/app/manual/routes.py`.
Každá položka je trojice `(id, cesta k souboru, kategorie)` — seznam určuje i **pořadí** v panelu.

> ⚠️ **Nový návod se v appce sám neobjeví.** Přidání souboru do `docs/znalostni-baze/moduly/`
> nestačí — musí se dopsat do `STRANKY`. Naopak soubor, který v seznamu je, ale na disku chybí,
> se **tiše přeskočí** (žádná chyba se nikde neukáže).

Titulek stránky v panelu se bere z **prvního nadpisu `#`** v souboru (proto má každý návod začínat
`# Název`), kategorie z třetího prvku trojice.

### Kontextová nápověda „?"

Mapování „adresa v appce → stránka manuálu" je ve funkci **`strankaManualu`**
(`frontend/src/navigace.js`). Ikonu vykresluje `Layout.jsx` a na `/manual` se skryje.

| Adresa | Stránka manuálu |
|---|---|
| `/projekty` | `prehled-projektu` |
| `/finance` | `prehled-financi` |
| `/zmeny` | `prehled-zmen` |
| `/nabidkovac/peak_shaving` | `nabidkovac-peak-shaving` |
| `/nabidkovac/ppa` | `nabidkovac-ppa-fve` |
| `/nabidkovac` (ostatní) | `nabidkovac` |
| `/admin` | `admin-nastaveni` |
| `/logy` | `logy` |
| `/konektor` | `konektor-raynet-gdrive` |
| cokoli dalšího | `uvod` |

> ⚠️ **Nový modul si mapování nepřidá sám.** Bez řádku ve `strankaManualu` pošle „?" uživatele na
> Úvod. Platí to i pro stránky, které návod mají (např. Katalog technologií je popsaný v návodu
> Nabídkovače, ale vlastní řádek nemá → padá na `nabidkovac`).

### Jak to funguje uvnitř (stručně technicky)

- **Datový model:** žádný — Manuál **nemá v databázi nic**. Obsah jsou soubory na disku.
- **API:** `GET /manual` (právo: jen přihlášení) vrátí **všechny stránky najednou** jako
  `{ stranky: [{ id, titulek, kategorie, html, text }] }`. `html` je vykreslený Markdown,
  `text` je z něj odstrojený čistý text pro hledání. Frontend si celý balík **jednou načte a drží
  v paměti** — přepínání stránek a hledání pak běží bez dalších volání serveru.
- **Vykreslení Markdownu:** knihovna `markdown` s rozšířeními `tables`, `fenced_code`, `sane_lists`,
  `attr_list`, `toc`. Tabulky a bloky kódu z návodů se tedy zobrazí správně.
- **Vkládání HTML:** frontend výsledek vkládá do stránky přes `innerHTML`. Je to **vědomé** —
  obsah je vlastní (z repa), ne uživatelský vstup.
- **Zvýrazňování hledaného** probíhá až nad vykresleným HTML, obalením textových uzlů do `<mark>`
  (přeskakuje `code`, `pre`, `script`, `style`).
- **Klíčové soubory:** `backend/app/manual/routes.py`, `frontend/src/pages/Manual.jsx`,
  `frontend/src/styles/manual.css`, `frontend/src/navigace.js` (`strankaManualu`),
  `frontend/src/components/Layout.jsx` (ikona „?").

### Časté potíže / co dělat, když…

| Symptom | Příčina | Řešení |
|---|---|---|
| Manuál hlásí **„Chyba: Zdroj manuálu (docs/znalostni-baze) nebyl nalezen."** | Backend nevidí složku `docs/znalostni-baze` — na serveru chybí (nedotažený `git pull`) nebo se kód nasadil bez `docs/` | Na serveru `git pull` v `~/projects/greensie-app` a ověřit, že složka existuje |
| **Nový návod v seznamu není** | Není v `STRANKY` v `backend/app/manual/routes.py`, nebo tam je jiná cesta k souboru | Dopsat/opravit položku a restartovat backend (`sudo systemctl restart greensie-backend`) |
| **Stránka je v seznamu, ale prázdná / stará** | Soubor je prázdný, nebo prohlížeč drží starý frontend z cache | Tvrdý refresh `Ctrl+Shift+R` |
| **Ikona „?" vede na Úvod** | Adresa modulu není ve `strankaManualu` | Dopsat řádek do `frontend/src/navigace.js` |
| **Titulek v panelu je nesmyslný (id místo názvu)** | Soubor nemá na začátku nadpis `#` | Doplnit `# Název` jako první řádek |
| **Odkaz uvnitř textu se otevřel v nové kartě, i když míří na jiný návod** | Basename souboru neodpovídá žádnému `id` ani položce v `MAPA_ODKAZU` v `Manual.jsx` | Opravit odkaz, nebo doplnit mapování |

---

## Poznámky a úskalí (k ověření / nezřejmé)

- **Tři místa při přidání modulu.** Nový modul znamená: (1) soubor v `docs/znalostni-baze/moduly/`,
  (2) položka v `STRANKY` (`backend/app/manual/routes.py`), (3) řádek ve `strankaManualu`
  (`frontend/src/navigace.js`) + řádek v [obsahu README](../README.md). Nic z toho se nedoplní samo.
- **Chybějící soubor se tiše přeskočí** (`if not cesta.exists(): continue`) — přejmenovaný soubor
  tedy z Manuálu jen zmizí, aniž by to někde zahlásil.
- **Celý manuál se posílá jedním požadavkem.** S rostoucím počtem návodů roste i objem dat
  (dnes ~16 stránek, řádově stovky kB HTML). Zatím to nevadí; kdyby manuál výrazně narostl,
  bude potřeba stránky načítat jednotlivě nebo přidat cache na serveru.
- **Obsah se nefiltruje podle práv** — návod k Adminu i serverová sekce jsou čitelné pro každého
  přihlášeného. Tajemství (hesla, klíče) se proto do znalostní báze nepíšou.
- **Screenshoty ještě nejsou.** Značky `📸 SCREENSHOT: …` se v Manuálu zobrazí jako obyčejný text
  odstavce — dokud se obrázky nedoplní, uživatel tam vidí popis toho, co na obrázku bude.
- **Vyhledávání je „obsahuje podřetězec"**, ne fulltext se skloňováním — „nabídky" nenajde „nabídka".

## Odkazy

- Kód: `backend/app/manual/routes.py`, `frontend/src/pages/Manual.jsx`,
  `frontend/src/navigace.js`, `frontend/src/components/Layout.jsx`
- Jak se návody píšou a jak je organizovaná znalostní báze: [`README.md`](../README.md)
  (šablona pro nový modul je v repu: `docs/znalostni-baze/_sablona-modulu.md`)
- Rámec appky (nabídka vlevo, horní lišta, uživatelské menu): [`spolecne-prvky.md`](spolecne-prvky.md)
- Nasazení změn na produkci (aby se nový text dostal k uživatelům):
  [`server/nasazeni.md`](../server/nasazeni.md)
