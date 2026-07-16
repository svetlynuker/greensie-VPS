import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Layout from "../components/Layout";
import FakturaDialog from "../components/FakturaDialog";
import {
  nactiMe,
  nactiFinance,
  ulozFakturu,
  pridejFakturu,
  smazFakturu,
  synchronizujPohodu,
  logout,
} from "../api";
import "../styles/pohled2.css";

/* ---- Stavy faktury: barva (CSS třída fm-st-*) + ikona + text ----
   Uživatel je barvoslepý → nikdy se nespoléháme jen na barvu. */
const STAV_META = {
  potreba_vystavit: { text: "Potřeba vystavit", ikona: "✎" },
  vystaveno: { text: "Vystaveno", ikona: "📤" },
  zaplaceno: { text: "Zaplaceno", ikona: "✓" },
  nefakturuje: { text: "Nefakturuje se", ikona: "∅" },
};
const LEGENDA_STAVU = ["potreba_vystavit", "vystaveno", "zaplaceno", "nefakturuje"];

function fmtDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(s || "");
}

function fmtCastka(c) {
  if (c == null) return null;
  return new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 2 }).format(c) + " Kč";
}

export default function PrehledFinanci() {
  const [uzivatel, setUzivatel] = useState(null);
  const [data, setData] = useState(null); // { muze_editovat, max_faktur, projekty }
  const [chyba, setChyba] = useState(null);
  const [editace, setEditace] = useState(null); // { projekt, faktura }
  const [pohodaStav, setPohodaStav] = useState(null); // hláška po synchronizaci
  const [pohodaBezi, setPohodaBezi] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const zvyraznenyId = Number(searchParams.get("projekt")) || null;
  const zvyraznenyRef = useRef(null);

  async function nactiZnovu() {
    const d = await nactiFinance();
    setData(d);
    return d;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nactiFinance()])
      .then(([me, d]) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
        setData(d);
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("přihlášení") || m.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (m.includes("oprávnění")) {
          // nemá právo na finance → zpět na rozcestník
          navigate("/rozcestnik");
        } else {
          setChyba(m);
        }
      });
  }, [navigate]);

  // po načtení dat naskroluj na projekt z prokliku (?projekt=ID)
  useEffect(() => {
    if (data && zvyraznenyId && zvyraznenyRef.current) {
      zvyraznenyRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [data, zvyraznenyId]);

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!data) return null;

  const { projekty, max_faktur, muze_editovat } = data;
  const sloupceFaktur = Math.max(max_faktur, 1);

  async function ulozEditaci(hodnoty) {
    const ulozena = await ulozFakturu(editace.faktura.id, hodnoty);
    setData((d) => ({
      ...d,
      projekty: d.projekty.map((p) =>
        p.id !== editace.projekt.id
          ? p
          : { ...p, faktury: p.faktury.map((f) => (f.id === ulozena.id ? ulozena : f)) }
      ),
    }));
    setEditace(null);
  }

  async function smazEditaci() {
    await smazFakturu(editace.faktura.id);
    await nactiZnovu();
    setEditace(null);
  }

  async function pridej(projektId) {
    await pridejFakturu(projektId);
    await nactiZnovu();
  }

  async function spustPohodu() {
    setPohodaBezi(true);
    setPohodaStav(null);
    try {
      const v = await synchronizujPohodu();
      setPohodaStav(v.zprava);
      if (v.aktivni) await nactiZnovu();
    } catch (e) {
      setPohodaStav(e.message);
    } finally {
      setPohodaBezi(false);
    }
  }

  function bunkaFaktury(p, index) {
    // render podle pozice (N-tá faktura), ne podle uloženého poradi
    const fakt = [...p.faktury].sort((a, b) => a.poradi - b.poradi);
    return fakt[index] || null;
  }

  return (
    <Layout uzivatel={uzivatel}>
      <div className="fm-app">
        <Link to="/rozcestnik" className="fm-backlink">
          ← Zpět na rozcestník
        </Link>

        {/* Topbar */}
        <div className="fm-topbar">
          <span style={{ fontSize: 15, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--fm-brand)" }} />
            Přehled financí
          </span>
          {muze_editovat && (
            <button className="fm-btn fm-primary" onClick={spustPohodu} disabled={pohodaBezi}>
              {pohodaBezi ? "Synchronizuji…" : "↻ Synchronizovat s Pohodou"}
            </button>
          )}
          {pohodaStav && <span className="fm-status">{pohodaStav}</span>}
          <span className="fm-spacer" />
          <span className="fm-status">
            <b>{projekty.length}</b> projektů
          </span>
        </div>

        {/* Legenda stavů – vždy viditelná, barva + ikona + text */}
        <div className="fm-fa-legend">
          <span className="fm-legend-title">Stavy faktur:</span>
          {LEGENDA_STAVU.map((klic) => (
            <span key={klic} className={`fm-st-${klic}`}>
              <span className="fm-pin" />
              <span className="fm-cell-icon">{STAV_META[klic].ikona}</span>
              {STAV_META[klic].text}
            </span>
          ))}
        </div>

        <div className="fm-scroll">
          <table className="fm-matrix">
            <thead>
              <tr>
                <th className="fm-col-proj" style={{ left: 0 }}>
                  Projekt
                </th>
                <th className="fm-col-term" style={{ left: "var(--fm-w-proj)" }}>
                  Termín
                </th>
                {Array.from({ length: sloupceFaktur }, (_, i) => (
                  <th key={i} className="fm-th-task">
                    <span className="fm-th-name">Faktura {i + 1}</span>
                  </th>
                ))}
                {muze_editovat && <th className="fm-th-task">Přidat</th>}
              </tr>
            </thead>
            <tbody>
              {projekty.map((p) => {
                const zvyrazneny = p.id === zvyraznenyId;
                return (
                  <tr
                    key={p.id}
                    id={`projekt-${p.id}`}
                    ref={zvyrazneny ? zvyraznenyRef : null}
                    className={zvyrazneny ? "fm-fa-highlight" : ""}
                  >
                    <td className="fm-col-proj" style={{ left: 0 }}>
                      <span className="fm-proj-name">
                        {p.url ? (
                          <a href={p.url} target="_blank" rel="noopener noreferrer">
                            {p.nazev}
                          </a>
                        ) : (
                          p.nazev
                        )}
                      </span>
                    </td>
                    <td className="fm-col-term" style={{ left: "var(--fm-w-proj)" }}>
                      {p.termin ? (
                        <span className="fm-term">
                          <span className="fm-term-label">Termín:</span> {fmtDate(p.termin)}
                        </span>
                      ) : (
                        <span className="fm-term fm-none">bez termínu</span>
                      )}
                    </td>

                    {Array.from({ length: sloupceFaktur }, (_, i) => {
                      const f = bunkaFaktury(p, i);
                      if (!f) {
                        return (
                          <td key={i} className="fm-fa fm-empty">
                            <span className="fm-cell-empty-hint">·</span>
                          </td>
                        );
                      }
                      const meta = STAV_META[f.stav] || STAV_META.potreba_vystavit;
                      return (
                        <td
                          key={i}
                          className={`fm-fa fm-st-${f.stav}`}
                          title={f.poznamka || undefined}
                          onClick={() => muze_editovat && setEditace({ projekt: p, faktura: f })}
                        >
                          <span className="fm-cell-status">
                            <span className="fm-pin" />
                            <span className="fm-cell-icon">{meta.ikona}</span>
                            {meta.text}
                          </span>
                          {f.castka != null && <div className="fm-fa-castka">{fmtCastka(f.castka)}</div>}
                          {f.termin && <div className="fm-cell-term">Termín: {fmtDate(f.termin)}</div>}
                          {f.variabilni_symbol && <div className="fm-fa-vs">VS: {f.variabilni_symbol}</div>}
                          {f.pohoda_potvrzeno && <div className="fm-fa-pohoda">✓ Pohoda</div>}
                          {f.poznamka && (
                            <div className="fm-cell-note" title={f.poznamka}>
                              {f.poznamka}
                            </div>
                          )}
                        </td>
                      );
                    })}

                    {muze_editovat && (
                      <td className="fm-fa fm-empty" style={{ cursor: "default" }}>
                        <button className="fm-fa-add" onClick={() => pridej(p.id)} title="Přidat další fakturu">
                          + faktura
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
              {projekty.length === 0 && (
                <tr>
                  <td
                    colSpan={2 + sloupceFaktur + (muze_editovat ? 1 : 0)}
                    style={{ padding: 40, textAlign: "center", color: "var(--fm-muted)" }}
                  >
                    Zatím žádné projekty. Projekty se načítají v Přehledu projektů z Freela.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editace && (
        <FakturaDialog
          projektNazev={editace.projekt.nazev}
          faktura={editace.faktura}
          onSave={ulozEditaci}
          onDelete={smazEditaci}
          onClose={() => setEditace(null)}
        />
      )}
    </Layout>
  );
}
