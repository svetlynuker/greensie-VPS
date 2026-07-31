# Jak tento soubor použít

### 🖥️ Na serveru (po přihlášení přes ssh, ve složce projektu)

```
cd ~/projects/greensie-app
claude
```

Tohle otevře Claude Code ve složce appky (stejně jako u peak shavingu). Jakmile se otevře
prompt (`>`), vlož do něj **celý text od nadpisu `## Kontext` níže až do úplného konce
souboru** a odešli.

Claude Code v tomto kroku **nemá psát žádný kód** – má jen navrhnout metodiku (textový
dokument), stejně jako se to dělalo u peak shavingu (`docs/METODIKA-peak-shaving.md` vznikla
dřív, než se psal `peak_shaving.py`). Až metodiku navrhne, přečti si ji, řekni mu k ní
poznámky/opravy, a teprve pak společně naplánujte implementaci po krocích (PR po PR, stejně
jako u peak shavingu).

---

# Prompt pro Claude Code

## Kontext

Pracujeme na appce Greensie (Nabídkovač). Už existuje hotový a nasazený modul **peak shaving**
(viz `docs/peak-shaving.md` a `docs/METODIKA-peak-shaving.md` v repu) – to je referenční vzor
jak co do **hloubky/rigoróznosti metodiky**, tak co do **vizuálu appky** (panel v detailu
nabídky, admin katalog + sazby, SVG grafy bez knihovny).

Teď chceme přidat druhý typ nabídky: **PPA pro FVE** (Power Purchase Agreement – odběratel
odebírá elektřinu z fotovoltaiky po sjednanou dobu za smluvenou cenu, bez vlastní investice
do FVE).

**Tvůj úkol v tomto kroku: navrhnout metodiku a výpočty, ne psát kód.** Výstup = nový soubor
`docs/METODIKA-ppa-fve.md`, strukturovaný a stejně podrobný jako
`docs/METODIKA-peak-shaving.md` (číslované kapitoly, konkrétní vzorce, jasně označené
předpoklady/otevřené body, které je potřeba se mnou ještě probrat před implementací).

Nejdřív si prosím přečti `docs/peak-shaving.md`, `docs/METODIKA-peak-shaving.md` (pokud
existuje) a relevantní kód (`backend/app/nabidkovac/peak_shaving.py`,
`backend/app/nabidkovac/models.py`, `frontend/src/components/PeakShavingPanel.jsx`,
`frontend/src/components/GrafOdberu.jsx`), ať metodika i budoucí implementace navazují na
stejné konvence, jmennou konvenci (české názvy sloupců), práva a strukturu API.

## Byznysový rámec – toto je už rozhodnuté, neřeš to jako otevřenou otázku

1. **Vlastnictví/investice:** FVE staví a vlastní Greensie (případně jiný investor), ne
   klient. Klient nic neinvestuje, jen po dobu kontraktu odebírá elektřinu za sjednanou PPA
   cenu (Kč/MWh). Ekonomika/návratnost se tedy počítá investorovi (Greensie), ne klientovi –
   klientovi se ukazuje jen srovnání "co platí dnes" vs. "co by platil s PPA".
2. **Data o výrobě FVE:** appka si výrobu **sama simuluje** – OZ zadá instalovaný výkon
   (kWp), lokalitu a sklon/azimut panelů, appka z toho dopočítá profil výroby (obdoba toho,
   jak dnes OZ nahrává profil spotřeby). Není potřeba nahrávat hotový profil výroby ručně.
3. **Cenotvorba PPA:** cena je **indexovaná/eskalovaná** – každý rok kontraktu se navyšuje o
   dohodnutý index (např. pevné % ročně nebo inflace), ne fixní cena po celou dobu. Výpočet
   musí umět spočítat vývoj ceny (a tedy i ekonomiky) po jednotlivých letech kontraktu, ne jen
   pro jeden rok.
4. **Výstupy appky:**
   - graf výroby FVE vs. spotřeby klienta (měsíční, obdoba `GrafOdberu.jsx`),
   - tabulka roční/kumulativní úspory a návratnosti po celou dobu kontraktu.

   Panel v detailu nabídky (obdoba `PeakShavingPanel.jsx`) a případný admin katalog/sazby
   nejsou v tomto kroku pevně zadané – navrhni, jak by měly vypadat, ať to sedí vizuálně a
   strukturně k peak shavingu, ale je to na tvém návrhu, ne na mém zadání.

