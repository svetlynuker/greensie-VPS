# Zákazníci a Obchodní případy (CRM)

> **Sekce v nabídce:** `zakaznici`, `obchodni_pripady` · **Adresy (routy):** `/zakaznici/lead`, `/zakaznici/klient`, `/zakaznici/detail/:id`, `/pripady`, `/pripady/detail/:id` · **Kdo smí otevřít:** kdokoli s právem `zakaznici` resp. `obchodni_pripady` (bez práva se sekce v nabídce vůbec nezobrazí; admin vždy)
> **Kód:** frontend `frontend/src/pages/Zakaznici.jsx`, `ZakaznikDetail.jsx`, `ObchodniPripady.jsx`, `ObchodniPripadDetail.jsx`, backend `backend/app/crm/`

Evidence obchodu: **zákazník → obchodní případ → nabídka** (a dál objednávka a projekt, které
se připravují). Cílem je, aby obchodní zástupce nemusel chodit do samotného nabídkovače —
všechno podstatné se zakládá a ukládá u zákazníka a u případu, a výpočet nabídky se z případu
jen zavolá.

> 📸 SCREENSHOT: kanban obchodních případů se sloupci fází a dlaždicemi zakázek

---

## 🧑 Pro uživatele

### Zákazníci: leady a klienti
Jedna evidence, dva pohledy přepínané záložkami:

- **Leady** — firmy, se kterými se obchod teprve baví.
- **Klienti** — firmy, se kterými už reálně obchodujeme.

Je to **jeden a tentýž záznam**, jen s přepínačem. Když se z leadu stane klient, nic se
nekopíruje a nic se neztrácí — zůstanou u něj všechny poznámky i obchodní případy z doby, kdy
byl ještě lead. Převést ho jde tlačítkem **„Převést na klienta"**, a stane se to i **samo**
v okamžiku, kdy se jeho první obchodní případ označí jako vyhraný.

### Zakládání zákazníka: nech to na IČO
V okně nového zákazníka je nahoře pole **IČO** a tlačítko **„Doplnit z ARESu"**. Zadej osm
číslic, klikni — a název firmy, DIČ a adresa se vyplní z veřejného registru. Kromě opisování
to řeší dvě věci:

- **Překlepy.** Název firmy z nabídky jde zákazníkovi na papír; překlep v něm vypadá špatně.
- **Duplicity.** Když už firmu s tímto IČO vedeme, appka to napíše (i když ji vede kolega),
  takže nevzniknou dva záznamy o téže firmě.

Když ARES nefunguje nebo IČO nezná, **nic se nezablokuje** — objeví se upozornění a údaje
vyplníš ručně.

> Pole **GPS šířka / délka** není kosmetika: bere si je výpočet PPA jako polohu elektrárny.
> U klientů, kde se chystá FVE, se je vyplatí doplnit.

### Karta zákazníka
Tři záložky:

1. **Přehled** — údaje firmy a **kontaktní osoby**. Hlavní kontakt může být jen jeden; když
   někoho označíš jako hlavního, předchozí se automaticky přepne na běžného.
2. **Obchodní případy** — seznam zakázek zákazníka, klik otevře případ.
3. **Aktivity a úkoly** — log práce (viz níže).

Nahoře vpravo je **„+ Obchodní případ"** — odtud se zakládá zakázka.

### Obchodní případy: kanban a tabulka
Sekce se otevře v **kanbanu**, protože hlavní denní práce je posouvat případy fázemi:

- **Dlaždici přetáhni** do jiného sloupce a stav se změní.
- Na dlaždici je i **rozbalovací volba stavu** — na mobilu a klávesnicí, kde přetahování
  nefunguje.
- V hlavičce sloupce je **počet** případů a pod ním **součet hodnot** — hned je vidět, kolik
  peněz v které fázi visí.

Přepínačem se dá zapnout **tabulka** s hledáním podle čísla, názvu nebo zákazníka.

### Čísla záznamů
Každý záznam má viditelné ID, které se dá nadiktovat do telefonu:

| Záznam | Formát | Poznámka |
|---|---|---|
| Obchodní případ | `OP-26-0301` | 26 = rok, číslo z řady |
| Nabídka | `NAB-26-0007` | vlastní řada |
| Objednávka | `OBJ-26-0012` | vlastní řada *(připravuje se)* |
| Projekt | `PRO-26-0301` | **kopíruje číslo případu**; druhý projekt téhož případu má `-2` |

Čísla přiděluje appka sama, do ruky se nezadávají — jinak by mohly vzniknout dva záznamy
se stejným ID. Řada se každý rok restartuje.

