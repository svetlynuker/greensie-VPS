import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import {
  nactiMe,
  logout,
  technologieSeznam,
  technologiePridej,
  technologieUprav,
  technologieSmaz,
  vypoctovaNastaveniSeznam,
  vypoctovaNastaveniUloz,
} from "../api";
import "../styles/nabidkovac.css";

const TYPY_TECH = [
  { klic: "fve_panel", nazev: "FVE panel" },
  { klic: "invertor", nazev: "Invertor" },
  { klic: "baterie", nazev: "Baterie" },
  { klic: "jina", nazev: "Jiná" },
];
const NAZEV_TYPU = Object.fromEntries(TYPY_TECH.map((t) => [t.klic, t.nazev]));

function num(v) {
  return v.trim() === "" ? null : Number(v.replace(",", "."));
}
function str(v) {
  return v == null ? "" : String(v);
}

/* ---------- modal editoru technologie ---------- */
function TechEditor({ tech, onSave, onClose }) {
  const [typ, setTyp] = useState(tech?.typ || "fve_panel");
  const [nazev, setNazev] = useState(tech?.nazev || "");
  const [model, setModel] = useState(tech?.model || "");
  const [vykon, setVykon] = useState(str(tech?.vykon_kw));
  const [kapacita, setKapacita] = useState(str(tech?.kapacita_kwh));
  const [cena, setCena] = useState(str(tech?.cena_kc));
  const [ucinnost, setUcinnost] = useState(str(tech?.ucinnost));
  const [dostupnost, setDostupnost] = useState(tech?.dostupnost ?? true);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    if (!nazev.trim()) {
      setChyba("Název je povinný.");
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        typ,
        nazev: nazev.trim(),
        model: model.trim(),
        vykon_kw: num(vykon),
        kapacita_kwh: num(kapacita),
        cena_kc: num(cena),
        ucinnost: num(ucinnost),
        dostupnost,
      });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <div
      onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(31,41,51,.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 200, padding: 16 }}
    >
      <div className="fm-card" onClick={(e) => e.stopPropagation()} style={{ padding: 20, width: "min(480px, 100%)", maxHeight: "90vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{tech ? "Upravit technologii" : "Nová technologie"}</h3>
        <div>
          <label className="nb-label">Typ</label>
          <select className="nb-pole" value={typ} onChange={(e) => setTyp(e.target.value)}>
            {TYPY_TECH.map((t) => (
              <option key={t.klic} value={t.klic}>{t.nazev}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="nb-label">Název</label>
          <input className="nb-pole" value={nazev} onChange={(e) => setNazev(e.target.value)} />
        </div>
        <div>
          <label className="nb-label">Model</label>
          <input className="nb-pole" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
        <div className="nb-form-grid">
          <div>
            <label className="nb-label">Výkon (kW)</label>
            <input className="nb-pole" value={vykon} onChange={(e) => setVykon(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <label className="nb-label">Kapacita (kWh)</label>
            <input className="nb-pole" value={kapacita} onChange={(e) => setKapacita(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <label className="nb-label">Cena (Kč)</label>
            <input className="nb-pole" value={cena} onChange={(e) => setCena(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <label className="nb-label">Účinnost (0–1)</label>
            <input className="nb-pole" value={ucinnost} onChange={(e) => setUcinnost(e.target.value)} inputMode="decimal" />
          </div>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <input type="checkbox" checked={dostupnost} onChange={(e) => setDostupnost(e.target.checked)} />
          Dostupná v katalogu
        </label>
        {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
          <span style={{ flex: 1 }} />
          <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
          <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
            {uklada ? "Ukládám…" : "Uložit"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function NabidkovacKatalog() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [tech, setTech] = useState(null);
  const [nastaveni, setNastaveni] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [editace, setEditace] = useState(undefined); // undefined = zavřeno, null = nová, obj = úprava

  // formulář výpočtových nastavení (nová verze)
  const [koef, setKoef] = useState("");
  const [minRoky, setMinRoky] = useState("");
  const [maxRoky, setMaxRoky] = useState("");
  const [nastavZprava, setNastavZprava] = useState(null);
  const [nastavUklada, setNastavUklada] = useState(false);

  async function nactiVse() {
    const [ts, ns] = await Promise.all([technologieSeznam(), vypoctovaNastaveniSeznam()]);
    setTech(ts);
    setNastaveni(ns);
    const akt = ns[0];
    setKoef(str(akt?.koeficient_zisku));
    setMinRoky(str(akt?.min_delka_kontraktu_roky));
    setMaxRoky(str(akt?.max_delka_kontraktu_roky));
  }

  useEffect(() => {
    nactiMe()
      .then((m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("nabidkovac_katalog")) {
          navigate("/nabidkovac");
          return;
        }
        setMe(m);
        return nactiVse();
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else {
          setChyba(msg);
        }
      });
  }, [navigate]);

  async function ulozTech(data) {
    if (editace) await technologieUprav(editace.id, data);
    else await technologiePridej(data);
    setEditace(undefined);
    await nactiVse();
  }

  async function smazTech(t) {
    if (!window.confirm(`Smazat "${t.nazev}"?`)) return;
    await technologieSmaz(t.id);
    await nactiVse();
  }

  async function ulozNastaveni() {
    setNastavUklada(true);
    setNastavZprava(null);
    try {
      await vypoctovaNastaveniUloz({
        koeficient_zisku: num(koef),
        min_delka_kontraktu_roky: minRoky.trim() === "" ? null : parseInt(minRoky, 10),
        max_delka_kontraktu_roky: maxRoky.trim() === "" ? null : parseInt(maxRoky, 10),
        parametry: {},
      });
      await nactiVse();
      setNastavZprava("Uložena nová verze nastavení.");
    } catch (e) {
      setNastavZprava(e.message);
    } finally {
      setNastavUklada(false);
    }
  }

  if (chyba) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "#c92a2a" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !tech || !nastaveni) return null;

  const aktualni = nastaveni[0];

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="nb-app">
        <Link to="/nabidkovac" className="nb-backlink">← Zpět na Nabídkovač</Link>
        <div className="nb-head">
          <span className="nb-dot" />
          <h1>Katalog a výpočtová nastavení</h1>
        </div>
        <p className="nb-popis">Spravuje jen vedení/admin. Katalog se zatím plní ručně (napojení na Raynet přijde později).</p>

        {/* Katalog technologií */}
        <div className="nb-toolbar">
          <h3 style={{ margin: 0, fontSize: 15 }}>Katalog technologií</h3>
          <span className="nb-spacer" />
          <button className="fm-btn fm-primary" onClick={() => setEditace(null)}>+ Technologie</button>
        </div>
        <div className="nb-scroll" style={{ marginBottom: 24 }}>
          <table className="nb-table">
            <thead>
              <tr>
                <th>Typ</th><th>Název</th><th>Model</th><th>Výkon/kap.</th><th>Cena</th><th>Dostupná</th><th></th>
              </tr>
            </thead>
            <tbody>
              {tech.map((t) => (
                <tr key={t.id} onClick={() => setEditace(t)}>
                  <td>{NAZEV_TYPU[t.typ] || t.typ}</td>
                  <td>{t.nazev}</td>
                  <td>{t.model || "—"}</td>
                  <td>{t.vykon_kw != null ? `${t.vykon_kw} kW` : t.kapacita_kwh != null ? `${t.kapacita_kwh} kWh` : "—"}</td>
                  <td>{t.cena_kc != null ? `${t.cena_kc.toLocaleString("cs-CZ")} Kč` : "—"}</td>
                  <td>{t.dostupnost ? "Ano" : "Ne"}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="fm-btn" style={{ padding: "4px 10px", color: "#c92a2a" }} onClick={() => smazTech(t)}>Smazat</button>
                  </td>
                </tr>
              ))}
              {tech.length === 0 && (
                <tr><td colSpan={7} className="nb-empty">Katalog je zatím prázdný.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Výpočtová nastavení (verzovaná) */}
        <h3 style={{ margin: "0 0 6px", fontSize: 15 }}>Výpočtová nastavení</h3>
        <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 12px" }}>
          Uložení vytvoří <b>novou verzi</b> (stará zůstává kvůli dohledatelnosti, s jakými parametry se počítala konkrétní nabídka).
          {aktualni ? ` Aktuální je verze ${aktualni.verze}.` : " Zatím žádná verze – ulož první."}
        </p>
        <div className="fm-card" style={{ padding: 18, marginBottom: 16 }}>
          <div className="nb-form-grid">
            <div>
              <label className="nb-label">Koeficient zisku (marže PPA)</label>
              <input className="nb-pole" value={koef} onChange={(e) => setKoef(e.target.value)} inputMode="decimal" placeholder="např. 1.3" />
            </div>
            <div>
              <label className="nb-label">Min. délka kontraktu (roky)</label>
              <input className="nb-pole" value={minRoky} onChange={(e) => setMinRoky(e.target.value)} inputMode="numeric" placeholder="např. 10" />
            </div>
            <div>
              <label className="nb-label">Max. délka kontraktu (roky)</label>
              <input className="nb-pole" value={maxRoky} onChange={(e) => setMaxRoky(e.target.value)} inputMode="numeric" placeholder="např. 20" />
            </div>
          </div>
          {nastavZprava && <div style={{ fontSize: 13, marginTop: 10, color: "var(--fm-brand-dk)" }}>{nastavZprava}</div>}
          <div style={{ marginTop: 14 }}>
            <button className="fm-btn fm-primary" onClick={ulozNastaveni} disabled={nastavUklada}>
              {nastavUklada ? "Ukládám…" : "Uložit jako novou verzi"}
            </button>
          </div>
        </div>

        {nastaveni.length > 0 && (
          <div className="nb-scroll">
            <table className="nb-table">
              <thead>
                <tr><th>Verze</th><th>Koef. zisku</th><th>Min. roky</th><th>Max. roky</th><th>Platné od</th></tr>
              </thead>
              <tbody>
                {nastaveni.map((v) => (
                  <tr key={v.id} style={{ cursor: "default" }}>
                    <td><span className="nb-badge">v{v.verze}</span></td>
                    <td>{v.koeficient_zisku ?? "—"}</td>
                    <td>{v.min_delka_kontraktu_roky ?? "—"}</td>
                    <td>{v.max_delka_kontraktu_roky ?? "—"}</td>
                    <td>{String(v.platne_od || "").slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {editace !== undefined && (
        <TechEditor tech={editace} onSave={ulozTech} onClose={() => setEditace(undefined)} />
      )}
    </Layout>
  );
}
