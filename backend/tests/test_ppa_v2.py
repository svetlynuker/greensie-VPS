# -*- coding: utf-8 -*-
"""Testy výpočetního jádra PPA v2 (`app/nabidkovac/ppa_v2.py`).

Klíčová část je **reprodukce `docs/PPA výpočet.xlsx`** – Excel je zdroj pravdy pro
obchodní model (metodika `docs/METODIKA-ppa-v2.md`), takže tyhle testy jsou regresní
pojistka: když se model rozbije, spadnou.

Tolerance: splátkový kalendář v Excelu je poskládaný z ručně zaokrouhlených měsíčních
hodnot, takže kumulovaně za 15 let uteče o ~600 Kč. Kde je to relevantní, testuje se
relativní odchylka, ne rovnost.
"""

from datetime import datetime, timedelta

import pytest

from app.nabidkovac import ppa_v2 as ppa


# ============================================================ reprodukce Excelu: FVE 15 let
class TestExcelCashflowFVE15:
    """List `cashflow FVE (15)`: FVE 300 kWp, 15 let, PPA 2 470 Kč/MWh.

    Vstupy z Excelu: nákladová 13 500 Kč/kWp, marže 1,35, provize 5 %, 20/80,
    7,5 % p.a., výroba rok 1 = 299 MWh, samospotřeba 78 %, export 17 % za
    1 800 Kč/MWh, servis 25 000 Kč/rok, indexace +3 % v letech 4, 7 a 10.

    Cenu za export si tenhle blok zadává **explicitně** – výchozí nastavení appky je
    dnes 0 Kč (za přetoky se neinkasuje nic), takže reprodukce Excelu se nesmí
    spoléhat na default, který se od Excelu záměrně liší.
    """

    KROKY_EXCEL = {4: 0.03, 7: 0.03, 10: 0.03}

    @pytest.fixture
    def p_excel(self):
        return ppa.ParametryEkonomiky(cena_exportu_kc_mwh=ppa.EXCEL_CENA_EXPORTU_KC_MWH)

    @pytest.fixture
    def projekt(self, p_excel):
        return ppa.sestav_projekt(
            nakladova_cena_kc=13_500.0 * 300,
            marze=1.35,
            provize=0.05,
            delka_roky=15,
            p=p_excel,
        )

    def test_capex_a_financovani(self, projekt):
        """Prodejní cena do SPV, provize, zisk Greensie, vlastní kapitál a úvěr."""
        assert projekt.nakladova_cena_kc == pytest.approx(4_050_000.0)
        assert projekt.capex_kc == pytest.approx(5_467_500.0)
        assert projekt.provize_kc == pytest.approx(273_375.0)
        assert projekt.zisk_greensie_kc == pytest.approx(1_144_125.0)
        assert projekt.vlastni_kapital_kc == pytest.approx(1_093_500.0)
        assert projekt.uver_kc == pytest.approx(4_374_000.0)

    def test_anuita(self, projekt):
        """Excel W31 = 40 547,52 Kč/měs – trefit se musí na haléře."""
        assert projekt.splatka_mesicni_kc == pytest.approx(40_547.52, abs=0.01)

    def test_prvni_urok_odpovida_sazbe(self, projekt):
        """Excel X31 = 27 337,50 Kč = 4 374 000 × 7,5 % / 12."""
        assert projekt.uver_kc * 0.075 / 12 == pytest.approx(27_337.50, abs=0.01)

    @pytest.fixture
    def cf(self, projekt, p_excel):
        return ppa.spocti_cashflow(
            vyroba_rok1_mwh=299.0,
            podil_samospotreby=0.78,
            podil_sdileni=0.17,
            cena_ppa_rok1_kc_mwh=2_470.0,
            projekt=projekt,
            p=p_excel,
            indexacni_kroky_rucne=self.KROKY_EXCEL,
        )

    def test_rok1(self, cf):
        """Excel: prodej zákazník 576 053,40; sdílení 91 494; zdroje 642 547,40."""
        r = cf.roky[0]
        assert r.vyroba_mwh == pytest.approx(299.0)
        assert r.prodej_zakaznik_kc == pytest.approx(576_053.40, rel=1e-6)
        assert r.prodej_sdileni_kc == pytest.approx(91_494.0, rel=1e-6)
        assert r.zdroje_kc == pytest.approx(642_547.40, rel=1e-6)
        assert r.dscr == pytest.approx(1.32058, abs=1e-4)

    def test_degradace(self, cf):
        """Excel G5 = F5 × 0,995 → rok 2 = 297,505 MWh."""
        assert cf.roky[1].vyroba_mwh == pytest.approx(297.505, rel=1e-9)

    def test_skokova_indexace(self, cf):
        """Cena drží 3 roky plochá a pak skočí o 3 % (Excel roky 4, 7, 10)."""
        ceny = [r.cena_ppa_kc_mwh for r in cf.roky]
        assert ceny[0] == ceny[1] == ceny[2] == pytest.approx(2_470.0)
        assert ceny[3] == ceny[4] == ceny[5] == pytest.approx(2_544.10)
        assert ceny[6] == pytest.approx(2_620.423)
        assert ceny[9] == pytest.approx(2_699.03569)
        # roky 13–15 už Excel neindexuje (hodnota skoku nevyplněná)
        assert ceny[14] == pytest.approx(2_699.03569)

    def test_dscr_rozsah(self, cf):
        """Excel DSCR jde od 1,3069 (rok 3) do 1,3817 (rok 10)."""
        dscr = [r.dscr for r in cf.roky]
        assert min(dscr) == pytest.approx(1.30690, abs=1e-4)
        assert max(dscr) == pytest.approx(1.38167, abs=1e-4)

    def test_zisk_po_splatkach_rok1(self, cf):
        """Excel F17 = 155 983 Kč (naše 155 977 – Excel má zaokrouhlenou anuitu)."""
        assert cf.roky[0].zisk_po_splatkach_kc == pytest.approx(155_983.40, abs=10.0)

    def test_irr_vlastnich_zdroju(self, cf):
        """Excel E20 = IRR(E19:T19) = 12,4252 %. Tohle je headline číslo modelu."""
        assert cf.irr == pytest.approx(0.124252, abs=2e-5)

    def test_cf_zacina_vlastnim_kapitalem(self, cf):
        """Excel E19 = −D24 = −1 093 500 (investice vlastního kapitálu v roce 0)."""
        assert cf.cf_vlastniho_kapitalu[0] == pytest.approx(-1_093_500.0)
        assert len(cf.cf_vlastniho_kapitalu) == 16


