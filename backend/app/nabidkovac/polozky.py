"""Rozpis položek nabídky a objednávky – jeden výpočet pro obě strany (CRM-08).

Proč vlastní modul: položky nabídky (`nabidka_polozky`) a položky objednávky
(`crm_objednavka_polozky`) mají schválně stejné sloupce, protože se z nabídky
do objednávky překlápějí. Kdyby si každá strana počítala součet po svém,
překlopená objednávka by mohla ukázat jinou částku než nabídka, ze které
vznikla – a nikdo by nevěděl, která z nich lže.

Zaokrouhlování: každá položka se zaokrouhlí na haléře PŘED sečtením
(`ROUND_HALF_UP`, jak to dělá účetnictví), ne až výsledek. Jinak by součet
v appce a součet na faktuře z POHODY mohl skončit o korunu vedle.

Nákupní ceny a marže se počítají vždy, ale do API je pouští jen route
s právem `nabidkovac_katalog` (rozhodl Dan 31. 7. 2026).
"""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

# Na kolik desetinných míst se zaokrouhluje peněžní částka.
_HALERE = Decimal("0.01")


def _dec(hodnota) -> Decimal:
    """Bezpečný převod na Decimal – None i prázdno je nula."""
    if hodnota is None or hodnota == "":
        return Decimal("0")
    if isinstance(hodnota, Decimal):
        return hodnota
    return Decimal(str(hodnota))


def _zaokrouhli(hodnota: Decimal) -> Decimal:
    return hodnota.quantize(_HALERE, rounding=ROUND_HALF_UP)


def radek_soucty(polozka) -> dict:
    """Spočítá jeden řádek rozpisu.

    Vrací slovník s částkami bez DPH, s DPH, nákupem a marží. Sleva se
    uplatňuje na jednotkovou cenu, ne na řádek – tak to lidé čtou v nabídce
    („panel za 4 500 Kč se slevou 10 %“), a u zlomkových množství to nedává
    jiný výsledek jen kvůli pořadí operací.
    """
    mnozstvi = _dec(getattr(polozka, "mnozstvi", 0))
    cena = _dec(getattr(polozka, "cena_jednotkova", 0))
    sleva = _dec(getattr(polozka, "sleva_procent", 0))
    nakup = _dec(getattr(polozka, "nakup_jednotkovy", 0))
    dph = _dec(getattr(polozka, "sazba_dph", 0))

    cena_po_sleve = cena * (Decimal("1") - sleva / Decimal("100"))
    bez_dph = _zaokrouhli(mnozstvi * cena_po_sleve)
    castka_dph = _zaokrouhli(bez_dph * dph)
    nakup_celkem = _zaokrouhli(mnozstvi * nakup)

    return {
        "cena_po_sleve": _zaokrouhli(cena_po_sleve),
        "bez_dph": bez_dph,
        "dph": castka_dph,
        "s_dph": bez_dph + castka_dph,
        "nakup_celkem": nakup_celkem,
        "marze_kc": bez_dph - nakup_celkem,
    }


def souhrn(polozky) -> dict:
    """Sečte rozpis. Vrací floaty, protože jde rovnou do JSON odpovědi.

    `marze_procent` je marže z PRODEJNÍ ceny (obchodní marže), ne přirážka
    k nákupu – to je číslo, se kterým vedení pracuje. Když nákup není u žádné
    položky vyplněný, vrací se None místo klamavých 100 %.
    """
    bez_dph = Decimal("0")
    dph = Decimal("0")
    nakup = Decimal("0")
    ma_nakup = False

    for p in polozky:
        r = radek_soucty(p)
        bez_dph += r["bez_dph"]
        dph += r["dph"]
        nakup += r["nakup_celkem"]
        if getattr(p, "nakup_jednotkovy", None) is not None:
            ma_nakup = True

    marze_kc = bez_dph - nakup if ma_nakup else None
    marze_procent = None
    if ma_nakup and bez_dph != 0:
        marze_procent = float(
            ((bez_dph - nakup) / bez_dph * Decimal("100")).quantize(
                Decimal("0.1"), rounding=ROUND_HALF_UP
            )
        )

    return {
        "pocet": len(polozky),
        "bez_dph": float(bez_dph),
        "dph": float(dph),
        "s_dph": float(bez_dph + dph),
        "nakup_celkem": float(nakup) if ma_nakup else None,
        "marze_kc": float(marze_kc) if marze_kc is not None else None,
        "marze_procent": marze_procent,
    }


