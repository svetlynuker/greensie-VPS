"""Testy e-mailového klienta (CRM-33) – části, které nepotřebují DB ani IMAP.

Co se tady hlídá a proč právě to:

* **Kódování názvů složek.** IMAP posílá `Odesl&AOE-n&AOk-` místo `Odeslané`.
  Když se dekodér rozbije, appka ukáže složky jako hieroglyfy a přesun do
  složky přestane fungovat – a hledá se to hodiny, protože nic nespadne.
* **Rozpoznání robota.** Na tom stojí pojistka proti smyčce OOO odpovědí.
  Chyba tady znamená dva autorespondery, které si píší navzájem, dokud
  někdo nevypne server.
* **Klíč vlákna.** Kdyby `Re: Nabídka` a `Nabídka` spadly do různých vláken,
  konverzace se rozsype na jednotlivé zprávy.
* **Šifrování hesel.** Heslo od schránky je to nejcitlivější, co appka drží.
  Test hlídá, že se dešifruje zpátky a že bez klíče nejde uložit (a hlavně že
  se dešifrování cizím klíčem nechová jako úspěch).
"""

from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from app import crypto
from app.crm.email_imap import (
    dekoduj_nazev,
    druh_slozky,
    hlavicky_ze_zpravy,
    telo_ze_zpravy,
    vypis_z_tela,
    zakoduj_nazev,
)
from app.crm.email_sync import vlakno_klic


# ---- názvy složek ------------------------------------------------------------
@pytest.mark.parametrize(
    "zakodovano,cekano",
    [
        ("INBOX", "INBOX"),
        ("Ko&AWE-", "Koš"),
        ("Pr&AOE-ce", "Práce"),
        ("Test &- spol", "Test & spol"),
        ("Prace/2026", "Prace/2026"),
    ],
)
def test_dekoduj_nazev_slozky(zakodovano, cekano):
    assert dekoduj_nazev(zakodovano) == cekano


@pytest.mark.parametrize(
    "nazev", ["Odeslané", "Koš", "Školní věci", "Práce/2026", "INBOX", "Test & spol", "žluťoučký"]
)
def test_kodovani_nazvu_je_obousmerne(nazev):
    """Co appka zakóduje, musí jít zpátky – jinak se složka „ztratí"."""
    assert dekoduj_nazev(zakoduj_nazev(nazev)) == nazev


def test_rozbity_nazev_slozky_nespadne():
    """Neuzavřená sekvence se vrátí, jak přišla. Ošklivé, ale funkční."""
    assert dekoduj_nazev("Nezn&amy") == "Nezn&amy"


def test_druh_slozky_podle_priznaku_i_nazvu():
    # Server někdy pošle příznak, Seznam u části složek nic – musí fungovat obojí.
    assert druh_slozky("Cokoli", ["\\Sent"]) == "odeslane"
    assert druh_slozky("Odeslané", []) == "odeslane"
    assert druh_slozky("Koš", []) == "kos"
    assert druh_slozky("Moje složka", []) == "vlastni"
    # Příznak má přednost před názvem – server ví lépe než my.
    assert druh_slozky("Odeslané", ["\\Trash"]) == "kos"


# ---- vlákna ------------------------------------------------------------------
def test_vlakno_klic_slepi_odpovedi_k_originalu():
    zaklad = vlakno_klic("Nabídka FVE")
    assert vlakno_klic("Re: Nabídka FVE") == zaklad
    assert vlakno_klic("RE: Fwd: Nabídka FVE") == zaklad
    assert vlakno_klic("Odp: Nabídka FVE") == zaklad
    # Jiný předmět je jiné vlákno.
    assert vlakno_klic("Objednávka FVE") != zaklad


# ---- rozpoznání strojové pošty (pojistka OOO) --------------------------------
def _zprava(hlavicky: dict, telo: str = "ahoj") -> EmailMessage:
    m = EmailMessage()
    for k, v in hlavicky.items():
        m[k] = v
    m.set_content(telo)
    return m


def test_bezny_email_neni_automat():
    m = _zprava({"From": "Jan Novák <jan@firma.cz>", "Subject": "Dotaz", "To": "dan@greensie.cz"})
    assert hlavicky_ze_zpravy(m)["automat"] is False


@pytest.mark.parametrize(
    "hlavicka,hodnota",
    [
        ("Auto-Submitted", "auto-replied"),
        ("Precedence", "bulk"),
        ("List-Id", "<novinky.firma.cz>"),
        ("List-Unsubscribe", "<mailto:off@firma.cz>"),
        ("X-Auto-Response-Suppress", "All"),
    ],
)
def test_strojova_posta_se_pozna(hlavicka, hodnota):
    """Na tohle OOO odpovídat NESMÍ – jinak vznikne nekonečná smyčka."""
    m = _zprava({"From": "robot@firma.cz", "Subject": "Novinky", hlavicka: hodnota})
    assert hlavicky_ze_zpravy(m)["automat"] is True


def test_zprava_bez_odesilatele_je_automat():
    """Prázdný odesílatel = odraz nedoručitelnosti. Odpovídat na něj nemá komu."""
    m = _zprava({"Subject": "Undelivered Mail Returned to Sender"})
    assert hlavicky_ze_zpravy(m)["automat"] is True


# ---- hlavičky ----------------------------------------------------------------
def test_hlavicky_rozlusti_diakritiku_a_adresy():
    m = _zprava(
        {
            "From": "=?utf-8?B?SmFuIE5vdsOhaw==?= <Jan.Novak@Firma.CZ>",
            "To": "dan@greensie.cz, Petra <petra@firma.cz>",
            "Cc": "sef@firma.cz",
            "Subject": "=?utf-8?B?TmFiw61ka2E=?=",
        }
    )
    h = hlavicky_ze_zpravy(m)
    assert h["od_jmeno"] == "Jan Novák"
    # Adresy se normalizují na malá písmena, jinak by párování na CRM míjelo.
    assert h["od_adresa"] == "jan.novak@firma.cz"
    assert h["predmet"] == "Nabídka"
    assert [a["adresa"] for a in h["komu"]] == ["dan@greensie.cz", "petra@firma.cz"]
    assert [a["adresa"] for a in h["kopie"]] == ["sef@firma.cz"]


