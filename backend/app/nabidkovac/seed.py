"""Naplnění tabulky `sazby_distributoru` výchozími daty (METODIKA kap. 3.1, 6–7).

Naostro jedeme zatím JEN s ČEZ Distribuce:
- `stara_2026` (VN + VVN) – ostrá čísla pro rok 2026 (kap. 6 bod 5),
- `nova_2027` (VN + VVN) – MODELOVÝ odhad pro rok 2027 (`je_modelovy_odhad`),
  závazné ceny ERÚ vyjdou až ~11/2026 (PROMPT 2027).
EG.D a PRE se do tabulky NEvkládají – doplní se přes admin, až budou čísla
ověřená.

Seed je idempotentní: běží při startu appky a vloží řádek jen tehdy, když
stejná kombinace (distributor, hladina, struktura, platne_od) ještě není –
takže ruční úpravy přes admin nikdy nepřepíše.

POZOR na jednotky: zdrojová čísla v dokumentu jsou v Kč/kW/MĚSÍC, ale klíč
`cena_rezervovana_kapacita_kc_kw_rok` je ROČNÍ sazba (kap. 4.1 násobí
rezervovanou kapacitu tímto číslem jednou = roční náklad). Rezervovanou
kapacitu proto ukládáme přepočtenou na rok (× 12). Pokuta za překročení se
naopak účtuje po měsících (kap. 4.1 sečte přes 12 měsíců), takže se ukládá
tak, jak je v dokumentu (Kč/kW za měsíc překročení).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.nabidkovac.models import SazbaDistributoru

# Platnost pro celý rok 2026 (ČEZ ceník služeb s platností od 1. 2. 2026).
_PLATNE_OD_2026 = date(2026, 1, 1)
_PLATNE_DO_2026 = date(2026, 12, 31)

# Nová tarifní struktura ERÚ platí od 1. 1. 2027 (PROMPT 2027).
_PLATNE_OD_2027 = date(2027, 1, 1)

# Pokuta za překročení – jednotná regulovaná sazba ERÚ (kap. 3.1), Kč/kW/měsíc.
_POKUTA_VN = 1108.0
_POKUTA_VVN = 521.0

# ČEZ rezervovaná kapacita VN: 237,31 Kč/kW/měsíc (potvrzeno) → ročně × 12.
_REZERVACE_CEZ_VN_ROK = round(237.31 * 12, 2)  # = 2847.72

_SEED_CEZ = [
    {
        "distributor": "cez",
        "napetova_hladina": "vn",
        "struktura_tarifu": "stara_2026",
        "parametry": {
            "cena_rezervovana_kapacita_kc_kw_rok": _REZERVACE_CEZ_VN_ROK,
            "cena_prekroceni_kc_kw": _POKUTA_VN,
        },
        "platne_od": _PLATNE_OD_2026,
        "platne_do": _PLATNE_DO_2026,
        "poznamka": (
            "ČEZ 2026, bez DPH. Rezervovaná kapacita 237,31 Kč/kW/měsíc "
            "(potvrzeno, ceník ČEZ od 1. 2. 2026) přepočteno na rok × 12. "
            "Pokuta 1108 Kč/kW/měsíc (regulovaná ERÚ)."
        ),
    },
    {
        # VVN: pokuta je regulovaná (známe ji), ale rezervovanou kapacitu ČEZ
        # VVN se nepodařilo dohledat (kap. 3.1) → necháváme NULL na doplnění.
        "distributor": "cez",
        "napetova_hladina": "vvn",
        "struktura_tarifu": "stara_2026",
        "parametry": {
            "cena_rezervovana_kapacita_kc_kw_rok": None,
            "cena_prekroceni_kc_kw": _POKUTA_VVN,
        },
        "platne_od": _PLATNE_OD_2026,
        "platne_do": _PLATNE_DO_2026,
        "poznamka": (
            "ČEZ 2026, bez DPH. Pokuta 521 Kč/kW/měsíc (regulovaná ERÚ). "
            "Rezervovaná kapacita ČEZ VVN NEDOHLEDÁNO – doplní admin."
        ),
    },
    # --- nová struktura 2027 (dvousložkový tarif ERÚ) – MODELOVÝ ODHAD -------
    # Čísla nejsou finální, závazné cenové rozhodnutí ERÚ vyjde v listopadu 2026
    # (PROMPT 2027). Vše bez DPH, Kč/kW/měsíc. Penalizace = 4× T1 kapacita.
    {
        "distributor": "cez",
        "napetova_hladina": "vn",
        "struktura_tarifu": "nova_2027",
        "parametry": {
            "t1_kapacita_kc_kw_mesic": 190.133,
            "t1_spicka_kc_kw_mesic": 19.013,
            "t2_kapacita_kc_kw_mesic": 22.743,
            "t2_spicka_kc_kw_mesic": 227.429,
            "sazba_prekroceni_kc_kw_mesic": 761.0,
            # Prahy účinnosti pro Koeficient AKU (kap. 4.8), VN.
            "u1_ucinnost": 0.60,
            "u2_ucinnost": 0.75,
        },
        "platne_od": _PLATNE_OD_2027,
        "platne_do": None,
        "je_modelovy_odhad": True,
        "poznamka": "ČEZ 2027 VN – MODELOVÝ ODHAD (ne finální ceny ERÚ, rozhodnutí ~11/2026).",
    },
    {
        "distributor": "cez",
        "napetova_hladina": "vvn",
        "struktura_tarifu": "nova_2027",
        "parametry": {
            "t1_kapacita_kc_kw_mesic": 96.862,
            "t1_spicka_kc_kw_mesic": 9.686,
            "t2_kapacita_kc_kw_mesic": 11.586,
            "t2_spicka_kc_kw_mesic": 115.862,
            "sazba_prekroceni_kc_kw_mesic": 387.0,
            # Prahy účinnosti pro Koeficient AKU (kap. 4.8), VVN (U2 = 0,70).
            "u1_ucinnost": 0.60,
            "u2_ucinnost": 0.70,
        },
        "platne_od": _PLATNE_OD_2027,
        "platne_do": None,
        "je_modelovy_odhad": True,
        "poznamka": "ČEZ 2027 VVN – MODELOVÝ ODHAD (ne finální ceny ERÚ, rozhodnutí ~11/2026).",
    },
]


# Klíče, které se do už existujících řádků smí doplnit (ne přepsat) – nově
# přidané prahy Koeficientu AKU (kap. 4.8). Ceny (T1/T2) nikdy nepřepisujeme,
# ať se neztratí případná ruční úprava přes admin.
_BACKFILL_KLICE = ("u1_ucinnost", "u2_ucinnost")


def seed_sazby(db: Session) -> int:
    """Idempotentně vloží výchozí sazby ČEZ a doplní chybějící prahy AKU.

    Vrací počet nově vložených řádků. U existujících `nova_2027` řádků jen
    dorovná chybějící klíče z `_BACKFILL_KLICE` (nepřepisuje už vyplněné hodnoty).
    """
    vlozeno = 0
    zmeneno = False
    for r in _SEED_CEZ:
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
            # Backfill chybějících prahů AKU do už existujícího řádku.
            if isinstance(existujici.parametry, dict) and isinstance(r.get("parametry"), dict):
                p = dict(existujici.parametry)
                doplneno = False
                for k in _BACKFILL_KLICE:
                    if p.get(k) is None and r["parametry"].get(k) is not None:
                        p[k] = r["parametry"][k]
                        doplneno = True
                if doplneno:
                    existujici.parametry = p  # reassign kvůli detekci změny JSONB
                    zmeneno = True
            continue
        db.add(SazbaDistributoru(**r))
        vlozeno += 1
    if vlozeno or zmeneno:
        db.commit()
    return vlozeno
