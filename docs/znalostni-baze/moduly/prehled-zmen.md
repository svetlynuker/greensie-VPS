# Přehled změn

> **Dlaždice:** `zmeny` · **Adresa (routa):** `/zmeny` · **Kdo smí otevřít:** kdokoli s právem `zmeny` (dlaždici vidí všichni, bez práva je zamčená 🔒; admin vždy)
> **Kód:** frontend `frontend/src/pages/PrehledZmen.jsx`, backend `backend/app/zmeny/`

Přehled toho, **co se v projektech za zvolené období pohnulo** — kolik úkolů se splnilo,
kolik spadlo do prodlení a kolik je v prodlení právě teď. Počítá se jako **čistý rozdíl
dvou „fotek" stavu** (snímek k datu OD vs. snímek nebo živý stav k datu DO). Modul je čistě
**čtecí** — nic se v něm needituje. V paměti projektu je veden jako **Pohled 3**.

> 📸 SCREENSHOT: celá obrazovka Přehledu změn — filtr období nahoře, tři souhrnné karty, tabulka projektů s proužky pohybu

---

## 🧑 Pro uživatele

### K čemu to slouží
Když chceš vědět, **jak se práce hnula za týden / za měsíc / od začátku sledování**, tenhle
přehled to ukáže na jedné obrazovce. Neukazuje aktuální stav (od toho je Přehled projektů),
ale **rozdíl mezi dvěma okamžiky**: co se mezitím dokončilo (👍) a co se mezitím zhoršilo, tzn.
spadlo po termínu (👎). Navíc říká, kolik úkolů je **v prodlení teď**, ať víš, co hoří.

### Rozvržení obrazovky
Shora dolů:

1. **Odkaz „← Rozcestník"** — návrat na hlavní rozcestník appky.
2. **Filtr období** — tři přepínače (segment) „Od začátku / Posledních 7 dní / Vlastní rozmezí",
   u vlastního rozmezí dvě pole s datem, a vpravo popisek **Období: OD – DO** se skutečně
   použitými hranicemi.
3. **Informační hláška** (občas) — o pokrytí daty (viz níže).
4. **Tři souhrnné karty** — Splněno / Spadlo do prodlení / Aktuálně v prodlení (součty za vše).
5. **Tabulka projektů** — řádek = projekt; proužek pohybu + tři čísla. Klik na řádek ho
   **rozbalí** a ukáže konkrétní úkoly ve třech sloupcích.

### Tři sledované veličiny (co která znamená)
Všechno se počítá k hranicím zvoleného období (OD a DO):

| Veličina | Barva | Přesně znamená |
|---|---|---|
| **Splněno** | 🟢 zelená | Úkol byl na začátku období **nehotový** (todo) a na konci je **hotový** (done). |
| **Spadlo do prodlení** | 🔴 červená | Úkol **nebyl v prodlení na začátku**, ale **je v prodlení na konci** období (mezitím se zhoršil). |
| **Aktuálně v prodlení** | 🟠 oranžová | Úkol je v prodlení **ke konci období** (bez ohledu na to, kdy do prodlení spadl). |

**Prodlení** = úkol je **nehotový** (todo) a jeho **termín už je v minulosti** vůči danému dni.
Úkoly bez termínu nebo hotové úkoly do prodlení nikdy nespadnou.

> 📸 SCREENSHOT: tři souhrnné karty s čísly (Splněno / Spadlo do prodlení / Aktuálně v prodlení)

### Snímky a net-rozdíl dvou fotek — jak to funguje
- Server si **jednou denně uloží „fotku" stavu** všech úkolů, které mají vyplněný stav
  (hotovo/nehotovo + termín). Prázdné úkoly (bez stavu) se do fotky neukládají.
- Přehled pak vezme **fotku k datu OD** a **fotku (nebo živý stav) k datu DO** a spočítá
  **rozdíl** mezi nimi. Není to součet denních událostí, ale **čistý rozdíl dvou okamžiků** —
  když se úkol během období dokončil a zase otevřel, ve výsledku se to vyruší.
