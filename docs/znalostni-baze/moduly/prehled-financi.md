# Přehled financí

> **Dlaždice:** `finance` · **Adresa (routa):** `/finance` · **Kdo smí otevřít:** jen s právem `finance` (dlaždici vidí všichni, bez práva je zamčená 🔒; v praxi Rosťa + skupina „vedení")
> **Kód:** frontend `frontend/src/pages/PrehledFinanci.jsx` + dialog `frontend/src/components/FakturaDialog.jsx`, backend `backend/app/finance/`

Přehledová tabulka **fakturace po projektech** (interně „Pohled 2"). Řádky jsou projekty (tytéž jako
v Přehledu projektů), sloupce jsou jednotlivé faktury projektu (Faktura 1, 2, 3…). U každé faktury se
sleduje stav (potřeba vystavit / vystaveno / zaplaceno / nefakturuje se), částka, termín, variabilní
symbol a poznámka. Cílem je později napojení na účetní systém **Pohoda** (párování přes variabilní symbol).

> 📸 SCREENSHOT: celá obrazovka Přehledu financí — horní lišta, legenda stavů, tabulka projekty × faktury

---

## 🧑 Pro uživatele

### K čemu to slouží
Na jednom místě vidíš u **každého projektu, jak je na tom s fakturami**: co je potřeba vystavit, co už
je vystavené a co zaplacené. Každý projekt může mít různý počet faktur. Kliknutím do buňky fakturu
upravíš (stav, částka, termín, variabilní symbol, poznámka). Tlačítko „Synchronizovat s Pohodou" má
v budoucnu stavy faktur samo potvrzovat podle účetnictví — **zatím napojení na Pohodu není aktivní**.

### Rozvržení obrazovky
Shora dolů:

1. **Odkaz „← Zpět na rozcestník"** — návrat na hlavní rozcestník appky.
2. **Horní lišta (topbar)** — název „Přehled financí", tlačítko **↻ Synchronizovat s Pohodou**
   (jen kdo smí editovat), místo pro hlášku po synchronizaci a vpravo počítadlo **„N projektů"**.
3. **Legenda stavů** — čtyři stavy faktury, každý s barvou **i ikonou i textem** (appka se nikdy
   nespoléhá jen na barvu — počítá s barvoslepým uživatelem).
4. **Tabulka (matice)** — první dva sloupce jsou **Projekt** a **Termín** (přilepené vlevo při
   vodorovném rolování), za nimi sloupce **Faktura 1 … Faktura N** a úplně vpravo sloupec **Přidat**
   (jen kdo smí editovat).

### Jak číst tabulku
- **Řádek = projekt.** Vlevo název (proklik do Freela, pokud má projekt URL) a jeho termín.
- **Sloupec „Faktura N" = N-tá faktura projektu** (řadí se podle pořadí `poradi`). Šířka tabulky
  (kolik sloupců faktur je) se řídí projektem s **nejvíc fakturami**; u ostatních projektů jsou přebývající
  buňky prázdné (tečka `·`).
- **Buňka faktury** ukazuje: **stav** (barva + ikona + text), a když jsou vyplněné, i **částku**,
  **termín**, **VS** (variabilní symbol), příznak **✓ Pohoda** (potvrzeno účetnictvím) a **poznámku**.
  Poznámka je zároveň v tooltipu buňky (najetí myší).

### Stavy faktury
| Stav (ikona) | Klíč v datech | Význam |
|---|---|---|
| ✎ **Potřeba vystavit** | `potreba_vystavit` | výchozí stav nové faktury; ještě není vystavená |
| 📤 **Vystaveno** | `vystaveno` | faktura byla vystavená, čeká na zaplacení |
| ✓ **Zaplaceno** | `zaplaceno` | faktura je uhrazená |
| ∅ **Nefakturuje se** | `nefakturuje` | u tohoto slotu se fakturovat nebude |

> 📸 SCREENSHOT: legenda stavů + několik buněk s částkou, VS a odznakem „✓ Pohoda"

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = každý, kdo modul otevře (má právo `finance`) · **(editor)** = kdo smí
finance editovat. **Pozor:** v tomto modulu je otevření i editace **totéž právo `finance`** — kdo modul
otevře, ten smí i editovat. Samostatná role „editor" jako v Přehledu projektů tu není (viz „Práva").

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **↻ Synchronizovat s Pohodou** | horní lišta | Spustí párování faktur s Pohodou podle VS; ukáže hlášku o výsledku. Dokud Pohoda není nakonfigurovaná, vrátí jen informaci, že napojení není aktivní | editor |
| **Hláška po synchronizaci** | horní lišta | Text výsledku poslední synchronizace (kolik faktur spárováno / že napojení není aktivní / chyba) | editor |
| **Počítadlo „N projektů"** | vpravo v liště | Kolik je projektů v tabulce | vše |
| **Legenda stavů** | pod lištou | Vysvětluje barvy, ikony a texty stavů (jen informativní) | vše |
| **Název projektu (odkaz)** | sloupec Projekt | Otevře projekt ve Freelu v novém panelu (jen když má projekt URL) | vše |
| **Buňka faktury** | tabulka | Klik otevře dialog editace faktury | editor (jinak klik nic neudělá) |
| **+ faktura** | sloupec „Přidat" | Přidá projektu další prázdnou fakturu (další „Faktura N") | editor |

