# Zákazníci a Obchodní případy (CRM)

> **Sekce v nabídce:** `zakaznici`, `obchodni_pripady`, `nabidky`, `objednavky`, `projekty` · **Adresy (routy):** `/zakaznici/lead`, `/zakaznici/klient`, `/zakaznici/detail/:id`, `/pripady`, `/pripady/detail/:id`, `/nabidky` · **Kdo smí otevřít:** právo `zakaznici` resp. `obchodni_pripady`; sekce Nabídky jede pod právem `nabidkovac` (bez práva se sekce v nabídce vůbec nezobrazí; admin vždy)
> **Kód:** frontend `frontend/src/pages/Zakaznici.jsx`, `ZakaznikDetail.jsx`, `ObchodniPripady.jsx`, `ObchodniPripadDetail.jsx`, `Nabidky.jsx`, backend `backend/app/crm/`

Evidence obchodu: **zákazník → obchodní případ → nabídka** (a dál objednávka a projekt, které
se připravují). Cílem je, aby obchodní zástupce nemusel chodit do samotného nabídkovače —
všechno podstatné se zakládá a ukládá u zákazníka a u případu, a výpočet nabídky se z případu
jen zavolá.

> 📸 SCREENSHOT: kanban obchodních případů se sloupci fází a dlaždicemi zakázek
> 📸 SCREENSHOT: karta případu, záložka Nabídky – podklady a pracovní stůl výpočtu na jednom místě

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

**Kategorie případu** říká, čím zakázka je — a podle ní appka pozná, **do kterého výpočtu**
poslat nabídku. Výchozí jsou *PPA*, *Prodej* a *Peak shaving*, ale seznam si vedení
spravuje samo (viz níž), takže se může objevit i „Servis" nebo „Dotace". Kategorií může mít
případ **víc současně** — PPA i peak shaving je běžná kombinace a právě z ní vzniká
kombinovaná nabídka.

> Kategorie, ke které žádný výpočet neexistuje (třeba servis), je v pořádku. Na záložce
> Nabídky se u ní jen nenabídne tlačítko „+ …", protože nabídkovač pro ni nic neumí spočítat.

### Filtry, řazení a vlastní pohledy
Každý seznam (Zákazníci, Případy, Nabídky, Objednávky, Projekty) má tři vrstvy filtrování a
všechny se dají kombinovat.

**1. Řazení kliknutím na hlavičku.** Výchozí je **podle čísla záznamu** (OP / NAB / OBJ / PRO),
nejnovější první; u Zákazníků podle názvu, protože číslo nemají. Klik přepne směr,
**shift + klik přidá další úroveň** — dá se tak řadit „podle stavu, a v rámci stavu podle čísla".
Aktuální řazení je vypsané nad tabulkou včetně pořadí úrovní.

> Čísla se řadí **přirozeně**, ne jako text: `OP-26-0099` je před `OP-26-0100` a
> `PRO-26-0301` před `PRO-26-0301-2`.

**2. Filtry sloupců.** Tlačítko **⌕ Filtry sloupců** rozbalí nad tabulkou řádek s filtrem
u každého sloupce. Tvar filtru se řídí typem: text (obsahuje), číslo a datum (od–do),
stav a typ (rozbalovací nabídka jen s hodnotami, které se v datech skutečně vyskytují),
ano/ne. Počet aktivních filtrů je vidět na tlačítku a jde je zrušit jedním kliknutím.

**3. Vlastní filtry (uložené pohledy).** Nad seznamem je lišta **Filtry** s tlačítkem
**+ Vlastní filtr**. Filtr je několik **podmínek**, které musí platit všechny, a
**víceúrovňové řazení**. Například *„kategorie obsahuje PPA, hodnota ≥ 1 000 000, stav není
Prohráno"* řazené podle stavu a pak podle čísla.

Uložený filtr má tři přepínače:

| Volba | Co dělá |
|---|---|
| **Nasdílet ostatním** | filtr uvidí i kolegové (jako pilulku se tvým jménem) |
| **Použít po otevření sekce** | tenhle filtr se aktivuje sám; výchozí může být jen jeden |
| *(bez volby)* | filtr je jen tvůj |

Cizí nasdílený filtr **můžeš použít, ale ne přepsat** — kdo si ho chce upravit, dá
*Uložit jako nový* a vznikne mu vlastní kopie. Jinak by si lidé měnili pohledy pod rukama.

