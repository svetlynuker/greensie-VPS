"""Automatizace CRM: „když záznam přejde do stavu X, udělej Y" (CRM-31).

Tři kroky, které dneska OZ dělá pokaždé znovu a pokaždé stejně:

  * případ vyhrán      → založ objednávku (cenu vezmi z přijaté nabídky),
  * objednávka podepsaná → založ projekt a rozbal do něj šablonu kroků,
  * nabídka odeslána   → za 7 dní úkol „zavolat, jak se rozhodli".

---- Pravidlo, na kterém tenhle modul stojí -----------------------------------

**Automatika musí být vidět a musí se dát vypnout.** Appka, která sama zakládá
záznamy a neřekne to, je horší než ruční práce: člověk nepozná, jestli
objednávku založil kolega nebo stroj, a přestane appce věřit. Proto každé
provedení zapisuje DVĚ věci:

  1. řádek do `crm_pravidlo_behy` (přehled v Nastavení → Automatizace),
  2. **poznámku do aktivit spouštěcího záznamu** – tam se na to člověk kouká,
     ne do nastavení.

A každé pravidlo má vypínač (`aktivni`).

---- Proč se pravidlo spustí na jeden záznam nejvýš jednou --------------------

Kdyby se hlídalo jen „už objednávka existuje?", u úkolů by to nefungovalo vůbec
(úkol může existovat z jiného důvodu) a případ vrácený z „Vyhráno" do
„Vyjednávání" a zpátky by vyrobil druhou objednávku. Proto se hlídá běh
pravidla: jedno pravidlo × jeden záznam = jeden běh (unikátní index na
`crm_pravidlo_behy`). Když se má akce provést znovu, člověk ji udělá ručně —
tlačítka nikam nezmizela.

---- Selhání akce nesmí shodit změnu stavu -----------------------------------

Stejné pravidlo jako u notifikací: člověk posunul případ v kanbanu a to se
musí uložit, i kdyby automatika spadla. Chyba jde do logu běhů a do
aplikačního logu, ne do odpovědi. Proto tady taky **není `db.commit()`** —
běží to ve transakci volajícího endpointu, který commit udělá sám.
"""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import ciselne_rady
from app.crm import projekty_kroky as kroky_modul
from app.crm import stavy as stavy_modul
from app.crm.models import (
    CrmAktivita,
    CrmPravidlo,
    CrmPravidloBeh,
    CrmProjekt,
    CrmStavHistorie,
    Objednavka,
    ObjednavkaPolozka,
    ObchodniPripad,
    ProjektSablona,
)

log = logging.getLogger(__name__)

# Entity, na kterých může spouštěč stát. Shodné s klíči `crm_stavy` – automatika
# reaguje na přesun v kanbanu, takže jinou entitu než ty se stavy nemá kde vzít.
SPOUSTECI_ENTITY = {
    "op": "Obchodní případ",
    "nab": "Nabídka",
    "obj": "Objednávka",
    "pro": "Projekt",
}

# Katalog akcí. `entity` říká, od které spouštěcí entity akce umí pracovat —
# „založ projekt" potřebuje objednávku nebo případ, z nabídky by neměl co vzít.
#
# Přidání akce = záznam sem + funkce `_akce_<klic>`. UI se skládá z tohohle
# katalogu, takže se nová akce objeví v nastavení sama.
AKCE = [
    {
        "klic": "objednavka",
        "nazev": "Založ objednávku",
        "popis": (
            "Vytvoří objednávku pod případem. Cenu i rozpis položek převezme "
            "z přijaté nabídky případu, vlastníky z případu."
        ),
        "entity": ["op"],
        "parametry": [],
    },
    {
        "klic": "projekt",
        "nazev": "Založ projekt ze šablony",
        "popis": (
            "Vytvoří projekt z objednávky (nebo z případu) a rozbalí do něj "
            "šablonu kroků s termíny. Bez zvolené šablony se vybere podle "
            "kategorie případu."
        ),
        "entity": ["obj", "op"],
        "parametry": ["sablona_id"],
    },
    {
        "klic": "ukol",
        "nazev": "Založ úkol s termínem",
        "popis": (
            "Přidá k záznamu úkol s termínem za zadaný počet dní. Řešitelem je "
            "vlastník záznamu, pokud není zvolený někdo konkrétní."
        ),
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["za_dni", "nazev", "text", "komu_user_id"],
    },
]

MAPA_AKCI = {a["klic"]: a for a in AKCE}