def test_predmet_pres_vic_radku_zustane_na_jednom():
    """Zalomený předmět by v seznamu zpráv rozhodil řádek.

    Dlouhé hlavičky přicházejí ze sítě „složené" na víc řádků (RFC 5322), takže
    se test staví z surových bajtů – nastavit takovou hlavičku přes
    `EmailMessage` totiž knihovna zakazuje.
    """
    import email as email_modul

    surove = (
        b"From: a@b.cz\r\n"
        b"Subject: Dlouhy predmet,\r\n ktery pokracuje na druhem radku\r\n"
        b"\r\ntelo\r\n"
    )
    h = hlavicky_ze_zpravy(email_modul.message_from_bytes(surove))
    assert "\n" not in h["predmet"] and "\r" not in h["predmet"]
    assert h["predmet"] == "Dlouhy predmet, ktery pokracuje na druhem radku"


# ---- tělo a přílohy ----------------------------------------------------------
def test_telo_rozdeli_text_html_a_prilohy():
    m = EmailMessage()
    m["From"] = "a@b.cz"
    m["Subject"] = "S přílohou"
    m.set_content("Textová verze")
    m.add_alternative("<p>HTML verze</p>", subtype="html")
    m.add_attachment(
        b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="nabidka.pdf"
    )

    telo = telo_ze_zpravy(m)
    assert "Textová verze" in telo["text"]
    assert "HTML verze" in telo["html"]
    nazvy = [p["nazev"] for p in telo["prilohy"]]
    assert "nabidka.pdf" in nazvy
    priloha = next(p for p in telo["prilohy"] if p["nazev"] == "nabidka.pdf")
    assert priloha["mime"] == "application/pdf"
    assert priloha["velikost"] > 0
    # Číslo části se používá k pozdějšímu stažení – nesmí být prázdné.
    assert priloha["cislo_casti"]


def test_vypis_z_html_odstrani_znacky_i_entity():
    vypis = vypis_z_tela(
        "", "<html><head><style>a{color:red}</style></head><body><p>Ahoj&nbsp;sv&#283;te</p>"
        "<script>zlo()</script></body></html>"
    )
    assert vypis == "Ahoj světe"
    assert "script" not in vypis
    assert "zlo" not in vypis


def test_vypis_dava_prednost_textu():
    assert vypis_z_tela("Čistý text", "<p>HTML</p>") == "Čistý text"


# ---- šifrování hesel ---------------------------------------------------------
KLIC_A = "iCA1YAqJlXBqQ0vJkTZlWvBM3TfMQ2z2xdNfTZ8sIYE="
KLIC_B = "9r0nSHBBoJDL_VqJqmzBLTt4h6uCTLKMh1kMv6QqoLE="


@pytest.fixture
def s_klicem(monkeypatch):
    monkeypatch.setenv("APP_ENC_KEY", KLIC_A)
    crypto._zapomen_klic()
    yield
    crypto._zapomen_klic()


def test_heslo_se_zasifruje_a_desifruje(s_klicem):
    sifra = crypto.sifruj("tajneHeslo123")
    assert sifra and sifra != "tajneHeslo123"
    assert crypto.desifruj(sifra) == "tajneHeslo123"


def test_prazdne_heslo_znamena_nenastaveno(s_klicem):
    assert crypto.sifruj("") == ""
    assert crypto.desifruj("") == ""


def test_bez_klice_se_heslo_neulozi(monkeypatch):
    """Radši chyba než heslo v čitelné podobě v databázi."""
    monkeypatch.delenv("APP_ENC_KEY", raising=False)
    monkeypatch.delenv("KONEKTOR_ENC_KEY", raising=False)
    crypto._zapomen_klic()
    assert crypto.klic_dostupny() is False
    with pytest.raises(RuntimeError):
        crypto.sifruj("heslo")
    crypto._zapomen_klic()


def test_desifrovani_cizim_klicem_vraci_prazdno(monkeypatch):
    """Nesmí to projít jako úspěch – appka pak řekne „zadej heslo znovu"."""
    monkeypatch.setenv("APP_ENC_KEY", KLIC_A)
    crypto._zapomen_klic()
    sifra = crypto.sifruj("heslo")

    monkeypatch.setenv("APP_ENC_KEY", KLIC_B)
    crypto._zapomen_klic()
    assert crypto.desifruj(sifra) == ""
    crypto._zapomen_klic()


def test_zaloha_na_konektorovy_klic(monkeypatch):
    """Na produkci klíč konektoru už existuje – e-mail nemá čekat na nový."""
    monkeypatch.delenv("APP_ENC_KEY", raising=False)
    monkeypatch.setenv("KONEKTOR_ENC_KEY", KLIC_A)
    crypto._zapomen_klic()
    assert crypto.klic_dostupny() is True
    assert crypto.zdroj_klice() == "KONEKTOR_ENC_KEY"
    assert crypto.desifruj(crypto.sifruj("x")) == "x"
    crypto._zapomen_klic()


def test_neplatny_klic_se_preskoci_na_dalsi(monkeypatch):
    """Překlep v APP_ENC_KEY nesmí odstřihnout appku od fungujícího klíče."""
    monkeypatch.setenv("APP_ENC_KEY", "tohle-neni-platny-fernet-klic")
    monkeypatch.setenv("KONEKTOR_ENC_KEY", KLIC_A)
    crypto._zapomen_klic()
    assert crypto.klic_dostupny() is True
    assert crypto.zdroj_klice() == "KONEKTOR_ENC_KEY"
    crypto._zapomen_klic()


