"""Synchronizace schránky se serverem – co se kdy stahuje a co se zapisuje zpět.

Nad `email_imap.py` (jak se mluví se serverem) a pod `email_routes.py` (co si
řekne obrazovka). Tady je jediné místo, které rozhoduje, co je v DB.

---- Proč se pošta ukládá do DB a nečte naživo -------------------------------
Jeden FETCH hlaviček pár set zpráv trvá sekundy a nové spojení k Seznamu půl
sekundy. Kdyby se seznam pošty stavěl při každém otevření obrazovky, appka by
byla nepoužitelná a Seznam by nás začal omezovat. V DB jsou proto hlavičky
a náhled; **těla se dotahují až při otevření zprávy** a pak zůstanou.

---- Tři věci, které tenhle modul dělá --------------------------------------
1. `synchronizuj_slozky` – seznam složek (přidané, přejmenované, zmizelé).
2. `synchronizuj_slozku` – nové zprávy + **obnova příznaků** u okna posledních
   zpráv. Druhá část je „živá kontrola přečtení": co si člověk přečte
   v mobilu, zmizí i v appce, protože se `\\Seen` čte znovu.
3. `nastav_precteno` / `presun_zpravu` – zápis **zpátky na server**. Tohle je
   podmínka, aby appka nebyla jen prohlížeč: co se udělá tady, musí být vidět
   i na webu Seznamu, jinak si člověk vede dvě různé schránky.

---- UIDVALIDITY -----------------------------------------------------------
`uidvalidity` je pojistka serveru: když se změní, **všechna UID přestala platit**
a cache složky se musí zahodit. Bez téhle kontroly by se po přeindexování
schránky začaly zprávy míchat mezi sebou – tichá a nedohledatelná chyba.

---- Co tenhle modul NEDĚLÁ ------------------------------------------------
Nemaže poštu na serveru (přesun do Koše ano, `EXPUNGE` ne) a nikdy nestahuje
zprávu tak, aby ji tím označil přečtenou (všude `BODY.PEEK`).
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crypto
from app.crm import adresar, email_pool
from app.crm.email_imap import (
    DELKA_VYPISU,
    PORADI_DRUHU,
    ImapChyba,
    ImapSpojeni,
    vypis_z_tela,
)
from app.crm.models import (
    CrmEmailPriloha,
    CrmEmailSlozka,
    CrmEmailUcet,
    CrmEmailZprava,
)

# Kolik posledních zpráv ve složce se kontroluje na změnu příznaků. Celá složka
# by znamenala FETCH nad desítkami tisíc UID při každém cyklu; okno pokrývá to,
# co člověk reálně čte, a drží jeden cyklus v desetinách sekundy.
OKNO_PRIZNAKU = 400
# Strop na jeden průběh jedné složky. Zbytek se dobere v dalším cyklu, takže
# první synchronizace velké schránky nezablokuje worker na hodinu.
MAX_NOVYCH_ZA_CYKLUS = 200
# Složky, které se ve výchozím stavu nestahují (nejvíc dat, nejméně čtení).
DRUHY_BEZ_SYNC = {"spam", "kos"}


def _ted() -> datetime:
    return datetime.now(timezone.utc)


def heslo_uctu(ucet: CrmEmailUcet) -> str:
    """Dešifrované heslo schránky. Prázdno = potřebuje znovu zadat."""
    return crypto.desifruj(ucet.heslo_sifra or "")


def spojeni(ucet: CrmEmailUcet) -> ImapSpojeni:
    """**Vlastní** IMAP spojení pro daný účet – pro dlouhou synchronizaci.

    Plná synchronizace běží desítky sekund ve workeru; kdyby si brala spojení
    z půjčovny, držela by celou tu dobu zámek a člověk klikající v appce by
    čekal. Interaktivní operace proto používají `email_pool.pujc` (viz níž).
    """
    heslo = heslo_uctu(ucet)
    if not heslo:
        raise ImapChyba(
            "Ke schránce není uložené heslo (nebo se nepodařilo rozšifrovat). "
            "Zadej ho znovu v nastavení e-mailu."
        )
    return ImapSpojeni(ucet.imap_host, ucet.imap_port, ucet.adresa, heslo)


def pujcene(ucet: CrmEmailUcet):
    """Sdílené spojení z půjčovny – pro krátké operace vyvolané klikem.

    Otevření zprávy, odškrtnutí přečteno nebo přesun do složky se musí stihnout
    hned. Nové přihlášení k Seznamu trvá až sekundu a půl, takže se spojení
    drží otevřené a půjčuje (viz `email_pool`).
    """
    return email_pool.pujc(ucet, heslo_uctu(ucet))


# ---- vlákna ------------------------------------------------------------------
_RE_ODPOVED = re.compile(r"^\s*((re|odp|fwd|fw|pr|předat|preposlat)\s*(\[\d+\])?\s*:\s*)+", re.I)


def vlakno_klic(predmet: str) -> str:
    """Klíč vlákna z předmětu – `Re: Fwd: Nabídka` a `Nabídka` patří k sobě.

    Přesné vláknování podle `References` by bylo lepší, ale Seznam ani část
    klientů hlavičku spolehlivě neposílá. Normalizovaný předmět je hrubší, zato
    funguje vždy; horší případ je, že se sloučí dvě různé zprávy stejného jména.
    """
    bez_prefixu = _RE_ODPOVED.sub("", predmet or "")
    return " ".join(bez_prefixu.split()).lower()[:200]


# ---- složky ------------------------------------------------------------------
def synchronizuj_slozky(db: Session, s: ImapSpojeni, ucet: CrmEmailUcet) -> dict:
    """Srovná seznam složek v DB s tím, co je na serveru.

    Zmizelé složky se **mažou i s nacachovanými zprávami**: složka, která na
    serveru není, by v appce byla mrtvý sloupec, do kterého nejde nic přesunout.
    """
    na_serveru = s.slozky()
    podle_nazvu = {x["imap_nazev"]: x for x in na_serveru}

    v_db = {x.imap_nazev: x for x in db.query(CrmEmailSlozka).filter_by(ucet_id=ucet.id).all()}
    pridano, upraveno, smazano = 0, 0, 0

    for imap_nazev, data in podle_nazvu.items():
        poradi = PORADI_DRUHU.index(data["druh"]) if data["druh"] in PORADI_DRUHU else 99
        slozka = v_db.get(imap_nazev)
        if slozka is None:
            db.add(
                CrmEmailSlozka(
                    ucet_id=ucet.id,
                    imap_nazev=imap_nazev,
                    nazev=data["nazev"],
                    druh=data["druh"],
                    oddelovac=data["oddelovac"],
                    poradi=poradi,
                    sync_zapnuto=data["druh"] not in DRUHY_BEZ_SYNC,
                )
            )
            pridano += 1
            continue
        # Název i druh se mohou na serveru změnit (přejmenování složky).
        if (slozka.nazev, slozka.druh, slozka.poradi) != (data["nazev"], data["druh"], poradi):
            slozka.nazev = data["nazev"]
            slozka.druh = data["druh"]
            slozka.poradi = poradi
            upraveno += 1

    for imap_nazev, slozka in v_db.items():
        if imap_nazev not in podle_nazvu:
            db.delete(slozka)
            smazano += 1

    db.commit()
    return {"pridano": pridano, "upraveno": upraveno, "smazano": smazano}


# ---- zprávy ------------------------------------------------------------------
def synchronizuj_slozku(db: Session, s: ImapSpojeni, slozka: CrmEmailSlozka) -> dict:
    """Stáhne nové zprávy a obnoví příznaky u okna posledních.

    Vrací počty pro log: `{nove, zmenene, smazane}`.
    """
    stav = s.vyber(slozka.imap_nazev)
    uidvalidity = stav["uidvalidity"]

    # UIDVALIDITY se změnila → UID nic neznamenají, cache je k zahození.
    if uidvalidity and slozka.uidvalidity and uidvalidity != slozka.uidvalidity:
        db.query(CrmEmailZprava).filter_by(slozka_id=slozka.id).delete(synchronize_session=False)
        slozka.posledni_uid = 0
        db.commit()
    if uidvalidity:
        slozka.uidvalidity = uidvalidity

    prvni_beh = slozka.posledni_uid == 0
    if prvni_beh:
        # První připojení: jen posledních N zpráv. Bez stropu by se tahalo
        # patnáct let newsletterů a člověk by na schránku čekal do večera.
        vsechna = s.uidy("ALL")
        strop = max(1, int(slozka.ucet.prvni_sync_pocet or 300))
        nove_uidy = vsechna[-strop:]
    else:
        nove_uidy = s.uidy_nad(slozka.posledni_uid)

    # Strop na cyklus – zbytek se dobere příště (od nejstarší nestažené).
    utnuto = False
    if len(nove_uidy) > MAX_NOVYCH_ZA_CYKLUS:
        nove_uidy = nove_uidy[:MAX_NOVYCH_ZA_CYKLUS]
        utnuto = True

    nove = _uloz_hlavicky(db, s, slozka, nove_uidy)
    zmenene = _obnov_priznaky(db, s, slozka)
    smazane = _uklid_smazane(db, s, slozka)

    slozka.celkem = stav["pocet"]
    slozka.nepreectenych = (
        db.query(func.count(CrmEmailZprava.id))
        .filter(CrmEmailZprava.slozka_id == slozka.id, CrmEmailZprava.precteno.is_(False))
        .scalar()
        or 0
    )
    slozka.posledni_sync_at = _ted()
    db.commit()
    return {"nove": nove, "zmenene": zmenene, "smazane": smazane, "utnuto": utnuto}


def _uloz_hlavicky(db: Session, s: ImapSpojeni, slozka: CrmEmailSlozka, uidy: list[int]) -> int:
    """Stáhne hlavičky daných UID a zapíše je jako zprávy."""
    if not uidy:
        return 0
    # Co už v DB je, znovu netaháme (může se stát po utnutém cyklu).
    mame = {
        u for (u,) in db.query(CrmEmailZprava.uid).filter(
            CrmEmailZprava.slozka_id == slozka.id, CrmEmailZprava.uid.in_(uidy)
        )
    }
    ke_stazeni = [u for u in uidy if u not in mame]
    if not ke_stazeni:
        slozka.posledni_uid = max(slozka.posledni_uid, max(uidy))
        return 0

    odchozi = slozka.druh in {"odeslane", "koncepty"}
    # POJISTKA PROTI LAVINĚ: zprávy stažené při PRVNÍM připojení schránky jsou
    # historie, ne nová pošta. Kdyby na ně automatika (OOO, přeposílání) mohla
    # sáhnout, zapnutí schránky by rozeslalo tři sta odpovědí na měsíce starou
    # poštu. Označíme je proto rovnou jako zpracované.
    prvni_stazeni = slozka.posledni_uid == 0
    ted = _ted()
    pocet = 0
    for hlavicka in s.hlavicky(ke_stazeni):
        priznaky = {p.lower() for p in hlavicka.get("priznaky", [])}
        # Adresa, podle které se hledá zákazník: u odeslané pošty je to
        # příjemce, u příchozí odesílatel. Jinak by se odeslaná pošta párovala
        # na vlastní firmu.
        klicova_adresa = hlavicka["od_adresa"]
        if odchozi and hlavicka["komu"]:
            klicova_adresa = hlavicka["komu"][0]["adresa"]
        vazba = adresar.dohledaj_podle_adresy(db, klicova_adresa)

        db.add(
            CrmEmailZprava(
                ucet_id=slozka.ucet_id,
                slozka_id=slozka.id,
                uid=hlavicka["uid"],
                message_id=hlavicka["message_id"][:998],
                in_reply_to=hlavicka["in_reply_to"][:998],
                vlakno_klic=vlakno_klic(hlavicka["predmet"]),
                od_jmeno=hlavicka["od_jmeno"][:255],
                od_adresa=hlavicka["od_adresa"][:255],
                komu=hlavicka["komu"],
                kopie=hlavicka["kopie"],
                odpovedet_na=hlavicka["odpovedet_na"][:255],
                predmet=hlavicka["predmet"][:998],
                datum_at=hlavicka["datum_at"],
                smer="odchozi" if odchozi else "prichozi",
                precteno="\\seen" in priznaky,
                oznaceno="\\flagged" in priznaky,
                zodpovezeno="\\answered" in priznaky,
                koncept="\\draft" in priznaky or slozka.druh == "koncepty",
                automat=hlavicka["automat"],
                velikost=hlavicka.get("velikost") or 0,
                zakaznik_id=vazba["zakaznik_id"],
                pripad_id=vazba["pripad_id"],
                # Historii a odchozí poštu automatika neřeší (viz výš).
                zpracovano_at=ted if (prvni_stazeni or odchozi) else None,
            )
        )
        pocet += 1

    slozka.posledni_uid = max(slozka.posledni_uid, max(uidy))
    db.commit()

    # Napojení na CRM až po commitu – vazby potřebují id zpráv. Chyba tady
    # nesmí shodit stahování: pošta je stažená, jen se nepropojí.
    try:
        for z in (
            db.query(CrmEmailZprava)
            .filter(CrmEmailZprava.slozka_id == slozka.id, CrmEmailZprava.uid.in_(ke_stazeni))
            .all()
        ):
            zaloz_vazby(db, z, komitni=False)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return pocet


def _obnov_priznaky(db: Session, s: ImapSpojeni, slozka: CrmEmailSlozka) -> int:
    """Živá kontrola přečtení – přečte `\\Seen`/`\\Flagged` u okna posledních zpráv.

    Tohle je důvod, proč appka neukazuje jinou realitu než mobil: příznaky se
    čtou znovu, ne jen při prvním stažení.
    """
    zpravy = (
        db.query(CrmEmailZprava)
        .filter(CrmEmailZprava.slozka_id == slozka.id)
        .order_by(CrmEmailZprava.uid.desc())
        .limit(OKNO_PRIZNAKU)
        .all()
    )
    if not zpravy:
        return 0
    na_serveru = s.priznaky([z.uid for z in zpravy])
    zmeneno = 0
    for z in zpravy:
        priznaky = na_serveru.get(z.uid)
        if priznaky is None:
            continue  # zpráva zmizela – řeší `_uklid_smazane`
        male = {p.lower() for p in priznaky}
        precteno = "\\seen" in male
        oznaceno = "\\flagged" in male
        zodpovezeno = "\\answered" in male
        if (z.precteno, z.oznaceno, z.zodpovezeno) != (precteno, oznaceno, zodpovezeno):
            z.precteno, z.oznaceno, z.zodpovezeno = precteno, oznaceno, zodpovezeno
            zmeneno += 1
    if zmeneno:
        db.commit()
    return zmeneno


def _uklid_smazane(db: Session, s: ImapSpojeni, slozka: CrmEmailSlozka) -> int:
    """Zahodí z cache zprávy, které na serveru už nejsou (smazané/přesunuté).

    Kontroluje se jen okno posledních UID: projít celou složku by znamenalo
    SEARCH ALL při každém cyklu. Starší smazaná zpráva v cache zůstane, dokud
    se nezmění UIDVALIDITY – nepříjemné, ale nezpůsobí to špatná data,
    jen zbytečný řádek.
    """
    v_db = (
        db.query(CrmEmailZprava.id, CrmEmailZprava.uid)
        .filter(CrmEmailZprava.slozka_id == slozka.id)
        .order_by(CrmEmailZprava.uid.desc())
        .limit(OKNO_PRIZNAKU)
        .all()
    )
    if not v_db:
        return 0
    nejnizsi = min(u for _, u in v_db)
    na_serveru = set(s.uidy(f"UID {nejnizsi}:*"))
    ke_smazani = [zid for zid, u in v_db if u not in na_serveru]
    if not ke_smazani:
        return 0
    db.query(CrmEmailZprava).filter(CrmEmailZprava.id.in_(ke_smazani)).delete(
        synchronize_session=False
    )
    db.commit()
    return len(ke_smazani)


# ---- celá schránka -----------------------------------------------------------
def synchronizuj_ucet(db: Session, ucet: CrmEmailUcet, jen_inbox: bool = False) -> dict:
    """Jeden průběh synchronizace celé schránky. Chybu zapíše k účtu a vyhodí dál.

    `jen_inbox=True` je rychlý cyklus pro worker: Doručená pošta se kontroluje
    často, ostatní složky stačí občas. Bez toho by se každou minutu procházelo
    dvacet složek kvůli jedné nové zprávě.
    """
    zacatek = _ted()
    vysledek: dict = {"slozky": {}, "nove": 0, "zmenene": 0, "smazane": 0}
    try:
        with spojeni(ucet) as s:
            vysledek["slozky_srovnani"] = synchronizuj_slozky(db, s, ucet)

            q = db.query(CrmEmailSlozka).filter_by(ucet_id=ucet.id, sync_zapnuto=True)
            if jen_inbox:
                q = q.filter(CrmEmailSlozka.druh == "inbox")
            for slozka in q.order_by(CrmEmailSlozka.poradi, CrmEmailSlozka.nazev).all():
                try:
                    d = synchronizuj_slozku(db, s, slozka)
                except ImapChyba as e:
                    # Jedna rozbitá složka nesmí shodit celou schránku.
                    db.rollback()
                    vysledek["slozky"][slozka.nazev] = {"chyba": str(e)}
                    continue
                vysledek["slozky"][slozka.nazev] = d
                vysledek["nove"] += d["nove"]
                vysledek["zmenene"] += d["zmenene"]
                vysledek["smazane"] += d["smazane"]
    except ImapChyba as e:
        db.rollback()
        ucet.stav = "chyba"
        ucet.posledni_chyba = str(e)[:2000]
        ucet.posledni_sync_at = _ted()
        db.commit()
        raise

    ucet.stav = "ok"
    ucet.posledni_chyba = ""
    ucet.posledni_sync_at = _ted()
    db.commit()
    vysledek["trvani_s"] = round((_ted() - zacatek).total_seconds(), 2)
    return vysledek


# ---- tělo zprávy -------------------------------------------------------------
def stahni_telo(db: Session, zprava: CrmEmailZprava) -> CrmEmailZprava:
    """Dotáhne text, HTML a seznam příloh. Podruhé už jen vrátí, co je v DB."""
    if zprava.telo_stazeno:
        return zprava
    slozka = zprava.slozka
    with pujcene(slozka.ucet) as s:
        s.vyber(slozka.imap_nazev)
        data = s.zprava(zprava.uid)

    zprava.telo_text = data.get("text") or ""
    zprava.telo_html = data.get("html") or ""
    zprava.telo_stazeno = True
    if not zprava.vypis:
        zprava.vypis = vypis_z_tela(zprava.telo_text, zprava.telo_html)[:DELKA_VYPISU]
    if not zprava.velikost:
        zprava.velikost = data.get("velikost") or 0

    # Přílohy se zapisují až tady – ze hlavičky se poznat nedají.
    db.query(CrmEmailPriloha).filter_by(zprava_id=zprava.id).delete(synchronize_session=False)
    skutecne = 0
    for p in data.get("prilohy", []):
        db.add(
            CrmEmailPriloha(
                zprava_id=zprava.id,
                nazev=(p["nazev"] or "priloha")[:255],
                mime=(p["mime"] or "")[:100],
                velikost=p["velikost"],
                cislo_casti=p["cislo_casti"][:20],
                vlozeny=bool(p.get("vlozeny")),
            )
        )
        if not p.get("vlozeny"):
            skutecne += 1
    zprava.ma_prilohy = skutecne > 0
    db.commit()
    return zprava


# ---- zápis zpět na server ----------------------------------------------------
def nastav_precteno(db: Session, zprava: CrmEmailZprava, precteno: bool) -> None:
    """Označí zprávu (ne)přečtenou **i na serveru**.

    Pořadí je schválně „nejdřív server, pak DB": kdyby se zapsalo do DB a server
    to odmítl, appka by tvrdila něco jiného než mobil a při další synchronizaci
    by se to vrátilo zpátky – uživatel by viděl, jak mu appka „samovolně" mění
    přečtenost.
    """
    slozka = zprava.slozka
    with pujcene(slozka.ucet) as s:
        s.nastav_priznak(slozka.imap_nazev, [zprava.uid], "\\Seen", precteno)
    zprava.precteno = precteno
    _preposcitej(db, slozka)
    db.commit()


def nastav_oznaceno(db: Session, zprava: CrmEmailZprava, oznaceno: bool) -> None:
    """Vlaječka (`\\Flagged`) – tatáž logika jako u přečtení."""
    slozka = zprava.slozka
    with pujcene(slozka.ucet) as s:
        s.nastav_priznak(slozka.imap_nazev, [zprava.uid], "\\Flagged", oznaceno)
    zprava.oznaceno = oznaceno
    db.commit()


def presun_zpravu(db: Session, zprava: CrmEmailZprava, cil: CrmEmailSlozka) -> None:
    """Přesune zprávu do jiné složky na serveru a smaže ji z cache.

    Z cache se maže schválně, místo přepsání `slozka_id`: po přesunu dostane
    zpráva v cílové složce **nové UID**, které dopředu neznáme. Dopsat ji tam
    s hádaným UID by rozbilo párování. Příští synchronizace cílové složky ji
    stáhne správně.
    """
    zdroj = zprava.slozka
    if zdroj.id == cil.id:
        return
    with pujcene(zdroj.ucet) as s:
        s.presun(zdroj.imap_nazev, [zprava.uid], cil.imap_nazev)
    db.delete(zprava)
    _preposcitej(db, zdroj)
    db.commit()


def _preposcitej(db: Session, slozka: CrmEmailSlozka) -> None:
    """Přepočte počet nepřečtených – to číslo visí v panelu složek."""
    db.flush()
    slozka.nepreectenych = (
        db.query(func.count(CrmEmailZprava.id))
        .filter(CrmEmailZprava.slozka_id == slozka.id, CrmEmailZprava.precteno.is_(False))
        .scalar()
        or 0
    )


def slozka_druhu(db: Session, ucet_id: int, druh: str) -> CrmEmailSlozka | None:
    """Systémová složka daného druhu (`odeslane`, `kos`…), nebo None."""
    return (
        db.query(CrmEmailSlozka)
        .filter_by(ucet_id=ucet_id, druh=druh)
        .order_by(CrmEmailSlozka.id)
        .first()
    )


def stara_nez(hodin: int) -> datetime:
    """Pomocník pro plánovač – hranice „starší než N hodin"."""
    return _ted() - timedelta(hours=hodin)


