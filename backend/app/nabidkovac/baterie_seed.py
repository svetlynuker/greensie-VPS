"""Naplnění katalogu `technologie` bateriemi z ceníku BESS.

Zdroj: docs/importy/pricelist-Simulační matice-2026-07-17.xlsx (list Pricelist)
– simulační matice jedné produktové řady: 84 konfigurací výkon × kapacita.

Mapování sloupců ceníku:
- „kW / Nominální výkon"            → Technologie.vykon_kw
- „kWh / nominální kapacita"        → Technologie.kapacita_kwh
- „efficiency / efektivita cyklu"   → Technologie.ucinnost (round-trip, 0–1)
- „dealer price / prodejní cena reálná" → Technologie.cena_kc; u konfigurací
  2 MW a víc ceník reálnou cenu neuvádí → použije se doporučená prodejní cena
- ostatní sloupce → Technologie.extra (vlastní sloupce katalogu, viz _SLOUPCE)

Seed je idempotentní: běží při startu appky, produkt se pozná podle
(typ="baterie", nazev) a existující řádky se NIKDY nepřepisují – ruční
úpravy cen/dostupnosti přes admin katalog tak zůstávají zachované. Stejně
tak definice vlastních sloupců se poznají podle `klic`.
"""

from sqlalchemy.orm import Session

from app.nabidkovac.models import KatalogSloupec, Technologie

# Vlastní sloupce katalogu pro data ceníku, která nemají vlastní pole modelu.
# Klíče jsou pevné (negenerují se z názvu), ať na ně jde spolehlivě sahat
# z výpočtů – peak shaving čte `uzitna_kapacita_kwh` (fallback kapacita_kwh).
_SLOUPCE = (
    # (klic, nazev, typ, poradi)
    ("max_vykon_stridacu_kw", "Reálný výkon střídačů (kW)", "cislo", 1),
    ("uzitna_kapacita_kwh", "Užitná kapacita (kWh)", "cislo", 2),
    ("typ_clanku", "Typ článku", "text", 3),
    ("doporucena_cena_kc", "Doporučená prodejní cena (Kč)", "cislo", 4),
    ("zaruka_roky", "Záruka (roky)", "cislo", 5),
)

