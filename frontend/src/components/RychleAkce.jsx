import { useEffect, useRef, useState } from "react";

/**
 * Zelené kolečko „+" s rychlými akcemi (CRM-34).
 *
 * ---- Proč to existuje ---------------------------------------------------
 * Akce jsou dnes rozeseté v hlavičkách obrazovek a na každé jinde. Kolečko je
 * **jedno pevné místo**, kde se dá začít nová věc, ať je člověk kdekoli.
 * Tlačítka v hlavičkách zůstávají — kolečko je nepřebíjí, protože zvyklost
 * „nahoře vpravo" nechceme lidem brát; přidává zkratku, ne náhradu.
 *
 * ---- Kontext určuje obsah ----------------------------------------------
 * Komponenta sama **nic neví** o tom, kde je. Nabídku akcí jí předá stránka
 * (`akce`), protože jen ta ví, co má po ruce (id zákazníka, otevřený případ…).
 * Kdyby si kolečko kontext hádalo z adresy, skončilo by to `if`em na patnáct
 * cest a akcemi, které na půlce obrazovek nefungují.
 *
 * ---- Přístupnost -------------------------------------------------------
 * Kolečko je normální `<button>`: chodí se na něj tabulátorem, otevírá se
 * mezerníkem i Enterem, `Escape` zavírá a fokus se vrací na kolečko. Menu je
 * `role="menu"` a šipkami se v něm dá jezdit. Bez tohohle by to byla myší
 * ozdoba, kterou půlka lidí neobslouží.
 */

const VELIKOST = 60; // px – „dostatečně velké pro viditelnost" (zadání Dana)

export default function RychleAkce({ akce = [], titulek = "Rychlé akce" }) {
  const [otevreno, setOtevreno] = useState(false);
  const obal = useRef(null);
  const tlacitko = useRef(null);
  const polozky = useRef([]);

  const pouzitelne = (akce || []).filter(Boolean);

  // Klik mimo zavře menu. Bez tohohle zůstane menu otevřené a překrývá obsah.
  useEffect(() => {
    if (!otevreno) return undefined;
    function mimo(e) {
      if (obal.current && !obal.current.contains(e.target)) setOtevreno(false);
    }
    document.addEventListener("mousedown", mimo);
    return () => document.removeEventListener("mousedown", mimo);
  }, [otevreno]);

  // Escape zavírá a vrací fokus na kolečko – jinak by fokus zůstal v prázdnu.
  useEffect(() => {
    if (!otevreno) return undefined;
    function klavesa(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOtevreno(false);
        tlacitko.current?.focus();
      }
    }
    document.addEventListener("keydown", klavesa);
    return () => document.removeEventListener("keydown", klavesa);
  }, [otevreno]);

  // Po otevření skočit fokusem na první akci (chování nabídky, ne dialogu).
  useEffect(() => {
    if (otevreno) polozky.current[0]?.focus();
  }, [otevreno]);

  if (pouzitelne.length === 0) return null;

  function sipky(e, index) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const posun = e.key === "ArrowDown" ? 1 : -1;
      const dalsi = (index + posun + pouzitelne.length) % pouzitelne.length;
      polozky.current[dalsi]?.focus();
    }
  }

  function spust(a) {
    setOtevreno(false);
    // Akce často otevírá dialog – zavřít menu dřív, ať se nepřekrývají.
    if (typeof a.onClick === "function") a.onClick();
  }

  return (
    <div className="ra-obal" ref={obal}>
      {otevreno && (
        <div className="ra-menu" role="menu" aria-label={titulek}>
          <div className="ra-menu-titulek">{titulek}</div>
          {pouzitelne.map((a, i) => (
            <button
              key={a.klic || a.nazev}
              ref={(el) => {
                polozky.current[i] = el;
              }}
              className="ra-polozka"
              role="menuitem"
              onClick={() => spust(a)}
              onKeyDown={(e) => sipky(e, i)}
              title={a.popis || ""}
            >
              {a.znak && (
                <span className="ra-polozka-znak" aria-hidden="true">
                  {a.znak}
                </span>
              )}
              <span className="ra-polozka-text">
                {a.nazev}
                {a.popis && <span className="ra-polozka-popis">{a.popis}</span>}
              </span>
            </button>
          ))}
        </div>
      )}

      <button
        ref={tlacitko}
        className="ra-kolecko"
        style={{ width: VELIKOST, height: VELIKOST }}
        aria-expanded={otevreno}
        aria-haspopup="menu"
        aria-label={otevreno ? "Zavřít rychlé akce" : titulek}
        title={titulek}
        onClick={() => setOtevreno((o) => !o)}
      >
        {/* Znak „+" je SVG, ne text: znak z fontu se mezi systémy liší
            v šířce i optickém středu a kolečko pak vypadá rozvážené. */}
        <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
          <path
            d="M12 5v14M5 12h14"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.4"
            strokeLinecap="round"
          />
        </svg>
      </button>
    </div>
  );
}