- **Ke dni DO = dnešek** se místo fotky bere **živý aktuální stav** (dnes ještě fotka nemusí
  odpovídat poslednímu kliknutí v matici). Pro DO v minulosti se použije nejbližší **starší
  nebo shodná** fotka.
- Pro OD se stejně bere **nejbližší starší nebo shodná** fotka. Když se ptáš na období před
  úplně první fotkou, chová se OD jako „prázdný stav" (vše se pak jeví jako přírůstek).
- **První uložená fotka = „základna"**, se kterou porovnává volba **„Od začátku"**.

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = všichni, kdo modul otevřou. Modul je jen ke čtení, takže
**všechny prvky vidí a používá každý, kdo má právo `zmeny`** — žádné editorské ani adminské
prvky tu nejsou.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **Od začátku** | filtr období | Období od nejstarší fotky (základny) po dnešek | vše |
| **Posledních 7 dní** | filtr období | Období od dne před 7 dny po dnešek | vše |
| **Vlastní rozmezí** | filtr období | Odemkne dvě pole s datem pro ruční volbu OD/DO | vše |
| **Pole „od"** | filtr (jen u Vlastní) | Datum začátku období; nejvýš rovné poli „do" | vše |
| **Pole „do"** | filtr (jen u Vlastní) | Datum konce období; nejvýš dnešek, nejméně pole „od" | vše |
| **Období: OD – DA** | vpravo ve filtru | Ukazuje **skutečně použité** hranice (server je může upravit, viz úskalí) | vše |
| **Souhrnná karta** | pod filtrem | Celkový součet dané veličiny za všechny projekty | vše |
| **Řádek projektu** | tabulka | Klik ho **rozbalí/sbalí** — ukáže konkrétní úkoly (▸ / ▾) | vše |
| **Proužek pohybu** | tabulka | Vizuální poměr: zelená = splněno, červená = spadlo do prodlení | vše |
| **Číslo Splněno / Spadlo / V prodlení** | tabulka | Počty za daný projekt; nula je zašedlá | vše |
| **Odkaz na úkol v detailu** | rozbalený detail | Otevře úkol ve Freelu (nový panel), když má odkaz | vše (když je URL) |

> 📸 SCREENSHOT: jeden rozbalený řádek projektu se třemi sloupci detailu (Splněno / Spadlo do prodlení / Aktuálně v prodlení)

### Rozbalený detail projektu
Klik na řádek projektu otevře tři sloupce s konkrétními úkoly:

| Sloupec | Co obsahuje | Ukazuje termín? |
|---|---|---|
| **Splněno** | úkoly, které se za období dokončily | ne |
| **Spadlo do prodlení** | úkoly, které za období spadly po termínu | ano (v závorce) |
| **Aktuálně v prodlení** | úkoly v prodlení ke konci období | ano (v závorce) |

U každého úkolu je (pokud jsou vyplněné) **fáze**, **název úkolu** a **odkaz do Freela**.
Prázdný sloupec ukáže pomlčku „–".

### Pořadí projektů a proužek
- Projekty se řadí tak, aby **problémové byly nahoře**: nejdřív podle počtu „aktuálně v prodlení",
  pak „spadlo do prodlení", pak „splněno", nakonec podle názvu.
- V tabulce jsou **všechny neskryté projekty** (i ty, kde se nic nepohnulo — mají samé nuly).
- **Proužek pohybu** má společnou škálu: jeho šířka se počítá z projektu s největším součtem
  (splněno + spadlo). Slouží k rychlému porovnání „kde se dělo nejvíc".

### Jak na…
- **Zjistit, co se hnulo za týden:** přepínač **Posledních 7 dní**. Karty ukážou souhrn,
  tabulka rozpad po projektech.
- **Podívat se na konkrétní měsíc:** **Vlastní rozmezí** → nastav „od" a „do".
- **Vidět, co konkrétně se dokončilo / spadlo:** klikni na řádek projektu → rozbalí se seznam úkolů.
- **Podívat se na celou historii:** **Od začátku** (porovná se se základnou = první fotkou).

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Přehled změn** vidí v rozcestníku **všichni**, ale bez práva `zmeny` je **zamčená** (🔒).
- Otevřít modul a číst data smí každý s právem **`zmeny`**; **supersprávce** (`uzivatel.je_admin`) má
  vše automaticky. Strážce endpointu je `vyzaduj_pravo_zmeny` (volá `muze_otevrit(user, "zmeny")`).
