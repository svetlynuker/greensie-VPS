import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { nactiMeSdilene } from "../api";
import { popisStranky, strankaManualu } from "../navigace";
import Ikona from "./Ikona";
import Sidebar from "./Sidebar";
import UserMenu from "./UserMenu";
import GlobalniHledani from "./GlobalniHledani";
import Zvonecek from "./Zvonecek";

// Zúžení panelu si pamatujeme lokálně — je to volba zařízení (malý notebook),
// ne uživatele, takže se do DB neposílá.
const KLIC_PANEL = "greensie_panel";

// Supersprávce má v backendu vždy všechna práva (permissions.prava_uzivatele);
// tohle je jen náhrada, dokud nedojde odpověď /auth/me, ať panel neproblikne.
const VSECHNA_PRAVA = [
  "projekty",
  "finance",
  "zmeny",
  "nabidkovac",
  "nabidkovac_katalog",
  "admin",
  "editace",
  "logy",
  "konektor",
];

function panelZPameti() {
  return localStorage.getItem(KLIC_PANEL) === "mini" ? "mini" : "expanded";
}

// Rámec appky: navigace vlevo, lišta nahoře, obsah stránky uvnitř.
// Stránky dál posílají `uzivatel` (kvůli okamžitému vykreslení jména);
// práva pro nabídku si rámec dotáhne sám ze sdíleného /auth/me.
export default function Layout({ uzivatel, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [panel, setPanel] = useState(panelZPameti);

  useEffect(() => {
    let zivy = true;
    nactiMeSdilene()
      .then((data) => {
        if (zivy) setMe(data);
      })
      .catch(() => {
        // Rámec se kvůli tomu neodhlašuje — o vypršené přihlášení se
        // stará samotná stránka, která si data načítá taky.
      });
    return () => {
      zivy = false;
    };
  }, []);

  function prepnoutPanel() {
    setPanel((p) => {
      const novy = p === "mini" ? "expanded" : "mini";
      localStorage.setItem(KLIC_PANEL, novy);
      return novy;
    });
  }

  const naManualu = location.pathname.startsWith("/manual");
  const [nazev, podnazev] = popisStranky(location.pathname);
  // Dokud se práva nenačtou, kreslíme nabídku podle toho, co víme z prop
  // (supersprávce vidí vše) — ať panel neproblikne prázdný.
  const prava = me?.prava || (uzivatel?.je_admin ? VSECHNA_PRAVA : []);
  const kdo = me?.uzivatel || uzivatel;

  return (
    <div className="gs-app" data-panel={panel}>
      <Sidebar
        prava={prava}
        novinky={Boolean(me?.novinky)}
        mini={panel === "mini"}
        onPrepnoutPanel={prepnoutPanel}
      />

      <div className="gs-main">
        <header className="gs-tb">
          <span className="gs-tb-title">{nazev}</span>
          {podnazev && <span className="gs-tb-crumb">{podnazev}</span>}
          <span className="gs-tb-spacer" />

          {kdo && !naManualu && (
            <button
              className="gs-icon-btn"
              title="Nápověda k této stránce"
              aria-label="Nápověda k této stránce"
              onClick={() => navigate(`/manual?stranka=${strankaManualu(location.pathname)}`)}
            >
              <Ikona jmeno="napoveda" velikost={16} />
            </button>
          )}

          {kdo && (
            <>
              <GlobalniHledani />
              {/* Zvoneček (CRM-10) — vedle hledání, před uživatelským menu.
                  Zatím jen pro ty, komu se ukazují novinky (crm/novinky.py). */}
              {me?.novinky && <Zvonecek />}
              <UserMenu uzivatel={kdo} prava={prava} />
            </>
          )}
        </header>

        <main className="gs-obsah">{children}</main>
      </div>
    </div>
  );
}
