# E-mail

> **Sekce v nabídce:** `emaily` · **Adresa (routa):** `/emaily` · **Kdo smí otevřít:** kdokoli s právem `emaily` (bez práva se sekce v nabídce vůbec nezobrazí; supersprávce má vždy)
> **Kód:** frontend `frontend/src/pages/Emaily.jsx`, `components/EmailCteni.jsx`, `components/EmailNastaveni.jsx`, backend `backend/app/crm/email_*.py`

**Tvoje e-mailová schránka ze Seznamu přímo v appce.** Čteš v ní poštu, vidíš složky a nepřečtené
zprávy — a hlavně: **každá zpráva se sama napojí na firmu a obchodní případ v CRM**. To je celý důvod,
proč e-mail není jen odkaz na seznam.cz: komunikace se zákazníkem je vidět u něj na kartě, aniž by
ji tam někdo přepisoval.

Pošta zůstává na Seznamu. Appka je do schránky **okno**, ne archiv — co uděláš tady (přečteno, přesun
do složky), se projeví i v mobilu a na webu Seznamu, a naopak.

> 📸 SCREENSHOT: celá obrazovka E-mailu — horní lišta s tlačítkem „Zkontrolovat poštu" a adresou schránky, pod ní tři panely: složky, seznam zpráv, otevřená zpráva

---

## 🧑 Pro uživatele

### K čemu to slouží

Abys nemusel přepínat mezi CRM a webmailem. Když ti přijde poptávka, vidíš u ní hned, **od které firmy
je** a **ke kterému obchodnímu případu patří** — a nemusíš to nikam opisovat.

### První nastavení: připojení schránky

Při prvním otevření se ukáže formulář **Připojit schránku**. Vyplň:

| Políčko | Co tam patří |
|---|---|
| **E-mailová adresa** | Celá adresa tvojí schránky, včetně části za zavináčem (`jmeno@greensie.cz`) |
| **Heslo ke schránce** | Opravdové heslo od schránky (viz upozornění níž) |
| **Jméno odesílatele** | Jak tě uvidí příjemce. Prázdné = vezme se tvoje jméno z appky |
| **Podpis** | Text, který se přidá pod odeslané zprávy |

Pod tlačítkem **Pokročilé** jsou adresy serverů (u Seznamu se nemusí měnit) a kolik nejnovějších
zpráv se má stáhnout při prvním připojení (výchozí 300 na složku).

> ⚠️ **K heslu.** Seznam Email nenabízí zvláštní „heslo pro aplikace" jako Google — IMAP je u něj
> trvale zapnutý a přihlašuje se **přímo heslem od schránky**. Nedá se to obejít, takže heslo v appce
> být musí. Ukládá se **zašifrované** a z appky už se nedá přečíst; nikdo, ani supersprávce, ho
> nezobrazí. Když si heslo na Seznamu změníš, **přepiš ho i tady**, jinak se pošta přestane stahovat.

Vždycky nejdřív zmáčkni **Otestovat připojení**. Nic neuloží, jen zkusí přihlášení a vypíše, kolik
složek schránka má. Špatné heslo se totiž jinak pozná až po uložení — a Seznam po několika marných
pokusech začne přihlášení zdržovat.

### Rozvržení obrazovky

Nahoře lišta, pod ní tři panely vedle sebe (klasické rozvržení poštovního programu):

1. **Horní lišta** — tlačítko **Zkontrolovat poštu**, barevné kolečko se stavem schránky
   (zelené = v pořádku, červené = chyba), adresa schránky a čas posledního stažení. Vpravo
   **Nastavení schránky**.
2. **Složky** (vlevo) — Doručená pošta, Odeslané, Koncepty, Spam, Koš a tvoje vlastní složky.
   Číslo v zeleném kolečku je počet **nepřečtených**.
