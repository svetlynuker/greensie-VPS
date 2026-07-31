/**
 * Kolečko s iniciálami vlastníka (CRM-44).
 *
 * Na dlaždici kanbanu je jméno navíc dlouhé a ukusuje řádek, ale bez něj není
 * poznat, čí zakázka to je. Iniciály tohle řeší na dvou znacích.
 *
 * Barva se odvozuje z jména, ne z pořadí v seznamu: kolega musí mít stejnou
 * barvu na každé obrazovce a i po tom, co někdo jiný přibude nebo odejde.
 */
const BARVY = [
  "#3f7a5e", "#2f6f9f", "#8a5a9e", "#a4703a", "#4b6cb7",
  "#7a8b3f", "#9e4f5a", "#3f8a86", "#6a5acd", "#9c6b3f",
];

export function barvaProJmeno(jmeno) {
  const text = String(jmeno || "");
  let soucet = 0;
  for (let i = 0; i < text.length; i += 1) soucet = (soucet + text.charCodeAt(i)) % 9973;
  return BARVY[soucet % BARVY.length];
}

export function iniciraly(jmeno) {
  const casti = String(jmeno || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (casti.length === 0) return "?";
  if (casti.length === 1) return casti[0].slice(0, 2).toUpperCase();
  return (casti[0][0] + casti[casti.length - 1][0]).toUpperCase();
}

export default function Iniciraly({ jmeno, velikost = 22, title }) {
  const text = iniciraly(jmeno);
  return (
    <span
      className="crm-iniciraly"
      style={{
        background: barvaProJmeno(jmeno),
        width: velikost,
        height: velikost,
        fontSize: Math.round(velikost * 0.42),
      }}
      title={title || jmeno || "bez vlastníka"}
      aria-label={jmeno || "bez vlastníka"}
    >
      {text}
    </span>
  );
}
