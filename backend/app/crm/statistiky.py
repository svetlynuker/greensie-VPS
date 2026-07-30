"""Souhrny obchodu pro grafy: funnel, forecast, důvody proher.

Jeden modul a jeden endpoint schválně — dashboard potřebuje všechna čísla
naráz a pět samostatných dotazů by znamenalo pět kol na server a pět míst,
kde se může „otevřený případ" definovat jinak.

---- Co je čí ---------------------------------------------------------------

`omez_na_moje` se tu NEOBCHÁZÍ: OZ vidí ve statistikách svoje čísla, vedení
(právo `crm_vse`) čísla celé firmy. Je to tentýž filtr jako v seznamech, takže
souhrn nad tabulkou a graf nad ním vždycky souhlasí — jinak by lidé hlásili
„v tabulce mám 5 případů, ale graf ukazuje 30".

---- Proč se posílá `data_od` ----------------------------------------------

Import z Raynetu se dělat nebude (rozhodnutí 30. 7. 2026), takže appka zná jen
zakázky založené od svého spuštění. Bez téhle informace by graf vypadal, jako
že obchod spadl na nulu. `data_od` je datum nejstaršího případu v CRM a UI ho
píše ke grafům (CRM-45).
"""

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmStav, ObchodniPripad
from app.crm.pristup import omez_na_moje


def _pripady(db: Session, user: User):
    """Základní dotaz na případy s uplatněnou viditelností."""
    return omez_na_moje(db.query(ObchodniPripad), ObchodniPripad, user)


def funnel(db: Session, user: User) -> list[dict]:
    """Počet a hodnota případů v jednotlivých fázích pipeline.

    Vrací VŠECHNY fáze v pořadí kanbanu, i prázdné — díra v cestě zakázky je
    informace („z kvalifikace nám nic nepokračuje do nabídky"), a kdyby se
    prázdné fáze vynechaly, funnel by se opticky zacelil.
    """
    stavy = (
        db.query(CrmStav)
        .filter(CrmStav.entita == "op")
        .order_by(CrmStav.poradi, CrmStav.id)
        .all()
    )
    souhrny = dict(
        (klic, (pocet, float(hodnota or 0)))
        for klic, pocet, hodnota in _pripady(db, user)
        .with_entities(
            ObchodniPripad.stav,
            func.count(ObchodniPripad.id),
            func.sum(ObchodniPripad.hodnota_kc),
        )
        .group_by(ObchodniPripad.stav)
        .all()
    )
    return [
        {
            "klic": s.klic,
            "nazev": s.nazev,
            "druh": s.druh,
            "barva": s.barva or "",
            "pocet": souhrny.get(s.klic, (0, 0.0))[0],
            "hodnota_kc": souhrny.get(s.klic, (0, 0.0))[1],
        }
        for s in stavy
    ]


def forecast(db: Session, user: User, mesicu: int = 6) -> list[dict]:
    """Očekávané uzavření po měsících: hrubá hodnota i vážená pravděpodobností.

    Vážená hodnota (hodnota × pravděpodobnost) je to, s čím se dá počítat —
    hrubý součet pipeline je vždycky optimističtější než realita. Posílá se
    obojí, aby bylo vidět i to, kolik je „na stole".

    Případy BEZ předpokládaného uzavření se do forecastu nepočítají, ale vrací
    se zvlášť jako `bez_terminu` — jinak by se tvářily jako nulová hodnota
    a nikdo by nevěděl, že v pipeline leží zakázky bez data.
    """
    dnes = date.today()
    od = date(dnes.year, dnes.month, 1)

    radky = (
        _pripady(db, user)
        .with_entities(
            ObchodniPripad.predpokladane_uzavreni,
            ObchodniPripad.hodnota_kc,
            ObchodniPripad.pravdepodobnost,
            CrmStav.druh,
        )
        .outerjoin(
            CrmStav,
            (CrmStav.klic == ObchodniPripad.stav) & (CrmStav.entita == "op"),
        )
        .all()
    )

    # Připravená mřížka měsíců, aby v grafu nechyběl měsíc bez zakázek.
    mrizka: dict[str, dict] = {}
    for i in range(mesicu):
        m = (od.month - 1 + i) % 12 + 1
        r = od.year + (od.month - 1 + i) // 12
        mrizka[f"{r}-{m:02d}"] = {"mesic": f"{r}-{m:02d}", "hodnota_kc": 0.0, "vazena_kc": 0.0, "pocet": 0}

    bez_terminu = {"pocet": 0, "hodnota_kc": 0.0}
    for termin, hodnota, pravdep, druh in radky:
        # Do forecastu patří jen otevřené případy — vyhrané už nejsou předpověď
        # a prohrané by ji nadhodnocovaly.
        if druh is not None and druh != "otevreny":
            continue
        castka = float(hodnota or 0)
        if termin is None:
            bez_terminu["pocet"] += 1
            bez_terminu["hodnota_kc"] += castka
            continue
        klic = f"{termin.year}-{termin.month:02d}"
        if klic not in mrizka:
            continue  # mimo zobrazené okno
        mrizka[klic]["pocet"] += 1
        mrizka[klic]["hodnota_kc"] += castka
        mrizka[klic]["vazena_kc"] += castka * (float(pravdep or 0) / 100.0)

    return [{"mesice": list(mrizka.values()), "bez_terminu": bez_terminu}]


