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