# ---- napojení zprávy na záznamy CRM („rejnetování") --------------------------
def zaloz_vazby(db: Session, zprava: CrmEmailZprava, komitni: bool = True) -> int:
    """Napojí zprávu na všechny firmy a kontakty, které v ní figurují.

    Volá se při stažení zprávy. Vazby označené `zdroj="rucne"` se **nesahají** —
    ruční rozhodnutí člověka nemá automatika přepisovat (ani obnovovat vazbu,
    kterou někdo schoval).
    """
    from app.crm import adresar
    from app.crm.models import CrmEmailVazba

    nalezy = adresar.dohledaj_vsechny(db, adresar.adresy_ze_zpravy(zprava))
    if not nalezy:
        return 0

    existujici = {
        (v.zakaznik_id, v.kontakt_id)
        for v in db.query(CrmEmailVazba).filter(CrmEmailVazba.zprava_id == zprava.id)
    }
    pridano = 0
    for n in nalezy:
        if (n["zakaznik_id"], n["kontakt_id"]) in existujici:
            continue
        db.add(
            CrmEmailVazba(
                zprava_id=zprava.id,
                zakaznik_id=n["zakaznik_id"],
                kontakt_id=n["kontakt_id"],
                pripad_id=n["pripad_id"],
                adresa=n["adresa"][:255],
                role=n["role"],
                zdroj="auto",
                kdy=zprava.datum_at,
            )
        )
        pridano += 1

    # Hlavní firma u zprávy = ta od odesílatele (u odchozí pošty od příjemce).
    # Drží se kvůli štítku v seznamu pošty, kde je místo na jednu.
    if zprava.zakaznik_id is None and nalezy:
        zprava.zakaznik_id = nalezy[0]["zakaznik_id"]
        zprava.pripad_id = nalezy[0]["pripad_id"]

    if komitni and pridano:
        db.commit()
    return pridano
