"""Složky na Disku pro záznamy z CRM (ne z Raynetu).

Rozhodnutí Dana (30. 7. 2026): appka přebírá štafetu po Raynetu, takže nové
obchodní případy vznikají tady — a složky na Disku se pro ně mají zakládat
stejně, jako je pro Raynetí případy zakládá konektor.

---- Proč vlastní vstupní bod a ne prosté zavolání `zajisti_slozku_op` -----

Ta funkce je celá postavená na Raynetu: případ i firmu čte přes
`raynet.get_record()`, ukládá se pod Raynetí `deal_id` a nakonec zapisuje odkaz
zpátky do Raynetu vlastním polem. U případu z appky není ani jedno z toho —
Raynetí ID neexistuje a zapisovat odkaz do Raynetu není kam.

Tenhle modul proto bere jméno a čísla z CRM, ale **strukturu na Disku vytváří
tímtéž kódem** (kopie vzoru `0. vzor`, kontejnery, podsložky). Díky tomu
zůstane na Disku jedna struktura, ne dvě — což je celý smysl varianty, kterou
Dan zvolil.

---- Klíč entity: proč `crm_op` a ne `deal` -------------------------------

Mapování složek (`konektor_entity_folder`) je klíčované `(entity, entity_id)`
a dnes tam leží Raynetí ID: `deal#228`. Naše případy mají vlastní řadu od 1,
takže `deal#4` z Raynetu a `deal#4` z appky by si přepsaly složku navzájem.
Vlastní klíče (`crm_op`, `crm_zakaznik`) dovolí obojímu žít vedle sebe, dokud
Dan Raynetí webhook nevypne.

---- Kdy se složka zakládá -----------------------------------------------

**Automaticky při vzniku záznamu** (zadání Dana z 3. 8. 2026: „aby se to
propisovalo plně automaticky, ne jen ručně"). Platí pro obchodní případ,
nabídku i objednávku; u zákazníka jen pro typ „klient" a pro okamžik konverze
lead → klient — leady, ze kterých nic nebude, by jinak na Disku nechaly stovky
prázdných složek.

Zakládání **nikdy neběží ve web procesu**: kopie vzoru je desítky volání na
Disk a několik sekund, takže by formulář visel a při souběhu by appka padala na
502 (stejný důvod, proč běží pošta jako vlastní služba). Endpointy proto jen
zařadí úlohu do fronty konektoru (`naplanuj`) a složku vytvoří worker.
Tlačítko „Založit složku" zůstává — je to záchranná brzda, když je konektor
nenastavený nebo úloha spadla.
"""

from sqlalchemy.orm import Session

from app.konektor import fronta, logika
from app.konektor.google_klient import DriveClient
from app.konektor.logger import zaloguj
from app.konektor.models import KonektorEntityFolder, KonektorJobQueue, KonektorNastaveni

# Klíče entit pro záznamy z appky (Raynetí používají „company" / „deal").
ENTITA_ZAKAZNIK = "crm_zakaznik"
ENTITA_OP = "crm_op"
ENTITA_NABIDKA = "crm_nabidka"
ENTITA_OBJEDNAVKA = "crm_objednavka"

# Typ úlohy ve frontě konektoru (`konektor_job_queue.typ`). Jeden pro všechny
# entity — worker si podle payloadu vybere, co zakládat.
TYP_JOBU = "crm_slozka"


def _drive_klient(n: KonektorNastaveni) -> DriveClient:
    """Jen Drive klient — pro záznamy z appky není Raynet potřeba.

    `logika.vytvor_klienty()` by vyžadovala i Raynetí přístup a spadla by
    v okamžiku, kdy Dan Raynet vypne. To by byl přesně ten den, kdy tohle musí
    fungovat nejvíc.
    """
    from app.konektor import crypto

    sa_json = crypto.desifruj(n.google_sa_json_enc)
    if not sa_json:
        raise logika.NastaveniNepripraveno("Chybí Google service-account JSON.")
    if not n.google_shared_drive_id:
        raise logika.NastaveniNepripraveno("Chybí ID sdíleného disku.")
    # Druhý parametr je subject_email (impersonace uživatele), NE id disku —
    # stejně jako v `logika.vytvor_klienty()`.
    return DriveClient(sa_json, n.google_subject_email or None)


