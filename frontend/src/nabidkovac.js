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
