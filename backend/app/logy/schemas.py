from datetime import datetime

from pydantic import BaseModel


class LogOut(BaseModel):
    """Jeden řádek logu ve tvaru, který čte frontend."""

    id: int
    cas: datetime
    uzivatel_id: int | None = None
    uzivatel_email: str | None = None
    metoda: str | None = None
    cesta: str | None = None
    status_kod: int | None = None
    doba_ms: int | None = None
    typ: str
    popis: str | None = None
    detail: str | None = None

    class Config:
        from_attributes = True


class SmazaniVysledek(BaseModel):
    smazano: int
