# Zákazníci a Obchodní případy (CRM)

> **Sekce v nabídce:** `zakaznici`, `kontakty`, `obchodni_pripady`, `nabidky`, `objednavky`, `projekty` · **Adresy (routy):** `/zakaznici/lead`, `/zakaznici/klient`, `/zakaznici/detail/:id`, `/kontakty`, `/kontakty/detail/:id`, `/pripady`, `/pripady/detail/:id`, `/nabidky` · **Kdo smí otevřít:** právo `zakaznici` resp. `obchodni_pripady`; sekce Nabídky jede pod právem `nabidkovac` (bez práva se sekce v nabídce vůbec nezobrazí; admin vždy)
> **Kód:** frontend `frontend/src/pages/Zakaznici.jsx`, `ZakaznikDetail.jsx`, `KontaktniOsoby.jsx`, `KontaktDetail.jsx`, `ObchodniPripady.jsx`, `ObchodniPripadDetail.jsx`, `Nabidky.jsx`, backend `backend/app/crm/`; automatické ukládání vstupů `backend/app/crm/pole_zaznamu.py`, `routes_pole.py`, `razitko.py` + `frontend/src/hooks/useZaznamAutosave.js`

Evidence obchodu: **zákazník → obchodní případ → nabídka** (a dál objednávka a projekt, které
se připravují). Cílem je, aby obchodní zástupce nemusel chodit do samotného nabídkovače —
všechno podstatné se zakládá a ukládá u zákazníka a u případu, a výpočet nabídky se z případu
jen zavolá.

> 📸 SCREENSHOT: kanban obchodních případů se sloupci fází a dlaždicemi zakázek
> 📸 SCREENSHOT: karta případu, záložka Nabídky – podklady a pracovní stůl výpočtu na jednom místě

---

## 🧑 Pro uživatele

### ⚠️ Jedno pravidlo nade všemi: nová věc = vždycky appka

**Cokoli nového — firma, obchodní případ, nabídka — se zakládá tady v appce. Do Raynetu se
už nezakládá nic.**

Proč to takhle je: stávající zakázky se do appky **nepřenášejí** (rozhodnuto 30. 7. 2026,
import se dělat nebude). Dojedou tam, kde vznikly, tedy v Raynetu. Appka tím pádem zná jen
to, co v ní vzniklo — a to je správně, dokud platí tohle pravidlo. Kdyby někdo založil novou
zakázku v Raynetu „ze zvyku", vznikla by třetí pravda a nikdo by nevěděl, kde se co eviduje.

Co z toho plyne pro každodenní práci:

- **Starší zakázky hledej v Raynetu** — v seznamech Zákazníci, Obchodní případy i u grafů je
  na to odkaz „Otevřít Raynet".
- **Čísla a součty v appce nejsou celý byznys firmy.** Pipeline, forecast i KPI nad seznamy
  počítají jen z toho, co je tady. Rostou tak, jak se sem zakládají nové zakázky — takže
  nízké číslo na začátku není propad obchodu.
- **Raynet se časem vypne sám**, až v něm dojedou poslední staré případy. Není potřeba nic
  migrovat ani dohánět.

### Úpravy se ukládají samy (od 6. 8. 2026)
V CRM **se neukládá tlačítkem**. Co napíšeš do pole na kartě, se uloží samo — u textu asi půl
sekundy po tom, co dopíšeš, u výběru, data a zaškrtávátka hned. Nahoře u nadpisu je vidět stav
(*Ukládám… / Uloženo v 14:32 / Neuloženo*). Tlačítko **Hotovo** už neukládá: jen dožene
posledních pár znaků, které se nestihly odeslat, a zavře okno.

**Podstatná změna není zmizelé tlačítko, ale to, že se ukládá jen pole, které jsi změnil.**
Dřív se posílala celá karta naráz, včetně polí, do kterých jsi ani neklikl. Když nad jednou
firmou seděli dva lidé, ten, kdo uložil později, přepsal kolegovi i telefon a poznámku,
kterých se vůbec nedotkl — a nikdo se to nedozvěděl. U **Doplňujících údajů** (vlastní pole)
to bylo ještě horší: pole, které tvůj formulář neznal, se uložením rovnou **smazalo**.

> ⚠️ **Prázdné pole je platná hodnota** (= vymazat). A protože se ukládá průběžně, jsou
> v databázi i rozepsané a nedokončené hodnoty — to je normální stav, ne chyba. Kdo se na
> kartu podívá ve chvíli, kdy do ní někdo píše, uvidí ji rozepsanou.

> ⚠️ **Povinná vlastní pole se při psaní nevynucují.** Kdyby ano, appka by u rozdělaného
> záznamu odmítla uložit cokoli, dokud nevyplníš všechno povinné — tedy by se neuložilo nic
> a průběžné ukládání by nefungovalo vůbec. Povinnost se hlídá tam, kde na ní záleží:
> **při přesunu do dalšího stavu**.

#### Co se ukládá samo a co zůstává na tlačítku
| Obrazovka | Co se ukládá samo |
|---|---|
| Karta zákazníka → **Upravit zákazníka** | název, IČO, DIČ, adresa, GPS, web, telefon, e-mail, zdroj, poznámka + Doplňující údaje |
| Karta kontaktní osoby (`/kontakty/detail/:id`) | jméno, funkce, telefon, e-mail, poznámka |
| Karta obchodního případu → **Upravit** | název, popis, hodnota, pravděpodobnost, předpokládané uzavření + Doplňující údaje |
| Objednávka (okno detailu) | **jen blok základních údajů**: název, cena, datum podpisu, datum dodání, popis + Doplňující údaje |
| Detail projektu | **termín zahájení** a **kroky realizace** (název, délka, termín, stav, osoba) |
| Detail nabídky → **Údaje zákazníka** | název zákazníka, adresa, GPS + Doplňující údaje |

**Co zůstává na vědomém potvrzení, a proč:** každá z těchhle věcí něco spustí, přepočítá nebo
založí další záznam. Uprostřed psaní by to zabralo na nedopsané hodnotě.

- **Stav** (přetažení v kanbanu, rozbalovátko) — spouští automatizace a vynucuje povinná pole.
- **Vlastník a spoluvlastníci** — mění, kdo záznam vůbec uvidí.
- **Kategorie případu** a **důvod prohry / zrušení** — kategorie určuje, do kterého výpočtu
  nabídka míří; důvod je podmínka uzavření.
- **Rozpis položek** a **fakturace** — mění cenu a rozepisují splátky.
- **E-maily**, **generování PDF/XLSX**, **výpočty nabídkovače** („Spočítat“) — odchází ven
  nebo vzniká nová verze.
- **Nastavení a práva**, **mazání**, **hromadné akce**.

> Kde tlačítko zůstalo, tam se před jeho zmáčknutím ještě dožene rozepsané pole a **znovu se
> načtou čerstvé údaje** — jinak by staré uložení vrátilo do databáze text, který mezitím
> někdo přepsal.

#### Kdo tu je se mnou
V hlavičce karty jsou kolečka s iniciálami lidí, kteří mají **ten samý záznam** otevřený.
Popisek u kolečka řekne i to, na kterém poli kolega právě stojí (*„Jméno — edituje:
Hodnota (Kč)“*). Je to schválně vidět dřív, než začneš psát — dohodnout se je vždycky lepší
než řešit kolizi potom.

