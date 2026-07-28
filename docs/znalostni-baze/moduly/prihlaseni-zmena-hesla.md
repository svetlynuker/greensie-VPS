# Přihlášení a změna hesla

> **Sekce v nabídce:** — (vstupní brána do appky, v nabídce není) · **Adresa (routa):** `/` (přihlášení), `/zmena-hesla` (nastavení nového hesla), `/rozcestnik` (úvodní souhrn po přihlášení) · **Kdo smí otevřít:** všichni (přihlášení je společné pro celou appku)
> **Kód:** frontend `frontend/src/pages/Login.jsx`, `frontend/src/pages/ZmenaHesla.jsx`, `frontend/src/pages/Rozcestnik.jsx`, `frontend/src/api.js`, `frontend/src/App.jsx`; backend `backend/app/auth/` (routes, permissions, models), `backend/app/mailer.py`

Vstupní brána do celé aplikace. Uživatel se přihlásí e-mailem a heslem, při prvním
přihlášení (nebo po resetu adminem) je **donucen si nastavit vlastní heslo**, a pak se
dostane na **Rozcestník** — úvodní souhrn stavu ke dnešnímu dni. Do modulů se pak chodí
**panelem vlevo**, ve kterém jsou jen sekce, na které má uživatel právo; ostatní se
vůbec nezobrazí.

> 📸 SCREENSHOT: přihlašovací obrazovka (pole E-mail, Heslo, tlačítko „Přihlásit se", vpravo nahoře přepínače vzhledu)

---

## 🧑 Pro uživatele

### K čemu to slouží
Abyste se dostali do appky, musíte se přihlásit. Účet vám zakládá **správce** (admin) —
sami se registrovat nelze. Správce vám pošle (nebo předá) **jednorázové heslo**; s ním se
poprvé přihlásíte a appka vás rovnou vyzve, ať si zvolíte vlastní. Po přihlášení uvidíte
**Rozcestník** (souhrn ke dnešnímu dni) a **vlevo panel** se všemi sekcemi, které máte
k dispozici.

### Rozvržení obrazovky — přihlášení (`/`)
Uprostřed stránky je jedna karta s formulářem:

1. **Logo a název „Greensie"** — nahoře v kartě.
2. **E-mail** — vaše přihlašovací adresa.
3. **Heslo**.
4. **Tlačítko „Přihlásit se"**.
5. **Chybová hláška** — objeví se červeně pod poli, když se přihlášení nepovede.
6. **Přepínače vzhledu** (vpravo nahoře na stránce) — světlý/tmavý motiv a režim pro
   barvoslepé; fungují i před přihlášením.

### Rozvržení obrazovky — nastavení nového hesla (`/zmena-hesla`)
Sem vás appka pošle automaticky, když máte příznak „musíš změnit heslo". Karta obsahuje:

1. **Nadpis „Nastav si nové heslo"** a větu s vaším jménem, proč to appka chce.
2. **Nové heslo**.
3. **Nové heslo znovu** (pro kontrolu překlepu).
4. **Tlačítko „Uložit nové heslo"** (během ukládání se změní na „Ukládám…").
5. **Tlačítko „Odhlásit"** — když nechcete pokračovat.

> 📸 SCREENSHOT: obrazovka „Nastav si nové heslo" se dvěma poli a tlačítky

### Rozvržení obrazovky — po přihlášení (`/rozcestnik`)
1. **Panel vlevo** — logo „Greensie" a pod ním sekce ve skupinách (Přehledy, Nabídky,
   Systém, Nápověda). Otevřená sekce je zvýrazněná zeleně. Dole je **Zúžit panel**.
2. **Lišta nahoře** — název stránky, ikona **„?"** (nápověda k té stránce, kde jste)
   a vpravo **vaše jméno** s kolečkem iniciál.
3. **Souhrn** — čísla ke dnešnímu dni (aktivní projekty, úkoly po termínu, neuhrazené
   faktury, nabídky v přípravě) a pod nimi výpisy **Potřebuje pozornost** a **Blíží se
   termín**. Ukazuje se jen to, na co máte právo.

> 📸 SCREENSHOT: obrazovka po přihlášení — panel vlevo, souhrn s čísly a výpisy

