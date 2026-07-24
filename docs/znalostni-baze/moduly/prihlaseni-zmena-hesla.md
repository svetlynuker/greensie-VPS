# Přihlášení a změna hesla

> **Dlaždice:** — (není v rozcestníku, je to vstupní brána do appky) · **Adresa (routa):** `/` (přihlášení), `/zmena-hesla` (nastavení nového hesla), `/rozcestnik` (rozcestník po přihlášení) · **Kdo smí otevřít:** všichni (přihlášení je společné pro celou appku)
> **Kód:** frontend `frontend/src/pages/Login.jsx`, `frontend/src/pages/ZmenaHesla.jsx`, `frontend/src/pages/Rozcestnik.jsx`, `frontend/src/components/Tile.jsx`, `frontend/src/api.js`, `frontend/src/App.jsx`; backend `backend/app/auth/` (routes, permissions, models), `backend/app/mailer.py`

Vstupní brána do celé aplikace. Uživatel se přihlásí e-mailem a heslem, při prvním
přihlášení (nebo po resetu adminem) je **donucen si nastavit vlastní heslo**, a pak se
dostane na **rozcestník** — mřížku dlaždic, odkud vede cesta do jednotlivých modulů.
Co uživatel smí otevřít, řídí jeho práva; nedostupné dlaždice jsou buď zamčené (🔒),
nebo se úplně skryjí.

