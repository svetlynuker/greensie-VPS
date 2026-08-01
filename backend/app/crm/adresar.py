"""Adresář CRM – našeptávač adres a dohledání, komu zpráva patří.

Dvě věci, které vypadají jako jedna, ale nejsou:

  1. **Našeptávač** (`naseptavac`) – člověk píše do políčka „Komu" a appka
     nabízí adresy z CRM. Jde o pohodlí, takže se hledá volně (podle jména,
     firmy i adresy, bez ohledu na diakritiku).
  2. **Párování** (`dohledaj_podle_adresy`) – u příchozí zprávy se hledá, ke
     komu ji přiřadit. Tady musí být shoda **přesná na adresu**, jinak by se
     zpráva připsala cizí firmě. Nepřesné párování je horší než žádné: v CRM
     by pak visela cizí komunikace a nikdo by nevěděl, že je špatně.

Adresář se nikde neukládá jako vlastní tabulka. Je to pohled na data, která
už v CRM jsou (zákazníci, jejich kontaktní osoby, uživatelé appky) – kopie by
znamenala, že se adresa opraví na jednom místě a v adresáři zůstane stará.

VIDITELNOST: našeptávač respektuje práva na záznamy (`pristup.omez_na_moje`),
takže kdo nevidí cizí zákazníky, nedostane je ani napovězené. Kolegy z appky
vidí každý – ti jsou „firemní telefonní seznam", ne cizí záznam.
"""

import unicodedata

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import pristup
from app.crm.models import ObchodniPripad, Zakaznik, ZakaznikKontakt

# Kolik položek se vejde do rozbaleného seznamu, než začne být k ničemu.
LIMIT_NASEPTAVACE = 12
# Nejkratší dotaz, který má smysl hledat. Na jedno písmeno by přišla polovina DB.
MIN_ZNAKU = 2


def bez_diakritiky(text: str) -> str:
    """`Nováková` → `novakova`. Aby našeptávač našel i na „novak"."""
    rozlozeno = unicodedata.normalize("NFKD", text or "")
    return "".join(z for z in rozlozeno if not unicodedata.combining(z)).lower()


def _vzor(dotaz: str) -> str:
    return f"%{(dotaz or '').strip()}%"


def naseptavac(db: Session, user: User, dotaz: str, limit: int = LIMIT_NASEPTAVACE) -> list[dict]:
    """Adresy z CRM pro políčko „Komu". Řadí podle užitečnosti, ne abecedy.

    Pořadí je záměrné: **kontaktní osoby první**. E-mail se v 90 % případů
    píše konkrétnímu člověku, ne na obecnou adresu firmy; kdyby byla první
    firma, člověk by ji odklikl omylem.

    Vrací `[{adresa, jmeno, popis, druh, zakaznik_id}]`, kde `druh` je
    `kontakt` | `zakaznik` | `kolega` – frontend podle něj vybírá ikonu.
    """
    dotaz = (dotaz or "").strip()
    if len(dotaz) < MIN_ZNAKU:
        return []
    vzor = _vzor(dotaz)
    vysledek: list[dict] = []
    videne: set[str] = set()

    def pridej(adresa: str, jmeno: str, popis: str, druh: str, zakaznik_id: int | None) -> None:
        adresa = (adresa or "").strip().lower()
        # Dvakrát tatáž adresa je v seznamu k ničemu – vyhrává první nalezení,
        # tedy to z přednějšího zdroje (kontakt před firmou).
        if "@" not in adresa or adresa in videne:
            return
        videne.add(adresa)
        vysledek.append(
            {
                "adresa": adresa,
                "jmeno": (jmeno or "").strip(),
                "popis": (popis or "").strip(),
                "druh": druh,
                "zakaznik_id": zakaznik_id,
            }
        )

    # ---- kontaktní osoby zákazníků ----
    q_kontakty = (
        db.query(ZakaznikKontakt, Zakaznik)
        .join(Zakaznik, ZakaznikKontakt.zakaznik_id == Zakaznik.id)
        .filter(ZakaznikKontakt.email != "")
        .filter(
            or_(
                ZakaznikKontakt.jmeno.ilike(vzor),
                ZakaznikKontakt.email.ilike(vzor),
                Zakaznik.nazev.ilike(vzor),
            )
        )
    )
    q_kontakty = pristup.omez_na_moje(q_kontakty, Zakaznik, user)
    for kontakt, zakaznik in q_kontakty.order_by(
        ZakaznikKontakt.hlavni.desc(), ZakaznikKontakt.jmeno
    ).limit(limit * 3):
        popis = zakaznik.nazev
        if kontakt.funkce:
            popis = f"{kontakt.funkce} – {zakaznik.nazev}"
        pridej(kontakt.email, kontakt.jmeno, popis, "kontakt", zakaznik.id)

    # ---- obecné adresy firem ----
    q_zakaznici = db.query(Zakaznik).filter(Zakaznik.email != "").filter(
        or_(Zakaznik.nazev.ilike(vzor), Zakaznik.email.ilike(vzor))
    )
    q_zakaznici = pristup.omez_na_moje(q_zakaznici, Zakaznik, user)
    for z in q_zakaznici.order_by(Zakaznik.nazev).limit(limit * 2):
        pridej(z.email, z.nazev, "klient" if z.typ == "klient" else "lead", "zakaznik", z.id)

    # ---- kolegové z appky ----
    q_lide = db.query(User).filter(User.email != "").filter(
        or_(User.jmeno.ilike(vzor), User.email.ilike(vzor))
    )
    for u in q_lide.order_by(User.jmeno).limit(limit):
        pridej(u.email, u.jmeno or u.email, "kolega", "kolega", None)

    # Dohledání bez diakritiky: databáze `unaccent` nemá, takže se dofiltruje
    # v Pythonu nad tím, co se našlo. Není to úplné, ale pokrývá běžný případ
    # „napíšu novak, chci Nováka" – kdo napíše přesně, najde vždy.
    if not vysledek:
        vysledek = _naseptavac_bez_diakritiky(db, user, dotaz, limit)

    return vysledek[:limit]