### Proč některé sekce v panelu nevidíte
Panel ukazuje **jen ty sekce, na které máte právo**. Sekce bez práva se nezobrazuje vůbec —
ani zašedle, ani se zámkem. **Rozcestník** a **Manuál** právo nepotřebují, ty má každý.

O tom, co máte k dispozici, rozhoduje správce v modulu **Admin nastavení**. Když vám nějaká
sekce chybí a potřebujete ji, ozvěte se správci.

### Nastavení a odhlášení najdete pod svým jménem
Vpravo nahoře klikněte na svoje jméno. V nabídce je tmavý/světlý režim, kompenzace barev pro
červeno-zelenou vadu zraku, velikost textu, **Změnit heslo** a **Odhlásit se**. Podrobně to
popisuje [Společné prvky UI](./spolecne-prvky.md).

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = kdokoli · **(admin)** = jen supersprávce nebo kdo má dané právo.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **E-mail** | přihlášení | Vaše přihlašovací adresa (povinné) | vše |
| **Heslo** | přihlášení | Heslo k účtu (povinné, skryté hvězdičkami) | vše |
| **Přihlásit se** | přihlášení | Odešle přihlášení; při úspěchu jde na Rozcestník (nebo na změnu hesla) | vše |
| **Přepínač motivu / barvoslepost** | přihlašovací obrazovka | Přepne světlý/tmavý vzhled a režim pro barvoslepé | vše |
| **Nové heslo** | změna hesla | Vaše nové vlastní heslo (min. 6 znaků) | vše |
| **Nové heslo znovu** | změna hesla | Zopakování pro kontrolu překlepu | vše |
| **Uložit nové heslo** | změna hesla | Uloží heslo a pustí vás dál na Rozcestník | vše |
| **Odhlásit** (na změně hesla) | změna hesla | Zruší přihlášení a vrátí na přihlašovací obrazovku | vše |
| **Položka nabídky** | panel vlevo | Otevře modul; v panelu jsou jen sekce, na které máte právo | vše (dle práv) |
| **Jméno uživatele** | lišta vpravo nahoře | Rozbalí nabídku: vzhled, změna hesla, odhlášení | vše |

Přepínače vzhledu a odhlášení po přihlášení najdete pod svým jménem — viz
[Společné prvky UI](./spolecne-prvky.md).

> 📸 SCREENSHOT: lišta s jménem a rozbalenou nabídkou uživatele

### Jak na…
- **Přihlásit se poprvé:** zadejte e-mail a **jednorázové heslo** od správce → „Přihlásit se".
  Appka vás rovnou přesměruje na **Nastav si nové heslo** → zadejte vlastní heslo dvakrát →
  „Uložit nové heslo". Hotovo, jste na Rozcestníku.
