# Disk

> **Sekce v nabídce:** `disk` (skupina **Agenda**) · **Adresa (routa):** `/disk` · **Kdo smí otevřít:** kdokoli s právem `disk` (bez práva se sekce v nabídce vůbec nezobrazí; supersprávce má vždy). Modul je zatím vedený jako **novinka** — vidí ho jen supersprávce, viz `backend/app/crm/novinky.py`.
> **Kód:** frontend `frontend/src/pages/Disk.jsx`, backend `backend/app/konektor/disk_routes.py` + `backend/app/konektor/disk_prochazeni.py`

**Firemní Google Disk k procházení přímo v appce**, přes celou plochu. Začíná se kořenovou složkou,
která je nastavená v Konektoru, a dá se dojít až k jednotlivému souboru. Na každé úrovni je odkaz,
kterým se dá z appky odejít na Disk — do té samé složky, ve které člověk právě je.

> 📸 SCREENSHOT: celá obrazovka modulu Disk — lišta s drobečkovou navigací a filtrem, seznam složek a souborů ve dvou sloupcích

---

## 🧑 Pro uživatele

### K čemu to slouží
Když člověk hledá soubor na firemním Disku, obvykle ví, **kudy** k němu vede cesta (klient → obchodní
případ → podsložka), ale na Disku se k tomu musí proklikat přes cizí rozhraní a hledání mezi všemi
sdílenými disky. Tady je vidět jen firemní struktura CRM od jednoho kořene dolů — a když je potřeba
soubor otevřít, upravit nebo něco nahrát, jedním klikem se přejde na Disk přímo do té složky.

Je to ta samá věc jako karta **Dokumenty na Disku** na klientovi nebo na obchodním případu, jen bez
omezení na jeden záznam.

### Rozvržení obrazovky
Shora dolů:

1. **Lišta** — tlačítko **← Zpět** (o úroveň výš), **drobečková navigace** (kořen › klient › případ › …),
   pole **Filtrovat v této složce…**, tlačítko **Obnovit** a vpravo **Otevřít na Disku ↗**.
2. **Seznam** — složky nejdřív, pak soubory, obojí podle názvu. Na širokém monitoru ve dvou sloupcích.
3. **Pata seznamu** — kolik je ve složce složek a souborů.

### Ovládací prvky — políčko po políčku

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět** | lišta vlevo | O jednu úroveň výš. V kořeni je nedostupné — nad kořen se z appky nedostaneš. | všichni s právem `disk` |
| **Drobečková navigace** | lišta | Klik na krok cestu zkrátí a otevře tu úroveň. | všichni s právem `disk` |
| **↗ u kroku cesty** | za každým krokem | Otevře **tuhle úroveň** na Google Disku (nová karta). | všichni s právem `disk` |
| **Filtrovat v této složce…** | lišta vpravo | Nechá v seznamu jen položky, které mají zadaný text v názvu. Po přechodu do jiné složky se filtr sám maže. | všichni s právem `disk` |
| **Obnovit** | lišta vpravo | Přečte obsah složky znovu z Disku (nic se necachuje, ale hodí se po změně na Disku). | všichni s právem `disk` |
| **Otevřít na Disku ↗** | lišta vpravo | Otevře **právě zobrazenou složku** na Google Disku. | všichni s právem `disk` |
| **Řádek složky** | seznam | Vejde do složky. | všichni s právem `disk` |
| **Řádek souboru** | seznam | Otevře soubor na Disku (nová karta). | všichni s právem `disk` |
| **↗ na konci řádku** | seznam vpravo | Otevře tu složku/soubor na Disku, aniž by se do složky vcházelo. | všichni s právem `disk` |

### Jak na…

**Najít smlouvu ke klientovi:** kořen → složka klienta → kontejner obchodních případů → případ →
podsložka. Když je klientů hodně, napiš část jména do **Filtrovat v této složce…**.

**Nahrát soubor:** tady ne — nahrávání je na **kartě zákazníka nebo obchodního případu**
(karta *Dokumenty na Disku*), kde je jasné, ke komu soubor patří. Odsud se dá jedním klikem
(**Otevřít na Disku ↗**) přejít do složky na Disku a nahrát ho tam.

