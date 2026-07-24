# Nabídkovač – kalkulátor PPA pro FVE

> **Kde to je:** uvnitř **Nabídkovače**, typ nabídky **`ppa`** · **Adresa (routa):** seznam `/nabidkovac/ppa`, konkrétní nabídka `/nabidkovac/nabidka/<id>` · **Kdo smí:** kdo má právo `nabidkovac` (OZ); manažerské defaulty výpočtu edituje jen `nabidkovac_katalog` (vedení/admin)
> **Kód:** frontend `frontend/src/components/PpaPanel.jsx` + `GrafVyrobaSpotreba.jsx`, backend `backend/app/nabidkovac/ppa_fve.py` (výpočetní jádro) + `routes.py` (API)

Kalkulátor ekonomiky **PPA (Power Purchase Agreement) pro fotovoltaiku**. Model: Greensie
(investor) postaví a **vlastní** FVE na střeše/pozemku klienta, klient **nic neinvestuje** a po
dobu kontraktu odebírá vyrobenou elektřinu za sjednanou (indexovanou) **PPA cenu**. Appka počítá
dvě ekonomiky nad stejnou fyzikou – **klientovi** úsporu (dnes vs. s PPA), **investorovi**
návratnost (payback / IRR / NPV). Výrobu FVE si appka **sama simuluje** (nenahrává se), velikost
FVE **navrhuje sama**. Ceny jsou **bez DPH**, výpočet je deterministický.

> 📸 SCREENSHOT: detail nabídky typu `ppa` – panel „PPA pro FVE – výpočet" s vyplněnými vstupy a výsledkem

---

## 🧑 Pro uživatele

### K čemu to slouží
PPA je nabídka, kde **zákazník neplatí za elektrárnu** – tu postaví a vlastní Greensie. Zákazník
jen odebírá vyrobenou elektřinu za **nižší cenu, než platí dnes svému dodavateli**. Kalkulátor
z nahraného **profilu spotřeby** spočítá:

- **pohled klienta** – kolik ročně a celkem ušetří (rozdíl mezi dnešní cenou a PPA cenou na té
  části spotřeby, kterou pokryje FVE),
- **pohled investora (Greensie)** – jestli se stavba FVE vyplatí (návratnost, IRR, NPV).

Výrobu FVE **nenahráváš** – appka si ji simuluje z výkonu, lokality a orientace panelů. **Velikost
FVE (kWp) taky nezadáváš** – appka vyzkouší řadu velikostí a navrhne tu s nejlepší ekonomikou
(volitelně můžeš omezit střechou nebo zadat výkon napevno).

### Rozvržení obrazovky
Panel PPA je spodní část detailu nabídky typu `ppa` (nad ním je karta **Zákazník**, **Podklady**
a tlačítko **Nabídka pro zákazníka**). Shora dolů:

1. **1. Profil spotřeby** – stav načtení profilu + tlačítka „Načíst profil" pro nahrané soubory.
2. **2. Parametry FVE a PPA** – mřížka vstupních polí (velikost, orientace, ceny, kontrakt, CAPEX…).
3. **Zaškrtávátko „Účtovat přetok do sítě"** – po zapnutí přibude pole „Cena přebytku".
4. **Tlačítko „Spočítat PPA"** – spustí výpočet.
5. **Výsledek** (po výpočtu): navržená velikost + **% pokrytí spotřeby z FVE**, dlaždice ekonomiky
   investora (návratnost / IRR / NPV / kum. úspora klienta), tabulka **Srovnání velikostí**,
   měsíční graf **výroba vs. spotřeba**, tabulka **po letech** a případná **upozornění**.

> 📸 SCREENSHOT: celý panel PPA shora dolů – profil, parametry, výsledek s grafem a tabulkami

### Jak založit a spočítat PPA (krok za krokem)
1. V Nabídkovači otevři sekci **PPA pro FVE** a založ/otevři nabídku (typ `ppa`).
2. V kartě **Zákazník** vyplň název a ideálně **GPS** (zpřesní simulaci výroby; bez GPS se použije
   střed ČR 49,8°).
