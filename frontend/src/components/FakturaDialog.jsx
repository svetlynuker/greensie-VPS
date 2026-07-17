import { useState } from "react";

const poleStyl = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
};

const labelStyl = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "var(--fm-muted)",
  marginBottom: 4,
};

// Stejný katalog stavů jako na stránce (drží se i na backendu ve schemas.py).
const STAVY = [
  { klic: "potreba_vystavit", text: "Potřeba vystavit" },
  { klic: "vystaveno", text: "Vystaveno" },
  { klic: "zaplaceno", text: "Zaplaceno" },
  { klic: "nefakturuje", text: "Nefakturuje se" },
];

export default function FakturaDialog({ projektNazev, faktura, onSave, onDelete, onClose }) {
  const [stav, setStav] = useState(faktura?.stav || "potreba_vystavit");
  const [castka, setCastka] = useState(faktura?.castka != null ? String(faktura.castka) : "");
  const [termin, setTermin] = useState(faktura?.termin || "");
  const [vs, setVs] = useState(faktura?.variabilni_symbol || "");
  const [poznamka, setPoznamka] = useState(faktura?.poznamka || "");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        stav,
        castka: castka.trim() === "" ? null : Number(castka.replace(",", ".")),
        termin: termin || null,
        variabilni_symbol: vs.trim() || null,
        poznamka,
      });
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
          <h3 style={{ margin: "0 0 2px", fontSize: 15 }}>Faktura {faktura?.poradi}</h3>
          <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>{projektNazev}</div>
        </div>

        <div>
          <label style={labelStyl}>Stav</label>
          <select style={poleStyl} value={stav} onChange={(e) => setStav(e.target.value)}>
            {STAVY.map((s) => (
              <option key={s.klic} value={s.klic}>
                {s.text}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={labelStyl}>Částka (Kč, nepovinné)</label>
          <input
            type="text"
            inputMode="decimal"
            style={poleStyl}
            value={castka}
            placeholder="např. 25000"
            onChange={(e) => setCastka(e.target.value)}
          />
        </div>

        <div>
          <label style={labelStyl}>Variabilní symbol (párování s Pohodou)</label>
          <input
            type="text"
            style={poleStyl}
            value={vs}
            placeholder="např. 2026001"
            onChange={(e) => setVs(e.target.value)}
          />
        </div>

        <div>
          <label style={labelStyl}>Termín (nepovinné)</label>
          <input type="date" style={poleStyl} value={termin || ""} onChange={(e) => setTermin(e.target.value)} />
        </div>

        <div>
          <label style={labelStyl}>Poznámka</label>
          <textarea
            rows={4}
            style={{ ...poleStyl, resize: "vertical" }}
            value={poznamka}
            placeholder="Napiš poznámku…"
            onChange={(e) => setPoznamka(e.target.value)}
          />
        </div>

        {faktura?.pohoda_potvrzeno && (
          <div style={{ fontSize: 12, color: "var(--fm-brand-dk)" }}>
            Pohoda potvrdila
            {faktura.pohoda_datum_vystaveni ? ` · vystaveno ${faktura.pohoda_datum_vystaveni}` : ""}
            {faktura.pohoda_datum_zaplaceni ? ` · zaplaceno ${faktura.pohoda_datum_zaplaceni}` : ""}
          </div>
        )}

        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}

        <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
          {onDelete && (
            <button
              className="fm-btn"
              style={{ color: "var(--st-crit)" }}
              onClick={onDelete}
              disabled={uklada}
              title="Odebrat tuto fakturu z projektu"
            >
              Smazat
            </button>
          )}
          <div style={{ flex: 1 }} />
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
