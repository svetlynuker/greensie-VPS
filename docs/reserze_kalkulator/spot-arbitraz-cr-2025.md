# Spotové ceny ČR 2025 a hodnota bateriové arbitráže — rešerše

Podklad pro rozšíření peak shaving kalkulátoru o režimy **Peak shaving / Kombinace / SPOT**
(zadání 28. 7. 2026). Všechny ceny **bez DPH**.

## 1. Zdroj dat a jeho ověření

- **Ceny:** `api.energy-charts.info/price?bzn=CZ` — day-ahead ceny české nabídkové zóny
  (EUR/MWh), tedy výsledek denního trhu OTE ve spojeném evropském sesouhlasení (SDAC).
- **Kurz:** denní kurzy ČNB (`cnb.cz/.../rok.txt?rok=2025`), EUR. Průměr 2025
  **24,691 CZK/EUR** (min 24,120, max 25,295).
- **Ověření proti OTE:** hodinové ceny z `ote-cr.cz/cs/kratkodobe-trhy/elektrina/denni-trh/@@chart-data`
  pro 15. 1. a 15. 6. 2025 se shodují **na 0,00 EUR/MWh**. Zdroj je tedy použitelný
  jako náhrada OTE (dostupný jedním requestem za celý rok, OTE jen po dnech).
- **Granularita:** denní trh v ČR přešel na **15minutové obchodní intervaly
  1. 10. 2025** (SDAC 15min MTU). Do 30. 9. 2025 jsou ceny hodinové — pro analýzu
  po čtvrthodinách se hodinová cena replikuje na 4 intervaly. Rok 2025 tedy dává
  **35 040 intervalů**, z toho reálně 15minutových je Q4.
  ⚠️ Roky 2026+ už budou 15minutové celé; roční profily zákazníků jsou 15minutové vždy.

## 2. Základní statistika DAM 2025 (Kč/MWh)

| Ukazatel | Hodnota |
|---|---|
| Průměr | **2 392** (96,83 EUR/MWh) |
| Medián | 2 419 |
| p1 / p5 / p10 | −288 / 9 / 573 |
| p90 / p95 / p99 | 3 654 / 4 184 / 6 140 |
| Minimum / maximum | −5 600 / 14 194 |
| Negativní intervaly | 1 293 = **323 h** (3,7 %) |
| Intervalů < 500 Kč/MWh | 3 356 (9,6 %) |
| Intervalů > 3 000 Kč/MWh | 8 634 (24,6 %) |

### Měsíčně

| Měsíc | Průměr | Medián | Min | Max | Neg. int. |
|---|---|---|---|---|---|
| 1 | 3 231 | 3 095 | 325 | 14 194 | 0 |
| 2 | 3 327 | 3 235 | 1 369 | 7 321 | 0 |
| 3 | 2 498 | 2 580 | −622 | 6 959 | 40 |
| 4 | 1 995 | 2 233 | −3 066 | 6 505 | 288 |
| 5 | 1 823 | 2 213 | −5 600 | 6 425 | 324 |
| 6 | 1 911 | 2 166 | −2 281 | 7 007 | 276 |
| 7 | 2 224 | 2 307 | −61 | 11 497 | 24 |
| 8 | 1 888 | 2 153 | −1 496 | 6 705 | 216 |
| 9 | 2 245 | 2 204 | −1 304 | 10 077 | 92 |
| 10 | 2 326 | 2 242 | −77 | 12 334 | 32 |
| 11 | 2 702 | 2 444 | −240 | 9 559 | 1 |
| 12 | 2 597 | 2 484 | 1 091 | 8 843 | 0 |

Zima je dražší v úrovni ceny, ale **arbitráž vydělává nejvíc na jaře a v září** —
rozhoduje rozkmit, ne úroveň (viz kap. 6).

### Denní profil (průměr Kč/MWh)

Trh je „solárně prohnutý" — nejlevněji se kupuje v poledním sedle, nejdráž prodává večer:

| Hodina | 00 | 03 | 07 | 10 | **13** | 16 | 19 | **20** | 23 |
|---|---|---|---|---|---|---|---|---|---|
| Kč/MWh | 2 307 | 2 091 | 3 008 | 1 894 | **1 371** | 2 280 | 3 658 | **3 517** | 2 386 |

Kde v dni padne cenové **minimum**: 13 h ve 109 dnech z 365, 14 h v 75, 23 h ve 41,
12 h ve 24. Kde **maximum**: 20 h ve 102 dnech, 19 h v 61, 18 h ve 47, 16 h ve 29,
8 h ve 27.

### Denní spread (max − min v rámci dne)

| p5 | p10 | p25 | medián | p75 | p90 | p95 |
|---|---|---|---|---|---|---|
| 1 329 | 1 562 | 2 097 | **3 083** | 4 134 | 5 687 | 6 620 |

Spread ≥ 1 000 Kč/MWh má 363 dnů (99 %), ≥ 1 500 Kč 336 dnů (92 %), ≥ 2 000 Kč
288 dnů (79 %). **Arbitrážní příležitost je prakticky každý den**, otázka je jen cena.

