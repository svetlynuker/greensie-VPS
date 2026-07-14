import { useRef, useState } from "react";
import { nabidkaNahrajDokument, nabidkaSmazDokument } from "../api";

// Typy dokumentů + jejich povolené přípony (zrcadlí backend POVOLENE_PRIPONY).
const TYPY = [
  { klic: "faktura_pdf", nazev: "Faktura (PDF)", pripony: ".pdf" },
  { klic: "spotreba_csv", nazev: "Spotřeba (CSV/XLSX)", pripony: ".csv,.xlsx,.xls" },
  { klic: "jiny", nazev: "Jiný dokument", pripony: ".pdf,.csv,.xlsx,.xls,.png,.jpg,.jpeg" },
];

const STAV_DOKUMENTU = {
  nahrano: "Čeká na zpracování (funkce se připravuje)",
  extrahovano: "Zpracováno",
  chyba_extrakce: "Chyba zpracování",
  rucne_doplneno: "Ručně doplněno",
};

function fmtVelikost(b) {
  if (b == null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} kB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Znovupoužitelná komponenta pro nahrání dokumentů k nabídce (kap. 5 SPEC).
 * Soubor se jen uloží (stav "nahráno") – NEZPRACOVÁVÁ se.
 */
export default function DokumentUpload({ nabidkaId, dokumenty, onZmena }) {
  const [typ, setTyp] = useState("faktura_pdf");
  const [nahrava, setNahrava] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [over, setOver] = useState(false);
  const inputRef = useRef(null);

  const aktualniTyp = TYPY.find((t) => t.klic === typ);

  async function nahraj(file) {
    if (!file) return;
    setNahrava(true);
    setChyba(null);
    try {
      await nabidkaNahrajDokument(nabidkaId, typ, file);
      if (inputRef.current) inputRef.current.value = "";
      await onZmena();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setNahrava(false);
    }
  }

  async function smaz(id) {
    setChyba(null);
    try {
      await nabidkaSmazDokument(id);
      await onZmena();
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", marginBottom: 10, flexWrap: "wrap" }}>
        <div>
          <label className="nb-label">Typ dokumentu</label>
          <select className="nb-pole" value={typ} onChange={(e) => setTyp(e.target.value)} style={{ width: "auto" }}>
            {TYPY.map((t) => (
              <option key={t.klic} value={t.klic}>
                {t.nazev}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div
        className={`nb-drop${over ? " nb-drop-over" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          if (e.dataTransfer.files?.[0]) nahraj(e.dataTransfer.files[0]);
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept={aktualniTyp?.pripony}
          style={{ display: "none" }}
          onChange={(e) => nahraj(e.target.files?.[0])}
        />
        {nahrava ? "Nahrávám…" : "Přetáhni sem soubor nebo klikni pro výběr"}
        <div style={{ fontSize: 11, marginTop: 4 }}>Povoleno: {aktualniTyp?.pripony} · max 25 MB</div>
      </div>

      {chyba && <div style={{ color: "#c92a2a", fontSize: 13, marginTop: 8 }}>{chyba}</div>}

      <div style={{ marginTop: 12 }}>
        {(dokumenty || []).length === 0 && (
          <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>Zatím žádné nahrané dokumenty.</div>
        )}
        {(dokumenty || []).map((d) => (
          <div key={d.id} className="nb-doc-row">
            <span style={{ fontWeight: 600 }}>{d.puvodni_nazev}</span>
            <span style={{ color: "var(--fm-muted)" }}>{fmtVelikost(d.velikost_bajtu)}</span>
            <span className="nb-doc-wait">{STAV_DOKUMENTU[d.stav_zpracovani] || d.stav_zpracovani}</span>
            <span style={{ flex: 1 }} />
            <button className="fm-btn" style={{ padding: "4px 10px", color: "#c92a2a" }} onClick={() => smaz(d.id)}>
              Smazat
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
