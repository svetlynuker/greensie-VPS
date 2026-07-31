# Doděláme v CRM

> **Typ:** pracovní seznam (ne návod) · **Vznikl:** 30. 7. 2026 · **Aktualizuje se průběžně**
> **Návod pro uživatele je jinde:** [`znalostni-baze/moduly/crm.md`](znalostni-baze/moduly/crm.md)

Srovnání hotového CRM v Greensie app s tím, co běžně umí Pipedrive, HubSpot, Raynet a Zoho.
Záměrně **ne** s enterprise Salesforce — cílem je firma s osmi lidmi, ne korporát.

## Zásadní rozhodnutí: import z Raynetu se dělat nebude (30. 7. 2026)

Stávající zakázky **dojedou v Raynetu**, do appky se zakládají jen **nové**. CRM tedy
nezačíná se 445 klienty a 210 případy, ale s nulou a poroste po jedné zakázce.

Co to mění:

| Položka | Bylo | Je |
|---|---|---|
| CRM-02 stránkování | ★★★, nutné **před** importem | ★, odloženo — počká, až bude v seznamu ~300 řádků |
| CRM-29 filtr na serveru | až budou desetitisíce | totéž, ale ten den přijde o roky později |
| CRM-07 merge duplicit | ★★, duplicity z importu | ★, duplicity vzniknou jen ručně a ARES na ně upozorní |
| CRM-14 import z CSV | ★ | **škrtnuto** — viz sekce 9 |
| CRM-03 kategorie | před importem | pořád brzo: každý den odkladu = víc případů k migraci |
| CRM-41 konverze, CRM-42 výkon OZ | data už sbíráte | **naplní se až za měsíce** — historie stavů začíná od nuly |
| CRM-06 kontakty jako entita | odložit, import to naplní | technicky je změna nejlevnější **teď** (0 kontaktů), přesto odloženo — viz odůvodnění u položky |

**Nové riziko, které tím vzniká** (dřív neexistovalo): firma má dvě pravdy vedle sebe —
staré v Raynetu, nové v appce. Není to technický problém, ale organizační: musí být jasné
pravidlo *„nová věc = vždycky appka"*, jinak se část zakázek založí na obou místech nebo
ani na jednom. Viz **CRM-45**.

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

- [x] **CRM-01 · UI pro „moje úkoly"** — **hotovo 30. 7. 2026** (dávka A)
  Karta „Moje úkoly v CRM" na Rozcestníku + KPI dlaždice s počtem po termínu.
  Skládání soupisu je v novém `backend/app/crm/ukoly.py`, aby endpoint
  `/crm/ukoly` i souhrn na Rozcestníku počítali stejně. Úkol ukazuje, **u čeho
  visí** (zákazník / případ / nabídka…) a kliknutím se tam dá jít.
  *Pozor při dalších úpravách:* `crm_vse` se tu neuplatňuje — „moje úkoly" jsou
  vždy jen moje, i pro vedení. A `dni` je kladné, když je úkol po termínu.

- [ ] **CRM-02 · Stránkování seznamů** — Velikost **M** · Dopad **★** · **odloženo, spouštěč: ~300 řádků**
  CRM API nemá `limit`/`offset` — vrací všechno. Bez importu roste seznam po jedné zakázce,
  takže dnes není proti čemu to dělat; pár set řádků prohlížeč unese.
  *Kde:* `crm/routes.py`, `crm/routes_realizace.py`, `CrmTabulka.jsx`.
  *Pozor:* filtrování běží na klientu, takže stránkování musí počítat s tím, že se filtruje
  nad načtenou dávkou — buď se filtr přesune na server, nebo se stránkuje až po filtru.

- [x] **CRM-03 · Konfigurovatelné kategorie případů** — **hotovo 30. 7. 2026** (dávka A)
  Nová tabulka `crm_kategorie` + `backend/app/crm/kategorie.py`; spravuje se v okně
  **Nastavení pipeline, kategorií a číslování** (právo `crm_nastaveni`). Konstanta
  v kódu zůstala jen jako seed výchozí trojice.
  *Jak je vyřešené „tady výpočet není":* kategorie má pole `typ_nabidky`. Prázdné =
  žádný výpočet, a na kartě případu se u ní tlačítko „+ nabídka" nenabídne —
  takže „Servis" jde přidat bez toho, aby appka slibovala výpočet, který neumí.
  *Ochrany:* klíč je neměnný (nesou ho případy i typ nabídky), kategorii, kterou
  případy používají, nelze smazat (jen vypnout), a vypnutá se dál zobrazuje
  u případů, které ji mají.

