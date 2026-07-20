import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { nactiMe, logout, nactiLogy as apiNactiLogy, smazLogy } from "../api";

// barevné odznaky podle druhu záznamu
const TYP_STYL = {
  provoz: { text: "Provoz", barva: "var(--fm-muted)" },
  audit: { text: "Akce", barva: "var(--fm-brand)" },
  chyba: { text: "Chyba", barva: "var(--st-crit)" },
};

const FILTRY = [
  { klic: "", popis: "Vše" },
  { klic: "audit", popis: "Jen akce (kdo co udělal)" },
  { klic: "chyba", popis: "Jen chyby" },
  { klic: "provoz", popis: "Jen provoz (načítání)" },
];

function barvaStavu(kod) {
  if (kod == null) return "var(--fm-muted)";
  if (kod >= 500) return "var(--st-crit)";
  if (kod >= 400) return "var(--st-warn)";
  if (kod >= 200 && kod < 300) return "var(--st-good)";
  return "var(--fm-muted)";
}

function formatCas(iso) {
  try {
    return new Date(iso).toLocaleString("cs-CZ");
  } catch {
    return iso;
  }
}

export default function Logy() {
  const [uzivatel, setUzivatel] = useState(null);
  const [logy, setLogy] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [typ, setTyp] = useState("");
  const [hledej, setHledej] = useState(""); // co je v poli
  const [hledejQ, setHledejQ] = useState(""); // co se posílá na server (s prodlevou)
  const [auto, setAuto] = useState(true);
  const [rozbaleny, setRozbaleny] = useState(null); // id řádku s otevřeným detailem
  const [aktualizovano, setAktualizovano] = useState(null);
  const navigate = useNavigate();

  // společné ošetření chyby: vypršené přihlášení → na login, jinak zobrazit.
  // nactiMe() hlásí 401 jako „Nepodařilo se načíst uživatele“, proto hlídáme
  // i slovo „uživatel“ (stejně jako ostatní stránky), ne jen „přihlášení“.
  const osetriChybu = useCallback(
    (e) => {
      const m = String(e.message || e);
      if (m.includes("přihlášení") || m.includes("uživatel")) {
        logout();
        navigate("/");
      } else {
        setChyba(m);
      }
    },
    [navigate]
  );

  const nacti = useCallback(() => {
    return apiNactiLogy({ typ: typ || undefined, hledej: hledejQ || undefined, limit: 300 })
      .then((data) => {
        setLogy(data);
        setChyba(null);
        setAktualizovano(new Date());
      })
      .catch(osetriChybu);
  }, [typ, hledejQ, osetriChybu]);

  // psaní do hledání neposílá požadavek na každý úhoz – počká 400 ms po dopsání
  useEffect(() => {
    const id = setTimeout(() => setHledejQ(hledej), 400);
    return () => clearTimeout(id);
  }, [hledej]);

  // úvod: ověř přihlášení a načti uživatele (guard na povinnou změnu hesla)
  useEffect(() => {
    nactiMe()
      .then((me) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
      })
      .catch(osetriChybu);
  }, [navigate, osetriChybu]);

  // načtení logů při změně filtru + volitelné automatické obnovování
  useEffect(() => {
    if (!uzivatel) return undefined;
    nacti();
    if (!auto) return undefined;
    const id = setInterval(nacti, 5000);
    return () => clearInterval(id);
  }, [uzivatel, nacti, auto]);

  async function vycisti() {
    if (!window.confirm("Opravdu smazat VŠECHNY záznamy logu? Tuto akci nelze vrátit.")) return;
    try {
      await smazLogy();
      await nacti();
    } catch (e) {
      osetriChybu(e);
    }
  }

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <Link to="/rozcestnik" style={{ fontSize: 13, color: "var(--fm-muted)", textDecoration: "none" }}>
          ← Zpět na rozcestník
        </Link>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (logy === null) return null; // úvodní načítání

  return (
    <Layout uzivatel={uzivatel}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link to="/rozcestnik" style={{ fontSize: 13, color: "var(--fm-muted)", textDecoration: "none" }}>
          ← Zpět na rozcestník
        </Link>

        <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>Logy</h2>
          <span style={{ fontSize: 12, color: "var(--fm-muted)" }}>
            {logy.length} záznamů
            {aktualizovano ? ` · aktualizováno ${aktualizovano.toLocaleTimeString("cs-CZ")}` : ""}
          </span>
        </div>

        {/* ovládací panel: filtr, hledání, auto-obnova */}
        <div
          className="fm-card"
          style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}
        >
          <select
            value={typ}
            onChange={(e) => setTyp(e.target.value)}
            style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--fm-line)" }}
          >
            {FILTRY.map((f) => (
              <option key={f.klic} value={f.klic}>
                {f.popis}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Hledat v cestě, popisu nebo e-mailu…"
            value={hledej}
            onChange={(e) => setHledej(e.target.value)}
            style={{
              padding: "6px 8px",
              borderRadius: 6,
              border: "1px solid var(--fm-line)",
              minWidth: 240,
              flex: "1 1 240px",
            }}
          />

          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            Automaticky obnovovat (5 s)
          </label>

          <button type="button" className="fm-btn" onClick={nacti}>
            Obnovit teď
          </button>

          <button
            type="button"
            className="fm-btn"
            onClick={vycisti}
            style={{ marginLeft: "auto", color: "var(--st-crit)" }}
          >
            Vyčistit vše
          </button>
        </div>

        {/* tabulka záznamů */}
        <div className="fm-card" style={{ padding: 0, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--fm-muted)" }}>
                <th style={{ padding: "8px 10px", whiteSpace: "nowrap" }}>Čas</th>
                <th style={{ padding: "8px 10px" }}>Uživatel</th>
                <th style={{ padding: "8px 10px" }}>Druh</th>
                <th style={{ padding: "8px 10px" }}>Akce</th>
                <th style={{ padding: "8px 10px", textAlign: "right" }}>Stav</th>
                <th style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap" }}>Doba</th>
              </tr>
            </thead>
            <tbody>
              {logy.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ padding: 20, textAlign: "center", color: "var(--fm-muted)" }}>
                    Žádné záznamy odpovídající filtru.
                  </td>
                </tr>
              )}
              {logy.map((z) => {
                const styl = TYP_STYL[z.typ] || TYP_STYL.provoz;
                const maDetail = Boolean(z.detail);
                const otevreny = rozbaleny === z.id;
                return (
                  <ZaznamRadek
                    key={z.id}
                    z={z}
                    styl={styl}
                    maDetail={maDetail}
                    otevreny={otevreny}
                    onToggle={() => setRozbaleny(otevreny ? null : z.id)}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
}

function ZaznamRadek({ z, styl, maDetail, otevreny, onToggle }) {
  return (
    <>
      <tr
        onClick={maDetail ? onToggle : undefined}
        style={{
          borderTop: "1px solid var(--fm-line)",
          cursor: maDetail ? "pointer" : "default",
        }}
      >
        <td style={{ padding: "8px 10px", whiteSpace: "nowrap", color: "var(--fm-muted)" }}>
          {formatCas(z.cas)}
        </td>
        <td style={{ padding: "8px 10px" }}>{z.uzivatel_email || "—"}</td>
        <td style={{ padding: "8px 10px" }}>
          <span
            style={{
              display: "inline-block",
              padding: "2px 8px",
              borderRadius: 999,
              fontSize: 12,
              color: "#fff",
              background: styl.barva,
            }}
          >
            {styl.text}
          </span>
        </td>
        <td style={{ padding: "8px 10px" }}>
          {z.popis ? <strong>{z.popis}</strong> : null}
          <span style={{ color: "var(--fm-muted)", marginLeft: z.popis ? 8 : 0 }}>
            {z.metoda} {z.cesta}
          </span>
          {maDetail ? (
            <span style={{ color: "var(--st-crit)", marginLeft: 8, fontSize: 12 }}>
              {otevreny ? "▾ skrýt detail" : "▸ detail chyby"}
            </span>
          ) : null}
        </td>
        <td style={{ padding: "8px 10px", textAlign: "right", color: barvaStavu(z.status_kod) }}>
          {z.status_kod ?? "—"}
        </td>
        <td style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap", color: "var(--fm-muted)" }}>
          {z.doba_ms != null ? `${z.doba_ms} ms` : "—"}
        </td>
      </tr>
      {otevreny && maDetail ? (
        <tr>
          <td colSpan={6} style={{ padding: "0 10px 10px" }}>
            <pre
              style={{
                margin: 0,
                padding: 12,
                background: "var(--fm-bg)",
                border: "1px solid var(--fm-line)",
                borderRadius: 6,
                fontSize: 12,
                overflowX: "auto",
                whiteSpace: "pre-wrap",
              }}
            >
              {z.detail}
            </pre>
          </td>
        </tr>
      ) : null}
    </>
  );
}
