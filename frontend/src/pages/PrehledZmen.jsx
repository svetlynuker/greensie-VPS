import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import { nactiMe, nactiZmeny, logout } from "../api";
import "../styles/pohled3.css";

/* ---- Datumové pomocníky ---- */
function dnesISO() {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const den = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${den}`;
}
function predDny(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const den = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${den}`;
}
function fmtDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(s || "");
}

/* jeden úkol v rozbaleném detailu */
function UkolPolozka({ u, sTerminem }) {
  const nazev = u.nazev || u.ukol || "(bez názvu)";
  return (
    <li>
      {u.faze ? <span className="pz-det-faze">{u.faze} · </span> : null}
      {u.url ? (
        <a href={u.url} target="_blank" rel="noopener noreferrer">
          {nazev}
        </a>
      ) : (
        nazev
      )}
      {sTerminem && u.termin ? (
        <span className="pz-det-term">({fmtDate(u.termin)})</span>
      ) : null}
    </li>
  );
}

function DetailSloupec({ trida, titulek, ukoly, sTerminem }) {
  return (
    <div className={`pz-det-col ${trida}`}>
      <h4>
        {titulek} ({ukoly.length})
      </h4>
      {ukoly.length === 0 ? (
        <div className="pz-det-prazdne">–</div>
      ) : (
        <ul>
          {ukoly.map((u, i) => (
            <UkolPolozka key={i} u={u} sTerminem={sTerminem} />
          ))}
        </ul>
      )}
    </div>
  );
}

