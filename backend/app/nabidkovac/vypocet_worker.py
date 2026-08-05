"""Dlouhé výpočty nabídkovače na pozadí – **samostatný proces**, ne vlákno ve webu.

Prohledání celého katalogu baterií (84 produktů × 1–5 kusů) nad ročním 15min
diagramem je řádově minuty čistého CPU. Uvnitř uvicornu by to appku dotlačilo
k 502 – stejná zkušenost jako s konektorem a se stahováním pošty, a stejné
rozhodnutí: vlastní systemd služba (`greensie-vypocty.service`).

Praktický důsledek, se kterým se počítá: appka a výpočty se restartují
nezávisle. Když worker neběží, appka funguje dál — jen se zařazené výpočty
neodbaví a v panelu je vidět, že úloha čeká (ne tiché kolečko).

---- Jak se spouští --------------------------------------------------------
    venv/bin/python -m app.nabidkovac.vypocet_worker   # ručně, pro ladění
    systemctl start greensie-vypocty                    # na produkci

---- Proč jedna úloha po druhé --------------------------------------------
Výpočet je čistě CPU-bound a server má i další práci (web, pošta, konektor).
Paralelizace by jen soutěžila o tatáž jádra a zpomalila i appku, takže se úlohy
berou sériově. Fronta v DB je pojistka proti dvěma instancím: úloha se přebírá
podmíněným UPDATE, který uspěje jen jednomu.

---- Nic nespadne tiše -----------------------------------------------------
Chyba jedné úlohy nesmí shodit smyčku ani zůstat nezaznamenaná: úloha se označí
jako `chyba` s textem, který uvidí obchodník v panelu, a worker jede dál.
"""

import logging
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime, timezone

from sqlalchemy import update

from app.database import SessionLocal
from app.nabidkovac.models import NavrhovaneReseni, VypocetFronta

# Jak často se kouká do fronty, když je prázdná. Výpočet zadává člověk
# kliknutím, takže dvě sekundy jsou z jeho pohledu „hned" a přitom to je
# zanedbatelný dotaz.
INTERVAL_PRAZDNO_S = float(os.environ.get("VYPOCTY_INTERVAL_S", "2"))
# Po startu chvíli počkat – při restartu serveru se rozjíždí i databáze.
START_PRODLEVA_S = float(os.environ.get("VYPOCTY_START_PRODLEVA_S", "5"))
# Kolikrát se úloha zkusí, než se označí jako chyba. Výpočet je
# deterministický, takže opakovat ho nemá moc smysl – jednička je tu pro
# případ, že spadne databázové spojení.
MAX_POKUSU = int(os.environ.get("VYPOCTY_MAX_POKUSU", "2"))
# Jak často se do DB propisuje pokrok. Každá konfigurace by znamenala stovky
# UPDATE za minutu; dvě sekundy stačí, aby se ukazatel v panelu hýbal.
INTERVAL_POKROKU_S = 2.0

_stop = threading.Event()
_log = logging.getLogger("greensie.vypocty")


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def _prevezmi_ulohu(db):
    """Vezme nejstarší čekající úlohu a označí ji jako běžící.

    Podmíněný UPDATE (`stav == "ceka"`) je zámek: kdyby běžely dvě instance
    workeru, druhá dostane 0 změněných řádků a úlohu nepřevezme. Levnější
    a spolehlivější než `SELECT ... FOR UPDATE` s ruční transakcí.
    """
    uloha = (
        db.query(VypocetFronta)
        .filter(VypocetFronta.stav == "ceka")
        .order_by(VypocetFronta.id)
        .first()
    )
    if uloha is None:
        return None
    vysledek = db.execute(
        update(VypocetFronta)
        .where(VypocetFronta.id == uloha.id, VypocetFronta.stav == "ceka")
        .values(
            stav="bezi",
            zahajeno_at=_ted(),
            pokusu=VypocetFronta.pokusu + 1,
            zprava="Spouštím výpočet…",
        )
    )
    db.commit()
    if vysledek.rowcount != 1:
        return None  # vzal ji někdo jiný
    db.refresh(uloha)
    return uloha


