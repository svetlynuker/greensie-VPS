// Datumoví pomocníci — jedno místo pro appku.
//
// Mimo komponenty schválně: kdyby žily v souboru s komponentou, rozbily by
// Fast Refresh (soubor smí exportovat jen komponenty) a používá je jak
// kalendář, tak vyhodnocení filtrů.
//
// PRAVIDLO, které je tu podstatné: dny se počítají v LOKÁLNÍM čase, nikdy ne
// přes `toISOString()`. Ten převádí na UTC, takže by v našem pásmu každý večer
// po druhé hodině hlásil „dnes" jako předchozí den.

/** Datum → „2026-08-03" v lokálním čase. */
export function isoDen(d) {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const den = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${den}`;
}

/** Pondělí týdne, do kterého datum padá (týden v ČR začíná pondělím). */
export function pondeliTydne(d) {
  const k = new Date(d);
  k.setDate(k.getDate() - ((k.getDay() + 6) % 7));
  k.setHours(0, 0, 0, 0);
  return k;
}

/** Datum posunuté o `dni` (kladně i záporně). Původní se nemění. */
export function posunDnu(d, dni) {
  const k = new Date(d);
  k.setDate(k.getDate() + dni);
  return k;
}

export const MESICE = [
  "Leden",
  "Únor",
  "Březen",
  "Duben",
  "Květen",
  "Červen",
  "Červenec",
  "Srpen",
  "Září",
  "Říjen",
  "Listopad",
  "Prosinec",
];

export function nazevMesice(index) {
  return MESICE[index] || "";
}

/**
 * ISO číslo týdne (1–53) — to, které se v ČR běžně používá („32. týden").
 *
 * Pravidlo ISO 8601: týden patří tomu roku, do kterého padá jeho **čtvrtek**.
 * Proto se nejdřív skočí na čtvrtek daného týdne a až od něj se počítá — prosté
 * dělení dnů od 1. ledna by u přelomu roku dávalo špatná čísla (např. 1. 1.
 * 2027 patří do 53. týdne roku 2026).
 */
export function cisloTydne(datum) {
  const d = new Date(datum);
  d.setHours(0, 0, 0, 0);
  // Posun na čtvrtek téhož ISO týdne (pondělí = 0 → +3).
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7) + 3);
  const prvniCtvrtek = new Date(d.getFullYear(), 0, 4);
  prvniCtvrtek.setDate(prvniCtvrtek.getDate() - ((prvniCtvrtek.getDay() + 6) % 7) + 3);
  return 1 + Math.round((d - prvniCtvrtek) / (7 * 86400000));
}
