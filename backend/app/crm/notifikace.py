"""Notifikace CRM: co se komu pošle, kam a jestli vůbec (CRM-36 + CRM-10).

Jeden modul pro obojí schválně — volba „co chci dostávat" a odesílání musí
znát tentýž katalog událostí. Kdyby byly zvlášť, dřív nebo později by vznikla
událost, kterou appka posílá, ale nejde vypnout.

---- Dvě roviny doručení ------------------------------------------------------

  * **v appce** (zvoneček) — vždycky se zapíše řádek do `crm_notifikace`,
    pokud si ho uživatel nevypnul,
  * **e-mailem** — jen když si ho uživatel u té události zapnul a SMTP je
    nastavené.

Notifikace v appce je výchozí u všeho, e-mail jen tam, kde se něco děje bez
uživatele (přiřazení, úkol po termínu). Důvod je v CRM-36: notifikace, kterou
si člověk nevybral, je obtěžování — a e-mail obtěžuje víc než tečka u zvonečku.

---- Pravidlo, na kterém tenhle modul stojí -----------------------------------

**Selhání notifikace nesmí nikdy shodit akci, která ji vyvolala.** Když se
nepodaří poslat e-mail, případ se musí uložit stejně. Proto je `posli()` celé
v try/except a chyba jde do logu, ne do odpovědi. Opačné pořadí (nejdřív
e-mail, pak commit) by znamenalo, že výpadek Seznamu blokuje práci obchodu.

---- Proč se nikomu neposílá to, co si udělal sám -----------------------------

`posli()` zahodí notifikaci, jejíž příjemce je zároveň původce. Bez toho by
appka psala „přiřadil sis případ" každému, kdo si sám sebe nastaví vlastníkem —
což je většina zakládání.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmNotifikace
from app.nastaveni.models import UzivatelskeNastaveni

log = logging.getLogger(__name__)

# Klíč v `uzivatelska_nastaveni`, pod kterým žije volba notifikací.
KLIC_NASTAVENI = "crm_notifikace"

# Katalog událostí. `email` je výchozí hodnota pro e-mail, `appka` pro zvoneček.
#
# Přidání události = jeden záznam sem (UI i ukládání jsou z něj odvozené) a
# volání `posli()` na místě, kde se to stane. Klíč je neměnný – nese ho uložená
# volba uživatele, takže přejmenování by lidem tiše zapnulo, co si vypnuli.
UDALOSTI = [
    {
        "klic": "prirazeni",
        "nazev": "Někdo mi přiřadil záznam",
        "popis": "Případ, objednávka nebo projekt, kde jsem nově vlastník nebo spoluvlastník.",
        "appka": True,
        "email": True,
    },
    {
        "klic": "ukol_dnes",
        "nazev": "Úkol mě čeká dnes",
        "popis": "Ranní souhrn úkolů, které mají termín dnes.",
        "appka": True,
        "email": False,
    },
    {
        "klic": "ukol_po_terminu",
        "nazev": "Úkol je po termínu",
        "popis": "Souhrn úkolů, kterým termín propadl a nejsou uzavřené.",
        "appka": True,
        "email": True,
    },
    {
        "klic": "zmena_stavu",
        "nazev": "Změnil se stav mého záznamu",
        "popis": "Někdo jiný posunul můj případ, nabídku, objednávku nebo projekt.",
        "appka": True,
        "email": False,
    },
    {
        "klic": "nabidka_odeslana",
        "nazev": "Nabídka odešla zákazníkovi",
        "popis": "Potvrzení, že e-mail s nabídkou opravdu odešel.",
        "appka": True,
        "email": False,
    },
    {
        "klic": "automatizace",
        "nazev": "Zpráva od automatiky",
        "popis": "Upozornění, které poslalo pravidlo automatizace (Nastavení → Automatizace).",
        "appka": True,
        # E-mailem ne: pravidlo, které má poslat e-mail, má na to vlastní krok
        # „Pošli e-mail“. Kdyby chodilo obojí, dostal by člověk dvě zprávy o téže
        # věci a jednu z nich by si vypnul — nejspíš tu, o kterou šlo.
        "email": False,
    },
]

MAPA_UDALOSTI = {u["klic"]: u for u in UDALOSTI}


def vychozi_volby() -> dict:
    """Výchozí nastavení pro uživatele, který si nic nezměnil."""
    return {u["klic"]: {"appka": u["appka"], "email": u["email"]} for u in UDALOSTI}


def volby(db: Session, uzivatel_id: int) -> dict:
    """Volby uživatele doplněné o výchozí hodnoty.

    Doplnění je důležité: když přibude nová událost, lidé s uloženým nastavením
    ji v uloženém JSONu nemají — a bez doplnění by ji přestali dostávat, aniž
    by si ji vypnuli.
    """
    out = vychozi_volby()
    row = (
        db.query(UzivatelskeNastaveni)
        .filter(
            UzivatelskeNastaveni.uzivatel_id == uzivatel_id,
            UzivatelskeNastaveni.klic == KLIC_NASTAVENI,
        )
        .first()
    )
    ulozene = (row.hodnota if row is not None else None) or {}
    for klic, hodnota in ulozene.items():
        if klic in out and isinstance(hodnota, dict):
            out[klic] = {
                "appka": bool(hodnota.get("appka", out[klic]["appka"])),
                "email": bool(hodnota.get("email", out[klic]["email"])),
            }
    return out


def uloz_volby(db: Session, uzivatel_id: int, vstup: dict) -> dict:
    """Uloží volby uživatele. Neznámé klíče se zahodí (smazaná událost)."""
    ciste = {
        klic: {"appka": bool(v.get("appka")), "email": bool(v.get("email"))}
        for klic, v in (vstup or {}).items()
        if klic in MAPA_UDALOSTI and isinstance(v, dict)
    }
    row = (
        db.query(UzivatelskeNastaveni)
        .filter(
            UzivatelskeNastaveni.uzivatel_id == uzivatel_id,
            UzivatelskeNastaveni.klic == KLIC_NASTAVENI,
        )
        .first()
    )
    if row is None:
        row = UzivatelskeNastaveni(uzivatel_id=uzivatel_id, klic=KLIC_NASTAVENI)
        db.add(row)
    row.hodnota = ciste
    db.commit()
    return volby(db, uzivatel_id)


def _posli_email(prijemce: User, predmet: str, telo: str, cesta: str) -> None:
    from app.mailer import app_url, email_nastaven, posli_email

    if not email_nastaven() or not prijemce.email:
        return
    odkaz = f"{app_url()}{cesta}" if cesta else app_url()
    posli_email(
        prijemce.email,
        f"[Greensie] {predmet}",
        f"{telo}\n\nOtevřít v appce: {odkaz}\n\n"
        "Tuhle zprávu posílá appka podle tvého nastavení notifikací "
        "(Nastavení → Notifikace).",
    )


def posli(
    db: Session,
    prijemce: User | None,
    udalost: str,
    predmet: str,
    text: str = "",
    cesta: str = "",
    puvodce: User | None = None,
) -> None:
    """Doručí notifikaci podle voleb příjemce. Nikdy nevyhodí výjimku.

    `cesta` je adresa ve frontendu (`/pripady/detail/12`), ne celé URL — e-mail
    si domyslí doménu z `APP_URL`, zvoneček ji použije rovnou jako odkaz.

    Volá se PŘED `db.commit()` volající akce, aby se řádek notifikace uložil
    ve stejné transakci; e-mail se posílá až po zapsání řádku.
    """
    try:
        if prijemce is None or udalost not in MAPA_UDALOSTI:
            return
        # Co si udělám sám, mi appka hlásit nemusí.
        if puvodce is not None and puvodce.id == prijemce.id:
            return

        volba = volby(db, prijemce.id).get(udalost, {})
        if volba.get("appka"):
            db.add(
                CrmNotifikace(
                    uzivatel_id=prijemce.id,
                    udalost=udalost,
                    predmet=predmet,
                    text=text,
                    cesta=cesta,
                )
            )
            db.flush()
        if volba.get("email"):
            try:
                _posli_email(prijemce, predmet, text or predmet, cesta)
            except Exception:  # noqa: BLE001 - výpadek SMTP nesmí zastavit práci
                log.warning("Notifikaci %s se nepodařilo odeslat e-mailem", udalost, exc_info=True)
    except Exception:  # noqa: BLE001 - notifikace je doplněk, ne součást akce
        log.warning("Notifikace %s selhala", udalost, exc_info=True)


def neprectene(db: Session, uzivatel_id: int, limit: int = 30) -> list[CrmNotifikace]:
    return (
        db.query(CrmNotifikace)
        .filter(CrmNotifikace.uzivatel_id == uzivatel_id, CrmNotifikace.precteno_at.is_(None))
        .order_by(CrmNotifikace.id.desc())
        .limit(limit)
        .all()
    )


def posledni(db: Session, uzivatel_id: int, limit: int = 30) -> list[CrmNotifikace]:
    """Poslední notifikace včetně přečtených — zvoneček ukazuje i historii,
    ať se dá dohledat, co člověk odklikl."""
    return (
        db.query(CrmNotifikace)
        .filter(CrmNotifikace.uzivatel_id == uzivatel_id)
        .order_by(CrmNotifikace.id.desc())
        .limit(limit)
        .all()
    )


def oznac_precteno(db: Session, uzivatel_id: int, ids: list[int] | None = None) -> int:
    """Označí notifikace za přečtené. Bez `ids` všechny nepřečtené."""
    q = db.query(CrmNotifikace).filter(
        CrmNotifikace.uzivatel_id == uzivatel_id, CrmNotifikace.precteno_at.is_(None)
    )
    if ids:
        q = q.filter(CrmNotifikace.id.in_(ids))
    ted = datetime.now(timezone.utc)
    pocet = 0
    for n in q.all():
        n.precteno_at = ted
        pocet += 1
    db.commit()
    return pocet


# ---- pomocníci pro volání z routes ------------------------------------------
def prijemci_zaznamu(db: Session, vlastnik_id, spoluvlastnici) -> list[User]:
    """Vlastník + spoluvlastníci jako uživatelé (bez duplicit a bez neexistujících)."""
    ids = []
    if vlastnik_id:
        ids.append(vlastnik_id)
    for i in list(spoluvlastnici or []):
        if i and i not in ids:
            ids.append(i)
    if not ids:
        return []
    mapa = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}
    return [mapa[i] for i in ids if i in mapa]


def ohlas_prirazeni(
    db: Session,
    puvodce: User,
    zaznam_popis: str,
    cesta: str,
    pridani: list[int],
) -> None:
    """„Někdo mi přiřadil záznam" pro nově přidané vlastníky.

    `pridani` jsou POUZE nově přibylí — volající musí porovnat starý a nový
    stav. Kdyby se posílalo všem vlastníkům při každém uložení, chodila by
    notifikace po každé změně čárky v popisu.
    """
    for u in prijemci_zaznamu(db, None, pridani):
        posli(
            db,
            u,
            "prirazeni",
            f"Máš na starost: {zaznam_popis}",
            f"{puvodce.jmeno or 'Někdo'} tě nastavil jako vlastníka nebo spoluvlastníka.",
            cesta,
            puvodce=puvodce,
        )


def ohlas_zmenu_stavu(
    db: Session,
    puvodce: User,
    zaznam_popis: str,
    cesta: str,
    novy_stav: str,
    vlastnik_id,
    spoluvlastnici=None,
) -> None:
    """„Změnil se stav mého záznamu" — posílá se vlastníkům, ne tomu, kdo klikl."""
    for u in prijemci_zaznamu(db, vlastnik_id, spoluvlastnici):
        posli(
            db,
            u,
            "zmena_stavu",
            f"{zaznam_popis} → {novy_stav}",
            f"Stav změnil {puvodce.jmeno or 'někdo'}.",
            cesta,
            puvodce=puvodce,
        )