def _odbav_ppa_bess_katalog(db, uloha: VypocetFronta) -> None:
    """Prohledá katalog baterií a uloží výsledek jako `navrhovana_reseni`.

    Vstup se skládá stejně jako v synchronním endpointu – proto se sem tahá
    `routes.sestav_vstup_ppa_bess`, aby se logika (parametry z nastavení, sazby
    ze sazebníku, GPS, validace profilu) neduplikovala. Kdyby si ji worker
    skládal sám, počítal by po změně nastavení s jinými čísly než appka a nikdo
    by si toho nevšiml.
    """
    from app.nabidkovac import ppa_bess
    from app.nabidkovac.routes import sestav_vstup_ppa_bess
    from app.nabidkovac.schemas import PpaBessVstup

    vstup_schema = PpaBessVstup(**(uloha.vstup_json or {}))
    vstup_calc, upozorneni, nastaveni, sazba = sestav_vstup_ppa_bess(
        db, uloha.nabidka_id, vstup_schema
    )

    posledni_zapis = [0.0]

    def hlaseni(hotovo: int, celkem: int, zprava: str) -> None:
        """Propíše pokrok do DB, ale ne častěji než `INTERVAL_POKROKU_S`."""
        if _stop.is_set():
            # Úloha se dokončí, ale rychleji: `prohledej_katalog` na tohle
            # nereaguje sama, takže se aspoň přestane psát do DB.
            return
        nyni = time.monotonic()
        if nyni - posledni_zapis[0] < INTERVAL_POKROKU_S:
            return
        posledni_zapis[0] = nyni
        try:
            db.execute(
                update(VypocetFronta)
                .where(VypocetFronta.id == uloha.id)
                .values(hotovo_variant=hotovo, celkem_variant=celkem, zprava=zprava[:200])
            )
            db.commit()
        except Exception:  # pragma: no cover – pokrok nesmí shodit výpočet
            db.rollback()

    vysledek = ppa_bess.prohledej_katalog(vstup_calc, hlaseni=hlaseni)
    plny = vysledek.get("vysledek")
    if plny is None:
        duvod = "; ".join(vysledek.get("upozorneni") or []) or "Katalog nedal platný výsledek."
        raise RuntimeError(duvod)

    # Upozornění z profilu (oříznutí na poslední rok, chybějící GPS…) patří před
    # ta z výpočtu – stejné pořadí jako u synchronního endpointu.
    plny["upozorneni"] = list(upozorneni) + list(plny.get("upozorneni") or [])
    plny["vstup"] = {
        **(plny.get("vstup") or {}),
        "distributor": vstup_schema.distributor,
        "napetova_hladina": vstup_schema.napetova_hladina,
        "sazba_2027_id": sazba.id if sazba is not None else None,
        "z_katalogu_na_pozadi": True,
    }

    reseni = NavrhovaneReseni(
        nabidka_id=uloha.nabidka_id, typ_reseni="ppa_bess", popis_json=plny
    )
    db.add(reseni)
    db.flush()

    nabidka = reseni.nabidka if hasattr(reseni, "nabidka") else None
    if nabidka is None:
        from app.nabidkovac.models import Nabidka

        nabidka = db.get(Nabidka, uloha.nabidka_id)
    if nabidka is not None:
        if nastaveni is not None:
            nabidka.vypoctova_nastaveni_id = nastaveni.id
        if nabidka.stav in ("koncept", "data_nahrana", "zkontrolovano_oz"):
            nabidka.stav = "spocitano"

    uloha.stav = "hotovo"
    uloha.reseni_id = reseni.id
    uloha.vysledek_json = {
        "prohledano_konfiguraci": vysledek.get("prohledano"),
        "varianty": vysledek.get("varianty"),
    }
    uloha.hotovo_variant = int(vysledek.get("prohledano") or 0)
    uloha.zprava = "Hotovo"
    uloha.dokonceno_at = _ted()
    db.commit()
    _log.info(
        "úloha %s hotová: prohledáno %s konfigurací, řešení %s",
        uloha.id, vysledek.get("prohledano"), reseni.id,
    )


