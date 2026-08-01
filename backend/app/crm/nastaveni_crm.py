"""Naše firma (Greensie) a firemní nastavení CRM — jeden řádek v `crm_nastaveni`.

Oddělené od uživatelských nastavení schválně: tohle jsou údaje FIRMY, které
vidí celá appka a mění je vedení, ne osobní volby jednotlivce.

Proč Greensie není záznam v Zákaznících, je v docstringu `CrmNastaveni`.
"""

from sqlalchemy.orm import Session

from app.auth.models import User, UzivatelProfil
from app.crm.models import CrmNastaveni

# Pole, která smí přijít z formuláře „Firma". Whitelist, ne `setattr` na cokoli:
# do konfigurace firmy se nesmí dát přepsat `id` ani `aktualizovano_at`.
TEXTOVA_POLE = (
    "nazev",
    "ico",
    "dic",
    "or_soud",
    "or_spisova_znacka",
    "adresa_ulice",
    "adresa_mesto",
    "adresa_psc",
    "adresa_stat",
    "koresp_ulice",
    "koresp_mesto",
    "koresp_psc",
    "koresp_stat",
    "telefon",
    "email",
    "web",
    "datova_schranka",
    "banka_nazev",
    "cislo_uctu",
    "iban",
    "swift",
    "statutar_jmeno",
    "statutar_funkce",
    "poznamka",
)
LOGICKA_POLE = ("platce_dph", "koresp_stejna")


def nacti(db: Session) -> CrmNastaveni:
    """Vrátí konfigurační řádek; když ještě není, vyrobí ho.

    Díky tomu nemusí volající řešit „co když je tabulka prázdná" a nastavení
    nepotřebuje seed při startu appky.
    """
    n = db.get(CrmNastaveni, 1)
    if n is None:
        n = CrmNastaveni(id=1, nase_adresa="")
        db.add(n)
        db.commit()
        db.refresh(n)
    return n


def slozena_adresa(n: CrmNastaveni) -> str:
    """Sídlo na jeden řádek („Ulice 1, 110 00 Praha").

    Tohle je to, co appka ukazuje u tlačítka „U nás" u místa konání schůzky.
    Skládá se ze sídla, aby existovala jediná pravda o naší adrese — dřív se
    ten řádek psal ručně zvlášť.
    """
    mesto = " ".join(
        x for x in [(n.adresa_psc or "").strip(), (n.adresa_mesto or "").strip()] if x
    )
    return ", ".join(x for x in [(n.adresa_ulice or "").strip(), mesto] if x)


def uloz(db: Session, vstup: dict) -> CrmNastaveni:
    """Uloží údaje o firmě. Pole, které ve vstupu není, zůstane beze změny.

    `nase_adresa` se dopočítá ze sídla — ale jen když je sídlo vyplněné. Bez té
    podmínky by prázdný formulář smazal adresu, kterou appka používá u schůzek.
    """
    n = nacti(db)
    for pole in TEXTOVA_POLE:
        if pole in vstup:
            setattr(n, pole, str(vstup[pole] or "").strip())
    for pole in LOGICKA_POLE:
        if pole in vstup:
            setattr(n, pole, bool(vstup[pole]))
    if "nase_adresa" in vstup:
        n.nase_adresa = str(vstup["nase_adresa"] or "").strip()
    slozena = slozena_adresa(n)
    if slozena:
        n.nase_adresa = slozena
    db.commit()
    db.refresh(n)
    return n


def interni_kontakty(db: Session) -> list[dict]:
    """Naši lidé = uživatelé appky, doplnění o profil pro e-mailový podpis.

    Seznam je jen ke ČTENÍ a nikde se nekopíruje: kdo přijde nebo odejde, řeší
    se v Admin nastavení → Uživatelé a Firma to hned ukáže. Druhá ruční evidence
    by se s tou první rozešla (rozhodnutí Dana, 1. 8. 2026).

    Telefon a funkce jsou z profilu (`uzivatel_profil`), který lidem vzniká pro
    podpis do pošty — takže se nezadávají dvakrát. Prázdné znamená „člověk si
    profil ještě nevyplnil", ne chybu.
    """
    # Profily jedním dotazem, ne přes relaci u každého uživatele (N+1).
    profily = {p.user_id: p for p in db.query(UzivatelProfil).all()}
    lide: list[dict] = []
    for u in db.query(User).order_by(User.jmeno).all():
        p = profily.get(u.id)
        lide.append(
            {
                "user_id": u.id,
                "jmeno": u.jmeno or u.email,
                "email": u.email or "",
                "funkce": (p.funkce or "") if p is not None else "",
                # Profil drží devět číslic bez předvolby (kvůli podpisu),
                # tady se ukazuje tak, jak se volá.
                "telefon": _telefon((p.telefon or "") if p is not None else ""),
                "skupina": u.skupina.nazev if u.skupina is not None else "",
                "je_admin": bool(u.je_admin),
            }
        )
    return lide


def _telefon(cislo: str) -> str:
    """Devět číslic z profilu → „+420 123 456 789"; cokoli jiného vrátí, jak je."""
    cifry = "".join(z for z in (cislo or "") if z.isdigit())
    if len(cifry) == 9:
        return f"+420 {cifry[0:3]} {cifry[3:6]} {cifry[6:9]}"
    return (cislo or "").strip()
