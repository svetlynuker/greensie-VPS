import { useEffect, useState } from "react";
import {
  crmSablonaTextuPridej,
  crmSablonaTextuSmaz,
  crmSablonaTextuUprav,
  crmSablonyTextu,
} from "../api";

/**
 * Správa šablon e-mailů a poznámek (CRM-32) — okno pro `crm_nastaveni`.
 *
 * Šablony jsou firemní, ne osobní: smysl je, aby všichni psali zákazníkům
 * podobně a nikdo nezačínal od prázdné stránky. Proto je spravuje admin
 * a ostatní si je jen vkládají.
 *
 * `entita` u šablony říká, kde se nabídne. Prázdná = všude — a je to výchozí
 * volba schválně: šablona, kterou nikde nevidíš, je k ničemu, a omezit ji jde
 * kdykoli potom.
 */
const PRAZDNA = {
  druh: "email",
  nazev: "",
  predmet: "",
  telo: "",
  entita: "",
  aktivni: true,
  poradi: 0,
};

const ENTITY = [
  ["", "Všude"],
  ["zakaznik", "Zákazník"],
  ["op", "Obchodní případ"],
  ["nab", "Nabídka"],
  ["obj", "Objednávka"],
];

export default function SablonyTextuNastaveni({ onZavri }) {
  const [sablony, setSablony] = useState(null);
  const [symboly, setSymboly] = useState([]);
  const [novy, setNovy] = useState(PRAZDNA);
  const [upravovana, setUpravovana] = useState(null);
  const [chyba, setChyba] = useState(null);

  async function nacti() {
    const d = await crmSablonyTextu({ vse: true });
    setSablony(d.sablony || []);
    setSymboly(d.symboly || []);
  }

  useEffect(() => {
    nacti().catch((e) => setChyba(e.message));
  }, []);

  async function pridej() {
    if (!novy.nazev.trim()) return;
    setChyba(null);
    try {
      await crmSablonaTextuPridej(novy);
      setNovy(PRAZDNA);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function uloz(s) {
    setChyba(null);
    try {
      await crmSablonaTextuUprav(s.id, s);
      setUpravovana(null);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(s) {
    if (!window.confirm(`Opravdu smazat šablonu „${s.nazev}"?`)) return;
    setChyba(null);
    try {
      await crmSablonaTextuSmaz(s.id);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  const formular = upravovana || novy;
  const zmen = (zmeny) =>
    upravovana ? setUpravovana({ ...upravovana, ...zmeny }) : setNovy({ ...novy, ...zmeny });

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Šablony e-mailů a poznámek</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Šablona je předvyplnění, ne uzamčení — po vložení se text normálně upravuje.
            Šablony jsou společné pro celou firmu.
          </p>

          {symboly.length > 0 && (
            <p className="crm-tise crm-napoveda">
              <b>Doplní se samo:</b>{" "}
              {symboly.map((s) => `{{${s.klic}}} = ${s.popis}`).join(" · ")}
            </p>
          )}

          {chyba && <div className="crm-chyba">{chyba}</div>}

          {sablony === null ? null : sablony.length === 0 ? (
            <div className="crm-prazdno">Zatím žádná šablona.</div>
          ) : (
            <table className="crm-tabulka crm-tabulka-hustá">
              <thead>
                <tr>
                  <th>Název</th>
                  <th>Druh</th>
                  <th>Kde</th>
                  <th>Aktivní</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {sablony.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <div className="crm-silne">{s.nazev}</div>
                      {s.predmet && <div className="crm-tise">{s.predmet}</div>}
                    </td>
                    <td>{s.druh === "email" ? "E-mail" : "Poznámka"}</td>
                    <td>{(ENTITY.find(([k]) => k === s.entita) || ["", s.entita])[1]}</td>
                    <td>{s.aktivni ? "Ano" : "Ne"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="fm-btn crm-btn-maly" onClick={() => setUpravovana(s)}>
                        Upravit
                      </button>{" "}
                      <button className="fm-btn crm-btn-maly" onClick={() => smaz(s)}>
                        Smazat
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 style={{ marginTop: 18 }}>{upravovana ? "Úprava šablony" : "Nová šablona"}</h3>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="sb-nazev">
              Název *
            </label>
            <input
              id="sb-nazev"
              className="crm-pole"
              value={formular.nazev}
              onChange={(e) => zmen({ nazev: e.target.value })}
              placeholder="např. Posíláme nabídku"
            />
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="sb-druh">
              Druh
            </label>
            <select
              id="sb-druh"
              className="crm-pole"
              value={formular.druh}
              onChange={(e) => zmen({ druh: e.target.value })}
            >
              <option value="email">E-mail</option>
              <option value="poznamka">Poznámka</option>
            </select>
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="sb-entita">
              Kde se nabídne
            </label>
            <select
              id="sb-entita"
              className="crm-pole"
              value={formular.entita}
              onChange={(e) => zmen({ entita: e.target.value })}
            >
              {ENTITY.map(([k, n]) => (
                <option key={k} value={k}>
                  {n}
                </option>
              ))}
            </select>
          </div>

          {formular.druh === "email" && (
            <div className="crm-pole-radek">
              <label className="crm-label" htmlFor="sb-predmet">
                Předmět
              </label>
              <input
                id="sb-predmet"
                className="crm-pole"
                value={formular.predmet}
                onChange={(e) => zmen({ predmet: e.target.value })}
                placeholder="Nabídka {{cislo}} pro {{zakaznik}}"
              />
            </div>
          )}

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="sb-telo">
              Text
            </label>
            <textarea
              id="sb-telo"
              className="crm-pole"
              rows={8}
              value={formular.telo}
              onChange={(e) => zmen({ telo: e.target.value })}
              placeholder={"Dobrý den,\n\nposíláme nabídku {{cislo}} pro {{zakaznik}}…"}
            />
          </div>

          <label className="crm-zaskrtavaci">
            <input
              type="checkbox"
              checked={Boolean(formular.aktivni)}
              onChange={(e) => zmen({ aktivni: e.target.checked })}
            />
            Aktivní (nabízí se při psaní)
          </label>
        </div>

        <div className="crm-okno-pata">
          {upravovana ? (
            <>
              <button className="fm-btn fm-primary" onClick={() => uloz(upravovana)}>
                Uložit změny
              </button>
              <button className="fm-btn" onClick={() => setUpravovana(null)}>
                Zrušit úpravu
              </button>
            </>
          ) : (
            <button className="fm-btn fm-primary" onClick={pridej} disabled={!novy.nazev.trim()}>
              Přidat šablonu
            </button>
          )}
          <span className="crm-mezera" />
          <button className="fm-btn" onClick={onZavri}>
            Hotovo
          </button>
        </div>
      </div>
    </div>
  );
}
