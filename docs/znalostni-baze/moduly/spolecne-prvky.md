# Společné prvky UI

> **Kde:** napříč celou appkou (horní lišta na každé přihlášené obrazovce, dlaždice na rozcestníku)
> **Kód:** frontend `frontend/src/components/Layout.jsx`, `ThemeToggle.jsx`, `CvdToggle.jsx`, `VelikostTextu.jsx`, `Tile.jsx`, `Ikona.jsx`, `theme.js`, `velikost.js`, `api.js`; backend `backend/app/nastaveni/`

Tenhle „modul" není samostatná stránka, ale **prvky, které se opakují všude**: horní lišta
(hlavička) s přepínači vzhledu, dlaždice na rozcestníku a uživatelská nastavení, která se ukládají
do profilu a přenášejí mezi zařízeními. Popisujeme je jednou tady, ať se to v ostatních modulech
nemusí opakovat.

> 📸 SCREENSHOT: horní lišta appky (logo Greensie, přepínač textu, měsíc/slunce, oko, jméno, Odhlásit)

---

## 🧑 Pro uživatele

### K čemu to slouží
Ať jsi v kterémkoli modulu, nahoře máš vždy stejnou lištu, ze které si přepneš **tmavý/světlý
režim**, **velikost textu** a **kompenzaci barev** pro červeno-zelenou vadu zraku, a odkud se
**odhlásíš**. Rozcestník (hlavní stránka po přihlášení) je mřížka **dlaždic** — jedna dlaždice =
jeden modul.

### Horní lišta (hlavička)
Je na každé přihlášené obrazovce a vypadá shora dolů (resp. zleva doprava) takto:

1. **Logo Greensie** (barevná značka + nápis „Greensie") — vlevo.
2. **Mezera** — odtlačí zbytek doprava.
3. **Text:** — rozbalovací výběr velikosti písma (Malé / Střední / Velké).
4. **Ikona měsíc/slunce** — přepínač tmavého a světlého režimu.
5. **Ikona oka** — zapnutí/vypnutí kompenzace červeno-zelené barevné vady.
6. **Jméno přihlášeného** — kdo je přihlášený.
7. **Odhlásit** — odhlášení (smaže přihlašovací token a vrátí na přihlašovací obrazovku).

Na **přihlašovací obrazovce** (ještě před loginem) jsou vpravo nahoře jen dva přepínače — režim
(měsíc/slunce) a oko; výběr velikosti textu a jméno/Odhlásit tam nejsou.

### Jak přepnout tmavý / světlý režim
Klikni na ikonu **měsíce** (přepne na tmavý) nebo **slunce** (přepne na světlý) v horní liště.
Přepnutí je okamžité a platí pro celou appku. Volba se uloží do tvého profilu, takže tě „potká"
i na jiném počítači nebo telefonu po přihlášení.

### Jak zvětšit / zmenšit text
V horní liště je výběr **Text:** se třemi stupni:

| Volba | Efekt |
|---|---|
| **Malé** | výchozí velikost (základ 14 px) |
| **Střední** | zvětší celou appku proporčně (přibližně 16/14) |
| **Velké** | zvětší celou appku proporčně (přibližně 18/14) |

Nezvětšuje se jen písmo, ale **celé rozhraní** (zoom), takže se nic nerozbije. I tato volba se ukládá
do profilu.

### Nastavení se přenáší mezi zařízeními
Režim (tmavý/světlý), velikost textu a kompenzace barev se **ukládají do tvého profilu na serveru**.
Když se přihlásíš na jiném zařízení, appka si je po přihlášení stáhne a nastaví. V samotném
prohlížeči se drží i lokální kopie (kvůli rychlosti a aby při startu neproblikla špatná varianta),
ale „pravdou" je to, co je uloženo v profilu.

### Dlaždice na rozcestníku
Rozcestník je mřížka dlaždic; **jedna dlaždice = jeden modul** (Přehled projektů, Přehled financí,
Přehled změn, Nabídkovač, Admin nastavení, Logy, Konektor Raynet ↔ Disk). Každá dlaždice má ikonu,
název a krátký podtitulek.

- **Dostupná dlaždice** má vpravo nahoře **šipku** a po kliknutí otevře daný modul.
- **Zamčená dlaždice** (nemáš na ni právo) má místo šipky **odznak „zamčeno" s ikonou zámku**, je
  zešedlá a po najetí ukáže popisek *„Zatím nedostupné – nemáš oprávnění tuto sekci otevřít"*.
  Klik na ni **otevře instruktážní video** (na nový panel), ne modul.
- Stejně (proklikem na video) se chová i **dlaždice, která je teprve rozpracovaná** / bez cílové
  stránky.
- Některé moduly se ti bez práva **vůbec nezobrazí** (ne jen zamknou) — viz „Pro admina".

> 📸 SCREENSHOT: rozcestník s několika dlaždicemi, z toho jedna zamčená (odznak „zamčeno")

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = každý přihlášený · **(login)** = i na přihlašovací obrazovce ·
**(dle práv)** = podle oprávnění uživatele.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **Logo Greensie** | vlevo v liště | Značka appky (bez akce) | vše |
| **Text:** (výběr velikosti) | horní lišta | Malé / Střední / Velké — proporčně zvětší/zmenší celé rozhraní; uloží se do profilu | vše |
| **Ikona měsíc / slunce** | horní lišta | Přepne tmavý ↔ světlý režim; uloží se do profilu | vše, i na loginu |
| **Ikona oka** | horní lišta | Zapne/vypne kompenzaci červeno-zelené barevné vady; uloží se do profilu | vše, i na loginu |
| **Jméno uživatele** | horní lišta | Ukazuje, kdo je přihlášený (bez akce) | vše (po přihlášení) |
| **Odhlásit** | horní lišta | Smaže token a přesměruje na přihlašovací obrazovku | vše (po přihlášení) |
| **Dlaždice (dostupná)** | rozcestník | Otevře příslušný modul | dle práv |
| **Dlaždice (zamčená)** | rozcestník | Odznak „zamčeno" + zámek; klik otevře instruktážní video | dle práv |
| **Šipka na dlaždici** | roh dlaždice | Náznak, že dlaždice vede do modulu (bez samostatné akce) | dle práv |

### Kompenzace barev (ikona oka)
Pro lidi s červeno-zelenou vadou zraku (deuteranopie/protanopie). Po zapnutí appka vymění stavové
barvy a barvy grafů za paletu čitelnou bez rozlišení červená/zelená (modrá = v pořádku, závažnost
se pozná jasem). Layout se přitom nemění. Volba se ukládá do profilu.

### Jak na…
- **Přepnout na tmavý režim:** klikni na ikonu měsíce v liště.
- **Zvětšit písmo:** v liště u **Text:** vyber Střední nebo Velké.
- **Přenést svůj vzhled na jiné zařízení:** nic navíc — stačí se tam přihlásit, nastavení se stáhne
  z profilu automaticky.
- **Odhlásit se:** tlačítko **Odhlásit** vpravo v liště.

---

## 🛠 Pro admina / provoz

### Kde se ukládají uživatelská nastavení
V tabulce **`uzivatelska_nastaveni`** (`backend/app/nastaveni/models.py`, třída
`UzivatelskeNastaveni`). Model je jednoduchý **klíč → JSON hodnota**, jeden řádek na dvojici
(uživatel, klíč):

| Sloupec | Typ | Význam |
|---|---|---|
| `id` | int, PK | identifikátor řádku |
| `uzivatel_id` | int, FK → `uzivatele.id` (ON DELETE CASCADE) | čí nastavení |
| `klic` | string | název nastavení (viz níže) |
| `hodnota` | JSON | libovolná JSON hodnota (řetězec, objekt, seznam…) |

Unikátní omezení **`uq_nastaveni_uzivatel_klic`** na dvojici (`uzivatel_id`, `klic`) — každý klíč
existuje na uživatele max. jednou, proto se ukládá „upsertem" (najdi řádek, nebo založ nový, pak
přepiš hodnotu).

### Používané klíče
| Klíč | Hodnota | Ukládá | Čte |
|---|---|---|---|
| `tema` | `"light"` / `"dark"` | `ThemeToggle.jsx` | `Login.jsx` (po přihlášení) |
| `velikost` | `"male"` / `"stredni"` / `"velke"` | `VelikostTextu.jsx` | `Login.jsx` |
| `cvd` | `"on"` / `"off"` (kompenzace barev) | `CvdToggle.jsx` | `Login.jsx` |
| `pohled1_skryte` | `{ faze: [...], ukoly: [...] }` | Přehled projektů | Přehled projektů |
| `pohled1_poradi` | `{ projekty, faze, ukoly }` | Přehled projektů | Přehled projektů |

Klíče `pohled1_skryte` a `pohled1_poradi` patří modulu Přehled projektů (osobní skrytí a pořadí) —
sdílí jen tenhle společný úložný mechanismus. Model je otevřený: **libovolný modul si sem může uložit
vlastní klíč** bez změny schématu.

### Jak se vzhled synchronizuje po loginu
- Při **startu appky** (`frontend/src/main.jsx`) se zavolá `initTheme()` a `initVelikost()`, které
  načtou hodnoty z **localStorage** a hned je aplikují na `<html>` (atribut `data-theme`,
  případně `data-cvd`, a `style.zoom`). localStorage tu slouží jako **rychlá lokální cache**, aby
  při startu **neproblikla** špatná varianta vzhledu.
- Po **úspěšném přihlášení** (`frontend/src/pages/Login.jsx`, funkce `synchronizujVzhled`) appka
  zavolá `GET /nastaveni`, a pokud v profilu najde `tema` / `velikost` / `cvd`, nastaví je
  (`setTheme`, `setVelikost`, `setCvd`) — tím se profil ze serveru „vyhraje" nad lokální cache.
  Když stažení selže, appka pokračuje s lokálním nastavením (vzhled není kritický).
- Při **každé změně** přepínače se nová hodnota uloží do localStorage **i** do DB
  (`ulozNastaveni(klic, hodnota)` → `PUT /nastaveni/{klic}`). Do DB se ukládá **jen když je uživatel
  přihlášený** (na přihlašovací obrazovce ještě není token).

### Datový model (technicky)
- **Aplikace vzhledu na DOM** (`frontend/src/theme.js`, `velikost.js`):
  - `data-theme="light|dark"` na `<html>` řídí barevné schéma (CSS proměnné v `styles/global.css`).
  - `data-cvd="on"` na `<html>` přepíná paletu pro barvoslepé (jinak se atribut odebere).
  - `document.documentElement.style.zoom` řídí velikost (1 / 16⁄14 / 18⁄14).
  - localStorage klíče: `greensie_theme`, `greensie_cvd`, `greensie_velikost` (pozor: **jiné názvy**
    než klíče v DB `tema` / `cvd` / `velikost`).
- **Dlaždice a práva** (`backend/app/auth/permissions.py`): katalog `DLAZDICE` (7 modulů) a `PRAVA`.
  `dlazdice_pro(user)` vrací všechny dlaždice s příznakem `muze_otevrit` (klíč práva = klíč dlaždice).
  Supersprávce (`je_admin`) má všechna práva; ostatní mají práva ze skupiny + individuální výjimky
  (`extra_prava`). Vrací se v `GET /auth/me` v poli `dlazdice`.

### API
| Metoda + cesta | K čemu | Kdo |
|---|---|---|
| `GET /nastaveni` | Vrátí všechna nastavení přihlášeného uživatele jako `{klíč: hodnota}` | přihlášený |
| `PUT /nastaveni/{klic}` | Uloží (upsert) jedno nastavení; tělo `{ "hodnota": <cokoli> }` | přihlášený |

Obě vyžadují přihlášení (`Depends(get_current_user)`); pracují **jen s vlastními** záznamy uživatele.
Prefix routeru je `/nastaveni` (`backend/app/nastaveni/routes.py`).

### Práva — kdo co vidí a smí
- **Přepínače vzhledu a velikosti** vidí a smí měnit **každý** (i nepřihlášený na loginu, tam ale bez
  uložení do DB).
- **Dlaždice** vidí každý přihlášený, ale otevření řídí právo se stejným klíčem
  (`muze_otevrit`). Bez práva je dlaždice **zamčená** (klik → video), nebo se u vybraných modulů
  **vůbec nezobrazí** (frontend `SKRYT_BEZ_PRAVA` v `Rozcestnik.jsx`: `finance`, `nabidkovac`,
  `logy`, `konektor`).
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky).

