import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import HistorieZmen from "../components/HistorieZmen";
import Spendlik from "../components/Spendlik";
import Aktivity from "../components/Aktivity";
import DuvodProhry from "../components/DuvodProhry";
import PripadFormular from "../components/PripadFormular";
import PripadNabidky from "../components/PripadNabidky";
import PripadRealizace from "../components/PripadRealizace";
import EmailOkno from "../components/EmailOkno";
import EmailHistorie from "../components/EmailHistorie";
import RychleAkce from "../components/RychleAkce";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import VlastniPoleVypis from "../components/VlastniPoleVypis";
import DiskSlozka from "../components/DiskSlozka";
import OdbernaMistaPanel from "../components/OdbernaMistaPanel";
import {
  crmKategorie,
  crmPripadDetail,
  crmPripadHistorie,
  crmPripadSmaz,
  crmPripadStav,
  crmStavy,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, nazvyKategorii } from "../crm";
import "../styles/crm.css";
import "../styles/rychleAkce.css";

const ZALOZKY = [
  { klic: "prehled", nazev: "Přehled" },
  { klic: "nabidky", nazev: "Nabídky" },
  { klic: "realizace", nazev: "Objednávky a projekty" },
  { klic: "aktivity", nazev: "Aktivity a úkoly" },
  { klic: "historie", nazev: "Historie stavů" },
];

/**
 * Karta obchodního případu – odtud se zakládají nabídky a posouvá stav.
 *
 * „Vytvořit nabídku": když má případ jedinou kategorii, jde se přímo do jejího
 * výpočtu. Když má víc nebo žádnou, appka se zeptá – přesně jak si to Dan přál.
 */
