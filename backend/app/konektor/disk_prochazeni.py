"""Procházení firemního Google Disku a nahrávání do něj.

Modul „Disk" v Agendě. Na kartě zákazníka i případu se už dá procházet složka
toho jednoho záznamu (`crm_slozky.obsah_slozky`) — tohle je totéž o dvě úrovně
výš: **firemní Disk od složky nad kořenem konektoru** (u nás `8. Raynet`), dolů
až k jednotlivému souboru, a s možností soubor nahrát do té složky, kde člověk
právě je.

---- Proč vlastní modul a ne rozšíření `crm_slozky` -----------------------

`crm_slozky` je celé postavené na jednom záznamu: bere `KonektorEntityFolder`
a všechno kontroluje proti jeho složce. Tady žádný záznam není — výchozí složka
se odvozuje z nastavení konektoru. Kdyby se to natlačilo do téže funkce, musela
by mít dva režimy s jinou bezpečnostní kontrolou v každém, což je přesně ten
druh větvení, kde se jednou omylem vypne ta kontrola.

---- Bezpečnost ----------------------------------------------------------

`folder_id` chodí z prohlížeče, takže se u **každého** požadavku (čtení i
nahrání) ověřuje, že složka leží pod **stropem** modulu — to je složka o úroveň
výš nad kořenem konektoru, viz `_strop_id`. Bez toho by stačilo dosadit cizí ID
a appka by posloužila jako čtečka (a zapisovačka) celého Google Disku firmy
včetně věcí, které leží mimo Raynet.

Strop je tedy hranice viditelnosti: kdo má právo `disk`, vidí právě to, co je
pod ním, nic výš a nic mimo.

---- Nic se necachuje ----------------------------------------------------

Obsah se čte z Disku při každém kliknutí, stejně jako na kartě záznamu. Kopie
v naší DB by tvrdila, že tam soubor je, i když ho někdo mezitím smazal — a nikdo
by nepoznal, které tvrzení platí.
"""

from sqlalchemy.orm import Session

from app.konektor import crm_slozky, logika
from app.konektor.google_klient import DriveClient
from app.konektor.logger import zaloguj
from app.konektor.models import KonektorNastaveni

# Kolik položek se pošle do prohlížeče na jednu složku. Vyšší strop než u karty
# záznamu (60): kořenová složka má jednu podsložku na klienta (k 1. 8. 2026 jich
# je 453), takže při šedesáti by se seznam klientů utnul v polovině abecedy.
# Filtrování si dělá frontend nad tímhle seznamem, proto musí být celý.
LIMIT_POLOZEK = 1000

# Kolik úrovní se leze nahoru při kontrole „leží to pod stropem" a při skládání
# drobečkové cesty. Vlastní konstanta, ne ta z `crm_slozky` (10): tam se počítá
# od složky záznamu, tady od složky o dvě úrovně výš (strop → klient → případ →
# …), takže deset by u hlouběji zanořených souborů nedosáhlo a kontrola by je
# odmítla jako „mimo strop".
MAX_HLOUBKA = 14

# Strop pro nahrávaný soubor. Stejný jako na kartě záznamu a ze stejného důvodu:
# soubor se drží celý v paměti web procesu, takže velké věci (fotodokumentace)
# patří na Disk přímo — při 502 z Hetzneru by se sem stejně nedonesly.
MAX_SOUBOR_B = 25 * 1024 * 1024


def _strop_id(drive: DriveClient, n: KonektorNastaveni) -> str:
    """Odkud modul začíná: **složka o úroveň výš nad kořenem konektoru**.

    Rozhodnutí Dana (1. 8. 2026): první obrazovka má být nadřazená složka, ne
    kořen konektoru — u nás tedy `8. Raynet` místo `1. zákazníci`. Vedle klientů
    tam leží i formuláře, interní dokumentace a návody, a právě pro ty se to
    dělá; jinak by se k nim z appky nedalo dostat.

    Odvozuje se **z rodiče na Disku**, ne z dalšího políčka v nastavení: kořen
    konektoru je jediná věc, kterou Dan nastavuje, a druhé políčko by se s ním
    mohlo rozejít (a pak by nikdo nevěděl, které platí).

    Když rodič neexistuje (kořen konektoru je sám kořenem sdíleného disku) nebo
    ho Drive neřekne, zůstává stropem kořen konektoru — výš než na sdílený disk
    se stoupat nedá.
    """
    zaklad = n.google_root_folder_id or n.google_shared_drive_id
    if not zaklad:
        return ""
    if not n.google_root_folder_id:
        return zaklad
    try:
        rodice = drive.get_file(n.google_root_folder_id).get("parents") or []
    except Exception:  # noqa: BLE001 – nedostupný rodič nesmí modul shodit
        rodice = []
    return rodice[0] if rodice else zaklad


def _odkaz(f: dict) -> str:
    """URL na položku na Disku.

    `webViewLink` Drive u kořene sdíleného disku občas nevrátí, a právě tam ten
    odkaz potřebujeme nejvíc (je to první obrazovka modulu). Skládá se proto
    záložní adresa z ID — to je tvar, na který Disk umí přesměrovat sám.
    """
    if f.get("webViewLink"):
        return f["webViewLink"]
    if f.get("mimeType") == logika.FOLDER_MIME and f.get("id"):
        return f"https://drive.google.com/drive/folders/{f['id']}"
    if f.get("id"):
        return f"https://drive.google.com/file/d/{f['id']}/view"
    return ""


