import { useState } from "react";

const poleStyl = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
};

const labelStyl = { display: "block", fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 4 };

export default function BunkaDialog({ projektNazev, ukolNazev, bunka, onSave, onClose }) {
  const [stav, setStav] = useState(bunka?.stav || "");
  const [termin, setTermin] = useState(bunka?.termin || "");
  const [osoba, setOsoba] = useState(bunka?.osoba || "");
  const [poznamka, setPoznamka] = useState(bunka?.poznamka || "");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({ stav: stav || null, termin: termin || null, osoba, poznamka });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(31,41,51,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: 16,
      }}
    >
      <div
        className="fm-card"
        onClick={(e) => e.stopPropagation()}
        style={{ padding: 20, width: "min(440px, 100%)", display: "flex", flexDirection: "column", gap: 12 }}
      >
        <div>
          <h3 style={{ margin: "0 0 2px", fontSize: 15 }}>{ukolNazev}</h3>
          <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>{projektNazev}</div>
        </div>

        <div>
          <label style={labelStyl}>Stav</label>
          <select style={poleStyl} value={stav} onChange={(e) => setStav(e.target.value)}>
            <option value="">— (prázdné / neexistuje)</option>
            <option value="todo">Nehotovo</option>
            <option value="done">Hotovo</option>
          </select>
        </div>

        <div>
          <label style={labelStyl}>Termín</label>
          <input type="date" style={poleStyl} value={termin || ""} onChange={(e) => setTermin(e.target.value)} />
        </div>

        <div>
          <label style={labelStyl}>Odpovědná osoba</label>
          <input
            type="text"
            style={poleStyl}
            value={osoba}
            placeholder="jméno"
            onChange={(e) => setOsoba(e.target.value)}
          />
        </div>

        <div>
          <label style={labelStyl}>Poznámka</label>
          <textarea
            rows={5}
            style={{ ...poleStyl, resize: "vertical" }}
            value={poznamka}
            placeholder="Napiš poznámku…"
            onChange={(e) => setPoznamka(e.target.value)}
          />
        </div>

        {bunka?.url && (
          <div style={{ fontSize: 12 }}>
            <a href={bunka.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--fm-brand-dk)" }}>
              Otevřít úkol ve Freelu ↗
            </a>
          </div>
        )}

        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
          <button className="fm-btn" onClick={onClose} disabled={uklada}>
            Zrušit
          </button>
          <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
            {uklada ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </div>
    </div>
  );
}
