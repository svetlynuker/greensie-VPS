# Disk

> **Sekce v nabídce:** `disk` (skupina **Agenda**) · **Adresa (routa):** `/disk` · **Kdo smí otevřít:** kdokoli s právem `disk` (bez práva se sekce v nabídce vůbec nezobrazí; supersprávce má vždy).
> **Kód:** frontend `frontend/src/pages/Disk.jsx`, backend `backend/app/konektor/disk_routes.py` + `backend/app/konektor/disk_prochazeni.py`

**Firemní Google Disk přímo v appce**, přes celou plochu. Začíná se složkou **o úroveň výš nad
kořenem konektoru** (u nás `8. Raynet`) a dá se dojít až k jednotlivému souboru. Soubor se
**otevře v appce** (PDF, obrázky, texty i Google dokumenty), do otevřené složky se dá **nahrát**
soubor nebo **založit podsložka**, u každé položky se dá vyřídit **sdílení** (kdo k tomu má přístup),
a na každé úrovni je odkaz, kterým se dá odejít na Disk — do té samé složky, ve které člověk právě je.

> 📸 SCREENSHOT: celá obrazovka modulu Disk — lišta s drobečkovou navigací, filtrem a tlačítkem + Nahrát, seznam složek a souborů ve dvou sloupcích

---

## 🧑 Pro uživatele

### K čemu to slouží
Když člověk hledá soubor na firemním Disku, obvykle ví, **kudy** k němu vede cesta (klient → obchodní
případ → podsložka), ale na Disku se k tomu musí proklikat přes cizí rozhraní a hledání mezi všemi
sdílenými disky. Tady je vidět jen firemní struktura od jedné složky dolů — soubor se odsud otevře
a přečte, nahraje, složka založí, nebo se jedním klikem přejde na Disk přímo do té složky.

**Soubory se otevírají v appce, ne přesměrováním na Disk.** Čtou se přes service account konektoru,
takže nezáleží na tom, jakým Google účtem je člověk v prohlížeči přihlášený — a nezáleží ani na tom,
jestli vlastní přístup ke Disku má. Google dokumenty se pro zobrazení převedou na PDF.

Výchozí složka je schválně **o úroveň výš nad kořenem konektoru**: vedle `1. zákazníci` tam leží i
`2. formuláře`, `3. interní dokumentace` a `4. návody`, a právě pro ně to má smysl — ke klientským
složkám vede cesta z CRM, k formulářům a návodům odsud jinak nic.

Je to ta samá věc jako karta **Dokumenty na Disku** na klientovi nebo na obchodním případu, jen bez
omezení na jeden záznam.

### Rozvržení obrazovky
Shora dolů:

1. **Lišta** — tlačítko **← Zpět** (o úroveň výš), **drobečková navigace** (výchozí složka › zákazníci ›
   klient › případ › …), pole **Filtrovat v této složce…**, tlačítka **Obnovit**, **+ Složka**,
   **+ Nahrát** a **Otevřít na Disku ↗**.
2. **Řádek na název nové složky** — ukáže se až po kliknutí na **+ Složka**, jinak tam není.
3. **Seznam** — složky nejdřív, pak soubory, obojí podle názvu. Na širokém monitoru ve dvou sloupcích.
   Soubor přetažený na plochu se nahraje do právě otevřené složky.
4. **Pata seznamu** — kolik je ve složce složek a souborů.
5. **Okno náhledu** — po kliknutí na soubor. Přes většinu obrazovky, s tlačítky **Uložit** a
   **Disk ↗**; zavírá se křížkem, klávesou Esc nebo kliknutím mimo okno.

