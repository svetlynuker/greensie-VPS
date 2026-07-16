import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import BunkaDialog from "../components/BunkaDialog";
import FreeloDialog from "../components/FreeloDialog";
import PridatDialog from "../components/PridatDialog";
import ZobrazeniDropdown from "../components/ZobrazeniDropdown";
import {
  nactiMe,
  nactiMatici,
  nactiNastaveni,
  ulozNastaveni,
  logout,
  ulozBunku,
  pridejProjekt,
  pridejSloupec,
  nacistZFreela,
  ulozBarvy,
  nastavZobrazeniProjektu,
} from "../api";
import "../styles/pohled1.css";

/* ---- Termíny ---- */
function parseDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}
function fmtDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(s || "");
}
function vRozsahu(d, od, do_) {
  return (od === null || d >= od) && (do_ === null || d <= do_);
}
// d = dnes - termín (dnů). Záporné = před termínem, kladné = po termínu.
function deadlineLevel(termin, barvy) {
  const dl = parseDate(termin);
  if (!dl) return "none";
  const dnes = new Date();
  dnes.setHours(0, 0, 0, 0);
  const d = Math.round((dnes - dl) / 86400000);
  if (vRozsahu(d, barvy.zelena_od, barvy.zelena_do)) return "green";
  if (vRozsahu(d, barvy.zluta_od, barvy.zluta_do)) return "yellow";
  if (vRozsahu(d, barvy.oranzova_od, barvy.oranzova_do)) return "orange";
  if (vRozsahu(d, barvy.cervena_od, barvy.cervena_do)) return "red";
  return "none";
}

/* ---- Prahy legendy: text <-> {od, do} ---- */
function formatRange(od, do_, druh) {
  if (druh === "green") return od === null && do_ !== null ? String(do_) : od !== null && do_ !== null ? `${od}/${do_}` : "";
  if (druh === "red") return do_ === null && od !== null ? String(od) : od !== null && do_ !== null ? `${od}/${do_}` : "";
  if (od === null && do_ === null) return "";
  return `${od ?? ""}/${do_ ?? ""}`;
}
function cislo(x) {
  const t = String(x).trim();
  if (t === "") return null;
  if (!/^-?\d+$/.test(t)) throw new Error(`Neplatné číslo: „${t}“`);
  return parseInt(t, 10);
}
function parseRange(text, druh) {
  const t = String(text).trim();
  if (t === "") return { od: null, do: null };
  if (t.includes("/")) {
    const [a, b] = t.split("/");
    return { od: cislo(a), do: cislo(b) };
  }
  const n = cislo(t);
  if (druh === "green") return { od: null, do: n };
  if (druh === "red") return { od: n, do: null };
  return { od: n, do: n };
}

// Barvy přes tokeny --st-* (global.css) — legenda tak vždy ukazuje totéž,
// co buňky, i v tmavém režimu a při kompenzaci červeno-zelené vady.
const LEGENDA = [
  { druh: "green", barva: "var(--st-good)", popis: "v termínu", prefixOd: "zelena_od", prefixDo: "zelena_do" },
  { druh: "yellow", barva: "var(--st-warn)", popis: "blíží se", prefixOd: "zluta_od", prefixDo: "zluta_do" },
  { druh: "orange", barva: "var(--st-serious)", popis: "po termínu", prefixOd: "oranzova_od", prefixDo: "oranzova_do" },
  { druh: "red", barva: "var(--st-crit)", popis: "hodně po", prefixOd: "cervena_od", prefixDo: "cervena_do" },
];

function bunkaKlic(projektId, sloupecId) {
  return `${projektId}||${sloupecId}`;
}

// malá ikonka oka pro skrytí úkolu/fáze
function Oko({ onClick, title }) {
  return (
    <span
      className="fm-eye"
      title={title}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
    >
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </span>
  );
}

// Nastavení pohledu se ukládá do DB (přenáší se mezi zařízeními).
// Zde se z uloženého JSON objektu poskládá vnitřní stav (Set / pole).
function parseSkryte(p) {
  p = p || {};
  return { faze: new Set(p.faze || []), ukoly: new Set(p.ukoly || []) };
}

function parsePoradi(p) {
  p = p || {};
  return { projekty: p.projekty || [], faze: p.faze || [], ukoly: p.ukoly || {} };
}

