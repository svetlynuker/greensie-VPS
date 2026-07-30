import { useState } from "react";
import { crmVytvorNabidku } from "../api";
import { KATEGORIE_OP } from "../crm";

/**
 * „Na co chceš nabídku?" – dialog při vytváření nabídky z obchodního případu.
 *
 * Když má případ jedinou kategorii, přijde sem jako `predvolba` a OZ jen
 * potvrdí (nebo změní). Když kategorie chybí nebo jich je víc, musí vybrat –
 * appka nehádá, protože z toho vzniká jiný výpočet.
 *
 * Zákazníka, adresu ani GPS tu nezadáváme: přenesou se z karty klienta na
 * backendu, aby se nic neopisovalo (a nevznikaly překlepy v dokumentu, který
 * jde zákazníkovi).
 */
export default function VolbaNabidky({ pripad, predvolba = null, onZavri, onHotovo }) {
  const [typ, setTyp] = useState(predvolba || "");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  // Kategorie případu nabízíme první; zbytek jde taky (případ se mohl posunout).
  const zKategorii = KATEGORIE_OP.filter((k) => (pripad.kategorie || []).includes(k.klic));
  const ostatni = KATEGORIE_OP.filter((k) => !(pripad.kategorie || []).includes(k.klic));

  async function vytvor() {
    if (!typ) return;
    setUklada(true);
    setChyba(null);
    try {
      onHotovo(await crmVytvorNabidku(pripad.id, typ));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno crm-okno-uzke" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Na co chceš nabídku?</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Nabídka se založí pod případem {pripad.cislo} a údaje zákazníka si vezme z karty
            klienta {pripad.zakaznik_nazev}.
          </p>

          {zKategorii.length > 0 && (
            <>
              <label className="crm-label">Podle kategorie případu</label>
              <div className="crm-volby crm-volby-svisle">
                {zKategorii.map((k) => (
                  <label key={k.klic} className="crm-zaskrtavaci">
                    <input
                      type="radio"
                      name="typ"
                      checked={typ === k.klic}
                      onChange={() => setTyp(k.klic)}
                    />
                    <span>
                      <b>{k.nazev}</b> — {k.popis}
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}

          {ostatni.length > 0 && (
            <>
              <label className="crm-label" style={{ marginTop: 12 }}>
                {zKategorii.length > 0 ? "Nebo jiný typ" : "Vyber typ nabídky"}
              </label>
              <div className="crm-volby crm-volby-svisle">
                {ostatni.map((k) => (
                  <label key={k.klic} className="crm-zaskrtavaci">
                    <input
                      type="radio"
                      name="typ"
                      checked={typ === k.klic}
                      onChange={() => setTyp(k.klic)}
                    />
                    <span>
                      <b>{k.nazev}</b> — {k.popis}
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button className="fm-btn fm-primary" onClick={vytvor} disabled={uklada || !typ}>
            {uklada ? "Zakládám…" : "Vytvořit nabídku"}
          </button>
        </div>
      </div>
    </div>
  );
}
