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
// Klíče se drží enumu KATEGORIE_OP na backendu.
export const KATEGORIE_OP = [
  { klic: "ppa", nazev: "PPA", popis: "Greensie zainvestuje FVE a dodává elektřinu." },
  { klic: "prodej", nazev: "Prodej", popis: "Zákazník je vlastníkem zařízení." },
  { klic: "peak_shaving", nazev: "Peak shaving", popis: "Baterie sráží špičky odběru." },
];

export const DRUHY_AKTIVITY = [
  { klic: "poznamka", nazev: "Poznámka", ikona: "📝" },
  { klic: "telefon", nazev: "Telefonát", ikona: "📞" },
  { klic: "email", nazev: "E-mail", ikona: "✉️" },
  { klic: "schuzka", nazev: "Schůzka", ikona: "🤝" },
  { klic: "ukol", nazev: "Úkol", ikona: "✅" },
];

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

/** Názvy kategorií pro výpis v řádku/dlaždici. */
export function nazvyKategorii(klice) {
  return (klice || [])
    .map((k) => KATEGORIE_OP.find((x) => x.klic === k)?.nazev || k)
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