Sebe mezi kolečky nenajdeš (víš, že tam jsi) a kolečko zmizí samo do půl minuty po tom, co
člověk stránku zavře nebo si přepne na jinou záložku. **Změny od ostatních se dotahují samy**,
do několika sekund a bez obnovování stránky. Pole, které máš právě rozepsané, ti aktualizace
nikdy nepřepíše.

#### Když do stejného pole zapsal někdo jiný
Appka **nic nepřepíše** a zeptá se: ukáže, kdo a na co pole změnil, co píšeš ty, a nabídne
**Přepsat mojí hodnotou** / **Nechat jejich**. Dokud nerozhodneš, hodnota není uložená —
u nabídky proto nejde zavřít blok údajů s nerozhodnutou kolizí, zavřením by se text zahodil.

Hlídá se to **porovnáním hodnoty** toho jednoho pole, ne „kdo uložil naposledy“. Takže když
kolega ve stejné chvíli mění telefon a ty poznámku, žádná hláška nepřijde — vaše změny si
nevadí.

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

### Kontaktní osoby (číselník)

> **Sekce v nabídce:** `Kontaktní osoby` (v Obchodu hned pod Zákazníky) · **Adresa:** `/kontakty`
> · **Kdo smí otevřít:** kdo má právo `zakaznici` · **Kód:** `frontend/src/pages/KontaktniOsoby.jsx`,
> `frontend/src/pages/KontaktDetail.jsx`, backend `backend/app/crm/routes.py`.

Seznam **všech kontaktních osob napříč firmami** — leadů i klientů. Je to druhý pohled na tatáž
data, která jsou na kartě zákazníka: **osoba se zakládá u své firmy**, tady se prochází, hledá,
filtruje a exportuje. Druhá tabulka lidí by znamenala, že se opravený telefon objeví jen na jednom
místě.

Umí to, co ostatní seznamy CRM: **hledání** (jméno, firma, funkce, telefon, e-mail), **filtry**,
**řazení**, **skrývání a přesouvání sloupců**, uložené pohledy a **export**.

| Sloupec | Co znamená |
|---|---|
| Jméno | klik na řádek otevře kartu osoby |
| Firma | proklik přímo na kartu zákazníka |
| Funkce, Telefon, E-mail | údaje osoby |
| Hlavní kontakt | koho appka u té firmy nabídne první |
| Typ firmy | Lead / Klient |
| Město, Vlastník firmy | podle firmy, ke které osoba patří |
| **Poslední e-mail**, **E-mailů** | reálná komunikace z pošty navázané na tu osobu, ne datum založení |

Nad tabulkou jsou **ukazatele**: kolik osob, u kolika firem, kolik osob **bez e-mailu** (těm nejde
napsat) a kolik **firem bez hlavního kontaktu** (tam appka nenapoví, komu volat první).

**Viditelnost se dědí z firmy:** kdo nevidí zákazníka, nevidí ani jeho lidi. Kdo nemá `crm_vse`,
má v číselníku jen osoby u svých firem.

#### Karta kontaktní osoby

Otevře se klikem na řádek. Je na ní:

- **Údaje osoby** — jméno, funkce, telefon a e-mail s proklikem na volání a psaní, poznámka.
  Tlačítkem **Upravit** se mění přímo tady a **ukládá se to samo, pole po poli** (viz
  „Úpravy se ukládají samy“ výš). „Hotovo“ jen zavře režim úprav.
  Příznak **hlavního kontaktu** zůstává na vědomé akci: přehazuje se i ostatním osobám téže
  firmy, takže se nesmí spustit uprostřed psaní.
- **Firma** — název s proklikem, město, telefon a e-mail firmy.
- **Obchodní případy firmy** — kontext „o čem s ním je řeč", s proklikem na případ.
- **E-mailová komunikace** — zprávy navázané právě na tuhle osobu. Napojuje se automaticky podle
  adresy, takže u osoby bez e-mailu zůstane prázdná.

> **Aktivity a úkoly na kartě osoby schválně nejsou.** V datech visí na firmě nebo na obchodním
> případu, ne na člověku — karta by tedy jen opisovala kartu zákazníka. Aktivity se vedou tam.

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

**2b. Které sloupce vidíš.** Tlačítko **⋮⋮ Sloupce** rozbalí seznam všech sloupců tabulky.
Zaškrtnutím se sloupec skryje nebo vrátí, šipkami **←** a **→** se mění jeho pořadí.
Nastavení se ukládá **k tvému účtu**, takže platí i na jiném počítači, a je **jen tvoje** —
kolegům se tabulka nepřerovná. Tlačítkem *Vrátit výchozí* se to smaže.

> Skrytý sloupec se dá **pořád filtrovat**. Ve filtru se nabízejí všechny sloupce, i ty,
> které v tabulce vidět nejsou — jinak by skrytí sloupce potichu zrušilo i možnost hledat
> podle něj.

**2c. Kolik řádků naráz.** Pod tabulkou je volba **Řádků na stránku** (25 / 50 / 100 / vše)
a šipky mezi stránkami. Stránkuje se **až po filtru**, takže filtr vždycky prohledá celý
seznam, ne jen tu stránku, na kterou zrovna koukáš. Na rozdíl od sloupců se tahle volba
pamatuje **v prohlížeči**, ne v profilu: na notebooku chce člověk jiný počet řádků než
na velkém monitoru.

**3. Vlastní filtry (uložené pohledy).** Nad seznamem je lišta **Filtry** s tlačítkem
**+ Vlastní filtr**. Filtr je několik **podmínek** a **víceúrovňové řazení**. Například
*„kategorie obsahuje PPA, hodnota ≥ 1 000 000, stav není Prohráno"* řazené podle stavu
a pak podle čísla.

**„a" nebo „nebo".** Mezi podmínkami je přepínač:

- **a** — musí platit obě (výchozí),
- **nebo** — stačí jedna z nich.

Sousední podmínky spojené přes **nebo** tvoří jeden blok. Platí, že **všechny bloky musí
vyjít, ale uvnitř bloku stačí jedna podmínka**. Tím se dá napsat i *„stav je Nabídka
**nebo** Vyjednávání, **a zároveň** hodnota nad milion"* — první dvě podmínky spojíš přes
„nebo", třetí přes „a".

Uložený filtr má tři přepínače:

| Volba | Co dělá |
|---|---|
| **Nasdílet ostatním** | filtr uvidí i kolegové (jako pilulku se tvým jménem) |
| **Použít po otevření sekce** | tenhle filtr se aktivuje sám; výchozí může být jen jeden |
| *(bez volby)* | filtr je jen tvůj |

Čtvrtá volba **Uložit i rozvržení sloupců** přibalí k filtru i to, které sloupce jsou
vidět a v jakém pořadí — kdo sleduje jiná čísla, chce obvykle i jinou tabulku. Bez ní
filtr rozvržení neřeší a zůstane to, co máš nastavené.

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
> **Jen s právem `export`.** Kdo ho nemá, tlačítko vůbec nevidí — seznam si prohlédne,
> ale neodnese si ho v souboru. Přiděluje se v Admin nastavení jako každé jiné právo.
> Zadání Dana (3. 8. 2026): „aby si nikdo, kdo nemá právo, nemohl exportovat třeba
> seznam kontaktů."
>
> Poctivě, ať to za rok nikdo nečte jako záruku, kterou to není: je to **kontrola
> pohodlné cesty, ne datová hráz.** Řádky už jsou v prohlížeči (jinak by tabulka
> nebyla vidět), takže kdo je vidí, může si je opsat nebo vytáhnout z vývojářských
> nástrojů. Serverový endpoint by na tom nic nezměnil — poslal by tytéž řádky, které
> tabulka už dostala, a navíc by se rozešel se slibem „exportuje se přesně to, co je
> vidět". Skutečná hráz na „kdo vidí která data" je právo na sekci a `crm_vse`
> (omezení na vlastní záznamy).

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

