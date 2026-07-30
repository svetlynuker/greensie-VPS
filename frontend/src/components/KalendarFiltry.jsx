import { useState } from "react";
import Ikona from "./Ikona";
import { DRUHY_AKTIVITY } from "../crm";

/**
 * Postranní panel kalendáře: uživatelé, typy aktivit, zobrazení, kategorie.
 *
 * Sekce jsou sbalovací, protože jich je pět a rozbalené naráz by panel byl
 * delší než mřížka. Rozbalení se nedrží v profilu schválně — je to okamžitá
 * pracovní věc, ne nastavení.
 *
 * Záložka „NENAPLÁNOVÁNO" ukazuje úkoly, které mají termín, ale ne hodinu.
 * V mřížce se kreslí v pruhu nahoře, takže se snadno přehlédnou; tady jsou
 * pohromadě a dá se z nich plánovat.
 */

function Sekce({ titulek, akce, deti, vychoziOtevrena = true }) {
  const [otevrena, setOtevrena] = useState(vychoziOtevrena);
  return (
    <div className="kalf-sekce">
      <div className="kalf-sekce-hlava">
        <button
          className="kalf-sekce-prepinac"
          onClick={() => setOtevrena((o) => !o)}
          aria-expanded={otevrena}
        >
          <span className={`kalf-sipka ${otevrena ? "dolu" : ""}`} aria-hidden="true">
            ›
          </span>
          {titulek}
        </button>
        {akce}
      </div>
      {otevrena && <div className="kalf-sekce-telo">{deti}</div>}
    </div>
  );
}

function Prepinac({ zapnuto, onZmena, popis }) {
  return (
    <button
      className={`kalf-toggle ${zapnuto ? "zap" : ""}`}
      onClick={() => onZmena(!zapnuto)}
      role="switch"
      aria-checked={zapnuto}
      aria-label={popis}
      title={popis}
    >
      <span className="kalf-toggle-kolecko" />
    </button>
  );
}

