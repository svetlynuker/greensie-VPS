# Práva, skupiny a role

> **Oblast:** server / provoz (přístupová práva napříč celou appkou)
> **Kód:** backend `backend/app/auth/permissions.py`, `backend/app/auth/models.py`, `backend/app/auth/routes.py`, `backend/app/admin/routes.py`; strážce editace `backend/app/matice/permissions.py`
> **Spravuje se z UI:** modul **Admin nastavení** (`/admin`)

Tento dokument popisuje **koncepčně**, jak appka rozhoduje, kdo co smí: kde se práva berou,
jak se skládají, jak se vynucují na backendu a co z toho dostane frontend. Nastavuje se to
z modulu **Admin nastavení**; tady je vysvětlený **model za tím**.

---

## Model práv v kostce

**Pevné role byly zrušeny.** Neexistuje žádný výčet typu „admin / editor / uživatel" jako
napevno zadrátovaná role. Místo toho platí jednoduchý model:

- **`je_admin` (supersprávce)** — má **VŠECHNA** práva automaticky a **nelze ho z nich vyřadit**
  (viz pojistky níže). Je to plný přístup ke všemu.
- **Všichni ostatní** mají **efektivní práva** složená ze dvou zdrojů:

  > **efektivní práva = `extra_prava` (individuální výjimky) ∪ `skupina.prava` (práva skupiny)**

Sjednocení (`∪`) znamená, že stačí, aby právo přišlo z **kterékoli** strany — buď je uživatel má
jako individuální výjimku, nebo mu ho dává jeho skupina. Uživatel nemusí mít žádnou skupinu
(pak má jen svoje `extra_prava`) a nemusí mít žádnou výjimku (pak má jen práva skupiny).

Přesně to dělá funkce `prava_uzivatele(user)` v `backend/app/auth/permissions.py`:

```
supersprávce            → všechna práva (VSECHNA_PRAVA)
kdokoli jiný            → set(extra_prava) | set(skupina.prava)
```

> „Role OZ" (obchodní zástupce) se řeší **bez** nového konceptu role: OZ je prostě běžná
> **skupina** s právem `nabidkovac`. Stejný princip jako u financí. Žádná speciální role v kódu.

---

## Katalog práv (klíče)

Práva jsou textové klíče z jednoho katalogu (`PRAVA` v `permissions.py`). Dělí se na dvě skupiny:

- **Otevírací práva** — mají **stejný klíč jako dlaždice** rozcestníku. Kdo má právo, smí dlaždici
  otevřít; kdo ne, vidí ji zamčenou (🔒).
- **Akční práva** — neodemykají dlaždici, ale konkrétní **akce** uvnitř modulu (typicky editaci).

| Klíč | Název (v katalogu) | Typ | Co odemyká |
|---|---|---|---|
| `projekty` | Otevřít Přehled projektů | otevření dlaždice | vstup do modulu Přehled projektů (čtení matice) |
| `finance` | Otevřít Přehled financí | otevření dlaždice | vstup do modulu Přehled financí |
| `zmeny` | Otevřít Přehled změn | otevření dlaždice | vstup do modulu Přehled změn |
| `nabidkovac` | Nabídkovač – vytvářet/upravovat nabídky (OZ) | otevření dlaždice | vstup do Nabídkovače (tvorba/úprava nabídek) |
| `admin` | Otevřít Admin nastavení | otevření dlaždice | vstup do Admin nastavení (správa uživatelů, skupin, práv) |
| `logy` | Otevřít Logy (provoz, chyby, audit) | otevření dlaždice | vstup do modulu Logy |
| `konektor` | Otevřít Konektor Raynet ↔ Google Drive | otevření dlaždice | vstup do Konektoru (nastavení, logy) |
| `editace` | Editace matice (Přehled projektů) | akční | úpravy v Přehledu projektů (buňky, projekty/sloupce, prahy, Disk…) |
| `nabidkovac_katalog` | Nabídkovač – editace katalogu a výpočtů (vedení) | akční | úprava katalogu technologií a výpočtových nastavení v Nabídkovači |

> **Pozor na dva „nedlaždicové" klíče:** `editace` a `nabidkovac_katalog` **nemají** vlastní
> dlaždici — jsou to práva k akcím **uvnitř** modulu. Naopak každá dlaždice má svůj stejnojmenný
> otevírací klíč.

---

## Dlaždice rozcestníku (`DLAZDICE`)

Dlaždice = položky hlavního rozcestníku appky. Backend jich vrací **vždy všech sedm** a ke každé
přidá příznak `muze_otevrit`:

| Klíč dlaždice | Název | Otevře, kdo má právo |
|---|---|---|
| `projekty` | Přehled projektů | `projekty` |
| `finance` | Přehled financí | `finance` |
| `zmeny` | Přehled změn | `zmeny` |
| `nabidkovac` | Nabídkovač | `nabidkovac` |
| `admin` | Admin nastavení | `admin` |
| `logy` | Logy | `logy` |
| `konektor` | Konektor Raynet ↔ Disk | `konektor` |

**Princip zobrazení (dle backendu):** dlaždici vidí **vždy všichni**; bez příslušného práva je
**zamčená (🔒)** a klik na ni vede na **výukové video** (rozpracovaný / nedostupný modul).
Kdo právo má, klikem modul otevře.

> ⚠️ **Frontend to dnes zjemňuje** (viz Poznámky a úskalí): některé dlaždice se uživateli bez
> práva **úplně skryjí** místo pouhého zamčení. Konceptuálně ale platí, že zdrojem pravdy je
> backend, který vrací všechny dlaždice s příznakem `muze_otevrit`.

> 📸 SCREENSHOT: rozcestník s několika odemčenými dlaždicemi a jednou zamčenou (🔒)

---

## Jak se práva vynucují

### Na backendu (strážci)

Práva se na serveru vynucují **strážci** (FastAPI dependency `Depends(...)`), které se přidají
k endpointu nebo celému routeru. Kdo právo nemá, dostane **HTTP 403** a akce se neprovede —
nezáleží na tom, co ukazuje frontend.

| Nástroj | Kde je | Co dělá |
|---|---|---|
| `get_current_user` | `auth/permissions.py` | ověří přihlášení (JWT token) a vrátí uživatele; bez platného tokenu **401** |
| `muze_otevrit(user, klic)` | `auth/permissions.py` | vrátí `True/False`, zda uživatel smí danou dlaždici otevřít |
| `muze_editovat(user)` | `auth/permissions.py` | vrátí `True/False`, zda má právo `editace` |
| `vyzaduj_admina` | `auth/permissions.py` | strážce: pustí jen toho, kdo smí otevřít `admin`, jinak **403** |
| `vyzaduj_editora` | `matice/permissions.py` | strážce: pustí jen toho, kdo má `editace`, jinak **403** |

Příklady použití v kódu:

- **Celý modul Admin nastavení** je za strážcem admina — router má
  `dependencies=[Depends(vyzaduj_admina)]` (`backend/app/admin/routes.py`), takže **všechny**
  jeho endpointy vyžadují právo `admin`.
- **Editace v Přehledu projektů** je za `Depends(vyzaduj_editora)` (`backend/app/matice/routes.py`) —
  ukládání buňky, přidání projektu/sloupce, prahy barev, odkazy na Disk atd.
- **Moduly Přehled změn, Logy, Konektor** si uvnitř kontrolují `muze_otevrit(user, "...")`
  (klíče `zmeny`, `logy`, `konektor`) a bez práva vracejí **403**.

> Poznámka: `vyzaduj_editora` je jen tenký strážce nad `muze_editovat` — a `muze_editovat`
> je řízené právem `editace` (skupina / výjimka / admin), nikoli žádnou pevnou rolí. Soubor
> `matice/permissions.py` právo jen re-exportuje kvůli stávajícím importům.

### Na frontendu (co vrací `/auth/me`)

Frontend se po přihlášení ptá endpointu **`GET /auth/me`** (`backend/app/auth/routes.py`), který
vrací vše potřebné, aby UI vědělo, co zobrazit a co zamknout:

| Pole | Význam |
|---|---|
| `uzivatel` | `id`, `jmeno`, `email`, `je_admin` |
| `dlazdice` | seznam **všech** dlaždic, každá s `klic`, `nazev`, `muze_otevrit` (False = ukázat, ale zamknout) |
| `muze_editovat` | zda smí editovat matici (má právo `editace`) |
| `prava` | **efektivní práva** uživatele (setříděný seznam klíčů) — UI si podle nich zobrazuje/skrývá prvky |
| `musi_zmenit_heslo` | zda si uživatel musí při přihlášení nejdřív změnit heslo |

Frontend tedy **nerozhoduje o bezpečnosti** — jen podle těchto příznaků skrývá/zamyká tlačítka
a dlaždice. Skutečná ochrana je vždy na backendu (strážci výše).

---

## Skupiny

Skupina sdružuje uživatele kvůli právům. Definuje se v Admin nastavení.

**Tabulka `skupiny`** (`backend/app/auth/models.py`, třída `Skupina`):

| Sloupec | Typ | Význam |
|---|---|---|
| `id` | integer | primární klíč |
| `nazev` | text, **unikátní**, povinný | název skupiny (např. „OZ", „Vedení") |
| `prava` | pole textů (`ARRAY(String)`), výchozí prázdné `{}` | seznam klíčů práv z katalogu `PRAVA` |

