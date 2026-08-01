# Disk

> **Sekce v nabídce:** `disk` (skupina **Agenda**) · **Adresa (routa):** `/disk` · **Kdo smí otevřít:** kdokoli s právem `disk` (bez práva se sekce v nabídce vůbec nezobrazí; supersprávce má vždy). Modul je zatím vedený jako **novinka** — vidí ho jen supersprávce, viz `backend/app/crm/novinky.py`.
> **Kód:** frontend `frontend/src/pages/Disk.jsx`, backend `backend/app/konektor/disk_routes.py` + `backend/app/konektor/disk_prochazeni.py`

**Firemní Google Disk k procházení a nahrávání přímo v appce**, přes celou plochu. Začíná se složkou
**o úroveň výš nad kořenem konektoru** (u nás `8. Raynet`) a dá se dojít až k jednotlivému souboru.
Na každé úrovni je odkaz, kterým se dá z appky odejít na Disk — do té samé složky, ve které člověk
právě je. Do otevřené složky se dá soubor nahrát, tlačítkem nebo přetažením.

> 📸 SCREENSHOT: celá obrazovka modulu Disk — lišta s drobečkovou navigací, filtrem a tlačítkem + Nahrát, seznam složek a souborů ve dvou sloupcích

---

## 🧑 Pro uživatele

### K čemu to slouží
Když člověk hledá soubor na firemním Disku, obvykle ví, **kudy** k němu vede cesta (klient → obchodní
případ → podsložka), ale na Disku se k tomu musí proklikat přes cizí rozhraní a hledání mezi všemi
sdílenými disky. Tady je vidět jen firemní struktura od jedné složky dolů — soubor se odsud otevře,
nahraje, nebo se jedním klikem přejde na Disk přímo do té složky.

Výchozí složka je schválně **o úroveň výš nad kořenem konektoru**: vedle `1. zákazníci` tam leží i
`2. formuláře`, `3. interní dokumentace` a `4. návody`, a právě pro ně to má smysl — ke klientským
složkám vede cesta z CRM, k formulářům a návodům odsud jinak nic.

Je to ta samá věc jako karta **Dokumenty na Disku** na klientovi nebo na obchodním případu, jen bez
omezení na jeden záznam.

### Rozvržení obrazovky
Shora dolů:

1. **Lišta** — tlačítko **← Zpět** (o úroveň výš), **drobečková navigace** (výchozí složka › zákazníci ›
   klient › případ › …), pole **Filtrovat v této složce…**, tlačítka **Obnovit**, **+ Nahrát** a
   **Otevřít na Disku ↗**.
2. **Seznam** — složky nejdřív, pak soubory, obojí podle názvu. Na širokém monitoru ve dvou sloupcích.
   Soubor přetažený na plochu se nahraje do právě otevřené složky.
3. **Pata seznamu** — kolik je ve složce složek a souborů.

### Ovládací prvky — políčko po políčku

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět** | lišta vlevo | O jednu úroveň výš. Ve výchozí složce je nedostupné — nad ni se z appky nedostaneš. | všichni s právem `disk` |
| **Drobečková navigace** | lišta | Klik na krok cestu zkrátí a otevře tu úroveň. | všichni s právem `disk` |
| **↗ u kroku cesty** | za každým krokem | Otevře **tuhle úroveň** na Google Disku (nová karta). | všichni s právem `disk` |
| **Filtrovat v této složce…** | lišta vpravo | Nechá v seznamu jen položky, které mají zadaný text v názvu. Po přechodu do jiné složky se filtr sám maže. | všichni s právem `disk` |
| **Obnovit** | lišta vpravo | Přečte obsah složky znovu z Disku (nic se necachuje, ale hodí se po změně na Disku). | všichni s právem `disk` |
| **+ Nahrát** | lišta vpravo | Vybere soubory a nahraje je do **právě otevřené složky**. Víc souborů naráz jde. | všichni s právem `disk` |
| **Přetažení souboru na plochu** | celá obrazovka | Totéž jako **+ Nahrát**, jen bez dialogu. Plocha se při přetahování zeleně orámuje. | všichni s právem `disk` |
| **Otevřít na Disku ↗** | lišta vpravo | Otevře **právě zobrazenou složku** na Google Disku. | všichni s právem `disk` |
| **Řádek složky** | seznam | Vejde do složky. | všichni s právem `disk` |
| **Řádek souboru** | seznam | Otevře soubor na Disku (nová karta). | všichni s právem `disk` |
| **↗ na konci řádku** | seznam vpravo | Otevře tu složku/soubor na Disku, aniž by se do složky vcházelo. | všichni s právem `disk` |