def duvody_proher(db: Session, user: User) -> list[dict]:
    """Rozpad prohraných případů podle důvodu.

    Kvůli tomuhle se důvod prohry vynucuje — jinak by se za měsíc nikdo
    nevzpomněl, proč zakázka spadla.
    """
    prohry = (
        _pripady(db, user)
        .join(CrmStav, (CrmStav.klic == ObchodniPripad.stav) & (CrmStav.entita == "op"))
        .filter(CrmStav.druh == "prohra")
        .with_entities(
            ObchodniPripad.duvod_prohry,
            func.count(ObchodniPripad.id),
            func.sum(ObchodniPripad.hodnota_kc),
        )
        .group_by(ObchodniPripad.duvod_prohry)
        .all()
    )
    out = [
        {
            "duvod": (duvod or "").strip() or "Neuvedeno",
            "pocet": pocet,
            "hodnota_kc": float(hodnota or 0),
        }
        for duvod, pocet, hodnota in prohry
    ]
    return sorted(out, key=lambda x: (-x["pocet"], x["duvod"]))


def souhrn(db: Session, user: User) -> dict:
    """Čísla do KPI dlaždic + `data_od` pro poznámku o rozsahu dat."""
    podle_druhu = dict(
        (druh, (pocet, float(hodnota or 0)))
        for druh, pocet, hodnota in _pripady(db, user)
        .outerjoin(
            CrmStav, (CrmStav.klic == ObchodniPripad.stav) & (CrmStav.entita == "op")
        )
        .with_entities(
            CrmStav.druh,
            func.count(ObchodniPripad.id),
            func.sum(ObchodniPripad.hodnota_kc),
        )
        .group_by(CrmStav.druh)
        .all()
    )
    otevrene = podle_druhu.get("otevreny", (0, 0.0))
    vyhry = podle_druhu.get("vyhra", (0, 0.0))
    prohry = podle_druhu.get("prohra", (0, 0.0))
    uzavrene = vyhry[0] + prohry[0]

    nejstarsi = _pripady(db, user).with_entities(
        func.min(ObchodniPripad.vytvoreno_at)
    ).scalar()

    return {
        "otevrenych": otevrene[0],
        "hodnota_otevrenych_kc": otevrene[1],
        "vyhranych": vyhry[0],
        "hodnota_vyhranych_kc": vyhry[1],
        "prohranych": prohry[0],
        "hodnota_prohranych_kc": prohry[1],
        # Úspěšnost se počítá jen z UZAVŘENÝCH případů. Kdyby se dělila všemi,
        # klesala by při každém novém případu v pipeline, což nic neříká.
        "uspesnost_pct": round(vyhry[0] / uzavrene * 100, 1) if uzavrene else None,
        "data_od": nejstarsi.date().isoformat() if nejstarsi else None,
    }


# ---- Můj den (CRM-16) -------------------------------------------------------
# Jedna obrazovka s tím, co člověka tlačí. Vedle „moje úkoly" na Rozcestníku
# přidává dvě věci, které jinak nikdo nehlídá: případy, kde se dlouho nic
# nestalo, a nabídky odeslané bez reakce.