- [ ] **CRM-04 · Vlastní pole i na nabídkách — a hlavně dodělat objednávku a projekt** — Velikost **S** · Dopad **★★**
  `ENTITY_VLASTNICH_POLI` zná zákazníka, případ, objednávku a projekt — nabídka chybí.
  **Nález z 30. 7. 2026 (dopad zvýšen z ★ na ★★):** u objednávky a projektu jsou vlastní
  pole jen *napůl*. Admin je smí definovat (klíč je v `ENTITY_VLASTNICH_POLI`), oba modely
  mají i sloupec `extra` — ale `vlastni_pole.MODELY` zná pouze zákazníka a případ a routes
  hodnoty nikde nezpracovávají. Takže **pole se založí, ale nikde se nezobrazí ani neuloží**,
  a to tiše. Buď to dodělat, nebo ty dva klíče z `ENTITY_VLASTNICH_POLI` dočasně vyndat —
  funkce, která mlčky nic nedělá, je horší než funkce, která tam není.

---

## 2. Doporučené pořadí dávek

**Odsouhlaseno 30. 7. 2026.** Rytmus: jedna dávka = jedna branch = jeden PR = jeden deploy.
Bez importu je řídící myšlenka jiná než dřív: **CRM je hotové, ale nikdo ho nepoužívá** (1 zákazník,
1 případ, 0 objednávek, žádná skupina nemá CRM právo). Dokud tam nechodí lidi a nezakládají
zakázky, je zbytek seznamu odhad — ne zkušenost. Proto se nejdřív zapíná, pak staví.

| Dávka | Obsah | Odhad | Proč právě tady |
|---|---|---|---|
| **A · Základ** ✅ | ~~CRM-01, CRM-03, CRM-25, CRM-13~~ — **hotovo 30. 7. 2026** | — | Hotové a otestované. Práva se **záměrně nepřidělují** (rozhodl Dan 30. 7. 2026: appku zatím staví a testuje jen s Claudem, CRM vidí pouze admini). |
| **B · Ať vedení vidí čísla** ✅ | ~~CRM-39, CRM-40, CRM-43, CRM-45, CRM-22, CRM-16~~ — **hotovo 30. 7. 2026** | — | Grafové komponenty už v appce jsou, data se v nich sečtou sama. Jediná věc, po které vedení pozná, že přechod z Raynetu má smysl. **CRM-41 a CRM-42 sem nepatří** — bez uzavřených obchodů v appce nemají co ukázat. |
| **C · Denní práce se zakázkou** ✅ | ~~CRM-05, CRM-19, CRM-30, CRM-24, CRM-27, CRM-18~~ — **hotovo 31. 7. 2026** | — | Odpracováno podle seznamu. Rezerva na to, „co vyleze z provozu", tím padla — až se appka začne používat naostro, přijdou věci, které v seznamu nejsou. |
| **D · Peníze** ✅ | ~~CRM-08, CRM-09~~ — **hotovo 31. 7. 2026** | — | Zakázka projde celým řetězcem až k faktuře v appce. Katalog technologií se přitom stal katalogem produktů (244 položek z Raynetu, přílohy, zaškrtávátko Aktivní). |
| **E · Komunikace** | CRM-36 → CRM-10 → CRM-32 | ~4 dny | V tomhle pořadí. Notifikace bez volby, co chci dostávat, je obtěžování. |
| **F · Druhý životní cyklus** | CRM-11, CRM-31 | ~1 týden+ | Až budou v appce první předané projekty, ke kterým se dá servis navěsit. |
| **Odloženo s podmínkou** | CRM-02 + CRM-38 (~300 řádků v seznamu), CRM-29 (desetitisíce), CRM-06 (jen když se objeví osoba u dvou firem), CRM-41 + CRM-42 (až bude ~20 uzavřených obchodů) | — | Spouštěč je napsaný, ať se to nedělá dřív, než to začne bolet. |

**Práva: zatím NEPŘIDĚLOVAT** (rozhodnutí Dana 30. 7. 2026). CRM i nové funkce vidí jen
admini (Dan, Mirek, Dezzi test) — appka se staví a testuje interně. Návrh přidělení níž
zůstává **jako podklad na později**, ne jako úkol:

| Skupina | Přidat | Poznámka |
|---|---|---|
| **OZ** (dnes jen `projekty`) | `zakaznici`, `obchodni_pripady`, `nabidkovac` | Bez `crm_vse` vidí každý jen svoje zakázky. |
| **Vedení** | `zakaznici`, `obchodni_pripady`, `nabidkovac`, `crm_vse`, `crm_nastaveni`, `nabidkovac_katalog` | `crm_vse` = vidí přes všechny OZ. |
| **Projektové** | `zakaznici`, `obchodni_pripady`, `crm_vse` | `crm_vse` **záměrně**: právo `obchodni_pripady` odemyká i Objednávky a CRM Projekty, ale bez `crm_vse` uvidí realizátor jen záznamy, kde je zapsaný jako vlastník/spoluvlastník — takže by po přihlášení viděl prázdný seznam. U osmi lidí nemá skrývání smysl. |

*Pozor na později:* pět z osmi lidí je dnes ve skupině **Projektové** a ve skupinách **OZ**
i **Vedení** není nikdo. Až se práva budou přidělovat, musí se lidi nejdřív přeřadit —
jinak přidělení nic neudělá.

---

## 3. Moduly

- [x] **CRM-05 · Dokumenty u zákazníka a případu** — **hotovo 31. 7. 2026** (dávka C)
  Karta zákazníka i případu má blok **Dokumenty na Disku**: odkaz na složku, výpis obsahu
  a tlačítko **Založit složku na Disku**. Zakládá se tlačítkem, ne automaticky (rozhodl
  Dan) — u případu, který za dva dny skončí jako nezajímavý, by automat nechal na Disku
  prázdnou složku.
  *Jak:* nový `konektor/crm_slozky.py` bere data z CRM, ale strukturu na Disku vytváří
  tímtéž kódem jako konektor pro Raynet, takže na Disku zůstane jedna struktura. Vlastní
  klíče entit (`crm_op`, `crm_zakaznik`), aby naše ID nekolidovala s Raynetími.
  *Bylo:* dokumenty jen u nabídek; chybělo místo pro smlouvy a revizní zprávy.
  Soubory se dnes nahrávají **jen k nabídce**. Chybí místo pro smlouvy, revizní zprávy, fotky
  z realizace. Konektor už mapuje složky obchodních případů na Google Disku
  (`konektor_entity_folder`), takže nejlevnější varianta je **proklik na složku**, jako to má
  Přehled projektů (`matice/disk_parovani.py`), a teprve pak vlastní upload.

- [ ] **CRM-06 · Kontakty jako samostatná entita** — Velikost **L** · Dopad **★★** · **odloženo, spouštěč: první osoba u dvou firem**
  Kontaktní osoba je dnes podřízená jedné firmě (`crm_zakaznik_kontakty`). Nejde ji najít
  napříč zákazníky ani mít jednu osobu u dvou firem (běžné u skupin a u OSVČ, které mají
  víc subjektů).
  *Vědomé rozhodnutí:* tabulka je dnes prázdná, takže technicky je **teď** změna nejlevnější.
  Přesto se odkládá — dokud tenhle případ v provozu nenastane, byla by to práce naslepo.
  Cena za odklad je migrační skript nad tím, co do té doby naroste; roste pomalu.

- [ ] **CRM-07 · Merge duplicitních zákazníků** — Velikost **M** · Dopad **★**
  ARES varuje při zakládání, ale když duplicita přesto vznikne, není jak ji slít. Musí umět
  převést případy, nabídky, aktivity i kontakty a nechat stopu.
  *Bez importu klesla priorita:* duplicity teď mohou vzniknout jen ručně a ARES na ně
  upozorní dřív, než se založí.

