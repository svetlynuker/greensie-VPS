import { logout } from "../api";
import ThemeToggle from "./ThemeToggle";
import CvdToggle from "./CvdToggle";
import VelikostTextu from "./VelikostTextu";
import Ikona from "./Ikona";

export default function Layout({ uzivatel, children }) {
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
