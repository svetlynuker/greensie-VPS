"""Automatizace CRM: „když se stane tohle, udělej tohle a tohle“ (CRM-31).

Pravidlo je věta o třech částech — **KDYŽ** (spouštěč) / **POKUD** (podmínky) /
**PAK** (kroky). Tenhle modul je motor: pozná, že spouštěč nastal, ověří
podmínky a provede kroky. Katalog polí je v `automatizace_pole.py`, katalog akcí
v `automatizace_akce.py`, časové spouštěče hlídá `automatizace_scheduler.py`.

---- Pravidlo, na kterém tenhle modul stojí -----------------------------------

**Automatika musí být vidět a musí se dát vypnout.** Appka, která sama zakládá
záznamy a neřekne to, je horší než ruční práce: člověk nepozná, jestli
objednávku založil kolega nebo stroj, a přestane appce věřit. Proto každé
provedení zapisuje DVĚ věci:

  1. řádek do `crm_pravidlo_behy` (přehled v Nastavení → Automatizace),
  2. **poznámku do aktivit spouštěcího záznamu** – tam se na to člověk kouká,
     ne do nastavení.

A každé pravidlo má vypínač (`aktivni`).

---- Kolikrát smí pravidlo zabrat na jeden záznam ----------------------------

Podle volby `opakovat`:

  * `jednou` (výchozí) — nejvýš jednou za život záznamu. Kdyby se hlídalo jen
    „už objednávka existuje?“, u úkolů by to nefungovalo vůbec (úkol může
    existovat z jiného důvodu) a případ vrácený z „Vyhráno“ do „Vyjednávání“
    a zpátky by vyrobil druhou objednávku. Proto se hlídá běh pravidla:
    jedno pravidlo × jeden záznam = jeden běh (unikátní index).
  * `vzdy` — při každém spuštění. Správné u spouštěče „změnilo se pole“: pole
    se mění pořád a člověk čeká, že se pravidlo ozve pokaždé.

---- Selhání akce nesmí shodit změnu stavu -----------------------------------

Stejné pravidlo jako u notifikací: člověk posunul případ v kanbanu a to se
musí uložit, i kdyby automatika spadla. Chyba jde do logu běhů a do
aplikačního logu, ne do odpovědi. Proto tady taky **není `db.commit()`** —
běží to ve transakci volajícího endpointu, který commit udělá sám.

---- Ochrana proti smyčce ----------------------------------------------------

Od chvíle, kdy umí akce „přesuň do stavu“, může pravidlo spustit další pravidlo.
Dvojice „do realizace → do předání“ a „do předání → do realizace“ by se bez
pojistky zacyklila a shodila request, kterým člověk jen posunul kartu. Pojistky
jsou dvě, obě nutné:

  * `MAX_HLOUBKA` — kolik pravidel smí být v řetězu za sebou,
  * `navstivene` — jedno pravidlo se v JEDNOM řetězu nespustí dvakrát, i kdyby
    hloubka zbývala.
"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import automatizace_pole as pole_modul
from app.crm import stavy as stavy_modul
from app.crm.automatizace_akce import (
    AKCE,
    ENTITY_S_VLASTNIKEM,
    MAPA_AKCI,
    PRIJEMCI,
    SPOUSTECI_ENTITY,
    VYKONAVACE,
    Kontext,
    over_krok,
    popis_kroku,
    popis_zaznamu,
)
from app.crm.models import CrmAktivita, CrmPravidlo, CrmPravidloBeh

log = logging.getLogger(__name__)

# Kolik pravidel smí být v řetězu za sebou (pravidlo → změna stavu → pravidlo…).
# Tři stačí na každý smysluplný postup („vyhráno → objednávka → projekt“) a
# zacyklení utne dřív, než si toho databáze všimne.
MAX_HLOUBKA = 3

# Co může pravidlo spustit. `parametry` říká UI, co se u typu doptat.
SPOUSTECE = [
    {
        "klic": "stav",
        "nazev": "Záznam přejde do stavu",
        "popis": "Spustí se ve chvíli, kdy někdo přetáhne kartu v kanbanu nebo změní stav v detailu.",
        "parametry": ["spoust_stav"],
    },
    {
        "klic": "vznik",
        "nazev": "Záznam vznikne",
        "popis": "Hned po založení nového záznamu — ať ho založil člověk, import, nebo jiné pravidlo.",
        "parametry": [],
    },
    {
        "klic": "pole",
        "nazev": "Změní se hodnota pole",
        "popis": "Když se při uložení změní zvolené pole. Přepsání stejnou hodnotou se nepočítá.",
        "parametry": ["spoust_pole"],
    },
    {
        "klic": "cas",
        "nazev": "Nastane čas",
        "popis": (
            "Hlídá plánovač jednou denně: blížící se termín, dlouho beze změny, "
            "nebo dlouho ve stejném stavu."
        ),
        "parametry": ["cas_nastaveni"],
    },
    {
        "klic": "rucne",
        "nazev": "Jen ručně",
        "popis": "Samo se nespustí nikdy. Pouští se tlačítkem u záznamu — hodí se na postupy, které chce mít člověk pod kontrolou.",
        "parametry": [],
    },
]

MAPA_SPOUSTECU = {s["klic"]: s for s in SPOUSTECE}

# Na čem může stát časový spouštěč.
CASOVE_ZAKLADY = [
    {
        "klic": "pole",
        "nazev": "Podle data v poli",
        "popis": "Například 5 dní před předpokládaným uzavřením nebo 30 dní po podpisu.",
        "parametry": ["pole", "posun_dni"],
    },
    {
        "klic": "necinnost",
        "nazev": "Dlouho se nic nedělo",
        "popis": "Od poslední změny záznamu (nebo poslední aktivity) uplynul zadaný počet dní.",
        "parametry": ["dni"],
    },
    {
        "klic": "ve_stavu",
        "nazev": "Dlouho leží ve stejném stavu",
        "popis": "Záznam je ve svém současném stavu déle než zadaný počet dní.",
        "parametry": ["dni"],
    },
]

MAPA_CASOVYCH = {z["klic"]: z for z in CASOVE_ZAKLADY}

# Jak často smí pravidlo zabrat na jeden záznam.
OPAKOVANI = [
    {
        "klic": "jednou",
        "nazev": "Nejvýš jednou na záznam",
        "popis": "Když se případ vrátí a znovu vyhraje, druhá objednávka nevznikne.",
    },
    {
        "klic": "vzdy",
        "nazev": "Pokaždé, když spouštěč nastane",
        "popis": "Vhodné u „změní se pole“ — jinak by pravidlo zabralo jen napoprvé.",
    },
]

__all__ = [
    "AKCE",
    "CASOVE_ZAKLADY",
    "ENTITY_S_VLASTNIKEM",
    "MAPA_AKCI",
    "MAX_HLOUBKA",
    "OPAKOVANI",
    "PRIJEMCI",
    "SPOUSTECE",
    "SPOUSTECI_ENTITY",
    "Kontext",
    "beh_out",
    "po_vzniku",
    "po_zmene_poli",
    "po_zmene_stavu",
    "pravidlo_out",
    "seed_pravidla",
    "spust_pravidlo",
    "spust_rucne",
    "zapni_sledovani",
    "zmenena_pole",
]


# ---- kroky pravidla ---------------------------------------------------------
def kroky_pravidla(pravidlo: CrmPravidlo) -> list[dict]:
    """Kroky pravidla v pořadí. Zvládne i starý tvar „jedna akce + nastavení“.

    Překlopení dělá migrace při nasazení, ale test i suchý běh můžou dostat
    objekt sestavený v paměti — a pravidlo bez kroků, které „má akci“, by tiše
    nedělalo nic.
    """
    kroky = list(pravidlo.kroky or [])
    if kroky:
        return [k for k in kroky if isinstance(k, dict) and k.get("akce")]
    if pravidlo.akce:
        return [{"akce": pravidlo.akce, "nastaveni": dict(pravidlo.nastaveni or {})}]
    return []


# ---- zápis do logu a do aktivit ---------------------------------------------
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
    spoustec: str = "",
    klic_behu: str = "",
) -> None:
    """Řádek do logu běhů. Selhání zápisu logu nesmí shodit akci, která uspěla."""
    try:
        db.add(
            CrmPravidloBeh(
                pravidlo_id=pravidlo.id,
                entita=entita,
                zaznam_id=zaznam_id,
                klic_behu=klic_behu,
                vysledek=vysledek,
                popis=popis,
                spoustec=spoustec,
                spustil_user_id=user.id if user is not None else None,
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001
        log.warning("Běh pravidla %s se nepodařilo zapsat", pravidlo.id, exc_info=True)


def uz_bezelo(db: Session, pravidlo: CrmPravidlo, entita: str, zaznam_id: int) -> bool:
    """Zabralo už tohle pravidlo na tenhle záznam? (Jen u `opakovat="jednou"`.)

    Kontroluje se tady i unikátním indexem v DB: index chrání před souběhem
    dvou requestů, dotaz před tím, aby se kvůli němu nemusela rušit transakce.
    """
    if (pravidlo.opakovat or "jednou") != "jednou":
        return False
    return (
        db.query(CrmPravidloBeh.id)
        .filter(
            CrmPravidloBeh.pravidlo_id == pravidlo.id,
            CrmPravidloBeh.entita == entita,
            CrmPravidloBeh.zaznam_id == zaznam_id,
        )
        .first()
        is not None
    )


# ---- provedení jednoho pravidla ---------------------------------------------
def spust_pravidlo(db: Session, pravidlo: CrmPravidlo, kontext: Kontext) -> list[str]:
    """Provede kroky jednoho pravidla nad jedním záznamem. Nikdy nevyhodí výjimku.

    Vrací popisy provedených kroků (prázdný seznam = nic se nestalo). Zápis do
    logu i poznámky dělá tahle funkce, aby se to nemuselo opakovat u každého
    spouštěče.
    """
    entita, zaznam = kontext.entita, kontext.zaznam
    zaznam_id = getattr(zaznam, "id", None)
    if zaznam_id is None:
        return []

    # Jedno pravidlo se v jednom řetězu nespustí dvakrát ani při dost velké
    # hloubce — jinak by „A mění stav na X“ a „X mění stav na A“ pingpongovaly.
    otisk = (pravidlo.id, entita, zaznam_id)
    if otisk in kontext.navstivene:
        return []
    kontext.navstivene.add(otisk)

    if not kontext.nanecisto and uz_bezelo(db, pravidlo, entita, zaznam_id):
        return []

    plati, duvod = pole_modul.vyhodnot(db, entita, zaznam, pravidlo.podminky)
    if not plati:
        if not kontext.nanecisto:
            # Nesplněné podmínky se ZAPISUJÍ jen u opakovatelných pravidel…
            # ne: u „jednou“ by řádek v logu znamenal „už běželo“ a pravidlo by
            # se na ten záznam nikdy nedostalo, i kdyby podmínky později platily.
            if (pravidlo.opakovat or "jednou") != "jednou":
                _zapis_beh(
                    db, pravidlo, entita, zaznam_id, "preskoceno", duvod,
                    kontext.user, kontext.spoustec, uuid.uuid4().hex,
                )
        return [f"(nic — {duvod})"] if kontext.nanecisto else []

    kroky = kroky_pravidla(pravidlo)
    if not kroky:
        return []

    # Klíč běhu: prázdný u „jednou“ (unikátní index pak hlídá jeden běh na
    # záznam), unikátní u „vždy“ (jinak by druhý běh spadl na duplicitě).
    klic = "" if (pravidlo.opakovat or "jednou") == "jednou" else uuid.uuid4().hex

    hotove: list[str] = []
    chyby: list[str] = []
    for poradi, krok in enumerate(kroky, start=1):
        vykonavac = VYKONAVACE.get(str(krok.get("akce") or ""))
        if vykonavac is None:
            continue
        nastaveni = dict(krok.get("nastaveni") or {})

        # SAVEPOINT na KAŽDÝ krok zvlášť. Když spadne třetí krok, první dva mají
        # zůstat: „založ projekt, pošli e-mail, přiřaď vlastníka“ má po chybě
        # e-mailu pořád smysl. A hlavně — bez savepointu je session po výjimce
        # rozbitá a commit endpointu (tedy i přesun karty v kanbanu) by selhal.
        sp = db.begin_nested()
        try:
            popis = vykonavac(db, kontext, nastaveni)
            sp.commit()
        except Exception as e:  # noqa: BLE001 - selhání kroku nesmí shodit zbytek
            sp.rollback()
            log.warning(
                "Pravidlo %s, krok %s (%s) selhalo u %s #%s",
                pravidlo.id,
                poradi,
                krok.get("akce"),
                entita,
                zaznam_id,
                exc_info=True,
            )
            nazev_akce = (MAPA_AKCI.get(str(krok.get("akce"))) or {}).get("nazev", krok.get("akce"))
            chyby.append(f"{poradi}. {nazev_akce}: {e}" if kontext.nanecisto else f"{poradi}. {nazev_akce}")
            continue
        if popis:
            hotove.append(popis)

    if kontext.nanecisto:
        return hotove + [f"CHYBA v kroku {c}" for c in chyby]

    if not hotove and not chyby:
        # Kroky se vědomě neprovedly (objednávka už existuje apod.). Zapisuje se
        # taky, jinak by v nastavení nebylo poznat, proč se „nic nestalo“.
        _zapis_beh(
            db, pravidlo, entita, zaznam_id, "preskoceno",
            "Nebylo co udělat (záznam už existuje nebo chybí podklad).",
            kontext.user, kontext.spoustec, klic,
        )
        return []

    souhrn = "; ".join(hotove)
    if chyby:
        souhrn = (souhrn + " | " if souhrn else "") + "selhalo: " + ", ".join(chyby)
    _zapis_beh(
        db, pravidlo, entita, zaznam_id,
        "chyba" if chyby and not hotove else "hotovo",
        souhrn, kontext.user, kontext.spoustec, klic,
    )
    if hotove:
        _zaloz_poznamku(
            db, entita, zaznam_id, f"{souhrn} — pravidlo „{pravidlo.nazev}“.", kontext.user
        )
    return hotove


# ---- spouštěče --------------------------------------------------------------
def pravidla_pro(db: Session, entita: str, spoust_typ: str, **kde) -> list[CrmPravidlo]:
    """Aktivní pravidla daného spouštěče, v pořadí, v jakém je má vedení."""
    q = db.query(CrmPravidlo).filter(
        CrmPravidlo.aktivni.is_(True),
        CrmPravidlo.spoust_entita == entita,
        CrmPravidlo.spoust_typ == spoust_typ,
    )
    if "stav" in kde:
        q = q.filter(CrmPravidlo.spoust_stav == kde["stav"])
    if "pole" in kde:
        q = q.filter(CrmPravidlo.spoust_pole == kde["pole"])
    return q.order_by(CrmPravidlo.poradi, CrmPravidlo.id).all()


def _spust_sadu(
    db: Session,
    pravidla: list[CrmPravidlo],
    entita: str,
    zaznam,
    user: User,
    spoustec: str,
    rodic: Kontext | None = None,
) -> list[str]:
    """Společné tělo všech spouštěčů: flush, kontrola hloubky, průchod pravidly."""
    if not pravidla:
        return []

    hloubka = (rodic.hloubka + 1) if rodic is not None else 0
    if hloubka > MAX_HLOUBKA:
        log.warning(
            "Automatizace: řetěz pravidel u %s #%s je hlubší než %s, další se nespouští",
            entita,
            getattr(zaznam, "id", "?"),
            MAX_HLOUBKA,
        )
        return []

    # FLUSH PŘED SAVEPOINTEM. Volající má změnu zatím jen v session (`p.stav =
    # ...` bez flushe). Kdyby se poprvé flushla až UVNITŘ savepointu,
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
        return []

    hotove: list[str] = []
    for pravidlo in pravidla:
        kontext = Kontext(
            entita=entita,
            zaznam=zaznam,
            user=user,
            pravidlo=pravidlo,
            spoustec=spoustec,
            hloubka=hloubka,
            navstivene=rodic.navstivene if rodic is not None else set(),
        )
        hotove.extend(spust_pravidlo(db, pravidlo, kontext))
    return hotove


def po_zmene_stavu(
    db: Session, entita: str, zaznam, novy_stav: str, user: User, rodic: Kontext | None = None
) -> list[str]:
    """Spustí pravidla navěšená na přechod do `novy_stav`. Nikdy nevyhodí výjimku.

    Volá se PŘED `db.commit()` volajícího endpointu, aby všechno (nová
    objednávka, poznámka, log běhu) vzniklo v jedné transakci se změnou stavu.
    Když spadne akce, případ se uloží stejně a v logu bude řádek „chyba“.

    Vrací popisy provedených akcí — volající je může vrátit do UI, aby člověk
    hned viděl, co appka udělala. Prázdný seznam = nic se nedělo.
    """
    try:
        pravidla = pravidla_pro(db, entita, "stav", stav=novy_stav)
    except Exception:  # noqa: BLE001 - automatika je doplněk, ne součást akce
        log.warning("Nepodařilo se načíst pravidla automatizace", exc_info=True)
        return []
    return _spust_sadu(db, pravidla, entita, zaznam, user, "stav", rodic)


def po_vzniku(db: Session, entita: str, zaznam, user: User, rodic: Kontext | None = None) -> list[str]:
    """Spustí pravidla navěšená na založení nového záznamu.

    Volá se až po `db.flush()` volajícího (záznam musí mít `id`), ale pořád před
    commitem — stejně jako u změny stavu.
    """
    try:
        pravidla = pravidla_pro(db, entita, "vznik")
    except Exception:  # noqa: BLE001
        log.warning("Nepodařilo se načíst pravidla automatizace", exc_info=True)
        return []
    return _spust_sadu(db, pravidla, entita, zaznam, user, "vznik", rodic)


# ---- sledování změn polí -----------------------------------------------------
# Klíč v `session.info`, pod kterým se hromadí, co se v téhle transakci změnilo.
KLIC_ZMEN = "automatizace_zmenena_pole"

# Model → entita. Co tu není, se nesleduje.
SLEDOVANE_MODELY = {
    "ObchodniPripad": "op",
    "Objednavka": "obj",
    "CrmProjekt": "pro",
    "Nabidka": "nab",
}


def _zmeny_objektu(entita: str, zaznam) -> set[str]:
    """Která pole se na objektu právě teď změnila (podle historie atributů).

    Porovnávají se STARÁ a NOVÁ hodnota, ne jen „bylo přiřazeno“: endpoint
    přiřazuje `p.nazev = vstup.nazev` u všech polí bez ohledu na to, jestli se
    hodnota liší, takže „co endpoint přiřadil“ by bylo vždycky všechno a
    spouštěč by bral po každém uložení.
    """
    from sqlalchemy import inspect as sa_inspect

    zmenene: set[str] = set()
    try:
        stav = sa_inspect(zaznam)
    except Exception:  # noqa: BLE001 - objekt mimo session (test, náhled)
        return zmenene

    for pole in pole_modul.POLE.get(entita, []):
        klic = pole["klic"]
        atribut = stav.attrs.get(klic)
        if atribut is None:
            continue
        historie = atribut.history
        if not historie.has_changes():
            continue
        stara = historie.deleted[0] if historie.deleted else None
        nova = historie.added[0] if historie.added else None
        # Přiřazení téže hodnoty změna není. Když stará hodnota není k dispozici
        # (atribut se nestihl načíst), bere se to jako změna — přehlédnutá změna
        # je horší než jedno spuštění navíc, protože se na pravidlo spoléhá.
        if historie.deleted and stara == nova:
            continue
        zmenene.add(klic)

    # Vlastní pole žijí v jednom JSONB sloupci, takže „změnilo se extra“ nestačí
    # — pravidlo visí na konkrétním poli. Porovnává se slovník po klíčích.
    extra = stav.attrs.get("extra")
    if extra is not None and extra.history.has_changes():
        stara_e = dict(extra.history.deleted[0] or {}) if extra.history.deleted else {}
        nova_e = dict(extra.history.added[0] or {}) if extra.history.added else {}
        for klic in set(stara_e) | set(nova_e):
            if stara_e.get(klic) != nova_e.get(klic):
                zmenene.add(f"{pole_modul.PREDPONA_VLASTNI}{klic}")
    return zmenene


def _zaznamenej_zmeny(session, flush_context=None, instances=None) -> None:
    """`before_flush`: uloží změněná pole do session, než je flush zahodí.

    Proč událost, a ne prosté zjištění v endpointu: historie atributů se ztrácí
    při KAŽDÉM flushi — a ten může nastat kdykoli, protože každý dotaz spouští
    autoflush. Endpoint, který mezi přiřazením polí a voláním automatiky pošle
    notifikaci (tedy se na něco zeptá databáze), by tím historii smazal a
    pravidlo by se tiše nespustilo. Stejný důvod, proč takhle funguje i audit.
    """
    try:
        for zaznam in list(session.dirty):
            entita = SLEDOVANE_MODELY.get(type(zaznam).__name__)
            if entita is None or getattr(zaznam, "id", None) is None:
                continue
            zmeny = _zmeny_objektu(entita, zaznam)
            if zmeny:
                kde = session.info.setdefault(KLIC_ZMEN, {})
                kde.setdefault((entita, zaznam.id), set()).update(zmeny)
    except Exception:  # noqa: BLE001 - sledování je doplněk, ne součást uložení
        log.warning("Automatizace: sledování změn polí selhalo", exc_info=True)


def zapni_sledovani() -> None:
    """Zapne sledování změn polí. Volá se jednou při startu (viz `main.py`)."""
    from sqlalchemy import event
    from sqlalchemy.orm import Session as SessionTrida

    if not event.contains(SessionTrida, "before_flush", _zaznamenej_zmeny):
        event.listen(SessionTrida, "before_flush", _zaznamenej_zmeny)


def zmenena_pole(db: Session, entita: str, zaznam) -> set[str]:
    """Co se u záznamu v téhle transakci změnilo — z paměti session i z aktuální.

    Spojuje dvě věci: co zachytily předchozí flushe (přes událost) a co je
    v objektu změněné právě teď a ještě neflushnuté.
    """
    zaznam_id = getattr(zaznam, "id", None)
    ulozene = set((db.info.get(KLIC_ZMEN) or {}).get((entita, zaznam_id)) or set())
    return ulozene | _zmeny_objektu(entita, zaznam)


def po_zmene_poli(
    db: Session, entita: str, zaznam, user: User, rodic: Kontext | None = None
) -> list[str]:
    """Spustí pravidla navěšená na změnu pole. Sama si zjistí, co se změnilo.

    Volá se PŘED commitem — po commitu se paměť změn zahazuje a nebylo by
    z čeho poznat, co se vlastně změnilo.
    """
    try:
        zmenene = zmenena_pole(db, entita, zaznam)
        if not zmenene:
            return []
        pravidla = [p for p in pravidla_pro(db, entita, "pole") if p.spoust_pole in zmenene]
        # Zapamatované změny se po vyzvednutí zahazují: druhé volání v témž
        # requestu (uložení → přepočet → uložení) by jinak spustilo pravidlo
        # podruhé na tutéž změnu.
        (db.info.get(KLIC_ZMEN) or {}).pop((entita, getattr(zaznam, "id", None)), None)
    except Exception:  # noqa: BLE001
        log.warning("Nepodařilo se načíst pravidla automatizace", exc_info=True)
        return []
    return _spust_sadu(db, pravidla, entita, zaznam, user, "pole", rodic)


def spust_rucne(
    db: Session, pravidlo: CrmPravidlo, zaznam, user: User, nanecisto: bool = False
) -> list[str]:
    """Pustí konkrétní pravidlo na konkrétní záznam — tlačítkem, nebo nanečisto.

    Ruční spuštění záměrně NEkontroluje typ spouštěče: když si člověk vybere
    pravidlo a záznam, chce ho spustit, i kdyby jinak čekalo na noční plánovač.
    Podmínky se kontrolují dál — pravidlo, které na záznam nesedí, by udělalo
    něco jiného, než co je v něm napsané.
    """
    kontext = Kontext(
        entita=pravidlo.spoust_entita,
        zaznam=zaznam,
        user=user,
        pravidlo=pravidlo,
        spoustec="rucne",
        nanecisto=nanecisto,
    )
    try:
        db.flush()
    except Exception:  # noqa: BLE001
        log.warning("Flush před ručním spuštěním selhal", exc_info=True)
        return []
    return spust_pravidlo(db, pravidlo, kontext)


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
        "spoustec": getattr(b, "spoustec", "") or "",
        "kdo": _jmeno(b.spustil),
        "kdy": b.kdy.isoformat() if b.kdy else None,
    }


def _popis_spoustece(db: Session, p: CrmPravidlo) -> str:
    """Věta „KDYŽ …“ pro seznam pravidel."""
    entita = SPOUSTECI_ENTITY.get(p.spoust_entita, p.spoust_entita)
    typ = p.spoust_typ or "stav"
    if typ == "stav":
        stav = stavy_modul.najdi(db, p.spoust_entita, p.spoust_stav)
        return f"{entita} → {stav.nazev if stav is not None else p.spoust_stav}"
    if typ == "vznik":
        return f"{entita} — nový záznam"
    if typ == "pole":
        d = pole_modul.definice(db, p.spoust_entita, p.spoust_pole)
        return f"{entita} — změna pole {d['nazev'] if d else p.spoust_pole}"
    if typ == "cas":
        n = p.cas_nastaveni or {}
        zaklad = str(n.get("zaklad") or "")
        if zaklad == "pole":
            d = pole_modul.definice(db, p.spoust_entita, str(n.get("pole") or ""))
            posun = int(n.get("posun_dni") or 0)
            nazev = d["nazev"] if d else n.get("pole")
            if posun < 0:
                return f"{entita} — {abs(posun)} dní před: {nazev}"
            if posun > 0:
                return f"{entita} — {posun} dní po: {nazev}"
            return f"{entita} — v den: {nazev}"
        if zaklad == "necinnost":
            return f"{entita} — {int(n.get('dni') or 0)} dní beze změny"
        if zaklad == "ve_stavu":
            return f"{entita} — {int(n.get('dni') or 0)} dní ve stejném stavu"
        return f"{entita} — časový spouštěč"
    return f"{entita} — jen ručně"


def pravidlo_out(db: Session, p: CrmPravidlo, s_behy: bool = False) -> dict:
    kroky = kroky_pravidla(p)
    out = {
        "id": p.id,
        "nazev": p.nazev,
        "aktivni": bool(p.aktivni),
        "poradi": p.poradi,
        "spoust_entita": p.spoust_entita,
        "spoust_typ": p.spoust_typ or "stav",
        "spoust_stav": p.spoust_stav or "",
        "spoust_pole": p.spoust_pole or "",
        "cas_nastaveni": dict(p.cas_nastaveni or {}),
        "podminky": dict(p.podminky or {}),
        "kroky": kroky,
        "opakovat": p.opakovat or "jednou",
        # Kolikrát pravidlo zabralo – hlavní údaj, po kterém vedení pozná,
        # jestli automatika něco dělá, nebo jen leží v seznamu.
        "behu": len([b for b in (p.behy or []) if b.vysledek == "hotovo"]),
    }
    stav = stavy_modul.najdi(db, p.spoust_entita, p.spoust_stav)
    out["spoust_stav_nazev"] = stav.nazev if stav is not None else (p.spoust_stav or "")
    out["entita_nazev"] = SPOUSTECI_ENTITY.get(p.spoust_entita, p.spoust_entita)
    out["spoustec_popis"] = _popis_spoustece(db, p)
    out["kroky_popis"] = [popis_kroku(db, p.spoust_entita, k) for k in kroky]
    out["podminky_popis"] = popis_podminek(db, p.spoust_entita, p.podminky)
    if s_behy:
        out["behy"] = [
            beh_out(b) for b in sorted(p.behy or [], key=lambda b: b.id, reverse=True)[:30]
        ]
    return out


def popis_podminek(db: Session, entita: str, podminky: dict | None) -> str:
    """Věta „POKUD …“ pro seznam pravidel. Prázdno = platí pro všechny."""
    polozky = list((podminky or {}).get("polozky") or [])
    if not polozky:
        return ""
    spojka = " a " if (podminky or {}).get("spojka", "vse") == "vse" else " nebo "
    casti: list[str] = []
    for pod in polozky:
        d = pole_modul.definice(db, entita, str(pod.get("pole") or ""))
        nazev = d["nazev"] if d else pod.get("pole")
        operatory = {
            o["klic"]: o for o in pole_modul.OPERATORY.get(d["typ"] if d else "text", [])
        }
        o = operatory.get(str(pod.get("operator") or ""))
        slovo = o["nazev"] if o else pod.get("operator")
        hodnota = pod.get("hodnota")
        if o is not None and not o.get("hodnota"):
            casti.append(f"{nazev} {slovo}")
        else:
            if isinstance(hodnota, (list, tuple)):
                hodnota = ", ".join(str(h) for h in hodnota)
            casti.append(f"{nazev} {slovo} {hodnota}")
    return spojka.join(casti)


# ---- kontrola při ukládání --------------------------------------------------
def over_pravidlo(db: Session, vstup: dict) -> dict:
    """Zkontroluje celé pravidlo a vrátí očištěná data k uložení.

    Vyhazuje `ValueError` s českým textem, který se v UI ukáže rovnou u
    formuláře. Kontroluje se všechno naráz — pravidlo, které nemá jak fungovat,
    se nemá dát uložit. Za běhu už na to není koho se zeptat.
    """
    entita = str(vstup.get("spoust_entita") or "")
    if entita not in SPOUSTECI_ENTITY:
        raise ValueError(f"Neznámá entita spouštěče: {entita}")

    typ = str(vstup.get("spoust_typ") or "stav")
    if typ not in MAPA_SPOUSTECU:
        raise ValueError(f"Neznámý spouštěč: {typ}")

    ciste: dict = {
        "spoust_entita": entita,
        "spoust_typ": typ,
        "spoust_stav": "",
        "spoust_pole": "",
        "cas_nastaveni": {},
    }

    if typ == "stav":
        stav = str(vstup.get("spoust_stav") or "")
        if stavy_modul.najdi(db, entita, stav) is None:
            raise ValueError(f"Stav „{stav}“ u {SPOUSTECI_ENTITY[entita]} neexistuje.")
        ciste["spoust_stav"] = stav

    if typ == "pole":
        klic = str(vstup.get("spoust_pole") or "")
        if pole_modul.definice(db, entita, klic) is None:
            raise ValueError(f"Pole „{klic}“ u {SPOUSTECI_ENTITY[entita]} neexistuje.")
        ciste["spoust_pole"] = klic

    if typ == "cas":
        ciste["cas_nastaveni"] = _over_cas(db, entita, vstup.get("cas_nastaveni") or {})

    opakovat = str(vstup.get("opakovat") or "jednou")
    if opakovat not in {o["klic"] for o in OPAKOVANI}:
        raise ValueError("Neznámé nastavení opakování.")
    ciste["opakovat"] = opakovat

    ciste["podminky"] = pole_modul.over_podminky(db, entita, vstup.get("podminky"))

    kroky_vstup = list(vstup.get("kroky") or [])
    if not kroky_vstup:
        raise ValueError("Pravidlo musí mít aspoň jeden krok — jinak by nic nedělalo.")
    if len(kroky_vstup) > 10:
        raise ValueError("Deset kroků v jednom pravidle je strop; rozděl to na dvě pravidla.")
    ciste["kroky"] = [over_krok(db, entita, k) for k in kroky_vstup]
    return ciste


def _over_cas(db: Session, entita: str, nastaveni: dict) -> dict:
    """Kontrola časového spouštěče."""
    zaklad = str(nastaveni.get("zaklad") or "")
    if zaklad not in MAPA_CASOVYCH:
        raise ValueError("U časového spouštěče vyber, na čem má stát.")
    if zaklad == "pole":
        klic = str(nastaveni.get("pole") or "")
        d = pole_modul.definice(db, entita, klic)
        if d is None:
            raise ValueError(f"Pole „{klic}“ u {SPOUSTECI_ENTITY[entita]} neexistuje.")
        if d["typ"] != "datum":
            raise ValueError(f"Pole „{d['nazev']}“ není datum, nedá se od něj počítat.")
        try:
            posun = int(nastaveni.get("posun_dni") or 0)
        except (TypeError, ValueError):
            raise ValueError("Posun ve dnech musí být číslo.") from None
        if abs(posun) > 365:
            raise ValueError("Posun je nejvýš rok dopředu nebo dozadu.")
        return {"zaklad": "pole", "pole": klic, "posun_dni": posun}

    try:
        dni = int(nastaveni.get("dni") or 0)
    except (TypeError, ValueError):
        raise ValueError("Počet dní musí být číslo.") from None
    if dni < 1 or dni > 365:
        raise ValueError("Počet dní musí být od 1 do 365.")
    return {"zaklad": zaklad, "dni": dni}


# Výchozí pravidla. Naseedují se VYPNUTÁ (`aktivni=False`) schválně: automatika,
# která začne zakládat záznamy hned po nasazení, aniž o ní kdokoli ví, je přesně
# to, co lidem vezme důvěru v appku. Vedení si je v Nastavení projde a zapne.
VYCHOZI_PRAVIDLA = [
    {
        "nazev": "Případ vyhrán → objednávka",
        "spoust_entita": "op",
        "spoust_typ": "stav",
        "spoust_stav": "vyhrano",
        "kroky": [{"akce": "objednavka", "nastaveni": {}}],
    },
    {
        "nazev": "Objednávka podepsaná → projekt ze šablony",
        "spoust_entita": "obj",
        "spoust_typ": "stav",
        "spoust_stav": "podepsana",
        "kroky": [{"akce": "projekt", "nastaveni": {}}],
    },
    {
        "nazev": "Nabídka odeslána → za 7 dní zavolat",
        "spoust_entita": "nab",
        "spoust_typ": "stav",
        "spoust_stav": "odeslana",
        "kroky": [
            {
                "akce": "ukol",
                "nastaveni": {
                    "za_dni": 7,
                    "nazev": "Zavolat zákazníkovi kvůli nabídce",
                    "text": "Ozvat se a zjistit, jak se k nabídce staví.",
                },
            }
        ],
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
                spoust_typ=p["spoust_typ"],
                spoust_stav=p["spoust_stav"],
                kroky=p["kroky"],
                opakovat="jednou",
            )
        )
    db.commit()