# ============================================================ reprodukce Excelu: odkupní tabulka
class TestExcelOdkupniTabulka:
    """List `odkupní tabulka (15)`: odkupní cena a zisk SPV po roce t."""

    @pytest.fixture
    def tabulka(self):
        p = ppa.ParametryEkonomiky()  # poplatek 0,5 %, předčasné splacení 5 %
        projekt = ppa.sestav_projekt(13_500.0 * 300, 1.35, 0.05, 15, p)
        return ppa.odkupni_tabulka(projekt, p)

    @pytest.mark.parametrize(
        "rok, excel_odkup",
        [(1, 5_289_189.98), (2, 5_094_455.61), (3, 4_882_560.65), (4, 4_652_172.89), (5, 4_401_856.67)],
    )
    def test_odkupni_cena(self, tabulka, rok, excel_odkup):
        """Zůstatek fiktivního úvěru na 100 % CAPEX + kumulativní poplatek 0,5 %/rok."""
        assert tabulka[rok - 1].odkupni_cena_kc == pytest.approx(excel_odkup, rel=3e-4)

    def test_zustatek_realneho_uveru_rok1(self, tabulka):
        """Excel E35 = 4 209 915,48 (zůstatek 80% úvěru po 12 splátkách)."""
        assert tabulka[0].zustatek_uveru_kc == pytest.approx(4_209_915.48, rel=3e-4)

    def test_zisk_spv_rok1(self, tabulka):
        """Excel E41 = 868 779 Kč."""
        assert tabulka[0].zisk_spv_kc == pytest.approx(868_778.72, rel=1e-3)

    def test_na_konci_kontraktu_je_nula(self, tabulka):
        """Po odsplacení celého úvěru zbývá jen kumulovaný poplatek."""
        assert tabulka[-1].zustatek_uveru_kc == pytest.approx(0.0, abs=1.0)
        assert tabulka[-1].odkupni_cena_kc == pytest.approx(394_715.67, rel=1e-3)

    def test_cena_klesa(self, tabulka):
        """Odkupní cena musí rok po roce klesat (technologie se umořuje)."""
        ceny = [t.odkupni_cena_kc for t in tabulka]
        assert all(a > b for a, b in zip(ceny, ceny[1:]))


# ============================================================ reprodukce Excelu: pronájem BESS
class TestExcelPronajemBESS:
    """List `pronájem BESS (10)`: baterie 100/200 za 800 000 Kč, 10 let."""

    @pytest.fixture
    def p(self):
        return ppa.ParametryEkonomiky()

    @pytest.fixture
    def projekt(self, p):
        return ppa.sestav_projekt(800_000.0, marze=1.47, provize=0.04, delka_roky=10, p=p)

    def test_capex_a_provize(self, projekt):
        """Excel E37 = 1 176 000; F37 = 47 040; vlastní kapitál 235 200."""
        assert projekt.capex_kc == pytest.approx(1_176_000.0)
        assert projekt.provize_kc == pytest.approx(47_040.0)
        assert projekt.vlastni_kapital_kc == pytest.approx(235_200.0)
        assert projekt.zisk_greensie_kc == pytest.approx(328_960.0)

    def test_splatka(self, projekt):
        """Excel B13 = 11 158 Kč/měs (940 800 Kč na 120 měsíců, 7,5 %).

        Pozor: 11 158 je v Excelu **ručně vepsaná** hodnota (žlutá buňka), ne
        formule – přesná anuita je 11 167,46 Kč. Odchylka 0,08 % je tím pádem
        vlastnost Excelu, ne chyba výpočtu.
        """
        assert projekt.splatka_mesicni_kc == pytest.approx(11_158.0, rel=1e-3)

    def test_najem_mesicni(self, projekt, p):
        """Excel D25 = marže 4 500 + splátka 11 158 + EMS 1 300 = 16 958 Kč/měs."""
        najem = ppa._najem_baterie_kc_mesic(projekt, p)
        assert najem == pytest.approx(16_958.0, rel=1e-3)

    def test_zdroje_a_dscr(self, projekt, p):
        """Excel: nájem 203 496 − EMS 15 600 − servis 12 000 = 175 896; DSCR 1,3137."""
        najem_rocni = ppa._najem_baterie_kc_mesic(projekt, p) * 12
        naklady = p.bess_ems_kc_mesic * 12 + p.bess_servis_kc_rok
        assert najem_rocni == pytest.approx(203_496.0, rel=1e-3)
        assert najem_rocni - naklady == pytest.approx(175_896.0, rel=1e-3)
        assert (najem_rocni - naklady) / projekt.splatka_rocni_kc == pytest.approx(1.31368, rel=2e-3)

    def test_zisk_po_splatkach_je_marze_minus_servis(self, projekt, p):
        """Excel E16 = 42 000 Kč/rok = marže 4 500 × 12 − servis 12 000.

        Nájem pokrývá splátku i EMS jedna ku jedné, takže SPV zůstává čistě marže
        minus servis – nezávisle na velikosti baterie.
        """
        najem_rocni = ppa._najem_baterie_kc_mesic(projekt, p) * 12
        naklady = p.bess_ems_kc_mesic * 12 + p.bess_servis_kc_rok
        zisk = najem_rocni - naklady - projekt.splatka_rocni_kc
        assert zisk == pytest.approx(42_000.0, abs=1.0)

    def test_irr(self, projekt, p):
        """Excel D19 = 12,2187 %."""
        cf = [-projekt.vlastni_kapital_kc] + [42_000.0] * 10
        assert ppa.irr(cf) == pytest.approx(0.122187, abs=1e-4)


