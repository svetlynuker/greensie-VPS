"""Obchodní pipeline nabídek – sekce Nabídky a její kanban.

Proč to žije v CRM a ne v nabídkovači: nabídkovač je *výpočetní* nástroj (sizing,
ROI, tisk). Otázka „co je odesláno, co viselo měsíc bez reakce a co zákazník
přijal" je obchodní evidence, tedy CRM. Data ale zůstávají v tabulce `nabidky` –
CRM si je nekopíruje, jen jim přidává obchodní stav a pohled.

DVA STAVY, KTERÉ SE NEMÍCHAJÍ:
  * `Nabidka.stav`          – stav zpracování (nahraná data, spočítáno…),
  * `Nabidka.stav_obchodni` – kde je nabídka u zákazníka (odeslána, přijata…).
Nabídka může být odeslaná a přitom mít rozpracovaný výpočet, a naopak. Kanban
sekce Nabídky pracuje s tím druhým.

VIDITELNOST: nabídka nemá vlastníka, patří k obchodnímu případu – řídí se tedy
právy případu. Nabídky bez případu (vznikly přímo v nabídkovači) vidí jejich
autor a kdokoli s právem `crm_vse`; jinak by „nikomu nepatřící" nabídky byly
vidět všem, což je horší chyba než nevidět je.
"""

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.auth.models import User
from app.crm import stavy as stavy_modul
from app.crm.models import ObchodniPripad
from app.crm.pristup import muze_vse
from app.nabidkovac.models import Nabidka

ENTITA = "nab"


def vychozi_stav(db: Session) -> str:
    """Klíč prvního stavu pipeline nabídek."""
    return stavy_modul.vychozi_klic(db, ENTITA)


def stav_nabidky(db: Session, n: Nabidka) -> str:
    """Obchodní stav nabídky; u starších záznamů spadne na první stav.

    Nezapisuje – čtení nemá měnit data. Zápis proběhne, až se s nabídkou
    v kanbanu skutečně pohne.
    """
    return n.stav_obchodni or vychozi_stav(db)


def omez_na_moje(q: Query, user: User) -> Query:
    """Filtr viditelnosti nabídek podle práv jejich obchodního případu.

    Dotaz musí mít připojenou `Nabidka`. Kdo má `crm_vse`, dostane ho nezměněný.
    """
    if muze_vse(user):
        return q
    # Případy, na které uživatel vidí (vlastník nebo spoluvlastník).
    moje_pripady = (
        q.session.query(ObchodniPripad.id)
        .filter(
            or_(
                ObchodniPripad.vlastnik_user_id == user.id,
                ObchodniPripad.spoluvlastnici.any(user.id),
            )
        )
        .subquery()
    )
    return q.filter(
        or_(
            Nabidka.obchodni_pripad_id.in_(moje_pripady),
            # Nabídka bez případu = vidí ji jen ten, kdo ji založil.
            (Nabidka.obchodni_pripad_id.is_(None)) & (Nabidka.vytvoril_user_id == user.id),
        )
    )


def vidi_nabidku(db: Session, n: Nabidka, user: User) -> bool:
    """Smí uživatel vidět konkrétní nabídku? (stejné pravidlo jako filtr výš)"""
    if muze_vse(user):
        return True
    if n is None:
        return False
    if n.obchodni_pripad_id is None:
        return n.vytvoril_user_id == user.id
    pripad = db.get(ObchodniPripad, n.obchodni_pripad_id)
    if pripad is None:
        return n.vytvoril_user_id == user.id
    return pripad.vlastnik_user_id == user.id or user.id in list(pripad.spoluvlastnici or [])


def je_spocitana(n: Nabidka) -> bool:
    """Má nabídka aspoň jedno spočítané řešení? (v kanbanu je to důležitější
    než stav zpracování – prázdnou nabídku nemá smysl posílat zákazníkovi)"""
    return len(n.reseni or []) > 0