def _nastaveni(db: Session) -> KonektorNastaveni:
    n = db.query(KonektorNastaveni).first()
    if n is None:
        raise logika.NastaveniNepripraveno("Konektor ještě není nastavený.")
    return n


def najdi_slozku(db: Session, entita: str, zaznam_id: int) -> KonektorEntityFolder | None:
    """Mapování složky, pokud už existuje (bez sahání na Disk)."""
    return logika._najdi_ef(db, entita, zaznam_id)


def zajisti_slozku_zakaznika(
    db: Session, drive: DriveClient, n: KonektorNastaveni, zakaznik
) -> KonektorEntityFolder:
    """Složka zákazníka z CRM; vytvoří ji, pokud chybí.

    Název drží konvenci konektoru („název [id]"), jen id je naše. Bez ní by na
    Disku vznikly dva různé způsoby pojmenování a nikdo by nepoznal, který je
    který.
    """
    ef = najdi_slozku(db, ENTITA_ZAKAZNIK, zakaznik.id)
    if ef is not None:
        return ef

    parent = n.google_root_folder_id or n.google_shared_drive_id
    nazev_slozky = logika._bezpecny_nazev(f"{zakaznik.nazev} [{zakaznik.id}]")
    kontejnery = None

    if n.google_vzor_folder_id:
        kop, _, _ = logika._kfg_kontejnery(n)
        # Vzorová složka OP se do kopie klienta nezahrne — bere se centrálně
        # z „0. vzor", stejně jako u Raynetích klientů.
        skip: set[str] = set()
        vzor_op = logika._vzor_op(drive, n)
        if vzor_op:
            skip.add(vzor_op["id"])
        root = drive.copy_tree(n.google_vzor_folder_id, parent, nazev_slozky, skip)
        kont_op = logika._najdi_podslozku(drive, root["id"], kop)
        if kont_op:
            kontejnery = {"op": kont_op["id"]}
    else:
        root = drive.create_folder(nazev_slozky, parent)

    ef = KonektorEntityFolder(
        entity=ENTITA_ZAKAZNIK,
        entity_id=zakaznik.id,
        drive_folder_id=root["id"],
        drive_folder_url=root.get("webViewLink", ""),
        name=zakaznik.nazev,
        kontejnery=kontejnery,
    )
    db.add(ef)
    db.commit()
    zaloguj(
        db,
        "info",
        "crm_slozka",
        f"Vytvořena složka zákazníka '{zakaznik.nazev}' (z appky).",
        {"zakaznik_id": zakaznik.id, "drive_folder_id": ef.drive_folder_id},
    )
    return ef