# ============================================================ financování – vlastnosti
class TestFinancovani:
    def test_anuita_odsplati_uver(self):
        """Po n splátkách musí být zůstatek nulový (jinak model tiše lže)."""
        assert ppa.zustatek_uveru(1_000_000, 0.075, 10, 120) == pytest.approx(0.0, abs=1e-6)

    def test_zustatek_klesa_monotonne(self):
        z = [ppa.zustatek_uveru(1_000_000, 0.075, 10, m) for m in range(0, 121, 12)]
        assert all(a > b for a, b in zip(z, z[1:]))

    def test_nulova_sazba_je_linearni(self):
        """Bez úroku je splátka jen podíl – ochrana proti dělení nulou."""
        assert ppa.anuita_mesicni(120_000, 0.0, 10) == pytest.approx(1_000.0)
        assert ppa.zustatek_uveru(120_000, 0.0, 10, 60) == pytest.approx(60_000.0)

    def test_delsi_splatnost_znamena_nizsi_splatku(self):
        """Jádro fáze C: delší kontrakt → nižší splátka → nižší potřebná cena PPA."""
        assert ppa.anuita_mesicni(1_000_000, 0.075, 20) < ppa.anuita_mesicni(1_000_000, 0.075, 10)

    def test_irr_bez_zmeny_znamenka_je_none(self):
        assert ppa.irr([100.0, 100.0]) is None
        assert ppa.irr([-100.0]) is None


# ============================================================ indexace
class TestIndexace:
    def test_periodicka_drzi_tri_roky(self):
        ceny = ppa.ceny_po_letech(1000.0, 10, krok=0.03, perioda_roky=3)
        assert ceny[:3] == pytest.approx([1000.0, 1000.0, 1000.0])
        assert ceny[3] == pytest.approx(1030.0)
        assert ceny[9] == pytest.approx(1000.0 * 1.03**3)

    def test_rucni_kroky_prebiji_periodu(self):
        ceny = ppa.ceny_po_letech(1000.0, 5, kroky_rucne={3: 0.10})
        assert ceny == pytest.approx([1000.0, 1000.0, 1100.0, 1100.0, 1100.0])

    def test_nulovy_krok_je_plocha_cena(self):
        assert ppa.ceny_po_letech(1000.0, 5, krok=0.0) == pytest.approx([1000.0] * 5)


# ============================================================ baterie
def _profil_vecerni_spotreba(dny: int = 30):
    """Profil s odběrem výhradně večer – bez baterie nelze samospotřebu zvýšit."""
    casy, spotreba = [], []
    t = datetime(2026, 6, 1)
    for d in range(dny):
        for i in range(96):
            c = t + timedelta(days=d, minutes=15 * i)
            casy.append(c)
            spotreba.append(10.0 if c.hour >= 19 or c.hour < 5 else 1.0)
    return casy, spotreba


class TestBaterie:
    def test_bez_baterie_je_shodne_se_sparuj(self):
        vyroba = [5.0, 0.0, 3.0]
        spotreba = [1.0, 2.0, 4.0]
        a = ppa.sparuj_s_baterii(vyroba, spotreba, None, None, 0.25)
        from app.nabidkovac.ppa_fve import sparuj

        b = sparuj(vyroba, spotreba, None, 0.25)
        assert (a.samospotreba_kwh, a.export_kwh, a.dokup_kwh) == (
            b.samospotreba_kwh,
            b.export_kwh,
            b.dokup_kwh,
        )

    def test_baterie_zvysi_samospotrebu(self):
        """Přebytek v den se uloží a večer vydá → SS roste, export klesá."""
        vyroba = [10.0] + [0.0] * 5
        spotreba = [0.0] + [2.0] * 5
        bez = ppa.sparuj_s_baterii(vyroba, spotreba, None, None, 1.0)
        s = ppa.sparuj_s_baterii(
            vyroba, spotreba, ppa.Baterie(kapacita_kwh=10.0, vykon_kw=10.0, dod=1.0), None, 1.0
        )
        assert s.samospotreba_kwh > bez.samospotreba_kwh
        assert s.export_kwh < bez.export_kwh

    def test_energie_se_neztraci_ani_netvori(self):
        """Bilance: výroba = samospotřeba + export + ořez + ztráty baterie (≥ 0)."""
        vyroba = [10.0, 8.0, 0.0, 0.0]
        spotreba = [1.0, 1.0, 6.0, 6.0]
        b = ppa.sparuj_s_baterii(
            vyroba, spotreba, ppa.Baterie(10.0, 10.0, ucinnost_round_trip=0.9), None, 1.0
        )
        ztraty = b.vyroba_kwh - b.samospotreba_kwh - b.export_kwh - b.orez_kwh
        assert ztraty >= -1e-9
        assert b.samospotreba_kwh <= b.spotreba_kwh + 1e-9

    def test_ucinnost_snizuje_ziskanou_energii(self):
        vyroba, spotreba = [10.0, 0.0], [0.0, 10.0]
        b90 = ppa.sparuj_s_baterii(vyroba, spotreba, ppa.Baterie(10.0, 10.0, 0.9, dod=1.0), None, 1.0)
        b100 = ppa.sparuj_s_baterii(vyroba, spotreba, ppa.Baterie(10.0, 10.0, 1.0, dod=1.0), None, 1.0)
        assert b90.samospotreba_kwh < b100.samospotreba_kwh

    def test_navrh_baterie_z_prebytku(self):
        casy, spotreba = _profil_vecerni_spotreba(10)
        vyroba = [8.0 if 8 <= c.hour < 16 else 0.0 for c in casy]
        b = ppa.navrhni_baterii(vyroba, spotreba, casy)
        assert b.kapacita_kwh > 0
        assert b.vykon_kw == pytest.approx(b.kapacita_kwh * ppa.VYCHOZI_C_RATE, rel=0.02)