3. V kartě **Podklady** nahraj soubor s **15minutovým profilem spotřeby** (XLS/CSV z portálu
   distributora – činný výkon kW).
4. V panelu PPA klikni u nahraného souboru na **„Načíst profil: …"**. Objeví se počet intervalů,
   rozsah dat a **roční spotřeba (MWh)**.
5. Vyplň **Parametry FVE a PPA** (viz tabulka níže). Povinné pro výpočet jsou **PPA cena**,
   **silová cena dodavatele** a **délka kontraktu** – bez nich zůstane tlačítko „Spočítat PPA"
   neaktivní.
6. Klikni **Spočítat PPA**. Výsledek se uloží a při příštím otevření nabídky se vstupy **předvyplní
   z posledního výpočtu**, takže jde libovolně **přepočítávat**.

> ⚠️ Bez načteného profilu spotřeby nejde počítat (příčinou je, že samospotřeba = souběh výroby
> a spotřeby po 15 minutách). Panel na to upozorní.

### Ovládací prvky – políčko po políčku
Legenda „kdo vidí": **(OZ)** = kdo má právo `nabidkovac` · **(admin)** = editace defaultů pod
`nabidkovac_katalog`. Všechny vstupy panelu vidí a mění **OZ**; admin nastavuje jen výchozí hodnoty
(viz „Pro admina").

| Prvek | Co to je | Co ovlivní | Kdo vidí |
|---|---|---|---|
| **Načíst profil: `<soubor>`** | Naparsuje nahraný XLS/CSV do 15min profilu spotřeby | Bez něj nejde počítat; z profilu se bere spotřeba i roční MWh | OZ |
| **Max. výkon dle střechy (kWp)** | Volitelný **strop** pro automatický návrh velikosti | Žádná navržená velikost ho nepřekročí (tvrdý limit) | OZ |
| **Výkon napevno (kWp)** | Volitelný ruční výkon FVE | Když vyplníš, appka **nenavrhuje** a počítá jen tuto velikost | OZ |
| **Sklon panelů (°)** | Sklon roviny panelů (0 = rovina, 90 = svisle) | Korekce ročního výnosu (optimum ~35°) | OZ |
| **Azimut (°, 0 = jih)** | Natočení panelů (0 = jih, ±90 = V/Z, 180 = sever) | Korekce výnosu (jih nejvyšší) | OZ |
| **PPA cena rok 1 (Kč/MWh)** | Nabízená cena, za kterou klient odebírá z FVE | Úsporu klienta i výnos investora; eskaluje se po letech | OZ |
| **Silová cena dodavatele (Kč/MWh)** | Dnešní **silová** složka ceny klienta (bez distribuce) | Referenční cena „bez PPA"; základ úspory | OZ |
| **Vyhnutelné regulované (Kč/MWh)** | Regulované platby, kterým se samospotřeba vyhne | Přičítá se k silové ceně → vyhnutelná cena klienta; prázdné = z nastavení (~260) | OZ |
| **Délka kontraktu (roky)** | Doba PPA smlouvy | Počet let ve výpočtu úspory i návratnosti | OZ |
| **Náklady na FVE** | Přepínač režimu CAPEX: *Zjednodušeně (cena za kWp)* / *Skutečné (komponenty z katalogu)* | Jak se spočítá investice (CAPEX) | OZ |
| **Max. rez. výkon dodávky (kW)** | Strop přetoku do sítě ze smlouvy o připojení | Přebytek nad strop se **ořízne** (0 Kč); prázdné = neomezeno | OZ |
| **Index PPA (%/rok)** | Roční eskalace PPA ceny | Růst PPA ceny po letech; prázdné = z nastavení (~0,03) | OZ |
| **Index dodavatele (%/rok)** | Roční eskalace silové ceny dodavatele | Růst ceny „bez PPA"; prázdné = stejný jako index PPA | OZ |
| **Účtovat přetok do sítě** | Zaškrtávátko – prodává se přebytek? | Zapnuto → přetok je **výnos investora**; posune optimum k větší FVE | OZ |
| **Cena přebytku (Kč/MWh)** | Výkupní cena přetoku (jen když je účtování zapnuté) | Výnos investora z prodeje do sítě | OZ |
| **Spočítat PPA** | Spustí výpočet | Uloží nové řešení a vykreslí výsledek | OZ |
| **Řádek v „Srovnání velikostí"** | Klikací řádek s jinou velikostí FVE | **Překreslí celý detail** (čísla, graf, tabulka let) pro danou velikost | OZ |

> 📸 SCREENSHOT: mřížka parametrů FVE a PPA s popisky polí

### Význam výstupů
Po výpočtu je nahoře **navržená FVE** (velikost v kWp) s odznakem, jak vznikla:
- **„ekonomický návrh"** – velikost navrhla appka podle nejlepší ekonomiky,
- **„ruční výkon"** – zadal jsi výkon napevno,
- **„alternativa – návrh je X kWp"** – právě si prohlížíš jinou velikost než navrženou.

| Výstup | Co znamená |
|---|---|
| **% pokrytí spotřeby z FVE** (velké číslo) | Jaký podíl roční spotřeby klienta reálně pokryje elektřina z FVE (samospotřeba / roční spotřeba). **Hlavní číslo nabídky.** |
| **Roční výroba** | Kolik FVE za rok vyrobí (+ měrný výnos kWh/kWp a faktor orientace) |
| **Roční spotřeba** | Spotřeba klienta z profilu (+ poměr výroba/spotřeba) |
| **Samospotřeba** | Kolik výroby klient rovnou spotřebuje (+ % z výroby) |
| **Přetok do sítě / ořez** | Přebytek do sítě; ořez = co se nevešlo do rez. výkonu dodávky (propadá) |
| **Investice (CAPEX)** | Náklad Greensie na postavení FVE |
| **Vyhnutelná cena klienta** | Silová složka + vyhnutelné regulované platby = cena, které se samospotřebou vyhne |
| **Návratnost** | Za kolik let se investorovi vrátí CAPEX (kumulativní cash-flow ≥ 0) |
| **IRR** | Vnitřní výnosové procento investice |
| **NPV** | Čistá současná hodnota při diskontní sazbě (kladné = vyplatí se) |
| **Kum. úspora klienta** | Kolik klient ušetří celkem za dobu kontraktu |

> ⚠️ Když je **NPV záporné**, panel červeně upozorní, že se PPA při daných parametrech investorovi
> nevyplatí (zvaž vyšší PPA cenu, delší kontrakt nebo levnější CAPEX).

### Grafy a tabulky
- **Srovnání velikostí** – tabulka kandidátních velikostí (pokrytí, samospotřeba, výroba, CAPEX,
  návratnost, NPV). Navržená = nejlepší ekonomika. **Klik na řádek** překreslí celý detail pro tu
  velikost (řádek `◄` = právě zobrazená).
- **Výroba FVE vs. spotřeba (měsíčně, rok 1)** – SVG graf, dva sloupce na měsíc: **spotřeba**
  (samospotřeba z FVE + dokup ze sítě) a **výroba** (samospotřeba + přetok do sítě + ořez).
  Ukáže, jak dobře se výroba a spotřeba potkávají v čase.
- **Úspora a návratnost po letech** – řádek na každý rok kontraktu: výroba, samospotřeba, cena PPA,
  vyhnutelná cena, úspora klienta (roční i kumulativní), cash-flow investora (roční i kumulativní).
  Řádek `◄` = rok návratnosti.

> 📸 SCREENSHOT: měsíční graf výroba vs. spotřeba + tabulka po letech se zvýrazněným rokem návratnosti

### Jak na…
- **Rychlá orientační nabídka:** nahraj profil → PPA cena, silová cena, délka → *Spočítat PPA*.
  Velikost i vše ostatní navrhne appka.
- **Omezit FVE střechou:** vyplň **Max. výkon dle střechy (kWp)** – návrh nikdy nepřekročí strop.
- **Zadat výkon napevno:** vyplň **Výkon napevno (kWp)** – appka spočítá jen tu velikost.
- **Prodávat přebytek:** zaškrtni **Účtovat přetok do sítě** a vyplň **Cena přebytku**. Optimum se
  posune k větší FVE (přebytek se investorovi vyplatí).
- **Porovnat víc velikostí:** ve **Srovnání velikostí** klikej na řádky – detail i graf se překreslí.
- **Přesnější simulace výroby:** vyplň **GPS** zákazníka (karta Zákazník) a reálný **sklon/azimut**.

---

## 🛠 Pro admina / provoz

### Práva – kdo co vidí a smí
- Celý panel PPA a výpočet používá kdokoli s právem **`nabidkovac`** (strážce `vyzaduj_nabidkovac`).
- **Výchozí parametry výpočtu** (cena/kWp, indexy, O&M, diskont…) edituje jen právo
  **`nabidkovac_katalog`** (vedení/admin) v **Katalogu a výpočtech** (`/nabidkovac/katalog`).
  „OZ" = skupina v Admin nastavení s právem `nabidkovac`. Viz `backend/app/nabidkovac/permissions.py`.

### Parametry výpočtu a jejich zdroj
Priorita hodnot: **vstup od OZ u nabídky** → **manažerské nastavení** (`vypoctova_nastaveni.parametry`,
JSONB, verzované) → **kódový default** (`ppa_fve.py`). Manažerské klíče se editují v adminu
(`NabidkovacKatalog.jsx`, blok „PPA pro FVE – náklady a defaulty"); uložení = **nová verze**
(staré zůstávají).

| Klíč (`vypoctova_nastaveni.parametry`) | Význam | Default |
|---|---|---|
| `ppa_cena_fve_kc_kwp` | Cena za kWp (zjednodušený CAPEX) | 25 000 |
| `ppa_ostatni_naklady_kc_kwp` | BOS (montáž/konstrukce) pro komponentový CAPEX | 0 |
| `ppa_merny_vynos_kwh_kwp` | Měrný výnos FVE (PVGIS v5.3, střed ČR) | 1055; **pojistka 100–2000** |
| `ppa_index_ceny_rocni` | Roční eskalace PPA ceny | 0,03 |
| `ppa_index_dodavatel_rocni` | Roční eskalace silové ceny dodavatele | = index PPA |
| `ppa_vyhnutelne_regulovane_kc_mwh` | Vyhnutelné regulované složky | 260 |
| `ppa_index_regulovane_rocni` | Eskalace regulovaných složek | 0 |
| `ppa_poze_kc_mwh` | POZE | 0 (2026) |
| `ppa_index_prebytek_rocni` | Eskalace ceny přebytku | 0 |
| `ppa_degradace_rocni` | Degradace panelů | 0,005 |
| `ppa_degradace_rok1` | LID – pokles 1. roku | 0,02 (PERC); 0,01 TOPCon |
| `ppa_oam_kc_kwp_rok` | Provozní náklady investora (vč. pojištění, revizí) | 350 |
| `ppa_diskontni_sazba` | Diskont pro NPV/IRR (WACC 6–9 %) | 0,075 |
| `ppa_vymena_stridace_rok` | Rok jednorázové výměny střídače (0 = vypnuto) | 0 |
| `ppa_vymena_stridace_kc_kwp` | Cena výměny střídače | 0 |

### Jak výpočet funguje (srozumitelně; detail v technickém souhrnu)
1. **Simulace výroby.** Roční výnos = `kWp × měrný_výnos × korekce_orientace(azimut, sklon)`.
   Rozpustí se **po měsících** (kalibrovaná tabulka PVGIS v5.3), měsíc na dny a den na 15min
   intervaly **clear-sky zvonovinou** ze solární geometrie. Ošetřen letní čas (v létě solární
   poledne ~13:00 lokálního času). Výroba je lineární v kWp → simuluje se jednou pro 1 kWp a škáluje.
2. **Spárování se spotřebou** (interval po intervalu): nejdřív **samospotřeba** `min(výroba, spotřeba)`,
   pak **přetok** do sítě omezený rezervovaným výkonem dodávky, zbytek **ořez** (0 Kč), a **dokup**
   toho, co FVE nepokryje.
3. **Ekonomika klienta:** `úspora = samospotřeba × (vyhnutelná cena − PPA cena)`, kde vyhnutelná
   cena = silová složka + vyhnutelné regulované platby. Ceny se eskalují geometricky po letech.
4. **Ekonomika investora:** `cash-flow = výnos z PPA (+ prodej přetoku) − O&M − výměna střídače`;
   z toho **payback** (kum. CF ≥ 0), **NPV** (diskont) a **IRR** (bisekce).
5. **Návrh velikosti = ekonomický sweep:** vygeneruje ~30 kandidátních velikostí (max
   `3× roční spotřeba`, tvrdý strop `max_kwp`), pro každou spočítá celou ekonomiku a vybere
   **nejvyšší NPV / nejkratší návratnost**; vrací i 2.–4. variantu. Respektuje prodej přebytku
   (bez prodeje → menší FVE).

**Degradace:** výroba v roce `t` = `V_nom × (1 − LID) × (1 − degradace)^(t−1)` – pokles 1. roku
(LID) je zahrnutý už v roce 1 a nese se celým kontraktem; headline metriky i graf ukazují rok 1
včetně LID.

**CAPEX – dva režimy:** `cena_kwp` (kWp × cena za kWp) nebo `komponenty` (nejlevnější panel +
invertor z katalogu `technologie` + BOS). Komponentový režim vyžaduje naplněný katalog.

### Datový model
**Bez nové tabulky a bez migrace** – výroba je deterministická, nepersistuje se.
- **`spotreba_profil`** – 15min profil spotřeby (`cas`, `hodnota_kw`). PPA čte `hodnota_kw` a
  přepočítává na energii `kWh = kW × interval_h` (sdíleno s peak shavingem).
- **`navrhovana_reseni`** – výstup výpočtu do `popis_json` (`typ_reseni = ppa`). Každý výpočet
  přidá nový řádek; panel načítá poslední. `popis_json` = `vstup` / `vysledek` / `varianty`
  (kompletní, aby šel detail přepínat) / `upozorneni`.
- **`vypoctova_nastaveni.parametry`** (JSONB, verzované) – manažerské defaulty PPA (tabulka výše).

### API (`backend/app/nabidkovac/routes.py`, prefix `/nabidkovac`)
| Metoda / cesta | Právo | Popis |
|---|---|---|
| `GET /nabidky/{id}/ppa/profil-souhrn` | `nabidkovac` | Počet / rozsah / roční spotřeba (MWh) profilu |
| `POST /nabidky/{id}/ppa/vypocet` | `nabidkovac` | Spustí výpočet, uloží do `navrhovana_reseni` |
| `POST /dokumenty/{id}/zpracuj-profil` | `nabidkovac` | Naparsuje XLS/CSV → `spotreba_profil` (sdíleno s peak shavingem) |

Vstup výpočtu (`PpaVstup` v `schemas.py`): povinné `cena_ppa_kc_mwh`, `cena_silova_kc_mwh`,
`delka_kontraktu_roky`; volitelné `sklon_st` (35), `azimut_st` (0), `instalovany_vykon_kwp`,
`max_kwp`, `rezim_capex`, `prebytek_uctovat` + `prebytek_cena_kc_mwh`, `rezervovany_vykon_dodavky_kw`,
indexy a degradace (prázdné = default). Route validuje **pokrytí roku** (profil delší než rok
ořízne na posledních 12 měsíců; kratší než ~350 dní / s dírami → HTTP 422).

### Klíčové soubory
```
backend/app/nabidkovac/
  ppa_fve.py   – VÝPOČETNÍ JÁDRO (simulace výroby, spárování, ekonomika, ekonomický výběr velikosti, CAPEX)
  routes.py    – API (…/ppa/vypocet, …/ppa/profil-souhrn) + doplnění defaultů, validace, upozornění
  schemas.py   – PpaVstup
  permissions.py – vyzaduj_nabidkovac / vyzaduj_nabidkovac_katalog
frontend/src/
  components/PpaPanel.jsx           – OZ panel výpočtu + výsledek + srovnání velikostí
  components/GrafVyrobaSpotreba.jsx – SVG graf výroba vs. spotřeba (bez knihovny)
  pages/NabidkaDetail.jsx           – pro typ=ppa renderuje PpaPanel
  pages/NabidkovacKatalog.jsx       – admin PPA nastavení (blok PPA_POLE)
  api.js                            – ppaVypocet, ppaProfilSouhrn, profilZpracuj
```

### Časté potíže / co dělat, když…
- **Tlačítko „Spočítat PPA" je šedé** → chybí načtený profil, nebo některé z povinných polí (PPA
  cena, silová cena, délka kontraktu).
- **HTTP 422 „Nabídka nemá nahraný 15min profil"** → nahraj a **načti** profil v kartě Podklady.
- **422 kvůli profilu** (kratší než rok / díry / chybějící měsíce) → profil nepokrývá celý rok;
  nahraj úplnější export.
- **Upozornění „Měrný výnos mimo rozsah"** → v adminu je nesmyslná hodnota `ppa_merny_vynos_kwh_kwp`
  (pojistka 100–2000), použil se default 1055 – oprav v Katalogu a výpočtech.
- **Komponentový CAPEX = 0 / chyba** → v katalogu `technologie` chybí panely nebo invertory s cenou;
  doplň je, nebo přepni na režim „cena za kWp".
- **Řádek srovnání nejde rozkliknout** → jde o **starší uložený výsledek** bez plných dat variant;
  detail se přepíná jen u nových výpočtů (přepočítej).
- **NPV záporné / „nevyplatí se"** → parametry nejsou pro investora ziskové; zvyš PPA cenu, prodluž
  kontrakt, sniž CAPEX nebo zapni prodej přebytku.

---

## Poznámky a úskalí (k ověření / nezřejmé)
- **Profil se ukládá jako výkon (kW), ne energie:** PPA přepočítává `kWh = kW × interval_h`. Import
  je stejný jako u peak shavingu (činný výkon), ne samostatný kWh sloupec.
- **Konstantní spotřeba přes roky** kontraktu je předpoklad v1 (růst/pokles se nezadává). Výnos
  investora je úměrný skutečné samospotřebě – reálné smlouvy to řeší minimálním odběrem / take-or-pay
  (upozornění je vždy ve výstupu).
- **Simulace výroby je clear-sky model** (bez proměnlivosti počasí) – na měsíční/roční samospotřebu
  stačí, na 15min špičky hůř. Regionalizace dle GPS zatím není (fallback střed ČR 49,8°); GPS
  ovlivní jen solární geometrii, ne měrný výnos.
- **„Cena dodavatele" = jen silová složka** (distribuce se z porovnání vypouští, platí ji klient tak
  jako tak); k ní se přičtou **vyhnutelné regulované platby**. Daň z elektřiny se nesrovnává
  (symetrická – u výroben > 30 kW jí PPA dodávka podléhá také, plus registrační povinnost investora).