# Řádky ceníku 1:1 (bez dopočítávání – co v XLSX chybí, je None):
# (vykon_kw, max_vykon_stridacu_kw, kapacita_kwh, uzitna_kapacita_kwh,
#  typ_clanku, ucinnost, doporucena_cena_kc, realna_cena_kc, zaruka_roky)
_BATERIE = (
    (50, 50, 220, 220, "NMC", 0.95, 1848823, 1663940.7, 10),
    (50, 50, 330, 330, "NMC", 0.95, 2318885, 2086996.5, 10),
    (50, 50, 440, 440, "NMC", 0.95, 2788946, 2510051.4, 10),
    (50, 50, 550, 550, "NMC", 0.95, 3259008, 2933107.2, 10),
    (50, 50, 660, 660, "NMC", 0.95, 4616969, 4155272.1, 10),
    (50, 50, 880, 880, "NMC", 0.95, 5557092, 5001382.8, 10),
    (50, 50, 1100, 1100, "NMC", 0.95, 6497215, 5847493.5, 10),
    (50, 50, 1650, 1650, "NMC", 0.95, 10044823, 9040340.7, 10),
    (50, 50, 2200, 2200, "NMC", 0.95, 12395131, 11155617.9, 10),
    (100, 100, 220, 220, "NMC", 0.95, 2003523, 1803170.7, 10),
    (100, 100, 330, 330, "NMC", 0.95, 2473585, 2226226.5, 10),
    (100, 100, 440, 440, "NMC", 0.95, 2943646, 2649281.4, 10),
    (100, 100, 550, 550, "NMC", 0.95, 3413708, 3072337.2, 10),
    (100, 100, 660, 660, "NMC", 0.95, 4771669, 4294502.1, 10),
    (100, 100, 880, 880, "NMC", 0.95, 5711792, 5140612.8, 10),
    (100, 100, 1100, 1100, "NMC", 0.95, 6651915, 5986723.5, 10),
    (100, 100, 1650, 1650, "NMC", 0.95, 10199523, 9179570.7, 10),
    (100, 100, 2200, 2200, "NMC", 0.95, 12549831, 11294847.9, 10),
    (200, 200, 220, 220, "NMC", 0.95, 2312923, 2081630.7, 10),
    (200, 200, 330, 330, "NMC", 0.95, 2782985, 2504686.5, 10),
    (200, 200, 440, 440, "NMC", 0.95, 3253046, 2927741.4, 10),
    (200, 200, 550, 550, "NMC", 0.95, 3723108, 3350797.2, 10),
    (200, 200, 660, 660, "NMC", 0.95, 5081069, 4572962.1, 10),
    (200, 200, 880, 880, "NMC", 0.95, 6021192, 5419072.8, 10),
    (200, 200, 1100, 1100, "NMC", 0.95, 6961315, 6265183.5, 10),
    (200, 200, 1650, 1650, "NMC", 0.95, 10508923, 9458030.7, 10),
    (200, 200, 2200, 2200, "NMC", 0.95, 12859231, 11573307.9, 10),
    (300, 300, 220, 220, "NMC", 0.95, 2622323, 2360090.7, 10),
    (300, 300, 330, 330, "NMC", 0.95, 3092385, 2783146.5, 10),
    (300, 300, 440, 440, "NMC", 0.95, 3562446, 3206201.4, 10),
    (300, 300, 550, 550, "NMC", 0.95, 4032508, 3629257.2, 10),
    (300, 300, 660, 660, "NMC", 0.95, 5390469, 4851422.1, 10),
    (300, 300, 880, 880, "NMC", 0.95, 6330592, 5697532.8, 10),
    (300, 300, 1100, 1100, "NMC", 0.95, 7270715, 6543643.5, 10),
    (300, 300, 1650, 1650, "NMC", 0.95, 10818323, 9736490.7, 10),
    (300, 300, 2200, 2200, "NMC", 0.95, 13168631, 11851767.9, 10),
    (400, 400, 220, 220, "NMC", 0.95, 2931723, 2638550.7, 10),
    (400, 400, 330, 330, "NMC", 0.95, 3401785, 3061606.5, 10),
    (400, 400, 440, 440, "NMC", 0.95, 3871846, 3484661.4, 10),
    (400, 400, 550, 550, "NMC", 0.95, 4341908, 3907717.2, 10),
    (400, 400, 660, 660, "NMC", 0.95, 5699869, 5129882.1, 10),
    (400, 400, 880, 880, "NMC", 0.95, 6639992, 5975992.8, 10),
    (400, 400, 1100, 1100, "NMC", 0.95, 7580115, 6822103.5, 10),
    (400, 400, 1650, 1650, "NMC", 0.95, 11127723, 10014950.7, 10),
    (400, 400, 2200, 2200, "NMC", 0.95, 13478031, 12130227.9, 10),
    (500, 500, 220, 220, "NMC", 0.95, 3241123, 2917010.7, 10),
    (500, 500, 330, 330, "NMC", 0.95, 3711185, 3340066.5, 10),
    (500, 500, 440, 440, "NMC", 0.95, 4181246, 3763121.4, 10),
    (500, 500, 550, 550, "NMC", 0.95, 4651308, 4186177.2, 10),
    (500, 500, 660, 660, "NMC", 0.95, 6009269, 5408342.1, 10),
    (500, 500, 880, 880, "NMC", 0.95, 6949392, 6254452.8, 10),
    (500, 500, 1100, 1100, "NMC", 0.95, 7889515, 7100563.5, 10),
    (500, 500, 1650, 1650, "NMC", 0.95, 11437123, 10293410.7, 10),
    (500, 500, 2200, 2200, "NMC", 0.95, 13787431, 12408687.9, 10),
    (800, 800, 220, 220, "NMC", 0.95, 4169323, 3752390.7, 10),
    (800, 800, 330, 330, "NMC", 0.95, 4639385, 4175446.5, 10),
    (800, 800, 440, 440, "NMC", 0.95, 5109446, 4598501.4, 10),
    (800, 800, 550, 550, "NMC", 0.95, 5579508, 5021557.2, 10),
    (800, 800, 660, 660, "NMC", 0.95, 6937469, 6243722.1, 10),
    (800, 800, 880, 880, "NMC", 0.95, 7877592, 7089832.8, 10),
    (800, 800, 1100, 1100, "NMC", 0.95, 8817715, 7935943.5, 10),
    (800, 800, 1650, 1650, "NMC", 0.95, 12365323, 11128790.7, 10),
    (800, 800, 2200, 2200, "NMC", 0.95, 14715631, 13244067.9, 10),
    (1000, 1000, 220, 220, "NMC", 0.95, 4788123, 4309310.7, 10),
    (1000, 1000, 330, 330, "NMC", 0.95, 5258185, 4732366.5, 10),
    (1000, 1000, 440, 440, "NMC", 0.95, 5728246, 5155421.4, 10),
    (1000, 1000, 550, 550, "NMC", 0.95, 6198308, 5578477.2, 10),
    (1000, 1000, 660, 660, "NMC", 0.95, 7556269, 6800642.1, 10),
    (1000, 1000, 880, 880, "NMC", 0.95, 8496392, 7646752.8, 10),
    (1000, 1000, 1100, 1100, "NMC", 0.95, 9436515, 8492863.5, 10),
    (1000, 1000, 1650, 1650, "NMC", 0.95, 12984123, 11685710.7, 10),
    (1000, 1000, 2200, 2200, "NMC", 0.95, 15334431, 13800987.9, 10),
    (2000, 2000, 2200, 2200, "NMC", 0.9, 18400000, None, None),
    (2000, 2000, 4400, 4400, "NMC", 0.95, 27800000, None, 10),
    (2000, 2000, 6600, 6600, "NMC", 0.95, 37200000, None, 10),
    (3000, 3000, 4400, 4400, "NMC", 0.95, 30900000, None, 10),
    (3000, 3000, 6600, 6600, "NMC", 0.95, 40300000, None, 10),
    (3000, 3000, 8800, 8800, "NMC", 0.95, 49700000, None, 10),
    (4000, 4000, 4400, 4400, "NMC", 0.95, 34000000, None, 10),
    (4000, 4000, 6600, 6600, "NMC", 0.95, 43400000, None, 10),
    (4000, 4000, 8800, 8800, "NMC", 0.95, 52800000, None, 10),
    (5000, 5000, 6600, 6600, "NMC", 0.95, 46500000, None, 10),
    (5000, 5000, 8800, 8800, "NMC", 0.95, 55900000, None, 10),
    (6000, 6000, 8800, 8800, "NMC", 0.95, 59000000, None, 10),
)


