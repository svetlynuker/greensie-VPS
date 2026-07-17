# -*- coding: utf-8 -*-
"""Testy výpočetního jádra peak shavingu (`app/nabidkovac/peak_shaving.py`).

Modul je bez závislostí na DB/FastAPI – testuje se přímo nad syntetickými
profily (inspirace: docs/reserze_kalkulator/bughunt/synteticke-testy.md).
"""

import pytest

from app.nabidkovac import peak_shaving as ps


# ---------------------------------------------------------------- PS-2: pokuty
class TestPokutaPrekroceniRk:
    """Bod 4.24 CV ERÚ: překročení RK = 1,5× měsíční cena za měsíční RK."""

    def test_odvozeni_z_mesicni_rk_cez_2026(self):
        # ČEZ 2026 (CV 13/2025): VN 281,823 → 422,73; VVN 131,036 → 196,55.
        assert ps.pokuta_prekroceni_rk_kc_kw(281.823) == pytest.approx(422.7345)
        assert ps.pokuta_prekroceni_rk_kc_kw(131.036) == pytest.approx(196.554)

    def test_nasobek_je_15(self):
        assert ps.NASOBEK_POKUTY_PREKROCENI_RK == 1.5
        assert ps.pokuta_prekroceni_rk_kc_kw(100.0) == pytest.approx(150.0)

    def test_vychozi_rocni_naklad_uctuje_prekroceni_po_mesicich(self):
        # Leden: maxima 180 kW (překročení 60), únor: 150 kW (překročení 30).
        profil = [100.0, 180.0, 100.0, 150.0]
        mesice = [1, 1, 2, 2]
        pokuta = ps.pokuta_prekroceni_rk_kc_kw(281.823)
        rez, prekr = ps.vychozi_rocni_naklad_2026(profil, mesice, 120.0, 3030.78, pokuta)
        assert rez == pytest.approx(120.0 * 3030.78)
        assert prekr == pytest.approx((60.0 + 30.0) * pokuta)

    def test_bez_prekroceni_zadna_pokuta(self):
        profil = [100.0, 110.0]
        mesice = [1, 2]
        rez, prekr = ps.vychozi_rocni_naklad_2026(
            profil, mesice, 120.0, 3030.78, ps.pokuta_prekroceni_rk_kc_kw(281.823)
        )
        assert prekr == 0.0


# ------------------------------------------------------ PS-3: model 2027 bez AKU
# Sazby ČEZ VN z informativního CV ERÚ (5/2026), Kč/kW/měsíc.
P2027_CEZ_VN = {
    "t1_kapacita_kc_kw_mesic": 190.133,
    "t1_spicka_kc_kw_mesic": 19.013,
    "t2_kapacita_kc_kw_mesic": 22.743,
    "t2_spicka_kc_kw_mesic": 227.429,
    "sazba_prekroceni_kc_kw_mesic": 761.0,
    "u1_ucinnost": 0.60,
    "u2_ucinnost": 0.75,
}

# Dva měsíce po 8 intervalech: leden konstantně 100 kW, únor konstantně 200 kW.
PROFIL_2M = [100.0] * 8 + [200.0] * 8
MESICE_2M = [1] * 8 + [2] * 8


