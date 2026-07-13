# Zadání pro Claude Code – firemní aplikace Greensie

Tento dokument shrnuje, co má nová appka dělat. Vychází ze tří zdrojů:

1. **Přepis pracovní schůzky** (`Transcript.pdf`), kde se domlouvala logika a chování jednotlivých pohledů.
2. **Existující funkční prototyp** (`prehled projektu.txt`) – hotová Google Apps Script appka nad Freelem, ze které appka vizuálně a funkčně vychází. Odkazy na konkrétní CSS proměnné a chování v textu níže se vztahují přímo k tomuto souboru.
3. **Technické prostředí** – Hetzner VPS (Debian 12), uživatel `dan`, projekty v `~/projects/`, backend Python/FastAPI, frontend JS, Claude Code nainstalovaný a přihlášený na serveru, GitHub napojený přes SSH.

Doporučený postup použití: tento soubor ulož do repozitáře appky (např. `~/projects/greensie-app/docs/SPEC.md`), spusť na serveru `claude` ve složce projektu a zadávej mu jednotlivé kapitoly postupně – nejdřív kostru a přihlášení, pak Pohled 1 (je nejlépe definovaný a má hotový vizuální vzor), až pak Pohled 2 a Pohled 3.

---

## 1. Architektura

- **Backend:** Python 3 + FastAPI, běží ve `venv` na VPS.
- **Frontend:** JavaScript (React). Vizuální styl (barvy, rozestupy, chování sticky hlaviček, dialogy) přebírá 1:1 z prototypu `prehled projektu.txt` – je to hotový, odsouhlasený design, ne návrh od nuly. Konkrétní CSS proměnné (`--fm-brand:#2f9e44` atd.) a třídy s prefixem `fm-` slouží jako referenční paleta a pojmenování.
- **Databáze:** PostgreSQL (ne Google Sheets jako v prototypu). Uloží se do ní projekty, sloupce/úkoly, ruční přepisy buněk, poznámky, práva uživatelů a (pro Pohled 3) historie změn stavů.
- **Autentizace:** celá appka je za loginem. Landing page → přihlášení je první krok, nic není přístupné bez přihlášení. Role: admin / zaměstnanec / vedení (viz práva u jednotlivých pohledů).
- **Zdroje pravdy pro data:**
  - **Freelo** (projektový management) – úkoly, to-do listy (= "fáze"), termíny, stav hotovo/nehotovo. API napojení už existuje (viz `getFreelo` v prototypu).
  - **Pohoda** (účetnictví) – stav faktur (vystaveno/zaplaceno). Napojení přes API existuje, zatím nevyužité.
  - **Rejnet** (CRM) – evidence firem a leadů. Napojení existuje, ale zatím se nikam nepoužívá – je to na později, není součástí tohoto zadání.
  - Propojení faktury z Pohody s projektem z Freela jde přes variabilní/specifický symbol, který se ručně zapisuje do Freela (protože Freelo je zdroj pravdy).

---

## 2. Struktura appky (rozcestník)

1. **Landing page** → hned po vstupu vyskočí přihlášení.
2. Po přihlášení **rozcestník** (hlavní menu appky, česky pojmenované – ne anglicismy typu "dashboard") s velkými dlaždicemi. Klik na dlaždici vede do dané sekce.
3. **Dlaždice se zobrazují jen ty, na které má uživatel právo** – pokud právo nemá, dlaždice se úplně skryje (ne jen zašedne/zamkne).
4. V rámci appky bude jedna mezivrstva pro "technické/administrativní" věci (databáze, nastavení práv apod.), oddělená od byznysových dlaždic – zatím stačí, že s tím počítáme ve struktuře, detail se řeší později.

Sekce (dlaždice) v první verzi:
- **Přehled projektů** (Pohled 1) – vidí všichni ve firmě.
- **Přehled financí** (Pohled 2) – vidí jen Rosťa + vedení.
- **Přehled změn** (Pohled 3) – zatím koncept, viz kapitola 5.
- Prostor pro budoucí dlaždice (CRM nad Rejnetem apod.) – nestavět teď, jen nezavírat architekturu.

---

## 3. Pohled 1 – Přehled projektů (hlavní modul, staví se první)

