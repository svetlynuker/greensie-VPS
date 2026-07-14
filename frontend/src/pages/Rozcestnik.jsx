import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Tile from "../components/Tile";
import { nactiMe, logout } from "../api";

// Dlaždice s hotovou sekcí vedou na svou stránku.
const TRASY = {
  projekty: "/projekty",
  admin: "/admin",
};

// Nedostupné (zamčené) a zatím rozpracované dlaždice vedou sem.
const VYVOJ_VIDEO = "https://youtu.be/oPLObjVAvIU";
// Výjimky: konkrétní dlaždice s vlastním odkazem.
const VIDEO_DLE_KLICE = {
  finance: "https://youtu.be/Q_L5CjNLh_o",
};

export default function Rozcestnik() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    nactiMe()
      .then((me) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setData(me);
      })
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
            zamceno={!d.muze_otevrit}
            onClick={() => {
              // hotová sekce, na kterou má uživatel právo → otevřít ji
              if (d.muze_otevrit && TRASY[d.klic]) {
                navigate(TRASY[d.klic]);
                return;
              }
              // nedostupné (zamčené) nebo zatím ve vývoji → proklik na video
              window.open(VIDEO_DLE_KLICE[d.klic] || VYVOJ_VIDEO, "_blank", "noopener,noreferrer");
            }}
          />
        ))}
      </div>
    </Layout>
  );
}
