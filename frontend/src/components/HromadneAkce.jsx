import { useState } from "react";
import {
  crmHromadnaAktivita,
  crmHromadnyStav,
  crmHromadnyVlastnik,
} from "../api";
import { DRUHY_AKTIVITY } from "../crm";
import { isoDen } from "../datum";

/**
 * Lišta hromadných akcí nad vybranými řádky (CRM-19).
 *
 * Ukáže se, až je něco vybrané — prázdná lišta nad tabulkou by jen zabírala
 * místo a lidem by nebylo jasné, co má vybrat dřív.
 *
 * ---- Proč se u aktivit ukazuje plán --------------------------------------
 * Naplánování řady telefonátů založí deset záznamů naráz a mazat se musí po
 * jednom. Proto se před uložením ukáže, kdo dostane jaký čas, a teprve pak se
 * potvrzuje. U změny vlastníka a stavu to není potřeba — jde to vzít zpátky
 * stejnou akcí.
 */
export default function HromadneAkce({ entita, vybrane, lide, stavy, onHotovo, onZrus }) {
  const [akce, setAkce] = useState(null); // "vlastnik" | "stav" | "aktivita"
  const [novyVlastnik, setNovyVlastnik] = useState("");
  const [novyStav, setNovyStav] = useState("");
  const [duvod, setDuvod] = useState("");
  const [akt, setAkt] = useState(() => ({
    druh: "telefon",
    nazev: "",
    termin: isoDen(new Date()),
    cas: "08:00",
    delka_min: 15,
    retez: true,
  }));
  const [plan, setPlan] = useState(null);
  const [pracuje, setPracuje] = useState(false);
  const [chyba, setChyba] = useState(null);

  const pocet = vybrane.length;
  if (!pocet) return null;

  const prohra = stavy?.find((s) => s.klic === novyStav)?.druh === "prohra";

  async function proved(fn) {
    setPracuje(true);
    setChyba(null);
    try {
      const out = await fn();
      setAkce(null);
      setPlan(null);
      onHotovo?.(out);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  return (
    <div className="ha">
      <div className="ha-lista">
        <b>{pocet}</b> vybráno
        <span className="crm-mezera" />
        {!akce && (
          <>
            <button className="fm-btn crm-btn-maly" onClick={() => setAkce("vlastnik")}>
              Změnit vlastníka
            </button>
            {entita === "op" && (
              <button className="fm-btn crm-btn-maly" onClick={() => setAkce("stav")}>
                Změnit stav
              </button>
            )}
            <button className="fm-btn crm-btn-maly fm-primary" onClick={() => setAkce("aktivita")}>
              Naplánovat aktivity
            </button>
          </>
        )}
        <button className="fm-btn crm-btn-maly" onClick={() => (akce ? setAkce(null) : onZrus?.())}>
          {akce ? "Zpět" : "Odznačit"}
        </button>
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {akce === "vlastnik" && (
        <div className="ha-formular">
          <select
            className="crm-pole crm-pole-uzke"
            value={novyVlastnik}
            onChange={(e) => setNovyVlastnik(e.target.value)}
          >
            <option value="">— vyber člověka —</option>
            {(lide || []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.jmeno}
              </option>
            ))}
          </select>
          <button
            className="fm-btn fm-primary crm-btn-maly"
            disabled={!novyVlastnik || pracuje}
            onClick={() =>
              proved(() =>
                crmHromadnyVlastnik({
                  entita,
                  ids: vybrane,
                  vlastnik_user_id: Number(novyVlastnik),
                })
              )
            }
          >
            {pracuje ? "Měním…" : `Přehodit ${pocet} záznamů`}
          </button>
        </div>
      )}

      {akce === "stav" && (
        <div className="ha-formular">
          <select
            className="crm-pole crm-pole-uzke"
            value={novyStav}
            onChange={(e) => setNovyStav(e.target.value)}
          >
            <option value="">— vyber stav —</option>
            {(stavy || []).map((s) => (
              <option key={s.klic} value={s.klic}>
                {s.nazev}
              </option>
            ))}
          </select>
          {prohra && (
            <input
              className="crm-pole"
              value={duvod}
              onChange={(e) => setDuvod(e.target.value)}
              placeholder="Důvod prohry (povinný)"
            />
          )}
          <button
            className="fm-btn fm-primary crm-btn-maly"
            disabled={!novyStav || (prohra && !duvod.trim()) || pracuje}
            onClick={() =>
              proved(() =>
                crmHromadnyStav({ ids: vybrane, stav: novyStav, duvod_prohry: duvod })
              )
            }
          >
            {pracuje ? "Měním…" : `Posunout ${pocet} případů`}
          </button>
        </div>
      )}

      {akce === "aktivita" && !plan && (
        <div className="ha-formular ha-aktivita">
          <select
            className="crm-pole crm-pole-uzke"
            value={akt.druh}
            onChange={(e) => setAkt((a) => ({ ...a, druh: e.target.value }))}
          >
            {DRUHY_AKTIVITY.filter((d) => d.klic !== "poznamka").map((d) => (
              <option key={d.klic} value={d.klic}>
                {d.nazev}
              </option>
            ))}
          </select>
          <input
            className="crm-pole"
            value={akt.nazev}
            onChange={(e) => setAkt((a) => ({ ...a, nazev: e.target.value }))}
            placeholder="Co je potřeba udělat (např. zavolat kvůli novým cenám)"
          />
          <input
            className="crm-pole crm-pole-uzke"
            type="date"
            value={akt.termin}
            onChange={(e) => setAkt((a) => ({ ...a, termin: e.target.value }))}
          />
          <input
            className="crm-pole crm-pole-cislo"
            type="time"
            value={akt.cas}
            onChange={(e) => setAkt((a) => ({ ...a, cas: e.target.value }))}
          />
          <label className="ha-mini">
            po
            <input
              className="crm-pole crm-pole-cislo"
              type="number"
              min={5}
              max={480}
              step={5}
              value={akt.delka_min}
              onChange={(e) => setAkt((a) => ({ ...a, delka_min: Number(e.target.value) }))}
            />
            min
          </label>
          <label className="ha-mini" title="Bez řetězení dostanou všechny stejný čas">
            <input
              type="checkbox"
              checked={akt.retez}
              onChange={(e) => setAkt((a) => ({ ...a, retez: e.target.checked }))}
            />
            za sebou
          </label>
          <button
            className="fm-btn fm-primary crm-btn-maly"
            disabled={!akt.nazev.trim() || !akt.termin || pracuje}
            onClick={async () => {
              // Náhled: spočítá se stejným pravidlem jako na serveru, ale nic
              // se neukládá — deset omylem založených telefonátů se maže těžko.
              const [h, m] = (akt.cas || "8:00").split(":").map(Number);
              let min = h * 60 + m;
              let den = akt.termin;
              const nahled = vybrane.map((id) => {
                const zapis = { id, den, cas: `${Math.floor(min / 60)}:${String(min % 60).padStart(2, "0")}` };
                if (akt.retez) {
                  min += akt.delka_min;
                  if (min >= 18 * 60) {
                    const d = new Date(`${den}T12:00:00`);
                    d.setDate(d.getDate() + 1);
                    den = isoDen(d);
                    min = h * 60 + m;
                  }
                }
                return zapis;
              });
              setPlan(nahled);
            }}
          >
            Ukázat plán
          </button>
        </div>
      )}

      {plan && (
        <div className="ha-plan">
          <p className="crm-tise">
            Takhle to vyjde. {plan.length} aktivit, {akt.delka_min} min na každou
            {akt.retez ? " (za sebou)" : " (všechny ve stejný čas)"}.
          </p>
          <ul>
            {plan.slice(0, 12).map((x) => (
              <li key={x.id}>
                {x.den} <b>{x.cas}</b>
              </li>
            ))}
            {plan.length > 12 && <li className="crm-tise">…a další {plan.length - 12}</li>}
          </ul>
          <div className="ha-formular">
            <button
              className="fm-btn fm-primary crm-btn-maly"
              disabled={pracuje}
              onClick={() =>
                proved(() =>
                  crmHromadnaAktivita({
                    entita,
                    ids: vybrane,
                    druh: akt.druh,
                    nazev: akt.nazev.trim(),
                    termin: akt.termin,
                    cas: akt.cas,
                    delka_min: akt.delka_min,
                    retez: akt.retez,
                  })
                )
              }
            >
              {pracuje ? "Zakládám…" : `Založit ${plan.length} aktivit`}
            </button>
            <button className="fm-btn crm-btn-maly" onClick={() => setPlan(null)}>
              Upravit
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
