"""Naplnění tabulky `sazby_distributoru` výchozími daty (METODIKA kap. 3.1, 6–7).

Naostro jedeme zatím JEN s ČEZ Distribuce, rok 2026, struktura `stara_2026`
(kap. 6 bod 5). EG.D, PRE a rok 2027 (`nova_2027`) se do tabulky NEvkládají –
zůstávají prázdné a doplní se přes admin rozhraní, až budou čísla ověřená,
resp. až je ERÚ zveřejní (kap. 7).

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

# Pokuta za překročení – jednotná regulovaná sazba ERÚ (kap. 3.1), Kč/kW/měsíc.
_POKUTA_VN = 1108.0
_POKUTA_VVN = 521.0

# ČEZ rezervovaná kapacita VN: 237,31 Kč/kW/měsíc (potvrzeno) → ročně × 12.
_REZERVACE_CEZ_VN_ROK = round(237.31 * 12, 2)  # = 2847.72

_SEED_CEZ_2026 = [
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
]


def seed_sazby(db: Session) -> int:
    """Idempotentně vloží výchozí sazby ČEZ 2026. Vrací počet nově vložených řádků."""
    vlozeno = 0
    for r in _SEED_CEZ_2026:
        existuje = (
            db.query(SazbaDistributoru.id)
            .filter(
                SazbaDistributoru.distributor == r["distributor"],
                SazbaDistributoru.napetova_hladina == r["napetova_hladina"],
                SazbaDistributoru.struktura_tarifu == r["struktura_tarifu"],
                SazbaDistributoru.platne_od == r["platne_od"],
            )
            .first()
        )
        if existuje is not None:
            continue
        db.add(SazbaDistributoru(**r))
        vlozeno += 1
    if vlozeno:
        db.commit()
    return vlozeno