def polozka_out(p, s_nakupem: bool) -> dict:
    """Jeden řádek rozpisu pro API.

    `s_nakupem=False` znamená, že se nákupní cena ani marže do odpovědi vůbec
    nedostanou – ne že by se jen skryly na frontendu. Kdo nemá právo na
    katalog, nákupní ceny prostě nedostane ani přes vývojářskou konzoli.
    """
    r = radek_soucty(p)
    out = {
        "id": p.id,
        "poradi": p.poradi,
        "technologie_id": p.technologie_id,
        "kod": p.kod or "",
        "nazev": p.nazev,
        "popis": p.popis or "",
        "jednotka": p.jednotka or "ks",
        "mnozstvi": float(_dec(p.mnozstvi)),
        "cena_jednotkova": float(_dec(p.cena_jednotkova)) if p.cena_jednotkova is not None else None,
        "sleva_procent": float(_dec(p.sleva_procent)),
        "sazba_dph": float(_dec(p.sazba_dph)) if p.sazba_dph is not None else None,
        "celkem_bez_dph": float(r["bez_dph"]),
        "celkem_s_dph": float(r["s_dph"]),
    }
    if s_nakupem:
        out["nakup_jednotkovy"] = (
            float(_dec(p.nakup_jednotkovy)) if p.nakup_jednotkovy is not None else None
        )
        out["marze_kc"] = float(r["marze_kc"]) if p.nakup_jednotkovy is not None else None
    return out


def napln_z_katalogu(polozka, technologie) -> None:
    """Doplní do položky snapshot údajů z katalogu (název, kód, jednotka, ceny).

    Volá se jen při VZNIKU položky z katalogu. Pozdější změna ceníku se do
    existujících položek nepromítá schválně – nabídka odeslaná zákazníkovi
    se nesmí měnit sama.
    """
    polozka.technologie_id = technologie.id
    polozka.kod = technologie.kod or ""
    polozka.nazev = technologie.nazev
    polozka.jednotka = technologie.jednotka or "ks"
    polozka.cena_jednotkova = technologie.cena_kc
    polozka.nakup_jednotkovy = technologie.cena_nakup_kc
    polozka.sazba_dph = technologie.sazba_dph


def kopiruj(zdroj, cil_trida, **vazba):
    """Vytvoří kopii položky v druhé tabulce (nabídka → objednávka).

    Kopírují se i ceny včetně nákupní – objednávka musí umět spočítat marži
    i tehdy, když se nabídka později smaže.
    """
    return cil_trida(
        poradi=zdroj.poradi,
        technologie_id=zdroj.technologie_id,
        kod=zdroj.kod or "",
        nazev=zdroj.nazev,
        popis=zdroj.popis or "",
        jednotka=zdroj.jednotka or "ks",
        mnozstvi=zdroj.mnozstvi,
        cena_jednotkova=zdroj.cena_jednotkova,
        nakup_jednotkovy=zdroj.nakup_jednotkovy,
        sleva_procent=zdroj.sleva_procent,
        sazba_dph=zdroj.sazba_dph,
        **vazba,
    )


def uloz_rozpis(db: Session, vstup, existujici: list, vyrob_novou) -> None:
    """Uloží celý rozpis najednou: co zmizelo, se smaže; zbytek se přepíše.

    Ukládá se celá tabulka, ne řádek po řádku – editor je mřížka, ve které
    člověk přehodí pořadí, smaže dva řádky a jeden přidá, a pak dá Uložit.
    Kdyby to šlo po řádcích, půlka změn by se uložila a půlka ne, kdyby to
    v půlce spadlo.
    """
    podle_id = {p.id: p for p in existujici}
    ponechane: set[int] = set()

    for poradi, radek in enumerate(vstup.polozky):
        nazev = (radek.nazev or "").strip()
        if not nazev:
            raise HTTPException(status_code=422, detail="Každá položka musí mít název.")
        if radek.mnozstvi is None or radek.mnozstvi <= 0:
            raise HTTPException(
                status_code=422, detail=f"Množství u „{nazev}“ musí být větší než nula."
            )
        if radek.sleva_procent < 0 or radek.sleva_procent > 100:
            raise HTTPException(
                status_code=422, detail=f"Sleva u „{nazev}“ musí být mezi 0 a 100 %."
            )

        p = podle_id.get(radek.id) if radek.id else None
        if p is None:
            p = vyrob_novou()
            db.add(p)
        else:
            ponechane.add(p.id)

        p.poradi = poradi
        p.technologie_id = radek.technologie_id
        p.kod = (radek.kod or "").strip()
        p.nazev = nazev
        p.popis = (radek.popis or "").strip()
        p.jednotka = (radek.jednotka or "ks").strip() or "ks"
        p.mnozstvi = radek.mnozstvi
        p.cena_jednotkova = radek.cena_jednotkova
        p.sleva_procent = radek.sleva_procent
        p.sazba_dph = radek.sazba_dph
        # Nákupní cenu smí přepsat jen ten, kdo ji vidí. Kdo ji nevidí,
        # nepošle ji – a kdyby ji poslal, uloží se to, co tam bylo (níž).
        if radek.nakup_jednotkovy is not None:
            p.nakup_jednotkovy = radek.nakup_jednotkovy

    for p in existujici:
        if p.id not in ponechane:
            db.delete(p)
