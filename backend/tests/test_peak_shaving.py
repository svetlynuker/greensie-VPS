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


class TestOptimalizaceRp2027:
    """Třetí výpočet: nejlevnější RP bez baterie v tarifu 2027 (fér baseline)."""

    def test_je_nejlevnejsi_ze_vsech_kandidatu(self):
        # Optimalizovaný náklad musí být ≤ náklad při libovolném RP.
        raw = ps._mesicni_maxima(PROFIL_2M, MESICE_2M)  # {1: 100, 2: 200}
        naklad, rp = ps.optimalizuj_rp_2027(raw, P2027_CEZ_VN)
        for zkusmy_rp in (0.0, 50.0, 100.0, 150.0, 200.0, 250.0, 300.0):
            zkusmy, _, _ = ps._rocni_naklad_2027(zkusmy_rp, raw, P2027_CEZ_VN)
            assert naklad <= zkusmy + 1e-6
        vlastni, _, _ = ps._rocni_naklad_2027(rp, raw, P2027_CEZ_VN)
        assert naklad == pytest.approx(vlastni)

    def test_neni_horsi_nez_soucasny_rp(self):
        # Optimalizace nikdy nezhorší náklad proti (předimenzovanému) RP.
        raw = ps._mesicni_maxima(PROFIL_2M, MESICE_2M)
        naklad_opt, _ = ps.optimalizuj_rp_2027(raw, P2027_CEZ_VN)
        soucasny, _, _ = ps._rocni_naklad_2027(300.0, raw, P2027_CEZ_VN)
        assert naklad_opt <= soucasny

    def test_prazdna_maxima(self):
        assert ps.optimalizuj_rp_2027({}, P2027_CEZ_VN) == (0.0, 0.0)


class TestEkonomika2027RozpadUspory:
    """Rozklad úspory 2027 je symetrický s modelem 2026 (dnešní → opt → baterie)."""

    def test_vystup_nese_rozpad_bez_baterie(self):
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 300.0, 150.0, 60.0, 1000.0, P2027_CEZ_VN)
        for klic in (
            "naklad_optimalni_bez_baterie",
            "optimalni_rp_bez_baterie_kw",
            "uspora_optimalizaci_bez_baterie",
            "prinos_baterie",
        ):
            assert klic in ek

    def test_soucet_slozek_dava_celkovou_usporu(self):
        # úspora bez investice + přínos baterie == celková roční úspora.
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 300.0, 150.0, 60.0, 1000.0, P2027_CEZ_VN)
        assert ek["uspora_optimalizaci_bez_baterie"] + ek["prinos_baterie"] == pytest.approx(
            ek["rocni_uspora"]
        )

    def test_optimalizovany_naklad_odpovida_funkci(self):
        ek = ps.ekonomika_2027(PROFIL_2M, MESICE_2M, 300.0, 150.0, 60.0, 1000.0, P2027_CEZ_VN)
        raw = ps._mesicni_maxima(PROFIL_2M, MESICE_2M)
        naklad, rp = ps.optimalizuj_rp_2027(raw, P2027_CEZ_VN)
        assert ek["naklad_optimalni_bez_baterie"] == pytest.approx(naklad)
        assert ek["optimalni_rp_bez_baterie_kw"] == pytest.approx(rp)