- **Cena za kWp (25 000) a O&M (350) jsou orientační defaulty** ke kalibraci – ověř reálné hodnoty
  v manažerském nastavení před ostrou nabídkou.
- **Dopočet PPA ceny z marže** (`koeficient_zisku`) a **kombinace PPA + baterie** zatím nejsou
  implementované – cenu vždy zadává OZ.
- Komponenta grafu je `GrafVyrobaSpotreba.jsx` (vlastní SVG bez knihovny). `GrafOdberu.jsx` patří
  peak shavingu, ne PPA.

## Odkazy
- Kód: backend `backend/app/nabidkovac/ppa_fve.py`, `routes.py`, `schemas.py` · frontend
  `frontend/src/components/PpaPanel.jsx`, `GrafVyrobaSpotreba.jsx`, `pages/NabidkovacKatalog.jsx`
- Technický souhrn (fakta, API, otevřené body): [`docs/moduly/ppa-fve.md`](../../moduly/ppa-fve.md)
- Metodika a vzorce: [`docs/METODIKA-ppa-fve.md`](../../METODIKA-ppa-fve.md)
- Nadřazený modul: [Nabídkovač](nabidkovac.md) (společné podklady, práva, katalog, PDF výstup)
- Paměť projektu: Nabídkový výstup PDF (`MEMORY.md` → nabidkovy-vystup-pdf)
