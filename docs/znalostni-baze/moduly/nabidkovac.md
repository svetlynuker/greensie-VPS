# Nabídkovač

> **Sekce v nabídce:** `nabidkovac` · **Adresy (routy):** `/nabidkovac` (rozcestník typů) · `/nabidkovac/:typ` (seznam nabídek podsekce) · `/nabidkovac/nabidka/:id` (detail nabídky) · `/nabidkovac/nabidka/:id/vystup/:typ` (editor + náhled nabídky pro zákazníka) · `/nabidkovac/katalog` (katalog a výpočtová nastavení)
> **Kdo smí otevřít:** kdokoli s právem `nabidkovac` (bez práva se sekce v nabídce vůbec nezobrazí); katalog a výpočty jen s právem `nabidkovac_katalog` (vedení/admin)
> **Kód:** frontend `frontend/src/pages/Nabidkovac.jsx`, `NabidkovacSekce.jsx`, `NabidkaDetail.jsx`, `NabidkaVystupStranka.jsx`, `NabidkovacKatalog.jsx`; backend `backend/app/nabidkovac/`

Nástroj obchodních zástupců (OZ) na tvorbu cenových nabídek ve třech produktových liniích –
**PPA**, **Prodej** a **Peak shaving**. Umožňuje založit nabídku, vyplnit zákazníka, nahrát
podklady (faktura, diagram spotřeby), spravovat společný **katalog technologií** a nakonec
sestavit **nabídkovou stránku pro zákazníka** a uložit ji do PDF.

> 📸 SCREENSHOT: rozcestník Nabídkovače – tři dlaždice podsekcí + tlačítko „Katalog a výpočty"

---

## 🧑 Pro uživatele

### K čemu to slouží
Na jednom místě založíš a spravuješ **cenové nabídky pro zákazníky**. Vybereš produktovou linii
(za jakým účelem nabídku děláš), založíš nabídku, doplníš zákazníka, nahraješ podklady a
u linií **PPA** a **Peak shaving** si necháš spočítat řešení a sestavíš z něj hezkou nabídkovou
stránku, kterou uložíš do PDF a pošleš zákazníkovi. Do nabídky pro zákazníka se přitom dostanou
**jen zákaznická data** – interní čísla (nákupní ceny, marže, návratnost investora) appka do
výstupu záměrně nepustí.

### Tři produktové linie (podsekce)
Rozcestník `/nabidkovac` nabízí tři dlaždice (klíč = typ nabídky na serveru):

| Linie | Klíč | K čemu |
|---|---|---|
| **PPA** | `ppa` | Greensie postaví a zainvestuje FVE na střeše zákazníka a dodává mu z ní elektřinu levněji než trh. |
| **Prodej** | `prodej` | Zákazník je vlastníkem zařízení; podle spotřeby se navrhne technologie z katalogu a prodejní cena. |
| **Peak shaving** | `peak_shaving` | Návrh baterie, která ořezává špičky odběru a šetří za rezervovanou kapacitu. |

> ⚠️ **Detailní obsluhu kalkulátorů „Peak shaving" a „PPA pro FVE" tady nepopisujeme** – mají
> vlastní návody: [nabidkovac-peak-shaving.md](nabidkovac-peak-shaving.md) a
> [nabidkovac-ppa-fve.md](nabidkovac-ppa-fve.md). Tenhle návod je o obecné práci s nabídkami,
> katalogem, podklady a nabídkovým výstupem (PDF).

#### Linie Prodej — výpočet se připravuje
U prodeje **zatím není výpočtová metodika**, takže tam nic nepočítá. Panel má ale **stejné
rozvržení jako ostatní linie**, aby se OZ nemusel nic přeučovat, až výpočet přijde:

- vlevo **funkční načtení profilu odběru** (uloží se k nabídce a použije ho i budoucí návrh) a
  seznam **podkladů, které si vyžádat od zákazníka** (spotřeba, požadovaný výkon nebo plocha
  střechy, jestli má být součástí baterie, marže a záruka),
- vpravo napsané, co se připravuje, s odkazem do katalogu produktů.

Vypnutá políčka pro parametry, které server neumí přijmout, tam **schválně nejsou** — vypadala by
jako funkce, kterou jen někdo nezapnul. Nabídku prodeje jde zatím připravit ručně: nahrát podklady,
načíst profil a technologii vybrat z katalogu.

### Tok práce (od založení po PDF)
1. **Vyber podsekci** na rozcestníku (PPA / Prodej / Peak shaving).
2. **Založ nabídku** tlačítkem „+ Nová nabídka" – vznikne prázdný záznam ve stavu *Koncept* a
   appka tě rovnou přepne do jejího detailu.
3. **Vyplň zákazníka** (název, adresa, případně GPS pro budoucí PVGIS) a ulož.
4. **Nahraj podklady** – fakturu (PDF) a/nebo diagram spotřeby (CSV/XLSX). Prvním nahraným
   dokumentem se koncept posune do stavu *Data nahrána*.
5. **Spočítej řešení** – u PPA a Peak shavingu v panelu v detailu nabídky (viz samostatné návody).
6. **Sestav nabídku pro zákazníka** – tlačítko „Nabídka pro zákazníka" v hlavičce detailu (jen u PPA a
   Peak shavingu). Otevře se editor se třemi panely: vlevo **paleta**, uprostřed **papír**
   (pevná A4 na výšku), vpravo **vlastnosti** vybraného prvku.
   Prvky se **přetahují z palety na papír** a dál se po něm volně posouvají myší; při tažení se
   přichytávají k mřížce a k hranám sousedů. **Text se píše přímo na papíře** (dvojklik) a dá se
   formátovat plovoucí lištou (tučné, kurzíva, velikost, barva, zarovnání, odrážky).
   Stránek si můžeš založit, kolik potřebuješ; když prvek přeteče pod okraj, editor to zvýrazní
   a nabídne přesun na další stránku.
   Hotové rozvržení si můžeš uložit jako **šablonu** a příště ji jen vybrat.
   U peak shavingu jsou v nabídce čísla roku 2026 i **modelu od roku 2027** (nové tarify) a
   u obchodních režimů i **výnos z obchodu s elektřinou** – tedy totéž, co ukazuje panel výsledku.
   Prvky, pro které data nejsou, se do PDF netisknou.