- **Modul nemá žádnou editaci** — neexistuje tu právo typu `editace`. Všichni, kdo modul otevřou,
  vidí a používají úplně stejné prvky.
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky), stejný klíč
  `zmeny` je zároveň dlaždice i právo (viz `backend/app/auth/permissions.py`).
- Frontend navíc: když server vrátí 403 (chybí právo), stránka přesměruje na `/rozcestnik`.

### Nastavení
Modul **nemá žádné vlastní nastavení ani konfiguraci** — žádné prahy, žádné volby. Jediné, co
ovlivňuje jeho data, je **pořizování denních snímků** (viz níže) a obsah matice v Přehledu projektů.

### Jak a kdy se pořizují snímky (plánovač)
- Snímky pořizuje **plánovač matice** (to samé vlákno, které dělá auto-synchronizaci z Freela):
  `backend/app/matice/scheduler.py`, funkce `_mozna_sejmi_snimek()` → `sejmi_snimek(db)`.
- Vlákno se probouzí **každou minutu** (`KONTROLA_S = 60`), po startu má krátkou prodlevu
  (`START_PRODLEVA_S = 30 s`). Při každém probuzení **zkusí sejmout snímek dneška**.
- `sejmi_snimek` je **idempotentní na den**: pokud pro daný den už fotka existuje, nic nepřidá
  (vrací 0). Fakticky tedy vznikne **jedna fotka za kalendářní den** — při prvním probuzení v novém dni.
- **Základna vzniká hned po startu** backendu (do ~30 s), pokud ještě žádná fotka není. To je
  první snímek, se kterým porovnává „Od začátku".
- Snímkuje se **jen dimenze hotovo/nehotovo + termín**; poznámky a osoby se záměrně neukládají.
- Chyby při snímkování se **spolknou** — snímek nikdy neshodí synchronizaci ani app.
- **Předpoklad:** backend běží v **jednom procesu** (jeden plánovač). Viz i paměť projektu
  „Konektory jako samostatné procesy".

### Napojení na okolní systémy
- **Přehled projektů / matice** (`backend/app/matice/models.py`) — jediný zdroj dat. Snímky se berou
  z tabulky `bunky` (stav, termín); metadata úkolů z `sloupce` (fáze, název, label) a projektů z `projekty`.
- **Freelo** — jen nepřímo: odkaz `url` u buňky vede na úkol ve Freelu (proklik v detailu).
- Jinak modul **nikam nezapisuje** — čte matici a vlastní snímky.

### Jak to funguje uvnitř (stručně technicky)
- **Datový model** (`backend/app/zmeny/models.py`):
  - `stav_snapshot` — denní fotka stavu jedné buňky: `den` (datum, index), `bunka_id`
    (FK `bunky.id`, ON DELETE CASCADE), `stav` (`done`/`todo`/`None`), `termin`.
    Unikát na dvojici (`den`, `bunka_id`) — jedna fotka buňky na den.
- **API** (`backend/app/zmeny/routes.py`, prefix `/zmeny`):
  - `GET /zmeny?od=YYYY-MM-DD&do=YYYY-MM-DD` — spočítá a vrátí přehled změn. Oba parametry jsou
    nepovinné: prázdné `od` = od nejstarší fotky, prázdné `do` = dnešek. Vrací `ZmenyOut`
    (skutečné hranice `od`/`do`, `sledovano_od`, `souhrn`, `projekty` s detaily).
- **Klíčová logika:**
  - `snapshot.py` — práce se snímky: `sejmi_snimek` (uloží fotku dne, idempotentní),
    `nejstarsi_den` (základna), `ziv_stav` (živý aktuální stav buněk), `snimek_ke_dni`
    (nejbližší starší/rovná fotka k datu).
  - `routes.py` — výpočet rozdílů: pro každou buňku porovná stav na začátku a na konci, dopočte
    prodlení funkcí `_je_v_prodleni(stav, termin, ke_dni)` a naplní počty + detaily po projektech.
    Zobrazují se jen **neskryté** projekty (`Projekt.skryty == False`).
