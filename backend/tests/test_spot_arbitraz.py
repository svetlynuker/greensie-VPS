# -*- coding: utf-8 -*-
"""Testy obchodní flexibility baterie (`app/nabidkovac/spot_arbitraz.py`).

Modul je bez závislostí na DB/FastAPI, takže se testuje přímo nad syntetickými
cenami a profily. Kromě dílčích vlastností se tu ověřuje i to nejdůležitější:
že **peak shaving nikdy nepřijde k újmě** kvůli obchodování a že prahová
strategie je blízko optimálnímu plánu (referenční dynamické programování
je součástí testu – v produkčním kódu záměrně není, protože potřebuje znát
celý úsek dopředu a hrubě diskretizuje stav nabití).
"""

import math

import pytest

from app.nabidkovac import peak_shaving as ps
from app.nabidkovac import spot_arbitraz as sa


def _ceny_pila(pocet_dnu: int = 1, nizka: float = 500.0, vysoka: float = 4000.0) -> list[float]:
    """Den po čtvrthodinách: levná noc (0–6 h), drahý večer (17–21 h), jinak střed."""
    ceny = []
    for _ in range(pocet_dnu):
        for i in range(96):
            hodina = i / 4
            if hodina < 6:
                ceny.append(nizka)
            elif 17 <= hodina < 21:
                ceny.append(vysoka)
            else:
                ceny.append((nizka + vysoka) / 2)
    return ceny


def _odber_konstantni(pocet_dnu: int = 1, kw: float = 100.0) -> list[float]:
    return [kw] * (96 * pocet_dnu)


# ------------------------------------------------------------------- ceny
class TestCeny:
    """Skutečná cena pro zákazníka: marže obchodníka + regulované složky."""

    def test_nakup_pricita_marzi_regulovane_i_dan(self):
        n = sa.NastaveniSpot(
            marze_nakup_kc_mwh=200.0,
            regulovane_nakup_kc_mwh=260.0,
            dan_z_elektriny_kc_mwh=28.3,
        )
        assert sa.cena_nakup_kc_mwh(2000.0, n) == pytest.approx(2488.3)

    def test_prodej_odecita_marzi(self):
        n = sa.NastaveniSpot(marze_prodej_kc_mwh=200.0)
        assert sa.cena_prodej_kc_mwh(2000.0, n) == pytest.approx(1800.0)

    def test_krytim_vlastni_spotreby_se_vyhne_i_regulovanym_slozkam(self):
        """Klíčová asymetrie: vybít do odběru je cennější než dodat do sítě."""
        n = sa.NastaveniSpot()
        assert sa.cena_nakup_kc_mwh(2000.0, n) > sa.cena_prodej_kc_mwh(2000.0, n)
        # Rozdíl = 2× marže + regulované složky.
        assert sa.cena_nakup_kc_mwh(2000.0, n) - sa.cena_prodej_kc_mwh(2000.0, n) == pytest.approx(
            2 * 200.0 + 260.0
        )

    def test_zaporna_spotova_cena_je_pro_zakaznika_stale_naklad(self):
        # Při −300 Kč/MWh zákazník s marží a distribucí pořád platí.
        n = sa.NastaveniSpot()
        assert sa.cena_nakup_kc_mwh(-300.0, n) == pytest.approx(160.0)


