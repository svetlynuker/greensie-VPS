# Nabídkovač

> **Dlaždice:** `nabidkovac` · **Adresy (routy):** `/nabidkovac` (rozcestník typů) · `/nabidkovac/:typ` (seznam nabídek podsekce) · `/nabidkovac/nabidka/:id` (detail nabídky) · `/nabidkovac/nabidka/:id/vystup/:typ` (editor + náhled nabídky pro zákazníka) · `/nabidkovac/katalog` (katalog a výpočtová nastavení)
> **Kdo smí otevřít:** kdokoli s právem `nabidkovac` (dlaždici vidí všichni, bez práva je zamčená 🔒); katalog a výpočty jen s právem `nabidkovac_katalog` (vedení/admin)
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

### Tok práce (od založení po PDF)
1. **Vyber podsekci** na rozcestníku (PPA / Prodej / Peak shaving).
2. **Založ nabídku** tlačítkem „+ Nová nabídka" – vznikne prázdný záznam ve stavu *Koncept* a
   appka tě rovnou přepne do jejího detailu.
3. **Vyplň zákazníka** (název, adresa, případně GPS pro budoucí PVGIS) a ulož.
4. **Nahraj podklady** – fakturu (PDF) a/nebo diagram spotřeby (CSV/XLSX). Prvním nahraným
   dokumentem se koncept posune do stavu *Data nahrána*.
5. **Spočítej řešení** – u PPA a Peak shavingu v panelu v detailu nabídky (viz samostatné návody).
6. **Sestav nabídku pro zákazníka** – tlačítko „Otevřít nabídku pro zákazníka" (jen u PPA a
   Peak shavingu): v editoru zapneš/vypneš bloky, upravíš texty a vybereš zobrazená pole.
7. **Ulož do PDF** – tlačítko „Uložit do PDF" otevře tiskový dialog prohlížeče (tisk / uložit jako PDF).

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

**C) Detail nabídky `/nabidkovac/nabidka/:id`** – shora: odkaz zpět, hlavička s názvem zákazníka
a štítky (linie + stav), karta **Zákazník** (formulář), karta **Podklady** (nahrávání dokumentů),
u PPA/Peak shavingu karta **Nabídka pro zákazníka** (tlačítko do editoru výstupu) a nakonec panel
**Navržená řešení** (u PPA/Peak shavingu kalkulátor, u Prodeje zatím jen upozornění).

**D) Nabídka pro zákazníka `/nabidkovac/nabidka/:id/vystup/:typ`** – nahoře lišta s tlačítky
(Zpět, Obnovit výchozí, Uložit, Uložit do PDF), pod ní vlevo **editor bloků**, vpravo **živý
náhled** tiskové A4 stránky.

> 📸 SCREENSHOT: detail nabídky – karty Zákazník, Podklady, Nabídka pro zákazníka
> 📸 SCREENSHOT: obrazovka „Nabídka pro zákazníka" – vlevo editor bloků, vpravo náhled

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

#### Detail nabídky – karta Zákazník
| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **Název zákazníka** | Jméno/firma zákazníka (zobrazí se i v hlavičce PDF) | vše |
| **Adresa** | Adresa zákazníka (zobrazí se v hlavičce PDF) | vše |
| **GPS šířka (lat) / délka (lng)** | Souřadnice pro budoucí PVGIS; zatím jen uložení | vše |
| **Uložit** | Uloží změny zákazníka | vše |
| **Smazat nabídku** | Smaže celou nabídku včetně nahraných souborů (s potvrzením) | vše |

#### Detail nabídky – karta Podklady (nahrávání dokumentů)
| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **Typ dokumentu** | Výběr: *Faktura (PDF)* / *Spotřeba (CSV/XLSX)* / *Jiný dokument* | vše |
| **Přetáhni sem soubor / klikni** | Nahraje soubor (drag & drop nebo výběr); povolené přípony dle typu, max 25 MB | vše |
| **Řádek dokumentu** | Ukáže název, velikost a stav zpracování | vše |
| **Smazat (u dokumentu)** | Smaže dokument (soubor i záznam) | vše |
| **Otevřít nabídku pro zákazníka** | Jen u PPA/Peak shavingu – přejde do editoru výstupu | vše |