- **Klíčové soubory:** `routes.py` (API + výpočet), `snapshot.py` (snímky), `models.py`
  (tabulka fotek), `schemas.py` (výstupní tvary). Snímkuje `matice/scheduler.py`.
  Frontend: `pages/PrehledZmen.jsx`, API funkce `nactiZmeny` v `frontend/src/api.js`,
  routa `/zmeny` v `frontend/src/App.jsx`. Práva `auth/permissions.py`.

### Časté potíže / co dělat, když…
- **„Zatím nebyl pořízen žádný snímek stavu"** → plánovač ještě neuložil základnu (čerstvě
  nasazeno, nebo plánovač neběží). Počkej ~minutu po startu backendu; když trvá, ověř, že
  běží vlákno plánovače (`spust_planovac`) a že v matici jsou buňky s vyplněným stavem.
- **„Změny se sledují až od …"** → ptáš se na období **před první fotkou**. Pro starší data
  prostě neexistují snímky; použij pozdější „od".
- **Přehled ukazuje samé nuly** → za období se nic nezměnilo, nebo je jen jedna fotka (základna)
  a od té doby beze změny stavu. U voleb v minulosti může být „od" i „do" ve stejné fotce.
- **Chybí projekt, který v matici je** → je nejspíš **skrytý** (`skryty=True`) v Přehledu projektů;
  skryté projekty se do přehledu změn nezahrnují.
- **Úkol „zmizel" z prodlení, aniž byl hotový** → nejspíš mu **posunuli termín** do budoucna
  (prodlení se počítá ze stavu + termínu k danému dni).

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Net-rozdíl, ne deník událostí:** krátkodobé překlopení (dokončit a zase otevřít) se ve
  výsledku vyruší. „Splněno" počítá jen úkoly, které jsou na konci období hotové a na začátku nebyly.
- **Dnešek = živý stav:** pro `do >= dnes` se místo fotky bere aktuální stav matice, takže
  dnešní čísla se mění průběžně, jak lidé klikají v Přehledu projektů.
- **Fotka „ke dni" je nejbližší starší/rovná** — když v konkrétní den fotka chybí (výpadek
  plánovače), použije se poslední předchozí. Díra v denních fotkách tedy přehled nerozbije,
  jen sníží přesnost porovnání.
- **Skutečné hranice se mohou lišit od zadaných:** server ořízne „do" na dnešek a když je
  „od" > „do", srovná je. Proto je vpravo ve filtru popisek se **skutečně použitým** obdobím.
- **Rozpor v UI hlášce:** frontend píše, že první snímek vznikne „**do hodiny po nasazení**",
  ale kód pořizuje základnu už ~30 s po startu (a pak zkouší každou minutu). Text je jen
  konzervativní odhad, ne reálná prodleva. (K ověření / kosmetická nesrovnalost.)
- **Závislost na jednom procesu:** snímkuje stejné vlákno jako Freelo-sync; při běhu ve více
  workerech by se pořizování snímků mohlo chovat jinak (viz paměť „Konektory jako samostatné procesy").
- **Mazání buněk:** `stav_snapshot` má FK s `ON DELETE CASCADE` — smazání buňky v matici smaže
  i její historické fotky.

## Odkazy
- Kód backend: `backend/app/zmeny/` (`routes.py`, `snapshot.py`, `models.py`, `schemas.py`) ·
  snímkuje `backend/app/matice/scheduler.py`
- Kód frontend: `frontend/src/pages/PrehledZmen.jsx`, `frontend/src/api.js` (`nactiZmeny`),
  `frontend/src/App.jsx` (routa `/zmeny`)
- Práva: `backend/app/auth/permissions.py` (klíč `zmeny`, `muze_otevrit`)
- Paměť projektu: „Pohled 3 Přehled změn" (denní snímky, net-rozdíl dvou fotek, `/zmeny`)
- Související: [Přehled projektů](prehled-projektu.md) (zdroj dat — matice, buňky, stav a termín)
