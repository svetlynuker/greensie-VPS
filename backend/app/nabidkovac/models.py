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
TYPY_NABIDKY = ("ppa", "prodej", "peak_shaving")

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

# Distributoři, se kterými appka počítá. Naostro jede zatím jen "cez"
# (kap. 6 bod 5), "egd"/"pre" se doplní přes admin, až budou čísla ověřená.
DISTRIBUTORI = ("cez", "egd", "pre")

# Peak shaving řešíme jen pro VN a VVN, NN appka nenabízí (kap. 1 / kap. 6 bod 4).
NAPETOVE_HLADINY = ("vn", "vvn")

# Dvě různé tarifní struktury – od 1. 1. 2027 mění ERÚ způsob zpoplatnění
# kapacity na VN/VVN (kap. 4.6). Ne jiná čísla do stejného vzorce, ale jiná
# STRUKTURA výpočtu → proto typ struktury + flexibilní JSONB parametry.
STRUKTURY_TARIFU = ("stara_2026", "nova_2027")


class Technologie(Base):
    """Katalog technologií (FVE panely, invertory, baterie…).

    Zatím se plní ručně přes admin rozhraní (jen vedení/admin). Později
    přibude synchronizace z Raynet API – pro tu je připravené pole
    `raynet_id` + `synchronizovano_at` (obojí nullable, teď se nepoužívá).
    """

    __tablename__ = "technologie"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False)  # jedna z TYPY_TECHNOLOGIE
    nazev = Column(String, nullable=False)
    model = Column(String, nullable=False, default="", server_default="")

    # Podle typu se plní buď výkon (panel/invertor), nebo kapacita (baterie).
    # Necháváme obě nullable, ať katalog pobere všechny typy jednou tabulkou.
    vykon_kw = Column(Numeric(12, 3), nullable=True)
    kapacita_kwh = Column(Numeric(12, 3), nullable=True)

    cena_kc = Column(Numeric(12, 2), nullable=True)  # CAPEX jednotky
    ucinnost = Column(Numeric(6, 4), nullable=True)  # 0–1, volitelné dle typu

    dostupnost = Column(Boolean, nullable=False, default=True, server_default="true")

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


class Nabidka(Base):
    """Hlavní záznam zakázky/nabídky (kap. 4.3 SPEC).

    `typ` = za jakým účelem OZ nabídku založil (z které podsekce vznikla),
    NE definitivní řešení – jedna zakázka může vygenerovat víc řešení
    (PPA + peak shaving) uložených v `navrhovana_reseni`.
    """

    __tablename__ = "nabidky"

    id = Column(Integer, primary_key=True, index=True)
    typ = Column(String, nullable=False)  # jedna z TYPY_NABIDKY

    zakaznik_nazev = Column(String, nullable=False, default="", server_default="")
    zakaznik_adresa = Column(String, nullable=False, default="", server_default="")
    # Pro budoucí PVGIS – lat/lng. Zatím ručně nebo geokódováním z adresy.
    zakaznik_gps_lat = Column(Numeric(9, 6), nullable=True)
    zakaznik_gps_lng = Column(Numeric(9, 6), nullable=True)

    stav = Column(
        String, nullable=False, default=VYCHOZI_STAV_NABIDKY, server_default=VYCHOZI_STAV_NABIDKY
    )

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

    vytvoril = relationship("User")
    dokumenty = relationship(
        "NabidkaDokument", back_populates="nabidka", cascade="all, delete-orphan"
    )
    reseni = relationship(
        "NavrhovaneReseni", back_populates="nabidka", cascade="all, delete-orphan"
    )


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
    """

    __tablename__ = "spotreba_profil"

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


class GenerovanaNabidkaPdf(Base):
    """Vygenerované PDF nabídky (kap. 4.8 SPEC).

    `reseni_id` je nullable – jedno PDF může shrnovat víc řešení najednou.
    Generování PDF se tu NEIMPLEMENTUJE (layout se řeší samostatně).
    """

    __tablename__ = "generovane_nabidky_pdf"

    id = Column(Integer, primary_key=True, index=True)
    nabidka_id = Column(
        Integer, ForeignKey("nabidky.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reseni_id = Column(
        Integer, ForeignKey("navrhovana_reseni.id", ondelete="SET NULL"), nullable=True
    )
    soubor_cesta = Column(String, nullable=False)
    vygeneroval_user_id = Column(
        Integer, ForeignKey("uzivatele.id", ondelete="SET NULL"), nullable=True
    )
    vygenerovano_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
