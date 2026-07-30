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
