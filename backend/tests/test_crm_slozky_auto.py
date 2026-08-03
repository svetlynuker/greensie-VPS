"""Testy automatického zakládání složek na Disku pro záznamy z appky.

Co se tady hlídá a proč právě to:

* **Nabídka a objednávka končí ve svém kontejneru.** Kdyby se složka založila
  přímo pod obchodním případem, na Disku se nic nerozbije — jen se struktura
  tiše rozejde s tou, kterou zakládá konektor z Raynetu, a nikdo nepozná, která
  je správná. Očima se to nechytá, protože obojí „nějak funguje".

* **Název složky nabídky nese číslo i typ.** Jeden případ může mít nabídku na
  PPA i na peak shaving. Bez typu by ve složce ležela dvě čísla bez vysvětlení,
  co je co.

* **Zakládání se plánuje, ne provádí.** Kopie vzoru je desítky volání na Disk.
  Kdyby se to vrátilo do endpointu, formulář by na pár sekund zatuhl a při
  souběhu by to appku tlačilo k 502 (stejný důvod, proč pošta běží zvlášť).

* **Chyba fronty nesmí sebrat záznam.** Kdyby `naplanuj` propustilo výjimku,
  zákazník by se kvůli nedostupnému Disku vůbec neuložil. To je nepoměr:
  nezaložená složka se dohoní tlačítkem, ztracený záznam ne.

Bez DB a bez Googlu: session i Drive klient se podstrkují (viz `FakeSession`).
"""

from types import SimpleNamespace

import pytest

from app.konektor import crm_slozky
from app.konektor.google_klient import FOLDER_MIME

# Testy tady zakládají skutečný ORM objekt (`KonektorEntityFolder`), a k tomu
# SQLAlchemy potřebuje dokončit VŠECHNY mapery v registru. Bez těchhle importů
# padne na `Faktura` → `Projekt`: jiný test si stáhne `app.finance.models`,
# jehož vazba na `Projekt` z `app.matice.models` pak nemá kde se najít.
# Pořadí testů je náhodné, takže bez importů to padá „jen někdy".
import app.crm.models  # noqa: E402,F401
import app.finance.models  # noqa: E402,F401
import app.matice.models  # noqa: E402,F401
import app.nabidkovac.models  # noqa: E402,F401

VZOR = "vzor0"  # globální „0. vzor"
KONT_OP = "1. Obchodní Případy"
KONT_NAB = "1. nabídky"
KONT_OBJ = "5. objednávky"


class FakeDrive:
    """Minimální Disk: strom složek v paměti + záznam, co se kam kopírovalo."""

    def __init__(self, polozky: dict[str, dict], deti: dict[str, list[str]]):
        self.polozky = polozky
        self.deti = deti
        self.kopie: list[tuple[str, str, str]] = []  # (zdroj, cíl, nový název)
        self.zalozene: list[tuple[str, str]] = []
        self.nahrane: list[tuple[str, str, bytes, str]] = []

    def get_file(self, file_id: str) -> dict:
        if file_id not in self.polozky:
            raise RuntimeError(f"neznámé id {file_id}")
        return self.polozky[file_id]

    def list_children(self, parent_id: str) -> list[dict]:
        return [self.polozky[i] for i in self.deti.get(parent_id, [])]

    def copy_tree(self, zdroj: str, cil: str, nazev: str, skip: set[str] | None = None) -> dict:
        self.kopie.append((zdroj, cil, nazev))
        nove = f"kopie-{len(self.kopie)}"
        self.polozky[nove] = {
            "id": nove,
            "name": nazev,
            "mimeType": FOLDER_MIME,
            "parents": [cil],
            "webViewLink": f"https://drive/{nove}",
        }
        self.deti.setdefault(cil, []).append(nove)
        return self.polozky[nove]

    def create_folder(self, nazev: str, parent_id: str) -> dict:
        self.zalozene.append((nazev, parent_id))
        nove = f"slozka-{len(self.zalozene)}"
        self.polozky[nove] = {
            "id": nove,
            "name": nazev,
            "mimeType": FOLDER_MIME,
            "parents": [parent_id],
            "webViewLink": f"https://drive/{nove}",
        }
        self.deti.setdefault(parent_id, []).append(nove)
        return self.polozky[nove]

    def upload_file(self, nazev: str, parent_id: str, data: bytes, mime: str) -> dict:
        self.nahrane.append((nazev, parent_id, data, mime))
        return {"id": "soubor1", "name": nazev, "webViewLink": "https://drive/soubor1"}


class FakeQuery:
    """Dotaz nad seznamem v paměti. Filtry se ignorují — testy si vybírají
    obsah `zaznamy` samy, takže na jejich vyhodnocování tu nic nestojí."""

    def __init__(self, zaznamy: list):
        self._zaznamy = zaznamy

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._zaznamy[0] if self._zaznamy else None

    def all(self):
        return list(self._zaznamy)


