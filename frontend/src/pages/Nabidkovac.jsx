import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { nactiMe, logout } from "../api";
import { PODSEKCE } from "../nabidkovac";
import "../styles/nabidkovac.css";

export default function Nabidkovac() {
  const [me, setMe] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    nactiMe()
      .then((m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        // dlaždice Nabídkovač je skrytá bez práva → sem se bez práva nedostane
        if (!m.prava?.includes("nabidkovac")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  if (!me) return null;
  const muzeKatalog = me.prava?.includes("nabidkovac_katalog");

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="nb-app">
        <Link to="/rozcestnik" className="nb-backlink">
          ← Zpět na rozcestník
        </Link>

        <div className="nb-toolbar">
          <div style={{ flex: 1 }}>
            <div className="nb-head">
              <span className="nb-dot" />
              <h1>Nabídkovač</h1>
            </div>
            <p className="nb-popis">
              Nástroj obchodních zástupců pro cenové nabídky ve třech produktových liniích.
              Vyber podsekci a založ novou nabídku. Jedna zakázka může nakonec vyústit ve víc
              navrhovaných řešení současně.
            </p>
          </div>
          {muzeKatalog && (
            <Link to="/nabidkovac/katalog" className="fm-btn">
              ⚙ Katalog a výpočty
            </Link>
          )}
        </div>

        <div className="nb-tiles">
          {PODSEKCE.map((s) => (
            <button
              key={s.klic}
              className="fm-card nb-tile"
              onClick={() => navigate(`/nabidkovac/${s.klic}`)}
            >
              <span className="nb-tile-nazev">{s.nazev}</span>
              <span className="nb-tile-popis">{s.popis}</span>
            </button>
          ))}
        </div>
      </div>
    </Layout>
  );
}
