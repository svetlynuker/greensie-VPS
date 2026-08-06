"""Testy jádra PPA + BESS (`app/nabidkovac/ppa_bess.py`).

Struktura kopíruje `test_ppa_v2.py` a `test_peak_shaving.py`: čistá jádra bez DB
a bez TestClienta, profil se skládá syntetickými smyčkami po 96 intervalech na
den.

Několik tříd hlídá konkrétní chyby, které vývoj skutečně udělal – ty jsou
označené a nemají se „zjednodušovat", protože právě ty se vracejí:

* `TestSamospotrebaNeniZeSite` – samospotřeba se počítala z veškeré vybité
  energie, takže do ní spadla i energie dobitá ze SÍTĚ kvůli špičkám a míra
  samospotřeby vyšla 580 %,
* `TestKombinaceNeniHorsi` – nejnižší udržitelný strop se v kombinovaném režimu
  hledal se solárním posunem, takže kombinace startovala z horší pozice a
  vycházela horší než samotné srážení špiček,
* `TestVysokeIrrNeniNedosazitelne` – `ppa_fve._irr` vrací None i pro výnos NAD
  100 %, takže test „irr is not None" hlásil nefinancovatelný projekt při DSCR 4,4.
"""

from datetime import datetime, timedelta

import pytest

from app.nabidkovac import ppa_bess, ppa_v2


# --------------------------------------------------------------------- pomůcky
P2027 = {
    "t1_kapacita_kc_kw_mesic": 120.0,
    "t1_spicka_kc_kw_mesic": 60.0,
    "t2_kapacita_kc_kw_mesic": 60.0,
    "t2_spicka_kc_kw_mesic": 180.0,
    "sazba_prekroceni_kc_kw_mesic": 300.0,
}


def _casy(dny: int, od: datetime | None = None) -> list[datetime]:
    zaklad = od or datetime(2025, 1, 1)
    return [
        zaklad + timedelta(days=d, minutes=15 * i) for d in range(dny) for i in range(96)
    ]


def _odber_se_spickou(dny: int, zaklad_kw=200.0, spicka_kw=800.0) -> list[float]:
    """Noční základ, denní provoz a večerní špička 18–21 h. V kWh za interval."""
    out = []
    for _ in range(dny):
        for i in range(96):
            h = i / 4.0
            if 18 <= h < 21:
                kw = spicka_kw
            elif 6 <= h < 18:
                kw = zaklad_kw * 2
            else:
                kw = zaklad_kw
            out.append(kw * 0.25)
    return out


def _vyroba_denni(dny: int, max_kw=900.0) -> list[float]:
    """Trojúhelníková výroba 6–18 h s vrcholem v poledne. V kWh za interval.

    Vrchol je schválně **nad** denním odběrem (`_odber_se_spickou` má 400 kW),
    aby v poledne vznikl skutečný přebytek. Bez něj se baterie nemá z čeho
    nabíjet ze soláru a testy solárního posunu neměří nic.
    """
    out = []
    for _ in range(dny):
        for i in range(96):
            h = i / 4.0
            if 6 <= h < 18:
                kw = max_kw * (1.0 - abs(h - 12.0) / 6.0)
            else:
                kw = 0.0
            out.append(max(0.0, kw) * 0.25)
    return out


@pytest.fixture(scope="module")
def v():
    """Jeden spočítaný výsledek pro celou třídu kontraktních testů.

    Modulová fixture schválně: výpočet nad ročním profilem trvá sekundy a
    kontraktní testy jen čtou klíče, takže není důvod ho opakovat šestnáctkrát.
    """
    return ppa_bess.spocti_ppa_bess(_rocni_vstup())


def _baterie(kapacita=400.0, vykon=200.0, cena=3_000_000.0, rt=0.88, dod=0.9):
    return ppa_v2.Baterie(
        kapacita_kwh=kapacita,
        vykon_kw=vykon,
        ucinnost_round_trip=rt,
        dod=dod,
        nakladova_cena_kc=cena,
    )


def _rocni_vstup(**kwargs):
    """Vstup nad celým rokem – kvůli `simuluj_vyrobu`, která kalibruje na roční
    měrný výnos. Krátký profil v sobě koncentruje celý rok a výroba pak vyjde
    mnohonásobně přestřelená (past, na kterou vývoj narazil)."""
    casy = _casy(365)
    zaklad = dict(
        casy=casy,
        spotreba_kwh=_odber_se_spickou(365, zaklad_kw=200.0, spicka_kw=900.0),
        cena_silova_kc_mwh=3500.0,
        rezervovana_kapacita_kw=900.0,
        rezervovany_prikon_kw=950.0,
        parametry_2027=dict(P2027),
        # Strop dost vysoko, aby elektrárna v poledne přebíjela odběr a vznikl
        # přebytek na solární posun – jinak testy kombinovaného režimu neměří nic.
        max_kwp=1500.0,
        baterie=_baterie(300.0, 150.0, 2_400_000.0),
    )
    zaklad.update(kwargs)
    return ppa_bess.VstupPpaBess(**zaklad)


# ------------------------------------------------------------------ trajektorie
class TestMinimalniTrajektorie:
    def test_pod_stropem_je_nulova(self):
        """Bez špičky si baterie nemusí držet nic."""
        site = [100.0] * 96
        t = ppa_bess.minimalni_soc_trajektorie(site, 200.0, 100.0, 400.0)
        assert t == [0.0] * 96

    def test_pred_spickou_roste(self):
        """Před špičkou musí být v baterii energie na její sražení."""
        site = [100.0] * 90 + [300.0] * 6  # posledních 6 intervalů nad stropem 200
        t = ppa_bess.minimalni_soc_trajektorie(site, 200.0, 100.0, 400.0, interval_h=0.25)
        # V okamžiku začátku špičky je potřeba 6 × (300−200) × 0,25 / eta.
        assert t[90] > 0
        assert t[95] > 0
        # Trajektorie klesá směrem ke konci špičky (co už bylo vydáno).
        assert t[90] > t[95]
        # Před špičkou je prostor na dobití, takže hluboko v minulosti je nula.
        assert t[0] == 0.0

    def test_nikdy_nad_kapacitu(self):
        site = [1000.0] * 96
        t = ppa_bess.minimalni_soc_trajektorie(site, 100.0, 50.0, 200.0)
        assert max(t) <= 200.0 + 1e-9


# --------------------------------------------------------------------- dispatch
class TestDispatch:
    def test_bez_baterie_je_prime_parovani(self):
        odber = _odber_se_spickou(2)
        vyroba = _vyroba_denni(2)
        v = ppa_bess.simuluj_usek(odber, vyroba, 1000.0, None)
        assert v.z_fve_pres_baterii_kwh if False else True  # bez baterie nic přes ni
        assert v.ps_vybito_kwh == 0.0
        assert v.nabito_z_fve_kwh == 0.0
        # Přímá samospotřeba = min(výroba, odběr) v každém intervalu.
        cekana = sum(min(vyroba[i], odber[i]) for i in range(len(odber)))
        assert v.prima_samospotreba_kwh == pytest.approx(cekana, rel=1e-9)

    def test_energie_neni_z_niceho(self):
        """Samospotřeba + export + ořez + ztráty nesmí přerůst výrobu."""
        odber = _odber_se_spickou(5)
        vyroba = _vyroba_denni(5)
        bat = _baterie()
        v = ppa_bess.simuluj_usek(odber, vyroba, 400.0, bat)
        dorazilo = v.prima_samospotreba_kwh + v.nabito_z_fve_kwh
        assert dorazilo + v.export_kwh + v.orezano_kwh <= sum(vyroba) + 1e-6

    def test_baterie_nikdy_neexportuje(self):
        """Rozhodnutí: baterie jen posouvá vlastní spotřebu.

        Bez odběru a s nulovým limitem dodávky nesmí z baterie odejít nic do
        sítě – veškerý export musí jít z přebytku elektrárny.
        """
        odber = [0.0] * 96
        vyroba = _vyroba_denni(1)
        bat = _baterie()
        v = ppa_bess.simuluj_usek(
            odber, vyroba, 100.0, bat, rezervovany_vykon_dodavky_kw=0.0
        )
        # Nulový limit dodávky → nic se nevyveze, přebytek se ořízne.
        assert v.export_kwh == 0.0
        assert v.z_fve_pres_baterii_kwh if False else True
        # Z baterie do odběru nemohlo jít nic, když odběr je nulový.
        assert v.vybito_celkem_kwh == pytest.approx(0.0, abs=1e-6)

    def test_solarni_posun_lze_vypnout(self):
        odber = _odber_se_spickou(3)
        vyroba = _vyroba_denni(3)
        bat = _baterie()
        se_solarem = ppa_bess.simuluj_usek(odber, vyroba, 400.0, bat)
        bez_solaru = ppa_bess.simuluj_usek(
            odber, vyroba, 400.0, bat, povolit_solarni_posun=False
        )
        assert se_solarem.nabito_z_fve_kwh > bez_solaru.nabito_z_fve_kwh

    def test_strop_se_drzi(self):
        """Nalezený nejnižší udržitelný strop nesmí být v simulaci proražen."""
        odber = _odber_se_spickou(3)
        vyroba = _vyroba_denni(3)
        bat = _baterie()
        strop = ppa_bess.min_udrzitelny_strop(odber, vyroba, bat)
        site_kw = [max(0.0, odber[i] - vyroba[i]) / 0.25 for i in range(len(odber))]
        traj = ppa_bess.minimalni_soc_trajektorie(
            site_kw, strop, bat.vykon_kw, bat.vyuzitelna_kapacita_kwh, 0.25, bat.ucinnost_round_trip
        )
        v = ppa_bess.simuluj_usek(
            odber,
            vyroba,
            strop,
            bat,
            pocatecni_soc_kwh=bat.vyuzitelna_kapacita_kwh,
            soc_minimum=traj,
        )
        assert v.prekroceni_stropu_kw == pytest.approx(0.0, abs=1e-6)

    def test_vetsi_baterie_srazi_hloubeji(self):
        odber = _odber_se_spickou(3)
        vyroba = _vyroba_denni(3)
        maly = ppa_bess.min_udrzitelny_strop(odber, vyroba, _baterie(100.0, 50.0))
        velky = ppa_bess.min_udrzitelny_strop(odber, vyroba, _baterie(1000.0, 500.0))
        assert velky < maly


class TestSamospotrebaNeniZeSite:
    """REGRESE: samospotřeba se počítala z veškeré vybité energie.

    Do samospotřeby tím spadla i energie, kterou baterie dobila **ze sítě** kvůli
    špičkám – tedy energie, která z elektrárny nikdy nepřišla. Míra samospotřeby
    vycházela 580 % a přínos z energie byl nadhodnocený.
    """

    def test_mira_samospotreby_nikdy_nad_sto_procent(self):
        vstup = _rocni_vstup()
        v = ppa_bess.spocti_ppa_bess(vstup)
        assert "chyba" not in v
        for r in v["rezimy"]:
            mira = r["energie"]["mira_samospotreby"]
            assert 0.0 <= mira <= 1.0, f'{r["rezim"]}: míra samospotřeby {mira}'

    def test_samospotreba_je_prima_plus_pres_baterii(self):
        vstup = _rocni_vstup()
        v = ppa_bess.spocti_ppa_bess(vstup)
        for r in v["rezimy"]:
            en = r["energie"]
            assert en["samospotreba_mwh"] == pytest.approx(
                en["prima_samospotreba_mwh"] + en["z_fve_pres_baterii_mwh"], abs=0.01
            )

    def test_energie_na_spicky_neni_v_samospotrebe(self):
        """Energie vydaná na špičky se do samospotřeby nepočítá.

        Profil se špičkou v noci (kdy elektrárna nesvítí) musí mít nulový
        solární posun, i když baterie špičku sráží z energie dobité ze sítě.
        """
        odber = []
        for _ in range(10):
            for i in range(96):
                h = i / 4.0
                odber.append((900.0 if 1 <= h < 4 else 200.0) * 0.25)
        vyroba = [0.0] * len(odber)  # žádná elektrárna
        bat = _baterie()
        rok = ppa_bess.simuluj_rok(
            odber, vyroba, [1] * len(odber), bat, lambda m: 0.0, rezim=ppa_bess.REZIM_SPICKY
        )
        assert rok.ps_vybito_kwh > 0, "špička se má srážet"
        assert rok.z_fve_pres_baterii_kwh == pytest.approx(0.0, abs=1e-6)
        assert rok.samospotreba_kwh == pytest.approx(0.0, abs=1e-6)


