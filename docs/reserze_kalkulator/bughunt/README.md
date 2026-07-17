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

1. **Koeficient AKU přepsat dle ERÚ** (optimistická větev pro baterie uvnitř odběru zmizí).
2. **Fair baseline u peak shavingu přidat** (optimalizovaná roční + měsíční RK bez
   baterie + výstup „úspora bez investice“); UI = rozpad úspory.
3. **„Cenu dodavatele“ v PPA rozložit** na silovou složku + vyhnutelné regulované složky
   (default 260 Kč/MWh z manažerského nastavení).
4. **Defaulty ekonomiky:** PPA LID −2 % (PERC), O&M 350 Kč/kWp/rok, diskont 7,5 %;
   PS účinnost RT 0,88, rezerva RK 5 %, O&M 2 % CAPEX/rok, diskont 8 %, horizont NPV
   10 let, degradace úspor 1,5 %/rok.
5. **Rezervovaný příkon:** přidat nepovinné pole (OZ ho mívá ze smlouvy o připojení)
   + přepínač snížení RP (default vypnuto).

## ✅ Stav implementace (16. 7. 2026, větev `bughunt-opravy-p0`)

**Všechny nálezy P0–P2 vyřešeny** (PS-1…PS-10, PPA-1…PPA-6+PPA-8, SP-1, SP-2) —
detail s odkazy na commity u jednotlivých nálezů. Testy: `backend/tests/`
(104 pytest testů). **P3 zůstává neimplementováno** (spotová arbitráž, kombinace
PPA+baterie, EDC sdílení, PVGIS API za runtime, jednosložková NTS cena, PPA-7
validace ceny přebytku, PPA-9 CAPEX pásma, SP-3 medián intervalu, SP-4 Status sloupec).

### Nasazení na produkci — checklist

1. **Sazby (automaticky):** seed při startu backendu doplní EG.D/PRE (2026 i NTS 2027)
   a cíleně opraví ČEZ řádky (`_BACKFILL_OPRAVY`: RK 2 847,72 → 3 030,78; VVN null →
   1 409,18; odstranění pokut 1108/521; doplnění měsíční RK). Ruční úpravy admina
   se nikdy nepřepisují — po deployi zkontrolovat v adminu poznámky „OPRAVA (audit
   16. 7. 2026)“.
2. **Migrace (automaticky):** `_lehka_migrace()` smaže duplicitní řádky profilů
   („poslední vyhrává“ = vyšší id) a založí unique index `(nabidka_id, cas)`.
3. **Manažerské nastavení (RUČNĚ v adminu):** nové defaulty platí, jen když klíč
   v `vypoctova_nastaveni.parametry` chybí. Pokud jsou na produkci uložené staré
   hodnoty, v adminu (Katalog a výpočty) vyprázdnit/nastavit: `ppa_oam_kc_kwp_rok`
   (350), `ppa_diskontni_sazba` (0.075), nové klíče se doplní samy defaulty —
   `ppa_degradace_rok1` (0.02), `ppa_vyhnutelne_regulovane_kc_mwh` (260),
   `ppa_index_regulovane_rocni` (0), `ppa_poze_kc_mwh` (0), `ppa_vymena_stridace_*`
   (vypnuto), `ps_cena_energie_kc_mwh` (3000), `ps_rezerva_rk_procenta` (5),
   `ps_diskontni_sazba` (0.08), `ps_horizont_npv_roky` (10),
   `ps_oam_procenta_capex_rok` (2), `ps_degradace_uspor_procenta_rok` (1.5).
4. **Katalog baterií (RUČNĚ):** doplnit `ucinnost` (AC-AC round-trip, např. 0,88)
   u bateriových produktů — bez ní platí default 0,88.
5. ✅ **Ověřeno 17. 7. 2026** (věstníky na https://eru.gov.cz/cenove-vymery):
   **CV 1/2026** (30. 4. 2026, účinnost 1. 6. 2026) mění CV 13/2025 jen v bodě (4.34)
   a části 24 — vyhodnocení RK u lokálních distribučních soustav s účastníky
   neplatícími RK dle § 54a odst. 2 PTE. Sazby RK (roční i měsíční) ani platby za
   překročení se nemění → bez dopadu na model. **CV 3/2026** (19. 6. 2026) mění jen
   CV 11/2025 (povinný výkup, záruky původu) — RK se netýká.

## Kalendář

- **říjen 2026** — veřejná konzultace ERÚ k parametrizaci koeficientu AKU.
- **~listopad 2026** — závazný cenový výměr 2027 → přepsat modelové seedy `nova_2027`.
- ~~Před nasazením oprav zkontrolovat změnový výměr CV 3/2026 (19. 6. 2026)~~ —
  ověřeno 17. 7. 2026, CV 1/2026 ani CV 3/2026 sazby RK nemění (viz checklist bod 5).
