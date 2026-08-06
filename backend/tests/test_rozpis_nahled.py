"""Náhled rozpisu v prohlížeči musí dát stejná čísla jako server (CRM-08).

Souhrn rozpisu počítá `app/nabidkovac/polozky.py` a appka ho bere hotový.
Dokud ale obchodník píše a nemá uloženo, žádný serverový souhrn neexistuje –
proto `frontend/src/rozpisSoucty.js` vzorec duplikuje pro řádek „Neuloženo —
po uložení bude bez DPH …“.

Duplikát je nutné zlo, tichý rozchod obou stran ne: kdyby se čísla lišila,
částka by po uložení poskočila a nikdo by nevěděl, která je ta pravá. Tenhle
test proto pouští JS modul v Node nad stejnými vstupy jako `polozky.py`
a porovnává haléř po haléři.

Zjištěno 6. 8. 2026: do té doby náhled sčítal NEZAOKROUHLENÉ řádky, kdežto
`souhrn()` sčítá už zaokrouhlené `bez_dph`. U dlouhého rozpisu se rozdíl
nasčítal na koruny. Případ je níž pod `test_dlouhy_rozpis_*`.
"""

import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.nabidkovac import polozky

MODUL_JS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "rozpisSoucty.js"
)

# (mnozstvi, cena_jednotkova, sleva_procent) – realistické i ošklivé případy.
PRIPADY = [
    (1, "4500", 0),
    (10, "4500", 10),
    # Zlomkové množství se slevou: kdyby se sleva brala z řádku a ne
    # z jednotkové ceny, vyjde to jinak.
    ("2.5", "1999.90", 15),
    ("0.333", "3000", 33.3),
    # Půlený haléř – ROUND_HALF_UP nahoru; `Math.round` sám by spadl dolů,
    # protože 2,675 × 100 je ve floatu 267,49999…
    (1, "2.675", 0),
    (3, "0.005", 0),
    # Sleva 100 % (validace ji povoluje) a nulové položky.
    (5, "1200", 100),
    (0, "4500", 10),
    (1, "0", 0),
    # Prázdno a desetinná čárka z ručně psaného políčka.
    ("", "4500", 0),
    ("1,5", "1234,56", "7,5"),
    # Velké částky – celý FVE systém na jednom řádku.
    (1, "12500000.49", 3),
    ("1000", "0.07", 0),
    # Záporné množství (dobropisovaný řádek) – zaokrouhlení musí jít OD nuly.
    ("-2", "2.675", 0),
]


def _polozka(mnozstvi, cena, sleva):
    """Položka jako prostý objekt – výpočet nepotřebuje DB ani SQLAlchemy.

    Prázdný řetězec a desetinná čárka projdou stejnou normalizací jako v API
    (`Decimal(str(...))` na to samo nestačí), aby obě strany dostaly totéž.
    """

    def cislo(h):
        text = str(h).replace(",", ".").strip()
        return Decimal(text) if text else Decimal("0")

    return SimpleNamespace(
        mnozstvi=cislo(mnozstvi),
        cena_jednotkova=cislo(cena),
        sleva_procent=cislo(sleva),
        nakup_jednotkovy=None,
        sazba_dph=None,
    )


def _spust_js(pripady):
    """Pustí `rozpisSoucty.js` v Node a vrátí jeho čísla.

    Node se volá přímo na ESM modul (`--input-type=module`), takže není potřeba
    build ani testovací runner ve frontendu – test se tím nezaváže na nic, co
    by se muselo udržovat zvlášť.
    """
    if shutil.which("node") is None:
        pytest.skip("Node není k dispozici – JS strana se neověří.")
    vstup = json.dumps(
        [
            {"mnozstvi": m, "cena_jednotkova": c, "sleva_procent": s}
            for m, c, s in pripady
        ]
    )
    skript = f"""
import {{ radekBezDph, mezisoucetBezDph }} from {json.dumps(str(MODUL_JS))};
const radky = {vstup};
console.log(JSON.stringify({{
  radky: radky.map((r) => radekBezDph(r.mnozstvi, r.cena_jednotkova, r.sleva_procent)),
  mezisoucet: mezisoucetBezDph(radky),
}}));
"""
    hotovo = subprocess.run(
        ["node", "--input-type=module", "-e", skript],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert hotovo.returncode == 0, f"Node spadl:\n{hotovo.stderr}"
    return json.loads(hotovo.stdout)


@pytest.fixture(scope="module")
def js():
    return _spust_js(PRIPADY)


def test_modul_existuje():
    # Kdyby se soubor přejmenoval, ať test spadne tady a ne až na Node chybě.
    assert MODUL_JS.is_file(), f"Chybí {MODUL_JS} – náhled rozpisu nemá kde brát vzorec."


@pytest.mark.parametrize("index", range(len(PRIPADY)))
def test_radek_sedi_s_backendem(js, index):
    mnozstvi, cena, sleva = PRIPADY[index]
    ocekavano = float(polozky.radek_soucty(_polozka(mnozstvi, cena, sleva))["bez_dph"])
    assert js["radky"][index] == pytest.approx(ocekavano, abs=1e-9), (
        f"Náhled a server se rozešly na řádku {mnozstvi} × {cena} se slevou {sleva} %. "
        "Srovnej frontend/src/rozpisSoucty.js s app/nabidkovac/polozky.radek_soucty."
    )


def test_mezisoucet_sedi_s_backendem(js):
    ocekavano = polozky.souhrn([_polozka(*p) for p in PRIPADY])["bez_dph"]
    assert js["mezisoucet"] == pytest.approx(ocekavano, abs=1e-9), (
        "Součet náhledu se rozešel se souhrnem serveru. "
        "Srovnej frontend/src/rozpisSoucty.js s app/nabidkovac/polozky.souhrn."
    )


def test_dlouhy_rozpis_zaokrouhluje_po_radcich():
    """Regrese: sčítat se musí ZAOKROUHLENÉ řádky, ne naopak.

    200 řádků po 0,005 Kč: po řádcích to je 200 × 0,01 = 2 Kč, kdežto součet
    nezaokrouhlených dá 1 Kč. Přesně tenhle rozdíl náhled do 6. 8. 2026 měl.
    """
    pripady = [(1, "0.005", 0)] * 200
    ze_serveru = polozky.souhrn([_polozka(*p) for p in pripady])["bez_dph"]
    assert ze_serveru == pytest.approx(2.0)
    assert _spust_js(pripady)["mezisoucet"] == pytest.approx(ze_serveru, abs=1e-9)