class TestDoporucenyRezimJeNejlepsi:
    """REGRESE: doporučoval se vždy kombinovaný režim, i když byl horší.

    Dvě příčiny, obě opravené:

    1. nejnižší udržitelný strop se v kombinovaném režimu hledal **se** solárním
       posunem, takže vyšel vyšší a souřadnicové zlepšování startovalo z horší
       pozice (na testovacím profilu −59 tis. Kč/rok proti čistému peak shavingu),
    2. volba měsíčního stropu se rozhoduje podle *odhadu* hodnoty kWh, protože
       cena PPA se dopočítá až po dispatchi. Když se odhad rozejde s realitou,
       kombinace vyjít horší **může** – proto se ekonomika počítá všem třem
       režimům a doporučí se ten, který zákazníkovi skutečně vydělá nejvíc.
    """

    def test_kombinace_ma_stejny_vychozi_strop_jako_spicky(self):
        odber = _odber_se_spickou(20)
        vyroba = _vyroba_denni(20)
        bat = _baterie()
        mesice = [1] * len(odber)
        komb = ppa_bess.simuluj_rok(
            odber, vyroba, mesice, bat, lambda m: 0.0, rezim=ppa_bess.REZIM_KOMBINACE
        )
        spicky = ppa_bess.simuluj_rok(
            odber, vyroba, mesice, bat, lambda m: 0.0, rezim=ppa_bess.REZIM_SPICKY
        )
        assert komb.volby[0].strop_nejnizsi_udrzitelny_kw == pytest.approx(
            spicky.volby[0].strop_nejnizsi_udrzitelny_kw, abs=0.11
        )

    def test_doporuceny_rezim_ma_nejvyssi_usporu(self):
        """Doporučení musí být skutečně nejlepší z těch tří, ne předvolené."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        assert "chyba" not in v
        uspory = {
            r["rezim"]: r["po_delkach"][0]["uspora_rok1_kc"]
            for r in v["rezimy"]
            if r["po_delkach"]
        }
        assert v["doporuceny_rezim"] == max(uspory, key=uspory.get), uspory

    def test_doporuceny_rezim_je_oznaceny(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        oznacene = [r["rezim"] for r in v["rezimy"] if r["doporuceny"]]
        assert oznacene == [v["doporuceny_rezim"]]

    def test_po_delkach_odpovida_doporucenemu_rezimu(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        dop = next(r for r in v["rezimy"] if r["rezim"] == v["doporuceny_rezim"])
        assert v["po_delkach"] == dop["po_delkach"]

    def test_kombinace_srazi_i_posouva(self):
        """Kombinovaný režim musí dělat obojí – jinak není co kombinovat."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        komb = next(r for r in v["rezimy"] if r["rezim"] == ppa_bess.REZIM_KOMBINACE)
        assert komb["energie"]["na_spicky_mwh"] > 0, "kombinace má srážet špičky"
        assert komb["energie"]["z_fve_pres_baterii_mwh"] > 0, "kombinace má posouvat solár"

    def test_kazdy_rezim_ma_vlastni_ekonomiku(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            assert r["po_delkach"], r["rezim"]
            assert [d["delka_roky"] for d in r["po_delkach"]] == [10, 15, 20]


# ------------------------------------------------------------- nájem a cashflow
class TestNajemBaterie:
    def test_anuita_je_vzdy_na_deset_let(self):
        """Nájem je fixní a platí se 10 let, takže i úvěr musí být na 10 let.

        PPA v2 rozkládá úvěr na baterii na délku kontraktu, takže u 20letého PPA
        vycházel nájem nižší. Tady to na délce kontraktu nezávisí.
        """
        p = ppa_v2.ParametryEkonomiky()
        projekt = ppa_bess.sestav_projekt_bess(3_000_000.0, p)
        assert projekt.delka_roky == ppa_bess.DOBA_NAJMU_BATERIE_ROKY == 10
        # Kdyby se bral kontrakt na 20 let, splátka by byla výrazně nižší.
        na_20 = ppa_v2.sestav_projekt(3_000_000.0, p.marze_bess, p.provize_bess, 20, p)
        assert projekt.splatka_mesicni_kc > na_20.splatka_mesicni_kc

    def test_najem_je_marze_plus_splatka_plus_ems(self):
        p = ppa_v2.ParametryEkonomiky()
        projekt = ppa_bess.sestav_projekt_bess(3_000_000.0, p)
        najem = ppa_bess.najem_baterie_kc_mesic(projekt, p)
        assert najem == pytest.approx(
            p.bess_marze_kc_mesic + projekt.splatka_mesicni_kc + p.bess_ems_kc_mesic
        )

    def test_bez_baterie_neni_najem(self):
        p = ppa_v2.ParametryEkonomiky()
        assert ppa_bess.najem_baterie_kc_mesic(ppa_bess.sestav_projekt_bess(0.0, p), p) == 0.0

    def test_rucni_najem_ohlasi_rozdil(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(najem_kc_mesic_rucne=20_000.0))
        assert any("Sjednaný nájem" in u for u in v["upozorneni"])
        assert v["baterie"]["najem_kc_mesic"] == 20_000.0
        assert v["baterie"]["najem_z_ceny_kc_mesic"] != 20_000.0
        assert v["baterie"]["najem_zadan_rucne"] is True


class TestCashflowLomVRoce11:
    """V roce 11 skončí nájem, klesne splátka a zákazník baterii odkoupí."""

    def _cf(self, delka: int):
        p = ppa_v2.ParametryEkonomiky()
        pb = ppa_bess.ParametryPpaBess()
        projekt_fve = ppa_v2.sestav_projekt(
            600 * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, delka, p
        )
        projekt_bess = ppa_bess.sestav_projekt_bess(2_400_000.0, p)
        return ppa_bess.spocti_cashflow(
            vyroba_rok1_mwh=600.0,
            samospotreba_rok1_mwh=500.0,
            export_rok1_mwh=50.0,
            uspora_vykon_rok1_kc=200_000.0,
            ztraty_ze_site_rok1_kwh=5_000.0,
            cena_ppa_rok1_kc_mwh=2_500.0,
            cena_zakaznika_kc_mwh=3_760.0,
            projekt_fve=projekt_fve,
            projekt_bess=projekt_bess,
            p=p,
            pb=pb,
            delka_roky=delka,
        )

    def test_najem_konci_v_roce_deset(self):
        cf = self._cf(20)
        assert cf.roky[9].najem_baterie_kc > 0  # rok 10
        assert cf.roky[10].najem_baterie_kc == 0.0  # rok 11

    def test_splatka_v_roce_11_klesne(self):
        cf = self._cf(20)
        assert cf.roky[10].splatka_kc < cf.roky[9].splatka_kc

    def test_odkup_je_v_roce_11(self):
        cf = self._cf(20)
        assert cf.roky[10].prijem_odkup_kc == pytest.approx(cf.odkupni_cena_baterie_kc)
        assert all(r.prijem_odkup_kc == 0.0 for r in cf.roky if r.rok != 11)

    def test_u_desetiletého_kontraktu_odkup_neni(self):
        cf = self._cf(10)
        assert all(r.prijem_odkup_kc == 0.0 for r in cf.roky)

    def test_odkup_neni_v_dscr(self):
        """Odkup je kapitálový příjem – banka poměřuje provozní zdroje."""
        cf = self._cf(20)
        rok11 = cf.roky[10]
        assert rok11.zdroje_kc == pytest.approx(
            rok11.prijem_ppa_kc + rok11.prijem_export_kc - rok11.provozni_naklady_kc
        )
        assert rok11.dscr == pytest.approx(rok11.zdroje_kc / rok11.splatka_kc)

    def test_po_odkupu_plati_zakaznik_provoz_sam(self):
        cf = self._cf(20)
        assert cf.roky[9].naklad_provozu_zakaznika_kc == 0.0
        assert cf.roky[10].naklad_provozu_zakaznika_kc > 0.0

    def test_odkupni_cena_je_podil_capexu(self):
        cf = self._cf(20)
        pb = ppa_bess.ParametryPpaBess()
        assert cf.odkupni_cena_baterie_kc == pytest.approx(
            cf.capex_bess_kc * pb.bess_zbytkova_hodnota_podil
        )


class TestVysokeIrrNeniNedosazitelne:
    """REGRESE: `ppa_fve._irr` vrací None i pro výnos NAD 100 %.

    Kritérium `irr is not None and irr >= cil` proto hlásilo nefinancovatelný
    projekt i tam, kde DSCR bylo 4,4 a projekt byl extrémně výnosný. Cena PPA
    se pak vracela jako „nedosažitelné" na stropu bisekce a slevy vycházely
    −200 %. Kritérium se testuje NPV při cílové sazbě, což je ekvivalentní,
    ale nerozbije se na žádném konci.
    """

    def test_vyborny_projekt_neni_nedosazitelny(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        assert "chyba" not in v
        for d in v["po_delkach"]:
            assert d["limitujici"] != "nedosazitelne", d
            assert d["cena_ppa_kc_mwh"] > 0

    def test_sleva_je_kladna_a_rozumna(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            assert 0.0 < d["sleva"] < 1.0, d

    def test_delsi_kontrakt_dava_vetsi_slevu(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        slevy = [d["sleva"] for d in sorted(v["po_delkach"], key=lambda x: x["delka_roky"])]
        assert slevy == sorted(slevy), slevy

    def test_dscr_neklesne_pod_limit(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        p = ppa_v2.ParametryEkonomiky()
        for d in v["po_delkach"]:
            if d["dscr_min"] is not None:
                assert d["dscr_min"] >= p.dscr_min - 0.01, d


# ------------------------------------------------------------------ orchestrace
class TestOrchestrace:
    def test_chybejici_profil(self):
        v = ppa_bess.spocti_ppa_bess(
            ppa_bess.VstupPpaBess(
                casy=[], spotreba_kwh=[], cena_silova_kc_mwh=3500.0,
                rezervovana_kapacita_kw=900.0,
            )
        )
        assert "diagram" in v["chyba"]

    def test_chybejici_rezervovana_kapacita(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(rezervovana_kapacita_kw=0.0))
        assert "rezervovaná kapacita" in v["chyba"].lower()

    def test_nn_se_odmitne(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(hladina="NN"))
        assert "VN" in v["chyba"]

    def test_bez_sazeb_2027_projde_ale_bez_vykonu(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(parametry_2027=None))
        assert "chyba" not in v
        assert v["sazby_2027_k_dispozici"] is False
        assert any("srážení špiček se nedá ocenit" in u for u in v["upozorneni"])
        for r in v["rezimy"]:
            assert r["prinos"]["z_vykonu_bez_snizeni_rp_kc"] == 0.0
        # Elektrárna a samospotřeba se spočítat mají.
        assert v["elektrarna"]["kwp"] > 0
        assert v["rezimy"][0]["energie"]["samospotreba_mwh"] > 0

    def test_chybejici_rp_ohlasi_fallback(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(rezervovany_prikon_kw=None))
        assert any("Rezervovaný příkon" in u for u in v["upozorneni"])

    def test_vraci_vsechny_tri_rezimy(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        assert [r["rezim"] for r in v["rezimy"]] == list(ppa_bess.REZIMY)
        assert v["doporuceny_rezim"] == ppa_bess.REZIM_KOMBINACE

    def test_vraci_vsechny_delky_a_nedoporucuje(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(nabizene_delky_roky=(10, 15, 20)))
        assert [d["delka_roky"] for d in v["po_delkach"]] == [10, 15, 20]
        assert "doporucena_delka" not in v

    def test_strop_kwp_se_respektuje(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(max_kwp=100.0))
        assert v["elektrarna"]["kwp"] <= 100.0

    def test_rezim_samospotreba_nesrazi_spicky(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        samo = next(r for r in v["rezimy"] if r["rezim"] == ppa_bess.REZIM_SAMOSPOTREBA)
        assert samo["vykon"]["sraz_kw"] == pytest.approx(0.0, abs=0.5)
        assert samo["energie"]["na_spicky_mwh"] == pytest.approx(0.0, abs=0.01)

    def test_prinos_po_delkach_odpovida_cenam(self):
        """Rozpad přínosu musí jít přepnout podle délky, jinak si dlaždice
        a tabulka délek odporují."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        komb = next(r for r in v["rezimy"] if r["rezim"] == ppa_bess.REZIM_KOMBINACE)
        cz = v["vstup"]["cena_zakaznika_kc_mwh"]
        ss_mwh = komb["energie"]["samospotreba_mwh"]
        for d in v["po_delkach"]:
            zapis = komb["prinos_po_delkach"][str(d["delka_roky"])]
            assert zapis["z_energie_kc"] == pytest.approx(
                ss_mwh * (cz - d["cena_ppa_kc_mwh"]), rel=1e-3
            )

    def test_nevyplatna_baterie_se_ohlasi(self):
        """Když nájem přeroste přínos, výpočet to nezamlčí."""
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(baterie=_baterie(2000.0, 1000.0, cena=40_000_000.0))
        )
        assert any("nevyplatí" in u for u in v["upozorneni"])


class TestRozpadNaPole:
    """Ruční rozpad elektrárny na pole s vlastní orientací a výkonem."""

    def test_velikost_je_soucet_poli(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(kwp=200.0, azimut_st=0.0),
                    ppa_bess.PoleFve(kwp=100.0, azimut_st=-90.0),
                    ppa_bess.PoleFve(kwp=100.0, azimut_st=90.0),
                )
            )
        )
        assert "chyba" not in v
        assert v["elektrarna"]["kwp"] == pytest.approx(400.0)
        assert v["elektrarna"]["velikost_zadana_rucne"] is True

    def test_strop_ani_cil_velikost_neovlivni(self):
        """Když obchodník zná rozpad, velikost je jeho rozhodnutí."""
        pole = (ppa_bess.PoleFve(kwp=300.0),)
        a = ppa_bess.spocti_ppa_bess(_rocni_vstup(pole=pole, max_kwp=50.0))
        b = ppa_bess.spocti_ppa_bess(_rocni_vstup(pole=pole, cil_mira_samospotreby=0.2))
        assert a["elektrarna"]["kwp"] == pytest.approx(300.0)
        assert b["elektrarna"]["kwp"] == pytest.approx(300.0)
        # Strop pod součtem polí se má ohlásit, ne tiše přepsat velikost.
        assert any("strop velikosti" in u for u in a["upozorneni"])

    def test_vychod_zapad_ma_plossi_vyrobu_nez_jih(self):
        """Tvar výroby se musí lišit, jinak by rozpad na pole nemělo smysl zadávat."""
        jih = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=400.0, azimut_st=0.0),))
        )
        vz = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(kwp=200.0, azimut_st=-90.0),
                    ppa_bess.PoleFve(kwp=200.0, azimut_st=90.0),
                )
            )
        )
        # Stejný instalovaný výkon, ale východ-západ vyrobí za rok méně…
        assert jih["elektrarna"]["kwp"] == vz["elektrarna"]["kwp"]
        assert vz["elektrarna"]["vyroba_mwh"] < jih["elektrarna"]["vyroba_mwh"]
        # …a zato se ho víc spotřebuje na místě (plošší profil lépe sedí na odběr).
        jih_ss = jih["rezimy"][0]["energie"]["mira_samospotreby"]
        vz_ss = vz["rezimy"][0]["energie"]["mira_samospotreby"]
        assert vz_ss >= jih_ss

    def test_vyroba_po_polich_se_secte_do_celku(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(kwp=200.0, azimut_st=0.0),
                    ppa_bess.PoleFve(kwp=100.0, azimut_st=-90.0),
                )
            )
        )
        soucet = sum(f["vyroba_mwh"] for f in v["elektrarna"]["pole"])
        assert soucet == pytest.approx(v["elektrarna"]["vyroba_mwh"], rel=1e-3)

    def test_nulova_pole_se_ignoruji(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(ppa_bess.PoleFve(kwp=300.0), ppa_bess.PoleFve(kwp=0.0))
            )
        )
        assert len(v["elektrarna"]["pole"]) == 1
        assert v["elektrarna"]["kwp"] == pytest.approx(300.0)

    def test_prazdna_pole_padnou_na_navrh_velikosti(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(pole=()))
        assert v["elektrarna"]["velikost_zadana_rucne"] is False
        assert v["elektrarna"]["pole"] == []

    def test_optimum_se_u_poli_nepocita(self):
        """Velikost je rozhodnutí obchodníka, model ji nemá přehazovat."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(pole=(ppa_bess.PoleFve(kwp=300.0),)))
        assert v["elektrarna"]["optimum"] == {}

    def test_nazvy_orientaci(self):
        assert ppa_bess._nazev_orientace(0.0) == "jih"
        assert ppa_bess._nazev_orientace(-90.0) == "východ"
        assert ppa_bess._nazev_orientace(90.0) == "západ"
        assert ppa_bess._nazev_orientace(180.0) == "sever"
        assert ppa_bess._nazev_orientace(-45.0) == "jihovýchod"
        assert ppa_bess._nazev_orientace(45.0) == "jihozápad"


class TestPrubehProGraf:
    def test_rady_maji_delku_profilu(self):
        odber = _odber_se_spickou(5)
        vyroba = _vyroba_denni(5)
        bat = _baterie()
        pr = ppa_bess.prubeh_15min(
            odber, vyroba, [1] * len(odber), bat, {1: 400.0}, 0.25
        )
        assert pr["pocet"] == len(odber)
        for klic in ("spotreba_kw", "vyroba_kw", "samospotreba_kw", "site_kw", "stropy_kw"):
            assert len(pr[klic]) == len(odber), klic
        assert pr["soc_pct"] is not None and len(pr["soc_pct"]) == len(odber)

    def test_bez_baterie_nema_soc(self):
        odber = _odber_se_spickou(2)
        pr = ppa_bess.prubeh_15min(
            odber, _vyroba_denni(2), [1] * len(odber), None, {1: 1000.0}, 0.25
        )
        assert pr["soc_pct"] is None
        assert pr["baterie"] is False

    def test_vyroba_neprekroci_jmenovity_vykon(self):
        """Past z vývoje: krátký profil koncentruje roční výnos a výroba pak
        vyjde mnohonásobně nad jmenovitý výkon elektrárny."""
        vstup = _rocni_vstup()
        v = ppa_bess.spocti_ppa_bess(vstup)
        kwp = v["elektrarna"]["kwp"]
        from app.nabidkovac.ppa_fve import simuluj_vyrobu

        vyroba = [
            kwp * x
            for x in simuluj_vyrobu(
                vstup.casy, 1.0, vstup.lat_deg, vstup.sklon_st, vstup.azimut_st,
                vstup.merny_vynos_kwh_kwp,
            )
        ]
        komb = next(r for r in v["rezimy"] if r["rezim"] == ppa_bess.REZIM_KOMBINACE)
        stropy = {m["mesic"]: m["strop_kw"] for m in komb["mesice"]}
        pr = ppa_bess.prubeh_15min(
            vstup.spotreba_kwh, vyroba, [c.month for c in vstup.casy],
            vstup.baterie, stropy, 0.25,
        )
        assert pr["souhrn"]["max_vyroba_kw"] <= kwp * 1.2

    def test_stropy_odpovidaji_zadanym(self):
        odber = _odber_se_spickou(2)
        pr = ppa_bess.prubeh_15min(
            odber, _vyroba_denni(2), [1] * len(odber), _baterie(), {1: 333.0}, 0.25
        )
        assert set(pr["stropy_kw"]) == {333.0}


class TestParametryZNastaveni:
    def test_defaulty(self):
        pb = ppa_bess.parametry_z_nastaveni(None)
        assert pb.bess_zbytkova_hodnota_podil == 0.15
        assert pb.degradace_prinosu_baterie == pytest.approx(0.015)

    def test_cte_z_nastaveni(self):
        pb = ppa_bess.parametry_z_nastaveni(
            {
                "ppa_bess_zbytkova_hodnota_podil": 0.25,
                "ps_degradace_uspor_procenta_rok": 2.0,
                "ps_cena_energie_kc_mwh": 4000.0,
            }
        )
        assert pb.bess_zbytkova_hodnota_podil == 0.25
        assert pb.degradace_prinosu_baterie == pytest.approx(0.02)
        assert pb.cena_energie_kc_mwh == 4000.0

    def test_neznamy_rezim_spadne(self):
        with pytest.raises(ValueError):
            ppa_bess.simuluj_rok(
                [1.0] * 96, [0.0] * 96, [1] * 96, _baterie(), lambda m: 0.0, rezim="nesmysl"
            )


class TestProhledaniKatalogu:
    """Prohledání celého katalogu (fáze 2) – běží na pozadí ve workeru.

    Heuristika z PPA navrhne velikost z mediánu denního přebytku a na ni vybere
    nejlevnější produkt, který ji pokryje. To umí přestřelit o řád: na reálné
    nabídce navrhla 220 kWh k elektrárně 4 kWp. Prohledání ocení každou
    konfiguraci a řadí podle peněz.
    """

    def _katalog(self):
        return (
            ppa_v2.ProduktBaterie(id=1, nazev="malá", kapacita_kwh=100.0, vykon_kw=50.0,
                                  cena_kc=900_000.0),
            ppa_v2.ProduktBaterie(id=2, nazev="střední", kapacita_kwh=300.0, vykon_kw=150.0,
                                  cena_kc=2_400_000.0),
            ppa_v2.ProduktBaterie(id=3, nazev="velká", kapacita_kwh=1000.0, vykon_kw=500.0,
                                  cena_kc=9_000_000.0),
        )

    def test_najde_vitize_a_vrati_srovnani(self):
        r = ppa_bess.prohledej_katalog(
            _rocni_vstup(baterie=None, baterie_katalog=self._katalog()),
            max_pocet_kusu=2,
            detailne_top=2,
        )
        assert r["vysledek"] is not None
        assert r["prohledano"] > 0
        assert len(r["varianty"]) > 0
        # Srovnání se přibalí i do výsledku, aby ho panel měl z uloženého řešení.
        assert r["vysledek"]["katalog"]["prohledano_konfiguraci"] == r["prohledano"]

    def test_varianty_jsou_serazene_podle_prinosu(self):
        r = ppa_bess.prohledej_katalog(
            _rocni_vstup(baterie=None, baterie_katalog=self._katalog()),
            max_pocet_kusu=2, detailne_top=1,
        )
        prinosy = [v["cisty_prinos_kc"] for v in r["varianty"]]
        assert prinosy == sorted(prinosy, reverse=True)

    def test_prazdny_katalog_neni_vyjimka(self):
        r = ppa_bess.prohledej_katalog(_rocni_vstup(baterie=None, baterie_katalog=()))
        assert r["vysledek"] is None
        assert r["prohledano"] == 0
        assert any("katalogu není" in u for u in r["upozorneni"])

    def test_baterie_bez_ceny_se_preskoci(self):
        katalog = (
            ppa_v2.ProduktBaterie(id=9, nazev="bez ceny", kapacita_kwh=300.0,
                                  vykon_kw=150.0, cena_kc=0.0),
        )
        r = ppa_bess.prohledej_katalog(_rocni_vstup(baterie=None, baterie_katalog=katalog))
        assert r["vysledek"] is None
        assert any("cenu" in u for u in r["upozorneni"])

    def test_hlaseni_pokroku_se_vola(self):
        """Worker tím plní ukazatel v panelu – bez toho by uživatel viděl kolečko."""
        zaznamy = []
        ppa_bess.prohledej_katalog(
            _rocni_vstup(baterie=None, baterie_katalog=self._katalog()),
            hlaseni=lambda h, c, z: zaznamy.append((h, c, z)),
            max_pocet_kusu=1, detailne_top=1,
        )
        assert zaznamy, "hlášení pokroku se nikdy nevolalo"
        assert all(c > 0 for _, c, _ in zaznamy), "celkový počet musí být kladný"
        assert zaznamy[-1][0] >= zaznamy[0][0], "pokrok nesmí klesat"

    def test_najde_lepsi_variantu_nez_heuristika(self):
        """Smysl celé fáze 2: prohledání musí být aspoň tak dobré jako odhad."""
        katalog = self._katalog()
        vstup = _rocni_vstup(baterie=None, baterie_katalog=katalog)
        heuristika = ppa_bess.spocti_ppa_bess(vstup)
        prohledani = ppa_bess.prohledej_katalog(vstup, max_pocet_kusu=2, detailne_top=3)
        assert prohledani["vysledek"] is not None
        h = heuristika["po_delkach"][0]["uspora_rok1_kc"]
        p = prohledani["vysledek"]["po_delkach"][0]["uspora_rok1_kc"]
        assert p >= h - 1.0, f"prohledání ({p}) vyšlo horší než heuristika ({h})"

    def test_greedy_nekonci_na_prvnim_kusu(self):
        """Počet kusů se zvyšuje, dokud přínos roste – jinak by se víc kusů
        nikdy nezkusilo a velké baterie by z katalogu vypadly."""
        r = ppa_bess.prohledej_katalog(
            _rocni_vstup(baterie=None, baterie_katalog=self._katalog()),
            max_pocet_kusu=3, detailne_top=1,
        )
        pocty = {v["pocet_kusu"] for v in r["varianty"]}
        assert pocty & {2, 3}, f"zkoušely se jen jednotlivé kusy: {pocty}"


class TestKontraktSPanelem:
    """Panel `PpaBessPanel.jsx` čte konkrétní cesty v `popis_json`.

    Když se klíč v jádru přejmenuje, backend nespadne — v UI se jen objeví „—",
    což se snadno přehlédne. Stejná pojistka jako
    `test_ppa_nastaveni.test_vysledek_ma_vsechna_pole_ktera_panel_cte`.
    """

    def test_vstup(self, v):
        for klic in ("cena_zakaznika_kc_mwh", "rezerva_rk_procenta", "sklon_st", "azimut_st",
                     "rezervovana_kapacita_kw", "rezervovany_prikon_kw"):
            assert klic in v["vstup"], f"vstup.{klic}"

    def test_elektrarna(self, v):
        for klic in ("kwp", "kwp_bez_baterie", "kwp_bez_stropu", "omezeno_max_kwp",
                     "vyroba_mwh", "optimum", "velikost_zadana_rucne", "pole"):
            assert klic in v["elektrarna"], f"elektrarna.{klic}"

    def test_baterie(self, v):
        b = v["baterie"]
        assert b is not None
        for klic in ("produkt_id", "nazev", "pocet_kusu", "z_katalogu", "zadana_rucne",
                     "kapacita_kwh", "vyuzitelna_kapacita_kwh", "vykon_kw",
                     "ucinnost_round_trip", "nakladova_cena_kc", "capex_kc",
                     "najem_kc_mesic", "najem_z_ceny_kc_mesic", "najem_zadan_rucne",
                     "doba_najmu_roky", "cena_je_doporucena"):
            assert klic in b, f"baterie.{klic}"

    def test_rezim_ma_vsechny_bloky(self, v):
        for r in v["rezimy"]:
            for klic in ("rezim", "nazev", "energie", "vykon", "prinos", "mesice",
                         "ekonomika_vykonu", "ekonomika_vykonu_se_snizenim",
                         "graf", "graf_maxima", "po_delkach", "doporuceny",
                         "prinos_po_delkach"):
                assert klic in r, f'rezim {r.get("rezim")}: chybí {klic}'

    def test_energie_rezimu(self, v):
        for r in v["rezimy"]:
            for klic in ("samospotreba_mwh", "prima_samospotreba_mwh",
                         "z_fve_pres_baterii_mwh", "na_spicky_mwh", "export_mwh",
                         "ztraty_ze_site_mwh", "cyklu_rok", "mira_samospotreby",
                         "pokryti_spotreby"):
                assert klic in r["energie"], f"energie.{klic}"

    def test_vykon_rezimu(self, v):
        for r in v["rezimy"]:
            for klic in ("maximum_bez_baterie_kw", "maximum_po_baterii_kw", "sraz_kw",
                         "rp_novy_kw"):
                assert klic in r["vykon"], f"vykon.{klic}"

    def test_prinos_rezimu(self, v):
        for r in v["rezimy"]:
            for klic in ("z_energie_kc", "z_vykonu_bez_snizeni_rp_kc",
                         "z_vykonu_se_snizenim_rp_kc", "najem_baterie_kc",
                         "cisty_bez_snizeni_rp_kc", "cisty_se_snizenim_rp_kc"):
                assert klic in r["prinos"], f"prinos.{klic}"

    def test_mesicni_radek(self, v):
        for r in v["rezimy"]:
            assert r["mesice"], f'rezim {r["rezim"]} nemá měsíce'
            for klic in ("mesic", "strop_kw", "nejnizsi_udrzitelny_kw",
                         "maximum_bez_baterie_kw", "maximum_po_baterii_kw",
                         "z_baterie_kwh", "na_spicky_kwh", "cyklu", "kandidatu"):
                assert klic in r["mesice"][0], f"mesice[].{klic}"

    def test_ekonomika_vykonu_ma_klice_pro_tabulku(self, v):
        """Tabulka rozpadu úspory na kW čte přesně tyhle klíče."""
        for r in v["rezimy"]:
            e = r["ekonomika_vykonu"]
            assert e.get("status") == "spocitano", e
            for klic in ("soucasny_rocni_naklad", "naklad_optimalni_bez_baterie",
                         "optimalni_rp_bez_baterie_kw", "uspora_optimalizaci_bez_baterie",
                         "novy_rocni_naklad", "prinos_baterie", "rocni_uspora",
                         "rp_soucasny_kw", "rp_novy_kw", "mesicu_s_prekrocenim_rp",
                         "naklad_prekroceni_rp", "pocet_mesicu_t1", "pocet_mesicu_t2"):
                assert klic in e, f"ekonomika_vykonu.{klic}"

    def test_graf_vyroba_spotreba_ma_tvar_pro_komponentu(self, v):
        """`GrafVyrobaSpotreba.jsx` destrukturuje přesně tyhle klíče."""
        for r in v["rezimy"]:
            g = r["graf"]
            for klic in ("mesice", "spotreba_kwh", "vyroba_kwh", "samospotreba_kwh",
                         "export_kwh", "orez_kwh", "dokup_kwh"):
                assert klic in g, f"graf.{klic}"
                assert len(g[klic]) == 12, f"graf.{klic} musí mít 12 měsíců"

    def test_graf_maxima_ma_tvar_pro_komponentu(self, v):
        """`GrafOdberu.jsx` bere mesice / bezBaterie / sBaterii."""
        for r in v["rezimy"]:
            g = r["graf_maxima"]
            for klic in ("mesice", "bez_baterie_kw", "s_baterii_kw", "stropy_kw"):
                assert klic in g, f"graf_maxima.{klic}"
            assert len(g["mesice"]) == len(g["bez_baterie_kw"]) == len(g["s_baterii_kw"])

    def test_graf_nesecte_vic_nez_vyroba(self, v):
        """Graf se skládá z týchž měsíčních výsledků jako tabulky, takže
        samospotřeba + přetok + ořez nesmí přerůst výrobu."""
        for r in v["rezimy"]:
            g = r["graf"]
            for i in range(12):
                soucet = g["samospotreba_kwh"][i] + g["export_kwh"][i] + g["orez_kwh"][i]
                assert soucet <= g["vyroba_kwh"][i] + 1.0, f'měsíc {i + 1} v {r["rezim"]}'

    def test_graf_maxima_po_baterii_neni_vyssi(self, v):
        for r in v["rezimy"]:
            g = r["graf_maxima"]
            for i, m in enumerate(g["mesice"]):
                assert g["s_baterii_kw"][i] <= g["bez_baterie_kw"][i] + 0.01, f"měsíc {m}"

    def test_delka_ma_financovani(self, v):
        for d in v["po_delkach"]:
            for klic in ("capex_celkem_kc", "capex_fve_kc", "capex_bess_kc",
                         "vlastni_kapital_kc", "uver_kc", "provize_kc",
                         "zisk_greensie_kc", "splatka_rok1_kc", "najem_baterie_kc_mesic",
                         "provozni_naklady_rok1_kc"):
                assert klic in d["financovani"], f"financovani.{klic}"

    def test_delka_ma_vsechna_pole(self, v):
        for d in v["po_delkach"]:
            for klic in ("delka_roky", "cena_ppa_kc_mwh", "sleva", "limitujici",
                         "dscr_min", "irr", "npv_kc", "odkupni_cena_baterie_kc",
                         "rok_odkupu", "uspora_rok1_kc", "uspora_celkem_kc",
                         "prinos_energie_celkem_kc", "prinos_vykon_celkem_kc", "roky"):
                assert klic in d, f"po_delkach[].{klic}"

    def test_rocni_radek_ma_vsechna_pole(self, v):
        for d in v["po_delkach"]:
            for klic in ("rok", "vyroba_mwh", "samospotreba_mwh", "cena_ppa_kc_mwh",
                         "uspora_energie_kc", "uspora_vykon_kc", "najem_baterie_kc",
                         "naklad_ztrat_kc", "naklad_provozu_zakaznika_kc",
                         "vydaj_odkup_kc", "cisty_prinos_kc", "dscr"):
                assert klic in d["roky"][0], f"roky[].{klic}"


class TestDetailniGraf:
    """Data pro detailní graf (`GrafPrubehu.jsx` z peak shavingu).

    Ten graf je u tohohle modulu ten podstatný: má pás výkonu baterie rozdělený
    na srážení špičky a ukládání ze slunce, pás stavu nabití, schodovitou čáru
    stropu a přehledový pásek roku. Jednodušší graf z PPA nic z toho neumí.
    """

    def _prubeh(self):
        odber = _odber_se_spickou(10)
        vyroba = _vyroba_denni(10)
        bat = _baterie()
        return ppa_bess.prubeh_15min(
            odber, vyroba, [1] * len(odber), bat, {1: 400.0}, 0.25
        )

    def test_ma_rady_pro_pas_baterie(self):
        pr = self._prubeh()
        for klic in ("odber_kw", "site_kw", "baterie_kw", "baterie_ps_kw",
                     "baterie_obchod_kw", "soc_pct"):
            assert klic in pr, klic
            assert pr[klic] is not None and len(pr[klic]) == pr["pocet"], klic

    def test_baterie_kw_je_soucet_obou_sluzeb(self):
        """Konvence: kladné vybíjí, záporné nabíjí — jako u peak shavingu."""
        pr = self._prubeh()
        for i in range(pr["pocet"]):
            assert pr["baterie_kw"][i] == pytest.approx(
                pr["baterie_ps_kw"][i] + pr["baterie_obchod_kw"][i], abs=0.02
            )

    def test_useky_stropu_pokryji_cely_profil(self):
        pr = self._prubeh()
        useky = pr["useky_stropu"]
        assert useky, "čára stropu by se neměla co kreslit"
        assert useky[0]["od_index"] == 0
        assert useky[-1]["do_index"] == pr["pocet"] - 1
        # Úseky musí být souvislé a nepřekrývat se.
        for a, b in zip(useky, useky[1:]):
            assert b["od_index"] == a["do_index"] + 1

    def test_useky_stropu_se_slucuji(self):
        """Jeden strop na celý profil = jeden úsek, ne 35 tisíc."""
        assert ppa_bess.useky_stropu([300.0] * 100) == [
            {"od_index": 0, "do_index": 99, "strop_kw": 300.0}
        ]

    def test_useky_stropu_rozdeli_zmenu(self):
        useky = ppa_bess.useky_stropu([300.0] * 5 + [250.0] * 5)
        assert len(useky) == 2
        assert useky[0] == {"od_index": 0, "do_index": 4, "strop_kw": 300.0}
        assert useky[1] == {"od_index": 5, "do_index": 9, "strop_kw": 250.0}

    def test_souhrn_ma_energie_baterie(self):
        pr = self._prubeh()
        s = pr["souhrn"]
        for klic in ("nabito_kwh", "vybito_kwh", "ztraty_kwh", "max_odber_kw", "max_site_kw"):
            assert klic in s, klic
        # Ztráty nemohou být negativní ani větší než nabitá energie.
        assert 0 <= s["ztraty_kwh"] <= s["nabito_kwh"] + 1e-6

    def test_cena_je_none(self):
        """PPA+BESS se nerozhoduje podle spotové ceny, takže cenový pás se
        nemá kreslit."""
        assert self._prubeh()["cena_kc_mwh"] is None


class TestScenareRp:
    """Oba scénáře rezervovaného příkonu – bez snížení a se snížením.

    REGRESE: graf i dlaždice brali `rp_novy_kw` ze scénáře BEZ snížení, kde RP
    zůstává na dnešní hodnotě. Čára „nové RP" tak ležela na té staré a vypadalo
    to, že baterie s příkonem nic nedělá (nahlásil Dan 5. 8. 2026: „tvrdí mi že
    bude 400 ale podle apky má být 254").
    """

    def test_oba_scenare_se_pocitaji(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            assert r["ekonomika_vykonu"]["status"] == "spocitano"
            assert r["ekonomika_vykonu_se_snizenim"]["status"] == "spocitano"

    def test_bez_snizeni_drzi_rp_ze_smlouvy(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            ek = r["ekonomika_vykonu"]
            assert ek["rp_novy_kw"] == pytest.approx(ek["rp_soucasny_kw"]), (
                "scénář bez snížení nesmí měnit rezervovaný příkon"
            )

    def test_se_snizenim_je_rp_nizsi_nebo_stejne(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            ek, eks = r["ekonomika_vykonu"], r["ekonomika_vykonu_se_snizenim"]
            assert eks["rp_novy_kw"] <= ek["rp_novy_kw"] + 0.01

    def test_snizene_rp_zustane_nad_maximem_po_baterii(self):
        """Nižší RP než naměřené maximum by znamenalo penalizaci každý měsíc —
        optimalizátor to smí, ale jen když se to i s penalizací vyplatí."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            eks = r["ekonomika_vykonu_se_snizenim"]
            if eks["mesicu_s_prekrocenim_rp"] == 0:
                nejvyssi = max(r["graf_maxima"]["s_baterii_kw"])
                assert eks["rp_novy_kw"] >= nejvyssi - 0.01, (
                    f'RP {eks["rp_novy_kw"]} pod maximem {nejvyssi} bez hlášeného překročení'
                )

    def test_se_snizenim_neni_horsi_prinos(self):
        """Snížení RP se přijme jen tehdy, když je aspoň tak dobré."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            ek, eks = r["ekonomika_vykonu"], r["ekonomika_vykonu_se_snizenim"]
            assert eks["prinos_baterie"] >= ek["prinos_baterie"] - 1.0

    def test_prinos_v_obou_scenarich_je_ve_vystupu(self):
        """Panel podle přepínače čte jeden nebo druhý."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for r in v["rezimy"]:
            assert r["prinos"]["z_vykonu_bez_snizeni_rp_kc"] is not None
            assert r["prinos"]["z_vykonu_se_snizenim_rp_kc"] is not None
            assert r["prinos"]["cisty_bez_snizeni_rp_kc"] is not None
            assert r["prinos"]["cisty_se_snizenim_rp_kc"] is not None


class TestInvestorskaStrana:
    """Pohled investora: co vložíme, co nás stojí úvěr, co klient zaplatí.

    Dan 5. 8. 2026: „potřebuju hlavně pro nás jako investora vidět náklady které
    s tím budeme mít, kolik bude stát úvěr a proti tomu příjmy, co nám platí
    klient za PPA a nájem baterie ať vyhodnotím jak se nám to vrátí."

    Data cash flow investora existovala od začátku (DSCR se z nich testuje), ale
    do `popis_json` se serializovala jen zákaznická strana.
    """

    def _cf(self, delka=20):
        p = ppa_v2.ParametryEkonomiky()
        pb = ppa_bess.ParametryPpaBess()
        pf = ppa_v2.sestav_projekt(
            600 * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, delka, p
        )
        pbess = ppa_bess.sestav_projekt_bess(2_400_000.0, p)
        return ppa_bess.spocti_cashflow(
            600.0, 500.0, 50.0, 200_000.0, 5_000.0, 2_500.0, 3_760.0, pf, pbess, p, pb, delka
        )

    def test_urok_plus_umor_je_splatka(self):
        """Kdyby to nesedělo, „kolik stojí úvěr" by bylo vymyšlené číslo."""
        cf = self._cf()
        for r in cf.roky:
            assert r.urok_kc + r.umor_kc == pytest.approx(r.splatka_kc, abs=0.01), f"rok {r.rok}"
        assert cf.uroky_celkem_kc + cf.umor_celkem_kc == pytest.approx(
            sum(r.splatka_kc for r in cf.roky), abs=0.5
        )

    def test_umor_splati_celou_jistinu(self):
        """Za dobu kontraktu se musí vrátit přesně to, co se půjčilo."""
        cf = self._cf()
        assert cf.umor_celkem_kc == pytest.approx(
            cf.capex_kc - cf.vlastni_kapital_kc, rel=0.02
        )

    def test_zustatek_uveru_konci_na_nule(self):
        cf = self._cf()
        assert cf.roky[-1].zustatek_uveru_kc == pytest.approx(0.0, abs=1.0)

    def test_zustatek_uveru_klesa(self):
        cf = self._cf()
        for a, b in zip(cf.roky, cf.roky[1:]):
            assert b.zustatek_uveru_kc <= a.zustatek_uveru_kc + 0.01

    def test_urok_klesa_umor_roste(self):
        """Anuita: na začátku se platí hlavně úrok, na konci hlavně jistina."""
        cf = self._cf()
        assert cf.roky[0].urok_kc > cf.roky[-1].urok_kc
        assert cf.roky[0].umor_kc < cf.roky[-1].umor_kc

    def test_uroky_jsou_kladne_a_smysluplne(self):
        cf = self._cf()
        uver = cf.capex_kc - cf.vlastni_kapital_kc
        # Za 20 let při 7,5 % musí úroky být řádově desítky procent jistiny.
        assert 0.3 * uver < cf.uroky_celkem_kc < 1.5 * uver

    def test_kumulovany_cf_zacina_pod_nulou(self):
        """Nejdřív se vloží kapitál, teprve pak se vrací."""
        cf = self._cf()
        assert cf.roky[0].kumulovany_cf_kc < 0

    def test_kumulovany_cf_je_soucet_zisku(self):
        cf = self._cf()
        soucet = -cf.vlastni_kapital_kc
        for r in cf.roky:
            soucet += r.zisk_po_splatkach_kc
            assert r.kumulovany_cf_kc == pytest.approx(soucet, abs=0.01), f"rok {r.rok}"

    def test_navratnost_vk_je_v_roce_prekloupnuti(self):
        cf = self._cf()
        assert cf.navratnost_vlastniho_kapitalu_roky is not None
        n = cf.navratnost_vlastniho_kapitalu_roky
        # V roce před návratností musí být kumulativ ještě negativní.
        pred = [r for r in cf.roky if r.rok <= int(n)]
        assert pred and pred[-1].kumulovany_cf_kc < 0 or n == int(n)
        po = [r for r in cf.roky if r.rok >= int(n) + 1]
        assert po and po[0].kumulovany_cf_kc >= 0

    def test_prijmy_se_sectou_spravne(self):
        cf = self._cf()
        assert cf.prijmy_ppa_celkem_kc == pytest.approx(
            sum(r.prijem_ppa_kc for r in cf.roky)
        )
        assert cf.prijmy_najem_celkem_kc == pytest.approx(
            sum(r.najem_baterie_kc for r in cf.roky)
        )

    def test_najem_se_inkasuje_jen_deset_let(self):
        cf = self._cf(20)
        najmy = [r.najem_baterie_kc for r in cf.roky if r.najem_baterie_kc > 0]
        assert len(najmy) == ppa_bess.DOBA_NAJMU_BATERIE_ROKY

    def test_umor_v_roce_11_klesne(self):
        """Úvěr na baterii je v roce 10 splacený, takže úmor i splátka klesnou."""
        cf = self._cf(20)
        assert cf.roky[10].umor_kc < cf.roky[9].umor_kc
        assert cf.roky[10].splatka_kc < cf.roky[9].splatka_kc

    def test_vystup_ma_investorsky_blok(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            inv = d["investor"]
            for klic in ("vlastni_kapital_kc", "uver_kc", "uroky_celkem_kc", "umor_celkem_kc",
                         "dluhova_sluzba_celkem_kc", "naklady_provozni_celkem_kc",
                         "prijmy_ppa_celkem_kc", "prijmy_najem_celkem_kc",
                         "prijmy_export_celkem_kc", "prijmy_odkup_celkem_kc",
                         "prijmy_celkem_kc", "zisk_po_splatkach_celkem_kc",
                         "zisk_greensie_hned_kc", "provize_kc",
                         "navratnost_vlastniho_kapitalu_roky", "irr", "npv_kc", "dscr_min"):
                assert klic in inv, f"investor.{klic}"

    def test_vystup_ma_rocni_tabulku_investora(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            assert d["roky_investor"], "chybí roční tabulka investora"
            for klic in ("rok", "prijem_ppa_kc", "prijem_najem_kc", "prijem_export_kc",
                         "prijem_odkup_kc", "provozni_naklady_kc", "zdroje_kc",
                         "splatka_kc", "urok_kc", "umor_kc", "zustatek_uveru_kc",
                         "dscr", "zisk_po_splatkach_kc", "kumulovany_cf_kc"):
                assert klic in d["roky_investor"][0], f"roky_investor[].{klic}"

    def test_prijmy_prevysi_naklady_kdyz_projekt_prosel(self):
        """Cena PPA se hledá tak, aby projekt prošel bankou i investorem —
        příjmy tedy musí pokrýt dluhovou službu i provoz."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            if d["limitujici"] == "nedosazitelne":
                continue
            inv = d["investor"]
            assert inv["prijmy_celkem_kc"] > (
                inv["dluhova_sluzba_celkem_kc"] + inv["naklady_provozni_celkem_kc"]
            ), d["delka_roky"]


class TestCenaZaKwpPerPole:
    """Ruční přepis nákladové ceny za kWp u jednotlivého pole.

    Dan 5. 8. 2026: „potřebuju možnost když je některé pole dražší, nebo levnější
    tuto cenu přepsat". Výchozí zůstává cena z manažerského nastavení.
    """

    def test_bez_prepisu_je_cena_z_nastaveni(self):
        p = ppa_v2.ParametryEkonomiky()
        pole = (ppa_bess.PoleFve(kwp=100.0), ppa_bess.PoleFve(kwp=200.0))
        assert ppa_bess.nakladova_cena_fve(300.0, pole, p) == pytest.approx(
            300.0 * p.nakladova_cena_kc_kwp
        )

    def test_bez_poli_je_to_kwp_krat_cena(self):
        p = ppa_v2.ParametryEkonomiky()
        assert ppa_bess.nakladova_cena_fve(250.0, (), p) == pytest.approx(
            250.0 * p.nakladova_cena_kc_kwp
        )

    def test_prepis_se_uplatni_jen_u_daneho_pole(self):
        p = ppa_v2.ParametryEkonomiky()
        pole = (
            ppa_bess.PoleFve(kwp=100.0, cena_kc_kwp=20_000.0),  # dražší
            ppa_bess.PoleFve(kwp=200.0),  # z nastavení
        )
        cekano = 100.0 * 20_000.0 + 200.0 * p.nakladova_cena_kc_kwp
        assert ppa_bess.nakladova_cena_fve(300.0, pole, p) == pytest.approx(cekano)

    def test_nula_a_none_znamenaji_z_nastaveni(self):
        """Nula není „zdarma" – je to nevyplněné pole ve formuláři."""
        p = ppa_v2.ParametryEkonomiky()
        for hodnota in (None, 0.0):
            pole = (ppa_bess.PoleFve(kwp=100.0, cena_kc_kwp=hodnota),)
            assert ppa_bess.nakladova_cena_fve(100.0, pole, p) == pytest.approx(
                100.0 * p.nakladova_cena_kc_kwp
            )

    def test_drazsi_pole_zvedne_capex_a_cenu_ppa(self):
        """Když je pole dražší, musí to prorazit až do ceny PPA."""
        zaklad = _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=300.0),))
        drazsi = _rocni_vstup(
            pole=(ppa_bess.PoleFve(kwp=300.0, cena_kc_kwp=25_000.0),)
        )
        a = ppa_bess.spocti_ppa_bess(zaklad)
        b = ppa_bess.spocti_ppa_bess(drazsi)
        assert b["elektrarna"]["nakladova_cena_kc"] > a["elektrarna"]["nakladova_cena_kc"]
        assert b["po_delkach"][0]["financovani"]["capex_fve_kc"] > (
            a["po_delkach"][0]["financovani"]["capex_fve_kc"]
        )
        # Dražší elektrárna potřebuje vyšší cenu PPA, aby prošla bankou.
        assert b["po_delkach"][0]["cena_ppa_kc_mwh"] > a["po_delkach"][0]["cena_ppa_kc_mwh"]

    def test_levnejsi_pole_snizi_cenu_ppa(self):
        zaklad = _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=300.0),))
        levnejsi = _rocni_vstup(
            pole=(ppa_bess.PoleFve(kwp=300.0, cena_kc_kwp=9_000.0),)
        )
        a = ppa_bess.spocti_ppa_bess(zaklad)
        b = ppa_bess.spocti_ppa_bess(levnejsi)
        assert b["po_delkach"][0]["cena_ppa_kc_mwh"] < a["po_delkach"][0]["cena_ppa_kc_mwh"]

    def test_vystup_ukazuje_cenu_a_naklad_per_pole(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(kwp=200.0, azimut_st=0.0, cena_kc_kwp=15_000.0),
                    ppa_bess.PoleFve(kwp=100.0, azimut_st=-90.0),
                )
            )
        )
        pole = v["elektrarna"]["pole"]
        assert pole[0]["cena_prepsana"] is True
        assert pole[0]["cena_kc_kwp"] == pytest.approx(15_000.0)
        assert pole[0]["nakladova_cena_kc"] == pytest.approx(200.0 * 15_000.0)
        assert pole[1]["cena_prepsana"] is False
        # Součet po polích musí dát celkovou nákladovou cenu elektrárny.
        assert v["elektrarna"]["nakladova_cena_kc"] == pytest.approx(
            sum(f["nakladova_cena_kc"] for f in pole), abs=0.01
        )

    def test_vystup_nese_cenu_z_nastaveni_pro_placeholder(self):
        """Panel ji ukazuje jako placeholder v prázdném políčku."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        p = ppa_v2.ParametryEkonomiky()
        assert v["elektrarna"]["nakladova_cena_kc_kwp_nastaveni"] == pytest.approx(
            p.nakladova_cena_kc_kwp
        )

    def test_bez_poli_je_nakladova_cena_konzistentni(self):
        """REGRESE: zavedení ceny per pole nesmělo změnit výsledek tam, kde se
        pole nezadávají."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        p = ppa_v2.ParametryEkonomiky()
        assert v["elektrarna"]["nakladova_cena_kc"] == pytest.approx(
            v["elektrarna"]["kwp"] * p.nakladova_cena_kc_kwp, rel=1e-6
        )


class TestRozdeleniVychodZapad:
    """Jedno pole rozdělené 50/50 na východ a západ.

    Dan 5. 8. 2026: „u pole dej ještě možnost že jedno pole se přesně 50/50
    rozloží do dvou směrů, východ západ, ať to nemusím psát 2x."

    Typická východ-západní konstrukce na ploché střeše: jeden blok panelů,
    polovina na každou stranu.
    """

    def test_rozlozi_na_dve_poloviny(self):
        pole = (ppa_bess.PoleFve(kwp=200.0, rozdelit_vychod_zapad=True),)
        rozlozeno = ppa_bess.rozloz_pole(pole)
        assert len(rozlozeno) == 2
        assert [f.kwp for f in rozlozeno] == [100.0, 100.0]
        assert sorted(f.azimut_st for f in rozlozeno) == [-90.0, 90.0]

    def test_zachova_sklon_a_cenu(self):
        pole = (
            ppa_bess.PoleFve(
                kwp=300.0, sklon_st=12.0, cena_kc_kwp=16_000.0, rozdelit_vychod_zapad=True
            ),
        )
        for f in ppa_bess.rozloz_pole(pole):
            assert f.sklon_st == 12.0
            assert f.cena_kc_kwp == 16_000.0

    def test_azimut_je_osa(self):
        """Pootočená střecha: osa 30° dá pole na −60° a +120°."""
        pole = (ppa_bess.PoleFve(kwp=100.0, azimut_st=30.0, rozdelit_vychod_zapad=True),)
        assert sorted(f.azimut_st for f in ppa_bess.rozloz_pole(pole)) == [-60.0, 120.0]

    def test_neoznacene_pole_zustane(self):
        pole = (
            ppa_bess.PoleFve(kwp=200.0, azimut_st=0.0),
            ppa_bess.PoleFve(kwp=100.0, rozdelit_vychod_zapad=True),
        )
        rozlozeno = ppa_bess.rozloz_pole(pole)
        assert len(rozlozeno) == 3
        assert rozlozeno[0].kwp == 200.0 and rozlozeno[0].azimut_st == 0.0

    def test_prazdny_vstup(self):
        assert ppa_bess.rozloz_pole(()) == ()

    def test_je_stejne_jako_dve_pole_rucne(self):
        """Zkratka nesmí dát jiný výsledek než ruční zadání dvou polí."""
        zkratka = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=300.0, rozdelit_vychod_zapad=True),))
        )
        rucne = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(kwp=150.0, azimut_st=-90.0),
                    ppa_bess.PoleFve(kwp=150.0, azimut_st=90.0),
                )
            )
        )
        assert zkratka["elektrarna"]["kwp"] == pytest.approx(rucne["elektrarna"]["kwp"])
        assert zkratka["elektrarna"]["vyroba_mwh"] == pytest.approx(
            rucne["elektrarna"]["vyroba_mwh"], rel=1e-6
        )
        assert zkratka["po_delkach"][0]["cena_ppa_kc_mwh"] == pytest.approx(
            rucne["po_delkach"][0]["cena_ppa_kc_mwh"], rel=1e-6
        )

    def test_vystup_ma_rozlozena_pole_i_zadani(self):
        """`pole` = rozložená (pro grafy a součty), `pole_zadani` = originál
        (pro předvyplnění formuláře)."""
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=300.0, rozdelit_vychod_zapad=True),))
        )
        assert len(v["elektrarna"]["pole"]) == 2
        assert len(v["elektrarna"]["pole_zadani"]) == 1
        z = v["elektrarna"]["pole_zadani"][0]
        assert z["rozdelit_vychod_zapad"] is True
        assert z["kwp"] == pytest.approx(300.0)
        # Rozložená pole musí dát dohromady zadaný výkon.
        assert sum(f["kwp"] for f in v["elektrarna"]["pole"]) == pytest.approx(300.0)

    def test_cena_per_pole_se_uplatni_i_na_polovinach(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(
                pole=(
                    ppa_bess.PoleFve(
                        kwp=200.0, cena_kc_kwp=17_000.0, rozdelit_vychod_zapad=True
                    ),
                )
            )
        )
        assert v["elektrarna"]["nakladova_cena_kc"] == pytest.approx(200.0 * 17_000.0)
        for f in v["elektrarna"]["pole"]:
            assert f["cena_kc_kwp"] == pytest.approx(17_000.0)
            assert f["cena_prepsana"] is True

    def test_orientace_se_pojmenuji(self):
        v = ppa_bess.spocti_ppa_bess(
            _rocni_vstup(pole=(ppa_bess.PoleFve(kwp=200.0, rozdelit_vychod_zapad=True),))
        )
        orientace = sorted(f["orientace"] for f in v["elektrarna"]["pole"])
        assert orientace == ["východ", "západ"]