def _vlastnictvi_pripadu(pripad: ObchodniPripad) -> tuple[int | None, list]:
    return pripad.vlastnik_user_id, list(pripad.spoluvlastnici or [])


def _pripad_zaznamu(db: Session, entita: str, zaznam) -> ObchodniPripad | None:
    """Obchodní případ, pod který spouštěcí záznam patří.

    Všechny akce ho potřebují: objednávka i projekt bez případu vzniknout
    nesmí (viz `routes_realizace`), a u úkolu se z něj berou vlastníci.
    """
    if entita == "op":
        return zaznam
    pripad_id = getattr(zaznam, "obchodni_pripad_id", None)
    return db.get(ObchodniPripad, pripad_id) if pripad_id else None


# ---- akce -------------------------------------------------------------------
def _akce_objednavka(db: Session, entita: str, zaznam, pravidlo: CrmPravidlo, user: User) -> str:
    """Případ vyhrán → objednávka. Vrací popis pro log, nebo prázdno = přeskočeno."""
    from app.nabidkovac import polozky as polozky_modul
    from app.nabidkovac.models import Nabidka

    pripad = _pripad_zaznamu(db, entita, zaznam)
    if pripad is None:
        return ""

    # Druhá objednávka téhož případu je legitimní věc (etapy), ale automatika ji
    # zakládat nemá – dvě objednávky na jednu zakázku vzniknou vždycky z lidského
    # rozhodnutí, ne z přesunu v kanbanu.
    if db.query(Objednavka.id).filter(Objednavka.obchodni_pripad_id == pripad.id).first():
        return ""

    # Nabídka, ze které se čerpá: přednost má PŘIJATÁ (druh „vyhra"), protože ta
    # je ta, na které se zákazník dohodl. Bez přijaté se vezme poslední s cenou.
    nabidky = (
        db.query(Nabidka)
        .filter(Nabidka.obchodni_pripad_id == pripad.id)
        .order_by(Nabidka.id.desc())
        .all()
    )
    prijate = [n for n in nabidky if stavy_modul.je_druhu(db, "nab", n.stav_obchodni or "", "vyhra")]
    nabidka = (prijate or nabidky or [None])[0]

    vlastnik, spolu = _vlastnictvi_pripadu(pripad)
    stav = stavy_modul.vychozi_klic(db, "obj")
    o = Objednavka(
        cislo=ciselne_rady.dalsi_cislo(db, "obj"),
        obchodni_pripad_id=pripad.id,
        nabidka_id=nabidka.id if nabidka is not None else None,
        nazev=pripad.nazev or "",
        popis=f"Založeno automaticky pravidlem „{pravidlo.nazev}“.",
        stav=stav,
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        vytvoril_user_id=user.id if user is not None else None,
    )
    db.add(o)
    db.flush()

    # Rozpis se KOPÍRUJE, ne váže – stejně jako v `zaloz_objednavku`: objednávka
    # je obchodní dokument a nesmí se změnit, když někdo přepočítá nabídku.
    if nabidka is not None and nabidka.polozky:
        for p in nabidka.polozky:
            db.add(polozky_modul.kopiruj(p, ObjednavkaPolozka, objednavka_id=o.id))
        db.flush()
        db.refresh(o)
        o.cena_kc = polozky_modul.souhrn(list(o.polozky))["bez_dph"]
        o.cena_rucni = False
    elif nabidka is not None:
        # Bez rozpisu se cena bere z výpočtu nabídky – TOU SAMOU funkcí, jakou
        # používá ruční zakládání objednávky. Druhá implementace by znamenala,
        # že automaticky a ručně založená objednávka mají jinou cenu.
        from app.crm.routes_realizace import _cena_z_nabidky

        o.cena_kc = _cena_z_nabidky(db, nabidka.id)
        o.cena_rucni = o.cena_kc is not None

    db.add(
        CrmStavHistorie(
            entita="obj",
            zaznam_id=o.id,
            ze_stavu=None,
            do_stavu=stav,
            zmenil_user_id=user.id if user is not None else None,
        )
    )
    db.flush()
    return f"Založena objednávka {o.cislo}"