def _naseptavac_bez_diakritiky(db: Session, user: User, dotaz: str, limit: int) -> list[dict]:
    """Záložní hledání, když přesná shoda nic nenašla (diakritika)."""
    hledane = bez_diakritiky(dotaz)
    vysledek: list[dict] = []
    videne: set[str] = set()

    q = (
        db.query(ZakaznikKontakt, Zakaznik)
        .join(Zakaznik, ZakaznikKontakt.zakaznik_id == Zakaznik.id)
        .filter(ZakaznikKontakt.email != "")
    )
    q = pristup.omez_na_moje(q, Zakaznik, user)
    # Strop na 2000 řádků: adresář firmy téhle velikosti se do něj vejde celý
    # a zároveň se tím nedá dotazem shodit databáze.
    for kontakt, zakaznik in q.limit(2000):
        cil = bez_diakritiky(f"{kontakt.jmeno} {zakaznik.nazev} {kontakt.email}")
        adresa = (kontakt.email or "").lower()
        if hledane in cil and adresa not in videne and "@" in adresa:
            videne.add(adresa)
            vysledek.append(
                {
                    "adresa": adresa,
                    "jmeno": kontakt.jmeno,
                    "popis": zakaznik.nazev,
                    "druh": "kontakt",
                    "zakaznik_id": zakaznik.id,
                }
            )
            if len(vysledek) >= limit:
                break
    return vysledek


def dohledaj_podle_adresy(db: Session, adresa: str) -> dict:
    """Ke které firmě a případu adresa patří. **Jen přesná shoda.**

    Vrací `{"zakaznik_id", "pripad_id", "kontakt_id"}` s `None` tam, kde se nic
    nenašlo. Volá se při synchronizaci pošty, takže musí být rychlé a hlavně
    nesmí hádat – přiřadit zprávu špatné firmě je horší než nepřiřadit vůbec.

    Práva se tady **neuplatňují schválně**: běží to v synchronizaci na pozadí,
    kde není „kdo se ptá". Viditelnost se řeší až při čtení zprávy, kde uživatel
    známý je.
    """
    adresa = (adresa or "").strip().lower()
    vysledek: dict = {"zakaznik_id": None, "pripad_id": None, "kontakt_id": None}
    if "@" not in adresa:
        return vysledek

    kontakt = (
        db.query(ZakaznikKontakt)
        .filter(func.lower(ZakaznikKontakt.email) == adresa)
        .order_by(ZakaznikKontakt.hlavni.desc(), ZakaznikKontakt.id)
        .first()
    )
    if kontakt is not None:
        vysledek["kontakt_id"] = kontakt.id
        vysledek["zakaznik_id"] = kontakt.zakaznik_id
    else:
        zakaznik = (
            db.query(Zakaznik)
            .filter(func.lower(Zakaznik.email) == adresa)
            .order_by(Zakaznik.id)
            .first()
        )
        if zakaznik is not None:
            vysledek["zakaznik_id"] = zakaznik.id

    if vysledek["zakaznik_id"] is None:
        # Poslední pokus: doména firmy. Jen když je doména u jediného zákazníka –
        # u „seznam.cz" nebo „gmail.com" by to jinak přiřadilo náhodně.
        vysledek["zakaznik_id"] = _zakaznik_podle_domeny(db, adresa)

    if vysledek["zakaznik_id"] is not None:
        vysledek["pripad_id"] = _otevreny_pripad(db, vysledek["zakaznik_id"])
    return vysledek