# ============================================================================
# Automatika příchozí pošty (dávka E4)
#
# Nejdůležitější testy celého modulu. Chyba v pravidlech znamená přeházenou
# schránku; chyba v pojistkách OOO znamená dva roboty, kteří si píší navzájem,
# dokud někdo nevypne server. Proto se tady testují hlavně situace, kdy se
# odpovědět NESMÍ.
# ============================================================================
from datetime import date

from app.crm import email_automat
from app.crm.email_smtp import (
    _adresy_ze_textu,
    _pridej_podpis,
    priprav_odpoved,
    priprav_preposlani,
)


class FalesnaZprava:
    """Zpráva bez databáze – stačí atributy, které automatika čte."""

    def __init__(self, **kw):
        self.od_jmeno = kw.get("od_jmeno", "Jan Novák")
        self.od_adresa = kw.get("od_adresa", "jan@firma.cz")
        self.komu = kw.get("komu", [{"jmeno": "Dan", "adresa": "dan@greensie.cz"}])
        self.kopie = kw.get("kopie", [])
        self.predmet = kw.get("predmet", "Poptávka FVE")
        self.vypis = kw.get("vypis", "Dobrý den, měli bychom zájem o nabídku.")
        self.telo_text = kw.get("telo_text", self.vypis)
        self.telo_html = kw.get("telo_html", "")
        self.ma_prilohy = kw.get("ma_prilohy", False)
        self.automat = kw.get("automat", False)
        self.smer = kw.get("smer", "prichozi")
        self.datum_at = kw.get("datum_at", datetime(2026, 7, 31, 9, 0, tzinfo=timezone.utc))
        self.message_id = kw.get("message_id", "<abc@firma.cz>")
        self.in_reply_to = kw.get("in_reply_to", "")
        self.odpovedet_na = kw.get("odpovedet_na", "")
        self.id = kw.get("id", 1)
        self.zakaznik_id = kw.get("zakaznik_id", None)
        self.pripad_id = kw.get("pripad_id", None)


class FalesnePravidlo:
    def __init__(self, podminky, spojka="a", akce=None):
        self.podminky = podminky
        self.spojka = spojka
        self.akce = akce or [{"typ": "oznacit"}]
        self.nazev = "Test"
        self.zastavit_dalsi = False


class FalesnyUcet:
    def __init__(self, **kw):
        self.id = 1
        self.adresa = kw.get("adresa", "dan@greensie.cz")
        self.jmeno_odesilatele = kw.get("jmeno_odesilatele", "Dan Lupínek")
        self.ooo_zapnuto = kw.get("ooo_zapnuto", True)
        self.ooo_od = kw.get("ooo_od", None)
        self.ooo_do = kw.get("ooo_do", None)
        self.ooo_predmet = kw.get("ooo_predmet", "Jsem mimo kancelář")
        self.ooo_text = kw.get("ooo_text", "Vrátím se v pondělí.")
        self.podpis = kw.get("podpis", "")
        self.smtp_host = "smtp.seznam.cz"
        self.smtp_port = 587


# ---- podmínky pravidel -------------------------------------------------------
def test_pravidlo_sedi_na_odesilatele():
    z = FalesnaZprava(od_adresa="faktury@dodavatel.cz")
    p = FalesnePravidlo([{"pole": "od", "operator": "obsahuje", "hodnota": "dodavatel.cz"}])
    assert email_automat.pravidlo_sedi(z, p) is True


def test_pravidlo_nesedi_na_jineho_odesilatele():
    z = FalesnaZprava(od_adresa="jan@firma.cz")
    p = FalesnePravidlo([{"pole": "od", "operator": "obsahuje", "hodnota": "dodavatel.cz"}])
    assert email_automat.pravidlo_sedi(z, p) is False


def test_spojka_a_vyzaduje_obe_podminky():
    z = FalesnaZprava(od_adresa="jan@firma.cz", predmet="Faktura 2026")
    obe = [
        {"pole": "od", "operator": "obsahuje", "hodnota": "firma.cz"},
        {"pole": "predmet", "operator": "obsahuje", "hodnota": "faktura"},
    ]
    assert email_automat.pravidlo_sedi(z, FalesnePravidlo(obe, "a")) is True

    nesedici = [
        {"pole": "od", "operator": "obsahuje", "hodnota": "firma.cz"},
        {"pole": "predmet", "operator": "obsahuje", "hodnota": "objednávka"},
    ]
    assert email_automat.pravidlo_sedi(z, FalesnePravidlo(nesedici, "a")) is False
    # …ale „nebo" stačí jedna.
    assert email_automat.pravidlo_sedi(z, FalesnePravidlo(nesedici, "nebo")) is True


def test_pravidlo_bez_podminek_nesedi_na_nic():
    """Prázdné podmínky by znamenaly „platí vždy" – rozházelo by to schránku."""
    assert email_automat.pravidlo_sedi(FalesnaZprava(), FalesnePravidlo([])) is False


@pytest.mark.parametrize(
    "operator,hodnota,ceka",
    [
        ("je", "poptávka fve", True),
        ("je", "poptávka", False),
        ("zacina", "poptávka", True),
        ("konci", "fve", True),
        ("konci", "poptávka", False),
        ("neobsahuje", "objednávka", True),
        ("neobsahuje", "poptávka", False),
    ],
)
def test_operatory_pravidel(operator, hodnota, ceka):
    z = FalesnaZprava(predmet="Poptávka FVE")
    p = FalesnePravidlo([{"pole": "predmet", "operator": operator, "hodnota": hodnota}])
    assert email_automat.pravidlo_sedi(z, p) is ceka