def _vyber_sablonu(db: Session, pripad: ObchodniPripad, sablona_id) -> ProjektSablona | None:
    """Šablona kroků: buď zvolená v pravidle, nebo podle kategorie případu.

    Volba „podle kategorie" existuje proto, že jedno pravidlo pak stačí na celou
    firmu: FVE případ dostane FVE šablonu, peak shaving tu svoji. Šablony už
    kategorie nesou (`ProjektSablona.kategorie`), takže se nic nedoplňuje.
    """
    if sablona_id:
        return db.get(ProjektSablona, int(sablona_id))
    kategorie = list(pripad.kategorie or [])
    if not kategorie:
        return None
    for s in db.query(ProjektSablona).order_by(ProjektSablona.id).all():
        if set(s.kategorie or []) & set(kategorie):
            return s
    return None


def _akce_projekt(db: Session, entita: str, zaznam, pravidlo: CrmPravidlo, user: User) -> str:
    """Objednávka podepsaná → projekt se rozbalenou šablonou kroků."""
    pripad = _pripad_zaznamu(db, entita, zaznam)
    if pripad is None:
        return ""

    objednavka = zaznam if entita == "obj" else None
    # Druhý projekt téže objednávky (nebo případu, když spouštěčem je případ)
    # automatika nezakládá – stejná úvaha jako u objednávky.
    q = db.query(CrmProjekt.id)
    if objednavka is not None:
        q = q.filter(CrmProjekt.objednavka_id == objednavka.id)
    else:
        q = q.filter(CrmProjekt.obchodni_pripad_id == pripad.id)
    if q.first():
        return ""

    pocet = (
        db.query(CrmProjekt.id).filter(CrmProjekt.obchodni_pripad_id == pripad.id).count()
    )
    vlastnik, spolu = (
        (objednavka.vlastnik_user_id, list(objednavka.spoluvlastnici or []))
        if objednavka is not None
        else _vlastnictvi_pripadu(pripad)
    )
    stav = stavy_modul.vychozi_klic(db, "pro")
    p = CrmProjekt(
        cislo=ciselne_rady.cislo_projektu(db, pripad, pocet),
        obchodni_pripad_id=pripad.id,
        objednavka_id=objednavka.id if objednavka is not None else None,
        nazev=(objednavka.nazev if objednavka is not None else "") or pripad.nazev or "",
        popis=f"Založeno automaticky pravidlem „{pravidlo.nazev}“.",
        stav=stav,
        # Zahájení je den, kdy se objednávka podepsala – od něj se počítají
        # termíny kroků. Datum podpisu má přednost, protože podpis mohl být dřív,
        # než ho někdo do appky zapsal.
        zahajeni=(
            getattr(objednavka, "datum_podpisu", None) if objednavka is not None else None
        )
        or date.today(),
        vlastnik_user_id=vlastnik,
        spoluvlastnici=spolu,
        vytvoril_user_id=user.id if user is not None else None,
    )
    db.add(p)
    db.flush()
    db.add(
        CrmStavHistorie(
            entita="pro",
            zaznam_id=p.id,
            ze_stavu=None,
            do_stavu=stav,
            zmenil_user_id=user.id if user is not None else None,
        )
    )

    sablona = _vyber_sablonu(db, pripad, (pravidlo.nastaveni or {}).get("sablona_id"))
    if sablona is not None:
        kroky_modul.rozbal_sablonu(db, p, sablona)
        db.refresh(p)
        kroky_modul.prepocitej_terminy(db, p)
        return f"Založen projekt {p.cislo} ze šablony „{sablona.nazev}“"
    db.flush()
    return f"Založen projekt {p.cislo} (bez šablony — žádná neodpovídá kategorii)"


def _akce_ukol(db: Session, entita: str, zaznam, pravidlo: CrmPravidlo, user: User) -> str:
    """„Za N dní zavolat" – úkol navěšený na spouštěcí záznam."""
    nastaveni = pravidlo.nastaveni or {}
    try:
        za_dni = max(0, int(nastaveni.get("za_dni") or 0))
    except (TypeError, ValueError):
        za_dni = 0
    nazev = str(nastaveni.get("nazev") or "").strip() or "Ozvat se zákazníkovi"
    text = str(nastaveni.get("text") or "").strip() or nazev

    komu = nastaveni.get("komu_user_id")
    resitel = int(komu) if komu else (getattr(zaznam, "vlastnik_user_id", None) or None)
    if resitel is None:
        pripad = _pripad_zaznamu(db, entita, zaznam)
        resitel = (pripad.vlastnik_user_id if pripad is not None else None) or (
            user.id if user is not None else None
        )
    # Úkol bez řešitele by nikomu nevyskočil v „moje úkoly" a byl by k ničemu.
    if resitel is None or not db.query(User.id).filter(User.id == resitel).first():
        return ""

    termin = date.today() + timedelta(days=za_dni)
    a = CrmAktivita(
        entita=entita,
        zaznam_id=zaznam.id,
        druh="ukol",
        nazev=nazev,
        text=text,
        termin=termin,
        vlastnik_user_id=resitel,
        vytvoril_user_id=user.id if user is not None else None,
    )
    db.add(a)
    db.flush()
    return f"Založen úkol „{nazev}“ s termínem {termin.strftime('%d.%m.%Y')}"


