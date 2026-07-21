import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import NabidkaVystup from "../components/NabidkaVystup";
import NabidkaVystupEditor from "../components/NabidkaVystupEditor";
import { nactiMe, logout, nabidkaVystup, nabidkaVystupUloz } from "../api";
import "../styles/nabidkovac.css";
import "../styles/vystup.css";

const TYP_NAZEV = { ppa: "PPA", peak_shaving: "Peak shaving" };

export default function NabidkaVystupStranka() {
  const { id, typ } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [data, setData] = useState(null);
  const [konfigurace, setKonfigurace] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [uklada, setUklada] = useState(false);

  async function nacti(vychozi = false) {
    const d = await nabidkaVystup(id, typ, vychozi);
    setData(d);
    setKonfigurace(d.konfigurace);
    return d;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nabidkaVystup(id, typ)])
      .then(([m, d]) => {
        if (m.musi_zmenit_heslo) return navigate("/zmena-hesla");
        if (!m.prava?.includes("nabidkovac")) return navigate("/rozcestnik");
        setMe(m);
        setData(d);
        setKonfigurace(d.konfigurace);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, typ]);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    setZprava(null);
    try {
      const d = await nabidkaVystupUloz(id, typ, konfigurace);
      setData(d);
      setKonfigurace(d.konfigurace);
      setZprava("Uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function obnovVychozi() {
    if (!window.confirm("Obnovit výchozí předlohu? Neuložené i uložené úpravy této nabídky se přepíšou až po uložení.")) return;
    setChyba(null);
    setZprava(null);
    try {
      await nacti(true);
      setZprava("Načtena výchozí předloha – ulož ji tlačítkem Uložit.");
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !data) {
    return <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>;
  }
  if (!me || !data || !konfigurace) return null;

  return (
    <div className="vystup-page">
      <div className="vystup-bar np">
        <button className="fm-btn" onClick={() => navigate(`/nabidkovac/nabidka/${id}`)}>← Zpět na nabídku</button>
        <h1>Nabídka pro zákazníka · {TYP_NAZEV[typ] || typ}</h1>
        <span className="sp" />
        {zprava && <span style={{ color: "var(--fm-brand-dk)", fontSize: 13 }}>{zprava}</span>}
        {chyba && <span style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</span>}
        <button className="fm-btn" onClick={obnovVychozi}>Obnovit výchozí</button>
        <button className="fm-btn" onClick={uloz} disabled={uklada}>{uklada ? "Ukládám…" : "Uložit"}</button>
        <button className="fm-btn fm-primary" onClick={() => window.print()}>Uložit do PDF</button>
      </div>

      {!data.existuje_reseni && (
        <div className="nb-warn np" style={{ margin: "12px 20px 0" }}>
          <span>⚠️</span>
          <span>
            Pro tuto nabídku zatím není spočítané řešení „{TYP_NAZEV[typ] || typ}". Šablonu si můžeš
            připravit, ale čísla se doplní až po spuštění výpočtu v detailu nabídky.
          </span>
        </div>
      )}

      <div className="vystup-layout">
        <div className="vystup-editor np">
          <div style={{ fontSize: 12, color: "var(--fm-muted)", marginBottom: 8 }}>
            Zaškrtnutím zapneš blok, šipkami měníš pořadí, texty jsou volně editovatelné.
            V nabídce jsou dostupná jen zákaznická data.
          </div>
          <NabidkaVystupEditor
            konfigurace={konfigurace}
            katalog={data.katalog}
            onZmena={setKonfigurace}
          />
        </div>
        <div className="vystup-nahled-wrap">
          <NabidkaVystup data={data} konfigurace={konfigurace} />
        </div>
      </div>
    </div>
  );
}