# ============================================================ měsíční graf
class TestGrafMesicni:
    """Data pro `GrafVyrobaSpotreba.jsx` (metodika kap. 6.1)."""

    @pytest.fixture
    def graf(self):
        casy, spotreba = _profil_vecerni_spotreba(40)
        vyroba = ppa.simuluj_vyrobu(casy, 50.0, 49.8, 35.0, 0.0)
        return ppa.graf_mesicni(casy, vyroba, spotreba, None, None, 0.25), casy, vyroba, spotreba

    def test_ma_vsechny_serie_a_12_mesicu(self, graf):
        g = graf[0]
        assert g["mesice"] == list(range(1, 13))
        for klic in ("spotreba_kwh", "vyroba_kwh", "samospotreba_kwh", "export_kwh", "orez_kwh", "dokup_kwh"):
            assert len(g[klic]) == 12, klic

    def test_soucty_odpovidaji_rocni_bilanci(self, graf):
        """Graf a roční bilance musí říkat totéž – jinak by nabídka lhala v grafu."""
        g, casy, vyroba, spotreba = graf
        b = ppa.sparuj_s_baterii(vyroba, spotreba, None, None, 0.25)
        assert sum(g["vyroba_kwh"]) == pytest.approx(b.vyroba_kwh, rel=1e-6)
        assert sum(g["spotreba_kwh"]) == pytest.approx(b.spotreba_kwh, rel=1e-6)
        assert sum(g["samospotreba_kwh"]) == pytest.approx(b.samospotreba_kwh, rel=1e-6)
        assert sum(g["export_kwh"]) == pytest.approx(b.export_kwh, rel=1e-6)
        assert sum(g["dokup_kwh"]) == pytest.approx(b.dokup_kwh, rel=1e-6)

    def test_skladba_sloupcu_vychazi(self, graf):
        """Spotřeba = samospotřeba + dokup; výroba = samospotřeba + přetok + ořez."""
        g = graf[0]
        for i in range(12):
            assert g["spotreba_kwh"][i] == pytest.approx(
                g["samospotreba_kwh"][i] + g["dokup_kwh"][i], abs=0.05
            )
            assert g["vyroba_kwh"][i] == pytest.approx(
                g["samospotreba_kwh"][i] + g["export_kwh"][i] + g["orez_kwh"][i], abs=0.05
            )

    def test_s_baterii_je_samospotreba_vyssi(self):
        casy, spotreba = _profil_vecerni_spotreba(40)
        vyroba = ppa.simuluj_vyrobu(casy, 50.0, 49.8, 35.0, 0.0)
        bez = ppa.graf_mesicni(casy, vyroba, spotreba, None, None, 0.25)
        s = ppa.graf_mesicni(
            casy, vyroba, spotreba, ppa.Baterie(100.0, 50.0), None, 0.25
        )
        assert sum(s["samospotreba_kwh"]) > sum(bez["samospotreba_kwh"])

    def test_toky_energie_sedi_s_bilanci_i_s_baterii(self):
        """Generátor toků je jediný zdroj dispatchu – musí dát stejný součet."""
        casy, spotreba = _profil_vecerni_spotreba(15)
        vyroba = ppa.simuluj_vyrobu(casy, 60.0, 49.8, 35.0, 0.0)
        bat = ppa.Baterie(120.0, 60.0)
        b = ppa.sparuj_s_baterii(vyroba, spotreba, bat, 40.0, 0.25)
        ss = ex = orz = dk = 0.0
        for t in ppa.toky_energie(vyroba, spotreba, bat, 40.0, 0.25):
            ss += t.samospotreba; ex += t.export; orz += t.orez; dk += t.dokup
        assert ss == pytest.approx(b.samospotreba_kwh, rel=1e-9)
        assert ex == pytest.approx(b.export_kwh, rel=1e-9)
        assert orz == pytest.approx(b.orez_kwh, rel=1e-9)
        assert dk == pytest.approx(b.dokup_kwh, rel=1e-9)