> ⚠️ **Čísla `OP-` používá i Raynet.** Dokud běží obojí, appka čísluje **nad** nejvyšším
> Raynetím číslem (proto začíná na `OP-26-0301`, ne na jedničce). Podrobně v sekci pro admina.

### Vytvoření nabídky z případu
Tlačítko **„+ Vytvořit nabídku"** na kartě případu:

- Má-li případ **jednu kategorii** (PPA / Prodej / Peak shaving), předvybere ji.
- Má-li **víc kategorií nebo žádnou**, appka se zeptá, na co nabídku chceš.

Nabídka se založí **pod případem** a **údaje zákazníka si vezme z jeho karty** — jméno, adresu
i GPS. Nic se neopisuje. Pak už jsi v nabídkovači a počítáš jako dřív; nabídka zůstane
navázaná na případ a je vidět na záložce **Nabídky**.

### Aktivity a úkoly
Na kartě zákazníka i případu je log práce: **poznámka, telefonát, e-mail, schůzka, úkol**.
Aktivita s **termínem** se stává úkolem — nedokončené jsou nahoře a po termínu se zvýrazní
červeně. Tohle je místo, kam patří „volal jsem, chce to probrat po dovolené" — jinak to zůstane
jen v hlavě jednoho člověka.

### Vlastní pole: když chcete sledovat něco dalšího
Rozhodne se, že u obchodního případu chcete vést třeba **číslo odběrného místa** nebo
**napěťovou hladinu**? Není na to potřeba programátor. Na kartě zákazníka i případu je blok
**Doplňující údaje** a v něm (pro toho, kdo má právo `crm_nastaveni`) tlačítko
**„⚙ Upravit pole"**.

Pole má název, typ a nepovinnou nápovědu, která se zobrazí pod polem ve formuláři:

| Typ | K čemu |
|---|---|
| Text | jeden řádek — čísla smluv, označení |
| Delší text | víc řádků |
| Číslo | dá se s ním počítat a řadit; příjme i „1 250,5" |
| Datum | vybírá se z kalendáře |
| Ano / ne | zaškrtávátko |
| Výběr ze seznamu | volby napíšeš po řádcích, nikdo pak nemůže udělat překlep |

Dva přepínače u každého pole:

- **Povinné** — bez vyplnění nejde záznam uložit.
- **Zobrazit i v seznamu** — pole přibude jako **sloupec v tabulce** (u případů i na dlaždici
  kanbanu), takže se podle něj dá přehledově koukat.

Pořadí polí se posouvá šipkami, tak se ve formuláři i objeví.

> **Přejmenovat pole je bezpečné.** Uvnitř si appka drží neměnný klíč, takže po
> přejmenování zůstanou vyplněné hodnoty na svém místě.
>
> **Smazání pole hodnoty nemaže** — jen je přestane zobrazovat, a appka řekne, kolika záznamů
> se to týkalo. Když pole smažeš omylem, založ ho znovu se stejným názvem a data se vrátí.

Zákazníci a obchodní případy mají **každý svou sadu** polí; pole přidané u případů se
u zákazníků neobjeví.

### Prohra: proč se appka ptá na důvod
Při přesunu případu do **prohraného** stavu se objeví dotaz na důvod (cena, konkurence,
odložená investice…). Bez důvodu prohru uložit nelze. Není to šikana: bez důvodů proher
nemá statistika pipeline žádnou vypovídací hodnotu a za měsíc si to už nikdo nevybaví.

---

## 🛠 Pro admina / provoz

### Práva
| Právo | Co dovolí |
|---|---|
| `zakaznici` | otevřít sekci Zákazníci |
| `obchodni_pripady` | otevřít sekci Obchodní případy |
| `crm_vse` | **vidět všechny záznamy**, ne jen svoje |
| `crm_nastaveni` | měnit stavy pipeline, číselné řady a **vlastní pole** |

**Viditelnost jednotlivých záznamů** je nad rámec otevíracích práv. Každý zákazník i případ má
**vlastníka** a případně **spoluvlastníky**. Kdo nemá `crm_vse`, vidí jen záznamy, kde je
vlastníkem nebo spoluvlastníkem; cizí záznam pro něj **neexistuje** (vrací se 404, ne 403 —
aby se hádáním ID nedalo zjistit, kolik zakázek firma vede).

- „Vedení vidí všechno" se nastaví tak, že **skupina Vedení** dostane právo `crm_vse`.
- Jednotlivci se totéž dá přidělit jako **individuální výjimka** u jeho účtu.
- Žádná hierarchie rolí se nezavádí — je to obyčejné právo jako `finance`.

