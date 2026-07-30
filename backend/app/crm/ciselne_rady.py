"""Generátor viditelných ID: OP-26-0301, NAB-26-0007, OBJ-26-0012, PRO-26-0301.

Formát: `PREFIX-RR-NNNN`, kde RR je dvojčíslí roku a NNNN číslo z řady dané
entity a roku. Řada se každý rok sama restartuje (rok je součástí klíče).

PROČ ŠÍŘKA 4 A POSUNUTÝ START: appka zatím koexistuje s Raynetem, který stejný
prefix už používá – ve složkách na Disku jsou čísla OP-26-002 až OP-26-228,
starší na tři místa, novější na čtyři (OP-26-0221). Kdyby appka začala od
OP-26-0001, vznikla by dvě různá čísla se stejným prefixem a nikdo by nepoznal,
které patří které zakázce; navíc by se rozbilo párování složek dokumentů, které
na Raynetím čísle stojí. Proto čtyři místa (jako novější Raynetí) a start řady
posazený nad nejvyšší známé Raynetí číslo s rezervou na další stovku
(`doporuceny_start`). Obojí se dá přenastavit v nastavení CRM.

PROJEKT MÁ ČÍSLO PO OBCHODNÍM PŘÍPADU: `PRO-26-0301` odpovídá `OP-26-0301`,
protože projekt vzniká jen z případu (nebo z jeho objednávky) a lidé je párují
očima. Když z jednoho případu vznikne druhý projekt, dostane suffix
`-2`, `-3`… (viz `cislo_projektu`) – jinak by dvě různé realizace nesly totéž
číslo.
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crm.models import ENTITY_CRM, CiselnaRada, ObchodniPripad

# Prefix a výchozí šířka pro každou entitu.
PREFIXY = {"op": "OP", "nab": "NAB", "obj": "OBJ", "pro": "PRO"}
VYCHOZI_SIRKA = 4


def _rok_dvojcisli(kdy: datetime | None = None) -> int:
    return (kdy or datetime.now()).year % 100


def formatuj(prefix: str, rok: int, cislo: int, sirka: int) -> str:
    """Složí viditelné ID. Když číslo přeteče šířku, prostě se rozšíří –
    nikdy se neodřezává, protože ID musí zůstat jednoznačné."""
    return f"{prefix}-{rok:02d}-{cislo:0{sirka}d}"


def dalsi_cislo(db: Session, entita: str, kdy: datetime | None = None) -> str:
    """Atomicky vydá další viditelné ID pro danou entitu.

    Řádek řady se zamkne (`FOR UPDATE`), takže dva OZ zakládající případ ve
    stejnou sekundu nedostanou totéž číslo. Volající je odpovědný za commit
    (číslo se přidělí ve stejné transakci jako záznam – když založení spadne,
    číslo se nespotřebuje).
    """
    if entita not in ENTITY_CRM:
        raise ValueError(f"Neznámá entita číselné řady: {entita}")

    rok = _rok_dvojcisli(kdy)
    rada = (
        db.query(CiselnaRada)
        .filter(CiselnaRada.entita == entita, CiselnaRada.rok == rok)
        .with_for_update()
        .first()
    )
    if rada is None:
        # První číslo v roce. Šířku a start převezmeme z loňské řady, aby se
        # nastavení (např. posunutý start kvůli Raynetu) nemuselo dělat znovu.
        loni = (
            db.query(CiselnaRada)
            .filter(CiselnaRada.entita == entita)
            .order_by(CiselnaRada.rok.desc())
            .first()
        )
        rada = CiselnaRada(
            entita=entita,
            rok=rok,
            prefix=PREFIXY[entita],
            sirka=loni.sirka if loni is not None else VYCHOZI_SIRKA,
            dalsi_cislo=1,
            pocatek=1,
        )
        db.add(rada)
        db.flush()

    cislo = int(rada.dalsi_cislo or 1)
    rada.dalsi_cislo = cislo + 1
    db.flush()
    return formatuj(rada.prefix, rada.rok, cislo, int(rada.sirka or VYCHOZI_SIRKA))


def cislo_projektu(db: Session, pripad: ObchodniPripad, pocet_existujicich: int) -> str:
    """Číslo projektu = číslo případu s prefixem PRO.

    `PRO-26-0301` pro první projekt případu `OP-26-0301`. Druhý projekt téhož
    případu dostane `PRO-26-0301-2` – bez suffixu by dvě realizace nesly
    stejné číslo a nešly by od sebe rozeznat.
    """
    zaklad = pripad.cislo.replace(PREFIXY["op"], PREFIXY["pro"], 1)
    if pocet_existujicich <= 0:
        return zaklad
    return f"{zaklad}-{pocet_existujicich + 1}"


def nejvyssi_raynet_cislo(db: Session, rok: int | None = None) -> int | None:
    """Nejvyšší Raynetí číslo obchodního případu (OP-26-0223 → 223) pro daný rok.

    Slouží k nastavení startu vlastní řady tak, aby se čísla appky a Raynetu
    nepřekrývala – dokud běží obojí, stejné ID u dvou různých zakázek by bylo
    v dokumentech i ve složkách na Disku nedohledatelné.

    Hledá ve DVOU zdrojích, protože každý zná jinou část skutečnosti:
      1) `raynet_code` u případů, které už appka vede,
      2) názvy složek obchodních případů, které drží konektor
         (`konektor_entity_folder`, entity='deal', name začíná číslem OP) –
         tam jsou i případy, které v appce ještě nejsou.
    Vrací None, když se nenajde ani jedno.
    """
    import re

    from sqlalchemy import text

    rok = rok if rok is not None else _rok_dvojcisli()
    predpona = f"{PREFIXY['op']}-{rok:02d}-"
    nejvyssi: int | None = None

    def _zvaz(hodnota: str | None) -> None:
        nonlocal nejvyssi
        if not hodnota:
            return
        # Číslo bereme jen ze začátku názvu složky („OP-26-0223 Firma s.r.o.").
        nalez = re.match(rf"{re.escape(predpona)}(\d+)", str(hodnota).strip(), re.IGNORECASE)
        if nalez is None:
            return
        cislo = int(nalez.group(1))
        if nejvyssi is None or cislo > nejvyssi:
            nejvyssi = cislo

    for (kod,) in (
        db.query(ObchodniPripad.raynet_code)
        .filter(ObchodniPripad.raynet_code.ilike(f"{predpona}%"))
        .all()
    ):
        _zvaz(kod)

    # Konektor je nepovinná závislost: když jeho tabulka není (nebo je prázdná),
    # návrh se prostě opře jen o to, co ví CRM.
    try:
        radky = db.execute(
            text(
                "SELECT name FROM konektor_entity_folder "
                "WHERE entity = 'deal' AND name ILIKE :vzor"
            ),
            {"vzor": f"{predpona}%"},
        ).fetchall()
    except Exception:
        radky = []
    for (nazev,) in radky:
        _zvaz(nazev)

    return nejvyssi


def doporuceny_start(nejvyssi_raynet: int) -> int:
    """Kde má začít vlastní řada, aby nikdy nekolidovala s Raynetem.

    Ne „nejvyšší + 1": Raynet během koexistence vydává čísla dál, takže by se
    obě řady po několika zakázkách potkaly. Zaokrouhlíme na další stovku
    (228 → 301), čímž zůstane rezerva pro dožívající Raynet a zároveň je na
    čísle vidět, že vzniklo v appce.
    """
    return ((nejvyssi_raynet // 100) + 1) * 100 + 1


def seed_rady(db: Session) -> None:
    """Založí řady pro aktuální rok, pokud ještě nejsou (idempotentní).

    U obchodních případů se start NEnastavuje na 1: v Raynetu už čísla
    OP-26-NNN existují (konektor je zná z názvů složek na Disku) a dvě různé
    zakázky se stejným ID by byly v dokumentech nedohledatelné. Proto se řada
    posadí nad ně (viz `doporuceny_start`). Vedení to může přenastavit
    v nastavení CRM.
    """
    rok = _rok_dvojcisli()
    existujici = {
        r.entita: r for r in db.query(CiselnaRada).filter(CiselnaRada.rok == rok).all()
    }
    for entita in ENTITY_CRM:
        start = 1
        if entita == "op":
            nejvyssi = nejvyssi_raynet_cislo(db, rok)
            if nejvyssi is not None:
                start = doporuceny_start(nejvyssi)

        rada = existujici.get(entita)
        if rada is None:
            db.add(
                CiselnaRada(
                    entita=entita,
                    rok=rok,
                    prefix=PREFIXY[entita],
                    sirka=VYCHOZI_SIRKA,
                    dalsi_cislo=start,
                    pocatek=start,
                )
            )
            continue

        # Dorovnání existující řady, která ještě NIC nevydala. Bez tohohle by
        # řada založená dřív (než se do appky dostala Raynetí čísla) zůstala na
        # jedničce a první případ by dostal číslo, které v Raynetu už existuje.
        # Jakmile řada něco vydala, nedotýkáme se jí – čísla se nepřepisují.
        if int(rada.dalsi_cislo or 1) < start:
            rada.dalsi_cislo = start
            rada.pocatek = start
        elif int(rada.dalsi_cislo or 1) == start and int(rada.pocatek or 1) != start:
            # Řada už na doporučeném startu je, ale počátek se nestihl uložit
            # (posun proběhl dřív, než sloupec `pocatek` existoval). Srovnáme ho,
            # jinak by nastavení tvrdilo, že se vydaly stovky čísel.
            rada.pocatek = start
    db.commit()


def pocet_pouzitych(db: Session, entita: str, rok: int | None = None) -> int:
    """Kolik čísel už řada v daném roce vydala (pro nastavení – ať je vidět,
    jestli je bezpečné start řady ještě posouvat)."""
    rok = rok if rok is not None else _rok_dvojcisli()
    rada = (
        db.query(CiselnaRada)
        .filter(CiselnaRada.entita == entita, CiselnaRada.rok == rok)
        .first()
    )
    if rada is None:
        return 0
    return max(0, int(rada.dalsi_cislo or 1) - int(rada.pocatek or 1))


def aktualni_rok() -> int:
    """Dvojčíslí aktuálního roku – ať si ho nemusí skládat routes."""
    return _rok_dvojcisli()


def pocet_zaznamu_op(db: Session) -> int:
    """Kolik obchodních případů appka vede (pro rozcestník/dashboard)."""
    return int(db.query(func.count(ObchodniPripad.id)).scalar() or 0)