def _priprav(db: Session) -> tuple[KonektorNastaveni, DriveClient, str]:
    n = crm_slozky._nastaveni(db)
    if not (n.google_root_folder_id or n.google_shared_drive_id):
        raise logika.NastaveniNepripraveno(
            "V konektoru není nastavená kořenová složka ani sdílený disk."
        )
    drive = crm_slozky._drive_klient(n)
    strop = _strop_id(drive, n)
    if not strop:
        raise logika.NastaveniNepripraveno("Nepodařilo se určit výchozí složku na Disku.")
    return n, drive, strop


def _pod_stropem(drive: DriveClient, folder_id: str, strop: str) -> bool:
    """Leží složka pod stropem modulu? Vlastní hloubka, jinak totéž co u záznamu."""
    return crm_slozky.je_pod_slozkou(drive, folder_id, strop, MAX_HLOUBKA)


def koren(db: Session) -> dict:
    """Výchozí složka modulu (o úroveň výš nad kořenem konektoru) + odkaz na Disk."""
    _, drive, strop = _priprav(db)
    f = drive.get_file(strop)
    return {"id": strop, "nazev": f.get("name") or "Disk", "url": _odkaz(f)}


def obsah(db: Session, folder_id: str | None = None, limit: int = LIMIT_POLOZEK) -> dict:
    """Obsah složky + cesta ke stropu pro drobečkovou navigaci.

    `folder_id` prázdné = výchozí složka modulu. Jinak se nejdřív ověří, že
    složka leží pod stropem (viz hlavička modulu) — teprve pak se cokoli čte.

    Každá položka i každý krok cesty nese `url` na Disk. Dan to chtěl výslovně:
    „na každé úrovni kde kliknu chci mít možnost nechat se přesměrovat na disk."
    """
    _, drive, koren_id = _priprav(db)
    cil = folder_id or koren_id
    if folder_id and not _pod_stropem(drive, folder_id, koren_id):
        raise PermissionError("Tato složka neleží pod výchozí složkou modulu Disk.")

    tady = drive.get_file(cil)
    polozky = [
        {
            "id": f.get("id"),
            "nazev": f.get("name") or "",
            "je_slozka": f.get("mimeType") == logika.FOLDER_MIME,
            "url": _odkaz(f),
            "velikost": int(f["size"]) if f.get("size") else None,
        }
        # `list_children_vse`, ne `list_children`: ta bere jen první stránku
        # (1000 položek) a utnutý konec abecedy by se neprojevil chybou.
        for f in drive.list_children_vse(cil)
        if not f.get("trashed")
    ]
    # Složky nahoru, pak soubory — obojí podle názvu. Člověk hledá cestu dolů,
    # ne soubor promíchaný mezi podsložkami.
    polozky.sort(key=lambda x: (not x["je_slozka"], x["nazev"].lower()))

    # Cesta se skládá odzadu přes rodiče a končí u stropu (ten se do ní nedává —
    # frontend ho kreslí jako první, vždy přítomný krok).
    cesta: list[dict] = []
    if cil != koren_id:
        aktualni = cil
        for _ in range(MAX_HLOUBKA):
            try:
                f = drive.get_file(aktualni)
            except Exception:  # noqa: BLE001 – rozbitá cesta nesmí shodit výpis
                break
            cesta.insert(0, {"id": f.get("id"), "nazev": f.get("name") or "", "url": _odkaz(f)})
            rodice = f.get("parents") or []
            if not rodice or koren_id in rodice:
                break
            aktualni = rodice[0]

    return {
        "folder_id": cil,
        "nazev": tady.get("name") or "",
        "url": _odkaz(tady),
        "je_koren": cil == koren_id,
        "cesta": cesta,
        "polozky": polozky[:limit],
        "zkraceno": len(polozky) > limit,
    }


def nahraj(
    db: Session, folder_id: str | None, nazev: str, data: bytes, mime: str, uzivatel: str = ""
) -> dict:
    """Nahraje soubor do právě otevřené složky na Disku.

    Rozhodnutí Dana (1. 8. 2026): nahrávat se má i odsud, ne jen z karty
    záznamu. Původní úvaha byla, že soubor „někam do firemního Disku" nemá
    majitele — ale ve složkách jako `2. formuláře` nebo `4. návody` žádný záznam
    v CRM neexistuje a přesto tam soubory patří.

    **Soubor u nás nezůstane.** Projde do Disku a v appce je jen odkaz; dvě kopie
    téhož dokumentu by znamenaly, že nikdo neví, která platí.

    Stejná kontrola jako u čtení — cílová složka musí ležet pod stropem modulu,
    jinak by se přes appku dalo zapisovat kamkoli na Disk.

    `uzivatel` jde do kontextu logu. Tabulka `konektor_log` sloupec pro člověka
    nemá (píše do ní automatika, ne lidé), ale zápis na firemní Disk je akce
    člověka — a „kdo to tam dal" je první otázka, kterou se někdo zeptá.
    """
    _, drive, strop = _priprav(db)
    cil = folder_id or strop
    if folder_id and not _pod_stropem(drive, folder_id, strop):
        raise PermissionError("Tato složka neleží pod výchozí složkou modulu Disk.")

    f = drive.upload_file(
        logika._bezpecny_nazev(nazev), cil, data, mime or "application/octet-stream"
    )
    zaloguj(
        db,
        "info",
        "disk_nahrani",
        f"Nahrán soubor '{nazev}' z modulu Disk.",
        {"folder_id": cil, "file_id": f.get("id"), "uzivatel": uzivatel or "?"},
    )
    return {"id": f.get("id"), "nazev": f.get("name"), "url": _odkaz(f)}
