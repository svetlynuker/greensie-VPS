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

* **Právo `disk` je jediná branka.** Dřív se vedle práva koukalo i na
  „přepínač novinek", takže přidělené právo samo modul neotevřelo. Kdyby se
  druhá podmínka vrátila, přidělování práv přestane fungovat a nikdo nepozná
  proč — proto se testuje, že právo samo stačí.

Bez DB a bez Googlu: `_nastaveni` i Drive klient se podstrkují monkeypatchem.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.konektor import crm_slozky, disk_prochazeni
from app.konektor.disk_routes import vyzaduj_disk
from app.konektor.google_klient import FOLDER_MIME

KOREN = "koren123"  # kořen konektoru (google_root_folder_id)
STROP = "strop123"  # složka o úroveň výš – odsud modul začíná


class FakeDrive:
    """Minimální Disk: strom složek a souborů v paměti.

    `deti` = {id rodiče: [id položek]}, `polozky` = {id: položka} pro `get_file`.
    Položky mají tvar odpovědi Drive API, ať se testuje totéž, co poteče z Googlu.
    `nahrane` sbírá, co si modul přál nahrát a kam.
    """

    def __init__(self, polozky: dict[str, dict], deti: dict[str, list[str]]):
        self.polozky = polozky
        self.deti = deti
        self.nahrane: list[tuple[str, str, bytes, str]] = []
        self.zalozene: list[tuple[str, str]] = []
        self.sdilene: list[tuple[str, str, str, bool]] = []
        self.zrusene: list[tuple[str, str]] = []
        # {id položky: [oprávnění ve tvaru Drive API]}
        self.opravneni: dict[str, list[dict]] = {}

    def get_file(self, file_id: str) -> dict:
        if file_id not in self.polozky:
            raise RuntimeError(f"neznámé id {file_id}")
        return self.polozky[file_id]

    def list_children_vse(self, parent_id: str) -> list[dict]:
        return [self.polozky[i] for i in self.deti.get(parent_id, [])]

    def upload_file(self, name: str, parent_id: str, data: bytes, mime: str) -> dict:
        self.nahrane.append((name, parent_id, data, mime))
        return {
            "id": f"novy-{len(self.nahrane)}",
            "name": name,
            "webViewLink": f"https://drive/novy-{len(self.nahrane)}",
        }

    def create_folder(self, name: str, parent_id: str) -> dict:
        self.zalozene.append((name, parent_id))
        return {
            "id": f"slozka-{len(self.zalozene)}",
            "name": name,
            "webViewLink": f"https://drive/slozka-{len(self.zalozene)}",
        }

    def prava(self, file_id: str) -> list[dict]:
        return self.opravneni.get(file_id, [])

    def pridej_pravo(self, file_id: str, email: str, role: str, oznamit: bool = False) -> dict:
        self.sdilene.append((file_id, email, role, oznamit))
        return {"id": f"perm-{len(self.sdilene)}", "emailAddress": email, "role": role}

    def smaz_pravo(self, file_id: str, permission_id: str) -> None:
        self.zrusene.append((file_id, permission_id))

    def stahni(self, file_id: str) -> bytes:
        return f"binarni obsah {file_id}".encode()

    def exportuj(self, file_id: str, mime: str) -> bytes:
        return f"export {file_id} jako {mime}".encode()


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
    """Strop (`8. Raynet`) → kořen konektoru → klient → případ (+ soubory).

    Vedle kořene konektoru leží sesterská složka (`2. formuláře`) — právě pro ni
    se výchozí složka posunula o úroveň výš. A mimo strop leží složka, kterou
    appka nesmí ani vypsat, ani do ní nahrát.
    """
    polozky = {
        "sdileny": _slozka("sdileny", "Greensie disk", None),
        # Strop schválně bez webViewLink – Drive ho u některých složek nevrátí.
        STROP: _slozka(STROP, "8. Raynet", "sdileny"),
        KOREN: _slozka(KOREN, "1. zákazníci", STROP, "https://drive/koren"),
        "formulare": _slozka("formulare", "2. formuláře", STROP, "https://drive/form"),
        "klient": _slozka("klient", "Alfa s.r.o. [7]", KOREN, "https://drive/klient"),
        "op": _slozka("op", "OP-26-0301 - FVE", "klient", "https://drive/op"),
        "zz": _soubor("zz", "zaloha.pdf", "op", "2048"),
        "aa": _soubor("aa", "smlouva.pdf", "op", "1024"),
        "pod": _slozka("pod", "3. nabidka", "op", "https://drive/pod"),
        # Mimo strop – tohle appka nesmí vypsat ani na přímé zadání ID.
        "mzdy": _slozka("mzdy", "Mzdy", "jinykoren", "https://drive/mzdy"),
        "jinykoren": _slozka("jinykoren", "Personalistika", None),
    }
    deti = {
        "sdileny": [STROP],
        STROP: [KOREN, "formulare"],
        KOREN: ["klient"],
        "klient": ["op"],
        # Schválně v „špatném" pořadí: soubor, soubor, složka.
        "op": ["zz", "aa", "pod"],
        "jinykoren": ["mzdy"],
    }
    return FakeDrive(polozky, deti)