> 📸 SCREENSHOT: horní lišta s tlačítkem „Synchronizovat s Pohodou" a počítadlem

### Dialog editace faktury
Otevře se klikem do buňky (jen editor). V hlavičce je „Faktura N" a název projektu. Pole:

| Pole | Co dělá |
|---|---|
| **Stav** | výběr ze čtyř stavů (Potřeba vystavit / Vystaveno / Zaplaceno / Nefakturuje se) |
| **Částka (Kč, nepovinné)** | volný text, přijímá i čárku jako desetinný oddělovač; prázdné = bez částky |
| **Variabilní symbol (párování s Pohodou)** | VS, přes který se faktura spáruje s Pohodou (např. `2026001`); prázdné = bez VS |
| **Termín (nepovinné)** | datum (kalendář) |
| **Poznámka** | volný text |
| **„Pohoda potvrdila…"** (jen text) | pokud Pohoda fakturu potvrdila, ukáže se datum vystavení / zaplacení; jen ke čtení |
| **Smazat** | odebere tuto fakturu z projektu (vlevo dole; jen když jde fakturu mazat) |
| **Zrušit / Uložit** | zavře bez uložení / uloží změny |

> ⚠️ Uložením dialogu se faktura označí jako **ručně upravená** (`upraveno_rucne = True`).
> Automatika (Pohoda) pak její **stav už nepřepíše** — ruční úprava má přednost. Pohoda u ručně
> upravené faktury doplní jen data potvrzení (`✓ Pohoda`, datum vystavení/zaplacení), ale stav nechá být.

> 📸 SCREENSHOT: dialog editace faktury s vyplněnými poli

### Jak na…
- **Nastavit stav faktury:** klik do buňky → vyber Stav → Uložit.
- **Zapsat částku a VS:** klik do buňky → vyplň Částku a Variabilní symbol → Uložit. VS je klíč pro
  budoucí párování s Pohodou.