def zajisti_slozku_pripadu(db: Session, pripad, zakaznik) -> KonektorEntityFolder:
    """Složka obchodního případu z CRM; zajistí i složku zákazníka nad ní.

    Název složky je `číslo případu - název`, tedy stejný vzorec jako u Raynetu.
    U nových případů to bude naše číslo (`OP-26-0301`), u starých Raynetí —
    dvě konvence vedle sebe jsou nevyhnutelné a správné: číslo případu se
    nepřepisuje.
    """
    ef = najdi_slozku(db, ENTITA_OP, pripad.id)
    if ef is not None:
        return ef

    n = _nastaveni(db)
    drive = _drive_klient(n)
    zak = zajisti_slozku_zakaznika(db, drive, n, zakaznik)

    cislo = pripad.raynet_code or pripad.cislo
    nazev = logika._bezpecny_nazev(
        f"{cislo} - {pripad.nazev}" if pripad.nazev else str(cislo)
    )
    kop, knab, kobj = logika._kfg_kontejnery(n)
    kontejnery = None

    if n.google_vzor_folder_id:
        vzor_op = logika._vzor_op(drive, n)
        if vzor_op is None:
            raise RuntimeError("Ve vzoru '0. vzor' chybí vzorová složka obchodního případu.")
        cil = logika._kontejner_ze_slozky(drive, zak, "op", kop)
        if cil is None:
            raise RuntimeError(f"Ve složce klienta chybí kontejner '{kop}'.")
        skip: set[str] = set()
        vzor_obj = logika._vzor_polozky(drive, n, "objednavky")
        if vzor_obj:
            skip.add(vzor_obj["id"])
        op = drive.copy_tree(vzor_op["id"], cil, nazev, skip)
        knab_kopie = logika._najdi_podslozku(drive, op["id"], knab)
        kobj_kopie = logika._najdi_podslozku(drive, op["id"], kobj)
        kontejnery = {
            "nabidky": knab_kopie["id"] if knab_kopie else None,
            "objednavky": kobj_kopie["id"] if kobj_kopie else None,
        }
    else:
        op = drive.create_folder(nazev, zak.drive_folder_id)
        for sub in logika._podslozky(n):
            drive.create_folder(sub, op["id"])

    ef = KonektorEntityFolder(
        entity=ENTITA_OP,
        entity_id=pripad.id,
        drive_folder_id=op["id"],
        drive_folder_url=op.get("webViewLink", ""),
        name=nazev,
        kontejnery=kontejnery,
    )
    db.add(ef)
    db.commit()
    zaloguj(
        db,
        "info",
        "crm_slozka",
        f"Vytvořena složka obchodního případu '{nazev}' (z appky).",
        {"pripad_id": pripad.id, "drive_folder_id": ef.drive_folder_id},
    )
    return ef


# Popis typu nabídky do názvu složky. Vlastní tabulka, ne převzatý překlad z
# UI: název složky na Disku se nesmí měnit s tím, jak se přepíše tlačítko.
NAZVY_TYPU_NABIDKY = {
    "ppa": "PPA",
    "prodej": "Prodej",
    "peak_shaving": "Peak shaving",
    "kombinace": "Kombinace opatření",
    "ppa_bess": "PPA + BESS",
}


def _zajisti_slozku_pod_op(
    db: Session,
    entita: str,
    zaznam_id: int,
    nazev_slozky: str,
    klic: str,
    pripad,
    zakaznik,
) -> KonektorEntityFolder:
    """Složka nabídky/objednávky v jejím kontejneru pod složkou případu.

    Společné tělo pro obě entity — liší se jen kontejner („1. nabídky" /
    „5. objednávky") a vzor uvnitř něj. Struktura je stejná jako u Raynetích
    nabídek (`logika._zpracuj_zaznam_pod_op`), aby na Disku nevznikly dvě
    konvence; odsud se ale navíc nezapisuje odkaz do Raynetu (není kam).
    """
    ef = najdi_slozku(db, entita, zaznam_id)
    if ef is not None:
        return ef

    n = _nastaveni(db)
    drive = _drive_klient(n)
    # Nadřazená složka případu musí existovat; když ne, vytvoří se teď (i se
    # složkou zákazníka nad ní). Nabídka založená u případu bez složky by jinak
    # neměla kam patřit.
    op_ef = zajisti_slozku_pripadu(db, pripad, zakaznik)

    _, knab, kobj = logika._kfg_kontejnery(n)
    nazev_kont = knab if klic == "nabidky" else kobj
    cil = logika._kontejner_ze_slozky(drive, op_ef, klic, nazev_kont)
    if cil is None:
        # Starý režim bez vzoru (nebo kontejner někdo ve složce smazal):
        # vytvoříme ho, ať nabídka neskončí volně v případu.
        cil = drive.create_folder(nazev_kont, op_ef.drive_folder_id)["id"]

    nazev = logika._bezpecny_nazev(nazev_slozky)
    vzor = logika._vzor_polozky(drive, n, klic) if n.google_vzor_folder_id else None
    slozka = (
        drive.copy_tree(vzor["id"], cil, nazev) if vzor is not None
        else drive.create_folder(nazev, cil)
    )

    ef = KonektorEntityFolder(
        entity=entita,
        entity_id=zaznam_id,
        drive_folder_id=slozka["id"],
        drive_folder_url=slozka.get("webViewLink", ""),
        name=nazev,
    )
    db.add(ef)
    db.commit()
    zaloguj(
        db,
        "info",
        "crm_slozka",
        f"Vytvořena složka '{nazev}' v '{nazev_kont}' (z appky).",
        {"entita": entita, "zaznam_id": zaznam_id, "drive_folder_id": ef.drive_folder_id},
    )
    return ef


