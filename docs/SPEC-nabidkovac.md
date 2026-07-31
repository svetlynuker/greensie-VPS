# Zadání pro Claude Code – dlaždice "Nabídkovač"

Tento dokument navazuje na `docs/SPEC.md` (kostra appky Greensie, dlaždice Přehled projektů/financí/změn) a `docs/instrukce-projekt-vps.md`. Ulož ho do `~/projects/greensie-app/docs/SPEC-nabidkovac.md` a zadej Claude Code na serveru.

**Rozsah tohoto promptu: POUZE kostra dlaždice + datový model.** Samotná výpočetní logika (sizing elektrárny, napojení na PVGIS, ROI vzorce, výběr technologie, generování PDF) se bude programovat v navazujících promptech, až bude s Danem doladěná přesná metodika. Tenhle prompt má appku připravit tak, aby na to šlo bez přestavby navázat.

---

## 1. Kontext

Nabídkovač je nová dlaždice v rozcestníku (vedle Přehledu projektů/financí/změn). Slouží obchodním zástupcům (OZ) k vytvoření cenové nabídky pro zákazníka ve třech produktových liniích:

- **PPA** – Greensie zainvestuje a postaví FVE elektrárnu na střeše zákazníka, dodává mu z ní vyrobenou elektřinu za cenu nižší než jeho současná tržní cena. Nástroj má z faktur/zadané ceny + 15minutového profilu spotřeby spočítat optimální velikost elektrárny, porovnat výrobu vs. spotřebu, dopočítat cenu dodávané elektřiny a minimální délku kontraktu tak, aby se investice Greensie zaplatila z marže (rozdíl cena výroby vs. cena pro zákazníka × koeficient zisku).
- **Prodej** – jednodušší větev: na základě křivky spotřeby (nebo natvrdo zadaného výkonu elektrárny) systém navrhne technologii z katalogu a vrátí prodejní cenovou nabídku (zákazník je vlastníkem zařízení).
- **Peak shaving** – návrh baterie, která ořezává špičky odběru a šetří zákazníkovi za rezervovanou kapacitu/výkon. Vstupem je soubor s 15minutovými maximy; z katalogu se vybere nejvhodnější baterie podle poměru cena/výkon.

Důležité: jedna zakázka může nakonec vyústit ve **víc navrhovaných řešení současně** (např. PPA + peak shaving baterie, pokud to model vyhodnotí jako vhodné). Uživatel (zákazník/OZ) si na konci vybírá z nabídnutých variant.

Architektura výpočtů: **deterministický kód** (žádní AI agenti za běhu appky pro matematiku), s jednou výjimkou – **extrakce dat z PDF faktur od elektřiny se dělá přes LLM** (Claude API), protože faktury jsou od různých dodavatelů v různých formátech a psát/udržovat parser pro každého dodavatele není udržitelné. Extrahovaná data se vždy zobrazí OZ ke kontrole/opravě, než se pustí do výpočtu (žádný výpočet neběží nad nezkontrolovanými daty).

---

## 2. Struktura dlaždice a navigace

- V rozcestníku přibude dlaždice **"Nabídkovač"**, viditelná podle práv (viz kapitola 3) – stejný princip jako u ostatních dlaždic (`SPEC.md` kap. 2): pokud uživatel nemá právo, dlaždice se skryje celá, ne jen zašedne.
- Po kliknutí na dlaždici se zobrazí rozcestník o úroveň níž se třemi podsekcemi: **PPA**, **Prodej**, **Peak shaving**.
- V této fázi (kostra) mají podsekce jen:
  - hlavičku a stručný popis produktu,
  - seznam dosavadních nabídek daného typu (tabulka: zákazník, stav, vytvořil, datum) – zatím prázdné/testovací,
  - tlačítko "Nová nabídka", které založí záznam a otevře formulář pro zadání zákazníka + nahrání dokumentů (viz kap. 5),
  - jasně viditelné označení "Výpočet zatím není aktivní" tam, kde by měl proběhnout skutečný výpočet – ať je zjevné, že tahle část se ještě staví, a nikdo omylem nepovažuje zástupný výstup za reálnou nabídku.
- Vizuální styl navazuje na existující dlaždice (barvy, layout) podle `SPEC.md`.

---

## 3. Práva

Existující role appky jsou **admin / zaměstnanec / vedení** (viz `SPEC.md`). Nabídkovač potřebuje navíc rozlišit **OZ (obchodní zástupce)** – ti appku primárně používají (vytvářejí a upravují nabídky). Úprava výpočtových nastavení a katalogu technologií (kapitola 4) smí dělat jen **vedení/admin**.

