import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import ImportRaynet from "../components/ImportRaynet";
import ZakaznikFormular from "../components/ZakaznikFormular";
import { nactiMe, logout, crmVlastniPole, crmZakaznici } from "../api";
import { POHLEDY_ZAKAZNIKU, fmtDatum } from "../crm";
import "../styles/crm.css";

/**
 * Sekce Zákazníci – dva pohledy nad jednou tabulkou (Leady / Klienti).
 *
 * Seznam nefiltruje podle vlastníka: to dělá backend podle práva `crm_vse`,
 * aby se dvě pravidla viditelnosti nemohla rozejít.
 */
export default function Zakaznici() {
  const { pohled = "lead" } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zakaznici, setZakaznici] = useState(null);
  const [hledat, setHledat] = useState("");
  const [chyba, setChyba] = useState(null);
  const [zaklada, setZaklada] = useState(false);
  // Vlastní pole označená „v seznamu" se ukazují jako další sloupce tabulky.
  const [sloupce, setSloupce] = useState([]);
  const [importRaynet, setImportRaynet] = useState(false);

  const sekce = POHLEDY_ZAKAZNIKU.find((p) => p.klic === pohled);

  const nacti = useCallback(
    async (dotaz = "") => {
      const list = await crmZakaznici({ typ: pohled, hledat: dotaz || undefined });
      setZakaznici(list);
    },
    [pohled]
  );

  useEffect(() => {
    if (!sekce) {
      navigate("/zakaznici/lead", { replace: true });
      return;
    }
    Promise.all([nactiMe(), crmZakaznici({ typ: pohled })])
      .then(([m, list]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setZakaznici(list);
        crmVlastniPole("zakaznik")
          .then((pole) => setSloupce(pole.filter((x) => x.v_seznamu)))
          .catch(() => setSloupce([]));
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (msg.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(msg);
        }
      });
  }, [pohled, sekce, navigate]);

  // Hledání se pouští s prodlevou, ať se neposílá dotaz na každý znak.
  useEffect(() => {
    if (!me) return undefined;
    const t = setTimeout(() => {
      nacti(hledat).catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me, nacti]);

  if (!sekce) return null;
  if (chyba && !zakaznici) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !zakaznici) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app">
        <div className="crm-hlava">
          <div>
            <h1>Zákazníci</h1>
            <p className="crm-popis">{sekce.popis}</p>
          </div>
          <span className="crm-mezera" />
          {/* Import z Raynetu – bez něj je CRM prázdná kostra. */}
          {me.prava?.includes("crm_nastaveni") && (
            <button className="fm-btn" onClick={() => setImportRaynet(true)}>
              ⬇ Import z Raynetu
            </button>
          )}
          <button className="fm-btn fm-primary" onClick={() => setZaklada(true)}>
            + Nový {pohled === "lead" ? "lead" : "klient"}
          </button>
        </div>

        <div className="crm-zalozky">
          {POHLEDY_ZAKAZNIKU.map((p) => (
            <Link
              key={p.klic}
              to={`/zakaznici/${p.klic}`}
              className={`crm-zalozka ${p.klic === pohled ? "aktivni" : ""}`}
            >
              {p.nazev}
            </Link>
          ))}
        </div>

        <div className="crm-toolbar">
          <input
            className="crm-pole crm-hledani"
            placeholder="Hledat podle názvu, IČO, města nebo e-mailu…"
            value={hledat}
            onChange={(e) => setHledat(e.target.value)}
          />
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{zakaznici.length}</b> {pohled === "lead" ? "leadů" : "klientů"}
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <div className="crm-scroll">
          <table className="crm-tabulka">
            <thead>
              <tr>
                <th>Název</th>
                <th>IČO</th>
                <th>Město</th>
                <th>Kontakt</th>
                <th>Vlastník</th>
                {sloupce.map((sl) => (
                  <th key={sl.klic}>{sl.nazev}</th>
                ))}
                <th className="crm-vpravo">Případy</th>
                <th>Vytvořeno</th>
              </tr>
            </thead>
            <tbody>
              {zakaznici.map((z) => (
                <tr key={z.id} onClick={() => navigate(`/zakaznici/detail/${z.id}`)}>
                  <td className="crm-silne">{z.nazev}</td>
                  <td>{z.ico || "—"}</td>
                  <td>{z.adresa_mesto || "—"}</td>
                  <td>
                    {z.telefon || z.email ? (
                      <span className="crm-tise">
                        {z.telefon}
                        {z.telefon && z.email ? " · " : ""}
                        {z.email}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{z.vlastnik_jmeno || "—"}</td>
                  {sloupce.map((sl) => (
                    <td key={sl.klic}>{(z.extra_text || {})[sl.klic] ?? "—"}</td>
                  ))}
                  <td className="crm-vpravo">{z.pocet_pripadu || 0}</td>
                  <td>{fmtDatum(z.vytvoreno_at)}</td>
                </tr>
              ))}
              {zakaznici.length === 0 && (
                <tr>
                  <td colSpan={7 + sloupce.length} className="crm-prazdno">
                    {hledat
                      ? "Nic nenalezeno. Zkus jiný výraz."
                      : `Zatím žádní ${pohled === "lead" ? "leadi" : "klienti"}. Založ prvního tlačítkem vpravo nahoře.`}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {importRaynet && (
        <ImportRaynet
          onZavri={() => setImportRaynet(false)}
          onHotovo={() => nacti(hledat)}
        />
      )}

      {zaklada && (
        <ZakaznikFormular
          vychoziTyp={pohled}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setZaklada(false)}
          onHotovo={(novy) => {
            setZaklada(false);
            navigate(`/zakaznici/detail/${novy.id}`);
          }}
        />
      )}
    </Layout>
  );
}
