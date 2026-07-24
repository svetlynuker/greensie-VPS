import { useLocation, useNavigate } from "react-router-dom";
import { logout } from "../api";
import ThemeToggle from "./ThemeToggle";
import CvdToggle from "./CvdToggle";
import VelikostTextu from "./VelikostTextu";
import Ikona from "./Ikona";

// Která stránka manuálu patří ke které routě (kontextová nápověda „?").
function strankaManualu(pathname) {
  if (pathname.startsWith("/projekty")) return "prehled-projektu";
  if (pathname.startsWith("/finance")) return "prehled-financi";
  if (pathname.startsWith("/zmeny")) return "prehled-zmen";
  if (pathname.startsWith("/nabidkovac")) return "nabidkovac";
  if (pathname.startsWith("/admin")) return "admin-nastaveni";
  if (pathname.startsWith("/logy")) return "logy";
  if (pathname.startsWith("/konektor")) return "konektor-raynet-gdrive";
  return "uvod";
}

export default function Layout({ uzivatel, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const naManualu = location.pathname.startsWith("/manual");

  return (
    <div style={{ padding: "16px" }}>
      <header className="gs-topbar">
        <span className="gs-brand-mark">
          <Ikona jmeno="logo" velikost={15} />
        </span>
        <span className="gs-brand-name">Greensie</span>
        <div className="gs-topbar-spacer" />
        <VelikostTextu />
        <ThemeToggle />
        <CvdToggle />
        {uzivatel && !naManualu && (
          <button
            className="fm-btn fm-ghost"
            title="Nápověda k této stránce"
            onClick={() => navigate(`/manual?stranka=${strankaManualu(location.pathname)}`)}
            style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
          >
            <Ikona jmeno="napoveda" velikost={16} />
            Nápověda
          </button>
        )}
        {uzivatel && (
          <>
            <span className="gs-topbar-who">{uzivatel.jmeno}</span>
            <button
              className="fm-btn"
              onClick={() => {
                logout();
                window.location.href = "/";
              }}
            >
              Odhlásit
            </button>
          </>
        )}
      </header>
      {children}
    </div>
  );
}