## 3. Hodnota arbitráže — metoda

Optimální plán nabíjení/vybíjení se počítá **dynamickým programováním nad stavem
nabití** po čtvrthodinách, den po dni (baterie začíná i končí den prázdná).
Perfektní znalost cen v rámci dne **není podvod** — výsledky denního trhu na zítřek
jsou známé dnes ve 13:00, takže denní plánovač s nimi reálně pracuje. Nadhodnocení
je jen v tom, že plán nepočítá s chybou predikce odběru (u kombinovaného režimu)
a nezahrnuje vnitrodenní trh (ten by hodnotu naopak zvýšil).

Round-trip účinnost **88 %** (stejný default jako peak shaving, `√RT` na každou stranu).
Výsledky jsou vztažené na **1 MWh kapacity**, takže čísla čti jako **Kč/kWh/rok**.

## 4. Hodnota při symetrických nákladech (citlivost)

Jednosměrný náklad = kolik se ztratí na každé straně obchodu proti spotové ceně:

| Jednosměrný náklad (Kč/MWh) | 2h baterie | cyklů/rok | 4h baterie | cyklů/rok |
|---|---|---|---|---|
| 0 | 1 117 | 636 | 766 | 469 |
| 200 | 879 | 498 | 587 | 376 |
| 400 | 688 | 396 | 445 | 284 |
| 700 | 476 | 274 | 296 | 191 |
| 1 000 | 327 | 202 | 192 | 140 |
| 1 500 | 155 | 115 | 82 | 65 |

## 5. Hodnota při skutečné ceně pro zákazníka

Model zadání: **nákup = spot + 200** (marže obchodníka, není naše) **+ regulované
složky za odebranou MWh**, **prodej = spot − 200**. Regulované složky přebírají
default z PPA modulu (`ppa_vyhnutelne_regulovane_kc_mwh` = **260 Kč/MWh** pro VN 2026:
použití sítí 83–106 dle DSO + systémové služby 164,24 + POZE 0 — u VN se POZE platí
z rezervované kapacity, ne z MWh).

| Regulované složky | 2h baterie | cyklů/rok | 4h baterie | cyklů/rok |
|---|---|---|---|---|
| 0 | 879 | 498 | 587 | 376 |
| 100 | 824 | 470 | 545 | 352 |
| **260** | **742** | **427** | **485** | 313 |
| 400 | 677 | 390 | 438 | 280 |

**Hrubá hodnota na MWh proteklou baterií:** 742 395 Kč / 427 MWh = **1 737 Kč/MWh
průchodu**. To je zároveň mez, pod kterou musí být náklad opotřebení, aby arbitráž
vydělávala.

## 6. Opotřebení baterie — zásadní položka

Spot přidává 300–500 cyklů ročně, tedy 2–3× víc, než odcykluje samotný peak shaving.
Náklad opotřebení = `CAPEX / (cykly životnosti × kapacita)` v Kč za MWh proteklou
baterií. Při nákupu spot+460 / prodeji spot−200:

| CAPEX Kč/kWh | Cyklů životnosti | Opotřebení Kč/MWh | 2h: Kč/kWh/rok | cyklů/rok | ziskových dnů | 4h: Kč/kWh/rok |
|---|---|---|---|---|---|---|
| — | — | 0 | 742 | 427 | 359 | 485 |
| 6 000 | 8 000 | 750 | 469 | 270 | 303 | 290 |
| 6 000 | 6 000 | 1 000 | 402 | 234 | 270 | 244 |
| **7 000** | **6 000** | **1 167** | **362** | **215** | 254 | **217** |
| 8 000 | 5 000 | 1 600 | 271 | 177 | 216 | 154 |

**Náklad opotřebení sám o sobě reguluje počet cyklů** — z 427 na 215 cyklů/rok.
Explicitní roční limit cyklů je tedy druhá pojistka (kvůli záruce), ne hlavní nástroj:

| Obchoduje se jen | Kč/kWh/rok | cyklů/rok | % z maxima |
|---|---|---|---|
| top 30 dnů | 123 | 32 | 34 % |
| top 60 dnů | 197 | 64 | 54 % |
| top 90 dnů | 253 | 93 | 70 % |
| top 120 dnů | 294 | 121 | 81 % |
| top 180 dnů | 347 | 177 | 96 % |
| všech 254 ziskových dnů | 362 | 215 | 100 % |

(2h baterie, opotřebení 1 167 Kč/MWh)

### Sezónnost výnosu arbitráže (2h, jednosměrný náklad 200, Kč/kWh za měsíc)

| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 53,5 | 42,3 | 83,1 | 91,9 | 94,6 | 100,9 | 54,4 | 81,6 | **113,8** | 89,4 | 47,8 | 25,5 |

Nejhorší je prosinec a únor (vysoká, ale plochá cena), nejlepší září a jaro. To je
**protifázové k peak shavingu**, jehož hodnota je nejvyšší v zimních měsících
s ročním maximem odběru — obě užití se tedy sezónně doplňují.

