"""API modulu „Disk" – `/disk/*` (procházení firemního Google Disku).

Vlastní router s vlastním prefixem, ne přílepek do `konektor/routes.py`: ten je
celý pod právem `konektor` (nastavení konektoru, tajemství, logy), což je věc pro
správce. Procházení Disku je naopak běžná denní práce a jede pod svým právem
`disk`. Kdyby to viselo na témže routeru, buď by se to zamklo správcům, nebo by
se muselo u každého endpointu hlídat, které právo platí — a to je přesně místo,
kde se jednou omylem povolí víc.

Vlastní prefix `/disk` navíc znamená, že to nemůže kolidovat s ničím existujícím
(past, na kterou už appka jednou naletěla – viz `tests/test_kolize_cest.py`).

Odpovědi jsou obyčejné slovníky, ne pydantic schémata: je to čtení průzkumníka,
tvar drží jedno místo (`disk_prochazeni`) a nová třída `*Out` by byla další
kandidát na kolizi názvů.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.crm.novinky import ma_novinky
from app.database import get_db
from app.konektor import disk_prochazeni
from app.konektor.logika import NastaveniNepripraveno

router = APIRouter(prefix="/disk", tags=["disk"])


def vyzaduj_disk(user: User = Depends(get_current_user)) -> User:
    """Právo `disk` + přepínač novinek (modul se zatím zkouší interně).

    404 místo 403 stejně jako v `novinky.py`: kdo funkci nemá vidět, pro toho
    neexistuje.
    """
    if not ma_novinky(user) or not muze_otevrit(user, "disk"):
        raise HTTPException(status_code=404, detail="Nenalezeno")
    return user


def _osetri(volani, hlaska_502: str = "Disk neodpověděl"):
    """Překlad chyb Disku na HTTP. Konkrétní hláška, ne tiché prázdno.

    Prázdný seznam by člověk čekal na Disku a hledal by, kdo mu smazal složky —
    proto se nenastavený konektor i mlčící Google hlásí jako chyba. `hlaska_502`
    se liší podle akce: „nepřijal soubor" a „neodpověděl" vedou k jinému
    hledání příčiny.
    """
    try:
        return volani()
    except NastaveniNepripraveno as e:
        raise HTTPException(status_code=409, detail=f"Konektor na Disk není připravený: {e}")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:  # noqa: BLE001 – chybu chceme ukázat čitelně
        raise HTTPException(status_code=502, detail=f"{hlaska_502}: {e}")


@router.get("/koren")
def koren(
    _user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Kořenová složka nastavená v konektoru – odkud modul začíná."""
    return _osetri(lambda: disk_prochazeni.koren(db))


@router.get("/obsah")
def obsah(
    folder_id: str | None = Query(default=None, description="Složka; prázdné = výchozí složka"),
    _user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Obsah složky + cesta ke stropu. Každá úroveň nese odkaz na Disk.

    `folder_id` je z prohlížeče, takže se ověřuje, že složka leží pod stropem
    modulu — viz hlavička `disk_prochazeni`.
    """
    return _osetri(lambda: disk_prochazeni.obsah(db, folder_id))


@router.post("/soubor")
async def nahraj_soubor(
    soubor: UploadFile = File(...),
    folder_id: str | None = Form(default=None),
    user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Nahraje soubor na Disk do právě otevřené složky.

    Soubor se u nás NEUKLÁDÁ ani po cestě — projde do Disku a v appce zůstane
    jen odkaz. Cílová složka se ověřuje stejně jako u čtení, jinak by se přes
    appku dalo zapisovat kamkoli na Disk.
    """
    data = await soubor.read()
    if not data:
        raise HTTPException(status_code=422, detail="Soubor je prázdný.")
    if len(data) > disk_prochazeni.MAX_SOUBOR_B:
        raise HTTPException(
            status_code=413,
            detail="Soubor je větší než 25 MB — nahraj ho prosím přímo na Disk.",
        )
    return _osetri(
        lambda: disk_prochazeni.nahraj(
            db,
            folder_id,
            soubor.filename or "soubor",
            data,
            soubor.content_type or "",
            user.email,
        ),
        "Disk soubor nepřijal",
    )
