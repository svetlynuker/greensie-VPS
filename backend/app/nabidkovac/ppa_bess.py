"""PPA + BESS – jedna baterie, dva cíle: srážení špiček i zvýšení samospotřeby.

Odpovídá na otázku, kterou dnes appka neumí zodpovědět: **kdy se baterie vyplatí
na peak shaving a kdy na spotřebu z elektrárny** – a hlavně, kolik se dá získat,
když dělá obojí zároveň. Zadá se 15min odběrový diagram, rezervovaná kapacita
a příkon, cena, kterou zákazník platí dnes, a strop velikosti FVE; výsledkem je
navržená elektrárna, navržená baterie a rozpad přínosu na kW a kWh.

## Proč nový modul a ne rozšíření existujících

`ppa_v2.py` umí baterii **jen jako zvýšení samospotřeby** (nabij přebytek, vybij
deficit) a kilowatty vůbec nezná. `peak_shaving.py` umí opačnou polovinu –
srážení špiček a ekonomiku rezervované kapacity – ale nad profilem, do kterého
elektrárna nezasahuje. Modul „Kombinace opatření" oba výsledky jen sečte, a nese
si tím známou výhradu: baterie navržená nad *původním* profilem je po instalaci
FVE předimenzovaná, protože reálné špičky budou nižší.

Tady se to láme: **profil pro hledání stropu je odběr ze sítě až po odečtení
výroby**, takže se baterie dimenzuje na špičky, které po instalaci opravdu
zůstanou.

## Rozhodovací vrstva (recyklace vzoru ze `spot_arbitraz.py`)

Dvoucílový dispatch appka už jednou vyřešila – u režimu „Kombinace" peak
shavingu, kde baterie sráží špičky a ve zbytku obchoduje na spotovém trhu.
Struktura je přenositelná, jen druhým cílem není obchod, ale uložení přebytku
z elektrárny:

1. `minimalni_soc_trajektorie` (odsud, adaptovaná) spočítá zpětným průchodem,
   kolik nabití si baterie musí v každém intervalu držet, aby srazila všechny
   budoucí špičky. Co je nad touhle hranicí, může solární posun bez rizika
   použít – a nemusí o peak shavingu nic vědět.
2. `simuluj_usek` jde interval po intervalu, peak shaving má absolutní přednost.
3. `simuluj_rok` volí měsíční cílový strop ekonomicky: výchozím bodem je
   nejnižší udržitelný strop (dnešní chování peak shavingu), takže kombinace
   **nikdy nevyjde horší** než čistý peak shaving.

Proti spotové verzi je to o jedno jednodušší: nabíjení z přebytku je zdarma
a hodnota vybití je pevná (cena, kterou zákazník za odebranou MWh neplatí),
takže tu nejsou žádné cenové prahy ani jejich kalibrace.

## Co se od PPA v2 vědomě liší (rozhodnuto s Danem 5. 8. 2026)

* **Baterie je pronájem od SPV**, ne investice zákazníka – celá nabídka je po
  dobu nájmu bez investice.
* **Nájem je fixní, neindexovaný, a platí se jen po dobu nájmu**, i když
  kontrakt na elektrárnu běží delší. Anuita úvěru na baterii se proto počítá na
  dobu nájmu, ne na délku kontraktu jako v `ppa_v2.sestav_projekt`. Doba nájmu
  je editovatelná (`VstupPpaBess.doba_najmu_baterie_roky`), default 10 let.
* **V prvním roce po skončení nájmu si zákazník baterii odkoupí** za zbytkovou
  cenu. Od té chvíle neplatí nájem, ale nese servis a EMS sám a přínos pokračuje
  se započtenou degradací. Alternativa **„odkup za korunu"** rozpustí zbytkovou
  hodnotu do nájmu (`odkup_symbolicky`) – vedle základní varianty se počítá celá
  znovu, protože mění DSCR i minimální cenu PPA.
* **Baterie nikdy nedodává do sítě** – jen posouvá vlastní spotřebu. Do sítě
  teče pouze přebytek elektrárny, za cenu přetoku (defaultně 0 Kč).

Modul je čistě výpočetní: pracuje jen se seznamy čísel a dataclassy, nezná DB
ani FastAPI (stejná konvence jako `peak_shaving.py` a `ppa_v2.py`). Ceny bez DPH.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from . import peak_shaving
from .ppa_v2 import Baterie, ProduktBaterie, baterie_z_produktu

# Výchozí doba nájmu baterie: nájem se platí nezávisle na délce kontraktu na
# elektrárnu (rozhodnutí Dana 5. 8. 2026) a na tutéž dobu se počítá i anuita
# úvěru na baterii. Od 6. 8. 2026 je to jen **default** – obchodník ho může
# u konkrétní nabídky přepsat (`VstupPpaBess.doba_najmu_baterie_roky`), protože
# u některých zákazníků má smysl rozložit baterii na víc let a snížit nájem.
DOBA_NAJMU_BATERIE_ROKY = 10

# Symbolická odkupní cena baterie (Kč) ve variantě, kde se zbytková hodnota
# nedoplácí na konci, ale rozpustí se do měsíčního nájmu. Není to nula, protože
# převod majetku za nula korun je daňově i právně nešikovný – proto „za korunu".
ODKUP_SYMBOLICKY_KC = 1.0

# Kolik kandidátních stropů se v měsíci zkouší při ekonomické volbě. Stejná
# hodnota jako u spotové kombinace – víc kandidátů výsledek zpřesní jen
# nepatrně a čas roste lineárně.
POCET_KANDIDATU_STROPU = 5

# Kolikrát se přejede souřadnicové zlepšování měsíčních stropů, než se to
# vzdá. Konverguje typicky do 2–3 průchodů.
_MAX_ITERACI_VOLBY = 6

# Bezpečnostní rezerva nad minimální trajektorií (% kapacity): dobíjet „na
# hranu" je křehké, protože trajektorie počítá s tím, že se vždy dá dobíjet
# plným výkonem. Stejné poučení jako u spotové verze.
VYCHOZI_REZERVA_TRAJEKTORIE_PROCENTA = 3.0

# Co má baterie dělat. Panel ukazuje všechny tři vedle sebe, aby bylo vidět,
# kolik kombinace přinesla nad rámec každé jednotlivé role.
REZIM_KOMBINACE = "kombinace"  # sráží špičky i posouvá solár (výchozí)
REZIM_SPICKY = "spicky"  # jen sráží špičky (co umí dnešní peak shaving)
REZIM_SAMOSPOTREBA = "samospotreba"  # jen posouvá solár (co umí dnešní PPA)
REZIMY = (REZIM_KOMBINACE, REZIM_SPICKY, REZIM_SAMOSPOTREBA)

REZIM_NAZVY = {
    REZIM_KOMBINACE: "Špičky i samospotřeba",
    REZIM_SPICKY: "Jen srážení špiček",
    REZIM_SAMOSPOTREBA: "Jen zvýšení samospotřeby",
}


# --------------------------------------------------------------- co si peak shaving drží
def minimalni_soc_trajektorie(
    site_kw: list[float],
    strop_kw: float,
    vykon_kw: float,
    kapacita_kwh: float,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    ucinnost_rt: float = peak_shaving.VYCHOZI_UCINNOST_RT,
) -> list[float]:
    """Kolik energie musí baterie mít v každém intervalu kvůli peak shavingu.

    Adaptace `spot_arbitraz.minimalni_soc_trajektorie`; jediný rozdíl je, že
    vstupem je **síťový odběr po odečtení přímé samospotřeby z FVE**, ne holý
    odběr zákazníka. Elektrárna špičky sama sráží, takže trajektorie vychází
    nižší a solárnímu posunu zbyde víc kapacity.

    Zpětný průchod: v intervalu nad stropem potřebuje baterie navíc energii na
    sražení špičky, v intervalu pod stropem si může část potřeby dobít. Výsledek
    je **dolní hranice stavu nabití** – co je nad ní, může solární posun bez
    rizika použít. Prvek `i` = minimální SOC (kWh) na začátku intervalu `i`.
    """
    eta = math.sqrt(max(1e-9, min(1.0, ucinnost_rt)))
    n = len(site_kw)
    minimum = [0.0] * n
    potreba = 0.0
    for i in range(n - 1, -1, -1):
        tok = site_kw[i]
        if tok > strop_kw:
            potreba += (tok - strop_kw) * interval_h / eta
        else:
            dobiti = min(strop_kw - tok, vykon_kw) * interval_h * eta
            potreba = max(0.0, potreba - dobiti)
        potreba = min(potreba, kapacita_kwh)
        minimum[i] = potreba
    return minimum


# ------------------------------------------------------------------- simulace dispatchu
@dataclass
class VysledekUseku:
    """Výsledek dvoucílové simulace jednoho úseku (typicky kalendářního měsíce)."""

    # --- energie, která dorazila k zákazníkovi z elektrárny (to, co platí cenou PPA)
    prima_samospotreba_kwh: float = 0.0  # z FVE přímo do odběru, bez baterie
    z_baterie_do_odberu_kwh: float = 0.0  # z FVE přes baterii do odběru (AC, po ztrátách)
    export_kwh: float = 0.0  # přebytek elektrárny do sítě
    orezano_kwh: float = 0.0  # přebytek, který se nevešel ani do baterie, ani do sítě

    # --- peak shaving
    ps_vybito_kwh: float = 0.0  # energie z baterie na srážení špiček (AC)
    ps_nabito_ze_site_kwh: float = 0.0  # povinné dobíjení ze SÍTĚ kvůli špičkám (AC)
    prekroceni_stropu_kw: float = 0.0  # o kolik strop neudržel (0 = udržel)

    # --- toky baterie
    nabito_z_fve_kwh: float = 0.0  # co se do baterie dostalo z přebytku (AC)
    vybito_celkem_kwh: float = 0.0  # co baterie celkem vydala (AC)
    ztraty_kwh: float = 0.0  # round-trip ztráty (DC rozdíl nabito − vybito)
    cyklu: float = 0.0  # ekvivalentních plných cyklů

    # --- síť
    max_site_kw: float = 0.0  # nejvyšší odběrový tok v úseku (měsíční maximum)
    ze_site_kwh: float = 0.0  # celkový odběr ze sítě
    koncovy_soc_kwh: float = 0.0

    # Rozepsaný průběh po intervalech – plní se jen se `zapisuj=True`.
    prubeh: dict | None = None


def _prazdny_prubeh() -> dict:
    """Kostra záznamu průběhu pro graf.

    Konvence `baterie_kw` je stejná jako u `peak_shaving.prubeh_baterie`
    a `spot_arbitraz.simuluj_usek` – kladné vybíjí, záporné nabíjí – aby
    frontend nemusel rozlišovat, ze kterého modulu data přišla.
    """
    return {
        "site_kw": [],
        "odber_kw": [],
        "vyroba_kw": [],
        "baterie_kw": [],
        "baterie_ps_kw": [],  # z toho srážení špičky
        "baterie_solar_kw": [],  # z toho solární posun (+ vybíjí, − nabíjí)
        "soc_pct": [],
        "stropy_kw": [],
    }


def simuluj_usek(
    odber_kwh: list[float],
    vyroba_kwh: list[float],
    strop_kw: float,
    baterie: Baterie | None,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    rezervovany_vykon_dodavky_kw: float | None = None,
    pocatecni_soc_kwh: float | None = None,
    soc_minimum: list[float] | None = None,
    rezerva_procenta: float = VYCHOZI_REZERVA_TRAJEKTORIE_PROCENTA,
    povolit_solarni_posun: bool = True,
    zapisuj: bool = False,
) -> VysledekUseku:
    """Projede úsek interval po intervalu; peak shaving má vždy přednost.

    Pořadí rozhodnutí v každém intervalu:

    1. **Přímá samospotřeba** – co elektrárna vyrobí, jde nejdřív do odběru.
       Nic to nestojí a sráží to síťový tok, tedy i špičku.
    2. **Peak shaving vybíjení** – zbývá-li síťový odběr nad stropem, baterie
       dodá rozdíl (co zvládne výkonem a zásobou). Tohle se neptá na cenu.
    3. **Povinné dobíjení na trajektorii** – aby baterie srazila špičku, která
       přijde za chvíli, musí mít na začátku dalšího intervalu dost energie.
       Dobíjí se **nejdřív z přebytku elektrárny** (zdarma) a jen když to
       nestačí, ze sítě pod stropem. To je proti spotové verzi nové: tam byl
       jediný zdroj síť, tady je přebytek přednostní, protože je bezplatný.
    4. **Solární nabíjení** – zbylý přebytek do volné kapacity a zbylého výkonu.
    5. **Solární vybíjení** – zbývá-li ještě síťový odběr, baterie ho kryje
       z kapacity **nad minimální trajektorií**. Není tu žádný cenový práh:
       energie v baterii je z elektrárny, takže vybít ji do odběru je vždy
       výhodnější než kupovat ze sítě.
    6. **Export** – co z přebytku zbylo, teče do sítě do rezervovaného výkonu
       dodávky; zbytek se ořízne.

    Původ energie v baterii se **záměrně nesleduje**. Ochranu řeší trajektorie:
    ze sítě se dobíjí jen do ní (krok 3), takže síťová energie se nikdy
    nehromadí „nazapas" a solární vybíjení (krok 5) na ni nesáhne.

    Se `zapisuj=True` se zaznamená průběh po intervalech pro graf – ze **stejné**
    simulace, ze které vyšla ekonomika, aby graf nemohl ukazovat jiné chování
    baterie než tabulky.
    """
    pocet = len(odber_kwh)
    v = VysledekUseku()
    if pocet == 0:
        return v
    if zapisuj:
        v.prubeh = _prazdny_prubeh()

    ma_baterii = (
        baterie is not None
        and baterie.vyuzitelna_kapacita_kwh > 0
        and baterie.vykon_kw > 0
    )
    kapacita = baterie.vyuzitelna_kapacita_kwh if ma_baterii else 0.0
    vykon_kw = baterie.vykon_kw if ma_baterii else 0.0
    eta = (
        math.sqrt(max(1e-9, min(1.0, baterie.ucinnost_round_trip)))
        if ma_baterii
        else 1.0
    )
    soc = 0.0 if pocatecni_soc_kwh is None else max(0.0, min(kapacita, pocatecni_soc_kwh))
    rezerva = kapacita * max(0.0, min(90.0, rezerva_procenta)) / 100.0
    # `None` = dodávka do sítě není omezená; `0` = do sítě nesmí nic (přebytek
    # se ořízne). Ta dvě se musí rozlišit – dřív se `0` vyhodnotila jako falsy
    # a znamenala „neomezeně", tedy přesný opak zadání.
    strop_exportu_kwh = (
        rezervovany_vykon_dodavky_kw * interval_h
        if rezervovany_vykon_dodavky_kw is not None and rezervovany_vykon_dodavky_kw >= 0
        else None
    )
    nabito_dc = 0.0
    vybito_dc = 0.0

    for i in range(pocet):
        odber = max(0.0, odber_kwh[i])
        vyroba = max(0.0, vyroba_kwh[i])
        # Dolní hranice pro solární vybíjení se bere z trajektorie pro
        # **následující** interval, ne pro aktuální. Solární vybíjení se totiž
        # děje na KONCI intervalu, takže musí zůstat tolik, kolik si žádá začátek
        # toho dalšího. S hranicí podle aktuálního intervalu krok 5 rušil dobití,
        # které krok 3 právě udělal kvůli blížící se špičce, a strop se proto
        # proráběl (na testovacím profilu u baterie 1 MWh o 100 kW).
        soc_min = 0.0
        if soc_minimum is not None:
            if i + 1 < len(soc_minimum):
                soc_min = soc_minimum[i + 1]
            elif i < len(soc_minimum):
                soc_min = soc_minimum[i]
        soc_dolni = min(kapacita, soc_min + rezerva)

        # --- 1) přímá samospotřeba
        prima = min(vyroba, odber)
        v.prima_samospotreba_kwh += prima
        prebytek = vyroba - prima
        site_kwh = odber - prima  # co by se bez baterie odebralo ze sítě

        ps_kwh = 0.0
        solar_vybito_kwh = 0.0
        nabito_kwh = 0.0
        zbyly_vykon_kwh = vykon_kw * interval_h if ma_baterii else 0.0

        if ma_baterii:
            # --- 2) peak shaving vybíjení
            strop_kwh = max(0.0, strop_kw) * interval_h
            if site_kwh > strop_kwh + 1e-9:
                potreba_kwh = site_kwh - strop_kwh
                ps_kwh = min(potreba_kwh, zbyly_vykon_kwh, soc * eta)
                nedodano_kw = (potreba_kwh - ps_kwh) / interval_h
                if nedodano_kw > v.prekroceni_stropu_kw:
                    v.prekroceni_stropu_kw = nedodano_kw
                if ps_kwh > 1e-9:
                    soc -= ps_kwh / eta
                    vybito_dc += ps_kwh / eta
                    site_kwh -= ps_kwh
                    zbyly_vykon_kwh -= ps_kwh
                    v.ps_vybito_kwh += ps_kwh

            # --- 3) povinné dobíjení na trajektorii (nejdřív z přebytku, pak ze sítě)
            soc_cil = 0.0
            if soc_minimum is not None and i + 1 < len(soc_minimum):
                soc_cil = min(kapacita, soc_minimum[i + 1] + rezerva)
            if soc < soc_cil - 1e-9 and zbyly_vykon_kwh > 1e-9:
                # a) z přebytku elektrárny – zdarma, a navíc to ubere export
                if prebytek > 1e-9:
                    z_fve = min(
                        prebytek,
                        zbyly_vykon_kwh,
                        (soc_cil - soc) / eta,
                        (kapacita - soc) / eta,
                    )
                    if z_fve > 1e-9:
                        soc += z_fve * eta
                        nabito_dc += z_fve * eta
                        prebytek -= z_fve
                        zbyly_vykon_kwh -= z_fve
                        nabito_kwh += z_fve
                        v.nabito_z_fve_kwh += z_fve
                # b) ze sítě, ale jen pod stropem – nesmí si zdražit platbu za výkon
                if soc < soc_cil - 1e-9 and zbyly_vykon_kwh > 1e-9:
                    prostor_kwh = max(0.0, max(0.0, strop_kw) * interval_h - site_kwh)
                    ze_site = min(
                        prostor_kwh,
                        zbyly_vykon_kwh,
                        (soc_cil - soc) / eta,
                        (kapacita - soc) / eta,
                    )
                    if ze_site > 1e-9:
                        soc += ze_site * eta
                        nabito_dc += ze_site * eta
                        site_kwh += ze_site
                        zbyly_vykon_kwh -= ze_site
                        nabito_kwh += ze_site
                        v.ps_nabito_ze_site_kwh += ze_site

            # --- 4) solární nabíjení ze zbylého přebytku
            if (
                povolit_solarni_posun
                and prebytek > 1e-9
                and zbyly_vykon_kwh > 1e-9
                and soc < kapacita - 1e-9
            ):
                z_fve = min(prebytek, zbyly_vykon_kwh, (kapacita - soc) / eta)
                if z_fve > 1e-9:
                    soc += z_fve * eta
                    nabito_dc += z_fve * eta
                    prebytek -= z_fve
                    zbyly_vykon_kwh -= z_fve
                    nabito_kwh += z_fve
                    v.nabito_z_fve_kwh += z_fve

            # --- 5) solární vybíjení do zbylého odběru (nad trajektorií)
            if (
                povolit_solarni_posun
                and site_kwh > 1e-9
                and zbyly_vykon_kwh > 1e-9
                and soc > soc_dolni + 1e-9
            ):
                k_dispozici = (soc - soc_dolni) * eta
                solar_vybito_kwh = min(k_dispozici, zbyly_vykon_kwh, site_kwh)
                if solar_vybito_kwh > 1e-9:
                    soc -= solar_vybito_kwh / eta
                    vybito_dc += solar_vybito_kwh / eta
                    site_kwh -= solar_vybito_kwh
                    zbyly_vykon_kwh -= solar_vybito_kwh
                else:
                    solar_vybito_kwh = 0.0

        # --- 6) export zbylého přebytku
        if prebytek > 1e-9:
            if strop_exportu_kwh is None:
                v.export_kwh += prebytek
            else:
                do_site = min(prebytek, strop_exportu_kwh)
                v.export_kwh += do_site
                v.orezano_kwh += prebytek - do_site

        # --- souhrny intervalu
        v.z_baterie_do_odberu_kwh += ps_kwh + solar_vybito_kwh
        v.vybito_celkem_kwh += ps_kwh + solar_vybito_kwh
        v.ze_site_kwh += max(0.0, site_kwh)
        tok_kw = max(0.0, site_kwh) / interval_h
        if tok_kw > v.max_site_kw:
            v.max_site_kw = tok_kw

        if zapisuj:
            v.prubeh["site_kw"].append(round(max(0.0, site_kwh) / interval_h, 3))
            v.prubeh["odber_kw"].append(round(odber / interval_h, 3))
            v.prubeh["vyroba_kw"].append(round(vyroba / interval_h, 3))
            solar_kw = (solar_vybito_kwh - nabito_kwh) / interval_h
            v.prubeh["baterie_kw"].append(round((ps_kwh / interval_h) + solar_kw, 3))
            v.prubeh["baterie_ps_kw"].append(round(ps_kwh / interval_h, 3))
            v.prubeh["baterie_solar_kw"].append(round(solar_kw, 3))
            v.prubeh["soc_pct"].append(
                round(100.0 * soc / kapacita, 2) if kapacita > 0 else 0.0
            )
            v.prubeh["stropy_kw"].append(round(strop_kw, 2))

    v.ztraty_kwh = max(0.0, nabito_dc - vybito_dc)
    v.cyklu = (vybito_dc / kapacita) if kapacita > 0 else 0.0
    v.koncovy_soc_kwh = soc
    return v


# --------------------------------------------------------------- hledání stropu
def min_udrzitelny_strop(
    odber_kwh: list[float],
    vyroba_kwh: list[float],
    baterie: Baterie | None,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    rezervovany_vykon_dodavky_kw: float | None = None,
    tolerance_kw: float = 0.05,
    povolit_solarni_posun: bool = True,
) -> float:
    """Nejnižší strop síťového odběru, který baterie s elektrárnou udrží.

    Vlastní bisekce nad `simuluj_usek`, ne `peak_shaving.min_udrzitelny_strop`.
    Ta totiž o elektrárně nic neví a počítá jen s dobíjením ze sítě pod stropem,
    takže by vyšla **pesimistická**: nabíjení z přebytku FVE umí baterii dostat
    do špičky nabitou i tam, kde by na to prostor pod stropem nestačil.

    Kritérium udržitelnosti je `prekroceni_stropu_kw == 0` – tedy že simulace
    strop v žádném intervalu neprorazila. Vrací se horní mez intervalu, tedy
    bezpečná strana (stejná konvence jako u peak shavingu).
    """
    if not odber_kwh:
        return 0.0
    site_kw = [
        max(0.0, odber_kwh[i] - (vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0)) / interval_h
        for i in range(len(odber_kwh))
    ]
    hi = max(site_kw) if site_kw else 0.0
    if hi <= 0:
        return 0.0
    ma_baterii = (
        baterie is not None
        and baterie.vyuzitelna_kapacita_kwh > 0
        and baterie.vykon_kw > 0
    )
    if not ma_baterii:
        return hi

    def udrzi(strop_kw: float) -> bool:
        # Trajektorie se počítá pro týž strop, který se testuje – dispatch pak
        # dobíjí právě na ni.
        trajektorie = minimalni_soc_trajektorie(
            site_kw,
            strop_kw,
            baterie.vykon_kw,
            baterie.vyuzitelna_kapacita_kwh,
            interval_h,
            baterie.ucinnost_round_trip,
        )
        v = simuluj_usek(
            odber_kwh,
            vyroba_kwh,
            strop_kw,
            baterie,
            interval_h,
            rezervovany_vykon_dodavky_kw,
            pocatecni_soc_kwh=baterie.vyuzitelna_kapacita_kwh,
            soc_minimum=trajektorie,
            povolit_solarni_posun=povolit_solarni_posun,
        )
        return v.prekroceni_stropu_kw <= 1e-9

    lo = 0.0
    if udrzi(lo):
        return 0.0
    while hi - lo > tolerance_kw:
        mid = (lo + hi) / 2.0
        if udrzi(mid):
            hi = mid
        else:
            lo = mid
    return hi


# ------------------------------------------------------- roční simulace a volba stropů
@dataclass
class MesicniVolba:
    """Co model pro daný měsíc vybral a proč (podklad pro tabulku ve výstupu)."""

    mesic: int
    strop_kw: float
    strop_nejnizsi_udrzitelny_kw: float
    maximum_bez_baterie_kw: float
    maximum_po_baterii_kw: float
    # Kolik energie z elektrárny dorazilo k zákazníkovi přes baterii, a kolik
    # baterie vydala na srážení špiček. Rozpad „kdy na co" je právě tohle.
    z_baterie_do_odberu_kwh: float
    ps_vybito_kwh: float
    cyklu: float
    kandidatu: int = 0
    # Energetická bilance měsíce – podklad pro graf výroba vs. spotřeba. Dispatch
    # ji spočítá tak jako tak (jede po měsících), takže se tu jen nezahazuje;
    # skládat ji znovu druhým průchodem by znamenalo počítat dvakrát totéž.
    spotreba_kwh: float = 0.0
    vyroba_kwh: float = 0.0
    prima_samospotreba_kwh: float = 0.0
    z_fve_pres_baterii_kwh: float = 0.0
    export_kwh: float = 0.0
    orezano_kwh: float = 0.0
    ze_site_kwh: float = 0.0


@dataclass
class VysledekRoku:
    """Roční výsledek dvoucílového dispatchu + maxima pro ekonomiku výkonu."""

    # Měsíční maxima síťového odběru po baterii – vstup do `peak_shaving.ekonomika_*`.
    cilova_maxima_kw: dict[int, float] = field(default_factory=dict)
    # Měsíční maxima bez baterie (ale už po odečtení výroby FVE) – baseline.
    maxima_bez_baterie_kw: dict[int, float] = field(default_factory=dict)
    volby: list[MesicniVolba] = field(default_factory=list)

    # Energie
    prima_samospotreba_kwh: float = 0.0
    z_baterie_do_odberu_kwh: float = 0.0
    export_kwh: float = 0.0
    orezano_kwh: float = 0.0
    ze_site_kwh: float = 0.0
    ps_vybito_kwh: float = 0.0
    ps_nabito_ze_site_kwh: float = 0.0
    nabito_z_fve_kwh: float = 0.0
    ztraty_kwh: float = 0.0
    cyklu: float = 0.0
    # Round-trip účinnost baterie – potřebná k rozdělení vybité energie na
    # solární a síťovou část (viz `z_fve_pres_baterii_kwh`).
    ucinnost_rt: float = 1.0
    upozorneni: list[str] = field(default_factory=list)

    @property
    def z_fve_pres_baterii_kwh(self) -> float:
        """Energie z elektrárny, která k zákazníkovi dorazila přes baterii.

        **Nepočítá se z vybité energie**, protože baterie nerozlišuje, odkud co
        přišlo: kdyby se sečetlo všechno, co z ní vyšlo, počítala by se do
        samospotřeby i energie dobitá ze SÍTĚ kvůli špičkám – a míra samospotřeby
        by vyšla nesmyslně vysoká (na testovacím profilu 580 %).

        Bere se proto opačná strana: co do baterie vstoupilo z přebytku, mínus
        round-trip ztráty. Zbytek nabití na konci úseku je proti roční energii
        zanedbatelný.
        """
        return self.nabito_z_fve_kwh * max(0.0, min(1.0, self.ucinnost_rt))

    @property
    def samospotreba_kwh(self) -> float:
        """Energie z elektrárny, která dorazila k zákazníkovi (tu platí cenou PPA).

        Ztráty v baterii se nezpeněžují – co se v ní ztratilo, k zákazníkovi
        nedorazilo a nefakturuje se (stejné rozhodnutí jako v `ppa_v2`).
        """
        return self.prima_samospotreba_kwh + self.z_fve_pres_baterii_kwh


def simuluj_rok(
    odber_kwh: list[float],
    vyroba_kwh: list[float],
    mesice: list[int],
    baterie: Baterie | None,
    naklad_vykonu,
    interval_h: float = peak_shaving.VYCHOZI_INTERVAL_H,
    rezervovany_vykon_dodavky_kw: float | None = None,
    pocet_kandidatu: int = POCET_KANDIDATU_STROPU,
    hodnota_kwh_kc: float = 0.0,
    rezim: str = REZIM_KOMBINACE,
) -> VysledekRoku:
    """Roční dvoucílová simulace včetně ekonomické volby měsíčních stropů.

    `naklad_vykonu(mesicni_maxima_kw) -> Kč/rok` je callback do ekonomiky
    rezervované kapacity (model 2026 nebo NTS 2027) – modul tak nemusí znát
    tarifní strukturu a jde testovat samostatně. Stejný vzor jako
    `spot_arbitraz.simuluj_rok`.

    `hodnota_kwh_kc` je čistá hodnota jedné kWh, která projde baterií k
    zákazníkovi (co by za ni zaplatil síti, minus co za ni zaplatí v PPA).
    Používá se jen k ekonomické volbě stropu: pustit strop výš znamená zaplatit
    víc za výkon, ale získat víc kapacity na solární posun.

    Režimy (`REZIMY`):

    * `kombinace` – obojí, se ekonomickou volbou měsíčního stropu. Souřadnicové
      zlepšování začíná u **nejnižších udržitelných stropů**, tedy u dnešního
      chování peak shavingu, takže výsledek nikdy není horší.
    * `spicky` – jen srážení špiček na nejnižší udržitelný strop; solární posun
      je vypnutý. Odpovídá tomu, co umí dnešní peak shaving.
    * `samospotreba` – strop je naměřené maximum, takže se nic nesráží a baterie
      jen posouvá solár. Odpovídá tomu, co umí dnešní PPA s baterií.
    """
    vysledek = VysledekRoku()
    if not odber_kwh:
        return vysledek
    if rezim not in REZIMY:
        raise ValueError(f"Neznámý režim baterie: {rezim!r}")
    solar = rezim != REZIM_SPICKY
    if baterie is not None:
        vysledek.ucinnost_rt = baterie.ucinnost_round_trip

    indexy: dict[int, list[int]] = {}
    for i, m in enumerate(mesice):
        indexy.setdefault(m, []).append(i)

    ma_baterii = (
        baterie is not None
        and baterie.vyuzitelna_kapacita_kwh > 0
        and baterie.vykon_kw > 0
    )

    # Síťový tok bez baterie (ale po odečtení přímé samospotřeby z FVE) – z něj
    # je baseline měsíčních maxim i horní hranice kandidátních stropů.
    site_bez_kw = [
        max(0.0, odber_kwh[i] - (vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0)) / interval_h
        for i in range(len(odber_kwh))
    ]

    udrzitelny: dict[int, float] = {}
    maximum: dict[int, float] = {}
    for m, idx in indexy.items():
        maximum[m] = max((site_bez_kw[i] for i in idx), default=0.0)
        if ma_baterii and rezim != REZIM_SAMOSPOTREBA:
            # Strop se hledá **vždy bez solárního posunu**, i v kombinovaném
            # režimu. Peak shaving má absolutní přednost, takže výchozím bodem
            # musí být tentýž nejnižší strop, jaký by dal čistý peak shaving –
            # jinak kombinace startuje z horší pozice a může skončit horší než
            # samotné srážení špiček (na testovacím profilu o 59 tis. Kč/rok).
            # Solární posun se pak vejde jen do kapacity nad trajektorií, takže
            # tenhle strop neohrozí.
            udrzitelny[m] = min_udrzitelny_strop(
                [odber_kwh[i] for i in idx],
                [vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0 for i in idx],
                baterie,
                interval_h,
                rezervovany_vykon_dodavky_kw,
                povolit_solarni_posun=False,
            )
        else:
            # Režim „jen samospotřeba": strop je naměřené maximum, takže se nic
            # nesráží – ale nabíjení ho pořád respektuje, aby si baterie platbu
            # za výkon nezdražila.
            udrzitelny[m] = maximum[m]
    vysledek.maxima_bez_baterie_kw = dict(maximum)

    cache: dict[tuple[int, int], VysledekUseku] = {}

    def sim(m: int, strop_kw: float) -> VysledekUseku:
        klic = (m, int(round(strop_kw * 100)))
        if klic not in cache:
            idx = indexy[m]
            odber_m = [odber_kwh[i] for i in idx]
            vyroba_m = [vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0 for i in idx]
            trajektorie = None
            pocatecni = None
            if ma_baterii:
                trajektorie = minimalni_soc_trajektorie(
                    [site_bez_kw[i] for i in idx],
                    strop_kw,
                    baterie.vykon_kw,
                    baterie.vyuzitelna_kapacita_kwh,
                    interval_h,
                    baterie.ucinnost_round_trip,
                )
                # Každý měsíc startuje z plné baterie – stejný (optimistický)
                # předpoklad jako `peak_shaving.mesicni_maxima_po_baterii`, ať
                # nevznikne tichý rozdíl mezi moduly.
                pocatecni = baterie.vyuzitelna_kapacita_kwh
            cache[klic] = simuluj_usek(
                odber_m,
                vyroba_m,
                strop_kw,
                baterie,
                interval_h,
                rezervovany_vykon_dodavky_kw,
                pocatecni_soc_kwh=pocatecni,
                soc_minimum=trajektorie,
                povolit_solarni_posun=solar,
            )
        return cache[klic]

    # Ekonomická volba stropu má smysl jen v kombinovaném režimu: u čistých
    # špiček je cílem nejnižší strop, u čisté samospotřeby se nesráží vůbec.
    kandidati: dict[int, list[float]] = {}
    for m in indexy:
        if (
            ma_baterii
            and rezim == REZIM_KOMBINACE
            and maximum[m] > udrzitelny[m] + 1e-9
            and pocet_kandidatu > 1
        ):
            krok = (maximum[m] - udrzitelny[m]) / (pocet_kandidatu - 1)
            kandidati[m] = [udrzitelny[m] + krok * k for k in range(pocet_kandidatu)]
        else:
            kandidati[m] = [udrzitelny[m]]
    volba: dict[int, float] = {m: kandidati[m][0] for m in indexy}

    eta_rt = max(0.0, min(1.0, baterie.ucinnost_round_trip)) if ma_baterii else 1.0

    def celkovy_prinos(v: dict[int, float]) -> float:
        """Přínos volby: hodnota solárního posunu minus platba za výkon.

        Oceňuje se jen energie **z elektrárny** přes baterii (nabito z přebytku
        po ztrátách) – ne všechno, co z baterie vyšlo. Energie dobitá ze sítě
        kvůli špičkám nemá s cenou PPA nic společného a její přínos je celý na
        straně platby za výkon.
        """
        maxima = {}
        hodnota = 0.0
        for m, strop in v.items():
            r = sim(m, strop)
            maxima[m] = min(max(r.max_site_kw, 0.0), maximum[m])
            hodnota += r.nabito_z_fve_kwh * eta_rt / 1000.0 * hodnota_kwh_kc
        return hodnota - naklad_vykonu(maxima)

    if ma_baterii and rezim == REZIM_KOMBINACE and any(len(k) > 1 for k in kandidati.values()):
        nejlepsi = celkovy_prinos(volba)
        for _ in range(_MAX_ITERACI_VOLBY):
            zmena = False
            for m in sorted(indexy):
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

    for m in sorted(indexy):
        strop = volba[m]
        r = sim(m, strop)
        maximum_po = min(max(r.max_site_kw, 0.0), maximum[m])
        vysledek.cilova_maxima_kw[m] = maximum_po
        vysledek.volby.append(
            MesicniVolba(
                mesic=m,
                strop_kw=strop,
                strop_nejnizsi_udrzitelny_kw=udrzitelny[m],
                maximum_bez_baterie_kw=maximum[m],
                maximum_po_baterii_kw=maximum_po,
                z_baterie_do_odberu_kwh=r.z_baterie_do_odberu_kwh,
                ps_vybito_kwh=r.ps_vybito_kwh,
                cyklu=r.cyklu,
                kandidatu=len(kandidati[m]),
                spotreba_kwh=sum(odber_kwh[i] for i in indexy[m]),
                vyroba_kwh=sum(
                    (vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0) for i in indexy[m]
                ),
                prima_samospotreba_kwh=r.prima_samospotreba_kwh,
                z_fve_pres_baterii_kwh=r.nabito_z_fve_kwh * eta_rt,
                export_kwh=r.export_kwh,
                orezano_kwh=r.orezano_kwh,
                ze_site_kwh=r.ze_site_kwh,
            )
        )
        vysledek.prima_samospotreba_kwh += r.prima_samospotreba_kwh
        vysledek.z_baterie_do_odberu_kwh += r.z_baterie_do_odberu_kwh
        vysledek.export_kwh += r.export_kwh
        vysledek.orezano_kwh += r.orezano_kwh
        vysledek.ze_site_kwh += r.ze_site_kwh
        vysledek.ps_vybito_kwh += r.ps_vybito_kwh
        vysledek.ps_nabito_ze_site_kwh += r.ps_nabito_ze_site_kwh
        vysledek.nabito_z_fve_kwh += r.nabito_z_fve_kwh
        vysledek.ztraty_kwh += r.ztraty_kwh
        vysledek.cyklu += r.cyklu

    return vysledek


# ------------------------------------------------------------------------- parametry
@dataclass
class ParametryPpaBess:
    """Co PPA+BESS potřebuje nad rámec `ppa_v2.ParametryEkonomiky`.

    Ekonomiku elektrárny (marže, financování, DSCR, IRR, indexace, poplatky za
    odkup) přebíráme z PPA v2 bez změny – tady jsou jen tři věci, které v PPA
    nemají obdobu, protože v PPA baterie nikdy nepřežila kontrakt.
    """

    # Za kolik si zákazník baterii odkoupí po skončení nájmu, jako podíl CAPEX.
    # `ppa_v2.odkupni_tabulka` se tu použít nedá: odvozuje cenu ze zbytku úvěru,
    # a ten je po deseti letech nulový – baterie by vyšla skoro zdarma, i když
    # reálnou hodnotu pořád má. Default 15 % odpovídá zařízení s ~60–70 %
    # původní kapacity.
    bess_zbytkova_hodnota_podil: float = 0.15
    # Roční pokles přínosu baterie (degradace kapacity). Stejná hodnota i klíč
    # jako u peak shavingu, ať tentýž produkt nestárne ve dvou modulech jinak.
    degradace_prinosu_baterie: float = 0.015
    # Cena energie pro ocenění ztrát cyklování (Kč/MWh). Ztráty vznikají jen na
    # energii dobité ze SÍTĚ kvůli špičkám; ztráty na solární energii se
    # nezpeněžují (k zákazníkovi nedorazily, tak se mu nefakturují).
    cena_energie_kc_mwh: float = peak_shaving.VYCHOZI_CENA_ENERGIE_KC_MWH


def _p(parametry: dict | None, klic: str, default: float) -> float:
    """Přečte parametr z manažerského nastavení s fallbackem."""
    if parametry:
        hodnota = parametry.get(klic)
        if hodnota is not None:
            try:
                return float(hodnota)
            except (TypeError, ValueError):
                pass
    return default


def parametry_z_nastaveni(parametry: dict | None) -> ParametryPpaBess:
    """Manažerské nastavení (`vypoctova_nastaveni.parametry`) → parametry PPA+BESS."""
    return ParametryPpaBess(
        bess_zbytkova_hodnota_podil=_p(
            parametry, "ppa_bess_zbytkova_hodnota_podil", 0.15
        ),
        degradace_prinosu_baterie=_p(
            parametry, "ps_degradace_uspor_procenta_rok", 1.5
        )
        / 100.0,
        cena_energie_kc_mwh=_p(
            parametry, "ps_cena_energie_kc_mwh", peak_shaving.VYCHOZI_CENA_ENERGIE_KC_MWH
        ),
    )


# ------------------------------------------------------------------------- nájem baterie
def sestav_projekt_bess(
    nakladova_cena_kc: float, p, doba_najmu_roky: int = DOBA_NAJMU_BATERIE_ROKY
) -> "object":
    """Financovaný projekt baterie – úvěr na **dobu nájmu**, ne na délku kontraktu.

    Jediný rozdíl proti `ppa_v2.sestav_projekt` je splatnost: PPA rozkládá úvěr
    na baterii na délku kontraktu na elektrárnu, takže u 20letého PPA vycházel
    nájem nižší, než na jak dlouho se reálně platí. Nájem je fixní a platí se
    jen po dobu nájmu (rozhodnutí Dana 5. 8. 2026), takže i úvěr musí být na
    stejnou dobu – jinak by po skončení nájmu zůstal nesplacený.

    Věcný důsledek: čím kratší nájem, tím vyšší roční splátka baterie. Protože
    se DSCR testuje po letech, může to zvednout minimální cenu PPA – banka se
    dívá na nejtěsnější rok, a ten je v době, kdy se baterie splácí.
    """
    from .ppa_v2 import sestav_projekt

    return sestav_projekt(
        nakladova_cena_kc,
        p.marze_bess,
        p.provize_bess,
        max(1, int(doba_najmu_roky)),
        p,
    )


def najem_baterie_kc_mesic(projekt_bess, p) -> float:
    """Fixní měsíční nájem baterie = marže + splátka úvěru + EMS.

    Neindexuje se – po celou dobu nájmu je to stejné číslo (na rozdíl od ceny
    PPA za energii, která se každé tři roky skokově zvedá). Splatnost úvěru je
    v `projekt_bess` (viz `sestav_projekt_bess`), takže delší nájem se tady
    projeví sám nižší splátkou.
    """
    if projekt_bess.capex_kc <= 0:
        return 0.0
    return p.bess_marze_kc_mesic + projekt_bess.splatka_mesicni_kc + p.bess_ems_kc_mesic


def odkupni_cena_baterie_kc(projekt_bess, pb: "ParametryPpaBess") -> float:
    """Zbytková hodnota baterie, za kterou si ji zákazník po nájmu odkoupí."""
    if projekt_bess.capex_kc <= 0:
        return 0.0
    return projekt_bess.capex_kc * max(0.0, pb.bess_zbytkova_hodnota_podil)


def navyseni_najmu_za_odkup_kc_mesic(
    odkupni_cena_kc: float, doba_najmu_roky: int
) -> float:
    """O kolik se zvedne měsíční nájem, když se odkup rozpustí do nájmu.

    Varianta „odkup za korunu": zákazník na konci nedoplácí zbytkovou hodnotu,
    ale platí ji průběžně – rovnoměrně rozpočítanou do všech měsíců nájmu.
    Rovnoměrně, ne anuitně: je to cena rozložená v čase, ne další úvěr, a
    obchodník musí být schopen zákazníkovi to číslo vysvětlit jednou dělenou.

    Pro SPV to není totéž: místo jednorázového kapitálového příjmu v roce po
    nájmu dostane provozní příjem už během nájmu, což zlepšuje DSCR. Proto se
    tahle varianta počítá celá znovu, ne jen jako přeskládání výsledku.
    """
    mesicu = max(1, int(doba_najmu_roky)) * 12
    return max(0.0, odkupni_cena_kc) / mesicu


# ------------------------------------------------------------------------- cashflow
@dataclass
class RokPpaBess:
    """Jeden rok kontraktu – pohled investora i zákazníka na jednom řádku."""

    rok: int
    # --- investor (SPV)
    vyroba_mwh: float
    samospotreba_mwh: float
    export_mwh: float
    cena_ppa_kc_mwh: float
    prijem_ppa_kc: float
    prijem_export_kc: float
    najem_baterie_kc: float
    prijem_odkup_kc: float  # jednorázový příjem z odkupu baterie (rok 11)
    provozni_naklady_kc: float
    zdroje_kc: float  # provozní zdroje na dluhovou službu (bez odkupu)
    splatka_kc: float  # FVE + BESS, dokud úvěr na baterii běží
    # Rozpad splátky: úrok je to, co úvěr **stojí**, úmor jen vrací půjčené.
    # Bez tohohle rozpadu se z výsledku nedá říct, kolik financování sežere.
    urok_kc: float
    umor_kc: float
    zustatek_uveru_kc: float  # na konci roku, FVE + BESS dohromady
    dscr: float | None
    zisk_po_splatkach_kc: float
    # Kumulovaný cash flow vlastního kapitálu – kde překlopí do plusu, tam se
    # investorovi vrátilo, co vložil.
    kumulovany_cf_kc: float

    # --- zákazník
    uspora_energie_kc: float  # co nezaplatí síti za energii z elektrárny
    uspora_vykon_kc: float  # co nezaplatí za rezervovanou kapacitu / špičku
    naklad_najmu_kc: float
    naklad_ztrat_kc: float  # energie dobitá ze sítě na špičky, ztracená v baterii
    naklad_provozu_zakaznika_kc: float  # servis a EMS po odkupu baterie
    vydaj_odkup_kc: float
    cisty_prinos_zakaznika_kc: float


@dataclass
class CashflowPpaBess:
    """Výsledek dopředného výpočtu pro danou velikost, baterii a délku kontraktu."""

    roky: list[RokPpaBess]
    vlastni_kapital_kc: float
    capex_kc: float
    capex_fve_kc: float
    capex_bess_kc: float
    najem_baterie_kc_mesic: float
    dscr_min: float | None
    irr: float | None
    npv_kc: float
    cf_vlastniho_kapitalu: list[float]
    zisk_greensie_kc: float
    provize_kc: float
    odkupni_cena_baterie_kc: float
    # Souhrn za zákazníka (nediskontovaně, celý kontrakt).
    uspora_celkem_kc: float
    prinos_energie_celkem_kc: float
    prinos_vykon_celkem_kc: float
    # --- souhrn za INVESTORA (SPV) za celý kontrakt, nediskontovaně
    prijmy_ppa_celkem_kc: float  # co klient zaplatí za energii
    prijmy_najem_celkem_kc: float  # co klient zaplatí za nájem baterie
    prijmy_export_celkem_kc: float  # výkup / sdílení přebytku
    prijmy_odkup_celkem_kc: float  # odkup baterie klientem
    naklady_provozni_celkem_kc: float  # servis, EMS
    uroky_celkem_kc: float  # kolik stojí úvěr
    umor_celkem_kc: float  # kolik se vrátí bance z jistiny
    # Kdy se investorovi vrátí vložený vlastní kapitál (roky, lineární
    # interpolace v roce překlopení). `None` = v horizontu kontraktu ne.
    navratnost_vlastniho_kapitalu_roky: float | None


def spocti_cashflow(
    vyroba_rok1_mwh: float,
    samospotreba_rok1_mwh: float,
    export_rok1_mwh: float,
    uspora_vykon_rok1_kc: float,
    ztraty_ze_site_rok1_kwh: float,
    cena_ppa_rok1_kc_mwh: float,
    cena_zakaznika_kc_mwh: float,
    projekt_fve,
    projekt_bess,
    p,
    pb: ParametryPpaBess,
    delka_roky: int,
    doba_najmu_roky: int = DOBA_NAJMU_BATERIE_ROKY,
    najem_kc_mesic: float | None = None,
    odkup_symbolicky: bool = False,
) -> CashflowPpaBess:
    """Cash flow po letech, kde se v roce po skončení nájmu mění hned tři věci.

    `ppa_v2.spocti_cashflow` tady nestačí: umí jen konstantní splátku a
    konstantní nájem po celou dobu kontraktu. V PPA+BESS se v prvním roce po
    skončení nájmu baterie stane najednou:

    1. **skončí nájem baterie** – zákazník ho přestane platit, SPV ho přestane
       inkasovat,
    2. **splátka klesne** na samotnou elektrárnu (úvěr na baterii je splacený),
    3. **zákazník baterii odkoupí** – jednorázový příjem SPV a výdaj zákazníka,
       a od té chvíle si zákazník platí servis a EMS sám.

    Odkup je **kapitálový** příjem, takže do DSCR nevstupuje: banka poměřuje
    provozní zdroje proti dluhové službě a jednorázový prodej majetku do toho
    nepatří. Do IRR vlastního kapitálu vstupuje, protože investorovi ty peníze
    reálně přijdou.

    Když kontrakt skončí nejpozději s nájmem, nic z toho se nestane – odkup
    i konec nájmu padnou až za horizont modelu, takže se nemodelují.

    `najem_kc_mesic` přepíše nájem dopočítaný z ceny baterie (sjednaný nájem
    z nabídky). Bez něj se cashflow počítalo z vzorce i tehdy, když obchodník
    zadal jiný nájem, a DSCR pak neodpovídalo tomu, co je ve smlouvě.

    `odkup_symbolicky` přepne na variantu **odkup za korunu**: zbytková hodnota
    se nedoplácí na konci, ale rovnoměrně rozpuštěná do nájmu (viz
    `navyseni_najmu_za_odkup_kc_mesic`). Pro SPV je to výměna kapitálového
    příjmu za provozní, takže DSCR i minimální cena PPA vycházejí jinak – proto
    se to počítá jako samostatný průchod, ne dopočtem nad výsledkem.
    """
    from .ppa_fve import _irr, _npv
    from .ppa_v2 import ceny_po_letech, zustatek_uveru

    n = max(1, int(delka_roky))
    ceny_ppa = ceny_po_letech(
        cena_ppa_rok1_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky
    )
    if p.indexovat_export:
        ceny_exp = ceny_po_letech(
            p.cena_exportu_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky
        )
    else:
        ceny_exp = [p.cena_exportu_kc_mwh] * n
    # Cena, kterou zákazník platí dnes, roste stejnou indexací jako cena PPA –
    # jinak by úspora umělé rostla nebo mizela jen kvůli tomu, že se jedna
    # strana rovnice indexuje a druhá ne.
    ceny_zak = ceny_po_letech(
        cena_zakaznika_kc_mwh, n, p.indexace_krok, p.indexace_perioda_roky
    )

    doba_najmu = max(1, int(doba_najmu_roky))
    ma_baterii = projekt_bess.capex_kc > 0
    najem_mesicni = (
        float(najem_kc_mesic)
        if najem_kc_mesic is not None
        else najem_baterie_kc_mesic(projekt_bess, p)
    )
    odkupni_cena = odkupni_cena_baterie_kc(projekt_bess, pb) if ma_baterii else 0.0
    # Rok, ve kterém nájem skončí a baterie přejde na zákazníka. Když kontrakt
    # skončí dřív nebo současně, k přechodu nikdy nedojde.
    rok_odkupu = doba_najmu + 1 if ma_baterii and n > doba_najmu else None
    # Varianta „odkup za korunu": zbytková hodnota se přesune z jednorázového
    # doplatku do nájmu.
    #
    # Rozpouští se **vždy, když je baterie v nájmu** – ne až když kontrakt nájem
    # přežije. Rozpuštěná část se totiž platí v nájmu, tedy uvnitř horizontu
    # modelu, i když samotný převod baterie padne až za konec kontraktu (u
    # kontraktu stejně dlouhého jako nájem). Dřív to bylo navázané na
    # `rok_odkupu`, takže u kontraktu na 10 let s 10letým nájmem varianta tiše
    # zmizela – a to je přitom nejčastěji nabízená kombinace.
    if odkup_symbolicky and ma_baterii:
        najem_mesicni += navyseni_najmu_za_odkup_kc_mesic(odkupni_cena, doba_najmu)
        odkupni_cena = ODKUP_SYMBOLICKY_KC
    najem_rocni = najem_mesicni * 12.0

    roky: list[RokPpaBess] = []
    cf = [-(projekt_fve.vlastni_kapital_kc + projekt_bess.vlastni_kapital_kc)]
    for t in range(1, n + 1):
        degradace_fve = (1.0 - p.degradace_rocni) ** (t - 1)
        vyroba = vyroba_rok1_mwh * degradace_fve
        # Samospotřeba i export klesají s výrobou; poměr mezi nimi se nemění,
        # protože profil odběru zůstává stejný.
        podil_ss = (samospotreba_rok1_mwh / vyroba_rok1_mwh) if vyroba_rok1_mwh > 0 else 0.0
        podil_ex = (export_rok1_mwh / vyroba_rok1_mwh) if vyroba_rok1_mwh > 0 else 0.0
        ss = vyroba * podil_ss
        ex = vyroba * podil_ex * max(0.0, min(1.0, p.podil_zpenezitelneho_prebytku))

        najem_letos = najem_rocni if (ma_baterii and t <= doba_najmu) else 0.0
        # Splátka: elektrárna po celou dobu, baterie jen dokud běží její úvěr.
        splatka = projekt_fve.splatka_rocni_kc
        if ma_baterii and t <= doba_najmu:
            splatka += projekt_bess.splatka_rocni_kc
        # Provozní náklady SPV: servis elektrárny vždy, servis baterie jen dokud
        # ji SPV vlastní.
        naklady = p.servis_kc_rok
        if ma_baterii and t <= doba_najmu:
            naklady += p.bess_servis_kc_rok

        prijem_ppa = ss * ceny_ppa[t - 1]
        prijem_ex = ex * ceny_exp[t - 1]
        odkup_prijem = odkupni_cena if (rok_odkupu is not None and t == rok_odkupu) else 0.0

        # Rozpad splátky na úrok a úmor. Úmor je rozdíl zůstatků na začátku
        # a na konci roku, úrok je zbytek splátky — analyticky přes
        # `zustatek_uveru`, bez iterace kalendáře. Počítá se pro oba úvěry
        # zvlášť, protože mají jinou splatnost (FVE délka kontraktu, BESS 10 let).
        umor = 0.0
        zustatek = 0.0
        for projekt in (projekt_fve, projekt_bess):
            if projekt.uver_kc <= 0:
                continue
            zac = zustatek_uveru(
                projekt.uver_kc, p.urokova_sazba, projekt.delka_roky, (t - 1) * 12
            )
            kon = zustatek_uveru(
                projekt.uver_kc, p.urokova_sazba, projekt.delka_roky, t * 12
            )
            umor += max(0.0, zac - kon)
            zustatek += kon
        urok = max(0.0, splatka - umor)

        zdroje = prijem_ppa + prijem_ex + najem_letos - naklady
        dscr = (zdroje / splatka) if splatka > 0 else None
        zisk = zdroje + odkup_prijem - splatka

        # --- zákazník
        # Přínos baterie na výkonu degraduje s kapacitou; po odkupu pokračuje,
        # protože baterie je jeho a dál sráží špičky.
        degradace_bat = (1.0 - pb.degradace_prinosu_baterie) ** (t - 1)
        uspora_vykon = uspora_vykon_rok1_kc * degradace_bat
        uspora_energie = ss * (ceny_zak[t - 1] - ceny_ppa[t - 1])
        naklad_ztrat = (
            ztraty_ze_site_rok1_kwh / 1000.0 * pb.cena_energie_kc_mwh * degradace_bat
        )
        provoz_zakaznika = 0.0
        if ma_baterii and rok_odkupu is not None and t >= rok_odkupu:
            provoz_zakaznika = p.bess_servis_kc_rok + p.bess_ems_kc_mesic * 12.0
        vydaj_odkup = odkup_prijem
        cisty = (
            uspora_energie
            + uspora_vykon
            - najem_letos
            - naklad_ztrat
            - provoz_zakaznika
            - vydaj_odkup
        )

        roky.append(
            RokPpaBess(
                rok=t,
                vyroba_mwh=vyroba,
                samospotreba_mwh=ss,
                export_mwh=ex,
                cena_ppa_kc_mwh=ceny_ppa[t - 1],
                prijem_ppa_kc=prijem_ppa,
                prijem_export_kc=prijem_ex,
                najem_baterie_kc=najem_letos,
                prijem_odkup_kc=odkup_prijem,
                provozni_naklady_kc=naklady,
                zdroje_kc=zdroje,
                splatka_kc=splatka,
                urok_kc=urok,
                umor_kc=umor,
                zustatek_uveru_kc=zustatek,
                dscr=dscr,
                zisk_po_splatkach_kc=zisk,
                kumulovany_cf_kc=0.0,  # dopočítá se po smyčce
                uspora_energie_kc=uspora_energie,
                uspora_vykon_kc=uspora_vykon,
                naklad_najmu_kc=najem_letos,
                naklad_ztrat_kc=naklad_ztrat,
                naklad_provozu_zakaznika_kc=provoz_zakaznika,
                vydaj_odkup_kc=vydaj_odkup,
                cisty_prinos_zakaznika_kc=cisty,
            )
        )
        cf.append(zisk)

    # Kumulovaný cash flow vlastního kapitálu a rok, kdy překlopí do plusu.
    vlozeno = projekt_fve.vlastni_kapital_kc + projekt_bess.vlastni_kapital_kc
    kum = -vlozeno
    navratnost_vk = None
    for r in roky:
        predchozi = kum
        kum += r.zisk_po_splatkach_kc
        r.kumulovany_cf_kc = kum
        if navratnost_vk is None and predchozi < 0 <= kum:
            # Lineární interpolace v roce překlopení – „vrátí se ve 7,4. roce"
            # je použitelnější než „mezi 7. a 8.".
            if r.zisk_po_splatkach_kc > 0:
                navratnost_vk = (r.rok - 1) + (-predchozi) / r.zisk_po_splatkach_kc
            else:
                navratnost_vk = float(r.rok)

    dscr_hodnoty = [r.dscr for r in roky if r.dscr is not None]
    capex_celkem = projekt_fve.capex_kc + projekt_bess.capex_kc
    return CashflowPpaBess(
        roky=roky,
        vlastni_kapital_kc=projekt_fve.vlastni_kapital_kc + projekt_bess.vlastni_kapital_kc,
        capex_kc=capex_celkem,
        capex_fve_kc=projekt_fve.capex_kc,
        capex_bess_kc=projekt_bess.capex_kc,
        najem_baterie_kc_mesic=najem_mesicni,
        dscr_min=min(dscr_hodnoty) if dscr_hodnoty else None,
        irr=_irr(cf[1:], -cf[0]) if cf[0] < 0 else None,
        npv_kc=_npv(cf[1:], -cf[0], p.diskontni_sazba) if cf[0] < 0 else 0.0,
        cf_vlastniho_kapitalu=cf,
        zisk_greensie_kc=projekt_fve.zisk_greensie_kc + projekt_bess.zisk_greensie_kc,
        provize_kc=projekt_fve.provize_kc + projekt_bess.provize_kc,
        odkupni_cena_baterie_kc=odkupni_cena,
        uspora_celkem_kc=sum(r.cisty_prinos_zakaznika_kc for r in roky),
        prinos_energie_celkem_kc=sum(r.uspora_energie_kc for r in roky),
        prinos_vykon_celkem_kc=sum(r.uspora_vykon_kc for r in roky),
        prijmy_ppa_celkem_kc=sum(r.prijem_ppa_kc for r in roky),
        prijmy_najem_celkem_kc=sum(r.najem_baterie_kc for r in roky),
        prijmy_export_celkem_kc=sum(r.prijem_export_kc for r in roky),
        prijmy_odkup_celkem_kc=sum(r.prijem_odkup_kc for r in roky),
        naklady_provozni_celkem_kc=sum(r.provozni_naklady_kc for r in roky),
        uroky_celkem_kc=sum(r.urok_kc for r in roky),
        umor_celkem_kc=sum(r.umor_kc for r in roky),
        navratnost_vlastniho_kapitalu_roky=navratnost_vk,
    )


# --------------------------------------------------------- inverzní úloha: cena PPA
@dataclass
class MinimalniCena:
    """Nejnižší cena PPA, se kterou projekt projde bankou i investorem."""

    cena_kc_mwh: float
    dscr_min: float | None
    irr: float | None
    limitujici: str  # 'dscr' | 'irr' | 'nedosazitelne'


def minimalni_cena_ppa(
    vyroba_rok1_mwh: float,
    samospotreba_rok1_mwh: float,
    export_rok1_mwh: float,
    uspora_vykon_rok1_kc: float,
    ztraty_ze_site_rok1_kwh: float,
    cena_zakaznika_kc_mwh: float,
    projekt_fve,
    projekt_bess,
    p,
    pb: ParametryPpaBess,
    delka_roky: int,
    strop_kc_mwh: float | None = None,
    doba_najmu_roky: int = DOBA_NAJMU_BATERIE_ROKY,
    najem_kc_mesic: float | None = None,
    odkup_symbolicky: bool = False,
) -> MinimalniCena:
    """Bisekcí najde nejnižší cenu PPA, kde projde DSCR i IRR.

    PPA v2 to řeší analyticky (`cena_ppa_z_dscr`), protože tam je splátka i nájem
    po celou dobu konstantní a nejtěsnější rok se dá spočítat přímo. Tady se
    splátka po skončení nájmu láme a v roce odkupu přijde jednorázový příjem,
    takže analytické řešení neexistuje – bisekce je poctivější než ho složitě
    obcházet.

    Poslední tři parametry se jen předávají do `spocti_cashflow`; cena musí být
    hledaná nad **týmž** cashflow, jaký se pak zobrazí, jinak by u varianty
    „odkup za korunu" vyšla cena z jiného modelu než DSCR.

    Obě kritéria jsou v ceně monotónní (vyšší cena = víc zdrojů = vyšší DSCR
    i IRR), takže bisekce konverguje. Vrací i to, které kritérium bylo těsnější.
    """
    strop = strop_kc_mwh if strop_kc_mwh and strop_kc_mwh > 0 else max(
        5_000.0, cena_zakaznika_kc_mwh * 3.0
    )

    from .ppa_fve import _npv

    def projde(cena: float) -> tuple[bool, bool, float | None, float | None]:
        cf = spocti_cashflow(
            vyroba_rok1_mwh,
            samospotreba_rok1_mwh,
            export_rok1_mwh,
            uspora_vykon_rok1_kc,
            ztraty_ze_site_rok1_kwh,
            cena,
            cena_zakaznika_kc_mwh,
            projekt_fve,
            projekt_bess,
            p,
            pb,
            delka_roky,
            doba_najmu_roky=doba_najmu_roky,
            najem_kc_mesic=najem_kc_mesic,
            odkup_symbolicky=odkup_symbolicky,
        )
        ok_dscr = cf.dscr_min is None or cf.dscr_min >= p.dscr_min
        # Kritérium investora se testuje **NPV při cílové sazbě**, ne přes IRR.
        # `ppa_fve._irr` bisekuje na [−0,9; 1,0] a vrací None, když v tom
        # intervalu NPV nemění znaménko – což se stane i tehdy, když je výnos
        # vysoko NAD 100 %. Test na `irr is not None` proto padal na obou
        # koncích a projekt se hlásil jako nefinancovatelný i při DSCR 4,4.
        # NPV ≥ 0 při diskontu `irr_cil` je s IRR ≥ cíl ekvivalentní, jen se
        # nikdy nerozbije.
        vlastni = -cf.cf_vlastniho_kapitalu[0]
        ok_irr = _npv(cf.cf_vlastniho_kapitalu[1:], vlastni, p.irr_cil) >= 0.0
        return ok_dscr, ok_irr, cf.dscr_min, cf.irr

    ok_dscr, ok_irr, dscr_h, irr_h = projde(strop)
    if not (ok_dscr and ok_irr):
        return MinimalniCena(strop, dscr_h, irr_h, "nedosazitelne")

    lo, hi = 0.0, strop
    for _ in range(60):
        mid = (lo + hi) / 2.0
        ok_d, ok_i, _, _ = projde(mid)
        if ok_d and ok_i:
            hi = mid
        else:
            lo = mid
    ok_d, ok_i, dscr_h, irr_h = projde(hi)
    # Které kritérium cenu drží: to, které při nepatrně nižší ceně spadne první.
    # Porovnávat „rezervy" u nalezené ceny nešlo – obě jsou na hraně nuly.
    limit = "dscr"
    ok_d_pod, ok_i_pod, _, _ = projde(max(0.0, hi * 0.98))
    if ok_d_pod and not ok_i_pod:
        limit = "irr"
    elif not ok_d_pod and ok_i_pod:
        limit = "dscr"
    elif not ok_d_pod and not ok_i_pod:
        # Spadnou obě – rozhoduje DSCR, protože banka je tvrdší limit.
        limit = "dscr"
    return MinimalniCena(hi, dscr_h, irr_h, limit)


# --------------------------------------------------------------------------- orchestrace
@dataclass
class PoleFve:
    """Jedno pole elektrárny – vlastní orientace a výkon.

    Když obchodník zná rozpad střechy („na jih 200 kWp, na východ 100, na západ
    100"), nemá smysl velikost navrhovat: je daná. Výroba se pak simuluje pro
    každé pole zvlášť a sečte, takže model zná i **tvar** výroby – a ten je
    u východ-západ výrazně plošší než u jihu. To mění, kolik se spotřebuje
    přímo, kolik přeteče do baterie a jak vysoko zůstanou špičky.
    """

    kwp: float
    sklon_st: float = 35.0
    azimut_st: float = 0.0  # 0 = jih, −90 = východ, +90 = západ, 180 = sever
    # Nákladová cena za kWp jen pro tohle pole. `None` = vezme se z manažerského
    # nastavení (`ppa_nakladova_cena_kc_kwp`). Přepis je tu proto, že jedno pole
    # umí být výrazně dražší než druhé – jiné kotvení, trapéz proti ploché střeše
    # s balastem, delší kabelové trasy – a paušál za celou elektrárnu by pak
    # zkreslil CAPEX, a s ním i cenu PPA.
    cena_kc_kwp: float | None = None
    # Východ-západní konstrukce: jeden blok panelů, polovina na východ a polovina
    # na západ. Zadá se jednou (celkový výkon a sklon) a rozloží se na dvě pole
    # 50/50, ať to obchodník nemusí psát dvakrát. `azimut_st` se pak bere jako
    # **osa** – 0 znamená klasické V/Z (−90 a +90), 30 pootočenou střechu
    # (−60 a +120).
    rozdelit_vychod_zapad: bool = False
    # Vyplní `rozloz_pole` u polovin, které vznikly rozdělením. Panel je tím
    # označí, aby nikdo nehledal, odkud se vzalo pole, které nezadal – tři
    # zadaná pole s jedním V/Z dávají ve výsledku čtyři.
    z_rozdeleni_vz: bool = False


def rozloz_pole(pole: tuple[PoleFve, ...]) -> tuple[PoleFve, ...]:
    """Rozloží pole označená jako východ-západ na dvě poloviny.

    Výpočet dál pracuje s obyčejnými poli, takže o téhle zkratce nemusí nic
    vědět – rozloží se jednou na vstupu. Zachovává cenu za kWp i sklon, jen
    půlí výkon a otáčí azimut o ±90° od zadané osy.
    """
    out: list[PoleFve] = []
    for f in pole:
        if not f.rozdelit_vychod_zapad:
            out.append(f)
            continue
        for smer in (-90.0, 90.0):
            out.append(
                PoleFve(
                    kwp=f.kwp / 2.0,
                    sklon_st=f.sklon_st,
                    azimut_st=f.azimut_st + smer,
                    cena_kc_kwp=f.cena_kc_kwp,
                    z_rozdeleni_vz=True,
                )
            )
    return tuple(out)


def _miri_takmer_na_sever(azimut_st: float) -> bool:
    """Míří pole do 30° od severu? (|azimut| > 150°)

    Hranice je schválně přísná, ne 112,5° jako u pojmenování světových stran:
    osa 30° dává poloviny na −60° a +120°, tedy jihovýchod a severozápad, a to
    je **legitimní** zadání pootočené střechy (je tak i v dokumentaci modulu).
    Chytat se má jen případ, kdy si obchodník spletl osu s orientací panelů —
    napsal 90 nebo −90 a dostal polovinu skoro přesně na sever.
    """
    return abs(((azimut_st + 180.0) % 360.0) - 180.0) > 150.0


def zkontroluj_osu_rozdeleni(pole_zadani: tuple[PoleFve, ...]) -> list[str]:
    """Upozornění, když osa V/Z rozdělení míří jinam, než obchodník myslel.

    `azimut_st` je u rozdělovaného pole **osa**, ne orientace panelů – poloviny
    vzniknou na −90° a +90° od ní. Kdo tam napíše 90 s tím, že „panely míří na
    západ", dostane poloviny na 0° a 180°, tedy jednu na jih a druhou **na
    sever**. Model to spočítá poslušně a severní polovina jen tiše nevyrábí.

    Narazil na to Dan 6. 8. 2026 na nabídce, kde takhle vzniklo 150 kWp na
    sever. Radši to říct nahlas než nechat obchodníka poslat zákazníkovi
    podstřelenou výrobu.
    """
    zpravy: list[str] = []
    for i, f in enumerate(pole_zadani, start=1):
        if not f.rozdelit_vychod_zapad:
            continue
        severni = [f.azimut_st + s for s in (-90.0, 90.0) if _miri_takmer_na_sever(f.azimut_st + s)]
        if severni:
            zpravy.append(
                f"**Pole {i} má osu rozdělení {f.azimut_st:.0f}°, takže jedna polovina "
                f"míří na {_nazev_orientace(severni[0])}** – u východo-západní "
                f"konstrukce má být osa 0° (poloviny na východ a na západ). "
                f"S osou {f.azimut_st:.0f}° vyjdou poloviny na "
                f"{_nazev_orientace(f.azimut_st - 90):s} a {_nazev_orientace(f.azimut_st + 90):s}, "
                f"takže {f.kwp / 2.0:.0f} kWp výpočtu skoro nevyrábí. Zkontroluj osu."
            )
    return zpravy


@dataclass
class VstupPpaBess:
    """Vstupy výpočtu – to, co zadává obchodník.

    Minimum je diagram, rezervovaná kapacita, rezervovaný příkon, distributor
    s hladinou, cena silové složky a strop kWp. Všechno ostatní má default nebo
    se dopočítá.
    """

    casy: list[datetime]
    spotreba_kwh: list[float]  # kWh za interval (ne kW!)
    # Co zákazník platí dnes za energii – to, co PPA nahrazuje.
    cena_silova_kc_mwh: float
    # Rezervovaná kapacita (distribuční smlouva) a rezervovaný příkon (smlouva
    # o připojení). RP je pro model 2027 to podstatné číslo.
    rezervovana_kapacita_kw: float
    rezervovany_prikon_kw: float | None = None
    hladina: str = "VN"
    # Sazby NTS 2027 ze sazebníku (`sazby_distributoru.parametry`). Bez nich se
    # peak shavingová část nedá ocenit a výpočet to řekne, místo aby tipoval.
    parametry_2027: dict | None = None
    je_modelovy_odhad_2027: bool = True
    vyhnutelne_regulovane_kc_mwh: float = 260.0
    cil_mira_samospotreby: float = 0.80
    cena_exportu_kc_mwh: float | None = None
    max_kwp: float | None = None
    rezervovany_vykon_dodavky_kw: float | None = None
    lat_deg: float = 49.8
    # Orientace jednoho pole – použije se, když `pole` je prázdné a velikost se
    # tedy navrhuje z cíle samospotřeby.
    sklon_st: float = 35.0
    azimut_st: float = 0.0
    # Rozpad elektrárny na pole s vlastní orientací. Když je vyplněný, velikost
    # se **nenavrhuje** – je daná součtem výkonů polí a `max_kwp` ani cíl
    # samospotřeby ji už neovlivní.
    pole: tuple[PoleFve, ...] = ()
    merny_vynos_kwh_kwp: float = 1055.0
    # Baterie: buď ruční zadání, nebo výběr z katalogu. Ruční má přednost.
    baterie: Baterie | None = None
    baterie_katalog: tuple[ProduktBaterie, ...] = ()
    # Sjednaný nájem (Kč/měsíc). Když je zadaný, použije se místo vzorce a
    # výpočet ukáže, jak se rozchází s tím, co vychází z ceny baterie.
    najem_kc_mesic_rucne: float | None = None
    # Na kolik let se baterie pronajímá a financuje. Nezávisí na délce kontraktu
    # na elektrárnu: delší nájem = nižší splátka úvěru = nižší měsíční nájem, ale
    # pozdější odkup. Default 10 let.
    doba_najmu_baterie_roky: int = DOBA_NAJMU_BATERIE_ROKY
    nabizene_delky_roky: tuple[int, ...] = (10, 15, 20)
    rezerva_rk_procenta: float = 5.0
    interval_h: float | None = None
    parametry: object | None = None  # ppa_v2.ParametryEkonomiky
    parametry_bess: ParametryPpaBess | None = None


def _kc(hodnota: float) -> str:
    """Částka s mezerou jako oddělovačem tisíců – pro texty upozornění."""
    return f"{hodnota:,.0f}".replace(",", " ")


def nakladova_cena_fve(kwp: float, pole: tuple[PoleFve, ...], p) -> float:
    """Nákladová cena elektrárny (Kč) – s ohledem na ceny jednotlivých polí.

    Bez rozpadu na pole je to jednoduše `kwp × cena z nastavení`. Když jsou pole
    zadaná, sečtou se **po polích**, aby se uplatnil případný přepis ceny za kWp
    u konkrétního pole. Jedno místo pro obě cesty a pro všechny volající —
    kdyby si to každý počítal sám, přepis by se někde tiše ztratil a CAPEX by
    vyšel jinak v ekonomice než ve screeningu katalogu.
    """
    if not pole:
        return kwp * p.nakladova_cena_kc_kwp
    return sum(
        f.kwp * (f.cena_kc_kwp if f.cena_kc_kwp and f.cena_kc_kwp > 0 else p.nakladova_cena_kc_kwp)
        for f in pole
    )


def _nazev_orientace(azimut_st: float) -> str:
    """Světová strana z azimutu (0 = jih) – jen pro čitelnost výstupu."""
    a = ((azimut_st + 180.0) % 360.0) - 180.0
    for hranice, nazev in (
        (22.5, "jih"),
        (67.5, "jihovýchod" if a < 0 else "jihozápad"),
        (112.5, "východ" if a < 0 else "západ"),
        (157.5, "severovýchod" if a < 0 else "severozápad"),
    ):
        if abs(a) <= hranice:
            return nazev
    return "sever"


def _naklad_vykonu_2027(
    rp_kw: float, parametry_2027: dict
):
    """Vrátí callback `maxima_kw -> Kč/rok` pro volbu měsíčních stropů.

    Používá se scénář **bez snížení RP** (rezervovaný příkon zůstane, jak je),
    protože kapacitní složka je pak fixní a volbu stropů ovlivňuje jen složka za
    naměřenou špičku. Vědomé zjednodušení: se snížením RP by volba stropů vyšla
    téměř stejná (náklad je v maximech monotónní v obou scénářích), a druhý
    dispatch by zdvojnásobil čas výpočtu.
    """

    def naklad(maxima_kw: dict[int, float]) -> float:
        # `_rocni_naklad_2027` je privátní, ale je to jediná cesta k nákladu bez
        # celé ekonomiky – a jsme ve stejném balíčku, takže to není cizí zámek.
        naklad_kc, _, _ = peak_shaving._rocni_naklad_2027(rp_kw, maxima_kw, parametry_2027)
        return naklad_kc

    return naklad


def _ekonomika_vykonu(
    site_bez_kw: list[float],
    mesice: list[int],
    cilova_maxima_kw: dict[int, float],
    rp_soucasny_kw: float,
    parametry_2027: dict,
    je_modelovy_odhad: bool,
    rezerva_rk_procenta: float,
    snizit_rp: bool,
) -> dict:
    """Ekonomika rezervované kapacity nad maximy z našeho dispatchu.

    Baseline je **profil po odečtení výroby FVE, bez baterie** – tedy co by
    zákazník platil, kdyby si postavil jen elektrárnu. Přínos baterie se tak
    nepočítá proti stavu bez elektrárny, což by ho nadhodnotilo.

    `mesicni_maxima_s_baterii` předáváme hotová, protože je nespočítal peak
    shaving, ale náš dvoucílový dispatch. Důsledek: `ekonomika_2027` si v tom
    případě nepočítá ztráty cyklování (nemá z čeho) a vrací je nulové – ocenit
    je musí volající, viz `ztraty_ze_site_kwh` ve `VysledekRoku`.
    """
    # `vykon_kw` a `kapacita_kwh` jsou schválně nulové: s předanými maximy je
    # `ekonomika_2027` nepoužije (viz peak_shaving.py:802–805).
    return peak_shaving.ekonomika_2027(
        site_bez_kw,
        mesice,
        rp_soucasny_kw,
        rp_soucasny_kw,
        vykon_kw=0.0,
        kapacita_kwh=0.0,
        parametry=parametry_2027,
        je_modelovy_odhad=je_modelovy_odhad,
        optimalizovat_rp=snizit_rp,
        rezerva_rk_procenta=rezerva_rk_procenta,
        mesicni_maxima_s_baterii=cilova_maxima_kw,
    )


@dataclass
class VysledekRezimu:
    """Co baterie v daném režimu udělala a co to zákazníkovi přineslo za rok 1."""

    rezim: str
    nazev: str
    # Energie
    samospotreba_kwh: float
    prima_samospotreba_kwh: float
    # Z elektrárny přes baterii (po ztrátách) – tohle je to, co baterie přidala
    # k samospotřebě. Odděleno od `na_spicky_kwh`, protože ta energie pochází
    # ze sítě a s cenou PPA nemá nic společného.
    z_fve_pres_baterii_kwh: float
    na_spicky_kwh: float
    export_kwh: float
    ztraty_ze_site_kwh: float
    cyklu: float
    mira_samospotreby: float  # samospotřeba / výroba
    pokryti_spotreby: float  # samospotřeba / spotřeba
    # Výkon (peak shaving)
    uspora_vykon_bez_snizeni_rp_kc: float
    uspora_vykon_se_snizenim_rp_kc: float
    rp_novy_kw: float | None
    maximum_bez_baterie_kw: float
    maximum_po_baterii_kw: float
    # Měsíční rozpad
    volby: list[MesicniVolba] = field(default_factory=list)
    cilova_maxima_kw: dict[int, float] = field(default_factory=dict)
    ekonomika_vykonu: dict = field(default_factory=dict)
    ekonomika_vykonu_se_snizenim: dict = field(default_factory=dict)


def spocti_rezim(
    vstup: VstupPpaBess,
    vyroba_kwh: list[float],
    mesice: list[int],
    baterie: Baterie | None,
    rezim: str,
    interval_h: float,
    hodnota_kwh_kc: float,
    pb: ParametryPpaBess,
) -> tuple[VysledekRezimu, VysledekRoku]:
    """Dispatch a ekonomika výkonu pro jeden režim baterie.

    Vrací i surový `VysledekRoku`, aby si volající mohl vzít měsíční maxima do
    ekonomiky PPA, aniž by se dispatch počítal znovu.
    """
    rp_soucasny = vstup.rezervovany_prikon_kw or vstup.rezervovana_kapacita_kw
    sazby = vstup.parametry_2027 or {}
    ma_sazby = bool(sazby) and all(sazby.get(k) is not None for k in peak_shaving.KLICE_2027)

    naklad_vykonu = (
        _naklad_vykonu_2027(rp_soucasny, sazby)
        if ma_sazby
        # Bez sazeb se nedá ocenit kilowatt, takže volba stropu nemá o co se
        # opřít – model zůstane na nejnižším udržitelném stropu (dnešní peak
        # shaving) a upozornění to řekne.
        else (lambda maxima: 0.0)
    )

    rok = simuluj_rok(
        vstup.spotreba_kwh,
        vyroba_kwh,
        mesice,
        baterie,
        naklad_vykonu,
        interval_h,
        vstup.rezervovany_vykon_dodavky_kw,
        hodnota_kwh_kc=hodnota_kwh_kc,
        rezim=rezim,
    )

    site_bez_kw = [
        max(0.0, vstup.spotreba_kwh[i] - (vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0))
        / interval_h
        for i in range(len(vstup.spotreba_kwh))
    ]
    ek_bez: dict = {}
    ek_se: dict = {}
    if ma_sazby:
        ek_bez = _ekonomika_vykonu(
            site_bez_kw,
            mesice,
            rok.cilova_maxima_kw,
            rp_soucasny,
            sazby,
            vstup.je_modelovy_odhad_2027,
            vstup.rezerva_rk_procenta,
            snizit_rp=False,
        )
        ek_se = _ekonomika_vykonu(
            site_bez_kw,
            mesice,
            rok.cilova_maxima_kw,
            rp_soucasny,
            sazby,
            vstup.je_modelovy_odhad_2027,
            vstup.rezerva_rk_procenta,
            snizit_rp=True,
        )

    vyroba_celkem = sum(vyroba_kwh)
    spotreba_celkem = sum(vstup.spotreba_kwh)
    ucinnost = baterie.ucinnost_round_trip if baterie else 1.0
    ztraty_ze_site = rok.ps_nabito_ze_site_kwh * max(0.0, 1.0 - ucinnost)

    vysledek = VysledekRezimu(
        rezim=rezim,
        nazev=REZIM_NAZVY.get(rezim, rezim),
        samospotreba_kwh=rok.samospotreba_kwh,
        prima_samospotreba_kwh=rok.prima_samospotreba_kwh,
        z_fve_pres_baterii_kwh=rok.z_fve_pres_baterii_kwh,
        na_spicky_kwh=rok.ps_vybito_kwh,
        export_kwh=rok.export_kwh,
        ztraty_ze_site_kwh=ztraty_ze_site,
        cyklu=rok.cyklu,
        mira_samospotreby=(rok.samospotreba_kwh / vyroba_celkem) if vyroba_celkem > 0 else 0.0,
        pokryti_spotreby=(
            (rok.samospotreba_kwh / spotreba_celkem) if spotreba_celkem > 0 else 0.0
        ),
        uspora_vykon_bez_snizeni_rp_kc=float(ek_bez.get("prinos_baterie") or 0.0),
        uspora_vykon_se_snizenim_rp_kc=float(ek_se.get("prinos_baterie") or 0.0),
        rp_novy_kw=ek_se.get("rp_novy_kw"),
        maximum_bez_baterie_kw=max(rok.maxima_bez_baterie_kw.values(), default=0.0),
        maximum_po_baterii_kw=max(rok.cilova_maxima_kw.values(), default=0.0),
        volby=rok.volby,
        cilova_maxima_kw=rok.cilova_maxima_kw,
        ekonomika_vykonu=ek_bez,
        ekonomika_vykonu_se_snizenim=ek_se,
    )
    return vysledek, rok


def graf_vyroba_spotreba(volby: list[MesicniVolba]) -> dict:
    """Měsíční agregáty pro graf výroba vs. spotřeba.

    Tvar odpovídá tomu, co čeká komponenta `GrafVyrobaSpotreba.jsx` – stejná,
    jakou používá PPA panel, takže se nemusí psát nový graf. Skládá se
    z měsíčních výsledků dispatchu, ne novým průchodem: čísla v grafu se tak
    nemohou rozejít s tabulkami.

    `samospotreba_kwh` je přímá samospotřeba **plus** to, co dorazilo přes
    baterii — v grafu jde o „spotřebu krytou z elektrárny", a je jedno, jestli
    energie tekla přímo nebo se cestou zastavila v baterii.
    """
    mesice = list(range(1, 13))
    podle_mesice = {v.mesic: v for v in volby}
    r2 = lambda hodnoty: [round(x, 2) for x in hodnoty]  # noqa: E731

    def per_mesic(fce) -> list[float]:
        return [fce(podle_mesice[m]) if m in podle_mesice else 0.0 for m in mesice]

    return {
        "mesice": mesice,
        "spotreba_kwh": r2(per_mesic(lambda v: v.spotreba_kwh)),
        "vyroba_kwh": r2(per_mesic(lambda v: v.vyroba_kwh)),
        "samospotreba_kwh": r2(
            per_mesic(lambda v: v.prima_samospotreba_kwh + v.z_fve_pres_baterii_kwh)
        ),
        "export_kwh": r2(per_mesic(lambda v: v.export_kwh)),
        "orez_kwh": r2(per_mesic(lambda v: v.orezano_kwh)),
        # Dokup = co se skutečně odebralo ze sítě (síťový tok po baterii).
        "dokup_kwh": r2(per_mesic(lambda v: v.ze_site_kwh)),
    }


def graf_maxima(volby: list[MesicniVolba]) -> dict:
    """Měsíční maxima odběru bez baterie vs. po baterii.

    Tvar pro komponentu `GrafOdberu.jsx` (tu používá peak shaving). Maxima
    „bez baterie" jsou už **po odečtení výroby elektrárny** – tedy co by
    zákazník naměřil, kdyby si postavil jen elektrárnu. Proti tomu se poctivě
    poměřuje, co přidala baterie.
    """
    ms = sorted(v.mesic for v in volby)
    podle_mesice = {v.mesic: v for v in volby}
    return {
        "mesice": ms,
        "bez_baterie_kw": [round(podle_mesice[m].maximum_bez_baterie_kw, 2) for m in ms],
        "s_baterii_kw": [round(podle_mesice[m].maximum_po_baterii_kw, 2) for m in ms],
        "stropy_kw": [round(podle_mesice[m].strop_kw, 2) for m in ms],
    }


def _rezim_json(
    v: VysledekRezimu,
    prinos_energie_kc: float,
    najem_rocni_kc: float,
    prinos_energie_po_delkach: dict[int, float] | None = None,
) -> dict:
    """Jeden režim k serializaci do `popis_json` – rozpad „kdy na co".

    `prinos_energie_kc` se počítá z **nejdražší** nabízené ceny PPA (nejkratší
    kontrakt), aby srovnání režimů nikdy nevypadalo lepší, než jaká bude nejhorší
    nabídka. `prinos_energie_po_delkach` k tomu dává totéž pro každou délku, aby
    panel mohl rozpad přepnout podle toho, kterou délku obchodník zvolil – jinak
    by dlaždice tvrdily jiné číslo než tabulka délek.
    """
    cisty_bez = prinos_energie_kc + v.uspora_vykon_bez_snizeni_rp_kc - najem_rocni_kc
    cisty_se = prinos_energie_kc + v.uspora_vykon_se_snizenim_rp_kc - najem_rocni_kc
    po_delkach = {
        str(delka): {
            "z_energie_kc": round(hodnota, 2),
            "cisty_bez_snizeni_rp_kc": round(
                hodnota + v.uspora_vykon_bez_snizeni_rp_kc - najem_rocni_kc, 2
            ),
            "cisty_se_snizenim_rp_kc": round(
                hodnota + v.uspora_vykon_se_snizenim_rp_kc - najem_rocni_kc, 2
            ),
        }
        for delka, hodnota in (prinos_energie_po_delkach or {}).items()
    }
    return {
        "prinos_po_delkach": po_delkach,
        "rezim": v.rezim,
        "nazev": v.nazev,
        "energie": {
            "samospotreba_mwh": round(v.samospotreba_kwh / 1000.0, 3),
            "prima_samospotreba_mwh": round(v.prima_samospotreba_kwh / 1000.0, 3),
            "z_fve_pres_baterii_mwh": round(v.z_fve_pres_baterii_kwh / 1000.0, 3),
            "na_spicky_mwh": round(v.na_spicky_kwh / 1000.0, 3),
            "export_mwh": round(v.export_kwh / 1000.0, 3),
            "ztraty_ze_site_mwh": round(v.ztraty_ze_site_kwh / 1000.0, 3),
            "cyklu_rok": round(v.cyklu, 1),
            "mira_samospotreby": round(v.mira_samospotreby, 4),
            "pokryti_spotreby": round(v.pokryti_spotreby, 4),
        },
        "vykon": {
            "maximum_bez_baterie_kw": round(v.maximum_bez_baterie_kw, 2),
            "maximum_po_baterii_kw": round(v.maximum_po_baterii_kw, 2),
            "sraz_kw": round(max(0.0, v.maximum_bez_baterie_kw - v.maximum_po_baterii_kw), 2),
            "rp_novy_kw": round(v.rp_novy_kw, 2) if v.rp_novy_kw is not None else None,
        },
        # Rozpad přínosu – přesně to, na co se Dan ptal: kolik Kč přišlo z kW
        # a kolik z kWh.
        "prinos": {
            "z_energie_kc": round(prinos_energie_kc, 2),
            "z_vykonu_bez_snizeni_rp_kc": round(v.uspora_vykon_bez_snizeni_rp_kc, 2),
            "z_vykonu_se_snizenim_rp_kc": round(v.uspora_vykon_se_snizenim_rp_kc, 2),
            "najem_baterie_kc": round(najem_rocni_kc, 2),
            "cisty_bez_snizeni_rp_kc": round(cisty_bez, 2),
            "cisty_se_snizenim_rp_kc": round(cisty_se, 2),
        },
        "mesice": [
            {
                "mesic": mv.mesic,
                "strop_kw": round(mv.strop_kw, 2),
                "nejnizsi_udrzitelny_kw": round(mv.strop_nejnizsi_udrzitelny_kw, 2),
                "maximum_bez_baterie_kw": round(mv.maximum_bez_baterie_kw, 2),
                "maximum_po_baterii_kw": round(mv.maximum_po_baterii_kw, 2),
                "z_baterie_kwh": round(mv.z_baterie_do_odberu_kwh, 1),
                "na_spicky_kwh": round(mv.ps_vybito_kwh, 1),
                "cyklu": round(mv.cyklu, 2),
                "kandidatu": mv.kandidatu,
            }
            for mv in v.volby
        ],
        # Rozpad úspory na rezervované kapacitě z `peak_shaving.ekonomika_2027`
        # (19 klíčů: současný náklad, fér baseline bez investice, přínos baterie,
        # nové RP, měsíce s překročením…). Panel z toho staví stejnou tabulku,
        # jakou má peak shaving — obchodník nemá u nového modulu hledat, kde se
        # kilowatty rozpadly.
        "ekonomika_vykonu": v.ekonomika_vykonu,
        "ekonomika_vykonu_se_snizenim": v.ekonomika_vykonu_se_snizenim,
        # Data pro grafy. Skládají se z týchž měsíčních výsledků jako tabulky,
        # takže se nemohou rozejít.
        "graf": graf_vyroba_spotreba(v.volby),
        "graf_maxima": graf_maxima(v.volby),
    }


@dataclass
class VariantaKatalogu:
    """Jedna posouzená konfigurace z katalogu (produkt × počet kusů)."""

    produkt_id: int
    nazev: str
    pocet_kusu: int
    kapacita_kwh: float
    vyuzitelna_kapacita_kwh: float
    vykon_kw: float
    nakladova_cena_kc: float
    najem_kc_mesic: float
    # Přínos v roce 1: energie (za nejdražší nabízenou cenu) + výkon − nájem.
    prinos_energie_kc: float
    prinos_vykon_kc: float
    cisty_prinos_kc: float
    sraz_kw: float
    mira_samospotreby: float
    cyklu: float
    cena_je_doporucena: bool = False


def prohledej_katalog(
    vstup: VstupPpaBess,
    hlaseni=None,
    max_pocet_kusu: int = 5,
    detailne_top: int = 5,
) -> dict:
    """Projde celý katalog baterií a najde tu s nejvyšším čistým přínosem.

    Tohle je to, co heuristika z PPA neumí: ta navrhne velikost z mediánu
    denního přebytku a na ni vybere nejlevnější produkt, který ji pokryje – což
    umí přestřelit o řád (na reálné nabídce navrhla 220 kWh k elektrárně 4 kWp).
    Tady se každá konfigurace **skutečně ocení** a řadí se podle peněz.

    Běží **mimo web proces** (`vypocet_worker.py`): 84 produktů × 1–5 kusů nad
    ročním diagramem je řádově minuty, uvnitř uvicornu by to skončilo 502.

    Dvě úrovně, aby to bylo únosné:

    1. **Screening** – každá konfigurace se ocení v režimu `spicky` (jeden
       dispatch místo tří) a s hrubým odhadem hodnoty kWh. Počet kusů se
       zvyšuje jen dokud přínos roste (greedy, stejně jako
       `peak_shaving.vyber_reseni`), takže se typicky nezkouší všech pět.
    2. **Detail** – nejlepších `detailne_top` konfigurací se prohnat plným
       výpočtem (`spocti_ppa_bess`) se všemi třemi režimy a celou ekonomikou.

    `hlaseni(hotovo, celkem, zprava)` je volitelný callback pro pokrok – worker
    jím plní `nabidkovac_vypocet_fronta`, aby panel mohl ukázat „120 ze 420".

    Vrací `{"vysledek": <plný výpočet nejlepší>, "varianty": [...], "prohledano": N}`.
    Když katalog nic použitelného nemá, `vysledek` je `None` a je to
    v upozorněních.
    """
    from .ppa_fve import simuluj_vyrobu
    from .ppa_v2 import ParametryEkonomiky, VYCHOZI_MIN_SLEVA, sestav_projekt

    p = vstup.parametry or ParametryEkonomiky()
    pb = vstup.parametry_bess or ParametryPpaBess()
    katalog = tuple(
        x for x in (vstup.baterie_katalog or ()) if x.kapacita_kwh > 0 and x.vykon_kw > 0
    )
    if not katalog:
        return {
            "vysledek": None,
            "varianty": [],
            "prohledano": 0,
            "upozorneni": [
                "V katalogu není použitelná baterie (potřebuje výkon, kapacitu i cenu)."
            ],
        }

    interval_h = vstup.interval_h or _odvod_interval_h(vstup.casy)
    mesice = [c.month for c in vstup.casy]
    cena_zakaznika = vstup.cena_silova_kc_mwh + vstup.vyhnutelne_regulovane_kc_mwh
    hodnota_kwh = cena_zakaznika * VYCHOZI_MIN_SLEVA

    # Elektrárna se pro screening drží pevná – jinak by se pro každou baterii
    # hledala jiná velikost a varianty by nebyly srovnatelné. Doladí se až
    # v detailním průchodu, kde `spocti_ppa_bess` velikost dopočítá znovu.
    if vstup.pole:
        vyroba_kwh = [0.0] * len(vstup.casy)
        for f in vstup.pole:
            for i, x in enumerate(
                simuluj_vyrobu(
                    vstup.casy, f.kwp, vstup.lat_deg, f.sklon_st, f.azimut_st,
                    vstup.merny_vynos_kwh_kwp,
                )
            ):
                vyroba_kwh[i] += x
    else:
        from .ppa_v2 import navrhni_kwp_na_cil

        vyroba_1kwp = simuluj_vyrobu(
            vstup.casy, 1.0, vstup.lat_deg, vstup.sklon_st, vstup.azimut_st,
            vstup.merny_vynos_kwh_kwp,
        )
        kwp_screening = navrhni_kwp_na_cil(
            vyroba_1kwp, vstup.spotreba_kwh, vstup.cil_mira_samospotreby, None,
            vstup.rezervovany_vykon_dodavky_kw, interval_h, vstup.max_kwp,
        )
        vyroba_kwh = [kwp_screening * v for v in vyroba_1kwp]

    # Horní mez počtu úloh pro odhad pokroku (greedy jich udělá méně).
    celkem_odhad = len(katalog) * max(1, max_pocet_kusu)
    hotovo = 0

    def oznam(zprava: str) -> None:
        if hlaseni is not None:
            hlaseni(hotovo, celkem_odhad, zprava)

    oznam(f"Prohledávám katalog: {len(katalog)} produktů")

    varianty: list[VariantaKatalogu] = []
    for produkt in katalog:
        if produkt.cena_kc <= 0:
            continue
        predchozi_cisty = None
        for pocet in range(1, max(1, max_pocet_kusu) + 1):
            baterie = baterie_z_produktu(produkt, pocet)
            if baterie.vyuzitelna_kapacita_kwh <= 0 or baterie.vykon_kw <= 0:
                break
            vr, _ = spocti_rezim(
                vstup, vyroba_kwh, mesice, baterie, REZIM_SPICKY, interval_h, hodnota_kwh, pb
            )
            projekt_bess = sestav_projekt_bess(
                baterie.nakladova_cena_kc, p, vstup.doba_najmu_baterie_roky
            )
            najem_m = (
                vstup.najem_kc_mesic_rucne
                if vstup.najem_kc_mesic_rucne is not None
                else najem_baterie_kc_mesic(projekt_bess, p)
            )
            prinos_energie = vr.samospotreba_kwh / 1000.0 * hodnota_kwh
            cisty = prinos_energie + vr.uspora_vykon_bez_snizeni_rp_kc - najem_m * 12.0
            varianty.append(
                VariantaKatalogu(
                    produkt_id=produkt.id,
                    nazev=produkt.nazev,
                    pocet_kusu=pocet,
                    kapacita_kwh=baterie.kapacita_kwh,
                    vyuzitelna_kapacita_kwh=baterie.vyuzitelna_kapacita_kwh,
                    vykon_kw=baterie.vykon_kw,
                    nakladova_cena_kc=baterie.nakladova_cena_kc,
                    najem_kc_mesic=najem_m,
                    prinos_energie_kc=prinos_energie,
                    prinos_vykon_kc=vr.uspora_vykon_bez_snizeni_rp_kc,
                    cisty_prinos_kc=cisty,
                    sraz_kw=max(0.0, vr.maximum_bez_baterie_kw - vr.maximum_po_baterii_kw),
                    mira_samospotreby=vr.mira_samospotreby,
                    cyklu=vr.cyklu,
                    cena_je_doporucena=baterie.cena_je_doporucena,
                )
            )
            hotovo += 1
            oznam(f"{produkt.nazev} × {pocet}")
            # Greedy: další kus už nezlepšuje, takže víc jich nemá smysl zkoušet.
            # Předpokládá se unimodalita v počtu kusů (stejně jako u peak shavingu).
            if predchozi_cisty is not None and cisty <= predchozi_cisty + 1e-6:
                break
            predchozi_cisty = cisty

    if not varianty:
        return {
            "vysledek": None,
            "varianty": [],
            "prohledano": hotovo,
            "upozorneni": ["Žádná baterie z katalogu nemá vyplněnou cenu."],
        }

    varianty.sort(key=lambda v: -v.cisty_prinos_kc)
    top = varianty[: max(1, detailne_top)]
    oznam(f"Dopočítávám {len(top)} nejlepších konfigurací")

    from dataclasses import replace as _replace

    nejlepsi = None
    nejlepsi_vysledek = None
    for i, v in enumerate(top, start=1):
        produkt = next(x for x in katalog if x.id == v.produkt_id)
        baterie = baterie_z_produktu(produkt, v.pocet_kusu)
        vysledek = spocti_ppa_bess(_replace(vstup, baterie=baterie, baterie_katalog=()))
        if vysledek.get("chyba"):
            continue
        radky = vysledek.get("po_delkach") or []
        uspora = radky[0]["uspora_rok1_kc"] if radky else float("-inf")
        if nejlepsi is None or uspora > nejlepsi:
            nejlepsi, nejlepsi_vysledek = uspora, vysledek
        oznam(f"Detail {i} z {len(top)}: {v.nazev} × {v.pocet_kusu}")

    if nejlepsi_vysledek is None:
        return {
            "vysledek": None,
            "varianty": [_varianta_katalogu_json(v) for v in varianty[:50]],
            "prohledano": hotovo,
            "upozorneni": ["Ani jedna konfigurace z katalogu nedala platný výsledek."],
        }

    # Do výsledku se přibalí srovnání konfigurací, ať je vidět, co se zvažovalo
    # a o kolik je vítěz lepší. Omezeno na 50 řádků – víc už nikdo nečte a
    # `popis_json` by zbytečně narostl.
    nejlepsi_vysledek["katalog"] = {
        "prohledano_konfiguraci": hotovo,
        "produktu_v_katalogu": len(katalog),
        "varianty": [_varianta_katalogu_json(v) for v in varianty[:50]],
        "poznamka": (
            "Screening ocenil každou konfiguraci v režimu srážení špiček s hrubým odhadem "
            "hodnoty kWh; nejlepších pět se pak dopočítalo celou ekonomikou. Počet kusů "
            "se zvyšoval jen dokud přínos rostl."
        ),
    }
    if len(varianty) > 50:
        nejlepsi_vysledek.setdefault("upozorneni", []).append(
            f"Ve srovnání je 50 nejlepších konfigurací z {len(varianty)} posouzených – "
            "zbytek byl horší a do výstupu se nevešel."
        )
    return {
        "vysledek": nejlepsi_vysledek,
        "varianty": [_varianta_katalogu_json(v) for v in varianty[:50]],
        "prohledano": hotovo,
        "upozorneni": [],
    }


def _varianta_katalogu_json(v: VariantaKatalogu) -> dict:
    """Jedna konfigurace ze srovnání katalogu k serializaci."""
    return {
        "produkt_id": v.produkt_id,
        "nazev": v.nazev,
        "pocet_kusu": v.pocet_kusu,
        "kapacita_kwh": round(v.kapacita_kwh, 1),
        "vyuzitelna_kapacita_kwh": round(v.vyuzitelna_kapacita_kwh, 1),
        "vykon_kw": round(v.vykon_kw, 1),
        "nakladova_cena_kc": round(v.nakladova_cena_kc, 2),
        "najem_kc_mesic": round(v.najem_kc_mesic, 2),
        "prinos_energie_kc": round(v.prinos_energie_kc, 2),
        "prinos_vykon_kc": round(v.prinos_vykon_kc, 2),
        "cisty_prinos_kc": round(v.cisty_prinos_kc, 2),
        "sraz_kw": round(v.sraz_kw, 2),
        "mira_samospotreby": round(v.mira_samospotreby, 4),
        "cyklu_rok": round(v.cyklu, 1),
        "cena_je_doporucena": v.cena_je_doporucena,
    }


def _varianta_1kc_json(
    minc: MinimalniCena,
    cf: CashflowPpaBess,
    cena_zakaznika_kc_mwh: float,
    najem_kc_mesic: float,
    navyseni_kc_mesic: float,
    odkupni_cena_puvodni_kc: float,
    doba_najmu_roky: int,
    delka_roky: int,
) -> dict:
    """Varianta „odkup za korunu" – jen čísla, ve kterých se od základní liší.

    Není to celý `_delka_json`: obchodník u alternativy potřebuje vidět nájem,
    cenu PPA a jestli to projde bankou, ne druhý kompletní rozpad financování.
    Kdyby se sem duplikoval celý blok, `popis_json` by nabídku zdvojnásobil
    a v panelu by se nedalo poznat, které číslo patří které variantě.
    """
    nedosazitelne = minc.limitujici == "nedosazitelne"
    sleva = (
        (cena_zakaznika_kc_mwh - minc.cena_kc_mwh) / cena_zakaznika_kc_mwh
        if cena_zakaznika_kc_mwh > 0
        else 0.0
    )
    return {
        "najem_baterie_kc_mesic": round(najem_kc_mesic, 2),
        # O kolik je nájem vyšší než v základní variantě = rozpuštěný odkup.
        "navyseni_najmu_kc_mesic": round(navyseni_kc_mesic, 2),
        "odkupni_cena_baterie_kc": ODKUP_SYMBOLICKY_KC,
        # Kolik by zákazník doplatil v základní variantě – to se rozpouští.
        "odkupni_cena_puvodni_kc": round(odkupni_cena_puvodni_kc, 2),
        # Kdy baterie přejde na zákazníka: po skončení nájmu, vždy. Když kontrakt
        # končí spolu s nájmem, padne převod až za horizont modelu – zaplacené
        # ale je celé, protože se platilo v nájmu. `odkup_v_horizontu` říká, jestli
        # ten rok ještě spadá do kontraktu, ať to panel nemusí dovozovat z délek.
        "rok_odkupu": int(doba_najmu_roky) + 1,
        "odkup_v_horizontu": int(delka_roky) > int(doba_najmu_roky),
        "cena_ppa_kc_mwh": None if nedosazitelne else round(minc.cena_kc_mwh, 2),
        "sleva": None if nedosazitelne else round(sleva, 4),
        "limitujici": minc.limitujici,
        "dscr_min": round(cf.dscr_min, 3) if cf.dscr_min is not None else None,
        "irr": round(cf.irr, 4) if cf.irr is not None else None,
        "npv_kc": round(cf.npv_kc, 2),
        "uspora_rok1_kc": round(
            cf.roky[0].cisty_prinos_zakaznika_kc if cf.roky else 0.0, 2
        ),
        "uspora_celkem_kc": round(cf.uspora_celkem_kc, 2),
        "prijmy_najem_celkem_kc": round(cf.prijmy_najem_celkem_kc, 2),
    }


def _delka_json(
    minc: MinimalniCena,
    cf: CashflowPpaBess,
    delka_roky: int,
    cena_zakaznika_kc_mwh: float,
    najem_kc_mesic: float,
    doba_najmu_roky: int = DOBA_NAJMU_BATERIE_ROKY,
    odkup_1kc: dict | None = None,
    odkupni_tabulka: list[dict] | None = None,
) -> dict:
    """Jedna délka kontraktu k serializaci do `popis_json`.

    Když projekt neprojde ani na stropu bisekce (`nedosazitelne`), vrací se cena
    i sleva jako `None`. Ta cena totiž není nabídka – je to horní mez hledání –
    a slevou by vyšlo něco jako −200 %, což by v panelu vypadalo jako spočítaný
    výsledek.

    `odkup_1kc` je paralelní varianta „odkup za korunu" (viz `_varianta_1kc_json`)
    nebo `None`, když u téhle délky k odkupu vůbec nedojde.

    `odkupni_tabulka` je odkup **elektrárny** v roce t – tatáž metodika jako
    u PPA, jen nad projektem elektrárny (`ppa_v2.odkupni_tabulka_json`). Baterie
    v ní není: nájem je smluvní na dobu nájmu a baterie přechází na zákazníka
    až po něm, takže její odkup je jedno číslo (`odkupni_cena_baterie_kc`),
    ne řada po letech. Rozhodl Dan 7. 8. 2026.
    """
    nedosazitelne = minc.limitujici == "nedosazitelne"
    sleva = (
        (cena_zakaznika_kc_mwh - minc.cena_kc_mwh) / cena_zakaznika_kc_mwh
        if cena_zakaznika_kc_mwh > 0
        else 0.0
    )
    return {
        "delka_roky": delka_roky,
        "cena_ppa_kc_mwh": None if nedosazitelne else round(minc.cena_kc_mwh, 2),
        "sleva": None if nedosazitelne else round(sleva, 4),
        # Financování rozepsané jako u PPA – obchodník potřebuje vidět, z čeho
        # cena vychází, ne jen výsledné číslo.
        "financovani": {
            "capex_celkem_kc": round(cf.capex_kc, 2),
            "capex_fve_kc": round(cf.capex_fve_kc, 2),
            "capex_bess_kc": round(cf.capex_bess_kc, 2),
            "vlastni_kapital_kc": round(cf.vlastni_kapital_kc, 2),
            "uver_kc": round(cf.capex_kc - cf.vlastni_kapital_kc, 2),
            "provize_kc": round(cf.provize_kc, 2),
            "zisk_greensie_kc": round(cf.zisk_greensie_kc, 2),
            "splatka_rok1_kc": round(cf.roky[0].splatka_kc if cf.roky else 0.0, 2),
            "najem_baterie_kc_mesic": round(najem_kc_mesic, 2),
            "provozni_naklady_rok1_kc": round(
                cf.roky[0].provozni_naklady_kc if cf.roky else 0.0, 2
            ),
        },
        "limitujici": minc.limitujici,
        "dscr_min": round(cf.dscr_min, 3) if cf.dscr_min is not None else None,
        "irr": round(cf.irr, 4) if cf.irr is not None else None,
        "npv_kc": round(cf.npv_kc, 2),
        "capex_kc": round(cf.capex_kc, 2),
        "capex_fve_kc": round(cf.capex_fve_kc, 2),
        "capex_bess_kc": round(cf.capex_bess_kc, 2),
        "najem_baterie_kc_mesic": round(najem_kc_mesic, 2),
        "odkupni_cena_baterie_kc": round(cf.odkupni_cena_baterie_kc, 2),
        "doba_najmu_baterie_roky": int(doba_najmu_roky),
        "rok_odkupu": (doba_najmu_roky + 1 if delka_roky > doba_najmu_roky else None),
        # Za kolik si zákazník odkoupí ELEKTRÁRNU v roce t (baterie zvlášť, viz
        # docstring). Prázdný seznam, když se tabulka nespočítala – nabídka pak
        # blok s tabulkou sama neukáže.
        "odkupni_tabulka": odkupni_tabulka or [],
        # Alternativa: baterie za korunu, zbytková hodnota rozpuštěná do nájmu.
        "odkup_1kc": odkup_1kc,
        "uspora_rok1_kc": round(cf.roky[0].cisty_prinos_zakaznika_kc if cf.roky else 0.0, 2),
        "uspora_celkem_kc": round(cf.uspora_celkem_kc, 2),
        "prinos_energie_celkem_kc": round(cf.prinos_energie_celkem_kc, 2),
        "prinos_vykon_celkem_kc": round(cf.prinos_vykon_celkem_kc, 2),
        # --- INVESTORSKÁ STRANA: co vložíme, co nás stojí úvěr, co nám klient
        # zaplatí a kdy se nám to vrátí. Bez tohohle bloku šlo z výsledku vyčíst
        # jen to, co získá zákazník.
        "investor": {
            # Co jde z naší kapsy
            "vlastni_kapital_kc": round(cf.vlastni_kapital_kc, 2),
            "uver_kc": round(cf.capex_kc - cf.vlastni_kapital_kc, 2),
            "uroky_celkem_kc": round(cf.uroky_celkem_kc, 2),
            "umor_celkem_kc": round(cf.umor_celkem_kc, 2),
            "dluhova_sluzba_celkem_kc": round(cf.uroky_celkem_kc + cf.umor_celkem_kc, 2),
            "naklady_provozni_celkem_kc": round(cf.naklady_provozni_celkem_kc, 2),
            # Co nám klient zaplatí
            "prijmy_ppa_celkem_kc": round(cf.prijmy_ppa_celkem_kc, 2),
            "prijmy_najem_celkem_kc": round(cf.prijmy_najem_celkem_kc, 2),
            "prijmy_export_celkem_kc": round(cf.prijmy_export_celkem_kc, 2),
            "prijmy_odkup_celkem_kc": round(cf.prijmy_odkup_celkem_kc, 2),
            "prijmy_celkem_kc": round(
                cf.prijmy_ppa_celkem_kc
                + cf.prijmy_najem_celkem_kc
                + cf.prijmy_export_celkem_kc
                + cf.prijmy_odkup_celkem_kc,
                2,
            ),
            # Výsledek
            "zisk_po_splatkach_celkem_kc": round(
                sum(r.zisk_po_splatkach_kc for r in cf.roky), 2
            ),
            "zisk_greensie_hned_kc": round(cf.zisk_greensie_kc, 2),
            "provize_kc": round(cf.provize_kc, 2),
            "navratnost_vlastniho_kapitalu_roky": (
                round(cf.navratnost_vlastniho_kapitalu_roky, 2)
                if cf.navratnost_vlastniho_kapitalu_roky is not None
                else None
            ),
            "irr": round(cf.irr, 4) if cf.irr is not None else None,
            "npv_kc": round(cf.npv_kc, 2),
            "dscr_min": round(cf.dscr_min, 3) if cf.dscr_min is not None else None,
        },
        "roky_investor": [
            {
                "rok": r.rok,
                "vyroba_mwh": round(r.vyroba_mwh, 3),
                "samospotreba_mwh": round(r.samospotreba_mwh, 3),
                "cena_ppa_kc_mwh": round(r.cena_ppa_kc_mwh, 2),
                # Příjmy
                "prijem_ppa_kc": round(r.prijem_ppa_kc, 2),
                "prijem_najem_kc": round(r.najem_baterie_kc, 2),
                "prijem_export_kc": round(r.prijem_export_kc, 2),
                "prijem_odkup_kc": round(r.prijem_odkup_kc, 2),
                # Náklady
                "provozni_naklady_kc": round(r.provozni_naklady_kc, 2),
                "zdroje_kc": round(r.zdroje_kc, 2),
                # Dluhová služba rozepsaná
                "splatka_kc": round(r.splatka_kc, 2),
                "urok_kc": round(r.urok_kc, 2),
                "umor_kc": round(r.umor_kc, 2),
                "zustatek_uveru_kc": round(r.zustatek_uveru_kc, 2),
                "dscr": round(r.dscr, 3) if r.dscr is not None else None,
                "zisk_po_splatkach_kc": round(r.zisk_po_splatkach_kc, 2),
                "kumulovany_cf_kc": round(r.kumulovany_cf_kc, 2),
            }
            for r in cf.roky
        ],
        "roky": [
            {
                "rok": r.rok,
                "vyroba_mwh": round(r.vyroba_mwh, 3),
                "samospotreba_mwh": round(r.samospotreba_mwh, 3),
                "cena_ppa_kc_mwh": round(r.cena_ppa_kc_mwh, 2),
                "uspora_energie_kc": round(r.uspora_energie_kc, 2),
                "uspora_vykon_kc": round(r.uspora_vykon_kc, 2),
                "najem_baterie_kc": round(r.naklad_najmu_kc, 2),
                "naklad_ztrat_kc": round(r.naklad_ztrat_kc, 2),
                "naklad_provozu_zakaznika_kc": round(r.naklad_provozu_zakaznika_kc, 2),
                "vydaj_odkup_kc": round(r.vydaj_odkup_kc, 2),
                "cisty_prinos_kc": round(r.cisty_prinos_zakaznika_kc, 2),
                "dscr": round(r.dscr, 3) if r.dscr is not None else None,
            }
            for r in cf.roky
        ],
    }


def spocti_ppa_bess(vstup: VstupPpaBess) -> dict:
    """Hlavní vstupní bod – navrhne elektrárnu, baterii a rozpadne přínos.

    Postup:

    1. velikost elektrárny z cíle samospotřeby (a vedle toho, kde by bylo
       ekonomické optimum, ať je vidět, jestli se nechávají peníze na stole),
    2. baterie – ruční zadání, nebo návrh z katalogu,
    3. **jeden dispatch pro každý ze tří režimů** (kombinace / jen špičky / jen
       samospotřeba), aby bylo vidět, co kombinace přinesla navíc,
    4. ekonomika výkonu ve dvou scénářích (s snížením RP i bez),
    5. ekonomika PPA pro každou nabízenou délku kontraktu – dispatch se
       nepočítá znovu, protože na délce kontraktu nezávisí.

    Délku kontraktu výpočet **nedoporučuje**, vrací všechny a vybírá obchodník
    (stejné rozhodnutí jako u PPA v2).
    """
    from .ppa_fve import simuluj_vyrobu
    from .ppa_v2 import (
        ParametryEkonomiky,
        VYCHOZI_MIN_SLEVA,
        navrhni_baterii,
        navrhni_kwp_na_cil,
        odkupni_tabulka_json,
        sestav_projekt,
        vyber_baterii_z_katalogu,
    )

    if vstup.hladina not in ("VN", "VVN"):
        return {
            "chyba": (
                "PPA+BESS zatím počítáme jen na VN a VVN – na NN není nakalibrovaná "
                "ani výroba, ani tarifní struktura."
            )
        }
    if not vstup.casy or not vstup.spotreba_kwh:
        return {"chyba": "Chybí 15minutový odběrový diagram."}
    if vstup.cena_silova_kc_mwh <= 0:
        return {"chyba": "Chybí silová složka ceny, kterou zákazník platí dnes."}
    if vstup.rezervovana_kapacita_kw <= 0:
        return {"chyba": "Chybí rezervovaná kapacita – bez ní se nedá ocenit srážení špiček."}

    p = vstup.parametry or ParametryEkonomiky()
    pb = vstup.parametry_bess or ParametryPpaBess()
    if vstup.cena_exportu_kc_mwh is not None:
        from dataclasses import replace as _replace

        p = _replace(p, cena_exportu_kc_mwh=max(0.0, vstup.cena_exportu_kc_mwh))

    interval_h = vstup.interval_h or _odvod_interval_h(vstup.casy)
    mesice = [c.month for c in vstup.casy]
    upozorneni: list[str] = []

    sazby = vstup.parametry_2027 or {}
    ma_sazby = bool(sazby) and all(sazby.get(k) is not None for k in peak_shaving.KLICE_2027)
    if not ma_sazby:
        upozorneni.append(
            "Sazby NTS 2027 pro tuhle hladinu a distributora nejsou v sazebníku, takže "
            "**srážení špiček se nedá ocenit**. Elektrárna a samospotřeba jsou spočítané, "
            "ale přínos na kilowattech chybí a baterie se volí jen podle energie."
        )
    if vstup.rezervovany_prikon_kw is None or vstup.rezervovany_prikon_kw <= 0:
        upozorneni.append(
            "Rezervovaný příkon ze smlouvy o připojení není zadaný, takže se místo něj "
            "použila rezervovaná kapacita. RP je typicky vyšší – přínos baterie na "
            "kapacitní složce tím může být podhodnocený."
        )

    # --- 1) elektrárna
    # Dvě cesty, které se vylučují:
    #  a) obchodník zná rozpad na pole → velikost je daná, jen se sečte výroba,
    #  b) rozpad nezná → velikost se navrhne z cíle samospotřeby nad jednou
    #     orientací (`sklon_st` / `azimut_st`).
    # Zadání se zachová kvůli předvyplnění formuláře (jedno pole „východ-západ"
    # se má vrátit jako jedno se zaškrtnutím, ne jako dvě). Výpočet ale pracuje
    # s rozloženými poli, aby o téhle zkratce nemusel nic vědět.
    pole_zadani = tuple(x for x in (vstup.pole or ()) if x.kwp and x.kwp > 0)
    pole = rozloz_pole(pole_zadani)
    zadana_pole = bool(pole)
    upozorneni.extend(zkontroluj_osu_rozdeleni(pole_zadani))

    if zadana_pole:
        vyroba_kwh = [0.0] * len(vstup.casy)
        for f in pole:
            dil = simuluj_vyrobu(
                vstup.casy,
                f.kwp,
                vstup.lat_deg,
                f.sklon_st,
                f.azimut_st,
                vstup.merny_vynos_kwh_kwp,
            )
            for i, x in enumerate(dil):
                vyroba_kwh[i] += x
        kwp = sum(f.kwp for f in pole)
        kwp_bez = kwp
        kwp_bez_stropu = kwp
        omezeno_stropem = False
        # Pro heuristický návrh baterie je potřeba výroba na 1 kWp ve stejném
        # tvaru, jaký mají zadaná pole – jinak by se baterie navrhla podle jihu,
        # i když je střecha východ-západ.
        vyroba_1kwp = [x / kwp for x in vyroba_kwh] if kwp > 0 else vyroba_kwh
        if vstup.max_kwp and kwp > vstup.max_kwp + 1e-9:
            upozorneni.append(
                f"Součet polí je {kwp:.0f} kWp, ale strop velikosti je "
                f"{vstup.max_kwp:.0f} kWp. Výpočet jede podle zadaných polí – strop se "
                "u ručního rozpadu neuplatňuje, protože velikost je tvoje rozhodnutí."
            )
    else:
        vyroba_1kwp = simuluj_vyrobu(
            vstup.casy,
            1.0,
            vstup.lat_deg,
            vstup.sklon_st,
            vstup.azimut_st,
            vstup.merny_vynos_kwh_kwp,
        )
        kwp_bez = navrhni_kwp_na_cil(
            vyroba_1kwp,
            vstup.spotreba_kwh,
            vstup.cil_mira_samospotreby,
            None,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
            vstup.max_kwp,
        )
        if kwp_bez <= 0:
            return {"chyba": "Z profilu nevychází žádná smysluplná velikost elektrárny."}

    # --- 2) baterie
    baterie = vstup.baterie
    if baterie is None:
        navrh = navrhni_baterii(
            [kwp_bez * v for v in vyroba_1kwp], vstup.spotreba_kwh, vstup.casy
        )
        baterie = navrh
        cil = navrh.vyuzitelna_kapacita_kwh
        if cil > 0 and vstup.baterie_katalog:
            z_katalogu = vyber_baterii_z_katalogu(vstup.baterie_katalog, cil, navrh.vykon_kw)
            if z_katalogu is not None:
                baterie = z_katalogu
                if z_katalogu.cena_je_doporucena:
                    upozorneni.append(
                        f"U baterie {z_katalogu.produkt_nazev} ceník neuvádí dealerskou cenu, "
                        "takže nákladová cena vychází z doporučené prodejní – nájem tím "
                        "vychází vyšší, než jaký by šlo nabídnout. Doplň nákupní cenu do "
                        "katalogu, nebo baterii zadej ručně."
                    )
            else:
                upozorneni.append(
                    "V katalogu není použitelná baterie (potřebuje výkon, kapacitu i cenu), "
                    "takže se navrhla jen velikost bez ceny – zadej baterii ručně."
                )
        elif cil > 0:
            upozorneni.append(
                "Katalog baterií je prázdný, takže se navrhla jen velikost bez ceny. "
                "Bez nákladové ceny se nájem ani ekonomika spočítat nedají."
            )

    if baterie is not None and baterie.kapacita_kwh > 0 and baterie.nakladova_cena_kc <= 0:
        if vstup.najem_kc_mesic_rucne is None:
            upozorneni.append(
                "Nákladová cena baterie není zadaná a nájem taky ne – varianta počítá "
                "s baterií zdarma, takže čísla nejsou platná. Zadej cenu nebo nájem."
            )

    # --- elektrárna znovu, teď s baterií (baterie zvedá samospotřebu, takže
    # při stejném cíli vyjde větší elektrárna). U zadaných polí se nic
    # nepřepočítává – velikost i tvar výroby jsou dané.
    if not zadana_pole:
        kwp = navrhni_kwp_na_cil(
            vyroba_1kwp,
            vstup.spotreba_kwh,
            vstup.cil_mira_samospotreby,
            baterie,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
            vstup.max_kwp,
        )
        if kwp <= 0:
            kwp = kwp_bez
        kwp_bez_stropu = navrhni_kwp_na_cil(
            vyroba_1kwp,
            vstup.spotreba_kwh,
            vstup.cil_mira_samospotreby,
            baterie,
            vstup.rezervovany_vykon_dodavky_kw,
            interval_h,
            None,
        )
        omezeno_stropem = bool(vstup.max_kwp and kwp < kwp_bez_stropu - 1e-9)
        if omezeno_stropem:
            upozorneni.append(
                f"Velikost elektrárny drží strop {vstup.max_kwp:.0f} kWp – bez něj by na cíl "
                f"samospotřeby vyšlo {kwp_bez_stropu:.0f} kWp a elektrárna by pokryla větší "
                "část spotřeby."
            )
        vyroba_kwh = [kwp * v for v in vyroba_1kwp]

    # --- 3) tři režimy nad jednou baterií a jednou elektrárnou
    # Hodnota kWh pro volbu stropu: cena PPA se teprve dopočítá (inverzní úloha),
    # takže se použije **minimální zaručená sleva**. Konzervativní záměrně –
    # model tím radši strop nepustí výš, než by ekonomika dovolila.
    cena_zakaznika = vstup.cena_silova_kc_mwh + vstup.vyhnutelne_regulovane_kc_mwh
    hodnota_kwh = cena_zakaznika * VYCHOZI_MIN_SLEVA

    rezimy: dict[str, VysledekRezimu] = {}
    roky_sim: dict[str, VysledekRoku] = {}
    for rezim in REZIMY:
        vr, rok = spocti_rezim(
            vstup, vyroba_kwh, mesice, baterie, rezim, interval_h, hodnota_kwh, pb
        )
        rezimy[rezim] = vr
        roky_sim[rezim] = rok


    # --- 4) financování: elektrárna na délku kontraktu, baterie na dobu nájmu
    ma_baterii = baterie is not None and baterie.kapacita_kwh > 0
    nakladova_bess = baterie.nakladova_cena_kc if ma_baterii else 0.0
    doba_najmu = max(1, int(vstup.doba_najmu_baterie_roky))
    projekt_bess = sestav_projekt_bess(nakladova_bess, p, doba_najmu)
    najem_z_ceny = najem_baterie_kc_mesic(projekt_bess, p)
    najem_mesicni = (
        vstup.najem_kc_mesic_rucne
        if vstup.najem_kc_mesic_rucne is not None
        else najem_z_ceny
    )
    # Zbytková hodnota a o kolik by zvedla nájem, kdyby se místo doplatku
    # rozpustila do měsíčních plateb (varianta „odkup za korunu").
    odkupni_cena = odkupni_cena_baterie_kc(projekt_bess, pb) if ma_baterii else 0.0
    navyseni_1kc = (
        navyseni_najmu_za_odkup_kc_mesic(odkupni_cena, doba_najmu)
        if ma_baterii
        else 0.0
    )
    if vstup.najem_kc_mesic_rucne is not None and najem_z_ceny > 0:
        rozdil = vstup.najem_kc_mesic_rucne - najem_z_ceny
        if abs(rozdil) > 1.0:
            smer = "pod" if rozdil < 0 else "nad"
            upozorneni.append(
                f"Sjednaný nájem {_kc(vstup.najem_kc_mesic_rucne)} Kč/měsíc je "
                f"{_kc(abs(rozdil))} Kč {smer} tím, co vychází z ceny baterie "
                f"({_kc(najem_z_ceny)} Kč/měsíc). Ekonomika investora se tím posouvá – "
                "hlídej DSCR a IRR u jednotlivých délek."
            )
    najem_rocni = najem_mesicni * 12.0

    # --- 5) ekonomika pro každou nabízenou délku, a to pro KAŽDÝ režim
    # Ekonomika je proti dispatchi levná (bisekce nad cashflow), takže se počítá
    # pro všechny tři režimy. Jinak by se doporučení nedalo poctivě udělat:
    # volba měsíčního stropu v kombinovaném režimu se rozhoduje podle *odhadu*
    # hodnoty kWh (cena PPA se dopočítá až potom), a když se odhad rozejde
    # s realitou, může kombinace vyjít horší než čisté srážení špiček. Místo aby
    # se to zametlo, spočítá se ekonomika všem třem a doporučí se ten, který
    # zákazníkovi skutečně vydělá nejvíc.
    delky = sorted({int(n) for n in vstup.nabizene_delky_roky if int(n) > 0})
    vyroba_mwh = sum(vyroba_kwh) / 1000.0

    def ekonomika_rezimu(vr: VysledekRezimu) -> list[dict]:
        out: list[dict] = []
        samospotreba_mwh = vr.samospotreba_kwh / 1000.0
        export_mwh = vr.export_kwh / 1000.0
        uspora_vykon = vr.uspora_vykon_bez_snizeni_rp_kc
        for n in delky:
            projekt_fve = sestav_projekt(
                nakladova_cena_fve(kwp, pole, p), p.marze_fve, p.provize_fve, n, p
            )
            # Argumenty, které jsou pro obě varianty odkupu stejné – ať se při
            # úpravě jedné cesty tiše nerozejde druhá.
            spolecne = (
                vyroba_mwh,
                samospotreba_mwh,
                export_mwh,
                uspora_vykon,
                vr.ztraty_ze_site_kwh,
            )
            minc = minimalni_cena_ppa(
                *spolecne,
                cena_zakaznika,
                projekt_fve,
                projekt_bess,
                p,
                pb,
                n,
                doba_najmu_roky=doba_najmu,
                najem_kc_mesic=najem_mesicni,
            )
            cf = spocti_cashflow(
                *spolecne,
                minc.cena_kc_mwh,
                cena_zakaznika,
                projekt_fve,
                projekt_bess,
                p,
                pb,
                n,
                doba_najmu_roky=doba_najmu,
                najem_kc_mesic=najem_mesicni,
            )
            # Varianta „odkup za korunu" se počítá celá znovu: rozpuštěný odkup
            # zvedne provozní příjem SPV, zlepší DSCR, a cena PPA proto může
            # vyjít nižší. Dopočítat ji nad hotovým cashflow nejde.
            #
            # Počítá se u KAŽDÉ délky, kde je baterie v nájmu – obchodník obě
            # varianty srovnává i u kontraktu stejně dlouhého jako nájem, což je
            # nejčastější případ.
            varianta_1kc = None
            if ma_baterii and navyseni_1kc > 0:
                najem_1kc = najem_mesicni + navyseni_1kc
                minc_1kc = minimalni_cena_ppa(
                    *spolecne,
                    cena_zakaznika,
                    projekt_fve,
                    projekt_bess,
                    p,
                    pb,
                    n,
                    doba_najmu_roky=doba_najmu,
                    najem_kc_mesic=najem_mesicni,
                    odkup_symbolicky=True,
                )
                cf_1kc = spocti_cashflow(
                    *spolecne,
                    minc_1kc.cena_kc_mwh,
                    cena_zakaznika,
                    projekt_fve,
                    projekt_bess,
                    p,
                    pb,
                    n,
                    doba_najmu_roky=doba_najmu,
                    najem_kc_mesic=najem_mesicni,
                    odkup_symbolicky=True,
                )
                varianta_1kc = _varianta_1kc_json(
                    minc_1kc,
                    cf_1kc,
                    cena_zakaznika,
                    najem_1kc,
                    navyseni_1kc,
                    odkupni_cena,
                    doba_najmu_roky=doba_najmu,
                    delka_roky=n,
                )
            out.append(
                _delka_json(
                    minc,
                    cf,
                    n,
                    cena_zakaznika,
                    najem_mesicni,
                    doba_najmu_roky=doba_najmu,
                    odkup_1kc=varianta_1kc,
                    # Odkup elektrárny po letech – z projektu elektrárny, ne
                    # z celého CAPEXu: baterie se odkupuje až po nájmu a jinou
                    # metodikou (zbytková hodnota, ne zbytek úvěru).
                    odkupni_tabulka=odkupni_tabulka_json(projekt_fve, p),
                )
            )
        return out

    ekonomiky = {r: ekonomika_rezimu(rezimy[r]) for r in REZIMY}

    # Doporučený režim: nejvyšší čistý přínos zákazníka v roce 1 u **nejkratšího**
    # kontraktu (nejdražší cena PPA, tedy nejkonzervativnější srovnání).
    def prinos_rok1(rezim: str) -> float:
        radky = ekonomiky[rezim]
        return radky[0]["uspora_rok1_kc"] if radky else float("-inf")

    doporuceny = max(REZIMY, key=prinos_rok1)
    hlavni = rezimy[doporuceny]
    sim_hlavni = roky_sim[doporuceny]
    po_delkach = ekonomiky[doporuceny]
    uspora_vykon = hlavni.uspora_vykon_bez_snizeni_rp_kc

    for d in po_delkach:
        if d["limitujici"] == "nedosazitelne":
            upozorneni.append(
                f'U kontraktu na {d["delka_roky"]} let neprojde projekt bankou ani při vysoké '
                "ceně PPA – elektrárna s baterií je na tenhle profil moc drahá, nebo je nájem "
                "baterie nastavený pod ekonomikou."
            )
    if doporuceny != REZIM_KOMBINACE:
        upozorneni.append(
            f"Nejlepší je režim **{REZIM_NAZVY[doporuceny].lower()}** – kombinace obou rolí "
            "u tohohle profilu nevydělá víc. Rozpad přínosu u všech tří režimů je v panelu, "
            "takže je vidět, o kolik jde."
        )

    # --- kontroly, které si obchodník musí přečíst, i když čísla „vyšla"
    if ma_baterii and delky and doba_najmu > delky[0]:
        # Nájem delší než kontrakt = po skončení kontraktu zůstane nesplacený
        # úvěr na baterii a k odkupu nedojde. Model to spočítá (nájem se prostě
        # přestane platit s kontraktem), ale sám o sobě je to obchodní problém.
        upozorneni.append(
            f"Nájem baterie je na {doba_najmu} let, ale nabízíš i kontrakt na "
            f"{delky[0]} let. U kratších kontraktů se baterie nesplatí – po jejich "
            "skončení zůstane zůstatek úvěru a k odkupu nedojde. Buď zkrať nájem, "
            "nebo z nabídky vynech krátké délky."
        )
    if ma_baterii and po_delkach:
        # Vyplatí se baterie vůbec? Nájem může přínos přerůst – typicky když
        # návrh z katalogu přestřelí velikost. Model to nezamlčí.
        nejlepsi_delka = max(po_delkach, key=lambda d: d["uspora_rok1_kc"])
        cena_nejlepsi = nejlepsi_delka.get("cena_ppa_kc_mwh")
        prinos_nejlepsi = hlavni.uspora_vykon_bez_snizeni_rp_kc
        if cena_nejlepsi is not None:
            prinos_nejlepsi += (
                hlavni.samospotreba_kwh
                / 1000.0
                * max(0.0, cena_zakaznika - cena_nejlepsi)
            )
        if prinos_nejlepsi < najem_rocni:
            upozorneni.append(
                f"**Baterie se v této velikosti nevyplatí:** přinese "
                f"{_kc(prinos_nejlepsi)} Kč/rok, ale nájem je {_kc(najem_rocni)} Kč/rok. "
                "Zkus menší baterii, nebo ji z nabídky vynech – elektrárna sama může "
                "vyjít lépe."
            )
        # Cykly: kolem 300+ ročně je baterie hnaná dost tvrdě a záruka bývá
        # vázaná na počet cyklů. Peak shaving to reguluje nákladem opotřebení,
        # tady na to zatím upozorňujeme.
        if hlavni.cyklu > 300:
            upozorneni.append(
                f"Dispatch baterii protočí {hlavni.cyklu:.0f}× za rok. Zkontroluj, co "
                "dovoluje záruka – model počet cyklů nijak neomezuje a degradaci počítá "
                f"jen paušálně ({pb.degradace_prinosu_baterie * 100:.1f} % přínosu za rok)."
            )

    # --- ekonomické optimum velikosti (informativně vedle cíle samospotřeby).
    # U ručně zadaných polí se nepočítá: velikost i orientace jsou rozhodnutí
    # obchodníka, ne něco, co by měl model přehazovat.
    optimum = (
        {}
        if zadana_pole
        else _optimum_velikosti(
            vstup, vyroba_1kwp, baterie, mesice, interval_h, p, pb, cena_zakaznika, kwp
        )
    )

    return {
        "typ_reseni": "ppa_bess",
        "verze": 1,
        "vstup": {
            "hladina": vstup.hladina,
            "cena_silova_kc_mwh": vstup.cena_silova_kc_mwh,
            "vyhnutelne_regulovane_kc_mwh": vstup.vyhnutelne_regulovane_kc_mwh,
            "cena_zakaznika_kc_mwh": round(cena_zakaznika, 2),
            "rezervovana_kapacita_kw": vstup.rezervovana_kapacita_kw,
            "rezervovany_prikon_kw": vstup.rezervovany_prikon_kw,
            "cil_mira_samospotreby": vstup.cil_mira_samospotreby,
            "max_kwp": vstup.max_kwp,
            "sklon_st": vstup.sklon_st,
            "azimut_st": vstup.azimut_st,
            "rezervovany_vykon_dodavky_kw": vstup.rezervovany_vykon_dodavky_kw,
            "cena_exportu_kc_mwh": p.cena_exportu_kc_mwh,
            "rezerva_rk_procenta": vstup.rezerva_rk_procenta,
            "poctu_intervalu": len(vstup.spotreba_kwh),
            "interval_h": interval_h,
            "najem_kc_mesic_rucne": vstup.najem_kc_mesic_rucne,
            "baterie_rucne": vstup.baterie is not None,
        },
        "elektrarna": {
            "kwp": kwp,
            "kwp_bez_baterie": kwp_bez,
            "kwp_bez_stropu": kwp_bez_stropu,
            "omezeno_max_kwp": omezeno_stropem,
            "vyroba_mwh": round(vyroba_mwh, 3),
            "optimum": optimum,
            # Rozpad na pole, když ho obchodník zadal. `vyroba_mwh` per pole se
            # dopočítá zvlášť, aby bylo vidět, kolik která orientace přinese.
            "velikost_zadana_rucne": zadana_pole,
            # Nákladová cena elektrárny – s uplatněnými přepisy ceny za kWp
            # u jednotlivých polí. Bez rozpadu je to `kwp × cena z nastavení`.
            "nakladova_cena_kc": round(nakladova_cena_fve(kwp, pole, p), 2),
            "nakladova_cena_kc_kwp_nastaveni": round(p.nakladova_cena_kc_kwp, 2),
            # Původní zadání – panel z něj předvyplňuje formulář, takže pole
            # označené jako východ-západ se vrátí jako jedno se zaškrtnutím.
            "pole_zadani": [
                {
                    "kwp": f.kwp,
                    "sklon_st": f.sklon_st,
                    "azimut_st": f.azimut_st,
                    "cena_kc_kwp": (
                        round(f.cena_kc_kwp, 2) if f.cena_kc_kwp and f.cena_kc_kwp > 0 else None
                    ),
                    "rozdelit_vychod_zapad": f.rozdelit_vychod_zapad,
                }
                for f in pole_zadani
            ],
            "pole": [
                {
                    "kwp": f.kwp,
                    "sklon_st": f.sklon_st,
                    "azimut_st": f.azimut_st,
                    "orientace": _nazev_orientace(f.azimut_st),
                    # Cena za kWp, se kterou se u tohohle pole opravdu počítalo,
                    # a příznak, jestli je z nastavení nebo přepsaná ručně.
                    "cena_kc_kwp": round(
                        f.cena_kc_kwp
                        if f.cena_kc_kwp and f.cena_kc_kwp > 0
                        else p.nakladova_cena_kc_kwp,
                        2,
                    ),
                    "cena_prepsana": bool(f.cena_kc_kwp and f.cena_kc_kwp > 0),
                    # Vzniklo tohle pole rozdělením V/Z? Bez příznaku vypadá
                    # výsledek se čtyřmi poli proti třem zadaným jako chyba.
                    "z_rozdeleni_vz": f.z_rozdeleni_vz,
                    "nakladova_cena_kc": round(
                        f.kwp
                        * (
                            f.cena_kc_kwp
                            if f.cena_kc_kwp and f.cena_kc_kwp > 0
                            else p.nakladova_cena_kc_kwp
                        ),
                        2,
                    ),
                    "vyroba_mwh": round(
                        sum(
                            simuluj_vyrobu(
                                vstup.casy,
                                f.kwp,
                                vstup.lat_deg,
                                f.sklon_st,
                                f.azimut_st,
                                vstup.merny_vynos_kwh_kwp,
                            )
                        )
                        / 1000.0,
                        3,
                    ),
                }
                for f in pole
            ],
        },
        "baterie": (
            {
                "produkt_id": baterie.produkt_id,
                "nazev": baterie.produkt_nazev,
                "pocet_kusu": baterie.pocet_kusu,
                "z_katalogu": baterie.produkt_id is not None,
                "zadana_rucne": vstup.baterie is not None,
                "kapacita_kwh": round(baterie.kapacita_kwh, 1),
                "vyuzitelna_kapacita_kwh": round(baterie.vyuzitelna_kapacita_kwh, 1),
                "vykon_kw": round(baterie.vykon_kw, 1),
                "dod": round(baterie.dod, 4),
                "ucinnost_round_trip": round(baterie.ucinnost_round_trip, 4),
                "nakladova_cena_kc": round(nakladova_bess, 2),
                "capex_kc": round(projekt_bess.capex_kc, 2),
                "najem_kc_mesic": round(najem_mesicni, 2),
                "najem_z_ceny_kc_mesic": round(najem_z_ceny, 2),
                "najem_zadan_rucne": vstup.najem_kc_mesic_rucne is not None,
                "doba_najmu_roky": doba_najmu,
                # Varianta „odkup za korunu": nájem navýšený o rozpuštěnou
                # zbytkovou hodnotu. Ekonomika téhle varianty je po délkách
                # v `po_delkach[].odkup_1kc` – tady je jen samo číslo nájmu,
                # protože nezávisí na délce kontraktu.
                "odkupni_cena_kc": round(odkupni_cena, 2),
                "najem_odkup_1kc_kc_mesic": round(najem_mesicni + navyseni_1kc, 2),
                "navyseni_najmu_za_odkup_kc_mesic": round(navyseni_1kc, 2),
                "cena_je_doporucena": baterie.cena_je_doporucena,
            }
            if ma_baterii
            else None
        ),
        # Doporučený režim je kombinace, ale panel ukáže všechny tři, aby bylo
        # vidět, kolik kombinace přinesla nad rámec každé jednotlivé role.
        # Všechny tři režimy vedle sebe, každý s vlastní ekonomikou po délkách –
        # panel z toho staví srovnání „kolik by baterie vydělala jen na špičkách,
        # jen na samospotřebě, a v kombinaci".
        "rezimy": [
            {
                **_rezim_json(
                    rezimy[r],
                    _prinos_energie_kc(rezimy[r], ekonomiky[r], cena_zakaznika),
                    najem_rocni,
                    {
                        d["delka_roky"]: rezimy[r].samospotreba_kwh
                        / 1000.0
                        * max(0.0, cena_zakaznika - d["cena_ppa_kc_mwh"])
                        for d in ekonomiky[r]
                        if d.get("cena_ppa_kc_mwh") is not None
                    },
                ),
                "po_delkach": ekonomiky[r],
                "doporuceny": r == doporuceny,
            }
            for r in REZIMY
        ],
        "doporuceny_rezim": doporuceny,
        "po_delkach": po_delkach,
        "sazby_2027_k_dispozici": ma_sazby,
        "sazby_2027_modelovy_odhad": vstup.je_modelovy_odhad_2027,
        "upozorneni": upozorneni,
    }


def _prinos_energie_kc(
    v: VysledekRezimu, po_delkach: list[dict], cena_zakaznika_kc_mwh: float
) -> float:
    """Roční přínos z energie v roce 1 pro daný režim.

    Cena PPA se bere z **nejkratší** nabízené délky, protože ta je nejdražší –
    srovnání režimů tak nikdy nevypadá lepší, než jaké nejhorší nabídka bude.
    Když žádná délka neprojde (cena je `None`), spadne to na minimální slevu –
    jinak by srovnání režimů zmizelo úplně a nebylo by vidět ani to, který režim
    je relativně nejlepší.
    """
    from .ppa_v2 import VYCHOZI_MIN_SLEVA

    # `max`, ne `min`: nejvyšší cena PPA = nejmenší sleva = nejmenší přínos.
    # Nejkratší kontrakt je nejdražší, takže srovnání režimů stojí na tom, co
    # zákazník dostane v nejhorším případě.
    ceny = [d["cena_ppa_kc_mwh"] for d in po_delkach if d.get("cena_ppa_kc_mwh") is not None]
    cena_ppa = max(ceny) if ceny else cena_zakaznika_kc_mwh * (1.0 - VYCHOZI_MIN_SLEVA)
    return v.samospotreba_kwh / 1000.0 * max(0.0, cena_zakaznika_kc_mwh - cena_ppa)


def _optimum_velikosti(
    vstup: VstupPpaBess,
    vyroba_1kwp: list[float],
    baterie: Baterie | None,
    mesice: list[int],
    interval_h: float,
    p,
    pb: ParametryPpaBess,
    cena_zakaznika_kc_mwh: float,
    kwp_z_cile: float,
) -> dict:
    """Kde by byla velikost elektrárny s nejvyšším čistým přínosem zákazníka.

    Informativně vedle návrhu z cíle samospotřeby (rozhodnuto s Danem 5. 8.
    2026): obchodník tak vidí, jestli se cílem 80 % nenechávají peníze na stole.
    Hrubý sken – dispatch je drahý, takže se zkouší jen pár velikostí a bez
    ekonomické volby stropů (režim `spicky` je pro tenhle účel dost blízko).
    """
    from .ppa_v2 import VYCHOZI_MIN_SLEVA

    strop = vstup.max_kwp or (kwp_z_cile * 2.0)
    if strop <= 0:
        return {}
    kandidati = sorted(
        {
            round(max(1.0, strop * podil))
            for podil in (0.25, 0.5, 0.75, 1.0)
        }
    )
    hodnota_kwh = cena_zakaznika_kc_mwh * VYCHOZI_MIN_SLEVA
    nejlepsi: dict = {}
    body: list[dict] = []
    for kwp in kandidati:
        vyroba = [kwp * v for v in vyroba_1kwp]
        vr, _ = spocti_rezim(
            vstup, vyroba, mesice, baterie, REZIM_SPICKY, interval_h, hodnota_kwh, pb
        )
        # Hrubý odhad přínosu: energie za minimální slevu + výkon. Nezahrnuje
        # cenu PPA z DSCR – to by znamenalo celou ekonomiku pro každou velikost.
        prinos = (
            vr.samospotreba_kwh / 1000.0 * hodnota_kwh + vr.uspora_vykon_bez_snizeni_rp_kc
        )
        bod = {
            "kwp": kwp,
            "prinos_odhad_kc": round(prinos, 2),
            "mira_samospotreby": round(vr.mira_samospotreby, 4),
        }
        body.append(bod)
        if not nejlepsi or prinos > nejlepsi["prinos_odhad_kc"]:
            nejlepsi = bod
    return {
        "kwp": nejlepsi.get("kwp"),
        "prinos_odhad_kc": nejlepsi.get("prinos_odhad_kc"),
        "body": body,
        "poznamka": (
            "Hrubý odhad: energie oceněná minimální slevou 10 % plus přínos na výkonu, "
            "bez dopočtu ceny PPA z DSCR. Slouží k porovnání velikostí, ne jako nabídka."
        ),
    }


def _odvod_interval_h(casy: list[datetime]) -> float:
    """Délka intervalu z prvních dvou časových značek profilu."""
    if len(casy) >= 2:
        delta = (casy[1] - casy[0]).total_seconds() / 3600.0
        if delta > 0:
            return delta
    return peak_shaving.VYCHOZI_INTERVAL_H


def prubeh_15min(
    odber_kwh: list[float],
    vyroba_kwh: list[float],
    mesice: list[int],
    baterie: Baterie | None,
    stropy_po_mesicich: dict[int, float],
    interval_h: float,
    rezervovany_vykon_dodavky_kw: float | None = None,
    rezim: str = REZIM_KOMBINACE,
) -> dict:
    """15min řady pro nitkový graf – ve **kW**, jako u PPA a peak shavingu.

    Neukládá se do řešení (~35 tis. hodnot na řadu), počítá se na vyžádání.
    Stropy se předávají z uloženého výsledku, aby graf ukazoval **tentýž**
    dispatch, ze kterého vyšla ekonomika – ne nový, spočítaný jinak.

    Vrací klíče, které umí `GrafPrubehuPpa` (`spotreba_kw`, `vyroba_kw`,
    `samospotreba_kw`, `pretok_kw`, `orez_kw`, `soc_pct`), a k nim tři navíc,
    které jsou pro tenhle modul podstatné: kolik baterie vydala na špičky, kolik
    na solární posun a kde byl strop.
    """
    delitel = interval_h if interval_h > 0 else peak_shaving.VYCHOZI_INTERVAL_H
    solar = rezim != REZIM_SPICKY
    ma_baterii = (
        baterie is not None
        and baterie.vyuzitelna_kapacita_kwh > 0
        and baterie.vykon_kw > 0
    )

    indexy: dict[int, list[int]] = {}
    for i, m in enumerate(mesice):
        indexy.setdefault(m, []).append(i)

    # Řady se plní po měsících, ale ukládají se na původní pozice – profil
    # nemusí mít měsíce v souvislých blocích.
    n = len(odber_kwh)
    rada = lambda: [0.0] * n  # noqa: E731 – krátká lokální pomůcka
    site_kw, odber_kw, vyroba_kw = rada(), rada(), rada()
    ps_kw, solar_kw, soc_pct, stropy = rada(), rada(), rada(), rada()

    for m, idx in sorted(indexy.items()):
        strop = float(stropy_po_mesicich.get(m, stropy_po_mesicich.get(str(m), 0.0)) or 0.0)
        odber_m = [odber_kwh[i] for i in idx]
        vyroba_m = [vyroba_kwh[i] if i < len(vyroba_kwh) else 0.0 for i in idx]
        trajektorie = None
        pocatecni = None
        if ma_baterii:
            site_bez = [
                max(0.0, odber_m[k] - vyroba_m[k]) / interval_h for k in range(len(odber_m))
            ]
            trajektorie = minimalni_soc_trajektorie(
                site_bez,
                strop,
                baterie.vykon_kw,
                baterie.vyuzitelna_kapacita_kwh,
                interval_h,
                baterie.ucinnost_round_trip,
            )
            pocatecni = baterie.vyuzitelna_kapacita_kwh
        v = simuluj_usek(
            odber_m,
            vyroba_m,
            strop,
            baterie,
            interval_h,
            rezervovany_vykon_dodavky_kw,
            pocatecni_soc_kwh=pocatecni,
            soc_minimum=trajektorie,
            povolit_solarni_posun=solar,
            zapisuj=True,
        )
        pr = v.prubeh or _prazdny_prubeh()
        for k, i in enumerate(idx):
            site_kw[i] = pr["site_kw"][k] if k < len(pr["site_kw"]) else 0.0
            odber_kw[i] = pr["odber_kw"][k] if k < len(pr["odber_kw"]) else 0.0
            vyroba_kw[i] = pr["vyroba_kw"][k] if k < len(pr["vyroba_kw"]) else 0.0
            ps_kw[i] = pr["baterie_ps_kw"][k] if k < len(pr["baterie_ps_kw"]) else 0.0
            solar_kw[i] = pr["baterie_solar_kw"][k] if k < len(pr["baterie_solar_kw"]) else 0.0
            soc_pct[i] = pr["soc_pct"][k] if k < len(pr["soc_pct"]) else 0.0
            stropy[i] = strop

    # Samospotřeba = co z odběru nepřišlo ze sítě. Přetok se dopočítá z výroby,
    # která se nikam nevešla; ořez odsud nejde rozlišit, takže je vždy 0 a
    # skutečné oříznutí drží roční souhrn.
    samospotreba_kw = [max(0.0, odber_kw[i] - site_kw[i]) for i in range(n)]
    pretok_kw = [
        max(0.0, vyroba_kw[i] - samospotreba_kw[i] + min(0.0, solar_kw[i])) for i in range(n)
    ]

    # Celkový výkon baterie: kladné vybíjí, záporné nabíjí. Stejná konvence jako
    # `peak_shaving.prubeh_baterie`, aby detailní graf nemusel rozlišovat zdroj.
    baterie_kw = [ps_kw[i] + solar_kw[i] for i in range(n)]
    nabito = sum(-x for x in baterie_kw if x < 0) * interval_h
    vybito = sum(x for x in baterie_kw if x > 0) * interval_h

    return {
        "pocet": n,
        "interval_min": int(round(interval_h * 60)),
        # --- řady pro jednodušší graf z PPA (GrafVyrobaSpotreba/GrafPrubehuPpa)
        "spotreba_kw": [round(x, 2) for x in odber_kw],
        "vyroba_kw": [round(x, 2) for x in vyroba_kw],
        "samospotreba_kw": [round(x, 2) for x in samospotreba_kw],
        "pretok_kw": [round(x, 2) for x in pretok_kw],
        "orez_kw": [0.0] * n,
        # --- řady pro DETAILNÍ graf z peak shavingu (GrafPrubehu): pás baterie,
        # SOC, čára stropu a přehledový pásek. U tohohle modulu je detailní graf
        # ten podstatný — je na něm vidět, jak baterie drží strop a jak se přes
        # den plní ze slunce.
        "odber_kw": [round(x, 2) for x in odber_kw],
        "site_kw": [round(x, 2) for x in site_kw],
        "baterie_kw": [round(x, 2) for x in baterie_kw],
        "baterie_ps_kw": [round(x, 2) for x in ps_kw],
        # Druhá série pásu baterie. U peak shavingu je to obchod na spotu, tady
        # solární posun — komponenta si popisek bere z propu, ne z názvu klíče.
        "baterie_obchod_kw": [round(x, 2) for x in solar_kw],
        "stropy_kw": [round(x, 2) for x in stropy],
        "useky_stropu": useky_stropu(stropy),
        "cena_kc_mwh": None,  # PPA+BESS se nerozhoduje podle spotové ceny
        "soc_pct": [round(x, 1) for x in soc_pct] if ma_baterii else None,
        "baterie": bool(ma_baterii),
        "souhrn": {
            "max_spotreba_kw": max(odber_kw) if odber_kw else None,
            "max_odber_kw": max(odber_kw) if odber_kw else None,
            "max_site_kw": max(site_kw) if site_kw else None,
            "max_vyroba_kw": max(vyroba_kw) if vyroba_kw else None,
            "max_pretok_kw": max(pretok_kw) if pretok_kw else None,
            "nabito_kwh": round(nabito, 1),
            "vybito_kwh": round(vybito, 1),
            "ztraty_kwh": round(max(0.0, nabito - vybito), 1),
        },
    }


def useky_stropu(stropy_kw: list[float]) -> list[dict]:
    """Souvislé úseky stejného stropu – pro schodovitou čáru v detailním grafu.

    Strop se mění po měsících, takže posílat 35 tisíc hodnot je zbytečné; graf
    kreslí segmenty. Tvar je stejný jako u peak shavingu (`routes._useky_stropu`),
    aby komponenta `GrafPrubehu` fungovala bez úprav.
    """
    useky: list[dict] = []
    for i, s in enumerate(stropy_kw):
        if useky and abs(useky[-1]["strop_kw"] - s) < 1e-9:
            useky[-1]["do_index"] = i
        else:
            useky.append({"od_index": i, "do_index": i, "strop_kw": round(s, 2)})
    return useky

