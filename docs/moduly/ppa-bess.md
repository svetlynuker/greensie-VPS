# PPA + BESS

Kalkulačka, která z jednoho odběrového diagramu navrhne **elektrárnu i baterii**
a rozhodne, kolik kapacity baterie věnovat srážení špiček a kolik zvýšení
samospotřeby. Odpovídá na otázku, kterou nabídkovač dosud neumí zodpovědět:
*kdy se baterie vyplatí na peak shaving a kdy na spotřebu z elektrárny.*

- Výpočetní jádro: `backend/app/nabidkovac/ppa_bess.py`
- Testy: `backend/tests/test_ppa_bess.py`
- Panel: `frontend/src/components/PpaBessPanel.jsx`
- Typ nabídky: `ppa_bess`, právo `nabidkovac_ppa_bess`

## Proč nový modul

`ppa_v2.py` umí baterii **jen jako zvýšení samospotřeby** (nabij přebytek, vybij
deficit) a kilowatty vůbec nezná. `peak_shaving.py` umí opačnou polovinu, ale nad
profilem, do kterého elektrárna nezasahuje. Modul „Kombinace opatření" oba
výsledky jen sečte, a nese si tím známou výhradu: baterie navržená nad *původním*
profilem je po instalaci FVE předimenzovaná.

Tady se to láme: **profil pro hledání stropu je odběr ze sítě až po odečtení
výroby**, takže se baterie dimenzuje na špičky, které po instalaci opravdu
zůstanou.

## Minimální vstupy

| Vstup | Proč bez toho nejde počítat |
|---|---|
| 15min diagram (celý rok) | základ pro párování s výrobou i hledání stropu |
| Rezervovaná kapacita (kW) | dnešní náklad na kW = baseline pro peak shaving |
| Rezervovaný příkon (kW) | model 2027 je dvousložkový; RP je jiné číslo než RK |
| Distributor + hladina | určuje sazby Kč/kW (jen VN a VVN) |
| Cena silové složky (Kč/MWh) | bez ní se kWh z elektrárny nedá ocenit |
| Strop velikosti (kWp) | co se fyzicky vejde |

Bez sazeb NTS 2027 v sazebníku výpočet **proběhne**, ale přínos na kilowattech
chybí a je to v upozorněních — netipuje se.

## Rozpad elektrárny na pole

