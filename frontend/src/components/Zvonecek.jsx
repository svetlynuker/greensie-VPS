import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Ikona from "./Ikona";
import { crmNotifikace, crmNotifikacePrecteno } from "../api";

/**
 * Zvoneček s notifikacemi (CRM-10).
 *
 * Proč vlastní kanál vedle e-mailu: e-mail si člověk odklikne a ztratí se
 * v poště. Tohle zůstane, dokud to nepřečte, a dá se dohledat zpětně.
 *
 * ---- Proč se ptá jednou za minutu, a ne přes websocket ----
 * Osm lidí a pár událostí denně. Jeden levný dotaz za minutu je řádově míň
 * práce (na serveru i na údržbě) než držet spojení, a zpoždění do minuty
 * u „někdo ti přiřadil případ" nikomu nevadí. Dotaz běží jen když je záložka
 * vidět — jinak by appka otevřená přes noc poslala 500 zbytečných dotazů.
 */
const INTERVAL_MS = 60_000;

function fmtKdy(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const minut = Math.round((Date.now() - d.getTime()) / 60000);
  if (minut < 1) return "teď";
  if (minut < 60) return `před ${minut} min`;
  const hodin = Math.round(minut / 60);
  if (hodin < 24) return `před ${hodin} h`;
  return d.toLocaleDateString("cs-CZ");
}

export default function Zvonecek() {
  const navigate = useNavigate();
  const [souhrn, setSouhrn] = useState({ neprectenych: 0, zaznamy: [] });
  const [otevreno, setOtevreno] = useState(false);
  const obal = useRef(null);

  const nacti = useCallback(() => {
    crmNotifikace()
      .then(setSouhrn)
      // Zvoneček je doplněk — když se nenačte, nesmí to nikde vyskočit.
      .catch(() => {});
  }, []);

  useEffect(() => {
    nacti();
    const t = setInterval(() => {
      if (document.visibilityState === "visible") nacti();
    }, INTERVAL_MS);
    return () => clearInterval(t);
  }, [nacti]);

  // Zavření kliknutím vedle. Bez toho by panel zůstal viset přes obsah.
  useEffect(() => {
    if (!otevreno) return undefined;
    function mimo(e) {
      if (obal.current && !obal.current.contains(e.target)) setOtevreno(false);
    }
    document.addEventListener("mousedown", mimo);
    return () => document.removeEventListener("mousedown", mimo);
  }, [otevreno]);

  async function otevri(n) {
    setOtevreno(false);
    if (!n.precteno) {
      await crmNotifikacePrecteno([n.id]).catch(() => {});
      nacti();
    }
    if (n.cesta) navigate(n.cesta);
  }

  async function precistVse() {
    await crmNotifikacePrecteno().catch(() => {});
    nacti();
  }

  const pocet = souhrn.neprectenych || 0;

  return (
    <div className="nt-obal" ref={obal}>
      <button
        className="gs-icon-btn nt-tlacitko"
        title={pocet ? `${pocet} nepřečtených notifikací` : "Notifikace"}
        aria-label="Notifikace"
        onClick={() => setOtevreno((s) => !s)}
      >
        <Ikona jmeno="zvonecek" velikost={16} />
        {pocet > 0 && <span className="nt-znacka">{pocet > 9 ? "9+" : pocet}</span>}
      </button>

      {otevreno && (
        <div className="nt-panel">
          <div className="nt-hlava">
            <b>Notifikace</b>
            <span className="crm-mezera" />
            {pocet > 0 && (
              <button className="nt-precist" onClick={precistVse}>
                Označit vše za přečtené
              </button>
            )}
          </div>

          {souhrn.zaznamy.length === 0 ? (
            <p className="nt-prazdno">
              Zatím nic. Co sem chodí, si nastavíš v <b>Nastavení → Notifikace</b>.
            </p>
          ) : (
            <ul className="nt-seznam">
              {souhrn.zaznamy.map((n) => (
                <li key={n.id}>
                  <button
                    className={`nt-radek ${n.precteno ? "" : "neprectene"}`}
                    onClick={() => otevri(n)}
                  >
                    <span className="nt-predmet">{n.predmet}</span>
                    {n.text && <span className="nt-text">{n.text}</span>}
                    <span className="nt-kdy">{fmtKdy(n.vytvoreno_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