def test_podminka_na_prilohu():
    p = FalesnePravidlo([{"pole": "ma_prilohy", "operator": "ano", "hodnota": ""}])
    assert email_automat.pravidlo_sedi(FalesnaZprava(ma_prilohy=True), p) is True
    assert email_automat.pravidlo_sedi(FalesnaZprava(ma_prilohy=False), p) is False


def test_presun_se_radi_az_nakonec():
    """Po přesunu zpráva v cache není – další akce by sahaly do prázdna."""
    p = FalesnePravidlo(
        [{"pole": "od", "operator": "obsahuje", "hodnota": "x"}],
        akce=[{"typ": "presun", "slozka_id": 3}, {"typ": "oznacit_precteno"}],
    )
    serazeno = [a["typ"] for a in email_automat._serad_akce(p)]
    assert serazeno[-1] == "presun"


# ---- pojistky OOO (nejdůležitější část) --------------------------------------
def test_ooo_odpovi_na_bezny_email():
    ucet, z = FalesnyUcet(), FalesnaZprava()
    smi, duvod = email_automat.smi_ooo_odpovedet(_bez_db(), ucet, z)
    assert smi is True, duvod


def test_ooo_neodpovi_robotovi():
    """RFC 3834: autoresponder nesmí odpovídat robotovi. Jinak vznikne smyčka."""
    smi, duvod = email_automat.smi_ooo_odpovedet(
        _bez_db(), FalesnyUcet(), FalesnaZprava(automat=True)
    )
    assert smi is False
    assert "strojová" in duvod


def test_ooo_neodpovi_sam_sobe():
    smi, duvod = email_automat.smi_ooo_odpovedet(
        _bez_db(), FalesnyUcet(adresa="dan@greensie.cz"),
        FalesnaZprava(od_adresa="DAN@greensie.cz"),
    )
    assert smi is False
    assert "sama" in duvod


def test_ooo_neodpovi_na_odchozi_postu():
    smi, _ = email_automat.smi_ooo_odpovedet(
        _bez_db(), FalesnyUcet(), FalesnaZprava(smer="odchozi")
    )
    assert smi is False


def test_ooo_neodpovi_bez_odesilatele():
    smi, _ = email_automat.smi_ooo_odpovedet(
        _bez_db(), FalesnyUcet(), FalesnaZprava(od_adresa="")
    )
    assert smi is False


def test_ooo_mimo_obdobi_neodpovida():
    dnes = date(2026, 7, 31)
    minulost = FalesnyUcet(ooo_od=date(2026, 7, 1), ooo_do=date(2026, 7, 15))
    smi, _ = email_automat.smi_ooo_odpovedet(_bez_db(), minulost, FalesnaZprava(), dnes)
    assert smi is False

    budoucnost = FalesnyUcet(ooo_od=date(2026, 8, 10))
    smi, _ = email_automat.smi_ooo_odpovedet(_bez_db(), budoucnost, FalesnaZprava(), dnes)
    assert smi is False

    prave_ted = FalesnyUcet(ooo_od=date(2026, 7, 20), ooo_do=date(2026, 8, 5))
    smi, duvod = email_automat.smi_ooo_odpovedet(_bez_db(), prave_ted, FalesnaZprava(), dnes)
    assert smi is True, duvod


def test_ooo_vypnute_neodpovida():
    smi, _ = email_automat.smi_ooo_odpovedet(
        _bez_db(), FalesnyUcet(ooo_zapnuto=False), FalesnaZprava()
    )
    assert smi is False


def _bez_db():
    """Náhrada session – `smi_ooo_odpovedet` se jí ptá jen na dřívější odpovědi."""

    class PrazdnyDotaz:
        def filter(self, *_a, **_k):
            return self

        def first(self):
            return None

    class PrazdnaSession:
        def query(self, *_a, **_k):
            return PrazdnyDotaz()

    return PrazdnaSession()


# ---- odesílání: parsování adres a podpis -------------------------------------
@pytest.mark.parametrize(
    "vstup,ceka",
    [
        ("a@b.cz", ["a@b.cz"]),
        ("a@b.cz, c@d.cz", ["a@b.cz", "c@d.cz"]),
        ("a@b.cz; c@d.cz", ["a@b.cz", "c@d.cz"]),
        ("Jan Novák <jan@firma.cz>", ["jan@firma.cz"]),
        ("a@b.cz, a@b.cz", ["a@b.cz"]),          # duplicita se zahodí
        ("nesmysl, a@b.cz", ["a@b.cz"]),          # adresa bez zavináče vypadne
        (["a@b.cz", " c@d.cz "], ["a@b.cz", "c@d.cz"]),
        ("", []),
    ],
)
def test_parsovani_adres(vstup, ceka):
    assert _adresy_ze_textu(vstup) == ceka


def test_podpis_se_neprida_dvakrat():
    """Šablony podpis často obsahují – druhý by vypadal jako chyba appky."""
    podpis = "Dan Lupínek\nGreensie s.r.o."
    s_podpisem = _pridej_podpis("Dobrý den,\n\nDan Lupínek\nGreensie s.r.o.", podpis)
    assert s_podpisem.count("Dan Lupínek") == 1

    bez_podpisu = _pridej_podpis("Dobrý den,", podpis)
    assert "Dan Lupínek" in bez_podpisu
    assert bez_podpisu.count("Dan Lupínek") == 1


# ---- příprava odpovědi a přeposlání ------------------------------------------
def test_odpoved_ma_re_prefix_a_citaci():
    z = FalesnaZprava(predmet="Poptávka FVE", telo_text="Dobrý den,\nmáme zájem.")
    v = priprav_odpoved(z, vsem=False, moje_adresa="dan@greensie.cz")
    assert v["predmet"] == "Re: Poptávka FVE"
    assert v["komu"] == ["jan@firma.cz"]
    assert "> Dobrý den," in v["telo"]
    assert v["odpoved_na_id"] == z.id