- **Přidat další fakturu projektu:** ve sloupci „Přidat" u řádku projektu klikni **+ faktura**
  (vznikne nová „Faktura N").
- **Odebrat fakturu:** klik do buňky → **Smazat** v dialogu.
- **Přejít z Přehledu projektů na konkrétní projekt:** proklik „💰 Finance" v Přehledu projektů otevře
  `/finance?projekt=<id>`; stránka na projekt sama naskroluje a zvýrazní jeho řádek.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Přehled financí** vidí v rozcestníku **všichni**, ale bez práva `finance` je **zamčená** (🔒).
- Právo **`finance`** je v tomto modulu **jediné** a zároveň otevírá modul i povoluje editaci
  (backend: `vyzaduj_finance`; do odpovědi se posílá `muze_editovat = muze_finance(user)`, což je totéž
  právo). Kdo modul otevře, může tedy i upravovat faktury, přidávat je, mazat a spouštět synchronizaci.
- **Supersprávce** (`uzivatel.je_admin`) má všechna práva včetně `finance`.
- Právo `finance` se přiděluje skupině nebo jako individuální výjimka v modulu **Admin nastavení**.
  Podle komentáře v kódu je určené pro **Rosťu + skupinu „vedení"**.
- **Frontend guard:** routa `/finance` je jen za přihlášením (`VyzadujePrihlaseni`). Kontrolu práva
  dělá až backend (403); stránka chybu „oprávnění" zachytí a přesměruje na `/rozcestnik`.

### Nastavení
Modul nemá vlastní obrazovku nastavení. Jediná konfigurace je **napojení na Pohodu přes proměnné v `.env`**
na serveru (viz níže). Výchozí počet prázdných faktur u nového projektu je **3** (`VYCHOZI_POCET_FAKTUR`
v `models.py`), výchozí stav faktury je **`potreba_vystavit`** (`VYCHOZI_STAV`).

### Napojení na okolní systémy
- **Přehled projektů / Freelo** — finance **nemají vlastní projekty**. Řádky jsou tytéž projekty jako
  v Přehledu projektů (tabulka `projekty` z modulu `matice`), které se plní z Freela. Když v Přehledu
  financí nejsou žádné projekty, je to proto, že se ještě nenačetly z Freela. Vazba je definovaná jen
  na straně financí (`Faktura.projekt_id → projekty.id`), do Pohledu 1 se finance nemíchají.
- **Pohoda (účetnictví)** — **napojení je zatím jen kostra, není aktivní.** Klient
  (`backend/app/finance/pohoda.py`) je připravený párovat faktury podle **variabilního symbolu** a číst
  z Pohody jen informaci „vystaveno / zaplaceno" (do Pohody se **nikdy nezapisuje**). Funguje až po
  doplnění přístupů do `.env`:

  | Proměnná `.env` | Význam |
  |---|---|
  | `POHODA_URL` | adresa API (typicky mServer, lokální XML rozhraní Pohody, např. `http://127.0.0.1:1234/xml`) |
  | `POHODA_LOGIN` | přihlašovací jméno k mServeru |
  | `POHODA_HESLO` | heslo k mServeru |
  | `POHODA_ICO` | IČO firmy, na kterou se dotaz váže |

  Dokud nejsou vyplněné všechny čtyři, `je_nakonfigurovano()` vrací `False` a synchronizace se chová jako
  vypnutá (vrátí `aktivni: false` a informativní hlášku). Reálné XML volání (`listInvoiceRequest`) zatím
  není implementované — `nacti_faktury_dle_vs` po nakonfigurování vyhodí `NotImplementedError`.
- **Fakturační pravidla z Freela** — soubor `backend/app/finance/pravidla.py` je připravený místo, kam se
  doplní logika „kdy se má co fakturovat" (např. po podpisu SOD vystavit Fakturu 1). **Zatím je to no-op**
  — appka jede na ručním nastavování stavů.

### Jak to funguje uvnitř (stručně technicky)
- **Datový model** (`backend/app/finance/models.py`), tabulka **`faktury`**:
  - `id`, `projekt_id` (FK na `projekty`, `ON DELETE CASCADE`) — smazáním projektu zmizí i jeho faktury.
  - `poradi` — 1, 2, 3… = „Faktura 1/2/3" v rámci projektu. Unikát na dvojici (`projekt_id`, `poradi`).
  - `stav` — jeden ze `STAVY_FAKTURY` (`potreba_vystavit` / `vystaveno` / `zaplaceno` / `nefakturuje`).
  - `castka` (Numeric 12,2), `termin` (Date), `poznamka` (Text), `variabilni_symbol` (String, indexovaný — párovací klíč na Pohodu).
  - `freelo_faze`, `freelo_task_id` — odkaz na úkol/fázi ve Freelu, který fakturu „spouští" (zatím se využívá jen v `pravidla.py`).
  - `pohoda_potvrzeno`, `pohoda_datum_vystaveni`, `pohoda_datum_zaplaceni` — co potvrdila Pohoda (plní se až po synchronizaci).
  - `upraveno_rucne` — `True` = stav zadán ručně v appce, má přednost před automatikou (Pohoda/Freelo).
  - Faktury nejsou sdílené napříč projekty (na rozdíl od „sloupců" v Pohledu 1) — každý projekt má vlastní seznam.
- **Lazy zakládání faktur:** při čtení `GET /finance` se každému projektu, který ještě **žádnou** fakturu
  nemá, doplní **3 prázdné** (Faktura 1–3) a uloží (stejný princip jako řádek barev v Pohledu 1).
- **API** (`backend/app/finance/routes.py`, prefix `/finance`, vše za právem `finance`):
  - `GET /finance` — celá matice: `muze_editovat`, `max_faktur`, seznam projektů s fakturami.
  - `PUT /finance/faktura/{id}` — uloží fakturu (stav, částka, termín, poznámka, VS); nastaví `upraveno_rucne = True`.
  - `POST /finance/projekt/{id}/faktura` — přidá projektu další fakturu (`poradi` = nejvyšší + 1).
  - `DELETE /finance/faktura/{id}` — smaže fakturu.
  - `POST /finance/pohoda/synchronizovat` — spáruje faktury s Pohodou podle VS (zatím kostra, viz výše).
- **Klíčové soubory:**
  - backend: `routes.py` (API), `models.py` (tabulka `faktury`), `schemas.py` (vstup/výstup),
    `permissions.py` (`muze_finance`, `vyzaduj_finance`), `pohoda.py` (klient Pohody – kostra),
    `pravidla.py` (fakturační pravidla z Freela – zatím no-op).
  - frontend: `pages/PrehledFinanci.jsx` (stránka), `components/FakturaDialog.jsx` (dialog),
    funkce v `api.js` (`nactiFinance`, `ulozFakturu`, `pridejFakturu`, `smazFakturu`, `synchronizujPohodu`),
    routa v `App.jsx`, styly `styles/pohled2.css`.
  - práva: `backend/app/auth/permissions.py` (klíč dlaždice `finance`, právo `finance`).

### Časté potíže / co dělat, když…
- **„Napojení na Pohodu zatím není nakonfigurované"** po kliknutí na Synchronizovat → do `.env` na serveru
  chybí některá z `POHODA_URL` / `POHODA_LOGIN` / `POHODA_HESLO` / `POHODA_ICO`. Je to očekávaný stav,
  dokud se Pohoda nenapojí.
- **Po vyplnění přístupů synchronizace spadne (`NotImplementedError`)** → reálné XML volání na mServer
  ještě není naprogramované; samotné vyplnění `.env` nestačí.
- **V tabulce nejsou žádné projekty** → projekty se načítají v Přehledu projektů z Freela; nejdřív je
  potřeba stáhnout je tam.
- **Pohoda mi nepřepsala stav faktury** → faktura je ručně upravená (`upraveno_rucne = True`); automatika
  ji záměrně nechává být. Ruční stav má přednost.
- **Nemůžu editovat / nevidím tlačítka** → chybí právo `finance`; přidělí se v Admin nastavení.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Otevření = editace.** Modul nemá oddělené „čtení" a „editaci" — vše hlídá jediné právo `finance`.
  Kdo modul otevře, může i upravovat, mazat faktury a spouštět synchronizaci. (Odlišné od Přehledu
  projektů, kde je zvlášť čtení a právo `editace`.)
- **Napojení na Pohodu je jen kostra** (`pohoda.py`) — funkce `nacti_faktury_dle_vs` je zatím TODO
  a po nakonfigurování vyhodí `NotImplementedError`. Reálné XML volání (mServer) se teprve doplní.
- **Fakturační pravidla z Freela** (`pravidla.py` → `navrhni_stavy`) jsou zatím **no-op**; pole
  `freelo_faze` a `freelo_task_id` na faktuře se proto v UI nikde nezobrazují ani neplní.
- **Žádné grafy.** Zadání zmiňovalo možné grafy, ale stránka `PrehledFinanci.jsx` žádnou grafovou
  komponentu neimportuje (chart komponenty jako `GrafOdberu`, `GrafVyrobaSpotreba` patří k Nabídkovači).
- **Šířka tabulky** se řídí projektem s nejvíc fakturami (`max_faktur`, minimálně 1 sloupec); ostatní
  projekty mají v přebývajících sloupcích prázdnou buňku s tečkou `·`.
- **VS jako párovací klíč** — variabilní symbol se ručně zapisuje do Freela i sem; přes jeho shodu se
  faktura spáruje s Pohodou. Bez vyplněného VS se faktura s Pohodou spárovat nedá.

## Odkazy
- Kód backend: `backend/app/finance/` · frontend: `frontend/src/pages/PrehledFinanci.jsx`, `frontend/src/components/FakturaDialog.jsx`
- Práva a dlaždice: `backend/app/auth/permissions.py` (klíč `finance`)
- Související modul: [Přehled projektů](./prehled-projektu.md) (zdroj projektů, proklik „💰 Finance")
- Paměť projektu: „Pohled 2 / Přehled financí" (viz `MEMORY.md` → greensie-app-projekt)
