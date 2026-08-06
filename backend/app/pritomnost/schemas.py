from pydantic import BaseModel


class TikVstup(BaseModel):
    entita_typ: str
    entita_id: str = ""
    # co má člověk rozevřené uvnitř entity (nepovinné, jen pro popisek v UI)
    pole: str = ""


class PritomnyOut(BaseModel):
    uzivatel_id: int
    jmeno: str
    pole: str = ""
    ja: bool = False


class TikOut(BaseModel):
    pritomni: list[PritomnyOut]
    # Podpis stavu modulu. Změní-li se proti tomu, co klient drží, načte si
    # data znovu — tím je vyřešená i druhá polovina synchronizace (viz
    # `razitka.py`), aniž by musel běžet druhý dotaz.
    razitko: str = ""