# ============================================================ 15min průběh (nitkový graf)
class TestPrubeh15min:
    """Řady pro `GrafPrubehuPpa.jsx` – v kW, ze stejné fyziky jako ekonomika."""

    @pytest.fixture
    def zaklad(self):
        casy, spotreba = _profil_vecerni_spotreba(20)
        vyroba = ppa.simuluj_vyrobu(casy, 60.0, 49.8, 35.0, 0.0)
        return casy, vyroba, spotreba

    def test_delky_rad_odpovidaji_profilu(self, zaklad):
        casy, vyroba, spotreba = zaklad
        p = ppa.prubeh_15min(vyroba, spotreba, None, None, 0.25)
        for klic in ("spotreba_kw", "vyroba_kw", "samospotreba_kw", "pretok_kw", "orez_kw", "dokup_kw"):
            assert len(p[klic]) == len(casy), klic

    def test_soucty_odpovidaji_rocni_bilanci(self, zaklad):
        """Graf a tabulky musí říkat totéž – kW × interval zpátky na kWh."""
        casy, vyroba, spotreba = zaklad
        p = ppa.prubeh_15min(vyroba, spotreba, None, None, 0.25)
        b = ppa.sparuj_s_baterii(vyroba, spotreba, None, None, 0.25)
        assert sum(p["spotreba_kw"]) * 0.25 == pytest.approx(b.spotreba_kwh, rel=1e-4)
        assert sum(p["vyroba_kw"]) * 0.25 == pytest.approx(b.vyroba_kwh, rel=1e-4)
        assert sum(p["samospotreba_kw"]) * 0.25 == pytest.approx(b.samospotreba_kwh, rel=1e-4)
        assert sum(p["pretok_kw"]) * 0.25 == pytest.approx(b.export_kwh, rel=1e-4)
        assert sum(p["dokup_kw"]) * 0.25 == pytest.approx(b.dokup_kwh, rel=1e-4)

    def test_bez_baterie_neni_soc(self, zaklad):
        casy, vyroba, spotreba = zaklad
        assert ppa.prubeh_15min(vyroba, spotreba, None, None, 0.25)["soc_pct"] is None

    def test_s_baterii_je_soc_v_procentech(self, zaklad):
        casy, vyroba, spotreba = zaklad
        p = ppa.prubeh_15min(vyroba, spotreba, ppa.Baterie(120.0, 60.0), None, 0.25)
        assert p["soc_pct"] is not None
        assert len(p["soc_pct"]) == len(casy)
        assert all(0.0 <= x <= 100.5 for x in p["soc_pct"])
        assert max(p["soc_pct"]) > 0  # baterie se opravdu nabíjí

    def test_rezervovany_vykon_strope_pretok(self, zaklad):
        """Přetok nesmí přelézt rezervovaný výkon dodávky – zbytek je ořez."""
        casy, vyroba, spotreba = zaklad
        strop = 10.0
        p = ppa.prubeh_15min(vyroba, spotreba, None, strop, 0.25)
        assert max(p["pretok_kw"]) <= strop + 1e-6
        assert sum(p["orez_kw"]) > 0

    def test_samospotreba_nikdy_nad_vyrobu_ani_spotrebu(self, zaklad):
        casy, vyroba, spotreba = zaklad
        p = ppa.prubeh_15min(vyroba, spotreba, ppa.Baterie(120.0, 60.0), None, 0.25)
        for ss, v, s in zip(p["samospotreba_kw"], p["vyroba_kw"], p["spotreba_kw"]):
            assert ss <= s + 0.02
            # s baterií může samospotřeba v daném intervalu přesáhnout okamžitou
            # výrobu (vybíjí se dřív uložená energie) – proto jen proti spotřebě.
        assert sum(p["samospotreba_kw"]) <= sum(p["vyroba_kw"]) + 1e-6

    def test_souhrn_ma_maxima(self, zaklad):
        casy, vyroba, spotreba = zaklad
        s = ppa.prubeh_15min(vyroba, spotreba, None, None, 0.25)["souhrn"]
        assert s["max_spotreba_kw"] > 0
        assert s["max_vyroba_kw"] > 0


# ============================================================ velikost FVE
class TestNavrhKwp:
    def test_mira_samospotreby_klesa_s_velikosti(self):
        """Předpoklad binárního hledání – kdyby neplatil, sizing je nesmysl."""
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        miry = [
            ppa._mira_samospotreby(v1, spotreba, kwp, None, None, 0.25) for kwp in (5, 20, 50, 200)
        ]
        assert all(a >= b for a, b in zip(miry, miry[1:]))

    def test_cil_je_dodrzen(self):
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        kwp = ppa.navrhni_kwp_na_cil(v1, spotreba, cil_mira_samospotreby=0.80)
        assert kwp > 0
        assert ppa._mira_samospotreby(v1, spotreba, kwp, None, None, 0.25) >= 0.80 - 0.02

    def test_max_kwp_se_respektuje(self):
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        assert ppa.navrhni_kwp_na_cil(v1, spotreba, 0.80, max_kwp=3.0) <= 3.0

    @pytest.mark.parametrize("strop", [3.5, 10.2, 35.5, 99.9, 128.7])
    def test_neceločíselný_strop_se_nepřekročí(self, strop):
        """Zaokrouhlení na celé kWp nesmí přelézt strop – střecha na 35,5 kWp
        nesmí vyjít jako 36 kWp (nalezeno testem, oprava v `na_cele_kwp`)."""
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        assert ppa.navrhni_kwp_na_cil(v1, spotreba, 0.80, max_kwp=strop) <= strop

    def test_strop_pod_1_kwp(self):
        """Strop pod 1 kWp = nedá se postavit; nesmí se zaokrouhlit na 1."""
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        assert ppa.navrhni_kwp_na_cil(v1, spotreba, 0.80, max_kwp=0.4) == 0.0

    def test_baterie_umozni_vetsi_fve(self):
        """Se stejným cílem samospotřeby musí baterie povolit větší elektrárnu."""
        casy, spotreba = _profil_vecerni_spotreba(20)
        v1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35.0, 0.0)
        bez = ppa.navrhni_kwp_na_cil(v1, spotreba, 0.80)
        s = ppa.navrhni_kwp_na_cil(
            v1, spotreba, 0.80, baterie=ppa.Baterie(kapacita_kwh=200.0, vykon_kw=100.0)
        )
        assert s > bez


