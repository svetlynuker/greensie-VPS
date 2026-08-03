# Admin nastavení

> **Sekce v nabídce:** `admin` · **Adresa (routa):** `/admin` · **Kdo smí otevřít:** jen kdo má právo `admin` (supersprávce ho má vždy). Bez práva se sekce v nabídce vlevo vůbec nezobrazí.
> **Kód:** frontend `frontend/src/pages/AdminNastaveni.jsx` (+ `frontend/src/components/FirmaNastaveni.jsx`), backend `backend/app/admin/` (+ `backend/app/auth/permissions.py`, `backend/app/auth/models.py`); údaje o firmě `backend/app/crm/nastaveni_crm.py`; nastavení synchronizace `backend/app/matice/routes.py`.

Evidence **naší firmy**, centrální správa **uživatelů, skupin a práv** celé appky, **reset hesel** a **nastavení automatické synchronizace s Freelem**. Slouží správci systému (supersprávci nebo komukoli s právem `admin`).

> 📸 SCREENSHOT: Admin nastavení se záložkami Firma / Uživatelé / Skupiny a práva / Přehled projektů

---

## 🧑 Pro uživatele

Uživatelem se zde myslí **administrátor** — jen ten stránku otevře.

### K čemu to slouží
Na jednom místě zakládáš a upravuješ **účty zaměstnanců**, přiděluješ jim **práva** (co smí v appce otevřít a dělat) buď jednotlivě, nebo přes **skupiny**, a **resetuješ hesla**, když je někdo zapomene. Poslední záložka řídí, jak často a co si má appka **sama stahovat z Freela** do Přehledu projektů.

### Rozvržení obrazovky — záložky
Nastavení je rozdělené do **záložek, jedna na každou spravovanou věc**. Dřív byly tři karty pod
sebou a stránka se musela rolovat; teď se přepíná nahoře a vidí se jen to, co člověk právě řeší.

| Záložka | Co v ní je |
|---|---|
| **Firma** | údaje o nás jako o Greensie + automatický seznam interních kontaktů |
| **Uživatelé** (s počtem) | tabulka všech účtů ve vlastním okně se scrollem, tlačítko *+ Přidat uživatele* |
| **Skupiny a práva** (s počtem) | seznam skupin s jejich právy, tlačítko *+ Přidat skupinu* |
| **Přehled projektů** | nastavení automatické synchronizace s Freelem (viz Pro admina / provoz) |

**Firma je první schválně** — je to identita, ze které vychází všechno ostatní (nabídky, podpis
pošty, adresa u schůzek), takže se otevírá jako výchozí záložka.

### Záložka Firma — údaje o nás

Jedno místo, kde je evidovaná **naše firma**. Údaje jsou rozdělené do sekcí:

| Sekce | Co se vyplňuje |
|---|---|
| **Identifikace** | název, IČO, DIČ, plátce DPH, soud a spisová značka zápisu v OR |
| **Adresa sídla** | ulice a číslo, PSČ, město, stát |
| **Korespondenční adresa** | zaškrtávátko *Stejná jako sídlo*; když se odškrtne, objeví se vlastní políčka |
| **Kontakt** | telefon, e-mail, web, datová schránka |
| **Bankovní spojení** | banka, číslo účtu, IBAN, SWIFT/BIC |
| **Statutární orgán** | jméno a funkce |
| **Poznámka** | volný text |

U Identifikace je tlačítko **„Doplnit z ARES podle IČO"** — vyplní název, DIČ a sídlo z veřejného
registru, takže se nic nepřepisuje ručně. Když ARES neodpoví, napíše to jako poznámku (ne jako
červenou chybu) a údaje se dají dopsat rukou.

**Adresa sídla je zároveň to, co nabídne tlačítko „U nás"** u místa konání schůzky v kalendáři —
appka si z ní skládá jednořádkovou adresu. Proto se ta adresa nepíše na dvou místech: opraví se
tady a všude jinde se to projeví samo.

**Kdo to smí měnit:** vedení s právem `crm_nastaveni` nebo supersprávce. Kdo právo nemá, údaje
**vidí** (potřebuje je appka i pro nabídky), ale políčka má zamčená a tlačítko Uložit nevidí.