Než se do toho pustíš: **zkontroluj stávající model rolí/práv v appce a navrhni, jak do něj OZ zapadne** (nová role, nebo podmnožina role "zaměstnanec" s dodatečným příznakem/oprávněním?). Pokud si nejsi jistý, jak to udělat bez narušení existujících práv u Přehledu projektů/financí, **zeptej se Dana**, než to zavedeš – ať se nerozbije nic ve stávajících pohledech.

Souhrn práv k Nabídkovači:
- **Vidí dlaždici a vytváří/edituje nabídky:** OZ, vedení, admin.
- **Edituje katalog technologií a výpočtová nastavení (CAPEX, marže, koeficient zisku, délky kontraktů apod.):** jen vedení, admin.
- **Zaměstnanec bez role OZ:** dlaždici nevidí (pokud Dan neurčí jinak).

---

## 4. Datový model

Cílem je připravit databázová schémata (PostgreSQL), na která navážou budoucí výpočty, aniž by se musela předělávat struktura. Návrhy tabulek níže ber jako výchozí kostru – uprav názvy/typy podle konvencí, které už appka používá.

### 4.1 `technologie` (katalog)
Zatím plněno ručně přes admin rozhraní, později synchronizace z Raynet API (nech pro to místo, např. pole `raynet_id`, `synchronizovano_at`, nullable).

- `id`
- `typ` (enum/text: `fve_panel`, `invertor`, `baterie`, `jina`)
- `nazev` / `model`
- `vykon_kw` nebo `kapacita_kwh` (podle typu)
- `cena_kc` (CAPEX jednotky)
- `ucinnost` (volitelné, podle typu)
- `dostupnost` (bool – aktivní/neaktivní v katalogu)
- `raynet_id` (nullable, na budoucí sync)
- `vytvoreno_at`, `aktualizovano_at`, `vytvoril_user_id`

### 4.2 `vypoctova_nastaveni` (globální parametry pro výpočty)
Editovatelné jen vedením/adminem. Navrhni jako verzovanou tabulku (ne přepis "natvrdo"), aby šlo dohledat, jaké parametry platily v době vytvoření konkrétní nabídky – nabídka si při výpočtu uloží referenci na verzi nastavení, se kterou byla počítána.

- `id`, `verze` nebo `platne_od`
- `koeficient_zisku` (marže pro výpočet min. délky PPA kontraktu)
- `min_delka_kontraktu_roky`, `max_delka_kontraktu_roky`
- další parametry podle potřeby (discount rate, přirážky, apod.) – klidně jako JSONB pole `parametry`, ať se dá rozšiřovat bez migrace při každé nové proměnné
- `vytvoril_user_id`, `vytvoreno_at`

### 4.3 `nabidky` (hlavní záznam zakázky/nabídky)
- `id`
- `typ` – ale pozor: protože jedna zakázka může vygenerovat víc řešení (PPA + peak shaving), `typ` na úrovni `nabidky` chápej spíš jako "za jakým účelem OZ nabídku založil" (např. z které podsekce vznikla), zatímco skutečná navržená řešení jsou v `navrhovana_reseni` (4.7) a mohou být i kombinovaná.
- `zakaznik_nazev`, `zakaznik_adresa`, `zakaznik_gps` (pro budoucí PVGIS – lat/lng, může se zatím doplňovat ručně nebo geokódovat z adresy)
- `stav` (koncept / data nahrána / zkontrolováno OZ / spočítáno / hotovo)
- `vytvoril_user_id` (OZ), `vytvoreno_at`, `aktualizovano_at`
- `vypoctova_nastaveni_id` (reference na verzi použitou při výpočtu, vyplní se až při skutečném výpočtu)

### 4.4 `nabidka_dokumenty` (nahrané soubory)
- `id`, `nabidka_id`
- `typ` (`faktura_pdf`, `spotreba_csv`, `jiny`)
- `soubor_cesta` / `soubor_blob_ref`
- `stav_zpracovani` (nahráno / extrahováno / chyba extrakce / ručně doplněno)
- `nahral_user_id`, `nahrano_at`

### 4.5 `spotreba_profil` (15minutový diagram spotřeby/maxim)
Časové řady mohou být objemné (35 040 řádků/rok na zákazníka) – navrhni efektivní uložení (buď širší tabulka s indexem na `nabidka_id` + `cas`, nebo komprimované uložení po dnech jako JSONB pole hodnot – zvol podle toho, co je v appce běžné, a zdůvodni volbu v komentáři v kódu).
- `nabidka_id`, `cas` (timestamp), `hodnota_kwh` (spotřeba) / `hodnota_kw` (maximum, dle typu podsekce)
- `zdroj_dokument_id` (reference na `nabidka_dokumenty`)