7. **Ulož do PDF** – tlačítko „Uložit do PDF" otevře tiskový dialog prohlížeče (tisk / uložit jako PDF).
   U **PPA** nabídky přitom vznikne i **interní výpočtový Excel** se stejným názvem (`.xlsx`) –
   model s živými vzorci k ručnímu doladění. Jsou v něm marže a zisk, takže **zákazníkovi se
   posílá jen PDF**. Podrobně: [Kalkulátor PPA](nabidkovac-ppa-fve.md#výpočtový-excel-k-nabídce).

### Stavy nabídky
Stav se ukazuje jako štítek u nabídky. Životní cyklus (enum na serveru):

| Stav (klíč) | Popisek v appce | Kdy nastává |
|---|---|---|
| `koncept` | Koncept | po založení |
| `data_nahrana` | Data nahrána | automaticky po nahrání prvního dokumentu |
| `zkontrolovano_oz` | Zkontrolováno OZ | povinná brána před výpočtem (řeší kalkulátory) |
| `spocitano` | Spočítáno | po spuštění výpočtu |
| `hotovo` | Hotovo | ruční koncový stav |

> Poznámka: stav se dá měnit i ručně přes úpravu nabídky (pole `stav`), ale v obecném rozhraní
> pro to není samostatné tlačítko – posun `koncept → data_nahrana` dělá appka sama při nahrání
> dokumentu, ostatní přechody obstarávají kalkulátory PPA / Peak shaving.

### Rozvržení obrazovek

**A) Rozcestník `/nabidkovac`** – odkaz zpět na hlavní rozcestník appky, hlavička s popisem,
vpravo nahoře tlačítko **⚙ Katalog a výpočty** (jen s právem na katalog) a tři dlaždice podsekcí.

**B) Seznam nabídek `/nabidkovac/:typ`** – nadpis podsekce, upozornění o rozpracovanosti výpočtu,
lišta s tlačítkem **+ Nová nabídka** a počítadlem, a tabulka nabídek (Zákazník · Stav · Vytvořil ·
Datum). Klik na řádek otevře detail.

**C) Detail nabídky `/nabidkovac/nabidka/:id`** – shora: odkaz zpět, pak **hlavička zákazníka**
na jeden řádek (název, adresa, štítky linie + stav, tlačítka *Upravit zákazníka* a u PPA/Peak
shavingu *Nabídka pro zákazníka*), sbalená karta **Podklady** (nahrávání dokumentů) a pak už
**panel řešení** — u Peak shavingu „pracovní stůl" (vlevo vstupy, vpravo výsledek), u PPA
kalkulátor, u Prodeje stejný stůl s prázdným výsledkem (výpočet se připravuje).

Formulář s údaji zákazníka a karta Podklady se rozbalují na vyžádání; u čerstvě založené nabídky
(bez názvu zákazníka, resp. bez dokumentů) se otevřou samy. Důvod: do obojího se sahá jednou na
začátku, zbytek času tam patří výpočet.

**D) Nabídka pro zákazníka `/nabidkovac/nabidka/:id/vystup/:typ`** – nahoře dvouřádková lišta
(zpět, historie ↶↷, zvětšení, uložení a PDF; ve druhém řádku stránky a šablony), pod ní tři
panely: vlevo **paleta**, uprostřed **papír** (pevné A4 stránky pod sebou), vpravo **vlastnosti**
vybraného prvku. Postranní panely se dají zabalit šipkou, aby byl papír větší.

Papír není náhled vedle editoru – **je to přímo dokument**, který se vytiskne. Co je na něm
vidět, to vyjede v PDF.

> 📸 SCREENSHOT: detail nabídky – hlavička zákazníka, sbalené Podklady a pod nimi panel řešení
> 📸 SCREENSHOT: obrazovka „Nabídka pro zákazníka" – tři panely, uprostřed A4 s prvky

### Ovládací prvky — políčko po políčku

Legenda „kdo vidí": **(vše)** = každý, kdo Nabídkovač otevře (právo `nabidkovac`) ·
**(katalog)** = jen s právem `nabidkovac_katalog` (vedení/admin).

#### Rozcestník a seznam nabídek
| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět na rozcestník** | rozcestník | Návrat na hlavní rozcestník appky | vše |
| **⚙ Katalog a výpočty** | rozcestník, vpravo | Otevře správu katalogu technologií a výpočtových nastavení | katalog |
| **Dlaždice PPA / Prodej / Peak shaving** | rozcestník | Otevře seznam nabídek dané podsekce | vše |
| **+ Nová nabídka** | seznam podsekce | Založí prázdnou nabídku (stav *Koncept*) a přejde do jejího detailu | vše |
| **Počítadlo „N nabídek"** | seznam podsekce | Kolik je v podsekci nabídek | vše |
| **Řádek nabídky** | tabulka | Klik otevře detail nabídky | vše |

#### Detail nabídky – údaje zákazníka (rozbalovací formulář)
| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **Název zákazníka** | Jméno/firma zákazníka (zobrazí se i v hlavičce PDF) | vše |
| **Adresa** | Adresa zákazníka (zobrazí se v hlavičce PDF) | vše |
| **GPS šířka (lat) / délka (lng)** | Souřadnice pro budoucí PVGIS; zatím jen uložení | vše |
| **Doplňující údaje** | Vlastní pole nabídky, definuje je admin v CRM | vše |
| **Upravit zákazníka / Zavřít údaje** | Rozbalí a zavře formulář v hlavičce detailu | vše |
| **Hotovo** | Zavře blok. **Neukládá** — pole se ukládají sama (viz níž) | vše |
| **Smazat nabídku** | Smaže celou nabídku včetně nahraných souborů (s potvrzením) | vše |

**Tenhle blok se od 6. 8. 2026 ukládá sám, pole po poli** — tlačítko *Uložit* v něm už není.
V hlavičce detailu je vidět stav (*Ukládám… / Uloženo v 14:32 / Neuloženo*) a kolečka
s iniciálami lidí, kteří mají tu samou nabídku otevřenou. Když do stejného pole mezitím zapsal
někdo jiný, appka nic nepřepíše a zeptá se, čí hodnota platí. Celý popis včetně toho, co
autosave neumí, je v [CRM → Úpravy se ukládají samy](crm.md).

> **Vstupy výpočtu se takhle neukládají** (profil spotřeby, sazby, parametry PPA/BESS).
> Nabídka se z nich přepočítává do verzí, takže je ukládá až **Spočítat** — průběžné ukládání
> by z každé rozepsané sazby udělalo novou verzi výpočtu.

**Když je nad nabídkou někdo další, panel vstupů to řekne (od 6. 8. 2026).** V hlavičce
*Vstupy výpočtu* se objeví kolečka s iniciálami a u tlačítka **Spočítat** věta, že přepočet
uloží tvoje vstupy jako novou verzi a přepíše zadání, na kterém možná někdo pracuje.

Je to schválně jen upozornění, ne zámek: rozpracované zadání zůstává v tvém prohlížeči, takže
technicky se cizí vstupy přepsat *dají* — appka ti k tomu jen nedá dojít omylem. Když jsi
u nabídky sám, nezobrazí se nic. Kdo pracuje na téže nabídce z jiného počítače, o rozepsaném
zadání kolegy pořád neví; to by šlo vyřešit až ukládáním konceptu na server.

