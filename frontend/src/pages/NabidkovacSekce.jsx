import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import { nactiMe, logout, nabidkySeznam, nabidkaZaloz } from "../api";
import { PODSEKCE, STAV_NABIDKY, fmtDatum } from "../nabidkovac";
import "../styles/nabidkovac.css";

export default function NabidkovacSekce() {
  const { typ } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [nabidky, setNabidky] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [zaklada, setZaklada] = useState(false);

  const sekce = PODSEKCE.find((s) => s.klic === typ);

  useEffect(() => {
    if (!sekce) {
      navigate("/nabidkovac");
      return;
    }
    Promise.all([nactiMe(), nabidkySeznam(typ)])
      .then(([m, list]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("nabidkovac")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setNabidky(list);
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
  }, [typ, sekce, navigate]);

  async function novaNabidka() {
    setZaklada(true);
    setChyba(null);
    try {
      const n = await nabidkaZaloz({ typ });
      navigate(`/nabidkovac/nabidka/${n.id}`);
    } catch (e) {
      setChyba(e.message);
      setZaklada(false);
    }
  }

  if (!sekce) return null;
  if (chyba) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "#c92a2a" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !nabidky) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="nb-app">
        <Link to="/nabidkovac" className="nb-backlink">
          ← Zpět na Nabídkovač
        </Link>

        <div className="nb-head">
          <span className="nb-dot" />
          <h1>{sekce.nazev}</h1>
        </div>
        <p className="nb-popis">{sekce.popis}</p>

        {/* Jasně viditelné: výpočet se teprve staví (kap. 2 SPEC) */}
        <div className="nb-warn">
          <span>⚠️</span>
          <span>
            Výpočet zatím není aktivní. Tahle část se staví – zástupný výstup není reálná nabídka.
            Zatím lze zakládat nabídky a nahrávat podklady; sizing, ROI a generování PDF přijdou
            v dalších krocích.
          </span>
        </div>

        <div className="nb-toolbar">
          <button className="fm-btn fm-primary" onClick={novaNabidka} disabled={zaklada}>
            {zaklada ? "Zakládám…" : "+ Nová nabídka"}
          </button>
          <span className="nb-spacer" />
          <span style={{ fontSize: 13, color: "var(--fm-muted)" }}>
            <b>{nabidky.length}</b> nabídek
          </span>
        </div>

        <div className="nb-scroll">
          <table className="nb-table">
            <thead>
              <tr>
                <th>Zákazník</th>
                <th>Stav</th>
                <th>Vytvořil</th>
                <th>Datum</th>
              </tr>
            </thead>
            <tbody>
              {nabidky.map((n) => (
                <tr key={n.id} onClick={() => navigate(`/nabidkovac/nabidka/${n.id}`)}>
                  <td>{n.zakaznik_nazev}</td>
                  <td>
                    <span className="nb-badge">{STAV_NABIDKY[n.stav] || n.stav}</span>
                  </td>
                  <td>{n.vytvoril_jmeno || "—"}</td>
                  <td>{fmtDatum(n.vytvoreno_at)}</td>
                </tr>
              ))}
              {nabidky.length === 0 && (
                <tr>
                  <td colSpan={4} className="nb-empty">
                    Zatím žádné nabídky. Založ první přes „+ Nová nabídka".
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
}