def test_odpoved_nezdvojuje_re():
    z = FalesnaZprava(predmet="Re: Poptávka")
    assert priprav_odpoved(z, False, "dan@greensie.cz")["predmet"] == "Re: Poptávka"


def test_odpovedet_vsem_vynecha_moji_adresu():
    """Odpovídat sám sobě nechce nikdo."""
    z = FalesnaZprava(
        komu=[{"adresa": "dan@greensie.cz"}, {"adresa": "kolega@greensie.cz"}],
        kopie=[{"adresa": "sef@firma.cz"}],
    )
    v = priprav_odpoved(z, vsem=True, moje_adresa="dan@greensie.cz")
    assert "dan@greensie.cz" not in v["kopie"]
    assert set(v["kopie"]) == {"kolega@greensie.cz", "sef@firma.cz"}
    assert v["komu"] == ["jan@firma.cz"]


def test_odpoved_respektuje_reply_to():
    z = FalesnaZprava(od_adresa="noreply@firma.cz", odpovedet_na="obchod@firma.cz")
    assert priprav_odpoved(z, False, "dan@greensie.cz")["komu"] == ["obchod@firma.cz"]


def test_preposlani_ma_fwd_prefix_a_zadneho_prijemce():
    z = FalesnaZprava(predmet="Poptávka FVE")
    v = priprav_preposlani(z)
    assert v["predmet"] == "Fwd: Poptávka FVE"
    assert v["komu"] == []
    assert "Přeposlaná zpráva" in v["telo"]


def test_preposlani_upozorni_na_neprenesene_prilohy():
    v = priprav_preposlani(FalesnaZprava(ma_prilohy=True))
    assert "přílohy" in v["telo"].lower()


# ============================================================================
# Názvy IMAP příkazů (regrese z 31. 7. 2026)
#
# Reálná chyba z produkce: kód volal `examine`, protože IMAP příkaz EXAMINE
# existuje — jenže `imaplib` metodu `examine` NEMÁ. Read-only otevření složky
# se dělá přes `select(mailbox, readonly=True)`. Připojení ke schránce spadlo
# hláškou „Unknown IMAP4 command: 'examine'" až u živého serveru, protože
# žádný test IMAP spojení nenavazuje.
#
# Tyhle dva testy tu třídu chyb chytí bez sítě: první ověří, že každý název
# předaný `_prikaz` je skutečná metoda `imaplib.IMAP4`, druhý zakáže skládat
# název příkazu do proměnné (přesně to první kontrolu tehdy obešlo).
# ============================================================================
import imaplib
import pathlib
import re

ZDROJE_IMAP = ["app/crm/email_imap.py", "app/crm/email_pool.py"]


def _zdroj(cesta):
    return pathlib.Path(cesta).read_text(encoding="utf-8")


def test_vsechny_imap_prikazy_existuji_v_imaplib():
    """Každý název v `_prikaz("…")` musí být metoda imaplib.IMAP4."""
    nalezene = set()
    for cesta in ZDROJE_IMAP:
        nalezene |= set(re.findall(r'_prikaz\(\s*"([a-z_]+)"', _zdroj(cesta)))

    assert nalezene, "Nenašel jsem žádné volání _prikaz – změnila se konvence?"
    chybi = sorted(j for j in nalezene if not hasattr(imaplib.IMAP4, j))
    assert not chybi, (
        "Tyhle názvy nejsou metody imaplib.IMAP4, takže spojení spadne na "
        "„Unknown IMAP4 command“: "
        + ", ".join(chybi)
        + ". Pozor hlavně na `examine` – dělá se přes select(readonly=True)."
    )


def test_nazev_imap_prikazu_se_neskalda_dynamicky():
    """`_prikaz(promenna, …)` je zakázané – obešlo by to kontrolu výš.

    Právě takhle chyba s `examine` vznikla: název se vybíral ternárním výrazem,
    takže v kódu nebyl jako literál a nikdo ho neporovnal s `imaplib`.
    """
    prohresky = []
    for cesta in ZDROJE_IMAP:
        for cislo, radek in enumerate(_zdroj(cesta).splitlines(), start=1):
            volani = re.search(r'_prikaz\(\s*([^"\s)])', radek)
            # `self._prikaz(` uvnitř definice metody samotné neřešíme.
            if volani and "def _prikaz" not in radek:
                prohresky.append(f"{cesta}:{cislo}: {radek.strip()}")
    assert not prohresky, (
        "Název IMAP příkazu se musí psát jako literál, ne skládat do proměnné:\n"
        + "\n".join(prohresky)
    )


def test_read_only_otevreni_jde_pres_select_readonly():
    """Kontrola konkrétního místa, kde chyba byla."""
    zdroj = _zdroj("app/crm/email_imap.py")
    assert '_prikaz("select", self._uvozovky(imap_nazev), jen_cteni)' in zdroj, (
        "`vyber()` musí volat select s příznakem readonly, ne examine."
    )
    assert '_prikaz("examine"' not in zdroj, "imaplib metodu `examine` nemá."


