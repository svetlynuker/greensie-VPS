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
  sazbySeznam,
  sazbaPridej,
  sazbaUprav,
  sazbaSmaz,
  katalogSloupceSeznam,
  katalogSloupecPridej,
  katalogSloupecUprav,
  katalogSloupecSmaz,
} from "../api";
import "../styles/nabidkovac.css";

const TYPY_TECH = [
  { klic: "fve_panel", nazev: "FVE panel" },
  { klic: "invertor", nazev: "Invertor" },
  { klic: "baterie", nazev: "Baterie" },
  { klic: "jina", nazev: "Jiná" },
];
const NAZEV_TYPU = Object.fromEntries(TYPY_TECH.map((t) => [t.klic, t.nazev]));

// ---- Sazby distributorů (peak shaving) ----
const DISTRIB = [
  { klic: "cez", nazev: "ČEZ Distribuce" },
  { klic: "egd", nazev: "EG.D" },
  { klic: "pre", nazev: "PRE distribuce" },
];
const HLADINY = [
  { klic: "vn", nazev: "VN" },
  { klic: "vvn", nazev: "VVN" },
];
const STRUKTURY = [
  { klic: "stara_2026", nazev: "2026 (stará struktura)" },
  { klic: "nova_2027", nazev: "2027 (nová struktura ERÚ)" },
];
const NAZEV_DISTRIB = Object.fromEntries(DISTRIB.map((d) => [d.klic, d.nazev]));
const NAZEV_HLADINY = Object.fromEntries(HLADINY.map((h) => [h.klic, h.nazev]));
const NAZEV_STRUKTURY = Object.fromEntries(STRUKTURY.map((s) => [s.klic, s.nazev]));

// Parametry (ceny) podle struktury tarifu – klíče musí sedět s backendem.
const POLE_PARAMETRU = {
  stara_2026: [
    { klic: "cena_rezervovana_kapacita_kc_kw_rok", label: "Rezervovaná kapacita (Kč/kW/rok)" },
    { klic: "cena_prekroceni_kc_kw", label: "Pokuta za překročení (Kč/kW/měsíc)" },
  ],
  nova_2027: [
    { klic: "t1_kapacita_kc_kw_mesic", label: "Tarif T1 – kapacita (Kč/kW/měsíc)" },
    { klic: "t1_spicka_kc_kw_mesic", label: "Tarif T1 – špička (Kč/kW/měsíc)" },
    { klic: "t2_kapacita_kc_kw_mesic", label: "Tarif T2 – kapacita (Kč/kW/měsíc)" },
    { klic: "t2_spicka_kc_kw_mesic", label: "Tarif T2 – špička (Kč/kW/měsíc)" },
    { klic: "sazba_prekroceni_kc_kw_mesic", label: "Penalizace překročení RP (Kč/kW/měsíc)" },
    { klic: "u1_ucinnost", label: "Koeficient AKU – práh U1 (např. 0,60)" },
    { klic: "u2_ucinnost", label: "Koeficient AKU – práh U2 (0,75 VN / 0,70 VVN)" },
  ],
};

// PPA pro FVE – manažerské parametry ukládané do vypoctova_nastaveni.parametry
// (klíče musí sedět s backendem app/nabidkovac/routes.py `_ppa_param`).
const PPA_POLE = [
  { klic: "ppa_cena_fve_kc_kwp", label: "Cena za kWp (Kč/kWp)" },
  { klic: "ppa_ostatni_naklady_kc_kwp", label: "Ostatní náklady / BOS (Kč/kWp)" },
  { klic: "ppa_merny_vynos_kwh_kwp", label: "Měrný výnos FVE (kWh/kWp/rok)" },
  { klic: "ppa_cil_mira_samospotreby", label: "Cíl samospotřeby pro návrh velikosti (např. 0.80)" },
  { klic: "ppa_index_ceny_rocni", label: "Index PPA ceny (%/rok, např. 0.03)" },
  { klic: "ppa_index_dodavatel_rocni", label: "Index ceny dodavatele (%/rok)" },
  { klic: "ppa_index_prebytek_rocni", label: "Index ceny přebytku (%/rok)" },
  { klic: "ppa_degradace_rocni", label: "Degradace panelů (%/rok, např. 0.005)" },
  { klic: "ppa_oam_kc_kwp_rok", label: "O&M (Kč/kWp/rok)" },
  { klic: "ppa_diskontni_sazba", label: "Diskontní sazba NPV/IRR (např. 0.05)" },
];

