from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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
from app.logy import models as logy_models  # noqa: F401 - registrace modelů
from app.logy.routes import router as logy_router
from app.logy.middleware import LogovaciMiddleware
from app.zmeny import models as zmeny_models  # noqa: F401 - registrace modelů
from app.zmeny.routes import router as zmeny_router
from app.admin.routes import router as admin_router
from app.dashboard.routes import router as dashboard_router
from app.konektor import models as konektor_models  # noqa: F401 - registrace modelů
from app.konektor.routes import router as konektor_router
from app.crm import models as crm_models  # noqa: F401 - registrace modelů
from app.crm.routes import router as crm_router
from app.manual.routes import router as manual_router
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
        # Příznak modelového (nezávazného) odhadu sazby – pro strukturu nova_2027.
        conn.execute(
            text(
                "ALTER TABLE sazby_distributoru ADD COLUMN IF NOT EXISTS "
                "je_modelovy_odhad BOOLEAN NOT NULL DEFAULT false"
            )
        )

        # Obousměrná synchronizace stavu: zápis stavu z tabulky zpět do Freela.
        # Tabulka nastaveni_synchronizace už mohla vzniknout dřív (bez tohoto
        # sloupce) → create_all ho nedoplní, přidáme ho ručně (idempotentní).
        conn.execute(
            text(
                "ALTER TABLE nastaveni_synchronizace ADD COLUMN IF NOT EXISTS "
                "zapis_stav_do_freela BOOLEAN NOT NULL DEFAULT true"
            )
        )

        # Duplicitní profily spotřeby (audit 16. 7. 2026, SP-2): dřív se dva
        # nahrané soubory tiše sečetly. Před unique indexem se existující
        # duplicity musí smazat („poslední vyhrává“ = řádek s vyšším id),
        # jinak by start appky spadl. Obojí je idempotentní.
        conn.execute(
            text(
                "DELETE FROM spotreba_profil a USING spotreba_profil b "
                "WHERE a.nabidka_id = b.nabidka_id AND a.cas = b.cas AND a.id < b.id"
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_spotreba_profil_nabidka_cas "
                "ON spotreba_profil (nabidka_id, cas)"
            )
        )

        # Konektor: hierarchie zákazník → obch. případ → nabídka/objednávka.
        # Nové kódy vlastních polí – create_all je do existující tabulky nepřidá.
        for sloupec in (
            "raynet_deal_drive_field",
            "raynet_deal_drive_field2",
            "raynet_offer_drive_field",
            "raynet_order_drive_field",
            "raynet_webhook_token",
            "google_root_folder_id",
            "google_vzor_folder_id",
            "google_dms_zdroj_folder_id",
        ):
            conn.execute(
                text(
                    f"ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS {sloupec} "
                    "VARCHAR NOT NULL DEFAULT ''"
                )
            )
        # názvy kontejnerů ve vzoru – s nenulovými výchozími hodnotami
        for sloupec, vychozi in (
            ("kontejner_op", "1. Obchodní Případy"),
            ("kontejner_nabidky", "1. nabídky"),
            ("kontejner_objednavky", "5. objednávky"),
        ):
            conn.execute(
                text(
                    f"ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS {sloupec} "
                    f"VARCHAR NOT NULL DEFAULT '{vychozi}'"
                )
            )
        # ID kontejnerů uvnitř složek klientů/OP (odolnost vůči přejmenování)
        conn.execute(
            text("ALTER TABLE konektor_entity_folder ADD COLUMN IF NOT EXISTS kontejnery JSONB")
        )

        # Proklik z Přehledu projektů na složku dokumentů („6. projekty" pod OP).
        # create_all nové sloupce do existující tabulky `projekty` nepřidá.
        conn.execute(
            text("ALTER TABLE projekty ADD COLUMN IF NOT EXISTS disk_url "
                 "VARCHAR NOT NULL DEFAULT ''")
        )
        conn.execute(
            text("ALTER TABLE projekty ADD COLUMN IF NOT EXISTS disk_rucni "
                 "BOOLEAN NOT NULL DEFAULT false")
        )
        conn.execute(
            text("ALTER TABLE projekty ADD COLUMN IF NOT EXISTS raynet_deal_id BIGINT")
        )
        # automatický sken Dokumentů (RN → Disk)
        conn.execute(
            text("ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS dms_sken_zapnuto "
                 "BOOLEAN NOT NULL DEFAULT true")
        )
        conn.execute(
            text("ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS dms_sken_casy "
                 "VARCHAR NOT NULL DEFAULT '08:00,20:00'")
        )
        conn.execute(
            text("ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS dms_sken_posledni "
                 "TIMESTAMPTZ")
        )
        conn.execute(
            text("ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS dms_presun_zapnuto "
                 "BOOLEAN NOT NULL DEFAULT false")
        )
        conn.execute(
            text("ALTER TABLE konektor_nastaveni ADD COLUMN IF NOT EXISTS dms_baseline JSONB")
        )

        # CRM: hodnoty vlastních (admin definovaných) polí. Tabulky
        # `crm_zakaznici` / `crm_obchodni_pripady` mohly vzniknout ještě bez
        # tohoto sloupce – create_all ho do existující tabulky nepřidá.
        for tabulka in ("crm_zakaznici", "crm_obchodni_pripady"):
            conn.execute(
                text(
                    f"ALTER TABLE {tabulka} ADD COLUMN IF NOT EXISTS extra "
                    "JSONB NOT NULL DEFAULT '{}'::jsonb"
                )
            )

        # CRM: počátek číselné řady. Tabulka `crm_ciselne_rady` mohla vzniknout
        # ještě bez tohoto sloupce (create_all ho do existující tabulky nepřidá).
        conn.execute(
            text(
                "ALTER TABLE crm_ciselne_rady ADD COLUMN IF NOT EXISTS pocatek "
                "INTEGER NOT NULL DEFAULT 1"
            )
        )

        # CRM: navázání nabídky na obchodní případ + viditelné číslo nabídky.
        # `nabidky` je existující tabulka, takže create_all nové sloupce nepřidá.
        # Cizí klíč zakládáme až po vytvoření CRM tabulek (create_all výš), a jen
        # pokud ještě není – opakovaný start by na duplicitním klíči spadl.
        conn.execute(text("ALTER TABLE nabidky ADD COLUMN IF NOT EXISTS cislo VARCHAR"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_nabidky_cislo ON nabidky (cislo) "
                "WHERE cislo IS NOT NULL"
            )
        )
        conn.execute(
            text("ALTER TABLE nabidky ADD COLUMN IF NOT EXISTS obchodni_pripad_id INTEGER")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_nabidky_obchodni_pripad_id "
                "ON nabidky (obchodni_pripad_id)"
            )
        )
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conname = 'fk_nabidky_obchodni_pripad') THEN "
                "ALTER TABLE nabidky ADD CONSTRAINT fk_nabidky_obchodni_pripad "
                "FOREIGN KEY (obchodni_pripad_id) REFERENCES crm_obchodni_pripady(id) "
                "ON DELETE SET NULL; END IF; END $$;"
            )
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