SLUZEBNI = "konektor@greensie.cz"


@pytest.fixture
def disk(monkeypatch):
    drive = _drive()
    # Typický stav u složky případu: náš člověk přidaný zvlášť, zákazník zvenčí,
    # zděděné oprávnění z klienta a service account konektoru.
    drive.opravneni["op"] = [
        {"id": "p1", "type": "user", "role": "writer", "emailAddress": "tomas@greensie.cz"},
        {"id": "p2", "type": "user", "role": "reader", "emailAddress": "klient@firma.cz"},
        {
            "id": "p3",
            "type": "user",
            "role": "reader",
            "emailAddress": "vedeni@greensie.cz",
            "permissionDetails": [{"inherited": True, "inheritedFrom": KOREN, "role": "reader"}],
        },
        {"id": "p4", "type": "user", "role": "writer", "emailAddress": SLUZEBNI},
    ]
    n = SimpleNamespace(
        google_root_folder_id=KOREN,
        google_shared_drive_id="sdileny",
        google_subject_email=SLUZEBNI,
    )
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    monkeypatch.setattr(crm_slozky, "_drive_klient", lambda nast: drive)
    # zaloguj by sahal na DB; obsah logu hlídá test níž zvlášť.
    monkeypatch.setattr(disk_prochazeni, "zaloguj", lambda *a, **k: None)
    return drive


# ---- výchozí složka: o úroveň výš nad kořenem konektoru ----------------------
def test_vychozi_slozka_je_o_uroven_vys_nad_korenem(disk):
    """Danovo zadání z 1. 8. 2026: první obrazovka je nadřazená složka.

    Kdyby se sem vrátil kořen konektoru, formuláře a návody by z appky nebyly
    dosažitelné vůbec.
    """
    d = disk_prochazeni.obsah(None, None)
    assert d["je_koren"] is True
    assert d["folder_id"] == STROP
    assert d["nazev"] == "8. Raynet"
    assert [p["nazev"] for p in d["polozky"]] == ["1. zákazníci", "2. formuláře"]
    assert d["cesta"] == [], "Ve výchozí složce není co v cestě zkracovat."


def test_sesterska_slozka_korene_je_pristupna(disk):
    """To je celý smysl posunu o úroveň výš."""
    d = disk_prochazeni.obsah(None, "formulare")
    assert d["nazev"] == "2. formuláře"


def test_cesta_vede_az_ke_stropu(disk):
    d = disk_prochazeni.obsah(None, "op")
    assert [k["nazev"] for k in d["cesta"]] == [
        "1. zákazníci",
        "Alfa s.r.o. [7]",
        "OP-26-0301 - FVE",
    ], "Cesta musí obsahovat i kořen konektoru – ten už je teď běžná úroveň."


# ---- strop viditelnosti ------------------------------------------------------
def test_slozka_mimo_strop_se_nevypise(disk):
    """Cizí ID z prohlížeče = 403, ne výpis. Jinak je appka čtečka celého Disku."""
    with pytest.raises(PermissionError):
        disk_prochazeni.obsah(None, "mzdy")


def test_slozka_pod_stropem_se_vypise(disk):
    d = disk_prochazeni.obsah(None, "op")
    assert d["nazev"] == "OP-26-0301 - FVE"
    assert [p["nazev"] for p in d["polozky"]] == ["3. nabidka", "smlouva.pdf", "zaloha.pdf"], (
        "Složky musí být první a pak soubory podle názvu – člověk hledá cestu dolů."
    )


def test_bez_korenove_slozky_padne_zpet_na_sdileny_disk():
    """Bez nastavené složky je stropem sdílený disk – výš se stoupat nedá."""
    n = SimpleNamespace(google_root_folder_id="", google_shared_drive_id="sdileny")
    assert disk_prochazeni._strop_id(_drive(), n) == "sdileny"


