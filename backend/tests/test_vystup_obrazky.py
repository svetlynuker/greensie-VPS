# -*- coding: utf-8 -*-
"""Úložiště obrázků vkládaných do nabídkového výstupu.

Cesta k obrázku je součástí konfigurace, kterou posílá prohlížeč – tedy vstup
od klienta. Většina testů proto míří na to, že se přes ni nedá sáhnout mimo
úložiště.
"""

import pytest

from app.nabidkovac import vystup_obrazky as vo


class TestPovoleneTypy:
    def test_obrazky_projdou(self):
        for nazev in ("foto.png", "SCHEMA.JPG", "logo.svg", "a.jpeg", "b.webp"):
            assert vo.je_povolena(nazev), nazev

    def test_ostatni_neprojdou(self):
        # PDF ani archivy do <img> nepatří a tisknout se nedají.
        for nazev in ("smlouva.pdf", "data.zip", "skript.js", "bezpripony", "a.svg.exe"):
            assert not vo.je_povolena(nazev), nazev

    def test_mime_podle_pripony(self):
        assert vo.mime_typ("a.png") == "image/png"
        assert vo.mime_typ("a.JPG") == "image/jpeg"
        assert vo.mime_typ("a.svg") == "image/svg+xml"
        assert vo.mime_typ("a.neznama") == "application/octet-stream"


class TestUlozeni:
    def test_ulozi_a_vrati_relativni_cestu(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        cesta = vo.uloz(42, "fotka.png", b"data")
        assert cesta.startswith("42/")
        assert cesta.endswith("_fotka.png")
        assert (tmp_path / cesta).read_bytes() == b"data"

    def test_dva_soubory_stejneho_jmena_se_neprepisou(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        a = vo.uloz(1, "foto.png", b"prvni")
        b = vo.uloz(1, "foto.png", b"druhy")
        assert a != b
        assert (tmp_path / a).read_bytes() == b"prvni"
        assert (tmp_path / b).read_bytes() == b"druhy"

    def test_nebezpecny_nazev_se_ocisti(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        cesta = vo.uloz(7, "../../../etc/passwd", b"x")
        # Ať uživatel pošle cokoli, soubor skončí ve složce nabídky.
        assert cesta.startswith("7/")
        assert ".." not in cesta
        assert (tmp_path / cesta).exists()

    def test_dlouhy_nazev_se_zkrati(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        cesta = vo.uloz(1, "a" * 500 + ".png", b"x")
        assert len(cesta.split("/")[1]) < 200


class TestCestaKObrazku:
    """POJISTKA: cesta jde od klienta, takže se jí nesmí věřit."""

    def test_platna_cesta_projde(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        rel = vo.uloz(3, "foto.png", b"x")
        assert vo.cesta_k_obrazku(rel).exists()

    def test_vylezt_z_uloziste_nejde(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        tajne = tmp_path.parent / "tajne.txt"
        tajne.write_text("heslo")
        for zla in (
            "../tajne.txt",
            "1/../../tajne.txt",
            "/etc/passwd",
            "../../../../etc/passwd",
            "1/subdir/../../../tajne.txt",
        ):
            with pytest.raises(ValueError):
                vo.cesta_k_obrazku(zla)

    def test_spatny_tvar_neprojde(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        for zla in ("", None, "bez_lomitka.png", "abc/foto.png", "1/a/b.png"):
            with pytest.raises(ValueError):
                vo.cesta_k_obrazku(zla)

    def test_smazani_nesmi_sahnout_mimo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        tajne = tmp_path.parent / "tajne.txt"
        tajne.write_text("heslo")
        vo.smaz("../tajne.txt")  # nesmí spadnout ani nic smazat
        assert tajne.exists()

    def test_smazani_platneho_obrazku(self, tmp_path, monkeypatch):
        monkeypatch.setattr(vo, "UPLOAD_DIR", tmp_path)
        rel = vo.uloz(5, "foto.png", b"x")
        vo.smaz(rel)
        assert not (tmp_path / rel).exists()
        vo.smaz(rel)  # opakované smazání je v pořádku