3. **Seznam zpráv** (uprostřed) — hledání, přepínač „jen nepřečtené" a samotný seznam. Nepřečtená
   zpráva je **tučně a s tečkou** vlevo. Pod předmětem je náhled textu a případně **štítek s názvem
   firmy** a číslem případu, ke kterému je zpráva připojená.
4. **Čtení** (vpravo) — otevřená zpráva: předmět, odesílatel, příjemci, tělo, přílohy a lišta akcí.

Na užší obrazovce (do 1100 px) se panel složek schová a zbydou dva; na mobilu se ukazuje vždy jen
jeden — seznam, nebo otevřená zpráva.

### Co se dá dělat

- **Otevřít zprávu** — klikni na ni v seznamu. Otevřením se označí jako přečtená (i na Seznamu).
- **Označit nepřečtené / přečtené** — tlačítko v liště nad zprávou.
- **Vlaječka (★)** — označení „tohle si pamatuj". Je to tentýž příznak, který vidíš na Seznamu.
- **Přesunout do složky** — rozbalovací seznam **Přesunout do…** v liště nad zprávou.
- **Do koše** — přesune zprávu do Koše. **Natrvalo appka nemaže nic** (viz níž).
- **Na celou plochu** — tlačítko **⛶ Na celou plochu** v liště nad zprávou schová složky i seznam
  a zpráva se roztáhne na celou plochu modulu. Hodí se na nabídky, dlouhá vlákna a maily
  s tabulkou. Zpátky tlačítkem **⤡ Zmenšit** nebo klávesou **Esc**; seznam se vrátí i sám, jakmile
  zprávu zavřeš, přesuneš nebo dáš do koše.
- **Stáhnout přílohu** — klikni na ni dole ve zprávě.
- **Hledat** — políčko nad seznamem zpráv. Hledá v předmětu, odesílateli a náhledu textu
  ve stažené poště (viz omezení níž).
- **Vypnout stahování složky** — **dvojklik** na složku v levém panelu. Spam a Koš jsou vypnuté
  od začátku, protože zabírají nejvíc a čtou se nejméně. Vypnutá složka je vypsaná kurzívou.

### Kdy se pošta stahuje

Sama, na pozadí: Doručená pošta každou minutu, ostatní složky každých patnáct minut. Stahuje to
**samostatná služba na serveru**, ne appka — takže se webová appka nikdy nezasekne kvůli pomalé
schránce. Seznam zpráv na obrazovce se obnovuje každých deset sekund z databáze appky.

Tlačítko **Zkontrolovat poštu** je pro chvíle, kdy nechceš čekat na další cyklus.

> 💡 Pokud v horní liště stojí „ještě se nestahovalo" a tlačítko nic nenajde, nejspíš neběží služba
> stahování pošty na serveru. Napiš to správci — v UI je to schválně vidět, aby to nebylo tiché.

### Co appka záměrně NEumí

- **Nesmaže poštu natrvalo.** „Do koše" přesune zprávu do Koše, nic víc. Nevratné mazání se dělá
  na webu Seznamu. Smazat cizí poštu omylem jedním kliknutím v CRM je horší nepříjemnost než
  dojít pro to na Seznam.
- **Nehledá v tělech všech zpráv.** Hledá se jen v tom, co je stažené (předmět, odesílatel, náhled).
  Fulltext přes celou schránku by znamenal stáhnout ji celou; na hluboké hledání je web Seznamu.
- **Neukazuje obrázky z internetu automaticky.** Viz níž.

### Obrázky v poště jsou zablokované

U zprávy s obrázky z internetu se objeví žlutá lišta a obrázky se nenačtou, dokud neklikneš na
**Zobrazit obrázky**. Není to obtěžování: takový obrázek je **sledovací pixel** — prozradí
odesílateli, že jsi zprávu otevřel, kdy a z jaké IP adresy. Stejně to dělá Gmail i Outlook.

### Psaní, odpovídání a přeposílání

