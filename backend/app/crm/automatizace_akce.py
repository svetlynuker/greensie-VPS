"""Co automatika umí udělat — katalog akcí a jejich vykonavače (CRM-31).

Pravidlo neprovádí jednu akci, ale **seznam kroků**: „založ projekt, přiřaď
vlastníka, pošli mu e-mail". Je to jeden lidský postup, takže je to jedno
pravidlo — tři pravidla navěšená na tentýž stav by šla vypnout každé zvlášť
a nikdo by nepoznal, že spolu souvisela.

---- Jak přidat akci --------------------------------------------------------

Záznam do `AKCE` + funkce `_akce_<klic>` + řádek do `VYKONAVACE`. UI se skládá
z katalogu, takže nová akce se v nastavení objeví sama.

Vykonavač dostane `Kontext` a nastavení kroku a vrací **popis pro člověka**
(„Založena objednávka OBJ-26-0012“). Prázdný popis znamená „nebylo co udělat“ —
zapíše se jako přeskočeno, ne jako chyba: objednávka, která už existuje, není
porucha.

---- Co se NIKDY nesmí stát ------------------------------------------------

**Suchý běh nesmí nic poslat.** Náhled („co by pravidlo udělalo“) běží ve
savepointu, který se zahodí, takže záznamy v databázi nevzniknou — ale e-mail
odeslaný do internetu se vrátit nedá. Proto se každá akce, která opouští appku
(e-mail, notifikace), musí podívat na `kontext.nanecisto` a jen popsat, co by
udělala. Tohle hlídá test.

**Akce nesmí volat `db.commit()`.** Běží v transakci endpointu, který přesouvá
záznam v kanbanu; commit uvnitř by potvrdil i tu polovinu změn, kterou člověk
ještě nedokončil.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import automatizace_pole as pole_modul
from app.crm import ciselne_rady
from app.crm import projekty_kroky as kroky_modul
from app.crm import sablony as sablony_modul
from app.crm import stavy as stavy_modul
from app.crm.models import (
    CrmAktivita,
    CrmPravidlo,
    CrmProjekt,
    CrmSablona,
    CrmStavHistorie,
    Objednavka,
    ObjednavkaPolozka,
    ObchodniPripad,
    ProjektSablona,
)

log = logging.getLogger(__name__)

# Entity, na kterých může spouštěč stát. Shodné s klíči `crm_stavy` – automatika
# reaguje na dění v pipeline, takže jinou entitu než ty se stavy nemá kde vzít.
SPOUSTECI_ENTITY = {
    "op": "Obchodní případ",
    "nab": "Nabídka",
    "obj": "Objednávka",
    "pro": "Projekt",
}

# Entity, které mají vlastníka. Nabídka ho nemá (má jen `vytvoril_user_id`),
# takže u ní nemá smysl nabízet „přiřaď vlastníka“.
ENTITY_S_VLASTNIKEM = ("op", "obj", "pro")


@dataclass
class Kontext:
    """Všechno, co vykonavač potřebuje vědět o jednom spuštění pravidla.

    `hloubka` a `navstivene` jsou ochrana proti smyčce: akce „změň stav“ spustí
    pravidla navěšená na nový stav, a ta můžou zase měnit stav. Bez stropu by
    dvě pravidla („do realizace → do předání“, „do předání → do realizace“)
    zacyklila transakci a shodila request, kterým člověk jen posunul kartu.
    """

    entita: str
    zaznam: object
    user: User | None
    pravidlo: CrmPravidlo
    # Čím se pravidlo spustilo (klíč z `automatizace.SPOUSTECE`, nebo "rucne").
    spoustec: str = "stav"
    hloubka: int = 0
    # Náhled: nic se neuloží (savepoint se zahodí) a nic neodejde z appky.
    nanecisto: bool = False
    # (pravidlo_id, entita, zaznam_id) už provedené v tomhle řetězu.
    navstivene: set = field(default_factory=set)

    def symboly(self, db: Session) -> dict:
        """Hodnoty pro `{{zakaznik}}`, `{{cislo}}`… ze záznamu, na kterém stojíme."""
        return sablony_modul.hodnoty(
            db, self.entita, getattr(self.zaznam, "id", None), self.user
        )


# Katalog akcí. `entity` říká, od které spouštěcí entity akce umí pracovat —
# „založ projekt“ potřebuje objednávku nebo případ, z nabídky by neměl co vzít.
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
    {
        "klic": "stav",
        "nazev": "Přesuň do stavu",
        "popis": (
            "Posune záznam do jiného stavu — zapíše se do historie stejně, jako "
            "kdyby kartu přetáhl člověk. Pravidla navěšená na nový stav se spustí."
        ),
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["novy_stav"],
    },
    {
        "klic": "pole",
        "nazev": "Nastav hodnotu pole",
        "popis": (
            "Přepíše jedno pole záznamu, včetně vlastních (admin definovaných) "
            "polí. Prázdná hodnota pole vymaže."
        ),
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["pole", "hodnota"],
    },
    {
        "klic": "vlastnik",
        "nazev": "Přiřaď vlastníka",
        "popis": (
            "Nastaví vlastníka záznamu. Původní vlastník zůstane jako "
            "spoluvlastník, aby o svůj případ nepřišel bez varování."
        ),
        "entity": list(ENTITY_S_VLASTNIKEM),
        "parametry": ["komu_user_id"],
    },
    {
        "klic": "email",
        "nazev": "Pošli e-mail",
        "popis": (
            "Odešle e-mail podle šablony nebo napsaného textu. Adresát: vlastník "
            "záznamu, konkrétní kolega, nebo napsaná adresa."
        ),
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["komu", "komu_user_id", "adresa", "sablona_id", "predmet", "telo"],
    },
    {
        "klic": "notifikace",
        "nazev": "Pošli notifikaci v appce",
        "popis": (
            "Zpráva do zvonečku. Tichá varianta e-mailu — hodí se na věci, "
            "o kterých má kolega vědět, ale nemusí kvůli nim otevírat poštu."
        ),
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["komu", "komu_user_id", "predmet", "telo"],
    },
    {
        "klic": "poznamka",
        "nazev": "Zapiš poznámku",
        "popis": "Přidá k záznamu poznámku do aktivit. Nikomu nic neposílá.",
        "entity": ["op", "nab", "obj", "pro"],
        "parametry": ["telo"],
    },
    {
        "klic": "sablona_kroku",
        "nazev": "Rozbal šablonu kroků",
        "popis": (
            "Přidá do projektu kroky ze šablony a přepočítá termíny. Existující "
            "kroky zůstanou — projekt může mít šablonu „FVE“ i „Dotace“."
        ),
        "entity": ["pro"],
        "parametry": ["sablona_id"],
    },
]

MAPA_AKCI = {a["klic"]: a for a in AKCE}

# Komu se posílá e-mail nebo notifikace.
PRIJEMCI = [
    {"klic": "vlastnik", "nazev": "Vlastníkovi záznamu"},
    {"klic": "spoluvlastnici", "nazev": "Vlastníkovi i spoluvlastníkům"},
    {"klic": "konkretni", "nazev": "Konkrétnímu kolegovi"},
    {"klic": "adresa", "nazev": "Na napsanou adresu", "jen_email": True},
]


# ---- pomůcky ----------------------------------------------------------------
def _pripad_zaznamu(db: Session, entita: str, zaznam) -> ObchodniPripad | None:
    """Obchodní případ, pod který spouštěcí záznam patří.

    Akce, které zakládají záznamy, ho potřebují: objednávka i projekt bez případu
    vzniknout nesmí (viz `routes_realizace`), a u úkolu se z něj berou vlastníci.
    """
    if entita == "op":
        return zaznam
    pripad_id = getattr(zaznam, "obchodni_pripad_id", None)
    return db.get(ObchodniPripad, pripad_id) if pripad_id else None


def _vlastnictvi_pripadu(pripad: ObchodniPripad) -> tuple[int | None, list]:
    return pripad.vlastnik_user_id, list(pripad.spoluvlastnici or [])


def _uzivatel(db: Session, uzivatel_id) -> User | None:
    if not uzivatel_id:
        return None
    try:
        return db.get(User, int(uzivatel_id))
    except (TypeError, ValueError):
        return None


def _vlastnik_zaznamu(db: Session, kontext: Kontext) -> User | None:
    """Vlastník spouštěcího záznamu, nebo vlastník případu nad ním.

    Nabídka vlastníka nemá, ale patří pod případ, který ho má — a člověk čeká,
    že „pošli vlastníkovi“ u nabídky dojde tomu, kdo případ vede.
    """
    prima = _uzivatel(db, getattr(kontext.zaznam, "vlastnik_user_id", None))
    if prima is not None:
        return prima
    pripad = _pripad_zaznamu(db, kontext.entita, kontext.zaznam)
    return _uzivatel(db, pripad.vlastnik_user_id) if pripad is not None else None


def _prijemci(db: Session, kontext: Kontext, nastaveni: dict) -> list[User]:
    """Lidé, kterým akce pošle zprávu. Bez duplicit a bez smazaných uživatelů."""
    komu = str(nastaveni.get("komu") or "vlastnik")
    if komu == "konkretni":
        u = _uzivatel(db, nastaveni.get("komu_user_id"))
        return [u] if u is not None else []

    lide: list[User] = []
    vlastnik = _vlastnik_zaznamu(db, kontext)
    if vlastnik is not None:
        lide.append(vlastnik)
    if komu == "spoluvlastnici":
        for i in list(getattr(kontext.zaznam, "spoluvlastnici", None) or []):
            u = _uzivatel(db, i)
            if u is not None:
                lide.append(u)
    # Zachovává pořadí (vlastník první), zahazuje duplicity.
    videne: set = set()
    return [u for u in lide if not (u.id in videne or videne.add(u.id))]


def _text_zpravy(db: Session, kontext: Kontext, nastaveni: dict) -> tuple[str, str]:
    """Předmět a tělo zprávy — ze šablony, nebo z textu napsaného v pravidle.

    Šablona má přednost: když si ji někdo v pravidle vybral, chce posílat to, co
    je v ní, a ne to, co v pravidle zbylo z dřívějška. Symboly `{{zakaznik}}`
    doplňuje `sablony.doplnil`, tedy stejný mechanismus jako u ručních e-mailů —
    dvě implementace by znamenaly dvě různá chování téhož symbolu.
    """
    predmet = str(nastaveni.get("predmet") or "")
    telo = str(nastaveni.get("telo") or "")
    sablona_id = nastaveni.get("sablona_id")
    if sablona_id:
        s = db.get(CrmSablona, int(sablona_id))
        if s is not None:
            predmet = s.predmet or predmet
            telo = s.telo or telo
    symboly = kontext.symboly(db)
    return sablony_modul.doplnil(predmet, symboly), sablony_modul.doplnil(telo, symboly)


def popis_zaznamu(zaznam) -> str:
    cislo = getattr(zaznam, "cislo", "") or ""
    nazev = getattr(zaznam, "nazev", "") or ""
    return f"{cislo} · {nazev}".strip(" ·") or f"#{getattr(zaznam, 'id', '?')}"


# ---- akce: zakládání záznamů ------------------------------------------------
def _akce_objednavka(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Případ vyhrán → objednávka. Vrací popis pro log, nebo prázdno = přeskočeno."""
    from app.nabidkovac import polozky as polozky_modul
    from app.nabidkovac.models import Nabidka

    pripad = _pripad_zaznamu(db, kontext.entita, kontext.zaznam)
    if pripad is None:
        return ""

    # Druhá objednávka téhož případu je legitimní věc (etapy), ale automatika ji
    # zakládat nemá – dvě objednávky na jednu zakázku vzniknou vždycky z lidského
    # rozhodnutí, ne z přesunu v kanbanu.
    if db.query(Objednavka.id).filter(Objednavka.obchodni_pripad_id == pripad.id).first():
        return ""

    # Nabídka, ze které se čerpá: přednost má PŘIJATÁ (druh „vyhra“), protože ta
    # je ta, na které se zákazník dohodl. Bez přijaté se vezme poslední s cenou.
    nabidky = (
        db.query(Nabidka)
        .filter(Nabidka.obchodni_pripad_id == pripad.id)
        .order_by(Nabidka.id.desc())
        .all()
    )
    prijate = [
        n for n in nabidky if stavy_modul.je_druhu(db, "nab", n.stav_obchodni or "", "vyhra")
    ]
    nabidka = (prijate or nabidky or [None])[0]

    vlastnik, spolu = _vlastnictvi_pripadu(pripad)
    stav = stavy_modul.vychozi_klic(db, "obj")
    user = kontext.user
    o = Objednavka(
        cislo=ciselne_rady.dalsi_cislo(db, "obj"),
        obchodni_pripad_id=pripad.id,
        nabidka_id=nabidka.id if nabidka is not None else None,
        nazev=pripad.nazev or "",
        popis=f"Založeno automaticky pravidlem „{kontext.pravidlo.nazev}“.",
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

    Volba „podle kategorie“ existuje proto, že jedno pravidlo pak stačí na celou
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


def _akce_projekt(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Objednávka podepsaná → projekt se rozbalenou šablonou kroků."""
    pripad = _pripad_zaznamu(db, kontext.entita, kontext.zaznam)
    if pripad is None:
        return ""

    objednavka = kontext.zaznam if kontext.entita == "obj" else None
    # Druhý projekt téže objednávky (nebo případu, když spouštěčem je případ)
    # automatika nezakládá – stejná úvaha jako u objednávky.
    q = db.query(CrmProjekt.id)
    if objednavka is not None:
        q = q.filter(CrmProjekt.objednavka_id == objednavka.id)
    else:
        q = q.filter(CrmProjekt.obchodni_pripad_id == pripad.id)
    if q.first():
        return ""

    pocet = db.query(CrmProjekt.id).filter(CrmProjekt.obchodni_pripad_id == pripad.id).count()
    vlastnik, spolu = (
        (objednavka.vlastnik_user_id, list(objednavka.spoluvlastnici or []))
        if objednavka is not None
        else _vlastnictvi_pripadu(pripad)
    )
    stav = stavy_modul.vychozi_klic(db, "pro")
    user = kontext.user
    p = CrmProjekt(
        cislo=ciselne_rady.cislo_projektu(db, pripad, pocet),
        obchodni_pripad_id=pripad.id,
        objednavka_id=objednavka.id if objednavka is not None else None,
        nazev=(objednavka.nazev if objednavka is not None else "") or pripad.nazev or "",
        popis=f"Založeno automaticky pravidlem „{kontext.pravidlo.nazev}“.",
        stav=stav,
        # Zahájení je den, kdy se objednávka podepsala – od něj se počítají
        # termíny kroků. Datum podpisu má přednost, protože podpis mohl být dřív,
        # než ho někdo do appky zapsal.
        zahajeni=(getattr(objednavka, "datum_podpisu", None) if objednavka is not None else None)
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

    sablona = _vyber_sablonu(db, pripad, nastaveni.get("sablona_id"))
    if sablona is not None:
        kroky_modul.rozbal_sablonu(db, p, sablona)
        db.refresh(p)
        kroky_modul.prepocitej_terminy(db, p)
        return f"Založen projekt {p.cislo} ze šablony „{sablona.nazev}“"
    db.flush()
    return f"Založen projekt {p.cislo} (bez šablony — žádná neodpovídá kategorii)"


def _akce_ukol(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """„Za N dní zavolat“ – úkol navěšený na spouštěcí záznam."""
    try:
        za_dni = max(0, int(nastaveni.get("za_dni") or 0))
    except (TypeError, ValueError):
        za_dni = 0
    symboly = kontext.symboly(db)
    nazev = sablony_modul.doplnil(str(nastaveni.get("nazev") or "").strip(), symboly)
    nazev = nazev or "Ozvat se zákazníkovi"
    text = sablony_modul.doplnil(str(nastaveni.get("text") or "").strip(), symboly) or nazev

    komu = nastaveni.get("komu_user_id")
    resitel = int(komu) if komu else (getattr(kontext.zaznam, "vlastnik_user_id", None) or None)
    if resitel is None:
        vlastnik = _vlastnik_zaznamu(db, kontext)
        resitel = (vlastnik.id if vlastnik is not None else None) or (
            kontext.user.id if kontext.user is not None else None
        )
    # Úkol bez řešitele by nikomu nevyskočil v „moje úkoly“ a byl by k ničemu.
    if resitel is None or not db.query(User.id).filter(User.id == resitel).first():
        return ""

    termin = date.today() + timedelta(days=za_dni)
    a = CrmAktivita(
        entita=kontext.entita,
        zaznam_id=kontext.zaznam.id,
        druh="ukol",
        nazev=nazev,
        text=text,
        termin=termin,
        vlastnik_user_id=resitel,
        vytvoril_user_id=kontext.user.id if kontext.user is not None else None,
    )
    db.add(a)
    db.flush()
    return f"Založen úkol „{nazev}“ s termínem {termin.strftime('%d.%m.%Y')}"


def _akce_sablona_kroku(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Rozbalí šablonu kroků do existujícího projektu."""
    if kontext.entita != "pro":
        return ""
    sablona_id = nastaveni.get("sablona_id")
    sablona = db.get(ProjektSablona, int(sablona_id)) if sablona_id else None
    if sablona is None:
        pripad = _pripad_zaznamu(db, "pro", kontext.zaznam)
        sablona = _vyber_sablonu(db, pripad, None) if pripad is not None else None
    if sablona is None:
        return ""
    kroky = kroky_modul.rozbal_sablonu(db, kontext.zaznam, sablona)
    db.refresh(kontext.zaznam)
    kroky_modul.prepocitej_terminy(db, kontext.zaznam)
    return f"Přidáno {len(kroky)}× krok ze šablony „{sablona.nazev}“"


# ---- akce: úpravy záznamu ---------------------------------------------------
def _akce_stav(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Přesune záznam do jiného stavu — včetně historie a navěšených pravidel.

    Historie je tu podstatná: bez řádku v `crm_stav_historie` by v přehledu
    změn vznikl skok, ke kterému se nikdo nepřiznal, a statistika „jak dlouho
    případ leží ve stavu" by lhala.
    """
    novy = str(nastaveni.get("novy_stav") or "").strip()
    if not novy:
        return ""
    stav_def = stavy_modul.najdi(db, kontext.entita, novy)
    if stav_def is None:
        return ""

    # Nabídka drží obchodní stav v jiném sloupci než stav zpracování výpočtu.
    sloupec = "stav_obchodni" if kontext.entita == "nab" else "stav"
    puvodni = getattr(kontext.zaznam, sloupec, None)
    if puvodni == novy:
        return ""  # už tam je, není co dělat

    setattr(kontext.zaznam, sloupec, novy)
    db.add(
        CrmStavHistorie(
            entita=kontext.entita,
            zaznam_id=kontext.zaznam.id,
            ze_stavu=puvodni,
            do_stavu=novy,
            zmenil_user_id=kontext.user.id if kontext.user is not None else None,
        )
    )
    db.flush()

    # Navěšená pravidla. Import až tady: engine importuje tenhle modul, takže
    # import na začátku souboru by byl kruh.
    from app.crm import automatizace as engine

    dalsi = engine.po_zmene_stavu(
        db,
        kontext.entita,
        kontext.zaznam,
        novy,
        kontext.user,
        rodic=kontext,
    )
    popis = f"Přesunuto do stavu „{stav_def.nazev}“"
    if dalsi:
        popis += " (a spustilo to: " + "; ".join(dalsi) + ")"
    return popis


def _akce_pole(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Přepíše jedno pole záznamu (včetně vlastních polí)."""
    klic = str(nastaveni.get("pole") or "").strip()
    if not klic:
        return ""
    symboly = kontext.symboly(db)
    vstup = nastaveni.get("hodnota")
    if isinstance(vstup, str):
        # I do hodnoty pole se dají psát symboly („Vyhráno {{cislo}}“). U čísla
        # a data se nic nenajde, takže se nic nezmění.
        vstup = sablony_modul.doplnil(vstup, symboly)
    zmena = pole_modul.zapis(db, kontext.entita, kontext.zaznam, klic, vstup)
    db.flush()
    return f"Nastaveno {zmena}"


def _akce_vlastnik(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Přiřadí vlastníka; původního nechá jako spoluvlastníka.

    Proč nechat původního: automatika, která někomu bez varování odebere případ
    ze seznamu „moje“, vypadá jako ztracená data. Jako spoluvlastník na něj vidí
    dál a může si ho vrátit.
    """
    if kontext.entita not in ENTITY_S_VLASTNIKEM:
        return ""
    novy = _uzivatel(db, nastaveni.get("komu_user_id"))
    if novy is None:
        return ""
    puvodni_id = getattr(kontext.zaznam, "vlastnik_user_id", None)
    if puvodni_id == novy.id:
        return ""

    spolu = [i for i in list(getattr(kontext.zaznam, "spoluvlastnici", None) or []) if i != novy.id]
    if puvodni_id and puvodni_id not in spolu:
        spolu.append(puvodni_id)
    kontext.zaznam.vlastnik_user_id = novy.id
    kontext.zaznam.spoluvlastnici = spolu

    # Ať se o tom dozví — stejnou cestou, jako když ho přiřadí kolega.
    if not kontext.nanecisto:
        from app.crm import notifikace as notifikace_modul

        notifikace_modul.ohlas_prirazeni(
            db,
            kontext.user,
            popis_zaznamu(kontext.zaznam),
            sablony_modul.cesta_zaznamu(kontext.entita, kontext.zaznam.id),
            [novy.id],
        )
    db.flush()
    return f"Vlastníkem je {novy.jmeno or novy.email}"


# ---- akce: zprávy -----------------------------------------------------------
def _akce_email(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Odešle e-mail. V suchém běhu jen popíše, co by odeslala."""
    from app.mailer import email_nastaven, posli_email

    predmet, telo = _text_zpravy(db, kontext, nastaveni)
    if not predmet and not telo:
        return ""

    komu = str(nastaveni.get("komu") or "vlastnik")
    if komu == "adresa":
        adresy = [
            a.strip() for a in str(nastaveni.get("adresa") or "").replace(";", ",").split(",")
        ]
        adresy = [a for a in adresy if a]
    else:
        adresy = [u.email for u in _prijemci(db, kontext, nastaveni) if u.email]
    if not adresy:
        return ""

    if kontext.nanecisto:
        return f"Odešel by e-mail „{predmet or 'bez předmětu'}“ na: {', '.join(adresy)}"
    if not email_nastaven():
        # Bez nastaveného SMTP se nemá tvrdit, že něco odešlo. Do logu běhu jde
        # čitelný důvod, ne prázdno – jinak by to vypadalo, že pravidlo nebralo.
        return "E-mail neodešel: v appce není nastavené odesílání pošty"

    odeslano: list[str] = []
    for adresa in adresy:
        try:
            posli_email(adresa, predmet or "Zpráva z appky Greensie", telo or predmet)
            odeslano.append(adresa)
        except Exception:  # noqa: BLE001 - výpadek SMTP nesmí shodit celé pravidlo
            log.warning("Automatizace: e-mail na %s neodešel", adresa, exc_info=True)
    if not odeslano:
        return "E-mail neodešel (chyba odesílání, podrobnosti v logu aplikace)"
    return f"Odeslán e-mail „{predmet or 'bez předmětu'}“ na: {', '.join(odeslano)}"


def _akce_notifikace(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Zpráva do zvonečku (a e-mailem, pokud si to adresát u události zapnul)."""
    from app.crm import notifikace as notifikace_modul

    predmet, telo = _text_zpravy(db, kontext, nastaveni)
    if not predmet:
        predmet = f"Automatika: {popis_zaznamu(kontext.zaznam)}"
    lide = _prijemci(db, kontext, nastaveni)
    if not lide:
        return ""

    jmena = ", ".join(u.jmeno or u.email or f"#{u.id}" for u in lide)
    if kontext.nanecisto:
        return f"Odešla by notifikace „{predmet}“ pro: {jmena}"
    for u in lide:
        notifikace_modul.posli(
            db,
            u,
            "automatizace",
            predmet,
            telo,
            sablony_modul.cesta_zaznamu(kontext.entita, kontext.zaznam.id),
            # Bez `puvodce`: notifikaci posílá appka, ne člověk, který klikl.
            # Kdyby se předával, `posli()` by ji tomu člověku zahodilo („co si
            # udělám sám, mi appka hlásit nemusí") — jenže tohle si neudělal.
        )
    return f"Odeslána notifikace „{predmet}“ pro: {jmena}"


def _akce_poznamka(db: Session, kontext: Kontext, nastaveni: dict) -> str:
    """Poznámka do aktivit záznamu."""
    _, telo = _text_zpravy(db, kontext, nastaveni)
    if not telo.strip():
        return ""
    db.add(
        CrmAktivita(
            entita=kontext.entita,
            zaznam_id=kontext.zaznam.id,
            druh="poznamka",
            nazev="Automatizace",
            text=telo,
            vytvoril_user_id=kontext.user.id if kontext.user is not None else None,
        )
    )
    db.flush()
    return "Zapsána poznámka"


VYKONAVACE = {
    "objednavka": _akce_objednavka,
    "projekt": _akce_projekt,
    "ukol": _akce_ukol,
    "stav": _akce_stav,
    "pole": _akce_pole,
    "vlastnik": _akce_vlastnik,
    "email": _akce_email,
    "notifikace": _akce_notifikace,
    "poznamka": _akce_poznamka,
    "sablona_kroku": _akce_sablona_kroku,
}


# ---- kontrola při ukládání --------------------------------------------------
def over_krok(db: Session, entita: str, krok: dict) -> dict:
    """Zkontroluje jeden krok a vrátí očištěné nastavení. `ValueError` s vysvětlením.

    Kontroluje se při ukládání, ne za běhu: krok, který nemá jak fungovat, se
    nemá dát uložit. Za běhu už není koho se zeptat — a chyba by se projevila
    až tím, že se něco nestalo.
    """
    akce = str(krok.get("akce") or "").strip()
    definice = MAPA_AKCI.get(akce)
    if definice is None:
        raise ValueError(f"Neznámá akce: {akce or '—'}")
    if entita not in definice["entity"]:
        nazvy = ", ".join(SPOUSTECI_ENTITY[e] for e in definice["entity"])
        raise ValueError(f"Akce „{definice['nazev']}“ jde spustit jen od: {nazvy}.")

    vstup = krok.get("nastaveni") or {}
    ciste: dict = {}

    if akce in ("projekt", "sablona_kroku"):
        sablona_id = vstup.get("sablona_id")
        if sablona_id:
            if db.get(ProjektSablona, int(sablona_id)) is None:
                raise ValueError("Zvolená šablona kroků neexistuje.")
            ciste["sablona_id"] = int(sablona_id)

    if akce == "ukol":
        try:
            ciste["za_dni"] = max(0, min(365, int(vstup.get("za_dni") or 0)))
        except (TypeError, ValueError):
            raise ValueError("Počet dní u úkolu musí být číslo.") from None
        ciste["nazev"] = str(vstup.get("nazev") or "").strip()[:200]
        ciste["text"] = str(vstup.get("text") or "").strip()[:2000]
        if not ciste["nazev"]:
            raise ValueError("U úkolu vyplň, jak se má jmenovat.")
        komu = vstup.get("komu_user_id")
        if komu:
            if _uzivatel(db, komu) is None:
                raise ValueError("Zvolený řešitel úkolu neexistuje.")
            ciste["komu_user_id"] = int(komu)

    if akce == "stav":
        novy = str(vstup.get("novy_stav") or "").strip()
        if not novy:
            raise ValueError("U přesunu vyber, do kterého stavu se má záznam posunout.")
        if stavy_modul.najdi(db, entita, novy) is None:
            raise ValueError(f"Stav „{novy}“ u {SPOUSTECI_ENTITY[entita]} neexistuje.")
        ciste["novy_stav"] = novy

    if akce == "pole":
        klic = str(vstup.get("pole") or "").strip()
        if not klic:
            raise ValueError("U nastavení hodnoty vyber, které pole se má přepsat.")
        # `prevod_pro_zapis` ověří i typ hodnoty a to, že se pole smí zapisovat.
        pole_modul.prevod_pro_zapis(db, entita, klic, vstup.get("hodnota"))
        ciste["pole"] = klic
        hodnota = vstup.get("hodnota")
        ciste["hodnota"] = (
            hodnota if isinstance(hodnota, (list, bool, int, float)) else str(hodnota or "")
        )

    if akce == "vlastnik":
        if _uzivatel(db, vstup.get("komu_user_id")) is None:
            raise ValueError("U přiřazení vlastníka vyber existujícího kolegu.")
        ciste["komu_user_id"] = int(vstup["komu_user_id"])

    if akce in ("email", "notifikace"):
        komu = str(vstup.get("komu") or "vlastnik")
        povolene = [p["klic"] for p in PRIJEMCI if akce == "email" or not p.get("jen_email")]
        if komu not in povolene:
            raise ValueError("U zprávy vyber, komu se má poslat.")
        ciste["komu"] = komu
        if komu == "konkretni":
            if _uzivatel(db, vstup.get("komu_user_id")) is None:
                raise ValueError("U zprávy vyber existujícího kolegu.")
            ciste["komu_user_id"] = int(vstup["komu_user_id"])
        if komu == "adresa":
            adresa = str(vstup.get("adresa") or "").strip()
            if "@" not in adresa:
                raise ValueError("Napsaná adresa nevypadá jako e-mail.")
            ciste["adresa"] = adresa[:500]

        sablona_id = vstup.get("sablona_id")
        if sablona_id:
            s = db.get(CrmSablona, int(sablona_id))
            if s is None:
                raise ValueError("Zvolená šablona textu neexistuje.")
            ciste["sablona_id"] = int(sablona_id)
        ciste["predmet"] = str(vstup.get("predmet") or "").strip()[:300]
        ciste["telo"] = str(vstup.get("telo") or "").strip()[:5000]
        if not sablona_id and not ciste["predmet"] and not ciste["telo"]:
            raise ValueError("U zprávy vyber šablonu, nebo napiš předmět a text.")

    if akce == "poznamka":
        ciste["telo"] = str(vstup.get("telo") or "").strip()[:5000]
        sablona_id = vstup.get("sablona_id")
        if sablona_id:
            if db.get(CrmSablona, int(sablona_id)) is None:
                raise ValueError("Zvolená šablona textu neexistuje.")
            ciste["sablona_id"] = int(sablona_id)
        if not ciste["telo"] and not sablona_id:
            raise ValueError("U poznámky napiš text, nebo vyber šablonu.")

    return {"akce": akce, "nastaveni": ciste}


def popis_kroku(db: Session, entita: str, krok: dict) -> str:
    """Krátká věta „co ten krok dělá“ pro seznam pravidel v UI.

    Skládá se na serveru, ne ve frontendu: parametry akcí zná tenhle modul a
    druhý popis v JSX by se s ním rozešel při každé nové akci.
    """
    akce = str(krok.get("akce") or "")
    definice = MAPA_AKCI.get(akce)
    if definice is None:
        return akce or "—"
    n = krok.get("nastaveni") or {}
    if akce == "ukol":
        za = n.get("za_dni")
        kdy = "dnes" if not za else f"za {za} dní"
        return f"Úkol „{n.get('nazev') or 'bez názvu'}“ ({kdy})"
    if akce == "stav":
        s = stavy_modul.najdi(db, entita, str(n.get("novy_stav") or ""))
        return f"Přesun do stavu „{s.nazev if s is not None else n.get('novy_stav')}“"
    if akce == "pole":
        d = pole_modul.definice(db, entita, str(n.get("pole") or ""))
        nazev = d["nazev"] if d else n.get("pole")
        hodnota = n.get("hodnota")
        return f"Nastavit {nazev} = {hodnota if not pole_modul.je_prazdna(hodnota) else '—'}"
    if akce == "vlastnik":
        u = _uzivatel(db, n.get("komu_user_id"))
        return f"Vlastníkem bude {u.jmeno or u.email if u is not None else '—'}"
    if akce in ("email", "notifikace"):
        komu = {p["klic"]: p["nazev"] for p in PRIJEMCI}.get(str(n.get("komu") or "vlastnik"), "")
        if n.get("komu") == "konkretni":
            u = _uzivatel(db, n.get("komu_user_id"))
            komu = u.jmeno or u.email if u is not None else komu
        if n.get("komu") == "adresa":
            komu = str(n.get("adresa") or "")
        slovo = "E-mail" if akce == "email" else "Notifikace"
        return f"{slovo} → {komu}"
    if akce in ("projekt", "sablona_kroku"):
        sid = n.get("sablona_id")
        s = db.get(ProjektSablona, int(sid)) if sid else None
        dodatek = f" ze šablony „{s.nazev}“" if s is not None else " (šablona podle kategorie)"
        return definice["nazev"].replace(" ze šablony", "") + dodatek
    return definice["nazev"]
