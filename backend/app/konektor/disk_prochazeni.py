"""Procházení firemního Google Disku od kořenové složky konektoru.

Modul „Disk" v Agendě. Na kartě zákazníka i případu se už dá procházet složka
toho jednoho záznamu (`crm_slozky.obsah_slozky`) — tohle je totéž o úroveň výš:
**celý firemní Disk od složky, která je nastavená v konektoru**, dolů až
k jednotlivému souboru.

---- Proč vlastní modul a ne rozšíření `crm_slozky` -----------------------

`crm_slozky` je celé postavené na jednom záznamu: bere `KonektorEntityFolder`
a všechno kontroluje proti jeho složce. Tady žádný záznam není — kořen je
`google_root_folder_id` z nastavení konektoru. Kdyby se to natlačilo do téže
funkce, musela by mít dva režimy s jinou bezpečnostní kontrolou v každém, což
je přesně ten druh větvení, kde se jednou omylem vypne ta kontrola.

---- Bezpečnost ----------------------------------------------------------

`folder_id` chodí z prohlížeče, takže se u **každého** požadavku ověřuje, že
požadovaná složka leží pod kořenem konektoru (`crm_slozky.je_pod_slozkou`).
Bez toho by stačilo dosadit cizí ID a appka by posloužila jako čtečka celého
Google Disku firmy včetně věcí, které na Disku leží mimo CRM (mzdy, smlouvy).

Kořen konektoru je tedy zároveň **strop viditelnosti** — kdo má právo `disk`,
vidí právě to, co je pod ním, nic výš.

---- Nic se necachuje ----------------------------------------------------

Obsah se čte z Disku při každém kliknutí, stejně jako na kartě záznamu. Kopie
v naší DB by tvrdila, že tam soubor je, i když ho někdo mezitím smazal — a nikdo
by nepoznal, které tvrzení platí.
"""

from sqlalchemy.orm import Session

from app.konektor import crm_slozky, logika
from app.konektor.google_klient import DriveClient
from app.konektor.models import KonektorNastaveni

# Kolik položek se pošle do prohlížeče na jednu složku. Vyšší strop než u karty
# záznamu (60): kořenová složka má jednu podsložku na klienta (k 1. 8. 2026 jich
# je 453), takže při šedesáti by se seznam klientů utnul v polovině abecedy.
# Filtrování si dělá frontend nad tímhle seznamem, proto musí být celý.
LIMIT_POLOZEK = 1000


def _koren_id(n: KonektorNastaveni) -> str:
    """Odkud se prochází. Bez nastavené složky bereme celý sdílený disk.

    U Shared Drive platí, že ID disku = ID jeho kořenové složky, takže se s ním
    dá pracovat stejně jako s obyčejnou složkou.
    """
    return n.google_root_folder_id or n.google_shared_drive_id


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
    koren = _koren_id(n)
    if not koren:
        raise logika.NastaveniNepripraveno(
            "V konektoru není nastavená kořenová složka ani sdílený disk."
        )
    return n, crm_slozky._drive_klient(n), koren


def koren(db: Session) -> dict:
    """Kořenová složka konektoru — název a odkaz na Disk pro první obrazovku."""
    _, drive, koren_id = _priprav(db)
    f = drive.get_file(koren_id)
    return {"id": koren_id, "nazev": f.get("name") or "Disk", "url": _odkaz(f)}


def obsah(db: Session, folder_id: str | None = None, limit: int = LIMIT_POLOZEK) -> dict:
    """Obsah složky + cesta ke kořeni pro drobečkovou navigaci.

    `folder_id` prázdné = kořen konektoru. Jinak se nejdřív ověří, že složka
    leží pod kořenem (viz hlavička modulu) — teprve pak se cokoli čte.

    Každá položka i každý krok cesty nese `url` na Disk. Dan to chtěl výslovně:
    „na každé úrovni kde kliknu chci mít možnost nechat se přesměrovat na disk."
    """
    _, drive, koren_id = _priprav(db)
    cil = folder_id or koren_id
    if folder_id and not crm_slozky.je_pod_slozkou(drive, folder_id, koren_id):
        raise PermissionError("Tato složka neleží pod kořenovou složkou konektoru.")

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

    # Cesta se skládá odzadu přes rodiče a končí u kořene (ten se do ní nedává —
    # frontend ho kreslí jako první, vždy přítomný krok).
    cesta: list[dict] = []
    if cil != koren_id:
        aktualni = cil
        for _ in range(crm_slozky.MAX_HLOUBKA_KONTROLY):
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
