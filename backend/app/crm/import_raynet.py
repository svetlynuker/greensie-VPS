"""Import klientů a obchodních případů z Raynetu do CRM.

Bez tohohle je CRM prázdná kostra: v Raynetu je ~450 firem a stovky případů
a nikdo je nebude přepisovat ručně. Import je **jednosměrný** (Raynet → appka)
a **idempotentní** – opakované spuštění existující záznamy aktualizuje, ne
zdvojí, protože se páruje na `raynet_id`.

CO SE MAPUJE (podle skutečných dat z API, ne z dokumentace):
  company.name          → nazev
  company.regNumber     → ico
  primaryAddress.address→ ulice, město, PSČ, **GPS** (lat/lng – potřebuje je PPA)
  primaryAddress.contactInfo → e-mail, telefon
  company.owner.fullName→ vlastník záznamu (mapuje se na uživatele appky podle jména)
  deal.code             → raynet_code (most na složky Disku – nesmí se zahodit)
  deal.name/description → název a popis případu
  deal.estimatedValue   → hodnota, deal.probability → pravděpodobnost
  deal.businessCasePhase→ stav (podle názvu; co se nenajde, padá do prvního)

CO SE NEMAPUJE A PROČ:
  * kategorie případu (PPA/prodej/peak shaving) – Raynetí fáze ji neobsahuje
    a hádat ji z názvu by vyrobilo tichý nepořádek. Zůstane prázdná a appka se
    zeptá při vytváření nabídky.
  * vlastní čísla appky – importovaný případ si nechává **Raynetí** číslo jako
    `raynet_code` a dostane své `cislo` z řady. Obojí vedle sebe je záměr, viz
    `crm/models.py`.
"""

import unicodedata
from datetime import datetime

from sqlalchemy.orm import Session

from app.auth.models import User
from app.crm import ciselne_rady, stavy as stavy_modul
from app.crm.models import CrmStavHistorie, ObchodniPripad, Zakaznik


def _text(x) -> str:
    return str(x).strip() if x is not None else ""


def _cislo(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _adresa(company: dict) -> dict:
    """Vytáhne adresu, kontakt a GPS z primární (nebo kontaktní) adresy."""
    pa = company.get("primaryAddress") or company.get("contactAddress") or {}
    adresa = (pa.get("address") or {}) if isinstance(pa, dict) else {}
    kontakt = (pa.get("contactInfo") or {}) if isinstance(pa, dict) else {}
    return {
        "adresa_ulice": _text(adresa.get("street")),
        "adresa_mesto": _text(adresa.get("city")),
        "adresa_psc": _text(adresa.get("zipCode")),
        "adresa_stat": _text(adresa.get("country")) or "Česko",
        # GPS z Raynetu je dárek: PPA výpočet ji potřebuje pro výrobu FVE.
        "gps_lat": _cislo(adresa.get("lat")),
        "gps_lng": _cislo(adresa.get("lng")),
        "email": _text(kontakt.get("email")),
        "telefon": _text(kontakt.get("tel1")) or _text(kontakt.get("tel2")),
    }


def _bez_diakritiky(s: str) -> str:
    """„Bártl" i „Bartl" musí dát stejný klíč – Raynet a appka píšou jména různě."""
    zaklad = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in zaklad if not unicodedata.combining(c)).strip().lower()


