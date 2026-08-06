import { barvaProJmeno, iniciraly } from "./Iniciraly";

/**
 * Kolečka lidí, kteří mají otevřený stejný záznam.
 *
 * Sebe záměrně nezobrazujeme — člověk ví, že tam je. Zajímavá je jen odpověď
 * na „dělá na tom teď ještě někdo jiný?“. Barvu i iniciály bere ze stejné
 * funkce jako kanban, aby měl kolega všude stejnou barvu.
 *
 * @param {object} p
 * @param {Array<{uzivatel_id: any, jmeno: string, pole?: string, ja?: boolean}>} p.pritomni
 * @param {(pole: string) => string} [p.popisekPole] z klíče pole udělá čitelný název
 */
const MAX_KOLECEK = 4;
const VELIKOST = 26;

const kolecko = {
  width: VELIKOST,
  height: VELIKOST,
  boxSizing: "border-box",
  borderRadius: "50%",
  border: "2px solid var(--fm-card, #fff)",
  marginLeft: -6,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 11,
  fontWeight: 700,
  lineHeight: 1,
  color: "#fff",
  letterSpacing: 0.2,
  cursor: "default",
  flex: "0 0 auto",
};

export default function Pritomni({ pritomni, popisekPole }) {
  const ostatni = (Array.isArray(pritomni) ? pritomni : []).filter((p) => p && !p.ja);
  if (ostatni.length === 0) return null;

  const videt = ostatni.slice(0, MAX_KOLECEK);
  const skryto = ostatni.length - videt.length;

  function tooltip(p) {
    const jmeno = p.jmeno || "neznámý";
    if (!p.pole) return jmeno;
    const nazev = (popisekPole ? popisekPole(p.pole) : null) || p.pole;
    return `${jmeno} — edituje: ${nazev}`;
  }

  return (
    <span
      style={{ display: "inline-flex", alignItems: "center", paddingLeft: 6 }}
      aria-label={`Otevřeno také u: ${ostatni.map((p) => p.jmeno || "neznámý").join(", ")}`}
    >
      {videt.map((p, i) => (
        <span
          key={p.uzivatel_id ?? `${p.jmeno}-${i}`}
          style={{ ...kolecko, background: barvaProJmeno(p.jmeno), marginLeft: i === 0 ? 0 : -6 }}
          title={tooltip(p)}
        >
          {iniciraly(p.jmeno)}
        </span>
      ))}
      {skryto > 0 && (
        <span
          style={{ ...kolecko, background: "var(--fm-muted)" }}
          title={ostatni
            .slice(MAX_KOLECEK)
            .map((p) => tooltip(p))
            .join("\n")}
        >
          +{skryto}
        </span>
      )}
    </span>
  );
}