class FakeSession:
    """Session, která si pamatuje přidané objekty a nic nikam neposílá.

    `mapovani` jsou existující řádky `KonektorEntityFolder` (klíčem
    `(entita, id)`), `fronta` sbírá zařazené úlohy.
    """

    def __init__(self, mapovani: dict[tuple[str, int], object] | None = None):
        self.mapovani = mapovani or {}
        self.pridane: list = []
        self.commity = 0
        self.rollbacky = 0

    def query(self, *args, **kwargs):
        return FakeQuery([])

    def add(self, obj):
        self.pridane.append(obj)

    def commit(self):
        self.commity += 1

    def rollback(self):
        self.rollbacky += 1

    def refresh(self, obj):
        pass

    def get(self, model, id_):
        return None


def _drive() -> FakeDrive:
    """Vzor („0. vzor" → kontejner OP → vzor OP → kontejnery nabídek a objednávek)
    a vedle něj hotová složka klienta s hotovou složkou případu."""
    polozky = {}
    deti = {}

    def slozka(id_, nazev, rodic):
        polozky[id_] = {
            "id": id_,
            "name": nazev,
            "mimeType": FOLDER_MIME,
            "parents": [rodic] if rodic else [],
            "webViewLink": f"https://drive/{id_}",
        }
        if rodic:
            deti.setdefault(rodic, []).append(id_)

    slozka(VZOR, "0. vzor", None)
    slozka("vzor-kont-op", KONT_OP, VZOR)
    slozka("vzor-op", "OP-XX-XXXX - vzor", "vzor-kont-op")
    slozka("vzor-kont-nab", KONT_NAB, "vzor-op")
    slozka("vzor-nab", "NAB vzor", "vzor-kont-nab")
    slozka("vzor-kont-obj", KONT_OBJ, "vzor-op")
    slozka("vzor-obj", "OBJ vzor", "vzor-kont-obj")

    # Hotová složka klienta a v ní hotová složka případu s oběma kontejnery.
    slozka("klient", "Alfa s.r.o. [7]", None)
    slozka("kont-op", KONT_OP, "klient")
    slozka("op", "OP-26-0301 - FVE", "kont-op")
    slozka("op-nab", KONT_NAB, "op")
    slozka("op-obj", KONT_OBJ, "op")
    return FakeDrive(polozky, deti)


@pytest.fixture
def disk(monkeypatch):
    drive = _drive()
    n = SimpleNamespace(
        google_root_folder_id="koren",
        google_shared_drive_id="sdileny",
        google_subject_email="konektor@greensie.cz",
        google_vzor_folder_id=VZOR,
        kontejner_op=KONT_OP,
        kontejner_nabidky=KONT_NAB,
        kontejner_objednavky=KONT_OBJ,
        template_subfolders="",
    )
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    monkeypatch.setattr(crm_slozky, "_drive_klient", lambda nast: drive)
    monkeypatch.setattr(crm_slozky, "zaloguj", lambda *a, **k: None)
    # Složka případu už existuje – testy nabídek nemají řešit její zakládání.
    monkeypatch.setattr(
        crm_slozky,
        "zajisti_slozku_pripadu",
        lambda db, pripad, zakaznik: SimpleNamespace(
            drive_folder_id="op", kontejnery={"nabidky": "op-nab", "objednavky": "op-obj"}
        ),
    )
    return drive


def _nabidka(**kwargs):
    zaklad = {"id": 12, "cislo": "NAB-26-0007", "typ": "ppa", "obchodni_pripad_id": 3}
    return SimpleNamespace(**{**zaklad, **kwargs})


def _objednavka(**kwargs):
    zaklad = {"id": 5, "cislo": "OBJ-26-0002", "nazev": "FVE Alfa", "obchodni_pripad_id": 3}
    return SimpleNamespace(**{**zaklad, **kwargs})


# ---- kam a pod jakým názvem složka vznikne -----------------------------------
def test_slozka_nabidky_vznikne_v_kontejneru_nabidek(disk, monkeypatch):
    """Kopie vzoru nabídky míří do „1. nabídky" pod složkou případu.

    Kdyby cíl spadl na složku případu, struktura z appky se rozejde se
    strukturou z Raynetu — a to je celý smysl tohohle modulu.
    """
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    db = FakeSession()

    ef = crm_slozky.zajisti_slozku_nabidky(db, _nabidka(), object(), object())

    assert disk.kopie == [("vzor-nab", "op-nab", "NAB-26-0007 - PPA")]
    assert ef.entity == crm_slozky.ENTITA_NABIDKA
    assert ef.entity_id == 12
    assert ef.drive_folder_url == "https://drive/kopie-1"


