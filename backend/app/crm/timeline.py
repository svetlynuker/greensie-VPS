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

    # Nejnovější první. Události bez datumu (nemělo by nastat) na konec, aby
    # nerozhodily řazení nahoře.
    udalosti.sort(key=lambda u: u["kdy"] or "", reverse=True)
    return udalosti[:LIMIT]
