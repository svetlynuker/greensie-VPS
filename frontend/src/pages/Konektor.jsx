import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import {
  nactiMe,
  logout,
  konektorNastaveni,
  konektorUlozNastaveni,
  konektorTestSpojeni,
  konektorLogy as apiKonektorLogy,
  konektorSmazLogy,
  konektorVytvorSlozku,
} from "../api";

const poleStyl = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
  boxSizing: "border-box",
};
const labelStyl = {
  display: "block",
  fontSize: 12,
  fontWeight: 600,
  color: "var(--fm-muted)",
  marginBottom: 4,
};
const sekceNadpis = {
  fontSize: 12,
  fontWeight: 700,
  color: "var(--fm-muted)",
  textTransform: "uppercase",
  letterSpacing: 0.4,
  margin: "8px 0 2px",
};

/* =================== Karta: Nastavení konektoru =================== */
function NastaveniKarta() {
  const [nast, setNast] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [stav, setStav] = useState(null); // "ok" | null
  const [chyba, setChyba] = useState(null);
  const [test, setTest] = useState(null); // {raynet, google}
  const [testuje, setTestuje] = useState(false);

  useEffect(() => {
    konektorNastaveni()
      .then((d) => setNast({ ...d, raynet_api_key: "", google_sa_json: "" }))
      .catch((e) => setChyba(e.message));
  }, []);

  function nastav(klic, hodnota) {
    setNast((n) => ({ ...n, [klic]: hodnota }));
    setStav(null);
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      const ulozene = await konektorUlozNastaveni({
        raynet_instance: nast.raynet_instance,
        raynet_api_user: nast.raynet_api_user,
        raynet_base_url: nast.raynet_base_url,
        raynet_company_drive_field: nast.raynet_company_drive_field,
        google_shared_drive_id: nast.google_shared_drive_id,
        google_subject_email: nast.google_subject_email,
        sync_model: nast.sync_model,
        template_subfolders: nast.template_subfolders,
        delete_policy: nast.delete_policy,
        fr3_plne_zrcadleni: nast.fr3_plne_zrcadleni,
        auto_zapnuto: nast.auto_zapnuto,
        reconcile_interval_min: Number(nast.reconcile_interval_min),
        log_level: nast.log_level,
        // tajemství: prázdné = neměnit stávající hodnotu v DB
        raynet_api_key: nast.raynet_api_key || "",
        google_sa_json: nast.google_sa_json || "",
      });
      setNast({ ...ulozene, raynet_api_key: "", google_sa_json: "" });
      setStav("ok");
      setTimeout(() => setStav(null), 1800);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function otestuj() {
    setTestuje(true);
    setTest(null);
    setChyba(null);
    try {
      const vysledek = await konektorTestSpojeni();
      setTest(vysledek);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setTestuje(false);
    }
  }

  if (!nast) {
    return (
      <div className="fm-card" style={{ padding: 16 }}>
        {chyba ? (
          <div style={{ color: "var(--st-crit)", fontSize: 13 }}>Chyba: {chyba}</div>
        ) : (
          <div style={{ color: "var(--fm-muted)", fontSize: 13 }}>Načítám…</div>
        )}
      </div>
    );
  }

  const dvojice = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 };

  return (
    <div className="fm-card" style={{ padding: 16 }}>
      <strong style={{ fontSize: 15 }}>Nastavení konektoru</strong>
      <p style={{ margin: "4px 0 12px", fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
        Přístupy k Raynetu a Google Disku a chování synchronizace. Tajemství (API klíč, service-account
        JSON) se ukládají šifrovaně a už se nezobrazují – přepíšeš je jen tím, že vyplníš nové.
      </p>

      {/* ---- Raynet ---- */}
      <div style={sekceNadpis}>Raynet CRM</div>
      <div style={dvojice}>
        <div>
          <label style={labelStyl}>Instance</label>
          <input style={poleStyl} value={nast.raynet_instance} onChange={(e) => nastav("raynet_instance", e.target.value)} placeholder="např. mojefirma" />
        </div>
        <div>
          <label style={labelStyl}>API uživatel</label>
          <input style={poleStyl} value={nast.raynet_api_user} onChange={(e) => nastav("raynet_api_user", e.target.value)} placeholder="api@greensie.cz" />
        </div>
        <div>
          <label style={labelStyl}>Base URL API</label>
          <input style={poleStyl} value={nast.raynet_base_url} onChange={(e) => nastav("raynet_base_url", e.target.value)} placeholder="https://app.raynet.cz/api/v2/" />
        </div>
        <div>
          <label style={labelStyl}>Kód vlastního pole (odkaz na Disk)</label>
          <input style={poleStyl} value={nast.raynet_company_drive_field} onChange={(e) => nastav("raynet_company_drive_field", e.target.value)} placeholder="např. Disk_slozka_ab12c" />
        </div>
        <div>
          <label style={labelStyl}>
            API klíč {nast.raynet_api_key_nastaven && <span style={{ color: "var(--fm-brand-dk)" }}>✓ nastaven</span>}
          </label>
          <input
            style={poleStyl}
            type="password"
            value={nast.raynet_api_key}
            onChange={(e) => nastav("raynet_api_key", e.target.value)}
            placeholder={nast.raynet_api_key_nastaven ? "•••••••• (vyplň jen pro změnu)" : "zatím nenastaven"}
            autoComplete="new-password"
          />
        </div>
      </div>

      {/* ---- Google ---- */}
      <div style={{ ...sekceNadpis, marginTop: 14 }}>Google Drive (Workspace + Shared Drive)</div>
      <div style={dvojice}>
        <div>
          <label style={labelStyl}>ID Shared Drive</label>
          <input style={poleStyl} value={nast.google_shared_drive_id} onChange={(e) => nastav("google_shared_drive_id", e.target.value)} placeholder="např. 0AB…" />
        </div>
        <div>
          <label style={labelStyl}>Impersonovaný uživatel (delegace, volitelné)</label>
          <input style={poleStyl} value={nast.google_subject_email} onChange={(e) => nastav("google_subject_email", e.target.value)} placeholder="uzivatel@greensie.cz" />
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label style={labelStyl}>
          Service-account JSON {nast.google_sa_json_nastaven && <span style={{ color: "var(--fm-brand-dk)" }}>✓ nastaven</span>}
        </label>
        <textarea
          style={{ ...poleStyl, minHeight: 90, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
          value={nast.google_sa_json}
          onChange={(e) => nastav("google_sa_json", e.target.value)}
          placeholder={nast.google_sa_json_nastaven ? "•••••••• (vlož nový JSON jen pro změnu)" : '{ "type": "service_account", … }'}
        />
      </div>

      {/* ---- Chování ---- */}
      <div style={{ ...sekceNadpis, marginTop: 14 }}>Chování synchronizace</div>
      <div style={dvojice}>
        <div>
          <label style={labelStyl}>Model synchronizace</label>
          <select style={poleStyl} value={nast.sync_model} onChange={(e) => nastav("sync_model", e.target.value)}>
            <option value="links">Odkazy (doporučeno)</option>
            <option value="mirror">Zrcadlení kopií</option>
          </select>
        </div>
        <div>
          <label style={labelStyl}>Politika mazání</label>
          <select style={poleStyl} value={nast.delete_policy} onChange={(e) => nastav("delete_policy", e.target.value)}>
            <option value="trash_reconcile">Koš + reconcile (doporučeno)</option>
            <option value="no_delete">Nemazat odkazy</option>
          </select>
        </div>
        <div>
          <label style={labelStyl}>Reconcile interval (min)</label>
          <input style={poleStyl} type="number" min={5} step={5} value={nast.reconcile_interval_min} onChange={(e) => nastav("reconcile_interval_min", e.target.value)} />
        </div>
        <div>
          <label style={labelStyl}>Úroveň logování</label>
          <select style={poleStyl} value={nast.log_level} onChange={(e) => nastav("log_level", e.target.value)}>
            <option value="debug">debug</option>
            <option value="info">info</option>
            <option value="warn">warn</option>
            <option value="error">error</option>
          </select>
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <label style={labelStyl}>Šablona podsložek (oddělené čárkou)</label>
        <input style={poleStyl} value={nast.template_subfolders} onChange={(e) => nastav("template_subfolders", e.target.value)} placeholder="01_Nabídky,02_Smlouvy,03_Faktury,04_Ostatní" />
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer", marginTop: 12 }}>
        <input type="checkbox" checked={nast.fr3_plne_zrcadleni} onChange={(e) => nastav("fr3_plne_zrcadleni", e.target.checked)} />
        Plné zrcadlení stromu Disku do modulu Dokumenty
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer", marginTop: 8 }}>
        <input type="checkbox" checked={nast.auto_zapnuto} onChange={(e) => nastav("auto_zapnuto", e.target.checked)} />
        <strong>Zapnout automatickou synchronizaci</strong>
      </label>

      {/* ---- Akce ---- */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit nastavení"}
        </button>
        <button className="fm-btn" onClick={otestuj} disabled={testuje}>
          {testuje ? "Testuji…" : "Test spojení"}
        </button>
        {stav === "ok" && <span style={{ color: "var(--fm-brand-dk)", fontSize: 13 }}>Uloženo ✓</span>}
        {chyba && <span style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</span>}
      </div>

      {test && (
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 6 }}>
          <StavRadek nazev="Raynet" stav={test.raynet} />
          <StavRadek nazev="Google Drive" stav={test.google} />
        </div>
      )}

      <div style={{ marginTop: 12, fontSize: 12, color: "var(--fm-muted)" }}>
        Naposledy proběhlo:{" "}
        {nast.posledni_beh ? new Date(nast.posledni_beh).toLocaleString("cs-CZ") : "zatím neproběhlo"}
        {nast.posledni_vysledek ? ` — ${nast.posledni_vysledek}` : ""}
      </div>
    </div>
  );
}

function StavRadek({ nazev, stav }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontSize: 13,
        padding: "8px 10px",
        borderRadius: 8,
        border: "1px solid var(--fm-line)",
        background: stav.ok ? "var(--fm-brand-soft)" : "var(--fm-head)",
      }}
    >
      <span style={{ fontWeight: 700, color: stav.ok ? "var(--fm-brand-dk)" : "var(--st-crit)" }}>
        {stav.ok ? "✓" : "✗"}
      </span>
      <strong style={{ minWidth: 100 }}>{nazev}</strong>
      <span style={{ color: "var(--fm-muted)" }}>{stav.zprava}</span>
    </div>
  );
}