Toto je maticová tabulka: řádky = projekty, sloupce = úkoly seskupené do fází (fáze = to-do listy z Freela). Přebírá funkčnost hotového prototypu `prehled projektu.txt` beze změny, plus úpravy z přepisu schůzky popsané níže.

### 3.1 Co zůstává z prototypu (funguje, jen se přepisuje do Python/JS stacku)

- Sloupce ukotvené vlevo (drag handle, název projektu s odkazem do Freela, termín projektu, počet hotových fází).
- Fáze jako sbalitelné skupiny sloupců (klik na hlavičku fáze = sbalit/rozbalit), sbalená fáze ukazuje souhrn (termín + poměr hotovo/celkem).
- Barevná logika podle termínu (funkce `deadlineLevel` v prototypu):
  - více než 3 dny do termínu → **zelená** (v termínu)
  - 0 až 3 dny do termínu → **žlutá** (blíží se)
  - 0 až 3 dny po termínu → **oranžová** (po termínu)
  - více než 3 dny po termínu → **červená** (hodně po)
  - bez vyplněného termínu se bere jako oranžová
- Buňka úkolu: klik otevře dialog se stavem (prázdné / nehotovo / hotovo), termínem, odpovědnou osobou a odkazem na úkol ve Freelu.
- Ruční přepisy (projekt, sloupec, buňka, termín) mají přednost před daty z Freela při refreshi – uživatel může vždy "Vrátit z Freela", pokud chce zahodit svou ruční úpravu.
- Přidání ručního projektu / ručního sloupce (úkolu) mimo Freelo.
- Poznámky – u buňky, u fáze (sbalené i rozbalené) i u projektu. Ikonka tužky, při najetí myší bublina s textem.
- Drag & drop řazení projektů (řádky), úkolů (sloupce) i fází (skupiny sloupců).
- Skrývání sloupců/fází přes dropdown checklist (checkbox u fáze i u jednotlivého úkolu), tlačítka "Zobrazit vše" / "Skrýt vše".
- Export do CSV.
- Automatický refresh dat z Freela každých 20 s, ale nikdy když je otevřený dialog nebo právě probíhá ukládání (aby uživateli nezmizel rozdělaný vstup).

### 3.2 Úpravy oproti prototypu (z domluvy na schůzce)

- **Horní lišta (topbar) je schovatelná** (roletka/menu), aby nezabírala místo – ale **legenda barev zůstává vždy viditelná a větší**, aby na první pohled bylo jasné, co která barva znamená. Tlačítka menu se dají naskládat pod sebe do rozbalovacího menu.
- **Zrušit barevný "proužek" u názvu projektu**, který dnes ukazuje nejhorší nehotový úkol nezávisle na termínu projektu (`fm-strip-*` v prototypu). Zůstává jen jedno obarvení řádku projektu – podle termínu projektu.
- Před datum termínu vždy natvrdo napsat popisek **"Termín:"**, aby nový/nezaškolený člověk hned věděl, co to číslo znamená (netýká se jen buňky úkolu, ale všude, kde se termín zobrazuje).
- Stavové ikony u buňky: **hotovo = zelená fajfka (✓)**, **nehotovo = přesýpací hodiny**, doplněné barevnou tečkou stejně jako dosud.
- **Vytváření nového sloupce/úkolu rovnou obsahuje pole pro poznámku** – nemá se to dodělávat až dodatečně, poznámka jde editovat i přímo z náhledu buňky (ne jen z formuláře přidání).
- Freelo komunikace zůstává **jednosměrná** (appka čte z Freela, nezapisuje zpět) – poznámky a ruční přepisy žijí jen v appce/databázi, ne ve Freelu.
- **Deadline vs. Termín** – kromě termínu z Freela chceme volitelné vlastní pole "deadline" (např. natvrdo nastavitelné na "2 týdny před termínem"), aby šlo mít firemní rezervu navíc. Důležité: **tohle pravidlo se má aplikovat jen na nové/budoucí projekty**, ne retroaktivně na už rozjeté – jinak by se najednou obarvily do červena úplně všechny stávající projekty. Při zavádění téhle logiky dát pozor a nejdřív probrat s Danem, na co konkrétně se to má vztahovat.
- **Práva:** Pohled 1 vidí kdokoliv ve firmě, žádné omezení (aby si každý mohl zkontrolovat i práci kolegy).

---

## 4. Pohled 2 – Přehled financí (pro Rosťu / vedení)