function num(v) {
  return v.trim() === "" ? null : Number(v.replace(",", "."));
}
function str(v) {
  return v == null ? "" : String(v);
}

// Kompaktní shrnutí cen sazby do buňky tabulky.
function shrnParametry(s) {
  if (s.parametry == null) return "čeká se na sazby ERÚ";
  const pole = POLE_PARAMETRU[s.struktura_tarifu] || [];
  const casti = pole.map((p) => {
    const v = s.parametry[p.klic];
    return `${p.label}: ${v == null ? "—" : Number(v).toLocaleString("cs-CZ")}`;
  });
  return casti.join(" · ");
}

/* ---------- modal editoru technologie ---------- */
function TechEditor({ tech, sloupce, onSave, onClose }) {
  const [typ, setTyp] = useState(tech?.typ || "fve_panel");
  const [nazev, setNazev] = useState(tech?.nazev || "");
  const [model, setModel] = useState(tech?.model || "");
  const [vykon, setVykon] = useState(str(tech?.vykon_kw));
  const [kapacita, setKapacita] = useState(str(tech?.kapacita_kwh));
  const [cena, setCena] = useState(str(tech?.cena_kc));
  const [ucinnost, setUcinnost] = useState(str(tech?.ucinnost));
  const [dostupnost, setDostupnost] = useState(tech?.dostupnost ?? true);
  // Hodnoty vlastních sloupců (mapa klíč→text pro input).
  const [extra, setExtra] = useState(() => {
    const e = tech?.extra || {};
    return Object.fromEntries((sloupce || []).map((s) => [s.klic, str(e[s.klic])]));
  });
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  function nastavExtra(klic, hodnota) {
    setExtra((e) => ({ ...e, [klic]: hodnota }));
  }

  async function uloz() {
    if (!nazev.trim()) {
      setChyba("Název je povinný.");
      return;
    }
    // Prázdné hodnoty vynecháme, číselné pošleme jako string (backend převede).
    const extraOut = {};
    for (const s of sloupce || []) {
      const v = (extra[s.klic] ?? "").trim();
      if (v !== "") extraOut[s.klic] = v;
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
        extra: extraOut,
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
        {(sloupce || []).length > 0 && (
          <div className="nb-form-grid">
            {sloupce.map((s) => (
              <div key={s.klic}>
                <label className="nb-label">{s.nazev}{s.typ === "cislo" ? " (číslo)" : ""}</label>
                <input
                  className="nb-pole"
                  value={extra[s.klic] ?? ""}
                  onChange={(e) => nastavExtra(s.klic, e.target.value)}
                  inputMode={s.typ === "cislo" ? "decimal" : "text"}
                />
              </div>
            ))}
          </div>
        )}
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

/* ---------- modal editoru vlastního sloupce ---------- */
function SloupecEditor({ sloupec, onSave, onClose }) {
  const [nazev, setNazev] = useState(sloupec?.nazev || "");
  const [typ, setTyp] = useState(sloupec?.typ || "text");
  const [poradi, setPoradi] = useState(str(sloupec?.poradi ?? ""));
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    if (!nazev.trim()) {
      setChyba("Název sloupce je povinný.");
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        nazev: nazev.trim(),
        typ,
        poradi: poradi.trim() === "" ? 0 : parseInt(poradi, 10),
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
      <div className="fm-card" onClick={(e) => e.stopPropagation()} style={{ padding: 20, width: "min(420px, 100%)", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{sloupec ? "Upravit sloupec" : "Nový vlastní sloupec"}</h3>
        <div>
          <label className="nb-label">Název sloupce</label>
          <input className="nb-pole" value={nazev} onChange={(e) => setNazev(e.target.value)} placeholder="např. Záruka (roky)" />
        </div>
        <div className="nb-form-grid">
          <div>
            <label className="nb-label">Typ hodnoty</label>
            <select className="nb-pole" value={typ} onChange={(e) => setTyp(e.target.value)}>
              <option value="text">Text</option>
              <option value="cislo">Číslo</option>
            </select>
          </div>
          <div>
            <label className="nb-label">Pořadí</label>
            <input className="nb-pole" value={poradi} onChange={(e) => setPoradi(e.target.value)} inputMode="numeric" placeholder="0" />
          </div>
        </div>
        {sloupec && (
          <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: 0 }}>
            Přejmenování a změna typu se projeví hned; už uložené hodnoty zůstávají.
          </p>
        )}
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

/* ---------- modal editoru sazby distributora ---------- */
function SazbaEditor({ sazba, onSave, onClose }) {
  const [distributor, setDistributor] = useState(sazba?.distributor || "cez");
  const [hladina, setHladina] = useState(sazba?.napetova_hladina || "vn");
  const [struktura, setStruktura] = useState(sazba?.struktura_tarifu || "stara_2026");
  const [platneOd, setPlatneOd] = useState((sazba?.platne_od || "").slice(0, 10));
  const [platneDo, setPlatneDo] = useState((sazba?.platne_do || "").slice(0, 10));
  const [poznamka, setPoznamka] = useState(sazba?.poznamka || "");
  const [modelovy, setModelovy] = useState(sazba?.je_modelovy_odhad ?? false);
  // Ceny drží jako mapu textových inputů podle klíče. `null` u sazby = ceny zatím nejsou.
  const [cekaNaEru, setCekaNaEru] = useState(sazba ? sazba.parametry == null : false);
  const [ceny, setCeny] = useState(() => {
    const p = sazba?.parametry || {};
    return Object.fromEntries(
      Object.entries(p).map(([k, v]) => [k, v == null ? "" : String(v)])
    );
  });
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  const pole = POLE_PARAMETRU[struktura] || [];

  function nastavCenu(klic, hodnota) {
    setCeny((c) => ({ ...c, [klic]: hodnota }));
  }

  async function uloz() {
    if (!platneOd) {
      setChyba("Datum „platné od“ je povinné.");
      return;
    }
    let parametry = null;
    if (!cekaNaEru) {
      // Poskládej objekt s klíči dané struktury; prázdné pole = null
      // (např. ČEZ VVN má vyplněnou jen pokutu, rezervace zůstává null).
      parametry = {};
      for (const p of pole) {
        parametry[p.klic] = num(ceny[p.klic] ?? "");
      }
    }
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        distributor,
        napetova_hladina: hladina,
        struktura_tarifu: struktura,
        parametry,
        platne_od: platneOd,
        platne_do: platneDo || null,
        je_modelovy_odhad: modelovy,
        poznamka: poznamka.trim(),
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
      <div className="fm-card" onClick={(e) => e.stopPropagation()} style={{ padding: 20, width: "min(520px, 100%)", maxHeight: "90vh", overflowY: "auto", display: "flex", flexDirection: "column", gap: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>{sazba ? "Upravit sazbu" : "Nová sazba distributora"}</h3>
        <div className="nb-form-grid">
          <div>
            <label className="nb-label">Distributor</label>
            <select className="nb-pole" value={distributor} onChange={(e) => setDistributor(e.target.value)}>
              {DISTRIB.map((d) => <option key={d.klic} value={d.klic}>{d.nazev}</option>)}
            </select>
          </div>
          <div>
            <label className="nb-label">Napěťová hladina</label>
            <select className="nb-pole" value={hladina} onChange={(e) => setHladina(e.target.value)}>
              {HLADINY.map((h) => <option key={h.klic} value={h.klic}>{h.nazev}</option>)}
            </select>
          </div>
          <div>
            <label className="nb-label">Struktura tarifu</label>
            <select className="nb-pole" value={struktura} onChange={(e) => setStruktura(e.target.value)}>
              {STRUKTURY.map((s) => <option key={s.klic} value={s.klic}>{s.nazev}</option>)}
            </select>
          </div>
          <div>
            <label className="nb-label">Platné od</label>
            <input type="date" className="nb-pole" value={platneOd} onChange={(e) => setPlatneOd(e.target.value)} />
          </div>
          <div>
            <label className="nb-label">Platné do (volitelné)</label>
            <input type="date" className="nb-pole" value={platneDo} onChange={(e) => setPlatneDo(e.target.value)} />
          </div>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <input type="checkbox" checked={cekaNaEru} onChange={(e) => setCekaNaEru(e.target.checked)} />
          Ceny zatím nejsou (čeká se na sazby ERÚ)
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <input type="checkbox" checked={modelovy} onChange={(e) => setModelovy(e.target.checked)} />
          Modelový odhad (nezávazné ceny, typicky struktura 2027)
        </label>

        {!cekaNaEru && (
          <div className="nb-form-grid">
            {pole.map((p) => (
              <div key={p.klic}>
                <label className="nb-label">{p.label}</label>
                <input className="nb-pole" value={ceny[p.klic] ?? ""} onChange={(e) => nastavCenu(p.klic, e.target.value)} inputMode="decimal" placeholder="prázdné = nedohledáno" />
              </div>
            ))}
          </div>
        )}

        <div>
          <label className="nb-label">Poznámka (zdroj / ověření)</label>
          <input className="nb-pole" value={poznamka} onChange={(e) => setPoznamka(e.target.value)} />
        </div>

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
  const [sazby, setSazby] = useState(null);
  const [sloupce, setSloupce] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [editace, setEditace] = useState(undefined); // undefined = zavřeno, null = nová, obj = úprava
  const [editaceSazby, setEditaceSazby] = useState(undefined);
  const [editaceSloupce, setEditaceSloupce] = useState(undefined);

  // formulář výpočtových nastavení (nová verze)
  const [koef, setKoef] = useState("");
  const [minRoky, setMinRoky] = useState("");
  const [maxRoky, setMaxRoky] = useState("");
  const [ppaParam, setPpaParam] = useState({});
  const [nastavZprava, setNastavZprava] = useState(null);
  const [nastavUklada, setNastavUklada] = useState(false);

  async function nactiVse() {
    const [ts, ns, sz, sl] = await Promise.all([
      technologieSeznam(),
      vypoctovaNastaveniSeznam(),
      sazbySeznam(),
      katalogSloupceSeznam(),
    ]);
    setTech(ts);
    setNastaveni(ns);
    setSazby(sz);
    setSloupce(sl);
    const akt = ns[0];
    setKoef(str(akt?.koeficient_zisku));
    setMinRoky(str(akt?.min_delka_kontraktu_roky));
    setMaxRoky(str(akt?.max_delka_kontraktu_roky));
    const p = akt?.parametry || {};
    setPpaParam(Object.fromEntries(PPA_POLE.map((f) => [f.klic, p[f.klic] == null ? "" : String(p[f.klic])])));
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

  async function ulozSazbu(data) {
    if (editaceSazby) await sazbaUprav(editaceSazby.id, data);
    else await sazbaPridej(data);
    setEditaceSazby(undefined);
    await nactiVse();
  }

  async function smazSazbu(s) {
    if (!window.confirm(`Smazat sazbu ${NAZEV_DISTRIB[s.distributor]} / ${NAZEV_HLADINY[s.napetova_hladina]} / ${NAZEV_STRUKTURY[s.struktura_tarifu]}?`)) return;
    await sazbaSmaz(s.id);
    await nactiVse();
  }

  async function ulozSloupec(data) {
    if (editaceSloupce) await katalogSloupecUprav(editaceSloupce.id, data);
    else await katalogSloupecPridej(data);
    setEditaceSloupce(undefined);
    await nactiVse();
  }

  async function smazSloupec(s) {
    if (!window.confirm(`Smazat sloupec "${s.nazev}"? Uložené hodnoty se přestanou zobrazovat.`)) return;
    await katalogSloupecSmaz(s.id);
    await nactiVse();
  }

  async function ulozNastaveni() {
    setNastavUklada(true);
    setNastavZprava(null);
    try {
      // Zachovej existující klíče parametrů (např. max_navratnost_roky_peak_shaving)
      // a přepiš/doplň jen PPA pole; prázdné pole klíč odebere.
      const parametry = { ...(nastaveni?.[0]?.parametry || {}) };
      for (const f of PPA_POLE) {
        const val = num(ppaParam[f.klic] ?? "");
        if (val == null) delete parametry[f.klic];
        else parametry[f.klic] = val;
      }
      await vypoctovaNastaveniUloz({
        koeficient_zisku: num(koef),
        min_delka_kontraktu_roky: minRoky.trim() === "" ? null : parseInt(minRoky, 10),
        max_delka_kontraktu_roky: maxRoky.trim() === "" ? null : parseInt(maxRoky, 10),
        parametry,
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
  if (!me || !tech || !nastaveni || !sazby || !sloupce) return null;

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
          <button className="fm-btn" onClick={() => setEditaceSloupce(null)}>+ Sloupec</button>
          <button className="fm-btn fm-primary" onClick={() => setEditace(null)}>+ Technologie</button>
        </div>
        {sloupce.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", margin: "0 0 12px" }}>
            <span style={{ fontSize: 12, color: "var(--fm-muted)" }}>Vlastní sloupce:</span>
            {sloupce.map((s) => (
              <span key={s.klic} className="nb-badge" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <button
                  onClick={() => setEditaceSloupce(s)}
                  title="Upravit sloupec"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", font: "inherit", color: "inherit" }}
                >
                  {s.nazev}{s.typ === "cislo" ? " (č.)" : ""}
                </button>
                <button
                  onClick={() => smazSloupec(s)}
                  title="Smazat sloupec"
                  style={{ background: "none", border: "none", padding: 0, cursor: "pointer", color: "#c92a2a", fontWeight: 700 }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="nb-scroll" style={{ marginBottom: 24 }}>
          <table className="nb-table">
            <thead>
              <tr>
                <th>Typ</th><th>Název</th><th>Model</th><th>Výkon (kW)</th><th>Kapacita (kWh)</th><th>Cena</th><th>Dostupná</th>
                {sloupce.map((s) => <th key={s.klic}>{s.nazev}</th>)}
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tech.map((t) => (
                <tr key={t.id} onClick={() => setEditace(t)}>
                  <td>{NAZEV_TYPU[t.typ] || t.typ}</td>
                  <td>{t.nazev}</td>
                  <td>{t.model || "—"}</td>
                  <td>{t.vykon_kw != null ? t.vykon_kw.toLocaleString("cs-CZ") : "—"}</td>
                  <td>{t.kapacita_kwh != null ? t.kapacita_kwh.toLocaleString("cs-CZ") : "—"}</td>
                  <td>{t.cena_kc != null ? `${t.cena_kc.toLocaleString("cs-CZ")} Kč` : "—"}</td>
                  <td>{t.dostupnost ? "Ano" : "Ne"}</td>
                  {sloupce.map((s) => {
                    const v = t.extra?.[s.klic];
                    return (
                      <td key={s.klic}>
                        {v == null || v === ""
                          ? "—"
                          : s.typ === "cislo" && typeof v === "number"
                          ? v.toLocaleString("cs-CZ")
                          : String(v)}
                      </td>
                    );
                  })}
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="fm-btn" style={{ padding: "4px 10px", color: "#c92a2a" }} onClick={() => smazTech(t)}>Smazat</button>
                  </td>
                </tr>
              ))}
              {tech.length === 0 && (
                <tr><td colSpan={8 + sloupce.length} className="nb-empty">Katalog je zatím prázdný.</td></tr>
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

          <div style={{ marginTop: 16, marginBottom: 4, fontSize: 13, fontWeight: 600 }}>PPA pro FVE – náklady a defaulty</div>
          <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 10px" }}>
            Cena za kWp (zjednodušený režim CAPEX), degradace, indexy eskalace a další výchozí hodnoty PPA výpočtu. OZ je u konkrétní nabídky může přepsat. Prázdné pole = použije se kódový default.
          </p>
          <div className="nb-form-grid">
            {PPA_POLE.map((f) => (
              <div key={f.klic}>
                <label className="nb-label">{f.label}</label>
                <input
                  className="nb-pole"
                  value={ppaParam[f.klic] ?? ""}
                  onChange={(e) => setPpaParam((s) => ({ ...s, [f.klic]: e.target.value }))}
                  inputMode="decimal"
                />
              </div>
            ))}
          </div>

          {nastavZprava && <div style={{ fontSize: 13, marginTop: 10, color: "var(--fm-brand-dk)" }}>{nastavZprava}</div>}
          <div style={{ marginTop: 14 }}>
            <button className="fm-btn fm-primary" onClick={ulozNastaveni} disabled={nastavUklada}>
              {nastavUklada ? "Ukládám…" : "Uložit jako novou verzi"}
            </button>
          </div>
        </div>

        {nastaveni.length > 0 && (
          <div className="nb-scroll" style={{ marginBottom: 24 }}>
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

        {/* Sazby distributorů (peak shaving) */}
        <div className="nb-toolbar">
          <h3 style={{ margin: 0, fontSize: 15 }}>Sazby distributorů (peak shaving)</h3>
          <span className="nb-spacer" />
          <button className="fm-btn fm-primary" onClick={() => setEditaceSazby(null)}>+ Sazba</button>
        </div>
        <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 12px" }}>
          Ceny bez DPH. Naostro jede zatím jen ČEZ Distribuce 2026 – EG.D, PRE a sazby 2027
          (nová struktura ERÚ) se doplní tady, až budou čísla ověřená, resp. zveřejněná.
        </p>
        <div className="nb-scroll">
          <table className="nb-table">
            <thead>
              <tr>
                <th>Distributor</th><th>Hladina</th><th>Struktura</th><th>Ceny</th><th>Platnost</th><th></th>
              </tr>
            </thead>
            <tbody>
              {sazby.map((s) => (
                <tr key={s.id} onClick={() => setEditaceSazby(s)}>
                  <td>{NAZEV_DISTRIB[s.distributor] || s.distributor}</td>
                  <td>{NAZEV_HLADINY[s.napetova_hladina] || s.napetova_hladina}</td>
                  <td>
                    {NAZEV_STRUKTURY[s.struktura_tarifu] || s.struktura_tarifu}
                    {s.je_modelovy_odhad && (
                      <span className="nb-badge" style={{ marginLeft: 6 }} title="Nezávazný odhad, ne finální cena ERÚ">
                        modelový odhad
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: 12, color: s.parametry == null ? "var(--fm-muted)" : undefined }}>
                    {shrnParametry(s)}
                  </td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {String(s.platne_od || "").slice(0, 10)}
                    {s.platne_do ? ` – ${String(s.platne_do).slice(0, 10)}` : ""}
                  </td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <button className="fm-btn" style={{ padding: "4px 10px", color: "#c92a2a" }} onClick={() => smazSazbu(s)}>Smazat</button>
                  </td>
                </tr>
              ))}
              {sazby.length === 0 && (
                <tr><td colSpan={6} className="nb-empty">Zatím žádné sazby.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editace !== undefined && (
        <TechEditor tech={editace} sloupce={sloupce} onSave={ulozTech} onClose={() => setEditace(undefined)} />
      )}
      {editaceSloupce !== undefined && (
        <SloupecEditor sloupec={editaceSloupce} onSave={ulozSloupec} onClose={() => setEditaceSloupce(undefined)} />
      )}
      {editaceSazby !== undefined && (
        <SazbaEditor sazba={editaceSazby} onSave={ulozSazbu} onClose={() => setEditaceSazby(undefined)} />
      )}
    </Layout>
  );
}