def test_koren_bez_rodice_zustava_stropem_sam():
    """Kořen konektoru = kořen sdíleného disku → není kam jít výš."""
    drive = _drive()
    n = SimpleNamespace(google_root_folder_id="jinykoren", google_shared_drive_id="sdileny")
    assert disk_prochazeni._strop_id(drive, n) == "jinykoren"


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
    assert [k["nazev"] for k in d["cesta"]] == [
        "1. zákazníci",
        "Alfa s.r.o. [7]",
        "OP-26-0301 - FVE",
        "3. nabidka",
    ]
    assert all(k["url"] for k in d["cesta"]), (
        "Každý krok cesty nese odkaz na Disk – to je Danovo zadání „na každé úrovni“."
    )
    obsah_op = disk_prochazeni.obsah(None, "op")
    assert all(p["url"] for p in obsah_op["polozky"])


def test_vychozi_slozka_bez_weblinku_dostane_zaloznu_adresu(disk):
    """Drive `webViewLink` u některých složek nevrátí – odkaz se skládá z ID."""
    k = disk_prochazeni.koren(None)
    assert k["url"] == f"https://drive.google.com/drive/folders/{STROP}"
    assert k["nazev"] == "8. Raynet"


def test_velikost_souboru_se_prevadi_na_cislo(disk):
    soubory = {p["nazev"]: p for p in disk_prochazeni.obsah(None, "op")["polozky"]}
    assert soubory["smlouva.pdf"]["velikost"] == 1024
    assert soubory["3. nabidka"]["velikost"] is None, "Složka velikost nemá."


def test_zkraceni_dlouhe_slozky_se_hlasi(disk):
    d = disk_prochazeni.obsah(None, "op", limit=1)
    assert len(d["polozky"]) == 1
    assert d["zkraceno"] is True, "Utnutý výpis se musí přiznat, jinak to vypadá na smazané soubory."


# ---- nahrávání ---------------------------------------------------------------
def test_nahrani_jde_do_otevrene_slozky(disk):
    v = disk_prochazeni.nahraj(None, "op", "nabidka.pdf", b"data", "application/pdf")
    assert disk.nahrane == [("nabidka.pdf", "op", b"data", "application/pdf")]
    assert v["url"], "Nahraný soubor musí jít hned otevřít na Disku."


def test_nahrani_bez_slozky_padne_do_vychozi(disk):
    """Prohlížeč posílá prázdné id, backend si výchozí složku dosadí sám."""
    disk_prochazeni.nahraj(None, None, "poznamka.txt", b"x", "text/plain")
    assert disk.nahrane[0][1] == STROP


def test_nahrani_mimo_strop_neprojde(disk):
    """Stejná kontrola jako u čtení – jinak by appka zapisovala kamkoli na Disk."""
    with pytest.raises(PermissionError):
        disk_prochazeni.nahraj(None, "mzdy", "vir.exe", b"x", "application/octet-stream")
    assert disk.nahrane == [], "Do cizí složky se nesmí dostat ani jeden bajt."


def test_nazev_souboru_se_ocisti(disk):
    """Lomítka v názvu Drive nemá rád – jdou přes `logika._bezpecny_nazev` na „-".

    Zároveň to znamená, že název z prohlížeče nemůže naznačit cestu jinam:
    „../tajne/smlouva.pdf" skončí jako jeden název souboru, ne jako cesta.
    """
    disk_prochazeni.nahraj(None, "op", "../tajne/smlouva.pdf", b"x", "application/pdf")
    ulozeny, kam, _, _ = disk.nahrane[0]
    assert "/" not in ulozeny
    assert ulozeny == "..-tajne-smlouva.pdf"
    assert kam == "op", "Cíl určuje folder_id, nikdy název souboru."


