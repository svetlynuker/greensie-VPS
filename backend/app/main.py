from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.auth import models  # noqa: F401 - registrace modelů před create_all
from app.auth.routes import router as auth_router
from app.finance import models as finance_models  # noqa: F401 - registrace modelů
from app.finance.routes import router as finance_router
from app.matice import models as matice_models  # noqa: F401 - registrace modelů
from app.matice.routes import router as matice_router
from app.nabidkovac import models as nabidkovac_models  # noqa: F401 - registrace modelů
from app.nabidkovac.routes import router as nabidkovac_router
from app.nastaveni import models as nastaveni_models  # noqa: F401 - registrace modelů
from app.nastaveni.routes import router as nastaveni_router
from app.admin.routes import router as admin_router
from app.database import Base, engine

Base.metadata.create_all(bind=engine)


def _lehka_migrace():
    """Doplní sloupce, které create_all neumí přidat do už existujících tabulek."""
    sloupce_pred = {c["name"] for c in inspect(engine).get_columns("uzivatele")}
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE uzivatele ADD COLUMN IF NOT EXISTS skupina_id INTEGER "
                "REFERENCES skupiny(id) ON DELETE SET NULL"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE uzivatele ADD COLUMN IF NOT EXISTS je_admin BOOLEAN "
                "NOT NULL DEFAULT false"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE uzivatele ADD COLUMN IF NOT EXISTS musi_zmenit_heslo BOOLEAN "
                "NOT NULL DEFAULT false"
            )
        )
        # přechod z původní role: kdo měl role='admin', stává se supersprávcem,
        # a sloupec role přestává být povinný (nově se už nepoužívá).
        if "role" in sloupce_pred:
            conn.execute(text("UPDATE uzivatele SET je_admin = true WHERE role = 'admin'"))
            conn.execute(text("ALTER TABLE uzivatele ALTER COLUMN role DROP NOT NULL"))

        # Vlastní sloupce katalogu: hodnoty se drží v Technologie.extra (JSONB).
        # create_all nepřidá sloupec do už existující tabulky → doplníme ručně.
        conn.execute(
            text("ALTER TABLE technologie ADD COLUMN IF NOT EXISTS extra JSONB NOT NULL DEFAULT '{}'")
        )


_lehka_migrace()


def _seed_sazby():
    """Naplní `sazby_distributoru` výchozími daty ČEZ 2026 (METODIKA kap. 3.1).

    Idempotentní – vloží jen chybějící řádky, ruční úpravy přes admin nepřepíše.
    EG.D, PRE a sazby 2027 se doplní přes admin (kap. 6–7).
    """
    from app.database import SessionLocal
    from app.nabidkovac.seed import seed_sazby

    db = SessionLocal()
    try:
        seed_sazby(db)
    finally:
        db.close()


_seed_sazby()

app = FastAPI(title="Greensie")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # lokální vývoj
        "https://167-235-254-188.sslip.io",  # produkce
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(matice_router)
app.include_router(finance_router)
app.include_router(nabidkovac_router)
app.include_router(nastaveni_router)
app.include_router(admin_router)


@app.get("/health")
def health():
    return {"stav": "ok"}
