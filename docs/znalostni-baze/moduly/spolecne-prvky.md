# Společné prvky UI

> **Kde:** napříč celou appkou (levý navigační panel a horní lišta na každé přihlášené obrazovce)
> **Kód:** frontend `frontend/src/components/Layout.jsx`, `Sidebar.jsx`, `UserMenu.jsx`, `Ikona.jsx`, `navigace.js`, `theme.js`, `velikost.js`, `api.js`, `styles/layout.css`; backend `backend/app/nastaveni/`

Tenhle „modul" není samostatná stránka, ale **rámec, ve kterém běží všechno ostatní**: navigační
panel vlevo, lišta nahoře s nabídkou uživatele a uživatelská nastavení, která se ukládají do profilu
a přenášejí mezi zařízeními. Popisujeme je jednou tady, ať se to v ostatních modulech nemusí
opakovat.

> 📸 SCREENSHOT: celá obrazovka appky — tmavý panel vlevo se skupinami, lišta nahoře s názvem stránky a uživatelem vpravo

---

## 🧑 Pro uživatele

### K čemu to slouží
Ať jsi v kterémkoli modulu, **vlevo máš stále stejný panel** se všemi sekcemi, na které máš právo —
mezi moduly se tedy přepínáš jedním kliknutím, bez vracení na úvodní stránku. **Vpravo nahoře** je
tvoje jméno; pod ním se skrývá nastavení vzhledu (tmavý režim, velikost textu, kompenzace barev),
změna hesla a odhlášení.

### Levý navigační panel
Panel je tmavý (v obou režimech) a je rozdělený do skupin:

| Skupina | Co je v ní |
|---|---|
| *(bez názvu, nahoře)* | **Rozcestník** — úvodní souhrn |
| **Přehledy** | Přehled projektů, Přehled financí, Přehled změn |
| **Nabídky** | Nabídkovač, Katalog technologií |
| **Systém** | Konektor Raynet ↔ Disk, Logy, Admin nastavení |
| **Nápověda** | Manuál |

- **Sekce, na kterou nemáš právo, v panelu vůbec není.** Nezobrazí se ani zašedle, ani se zámkem —
  prostě tam není. Když ti nějaká sekce chybí a myslíš si, že bys ji mít měl, řekni si o právo
  správci (Admin nastavení).
- **Rozcestník a Manuál** vidí každý přihlášený, ty právo nepotřebují.
- **Otevřená sekce** je zvýrazněná: ikona dostane zelený podklad a u levé hrany svítí zelený pásek.
- Nahoře je **logo Greensie** — klikem se vrátíš na Rozcestník.
- Dole je **Zúžit panel** — panel se zmenší na samotné ikony (hodí se na malém notebooku). Volba se
  pamatuje v prohlížeči, takže po dalším otevření appky zůstane. Ve zúženém stavu popisek najdeš po
  najetí myší na ikonu.
- Na **úzké obrazovce** (telefon, rozdělené okno) se panel zúží na ikony sám.

> 📸 SCREENSHOT: levý panel rozbalený vs. zúžený na ikony (vedle sebe)

### Horní lišta
Je na každé přihlášené obrazovce a obsahuje zleva doprava:

1. **Název stránky**, kde právě jsi (např. „Přehled projektů").
2. **Podtitulek** za lomítkem — čeho se stránka týká („Matice úkolů a fází"). Na úzké obrazovce se
   skryje.
3. **Mezera** — odtlačí zbytek doprava.
4. **Ikona „?"** — otevře **nápovědu k té stránce, na které právě jsi** (ne obecný začátek manuálu).
   Na samotném Manuálu se ikona neukazuje.
5. **Ty** — kolečko s iniciálami, jméno a pod ním tvoje skupina (u supersprávce „Supersprávce").
   Klikem se rozbalí nabídka.

### Nabídka uživatele (vpravo nahoře)
Klikni na svoje jméno. Nabídka má tři části:

**Kdo jsi** — iniciály, jméno, e-mail a odznak se skupinou (nebo „Supersprávce · všechna práva").

**Vzhled** — tři přepínače, u každého je zvýrazněná ta možnost, která právě platí:

| Přepínač | Volby | Co dělá |
|---|---|---|
| **Režim** | slunce / měsíc | světlý ↔ tmavý režim celé appky |
| **Barvosleposti** | Vyp / Zap | kompenzace červeno-zelené vady zraku |
| **Velikost textu** | A− / A / A+ | proporčně zvětší nebo zmenší celé rozhraní |

**Akce** — Změnit heslo, Admin nastavení (jen kdo na ně má právo), Manuál a **Odhlásit se**
(červeně, dole).

Nabídku zavřeš klikem mimo ni nebo klávesou **Esc**.

> 📸 SCREENSHOT: rozbalená nabídka uživatele s přepínači vzhledu

### Jak přepnout tmavý / světlý režim
Klikni vpravo nahoře na svoje jméno → u **Režim** vyber **měsíc** (tmavý) nebo **slunce** (světlý).
Přepnutí je okamžité a platí pro celou appku. Volba se uloží do tvého profilu, takže tě „potká" i na
jiném počítači nebo telefonu po přihlášení.

Na **přihlašovací obrazovce** (ještě před loginem) jsou vpravo nahoře jen dvě ikony — režim
(měsíc/slunce) a oko (kompenzace barev). Velikost textu a nabídka uživatele tam nejsou.

### Jak zvětšit / zmenšit text
Jméno vpravo nahoře → u **Velikost textu** vyber jeden ze tří stupňů:

| Volba | Efekt |
|---|---|
| **A−** | výchozí velikost (základ 14 px) |
| **A** | zvětší celou appku proporčně (přibližně 16/14) |
| **A+** | zvětší celou appku proporčně (přibližně 18/14) |

Nezvětšuje se jen písmo, ale **celé rozhraní** (zoom), takže se nic nerozbije. I tato volba se ukládá
do profilu.

### Nastavení se přenáší mezi zařízeními
Režim (tmavý/světlý), velikost textu a kompenzace barev se **ukládají do tvého profilu na serveru**.
Když se přihlásíš na jiném zařízení, appka si je po přihlášení stáhne a nastaví. V samotném
prohlížeči se drží i lokální kopie (kvůli rychlosti a aby při startu neproblikla špatná varianta),
ale „pravdou" je to, co je uloženo v profilu.

Výjimka: **zúžení panelu** se do profilu neukládá. Je to volba zařízení (malá obrazovka), ne
uživatele, takže zůstává jen v tom prohlížeči, kde jsi ji nastavil.

### Rozcestník — úvodní souhrn
Rozcestník je první stránka po přihlášení a ukazuje **stav ke dnešnímu dni**. Není to rozcestník
v původním smyslu (mřížka dlaždic) — navigaci obstarává panel vlevo.

Nahoře je pás **čísel**; ukazuje se jen to, na co máš právo:

| Číslo | Odkud se bere | Potřebné právo |
|---|---|---|
| **Aktivní projekty** | nezakryté projekty v matici | Přehled projektů |
| **Úkoly po termínu** | nehotové úkoly, kterým už termín uplynul | Přehled projektů |
| **Termín do 14 dnů** | nehotové úkoly s termínem v příštích 14 dnech (pod číslem je i kolik úkolů nemá termín vůbec) | Přehled projektů |
| **Neuhrazené faktury** | součet faktur, které nejsou zaplacené ani „nefakturuje" | Přehled financí |
| **Nabídky v přípravě** | nabídky, které ještě nejsou „hotovo" | Nabídkovač |

Pod čísly jsou dva výpisy (jen s právem na Přehled projektů):

- **Potřebuje pozornost** — nehotové úkoly po termínu, **nejstarší první**, u každého projekt, úkol,
  kdo ho má a o kolik dní se to protáhlo (červená pilulka).
- **Blíží se termín** — nehotové úkoly s termínem v příštích 14 dnech (žlutá pilulka „za X dní").

V každém výpisu je nejvýš 6 řádků a tlačítko **Otevřít Přehled projektů** — dashboard má být
přehled, ne seznam. Když není co ukázat, výpis to řekne („Nic není po termínu").

Když nemáš právo na žádný z modulů, které souhrn skládají, stránka to napíše a pošle tě do Manuálu.

> 📸 SCREENSHOT: úvodní souhrn — pás čísel a výpis „Potřebuje pozornost"

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = každý přihlášený · **(login)** = i na přihlašovací obrazovce ·
**(dle práv)** = podle oprávnění uživatele.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **Logo Greensie** | nahoře v panelu | Klik = zpět na Rozcestník | vše |
| **Položka nabídky** | levý panel | Otevře modul; aktivní má zelenou ikonu a pásek u hrany | dle práv |
| **Zúžit panel / Rozšířit** | dole v panelu | Zmenší panel na ikony; pamatuje se v prohlížeči | vše |
| **Název stránky + podtitulek** | horní lišta | Kde jsi (bez akce) | vše |
| **Ikona „?"** | horní lišta | Nápověda k aktuální stránce | vše (mimo Manuál) |
| **Jméno + iniciály** | horní lišta vpravo | Rozbalí nabídku uživatele | vše (po přihlášení) |
| **Režim (slunce/měsíc)** | nabídka uživatele | Světlý ↔ tmavý; uloží se do profilu | vše |
| **Barvosleposti (Vyp/Zap)** | nabídka uživatele | Kompenzace červeno-zelené vady; uloží se do profilu | vše |
| **Velikost textu (A− / A / A+)** | nabídka uživatele | Proporčně zvětší rozhraní; uloží se do profilu | vše |
| **Změnit heslo** | nabídka uživatele | Otevře stránku změny hesla | vše |
| **Admin nastavení** | nabídka uživatele | Zkratka do správy uživatelů | dle práv |
| **Odhlásit se** | nabídka uživatele | Smaže token a vrátí na přihlašovací obrazovku | vše |
| **Ikona měsíc / oko** | přihlašovací obrazovka | Režim a kompenzace barev před přihlášením | login |

### Kompenzace barev (Barvosleposti)
Pro lidi s červeno-zelenou vadou zraku (deuteranopie/protanopie). Po zapnutí appka vymění stavové
barvy a barvy grafů za paletu čitelnou bez rozlišení červená/zelená (modrá = v pořádku, závažnost
se pozná jasem). Layout se přitom nemění. Volba se ukládá do profilu.

### Jak na…
- **Přepnout na tmavý režim:** jméno vpravo nahoře → u **Režim** klikni na měsíc.
- **Zvětšit písmo:** jméno vpravo nahoře → u **Velikost textu** vyber **A** nebo **A+**.
- **Získat víc místa pro tabulku:** dole v panelu **Zúžit panel**.
- **Najít nápovědu k tomu, co mám na obrazovce:** ikona **„?"** v liště.
- **Přenést svůj vzhled na jiné zařízení:** nic navíc — stačí se tam přihlásit, nastavení se stáhne
  z profilu automaticky.
- **Odhlásit se:** jméno vpravo nahoře → **Odhlásit se**.

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
| `tema` | `"light"` / `"dark"` | `UserMenu.jsx` (na loginu `ThemeToggle.jsx`) | `Login.jsx` (po přihlášení) |
| `velikost` | `"male"` / `"stredni"` / `"velke"` | `UserMenu.jsx` | `Login.jsx` |
| `cvd` | `"on"` / `"off"` (kompenzace barev) | `UserMenu.jsx` (na loginu `CvdToggle.jsx`) | `Login.jsx` |
| `pohled1_skryte` | `{ faze: [...], ukoly: [...] }` | Přehled projektů | Přehled projektů |
| `pohled1_poradi` | `{ projekty, faze, ukoly }` | Přehled projektů | Přehled projektů |

Klíče `pohled1_skryte` a `pohled1_poradi` patří modulu Přehled projektů (osobní skrytí a pořadí) —
sdílí jen tenhle společný úložný mechanismus. Model je otevřený: **libovolný modul si sem může uložit
vlastní klíč** bez změny schématu.

**Zúžení panelu se do DB neukládá** — drží se jen v localStorage pod `greensie_panel`
(`"mini"` / `"expanded"`), protože je to vlastnost zařízení, ne uživatele.

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

### Jak rámec zjistí, co uživateli ukázat
- Struktura nabídky je v jednom souboru: **`frontend/src/navigace.js`** — `NABIDKA` (skupiny a
  položky s klíčem práva), `nabidkaPro(prava)` (profiltruje podle práv a zahodí prázdné skupiny),
  `aktivniKlic(pathname)` (která položka je zvýrazněná — vyhrává **nejdelší shoda cesty**, takže
  `/nabidkovac/katalog` přebije `/nabidkovac`), `popisStranky(pathname)` (název + podtitulek do
  lišty) a `strankaManualu(pathname)` (kam vede „?").
- **Práva** bere rámec ze `GET /auth/me` přes **`api.nactiMeSdilene()`** — sdílená odpověď
  s **minutovou platností**, aby se rámec nedotazoval znovu při každém přechodu mezi stránkami.
  Cache se zahodí při odhlášení (`logout()` volá `zapomenMe()`).
- Jednotlivé stránky si `nactiMe()` volají **dál samy** (bez cache) a Layoutu podávají jen
  `uzivatel`. Díky tomu se při přechodu na nový rámec nemusel měnit kód žádné stránky.
- Dokud odpověď `/auth/me` nedojde, kreslí se panel podle toho, co je známo z prop: supersprávce
  vidí vše, ostatní nic — ať panel neproblikne špatným obsahem.

### Souhrn na úvodní stránce
- Endpoint **`GET /dashboard`** (`backend/app/dashboard/routes.py`) složí čísla ze všech modulů
  jedním dotazem. **Sekce, na kterou uživatel nemá právo, se vrátí jako `None`** a frontend ji
  vůbec nekreslí — stejný princip jako skrývání položek v nabídce.
- Nic nepočítá jinak než příslušný modul: *nehotový úkol* je `Bunka.stav == "todo"` (jako v Přehledu
  změn), *neuhrazená faktura* je ta, jejíž stav není `zaplaceno` ani `nefakturuje` (jako v Přehledu
  financí). Počítají se jen úkoly a faktury projektů, které **nejsou zakryté** (`Projekt.skryty`).
- Konstanty na začátku souboru: `OKNO_BLIZI_SE_DNI = 14` (co je „blíží se"), `LIMIT_VYPISU = 6`
  (kolik řádků nejvýš) a `STAVY_MIMO_NEUHRAZENE`.
- Když `/dashboard` spadne, stránka **zůstane** a jen napíše, že se souhrn nepodařilo načíst —
  o vypršené přihlášení se stará `nactiMe()`.

### Práva — kdo co vidí a smí
- **Přepínače vzhledu a velikosti** smí měnit **každý** (i nepřihlášený na loginu, tam ale bez
  uložení do DB).
- **Položky nabídky:** kdo nemá právo se stejným klíčem, položku **vůbec neuvidí**. Nezobrazuje se
  zamčená varianta. Výjimka: **Rozcestník** a **Manuál** právo nepotřebují.
- **Odkaz na Admin nastavení** v nabídce uživatele se ukazuje jen s právem `admin`.
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky). Katalog práv je
  v `backend/app/auth/permissions.py` (`PRAVA`); supersprávce (`je_admin`) má vždy všechna.
- Skrytí v nabídce je **pohodlí, ne ochrana** — každý modul si právo hlídá i na backendu
  (např. `vyzaduj_admina`, `vyzaduj_pravo_zmeny`). Kdo by si adresu napsal ručně, dostane 403.

### Klíčové soubory
- **Frontend:** `components/Layout.jsx` (rámec), `Sidebar.jsx` (levý panel), `UserMenu.jsx` (nabídka
  uživatele), `Ikona.jsx` (sdílené SVG ikony), `navigace.js` (struktura appky), `theme.js`,
  `velikost.js`, `api.js` (`nactiMeSdilene`, `nactiDashboard`, `nactiNastaveni`, `ulozNastaveni`),
  `main.jsx` (init při startu), `pages/Login.jsx` (`synchronizujVzhled`), `pages/Rozcestnik.jsx`
  (úvodní souhrn), `styles/layout.css` (třídy `gs-app`, `gs-sb`, `gs-tb`, `gs-menu`),
  `styles/global.css` (tokeny, přepínání `data-theme` / `data-cvd`).
- **Backend:** `app/nastaveni/` (models/routes/schemas), `app/dashboard/` (souhrn),
  `app/auth/permissions.py` (`prava_uzivatele`, `muze_otevrit`), `app/auth/routes.py` (`/auth/me`).

### Časté potíže / co dělat, když…
- **Sekce v panelu chybí** → uživatel nemá její právo. Přidej ho v Admin nastavení (skupině nebo
  jako individuální výjimku).
- **Právo jsem přidal, ale v panelu se sekce neobjevila** → rámec drží práva **minutu** v cache.
  Počkej chvíli, obnov stránku (F5), nebo se odhlas a přihlas.
- **Vzhled se nepřenesl na jiné zařízení** → sync z DB běží **jen při přihlášení**. Odhlas se a
  přihlas znovu, ať se `GET /nastaveni` provede.
- **Po ručním obnovení stránky (F5) je vzhled ten „starý"** → po refreshi se aplikuje jen localStorage
  cache (v `main.jsx`), znovu-stažení z DB se děje až při dalším loginu. Změny provedené na jiném
  zařízení se tedy projeví až po opětovném přihlášení.
- **Přepnutí režimu/velikosti se neuložilo do profilu** → nejspíš chybí token (nepřihlášený stav) nebo
  selhal `PUT /nastaveni/{klic}`; chyba se v přepínačích **tiše ignoruje** (`.catch(() => {})`), takže
  vizuálně to funguje, ale mezi zařízeními se to nepřenese.
- **Na úvodní stránce chybí čísla, ale sekce v panelu jsou** → `/dashboard` selhal; stránka to hlásí
  pilulkou „Souhrn se nepodařilo načíst" i s textem chyby. Zkus Logy.
- **Panel je zúžený a nejde rozšířit** → na úzké obrazovce se zúží automaticky a tlačítko se skryje;
  rozšíří se sám, až bude okno širší než 720 px.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Dvojí zdroj pravdy o vzhledu:** localStorage (rychlá cache proti probliknutí) vs. DB profil
  (přenos mezi zařízeními). Sladí se **jen při loginu**; po pouhém refreshi vyhrává localStorage.
- **Rozdílné názvy klíčů:** v prohlížeči `greensie_theme` / `greensie_velikost` / `greensie_cvd`,
  v DB `tema` / `velikost` / `cvd`. Snadné je zaměnit.
- **Chyby ukládání se tiše polykají** (`.catch(() => {})` v `UserMenu`), takže neúspěšné uložení do
  profilu uživatel nepozná.
- **Minutová cache práv** (`nactiMeSdilene`) je kompromis: bez ní by se `/auth/me` volalo dvakrát na
  každý přechod mezi stránkami, s ní se změna práv projeví se zpožděním až minutu.
- **`GET /auth/me` dál vrací pole `dlazdice`** (`dlazdice_pro`, katalog `DLAZDICE` v
  `permissions.py`), ale **frontend ho už nepoužívá** — nabídka se řídí polem `prava`. Pole zůstalo,
  aby se nerozbilo API; při dalším úklidu je kandidát na odstranění.
- **Dlaždicové styly** (`gs-tile`, `gs-lockchip` v `global.css`) a komponenta `Tile.jsx` zůstaly
  v kódu nepoužité — schválně, dokud se nový vzhled neusadí, ať je cesta zpět k dlaždicím snadná.
- **Zamčené dlaždice a instruktážní video** (`VYVOJ_VIDEO`) v novém rámci **nejsou**. Sekce bez práva
  se skryje, takže není co odemykat ani kam prokliknout.
- **Kompenzace barev (`cvd`)** je nad rámec zadání (to zmiňovalo jen tema/velikost/pohled1_*), ale je
  to plnohodnotný společný přepínač uložený v profilu — proto je zdokumentovaný.
- **Hledání v liště** zatím neexistuje (nemá backend), stejně jako **odznaky s počty** u položek
  nabídky (CSS `gs-nav-badge` je připravené, ale nic ho neplní).

## Odkazy
- Kód frontend: `frontend/src/components/Layout.jsx`, `Sidebar.jsx`, `UserMenu.jsx`, `Ikona.jsx`,
  `navigace.js`, `theme.js`, `velikost.js`, `api.js`, `main.jsx`, `pages/Login.jsx`,
  `pages/Rozcestnik.jsx`, `styles/layout.css`, `styles/global.css`
- Kód backend: `backend/app/nastaveni/` (models/routes/schemas), `backend/app/dashboard/`,
  `backend/app/auth/permissions.py`
- Související: [Přehled projektů](./prehled-projektu.md) (klíče `pohled1_skryte`, `pohled1_poradi`),
  [Práva a skupiny](../server/prava-a-skupiny.md), Admin nastavení (správa práv a skupin)