Tlačítko **✎ Napsat** v horní liště, nebo **Odpovědět / Odpovědět všem / Přeposlat** nad otevřenou
zprávou. Odesílá se **z tvojí adresy**, ne z firemního automatu, takže odpověď přijde tobě.

Do políčka **Komu** se adresy napovídají z **adresáře CRM** — kontaktní osoby zákazníků, obecné
adresy firem a kolegové z appky. Napovídá se od druhého napsaného znaku; osoby jsou první, protože
e-mail se skoro vždycky píše konkrétnímu člověku, ne na obecnou adresu firmy. Adresu, která v CRM
není, prostě napíšeš a potvrdíš Enterem, čárkou nebo středníkem.

Po odeslání se stanou tři věci: zpráva odejde, uloží se **kopie do Odeslaných** (takže je vidět
i v mobilu) a zapíše se **aktivita k firmě nebo obchodnímu případu** — to je celý smysl e-mailu
v CRM.

> 💡 **Odpovědět všem** vynechá tvoji vlastní adresu, aby sis neposílal kopii sám sobě.
> **Přeposlání nepřenáší přílohy** — musely by se stáhnout a poslat znovu, což u velké zprávy
> znamená dlouhé čekání v okně. Když je potřebuješ, stáhni si je a připoj ručně; okno na to
> upozorní.

Přílohy: **📎 Připojit soubor**. Strop je 18 MB na celou zprávu včetně příloh — nad to zprávu
poštovní server odmítne, takže velké soubory posílej odkazem na Disk.

### Psaní s formátováním

Tělo zprávy se píše ve **formátovacím editoru** — tučné, kurzíva, podtržení, přeškrtnutí,
písmo a jeho velikost, barva textu i zvýraznění, odrážky, číslování, odsazení, zarovnání,
odkazy a vodorovná čára. Funguje i Ctrl+B / Ctrl+I / Ctrl+U.

Vkládání z Wordu je ošetřené: `mso-` styly a wordovský balast se při vložení zahodí, aby se
zpráva nerozsypala v Outlooku. **Ctrl+Shift+V** vloží bez formátování.

> 💡 Formátování je záměrně jednoduché (tabulky, inline styly). Poštovní klienti nejsou
> prohlížeče — Outlook renderuje přes Word, takže moderní HTML by se rozpadlo.

### Hromadné akce

Vlevo u každé zprávy je **zaškrtávátko**. Jakmile něco vybereš, nad seznamem se objeví zelená
lišta: **Přečtené**, **Nepřečtené**, **★** (vlaječka), **Přesunout do…** a **Do koše**.
Nahoře je „Vybrat vše na stránce".

Akce se provede po jedné zprávě, takže když jedna selže (třeba ji mezitím někdo přesunul),
ostatní se dokončí a v hlášce je počet neúspěchů.

### Párování pošty na záznamy CRM

Zpráva, ve které figuruje adresa někoho z CRM — **odesílatel, příjemce nebo kopie** — se
sama napojí na jeho firmu, kontaktní osobu a otevřený obchodní případ. Raynet tomu říká
„rejnetování" a dělá to stejně.

Napojená komunikace je pak vidět:

- na **kartě zákazníka** v záložce *Aktivity a úkoly*, v sekci „Komunikace e-mailem",
- na **kartě obchodního případu** tamtéž (bere i poštu firmy bez konkrétního případu),
- v **timeline** zákazníka mezi ostatními událostmi.

### Ruční dopárování

Automatika spáruje jen zprávy, jejichž adresa už v CRM je. Zbytek — nová firma, člověk
píšící ze soukromé adresy, přeposlaná poptávka — připojíš ručně:

- **Jednu zprávu:** otevři ji a nad tělem klikni na **🔗 Připojit ke klientovi**. Když už
  spárovaná je, je tam místo toho název firmy a tlačítka **Připojit jinam** a **Odpojit**.
- **Víc zpráv naráz:** zaškrtni je v seznamu a v zelené liště klikni na **🔗 Ke klientovi**
  (nebo **Odpojit**).

