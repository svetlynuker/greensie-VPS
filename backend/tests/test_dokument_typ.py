# -*- coding: utf-8 -*-
"""Automatické rozpoznání typu nahraného dokumentu podle přípony."""

from app.nabidkovac import soubory
from app.nabidkovac.models import TYPY_DOKUMENTU


def test_tabulka_je_profil_spotreby():
    assert soubory.odvod_typ("odber_2025.xlsx") == "spotreba_csv"
    assert soubory.odvod_typ("profil.CSV") == "spotreba_csv"
    assert soubory.odvod_typ("stary_export.xls") == "spotreba_csv"


def test_pdf_je_faktura():
    assert soubory.odvod_typ("faktura_cez.pdf") == "faktura_pdf"


def test_obrazek_je_jiny_dokument():
    assert soubory.odvod_typ("rozvadec.JPG") == "jiny"
    assert soubory.odvod_typ("stitek.png") == "jiny"


def test_neznama_pripona_vrati_none():
    assert soubory.odvod_typ("smlouva.docx") is None
    assert soubory.odvod_typ("bez_pripony") is None
    assert soubory.odvod_typ("") is None


def test_odvozene_typy_jsou_platne_a_maji_povolenou_priponu():
    # Automat nesmí přiřadit typ, který by upload vzápětí odmítl na whitelistu.
    for pripona, typ in soubory.TYP_PODLE_PRIPONY.items():
        assert typ in TYPY_DOKUMENTU
        assert pripona in soubory.POVOLENE_PRIPONY[typ]