## 7. Kolize s peak shavingem

**Časově si obě užití překvapivě moc nelezou do cesty.** Průměrná cena v typických
oknech odběru:

| Okno | Průměr Kč/MWh | Medián |
|---|---|---|
| Prac. den 06–14 (denní směna) | 2 467 | 2 533 |
| Prac. den 08–16 | 2 164 | 2 186 |
| Prac. den 10–15 (solární sedlo) | **1 848** | 1 961 |
| Prac. den 14–22 | 2 966 | 2 928 |
| Prac. den 17–21 (špička trhu) | **3 539** | 3 297 |
| Prac. den 00–06 (noc) | 2 215 | 2 227 |
| Víkend | 1 923 | 2 233 |

Průmyslová špička odběru padá typicky do pracovního dne 8–16 h, kdy je elektřina
**nejlevnější** — peak shaving tedy „nekrade" spotu nejcennější hodiny (19–21 h),
kdy už většina provozů netočí.

**Cena za dělení baterie** (2h, náklad 200, jinak plný výkon/kapacita):

| Podíl kapacity pro spot | 100 % | 80 % | 60 % | 40 % | 20 % |
|---|---|---|---|---|---|
| Zbylá hodnota arbitráže | 100 % | 86 % | 71 % | 46 % | 24 % |

| Podíl výkonu pro spot | 100 % | 75 % | 50 % | 25 % |
|---|---|---|---|---|
| Zbylá hodnota arbitráže | 100 % | 87 % | 67 % | 34 % |

Ztráta je **podlineární** — půlka kapacity si drží 71 % hodnoty. Kombinovaný režim
tedy má smysl: peak shaving obvykle potřebuje plnou baterii jen v několika
čtvrthodinách měsíce.

**Skutečné riziko není energie, ale měsíční maximum.** Jediná čtvrthodina, kdy je
baterie vybitá do sítě a přijde špička, může zvednout měsíční maximum a smazat
úsporu za celý měsíc. Proto rozhodovací vrstva musí pracovat s cenou překročení,
ne jen s cenou energie.

## 8. Řádové srovnání obou hodnot

Peak shaving na sazbách NTS 2027 (ČEZ VN, T1: kapacita 190,133 + špička
19,013 Kč/kW/měsíc) při ideálním sražení celého výkonu každý měsíc:

| Baterie na 1 MWh | Peak shaving (ideální) | Spot (reálné náklady, opotř. 1 167) |
|---|---|---|
| 2h (500 kW) | ~1 255 Kč/kWh/rok | 362 Kč/kWh/rok |
| 4h (250 kW) | ~627 Kč/kWh/rok | 217 Kč/kWh/rok |

Peak shaving je tedy u vhodného profilu **hlavní hodnota** a spot **přírůstek řádu
20–40 %** — u 330kWh baterie ~120 tis. Kč/rok, což návratnost zkrátí znatelně.
U profilu, kde peak shaving nedává smysl (plochý odběr), naopak spot může být
jediný důvod baterii postavit — proto samostatný režim SPOT.

## 9. Co analýza záměrně nepokrývá

- **Vnitrodenní trh (ID)** a **podpůrné služby (aFRR/mFRR/FCR)** — v ČR dnes tvoří
  většinu reálného výnosu bateriových projektů. Mimo scope zadání (jen spot),
  ale hodnota by byla vyšší, ne nižší.
- **Chyba predikce odběru** u kombinovaného režimu — model plánuje s reálným
  profilem, provoz s predikcí.
- **Daň z elektřiny** (28,30 Kč/MWh) — u akumulace je otázka osvobození; ponecháno
  jako parametr k ověření (default 0).
- **Rezervovaný výkon pro dodávku do sítě** a licenční podmínky exportu — export
  se v modelu omezuje parametrem, poplatky za rezervovaný výkon dodávky nejsou
  zahrnuty (TO VERIFY).
- **Koeficient AKU (NTS 2027)** — u baterie, která do sítě dodává, už podíl
  export/import není nulový, takže sleva na platbu za maximální odebraný výkon
  by nemusela být nulová. **Rozhodnuto 28. 7. 2026: konzervativně K = 0 i pro
  spotové režimy** (prahy U1/U2 jsou předběžné, VKP ERÚ 10/2026) — stejně jako
  u čistého peak shavingu (bughunt PS-3).

## 10. Reprodukce

Stažení dat: `python -m scripts.import_spot_ceny --rok 2025 --csv` (v `backend/`) —
stáhne ceny z energy-charts i denní kurzy ČNB a uloží
`backend/app/nabidkovac/data/spot_dam_cz_2025.csv.gz`, odkud appka ceny seeduje.

Analýza: `docs/reserze_kalkulator/skripty/spot_analyza.py` (statistika + optimální
arbitráž dynamickým programováním). Appka sama používá **prahovou strategii**
(`spot_arbitraz.py`), protože ta je proveditelná v reálném provozu; číslo z DP je
horní odhad, proti kterému se poměřuje (testy hlídají aspoň 90 % optima).