> **Ukládá se sám jen blok základních údajů** (název, cena, datum podpisu a dodání, popis
> a Doplňující údaje) — pole po poli, viz „Úpravy se ukládají samy“ výš. **Rozpis položek,
> fakturace, změna stavu a založení projektu** zůstávají na tlačítku: každá z nich něco
> přepočítá nebo založí další záznam, a to se nesmí spustit uprostřed psaní.
>
> Při **zakládání** nové objednávky se průběžně neukládá nic — záznam ještě neexistuje, takže
> není co ukládat. Hodnoty odejdou naráz tlačítkem *Založit objednávku*. Totéž platí u nového
> zákazníka a nového případu: půl vyplněná firma by se jinak objevila v seznamu už při psaní
> prvního slova.

### Rozpis položek: z čeho se skládá cena
Nabídka i objednávka mají **rozpis položek** — panely, měnič, baterie, montáž, doprava,
administrativa. Bez něj nejde doložit, z čeho cena vznikla, ani zakázku vyfakturovat.

Na nabídce je rozpis pod výpočtem (rozbalovací blok **Rozpis položek**), na objednávce
uprostřed karty. Ovládá se stejně:

| Tlačítko | Co udělá |
|---|---|
| **+ Z katalogu** | Otevře výběr z ceníku (hledání podle kódu, filtr kategorie), zaškrtneš víc položek naráz |
| **+ Vlastní položka** | Prázdný řádek pro to, co v ceníku není |
| **↓ Z nabídky** | (jen na objednávce) Dotáhne rozpis z nabídky, ze které objednávka vznikla |
| **↑ ↓ ×** | Přesun řádku nahoru/dolů a smazání |

