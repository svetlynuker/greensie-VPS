from sqlalchemy import Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.types import JSON

from app.database import Base


class UzivatelskeNastaveni(Base):
    """Uživatelské preference (klíč → JSON hodnota), jeden řádek na dvojici
    (uživatel, klíč). Sem patří nastavení pohledů (skryté fáze/úkoly, pořadí)
    i vzhled (velikost textu, tmavý režim), aby se přenášely mezi zařízeními.
    """

    __tablename__ = "uzivatelska_nastaveni"
    __table_args__ = (
        UniqueConstraint("uzivatel_id", "klic", name="uq_nastaveni_uzivatel_klic"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uzivatel_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="CASCADE"), nullable=False, index=True
    )
    klic = Column(String, nullable=False)
    hodnota = Column(JSON, nullable=False)