# ============================================================ inverzní úloha
class TestMinimalniCena:
    @pytest.fixture
    def projekt(self):
        return ppa.sestav_projekt(13_500.0 * 300, 1.35, 0.05, 15, ppa.ParametryEkonomiky())

    def test_cena_z_dscr_da_presne_cilovy_dscr(self, projekt):
        """Analytické řešení musí sedět: při té ceně je min. DSCR přesně dscr_min."""
        p = ppa.ParametryEkonomiky()
        cena = ppa.cena_ppa_z_dscr(299.0, 0.78, 0.17, projekt, p)
        cf = ppa.spocti_cashflow(299.0, 0.78, 0.17, cena, projekt, p)
        assert cf.dscr_min == pytest.approx(p.dscr_min, abs=1e-6)

    def test_cena_z_irr_da_presne_cilove_irr(self, projekt):
        p = ppa.ParametryEkonomiky()
        cena = ppa.cena_ppa_z_irr(299.0, 0.78, 0.17, projekt, p)
        cf = ppa.spocti_cashflow(299.0, 0.78, 0.17, cena, projekt, p)
        assert cf.irr == pytest.approx(p.irr_cil, abs=1e-4)

    def test_minimalni_cena_splni_obe_podminky(self, projekt):
        p = ppa.ParametryEkonomiky()
        minc = ppa.minimalni_cena_ppa(299.0, 0.78, 0.17, projekt, p)
        cf = ppa.spocti_cashflow(299.0, 0.78, 0.17, minc.cena_kc_mwh, projekt, p)
        assert cf.dscr_min >= p.dscr_min - 1e-6
        assert cf.irr >= p.irr_cil - 1e-6
        assert minc.limitujici in ("dscr", "irr")

    def test_delsi_kontrakt_znamena_nizsi_cenu(self):
        """Jádro fáze C – bez téhle monotonie by výběr délky nedával smysl."""
        p = ppa.ParametryEkonomiky()
        ceny = []
        for n in (10, 15, 20):
            projekt = ppa.sestav_projekt(13_500.0 * 300, 1.35, 0.05, n, p)
            ceny.append(ppa.minimalni_cena_ppa(299.0, 0.78, 0.17, projekt, p).cena_kc_mwh)
        assert all(a > b for a, b in zip(ceny, ceny[1:]))

    def test_export_snizuje_potrebnou_cenu(self, projekt):
        """Druhý výnosový tok musí cenu pro zákazníka stlačit."""
        p = ppa.ParametryEkonomiky(cena_exportu_kc_mwh=1_800.0)
        bez = ppa.minimalni_cena_ppa(299.0, 0.78, 0.0, projekt, p).cena_kc_mwh
        se = ppa.minimalni_cena_ppa(299.0, 0.78, 0.17, projekt, p).cena_kc_mwh
        assert se < bez

    def test_nulova_cena_exportu_nic_nesnizi(self, projekt):
        """Výchozí nastavení: za přetoky se neinkasuje nic, takže je cena stejná,
        jako by přebytek vůbec nebyl."""
        p = ppa.ParametryEkonomiky()
        assert p.cena_exportu_kc_mwh == 0.0
        bez = ppa.minimalni_cena_ppa(299.0, 0.78, 0.0, projekt, p).cena_kc_mwh
        se = ppa.minimalni_cena_ppa(299.0, 0.78, 0.17, projekt, p).cena_kc_mwh
        assert se == pytest.approx(bez)

    def test_vyssi_cena_exportu_snizuje_cenu_ppa(self, projekt):
        """Čím lépe se přebytek zpeněží, tím nižší cenu zákazník potřebuje."""
        ceny = [
            ppa.minimalni_cena_ppa(
                299.0, 0.78, 0.17, projekt, ppa.ParametryEkonomiky(cena_exportu_kc_mwh=c)
            ).cena_kc_mwh
            for c in (0.0, 900.0, 1_800.0, 2_700.0)
        ]
        assert all(a > b for a, b in zip(ceny, ceny[1:]))


# ============================================================ orchestrace
def _profil_denni_spotreba(dny: int = 60):
    """Denní odběr (výroba a spotřeba se potkávají) – realistický PPA případ."""
    casy, spotreba = [], []
    t = datetime(2026, 1, 1)
    for d in range(dny):
        for i in range(96):
            c = t + timedelta(days=d * 6, minutes=15 * i)
            casy.append(c)
            spotreba.append(30.0 if 7 <= c.hour < 18 else 5.0)
    return casy, spotreba