**Vlastníka smí přepsat jen ten, kdo má `crm_vse`.** Běžný uživatel je vlastníkem toho, co
založí; jinak by si mohl záznam přehodit na kolegu a sám o něj přijít, nebo naopak přebrat cizí.

Záznamy **bez vlastníka** (například po budoucí migraci starých nabídek) vidí jen ten, kdo má
`crm_vse` — „nikomu nepatřící" data se nemají zjevit všem.

### Stavy pipeline (sloupce kanbanu)
Stavy **nejsou v kódu**, jsou v tabulce `crm_stavy`. V sekci Obchodní případy je pod právem
`crm_nastaveni` tlačítko **„⚙ Stavy pipeline"**, kde se dají přidávat, přejmenovávat, barvit
a přeskládat.

Každý stav má **druh**:

| Druh | Chování |
|---|---|
| `otevreny` | případ je živý, počítá se do pipeline |
| `vyhra` | uzavírá případ, zapíše datum a **z leadu udělá klienta** |
| `prohra` | uzavírá případ a **vynutí důvod prohry** |

Omezení: stav, ve kterém nějaké případy jsou, **nejde smazat** (nejdřív je přesuň), a poslední
stav nejde smazat vůbec. Strojový klíč stavu se **nikdy nemění** ani při přejmenování — drží
ho záznamy i historie.

Každý přesun se zapisuje do `crm_stav_historie` (kdo, kdy, odkud kam). Na kartě případu je to
vidět na záložce **Historie stavů**. Bez toho by nešlo zjistit, jak dlouho případ visel v které
fázi.

### Číselné řady a koexistence s Raynetem
Tabulka `crm_ciselne_rady`, jeden řádek na (entita, rok). Číslo se přiděluje **atomicky**
(`SELECT … FOR UPDATE`) ve stejné transakci jako záznam — dva OZ zakládající případ ve stejnou
sekundu nedostanou stejné číslo, a když založení spadne, číslo se nespotřebuje.

**Proč OP nezačíná na jedničce.** Prefix `OP-` už používá Raynet: v jeho obchodních případech
jsou letos čísla `OP-26-002` až `OP-26-228` (starší na tři místa, novější na čtyři). Na tomhle
čísle navíc stojí dvě věci, které v appce běží dnes:

- **konektor** podle něj pojmenovává složky obchodních případů na Google Disku,
- **Přehled projektů** podle něj páruje Freelo projekty s jejich složkou dokumentů
  (`matice/disk_parovani.py`, regulární výraz `OP-\d{2,}-\d+`).

Kdyby appka začala vydávat `OP-26-0001`, existovala by dvě různá čísla se stejným prefixem.
Proto se řada při prvním spuštění posadí **nad nejvyšší známé Raynetí číslo, zaokrouhleně na
další stovku** (228 → **301**). Nejvyšší číslo se zjišťuje ze dvou zdrojů: z `raynet_code`
u případů v CRM a z **názvů složek, které drží konektor** (`konektor_entity_folder`,
`entity='deal'`) — tam jsou i případy, které v appce ještě nejsou.

Rezerva do další stovky je tam schválně: Raynet během koexistence čísla dál vydává, takže
„nejvyšší + 1" by se s ním po pár zakázkách potkalo.

**Case případů, které vznikly v Raynetu:** na kartě případu (v úpravě) je pole **Raynetí
číslo**. Vyplň ho a párování složky dokumentů na Disku funguje dál. Appka toto pole nikdy
nepřepisuje na prázdno.

Řadu lze přenastavit v okně **Stavy pipeline** (šířka čísla, další číslo). Zpět pod už vydané
číslo to nepustí — vznikla by duplicitní ID.

### Vlastní pole: jak to funguje uvnitř
Stejný princip, jaký appka už používá pro vlastní sloupce katalogu technologií
(`KatalogSloupec` + `Technologie.extra`):

- **definice** pole je řádek v `crm_vlastni_pole` (entita, klíč, název, typ, volby, povinné,
  v seznamu, pořadí),
- **hodnoty** jsou v JSONB sloupci `extra` daného záznamu pod klíčem pole.

Proč JSONB a ne skutečný sloupec: přidání sloupce znamená migraci a nasazení, což je přesně
to, čemu se tahle funkce vyhýbá. Cenou je, že se nad polem nedá udělat databázový index —
u řádu stovek záznamů to nehraje roli.

