from sqlalchemy import Column, Date, ForeignKey, Integer, String, UniqueConstraint

from app.database import Base


class StavSnapshot(Base):
    """Denní snímek stavu jedné buňky matice (fotka pro Přehled změn).

    Jednou denně server uloží stav (hotovo/nehotovo) a termín každé buňky,
    která má vyplněný stav. Porovnáním dvou snímků (nebo snímku a živého stavu)
    se pak spočítá, co se za období pohnulo – co se splnilo a co spadlo do
    prodlení. První uložený den = „základna“, se kterou porovnává volba
    „od začátku“.

    Sledujeme JEN dimenzi hotovo/nehotovo + termín (kvůli dopočtu prodlení).
    Poznámky/osoby se sem záměrně neukládají.
    """

    __tablename__ = "stav_snapshot"
    __table_args__ = (
        UniqueConstraint("den", "bunka_id", name="uq_snapshot_den_bunka"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # den snímku (lokální datum serveru); index kvůli výběru fotky ke dni
    den = Column(Date, nullable=False, index=True)
    bunka_id = Column(
        Integer, ForeignKey("bunky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # kopie stavu buňky v ten den: "done" | "todo" | None
    stav = Column(String, nullable=True)
    # kopie termínu v ten den (kvůli dopočtu prodlení k danému dni)
    termin = Column(Date, nullable=True)