**Napojení na uživatele** (třída `User`):

| Sloupec | Typ | Význam |
|---|---|---|
| `skupina_id` | integer, FK → `skupiny.id`, **`ON DELETE SET NULL`**, nepovinný | do které skupiny uživatel patří (dědí její práva) |
| `extra_prava` | pole textů (`ARRAY(String)`), výchozí `{}` | individuální výjimky nad rámec skupiny |
| `je_admin` | boolean, výchozí `false` | supersprávce (má vše) |

**`ON DELETE SET NULL`** znamená: když se skupina smaže, členům se pole `skupina_id` **vynuluje**
(uživatel nezmizí, jen ztratí práva plynoucí z té skupiny — zůstanou mu jeho `extra_prava`).

Při ukládání skupiny i uživatele backend **ověřuje**, že všechna přiřazená práva jsou známé klíče
z katalogu (`_over_prava`); neznámý klíč vrátí **422**. Názvy skupin musí být unikátní.

---

## Pojistky (co nejde udělat)

Backend hlídá, aby si šlo appku „nezamknout zvenčí". V `backend/app/admin/routes.py`:

- **Nelze smazat sám sebe** — mazání uživatele, který je zároveň přihlášený admin, vrátí **409**
  („Nemůžeš smazat sám sebe.").
- **Nelze smazat posledního admina** — pokud by po smazání nezůstal žádný supersprávce (**409**).
- **Nelze odebrat supersprávce poslednímu adminovi** — při úpravě uživatele, když by se
  poslednímu adminovi vzalo `je_admin` (**409**). Počet adminů zjišťuje `_pocet_adminu`.

Díky tomu vždy zůstane aspoň jeden supersprávce, který má přístup do Admin nastavení.

---

## Kde se to spravuje z UI

Vše výše (uživatelé, jejich skupina a výjimky, `je_admin`, definice skupin a jejich práv,
reset hesel) se nastavuje v modulu **Admin nastavení** — dlaždice `admin`, routa `/admin`.
Přístup má jen supersprávce, resp. kdo má právo `admin`.

Viz [Admin nastavení](../moduly/admin-nastaveni.md).

---

## Poznámky a úskalí (k ověření / nezřejmé)

- **Frontend zamčené dlaždice zčásti skrývá.** Backend vrací všech sedm dlaždic a záměr je
  „vidí všichni, bez práva zamčené (🔒) s proklikem na video". Rozcestník
  (`frontend/src/pages/Rozcestnik.jsx`) ale drží seznam `SKRYT_BEZ_PRAVA` = `finance`,
  `nabidkovac`, `logy`, `konektor` — ty se uživateli bez práva **úplně skryjí**. Zamčené (🔒)
  se tak reálně ukazují jen dlaždice **mimo** tento seznam (`projekty`, `zmeny`, `admin`).
  Klik na zamčenou/rozpracovanou dlaždici otevře výukové video (výchozí odkaz, s možností výjimky
  per klíč přes `VIDEO_DLE_KLICE`, dnes prázdné). Chování se do budoucna může sjednotit —
  k ověření, zda je skrývání záměr, nebo dočasné.
- **`nabidkovac_katalog` je akční právo** (editace katalogu/výpočtů v Nabídkovači), ne dlaždice —
  jak přesně se vynucuje uvnitř modulu Nabídkovač, patří do dokumentace toho modulu (zde jen
  koncepčně z katalogu práv).
- **Práva jsou volný textový seznam v DB**, validovaný jen proti katalogu při zápisu přes Admin
  nastavení. Když se z katalogu klíč odebere, historicky uložené hodnoty v `extra_prava`/`prava`
  se automaticky nečistí (fungují jen tam, kde se na klíč ptá kód).
- **Supersprávce ignoruje skupinu i výjimky** — `prava_uzivatele` mu vrací rovnou vše; skupina
  a `extra_prava` se u něj nevyhodnocují.

## Odkazy

- Kód: `backend/app/auth/permissions.py` (katalog `PRAVA`, `DLAZDICE`, `prava_uzivatele`,
  `muze_otevrit`, `muze_editovat`, `vyzaduj_admina`), `backend/app/auth/models.py`
  (`User`, `Skupina`), `backend/app/auth/routes.py` (`/auth/me`), `backend/app/admin/routes.py`
  (správa + pojistky), `backend/app/matice/permissions.py` (`vyzaduj_editora`)
- Frontend: `frontend/src/pages/Rozcestnik.jsx` (zobrazení dlaždic), `frontend/src/components/Tile.jsx`
- Související moduly: [Admin nastavení](../moduly/admin-nastaveni.md),
  [Přihlášení a změna hesla](../moduly/prihlaseni-zmena-hesla.md)
