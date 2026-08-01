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

# Totéž pro náhled: soubor se stahuje z Disku do paměti a posílá do prohlížeče.
# Nad tímhle stropem se náhled nenabízí a člověk jde na Disk — několik lidí,
# kteří si naráz otevřou stometrové video, by web proces uspalo.
MAX_NAHLED_B = 25 * 1024 * 1024

# Google formáty (Docs/Sheets/Slides) nemají binární obsah — do náhledu se
# převádějí na PDF. Prezentace a tabulky v PDF nejsou ideální na čtení, ale je to
# jediný tvar, který umí Google vyexportovat a prohlížeč zobrazit bez pluginu.
EXPORT_PDF = "application/pdf"
GOOGLE_PREFIX = "application/vnd.google-apps."

# Co se v appce dá reálně ukázat. Ostatní typy (zipy, dwg, videa) se nabídnou
# k uložení — tvářit se, že je appka umí zobrazit, by bylo horší než to přiznat.
NAHLED_PRIMO = ("application/pdf", "text/", "image/")


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


def _lze_nahled(f: dict) -> bool:
    """Dá se soubor ukázat v appce, nebo je to případ pro Disk?

    Google formáty ano (exportují se na PDF), z ostatních jen PDF, obrázky a text.
    Zip nebo dwg by prohlížeč jen nabídl k uložení, což z náhledu dělá past —
    člověk klikne „otevřít" a stáhne se mu soubor.
    """
    mime = f.get("mimeType") or ""
    if mime == logika.FOLDER_MIME:
        return False
    if int(f.get("size") or 0) > MAX_NAHLED_B:
        return False
    return mime.startswith(GOOGLE_PREFIX) or mime.startswith(NAHLED_PRIMO)


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
            # Aby prohlížeč věděl, jestli soubor otevřít v appce, nebo poslat na
            # Disk. Rozhodnout to musí backend: jen on ví, co umí vyexportovat.
            "lze_nahled": _lze_nahled(f),
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


def zaloz_slozku(
    db: Session, folder_id: str | None, nazev: str, uzivatel: str = ""
) -> dict:
    """Založí podsložku v právě otevřené složce.

    Rozhodnutí Dana (1. 8. 2026). Do téhle chvíle appka na Disku zakládala jen
    složky podle firemního vzoru (klient, obchodní případ) — tohle je obyčejná
    složka, kterou si člověk pojmenuje sám, protože ne všechno na Disku má
    předlohu.

    Kontrola stropu jako u zápisu souboru. Duplicitní název se **nehlídá**:
    Google Disk dvě složky téhož jména dovolí a appka za něj rozhodovat nemá —
    jen by se pak lidé divili, proč jim appka nedovolí, co Disk dovolí.
    """
    cisty = logika._bezpecny_nazev(nazev)
    if not cisty or cisty == "beze-jmena":
        raise ValueError("Složka musí mít název.")

    _, drive, strop = _priprav(db)
    cil = folder_id or strop
    if folder_id and not _pod_stropem(drive, folder_id, strop):
        raise PermissionError("Tato složka neleží pod výchozí složkou modulu Disk.")

    f = drive.create_folder(cisty, cil)
    zaloguj(
        db,
        "info",
        "disk_slozka",
        f"Založena složka '{cisty}' z modulu Disk.",
        {"parent_id": cil, "folder_id": f.get("id"), "uzivatel": uzivatel or "?"},
    )
    return {"id": f.get("id"), "nazev": f.get("name"), "url": _odkaz(f)}


# ---- sdílení položek -------------------------------------------------------
# Role, které smí appka nastavit. `owner` a `organizer` ne: na sdíleném disku
# rozdávají práva dál a odebrat je zpátky přes appku nejde. `commenter` je
# užitečný u smluv, kde má druhá strana psát poznámky, ale ne měnit obsah.
POVOLENE_ROLE = ("reader", "commenter", "writer")

def _znami(drive: DriveClient, strop: str) -> set[str]:
    """E-maily, které na Disku už přístup mají (členové sdíleného disku).

    Slouží k rozpoznání, že se dokument sdílí **někomu novému** — to je jediný
    okamžik, kdy má appka varovat.

    Původně se to zkoušelo podle domény (`@greensie.cz` = naše). Ukázalo se to
    jako slepá cesta: tým používá vlastní gmaily a seznam.cz, takže doménová
    kontrola označila 17 z 20 kolegů jako „mimo firmu". Varování, které svítí
    vždycky, si člověk odvykne čítat — a pak přehlédne to jediné důležité.
    """
    try:
        return {
            (p.get("emailAddress") or "").strip().lower()
            for p in drive.prava(strop)
            if p.get("emailAddress")
        }
    except Exception:  # noqa: BLE001 – bez seznamu se jen nevaruje, nesmí to spadnout
        return set()


