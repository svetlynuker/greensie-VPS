"""Timeline zákazníka: celý děj na jedné chronologické ose (CRM-18).

Dnes je historie rozsypaná do záložek — aktivity zvlášť, případy zvlášť,
nabídky zvlášť, změny stavů ještě jinde. Kdo chce vědět „co se u toho klienta
za poslední rok dělo", musí si to skládat v hlavě.

---- Co se do osy slévá a proč právě to -----------------------------------

Aktivity (co jsme dělali), vznik případů, nabídek, objednávek a projektů (co
z toho bylo) a změny stavů (jak se to hýbalo). Dohromady je to odpověď na
otázku „jak jsme se sem dostali".

Změny stavů se berou z `crm_stav_historie` — právě kvůli tomuhle ta tabulka
existuje.

---- Jedno rozhodnutí, které stojí za vysvětlení -------------------------

Osa se skládá v Pythonu ze pěti dotazů, ne jedním SQL UNION. Každá entita má
jiné sloupce a UNION by je musel narovnat na společný tvar — což znamená psát
typování ručně a při každém novém poli to opravovat. Pět malých dotazů nad
jedním zákazníkem je levné a čitelné; kdyby se to někdy ukázalo jako pomalé,
přijde na řadu UNION, ne dřív.
"""

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import (
    CrmAktivita,
    CrmProjekt,
    CrmStav,
    CrmStavHistorie,
    ObchodniPripad,
    Objednavka,
    Zakaznik,
)

# Kolik událostí nejvýš. Osa je pro čtení, ne archiv — kdo chce všechno, jde
# do příslušné sekce a filtruje.
LIMIT = 120


def _iso(x):
    return x.isoformat() if x is not None else None


def pro_zakaznika(db: Session, user: User, zakaznik: Zakaznik) -> list[dict]:
    """Události u zákazníka, nejnovější první.

    Práva už ověřil volající (přístup k zákazníkovi). Případy patřící jinému OZ
    se sem nedostanou, protože se čtou jen ty pod tímhle zákazníkem — a na toho
    uživatel nárok má.
    """
    udalosti: list[dict] = []
    pripady = (
        db.query(ObchodniPripad)
        .filter(ObchodniPripad.zakaznik_id == zakaznik.id)
        .all()
    )
    pripad_ids = [p.id for p in pripady]
    cisla = {p.id: p.cislo for p in pripady}

    # --- vznik případů ---
    for p in pripady:
        udalosti.append(
            {
                "kdy": _iso(p.vytvoreno_at),
                "druh": "pripad",
                "titulek": f"Vznikl případ {p.cislo}",
                "popis": p.nazev or "",
                "cesta": f"/pripady/detail/{p.id}",
            }
        )

    # --- aktivity u zákazníka i u jeho případů ---
    aktivity = (
        db.query(CrmAktivita)
        .filter(
            (
                (CrmAktivita.entita == "zakaznik")
                & (CrmAktivita.zaznam_id == zakaznik.id)
            )
            | (
                (CrmAktivita.entita == "op")
                & (CrmAktivita.zaznam_id.in_(pripad_ids or [0]))
            )
        )
        .order_by(CrmAktivita.vytvoreno_at.desc())
        .limit(LIMIT)
        .all()
    )
    for a in aktivity:
        # Soukromá aktivita se do timeline zákazníka nedostane vůbec — nemá
        # k němu vazbu a její obsah nevidí ani vedení.
        if a.soukroma:
            continue
        stav = (
            " · realizováno"
            if a.stav == "realizovano"
            else " · nekonalo se"
            if a.stav == "nekonalo_se"
            else ""
        )
        udalosti.append(
            {
                "kdy": _iso(a.zacatek or a.vytvoreno_at),
                "druh": a.druh,
                "titulek": (a.nazev or a.text or "Aktivita")[:120] + stav,
                "popis": a.vysledek or (a.text if a.nazev else "") or "",
                "kdo": a.vlastnik.jmeno if a.vlastnik else "",
                "cesta": cisla.get(a.zaznam_id) and f"/pripady/detail/{a.zaznam_id}" or "",
            }
        )

    # --- nabídky, objednávky, projekty ---
    if pripad_ids:
        from app.nabidkovac.models import Nabidka

        for n in (
            db.query(Nabidka).filter(Nabidka.obchodni_pripad_id.in_(pripad_ids)).all()
        ):
            udalosti.append(
                {
                    "kdy": _iso(n.vytvoreno_at),
                    "druh": "nabidka",
                    "titulek": f"Nabídka {n.cislo or f'#{n.id}'}",
                    "popis": cisla.get(n.obchodni_pripad_id, ""),
                    "cesta": f"/nabidkovac/nabidka/{n.id}",
                }
            )
        for o in (
            db.query(Objednavka)
            .filter(Objednavka.obchodni_pripad_id.in_(pripad_ids))
            .all()
        ):
            udalosti.append(
                {
                    "kdy": _iso(o.vytvoreno_at),
                    "druh": "objednavka",
                    "titulek": f"Objednávka {o.cislo}",
                    "popis": o.nazev or "",
                    "cesta": "/objednavky",
                }
            )
        for pr in (
            db.query(CrmProjekt)
            .filter(CrmProjekt.obchodni_pripad_id.in_(pripad_ids))
            .all()
        ):
            udalosti.append(
                {
                    "kdy": _iso(pr.vytvoreno_at),
                    "druh": "projekt",
                    "titulek": f"Projekt {pr.cislo}",
                    "popis": pr.nazev or "",
                    "cesta": f"/projekty/detail/{pr.id}",
                }
            )

        # --- změny stavů (kvůli tomuhle ta historie existuje) ---
        nazvy = {
            s.klic: s.nazev
            for s in db.query(CrmStav).filter(CrmStav.entita == "op").all()
        }
        for h in (
            db.query(CrmStavHistorie)
            .filter(
                CrmStavHistorie.entita == "op",
                CrmStavHistorie.zaznam_id.in_(pripad_ids),
            )
            .order_by(CrmStavHistorie.zmeneno_at.desc())
            .limit(LIMIT)
            .all()
        ):
            z = nazvy.get(h.ze_stavu or "", h.ze_stavu or "")
            do = nazvy.get(h.do_stavu, h.do_stavu)
            udalosti.append(
                {
                    "kdy": _iso(h.zmeneno_at),
                    "druh": "stav",
                    "titulek": f"{cisla.get(h.zaznam_id, 'Případ')}: {do}",
                    "popis": f"z {z}" if z else "založeno",
                    "kdo": h.zmenil.jmeno if getattr(h, "zmenil", None) else "",
                    "cesta": f"/pripady/detail/{h.zaznam_id}",
                }
            )

    # --- e-maily napojené na firmu („rejnetované", CRM-33) ---
    # Tohle je celý smysl párování pošty: komunikace se zákazníkem má být
    # v ději, ne schovaná v cizí schránce. Do osy jde jen hlavička a náhled —
    # obsah zůstává majiteli schránky.
    udalosti.extend(_emaily_zakaznika(db, zakaznik.id, pripad_ids, cisla))

    # Nejnovější první. Události bez datumu (nemělo by nastat) na konec, aby
    # nerozhodily řazení nahoře.
    udalosti.sort(key=lambda u: u["kdy"] or "", reverse=True)
    return udalosti[:LIMIT]


