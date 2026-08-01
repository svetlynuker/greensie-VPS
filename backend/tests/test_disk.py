"""Testy modulu „Disk" (procházení firemního Google Disku).

Co se tady hlídá a proč právě to:

* **Strop viditelnosti.** `folder_id` chodí z prohlížeče. Kdyby kontrola
  „leží to pod kořenem konektoru" vypadla, appka by se stala čtečkou celého
  firemního Disku — a nic by nespadlo, jen by šla vypsat cizí složka. Přesně
  ten druh chyby, kterou nikdo nenajde očima.

* **Odkaz na každé úrovni.** Danovo zadání znělo „na každé úrovni kde kliknu
  chci mít možnost nechat se přesměrovat na disk". Kdyby `url` u položek nebo
  u kroků cesty zmizelo, obrazovka pořád funguje — jen ta tlačítka nikam
  nevedou, což se v kódu nepozná.

* **Kořen bez `webViewLink`.** Drive u kořene sdíleného disku ten odkaz občas
  nevrátí. Bez záložní adresy by první obrazovka modulu byla jediná, ze které
  se na Disk odejít nedá.

* **Přepínač novinek + právo.** Modul je zatím interní; kdyby `vyzaduj_disk`
  přestal koukat na `ma_novinky`, naskočí Disk všem, kdo dostanou právo.

Bez DB a bez Googlu: `_nastaveni` i Drive klient se podstrkují monkeypatchem.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.konektor import crm_slozky, disk_prochazeni
from app.konektor.disk_routes import vyzaduj_disk
from app.konektor.google_klient import FOLDER_MIME

KOREN = "koren123"


class FakeDrive:
    """Minimální Disk: strom složek a souborů v paměti.

    `deti` = {id rodiče: [položky]}, `soubory` = {id: položka} pro `get_file`.
    Položky mají tvar odpovědi Drive API, ať se testuje totéž, co poteče z Googlu.
    """

    def __init__(self, polozky: dict[str, dict], deti: dict[str, list[str]]):
        self.polozky = polozky
        self.deti = deti

    def get_file(self, file_id: str) -> dict:
        if file_id not in self.polozky:
            raise RuntimeError(f"neznámé id {file_id}")
        return self.polozky[file_id]

    def list_children_vse(self, parent_id: str) -> list[dict]:
        return [self.polozky[i] for i in self.deti.get(parent_id, [])]


def _slozka(id_: str, nazev: str, rodic: str | None, link: str | None = None) -> dict:
    f = {"id": id_, "name": nazev, "mimeType": FOLDER_MIME, "parents": [rodic] if rodic else []}
    if link is not None:
        f["webViewLink"] = link
    return f


def _soubor(id_: str, nazev: str, rodic: str, velikost: str | None = None) -> dict:
    f = {
        "id": id_,
        "name": nazev,
        "mimeType": "application/pdf",
        "parents": [rodic],
        "webViewLink": f"https://drive.google.com/file/d/{id_}/view",
    }
    if velikost:
        f["size"] = velikost
    return f


def _drive() -> FakeDrive:
    """Kořen → klient → případ (+ soubory) a jedna složka MIMO kořen."""
    polozky = {
        # Kořen schválně bez webViewLink – tak se chová kořen sdíleného disku.
        KOREN: _slozka(KOREN, "6. projekty", None),
        "klient": _slozka("klient", "Alfa s.r.o. [7]", KOREN, "https://drive/klient"),
        "op": _slozka("op", "OP-26-0301 - FVE", "klient", "https://drive/op"),
        "zz": _soubor("zz", "zaloha.pdf", "op", "2048"),
        "aa": _soubor("aa", "smlouva.pdf", "op", "1024"),
        "pod": _slozka("pod", "3. nabidka", "op", "https://drive/pod"),
        # Mimo kořen – tohle appka nesmí vypsat ani na přímé zadání ID.
        "mzdy": _slozka("mzdy", "Mzdy", "jinykoren", "https://drive/mzdy"),
        "jinykoren": _slozka("jinykoren", "Personalistika", None),
    }
    deti = {
        KOREN: ["klient"],
        "klient": ["op"],
        # Schválně v „špatném" pořadí: soubor, soubor, složka.
        "op": ["zz", "aa", "pod"],
        "jinykoren": ["mzdy"],
    }
    return FakeDrive(polozky, deti)


@pytest.fixture
def disk(monkeypatch):
    drive = _drive()
    n = SimpleNamespace(google_root_folder_id=KOREN, google_shared_drive_id="sdileny")
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    monkeypatch.setattr(crm_slozky, "_drive_klient", lambda nast: drive)
    return drive


# ---- strop viditelnosti ------------------------------------------------------
def test_slozka_mimo_koren_se_nevypise(disk):
    """Cizí ID z prohlížeče = 403, ne výpis. Jinak je appka čtečka celého Disku."""
    with pytest.raises(PermissionError):
        disk_prochazeni.obsah(None, "mzdy")


def test_slozka_pod_korenem_se_vypise(disk):
    d = disk_prochazeni.obsah(None, "op")
    assert d["nazev"] == "OP-26-0301 - FVE"
    assert [p["nazev"] for p in d["polozky"]] == ["3. nabidka", "smlouva.pdf", "zaloha.pdf"], (
        "Složky musí být první a pak soubory podle názvu – člověk hledá cestu dolů."
    )


def test_koren_se_bere_z_nastaveni_konektoru(disk):
    d = disk_prochazeni.obsah(None, None)
    assert d["je_koren"] is True
    assert d["folder_id"] == KOREN
    assert d["cesta"] == [], "V kořeni není co v cestě zkracovat."


def test_bez_korenove_slozky_padne_zpet_na_sdileny_disk():
    n = SimpleNamespace(google_root_folder_id="", google_shared_drive_id="sdileny")
    assert disk_prochazeni._koren_id(n) == "sdileny"


def test_bez_nastaveni_hlasi_neprichystany_konektor(monkeypatch):
    from app.konektor.logika import NastaveniNepripraveno

    n = SimpleNamespace(google_root_folder_id="", google_shared_drive_id="")
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    with pytest.raises(NastaveniNepripraveno):
        disk_prochazeni.koren(None)


# ---- odkaz na Disk na každé úrovni ------------------------------------------
def test_kazda_polozka_i_krok_cesty_ma_odkaz_na_disk(disk):
    d = disk_prochazeni.obsah(None, "pod")
    assert d["url"], "Aktuální složka musí mít odkaz – jinak není kam odejít."
    assert [k["nazev"] for k in d["cesta"]] == ["Alfa s.r.o. [7]", "OP-26-0301 - FVE", "3. nabidka"]
    assert all(k["url"] for k in d["cesta"]), (
        "Každý krok cesty nese odkaz na Disk – to je Danovo zadání „na každé úrovni“."
    )
    obsah_op = disk_prochazeni.obsah(None, "op")
    assert all(p["url"] for p in obsah_op["polozky"])


def test_koren_bez_weblinku_dostane_zaloznu_adresu(disk):
    """Kořen sdíleného disku `webViewLink` nevrací – odkaz se skládá z ID."""
    k = disk_prochazeni.koren(None)
    assert k["url"] == f"https://drive.google.com/drive/folders/{KOREN}"
    assert k["nazev"] == "6. projekty"


def test_velikost_souboru_se_prevadi_na_cislo(disk):
    soubory = {p["nazev"]: p for p in disk_prochazeni.obsah(None, "op")["polozky"]}
    assert soubory["smlouva.pdf"]["velikost"] == 1024
    assert soubory["3. nabidka"]["velikost"] is None, "Složka velikost nemá."


def test_zkraceni_dlouhe_slozky_se_hlasi(disk):
    d = disk_prochazeni.obsah(None, "op", limit=1)
    assert len(d["polozky"]) == 1
    assert d["zkraceno"] is True, "Utnutý výpis se musí přiznat, jinak to vypadá na smazané soubory."


# ---- práva a přepínač novinek ------------------------------------------------
def _uzivatel(admin: bool, prava: list[str]):
    return SimpleNamespace(je_admin=admin, extra_prava=prava, skupina=None)


def test_bez_prava_disk_modul_neexistuje():
    with pytest.raises(HTTPException) as e:
        vyzaduj_disk(_uzivatel(False, []))
    assert e.value.status_code == 404, "404, ne 403 – kdo funkci nemá vidět, pro toho neexistuje."


def test_pravo_disk_zatim_nestaci_bez_novinek():
    """Modul je interní: samotné právo ho neodemkne, dokud běží přepínač novinek."""
    with pytest.raises(HTTPException) as e:
        vyzaduj_disk(_uzivatel(False, ["disk"]))
    assert e.value.status_code == 404


def test_superspravce_disk_otevre():
    u = _uzivatel(True, [])
    assert vyzaduj_disk(u) is u


def test_vypis_slozky_projde_vsechny_stranky():
    """Drive vrací po 1000 položkách. Utnutá první stránka by nebyla chyba,
    jen chybějící konec abecedy – a to nikdo nepozná."""
    from app.konektor.google_klient import DriveClient

    stranky = [
        {"files": [{"id": "a"}, {"id": "b"}], "nextPageToken": "t2"},
        {"files": [{"id": "c"}]},
    ]
    volani: list[str | None] = []

    class FakeFiles:
        def list(self, **kw):
            volani.append(kw.get("pageToken"))
            odpoved = stranky[len(volani) - 1]
            return SimpleNamespace(execute=lambda num_retries=0: odpoved)

    klient = DriveClient.__new__(DriveClient)  # bez sítě: service podstrčíme
    klient.service = SimpleNamespace(files=lambda: FakeFiles())

    assert [f["id"] for f in klient.list_children_vse("koren")] == ["a", "b", "c"]
    assert volani == [None, "t2"], "Druhá stránka se musí dotáhnout tokenem z první."


def test_pravo_disk_je_v_katalogu():
    """Bez klíče v katalogu by ho nešlo v Admin nastavení nikomu přidělit."""
    from app.auth.permissions import VSECHNA_PRAVA

    assert "disk" in VSECHNA_PRAVA