#### Nabídka pro zákazníka – lišta a editor
| Prvek | Kde | Co dělá | Kdo vidí |
|---|---|---|---|
| **← Zpět na nabídku** | lišta | Návrat do detailu nabídky | vše |
| **Obnovit výchozí** | lišta | Načte kódovou výchozí předlohu (přepíše se až po Uložit; ptá se na potvrzení) | vše |
| **Uložit** | lišta | Uloží šablonu výstupu této nabídky (per typ řešení) | vše |
| **Uložit do PDF** | lišta | Otevře tiskový dialog prohlížeče (tisk / uložit jako PDF) | vše |
| **Zaškrtávátko u bloku** | editor | Zapne/vypne blok ve výstupu (skrytý blok je ztlumený) | vše |
| **↑ / ↓ (u bloku)** | editor | Změní pořadí bloků | vše |
| **Nadpis bloku** | editor | Upraví nadpis (u hlavičky = titulek nabídky, u grafu = nadpis grafu) | vše |
| **Text bloku** | editor | Upraví text (hlavička = podnadpis, text = odstavec, údaje = úvodní věta) | vše |
| **Přidat/odebrat údaj + ↑↓** | editor (blok „Údaje") | Vybere zobrazená zákaznická pole a jejich pořadí | vše |
| **Sloupce tabulky** | editor (blok „Tabulka") | Zaškrtne sloupce roční tabulky | vše |

> 📸 SCREENSHOT: editor bloků – zaškrtávátka, šipky pořadí, výběr zobrazených údajů

### Práce s katalogem a vlastními sloupci
Katalog technologií je **společný** (jeden pro celý Nabídkovač) a najdeš ho přes **⚙ Katalog
a výpočty** (`/nabidkovac/katalog`). **Prohlížet ho může každý s právem `nabidkovac`, editovat
jen s právem `nabidkovac_katalog`.** Obrazovka má tři části: Katalog technologií, Výpočtová
nastavení a Sazby distributorů.

| Prvek | Co dělá | Kdo vidí |
|---|---|---|
| **+ Technologie** | Otevře dialog nové položky katalogu | katalog |
| **+ Sloupec** | Přidá vlastní sloupec katalogu (např. „Záruka"), text nebo číslo | katalog |
| **Řádek technologie** | Klik otevře editaci | katalog |
| **Smazat (u technologie / sloupce)** | Smaže položku / definici sloupce | katalog |
| **Vlastní sloupec (štítek)** | Klik na název upraví sloupec, × ho smaže (uložené hodnoty osiřejí, neškodí) | katalog |

**Dialog technologie** obsahuje: *Typ* (FVE panel / Invertor / Baterie / Jiná), *Název*, *Model*,
*Výkon (kW)*, *Kapacita (kWh)*, *Cena (Kč)*, *Účinnost (0–1)*, přepínač *Dostupná v katalogu* a
vstupy pro případné vlastní sloupce. **U typu Baterie musí být vyplněný výkon i kapacita** (obojí
kladné) – bez nich nelze počítat peak shaving.

> Výpočtová nastavení (verze, PPA/PS defaulty) a Sazby distributorů slouží kalkulátorům a jsou
> popsané v návodech [nabidkovac-ppa-fve.md](nabidkovac-ppa-fve.md) a
> [nabidkovac-peak-shaving.md](nabidkovac-peak-shaving.md).

### Editor bloků nabídkového výstupu
Nabídka pro zákazníka se skládá z **bloků**. Každý blok má typ (druh), zapnutí (`viditelný`),
nadpis, text a případně výběr polí. Druhy bloků:

| Druh | Co zobrazí |
|---|---|
| **Hlavička** | Místo pro logo, titulek nabídky, podnadpis a příjemce (jméno, adresa, datum) |
| **Text** | Volný odstavec (např. úvod „Co vám nabízíme", závěr) |
| **Údaje** | Karty s vybranými zákaznickými hodnotami (např. velikost elektrárny, úspora) |
| **Graf** | Graf dle typu řešení (PPA: výroba vs. spotřeba; Peak shaving: měsíční špičky) |
| **Tabulka** | Roční tabulka (jen zákaznické sloupce) |

Nová nabídka startuje z **kódové výchozí předlohy** (jiné bloky pro PPA a jiné pro Peak shaving).
Jakmile klikneš **Uložit**, uloží se úprava jako šablona konkrétní nabídky. Není žádná globální
master šablona – **každá nabídka má vlastní**. V editoru jsou **dostupná jen zákaznická pole**;
interní čísla se nenabízejí.

> V editoru se prázdná pole (bez spočítané hodnoty) ukazují se zástupným „—", ať je vidět, co
> se doplní po výpočtu. **V tisku/PDF se pole a bloky bez dat automaticky skryjí.**

### Jak na…
- **Založit novou nabídku:** rozcestník → vyber linii → *+ Nová nabídka* → vyplň zákazníka → *Uložit*.
- **Nahrát fakturu / diagram spotřeby:** detail nabídky → karta *Podklady* → vyber typ → přetáhni
  soubor. (Soubor se zatím jen uloží, automatické čtení se připravuje.)
- **Sestavit nabídku do PDF:** detail (PPA/Peak shaving) → *Otevřít nabídku pro zákazníka* →
  zapni/vypni bloky, uprav texty a vyber údaje → *Uložit* → *Uložit do PDF* (dialog tisku prohlížeče).
- **Vrátit se k výchozí předloze:** v editoru výstupu *Obnovit výchozí* (přepíše se až po *Uložit*).
- **Přidat technologii do katalogu:** *Katalog a výpočty* → *+ Technologie* → vyplň a *Uložit*.
- **Přidat vlastní sloupec katalogu:** *Katalog a výpočty* → *+ Sloupec* → název + typ (text/číslo).
- **Smazat nabídku:** detail nabídky → *Smazat nabídku* (smaže i nahrané soubory).

---

## 🛠 Pro admina / provoz

### Práva — kdo co vidí a smí
- Dlaždici **Nabídkovač** vidí v rozcestníku **všichni**, ale bez práva `nabidkovac` je **zamčená** (🔒).
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
    dvojici; `konfigurace_json` = seznam bloků.
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
  - `POST /nabidky/{id}/dokumenty` — nahraje dokument (multipart: `typ`, `soubor`); posune
    koncept na *data_nahrana*.
  - `DELETE /dokumenty/{id}` — smaže dokument (soubor + záznam).
  - `GET/POST /technologie`, `PUT/DELETE /technologie/{id}` — katalog (čtení: `nabidkovac`; zápis: `nabidkovac_katalog`).
  - `GET/POST /katalog-sloupce`, `PUT/DELETE /katalog-sloupce/{id}` — vlastní sloupce katalogu.
  - `GET /nabidky/{id}/vystup/{typ_reseni}?vychozi=` — podklad pro editor i náhled (konfigurace,
    katalog polí, resolvnuté zákaznické hodnoty, tabulka, graf). `vychozi=1` vrátí kódovou předlohu.
  - `PUT /nabidky/{id}/vystup/{typ_reseni}` — uloží šablonu výstupu (s validací whitelistu).
  - Výpočtové endpointy (`.../peak-shaving/*`, `.../ppa/*`), `vypoctova-nastaveni`, `sazby` —
    patří kalkulátorům (viz jejich návody).
- **PDF / tisk (jak vzniká):** žádné serverové generování. Komponenta `NabidkaVystup.jsx`
  vykreslí nabídku z konfigurace bloků + resolvnutých hodnot **dvakrát** – jako živý náhled a
  jako tisková A4 stránka. Tlačítko „Uložit do PDF" spustí `window.print()`; layout řeší
  `frontend/src/styles/vystup.css`. V tisku se skrývají prázdné bloky a pole bez hodnoty.
- **Whitelist dat v PDF (pojistka „jen zákaznická data"):** jediné místo, kudy se hodnoty do
  výstupu dostanou, je `backend/app/nabidkovac/sablona_katalog.py`. Vyjmenovává **pouze
  zákaznická pole** (`_POLE_PPA`, `_POLE_PS`) a jejich extraktory z `navrhovana_reseni.popis_json`.
  Interní čísla (CAPEX, NPV, IRR, marže, náklady/výnosy investora) tam extraktor **nemají**, takže
  je resolver nikdy nevrátí a editor je ani nenabídne. Navíc `PUT .../vystup/...` odmítne (422)
  jakékoli pole/sloupec, které není ve whitelistu (`platne_klice` / `platne_sloupce`). Formátování
  čísel do češtiny (mezera po tisících, desetinná čárka) dělá server.
- **Klíčové soubory:**
  - Backend: `routes.py` (API), `models.py` (tabulky), `schemas.py` (vstupy/výstupy),
    `sablona_katalog.py` (whitelist polí + výchozí předlohy + resolver + formátování),
    `soubory.py` (ukládání souborů), `permissions.py` (`vyzaduj_nabidkovac`, `vyzaduj_katalog`).
  - Frontend: `pages/Nabidkovac.jsx`, `NabidkovacSekce.jsx`, `NabidkaDetail.jsx`,
    `NabidkaVystupStranka.jsx`, `NabidkovacKatalog.jsx`; `components/NabidkaVystup.jsx`,
    `NabidkaVystupEditor.jsx`, `DokumentUpload.jsx`, `PridatDialog.jsx`; sdílené konstanty
    `nabidkovac.js`; API funkce `api.js`; routy `App.jsx`.

### Časté potíže / co dělat, když…
- **„Na Nabídkovač nemáš oprávnění" (403)** → uživateli chybí právo `nabidkovac`; přiděl skupině
  nebo jednotlivci v Admin nastavení.
- **Katalog jde jen číst, tlačítka + Technologie/+ Sloupec chybí** → chybí právo `nabidkovac_katalog`
  (jen vedení/admin); dlaždice „⚙ Katalog a výpočty" se pak ani nezobrazí.
- **„Nepovolená přípona" / „Soubor je příliš velký"** → povolené přípony podle typu dokumentu
  (faktura = `.pdf`; spotřeba = `.csv/.xlsx/.xls`), limit 25 MB.
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