U každého řádku se zadává **množství, jednotková cena, sleva v %** a **sazba DPH**; sleva se
počítá z jednotkové ceny („panel za 4 500 se slevou 10 %"), ne z celého řádku. Součet
**bez DPH / DPH / s DPH** je pod tabulkou. Kdo má právo na katalog, vidí navíc sloupec
**Nákup/MJ** a celkovou **marži**.

Položka z katalogu si bere **snapshot** názvu a cen. Když se pak v ceníku zdraží panel,
**odeslaná nabídka se nezmění** — to je záměr, ne opomenutí.

**Při vzniku objednávky z nabídky se rozpis překlopí** (zkopíruje). Objednávka pak žije vlastním
životem: přepočítaná nabídka jí obsah nezmění.

**Cena objednávky se počítá ze součtu rozpisu.** Když ji přepíšeš ručně (dohodnutá sleva
„za kulatých 2,4 mil."), appka to respektuje, přestane ji přepisovat a u pole ukáže, o kolik se
od součtu liší — s tlačítkem **Vrátit na součet rozpisu**.

### Fakturace objednávky: kolik je vyfakturováno a zaplaceno
Na kartě objednávky je blok **Fakturace** — řetěz *objednávka → faktura → zaplaceno*.

Splátky se rozepíšou tlačítkem podle předvolby:

| Předvolba | Splátky |
|---|---|
| Jednou fakturou | 100 % |
| Záloha + doplatek | 50 % + 50 % |
| Záloha, průběžná, doplatek | 30 % + 40 % + 30 % |

Vyplníš-li **termín první splátky**, další dostanou termín po měsíci. Částky se dělí tak, aby
součet **seděl na haléř** — u třetin nezůstane chybějící desetikoruna.

U každé faktury se dá měnit název, částka, termín, **variabilní symbol** (přes něj se páruje
POHODA) a stav: *Potřeba vystavit → Vystaveno → Zaplaceno*, případně *Nefakturuje se*
(nepočítá se do součtů). Faktura po termínu, která není zaplacená, se označí červeně —
**i ta, kterou nikdo nevystavil**, protože právě to je problém.

Souhrn pod tabulkou ukazuje **cenu objednávky, vyfakturováno, zaplaceno, zbývá rozepsat**
a *po termínu*. Když se součet faktur rozejde s cenou objednávky (třeba se cena změnila),
appka to napíše a nabídne **Přepočítat podle podílů** — sáhne jen na faktury, které ještě
nejsou vystavené. Vystavená faktura je doklad, ten appka sama nemění.

Objednávky s fakturami se objeví i v **Přehledu financí**, ve vlastní tabulce pod projekty
z Freela. Tam jsou jen ke čtení — upravují se tady, kde platí práva CRM.

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

**Kroky i termín zahájení se ukládají samy** (u kroků je stav ukládání vidět v hlavičce
seznamu). Změna zahájení hned přepočítá termíny všech kroků bez ručního termínu, takže se
karta sama načte znovu — dřív to zajišťovala odpověď na uložení celého projektu.

> ⚠️ **U kroků neplatí ochrana proti přepsání.** Kroky mají vlastní starší endpoint, který
> neumí porovnat, jestli se hodnota od načtení nezměnila — takže u nich pořád platí
> **„poslední zápis vyhrává“**. Když dva lidé ve stejnou chvíli přepisují název jednoho kroku,
> zůstane ten, kdo dopsal později, a appka neřekne nic. U polí na kartách (zákazník, případ,
> objednávka, projekt, nabídka) se to hlídá a kolize se ohlásí.

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

> ⚠️ **Aktivity se průběžně neukládají** — v jejich okně zůstává tlačítko *Uložit*, stejně
> jako v **Kalendáři**. Je to záměr: aktivita může být částí **série** (změna se přenáší na
> ostatní porady) a její uložení rozesílá **notifikace**. Obojí uprostřed psaní znamená deset
> e-mailů a deset přepsaných porad. Zároveň u nich platí **„poslední zápis vyhrává“** — jejich
> endpoint kolizi nekontroluje, takže když text jedné aktivity mění dva lidé současně,
> zůstane ten, kdo uložil později.

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
- **barvy druhů aktivit v kalendáři** — podle barvy poznáš na první pohled, co tě čeká,
- **notifikace** — co chceš vědět a jak (viz níž).

Všechno je uložené u tvého účtu, ne v prohlížeči, takže to platí i na jiném počítači. A je to
**jen tvoje** — kolegům se kalendář nepřebarví.

> Nastavení firmy (stavy pipeline, kategorie, práva, uživatelé) je jinde — v **Admin
> nastavení**. Sem patří jen to, co je osobní.

### Co je vidět na dlaždici v kanbanu
Kromě čísla, zákazníka a hodnoty ukazuje dlaždice tři věci, které se hodí na první pohled:

- **kolečko s iniciálami** vlastníka (barva je pro každého člověka stálá),
- **počet dní ve fázi** vpravo dole — od poslední změny stavu. Nad 30 dní se zvýrazní, takže
  je vidět, co někde leží,
- **propadlý termín** předpokládaného uzavření červeně a tučně.

### Historie změn: kdo co kdy upravil
Na kartě zákazníka, obchodního případu i projektu je dole sbalený panel **Historie změn**.
Po rozbalení ukáže řádek na každou změněnou položku: kdy, co, **z čeho na co** a kdo to
udělal. Původní hodnota je přeškrtnutá, nová tučně.

Co v historii **není** a proč:

- **posuny stavů** — ty mají vlastní, bohatší záznam v timeline zákazníka,
- **technické údaje** (kdy se záznam naposled uložil) — měnily by se pokaždé a nešlo by
  v logu nic najít,
- **cokoli staršího než zapnutí funkce** — sbírá se od 31. 7. 2026, zpětně to dohledat nejde.

> Vlastní pole se zapisují po jednotlivých údajích, takže je vidět „Číslo smlouvy ČEZ:
> A1 → A2", ne nesrozumitelná změna celého bloku.

**Jedno psaní = jeden řádek.** Od chvíle, kdy se ukládá průběžně, přijde při psaní slova
„Technicplast“ na server několik uložení téhož pole za sebou. V historii by z toho bylo
*Tech → Technic → Technicpl → Technicplast* a po jednom odpoledni by v ní nešlo nic najít
(výpis má strop sto řádků). Proto se **opakovaná změna téhož pole týmž člověkem do pěti minut
přilepí k prvnímu řádku**: zůstane „z čeho → na co“, ne cesta po znacích.

Pět minut je záměrný kompromis. Jedna oprava jednoho pole se do okna celá vejde; delší okno by
už slévalo dvě **samostatná rozhodnutí** ve stejném dni — ráno cena 2,5 mil., po obědě
1,9 mil. — a přesně tahle informace je to, kvůli čemu historie existuje.

> Když hodnotu napíšeš a **vrátíš zpátky** na původní (A → B → A), řádek z historie **zmizí**.
> „Změnil z Praha na Praha“ není informace, jen šum. Po uplynutí okna se ale vrácení zpět
> zaloguje jako běžná změna — po pěti minutách už to bylo rozhodnutí, ne přepsání se.

### Mapa
Sekce **Mapa** ukáže zákazníky se souřadnicemi. Zelený špendlík je klient, oranžový lead;
po kliknutí se ukáže, kolik u firmy běží případů a projektů, a odkaz na kartu. Zaškrtávátko
**Jen s otevřeným případem** schová firmy, kde se zrovna nic neděje.

**Odkud jsou souřadnice:** přednostně z **provozovny** (odběrného místa), a když ji firma
nemá vyplněnou, z adresy firmy. U každého bodu je to napsané — fakturační adresa v rejstříku
totiž bývá jinde než místo, kam se opravdu jede.

> Mapa je zatím prázdná: **žádný záznam nemá vyplněné GPS**. Doplní se u odběrného místa na
> kartě zákazníka a body se objeví samy.

### Časová osa projektu (Gantt)
V projektu v záložce **Kroky realizace** je nahoře sbalená **Časová osa**. Každý krok je
pruh podle svého trvání, svislá čára ukazuje dnešek.

- **červené pruhy = kritická cesta** — řetěz kroků, který určuje datum předání. Když se
  zpozdí kterýkoli z nich, posune se konec projektu. Kroky mimo cestu mají rezervu.
- **zelené = hotové**, šrafované = po termínu.

Kroky bez termínu se nekreslí a je pod osou napsáno, kolik jich je. Termín se dopočítá ze
zahájení projektu a délky kroků — když osa nic neukazuje, chybí obvykle **zahájení**.

### Oblíbené a naposledy otevřené
V poli hledání (**Ctrl+K**) se hned po otevření — ještě než začneš psát — ukáže, s čím jsi
naposledy pracoval, a nahoře **★ Oblíbené**. Je to nejrychlejší cesta zpátky k rozdělané
zakázce.

Přišpendlit se dá **hvězdičkou u nadpisu** na kartě zákazníka, obchodního případu nebo
projektu. Klik na plnou hvězdičku ji zase odebere. Naposledy otevřených se pamatuje
posledních patnáct; oblíbené tam zůstávají, dokud je sám neodebereš.

### Notifikace: zvoneček a e-maily
Vpravo nahoře v liště je **zvoneček**. Číslo u něj říká, kolik máš nepřečtených zpráv;
kliknutím se rozbalí seznam a klik na zprávu tě rovnou přenese k záznamu, kterého se týká.
Zprávy zůstávají i po přečtení, takže se dá dohledat, co ti appka kdy hlásila.

**Co appka hlásí:**

| Událost | Kdy přijde |
|---|---|
| Někdo mi přiřadil záznam | Když tě kolega nastaví vlastníkem nebo spoluvlastníkem případu, objednávky či projektu. |
| Úkol mě čeká dnes | Ráno, souhrnem za všechny dnešní úkoly. |
| Úkol je po termínu | Ráno, souhrnem — kolik jich je a který čeká nejdéle. |
| Změnil se stav mého záznamu | Když někdo jiný posune tvůj případ, nabídku, objednávku nebo projekt. |
| Nabídka odešla zákazníkovi | Potvrzení, že e-mail s nabídkou opravdu odešel. |

U každé události si v **Nastavení → Notifikace** zvlášť zapneš **v appce** (zvoneček)
a **e-mailem**. Dvě věci, které stojí za zapamatování:

- **Co si uděláš sám, ti appka nehlásí.** Když si případ přiřadíš sobě, zpráva nechodí.
- **Úkoly chodí souhrnem, ne po jednom.** Pět úkolů = jedna zpráva, ne pět.

### Poslat e-mail zákazníkovi z appky
Na kartě obchodního případu i v detailu nabídky je tlačítko **✉ Poslat e-mail**. Proč to
dělat odsud a ne z Outlooku: **odeslaný e-mail se zapíše k záznamu jako aktivita**, takže
je pak v historii vidět, co už zákazníkovi odešlo — i pro kolegu, který zakázku přebírá.

V okně je nahoře výběr **šablony**. Vložený text se dá dál normálně upravovat a údaje jako
název firmy nebo číslo případu se doplní samy. Podpis se přidá automaticky; e-mail odchází
z firemní schránky, ne z tvojí osobní.

> Když je někde v odeslaném textu vidět něco jako `{{zakaznik}}`, znamená to, že se ten
> údaj nedoplnil — obvykle proto, že u záznamu chybí. Je to schválně vidět: prázdné místo
> uprostřed věty by si nikdo nevšiml.

**Šablony** (Nastavení → Šablony e-mailů a poznámek) spravuje správce nastavení a jsou
**společné pro celou firmu** — smysl je, aby všichni psali zákazníkům podobně a nikdo
nezačínal od prázdné stránky.

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

- **Povinné** — bez vyplnění nejde záznam **posunout do dalšího stavu**. Pozor, není to
  „nejde uložit“: Doplňující údaje se ukládají průběžně po jednotlivých polích, a kdyby
  povinnost platila při každém stisku klávesy, u rozdělaného záznamu by se nedalo uložit
  vůbec nic. Kontrola je proto u přechodu stavu, kde na ní opravdu záleží.
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

**Skupiny.** Vyplněná *Skupina* seskupí pole pod společný nadpis („Peníze", „Technika").
Pole bez skupiny zůstanou pod obecným nadpisem *Doplňující údaje*.

**Ukázat, jen když…** Pole se dá schovat, dokud jiné pole nemá určitou hodnotu — třeba
*Výkon FVE* jen u případů s kategorií PPA. Napíše se název pole a hodnota, na kterou má
reagovat. Skryté pole se **nevyžaduje**, ani když je označené jako povinné.

**Výpočtová pole.** Vyplněný *Vzorec* udělá z pole počítané: nevyplňuje se ručně, ale
spočítá se — například `hodnota_kc - nakup` pro marži. Ve vzorci smí být čísla, názvy jiných
**číselných** polí, `+ − * /` a závorky. V přehledu i na kartě je takové pole označené
znakem **∑**.

> Výsledek se **přepočítává při každém zobrazení**, neukládá se. Když se změní cena, marže
> se změní sama — nemůže se stát, že by na kartě svítilo staré číslo.

### Automatizace: co appka udělá sama
Některé kroky se dělají pokaždé stejně: případ se vyhraje → založí se objednávka; objednávka
se podepíše → založí se projekt s kroky; nabídka odejde → za týden se má zavolat. Tohle za
tebe udělá appka, pokud je k tomu nastavené **pravidlo**.

> 📸 SCREENSHOT: Nastavení → Automatizace, seznam pravidel s vypínačem a historií běhů

Jak to poznáš, když se to stane:

- **U záznamu se objeví poznámka** „Automatizace: Založena objednávka OBJ-26-0003 — pravidlo
  *Případ vyhrán → objednávka*". Takže je vždycky vidět, že to nebyl člověk.
- Při **hromadné změně stavu** se nad seznamem vypíše, co všechno appka založila.

Čtyři věci, které je dobré vědět dopředu:

1. **Pravidlo zabere u jednoho záznamu jen jednou.** Když případ vrátíš z *Vyhráno* zpátky
   a znovu ho vyhraješ, druhá objednávka nevznikne. Není to chyba — je to ochrana, aby
   zákazník nedostal dvě objednávky na tutéž zakázku.
2. **Když už objednávka (nebo projekt) existuje, automatika nic nezaloží.** Druhá objednávka
   na jednu zakázku je vždycky lidské rozhodnutí, tak ji založ ručně.
3. **Ručně to jde pořád stejně.** Automatika tlačítka nenahrazuje, jen ubírá klikání.
4. **Pravidlo navěšené na změnu pole zabere teprve, když pole opustíš** (klikneš jinam nebo
   zavřeš okno) — ne po každé klávese. Jinak by pravidlo *„změní se hodnota → založ
   objednávku“* zabralo nad nedopsaným **„1“** místo nad **„1 500 000“**, a objednávka za
   korunu už by byla na světě. Průběžné ukládání mezitím hodnotu jen zapisuje, nic nespouští.

**Nastavení** (Nastavení → Automatizace) patří správci nastavení. Pravidlo se skládá ze tří
vět: *když se přesune* (případ / nabídka / objednávka / projekt) — *do stavu* — *tak appka*
(založ objednávku / založ projekt ze šablony / založ úkol s termínem).

> **Nové pravidlo se zakládá vypnuté** a appka s ním nabízí trojici hotových pravidel, taky
> vypnutých. Nejdřív si je projdi, pak zapni — automatika, kterou nikdo nečekal, dělá
> v evidenci větší nepořádek než ruční práce.

U akce **založ projekt ze šablony** se dá šablona nechat na *„podle kategorie případu"* —
FVE případ pak dostane FVE šablonu, peak shaving tu svoji, a stačí jedno pravidlo pro celou
firmu.

U akce **založ úkol** se nastaví, za kolik dní má být termín, jak se úkol jmenuje a kdo ho
dostane (výchozí je vlastník záznamu). Úkol se pak objeví v *Mých úkolech* i v kalendáři.

**Když chceš pravidlo zastavit, vypni ho — nemaž ho.** Historie běhů je jediné vysvětlení,
odkud se vzaly staré automaticky založené záznamy; smazáním pravidla o něj přijdeš (samotné
objednávky a projekty zůstanou).

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

**Totéž platí pro „kdo má záznam otevřený“ a pro ukládání po polích.** Právo na modul tu
nestačí: kdyby se seznam přítomných ověřoval jen jím, dal by se **zkoušením ID** zjistit, že
cizí případ existuje a kdo na něm pracuje — a to je přesně ta informace, kterou 404 místo 403
schovává. Kontroluje se proto přístup ke **konkrétnímu záznamu** a na cizí se odpovídá **404**,
jako by neexistoval. Pravidla se neopisují: použije se ta samá funkce, jakou používá čtení
aktivit a historie, včetně toho, že objednávka, projekt a nabídka vlastníka nemají a práva
dědí ze svého obchodního případu.

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

### Automatizace: jak to funguje uvnitř
`app/crm/automatizace.py`. Volá se z **pěti míst**, kde se mění stav: `zmen_stav_pripadu`,
`zmen_stav_nabidky` (oba `crm/routes.py`), `zmen_stav_objednavky`, `zmen_stav_projektu`
(`crm/routes_realizace.py`) a `hromadne.zmen_stav`. Hromadná akce je v tom seznamu schválně —
kdyby automatiku obcházela, byla by to tichá zadní vrátka („u jednoho případu objednávka
vznikne, u deseti ne").

Čtyři věci, na kterých to stojí, a každá se dá udělat špatně tak, že to vypadá funkčně:

1. **Chyba akce se řeší SAVEPOINTEM, ne `db.rollback()`.** Automatika běží uvnitř transakce,
   která už nese změnu stavu od člověka. Rollback by ji zahodil: appka odpoví OK a případ
   zůstane v původním sloupci. Savepoint (`db.begin_nested()`) vrátí jen to, co nastihla
   spáchat spadlá akce. Hlídá `test_selhani_akce_nezrusi_predchozi_zmeny`.
2. **Před savepointem se flushuje.** Změna stavu je v session ještě neuložená; kdyby ji
   poprvé zapsal až flush *uvnitř* akce, patřila by do savepointu a rollback by ji vzal
   s sebou. Nespoléhat se na autoflush hlídá `test_zmena_stavu_prezije_i_bez_autoflushe`.
3. **„Jednou na záznam" hlídá unikátní index na `crm_pravidlo_behy`**, ne kontrola „existuje
   už objednávka?". Ta by u úkolů nefungovala (úkol může vzniknout i jinak) a případ vrácený
   z výhry a znovu vyhraný by vyrobil druhou objednávku.
4. **Zapisuje se i přeskočení a chyba.** Jen úspěch v logu by znamenal, že tiché selhání
   vypadá jako „pravidlo se nikdy nespustilo" a nikdo by ho nehledal.

Cena objednávky se bere **tou samou funkcí** jako u ručního zakládání (`_cena_z_nabidky`) —
druhá implementace by znamenala, že automaticky a ručně založená objednávka mají jinou cenu.

Katalog akcí (`AKCE`) i nabídku stavů dodává endpoint `/crm/automatizace/akce`, ne konstanta
ve frontendu: stavy jsou konfigurovatelné, takže zadrátovaný seznam by po přeskládání kanbanu
nabízel fáze, které neexistují. Přidání akce = záznam v `AKCE` + funkce `_akce_<klic>`;
`test_kazda_akce_ma_vykonavace` hlídá, že se to nerozejde.

Výchozí pravidla (`seed_pravidla`) se zakládají **`aktivni=False`** a seed sahá jen do úplně
prázdné tabulky. Automatika, která po nasazení začne sama zakládat záznamy, je přesně to, co
lidem vezme důvěru v appku.

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

### Ukládání po polích a přítomnost: jak to funguje uvnitř
Dvě věci, které drží spolu: `PATCH` jednoho pole a tik „jsem tady, mám otevřené tohle“. Je to
**tentýž princip, jaký už běží v [Přehledu projektů](prehled-projektu.md)** a hooky
i komponenty jsou společné (`hooks/useAutosave.js`, `hooks/usePritomnost.js`,
`components/Pritomni.jsx`, `components/StavUlozeni.jsx`) — druhá implementace by se dřív nebo
později rozešla a jedna z nich by tiše ztrácela data.

**API** — jeden generický endpoint pro všechny entity CRM (`crm/routes_pole.py`):

- `PATCH /crm/zaznam/{entita}/{id}/pole` — uloží **jedno** pole. Tělo: `pole`, `hodnota`,
  `puvodni`, `usazeno`. `entita` je `zakaznik` / `kontakt` / `om` / `op` / `obj` / `pro` /
  `nab`. Když se `puvodni` neshoduje s tím, co je v databázi, vrací **409** s
  `{zprava, pole, aktualni, kdo, kdy}` a **nic nepřepíše**; `puvodni: null` znamená „přepiš bez
  kontroly“ (člověk kolizi potvrdil). Vrací **celý** aktualizovaný záznam schválně: server
  dopočítává věci za klientovými zády (cena objednávky, termíny navazujících kroků, výpočtová
  vlastní pole), a kdyby si je prohlížeč nepřepsal, hlásil by při dalším stisku falešnou kolizi.
- `GET /crm/zaznam/{entita}/{id}/razitko` — podpis stavu záznamu. Běžně přichází rovnou
  v odpovědi na tik přítomnosti, takže se nevolá dvakrát.
- `POST /pritomnost/tik` — „jsem tady“ + razítko v jedné odpovědi. Prohlížeč tiká každých 8 s
  a jen když je záložka vidět.

> **Jeden endpoint místo šesti PATCHů** proto, že logika je pro všechny entity stejná
> (whitelist → kontrola kolize → zápis → dopočty). Rozepsat ji šestkrát znamená pět míst, kde
> se na kontrolu kolize zapomene.
>
> **Vlastní prefix `/crm/zaznam`** je taky záměr: cesty v CRM se už dvakrát tiše potkaly
> a přebily funkční obrazovku. Hlídá to `tests/test_kolize_cest.py`.

**Registr entit** (`crm/pole_zaznamu.py`) — jeden řádek na druh záznamu: model, právo,
**whitelist polí**, klíč vlastních polí, entita pro automatizaci a funkce na ověření přístupu
k záznamu. Čtyři rozhodnutí, která z toho plynou:

1. **Whitelist, ne „cokoli na modelu“.** Generický endpoint bez seznamu povolených polí by
   dovolil přepsat vlastníka záznamu, `raynet_id` nebo interní příznaky. Povolená jsou jen
   pole, která člověk skutečně píše do formuláře — `stav`, vlastnictví, `kategorie`, důvod
   prohry ani `hlavni` u kontaktu tam nejsou, protože mají vedlejší efekt na jiné záznamy.
   Že whitelist neobsahuje překlep, hlídá `zkontroluj_whitelist()` z testu; jinak by se to
   projevilo až za běhu jako „pole nelze měnit“ u něčeho, co evidentně existuje.
2. **Typ hodnoty se bere z modelu** (typ sloupce SQLAlchemy), ne z druhého seznamu — ten by se
   s prvním rozešel.
3. **Vlastní pole jdou stejnou cestou** pod klíčem `extra:<klic>`. Zapisuje se ale
   **sloučením** se stavem v databázi (`zpracuj_jedno()`), ne přestavěním celého slovníku:
   `vlastni_pole.zpracuj()` staví nový objekt, takže chybějící klíč se uložením **smaže**.
   Autosave nad ním by z tiché ztráty dat udělal pravidlo. Nový slovník se do atributu musí
   přiřadit znovu — SQLAlchemy si změny uvnitř JSONB nevšimne.
4. **Rozepsaný stav není chyba.** Prázdná hodnota je legitimní (vymazání) a **povinná vlastní
   pole se tu nevynucují** — jinak by autosave u rozpracovaného záznamu vracel 422 a nefungoval
   vůbec. Povinnost hlídá `povinna_pole.py` při přechodu stavu.

**Kolize se hlídá hodnotou, ne verzí.** `verze` roste i při změně **jiného** pole, takže podle
ní by appka hlásila kolizi u věcí, které si vzájemně nevadí (kolega mění telefon, ty poznámku).
Porovnává se proto textová podoba té jedné hodnoty, se kterou člověk začal psát (`puvodni`).
**Čísla se porovnávají číselně:** databáze vrátí `1500000.00`, prohlížeč pošle `1500000` —
textově se to nerovná a člověk by dostal hlášku o kolizi tam, kde se nic nezměnilo. U vlastních
polí se čte přímo z `extra`, ne z výstupu s dopočty (`s_vypocty`): ten dopočítává výpočtová
pole, která v databázi nejsou, a kontrola by na nich hlásila rozdíl pořád.

**Automatizace až při usazení pole.** `usazeno: true` posílá prohlížeč teprve při opuštění pole
(`onBlur`) nebo při zavírání formuláře; průběžné uložení hodnotu jen zapíše. Kdyby se pravidla
navěšená na změnu pole spouštěla po každé klávese, pravidlo *„změní se hodnota → založ
objednávku“* by zabralo nad nedopsaným `1` místo nad `1500000`. Volá se **před commitem** —
po něm SQLAlchemy zahodí historii atributů a nebylo by z čeho poznat, co se změnilo.

**Razítko** (`crm/razitko.py`) — `razitko_zaznamu` je podpis stavu jednoho záznamu,
`razitko_seznamu` podpis celého seznamu (pro kanbany a tabulky). Kromě času poslední změny
a verze jsou v podpisu i **počty pod-záznamů** (kontakty, odběrná místa, aktivity, nabídky,
kroky): přidání ani smazání pod-záznamu čas změny nadřazeného záznamu neposune, takže samotný
čas by na ně byl slepý. U seznamu je navíc nejvyšší `id` — zachytí vznik záznamu i v případě,
že by se hned nato jiný smazal a počet zůstal stejný. **Proč podpis a ne seznam rozdílů:**
počítat „co přesně se změnilo od času X“ by znamenalo držet a testovat historii, a při první
nepřesnosti by lidem tiše chyběla aktualizace. Podpis je tupý, ale nemůže lhát.

**Kdo razítkem musí hýbat.** Aby to fungovalo, volá `pole_zaznamu.oznac_zmenu()` i každý
endpoint, který mění stav (`zmen_stav_pripadu`, `zmen_stav_nabidky`, `zmen_stav_objednavky`,
`zmen_stav_projektu`, `hromadne.zmen_stav`), úprava aktivity a úprava kroku projektu. Bez toho
by se cizí přetažení karty v kanbanu u ostatních neprojevilo, dokud by si stránku neobnovili
ručně — kanban se dosud načítal jen na akci uživatele.

**Registr přítomnosti** (`pritomnost/registr.py`) — jeden řádek na entitu: `pravo` (kdo nesmí
modul otevřít, nesmí vidět ani kdo v něm je), `razitko` a nepovinně `pristup` (ověření
konkrétního záznamu, viz Práva výš). Kromě detailů (`crm_zakaznik`, `crm_kontakt`, `crm_om`,
`crm_op`, `crm_obj`, `crm_pro`, `crm_nab`) jsou v registru i **seznamy** (`crm_seznam_*`), kde
se `entita_id` nepoužívá a razítko je za celý seznam. U seznamů se přítomnost **nezobrazuje** —
kolečko „pět lidí je v seznamu“ je šum; jde jen o to, aby se obrazovka sama aktualizovala po
cizí změně. Neznámý typ endpoint odmítne (400), aby se seznam přítomných nedal obejít bez práva.

**Sledování změn na modelech** (`ZmenaMixin` v `app/database.py`) — `zmeneno_at`, `zmenil_id`
a `verze` na `crm_zakaznici`, `crm_zakaznik_kontakty`, `crm_odberna_mista`,
`crm_obchodni_pripady`, `crm_aktivity`, `crm_objednavky`, `crm_projekty`, `crm_projekt_kroky`
a `nabidky`. **Proč nestačí `aktualizovano_at`,** které některé tabulky měly: hýbe se při
jakékoli změně a **neříká KDO** — hlášku „hodnotu mezitím změnil Petr“ se z něj postavit nedá,
a bez jména se člověk nemá jak rozhodnout, čí verze platí. Tři tabulky (kontakty, aktivity,
kroky) neměly ani to. Mixin sedí vedle `Base`, ne v `crm/models.py`, protože ho používá
i nabídka — a nabídkovač s CRM se navzájem neimportují na úrovni modulu. Sloupce doplňuje lehká
migrace při startu (`main.py`, `ADD COLUMN IF NOT EXISTS`).

> ⚠️ U `Nabidka` musela vazba `vytvoril` dostat explicitní `foreign_keys`: od `ZmenaMixin`
> vedou na uživatele **dva** cizí klíče (autor nabídky a autor poslední změny) a SQLAlchemy
> sám nepozná, který z nich ta vazba používá.

**Chování prohlížeče** (`hooks/useZaznamAutosave.js`) — tři pravidla, bez kterých by průběžné
ukládání škodilo víc, než pomůže:

1. **Pole, ve kterém člověk píše** (nebo které má nedoručenou změnu), aktualizace ze serveru
   **nikdy nepřepíše** — jinak by mu text mizel pod rukama uprostřed věty.
2. Jako `puvodni` se posílá **to, co server naposledy potvrdil**, ne to, co je zobrazené.
3. **Debounce je po jednotlivých polích** (`useAutosave`), ne jeden timer na formulář: člověk
   vyplní termín, hned skočí na poznámku a píše dál — s jedním timerem by psaní do poznámky
   pořád odkládalo i uložení termínu a při zavření okna by se ztratilo obojí. Pro tentýž klíč
   navíc nikdy neletí dvě uložení naráz; poslední hodnota čeká ve frontě, jinak by je server
   mohl zapsat v opačném pořadí.

**Nad jedním záznamem tiká jen jedno místo.** V tabulce přítomnosti je jeden řádek na dvojici
(uživatel, entita), takže dva tiky ze stejné stránky by si navzájem přepisovaly, na kterém poli
člověk stojí, a kolegům by editované pole poblikávalo. U obchodního případu proto tiká **karta**
(`entitaTyp` má ona) a formulář jí právě editované pole jen hlásí; u zákazníka si to střídají —
karta tiká, dokud není otevřené okno úprav, pak tiká ono.

**Zakládání nového záznamu autosave nemá** a mít nesmí: záznam v databázi neexistuje, není co
PATCHovat, a půl vyplněná firma by v seznamu vznikla už při psaní prvního slova. Formuláře proto
mají dva režimy a v tom druhém drží hodnoty ve svém stavu (`zapnuto: false`).

**Klíčové soubory:** `crm/pole_zaznamu.py` (registr, whitelist, převody, kolize, zápis),
`crm/routes_pole.py` (endpointy), `crm/razitko.py` (podpisy), `crm/vlastni_pole.py`
(`zpracuj_jedno`), `pritomnost/registr.py`, `app/database.py` (`ZmenaMixin`), `crm/audit.py`
(slučovací okno `OKNO_SLOUCENI_S`). Frontend: `hooks/useZaznamAutosave.js`, `hooks/useAutosave.js`,
`hooks/usePritomnost.js`, `components/Pritomni.jsx`, `components/StavUlozeni.jsx`,
`components/VlastniPoleVstupy.jsx` (prop `onZmenaPole` = hlášení po jednom poli vedle staršího
`onZmena` s celým `extra`). Testy: `tests/test_crm_pole.py`, `tests/test_pritomnost_pristup.py`,
`tests/test_audit_slouceni.py`.

### Historie změn: slučovací okno
`crm/audit.py`, konstanta **`OKNO_SLOUCENI_S = 300`** (5 minut). Od zavedení ukládání po polích
neplatí „jedno uložení = jedno rozhodnutí“: napsání jednoho slova pošle několik uložení téhož
pole za sebou. Bez slučování by ve výpisu (limit 100 řádků) byly řádky *Tech → Technic →
Technicpl* a po jednom odpoledni psaní by v historii nebylo nic užitečného.

Slučuje se řádek se **stejnou čtveřicí** (`entita`, `zaznam_id`, `pole`, `zmenil_user_id`),
druhu `zmena` a mladší než okno. Autor je v té čtveřici podstatný: cizí změnu si nikdo
přivlastnit nesmí, jinak by v logu stálo, že cenu snížil ten, kdo pak jen opravil telefon.
Vznik ani smazání záznamu se neslučují.

- **`stara` se nikdy nepřepisuje** — drží hodnotu, ZE KTERÉ se to začalo měnit, a to je celý
  smysl logu.
- Když se nová hodnota rovná té původní (A → B → A), **řádek se smaže**: „změnil z Praha na
  Praha“ není informace.
- Slučování je **vylepšení, ne povinnost**: když z jakéhokoli důvodu selže, zapíše se běžný
  nový řádek. Audit nikdy nesmí o změnu přijít kvůli tomu, že se ji nepodařilo přilepit
  k předchozí.

> ⚠️ Slučování jde **surovým SQL** přes `session.connection()`, ne přes ORM. Běží se totiž
> uvnitř `before_flush`: ORM dotaz by spustil autoflush, tedy flush uvnitř flushe („Session is
> already flushing“) a rekurzivní zavolání téhož listeneru. Cenou je, že ORM o zápisu neví — což
> nevadí, protože audit se nikde nečte a nezapisuje současně.

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
| `crm_objednavky` | potvrzené zakázky; `cena_kc` je snapshot, `cena_rucni` = ruční přepis má přednost před součtem rozpisu, `nabidka_id` informativní |
| `nabidka_polozky`, `crm_objednavka_polozky` | rozpis položek; stejné sloupce schválně, protože se z nabídky do objednávky **kopírují**. `technologie_id` je nepovinné (položka mimo katalog), název a ceny jsou snapshot |
| `faktury` *(modul finance)* | od CRM-09 má **dva možné rodiče**: `projekt_id` (Freelo projekt) nebo `crm_objednavka_id` (CRM objednávka). Právě jeden musí být vyplněný — hlídá `ck_faktura_prave_jeden_rodic` |
| `technologie` *(nabídkovač)* | katalog produktů: kód, kategorie, jednotka, prodejní i nákupní cena, DPH, platnost, `zdroj` (`bess_cenik` / `raynet_import` / `rucne`), `aktivni` |
| `technologie_prilohy` | soubory u položky katalogu (technický list, foto, certifikát); na disku v `katalog_soubory/` |
| `crm_projekty` | realizace; `freelo_projekt_id` je most na Freelo projekt (koexistence) |
| `crm_projekt_kroky` | kroky projektu; `zavisi_na_id` je skutečná návaznost mezi kroky |
| `crm_projekt_sablony`, `crm_projekt_sablona_kroky` | šablony kroků; návaznost drží **pořadí** předchůdce, ne id |
| `crm_ulozene_filtry` | uživatelské filtry: podmínky a řazení jako JSONB, příznaky sdílený/výchozí |
| `crm_pravidla` | automatizace: spouštěč (`spoust_entita` + `spoust_stav`), `akce` a její parametry v JSONB `nastaveni`, vypínač `aktivni` |
| `crm_pravidlo_behy` | co pravidlo u kterého záznamu udělalo; unikátní `(pravidlo_id, entita, zaznam_id)` je to, co brání druhému spuštění |

Od 6. 8. 2026 má většina těch tabulek navíc trojici **`zmeneno_at`, `zmenil_id`, `verze`**
(`ZmenaMixin`) — kdo a kdy záznam naposledy změnil. Je to podklad pro razítko změn a pro hlášku
„mezitím to změnil Petr“; `verze` je jen informativní, kolize se hlídá hodnotou (viz „Ukládání
po polích“ výš). Tabulka `pritomnost` (`backend/app/pritomnost/models.py`) drží, kdo má co
otevřené: jeden řádek na dvojici (uživatel, entita), obnovovaný tikem z prohlížeče.

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
| Pravidlo automatizace je zapnuté, ale nic neudělalo | Tři možnosti: (a) u toho záznamu už jednou zabralo — v historii pravidla je řádek, (b) objednávka/projekt už existuje (v logu „Nebylo co udělat"), (c) pravidlo míří na stav, který v nastavení kanbanu už není. |
| V historii pravidla je „Chyba" | Podrobnost je v logu aplikace (`journalctl -u greensie-backend`). Změna stavu se uložila, akce ne — dokonči ji ručně. |
| Automatika nezaložila druhou objednávku po vrácení případu z výhry | Správné chování — pravidlo zabere u záznamu jen jednou. Druhou objednávku (etapu) založ ručně. |
| Projekt vznikl bez kroků | Žádná šablona neodpovídá kategorii případu, nebo případ kategorii nemá. Přiřaď šablonu v pravidle přímo, nebo doplň kategorie u šablon. |
| U karty svítí **„Neuloženo“** | Poslední pokus o uložení selhal (spadlá síť, vypršené přihlášení, neplatná hodnota). Text chyby je vedle. Okno **nezavírej**, dokud nezmizí — zavřením se čekající změna sice ještě odešle, ale když selže i to, je ztracená. |
| **„Mezitím to změnil někdo jiný“** | Do stejného pole zapsal jiný člověk. Nic se nepřepsalo; vyber *Přepsat mojí hodnotou* nebo *Nechat jejich*. |
| Kolečko člověka nezmizelo, i když už odešel | Mizí do 25 s. Uspaný počítač s otevřenou záložkou taky zmizí — skrytá záložka přestane hlásit přítomnost. |
| Změna se neuložila a hlásí „pole se přes automatické ukládání měnit nedá“ | Pole není ve whitelistu (`crm/pole_zaznamu.py`) — typicky stav, vlastník, kategorie. Patří na tlačítko, protože má vedlejší efekty. Když má nové pole autosave dostat, přidej ho do whitelistu i do seznamu polí na frontendu. |
| Kanban se po cizím přetažení karty neaktualizoval | Endpoint měnící stav nezavolal `oznac_zmenu`, takže se razítko seznamu nezměnilo. Doplň ho stejně jako v `zmen_stav_pripadu`. |
| V historii změn je jeden řádek místo dvou úprav | Obě spadly do slučovacího okna (5 min, stejné pole, stejný člověk). Záměr — jinak by výpis zaplnily mezistavy psaní. |

### Poznámky a úskalí
- **Kroky projektu a aktivity: „poslední zápis vyhrává“.** Kroky se ukládají po jednotlivých
  polích, ale jejich endpoint (`PATCH /crm/kroky/{id}`) **kontrolu kolize neumí** — neposílá se
  mu, jakou hodnotu měl člověk na obrazovce, takže nemá s čím porovnávat. U aktivit platí totéž
  (a ty navíc autosave vůbec nemají). Když dva lidé mění tentýž krok nebo tutéž aktivitu
  současně, zůstane ten, kdo uložil později, a appka neřekne nic. **Známé omezení**, ne chyba
  k opravě naslepo: ochrana se dá dodělat tím, že se tyhle endpointy převedou na
  `PATCH /crm/zaznam/...` — u kroků k tomu chybí registr entity a whitelist polí.
- **Kalendář a aktivity autosave nedostaly** a je to záměr. Aktivita může být částí **série**
  (změna se přenáší na ostatní výskyty) a její uložení **rozesílá notifikace** — průběžné
  ukládání by u jedné rozepsané schůzky znamenalo desítky e-mailů a desítky přepsaných porad.
  V obou zůstává tlačítko *Uložit*.
- **Odběrné místo je připravené, ale ještě nezapojené.** Entita `om` je ve whitelistu i registru
  přítomnosti, jenže panel odběrných míst na kartě zákazníka pořád ukládá po staru. Totéž platí
  pro **panel kontaktních osob** na kartě zákazníka (autosave má jen samostatná karta osoby na
  `/kontakty/detail/:id`). Dokud to platí, je nad těmi dvěma panely možné cizí změnu přepsat.
- **Seznamy a kanbany se obnovují samy, ale bez koleček.** Zákazníci, Případy, Objednávky,
  Projekty i Nabídky si tahají razítko seznamu (`crm_seznam_*`) a po cizí změně se přenačtou.
  Kolečka přítomnosti tam schválně nejsou: „pět lidí je v seznamu“ nic neříká a u karty by
  dokonce lhalo o tom, kdo ji drží. Rozepsané hledání a filtry refresh nezahodí — načítá se
  se stejným dotazem, jaký má obrazovka zrovna nastavený.
- **Dvě pravdy o zákazníkovi.** Dokud běží Raynet i appka, vedou se klienti na dvou místech
  a budou se rozjíždět. Jednosměrný sync z Raynetu (`raynet_id` je připravené) zatím není.
- **Objednávky a projekty** ještě nejsou hotové — na kartě případu jsou vyznačené jako
  „připravuje se". Stavy a číselné řady pro ně už ale existují.
- **Sekce Nabídky** jako samostatný globální seznam se připravuje; nabídky jsou dnes vidět
  na kartě případu a v nabídkovači.
