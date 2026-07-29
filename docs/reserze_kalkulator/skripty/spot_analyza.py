"""Analýza spotových cen ČR a hodnoty bateriové arbitráže (rešerše 28. 7. 2026).

Podklad pro `docs/reserze_kalkulator/spot-arbitraz-cr-2025.md`. Spouští se ručně,
mimo appku (čistý Python, bez závislostí):

    python -m scripts.import_spot_ceny --rok 2025 --csv   # v backend/, stáhne data
    python docs/reserze_kalkulator/skripty/spot_analyza.py

Očekává v pracovním adresáři `cz_2025.json` (ceny z api.energy-charts.info) a
`cnb2025.txt` (denní kurzy ČNB). Optimální arbitráž se počítá dynamickým
programováním nad stavem nabití – appka sama používá prahovou strategii
(`spot_arbitraz.py`), tohle je horní odhad, proti kterému se poměřuje.
"""

import json, datetime, statistics
from collections import defaultdict

PRAHA = datetime.timezone(datetime.timedelta(hours=1))  # jen pro hrubé dělení dne použijeme UTC+1/+2 dle DST


def load_kurzy(path):
    kurzy = {}
    with open(path, encoding="utf-8") as f:
        hlavicka = f.readline().strip().split("|")
        idx = hlavicka.index("1 EUR")
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = line.split("|")
            d = datetime.datetime.strptime(c[0], "%d.%m.%Y").date()
            kurzy[d] = float(c[idx].replace(",", "."))
    return kurzy


def load_ceny(path):
    d = json.load(open(path))
    return list(zip(d["unix_seconds"], d["price"]))


def dst_offset(ts):
    """Praha: CET/CEST. Jednoduše: DST od poslední březnové do poslední říjnové neděle."""
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    y = dt.year
    # poslední nedělní březen 01:00 UTC / poslední nedělní říjen 01:00 UTC
    def posledni_nedele(rok, mesic):
        d = datetime.date(rok, mesic, 31)
        while d.weekday() != 6:
            d -= datetime.timedelta(days=1)
        return datetime.datetime(d.year, d.month, d.day, 1, 0, tzinfo=datetime.timezone.utc)
    start = posledni_nedele(y, 3)
    end = posledni_nedele(y, 10)
    return 2 if start <= dt < end else 1


def na_15min(body):
    """Rozpad hodinových hodnot na 4×15min; vrací seznam (dt_praha_naive, cena_eur)."""
    out = []
    for i, (ts, cena) in enumerate(body):
        if cena is None:
            continue
        krok = (body[i + 1][0] - ts) if i + 1 < len(body) else 900
        n = max(1, min(4, round(krok / 900)))
        for k in range(n):
            t = ts + k * 900
            off = dst_offset(t)
            dtl = datetime.datetime.fromtimestamp(t, datetime.timezone.utc) + datetime.timedelta(hours=off)
            out.append((dtl.replace(tzinfo=None), float(cena)))
    return out