### Jak na…

**Najít smlouvu ke klientovi:** výchozí složka → `1. zákazníci` → složka klienta → kontejner
obchodních případů → případ → podsložka. Když je klientů hodně, napiš část jména do
**Filtrovat v této složce…**.

**Nahrát soubor:** doklikej se do složky, kam soubor patří, a použij **+ Nahrát** (nebo soubor
přetáhni na plochu). Soubor jde přímo na Disk — v appce po něm zůstane jen odkaz, takže nikdy
neexistují dvě kopie. Strop je 25 MB; větší věci (fotodokumentace z realizace) patří na Disk přímo,
appka není přenosová trubka.

**Nahrát dokument ke konkrétnímu klientovi:** dá se i tady, ale přehlednější je karta zákazníka nebo
obchodního případu (*Dokumenty na Disku*) — tam se cílová složka nabídne sama.

**Filtr nenašel, co hledám:** filtr pracuje **jen s právě otevřenou složkou**, nehledá napříč Diskem.
Na celý Disk je hledání na Disku samotném.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
Modul je pod samostatným právem **`disk`** („Otevřít Disk"), které se přiděluje v **Admin nastavení**
(skupině nebo jednotlivci). Kdo ho má, může procházet **a nahrávat** kamkoli pod výchozí složkou
modulu. Právo `konektor` (nastavení konektoru) s tím nemá nic společného; jsou to dvě různé věci
schválně, aby procházení Disku nemuseli mít správci a naopak.

Pozor: nahrávání není zvlášť — právo `disk` znamená i právo přidat soubor. Mazání a přejmenování
appka neumí vůbec, to se dělá na Disku.

Navíc platí přepínač novinek: dokud `crm/novinky.py` vrací „jen supersprávce", modul se ostatním
neukáže ani s právem (endpointy vrací 404, ne 403 — kdo funkci nemá vidět, pro toho neexistuje).

### Nastavení
Žádné vlastní. Výchozí složka se **odvozuje** z **Konektoru Raynet ↔ Disk**:

1. Vezme se **kořenová složka na Disku** (`google_root_folder_id`) a jde se **o úroveň výš** —
   na jejího rodiče na Disku. U nás tedy z `1. zákazníci` na `8. Raynet`.
2. Když rodič neexistuje (kořen konektoru je sám kořenem sdíleného disku) nebo ho Drive neřekne,
   zůstává výchozí složkou kořen konektoru. Výš než na sdílený disk se nestoupá.
3. Když není nastavená ani kořenová složka, bere se **celý sdílený disk** (`google_shared_drive_id`);
   u Shared Drive je ID disku zároveň ID jeho kořenové složky.
4. Když není ani jedno, modul hlásí, že konektor není připravený (HTTP 409).

Rodič se odvozuje z Disku a **není to druhé políčko v nastavení** schválně: kořen konektoru je jediná
věc, kterou admin nastavuje, a dvě políčka by se mohla rozejít — a pak by nikdo nevěděl, které platí.
Kdyby měl modul jednou začínat někde úplně jinde, je to na nové políčko v Konektoru, ne na ruční
posouvání kořene (na tom závisí zakládání složek pro celý CRM).

**Výchozí složka je zároveň strop.** Nad ni se z appky nedostane nikdo, ani zápisem — takže co leží
mimo ni (mzdy, personální složky), appka nezobrazí a nedovolí do toho nahrát, ani když někdo dosadí
ID do adresy.

### Napojení na okolní systémy
Jen **Google Drive API v3** (přes service account konektoru, `DriveClient`). Appka **čte a nahrává**,
nic nemaže a nepřejmenovává. Soubory se u nás neukládají ani po cestě — projdou do Disku a v appce
zůstane jen odkaz, aby neexistovaly dvě kopie téhož dokumentu. Každé nahrání se zapisuje do logu
konektoru (`disk_nahrani`), takže je dohledatelné, kdo co přidal.

### Jak to funguje uvnitř (stručně technicky)
- **Datový model:** žádný vlastní. Nastavení se čte z `konektor_nastaveni`.
- **API:**
  - `GET /disk/koren` — výchozí složka modulu (id, název, odkaz na Disk).
  - `GET /disk/obsah?folder_id=<id>` — obsah složky (prázdné `folder_id` = výchozí složka) + cesta
    ke stropu. Každá položka i každý krok cesty nese `url` na Disk.
  - `POST /disk/soubor` (multipart: `soubor`, `folder_id`) — nahrání do složky; prázdné `folder_id`
    = výchozí složka. Strop 25 MB (`disk_prochazeni.MAX_SOUBOR_B`), pak 413.
- **Bezpečnost:** `folder_id` chodí z prohlížeče, takže se u **každého** požadavku — čtení i nahrání —
  ověřuje, že složka leží pod stropem (`crm_slozky.je_pod_slozkou` — leze se po rodičích, jinak to
  Drive API neumí; modul si volá vyšší `MAX_HLOUBKA`, protože počítá od složky o dvě úrovně výš).
  Bez téhle kontroly by appka posloužila jako čtečka i zapisovačka celého firemního Disku. Název
  souboru z prohlížeče jde přes `logika._bezpecny_nazev`, takže „../tajne/x.pdf" skončí jako jeden
  název souboru, ne jako cesta — cíl určuje výhradně `folder_id`.
- **Nic se necachuje:** obsah se čte z Disku při každém kliknutí. Kopie v naší DB by tvrdila, že tam
  soubor je, i když ho někdo mezitím smazal.
- **Klíčové soubory:** `backend/app/konektor/disk_prochazeni.py` (logika), `disk_routes.py` (API),
  `frontend/src/pages/Disk.jsx` (obrazovka), `frontend/src/styles/disk.css`.

### Časté potíže / co dělat, když…

| Symptom | Příčina | Řešení |
|---|---|---|
| „Modul Disk pro tebe zatím není zapnutý." | Chybí právo `disk` nebo je modul ještě jen pro supersprávce (novinky). | Přidělit právo v Admin nastavení; otevření všem se dělá v `crm/novinky.py`. |
| „Konektor na Disk není připravený…" (409) | V Konektoru chybí kořenová složka / sdílený disk nebo service-account JSON. | Doplnit v Konektoru Raynet ↔ Disk a použít **Otestovat spojení**. |
| „Disk neodpověděl…" (502) | Google API vrátilo chybu (přístup, rate limit, výpadek). | Zkusit **Obnovit**; když trvá, podívat se do Logů a do konektoru. |
| „Tato složka neleží pod výchozí složkou modulu Disk." (403) | Ručně dosazené `folder_id` mimo strop, nebo se složka na Disku přesunula jinam. | Vrátit se na výchozí složku (první krok cesty) a projít cestu znovu. |
| „Disk soubor nepřijal…" (502) | Google odmítlo zápis (práva service accountu, kvóta). | Zkusit znovu; když trvá, ověřit v Konektoru **Otestovat spojení** a mrknout do Logů. |
| „Soubor je větší než 25 MB…" (413) | Strop nahrávání přes appku. | Nahrát ho přímo na Disk (**Otevřít na Disku ↗**). |
| Ve složce chybí položky | Složka má víc položek, než se posílá do prohlížeče (1000). | Zbytek je vidět na Disku — použít **Otevřít na Disku ↗**. |

---

## Poznámky a úskalí (k ověření / nezřejmé)
- Filtr je **jen nad načtenou složkou**, ne hledání přes Disk. Hledání napříč by muselo sahat i mimo
  strop, což je přesně to, co bezpečnostní kontrola brání.
- Načtení složky i nahrání sahá na Google **v požadavku webu**. U složek s tisíci položkami to může
  být pomalé; proto je strop 1000 položek na složku a 25 MB na soubor.
- Nahrání jde do složky, ve které člověk **právě je** — ne do složky, na kterou se dívá v seznamu.
  Když má soubor patřit do podsložky, je potřeba do ní nejdřív vejít.
- Výchozí složka se odvozuje z rodiče kořene konektoru. **Kdyby někdo v Konektoru změnil kořenovou
  složku, posune se i výchozí složka modulu** — to je zamýšlené, ale není to na první pohled vidět.

## Odkazy
- Kód: `backend/app/konektor/disk_prochazeni.py`, `backend/app/konektor/disk_routes.py`,
  `frontend/src/pages/Disk.jsx`
- Související dokumentace: [Konektor Raynet ↔ Google Disk](konektor-raynet-gdrive.md),
  [CRM](crm.md) (karta *Dokumenty na Disku*), [Admin nastavení](admin-nastaveni.md) (práva)
