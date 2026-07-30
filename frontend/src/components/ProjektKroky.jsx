import { useEffect, useState } from "react";
import { crmKrokPridej, crmKrokSmaz, crmKrokUprav, crmUzivatele } from "../api";
import { fmtDatum, jePoTerminu } from "../crm";

const STAVY = [
  { klic: "ceka", nazev: "Čeká" },
  { klic: "probiha", nazev: "Probíhá" },
  { klic: "hotovo", nazev: "Hotovo" },
  { klic: "preskoceno", nazev: "Přeskočeno" },
];

/**
 * Kroky realizace s termíny a návaznostmi.
 *
 * Termíny se dopočítávají: krok bez předchůdce od zahájení projektu, krok
 * s předchůdcem od jeho skutečného dokončení. Když se něco zdrží, posunou se
 * kroky za tím — proto se po každé změně přebírá celý projekt z odpovědi
 * serveru, ne jen ten jeden krok.
 *
 * Krok, který čeká na nedokončeného předchůdce, je vizuálně utlumený: OZ nemá
 * začínat něčím, co ještě nejde.
 */
export default function ProjektKroky({ projekt, sablony, onZmena, onSablona }) {
  const [lidi, setLidi] = useState([]);
  const [novy, setNovy] = useState({ nazev: "", delka_dni: "5", zavisi_na_id: "" });
  const [sablonaId, setSablonaId] = useState("");
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmUzivatele().then(setLidi).catch(() => setLidi([]));
  }, []);

  const kroky = projekt.kroky_seznam || [];

  async function uprav(krok, zmeny) {
    setChyba(null);
    try {
      onZmena(await crmKrokUprav(krok.id, zmeny));
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function pridej() {
    if (!novy.nazev.trim()) return;
    setChyba(null);
    try {
      onZmena(
        await crmKrokPridej(projekt.id, {
          nazev: novy.nazev.trim(),
          delka_dni: Number(novy.delka_dni) || 1,
          zavisi_na_id: novy.zavisi_na_id ? Number(novy.zavisi_na_id) : null,
        })
      );
      setNovy({ nazev: "", delka_dni: "5", zavisi_na_id: "" });
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(krok) {
    if (!window.confirm(`Smazat krok „${krok.nazev}"?`)) return;
    setChyba(null);
    try {
      onZmena(await crmKrokSmaz(krok.id));
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div className="fm-card crm-blok">
      <div className="crm-blok-hlava">
        <h3>Kroky realizace</h3>
        {projekt.kroku > 0 && (
          <span className="crm-znacka">
            {projekt.hotovo}/{projekt.kroku} · {projekt.procent} %
          </span>
        )}
        <span className="crm-mezera" />
        {/* Šablonu lze přidat i k rozjetému projektu – kroky se přidají za ty
            existující (např. „FVE" + „Dotace"). */}
        <select
          className="crm-pole crm-pole-uzke"
          value={sablonaId}
          onChange={(e) => setSablonaId(e.target.value)}
        >
          <option value="">— přidat kroky ze šablony —</option>
          {(sablony || []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.nazev} ({s.kroky.length})
            </option>
          ))}
        </select>
        <button
          className="fm-btn"
          onClick={() => {
            onSablona(Number(sablonaId));
            setSablonaId("");
          }}
          disabled={!sablonaId}
        >
          Přidat
        </button>
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {kroky.length === 0 ? (
        <p className="crm-tise">
          Projekt zatím nemá kroky. Přidej je ze šablony (vybere se nahoře) nebo po jednom níž.
        </p>
      ) : (
        <ol className="crm-kroky-seznam">
          {kroky.map((k) => {
            const hotovy = k.stav === "hotovo" || k.stav === "preskoceno";
            const spatne = !hotovy && k.termin && jePoTerminu(k.termin);
            return (
              <li
                key={k.id}
                className={`crm-krok ${hotovy ? "hotovy" : ""} ${!k.dostupny && !hotovy ? "ceka" : ""}`}
              >
                <div className="crm-krok-hlava">
                  {/* Rychlé odkliknutí hotového kroku – to je nejčastější akce. */}
                  <input
                    type="checkbox"
                    checked={hotovy}
                    onChange={(e) => uprav(k, { stav: e.target.checked ? "hotovo" : "ceka" })}
                    aria-label={`${k.nazev} hotovo`}
                  />
                  <input
                    className="crm-pole crm-krok-nazev"
                    defaultValue={k.nazev}
                    onBlur={(e) => {
                      const v = e.target.value.trim();
                      if (v && v !== k.nazev) uprav(k, { nazev: v });
                    }}
                  />
                  <select
                    className="crm-pole crm-pole-uzke"
                    value={k.stav}
                    onChange={(e) => uprav(k, { stav: e.target.value })}
                  >
                    {STAVY.map((s) => (
                      <option key={s.klic} value={s.klic}>
                        {s.nazev}
                      </option>
                    ))}
                  </select>
                  <button
                    className="fm-btn crm-btn-maly crm-btn-smazat"
                    onClick={() => smaz(k)}
                    title="Smazat krok"
                  >
                    ✕
                  </button>
                </div>

                <div className="crm-krok-radek">
                  <label className="crm-krok-pole">
                    <span className="crm-label">Termín</span>
                    <input
                      className="crm-pole crm-pole-uzke"
                      type="date"
                      value={(k.termin || "").slice(0, 10)}
                      onChange={(e) => uprav(k, { termin: e.target.value })}
                    />
                  </label>
                  {k.termin_rucne ? (
                    <span className="crm-tise" title="Ruční termín přepočet nepřepíše">
                      ruční —{" "}
                      <button
                        className="crm-odkaz-tlacitko"
                        onClick={() => uprav(k, { termin: "" })}
                      >
                        vrátit do automatu
                      </button>
                    </span>
                  ) : (
                    <span className="crm-tise">dopočítaný</span>
                  )}

                  <label className="crm-krok-pole">
                    <span className="crm-label">Trvání (dny)</span>
                    <input
                      className="crm-pole crm-pole-cislo"
                      type="number"
                      min={1}
                      defaultValue={k.delka_dni}
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (v && v !== k.delka_dni) uprav(k, { delka_dni: v });
                      }}
                    />
                  </label>

                  <label className="crm-krok-pole">
                    <span className="crm-label">Navazuje na</span>
                    <select
                      className="crm-pole crm-pole-uzke"
                      value={k.zavisi_na_id || ""}
                      onChange={(e) =>
                        uprav(k, { zavisi_na_id: e.target.value ? Number(e.target.value) : 0 })
                      }
                    >
                      <option value="">— nic (od zahájení) —</option>
                      {kroky
                        .filter((j) => j.id !== k.id)
                        .map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.nazev}
                          </option>
                        ))}
                    </select>
                  </label>

                  <label className="crm-krok-pole">
                    <span className="crm-label">Odpovědný</span>
                    <select
                      className="crm-pole crm-pole-uzke"
                      value={k.odpovedny_user_id || ""}
                      onChange={(e) =>
                        uprav(k, {
                          odpovedny_user_id: e.target.value ? Number(e.target.value) : 0,
                        })
                      }
                    >
                      <option value="">— nikdo —</option>
                      {lidi.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.jmeno}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="crm-krok-pata">
                  {!k.dostupny && !hotovy && (
                    <span className="crm-tise">čeká na „{k.zavisi_na_nazev}"</span>
                  )}
                  {spatne && <span className="crm-po-terminu">po termínu</span>}
                  {hotovy && k.hotovo_at && (
                    <span className="crm-tise">dokončeno {fmtDatum(k.hotovo_at)}</span>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}

      <div className="crm-oddelovac" style={{ marginTop: 14, paddingTop: 12 }}>
        <div className="crm-stav-novy">
          <input
            className="crm-pole"
            value={novy.nazev}
            onChange={(e) => setNovy((n) => ({ ...n, nazev: e.target.value }))}
            placeholder="Název nového kroku"
          />
          <input
            className="crm-pole crm-pole-cislo"
            type="number"
            min={1}
            value={novy.delka_dni}
            onChange={(e) => setNovy((n) => ({ ...n, delka_dni: e.target.value }))}
            title="Trvání ve dnech"
          />
          <select
            className="crm-pole crm-pole-uzke"
            value={novy.zavisi_na_id}
            onChange={(e) => setNovy((n) => ({ ...n, zavisi_na_id: e.target.value }))}
          >
            <option value="">— navazuje na nic —</option>
            {kroky.map((j) => (
              <option key={j.id} value={j.id}>
                {j.nazev}
              </option>
            ))}
          </select>
          <button className="fm-btn fm-primary" onClick={pridej} disabled={!novy.nazev.trim()}>
            Přidat krok
          </button>
        </div>
      </div>
    </div>
  );
}