def test_vyber_slozky_posle_select_s_readonly():
    """Behaviorální test: `vyber()` musí zavolat select(nazev, readonly).

    Kontrola zdrojáku podle řetězce je křehká — tenhle test ověří skutečné
    volání proti podvrženému imaplib objektu, takže projde jen když se
    read-only otevření opravdu dělá přes `select`.
    """
    from app.crm.email_imap import ImapSpojeni

    class FalesnyImap:
        def __init__(self):
            self.volani = []

        def select(self, mailbox="INBOX", readonly=False):
            self.volani.append(("select", mailbox, readonly))
            return "OK", [b"42"]

        def response(self, _co):
            return "OK", [b"UIDVALIDITY 12345"]

        # Kdyby kód sáhl po neexistující metodě (jako kdysi `examine`),
        # spadne to tady stejně jako u opravdového imaplib.
        def __getattr__(self, jmeno):
            raise AttributeError(f"Unknown IMAP4 command: '{jmeno}'")

    s = ImapSpojeni("imap.seznam.cz", 993, "a@b.cz", "heslo")
    falesny = FalesnyImap()
    s._m = falesny

    stav = s.vyber("INBOX", jen_cteni=True)
    assert falesny.volani == [("select", '"INBOX"', True)], falesny.volani
    assert stav["pocet"] == 42
    assert stav["uidvalidity"] == 12345

    # Zápisový režim musí poslat readonly=False, jinak by nešlo měnit příznaky.
    s.vyber("INBOX", jen_cteni=False)
    assert falesny.volani[-1] == ("select", '"INBOX"', False)


# ============================================================================
# HTML podpis z profilu (CRM-33)
#
# Podpis jde ven pod každou zprávou, takže chyba je vidět u každého zákazníka.
# Hlídá se hlavně: volitelnost funkce (Danův požadavek), interaktivita
# telefonu/mailu/webu, escapování a to, že se zpráva opravdu sestaví jako
# multipart (text i HTML) — klient bez HTML nesmí dostat prázdnou zprávu.
# ============================================================================
from app.crm import email_podpis


class FalesnyProfil:
    def __init__(self, **kw):
        self.jmeno = kw.get("jmeno", "Daniel")
        self.prijmeni = kw.get("prijmeni", "Lupínek")
        self.telefon = kw.get("telefon", "773492029")
        self.funkce = kw.get("funkce", "")
        self.pozdrav = kw.get("pozdrav", "S pozdravem")
        self.podpis_zapnuty = kw.get("podpis_zapnuty", True)


@pytest.mark.parametrize(
    "vstup,ceka",
    [
        ("773492029", "+420 773 492 029"),
        ("+420 773 492 029", "+420 773 492 029"),
        ("00420773492029", "+420 773 492 029"),
        ("773 492 029", "+420 773 492 029"),
        ("", ""),
        ("abc", ""),
    ],
)
def test_telefon_se_normalizuje_na_jeden_tvar(vstup, ceka):
    """Do pole se dá napsat cokoli, v datech i v podpisu je jeden tvar."""
    assert email_podpis.formatuj_telefon(vstup) == ceka


def test_telefon_pro_odkaz_je_bez_mezer():
    assert email_podpis.telefon_pro_odkaz("773 492 029") == "+420773492029"
    assert email_podpis.telefon_pro_odkaz("") == ""


def test_podpis_bez_funkce_nema_radek_s_funkci():
    """Danův požadavek: prázdná funkce = podpis bez ní, ne prázdné místo."""
    html_bez = email_podpis.sestav_html(FalesnyProfil(funkce=""), "a@greensie.cz")
    html_s = email_podpis.sestav_html(FalesnyProfil(funkce="Jednatel"), "a@greensie.cz")
    assert "Jednatel" not in html_bez
    assert "Jednatel" in html_s
    # Zelená linka musí být pod posledním řádkem hlavičky – tedy pod jménem,
    # když funkce chybí, a pod funkcí, když je. Nikdy dvakrát.
    zelena = "border-bottom:2px solid rgb(114,193,70)"
    assert html_bez.count(zelena) == 1
    assert html_s.count(zelena) == 1


def test_kontakty_v_podpisu_jsou_proklikavaci():
    """Telefon, e-mail i web musí být odkazy (výslovné zadání Dana)."""
    h = email_podpis.sestav_html(FalesnyProfil(), "daniel.lupinek@greensie.cz")
    assert 'href="tel:+420773492029"' in h
    assert 'href="mailto:daniel.lupinek@greensie.cz"' in h
    assert 'href="https://www.greensie.cz/"' in h


def test_podpis_bez_telefonu_radek_vynecha():
    h = email_podpis.sestav_html(FalesnyProfil(telefon=""), "a@greensie.cz")
    assert "tel:" not in h
    # E-mail a web tam ale zůstávají.
    assert "mailto:a@greensie.cz" in h
    assert "www.greensie.cz" in h


def test_prazdny_profil_negeneruje_podpis():
    """Samotné logo bez jména by vypadalo jako chyba – radši nic."""
    prazdny = FalesnyProfil(jmeno="", prijmeni="")
    assert email_podpis.profil_je_vyplneny(prazdny) is False
    assert email_podpis.sestav_html(prazdny, "a@b.cz") == ""
    assert email_podpis.sestav_text(prazdny, "a@b.cz") == ""


def test_podpis_escapuje_jmeno():
    """Jméno jde do HTML – bez escapování by `&` nebo `<` rozbily podpis."""
    h = email_podpis.sestav_html(
        FalesnyProfil(jmeno="<script>", prijmeni="A&B"), "a@b.cz"
    )
    assert "<script>" not in h
    assert "&lt;script&gt;" in h and "A&amp;B" in h


def test_podpis_nepouziva_gmailovou_proxy():
    """Předloha měla obrázky přes ci3.googleusercontent.com – mimo Gmail
    nespolehlivé. Musí se používat skutečný zdroj na webu Greensie."""
    h = email_podpis.sestav_html(FalesnyProfil(), "a@b.cz")
    assert "googleusercontent" not in h
    assert "greensie-fotovoltaika.cz/wp-content/uploads/logo_greensie.png" in h


