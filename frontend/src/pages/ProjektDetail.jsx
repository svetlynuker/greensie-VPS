import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Aktivity from "../components/Aktivity";
import ProjektKroky from "../components/ProjektKroky";
import VlastniPoleVypis from "../components/VlastniPoleVypis";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import {
  crmProjektDetail,
  crmProjektPouzijSablonu,
  crmProjektSmaz,
  crmProjektStav,
  crmProjektUprav,
  crmSablony,
  crmStavy,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum } from "../crm";
import "../styles/crm.css";

const ZALOZKY = [
  { klic: "kroky", nazev: "Kroky realizace" },
  { klic: "prehled", nazev: "Přehled" },
  { klic: "aktivity", nazev: "Aktivity a úkoly" },
];

/**
 * Detail projektu – kroky realizace s termíny a návaznostmi.
 *
 * Výchozí záložka jsou schválně KROKY, ne přehled: na projekt se člověk dívá
 * proto, aby věděl, co je hotové a co hoří.
 */
export default function ProjektDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [p, setP] = useState(null);
  const [stavy, setStavy] = useState([]);
  const [sablony, setSablony] = useState([]);
  const [zalozka, setZalozka] = useState("kroky");
  const [spravaPoli, setSpravaPoli] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nactiZnovu = useCallback(async () => {
    setP(await crmProjektDetail(id));
  }, [id]);

  useEffect(() => {
    Promise.all([nactiMe(), crmProjektDetail(id), crmStavy("pro"), crmSablony()])
      .then(([m, detail, s, sab]) => {
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
        setSablony(sab);
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
    try {
      setP(await crmProjektStav(id, klic));
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function pouzijSablonu(sablonaId) {
    if (!sablonaId) return;
    try {
      setP(await crmProjektPouzijSablonu(id, sablonaId));
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function ulozZahajeni(hodnota) {
    try {
      setP(
        await crmProjektUprav(id, {
          nazev: p.nazev || "",
          popis: p.popis || "",
          zahajeni: hodnota || null,
          predani: p.predani || null,
          freelo_projekt_id: p.freelo_projekt_id,
          extra: p.extra || {},
        })
      );
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz() {
    if (!window.confirm(`Smazat projekt ${p.cislo} včetně kroků?`)) return;
    try {
      await crmProjektSmaz(id);
      navigate("/projekty");
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

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <Link to="/projekty" className="crm-zpet">
          ← Zpět na Projekty
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>
              {p.cislo}
              {p.nazev ? ` · ${p.nazev}` : ""}
            </h1>
            <div className="crm-karta-radek">
              <Link to={`/pripady/detail/${p.pripad_id}`} className="crm-odkaz">
                {p.pripad_cislo}
              </Link>
              {p.zakaznik_nazev ? ` · ${p.zakaznik_nazev}` : ""}
              {p.objednavka_cislo ? ` · z objednávky ${p.objednavka_cislo}` : ""}
              {p.kroku > 0 ? ` · ${p.hotovo}/${p.kroku} kroků (${p.procent} %)` : ""}
              {p.po_terminu > 0 && (
                <span className="crm-po-terminu"> · {p.po_terminu} po termínu</span>
              )}
            </div>
          </div>
          <span className="crm-mezera" />
          <select
            className="crm-pole crm-pole-uzke"
            value={p.stav}
            onChange={(e) => zmenStav(e.target.value)}
            aria-label="Stav projektu"
          >
            {stavy.map((s) => (
              <option key={s.klic} value={s.klic}>
                {s.nazev}
              </option>
            ))}
          </select>
        </div>

        <div className="crm-zalozky">
          {ZALOZKY.map((zl) => (
            <button
              key={zl.klic}
              className={`crm-zalozka ${zalozka === zl.klic ? "aktivni" : ""}`}
              onClick={() => setZalozka(zl.klic)}
            >
              {zl.nazev}
              {zl.klic === "kroky" && p.kroku > 0 ? ` (${p.kroku})` : ""}
            </button>
          ))}
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zalozka === "kroky" && (
          <ProjektKroky
            projekt={p}
            sablony={sablony}
            onZmena={setP}
            onSablona={pouzijSablonu}
          />
        )}

        {zalozka === "prehled" && (
          <div className="crm-dva-sloupce">
            <div className="fm-card crm-blok">
              <h3>Projekt</h3>
              <dl className="crm-udaje">
                <dt>Číslo</dt>
                <dd>{p.cislo}</dd>
                <dt>Zákazník</dt>
                <dd>{p.zakaznik_nazev || "—"}</dd>
                <dt>Obchodní případ</dt>
                <dd>{p.pripad_cislo}</dd>
                <dt>Objednávka</dt>
                <dd>{p.objednavka_cislo || "—"}</dd>
                <dt>Zahájení</dt>
                <dd>
                  {/* Změna zahájení přepočítá termíny všech kroků, které nemají
                      ruční termín – v tom je hodnota návazností. */}
                  <input
                    className="crm-pole crm-pole-uzke"
                    type="date"
                    value={(p.zahajeni || "").slice(0, 10)}
                    onChange={(e) => ulozZahajeni(e.target.value)}
                  />
                </dd>
                <dt>Plánované předání</dt>
                <dd>{fmtDatum(p.predani) || "—"}</dd>
                <dt>Postup</dt>
                <dd>{p.kroku > 0 ? `${p.hotovo} z ${p.kroku} kroků (${p.procent} %)` : "—"}</dd>
                {p.freelo_projekt_id && (
                  <>
                    {/* Koexistence s Freelem – appka ho má nahradit, do té doby
                        je vidět, že jde o tentýž projekt. */}
                    <dt>Freelo projekt</dt>
                    <dd>#{p.freelo_projekt_id}</dd>
                  </>
                )}
              </dl>
              {p.popis && <p className="crm-poznamka">{p.popis}</p>}
              <div className="crm-blok-pata">
                <span className="crm-mezera" />
                <button className="fm-btn crm-btn-smazat" onClick={smaz}>
                  Smazat projekt
                </button>
              </div>
            </div>

            <VlastniPoleVypis
              pole={p.vlastni_pole}
              hodnoty={p.extra}
              muzeSpravovat={me.prava?.includes("crm_nastaveni")}
              onSprava={() => setSpravaPoli(true)}
            />
          </div>
        )}

        {zalozka === "aktivity" && <Aktivity entita="pro" zaznamId={p.id} />}
      </div>

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="pro"
          nazevObrazovky="Projekty"
          onZavri={() => setSpravaPoli(false)}
          onZmena={nactiZnovu}
        />
      )}
    </Layout>
  );
}