class TestEkonomika2027BezAku:
    """Rozhodnutí PS-3: sleva AKU pro BTM baterii bez exportu neexistuje (K=0)."""

    def test_mesicni_naklad_je_min_z_tarifu_bez_slevy(self):
        c, tarif = ps._mesicni_naklad_2027(100.0, 80.0, P2027_CEZ_VN)
        t1 = 100.0 * 190.133 + 80.0 * 19.013
        t2 = 100.0 * 22.743 + 80.0 * 227.429
        assert c == pytest.approx(min(t1, t2))
        assert tarif == ("t1" if t1 <= t2 else "t2")

    def test_penalizace_za_prekroceni_rp(self):
        t1 = 100.0 * 190.133 + 120.0 * 19.013
        t2 = 100.0 * 22.743 + 120.0 * 227.429
        c, _ = ps._mesicni_naklad_2027(100.0, 120.0, P2027_CEZ_VN)
        assert c == pytest.approx(min(t1, t2) + 20.0 * 761.0)

    def test_vystup_neobsahuje_aku_pole(self):
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 200.0, 150.0, 60.0, 1000.0, P2027_CEZ_VN)
        assert ek["status"] == "spocitano"
        for klic in (
            "prumerny_koeficient_aku",
            "prumerna_ucinnost",
            "predpoklad_aku_neoverovany",
            "novy_rocni_naklad_bez_aku",
            "rocni_uspora_bez_aku",
        ):
            assert klic not in ek
        assert ek["rocni_uspora"] == pytest.approx(
            ek["soucasny_rocni_naklad"] - ek["novy_rocni_naklad"]
        )
        assert ek["pocet_mesicu_t1"] + ek["pocet_mesicu_t2"] == 2

    def test_novy_naklad_odpovida_srazenym_maximum_bez_slevy(self):
        vykon, kapacita = 60.0, 1000.0
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 200.0, 150.0, vykon, kapacita, P2027_CEZ_VN)
        po_mesicich = ps.mesicni_maxima_po_baterii(PROFIL_2M, MESICE_2M, vykon, kapacita)
        ocekavany, _, _ = ps._rocni_naklad_2027(150.0, po_mesicich, P2027_CEZ_VN)
        assert ek["novy_rocni_naklad"] == pytest.approx(ocekavany)

    def test_varianta_nese_jedinou_navratnost_2027(self):
        baterie = ps.Baterie(id=1, nazev="Test 60/120", vykon_kw=60.0, kapacita_kwh=120.0, cena_kc=1_000_000.0)
        v = ps.spocti_variantu(
            baterie,
            1,
            PROFIL_2M,
            MESICE_2M,
            200.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            parametry_2027=P2027_CEZ_VN,
        )
        assert v.navratnost_2027 is not None
        assert not hasattr(v, "navratnost_2027_optim")
        assert not hasattr(v, "navratnost_2027_konzerv")
        assert "prumerny_koeficient_aku" not in v.ekonomika_2027


# ------------------------------------------------------- PS-5: ztráty baterie
class TestZtratyBaterie:
    def test_normalizace_ucinnosti(self):
        assert ps.normalizuj_ucinnost_rt(None) == 0.88
        assert ps.normalizuj_ucinnost_rt(0.92) == 0.92
        assert ps.normalizuj_ucinnost_rt(88) == 0.88  # zadáno v procentech
        assert ps.normalizuj_ucinnost_rt(1.2) == 0.88  # nesmysl → default
        assert ps.normalizuj_ucinnost_rt(0.3) == 0.88  # nereálně nízké → default
        assert ps.normalizuj_ucinnost_rt("nesmysl") == 0.88

    def test_strop_se_ztratami_je_vyssi_nez_bezztraty(self):
        # T7: dvě špičky denně, mezi nimi krátké okno na dobití.
        profil = []
        for den in range(5):
            profil += [200.0] * 36 + [350.0] * 8 + [200.0] * 8 + [350.0] * 8 + [200.0] * 36
        bez = ps.min_udrzitelny_strop(profil, 80.0, 160.0, ucinnost_rt=1.0)
        se_ztratami = ps.min_udrzitelny_strop(profil, 80.0, 160.0, ucinnost_rt=0.88)
        assert se_ztratami > bez

    def test_energeticka_bilance_nabito_vybito(self):
        # Vybije se 25 kWh AC na špičce, pak se plně dobije: nabito = vybito/RT.
        profil = [150.0, 150.0] + [50.0] * 96
        nabito, vybito = ps.energie_pri_stropu(
            profil, 100.0, 80.0, 100.0, interval_h=0.25, ucinnost_rt=0.88
        )
        assert vybito == pytest.approx(25.0)
        assert nabito == pytest.approx(25.0 / 0.88, rel=1e-6)

    def test_naklad_ztrat(self):
        # 10 MWh nabito při RT 0,88 a 3000 Kč/MWh → 10 000 × 0,12 × 3 = 3 600 Kč.
        assert ps.naklad_ztrat_baterie_kc(10_000.0, 0.88, 3000.0) == pytest.approx(3600.0)
        assert ps.naklad_ztrat_baterie_kc(10_000.0, 1.0, 3000.0) == 0.0

    def test_varianta_pocita_s_vyuzitelnou_kapacitou_a_ztratami(self):
        # Špička na začátku, pak base load pod stropem → baterie se po vybití
        # dobíjí ze sítě a ztráty cyklování mají nenulovou cenu.
        profil = [200.0] * 4 + [100.0] * 12
        mesice = [1] * 8 + [2] * 8
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=120.0, cena_kc=1_000_000.0, ucinnost_rt=0.88
        )
        v = ps.spocti_variantu(
            baterie,
            1,
            profil,
            mesice,
            200.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            cena_energie_kc_mwh=3000.0,
        )
        assert v.vyuzitelna_kapacita_kwh == pytest.approx(120.0 * 0.85)
        assert v.ucinnost_rt == 0.88
        ek = v.ekonomika_2026
        assert ek["naklad_ztrat_baterie"] > 0
        assert ek["rocni_uspora"] == pytest.approx(
            ek["soucasny_naklad_celkem"] - ek["novy_naklad_rezervace"] - ek["naklad_ztrat_baterie"]
        )

    def test_bezztratovy_rezim_odpovida_puvodnimu_chovani(self):
        profil = [100.0, 180.0, 100.0, 150.0]
        strop = ps.min_udrzitelny_strop(profil, 50.0, 100.0, ucinnost_rt=1.0)
        nabito, vybito = ps.energie_pri_stropu(profil, strop, 50.0, 100.0, ucinnost_rt=1.0)
        assert nabito >= 0 and vybito >= 0
        assert ps.naklad_ztrat_baterie_kc(nabito, 1.0, 3000.0) == 0.0