def zajisti_slozku_nabidky(db: Session, nabidka, pripad, zakaznik) -> KonektorEntityFolder:
    """Složka nabídky v kontejneru nabídek pod složkou případu.

    Název je `číslo - typ řešení` (např. „NAB-26-0007 - PPA"). Číslo samo by
    nestačilo: jeden případ může mít nabídku na PPA i na peak shaving a ve
    složce případu by pak byly dvě řady čísel bez vysvětlení, co je co.
    """
    popis = NAZVY_TYPU_NABIDKY.get(nabidka.typ, nabidka.typ or "")
    zaklad = f"{nabidka.cislo} - {popis}".strip(" -") if nabidka.cislo else popis
    return _zajisti_slozku_pod_op(
        db,
        ENTITA_NABIDKA,
        nabidka.id,
        zaklad or f"nabidka-{nabidka.id}",
        "nabidky",
        pripad,
        zakaznik,
    )


def zajisti_slozku_objednavky(db: Session, objednavka, pripad, zakaznik) -> KonektorEntityFolder:
    """Složka objednávky v kontejneru objednávek pod složkou případu."""
    zaklad = f"{objednavka.cislo} - {objednavka.nazev or ''}".strip(" -")
    return _zajisti_slozku_pod_op(
        db,
        ENTITA_OBJEDNAVKA,
        objednavka.id,
        zaklad or f"objednavka-{objednavka.id}",
        "objednavky",
        pripad,
        zakaznik,
    )


# ---- automatika: zařazení do fronty a její zpracování ----------------------


def naplanuj(db: Session, entita: str, zaznam_id: int) -> None:
    """Zařadí založení složky do fronty konektoru (idempotentně).

    Volá se z endpointů, které záznam zakládají — a **až po jejich commitu**:
    `fronta.zarad` commituje, takže dřív by uložil rozdělaný záznam.

    Chyba se tady polkne schválně. Kdyby zařazení do fronty shodilo zakládání
    zákazníka, appka by kvůli složce na Disku přestala umět svou hlavní práci.
    Nezaložená složka se pozná (tlačítko „Založit složku" zůstane) a dá se
    dohnat; ztracený záznam ne.
    """
    try:
        if najdi_slozku(db, entita, zaznam_id) is not None:
            return
        ceka = (
            db.query(KonektorJobQueue)
            .filter(
                KonektorJobQueue.typ == TYP_JOBU,
                KonektorJobQueue.status == "pending",
                KonektorJobQueue.payload["entita"].astext == entita,
                KonektorJobQueue.payload["id"].astext == str(zaznam_id),
            )
            .first()
        )
        if ceka is not None:
            return
        fronta.zarad(db, TYP_JOBU, {"entita": entita, "id": zaznam_id})
    except Exception:  # noqa: BLE001 - viz docstring
        db.rollback()


