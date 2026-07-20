import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Tile from "../components/Tile";
import { nactiMe, logout } from "../api";

// Dlaždice s hotovou sekcí vedou na svou stránku.
const TRASY = {
  projekty: "/projekty",
  finance: "/finance",
  nabidkovac: "/nabidkovac",
  admin: "/admin",
  logy: "/logy",
};

// Vzhled dlaždic: ikona + podtitulek dle klíče modulu.
const IKONY = {
  projekty: "projekty",
  finance: "finance",
  zmeny: "zmeny",
  nabidkovac: "nabidkovac",
  admin: "admin",
  logy: "logy",
};
const PODTITULY = {
  projekty: "Matice úkolů a fází ze Freela",
  finance: "Faktury k projektům, párování POHODA",
  zmeny: "Připravujeme",
  nabidkovac: "Nabídky FVE, PPA a peak shaving",
  admin: "Uživatelé, skupiny a oprávnění",
  logy: "Provoz serveru, chyby a kdo co udělal",
};

// Nedostupné (zamčené) a zatím rozpracované dlaždice vedou sem.
const VYVOJ_VIDEO = "https://youtu.be/oPLObjVAvIU";
// Výjimky: konkrétní dlaždice s vlastním odkazem.
const VIDEO_DLE_KLICE = {};

// Dlaždice, které se uživateli bez práva ÚPLNĚ SKRYJÍ (dle SPEC kap. 2 a 4),
// místo aby se jen zamkly. Zatím jen finance (Přehled financí – jen Rosťa/vedení).
const SKRYT_BEZ_PRAVA = new Set(["finance", "nabidkovac", "logy"]);

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
        {data.dlazdice
          .filter((d) => d.muze_otevrit || !SKRYT_BEZ_PRAVA.has(d.klic))
          .map((d) => (
          <Tile
            key={d.klic}
            nazev={d.nazev}
            popis={PODTITULY[d.klic]}
            ikona={IKONY[d.klic] || "projekty"}
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
