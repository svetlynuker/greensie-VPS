import { useState } from "react";
import { DUVODY_PROHRY } from "../crm";

/**
 * Dotaz na důvod prohry při přesunu případu do prohraného stavu.
 *
 * Nabídnutý seznam je tu proto, aby se z důvodů dala udělat statistika – volný
 * text je taky možný, ale jako doplněk, ne jako jediná varianta. Backend prohru
 * bez důvodu odmítne, takže tenhle dialog nelze obejít.
 */
export default function DuvodProhry({ onZavri, onPotvrd }) {
  const [volba, setVolba] = useState(DUVODY_PROHRY[0]);
  const [vlastni, setVlastni] = useState("");

  const jeJiny = volba === "Jiný";
  const vysledek = jeJiny ? vlastni.trim() : volba;

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno crm-okno-uzke" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Proč jsme případ prohráli?</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Bez důvodu prohry nemá statistika pipeline smysl a za měsíc už si to nikdo
            nevybaví. Vyber nejbližší důvod, případně dopiš vlastní.
          </p>
          <div className="crm-volby crm-volby-svisle">
            {DUVODY_PROHRY.map((d) => (
              <label key={d} className="crm-zaskrtavaci">
                <input
                  type="radio"
                  name="duvod"
                  checked={volba === d}
                  onChange={() => setVolba(d)}
                />
                {d}
              </label>
            ))}
          </div>
          {jeJiny && (
            <input
              className="crm-pole"
              value={vlastni}
              onChange={(e) => setVlastni(e.target.value)}
              placeholder="Napiš důvod"
              autoFocus
            />
          )}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={() => onPotvrd(vysledek)}
            disabled={!vysledek}
          >
            Označit jako prohrané
          </button>
        </div>
      </div>
    </div>
  );
}