# --------------------------------------------------------- PS-6: rezerva RK
class TestRezervaRk:
    def _varianta(self, rezerva):
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=1000.0, cena_kc=1_000_000.0, ucinnost_rt=1.0
        )
        return ps.spocti_variantu(
            baterie,
            1,
            PROFIL_2M,
            MESICE_2M,
            250.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=rezerva,
            cena_mesicni_rk_kc_kw_mesic=281.823,
        )

    def test_default_rezervy_je_5_procent(self):
        assert ps.VYCHOZI_REZERVA_RK_PROCENTA == 5.0

    def test_rezerva_zdrazuje_cilovou_rezervaci(self):
        # Rezerva navyšuje cílová maxima obou optimalizací (PS-6 × PS-7).
        bez = self._varianta(0.0)
        s_rezervou = self._varianta(5.0)
        assert s_rezervou.ekonomika_2026["novy_naklad_rezervace"] == pytest.approx(
            bez.ekonomika_2026["novy_naklad_rezervace"] * 1.05, rel=1e-6
        )
        assert s_rezervou.rezerva_rk_procenta == 5.0

    def test_rezerva_snizuje_usporu(self):
        bez = self._varianta(0.0)
        s_rezervou = self._varianta(5.0)
        assert s_rezervou.rocni_uspora_2026 < bez.rocni_uspora_2026


