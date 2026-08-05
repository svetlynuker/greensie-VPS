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

from app.crm.models import CrmKategorie, CrmKategorieAktivity
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
#
# „PPA + BESS" je vynechané z jiného důvodu: výpočet se teprve ověřuje na
# reálných datech a má vlastní právo, které nikdo nemá přidělené. Nabízet ho
# u kategorií by znamenalo, že si ho vedení přiřadí a OZ pak narazí na 403.
# Až se právo začne přidělovat, stačí ho odsud přestat vylučovat.
_MIMO_KATEGORIE = ("kombinace", "ppa_bess")
TYPY_NABIDKY_PRO_KATEGORII = tuple(t for t in TYPY_NABIDKY if t not in _MIMO_KATEGORIE)


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


# ============================================================================
# Kategorie AKTIVIT — barevné štítky v kalendáři
# ============================================================================
# Pozor na záměnu s kategoriemi výše: ty říkají, do kterého VÝPOČTU míří
# obchodní případ. Tyhle jsou barevné škatulky aktivit v kalendáři („Porada",
# „Servis"), kterými se filtruje. Žijí ve stejném souboru, protože je to týž
# druh věci — konfigurovatelný číselník, který spravuje vedení.

# Výchozí sada. Barvy jsou pastelové schválně: dlaždice v kalendáři má být
# čitelná s tmavým textem a nemá překřičet zbytek obrazovky.
VYCHOZI_KATEGORIE_AKTIVIT: list[dict] = [
    {"nazev": "Akvizice", "barva": "#b9e6c9"},
    {"nazev": "Porada", "barva": "#fbd8b4"},
    {"nazev": "Servis", "barva": "#bcd9f5"},
    {"nazev": "Reklamace", "barva": "#f7bcc3"},
    {"nazev": "Administrativa", "barva": "#ded8f0"},
    {"nazev": "Osobní", "barva": "#dfe3e8"},
]


def seed_kategorie_aktivit(db: Session) -> None:
    """Naplní barevné kategorie aktivit, když tabulka nemá ani řádek.

    Jen do prázdné tabulky – dorovnávání chybějících klíčů by vracelo
    kategorie, které vedení schválně smazalo.
    """
    if db.query(CrmKategorieAktivity.id).first() is not None:
        return
    for poradi, k in enumerate(VYCHOZI_KATEGORIE_AKTIVIT):
        db.add(
            CrmKategorieAktivity(
                nazev=k["nazev"], barva=k["barva"], poradi=poradi, aktivni=True
            )
        )
    db.commit()


def seznam_aktivit(db: Session, jen_aktivni: bool = False) -> list[CrmKategorieAktivity]:
    q = db.query(CrmKategorieAktivity)
    if jen_aktivni:
        q = q.filter(CrmKategorieAktivity.aktivni.is_(True))
    return q.order_by(CrmKategorieAktivity.poradi, CrmKategorieAktivity.id).all()


def over_kategorii_aktivity(db: Session, kategorie_id: int | None) -> int | None:
    """Ověří, že kategorie existuje. `None` je platná hodnota (bez kategorie)."""
    if kategorie_id is None:
        return None
    if db.get(CrmKategorieAktivity, kategorie_id) is None:
        raise ValueError(f"Kategorie aktivity s id {kategorie_id} neexistuje.")
    return kategorie_id