// seřadí položky podle uloženého pořadí klíčů; položky mimo pořadí zůstanou vzadu (stabilně)
function seradPodle(items, poradi, klicFn) {
  if (!poradi || poradi.length === 0) return items;
  const index = new Map(poradi.map((k, i) => [k, i]));
  return [...items].sort((a, b) => {
    const ia = index.has(klicFn(a)) ? index.get(klicFn(a)) : Infinity;
    const ib = index.has(klicFn(b)) ? index.get(klicFn(b)) : Infinity;
    return ia - ib;
  });
}

// přesune fromId před toId a vrátí nové kompletní pořadí id
function presunPole(ids, fromId, toId) {
  if (fromId === toId) return ids;
  const arr = [...ids];
  const fi = arr.indexOf(fromId);
  if (fi < 0) return ids;
  arr.splice(fi, 1);
  const ti = arr.indexOf(toId);
  if (ti < 0) return ids;
  arr.splice(ti, 0, fromId);
  return arr;
}

export default function PrehledProjektu() {
  const [uzivatel, setUzivatel] = useState(null);
  const [muzeFinance, setMuzeFinance] = useState(false);
  const [matice, setMatice] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [collapsed, setCollapsed] = useState({});
  const [nastrojeSkryte, setNastrojeSkryte] = useState(false);

  const [editace, setEditace] = useState(null); // {projekt, ukol, bunka}
  const [freeloOtevreno, setFreeloOtevreno] = useState(false);
  const [freeloBezi, setFreeloBezi] = useState(false);
  const [pridatProjekt, setPridatProjekt] = useState(false);
  const [pridatSloupec, setPridatSloupec] = useState(false);
  const [barvyText, setBarvyText] = useState(null);
  const [barvyStav, setBarvyStav] = useState(null);
  // per-uživatelské skrytí úkolů/fází (uloženo v prohlížeči dle ID uživatele)
  const [skryteFaze, setSkryteFaze] = useState(() => new Set());
  const [skryteUkoly, setSkryteUkoly] = useState(() => new Set());
  // per-uživatelské pořadí (drag & drop), uloženo v prohlížeči dle ID
  const [poradiProjektu, setPoradiProjektu] = useState([]);
  const [poradiFazi, setPoradiFazi] = useState([]);
  const [poradiUkolu, setPoradiUkolu] = useState({});
  const dragInfo = useRef(null);
  const [dropCil, setDropCil] = useState(null);
  const navigate = useNavigate();

  // Uložení nastavení pohledu do DB (voláno vždy po konkrétní akci uživatele).
  function ulozSkryte(faze, ukoly) {
    ulozNastaveni("pohled1_skryte", { faze: [...faze], ukoly: [...ukoly] }).catch(() => {});
  }
  function ulozPoradi(projekty, faze, ukoly) {
    ulozNastaveni("pohled1_poradi", { projekty, faze, ukoly }).catch(() => {});
  }

  function naplnBarvyText(barvy) {
    setBarvyText({
      green: formatRange(barvy.zelena_od, barvy.zelena_do, "green"),
      yellow: formatRange(barvy.zluta_od, barvy.zluta_do, "yellow"),
      orange: formatRange(barvy.oranzova_od, barvy.oranzova_do, "orange"),
      red: formatRange(barvy.cervena_od, barvy.cervena_do, "red"),
    });
  }

  async function nactiZnovu() {
    const d = await nactiMatici();
    setMatice(d);
    naplnBarvyText(d.barvy);
    return d;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nactiMatici(), nactiNastaveni()])
      .then(([me, d, nast]) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
        // proklik na finance ukazujeme jen tomu, kdo smí Přehled financí otevřít
        setMuzeFinance(!!me.dlazdice?.find((d) => d.klic === "finance")?.muze_otevrit);
        const skryte = parseSkryte(nast.pohled1_skryte);
        setSkryteFaze(skryte.faze);
        setSkryteUkoly(skryte.ukoly);
        const poradi = parsePoradi(nast.pohled1_poradi);
        setPoradiProjektu(poradi.projekty);
        setPoradiFazi(poradi.faze);
        setPoradiUkolu(poradi.ukoly);
        setMatice(d);
        naplnBarvyText(d.barvy);
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("uživatel") || m.includes("přihlášení")) {
          logout();
          navigate("/");
        } else {
          setChyba(m);
        }
      });
  }, [navigate]);

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!matice) return null;

  const { faze, projekty, bunky, barvy, muze_editovat } = matice;
  const pocetUkolu = faze.reduce((n, f) => n + f.ukoly.length, 0);
  // 1) aplikuj uživatelské pořadí (drag & drop)
  const seradaneProjekty = seradPodle(projekty, poradiProjektu, (p) => p.id);
  const seradaneFaze = seradPodle(faze, poradiFazi, (f) => f.todo).map((f) => ({
    ...f,
    ukoly: seradPodle(f.ukoly, poradiUkolu[f.todo], (u) => u.sloupec_id),
  }));
  // 2) pak uživatelské skrytí
  const viditelneProjekty = seradaneProjekty.filter((p) => !p.skryty);
  const skryteProjekty = seradaneProjekty.filter((p) => p.skryty);
  const viditelneFaze = seradaneFaze
    .filter((f) => !skryteFaze.has(f.todo))
    .map((f) => ({ ...f, ukoly: f.ukoly.filter((u) => !skryteUkoly.has(u.sloupec_id)) }))
    .filter((f) => f.ukoly.length > 0);
  const pocetSloupcuMatice = viditelneFaze.reduce(
    (n, f) => n + (collapsed[f.todo] ? 1 : f.ukoly.length),
    0
  );

  function toggleFaze(todo) {
    setCollapsed((c) => ({ ...c, [todo]: !c[todo] }));
  }
  function sbalitVse() {
    const c = {};
    faze.forEach((f) => (c[f.todo] = true));
    setCollapsed(c);
  }
  function bunkaFor(projektId, sloupecId) {
    return bunky[bunkaKlic(projektId, sloupecId)] || null;
  }
  function toggleSkrytFazi(todo) {
    const n = new Set(skryteFaze);
    if (n.has(todo)) n.delete(todo);
    else n.add(todo);
    setSkryteFaze(n);
    ulozSkryte(n, skryteUkoly);
  }
  function toggleSkrytUkol(sloupecId) {
    const n = new Set(skryteUkoly);
    if (n.has(sloupecId)) n.delete(sloupecId);
    else n.add(sloupecId);
    setSkryteUkoly(n);
    ulozSkryte(skryteFaze, n);
  }
  function zobrazitVse() {
    const prazdneFaze = new Set();
    const prazdneUkoly = new Set();
    setSkryteFaze(prazdneFaze);
    setSkryteUkoly(prazdneUkoly);
    ulozSkryte(prazdneFaze, prazdneUkoly);
  }

  function dropProjekt(cilId) {
    const info = dragInfo.current;
    dragInfo.current = null;
    setDropCil(null);
    if (!info || info.typ !== "projekt" || info.id === cilId) return;
    const nove = presunPole(seradaneProjekty.map((p) => p.id), info.id, cilId);
    setPoradiProjektu(nove);
    ulozPoradi(nove, poradiFazi, poradiUkolu);
  }
  function dropFaze(cilTodo) {
    const info = dragInfo.current;
    dragInfo.current = null;
    setDropCil(null);
    if (!info || info.typ !== "faze" || info.todo === cilTodo) return;
    const nove = presunPole(seradaneFaze.map((f) => f.todo), info.todo, cilTodo);
    setPoradiFazi(nove);
    ulozPoradi(poradiProjektu, nove, poradiUkolu);
  }
  function dropUkol(fazeTodo, cilId) {
    const info = dragInfo.current;
    dragInfo.current = null;
    setDropCil(null);
    if (!info || info.typ !== "ukol" || info.faze !== fazeTodo || info.id === cilId) return;
    const faseObj = seradaneFaze.find((f) => f.todo === fazeTodo);
    if (!faseObj) return;
    const nove = presunPole(faseObj.ukoly.map((u) => u.sloupec_id), info.id, cilId);
    const noveUkolu = { ...poradiUkolu, [fazeTodo]: nove };
    setPoradiUkolu(noveUkolu);
    ulozPoradi(poradiProjektu, poradiFazi, noveUkolu);
  }

  function fazeStat(projektId, f) {
    let total = 0;
    let done = 0;
    const deadlines = [];
    f.ukoly.forEach((u) => {
      const c = bunkaFor(projektId, u.sloupec_id);
      if (c && c.stav) {
        total++;
        if (c.stav === "done") done++;
        else if (c.termin) deadlines.push(c.termin);
      }
    });
    const exists = total > 0;
    const allDone = exists && done === total;
    deadlines.sort();
    const term = allDone ? "" : deadlines.length ? deadlines[deadlines.length - 1] : "";
    const level = allDone ? "green" : term ? deadlineLevel(term, barvy) : "none";
    return { total, done, exists, allDone, term, level };
  }
  function projektStat(projektId) {
    let totalPhases = 0;
    let donePhases = 0;
    faze.forEach((f) => {
      const s = fazeStat(projektId, f);
      if (s.exists) {
        totalPhases++;
        if (s.allDone) donePhases++;
      }
    });
    return { totalPhases, donePhases };
  }

  function otevriBunku(projekt, ukol) {
    if (!muze_editovat) return;
    setEditace({ projekt, ukol, bunka: bunkaFor(projekt.id, ukol.sloupec_id) });
  }

  async function ulozEditaci(data) {
    const ulozena = await ulozBunku({
      projekt_id: editace.projekt.id,
      sloupec_id: editace.ukol.sloupec_id,
      ...data,
    });
    setMatice((m) => ({
      ...m,
      bunky: { ...m.bunky, [bunkaKlic(editace.projekt.id, editace.ukol.sloupec_id)]: ulozena },
    }));
    setEditace(null);
  }

  async function nastavZobrazeni(projektId, skryty) {
    const aktual = await nastavZobrazeniProjektu(projektId, skryty);
    setMatice((m) => ({
      ...m,
      projekty: m.projekty.map((p) => (p.id === projektId ? { ...p, skryty: aktual.skryty } : p)),
    }));
  }

  async function spustFreelo(rezim) {
    setFreeloBezi(true);
    try {
      await nacistZFreela(rezim);
      await nactiZnovu();
      setFreeloOtevreno(false);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setFreeloBezi(false);
    }
  }

  async function ulozBarvyPrahy() {
    setBarvyStav("uklada");
    try {
      const payload = {};
      LEGENDA.forEach((l) => {
        const { od, do: do_ } = parseRange(barvyText[l.druh], l.druh);
        payload[l.prefixOd] = od;
        payload[l.prefixDo] = do_;
      });
      const nove = await ulozBarvy(payload);
      setMatice((m) => ({ ...m, barvy: nove }));
      naplnBarvyText(nove);
      setBarvyStav("ok");
      setTimeout(() => setBarvyStav(null), 1500);
    } catch (e) {
      setBarvyStav(null);
      setChyba(e.message);
    }
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
            Přehled projektů
          </span>
          <button className="fm-btn fm-ghost" onClick={() => setNastrojeSkryte((v) => !v)}>
            {nastrojeSkryte ? "Zobrazit nástroje ▾" : "Skrýt nástroje ▴"}
          </button>

          {!nastrojeSkryte && (
            <>
              {muze_editovat && (
                <>
                  <button className="fm-btn fm-primary" onClick={() => setFreeloOtevreno(true)}>
                    ↻ Načíst z Freelo
                  </button>
                  <button className="fm-btn" onClick={() => setPridatProjekt(true)}>
                    + Projekt
                  </button>
                  <button className="fm-btn" onClick={() => setPridatSloupec(true)}>
                    + Sloupec
                  </button>
                </>
              )}
              <span className="fm-group">
                <span className="fm-group-label">Fáze:</span>
                <button className="fm-btn fm-ghost" onClick={sbalitVse}>
                  Sbalit vše
                </button>
                <button className="fm-btn fm-ghost" onClick={() => setCollapsed({})}>
                  Rozbalit vše
                </button>
                <ZobrazeniDropdown
                  faze={seradaneFaze}
                  skryteFaze={skryteFaze}
                  skryteUkoly={skryteUkoly}
                  onToggleFaze={toggleSkrytFazi}
                  onToggleUkol={toggleSkrytUkol}
                  onZobrazitVse={zobrazitVse}
                />
                <button className="fm-btn fm-ghost" onClick={zobrazitVse}>
                  Zobrazit vše
                </button>
              </span>
              <span className="fm-spacer" />
              <span className="fm-status">
                <b>{viditelneProjekty.length}</b> projektů · <b>{faze.length}</b> fází · <b>{pocetUkolu}</b> úkolů
              {skryteProjekty.length > 0 && <> · {skryteProjekty.length} skrytých</>}
              </span>
            </>
          )}
        </div>

        {/* Legenda s konfigurovatelnými prahy */}
        <div className="fm-legend">
          <span className="fm-legend-title">Legenda termínů:</span>
          {LEGENDA.map((l) => (
            <span key={l.druh} className="fm-legend-col">
              <span>
                <i className="fm-lc" style={{ background: l.barva }} /> {l.popis}
              </span>
              {muze_editovat ? (
                <input
                  className="fm-legend-input"
                  value={barvyText?.[l.druh] ?? ""}
                  placeholder="např. -3/0"
                  title="Dny vůči termínu: záporné = před termínem, kladné = po. Rozsah „od/do“ (např. -14/-3) nebo jedno číslo."
                  onChange={(e) => setBarvyText((b) => ({ ...b, [l.druh]: e.target.value }))}
                />
              ) : (
                <span className="fm-legend-range">{barvyText?.[l.druh] || "—"}</span>
              )}
            </span>
          ))}
          {muze_editovat && (
            <button className="fm-btn" onClick={ulozBarvyPrahy} disabled={barvyStav === "uklada"}>
              {barvyStav === "uklada" ? "Ukládám…" : barvyStav === "ok" ? "Uloženo ✓" : "Uložit prahy"}
            </button>
          )}
        </div>

        {muze_editovat && skryteProjekty.length > 0 && (
          <div className="fm-card fm-skryte-panel">
            <span>Skryté projekty:</span>
            {skryteProjekty.map((p) => (
              <span key={p.id}>
                {p.nazev}{" "}
                <span className="fm-obnovit" onClick={() => nastavZobrazeni(p.id, false)}>
                  obnovit
                </span>
              </span>
            ))}
          </div>
        )}

        <div className="fm-scroll">
          <table className="fm-matrix">
            <thead>
              <tr>
                <th className="fm-col-handle" rowSpan={2}></th>
                <th className="fm-col-proj" rowSpan={2}>Projekt</th>
                <th className="fm-col-term" rowSpan={2}>Termín</th>
                <th className="fm-col-done" rowSpan={2}>Hotové fáze</th>
                {viditelneFaze.map((f) => (
                  <th
                    key={f.todo}
                    className={
                      "fm-grp" +
                      (dropCil?.typ === "faze" && dropCil.key === f.todo ? " fm-drop-col" : "")
                    }
                    colSpan={collapsed[f.todo] ? 1 : f.ukoly.length}
                    onClick={() => toggleFaze(f.todo)}
                    title="Klik: sbalit / rozbalit · táhni: přesunout fázi"
                    draggable
                    onDragStart={() => {
                      dragInfo.current = { typ: "faze", todo: f.todo };
                    }}
                    onDragEnd={() => {
                      dragInfo.current = null;
                      setDropCil(null);
                    }}
                    onDragOver={(e) => {
                      if (dragInfo.current?.typ === "faze") e.preventDefault();
                    }}
                    onDragEnter={() => {
                      if (dragInfo.current?.typ === "faze") setDropCil({ typ: "faze", key: f.todo });
                    }}
                    onDrop={() => dropFaze(f.todo)}
                  >
                    <Oko title="Skrýt fázi (Zobrazení → zpět)" onClick={() => toggleSkrytFazi(f.todo)} />
                    <span className="fm-grp-toggle">{collapsed[f.todo] ? "▸" : "▾"}</span>
                    {f.todo || "—"}
                  </th>
                ))}
              </tr>
              <tr className="fm-tasks">
                {viditelneFaze.map((f) =>
                  collapsed[f.todo] ? (
                    <th key={f.todo} className="fm-th-sum">termín · hotovo</th>
                  ) : (
                    f.ukoly.map((u, ci) => (
                      <th
                        key={u.sloupec_id}
                        className={
                          "fm-th-task" +
                          (ci === 0 ? " fm-grp-start" : "") +
                          (dropCil?.typ === "ukol" && dropCil.key === u.sloupec_id ? " fm-drop-col" : "")
                        }
                        title="Táhni pro přesunutí úkolu (v rámci fáze)"
                        draggable
                        onDragStart={() => {
                          dragInfo.current = { typ: "ukol", id: u.sloupec_id, faze: f.todo };
                        }}
                        onDragEnd={() => {
                          dragInfo.current = null;
                          setDropCil(null);
                        }}
                        onDragOver={(e) => {
                          if (dragInfo.current?.typ === "ukol" && dragInfo.current.faze === f.todo)
                            e.preventDefault();
                        }}
                        onDragEnter={() => {
                          if (dragInfo.current?.typ === "ukol" && dragInfo.current.faze === f.todo)
                            setDropCil({ typ: "ukol", key: u.sloupec_id });
                        }}
                        onDrop={() => dropUkol(f.todo, u.sloupec_id)}
                      >
                        <Oko title="Skrýt úkol (Zobrazení → zpět)" onClick={() => toggleSkrytUkol(u.sloupec_id)} />
                        <span className="fm-th-name">{u.nazev}</span>
                      </th>
                    ))
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {viditelneProjekty.map((p) => {
                const stat = projektStat(p.id);
                const pLevel = p.termin ? deadlineLevel(p.termin, barvy) : "none";
                const pct = stat.totalPhases > 0 ? Math.round((100 * stat.donePhases) / stat.totalPhases) : 0;
                const vseHotovo = stat.totalPhases > 0 && stat.donePhases === stat.totalPhases;
                return (
                  <tr
                    key={p.id}
                    className={dropCil?.typ === "projekt" && dropCil.key === p.id ? "fm-drop-row" : ""}
                    onDragOver={(e) => {
                      if (dragInfo.current?.typ === "projekt") e.preventDefault();
                    }}
                    onDragEnter={() => {
                      if (dragInfo.current?.typ === "projekt") setDropCil({ typ: "projekt", key: p.id });
                    }}
                    onDrop={() => dropProjekt(p.id)}
                  >
                    <td className="fm-col-handle">
                      <span
                        className="fm-handle"
                        title="Táhni pro změnu pořadí projektů"
                        draggable
                        onDragStart={() => {
                          dragInfo.current = { typ: "projekt", id: p.id };
                        }}
                        onDragEnd={() => {
                          dragInfo.current = null;
                          setDropCil(null);
                        }}
                      >
                        ⋮⋮
                      </span>
                    </td>
                    <td className={`fm-col-proj fm-lvl fm-lvl-${pLevel}`}>
                      <span className="fm-proj-name">
                        {p.url ? (
                          <a href={p.url} target="_blank" rel="noopener noreferrer">{p.nazev}</a>
                        ) : (
                          p.nazev
                        )}
                      </span>
                      {muzeFinance && (
                        <Link
                          to={`/finance?projekt=${p.id}`}
                          className="fm-fin-link"
                          title="Zobrazit faktury tohoto projektu (Přehled financí)"
                        >
                          💰 Finance
                        </Link>
                      )}
                      {muze_editovat && (
                        <span
                          className="fm-row-hide"
                          title="Skrýt projekt ze zobrazení (půjde obnovit)"
                          onClick={() => nastavZobrazeni(p.id, true)}
                        >
                          × skrýt řádek
                        </span>
                      )}
                    </td>
                    <td className="fm-col-term">
                      {p.termin ? (
                        <span className="fm-term">
                          <span className="fm-term-label">Termín:</span> {fmtDate(p.termin)}
                        </span>
                      ) : (
                        <span className="fm-term fm-none">bez termínu</span>
                      )}
                    </td>
                    <td className="fm-col-done">
                      <span className={"fm-done-badge" + (vseHotovo ? " fm-all" : "")}>
                        {stat.donePhases} / {stat.totalPhases}
                      </span>
                      <span className="fm-done-bar">
                        <span style={{ width: pct + "%" }} />
                      </span>
                    </td>

                    {viditelneFaze.map((f) => {
                      if (collapsed[f.todo]) {
                        const s = fazeStat(p.id, f);
                        if (!s.exists) {
                          return (
                            <td key={f.todo} className="fm-sum fm-empty fm-grp-start">
                              <span className="fm-cell-empty-hint">·</span>
                            </td>
                          );
                        }
                        const t = s.allDone ? "✓ hotovo" : s.term ? `Termín: ${fmtDate(s.term)}` : "bez termínu";
                        const spc = s.total ? Math.round((100 * s.done) / s.total) : 0;
                        return (
                          <td
                            key={f.todo}
                            className={`fm-sum fm-grp-start fm-lvl fm-lvl-${s.allDone ? "green" : s.level}`}
                            onClick={() => toggleFaze(f.todo)}
                            title="Klik: rozbalit fázi"
                          >
                            <div className="fm-sum-term">{t}</div>
                            <div className="fm-sum-count">{s.done} / {s.total} úkolů</div>
                            <span className="fm-done-bar"><span style={{ width: spc + "%" }} /></span>
                          </td>
                        );
                      }
                      return f.ukoly.map((u, ci) => {
                        const c = bunkaFor(p.id, u.sloupec_id);
                        const grpStart = ci === 0 ? " fm-grp-start" : "";
                        const klik = muze_editovat ? " fm-klik" : "";
                        if (!c || !c.stav) {
                          return (
                            <td
                              key={u.sloupec_id}
                              className={"fm-cell fm-empty" + grpStart + klik}
                              onClick={() => otevriBunku(p, u)}
                            >
                              <span className="fm-cell-empty-hint">·</span>
                            </td>
                          );
                        }
                        const termHtml = c.termin ? (
                          <div className="fm-cell-term">Termín: {fmtDate(c.termin)}</div>
                        ) : (
                          <div className="fm-cell-term fm-none">bez termínu</div>
                        );
                        const spolecne = (
                          <>
                            {termHtml}
                            {c.osoba && <div className="fm-cell-owner">{c.osoba}</div>}
                            {c.poznamka && (
                              <div className="fm-cell-note" title={c.poznamka}>{c.poznamka}</div>
                            )}
                          </>
                        );
                        if (c.stav === "done") {
                          return (
                            <td
                              key={u.sloupec_id}
                              className={"fm-cell fm-s-done" + grpStart + klik}
                              title={c.poznamka || undefined}
                              onClick={() => otevriBunku(p, u)}
                            >
                              <span className="fm-cell-status">
                                <span className="fm-pin" />
                                <span className="fm-cell-icon">✓</span>Hotovo
                              </span>
                              {spolecne}
                            </td>
                          );
                        }
                        const lvl = c.termin ? deadlineLevel(c.termin, barvy) : "none";
                        return (
                          <td
                            key={u.sloupec_id}
                            className={`fm-cell fm-todo-lvl fm-lvl-${lvl}${grpStart}${klik}`}
                            title={c.poznamka || undefined}
                            onClick={() => otevriBunku(p, u)}
                          >
                            <span className="fm-cell-status">
                              <span className="fm-pin" />
                              <span className="fm-cell-icon">⏳</span>Nehotovo
                            </span>
                            {spolecne}
                          </td>
                        );
                      });
                    })}
                  </tr>
                );
              })}
              {viditelneProjekty.length === 0 && (
                <tr>
                  <td colSpan={4 + pocetSloupcuMatice} style={{ padding: 40, textAlign: "center", color: "var(--fm-muted)" }}>
                    {projekty.length === 0
                      ? muze_editovat
                        ? "Zatím žádná data. Klikni na „Načíst z Freelo“ nebo přidej projekt ručně."
                        : "Zatím žádná data."
                      : "Všechny projekty jsou skryté."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {editace && (
        <BunkaDialog
          projektNazev={editace.projekt.nazev}
          ukolNazev={editace.ukol.nazev}
          bunka={editace.bunka}
          onSave={ulozEditaci}
          onClose={() => setEditace(null)}
        />
      )}
      {freeloOtevreno && (
        <FreeloDialog bezi={freeloBezi} onVyber={spustFreelo} onClose={() => setFreeloOtevreno(false)} />
      )}
      {pridatProjekt && (
        <PridatDialog
          nadpis="Přidat projekt"
          pole={[
            { klic: "nazev", label: "Název projektu", placeholder: "např. OP-26-099 – Nový klient" },
            { klic: "termin", label: "Termín (nepovinné)", typ: "date" },
          ]}
          onSave={async (v) => {
            await pridejProjekt({ nazev: v.nazev, termin: v.termin || null });
            await nactiZnovu();
            setPridatProjekt(false);
          }}
          onClose={() => setPridatProjekt(false)}
        />
      )}
      {pridatSloupec && (
        <PridatDialog
          nadpis="Přidat sloupec (úkol)"
          pole={[
            { klic: "faze", label: "Fáze / to-do list", placeholder: "např. SOP" },
            { klic: "nazev", label: "Název úkolu", placeholder: "např. podpis SOP" },
          ]}
          onSave={async (v) => {
            await pridejSloupec({ faze: v.faze, nazev: v.nazev });
            await nactiZnovu();
            setPridatSloupec(false);
          }}
          onClose={() => setPridatSloupec(false)}
        />
      )}
    </Layout>
  );
}