def nazev_baterie(vykon_kw: float, kapacita_kwh: float) -> str:
    """Jednotný název konfigurace – zároveň idempotenční klíč seedu."""
    return f"BESS {vykon_kw:g} kW / {kapacita_kwh:g} kWh"


def seed_baterie(db: Session) -> int:
    """Idempotentně založí vlastní sloupce katalogu a baterie z ceníku.

    Vrací počet nově vložených baterií. Existující řádky (podle názvu, resp.
    klíče sloupce) nechává beze změny.
    """
    zmena = False

    existujici_klice = {k for (k,) in db.query(KatalogSloupec.klic).all()}
    for klic, nazev, typ, poradi in _SLOUPCE:
        if klic in existujici_klice:
            continue
        db.add(KatalogSloupec(klic=klic, nazev=nazev, typ=typ, poradi=poradi))
        zmena = True

    existujici_nazvy = {
        n for (n,) in db.query(Technologie.nazev).filter(Technologie.typ == "baterie").all()
    }
    vlozeno = 0
    for vykon, max_kw, kapacita, uzitna, clanek, ucinnost, dop_cena, real_cena, zaruka in _BATERIE:
        nazev = nazev_baterie(vykon, kapacita)
        if nazev in existujici_nazvy:
            continue
        extra = {
            "max_vykon_stridacu_kw": float(max_kw),
            "uzitna_kapacita_kwh": float(uzitna),
            "typ_clanku": clanek,
            "doporucena_cena_kc": float(dop_cena),
        }
        if zaruka is not None:
            extra["zaruka_roky"] = float(zaruka)
        db.add(
            Technologie(
                typ="baterie",
                nazev=nazev,
                model="",
                vykon_kw=vykon,
                kapacita_kwh=kapacita,
                # Reálná prodejní cena; velké konfigurace (2 MW+) ji v ceníku
                # nemají → doporučená prodejní cena.
                cena_kc=(real_cena if real_cena is not None else dop_cena),
                ucinnost=ucinnost,
                dostupnost=True,
                extra=extra,
            )
        )
        vlozeno += 1
        zmena = True

    if zmena:
        db.commit()
    return vlozeno
