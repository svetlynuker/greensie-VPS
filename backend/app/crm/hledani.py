"""Globální hledání napříč CRM (CRM-24).

Jedno pole, které najde zákazníka, případ, nabídku, objednávku i projekt. Dnes
se hledá v každé sekci zvlášť, takže „kde je ten klient z Berouna" znamená
proklikat pět obrazovek.

Prohledávaná pole podle zadání Dana: názvy a čísla záznamů + IČO, telefon,
e-mail a město zákazníka. Text aktivit a poznámek NE — Dan ho nevybral, a je to
dobře: výsledků by bylo mnoho a hledání by zpomalilo.

---- Dvě věci, které rozhodují o tom, jestli je hledání použitelné ---------

1. **Viditelnost.** Každá entita jde přes `omez_na_moje`, takže OZ nenajde cizí
   zakázku. Bez toho by hledání bylo obchvat práv — nejjednodušší způsob, jak se
   dozvědět, na čem pracují ostatní.
2. **Diakritika a velikost písmen.** Lidé hledají „kovarna" i „Kovárna" a nikdo
   nebude přepínat klávesnici. `ILIKE` řeší jen velikost písmen, proto se
   porovnává i podoba BEZ diakritiky — přes `translate()` v SQL, aby to nezáviselo
   na rozšíření `unaccent`, které na serveru nemusí být nainstalované.
"""

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm.models import CrmProjekt, ObchodniPripad, Objednavka, Zakaznik
from app.crm.pristup import muze_vse, omez_na_moje

# Kolik výsledků na jednu sekci. Víc než pět v rozbalovací nabídce nikdo nečte;
# kdo hledá dávku, použije filtr v seznamu.
LIMIT_SEKCE = 5


# Mapa pro odstranění diakritiky. Musí být stejná na obou stranách porovnání:
# v SQL přes translate() a v Pythonu na hledaném výrazu.
_S_DIA = "áčďéěíňóřšťúůýžÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ"
_BEZ_DIA = "acdeeinorstuuyzACDEEINORSTUUYZ"
_PREKLAD = str.maketrans(_S_DIA, _BEZ_DIA)


def _vzor(dotaz: str) -> str:
    return f"%{(dotaz or '').strip()}%"


def _vzor_bez_dia(dotaz: str) -> str:
    return f"%{(dotaz or '').strip().translate(_PREKLAD)}%"


def _shoda(sloupec, v: str, v_bez: str):
    """Sloupec obsahuje hledaný text — se diakritikou i bez ní.

    Bez druhé podmínky by „kovarna" nenašlo „Kovárna", což je přesně to, jak
    lidé hledají.
    """
    return or_(
        sloupec.ilike(v),
        func.translate(sloupec, _S_DIA, _BEZ_DIA).ilike(v_bez),
    )


