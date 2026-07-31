from typing import Literal, Optional

from pydantic import BaseModel

# Musí odpovídat STAVY_FAKTURY v models.py.
StavFaktury = Literal["potreba_vystavit", "vystaveno", "zaplaceno", "nefakturuje"]


class FakturaOut(BaseModel):
    id: int
    poradi: int
    stav: StavFaktury
    castka: Optional[float] = None
    termin: Optional[str] = None  # "YYYY-MM-DD"
    poznamka: str = ""
    variabilni_symbol: Optional[str] = None
    pohoda_potvrzeno: bool = False
    pohoda_datum_vystaveni: Optional[str] = None
    pohoda_datum_zaplaceni: Optional[str] = None
    upraveno_rucne: bool = False


class ProjektFinanceOut(BaseModel):
    id: int
    nazev: str
    url: str
    termin: Optional[str] = None
    faktury: list[FakturaOut]


class ObjednavkaFinanceOut(BaseModel):
    """Řádek Přehledu financí za CRM objednávku (CRM-09).

    Vedle Freelo projektů, ne místo nich: staré zakázky dojíždějí ve Freelu
    a nové vznikají v CRM, takže obojí musí být na jedné obrazovce vidět
    zároveň (jinak by finance vypadaly jako propad, viz CRM-45).
    """

    id: int
    cislo: str
    nazev: str = ""
    zakaznik_nazev: str = ""
    cena_kc: Optional[float] = None
    stav_nazev: str = ""
    faktury: list[FakturaOut]


class FinanceOut(BaseModel):
    muze_editovat: bool  # smí editovat finance (= má právo "finance")
    max_faktur: int  # nejvyšší počet faktur napříč projekty (šířka tabulky)
    projekty: list[ProjektFinanceOut]
    # CRM objednávky se svými fakturami. Editují se na kartě objednávky
    # v CRM, tady jsou jen ke čtení – jinak by tatáž faktura šla měnit na dvou
    # místech s jinými právy.
    objednavky: list[ObjednavkaFinanceOut] = []
    max_faktur_objednavek: int = 0


class FakturaVstup(BaseModel):
    """Editace jedné faktury. Všechna pole nepovinná kromě stavu."""

    stav: StavFaktury
    castka: Optional[float] = None
    termin: Optional[str] = None  # "YYYY-MM-DD" nebo prázdné
    poznamka: str = ""
    variabilni_symbol: Optional[str] = None


class PohodaVysledek(BaseModel):
    """Výsledek synchronizace s Pohodou (zatím napojení není aktivní)."""

    aktivni: bool  # False = Pohoda ještě není nakonfigurovaná/napojená
    zprava: str
    sparovanych: int = 0
