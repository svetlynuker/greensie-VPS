# Prompt pro Claude Code – Koeficient AKU + grafy odběru pro peak shaving

Kalkulátor pro peak shaving (2026 i 2027 s T1/T2) už funguje. Tenhle prompt řeší **dvě doplnění**: sleva pro baterie (Koeficient AKU) a vizualizace odběru v nabídce. Podrobný popis je v `docs/METODIKA-peak-shaving.md`, kap. 4.8 – přečti si ji před implementací, tady je shrnutí + přesné vzorce.

## Část A – Koeficient AKU (kap. 4.8 metodiky)

Od roku 2027 existuje na VN/VVN sleva na složku za naměřené maximum (M) pro bateriová úložiště, podle "účinnosti" provozu baterie v daném měsíci. Mechanismus je potvrzený, přesná definice účinnosti pro čistě peak-shavingovou baterii (bez exportu do sítě) ale **není ověřená** – bereme ji jako optimistický, jasně označený předpoklad.

**Vzorec:**

```
ucinnost_mesic = energie_vybito_kwh / energie_nabito_kwh     (ze simulace baterie, po měsících)

koeficient_aku = 0                                            když ucinnost ≤ U1
koeficient_aku = (ucinnost − U1) / (U2 − U1)                  když U1 < ucinnost < U2
koeficient_aku = 1                                             když ucinnost ≥ U2

M_kryto_baterii = min(M, celkovy_nabijeci_vykon_baterie)
M_zbytek = M − M_kryto_baterii

nakl_spicka_T1 = M_zbytek × T1_špička + M_kryto_baterii × T1_špička × (1 − koeficient_aku)
nakl_spicka_T2 = M_zbytek × T2_špička + M_kryto_baterii × T2_špička × (1 − koeficient_aku)

mesicni_naklad_2027 = min(RP × T1_kapacita + nakl_spicka_T1, RP × T2_kapacita + nakl_spicka_T2)
                       + max(0, M − RP) × sazba_prekroceni
```

Kde `U1 = 0,60`, `U2 = 0,75` pro VN a `0,70` pro VVN.

### Úkoly

1. Přidej do `sazby_distributoru.parametry` (`nova_2027`) pole `u1_ucinnost` (0,60 pro obě hladiny) a `u2_ucinnost` (0,75 VN / 0,70 VVN).
2. Uprav simulaci baterie (kap. 4.2 metodiky) tak, aby si pro každý měsíc ukládala i `energie_nabito_kwh` a `energie_vybito_kwh` (pravděpodobně už je počítá interně, jen to zatím nikam neukládá) – bude to potřeba i pro grafy v části B.
3. Uprav výpočet ekonomiky 2027 tak, aby počítal `koeficient_aku` po měsících a použil vzorec `mesicni_naklad_2027` výše místo dosavadního (bez koeficientu).
4. Do `navrhovana_reseni.popis_json` u `ekonomika_2027` přidej `predpoklad_aku_neoverovany: true` a průměrnou měsíční účinnost/slevu za rok, ať je jasně vidět, jak moc na tomto předpokladu nabídka staví.
5. V UI zobraz u čísel roku 2027 dobře viditelné upozornění (např. tooltip nebo poznámka pod částkou): "Zahrnuje nepotvrzený předpoklad slevy pro baterie (Koeficient AKU) – k ověření s manuálem ERÚ."

## Část B – Grafy odběru ze sítě (2026 a 2027)

K nabídce peak shaving přidej vizualizaci, která ukáže, jak se za rok očekává odběr ze sítě **bez baterie** (současný stav, ze vstupního profilu) vs. **s baterií** (po simulaci) – zvlášť v kontextu roku 2026 a zvlášť roku 2027 (i když je podkladová fyzika odběru stejná pro oba roky, ukaž graf u ekonomiky obou let, ať OZ nemusí přepínat mezi sekcemi).

### Úkoly

1. **Hlavní graf: měsíční maxima, bez baterie vs. s baterií.** Sloupcový nebo čárový graf, 12 měsíců na ose X, dvě série: naměřené měsíční maximum z původního profilu (bez baterie) a měsíční maximum po simulaci baterie (s baterií). Přidej i vodorovnou čáru/oblast pro sjednanou rezervovanou kapacitu/rezervovaný příkon (aktuální i nově navrhovanou), ať je vizuálně vidět, kde docházelo k překročení.
2. **Volitelný detail:** možnost prokliknout si jeden měsíc a zobrazit plnou 15minutovou křivku odběru za ten měsíc (bez baterie vs. s baterií) – užitečné pro vysvětlení konkrétní špičky zákazníkovi. Pokud by to bylo časově náročné, tenhle detail klidně nech jako "later" a implementuj jen hlavní měsíční graf.
3. Použij knihovnu, která už je v projektu zavedená pro grafy (pokud žádná není, Chart.js je rozumná volba – lehká, běžně používaná).
4. Graf umísti do výstupu nabídky u obou ekonomik (`ekonomika_2026` i `ekonomika_2027`), s popiskem roku.

## Co NEDĚLAT

- Neměň nic na hledání minimálního `T` (kap. 4.3) ani na základní simulaci baterie (kap. 4.2) – jen ji rozšiř o ukládání měsíčních součtů nabito/vybito.
- Nezaváděj EG.D/PRE sazby ani finální (nemodelová) čísla pro 2027 – to zůstává otevřené (viz metodika kap. 7).
- Neptej se na věci, které jsou v `METODIKA-peak-shaving.md` už rozhodnuté (označené ✅) – jen na to, co by implementaci skutečně bránilo.