def _seed_baterie():
    """Naplní katalog `technologie` bateriemi z ceníku BESS (baterie_seed.py).

    Idempotentní – vloží jen chybějící produkty a definice sloupců, ruční
    úpravy cen/dostupnosti přes admin katalog nepřepíše.
    """
    from app.database import SessionLocal
    from app.nabidkovac.baterie_seed import seed_baterie

    db = SessionLocal()
    try:
        seed_baterie(db)
    finally:
        db.close()


def _seed_spotove_ceny():
    """Naseeduje spotové ceny z přiložených datových souborů (spot_ceny.py).

    Idempotentní a offline – produkce nechodí na internet, ceny jsou v repu
    jako `app/nabidkovac/data/spot_dam_cz_<rok>.csv.gz`. Když už jsou ceny roku
    v DB v plném počtu, seed se přeskočí (35 tis. řádků na rok by zdržovalo
    každý restart). Další rok se přidává skriptem `scripts/import_spot_ceny.py`.
    """
    from app.database import SessionLocal
    from app.nabidkovac.spot_ceny import seed_z_datovych_souboru

    db = SessionLocal()
    try:
        seed_z_datovych_souboru(db)
    finally:
        db.close()


def _seed_crm():
    """Naseeduje stavy pipeline a číselné řady CRM (idempotentní).

    Bez stavů by kanban neměl sloupce a nový případ by neměl kam padnout;
    bez řad by nešlo vydat viditelné ID. Doplňuje jen chybějící – přejmenované
    či smazané stavy se nevracejí, jinak by se změny vedení po každém restartu
    přepisovaly zpátky.
    """
    from app.crm.ciselne_rady import seed_rady
    from app.crm.stavy import seed_stavy
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed_stavy(db)
        seed_rady(db)
    finally:
        db.close()


_seed_sazby()
_seed_baterie()
_seed_spotove_ceny()
_seed_crm()

app = FastAPI(title="Greensie")

# Komprese odpovědí: většina API vrací pár kB (nekomprimuje se), ale průběh
# peak shavingu posílá celoroční 15min řady (~1 MB JSON) – gzip z toho udělá
# desetinu. Přidáno jako nejvnitřnější vrstva, aby logování i CORS zůstaly nad ním.
app.add_middleware(GZipMiddleware, minimum_size=4096)

# Logovací middleware přidáváme PŘED CORS, aby CORS zůstal nejkrajnější
# vrstvou (jinak by se hlavičky nemusely dostat na chybové odpovědi).
app.add_middleware(LogovaciMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # lokální vývoj
        "https://app.greensie.cz",  # produkce – hlavní adresa
        "https://167-235-254-188.sslip.io",  # produkce – původní adresa
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
app.include_router(logy_router)
app.include_router(zmeny_router)
app.include_router(admin_router)
app.include_router(konektor_router)
app.include_router(crm_router)
app.include_router(manual_router)
app.include_router(dashboard_router)


@app.on_event("startup")
def _spust_planovac_synchronizace():
    # plánovaná automatická synchronizace z Freela (vlákno na pozadí)
    from app.matice.scheduler import spust_planovac

    spust_planovac()


@app.on_event("shutdown")
def _zastav_planovac_synchronizace():
    from app.matice.scheduler import zastav_planovac

    zastav_planovac()


@app.on_event("startup")
def _spust_konektor_worker():
    # worker fronty úloh konektoru (Raynet ↔ Google Disk)
    from app.konektor.scheduler import spust_worker

    spust_worker()


@app.on_event("shutdown")
def _zastav_konektor_worker():
    from app.konektor.scheduler import zastav_worker

    zastav_worker()


@app.get("/health")
def health():
    return {"stav": "ok"}