- **Změnit si heslo:** změna hesla je v appce navázaná jen na povinnou první změnu / reset
  (obrazovka `/zmena-hesla`). Když chcete heslo změnit dobrovolně kdykoli jindy, požádejte
  správce o **reset** — ten vám nastaví nové jednorázové heslo a appka vás při dalším
  přihlášení znovu vyzve k volbě vlastního (viz „Poznámky a úskalí").
- **Zapomněl(a) jsem heslo:** obraťte se na správce (admina). V modulu **Admin nastavení**
  vám udělá **reset hesla** — buď vám systém vygeneruje nové jednorázové heslo, nebo vám
  správce nastaví konkrétní. Po přihlášení tímto heslem si zase zvolíte vlastní. Samoobslužné
  „zapomenuté heslo" appka nemá.
- **Nevidím sekci v panelu:** je to otázka práv — napište správci, ať vám přidá
  příslušné právo v Admin nastavení.
- **Odhlásit se:** vpravo nahoře klikněte na svoje jméno → **Odhlásit se** (nebo tlačítko
  „Odhlásit" na obrazovce změny hesla).

---

## 🛠 Pro admina / provoz

### Jak funguje autentizace
- **Přihlášení** (`POST /auth/login`, `backend/app/auth/routes.py`): server najde uživatele
  podle e-mailu a ověří heslo (bcrypt, `over_heslo`). Při úspěchu vytvoří **JWT token**
  (`vytvor_access_token`) a vrátí ho jako `access_token`. Frontend token uloží do
  `localStorage` pod klíč `greensie_token` (`frontend/src/api.js`) a posílá ho v hlavičce
  `Authorization: Bearer …` u všech dalších volání.
- **Token**: JWT, algoritmus **HS256**, podepsaný serverovým `SECRET_KEY` (z prostředí,
  nikde se nevypisuje). Platnost **8 hodin** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8`).
  V tokenu je jen `sub` = ID uživatele. Neexistuje refresh — po vypršení je nutné se
  přihlásit znovu.
- **`GET /auth/me`** (`get_current_user` dekóduje token) vrací kompletní profil pro frontend:

  | Pole | Význam |
  |---|---|
  | `uzivatel` | `{ id, jmeno, email, je_admin, skupina }` — `skupina` je název skupiny (nebo `null`), ukazuje se u jména v liště |
  | `prava` | **efektivní práva uživatele** (klíče z katalogu práv), seřazená — podle nich se skládá nabídka vlevo |
  | `muze_editovat` | zda smí editovat matici (Přehled projektů), tj. má právo `editace` |
  | `dlazdice` | seznam `{ klic, nazev, muze_otevrit }` — **pozůstatek po dlaždicovém rozcestníku, frontend ho už nepoužívá** |
  | `musi_zmenit_heslo` | `true` = uživatel je přesměrován na `/zmena-hesla` |

- **Práva** (`backend/app/auth/permissions.py`): supersprávce (`je_admin`) má **všechna
  práva**; ostatní mají sjednocení `extra_prava` (individuální výjimky) a práv své skupiny
  (`skupina.prava`). `muze_otevrit(user, klic)` = daný klíč je v efektivních právech.
  Katalog přidělitelných práv je `PRAVA` (a `DLAZDICE` je zbytek po starém rozcestníku).
- **Rámec appky** si `/auth/me` bere přes `api.nactiMeSdilene()` — sdílená odpověď
  s minutovou platností, ať se nedotazuje znovu při každém přechodu mezi stránkami.
  Jednotlivé stránky volají `nactiMe()` dál samy (bez cache).

### Pravidla hesel
- **Minimální délka: 6 znaků.** Vynucuje se na frontendu (`ZmenaHesla.jsx`) i na backendu
  (`PUT /auth/heslo` → jinak `422 Heslo musí mít alespoň 6 znaků.`). Kontrola shody dvou
  polí je jen na frontendu.
- **Jednorázové heslo**: při založení uživatele (`POST /admin/uzivatele`) a při resetu
  server vygeneruje náhodné heslo `vygeneruj_heslo()` (výchozí délka 10 znaků, znaková sada
  **bez záměnných dvojic** 0/O, 1/l/I kvůli čitelnosti). Ukládá se jen jeho **bcrypt hash**
  (`hash_heslo`), nikdy holé heslo.
- **`musi_zmenit_heslo`**: nastaví se na `true` při **založení** uživatele i při **resetu**.
  Uživatel se sice přihlásí, ale `GET /auth/me` vrátí `musi_zmenit_heslo=true` → frontend ho
  pošle na `/zmena-hesla` a nepustí dál, dokud si heslo nezmění. `PUT /auth/heslo` po uložení
  nastaví příznak zpět na `false`.
- **Reset hesla** (`POST /admin/uzivatele/{id}/reset-hesla`): admin buď zadá konkrétní heslo
  (min. 6 znaků), nebo nechá pole prázdné a systém vygeneruje náhodné. V obou případech se
  nastaví `musi_zmenit_heslo=true`.

### E-mail s přihlašovacím odkazem
- Po založení uživatele i po resetu se appka **pokusí** odeslat e-mail s přihlašovacími
  údaji (`backend/app/mailer.py`, funkce `email_pristupu` + `posli_email`). E-mail obsahuje
  jméno, **přihlašovací odkaz** (`APP_URL`), **jednorázové heslo** a upozornění, že si po
  prvním přihlášení uživatel zvolí vlastní.
- Odesílání je **best-effort** (`_posli_pristup` v `admin/routes.py`): když SMTP není
  nastavené nebo se odeslání nepovede, **akce se nezruší** — uživatel vznikne / heslo se
  resetuje a admin dostane heslo zpět v odpovědi API (zobrazí se v Admin nastavení), takže
  ho může předat ručně. V odpovědi je `email_odeslan` a případná `email_poznamka` s důvodem.
- SMTP se konfiguruje jen přes prostředí (`.env`): `SMTP_HOST` (výchozí `smtp.seznam.cz`),
  `SMTP_PORT` (výchozí 587 STARTTLS; 465 = implicitní SSL, u Hetzneru bývá blokovaný),
  `SMTP_USER`, `SMTP_HESLO` (bez něj se e-maily **neposílají**), `SMTP_ODESILATEL`, `APP_URL`.
  Kontrola `email_nastaven()` = je vyplněné `SMTP_HESLO`.

### Guardy chráněných stránek
- **Frontend** (`App.jsx`, komponenta `VyzadujePrihlaseni`): všechny routy kromě `/` jsou
  obalené — pokud v `localStorage` **není token**, přesměruje na `/`. Guard kontroluje jen
  **existenci** tokenu, ne jeho platnost (viz „Poznámky a úskalí").
- **Přesměrování podle stavu**: `Login` po přihlášení volá `nactiMe()` a podle
  `musi_zmenit_heslo` jde na `/zmena-hesla` nebo `/rozcestnik`. `Rozcestnik` i `ZmenaHesla`
  si při načtení taky ověří `nactiMe()`; když selže (neplatný token), zavolají `logout()` a
  vrátí na `/`. `Rozcestnik` navíc při `musi_zmenit_heslo=true` sám přesměruje na
  `/zmena-hesla`.
- **Backend**: skutečnou ochranu dělá `get_current_user` (ověří JWT) u chráněných endpointů;
  administrátorské endpointy chrání navíc `vyzaduj_admina`.
- **Nabídka vlevo** (`components/Sidebar.jsx` + `navigace.js`): `nabidkaPro(prava)`
  profiltruje položky podle efektivních práv a zahodí prázdné skupiny — sekce bez práva se
  **nezobrazí vůbec**, zamčená varianta neexistuje. `Rozcestník` a `Manuál` jsou označené
  `vzdy: true`, ty právo nepotřebují.

### Synchronizace vzhledu po přihlášení
Hned po `login` volá frontend `synchronizujVzhled()` — stáhne uložené nastavení vzhledu
z DB (`GET /nastaveni`: motiv, velikost textu, režim pro barvoslepé) a použije ho, takže se
vzhled **přenáší mezi zařízeními**. Když se nenačte, jede se s lokálním nastavením (vzhled
není kritický).

### API
| Metoda + cesta | Účel |
|---|---|
| `POST /auth/login` | Ověří e-mail + heslo, vrátí JWT token. Úspěch i neúspěch se zapisuje do auditu. |
| `GET /auth/me` | Profil přihlášeného: uživatel (včetně názvu skupiny), `prava`, `muze_editovat`, `musi_zmenit_heslo` (+ historické `dlazdice`). |
| `PUT /auth/heslo` | Změna vlastního hesla (min. 6 znaků); vypne `musi_zmenit_heslo`. |
| `POST /admin/uzivatele` | (admin) Založí uživatele s jednorázovým heslem, `musi_zmenit_heslo=true`, pokusí se poslat e-mail. |
| `POST /admin/uzivatele/{id}/reset-hesla` | (admin) Reset hesla (zadané nebo vygenerované), `musi_zmenit_heslo=true`. |
| `GET /nastaveni` | Uložený vzhled (motiv, velikost, barvoslepost) pro synchronizaci mezi zařízeními. |

### Klíčové soubory
- **Frontend:** `pages/Login.jsx` (přihlášení + synchronizace vzhledu), `pages/ZmenaHesla.jsx`
  (vynucená změna), `pages/Rozcestnik.jsx` (úvodní souhrn), `components/Layout.jsx` (rámec),
  `components/Sidebar.jsx` (nabídka dle práv), `components/UserMenu.jsx` (nabídka uživatele),
  `navigace.js` (struktura appky), `api.js` (`login`, `nactiMe`, `nactiMeSdilene`, `zmenHeslo`,
  `logout`, `getToken`, `nactiNastaveni`), `App.jsx` (routy + guard `VyzadujePrihlaseni`).
- **Backend:** `auth/routes.py` (login, /me, PUT /heslo), `auth/permissions.py`
  (JWT, hashování, generování hesla, práva, guardy), `auth/models.py`
  (tabulky `uzivatele`, `skupiny`; schémata `LoginRequest`, `Token`, `MeOut`, …),
  `mailer.py` (SMTP + e-mail s přístupem), `admin/routes.py` (`_posli_pristup`, reset hesla).

### Časté potíže / co dělat, když…
- **„Nesprávný e-mail nebo heslo"** → chybný údaj, nebo účet neexistuje. Hláška je **záměrně
  stejná** pro obě příčiny (bezpečnost, ať se neprozradí existence účtu). Zkontroluj e-mail
  a jednorázové heslo; případně proveď reset.
- **Uživatele to pořád vrací na „Nastav si nové heslo"** → má `musi_zmenit_heslo=true` a heslo
  ještě neuložil; dokud si ho nezvolí, dál se nedostane. Řešení: dokončit změnu hesla.
- **E-mail s přístupem nedorazil** → SMTP nemusí být nastavené (`email_odeslan=false`,
  `email_poznamka` řekne důvod). Heslo předej ručně — admin ho vidí v odpovědi po
  založení/resetu. Zkontroluj `SMTP_HESLO` a `SMTP_HOST/PORT` v `.env`.
- **Uživatel byl „vykopnut" na přihlášení uprostřed práce** → nejspíš vypršel token (platnost
  8 h) nebo je neplatný; `nactiMe()` selhal a frontend odhlásil. Řešení: přihlásit se znovu.
- **Sekce v panelu chybí** → chybí právo se stejným klíčem. Přiděl ho ve skupině nebo
  jako individuální výjimku (`extra_prava`) v Admin nastavení. Pozor: rámec drží práva
  **minutu** v cache (`nactiMeSdilene`), takže se změna projeví až po chvíli / po F5.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Frontendový guard hlídá jen existenci tokenu, ne jeho platnost.** S vypršelým tokenem se
  chráněná stránka nejdřív otevře a teprve první volání API (`nactiMe`) selže → pak teprve
  odhlášení a přesměrování. Reálnou ochranu dat zajišťuje backend, ne guard.
- **Není samoobslužné „zapomenuté heslo".** Dobrovolnou změnu hesla „za běhu" appka nemá —
  obrazovka `/zmena-hesla` slouží jen k **vynucené** změně (první přihlášení / reset). Kdo
  si chce heslo změnit dobrovolně, musí projít přes admin reset. (K ověření, zda je to
  záměr, nebo se počítá s doplněním samoobslužné změny.)
- **Jednorázové heslo se v UI zobrazí adminovi v čistém tvaru** (v odpovědi po založení /
  resetu), aby ho mohl předat, když e-mail nefunguje. V DB je uložený jen hash.
- **Token v `localStorage`** přežije zavření prohlížeče až do vypršení (8 h); „Odhlásit" ho
  smaže (`logout` = odebrání klíče `greensie_token`).
- **Neúspěšné přihlášení neznámého účtu** se do auditu ukládá bez surového vstupu (aby se
  omylem nezalogovalo heslo napsané do pole e-mail).
- **Názvy a ikony sekcí** jsou napevno na frontendu (`navigace.js`), nechodí ze serveru —
  ze serveru přijdou jen klíče práv. Přidání nové sekce tedy znamená zásah do `navigace.js`
  i do katalogu `PRAVA` na backendu.
- **`GET /auth/me` dál vrací pole `dlazdice`**, ale frontend ho už nepoužívá (nabídka se řídí
  polem `prava`). Zůstalo, aby se nerozbilo API — kandidát na úklid.

## Odkazy
- Kód frontend: `frontend/src/pages/Login.jsx`, `ZmenaHesla.jsx`, `Rozcestnik.jsx`,
  `components/Layout.jsx`, `components/Sidebar.jsx`, `components/UserMenu.jsx`,
  `navigace.js`, `api.js`, `App.jsx`
- Kód backend: `backend/app/auth/` (routes, permissions, models), `backend/app/mailer.py`,
  `backend/app/admin/routes.py`
- Související dokumentace: [Admin nastavení](admin-nastaveni.md) — správa uživatelů, skupin,
  práv, reset hesel a odesílání přístupů e-mailem (serverová sekce e-mailů a práv)
- Paměť projektu: greensie-app-projekt (stack, práva) a konektor-raynet-gdrive (SMTP/tajemství z UI)