### Ovládací prvky — políčko po políčku

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět** | lišta vlevo | O jednu úroveň výš. Ve výchozí složce je nedostupné — nad ni se z appky nedostaneš. | všichni s právem `disk` |
| **Drobečková navigace** | lišta | Klik na krok cestu zkrátí a otevře tu úroveň. | všichni s právem `disk` |
| **↗ u kroku cesty** | za každým krokem | Otevře **tuhle úroveň** na Google Disku (nová karta). | všichni s právem `disk` |
| **Filtrovat v této složce…** | lišta vpravo | Nechá v seznamu jen položky, které mají zadaný text v názvu. Po přechodu do jiné složky se filtr sám maže. | všichni s právem `disk` |
| **Obnovit** | lišta vpravo | Přečte obsah složky znovu z Disku (nic se necachuje, ale hodí se po změně na Disku). | všichni s právem `disk` |
| **+ Složka** | lišta vpravo | Otevře řádek na název a založí podsložku v **právě otevřené složce**. Enter založí, Esc zruší. | všichni s právem `disk` |
| **+ Nahrát** | lišta vpravo | Vybere soubory a nahraje je do **právě otevřené složky**. Víc souborů naráz jde. | všichni s právem `disk` |
| **Přetažení souboru na plochu** | celá obrazovka | Totéž jako **+ Nahrát**, jen bez dialogu. Plocha se při přetahování zeleně orámuje. | všichni s právem `disk` |
| **Otevřít na Disku ↗** | lišta vpravo | Otevře **právě zobrazenou složku** na Google Disku. | všichni s právem `disk` |
| **Řádek složky** | seznam | Vejde do složky. | všichni s právem `disk` |
| **Řádek souboru** | seznam | **Otevře soubor v appce** (PDF, obrázek, text, Google dokument). U typů, které appka zobrazit neumí (zip, dwg, video) a u souborů nad 25 MB je za názvem ↗ a řádek vede na Disk. | všichni s právem `disk` |
| **🔒 na konci řádku** | seznam vpravo | Otevře **sdílení** té složky/souboru — kdo k tomu má přístup. | vidí všichni s právem `disk`, mění jen `disk_sdileni` |
| **↗ na konci řádku** | seznam vpravo | Otevře tu složku/soubor na Disku, aniž by se do složky vcházelo nebo otevíral náhled. | všichni s právem `disk` |
| **Uložit** (v náhledu) | okno náhledu | Uloží otevřený soubor k sobě do počítače. | všichni s právem `disk` |
| **Disk ↗** (v náhledu) | okno náhledu | Otevře soubor na Disku — tam se dá i **upravit**, což appka neumí. | všichni s právem `disk` |

### Jak na…

**Najít smlouvu ke klientovi:** výchozí složka → `1. zákazníci` → složka klienta → kontejner
obchodních případů → případ → podsložka. Když je klientů hodně, napiš část jména do
**Filtrovat v této složce…**.

**Otevřít soubor:** klikni na jeho řádek — otevře se v appce. Pro úpravu je v okně **Disk ↗**;
appka soubory needituje.

**Založit složku:** doklikej se tam, kde má vzniknout, klikni **+ Složka**, napiš název a dej Enter.
Lomítko v názvu se změní na „-" (Disk ho nemá rád), takže „2026/revize" vznikne jako jedna složka
`2026-revize`. Dvě složky stejného jména Disk dovolí a appka je nezakazuje.

**Nahrát soubor:** doklikej se do složky, kam soubor patří, a použij **+ Nahrát** (nebo soubor
přetáhni na plochu). Soubor jde přímo na Disk — v appce po něm zůstane jen odkaz, takže nikdy
neexistují dvě kopie. Strop je 25 MB; větší věci (fotodokumentace z realizace) patří na Disk přímo,
appka není přenosová trubka.

**Nahrát dokument ke konkrétnímu klientovi:** dá se i tady, ale přehlednější je karta zákazníka nebo
obchodního případu (*Dokumenty na Disku*) — tam se cílová složka nabídne sama.

**Nasdílet složku nebo soubor někomu:** klikni na 🔒 na jeho řádku. V okně je vidět, kdo k tomu
už má přístup; dole se přidá e-mail a role (**může číst** / **komentovat** / **upravovat**).

Tři věci, které je u sdílení potřeba vědět:

1. **Sdílení složky platí na všechno v ní**, i na podsložky. Tak to má Google Disk — když nasdílíš
   složku klienta, nasdílíš i všechny smlouvy uvnitř.
2. **Pozvánka e-mailem je zaškrtnutá schválně.** Většina našich adres `@greensie.cz` nemá účet Google
   (tým má Disk pod vlastními gmaily) a takovou adresu Disk bez pozvánky **odmítne přidat vůbec**.
   Když zaškrtnutí zrušíš, appka to u takové adresy pozná a napíše, ať pozvánku pošleš.
3. **„Kdokoli s odkazem" appka neumí** a je to záměr — veřejný odkaz na firemní dokument nikdo nevzal
   zpět. Když ho někdo opravdu potřebuje, udělá ho na Disku vědomě.
