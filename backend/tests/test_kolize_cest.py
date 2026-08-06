"""Hlídání kolizí cest v API.

Vzniklo z reálné chyby (31. 7. 2026): šablony e-mailů dostaly `/crm/sablony`,
jenže tu už měly ŠABLONY PROJEKTOVÝCH KROKŮ. Oba moduly visí na stejném
routeru, takže FastAPI tiše nechalo vyhrát tu registrovanou dřív a projektové
šablony přestaly fungovat. Nic nespadlo, nic nevypsalo — chyba se pozná jen
tím, že obrazovka vrací cizí data.

Stejná past sklapla u CRM-46 (`/crm/odberna-mista/{entita}/{zaznam_id}` vs.
`/crm/odberna-mista/{id}/diagramy`), takže je to opakovaná chyba, ne náhoda.

Routery se skládají ručně, ne přes `app.main`: import mainu spustí
`create_all`, který proti testovací SQLite spadne na JSONB. Pořadí je stejné
jako v `main.py` — na něm kolize závisí.
"""

import importlib
from collections import Counter

import pytest

# Pořadí odpovídá include_router v app/main.py. Nové moduly sem patří taky,
# jinak je test přestane hlídat.
MODULY_ROUTERU = [
    "app.auth.routes",
    "app.admin.routes",
    "app.nastaveni.routes",
    "app.matice.routes",
    "app.pritomnost.routes",
    "app.finance.routes",
    "app.nabidkovac.routes",
    "app.crm.routes",
    "app.crm.routes_realizace",
    "app.crm.routes_pole",
    "app.crm.email_routes",
    "app.konektor.routes",
    "app.konektor.disk_routes",
    "app.logy.routes",
    "app.manual.routes",
    "app.zmeny.routes",
    "app.dashboard.routes",
]


def _aplikace():
    from fastapi import FastAPI

    app = FastAPI()
    for nazev in MODULY_ROUTERU:
        app.include_router(importlib.import_module(nazev).router)
    return app


def test_zadna_cesta_neni_registrovana_dvakrat():
    dvojice = Counter()
    for r in _aplikace().routes:
        cesta = getattr(r, "path", None)
        metody = getattr(r, "methods", None)
        if not cesta or not metody:
            continue
        for m in metody:
            dvojice[(m, cesta)] += 1

    kolize = sorted(k for k, pocet in dvojice.items() if pocet > 1)
    assert not kolize, (
        "Tyhle cesty jsou zaregistrované víckrát – ta pozdější tiše prohrává:\n"
        + "\n".join(f"  {m} {c}" for m, c in kolize)
    )


def test_seznam_routeru_odpovida_mainu():
    """Kdyby přibyl router jen do mainu, test kolizí by ho nehlídal."""
    zdroj = (
        importlib.resources.files("app").joinpath("main.py").read_text(encoding="utf-8")
        if hasattr(importlib, "resources")
        else ""
    )
    if not zdroj:
        pytest.skip("main.py se nepodařilo přečíst")
    pocet_v_mainu = zdroj.count("app.include_router(")
    assert pocet_v_mainu == len(MODULY_ROUTERU), (
        f"main.py registruje {pocet_v_mainu} routerů, ale test hlídá "
        f"{len(MODULY_ROUTERU)}. Doplň chybějící do MODULY_ROUTERU."
    )


# ---- kolize NÁZVŮ schémat ----------------------------------------------------
# Druhá polovina téže chyby z 31. 7. 2026: kromě cesty se srazily i názvy tříd.
# `class SablonaOut` pro šablony textů tiše přepsal `SablonaOut` projektových
# šablon o 200 řádků výš — Python nic neřekne, ale endpointy, které staršího
# schématu používají, začnou padat na 500 (chybí jim pole).
def test_v_modulu_schemat_nejsou_dve_tridy_stejneho_jmena():
    import ast
    import pathlib

    for soubor in sorted(pathlib.Path("app").rglob("schemas.py")):
        strom = ast.parse(soubor.read_text(encoding="utf-8"))
        jmena = [u.name for u in strom.body if isinstance(u, ast.ClassDef)]
        duplicity = sorted({j for j in jmena if jmena.count(j) > 1})
        assert not duplicity, (
            f"{soubor}: dvě třídy stejného jména – ta pozdější tiše přepíše dřívější: "
            + ", ".join(duplicity)
        )
