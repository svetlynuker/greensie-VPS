import { useLocation, useNavigate } from "react-router-dom";
import { aktivniKlic, nabidkaPro } from "../navigace";
import Ikona from "./Ikona";
import Logo from "./Logo";

// Levý navigační panel. Vidí jen to, na co má uživatel právo — sekce bez
// práva se neukazují vůbec (ani zamčené), takže se o nich uživatel nedozví.
export default function Sidebar({ prava, mini, onPrepnoutPanel }) {
  const location = useLocation();
  const navigate = useNavigate();
  const skupiny = nabidkaPro(prava);
  const aktivni = aktivniKlic(location.pathname);

  return (
    <aside className="gs-sb">
      <button
        className="gs-sb-brand"
        onClick={() => navigate("/rozcestnik")}
        title="Na úvodní stránku"
      >
        {/* Zúžený panel unese jen značku; v rozbaleném je logotyp celý.
            Text v logu přebírá barvu panelu (currentColor), značka zůstává
            firemně zelená. */}
        <Logo jen={mini ? "znacka" : "plne"} vyska={mini ? 28 : 23} title="Greensie" />
      </button>

      <nav className="gs-sb-scroll" aria-label="Hlavní nabídka">
        {skupiny.map((grp, i) => (
          <div key={grp.skupina || `grp-${i}`} data-barva={grp.barva || undefined}>
            {grp.skupina && <div className="gs-nav-grp-label">{grp.skupina}</div>}
            {grp.polozky.map((p) => (
              <button
                key={p.klic}
                className="gs-nav-item"
                aria-current={aktivni === p.klic ? "page" : undefined}
                onClick={() => navigate(p.cesta)}
              >
                <span className="gs-nav-ico">
                  <Ikona jmeno={p.ikona} velikost={18} />
                </span>
                <span className="gs-nav-txt">{p.nazev}</span>
              </button>
            ))}
          </div>
        ))}
      </nav>

      <div className="gs-sb-foot">
        <button
          className="gs-sb-collapse"
          onClick={onPrepnoutPanel}
          title={mini ? "Rozšířit panel" : "Zúžit panel na ikony"}
          aria-expanded={!mini}
        >
          <span className="gs-nav-ico">
            <Ikona jmeno="panel" velikost={17} />
          </span>
          <span className="gs-sb-foot-text">{mini ? "Rozšířit" : "Zúžit panel"}</span>
        </button>
      </div>
    </aside>
  );
}
