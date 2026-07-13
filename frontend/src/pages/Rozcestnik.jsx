import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Tile from "../components/Tile";
import { nactiMe, logout } from "../api";

// Dlaždice s hotovou sekcí vedou na svou stránku; ostatní zatím ukážou placeholder.
const TRASY = {
  projekty: "/projekty",
};

export default function Rozcestnik() {
  const [data, setData] = useState(null);
  const [otevrenaDlazdice, setOtevrenaDlazdice] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    nactiMe()
      .then(setData)
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  if (!data) {
    return null;
  }

  return (
    <Layout uzivatel={data.uzivatel}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(var(--fm-tile-min-width), 1fr))",
          gap: "var(--fm-tile-gap)",
        }}
      >
        {data.dlazdice.map((d) => (
          <Tile
            key={d.klic}
            nazev={d.nazev}
            onClick={() =>
              TRASY[d.klic] ? navigate(TRASY[d.klic]) : setOtevrenaDlazdice(d.nazev)
            }
          />
        ))}
      </div>

      {otevrenaDlazdice && (
        <div
          onClick={() => setOtevrenaDlazdice(null)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(31,41,51,.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div
            className="fm-card"
            onClick={(e) => e.stopPropagation()}
            style={{ padding: 28, minWidth: 260, textAlign: "center" }}
          >
            <div style={{ fontWeight: 700, marginBottom: 8 }}>{otevrenaDlazdice}</div>
            <div style={{ color: "var(--fm-muted)", marginBottom: 16 }}>Připravujeme</div>
            <button className="fm-btn" onClick={() => setOtevrenaDlazdice(null)}>
              Zavřít
            </button>
          </div>
        </div>
      )}
    </Layout>
  );
}
