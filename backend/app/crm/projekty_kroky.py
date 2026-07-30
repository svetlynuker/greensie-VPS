"""Kroky projektu: rozbalení šablony a dopočet termínů podle návazností.

Proč vůbec návaznosti: u realizace nejde o seznam nezávislých úkolů. „Předat
dokumentaci" nemá termín sám za sebe — má ho odvozený od toho, kdy skončí
„Zaměření na místě". Když se zaměření o týden zdrží, posunou se i všechny kroky
za ním. Bez toho by termíny po první změně lhaly a nikdo by jim nevěřil.

Jak se termín počítá:
  * krok bez předchůdce  → od `zahajeni` projektu,
  * krok s předchůdcem   → od jeho SKUTEČNÉHO dokončení, pokud už hotový je,
                            jinak od jeho plánovaného termínu,
  * ke startu se přičte `delka_dni`.

Ručně přepsaný termín (`termin_rucne`) se NIKDY nepřepisuje. Když někdo řekne
„tenhle krok bude 15. srpna, protože tehdy přijede jeřáb", přepočet to musí
respektovat — jinak by ruční zásah zmizel při první změně jinde.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.crm.models import CrmProjekt, ProjektKrok, ProjektSablona


def rozbal_sablonu(db: Session, projekt: CrmProjekt, sablona: ProjektSablona) -> list[ProjektKrok]:
    """Vytvoří kroky projektu podle šablony a naváže je na sebe.

    Návaznost je v šabloně uložená jako POŘADÍ předchůdce; tady se překlopí na
    skutečné `zavisi_na_id`, protože kroky projektu už mají vlastní id.

    Kroky se PŘIDÁVAJÍ, nemažou se existující — projekt může vzniknout z jedné
    šablony a pak dostat ještě druhou (např. „FVE" + „Dotace").
    """
    sablonove = sorted(sablona.kroky, key=lambda k: (k.poradi, k.id))
    posun = len(projekt.kroky or [])  # už existující kroky zůstávají před novými

    podle_poradi: dict[int, ProjektKrok] = {}
    nove: list[ProjektKrok] = []
    for i, sk in enumerate(sablonove):
        krok = ProjektKrok(
            projekt_id=projekt.id,
            nazev=sk.nazev,
            popis=sk.popis or "",
            poradi=posun + i,
            delka_dni=max(1, int(sk.delka_dni or 1)),
            stav="ceka",
        )
        db.add(krok)
        nove.append(krok)
        podle_poradi[sk.poradi] = krok

    # ID vzniknou až po flush; teprve pak se dají navázat závislosti.
    db.flush()
    for sk, krok in zip(sablonove, nove):
        if sk.zavisi_na_poradi is None:
            continue
        predchudce = podle_poradi.get(sk.zavisi_na_poradi)
        if predchudce is not None and predchudce.id != krok.id:
            krok.zavisi_na_id = predchudce.id
    db.flush()
    return nove


def _start_kroku(krok: ProjektKrok, mapa: dict[int, ProjektKrok], zahajeni: date | None) -> date | None:
    """Od kterého dne se krok počítá (viz pravidla v docstringu modulu)."""
    if krok.zavisi_na_id is None:
        return zahajeni
    predchudce = mapa.get(krok.zavisi_na_id)
    if predchudce is None:
        return zahajeni
    if predchudce.hotovo_at is not None:
        return predchudce.hotovo_at.date()
    return predchudce.termin


def prepocitej_terminy(db: Session, projekt: CrmProjekt) -> None:
    """Dopočítá termíny všech kroků projektu podle návazností.

    Jde přes kroky v pořadí a respektuje ručně zadané termíny. Cyklus
    v závislostech (A čeká na B, B na A) se nemůže zacyklit: každý krok se
    počítá nejvýš jednou a chybějící start znamená prostě nevyplněný termín.
    """
    kroky = sorted(projekt.kroky or [], key=lambda k: (k.poradi, k.id))
    mapa = {k.id: k for k in kroky}

    for krok in kroky:
        if krok.termin_rucne:
            continue  # ruční termín je rozhodnutí člověka, nepřepisujeme
        start = _start_kroku(krok, mapa, projekt.zahajeni)
        krok.termin = (
            start + timedelta(days=max(1, int(krok.delka_dni or 1))) if start is not None else None
        )
    db.flush()


def dostupny(krok: ProjektKrok, mapa: dict[int, ProjektKrok]) -> bool:
    """Může se na kroku začít pracovat? (předchůdce je hotový nebo přeskočený)

    Slouží UI, aby bylo vidět, co se dá dělat hned a co ještě na něco čeká.
    """
    if krok.zavisi_na_id is None:
        return True
    predchudce = mapa.get(krok.zavisi_na_id)
    if predchudce is None:
        return True
    return predchudce.stav in ("hotovo", "preskoceno")


def souhrn(projekt: CrmProjekt) -> dict:
    """Kolik kroků je hotovo a co je nejbližší termín – pro dlaždici a seznam."""
    kroky = list(projekt.kroky or [])
    hotovo = sum(1 for k in kroky if k.stav in ("hotovo", "preskoceno"))
    otevrene_terminy = [k.termin for k in kroky if k.termin and k.stav not in ("hotovo", "preskoceno")]
    return {
        "kroku": len(kroky),
        "hotovo": hotovo,
        "procent": round(100 * hotovo / len(kroky)) if kroky else 0,
        "nejblizsi_termin": min(otevrene_terminy).isoformat() if otevrene_terminy else None,
        # Kolik kroků je po termínu – to je to, co má vedení zajímat první.
        "po_terminu": sum(
            1
            for k in kroky
            if k.termin and k.stav not in ("hotovo", "preskoceno") and k.termin < date.today()
        ),
    }


VYCHOZI_SABLONY = [
    {
        "nazev": "FVE – standardní realizace",
        "popis": "Typický průběh instalace fotovoltaiky od podpisu po předání.",
        "kategorie": ["ppa", "prodej"],
        "kroky": [
            ("Zaměření na místě", 5, None),
            ("Projektová dokumentace", 10, 0),
            ("Žádost o připojení k distribuci", 5, 1),
            ("Objednání technologie", 3, 1),
            ("Montáž konstrukce a panelů", 10, 3),
            ("Elektroinstalace a zapojení", 5, 4),
            ("Revize a zkoušky", 3, 5),
            ("Předání zákazníkovi", 2, 6),
        ],
    },
    {
        "nazev": "Peak shaving – instalace baterie",
        "popis": "Bateriové úložiště pro srážení špiček odběru.",
        "kategorie": ["peak_shaving"],
        "kroky": [
            ("Ověření odběrného místa a rezervované kapacity", 5, None),
            ("Projekt zapojení baterie", 8, 0),
            ("Objednání baterie a měniče", 3, 1),
            ("Stavební příprava stanoviště", 7, 1),
            ("Instalace baterie", 5, 3),
            ("Nastavení řízení a zkušební provoz", 5, 4),
            ("Úprava rezervované kapacity u distributora", 10, 5),
            ("Předání zákazníkovi", 2, 5),
        ],
    },
]


def seed_sablony(db: Session) -> None:
    """Naseeduje výchozí šablony, pokud žádné nejsou (idempotentní).

    Jen když je tabulka úplně prázdná – jakmile si vedení šablony upraví nebo
    smaže, seed do nich už nesahá.
    """
    from app.crm.models import ProjektSablonaKrok

    if db.query(ProjektSablona.id).first() is not None:
        return
    for s in VYCHOZI_SABLONY:
        sablona = ProjektSablona(nazev=s["nazev"], popis=s["popis"], kategorie=s["kategorie"])
        db.add(sablona)
        db.flush()
        for poradi, (nazev, dni, zavisi) in enumerate(s["kroky"]):
            db.add(
                ProjektSablonaKrok(
                    sablona_id=sablona.id,
                    nazev=nazev,
                    poradi=poradi,
                    delka_dni=dni,
                    zavisi_na_poradi=zavisi,
                )
            )
    db.commit()
