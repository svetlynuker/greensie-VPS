"""Testy tisku nabídky do PDF (`nabidkovac/pdf.py`).

Co se tady hlídá a proč právě to:

* **Chybějící Chromium se pozná.** Na serveru, kde neproběhl `update.sh`,
  prohlížeč není. Bez převodu na `PdfNedostupne` by obchodník dostal
  pětistovku a v logu stacktrace z podprocesu — a nikdo by netušil, že stačí
  spustit deploy.

* **Název souboru drží číslo nabídky a datum.** Podle čísla se soubor hledá na
  Disku i ve schránce zákazníka; bez data by druhý tisk té samé nabídky nešel
  odlišit od prvního.

* **Nahrání na Disk je idempotentní.** Úloha ve frontě se po chybě opakuje.
  Kdyby se nekontrolovalo `disk_file_id`, ve složce nabídky by po pár retry
  ležely tři kopie stejného PDF.

Chromium se tady nespouští — jeho výstup ověřuje samostatná zkouška při
nasazení. Tady jde o rozhodování kolem něj.
"""

import subprocess
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.nabidkovac import pdf as pdf_modul


def _nabidka(**kwargs):
    zaklad = {"id": 12, "cislo": "NAB-26-0007", "typ": "ppa", "obchodni_pripad_id": 3}
    return SimpleNamespace(**{**zaklad, **kwargs})


# ---- název souboru -----------------------------------------------------------
def test_nazev_souboru_ma_cislo_typ_a_datum():
    nazev = pdf_modul.nazev_souboru(_nabidka(), "ppa", datetime(2026, 8, 3, 14, 30))
    assert nazev == "NAB-26-0007_ppa_2026-08-03.pdf"


def test_nazev_souboru_bez_cisla_pouzije_id():
    """Nabídka z doby před číselnými řadami číslo nemá; soubor musí mít název
    tak jako tak, jinak by na Disku vznikl „None.pdf"."""
    nazev = pdf_modul.nazev_souboru(_nabidka(cislo=None), "ppa", datetime(2026, 8, 3))
    assert nazev == "nabidka-12_ppa_2026-08-03.pdf"


# ---- výroba PDF: co se stane, když to nejde ---------------------------------
def test_chybejici_chromium_hlasi_co_s_tim(monkeypatch):
    def spadne(*args, **kwargs):
        return SimpleNamespace(
            returncode=1,
            stdout=b"",
            stderr=b"Executable doesn't exist at /root/.cache/ms-playwright/chromium",
        )

    monkeypatch.setattr(pdf_modul.subprocess, "run", spadne)
    with pytest.raises(pdf_modul.PdfNedostupne) as chyba:
        pdf_modul.vyrob("<html></html>")
    assert "update.sh" in str(chyba.value)


def test_zatuhly_prohlizec_se_prerusi(monkeypatch):
    """Timeout musí skončit hlášením, ne viset až do timeoutu prohlížeče."""

    def zatuhne(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="chromium", timeout=pdf_modul.TIMEOUT_S)

    monkeypatch.setattr(pdf_modul.subprocess, "run", zatuhne)
    with pytest.raises(pdf_modul.PdfNedostupne) as chyba:
        pdf_modul.vyrob("<html></html>")
    assert "přerušeno" in str(chyba.value)


def test_prilis_velky_podklad_se_odmitne_bez_spusteni_prohlizece(monkeypatch):
    """Desítky MB obrázků nemá cenu posílat Chromiu — na 4GB serveru by to
    znamenalo swapování, ne PDF."""
    spusteno = []
    monkeypatch.setattr(pdf_modul.subprocess, "run", lambda *a, **k: spusteno.append(1))

    with pytest.raises(pdf_modul.PdfNedostupne):
        pdf_modul.vyrob("x" * (pdf_modul.MAX_HTML_BAJTU + 1))
    assert spusteno == []


def test_uspesne_vykresleni_vrati_bajty(monkeypatch):
    monkeypatch.setattr(
        pdf_modul.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"%PDF-1.4 ...", stderr=b""),
    )
    assert pdf_modul.vyrob("<html></html>").startswith(b"%PDF")


# ---- nahrání na Disk --------------------------------------------------------
class FakeSession:
    def __init__(self, zaznam):
        self.zaznam = zaznam
        self.commity = 0

    def get(self, model, id_):
        return self.zaznam if model.__name__ == "GenerovanaNabidkaPdf" else None

    def commit(self):
        self.commity += 1


def test_uz_nahrane_pdf_se_nenahrava_znovu():
    """Opakovaná úloha z fronty nesmí ve složce nabídky vyrobit druhou kopii."""
    zaznam = SimpleNamespace(id=1, nabidka_id=12, disk_file_id="soubor1", soubor_cesta="12/a.pdf")
    assert pdf_modul.nahraj_na_disk(FakeSession(zaznam), 1) == {"skip": True}


def test_smazane_pdf_uloha_preskoci():
    """Záznam mezitím někdo smazal — není co nahrávat a není to chyba."""
    assert pdf_modul.nahraj_na_disk(FakeSession(None), 1) == {"skip": True}