def zpracuj_job(db: Session, payload: dict) -> dict:
    """Vykoná jednu úlohu z fronty: založí složku podle entity v payloadu.

    Záznam mezitím mohl někdo smazat — to není chyba, jen už není co zakládat
    (jinak by úloha šla do `failed` a hlásila chybu, se kterou nikdo nic
    neudělá).
    """
    from app.crm.models import ObchodniPripad, Objednavka, Zakaznik
    from app.nabidkovac.models import Nabidka

    entita = str(payload.get("entita") or "")
    zaznam_id = int(payload.get("id") or 0)
    if najdi_slozku(db, entita, zaznam_id) is not None:
        return {"skip": True}

    if entita == ENTITA_ZAKAZNIK:
        z = db.get(Zakaznik, zaznam_id)
        if z is None:
            return {"skip": True}
        n = _nastaveni(db)
        ef = zajisti_slozku_zakaznika(db, _drive_klient(n), n, z)
    elif entita == ENTITA_OP:
        p = db.get(ObchodniPripad, zaznam_id)
        if p is None:
            return {"skip": True}
        ef = zajisti_slozku_pripadu(db, p, db.get(Zakaznik, p.zakaznik_id))
    elif entita in (ENTITA_NABIDKA, ENTITA_OBJEDNAVKA):
        zaznam = db.get(Nabidka if entita == ENTITA_NABIDKA else Objednavka, zaznam_id)
        if zaznam is None:
            return {"skip": True}
        pripad = (
            db.get(ObchodniPripad, zaznam.obchodni_pripad_id)
            if zaznam.obchodni_pripad_id
            else None
        )
        if pripad is None:
            # Nabídka bez případu (nabídkovač otevřený samostatně) nemá pod čím
            # na Disku být. Není to chyba fronty, jen tady práce končí.
            return {"skip": True}
        zakaznik = db.get(Zakaznik, pripad.zakaznik_id)
        if zakaznik is None:
            return {"skip": True}
        if entita == ENTITA_NABIDKA:
            ef = zajisti_slozku_nabidky(db, zaznam, pripad, zakaznik)
        else:
            ef = zajisti_slozku_objednavky(db, zaznam, pripad, zakaznik)
    else:
        raise ValueError(f"Neznámá entita složky: {entita}")

    return {"drive_folder_id": ef.drive_folder_id, "drive_folder_url": ef.drive_folder_url}


def soubory(db: Session, ef: KonektorEntityFolder, limit: int = 40) -> list[dict]:
    """Obsah složky pro výpis v appce — složky první, pak soubory.

    Čte se z Disku při každém zobrazení (žádná kopie v naší DB): kdyby se to
    cachovalo, appka by tvrdila, že tam soubor je, i když ho někdo mezitím
    smazal — a nikdo by nepoznal, které tvrzení platí.
    """
    n = _nastaveni(db)
    drive = _drive_klient(n)
    polozky = drive.list_children(ef.drive_folder_id)
    out = [
        {
            "id": f.get("id"),
            "nazev": f.get("name") or "",
            "je_slozka": f.get("mimeType") == logika.FOLDER_MIME,
            "url": f.get("webViewLink") or "",
        }
        for f in polozky
        if not f.get("trashed")
    ]
    out.sort(key=lambda x: (not x["je_slozka"], x["nazev"].lower()))
    return out[:limit]


# ---- procházení a nahrávání (na přání Dana: „ať nemusím na Disk") ----------

# Kolik úrovní se leze nahoru při kontrole, že složka patří pod záznam.
# Struktura vzoru má 3–4 úrovně; deset je rezerva a zároveň strop, aby se
# z kontroly nestalo lezení celým Diskem.
MAX_HLOUBKA_KONTROLY = 10


