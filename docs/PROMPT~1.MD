# Prompt pro Claude Code – doplnění roku 2027 do peak shaving kalkulátoru

Kalkulátor pro peak shaving (ČEZ Distribuce, rok 2026) už je hotový a funkční. Tenhle prompt řeší **jen doplnění**: přidat k výsledku i modelovou ekonomiku pro rok 2027 podle nové tarifní struktury ERÚ. Podrobný popis je v `docs/METODIKA-peak-shaving.md`, kap. 4.6 a 4.7 – přečti si je před implementací, tady je jen shrnutí + konkrétní čísla k zadání.

## Co se mění od 2027 (jen VN/VVN)

Místo "rezervovaná kapacita + pokuta za překročení" (2026) nastupuje dvousložkový model: **rezervovaný příkon (RP)** + **naměřené měsíční maximum (M)**, se dvěma tarify T1/T2, kde se každý měsíc automaticky použije levnější varianta. Navíc zůstává penalizace, pokud M přesáhne RP.

Vzorec pro měsíční náklad:
```
min(RP × T1_kapacita + M × T1_špička, RP × T2_kapacita + M × T2_špička) + max(0, M − RP) × sazba_prekroceni
```
Roční náklad 2027 = součet za 12 měsíců.

**Simulace baterie se nemění.** Používá se stejný výsledek jako pro 2026 (minimální udržitelné `T` = nová RP + měsíční maxima po baterii z existující simulace, kap. 4.2–4.3 metodiky) – jen se dosadí do vzorce výše místo do vzorce pro 2026.

## Úkoly

1. **Rozšiř `sazby_distributoru`** o strukturu `nova_2027` pro ČEZ Distribuce, VN a VVN, s parametry (modelové/informativní hodnoty, bez DPH):

   | Hladina | Tarif | Kapacita (Kč/kW/měsíc) | Špička (Kč/kW/měsíc) |
   |---|---|---|---|
   | VN | T1 | 190,133 | 19,013 |
   | VN | T2 | 22,743 | 227,429 |
   | VVN | T1 | 96,862 | 9,686 |
   | VVN | T2 | 11,586 | 115,862 |

   Penalizace za překročení RP: VN 761 Kč/kW/měsíc, VVN 387 Kč/kW/měsíc (= 4× T1 kapacita dané hladiny).

   Přidej k těmto řádkům příznak `je_modelovy_odhad = true` (nové boolean pole na `sazby_distributoru`) – čísla nejsou finální, ERÚ vydá závazné cenové rozhodnutí až v listopadu 2026. `platne_od` nastav na 2027-01-01.

2. **Uprav výpočet ekonomiky** tak, aby pro VN/VVN zákazníky vracel ekonomiku **za oba roky zvlášť** (2026 podle stávajícího vzorce, 2027 podle vzorce výše), ne jen za jeden rok. Struktura výstupu v `navrhovana_reseni.popis_json` nově obsahuje pole `ekonomika_2026` a `ekonomika_2027` (každé: současný roční náklad, nový roční náklad, roční úspora), přičemž `ekonomika_2027` navíc nese `je_modelovy_odhad: true`.

3. **Přidej rozpad T1/T2 pro rok 2027**: kolik měsíců v roce (po nasazení baterie) vyjde levněji T1 a kolik T2 (`pocet_mesicu_t1`, `pocet_mesicu_t2` v `ekonomika_2027`).

4. **UI**: u výsledku nabídky pro VN/VVN zobraz obě ekonomiky vedle sebe (2026 / 2027), u 2027 viditelně označ "modelový odhad, ne finální cena ERÚ" (např. badge/ikona u čísla). Přidej krátké vysvětlení pro OZ (statický text, ne dynamicky generovaný): "Tarif T1 (dražší paušál, levná špička) obvykle vyjde levněji při provozu naplno blízko rezervovanému příkonu. Tarif T2 (levný paušál, drahá špička) vyjde levněji při utlumeném provozu nebo velké rezervě. Zákazník si tarif nevybírá, distributor ho určuje automaticky každý měsíc podle skutečné spotřeby."

5. Peak shaving pro NN appka nenabízí (beze změny, jen pro jistotu ověř, že se `nova_2027` nikde nesnaží aplikovat na NN záznamy, kdyby náhodou v datech byly).

## Co NEDĚLAT

- Neměň nic na simulaci baterie ani na logice hledání minimálního `T` (kap. 4.2–4.3 metodiky) – ta zůstává stejná pro oba roky.
- Nezaváděj EG.D/PRE sazby pro 2027 – zatím máme modelová čísla jen pro ČEZ Distribuce.
- Neptej se na věci, které jsou v `METODIKA-peak-shaving.md` už rozhodnuté – jen na to, co by bránilo implementaci.
