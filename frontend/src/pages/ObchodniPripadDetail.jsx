import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Aktivity from "../components/Aktivity";
import DuvodProhry from "../components/DuvodProhry";
import PripadFormular from "../components/PripadFormular";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import VlastniPoleVypis from "../components/VlastniPoleVypis";
import VolbaNabidky from "../components/VolbaNabidky";
import {
  crmPripadDetail,
  crmPripadHistorie,
  crmPripadSmaz,
  crmPripadStav,
  crmStavy,
  logout,
  nactiMe,
} from "../api";
import { KATEGORIE_OP, cilNabidky, fmtDatum, fmtKc, nazvyKategorii } from "../crm";
import "../styles/crm.css";

const ZALOZKY = [
  { klic: "prehled", nazev: "Přehled" },
  { klic: "nabidky", nazev: "Nabídky" },
  { klic: "aktivity", nazev: "Aktivity a úkoly" },
  { klic: "historie", nazev: "Historie stavů" },
];

const TYPY_NABIDKY_NAZVY = { ppa: "PPA", prodej: "Prodej", peak_shaving: "Peak shaving" };

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
  const [historie, setHistorie] = useState([]);
  const [zalozka, setZalozka] = useState("prehled");
  const [upravuje, setUpravuje] = useState(false);
  const [volbaNabidky, setVolbaNabidky] = useState(false);
  const [prohra, setProhra] = useState(null);
  const [spravaPoli, setSpravaPoli] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nactiZnovu = useCallback(async () => {
    const [detail, h] = await Promise.all([crmPripadDetail(id), crmPripadHistorie(id)]);
    setP(detail);
    setHistorie(h);
  }, [id]);

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

  function novaNabidka() {
    // Jedna kategorie → přímo do výpočtu. Jinak se zeptáme.
    const cil = cilNabidky(p.kategorie);
    if (cil) {
      setVolbaNabidky({ predvolba: cil });
    } else {
      setVolbaNabidky({ predvolba: null });
    }
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
      <div className="crm-app siroky">
        <Link to="/pripady" className="crm-zpet">
          ← Zpět na Obchodní případy
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>
              {p.cislo}
              {p.nazev ? ` · ${p.nazev}` : ""}
            </h1>
            <div className="crm-karta-radek">
              <Link to={`/zakaznici/detail/${p.zakaznik_id}`} className="crm-odkaz">
                {p.zakaznik_nazev}
              </Link>
              {p.kategorie?.length ? ` · ${nazvyKategorii(p.kategorie)}` : " · bez kategorie"}
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
                    nazvyKategorii(p.kategorie)
                  ) : (
                    <span className="crm-tise">
                      nevyplněno – appka se zeptá při vytváření nabídky
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
              <div className="fm-card crm-blok">
              <h3>Co dál</h3>
              <p className="crm-tise">
                Z případu vede celá cesta zakázky. Nabídku vytvoř tlačítkem vpravo nahoře –
                zákazníka i adresu si vezme z karty klienta, nic se neopisuje.
              </p>
              <ul className="crm-kroky">
                <li>
                  <b>Nabídka</b> – spočítá se v nabídkovači a zůstane navázaná na tento případ.
                </li>
                <li>
                  <b>Objednávka</b> – vznikne z přijaté nabídky.{" "}
                  <span className="crm-tise">(připravuje se)</span>
                </li>
                <li>
                  <b>Projekt</b> – vznikne z objednávky, číslo převezme po případu.{" "}
                  <span className="crm-tise">(připravuje se)</span>
                </li>
              </ul>
              {p.kategorie?.length === 0 && (
                <p className="crm-tise">
                  Tip: doplň kategorii ({KATEGORIE_OP.map((k) => k.nazev).join(" / ")}) a
                  nabídka se pak založí bez dalšího dotazu.
                </p>
              )}
              </div>
            </div>
          </div>
        )}

        {zalozka === "nabidky" && (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Typ</th>
                  <th>Stav</th>
                  <th className="crm-vpravo">Spočítaná řešení</th>
                  <th>Vytvořeno</th>
                </tr>
              </thead>
              <tbody>
                {(p.nabidky || []).map((n) => (
                  <tr
                    key={n.id}
                    onClick={() => navigate(`/nabidkovac/nabidka/${n.id}`)}
                    title="Otevřít nabídku v nabídkovači"
                  >
                    <td className="crm-silne">{n.cislo || `#${n.id}`}</td>
                    <td>{TYPY_NABIDKY_NAZVY[n.typ] || n.typ}</td>
                    <td>
                      <span className="crm-znacka">{n.stav}</span>
                    </td>
                    <td className="crm-vpravo">{n.pocet_reseni}</td>
                    <td>{fmtDatum(n.vytvoreno_at)}</td>
                  </tr>
                ))}
                {(p.nabidky || []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="crm-prazdno">
                      K případu zatím není nabídka. Založ ji tlačítkem „+ Vytvořit nabídku".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {zalozka === "aktivity" && <Aktivity entita="op" zaznamId={p.id} />}

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

      {volbaNabidky && (
        <VolbaNabidky
          pripad={p}
          predvolba={volbaNabidky.predvolba}
          onZavri={() => setVolbaNabidky(false)}
          onHotovo={(nabidka) => navigate(`/nabidkovac/nabidka/${nabidka.id}`)}
        />
      )}

      {prohra && <DuvodProhry onZavri={() => setProhra(null)} onPotvrd={potvrdProhru} />}
    </Layout>
  );
}