> 📸 SCREENSHOT: přihlašovací obrazovka (pole E-mail, Heslo, tlačítko „Přihlásit se", vpravo nahoře přepínače vzhledu)

---

## 🧑 Pro uživatele

### K čemu to slouží
Abyste se dostali do appky, musíte se přihlásit. Účet vám zakládá **správce** (admin) —
sami se registrovat nelze. Správce vám pošle (nebo předá) **jednorázové heslo**; s ním se
poprvé přihlásíte a appka vás rovnou vyzve, ať si zvolíte vlastní. Po přihlášení uvidíte
**rozcestník** se všemi moduly, které máte k dispozici.

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

### Rozvržení obrazovky — rozcestník (`/rozcestnik`)
1. **Horní lišta** — logo a název „Greensie", vpravo přepínač velikosti textu, motivu,
   režimu pro barvoslepé, **vaše jméno** a tlačítko **„Odhlásit"**.
2. **Mřížka dlaždic** — jedna dlaždice = jeden modul. Každá má ikonu, název, krátký
   podtitulek a buď **šipku** (dá se otevřít), nebo **odznak „zamčeno" 🔒**.

> 📸 SCREENSHOT: rozcestník s mřížkou dlaždic — některé s šipkou, jedna zamčená

### Co je rozcestník a proč jsou některé dlaždice zamčené
Rozcestník ukazuje moduly aplikace. Podle vašich práv se dlaždice chovají třemi způsoby:

- **Otevřená (se šipkou →)** — na modul máte právo; kliknutím se otevře.
- **Zamčená (🔒 „zamčeno")** — dlaždici vidíte, ale nemáte právo ji otevřít. Po najetí
  myší se ukáže vysvětlení „Zatím nedostupné – nemáš oprávnění tuto sekci otevřít".
  Kliknutím se místo modulu otevře **video** (na nový panel), které modul představí.
- **Úplně skrytá** — některé citlivé moduly (Přehled financí, Nabídkovač, Logy, Konektor)
  se bez práva vůbec nezobrazí, takže o nich ani nevíte.

O tom, co máte odemčené, rozhoduje správce v modulu **Admin nastavení**. Když vám dlaždice
chybí nebo je zamčená a potřebujete ji, ozvěte se správci.

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = kdokoli · **(admin)** = jen supersprávce nebo kdo má dané právo.

| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **E-mail** | přihlášení | Vaše přihlašovací adresa (povinné) | vše |
| **Heslo** | přihlášení | Heslo k účtu (povinné, skryté hvězdičkami) | vše |
| **Přihlásit se** | přihlášení | Odešle přihlášení; při úspěchu jde na rozcestník (nebo na změnu hesla) | vše |
| **Přepínač motivu / barvoslepost** | přihlášení i rozcestník | Přepne světlý/tmavý vzhled a režim pro barvoslepé | vše |
| **Nové heslo** | změna hesla | Vaše nové vlastní heslo (min. 6 znaků) | vše |
| **Nové heslo znovu** | změna hesla | Zopakování pro kontrolu překlepu | vše |
| **Uložit nové heslo** | změna hesla | Uloží heslo a pustí vás dál na rozcestník | vše |
| **Odhlásit** (na změně hesla) | změna hesla | Zruší přihlášení a vrátí na přihlašovací obrazovku | vše |
| **Velikost textu** | rozcestník (horní lišta) | Zvětší/zmenší text v celé appce | vše |
| **Jméno uživatele** | rozcestník (horní lišta) | Ukazuje, kdo je přihlášený | vše |
| **Odhlásit** (v liště) | rozcestník | Odhlásí a vrátí na přihlašovací obrazovku | vše |
| **Dlaždice modulu** | rozcestník | Otevře modul (má-li právo), jinak přehraje video / je skrytá | vše (dle práv) |

> 📸 SCREENSHOT: horní lišta rozcestníku s jménem a tlačítkem „Odhlásit"

### Jak na…
- **Přihlásit se poprvé:** zadejte e-mail a **jednorázové heslo** od správce → „Přihlásit se".
  Appka vás rovnou přesměruje na **Nastav si nové heslo** → zadejte vlastní heslo dvakrát →
  „Uložit nové heslo". Hotovo, jste na rozcestníku.
- **Změnit si heslo:** změna hesla je v appce navázaná jen na povinnou první změnu / reset
  (obrazovka `/zmena-hesla`). Když chcete heslo změnit dobrovolně kdykoli jindy, požádejte
  správce o **reset** — ten vám nastaví nové jednorázové heslo a appka vás při dalším
  přihlášení znovu vyzve k volbě vlastního (viz „Poznámky a úskalí").
- **Zapomněl(a) jsem heslo:** obraťte se na správce (admina). V modulu **Admin nastavení**
  vám udělá **reset hesla** — buď vám systém vygeneruje nové jednorázové heslo, nebo vám
  správce nastaví konkrétní. Po přihlášení tímto heslem si zase zvolíte vlastní. Samoobslužné
  „zapomenuté heslo" appka nemá.
- **Nevidím dlaždici / je zamčená:** je to otázka práv — napište správci, ať vám přidá
  příslušné právo v Admin nastavení.
- **Odhlásit se:** tlačítko **„Odhlásit"** v horní liště rozcestníku (nebo na obrazovce
  změny hesla).

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
  | `uzivatel` | `{ id, jmeno, email, je_admin }` |
  | `dlazdice` | seznam všech dlaždic: `{ klic, nazev, muze_otevrit }` — `muze_otevrit=false` = zamčená |
  | `muze_editovat` | zda smí editovat matici (Přehled projektů), tj. má právo `editace` |
  | `prava` | efektivní práva uživatele (klíče z katalogu práv), seřazená |
  | `musi_zmenit_heslo` | `true` = uživatel je přesměrován na `/zmena-hesla` |

- **Práva** (`backend/app/auth/permissions.py`): supersprávce (`je_admin`) má **všechna
  práva**; ostatní mají sjednocení `extra_prava` (individuální výjimky) a práv své skupiny
  (`skupina.prava`). `muze_otevrit(user, klic)` = daný klíč je v efektivních právech.
  Katalog dlaždic je `DLAZDICE`, katalog přidělitelných práv `PRAVA`.

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
- **Rozcestník a dlaždice** (`Rozcestnik.jsx`, `Tile.jsx`): dlaždice se filtrují — modul bez
  práva se buď **zamkne** (🔒), nebo **úplně skryje**, pokud je v množině `SKRYT_BEZ_PRAVA`
  (`finance`, `nabidkovac`, `logy`, `konektor`). Klik na otevřenou dlaždici jde na trasu
  z `TRASY`; klik na zamčenou/rozpracovanou otevře video (`VYVOJ_VIDEO`).

### Synchronizace vzhledu po přihlášení
Hned po `login` volá frontend `synchronizujVzhled()` — stáhne uložené nastavení vzhledu
z DB (`GET /nastaveni`: motiv, velikost textu, režim pro barvoslepé) a použije ho, takže se
vzhled **přenáší mezi zařízeními**. Když se nenačte, jede se s lokálním nastavením (vzhled
není kritický).

### API
| Metoda + cesta | Účel |
|---|---|
| `POST /auth/login` | Ověří e-mail + heslo, vrátí JWT token. Úspěch i neúspěch se zapisuje do auditu. |
| `GET /auth/me` | Profil přihlášeného: uživatel, dlaždice s `muze_otevrit`, `muze_editovat`, `prava`, `musi_zmenit_heslo`. |
| `PUT /auth/heslo` | Změna vlastního hesla (min. 6 znaků); vypne `musi_zmenit_heslo`. |
| `POST /admin/uzivatele` | (admin) Založí uživatele s jednorázovým heslem, `musi_zmenit_heslo=true`, pokusí se poslat e-mail. |
| `POST /admin/uzivatele/{id}/reset-hesla` | (admin) Reset hesla (zadané nebo vygenerované), `musi_zmenit_heslo=true`. |
| `GET /nastaveni` | Uložený vzhled (motiv, velikost, barvoslepost) pro synchronizaci mezi zařízeními. |

### Klíčové soubory
- **Frontend:** `pages/Login.jsx` (přihlášení + synchronizace vzhledu), `pages/ZmenaHesla.jsx`
  (vynucená změna), `pages/Rozcestnik.jsx` (dlaždice + filtrování dle práv), `components/Tile.jsx`
  (dlaždice, zámek 🔒), `components/Layout.jsx` (horní lišta, Odhlásit), `api.js`
  (`login`, `nactiMe`, `zmenHeslo`, `logout`, `getToken`, `nactiNastaveni`), `App.jsx`
  (routy + guard `VyzadujePrihlaseni`).
- **Backend:** `auth/routes.py` (login, /me, PUT /heslo), `auth/permissions.py`
  (JWT, hashování, generování hesla, práva, dlaždice, guardy), `auth/models.py`
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
- **Dlaždice chybí / je zamčená** → chybí právo se stejným klíčem. Přiděl ho ve skupině nebo
  jako individuální výjimku (`extra_prava`) v Admin nastavení.

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
- **Podtituly a ikony dlaždic** jsou napevno na frontendu (`Rozcestnik.jsx`), nechodí ze
  serveru — server posílá jen klíč a název dlaždice.

## Odkazy
- Kód frontend: `frontend/src/pages/Login.jsx`, `ZmenaHesla.jsx`, `Rozcestnik.jsx`,
  `components/Tile.jsx`, `components/Layout.jsx`, `api.js`, `App.jsx`
- Kód backend: `backend/app/auth/` (routes, permissions, models), `backend/app/mailer.py`,
  `backend/app/admin/routes.py`
- Související dokumentace: [Admin nastavení](admin-nastaveni.md) — správa uživatelů, skupin,
  práv, reset hesel a odesílání přístupů e-mailem (serverová sekce e-mailů a práv)
- Paměť projektu: greensie-app-projekt (stack, práva) a konektor-raynet-gdrive (SMTP/tajemství z UI)
