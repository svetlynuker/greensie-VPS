# Doděláme v CRM

> **Typ:** pracovní seznam (ne návod) · **Vznikl:** 30. 7. 2026 · **Aktualizuje se průběžně**
> **Návod pro uživatele je jinde:** [`znalostni-baze/moduly/crm.md`](znalostni-baze/moduly/crm.md)

Srovnání hotového CRM v Greensie app s tím, co běžně umí Pipedrive, HubSpot, Raynet a Zoho.
Záměrně **ne** s enterprise Salesforce — cílem je firma s osmi lidmi, ne korporát.

## Jak s tímhle souborem pracovat

Každá položka má **ID** (`CRM-01`), takže se na ni dá odkázat: *„udělej CRM-03 a CRM-07"*.
Hotové položky se odškrtnou (`- [x]`) a doplní se k nim číslo PR.

| Značka | Znamená |
|---|---|
| **Velikost** S | do půl dne |
| **Velikost** M | jeden den |
| **Velikost** L | dva až tři dny |
| **Velikost** XL | víc než tři dny, dělit na dávky |
| **Dopad** ★★★ | bez toho appka někoho denně zdržuje nebo lže |
| **Dopad** ★★ | citelně zlepší práci, ale jde to i bez toho |
| **Dopad** ★ | pohodlí, ozdoba, nebo se u osmi lidí nemusí vyplatit |

---

## Obsah