def mapa_uzivatelu(db: Session) -> tuple[dict[str, int], dict[str, int]]:
    """Dvě mapy pro párování vlastníka: podle celého jména a podle příjmení.

    Raynet posílá u vlastníka jen `fullName`, ne e-mail, takže se páruje podle
    jména – a reálně se neshoduje: appka má „Dan Lupínek", Raynet „Daniel
    Lupínek"; appka „Rostislav Bártl", Raynet „Rostislav Bartl". Proto se
    porovnává bez diakritiky a při neúspěchu podle **příjmení**, ale jen když je
    v appce jednoznačné. Dvakrát stejné příjmení = radši nikdo než špatně
    přiřazená zakázka.
    """
    cela: dict[str, int] = {}
    prijmeni_pocty: dict[str, list[int]] = {}
    for u in db.query(User).all():
        jmeno = (u.jmeno or "").strip()
        if not jmeno:
            continue
        cela[_bez_diakritiky(jmeno)] = u.id
        casti = jmeno.split()
        if casti:
            prijmeni_pocty.setdefault(_bez_diakritiky(casti[-1]), []).append(u.id)
    # Jen jednoznačná příjmení.
    prijmeni = {k: v[0] for k, v in prijmeni_pocty.items() if len(v) == 1}
    return cela, prijmeni


def _vlastnik(zdroj: dict, uzivatele: tuple[dict[str, int], dict[str, int]]) -> int | None:
    cela, prijmeni = uzivatele
    owner = zdroj.get("owner") or {}
    jmeno = _text(owner.get("fullName"))
    if not jmeno:
        return None
    klic = _bez_diakritiky(jmeno)
    if klic in cela:
        return cela[klic]
    casti = jmeno.split()
    if casti:
        return prijmeni.get(_bez_diakritiky(casti[-1]))
    return None


def _stav_pripadu(db: Session, deal: dict, mapa_stavu: dict[str, str], vychozi: str) -> str:
    """Raynetí fázi zkusí najít mezi našimi stavy podle názvu.

    Nehádá: co se nenajde, padne do prvního stavu a původní fáze se zapíše do
    popisu, aby se informace neztratila.
    """
    faze = deal.get("businessCasePhase") or {}
    nazev = _text(faze.get("value")).lower()
    return mapa_stavu.get(nazev, vychozi)


