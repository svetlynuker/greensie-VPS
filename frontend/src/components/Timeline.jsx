import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { crmTimeline } from "../api";
import { DRUHY_AKTIVITY, fmtDatum } from "../crm";

/**
 * Timeline zákazníka (CRM-18) — celý děj na jedné chronologické ose.
 *
 * Dnes je historie rozsypaná do záložek: aktivity zvlášť, případy zvlášť,
 * nabídky zvlášť, změny stavů ještě jinde. Kdo chce vědět „co se u toho klienta
 * dělo", musí si to skládat v hlavě.
 *
 * Události se seskupují po dnech, ne po jedné — u zákazníka se během dne stane
 * několik věcí a datum u každého řádku by byl šum.
 */

const ZNAKY = {
  pripad: "📁",
  nabidka: "📄",
  objednavka: "🧾",
  projekt: "🔧",
  stav: "→",
};

function znak(druh) {
  return ZNAKY[druh] || DRUHY_AKTIVITY.find((d) => d.klic === druh)?.znak || "•";
}

export default function Timeline({ zakaznikId }) {
  const [udalosti, setUdalosti] = useState(null);
  const [chyba, setChyba] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    let zruseno = false;
    crmTimeline(zakaznikId)
      .then((d) => !zruseno && setUdalosti(d.udalosti || []))
      .catch((e) => !zruseno && setChyba(e.message));
    return () => {
      zruseno = true;
    };
  }, [zakaznikId]);

  if (chyba) return <div className="crm-chyba">{chyba}</div>;
  if (udalosti === null) return <p className="crm-tise">Skládám osu…</p>;
  if (!udalosti.length) {
    return (
      <p className="crm-tise">
        U tohohle zákazníka se zatím nic nestalo. Jak přidáš aktivitu nebo případ,
        objeví se to tady.
      </p>
    );
  }

  // Seskupení po dnech se zachovaným pořadím (události přicházejí seřazené).
  const dny = [];
  for (const u of udalosti) {
    const den = (u.kdy || "").slice(0, 10);
    const posledni = dny[dny.length - 1];
    if (posledni && posledni.den === den) posledni.polozky.push(u);
    else dny.push({ den, polozky: [u] });
  }

  return (
    <div className="tl">
      {dny.map((d) => (
        <div className="tl-den" key={d.den}>
          <div className="tl-datum">{fmtDatum(d.den) || "bez data"}</div>
          <ul className="tl-seznam">
            {d.polozky.map((u, i) => (
              <li key={`${d.den}-${i}`}>
                <button
                  className="tl-radek"
                  onClick={() => u.cesta && navigate(u.cesta)}
                  disabled={!u.cesta}
                >
                  <span className="tl-znak" aria-hidden="true">
                    {znak(u.druh)}
                  </span>
                  <span className="tl-telo">
                    <span className="tl-titulek">{u.titulek}</span>
                    {(u.popis || u.kdo) && (
                      <span className="tl-popis">
                        {u.popis}
                        {u.popis && u.kdo ? " · " : ""}
                        {u.kdo}
                      </span>
                    )}
                  </span>
                  <span className="tl-cas">{(u.kdy || "").slice(11, 16)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