> **Proč Greensie není záznam v Zákaznících:** vlastní firma by lezla do každého filtru, do
> statistik pipeline i do výběru „komu nabídku". Naše identita je konfigurace appky, ne obchodní
> záznam — proto má vlastní záložku a ne kartu klienta.

### Záložka Firma — interní kontakty

Pod údaji je tabulka **našich lidí**: jméno, funkce, telefon, e-mail a skupina. Seznam se plní
**sám z uživatelů appky** — nic se do něj nezadává. Kdo přijde nebo odejde, řeší se v záložce
Uživatelé (je tam na to i tlačítko) a Firma to hned ukáže.

Funkce a telefon se berou z **osobního profilu** (ten, který si člověk vyplňuje pro podpis do
e-mailu, viz Nastavení → Podpis). Prázdná funkce nebo telefon tedy znamená „ten člověk si profil
ještě nevyplnil", ne chybu. Druhá, ruční evidence lidí tu schválně není — rozešla by se s tou první.

Nad záložkami je jen odkaz **„← Zpět na rozcestník"**; nadpis stránky nese horní lišta appky, tak
se tu nedubluje. Až přijdou nastavení dalších modulů, přidají se jako další záložka — proto se
záložka jmenuje po modulu (**Přehled projektů**), ne po technologii (~~Freelo~~).

Úpravy uživatele, skupiny, reset hesla i zobrazení vygenerovaného hesla se dějí ve **vyskakovacím okně (modalu)** nad stránkou.

> 📸 SCREENSHOT: záložka Uživatelé s tabulkou účtů a tlačítkem „+ Přidat uživatele"

### Ovládací prvky — políčko po políčku

Celou stránku i všechna její tlačítka vidí **jen administrátor** (kdo má právo `admin`); ostatní se sem vůbec nedostanou. Ve sloupci „Kdo vidí" proto rozlišuji jen jemnější pojistky.

#### Záložka Uživatelé — tabulka

| Prvek | Kde | Co dělá |
|---|---|---|
| **+ Přidat uživatele** | nad tabulkou | Otevře okno pro založení nového účtu |
| **Počítadlo `(N)`** | v záložce | Kolik je celkem uživatelů |
| Sloupec **Jméno** | tabulka | Jméno uživatele |
| Sloupec **E-mail** | tabulka | Přihlašovací e-mail |
| Sloupec **Přístup** | tabulka | Štítek **Supersprávce**, nebo text *Uživatel*; pod tím se u čekajících účtů ukáže „🔑 čeká na změnu hesla" |
| Sloupec **Skupina** | tabulka | Název skupiny uživatele, nebo „—" |
| Sloupec **Práva navíc** | tabulka | Barevné štítky práv přidělených jednotlivě (mimo skupinu), nebo „—" |
| **Upravit** | sloupec Akce | Otevře okno úpravy účtu |
| **Reset hesla** | sloupec Akce | Otevře okno pro reset hesla |
| **Smazat** | sloupec Akce | Po potvrzení smaže účet (s pojistkami — viz níže) |

#### Okno „Přidat / Upravit uživatele"

| Pole | Co dělá |
|---|---|
| **Jméno** | Jméno uživatele (povinné) |
| **E-mail** | Přihlašovací e-mail (povinný, ukládá se malými písmeny, musí být unikátní) |
| *(info o hesle)* | Jen u nového účtu: upozornění, že heslo se vygeneruje automaticky a pošle uživateli |
| **Supersprávce** (zaškrtávátko) | Zapne plný přístup ke všemu. Když je zaškrtnuté, sekce Skupina + Práva se **zešedne a zamkne** (u supersprávce se ignorují). **Na jednotlivé moduly ho nepotřebuješ** — stačí zaškrtnout právo níž |
| **Skupina** (rozbalovací) | Přiřadí uživatele do skupiny (dědí její práva); „— žádná —" = bez skupiny |
| **Práva** | Zaškrtávátka jednotlivých práv z katalogu. Co člověk **dědí ze skupiny**, je zaškrtnuté, zamčené a označené „ze skupiny" — odebírá se ve skupině, ne tady. Ostatní zaškrtnutá jsou osobní výjimky nad rámec skupiny |
| *(souhrn pod právy)* | „Výsledně bude mít N práv (X ze skupiny, Y navíc)" — kolik práv člověk po uložení opravdu bude mít |
| **Zrušit / Uložit** | Zavře bez uložení / uloží |