def arbitraz_dp(ceny_kc, kapacita_kwh, vykon_kw, rt=0.88, interval_h=0.25,
                marze_kc_mwh=200.0, kroku_soc=40, max_cyklu_den=None):
    """Optimální plán nabíjení/vybíjení s perfektní předvídavostí (DP nad SOC).

    ceny_kc: seznam cen Kč/MWh (spot) pro jednotlivé intervaly jednoho úseku (den).
    Nákup = spot + marže, prodej = spot - marže.
    Vrací (zisk_kc, nabito_kwh, vybito_kwh).
    """
    n = len(ceny_kc)
    if n == 0 or kapacita_kwh <= 0 or vykon_kw <= 0:
        return 0.0, 0.0, 0.0
    eta = rt ** 0.5
    # Krok SOC volíme jako podíl energie, kterou baterie zvládne za interval,
    # aby se výkonový limit nezaokrouhloval (jinak by 4h baterie vyšla hůř).
    max_kwh_interval = vykon_kw * interval_h
    max_kroku = 2
    krok_kwh = max_kwh_interval / max_kroku
    kroku_soc = max(1, int(round(kapacita_kwh / krok_kwh)))

    NEG = float("-inf")
    # stav: úroveň SOC 0..kroku_soc; hodnota = max kumulovaný zisk
    V = [NEG] * (kroku_soc + 1)
    V[0] = 0.0  # den začíná prázdná (pro arbitráž), končí prázdná
    # sledování energií: uložíme (zisk, nabito, vybito)
    N = [0.0] * (kroku_soc + 1)
    D = [0.0] * (kroku_soc + 1)
    for cena in ceny_kc:
        nV = [NEG] * (kroku_soc + 1)
        nN = [0.0] * (kroku_soc + 1)
        nD = [0.0] * (kroku_soc + 1)
        c_nakup = cena + marze_kc_mwh
        c_prodej = cena - marze_kc_mwh
        for s in range(kroku_soc + 1):
            if V[s] == NEG:
                continue
            for d in range(-max_kroku, max_kroku + 1):
                s2 = s + d
                if s2 < 0 or s2 > kroku_soc:
                    continue
                if d > 0:  # nabíjení: do baterie d*krok, ze sítě d*krok/eta
                    ze_site_kwh = d * krok_kwh / eta
                    if ze_site_kwh > max_kwh_interval + 1e-9:
                        continue
                    zisk = -ze_site_kwh / 1000.0 * c_nakup
                    nab, vyb = ze_site_kwh, 0.0
                elif d < 0:  # vybíjení: z baterie -d*krok, do sítě -d*krok*eta
                    do_site_kwh = -d * krok_kwh * eta
                    if do_site_kwh > max_kwh_interval + 1e-9:
                        continue
                    zisk = do_site_kwh / 1000.0 * c_prodej
                    nab, vyb = 0.0, do_site_kwh
                else:
                    zisk, nab, vyb = 0.0, 0.0, 0.0
                nova = V[s] + zisk
                if nova > nV[s2]:
                    nV[s2] = nova
                    nN[s2] = N[s] + nab
                    nD[s2] = D[s] + vyb
        V, N, D = nV, nN, nD
    # konec: baterie prázdná (nejvíc hodnoty se realizuje prodejem)
    best = 0
    for s in range(kroku_soc + 1):
        if V[s] > V[best]:
            best = s
    return V[0] if V[0] != NEG else 0.0, N[0], D[0]


