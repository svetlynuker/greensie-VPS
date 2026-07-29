from pydantic import BaseModel


class ProjektySouhrn(BaseModel):
    """Souhrn matice (Pohled 1) — jen pro toho, kdo smí otevřít Přehled projektů."""

    aktivni: int  # nezakryté projekty
    po_terminu: int  # nehotové úkoly s termínem v minulosti
    blizi_se: int  # nehotové úkoly s termínem do 14 dnů
    bez_terminu: int  # nehotové úkoly, kterým termín nikdo nedal


class FinanceSouhrn(BaseModel):
    """Souhrn faktur (Pohled 2) — jen s právem finance."""

    neuhrazeno_kc: float  # součet částek faktur, které nejsou zaplacené ani „nefakturuje"
    neuhrazeno_pocet: int
    po_splatnosti_pocet: int
    po_splatnosti_kc: float
    nejstarsi_dni: int | None  # o kolik dní je nejstarší nezaplacená faktura po termínu


class NabidkySouhrn(BaseModel):
    """Souhrn nabídkovače — jen s právem nabidkovac."""

    celkem: int
    rozpracovane: int  # vše, co ještě není „hotovo"
    hotove: int
    nove_30_dni: int


class UkolRadek(BaseModel):
    """Jeden úkol z matice pro výpis na dashboardu."""

    projekt_id: int
    projekt_nazev: str
    ukol: str
    termin: str | None
    osoba: str
    dni: int  # kladné = tolik dní po termínu, negativní = tolik dní do termínu


class DashboardOut(BaseModel):
    """Souhrn pro úvodní stránku. Sekce, na které uživatel nemá právo,
    zůstanou None — frontend je pak vůbec nekreslí."""

    projekty: ProjektySouhrn | None = None
    finance: FinanceSouhrn | None = None
    nabidky: NabidkySouhrn | None = None
    po_terminu: list[UkolRadek] = []
    blizi_se: list[UkolRadek] = []
