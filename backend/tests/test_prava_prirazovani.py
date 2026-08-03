"""Přidělené právo musí opravdu otevřít modul — a odebrané ho zavřít.

Proč tenhle soubor vznikl (3. 8. 2026): v Admin nastavení se dalo zaškrtnout
právo `emaily`, uložit to, a člověku se pořád nic neukázalo. Vedle práva totiž
běžela druhá, nezávislá branka („přepínač novinek"), která pouštěla jen
supersprávce. Jediná cesta, jak někoho dostat k e-mailu, tak bylo dát mu plná
práva na všechno — což je přesně to, co se přidělováním práv řeší.

Tři pasti, které se tady hlídají:

* **Druhá branka u modulu.** Právo samo musí stačit. Kdyby k němu kdokoli
  přidal další podmínku (`je_admin`, příznak, feature flag), spadne to tady,
  a ne až u uživatele, kterému „appka nefunguje" a nikdo neví proč.

* **Duplikát práva ve skupině i ve výjimkách.** Obojí se sčítá, takže duplikát
  nic nepřidá — ale při odebírání ze skupiny právo tiše zůstane ve výjimkách
  a odebrání se navenek „neprovede". Proto se výjimky ukládají očištěné.

* **Schovaná položka v nabídce místo kontroly na backendu.** Přehled projektů
  se v levém panelu schovává za právem `projekty`, ale endpoint matice byl jen
  za přihlášením — kdo právo neměl, přečetl si ji zadáním adresy.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.admin.routes import _jen_navic, _smi_delat_superspravce
from app.auth.permissions import prava_uzivatele


def _uzivatel(admin=False, extra=(), skupina_prava=None):
    skupina = None if skupina_prava is None else SimpleNamespace(prava=list(skupina_prava))
    return SimpleNamespace(je_admin=admin, extra_prava=list(extra), skupina=skupina)


class _FakeDb:
    """Nahrazuje `db.get(Skupina, id)` – testy práv nepotřebují databázi."""

    def __init__(self, prava_podle_id):
        self._prava = prava_podle_id

    def get(self, _model, skupina_id):
        prava = self._prava.get(skupina_id)
        return None if prava is None else SimpleNamespace(prava=prava)


# ---- právo je jediná branka --------------------------------------------------
def test_pravo_emaily_staci_bez_superspravce():
    from app.crm.email_routes import vyzaduj_emaily

    u = _uzivatel(extra=["emaily"])
    assert vyzaduj_emaily(u) is u


def test_pravo_disk_staci_bez_superspravce():
    from app.konektor.disk_routes import vyzaduj_disk

    u = _uzivatel(extra=["disk"])
    assert vyzaduj_disk(u) is u


def test_pravo_ze_skupiny_funguje_stejne_jako_osobni():
    """Nezáleží na tom, jestli právo přišlo ze skupiny, nebo jako výjimka."""
    from app.crm.email_routes import vyzaduj_emaily

    u = _uzivatel(skupina_prava=["emaily"])
    assert vyzaduj_emaily(u) is u


@pytest.mark.parametrize(
    "modul, guard_cesta",
    [
        ("emaily", "app.crm.email_routes:vyzaduj_emaily"),
        ("disk", "app.konektor.disk_routes:vyzaduj_disk"),
        ("projekty", "app.matice.permissions:vyzaduj_projekty"),
    ],
)
def test_bez_prava_403_s_vysvetlenim(modul, guard_cesta):
    """403, ne 404: člověk má z hlášky poznat, o jaké právo požádat."""
    import importlib

    cesta, nazev = guard_cesta.split(":")
    guard = getattr(importlib.import_module(cesta), nazev)

    with pytest.raises(HTTPException) as e:
        guard(_uzivatel())
    assert e.value.status_code == 403
    assert "oprávnění" in e.value.detail


# ---- matice: schovaná nabídka není kontrola přístupu ------------------------
def test_matici_neprecte_kdo_nema_pravo_projekty():
    from app.matice.permissions import vyzaduj_projekty

    s_pravem = _uzivatel(extra=["projekty"])
    assert vyzaduj_projekty(s_pravem) is s_pravem

    with pytest.raises(HTTPException) as e:
        vyzaduj_projekty(_uzivatel(extra=["zakaznici"]))
    assert e.value.status_code == 403


# ---- výjimky se ukládají očištěné o práva skupiny ---------------------------
def test_vyjimky_se_zbavi_prav_ze_skupiny():
    db = _FakeDb({1: ["zakaznici", "emaily"]})
    assert _jen_navic(db, 1, ["zakaznici", "emaily", "finance"]) == ["finance"]


def test_bez_skupiny_zustanou_vyjimky_cele():
    db = _FakeDb({})
    assert _jen_navic(db, None, ["emaily", "finance"]) == ["emaily", "finance"]


def test_ocisteni_nikomu_neubere_zadne_pravo():
    """Klíčová vlastnost: očištění mění zápis, ne výsledek.

    Kdyby `_jen_navic` odebralo právo, které skupina nedává, člověk by po
    uložení formuláře tiše přišel o přístup — a nikdo by nevěděl proč.
    """
    db = _FakeDb({1: ["zakaznici", "emaily"]})
    pred = _uzivatel(extra=["zakaznici", "emaily", "finance"], skupina_prava=["zakaznici", "emaily"])
    po = _uzivatel(extra=_jen_navic(db, 1, pred.extra_prava), skupina_prava=["zakaznici", "emaily"])
    assert prava_uzivatele(po) == prava_uzivatele(pred)


# ---- právo `admin` není cesta k supersprávci --------------------------------
def test_kdo_neni_superspravce_nesmi_superspravce_delat():
    with pytest.raises(HTTPException) as e:
        _smi_delat_superspravce(_uzivatel(extra=["admin"]))
    assert e.value.status_code == 403


def test_superspravce_superspravce_delat_smi():
    assert _smi_delat_superspravce(_uzivatel(admin=True)) is None