def hledej(db: Session, user: User, dotaz: str) -> dict:
    """Výsledky po sekcích. Prázdný nebo příliš krátký dotaz nic nevrací.

    Jeden znak by vrátil skoro všechno a jen zdržel — od dvou znaků to začíná
    mít smysl.
    """
    q = (dotaz or "").strip()
    if len(q) < 2:
        return {"dotaz": q, "sekce": []}
    v = _vzor(q)
    vb = _vzor_bez_dia(q)
    sekce = []

    # --- zákazníci: název, IČO, telefon, e-mail, město ---
    zak = (
        omez_na_moje(db.query(Zakaznik), Zakaznik, user)
        .filter(
            or_(
                _shoda(Zakaznik.nazev, v, vb),
                Zakaznik.ico.ilike(v),
                Zakaznik.telefon.ilike(v),
                Zakaznik.email.ilike(v),
                _shoda(Zakaznik.adresa_mesto, v, vb),
            )
        )
        .order_by(Zakaznik.nazev)
        .limit(LIMIT_SEKCE + 1)
        .all()
    )
    if zak:
        sekce.append(
            {
                "klic": "zakaznik",
                "nazev": "Zákazníci",
                "vysledky": [
                    {
                        "id": z.id,
                        "titulek": z.nazev,
                        "popis": ", ".join(
                            x for x in [z.ico, z.adresa_mesto, z.telefon] if x
                        ),
                        "cesta": f"/zakaznici/detail/{z.id}",
                    }
                    for z in zak[:LIMIT_SEKCE]
                ],
                "vic": len(zak) > LIMIT_SEKCE,
            }
        )

    # --- obchodní případy: číslo a název ---
    pripady = (
        omez_na_moje(db.query(ObchodniPripad), ObchodniPripad, user)
        .filter(
            or_(
                ObchodniPripad.cislo.ilike(v),
                _shoda(ObchodniPripad.nazev, v, vb),
            )
        )
        .order_by(ObchodniPripad.cislo.desc())
        .limit(LIMIT_SEKCE + 1)
        .all()
    )
    if pripady:
        sekce.append(
            {
                "klic": "op",
                "nazev": "Obchodní případy",
                "vysledky": [
                    {
                        "id": p.id,
                        "titulek": f"{p.cislo} · {p.nazev}" if p.nazev else p.cislo,
                        "popis": p.stav or "",
                        "cesta": f"/pripady/detail/{p.id}",
                    }
                    for p in pripady[:LIMIT_SEKCE]
                ],
                "vic": len(pripady) > LIMIT_SEKCE,
            }
        )

    # --- nabídky: číslo a zákazník. Nemají vlastníka, práva se odvozují od
    #     případu; nabídka bez případu je vidět jen s `crm_vse`. ---
    from app.nabidkovac.models import Nabidka

    nab_q = (
        db.query(Nabidka, ObchodniPripad)
        .outerjoin(ObchodniPripad, Nabidka.obchodni_pripad_id == ObchodniPripad.id)
        .filter(
            or_(
                cast(Nabidka.cislo, String).ilike(v),
                _shoda(Nabidka.zakaznik_nazev, v, vb),
            )
        )
        .order_by(Nabidka.id.desc())
        .limit(30)
        .all()
    )
    nabidky = []
    for n, p in nab_q:
        if p is None:
            if not muze_vse(user):
                continue
        elif not (
            muze_vse(user)
            or p.vlastnik_user_id == user.id
            or user.id in list(p.spoluvlastnici or [])
        ):
            continue
        nabidky.append(
            {
                "id": n.id,
                "titulek": f"{n.cislo or f'#{n.id}'} · {n.zakaznik_nazev or ''}".strip(" ·"),
                "popis": p.cislo if p else "bez případu",
                "cesta": f"/nabidkovac/nabidka/{n.id}",
            }
        )
        if len(nabidky) > LIMIT_SEKCE:
            break
    if nabidky:
        sekce.append(
            {
                "klic": "nab",
                "nazev": "Nabídky",
                "vysledky": nabidky[:LIMIT_SEKCE],
                "vic": len(nabidky) > LIMIT_SEKCE,
            }
        )

    # --- objednávky a projekty: číslo a název, práva od případu ---
    for model, klic, nazev_sekce, cesta in (
        (Objednavka, "obj", "Objednávky", "/objednavky"),
        (CrmProjekt, "pro", "Projekty", "/projekty/detail/{id}"),
    ):
        radky = (
            db.query(model, ObchodniPripad)
            .join(ObchodniPripad, model.obchodni_pripad_id == ObchodniPripad.id)
            .filter(or_(model.cislo.ilike(v), _shoda(model.nazev, v, vb)))
            .order_by(model.cislo.desc())
            .limit(30)
            .all()
        )
        out = []
        for r, p in radky:
            if not (
                muze_vse(user)
                or p.vlastnik_user_id == user.id
                or user.id in list(p.spoluvlastnici or [])
            ):
                continue
            out.append(
                {
                    "id": r.id,
                    "titulek": f"{r.cislo} · {r.nazev}" if r.nazev else r.cislo,
                    "popis": p.cislo,
                    "cesta": cesta.format(id=r.id) if "{id}" in cesta else cesta,
                }
            )
            if len(out) > LIMIT_SEKCE:
                break
        if out:
            sekce.append(
                {
                    "klic": klic,
                    "nazev": nazev_sekce,
                    "vysledky": out[:LIMIT_SEKCE],
                    "vic": len(out) > LIMIT_SEKCE,
                }
            )

    return {
        "dotaz": q,
        "sekce": sekce,
        "celkem": sum(len(s["vysledky"]) for s in sekce),
    }