Pravidla, která backend drží (`app/crm/vlastni_pole.py`):

| Pravidlo | Proč |
|---|---|
| `klic` se odvodí z názvu a **nikdy se nemění** | drží ho uložené hodnoty; změna by data odpojila |
| neznámé klíče se při ukládání **zahodí**, ne odmítnou | formulář z déle otevřené stránky by po smazání pole nešel uložit vůbec |
| prázdná hodnota se neukládá | v JSONB nezůstávají prázdné klíče |
| typ se kontroluje a hodnota převede do kanonické podoby | `„1 250,5"` → `1250.5`, datum na ISO |
| u typu `vyber` musí hodnota být z voleb | jinak by seznam nebyl k ničemu |
| smazání pole **nemaže hodnoty** | omylem smazané pole se dá vrátit se všemi daty |

Rozšíření na další obrazovku (až budou objednávky a projekty) je práce na dva řádky: přidat
klíč do `ENTITY_VLASTNICH_POLI` a model do `vlastni_pole.MODELY` — entita jen musí mít
sloupec `extra`.

Práva: **čtení definic** smí každý, kdo vidí CRM (z definic se kreslí formulář i sloupce),
**měnit** je smí jen `crm_nastaveni`.

### Datový model
| Tabulka | Co drží |
|---|---|
| `crm_zakaznici` | leady i klienti (`typ`), adresa, GPS, vlastník, `raynet_id` |
| `crm_zakaznik_kontakty` | kontaktní osoby, příznak hlavního |
| `crm_obchodni_pripady` | číslo, zákazník, kategorie (seznam), stav, hodnota, důvod prohry, `raynet_code` |
| `crm_stavy` | konfigurovatelné stavy pipeline pro `op` / `nab` / `obj` / `pro` |
| `crm_stav_historie` | dráha záznamu fázemi (generická pro všechny entity) |
| `crm_ciselne_rady` | viditelná ID: prefix, rok, šířka, další číslo, počátek |
| `crm_aktivity` | poznámky, telefonáty, schůzky a úkoly (generická pro všechny entity) |
| `crm_vlastni_pole` | definice admin přidaných polí; hodnoty jsou v `extra` daného záznamu |

Na `nabidky` (nabídkovač) přibyly dva sloupce: **`cislo`** (`NAB-26-NNNN`) a
**`obchodni_pripad_id`**. Obojí je nullable schválně — nabídkovač jde pořád otevřít samostatně
jako výpočtový nástroj a staré nabídky případ nemají.

`kategorie` u případu je **seznam**, ne jedna hodnota: případ může být PPA i peak shaving
současně (a právě z toho vznikne kombinovaná nabídka, až se to postaví).

### Řešení potíží
| Projev | Příčina a co s tím |
|---|---|
| OZ nevidí záznam, který založil kolega | Správné chování. Přidej ho jako spoluvlastníka, nebo mu dej právo `crm_vse`. |
| Nový případ dostal číslo, které už v Raynetu je | Řada je posazená moc nízko. V nastavení posuň **další číslo** nad Raynetí maximum. |
| „Doplnit z ARESu" hlásí chybu | ARES je veřejná služba a občas neodpovídá; nebo IČO nemá platný kontrolní součet. Vyplň ručně, ukládání to neblokuje. |
| Případ nejde přesunout do prohry | Chybí důvod prohry — dialog ho vyžaduje. |
| Stav nejde smazat | Jsou v něm případy, nebo je to poslední stav. |
| Po smazání vlastního pole zmizely hodnoty | Nezmizely, jen se neukazují. Založ pole znovu se stejným názvem. |
| Vlastní pole nejde uložit s textem v čísle | Číselné pole přijímá jen čísla (i s mezerami a čárkou). Změň typ pole, nebo hodnotu. |
| V kanbanu chybí sloupec, ale případy někde jsou | Stav byl smazán z nastavení; případy v neexistujícím stavu padají do prvního sloupce, aby se neztratily. |

### Poznámky a úskalí
- **Dvě pravdy o zákazníkovi.** Dokud běží Raynet i appka, vedou se klienti na dvou místech
  a budou se rozjíždět. Jednosměrný sync z Raynetu (`raynet_id` je připravené) zatím není.
- **Objednávky a projekty** ještě nejsou hotové — na kartě případu jsou vyznačené jako
  „připravuje se". Stavy a číselné řady pro ně už ale existují.
- **Sekce Nabídky** jako samostatný globální seznam se připravuje; nabídky jsou dnes vidět
  na kartě případu a v nabídkovači.