- [x] **CRM-08 · Katalog produktů a položky nabídek a objednávek** — **hotovo 31. 7. 2026** (dávka D)
  Rozpis položek je na **nabídce i objednávce** (`nabidka_polozky`,
  `crm_objednavka_polozky`) a při vzniku objednávky z nabídky se **překlopí**
  (zkopíruje, ne naváže) — objednávka je obchodní dokument a nesmí se měnit,
  když někdo přepočítá nabídku. Položka může, ale nemusí být z katalogu; název,
  kód a ceny jsou vždy snapshot.
  *Cena objednávky* = součet rozpisu, dokud ji někdo nepřepíše ručně (`cena_rucni`);
  pak má přednost ruční hodnota a appka jen ukáže rozdíl (rozhodl Dan).
  *Katalog technologií se stal katalogem produktů:* tabulka `technologie` má
  navíc kód, kategorii, jednotku, popis, nákupní cenu, DPH, platnost, zdroj,
  přejmenované `dostupnost` → `aktivni` a novou tabulku příloh
  `technologie_prilohy` (technický list, foto, certifikát; víc souborů naráz).
  **Naimportováno 244 položek** z Raynetu (`docs/moduly/produkty/Produkty_výběr.xlsx`)
  skriptem `backend/scripts/import_produkty.py` — idempotentní podle kódu, s náhledem
  nasucho. 85 baterií z ceníku BESS zůstalo nedotčených (poznají se podle
  `zdroj='bess_cenik'`) a dál pohánějí simulaci peak shavingu.
  *Nákupní cena a marže:* posílají se jen s právem `nabidkovac_katalog` — ne skryté
  na frontendu, ale vůbec ne v odpovědi API.
  *Pozor při dalších úpravách:* validace „baterie musí mít kW i kWh“ platí jen pro
  `zdroj='bess_cenik'` — bateriové komponenty z ceníku (BMS, racky) ta čísla nemají
  a do simulace se stejně nedostanou (filtr na NOT NULL).

- [x] **CRM-09 · Napojení na fakturaci a Přehled financí** — **hotovo 31. 7. 2026** (dávka D)
  Řetěz **objednávka → faktura → zaplaceno** na kartě objednávky: splátkový kalendář
  z předvolby (100 % / 50-50 / 30-40-30), termíny po měsíci, souhrn
  vyfakturováno / zaplaceno / zbývá rozepsat / po termínu.
  *Jedna tabulka, dva rodiče (rozhodl Dan):* faktura visí buď na Freelo projektu
  (`projekt_id`, starý svět), nebo na CRM objednávce (`crm_objednavka_id`).
  Hlídá to `ck_faktura_prave_jeden_rodic`. Díky tomu je párování s POHODOU přes
  variabilní symbol napsané jednou a Přehled financí zůstal jedna obrazovka —
  CRM objednávky v něm mají vlastní tabulku pod projekty.
  *Editace jen z CRM:* `/finance/faktura/{id}` na fakturu objednávky vrací 409.
  Jinak by ji mohl měnit i ten, kdo na zakázku podle práv CRM nevidí.
  *Přepočet po změně ceny je vždy na tlačítko* a sáhne jen na nevystavené faktury —
  vystavená faktura je doklad, ne plán. Rozdělení na haléř hlídá test
  (3× 33,33 % z milionu musí dát přesně milion).

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

- [x] **CRM-13 · Export do CSV / Excelu** — **hotovo 30. 7. 2026** (dávka A)
  Tlačítko „↓ Export CSV (n)" v liště tabulky všech pěti sekcí. Exportuje **přesně
  to, co je vidět**: sloupce v zobrazeném pořadí, řádky už profiltrované a seřazené.
  Modul `frontend/src/crmExport.js`.
  *Vyladěné pro český Excel:* BOM (jinak rozsypaná diakritika), oddělovač `;`,
  desetinná čárka, datum `DD.MM.RRRR`.
  *Bezpečnost:* hodnoty začínající `=`, `+`, `-`, `@` se odzbrojují apostrofem —
  jinak by se telefon „+420…" a text `=HYPERLINK(…)` staly v Excelu formulí.

- [x] **CRM-14 · Import z CSV** — **škrtnuto 30. 7. 2026**, viz sekce 9

- [ ] **CRM-15 · Cíle a provize OZ** — Velikost **L** · Dopad **★★**
  Bez cílů nejde měřit výkon a bez provizí se stejně počítají v Excelu. Navazuje na CRM-42,
  takže stejný spouštěč: má smysl až budou v appce uzavřené obchody.

---

## 4. Pohledy

- [ ] **CRM-16 · Můj den** — Velikost **M** · Dopad **★★★** · *dávka B*
  Jedna obrazovka: úkoly po termínu, dnešní úkoly, případy bez aktivity X dní, nabídky
  odeslané bez reakce. Staví na CRM-01.

