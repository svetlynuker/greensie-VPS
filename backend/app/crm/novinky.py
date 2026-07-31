"""Kdo už vidí čerstvě postavené funkce (rozhodnutí Dana, 31. 7. 2026).

Situace, kterou to řeší: Tomáš Minařík má právo `zakaznici`, takže **Zákazníky
a Obchodní případy vidět má a má je vidět dál**. Ale funkce, které vznikly
v posledních dnech, se zatím zkoušejí jen interně a nemají mu naskočit dřív,
než se Dan rozhodne je otevřít.

Kdyby se to řešilo právy, znamenalo by to buď vzít Minaříkovi `zakaznici`
(a sebrat mu i to, co dnes používá), nebo zavést právo, které by se muselo
ručně přidělovat každému zvlášť. Tohle je jednodušší: **jeden přepínač na
jednom místě.**

---- Až se to bude otevírat ----

Stačí přepsat tělo `ma_novinky()` (např. na `return True`, nebo na kontrolu
konkrétního práva). Nic jiného se měnit nemusí — frontend si příznak bere
z `/auth/me` a všechny endpointy jdou přes `vyzaduj_novinky`.

Co pod „novinky" spadá: zvoneček a notifikace, e-mail z appky, šablony textů,
mapa, panel historie změn, oblíbené záznamy. Naopak **nespadají** úpravy
obrazovek, které člověk už používá (sloupce v tabulce, stránkování, „nebo"
ve filtru, KPI pás) — ty se skrýt nedají, aniž by tabulka zůstala rozbitá,
a nejsou to samostatné funkce.
"""

from fastapi import Depends, HTTPException

from app.auth.models import User
from app.auth.permissions import get_current_user


def ma_novinky(user: User) -> bool:
    """Zatím jen supersprávci — appka se staví a testuje interně."""
    return bool(user.je_admin)


def vyzaduj_novinky(user: User = Depends(get_current_user)) -> User:
    """Závislost pro endpointy nových funkcí.

    Vrací 404, ne 403: pro toho, kdo funkci nemá vidět, prostě neexistuje.
    403 by prozradilo, že tam něco je, a lidé by se ptali, proč to nemají.
    """
    if not ma_novinky(user):
        raise HTTPException(status_code=404, detail="Nenalezeno")
    return user