> **Filtr platí zároveň pro tabulku i kanban.** Když si vyfiltrujete „jen moje případy nad
> milion", uvidíte je v tabulce i jako dlaždice v kanbanu, a součty i počty v hlavičkách
> sloupců se přepočítají. Kdyby si každé zobrazení drželo vlastní filtr, člověk by v každém
> viděl něco jiného a nechápal proč.

Co filtr skryl, je vidět u počtu nad tabulkou (`5 z 210`).

**Datumy: používej „je v období", ne od–do.** U každého datumového sloupce je operátor
**je v období** s hotovými volbami: *dnes, včera, zítra, tento týden, příštích 7 dní,
posledních 30 dní, tento měsíc, minulý měsíc, tento rok, v minulosti, v budoucnosti* a další.

Proč na tom záleží: filtr *„od 1. 7. do 31. 7."* je za měsíc **lež** — ukazuje starý červenec
a nic tě na to neupozorní. Relativní období se přepočítává k dnešnímu dni, takže uložený
pohled *„uzavření tento měsíc"* platí pořád. V editoru je vedle výběru vidět, co období dnes
znamená (`1. 7. – 31. 7. 2026`), ať je jasné, co se filtruje.

Absolutní od–do zůstává pro případy, kdy opravdu chceš pevné datum (třeba kvůli auditu).

### Export do Excelu
V liště nad každou tabulkou je **↓ Export CSV (n)**. Číslo v závorce říká, kolik řádků se
stáhne — je to **přesně to, co máš na obrazovce**: se zapnutým filtrem, ve zvoleném řazení
a s vybranými sloupci. Soubor se jmenuje podle sekce a data (`obchodni-pripady-2026-07-30.csv`).

Otevři ho v Excelu normálním dvojklikem: je připravený pro české nastavení, takže diakritika
sedí, sloupce se rozdělí samy a s částkami i procenty jde hned počítat. Datumy jsou ve formátu
`30.07.2026`.

> Export je **jen ke čtení dat** — zpátky do appky se soubor nahrát nedá. Změny se dělají
> v appce, aby nevznikly dvě verze pravdy.

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

### Nabídky: celý výpočet na kartě případu
Všechno se děje na záložce **Nabídky** u obchodního případu — **do nabídkovače chodit nemusíš**.

1. **Založení** je jedno kliknutí: tlačítka *+ PPA*, *+ Peak shaving*, *+ Prodej* vpravo nahoře.
   Kategorie případu jsou zvýrazněné jako obvyklá volba, ale založit jde kterýkoli typ.
   Číslo (`NAB-26-NNNN`) přidělí appka a **údaje zákazníka** — jméno, adresu i GPS — si nabídka
   vezme z karty klienta. Nic se neopisuje.
2. **Podklady** nahraješ hned pod tím: faktura za elektřinu (PDF), diagram spotřeby (XLS/CSV).
   Dokud není nic nahráno, je ta část rozbalená, protože bez podkladů se výpočet nerozjede.
3. **Výpočet** je rovnou tam — stejný pracovní stůl jako v nabídkovači (vstupy vlevo,
   spočítané hodnoty vpravo). Výsledky se vrací na místě, na kartě případu.

Má-li případ víc nabídek, přepínají se pilulkami s čísly vlevo nahoře. Když případ nabídku
už má, otevře se sama.

Dvě tlačítka vedou dál, protože jsou to jiné úlohy:

- **Nabídka pro zákazníka (PDF)** — sestavení dokumentu (papír, náhled, tisk).
- **Otevřít v nabídkovači** — tatáž nabídka na samostatné obrazovce; hodí se na testování
  nebo když chceš mít víc místa.

### Sekce Nabídky: co je odesláno a co zákazník přijal
Vedle Zákazníků a Obchodních případů je sekce **Nabídky** — přehled napříč všemi případy.
Odpovídá na jiné otázky než karta případu: *co jsme odeslali, co visí bez reakce, co zákazník
přijal.* Nepočítá se tu; klik na nabídku vede na její obchodní případ, kde je pracovní stůl.

Nabídka má **dva stavy na dvou různých osách** a schválně se nemíchají:

| Osa | Kde se mění | Hodnoty |
|---|---|---|
| **Obchodní stav** | kanban sekce Nabídky | koncept → ke kontrole → odeslána → přijata / zamítnuta |
| **Stav zpracování** | výpočet na kartě případu | koncept, data nahrána, zkontrolováno, spočítáno, hotovo |

Nabídka totiž může být dávno odeslaná a přitom mít rozpracovaný výpočet — a naopak. V tabulce
je proto vidět obojí, včetně sloupce, jestli je nabídka vůbec **spočítaná** (nespočítanou nemá
smysl posílat).

Kanban se přetahuje stejně jako u případů a každý přesun se zapisuje do historie, takže jde
zjistit, jak dlouho nabídka u zákazníka visela. Stavy si vedení upraví tlačítkem
**„⚙ Stavy nabídek"** (právo `crm_nastaveni`).

> **Přijatá nabídka NEPOSOUVÁ obchodní případ na výhru.** Přijatá nabídka ještě není podepsaná
> objednávka; předbíhat rozhodnutí obchodníka by bylo horší než nechat ho případ posunout sám.

### Objednávky: potvrzená zakázka
Sekce **Objednávky** (a záložka *Objednávky a projekty* na kartě případu). Objednávka se
zakládá **z nabídky**, kterou zákazník přijal — převezme z ní cenu, pokud ji umíme určit
(u peak shavingu investici do baterie; u PPA ne, protože tam zákazník neplatí zařízení, ale
dodanou elektřinu).

Cena na objednávce je **snapshot**, ne odkaz do výpočtu: je to to, na čem jste se dohodli.
Kdyby se nabídka pak přepočítala, objednávka se tím nezmění.

Zrušení objednávky si vyžádá **důvod** — stejně jako prohra případu. Objednávku, ze které už
vznikl projekt, **nelze smazat** (projekt by osiřel).

### Projekty: realizace s kroky a návaznostmi
Sekce **Projekty**. Projekt **nelze založit samostatně** — vzniká z objednávky (tlačítko v jejím
detailu) nebo z obchodního případu u zakázek, které objednávkou neprochází. Číslo kopíruje
případ: `PRO-26-0301` k `OP-26-0301`; druhý projekt téhož případu má `-2`.

**Kroky realizace** jsou jádro. Každý krok má trvání ve dnech a může **navazovat** na jiný krok:

- krok bez předchůdce se počítá **od zahájení projektu**,
- krok s předchůdcem **od jeho skutečného dokončení** (dokud předchůdce hotový není, od jeho
  plánovaného termínu),
- když se něco zdrží, **posunou se termíny kroků za tím**. To je celý smysl: termíny nelžou.

Krok, který čeká na nedokončeného předchůdce, je v seznamu utlumený — nemá se do něj pouštět.
Odkliknutí hotového kroku je zaškrtávátko vlevo, protože to je nejčastější akce.

