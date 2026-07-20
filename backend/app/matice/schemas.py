from typing import Literal, Optional

from pydantic import BaseModel


class UkolOut(BaseModel):
    sloupec_id: int
    label: str
    nazev: str


class FazeOut(BaseModel):
    todo: str
    ukoly: list[UkolOut]


class ProjektOut(BaseModel):
    id: int
    nazev: str
    url: str
    termin: Optional[str] = None
    rucni: bool
    skryty: bool = False


class ZobrazeniVstup(BaseModel):
    skryty: bool


class BunkaOut(BaseModel):
    stav: Optional[str] = None
    termin: Optional[str] = None
    osoba: str = ""
    poznamka: str = ""
    url: str = ""


class BarvyOut(BaseModel):
    zelena_od: Optional[int] = None
    zelena_do: Optional[int] = None
    zluta_od: Optional[int] = None
    zluta_do: Optional[int] = None
    oranzova_od: Optional[int] = None
    oranzova_do: Optional[int] = None
    cervena_od: Optional[int] = None
    cervena_do: Optional[int] = None


class MaticeOut(BaseModel):
    muze_editovat: bool
    faze: list[FazeOut]
    projekty: list[ProjektOut]
    bunky: dict[str, BunkaOut]  # klíč "projektId||sloupecId"
    barvy: BarvyOut


class BunkaVstup(BaseModel):
    projekt_id: int
    sloupec_id: int
    stav: Optional[Literal["done", "todo"]] = None
    termin: Optional[str] = None  # "YYYY-MM-DD" nebo prázdné
    osoba: str = ""
    poznamka: str = ""


class ProjektVstup(BaseModel):
    nazev: str
    termin: Optional[str] = None


class SloupecVstup(BaseModel):
    faze: str = ""
    nazev: str


class FreeloVstup(BaseModel):
    rezim: Literal["prepsat", "bez_prepsani"]


class FreeloVysledek(BaseModel):
    projektu: int
    sloupcu: int
    bunek_novych: int
    bunek_prepsanych: int


class SyncNastaveniOut(BaseModel):
    auto_zapnuto: bool
    interval_min: int
    sync_stav: bool
    zapis_stav_do_freela: bool
    sync_nove_ukoly: bool
    sync_nove_projekty: bool
    sync_terminy: bool
    sync_osoby: bool
    posledni_beh: Optional[str] = None  # ISO datetime, nebo None když ještě neběželo
    posledni_vysledek: str = ""


class SyncNastaveniVstup(BaseModel):
    auto_zapnuto: bool
    interval_min: int
    sync_stav: bool
    zapis_stav_do_freela: bool
    sync_nove_ukoly: bool
    sync_nove_projekty: bool
    sync_terminy: bool
    sync_osoby: bool