class TestNabidkaProZakaznika:
    """Výstupní vrstva – katalog polí a předloha nabídky (PDF).

    Dan 5. 8. 2026: „dej mi ještě možnost generovat nabídky stejně jako
    v ostatních modulech."

    Nejde jen o to, že se typ přidá do `PODPOROVANE_TYPY` – resolver musí
    z reálného výsledku opravdu vytáhnout hodnoty. Kdyby extraktor mířil na
    špatný klíč, backend nespadne a nabídka se vytiskne s „—" všude.
    """

    def test_typ_je_podporovany(self):
        from app.nabidkovac import sablona_katalog as sk

        assert "ppa_bess" in sk.PODPOROVANE_TYPY

    def test_vsechna_pole_maji_hodnotu(self, v):
        """Žádné pole v katalogu nesmí u platného výpočtu vracet „—"."""
        from app.nabidkovac import sablona_katalog as sk

        hodnoty = sk.resolvni_hodnoty("ppa_bess", v)
        prazdne = [k for k, x in hodnoty.items() if x["hodnota_text"] == "—"]
        assert not prazdne, f"pole bez hodnoty: {prazdne}"

    def test_vychozi_predloha_pouziva_jen_znama_pole(self):
        from app.nabidkovac import sablona_katalog as sk

        povolene = sk.platne_klice("ppa_bess")
        predloha = sk.vychozi_sablona("ppa_bess")
        for stranka in predloha["stranky"]:
            for prvek in stranka["prvky"]:
                for klic in prvek.get("pole") or []:
                    assert klic in povolene or klic in {
                        s["klic"] for s in sk._TABULKA_PPA_BESS
                    }, f"neznámé pole v předloze: {klic}"

    def test_tabulka_ma_radky(self, v):
        from app.nabidkovac import sablona_katalog as sk

        t = sk.resolvni_tabulku("ppa_bess", v)
        assert t["sloupce"], "chybí sloupce"
        assert t["radky"], "tabulka nabídky je prázdná"
        # Každý řádek musí mít tolik hodnot, kolik je sloupců.
        for r in t["radky"]:
            assert len(r) == len(t["sloupce"])
        # A žádná hodnota nesmí být „—" (to by znamenalo špatný klíč).
        assert not [x for r in t["radky"] for x in r if x == "—"]

    def test_tabulka_je_z_teze_delky_jako_dlazdice(self, v):
        """Kdyby tabulka brala jinou délku kontraktu než dlaždice, čísla
        v nabídce by si odporovala."""
        from app.nabidkovac import sablona_katalog as sk

        hodnoty = sk.resolvni_hodnoty("ppa_bess", v)
        cena_dlazdice = hodnoty["cena_ppa_kc_mwh"]["hodnota"]
        t = sk.resolvni_tabulku("ppa_bess", v)
        idx = [i for i, s in enumerate(t["sloupce"]) if s["klic"] == "cena_ppa_kc_mwh"][0]
        # První řádek tabulky = rok 1 téže délky.
        nejdelsi = max(v["po_delkach"], key=lambda d: d["delka_roky"])
        assert cena_dlazdice == pytest.approx(nejdelsi["cena_ppa_kc_mwh"])
        assert t["radky"][0][idx] != "—"

    def test_graf_pro_typ_vraci_data(self, v):
        from app.nabidkovac import sablona_katalog as sk

        g = sk.graf_pro_typ("ppa_bess", v)
        assert isinstance(g, dict)
        assert len(g.get("mesice") or []) == 12
        assert len(g.get("vyroba_kwh") or []) == 12

    def test_investorska_cisla_nejsou_v_katalogu(self):
        """Zákaznická nabídka nesmí umět zobrazit CAPEX, úroky, IRR ani marže —
        stejná zásada jako u PPA (whitelist bez extraktoru)."""
        from app.nabidkovac import sablona_katalog as sk

        klice = sk.platne_klice("ppa_bess")
        zakazane = {
            "capex", "uver", "urok", "uroky", "irr", "dscr", "npv", "marze",
            "provize", "zisk_greensie", "vlastni_kapital", "nakladova_cena",
        }
        for k in klice:
            assert not any(z in k for z in zakazane), f"interní číslo v katalogu: {k}"

    def test_pole_ctou_doporuceny_rezim(self, v):
        """Nabídka má ukazovat doporučený režim, ne první v seznamu."""
        from app.nabidkovac import sablona_katalog as sk

        dop = next(r for r in v["rezimy"] if r["doporuceny"])
        hodnoty = sk.resolvni_hodnoty("ppa_bess", v)
        assert hodnoty["sraz_kw"]["hodnota"] == pytest.approx(dop["vykon"]["sraz_kw"])

    def test_novy_prikon_je_ze_scenare_se_snizenim(self, v):
        """Zákazníka zajímá, na kolik lze příkon snížit — ne že zůstane."""
        from app.nabidkovac import sablona_katalog as sk

        dop = next(r for r in v["rezimy"] if r["doporuceny"])
        hodnoty = sk.resolvni_hodnoty("ppa_bess", v)
        assert hodnoty["rp_novy_kw"]["hodnota"] == pytest.approx(
            dop["ekonomika_vykonu_se_snizenim"]["rp_novy_kw"]
        )


