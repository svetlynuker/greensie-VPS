"""15minutové diagramy odběru u odběrného místa (CRM-46, etapa 2).

Diagram patří odběrnému MÍSTU. Nahraje se jednou a použije se pro všechny
nabídky té provozovny — dřív visel na nabídce, takže se tentýž export
z portálu distributora nahrával ke každé nabídce znovu.

DVĚ VĚCI, KTERÉ TENHLE MODUL DĚLÁ VĚDOMĚ JINAK NEŽ PŮVODNÍ TOK:

1. **Parsuje se hned při nahrání.** Dokud se parsovalo až na kliknutí v panelu
   výpočtu, šlo nahrát nepoužitelný soubor a poznalo se to teprve u výpočtu —
   nebo vůbec, a nabídka se spočítala bez dat spotřeby (nahlásil Dan
   31. 7. 2026). Souhrn (období, počet intervalů, spotřeba, maximum) se uloží
   k diagramu, takže je v seznamu vidět, jestli soubor pokrývá celý rok.

2. **Řada se do CRM nekopíruje.** Zůstává uložený soubor; do `spotreba_profil`
   se zapíše až ve chvíli, kdy si diagram vezme konkrétní nabídka
   (`pouzij_pro_nabidku`). Nabídka si tím drží čísla, se kterými odešla
   zákazníkovi, a novější diagram jí je nepřepíše sám (rozhodnutí Dana).

Selhání parsování NENÍ důvod odmítnout nahrání: soubor se uloží se stavem
"chyba" a textem důvodu. OZ tak vidí, co se pokazilo, a může nahrát jiný
export — místo aby mu appka jen řekla „nepovedlo se“ a nic nezůstalo.
"""

from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crm.models import CrmDiagram, OdberneMisto
from app.nabidkovac import profil_import, soubory

# Co se dá jako diagram nahrát (stejné přípony jako u profilu na nabídce).
POVOLENE_PRIPONY = {".csv", ".xls", ".xlsx"}

# Strop velikosti souboru. Roční 15min export má ~35 tis. řádků a v XLSX
# typicky do 2 MB; 25 MB je stejný strop jako u dokumentů nabídky.
MAX_BAJTU = soubory.MAX_BAJTU


def over_priponu(nazev: str) -> str:
    pripona = Path(nazev or "").suffix.lower()
    if pripona not in POVOLENE_PRIPONY:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Diagram odběru musí být {', '.join(sorted(POVOLENE_PRIPONY))} "
                f"(dostal jsem {pripona or 'soubor bez přípony'})."
            ),
        )
    return pripona


def _interval_min(casy: list) -> int | None:
    """Délka intervalu z prvních dvou značek. Poznáme tak hodinový export."""
    if len(casy) < 2:
        return None
    minut = round((casy[1] - casy[0]).total_seconds() / 60)
    return minut if minut > 0 else None


def souhrn_rady(body: list[tuple]) -> dict:
    """Souhrn naparsované řady (čas, kW) pro seznam diagramů.

    Spotřeba se počítá jako součet kW × délka intervalu v hodinách, ne jako
    součet kW — v exportu je ČINNÝ VÝKON, takže sečtením samotných kW by
    u 15min dat vyšla čtyřnásobná „spotřeba“ (na tenhle omyl v jiné podobě
    upozorňuje i docstring `profil_import`).
    """
    if not body:
        return {
            "pocet_intervalu": 0,
            "obdobi_od": None,
            "obdobi_do": None,
            "interval_min": None,
            "spotreba_mwh": None,
            "max_kw": None,
        }
    casy = [c for c, _ in body]
    hodnoty = [float(v) for _, v in body if v is not None]
    minut = _interval_min(casy)
    hodin = (minut or 15) / 60.0
    return {
        "pocet_intervalu": len(body),
        "obdobi_od": min(casy),
        "obdobi_do": max(casy),
        "interval_min": minut,
        "spotreba_mwh": round(sum(hodnoty) * hodin / 1000.0, 3) if hodnoty else None,
        "max_kw": round(max(hodnoty), 3) if hodnoty else None,
    }


