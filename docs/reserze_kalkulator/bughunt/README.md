# Bughunt: nálezy auditu výpočtů PPA FVE + Peak shaving

Audit provedený **16. 7. 2026** nad `backend/app/nabidkovac/ppa_fve.py`,
`peak_shaving.py`, `routes.py`, `seed.py`, `profil_import.py` a frontend panely.
Podklady s ověřenými čísly: [../README.md](../README.md). Kvantifikace dopadů:
[synteticke-testy.md](synteticke-testy.md).

**Celkový verdikt:** implementace je čistá a odpovídá metodikám — vzorce v kódu sedí,
simulace jsou vnitřně konzistentní, předpoklady poctivě označené. Problém je v několika
**vstupních faktech** (sazby, mechanismus pokut, definice koeficientu AKU) a **metodických
předpokladech** (atribuce úspory, defaulty ekonomiky), které systematicky vychylují
prodejní čísla.

## Nálezy podle souborů

| Soubor | Obsah |
|---|---|
| [peak-shaving.md](peak-shaving.md) | Nálezy PS-1 … PS-10 (sazby, pokuty, AKU, RP, fyzika baterie, ekonomika, atribuce) |
| [ppa-fve.md](ppa-fve.md) | Nálezy PPA-1 … PPA-9 (bug max_kwp, kalibrace výroby, letní čas, úspora klienta, ekonomika investora) |
| [spolecne-profil-a-data.md](spolecne-profil-a-data.md) | Nálezy SP-1 … SP-4 (validace pokrytí roku, duplicitní profily, interval, status řádků) |
| [synteticke-testy.md](synteticke-testy.md) | Reprodukovatelné testy T1–T8 s naměřenými dopady + skript |

## Prioritizace oprav

**P0 — čísla jsou fakticky špatně (opravit před dalším obchodním použitím):**
1. Seed sazeb 2026: ČEZ VN roční RK 252,565 Kč/kW/měs (ne 237,31 = rok 2025), VVN 117,432; doplnit měsíční RK; doplnit EG.D + PRE. → PS-1
2. Mechanismus pokut za překročení RK: 1,5× měsíční cena měsíční RK (VN 422,73 / VVN 196,55 Kč/kW), ne 1 108/521 (to je překročení rezervovaného výkonu — směr do sítě). → PS-2
3. Koeficient AKU přepsat dle definice ERÚ (BTM baterie bez exportu → sleva 0). → PS-3
4. Validace pokrytí profilu ~12 měsíců + řešení duplicitních dokumentů. → SP-1, SP-2
5. Bug: sweep velikostí FVE překračuje `max_kwp` < 5. → PPA-1

**P1 — kalibrace a poctivé defaulty:**
6. PVGIS kalibrace výroby (výnos 1 055, měsíční tabulka, orientace) + posun letního času + LID. → PPA-2, PPA-3, PPA-4
7. PPA: rozklad „ceny dodavatele“ (silová + vyhnutelné regulované ~250–270 Kč/MWh); O&M 1–2 % CAPEX; diskont 7–8 %; flag záporného NPV. → PPA-5, PPA-6, PPA-8
8. PS: ztráty baterie do ekonomiky (katalog už má sloupec `ucinnost`!), rezerva RK 5–10 %, vstup „rezervovaný příkon“ + přepínač snížení RP pro 2027. → PS-5, PS-6, PS-4

**P2 — metodika, která zlepší doporučení:**
9. Fair baseline: optimalizovaná RK bez baterie (roční + měsíční kombinace) + výstup „úspora bez investice“. → PS-7
10. Výběr vítěze PS podle NPV na horizontu 2026→NTS (konzervativně), degradace úspor. → PS-8, PS-9
11. Walk-forward validace stropu (druhý rok dat / bootstrap ±5–10 % špiček). → PS-10

**P3 — rozšíření:** spotová arbitráž z OTE, kombinace PPA+baterie, EDC sdílení přebytků,
PVGIS API za runtime, jednosložková NTS cena pro < 600 h/rok.

## Rozhodnutí (Daniel, 16. 7. 2026)

- **Zatím se nic neimplementuje** — tento adresář slouží jako podklad, opravy proběhnou
  samostatně.
- Až se bude implementovat, je rozhodnuto:
  1. **Koeficient AKU přepsat dle ERÚ** (optimistická větev pro baterie uvnitř odběru zmizí).
  2. **Fair baseline u peak shavingu přidat** (optimalizovaná roční + měsíční RK bez
     baterie + výstup „úspora bez investice“).
  3. **„Cenu dodavatele“ v PPA rozložit** na silovou složku + vyhnutelné regulované složky
     (default ~250–270 Kč/MWh z manažerského nastavení).

**Otevřené (nerozhodnuté):** defaulty ekonomiky (O&M, diskont, LID, rezerva RK — návrhy
v nálezech), zda má OZ k dispozici rezervovaný příkon ze smlouvy o připojení (nový vstup
pro model 2027), pořadí implementace.

## Kalendář

- **říjen 2026** — veřejná konzultace ERÚ k parametrizaci koeficientu AKU.
- **~listopad 2026** — závazný cenový výměr 2027 → přepsat modelové seedy `nova_2027`.
- Před nasazením oprav zkontrolovat změnový výměr CV 3/2026 (19. 6. 2026) na
  https://eru.gov.cz/cenove-vymery.