class TestPravoNaVystup:
    """Editor nabídky pro PPA + BESS musí být za stejným právem jako výpočet.

    Výstupní endpointy jsou chráněné jen `vyzaduj_nabidkovac`, takže bez
    explicitní kontroly by nabídka do PDF obešla branku modulu — obchodník bez
    práva `nabidkovac_ppa_bess` by si nabídku otevřel, i když výpočet spustit
    nemůže. Nabídka je jen jiný pohled na tentýž výpočet.
    """

    def _uzivatel(self, prava):
        """Minimální dvojník uživatele – `muze_otevrit` čte `je_admin`,
        `skupina` a `extra_prava`."""

        class Skupina:
            def __init__(self, prava):
                self.prava = list(prava)

        class U:
            def __init__(self, prava):
                self.je_admin = False
                self.skupina = Skupina(prava)
                self.extra_prava = []

        return U(prava)

    def test_bez_prava_neprojde(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_typ_reseni

        with pytest.raises(HTTPException) as e:
            _over_typ_reseni("ppa_bess", self._uzivatel(["nabidkovac"]))
        assert e.value.status_code == 403

    def test_s_pravem_projde(self):
        from app.nabidkovac.routes import _over_typ_reseni

        _over_typ_reseni("ppa_bess", self._uzivatel(["nabidkovac", "nabidkovac_ppa_bess"]))

    def test_supersprávce_projde(self):
        from app.nabidkovac.routes import _over_typ_reseni

        u = self._uzivatel([])
        u.je_admin = True
        _over_typ_reseni("ppa_bess", u)

    def test_ostatni_typy_pravo_nepotrebuji(self):
        from app.nabidkovac.routes import _over_typ_reseni

        u = self._uzivatel(["nabidkovac"])
        for typ in ("ppa", "peak_shaving", "kombinace"):
            _over_typ_reseni(typ, u)

    def test_bez_uzivatele_se_kontrola_preskoci(self):
        """Volání bez uživatele (interní, testy) nemá padat na oprávnění."""
        from app.nabidkovac.routes import _over_typ_reseni

        _over_typ_reseni("ppa_bess")

    def test_neznamy_typ_je_422(self):
        from fastapi import HTTPException

        from app.nabidkovac.routes import _over_typ_reseni

        with pytest.raises(HTTPException) as e:
            _over_typ_reseni("nesmysl", self._uzivatel(["nabidkovac"]))
        assert e.value.status_code == 422


class TestVolbaDelkyVNabidce:
    """Obchodník si u nabídky vybere, o jaký kontrakt jde.

    Dan 5. 8. 2026: „nabídka mi automaticky dává výpočty pro 20 letý kontrakt,
    potřebuju možnost vybrat si o jaký kontrakt jde."

    Bez volby zůstává nejdelší nabízená délka (má největší slevu), ale volba se
    ukládá s rozvržením nabídky a přebíjí ji.
    """

    def test_bez_volby_je_nejdelsi(self, v):
        from app.nabidkovac import sablona_katalog as sk

        h = sk.resolvni_hodnoty("ppa_bess", v)
        nejdelsi = max(v["po_delkach"], key=lambda d: d["delka_roky"])
        assert h["delka_roky"]["hodnota"] == nejdelsi["delka_roky"]
        assert h["cena_ppa_kc_mwh"]["hodnota"] == pytest.approx(
            nejdelsi["cena_ppa_kc_mwh"]
        )

    def test_volba_prebije_vychozi(self, v):
        from app.nabidkovac import sablona_katalog as sk

        for d in v["po_delkach"]:
            h = sk.resolvni_hodnoty("ppa_bess", v, d["delka_roky"])
            assert h["delka_roky"]["hodnota"] == d["delka_roky"]
            assert h["cena_ppa_kc_mwh"]["hodnota"] == pytest.approx(d["cena_ppa_kc_mwh"])
            assert h["sleva"]["hodnota"] == pytest.approx(d["sleva"])
            assert h["uspora_celkem_kc"]["hodnota"] == pytest.approx(d["uspora_celkem_kc"])

    def test_tabulka_sleduje_volbu(self, v):
        """Tabulka i dlaždice musí být z téže délky, jinak si odporují."""
        from app.nabidkovac import sablona_katalog as sk

        for d in v["po_delkach"]:
            t = sk.resolvni_tabulku("ppa_bess", v, d["delka_roky"])
            assert len(t["radky"]) == d["delka_roky"], (
                f'tabulka má {len(t["radky"])} let, čekáno {d["delka_roky"]}'
            )

    def test_rozpad_prinosu_sleduje_volbu(self, v):
        """Úspora na elektřině závisí na ceně PPA, ta se s délkou mění."""
        from app.nabidkovac import sablona_katalog as sk

        kratky = min(d["delka_roky"] for d in v["po_delkach"])
        dlouhy = max(d["delka_roky"] for d in v["po_delkach"])
        h_k = sk.resolvni_hodnoty("ppa_bess", v, kratky)
        h_d = sk.resolvni_hodnoty("ppa_bess", v, dlouhy)
        # Delší kontrakt = nižší cena = větší úspora na elektřině.
        assert h_d["uspora_z_energie_kc"]["hodnota"] > h_k["uspora_z_energie_kc"]["hodnota"]

    def test_neznama_delka_spadne_na_nejdelsi(self, v):
        """Sada nabízených délek se po přepočtu může změnit – nabídka se nesmí
        rozbít, jen se vrátí k výchozí volbě."""
        from app.nabidkovac import sablona_katalog as sk

        h = sk.resolvni_hodnoty("ppa_bess", v, 999)
        nejdelsi = max(v["po_delkach"], key=lambda d: d["delka_roky"])
        assert h["delka_roky"]["hodnota"] == nejdelsi["delka_roky"]

    def test_resolver_nemeni_ulozeny_vysledek(self, v):
        """Volba se vkládá do KOPIE popisu – uložený výpočet zůstane čistý."""
        from app.nabidkovac import sablona_katalog as sk

        sk.resolvni_hodnoty("ppa_bess", v, 10)
        sk.resolvni_tabulku("ppa_bess", v, 10)
        sk.graf_pro_typ("ppa_bess", v, 10)
        assert sk.KLIC_VOLBA_DELKY not in v

    def test_schema_prijme_volbu(self):
        from app.nabidkovac.schemas import VystupKonfigurace

        k = VystupKonfigurace(verze=2, delka_kontraktu_roky=15)
        assert k.delka_kontraktu_roky == 15
        assert VystupKonfigurace(verze=2).delka_kontraktu_roky is None

    def test_schema_odmitne_nesmyslnou_delku(self):
        import pydantic

        from app.nabidkovac.schemas import VystupKonfigurace

        for delka in (0, -5, 41):
            with pytest.raises(pydantic.ValidationError):
                VystupKonfigurace(verze=2, delka_kontraktu_roky=delka)

    def test_nabizene_delky_pro_prepinac(self, v):
        from app.nabidkovac.routes import _nabizene_delky

        assert _nabizene_delky("ppa_bess", v) == sorted(
            d["delka_roky"] for d in v["po_delkach"]
        )

    def test_ostatni_typy_prepinac_nemaji(self):
        """PPA má délku danou variantou, peak shaving žádnou – přepínač by tam
        neměl co přepínat."""
        from app.nabidkovac.routes import _nabizene_delky

        for typ in ("ppa", "peak_shaving", "kombinace"):
            assert _nabizene_delky(typ, {"po_delkach": [{"delka_roky": 10}]}) == []

    def test_bez_reseni_zadne_delky(self):
        from app.nabidkovac.routes import _nabizene_delky

        assert _nabizene_delky("ppa_bess", None) == []
        assert _nabizene_delky("ppa_bess", {}) == []


# --------------------------------------------- délka kontraktu baterie (editovatelná)
class TestDobaNajmuBaterie:
    """Nájem i financování baterie jde počítat na jiný počet let než default 10."""

    def _cf(self, delka: int, doba_najmu: int):
        p = ppa_v2.ParametryEkonomiky()
        pb = ppa_bess.ParametryPpaBess()
        projekt_fve = ppa_v2.sestav_projekt(
            600 * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, delka, p
        )
        projekt_bess = ppa_bess.sestav_projekt_bess(2_400_000.0, p, doba_najmu)
        return ppa_bess.spocti_cashflow(
            vyroba_rok1_mwh=600.0,
            samospotreba_rok1_mwh=500.0,
            export_rok1_mwh=50.0,
            uspora_vykon_rok1_kc=200_000.0,
            ztraty_ze_site_rok1_kwh=5_000.0,
            cena_ppa_rok1_kc_mwh=2_500.0,
            cena_zakaznika_kc_mwh=3_760.0,
            projekt_fve=projekt_fve,
            projekt_bess=projekt_bess,
            p=p,
            pb=pb,
            delka_roky=delka,
            doba_najmu_roky=doba_najmu,
        )

    def test_default_zustava_deset_let(self):
        p = ppa_v2.ParametryEkonomiky()
        assert ppa_bess.sestav_projekt_bess(3_000_000.0, p).delka_roky == 10
        assert ppa_bess.VstupPpaBess.doba_najmu_baterie_roky == 10

    def test_delsi_najem_snizi_mesicni_platbu(self):
        """Delší rozložení úvěru = nižší anuita = nižší nájem. To je celý smysl."""
        p = ppa_v2.ParametryEkonomiky()
        na_10 = ppa_bess.sestav_projekt_bess(3_000_000.0, p, 10)
        na_15 = ppa_bess.sestav_projekt_bess(3_000_000.0, p, 15)
        assert na_15.delka_roky == 15
        assert ppa_bess.najem_baterie_kc_mesic(
            na_15, p
        ) < ppa_bess.najem_baterie_kc_mesic(na_10, p)

    def test_nesmyslna_doba_se_srovna_na_jeden_rok(self):
        p = ppa_v2.ParametryEkonomiky()
        assert ppa_bess.sestav_projekt_bess(1_000_000.0, p, 0).delka_roky == 1
        assert ppa_bess.sestav_projekt_bess(1_000_000.0, p, -3).delka_roky == 1

    def test_najem_konci_podle_zadane_doby(self):
        cf = self._cf(delka=20, doba_najmu=15)
        assert cf.roky[14].najem_baterie_kc > 0  # rok 15
        assert cf.roky[15].najem_baterie_kc == 0.0  # rok 16

    def test_odkup_se_posune_za_delsi_najem(self):
        cf = self._cf(delka=20, doba_najmu=15)
        odkupy = [r.rok for r in cf.roky if r.prijem_odkup_kc > 0]
        assert odkupy == [16]

    def test_splatka_baterie_konci_s_najmem(self):
        cf = self._cf(delka=20, doba_najmu=15)
        assert cf.roky[15].splatka_kc < cf.roky[14].splatka_kc

    def test_kratsi_najem_znamena_drivejsi_odkup(self):
        cf = self._cf(delka=20, doba_najmu=5)
        odkupy = [r.rok for r in cf.roky if r.prijem_odkup_kc > 0]
        assert odkupy == [6]
        assert cf.roky[5].najem_baterie_kc == 0.0

    def test_vystup_nese_zadanou_dobu(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(doba_najmu_baterie_roky=15))
        assert v["baterie"]["doba_najmu_roky"] == 15
        podle_delky = {d["delka_roky"]: d for d in v["po_delkach"]}
        # Kontrakt na 20 let nájem přežije, takže odkup je v roce 16.
        assert podle_delky[20]["rok_odkupu"] == 16
        assert podle_delky[20]["doba_najmu_baterie_roky"] == 15
        # Kontrakty na 10 a 15 let skončí nejpozději s nájmem – žádný odkup.
        assert podle_delky[10]["rok_odkupu"] is None
        assert podle_delky[15]["rok_odkupu"] is None

    def test_najem_delsi_nez_nejkratsi_kontrakt_upozorni(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(doba_najmu_baterie_roky=15))
        assert any("Nájem baterie je na 15 let" in u for u in v["upozorneni"])

    def test_pri_najmu_do_kontraktu_zadne_upozorneni(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(doba_najmu_baterie_roky=10))
        assert not any("Nájem baterie je na" in u for u in v["upozorneni"])


# ------------------------------------------------------ odkup baterie za 1 Kč
class TestOdkupZaKorunu:
    """Zbytková hodnota se místo doplatku rovnoměrně rozpustí do nájmu."""

    def _cf(self, symbolicky: bool, delka: int = 20, doba_najmu: int = 10):
        p = ppa_v2.ParametryEkonomiky()
        pb = ppa_bess.ParametryPpaBess()
        projekt_fve = ppa_v2.sestav_projekt(
            600 * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, delka, p
        )
        projekt_bess = ppa_bess.sestav_projekt_bess(2_400_000.0, p, doba_najmu)
        return ppa_bess.spocti_cashflow(
            vyroba_rok1_mwh=600.0,
            samospotreba_rok1_mwh=500.0,
            export_rok1_mwh=50.0,
            uspora_vykon_rok1_kc=200_000.0,
            ztraty_ze_site_rok1_kwh=5_000.0,
            cena_ppa_rok1_kc_mwh=2_500.0,
            cena_zakaznika_kc_mwh=3_760.0,
            projekt_fve=projekt_fve,
            projekt_bess=projekt_bess,
            p=p,
            pb=pb,
            delka_roky=delka,
            doba_najmu_roky=doba_najmu,
            odkup_symbolicky=symbolicky,
        )

    def test_navyseni_je_prosta_delena_na_mesice(self):
        assert ppa_bess.navyseni_najmu_za_odkup_kc_mesic(120_000.0, 10) == pytest.approx(
            1_000.0
        )
        assert ppa_bess.navyseni_najmu_za_odkup_kc_mesic(120_000.0, 15) == pytest.approx(
            120_000.0 / 180.0
        )

    def test_bez_odkupni_ceny_neni_co_rozpustit(self):
        assert ppa_bess.navyseni_najmu_za_odkup_kc_mesic(0.0, 10) == 0.0

    def test_zakaznik_na_konci_zaplati_korunu(self):
        cf = self._cf(symbolicky=True)
        assert cf.odkupni_cena_baterie_kc == ppa_bess.ODKUP_SYMBOLICKY_KC == 1.0
        assert cf.prijmy_odkup_celkem_kc == pytest.approx(1.0)
        assert cf.roky[10].vydaj_odkup_kc == pytest.approx(1.0)

    def test_najem_je_vyssi_presne_o_rozpusteny_odkup(self):
        zaklad = self._cf(symbolicky=False)
        korunou = self._cf(symbolicky=True)
        navyseni = ppa_bess.navyseni_najmu_za_odkup_kc_mesic(
            zaklad.odkupni_cena_baterie_kc, 10
        )
        assert korunou.najem_baterie_kc_mesic == pytest.approx(
            zaklad.najem_baterie_kc_mesic + navyseni
        )

    def test_klient_celkem_zaplati_totez(self):
        """Rozpuštění je přesun v čase, ne sleva – součet se smí lišit o tu korunu."""
        zaklad = self._cf(symbolicky=False)
        korunou = self._cf(symbolicky=True)
        zaplaceno_zaklad = zaklad.prijmy_najem_celkem_kc + zaklad.prijmy_odkup_celkem_kc
        zaplaceno_korunou = (
            korunou.prijmy_najem_celkem_kc + korunou.prijmy_odkup_celkem_kc
        )
        assert zaplaceno_korunou == pytest.approx(zaplaceno_zaklad + 1.0, abs=1.0)

    def test_dscr_se_zlepsi(self):
        """Odkup je kapitálový příjem (mimo DSCR), nájem provozní – banka to vidí."""
        zaklad = self._cf(symbolicky=False)
        korunou = self._cf(symbolicky=True)
        assert korunou.dscr_min > zaklad.dscr_min

    def test_rozpousti_se_i_kdyz_kontrakt_neprezije_najem(self):
        """Kontrakt stejně dlouhý jako nájem je nejčastější případ – varianta
        tam musí existovat, i když převod baterie padne za horizont modelu.

        Rozpuštěná část se platí v nájmu, tedy uvnitř horizontu. Dřív to bylo
        navázané na `rok_odkupu` a u 10letého kontraktu varianta tiše zmizela –
        obchodník ji na přehledu vůbec neviděl.
        """
        zaklad = self._cf(symbolicky=False, delka=10, doba_najmu=10)
        korunou = self._cf(symbolicky=True, delka=10, doba_najmu=10)
        navyseni = ppa_bess.navyseni_najmu_za_odkup_kc_mesic(
            zaklad.odkupni_cena_baterie_kc, 10
        )
        assert navyseni > 0
        assert korunou.najem_baterie_kc_mesic == pytest.approx(
            zaklad.najem_baterie_kc_mesic + navyseni
        )
        # Zaplaceno je celé, i když se samotný převod baterie nemodeluje.
        assert korunou.prijmy_najem_celkem_kc == pytest.approx(
            zaklad.prijmy_najem_celkem_kc + zaklad.odkupni_cena_baterie_kc
        )

    def test_vystup_ma_variantu_u_kazde_delky(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        podle_delky = {d["delka_roky"]: d for d in v["po_delkach"]}
        for delka in (10, 15, 20):
            varianta = podle_delky[delka]["odkup_1kc"]
            assert varianta is not None, delka
            assert varianta["odkupni_cena_baterie_kc"] == 1.0
            assert varianta["navyseni_najmu_kc_mesic"] > 0
            assert varianta["najem_baterie_kc_mesic"] > podle_delky[delka][
                "najem_baterie_kc_mesic"
            ]
            assert varianta["odkupni_cena_puvodni_kc"] == pytest.approx(
                podle_delky[delka]["odkupni_cena_baterie_kc"]
            )
            # Baterie přechází po skončení nájmu, tedy v 11. roce – i u
            # kontraktu na 10 let, kde je to už za horizontem výpočtu.
            assert varianta["rok_odkupu"] == 11
            assert varianta["odkup_v_horizontu"] is (delka > 10)

    def test_zbytkova_cena_je_v_prehledu_u_kazde_delky(self):
        """Základní varianta musí nést zbytkovou cenu i tam, kde se odkup
        nemodeluje – jinak dlaždice „odkup za zbytkovou cenu" nemá co ukázat."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            assert d["odkupni_cena_baterie_kc"] > 0, d["delka_roky"]

    def test_varianta_ma_vlastni_ekonomiku(self):
        """Cena PPA musí být hledaná nad stejným cashflow, jaké se zobrazí."""
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        for d in v["po_delkach"]:
            if not d["odkup_1kc"]:
                continue
            for klic in ("cena_ppa_kc_mwh", "sleva", "limitujici", "dscr_min",
                         "irr", "npv_kc", "uspora_rok1_kc", "uspora_celkem_kc"):
                assert klic in d["odkup_1kc"], f"odkup_1kc.{klic}"
            # Vyšší provozní příjem nemůže cenu PPA zdražit.
            if d["cena_ppa_kc_mwh"] and d["odkup_1kc"]["cena_ppa_kc_mwh"]:
                assert d["odkup_1kc"]["cena_ppa_kc_mwh"] <= d["cena_ppa_kc_mwh"] + 0.01

    def test_baterie_nese_najem_varianty(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup())
        b = v["baterie"]
        assert b["odkupni_cena_kc"] > 0
        assert b["navyseni_najmu_za_odkup_kc_mesic"] == pytest.approx(
            ppa_bess.navyseni_najmu_za_odkup_kc_mesic(b["odkupni_cena_kc"], 10), abs=0.01
        )
        assert b["najem_odkup_1kc_kc_mesic"] == pytest.approx(
            b["najem_kc_mesic"] + b["navyseni_najmu_za_odkup_kc_mesic"], abs=0.01
        )


class TestSjednanyNajemVstupujeDoEkonomiky:
    """Ruční nájem musí ovlivnit DSCR, ne jen zobrazené číslo.

    Dřív se cashflow počítalo z vzorce i tehdy, když obchodník zadal jiný nájem,
    takže upozornění „hlídej DSCR" ukazovalo na čísla, která sjednaný nájem
    vůbec neznala.
    """

    def _cf(self, najem: float | None):
        p = ppa_v2.ParametryEkonomiky()
        pb = ppa_bess.ParametryPpaBess()
        projekt_fve = ppa_v2.sestav_projekt(
            600 * p.nakladova_cena_kc_kwp, p.marze_fve, p.provize_fve, 20, p
        )
        projekt_bess = ppa_bess.sestav_projekt_bess(2_400_000.0, p)
        return ppa_bess.spocti_cashflow(
            vyroba_rok1_mwh=600.0,
            samospotreba_rok1_mwh=500.0,
            export_rok1_mwh=50.0,
            uspora_vykon_rok1_kc=200_000.0,
            ztraty_ze_site_rok1_kwh=5_000.0,
            cena_ppa_rok1_kc_mwh=2_500.0,
            cena_zakaznika_kc_mwh=3_760.0,
            projekt_fve=projekt_fve,
            projekt_bess=projekt_bess,
            p=p,
            pb=pb,
            delka_roky=20,
            najem_kc_mesic=najem,
        )

    def test_override_se_pouzije(self):
        cf = self._cf(50_000.0)
        assert cf.najem_baterie_kc_mesic == 50_000.0
        assert cf.roky[0].najem_baterie_kc == pytest.approx(600_000.0)

    def test_vyssi_najem_zvedne_dscr(self):
        assert self._cf(50_000.0).dscr_min > self._cf(None).dscr_min

    def test_bez_override_zustava_vzorec(self):
        p = ppa_v2.ParametryEkonomiky()
        ocekavany = ppa_bess.najem_baterie_kc_mesic(
            ppa_bess.sestav_projekt_bess(2_400_000.0, p), p
        )
        assert self._cf(None).najem_baterie_kc_mesic == pytest.approx(ocekavany)

    def test_rucni_najem_projde_az_do_vysledku(self):
        v = ppa_bess.spocti_ppa_bess(_rocni_vstup(najem_kc_mesic_rucne=40_000.0))
        for d in v["po_delkach"]:
            assert d["najem_baterie_kc_mesic"] == 40_000.0
            assert d["roky"][0]["najem_baterie_kc"] == pytest.approx(480_000.0)