export default function ObchodniPripadDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [p, setP] = useState(null);
  const [stavy, setStavy] = useState([]);
  // Kategorie případu jsou konfigurovatelné (CRM-03) – tady se z nich jen
  // překládá klíč na název a nabízí se v tipu u prázdné kategorie.
  const [kategorie, setKategorie] = useState([]);
  const [historie, setHistorie] = useState([]);
  const [zalozka, setZalozka] = useState("prehled");
  const [upravuje, setUpravuje] = useState(false);
  // Odeslání e-mailu z appky (CRM-10) – zapíše se k případu jako aktivita.
  const [posilaEmail, setPosilaEmail] = useState(false);
  const [prohra, setProhra] = useState(null);
  const [spravaPoli, setSpravaPoli] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nactiZnovu = useCallback(async () => {
    const [detail, h] = await Promise.all([crmPripadDetail(id), crmPripadHistorie(id)]);
    setP(detail);
    setHistorie(h);
  }, [id]);

  useEffect(() => {
    crmKategorie()
      .then(setKategorie)
      .catch(() => setKategorie([]));
  }, []);

  useEffect(() => {
    Promise.all([nactiMe(), crmPripadDetail(id), crmStavy("op"), crmPripadHistorie(id)])
      .then(([m, detail, s, h]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("obchodni_pripady")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setP(detail);
        setStavy(s);
        setHistorie(h);
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (msg.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(msg);
        }
      });
  }, [id, navigate]);

  async function zmenStav(klic) {
    const stav = stavy.find((s) => s.klic === klic);
    if (stav?.druh === "prohra") {
      setProhra(klic);
      return;
    }
    setChyba(null);
    try {
      setP(await crmPripadStav(id, klic));
      await nactiZnovu();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function potvrdProhru(duvod) {
    const klic = prohra;
    setProhra(null);
    try {
      setP(await crmPripadStav(id, klic, duvod));
      await nactiZnovu();
    } catch (e) {
      setChyba(e.message);
    }
  }

  /**
   * „+ Vytvořit nabídku" jen přepne na záložku Nabídky – zakládání i výpočet
   * se dějí tam, na kartě případu. Dřív to vodilo do nabídkovače; OZ ale nemá
   * odcházet z případu, aby nahrál fakturu a spustil výpočet.
   */
  function novaNabidka() {
    setZalozka("nabidky");
  }

  async function smaz() {
    if (!window.confirm(`Opravdu smazat případ ${p.cislo}? Nelze vzít zpět.`)) return;
    try {
      await crmPripadSmaz(id);
      navigate("/pripady");
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !p) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !p) return null;

  const stav = stavy.find((s) => s.klic === p.stav);

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky ra-misto">
        <Link to="/pripady" className="crm-zpet">
          ← Zpět na Obchodní případy
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>
              <Spendlik entita="op" zaznamId={p.id} />
              {p.cislo}
              {p.nazev ? ` · ${p.nazev}` : ""}
            </h1>
            <div className="crm-karta-radek">
              <Link to={`/zakaznici/detail/${p.zakaznik_id}`} className="crm-odkaz">
                {p.zakaznik_nazev}
              </Link>
              {p.kategorie?.length ? ` · ${nazvyKategorii(p.kategorie, kategorie)}` : " · bez kategorie"}
              {p.vlastnik_jmeno ? ` · ${p.vlastnik_jmeno}` : ""}
              {p.raynet_code ? ` · Raynet ${p.raynet_code}` : ""}
            </div>
          </div>
          <span className="crm-mezera" />
          {/* Stav se dá přehodit i tady, ne jen přetažením v kanbanu. */}
          <select
            className="crm-pole crm-pole-uzke"
            value={p.stav}
            onChange={(e) => zmenStav(e.target.value)}
            aria-label="Stav případu"
          >
            {stavy.map((s) => (
              <option key={s.klic} value={s.klic}>
                {s.nazev}
              </option>
            ))}
          </select>
          <button className="fm-btn" onClick={() => setPosilaEmail(true)}>
            ✉ Poslat e-mail
          </button>
          <button className="fm-btn" onClick={() => setUpravuje(true)}>
            Upravit
          </button>
          <button className="fm-btn fm-primary" onClick={novaNabidka}>
            + Vytvořit nabídku
          </button>
        </div>

        <div className="crm-zalozky">
          {ZALOZKY.map((zl) => (
            <button
              key={zl.klic}
              className={`crm-zalozka ${zalozka === zl.klic ? "aktivni" : ""}`}
              onClick={() => setZalozka(zl.klic)}
            >
              {zl.nazev}
              {zl.klic === "nabidky" && p.nabidky?.length ? ` (${p.nabidky.length})` : ""}
            </button>
          ))}
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zalozka === "prehled" && (
          <div className="crm-dva-sloupce">
            <div className="fm-card crm-blok">
              <h3>Případ</h3>
              <dl className="crm-udaje">
                <dt>Číslo</dt>
                <dd>{p.cislo}</dd>
                <dt>Zákazník</dt>
                <dd>{p.zakaznik_nazev}</dd>
                <dt>Kategorie</dt>
                <dd>
                  {p.kategorie?.length ? (
                    nazvyKategorii(p.kategorie, kategorie)
                  ) : (
                    <span className="crm-tise">
                      nevyplněno – appka se zeptá při vytváření nabídky
                    </span>
                  )}
                </dd>
                <dt>Odběrné místo</dt>
                <dd>
                  {p.odberne_misto_nazev || (
                    <span className="crm-tise">
                      nevybráno – vyber ho v kartě Odběrná místa, nabídka si z něj vezme
                      diagram i sazby
                    </span>
                  )}
                </dd>
                <dt>Stav</dt>
                <dd>{stav?.nazev || p.stav}</dd>
                <dt>Hodnota</dt>
                <dd>{fmtKc(p.hodnota_kc)}</dd>
                <dt>Pravděpodobnost</dt>
                <dd>{p.pravdepodobnost != null ? `${p.pravdepodobnost} %` : "—"}</dd>
                <dt>Předpokládané uzavření</dt>
                <dd>{fmtDatum(p.predpokladane_uzavreni) || "—"}</dd>
                {p.uzavreno_at && (
                  <>
                    <dt>Uzavřeno</dt>
                    <dd>{fmtDatum(p.uzavreno_at)}</dd>
                  </>
                )}
                {p.duvod_prohry && (
                  <>
                    <dt>Důvod prohry</dt>
                    <dd>{p.duvod_prohry}</dd>
                  </>
                )}
                {p.raynet_code && (
                  <>
                    <dt>Raynetí číslo</dt>
                    <dd>
                      {p.raynet_code}
                      <span className="crm-tise"> (most na složku dokumentů na Disku)</span>
                    </dd>
                  </>
                )}
                <dt>Vytvořeno</dt>
                <dd>{fmtDatum(p.vytvoreno_at)}</dd>
              </dl>
              {p.popis && <p className="crm-poznamka">{p.popis}</p>}
              <div className="crm-blok-pata">
                <span className="crm-mezera" />
                <button className="fm-btn crm-btn-smazat" onClick={smaz}>
                  Smazat případ
                </button>
              </div>
            </div>

            <div className="crm-sloupec-bloky">
              <VlastniPoleVypis
                pole={p.vlastni_pole}
                hodnoty={p.extra}
                muzeSpravovat={me.prava?.includes("crm_nastaveni")}
                onSprava={() => setSpravaPoli(true)}
              />
              {/* CRM-12: sbalené, načítá se až po rozbalení. */}
              <HistorieZmen entita="op" zaznamId={p.id} />
              <OdbernaMistaPanel
                entita="op"
                zaznamId={p.id}
                onZmenaVazby={nactiZnovu}
                muzeSpravovatPole={me.prava?.includes("crm_nastaveni")}
              />
              <div className="fm-card crm-blok">
                <DiskSlozka entita="op" zaznamId={p.id} popisZaznamu="případu" />
              </div>
              <div className="fm-card crm-blok">
              <h3>Co dál</h3>
              <p className="crm-tise">
                Z případu vede celá cesta zakázky. Na záložce <b>Nabídky</b> nahraješ podklady
                a spustíš výpočet – přímo tady, do nabídkovače chodit nemusíš. Zákazníka
                i adresu si nabídka vezme z karty klienta, nic se neopisuje.
              </p>
              <ul className="crm-kroky">
                <li>
                  <b>Nabídka</b> – podklady i výpočet jsou na záložce Nabídky, výsledek zůstává
                  navázaný na tento případ.
                </li>
                <li>
                  <b>Objednávka</b> – zakládá se z přijaté nabídky na záložce
                  „Objednávky a projekty".
                </li>
                <li>
                  <b>Projekt</b> – vzniká z objednávky, číslo převezme po případu a kroky
                  se rozbalí ze šablony.
                </li>
              </ul>
              {p.kategorie?.length === 0 && (
                <p className="crm-tise">
                  Tip: doplň kategorii (
                  {kategorie
                    .filter((k) => k.aktivni)
                    .map((k) => k.nazev)
                    .join(" / ")}
                  ) – na záložce Nabídky se pak nabídne jako první volba.
                </p>
              )}
              </div>
            </div>
          </div>
        )}

        {zalozka === "nabidky" && (
          <PripadNabidky
            pripad={p}
            onZmena={nactiZnovu}
            muzeExportovat={me.prava?.includes("export")}
          />
        )}

        {zalozka === "realizace" && (
          <PripadRealizace pripad={p} me={me} onZmena={nactiZnovu} />
        )}

        {zalozka === "aktivity" && (
          <>
            <Aktivity entita="op" zaznamId={p.id} />
            {/* Pošta spárovaná na případ i na jeho firmu (viz backend:
                u případu se berou i zprávy firmy bez konkrétního případu,
                jinak by karta zela prázdnotou). */}
            <EmailHistorie entita="op" zaznamId={p.id} />
          </>
        )}

        {zalozka === "historie" && (
          <div className="fm-card crm-blok">
            <h3>Dráha případu fázemi</h3>
            {historie.length === 0 ? (
              <p className="crm-tise">Zatím žádná změna stavu.</p>
            ) : (
              <ul className="crm-casova-osa">
                {historie.map((h) => (
                  <li key={h.id} className="crm-osa-radek">
                    <span className="crm-osa-ikona" aria-hidden="true">
                      →
                    </span>
                    <div className="crm-osa-telo">
                      <div className="crm-osa-text">
                        {h.ze_stavu ? `${h.ze_stavu} → ${h.do_stavu}` : `Založeno v ${h.do_stavu}`}
                      </div>
                      <div className="crm-osa-meta">
                        {h.zmenil_jmeno || "—"} · {fmtDatum(h.zmeneno_at)}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      {upravuje && (
        <PripadFormular
          pripad={p}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setUpravuje(false)}
          onHotovo={(novy) => {
            setP(novy);
            setUpravuje(false);
          }}
        />
      )}

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="op"
          nazevObrazovky="Obchodní případy"
          onZavri={() => setSpravaPoli(false)}
          onZmena={nactiZnovu}
        />
      )}

      {posilaEmail && (
        <EmailOkno
          entita="op"
          zaznamId={p.id}
          nazev={`${p.cislo}${p.nazev ? ` · ${p.nazev}` : ""}`}
          onZavri={() => setPosilaEmail(false)}
          // Po odeslání se detail přenačte, aby se e-mail objevil v aktivitách.
          onOdeslano={nactiZnovu}
        />
      )}

      {prohra && <DuvodProhry onZavri={() => setProhra(null)} onPotvrd={potvrdProhru} />}

      {/* U případu je nabídka nejužší a nejkonkrétnější: tady se ví i firma,
          i zakázka, takže dává smysl počítat nabídku a psát zákazníkovi. */}
      <RychleAkce
        titulek={`Rychlé akce · ${p.cislo}`}
        akce={[
          {
            klic: "nabidka",
            znak: "⚡",
            nazev: "Vytvořit nabídku",
            popis: "Otevřít výpočet podle kategorie",
            onClick: novaNabidka,
          },
          {
            klic: "email",
            znak: "✉",
            nazev: "Poslat e-mail",
            popis: "Zapíše se k případu jako aktivita",
            onClick: () => setPosilaEmail(true),
          },
          {
            klic: "aktivita",
            znak: "🗒",
            nazev: "Aktivita nebo úkol",
            popis: "Telefonát, schůzka, poznámka",
            onClick: () => setZalozka("aktivity"),
          },
          {
            klic: "realizace",
            znak: "🔧",
            nazev: "Objednávky a projekty",
            popis: "Přejít na realizaci zakázky",
            onClick: () => setZalozka("realizace"),
          },
          {
            klic: "upravit",
            znak: "✎",
            nazev: "Upravit případ",
            popis: "Název, kategorie, vlastník",
            onClick: () => setUpravuje(true),
          },
        ]}
      />
    </Layout>
  );
}