## Co konkrétně chci, abys v metodice navrhl a zdůvodnil

1. **Tok dat** – analogicky ke kapitole 1 v `METODIKA-peak-shaving.md`: co OZ zadává, co se
   simuluje, co se ukládá, co se zobrazí.
2. **Datový model** – nové/upravené tabulky (např. `profil_vyroby_fve` obdoba
   `spotreba_profil`, tabulka pro PPA sazby/eskalaci obdoba `sazby_distributoru`, případně
   rozšíření `technologie`/`katalog_sloupce` pro FVE komponenty). Piš v duchu existujících
   konvencí (české názvy, JSONB pro flexibilní parametry, idempotentní seed).
3. **Simulace výroby FVE** – jaký zdroj/model použít pro odhad výroby podle kWp, lokality a
   sklonu/azimutu (např. zjednodušený model s měsíčními/hodinovými koeficienty pro ČR místo
   volání externího API), jaké rozlišení (hodinové vs. 15minutové) a jak ho spárovat s
   15minutovým profilem spotřeby. Zahrň i degradaci výkonu panelů v čase (obvykle ~0,5 %/rok)
   – navrhni, jestli a jak ji promítnout do výpočtu za jednotlivé roky kontraktu.
4. **Spárování výroby a spotřeby** – jak počítat, kolik vyrobené energie klient reálně
   spotřebuje (self-consumption) a co se stane s přebytkem, který klient v daný okamžik
   nespotřebuje (nabízí se: přebytek se v PPA neúčtuje / prodává se do sítě za jinou,
   nižší cenu / jiná varianta). Tohle jasně označ jako **otevřený předpoklad**, který
   potvrdíme spolu – neprosazuj jednu variantu jako jistou.
5. **Ekonomika PPA po letech** – vzorec pro roční náklad klienta s PPA (indexovaná cena ×
   spotřebovaná FVE energie + zbytek spotřeby za cenu od současného dodavatele, tu ať jde
   taky eskalovat/zafixovat – navrhni rozumný výchozí předpoklad a označ ho jako předpoklad
   k ověření) vs. bez PPA (současný dodavatel na celou spotřebu). Roční a kumulativní úspora
   klienta po celou dobu kontraktu (typicky 10–20 let – navrhni, jak nastavit délku kontraktu
   jako parametr).
6. **Ekonomika investora (Greensie)** – capex FVE (z katalogu technologií, Kč/kWp), roční
   výnos z PPA plateb klienta, návratnost/IRR investice. Návrhni, jestli/jak zahrnout
   provozní náklady (O&M) FVE – označ jako otevřený bod.
7. **Výběr/doporučení varianty** – obdoba kapitoly 4.7 u peak shavingu: pokud appka nabízí
   víc velikostí/konfigurací FVE, jak vybrat doporučenou (např. podle nejkratší návratnosti
   investora nebo podle pokrytí spotřeby klienta – navrhni a zdůvodni).
8. **Data pro grafy** – co přesně by měl graf výroby vs. spotřeby ukazovat (měsíční
   výroba/spotřeba, self-consumption vs. přebytek/nedostatek) a co tabulka úspory/návratnosti
   (roky, roční úspora klienta, kumulativní úspora, cash-flow/návratnost investora).
9. **Otevřené body / předpoklady k ověření** – vlastní kapitola na konci (jako kapitola 8 u
   peak shavingu), kde vypíšeš úplně všechno, co jsi si musel domyslet/odhadnout a co
   potřebuješ ode mě potvrdit, než se začne psát kód.

## Formální požadavky na výstup

- Nový soubor `docs/METODIKA-ppa-fve.md`, číslované kapitoly, konkrétní vzorce (ne jen slovní
  popis), stejná úroveň detailu jako `METODIKA-peak-shaving.md`.
- Žádné zásahy do kódu appky v tomto kroku.
- Na konci mi napiš stručné shrnutí (5–10 řádků), na co konkrétně potřebuješ ode mě
  odpověď/rozhodnutí, než půjdeme do implementace.