4. **Vyšší přístup se nepřepisuje.** Když má kolega ze sdíleného disku „může upravovat" a dáš mu tady
   „může číst", Google mu upravování nechá — appka to po přidání napíše, ať to není překvapení.

Přístupy z řádku **Přístup ze sdíleného disku a nadřazených složek** jsou sbalené a odebrat se tady
nedají — dal je někdo výš, tam se musí i sebrat. Přístup konektoru odebrat nejde vůbec: bez něj
přestane fungovat zakládání složek i tenhle modul.

**Filtr nenašel, co hledám:** filtr pracuje **jen s právě otevřenou složkou**, nehledá napříč Diskem.
Na celý Disk je hledání na Disku samotném.

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
Modul je pod samostatným právem **`disk`** („Otevřít Disk"), které se přiděluje v **Admin nastavení**
(skupině nebo jednotlivci). Kdo ho má, může pod výchozí složkou modulu **procházet, otevírat soubory,
nahrávat a zakládat složky**. Právo `konektor` (nastavení konektoru) s tím nemá nic společného; jsou
to dvě různé věci schválně, aby procházení Disku nemuseli mít správci a naopak.

**Měnit sdílení je vlastní právo `disk_sdileni`** („Disk – měnit sdílení složek a souborů“). Kdo ho
nemá, sdílení **vidí** (potřebuje vědět, komu už je dokument dostupný), ale nemění. Odděleno schválně:
„komu se ten dokument otevře“ je rozhodnutí, které jde i mimo firmu a nikdo ho nevezme zpět. Server
právo kontroluje u každé změny, ne jen při kreslení tlačítek.

Pozor: **jinak to odstupňované není** — právo `disk` znamená i právo přidat soubor a složku. A protože se
soubory čtou service accountem, **náhled v appce nekontroluje, jestli má člověk k souboru přístup na
Disku samotném**: rozhoduje jedině právo `disk` a strop modulu. Kdo tedy nemá vidět něco, co pod
stropem leží, nesmí dostat právo `disk` — nebo to patří mimo strop.

Mazání a přejmenování appka neumí vůbec, to se dělá na Disku.

Právo `disk` je jediná branka — kdo ho má, modul se mu otevře. (Do 3. 8. 2026 vedle něj běžel
ještě „přepínač novinek“, který pouštěl jen supersprávce, takže přidělené právo samo nic
neotevřelo. Zrušeno; bez práva se teď vrací 403 s vysvětlením, ne 404.)

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
Jen **Google Drive API v3** (přes service account konektoru, `DriveClient`). Appka **čte, nahrává,
zakládá složky a mění sdílení**, nic nemaže a nepřejmenovává (kromě rušení sdílení). Soubory se u nás neukládají ani po cestě — projdou do Disku a v appce
zůstane jen odkaz, aby neexistovaly dvě kopie téhož dokumentu. Každé nahrání se zapisuje do logu
konektoru jako `disk_nahrani` — v kontextu záznamu je e-mail toho, kdo soubor nahrál, ID složky a ID
souboru, takže je dohledatelné, kdo co kam přidal (tabulka `konektor_log` sloupec pro uživatele nemá,
píše do ní jinak jen automatika).

### Jak to funguje uvnitř (stručně technicky)
- **Datový model:** žádný vlastní. Nastavení se čte z `konektor_nastaveni`.
- **API:**
  - `GET /disk/koren` — výchozí složka modulu (id, název, odkaz na Disk).
  - `GET /disk/obsah?folder_id=<id>` — obsah složky (prázdné `folder_id` = výchozí složka) + cesta
    ke stropu. Každá položka i každý krok cesty nese `url` na Disk.
  - `POST /disk/soubor` (multipart: `soubor`, `folder_id`) — nahrání do složky; prázdné `folder_id`
    = výchozí složka. Strop 25 MB (`disk_prochazeni.MAX_SOUBOR_B`), pak 413.
  - `POST /disk/slozka` (JSON: `nazev`, `folder_id`) — nová podsložka; prázdné `folder_id` = výchozí
    složka. Prázdný název → 422.
  - `GET /disk/prava?item_id=<id>` — kdo má k položce přístup. Každý řádek nese `zdedene`
    (dal ho někdo výš, nejde odebrat tady), `sluzebni` (service account konektoru, nejde odebrat
    vůbec) a `novy` (adresa, která na Disku jinde přístup nemá). V odpovědi je i `znami` — e-maily,
    které Disk zná, aby prohlížeč poznal, že se sdílí někomu novému.
  - `POST /disk/prava` (JSON: `item_id`, `email`, `role`, `oznamit`) — nasdílení. Role jen
    `reader` | `commenter` | `writer` (`owner` a `organizer` appka nenastavuje: na sdíleném disku
    rozdávají práva dál a přes appku je nejde vzít zpět). `oznamit` je **výchozí `true`** — adresy bez
    účtu Google Google bez pozvánky nepřijme. Vyžaduje `disk_sdileni`.
  - `DELETE /disk/prava/{permission_id}?item_id=<id>` — odebrání přístupu. Zděděné oprávnění → 422,
    service account → 422. Vyžaduje `disk_sdileni`.
  - `GET /disk/soubor/{file_id}/nahled` — obsah souboru k zobrazení v appce
    (`Content-Disposition: inline`, `Cache-Control: no-store`). Google formáty přijdou jako PDF
    (`files.export`), ostatní tak, jak jsou (`files.get_media`). Složka → 422, soubor nad 25 MB → 422.
    Ve výpisu položek je proto příznak **`lze_nahled`** — rozhoduje backend, protože jen on ví, co umí
    vyexportovat; prohlížeč by to hádal z přípony.
- **Bezpečnost:** `folder_id` chodí z prohlížeče, takže se u **každého** požadavku — čtení i nahrání —
  ověřuje, že složka leží pod stropem (`crm_slozky.je_pod_slozkou` — leze se po rodičích, jinak to
  Drive API neumí; modul si volá vyšší `MAX_HLOUBKA`, protože počítá od složky o dvě úrovně výš).
  Bez téhle kontroly by appka posloužila jako čtečka i zapisovačka celého firemního Disku. Název
  souboru z prohlížeče jde přes `logika._bezpecny_nazev`, takže „../tajne/x.pdf" skončí jako jeden
  název souboru, ne jako cesta — cíl určuje výhradně `folder_id`.
- **Nic se necachuje:** obsah se čte z Disku při každém kliknutí. Kopie v naší DB by tvrdila, že tam
  soubor je, i když ho někdo mezitím smazal.
- **Klíčové soubory:** `backend/app/konektor/disk_prochazeni.py` (logika), `disk_routes.py` (API),
  `frontend/src/pages/Disk.jsx` (obrazovka), `frontend/src/components/DiskNahled.jsx` (okno náhledu),
  `frontend/src/components/DiskPrava.jsx` (okno sdílení), `frontend/src/styles/disk.css`.

### Časté potíže / co dělat, když…

| Symptom | Příčina | Řešení |
|---|---|---|
| „Na Disk nemáš oprávnění." (403) | Chybí právo `disk`. | Přidělit ho v Admin nastavení — ve skupině, nebo jako osobní výjimku. Nic dalšího se zapínat nemusí. |
| „Konektor na Disk není připravený…" (409) | V Konektoru chybí kořenová složka / sdílený disk nebo service-account JSON. | Doplnit v Konektoru Raynet ↔ Disk a použít **Otestovat spojení**. |
| „Disk neodpověděl…" (502) | Google API vrátilo chybu (přístup, rate limit, výpadek). | Zkusit **Obnovit**; když trvá, podívat se do Logů a do konektoru. |
| „Tato složka neleží pod výchozí složkou modulu Disk." (403) | Ručně dosazené `folder_id` mimo strop, nebo se složka na Disku přesunula jinam. | Vrátit se na výchozí složku (první krok cesty) a projít cestu znovu. |
| „Disk soubor nepřijal…" / „Disk složku nezaložil…" (502) | Google odmítlo zápis (práva service accountu, kvóta). | Zkusit znovu; když trvá, ověřit v Konektoru **Otestovat spojení** a mrknout do Logů. |
| „Složka musí mít název." (422) | Prázdný název nové složky. | Napsat název. |
| „Adresa … nemá účet Google, takže ji Disk pustí jen s pozvánkou." (422) | Sdílení bez pozvánky na adresu bez účtu Google (u nás většina `@greensie.cz`). | Zaškrtnout **poslat pozvánku e-mailem** a poslat znovu. |
| „Tohle oprávnění je zděděné z nadřazené složky…" (422) | Přístup dal někdo na sdíleném disku nebo výš. | Odebrat tam, kde byl daný. |
| „Tohle je přístup konektoru…" (422) | Pokus odebrat service account. | Nedělat to — bez něj přestane fungovat konektor i modul. |
| „Na měnění sdílení na Disku nemáš oprávnění." (403) | Chybí právo `disk_sdileni`. | Přidělit ho v Admin nastavení. |
| „Tohle je složka, ne soubor." (422) | Náhled zavolaný na složku (ručně dosazené ID). | Do složky se vchází kliknutím na řádek. |
| „Soubor je větší než 25 MB — otevři ho prosím na Disku." (422) | Strop náhledu. | Otevřít na Disku (↗ na konci řádku). |
| Soubor se v okně nezobrazí (prázdné okno) | Prohlížeč ten typ neumí zobrazit, i když ho appka poslala. | Použít **Uložit**, nebo **Disk ↗**. |
| „Soubor je větší než 25 MB…" (413) | Strop nahrávání přes appku. | Nahrát ho přímo na Disk (**Otevřít na Disku ↗**). |
| Ve složce chybí položky | Složka má víc položek, než se posílá do prohlížeče (1000). | Zbytek je vidět na Disku — použít **Otevřít na Disku ↗**. |

---

## Poznámky a úskalí (k ověření / nezřejmé)
- Filtr je **jen nad načtenou složkou**, ne hledání přes Disk. Hledání napříč by muselo sahat i mimo
  strop, což je přesně to, co bezpečnostní kontrola brání.
- Načtení složky i nahrání sahá na Google **v požadavku webu**. U složek s tisíci položkami to může
  být pomalé; proto je strop 1000 položek na složku a 25 MB na soubor.
- Nahrání i zakládání složky jde do složky, ve které člověk **právě je** — ne do složky, na kterou se
  dívá v seznamu. Když má soubor patřit do podsložky, je potřeba do ní nejdřív vejít.
- Náhled **teče přes web proces**: soubor se stáhne z Disku do paměti a pošle do prohlížeče. Proto ten
  strop 25 MB. Kdyby si víc lidí naráz otevíralo velké soubory, je to první místo, které bude škrtat.
- V prohlížeči se obsah drží jako `blob:` URL a uvolňuje se při zavření okna. Odkaz na náhled se proto
  nedá poslat kolegovi — na poslání je odkaz na Disk.
- Google dokumenty se zobrazují **jako PDF**, takže tabulky a prezentace vypadají jinak než na Disku.
  Je to jediná podoba, kterou Google vydá a prohlížeč zobrazí bez pluginu.
- Varování „tuhle adresu na Disku nikdo jiný nemá" se **nepozná podle domény**. Doménová kontrola
  (`@greensie.cz` = naše) se zkoušela a označila 17 z 20 kolegů jako cizí, protože tým má Disk pod
  vlastními gmaily a seznam.cz. Varování, které svítí vždycky, si člověk odvykne čítat, takže
  rozhoduje **členství na Disku**, ne text za zavináčem.
- Modul **nikdy nenabízí „kdokoli s odkazem"** ani role `owner`/`organizer`. Kdyby to někdo
  potřeboval, dělá to na Disku — vědomě a na svoje jméno.
- Zrušení sdílení u složky se projeví i na jejím obsahu (dědí se), ale **až pro to, co bylo zděděné**;
  co má někdo přidané u konkrétního souboru zvlášť, zůstává. To je chování Disku, ne appky.
- Výchozí složka se odvozuje z rodiče kořene konektoru. **Kdyby někdo v Konektoru změnil kořenovou
  složku, posune se i výchozí složka modulu** — to je zamýšlené, ale není to na první pohled vidět.

## Odkazy
- Kód: `backend/app/konektor/disk_prochazeni.py`, `backend/app/konektor/disk_routes.py`,
  `frontend/src/pages/Disk.jsx`
- Související dokumentace: [Konektor Raynet ↔ Google Disk](konektor-raynet-gdrive.md),
  [CRM](crm.md) (karta *Dokumenty na Disku*), [Admin nastavení](admin-nastaveni.md) (práva)