V obou případech se vyhledá firma podle názvu, IČO nebo města a volitelně se vybere
i konkrétní obchodní případ. Bez případu se zpráva ukáže na kartě firmy i u jejích případů.

Ruční napojení má přednost: **automatika ho nikdy nepřepíše**. Odpojení vazbu neruší, jen ji
schová — smazanou by synchronizace při dalším stažení vyrobila znovu a zpráva by se na kartu
vrátila.

> ⚠️ **Co to znamená pro soukromí — přečti si to.** Tohle je jediné místo, kde se ukazuje
> pošta z cizí schránky. Seznam pošty v E-mailu vidí pořád jen její majitel, ale zpráva
> **napojená na zákazníka se ukáže i kolegům**, kteří na ten záznam mají právo. Bez toho by
> celá funkce neměla smysl (komunikace by dál zapadala v cizí schránce).
>
> Pojistky: napojí se **jen zpráva, jejíž adresa přesně sedí** na záznam v CRM, takže osobní
> pošta od neznámých adres se do CRM nedostane vůbec. Veřejné domény (`seznam.cz`,
> `gmail.com`…) se k určení firmy nepoužívají. A na kartě je vidět **jen předmět a náhled** —
> celou zprávu si otevře jenom majitel schránky.

### Pravidla, oznámení o nepřítomnosti a přeposílání

Tlačítko **Pravidla a automatika** v horní liště.

> ⚠️ **Tohle dělá appka, ne Seznam.** Seznam neumí OOO ani přeposílání nastavit zdálky, takže to
> není zrcadlo jeho nastavení, ale vlastní funkce. **Funguje jen když na serveru běží stahování
> pošty.** Na delší dovolenou si to radši nastav i přímo na seznam.cz jako zálohu.

**Oznámení o nepřítomnosti (OOO).** Zapneš, napíšeš text a volitelně období od–do. Pojistky, které
jsou tam schválně a nejdou vypnout:

- **Robotům se neodpovídá.** Newslettery, automatické odpovědi a odrazy nedoručení appka pozná
  a přeskočí. Bez toho by si dva autorespondery psaly donekonečna.
- **Jedné adrese nejvýš jednou za 24 hodin.** I kdyby ti někdo napsal pětkrát, odpověď dostane jednou.
- **Sám sobě si appka neodpovídá** a **na starou poštu taky ne** — zapnutí OOO nerozešle odpovědi
  na to, co ti přišlo minulý týden.

**Automatické přeposílání.** Zapneš a vyplníš adresu. Můžeš si nechat kopii ve své schránce
(výchozí), nebo nechat zprávy rovnou padat do Koše. Přeposílat na **vlastní adresu** nejde — vznikla
by nekonečná smyčka a appka to odmítne. Newslettery se nepřeposílají a přílohy se nepřenášejí.

**Pravidla pro třídění pošty.** Fungují jako v Outlooku: *Když* platí podmínky, *pak* se provedou akce.

| Podmínka na | Operátory |
|---|---|
| Odesílatel, Předmět, Příjemce, Text zprávy | obsahuje, neobsahuje, je přesně, začíná na, končí na |
| Má přílohu | ano / ne |

Akce: **přesunout do složky**, **označit jako přečtené**, **označit vlaječkou**, **přeposlat na adresu**.

Podmínky se spojují buď „platí všechny", nebo „stačí jedna". Pravidla se vyhodnocují **shora dolů**
a zaškrtnutí „když tohle pravidlo zabere, další už nezkoušet" zastaví zpracování — bez toho by
zpráva propadla i pravidly, která už platit nemají.

Dvě věci, které stojí za pozornost:

- **Pravidla platí jen na nově příchozí poštu.** Zpětně se na stažené zprávy nepoužijí.
- **Pravidlo bez podmínky nebo bez akce nejde uložit.** Prázdné podmínky by znamenaly „platí vždy"
  a rozházelo by to celou schránku.