> **Zaškrtnuté právo modul opravdu otevře.** Nic dalšího se nezapíná. Do 3. 8. 2026
> to tak nebylo: u nových modulů (E-mail, Disk, Mapa) běžela vedle práva ještě
> druhá branka, která pouštěla jen supersprávce — právo se přidělilo, uložilo,
> a člověku se pořád nic neukázalo. Ta branka je zrušená.

> 📸 SCREENSHOT: okno „Upravit uživatele" s přepínačem Supersprávce, výběrem skupiny a zaškrtávátky práv

#### Okno „Reset hesla"

| Prvek | Co dělá |
|---|---|
| **Vygenerovat nové heslo** (přepínač) | Server vytvoří náhodné jednorázové heslo |
| **Zadat vlastní heslo** (přepínač) | Umožní zadat heslo ručně (pole se objeví po volbě; minimálně 6 znaků) |
| **Zrušit / Resetovat heslo** | Zavře / provede reset |

Po resetu si uživatel při dalším přihlášení **musí zvolit vlastní heslo**.

#### Okno „Přihlašovací údaje" (po vytvoření účtu / resetu)

Zobrazí se **jednorázové heslo**, odkaz na appku a e-mail. Heslo se **ukáže jen teď** — je potřeba si ho zkopírovat.

| Prvek | Co dělá |
|---|---|
| **Kopírovat údaje** | Zkopíruje odkaz + e-mail + heslo do schránky |
| Řádek o e-mailu | Napíše, zda se údaje podařilo odeslat uživateli e-mailem, nebo proč ne |
| **Hotovo** | Zavře okno |

> 📸 SCREENSHOT: okno „Přihlašovací údaje" s vygenerovaným heslem a tlačítkem „Kopírovat údaje"

#### Záložka Skupiny a práva