def prava(db: Session, item_id: str) -> dict:
    """Kdo má k položce (složce i souboru) přístup na Disku.

    Rozhodnutí Dana (1. 8. 2026): sdílení se má dát vyřídit odsud, ne odchodem
    na Disk.

    Co se vrací a proč právě to:

    * `zdedene` — oprávnění, které položka dostala z nadřazené složky nebo ze
      samotného sdíleného disku. **Smazat ho na téhle úrovni nejde** (Google to
      odmítne), takže se posílá s příznakem a appka u něj tlačítko nenabídne.
      Bez toho by lidé klikali na „odebrat" a dostávali chybu.
    * `sluzebni` — service account konektoru. Kdyby si ho někdo odebral, přestane
      fungovat celý konektor (zakládání složek, synchronizace, i tento modul).
    * `novy` — e-mail, který na Disku jinak nikde není (zákazník, projektant).
      Není to chyba, ale musí to být vidět. Záměrně se to NEpozná podle domény:
      tým používá vlastní gmaily, takže doménová kontrola označila 17 z 20 kolegů
      a varování by ztratilo význam.
    """
    n, drive, strop = _priprav(db)
    if not _pod_stropem(drive, item_id, strop):
        raise PermissionError("Tato položka neleží pod výchozí složkou modulu Disk.")

    f = drive.get_file(item_id)
    sluzebni = (n.google_subject_email or "").strip().lower()
    znami = _znami(drive, strop)
    lidi = []
    for p in drive.prava(item_id):
        if p.get("deleted"):
            continue
        detaily = p.get("permissionDetails") or []
        email = (p.get("emailAddress") or "").strip()
        lidi.append(
            {
                "id": p.get("id"),
                "email": email,
                "jmeno": p.get("displayName") or "",
                "typ": p.get("type") or "",
                "role": p.get("role") or "",
                "zdedene": any(d.get("inherited") for d in detaily),
                "sluzebni": bool(sluzebni and email.lower() == sluzebni),
                # „Někdo, kdo na Disku jinak není" — typicky zákazník nebo
                # projektant. U zděděných to nemá smysl: ti JSOU členové disku.
                "novy": bool(email) and email.lower() not in znami,
            }
        )
    # Nejdřív ti, se kterými se dá něco udělat; zděděná a služební práva až pod
    # nimi, aby v seznamu nepřekrývala to, co člověk hledá.
    lidi.sort(key=lambda x: (x["zdedene"] or x["sluzebni"], x["email"].lower()))
    return {
        "id": item_id,
        "nazev": f.get("name") or "",
        "je_slozka": f.get("mimeType") == logika.FOLDER_MIME,
        "url": _odkaz(f),
        "lide": lidi,
        "role": list(POVOLENE_ROLE),
        # Prohlížeč z toho pozná, že se adresa v políčku sdílí někomu novému, a
        # varuje ještě před odesláním. Nejsou to citlivá data: tyhle e-maily jsou
        # v témže okně vidět v seznamu.
        "znami": sorted(znami),
    }


def pridej_pravo(
    db: Session,
    item_id: str,
    email: str,
    role: str,
    oznamit: bool = False,
    uzivatel: str = "",
) -> dict:
    """Přidá člověka k položce na Disku.

    Jen konkrétní e-mail — **žádné „kdokoli s odkazem"**. Veřejný odkaz na
    firemní dokument je věc, kterou nikdo nevzal zpět; když ho někdo opravdu
    potřebuje, udělá ho na Disku vědomě.

    Sdílení celé složky se dědí na všechno v ní. To je vlastnost Disku, ne naše,
    ale appka to musí říct nahlas — proto je to v hlášce i v manuálu.

    `oznamit` je u nás **zapnuté ve výchozím stavu**, a to kvůli reálnému stavu
    Disku: tým ho má pod vlastními gmaily, takže adresy `@greensie.cz` nemají
    účet Google a Google je bez pozvánky odmítne přidat vůbec.
    """
    cisty = (email or "").strip()
    if "@" not in cisty or " " in cisty:
        raise ValueError("Zadej e-mailovou adresu člověka, kterému se má sdílet.")
    if role not in POVOLENE_ROLE:
        raise ValueError(f"Neznámá role „{role}“.")

    _, drive, strop = _priprav(db)
    if not _pod_stropem(drive, item_id, strop):
        raise PermissionError("Tato položka neleží pod výchozí složkou modulu Disk.")

    novy = cisty.lower() not in _znami(drive, strop)
    try:
        p = drive.pridej_pravo(item_id, cisty, role, oznamit)
    except Exception as e:  # noqa: BLE001
        # Reálný případ z 1. 8. 2026: kolegové mají Disk pod vlastními gmaily,
        # takže adresy @greensie.cz nemají účet Google. Takovou adresu Google
        # odmítne pozvat bez oznámení e-mailem (`invalidSharingRequest`) — a
        # surová anglická chyba z Drive API by člověku neřekla, co udělat.
        if "invalidSharingRequest" in str(e) and not oznamit:
            raise ValueError(
                f"Adresa {cisty} nemá účet Google, takže ji Disk pustí jen s pozvánkou. "
                "Zaškrtni „dát vědět e-mailem“ a pošli to znovu."
            )
        raise
    zaloguj(
        db,
        # Sdílení někomu, kdo na Disku jinak není, je varování, ne běžný provoz:
        # v Logech má být vidět na první pohled. U kolegy, který na disku už je,
        # by to samé jen zaplevelilo log.
        "warn" if novy else "info",
        "disk_prava",
        f"Sdíleno '{cisty}' ({role}) na Disku z modulu Disk.",
        {
            "item_id": item_id,
            "permission_id": p.get("id"),
            "email": cisty,
            "role": role,
            "novy_clovek": novy,
            "uzivatel": uzivatel or "?",
        },
    )
    # Reálný případ: když člověk už na sdíleném disku roli má (třeba `writer`)
    # a tady se mu dá `reader`, Google vrátí to STÁVAJÍCÍ oprávnění — vyšší
    # přístup nepřepíše. Appka pak nesmí tvrdit „nasdíleno jako může číst";
    # proto se posílá i to, co se žádalo, a prohlížeč rozdíl řekne nahlas.
    skutecna = p.get("role") or role
    return {
        "id": p.get("id"),
        "email": p.get("emailAddress") or cisty,
        "jmeno": p.get("displayName") or "",
        "role": skutecna,
        "pozadovana_role": role,
        "novy": novy,
    }


