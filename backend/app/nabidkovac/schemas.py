"""Pydantic schémata Nabídkovače. Literaly musí odpovídat enumům v models.py."""

from typing import Literal, Optional

from pydantic import BaseModel

TypNabidky = Literal["ppa", "prodej", "peak_shaving"]
StavNabidky = Literal["koncept", "data_nahrana", "zkontrolovano_oz", "spocitano", "hotovo"]
TypTechnologie = Literal["fve_panel", "invertor", "baterie", "jina"]
TypDokumentu = Literal["faktura_pdf", "spotreba_csv", "jiny"]
StavZpracovani = Literal["nahrano", "extrahovano", "chyba_extrakce", "rucne_doplneno"]


# ---- Nabídky ----
class DokumentOut(BaseModel):
    id: int
    typ: TypDokumentu
    puvodni_nazev: str
    velikost_bajtu: Optional[int] = None
    stav_zpracovani: StavZpracovani
    nahrano_at: Optional[str] = None


class ReseniOut(BaseModel):
    id: int
    typ_reseni: TypNabidky
    popis_json: dict = {}
    vybrano_zakaznikem: Optional[bool] = None


class NabidkaRadekOut(BaseModel):
    """Řádek v seznamu nabídek dané podsekce (zákazník, stav, vytvořil, datum)."""

    id: int
    typ: TypNabidky
    zakaznik_nazev: str
    stav: StavNabidky
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None


class NabidkaDetailOut(BaseModel):
    id: int
    typ: TypNabidky
    zakaznik_nazev: str
    zakaznik_adresa: str = ""
    zakaznik_gps_lat: Optional[float] = None
    zakaznik_gps_lng: Optional[float] = None
    stav: StavNabidky
    vytvoril_jmeno: Optional[str] = None
    vytvoreno_at: Optional[str] = None
    vypoctova_nastaveni_id: Optional[int] = None
    dokumenty: list[DokumentOut] = []
    reseni: list[ReseniOut] = []


class NabidkaVstup(BaseModel):
    """Založení nové nabídky. Zákazníka lze doplnit hned, nebo až v detailu."""

    typ: TypNabidky
    zakaznik_nazev: str = ""


class NabidkaUprava(BaseModel):
    zakaznik_nazev: str = ""
    zakaznik_adresa: str = ""
    zakaznik_gps_lat: Optional[float] = None
    zakaznik_gps_lng: Optional[float] = None
    stav: Optional[StavNabidky] = None


# ---- Katalog technologií ----
class TechnologieOut(BaseModel):
    id: int
    typ: TypTechnologie
    nazev: str
    model: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    ucinnost: Optional[float] = None
    dostupnost: bool = True
    raynet_id: Optional[str] = None


class TechnologieVstup(BaseModel):
    typ: TypTechnologie
    nazev: str
    model: str = ""
    vykon_kw: Optional[float] = None
    kapacita_kwh: Optional[float] = None
    cena_kc: Optional[float] = None
    ucinnost: Optional[float] = None
    dostupnost: bool = True


# ---- Výpočtová nastavení (verzovaná) ----
class VypoctovaNastaveniOut(BaseModel):
    id: int
    verze: int
    platne_od: Optional[str] = None
    koeficient_zisku: Optional[float] = None
    min_delka_kontraktu_roky: Optional[int] = None
    max_delka_kontraktu_roky: Optional[int] = None
    parametry: dict = {}
    vytvoreno_at: Optional[str] = None


class VypoctovaNastaveniVstup(BaseModel):
    """Uložení = založení NOVÉ verze (stará se nepřepisuje)."""

    koeficient_zisku: Optional[float] = None
    min_delka_kontraktu_roky: Optional[int] = None
    max_delka_kontraktu_roky: Optional[int] = None
    parametry: dict = {}
