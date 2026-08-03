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

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.permissions import get_current_user, muze_otevrit
from app.database import get_db
from app.konektor import disk_prochazeni
from app.konektor.logika import NastaveniNepripraveno

router = APIRouter(prefix="/disk", tags=["disk"])


class DiskPravoVstup(BaseModel):
    """Komu a s jakou rolí se má položka na Disku sdílet."""

    item_id: str
    email: str
    role: str = "reader"
    # Zapnuto schválně: adresy bez účtu Google (u nás většina `@greensie.cz`)
    # Google bez pozvánky odmítne přidat vůbec — viz `disk_prochazeni.pridej_pravo`.
    oznamit: bool = True


class DiskSlozkaVstup(BaseModel):
    """Nová podsložka. `folder_id` prázdné = výchozí složka modulu.

    Vlastní název třídy s předponou `Disk` schválně – v projektu už `SlozkaOut`
    existuje pro e-mailové složky a stejná jména se tiše přepisují
    (viz `tests/test_kolize_cest.py`).
    """

    nazev: str
    folder_id: str | None = None


def vyzaduj_disk(user: User = Depends(get_current_user)) -> User:
    """Právo `disk` – nic víc.

    403 a ne 404, ze stejného důvodu jako u sdílení níž: modul existuje a kdo
    ho nemá, má vědět, o co požádat. Dřív tu byla ještě druhá branka
    („přepínač novinek"), takže přidělené právo samo nic neotevřelo.
    """
    if not muze_otevrit(user, "disk"):
        raise HTTPException(
            status_code=403,
            detail="Na Disk nemáš oprávnění.",
        )
    return user


def vyzaduj_sdileni(user: User = Depends(vyzaduj_disk)) -> User:
    """Právo `disk_sdileni` na měnění sdílení.

    Tady 403 a ne 404: modul člověk vidí (dostal se přes `vyzaduj_disk`), takže
    „neexistuje" by byla lež — a hláška „na tohle nemáš právo" mu řekne, o co
    má požádat.
    """
    if not muze_otevrit(user, "disk_sdileni"):
        raise HTTPException(
            status_code=403,
            detail="Na měnění sdílení na Disku nemáš oprávnění.",
        )
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
    except ValueError as e:
        # Vstup, se kterým se nedá pracovat (prázdný název, složka místo souboru,
        # příliš velký soubor) – to není chyba Disku, ale zadání.
        raise HTTPException(status_code=422, detail=str(e))
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


@router.post("/slozka")
def zaloz_slozku(
    vstup: DiskSlozkaVstup,
    user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Založí podsložku v právě otevřené složce."""
    return _osetri(
        lambda: disk_prochazeni.zaloz_slozku(db, vstup.folder_id, vstup.nazev, user.email),
        "Disk složku nezaložil",
    )


@router.get("/prava")
def prava(
    item_id: str = Query(..., description="Složka nebo soubor"),
    user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Kdo má k položce přístup na Disku.

    Čtení stačí právo `disk` — vědět, komu už je dokument dostupný, potřebuje
    každý, kdo ho má komu poslat. `smim_menit` říká prohlížeči, jestli má vůbec
    ukazovat tlačítka (rozhoduje ale server u každé změny znovu).
    """
    vysledek = _osetri(lambda: disk_prochazeni.prava(db, item_id))
    vysledek["smim_menit"] = muze_otevrit(user, "disk_sdileni")
    return vysledek


@router.post("/prava")
def pridej_pravo(
    vstup: DiskPravoVstup,
    user: User = Depends(vyzaduj_sdileni),
    db: Session = Depends(get_db),
):
    """Nasdílí položku konkrétnímu člověku. Žádné „kdokoli s odkazem"."""
    return _osetri(
        lambda: disk_prochazeni.pridej_pravo(
            db, vstup.item_id, vstup.email, vstup.role, vstup.oznamit, user.email
        ),
        "Disk sdílení nepřijal",
    )


@router.delete("/prava/{permission_id}")
def odeber_pravo(
    permission_id: str,
    item_id: str = Query(..., description="Složka nebo soubor, u které se právo ruší"),
    user: User = Depends(vyzaduj_sdileni),
    db: Session = Depends(get_db),
):
    """Odebere člověku přístup k položce."""
    return _osetri(
        lambda: disk_prochazeni.odeber_pravo(db, item_id, permission_id, user.email),
        "Disk sdílení nezrušil",
    )


@router.get("/soubor/{file_id}/nahled")
def nahled_souboru(
    file_id: str,
    _user: User = Depends(vyzaduj_disk),
    db: Session = Depends(get_db),
):
    """Obsah souboru k zobrazení **v appce**, ne přesměrováním na Disk.

    Čte se přes service account konektoru, takže na tom, jestli má člověk vlastní
    přístup ke Google Disku, nezáleží. Google dokumenty přijdou jako PDF.

    `Content-Disposition: inline` — prohlížeč to má zobrazit, ne stáhnout. Název
    se posílá i v `filename*` (RFC 5987), jinak by se české znaky v názvu
    rozsypaly.
    """
    data, mime, nazev = _osetri(lambda: disk_prochazeni.nahled(db, file_id))
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(nazev)}",
            # Nechceme, aby náhled zůstal v cache prohlížeče: soubor na Disku se
            # může kdykoli změnit a stará podoba by pak tvrdila, že je platná.
            "Cache-Control": "no-store",
        },
    )
