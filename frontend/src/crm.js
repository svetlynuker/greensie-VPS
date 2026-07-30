// Sdílené konstanty a pomocníky CRM (mimo komponenty kvůli HMR).

// Dva pohledy sekce Zákazníci. Jeden datový záznam, `typ` rozhoduje, kde je –
// konverze leadu na klienta proto nemaže historii ani vazby.
export const POHLEDY_ZAKAZNIKU = [
  {
    klic: "lead",
    nazev: "Leady",
    popis: "Firmy, se kterými se teprve baví obchod. Z leadu se stane klient první výhrou.",
  },
  {
    klic: "klient",
    nazev: "Klienti",
    popis: "Firmy, se kterými už reálně obchodujeme. Odtud vedou obchodní případy.",
  },
];

// Kategorie obchodního případu = do kterého výpočtu nabídkovače případ míří.
//
// POZOR: kategorie tady ZÁMĚRNĚ nejsou. Od 30. 7. 2026 (CRM-03) je to
// konfigurovatelný seznam v tabulce `crm_kategorie` a vedení si ho spravuje
// v nastavení pipeline. Načítá se přes `crmKategorie()` z api.js, stejně jako
// stavy kanbanu. Kdyby se sem konstanta vrátila, appka by měla dvě pravdy
// a nová kategorie by se v UI neobjevila.

// Druhy aktivit. `barva` je VÝCHOZÍ barva v kalendáři — každý uživatel si ji
// může přepsat v Nastavení (klíč `kalendar_barvy`, viz `barvyAktivit.js`).
// Hodnoty jsou tokeny appky, ne hex, aby fungovaly ve světlém i tmavém režimu.
// Pořadí se drží předlohy kalendáře (Úkol, Schůzka, Událost, Telefonát, Dopis);
// e-mail a poznámka jsou navíc — poznámka je zápis do historie bez plánování
// a v kalendáři se nekreslí.
// `ikona` je klíč do komponenty Ikona, `znak` emoji pro drobné výpisy.
export const DRUHY_AKTIVITY = [
  { klic: "ukol", nazev: "Úkol", ikona: "ukol", znak: "☑", barva: "#f3b98f" },
  { klic: "schuzka", nazev: "Schůzka", ikona: "schuzka", znak: "☕", barva: "#a8d8b9" },
  { klic: "udalost", nazev: "Událost", ikona: "kalendar", znak: "📅", barva: "#f7c08a" },
  { klic: "telefon", nazev: "Telefonát", ikona: "telefon", znak: "📞", barva: "#f5b8c1" },
  { klic: "dopis", nazev: "Dopis", ikona: "dopis", znak: "✉", barva: "#c9c2ea" },
  { klic: "email", nazev: "E-mail", ikona: "dopis", znak: "✉️", barva: "#a9cdf0" },
  { klic: "poznamka", nazev: "Poznámka", ikona: "poznamka", znak: "📝", barva: "#d3d9de" },
];

// Frekvence opakování aktivity (zadání Dana). „Vlastní" se doplní číslem =
// počet dní mezi opakováními, takže pokryje i „každých 14 dní".
export const FREKVENCE_OPAKOVANI = [
  { klic: "denne", nazev: "Každý den" },
  { klic: "pracovni_dny", nazev: "Každý pracovní den" },
  { klic: "tydne", nazev: "Každý týden" },
  { klic: "mesicne", nazev: "Každý měsíc" },
  { klic: "vlastni", nazev: "Vlastní (po N dnech)" },
];

// Priorita z předlohy. `znak` je to, co se ukazuje na dlaždici a v přepínači.
export const PRIORITY_AKTIVITY = [
  { klic: "nizka", nazev: "Nízká", znak: "⌄" },
  { klic: "stredni", nazev: "Střední", znak: "–" },
  { klic: "vysoka", nazev: "Vysoká", znak: "!" },
];

// Stav aktivity: naplánováno → realizováno / nekonalo se. Nahradil dřívější
// zaškrtávátko „hotovo", které neumělo odlišit schůzku, co proběhla, od
// schůzky, kterou zákazník zrušil.
export const STAVY_AKTIVITY = [
  { klic: "naplanovano", nazev: "Naplánováno", znacka: "info" },
  { klic: "realizovano", nazev: "Realizováno", znacka: "ok" },
  { klic: "nekonalo_se", nazev: "Nekonalo se", znacka: "crit" },
];

export function nazevStavuAktivity(klic) {
  return STAVY_AKTIVITY.find((s) => s.klic === klic)?.nazev || klic;
}

/** Je aktivita ještě čekající? (jediné místo, které to rozhoduje) */
export function jeNaplanovana(a) {
  return (a?.stav || "naplanovano") === "naplanovano";
}

/** „9:00–10:00" pro dlaždici v kalendáři; u celodenní vrací prázdno. */
export function fmtCas(zacatek, delkaMin) {
  if (!zacatek) return "";
  const d = new Date(zacatek);
  if (Number.isNaN(d.getTime())) return "";
  const hm = (x) => `${x.getHours()}:${String(x.getMinutes()).padStart(2, "0")}`;
  if (!delkaMin) return hm(d);
  return `${hm(d)}–${hm(new Date(d.getTime() + delkaMin * 60000))}`;
}

// Krátký seznam důvodů prohry. Volný text jde taky – ale nabídnutá volba
// zajistí, že se dá aspoň něco spočítat (proto je „Jiný" až poslední).
export const DUVODY_PROHRY = [
  "Cena",
  "Konkurence",
  "Zákazník odložil investici",
  "Technicky neproveditelné",
  "Nedostupné podklady",
  "Bez reakce zákazníka",
  "Jiný",
];

export function fmtDatum(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "";
}

/** Peníze v Kč bez desetin – tabulky i kanban mají být čitelné na první pohled. */
export function fmtKc(x) {
  if (x === null || x === undefined || x === "") return "—";
  const n = Number(x);
  if (!Number.isFinite(n)) return "—";
  return `${n.toLocaleString("cs-CZ", { maximumFractionDigits: 0 })} Kč`;
}

/** Zkrácený zápis větších částek do dlaždice kanbanu (1,2 mil. / 340 tis.). */
export function fmtKcKratce(x) {
  const n = Number(x);
  if (!Number.isFinite(n) || n === 0) return "—";
  if (Math.abs(n) >= 1_000_000) {
    return `${(n / 1_000_000).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} mil. Kč`;
  }
  if (Math.abs(n) >= 10_000) {
    return `${Math.round(n / 1000).toLocaleString("cs-CZ")} tis. Kč`;
  }
  return fmtKc(n);
}

/** Názvy kategorií pro výpis v řádku/dlaždici.
 *
 * `kategorie` je seznam z `crmKategorie()`. Když ho volající nemá (ještě se
 * načítá), vypíše se strojový klíč – lepší než prázdno, protože „peak_shaving"
 * je pořád čitelnější než nic.
 */
export function nazvyKategorii(klice, kategorie) {
  return (klice || [])
    .map((k) => (kategorie || []).find((x) => x.klic === k)?.nazev || k)
    .join(" + ");
}

/** Barva stavu → CSS třída (tokeny appky, ne hex, kvůli tmavému režimu). */
export function tridaBarvy(barva) {
  const povolene = ["ok", "warn", "crit", "info"];
  return povolene.includes(barva) ? `crm-barva-${barva}` : "crm-barva-info";
}

/** Je termín po datu? (zvýraznění nesplněných úkolů) */
export function jePoTerminu(termin) {
  if (!termin) return false;
  const d = new Date(`${String(termin).slice(0, 10)}T23:59:59`);
  return d.getTime() < Date.now();
}