class TestOptimalizaceRpSBaterii:
    """Scénář se snížením RP volí RP optimalizací, ne natvrdo celoročním stropem.

    Jinak by byla baseline optimalizovaná a scénář s baterií ne → přínos
    baterie systematicky podhodnocený.
    """

    # Rok, kde jeden měsíc výrazně přečnívá: leden 1500 kW, ostatní 1000 kW.
    # (16 intervalů na měsíc, baterie se nezadává tak velká, aby špičku srazila.)
    PROFIL_ROK = [1500.0] * 16 + [1000.0] * 16 * 11
    MESICE_ROK = [1] * 16 + [m for m in range(2, 13) for _ in range(16)]

    def _ek(self, optimalizovat, rezerva=0.0):
        # Baterie 0 kW = nic nesráží, měsíční maxima zůstanou původní. Zajímá
        # nás jen volba RP, ne fyzika srážení.
        return ps.ekonomika_2027(
            self.PROFIL_ROK,
            self.MESICE_ROK,
            2000.0,  # současný RP ze smlouvy
            1500.0,  # RP „natvrdo na strop" = nejvyšší měsíční maximum
            0.0,
            0.0,
            P2027_CEZ_VN,
            optimalizovat_rp=optimalizovat,
            rezerva_rk_procenta=rezerva,
        )

    def test_bez_optimalizace_drzi_rp_na_stropu(self):
        ek = self._ek(optimalizovat=False)
        assert ek["rp_novy_kw"] == pytest.approx(1500.0)
        assert ek["mesicu_s_prekrocenim_rp"] == 0
        assert ek["rp_optimalizovan"] is False

    def test_optimalizace_pusti_rp_pod_spicku(self):
        ek = self._ek(optimalizovat=True)
        # Snížit RP o 1 kW ušetří 12× kapacitní sazbu, překročení stojí jednou
        # sazbu za překročení → u jediného vybočujícího měsíce se to vyplatí.
        assert ek["rp_novy_kw"] < 1500.0
        assert ek["mesicu_s_prekrocenim_rp"] == 1
        assert ek["naklad_prekroceni_rp"] > 0

    def test_optimalizace_nikdy_nezhorsi_naklad(self):
        bez = self._ek(optimalizovat=False)
        s_opt = self._ek(optimalizovat=True)
        assert s_opt["novy_rocni_naklad"] <= bez["novy_rocni_naklad"] + 1e-6
        assert s_opt["prinos_baterie"] >= bez["prinos_baterie"] - 1e-6

    def test_rezerva_rk_zvedne_volene_rp(self):
        # Rezerva navyšuje cílová maxima → optimalizátor volí opatrnější RP.
        bez_rezervy = self._ek(optimalizovat=True, rezerva=0.0)
        s_rezervou = self._ek(optimalizovat=True, rezerva=5.0)
        assert s_rezervou["rp_novy_kw"] >= bez_rezervy["rp_novy_kw"]

    def test_plochy_rok_rp_nesnizi_pod_maximum(self):
        # Když všechny měsíce sedí na stejném maximu, překročení by se platilo
        # 12× – optimalizace proto RP nechá na maximu.
        profil = [1000.0] * 16 * 12
        mesice = [m for m in range(1, 13) for _ in range(16)]
        ek = ps.ekonomika_2027(
            profil, mesice, 2000.0, 1000.0, 0.0, 0.0, P2027_CEZ_VN, optimalizovat_rp=True
        )
        assert ek["rp_novy_kw"] == pytest.approx(1000.0)
        assert ek["mesicu_s_prekrocenim_rp"] == 0


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

    def test_vysledek_nese_variantu_za_kazdy_produkt(self):
        # Srovnání v UI umí zobrazit celý katalog (manažerské rozhodnutí), takže
        # výběr nesmí produkty zahazovat – za každý zůstane jeho nejlepší počet kusů.
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        katalog = [
            ps.Baterie(
                id=i,
                nazev=f"BESS {30 * i}",
                vykon_kw=30.0 * i,
                kapacita_kwh=100.0 * i,
                cena_kc=300_000.0 * i,
                ucinnost_rt=1.0,
            )
            for i in range(1, 7)
        ]
        vysledek = ps.vyber_reseni(
            katalog,
            profil,
            mesice,
            400.0,
            self.CENA_ROCNI,
            ps.pokuta_prekroceni_rk_kc_kw(self.CENA_MESICNI),
            max_navratnost_roky=100.0,
            cena_mesicni_rk_kc_kw_mesic=self.CENA_MESICNI,
        )
        assert len(vysledek.varianty) == len(katalog)
        assert {v.baterie_id for v in vysledek.varianty} == {b.id for b in katalog}
        # a pořadí je sestupně dle NPV (vítěz první)
        npvs = [v.npv_kc for v in vysledek.varianty]
        assert npvs == sorted(npvs, reverse=True)

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
        # horizont 2, bez diskontu/O&M/degradace: NPV = 2× přínos 2027 − cena
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=2,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        npv, irr, cf, pouzit = ps._npv_baterie(500_000.0, 300_000.0, 400_000.0, n)
        assert cf == [400_000.0, 400_000.0]
        assert npv == pytest.approx(300_000.0)
        assert pouzit is True

    def test_cely_horizont_jede_na_modelu_2027(self):
        # Rozhodnuto 27. 7. 2026: co se dnes nabízí, se instaluje a spouští už
        # v NTS – rok na tarifu 2026 nikdo neodžije, do CF tedy nevstupuje.
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        _, _, cf, _ = ps._npv_baterie(0.0, 100.0, 250.0, n)
        assert cf == [250.0, 250.0, 250.0]

    def test_prinos_2026_je_jen_fallback_bez_sazeb_2027(self):
        n = ps.NastaveniNpv(diskontni_sazba=0.0, horizont_roky=3,
                            oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0)
        # Se sazbami 2027 se hodnota 2026 vůbec nepoužije…
        _, _, cf_s, _ = ps._npv_baterie(0.0, 999_999.0, 250.0, n)
        assert cf_s == [250.0, 250.0, 250.0]
        # …bez nich drží celý horizont.
        _, _, cf_bez, _ = ps._npv_baterie(0.0, 100.0, None, n)
        assert cf_bez == [100.0, 100.0, 100.0]

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
        assert [r["model"] for r in roky] == ["2027", "2027", "2027"]
        assert [r["cf_kc"] for r in roky] == [250.0, 250.0, 250.0]
        assert roky[-1]["uspora_kum_kc"] == pytest.approx(750.0)
        # kum. CF = kum. úspora − investice
        assert roky[-1]["cf_kum_kc"] == pytest.approx(250.0)

    def test_kumulovany_diskontovany_cf_konci_na_npv(self):
        n = ps.NastaveniNpv()  # defaulty: diskont 8 %, O&M 2 % CAPEX, degradace 1,5 %
        npv, _, cf, pouzit = ps._npv_baterie(1_000_000.0, 180_000.0, 240_000.0, n)
        roky = ps._roky_cash_flow(1_000_000.0, cf, n, pouzit)
        assert len(roky) == n.horizont_roky
        assert roky[-1]["cf_kum_disk_kc"] == pytest.approx(npv, abs=0.01)
        # přínos = CF + O&M; O&M = 2 % z CAPEX; rok 1 bez degradace, model 2027
        assert roky[0]["oam_kc"] == pytest.approx(20_000.0)
        assert roky[0]["prinos_kc"] == pytest.approx(240_000.0)

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


# --------------------------------------- ruční override max. výkonu střídače
class TestMaxVykonStridace:
    """U modulárních baterií kapacita roste s počtem kusů, ale AC výkon bývá
    omezen sdíleným/pevným střídačem (PCS) – OZ ho může zadat natvrdo."""

    def _varianta(self, max_vykon_stridace_kw):
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=200.0, cena_kc=1_000_000.0, ucinnost_rt=1.0
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
            max_vykon_stridace_kw=max_vykon_stridace_kw,
        )

    def test_bez_zadani_pouzije_stitkovy_vykon(self):
        assert self._varianta(None).celkovy_vykon_kw == 60.0

    def test_override_omezi_vykon_pod_stitkovy(self):
        assert self._varianta(30.0).celkovy_vykon_kw == 30.0

    def test_override_nad_stitkovym_vykonem_nema_vliv(self):
        assert self._varianta(200.0).celkovy_vykon_kw == 60.0

    def test_nekladna_hodnota_se_ignoruje(self):
        assert self._varianta(0.0).celkovy_vykon_kw == 60.0

    def test_nizsi_vykon_nemuze_snizit_strop_pod_bez_omezeni(self):
        # Nižší reálný AC výkon omezuje vybíjení → udržitelný strop nemůže
        # klesnout pod hodnotu bez omezení (může jen zůstat stejný nebo růst).
        bez = self._varianta(None)
        s_omezenim = self._varianta(30.0)
        assert s_omezenim.strop_kw >= bez.strop_kw


