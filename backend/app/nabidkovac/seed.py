"""Naplnění tabulky `sazby_distributoru` výchozími daty (METODIKA kap. 3.1, 6–7).

Zdroje čísel (audit 16. 7. 2026, docs/reserze_kalkulator/eru-sazby-2026-a-nts-2027.md):
- `stara_2026` – finální cenový výměr ERÚ č. 13/2025 (ERV 17/2025), bod 4.18.
  Výměr platí pro všechny tři RDS → seedují se ČEZ, EG.D i PRE (VN + VVN).
- `nova_2027` – MODELOVÝ odhad (`je_modelovy_odhad`) z INFORMATIVNÍHO cenového
  výměru ERÚ k nové tarifní struktuře (publikován 5/2026, „jako by NTS platila
  už 2026“). Závazné ceny pro 2027 vyjdou ~11/2026 (pak nový řádek s novým
  `platne_od`, ne přepis modelového).

Seed je idempotentní: běží při startu appky a vloží řádek jen tehdy, když
stejná kombinace (distributor, hladina, struktura, platne_od) ještě není –
ruční úpravy přes admin tedy nikdy nepřepíše. Nad rámec vkládání navíc:
- doplní do existujících řádků chybějící klíče z `_BACKFILL_KLICE`
  (jen hodnoty, které jsou None/chybí – vyplněné nikdy nepřepisuje),
- opraví přesně známé chybné hodnoty z dřívějších seedů (`_BACKFILL_OPRAVY`):
  přepíše (příp. odstraní) se jen hodnota, která se PŘESNĚ rovná známé chybné,
  s dovětkem o zdroji do poznámky – ruční úpravy adminem zůstávají nedotčené.

POZOR na jednotky: výměr uvádí ceny v Kč/kW/MĚSÍC (resp. Kč/MW/měsíc), ale klíč
`cena_rezervovana_kapacita_kc_kw_rok` je ROČNÍ sazba (kap. 4.1 násobí
rezervovanou kapacitu tímto číslem jednou = roční náklad) → ukládá se ×12
z měsíční ceny za ROČNÍ rezervovanou kapacitu. Klíč `cena_mesicni_rk_kc_kw_mesic`
je měsíční cena za MĚSÍČNÍ rezervovanou kapacitu (jiný produkt, dražší) –
potřebná pro pokutu za překročení (1,5× dle bodu 4.24 výměru) a pro
optimalizaci kombinace roční + měsíční RK.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.nabidkovac.models import SazbaDistributoru

# Platnost pro celý rok 2026 (CV č. 13/2025 platí od 1. 1. 2026).
_PLATNE_OD_2026 = date(2026, 1, 1)
_PLATNE_DO_2026 = date(2026, 12, 31)

# Nová tarifní struktura ERÚ platí od 1. 1. 2027.
_PLATNE_OD_2027 = date(2027, 1, 1)

_ZDROJ_2026 = "CV ERÚ č. 13/2025 (ERV 17/2025), bod 4.18"
_ZDROJ_2027 = "informativní CV ERÚ k NTS (5/2026)"

# Pokuta za překročení RK se v sazebníku NEdrží jako samostatné číslo – výpočet
# ji odvozuje jako 1,5× měsíční cena měsíční RK (bod 4.24 výměru; audit PS-2,
# `peak_shaving.pokuta_prekroceni_rk_kc_kw`). Dřívější seed hodnoty 1108/521
# byly ceny za překročení rezervovaného VÝKONU (dodávka do sítě, bod 4.38) –
# odstraňuje je cílená oprava v `_BACKFILL_OPRAVY`.

# Ceny za rezervovanou kapacitu 2026, Kč/kW/měsíc, bez DPH (zdroj: _ZDROJ_2026).
# `rocni` = měsíční cena za ROČNÍ RK, `mesicni` = měsíční cena za MĚSÍČNÍ RK.
_RK_2026 = {
    ("cez", "vn"): {"rocni": 252.565, "mesicni": 281.823},
    ("cez", "vvn"): {"rocni": 117.432, "mesicni": 131.036},
    ("egd", "vn"): {"rocni": 230.551, "mesicni": 254.260},
    ("egd", "vvn"): {"rocni": 110.826, "mesicni": 122.223},
    ("pre", "vn"): {"rocni": 271.093, "mesicni": 299.351},
    ("pre", "vvn"): {"rocni": 129.580, "mesicni": 143.087},
}

# NTS 2027, Kč/kW/měsíc, bez DPH (zdroj: _ZDROJ_2027, body 4.2/4.3).
# t1/t2 = dvojice (kapacita = cena za RP, spicka = cena za max. odebraný výkon);
# `prekroceni` = pevná cena za překročení rezervovaného příkonu.
_NTS_2027 = {
    ("cez", "vn"): {"t1_kap": 190.133, "t1_sp": 19.013, "t2_kap": 22.743, "t2_sp": 227.429, "prekroceni": 761.0},
    ("cez", "vvn"): {"t1_kap": 96.862, "t1_sp": 9.686, "t2_kap": 11.586, "t2_sp": 115.862, "prekroceni": 387.0},
    ("egd", "vn"): {"t1_kap": 181.386, "t1_sp": 18.139, "t2_kap": 21.697, "t2_sp": 216.967, "prekroceni": 726.0},
    ("egd", "vvn"): {"t1_kap": 87.770, "t1_sp": 8.777, "t2_kap": 10.499, "t2_sp": 104.987, "prekroceni": 351.0},
    ("pre", "vn"): {"t1_kap": 196.298, "t1_sp": 19.630, "t2_kap": 23.480, "t2_sp": 234.804, "prekroceni": 785.0},
    ("pre", "vvn"): {"t1_kap": 109.073, "t1_sp": 10.907, "t2_kap": 13.047, "t2_sp": 130.470, "prekroceni": 436.0},
}

# Prahy koeficientu AKU (část 24 informativního CV; jednotné pro všechny RDS).
# Předběžné hodnoty – konečná podoba projde veřejnou konzultací ERÚ 10/2026.
_AKU_PRAHY = {"vn": (0.60, 0.75), "vvn": (0.60, 0.70)}

_NAZVY_DSO = {"cez": "ČEZ", "egd": "EG.D", "pre": "PRE"}


def _cz(cislo: float) -> str:
    """Číslo do české poznámky (desetinná čárka)."""
    return f"{cislo:g}".replace(".", ",")


def _rocni_sazba_rk(mesicni_cena_rocni_rk: float) -> float:
    """Kč/kW/měsíc (roční RK) → Kč/kW/rok (kap. 4.1 násobí jednou za rok)."""
    return round(mesicni_cena_rocni_rk * 12, 2)


def _radek_2026(distributor: str, hladina: str) -> dict:
    rk = _RK_2026[(distributor, hladina)]
    return {
        "distributor": distributor,
        "napetova_hladina": hladina,
        "struktura_tarifu": "stara_2026",
        "parametry": {
            "cena_rezervovana_kapacita_kc_kw_rok": _rocni_sazba_rk(rk["rocni"]),
            "cena_mesicni_rk_kc_kw_mesic": rk["mesicni"],
        },
        "platne_od": _PLATNE_OD_2026,
        "platne_do": _PLATNE_DO_2026,
        "poznamka": (
            f"{_NAZVY_DSO[distributor]} {hladina.upper()} 2026, bez DPH ({_ZDROJ_2026}): "
            f"roční RK {_cz(rk['rocni'])} Kč/kW/měs (= {_cz(_rocni_sazba_rk(rk['rocni']))} Kč/kW/rok), "
            f"měsíční RK {_cz(rk['mesicni'])} Kč/kW/měs. Pokuta za překročení RK se "
            f"odvozuje výpočtem: 1,5× měsíční RK (bod 4.24)."
        ),
    }


def _radek_2027(distributor: str, hladina: str) -> dict:
    nts = _NTS_2027[(distributor, hladina)]
    u1, u2 = _AKU_PRAHY[hladina]
    return {
        "distributor": distributor,
        "napetova_hladina": hladina,
        "struktura_tarifu": "nova_2027",
        "parametry": {
            "t1_kapacita_kc_kw_mesic": nts["t1_kap"],
            "t1_spicka_kc_kw_mesic": nts["t1_sp"],
            "t2_kapacita_kc_kw_mesic": nts["t2_kap"],
            "t2_spicka_kc_kw_mesic": nts["t2_sp"],
            "sazba_prekroceni_kc_kw_mesic": nts["prekroceni"],
            "u1_ucinnost": u1,
            "u2_ucinnost": u2,
        },
        "platne_od": _PLATNE_OD_2027,
        "platne_do": None,
        "je_modelovy_odhad": True,
        "poznamka": (
            f"{_NAZVY_DSO[distributor]} {hladina.upper()} 2027 – MODELOVÝ ODHAD "
            f"({_ZDROJ_2027}), závazné ceny ERÚ vyjdou ~11/2026."
        ),
    }


_SEED_SAZBY = [_radek_2026(d, h) for (d, h) in sorted(_RK_2026)] + [
    _radek_2027(d, h) for (d, h) in sorted(_NTS_2027)
]


# Klíče, které se do už existujících řádků smí DOPLNIT, když chybí/jsou None
# (vyplněné hodnoty se nikdy nepřepisují – neztratí se ruční úprava z adminu):
# prahy AKU (předběžné, v modelu se neaplikují – PS-3) a měsíční cena RK (PS-1/PS-2).
_BACKFILL_KLICE = ("u1_ucinnost", "u2_ucinnost", "cena_mesicni_rk_kc_kw_mesic")

# Cílené opravy přesně známých chybných hodnot z dřívějších seedů
# (audit 16. 7. 2026, bughunt PS-1/PS-2). Přepíše se JEN hodnota, která se
# přesně rovná `chybna` – ruční úpravy přes admin zůstávají nedotčené.
# `chybna=None` znamená doplnění dosud nedohledané (NULL) hodnoty.
_BACKFILL_OPRAVY = (
    {
        "distributor": "cez",
        "napetova_hladina": "vn",
        "struktura_tarifu": "stara_2026",
        "platne_od": _PLATNE_OD_2026,
        "klic": "cena_rezervovana_kapacita_kc_kw_rok",
        "chybna": 2847.72,  # 237,31 × 12 = sazba roku 2025 (CV č. 11/2024)
        "spravna": 3030.78,  # 252,565 × 12 dle CV č. 13/2025
        "poznamka_dodatek": (
            "OPRAVA (audit 16. 7. 2026): 2847,72 Kč/kW/rok byla sazba 2025; "
            "pro 2026 platí 3030,78 Kč/kW/rok dle CV č. 13/2025 (ERV 17/2025)."
        ),
    },
    {
        "distributor": "cez",
        "napetova_hladina": "vvn",
        "struktura_tarifu": "stara_2026",
        "platne_od": _PLATNE_OD_2026,
        "klic": "cena_rezervovana_kapacita_kc_kw_rok",
        "chybna": None,  # v původním seedu „nedohledáno“
        "spravna": 1409.18,  # 117,432 × 12 dle CV č. 13/2025
        "poznamka_dodatek": (
            "DOPLNĚNO (audit 16. 7. 2026): roční RK VVN 117,432 Kč/kW/měs "
            "= 1409,18 Kč/kW/rok dle CV č. 13/2025 (ERV 17/2025)."
        ),
    },
    # Odstranění chybné pokuty (bughunt PS-2): 1108/521 Kč/kW/měs jsou ceny za
    # překročení rezervovaného VÝKONU (bod 4.38, dodávka do sítě), ne kapacity.
    # Pokuta za překročení RK se nově odvozuje výpočtem (1,5× měsíční RK).
    {
        "distributor": "cez",
        "napetova_hladina": "vn",
        "struktura_tarifu": "stara_2026",
        "platne_od": _PLATNE_OD_2026,
        "klic": "cena_prekroceni_kc_kw",
        "chybna": 1108.0,
        "spravna": None,
        "poznamka_dodatek": (
            "OPRAVA (audit 16. 7. 2026): pokuta 1108 Kč/kW/měs patřila překročení "
            "rezervovaného VÝKONU (bod 4.38); překročení RK se nově odvozuje "
            "výpočtem jako 1,5× měsíční RK (bod 4.24) = 422,73 Kč/kW/měs."
        ),
    },
    {
        "distributor": "cez",
        "napetova_hladina": "vvn",
        "struktura_tarifu": "stara_2026",
        "platne_od": _PLATNE_OD_2026,
        "klic": "cena_prekroceni_kc_kw",
        "chybna": 521.0,
        "spravna": None,
        "poznamka_dodatek": (
            "OPRAVA (audit 16. 7. 2026): pokuta 521 Kč/kW/měs patřila překročení "
            "rezervovaného VÝKONU (bod 4.38); překročení RK se nově odvozuje "
            "výpočtem jako 1,5× měsíční RK (bod 4.24) = 196,55 Kč/kW/měs."
        ),
    },
)


def doplneni_chybejicich(parametry: dict, seed_parametry: dict) -> tuple[dict, bool]:
    """Doplní do parametrů klíče z `_BACKFILL_KLICE`, které chybí / jsou None.

    Vrací (nové parametry, došlo-li ke změně). Vyplněné hodnoty nechává být –
    idempotentní a bezpečné vůči ručním úpravám přes admin.
    """
    out = dict(parametry)
    zmena = False
    for k in _BACKFILL_KLICE:
        if out.get(k) is None and seed_parametry.get(k) is not None:
            out[k] = seed_parametry[k]
            zmena = True
    return out, zmena


def aplikuj_opravu(parametry: dict, poznamka: str, oprava: dict) -> tuple[dict, str, bool]:
    """Aplikuje jednu cílenou opravu z `_BACKFILL_OPRAVY` na (parametry, poznámku).

    Přepíše jen hodnotu PŘESNĚ rovnou známé chybné (`oprava["chybna"]`); cokoli
    jiného (ruční úprava adminem, už opravená hodnota) nechává být.
    `spravna=None` znamená odstranění klíče (pro klíče, které v sazebníku nemají
    co dělat). Dovětek do poznámky se přidá jen jednou. Vrací (parametry,
    poznámka, došlo-li ke změně).
    """
    aktualni = parametry.get(oprava["klic"])
    if aktualni != oprava["chybna"] or aktualni == oprava["spravna"]:
        return parametry, poznamka, False
    out = dict(parametry)
    if oprava["spravna"] is None:
        out.pop(oprava["klic"], None)
    else:
        out[oprava["klic"]] = oprava["spravna"]
    nova_poznamka = poznamka or ""
    dodatek = oprava.get("poznamka_dodatek") or ""
    if dodatek and dodatek not in nova_poznamka:
        nova_poznamka = (nova_poznamka.rstrip() + " " + dodatek).strip()
    return out, nova_poznamka, True


def seed_sazby(db: Session) -> int:
    """Idempotentně vloží výchozí sazby a ošetří existující řádky.

    Vrací počet nově vložených řádků. U existujících řádků:
    1. doplní chybějící klíče z `_BACKFILL_KLICE` (nepřepisuje vyplněné),
    2. aplikuje cílené opravy `_BACKFILL_OPRAVY` (přepíše jen přesně známé
       chybné hodnoty, s dovětkem o zdroji do poznámky).
    """
    vlozeno = 0
    zmeneno = False
    for r in _SEED_SAZBY:
        existujici = (
            db.query(SazbaDistributoru)
            .filter(
                SazbaDistributoru.distributor == r["distributor"],
                SazbaDistributoru.napetova_hladina == r["napetova_hladina"],
                SazbaDistributoru.struktura_tarifu == r["struktura_tarifu"],
                SazbaDistributoru.platne_od == r["platne_od"],
            )
            .first()
        )
        if existujici is not None:
            if isinstance(existujici.parametry, dict) and isinstance(r.get("parametry"), dict):
                p, doplneno = doplneni_chybejicich(existujici.parametry, r["parametry"])
                if doplneno:
                    existujici.parametry = p  # reassign kvůli detekci změny JSONB
                    zmeneno = True
            continue
        db.add(SazbaDistributoru(**r))
        vlozeno += 1

    for o in _BACKFILL_OPRAVY:
        radek = (
            db.query(SazbaDistributoru)
            .filter(
                SazbaDistributoru.distributor == o["distributor"],
                SazbaDistributoru.napetova_hladina == o["napetova_hladina"],
                SazbaDistributoru.struktura_tarifu == o["struktura_tarifu"],
                SazbaDistributoru.platne_od == o["platne_od"],
            )
            .first()
        )
        if radek is None or not isinstance(radek.parametry, dict):
            continue
        p, poznamka, zmena = aplikuj_opravu(radek.parametry, radek.poznamka or "", o)
        if zmena:
            radek.parametry = p
            radek.poznamka = poznamka
            zmeneno = True

    if vlozeno or zmeneno:
        db.commit()
    return vlozeno