### Klíčové soubory
- **Frontend:** `components/Layout.jsx` (hlavička), `ThemeToggle.jsx`, `CvdToggle.jsx`,
  `VelikostTextu.jsx`, `Tile.jsx`, `Ikona.jsx` (sdílené SVG ikony), `theme.js`, `velikost.js`,
  `api.js` (`nactiNastaveni`, `ulozNastaveni`), `main.jsx` (init při startu), `pages/Login.jsx`
  (`synchronizujVzhled`), `pages/Rozcestnik.jsx` (mřížka dlaždic), `styles/global.css` (třídy
  `gs-topbar`, `gs-tile`, `gs-lockchip`, přepínání `data-theme` / `data-cvd`).
- **Backend:** `app/nastaveni/models.py`, `routes.py`, `schemas.py`; `app/auth/permissions.py`
  (`dlazdice_pro`, `muze_otevrit`), `app/auth/routes.py` (`/auth/me`).

### Časté potíže / co dělat, když…
- **Vzhled se nepřenesl na jiné zařízení** → sync z DB běží **jen při přihlášení**. Odhlas se a
  přihlas znovu, ať se `GET /nastaveni` provede.
- **Po ručním obnovení stránky (F5) je vzhled ten „starý"** → po refreshi se aplikuje jen localStorage
  cache (v `main.jsx`), znovu-stažení z DB se děje až při dalším loginu. Změny provedené na jiném
  zařízení se tedy projeví až po opětovném přihlášení.