def test_nahrani_se_zaloguje(monkeypatch):
    """Zápis na firemní Disk musí být dohledatelný – jinak nikdo nezjistí, kdo co přidal."""
    drive = _drive()
    n = SimpleNamespace(google_root_folder_id=KOREN, google_shared_drive_id="sdileny")
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    monkeypatch.setattr(crm_slozky, "_drive_klient", lambda nast: drive)
    zapsano: list[tuple] = []
    monkeypatch.setattr(
        disk_prochazeni, "zaloguj", lambda db, uroven, kod, zprava, detail=None: zapsano.append(
            (uroven, kod, zprava, detail)
        )
    )
    disk_prochazeni.nahraj(None, "op", "smlouva.pdf", b"x", "application/pdf", "dan@greensie.cz")
    assert len(zapsano) == 1
    uroven, kod, zprava, detail = zapsano[0]
    assert (uroven, kod) == ("info", "disk_nahrani")
    assert "smlouva.pdf" in zprava
    assert detail["folder_id"] == "op"
    assert detail["uzivatel"] == "dan@greensie.cz", (
        "Zápis na firemní Disk musí nést, kdo ho udělal – `konektor_log` na to sloupec nemá."
    )


# ---- zakládání složek --------------------------------------------------------
def test_slozka_vznikne_v_otevrene_slozce(disk):
    v = disk_prochazeni.zaloz_slozku(None, "op", "5. revize", "dan@greensie.cz")
    assert disk.zalozene == [("5. revize", "op")]
    assert v["nazev"] == "5. revize" and v["url"]


def test_slozka_bez_rodice_vznikne_ve_vychozi(disk):
    disk_prochazeni.zaloz_slozku(None, None, "9. archiv")
    assert disk.zalozene[0][1] == STROP


def test_slozka_mimo_strop_nevznikne(disk):
    with pytest.raises(PermissionError):
        disk_prochazeni.zaloz_slozku(None, "mzdy", "moje")
    assert disk.zalozene == []


def test_slozka_bez_nazvu_neprojde(disk):
    """Prázdný název by na Disku udělal složku „beze-jmena" – to nikdo nechtěl."""
    for nazev in ("", "   ", "\t\n"):
        with pytest.raises(ValueError):
            disk_prochazeni.zaloz_slozku(None, "op", nazev)
    assert disk.zalozene == []


def test_nazev_slozky_nemuze_byt_cesta(disk):
    """Lomítka jdou na „-", takže „a/b" je jedna složka, ne dvě zanořené."""
    disk_prochazeni.zaloz_slozku(None, "op", "2026/revize")
    assert disk.zalozene == [("2026-revize", "op")]


# ---- náhled souboru v appce --------------------------------------------------
def test_binarni_soubor_jde_tak_jak_je(disk):
    data, mime, nazev = disk_prochazeni.nahled(None, "aa")
    assert data == b"binarni obsah aa"
    assert mime == "application/pdf"
    assert nazev == "smlouva.pdf"


def test_google_dokument_se_exportuje_do_pdf(disk):
    """Google formáty binární obsah nemají – bez exportu by je appka neukázala."""
    disk.polozky["gdoc"] = {
        "id": "gdoc",
        "name": "Zápis z jednání",
        "mimeType": "application/vnd.google-apps.document",
        "parents": ["op"],
    }
    disk.deti["op"].append("gdoc")
    data, mime, nazev = disk_prochazeni.nahled(None, "gdoc")
    assert mime == "application/pdf"
    assert nazev == "Zápis z jednání.pdf", "Přípona musí odpovídat tomu, co se posílá."
    assert b"export" in data


def test_nahled_mimo_strop_neprojde(disk):
    """Nejdůležitější kontrola modulu: bez ní by `file_id` z adresy stáhlo cokoli."""
    disk.polozky["tajny"] = _soubor("tajny", "mzdy-2026.xlsx", "mzdy", "5000")
    with pytest.raises(PermissionError):
        disk_prochazeni.nahled(None, "tajny")


def test_slozka_nahled_nema(disk):
    with pytest.raises(ValueError):
        disk_prochazeni.nahled(None, "pod")


def test_velky_soubor_se_posila_na_disk(disk):
    disk.polozky["velky"] = _soubor("velky", "video.mp4", "op", str(60 * 1024 * 1024))
    with pytest.raises(ValueError):
        disk_prochazeni.nahled(None, "velky")


def test_vypis_rika_co_appka_umi_zobrazit(disk):
    """Prohlížeč se nesmí rozhodovat podle přípony – ví to jen backend."""
    disk.polozky["zip"] = _soubor("zip", "podklady.zip", "op", "9999")
    disk.polozky["zip"]["mimeType"] = "application/zip"
    disk.deti["op"].append("zip")
    polozky = {p["nazev"]: p for p in disk_prochazeni.obsah(None, "op")["polozky"]}
    assert polozky["smlouva.pdf"]["lze_nahled"] is True
    assert polozky["podklady.zip"]["lze_nahled"] is False
    assert polozky["3. nabidka"]["lze_nahled"] is False, "Do složky se vchází, nenahlíží."


