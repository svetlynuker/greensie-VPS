import { useEffect, useState } from "react";
import { crmPosliEmail, crmSablonaTextuPouzij, crmSablonyTextu } from "../api";

/**
 * Odeslání e-mailu zákazníkovi z appky (CRM-10) se šablonami (CRM-32).
 *
 * Proč se maily posílají odsud a ne z Outlooku: odeslaný e-mail se **zapíše
 * k záznamu jako aktivita**, takže je pak vidět v timeline, co už zákazníkovi
 * odešlo. To je celý důvod existence tohohle okna.
 *
 * Šablona je **předvyplnění, ne uzamčení** — po vložení se text normálně
 * edituje. Vkládá se do prázdného formuláře bez ptaní, ale přes rozepsaný text
 * až po potvrzení: přepsat někomu deset vět rozepsané nabídky jedním kliknutím
 * do špatného řádku by bylo horší než dotaz navíc.
 */
export default function EmailOkno({ entita, zaznamId, komu: vychoziKomu = "", nazev, onZavri, onOdeslano }) {
  const [komu, setKomu] = useState(vychoziKomu);
  const [predmet, setPredmet] = useState("");
  const [telo, setTelo] = useState("");
  const [sablony, setSablony] = useState([]);
  const [odesila, setOdesila] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmSablonyTextu({ druh: "email", entita })
      .then((d) => setSablony(d.sablony || []))
      // Bez šablon se dá e-mail napsat ručně – nesmí to okno zablokovat.
      .catch(() => setSablony([]));
  }, [entita]);

  async function vlozSablonu(id) {
    if (!id) return;
    const rozepsano = predmet.trim() || telo.trim();
    if (rozepsano && !window.confirm("Vložením šablony se přepíše rozepsaný text. Pokračovat?")) {
      return;
    }
    try {
      const s = await crmSablonaTextuPouzij(id, { entita, zaznamId });
      setPredmet(s.predmet || "");
      setTelo(s.telo || "");
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function odesli() {
    setOdesila(true);
    setChyba(null);
    try {
      await crmPosliEmail({ komu, predmet, telo, entita, zaznamId });
      if (onOdeslano) onOdeslano();
      onZavri();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setOdesila(false);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Poslat e-mail{nazev ? ` — ${nazev}` : ""}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          {sablony.length > 0 && (
            <div className="crm-pole-radek">
              <label className="crm-label" htmlFor="em-sablona">
                Šablona
              </label>
              <select
                id="em-sablona"
                className="crm-pole"
                defaultValue=""
                onChange={(e) => {
                  vlozSablonu(Number(e.target.value));
                  e.target.value = "";
                }}
              >
                <option value="">— vybrat a vložit —</option>
                {sablony.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nazev}
                  </option>
                ))}
              </select>
              <p className="crm-tise crm-napoveda">
                Vložený text se dá dál upravovat. Údaje jako název firmy nebo číslo případu
                se doplní samy.
              </p>
            </div>
          )}

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="em-komu">
              Komu *
            </label>
            <input
              id="em-komu"
              className="crm-pole"
              type="email"
              value={komu}
              onChange={(e) => setKomu(e.target.value)}
              placeholder="jmeno@firma.cz"
            />
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="em-predmet">
              Předmět *
            </label>
            <input
              id="em-predmet"
              className="crm-pole"
              value={predmet}
              onChange={(e) => setPredmet(e.target.value)}
            />
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="em-telo">
              Text *
            </label>
            <textarea
              id="em-telo"
              className="crm-pole"
              rows={12}
              value={telo}
              onChange={(e) => setTelo(e.target.value)}
            />
            <p className="crm-tise crm-napoveda">
              Podpis se doplní automaticky. E-mail odchází z firemní schránky a uloží se
              k záznamu jako aktivita.
            </p>
          </div>

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={odesli}
            disabled={odesila || !komu.trim() || !predmet.trim() || !telo.trim()}
          >
            {odesila ? "Odesílám…" : "Odeslat"}
          </button>
        </div>
      </div>
    </div>
  );
}