- [ ] **CRM-17 · Kalendář aktivit** — Velikost **XL** · Dopad **★★★** · **ROZPRACOVÁNO od 30. 7. 2026**
  Zadání Dana z 30. 7. 2026 je širší než původní odrážka („měsíční/týdenní pohled"), proto
  velikost L → XL a dopad ★★ → ★★★. Dělá se **před** dávkou B, protože bez kalendáře
  nemá OZ kde plánovat den.

  **Co je zadané:** týdenní mřížka po–ne (den = sloupec, hodina = řádek), vlevo čtvercový
  měsíc s klikatelnými dny; barvy podle druhu aktivity, **barvu si každý mění ve svém
  nastavení**; rychlé i uložitelné filtry; klik do prázdna zakládá aktivitu (klient / OP /
  nabídka nepovinně, nebo **soukromá událost**); klik na aktivitu ji uzavře s výsledkem
  a umí hned naplánovat další; **kalendáře dalších osob** k porovnání.

  **Viditelnost (odsouhlaseno):** moje = detail · cizí **soukromá = jen blok, i pro vedení
  a admina** · cizí běžná: účastník a `crm_vse` vidí detail, ostatní jen „Obsazeno".

  **Etapy** (nasazuje se po etapách):

  | | Co | Stav |
  |---|---|---|
  | K1 | aktivita se učí **čas** (`zacatek` + `delka_min`), **stavy** naplánováno / realizováno / nekonalo se, **výsledek**, **soukromá**, **účastníci**; pravidla viditelnosti; endpointy `/crm/kalendar` | ✅ hotovo |
  | K2 | stránka **Nastavení** (osobní volby + barvy druhů aktivit) | ✅ hotovo |
  | K3 | kalendář: týdenní mřížka + čtvercový měsíc | ✅ hotovo |
  | K4a | **vzhled podle předlohy** `docs/moduly/Kalendář/`: horní lišta (ISO týden, ‹ Dnes ›), panel filtrů (uživatelé / typy / zobrazení / kategorie, záložka Nenaplánováno), komprimovaná noc a večer, pruh vícedenních; aktivita se učí prioritu, místo a barevnou kategorii | ✅ hotovo |
  | K4d | **drag & drop**: přesun tažením (i mezi dny), změna délky tažením za horní/dolní hranu, krok 15 min | ✅ hotovo (mimo pořadí, na přání Dana) |
  | K4b | modál nové/editace aktivity podle předlohy (typ, priorita, termín, místo s „U nás", kategorie, účastníci, „Čeho se to týká", náhled dne) | ✅ hotovo |
  | K4c | popover detailu ukotvený u dlaždice, akce Mám hotovo / Zrušit / Přesunout / … (upravit, vrátit do plánu, smazat) | ✅ hotovo |
  | K5 | opakované události: denně / pracovní dny / týdně / měsíčně / vlastní po N dnech, povinný konec (datum nebo počet, max 2 roky), úprava a mazání se ptá „tuhle / tuhle a další / celou sérii" | ✅ hotovo |
  | K6 | pohledy **Den / Týden / Měsíc** (přepínač, volba se pamatuje v profilu); správa barevných kategorií aktivit a firemní adresa pro „U nás" v nastavení CRM. *(Filtry a kalendáře kolegů hotové už v K4a.)* | ✅ hotovo |

  **Kalendář je hotový (30. 7. 2026).** Vědomě mimo rozsah: napojení na Google
  Kalendář a připomenutí (to patří k notifikacím, CRM-10/36).

- [x] **CRM-18 · Timeline zákazníka** — **hotovo 31. 7. 2026** (dávka C)
  Nová záložka **Historie** na kartě zákazníka: aktivity, vznik případů, nabídek,
  objednávek a projektů a změny stavů na jedné chronologické ose, seskupené po dnech.
  Změny stavů se berou z `crm_stav_historie` — kvůli tomuhle ta tabulka existuje.
  *Soukromé aktivity v ose nejsou* (nemají vazbu na zákazníka a obsah nevidí ani vedení).
  *Skládá se v Pythonu z pěti dotazů, ne SQL UNIONem:* každá entita má jiné sloupce
  a UNION by je musel narovnávat ručně při každé změně pole.
  Všechno chronologicky na jedné ose (aktivity, nabídky, objednávky, projekty, změny stavů).
  Dnes je to rozdělené do záložek a člověk si musí děj skládat v hlavě.

- [x] **CRM-19 · Hromadné akce nad seznamem** — **hotovo 31. 7. 2026** (dávka C)
  Zaškrtávátka v tabulce případů; lišta nabídne změnu vlastníka, změnu stavu a **plánování
  aktivit za sebe** (Danovo rozšíření: 10 klientů → telefonát → start 8:00 → 15 min na
  každou → appka je naskládá 8:00, 8:15, 8:30…). Mazání záměrně není — Dan ho nevybral.
  *Pojistky:* práva se ověřují u každého záznamu zvlášť (cizí se přeskočí, ne aby dávka
  spadla), u prohry se vynucuje důvod i hromadně, řada aktivit nepřeteče do noci
  (pokračuje dalším dnem) a před založením se ukáže plán, kdo dostane jaký čas.
  Označit víc řádků a hromadně: změnit vlastníka, změnit stav, přidat aktivitu, exportovat.

- [ ] **CRM-20 · Mapa zákazníků a projektů** — Velikost **M** · Dopad **★★**
  **GPS už v datech je** (z Raynetu i z ARESu). U FVE se hodí na plánování obchůzek, na
  posouzení lokality a na „co máme v okolí, když už tam jedeme".

- [ ] **CRM-21 · Ganttův diagram projektu** — Velikost **L** · Dopad **★★**
  Kroky mají trvání i návaznosti, takže Gantt je nad nimi přirozený a ukáže kritickou cestu.

- [ ] **CRM-22 · KPI dlaždice nad seznamy** — Velikost **S** · Dopad **★★** · *dávka B*
  Nad tabulkou počet, celková hodnota, průměr, kolik je po termínu. Appka má na to hotový
  vizuální prvek (`gs-kpi` na rozcestníku).

- [ ] **CRM-23 · Swimlanes v kanbanu** — Velikost **M** · Dopad **★**
  Řádky podle vlastníka (nebo kategorie) — vedení hned vidí, kdo má co rozjeté.

- [x] **CRM-24 · Globální hledání** — **hotovo 31. 7. 2026** (dávka C)
  Pole v horní liště (+ **Ctrl+K** odkudkoli) prohledá zákazníky, případy, nabídky,
  objednávky i projekty. Podle zadání Dana: názvy a čísla záznamů + IČO, telefon, e-mail
  a město. Text aktivit ne — výsledků by bylo mnoho a hledání by zpomalilo.
  *Hledá i bez diakritiky* („kovarna" najde „Kovárna") přes `translate()` v SQL, aby to
  nezáviselo na rozšíření `unaccent`. Klávesy ↑ ↓ Enter, dotaz se posílá se zpožděním
  250 ms a starší odpověď nepřepíše novější.
  *Práva:* každá entita jde přes filtr viditelnosti — bez toho by hledání bylo obchvat
  práv a nejjednodušší způsob, jak zjistit, na čem pracují ostatní.
  Jedno pole, které prohledá zákazníky, případy, nabídky, objednávky i projekty. Dnes se hledá
  v každé sekci zvlášť.

---

## 5. Filtry a práce se seznamy

Základ je hotový (filtry sloupců, víceúrovňové řazení, uložené a sdílené pohledy).
Co běžná CRM mají navíc:

- [x] **CRM-25 · Relativní datumové filtry** — **hotovo 30. 7. 2026** (dávka A)
  Nový operátor **„je v období"** se 17 volbami (dnes, tento týden, posledních
  7/30/90 dní, tento/minulý/příští měsíc, tento/minulý rok, v minulosti,
  v budoucnosti…). V podmínce se drží **klíč období**, ne datum, takže se rozsah
  dopočítává k dnešku — uložený filtr proto nezastará. V editoru je vedle výběru
  vidět, co období dnes znamená (`1. 7. – 31. 7. 2026`).
  *Pozor:* dny se počítají v lokálním čase, ne přes `toISOString()` — ten by
  v našem pásmu každý večer hlásil „dnes" jako předchozí den.