#### Detail nabídky – sbalená karta Podklady (nahrávání dokumentů)
| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **Přetáhni sem soubor / klikni** | Nahraje soubor (drag & drop nebo výběr); typ se pozná sám z přípony, max 25 MB | vše |
| **Typ (u řádku dokumentu)** | Rozpoznaný typ; rozbalovátkem jde opravit, pokud to přípona dovolí (PDF = faktura / jiný, tabulka = spotřeba / jiný) | vše |
| **Řádek dokumentu** | Ukáže název, velikost, typ a stav zpracování | vše |
| **Smazat (u dokumentu)** | Smaže dokument (soubor i záznam) | vše |
| **Nabídka pro zákazníka** | Jen u PPA/Peak shavingu – tlačítko v hlavičce detailu, přejde do editoru výstupu | vše |

#### Nabídka pro zákazníka – lišta a editor
| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět na nabídku** | lišta | Návrat do detailu nabídky | vše |
| **↶ / ↷** | lišta | Krok zpět a vpřed (Ctrl+Z / Ctrl+Y). Tažení nebo psaní je jeden krok, ne stovky | vše |
| **− 100 % +** | lišta | Zvětšení papíru (50–150 %). Rozměry dokumentu to nemění, jen se na něj líp vidí | vše |
| **• neuloženo** | lišta | Upozornění, že rozvržení má neuložené změny. Při zavření karty se appka ještě zeptá | vše |
| **Uložit** | lišta | Uloží rozvržení této nabídky (per typ řešení) | vše |
| **Uložit do PDF** | lišta | Otevře tiskový dialog prohlížeče (tisk / uložit jako PDF) | vše |
| **Čísla stránek** | lišta, 2. řádek | Skok na stránku. Vykřičník = na stránce něco přetéká | vše |
| **+ stránka / Duplikovat / ↑ ↓ / Smazat stránku** | lišta, 2. řádek | Správa stránek dokumentu (max 50). Poslední stránka se nemaže, jen vyprázdní | vše |
| **Použít šablonu…** | lišta, 2. řádek | Nahradí rozvržení: výchozí předlohou, uloženou šablonou, nebo rozvržením jiné nabídky téhož typu | vše |
| **Uložit jako šablonu…** | lišta, 2. řádek | Uloží současné rozvržení pod názvem pro další nabídky (stejný název přepíše) | vše |
| **Smazat šablonu…** | lišta, 2. řádek | Smaže uloženou šablonu (nabídky, které z ní vznikly, to neovlivní) | vše |
| **Pruh „přetéká"** | pod lištou | Kolik prvků leze pod okraj sazby, s prokliky na ně. V PDF by se ořízly | vše |
| **Paleta – Prvky** | vlevo | Kontejner, Text, Graf, Tabulka, Obrázek, Čára, Obdélník, Číslo stránky. Chyť a přetáhni na papír | vše |
| **Paleta – sekce s údaji** | vlevo | Skupiny zákaznických hodnot (Navržené řešení, Rezervovaná kapacita, Úspora 2026, Úspora od 2027, Obchod). Každá položka je **hotová dlaždice s reálnou hodnotou** té nabídky. Ztlumená = na papíře už je (další kopii přidat můžeš) | vše |
| **Tažení po papíře** | papír | Chyť prvek kdekoli a posuň. Přichytává se k mřížce po 5 mm a k hranám sousedů – oranžová linka ukazuje, na co se chytil | vše |
| **Puštění nad kontejnerem** | papír | Vloží prvek dovnitř kontejneru. Oranžová značka ukazuje, mezi které dva prvky spadne | vše |
| **Osm úchytů kolem prvku** | papír | Změna velikosti. Tažením za horní/dolní hranu se zároveň vypne „výška podle obsahu" | vše |
| **Dvojklik na text** | papír | Otevře psaní přímo v prvku. Nad ním se objeví lišta s formátováním | vše |
| **Formátovací lišta** | papír | Tučné, kurzíva, podtržené, přeškrtnuté, velikost písma (7–32 b), barva, zarovnání, odrážky, číslování, zrušení formátu | vše |
| **Šipky / Shift+šipky** | papír | Posun vybraného prvku po 1 mm, se Shiftem po 5 mm | vše |
| **Delete / Ctrl+D / Escape** | papír | Smazat prvek · duplikovat · zrušit výběr (a při tažení vrátit prvek zpátky) | vše |
| **Obsah** | vpravo | Podle druhu: výběr údaje a vlastní popisek, sloupce tabulky, nahrání obrázku. Přepínač **Tisknout** prvek skryje z PDF, ale nechá ho v editoru | vše |
| **Uspořádání uvnitř** | vpravo (Kontejner) | Kolik prvků vedle sebe (1–6 sloupců) a mezera mezi nimi | vše |
| **Umístění a velikost** | vpravo | Přesná čísla v milimetrech, „výška podle obsahu" a zámek proti posunu | vše |
| **Vzhled** | vpravo | Pozadí, rámeček a jeho tloušťka, zaoblení rohů, vnitřní okraj | vše |
| **Pořadí a akce** | vpravo | Dopředu/dozadu ve vrstvách, duplikovat, smazat, přesun na sousední stránku | vše |
| **Nastavení dokumentu** | vpravo (bez výběru) | Pruh s logem, kontaktní zápatí, vodoznak a jeho sytost; přepínač přichytávání k mřížce | vše |

Papír je WYSIWYG: je na něm právě to, co se vytiskne. Prvek s vypnutým **Tisknout** je v editoru
ztlumený a označený, do PDF nejde.

Prvek může ležet přímo na papíře, nebo v **kontejneru**. Kontejner je rámeček, ve kterém prvky
stojí pod sebou (nebo v mřížce o několika sloupcích) – hodí se na skupiny dlaždic, které mají
držet pohromadě. Přetahováním se mění jejich pořadí uvnitř i mezi kontejnery. Kontejner do
kontejneru vložit nejde.

> 📸 SCREENSHOT: editor nabídky – vlevo paleta, uprostřed A4 s vybraným prvkem, vpravo vlastnosti
> 📸 SCREENSHOT: psaní textu na papíře s plovoucí formátovací lištou

### Práce s katalogem a vlastními sloupci
Katalog technologií je **společný** (jeden pro celý Nabídkovač) a najdeš ho přes **⚙ Katalog
a výpočty** (`/nabidkovac/katalog`). **Prohlížet ho může každý s právem `nabidkovac`, editovat
jen s právem `nabidkovac_katalog`.**

