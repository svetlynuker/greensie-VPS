"""Hromadné akce nad vybranými záznamy (CRM-19).

Zadání Dana: změnit vlastníka, změnit stav, přidat aktivitu všem — a k tomu
**naplánovat aktivity za sebe**: označím 10 klientů, dám telefonát od 8:00
s trváním 15 minut a appka je naskládá jednu za druhou.

---- Co je na hromadných akcích nebezpečné a jak se to řeší ----------------

1. **Práva se kontrolují u KAŽDÉHO záznamu zvlášť.** Seznam ID přichází
   z prohlížeče, takže se do něj dá dopsat cokoli. Kdo na záznam nemá nárok,
   ten se přeskočí a vrátí se v `preskoceno` — ne aby celá dávka spadla kvůli
   jednomu cizímu ID.
2. **Vynucený důvod prohry platí i tady.** Bez něj by hromadná změna stavu byla
   zadní vrátka, kterými by se do dat dostaly prohry bez důvodu — a rozpad
   důvodů proher v Přehledu obchodu by přestal mít smysl.
3. **Řetězení aktivit nepřeteče do noci.** Když se řada nevejde do pracovního
   dne, pokračuje se dalším dnem, ne ve 23:00. Kdo chce plánovat na večer, zadá
   pozdější start.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import automatizace as automatizace_modul, kalendar, stavy as stavy_modul
from app.crm.models import CrmAktivita, CrmStavHistorie, ObchodniPripad, Zakaznik
from app.crm.pristup import smi_menit, vidi_zaznam

# Do kolika hodin se řetěz aktivit plánuje. Po překročení pokračuje další den
# od stejné hodiny, jako začal první.
KONEC_PRACOVNI_DOBY = 18


def _zaznamy(db: Session, entita: str, ids: list[int], user: User):
    """Záznamy, na které má uživatel nárok. Ostatní vrací jako přeskočené."""
    model = {"zakaznik": Zakaznik, "op": ObchodniPripad}.get(entita)
    if model is None:
        raise ValueError(f"Hromadné akce nejsou pro '{entita}' k dispozici.")
    nalezene = db.query(model).filter(model.id.in_(ids or [])).all()
    ok = [z for z in nalezene if vidi_zaznam(z, user) and smi_menit(z, user)]
    preskoceno = len(ids or []) - len(ok)
    return ok, preskoceno


def zmen_vlastnika(db: Session, entita: str, ids: list[int], user: User, novy_id: int) -> dict:
    """Přehodí záznamy na jiného člověka (odchod, dovolená)."""
    if not db.query(User.id).filter(User.id == novy_id).first():
        raise ValueError("Zvolený uživatel neexistuje.")
    zaznamy, preskoceno = _zaznamy(db, entita, ids, user)
    for z in zaznamy:
        z.vlastnik_user_id = novy_id
    db.commit()
    return {"zmeneno": len(zaznamy), "preskoceno": preskoceno}


def zmen_stav(
    db: Session, ids: list[int], user: User, stav: str, duvod_prohry: str = ""
) -> dict:
    """Posune víc případů do stejné fáze. Historie se píše u každého zvlášť.

    U prohry je důvod povinný stejně jako při jednotlivé změně — jinak by tohle
    byla zadní vrátka pro prohry bez důvodu.
    """
    cil = stavy_modul.najdi(db, "op", stav)
    if cil is None:
        raise ValueError(f"Stav '{stav}' u obchodního případu neexistuje.")
    if cil.druh == "prohra" and not (duvod_prohry or "").strip():
        raise ValueError("U prohry je potřeba důvod — bez něj nemá statistika smysl.")

    zaznamy, preskoceno = _zaznamy(db, "op", ids, user)
    automatika: list[str] = []
    for p in zaznamy:
        if p.stav == stav:
            continue
        db.add(
            CrmStavHistorie(
                entita="op",
                zaznam_id=p.id,
                ze_stavu=p.stav,
                do_stavu=stav,
                zmenil_user_id=user.id,
            )
        )
        p.stav = stav
        if cil.druh == "prohra":
            p.duvod_prohry = duvod_prohry.strip()
        if cil.druh in ("vyhra", "prohra"):
            p.uzavreno_at = datetime.now()
        else:
            p.uzavreno_at = None
        # CRM-31: pravidla platí i tady. Kdyby hromadná změna automatiku
        # obcházela, byla by to tichá zadní vrátka („u jednoho případu se
        # objednávka založí, u deseti ne") — přesně ten druh nekonzistence,
        # kvůli které lidé přestanou appce věřit. Co se stalo, se vrací
        # volajícímu, aby to UI mohlo vypsat.
        automatika += automatizace_modul.po_zmene_stavu(db, "op", p, stav, user)
    db.commit()
    return {
        "zmeneno": len(zaznamy),
        "preskoceno": preskoceno,
        "automatika": automatika,
    }


def naplanuj_aktivity(
    db: Session,
    entita: str,
    ids: list[int],
    user: User,
    druh: str,
    nazev: str,
    den: date,
    cas: str | None = None,
    delka_min: int | None = None,
    retez: bool = False,
    vlastnik_user_id: int | None = None,
) -> dict:
    """Založí aktivitu každému vybranému záznamu.

    `retez=True` je Danovo zadání: aktivity se naskládají jedna za druhou od
    `cas` po `delka_min`. Bez řetězení dostanou všechny stejný čas — což je
    správné u úkolu („do konce dne"), ale ne u telefonátů.

    Pořadí drží pořadí ID ze seznamu, aby odpovídalo tomu, co člověk vidí
    v tabulce; nesetřídí se to podle id ani jmen.
    """
    zaznamy, preskoceno = _zaznamy(db, entita, ids, user)
    poradi = {z: i for i, z in enumerate(ids or [])}
    zaznamy.sort(key=lambda z: poradi.get(z.id, 0))

    delka = delka_min or kalendar.vychozi_delka(druh)
    vlastnik = vlastnik_user_id or user.id
    zacatek_min = None
    if cas:
        try:
            h, m = (int(x) for x in cas.split(":")[:2])
            zacatek_min = h * 60 + m
        except (TypeError, ValueError):
            raise ValueError("Čas musí být ve formátu HH:MM.")

    plan = []
    aktualni_den = den
    kurzor = zacatek_min
    for z in zaznamy:
        a = CrmAktivita(
            entita=entita,
            zaznam_id=z.id,
            druh=druh,
            nazev=nazev,
            termin=aktualni_den,
            delka_min=delka if kurzor is not None else None,
            vlastnik_user_id=vlastnik,
            vytvoril_user_id=user.id,
        )
        if kurzor is not None:
            a.zacatek = datetime.combine(
                aktualni_den, time(hour=kurzor // 60, minute=kurzor % 60)
            )
        kalendar.srovnej_termin(a)
        db.add(a)
        plan.append(
            {
                "zaznam_id": z.id,
                "popis": getattr(z, "nazev", "") or f"#{z.id}",
                "termin": aktualni_den.isoformat(),
                "cas": f"{kurzor // 60}:{kurzor % 60:02d}" if kurzor is not None else None,
            }
        )
        if retez and kurzor is not None:
            kurzor += delka
            # Řada nepřeteče do noci — pokračuje dalším dnem od stejné hodiny.
            if kurzor >= KONEC_PRACOVNI_DOBY * 60:
                aktualni_den = aktualni_den + timedelta(days=1)
                kurzor = zacatek_min
    db.commit()
    return {"zalozeno": len(plan), "preskoceno": preskoceno, "plan": plan}