U každého pravidla je vidět, kolikrát už zabralo — podle toho poznáš, jestli dělá, co má.

### Napojení na CRM

Zpráva se páruje na firmu podle e-mailové adresy — v tomhle pořadí:

1. přesná adresa **kontaktní osoby** u zákazníka,
2. přesná **obecná adresa firmy**,
3. **doména** adresy, ale **jen když patří jedné jedinné firmě** v CRM.

Veřejné domény (`seznam.cz`, `gmail.com`, `centrum.cz` a podobné) se pro párování nepoužívají —
podle nich by se zpráva přiřadila náhodně. Když se firma nenajde, zpráva prostě zůstane nepřiřazená;
**nepřesné párování je horší než žádné**, protože v CRM by pak visela cizí komunikace a nikdo by
nevěděl, že je špatně.

Když je firma známá, hledá se k ní ještě **nejnovější otevřený obchodní případ**. Uzavřené případy
se přeskakují — došlá pošta se nemá lepit na zakázku, která je rok hotová.

### Čí poštu kdo vidí

**Jen svoji.** Schránka patří člověku, ne firmě, takže do cizí pošty nevidí **nikdo** — ani vedení
s právem `crm_vse`, ani supersprávce. To je jinak než u záznamů CRM, kde vedení vidí vše.

### Odpojení schránky

**Nastavení schránky → Odpojit schránku.** Z appky zmizí stažená pošta a uložené heslo.
**Na seznam.cz se nesmaže nic** — schránka funguje dál, jen do ní appka přestane vidět.

---

## 🛠 Pro správce a vývojáře

### Šifrovací klíč

Hesla ke schránkám jsou v databázi zašifrovaná (Fernet). Klíč žije **jen v `.env`** v kořeni repa
a bere se v tomto pořadí:

1. `APP_ENC_KEY` — společný klíč appky,
2. `KONEKTOR_ENC_KEY` — původní klíč konektoru (záloha, aby e-mail nemusel čekat na nový záznam).

Pokud se `APP_ENC_KEY` doplňuje dodatečně, musí to být **tentýž klíč**. Jinak se dřív uložená hesla
přestanou dešifrovat — nespadne to, jen se schránky začnou hlásit „zadej heslo znovu".
Bez klíče se heslo vůbec neuloží a formulář to řekne rovnou.

### Služba stahování pošty

Stahování běží jako **samostatná systemd služba**, ne ve web procesu:

```bash
sudo systemctl status greensie-email     # stav
sudo journalctl -u greensie-email -f     # co právě dělá
sudo systemctl restart greensie-email    # po změně kódu
```

Jednotka je v `deploy/greensie-email.service`. Důvod oddělení: pomalé IMAP volání uvnitř web procesu
dokáže appku dotlačit k 502 (zkušenost s konektorem), a jeden FETCH velké schránky trvá desítky
sekund. Důsledek, se kterým se počítá: **appka a stahování pošty se restartují nezávisle.** Když
služba neběží, appka funguje dál — jen se pošta nestahuje sama, a v UI je vidět čas posledního stažení.

Intervaly se dají přepsat v `.env`: `EMAIL_INTERVAL_INBOX_S` (výchozí 60), `EMAIL_INTERVAL_PLNY_S`
(výchozí 900).

Když schránka selže **třikrát za sebou**, worker ji odloží na 30 minut. Špatné heslo nemá smysl
zkoušet každou minutu — Seznam by nás mohl začít blokovat.

### Datový model

