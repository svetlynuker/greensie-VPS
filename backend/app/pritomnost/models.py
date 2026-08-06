from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


def _ted():
    return datetime.now(timezone.utc)


class Pritomnost(Base):
    """Kdo má právě otevřenou kterou věc („kdo tu je“).

    Jeden řádek na dvojici (uživatel, entita) — obnovuje se každým tikem
    z prohlížeče. Přítomný je ten, kdo tikl v posledních `OKNO_S` sekundách
    (viz `sluzba.py`), takže zavřená záložka zmizí ze seznamu sama a nic se
    nemusí mazat. Kdyby se přítomnost místo toho zakládala a rušila párem
    „přišel/odešel“, každý spadlý prohlížeč by tu nechal ducha, který v appce
    věčně někoho edituje.

    `entita_id` je text, ne číslo, aby stejná tabulka unesla i klíče, které
    číslem nejsou (buňka matice = „projektId||sloupecId“). Prázdné = celý
    modul. `pole` je nepovinné upřesnění, co má člověk rozevřené uvnitř
    entity — z toho se v UI skládá „Petr edituje Kolaudace“.
    """

    __tablename__ = "pritomnost"
    __table_args__ = (
        UniqueConstraint("uzivatel_id", "entita_typ", "entita_id", name="uq_pritomnost_kdo_kde"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uzivatel_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entita_typ = Column(String, nullable=False, index=True)
    entita_id = Column(String, nullable=False, default="", server_default="")
    pole = Column(String, nullable=False, default="", server_default="")
    kdy = Column(DateTime(timezone=True), nullable=False, default=_ted, index=True)
