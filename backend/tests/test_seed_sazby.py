# -*- coding: utf-8 -*-
"""Testy seedu sazeb distributorů (audit 16. 7. 2026, bughunt PS-1).

Hodnoty 2026 proti finálnímu cenovému výměru ERÚ č. 13/2025 (ERV 17/2025),
hodnoty NTS 2027 proti informativnímu CV ERÚ (5/2026) – viz
docs/reserze_kalkulator/eru-sazby-2026-a-nts-2027.md. Backfill logika se
testuje na čistých funkcích (bez DB).
"""

import pytest

from app.nabidkovac import seed


def _radek(distributor: str, hladina: str, struktura: str) -> dict:
    for r in seed._SEED_SAZBY:
        if (r["distributor"], r["napetova_hladina"], r["struktura_tarifu"]) == (
            distributor,
            hladina,
            struktura,
        ):
            return r
    raise AssertionError(f"Seed neobsahuje {distributor}/{hladina}/{struktura}")


# Očekávané sazby 2026 dle CV 13/2025, bod 4.18: (roční RK Kč/kW/rok = 12×
# měsíční cena za roční RK, měsíční cena za měsíční RK Kč/kW/měs).
SAZBY_2026_DLE_VYMERU = {
    ("cez", "vn"): (3030.78, 281.823),
    ("cez", "vvn"): (1409.18, 131.036),
    ("egd", "vn"): (2766.61, 254.260),
    ("egd", "vvn"): (1329.91, 122.223),
    ("pre", "vn"): (3253.12, 299.351),
    ("pre", "vvn"): (1554.96, 143.087),
}


def test_stara_2026_pokryva_vsechny_tri_rds_na_obou_hladinach():
    kombinace = {
        (r["distributor"], r["napetova_hladina"])
        for r in seed._SEED_SAZBY
        if r["struktura_tarifu"] == "stara_2026"
    }
    assert kombinace == set(SAZBY_2026_DLE_VYMERU)


@pytest.mark.parametrize("klic", sorted(SAZBY_2026_DLE_VYMERU))
def test_stara_2026_sazby_odpovidaji_vymeru(klic):
    rocni, mesicni = SAZBY_2026_DLE_VYMERU[klic]
    r = _radek(klic[0], klic[1], "stara_2026")
    p = r["parametry"]
    assert p["cena_rezervovana_kapacita_kc_kw_rok"] == pytest.approx(rocni, abs=0.005)
    assert p["cena_mesicni_rk_kc_kw_mesic"] == pytest.approx(mesicni, abs=1e-9)
    # Pokuta za překročení RK se odvozuje výpočtem (1,5× měsíční RK, PS-2)
    # a v sazebníku se jako samostatné číslo nedrží.
    assert "cena_prekroceni_kc_kw" not in p
    assert str(r["platne_od"]) == "2026-01-01"
    assert str(r["platne_do"]) == "2026-12-31"
    assert not r.get("je_modelovy_odhad", False)


def test_stara_2026_rocni_sazba_je_12x_mesicni_cena_rocni_rk():
    for (d, h), rk in seed._RK_2026.items():
        r = _radek(d, h, "stara_2026")
        assert r["parametry"]["cena_rezervovana_kapacita_kc_kw_rok"] == pytest.approx(
            rk["rocni"] * 12, abs=0.005
        )


# NTS 2027 dle informativního CV (Kč/kW/měs): t1_kap, t1_sp, t2_kap, t2_sp, překročení.
NTS_2027_DLE_INFORMATIVNIHO_CV = {
    ("cez", "vn"): (190.133, 19.013, 22.743, 227.429, 761.0),
    ("cez", "vvn"): (96.862, 9.686, 11.586, 115.862, 387.0),
    ("egd", "vn"): (181.386, 18.139, 21.697, 216.967, 726.0),
    ("egd", "vvn"): (87.770, 8.777, 10.499, 104.987, 351.0),
    ("pre", "vn"): (196.298, 19.630, 23.480, 234.804, 785.0),
    ("pre", "vvn"): (109.073, 10.907, 13.047, 130.470, 436.0),
}


@pytest.mark.parametrize("klic", sorted(NTS_2027_DLE_INFORMATIVNIHO_CV))
def test_nova_2027_sazby_odpovidaji_informativnimu_cv(klic):
    t1k, t1s, t2k, t2s, prekroceni = NTS_2027_DLE_INFORMATIVNIHO_CV[klic]
    r = _radek(klic[0], klic[1], "nova_2027")
    p = r["parametry"]
    assert p["t1_kapacita_kc_kw_mesic"] == t1k
    assert p["t1_spicka_kc_kw_mesic"] == t1s
    assert p["t2_kapacita_kc_kw_mesic"] == t2k
    assert p["t2_spicka_kc_kw_mesic"] == t2s
    assert p["sazba_prekroceni_kc_kw_mesic"] == prekroceni
    # Modelový odhad, dokud ERÚ nevydá závazný výměr pro 2027 (~11/2026).
    assert r["je_modelovy_odhad"] is True
    assert str(r["platne_od"]) == "2027-01-01"


@pytest.mark.parametrize("hladina,u1,u2", [("vn", 0.60, 0.75), ("vvn", 0.60, 0.70)])
def test_nova_2027_prahy_aku_dle_hladiny(hladina, u1, u2):
    for d in ("cez", "egd", "pre"):
        p = _radek(d, hladina, "nova_2027")["parametry"]
        assert p["u1_ucinnost"] == u1
        assert p["u2_ucinnost"] == u2


