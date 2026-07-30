"""Práva CRM – otevírací práva na sekce + viditelnost jednotlivých ZÁZNAMŮ.

Zadání Dana (30. 7. 2026): „každý vidí jen svoje záznamy, vedení a vyšší vidí
všechny automaticky, s možností přidat právo vidět všechny i individuálně."

Žádný nový mechanismus rolí se nezavádí – appka už má skupiny + individuální
výjimky (`User.extra_prava`), což na to stačí přesně:

- `zakaznici`, `obchodni_pripady`  → otevřít danou sekci,
- `crm_vse`                        → vidět VŠECHNY záznamy, ne jen svoje.

„Vedení vidí vše automaticky" = skupina Vedení má v Admin nastavení právo
`crm_vse`. „Individuálně" = totéž právo v `extra_prava` konkrétního člověka.
Supersprávce (`je_admin`) má všechna práva, takže vidí vše bez nastavování.

Viditelnost záznamu: vlastník NEBO spoluvlastník. Spoluvlastníci existují
kvůli zástupům (dovolená) a tandemu OZ + technik – bez nich by se záznamy
musely překlápět na jiného vlastníka a ztratila by se odpovědnost.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit


def muze_zakazniky(user: User) -> bool:
    return muze_otevrit(user, "zakaznici")


def muze_pripady(user: User) -> bool:
    return muze_otevrit(user, "obchodni_pripady")


def muze_vse(user: User) -> bool:
    """Vidí uživatel všechny záznamy (vedení/admin), nebo jen svoje?"""
    return muze_otevrit(user, "crm_vse")


def muze_nastaveni(user: User) -> bool:
    """Smí měnit stavy pipeline a číselné řady?"""
    return muze_otevrit(user, "crm_nastaveni")


def vyzaduj_zakazniky(user: User = Depends(get_current_user)) -> User:
    if not muze_zakazniky(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Zákazníky nemáš oprávnění.",
        )
    return user


def vyzaduj_pripady(user: User = Depends(get_current_user)) -> User:
    if not muze_pripady(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na Obchodní případy nemáš oprávnění.",
        )
    return user


def vyzaduj_nastaveni(user: User = Depends(get_current_user)) -> User:
    if not muze_nastaveni(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Na nastavení CRM (stavy, číselné řady) nemáš oprávnění.",
        )
    return user


def omez_na_moje(q: Query, model, user: User) -> Query:
    """Přidá do dotazu filtr viditelnosti záznamů.

    Kdo má `crm_vse`, dostane dotaz nezměněný. Ostatní vidí jen záznamy, kde
    jsou vlastníkem nebo spoluvlastníkem. Záznamy BEZ vlastníka (např. po
    migraci ze starých nabídek) vidí jen ten, kdo má `crm_vse` – jinak by se
    „nikomu nepatřící" data zjevila všem, což je horší chyba než nevidět je.
    """
    if muze_vse(user):
        return q
    return q.filter(
        or_(
            model.vlastnik_user_id == user.id,
            model.spoluvlastnici.any(user.id),
        )
    )


def vidi_zaznam(zaznam, user: User) -> bool:
    """Smí uživatel vidět konkrétní záznam? (stejné pravidlo jako `omez_na_moje`)"""
    if muze_vse(user):
        return True
    if zaznam is None:
        return False
    if zaznam.vlastnik_user_id == user.id:
        return True
    return user.id in list(zaznam.spoluvlastnici or [])


def vyzaduj_zaznam(zaznam, user: User, co: str = "Záznam"):
    """Vrátí záznam, nebo skončí 404.

    Schválně 404, ne 403: cizí záznam se nemá projevit ani svou existencí.
    Kdo nevidí, pro toho neexistuje – jinak by se dalo hádáním ID zjistit,
    kolik případů firma vede a jaká čísla používá.
    """
    if zaznam is None or not vidi_zaznam(zaznam, user):
        raise HTTPException(status_code=404, detail=f"{co} neexistuje")
    return zaznam


def vychozi_vlastnik(user: User) -> int:
    """Kdo je vlastníkem nově zakládaného záznamu – vždy jeho autor.

    (Vedení může vlastníka přepsat při uložení; tohle je jen výchozí hodnota,
    aby žádný záznam nevznikl bez vlastníka a nespadl do „nikomu nepatří".)
    """
    return user.id


def smi_menit(zaznam, user: User) -> bool:
    """Smí uživatel záznam upravit?

    Zatím totéž jako vidět: kdo záznam vidí, může ho i editovat. Rozdělovat
    čtení a zápis nemá pro pětičlenný obchod smysl a přidalo by to další
    dvě práva do katalogu. Vlastní právo na editaci se dá doplnit později,
    aniž by se měnil datový model.
    """
    return vidi_zaznam(zaznam, user)