class TestSpoctiPpa2:
    @pytest.fixture
    def vstup(self):
        casy, spotreba = _profil_denni_spotreba()
        return ppa.VstupPPA2(
            casy=casy,
            spotreba_kwh=spotreba,
            cena_silova_kc_mwh=3_500.0,
            s_baterii=False,
        )

    @staticmethod
    def _delka(v, roky, blok="bez_baterie"):
        """Varianta pro konkrétní délku kontraktu."""
        return next(x for x in v[blok]["po_delkach"] if x["delka_kontraktu_roky"] == roky)

    def test_nabizi_10_15_20_let_a_nedoporucuje(self, vstup):
        """Rozhodnuto: výpočet nabídne tři délky a výběr nechá na obchodníkovi."""
        v = ppa.spocti_ppa2(vstup)
        assert [x["delka_kontraktu_roky"] for x in v["bez_baterie"]["po_delkach"]] == [10, 15, 20]
        assert "doporucena" not in v

    def test_kazda_delka_ma_headline_cisla(self, vstup):
        """Zadání: velikost FVE, cena za kWh a délka kontraktu."""
        v = ppa.spocti_ppa2(vstup)
        assert v["bez_baterie"]["kwp"] > 0
        for x in v["bez_baterie"]["po_delkach"]:
            assert x["cena_ppa_kc_kwh"] > 0
            assert x["kwp"] == v["bez_baterie"]["kwp"]

    def test_delsi_kontrakt_je_pro_zakaznika_levnejsi(self, vstup):
        """Nižší splátka → nižší cena → větší sleva. Tohle obchodník potřebuje vidět."""
        v = ppa.spocti_ppa2(vstup)
        ceny = [x["cena_ppa_kc_mwh"] for x in v["bez_baterie"]["po_delkach"]]
        slevy = [x["sleva_zakaznikovi"] for x in v["bez_baterie"]["po_delkach"]]
        assert all(a > b for a, b in zip(ceny, ceny[1:]))
        assert all(a < b for a, b in zip(slevy, slevy[1:]))

    def test_cil_samospotreby_se_drzi(self, vstup):
        v = ppa.spocti_ppa2(vstup)
        for x in v["bez_baterie"]["po_delkach"]:
            assert x["energie"]["mira_samospotreby"] >= vstup.cil_mira_samospotreby - 0.02

    def test_nizsi_cil_da_vetsi_elektrarnu(self, vstup):
        """Cíl 60 % připouští víc přebytku → větší FVE než cíl 90 %."""
        vstup.cil_mira_samospotreby = 0.60
        velka = ppa.spocti_ppa2(vstup)["bez_baterie"]["kwp"]
        vstup.cil_mira_samospotreby = 0.90
        mala = ppa.spocti_ppa2(vstup)["bez_baterie"]["kwp"]
        assert velka > mala

    def test_dscr_a_irr_jsou_splnene(self, vstup):
        """Cena musí projít bankou i investorem – v každé nabízené délce."""
        v = ppa.spocti_ppa2(vstup)
        for x in v["bez_baterie"]["po_delkach"]:
            assert x["vysledek_investora"]["dscr_min"] >= vstup.parametry.dscr_min - 1e-3
            assert x["vysledek_investora"]["irr"] >= vstup.parametry.irr_cil - 1e-3

    def test_dscr_a_irr_jde_zadat_v_nastaveni(self, vstup):
        """Rozhodnuto: DSCR i IRR jsou manažerské nastavení, ne konstanty v kódu."""
        vstup.parametry = ppa.ParametryEkonomiky(dscr_min=1.45, irr_cil=0.18)
        v = ppa.spocti_ppa2(vstup)
        assert v["vstup"]["dscr_min"] == 1.45
        assert v["vstup"]["irr_cil"] == 0.18
        for x in v["bez_baterie"]["po_delkach"]:
            assert x["vysledek_investora"]["dscr_min"] >= 1.45 - 1e-3
            assert x["vysledek_investora"]["irr"] >= 0.18 - 1e-3

    def test_tvrdsi_pozadavky_zdrazi_cenu(self, vstup):
        """Vyšší DSCR/IRR musí cenu pro zákazníka zvednout, ne snížit."""
        mirne = self._delka(ppa.spocti_ppa2(vstup), 15)["cena_ppa_kc_mwh"]
        vstup.parametry = ppa.ParametryEkonomiky(dscr_min=1.45, irr_cil=0.18)
        tvrde = self._delka(ppa.spocti_ppa2(vstup), 15)["cena_ppa_kc_mwh"]
        assert tvrde > mirne

    def test_odkupni_tabulka_ma_radek_na_kazdy_rok(self, vstup):
        v = ppa.spocti_ppa2(vstup)
        for x in v["bez_baterie"]["po_delkach"]:
            assert len(x["odkupni_tabulka"]) == x["delka_kontraktu_roky"]

    def test_vyhnutelna_cena_je_silova_plus_regulovane(self, vstup):
        """Rozhodnuto: PPA nahrazuje silovou složku + část regulovaných."""
        vstup.vyhnutelne_regulovane_kc_mwh = 260.0
        v = ppa.spocti_ppa2(vstup)
        assert v["vstup"]["cena_vyhnutelna_kc_mwh"] == pytest.approx(3_760.0)
        assert self._delka(v, 15)["cena_vyhnutelna_kc_mwh"] == pytest.approx(3_760.0)

    def test_regulovane_slozky_zvysi_slevu(self, vstup):
        """Čím víc složek PPA ušetří, tím větší sleva – cena PPA se nemění."""
        vstup.vyhnutelne_regulovane_kc_mwh = 0.0
        bez = self._delka(ppa.spocti_ppa2(vstup), 15)
        vstup.vyhnutelne_regulovane_kc_mwh = 500.0
        se = self._delka(ppa.spocti_ppa2(vstup), 15)
        assert se["sleva_zakaznikovi"] > bez["sleva_zakaznikovi"]
        assert se["cena_ppa_kc_mwh"] == pytest.approx(bez["cena_ppa_kc_mwh"])

    def test_drazsi_elektrina_znamena_vetsi_slevu(self, vstup):
        """Cena PPA se odvozuje jen z ekonomiky projektu, ne z ceny zákazníka.

        Při stejné délce kontraktu proto musí být cena identická a lišit se má
        jen sleva.
        """
        levna = self._delka(ppa.spocti_ppa2(vstup), 15)
        vstup.cena_silova_kc_mwh = 6_000.0
        drahá = self._delka(ppa.spocti_ppa2(vstup), 15)
        assert drahá["cena_ppa_kc_mwh"] == pytest.approx(levna["cena_ppa_kc_mwh"])
        assert drahá["sleva_zakaznikovi"] > levna["sleva_zakaznikovi"]

    def test_varianta_s_baterii(self, vstup):
        """Baterie se zadanou nákladovou cenou → druhá varianta s nájmem."""
        vstup.s_baterii = True
        vstup.baterie = ppa.Baterie(kapacita_kwh=200.0, vykon_kw=100.0, nakladova_cena_kc=800_000.0)
        v = ppa.spocti_ppa2(vstup)
        assert v["s_baterii"] is not None
        d = self._delka(v, 15, "s_baterii")
        assert d["baterie"]["najem_kc_mesic"] > 0
        assert d["kwp"] >= v["bez_baterie"]["kwp"]

    def test_upozorni_kdyz_baterie_zhorsi_usporu(self, vstup):
        """Nájem baterie může převážit přínos samospotřeby – to nesmí zůstat skryté.

        Model baterii započítává jen jako posun přebytku FVE do večera; peak shaving
        ani bateriové služby v něm nejsou, takže varianta s baterií může vyjít pro
        zákazníka hůř. Výpočet to musí říct nahlas – a to i když je horší jen u
        některé délky kontraktu (u krátkého nájem převáží, u dlouhého ne).
        """
        vstup.s_baterii = True
        vstup.baterie = ppa.Baterie(kapacita_kwh=200.0, vykon_kw=100.0, nakladova_cena_kc=800_000.0)
        v = ppa.spocti_ppa2(vstup)
        horsi = [
            n
            for n in (10, 15, 20)
            if self._delka(v, n, "s_baterii")["uspora_kumulativni_kc"]
            < self._delka(v, n)["uspora_kumulativni_kc"]
        ]
        if horsi:
            hlaska = next((u for u in v["upozorneni"] if "nájem baterie převáží" in u), None)
            assert hlaska is not None
            for n in horsi:
                assert f"{n} let" in hlaska

    def test_max_kwp_omezi_elektrarnu(self, vstup):
        """Strop musí velikost opravdu srazit a nesmí ji překročit."""
        bez_stropu = ppa.spocti_ppa2(vstup)["bez_baterie"]["kwp"]
        vstup.max_kwp = bez_stropu / 2
        v = ppa.spocti_ppa2(vstup)
        assert v["bez_baterie"]["kwp"] <= vstup.max_kwp
        assert v["bez_baterie"]["kwp"] < bez_stropu
        assert v["bez_baterie"]["omezeno_max_kwp"] is True
        assert v["bez_baterie"]["kwp_bez_stropu"] == pytest.approx(bez_stropu)

    def test_max_kwp_nad_optimem_nic_nemeni(self, vstup):
        """Strop vyšší než potřeba nesmí do výsledku zasáhnout ani ho označit."""
        bez_stropu = ppa.spocti_ppa2(vstup)["bez_baterie"]["kwp"]
        vstup.max_kwp = bez_stropu * 3
        v = ppa.spocti_ppa2(vstup)
        assert v["bez_baterie"]["kwp"] == pytest.approx(bez_stropu)
        assert v["bez_baterie"]["omezeno_max_kwp"] is False

    def test_max_kwp_zvysi_miru_samospotreby(self, vstup):
        """Menší elektrárna se spotřebuje na místě lépe → míra je nad cílem."""
        bez_stropu = ppa.spocti_ppa2(vstup)["bez_baterie"]["kwp"]
        vstup.max_kwp = bez_stropu / 3
        v = ppa.spocti_ppa2(vstup)
        mira = v["bez_baterie"]["po_delkach"][0]["energie"]["mira_samospotreby"]
        assert mira > vstup.cil_mira_samospotreby
        assert any("drží **strop" in u for u in v["upozorneni"])

    def test_export_se_defaultne_neinkasuje(self, vstup):
        """Rozhodnuto: výchozí cena za přetok je 0 Kč a výpočet to hlásí."""
        v = ppa.spocti_ppa2(vstup)
        assert v["vstup"]["cena_exportu_kc_mwh"] == 0.0
        assert v["bez_baterie"]["po_delkach"][0]["cena_exportu_kc_mwh"] == 0.0
        assert any("neinkasuje nic" in u for u in v["upozorneni"])

    def test_cena_exportu_se_zada_u_nabidky(self, vstup):
        """Zadaná cena za export musí srazit cenu PPA a zvýšit slevu."""
        bez = self._delka(ppa.spocti_ppa2(vstup), 15)
        vstup.cena_exportu_kc_mwh = 1_800.0
        se = self._delka(ppa.spocti_ppa2(vstup), 15)
        assert se["cena_exportu_kc_mwh"] == 1_800.0
        assert se["cena_ppa_kc_mwh"] < bez["cena_ppa_kc_mwh"]
        assert se["sleva_zakaznikovi"] > bez["sleva_zakaznikovi"]

    def test_upozorneni_pri_male_sleve(self, vstup):
        """Zákazník s už levnou elektřinou → nabídka nedává smysl a musí to říct."""
        vstup.cena_silova_kc_mwh = 1_200.0
        v = ppa.spocti_ppa2(vstup)
        assert any("nedává obchodní smysl" in u for u in v["upozorneni"])

    def test_nn_je_odmitnuto(self, vstup):
        vstup.hladina = "NN"
        with pytest.raises(ppa.NepodporovanaHladina):
            ppa.spocti_ppa2(vstup)

    def test_neznama_hladina_je_odmitnuta(self, vstup):
        vstup.hladina = "VVN"
        with pytest.raises(ppa.NepodporovanaHladina):
            ppa.spocti_ppa2(vstup)

    def test_chybejici_cena_zakaznika(self, vstup):
        vstup.cena_silova_kc_mwh = 0.0
        assert "chyba" in ppa.spocti_ppa2(vstup)

    def test_chybejici_diagram(self, vstup):
        vstup.casy = []
        assert "chyba" in ppa.spocti_ppa2(vstup)
