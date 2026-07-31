"""Diagramy odběru u odběrného místa (CRM-46, etapa 2).

Testuje se souhrn, který se ukládá při nahrání — na něm stojí to, že OZ v seznamu
pozná nepoužitelný export dřív, než na něm postaví výpočet. Zvlášť hlídáme
přepočet kW → MWh: v exportu je ČINNÝ VÝKON, takže sečtením samotných kW by
u 15minutových dat vyšla čtyřnásobná spotřeba.
"""

from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.crm import diagramy


def _rada(pocet, krok_min=15, hodnota=100.0, start=datetime(2025, 1, 1)):
    return [(start + timedelta(minutes=krok_min * i), hodnota) for i in range(pocet)]


class TestPripony:
    def test_povolene(self):
        for nazev in ("export.csv", "PND_EXPORT.XLS", "profil.xlsx"):
            assert diagramy.over_priponu(nazev) in {".csv", ".xls", ".xlsx"}

    def test_pdf_neprojde(self):
        """Faktura v PDF není diagram — bez kontroly by se uložila a hlásila chybu čtení."""
        with pytest.raises(HTTPException) as e:
            diagramy.over_priponu("faktura.pdf")
        assert e.value.status_code == 422

    def test_bez_pripony(self):
        with pytest.raises(HTTPException):
            diagramy.over_priponu("diagram")


class TestSouhrn:
    def test_prazdna_rada(self):
        s = diagramy.souhrn_rady([])
        assert s["pocet_intervalu"] == 0
        assert s["obdobi_od"] is None and s["max_kw"] is None

    def test_obdobi_a_pocet(self):
        s = diagramy.souhrn_rady(_rada(4))
        assert s["pocet_intervalu"] == 4
        assert s["obdobi_od"] == datetime(2025, 1, 1, 0, 0)
        assert s["obdobi_do"] == datetime(2025, 1, 1, 0, 45)
        assert s["interval_min"] == 15

    def test_spotreba_je_energie_ne_soucet_kw(self):
        """4 × 100 kW po 15 minutách = 100 kWh = 0,1 MWh (ne 400)."""
        s = diagramy.souhrn_rady(_rada(4, hodnota=100.0))
        assert s["spotreba_mwh"] == 0.1

    def test_hodinovy_export(self):
        """Hodinový krok pozná z časů a spotřebu spočítá jako kW × 1 h."""
        s = diagramy.souhrn_rady(_rada(4, krok_min=60, hodnota=100.0))
        assert s["interval_min"] == 60
        assert s["spotreba_mwh"] == 0.4

    def test_max_kw(self):
        rada = _rada(3, hodnota=50.0)
        rada[1] = (rada[1][0], 275.5)
        assert diagramy.souhrn_rady(rada)["max_kw"] == 275.5

    def test_jediny_interval_nema_krok(self):
        """Z jedné značky se délka intervalu odvodit nedá – hlásí se None,
        spotřeba se dopočítá výchozími 15 minutami."""
        s = diagramy.souhrn_rady(_rada(1, hodnota=100.0))
        assert s["interval_min"] is None
        assert s["spotreba_mwh"] == 0.025

    def test_rocni_15min_rada(self):
        """Roční 15min diagram: 35 040 intervalů a ~365 dní období."""
        s = diagramy.souhrn_rady(_rada(35040, hodnota=40.0))
        assert s["pocet_intervalu"] == 35040
        assert (s["obdobi_do"] - s["obdobi_od"]).days == 364
        assert s["spotreba_mwh"] == 350.4

    def test_nulove_hodnoty_nejsou_chybejici(self):
        """Odstávka = 0 kW. Nula musí projít do součtu, ne se zahodit jako „nevíme“."""
        s = diagramy.souhrn_rady([(datetime(2025, 1, 1), 0.0), (datetime(2025, 1, 1, 0, 15), 0.0)])
        assert s["spotreba_mwh"] == 0.0
        assert s["max_kw"] == 0.0


def test_povolene_pripony_odpovidaji_profilu_nabidky():
    """Diagram místa a profil na nabídce jedou přes týž parser, takže musí brát
    stejné formáty — jinak by šel soubor nahrát na jedno místo a na druhé ne."""
    from app.nabidkovac import soubory

    assert diagramy.POVOLENE_PRIPONY == soubory.POVOLENE_PRIPONY["spotreba_csv"]
