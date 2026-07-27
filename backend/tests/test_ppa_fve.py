# -*- coding: utf-8 -*-
"""Testy výpočetního jádra PPA pro FVE (`app/nabidkovac/ppa_fve.py`).

Modul je bez závislostí na DB/FastAPI – testuje se přímo (inspirace:
docs/reserze_kalkulator/bughunt/synteticke-testy.md).
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.nabidkovac import ppa_fve as ppa


def den_casy(rok, mesic, den):
    """15min časové značky jednoho dne."""
    t = datetime(rok, mesic, den)
    return [t + timedelta(minutes=15 * i) for i in range(96)]


# --------------------------------------------------- PPA-1: limit max_kwp
class TestKandidatniVelikosti:
    """Bughunt PPA-1 (test T1): sweep nesmí překročit limit střechy max_kwp."""

    # kandidatni_velikosti používá jen součty řad – stačí jednoprvkové seznamy.
    BASE_1KWP = [1000.0]  # kWh/kWp/rok
    SPOTREBA = [3000.0]  # kWh/rok → surový strop sweeper = 3× 3000/1000 = 9 kWp

    def test_max_kwp_pod_5_je_tvrdy_limit(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=3.0)
        assert kandidati == [1, 2, 3]
        assert all(k <= 3.0 for k in kandidati)

    def test_bez_limitu_se_pouzije_pomer_ke_spotrebe(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=None)
        assert max(kandidati) == 9
        assert min(kandidati) >= 1

    def test_mala_spotreba_ma_sweep_aspon_do_5_kwp(self):
        # surový strop 3×1000/1000 = 3 kWp → minimální rozsah sweepu je 5 kWp.
        kandidati = ppa.kandidatni_velikosti([], [1000.0], self.BASE_1KWP, max_kwp=None)
        assert max(kandidati) == 5

    def test_limit_pod_1_kwp_vrati_aspon_jednoho_kandidata(self):
        kandidati = ppa.kandidatni_velikosti([], self.SPOTREBA, self.BASE_1KWP, max_kwp=0.5)
        assert kandidati == [1]

    def test_prazdna_spotreba_nema_kandidaty(self):
        assert ppa.kandidatni_velikosti([], [0.0], self.BASE_1KWP) == []


# ------------------------------------------- PPA-2: kalibrace výroby dle PVGIS
class TestKalibraceVyroby:
    """Hodnoty z PVGIS v5.3 (SARAH3), střed ČR – pvgis-kalibrace-vyroby-fve.md."""

    def test_merny_vynos_stred_cr(self):
        assert ppa.VYCHOZI_MERNY_VYNOS_KWH_KWP == 1055.0

    def test_mesicni_tabulka_sedi_s_pvgis_a_secte_1000(self):
        assert sum(ppa._MESICNI_VYNOS.values()) == pytest.approx(1000.0)
        assert ppa._MESICNI_VYNOS[10] == 72.0  # říjen: dřív 58 (+24 % rel. chyba)
        assert ppa._MESICNI_VYNOS[5] == 120.9  # květen: dřív 135 (moc „letní")
        # zimní půlrok (říj–bře) = 30,4 % ročního výnosu dle SARAH3
        zima = sum(ppa._MESICNI_VYNOS[m] for m in (10, 11, 12, 1, 2, 3))
        assert zima / 1000.0 == pytest.approx(0.304, abs=0.002)

    @pytest.mark.parametrize(
        "azimut,sklon,k",
        [
            (0, 35, 1.00),
            (180, 35, 0.54),  # sever: dřív 0,66 (nadhodnocení ~+22 %)
            (180, 60, 0.34),  # strmý sever: dřív 0,50 (+48 % rel.!)
            (0, 0, 0.85),  # horizontála: dřív 0,88
            (90, 35, 0.80),  # V/Z: dřív 0,84
            (0, 60, 0.94),  # strmý jih: dřív 0,91
            (45, 35, 0.94),
        ],
    )
    def test_korekce_orientace_dle_pvgis(self, azimut, sklon, k):
        assert ppa.korekce_orientace(azimut, sklon) == pytest.approx(k)

    def test_korekce_orientace_symetrie_vychod_zapad(self):
        assert ppa.korekce_orientace(-90, 35) == ppa.korekce_orientace(90, 35)

    def test_rocni_vyroba_odpovida_mernemu_vynosu(self):
        casy = []
        t = datetime(2025, 1, 1)
        while t < datetime(2026, 1, 1):
            casy.append(t)
            t += timedelta(minutes=15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        assert sum(vyroba) == pytest.approx(1055.0, rel=1e-6)


# --------------------------------------------------- PPA-3: posun letního času
class TestLetniCas:
    def test_okno_letniho_casu_2025(self):
        # 2025: přechody 30. 3. a 26. 10.
        assert not ppa._je_letni_cas(datetime(2025, 3, 30, 1, 45))
        assert ppa._je_letni_cas(datetime(2025, 3, 30, 2, 0))
        assert ppa._je_letni_cas(datetime(2025, 10, 26, 2, 45))
        assert not ppa._je_letni_cas(datetime(2025, 10, 26, 3, 0))
        assert not ppa._je_letni_cas(datetime(2025, 1, 15, 12, 0))
        assert ppa._je_letni_cas(datetime(2025, 7, 15, 12, 0))

    def test_letni_spicka_vyroby_je_ve_13_hodin(self):
        casy = den_casy(2025, 7, 15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        spicka = casy[vyroba.index(max(vyroba))]
        assert spicka.hour == 13 and spicka.minute == 0

    def test_zimni_spicka_vyroby_je_ve_12_hodin(self):
        casy = den_casy(2025, 1, 15)
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        spicka = casy[vyroba.index(max(vyroba))]
        assert spicka.hour == 12 and spicka.minute == 0

    def test_tz_aware_casy_z_db_nepadaji(self):
        # Sloupec spotreba_profil.cas je DateTime(timezone=True) → routes
        # posílají tz-aware datetimes; porovnání s naive oknem SELČ padalo
        # na TypeError (500 z /ppa/vypocet).
        tz = timezone(timedelta(hours=2))
        casy = [datetime(2025, 7, 15, tzinfo=tz) + timedelta(minutes=15 * i) for i in range(96)]
        vyroba = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 35, 0)
        assert sum(vyroba) > 0
        spicka = casy[vyroba.index(max(vyroba))]
        assert spicka.hour == 13  # posun SELČ platí i pro aware časy

    def test_posun_nemeni_denni_energii(self):
        # Normalizace tvaru dne zachovává energii – posun jen přesouvá v čase.
        letni = sum(ppa.simuluj_vyrobu(den_casy(2025, 7, 15), 1.0, 49.8, 35, 0))
        assert letni > 0
        # Bez denní proměnlivosti (vyhlazený model) mají dny téhož měsíce
        # shodnou energii – tenhle invariant drží normalizace tvaru dne.
        casy2 = den_casy(2025, 7, 15) + den_casy(2025, 7, 16)
        vyroba2 = ppa.simuluj_vyrobu(casy2, 1.0, 49.8, 35, 0, denni_promenlivost=False)
        assert sum(vyroba2[:96]) == pytest.approx(sum(vyroba2[96:]), rel=1e-9)

    def test_denni_promenlivost_zachova_energii_dvojice_dnu(self):
        # Se zapnutou proměnlivostí se dny LIŠÍ (jasno/zataženo), ale součet
        # dvojice zůstává stejný jako u vyhlazeného modelu – měsíční energie
        # se jen jinak rozdělí mezi dny (revize 26. 7. 2026).
        casy2 = den_casy(2025, 7, 15) + den_casy(2025, 7, 16)
        s_prom = ppa.simuluj_vyrobu(casy2, 1.0, 49.8, 35, 0, denni_promenlivost=True)
        bez_prom = ppa.simuluj_vyrobu(casy2, 1.0, 49.8, 35, 0, denni_promenlivost=False)
        assert sum(s_prom) == pytest.approx(sum(bez_prom), rel=1e-9)
        assert sum(s_prom[:96]) != pytest.approx(sum(s_prom[96:]), rel=1e-3)


# ------------------------------------- revize fyziky výroby (26. 7. 2026)
class TestFyzikaVyrobyRevize:
    """Tvar dne dle azimutu, měsíční rozdělení dle orientace, denní proměnlivost.

    Původní model měl symetrickou zvonovinu bez azimutu, jednu měsíční řadu
    (35°/jih) pro všechny orientace a všechny dny měsíce stejné. Kalibrační
    zdroj: docs/reserze_kalkulator/pvgis-data.csv (PVGIS v5.3, střed ČR).
    """

    ROK_CASY = None

    @classmethod
    def setup_class(cls):
        casy = []
        t = datetime(2025, 1, 1)
        while t < datetime(2026, 1, 1):
            casy.append(t)
            t += timedelta(minutes=15)
        cls.ROK_CASY = casy

    def test_rocni_energie_drzi_pvgis_kalibraci_pro_vsechny_orientace(self):
        # Roční úroveň určuje měrný výnos × k_orient – revize tvaru dne ani
        # měsíčního rozdělení ji nesmí posunout.
        for sklon, azimut in ((35, 0), (0, 0), (15, 45), (35, 90), (60, 0), (35, 180)):
            vyroba = ppa.simuluj_vyrobu(self.ROK_CASY, 1.0, 49.8, sklon, azimut)
            ocekavano = 1055.0 * ppa.korekce_orientace(azimut, sklon)
            assert sum(vyroba) == pytest.approx(ocekavano, rel=1e-9)

    @pytest.mark.parametrize(
        "azimut,hodina",
        [(0, 13), (-90, 11), (90, 15)],  # jih / východ / západ (letní čas)
    )
    def test_spicka_dne_se_posouva_s_azimutem(self, azimut, hodina):
        den = den_casy(2025, 7, 16)
        vyroba = ppa.simuluj_vyrobu(den, 1.0, 49.8, 35, azimut, denni_promenlivost=False)
        assert den[vyroba.index(max(vyroba))].hour == hodina

    def test_vychod_a_zapad_maji_zrcadlovy_tvar_dne(self):
        den = den_casy(2025, 7, 16)
        v_vychod = ppa.simuluj_vyrobu(den, 1.0, 49.8, 35, -90, denni_promenlivost=False)
        v_zapad = ppa.simuluj_vyrobu(den, 1.0, 49.8, 35, 90, denni_promenlivost=False)
        # stejná denní energie (k_orient je symetrický), ale zrcadlený tvar
        assert sum(v_vychod) == pytest.approx(sum(v_zapad), rel=1e-9)
        assert den[v_vychod.index(max(v_vychod))].hour < den[v_zapad.index(max(v_zapad))].hour

    @pytest.mark.parametrize(
        "sklon,azimut,zima_procent",
        [
            (0, 0, 23.1),  # plochá střecha – dřív model tvrdil 30,4 %
            (15, 0, 26.8),
            (35, 0, 30.4),  # referenční uzel (= _MESICNI_VYNOS)
            (60, 0, 34.4),
            (35, 90, 24.3),
            (35, 180, 17.7),
        ],
    )
    def test_zimni_pulrok_sedi_s_pvgis_pro_danou_orientaci(self, sklon, azimut, zima_procent):
        vyroba = ppa.simuluj_vyrobu(
            self.ROK_CASY, 1.0, 49.8, sklon, azimut, denni_promenlivost=False
        )
        zima = sum(
            v for v, c in zip(vyroba, self.ROK_CASY) if c.month in (10, 11, 12, 1, 2, 3)
        )
        assert zima / sum(vyroba) * 100 == pytest.approx(zima_procent, abs=0.2)

    def test_mesicni_podily_referencni_uzel_odpovida_puvodni_rade(self):
        podily = ppa.mesicni_podily(0, 35)
        assert sum(podily.values()) == pytest.approx(1.0)
        for m in range(1, 13):
            assert podily[m] == pytest.approx(ppa._MESICNI_VYNOS[m] / 1000.0, abs=1e-6)

    def test_spickovy_vykon_odpovida_realne_fve(self):
        # Reálná FVE dává za jasného dne v poledne 75–85 % kWp; vyhlazený
        # model dával jen ~51 %, čímž nadhodnocoval samospotřebu.
        vyroba = ppa.simuluj_vyrobu(self.ROK_CASY, 1.0, 49.8, 35, 0)
        spicka_kw = max(vyroba) / 0.25
        assert 0.72 <= spicka_kw <= 0.88

    def test_promenlivost_snizuje_samospotrebu_a_zvysuje_orez(self):
        # Σ min(V, S) je konkávní → vyhlazený profil samospotřebu nadhodnocuje.
        spotreba = [
            (1.0 if (c.weekday() < 5 and 5 <= c.hour < 13) else 0.25) * 0.25 * 40.0
            for c in self.ROK_CASY
        ]
        vyhlazeny = ppa.simuluj_vyrobu(
            self.ROK_CASY, 200.0, 49.8, 35, 0, denni_promenlivost=False
        )
        realny = ppa.simuluj_vyrobu(self.ROK_CASY, 200.0, 49.8, 35, 0, denni_promenlivost=True)
        assert sum(vyhlazeny) == pytest.approx(sum(realny), rel=1e-9)
        b_vyhlazeny = ppa.sparuj(vyhlazeny, spotreba, 40.0, 0.25)
        b_realny = ppa.sparuj(realny, spotreba, 40.0, 0.25)
        assert b_realny.samospotreba_kwh < b_vyhlazeny.samospotreba_kwh
        assert b_realny.orez_kwh > b_vyhlazeny.orez_kwh

    def test_diry_v_profilu_nenafouknou_vyrobu(self):
        # E_den se dělí KALENDÁŘNÍMI dny měsíce: chybějící dny nesmí svou
        # energii přesypat do dnů přítomných (dřív +2,9 % při 1,9 % děr).
        cely = ppa.simuluj_vyrobu(self.ROK_CASY, 1.0, 49.8, 35, 0)
        vynechane = {(2025, 7, d) for d in range(10, 17)}
        s_dirou_casy = [
            c for c in self.ROK_CASY if (c.year, c.month, c.day) not in vynechane
        ]
        s_dirou = ppa.simuluj_vyrobu(s_dirou_casy, 1.0, 49.8, 35, 0)
        assert sum(s_dirou) < sum(cely)
        # chybí 7 z 31 dní července → červenec dá jen 24/31 své energie
        cervenec_cely = sum(v for v, c in zip(cely, self.ROK_CASY) if c.month == 7)
        cervenec_dira = sum(v for v, c in zip(s_dirou, s_dirou_casy) if c.month == 7)
        assert cervenec_dira == pytest.approx(cervenec_cely * 24 / 31, rel=0.02)

    def test_nadmerny_sklon_je_mimo_kalibraci(self):
        # PVGIS mřížka končí na 60°; nad ní se hodnoty klipují, což u svislé
        # plochy nadhodnocuje výnos → route na to upozorňuje.
        assert ppa.SKLON_KALIBROVANY_MAX == 60.0
        assert ppa.korekce_orientace(0, 90) == ppa.korekce_orientace(0, 60)


# --------------------------------------------------- PPA-4: LID prvního roku
def vstup_ppa(**zmeny):
    """Vstup PPA s neutrálními defaulty pro testy ekonomiky."""
    zaklad = dict(
        kwp=100.0,
        lat=49.8,
        sklon_st=35,
        azimut_st=0,
        cena_ppa_kc_mwh=2500,
        index_ppa_rocni=0.0,
        cena_silova_kc_mwh=3500,
        index_dodavatel_rocni=0.0,
        vyhnutelne_regulovane_kc_mwh=0.0,  # v testech LID izolujeme cenu
        index_regulovane_rocni=0.0,
        poze_kc_mwh=0.0,
        delka_kontraktu_roky=3,
        degradace_rocni=0.005,
        capex_kc=2_500_000,
        prebytek_uctovat=False,
        prebytek_cena_kc_mwh=0,
        index_prebytek_rocni=0,
        rezervovany_vykon_dodavky_kw=None,
        oam_kc_kwp_rok=0,
        diskontni_sazba=0.05,
    )
    zaklad.update(zmeny)
    return ppa.VstupPPA(**zaklad)


class TestDegradaceLid:
    """Bughunt PPA-4: f(t) = (1 − LID) × (1 − d)^(t−1), LID už v roce 1."""

    CASY = den_casy(2025, 7, 15)
    SPOTREBA = [5.0] * 96  # kWh/interval – dost vysoká, ať je vše samospotřeba

    def test_default_lid_je_2_procenta(self):
        assert ppa.VYCHOZI_DEGRADACE_ROK1 == 0.02
        assert vstup_ppa().degradace_rok1 == 0.02

    def test_rok1_zahrnuje_lid_a_dalsi_roky_navazuji(self):
        bez_lid = ppa.spocti_ppa(vstup_ppa(degradace_rok1=0.0), self.CASY, self.SPOTREBA)
        s_lid = ppa.spocti_ppa(vstup_ppa(degradace_rok1=0.02), self.CASY, self.SPOTREBA)
        for t in range(3):
            # výstup je zaokrouhlený na 0,1 kWh → absolutní tolerance
            assert s_lid["roky"][t]["vyroba_kwh"] == pytest.approx(
                bez_lid["roky"][t]["vyroba_kwh"] * 0.98, abs=0.2
            )
        # meziroční poměr zůstává (1 − d)
        assert s_lid["roky"][1]["vyroba_kwh"] / s_lid["roky"][0]["vyroba_kwh"] == pytest.approx(
            0.995, rel=1e-4
        )

    def test_headline_vyroba_rok1_odpovida_prvnimu_roku_tabulky(self):
        r = ppa.spocti_ppa(vstup_ppa(), self.CASY, self.SPOTREBA)
        assert r["vyroba_rok1_kwh"] == pytest.approx(r["roky"][0]["vyroba_kwh"], abs=0.2)
        assert r["degradace_rok1"] == 0.02


# ---------------------------------------- PPA-5: rozklad ceny dodavatele
class TestRozkladCenyDodavatele:
    """Úspora klienta = SS × (silová + vyhnutelné regulované − PPA cena)."""

    CASY = den_casy(2025, 7, 15)
    SPOTREBA = [50.0] * 96  # dost vysoká → veškerá výroba je samospotřeba

    def test_default_vyhnutelnych_regulovanych(self):
        assert ppa.VYCHOZI_VYHNUTELNE_REGULOVANE_KC_MWH == 260.0
        v = vstup_ppa()
        # helper je explicitně nuluje; čistý VstupPPA má default 260
        assert v.vyhnutelne_regulovane_kc_mwh == 0.0

    def test_uspora_zahrnuje_regulovane_slozky(self):
        vstup = vstup_ppa(
            cena_silova_kc_mwh=3000.0,
            vyhnutelne_regulovane_kc_mwh=260.0,
            cena_ppa_kc_mwh=2500.0,
            delka_kontraktu_roky=1,
            degradace_rok1=0.0,
        )
        r = ppa.spocti_ppa(vstup, self.CASY, self.SPOTREBA)
        ss_mwh = r["samospotreba_rok1_kwh"] / 1000.0
        # marže klienta = 3000 + 260 − 2500 = 760 Kč/MWh
        assert r["roky"][0]["uspora_klient_kc"] == pytest.approx(ss_mwh * 760.0, rel=1e-4)
        assert r["vyhnutelna_cena_rok1_kc_mwh"] == pytest.approx(3260.0)
        assert r["roky"][0]["cena_dodavatel_kc_mwh"] == pytest.approx(3260.0)
        assert r["roky"][0]["cena_silova_kc_mwh"] == pytest.approx(3000.0)

    def test_eskalace_silove_a_regulovanych_zvlast(self):
        vstup = vstup_ppa(
            cena_silova_kc_mwh=3000.0,
            index_dodavatel_rocni=0.03,
            vyhnutelne_regulovane_kc_mwh=260.0,
            index_regulovane_rocni=0.0,
            delka_kontraktu_roky=2,
        )
        r = ppa.spocti_ppa(vstup, self.CASY, self.SPOTREBA)
        # rok 2: eskaluje jen silová, regulované zůstávají
        assert r["roky"][1]["cena_dodavatel_kc_mwh"] == pytest.approx(3000.0 * 1.03 + 260.0, abs=0.01)

    def test_poze_se_pricita_k_regulovanym(self):
        vstup = vstup_ppa(
            cena_silova_kc_mwh=3000.0,
            vyhnutelne_regulovane_kc_mwh=260.0,
            poze_kc_mwh=100.0,
            delka_kontraktu_roky=1,
        )
        r = ppa.spocti_ppa(vstup, self.CASY, self.SPOTREBA)
        assert r["vyhnutelna_cena_rok1_kc_mwh"] == pytest.approx(3360.0)
        assert r["roky"][0]["cena_dodavatel_kc_mwh"] == pytest.approx(3360.0)


# ---------------------------------- PPA-6/PPA-8: ekonomika investora + flag
class TestEkonomikaInvestora:
    CASY = den_casy(2025, 7, 15)
    SPOTREBA = [50.0] * 96

    def test_defaulty_dle_rozhodnuti(self):
        assert ppa.VYCHOZI_OAM_KC_KWP_ROK == 350.0
        assert ppa.VYCHOZI_DISKONTNI_SAZBA == 0.075

    def test_oam_snizuje_cf_investora(self):
        bez = ppa.spocti_ppa(vstup_ppa(oam_kc_kwp_rok=0.0), self.CASY, self.SPOTREBA)
        s_oam = ppa.spocti_ppa(vstup_ppa(oam_kc_kwp_rok=350.0), self.CASY, self.SPOTREBA)
        assert s_oam["roky"][0]["naklad_oam_kc"] == pytest.approx(350.0 * 100.0)
        assert s_oam["roky"][0]["cf_investor_kc"] == pytest.approx(
            bez["roky"][0]["cf_investor_kc"] - 35_000.0, abs=0.01
        )

    def test_vymena_stridace_jen_v_danem_roce(self):
        vstup = vstup_ppa(vymena_stridace_rok=2, vymena_stridace_kc_kwp=1000.0)
        r = ppa.spocti_ppa(vstup, self.CASY, self.SPOTREBA)
        assert r["roky"][0]["naklad_vymena_stridace_kc"] == 0.0
        assert r["roky"][1]["naklad_vymena_stridace_kc"] == pytest.approx(100_000.0)
        assert r["roky"][2]["naklad_vymena_stridace_kc"] == 0.0
        assert r["vymena_stridace"] == {"rok": 2, "kc_kwp": 1000.0}
        bez = ppa.spocti_ppa(vstup_ppa(), self.CASY, self.SPOTREBA)
        assert r["roky"][1]["cf_investor_kc"] == pytest.approx(
            bez["roky"][1]["cf_investor_kc"] - 100_000.0, abs=0.01
        )

    def test_vypnuta_vymena_stridace_nic_nemeni(self):
        r = ppa.spocti_ppa(vstup_ppa(), self.CASY, self.SPOTREBA)
        assert r["vymena_stridace"] is None
        assert all(x["naklad_vymena_stridace_kc"] == 0.0 for x in r["roky"])

    def test_doporuceno_dle_znamenka_npv(self):
        # Malý CAPEX → kladné NPV → doporučeno.
        zisk = ppa.spocti_ppa(vstup_ppa(capex_kc=1000.0), self.CASY, self.SPOTREBA)
        assert zisk["npv_kc"] > 0 and zisk["doporuceno"] is True
        # Obří CAPEX → záporné NPV → nedoporučeno.
        ztrata = ppa.spocti_ppa(vstup_ppa(capex_kc=100_000_000.0), self.CASY, self.SPOTREBA)
        assert ztrata["npv_kc"] < 0 and ztrata["doporuceno"] is False


# ------------------ CAPEX z komponent: kontrola jednotek (26. 7. 2026)
class TestCapexKomponentyJednotky:
    """Výběr „nejlevnější dle Kč/kW“ je bezbranný proti překlepu v jednotkách.

    Panel „550 Wp“ zadaný jako `vykon_kw = 550` má cenu za kW 1000× nižší,
    takže by ho výběr VŽDY zvolil: `ceil(300 / 550) = 1` panel na 300 kWp,
    tj. CAPEX o desítky procent nižší a NPV s payback silně nadhodnocené.
    """

    PANEL_OK = ppa.Komponenta(1, "fve_panel", "Panel 550 Wp", 0.55, 3300.0)
    PANEL_PREKLEP = ppa.Komponenta(2, "fve_panel", "Panel 550 (chybné W)", 550.0, 3300.0)
    INVERTOR = ppa.Komponenta(3, "invertor", "Střídač 100 kW", 100.0, 110_000.0)

    def test_panel_s_prekleplou_jednotkou_se_nepouzije(self):
        capex, rozpad = ppa.capex_komponenty(
            300.0, [self.PANEL_OK, self.PANEL_PREKLEP], [self.INVERTOR], 11_000.0
        )
        assert rozpad["panely"]["nazev"] == "Panel 550 Wp"
        assert rozpad["panely"]["pocet"] == 546  # ceil(300 / 0,55)
        assert "preskocene" in rozpad
        assert any("550" in s for s in rozpad["preskocene"])
        # 546 × 3 300 + 3 × 110 000 + 300 × 11 000
        assert capex == pytest.approx(546 * 3300.0 + 3 * 110_000.0 + 300 * 11_000.0)

    def test_rozpad_uvadi_instalovany_vykon_komponent(self):
        _, rozpad = ppa.capex_komponenty(300.0, [self.PANEL_OK], [self.INVERTOR], 0.0)
        assert rozpad["panely"]["vykon_kw"] == pytest.approx(300.3, abs=0.05)
        assert rozpad["invertory"]["vykon_kw"] == pytest.approx(300.0)

    def test_kdyz_zbydou_jen_vadne_polozky_slozka_chybi(self):
        capex, rozpad = ppa.capex_komponenty(
            300.0, [self.PANEL_PREKLEP], [self.INVERTOR], 0.0
        )
        assert rozpad["panely"] == {"chybi": True}
        assert capex == pytest.approx(3 * 110_000.0)

    def test_prilis_velky_stridac_se_taky_odfiltruje(self):
        vadny = ppa.Komponenta(4, "invertor", "Střídač 5000 kW", 5000.0, 100.0)
        _, rozpad = ppa.capex_komponenty(300.0, [self.PANEL_OK], [vadny, self.INVERTOR], 0.0)
        assert rozpad["invertory"]["nazev"] == "Střídač 100 kW"
        assert "preskocene" in rozpad


# --------------- sweep velikostí: jemnost a degenerace (26. 7. 2026)
class TestSweepVelikosti:
    """Doporučená velikost nesmí být artefaktem kroku mřížky.

    Nejmenší kandidát byl dřív rovnou `krok = cap/pocet`, tedy u velké
    spotřeby desítky až stovky kWp – menší FVE se nikdy nezkusila. A když
    marginální kWp nevydělá (což závisí na ceně za kWp, kterou se ladí
    v adminu), kritérium „max NPV“ nemá vnitřní optimum a vrací hranici
    rozsahu; to musí appka říct, ne mlčky vydat číslo.
    """

    BASE_1KWP = [1000.0]

    def test_male_velikosti_jsou_v_mrizce_i_pri_velke_spotrebe(self):
        # 5 GWh/rok → cap 15 000 kWp, krok 500 kWp; dřív byl nejmenší
        # kandidát 500 kWp a nic menšího se nezkusilo.
        kandidati = ppa.kandidatni_velikosti([], [5_000_000.0], self.BASE_1KWP, pocet=30)
        assert min(kandidati) == 1
        for k in (1, 2, 3, 5, 8, 13, 21, 34, 55):
            assert k in kandidati

    def test_limit_strechy_zustava_tvrdy(self):
        kandidati = ppa.kandidatni_velikosti([], [5_000_000.0], self.BASE_1KWP, max_kwp=40.0)
        assert max(kandidati) <= 40
        assert 55 not in kandidati  # malá velikost nad limitem se nepřidá

    def _uloha(self, cena_kwp, delka=20):
        casy = []
        t = datetime(2025, 1, 1)
        while t < datetime(2026, 1, 1):
            casy.append(t)
            t += timedelta(minutes=15)
        spotreba = [
            (1.0 if (c.weekday() < 5 and 6 <= c.hour < 18) else 0.3) * 0.25 * 60.0 for c in casy
        ]
        base1 = ppa.simuluj_vyrobu(casy, 1.0, 49.8, 30, 0)
        sab = vstup_ppa(
            kwp=0.0, sklon_st=30, delka_kontraktu_roky=delka, capex_kc=0.0,
            cena_ppa_kc_mwh=2200.0, index_ppa_rocni=0.03,
            cena_silova_kc_mwh=3500.0, index_dodavatel_rocni=0.03,
            vyhnutelne_regulovane_kc_mwh=260.0, oam_kc_kwp_rok=350.0,
            diskontni_sazba=0.075,
        )

        def capex_fn(kwp):
            return kwp * cena_kwp, {"rezim": "cena_kwp", "cena_kc_kwp": cena_kwp}

        kandidati = ppa.kandidatni_velikosti(casy, spotreba, base1, None, pocet=30)
        return ppa.vyber_velikost(sab, casy, spotreba, kandidati, capex_fn, base1)

    def test_degenerovane_optimum_je_oznacene(self):
        # Drahá FVE: každý další kWp NPV zhoršuje → vítěz je nejmenší kandidát.
        vysledky = self._uloha(cena_kwp=40_000.0)
        assert vysledky[0]["optimum_na_hranici"] is True
        assert vysledky[0]["kwp"] == pytest.approx(1.0)

    def test_vnitrni_optimum_neni_oznacene_jako_hranice(self):
        vysledky = self._uloha(cena_kwp=14_000.0)
        assert vysledky[0]["optimum_na_hranici"] is False
        assert vysledky[0]["kwp"] > 1.0

    def test_jemny_pruchod_zpresni_vitezne_kwp(self):
        # Vítěz nemusí ležet na hrubé mřížce – jemný průchod zkouší i mezi body.
        vysledky = self._uloha(cena_kwp=14_000.0)
        nejlepsi_npv = max(r["npv_kc"] for r in vysledky)
        assert vysledky[0]["npv_kc"] == pytest.approx(nejlepsi_npv)
        # výsledky jsou seřazené od nejlepší ekonomiky
        assert vysledky[0]["npv_kc"] >= vysledky[-1]["npv_kc"]