- [ ] **CRM-26 · OR a skupiny podmínek** — Velikost **M** · Dopad **★★**
  Dnes se všechny podmínky sčítají (AND). Chybí „stav je Nabídka **nebo** Vyjednávání".
  Formát podmínek v `crm_ulozene_filtry` to zvládne, jde o vyhodnocení v `crmFiltry.js`.

- [x] **CRM-27 · Rychlé předvolby** — **hotovo 31. 7. 2026** (dávka C)
  Pilulky nad seznamem: **Jen moje · Jen otevřené · Po termínu · Uzavření tento měsíc**.
  Dají se kombinovat i odkliknout a vracejí podmínky ve **stejném formátu** jako vlastní
  filtr — takže se dají dál upravit a uložit jako pohled. Datumové předvolby používají
  relativní období, aby za měsíc nelhaly.
  „Jen moje", „jen otevřené", „po termínu" jedním kliknutím, bez skládání filtru.

- [ ] **CRM-28 · Skrývání a přeskládání sloupců** — Velikost **M** · Dopad **★★**
  Včetně uložení rozvržení k filtru — kdo sleduje jiná čísla, chce jinou tabulku.

- [ ] **CRM-29 · Filtr na serveru** — Velikost **L** · Dopad **★** · **odloženo, spouštěč: desetitisíce záznamů**
  Dnes se filtruje na klientu (vědomé rozhodnutí, viz `crmFiltry.js`). Až budou desetitisíce
  záznamů, musí se to přesunout; formát podmínek je na to připravený. Souvisí s CRM-02.