# ---------------------------------------------------------------- backfill
def test_doplneni_chybejicich_doplni_jen_none_a_chybejici():
    existujici = {
        "cena_rezervovana_kapacita_kc_kw_rok": 2847.72,
        "cena_prekroceni_kc_kw": 1108.0,
        "u1_ucinnost": None,
    }
    ze_seedu = {
        "cena_rezervovana_kapacita_kc_kw_rok": 3030.78,
        "cena_mesicni_rk_kc_kw_mesic": 281.823,
        "u1_ucinnost": 0.60,
        "u2_ucinnost": 0.75,
    }
    out, zmena = seed.doplneni_chybejicich(existujici, ze_seedu)
    assert zmena is True
    assert out["cena_mesicni_rk_kc_kw_mesic"] == 281.823  # chyběl → doplněn
    assert out["u1_ucinnost"] == 0.60  # None → doplněn
    assert out["u2_ucinnost"] == 0.75  # chyběl → doplněn
    # Vyplněné hodnoty zůstávají (i chybnou opraví až cílená oprava, ne tohle):
    assert out["cena_rezervovana_kapacita_kc_kw_rok"] == 2847.72
    assert existujici["u1_ucinnost"] is None  # vstup se nemutuje


def test_doplneni_chybejicich_je_idempotentni():
    ze_seedu = {"cena_mesicni_rk_kc_kw_mesic": 281.823}
    jednou, zmena1 = seed.doplneni_chybejicich({}, ze_seedu)
    podruhe, zmena2 = seed.doplneni_chybejicich(jednou, ze_seedu)
    assert (zmena1, zmena2) == (True, False)
    assert podruhe == jednou


def _oprava(hladina: str, klic: str) -> dict:
    return next(
        o
        for o in seed._BACKFILL_OPRAVY
        if o["napetova_hladina"] == hladina and o["klic"] == klic
    )


OPRAVA_CEZ_VN = _oprava("vn", "cena_rezervovana_kapacita_kc_kw_rok")
OPRAVA_CEZ_VVN = _oprava("vvn", "cena_rezervovana_kapacita_kc_kw_rok")
OPRAVA_POKUTA_VN = _oprava("vn", "cena_prekroceni_kc_kw")


def test_oprava_prepise_presne_znamou_chybnou_hodnotu_a_doplni_poznamku():
    parametry = {"cena_rezervovana_kapacita_kc_kw_rok": 2847.72, "cena_prekroceni_kc_kw": 1108.0}
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "ČEZ 2026, bez DPH.", OPRAVA_CEZ_VN)
    assert zmena is True
    assert out["cena_rezervovana_kapacita_kc_kw_rok"] == 3030.78
    assert out["cena_prekroceni_kc_kw"] == 1108.0  # ostatní klíče nedotčené
    assert poznamka.startswith("ČEZ 2026, bez DPH.")
    assert "CV č. 13/2025" in poznamka


def test_oprava_nesahne_na_rucne_upravenou_hodnotu():
    parametry = {"cena_rezervovana_kapacita_kc_kw_rok": 2900.0}  # admin ji už změnil
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "pozn", OPRAVA_CEZ_VN)
    assert zmena is False
    assert out["cena_rezervovana_kapacita_kc_kw_rok"] == 2900.0
    assert poznamka == "pozn"


def test_oprava_je_idempotentni():
    parametry = {"cena_rezervovana_kapacita_kc_kw_rok": 2847.72}
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "", OPRAVA_CEZ_VN)
    out2, poznamka2, zmena2 = seed.aplikuj_opravu(out, poznamka, OPRAVA_CEZ_VN)
    assert zmena is True and zmena2 is False
    assert out2 == out and poznamka2 == poznamka
    assert poznamka.count("OPRAVA (audit 16. 7. 2026)") == 1


def test_oprava_doplni_nedohledanou_vvn_hodnotu():
    parametry = {"cena_rezervovana_kapacita_kc_kw_rok": None, "cena_prekroceni_kc_kw": 521.0}
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "", OPRAVA_CEZ_VVN)
    assert zmena is True
    assert out["cena_rezervovana_kapacita_kc_kw_rok"] == 1409.18
    assert "1409,18" in poznamka


def test_oprava_odstrani_chybnou_pokutu_z_puvodniho_seedu():
    # PS-2: 1108 Kč/kW/měs = překročení rezervovaného VÝKONU, do sazebníku
    # nepatří (pokuta za RK se odvozuje 1,5× z měsíční RK).
    parametry = {"cena_rezervovana_kapacita_kc_kw_rok": 3030.78, "cena_prekroceni_kc_kw": 1108.0}
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "pozn.", OPRAVA_POKUTA_VN)
    assert zmena is True
    assert "cena_prekroceni_kc_kw" not in out
    assert out["cena_rezervovana_kapacita_kc_kw_rok"] == 3030.78
    assert "1,5× měsíční RK" in poznamka
    # Idempotence: druhé spuštění už nic nemění.
    out2, _, zmena2 = seed.aplikuj_opravu(out, poznamka, OPRAVA_POKUTA_VN)
    assert zmena2 is False and out2 == out


def test_oprava_nesahne_na_rucne_zadanou_pokutu():
    parametry = {"cena_prekroceni_kc_kw": 900.0}  # admin zadal vlastní hodnotu
    out, poznamka, zmena = seed.aplikuj_opravu(parametry, "", OPRAVA_POKUTA_VN)
    assert zmena is False
    assert out["cena_prekroceni_kc_kw"] == 900.0
