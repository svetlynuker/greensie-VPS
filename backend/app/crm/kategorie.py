"""Kategorie obchodního případu jako data, ne jako konstanta v kódu.

Kategorie říká, o jaký typ zakázky jde – a hlavně do kterého VÝPOČTU
nabídkovače případ míří (`typ_nabidky`). Do 30. 7. 2026 byly tři kategorie
zadrátované na dvou místech (backend enum + frontendová konstanta), takže
„chceme ještě Servis" znamenalo nasazení. Tenhle modul je jedno místo, kde se
kategorie čtou a validují; tabulku spravuje vedení v nastavení CRM.

Proč `typ_nabidky` může být prázdný: ne každá kategorie je výpočet. „Servis"
nebo „Dotace" je pořád obchodní případ, ale nabídkovač pro ni nic neumí –
tlačítko „+ Servis" by pak vedlo do prázdna. Prázdná hodnota tuhle situaci
umí říct nahlas, místo aby se na ni přišlo až po kliknutí.
"""

from sqlalchemy.orm import Session

from app.crm.models import CrmKategorie
from app.nabidkovac.models import TYPY_NABIDKY

# Výchozí sada, kterou se naseeduje prázdná tabulka. Klíče se MUSÍ shodovat
# s dosavadními hodnotami v `ObchodniPripad.kategorie` a `Nabidka.typ`, jinak
# by staré případy přestaly mít čitelnou kategorii.
VYCHOZI_KATEGORIE: list[dict] = [
    {
        "klic": "ppa",
        "nazev": "PPA",
        "popis": "Greensie zainvestuje FVE a dodává elektřinu.",
        "typ_nabidky": "ppa",
    },
    {
        "klic": "prodej",
        "nazev": "Prodej",
        "popis": "Zákazník je vlastníkem zařízení.",
        "typ_nabidky": "prodej",
    },
    {
        "klic": "peak_shaving",
        "nazev": "Peak shaving",
        "popis": "Baterie sráží špičky odběru.",
        "typ_nabidky": "peak_shaving",
    },
]

# „Kombinace" je typ nabídky, ne kategorie případu – vzniká spojením dvou
# hotových nabídek, ne volbou u případu. Do nabídky typů pro kategorii nepatří.
TYPY_NABIDKY_PRO_KATEGORII = tuple(t for t in TYPY_NABIDKY if t != "kombinace")


def seed_kategorie(db: Session) -> None:
    """Naplní kategorie, když tabulka nemá ani jeden řádek (idempotentní).

    Doplňuje jen do PRÁZDNÉ tabulky – kdyby seed dorovnával chybějící klíče,
    kategorii smazanou vedením by vrátil při každém restartu.
    """
    if db.query(CrmKategorie.id).first() is not None:
        return
    for poradi, k in enumerate(VYCHOZI_KATEGORIE):
        db.add(
            CrmKategorie(
                klic=k["klic"],
                nazev=k["nazev"],
                popis=k.get("popis", ""),
                poradi=poradi,
                typ_nabidky=k.get("typ_nabidky", ""),
                aktivni=True,
            )
        )
    db.commit()


def seznam(db: Session, jen_aktivni: bool = False) -> list[CrmKategorie]:
    """Kategorie v pořadí, v jakém je má vidět člověk."""
    q = db.query(CrmKategorie)
    if jen_aktivni:
        q = q.filter(CrmKategorie.aktivni.is_(True))
    return q.order_by(CrmKategorie.poradi, CrmKategorie.id).all()


def platne_klice(db: Session) -> set[str]:
    """Klíče, které smí případ nést. Vypnuté kategorie se sem počítají taky:
    případ, který ji už má, se musí dát dál uložit (jinak by ho po vypnutí
    kategorie nešlo editovat)."""
    return {k.klic for k in seznam(db)}


def typ_nabidky_pro(db: Session, klic: str) -> str:
    """Do kterého výpočtu kategorie míří. Prázdný string = žádný."""
    k = db.query(CrmKategorie).filter(CrmKategorie.klic == klic).first()
    return (k.typ_nabidky or "") if k is not None else ""


def klic_podle_typu_nabidky(db: Session, typ_nabidky: str) -> str | None:
    """Opačný směr: k typu nabídky (`ppa`) najdi kategorii případu.

    Potřebuje to dohledání starých nabídek – z typu nabídky se odvozuje
    kategorie případu, který se k ní zpětně zakládá. Když žádná kategorie na
    ten výpočet nemíří, vrací None a případ zůstane bez kategorie (radši
    prázdno než vymyšlený klíč).
    """
    if not typ_nabidky:
        return None
    k = (
        db.query(CrmKategorie)
        .filter(CrmKategorie.typ_nabidky == typ_nabidky)
        .order_by(CrmKategorie.poradi, CrmKategorie.id)
        .first()
    )
    return k.klic if k is not None else None


def klic_ze_nazvu(db: Session, nazev: str, ignoruj_id: int | None = None) -> str:
    """Strojový klíč z názvu (bez diakritiky, unikátní).

    Stejný princip jako u stavů a vlastních polí: klíč je neměnný, protože ho
    nesou uložené záznamy, ale musí vzniknout sám – vedení nemá vymýšlet
    strojové identifikátory.
    """
    import re
    import unicodedata

    zaklad = unicodedata.normalize("NFKD", nazev or "")
    zaklad = "".join(c for c in zaklad if not unicodedata.combining(c))
    zaklad = re.sub(r"[^a-zA-Z0-9]+", "_", zaklad).strip("_").lower() or "kategorie"

    obsazene = {
        k.klic for k in db.query(CrmKategorie).all() if ignoruj_id is None or k.id != ignoruj_id
    }
    if zaklad not in obsazene:
        return zaklad
    i = 2
    while f"{zaklad}_{i}" in obsazene:
        i += 1
    return f"{zaklad}_{i}"
