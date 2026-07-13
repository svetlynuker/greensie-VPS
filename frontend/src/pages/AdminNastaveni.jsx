import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import {
  nactiMe,
  logout,
  adminCiselniky,
  adminUzivatele,
  adminPridejUzivatele,
  adminUpravUzivatele,
  adminSmazUzivatele,
  adminResetHesla,
  adminSkupiny,
  adminPridejSkupinu,
  adminUpravSkupinu,
  adminSmazSkupinu,
} from "../api";

const poleStyl = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
};
const labelStyl = { display: "block", fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 4 };

/* ---------- společný modal ---------- */
function Modal({ nadpis, children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(31,41,51,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: 16,
      }}
    >
      <div
        className="fm-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          padding: 20,
          width: "min(460px, 100%)",
          maxHeight: "90vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>{nadpis}</h3>
        {children}
      </div>
    </div>
  );
}

/* ---------- výběr práv (zaškrtávátka) ---------- */
function PravaVyber({ katalog, vybrana, onZmena }) {
  const set = new Set(vybrana);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {katalog.map((p) => (
        <label key={p.klic} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={set.has(p.klic)}
            onChange={(e) => {
              const nove = new Set(set);
              if (e.target.checked) nove.add(p.klic);
              else nove.delete(p.klic);
              onZmena([...nove]);
            }}
          />
          {p.nazev}
        </label>
      ))}
    </div>
  );
}