def test_pracovni_adresa_ze_jmena():
    assert email_podpis.pracovni_adresa(FalesnyProfil()) == "daniel.lupinek@greensie.cz"
    assert (
        email_podpis.pracovni_adresa(FalesnyProfil(jmeno="Žofie", prijmeni="Čermák"))
        == "zofie.cermak@greensie.cz"
    )
    assert email_podpis.pracovni_adresa(FalesnyProfil(jmeno="", prijmeni="")) == ""


def test_textova_podoba_podpisu_ma_vse_podstatne():
    t = email_podpis.sestav_text(FalesnyProfil(funkce="Jednatel"), "a@greensie.cz")
    for kus in ["S pozdravem", "Daniel Lupínek", "Jednatel", "Greensie s.r.o.",
                "+420 773 492 029", "a@greensie.cz", "www.greensie.cz"]:
        assert kus in t, kus


# ---- sestavení zprávy s podpisem ---------------------------------------------
class FalesnyUcetSmtp:
    adresa = "daniel.lupinek@greensie.cz"
    jmeno_odesilatele = "Daniel Lupínek"
    podpis = ""


class FalesnyUser:
    jmeno = "Daniel Lupínek"
    id = 1


def _sestav(profil=None, telo="Dobrý den,\nposílám nabídku.", prilohy=None, ucet=None):
    from app.crm.email_smtp import sestav_zpravu

    return sestav_zpravu(
        ucet or FalesnyUcetSmtp(), FalesnyUser(), ["zakaznik@firma.cz"],
        "Nabídka", telo, profil=profil, prilohy=prilohy,
    )


def test_zprava_s_podpisem_je_multipart_text_i_html():
    """Klient bez HTML musí dostat text, ne prázdnou zprávu."""
    msg = _sestav(FalesnyProfil(funkce="Jednatel"))
    assert msg.get_content_type() == "multipart/alternative"
    typy = [c.get_content_type() for c in msg.walk()]
    assert "text/plain" in typy and "text/html" in typy

    html = msg.get_body(preferencelist=("html",)).get_content()
    text = msg.get_body(preferencelist=("plain",)).get_content()
    assert "tel:+420773492029" in html
    assert "posílám nabídku." in text
    assert "Jednatel" in text and "Jednatel" in html


def test_priloha_nerozbije_html_cast():
    """S přílohou se struktura mění na multipart/mixed – HTML musí zůstat."""
    msg = _sestav(
        FalesnyProfil(),
        prilohy=[{"nazev": "n.pdf", "mime": "application/pdf", "obsah": b"%PDF-1.4"}],
    )
    assert msg.get_content_type() == "multipart/mixed"
    assert msg.get_body(preferencelist=("html",)) is not None
    assert "application/pdf" in [c.get_content_type() for c in msg.walk()]


def test_bez_profilu_zustava_prosty_text():
    """Kdo profil nevyplnil, dostane starý textový podpis schránky."""
    class UcetSPodpisem(FalesnyUcetSmtp):
        podpis = "Daniel\nGreensie s.r.o."

    msg = _sestav(profil=None, ucet=UcetSPodpisem())
    assert msg.get_content_type() == "text/plain"
    assert "Greensie s.r.o." in msg.get_content()


def test_vypnuty_podpis_negeneruje_html():
    msg = _sestav(FalesnyProfil(podpis_zapnuty=False))
    assert msg.get_content_type() == "text/plain"


def test_napsany_text_se_v_html_escapuje():
    """Do HTML části nesmí propadnout syrové značky z napsaného textu."""
    msg = _sestav(FalesnyProfil(), telo="<script>zlo()</script> a <b>tučně</b>")
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # Text zůstane čitelný v textové části tak, jak ho člověk napsal.
    assert "<script>zlo()</script>" in msg.get_body(preferencelist=("plain",)).get_content()


def test_zalomeni_radku_se_prevede_na_br():
    msg = _sestav(FalesnyProfil(), telo="prvni\ndruhy")
    html = msg.get_body(preferencelist=("html",)).get_content()
    assert "prvni<br>druhy" in html


# ============================================================================
# Čištění HTML z formátovacího editoru (CRM-33)
#
# Tělo zprávy se posílá jako HTML, takže do něj propadá všechno, co člověk
# vloží z Wordu, z webu nebo z jiného mailu. Čistí se na serveru, protože
# prohlížeči se věřit nedá — požadavek jde přes HTTP.
# ============================================================================
from app.crm import email_html


@pytest.mark.parametrize(
    "vstup,nesmi_obsahovat",
    [
        ("<p>Ahoj</p><script>zlo()</script>", "zlo()"),
        ('<img src="x" onerror="zlo()">', "onerror"),
        ('<a href="javascript:zlo()">klik</a>', "javascript"),
        ('<a href="java\nscript:zlo()">klik</a>', "script:"),
        ('<div style="background:url(http://zlo.cz/x)">t</div>', "url("),
        ("<style>p{color:red}</style><p>t</p>", "color:red"),
        ("<iframe src='https://zlo.cz'></iframe><p>t</p>", "iframe"),
    ],
)
def test_cistic_zahodi_nebezpecne(vstup, nesmi_obsahovat):
    assert nesmi_obsahovat not in email_html.vycisti(vstup)


def test_cistic_zachova_formatovani():
    """Co editor umí, musí projít – jinak by formátování mizelo při odeslání."""
    vstup = (
        '<p><b>tučně</b> <i>kurzíva</i> <u>podtrženo</u></p>'
        '<ul><li>odrážka</li></ul><ol><li>číslo</li></ol>'
        '<p style="text-align:center"><span style="color:#ff0000">červeně</span></p>'
    )
    v = email_html.vycisti(vstup)
    for kus in ["<b>", "<i>", "<u>", "<ul>", "<ol>", "<li>", "text-align:center", "color:#ff0000"]:
        assert kus in v, kus


