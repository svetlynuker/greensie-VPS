import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, ForeignKey, Integer, create_engine
from sqlalchemy.orm import declarative_base, declared_attr, sessionmaker

# .env leží v kořeni repa (backend/app/database.py -> backend/app -> backend -> kořen)
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class ZmenaMixin:
    """Kdo a kdy záznam naposledy změnil — pro automatické ukládání vstupů.

    Proč to nestačí odvodit z `aktualizovano_at`, které některé tabulky mají:
    ten se hýbe při jakékoli změně a NEŘÍKÁ KDO. Hláška „hodnotu mezitím změnil
    Petr“ se z něj postavit nedá, a bez jména se člověk nemá jak rozhodnout,
    čí verze platí.

    `verze` je jen informativní. Kolize se hlídá porovnáním hodnoty (viz
    `crm/pole_zaznamu.py`), protože verze roste i při změně JINÉHO pole — podle
    ní by appka hlásila kolizi u věcí, které si vzájemně nevadí.

    Mixin sedí tady vedle `Base`, ne v `crm/models.py`, protože ho používá i
    nabídka (`nabidkovac/models.py`) — a nabídkovač s CRM se navzájem
    neimportují na úrovni modulu.
    """

    zmeneno_at = Column(DateTime(timezone=True), nullable=True, index=True)
    verze = Column(Integer, nullable=False, default=0, server_default="0")

    @declared_attr
    def zmenil_id(cls):  # noqa: N805 - SQLAlchemy mixin
        # Cizí klíč musí být v `declared_attr`, jinak by ho SQLAlchemy chtěl
        # sdílet mezi tabulkami a spadl by při druhém použití mixinu.
        return Column(
            Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