def nahraj(
    db: Session,
    misto: OdberneMisto,
    nazev: str,
    obsah: bytes,
    user_id: int | None,
    pripad_id: int | None = None,
    popis: str = "",
) -> CrmDiagram:
    """Uloží soubor k místu a hned ho naparsuje. Vrací uložený diagram.

    Soubor jde do `UPLOAD_DIR/om-<id>/`, aby se nemíchal se soubory nabídek.
    """
    pripona = over_priponu(nazev)
    if not obsah:
        raise HTTPException(status_code=422, detail="Soubor je prázdný.")
    if len(obsah) > MAX_BAJTU:
        raise HTTPException(
            status_code=422,
            detail=f"Soubor je větší než {MAX_BAJTU // (1024 * 1024)} MB.",
        )

    rel_cesta = soubory.uloz_soubor(f"om-{misto.id}", nazev or "diagram", obsah)
    d = CrmDiagram(
        odberne_misto_id=misto.id,
        obchodni_pripad_id=pripad_id,
        soubor_cesta=rel_cesta,
        puvodni_nazev=nazev or "diagram",
        velikost_bajtu=len(obsah),
        popis=(popis or "").strip(),
        nahral_user_id=user_id,
    )

    try:
        body = profil_import.nacti_profil(str(soubory.UPLOAD_DIR / rel_cesta), pripona)
        body, _ = profil_import.deduplikuj_casy(body)
    except (ValueError, FileNotFoundError) as e:
        # Soubor zůstává uložený i při chybě – OZ uvidí, co se nepovedlo,
        # a nemusí ho stahovat z portálu znovu, aby zkusil jiný typ.
        d.stav = "chyba"
        d.chyba_text = str(e)[:500]
        db.add(d)
        db.commit()
        db.refresh(d)
        return d

    s = souhrn_rady(body)
    d.stav = "zpracovano"
    d.obdobi_od = s["obdobi_od"]
    d.obdobi_do = s["obdobi_do"]
    d.pocet_intervalu = s["pocet_intervalu"]
    d.interval_min = s["interval_min"]
    d.spotreba_mwh = s["spotreba_mwh"]
    d.max_kw = s["max_kw"]
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def nacti_radu(d: CrmDiagram) -> list[tuple]:
    """Znovu naparsuje řadu ze uloženého souboru (pro použití v nabídce)."""
    if d.stav != "zpracovano":
        raise HTTPException(
            status_code=422,
            detail=f"Tenhle diagram se nepodařilo přečíst, nejde z něj počítat: {d.chyba_text}",
        )
    pripona = Path(d.soubor_cesta).suffix.lower()
    try:
        body = profil_import.nacti_profil(str(soubory.UPLOAD_DIR / d.soubor_cesta), pripona)
    except FileNotFoundError:
        raise HTTPException(status_code=422, detail="Soubor diagramu už na disku není.")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Diagram se nepodařilo přečíst: {e}")
    body, _ = profil_import.deduplikuj_casy(body)
    return body


def pouzij_pro_nabidku(db: Session, d: CrmDiagram, nabidka_id: int) -> dict:
    """Zapíše řadu diagramu do `spotreba_profil` dané nabídky.

    „Poslední vyhrává“ jako u dokumentu nabídky: celý dosavadní profil nabídky
    se zahodí a vloží se nový. Bez toho by se dva zdroje sečetly do dvojnásobné
    spotřeby (audit 16. 7. 2026, SP-2).

    `zdroj_dokument_id` zůstává NULL — profil nepřišel z `nabidka_dokumenty`,
    ale z diagramu místa. Odkaz na diagram drží nabídka na své straně
    (etapa 3), tady se nezakládá další vazba, která by mohla zestárnout.
    """
    from app.nabidkovac.models import SpotrebaProfil

    body = nacti_radu(d)
    db.query(SpotrebaProfil).filter(SpotrebaProfil.nabidka_id == nabidka_id).delete(
        synchronize_session=False
    )
    db.bulk_insert_mappings(
        SpotrebaProfil,
        [
            {"nabidka_id": nabidka_id, "cas": cas, "hodnota_kw": kw, "zdroj_dokument_id": None}
            for cas, kw in body
        ],
    )
    db.commit()
    s = souhrn_rady(body)
    return {
        "diagram_id": d.id,
        "nabidka_id": nabidka_id,
        "pocet": s["pocet_intervalu"],
        "od": s["obdobi_od"].isoformat() if s["obdobi_od"] else None,
        "do": s["obdobi_do"].isoformat() if s["obdobi_do"] else None,
        "max_kw": s["max_kw"],
        "spotreba_mwh": s["spotreba_mwh"],
    }


def vyzaduj_diagram(db: Session, diagram_id: int) -> CrmDiagram:
    d = db.get(CrmDiagram, diagram_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Diagram neexistuje")
    return d


def smaz(db: Session, d: CrmDiagram) -> None:
    """Smaže diagram i jeho soubor. Profily nabídek, které z něj počítaly,
    zůstávají — nabídka si drží svá čísla a nemá se změnit tím, že někdo
    uklidil podklad."""
    soubory.smaz_soubor(d.soubor_cesta)
    db.delete(d)
    db.commit()