/* ---------- editor uživatele ---------- */
function UzivatelEditor({ uzivatel, ciselniky, skupiny, onSave, onClose }) {
  const novy = !uzivatel;
  const [jmeno, setJmeno] = useState(uzivatel?.jmeno || "");
  const [email, setEmail] = useState(uzivatel?.email || "");
  const [jeAdmin, setJeAdmin] = useState(uzivatel?.je_admin || false);
  const [skupinaId, setSkupinaId] = useState(uzivatel?.skupina_id ?? "");
  const [extraPrava, setExtraPrava] = useState(uzivatel?.extra_prava || []);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        jmeno,
        email,
        je_admin: jeAdmin,
        skupina_id: skupinaId === "" ? null : Number(skupinaId),
        extra_prava: extraPrava,
      });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={novy ? "Přidat uživatele" : "Upravit uživatele"} onClose={onClose}>
      <div>
        <label style={labelStyl}>Jméno</label>
        <input style={poleStyl} value={jmeno} onChange={(e) => setJmeno(e.target.value)} placeholder="Jan Novák" />
      </div>
      <div>
        <label style={labelStyl}>E-mail</label>
        <input style={poleStyl} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jan@greensie.cz" />
      </div>
      {novy && (
        <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
          Heslo se vygeneruje automaticky a pošle uživateli. Při prvním přihlášení si zvolí vlastní.
        </div>
      )}
      <div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={jeAdmin} onChange={(e) => setJeAdmin(e.target.checked)} />
          <strong>Supersprávce</strong> – plný přístup ke všemu
        </label>
        {jeAdmin && (
          <div style={{ fontSize: 12, color: "var(--fm-muted)", marginTop: 4 }}>
            Supersprávce vidí a otevře vše; skupina a práva navíc se ignorují.
          </div>
        )}
      </div>
      <div style={{ opacity: jeAdmin ? 0.5 : 1, pointerEvents: jeAdmin ? "none" : "auto" }}>
        <label style={labelStyl}>Skupina</label>
        <select style={poleStyl} value={skupinaId} onChange={(e) => setSkupinaId(e.target.value)}>
          <option value="">— žádná —</option>
          {skupiny.map((s) => (
            <option key={s.id} value={s.id}>{s.nazev}</option>
          ))}
        </select>
        <label style={{ ...labelStyl, marginTop: 12 }}>Práva navíc (mimo skupinu)</label>
        <PravaVyber katalog={ciselniky.prava} vybrana={extraPrava} onZmena={setExtraPrava} />
      </div>
      {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- dialog resetu hesla ---------- */
function ResetDialog({ uzivatel, onReset, onClose }) {
  const [rezim, setRezim] = useState("generovat"); // "generovat" | "vlastni"
  const [heslo, setHeslo] = useState("");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onReset(uzivatel.id, rezim === "vlastni" ? heslo : null);
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={`Reset hesla – ${uzivatel.jmeno}`} onClose={onClose}>
      <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>
        Po resetu si uživatel při dalším přihlášení nastaví vlastní heslo.
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
        <input type="radio" checked={rezim === "generovat"} onChange={() => setRezim("generovat")} />
        Vygenerovat nové heslo
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
        <input type="radio" checked={rezim === "vlastni"} onChange={() => setRezim("vlastni")} />
        Zadat vlastní heslo
      </label>
      {rezim === "vlastni" && (
        <input
          style={poleStyl}
          type="text"
          value={heslo}
          onChange={(e) => setHeslo(e.target.value)}
          placeholder="alespoň 6 znaků"
        />
      )}
      {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Resetuji…" : "Resetovat heslo"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- výsledek s heslem (po vytvoření / resetu) ---------- */
function HesloVysledekModal({ vysledek, onClose }) {
  const { uzivatel, heslo, email_odeslan, email_poznamka } = vysledek;
  const odkaz = window.location.origin;
  const [zkopirovano, setZkopirovano] = useState(false);

  function kopiruj() {
    const text = `Přihlášení: ${odkaz}\nE-mail: ${uzivatel.email}\nHeslo: ${heslo}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setZkopirovano(true);
        setTimeout(() => setZkopirovano(false), 1500);
      });
    }
  }

  return (
    <Modal nadpis="Přihlašovací údaje" onClose={onClose}>
      <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>
        Jednorázové heslo pro <strong>{uzivatel.jmeno}</strong>. Zobrazí se jen teď – zkopíruj si ho.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, background: "var(--fm-head)", borderRadius: 8, padding: 12 }}>
        <div style={{ fontSize: 13 }}><span style={{ color: "var(--fm-muted)" }}>Odkaz: </span>{odkaz}</div>
        <div style={{ fontSize: 13 }}><span style={{ color: "var(--fm-muted)" }}>E-mail: </span>{uzivatel.email}</div>
        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "monospace" }}>{heslo}</div>
      </div>
      <div style={{ fontSize: 13, color: email_odeslan ? "var(--fm-brand-dk)" : "var(--fm-muted)" }}>
        {email_odeslan ? "✓ Odesláno e-mailem uživateli." : email_poznamka || "E-mail nebyl odeslán."}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={kopiruj}>{zkopirovano ? "Zkopírováno ✓" : "Kopírovat údaje"}</button>
        <button className="fm-btn fm-primary" onClick={onClose}>Hotovo</button>
      </div>
    </Modal>
  );
}

/* ---------- editor skupiny ---------- */
function SkupinaEditor({ skupina, ciselniky, onSave, onClose }) {
  const novy = !skupina;
  const [nazev, setNazev] = useState(skupina?.nazev || "");
  const [prava, setPrava] = useState(skupina?.prava || []);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({ nazev, prava });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={novy ? "Přidat skupinu" : "Upravit skupinu"} onClose={onClose}>
      <div>
        <label style={labelStyl}>Název skupiny</label>
        <input style={poleStyl} value={nazev} onChange={(e) => setNazev(e.target.value)} placeholder="např. Projektoví manažeři" />
      </div>
      <div>
        <label style={labelStyl}>Co smí členové skupiny</label>
        <PravaVyber katalog={ciselniky.prava} vybrana={prava} onZmena={setPrava} />
      </div>
      {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- barevný štítek práva ---------- */
function Chip({ children }) {
  return (
    <span
      style={{
        display: "inline-block",
        background: "var(--fm-brand-soft)",
        color: "var(--fm-brand-dk)",
        borderRadius: 999,
        padding: "2px 9px",
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      {children}
    </span>
  );
}

export default function AdminNastaveni() {
  const [uzivatel, setUzivatel] = useState(null);
  const [ciselniky, setCiselniky] = useState(null);
  const [uzivatele, setUzivatele] = useState([]);
  const [skupiny, setSkupiny] = useState([]);
  const [chyba, setChyba] = useState(null);
  const [editUzivatel, setEditUzivatel] = useState(null); // {} = nový, obj = úprava
  const [editSkupina, setEditSkupina] = useState(null);
  const [resetUzivatel, setResetUzivatel] = useState(null);
  const [hesloVysledek, setHesloVysledek] = useState(null);
  const navigate = useNavigate();

  const nazvyPrav = (klice) => {
    if (!ciselniky) return [];
    return ciselniky.prava.filter((p) => klice.includes(p.klic)).map((p) => p.nazev);
  };
  const nazevSkupiny = (id) => skupiny.find((s) => s.id === id)?.nazev || "—";

  async function nactiVse() {
    const [c, u, s] = await Promise.all([adminCiselniky(), adminUzivatele(), adminSkupiny()]);
    setCiselniky(c);
    setUzivatele(u);
    setSkupiny(s);
  }

  useEffect(() => {
    nactiMe()
      .then((me) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
        return nactiVse();
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("přihlášení")) {
          logout();
          navigate("/");
        } else {
          setChyba(m); // typicky 403 = nemáš na admin právo
        }
      });
  }, [navigate]);

  async function ulozUzivatele(data) {
    if (editUzivatel && editUzivatel.id) {
      await adminUpravUzivatele(editUzivatel.id, data);
      setEditUzivatel(null);
      await nactiVse();
    } else {
      const vysledek = await adminPridejUzivatele(data);
      setEditUzivatel(null);
      await nactiVse();
      setHesloVysledek(vysledek); // zobrazí jednorázové heslo + odkaz
    }
  }
  async function provedReset(id, noveHeslo) {
    const vysledek = await adminResetHesla(id, noveHeslo);
    setResetUzivatel(null);
    await nactiVse();
    setHesloVysledek(vysledek);
  }
  async function smazUzivatele(u) {
    if (!window.confirm(`Opravdu smazat uživatele ${u.jmeno}?`)) return;
    try {
      await adminSmazUzivatele(u.id);
      await nactiVse();
    } catch (e) {
      alert(e.message);
    }
  }
  async function ulozSkupinu(data) {
    if (editSkupina && editSkupina.id) await adminUpravSkupinu(editSkupina.id, data);
    else await adminPridejSkupinu(data);
    setEditSkupina(null);
    await nactiVse();
  }
  async function smazSkupinu(s) {
    if (!window.confirm(`Opravdu smazat skupinu „${s.nazev}"? Členům se skupina odebere.`)) return;
    try {
      await adminSmazSkupinu(s.id);
      await nactiVse();
    } catch (e) {
      alert(e.message);
    }
  }

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <Link to="/rozcestnik" className="fm-btn" style={{ textDecoration: "none" }}>← Zpět na rozcestník</Link>
        <div style={{ padding: 24, color: "#c92a2a" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!ciselniky) return null;

  return (
    <Layout uzivatel={uzivatel}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Link to="/rozcestnik" style={{ fontSize: 13, color: "var(--fm-muted)", textDecoration: "none" }}>
          ← Zpět na rozcestník
        </Link>
        <h2 style={{ margin: 0, fontSize: 18 }}>Admin nastavení</h2>

        {/* ---- Uživatelé ---- */}
        <div className="fm-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 15 }}>Uživatelé</strong>
            <span style={{ color: "var(--fm-muted)", fontSize: 13, marginLeft: 8 }}>({uzivatele.length})</span>
            <div style={{ flex: 1 }} />
            <button className="fm-btn fm-primary" onClick={() => setEditUzivatel({})}>+ Přidat uživatele</button>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 640 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--fm-muted)" }}>
                  <th style={{ padding: "8px 10px" }}>Jméno</th>
                  <th style={{ padding: "8px 10px" }}>E-mail</th>
                  <th style={{ padding: "8px 10px" }}>Přístup</th>
                  <th style={{ padding: "8px 10px" }}>Skupina</th>
                  <th style={{ padding: "8px 10px" }}>Práva navíc</th>
                  <th style={{ padding: "8px 10px", textAlign: "right" }}>Akce</th>
                </tr>
              </thead>
              <tbody>
                {uzivatele.map((u) => (
                  <tr key={u.id} style={{ borderTop: "1px solid var(--fm-line)" }}>
                    <td style={{ padding: "8px 10px", fontWeight: 600 }}>{u.jmeno}</td>
                    <td style={{ padding: "8px 10px", color: "var(--fm-muted)" }}>{u.email}</td>
                    <td style={{ padding: "8px 10px" }}>
                      {u.je_admin ? <Chip>Supersprávce</Chip> : <span style={{ color: "var(--fm-muted)" }}>Uživatel</span>}
                      {u.musi_zmenit_heslo && (
                        <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 2 }}>🔑 čeká na změnu hesla</div>
                      )}
                    </td>
                    <td style={{ padding: "8px 10px" }}>{u.skupina_id ? nazevSkupiny(u.skupina_id) : <span style={{ color: "var(--fm-muted)" }}>—</span>}</td>
                    <td style={{ padding: "8px 10px" }}>
                      <span style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {u.extra_prava.length ? nazvyPrav(u.extra_prava).map((n) => <Chip key={n}>{n}</Chip>) : <span style={{ color: "var(--fm-muted)" }}>—</span>}
                      </span>
                    </td>
                    <td style={{ padding: "8px 10px", textAlign: "right", whiteSpace: "nowrap" }}>
                      <button className="fm-btn" style={{ padding: "5px 10px" }} onClick={() => setEditUzivatel(u)}>Upravit</button>{" "}
                      <button className="fm-btn" style={{ padding: "5px 10px" }} onClick={() => setResetUzivatel(u)}>Reset hesla</button>{" "}
                      <button className="fm-btn" style={{ padding: "5px 10px" }} onClick={() => smazUzivatele(u)}>Smazat</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ---- Skupiny ---- */}
        <div className="fm-card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
            <strong style={{ fontSize: 15 }}>Skupiny</strong>
            <span style={{ color: "var(--fm-muted)", fontSize: 13, marginLeft: 8 }}>({skupiny.length})</span>
            <div style={{ flex: 1 }} />
            <button className="fm-btn fm-primary" onClick={() => setEditSkupina({})}>+ Přidat skupinu</button>
          </div>
          {skupiny.length === 0 ? (
            <div style={{ color: "var(--fm-muted)", fontSize: 13, padding: "8px 2px" }}>
              Zatím žádné skupiny. Skupina sdružuje uživatele se stejnými právy – vytvoř si třeba „Vedení" a zaškrtni, co smí otevřít.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {skupiny.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 12px",
                    border: "1px solid var(--fm-line)",
                    borderRadius: 10,
                  }}
                >
                  <div style={{ minWidth: 140 }}>
                    <div style={{ fontWeight: 700 }}>{s.nazev}</div>
                    <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>{s.pocet_clenu} členů</div>
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4, flex: 1 }}>
                    {s.prava.length ? nazvyPrav(s.prava).map((n) => <Chip key={n}>{n}</Chip>) : <span style={{ color: "var(--fm-muted)", fontSize: 13 }}>žádná práva</span>}
                  </div>
                  <button className="fm-btn" style={{ padding: "5px 10px" }} onClick={() => setEditSkupina(s)}>Upravit</button>
                  <button className="fm-btn" style={{ padding: "5px 10px" }} onClick={() => smazSkupinu(s)}>Smazat</button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {editUzivatel && (
        <UzivatelEditor
          uzivatel={editUzivatel.id ? editUzivatel : null}
          ciselniky={ciselniky}
          skupiny={skupiny}
          onSave={ulozUzivatele}
          onClose={() => setEditUzivatel(null)}
        />
      )}
      {editSkupina && (
        <SkupinaEditor
          skupina={editSkupina.id ? editSkupina : null}
          ciselniky={ciselniky}
          onSave={ulozSkupinu}
          onClose={() => setEditSkupina(null)}
        />
      )}
      {resetUzivatel && (
        <ResetDialog
          uzivatel={resetUzivatel}
          onReset={provedReset}
          onClose={() => setResetUzivatel(null)}
        />
      )}
      {hesloVysledek && (
        <HesloVysledekModal vysledek={hesloVysledek} onClose={() => setHesloVysledek(null)} />
      )}
    </Layout>
  );
}