# ------------------------------------------------------ PS-7: fair baseline
class TestFairBaseline:
    # T5 tvar: základ 300 kW, leden 400, únor 380 (měsíční maxima).
    MAXIMA_T5 = {1: 400.0, 2: 380.0, **{m: 300.0 for m in range(3, 13)}}
    CENA_ROCNI = 3030.78
    CENA_MESICNI = 281.823

    def test_optimum_kombinace_je_v_medianu_maxim(self):
        opt = ps.optimalizuj_rk(self.MAXIMA_T5, self.CENA_ROCNI, self.CENA_MESICNI)
        # dokup (1×) je levnější než držet roční RK na špičce → R* = 300
        assert opt.rocni_rk_kw == 300.0
        ocekavany = 300.0 * self.CENA_ROCNI + (100.0 + 80.0) * self.CENA_MESICNI
        assert opt.naklad_kc == pytest.approx(ocekavany)
        assert opt.dokupy_kw == {1: 100.0, 2: 80.0}

    def test_optimum_nikdy_neplati_pokuty(self):
        # náklad optimální kombinace ≤ čistě roční RK na celoročním maximu
        opt = ps.optimalizuj_rk(self.MAXIMA_T5, self.CENA_ROCNI, self.CENA_MESICNI)
        assert opt.naklad_kc <= 400.0 * self.CENA_ROCNI

    def test_plochy_profil_bez_dokupu(self):
        maxima = {m: 250.0 for m in range(1, 13)}
        opt = ps.optimalizuj_rk(maxima, self.CENA_ROCNI, self.CENA_MESICNI)
        assert opt.rocni_rk_kw == 250.0
        assert opt.dokupy_kw == {}

    def test_ekonomika_2026_rozpad_uspory(self):
        # Profil dle T5 (15min konstantní bloky po měsících stačí pro maxima).
        profil, mesice = [], []
        for m, maximum in sorted(self.MAXIMA_T5.items()):
            profil += [200.0, maximum]  # v každém měsíci základ + špička
            mesice += [m, m]
        ek = ps.ekonomika_2026(
            profil,
            mesice,
            rezervovana_kapacita_kw=400.0,
            cena_rezervace_kc_kw_rok=self.CENA_ROCNI,
            cena_prekroceni_kc_kw=ps.pokuta_prekroceni_rk_kc_kw(self.CENA_MESICNI),
            strop_kw=300.0,
            cena_mesicni_rk_kc_kw_mesic=self.CENA_MESICNI,
            rezerva_rk_procenta=0.0,
            naklad_ztrat_baterie=1000.0,
        )
        # dnešní stav: RK 400, žádné překročení → jen rezervace
        assert ek.soucasny_naklad_celkem == pytest.approx(400.0 * self.CENA_ROCNI)
        # fair baseline: R*=300 + dokupy 100/80
        assert ek.optimalni_rk_bez_baterie_kw == 300.0
        assert ek.uspora_bez_investice == pytest.approx(
            400.0 * self.CENA_ROCNI - (300.0 * self.CENA_ROCNI + 180.0 * self.CENA_MESICNI)
        )
        # s baterií (strop 300): maxima všude 300 → čistá roční RK 300
        assert ek.novy_naklad_rezervace == pytest.approx(300.0 * self.CENA_ROCNI)
        assert ek.dokupy_s_baterii_pocet_mesicu == 0
        # přínos baterie = dokupy, které baterie ušetří, minus ztráty
        assert ek.prinos_baterie == pytest.approx(180.0 * self.CENA_MESICNI - 1000.0)
        # konzistence rozpadu
        assert ek.rocni_uspora == pytest.approx(ek.uspora_bez_investice + ek.prinos_baterie)

    def test_npv_ridi_vyber_vitezneho_produktu(self):
        # Dva produkty: levný s rychlou návratností, ale malým přínosem, vs.
        # dražší s pomalejší návratností a větším NPV → vítěz dle NPV (PS-8).
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        maly = ps.Baterie(id=1, nazev="Malý", vykon_kw=30.0, kapacita_kwh=100.0, cena_kc=300_000.0, ucinnost_rt=1.0)
        velky = ps.Baterie(id=2, nazev="Velký", vykon_kw=190.0, kapacita_kwh=600.0, cena_kc=2_400_000.0, ucinnost_rt=1.0)
        vysledek = ps.vyber_reseni(
            [maly, velky],
            profil,
            mesice,
            400.0,
            self.CENA_ROCNI,
            ps.pokuta_prekroceni_rk_kc_kw(self.CENA_MESICNI),
            max_navratnost_roky=100.0,
            max_pocet_kusu=1,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=0.0,
            cena_mesicni_rk_kc_kw_mesic=self.CENA_MESICNI,
            npv_nastaveni=ps.NastaveniNpv(
                diskontni_sazba=0.08, horizont_roky=10,
                oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0,
            ),
        )
        assert vysledek.doporucena is not None
        npv_vitez = vysledek.doporucena.npv_kc
        assert all(v.npv_kc <= npv_vitez + 1e-6 for v in vysledek.varianty)

    def test_navratnost_varianty_je_z_prinosu_baterie(self):
        profil, mesice = [], []
        for m, maximum in sorted(self.MAXIMA_T5.items()):
            profil += [200.0] * 6 + [maximum] + [200.0] * 5
            mesice += [m] * 12
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=150.0, kapacita_kwh=400.0, cena_kc=2_000_000.0, ucinnost_rt=1.0
        )
        v = ps.spocti_variantu(
            baterie,
            1,
            profil,
            mesice,
            400.0,
            self.CENA_ROCNI,
            ps.pokuta_prekroceni_rk_kc_kw(self.CENA_MESICNI),
            5.0,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=0.0,
            cena_mesicni_rk_kc_kw_mesic=self.CENA_MESICNI,
        )
        assert v.prinos_baterie_2026 > 0
        assert v.navratnost_roky == pytest.approx(v.cena_celkem_kc / v.prinos_baterie_2026)
        assert v.rocni_uspora_2026 == pytest.approx(
            v.uspora_bez_investice_2026 + v.prinos_baterie_2026
        )