---

## 6. Modifikace a konfigurace

- [x] **CRM-30 · Povinná pole podle stavu** — **hotovo 31. 7. 2026** (dávka C)
  U každého stavu pipeline se zaškrtne, co musí být vyplněné pro přechod do něj. Zadání
  Dana: **jakékoli editovatelné pole, stávající i budoucí** — proto se seznam skládá za
  běhu (systémová pole z jedné deklarace v `povinna_pole.py` + vlastní pole z DB, ta se
  v nabídce objeví hned jak vzniknou). Kromě políček jdou vynutit i vazby („aspoň jedna
  nabídka", „kontaktní osoba u zákazníka").
  *Hlídá se PŘECHOD, ne uložení:* případ se zakládá rozpracovaný a nutit cenu hned při
  vzniku by lidi otravovalo (psali by tam nuly). Kontrola platí i pro hromadnou změnu stavu.
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

- [~] **CRM-35 · Profil uživatele** — Velikost **M** · Dopad **★★** · **částečně hotovo 30. 7. 2026**
  **Hotovo (etapa K2 kalendáře):** stránka **Nastavení** (`/nastaveni`, odkaz v nabídce
  u jména) — osobní volby na jednom místě: režim zobrazení, velikost textu, režim pro
  barvoslepé a **barvy druhů aktivit v kalendáři**. Vše se ukládá do
  `uzivatelska_nastaveni`, takže to platí i na jiném počítači.
  **Zbývá:** podpis do e-mailů (souvisí s CRM-10), telefon, fotka místo iniciál.

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

- [ ] **CRM-39 · Pipeline funnel** — Velikost **M** · Dopad **★★★** · *dávka B*
  Kolik případů v které fázi, kolik hodnoty a kde to propadá.

- [ ] **CRM-40 · Forecast** — Velikost **M** · Dopad **★★★** · *dávka B*
  Hodnota × pravděpodobnost podle měsíce předpokládaného uzavření. Data jsou uložená
  (`hodnota_kc`, `pravdepodobnost`, `predpokladane_uzavreni`), jen se nikde nesčítají.

- [ ] **CRM-41 · Konverze a doba ve fázi** — Velikost **M** · Dopad **★★** · **odloženo, spouštěč: ~20 uzavřených obchodů**
  Z `crm_stav_historie` — kolik % projde z fáze do fáze a jak dlouho tam případ visí. Tohle je
  hlavní důvod, proč historie stavů vůbec existuje. **Ale** historie má dnes 2 řádky a bez
  importu začíná od nuly, takže graf by první měsíce ukazoval prázdno nebo nesmysl z pár vzorků.

- [ ] **CRM-42 · Výkon OZ** — Velikost **M** · Dopad **★★** · **odloženo, stejný spouštěč jako CRM-41**
  Vyhráno/prohráno, průměrná délka obchodu, průměrná hodnota. Navazuje na CRM-15.

- [ ] **CRM-43 · Důvody proher** — Velikost **S** · Dopad **★★** · *dávka B*
  Rozpad podle `duvod_prohry`. Kvůli tomu se ten důvod vynucuje.

- [ ] **CRM-44 · Drobnosti v UI** — Velikost **S** · Dopad **★**
  Avatary/iniciály vlastníka na dlaždicích, barevné zvýraznění případů po termínu v kanbanu,
  ikonky typů nabídek, počítadlo dní ve fázi na dlaždici.