def je_pod_slozkou(
    drive: DriveClient, folder_id: str, koren_id: str, max_hloubka: int = MAX_HLOUBKA_KONTROLY
) -> bool:
    """Leží `folder_id` uvnitř `koren_id` (nebo je to on sám)?

    BEZPEČNOSTNÍ KONTROLA, ne pohodlí. ID složky přichází z prohlížeče, takže
    bez ní by si kdokoli mohl vyžádat obsah libovolné složky na firemním Disku —
    včetně mezd nebo smluv, ke kterým v CRM nemá co dělat. Ověřuje se řetěz
    rodičů, protože jiný způsob Drive API nenabízí.

    `max_hloubka` si volá modul Disk vyšší (viz `disk_prochazeni.MAX_HLOUBKA`):
    počítá od složky o dvě úrovně výš, takže s desítkou by hlouběji zanořené
    soubory odmítl jako „mimo strop".
    """
    if not folder_id or not koren_id:
        return False
    if folder_id == koren_id:
        return True
    aktualni = folder_id
    for _ in range(max_hloubka):
        try:
            f = drive.get_file(aktualni)
        except Exception:  # noqa: BLE001 – neexistující ID = nemá přístup
            return False
        rodice = f.get("parents") or []
        if not rodice:
            return False
        if koren_id in rodice:
            return True
        aktualni = rodice[0]
    return False


def obsah_slozky(
    db: Session, ef: KonektorEntityFolder, folder_id: str | None = None, limit: int = 60
) -> dict:
    """Obsah složky záznamu nebo její podsložky, včetně cesty pro navigaci.

    `folder_id` prázdné = koren záznamu. Jinak se nejdřív ověří, že požadovaná
    složka pod záznam patří (viz `je_pod_slozkou`).
    """
    n = _nastaveni(db)
    drive = _drive_klient(n)
    cil = folder_id or ef.drive_folder_id
    if folder_id and not je_pod_slozkou(drive, folder_id, ef.drive_folder_id):
        raise PermissionError("Tato složka nepatří k tomuto záznamu.")

    polozky = [
        {
            "id": f.get("id"),
            "nazev": f.get("name") or "",
            "je_slozka": f.get("mimeType") == logika.FOLDER_MIME,
            "url": f.get("webViewLink") or "",
            "velikost": int(f.get("size") or 0) if f.get("size") else None,
        }
        for f in drive.list_children(cil)
        if not f.get("trashed")
    ]
    polozky.sort(key=lambda x: (not x["je_slozka"], x["nazev"].lower()))

    # Cesta od záznamu k aktuální složce (pro drobečkovou navigaci). Skládá se
    # odzadu přes rodiče a končí u složky záznamu.
    cesta = []
    if cil != ef.drive_folder_id:
        aktualni = cil
        for _ in range(MAX_HLOUBKA_KONTROLY):
            try:
                f = drive.get_file(aktualni)
            except Exception:  # noqa: BLE001
                break
            cesta.insert(0, {"id": f.get("id"), "nazev": f.get("name") or ""})
            rodice = f.get("parents") or []
            if not rodice or ef.drive_folder_id in rodice:
                break
            aktualni = rodice[0]

    return {
        "folder_id": cil,
        "je_koren": cil == ef.drive_folder_id,
        "cesta": cesta,
        "polozky": polozky[:limit],
        "zkraceno": len(polozky) > limit,
    }


def nahraj(
    db: Session, ef: KonektorEntityFolder, folder_id: str | None, nazev: str, data: bytes, mime: str
) -> dict:
    """Nahraje soubor do složky záznamu (nebo do její podsložky).

    Stejná kontrola jako u čtení — cílová složka musí patřit pod záznam, jinak
    by šlo appkou zapisovat kamkoli na Disk.
    """
    n = _nastaveni(db)
    drive = _drive_klient(n)
    cil = folder_id or ef.drive_folder_id
    if folder_id and not je_pod_slozkou(drive, folder_id, ef.drive_folder_id):
        raise PermissionError("Tato složka nepatří k tomuto záznamu.")
    f = drive.upload_file(
        logika._bezpecny_nazev(nazev), cil, data, mime or "application/octet-stream"
    )
    zaloguj(
        db,
        "info",
        "crm_slozka",
        f"Nahrán soubor '{nazev}' z appky.",
        {"entity": ef.entity, "entity_id": ef.entity_id, "file_id": f.get("id")},
    )
    return {"id": f.get("id"), "nazev": f.get("name"), "url": f.get("webViewLink") or ""}