# Domény, ze kterých se firma odvodit nedá (veřejné freemaily).
VEREJNE_DOMENY = {
    "seznam.cz", "email.cz", "post.cz", "centrum.cz", "volny.cz", "atlas.cz",
    "gmail.com", "googlemail.com", "outlook.com", "outlook.cz", "hotmail.com",
    "hotmail.cz", "live.com", "icloud.com", "me.com", "yahoo.com", "proton.me",
    "protonmail.com", "mail.com", "tiscali.cz", "quick.cz", "chello.cz",
}


def _zakaznik_podle_domeny(db: Session, adresa: str) -> int | None:
    """Firma podle domény adresy – jen když je shoda jednoznačná."""
    domena = adresa.rsplit("@", 1)[-1].strip().lower()
    if not domena or domena in VEREJNE_DOMENY:
        return None
    vzor = f"%@{domena}"
    nalezeni = (
        db.query(Zakaznik.id)
        .filter(or_(Zakaznik.email.ilike(vzor), Zakaznik.web.ilike(f"%{domena}%")))
        .limit(3)
        .all()
    )
    if len(nalezeni) == 1:
        return nalezeni[0][0]
    # Zkusit ještě kontaktní osoby – firma nemusí mít obecnou adresu.
    kontakty = (
        db.query(ZakaznikKontakt.zakaznik_id)
        .filter(ZakaznikKontakt.email.ilike(vzor))
        .distinct()
        .limit(3)
        .all()
    )
    ids = {k[0] for k in kontakty}
    return ids.pop() if len(ids) == 1 else None


def _otevreny_pripad(db: Session, zakaznik_id: int) -> int | None:
    """Nejnovější **otevřený** případ firmy – tam pošta nejspíš patří.

    Uzavřené případy se přeskakují: došlá pošta se nemá lepit na zakázku, která
    je rok hotová. Když otevřený případ není, zpráva zůstane jen u firmy.
    """
    from app.crm.models import CrmStav

    # `ObchodniPripad.stav` je KLÍČ do `CrmStav` (entita="op"), ne FK – stavy se
    # dají mazat a případ o svůj stav přijít nesmí. Join proto jde přes klíč.
    pripad = (
        db.query(ObchodniPripad)
        .outerjoin(
            CrmStav,
            (CrmStav.klic == ObchodniPripad.stav) & (CrmStav.entita == "op"),
        )
        .filter(ObchodniPripad.zakaznik_id == zakaznik_id)
        .filter(or_(CrmStav.id.is_(None), CrmStav.druh == "otevreny"))
        .order_by(ObchodniPripad.id.desc())
        .first()
    )
    return pripad.id if pripad is not None else None


def dohledaj_vsechny(db: Session, adresy: list[str]) -> list[dict]:
    """Ke každé adrese najde záznam v CRM. Duplicitní firmy sloučí.

    Tohle je základ „rejnetování" (párování pošty na záznamy po vzoru Raynetu):
    zpráva se netýká jen odesílatele, ale **všech** adres, které v ní jsou.
    Když je v kopii kontaktní osoba jiné firmy, patří zpráva i k ní.

    Vrací `[{adresa, role, zakaznik_id, kontakt_id, pripad_id}]` jen pro adresy,
    kde se něco našlo. Pořadí zachovává vstup, takže odesílatel je první.
    """
    vysledek: list[dict] = []
    # Jedna firma se ve zprávě objeví klidně třikrát (osoba, obecná adresa,
    # kopie). Do historie patří jednou – jinak by karta ukazovala trojmo totéž.
    videne_dvojice: set[tuple] = set()

    for polozka in adresy:
        adresa = (polozka.get("adresa") or "").strip().lower()
        role = polozka.get("role") or "od"
        if not adresa or "@" not in adresa:
            continue
        nalez = dohledaj_podle_adresy(db, adresa)
        if nalez["zakaznik_id"] is None:
            continue
        klic = (nalez["zakaznik_id"], nalez["kontakt_id"])
        if klic in videne_dvojice:
            continue
        videne_dvojice.add(klic)
        vysledek.append(
            {
                "adresa": adresa,
                "role": role,
                "zakaznik_id": nalez["zakaznik_id"],
                "kontakt_id": nalez["kontakt_id"],
                "pripad_id": nalez["pripad_id"],
            }
        )
    return vysledek


def adresy_ze_zpravy(zprava) -> list[dict]:
    """Všechny adresy zprávy s rolí: odesílatel, příjemci, kopie."""
    seznam = [{"adresa": zprava.od_adresa or "", "role": "od"}]
    for pole, role in (("komu", "komu"), ("kopie", "kopie")):
        for a in getattr(zprava, pole, None) or []:
            if isinstance(a, dict) and a.get("adresa"):
                seznam.append({"adresa": a["adresa"], "role": role})
    return seznam