def importuj(
    db: Session,
    raynet,
    user: User,
    nasucho: bool = True,
    limit_firem: int | None = None,
) -> dict:
    """Natáhne firmy a obchodní případy z Raynetu.

    `nasucho=True` (výchozí) nic nezapisuje – jen spočítá, co by se stalo.
    Vrací souhrn s prvními položkami k nahlédnutí.
    """
    firmy = raynet.list_records("company", max_zaznamu=limit_firem)
    dealy = raynet.list_records("deal")

    uzivatele = mapa_uzivatelu(db)
    # Naše stavy podle NÁZVU, ať se dá Raynetí fáze napárovat, když se jmenuje stejně.
    stavy = stavy_modul.seznam(db, "op")
    mapa_stavu = {(s.nazev or "").strip().lower(): s.klic for s in stavy}
    vychozi_stav = stavy_modul.vychozi_klic(db, "op")

    # Existující záznamy podle Raynetího id – klíč idempotence.
    zak_podle_raynet = {
        z.raynet_id: z for z in db.query(Zakaznik).filter(Zakaznik.raynet_id.isnot(None)).all()
    }
    pripady_podle_raynet = {
        p.raynet_id: p
        for p in db.query(ObchodniPripad).filter(ObchodniPripad.raynet_id.isnot(None)).all()
    }
    # Dedup i podle IČO, aby import nezdvojil firmu založenou ručně.
    zak_podle_ico = {
        (z.ico or "").strip(): z for z in db.query(Zakaznik).all() if (z.ico or "").strip()
    }

    # Raynetí id firem, které po importu budou v appce existovat – u náhledu se
    # jinak jeví, že se nenaváže ani jeden případ (firmy se ještě nezaložily).
    firmy_po_importu: set[int] = set(zak_podle_raynet.keys())

    novych_firem = aktualizovanych_firem = 0
    novych_pripadu = aktualizovanych_pripadu = 0
    bez_zakaznika: list[str] = []
    ukazka_firem: list[dict] = []
    ukazka_pripadu: list[dict] = []

    # --- firmy ---
    for f in firmy:
        rid = f.get("id")
        nazev = _text(f.get("name"))
        if rid is None or not nazev:
            continue
        ico = _text(f.get("regNumber"))
        udaje = _adresa(f)
        existujici = zak_podle_raynet.get(int(rid)) or (zak_podle_ico.get(ico) if ico else None)

        if rid is not None:
            firmy_po_importu.add(int(rid))

        if existujici is None:
            novych_firem += 1
            if len(ukazka_firem) < 5:
                ukazka_firem.append({"nazev": nazev, "ico": ico, "mesto": udaje["adresa_mesto"],
                                     "novy": True})
            if not nasucho:
                z = Zakaznik(
                    typ="klient",  # v Raynetu jsou firmy, se kterými se obchoduje
                    nazev=nazev,
                    ico=ico,
                    dic=_text(f.get("taxNumber")),
                    adresa_ulice=udaje["adresa_ulice"],
                    adresa_mesto=udaje["adresa_mesto"],
                    adresa_psc=udaje["adresa_psc"],
                    adresa_stat=udaje["adresa_stat"],
                    gps_lat=udaje["gps_lat"],
                    gps_lng=udaje["gps_lng"],
                    email=udaje["email"],
                    telefon=udaje["telefon"],
                    poznamka=_text(f.get("notice")),
                    vlastnik_user_id=_vlastnik(f, uzivatele),
                    raynet_id=int(rid),
                    raynet_synchronizovano_at=datetime.now(),
                    vytvoril_user_id=user.id,
                )
                db.add(z)
                db.flush()
                zak_podle_raynet[int(rid)] = z
                if ico:
                    zak_podle_ico[ico] = z
        else:
            aktualizovanych_firem += 1
            if len(ukazka_firem) < 5:
                ukazka_firem.append({"nazev": nazev, "ico": ico, "mesto": udaje["adresa_mesto"],
                                     "novy": False})
            if not nasucho:
                # Doplňujeme jen to, co v appce chybí – ruční úpravy nepřepisujeme.
                z = existujici
                z.raynet_id = int(rid)
                z.raynet_synchronizovano_at = datetime.now()
                if not (z.ico or "").strip():
                    z.ico = ico
                for pole, hodnota in (
                    ("adresa_ulice", udaje["adresa_ulice"]),
                    ("adresa_mesto", udaje["adresa_mesto"]),
                    ("adresa_psc", udaje["adresa_psc"]),
                    ("email", udaje["email"]),
                    ("telefon", udaje["telefon"]),
                ):
                    if not (getattr(z, pole) or "").strip() and hodnota:
                        setattr(z, pole, hodnota)
                if z.gps_lat is None and udaje["gps_lat"] is not None:
                    z.gps_lat = udaje["gps_lat"]
                    z.gps_lng = udaje["gps_lng"]
                zak_podle_raynet[int(rid)] = z

    if not nasucho:
        db.flush()

    # --- obchodní případy ---
    for d in dealy:
        rid = d.get("id")
        if rid is None:
            continue
        firma = d.get("company") or {}
        firma_id = firma.get("id")
        zakaznik = zak_podle_raynet.get(int(firma_id)) if firma_id is not None else None
        kod = _text(d.get("code"))

        # U náhledu ještě zákazník neexistuje, ale bude – ať náhled neříká, že se
        # nenaimportuje nic.
        if nasucho and zakaznik is None and firma_id is not None:
            if int(firma_id) in firmy_po_importu:
                novych_pripadu += 1
                if len(ukazka_pripadu) < 5:
                    ukazka_pripadu.append(
                        {"kod": kod, "nazev": _text(d.get("name"))[:60],
                         "zakaznik": _text(firma.get("name")),
                         "faze": _text((d.get("businessCasePhase") or {}).get("value")),
                         "hodnota": _cislo(d.get("estimatedValue"))}
                    )
                continue

        if zakaznik is None:
            # Případ bez firmy v appce nemá kam patřit (u nasucho je to běžné,
            # protože firmy se ještě nezaložily).
            bez_zakaznika.append(kod or f"#{rid}")
            continue

        existujici = pripady_podle_raynet.get(int(rid))
        faze = _text((d.get("businessCasePhase") or {}).get("value"))

        if existujici is None:
            novych_pripadu += 1
            if len(ukazka_pripadu) < 5:
                ukazka_pripadu.append(
                    {"kod": kod, "nazev": _text(d.get("name"))[:60],
                     "zakaznik": zakaznik.nazev if not nasucho else firma.get("name"),
                     "faze": faze, "hodnota": _cislo(d.get("estimatedValue"))}
                )
            if not nasucho:
                popis = _text(d.get("description"))
                if faze:
                    # Původní fáze se nesmí ztratit – naše stavy se s Raynetími
                    # nemusí jmenovat stejně.
                    popis = (popis + "\n\n" if popis else "") + f"Raynetí fáze při importu: {faze}"
                stav = _stav_pripadu(db, d, mapa_stavu, vychozi_stav)
                p = ObchodniPripad(
                    cislo=ciselne_rady.dalsi_cislo(db, "op"),
                    zakaznik_id=zakaznik.id,
                    nazev=_text(d.get("name")),
                    popis=popis,
                    kategorie=[],  # Raynet ji nezná – appka se zeptá u nabídky
                    stav=stav,
                    hodnota_kc=_cislo(d.get("estimatedValue")),
                    pravdepodobnost=(
                        int(d["probability"]) if isinstance(d.get("probability"), (int, float)) else None
                    ),
                    duvod_prohry=_text((d.get("losingReason") or {}).get("value"))
                    if isinstance(d.get("losingReason"), dict)
                    else _text(d.get("losingReason")),
                    vlastnik_user_id=_vlastnik(d, uzivatele) or zakaznik.vlastnik_user_id,
                    raynet_id=int(rid),
                    raynet_code=kod.upper(),
                    vytvoril_user_id=user.id,
                )
                db.add(p)
                db.flush()
                db.add(
                    CrmStavHistorie(
                        entita="op", zaznam_id=p.id, ze_stavu=None,
                        do_stavu=stav, zmenil_user_id=user.id,
                    )
                )
                pripady_podle_raynet[int(rid)] = p
        else:
            aktualizovanych_pripadu += 1
            if not nasucho:
                p = existujici
                # Raynetí kód je most na složky Disku – doplníme, když chybí,
                # ale nikdy nepřepisujeme na prázdno.
                if kod and not (p.raynet_code or "").strip():
                    p.raynet_code = kod.upper()
                if p.hodnota_kc is None:
                    p.hodnota_kc = _cislo(d.get("estimatedValue"))

    if not nasucho:
        db.commit()

    return {
        "nasucho": nasucho,
        "firem_v_raynetu": len(firmy),
        "pripadu_v_raynetu": len(dealy),
        "firem_novych": novych_firem,
        "firem_aktualizovanych": aktualizovanych_firem,
        "pripadu_novych": novych_pripadu,
        "pripadu_aktualizovanych": aktualizovanych_pripadu,
        # U náhledu je tohle číslo vždy vysoké: firmy se ještě nezaložily, takže
        # se případy nemají na co navázat. Po skutečném importu má být nulové.
        "pripadu_bez_zakaznika": len(bez_zakaznika),
        "ukazka_firem": ukazka_firem,
        "ukazka_pripadu": ukazka_pripadu,
        # Koho se nepodařilo napárovat na uživatele appky – jeho záznamy zůstanou
        # bez vlastníka, tedy viditelné jen s právem `crm_vse`.
        "nenamapovani_vlastnici": sorted(
            {
                _text((x.get("owner") or {}).get("fullName"))
                for x in firmy + dealy
                if _text((x.get("owner") or {}).get("fullName"))
                and _vlastnik(x, uzivatele) is None
            }
        ),
    }