### 4.6 `extrahovana_data_faktury`
Výstup LLM extrakce z PDF faktury – vždy s příznakem, zda byl uživatelem zkontrolován/upraven, aby bylo jasné, že se nepočítá nad nedůvěryhodnými daty.
- `id`, `nabidka_id`, `dokument_id`
- `dodavatel_text` (jak LLM přečetl jméno dodavatele – informativní)
- `cena_kwh`, `rocni_spotreba_kwh`, `rezervovany_prikon_kw` (a další pole, doplň podle reálných faktur, až budou k dispozici vzorky)
- `zkontrolovano_ok` (bool), `upravil_user_id`, `upraveno_at`
- `surova_extrakce_json` (JSONB – celý raw výstup LLM, pro debug a pozdější zpřesňování promptu)

### 4.7 `navrhovana_reseni` (výstup výpočtu – může jich být pro jednu nabídku víc)
- `id`, `nabidka_id`
- `typ_reseni` (`ppa`, `prodej`, `peak_shaving`)
- `popis_json` (JSONB – velikost elektrárny/baterie, doporučená cena, délka kontraktu, ROI, payback, apod. – necháváme flexibilní, dokud nejsou vzorce finální)
- `vybrano_zakaznikem` (bool, nullable dokud není rozhodnuto)
- `vytvoreno_at`

### 4.8 `generovane_nabidky_pdf`
- `id`, `nabidka_id`, `reseni_id` (nullable, pokud PDF shrnuje víc řešení najednou)
- `soubor_cesta`
- `vygeneroval_user_id`, `vygenerovano_at`

---

## 5. Nahrávání dokumentů (UI komponenta, bez zpracování)

Postav znovupoužitelnou komponentu pro nahrání dokumentů k nabídce (PDF faktura, CSV se spotřebou), společnou pro všechny tři podsekce:

- Drag & drop nebo výběr souboru, validace přípony/velikosti.
- Po nahrání se vytvoří záznam v `nabidka_dokumenty` se stavem "nahráno".
- **Skutečné zpracování (LLM extrakce z PDF, parsování CSV) v tomto promptu NEIMPLEMENTUJ** – jen ulož soubor a vytvoř placeholder úlohu/stav, aby na to šlo navázat. V UI u nahraného souboru zobraz "Čeká na zpracování (funkce se připravuje)".

---

## 6. Co NENÍ součástí tohoto promptu

Aby nedošlo k nedorozumění, explicitně vypiš/potvrď, že se v tomto kroku NEPROGRAMUJE:

- LLM extrakce dat z PDF faktur (bude samostatný prompt, včetně promptování Claude API a UI pro kontrolu/opravu extrahovaných dat).
- Parsování CSV se spotřebou a napojení na `spotreba_profil`.
- Napojení na PVGIS (výpočet roční křivky výroby FVE z GPS + orientace + sklonu).
- Algoritmus sizingu elektrárny/baterie a výběru technologie z katalogu.
- Výpočet ROI, minimální délky PPA kontraktu, prodejní ceny.
- Generování finálního PDF nabídky (layout ještě není navržený, řeší se samostatně).
- Napojení katalogu technologií na Raynet API (zatím jen ruční správa přes admin UI).

---

## 7. Technické prostředí

Stejné jako u zbytku appky (`SPEC.md` kap. 6): Hetzner VPS, Python/FastAPI backend, JS frontend, PostgreSQL, `.env` pro citlivé údaje (včetně budoucího Anthropic API klíče pro LLM extrakci faktur – zatím do `.env` jen připrav proměnnou, i když se nepoužije).

---

## 8. Priorita v rámci tohoto promptu

1. Datový model (kapitola 4) – migrace v PostgreSQL.
2. Dlaždice + navigace + prázdné podsekce (kapitola 2).
3. Práva – ujasnit roli OZ, případně se zeptat Dana (kapitola 3).
4. Komponenta pro nahrávání dokumentů bez zpracování (kapitola 5).

Po dokončení tohoto kroku se vrátíme k business logice (kapitola 1) a rozepíšeme ji do samostatných promptů – nejdřív pravděpodobně Peak shaving (nejjednodušší), pak Prodej, nakonec PPA (nejsložitější kvůli výpočtu kontraktu).