| Tabulka | Co drží |
|---|---|
| `crm_email_ucty` | Připojená schránka jednoho člověka (adresa, zašifrované heslo, servery, podpis, OOO, přeposílání) |
| `crm_email_slozky` | Zrcadlo složek na serveru. `imap_nazev` = surový název pro server, `nazev` = rozluštěný pro člověka |
| `crm_email_zpravy` | Hlavičky a náhled; těla se dotahují až při otevření (`telo_stazeno`) |
| `crm_email_prilohy` | Jen popis přílohy. **Obsah se neukládá** — tahá se z IMAPu na vyžádání |
| `crm_email_pravidla` | Pravidla pro příchozí poštu (sortování, přeposlání) |
| `crm_email_vazby` | Napojení zprávy na firmu / kontakt / případ („rejnetování") |
| `crm_email_auto_odpovedi` | Komu už odešla OOO odpověď — pojistka proti smyčce |

Dvě věci, které se snadno popletou:

- **`uid` není `id`.** UID je číslo zprávy **v rámci složky na serveru** a platí jen dokud se nezmění
  `uidvalidity` složky. Zprávy ze dvou složek klidně mají UID 1. Napříč schránkami se páruje přes
  `message_id`.
- **`uidvalidity`** je pojistka serveru. Když se změní, všechna UID přestala platit a cache složky se
  musí zahodit a stáhnout znovu. Bez téhle kontroly by se po přeindexování schránky u Seznamu začaly
  zprávy míchat mezi sebou — tichá a nedohledatelná chyba.

### Bezpečnost vykreslování HTML pošty

Tělo e-mailu je cizí HTML od kohokoli na internetu. Vykresluje se ve **`<iframe sandbox>` bez
`allow-scripts` a bez `allow-same-origin`**, takže rám nemá přístup ke stránce appky ani
k přihlašovacímu tokenu. Navíc běží sanitizace značek a `Content-Security-Policy` uvnitř rámu —
tři nezávislé pojistky, protože jedna se dá obejít překlepem.

**Nikdy** to nepřepisuj na `dangerouslySetInnerHTML`. Skript v mailu by pak běžel v přihlášené
session a odeslal si token; je to nejběžnější způsob, jak se webová pošta hackuje.

### Co se nikdy nesmí stát

- **Stahování nesmí označovat poštu přečtenou.** Všude se používá `BODY.PEEK[...]`, ne `BODY[...]`.
  Kdyby appka při synchronizaci odškrtala nepřečtenou poštu, člověk by o ni v mobilu přišel.
- **Účet se nikdy nebere z parametru URL.** Každý endpoint si ho hledá podle přihlášeného uživatele
  (`_muj_ucet`). Jakmile by se bral z URL, dala by se cizí schránka otevřít hádáním čísla.
- **Zápis příznaků jde nejdřív na server, pak do DB.** Obrácené pořadí by znamenalo, že appka tvrdí
  něco jiného než mobil a při další synchronizaci se to vrátí zpátky — uživatel by viděl, jak mu
  appka „samovolně" mění přečtenost.

### Nastavení schránky u Seznamu

| Protokol | Server | Port | Šifrování |
|---|---|---|---|
| IMAP (příjem) | `imap.seznam.cz` | 993 | SSL/TLS |
| SMTP (odesílání) | `smtp.seznam.cz` | **587** | STARTTLS |

> ⚠️ **Proč 587 a ne 465.** Seznam nabízí obojí, ale na Hetzneru (kde appka běží) je odchozí port
> **465 blokovaný** — ověřeno, spojení timeoutuje. Blokovaný je i port 25. Výchozí port schránky je
> proto **587 se STARTTLS**, stejně jako u firemního odesílání v `backend/app/mailer.py`. Kdyby někdo
> port v Nastavení schránky → Pokročilé přepsal na 465, odesílání by přestalo fungovat s timeoutem.
> Příjem (IMAP 993) blokovaný není.

### Související

- [CRM](?stranka=crm) — zákazníci, kontaktní osoby a obchodní případy, na které se pošta páruje
- [Společné prvky](?stranka=spolecne-prvky) — panel vlevo, kontextová nápověda
- [Konfigurace serveru](?stranka=server-konfigurace) — `.env` a šifrovací klíče