def odeber_pravo(db: Session, item_id: str, permission_id: str, uzivatel: str = "") -> dict:
    """Odebere člověku přístup k položce.

    Zděděné oprávnění a service account konektoru se odebrat nedají — první
    Google odmítne, druhé by rozbilo konektor i tenhle modul.
    """
    n, drive, strop = _priprav(db)
    if not _pod_stropem(drive, item_id, strop):
        raise PermissionError("Tato položka neleží pod výchozí složkou modulu Disk.")

    sluzebni = (n.google_subject_email or "").strip().lower()
    ktere = [p for p in drive.prava(item_id) if p.get("id") == permission_id]
    if not ktere:
        raise ValueError("Tohle oprávnění u položky neexistuje.")
    p = ktere[0]
    email = (p.get("emailAddress") or "").strip()
    if sluzebni and email.lower() == sluzebni:
        raise ValueError(
            "Tohle je přístup konektoru — kdyby zmizel, přestane fungovat "
            "zakládání složek i tenhle modul."
        )
    if any(d.get("inherited") for d in p.get("permissionDetails") or []):
        raise ValueError(
            "Tohle oprávnění je zděděné z nadřazené složky — odebrat se musí tam, "
            "kde bylo dáno."
        )

    drive.smaz_pravo(item_id, permission_id)
    zaloguj(
        db,
        "info",
        "disk_prava",
        f"Odebráno sdílení '{email or permission_id}' na Disku z modulu Disk.",
        {
            "item_id": item_id,
            "permission_id": permission_id,
            "email": email,
            "uzivatel": uzivatel or "?",
        },
    )
    return {"id": permission_id, "email": email}


def nahled(db: Session, file_id: str) -> tuple[bytes, str, str]:
    """Obsah souboru pro zobrazení **přímo v appce**. Vrací (data, mime, název).

    Rozhodnutí Dana (1. 8. 2026): soubor se má otevřít v appce, ne přesměrováním
    na Disk. Proto se čte přes service account konektoru a posílá do prohlížeče —
    nezáleží tedy na tom, jestli má člověk vlastní přístup ke Google Disku.

    Google formáty se exportují na PDF (`exportuj`), binární soubory jdou tak,
    jak jsou (`stahni`). Složka náhled nemá — do té se vchází.

    Kontrola stropu je i tady, a je to ta nejdůležitější z celého modulu: bez ní
    by `file_id` z adresy stáhlo jakýkoli soubor na firemním Disku, včetně těch,
    ke kterým se v appce nedá doklikat.
    """
    _, drive, strop = _priprav(db)
    if not _pod_stropem(drive, file_id, strop):
        raise PermissionError("Tento soubor neleží pod výchozí složkou modulu Disk.")

    f = drive.get_file(file_id)
    mime = f.get("mimeType") or ""
    nazev = f.get("name") or "soubor"
    if mime == logika.FOLDER_MIME:
        raise ValueError("Tohle je složka, ne soubor.")

    velikost = int(f.get("size") or 0)
    if velikost > MAX_NAHLED_B:
        raise ValueError(
            "Soubor je větší než 25 MB — otevři ho prosím na Disku."
        )

    if mime.startswith(GOOGLE_PREFIX):
        # Google dokument nemá binární obsah; PDF je jediná podoba, kterou umí
        # vydat i prohlížeč zobrazit. Název dostane .pdf, ať je jasné, co to je.
        return drive.exportuj(file_id, EXPORT_PDF), EXPORT_PDF, f"{nazev}.pdf"
    return drive.stahni(file_id), mime or "application/octet-stream", nazev
