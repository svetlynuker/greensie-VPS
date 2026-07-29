"""Obchodní flexibilita baterie na spotovém trhu (režimy Kombinace / SPOT).

Navazuje na `peak_shaving.py` (fyzika baterie, ekonomika rezervované kapacity)
a na `spot_ceny.py` (data denního trhu). Rešerše s čísly a metodikou:
`docs/reserze_kalkulator/spot-arbitraz-cr-2025.md`.

Tři režimy, které si OZ volí u výpočtu:

| Režim | Co baterie dělá | Cílový síťový strop |
|---|---|---|
| `peak_shaving` | jen sráží špičky (dnešní chování, výchozí) | nejnižší udržitelný |
| `kombinace` | sráží špičky a ve zbytku obchoduje | **volí se ekonomicky** |
| `spot` | jen obchoduje | naměřené maximum (nesmí ho zvýšit) |

## Cena pro zákazníka

Marže 200 Kč/MWh není naše, ale obchodníkova (rozhodnuto se zadavatelem
28. 7. 2026): rozdíl proti spotu je vždy 200 Kč na každou stranu. K nákupu se
navíc přičítají regulované složky za odebranou MWh, protože model má počítat
**skutečnou cenu, kterou zákazník zaplatí a kterou dostane**:

    nákup  = spot + marže + regulované složky (+ daň z elektřiny)
    prodej = spot − marže − případné složky za dodávku

Z toho plyne věc, která je pro ekonomiku klíčová: **krytí vlastní spotřeby je
cennější než dodávka do sítě.** Když baterie vybije do odběru, zákazník se
vyhne celé nákupní ceně (včetně regulovaných složek); když dodá do sítě,
dostane jen spot mínus marže. Model proto vybíjí nejdřív do odběru a teprve
přebytek exportuje.

## Rozhodovací vrstva

Hodnota peak shavingu není cena energie, ale **měsíční maximum** – jeden skalár
za celý měsíc. Lokální rozhodnutí „teď prodám, cena je vysoko" proto nejde
ocenit, dokud není známé, jaké maximum v měsíci padne. Model to řeší dvěma
úrovněmi:

1. **Volba měsíčního cílového stropu** (`simuluj_rok`): pro každý měsíc se
   zkusí kandidátní stropy od nejnižšího udržitelného až po naměřené maximum
   a vybere se ten, kde je `úspora na platbě za výkon + výnos obchodu`
   největší. Model tedy sám najde měsíce, kde se vyplatí špičku pustit výš,
   protože obchod vydělá víc, než stojí vyšší platba za výkon. Výchozím bodem
   hledání je dnešní chování (nejnižší udržitelné stropy), takže kombinovaný
   režim nikdy nevyjde horší než čistý peak shaving.
2. **Rozhodování po čtvrthodinách** (`simuluj_usek`): spojitá simulace, kde
   peak shaving má v každém intervalu absolutní přednost a obchod dostane jen
   zbylý výkon a kapacitu **nad minimální trajektorií nabití**
   (`minimalni_soc_trajektorie`) – tedy nad tím, co baterie potřebuje na
   sražení všech budoucích špiček.

Obchodní rozhodnutí řídí **cenové prahy** kalibrované na každý den zvlášť
(`optimalizuj_prahy`): nabíjej v nejlevnějších hodinách dne, vybíjej
v nejdražších, a jen když rozdíl pokryje ztráty, marže i opotřebení. Je to
schválně strategie, kterou umí i reálná řídicí jednotka – ne teoretické
optimum, které by šlo spočítat jen se znalostí celého roku dopředu. Proti
optimálnímu plánu (dynamické programování, měřeno při vývoji) ztrácí jednotky
procent, zato nikdy nespoléhá na to, že se budoucnost odhadne přesně.

Perfektní znalost cen **v rámci dne není podvod**: výsledky denního trhu na
zítřek jsou známé dnes ve 13:00. Zjednodušení je, že model plánuje s reálným,
ne predikovaným odběrem – proto `bezpecnostni_rezerva_procenta`, která obchodu
ubere část kapacity na krytí chyby predikce.

Všechny peněžní hodnoty jsou bez DPH.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.nabidkovac import peak_shaving

# ---------------------------------------------------------------- konstanty
REZIM_PEAK_SHAVING = "peak_shaving"
REZIM_KOMBINACE = "kombinace"
REZIM_SPOT = "spot"
REZIMY = (REZIM_PEAK_SHAVING, REZIM_KOMBINACE, REZIM_SPOT)
VYCHOZI_REZIM = REZIM_PEAK_SHAVING

# Marže obchodníka nad/pod spotem, Kč/MWh bez DPH (zadání 28. 7. 2026).
VYCHOZI_MARZE_KC_MWH = 200.0

# Regulované složky za MWh **odebranou ze sítě** (Kč/MWh bez DPH). Default
# přebírá hodnotu z PPA modulu (`ppa_fve.VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH`
# = 260): VN 2026 = použití sítí 83–106 dle DSO + systémové služby 164,24 +
# POZE 0 (u VN se POZE platí z rezervované kapacity, ne z MWh).
VYCHOZI_REGULOVANE_NAKUP_KC_MWH = 260.0

# Složky za MWh **dodanou do sítě** – dodávka distribuci neplatí, default 0.
VYCHOZI_REGULOVANE_PRODEJ_KC_MWH = 0.0

# Daň z elektřiny 28,30 Kč/MWh: u akumulace je otázka osvobození (energie
# uložená a vrácená do sítě není konečná spotřeba) → default 0 a parametr
# k ověření (TO VERIFY, viz rešerše kap. 9).
VYCHOZI_DAN_Z_ELEKTRINY_KC_MWH = 0.0

# Počet ekvivalentních plných cyklů, které baterie vydrží. Fallback, když ho
# produkt nemá v katalogu (`technologie.extra.cyklu_zivotnosti`). 6 000 cyklů
# při 80 % DoD je běžná garance LFP kontejnerů.
VYCHOZI_CYKLU_ZIVOTNOSTI = 6000

# Kolik využitelné kapacity si peak shaving drží jako rezervu proti chybě
# predikce odběru (obchod ji nesmí použít). 0 = plánuje se s dokonalou
# znalostí odběru, což je pro nabídku moc optimistické.
VYCHOZI_BEZPECNOSTNI_REZERVA_PROCENTA = 10.0

# Kolik kandidátních stropů se v každém měsíci zkouší (rozhodovací vrstva):
# nejnižší udržitelný + kroky k naměřenému maximu. Čas výpočtu roste lineárně
# s tímhle číslem, protože každý kandidát znamená odsimulovat celý měsíc.
POCET_KANDIDATU_STROPU = 3

# Kolik průchodů souřadnicového zlepšování volby měsíčních stropů.
_MAX_ITERACI_VOLBY = 3

# Kolik pokusů o dodržení ročního limitu cyklů (zvyšováním nákladu opotřebení).
_MAX_ITERACI_LIMITU_CYKLU = 5

# Řady, které se zapisují do průběhu pro nitkový graf (`simuluj_usek(zapisuj=True)`).
_KLICE_PRUBEHU = (
    "site_kw",
    "baterie_kw",
    "baterie_ps_kw",
    "baterie_obchod_kw",
    "soc_pct",
    "cena_kc_mwh",
    "stropy_kw",
)

# Kalibrace denních cenových prahů (`optimalizuj_prahy`) probíhá ve dvou
# průchodech: hrubá mřížka percentilů, pak zjemnění o `KROK_ZJEMNENI` kolem
# nejlepšího nálezu. Plná mřížka 4×4 dávala stejné výsledky za dvojnásobek
# času – u celého ceníku baterií to je rozdíl desítek sekund.
PERCENTILY_NAKUP = (15.0, 35.0)
PERCENTILY_PRODEJ = (65.0, 85.0)
KROK_ZJEMNENI = 10.0


@dataclass
class NastaveniSpot:
    """Parametry obchodování; vše z manažerského nastavení (`spot_*`)."""

    marze_nakup_kc_mwh: float = VYCHOZI_MARZE_KC_MWH
    marze_prodej_kc_mwh: float = VYCHOZI_MARZE_KC_MWH
    regulovane_nakup_kc_mwh: float = VYCHOZI_REGULOVANE_NAKUP_KC_MWH
    regulovane_prodej_kc_mwh: float = VYCHOZI_REGULOVANE_PRODEJ_KC_MWH
    dan_z_elektriny_kc_mwh: float = VYCHOZI_DAN_Z_ELEKTRINY_KC_MWH
    cyklu_zivotnosti: int = VYCHOZI_CYKLU_ZIVOTNOSTI
    # Pojistka záruky: max. ekvivalentních plných cyklů za rok (None = bez
    # limitu). Náklad opotřebení počet cyklů reguluje sám (rešerše kap. 6),
    # tohle je druhá pojistka pro případ, že to vyžaduje smlouva o záruce.
    max_cyklu_rok: float | None = None
    # Dodávka do sítě: povolena a čím omezená (kW). None = výkonem baterie.
    umoznit_export: bool = True
    max_export_kw: float | None = None
    bezpecnostni_rezerva_procenta: float = VYCHOZI_BEZPECNOSTNI_REZERVA_PROCENTA


def cena_nakup_kc_mwh(spot_kc_mwh: float, n: NastaveniSpot) -> float:
    """Co zákazník za MWh ze sítě skutečně zaplatí (bez DPH)."""
    return (
        spot_kc_mwh
        + n.marze_nakup_kc_mwh
        + n.regulovane_nakup_kc_mwh
        + n.dan_z_elektriny_kc_mwh
    )


def cena_prodej_kc_mwh(spot_kc_mwh: float, n: NastaveniSpot) -> float:
    """Co zákazník za MWh dodanou do sítě skutečně dostane (bez DPH)."""
    return spot_kc_mwh - n.marze_prodej_kc_mwh - n.regulovane_prodej_kc_mwh


def naklad_opotrebeni_kc_mwh(
    cena_baterie_kc: float, kapacita_kwh: float, cyklu_zivotnosti: int | None
) -> float:
    """Cena opotřebení za MWh proteklou baterií (Kč/MWh bez DPH).

    `CAPEX / (cykly × kapacita)`. Obchodování přidává 300–500 cyklů ročně, tedy
    2–3× víc než samotný peak shaving, takže bez téhle položky by model
    doporučoval nesmyslně velké baterie (rešerše kap. 6). Účtuje se jen za
    **obchodní** energii, ne za srážení špiček – ekonomika peak shavingu se tím
    proti dnešnímu stavu nemění a je vidět, co obchod přináší netto.
    """
    cyklu = cyklu_zivotnosti or VYCHOZI_CYKLU_ZIVOTNOSTI
    if cena_baterie_kc <= 0 or kapacita_kwh <= 0 or cyklu <= 0:
        return 0.0
    return cena_baterie_kc / (cyklu * kapacita_kwh) * 1000.0


# ------------------------------------------------- co si peak shaving drží
def minimalni_soc_trajektorie(
    odber_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
) -> list[float]:
    """Kolik energie musí baterie mít v každém intervalu kvůli peak shavingu.

    Zpětný průchod úsekem: v intervalu nad stropem potřebuje baterie navíc
    energii na sražení špičky, v intervalu pod stropem si může část potřeby
    dobít (`strop − odběr`, max. výkonem). Výsledek je **dolní hranice stavu
    nabití** – co je nad ní, může obchod bez rizika použít.

    Díky téhle hranici nemusí obchodní logika o peak shavingu nic vědět: stačí
    pod ni nikdy nesáhnout. Vrací seznam délky `len(odber_kw)`, prvek `i` =
    minimální SOC (kWh) na začátku intervalu `i`.
    """
    eta = math.sqrt(max(1e-9, min(1.0, ucinnost_rt)))
    n = len(odber_kw)
    minimum = [0.0] * n
    potreba = 0.0  # kolik SOC je potřeba na začátku následujícího intervalu
    for i in range(n - 1, -1, -1):
        odber = odber_kw[i]
        if odber > strop_kw:
            # Špička: energie z baterie (na AC straně odběr − strop) + ztráty.
            potreba += (odber - strop_kw) * interval_h / eta
        else:
            # Prostor pod stropem – část potřeby se dá dobít, takže na začátku
            # intervalu jí musí být v baterii o tolik méně.
            dobiti = min(strop_kw - odber, vykon_kw) * interval_h * eta
            potreba = max(0.0, potreba - dobiti)
        potreba = min(potreba, kapacita_kwh)
        minimum[i] = potreba
    return minimum


# -------------------------------------------------------- simulace obchodu
@dataclass
class VysledekUseku:
    """Výsledek simulace jednoho úseku (typicky kalendářního měsíce)."""

    # Peníze proti scénáři „stejný odběr, žádná baterie" – jen energetická
    # složka; platba za výkon se řeší v `peak_shaving.ekonomika_*`.
    zisk_energie_kc: float = 0.0
    naklad_opotrebeni_kc: float = 0.0
    zisk_kc: float = 0.0
    # Energetické toky.
    ze_site_kwh: float = 0.0  # co baterie odebrala ze sítě (AC)
    do_site_kwh: float = 0.0  # co baterie dodala do sítě (AC)
    do_odberu_kwh: float = 0.0  # co baterie dodala do vlastního odběru (AC)
    obchodni_vybito_kwh: float = 0.0  # obchodní energie z baterie (DC)
    ps_vybito_kwh: float = 0.0  # energie na srážení špiček (AC)
    ps_nabito_kwh: float = 0.0  # povinné dobíjení kvůli peak shavingu (AC)
    obchodnich_cyklu: float = 0.0
    max_site_kw: float = 0.0  # nejvyšší síťový tok v úseku (měsíční maximum)
    prekroceni_stropu_kw: float = 0.0  # o kolik strop neudržel (0 = udržel)
    koncovy_soc_kwh: float = 0.0
    # Rozepsaný průběh po intervalech – plní se jen se `zapisuj=True`
    # (podklad pro nitkový graf, viz `prubeh_roku`).
    prubeh: dict | None = None


def simuluj_usek(
    ceny_kc_mwh: list[float],
    odber_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    n: NastaveniSpot,
    prah_nakup_kc_mwh: float,
    prah_prodej_kc_mwh: float,
    opotrebeni_kc_mwh: float = 0.0,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
    pocatecni_soc_kwh: float | None = None,
    soc_minimum: list[float] | None = None,
    zapisuj: bool = False,
) -> VysledekUseku:
    """Projede úsek interval po intervalu; peak shaving má vždy přednost.

    Pořadí rozhodnutí v každém intervalu:

    1. **Peak shaving** – je-li `odběr > strop`, baterie dodá rozdíl (co
       zvládne výkonem a zásobou). Tohle se neptá na cenu.
    2. **Obchodní nabíjení** – je-li spot pod `prah_nakup_kc_mwh`, dobíjí se,
       ale jen do volné kapacity a tak, aby síťový tok nepřesáhl strop (v
       režimu SPOT je stropem naměřené maximum, takže si baterie nabíjením
       nemůže zdražit platbu za výkon).
    3. **Obchodní vybíjení** – je-li spot nad `prah_prodej_kc_mwh`, vybíjí se
       z kapacity **nad minimální trajektorií** (`soc_minimum`); nejdřív do
       vlastního odběru (vyhne se celé nákupní ceně), přebytek do sítě
       (za prodejní cenu, do `max_export_kw`).

    `zisk_energie_kc` je rozdíl proti scénáři bez baterie (kde by zákazník
    koupil celý odběr ze sítě).

    Se `zapisuj=True` se navíc zaznamená průběh po intervalech (`prubeh`) pro
    nitkový graf — ze **stejné** simulace, ze které vyšla ekonomika, aby graf
    nemohl ukazovat jiné chování baterie než tabulky.
    """
    pocet = len(odber_kw)
    v = VysledekUseku()
    if pocet == 0 or vykon_kw <= 0 or kapacita_kwh <= 0:
        return v

    eta = math.sqrt(max(1e-9, min(1.0, ucinnost_rt)))
    max_export = vykon_kw if n.max_export_kw is None else max(0.0, n.max_export_kw)
    if not n.umoznit_export:
        max_export = 0.0
    soc = kapacita_kwh if pocatecni_soc_kwh is None else max(
        0.0, min(kapacita_kwh, pocatecni_soc_kwh)
    )
    rezerva = kapacita_kwh * max(0.0, min(90.0, n.bezpecnostni_rezerva_procenta)) / 100.0
    if zapisuj:
        # `baterie_kw` = kladné vybíjí, záporné nabíjí (stejná konvence jako
        # `peak_shaving.prubeh_baterie`, aby FE nemusel rozlišovat zdroj dat).
        v.prubeh = {
            "site_kw": [],
            "baterie_kw": [],
            "baterie_ps_kw": [],  # z toho srážení špičky
            "baterie_obchod_kw": [],  # z toho obchod (+ prodej, − nákup)
            "soc_pct": [],
            "cena_kc_mwh": [],
            "stropy_kw": [],
        }

    for i in range(pocet):
        odber = odber_kw[i]
        spot = ceny_kc_mwh[i] if i < len(ceny_kc_mwh) else 0.0
        c_nakup = cena_nakup_kc_mwh(spot, n)
        c_prodej = cena_prodej_kc_mwh(spot, n)
        soc_min = soc_minimum[i] if soc_minimum is not None and i < len(soc_minimum) else 0.0
        # Rezerva na chybu predikce: obchod nesmí sáhnout ani na ni.
        soc_dolni = min(kapacita_kwh, soc_min + rezerva)

        # --- 1) peak shaving (bez ohledu na cenu)
        ps_ac_kw = 0.0
        if odber > strop_kw:
            potreba_kw = odber - strop_kw
            ps_ac_kw = min(potreba_kw, vykon_kw, soc * eta / interval_h)
            if potreba_kw - ps_ac_kw > v.prekroceni_stropu_kw:
                v.prekroceni_stropu_kw = potreba_kw - ps_ac_kw
            soc -= ps_ac_kw * interval_h / eta
            v.ps_vybito_kwh += ps_ac_kw * interval_h
        site_kw = odber - ps_ac_kw
        zbyly_vykon_kw = vykon_kw - ps_ac_kw

        # --- 2) povinné dobíjení pro peak shaving (bez ohledu na cenu)
        # Na začátku dalšího intervalu musí být v baterii tolik, kolik si žádá
        # minimální trajektorie – jinak by špičku, která přijde za chvíli,
        # nesrazila. Tohle je to, co dělá klasický peak shaving: dobíjí, kdykoli
        # je pod stropem místo. Obchodní logika se ptá na cenu, tato ne.
        # Cílem je minimální trajektorie **plus bezpečnostní rezerva**: dobíjet
        # jen „na hranu" se ukázalo jako křehké – trajektorie počítá s tím, že
        # se dá dobíjet plným výkonem, a jakmile se to o kousek nepovede,
        # baterie špičku nesrazí (na testovacím profilu 5 intervalů z 35 040,
        # nejvíc o 31 kW).
        soc_cil = 0.0
        if soc_minimum is not None and i + 1 < len(soc_minimum):
            soc_cil = min(kapacita_kwh, soc_minimum[i + 1] + rezerva)
        if soc < soc_cil - 1e-9 and zbyly_vykon_kw > 1e-9:
            prostor_kw = min(zbyly_vykon_kw, max(0.0, strop_kw - site_kw))
            if prostor_kw > 1e-9:
                ze_site_kwh = min(
                    prostor_kw * interval_h,
                    (soc_cil - soc) / eta,
                    (kapacita_kwh - soc) / eta,
                )
                if ze_site_kwh > 1e-9:
                    soc += ze_site_kwh * eta
                    site_kw += ze_site_kwh / interval_h
                    v.ze_site_kwh += ze_site_kwh
                    v.ps_nabito_kwh += ze_site_kwh
                    zbyly_vykon_kw -= ze_site_kwh / interval_h

        # --- 3) obchodní nabíjení
        if zbyly_vykon_kw > 1e-9 and spot <= prah_nakup_kc_mwh and soc < kapacita_kwh:
            # Strop drží i nabíjení: nesmí zvednout síťový tok nad strop.
            prostor_kw = min(zbyly_vykon_kw, max(0.0, strop_kw - site_kw))
            if prostor_kw > 1e-9:
                ze_site_kwh = min(
                    prostor_kw * interval_h, (kapacita_kwh - soc) / eta
                )
                if ze_site_kwh > 1e-9:
                    soc += ze_site_kwh * eta
                    site_kw += ze_site_kwh / interval_h
                    v.ze_site_kwh += ze_site_kwh
                    zbyly_vykon_kw -= ze_site_kwh / interval_h
        # --- 4) obchodní vybíjení
        elif zbyly_vykon_kw > 1e-9 and spot >= prah_prodej_kc_mwh and soc > soc_dolni:
            k_dispozici_kwh = (soc - soc_dolni) * eta  # na AC straně
            vybit_kwh = min(k_dispozici_kwh, zbyly_vykon_kw * interval_h)
            # Nejdřív krytí vlastního odběru (vyhne se celé nákupní ceně),
            # pak export (jen za prodejní cenu, a jen když je povolený).
            do_odberu_kwh = min(vybit_kwh, max(0.0, site_kw) * interval_h)
            zbytek_kwh = vybit_kwh - do_odberu_kwh
            export_kwh = 0.0
            if zbytek_kwh > 1e-9 and max_export > 0 and c_prodej > opotrebeni_kc_mwh:
                export_kwh = min(zbytek_kwh, max_export * interval_h)
            vybito_ac_kwh = do_odberu_kwh + export_kwh
            if vybito_ac_kwh > 1e-9:
                soc -= vybito_ac_kwh / eta
                site_kw -= vybito_ac_kwh / interval_h
                v.do_odberu_kwh += do_odberu_kwh
                v.do_site_kwh += export_kwh
                v.obchodni_vybito_kwh += vybito_ac_kwh / eta

        # --- peníze intervalu proti scénáři bez baterie
        naklad_bez_baterie = odber * interval_h / 1000.0 * c_nakup
        if site_kw >= 0:
            naklad = site_kw * interval_h / 1000.0 * c_nakup
        else:
            naklad = site_kw * interval_h / 1000.0 * c_prodej  # záporné = příjem
        v.zisk_energie_kc += naklad_bez_baterie - naklad
        if site_kw > v.max_site_kw:
            v.max_site_kw = site_kw

        if zapisuj:
            # Co baterie v tomhle intervalu udělala: `odber − site` je čistý
            # tok z baterie do odběru, přebytek nad odběr šel do sítě.
            obchod_kw = (odber - site_kw) / 1.0 - ps_ac_kw
            v.prubeh["site_kw"].append(site_kw)
            v.prubeh["baterie_kw"].append(ps_ac_kw + obchod_kw)
            v.prubeh["baterie_ps_kw"].append(ps_ac_kw)
            v.prubeh["baterie_obchod_kw"].append(obchod_kw)
            v.prubeh["soc_pct"].append(
                100.0 * soc / kapacita_kwh if kapacita_kwh > 0 else 0.0
            )
            v.prubeh["cena_kc_mwh"].append(spot)
            v.prubeh["stropy_kw"].append(strop_kw)

    v.naklad_opotrebeni_kc = v.obchodni_vybito_kwh / 1000.0 * opotrebeni_kc_mwh
    v.zisk_kc = v.zisk_energie_kc - v.naklad_opotrebeni_kc
    v.obchodnich_cyklu = v.obchodni_vybito_kwh / kapacita_kwh if kapacita_kwh > 0 else 0.0
    v.koncovy_soc_kwh = soc
    return v


def _percentil(serazene: list[float], p: float) -> float:
    """p-tý percentil ze setřízeného seznamu (lineární index, bez interpolace)."""
    if not serazene:
        return 0.0
    idx = int(round((len(serazene) - 1) * max(0.0, min(100.0, p)) / 100.0))
    return serazene[idx]


def optimalizuj_prahy(
    ceny_kc_mwh: list[float],
    odber_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    n: NastaveniSpot,
    opotrebeni_kc_mwh: float,
    interval_h: float,
    ucinnost_rt: float,
    pocatecni_soc_kwh: float | None,
    soc_minimum: list[float] | None,
) -> tuple[float, float, VysledekUseku]:
    """Najde nejlepší pár cenových prahů pro daný úsek (typicky jeden den).

    Prahy se hledají jako percentily cen v úseku – mřížka
    `PERCENTILY_NAKUP × PERCENTILY_PRODEJ`, tedy 16 simulací úseku. Percentily
    (ne absolutní ceny) proto, že úroveň ceny se přes rok mění o tisíce
    Kč/MWh, ale **tvar dne** zůstává podobný.

    Přidaná ekonomická podmínka: obchod se pustí jen tam, kde rozdíl prahů
    pokryje ztráty a náklad opotřebení – jinak by baterie v plochých dnech
    cyklovala do mínusu (na datech 2025 by to v prosinci a únoru dělalo
    desetitisíce Kč ztráty ročně).
    """
    serazene = sorted(ceny_kc_mwh)
    nejlepsi: tuple[float, float, VysledekUseku] | None = None
    nejlepsi_percentily: tuple[float, float] | None = None

    def zkus(p_nakup: float, p_prodej: float) -> None:
        nonlocal nejlepsi, nejlepsi_percentily
        prah_nakup = _percentil(serazene, p_nakup)
        prah_prodej = _percentil(serazene, p_prodej)
        # Vyplatí se vůbec cyklovat? Nákup na spodním prahu musí být po
        # ztrátách a opotřebení levnější než hodnota na horním prahu.
        if cena_nakup_kc_mwh(prah_nakup, n) + opotrebeni_kc_mwh >= ucinnost_rt * (
            cena_nakup_kc_mwh(prah_prodej, n)
        ):
            return
        vysledek = simuluj_usek(
            ceny_kc_mwh,
            odber_kw,
            strop_kw,
            vykon_kw,
            kapacita_kwh,
            n,
            prah_nakup,
            prah_prodej,
            opotrebeni_kc_mwh,
            interval_h,
            ucinnost_rt,
            pocatecni_soc_kwh,
            soc_minimum,
        )
        if nejlepsi is None or vysledek.zisk_kc > nejlepsi[2].zisk_kc:
            nejlepsi = (prah_nakup, prah_prodej, vysledek)
            nejlepsi_percentily = (p_nakup, p_prodej)

    for p_nakup in PERCENTILY_NAKUP:
        for p_prodej in PERCENTILY_PRODEJ:
            zkus(p_nakup, p_prodej)
    # Zjemnění kolem nejlepšího nálezu – posun o krok v každém směru.
    if nejlepsi_percentily is not None:
        p_n, p_p = nejlepsi_percentily
        for dn in (-KROK_ZJEMNENI, KROK_ZJEMNENI):
            if 0.0 <= p_n + dn <= 50.0:
                zkus(p_n + dn, p_p)
        p_n = nejlepsi_percentily[0]
        for dp in (-KROK_ZJEMNENI, KROK_ZJEMNENI):
            if 50.0 <= p_p + dp <= 100.0:
                zkus(p_n, p_p + dp)
    if nejlepsi is None:
        # Žádná kombinace prahů se nevyplatí → baterie jen sráží špičky.
        return (
            float("-inf"),
            float("inf"),
            simuluj_usek(
                ceny_kc_mwh,
                odber_kw,
                strop_kw,
                vykon_kw,
                kapacita_kwh,
                n,
                float("-inf"),
                float("inf"),
                opotrebeni_kc_mwh,
                interval_h,
                ucinnost_rt,
                pocatecni_soc_kwh,
                soc_minimum,
            ),
        )
    return nejlepsi


def _pricti(souhrn: VysledekUseku, dil: VysledekUseku) -> None:
    """Přisčítá výsledek dílčího úseku do souhrnu (max u extrémů)."""
    souhrn.zisk_energie_kc += dil.zisk_energie_kc
    souhrn.naklad_opotrebeni_kc += dil.naklad_opotrebeni_kc
    souhrn.zisk_kc += dil.zisk_kc
    souhrn.ze_site_kwh += dil.ze_site_kwh
    souhrn.do_site_kwh += dil.do_site_kwh
    souhrn.do_odberu_kwh += dil.do_odberu_kwh
    souhrn.obchodni_vybito_kwh += dil.obchodni_vybito_kwh
    souhrn.ps_vybito_kwh += dil.ps_vybito_kwh
    souhrn.ps_nabito_kwh += dil.ps_nabito_kwh
    souhrn.obchodnich_cyklu += dil.obchodnich_cyklu
    souhrn.max_site_kw = max(souhrn.max_site_kw, dil.max_site_kw)
    souhrn.prekroceni_stropu_kw = max(souhrn.prekroceni_stropu_kw, dil.prekroceni_stropu_kw)
    souhrn.koncovy_soc_kwh = dil.koncovy_soc_kwh


def plan_mesice(
    ceny_kc_mwh: list[float],
    odber_kw: list[float],
    dny: list[int],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    n: NastaveniSpot,
    opotrebeni_kc_mwh: float,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
    pocatecni_soc_kwh: float | None = None,
    zapisuj: bool = False,
) -> VysledekUseku:
    """Odsimuluje měsíc **po dnech**, s prahy kalibrovanými na každý den zvlášť.

    Den je přirozená jednotka rozhodování: ceny denního trhu na zítřek jsou
    známé dnes ve 13:00, takže „nakupuj v nejlevnějších hodinách dne, prodávej
    v nejdražších" je strategie, kterou reálná řídicí jednotka umí. Stav nabití
    se mezi dny přenáší.

    Minimální trajektorie nabití pro peak shaving se počítá nad **celým
    měsícem** – jinak by baterie na konci dne vyprodala energii, kterou
    potřebuje na ranní špičku dne následujícího.
    """
    soc_minimum = minimalni_soc_trajektorie(
        odber_kw, strop_kw, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt
    )
    souhrn = VysledekUseku()
    soc = kapacita_kwh if pocatecni_soc_kwh is None else pocatecni_soc_kwh
    souhrn.koncovy_soc_kwh = soc
    if zapisuj:
        souhrn.prubeh = {k: [] for k in _KLICE_PRUBEHU}
    for indexy in _po_dnech(dny):
        prah_n, prah_p, dil = optimalizuj_prahy(
            [ceny_kc_mwh[i] for i in indexy],
            [odber_kw[i] for i in indexy],
            strop_kw,
            vykon_kw,
            kapacita_kwh,
            n,
            opotrebeni_kc_mwh,
            interval_h,
            ucinnost_rt,
            soc,
            [soc_minimum[i] for i in indexy],
        )
        if zapisuj:
            # Kalibrace prahů projede den víckrát; průběh chceme jen z té
            # vítězné kombinace, tak ji zopakujeme se zápisem.
            dil = simuluj_usek(
                [ceny_kc_mwh[i] for i in indexy],
                [odber_kw[i] for i in indexy],
                strop_kw,
                vykon_kw,
                kapacita_kwh,
                n,
                prah_n,
                prah_p,
                opotrebeni_kc_mwh,
                interval_h,
                ucinnost_rt,
                soc,
                [soc_minimum[i] for i in indexy],
                zapisuj=True,
            )
            for klic in _KLICE_PRUBEHU:
                souhrn.prubeh[klic].extend(dil.prubeh[klic])
        _pricti(souhrn, dil)
        soc = dil.koncovy_soc_kwh
    return souhrn


def _po_dnech(dny: list[int]) -> list[list[int]]:
    """Rozdělí indexy intervalů na souvislé dny (podle identifikátoru dne)."""
    useky: list[list[int]] = []
    posledni = None
    for i, den in enumerate(dny):
        if den != posledni:
            useky.append([])
            posledni = den
        useky[-1].append(i)
    return useky


# ------------------------------------------- rozhodovací vrstva nad měsíci
@dataclass
class MesicniVolba:
    """Co model pro daný měsíc vybral a proč (podklad pro tabulku ve výstupu)."""

    mesic: int
    strop_kw: float
    strop_nejnizsi_udrzitelny_kw: float
    maximum_bez_baterie_kw: float
    zisk_obchodu_kc: float
    naklad_opotrebeni_kc: float
    obchodnich_cyklu: float
    ze_site_kwh: float
    do_site_kwh: float
    do_odberu_kwh: float
    kandidatu: int = 0
    # Kolik by obchod přinesl při nejnižším udržitelném stropu (= peak shaving
    # má absolutní prioritu). Rozdíl proti `zisk_obchodu_kc` je to, co model
    # získal tím, že strop pustil výš.
    zisk_pri_nejnizsim_stropu_kc: float = 0.0


def kandidatni_stropy(
    nejnizsi_udrzitelny_kw: float, maximum_kw: float, pocet: int = POCET_KANDIDATU_STROPU
) -> list[float]:
    """Kandidátní cílové stropy měsíce: od nejnižšího udržitelného k maximu.

    Nejnižší udržitelný strop je dnešní chování peak shavingu (nejvyšší úspora
    na platbě za výkon), naměřené maximum znamená „baterie nesráží nic a plně
    obchoduje". Mezi tím se rozhoduje ekonomicky.
    """
    if maximum_kw <= nejnizsi_udrzitelny_kw + 1e-9 or pocet <= 1:
        return [nejnizsi_udrzitelny_kw]
    krok = (maximum_kw - nejnizsi_udrzitelny_kw) / (pocet - 1)
    return [nejnizsi_udrzitelny_kw + krok * k for k in range(pocet)]


@dataclass
class VysledekRoku:
    """Roční výsledek obchodování + cílová měsíční maxima pro ekonomiku výkonu."""

    # Cílový síťový strop každého měsíce = měsíční maximum, se kterým se pak
    # počítá platba za výkon (`peak_shaving.ekonomika_2026` / `_2027`).
    cilova_maxima_kw: dict[int, float] = field(default_factory=dict)
    volby: list[MesicniVolba] = field(default_factory=list)
    zisk_energie_kc: float = 0.0
    naklad_opotrebeni_kc: float = 0.0
    zisk_kc: float = 0.0
    ze_site_kwh: float = 0.0
    do_site_kwh: float = 0.0
    do_odberu_kwh: float = 0.0
    obchodni_vybito_kwh: float = 0.0
    obchodnich_cyklu: float = 0.0
    # Co by obchod přinesl, kdyby měl peak shaving absolutní prioritu.
    zisk_pri_prioritnim_ps_kc: float = 0.0
    opotrebeni_pouzite_kc_mwh: float = 0.0
    upozorneni: list[str] = field(default_factory=list)
    # Odkud jsou ceny a jak se párovaly na profil (`spot_ceny.ceny_pro_casy`).
    info_cen: dict = field(default_factory=dict)
    # Použité parametry obchodu (marže, poplatky, rezerva…) – aby se průběh
    # pro nitkový graf dopočítal se stejnými čísly (`nastaveni_z_json`).
    nastaveni_json: dict = field(default_factory=dict)


def simuluj_rok(
    ceny_kc_mwh: list[float],
    odber_kw: list[float],
    mesice: list[int],
    dny: list[int],
    vykon_kw: float,
    kapacita_kwh: float,
    n: NastaveniSpot,
    opotrebeni_kc_mwh: float,
    naklad_vykonu,
    rezim: str = REZIM_KOMBINACE,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
    pocet_kandidatu: int = POCET_KANDIDATU_STROPU,
) -> VysledekRoku:
    """Roční simulace obchodování včetně ekonomické volby měsíčních stropů.

    `naklad_vykonu(mesicni_maxima) -> Kč/rok` je callback do ekonomiky
    rezervované kapacity (model 2026 nebo NTS 2027) – modul tak nemusí znát
    tarifní strukturu a jde testovat samostatně.

    **Režim `spot`:** stropem je naměřené měsíční maximum, takže baterie špičky
    nesráží (platba za výkon zůstane jako dnes), ale nabíjením si ji nemůže
    zdražit.

    **Režim `kombinace`:** pro každý měsíc se zkusí kandidátní stropy
    (`kandidatni_stropy`) a hledá se kombinace s nejvyšším přínosem
    `− náklad na výkon + zisk obchodu`. Protože roční složka rezervované
    kapacity spojuje měsíce dohromady, hledá se souřadnicovým zlepšováním:
    začne se u nejnižších udržitelných stropů (dnešní peak shaving) a měsíc po
    měsíci se zkouší, jestli se vyplatí strop pustit výš. Výsledek proto nikdy
    není horší než dnešní chování.
    """
    vysledek = VysledekRoku(opotrebeni_pouzite_kc_mwh=opotrebeni_kc_mwh)
    if not odber_kw or vykon_kw <= 0 or kapacita_kwh <= 0:
        return vysledek

    indexy_mesicu: dict[int, list[int]] = {}
    for i, m in enumerate(mesice):
        indexy_mesicu.setdefault(m, []).append(i)

    udrzitelny: dict[int, float] = {}
    maximum: dict[int, float] = {}
    for m, idx in indexy_mesicu.items():
        odber_m = [odber_kw[i] for i in idx]
        maximum[m] = max(odber_m) if odber_m else 0.0
        if rezim == REZIM_SPOT:
            udrzitelny[m] = maximum[m]
        else:
            udrzitelny[m] = peak_shaving.min_udrzitelny_strop(
                odber_m, vykon_kw, kapacita_kwh, interval_h, ucinnost_rt
            )

    cache: dict[tuple[int, int], VysledekUseku] = {}

    def plan(m: int, strop: float) -> VysledekUseku:
        klic = (m, int(round(strop * 100)))
        if klic not in cache:
            idx = indexy_mesicu[m]
            cache[klic] = plan_mesice(
                [ceny_kc_mwh[i] for i in idx],
                [odber_kw[i] for i in idx],
                [dny[i] for i in idx],
                strop,
                vykon_kw,
                kapacita_kwh,
                n,
                opotrebeni_kc_mwh,
                interval_h,
                ucinnost_rt,
            )
        return cache[klic]

    kandidati: dict[int, list[float]] = {
        m: (
            kandidatni_stropy(udrzitelny[m], maximum[m], pocet_kandidatu)
            if rezim == REZIM_KOMBINACE
            else [udrzitelny[m]]
        )
        for m in indexy_mesicu
    }
    volba: dict[int, float] = {m: kandidati[m][0] for m in indexy_mesicu}

    def celkovy_prinos(v: dict[int, float]) -> float:
        maxima = {m: min(s, maximum[m]) for m, s in v.items()}
        return sum(plan(m, s).zisk_kc for m, s in v.items()) - naklad_vykonu(maxima)

    if rezim == REZIM_KOMBINACE and any(len(k) > 1 for k in kandidati.values()):
        nejlepsi = celkovy_prinos(volba)
        for _ in range(_MAX_ITERACI_VOLBY):
            zmena = False
            for m in sorted(indexy_mesicu):
                for kandidat in kandidati[m]:
                    if abs(kandidat - volba[m]) < 1e-9:
                        continue
                    zkusit = dict(volba)
                    zkusit[m] = kandidat
                    hodnota = celkovy_prinos(zkusit)
                    if hodnota > nejlepsi + 1e-6:
                        nejlepsi, volba, zmena = hodnota, zkusit, True
            if not zmena:
                break

    # Roční limit cyklů (pojistka záruky): opotřebení se zvedá, dokud počet
    # obchodních cyklů nespadne pod limit. Náklad opotřebení počet cyklů
    # reguluje sám (rešerše kap. 6), tohle je druhá pojistka.
    opotrebeni_pouzite = opotrebeni_kc_mwh
    if n.max_cyklu_rok is not None and n.max_cyklu_rok > 0:
        for _ in range(_MAX_ITERACI_LIMITU_CYKLU):
            cyklu = sum(plan(m, s).obchodnich_cyklu for m, s in volba.items())
            if cyklu <= n.max_cyklu_rok:
                break
            # Zvýšení se odvozuje z toho, o kolik jsme nad limitem – pevný krok
            # by u velkých spreadů nestačil ani po pěti průchodech.
            faktor = max(1.6, min(4.0, cyklu / n.max_cyklu_rok))
            opotrebeni_pouzite = max(opotrebeni_pouzite * faktor, 150.0)
            opotrebeni_kc_mwh = opotrebeni_pouzite
            cache.clear()
        if opotrebeni_pouzite > vysledek.opotrebeni_pouzite_kc_mwh:
            vysledek.upozorneni.append(
                f"Obchodování je omezené ročním limitem {n.max_cyklu_rok:g} cyklů – model "
                f"proto počítá s vyšším nákladem opotřebení ({opotrebeni_pouzite:.0f} Kč/MWh) "
                "a obchoduje jen v nejvýnosnějších hodinách."
            )

    for m in sorted(indexy_mesicu):
        strop = volba[m]
        r = plan(m, strop)
        zakladni = plan(m, kandidati[m][0])
        vysledek.volby.append(
            MesicniVolba(
                mesic=m,
                strop_kw=strop,
                strop_nejnizsi_udrzitelny_kw=udrzitelny[m],
                maximum_bez_baterie_kw=maximum[m],
                zisk_obchodu_kc=r.zisk_kc,
                naklad_opotrebeni_kc=r.naklad_opotrebeni_kc,
                obchodnich_cyklu=r.obchodnich_cyklu,
                ze_site_kwh=r.ze_site_kwh,
                do_site_kwh=r.do_site_kwh,
                do_odberu_kwh=r.do_odberu_kwh,
                kandidatu=len(kandidati[m]),
                zisk_pri_nejnizsim_stropu_kc=zakladni.zisk_kc,
            )
        )
        # Měsíční maximum, které se opravdu naměří (síťový tok ze simulace).
        vysledek.cilova_maxima_kw[m] = min(max(r.max_site_kw, 0.0), maximum[m])
        vysledek.zisk_energie_kc += r.zisk_energie_kc
        vysledek.naklad_opotrebeni_kc += r.naklad_opotrebeni_kc
        vysledek.zisk_kc += r.zisk_kc
        vysledek.ze_site_kwh += r.ze_site_kwh
        vysledek.do_site_kwh += r.do_site_kwh
        vysledek.do_odberu_kwh += r.do_odberu_kwh
        vysledek.obchodni_vybito_kwh += r.obchodni_vybito_kwh
        vysledek.obchodnich_cyklu += r.obchodnich_cyklu
        vysledek.zisk_pri_prioritnim_ps_kc += zakladni.zisk_kc

    vysledek.opotrebeni_pouzite_kc_mwh = opotrebeni_pouzite
    return vysledek


# ------------------------------------------------ vstupní bod pro varianty
@dataclass
class Kontext:
    """Vše, co je pro obchodování stejné napříč variantami baterií.

    Sestavuje ho `routes.py` jednou za výpočet (ceny už napárované na časy
    profilu), varianty si ho pak jen půjčují – jinak by se pro každý produkt
    z katalogu znovu načítal celý rok cen.
    """

    ceny_kc_mwh: list[float]
    mesice: list[int]
    # Identifikátor dne (např. `datetime.date.toordinal()`) – dělí rok na dny,
    # v nichž se kalibrují cenové prahy.
    dny: list[int]
    nastaveni: NastaveniSpot = field(default_factory=NastaveniSpot)
    info_cen: dict = field(default_factory=dict)


def spocti_pro_variantu(
    kontext: Kontext,
    profil_kw: list[float],
    vykon_kw: float,
    kapacita_kwh: float,
    kapacita_jmenovita_kwh: float,
    cena_baterie_kc: float,
    cyklu_zivotnosti: int | None,
    rezim: str,
    interval_h: float,
    ucinnost_rt: float,
    parametry_2027: dict | None,
    rezervovany_prikon_kw: float,
    uvazovat_snizeni_rp: bool,
    cena_rezervace_kc_kw_rok: float,
    cena_mesicni_rk_kc_kw_mesic: float,
    rezerva_rk_procenta: float,
) -> VysledekRoku:
    """Odsimuluje obchodní rok pro jednu variantu baterie.

    Postaví callback „co stojí platba za výkon při daných měsíčních maximech"
    – rozhodovací vrstva podle něj volí měsíční stropy. Přednost má model NTS
    2027 (na něm jede celý horizont NPV, rozhodnuto 27. 7. 2026); bez sazeb
    2027 se použije struktura 2026 s optimalizací kombinace roční a měsíční
    rezervované kapacity.

    Náklad opotřebení se počítá z **jmenovité** kapacity a ceny baterie
    (`naklad_opotrebeni_kc_mwh`), protože záruka na cykly se vztahuje k
    jmenovité kapacitě, ne k využitelnému SOC oknu.
    """
    faktor_rezervy = 1.0 + max(0.0, rezerva_rk_procenta) / 100.0
    ma_2027 = bool(parametry_2027) and not any(
        parametry_2027.get(k) is None for k in peak_shaving.KLICE_2027
    )

    def naklad_vykonu(maxima: dict[int, float]) -> float:
        if ma_2027:
            if uvazovat_snizeni_rp:
                _, rp = peak_shaving.optimalizuj_rp_2027(
                    {m: v * faktor_rezervy for m, v in maxima.items()}, parametry_2027
                )
            else:
                rp = rezervovany_prikon_kw
            naklad, _, _ = peak_shaving._rocni_naklad_2027(rp, maxima, parametry_2027)
            return naklad
        opt = peak_shaving.optimalizuj_rk(
            {m: v * faktor_rezervy for m, v in maxima.items()},
            cena_rezervace_kc_kw_rok,
            cena_mesicni_rk_kc_kw_mesic,
        )
        return opt.naklad_kc

    vysledek = simuluj_rok(
        kontext.ceny_kc_mwh,
        profil_kw,
        kontext.mesice,
        kontext.dny,
        vykon_kw,
        kapacita_kwh,
        kontext.nastaveni,
        naklad_opotrebeni_kc_mwh(
            cena_baterie_kc,
            kapacita_jmenovita_kwh,
            cyklu_zivotnosti or kontext.nastaveni.cyklu_zivotnosti,
        ),
        naklad_vykonu,
        rezim=rezim,
        interval_h=interval_h,
        ucinnost_rt=ucinnost_rt,
    )
    vysledek.info_cen = dict(kontext.info_cen)
    # Parametry se ukládají do výsledku, aby se průběh pro nitkový graf dal
    # dopočítat se stejnými čísly, i když se mezitím nastavení změní.
    vysledek.nastaveni_json = nastaveni_do_json(kontext.nastaveni)
    return vysledek


def prubeh_roku(
    ceny_kc_mwh: list[float],
    odber_kw: list[float],
    mesice: list[int],
    dny: list[int],
    stropy_mesicu: dict[int, float],
    vykon_kw: float,
    kapacita_kwh: float,
    n: NastaveniSpot,
    opotrebeni_kc_mwh: float,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
) -> dict:
    """Rozepíše celý rok interval po intervalu — podklad pro nitkový graf.

    Stropy si nevolí, ale **dostane je zadané** (z uloženého výsledku výpočtu),
    takže graf ukazuje přesně to chování, ze kterého vyšla uložená ekonomika.
    Fyzika i obchodní logika jsou tytéž (`simuluj_usek`) – nitkový graf a
    tabulky se tak nemohou rozejít.

    Vrací řady v pořadí intervalů profilu (`site_kw`, `baterie_kw`,
    `baterie_ps_kw`, `baterie_obchod_kw`, `soc_pct`, `cena_kc_mwh`,
    `stropy_kw`) a souhrn energií, stejně jako `peak_shaving.prubeh_baterie`.
    """
    pocet = len(odber_kw)
    rady: dict[str, list[float]] = {k: [0.0] * pocet for k in _KLICE_PRUBEHU}
    souhrn = VysledekUseku()
    if pocet == 0 or vykon_kw <= 0 or kapacita_kwh <= 0:
        return {**rady, "nabito_kwh": 0.0, "vybito_kwh": 0.0, "zisk_kc": 0.0}

    indexy_mesicu: dict[int, list[int]] = {}
    for i, m in enumerate(mesice):
        indexy_mesicu.setdefault(m, []).append(i)

    # Každý měsíc startuje od PLNÉ baterie – stejně jako ekonomika
    # (`simuluj_rok` počítá měsíce nezávisle) a jako model 2027 u čistého peak
    # shavingu. Přenášet nabití mezi měsíci by bylo realističtější, ale graf by
    # se pak rozešel s čísly v tabulkách (na testovacím profilu o 7,5 % zisku).
    for m in sorted(indexy_mesicu):
        idx = indexy_mesicu[m]
        maximum = max(odber_kw[i] for i in idx)
        dil = plan_mesice(
            [ceny_kc_mwh[i] for i in idx],
            [odber_kw[i] for i in idx],
            [dny[i] for i in idx],
            stropy_mesicu.get(m, maximum),
            vykon_kw,
            kapacita_kwh,
            n,
            opotrebeni_kc_mwh,
            interval_h,
            ucinnost_rt,
            zapisuj=True,
        )
        for klic in _KLICE_PRUBEHU:
            for poradi, i in enumerate(idx):
                if poradi < len(dil.prubeh[klic]):
                    rady[klic][i] = dil.prubeh[klic][poradi]
        _pricti(souhrn, dil)

    return {
        **rady,
        # Nabito ze sítě zahrnuje i povinné dobíjení pro peak shaving, vybito
        # je vše, co baterie vydala (do odběru i do sítě).
        "nabito_kwh": souhrn.ze_site_kwh,
        "vybito_kwh": souhrn.ps_vybito_kwh + souhrn.do_odberu_kwh + souhrn.do_site_kwh,
        "do_site_kwh": souhrn.do_site_kwh,
        "do_odberu_kwh": souhrn.do_odberu_kwh,
        "ps_vybito_kwh": souhrn.ps_vybito_kwh,
        "obchodnich_cyklu": souhrn.obchodnich_cyklu,
        "zisk_kc": souhrn.zisk_kc,
    }


def nastaveni_z_json(data: dict | None) -> NastaveniSpot:
    """Rekonstruuje `NastaveniSpot` z toho, co se uložilo do výsledku výpočtu.

    Průběh pro graf se musí počítat se **stejnými** parametry jako uložená
    ekonomika, ne s aktuálním nastavením – to se mohlo mezitím změnit.
    """
    d = data or {}

    def cislo(klic: str, vychozi: float) -> float:
        hodnota = d.get(klic)
        try:
            return float(hodnota) if hodnota is not None else vychozi
        except (TypeError, ValueError):
            return vychozi

    return NastaveniSpot(
        marze_nakup_kc_mwh=cislo("marze_nakup_kc_mwh", VYCHOZI_MARZE_KC_MWH),
        marze_prodej_kc_mwh=cislo("marze_prodej_kc_mwh", VYCHOZI_MARZE_KC_MWH),
        regulovane_nakup_kc_mwh=cislo(
            "regulovane_nakup_kc_mwh", VYCHOZI_REGULOVANE_NAKUP_KC_MWH
        ),
        regulovane_prodej_kc_mwh=cislo(
            "regulovane_prodej_kc_mwh", VYCHOZI_REGULOVANE_PRODEJ_KC_MWH
        ),
        dan_z_elektriny_kc_mwh=cislo("dan_z_elektriny_kc_mwh", VYCHOZI_DAN_Z_ELEKTRINY_KC_MWH),
        cyklu_zivotnosti=int(cislo("cyklu_zivotnosti", VYCHOZI_CYKLU_ZIVOTNOSTI)),
        max_cyklu_rok=(cislo("max_cyklu_rok", 0.0) or None),
        umoznit_export=bool(d.get("umoznit_export", True)),
        max_export_kw=(cislo("max_export_kw", 0.0) or None),
        bezpecnostni_rezerva_procenta=cislo(
            "bezpecnostni_rezerva_procenta", VYCHOZI_BEZPECNOSTNI_REZERVA_PROCENTA
        ),
    )


def nastaveni_do_json(n: NastaveniSpot) -> dict:
    """Uloží parametry obchodu do výsledku, ať jde průběh dopočítat stejně."""
    return {
        "marze_nakup_kc_mwh": n.marze_nakup_kc_mwh,
        "marze_prodej_kc_mwh": n.marze_prodej_kc_mwh,
        "regulovane_nakup_kc_mwh": n.regulovane_nakup_kc_mwh,
        "regulovane_prodej_kc_mwh": n.regulovane_prodej_kc_mwh,
        "dan_z_elektriny_kc_mwh": n.dan_z_elektriny_kc_mwh,
        "cyklu_zivotnosti": n.cyklu_zivotnosti,
        "max_cyklu_rok": n.max_cyklu_rok,
        "umoznit_export": n.umoznit_export,
        "max_export_kw": n.max_export_kw,
        "bezpecnostni_rezerva_procenta": n.bezpecnostni_rezerva_procenta,
    }
