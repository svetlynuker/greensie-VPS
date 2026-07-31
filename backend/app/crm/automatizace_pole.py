"""Pole záznamů pro automatizaci: podmínky „POKUD“ a akce „nastav pole“ (CRM-31).

Automatika potřebuje umět dvě věci, které v appce nikde jinde nejsou:

  1. **rozhodnout**, jestli pravidlo na záznam sedí („jen když je kategorie FVE
     a hodnota nad půl milionu“),
  2. **přepsat** hodnotu pole („nastav pravděpodobnost na 100 %“).

Obojí stojí na jednom katalogu polí, ne na dvou. Kdyby měly podmínky vlastní
seznam a akce vlastní, dřív nebo později by se rozešly a člověk by v UI viděl
pole, na které se dá filtrovat, ale nedá se nastavit — bez vysvětlení, proč.

---- Proč jen pole spouštěcí entity (a vlastní pole) --------------------------

Do podmínek se ZÁMĚRNĚ nedostanou pole navázaných záznamů („zákazník má PSČ
z Moravy“). Sahat přes relace znamená pro každé pole vymyslet, co když relace
chybí, a v UI vysvětlit, odkud se hodnota bere. Jediná výjimka je název
zákazníka u obchodního případu: je to údaj, podle kterého lidi opravdu filtrují,
a je jen jeden. Čte se, nezapisuje.

---- Proč `stav` není zapisovatelný -----------------------------------------

Stav se mění akcí „změň stav“, protože ta kromě sloupce zapíše i řádek do
`crm_stav_historie` a spustí navěšená pravidla. Kdyby se stav dal přepsat jako
obyčejné pole, vznikl by záznam, který v historii „nikdy nikam nepřešel“, a
kanban by ukazoval stav, ke kterému se nikdo nepřiznal.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmProjekt, CrmVlastniPole, ObchodniPripad, Objednavka

# Předpona, pod kterou se v klíči schovávají vlastní (admin definovaná) pole.
# `extra.dotace` je hodnota `zaznam.extra["dotace"]`.
PREDPONA_VLASTNI = "extra."

# ---- typy a operátory -------------------------------------------------------
# Operátory se nabízejí podle TYPU pole – „obsahuje“ u čísla nedává smysl a
# „větší než“ u textu by porovnávalo abecedně, což nikdo nečeká.
#
# Klíč operátoru je strojový a neměnný (drží se v `podminky` v DB), `nazev` je
# to, co člověk vidí. „Prázdné“ je u většiny typů: nevyplněné pole je legitimní
# stav, na který se pravidlo často věší („chybí předpokládané uzavření“).
OPERATORY: dict[str, list[dict]] = {
    "text": [
        {"klic": "je", "nazev": "je", "hodnota": True},
        {"klic": "neni", "nazev": "není", "hodnota": True},
        {"klic": "obsahuje", "nazev": "obsahuje", "hodnota": True},
        {"klic": "neobsahuje", "nazev": "neobsahuje", "hodnota": True},
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
    "dlouhy_text": [
        {"klic": "obsahuje", "nazev": "obsahuje", "hodnota": True},
        {"klic": "neobsahuje", "nazev": "neobsahuje", "hodnota": True},
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
    "cislo": [
        {"klic": "je", "nazev": "je rovno", "hodnota": True},
        {"klic": "neni", "nazev": "není rovno", "hodnota": True},
        {"klic": "vetsi", "nazev": "je větší než", "hodnota": True},
        {"klic": "vetsi_nebo", "nazev": "je větší nebo rovno", "hodnota": True},
        {"klic": "mensi", "nazev": "je menší než", "hodnota": True},
        {"klic": "mensi_nebo", "nazev": "je menší nebo rovno", "hodnota": True},
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
    "datum": [
        {"klic": "je", "nazev": "je", "hodnota": True},
        {"klic": "pred", "nazev": "je před", "hodnota": True},
        {"klic": "po", "nazev": "je po", "hodnota": True},
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
    "ano_ne": [
        {"klic": "je_ano", "nazev": "je zaškrtnuto", "hodnota": False},
        {"klic": "je_ne", "nazev": "není zaškrtnuto", "hodnota": False},
    ],
    "vyber": [
        {"klic": "je_jedno_z", "nazev": "je jedno z", "hodnota": True, "vice": True},
        {"klic": "neni_zadne_z", "nazev": "není žádné z", "hodnota": True, "vice": True},
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
    "vyber_mnoho": [
        {"klic": "obsahuje_nektere", "nazev": "obsahuje některé z", "hodnota": True, "vice": True},
        {
            "klic": "neobsahuje_zadne",
            "nazev": "neobsahuje žádné z",
            "hodnota": True,
            "vice": True,
        },
        {"klic": "prazdne", "nazev": "je prázdné", "hodnota": False},
        {"klic": "neprazdne", "nazev": "je vyplněné", "hodnota": False},
    ],
}
# Uživatel, stav i kategorie se v UI vybírají ze seznamu, takže se chovají jako
# „výběr“. Vlastní typ by znamenal třikrát tytéž operátory.
OPERATORY["uzivatel"] = OPERATORY["vyber"]
OPERATORY["stav"] = OPERATORY["vyber"]

# Typ vlastního pole (`TYPY_VLASTNIHO_POLE`) → typ tady. Shodné až na `vyber`,
# které u vlastního pole nabízí vlastní `volby`.
TYPY_Z_VLASTNIHO = {
    "text": "text",
    "dlouhy_text": "dlouhy_text",
    "cislo": "cislo",
    "datum": "datum",
    "ano_ne": "ano_ne",
    "vyber": "vyber",
}


# ---- katalog polí -----------------------------------------------------------
# `zapis` = smí se nastavit akcí „nastav pole“. Co se nedá zapsat, je buď
# odvozené (číslo záznamu z číselné řady), nebo má vlastní akci (stav, vlastník).
#
# `volby_z` říká UI, odkud vzít hodnoty do výběru; seznam se dopočítá až
# v `katalog()`, protože sedí v databázi (stavy, kategorie, uživatelé).
POLE: dict[str, list[dict]] = {
    "op": [
        {"klic": "cislo", "nazev": "Číslo případu", "typ": "text", "zapis": False},
        {"klic": "nazev", "nazev": "Název", "typ": "text", "zapis": True},
        {"klic": "popis", "nazev": "Popis", "typ": "dlouhy_text", "zapis": True},
        {"klic": "stav", "nazev": "Stav", "typ": "stav", "zapis": False, "volby_z": "stavy"},
        {
            "klic": "kategorie",
            "nazev": "Kategorie",
            "typ": "vyber_mnoho",
            "zapis": True,
            "volby_z": "kategorie",
        },
        {"klic": "hodnota_kc", "nazev": "Hodnota (Kč)", "typ": "cislo", "zapis": True},
        {
            "klic": "pravdepodobnost",
            "nazev": "Pravděpodobnost (%)",
            "typ": "cislo",
            "zapis": True,
        },
        {
            "klic": "predpokladane_uzavreni",
            "nazev": "Předpokládané uzavření",
            "typ": "datum",
            "zapis": True,
        },
        {"klic": "duvod_prohry", "nazev": "Důvod prohry", "typ": "text", "zapis": True},
        {
            "klic": "vlastnik_user_id",
            "nazev": "Vlastník",
            "typ": "uzivatel",
            "zapis": False,
            "volby_z": "uzivatele",
        },
        # Jediné pole přes relaci – viz docstring modulu.
        {"klic": "zakaznik_nazev", "nazev": "Zákazník (název)", "typ": "text", "zapis": False},
        {"klic": "raynet_code", "nazev": "Kód v Raynetu", "typ": "text", "zapis": False},
    ],
    "nab": [
        {"klic": "cislo", "nazev": "Číslo nabídky", "typ": "text", "zapis": False},
        {
            "klic": "typ",
            "nazev": "Typ nabídky",
            "typ": "vyber",
            "zapis": False,
            "volby_z": "typy_nabidky",
        },
        {
            "klic": "stav_obchodni",
            "nazev": "Obchodní stav",
            "typ": "stav",
            "zapis": False,
            "volby_z": "stavy",
        },
        {"klic": "zakaznik_nazev", "nazev": "Zákazník (název)", "typ": "text", "zapis": True},
        {"klic": "zakaznik_adresa", "nazev": "Adresa", "typ": "text", "zapis": True},
    ],
    "obj": [
        {"klic": "cislo", "nazev": "Číslo objednávky", "typ": "text", "zapis": False},
        {"klic": "nazev", "nazev": "Název", "typ": "text", "zapis": True},
        {"klic": "popis", "nazev": "Popis", "typ": "dlouhy_text", "zapis": True},
        {"klic": "stav", "nazev": "Stav", "typ": "stav", "zapis": False, "volby_z": "stavy"},
        {"klic": "cena_kc", "nazev": "Cena (Kč)", "typ": "cislo", "zapis": True},
        {"klic": "datum_podpisu", "nazev": "Datum podpisu", "typ": "datum", "zapis": True},
        {"klic": "datum_dodani", "nazev": "Datum dodání", "typ": "datum", "zapis": True},
        {"klic": "duvod_zruseni", "nazev": "Důvod zrušení", "typ": "text", "zapis": True},
        {
            "klic": "vlastnik_user_id",
            "nazev": "Vlastník",
            "typ": "uzivatel",
            "zapis": False,
            "volby_z": "uzivatele",
        },
    ],
    "pro": [
        {"klic": "cislo", "nazev": "Číslo projektu", "typ": "text", "zapis": False},
        {"klic": "nazev", "nazev": "Název", "typ": "text", "zapis": True},
        {"klic": "popis", "nazev": "Popis", "typ": "dlouhy_text", "zapis": True},
        {"klic": "stav", "nazev": "Stav", "typ": "stav", "zapis": False, "volby_z": "stavy"},
        {"klic": "zahajeni", "nazev": "Zahájení", "typ": "datum", "zapis": True},
        {"klic": "predani", "nazev": "Plánované předání", "typ": "datum", "zapis": True},
        {
            "klic": "vlastnik_user_id",
            "nazev": "Vlastník",
            "typ": "uzivatel",
            "zapis": False,
            "volby_z": "uzivatele",
        },
    ],
}

# Entita → model. Používá se při vyhledávání záznamů pro suchý běh a plánovač.
MODELY = {"op": ObchodniPripad, "obj": Objednavka, "pro": CrmProjekt}


def model_entity(entita: str):
    """Model spouštěcí entity. Nabídka je v jiném modulu, proto import až tady."""
    if entita == "nab":
        from app.nabidkovac.models import Nabidka

        return Nabidka
    return MODELY.get(entita)


def _vlastni_pole(db: Session, entita: str) -> list[dict]:
    """Vlastní (admin definovaná) pole entity jako položky katalogu."""
    out: list[dict] = []
    try:
        radky = (
            db.query(CrmVlastniPole)
            .filter(CrmVlastniPole.entita == entita)
            .order_by(CrmVlastniPole.poradi, CrmVlastniPole.id)
            .all()
        )
    except Exception:  # noqa: BLE001 - bez vlastních polí katalog dál funguje
        return out
    for p in radky:
        typ = TYPY_Z_VLASTNIHO.get(p.typ or "text", "text")
        polozka = {
            "klic": f"{PREDPONA_VLASTNI}{p.klic}",
            "nazev": p.nazev,
            "typ": typ,
            # Vlastní pole se zapisovat dají vždycky – nejsou odvozená a nemají
            # vlastní akci. Výjimka jsou výpočtová (mají `vzorec`): ta se počítají
            # ze jiných polí, takže by ruční přepis stejně přepočet přemazal.
            "zapis": not (getattr(p, "vzorec", "") or "").strip(),
            "vlastni": True,
        }
        if typ == "vyber":
            polozka["volby"] = [{"klic": v, "nazev": v} for v in (p.volby or [])]
        out.append(polozka)
    return out


def katalog(db: Session, entita: str) -> list[dict]:
    """Pole entity pro UI: pevná + vlastní, s operátory a naplněnými volbami."""
    from app.crm import kategorie as kategorie_modul
    from app.crm import stavy as stavy_modul
    from app.nabidkovac.models import TYPY_NABIDKY

    volby_zdroje = {
        "stavy": lambda: [
            {"klic": s.klic, "nazev": s.nazev} for s in stavy_modul.seznam(db, entita)
        ],
        "kategorie": lambda: [
            {"klic": k.klic, "nazev": k.nazev} for k in kategorie_modul.seznam(db)
        ],
        "uzivatele": lambda: [
            {"klic": str(u.id), "nazev": u.jmeno or u.email or f"#{u.id}"}
            for u in db.query(User).order_by(User.jmeno, User.id).all()
        ],
        "typy_nabidky": lambda: [{"klic": t, "nazev": t} for t in TYPY_NABIDKY],
    }

    out: list[dict] = []
    for p in list(POLE.get(entita, [])) + _vlastni_pole(db, entita):
        polozka = dict(p)
        zdroj = polozka.pop("volby_z", None)
        if zdroj and zdroj in volby_zdroje:
            polozka["volby"] = volby_zdroje[zdroj]()
        polozka["operatory"] = OPERATORY.get(polozka["typ"], OPERATORY["text"])
        out.append(polozka)
    return out


def definice(db: Session, entita: str, klic: str) -> dict | None:
    """Definice jednoho pole (bez naplněných voleb – ty potřebuje jen UI)."""
    for p in POLE.get(entita, []):
        if p["klic"] == klic:
            return p
    if klic.startswith(PREDPONA_VLASTNI):
        for p in _vlastni_pole(db, entita):
            if p["klic"] == klic:
                return p
    return None


# ---- čtení hodnot -----------------------------------------------------------
def hodnota(zaznam, klic: str):
    """Hodnota pole na záznamu. Neznámé pole vrací None, nevyhazuje."""
    if not klic:
        return None
    if klic.startswith(PREDPONA_VLASTNI):
        extra = getattr(zaznam, "extra", None) or {}
        return extra.get(klic[len(PREDPONA_VLASTNI) :])
    if klic == "zakaznik_nazev":
        # Nabídka má název zákazníka jako vlastní sloupec, případ ho má přes
        # relaci. Pro pravidlo je to jedno pole – rozdíl řeším tady, ne v UI.
        vlastni = getattr(zaznam, "zakaznik_nazev", None)
        if vlastni:
            return vlastni
        zakaznik = getattr(zaznam, "zakaznik", None)
        return getattr(zakaznik, "nazev", None) if zakaznik is not None else None
    return getattr(zaznam, klic, None)


def _na_cislo(x) -> Decimal | None:
    if x is None or x == "":
        return None
    if isinstance(x, bool):
        return None
    try:
        # Přes `str`, aby float 0.1 nedělal 0.1000000000000000055.
        return Decimal(str(x).replace(",", ".").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def na_datum(x) -> date | None:
    """Datum z čehokoli, co v poli může být (date, datetime, text). Veřejné —
    plánovač ho potřebuje na vlastní pole, kde datum leží v JSONB jako text."""
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    if isinstance(x, str) and x.strip():
        try:
            return date.fromisoformat(x.strip()[:10])
        except ValueError:
            return None
    return None


def _text(x) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "ano" if x else ""
    return str(x).strip()


def _seznam_hodnot(x) -> list[str]:
    """Hodnota podmínky jako seznam textů — operátory „je jedno z“ ho čekají."""
    if x is None:
        return []
    if isinstance(x, (list, tuple, set)):
        return [_text(v).lower() for v in x if _text(v)]
    return [v.strip().lower() for v in _text(x).split(",") if v.strip()]


def je_prazdna(x) -> bool:
    if x is None:
        return True
    if isinstance(x, bool):
        return False  # nezaškrtnuto NENÍ prázdné, je to platná odpověď „ne“
    if isinstance(x, (list, tuple, set, dict)):
        return len(x) == 0
    return _text(x) == ""


# ---- vyhodnocení podmínek ---------------------------------------------------
def _porovnej(typ: str, operator: str, skutecna, ocekavana) -> bool:
    """Jedna podmínka. Nikdy nevyhazuje — nevyhodnotitelná podmínka = nesplněná.

    Proč nesplněná a ne splněná: pravidlo, kterému nerozumíme, nemá zakládat
    objednávky. Tichý „nic se nestalo“ se dá dohledat v logu běhů, tichý „udělalo
    se to omylem" už ne.
    """
    if operator == "prazdne":
        return je_prazdna(skutecna)
    if operator == "neprazdne":
        return not je_prazdna(skutecna)
    if operator == "je_ano":
        return bool(skutecna)
    if operator == "je_ne":
        return not bool(skutecna)

    if typ in ("vyber", "uzivatel", "stav"):
        moznosti = _seznam_hodnot(ocekavana)
        mam = _text(skutecna).lower()
        if operator == "je_jedno_z":
            return bool(mam) and mam in moznosti
        if operator == "neni_zadne_z":
            return mam not in moznosti
        return False

    if typ == "vyber_mnoho":
        moznosti = set(_seznam_hodnot(ocekavana))
        mam = set(_seznam_hodnot(skutecna))
        if operator == "obsahuje_nektere":
            return bool(mam & moznosti)
        if operator == "neobsahuje_zadne":
            return not (mam & moznosti)
        return False

    if typ == "cislo":
        a, b = _na_cislo(skutecna), _na_cislo(ocekavana)
        if a is None or b is None:
            return False
        return {
            "je": a == b,
            "neni": a != b,
            "vetsi": a > b,
            "vetsi_nebo": a >= b,
            "mensi": a < b,
            "mensi_nebo": a <= b,
        }.get(operator, False)

    if typ == "datum":
        a, b = na_datum(skutecna), na_datum(ocekavana)
        if a is None or b is None:
            return False
        return {"je": a == b, "pred": a < b, "po": a > b}.get(operator, False)

    if typ == "ano_ne":
        return False  # ano/ne má jen `je_ano` / `je_ne`, vyřízené výš

    # text a dlouhy_text
    a, b = _text(skutecna).lower(), _text(ocekavana).lower()
    return {
        "je": a == b,
        "neni": a != b,
        "obsahuje": bool(b) and b in a,
        "neobsahuje": not (bool(b) and b in a),
    }.get(operator, False)


def vyhodnot(db: Session, entita: str, zaznam, podminky: dict | None) -> tuple[bool, str]:
    """Sedí pravidlo na záznam? Vrací (platí, důvod pro log).

    Prázdné podmínky = platí vždy. `spojka` říká, jestli musí platit všechny
    (`vse`) nebo aspoň jedna (`cokoli`); výchozí je `vse`, protože to je to, co
    člověk čeká, když si naklikal dvě podmínky pod sebe.
    """
    polozky = list((podminky or {}).get("polozky") or [])
    if not polozky:
        return True, ""

    spojka = (podminky or {}).get("spojka") or "vse"
    vysledky: list[tuple[bool, str]] = []
    for pod in polozky:
        klic = str(pod.get("pole") or "")
        operator = str(pod.get("operator") or "")
        d = definice(db, entita, klic)
        if d is None:
            # Pole mezitím zmizelo (admin smazal vlastní pole). Nesplněno –
            # a v důvodu je vidět, proč pravidlo přestalo brát.
            vysledky.append((False, f"pole „{klic}“ už neexistuje"))
            continue
        skutecna = hodnota(zaznam, klic)
        ok = _porovnej(d["typ"], operator, skutecna, pod.get("hodnota"))
        vysledky.append((ok, f"{d['nazev']}: {'ano' if ok else 'ne'}"))

    if spojka == "cokoli":
        plati = any(ok for ok, _ in vysledky)
    else:
        plati = all(ok for ok, _ in vysledky)
    if plati:
        return True, ""
    nesplnene = [popis for ok, popis in vysledky if not ok]
    return False, "Podmínky nesplněny (" + "; ".join(nesplnene) + ")"


def over_podminky(db: Session, entita: str, podminky: dict | None) -> dict:
    """Očistí podmínky při ukládání pravidla. Vyhazuje `ValueError` s vysvětlením.

    Kontroluje se při ukládání, ne za běhu: podmínka na neexistující pole by
    znamenala pravidlo, které nikdy nezabere, a nikdo by nevěděl proč.
    """
    vstup = podminky or {}
    polozky_vstup = list(vstup.get("polozky") or [])
    spojka = str(vstup.get("spojka") or "vse")
    if spojka not in ("vse", "cokoli"):
        raise ValueError("Spojka podmínek musí být „vse“ nebo „cokoli“.")

    ciste: list[dict] = []
    for pod in polozky_vstup:
        klic = str(pod.get("pole") or "").strip()
        if not klic:
            continue
        d = definice(db, entita, klic)
        if d is None:
            raise ValueError(f"Pole „{klic}“ u této entity neexistuje.")
        operator = str(pod.get("operator") or "").strip()
        povolene = {o["klic"]: o for o in OPERATORY.get(d["typ"], [])}
        if operator not in povolene:
            raise ValueError(
                f"Podmínka u pole „{d['nazev']}“ má neznámé srovnání: {operator or '—'}."
            )
        polozka = {"pole": klic, "operator": operator}
        if povolene[operator].get("hodnota"):
            hodnota_vstup = pod.get("hodnota")
            if povolene[operator].get("vice"):
                seznam = [
                    _text(v)
                    for v in (
                        hodnota_vstup
                        if isinstance(hodnota_vstup, (list, tuple))
                        else _text(hodnota_vstup).split(",")
                    )
                    if _text(v)
                ]
                if not seznam:
                    raise ValueError(f"U podmínky „{d['nazev']}“ chybí, s čím se má srovnat.")
                polozka["hodnota"] = seznam
            else:
                if je_prazdna(hodnota_vstup):
                    raise ValueError(f"U podmínky „{d['nazev']}“ chybí, s čím se má srovnat.")
                if d["typ"] == "cislo" and _na_cislo(hodnota_vstup) is None:
                    raise ValueError(f"U podmínky „{d['nazev']}“ musí být číslo.")
                if d["typ"] == "datum" and na_datum(hodnota_vstup) is None:
                    raise ValueError(
                        f"U podmínky „{d['nazev']}“ musí být datum ve tvaru RRRR-MM-DD."
                    )
                polozka["hodnota"] = (
                    _text(hodnota_vstup) if d["typ"] != "cislo" else str(_na_cislo(hodnota_vstup))
                )
        ciste.append(polozka)

    if not ciste:
        return {}
    return {"spojka": spojka, "polozky": ciste}


# ---- zápis hodnot -----------------------------------------------------------
def prevod_pro_zapis(db: Session, entita: str, klic: str, vstup):
    """Hodnota připravená k zapsání do sloupce. `ValueError` s českým textem.

    Převod musí být tady, ne v akci: `hodnota_kc` je Numeric, `predpokladane_
    uzavreni` Date a `extra.*` prostý JSON. Bez převodu by SQLAlchemy uložilo
    text do číselného sloupce a spadlo by to až při commitu — tedy v okamžiku,
    kdy už člověk posunul případ v kanbanu.
    """
    d = definice(db, entita, klic)
    if d is None:
        raise ValueError(f"Pole „{klic}“ u této entity neexistuje.")
    if not d.get("zapis"):
        raise ValueError(f"Pole „{d['nazev']}“ automatika přepisovat nesmí.")

    typ = d["typ"]
    if je_prazdna(vstup) and typ != "ano_ne":
        # Prázdná hodnota = smazat obsah pole. U textových sloupců je NOT NULL
        # s defaultem "", takže None by spadlo – proto prázdný text.
        return "" if typ in ("text", "dlouhy_text") else None
    if typ == "cislo":
        c = _na_cislo(vstup)
        if c is None:
            raise ValueError(f"U pole „{d['nazev']}“ musí být číslo.")
        return c
    if typ == "datum":
        dt = na_datum(vstup)
        if dt is None:
            raise ValueError(f"U pole „{d['nazev']}“ musí být datum ve tvaru RRRR-MM-DD.")
        return dt
    if typ == "ano_ne":
        return bool(vstup) and _text(vstup).lower() not in ("ne", "false", "0")
    if typ == "vyber_mnoho":
        polozky = [
            _text(v) for v in (vstup if isinstance(vstup, (list, tuple)) else _text(vstup).split(","))
        ]
        return [v for v in polozky if v]
    return _text(vstup)


def zapis(db: Session, entita: str, zaznam, klic: str, vstup) -> str:
    """Zapíše hodnotu do záznamu a vrátí popis změny pro log.

    `extra` se přiřazuje jako NOVÝ slovník, ne mutací původního: JSONB sloupec
    SQLAlchemy nesleduje po prvcích, takže `zaznam.extra["x"] = 1` by se
    do databáze nikdy neuložilo.
    """
    d = definice(db, entita, klic)
    if d is None:
        raise ValueError(f"Pole „{klic}“ u této entity neexistuje.")
    nova = prevod_pro_zapis(db, entita, klic, vstup)
    if klic.startswith(PREDPONA_VLASTNI):
        extra = dict(getattr(zaznam, "extra", None) or {})
        vlastni_klic = klic[len(PREDPONA_VLASTNI) :]
        if nova is None:
            extra.pop(vlastni_klic, None)
        else:
            # Do JSONB nepatří Decimal ani date – ani jedno se neserializuje.
            extra[vlastni_klic] = (
                str(nova) if isinstance(nova, Decimal) else nova.isoformat()
                if isinstance(nova, (date, datetime))
                else nova
            )
        zaznam.extra = extra
    else:
        setattr(zaznam, klic, nova)
    lidsky = "—" if je_prazdna(nova) else _text(nova)
    return f"{d['nazev']} = {lidsky}"