# Jaký typ úlohy umí kdo odbavit. Fronta je záměrně obecná, ať se do ní dají
# přidat další dlouhé výpočty bez nové tabulky a nové služby.
ODBAVOVACE = {"ppa_bess_katalog": _odbav_ppa_bess_katalog}


def _krok(db) -> bool:
    """Odbaví jednu úlohu. Vrací True, když se něco dělalo."""
    uloha = _prevezmi_ulohu(db)
    if uloha is None:
        return False

    odbavovac = ODBAVOVACE.get(uloha.typ)
    if odbavovac is None:
        uloha.stav = "chyba"
        uloha.chyba = f"Neznámý typ úlohy: {uloha.typ}"
        uloha.dokonceno_at = _ted()
        db.commit()
        _log.error("úloha %s má neznámý typ %s", uloha.id, uloha.typ)
        return True

    _log.info("beru úlohu %s (%s) pro nabídku %s", uloha.id, uloha.typ, uloha.nabidka_id)
    zacatek = time.monotonic()
    try:
        odbavovac(db, uloha)
        _log.info("úloha %s trvala %.1f s", uloha.id, time.monotonic() - zacatek)
    except Exception as e:
        db.rollback()
        # Text chyby jde do panelu, takže musí být čitelný pro obchodníka;
        # celý traceback zůstane v logu služby.
        _log.error("úloha %s spadla: %s\n%s", uloha.id, e, traceback.format_exc())
        try:
            db.refresh(uloha)
            znovu = uloha.pokusu < MAX_POKUSU
            uloha.stav = "ceka" if znovu else "chyba"
            uloha.chyba = str(e)[:2000]
            uloha.zprava = "Zkusím to znovu…" if znovu else "Výpočet se nepovedl"
            if not znovu:
                uloha.dokonceno_at = _ted()
            db.commit()
        except Exception:  # pragma: no cover
            db.rollback()
    return True


def _smycka() -> None:
    _log.info("worker výpočtů startuje")
    if START_PRODLEVA_S > 0:
        _stop.wait(START_PRODLEVA_S)
    while not _stop.is_set():
        db = SessionLocal()
        try:
            delalo_se = _krok(db)
        except Exception:  # pragma: no cover – smyčka nesmí spadnout
            _log.error("chyba ve smyčce:\n%s", traceback.format_exc())
            delalo_se = False
        finally:
            db.close()
        if not delalo_se:
            _stop.wait(INTERVAL_PRAZDNO_S)
    _log.info("worker výpočtů končí")


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("VYPOCTY_LOG_UROVEN", "INFO").upper(),
        # systemd si čas loguje sám, takže tady jen úroveň a text.
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    def zastav(_signum, _rama):
        _log.info("dostal jsem signál, dokončím rozdělané a skončím")
        _stop.set()

    # Bez tohohle by `systemctl stop` čekal na timeout a killoval proces.
    signal.signal(signal.SIGTERM, zastav)
    signal.signal(signal.SIGINT, zastav)

    # VŠECHNY modely se musí zaregistrovat, ne jen ty, které worker sám používá.
    # SQLAlchemy inicializuje mappery jako celek: `Nabidka` se odkazuje na
    # `User`, `Objednavka` z CRM na `Faktura` z financí, takže bez jejich
    # importu spadne úplně první dotaz na „name 'Faktura' is not defined" – a to
    # i u dotazu na frontu, který s fakturami nemá nic společného. Web proces
    # tenhle problém nemá, protože `app.main` importuje všechno.
    from app.auth import models as _auth_models  # noqa: F401
    from app.crm import models as _crm_models  # noqa: F401
    from app.finance import models as _finance_models  # noqa: F401
    from app.konektor import models as _konektor_models  # noqa: F401
    from app.logy import models as _logy_models  # noqa: F401
    from app.matice import models as _matice_models  # noqa: F401
    from app.nabidkovac import models as _nabidkovac_models  # noqa: F401
    from app.nastaveni import models as _nastaveni_models  # noqa: F401
    from app.zmeny import models as _zmeny_models  # noqa: F401

    _smycka()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