# Po kolika dnech se ticho začne považovat za problém. Prahy jsou různé
# schválně: u nabídky je týden bez reakce signál, u případu v pipeline ne.
TICHO_PRIPAD_DNI = 14
TICHO_NABIDKA_DNI = 7


def zanedbane_pripady(db: Session, user: User, dni: int = TICHO_PRIPAD_DNI) -> list[dict]:
    """Otevřené případy, u kterých se `dni` nic nestalo.

    „Nic se nestalo" = žádná aktivita, nebo poslední aktivita starší než práh.
    Případ bez JAKÉKOLI aktivity se počítá taky — právě ten se nejspíš ztratil.
    Řadí se od nejdéle mlčících.
    """
    from app.crm.models import CrmAktivita

    hranice = date.today() - timedelta(days=dni)
    posledni = (
        db.query(
            CrmAktivita.zaznam_id.label("pripad_id"),
            func.max(func.date(CrmAktivita.vytvoreno_at)).label("kdy"),
        )
        .filter(CrmAktivita.entita == "op")
        .group_by(CrmAktivita.zaznam_id)
        .subquery()
    )
    radky = (
        _pripady(db, user)
        .outerjoin(CrmStav, (CrmStav.klic == ObchodniPripad.stav) & (CrmStav.entita == "op"))
        .outerjoin(posledni, posledni.c.pripad_id == ObchodniPripad.id)
        .filter(CrmStav.druh == "otevreny")
        .filter((posledni.c.kdy.is_(None)) | (posledni.c.kdy <= hranice))
        .with_entities(
            ObchodniPripad.id,
            ObchodniPripad.cislo,
            ObchodniPripad.nazev,
            ObchodniPripad.hodnota_kc,
            CrmStav.nazev,
            posledni.c.kdy,
        )
        .all()
    )
    dnes = date.today()
    out = [
        {
            "id": i,
            "cislo": cislo,
            "nazev": nazev or "",
            "hodnota_kc": float(hodnota or 0),
            "stav": stav or "",
            "posledni_aktivita": kdy.isoformat() if kdy else None,
            "dni": (dnes - kdy).days if kdy else None,
        }
        for i, cislo, nazev, hodnota, stav, kdy in radky
    ]
    # Bez aktivity (dni=None) nahoru — u nich je ticho nejdelší.
    return sorted(out, key=lambda x: (x["dni"] is not None, -(x["dni"] or 0)))


def nabidky_bez_reakce(db: Session, user: User, dni: int = TICHO_NABIDKA_DNI) -> list[dict]:
    """Nabídky odeslané zákazníkovi, na které `dni` nikdo neodpověděl.

    Bere se OBCHODNÍ stav nabídky (odeslána), ne stav výpočtu — nabídka může být
    dávno odeslaná a přitom mít rozpracovaný výpočet, a naopak.
    """
    from app.nabidkovac.models import Nabidka

    hranice = date.today() - timedelta(days=dni)
    q = (
        db.query(Nabidka, ObchodniPripad)
        .outerjoin(ObchodniPripad, Nabidka.obchodni_pripad_id == ObchodniPripad.id)
        .filter(Nabidka.stav_obchodni == "odeslana")
        .filter(func.date(Nabidka.vytvoreno_at) <= hranice)
    )
    # Viditelnost: nabídka bez případu nemá vlastníka, takže ji vidí jen crm_vse.
    from app.crm.pristup import muze_vse

    dnes = date.today()
    out = []
    for n, p in q.all():
        if p is None:
            if not muze_vse(user):
                continue
        elif not (
            muze_vse(user)
            or p.vlastnik_user_id == user.id
            or user.id in list(p.spoluvlastnici or [])
        ):
            continue
        kdy = n.vytvoreno_at.date() if n.vytvoreno_at else None
        out.append(
            {
                "id": n.id,
                "cislo": n.cislo or f"#{n.id}",
                "zakaznik": n.zakaznik_nazev or (p.nazev if p else ""),
                "pripad_cislo": p.cislo if p else "",
                "dni": (dnes - kdy).days if kdy else None,
            }
        )
    return sorted(out, key=lambda x: -(x["dni"] or 0))