# --------------------------- katalogové parametry z ceníku BESS (extra)
class TestKatalogoveParametry:
    """Nové sloupce ceníku BESS: `uzitna_kapacita_kwh` (kapacita pro simulaci)
    a `max_vykon_stridacu_kw` (reálný AC výkon střídačů na kus). Chybí-li,
    výpočet spadne na jmenovité hodnoty (beze změny oproti dřívějšku)."""

    def _varianta(self, pocet, **kwargs):
        baterie = ps.Baterie(
            id=1, nazev="B", vykon_kw=60.0, kapacita_kwh=200.0, cena_kc=1_000_000.0,
            ucinnost_rt=1.0, **kwargs,
        )
        return ps.spocti_variantu(
            baterie, pocet, PROFIL_2M, MESICE_2M, 250.0, 3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823), 5.0, cena_energie_kc_mwh=0.0,
        )

    def test_uzitna_kapacita_se_pouzije_v_simulaci(self):
        # Užitná < jmenovitá → simulace jede na užitné × SOC okno, nameplate
        # (celková kapacita) zůstává jmenovitá.
        v = self._varianta(1, uzitna_kapacita_kwh=100.0)
        assert v.celkova_kapacita_kwh == 200.0  # nameplate beze změny
        assert v.vyuzitelna_kapacita_kwh == 100.0 * ps.PODIL_VYUZITELNE_KAPACITY

    def test_chybejici_uzitna_spadne_na_jmenovitou(self):
        v = self._varianta(1)
        assert v.vyuzitelna_kapacita_kwh == 200.0 * ps.PODIL_VYUZITELNE_KAPACITY

    def test_nekladna_uzitna_spadne_na_jmenovitou(self):
        v = self._varianta(1, uzitna_kapacita_kwh=0.0)
        assert v.vyuzitelna_kapacita_kwh == 200.0 * ps.PODIL_VYUZITELNE_KAPACITY

    def test_ac_strop_stridacu_omezi_vykon_pri_vice_kusech(self):
        # Střídač 40 kW/kus × 2 kusy = 80 kW AC strop, i když jmenovitý
        # výkon dvou kusů je 120 kW.
        v = self._varianta(2, max_vykon_stridacu_kw=40.0)
        assert v.celkovy_vykon_kw == 80.0

    def test_ac_strop_rovny_jmenovitemu_nema_vliv(self):
        v = self._varianta(2, max_vykon_stridacu_kw=60.0)
        assert v.celkovy_vykon_kw == 120.0


