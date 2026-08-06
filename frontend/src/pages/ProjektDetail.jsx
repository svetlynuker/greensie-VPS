import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import GanttProjektu from "../components/GanttProjektu";
import HistorieZmen from "../components/HistorieZmen";
import Spendlik from "../components/Spendlik";
import Aktivity from "../components/Aktivity";
import Pritomni from "../components/Pritomni";
import StavUlozeni from "../components/StavUlozeni";
import ProjektKroky from "../components/ProjektKroky";
import VlastniPoleVypis from "../components/VlastniPoleVypis";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";
import {
  crmProjektDetail,
  crmProjektPouzijSablonu,
  crmProjektSmaz,
  crmProjektStav,
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

// Pole, která se na téhle stránce ukládají sama. Je tu jen zahájení — název,
// popis a vlastní pole se z detailu projektu neupravují (mají svoje místo
// v objednávce, resp. ve správě polí) a plánované předání se jen ukazuje,
// protože ho počítají kroky. Stav projektu tu schválně NENÍ: přepíná fázi
// realizace, takže patří na vědomé kliknutí, ne na ukládání za pochodu.
const POLE = ["zahajeni"];

const NAZVY_POLI = { zahajeni: "Zahájení", predani: "Plánované předání" };

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

  const {
    hodnoty,
    zmen,
    stav: stavUlozeni,
    chyba: chybaUlozeni,
    kdy,
    pritomni,
    razitko,
    kolize,
    prepis,
    vezmiJejich,
    onFokus,
    onBlur,
  } = useZaznamAutosave({
    entita: "pro",
    id,
    zaznam: p,
    pole: POLE,
    entitaTyp: "crm_pro",
    // Přítomnost („kdo tu je“) běží od chvíle, kdy je projekt načtený — kolegu
    // má člověk vidět dřív, než sáhne na termín.
    zapnuto: Boolean(p),
  });

  // Razítko se změnilo → někdo (nebo já z jiného okna) projekt upravil,
  // natáhneme ho znovu. První razítko se jen zapamatuje, jinak by se stránka po
  // načtení obnovila zbytečně. Rozepsané pole hook nepřepíše, takže to nic
  // nesebere.
  const razitkoRef = useRef(null);
  useEffect(() => {
    if (!razitko) return;
    if (razitkoRef.current === null || razitkoRef.current === razitko) {
      razitkoRef.current = razitko;
      return;
    }
    razitkoRef.current = razitko;
    nactiZnovu().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [razitko]);

  // Po každém vlastním uložení natáhneme detail hned, nečekáme na razítko:
  // změna zahájení přepočítá termíny všech kroků bez ručního termínu a ty musí
  // být vidět okamžitě (dřív to zajišťovala odpověď na celý PUT).
  const kdyRef = useRef(null);
  useEffect(() => {
    if (!kdy || kdyRef.current === kdy) return;
    kdyRef.current = kdy;
    nactiZnovu().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kdy]);

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
              <Spendlik entita="pro" zaznamId={p.id} />
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
          {/* Kdo má projekt otevřený taky – ať je kolize vidět dřív, než
              nastane. Vedle je stav ukládání: bez tlačítka „Uložit“ nemá člověk
              jinak jak poznat, že termín došel na server. */}
          <Pritomni pritomni={pritomni} popisekPole={(f) => NAZVY_POLI[f] || f} />
          <StavUlozeni stav={stavUlozeni} chyba={chybaUlozeni} kdy={kdy} />
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
          <>
            {/* Gantt (CRM-21) nad seznamem: nejdřív „kdy to bude", pak detaily. */}
            <GanttProjektu projekt={p} />
          </>
        )}

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
                      ruční termín – v tom je hodnota návazností. Datum je hotové
                      rozhodnutí, ne rozepsaná věta, takže se ukládá bez prodlevy
                      (`ihned`). */}
                  <input
                    className="crm-pole crm-pole-uzke"
                    type="date"
                    value={hodnoty.zahajeni || ""}
                    onChange={(e) => zmen("zahajeni", e.target.value, true)}
                    onFocus={() => onFokus("zahajeni")}
                    onBlur={() => onBlur("zahajeni")}
                  />
                </dd>
                {/* Plánované předání se jen ukazuje – počítá ho poslední krok
                    realizace, takže tu není co ukládat. */}
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

              {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. */}
              {kolize && (
                <div className="crm-kolize">
                  <div>
                    <strong>{NAZVY_POLI[kolize.pole] || kolize.pole}</strong> mezitím změnil
                    {kolize.kdo ? ` ${kolize.kdo}` : " někdo jiný"} na{" "}
                    <strong>{fmtDatum(kolize.aktualni) || "prázdné"}</strong>.
                    <br />
                    Ty píšeš <strong>{fmtDatum(kolize.moje) || "prázdné"}</strong>.
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button className="fm-btn fm-primary" onClick={prepis}>
                      Přepsat mojí hodnotou
                    </button>
                    <button className="fm-btn" onClick={vezmiJejich}>
                      Nechat jejich
                    </button>
                  </div>
                </div>
              )}

              {p.popis && <p className="crm-poznamka">{p.popis}</p>}
              <div className="crm-blok-pata">
                <span className="crm-tise">Termín zahájení se ukládá sám.</span>
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
            {/* CRM-12: sbalené, načítá se až po rozbalení. */}
            <HistorieZmen entita="pro" zaznamId={p.id} />
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
