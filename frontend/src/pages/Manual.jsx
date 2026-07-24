import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import Layout from "../components/Layout";
import { nactiMe, nactiManual, logout } from "../api";
import "../styles/manual.css";

// Porovnání bez ohledu na diakritiku a velikost písmen (pro filtr seznamu).
const norm = (s) =>
  (s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

// Odkazy v Markdownu (basename souboru bez .md) → id stránky manuálu.
// Moduly mají stejný název jako id; serverové soubory mají prefix "server-".
const MAPA_ODKAZU = {
  README: "uvod",
  "architektura-prostredi": "server-architektura",
  nasazeni: "server-nasazeni",
  konfigurace: "server-konfigurace",
  "prava-a-skupiny": "server-prava",
};

// Zvýrazní výskyty hledaného výrazu v už vykresleném HTML (bezpečně přes DOM,
// obalí textové uzly do <mark>). Case-insensitive, přeskakuje kód a nadpisy.
function zvyrazni(root, dotaz) {
  const q = dotaz.toLowerCase();
  if (!q) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
  const uzly = [];
  while (walker.nextNode()) {
    const n = walker.currentNode;
    const rodic = n.parentNode?.nodeName;
    if (["SCRIPT", "STYLE", "MARK", "CODE", "PRE"].includes(rodic)) continue;
    if (n.nodeValue.toLowerCase().includes(q)) uzly.push(n);
  }
  uzly.forEach((n) => {
    const text = n.nodeValue;
    const low = text.toLowerCase();
    const frag = document.createDocumentFragment();
    let i = 0;
    let idx;
    while ((idx = low.indexOf(q, i)) !== -1) {
      if (idx > i) frag.appendChild(document.createTextNode(text.slice(i, idx)));
      const m = document.createElement("mark");
      m.textContent = text.slice(idx, idx + q.length);
      frag.appendChild(m);
      i = idx + q.length;
    }
    if (i < text.length) frag.appendChild(document.createTextNode(text.slice(i)));
    n.parentNode.replaceChild(frag, n);
  });
}

export default function Manual() {
  const [uzivatel, setUzivatel] = useState(null);
  const [stranky, setStranky] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [hledani, setHledani] = useState("");
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const teloRef = useRef(null);

  const aktivniId = params.get("stranka");

  function otevri(id) {
    setParams({ stranka: id });
  }

  useEffect(() => {
    Promise.all([nactiMe(), nactiManual()])
      .then(([me, data]) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
        setStranky(data.stranky);
        if (!params.get("stranka") && data.stranky.length) {
          setParams({ stranka: data.stranky[0].id }, { replace: true });
        }
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("uživ") || m.includes("přihl")) {
          logout();
          navigate("/");
        } else {
          setChyba(m);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const aktivni = useMemo(
    () => stranky?.find((s) => s.id === aktivniId) || stranky?.[0] || null,
    [stranky, aktivniId],
  );

  const dotaz = hledani.trim();
  const vysledky = useMemo(() => {
    if (!stranky) return [];
    if (!dotaz) return stranky;
    const q = norm(dotaz);
    return stranky.filter((s) => norm(s.titulek).includes(q) || norm(s.text).includes(q));
  }, [stranky, dotaz]);

  // seskupení výsledků do kategorií (zachová pořadí ze serveru)
  const kategorie = useMemo(() => {
    const out = [];
    vysledky.forEach((s) => {
      let k = out.find((x) => x.nazev === s.kategorie);
      if (!k) {
        k = { nazev: s.kategorie, polozky: [] };
        out.push(k);
      }
      k.polozky.push(s);
    });
    return out;
  }, [vysledky]);

  // vykreslení HTML aktivní stránky + interní odkazy + zvýraznění
  useEffect(() => {
    const el = teloRef.current;
    if (!el || !aktivni) return;
    el.innerHTML = aktivni.html;

    const ids = new Set((stranky || []).map((s) => s.id));
    el.querySelectorAll('a[href$=".md"]').forEach((a) => {
      const base = a.getAttribute("href").split("/").pop().replace(/\.md$/, "");
      const cil = ids.has(base) ? base : MAPA_ODKAZU[base];
      if (cil) {
        a.classList.add("man-vnitrni");
        a.addEventListener("click", (ev) => {
          ev.preventDefault();
          otevri(cil);
        });
      } else {
        a.setAttribute("target", "_blank");
        a.setAttribute("rel", "noopener noreferrer");
      }
    });

    if (dotaz) zvyrazni(el, dotaz);
    const scroller = el.closest(".man-obsah");
    if (scroller) scroller.scrollTop = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aktivni, dotaz, stranky]);

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!stranky) return <Layout uzivatel={uzivatel}>{null}</Layout>;

  return (
    <Layout uzivatel={uzivatel}>
      <div className="man-wrap">
        <aside className="man-sidebar">
          <Link to="/rozcestnik" className="fm-backlink">
            ← Rozcestník
          </Link>
          <div className="man-hledani">
            <input
              type="search"
              placeholder="Hledat v manuálu…"
              value={hledani}
              onChange={(e) => setHledani(e.target.value)}
              autoFocus
            />
            {dotaz && (
              <div className="man-hledani-info">
                {vysledky.length === 0
                  ? "Nic nenalezeno"
                  : `Nalezeno na ${vysledky.length} stránkách`}
              </div>
            )}
          </div>

          <nav className="man-nav">
            {kategorie.map((k) => (
              <div key={k.nazev} className="man-nav-skupina">
                <div className="man-nav-kat">{k.nazev}</div>
                {k.polozky.map((s) => (
                  <button
                    key={s.id}
                    className={"man-nav-item" + (aktivni?.id === s.id ? " aktivni" : "")}
                    onClick={() => otevri(s.id)}
                  >
                    {s.titulek}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        </aside>

        <section className="man-obsah">
          {aktivni ? (
            <article className="man-telo" ref={teloRef} />
          ) : (
            <div className="man-prazdno">Vyber stránku vlevo.</div>
          )}
        </section>
      </div>
    </Layout>
  );
}
