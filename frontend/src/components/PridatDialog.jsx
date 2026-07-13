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

// pole: [{ klic, label, typ: "text"|"date", placeholder?, povinne? }]
export default function PridatDialog({ nadpis, pole, onSave, onClose }) {
  const [hodnoty, setHodnoty] = useState(() => Object.fromEntries(pole.map((p) => [p.klic, ""])));
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave(hodnoty);
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
        style={{ padding: 20, width: "min(420px, 100%)", display: "flex", flexDirection: "column", gap: 12 }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>{nadpis}</h3>
        {pole.map((p) => (
          <div key={p.klic}>
            <label style={labelStyl}>{p.label}</label>
            <input
              type={p.typ || "text"}
              style={poleStyl}
              value={hodnoty[p.klic]}
              placeholder={p.placeholder || ""}
              onChange={(e) => setHodnoty((h) => ({ ...h, [p.klic]: e.target.value }))}
            />
          </div>
        ))}
        {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
          <button className="fm-btn" onClick={onClose} disabled={uklada}>
            Zrušit
          </button>
          <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
            {uklada ? "Ukládám…" : "Přidat"}
          </button>
        </div>
      </div>
    </div>
  );
}
