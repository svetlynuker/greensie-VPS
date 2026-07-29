// Sdílené konstanty/pomocníky Nabídkovače (mimo komponenty kvůli HMR).

// Tři produktové linie (kap. 1 SPEC). `klic` = typ nabídky na backendu.
export const PODSEKCE = [
  {
    klic: "ppa",
    nazev: "PPA",
    popis:
      "Greensie postaví a zainvestuje FVE na střeše zákazníka a dodává mu z ní elektřinu levněji než trh. Nástroj spočítá optimální velikost elektrárny, cenu dodávky a min. délku kontraktu.",
  },
  {
    klic: "prodej",
    nazev: "Prodej",
    popis:
      "Zákazník je vlastníkem zařízení. Podle křivky spotřeby (nebo zadaného výkonu) systém navrhne technologii z katalogu a vrátí prodejní cenovou nabídku.",
  },
  {
    klic: "peak_shaving",
    nazev: "Peak shaving",
    popis:
      "Návrh baterie, která ořezává špičky odběru a šetří za rezervovanou kapacitu/výkon. Vstupem je soubor s 15minutovými maximy; z katalogu se vybere nejvhodnější baterie.",
  },
];

// Popisky stavů nabídky (drží se enumu STAVY_NABIDKY na backendu).
export const STAV_NABIDKY = {
  koncept: "Koncept",
  data_nahrana: "Data nahrána",
  zkontrolovano_oz: "Zkontrolováno OZ",
  spocitano: "Spočítáno",
  hotovo: "Hotovo",
};

export function fmtDatum(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
}

// Mřížka papíru: 12 sloupců. Prvek si nese `sirka` (kolik sloupců zabere) a
// prvky se skládají za sebou do řádků – co se nevejde, jde na další řádek.
export const SLOUPCU = 12;

export function sirkaPolozky(polozka) {
  const s = Number(polozka?.sirka);
  if (!Number.isFinite(s)) return SLOUPCU; // starší nabídky šířku nemají
  return Math.min(SLOUPCU, Math.max(1, Math.round(s)));
}

/**
 * Rozdělí prvky do řádků po `SLOUPCU` sloupcích. Zlom stránky stojí vždy sám.
 * Vrací [{ polozky, sirkaCelkem }].
 */
export function doRadku(polozky) {
  const radky = [];
  let radek = [];
  let suma = 0;
  const uzavri = () => {
    if (radek.length) radky.push({ polozky: radek, sirkaCelkem: suma });
    radek = [];
    suma = 0;
  };
  for (const p of polozky) {
    if (p.druh === "zlom") {
      uzavri();
      radky.push({ polozky: [p], sirkaCelkem: SLOUPCU });
      continue;
    }
    const s = sirkaPolozky(p);
    if (suma + s > SLOUPCU) uzavri();
    radek.push(p);
    suma += s;
  }
  uzavri();
  return radky;
}

/**
 * Vloží nový prvek na `index` v seznamu prvků nabídky. Vrací nový seznam.
 */
export function vlozPolozku(bloky, polozka, index) {
  const nove = [...bloky];
  nove.splice(Math.max(0, Math.min(index, nove.length)), 0, polozka);
  return nove;
}

/**
 * Přesune prvek `id` před pozici `index` (číslovanou v původním seznamu).
 * Po vyjmutí se indexy za odebraným prvkem posunou o jeden dolů – proto ta
 * korekce, jinak by prvek při tažení dopředu skončil o místo dál.
 */
export function presunPolozku(bloky, id, index) {
  const odkud = bloky.findIndex((b) => b.id === id);
  if (odkud < 0) return bloky;
  const nove = [...bloky];
  const [p] = nove.splice(odkud, 1);
  nove.splice(odkud < index ? index - 1 : index, 0, p);
  return nove;
}