> **Ruční termín má vždy přednost.** Když u kroku nastavíš datum sám („tehdy přijede jeřáb"),
> přepočet ho už nikdy nepřepíše. Vrátit ho do automatického dopočtu jde odkazem *vrátit
> do automatu*.

### Šablony projektových kroků
Tlačítko **📋 Šablony kroků** v sekci Projekty. Šablona je posloupnost kroků s trváním
a návaznostmi — „takhle u nás vypadá FVE realizace". Na projektu se jedním kliknutím rozbalí
do konkrétních úkolů s termíny.

Appka přináší dvě hotové: **FVE – standardní realizace** a **Peak shaving – instalace baterie**
(8 kroků každá). Vedení je může upravit, přidat vlastní, nebo je smazat — projekty, které z nich
už vznikly, zůstanou nedotčené (kroky se do nich zkopírovaly).

Šablonu lze přidat i k rozjetému projektu; kroky se přidají za existující.

### Kombinace opatření: PPA + baterie v jedné nabídce
Když zákazník chce obojí, není potřeba posílat dvě nabídky. Na kartě případu je na záložce
**Nabídky** tlačítko **⇄ Kombinace** (objeví se, jen když případ má nabídku na PPA i na peak
shaving). Vybereš obě, appka je spojí do **nové nabídky typu Kombinace** — a ta má vlastní
dokument pro zákazníka se souhrnem, oběma grafy a společnou tabulkou úspor po letech.

**Nic se nepřepočítává.** Kombinace bere hotové výsledky obou nabídek. Proto obě musí mít
spuštěný výpočet — z prázdné nabídky by vznikla kombinace bez čísel a appka to odmítne.

Co je v souhrnu:

| Údaj | Jak se počítá |
|---|---|
| Vaše investice | jen **cena baterie** — PPA je bez počáteční investice zákazníka |
| Úspora v 1. roce | úspora z elektrárny + úspora z baterie |
| Celková úspora | součet po letech za dobu kontraktu |
| Návratnost | vztažená **pouze k baterii** — vázat ji na úsporu z elektrárny by tvrdilo, že se baterie zaplatí i z toho, co ušetří FVE |

> ⚠️ **Výhrada, kterou je potřeba znát:** oba výpočty běžely nad *původním* profilem spotřeby.
> Fotovoltaika přes den snižuje odběr ze sítě, takže skutečné špičky po její instalaci mohou být
> nižší a baterie může být navržená s rezervou. Úspory se nesčítají dvakrát za totéž (elektrárna
> šetří na ceně energie v Kč/MWh, baterie na rezervované kapacitě v Kč/kW), ale dimenzování
> baterie by přesně vzato mělo vycházet z profilu po odečtení výroby FVE. Tuhle poznámku appka
> zobrazuje i při spojování.

**Aktualizace:** když se zdrojová nabídka přepočítá, kombinace se **nezmění sama**. Spoj ji
znovu (tlačítko nabídne „aktualizovat"). Je to schválně: takhle je dohledatelné, s jakými čísly
nabídka odešla zákazníkovi — každé spojení zůstává v historii.

### Import z Raynetu
> **Rozhodnuto 30. 7. 2026: import se dělat NEBUDE.** Stávající zakázky **dojedou v Raynetu**
> a do appky se zakládají jen **nové**. Funkce v appce zůstává (popis níž platí), ale nikdo ji
> nespouští. Praktický důsledek pro každodenní práci: **nová zakázka = vždycky appka**, do
> Raynetu se už nic nezakládá. Starší zakázky hledej dál v Raynetu.

V sekci **Zákazníci** je pro `crm_nastaveni` tlačítko **⬇ Import z Raynetu**. Natáhne klienty
a obchodní případy — jednosměrně (Raynet → appka) a **idempotentně**: opakované spuštění
existující záznamy aktualizuje, nezdvojí, protože se páruje na Raynetí `id`.

Nejdřív **náhled** (nic se nemění), pak potvrzení. Náhled se nespouští sám: čtení ~450 firem
a ~200 případů stojí API cally a Raynet má denní limit, který se před importem kontroluje.

Co se přenese: název, IČO, adresa, **GPS** (tu potřebuje PPA výpočet!), e-mail, telefon,
poznámka; u případů název, popis, hodnota, pravděpodobnost, důvod prohry a **Raynetí číslo**
(uloží se zvlášť do `raynet_code`, protože na něm stojí párování složek na Disku).

**Co se nepřenese a proč:**

- **kategorie případu** (PPA / prodej / peak shaving) — Raynetí fáze ji neobsahuje a hádat ji
  z názvu by vyrobilo tichý nepořádek. Zůstane prázdná a appka se zeptá u nabídky.
- **Raynetí fáze → náš stav**: zkusí se najít stav se stejným názvem; co se nenajde, padne do
  prvního stavu a **původní fáze se zapíše do popisu**, aby se informace neztratila.

**Vlastníci:** Raynet posílá u vlastníka jen jméno, ne e-mail. Páruje se proto podle jména bez
diakritiky, a když to nevyjde, podle **příjmení** — ale jen když je v appce jednoznačné (dvakrát
stejné příjmení = radši nikdo než špatně přiřazená zakázka). Koho appka nezná, jeho záznamy
zůstanou **bez vlastníka**, tedy viditelné jen s `crm_vse`. Náhled ta jména vypíše; když jim
založíš účet a import spustíš znovu, vlastníci se doplní.

### Staré nabídky bez případu
Nabídky vytvořené v nabídkovači před CRM nemají zákazníka ani případ a v přehledu visí jako
`#21`. V sekci Nabídky je pro ně tlačítko **🔗 Dohledat staré** (právo `crm_nastaveni`): podle
jména zákazníka z nabídky založí klienta a obchodní případ a doplní číslo.

Vlastníkem se stane **autor nabídky**, ne ten, kdo dohledání spustil — jinak by všechny staré
zakázky spadly na jednoho člověka. Nabídky **bez jména zákazníka** se přeskočí a vypíšou; nemají
kam patřit a prázdní klienti by jen zanesli evidenci.

Nejdřív se vždy ukáže **náhled** (nic se nemění) a teprve druhé potvrzení migraci provede —
je nevratná.

### Aktivity a úkoly
Na kartě zákazníka i případu je log práce: **poznámka, telefonát, e-mail, schůzka, úkol**.
Aktivita s **termínem** se stává úkolem — nedokončené jsou nahoře a po termínu se zvýrazní
červeně. Tohle je místo, kam patří „volal jsem, chce to probrat po dovolené" — jinak to zůstane
jen v hlavě jednoho člověka.

**Nemusíš je hledat po záznamech.** Na **Rozcestníku** (úvodní stránka) je karta
**Moje úkoly v CRM** se všemi tvými nehotovými úkoly napříč zákazníky, případy, nabídkami,
objednávkami i projekty — nejbližší termín první. U každého je vidět, **u čeho visí**, a
kliknutím na řádek se tam dostaneš. Nahoře je k tomu dlaždice s počtem: svítí červeně, když
je něco po termínu, oranžově u dnešních termínů.

> Jsou to vždycky **jen tvoje** úkoly. I vedení, které jinak vidí všechny záznamy, tu má
> svoje — jinak by tahle karta byla seznam práce celé firmy a nikdo by v ní nic nenašel.

#### Uzavření aktivity: co z ní vyšlo
Aktivita s termínem má tři stavy a **appka se při uzavírání zeptá na výsledek**:

| Stav | Kdy ho použít |
|---|---|
| **Naplánováno** | čeká to na tebe, počítá se do „moje úkoly" |
| **Realizováno** | proběhlo — do výsledku napiš, jak to šlo |
| **Nekonalo se** | schůzku zákazník zrušil, nedovolal jsi se — do výsledku napiš proč |

Proč to není jedno zaškrtávátko „hotovo": schůzka, která proběhla, a schůzka, kterou zákazník
zrušil, jsou dvě různé věci. Kdyby obojí spadlo pod „hotovo", nešlo by spočítat, kolik jednání
se opravdu odehrálo. A výsledek („volal jsem, chce to probrat po dovolené") je ta hodnotná
informace — bez ní zůstane v CRM jen odškrtnutý řádek.

Špatně uzavřená aktivita se dá vrátit tlačítkem **Vrátit** mezi naplánované.

### Nastavení: tvoje osobní volby
V nabídce u svého jména vpravo nahoře je **Nastavení**. Je to jedno místo pro všechno, co si
každý nastavuje sám:

- **režim zobrazení** (světlý / tmavý), **velikost textu**, **režim pro barvoslepé**,
- **barvy druhů aktivit v kalendáři** — podle barvy poznáš na první pohled, co tě čeká.

Všechno je uložené u tvého účtu, ne v prohlížeči, takže to platí i na jiném počítači. A je to
**jen tvoje** — kolegům se kalendář nepřebarví.

> Nastavení firmy (stavy pipeline, kategorie, práva, uživatelé) je jinde — v **Admin
> nastavení**. Sem patří jen to, co je osobní.

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

### Kategorie obchodního případu
Ve stejném okně jako stavy pipeline (**Nastavení pipeline, kategorií a číslování**, právo
`crm_nastaveni`) je tabulka kategorií. Přidání „Servisu" nebo „Dotace" je tedy práce pro
vedení, ne pro programátora.

U každé kategorie se nastavuje:

| Pole | Co znamená |
|---|---|
| **Název** | co vidí lidé; dá se kdykoli přejmenovat |
| **Výpočet nabídky** | do kterého výpočtu kategorie míří (PPA / Prodej / Peak shaving), nebo **bez výpočtu** |
| **Nabízet** | vypnutá kategorie se nenabízí u nových případů, ale u těch, které ji mají, se dál zobrazuje |
| **Pořadí** | v jakém sledu se kategorie nabízejí |

**Bez výpočtu** je plnohodnotná volba: „Servis" je pořád obchodní případ, ale nabídkovač pro
něj nic neumí — tak se u něj tlačítko „+ Servis" na kartě případu nenabídne. Kdyby se
nabídlo, vedlo by do prázdna.

Dvě věci, které appka nedovolí, a proč:

- **Strojový klíč se nemění** (je vypsaný pod názvem). Nesou ho uložené případy a typ
  nabídky, takže jeho změna by je odpojila. Přejmenovat název je proto bezpečné, klíč zůstává.
- **Kategorii, kterou už případy mají, nelze smazat.** Appka řekne kolik jich je a doporučí ji
  **vypnout**. Smazání by z historických případů udělalo záznamy s klíčem, který nikdo
  nepřeloží na název.

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

### Nabídky na kartě případu: jak to funguje uvnitř
Výpočtové panely se **nepřekreslují znovu** — `PripadNabidky.jsx` vkládá tytéž komponenty,
které používá nabídkovač (`PpaPanel`, `PeakShavingPanel`, `ProdejPanel`, `DokumentUpload`).
Kdyby existovaly dva pracovní stoly, po první úpravě výpočtu by se rozešly.

Panely potřebují z nabídky jen `id`, `dokumenty` a `reseni`, takže si karta případu při výběru
nabídky dotáhne její detail (`GET /nabidkovac/nabidky/{id}`) a po každém nahrání podkladu ho
načte znovu. Seznam nabídek případu chodí v jeho detailu (`nabidky`), obsah nabídek si CRM
nekopíruje — zdroj pravdy o výpočtech zůstává nabídkovač.

### Projekt vs. Přehled projektů (dvojí význam slova)
V appce jsou **dva různé „projekty"** a je potřeba je nemíchat:

| Co | Tabulka | Adresa | Odkud data |
|---|---|---|---|
| **Projekty** (CRM realizace) | `crm_projekty` | `/projekty` | zakládá se z objednávky/případu |
| **Přehled projektů** (matice úkolů) | `projekty` | `/prehled-projektu` | synchronizace z **Freela** |

CRM projekt má na Freelo projekt volitelný odkaz (`freelo_projekt_id`) — appka má Freelo časem
nahradit, do té doby běží obojí a páruje se přes číslo OP mostem v `matice/disk_parovani.py`.

> ⚠️ Přehled projektů se přesunul z `/projekty` na `/prehled-projektu`, protože adresu
> `/projekty` převzala CRM realizace. Staré záložky v prohlížeči je potřeba přepsat.

### Kroky a termíny: jak to funguje uvnitř
`app/crm/projekty_kroky.py`. Termín kroku = start + `delka_dni`, kde start je zahájení projektu
(krok bez předchůdce) nebo dokončení/termín předchůdce. Přepočet běží po každé změně kroku,
po dokončení kroku i po posunu zahájení projektu, a **respektuje `termin_rucne`**.

Návaznost v **šabloně** se drží jako `zavisi_na_poradi` (pořadí předchůdce), v **projektu** jako
`zavisi_na_id` (skutečný cizí klíč). Důvod: šablona se do projektu kopíruje a tam vznikají nové
řádky s novými id — odkaz přes id by po kopii nesouhlasil. Krok nesmí navazovat sám na sebe
(odmítne se), takže termín se nemůže zacyklit.

### Filtry: jak to funguje uvnitř
**Definice** filtrů drží backend (`crm_ulozene_filtry`), ale **samo filtrování a řazení běží
na klientu** (`frontend/src/crmFiltry.js`). Důvody: seznamy vracejí stovky řádků, takže je
to okamžité bez round-tripu; stejná logika obslouží tabulku i kanban; a nemusí se psát
generátor SQL z uživatelských podmínek, což je klasický zdroj chyb i děr. Až budou
desetitisíce záznamů, filtr se přesune na server — formát podmínek je na to připravený.

Sloupce jsou **deklarativní** (`sloupceEntity`), takže hlavička tabulky, filtr sloupce
i porovnávací funkce vycházejí z jednoho zdroje. Vlastní (admin definovaná) pole označená
*v seznamu* se do filtrů přidávají automaticky jako textové sloupce.

Podmínky se vyhodnocují jako **AND** (postupné zúžení). Filtry sloupců zapisují do stejného
seznamu podmínek jako uložený filtr (mají jen příznak `zdroj: "sloupec"`), takže cokoli
naklikaného ve sloupcích jde uložit jako vlastní filtr, aniž by se to zadávalo znovu.

Prázdné hodnoty jdou při řazení **vždy na konec**, ať se nemíchají mezi vyplněné.

### Pipeline nabídek: jak to funguje uvnitř
`app/crm/nabidky_pipeline.py`. Obchodní stav je sloupec `nabidky.stav_obchodni` (klíč do
`crm_stavy`, entita `nab`), **nullable** — starším nabídkám se při čtení dopočítá první stav
pipeline, ale nezapisuje se; zápis proběhne teprve, když s nabídkou někdo v kanbanu pohne.
Čtení nemá měnit data.

**Viditelnost** nabídka nemá vlastní: řídí se právy svého obchodního případu. Nabídku **bez
případu** (vznikla přímo v nabídkovači) vidí jen její autor a kdokoli s `crm_vse` — jinak by
„nikomu nepatřící" nabídky byly vidět všem.

Kanban sekce Nabídky používá **tutéž komponentu** jako kanban případů; liší se jen render
dlaždice (`dlazdice` prop). Dva kanbany by se rozešly.

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
| *(nabídky)* | zůstávají v tabulce `nabidky` nabídkovače – CRM jim přidává jen `stav_obchodni` a pohled |
| `crm_vlastni_pole` | definice admin přidaných polí; hodnoty jsou v `extra` daného záznamu |
| `crm_objednavky` | potvrzené zakázky; `cena_kc` je snapshot, `nabidka_id` informativní |
| `crm_projekty` | realizace; `freelo_projekt_id` je most na Freelo projekt (koexistence) |
| `crm_projekt_kroky` | kroky projektu; `zavisi_na_id` je skutečná návaznost mezi kroky |
| `crm_projekt_sablony`, `crm_projekt_sablona_kroky` | šablony kroků; návaznost drží **pořadí** předchůdce, ne id |
| `crm_ulozene_filtry` | uživatelské filtry: podmínky a řazení jako JSONB, příznaky sdílený/výchozí |

Na `nabidky` (nabídkovač) přibyly dva sloupce: **`cislo`** (`NAB-26-NNNN`) a
**`obchodni_pripad_id`**. Obojí je nullable schválně — nabídkovač jde pořád otevřít samostatně
jako výpočtový nástroj a staré nabídky případ nemají.

`kategorie` u případu je **seznam**, ne jedna hodnota: případ může být PPA i peak shaving
současně (a právě z toho vzniká kombinovaná nabídka).

Samotné kategorie jsou od 30. 7. 2026 **data v tabulce `crm_kategorie`**, ne konstanta v kódu
(stejný princip jako stavy pipeline). V případu se drží jen jejich `klic`; převod na název
i na výpočet nabídky (`typ_nabidky`) řeší ta tabulka.

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
| Nabídka je v kanbanu Nabídek, ale nemá případ | Vznikla přímo v nabídkovači. Vidí ji jen autor; navázat ji na případ jde tím, že se nová založí z případu. |
| Nabídka je „přijata", ale případ pořád není vyhraný | Správné chování — případ posouvá obchodník sám, přijatá nabídka ještě není podepsaná objednávka. |
| Projekt nejde založit („nelze samostatně") | Musí vzniknout z objednávky nebo z případu. Otevři případ → záložka Objednávky a projekty. |
| Termín kroku se nepřepočítal | Je zadaný ručně (`ruční` u termínu). Vrať ho do automatu odkazem u pole. |
| Objednávku nelze smazat | Vznikl z ní projekt. Smaž nejdřív projekt. |
| Přehled projektů zmizel z `/projekty` | Je na `/prehled-projektu` — adresu převzala CRM realizace. |

### Poznámky a úskalí
- **Dvě pravdy o zákazníkovi.** Dokud běží Raynet i appka, vedou se klienti na dvou místech
  a budou se rozjíždět. Jednosměrný sync z Raynetu (`raynet_id` je připravené) zatím není.
- **Objednávky a projekty** ještě nejsou hotové — na kartě případu jsou vyznačené jako
  „připravuje se". Stavy a číselné řady pro ně už ale existují.
- **Sekce Nabídky** jako samostatný globální seznam se připravuje; nabídky jsou dnes vidět
  na kartě případu a v nabídkovači.
