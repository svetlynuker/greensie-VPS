"""Datový model dlaždice Nabídkovač (SPEC-nabidkovac.md, kap. 4).

POZOR – KOSTRA: tenhle modul zakládá jen tabulky a jejich vztahy, na které
navážou budoucí výpočty (sizing FVE/baterie, PVGIS, ROI, PPA kontrakt,
LLM extrakce faktur, generování PDF). Žádná výpočetní logika tu není a
záměrně tu být nemá – viz kap. 6 SPEC ("Co NENÍ součástí tohoto promptu").

Konvence přebíráme ze zbytku appky (viz app/finance/models.py,
app/matice/models.py): Numeric na peníze/výkony, JSONB na flexibilní
struktury, ForeignKey na uzivatele s ondelete="SET NULL" (smazání OZ
nesmí shodit historii nabídek), povolené hodnoty enumů držíme jako
modulové n-tice, ať je backend může validovat.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base

# ---- Povolené hodnoty enumů (drží se i tady kvůli validaci na backendu) ----

# Typ položky katalogu technologií.
TYPY_TECHNOLOGIE = ("fve_panel", "invertor", "baterie", "jina")

# "Za jakým účelem" OZ nabídku založil = z které podsekce vznikla. Skutečná
# navržená řešení (klidně kombinovaná) žijí v NavrhovaneReseni.typ_reseni.
# `kombinace` není další produktová linie – je to nabídka, která SPOJUJE hotovou
# PPA a peak shaving nabídku téhož případu do jednoho dokumentu pro zákazníka,
# který chce obojí. Nic nepočítá (viz `nabidkovac/kombinace.py`).
# `ppa_bess` je vlastní výpočet, ne spojení dvou hotových: elektrárnu i baterii
# navrhne z jednoho profilu a rozhodne, kolik kapacity dát na srážení špiček
# a kolik na samospotřebu (viz `nabidkovac/ppa_bess.py`). Má vlastní právo
# `nabidkovac_ppa_bess`, takže ho zatím vidí jen supersprávce.
TYPY_NABIDKY = ("ppa", "prodej", "peak_shaving", "kombinace", "ppa_bess")

# Životní cyklus nabídky. Výpočet nikdy neběží nad nezkontrolovanými daty
# (viz kap. 1 SPEC) → mezistav "zkontrolovano_oz" je povinná brána před "spocitano".
STAVY_NABIDKY = ("koncept", "data_nahrana", "zkontrolovano_oz", "spocitano", "hotovo")
VYCHOZI_STAV_NABIDKY = "koncept"

# Typ nahraného dokumentu.
TYPY_DOKUMENTU = ("faktura_pdf", "spotreba_csv", "jiny")

# Stav zpracování dokumentu. V této fázi se soubor jen uloží ("nahrano");
# extrakce/parsování se NEIMPLEMENTUJE (kap. 5 SPEC) – ostatní stavy jsou
# připravené pro navazující prompty.
STAVY_ZPRACOVANI = ("nahrano", "extrahovano", "chyba_extrakce", "rucne_doplneno")
VYCHOZI_STAV_ZPRACOVANI = "nahrano"

# ---- Peak shaving: sazby distributorů (METODIKA-peak-shaving.md, kap. 3.1) ----

# Distributoři, se kterými appka počítá. Sazby 2026 všech tří RDS jsou
# seedované z CV ERÚ č. 13/2025 (audit 16. 7. 2026, bughunt PS-1).
DISTRIBUTORI = ("cez", "egd", "pre")

# Peak shaving řešíme jen pro VN a VVN, NN appka nenabízí (kap. 1 / kap. 6 bod 4).
NAPETOVE_HLADINY = ("vn", "vvn")

# Dvě různé tarifní struktury – od 1. 1. 2027 mění ERÚ způsob zpoplatnění
# kapacity na VN/VVN (kap. 4.6). Ne jiná čísla do stejného vzorce, ale jiná
# STRUKTURA výpočtu → proto typ struktury + flexibilní JSONB parametry.
STRUKTURY_TARIFU = ("stara_2026", "nova_2027")

# Datový typ vlastního (admin definovaného) sloupce katalogu technologií.
TYPY_SLOUPCE = ("text", "cislo")

# Odkud se položka katalogu vzala. Je to jen informace pro člověka a filtr
# v katalogu – appka se podle zdroje nechová jinak. Existuje proto, že v jedné
# tabulce žijí dvě různé věci: velké BESS sestavy pro výpočet peak shavingu
# (`bess_cenik`) a běžný prodejní ceník z Raynetu (`raynet_import`).
ZDROJE_POLOZKY = ("rucne", "bess_cenik", "raynet_import")
VYCHOZI_ZDROJ = "rucne"

# Druh přílohy u položky katalogu. Řídí jen ikonu a filtr, ne zpracování.
DRUHY_PRILOHY = ("technicky_list", "foto", "certifikat", "jiny")
VYCHOZI_DRUH_PRILOHY = "jiny"

# Sazby DPH, se kterými se v ceníku pracuje (ceník z Raynetu má 21 / 12 / 0 %).
SAZBY_DPH = (0.21, 0.12, 0.0)
VYCHOZI_SAZBA_DPH = 0.21


class Technologie(Base):
    """Katalog produktů – ceník všeho, co se prodává a montuje.

    Historicky to byl jen „katalog technologií“ pro výpočty (panel, invertor,
    baterie). Od 31. 7. 2026 (CRM-08) je to plnohodnotný ceník: kromě
    výpočtových parametrů drží i kód, kategorii, jednotku, nákupní cenu, DPH
    a platnost – tedy to, co bylo dřív v Raynetu. Tabulka zůstala jedna
    záměrně (rozhodl Dan): jinak by se při vkládání položky do nabídky
    vybíralo ze dvou různých seznamů.

    Dvě věci v jedné tabulce rozlišuje `zdroj`:
    - `bess_cenik` – velké BESS sestavy, které pohání simulaci peak shavingu
      (potřebují `vykon_kw` i `kapacita_kwh`, viz METODIKA kap. 3.2),
    - `raynet_import` / `rucne` – běžný prodejní ceník (panely, střídače,
      montážní práce, administrativa), který se vkládá do položek nabídek.

    `raynet_id` + `synchronizovano_at` zůstávají pro případný pozdější sync;
    dnes se neplní (import z Excelu si drží původní kód v `kod`).
    """

    __tablename__ = "technologie"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False)  # jedna z TYPY_TECHNOLOGIE
    nazev = Column(String, nullable=False)
    model = Column(String, nullable=False, default="", server_default="")

    # Katalogový kód (v Raynetu „Kód“, např. „Administr17“). Unikátní, ale
    # nullable – ručně založená položka kód mít nemusí. Prázdný řetězec se
    # NEUKLÁDÁ (ukládá se NULL), jinak by unikátnost padla na druhé položce
    # bez kódu.
    kod = Column(String, nullable=True, unique=True, index=True)

    # Kategorie ceníku („Střídače“, „Montážní práce“…). Volný text s
    # našeptávačem z už použitých hodnot – ne číselník, aby kvůli nové
    # kategorii nemusel nikdo chodit do další nastavovací obrazovky.
    kategorie = Column(String, nullable=False, default="", server_default="", index=True)
    jednotka = Column(String, nullable=False, default="ks", server_default="ks")
    popis = Column(Text, nullable=False, default="", server_default="")

    # Podle typu se plní buď výkon (panel/invertor), nebo kapacita (baterie).
    # Necháváme obě nullable, ať katalog pobere všechny typy jednou tabulkou.
    vykon_kw = Column(Numeric(12, 3), nullable=True)
    kapacita_kwh = Column(Numeric(12, 3), nullable=True)

    cena_kc = Column(Numeric(12, 2), nullable=True)  # prodejní cena bez DPH
    # Nákupní cena („Náklad“ v Raynetu). Vidí ji jen právo `nabidkovac_katalog`
    # (rozhodl Dan 31. 7. 2026) – proto se v API pro ostatní vůbec neposílá,
    # ne že by se jen skryla na frontendu.
    cena_nakup_kc = Column(Numeric(12, 2), nullable=True)
    sazba_dph = Column(Numeric(5, 4), nullable=True)  # 0.21 / 0.12 / 0
    ucinnost = Column(Numeric(6, 4), nullable=True)  # 0–1, volitelné dle typu

    platnost_od = Column(Date, nullable=True)
    platnost_do = Column(Date, nullable=True)

    zdroj = Column(String, nullable=False, default=VYCHOZI_ZDROJ, server_default=VYCHOZI_ZDROJ)

    # Zaškrtávátko „Aktivní“ v katalogu. Neaktivní položka zůstává v datech
    # (visí na starých nabídkách), ale nejde ji vložit do nové nabídky.
    # Sloupec se dřív jmenoval `dostupnost` – přejmenovaný lehkou migrací.
    aktivni = Column(Boolean, nullable=False, default=True, server_default="true")

    # Hodnoty vlastních (admin definovaných) sloupců katalogu – mapa
    # {klic_sloupce: hodnota}. Definice sloupců drží KatalogSloupec; tady jsou
    # jen hodnoty konkrétní technologie. JSONB, ať se dají přidávat sloupce bez
    # migrace (stejný princip jako parametry u sazeb / výpočtových nastavení).
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    # Budoucí sync z Raynetu (zatím jen ruční správa – kap. 6 SPEC).
    raynet_id = Column(String, nullable=True, index=True)
    synchronizovano_at = Column(DateTime(timezone=True), nullable=True)

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )

    prilohy = relationship(
        "TechnologiePriloha", back_populates="technologie", cascade="all, delete-orphan"
    )


class TechnologiePriloha(Base):
    """Soubor u položky katalogu – technický list, foto, certifikát.

    Ukládá se stejným způsobem jako dokumenty u nabídky (soubor na disk,
    v DB jen cesta), ale do vlastního adresáře `katalog_soubory`, ať se
    zálohuje odděleně od dat konkrétních zakázek. Smazání položky bere
    přílohy s sebou (cascade) – soubory z disku maže route.
    """

    __tablename__ = "technologie_prilohy"

    id = Column(Integer, primary_key=True, index=True)
    technologie_id = Column(
        Integer, ForeignKey("technologie.id", ondelete="CASCADE"), nullable=False, index=True
    )
    druh = Column(
        String, nullable=False, default=VYCHOZI_DRUH_PRILOHY, server_default=VYCHOZI_DRUH_PRILOHY
    )
    puvodni_nazev = Column(String, nullable=False)
    soubor_cesta = Column(String, nullable=False)  # relativní k UPLOAD_DIR katalogu
    velikost_bajtu = Column(Integer, nullable=True)
    popis = Column(String, nullable=False, default="", server_default="")

    nahrano_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    nahral_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )

    technologie = relationship("Technologie", back_populates="prilohy")


class KatalogSloupec(Base):
    """Vlastní (admin definovaný) sloupec katalogu technologií.

    Umožňuje vedení/adminovi přidat do katalogu další sloupce (např. „Záruka“,
    „Hmotnost“) bez zásahu do kódu. Definice (název, typ, pořadí) žije tady,
    hodnoty se ukládají do Technologie.extra pod klíčem `klic`. Smazání sloupce
    jen skryje hodnoty – v JSONB `extra` osiřelé klíče nevadí.
    """

    __tablename__ = "katalog_sloupce"

    id = Column(Integer, primary_key=True, index=True)
    # Strojový klíč do Technologie.extra (odvozený z názvu, unikátní, neměnný).
    klic = Column(String, nullable=False, unique=True, index=True)
    nazev = Column(String, nullable=False)  # zobrazovaný název sloupce
    typ = Column(String, nullable=False, default="text", server_default="text")  # TYPY_SLOUPCE
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )


class VypoctovaNastaveni(Base):
    """Globální parametry výpočtů – VERZOVANĚ (kap. 4.2 SPEC).

    Nikdy nepřepisujeme řádek "natvrdo": každá změna = nový řádek s vyšší
    `verze`. Nabídka si při skutečném výpočtu uloží referenci na verzi,
    se kterou počítala (Nabidka.vypoctova_nastaveni_id), aby šlo zpětně
    dohledat, jaké parametry tehdy platily. Aktuální = řádek s nejvyšší verzí.

    Nové proměnné (discount rate, přirážky…) přidávej přednostně do JSONB
    pole `parametry`, ať se kvůli každé nové veličině nemusí migrovat schéma.
    """

    __tablename__ = "vypoctova_nastaveni"

    id = Column(Integer, primary_key=True, index=True)
    # Monotónně rostoucí verze (max+1 při každém uložení). Aktuální = nejvyšší.
    verze = Column(Integer, nullable=False, index=True)
    platne_od = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Marže pro výpočet min. délky PPA kontraktu (rozdíl cena výroby vs. cena
    # pro zákazníka × koeficient zisku). Samotný vzorec se doprogramuje později.
    koeficient_zisku = Column(Numeric(8, 4), nullable=True)
    min_delka_kontraktu_roky = Column(Integer, nullable=True)
    max_delka_kontraktu_roky = Column(Integer, nullable=True)

    # Rozšiřitelné parametry bez migrace (discount rate, přirážky, apod.).
    parametry = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SpotovaCena(Base):
    """Spotová (day-ahead) cena elektřiny za jeden obchodní interval.

    Vstup pro režimy „Kombinace“ a „SPOT“ peak shaving kalkulátoru. Ceny se
    ukládají **v granularitě, ve které je vydal trh** (`interval_min` = 60 do
    30. 9. 2025, pak 15 – přechod SDAC na čtvrthodinové intervaly); na
    čtvrthodiny je rozpadá až čtení (`spot_ceny.nacti_rok`).

    `cas_utc` je začátek intervalu v UTC – lokální čas (a tedy i přechody
    letního času) se dopočítává až při čtení, aby v datech nebyla dvojznačnost.
    Kč se odvozují kurzem ČNB dne dodávky, stejně jako zúčtovává OTE.
    """

    __tablename__ = "spotove_ceny"
    __table_args__ = (UniqueConstraint("trh", "cas_utc", name="uq_spotove_ceny_trh_cas"),)

    id = Column(Integer, primary_key=True, index=True)
    trh = Column(String, nullable=False, index=True)  # zatím jen "dam_cz"
    cas_utc = Column(DateTime(timezone=True), nullable=False, index=True)
    interval_min = Column(Integer, nullable=False, default=15, server_default="15")
    cena_eur_mwh = Column(Numeric(12, 4), nullable=True)
    cena_kc_mwh = Column(Numeric(12, 4), nullable=True)
    zdroj = Column(String, nullable=False, default="", server_default="")
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Nabidka(Base):
    """Hlavní záznam zakázky/nabídky (kap. 4.3 SPEC).

    `typ` = za jakým účelem OZ nabídku založil (z které podsekce vznikla),
    NE definitivní řešení – jedna zakázka může vygenerovat víc řešení
    (PPA + peak shaving) uložených v `navrhovana_reseni`.
    """

    __tablename__ = "nabidky"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False)  # jedna z TYPY_NABIDKY

    # Viditelné ID nabídky (NAB-RR-NNNN) z číselné řady CRM. Nullable kvůli
    # nabídkám, které vznikly před zavedením řad – ty číslo nemají a doplní se
    # jim až při navázání na obchodní případ.
    cislo = Column(String, nullable=True, unique=True, index=True)

    # Obchodní případ, pod který nabídka patří. Nullable schválně: nabídkovač
    # jde pořád otevřít i samostatně (výpočtový nástroj) a staré nabídky případ
    # nemají. Cílový stav je, že OZ zakládá nabídky z případu a tohle je vyplněné.
    obchodni_pripad_id = Column(
        Integer, ForeignKey("crm_obchodni_pripady.id", ondelete="SET NULL"), nullable=True,
        index=True,
    )

    zakaznik_nazev = Column(String, nullable=False, default="", server_default="")
    zakaznik_adresa = Column(String, nullable=False, default="", server_default="")
    # Pro budoucí PVGIS – lat/lng. Zatím ručně nebo geokódováním z adresy.
    zakaznik_gps_lat = Column(Numeric(9, 6), nullable=True)
    zakaznik_gps_lng = Column(Numeric(9, 6), nullable=True)

    # Stav ZPRACOVÁNÍ nabídky (jsou nahraná data? je spočítáno?). Je to něco
    # jiného než obchodní stav níž a schválně se to nemíchá: nabídka může být
    # dávno odeslaná zákazníkovi a přitom mít rozpracovaný výpočet, a naopak.
    stav = Column(
        String, nullable=False, default=VYCHOZI_STAV_NABIDKY, server_default=VYCHOZI_STAV_NABIDKY
    )

    # OBCHODNÍ stav nabídky (koncept → odeslána → přijata / zamítnuta). Klíč do
    # `crm_stavy` pro entitu "nab", takže si fáze konfiguruje vedení v CRM
    # a kanban z nich kreslí sloupce. Ne cizí klíč – stav se dá smazat a
    # historie záznamů by se tím rozpadla; klíč je stabilní text.
    #
    # Nullable kvůli nabídkám, které vznikly před zavedením pipeline; ty se při
    # prvním čtení berou jako první stav (viz `crm/nabidky_pipeline.py`).
    stav_obchodni = Column(String, nullable=True, index=True)

    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Verze výpočtových nastavení použitá při výpočtu (vyplní se až při
    # skutečném výpočtu; teď zůstává NULL).
    vypoctova_nastaveni_id = Column(
        Integer, ForeignKey("vypoctova_nastaveni.id", ondelete="SET NULL"), nullable=True
    )

    # Hodnoty vlastních (admin definovaných) polí – definice žijí v
    # `crm_vlastni_pole` pro entitu "nab". Stejný princip jako u zákazníka
    # a případu; nabídka je v CRM měla jako jediná chybět (CRM-04).
    extra = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoril = relationship("User")
    dokumenty = relationship(
        "NabidkaDokument", back_populates="nabidka", cascade="all, delete-orphan"
    )
    reseni = relationship(
        "NavrhovaneReseni", back_populates="nabidka", cascade="all, delete-orphan"
    )
    polozky = relationship(
        "NabidkaPolozka",
        back_populates="nabidka",
        cascade="all, delete-orphan",
        order_by="NabidkaPolozka.poradi, NabidkaPolozka.id",
    )


class NabidkaPolozka(Base):
    """Řádek rozpisu nabídky (CRM-08) – panely, měnič, montáž, doprava.

    Rozpis je vědomě NEZÁVISLÝ na výpočtu PPA / peak shavingu. Výpočet říká,
    co se zákazníkovi vyplatí; rozpis říká, z čeho se skládá cena. Jedno
    druhé nepřepisuje – kdyby rozpis vznikal z výpočtu automaticky, nešlo by
    do nabídky přidat položku, kterou výpočet nezná (což je většina montáže
    a administrativy).

    Položka může, ale nemusí mít vazbu do katalogu (`technologie_id`).
    Zadání Dana: „musí zvládnout i položku, která v katalogu není.“
    Proto se název, kód, jednotka a ceny ukládají jako SNAPSHOT – když se
    v katalogu zdraží panel, stará nabídka se tím měnit nesmí.
    """

    __tablename__ = "nabidka_polozky"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    poradi = Column(Integer, nullable=False, default=0, server_default="0")

    # Odkud položka přišla. SET NULL: smazání položky z katalogu nesmí shodit
    # nabídku – zůstane v ní snapshot názvu a ceny.
    technologie_id = Column(
        Integer, ForeignKey("technologie.id", ondelete="SET NULL"), nullable=True, index=True
    )

    kod = Column(String, nullable=False, default="", server_default="")
    nazev = Column(String, nullable=False)
    popis = Column(Text, nullable=False, default="", server_default="")
    jednotka = Column(String, nullable=False, default="ks", server_default="ks")

    mnozstvi = Column(Numeric(12, 3), nullable=False, default=1, server_default="1")
    cena_jednotkova = Column(Numeric(12, 2), nullable=True)  # prodejní, bez DPH
    # Snapshot nákupní ceny kvůli marži. Vidí ho jen právo `nabidkovac_katalog`.
    nakup_jednotkovy = Column(Numeric(12, 2), nullable=True)
    sleva_procent = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    sazba_dph = Column(Numeric(5, 4), nullable=True)

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    nabidka = relationship("Nabidka", back_populates="polozky")


class NabidkaDokument(Base):
    """Nahraný soubor k nabídce (kap. 4.4 SPEC).

    V této fázi se soubor jen uloží a založí se záznam se stavem "nahrano".
    Skutečné zpracování (LLM extrakce z PDF, parsování CSV) se NEDĚLÁ.
    """

    __tablename__ = "nabidka_dokumenty"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    typ = Column(String, nullable=False)  # jedna z TYPY_DOKUMENTU
    soubor_cesta = Column(String, nullable=False)  # cesta na disku (relativní k UPLOAD_DIR)
    puvodni_nazev = Column(String, nullable=False, default="", server_default="")
    velikost_bajtu = Column(Integer, nullable=True)

    stav_zpracovani = Column(
        String,
        nullable=False,
        default=VYCHOZI_STAV_ZPRACOVANI,
        server_default=VYCHOZI_STAV_ZPRACOVANI,
    )

    nahral_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    nahrano_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    nabidka = relationship("Nabidka", back_populates="dokumenty")


class SpotrebaProfil(Base):
    """15minutový diagram spotřeby / maxim (kap. 4.5 SPEC).

    Volba uložení: širší tabulka řádek-na-interval s indexem na
    (nabidka_id, cas). Časová řada je sice objemná (~35 040 řádků/rok na
    zákazníka), ale appka jinde pracuje relačně (viz matice/finance) a
    dotazy typu "výroba vs. spotřeba v čase" nad indexovanou tabulkou jsou
    přímočaré. Kdyby se objem ukázal jako problém, dá se přejít na denní
    JSONB agregaci bez zásahu do zbytku modelu (řešíme, až budou reálná data).

    Plnění (parsování CSV) se v tomto promptu NEIMPLEMENTUJE – tabulka jen
    existuje, aby na ni šlo navázat.

    Unikátnost (nabidka_id, cas) je DB pojistka proti dvojímu profilu (audit
    16. 7. 2026, SP-2): dva nahrané soubory se dřív tiše sečetly (2× „roční“
    spotřeba). Zpracování profilu maže celý předchozí profil nabídky
    („poslední vyhrává“) a duplicitní časy v souboru (podzimní přechod času)
    slučuje ještě před vkladem. Na existující DB doplňuje unique index
    `_lehka_migrace()` v main.py (včetně deduplikace, jinak by start spadl).
    """

    __tablename__ = "spotreba_profil"
    __table_args__ = (
        UniqueConstraint("nabidka_id", "cas", name="uq_spotreba_profil_nabidka_cas"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cas = Column(DateTime(timezone=True), nullable=False, index=True)
    hodnota_kwh = Column(Numeric(14, 4), nullable=True)  # spotřeba (PPA/Prodej)
    hodnota_kw = Column(Numeric(14, 4), nullable=True)  # maximum (Peak shaving)
    zdroj_dokument_id = Column(
        Integer, ForeignKey("nabidka_dokumenty.id", ondelete="SET NULL"), nullable=True
    )


class ExtrahovanaDataFaktury(Base):
    """Výstup LLM extrakce z PDF faktury (kap. 4.6 SPEC).

    Vždy s příznakem `zkontrolovano_ok`, aby bylo jasné, že se nepočítá nad
    nedůvěryhodnými daty. Samotná extrakce (Claude API) se tu NEIMPLEMENTUJE
    – řádky sem bude zapisovat navazující prompt. `surova_extrakce_json` drží
    celý raw výstup LLM pro debug a pozdější zpřesňování promptu.
    """

    __tablename__ = "extrahovana_data_faktury"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dokument_id = Column(
        Integer, ForeignKey("nabidka_dokumenty.id", ondelete="CASCADE"), nullable=False, index=True
    )

    dodavatel_text = Column(String, nullable=True)  # jak LLM přečetl dodavatele (informativní)
    cena_kwh = Column(Numeric(12, 4), nullable=True)
    rocni_spotreba_kwh = Column(Numeric(14, 3), nullable=True)
    rezervovany_prikon_kw = Column(Numeric(12, 3), nullable=True)
    # Další pole se doplní podle reálných faktur, až budou k dispozici vzorky.

    zkontrolovano_ok = Column(Boolean, nullable=False, default=False, server_default="false")
    upravil_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    upraveno_at = Column(DateTime(timezone=True), nullable=True)

    surova_extrakce_json = Column(JSONB, nullable=True)  # celý raw výstup LLM


class SazbaDistributoru(Base):
    """Sazby distributorů pro peak shaving (METODIKA-peak-shaving.md, kap. 3.1).

    Nese DVĚ různé tarifní struktury (2026 vs. 2027, kap. 4.6). Proto ne pevné
    sloupce pro ceny, ale `struktura_tarifu` + flexibilní JSONB `parametry`
    (stejný princip jako VypoctovaNastaveni.parametry) – až ERÚ zveřejní sazby
    2027, doplní se jen řádek, žádná přestavba schématu.

    Obsah `parametry` podle struktury (vše bez DPH):
      stara_2026 → {cena_rezervovana_kapacita_kc_kw_rok, cena_prekroceni_kc_kw}
      nova_2027  → {sazba_a_kapacita_kc_kw_rok, sazba_a_zmereny_max_kc_kw_mesic,
                    sazba_b_kapacita_kc_kw_rok, sazba_b_zmereny_max_kc_kw_mesic}

    `parametry` je nullable: u `nova_2027` zůstává NULL, dokud ERÚ nezveřejní
    cenové rozhodnutí (kap. 4.6) – appka pak u roku 2027 ukáže „čeká se na
    oficiální sazby ERÚ“ místo čísel.

    `platne_od`/`platne_do` drží historii (sazby se mění každý rok) kvůli
    zpětné dohledatelnosti, se kterou sazbou byla nabídka počítána.
    """

    __tablename__ = "sazby_distributoru"
    __table_args__ = (
        # Jeden platný řádek na kombinaci distributor × hladina × struktura
        # × začátek platnosti (historii odlišuje právě platne_od).
        UniqueConstraint(
            "distributor",
            "napetova_hladina",
            "struktura_tarifu",
            "platne_od",
            name="uq_sazba_distributor_hladina_struktura_od",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    distributor = Column(String, nullable=False, index=True)  # jedna z DISTRIBUTORI
    napetova_hladina = Column(String, nullable=False)  # jedna z NAPETOVE_HLADINY
    struktura_tarifu = Column(String, nullable=False)  # jedna ze STRUKTURY_TARIFU

    # NULL = struktura připravená, ale ceny ještě nejsou (typicky nova_2027).
    parametry = Column(JSONB, nullable=True)

    platne_od = Column(Date, nullable=False)
    platne_do = Column(Date, nullable=True)  # NULL = platí zatím bez konce

    # Modelový/nezávazný odhad? U nova_2027 ano – ERÚ vydá závazné cenové
    # rozhodnutí až v listopadu 2026 (PROMPT 2027). UI to u čísel označí.
    je_modelovy_odhad = Column(Boolean, nullable=False, default=False, server_default="false")

    # Volitelná poznámka ke zdroji/ověření (kap. 3.1 rozlišuje „potvrzeno“ vs.
    # „doporučuji ověřit“) – pomůže kolegovi, co sazby doplňuje přes admin.
    poznamka = Column(Text, nullable=False, default="", server_default="")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )


class NavrhovaneReseni(Base):
    """Výstup výpočtu – jedna nabídka jich může mít víc (kap. 4.7 SPEC).

    Např. PPA + peak shaving baterie současně; zákazník/OZ si na konci
    vybírá z variant (`vybrano_zakaznikem`). `popis_json` je flexibilní,
    dokud nejsou vzorce finální (velikost elektrárny/baterie, cena, délka
    kontraktu, ROI, payback…). Výpočet se tu NEDĚLÁ.
    """

    __tablename__ = "navrhovana_reseni"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    typ_reseni = Column(String, nullable=False)  # jedna z TYPY_NABIDKY
    popis_json = Column(JSONB, nullable=False, default=dict, server_default="{}")
    vybrano_zakaznikem = Column(Boolean, nullable=True)  # NULL = ještě nerozhodnuto
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    nabidka = relationship("Nabidka", back_populates="reseni")


class NabidkaVystup(Base):
    """Uložená nabídková šablona konkrétní nabídky (per typ řešení).

    Dan zvolil variantu „šablona zvlášť u každé nabídky“ – žádný globální
    master. Nová nabídka startuje z kódové výchozí předlohy
    (`sablona_katalog.vychozi_sablona`), a jakmile ji OZ v editoru uloží,
    uloží se sem override konkrétní nabídky. `konfigurace_json` drží seznam
    bloků (druh, viditelný, nadpis, text, vybraná pole) – strukturu i
    whitelist polí hlídá `sablona_katalog`.

    Jeden řádek na (nabídka × typ řešení), protože jedna nabídka může mít
    víc řešení (PPA i peak shaving) a každé má vlastní šablonu. Nová tabulka
    vzniká přes `create_all` – žádná migrace navíc.
    """

    __tablename__ = "nabidka_vystup"
    __table_args__ = (
        UniqueConstraint("nabidka_id", "typ_reseni", name="uq_nabidka_vystup_nabidka_typ"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    typ_reseni = Column(String, nullable=False)  # "ppa" / "peak_shaving"
    konfigurace_json = Column(JSONB, nullable=False, default=dict, server_default="{}")

    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )


class VystupSablona(Base):
    """Pojmenované rozvržení nabídky k opakovanému použití.

    `NabidkaVystup` je šablona *jedné* nabídky. Tady jsou naopak rozvržení
    uložená napříč nabídkami: obchodník si vyladí vizuál, dá „Uložit jako
    šablonu“ a příště ho jen vybere. Ukládá se pouze rozvržení (bloky, texty,
    šířky) – žádná zákaznická čísla, ta se do nabídky vždy dopočítají z jejího
    vlastního řešení.

    Jedna šablona na (název × typ řešení): PPA a peak shaving mají jiná pole,
    takže se šablony mezi typy nepřenášejí. Tabulka vzniká přes `create_all`.
    """

    __tablename__ = "vystup_sablony"
    __table_args__ = (
        UniqueConstraint("nazev", "typ_reseni", name="uq_vystup_sablony_nazev_typ"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nazev = Column(String, nullable=False)
    typ_reseni = Column(String, nullable=False, index=True)  # "ppa" / "peak_shaving"
    konfigurace_json = Column(JSONB, nullable=False, default=dict, server_default="{}")

    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    aktualizovano_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    vytvoril_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )


class GenerovanaNabidkaPdf(Base):
    """Vygenerované PDF nabídky pro zákazníka (kap. 4.8 SPEC).

    Vzniká tlačítkem „Uložit do PDF" v editoru výstupu: prohlížeč pošle hotovou
    podobu papíru, Chromium z ní udělá PDF (`nabidkovac/pdf.py`) a soubor se
    uloží k nabídce. Historie se NEMAŽE – jedna nabídka se přepočítá a vytiskne
    víckrát a musí být dohledatelné, co přesně zákazník dostal a kdy.

    `reseni_id` je nullable – jedno PDF může shrnovat víc řešení najednou
    (kombinace opatření), takže se neváže na jedno konkrétní.
    """

    __tablename__ = "generovane_nabidky_pdf"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reseni_id = Column(
        Integer, ForeignKey("navrhovana_reseni.id", ondelete="SET NULL"), nullable=True
    )
    # Ze které šablony výstupu PDF vzniklo ("ppa" / "peak_shaving" /
    # "kombinace"). Nullable kvůli řádkům z doby před tímhle tlačítkem.
    typ_reseni = Column(String, nullable=True, index=True)
    # "pdf" = nabídka pro zákazníka, "xlsx" = interní výpočtový model k dolaďování.
    # Obojí vzniká jedním kliknutím a leží vedle sebe pod stejným jménem, proto
    # sdílí tabulku i frontu na Disk; liší se jen formátem a příponou.
    format = Column(String, nullable=False, default="pdf", server_default="pdf", index=True)
    # Jméno souboru pro člověka (NAB-26-0007_ppa_2026-08-03.pdf). Uložená cesta
    # ho neobsahuje čitelně – před názvem je uuid, aby se soubory nepřepisovaly.
    nazev = Column(String, nullable=False, default="", server_default="")
    soubor_cesta = Column(String, nullable=False)

    # Kopie na Disku. Prázdné = ještě se nenahrála (běží fronta) nebo nahrát
    # nešla; podle toho UI pozná, jestli má nabídnout odkaz na Disk.
    disk_file_id = Column(String, nullable=False, default="", server_default="")
    disk_url = Column(String, nullable=False, default="", server_default="")

    vygeneroval_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vygenerovano_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    vygeneroval = relationship("User")


# --------------------------------------------------------------- fronta výpočtů
# Stavy úlohy ve frontě. `bezi` drží worker, aby dvě instance nevzaly totéž.
STAVY_VYPOCTU = ("ceka", "bezi", "hotovo", "chyba", "zruseno")


class VypocetFronta(Base):
    """Fronta dlouhých výpočtů, které web proces neunese.

    Prohledání celého katalogu baterií (84 produktů × 1–5 kusů) nad ročním
    15min diagramem trvá minuty. Uvnitř uvicornu by to dotlačilo appku k 502 –
    stejná zkušenost jako s konektorem a se stahováním pošty (rozhodnutí Dana
    o samostatných procesech). Úloha se proto jen zařadí sem a odbaví ji
    `app/nabidkovac/vypocet_worker.py` jako vlastní služba.

    Tvar tabulky je záměrně stejný jako u `konektor_job_queue`: typ + payload +
    stav + pokus + chyba. Navíc drží **pokrok** (`hotovo_variant` z `celkem_variant`),
    aby panel mohl ukázat „120 ze 420" místo neurčitého kolečka, a `vysledek_json`,
    do kterého worker uloží hotový výpočet.

    Proč se výsledek neukládá rovnou do `navrhovana_reseni`: dokud výpočet
    nedoběhne, není co uložit, a kdyby se uložil rozdělaný, panel by ho ukázal
    jako hotovou nabídku. Worker proto zapíše `navrhovana_reseni` teprve na
    konci a tady zůstane jen záznam o průběhu.
    """

    __tablename__ = "nabidkovac_vypocet_fronta"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Druh úlohy, ať se fronta dá použít i pro další dlouhé výpočty
    # ("ppa_bess_katalog" je zatím jediný).
    typ = Column(String, nullable=False, index=True)
    # Vstup výpočtu tak, jak ho poslal panel (schéma `PpaBessVstup`).
    vstup_json = Column(JSONB, nullable=False)
    stav = Column(String, nullable=False, default="ceka", server_default="ceka", index=True)

    # Pokrok pro UI. `celkem_variant` zná až worker (po dotazu na katalog),
    # takže dokud je 0, panel ukáže jen „počítá se".
    celkem_variant = Column(Integer, nullable=False, default=0, server_default="0")
    hotovo_variant = Column(Integer, nullable=False, default=0, server_default="0")
    # Krátká zpráva o tom, co worker právě dělá („prohledávám katalog…").
    zprava = Column(String, nullable=False, default="", server_default="")

    vysledek_json = Column(JSONB, nullable=True)
    # Řešení, které worker nakonec uložil – panel si podle něj najde výsledek.
    reseni_id = Column(
        Integer, ForeignKey("navrhovana_reseni.id", ondelete="SET NULL"), nullable=True
    )
    chyba = Column(Text, nullable=True)
    pokusu = Column(Integer, nullable=False, default=0, server_default="0")

    zadal_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vytvoreno_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    zahajeno_at = Column(DateTime(timezone=True), nullable=True)
    dokonceno_at = Column(DateTime(timezone=True), nullable=True)
