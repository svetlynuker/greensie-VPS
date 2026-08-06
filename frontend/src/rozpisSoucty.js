// Náhled součtů rozpisu položek – JEDINÁ kopie vzorce na straně prohlížeče.
//
// ---- Proč tenhle soubor vůbec je ------------------------------------------
//
// Souhrn rozpisu počítá server (`app/nabidkovac/polozky.py`) a appka ho jinde
// bere hotový – tak sedí s tiskovým výstupem i s fakturou. Jenom dokud OZ píše
// a nemá uloženo, žádný serverový souhrn neexistuje: řádky jsou zatím jen na
// obrazovce. Proto tenhle náhled („po uložení bude bez DPH …“).
//
// Náhled tedy vzorec nutně duplikuje. Duplikát se ale musí chovat ZNAKU
// STEJNĚ jako `polozky.radek_soucty`, jinak by po uložení číslo poskočilo:
//
//   1. sleva se uplatňuje na JEDNOTKOVOU cenu, ne na řádek (u zlomkových
//      množství to jinak dá jiný výsledek jen kvůli pořadí operací),
//   2. na haléře se zaokrouhluje KAŽDÝ ŘÁDEK ZVLÁŠŤ a teprve pak se sčítá –
//      `souhrn()` sčítá už zaokrouhlené `bez_dph`,
//   3. půlené haléře jdou nahoru, od nuly (Decimal ROUND_HALF_UP).
//
// Do 6. 8. 2026 náhled sčítal nezaokrouhlené řádky, takže se od uloženého
// souhrnu lišil o zaokrouhlení každého řádku (u dlouhého rozpisu klidně
// o koruny). Shodu obou stran hlídá test `backend/tests/test_rozpis_nahled.py`,
// který tenhle soubor pouští v Node proti `polozky.radek_soucty`.
//
// Pravda zůstává na serveru: uložený souhrn se pořád zobrazuje z backendu,
// tohle je jen dopředný odhad, dokud je rozpis rozepsaný.

/** Zaokrouhlení na haléře půlkou nahoru (od nuly) – jako Decimal ROUND_HALF_UP.
 *
 * `Math.round` samo nestačí ze dvou důvodů: u záporných částek zaokrouhluje
 * půlku k nule (−0,5 → −0), a float neumí přesně desetiny (2,675 × 100 vyjde
 * 267,49999…, takže by spadlo dolů, zatímco Decimal dá 2,68). Znaménko se
 * proto řeší zvlášť a k číslu se přičte relativní epsilon – ten je o řády
 * menší než haléř, takže posune jen ty hodnoty, které na půlce opravdu leží.
 */
export function naHalere(castka) {
  if (!Number.isFinite(castka)) return 0;
  const znamenko = castka < 0 ? -1 : 1;
  const zvetseno = Math.abs(castka) * 100;
  return (znamenko * Math.round(zvetseno + zvetseno * Number.EPSILON * 4)) / 100;
}

/** Číslo z políčka formuláře: prázdno i nesmysl je nula, desetinná čárka projde.
 *
 * Do polí rozpisu se píše ručně, takže tam běžně je „1,5“ nebo rozepsaná
 * mezera. Backend si `Decimal(str(...))` poradí až s tím, co dorazí přes API –
 * náhled musí to samé zvládnout rovnou nad rozepsaným řádkem.
 */
function cislo(hodnota) {
  if (typeof hodnota === "number") return Number.isFinite(hodnota) ? hodnota : 0;
  const text = String(hodnota ?? "").replace(",", ".").replace(/\s/g, "").trim();
  if (text === "") return 0;
  const n = Number(text);
  return Number.isFinite(n) ? n : 0;
}

/** Částka jednoho řádku bez DPH – zrcadlo `polozky.radek_soucty()["bez_dph"]`. */
export function radekBezDph(mnozstvi, cenaJednotkova, slevaProcent) {
  const mn = cislo(mnozstvi);
  const cena = cislo(cenaJednotkova);
  const sleva = cislo(slevaProcent);
  // Sleva na jednotkovou cenu; zaokrouhluje se až součin, stejně jako v Pythonu.
  return naHalere(mn * (cena * (1 - sleva / 100)));
}

/** Součet rozpisu bez DPH – zrcadlo `polozky.souhrn()["bez_dph"]`.
 *
 * Sčítá už zaokrouhlené řádky (viz bod 2 v hlavičce). Součet se na konci
 * zaokrouhlí ještě jednou, aby se sečetlo pár desetin z float aritmetiky
 * (0,1 + 0,2 = 0,30000000000000004) – na výsledek v haléřích to nesahá.
 */
export function mezisoucetBezDph(radky) {
  const suma = (radky || []).reduce(
    (s, r) => s + radekBezDph(r.mnozstvi, r.cena_jednotkova, r.sleva_procent),
    0
  );
  return naHalere(suma);
}