| Prvek | Kde | Co dělá |
|---|---|---|
| **+ Přidat skupinu** | nad seznamem | Otevře okno pro založení skupiny |
| **Počítadlo `(N)`** | v záložce | Kolik je skupin |
| **Název skupiny** | řádek skupiny | Název + počet členů |
| Štítky práv | řádek skupiny | Barevné štítky práv skupiny (nebo „žádná práva") |
| **Upravit** | řádek skupiny | Otevře okno úpravy |
| **Smazat** | řádek skupiny | Po potvrzení skupinu smaže (členům se skupina odebere) |

Okno **„Přidat / Upravit skupinu"** má pole **Název skupiny** a seznam zaškrtávátek **„Co smí členové skupiny"** (katalog práv).

> 📸 SCREENSHOT: záložka Skupiny a práva se dvěma skupinami a jejich štítky práv

### Jak na…

- **Jak přidat uživatele:** záložka Uživatelé → *+ Přidat uživatele* → vyplň Jméno a E-mail → případně nastav Supersprávce / Skupinu / Práva navíc → *Uložit*. Objeví se okno s **jednorázovým heslem** — zkopíruj ho a předej uživateli (pokud je nastavený e-mail, appka ho pošle sama). Uživatel si při prvním přihlášení nastaví vlastní heslo.
- **Jak resetovat heslo:** u řádku uživatele *Reset hesla* → vyber *Vygenerovat nové heslo* (nebo *Zadat vlastní heslo*) → *Resetovat heslo* → zkopíruj z okna nové heslo. Uživatel si při dalším přihlášení nastaví vlastní.
- **Jak vytvořit skupinu a přidělit práva:** záložka Skupiny a práva → *+ Přidat skupinu* → zadej název (např. „Vedení") → zaškrtej, co smí členové otevřít/dělat → *Uložit*. Pak u uživatele *Upravit* → vyber tuto skupinu.
- **Jak dát jednomu člověku právo navíc:** *Upravit* uživatele → v sekci **Práva navíc** zaškrtni konkrétní právo (např. „Otevřít Přehled financí") → *Uložit*. Nemusíš kvůli tomu zakládat skupinu.
- **Jak z někoho udělat správce:** *Upravit* → zaškrtni **Supersprávce** → *Uložit*. Získá přístup ke všemu; skupina a práva navíc se u něj ignorují.

---

## 🛠 Pro admina / provoz

### Model práv — kdo co smí
Efektivní práva uživatele počítá `prava_uzivatele` (`backend/app/auth/permissions.py`):

- **Supersprávce** (`uzivatel.je_admin = true`) → má **všechna práva**, skupina a `extra_prava` se ignorují.
- **Ostatní** → **`extra_prava` ∪ `skupina.prava`** (individuální práva sjednocená s právy skupiny).

Klíčové funkce:
- `muze_otevrit(user, klic)` — smí uživatel otevřít danou sekci (klíč práva = klíč sekce).
- `muze_editovat(user)` — má právo `editace` (editace matice v Přehledu projektů).
- `vyzaduj_admina` — FastAPI závislost, která pustí dál jen toho, kdo `muze_otevrit(..., "admin")`; jinak vrátí **403**. Chrání **celý** router `/admin` i endpointy `/matice/sync-nastaveni`.

### Katalog práv (`PRAVA`)
Práva se dělí na **otevírací** (stejný klíč jako sekce v nabídce) a **akční**:

| Klíč | Název v UI | Typ |
|---|---|---|
| `projekty` | Otevřít Přehled projektů | otevírací |
| `finance` | Otevřít Přehled financí | otevírací |
| `zmeny` | Otevřít Přehled změn | otevírací |
| `nabidkovac` | Nabídkovač – vytvářet/upravovat nabídky (OZ) | otevírací |
| `nabidkovac_katalog` | Nabídkovač – editace katalogu a výpočtů (vedení) | akční |
| `admin` | Otevřít Admin nastavení | otevírací |
| `editace` | Editace matice (Přehled projektů) | akční |
| `logy` | Otevřít Logy (provoz, chyby, audit) | otevírací |
| `konektor` | Otevřít Konektor Raynet ↔ Google Disk | otevírací |

### Dlaždice (`DLAZDICE`) — pozůstatek
Historický katalog položek starého dlaždicového rozcestníku: `projekty`, `finance`, `zmeny`, `nabidkovac`, `admin`, `logy`, `konektor`. **Frontend ho už nepoužívá** — nabídku vlevo skládá z pole `prava` (viz `frontend/src/navigace.js`) a sekce bez práva se vůbec nezobrazí. Katalog zůstal v `permissions.py` a `GET /auth/me` ho dál vrací, aby se nerozbilo API.

### Pojistky
- **Nelze smazat sám sebe** — mazání účtu, který právě mažeš pod svým přihlášením, vrátí 409 („Nemůžeš smazat sám sebe.").
- **Nelze smazat posledního admina** — když by to byl poslední supersprávce (`_pocet_adminu(db) <= 1`), server odmítne (409).
- **Nelze odebrat supersprávce poslednímu adminovi** — při úpravě účtu, který je posledním adminem, nejde odškrtnout Supersprávce (409).
- **Supersprávce může nastavit jen supersprávce** — právo `admin` může mít i nesupersprávce, ale zaškrtnutí/odškrtnutí **Supersprávce** mu server odmítne (403). Jinak by si držitel práva `admin` sám udělal plný přístup do všeho a katalog práv by nic neznamenal.
- **Osobní výjimky se ukládají očištěné** — co člověk dědí ze skupiny, se do `extra_prava` neuloží podruhé (`_jen_navic`). Duplikát nic nepřidával, ale bránil odebrání: právo odebrané ze skupiny zůstalo ve výjimkách a odebrání se navenek „neprovedlo". Stejné očištění proběhne i při **úpravě skupiny** (u všech členů) a jednorázově při startu backendu.
- **Unikátní e-mail** — dva účty se stejným e-mailem nejdou (409); e-mail se normalizuje na malá písmena.
- **Unikátní název skupiny** — duplicitní název skupiny je 409.
- **Kontrola práv** — přiřazovaná práva musí být z katalogu, jinak 422 („Neznámá práva: …"). Neexistující skupina → 422.

### Hesla
- Nový uživatel dostane **náhodné jednorázové heslo** (`vygeneruj_heslo`, 10 znaků z čitelné abecedy bez záměnných dvojic 0/O, 1/l/I). Nastaví se mu `musi_zmenit_heslo = true`.
- **Reset hesla** buď vygeneruje náhodné, nebo přijme ručně zadané (min. 6 znaků); vždy nastaví `musi_zmenit_heslo = true`.
- Heslo se ukládá jen jako **hash** (bcrypt). Jednorázové heslo v čitelné podobě se adminovi ukáže **jen jednou** v odpovědi na vytvoření/reset a appka se ho pokusí poslat i e-mailem (best-effort — když SMTP není nastaven nebo selže, akce se nezruší, jen se to oznámí).
- Uživatel s `musi_zmenit_heslo = true` je při vstupu do appky přesměrován na změnu hesla (v `AdminNastaveni.jsx` i `/zmena-hesla`).

### Datový model (`backend/app/auth/models.py`)
- **`uzivatele`** — `id`, `jmeno`, `email` (unikát), `heslo_hash`, `je_admin`, `musi_zmenit_heslo`, `skupina_id` (FK na `skupiny`, při smazání skupiny `SET NULL`), `extra_prava` (pole klíčů práv).
- **`skupiny`** — `id`, `nazev` (unikát), `prava` (pole klíčů práv). Relace 1:N na uživatele (`clenove`).

### API (`backend/app/admin/routes.py`, prefix `/admin`, celé pod `vyzaduj_admina`)

| Metoda + cesta | Účel |
|---|---|
| `GET /admin/ciselniky` | Katalog přidělitelných práv (klíč + název) pro zaškrtávátka |
| `GET /admin/uzivatele` | Seznam uživatelů (bez hesla) |
| `POST /admin/uzivatele` | Založí uživatele; vrátí jednorázové heslo + stav odeslání e-mailu |
| `PUT /admin/uzivatele/{id}` | Upraví jméno, e-mail, supersprávce, skupinu, práva navíc |
| `POST /admin/uzivatele/{id}/reset-hesla` | Reset hesla (náhodné, nebo vlastní); vrátí nové heslo |
| `DELETE /admin/uzivatele/{id}` | Smaže uživatele (pojistky výše) |
| `GET /admin/skupiny` | Seznam skupin (+ počet členů) |
| `POST /admin/skupiny` | Založí skupinu |
| `PUT /admin/skupiny/{id}` | Upraví název a práva skupiny |
| `DELETE /admin/skupiny/{id}` | Smaže skupinu (členům se odebere) |

**Bezpečnost:** odpovědi o uživateli (`UzivatelOut`) obsahují jen `id, jmeno, email, je_admin, musi_zmenit_heslo, skupina_id, extra_prava`. **`heslo_hash` se nikdy nevrací.** Jednorázové čitelné heslo je jen v odpovědi na vytvoření/reset (`HesloVysledek`).

### Nastavení automatické synchronizace s Freelem
Poslední karta na stránce; volá endpointy modulu Přehled projektů (matice):

| Metoda + cesta | Účel |
|---|---|
| `GET /matice/sync-nastaveni` | Načte aktuální nastavení (jen admin) |
| `PUT /matice/sync-nastaveni` | Uloží nastavení (jen admin; `interval_min < 5` → 422) |

Ovládací prvky karty a jejich klíče (tabulka `nastaveni_synchronizace`, jeden řádek `id=1`):

| Prvek v UI | Klíč | Výchozí | Význam |
|---|---|---|---|
| Zapnout automatickou synchronizaci | `auto_zapnuto` | zapnuto | Zda plánovač na serveru vůbec běží |
| Spouštět každých … minut | `interval_min` | 60 | Interval v minutách (nejméně 5) |
| Stav (hotovo / nehotovo) | `sync_stav` | zapnuto | Přepsat stav úkolu podle Freela |
| Nové úkoly z Freela | `sync_nove_ukoly` | zapnuto | Zakládat nové sloupce/buňky |
| Nové projekty z Freela | `sync_nove_projekty` | zapnuto | Zakládat nové projekty |
| Termíny | `sync_terminy` | vypnuto | Přepsat termín podle Freela (i ručně zadaný) |
| Odpovědné osoby | `sync_osoby` | vypnuto | Přepsat osobu podle Freela (i ručně zadanou) |
| Zapisovat změnu stavu zpět do Freela | `zapis_stav_do_freela` | zapnuto | Obousměrně: změna stavu v tabulce se propíše i do Freela |

**Pravidlo:** zaškrtnuté pole = „Freelo vyhrává" a přepíše i ručně zadanou hodnotu; nezaškrtnuté zůstává beze změny. **Poznámka se nepřepisuje nikdy.** Pod tlačítkem *Uložit nastavení* se ukazuje čas a výsledek posledního běhu (`posledni_beh`, `posledni_vysledek`). Podrobnosti o plánovači viz dokumentace Přehledu projektů.

### Klíčové soubory
- Frontend: `frontend/src/pages/AdminNastaveni.jsx` (karty, okna, tabulky), `frontend/src/api.js` (funkce `admin*`, `getSyncNastaveni`, `ulozSyncNastaveni`), `frontend/src/App.jsx` (routa `/admin`).
- Backend: `backend/app/admin/routes.py` + `schemas.py`, `backend/app/auth/permissions.py` (`PRAVA`, `DLAZDICE`, `prava_uzivatele`, `muze_otevrit`, `muze_editovat`, `vyzaduj_admina`, `vygeneruj_heslo`, `hash_heslo`), `backend/app/auth/models.py` (`User`, `Skupina`), `backend/app/matice/routes.py` (sync-nastaveni), `backend/app/mailer.py` (odeslání údajů e-mailem).

### Časté potíže / co dělat, když…
- **Stránka hlásí „Chyba: … 403"** → uživatel nemá právo `admin`. Přidej mu ho (jako supersprávce, přes skupinu, nebo přes práva navíc).
- **„Uživatel s tímto e-mailem už existuje" / „…už existuje"** → e-mail nebo název skupiny musí být unikátní.
- **„Nelze smazat posledního admina" / „Nemůžeš smazat sám sebe."** → pojistky; nech aspoň jednoho supersprávce a nemaž vlastní účet.
- **Uživatel nedostal přihlašovací e-mail** → SMTP nemusí být nastaven (`SMTP_HESLO` v `.env`). Heslo z okna zkopíruj a předej ručně.
- **Uživatel se nemůže dostat dál po přihlášení** → má `musi_zmenit_heslo = true` a je veden na změnu hesla; to je záměr.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- Stránka i všechny endpointy `/admin` jsou chráněné právem `admin`, ne příznakem `je_admin` — právo `admin` může mít i nesupersprávce (přes skupinu / práva navíc), a pak plnohodnotně spravuje uživatele. Supersprávce (`je_admin`) je nadmnožina (má všechna práva včetně `admin`).
- Katalog práv je „napevno" v kódu (`permissions.py`), nedá se měnit z UI; struktura nabídky
  je stejně tak napevno na frontendu (`navigace.js`).
- Karta Synchronizace patří logicky do Přehledu projektů (endpointy `/matice/…`), ale UI žije zde. Nastavení je globální (jeden řádek pro celou firmu).
- Přesné chování jednotlivých přepínačů synchronizace (co přesně přepisují při běhu plánovače) je popsáno u modulu Přehled projektů — zde je jen ovládání.

## Odkazy
- Kód backend: `backend/app/admin/`, `backend/app/auth/permissions.py`, `backend/app/auth/models.py` · frontend: `frontend/src/pages/AdminNastaveni.jsx`
- Související dokumentace:
  - Přihlášení a změna hesla — `prihlaseni-zmena-hesla.md` (jednorázová hesla, `musi_zmenit_heslo`) — *až vznikne*
  - [Přehled projektů](prehled-projektu.md) — automatická synchronizace z Freela (plánovač, endpointy `/matice/sync-nastaveni`)
  - Serverová sekce práv (model a katalog práv na backendu) — *až vznikne*