export default function PrehledZmen() {
  const [uzivatel, setUzivatel] = useState(null);
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [nacita, setNacita] = useState(false);
  const [rezim, setRezim] = useState("zacatek"); // zacatek | tyden | vlastni
  const [vlastniOd, setVlastniOd] = useState(predDny(30));
  const [vlastniDo, setVlastniDo] = useState(dnesISO());
  const [rozbaleny, setRozbaleny] = useState(null); // id projektu
  const navigate = useNavigate();

  // ověření přihlášení + práva hned na začátku
  useEffect(() => {
    nactiMe()
      .then((me) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  // parametry dotazu podle zvoleného režimu
  const parametry = useMemo(() => {
    if (rezim === "tyden") return { od: predDny(7), do: dnesISO() };
    if (rezim === "vlastni") return { od: vlastniOd, do: vlastniDo };
    return {}; // zacatek = od nejstaršího snímku po dnešek
  }, [rezim, vlastniOd, vlastniDo]);

  // načtení dat při změně parametrů
  useEffect(() => {
    if (!uzivatel) return;
    setNacita(true);
    nactiZmeny(parametry)
      .then((d) => {
        setData(d);
        setChyba(null);
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(m);
        }
      })
      .finally(() => setNacita(false));
  }, [uzivatel, parametry, navigate]);

  // škála pro proužek pohybu (max ze součtu splněno+spadlo napříč projekty)
  const maxKombinace = useMemo(() => {
    if (!data) return 0;
    return data.projekty.reduce(
      (m, p) => Math.max(m, p.splneno + p.spadlo_do_prodleni),
      0,
    );
  }, [data]);

  return (
    <Layout uzivatel={uzivatel}>
      <div className="pz-wrap">
        <Link to="/rozcestnik" className="fm-backlink">
          ← Rozcestník
        </Link>

        {/* Filtr období */}
        <div className="pz-filter">
          <div className="pz-seg">
            <button
              className={rezim === "zacatek" ? "pz-active" : ""}
              onClick={() => setRezim("zacatek")}
            >
              Od začátku
            </button>
            <button
              className={rezim === "tyden" ? "pz-active" : ""}
              onClick={() => setRezim("tyden")}
            >
              Posledních 7 dní
            </button>
            <button
              className={rezim === "vlastni" ? "pz-active" : ""}
              onClick={() => setRezim("vlastni")}
            >
              Vlastní rozmezí
            </button>
          </div>

          {rezim === "vlastni" && (
            <div className="pz-dates">
              <span>od</span>
              <input
                type="date"
                value={vlastniOd}
                max={vlastniDo || dnesISO()}
                onChange={(e) => setVlastniOd(e.target.value)}
              />
              <span>do</span>
              <input
                type="date"
                value={vlastniDo}
                min={vlastniOd}
                max={dnesISO()}
                onChange={(e) => setVlastniDo(e.target.value)}
              />
            </div>
          )}

          <div className="pz-spacer" />
          {data && (
            <div className="pz-obdobi">
              Období: <b>{fmtDate(data.od)}</b> – <b>{fmtDate(data.do)}</b>
            </div>
          )}
        </div>

        {chyba && (
          <div style={{ padding: 16, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
        )}

        {/* Hláška o pokrytí dat */}
        {data && data.sledovano_od && data.od < data.sledovano_od && (
          <p className="pz-info">
            Změny se sledují až od {fmtDate(data.sledovano_od)} – pro starší
            období data nejsou.
          </p>
        )}
        {data && !data.sledovano_od && (
          <p className="pz-info">
            Zatím nebyl pořízen žádný snímek stavu – první se uloží automaticky
            do hodiny po nasazení a stane se výchozí základnou.
          </p>
        )}

        {/* Souhrnné karty */}
        {data && (
          <div className="pz-cards">
            <div className="pz-card pz-c-done">
              <div className="pz-card-num">{data.souhrn.splneno}</div>
              <div className="pz-card-lbl">Splněno</div>
            </div>
            <div className="pz-card pz-c-fall">
              <div className="pz-card-num">{data.souhrn.spadlo_do_prodleni}</div>
              <div className="pz-card-lbl">Spadlo do prodlení</div>
            </div>
            <div className="pz-card pz-c-late">
              <div className="pz-card-num">{data.souhrn.aktualne_v_prodleni}</div>
              <div className="pz-card-lbl">Aktuálně v prodlení</div>
            </div>
          </div>
        )}

        {/* Tabulka projektů */}
        {data && data.projekty.length > 0 && (
          <div className="pz-table">
            <div className="pz-row pz-head">
              <div>Projekt</div>
              <div>Pohyb (zelená splněno · červená prodlení)</div>
              <div style={{ textAlign: "center" }}>Splněno</div>
              <div style={{ textAlign: "center" }}>Spadlo</div>
              <div style={{ textAlign: "center" }}>V prodlení</div>
            </div>

            {data.projekty.map((p) => {
              const otevreno = rozbaleny === p.id;
              const sirka = maxKombinace > 0 ? 100 / maxKombinace : 0;
              return (
                <div key={p.id}>
                  <div
                    className="pz-row"
                    onClick={() => setRozbaleny(otevreno ? null : p.id)}
                  >
                    <div className="pz-name">
                      <span className="pz-caret">{otevreno ? "▾" : "▸"}</span>
                      <span className="pz-name-txt" title={p.nazev}>
                        {p.nazev}
                      </span>
                    </div>
                    <div
                      className="pz-bar"
                      title={`Splněno ${p.splneno}, spadlo do prodlení ${p.spadlo_do_prodleni}`}
                    >
                      <span
                        className="pz-bar-done"
                        style={{ width: `${p.splneno * sirka}%` }}
                      />
                      <span
                        className="pz-bar-fall"
                        style={{ width: `${p.spadlo_do_prodleni * sirka}%` }}
                      />
                    </div>
                    <div className={`pz-num ${p.splneno ? "pz-done" : "pz-zero"}`}>
                      {p.splneno}
                    </div>
                    <div
                      className={`pz-num ${p.spadlo_do_prodleni ? "pz-fall" : "pz-zero"}`}
                    >
                      {p.spadlo_do_prodleni}
                    </div>
                    <div
                      className={`pz-num ${p.aktualne_v_prodleni ? "pz-late" : "pz-zero"}`}
                    >
                      {p.aktualne_v_prodleni}
                    </div>
                  </div>

                  {otevreno && (
                    <div className="pz-detail">
                      <DetailSloupec
                        trida="pz-done"
                        titulek="Splněno"
                        ukoly={p.detail_splneno}
                      />
                      <DetailSloupec
                        trida="pz-fall"
                        titulek="Spadlo do prodlení"
                        ukoly={p.detail_spadlo}
                        sTerminem
                      />
                      <DetailSloupec
                        trida="pz-late"
                        titulek="Aktuálně v prodlení"
                        ukoly={p.detail_prodleni}
                        sTerminem
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Prázdný stav */}
        {data && data.projekty.length === 0 && !nacita && (
          <div className="pz-table">
            <div className="pz-empty">
              Za zvolené období se v žádném projektu nic nezměnilo.
            </div>
          </div>
        )}

        {nacita && !data && (
          <div style={{ padding: 24, color: "var(--fm-muted)" }}>Načítám…</div>
        )}
      </div>
    </Layout>
  );
}