# ------------------------------------------- průběh v čase (nitkový graf)
class TestPrubehBaterie:
    """Rozepsaná 15min simulace – podklad pro graf průběhu.

    Klíčové je, aby se nerozešla s ekonomikou: sdílí `_krok_simulace`
    s `energie_pri_stropu`, takže součty musí sedět na haléř.
    """

    # Špičkový profil: dvě hodiny nad stropem, zbytek hluboko pod ním.
    PROFIL = [50.0] * 8 + [180.0] * 8 + [50.0] * 8 + [200.0] * 8 + [40.0] * 8

    def test_soucty_sedi_s_energie_pri_stropu(self):
        strop = 120.0
        nabito, vybito = ps.energie_pri_stropu(self.PROFIL, strop, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        p = ps.prubeh_baterie(self.PROFIL, strop, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        assert p["nabito_kwh"] == pytest.approx(nabito)
        assert p["vybito_kwh"] == pytest.approx(vybito)

    def test_energeticka_bilance_site(self):
        # Co teče z přípojky = odběr − vybíjení + nabíjení (po intervalech).
        p = ps.prubeh_baterie(self.PROFIL, 120.0, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        for odber, site, bat in zip(self.PROFIL, p["site_kw"], p["baterie_kw"]):
            assert site == pytest.approx(odber - bat)
        odebrano = sum(p["site_kw"]) * 0.25
        spotreba = sum(self.PROFIL) * 0.25
        assert odebrano == pytest.approx(spotreba - p["vybito_kwh"] + p["nabito_kwh"])

    def test_udrzitelny_strop_se_v_prubehu_neprekroci(self):
        strop = ps.min_udrzitelny_strop(self.PROFIL, 100.0, 200.0, 0.25, 0.88)
        p = ps.prubeh_baterie(self.PROFIL, strop, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        assert max(p["site_kw"]) <= strop + 1e-6

    def test_prilis_nizky_strop_se_v_grafu_projevi_prekrocenim(self):
        # Baterie nestačí → graf poctivě ukáže, že síť jde nad strop.
        p = ps.prubeh_baterie(self.PROFIL, 60.0, 20.0, 20.0, 0.25, ucinnost_rt=0.88)
        assert max(p["site_kw"]) > 60.0

    def test_soc_zustava_v_mezich(self):
        p = ps.prubeh_baterie(self.PROFIL, 120.0, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        assert min(p["soc_kwh"]) >= -1e-9
        assert max(p["soc_kwh"]) <= 200.0 + 1e-9
        assert min(p["soc_pct"]) >= -1e-9
        assert max(p["soc_pct"]) <= 100.0 + 1e-9

    def test_znamenko_vykonu_baterie(self):
        # Nad stropem baterie dodává (+), pod stropem se nabíjí (−).
        p = ps.prubeh_baterie(self.PROFIL, 120.0, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        assert p["baterie_kw"][8] > 0  # první interval špičky – baterie dodává
        assert p["baterie_kw"][0] == 0.0  # simulace startuje s plnou baterií, nemá co dobírat
        assert p["baterie_kw"][16] < 0  # po špičce se pod stropem dobíjí
        assert all(b <= 0 for b, o in zip(p["baterie_kw"], self.PROFIL) if o <= 120.0)

    def test_stropy_po_intervalech(self):
        # Model 2027 sráží každý měsíc jinak – strop se předává po intervalech.
        stropy = [120.0] * 20 + [150.0] * 20
        p = ps.prubeh_baterie(self.PROFIL, stropy, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        assert p["stropy_kw"] == stropy

    def test_spatny_pocet_stropu_je_chyba(self):
        with pytest.raises(ValueError):
            ps.prubeh_baterie(self.PROFIL, [120.0, 130.0], 100.0, 200.0, 0.25)

    def test_bez_baterie_je_prubeh_totozny_s_profilem(self):
        p = ps.prubeh_baterie(self.PROFIL, 120.0, 0.0, 0.0, 0.25)
        assert p["site_kw"] == self.PROFIL
        assert set(p["baterie_kw"]) == {0.0}


class TestUdalostiPrubehu:
    """Vypíchnuté momenty pro graf (roční/měsíční extrémy, chování baterie)."""

    PROFIL = [50.0] * 8 + [180.0] * 8 + [50.0] * 8 + [200.0] * 8 + [40.0] * 8
    MESICE = [1] * 20 + [2] * 20

    def _udalosti(self, rk=None):
        p = ps.prubeh_baterie(self.PROFIL, 120.0, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
        return ps.udalosti_prubehu(
            self.PROFIL, p["site_kw"], p["baterie_kw"], p["soc_pct"],
            self.MESICE, 0.25, rk_soucasna_kw=rk,
        )

    def _najdi(self, ud, typ, mesic=None):
        return [u for u in ud if u["typ"] == typ and (mesic is None or u["mesic"] == mesic)]

    def test_rocni_maximum_ukazuje_na_nejvyssi_odber(self):
        ud = self._udalosti()
        u = self._najdi(ud, "max_rok_bez")[0]
        assert u["hodnota"] == pytest.approx(200.0)
        assert self.PROFIL[u["index"]] == 200.0

    def test_mesicni_maxima_pro_kazdy_mesic(self):
        ud = self._udalosti()
        assert self._najdi(ud, "max_mesic_bez", 1)[0]["hodnota"] == pytest.approx(180.0)
        assert self._najdi(ud, "max_mesic_bez", 2)[0]["hodnota"] == pytest.approx(200.0)

    def test_minimum_roku(self):
        ud = self._udalosti()
        assert self._najdi(ud, "min_rok")[0]["hodnota"] == pytest.approx(40.0)

    def test_udalosti_baterie(self):
        ud = self._udalosti()
        assert self._najdi(ud, "max_vyboj")
        assert self._najdi(ud, "max_nabijeni")
        assert self._najdi(ud, "min_soc")[0]["jednotka"] == "%"

    def test_prekroceni_rk_jen_kdyz_se_deje(self):
        # Strop 120 kW se udrží → při RK 150 kW žádné překročení…
        assert not self._najdi(self._udalosti(rk=150.0), "prekroceni_rk")
        # …při RK 80 kW ano, v obou měsících.
        prekroceni = self._najdi(self._udalosti(rk=80.0), "prekroceni_rk")
        assert {u["mesic"] for u in prekroceni} == {1, 2}

    def test_udalosti_jsou_serazene_v_case(self):
        ud = self._udalosti(rk=80.0)
        assert [u["index"] for u in ud] == sorted(u["index"] for u in ud)

    def test_prazdny_profil(self):
        assert ps.udalosti_prubehu([], [], [], [], [], 0.25) == []


class TestPrubehPoMesicich:
    """Model 2027: každý měsíc má vlastní strop a startuje s plnou baterií."""

    PROFIL = [50.0] * 10 + [180.0] * 10 + [60.0] * 10 + [200.0] * 10
    MESICE = [1] * 20 + [2] * 20

    def test_delka_a_stropy_odpovidaji_mesicum(self):
        stropy = {1: 120.0, 2: 150.0}
        p = ps.prubeh_po_mesicich(self.PROFIL, self.MESICE, stropy, 100.0, 200.0, 0.25, 0.88)
        assert len(p["site_kw"]) == len(self.PROFIL)
        assert p["stropy_kw"][:20] == [120.0] * 20
        assert p["stropy_kw"][20:] == [150.0] * 20

    def test_kazdy_mesic_startuje_s_plnou_baterii(self):
        # Simulace 2027 počítá měsíce samostatně (ekonomika taky) – na začátku
        # února tedy baterie nesmí být „dojetá“ z ledna.
        stropy = {1: 120.0, 2: 150.0}
        p = ps.prubeh_po_mesicich(self.PROFIL, self.MESICE, stropy, 100.0, 200.0, 0.25, 0.88)
        assert p["soc_kwh"][20] == pytest.approx(200.0, abs=1.0)

    def test_soucty_odpovidaji_mesicnim_simulacim(self):
        stropy = {1: 120.0, 2: 150.0}
        p = ps.prubeh_po_mesicich(self.PROFIL, self.MESICE, stropy, 100.0, 200.0, 0.25, 0.88)
        nabito = 0.0
        vybito = 0.0
        for m, strop in stropy.items():
            cast = [v for v, mm in zip(self.PROFIL, self.MESICE) if mm == m]
            a, b = ps.energie_pri_stropu(cast, strop, 100.0, 200.0, 0.25, ucinnost_rt=0.88)
            nabito += a
            vybito += b
        assert p["nabito_kwh"] == pytest.approx(nabito)
        assert p["vybito_kwh"] == pytest.approx(vybito)

    def test_mesicni_stropy_z_metodiky_se_v_grafu_udrzi(self):
        # Stropy spočítané „srážej co to dá“ musí v průběhu opravdu držet.
        stropy = ps.mesicni_maxima_po_baterii(self.PROFIL, self.MESICE, 100.0, 200.0, 0.25, 0.88)
        p = ps.prubeh_po_mesicich(self.PROFIL, self.MESICE, stropy, 100.0, 200.0, 0.25, 0.88)
        for site, m in zip(p["site_kw"], self.MESICE):
            assert site <= stropy[m] + 1e-6


# ------------------------------------------- oprava 27. 7. 2026: fér baseline
class TestBaselineBezInvestice:
    """Baseline bez investice = levnější z {nedělat nic, optimalizovat}.

    Rezerva RK (PS-6) navyšuje cílová maxima optimalizace, ale dnešní stav ji
    nenese (je to naměřený fakt). U zákazníka, který dnes vědomě riskuje pokuty,
    proto umí optimalizace vyjít DRÁŽ – „úspora bez investice" pak nesmí vyjít
    záporně a přínos baterie se musí počítat proti dnešnímu nákladu.
    """

    CENA_ROCNI = 3030.78
    CENA_MESICNI = 281.823
    # Tvar odběru „hydry": RK 339 kW sjednaná pod maximy (340–372 kW).
    MAXIMA = {1: 340.0, 2: 336.0, 3: 324.0, 4: 355.0, 5: 372.0, 6: 366.0,
              7: 352.0, 8: 372.0, 9: 320.0, 10: 316.0, 11: 310.0, 12: 322.0}

    def _ek(self, rezerva, strop=312.79):
        profil, mesice = [], []
        for m, maximum in sorted(self.MAXIMA.items()):
            profil += [200.0, maximum]
            mesice += [m, m]
        return ps.ekonomika_2026(
            profil,
            mesice,
            rezervovana_kapacita_kw=339.0,
            cena_rezervace_kc_kw_rok=self.CENA_ROCNI,
            cena_prekroceni_kc_kw=ps.pokuta_prekroceni_rk_kc_kw(self.CENA_MESICNI),
            strop_kw=strop,
            cena_mesicni_rk_kc_kw_mesic=self.CENA_MESICNI,
            rezerva_rk_procenta=rezerva,
        )

    def test_rezerva_muze_zdrazit_optimalizaci_nad_dnesni_stav(self):
        # Předpoklad testu: s 5% rezervou je optimalizace RK dražší než dnešní RK.
        ek = self._ek(rezerva=5.0)
        assert ek.naklad_optimalni_bez_baterie > ek.soucasny_naklad_celkem

    def test_uspora_bez_investice_neni_nikdy_zaporna(self):
        for rezerva in (0.0, 5.0, 15.0):
            ek = self._ek(rezerva=rezerva)
            assert ek.uspora_bez_investice >= 0.0

    def test_baseline_je_levnejsi_z_obou_variant(self):
        ek = self._ek(rezerva=5.0)
        assert ek.naklad_baseline_bez_investice == pytest.approx(
            min(ek.soucasny_naklad_celkem, ek.naklad_optimalni_bez_baterie)
        )
        # Dražší optimalizace → baseline zůstává dnešní stav.
        assert ek.naklad_baseline_bez_investice == pytest.approx(ek.soucasny_naklad_celkem)

    def test_prinos_baterie_se_meri_proti_baseline(self):
        ek = self._ek(rezerva=5.0)
        assert ek.prinos_baterie == pytest.approx(
            ek.naklad_baseline_bez_investice
            - ek.novy_naklad_rezervace
            - ek.naklad_ztrat_baterie
        )

    def test_rozpad_uspory_zustava_konzistentni(self):
        for rezerva in (0.0, 5.0):
            ek = self._ek(rezerva=rezerva)
            assert ek.rocni_uspora == pytest.approx(
                ek.uspora_bez_investice + ek.prinos_baterie
            )

    def test_levnejsi_optimalizace_se_pouzije(self):
        # Bez rezervy je optimalizace RK levnější než dnešní stav → baseline = ona.
        ek = self._ek(rezerva=0.0)
        assert ek.naklad_optimalni_bez_baterie < ek.soucasny_naklad_celkem
        assert ek.naklad_baseline_bez_investice == pytest.approx(
            ek.naklad_optimalni_bez_baterie
        )
        assert ek.uspora_bez_investice > 0.0


class TestSymetrieRezervy2027:
    """Baseline 2027 nese rezervu stejně jako scénář s baterií.

    Dřív se baseline optimalizovala nad naměřenými maximy bez rezervy, zatímco
    scénář s baterií nad maximy × (1 + rezerva) → přínos baterie systematicky
    podhodnocený (nesymetrická opatrnost).
    """

    PROFIL = [100.0] * 8 + [200.0] * 8
    MESICE = [1] * 8 + [2] * 8

    def _ek(self, rezerva, rp_ze_smlouvy=300.0):
        return ps.ekonomika_2027(
            self.PROFIL,
            self.MESICE,
            rp_ze_smlouvy,  # RP ze smlouvy (default předimenzovaný)
            rp_ze_smlouvy,
            0.0,  # baterie 0 kW – zajímá nás jen volba RP
            0.0,
            P2027_CEZ_VN,
            optimalizovat_rp=True,
            rezerva_rk_procenta=rezerva,
        )

    def test_rezerva_zvedne_baseline_rp(self):
        # Únorové maximum 200 kW → bez rezervy RP 200, s 5% rezervou 210.
        assert self._ek(0.0)["optimalni_rp_bez_baterie_kw"] == pytest.approx(200.0)
        assert self._ek(5.0)["optimalni_rp_bez_baterie_kw"] == pytest.approx(210.0)

    def test_baseline_rp_odpovida_optimalizaci_nad_navysenymi_maximy(self):
        rezerva = 5.0
        ek = self._ek(rezerva)
        raw = ps._mesicni_maxima(self.PROFIL, self.MESICE)
        faktor = 1.0 + rezerva / 100.0
        _, rp = ps.optimalizuj_rp_2027({m: v * faktor for m, v in raw.items()}, P2027_CEZ_VN)
        assert ek["optimalni_rp_bez_baterie_kw"] == pytest.approx(rp)
        # Náklad se počítá nad SKUTEČNÝMI maximy – špička se platí za naměřené M.
        naklad, _, _ = ps._rocni_naklad_2027(rp, raw, P2027_CEZ_VN)
        assert ek["naklad_optimalni_bez_baterie"] == pytest.approx(naklad)

    def test_baseline_bere_levnejsi_z_obou_variant(self):
        ek = self._ek(5.0)
        assert ek["naklad_baseline_bez_investice"] == pytest.approx(
            min(ek["soucasny_rocni_naklad"], ek["naklad_optimalni_bez_baterie"])
        )
        assert ek["uspora_optimalizaci_bez_baterie"] >= 0.0

    def test_dnesni_rp_zustane_baseline_kdyz_je_levnejsi(self):
        # RP ze smlouvy 200 kW = optimum bez rezervy; s 5% rezervou by
        # optimalizace navrhla 210 kW, což je dráž → baseline zůstane dnešní stav.
        ek = self._ek(5.0, rp_ze_smlouvy=200.0)
        assert ek["naklad_optimalni_bez_baterie"] > ek["soucasny_rocni_naklad"]
        assert ek["naklad_baseline_bez_investice"] == pytest.approx(
            ek["soucasny_rocni_naklad"]
        )
        assert ek["uspora_optimalizaci_bez_baterie"] == pytest.approx(0.0)

    def test_rozpad_uspory_zustava_konzistentni(self):
        for rezerva in (0.0, 5.0):
            ek = self._ek(rezerva)
            assert ek["uspora_optimalizaci_bez_baterie"] + ek["prinos_baterie"] == pytest.approx(
                ek["rocni_uspora"]
            )


class TestPaybackRidiDoporuceni:
    """Doporučení se řídí reálnou návratností z kombinovaného cash flow.

    Dřív rozhodovala prostá návratnost modelu 2026, takže varianta s výbornou
    ekonomikou 2027 (a slabým rokem 2026) vyšla „nedoporučeno", i když se
    investice reálně vrátí dřív než za firemní práh.
    """

    NPV = ps.NastaveniNpv(
        diskontni_sazba=0.08, horizont_roky=10,
        oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0,
    )

    def test_payback_interpoluje_zlomek_roku(self):
        # Investice 1000, přínos 400/rok → 2,5 roku.
        assert ps._payback_z_cash_flow(1000.0, [400.0] * 10) == pytest.approx(2.5)

    def test_payback_presne_na_konci_roku(self):
        assert ps._payback_z_cash_flow(1000.0, [500.0] * 4) == pytest.approx(2.0)

    def test_bez_navratu_v_horizontu_vraci_none(self):
        assert ps._payback_z_cash_flow(1000.0, [50.0] * 10) is None

    def test_zaporne_cash_flow_neprojde(self):
        assert ps._payback_z_cash_flow(1000.0, [-100.0] * 10) is None

    def _varianta(self, parametry_2027):
        # Profil s jednou špičkou v měsíci: baterie ji srazí.
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        baterie = ps.Baterie(
            id=1, nazev="BESS", vykon_kw=200.0, kapacita_kwh=400.0,
            cena_kc=1_000_000.0, ucinnost_rt=1.0,
        )
        return ps.spocti_variantu(
            baterie,
            1,
            profil,
            mesice,
            rezervovana_kapacita_kw=400.0,
            cena_rezervace_kc_kw_rok=3030.78,
            cena_prekroceni_kc_kw=ps.pokuta_prekroceni_rk_kc_kw(281.823),
            max_navratnost_roky=5.0,
            parametry_2027=parametry_2027,
            cena_energie_kc_mwh=0.0,
            rezerva_rk_procenta=0.0,
            cena_mesicni_rk_kc_kw_mesic=281.823,
            npv_nastaveni=self.NPV,
        )

    def test_varianta_nese_payback(self):
        v = self._varianta(P2027_CEZ_VN)
        assert v.payback_roky is not None
        assert v.payback_roky > 0

    def test_payback_odpovida_cash_flow_z_tabulky(self):
        # Musí souhlasit s řádkem ◄ v tabulce „Ekonomika po letech" (cf_kum_kc).
        v = self._varianta(P2027_CEZ_VN)
        prvni_kladny = next(r["rok"] for r in v.roky if r["cf_kum_kc"] >= 0)
        assert prvni_kladny - 1 <= v.payback_roky <= prvni_kladny

    def test_doporuceni_se_ridi_paybackem_ne_rokem_2026(self):
        v = self._varianta(P2027_CEZ_VN)
        assert v.doporuceno is (v.payback_roky is not None and v.payback_roky <= 5.0)

    def test_silny_rok_2027_neprepadne_kvuli_slabemu_2026(self):
        # Model 2027 přináší mnohem víc než 2026 → reálná návratnost je kratší
        # než ta z modelu 2026 a doporučení nesmí viset na roce 2026.
        v = self._varianta(P2027_CEZ_VN)
        if v.navratnost_2027 is not None and v.navratnost_2026 is not None:
            if v.navratnost_2027 < v.navratnost_2026:
                assert v.payback_roky < v.navratnost_2026

    def test_bez_sazeb_2027_se_pocita_cely_horizont_dle_2026(self):
        v = self._varianta(None)
        assert v.npv_pouzit_model_2027 is False
        # Bez sazeb 2027 je payback ≈ prostá návratnost 2026 (bez O&M a degradace).
        assert v.payback_roky == pytest.approx(v.navratnost_2026, rel=0.02)


# ------------------- rozhodnuto 27. 7. 2026: rozhoduje jen model NTS 2027
class TestJenModel2027Rozhoduje:
    """Model 2026 je informativní – NPV, výběr i doporučení jedou na 2027.

    Co se dnes nabízí, se instaluje a spouští už v NTS 2027, takže rok na
    starém tarifu nikdo neodžije.
    """

    NPV = ps.NastaveniNpv(
        diskontni_sazba=0.0, horizont_roky=10,
        oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0,
    )

    def _profil(self):
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        return profil, mesice

    def _varianta(self, **kw):
        profil, mesice = self._profil()
        baterie = ps.Baterie(
            id=1, nazev="BESS", vykon_kw=200.0, kapacita_kwh=400.0,
            cena_kc=1_000_000.0, ucinnost_rt=1.0,
        )
        parametry = {
            "rezervovana_kapacita_kw": 400.0,
            "cena_rezervace_kc_kw_rok": 3030.78,
            "cena_prekroceni_kc_kw": ps.pokuta_prekroceni_rk_kc_kw(281.823),
            "max_navratnost_roky": 5.0,
            "parametry_2027": P2027_CEZ_VN,
            "cena_energie_kc_mwh": 0.0,
            "rezerva_rk_procenta": 0.0,
            "cena_mesicni_rk_kc_kw_mesic": 281.823,
            "npv_nastaveni": self.NPV,
        }
        parametry.update(kw)
        return ps.spocti_variantu(baterie, 1, profil, mesice, **parametry)

    def test_vsechny_roky_cash_flow_jsou_2027(self):
        v = self._varianta()
        assert {r["model"] for r in v.roky} == {"2027"}

    def test_cash_flow_stoji_na_rocni_uspore_2027(self):
        # Rozhodnuto 27. 7. 2026: projekt se prodává jako celek „dnešní faktura
        # → faktura po instalaci", takže do CF jde celá úspora 2027, ne jen
        # přínos baterie. Rozpad zůstává vidět v kartě 2027.
        v = self._varianta()
        assert v.roky[0]["prinos_kc"] == pytest.approx(
            v.ekonomika_2027["rocni_uspora"], abs=0.01
        )

    def test_zmena_ekonomiky_2026_neovlivni_npv(self):
        # Jiná dnešní RK mění celou ekonomiku 2026, NPV ne – to jede výhradně
        # na modelu 2027, kde je RP dané smlouvou o připojení.
        a = self._varianta(rezervovana_kapacita_kw=400.0, rezervovany_prikon_kw=600.0)
        b = self._varianta(rezervovana_kapacita_kw=520.0, rezervovany_prikon_kw=600.0)
        assert a.rocni_uspora_2026 != b.rocni_uspora_2026  # model 2026 se liší…
        assert a.npv_kc == pytest.approx(b.npv_kc)  # …NPV ne
        assert a.payback_roky == pytest.approx(b.payback_roky)
        assert a.doporuceno == b.doporuceno

    def test_npv_sedi_na_rucni_vypocet_z_uspory_2027(self):
        # Bez diskontu, O&M i degradace: NPV = horizont × úspora 2027 − cena.
        v = self._varianta()
        ocekavane = self.NPV.horizont_roky * v.ekonomika_2027["rocni_uspora"] - v.cena_celkem_kc
        assert v.npv_kc == pytest.approx(ocekavane, abs=0.01)

    def test_bez_sazeb_2027_spadne_na_model_2026(self):
        v = self._varianta(parametry_2027=None)
        assert v.npv_pouzit_model_2027 is False
        assert {r["model"] for r in v.roky} == {"2026"}

    def test_tie_break_je_realna_navratnost(self):
        # Řadicí klíč: NPV sestupně, pak reálná návratnost – ne model 2026.
        v = self._varianta()
        assert v._radici_klic()[1] == (
            v.payback_roky if v.payback_roky is not None else float("inf")
        )


class TestObaZakladyNpv:
    """Obě varianty základu NPV se počítají vždy – UI mezi nimi jen přepíná."""

    NPV = ps.NastaveniNpv(
        diskontni_sazba=0.0, horizont_roky=10,
        oam_procenta_capex_rok=0.0, degradace_uspor_procenta_rok=0.0,
    )

    def _varianta(self, **kw):
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        baterie = ps.Baterie(
            id=1, nazev="BESS", vykon_kw=200.0, kapacita_kwh=400.0,
            cena_kc=1_000_000.0, ucinnost_rt=1.0,
        )
        parametry = {
            "rezervovana_kapacita_kw": 400.0,
            "cena_rezervace_kc_kw_rok": 3030.78,
            "cena_prekroceni_kc_kw": ps.pokuta_prekroceni_rk_kc_kw(281.823),
            "max_navratnost_roky": 5.0,
            "parametry_2027": P2027_CEZ_VN,
            "cena_energie_kc_mwh": 0.0,
            "rezerva_rk_procenta": 0.0,
            "cena_mesicni_rk_kc_kw_mesic": 281.823,
            "npv_nastaveni": self.NPV,
            "rezervovany_prikon_kw": 600.0,  # ať je co optimalizovat i bez baterie
            "uvazovat_snizeni_rp": True,
        }
        parametry.update(kw)
        return ps.spocti_variantu(baterie, 1, profil, mesice, **parametry)

    def test_vystup_nese_obe_sady(self):
        v = self._varianta()
        assert set(v.npv_varianty) == set(ps.ZAKLADY_NPV)
        for sada in v.npv_varianty.values():
            for klic in ("npv_kc", "irr", "payback_roky", "doporuceno", "roky"):
                assert klic in sada

    def test_kazda_sada_sedi_na_svuj_zaklad(self):
        v = self._varianta()
        h = self.NPV.horizont_roky
        assert v.npv_varianty["uspora"]["npv_kc"] == pytest.approx(
            h * v.ekonomika_2027["rocni_uspora"] - v.cena_celkem_kc, abs=0.01
        )
        assert v.npv_varianty["prinos_baterie"]["npv_kc"] == pytest.approx(
            h * v.ekonomika_2027["prinos_baterie"] - v.cena_celkem_kc, abs=0.01
        )

    def test_prisnejsi_zaklad_neni_nikdy_vyhodnejsi(self):
        # Přínos baterie ≤ celá úspora (liší se o úsporu bez investice).
        v = self._varianta()
        assert (
            v.npv_varianty["prinos_baterie"]["npv_kc"] <= v.npv_varianty["uspora"]["npv_kc"] + 1e-6
        )

    def test_vychozi_zaklad_se_propise_do_plochych_poli(self):
        v = self._varianta()
        assert v.zaklad_npv == ps.VYCHOZI_ZAKLAD_NPV
        vychozi = v.npv_varianty[ps.VYCHOZI_ZAKLAD_NPV]
        assert v.npv_kc == pytest.approx(vychozi["npv_kc"])
        assert v.doporuceno == vychozi["doporuceno"]
        assert v.roky == vychozi["roky"]

    def test_volba_zakladu_prepne_ploche_hodnoty(self):
        v = self._varianta(zaklad_npv=ps.ZAKLAD_NPV_PRINOS_BATERIE)
        assert v.zaklad_npv == ps.ZAKLAD_NPV_PRINOS_BATERIE
        assert v.npv_kc == pytest.approx(v.npv_varianty["prinos_baterie"]["npv_kc"])
        # Druhá sada zůstává k dispozici pro přepínač v UI.
        assert v.npv_varianty["uspora"]["npv_kc"] != pytest.approx(v.npv_kc)

    def test_neznamy_zaklad_spadne_na_vychozi(self):
        v = self._varianta(zaklad_npv="nesmysl")
        assert v.zaklad_npv == ps.VYCHOZI_ZAKLAD_NPV

    def test_zaklad_ridi_poradi_variant(self):
        # Řadicí klíč staví na plochém NPV → volba základu může změnit vítěze.
        profil, mesice = [], []
        for m in range(1, 13):
            profil += [200.0] * 6 + [400.0] + [200.0] * 5
            mesice += [m] * 12
        katalog = [
            ps.Baterie(id=1, nazev="Malý", vykon_kw=30.0, kapacita_kwh=100.0,
                       cena_kc=300_000.0, ucinnost_rt=1.0),
            ps.Baterie(id=2, nazev="Velký", vykon_kw=190.0, kapacita_kwh=600.0,
                       cena_kc=2_400_000.0, ucinnost_rt=1.0),
        ]
        for zaklad in ps.ZAKLADY_NPV:
            vysledek = ps.vyber_reseni(
                katalog, profil, mesice, 400.0, 3030.78,
                ps.pokuta_prekroceni_rk_kc_kw(281.823),
                max_navratnost_roky=100.0, max_pocet_kusu=1,
                parametry_2027=P2027_CEZ_VN, cena_energie_kc_mwh=0.0,
                rezerva_rk_procenta=0.0, cena_mesicni_rk_kc_kw_mesic=281.823,
                npv_nastaveni=self.NPV, zaklad_npv=zaklad,
            )
            npv_vitez = vysledek.doporucena.npv_kc
            assert all(v.npv_kc <= npv_vitez + 1e-6 for v in vysledek.varianty)
            assert all(v.zaklad_npv == zaklad for v in vysledek.varianty)


# ------------------------------------------- návratnost za horizontem (FE→BE)
class TestNavratnostZaHorizontem:
    """Odhad roku návratnosti za horizontem NPV.

    Do 6. 8. 2026 to počítal prohlížeč (`PeakShavingPanel.navratnostZaHorizontem`),
    teď je to na serveru. Testy drží přesně to chování, které měl FE – ať se
    obchodníkovi po přesunu nezmění čísla pod rukama.
    """

    @staticmethod
    def _rozpis(investice, cf_roky):
        """Minimální rozpis po letech (jen pole, která odhad čte)."""
        kum = -investice
        radky = []
        for rok, cf in enumerate(cf_roky, start=1):
            kum += cf
            radky.append({"rok": rok, "cf_kc": cf, "cf_kum_kc": kum})
        return radky

    def test_vraceno_v_horizontu_nema_odhad(self):
        # Kumulace končí v plusu → varianta má reálný payback, odhad je zbytečný.
        rozpis = self._rozpis(100.0, [40.0] * 5)
        assert ps.navratnost_za_horizontem(rozpis) is None

    def test_konstantni_cf_dopocita_rok_za_horizontem(self):
        # Investice 1000, 10 let po 50 → po horizontu chybí 500, dalších 10 let
        # po 50 (tempo poklesu = 1, CF neklesá) → 20 let přesně.
        rozpis = self._rozpis(1000.0, [50.0] * 10)
        assert ps.navratnost_za_horizontem(rozpis) == pytest.approx(20.0)

    def test_klesajici_cf_prodlouzi_navratnost(self):
        # CF klesá o 10 % ročně (degradace úspor): za horizontem se ještě vrátí,
        # ale později, než kdyby CF drželo hodnotu posledního roku.
        cf = [100.0 * 0.9**i for i in range(10)]
        rozpis = self._rozpis(800.0, cf)
        odhad = ps.navratnost_za_horizontem(rozpis)
        zbyva = 800.0 - sum(cf)
        assert odhad is not None
        assert odhad > 10.0 + zbyva / cf[-1]

    def test_na_hrane_soucet_rady_presne_pokryje_dluh(self):
        # Nekonečný součet klesající řady == zbývající dluh: v konečném čase se
        # nevrátí, takže „nevrátí se". Hraniční případ, ať se chování nerozjede.
        cf = [100.0 * 0.9**i for i in range(10)]
        rozpis = self._rozpis(1000.0, cf)
        assert ps.navratnost_za_horizontem(rozpis) is None

    def test_prilis_strme_klesajici_cf_se_nevrati_nikdy(self):
        # Součet klesající řady za horizontem nepokryje zbytek dluhu → None.
        cf = [100.0 * 0.3**i for i in range(10)]
        rozpis = self._rozpis(1_000_000.0, cf)
        assert ps.navratnost_za_horizontem(rozpis) is None

    def test_zaporne_cf_se_nevrati_nikdy(self):
        # Úspora nepokryje ani O&M → nevrátí se, ať se čeká jakkoli dlouho.
        rozpis = self._rozpis(1000.0, [-5.0] * 10)
        assert ps.navratnost_za_horizontem(rozpis) is None

    def test_rostouci_cf_se_neextrapoluje_nahoru(self):
        # Rostoucí CF se bere jako konstantní (žádný optimismus navíc): po 5 letech
        # chybí 670, poslední CF je 100 → 6,7 roku navíc. Kdyby se růst 80→100
        # protahoval dál, vyšlo by míň – a to schválně nedělá.
        rozpis = self._rozpis(1000.0, [40.0, 50.0, 60.0, 80.0, 100.0])
        assert ps.navratnost_za_horizontem(rozpis) == pytest.approx(11.7)

    def test_prazdny_rozpis(self):
        assert ps.navratnost_za_horizontem([]) is None
        assert ps.navratnost_za_horizontem(None) is None


class TestDoplneniOdhaduDoUlozenych:
    """Starší uložená řešení pole nemají – doplní se cestou ven z API."""

    def _popis(self):
        rozpis = TestNavratnostZaHorizontem._rozpis(1000.0, [50.0] * 10)
        varianta = {
            "nazev": "Stará varianta",
            "payback_roky": None,
            "roky": rozpis,
            "npv_varianty": {"uspora": {"payback_roky": None, "roky": rozpis}},
        }
        return {"varianty": [varianta], "doporucena": varianta}

    def test_dopocita_se_i_do_npv_variant(self):
        out = ps.doplnit_odhad_navratnosti(self._popis())
        assert out["varianty"][0]["navratnost_odhad_roky"] == pytest.approx(20.0)
        assert out["doporucena"]["navratnost_odhad_roky"] == pytest.approx(20.0)
        assert out["varianty"][0]["npv_varianty"]["uspora"][
            "navratnost_odhad_roky"
        ] == pytest.approx(20.0)

    def test_puvodni_objekt_zustane_nedotcen(self):
        # Dopočet nesmí přepsat uložené řešení – jede nad kopií.
        popis = self._popis()
        ps.doplnit_odhad_navratnosti(popis)
        assert "navratnost_odhad_roky" not in popis["varianty"][0]

    def test_nove_vysledky_se_neprepisuji(self):
        popis = self._popis()
        popis["varianty"][0]["navratnost_odhad_roky"] = 42.0
        out = ps.doplnit_odhad_navratnosti(popis)
        assert out["varianty"][0]["navratnost_odhad_roky"] == 42.0

    def test_jine_reseni_projde_beze_zmeny(self):
        assert ps.doplnit_odhad_navratnosti({"neco": 1}) == {"neco": 1}