Zjednodušená duplicita Pohledu 1, ale s jiným obsahem sloupců – **finance se do Pohledu 1 vůbec nemíchají**, jsou to dva oddělené světy.

- Řádky = stejné projekty jako v Pohledu 1 (proklik z Pohledu 1 na Pohled 2 u daného projektu).
- Sloupce = faktury: **Faktura 1, Faktura 2, Faktura 3...** (výchozí 3, jde přidat další podle projektu – ne všechny projekty budou mít stejný počet).
- Každá faktura má stav: **potřeba vystavit / vystaveno / zaplaceno** (případně "zatím se nefakturuje").
- **Uživatel je barvoslepý** → stav se nikdy nesmí spoléhat jen na barvu. Vždy barva + piktogram/ikona (a klidně i text), aby stav poznal i bez rozlišení barev.
- Zdroj dat: Freelo (fáze/úkoly = kdy se má co fakturovat, podle domluvené logiky "po podpisu SOD/SOP se vystavuje faktura 1" apod. – přesná pravidla per-projekt zatím nejsou plně nadefinovaná, řešit iterativně), Pohoda (potvrzení, že faktura byla vystavena/zaplacena, napojení přes specifický/variabilní symbol).
- Cíl: aby Rosťa na první pohled viděl, co ještě musí vyfakturovat a co už je hotové, bez nutnosti se ptát ve Freelu/Pohodě/Rejnetu ručně.
- **Práva:** vidí jen Rosťa a vedení (skupina "vedení"). Ostatní k tomu přístup nemají (pokud budou chtít, řeší se to individuálně s Rosťou).

---

## 5. Pohled 3 – Přehled změn (koncept, není finální)

Tohle je **záložka, na které se ještě budeme muset sejít znovu** – zadání níže je jen směr, ne kompletní spec. Neimplementovat naslepo, nejdřív potvrdit s Danem.

- Cíl: vidět, kolik se toho v daném období (den/týden/měsíc) reálně udělalo – kolik úkolů přešlo z nehotovo na hotovo, kolik jich propadlo termínem.
- Sleduje se **jen na úrovni úkolů** (hotovo/nehotovo + průšvih termínu), ne detailní historie každé změny textu/poznámky.
- Potřebuje vlastní tabulku v databázi, která ukládá časové razítko každé změny stavu úkolu (jednoduchý log, ne plná verzovaná historie).
- **Problém, který je potřeba vyřešit před spuštěním:** nemůže se to spustit "od teď", protože všechny stávající projekty by v ten den vypadaly stejně (chybí historická data před spuštěním). Potřeba domluvit reálný počáteční bod sledování.
- Filtrace podle týdne/měsíce/dne, časová osa vývoje napříč projekty.

---

## 6. Technické prostředí a nasazení

- **Server:** Hetzner VPS, Debian 12, uživatel `dan` (sudo), SSH klíč, firewall (UFW – porty 22/80/443).
- **Projekt:** appka žije ve složce `~/projects/greensie-app`, s vlastním git repem napojeným na GitHub přes SSH klíč.
- **Nainstalováno na serveru:** Python 3 + venv, Node.js LTS, git, PostgreSQL, Claude Code (přihlášený, funkční).
- **Doména/nginx:** zatím neřešeno (appka zatím běží přes IP nebo lokálně) – až budeme mít víc appek najednou nebo chceme appku na doméně (např. `nastroj.greensie.cz`), doplní se nginx jako reverzní proxy. Není součástí tohoto zadání, jen na to nezapomenout při plánování portů.
- **Zálohy:** Hetzner snapshoty doporučeno zapnout, jakmile v appce budou reálná firemní data.
- **Citlivé údaje (API klíče k Freelu/Pohodě/Rejnetu, hesla k databázi):** vždy jen v souboru `.env`, který se **nikdy** neukládá do gitu (musí být v `.gitignore`).

---

## 7. Priorita implementace

1. **Kostra appky: login, rozcestník s dlaždicemi podle práv, prázdné sekce.** ← START ZDE
2. Pohled 1 – Přehled projektů (plná funkčnost dle kapitoly 3), napojení na Freelo.
3. Pohled 2 – Přehled financí, napojení na Pohodu.
4. Pohled 3 – až po další společné schůzce, kde se doladí přesná logika trackování změn.
