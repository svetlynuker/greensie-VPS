import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import DokumentUpload from "../components/DokumentUpload";
import PeakShavingPanel from "../components/PeakShavingPanel";
import PpaPanel from "../components/PpaPanel";
import { nactiMe, logout, nabidkaDetail, nabidkaUprav, nabidkaSmaz } from "../api";
import { PODSEKCE, STAV_NABIDKY, fmtDatum } from "../nabidkovac";
import "../styles/nabidkovac.css";

export default function NabidkaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [nabidka, setNabidka] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [zprava, setZprava] = useState(null);

  // editovatelná pole zákazníka
  const [nazev, setNazev] = useState("");
  const [adresa, setAdresa] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");

  function naplnFormular(n) {
    setNazev(n.zakaznik_nazev || "");
    setAdresa(n.zakaznik_adresa || "");
    setLat(n.zakaznik_gps_lat != null ? String(n.zakaznik_gps_lat) : "");
    setLng(n.zakaznik_gps_lng != null ? String(n.zakaznik_gps_lng) : "");
  }

  async function nactiZnovu() {
    const n = await nabidkaDetail(id);
    setNabidka(n);
    return n;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nabidkaDetail(id)])
      .then(([m, n]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("nabidkovac")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setNabidka(n);
        naplnFormular(n);
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (msg.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(msg);
        }
      });
  }, [id, navigate]);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    setZprava(null);
    try {
      const n = await nabidkaUprav(id, {
        zakaznik_nazev: nazev.trim(),
        zakaznik_adresa: adresa.trim(),
        zakaznik_gps_lat: lat.trim() === "" ? null : Number(lat.replace(",", ".")),
        zakaznik_gps_lng: lng.trim() === "" ? null : Number(lng.replace(",", ".")),
      });
      setNabidka(n);
      setZprava("Uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function smaz() {
    if (!window.confirm("Opravdu smazat celou nabídku včetně nahraných dokumentů?")) return;
    try {
      await nabidkaSmaz(id);
      navigate(`/nabidkovac/${nabidka.typ}`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !nabidka) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !nabidka) return null;

  const sekce = PODSEKCE.find((s) => s.klic === nabidka.typ);

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="nb-app">
        <Link to={`/nabidkovac/${nabidka.typ}`} className="nb-backlink">
          ← Zpět na {sekce?.nazev || "seznam"}
        </Link>

        <div className="nb-head">
          <span className="nb-dot" />
          <h1>{nabidka.zakaznik_nazev || "Nová nabídka"}</h1>
          <span className="nb-badge" style={{ marginLeft: 8 }}>
            {sekce?.nazev || nabidka.typ}
          </span>
          <span className="nb-badge">{STAV_NABIDKY[nabidka.stav] || nabidka.stav}</span>
        </div>
        <p className="nb-popis">
          Založil {nabidka.vytvoril_jmeno || "—"} · {fmtDatum(nabidka.vytvoreno_at)}
        </p>

        {/* Zákazník */}
        <div className="fm-card" style={{ padding: 18, marginBottom: 16 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>Zákazník</h3>
          <div className="nb-form-grid">
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="nb-label">Název zákazníka</label>
              <input className="nb-pole" value={nazev} onChange={(e) => setNazev(e.target.value)} placeholder="např. Firma s.r.o." />
            </div>
            <div style={{ gridColumn: "1 / -1" }}>
              <label className="nb-label">Adresa</label>
              <input className="nb-pole" value={adresa} onChange={(e) => setAdresa(e.target.value)} placeholder="Ulice, město" />
            </div>
            <div>
              <label className="nb-label">GPS šířka (lat) – pro budoucí PVGIS</label>
              <input className="nb-pole" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="např. 50.087" inputMode="decimal" />
            </div>
            <div>
              <label className="nb-label">GPS délka (lng) – pro budoucí PVGIS</label>
              <input className="nb-pole" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="např. 14.421" inputMode="decimal" />
            </div>
          </div>
          {zprava && <div style={{ color: "var(--fm-brand-dk)", fontSize: 13, marginTop: 10 }}>{zprava}</div>}
          {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}
          <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
            <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
              {uklada ? "Ukládám…" : "Uložit"}
            </button>
            <span style={{ flex: 1 }} />
            <button className="fm-btn" style={{ color: "var(--st-crit)" }} onClick={smaz}>
              Smazat nabídku
            </button>
          </div>
        </div>

        {/* Dokumenty */}
        <div className="fm-card" style={{ padding: 18, marginBottom: 16 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 14 }}>Podklady</h3>
          <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 12px" }}>
            Nahraj fakturu za elektřinu (PDF) a/nebo diagram spotřeby (CSV). Soubory se zatím jen
            uloží – automatické zpracování (extrakce z faktury, parsování spotřeby) se připravuje.
          </p>
          <DokumentUpload nabidkaId={nabidka.id} dokumenty={nabidka.dokumenty} onZmena={nactiZnovu} />
        </div>

        {/* Navržená řešení */}
        {nabidka.typ === "peak_shaving" ? (
          <PeakShavingPanel nabidka={nabidka} />
        ) : nabidka.typ === "ppa" ? (
          <PpaPanel nabidka={nabidka} />
        ) : (
          <div className="fm-card" style={{ padding: 18 }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Navržená řešení</h3>
            <div className="nb-warn" style={{ margin: 0 }}>
              <span>⚠️</span>
              <span>
                Výpočet zatím není aktivní. Až bude doladěná metodika, tady se objeví navržená řešení
                (velikost elektrárny/baterie, cena, délka kontraktu, ROI) – i víc variant najednou.
              </span>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