def _emaily_zakaznika(db: Session, zakaznik_id: int, pripad_ids: list[int], cisla: dict) -> list[dict]:
    """E-maily napojené na firmu nebo její případy, jako události do osy.

    Selhání se polyká schválně: e-mailový klient je novinka a rozbitá pošta
    nesmí shodit celou historii zákazníka, která fungovala dřív než on.
    """
    try:
        from app.crm.models import CrmEmailVazba, CrmEmailZprava

        radky = (
            db.query(CrmEmailVazba, CrmEmailZprava)
            .join(CrmEmailZprava, CrmEmailVazba.zprava_id == CrmEmailZprava.id)
            .filter(
                CrmEmailVazba.skryta.is_(False),
                (CrmEmailVazba.zakaznik_id == zakaznik_id)
                | (CrmEmailVazba.pripad_id.in_(pripad_ids or [0])),
            )
            .order_by(CrmEmailZprava.datum_at.desc())
            .limit(LIMIT)
            .all()
        )
    except Exception:  # noqa: BLE001 - viz docstring
        return []

    udalosti = []
    videne = set()
    for vazba, z in radky:
        # Jedna zpráva může mít víc vazeb (osoba i firma) – do osy patří jednou.
        if z.id in videne:
            continue
        videne.add(z.id)
        smer = "Odesláno" if z.smer == "odchozi" else "Přijato"
        protistrana = (
            (z.komu or [{}])[0].get("adresa", "") if z.smer == "odchozi" else z.od_adresa
        )
        udalosti.append(
            {
                "kdy": _iso(z.datum_at),
                "druh": "email",
                "titulek": f"{smer}: {z.predmet or '(bez předmětu)'}"[:120],
                "popis": f"{protistrana}{' · ' + z.vypis if z.vypis else ''}"[:200],
                "cesta": (
                    f"/pripady/detail/{vazba.pripad_id}"
                    if vazba.pripad_id and vazba.pripad_id in cisla
                    else ""
                ),
            }
        )
    return udalosti