Obrazovka je rozdělená do **pěti záložek**, jedna na každou spravovanou věc:

| Záložka | Co v ní je |
|---|---|
| **Produkty** (s počtem) | katalog produktů — celý ceník firmy (ceny, kategorie, přílohy), hledání, filtry, vlastní sloupce |
| **Sazby distributorů** (s počtem) | ceny pro peak shaving po distributorech a hladinách |
| **Peak shaving** | výchozí hodnoty výpočtu baterie (práh doporučení, NPV, O&M, degradace) |
| **PPA pro FVE** | marže, délky kontraktu a výchozí hodnoty PPA výpočtu |
| **Verze nastavení** | historie verzí — jen ke čtení, doklad, s čím se počítala která nabídka |

Dřív bylo všechno na jedné stránce pod sebou a katalog produktů ji roztáhl na několik obrazovek.

**Záložka Produkty** je celý ceník firmy — od 31. 7. 2026 je v něm **329 položek**:
244 naimportovaných z Raynetu (panely, střídače, baterie, montážní práce, administrativa)
a 85 sestav z ceníku BESS, které pohánějí výpočet peak shavingu.

Ovládací prvky nad tabulkou:

| Prvek | Co dělá |
|---|---|
| **Hledání** | filtruje podle kódu, názvu, modelu i kategorie |
| **Filtr kategorie** | Střídače, Baterie, Panely, Montážní práce, Administrativa… (co je v datech) |
| **Aktivní / Vyřazené / Vše** | výchozí je *Aktivní* — vyřazené zboží nepřekáží |
| **Filtr typu** | Vše / FVE panel / Invertor / Baterie / Jiná (typ řídí **výpočty**, kategorie jen zobrazení) |
| **Okno: nízké / vysoké / celé** | jak vysoký je výřez seznamu; *celé* limit zruší a tabulka roste, jak potřebuje. Volba se pamatuje v prohlížeči. |

Pod tabulkou je vidět, **kolik z kolika** položek je zobrazeno, takže filtr nejde přehlédnout.

**Hromadné akce:** zaškrtávátka v prvním sloupci. Jakmile něco označíš, objeví se lišta
s **Zapnout**, **Vypnout** a **Přeřadit do kategorie…** — po importu 244 položek by jinak
vyřazení celé kategorie znamenalo desítky kliknutí.

| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **+ Produkt** | Otevře dialog nové položky katalogu | katalog |
| **+ Vlastní sloupec** | Přidá vlastní sloupec katalogu (např. „Záruka"), text nebo číslo | katalog |
| **Řádek produktu** | Klik otevře editaci | katalog |
| **Smazat (u produktu / sloupce)** | Smaže položku / definici sloupce | katalog |
| **Vlastní sloupec (štítek)** | Klik na název upraví sloupec, × ho smaže (uložené hodnoty osiřejí, neškodí) | katalog |
| **Uložit jako novou verzi** | V záložkách *Peak shaving* a *PPA* — uloží **obě** sady parametrů jako novou verzi (drží se ve stavu, přepnutím záložky se nic neztratí) | katalog |

**Karta položky** (klik na řádek) má všechno na jednom místě:

| Sekce | Pole |
|---|---|
| Hlavička | *Kód*, *Kategorie* (s našeptávačem už použitých), *Název*, *Model*, *Jednotka*, *Popis* |
| Ceny | *Prodejní cena bez DPH*, *Nákupní cena / náklad*, *Sazba DPH* (21 / 12 / 0 %) a dopočítaná **Marže** v Kč i % |
| Parametry a platnost | *Typ* (pro výpočty), *Účinnost*, *Výkon (kW)*, *Kapacita (kWh)*, *Platnost od / do* |
| Vlastní sloupce | co si vedení nadefinovalo (Záruka, Cyklů životnosti…) |
| **Soubory** | technický list, foto, certifikát — dá se nahrát **víc souborů naráz**, u obrázků se ukáže náhled, druh přílohy jde přepnout |
| **Aktivní** | zaškrtávátko dole; neaktivní položka zůstane na starých nabídkách, ale do nových se už nenabídne |

**Nákupní cenu a marži vidí jen ten, kdo má právo `nabidkovac_katalog`** (vedení a admin).
Není to jen skryté v obrazovce — obchodníkovi je API vůbec nepošle.

**U baterií z ceníku BESS musí být vyplněný výkon i kapacita** (obojí kladné) – bez nich nelze
počítat peak shaving. U bateriových *komponent* z prodejního ceníku (BMS, racky, kabeláž) se
tyhle údaje nevynucují; do simulace se nedostanou právě proto, že je nemají.

**Smazat položku, která už je v nějakém rozpisu, nejde** — appka to odmítne a nabídne odškrtnutí
*Aktivní*. Rozpis by jinak přišel o vazbu na technický list a historii.

> **Znovunahrání ceníku z Raynetu:** `python -m scripts.import_produkty` (náhled nasucho)
> a `--zapsat` (provede). Idempotentní podle kódu: existující položce srovná ceny, platnost
> a popis, nesahá na *Aktivní* ani na typ. Baterie z ceníku BESS nikdy nepřepíše.

> Výpočtová nastavení (verze, PPA/PS defaulty) a Sazby distributorů slouží kalkulátorům a jsou
> popsané v návodech [nabidkovac-ppa-fve.md](nabidkovac-ppa-fve.md) a
> [nabidkovac-peak-shaving.md](nabidkovac-peak-shaving.md).

### Z čeho se skládá nabídkový výstup
Dokument je seznam **pevných A4 stránek na výšku**. Na stránce leží **prvky** na milimetrových
souřadnicích – tam, kam je obchodník posadil. Druhy prvků:

| Druh | Co zobrazí |
|---|---|
| **Kontejner** | Rámeček s vlastním nadpisem; uvnitř stojí prvky pod sebou nebo v mřížce o 1–6 sloupcích |
| **Text** | Formátovaný odstavec – píše se přímo na papíře, včetně tučného, barev a velikostí |
| **Údaj** | Dlaždice s jednou zákaznickou hodnotou z výpočtu (např. roční úspora) |
| **Graf** | Graf dle typu řešení (PPA: výroba vs. spotřeba; Peak shaving: měsíční špičky) |
| **Tabulka** | Roční tabulka (jen zákaznické sloupce) |
| **Obrázek** | Nahraná fotka, schéma nebo logo |
| **Čára / Obdélník / Číslo stránky** | Grafické drobnosti na dotažení vzhledu |

Prvek leží buď přímo na stránce, nebo v kontejneru. **Vnoření je jednoúrovňové** – kontejner do
kontejneru nepatří; jedna úroveň stačí a chová se při tažení předvídatelně.

Nová nabídka startuje z **kódové výchozí předlohy** (jiná pro PPA, Peak shaving a Kombinaci).
Předloha se negeneruje ručně po souřadnicích: `sablona_katalog.py` popisuje sekce a rozvržení
dopočítá – skládá je pod sebe a při přetečení založí novou stránku. Jakmile klikneš **Uložit**,
uloží se rozvržení konkrétní nabídky. Není žádná globální master šablona – **každá nabídka má
vlastní**; sdílet se dají přes pojmenované šablony. V editoru jsou **dostupná jen zákaznická
pole**; interní čísla se nenabízejí.

> V editoru se prázdná pole (bez spočítané hodnoty) ukazují se zástupným „—", ať je vidět, co
> se doplní po výpočtu. **V tisku/PDF se prvky bez dat automaticky skryjí.**

#### Přetečení stránky
Papír je pevná A4, takže se obsah sám nikam nepřelije. Když prvek přeleze pod spodní okraj sazby
(266 mm), editor ho **orámuje červeně** a nahoře se objeví pruh s prokliky na všechna taková
místa. V panelu vlastností je pak tlačítko *Přesunout na další stránku*. Je to schválně ruční:
u volného umísťování by automatické přeskakování prvků mezi stránkami rozvržení rozhazovalo
pod rukama.

### Jak na…
- **Založit novou nabídku:** rozcestník → vyber linii → *+ Nová nabídka* → vyplň zákazníka → *Uložit*.
- **Nahrát fakturu / diagram spotřeby:** detail nabídky → rozbal *Podklady* → vyber typ → přetáhni
  soubor. (Soubor se zatím jen uloží, automatické čtení se připravuje.)
- **Sestavit nabídku do PDF:** detail (PPA/Peak shaving) → *Nabídka pro zákazníka* → přetáhni
  prvky z palety na papír, rozmísti je myší, dvojklikem napiš texty → *Uložit* → *Uložit do PDF*
  (dialog tisku prohlížeče).
- **Vrátit se k výchozí předloze:** v editoru výstupu *Použít šablonu… → Výchozí předloha*
  (přepíše se až po *Uložit*).
- **Přesunout prvek do kontejneru:** chyť ho a pusť nad kontejnerem – oranžová značka ukáže,
  mezi které dva prvky spadne. Ven se dostane stejně, jen ho pustíš na volné místo papíru.
- **Vrátit omyl:** Ctrl+Z (nebo ↶ v liště). Celé přetažení je jeden krok zpět.
- **Přidat technologii do katalogu:** *Katalog a výpočty* → záložka *Produkty* → *+ Produkt* → vyplň a *Uložit*.
- **Přidat vlastní sloupec katalogu:** *Katalog a výpočty* → záložka *Produkty* → *+ Vlastní sloupec* → název + typ (text/číslo).
- **Najít produkt v dlouhém katalogu:** záložka *Produkty* → napiš část názvu do hledání, případně zvol typ. Přepínačem **Okno** si nastavíš, jak vysoký výřez seznamu chceš.
- **Smazat nabídku:** detail nabídky → *Smazat nabídku* (smaže i nahrané soubory).

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Sekci **Nabídkovač** uvidí v panelu vlevo jen ten, kdo má právo `nabidkovac` — bez něj tam položka vůbec není.
- **Práce s nabídkami** (seznam, založení, úprava, mazání, dokumenty, nabídkový výstup) vyžaduje
  právo **`nabidkovac`** (role „OZ" = běžná skupina s tímto právem). Strážce `vyzaduj_nabidkovac`.
- **Editace katalogu a výpočtových nastavení** (technologie, vlastní sloupce, výpočtová nastavení,
  sazby distributorů) vyžaduje navíc právo **`nabidkovac_katalog`** (vedení/admin). Strážce
  `vyzaduj_katalog`. **Čtení** katalogu (`GET /technologie`, `GET /katalog-sloupce`) stačí právo
  `nabidkovac`; zápis vyžaduje `nabidkovac_katalog`.
- **Supersprávce** (`uzivatel.je_admin`) má automaticky všechna práva.
- Práva se spravují v modulu **Admin nastavení** (skupiny + individuální výjimky). Klíče práv:
  `nabidkovac`, `nabidkovac_katalog` (viz `backend/app/auth/permissions.py`).

### Napojení na okolní systémy
- **Disk / soubory:** nahrané dokumenty se ukládají na disk serveru do
  `NABIDKOVAC_UPLOAD_DIR` (default `<kořen repa>/nabidka_soubory`, je v `.gitignore`),
  do podsložky `<nabidka_id>/<uuid>_<nazev>`. Soubory se **nezpracovávají** – jen uloží.
- **Raynet:** katalog technologií má připravená pole `raynet_id` + `synchronizovano_at` pro
  budoucí synchronizaci, zatím se plní **ručně**.
- **PVGIS:** GPS zákazníka (`zakaznik_gps_lat/lng`) je připravené pro budoucí výpočet výroby FVE.
- **PDF:** **negeneruje se na serveru** – tlačítko „Uložit do PDF" volá `window.print()`
  v prohlížeči nad tiskovou A4 stránkou náhledu (viz níže).

### Jak to funguje uvnitř (stručně technicky)

- **Datový model** (`backend/app/nabidkovac/models.py`):
  - `nabidky` — nabídka (`typ` = ppa/prodej/peak_shaving, `zakaznik_nazev`, `zakaznik_adresa`,
    `zakaznik_gps_lat/lng`, `stav`, `vytvoril_user_id`, `vypoctova_nastaveni_id`). `typ` je jen
    účel založení; skutečná řešení žijí v `navrhovana_reseni`.
  - `nabidka_dokumenty` — nahraný soubor (`typ` = faktura_pdf/spotreba_csv/jiny, `soubor_cesta`,
    `puvodni_nazev`, `velikost_bajtu`, `stav_zpracovani`; default `nahrano`). Kaskáda z nabídky.
  - `technologie` — katalog (`typ`, `nazev`, `model`, `vykon_kw`, `kapacita_kwh`, `cena_kc`,
    `ucinnost`, `dostupnost`, `extra` JSONB pro vlastní sloupce, `raynet_id`).
  - `katalog_sloupce` — definice vlastního sloupce katalogu (`klic` unikátní/neměnný, `nazev`,
    `typ` text/cislo, `poradi`). Hodnoty se ukládají do `technologie.extra` pod `klic`.
  - `nabidka_vystup` — uložená nabídková šablona per (`nabidka_id`, `typ_reseni`), unikát na
    dvojici; `konfigurace_json` = seznam prvků (`druh`, `viditelny`, `nadpis`, `text`, `pole`,
    `klic`, `sirka`).
  - `vystup_sablony` — pojmenované rozvržení k opakovanému použití, unikát na (`nazev`,
    `typ_reseni`); `konfigurace_json` má stejnou strukturu. Bez zákaznických čísel.
  - `navrhovana_reseni` — výstup výpočtu (`typ_reseni`, `popis_json`, `vybrano_zakaznikem`).
    Zdroj hodnot pro nabídkový výstup.
  - `vypoctova_nastaveni` — verzovaná globální nastavení (nikdy se nepřepisují), `spotreba_profil`,
    `extrahovana_data_faktury`, `sazby_distributoru`, `generovane_nabidky_pdf` — patří kalkulátorům
    (viz jejich návody).
- **API** (`backend/app/nabidkovac/routes.py`, prefix `/nabidkovac`):
  - `GET /nabidky?typ=` — seznam nabídek (volitelný filtr podsekce.)
  - `POST /nabidky` — založí nabídku (stav *koncept*).
  - `GET /nabidky/{id}` — detail (včetně dokumentů a řešení).
  - `PUT /nabidky/{id}` — úprava zákazníka a případně stavu.
  - `DELETE /nabidky/{id}` — smaže nabídku i soubory.
  - `POST /nabidky/{id}/dokumenty` — nahraje dokument (multipart: `soubor`, volitelně `typ`;
    bez `typ` se odvodí z přípony); posune koncept na *data_nahrana*.
  - `PATCH /dokumenty/{id}` — přepne typ nahraného dokumentu (jen typ, který přípona dovoluje).
  - `DELETE /dokumenty/{id}` — smaže dokument (soubor + záznam).
  - `GET/POST /technologie`, `PUT/DELETE /technologie/{id}` — katalog (čtení: `nabidkovac`; zápis: `nabidkovac_katalog`).
  - `GET/POST /katalog-sloupce`, `PUT/DELETE /katalog-sloupce/{id}` — vlastní sloupce katalogu.
  - `GET /nabidky/{id}/vystup/{typ_reseni}?vychozi=` — podklad pro editor i náhled (konfigurace,
    katalog polí, resolvnuté zákaznické hodnoty, tabulka, graf). `vychozi=1` vrátí kódovou předlohu.
  - `PUT /nabidky/{id}/vystup/{typ_reseni}` — uloží rozvržení (validace whitelistu + sanitizace
    formátovaného textu).
  - `GET /vystup-sablony/{typ_reseni}?krome_nabidky=` — pojmenované šablony + rozvržení jiných
    nabídek stejného typu (k výběru v editoru).
  - `POST /vystup-sablony/{typ_reseni}` — uloží rozvržení pod názvem (stejný název přepíše),
    `DELETE /vystup-sablony/{typ_reseni}/{id}` — smaže šablonu.
  - `POST /nabidky/{id}/vystup-obrazky` — nahraje obrázek k vložení do nabídky (max 10 MB,
    png/jpg/webp/svg), vrátí cestu do konfigurace.
    `GET /vystup-obrazky/{cesta}` — vydá ho zpátky (kontroluje tvar cesty i úložiště).
  - Výpočtové endpointy (`.../peak-shaving/*`, `.../ppa/*`), `vypoctova-nastaveni`, `sazby` —
    patří kalkulátorům (viz jejich návody).
- **PDF / tisk (jak vzniká):** žádné serverové generování. Komponenta
  `frontend/src/components/vystup/Papir.jsx` vykreslí dokument z konfigurace + resolvnutých
  hodnot **dvakrát** – jednou jako editovatelný papír a jednou jako skrytá tisková kopie bez
  ovládání (`.vystup-tisk`). Tlačítko „Uložit do PDF" spustí `window.print()`; v `@media print`
  se editor schová a vytiskne se ta kopie. V tisku se skrývají prvky bez dat a prvky s vypnutým
  *Tisknout*.
- **Proč pevná A4 a mm souřadnice:** stránka má natvrdo 210 × 297 mm a `@page` má `margin: 0`,
  takže **milimetr na obrazovce = milimetr na papíře**. Okraje sazby si drží samy prvky. Kdyby
  okraje řešil `@page`, obsah by se v PDF posunul a souřadnice z editoru by přestaly sedět.
  Zvětšení v editoru je `transform: scale()` na stránce plus obal, který za ni drží místo v
  rozvržení – bez obalu by se při zoomu nad 100 % stránky překrývaly.
- **Záhlaví, zápatí a vodoznak na každé stránce:** protože každá stránka dokumentu je vlastní
  element o rozměru A4, jsou to prostě prvky `position: absolute` uvnitř ní – žádné triky
  s `<thead>` a `position: fixed`, které tenhle výstup potřeboval, dokud byl jedním nekonečným
  listem. Zapínají se v panelu vlastností (bez vybraného prvku).
- **Tažení (proč pointer events, ne HTML5 drag & drop):** `frontend/src/vystup/tazeni.js`.
  HTML5 tažení neumí průběžně hlásit pozici v milimetrech, nejde u něj kreslit vodicí linky a
  v každém prohlížeči se chová jinak. Pozice se proto počítá sama: poměr px/mm se měří na
  skutečné šířce vykreslené stránky, takže se do něj **automaticky promítne i zoom**. Snap míří
  nejdřív na hrany sousedů (do 2 mm), teprve pak na mřížku po 5 mm. Tažený prvek dostane
  `pointer-events: none`, jinak by `elementsFromPoint` neviděl, co je pod ním, a cíl puštění by
  byl vždycky on sám.
- **Formátovaný text:** `TextPole.jsx` staví na `contentEditable` a `document.execCommand`.
  execCommand je sice zastaralý, ale ve všech prohlížečích funguje, zachová kurzor a výběr a
  nepotřebuje k tomu 150 kB knihovny (ProseMirror/TipTap). Zásada: **dokud se píše, React do
  obsahu nesahá** – přepis `innerHTML` při každém stisku by shodil kurzor na začátek. Do modelu
  se přitom ukládá pročištěná podoba.
- **Sanitizace HTML (bezpečnost):** text z papíru je uživatelský vstup, který se znovu vykresluje
  jako HTML. Čistí se dvakrát: v prohlížeči hned při psaní a vkládání
  (`frontend/src/vystup/sanitizace.js`) a na serveru před uložením
  (`backend/app/nabidkovac/vystup_html.py`). Autorita je server – klientovi se nevěří, protože
  `PUT` na API pošle kdokoli s přihlášením. Whitelist: povolené značky formátování, jediný
  atribut `style` a v něm jen povolené vlastnosti; `url()`, `expression()` ani cizí písma
  neprojdou, `<script>` se zahodí i s obsahem. **Whitelisty na obou stranách musí zůstat
  shodné**, jinak se text po uložení „sám přeformátuje".
- **Obrázky:** nahrávají se zvlášť (`POST /nabidky/{id}/vystup-obrazky`) do
  `vystup_obrazky/<nabidka_id>/`, do konfigurace jde jen cesta. Endpoint pro výdej ověřuje tvar
  cesty i to, že nevede mimo úložiště – cesta totiž chodí od klienta jako součást konfigurace.
  Protože výdej chce token v hlavičce (a `<img src>` ho poslat neumí), stahují se přes `fetch`
  do blob URL, které si `api.js` cachuje podle cesty.
- **Model v2 a starší data:** konfigurace nese `verze: 2`. Původní model (plochý seznam bloků
  v mřížce 12 sloupců) se **nemigruje** – v době přepisu byla v provozu tři rozvržení a Dan
  zvolil čistý start. Konfigurace bez `verze: 2` se ignoruje a vrátí se výchozí předloha; uložený
  záznam v DB zůstane, dokud ho obchodník nepřepíše tlačítkem *Uložit*. Staré pojmenované
  šablony se vracejí s `pouzitelna: false` – nejdou použít, ale jdou smazat (jinak by v databázi
  uvízly bez cesty ven).
- **Whitelist dat v PDF (pojistka „jen zákaznická data"):** jediné místo, kudy se hodnoty do
  výstupu dostanou, je `backend/app/nabidkovac/sablona_katalog.py`. Vyjmenovává **pouze
  zákaznická pole** (`_POLE_PPA`, `_POLE_PS`) a jejich extraktory z `navrhovana_reseni.popis_json`.
  Interní čísla (CAPEX, NPV, IRR, marže, náklady/výnosy investora) tam extraktor **nemají**, takže
  je resolver nikdy nevrátí a editor je ani nenabídne. Navíc `PUT .../vystup/...` odmítne (422)
  jakékoli pole/sloupec, které není ve whitelistu (`platne_klice` / `platne_sloupce`). Formátování
  čísel do češtiny (mezera po tisících, desetinná čárka) dělá server.
  - Vědomě zákazníkovi **neukazujeme rozpad úspory** (`prinos_baterie`,
    `uspora_bez_investice`) – to je obchodní informace („tolik ušetříte i bez investice").
- **Co z peak shavingu je v nabídce:** kromě roku 2026 (platba za rezervovanou kapacitu) i
  **model od roku 2027** (nová tarifní struktura ERÚ – náklad dnes / s baterií, roční úspora,
  rezervovaný příkon před a po, návratnost) a **obchod s elektřinou** (provozní režim a roční
  výnos, jen v režimu *Kombinace*/*Spot*). Jsou to stejná čísla, jaká ukazuje panel v detailu
  nabídky. Bloky „Vaše úspora podle nových tarifů" a „Obchod s elektřinou" se v tisku samy
  skryjí, když pro ně data nejsou (chybí sazby ERÚ, resp. čistý peak shaving) – prázdná pole
  se netisknou.
- **Mřížka papíru (drag & drop editor):** prvek nese `sirka` = kolik z **12 sloupců** zabere
  (`schemas.SIRKA_PLNA`). Prvky se skládají za sebou do řádků – co se do dvanáctky nevejde,
  jde na další řádek (`nabidkovac.js: doRadku`). Řádek je `display: flex`, buňka má
  `flex-grow: sirka`, nevyužitý zbytek řádku drží `.vy-mezera` (bez ní by jedna třetinová
  dlaždice roztáhla řádek na celou šířku). **Proč flex a ne CSS grid:** grid se přes stránky
  láme nespolehlivě, což by rozbilo opakované záhlaví. Starší uložené nabídky `sirka` nemají
  a dostanou celou šířku, takže vypadají jako dřív.
  - Nové druhy prvků: **`udaj`** = jedna dlaždice s hodnotou (nese `klic` do katalogu; whitelist
    ji hlídá stejně jako pole ve skupině – viz `_over_konfiguraci`) a **`zlom`** = ruční zlom
    stránky (`break-after: page`; čárka s popiskem je jen pro obrazovku).
  - V tisku se nesmí rozříznout řádek s víc prvky vedle sebe (`.vy-radek-nelamat`); řádek
    s jediným prvkem se lámat smí, jinak by dlouhý text přeskočil a nechal mezeru.
  - Papír je WYSIWYG – `NabidkaVystup` kreslí jen `viditelny` prvky, i v editoru. Ovládání
    (úchopy, cíle pro puštění) je v tisku skryté třídami v `@media print`.
  - **Paleta je grafická:** dlaždice s hodnotou se v paletě vykreslí tou samou
    komponentou jako na papíře (`NabidkaVystup.DlazdiceNahled`, včetně zvýraznění),
    takže se náhled nemůže rozejít s výsledkem. Strukturní prvky (text, skupina,
    graf, tabulka, zlom) mají miniaturu ze skutečných tříd papíru: obsah má šířku
    textového sloupce A4 a je zmenšený přes `transform: scale(--k)` v `.ed-nahled`.
    Výřez má pevnou výšku a obsah se ustřihne, takže **miniatura musí být plochá** –
    schematický graf má proto jiný poměr stran než ten na papíře (jinak se ustřihly
    zelené sloupce u dna).
  - Tahání je čisté HTML5 drag & drop, žádná knihovna. Matematika vkládání a přesunu je
    v `nabidkovac.js` (`vlozPolozku`, `presunPolozku`), aby šla ověřit bez prohlížeče.
    Pozn.: HTML5 DnD nefunguje na dotyku – editor je myšový.
- **Pojmenované šablony rozvržení:** tabulka `vystup_sablony` (model `VystupSablona`, vzniká přes
  `create_all`) drží rozvržení napříč nabídkami: `GET/POST /nabidkovac/vystup-sablony/{typ}` a
  `DELETE .../{typ}/{id}`. Seznam vrací i **rozvržení jiných nabídek** stejného typu řešení
  (nejnovějších 20), takže jde převzít vizuál i bez uložené šablony. Ukládá se **jen rozvržení**,
  nikdy čísla – ta se vždy dopočítají z řešení té nabídky, do které se šablona použije, takže se
  nemohou přenést data jiného zákazníka. Šablony se nepřenášejí mezi typy řešení (PPA a peak
  shaving mají jiná pole) a stejný název v rámci typu se přepíše.
- **Nové bloky se objeví i ve starých nabídkách:** uložená šablona se při otevření doplní bloky,
  které předloha zná a ona ne (`sablona_katalog.doplnene_bloky`, vkládá je na místo z předlohy).
  Vlastní texty, pořadí ani vypnuté bloky se nepřepisují a uloží se to až na *Uložit* – OZ tedy
  nemusí kvůli novému bloku mačkat *Obnovit výchozí* a přijít o svoje texty.
- **Graf v nabídce = graf z nabídkovače:** který model se kreslí, rozhoduje server
  (`graf_pro_typ` → `s_baterii_kw`, `rp_*_zobrazena_kw`, `popis_*`) podle stejného pravidla jako
  panel: **2027**, jakmile je ekonomika 2027 spočítaná, jinak 2026. Rok mění jak sloupce
  „s baterií" (2027 sráží po měsících, 2026 drží roční strop), tak referenční čáry (2026
  rezervovaná kapacita, 2027 rezervovaný příkon). Dřív měla nabídka natvrdo 2026, takže
  ukazovala jiný graf než obrazovka. **Pozor:** nabídka vždy bere **doporučenou** variantu –
  když si OZ v srovnání rozklikne jinou, do nabídky se to nepřenáší (volba se nikam neukládá).
- **Klíčové soubory:**
  - Backend: `routes.py` (API), `models.py` (tabulky), `schemas.py` (vstupy/výstupy),
    `sablona_katalog.py` (whitelist polí + výchozí předlohy + resolver + formátování),
    `vystup_html.py` (sanitizace formátovaného textu), `vystup_obrazky.py` (úložiště obrázků
    do nabídky), `soubory.py` (ukládání podkladů), `permissions.py` (`vyzaduj_nabidkovac`,
    `vyzaduj_katalog`).
  - Frontend: `pages/Nabidkovac.jsx`, `NabidkovacSekce.jsx`, `NabidkaDetail.jsx`,
    `NabidkaVystupStranka.jsx`, `NabidkovacKatalog.jsx`; `components/DokumentUpload.jsx`,
    `PridatDialog.jsx`; API funkce `api.js`; routy `App.jsx`.
  - Nabídkový výstup má vlastní složky: logika v `frontend/src/vystup/` (`model.js` – data a
    operace nad nimi, `editor.js` – stav a interakce, `tazeni.js` – snap a pointer events,
    `historie.js` – undo/redo, `sanitizace.js` – čištění HTML) a komponenty v
    `frontend/src/components/vystup/` (`Papir.jsx`, `PrvekObsah.jsx`, `TextPole.jsx`,
    `Paleta.jsx`, `Vlastnosti.jsx`, `Lista.jsx`). Styly `styles/vystup.css`.

### Časté potíže / co dělat, když…
- **„Na Nabídkovač nemáš oprávnění" (403)** → uživateli chybí právo `nabidkovac`; přiděl skupině
  nebo jednotlivci v Admin nastavení.
- **Katalog jde jen číst, tlačítka + Technologie/+ Sloupec chybí** → chybí právo `nabidkovac_katalog`
  (jen vedení/admin); dlaždice „⚙ Katalog a výpočty" se pak ani nezobrazí.
- **„Typ souboru se nepodařilo rozpoznat"** → nahráváš něco mimo povolené formáty
  (`.pdf`, `.csv`, `.xlsx`, `.xls`, `.png`, `.jpg`, `.jpeg`). Např. `.docx` neprojde.
- **„Soubor je příliš velký"** → limit je 25 MB na soubor.
- **Dokument se označil špatně** (např. PDF jako faktura, i když je to smlouva) → přepni typ
  rozbalovátkem přímo u řádku dokumentu.
- **„U baterie musí být vyplněný výkon i kapacita"** → u typu Baterie musí být obě čísla kladná.
- **„Pole … není mezi povolenými zákaznickými údaji" (422 při ukládání výstupu)** → do konfigurace
  se dostal klíč mimo whitelist (typicky zastaralá uložená konfigurace); je to záměrná ochrana.
- **PDF vyšlo divně (okraje, zalomení)** → jde o tisk z prohlížeče (`window.print()`); zkontroluj
  nastavení tisku (A4, měřítko 100 %, pozadí grafiky) a `styles/vystup.css`.
- **Nahrané soubory zmizely po redeployi** → soubory jsou na disku v `NABIDKOVAC_UPLOAD_DIR`
  (mimo Git); ověř, že adresář na serveru přežívá nasazení a je zálohovaný.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Nabídka pro zákazníka je jen pro PPA a Peak shaving.** U linie **Prodej** se tlačítko
  „Otevřít nabídku pro zákazníka" nezobrazuje a `sablona_katalog` pro `prodej` nemá whitelist ani
  předlohu (`PODPOROVANE_TYPY = ppa, peak_shaving`) – výstup pro prodej zatím neexistuje.
- **Rozporné upozornění o výpočtu:** seznam nabídek (`NabidkovacSekce.jsx`) i panel „Navržená
  řešení" u Prodeje ukazují text „Výpočet zatím není aktivní", ale PPA a Peak shaving už mají
  funkční kalkulační panely a endpointy. Text vypadá jako zastaralý pro linie PPA/Peak shaving –
  vhodné ověřit/aktualizovat.
- **Zpracování dokumentů se neděje.** Nahrané faktury/CSV se jen uloží (stav *Čeká na zpracování*);
  extrakce z faktury (LLM) a parsování spotřeby se teprve připravují (tabulky `extrahovana_data_faktury`,
  `spotreba_profil` existují jako kostra; profil se plní až přes „zpracuj-profil", viz návod Peak shaving).
- **Šablona výstupu je per nabídka**, ne globální – změna výchozí předlohy v kódu se projeví jen
  u nabídek, které ještě nemají uloženou vlastní konfiguraci (nebo po „Obnovit výchozí" + Uložit).
- **Smazání vlastního sloupce katalogu** nechá hodnoty v `technologie.extra` jako osiřelé klíče –
  neškodí, jen se nezobrazují.
- **Výpočtová nastavení jsou verzovaná** – uložení = nová verze, stará zůstává (dohledatelnost,
  s jakými parametry byla nabídka počítána). Aktuální = nejvyšší verze.
- Návrhová dokumentace: `docs/SPEC-nabidkovac.md`; PDF výstup též v paměti projektu „Nabídkový výstup PDF".

## Odkazy
- Kód backend: `backend/app/nabidkovac/` · frontend: `frontend/src/pages/Nabidkovac*.jsx`,
  `NabidkaDetail.jsx`, `NabidkaVystupStranka.jsx`, `frontend/src/components/NabidkaVystup*.jsx`,
  `DokumentUpload.jsx`
- Práva: `backend/app/auth/permissions.py` (klíče `nabidkovac`, `nabidkovac_katalog`)
- Kalkulátory (samostatné návody): [nabidkovac-peak-shaving.md](nabidkovac-peak-shaving.md),
  [nabidkovac-ppa-fve.md](nabidkovac-ppa-fve.md)
- Spec: `docs/SPEC-nabidkovac.md` · Znalostní báze: [README](../README.md)
