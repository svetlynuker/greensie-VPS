import { useRef, useState } from "react";
import { nabidkaNahrajDokument, nabidkaSmazDokument, nabidkaZmenTypDokumentu } from "../api";

// Typy dokumentů + jejich povolené přípony (zrcadlí backend POVOLENE_PRIPONY).
const TYPY = [
  { klic: "faktura_pdf", nazev: "Faktura (PDF)", pripony: [".pdf"] },
  { klic: "spotreba_csv", nazev: "Spotřeba (CSV/XLSX)", pripony: [".csv", ".xlsx", ".xls"] },
  {
    klic: "jiny",
    nazev: "Jiný dokument",
    pripony: [".pdf", ".csv", ".xlsx", ".xls", ".png", ".jpg", ".jpeg"],
  },
];

// Vše, co jde nahrát (zrcadlí backend TYP_PODLE_PRIPONY) – typ si odvodí backend z přípony.
const VSECHNY_PRIPONY = ".pdf,.csv,.xlsx,.xls,.png,.jpg,.jpeg";

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

function pripona(nazev) {
  const i = (nazev || "").lastIndexOf(".");
  return i < 0 ? "" : nazev.slice(i).toLowerCase();
}

/** Na jaké typy jde daný soubor přeoznačit (PDF nemůže být profil spotřeby). */
function moznostiProSoubor(nazev) {
  const p = pripona(nazev);
  return TYPY.filter((t) => t.pripony.includes(p));
}

/**
 * Znovupoužitelná komponenta pro nahrání dokumentů k nabídce (kap. 5 SPEC).
 * Typ dokumentu se rozpozná automaticky z přípony; u nahraného souboru
 * jde přeoznačit rozbalovátkem. Soubor se jen uloží – NEZPRACOVÁVÁ se.
 */
export default function DokumentUpload({ nabidkaId, dokumenty, onZmena }) {
  const [nahrava, setNahrava] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [over, setOver] = useState(false);
  const [meniTypId, setMeniTypId] = useState(null);
  const inputRef = useRef(null);

  async function nahraj(file) {
    if (!file) return;
    setNahrava(true);
    setChyba(null);
    try {
      await nabidkaNahrajDokument(nabidkaId, file);
      if (inputRef.current) inputRef.current.value = "";
      await onZmena();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setNahrava(false);
    }
  }

  async function zmenTyp(id, typ) {
    setMeniTypId(id);
    setChyba(null);
    try {
      await nabidkaZmenTypDokumentu(id, typ);
      await onZmena();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setMeniTypId(null);
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
          accept={VSECHNY_PRIPONY}
          style={{ display: "none" }}
          onChange={(e) => nahraj(e.target.files?.[0])}
        />
        {nahrava ? "Nahrávám…" : "Přetáhni sem soubor nebo klikni pro výběr"}
        <div style={{ fontSize: 11, marginTop: 4 }}>
          Typ dokumentu poznáme sami · PDF, CSV, XLS/XLSX, obrázek · max 25 MB
        </div>
      </div>

      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 8 }}>{chyba}</div>}

      <div style={{ marginTop: 12 }}>
        {(dokumenty || []).length === 0 && (
          <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>Zatím žádné nahrané dokumenty.</div>
        )}
        {(dokumenty || []).map((d) => {
          const moznosti = moznostiProSoubor(d.puvodni_nazev);
          return (
            <div key={d.id} className="nb-doc-row">
              <span style={{ fontWeight: 600 }}>{d.puvodni_nazev}</span>
              <span style={{ color: "var(--fm-muted)" }}>{fmtVelikost(d.velikost_bajtu)}</span>
              {moznosti.length > 1 ? (
                <select
                  className="nb-pole"
                  value={d.typ}
                  disabled={meniTypId === d.id}
                  title="Rozpoznáno automaticky – tady se dá opravit"
                  onChange={(e) => zmenTyp(d.id, e.target.value)}
                  style={{ width: "auto", padding: "2px 6px", fontSize: 12 }}
                >
                  {moznosti.map((t) => (
                    <option key={t.klic} value={t.klic}>
                      {t.nazev}
                    </option>
                  ))}
                </select>
              ) : (
                <span style={{ color: "var(--fm-muted)", fontSize: 12 }}>
                  {TYPY.find((t) => t.klic === d.typ)?.nazev || d.typ}
                </span>
              )}
              <span className="nb-doc-wait">{STAV_DOKUMENTU[d.stav_zpracovani] || d.stav_zpracovani}</span>
              <span style={{ flex: 1 }} />
              <button
                className="fm-btn"
                style={{ padding: "4px 10px", color: "var(--st-crit)" }}
                onClick={() => smaz(d.id)}
              >
                Smazat
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
