import { useEffect, useMemo, useState } from "react";
import { technologieSeznam } from "../api";

// Rozpis položek nabídky nebo objednávky (CRM-08).
//
// Jedna komponenta pro obojí schválně: rozpis se z nabídky do objednávky
// překlápí, takže musí vypadat i počítat stejně. Rozdíl je jen v tom, které
// API funkce dostane přes props (`nacti`, `uloz`, `pridejZKatalogu`).
//
// Souhrn se bere z backendu, ne z JavaScriptu. Kdyby se sčítal tady, mohla by
// appka ukázat jiné číslo než tiskový výstup a faktura – zaokrouhlování
// v JS a v Pythonu se chová jinak.

function kc(v) {
  return v == null ? "—" : `${v.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} Kč`;
}

function num(v) {
  const t = String(v ?? "").replace(",", ".").trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

const PRAZDNY_RADEK = {
  id: null,
  technologie_id: null,
  kod: "",
  nazev: "",
  popis: "",
  jednotka: "ks",
  mnozstvi: "1",
  cena_jednotkova: "",
  nakup_jednotkovy: "",
  sleva_procent: "0",
  sazba_dph: "0.21",
};

/* ---------- výběr položek z katalogu ---------- */
function VyberZKatalogu({ onVybrano, onClose }) {
  const [katalog, setKatalog] = useState(null);
  const [hledani, setHledani] = useState("");
  const [kategorie, setKategorie] = useState("vse");
  const [vybrane, setVybrane] = useState(() => new Set());
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    // `jen_aktivni` – vyřazené zboží ani neplatný ceník se do nové nabídky
    // nabízet nemá.
    technologieSeznam(true)
      .then(setKatalog)
      .catch((e) => setChyba(e.message));
  }, []);

  const kategorie_seznam = useMemo(() => {
    const s = new Set((katalog || []).map((t) => t.kategorie).filter(Boolean));
    return [...s].sort((a, b) => a.localeCompare(b, "cs"));
  }, [katalog]);

  const dotaz = hledani.trim().toLowerCase();
  const videne = (katalog || []).filter(
    (t) =>
      (kategorie === "vse" || t.kategorie === kategorie) &&
      (dotaz === "" ||
        `${t.nazev} ${t.kod || ""} ${t.model || ""}`.toLowerCase().includes(dotaz))
  );

  function prepni(id) {
    setVybrane((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  }

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(31,41,51,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 210, padding: 16 }}
    >
      <div
        className="fm-card"
        onClick={(e) => e.stopPropagation()}
        style={{ padding: 18, width: "min(760px, 100%)", maxHeight: "88vh", display: "flex", flexDirection: "column", gap: 12 }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>Vybrat z katalogu</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            className="gs-input"
            autoFocus
            value={hledani}
            onChange={(e) => setHledani(e.target.value)}
            placeholder="Hledat podle kódu nebo názvu…"
            style={{ flex: "1 1 200px" }}
          />
          <select className="gs-input" value={kategorie} onChange={(e) => setKategorie(e.target.value)} style={{ maxWidth: 200 }}>
            <option value="vse">Všechny kategorie</option>
            {kategorie_seznam.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>

        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}
        {katalog == null && !chyba && <div style={{ fontSize: 13 }}>Načítám katalog…</div>}

        <div className="gs-scroll" style={{ flex: 1, minHeight: 200, overflowY: "auto" }}>
          <table className="gs-table">
            <thead>
              <tr>
                <th style={{ width: 28 }}></th>
                <th>Kód</th><th>Název</th><th>Kategorie</th><th className="n">Cena</th><th>MJ</th>
              </tr>
            </thead>
            <tbody>
              {videne.map((t) => (
                <tr key={t.id} onClick={() => prepni(t.id)} style={{ cursor: "pointer" }}>
                  <td onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={vybrane.has(t.id)} onChange={() => prepni(t.id)} />
                  </td>
                  <td style={{ fontFamily: "monospace", fontSize: 12 }}>{t.kod || "—"}</td>
                  <td>{t.nazev}</td>
                  <td>{t.kategorie || "—"}</td>
                  <td className="n">{kc(t.cena_kc)}</td>
                  <td>{t.jednotka || "ks"}</td>
                </tr>
              ))}
              {katalog != null && videne.length === 0 && (
                <tr className="staticky">
                  <td colSpan={6} className="gs-empty">Nic nenalezeno.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--muted)" }}>Vybráno: {vybrane.size}</span>
          <span style={{ flex: 1 }} />
          <button className="fm-btn" onClick={onClose}>Zrušit</button>
          <button
            className="fm-btn fm-primary"
            disabled={vybrane.size === 0}
            onClick={() => onVybrano([...vybrane])}
          >
            Přidat do rozpisu
          </button>
        </div>
      </div>
    </div>
  );
}

/* ---------- editor rozpisu ---------- */
export default function RozpisPolozek({
  nacti,
  uloz,
  pridejZKatalogu,
  prekloopZNabidky = null, // jen u objednávky, která vznikla z nabídky
  muzeEditovat = true,
  nadpis = "Rozpis položek",
  // Zavolá se po každé změně rozpisu – u objednávky se tím přenačte cena,
  // kterou backend srovnal podle součtu.
  onZmena = null,
}) {
  const [data, setData] = useState(null);
  const [radky, setRadky] = useState([]);
  const [zmeneno, setZmeneno] = useState(false);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [vyberOtevren, setVyberOtevren] = useState(false);

  function prevezmi(odpoved) {
    setData(odpoved);
    setRadky(
      (odpoved.polozky || []).map((p) => ({
        id: p.id,
        technologie_id: p.technologie_id,
        kod: p.kod || "",
        nazev: p.nazev || "",
        popis: p.popis || "",
        jednotka: p.jednotka || "ks",
        mnozstvi: String(p.mnozstvi ?? 1),
        cena_jednotkova: p.cena_jednotkova == null ? "" : String(p.cena_jednotkova),
        nakup_jednotkovy: p.nakup_jednotkovy == null ? "" : String(p.nakup_jednotkovy),
        sleva_procent: String(p.sleva_procent ?? 0),
        sazba_dph: p.sazba_dph == null ? "" : String(p.sazba_dph),
      }))
    );
    setZmeneno(false);
  }

  useEffect(() => {
    nacti()
      .then(prevezmi)
      .catch((e) => setChyba(e.message));
    // Načítá se jednou při otevření – `nacti` je stabilní funkce z rodiče.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function zmen(index, pole, hodnota) {
    setRadky((r) => r.map((x, i) => (i === index ? { ...x, [pole]: hodnota } : x)));
    setZmeneno(true);
  }

  function pridejPrazdny() {
    setRadky((r) => [...r, { ...PRAZDNY_RADEK }]);
    setZmeneno(true);
  }

  function smazRadek(index) {
    setRadky((r) => r.filter((_, i) => i !== index));
    setZmeneno(true);
  }

  function presun(index, smer) {
    const cil = index + smer;
    if (cil < 0 || cil >= radky.length) return;
    setRadky((r) => {
      const n = [...r];
      [n[index], n[cil]] = [n[cil], n[index]];
      return n;
    });
    setZmeneno(true);
  }

  async function ulozRozpis() {
    setUklada(true);
    setChyba(null);
    try {
      const odpoved = await uloz(
        radky.map((r) => ({
          id: r.id,
          technologie_id: r.technologie_id,
          kod: r.kod,
          nazev: r.nazev,
          popis: r.popis,
          jednotka: r.jednotka,
          mnozstvi: num(r.mnozstvi) ?? 0,
          cena_jednotkova: num(r.cena_jednotkova),
          nakup_jednotkovy: num(r.nakup_jednotkovy),
          sleva_procent: num(r.sleva_procent) ?? 0,
          sazba_dph: num(r.sazba_dph),
        }))
      );
      prevezmi(odpoved);
      await onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
    setUklada(false);
  }

  async function zKatalogu(ids) {
    setVyberOtevren(false);
    setChyba(null);
    try {
      prevezmi(await pridejZKatalogu(ids));
      await onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function zNabidky() {
    setChyba(null);
    try {
      prevezmi(await prekloopZNabidky());
      await onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && data == null) {
    return <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>;
  }
  if (data == null) return <div style={{ fontSize: 13 }}>Načítám rozpis…</div>;

  const vidiNakup = !!data.vidi_nakup;
  const souhrn = data.souhrn || {};

  // Živý součet z rozepsaných řádků – ukazuje, jak se souhrn změní po uložení.
  // Uložený souhrn zůstává vedle, aby bylo jasné, co je zatím jen na obrazovce.
  const zivyMezisoucet = radky.reduce((suma, r) => {
    const mn = num(r.mnozstvi) ?? 0;
    const cena = num(r.cena_jednotkova) ?? 0;
    const sleva = num(r.sleva_procent) ?? 0;
    return suma + mn * cena * (1 - sleva / 100);
  }, 0);

  return (
    <div className="fm-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="gs-sekce-t" style={{ marginTop: 0 }}>
        {nadpis}
        <span className="gs-pill">{radky.length} položek</span>
        <span className="gs-mezera" />
        {muzeEditovat && (
          <>
            {prekloopZNabidky && (
              <button className="fm-btn" onClick={zNabidky} title="Zkopírovat rozpis z nabídky, ze které objednávka vznikla">
                ↓ Z nabídky
              </button>
            )}
            <button className="fm-btn" onClick={() => setVyberOtevren(true)}>+ Z katalogu</button>
            <button className="fm-btn" onClick={pridejPrazdny}>+ Vlastní položka</button>
          </>
        )}
      </div>

      <div className="gs-scroll">
        <table className="gs-table">
          <thead>
            <tr>
              <th style={{ width: 30 }}></th>
              <th>Kód</th>
              <th style={{ minWidth: 180 }}>Název</th>
              <th className="n" style={{ width: 80 }}>Množství</th>
              <th style={{ width: 60 }}>MJ</th>
              <th className="n" style={{ width: 110 }}>Cena/MJ</th>
              <th className="n" style={{ width: 70 }}>Sleva %</th>
              {vidiNakup && <th className="n" style={{ width: 110 }}>Nákup/MJ</th>}
              <th className="n" style={{ width: 70 }}>DPH</th>
              <th className="n" style={{ width: 110 }}>Celkem</th>
              {muzeEditovat && <th style={{ width: 70 }}></th>}
            </tr>
          </thead>
          <tbody>
            {radky.map((r, i) => {
              const mn = num(r.mnozstvi) ?? 0;
              const cena = num(r.cena_jednotkova) ?? 0;
              const sleva = num(r.sleva_procent) ?? 0;
              const celkem = mn * cena * (1 - sleva / 100);
              return (
                <tr key={r.id ?? `novy-${i}`} className="staticky">
                  <td style={{ color: "var(--muted)", fontSize: 12 }}>{i + 1}</td>
                  <td>
                    <input className="nb-pole" style={{ width: 90, fontSize: 12 }} value={r.kod}
                      onChange={(e) => zmen(i, "kod", e.target.value)} disabled={!muzeEditovat} />
                  </td>
                  <td>
                    <input className="nb-pole" style={{ width: "100%", minWidth: 170 }} value={r.nazev}
                      onChange={(e) => zmen(i, "nazev", e.target.value)} disabled={!muzeEditovat}
                      placeholder="Název položky" />
                  </td>
                  <td className="n">
                    <input className="nb-pole" style={{ width: 70, textAlign: "right" }} value={r.mnozstvi}
                      onChange={(e) => zmen(i, "mnozstvi", e.target.value)} inputMode="decimal" disabled={!muzeEditovat} />
                  </td>
                  <td>
                    <input className="nb-pole" style={{ width: 52 }} value={r.jednotka}
                      onChange={(e) => zmen(i, "jednotka", e.target.value)} disabled={!muzeEditovat} />
                  </td>
                  <td className="n">
                    <input className="nb-pole" style={{ width: 100, textAlign: "right" }} value={r.cena_jednotkova}
                      onChange={(e) => zmen(i, "cena_jednotkova", e.target.value)} inputMode="decimal" disabled={!muzeEditovat} />
                  </td>
                  <td className="n">
                    <input className="nb-pole" style={{ width: 60, textAlign: "right" }} value={r.sleva_procent}
                      onChange={(e) => zmen(i, "sleva_procent", e.target.value)} inputMode="decimal" disabled={!muzeEditovat} />
                  </td>
                  {vidiNakup && (
                    <td className="n">
                      <input className="nb-pole" style={{ width: 100, textAlign: "right" }} value={r.nakup_jednotkovy}
                        onChange={(e) => zmen(i, "nakup_jednotkovy", e.target.value)} inputMode="decimal" disabled={!muzeEditovat} />
                    </td>
                  )}
                  <td className="n">
                    <select className="nb-pole" style={{ width: 66 }} value={r.sazba_dph}
                      onChange={(e) => zmen(i, "sazba_dph", e.target.value)} disabled={!muzeEditovat}>
                      <option value="">—</option>
                      <option value="0.21">21 %</option>
                      <option value="0.12">12 %</option>
                      <option value="0">0 %</option>
                    </select>
                  </td>
                  <td className="n" style={{ fontWeight: 600 }}>{kc(Math.round(celkem * 100) / 100)}</td>
                  {muzeEditovat && (
                    <td className="n" style={{ whiteSpace: "nowrap" }}>
                      <button type="button" onClick={() => presun(i, -1)} title="Nahoru"
                        style={{ background: "none", border: "none", cursor: "pointer", padding: "0 3px" }}>↑</button>
                      <button type="button" onClick={() => presun(i, 1)} title="Dolů"
                        style={{ background: "none", border: "none", cursor: "pointer", padding: "0 3px" }}>↓</button>
                      <button type="button" onClick={() => smazRadek(i)} title="Smazat řádek"
                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--st-crit)", fontWeight: 700, padding: "0 3px" }}>×</button>
                    </td>
                  )}
                </tr>
              );
            })}
            {radky.length === 0 && (
              <tr className="staticky">
                <td colSpan={muzeEditovat ? 11 : 10} className="gs-empty">
                  Rozpis je prázdný. Přidej položky z katalogu, nebo napiš vlastní.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Souhrn – uložený z backendu, aby čísla seděla s tiskem a fakturou. */}
      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "center", fontSize: 13 }}>
        <span>Bez DPH: <b>{kc(souhrn.bez_dph)}</b></span>
        <span>DPH: <b>{kc(souhrn.dph)}</b></span>
        <span>S DPH: <b>{kc(souhrn.s_dph)}</b></span>
        {vidiNakup && souhrn.marze_kc != null && (
          <span style={{ color: "var(--muted)" }}>
            Marže: <b>{kc(souhrn.marze_kc)}</b>
            {souhrn.marze_procent != null ? ` (${souhrn.marze_procent} %)` : ""}
          </span>
        )}
        {zmeneno && (
          <span style={{ color: "var(--st-warn, #b26a00)" }}>
            Neuloženo — po uložení bude bez DPH {kc(Math.round(zivyMezisoucet * 100) / 100)}
          </span>
        )}
      </div>

      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}

      {muzeEditovat && (
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ flex: 1 }} />
          <button className="fm-btn fm-primary" onClick={ulozRozpis} disabled={uklada || !zmeneno}>
            {uklada ? "Ukládám…" : "Uložit rozpis"}
          </button>
        </div>
      )}

      {vyberOtevren && <VyberZKatalogu onVybrano={zKatalogu} onClose={() => setVyberOtevren(false)} />}
    </div>
  );
}