# ------------------------------------------------- PS-8/PS-9: NPV baterie
class TestNpvBaterie:
    def test_defaulty_dle_rozhodnuti(self):
        n = ps.NastaveniNpv()
        assert n.diskontni_sazba == 0.08
        assert n.horizont_roky == 10
        assert n.oam_procenta_capex_rok == 2.0
        assert n.degradace_uspor_procenta_rok == 1.5

    def test_jednoduchy_pripad_bez_diskontu(self):
        # horizont 2, bez diskontu/O&M/degradace: NPV = přínos26 + přínos27 − cena
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=2,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        npv, irr, cf, pouzit = ps._npv_baterie(500_000.0, 300_000.0, 400_000.0, n)
        assert cf == [300_000.0, 400_000.0]
        assert npv == pytest.approx(200_000.0)
        assert pouzit is True

    def test_rok1_model_2026_dalsi_roky_2027(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        _, _, cf, _ = ps._npv_baterie(0.0, 100.0, 250.0, n)
        assert cf == [100.0, 250.0, 250.0]

    def test_oam_a_degradace_snizuji_cf(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=2,
                            oam_procenta_capex_rok=2.0, degradace_uspor_procenta_rok=10.0)
        _, _, cf, _ = ps._npv_baterie(1_000_000.0, 500_000.0, 500_000.0, n)
        # O&M = 20 000/rok; rok 2 přínos × 0,9
        assert cf[0] == pytest.approx(500_000.0 - 20_000.0)
        assert cf[1] == pytest.approx(500_000.0 * 0.9 - 20_000.0)

    def test_bez_sazeb_2027_pouzije_model_2026(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        npv, _, cf, pouzit = ps._npv_baterie(0.0, 100.0, None, n)
        assert pouzit is False
        assert cf == [100.0, 100.0, 100.0]


# -------------------------------------- rozpis cash flow po letech (FE tabulka)
class TestRokyCashFlow:
    def test_struktura_a_modely_roku(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        _, _, cf, pouzit = ps._npv_baterie(500.0, 100.0, 250.0, n)
        roky = ps._roky_cash_flow(500.0, cf, n, pouzit)
        assert [r["rok"] for r in roky] == [1, 2, 3]
        assert [r["model"] for r in roky] == ["2026", "2027", "2027"]
        assert [r["cf_kc"] for r in roky] == [100.0, 250.0, 250.0]
        assert roky[-1]["uspora_kum_kc"] == pytest.approx(600.0)
        # kum. CF = kum. úspora − investice
        assert roky[-1]["cf_kum_kc"] == pytest.approx(100.0)

    def test_kumulovany_diskontovany_cf_konci_na_npv(self):
        n = ps.NastaveniNpv()  # defaulty: diskont 8 %, O&M 2 % CAPEX, degradace 1,5 %
        npv, _, cf, pouzit = ps._npv_baterie(1_000_000.0, 180_000.0, 240_000.0, n)
        roky = ps._roky_cash_flow(1_000_000.0, cf, n, pouzit)
        assert len(roky) == n.horizont_roky
        assert roky[-1]["cf_kum_disk_kc"] == pytest.approx(npv, abs=0.01)
        # přínos = CF + O&M; O&M = 2 % z CAPEX; rok 1 bez degradace
        assert roky[0]["oam_kc"] == pytest.approx(20_000.0)
        assert roky[0]["prinos_kc"] == pytest.approx(180_000.0)

    def test_bez_sazeb_2027_je_cely_horizont_2026(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        _, _, cf, pouzit = ps._npv_baterie(0.0, 100.0, None, n)
        roky = ps._roky_cash_flow(0.0, cf, n, pouzit)
        assert [r["model"] for r in roky] == ["2026", "2026", "2026"]

    def test_spocti_variantu_nese_konzistentni_roky(self):
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=150.0, kapacita_kwh=400.0, cena_kc=2_000_000.0, ucinnost_rt=1.0
        )
        v = ps.spocti_variantu(
            baterie,
            1,
            profil,
            mesice,
            400.0,
            1_287.48,
            160.0,
            8.0,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=0.0,
            cena_mesicni_rk_kc_kw_mesic=107.29,
        )
        assert len(v.roky) == v.npv_horizont_roky
        assert v.roky[-1]["cf_kum_disk_kc"] == pytest.approx(v.npv_kc, abs=0.01)
        assert v.roky[0]["prinos_kc"] == pytest.approx(v.prinos_baterie_2026, abs=0.01)


# ------------------------------------------------ PS-10: citlivost stropu
class TestCitlivostStropu:
    # Špička 350 kW nad základem 200, baterie výkonově omezená (80 kW).
    PROFIL = ([200.0] * 8 + [350.0] * 4 + [200.0] * 8) * 12

    def test_strop_roste_s_profilem(self):
        strop = ps.min_udrzitelny_strop(self.PROFIL, 80.0, 500.0)
        c = ps.citlivost_stropu(self.PROFIL, 80.0, 500.0, strop, rezerva_rk_procenta=5.0)
        assert c["strop_minus_kw"] < strop < c["strop_plus_kw"]
        assert c["procenta"] == 5.0

    def test_vykonove_omezena_baterie_roste_rychleji_nez_profil(self):
        # Výkon baterie se s rokem neškáluje: strop = max − výkon → při
        # špičkách +5 % roste strop o VÍC než 5 % → rezerva 5 % nestačí.
        strop = ps.min_udrzitelny_strop(self.PROFIL, 80.0, 500.0)
        c = ps.citlivost_stropu(self.PROFIL, 80.0, 500.0, strop, rezerva_rk_procenta=5.0)
        assert c["strop_plus_kw"] > strop * 1.05
        assert c["rezerva_pokryje_horni_scenar"] is False

    def test_dostatecna_rezerva_horni_scenar_pokryje(self):
        strop = ps.min_udrzitelny_strop(self.PROFIL, 80.0, 500.0)
        c = ps.citlivost_stropu(self.PROFIL, 80.0, 500.0, strop, rezerva_rk_procenta=15.0)
        assert c["rezerva_pokryje_horni_scenar"] is True


# ------------------------------------------ PS-4: rezervovaný příkon (2027)
class TestRezervovanyPrikon2027:
    def _varianta(self, rezervovany_prikon_kw=None, uvazovat_snizeni_rp=False):
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=1000.0, cena_kc=1_000_000.0, ucinnost_rt=1.0
        )
        return ps.spocti_variantu(
            baterie,
            1,
            PROFIL_2M,
            MESICE_2M,
            250.0,
            3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823),
            5.0,
            parametry_2027=P2027_CEZ_VN,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=0.0,
            rezervovany_prikon_kw=rezervovany_prikon_kw,
            uvazovat_snizeni_rp=uvazovat_snizeni_rp,
        )

    def test_fallback_na_soucasnou_rk(self):
        v = self._varianta(rezervovany_prikon_kw=None)
        assert v.ekonomika_2027["rp_soucasny_kw"] == 250.0

    def test_zadany_rp_se_pouzije_v_obou_scenarich(self):
        v = self._varianta(rezervovany_prikon_kw=320.0)
        assert v.ekonomika_2027["rp_soucasny_kw"] == 320.0
        # bez snížení smlouvy zůstává RP i ve scénáři s PS (poctivý default)
        assert v.ekonomika_2027["rp_novy_kw"] == 320.0

    def test_snizeni_rp_na_novou_rk(self):
        v = self._varianta(rezervovany_prikon_kw=320.0, uvazovat_snizeni_rp=True)
        # Cíl snížení RP = fyzický strop + rezerva (zde 0 %) – v NTS neexistují
        # měsíční dokupy RK, roční složka kombinace 2026 se nepoužívá.
        assert v.ekonomika_2027["rp_novy_kw"] == pytest.approx(v.strop_kw)
        # snížení RP zlevňuje kapacitní složku → vyšší úspora 2027
        bez_snizeni = self._varianta(rezervovany_prikon_kw=320.0)
        assert v.ekonomika_2027["rocni_uspora"] > bez_snizeni.ekonomika_2027["rocni_uspora"]

    def test_bez_snizeni_je_prinos_jen_na_slozce_maxima(self):
        v = self._varianta(rezervovany_prikon_kw=320.0)
        ek = v.ekonomika_2027
        # RP stejné v obou scénářích → úspora vzniká jen sražením měsíčních maxim
        assert ek["rp_soucasny_kw"] == ek["rp_novy_kw"]
        assert ek["rocni_uspora"] > 0