1. [Nedodělky](#1-nedodělky-dluh-z-vlastní-práce)
2. [Doporučené pořadí dávek](#2-doporučené-pořadí-dávek)
3. [Moduly](#3-moduly)
4. [Pohledy](#4-pohledy)
5. [Filtry a práce se seznamy](#5-filtry-a-práce-se-seznamy)
6. [Modifikace a konfigurace](#6-modifikace-a-konfigurace)
7. [Uživatelská nastavení](#7-uživatelská-nastavení)
8. [Grafické prvky](#8-grafické-prvky)
9. [Co záměrně nedělat](#9-co-záměrně-nedělat)
10. [Co už CRM umí](#10-co-už-crm-umí-stav-k-30-7-2026)

---

## 1. Nedodělky (dluh z vlastní práce)

Tohle nejsou chybějící featury, ale díry, které vznikly během stavby. Mají přednost.

- [ ] **CRM-01 · UI pro „moje úkoly"** — Velikost **S** · Dopad **★★★**
  Endpoint `GET /crm/ukoly` existuje a funguje, ale **nikde se nezobrazuje**. Aktivity
  s termínem se ukládají a nikdo je nevidí, dokud neotevře konkrétní záznam.
  *Kde:* `backend/app/crm/routes.py` (hotovo) → chybí obrazovka/panel na rozcestníku.
  *Poznámka:* nejrychlejší výhra v celém seznamu.

- [ ] **CRM-02 · Stránkování seznamů** — Velikost **M** · Dopad **★★★**
  CRM API nemá `limit`/`offset` — vrací všechno. Po importu (445 klientů, 210 případů) se
  bude do prohlížeče posílat a renderovat celý seznam.
  *Kde:* `crm/routes.py`, `crm/routes_realizace.py`, `CrmTabulka.jsx`.
  *Pozor:* filtrování běží na klientu, takže stránkování musí počítat s tím, že se filtruje
  nad načtenou dávkou — buď se filtr přesune na server, nebo se stránkuje až po filtru.

- [ ] **CRM-03 · Konfigurovatelné kategorie případů** — Velikost **S** · Dopad **★★**
  Kategorie (`prodej` / `ppa` / `peak_shaving`) jsou **zadrátované v kódu na dvou místech**
  (`backend/app/crm/models.py:66`, `frontend/src/crm.js:20`). Stavy i vlastní pole si přitom
  vedení mění samo — tohle je nekonzistence. Až budete chtít „servis" nebo „dotace“, musí
  k tomu programátor.
  *Pozor:* kategorie řídí, do kterého výpočtu míří nabídka, takže nová kategorie musí umět
  říct „tady výpočet není".

- [ ] **CRM-04 · Vlastní pole i na nabídkách** — Velikost **S** · Dopad **★**
  `ENTITY_VLASTNICH_POLI` zná zákazníka, případ, objednávku a projekt — nabídka chybí.

---

## 2. Doporučené pořadí dávek

| Dávka | Obsah | Proč právě teď |
|---|---|---|
| **A** | CRM-01, CRM-02, CRM-25, CRM-05, CRM-03, CRM-22 | Rychlé, hodnotné, a CRM-02 je potřeba **před** importem 445 klientů |
| **B** | CRM-08, CRM-09 | Položky a fakturace = největší dík pro vedení; největší kus práce |
| **C** | CRM-39 – CRM-43 | Dashboard s grafy — data už máte, jen je nikdo nevidí |
| **D** | CRM-10, CRM-11 | E-mail a notifikace, pak servis a revize |
| **E** | CRM-19, CRM-13, pak zbytek podle toho, co začne v provozu chybět | U osmi lidí se část nemusí vyplatit vůbec |

---

## 3. Moduly

- [ ] **CRM-05 · Dokumenty u zákazníka a případu** — Velikost **M** · Dopad **★★★**
  Soubory se dnes nahrávají **jen k nabídce**. Chybí místo pro smlouvy, revizní zprávy, fotky
  z realizace. Konektor už mapuje složky obchodních případů na Google Disku
  (`konektor_entity_folder`), takže nejlevnější varianta je **proklik na složku**, jako to má
  Přehled projektů (`matice/disk_parovani.py`), a teprve pak vlastní upload.

- [ ] **CRM-06 · Kontakty jako samostatná entita** — Velikost **L** · Dopad **★★**
  Kontaktní osoba je dnes podřízená jedné firmě (`crm_zakaznik_kontakty`). Nejde ji najít
  napříč zákazníky ani mít jednu osobu u dvou firem (běžné u skupin a u OSVČ, které mají
  víc subjektů).

- [ ] **CRM-07 · Merge duplicitních zákazníků** — Velikost **M** · Dopad **★★**
  ARES varuje při zakládání, ale když duplicita vznikne (import + ruční založení), není jak
  ji slít. Musí umět převést případy, nabídky, aktivity i kontakty a nechat stopu.

- [ ] **CRM-08 · Položky nabídek a objednávek** — Velikost **XL** · Dopad **★★★**
  Objednávka má jen `cena_kc`. Bez rozpisu (panely, měnič, baterie, montáž, doprava) nejde
  vyfakturovat ani doložit, z čeho cena vznikla. **Katalog technologií už existuje**
  (`nabidkovac.Technologie`) a není s objednávkou nijak propojený.
  *Návrh:* tabulka `crm_objednavka_polozky` (technologie_id nebo volný text, počet, jednotková
  cena, sleva) + přenos z nabídky. Musí zvládnout i položku, která v katalogu není.

- [ ] **CRM-09 · Napojení na fakturaci a Přehled financí** — Velikost **L** · Dopad **★★★**
  Appka má Přehled financí s párováním na POHODU, ale objednávka o fakturách nic neví.
  Chybí řetěz **objednávka → faktura → zaplaceno**, což je přesně to, co vedení u zakázky
  zajímá nejvíc. Navázat na `backend/app/finance/`.

- [ ] **CRM-10 · E-mail z appky a notifikace** — Velikost **L** · Dopad **★★★**
  V appce je `backend/app/mailer.py` (`posli_email`), CRM ho nepoužívá. Chybí:
  odeslat nabídku zákazníkovi z appky a mít to v logu komunikace; upozornit na úkol po
  termínu; dát vědět, že mi někdo přiřadil případ. Potřebuje k tomu i CRM-36 (co komu posílat), jinak je to obtěžování.

- [ ] **CRM-11 · Servis, revize a reklamace** — Velikost **XL** · Dopad **★★★**
  Projekt skončí předáním, ale zákazník žije dál: servisní smlouvy, revize po 4 letech,
  reklamace, výměna měniče. U FVE je to **celý druhý životní cyklus** a dnes pro něj v appce
  není místo. Zvážit jako pátou entitu řetězce s vlastní číselnou řadou (`SER-26-NNNN`).

- [ ] **CRM-12 · Audit log změn záznamů** — Velikost **M** · Dopad **★★**
  Máte historii **stavů** (`crm_stav_historie`), ale ne „kdo změnil cenu z 2,5 na 1,9 mil.".
  Appka má modul `logy` — dá se využít.

- [ ] **CRM-13 · Export do CSV / Excelu** — Velikost **S** · Dopad **★★**
  Ani filtrovaného seznamu. Vedení chce data do tabulky, tohle je nejjednodušší cesta.

- [ ] **CRM-14 · Import z CSV** — Velikost **M** · Dopad **★**
  Mimo Raynet (seznam z výstavy, koupená databáze). Po CRM-07 (merge), aby to nedělalo duplicity.

- [ ] **CRM-15 · Cíle a provize OZ** — Velikost **L** · Dopad **★★**
  Bez cílů nejde měřit výkon a bez provizí se stejně počítají v Excelu. Navazuje na CRM-42.

---

## 4. Pohledy

- [ ] **CRM-16 · Můj den** — Velikost **M** · Dopad **★★★**
  Jedna obrazovka: úkoly po termínu, dnešní úkoly, případy bez aktivity X dní, nabídky
  odeslané bez reakce. Staví na CRM-01.

- [ ] **CRM-17 · Kalendář aktivit** — Velikost **L** · Dopad **★★**
  Dnes jsou úkoly vidět jen v záznamu. Měsíční/týdenní pohled s možností přesunout termín.

- [ ] **CRM-18 · Timeline zákazníka** — Velikost **M** · Dopad **★★**
  Všechno chronologicky na jedné ose (aktivity, nabídky, objednávky, projekty, změny stavů).
  Dnes je to rozdělené do záložek a člověk si musí děj skládat v hlavě.

- [ ] **CRM-19 · Hromadné akce nad seznamem** — Velikost **M** · Dopad **★★**
  Označit víc řádků a hromadně: změnit vlastníka, změnit stav, přidat aktivitu, exportovat.

- [ ] **CRM-20 · Mapa zákazníků a projektů** — Velikost **M** · Dopad **★★**
  **GPS už v datech je** (z Raynetu i z ARESu). U FVE se hodí na plánování obchůzek, na
  posouzení lokality a na „co máme v okolí, když už tam jedeme".

- [ ] **CRM-21 · Ganttův diagram projektu** — Velikost **L** · Dopad **★★**
  Kroky mají trvání i návaznosti, takže Gantt je nad nimi přirozený a ukáže kritickou cestu.

- [ ] **CRM-22 · KPI dlaždice nad seznamy** — Velikost **S** · Dopad **★★**
  Nad tabulkou počet, celková hodnota, průměr, kolik je po termínu. Appka má na to hotový
  vizuální prvek (`gs-kpi` na rozcestníku).

- [ ] **CRM-23 · Swimlanes v kanbanu** — Velikost **M** · Dopad **★**
  Řádky podle vlastníka (nebo kategorie) — vedení hned vidí, kdo má co rozjeté.

- [ ] **CRM-24 · Globální hledání** — Velikost **M** · Dopad **★★**
  Jedno pole, které prohledá zákazníky, případy, nabídky, objednávky i projekty. Dnes se hledá
  v každé sekci zvlášť.

---

## 5. Filtry a práce se seznamy

Základ je hotový (filtry sloupců, víceúrovňové řazení, uložené a sdílené pohledy).
Co běžná CRM mají navíc:

- [ ] **CRM-25 · Relativní datumové filtry** — Velikost **S** · Dopad **★★★**
  „Posledních 30 dní", „tento měsíc", „příští týden". Dnes jen absolutní od–do, takže
  **uložený filtr za měsíc lže** — to je horší než chybějící funkce.

- [ ] **CRM-26 · OR a skupiny podmínek** — Velikost **M** · Dopad **★★**
  Dnes se všechny podmínky sčítají (AND). Chybí „stav je Nabídka **nebo** Vyjednávání".
  Formát podmínek v `crm_ulozene_filtry` to zvládne, jde o vyhodnocení v `crmFiltry.js`.

- [ ] **CRM-27 · Rychlé předvolby** — Velikost **S** · Dopad **★★**
  „Jen moje", „jen otevřené", „po termínu" jedním kliknutím, bez skládání filtru.

- [ ] **CRM-28 · Skrývání a přeskládání sloupců** — Velikost **M** · Dopad **★★**
  Včetně uložení rozvržení k filtru — kdo sleduje jiná čísla, chce jinou tabulku.

- [ ] **CRM-29 · Filtr na serveru** — Velikost **L** · Dopad **★**
  Dnes se filtruje na klientu (vědomé rozhodnutí, viz `crmFiltry.js`). Až budou desetitisíce
  záznamů, musí se to přesunout; formát podmínek je na to připravený. Souvisí s CRM-02.

---

## 6. Modifikace a konfigurace

- [ ] **CRM-30 · Povinná pole podle stavu** — Velikost **M** · Dopad **★★**
  „Bez ceny nesmíš dát *Nabídka odeslána*", „bez data podpisu ne *Podepsaná*". Dnes hlídáme
  jen důvod prohry a zrušení.

- [ ] **CRM-31 · Workflow automatizace** — Velikost **XL** · Dopad **★★**
  „Případ vyhrán → založ objednávku", „objednávka podepsána → založ projekt ze šablony",
  „nabídka odeslána → za 7 dní úkol *zavolat*". Dnes se tyhle kroky dělají ručně.
  *Pozor:* automatika, která něco zakládá sama, musí být viditelná a vypnutelná, jinak lidé
  přestanou appce věřit.

- [ ] **CRM-32 · Šablony e-mailů a poznámek** — Velikost **M** · Dopad **★★**
  Navazuje na CRM-10.

- [ ] **CRM-33 · Skupiny a podmíněná viditelnost vlastních polí** — Velikost **M** · Dopad **★**
  Dnes jsou vlastní pole jeden seznam pod sebou. Chybí sekce a „ukaž jen když kategorie = PPA".

- [ ] **CRM-34 · Výpočtová pole** — Velikost **M** · Dopad **★**
  Např. „marže = cena − nákup" bez zásahu do kódu.

---

## 7. Uživatelská nastavení

- [ ] **CRM-35 · Profil uživatele** — Velikost **M** · Dopad **★★**
  Dnes jen změna hesla. Chybí podpis do e-mailů, telefon, fotka/iniciály, jazyk formátů.

- [ ] **CRM-36 · Volba notifikací** — Velikost **M** · Dopad **★★**
  Co chci dostávat e-mailem a co jen v appce. Bez toho je CRM-10 obtěžování.

- [ ] **CRM-37 · Oblíbené a naposledy otevřené** — Velikost **S** · Dopad **★**
  Rychlý návrat k záznamu, se kterým člověk zrovna pracuje.

- [ ] **CRM-38 · Počet řádků na stránku** — Velikost **S** · Dopad **★**
  Souvisí s CRM-02.

> **Hotové už teď:** světlý/tmavý režim, velikost textu a režim pro barvoslepé (appka je má
> globálně — `theme.js`, `velikost.js`), výchozí filtr per sekce (`crm_ulozene_filtry.vychozi`).

---

## 8. Grafické prvky

CRM nemá **ani jeden graf**, přitom grafové komponenty v appce existují (pro nabídkovač:
`GrafOdberu`, `GrafVyrobaSpotreba`, `GrafPrubehu`).

- [ ] **CRM-39 · Pipeline funnel** — Velikost **M** · Dopad **★★★**
  Kolik případů v které fázi, kolik hodnoty a kde to propadá.

- [ ] **CRM-40 · Forecast** — Velikost **M** · Dopad **★★★**
  Hodnota × pravděpodobnost podle měsíce předpokládaného uzavření. Data jsou uložená
  (`hodnota_kc`, `pravdepodobnost`, `predpokladane_uzavreni`), jen se nikde nesčítají.

- [ ] **CRM-41 · Konverze a doba ve fázi** — Velikost **M** · Dopad **★★**
  Z `crm_stav_historie`, kterou už sbíráte — kolik % projde z fáze do fáze a jak dlouho tam
  případ visí. Tohle je hlavní důvod, proč historie stavů vůbec existuje.

- [ ] **CRM-42 · Výkon OZ** — Velikost **M** · Dopad **★★**
  Vyhráno/prohráno, průměrná délka obchodu, průměrná hodnota. Navazuje na CRM-15.

- [ ] **CRM-43 · Důvody proher** — Velikost **S** · Dopad **★★**
  Rozpad podle `duvod_prohry`. Kvůli tomu se ten důvod vynucuje.

- [ ] **CRM-44 · Drobnosti v UI** — Velikost **S** · Dopad **★**
  Avatary/iniciály vlastníka na dlaždicích, barevné zvýraznění případů po termínu v kanbanu,
  ikonky typů nabídek, počítadlo dní ve fázi na dlaždici.

> **Poznámka k provedení:** grafy mají držet jeden vizuální jazyk (barvy z tokenů appky, ne
> vlastní paleta) a fungovat ve světlém i tmavém režimu — stejně jako grafy v nabídkovači.

---

## 9. Co záměrně nedělat

Zváženo a odmítnuto — ať se to nemusí řešit znovu:

| Věc | Proč ne |
|---|---|
| Territory management, round-robin přiřazování leadů | Osm lidí si zakázky rozdělí bez algoritmu |
| Vícejazyčnost, více měn | Firma obchoduje česky a v Kč; přidat lze, až bude důvod |
| Sociální sítě, chat v appce, interní zdi | Komunikace probíhá jinde, appka by soutěžila s Teams |
| Skórování leadů, AI predikce | Bez historie stovek uzavřených obchodů to jen vymýšlí čísla |
| Dvousměrná synchronizace s Raynetem | Appka Raynet **nahrazuje**; dvousměrný sync by natrvalo zabetonoval dvě pravdy |
| Vlastní workflow engine s podmínkami a větvením | Zbytečná složitost; CRM-31 stačí jako pár pevných pravidel |

---

## 10. Co už CRM umí (stav k 30. 7. 2026)

Pro srovnání a aby bylo jasné, na čem se staví. **14 tabulek, 49 API cest, 7 obrazovek.**

**Řetězec:** Zákazníci (leady/klienti) → Obchodní případy → Nabídky → Objednávky → Projekty.

| Oblast | Co funguje |
|---|---|
| Zákazníci | leady i klienti v jedné tabulce, ARES podle IČO, kontrola duplicit, kontaktní osoby, GPS |
| Případy | kanban i tabulka, kategorie jako seznam, vynucený důvod prohry, historie přesunů |
| Nabídky | vlastní sekce, obchodní stav odděleně od stavu výpočtu, podklady i výpočet na kartě případu |
| Objednávky | z přijaté nabídky s převzetím ceny, snapshot ceny, kanban |
| Projekty | číslo po případu, kroky s trváním a **návaznostmi termínů**, šablony kroků, kanban s postupem |
| Kombinace opatření | spojení PPA + peak shaving do jedné nabídky se souhrnem a oběma grafy |
| Práva | vlastník + spoluvlastníci na záznamu, právo `crm_vse`, cizí záznam vrací 404 |
| Čísla | `OP/NAB/OBJ/PRO-26-NNNN`, atomická řada, koexistence s Raynetím číslem |
| Modifikace | vlastní pole (6 typů) na 4 entitách, konfigurovatelné stavy pipeline |
| Filtry | filtry sloupců, víceúrovňové řazení (výchozí podle čísla), uložené a sdílené pohledy |
| Migrace | dohledání starých nabídek, import z Raynetu (obojí s náhledem nasucho) |

**Čeká na rozhodnutí Dana (ne na práci):**

- [ ] spustit import z Raynetu (445 klientů, 210 případů) — nevratné
- [ ] přidělit práva skupinám v Admin nastavení (bez toho CRM nikdo kromě admina nevidí)
- [ ] rozhodnout, komu z 11 Raynetích vlastníků založit účet v appce
- [ ] zavěsit 5 starých nabídek na zákazníka a případ
- [ ] nafotit screenshoty do nápovědy (v `crm.md` jsou zatím placeholdery)