/* =================== Karta: Ruční akce (test) =================== */
function RucniAkceKarta() {
  const [companyId, setCompanyId] = useState("");
  const [bezi, setBezi] = useState(false);
  const [vysledek, setVysledek] = useState(null);
  const [chyba, setChyba] = useState(null);

  async function vytvor() {
    setBezi(true);
    setChyba(null);
    setVysledek(null);
    try {
      const v = await konektorVytvorSlozku(Number(companyId));
      setVysledek(v);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setBezi(false);
    }
  }

  return (
    <div className="fm-card" style={{ padding: 16 }}>
      <strong style={{ fontSize: 15 }}>Ruční test – vytvoření složky klienta</strong>
      <p style={{ margin: "4px 0 12px", fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
        Spustí Flow A pro zadané ID company v Raynetu (vytvoří složku + podsložky na Disku a zapíše
        odkaz zpět). Slouží k ověření nastavení bez čekání na webhook.
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input
          style={{ ...poleStyl, width: 200 }}
          type="number"
          value={companyId}
          onChange={(e) => setCompanyId(e.target.value)}
          placeholder="ID company v Raynetu"
        />
        <button className="fm-btn fm-primary" onClick={vytvor} disabled={bezi || !companyId}>
          {bezi ? "Vytvářím…" : "Vytvořit složku"}
        </button>
      </div>
      {vysledek && (
        <div style={{ marginTop: 12, fontSize: 13, color: "var(--fm-brand-dk)" }}>
          {vysledek.skip
            ? `Klient už složku má (${vysledek.drive_folder_id}).`
            : `Hotovo – složka ${vysledek.drive_folder_id}${vysledek.odkaz_ok ? ", odkaz zapsán ✓" : ", ale odkaz se nezapsal ✗"}.`}
          {vysledek.drive_folder_url && (
            <>
              {" "}
              <a href={vysledek.drive_folder_url} target="_blank" rel="noopener noreferrer">otevřít na Disku</a>
            </>
          )}
        </div>
      )}
      {chyba && <div style={{ marginTop: 12, fontSize: 13, color: "var(--st-crit)" }}>{chyba}</div>}
    </div>
  );
}

/* =================== Panel: Logy konektoru =================== */
const UROVEN_STYL = {
  debug: { text: "debug", barva: "var(--fm-muted)" },
  info: { text: "info", barva: "var(--fm-brand)" },
  warn: { text: "warn", barva: "var(--st-warn)" },
  error: { text: "error", barva: "var(--st-crit)" },
};
const UROVEN_FILTRY = [
  { klic: "", popis: "Vše" },
  { klic: "info", popis: "Info" },
  { klic: "warn", popis: "Varování" },
  { klic: "error", popis: "Chyby" },
  { klic: "debug", popis: "Debug" },
];

function LogyPanel({ onChyba }) {
  const [logy, setLogy] = useState(null);
  const [uroven, setUroven] = useState("");
  const [hledej, setHledej] = useState("");
  const [hledejQ, setHledejQ] = useState("");
  const [auto, setAuto] = useState(true);
  const [aktualizovano, setAktualizovano] = useState(null);

  const nacti = useCallback(() => {
    return apiKonektorLogy({ uroven: uroven || undefined, hledej: hledejQ || undefined, limit: 300 })
      .then((data) => {
        setLogy(data);
        setAktualizovano(new Date());
      })
      .catch(onChyba);
  }, [uroven, hledejQ, onChyba]);

  useEffect(() => {
    const id = setTimeout(() => setHledejQ(hledej), 400);
    return () => clearTimeout(id);
  }, [hledej]);

  useEffect(() => {
    nacti();
    if (!auto) return undefined;
    const id = setInterval(nacti, 5000);
    return () => clearInterval(id);
  }, [nacti, auto]);

  async function vycisti() {
    if (!window.confirm("Opravdu smazat všechny logy konektoru? Tuto akci nelze vrátit.")) return;
    try {
      await konektorSmazLogy();
      await nacti();
    } catch (e) {
      onChyba(e);
    }
  }

  return (
    <div className="fm-card" style={{ padding: 0 }}>
      <div style={{ padding: 12, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", borderBottom: "1px solid var(--fm-line)" }}>
        <strong style={{ fontSize: 15 }}>Logy konektoru</strong>
        <span style={{ fontSize: 12, color: "var(--fm-muted)" }}>
          {logy ? `${logy.length} záznamů` : ""}
          {aktualizovano ? ` · ${aktualizovano.toLocaleTimeString("cs-CZ")}` : ""}
        </span>
        <select value={uroven} onChange={(e) => setUroven(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--fm-line)" }}>
          {UROVEN_FILTRY.map((f) => (
            <option key={f.klic} value={f.klic}>{f.popis}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Hledat ve zprávě nebo události…"
          value={hledej}
          onChange={(e) => setHledej(e.target.value)}
          style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid var(--fm-line)", minWidth: 200, flex: "1 1 200px" }}
        />
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
          Obnovovat (5 s)
        </label>
        <button type="button" className="fm-btn" onClick={nacti}>Obnovit</button>
        <button type="button" className="fm-btn" onClick={vycisti} style={{ marginLeft: "auto", color: "var(--st-crit)" }}>
          Vyčistit
        </button>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ textAlign: "left", color: "var(--fm-muted)" }}>
              <th style={{ padding: "8px 10px", whiteSpace: "nowrap" }}>Čas</th>
              <th style={{ padding: "8px 10px" }}>Úroveň</th>
              <th style={{ padding: "8px 10px" }}>Událost</th>
              <th style={{ padding: "8px 10px" }}>Zpráva</th>
            </tr>
          </thead>
          <tbody>
            {logy && logy.length === 0 && (
              <tr>
                <td colSpan={4} style={{ padding: 20, textAlign: "center", color: "var(--fm-muted)" }}>
                  Zatím žádné záznamy.
                </td>
              </tr>
            )}
            {(logy || []).map((z) => {
              const styl = UROVEN_STYL[z.uroven] || UROVEN_STYL.info;
              return (
                <tr key={z.id} style={{ borderTop: "1px solid var(--fm-line)" }}>
                  <td style={{ padding: "8px 10px", whiteSpace: "nowrap", color: "var(--fm-muted)" }}>
                    {new Date(z.cas).toLocaleString("cs-CZ")}
                  </td>
                  <td style={{ padding: "8px 10px" }}>
                    <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 999, fontSize: 12, color: "#fff", background: styl.barva }}>
                      {styl.text}
                    </span>
                  </td>
                  <td style={{ padding: "8px 10px", color: "var(--fm-muted)", whiteSpace: "nowrap" }}>{z.udalost || "—"}</td>
                  <td style={{ padding: "8px 10px", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{z.zprava}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* =================== Stránka =================== */
export default function Konektor() {
  const [uzivatel, setUzivatel] = useState(null);
  const [chyba, setChyba] = useState(null);
  const navigate = useNavigate();

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
  if (!uzivatel) return null;

  return (
    <Layout uzivatel={uzivatel}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link to="/rozcestnik" style={{ fontSize: 13, color: "var(--fm-muted)", textDecoration: "none" }}>
          ← Zpět na rozcestník
        </Link>
        <h2 style={{ margin: 0, fontSize: 18 }}>Konektor Raynet ↔ Google Disk</h2>
        <NastaveniKarta />
        <RucniAkceKarta />
        <LogyPanel onChyba={osetriChybu} />
      </div>
    </Layout>
  );
}