**Filtr nenašel, co hledám:** filtr pracuje **jen s právě otevřenou složkou**, nehledá napříč Diskem.
Na celý Disk je hledání na Disku samotném.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
Modul je pod samostatným právem **`disk`** („Otevřít Disk"), které se přiděluje v **Admin nastavení**
(skupině nebo jednotlivci). Právo je jen otevírací — kdo ho má, může procházet celý obsah pod
kořenovou složkou konektoru. Právo `konektor` (nastavení konektoru) s tím nemá nic společného; jsou
to dvě různé věci schválně, aby procházení Disku nemuseli mít správci a naopak.

Navíc platí přepínač novinek: dokud `crm/novinky.py` vrací „jen supersprávce", modul se ostatním
neukáže ani s právem (endpointy vrací 404, ne 403 — kdo funkci nemá vidět, pro toho neexistuje).

### Nastavení
Žádné vlastní. Kořen bere z **Konektoru Raynet ↔ Disk**:

1. **Kořenová složka na Disku** (`google_root_folder_id`) — odkud modul začíná.
2. Když není nastavená, bere se **celý sdílený disk** (`google_shared_drive_id`); u Shared Drive je
   ID disku zároveň ID jeho kořenové složky.
3. Když není ani jedno, modul hlásí, že konektor není připravený (HTTP 409).

**Kořen je zároveň strop viditelnosti.** Nad něj se z appky nedostane nikdo — takže pokud na Disku
leží mimo tenhle kořen věci, které nemá vidět celá firma (mzdy, personální složky), je to v pořádku:
appka je nezobrazí, ani když někdo dosadí jejich ID do adresy.

### Napojení na okolní systémy
Jen **Google Drive API v3** (přes service account konektoru, `DriveClient`). Appka **nic nezapisuje**
a nic si neukládá — je to čtení a rozcestník na Disk. Soubory nikdy neprocházejí naší databází.

### Jak to funguje uvnitř (stručně technicky)
- **Datový model:** žádný vlastní. Nastavení se čte z `konektor_nastaveni`.
- **API:**
  - `GET /disk/koren` — kořenová složka konektoru (id, název, odkaz na Disk).
  - `GET /disk/obsah?folder_id=<id>` — obsah složky (prázdné `folder_id` = kořen) + cesta ke kořeni.
    Každá položka i každý krok cesty nese `url` na Disk.
- **Bezpečnost:** `folder_id` chodí z prohlížeče, takže se u **každého** požadavku ověřuje, že složka
  leží pod kořenem konektoru (`crm_slozky.je_pod_slozkou` — leze se po rodičích, jinak to Drive API
  neumí). Bez téhle kontroly by appka posloužila jako čtečka celého firemního Disku.
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
| „Tato složka neleží pod kořenovou složkou konektoru." (403) | Ručně dosazené `folder_id` mimo kořen, nebo se složka na Disku přesunula jinam. | Vrátit se na kořen (první krok cesty) a projít cestu znovu. |
| Ve složce chybí položky | Složka má víc položek, než se posílá do prohlížeče (500). | Zbytek je vidět na Disku — použít **Otevřít na Disku ↗**. |

---

## Poznámky a úskalí (k ověření / nezřejmé)
- Filtr je **jen nad načtenou složkou**, ne hledání přes Disk. Hledání napříč by muselo sahat i mimo
  kořen, což je přesně to, co bezpečnostní kontrola brání.
- Načtení složky sahá na Google **v požadavku webu**. U složek s tisíci položkami to může být pomalé;
  proto je strop 500 položek na složku.
- Nahrávání tady vědomě není — soubor „někam do firemního Disku" by neměl majitele. Patří na kartu
  záznamu.

## Odkazy
- Kód: `backend/app/konektor/disk_prochazeni.py`, `backend/app/konektor/disk_routes.py`,
  `frontend/src/pages/Disk.jsx`
- Související dokumentace: [Konektor Raynet ↔ Google Disk](konektor-raynet-gdrive.md),
  [CRM](crm.md) (karta *Dokumenty na Disku*), [Admin nastavení](admin-nastaveni.md) (práva)