class TestNakladOpotrebeni:
    """CAPEX / (cykly × kapacita) – bez toho by model chtěl obří baterie."""

    def test_typicky_kontejner(self):
        # 7 mil. Kč / (6 000 cyklů × 1 000 kWh) = 1,167 Kč/kWh = 1 167 Kč/MWh.
        assert sa.naklad_opotrebeni_kc_mwh(7_000_000, 1000, 6000) == pytest.approx(1166.667, abs=0.01)

    def test_vice_cyklu_znamena_nizsi_naklad(self):
        drazsi = sa.naklad_opotrebeni_kc_mwh(6_000_000, 1000, 5000)
        levnejsi = sa.naklad_opotrebeni_kc_mwh(6_000_000, 1000, 10000)
        assert levnejsi == pytest.approx(drazsi / 2)

    def test_chybejici_cykly_padnou_na_default(self):
        assert sa.naklad_opotrebeni_kc_mwh(6_000_000, 1000, None) == pytest.approx(
            sa.naklad_opotrebeni_kc_mwh(6_000_000, 1000, sa.VYCHOZI_CYKLU_ZIVOTNOSTI)
        )

    def test_nulova_cena_nebo_kapacita_neshodi_vypocet(self):
        assert sa.naklad_opotrebeni_kc_mwh(0, 1000, 6000) == 0.0
        assert sa.naklad_opotrebeni_kc_mwh(1_000_000, 0, 6000) == 0.0


# ---------------------------------------- minimální trajektorie peak shavingu
class TestMinimalniSocTrajektorie:
    """Dolní hranice nabití, pod kterou obchod nesmí sáhnout."""

    def test_bez_spicek_je_nulova(self):
        odber = [100.0] * 20
        minimum = sa.minimalni_soc_trajektorie(odber, 200.0, 50.0, 100.0)
        assert minimum == [0.0] * 20

    def test_pred_spickou_roste(self):
        # Poslední interval je špička 100 kW nad strop → 25 kWh na AC straně.
        odber = [100.0, 100.0, 300.0]
        minimum = sa.minimalni_soc_trajektorie(
            odber, 200.0, 500.0, 1000.0, interval_h=0.25, ucinnost_rt=1.0
        )
        assert minimum[2] == pytest.approx(25.0)
        # Před špičkou stačí méně, protože se dá dobíjet (100 kW pod stropem).
        assert minimum[1] < minimum[2]

    def test_dlouha_spicka_scita_potrebu(self):
        odber = [400.0, 400.0]  # 2× 200 kW nad strop 200
        minimum = sa.minimalni_soc_trajektorie(
            odber, 200.0, 500.0, 1000.0, interval_h=0.25, ucinnost_rt=1.0
        )
        assert minimum[0] == pytest.approx(100.0)  # 2 × 50 kWh
        assert minimum[1] == pytest.approx(50.0)

    def test_ztraty_zvysuji_potrebu(self):
        odber = [400.0]
        bez_ztrat = sa.minimalni_soc_trajektorie(
            odber, 200.0, 500.0, 1000.0, interval_h=0.25, ucinnost_rt=1.0
        )
        se_ztratami = sa.minimalni_soc_trajektorie(
            odber, 200.0, 500.0, 1000.0, interval_h=0.25, ucinnost_rt=0.88
        )
        assert se_ztratami[0] > bez_ztrat[0]

    def test_nikdy_nepresahne_kapacitu(self):
        odber = [10_000.0] * 50
        minimum = sa.minimalni_soc_trajektorie(odber, 100.0, 500.0, 200.0)
        assert max(minimum) <= 200.0