- [ ] **CRM-45 · Přiznat, že Raynet ještě jede** — Velikost **S** · Dopad **★★★** · *dávka B*
  Vznikla rozhodnutím neimportovat. Appka se dnes tváří, jako by v ní byl celý byznys —
  a přitom v ní budou jen nové zakázky, zatímco staré dojíždějí v Raynetu. Bez toho bude
  **forecast a funnel v dávce B vypadat jako propad obchodu**, i když se nic nestalo.
  *Co udělat:*
  - u grafů a KPI napsat, od kterého data appka data má („zakázky založené od …")
  - v Zákaznících a Případech viditelný odkaz „starší zakázky najdeš v Raynetu"
  - jedno pravidlo v nápovědě: **nová věc = vždycky appka, do Raynetu se už nezakládá**

  *Volitelné později:* až Raynet dojede, jednorázově dotáhnout jen **historii uzavřených
  obchodů** (vyhráno/prohráno + důvod), aby CRM-41 a CRM-43 měly z čeho počítat. Není to
  obousměrný sync (ten zůstává zakázaný, viz sekce 9), ale jednorázové čtení na konci.

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
| **Import z Raynetu** (CRM-14 i hotový `import_raynet.py`) | Rozhodnuto 30. 7. 2026: stávající zakázky dojedou v Raynetu, do appky jdou jen nové. Kód importu zůstává v repu nespuštěný — pro případ, že se rozhodnutí změní. |
| **Import z CSV** (bývalé CRM-14) | Padá se stejným rozhodnutím. Nových zakázek je pár měsíčně, ty se zakládají ručně. |

---

## 10. Co už CRM umí (stav k 30. 7. 2026)

Pro srovnání a aby bylo jasné, na čem se staví. **14 tabulek, 49 API cest, 7 obrazovek.**

**Řetězec:** Zákazníci (leady/klienti) → Obchodní případy → Nabídky → Objednávky → Projekty.

| Oblast | Co funguje |
|---|---|
| Zákazníci | leady i klienti v jedné tabulce, ARES podle IČO, kontrola duplicit, kontaktní osoby, GPS |
| Případy | kanban i tabulka, kategorie jako seznam, vynucený důvod prohry, historie přesunů |
| Nabídky | vlastní sekce, obchodní stav odděleně od stavu výpočtu, podklady i výpočet na kartě případu |
| Objednávky | z přijaté nabídky s převzetím ceny, snapshot ceny, kanban, **rozpis položek a fakturace** |
| Katalog produktů | 329 položek (244 z Raynetu + 85 BESS), kód, kategorie, jednotka, nákupní cena a marže jen pro vedení, DPH, platnost, přílohy (technický list, foto), zaškrtávátko Aktivní, hromadné zapnutí/vypnutí |
| Peníze | rozpis položek na nabídce i objednávce, splátkové kalendáře, řetěz objednávka → faktura → zaplaceno, objednávky v Přehledu financí |
| Projekty | číslo po případu, kroky s trváním a **návaznostmi termínů**, šablony kroků, kanban s postupem |
| Kombinace opatření | spojení PPA + peak shaving do jedné nabídky se souhrnem a oběma grafy |
| Práva | vlastník + spoluvlastníci na záznamu, právo `crm_vse`, cizí záznam vrací 404 |
| Čísla | `OP/NAB/OBJ/PRO-26-NNNN`, atomická řada, koexistence s Raynetím číslem |
| Modifikace | vlastní pole (6 typů) na 4 entitách, konfigurovatelné stavy pipeline |
| Filtry | filtry sloupců, víceúrovňové řazení (výchozí podle čísla), uložené a sdílené pohledy |
| Migrace | dohledání starých nabídek, import z Raynetu (obojí s náhledem nasucho) |

**Skutečný stav v produkční DB k 30. 7. 2026** — proto je dávka A o zapnutí, ne o featurách:

| Tabulka | Řádků |
|---|---|
| `crm_zakaznici` | 1 |
| `crm_obchodni_pripady` | 1 |
| `crm_objednavky`, `crm_projekty`, `crm_aktivity`, `crm_ulozene_filtry`, `crm_vlastni_pole`, `crm_zakaznik_kontakty` | 0 |
| `crm_stavy` (konfigurace pipeline) | 21 |
| `crm_projekt_sablony` / `_kroky` | 2 / 16 |
| skupiny s CRM právem | **0 ze 3** |

**Čeká na rozhodnutí Dana (ne na práci):**

- [x] ~~spustit import z Raynetu~~ — **rozhodnuto 30. 7. 2026: nebude, viz úvod**
- [x] ~~přidělit práva skupinám~~ — **odloženo 30. 7. 2026:** zatím nikomu kromě adminů,
      appka se staví a testuje interně. Až na to přijde, nejdřív přeřadit lidi do skupin
      OZ a Vedení (dnes je 5 z 8 v *Projektové*, v OZ i Vedení nikdo).
- [ ] zavěsit 5 starých nabídek na zákazníka a případ
- [ ] říct lidem pravidlo *„nová zakázka = vždycky appka"* (souvisí s CRM-45)
- [ ] nafotit screenshoty do nápovědy (v `crm.md` jsou zatím placeholdery)