- **Přepnutí režimu/velikosti se neuložilo do profilu** → nejspíš chybí token (nepřihlášený stav) nebo
  selhal `PUT /nastaveni/{klic}`; chyba se v přepínačích **tiše ignoruje** (`.catch(() => {})`), takže
  vizuálně to funguje, ale mezi zařízeními se to nepřenese.
- **Dlaždice chybí úplně (ne jen zamčená)** → modul je v `SKRYT_BEZ_PRAVA` a uživatel nemá jeho právo;
  přidej právo v Admin nastavení.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Dvojí zdroj pravdy o vzhledu:** localStorage (rychlá cache proti probliknutí) vs. DB profil
  (přenos mezi zařízeními). Sladí se **jen při loginu**; po pouhém refreshi vyhrává localStorage.
- **Rozdílné názvy klíčů:** v prohlížeči `greensie_theme` / `greensie_velikost` / `greensie_cvd`,
  v DB `tema` / `velikost` / `cvd`. Snadné je zaměnit.
- **Chyby ukládání se tiše polykají** (`.catch(() => {})` v `ThemeToggle`/`VelikostTextu`/`CvdToggle`),
  takže neúspěšné uložení do profilu uživatel nepozná.
- **Odznak „zamčeno"** používá ikonu zámku a text „zamčeno" (ne emoji 🔒); popisek při najetí je
  „Zatím nedostupné – nemáš oprávnění tuto sekci otevřít".
- **Video pro zamčené/rozpracované dlaždice** je jeden společný odkaz `VYVOJ_VIDEO`
  (`https://youtu.be/oPLObjVAvIU`); mapa výjimek `VIDEO_DLE_KLICE` je zatím prázdná, takže všechny
  zamčené dlaždice vedou na totéž video. V praxi jsou dnes všechny moduly „hotové" (mají trasu), takže
  na video se dostaneš prakticky jen u zamčených (bez práva).
- **Kompenzace barev (`cvd`)** je nad rámec zadání (to zmiňovalo jen tema/velikost/pohled1_*), ale je
  to plnohodnotný společný přepínač uložený v profilu — proto je zdokumentovaný.

## Odkazy
- Kód frontend: `frontend/src/components/Layout.jsx`, `ThemeToggle.jsx`, `CvdToggle.jsx`,
  `VelikostTextu.jsx`, `Tile.jsx`, `Ikona.jsx`, `theme.js`, `velikost.js`, `api.js`, `main.jsx`,
  `pages/Login.jsx`, `pages/Rozcestnik.jsx`, `styles/global.css`
- Kód backend: `backend/app/nastaveni/` (models/routes/schemas), `backend/app/auth/permissions.py`
- Související: [Přehled projektů](./prehled-projektu.md) (klíče `pohled1_skryte`, `pohled1_poradi`),
  Admin nastavení (správa práv a skupin)
</content>
</invoke>