export default function KalendarFiltry({
  lide, // [{id, jmeno}] – koho lze přidat do kalendáře
  vybraniLide, // Set id
  onLide,
  jaId,
  druhy, // Set klíčů druhů
  onDruhy,
  kategorie, // [{id, nazev, barva}]
  vybraneKategorie, // Set id
  onKategorie,
  schovatRealizovane,
  onSchovatRealizovane,
  zobrazitZrusene,
  onZobrazitZrusene,
  nenaplanovane, // úkoly s termínem bez hodiny
  onUdalost,
  onUlozitFiltr,
  onVycistit,
  maFiltr,
}) {
  const [zalozka, setZalozka] = useState("filtry");

  function prepniVSetu(set, klic, onZmena, prazdnyZnamenaVse) {
    const n = new Set(set);
    if (n.has(klic)) n.delete(klic);
    else n.add(klic);
    // U typů aktivit by prázdný výběr ukázal prázdný kalendář a vypadal jako
    // porucha; u kategorií prázdno naopak znamená „nefiltrovat".
    onZmena(prazdnyZnamenaVse && n.size === 0 ? new Set(set) : n);
  }

  return (
    <div className="kalf">
      <div className="kalf-zalozky">
        <button
          className={`kalf-zalozka ${zalozka === "filtry" ? "aktivni" : ""}`}
          onClick={() => setZalozka("filtry")}
        >
          Filtry
        </button>
        <button
          className={`kalf-zalozka ${zalozka === "nenaplanovano" ? "aktivni" : ""}`}
          onClick={() => setZalozka("nenaplanovano")}
        >
          Nenaplánováno
          {nenaplanovane?.length ? <span className="kalf-pocet">{nenaplanovane.length}</span> : null}
        </button>
      </div>

      {zalozka === "nenaplanovano" ? (
        <div className="kalf-sekce-telo">
          {(nenaplanovane || []).length === 0 ? (
            <p className="crm-tise" style={{ margin: "6px 0" }}>
              Všechno má svůj čas. Úkoly bez konkrétní hodiny se objeví tady.
            </p>
          ) : (
            <ul className="kalf-nenaplanovane">
              {nenaplanovane.map((u) => (
                <li key={u.id}>
                  <button className="kalf-nenapl-radek" onClick={() => onUdalost?.(u)}>
                    <span
                      className="kalf-barva-tecka"
                      style={{ background: u.kategorie_barva || "#d3d9de" }}
                    />
                    <span className="kalf-nenapl-nazev">{u.nazev || "(bez názvu)"}</span>
                    <span className="crm-tise">{(u.termin || "").slice(8, 10)}.</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <>
          <Sekce
            titulek="Uživatelé"
            akce={
              lide?.length > 1 ? (
                <select
                  className="kalf-pridat"
                  value=""
                  onChange={(e) => {
                    if (!e.target.value) return;
                    const n = new Set(vybraniLide);
                    n.add(Number(e.target.value));
                    onLide(n);
                  }}
                  title="Přidat kalendář kolegy"
                  aria-label="Přidat kalendář kolegy"
                >
                  <option value="">+</option>
                  {lide
                    .filter((u) => !vybraniLide.has(u.id))
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.jmeno}
                      </option>
                    ))}
                </select>
              ) : null
            }
            deti={
              <ul className="kalf-lide">
                {(lide || [])
                  .filter((u) => vybraniLide.has(u.id))
                  .map((u) => (
                    <li key={u.id}>
                      <span className="kalf-avatar" aria-hidden="true">
                        {(u.jmeno || "?")
                          .split(/\s+/)
                          .map((x) => x[0] || "")
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </span>
                      <span className="kalf-jmeno">{u.jmeno}</span>
                      {u.id !== jaId && (
                        <button
                          className="kalf-odebrat"
                          onClick={() => {
                            const n = new Set(vybraniLide);
                            n.delete(u.id);
                            onLide(n);
                          }}
                          title="Odebrat z kalendáře"
                        >
                          ✕
                        </button>
                      )}
                    </li>
                  ))}
              </ul>
            }
          />

          <Sekce
            titulek="Typ aktivity"
            deti={
              <ul className="kalf-typy">
                {DRUHY_AKTIVITY.filter((d) => d.klic !== "poznamka").map((d) => (
                  <li key={d.klic}>
                    <button
                      className={`kalf-typ ${druhy.has(d.klic) ? "aktivni" : ""}`}
                      onClick={() => prepniVSetu(druhy, d.klic, onDruhy, true)}
                      aria-pressed={druhy.has(d.klic)}
                    >
                      <Ikona jmeno={d.ikona} velikost={15} />
                      {d.nazev}
                    </button>
                  </li>
                ))}
              </ul>
            }
          />

          <Sekce
            titulek="Zobrazení aktivit"
            deti={
              <>
                <div className="kalf-radek">
                  <span>Schovat realizované</span>
                  <Prepinac
                    zapnuto={schovatRealizovane}
                    onZmena={onSchovatRealizovane}
                    popis="Schovat realizované aktivity"
                  />
                </div>
                <div className="kalf-radek">
                  <span>Zobrazit i zrušené</span>
                  <Prepinac
                    zapnuto={zobrazitZrusene}
                    onZmena={onZobrazitZrusene}
                    popis="Zobrazit i zrušené aktivity"
                  />
                </div>
              </>
            }
          />

          <Sekce
            titulek="Kategorie"
            vychoziOtevrena={false}
            deti={
              (kategorie || []).length === 0 ? (
                <p className="crm-tise" style={{ margin: "4px 0" }}>
                  Žádné kategorie. Přidat je lze v nastavení CRM.
                </p>
              ) : (
                <ul className="kalf-kategorie">
                  {kategorie.map((k) => (
                    <li key={k.id}>
                      <button
                        className={`kalf-kategorie-radek ${
                          vybraneKategorie.has(k.id) ? "aktivni" : ""
                        }`}
                        onClick={() => prepniVSetu(vybraneKategorie, k.id, onKategorie, false)}
                        aria-pressed={vybraneKategorie.has(k.id)}
                      >
                        <span className="kalf-barva-tecka" style={{ background: k.barva }} />
                        {k.nazev}
                      </button>
                    </li>
                  ))}
                </ul>
              )
            }
          />

          <div className="kalf-pata">
            <button
              className="fm-btn fm-primary crm-btn-maly"
              onClick={onUlozitFiltr}
              disabled={!maFiltr}
              title={maFiltr ? "Uložit nastavení filtru jako vlastní pohled" : "Nejdřív něco vyfiltruj"}
            >
              Uložit filtr
            </button>
            <button className="fm-btn crm-btn-maly" onClick={onVycistit}>
              Vyčistit
            </button>
          </div>
        </>
      )}
    </div>
  );
}