def test_slozka_objednavky_vznikne_v_kontejneru_objednavek(disk, monkeypatch):
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    db = FakeSession()

    crm_slozky.zajisti_slozku_objednavky(db, _objednavka(), object(), object())

    assert disk.kopie == [("vzor-obj", "op-obj", "OBJ-26-0002 - FVE Alfa")]


def test_nazev_slozky_nabidky_nese_typ_reseni(disk, monkeypatch):
    """Peak shaving a PPA pod jedním případem musí být rozeznatelné."""
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    crm_slozky.zajisti_slozku_nabidky(
        FakeSession(), _nabidka(typ="peak_shaving"), object(), object()
    )
    assert disk.kopie[0][2] == "NAB-26-0007 - Peak shaving"


def test_nabidka_bez_cisla_ma_nazev_z_typu(disk, monkeypatch):
    """Staré nabídky číslo nemají; složka bez názvu by na Disku nešla najít."""
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    crm_slozky.zajisti_slozku_nabidky(FakeSession(), _nabidka(cislo=None), object(), object())
    assert disk.kopie[0][2] == "PPA"


def test_chybejici_kontejner_se_dozalozi(disk, monkeypatch):
    """Kontejner ve složce případu není → vytvoří se, ať nabídka neskončí
    volně v případu.

    Realistický případ: složka případu vznikla ve starém režimu (bez uložených
    ID kontejnerů) a kontejner nabídek v ní nikdo neudělal.
    """
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    monkeypatch.setattr(
        crm_slozky,
        "zajisti_slozku_pripadu",
        lambda db, pripad, zakaznik: SimpleNamespace(drive_folder_id="op", kontejnery=None),
    )
    disk.deti["op"] = []  # kontejnery ve složce případu nejsou

    crm_slozky.zajisti_slozku_nabidky(FakeSession(), _nabidka(), object(), object())

    assert disk.zalozene == [(KONT_NAB, "op")]
    assert disk.kopie[0][1] == "slozka-1"


def test_existujici_slozka_se_nezaklada_znovu(disk, monkeypatch):
    """Idempotence: druhý běh nesmí na Disku vyrobit druhou složku."""
    hotova = SimpleNamespace(drive_folder_id="kopie-1", entity=crm_slozky.ENTITA_NABIDKA)
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: hotova)

    ef = crm_slozky.zajisti_slozku_nabidky(FakeSession(), _nabidka(), object(), object())

    assert ef is hotova
    assert disk.kopie == []


# ---- plánování do fronty -----------------------------------------------------
def test_naplanuj_zaradi_ulohu_do_fronty(monkeypatch):
    zarazene = []
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    monkeypatch.setattr(
        crm_slozky.fronta, "zarad", lambda db, typ, payload: zarazene.append((typ, payload))
    )
    db = FakeSession()

    crm_slozky.naplanuj(db, crm_slozky.ENTITA_OP, 42)

    assert zarazene == [("crm_slozka", {"entita": "crm_op", "id": 42})]


def test_naplanuj_nic_nedela_kdyz_slozka_uz_je(monkeypatch):
    """Jinak by každé uložení zákazníka plnilo frontu úlohami, které nic nedělají."""
    zarazene = []
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: object())
    monkeypatch.setattr(
        crm_slozky.fronta, "zarad", lambda db, typ, payload: zarazene.append(payload)
    )

    crm_slozky.naplanuj(FakeSession(), crm_slozky.ENTITA_OP, 42)

    assert zarazene == []


def test_naplanuj_polkne_chybu_a_vrati_session_do_poradku(monkeypatch):
    """Nedostupná fronta nesmí shodit zakládání záznamu (viz docstring modulu)."""

    def rozbite(db, e, i):
        raise RuntimeError("DB je pryč")

    monkeypatch.setattr(crm_slozky, "najdi_slozku", rozbite)
    db = FakeSession()

    crm_slozky.naplanuj(db, crm_slozky.ENTITA_OP, 42)  # nesmí vyhodit

    assert db.rollbacky == 1


# ---- zpracování úlohy workerem ----------------------------------------------
def test_zpracuj_job_smazany_zaznam_preskoci(monkeypatch):
    """Záznam mezitím někdo smazal → není chyba, jen už není co zakládat.
    Kdyby to vyhodilo výjimku, úloha skončí ve `failed` a hlásí problém,
    se kterým nikdo nic neudělá."""
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    db = FakeSession()  # `get` vrací vždy None

    assert crm_slozky.zpracuj_job(db, {"entita": crm_slozky.ENTITA_ZAKAZNIK, "id": 9}) == {
        "skip": True
    }


def test_zpracuj_job_neznama_entita_je_chyba(monkeypatch):
    """Překlep v klíči entity musí být vidět, ne tiše přeskočen."""
    monkeypatch.setattr(crm_slozky, "najdi_slozku", lambda db, e, i: None)
    with pytest.raises(ValueError):
        crm_slozky.zpracuj_job(FakeSession(), {"entita": "crm_neco", "id": 1})