# ---- sdílení položek na Disku -------------------------------------------------
def test_vypis_sdileni_oznaci_zdedene_sluzebni_i_noveho(disk):
    """Tři příznaky, na kterých závisí, co appka nabídne odebrat a před čím varuje.

    Kdyby zmizely, lidé by klikali na „odebrat" u zděděného oprávnění (Google to
    odmítne) nebo by si odebrali konektor a rozbili synchronizaci.
    """
    d = disk_prochazeni.prava(None, "op")
    podle = {c["email"]: c for c in d["lide"]}
    assert podle["tomas@greensie.cz"]["zdedene"] is False
    assert podle["klient@firma.cz"]["novy"] is True, "Na disku nikde jinde přístup nemá."
    assert podle["vedeni@greensie.cz"]["zdedene"] is True
    assert podle[SLUZEBNI]["sluzebni"] is True
    assert d["role"] == ["reader", "commenter", "writer"], "Owner ani organizer appka nenabízí."


def test_novy_clovek_se_nepozna_podle_domeny(disk):
    """Tým používá vlastní gmaily – doménová kontrola označila 17 z 20 kolegů.

    Varování, které svítí vždycky, si člověk odvykne čítat, takže rozhoduje
    členství na Disku, ne text za zavináčem.
    """
    disk.opravneni[STROP] = [
        {"id": "s1", "type": "user", "role": "writer", "emailAddress": "kolega@gmail.com"},
    ]
    d = disk_prochazeni.prava(None, "op")
    podle = {c["email"]: c for c in d["lide"]}
    assert podle["klient@firma.cz"]["novy"] is True
    assert "kolega@gmail.com" in d["znami"], "Prohlížeč z toho pozná, koho už disk zná."

    # Kolega z gmailu, který je členem disku, se za nového nepočítá.
    disk.opravneni["op"].append(
        {"id": "p9", "type": "user", "role": "reader", "emailAddress": "kolega@gmail.com"}
    )
    podle = {c["email"]: c for c in disk_prochazeni.prava(None, "op")["lide"]}
    assert podle["kolega@gmail.com"]["novy"] is False


def test_sdileni_se_da_pridat(disk):
    disk.opravneni[STROP] = [
        {"id": "s1", "type": "user", "role": "writer", "emailAddress": "kdo@greensie.cz"},
    ]
    v = disk_prochazeni.pridej_pravo(None, "op", " kdo@greensie.cz ", "writer", False, "dan@x.cz")
    assert disk.sdilene == [("op", "kdo@greensie.cz", "writer", False)]
    assert v["novy"] is False, "Disk ho zná, tedy nic k varování."
    assert v["pozadovana_role"] == "writer" and v["role"] == "writer"


def test_vyssi_role_ze_disku_se_neprepise_a_appka_to_rekne(disk, monkeypatch):
    """Reálný případ: kolega má ze sdíleného disku „upravovat", dostane „číst".

    Google vrátí stávající (vyšší) oprávnění a nic nepřepíše. Kdyby appka
    tvrdila „nasdíleno jako může číst", byla by to lež, kterou nikdo neodhalí,
    dokud na tom nezáleží.
    """
    monkeypatch.setattr(
        disk,
        "pridej_pravo",
        lambda file_id, email, role, oznamit=False: {
            "id": "p-existing",
            "emailAddress": email,
            "role": "writer",  # Disk vrátí, co tam už je
        },
    )
    v = disk_prochazeni.pridej_pravo(None, "op", "tomas@greensie.cz", "reader")
    assert v["role"] == "writer"
    assert v["pozadovana_role"] == "reader", "Prohlížeč z rozdílu pozná, že má říct pravdu."


def test_neplatna_adresa_a_role_neprojdou(disk):
    for email in ("", "bez-zavinace", "dva lidi@x.cz"):
        with pytest.raises(ValueError):
            disk_prochazeni.pridej_pravo(None, "op", email, "reader")
    with pytest.raises(ValueError):
        disk_prochazeni.pridej_pravo(None, "op", "kdo@greensie.cz", "owner")
    assert disk.sdilene == [], "Nic z toho se nesmělo dostat na Disk."


