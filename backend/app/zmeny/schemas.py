from typing import Optional

from pydantic import BaseModel


class UkolZmena(BaseModel):
    """Jeden konkrétní úkol v detailu (v které fázi, s odkazem do Freela)."""

    ukol: str = ""  # label sloupce (fáze - úkol)
    faze: str = ""
    nazev: str = ""
    termin: Optional[str] = None
    url: str = ""


class ProjektZmeny(BaseModel):
    id: int
    nazev: str
    url: str = ""
    splneno: int = 0
    spadlo_do_prodleni: int = 0
    aktualne_v_prodleni: int = 0
    detail_splneno: list[UkolZmena] = []
    detail_spadlo: list[UkolZmena] = []
    detail_prodleni: list[UkolZmena] = []


class Souhrn(BaseModel):
    splneno: int = 0
    spadlo_do_prodleni: int = 0
    aktualne_v_prodleni: int = 0


class ZmenyOut(BaseModel):
    # skutečně použité hranice období (YYYY-MM-DD)
    od: str
    do: str
    # nejstarší den, od kdy vůbec máme data (kvůli hlášce o pokrytí); None = zatím nic
    sledovano_od: Optional[str] = None
    souhrn: Souhrn
    projekty: list[ProjektZmeny] = []