VYKONAVACE = {
    "objednavka": _akce_objednavka,
    "projekt": _akce_projekt,
    "ukol": _akce_ukol,
}


# ---- spouštění --------------------------------------------------------------
def _popis_zaznamu(zaznam) -> str:
    cislo = getattr(zaznam, "cislo", "") or ""
    nazev = getattr(zaznam, "nazev", "") or ""
    return f"{cislo} · {nazev}".strip(" ·") or f"#{getattr(zaznam, 'id', '?')}"


def _zaloz_poznamku(db: Session, entita: str, zaznam_id: int, popis: str, user: User) -> None:
    """Zapíše do aktivit záznamu, co automatika udělala.

    Tohle je to místo, kde si to člověk přečte — v nastavení se nikdo dívat
    nebude. Poznámka je bez termínu, takže se neplete do úkolů.
    """
    db.add(
        CrmAktivita(
            entita=entita,
            zaznam_id=zaznam_id,
            druh="poznamka",
            nazev="Automatizace",
            text=popis,
            vytvoril_user_id=user.id if user is not None else None,
        )
    )
    db.flush()


def _zapis_beh(
    db: Session,
    pravidlo: CrmPravidlo,
    entita: str,
    zaznam_id: int,
    vysledek: str,
    popis: str,
    user: User,
) -> None:
    """Řádek do logu běhů. Selhání zápisu logu nesmí shodit akci, která uspěla."""
    try:
        db.add(
            CrmPravidloBeh(
                pravidlo_id=pravidlo.id,
                entita=entita,
                zaznam_id=zaznam_id,
                vysledek=vysledek,
                popis=popis,
                spustil_user_id=user.id if user is not None else None,
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001
        log.warning("Běh pravidla %s se nepodařilo zapsat", pravidlo.id, exc_info=True)


def pravidla_pro(db: Session, entita: str, stav_klic: str) -> list[CrmPravidlo]:
    return (
        db.query(CrmPravidlo)
        .filter(
            CrmPravidlo.aktivni.is_(True),
            CrmPravidlo.spoust_entita == entita,
            CrmPravidlo.spoust_stav == stav_klic,
        )
        .order_by(CrmPravidlo.poradi, CrmPravidlo.id)
        .all()
    )


def po_zmene_stavu(db: Session, entita: str, zaznam, novy_stav: str, user: User) -> list[str]:
    """Spustí pravidla navěšená na přechod do `novy_stav`. Nikdy nevyhodí výjimku.

    Volá se PŘED `db.commit()` volajícího endpointu, aby všechno (nová
    objednávka, poznámka, log běhu) vzniklo v jedné transakci se změnou stavu.
    Když spadne akce, případ se uloží stejně a v logu bude řádek „chyba".

    Vrací popisy provedených akcí — volající je může vrátit do UI, aby člověk
    hned viděl, co appka udělala. Prázdný seznam = nic se nedělo.
    """
    hotove: list[str] = []
    try:
        pravidla = pravidla_pro(db, entita, novy_stav)
    except Exception:  # noqa: BLE001 - automatika je doplněk, ne součást akce
        log.warning("Nepodařilo se načíst pravidla automatizace", exc_info=True)
        return hotove
    if not pravidla:
        return hotove

    # FLUSH PŘED SAVEPOINTEM. Volající má změnu stavu zatím jen v session
    # (`p.stav = ...` bez flushe). Kdyby se poprvé flushla až UVNITŘ savepointu,
    # `sp.rollback()` po chybě akce by ji vrátil zpátky: člověk přesune případ
    # v kanbanu, appka odpoví OK a stav zůstane starý.
    #
    # Dnes to obvykle zachrání i autoflush při dotazu na pravidla výš, takže je
    # tenhle řádek pojistka — ale pojistka za jeden dotaz, která dělá chování
    # nezávislým na tom, jestli je autoflush zapnutý a jak SQLAlchemy zachází
    # s neflushnutými změnami po rollbacku savepointu. Nespoléhat se na to
    # hlídá `test_zmena_stavu_prezije_i_bez_autoflushe`.
    try:
        db.flush()
    except Exception:  # noqa: BLE001 - když neprojde flush, neprojde ani commit volajícího
        log.warning("Flush před automatizací selhal", exc_info=True)
        return hotove

    for pravidlo in pravidla:
        # Jedno pravidlo × jeden záznam = jeden běh. Kontrola tady i unikátní
        # index v DB: index chrání před souběhem dvou requestů, dotaz před tím,
        # aby se kvůli němu nemusela rušit celá transakce.
        uz_bezelo = (
            db.query(CrmPravidloBeh.id)
            .filter(
                CrmPravidloBeh.pravidlo_id == pravidlo.id,
                CrmPravidloBeh.entita == entita,
                CrmPravidloBeh.zaznam_id == zaznam.id,
            )
            .first()
        )
        if uz_bezelo is not None:
            continue
        vykonavac = VYKONAVACE.get(pravidlo.akce)
        if vykonavac is None:
            continue

        # SAVEPOINT, ne obyčejný try/except. Když akce spadne v půlce, session
        # je rozbitá a commit endpointu by selhal — tedy člověk by nepřesunul
        # případ. `db.rollback()` tady nejde: zahodil by i tu změnu stavu.
        # Savepoint zahodí jen to, co nastihla udělat akce.
        sp = db.begin_nested()
        try:
            popis = vykonavac(db, entita, zaznam, pravidlo, user)
            sp.commit()
        except Exception:  # noqa: BLE001 - selhání akce nesmí shodit změnu stavu
            sp.rollback()
            log.warning(
                "Pravidlo %s (%s) selhalo u %s #%s",
                pravidlo.id,
                pravidlo.akce,
                entita,
                getattr(zaznam, "id", "?"),
                exc_info=True,
            )
            _zapis_beh(
                db,
                pravidlo,
                entita,
                zaznam.id,
                "chyba",
                "Akce selhala, podrobnosti jsou v logu aplikace.",
                user,
            )
            continue

        if not popis:
            # Akce se vědomě neprovedla (objednávka už existuje apod.). Zapisuje
            # se taky, jinak by v nastavení nebylo poznat, proč se „nic nestalo“.
            _zapis_beh(
                db,
                pravidlo,
                entita,
                zaznam.id,
                "preskoceno",
                "Nebylo co udělat (záznam už existuje nebo chybí podklad).",
                user,
            )
            continue

        _zapis_beh(db, pravidlo, entita, zaznam.id, "hotovo", popis, user)
        _zaloz_poznamku(
            db, entita, zaznam.id, f"{popis} — pravidlo „{pravidlo.nazev}“.", user
        )
        hotove.append(popis)
    return hotove


# ---- pro API ----------------------------------------------------------------
def _jmeno(u: User | None) -> str | None:
    return (u.jmeno or u.email) if u is not None else None


def beh_out(b: CrmPravidloBeh) -> dict:
    return {
        "id": b.id,
        "entita": b.entita,
        "zaznam_id": b.zaznam_id,
        "vysledek": b.vysledek,
        "popis": b.popis or "",
        "kdo": _jmeno(b.spustil),
        "kdy": b.kdy.isoformat() if b.kdy else None,
    }


def pravidlo_out(db: Session, p: CrmPravidlo, s_behy: bool = False) -> dict:
    out = {
        "id": p.id,
        "nazev": p.nazev,
        "aktivni": bool(p.aktivni),
        "poradi": p.poradi,
        "spoust_entita": p.spoust_entita,
        "spoust_stav": p.spoust_stav,
        "akce": p.akce,
        "nastaveni": dict(p.nastaveni or {}),
        # Kolikrát pravidlo zabralo – hlavní údaj, po kterém vedení pozná,
        # jestli automatika něco dělá, nebo jen leží v seznamu.
        "behu": len([b for b in (p.behy or []) if b.vysledek == "hotovo"]),
    }
    stav = stavy_modul.najdi(db, p.spoust_entita, p.spoust_stav)
    out["spoust_stav_nazev"] = stav.nazev if stav is not None else p.spoust_stav
    out["entita_nazev"] = SPOUSTECI_ENTITY.get(p.spoust_entita, p.spoust_entita)
    out["akce_nazev"] = (MAPA_AKCI.get(p.akce) or {}).get("nazev", p.akce)
    if s_behy:
        out["behy"] = [
            beh_out(b) for b in sorted(p.behy or [], key=lambda b: b.id, reverse=True)[:30]
        ]
    return out


def over_pravidlo(db: Session, entita: str, stav: str, akce: str, nastaveni: dict) -> dict:
    """Zkontroluje smysluplnost pravidla a vrátí očištěné `nastaveni`.

    Kontroluje se při ukládání, ne při běhu: pravidlo, které nemá jak fungovat,
    se nemá dát uložit. Za běhu už na to není koho se zeptat.
    """
    if entita not in SPOUSTECI_ENTITY:
        raise ValueError(f"Neznámá entita spouštěče: {entita}")
    if stavy_modul.najdi(db, entita, stav) is None:
        raise ValueError(f"Stav „{stav}“ u {SPOUSTECI_ENTITY[entita]} neexistuje.")
    definice = MAPA_AKCI.get(akce)
    if definice is None:
        raise ValueError(f"Neznámá akce: {akce}")
    if entita not in definice["entity"]:
        nazvy = ", ".join(SPOUSTECI_ENTITY[e] for e in definice["entity"])
        raise ValueError(f"Akce „{definice['nazev']}“ jde spustit jen od: {nazvy}.")

    vstup = nastaveni or {}
    ciste: dict = {}
    if akce == "projekt":
        sablona_id = vstup.get("sablona_id")
        if sablona_id:
            if db.get(ProjektSablona, int(sablona_id)) is None:
                raise ValueError("Zvolená šablona neexistuje.")
            ciste["sablona_id"] = int(sablona_id)
    if akce == "ukol":
        try:
            ciste["za_dni"] = max(0, min(365, int(vstup.get("za_dni") or 0)))
        except (TypeError, ValueError):
            raise ValueError("Počet dní musí být číslo.") from None
        ciste["nazev"] = str(vstup.get("nazev") or "").strip()[:200]
        ciste["text"] = str(vstup.get("text") or "").strip()[:2000]
        komu = vstup.get("komu_user_id")
        if komu:
            if not db.query(User.id).filter(User.id == int(komu)).first():
                raise ValueError("Zvolený řešitel neexistuje.")
            ciste["komu_user_id"] = int(komu)
        if not ciste["nazev"]:
            raise ValueError("U úkolu vyplň, jak se má jmenovat.")
    return ciste


# Výchozí pravidla. Naseedují se VYPNUTÁ (`aktivni=False`) schválně: automatika,
# která začne zakládat záznamy hned po nasazení, aniž o ní kdokoli ví, je přesně
# to, co lidem vezme důvěru v appku. Vedení si je v Nastavení projde a zapne.
VYCHOZI_PRAVIDLA = [
    {
        "nazev": "Případ vyhrán → objednávka",
        "spoust_entita": "op",
        "spoust_stav": "vyhrano",
        "akce": "objednavka",
        "nastaveni": {},
    },
    {
        "nazev": "Objednávka podepsaná → projekt ze šablony",
        "spoust_entita": "obj",
        "spoust_stav": "podepsana",
        "akce": "projekt",
        "nastaveni": {},
    },
    {
        "nazev": "Nabídka odeslána → za 7 dní zavolat",
        "spoust_entita": "nab",
        "spoust_stav": "odeslana",
        "akce": "ukol",
        "nastaveni": {
            "za_dni": 7,
            "nazev": "Zavolat zákazníkovi kvůli nabídce",
            "text": "Ozvat se a zjistit, jak se k nabídce staví.",
        },
    },
]


def seed_pravidla(db: Session) -> None:
    """Nachystá výchozí pravidla, pokud žádná nejsou (idempotentní, vypnutá).

    Jen do úplně prázdné tabulky – jakmile si je vedení upraví nebo smaže, seed
    do nich nesahá (stejně jako u šablon a stavů).
    """
    if db.query(CrmPravidlo.id).first() is not None:
        return
    for poradi, p in enumerate(VYCHOZI_PRAVIDLA):
        # Stav musí existovat: kdo si kanban přeskládal, výchozí klíč mít nemusí
        # a pravidlo na neexistující stav by nikdy nezabralo.
        if stavy_modul.najdi(db, p["spoust_entita"], p["spoust_stav"]) is None:
            continue
        db.add(
            CrmPravidlo(
                nazev=p["nazev"],
                aktivni=False,
                poradi=poradi,
                spoust_entita=p["spoust_entita"],
                spoust_stav=p["spoust_stav"],
                akce=p["akce"],
                nastaveni=p["nastaveni"],
            )
        )
    db.commit()