def test_sdileni_novemu_cloveku_se_loguje_jako_varovani(monkeypatch):
    """V Logech to má být vidět na první pohled – únik dokumentů začíná tady."""
    drive = _drive()
    drive.opravneni[STROP] = [
        {"id": "s1", "type": "user", "role": "writer", "emailAddress": "kolega@gmail.com"},
    ]
    n = SimpleNamespace(
        google_root_folder_id=KOREN, google_shared_drive_id="sdileny", google_subject_email=SLUZEBNI
    )
    monkeypatch.setattr(crm_slozky, "_nastaveni", lambda db: n)
    monkeypatch.setattr(crm_slozky, "_drive_klient", lambda nast: drive)
    zapsano: list[tuple] = []
    monkeypatch.setattr(
        disk_prochazeni,
        "zaloguj",
        lambda db, uroven, kod, zprava, detail=None: zapsano.append((uroven, kod, detail)),
    )
    disk_prochazeni.pridej_pravo(None, "op", "cizi@firma.cz", "reader", False, "dan@x.cz")
    uroven, kod, detail = zapsano[0]
    assert (uroven, kod) == ("warn", "disk_prava")
    assert detail["novy_clovek"] is True
    assert detail["uzivatel"] == "dan@x.cz"

    disk_prochazeni.pridej_pravo(None, "op", "kolega@gmail.com", "reader", False, "dan@x.cz")
    assert zapsano[1][0] == "info", "Kolega, kterého disk zná, je běžný provoz."


def test_sdileni_se_da_odebrat(disk):
    disk_prochazeni.odeber_pravo(None, "op", "p1", "dan@x.cz")
    assert disk.zrusene == [("op", "p1")]


def test_konektoru_se_pristup_odebrat_neda(disk):
    """Kdyby zmizel, přestane fungovat zakládání složek i celý modul."""
    with pytest.raises(ValueError):
        disk_prochazeni.odeber_pravo(None, "op", "p4")
    assert disk.zrusene == []


def test_zdedene_opravneni_se_odebrat_neda(disk):
    """Google to odmítne – appka to musí říct dřív a čitelněji."""
    with pytest.raises(ValueError) as e:
        disk_prochazeni.odeber_pravo(None, "op", "p3")
    assert "zděděné" in str(e.value)
    assert disk.zrusene == []


def test_neexistujici_opravneni_hlasi_chybu(disk):
    with pytest.raises(ValueError):
        disk_prochazeni.odeber_pravo(None, "op", "vymyslene")


def test_sdileni_mimo_strop_neprojde(disk):
    """Stejná hranice jako všude jinde – u sdílení o to víc."""
    for volani in (
        lambda: disk_prochazeni.prava(None, "mzdy"),
        lambda: disk_prochazeni.pridej_pravo(None, "mzdy", "kdo@greensie.cz", "reader"),
        lambda: disk_prochazeni.odeber_pravo(None, "mzdy", "p1"),
    ):
        with pytest.raises(PermissionError):
            volani()
    assert disk.sdilene == [] and disk.zrusene == []


def test_zmena_sdileni_ma_vlastni_pravo():
    """Právo `disk` na měnění sdílení nestačí — je to rozhodnutí, které jde i mimo firmu."""
    from app.auth.permissions import VSECHNA_PRAVA
    from app.konektor.disk_routes import vyzaduj_sdileni

    assert "disk_sdileni" in VSECHNA_PRAVA
    with pytest.raises(HTTPException) as e:
        vyzaduj_sdileni(_uzivatel(False, ["disk"]))
    assert e.value.status_code == 403, "403, ne 404: modul člověk vidí, jen na tohle nemá právo."
    u = _uzivatel(True, [])
    assert vyzaduj_sdileni(u) is u


# ---- práva a přepínač novinek ------------------------------------------------
def _uzivatel(admin: bool, prava: list[str]):
    return SimpleNamespace(je_admin=admin, extra_prava=prava, skupina=None)


def test_bez_prava_disk_neotevre():
    with pytest.raises(HTTPException) as e:
        vyzaduj_disk(_uzivatel(False, []))
    assert e.value.status_code == 403, "403, ne 404 – ať člověk ví, o jaké právo požádat."


def test_pravo_disk_staci_samo():
    """Právo `disk` modul otevře — bez supersprávce a bez druhé branky.

    Dřív tu byl vedle práva ještě „přepínač novinek", takže přidělené právo
    samo nic neotevřelo a jediná cesta dovnitř bylo dát člověku plná práva
    supersprávce. Kdyby se druhá podmínka vrátila, spadne tenhle test.
    """
    u = _uzivatel(False, ["disk"])
    assert vyzaduj_disk(u) is u


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