def test_cistic_vyhodi_wordovsky_balast():
    vstup = '<!--[if mso]><p>x</p><![endif]--><o:p></o:p><p style="mso-x:1;color:blue">text</p>'
    v = email_html.vycisti(vstup)
    assert "mso" not in v
    assert "o:p" not in v
    assert "color:blue" in v and "text" in v


def test_cistic_doplni_bezpecny_odkaz():
    v = email_html.vycisti('<a href="https://greensie.cz">web</a>')
    assert 'href="https://greensie.cz"' in v
    assert 'rel="noopener noreferrer"' in v and 'target="_blank"' in v


def test_cistic_uzavre_rozbite_znacky():
    """Word a vkládání z webu produkují nedovřené značky běžně."""
    v = email_html.vycisti("<b>tučné <i>kurzíva</b> konec")
    assert v.count("<b>") == v.count("</b>")
    assert v.count("<i>") == v.count("</i>")


def test_prevod_na_text_zachova_strukturu():
    t = email_html.na_text(
        "<p>Dobrý den,</p><ul><li>první</li><li>druhá</li></ul><p>Konec</p>"
    )
    assert "Dobrý den," in t and "- první" in t and "- druhá" in t and "Konec" in t
    assert "<" not in t


def test_prevod_na_text_doplni_adresu_odkazu():
    """V textové verzi by jinak odkaz zmizel a zbyl by jen popisek."""
    t = email_html.na_text('<a href="https://greensie.cz">náš web</a>')
    assert "náš web" in t and "https://greensie.cz" in t
    # U mailto stejného jako popisek se adresa neopakuje.
    assert email_html.na_text('<a href="mailto:a@b.cz">a@b.cz</a>') == "a@b.cz"


@pytest.mark.parametrize(
    "html,prazdne",
    [("<p><br></p>", True), ("<div></div>", True), ("", True),
     ("<p>&nbsp;</p>", True), ("<p>text</p>", False), ("<ul><li>x</li></ul>", False)],
)
def test_prazdne_telo_se_pozna(html, prazdne):
    """`<p><br></p>` z prázdného editoru není obsah."""
    assert email_html.je_prazdne(html) is prazdne


def test_zprava_z_editoru_zachova_formatovani_a_vycisti_script():
    """Celý řetěz: HTML z editoru → sestavená zpráva."""
    msg = _sestav(
        FalesnyProfil(),
        telo="",
    )
    from app.crm.email_smtp import sestav_zpravu

    msg = sestav_zpravu(
        FalesnyUcetSmtp(), FalesnyUser(), ["a@b.cz"], "P", "",
        profil=FalesnyProfil(),
        telo_html="<p>Dobrý den,</p><ul><li><b>první</b></li></ul><script>zlo()</script>",
    )
    html = msg.get_body(preferencelist=("html",)).get_content()
    text = msg.get_body(preferencelist=("plain",)).get_content()
    assert "<ul>" in html and "<b>" in html
    assert "zlo()" not in html
    # Textová varianta se odvodí z HTML, takže obsah nezmizí.
    assert "Dobrý den," in text and "- první" in text


# ============================================================================
# Párování pošty na záznamy CRM („rejnetování")
# ============================================================================
def test_adresy_ze_zpravy_maji_role():
    from app.crm import adresar

    class Z:
        od_adresa = "jan@firma.cz"
        komu = [{"adresa": "dan@greensie.cz"}]
        kopie = [{"adresa": "sef@firma.cz"}]

    adresy = adresar.adresy_ze_zpravy(Z())
    assert adresy[0] == {"adresa": "jan@firma.cz", "role": "od"}
    role = {a["adresa"]: a["role"] for a in adresy}
    assert role["dan@greensie.cz"] == "komu"
    assert role["sef@firma.cz"] == "kopie"


def test_verejne_domeny_neparuji_firmu():
    """Podle `seznam.cz` se firma určit nedá – přiřadilo by to náhodně."""
    from app.crm.adresar import VEREJNE_DOMENY

    for d in ["seznam.cz", "gmail.com", "email.cz", "centrum.cz", "outlook.com"]:
        assert d in VEREJNE_DOMENY


# ============================================================================
# Ruční párování zpráv na klienta (jednotlivě i hromadně)
#
# Automatika spáruje jen adresy, které v CRM jsou. Zbytek — nová firma, člověk
# píšící ze soukromé adresy, přeposlaná poptávka — musí připojit člověk, a to
# i po desítkách zpráv naráz.
# ============================================================================
def test_schema_hromadne_vazby_ma_vychozi_hodnoty():
    from app.crm.schemas import EmailHromadnaVazbaVstup

    v = EmailHromadnaVazbaVstup(ids=[1, 2, 3])
    assert v.zakaznik_id is None and v.pripad_id is None
    # Výchozí `odpojit=False` je důležité: překlep v požadavku nesmí omylem
    # odpojit zprávy z karet.
    assert v.odpojit is False


def test_schema_hromadne_vazby_umi_odpojeni():
    from app.crm.schemas import EmailHromadnaVazbaVstup

    v = EmailHromadnaVazbaVstup(ids=[5], odpojit=True)
    assert v.odpojit is True and v.zakaznik_id is None


def test_vazba_ma_zdroj_a_priznak_skryti():
    """`zdroj="rucne"` chrání ruční rozhodnutí před automatikou a `skryta`
    je důvod, proč se odpojení neřeší smazáním."""
    from app.crm.models import CrmEmailVazba

    sloupce = {c.name for c in CrmEmailVazba.__table__.columns}
    assert {"zdroj", "skryta", "zakaznik_id", "pripad_id", "kontakt_id"} <= sloupce
    assert CrmEmailVazba.__table__.c.zdroj.default.arg == "auto"
    assert CrmEmailVazba.__table__.c.skryta.default.arg is False