# ------------------------------------------------------------- simulace úseku
class TestSimulaceUseku:
    """Fyzika a priority jedné simulace."""

    def test_arbitraz_na_pile_vydelava(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=500.0, vykon_kw=100.0, kapacita_kwh=200.0,
            n=sa.NastaveniSpot(), prah_nakup_kc_mwh=500.0, prah_prodej_kc_mwh=4000.0,
            pocatecni_soc_kwh=0.0,
        )
        assert v.zisk_kc > 0
        assert v.ze_site_kwh > 0
        assert v.do_odberu_kwh > 0

    def test_bez_prahu_se_neobchoduje(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=500.0, vykon_kw=100.0, kapacita_kwh=200.0,
            n=sa.NastaveniSpot(), prah_nakup_kc_mwh=float("-inf"),
            prah_prodej_kc_mwh=float("inf"), pocatecni_soc_kwh=0.0,
        )
        assert v.obchodni_vybito_kwh == pytest.approx(0.0)
        assert v.zisk_kc == pytest.approx(0.0)

    def test_peak_shaving_ma_prednost_pred_obchodem(self):
        """Špička se srazí, i když je cena nízká a obchod by radši nabíjel."""
        # Levná cena celý den (obchod by chtěl nabíjet), špička nad stropem.
        ceny = [500.0] * 8
        odber = [100.0, 100.0, 100.0, 100.0, 300.0, 300.0, 100.0, 100.0]
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=200.0, vykon_kw=200.0, kapacita_kwh=500.0,
            n=sa.NastaveniSpot(), prah_nakup_kc_mwh=1000.0, prah_prodej_kc_mwh=5000.0,
            interval_h=0.25, ucinnost_rt=1.0,
        )
        assert v.prekroceni_stropu_kw == pytest.approx(0.0)
        assert v.max_site_kw <= 200.0 + 1e-6
        assert v.ps_vybito_kwh == pytest.approx(2 * 100.0 * 0.25)

    def test_nabijeni_nikdy_neprekroci_strop(self):
        """V režimu SPOT je strop naměřené maximum – nabíjení ho nesmí zvednout."""
        ceny = [100.0] * 20  # trvale levno → obchod chce nabíjet co nejvíc
        odber = [180.0] * 20
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=200.0, vykon_kw=500.0, kapacita_kwh=1000.0,
            n=sa.NastaveniSpot(), prah_nakup_kc_mwh=100.0, prah_prodej_kc_mwh=9999.0,
            interval_h=0.25, ucinnost_rt=1.0, pocatecni_soc_kwh=0.0,
        )
        assert v.max_site_kw <= 200.0 + 1e-6

    def test_zakazany_export_znamena_jen_posun_vlastni_spotreby(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=20.0)  # malý odběr → přebytek by šel do sítě
        n = sa.NastaveniSpot(umoznit_export=False)
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=500.0, vykon_kw=100.0, kapacita_kwh=200.0,
            n=n, prah_nakup_kc_mwh=500.0, prah_prodej_kc_mwh=4000.0, pocatecni_soc_kwh=0.0,
        )
        assert v.do_site_kwh == pytest.approx(0.0)

    def test_export_se_omezi_limitem(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=0.0)
        n = sa.NastaveniSpot(max_export_kw=10.0)
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=500.0, vykon_kw=100.0, kapacita_kwh=200.0,
            n=n, prah_nakup_kc_mwh=500.0, prah_prodej_kc_mwh=4000.0,
            interval_h=0.25, pocatecni_soc_kwh=0.0,
        )
        # 4 hodiny drahého okna × 10 kW = nejvýš 40 kWh za den.
        assert v.do_site_kwh <= 40.0 + 1e-6

    def test_bezpecnostni_rezerva_ubira_obchodu_kapacitu(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        bez_rezervy = sa.simuluj_usek(
            ceny, odber, 500.0, 100.0, 200.0, sa.NastaveniSpot(bezpecnostni_rezerva_procenta=0.0),
            500.0, 4000.0, pocatecni_soc_kwh=200.0,
        )
        s_rezervou = sa.simuluj_usek(
            ceny, odber, 500.0, 100.0, 200.0, sa.NastaveniSpot(bezpecnostni_rezerva_procenta=50.0),
            500.0, 4000.0, pocatecni_soc_kwh=200.0,
        )
        assert s_rezervou.obchodni_vybito_kwh < bez_rezervy.obchodni_vybito_kwh

    def test_opotrebeni_snizuje_zisk(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        args = dict(strop_kw=500.0, vykon_kw=100.0, kapacita_kwh=200.0, n=sa.NastaveniSpot(),
                    prah_nakup_kc_mwh=500.0, prah_prodej_kc_mwh=4000.0, pocatecni_soc_kwh=0.0)
        bez = sa.simuluj_usek(ceny, odber, opotrebeni_kc_mwh=0.0, **args)
        s_opotrebenim = sa.simuluj_usek(ceny, odber, opotrebeni_kc_mwh=1000.0, **args)
        assert s_opotrebenim.zisk_kc < bez.zisk_kc
        assert s_opotrebenim.naklad_opotrebeni_kc > 0

    def test_prazdna_baterie_hlasi_prekroceni_stropu(self):
        ceny = [2000.0] * 4
        odber = [500.0] * 4  # strop 100 kW, baterie nemá čím srážet
        v = sa.simuluj_usek(
            ceny, odber, strop_kw=100.0, vykon_kw=50.0, kapacita_kwh=10.0,
            n=sa.NastaveniSpot(), prah_nakup_kc_mwh=0.0, prah_prodej_kc_mwh=9999.0,
            interval_h=0.25, ucinnost_rt=1.0, pocatecni_soc_kwh=0.0,
        )
        assert v.prekroceni_stropu_kw > 0


class TestOptimalizacePrahu:
    """Kalibrace denních cenových prahů."""

    def test_najde_ziskove_prahy_na_pile(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        prah_n, prah_p, v = sa.optimalizuj_prahy(
            ceny, odber, 500.0, 100.0, 200.0, sa.NastaveniSpot(), 0.0, 0.25, 0.88, 0.0, None
        )
        assert v.zisk_kc > 0
        assert prah_n < prah_p

    def test_ploche_ceny_neobchoduji(self):
        """Bez rozkmitu se nesmí cyklovat – jinak by baterie jen platila ztráty."""
        ceny = [2000.0] * 96
        odber = _odber_konstantni(kw=200.0)
        _, _, v = sa.optimalizuj_prahy(
            ceny, odber, 500.0, 100.0, 200.0, sa.NastaveniSpot(), 1000.0, 0.25, 0.88, 0.0, None
        )
        assert v.obchodni_vybito_kwh == pytest.approx(0.0)
        assert v.zisk_kc == pytest.approx(0.0)

    def test_vysoke_opotrebeni_obchod_zastavi(self):
        ceny = _ceny_pila(nizka=1800.0, vysoka=2200.0)  # spread 400 Kč/MWh
        odber = _odber_konstantni(kw=200.0)
        _, _, v = sa.optimalizuj_prahy(
            ceny, odber, 500.0, 100.0, 200.0, sa.NastaveniSpot(), 5000.0, 0.25, 0.88, 0.0, None
        )
        assert v.zisk_kc == pytest.approx(0.0)


# ------------------------------------------------------- kvalita proti optimu
def _dp_optimum(
    ceny: list[float], odber: list[float], vykon_kw: float, kapacita_kwh: float,
    n: sa.NastaveniSpot, interval_h: float = 0.25, ucinnost_rt: float = 0.88,
    urovni: int = 40,
) -> float:
    """Referenční optimum jednoho úseku dynamickým programováním.

    Slouží jen v testu jako měřítko kvality prahové strategie. Potřebuje znát
    celý úsek dopředu a diskretizuje stav nabití, proto v produkčním kódu není.
    Bez peak shavingu (strop je nekonečný), baterie začíná i končí prázdná.
    """
    eta = math.sqrt(ucinnost_rt)
    krok = kapacita_kwh / urovni
    max_kroku = max(1, int(vykon_kw * interval_h / krok))
    NEG = float("-inf")
    hodnota = [NEG] * (urovni + 1)
    hodnota[0] = 0.0
    for i, spot in enumerate(ceny):
        c_nakup = sa.cena_nakup_kc_mwh(spot, n)
        c_prodej = sa.cena_prodej_kc_mwh(spot, n)
        nova = [NEG] * (urovni + 1)
        for s in range(urovni + 1):
            if hodnota[s] == NEG:
                continue
            for d in range(-max_kroku, max_kroku + 1):
                cil = s + d
                if cil < 0 or cil > urovni:
                    continue
                if d > 0:
                    ze_site = d * krok / eta
                    if ze_site > vykon_kw * interval_h + 1e-9:
                        continue
                    zmena = -(ze_site / 1000.0) * c_nakup
                elif d < 0:
                    na_ac = -d * krok * eta
                    if na_ac > vykon_kw * interval_h + 1e-9:
                        continue
                    # Vybití nejdřív krylo odběr (cena nákupu), zbytek do sítě.
                    do_odberu = min(na_ac, odber[i] * interval_h)
                    do_site = na_ac - do_odberu
                    zmena = (do_odberu / 1000.0) * c_nakup + (do_site / 1000.0) * c_prodej
                else:
                    zmena = 0.0
                if hodnota[s] + zmena > nova[cil]:
                    nova[cil] = hodnota[s] + zmena
        hodnota = nova
    return max(hodnota[0], 0.0)


class TestKvalitaProtiOptimu:
    """Prahová strategie musí být blízko optimálního plánu."""

    def test_na_pile_dosahne_vetsiny_optima(self):
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        n = sa.NastaveniSpot(bezpecnostni_rezerva_procenta=0.0)
        _, _, v = sa.optimalizuj_prahy(
            ceny, odber, 100_000.0, 100.0, 200.0, n, 0.0, 0.25, 0.88, 0.0, None
        )
        optimum = _dp_optimum(ceny, odber, 100.0, 200.0, n)
        assert optimum > 0
        assert v.zisk_kc >= 0.9 * optimum

    def test_nikdy_neprekroci_optimum(self):
        """Heuristika nemůže být lepší než optimální plán (kontrola konzistence)."""
        ceny = _ceny_pila()
        odber = _odber_konstantni(kw=200.0)
        n = sa.NastaveniSpot(bezpecnostni_rezerva_procenta=0.0)
        _, _, v = sa.optimalizuj_prahy(
            ceny, odber, 100_000.0, 100.0, 200.0, n, 0.0, 0.25, 0.88, 0.0, None
        )
        optimum = _dp_optimum(ceny, odber, 100.0, 200.0, n)
        assert v.zisk_kc <= optimum * 1.02  # 2 % na diskretizaci DP


# --------------------------------------------------------- kandidátní stropy
class TestKandidatniStropy:
    def test_od_udrzitelneho_k_maximu(self):
        stropy = sa.kandidatni_stropy(100.0, 200.0, pocet=3)
        assert stropy == [100.0, 150.0, 200.0]

    def test_shodne_hodnoty_daji_jediny_kandidat(self):
        assert sa.kandidatni_stropy(150.0, 150.0, pocet=4) == [150.0]

    def test_prvni_kandidat_je_vzdy_dnesni_chovani(self):
        stropy = sa.kandidatni_stropy(80.0, 300.0, pocet=4)
        assert stropy[0] == 80.0


# --------------------------------------------------------------- roční model
def _rok_ceny_a_profil(dnu: int = 28):
    ceny = _ceny_pila(dnu)
    odber = []
    for _ in range(dnu):
        for i in range(96):
            hodina = i / 4
            odber.append(400.0 if 8 <= hodina < 16 else 150.0)
    mesice = [1] * (96 * dnu)
    dny = [d for d in range(dnu) for _ in range(96)]
    return ceny, odber, mesice, dny


class TestSimulujRok:
    """Rozhodovací vrstva: volba měsíčních stropů a vazba na platbu za výkon."""

    def test_kombinace_nikdy_nevyjde_horsi_nez_cisty_peak_shaving(self):
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        # Platba za výkon: 200 Kč/kW/měsíc za naměřené maximum.
        naklad = lambda maxima: sum(maxima.values()) * 200.0  # noqa: E731

        r = sa.simuluj_rok(
            ceny, odber, mesice, dny, vykon_kw=150.0, kapacita_kwh=400.0,
            n=sa.NastaveniSpot(), opotrebeni_kc_mwh=200.0, naklad_vykonu=naklad,
            rezim=sa.REZIM_KOMBINACE,
        )
        volba = r.volby[0]
        prinos_zvolene = r.zisk_kc - naklad(r.cilova_maxima_kw)
        prinos_dnesniho = volba.zisk_pri_nejnizsim_stropu_kc - naklad(
            {volba.mesic: volba.strop_nejnizsi_udrzitelny_kw}
        )
        assert prinos_zvolene >= prinos_dnesniho - 1e-6

    def test_draha_platba_za_vykon_drzi_strop_dole(self):
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        drahy = lambda maxima: sum(maxima.values()) * 100_000.0  # noqa: E731
        r = sa.simuluj_rok(
            ceny, odber, mesice, dny, 150.0, 400.0, sa.NastaveniSpot(), 200.0, drahy,
            rezim=sa.REZIM_KOMBINACE,
        )
        v = r.volby[0]
        assert v.strop_kw == pytest.approx(v.strop_nejnizsi_udrzitelny_kw)

    def test_bezcenna_platba_za_vykon_pusti_strop_nahoru(self):
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        zadny = lambda maxima: 0.0  # noqa: E731
        r = sa.simuluj_rok(
            ceny, odber, mesice, dny, 150.0, 400.0, sa.NastaveniSpot(), 0.0, zadny,
            rezim=sa.REZIM_KOMBINACE,
        )
        v = r.volby[0]
        # Když sražení špičky nic nešetří, model dá přednost obchodu.
        assert v.strop_kw > v.strop_nejnizsi_udrzitelny_kw

    def test_rezim_spot_nesrazi_spicky(self):
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        naklad = lambda maxima: sum(maxima.values()) * 200.0  # noqa: E731
        r = sa.simuluj_rok(
            ceny, odber, mesice, dny, 150.0, 400.0, sa.NastaveniSpot(), 200.0, naklad,
            rezim=sa.REZIM_SPOT,
        )
        v = r.volby[0]
        assert v.strop_kw == pytest.approx(v.maximum_bez_baterie_kw)
        # Měsíční maximum se nesmí zvýšit nabíjením.
        assert r.cilova_maxima_kw[1] <= v.maximum_bez_baterie_kw + 1e-6

    def test_limit_cyklu_snizi_pocet_cyklu(self):
        # Dny s různým rozkmitem ceny – limit má odříznout ty nejslabší.
        # (Na 28 identických dnech by šel obchod jen zapnout nebo vypnout.)
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        ceny = [
            c if den % 4 == 0 else 2000.0 + (c - 2250.0) * 0.15
            for den, c in zip(dny, ceny)
        ]
        naklad = lambda maxima: sum(maxima.values()) * 200.0  # noqa: E731
        bez_limitu = sa.simuluj_rok(
            ceny, odber, mesice, dny, 150.0, 400.0, sa.NastaveniSpot(), 100.0, naklad,
            rezim=sa.REZIM_SPOT,
        )
        s_limitem = sa.simuluj_rok(
            ceny, odber, mesice, dny, 150.0, 400.0,
            sa.NastaveniSpot(max_cyklu_rok=bez_limitu.obchodnich_cyklu / 2), 100.0, naklad,
            rezim=sa.REZIM_SPOT,
        )
        assert s_limitem.obchodnich_cyklu < bez_limitu.obchodnich_cyklu
        assert s_limitem.upozorneni

    def test_prazdny_profil_neshodi_vypocet(self):
        r = sa.simuluj_rok([], [], [], [], 100.0, 200.0, sa.NastaveniSpot(), 0.0, lambda m: 0.0)
        assert r.zisk_kc == 0.0
        assert r.volby == []


class TestSpoctiProVariantu:
    """Vstupní bod pro `peak_shaving.spocti_variantu`."""

    def _kontext(self, dnu: int = 28):
        ceny, odber, mesice, dny = _rok_ceny_a_profil(dnu)
        return (
            sa.Kontext(ceny_kc_mwh=ceny, mesice=mesice, dny=dny, info_cen={"rok_cen": 2025}),
            odber,
        )

    def test_vraci_zisk_a_mesicni_volby(self):
        kontext, odber = self._kontext()
        v = sa.spocti_pro_variantu(
            kontext, profil_kw=odber, vykon_kw=150.0, kapacita_kwh=400.0,
            kapacita_jmenovita_kwh=470.0, cena_baterie_kc=3_000_000, cyklu_zivotnosti=6000,
            rezim=sa.REZIM_KOMBINACE, interval_h=0.25, ucinnost_rt=0.88,
            parametry_2027=None, rezervovany_prikon_kw=500.0, uvazovat_snizeni_rp=False,
            cena_rezervace_kc_kw_rok=3030.78, cena_mesicni_rk_kc_kw_mesic=281.823,
            rezerva_rk_procenta=5.0,
        )
        assert v.volby
        assert v.info_cen["rok_cen"] == 2025
        assert v.opotrebeni_pouzite_kc_mwh > 0

    def test_pouzije_sazby_2027_kdyz_jsou(self):
        kontext, odber = self._kontext()
        p2027 = {
            "t1_kapacita_kc_kw_mesic": 190.133, "t1_spicka_kc_kw_mesic": 19.013,
            "t2_kapacita_kc_kw_mesic": 22.743, "t2_spicka_kc_kw_mesic": 227.429,
            "sazba_prekroceni_kc_kw_mesic": 761.0,
        }
        v = sa.spocti_pro_variantu(
            kontext, profil_kw=odber, vykon_kw=150.0, kapacita_kwh=400.0,
            kapacita_jmenovita_kwh=470.0, cena_baterie_kc=3_000_000, cyklu_zivotnosti=6000,
            rezim=sa.REZIM_KOMBINACE, interval_h=0.25, ucinnost_rt=0.88,
            parametry_2027=p2027, rezervovany_prikon_kw=500.0, uvazovat_snizeni_rp=True,
            cena_rezervace_kc_kw_rok=3030.78, cena_mesicni_rk_kc_kw_mesic=281.823,
            rezerva_rk_procenta=5.0,
        )
        assert v.cilova_maxima_kw


# ------------------------------------------ propojení s ekonomikou variant
class TestPropojeniSPeakShavingem:
    """Co obchodování dělá s ekonomikou rezervované kapacity."""

    def _zadani(self):
        ceny, odber, mesice, dny = _rok_ceny_a_profil()
        baterie = ps.Baterie(
            id=1, nazev="test 150/400", vykon_kw=150.0, kapacita_kwh=400.0,
            cena_kc=3_000_000, ucinnost_rt=0.88, cyklu_zivotnosti=6000,
        )
        kontext = sa.Kontext(ceny_kc_mwh=ceny, mesice=mesice, dny=dny, info_cen={"rok_cen": 2025})
        return baterie, odber, mesice, kontext

    def test_cisty_peak_shaving_se_nezmenil(self):
        """Bez režimu se výsledek nesmí lišit od dřívějšího chování."""
        baterie, odber, mesice, _ = self._zadani()
        v = ps.spocti_variantu(
            baterie, 1, odber, mesice, 500.0, 3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823), 5.0,
            cena_mesicni_rk_kc_kw_mesic=281.823,
        )
        assert v.ekonomika_spot is None
        assert v.zisk_spot_kc == 0.0
        assert v.rezim == "peak_shaving"

    def test_kombinace_pridava_zisk_obchodu_do_npv(self):
        baterie, odber, mesice, kontext = self._zadani()
        spolecne = dict(
            profil_kw=odber, mesice=mesice, rezervovana_kapacita_kw=500.0,
            cena_rezervace_kc_kw_rok=3030.78,
            cena_prekroceni_kc_kw=ps.pokuta_prekroceni_rk_kc_kw(281.823),
            max_navratnost_roky=5.0, cena_mesicni_rk_kc_kw_mesic=281.823,
        )
        cisty = ps.spocti_variantu(baterie, 1, **spolecne)
        kombinace = ps.spocti_variantu(
            baterie, 1, rezim=sa.REZIM_KOMBINACE, spot_kontext=kontext, **spolecne
        )
        assert kombinace.zisk_spot_kc > 0
        assert kombinace.ekonomika_spot is not None
        assert kombinace.npv_kc > cisty.npv_kc

    def test_ekonomika_spot_json_ma_mesicni_rozpad(self):
        baterie, odber, mesice, kontext = self._zadani()
        v = ps.spocti_variantu(
            baterie, 1, odber, mesice, 500.0, 3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823), 5.0,
            cena_mesicni_rk_kc_kw_mesic=281.823,
            rezim=sa.REZIM_KOMBINACE, spot_kontext=kontext,
        )
        es = v.ekonomika_spot
        assert set(es) >= {
            "zisk_kc", "zisk_energie_kc", "naklad_opotrebeni_kc", "obchodnich_cyklu", "mesice"
        }
        assert es["mesice"][0]["mesic"] == 1
        assert es["zisk_kc"] == pytest.approx(v.zisk_spot_kc)

    def test_ztraty_cyklovani_se_nepocitaji_dvakrat(self):
        """V režimu s obchodem nese energetiku zisk obchodu, ne paušální ztráty."""
        baterie, odber, mesice, kontext = self._zadani()
        v = ps.spocti_variantu(
            baterie, 1, odber, mesice, 500.0, 3030.78,
            ps.pokuta_prekroceni_rk_kc_kw(281.823), 5.0,
            cena_mesicni_rk_kc_kw_mesic=281.823, cena_energie_kc_mwh=3000.0,
            rezim=sa.REZIM_KOMBINACE, spot_kontext=kontext,
        )
        assert v.ekonomika_2026["naklad_ztrat_baterie"] == pytest.approx(0.0)


class TestEkonomikaSDodanymiMaximy:
    """Ekonomiky 2026/2027 musí umět pracovat s maximy ze simulace obchodu."""

    def test_2026_pouzije_dodana_maxima(self):
        profil = [100.0, 300.0, 100.0, 250.0]
        mesice = [1, 1, 2, 2]
        pokuta = ps.pokuta_prekroceni_rk_kc_kw(281.823)
        bez = ps.ekonomika_2026(profil, mesice, 300.0, 3030.78, pokuta, 200.0,
                                cena_mesicni_rk_kc_kw_mesic=281.823)
        s_maximy = ps.ekonomika_2026(
            profil, mesice, 300.0, 3030.78, pokuta, 200.0,
            cena_mesicni_rk_kc_kw_mesic=281.823,
            mesicni_maxima_s_baterii={1: 300.0, 2: 250.0},  # baterie nesráží nic
        )
        # Bez srážení nemůže být přínos baterie vyšší.
        assert s_maximy.prinos_baterie <= bez.prinos_baterie

    def test_2027_pouzije_dodana_maxima(self):
        profil = [100.0, 300.0, 100.0, 250.0]
        mesice = [1, 1, 2, 2]
        p = {
            "t1_kapacita_kc_kw_mesic": 190.133, "t1_spicka_kc_kw_mesic": 19.013,
            "t2_kapacita_kc_kw_mesic": 22.743, "t2_spicka_kc_kw_mesic": 227.429,
            "sazba_prekroceni_kc_kw_mesic": 761.0,
        }
        ek = ps.ekonomika_2027(
            profil, mesice, 300.0, 300.0, 100.0, 200.0, p,
            mesicni_maxima_s_baterii={1: 300.0, 2: 250.0},
        )
        assert ek["status"] == "spocitano"
        # Maxima jako bez baterie → na platbě za výkon baterie nic nemění.
        assert ek["prinos_baterie"] == pytest.approx(0.0, abs=1.0)