def main():
    kurzy = load_kurzy("cnb2025.txt")
    body = load_ceny("cz_2025.json")
    rada = na_15min(body)
    # jen rok 2025 v lokálním čase
    rada = [(d, c) for d, c in rada if d.year == 2025]
    print(f"intervalů 2025: {len(rada)} (očekáváno 35040)")

    # kurz: doplň chybějící dny (víkendy) poslední známou hodnotou
    kurz_dne = {}
    posledni = 25.0
    d0 = datetime.date(2025, 1, 1)
    for i in range(365):
        d = d0 + datetime.timedelta(days=i)
        posledni = kurzy.get(d, posledni)
        kurz_dne[d] = posledni
    prumer_kurz = statistics.mean(kurz_dne.values())
    print(f"kurz EUR/CZK 2025: průměr {prumer_kurz:.3f}, min {min(kurz_dne.values()):.3f}, max {max(kurz_dne.values()):.3f}")

    # ceny v Kč/MWh
    rada_kc = [(d, c * kurz_dne[d.date()]) for d, c in rada]
    ceny = [c for _, c in rada_kc]
    ceny_eur = [c for _, c in rada]

    print("\n=== ZÁKLADNÍ STATISTIKY (DAM CZ 2025, Kč/MWh bez DPH) ===")
    print(f"průměr        {statistics.mean(ceny):8.1f} Kč/MWh   ({statistics.mean(ceny_eur):6.2f} EUR/MWh)")
    print(f"medián        {statistics.median(ceny):8.1f}")
    print(f"min           {min(ceny):8.1f}   max {max(ceny):8.1f}")
    kv = sorted(ceny)
    for p in (1, 5, 10, 25, 75, 90, 95, 99):
        print(f"p{p:<3}          {kv[int(len(kv)*p/100)]:8.1f}")
    neg = sum(1 for c in ceny if c < 0)
    print(f"negativních intervalů: {neg} ({neg/len(ceny)*100:.1f} %), tj. {neg*0.25:.0f} h")
    print(f"intervalů < 500 Kč/MWh: {sum(1 for c in ceny if c < 500)} ({sum(1 for c in ceny if c<500)/len(ceny)*100:.1f} %)")
    print(f"intervalů > 3000 Kč/MWh: {sum(1 for c in ceny if c > 3000)} ({sum(1 for c in ceny if c>3000)/len(ceny)*100:.1f} %)")
    print(f"intervalů > 5000 Kč/MWh: {sum(1 for c in ceny if c > 5000)}")

    print("\n=== MĚSÍČNĚ ===")
    po_mesici = defaultdict(list)
    for d, c in rada_kc:
        po_mesici[d.month].append(c)
    print("měsíc  průměr   medián   min      max     neg.int")
    for m in range(1, 13):
        v = po_mesici[m]
        print(f"{m:5d}  {statistics.mean(v):7.0f} {statistics.median(v):8.0f} {min(v):8.0f} {max(v):8.0f} {sum(1 for x in v if x<0):8d}")

    print("\n=== PROFIL DNE (průměr Kč/MWh po hodinách) ===")
    po_hod = defaultdict(list)
    for d, c in rada_kc:
        po_hod[d.hour].append(c)
    for h in range(24):
        v = po_hod[h]
        bar = "#" * int(statistics.mean(v) / 60)
        print(f"{h:02d}:00 {statistics.mean(v):7.0f}  {bar}")

    print("\n=== DENNÍ SPREAD (max-min v rámci dne, Kč/MWh) ===")
    po_dni = defaultdict(list)
    for d, c in rada_kc:
        po_dni[d.date()].append(c)
    spready = sorted((max(v) - min(v)) for v in po_dni.values())
    print(f"dnů: {len(spready)}")
    print(f"průměr spread {statistics.mean(spready):.0f}, medián {statistics.median(spready):.0f}")
    for p in (5, 10, 25, 50, 75, 90, 95):
        print(f"  p{p:<3} {spready[int(len(spready)*p/100)]:7.0f}")
    for prah in (400, 600, 800, 1000, 1500, 2000):
        n = sum(1 for s in spready if s >= prah)
        print(f"  dnů se spreadem >= {prah:5d}: {n:3d} ({n/len(spready)*100:.0f} %)")

    print("\n=== OPTIMÁLNÍ ARBITRÁŽ (perfektní předvídavost, den po dni) ===")
    print("konfigurace: kapacita 1000 kWh (na 1 MWh) různé C-raty, RT 88 %")
    dny = sorted(po_dni.keys())
    for hodin_baterie, popis in ((1, "1h (1C)"), (2, "2h (0,5C)"), (4, "4h (0,25C)")):
        for marze in (0.0, 200.0):
            kap = 1000.0
            vyk = kap / hodin_baterie
            zisk_rok = 0.0
            nabito_rok = 0.0
            vybito_rok = 0.0
            dny_aktivni = 0
            for d in dny:
                z, nab, vyb = arbitraz_dp(po_dni[d], kap, vyk, rt=0.88, marze_kc_mwh=marze, kroku_soc=20)
                zisk_rok += z
                nabito_rok += nab
                vybito_rok += vyb
                if z > 1:
                    dny_aktivni += 1
            cyklu = nabito_rok * 0.88 / kap
            print(f"  {popis:9s} marže {marze:5.0f} Kč/MWh → {zisk_rok:10.0f} Kč/rok = "
                  f"{zisk_rok/kap:6.0f} Kč/kWh/rok | cyklů {cyklu:5.1f} | aktivních dnů {dny_aktivni:3d}")


if __name__ == "__main__":
    main()