Když je rozpad střechy známý („na jih 200 kWp, na východ 100, na západ 100"),
zadá se přímo a **velikost se nenavrhuje**: je daná součtem výkonů a `max_kwp`
ani cíl samospotřeby ji už neovlivní. Výroba se simuluje pro každé pole zvlášť
a sečte, takže model zná i **tvar** výroby. To není kosmetika — východ-západ má
plošší profil než jih, takže při stejném instalovaném výkonu vyrobí za rok méně,
ale víc se ho spotřebuje na místě a jinak zbyde na baterii.

### Východ-západní konstrukce jedním zadáním

U pole se dá zaškrtnout **rozdělení 50/50 na východ a západ**
(`PoleFve.rozdelit_vychod_zapad`). Zadá se celkový výkon a sklon jednou a jádro
z toho udělá dvě pole po polovině výkonu, s azimutem −90° a +90° od zadané osy.
Osa je `azimut_st`: 0 znamená klasické V/Z, 30 pootočenou střechu (−60 a +120).

Rozklad dělá `rozloz_pole()` **na vstupu**, takže zbytek výpočtu o téhle zkratce
nemusí nic vědět — a výsledek je bit za bit stejný jako při ručním zadání dvou
polí (hlídá test `test_je_stejne_jako_dve_pole_rucne`).

Ve výstupu jsou obě podoby: `elektrarna.pole` = rozložená (z nich se počítají
grafy a součty) a `elektrarna.pole_zadani` = původní zadání, ze kterého panel
předvyplňuje formulář. Bez toho by se pole vrátilo jako dvě a zaškrtnutí by se
ztratilo.

### Cena za kWp u jednotlivého pole

Každé pole umí mít **vlastní nákladovou cenu za kWp** (`PoleFve.cena_kc_kwp`).
Prázdné = použije se `ppa_nakladova_cena_kc_kwp` z Katalogu a výpočtů. Přepis je
tu proto, že jedno pole bývá výrazně dražší než druhé — jiné kotvení, trapéz
proti ploché střeše s balastem, delší kabelové trasy — a paušál za celou
elektrárnu by zkreslil CAPEX, a s ním i cenu PPA.

Nákladovou cenu skládá `nakladova_cena_fve()`, jedno místo pro všechny volající.
Kdyby si to každý počítal sám, přepis by se někde tiše ztratil a CAPEX by vyšel
jinak v ekonomice než ve screeningu katalogu.

Na reálném profilu (2 × 203 kWp, výchozí cena 13 500 Kč/kWp):

| Scénář | Nákladová cena | Cena PPA (20 let) | Sleva |
|---|---|---|---|
| vše z nastavení | 5 481 000 Kč | 2 487 Kč/MWh | 33,9 % |
| východ dražší (18 000) | 6 394 500 Kč | 2 855 Kč/MWh | 24,1 % |
| jih levnější (11 000) | 4 973 500 Kč | 2 282 Kč/MWh | 39,3 % |

Panel u pole s přepsanou cenou ukáže štítek, aby bylo poznat, kde se od
nastavení odchýlilo.

## Dvoucílový dispatch

Vzor je recyklovaný ze `spot_arbitraz.py` (režim „Kombinace" peak shavingu, kde
baterie sráží špičky a ve zbytku obchoduje na spotu). Druhým cílem tu není
obchod, ale uložení přebytku z elektrárny — což je o jedno jednodušší, protože
nabíjení je zdarma a hodnota vybití je pevná, takže nejsou potřeba cenové prahy.

Pořadí rozhodnutí v každém intervalu (`simuluj_usek`):

1. **Přímá samospotřeba** — co elektrárna vyrobí, jde nejdřív do odběru.
2. **Peak shaving vybíjení** — je-li síťový odběr nad stropem, baterie dodá
   rozdíl. Neptá se na cenu.
3. **Povinné dobíjení na trajektorii** — nejdřív z přebytku elektrárny (zdarma),
   a jen když to nestačí, ze sítě pod stropem.
4. **Solární nabíjení** — zbylý přebytek do volné kapacity.
5. **Solární vybíjení** — z kapacity **nad minimální trajektorií**.
6. **Export** — co z přebytku zbylo, do rezervovaného výkonu dodávky.

`minimalni_soc_trajektorie` spočítá zpětným průchodem, kolik nabití si baterie
musí v každém intervalu držet, aby srazila všechny budoucí špičky. Solární posun
pod tuhle hranici nikdy nesáhne, takže o peak shavingu nemusí nic vědět.

**Původ energie v baterii se záměrně nesleduje.** Ochranu řeší trajektorie: ze
sítě se dobíjí jen do ní, takže síťová energie se nikdy nehromadí „nazapas".
Samospotřeba se proto počítá z opačné strany — co do baterie vstoupilo
z přebytku, mínus round-trip ztráty.

## Tři režimy a doporučení

Panel ukazuje všechny tři vedle sebe, aby bylo vidět, kolik kombinace přinesla
nad rámec každé jednotlivé role:

| Režim | Co baterie dělá |
|---|---|
| `kombinace` | sráží špičky i posouvá solár, měsíční strop se volí ekonomicky |
| `spicky` | jen sráží špičky na nejnižší udržitelný strop (dnešní peak shaving) |
| `samospotreba` | strop = naměřené maximum, jen posouvá solár (dnešní PPA) |

**Doporučuje se ten režim, který zákazníkovi skutečně vydělá nejvíc — není to
vždy kombinace.** Volba měsíčního stropu se totiž rozhoduje podle *odhadu*
hodnoty kWh (cena PPA se dopočítá až po dispatchi), a když se odhad rozejde
s realitou, může kombinace vyjít horší. Ekonomika se proto počítá všem třem
režimům a doporučení z toho vypadne, místo aby se předvolilo.

## Ekonomika baterie

Rozhodnuto s Danem 5. 8. 2026:

- **Baterie je pronájem od SPV**, ne investice zákazníka — nabídka je prvních
  deset let bez investice.
- **Nájem je fixní, neindexovaný, a platí se jen 10 let**, i když kontrakt na
  elektrárnu běží 15 nebo 20 let. Anuita úvěru na baterii se proto počítá vždy
  na 10 let, ne na délku kontraktu jako v `ppa_v2.sestav_projekt`.
- **V roce 11 si zákazník baterii odkoupí** za zbytkovou cenu
  (`ppa_bess_zbytkova_hodnota_podil`, default 15 % CAPEX). Od té chvíle neplatí
  nájem, ale nese servis a EMS sám a přínos pokračuje se započtenou degradací.
- **Baterie nikdy nedodává do sítě** — jen posouvá vlastní spotřebu. Do sítě
  teče pouze přebytek elektrárny, za cenu přetoku (defaultně 0 Kč).
- **Snížení RP** se ukazuje jako druhý scénář vedle scénáře bez snížení.

Věcný důsledek fixního nájmu: roční splátka baterie je u 15 a 20letých kontraktů
vyšší než dřív. Protože se DSCR testuje po letech, může to zvednout minimální
cenu PPA — banka se dívá na nejtěsnější rok, a ten je teď v první dekádě.

Cena PPA se hledá **bisekcí**, ne analyticky jako v PPA v2: splátka se v roce 11
láme a v roce odkupu přijde jednorázový příjem, takže analytické řešení
neexistuje. Kritérium investora se testuje jako **NPV při cílové sazbě**, ne přes
IRR — `ppa_fve._irr` bisekuje na [−0,9; 1,0] a vrací `None` i pro výnos nad
100 %, takže test na `irr is not None` hlásil nefinancovatelný projekt i při
DSCR 4,4.

Odkup je **kapitálový** příjem, takže do DSCR nevstupuje: banka poměřuje provozní
zdroje proti dluhové službě. Do IRR vlastního kapitálu vstupuje.

## Výběr baterie: tři cesty

| Cesta | Kdy | Jak dlouho |
|---|---|---|
| **odhad** | rychlá kontrola | sekundy, synchronně |
| **prohledání katalogu** | reálná nabídka | ~2 minuty, na pozadí |
| **ruční zadání** | baterie je známá | sekundy, synchronně |

**Odhad** je heuristika z PPA (medián denního přebytku) + nejlevnější produkt,
který velikost pokryje. Umí přestřelit o řád — na reálné nabídce navrhla 220 kWh
k elektrárně 4 kWp. Model pak aspoň upozorní, že se baterie nevyplatí.

**Prohledání katalogu** (`prohledej_katalog`) ocení každou konfiguraci a řadí
podle peněz. Na reálném profilu (881 MWh, špička 406 kW) prošlo **168 konfigurací
za 1,8 minuty** a našlo baterii o **52 785 Kč/rok lepší** než odhad. Dvě úrovně:

1. **screening** — každá konfigurace v režimu `spicky` s hrubým odhadem hodnoty
   kWh; počet kusů roste jen dokud přínos roste (greedy, jako
   `peak_shaving.vyber_reseni`), takže z 420 konfigurací se počítá 168,
2. **detail** — nejlepších pět se prohnat plným výpočtem se všemi režimy.

Screeningová čísla ve srovnání jsou proto **jen pro řazení** — po plném dopočtu
vycházejí jinak (a lépe). Panel to říká pod tabulkou.

### Běh na pozadí

`prohledej_katalog` běží ve vlastní službě `greensie-vypocty`
(`app/nabidkovac/vypocet_worker.py`), ne v uvicornu — minuty čistého CPU ve web
procesu znamenají 502. Úloha se zařadí do `nabidkovac_vypocet_fronta`, worker ji
přebere podmíněným UPDATE (zámek proti dvěma instancím), propisuje pokrok každé
dvě sekundy a na konci uloží `navrhovana_reseni`.

Vstup skládá **stejná funkce jako endpoint** (`routes.sestav_vstup_ppa_bess`) —
kdyby si ji worker skládal sám, počítal by po změně nastavení nebo sazebníku
s jinými čísly než appka a nikdo by si toho nevšiml.

Když služba neběží, endpoint `/ppa-bess/katalog/stav` vrací `sluzba_bezi: false`
a panel to řekne, místo aby točil kolečko donekonečna. Úlohy se nezařazují
duplicitně: když už jedna pro nabídku čeká nebo běží, vrátí se ta stávající.

## Co panel ukazuje

Struktura držená záměrně blízko PPA a peak shavingu — obchodník má u nového
modulu poznat stejná čísla na stejných místech.

**Dlaždice:** čistý přínos zákazníka (za rok i celkem), z kilowatthodin,
z kilowattů se sražením špičky, **nová rezervovaná kapacita** (dnes → nová,
o kolik lze snížit), nájem baterie s odkupní cenou, pokrytí spotřeby.

**Záložky:**

| Záložka | Co v ní je |
|---|---|
| Přehled | tabulka délek kontraktu (cena, sleva, kdo drží cenu, DSCR, IRR, úspora), rozpad přínosu, projekt a financování, detail baterie |
| **Pro nás (investor)** | co vložíme, **kolik nás stojí úvěr** (úroky), co nám klient zaplatí za PPA a nájem, kdy se vrátí vlastní kapitál, a cash flow po letech se splátkou rozepsanou na úrok a úmor |
| Srážení špiček | **rozpad úspory na rezervované kapacitě** jako u peak shavingu, graf měsíčních maxim (`GrafOdberu`), měsíční tabulka stropů |
| Elektrárna | graf výroba vs. spotřeba (`GrafVyrobaSpotreba`), energetická bilance, detail elektrárny včetně rozpadu na pole |
| Po letech | roční cash flow zákazníka s rokem odkupu |
| Co má baterie dělat | srovnání tří režimů, kliknutím se přepne celý výsledek |
| Průběh | detailní 15min graf (`GrafPrubehu`) — pás výkonu baterie rozdělený na srážení špičky a ukládání ze slunce, pás stavu nabití, schodovitá čára stropu, přehledový pásek roku a vypíchnuté události |
| Katalog baterií | srovnání posouzených konfigurací (jen po prohledání katalogu) |

Rozpad úspory na kilowattech drží stejný vzor jako peak shaving: **dnešní náklad
→ nejlevnější příkon bez investice → „úspora hned bez investice" → náklad
s baterií → „přínos baterie" → roční úspora celkem**, včetně pojistky, že
optimalizace může vyjít dráž než nedělat nic (nese rezervu, dnešní RP ne).

### Pohled investora

Modul dělá nabídku pro zákazníka, ale investorem je Greensie/SPV — a ta potřebuje
vidět druhou stranu rovnice. Záložka „Pro nás" ji rozepisuje:

**Co nás to stojí:** vlastní kapitál (20 % CAPEX, hned), **úroky z úvěru** za celou
dobu, servis a EMS. Úmor se do nákladů nepočítá — jen vrací půjčenou jistinu;
nákladem financování jsou úroky. Splátka je proto v roční tabulce rozepsaná na
**úrok a úmor** (analyticky přes `ppa_v2.zustatek_uveru`, bez iterace kalendáře)
a hlídá to test `test_urok_plus_umor_je_splatka`.

**Co nám klient zaplatí:** za energii z PPA, za nájem baterie (10 let), za odkup
baterie v roce 11, případně výkup přebytku.

**Kdy se to vrátí:** `navratnost_vlastniho_kapitalu_roky` = rok, kdy kumulovaný
cash flow překlopí nad vložený kapitál, s lineární interpolací v tom roce
(„6,6 roku" je použitelnější než „mezi 6. a 7."). K tomu IRR vlastního kapitálu,
NPV a nejtěsnější DSCR.

Na reálném profilu u 15letého kontraktu: vložíme 2,2 mil., úroky nás stojí
5,2 mil., klient zaplatí 20,2 mil. (14,7 za energii + 4,9 za nájem + 0,55 odkup),
zisk po splátkách 5,6 mil., vrátí se za 6,6 roku při IRR 13,9 %.

Delší kontrakt znamená víc zaplacených úroků, ale i víc příjmů a vyšší IRR —
proto se délka nedoporučuje a vybírá ji obchodník podle toho, co klient podepíše.

### Dva scénáře rezervovaného příkonu

Výpočet počítá oba a panel má v hlavičce **přepínač**:

- **se snížením** (výchozí) — smlouva o připojení se sníží na hodnotu, kterou
  baterie umožní. Jednosměrná změna, zpětné navýšení je zpoplatněné.
- **bez snížení** — smlouva zůstane, platí se jen za naměřenou špičku.
  Konzervativní varianta.

Přepínač mění dlaždice, tabulku rozpadu **i graf**. Bez toho graf kreslil vždycky
scénář „bez snížení", kde RP zůstává na dnešní hodnotě — čára „nové RP" tak
ležela na té staré a vypadalo to, že baterie s příkonem nic nedělá. Na reálném
profilu je rozdíl 447 → 263 kW, tedy 99 tis. Kč/rok.

Grafy se skládají z **týchž měsíčních výsledků dispatchu** jako tabulky, takže se
nemohou rozejít. Kontrakt panel ↔ jádro hlídá `TestKontraktSPanelem` — kdyby se
klíč přejmenoval, backend nespadne a v UI by se jen objevilo „—".

## Nabídka pro zákazníka (PDF)

`ppa_bess` je v `sablona_katalog.PODPOROVANE_TYPY`, takže se nabídka sestavuje
a tiskne stejně jako u PPA a peak shavingu — tlačítko „Nabídka pro zákazníka"
na kartě nabídky, editor rozvržení, tisk do PDF.

**Katalog obsahuje 24 zákaznických polí** v pěti skupinách: Elektrárna, Baterie,
Špičky a rezervovaný příkon, Cena a kontrakt, Vaše úspora. Výchozí předloha jich
používá 22 na třech A4 stránkách (řešení → cena → špičky → úspora → graf →
tabulka po letech → závěr).

Dvě věci, které katalog rozhoduje za obchodníka:

- **doporučený režim** — nabídka ukazuje ten, který vyšel nejlépe, ne první
  v seznamu (`_pb_rezim`),
- **nejdelší nabízený kontrakt** — má největší slevu a nabídka má prodávat
  (`_pb_delka`). Dlaždice i roční tabulka čtou z **téže** délky, jinak by si
  odporovaly. Rozpad přínosu se navíc přepočítává přes `prinos_po_delkach`,
  protože cena PPA se s délkou mění.

Nový rezervovaný příkon se bere ze scénáře **se snížením** — zákazníka zajímá,
na kolik lze příkon snížit, ne že zůstane.

**Investorská čísla se do nabídky nedostanou.** CAPEX, úroky, IRR, DSCR, marže,
provize ani zisk Greensie nemají v katalogu extraktor, takže je resolver nikdy
nevrátí a editor je ani nenabídne — stejná zásada jako u PPA. Hlídá to test
`test_investorska_cisla_nejsou_v_katalogu`.

**Právo.** Výstupní endpointy jsou chráněné jen `nabidkovac`, takže
`_over_typ_reseni` u `ppa_bess` navíc kontroluje `nabidkovac_ppa_bess`. Bez toho
by editor nabídky obešel branku modulu — nabídka do PDF je jen jiný pohled na
tentýž výpočet.

## Co modul zatím nemá

- **Výpočtový Excel se vzorci.** `excel_ppa.py` je napsaný pro PPA a obě jeho
  volání mají `"ppa"` natvrdo. Pro PPA + BESS by šel obdobný modul, ale zatím
  ho nic nepředpokládá.
- **Omezení počtu cyklů.** Dispatch může baterii protočit 300× a víc za rok;
  model na to upozorní, ale neomezuje to (peak shaving to reguluje nákladem
  opotřebení).
- **Souběh elektrárny a baterie při prohledávání.** Screening drží velikost
  elektrárny pevnou, aby byly konfigurace srovnatelné; teprve detailní průchod
  ji dopočítá znovu ke konkrétní baterii. Hledat obojí naráz by znamenalo
  násobit dvě smyčky.

## Právo

`nabidkovac_ppa_bess` se schválně **nepřiděluje žádné skupině** — supersprávce má
všechna práva automaticky, takže modul zatím vidí jen on. Až se čísla ověří,
stačí právo přidělit v Admin nastavení bez sahání do kódu. Podsekce se bez práva
nezobrazí ani nepustí přes URL (`muzeDoPodsekce` v `frontend/src/nabidkovac.js`),
a `ppa_bess` je vynechané z `TYPY_NABIDKY_PRO_KATEGORII`, aby si ho vedení
nepřiřadilo ke CRM kategorii a OZ pak nenarazil na 403.

## Záměr do budoucna

„Kombinace opatření" dělá totéž, ale nad původním profilem, tedy s předimenzovanou
baterií. Až se PPA + BESS ověří, Kombinace se zruší. Teď se na ni nesahá —
používají ji OZ.
