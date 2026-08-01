// ============================================================
// Filtry, řazení a definice sloupců pro seznamy i kanbany CRM.
//
// Filtruje a řadí se NA KLIENTU nad už načtenými řádky: seznamy vracejí stovky
// záznamů, takže je to okamžité, funguje to stejně v tabulce i v kanbanu a
// nemusí se psát generátor SQL z uživatelských podmínek (klasický zdroj chyb).
// Uložené filtry drží backend, ale jen jako definici.
//
// Sloupce jsou deklarativní, aby tabulka, filtry i řazení vycházely z jednoho
// zdroje – jinak by se hlavička, filtr a porovnávací funkce rozešly.
// ============================================================

import { isoDen, pondeliTydne, posunDnu } from "./datum";

/** Typy sloupců řídí, jaký filtr se nabídne a jak se porovnává. */
export const TYPY_SLOUPCU = {
  text: "text",
  cislo: "cislo",
  penize: "penize",
  datum: "datum",
  vyber: "vyber", // pevná sada hodnot (stav, typ…)
  seznam: "seznam", // pole hodnot v řádku (kategorie)
  ano_ne: "ano_ne",
};

/** Operátory podle typu sloupce – musí odpovídat `OPERATORY_FILTRU` na backendu. */
export const OPERATORY = {
  text: [
    { klic: "obsahuje", nazev: "obsahuje" },
    { klic: "neobsahuje", nazev: "neobsahuje" },
    { klic: "je", nazev: "je přesně" },
    { klic: "neni", nazev: "není" },
    { klic: "je_prazdne", nazev: "je prázdné", bezHodnoty: true },
    { klic: "neni_prazdne", nazev: "není prázdné", bezHodnoty: true },
  ],
  cislo: [
    { klic: "je", nazev: "=" },
    { klic: "vetsi", nazev: "≥" },
    { klic: "mensi", nazev: "≤" },
    { klic: "mezi", nazev: "mezi", dvojice: true },
    { klic: "je_prazdne", nazev: "není vyplněno", bezHodnoty: true },
    { klic: "neni_prazdne", nazev: "je vyplněno", bezHodnoty: true },
  ],
  datum: [
    // Relativní období je první schválně: je to ta volba, kterou člověk chce
    // v devíti z deseti případů („co mám tenhle měsíc"), a jako jediná
    // nezastará v uloženém filtru (viz OBDOBI níž).
    { klic: "v_obdobi", nazev: "je v období", obdobi: true },
    { klic: "je", nazev: "= den" },
    { klic: "vetsi", nazev: "od" },
    { klic: "mensi", nazev: "do" },
    { klic: "mezi", nazev: "mezi", dvojice: true },
    { klic: "je_prazdne", nazev: "není vyplněno", bezHodnoty: true },
    { klic: "neni_prazdne", nazev: "je vyplněno", bezHodnoty: true },
  ],
  vyber: [
    { klic: "je_jeden_z", nazev: "je jeden z", vicenasobne: true },
    { klic: "neni", nazev: "není" },
  ],
  seznam: [
    { klic: "obsahuje", nazev: "obsahuje" },
    { klic: "neobsahuje", nazev: "neobsahuje" },
    { klic: "je_prazdne", nazev: "je prázdné", bezHodnoty: true },
  ],
  ano_ne: [{ klic: "je", nazev: "je" }],
};

OPERATORY.penize = OPERATORY.cislo;

// ---- relativní datumová období (CRM-25) ----
//
// Proč to vůbec existuje: uložený filtr „od 1. 7. do 31. 7." je za měsíc LEŽ.
// Ukazuje starý měsíc a nikdo si toho nemusí všimnout, protože filtr se tváří,
// že funguje. Relativní období proto v podmínce drží KLÍČ („tento_mesic"), ne
// datum, a rozsah se dopočítává k dnešnímu dni při každém vyhodnocení.
//
// Rozsah je vždy uzavřený interval včetně krajních dnů, v ISO (YYYY-MM-DD),
// aby se dal porovnávat jako text – stejně jako to dělá zbytek modulu.
// `od`/`do` = null znamená „neomezeno na té straně".
export const OBDOBI = [
  { klic: "dnes", nazev: "dnes" },
  { klic: "vcera", nazev: "včera" },
  { klic: "zitra", nazev: "zítra" },
  { klic: "tento_tyden", nazev: "tento týden (po–ne)" },
  { klic: "pristi_tyden", nazev: "příští týden" },
  { klic: "poslednich_7_dni", nazev: "posledních 7 dní" },
  { klic: "poslednich_30_dni", nazev: "posledních 30 dní" },
  { klic: "poslednich_90_dni", nazev: "posledních 90 dní" },
  { klic: "pristich_7_dni", nazev: "příštích 7 dní" },
  { klic: "pristich_30_dni", nazev: "příštích 30 dní" },
  { klic: "tento_mesic", nazev: "tento měsíc" },
  { klic: "minuly_mesic", nazev: "minulý měsíc" },
  { klic: "pristi_mesic", nazev: "příští měsíc" },
  { klic: "tento_rok", nazev: "tento rok" },
  { klic: "minuly_rok", nazev: "minulý rok" },
  { klic: "v_minulosti", nazev: "v minulosti (před dneškem)" },
  { klic: "v_budoucnosti", nazev: "v budoucnosti (po dnešku)" },
];

export const VYCHOZI_OBDOBI = "tento_mesic";

// Datumoví pomocníci jsou v `datum.js` – používá je i kalendář, takže je tu
// nedržíme podruhé (dvě kopie „co je dnes" se dřív nebo později rozejdou).

/**
 * Rozsah období k danému dni: `{ od, do }` v ISO, null = neomezeno.
 * `dnes` je parametr kvůli testovatelnosti (a aby se dnešek nečetl vícekrát).
 */
export function rozsahObdobi(klic, dnes = new Date()) {
  const d = isoDen(dnes);
  const prvniDenMesice = (posunMesicu) =>
    new Date(dnes.getFullYear(), dnes.getMonth() + posunMesicu, 1);
  const posledniDenMesice = (posunMesicu) =>
    new Date(dnes.getFullYear(), dnes.getMonth() + posunMesicu + 1, 0);

  switch (klic) {
    case "dnes":
      return { od: d, do: d };
    case "vcera": {
      const v = isoDen(posunDnu(dnes, -1));
      return { od: v, do: v };
    }
    case "zitra": {
      const z = isoDen(posunDnu(dnes, 1));
      return { od: z, do: z };
    }
    case "tento_tyden": {
      const po = pondeliTydne(dnes);
      return { od: isoDen(po), do: isoDen(posunDnu(po, 6)) };
    }
    case "pristi_tyden": {
      const po = posunDnu(pondeliTydne(dnes), 7);
      return { od: isoDen(po), do: isoDen(posunDnu(po, 6)) };
    }
    // „Posledních N dní" včetně dneška – 7 dní znamená dnes a šest předchozích.
    case "poslednich_7_dni":
      return { od: isoDen(posunDnu(dnes, -6)), do: d };
    case "poslednich_30_dni":
      return { od: isoDen(posunDnu(dnes, -29)), do: d };
    case "poslednich_90_dni":
      return { od: isoDen(posunDnu(dnes, -89)), do: d };
    case "pristich_7_dni":
      return { od: d, do: isoDen(posunDnu(dnes, 6)) };
    case "pristich_30_dni":
      return { od: d, do: isoDen(posunDnu(dnes, 29)) };
    case "tento_mesic":
      return { od: isoDen(prvniDenMesice(0)), do: isoDen(posledniDenMesice(0)) };
    case "minuly_mesic":
      return { od: isoDen(prvniDenMesice(-1)), do: isoDen(posledniDenMesice(-1)) };
    case "pristi_mesic":
      return { od: isoDen(prvniDenMesice(1)), do: isoDen(posledniDenMesice(1)) };
    case "tento_rok":
      return { od: `${dnes.getFullYear()}-01-01`, do: `${dnes.getFullYear()}-12-31` };
    case "minuly_rok":
      return { od: `${dnes.getFullYear() - 1}-01-01`, do: `${dnes.getFullYear() - 1}-12-31` };
    case "v_minulosti":
      return { od: null, do: isoDen(posunDnu(dnes, -1)) };
    case "v_budoucnosti":
      return { od: isoDen(posunDnu(dnes, 1)), do: null };
    default:
      // Neznámý klíč nesmí seznam vyprázdnit – filtr, kterému nikdo nerozumí,
      // radši nefiltruje, než aby tvrdil, že data nejsou.
      return { od: null, do: null };
  }
}

/** Lidský název období do popisu podmínky. */
export function nazevObdobi(klic) {
  return OBDOBI.find((o) => o.klic === klic)?.nazev || klic;
}

// ---- definice sloupců jednotlivých sekcí ----
// `klic` = klíč v řádku z API, `hodnota` volitelně přepočet (např. pole → text).

const S = (klic, nazev, typ = "text", extra = {}) => ({ klic, nazev, typ, ...extra });

export const SLOUPCE_ZAKAZNICI = [
  S("nazev", "Název"),
  S("ico", "IČO"),
  S("adresa_mesto", "Město"),
  S("telefon", "Telefon"),
  S("email", "E-mail"),
  S("vlastnik_jmeno", "Vlastník"),
  S("pocet_pripadu", "Případy", "cislo", { vpravo: true }),
  S("vytvoreno_at", "Vytvořeno", "datum"),
];

export const SLOUPCE_PRIPADY = [
  S("cislo", "Číslo"),
  S("zakaznik_nazev", "Zákazník"),
  S("nazev", "Název"),
  S("kategorie", "Kategorie", "seznam"),
  S("stav_nazev", "Stav", "vyber"),
  S("hodnota_kc", "Hodnota", "penize", { vpravo: true }),
  S("pravdepodobnost", "Pravděpodobnost", "cislo", { vpravo: true }),
  S("predpokladane_uzavreni", "Uzavření", "datum"),
  S("vlastnik_jmeno", "Vlastník"),
  S("raynet_code", "Raynetí číslo"),
];

export const SLOUPCE_NABIDKY = [
  S("cislo", "Číslo"),
  S("typ", "Typ", "vyber"),
  S("zakaznik_nazev", "Zákazník"),
  S("pripad_cislo", "Případ"),
  S("stav_nazev", "Obchodní stav", "vyber"),
  S("spocitana", "Spočítáno", "ano_ne"),
  S("vytvoril_jmeno", "Vytvořil"),
  S("vytvoreno_at", "Vytvořeno", "datum"),
];

export const SLOUPCE_OBJEDNAVKY = [
  S("cislo", "Číslo"),
  S("zakaznik_nazev", "Zákazník"),
  S("nazev", "Název"),
  S("pripad_cislo", "Případ"),
  S("nabidka_cislo", "Nabídka"),
  S("cena_kc", "Cena", "penize", { vpravo: true }),
  S("datum_podpisu", "Podpis", "datum"),
  S("datum_dodani", "Dodání", "datum"),
  S("stav_nazev", "Stav", "vyber"),
  S("ma_projekt", "Projekt", "ano_ne"),
];

export const SLOUPCE_PROJEKTY = [
  S("cislo", "Číslo"),
  S("zakaznik_nazev", "Zákazník"),
  S("nazev", "Název"),
  S("pripad_cislo", "Případ"),
  S("objednavka_cislo", "Objednávka"),
  S("stav_nazev", "Stav", "vyber"),
  S("procent", "Hotovo %", "cislo", { vpravo: true }),
  S("po_terminu", "Po termínu", "cislo", { vpravo: true }),
  S("nejblizsi_termin", "Nejbližší termín", "datum"),
  S("vlastnik_jmeno", "Vlastník"),
];

// Číselník kontaktních osob. „Firma" je tu druhá hned za jménem: bez ní se
// řádek nedá zařadit, protože seznam je napříč všemi zákazníky.
export const SLOUPCE_KONTAKTY = [
  S("jmeno", "Jméno"),
  S("zakaznik_nazev", "Firma"),
  S("funkce", "Funkce"),
  S("telefon", "Telefon"),
  S("email", "E-mail"),
  S("hlavni", "Hlavní kontakt", "ano_ne"),
  S("zakaznik_typ_nazev", "Typ firmy", "vyber"),
  S("zakaznik_mesto", "Město"),
  S("vlastnik_jmeno", "Vlastník firmy"),
  S("posledni_email_at", "Poslední e-mail", "datum"),
  S("pocet_emailu", "E-mailů", "cislo", { vpravo: true }),
  S("vytvoreno_at", "Vytvořeno", "datum"),
];

/** Sloupce podle entity + vlastní (admin definovaná) pole označená „v seznamu". */
export function sloupceEntity(entita, vlastniPole = []) {
  const zaklad =
    {
      zakaznik: SLOUPCE_ZAKAZNICI,
      op: SLOUPCE_PRIPADY,
      nab: SLOUPCE_NABIDKY,
      obj: SLOUPCE_OBJEDNAVKY,
      pro: SLOUPCE_PROJEKTY,
      kontakt: SLOUPCE_KONTAKTY,
    }[entita] || [];
  // Vlastní pole se filtrují jako text nad naformátovanou hodnotou – uložená
  // hodnota může být číslo i datum, ale v řádku je vždy jako `extra_text`.
  const vlastni = (vlastniPole || [])
    .filter((p) => p.v_seznamu)
    .map((p) => ({ klic: `extra:${p.klic}`, nazev: p.nazev, typ: "text", vlastni: true }));
  return [...zaklad, ...vlastni];
}

/** Výchozí řazení: podle čísla záznamu (OP/NAB/OBJ/PRO), nejnovější první. */
export function vychoziRazeni(entita) {
  if (entita === "zakaznik") return [{ pole: "nazev", smer: "asc" }];
  // Lidé ani firmy číslo nemají – abecedně podle jména, jako v telefonu.
  if (entita === "kontakt") return [{ pole: "jmeno", smer: "asc" }];
  return [{ pole: "cislo", smer: "desc" }];
}

// ---- čtení hodnot z řádku ----
export function hodnotaRadku(radek, klic) {
  if (klic.startsWith("extra:")) {
    return (radek.extra_text || {})[klic.slice(6)] ?? null;
  }
  return radek[klic] ?? null;
}

function naText(x) {
  if (x === null || x === undefined) return "";
  if (Array.isArray(x)) return x.join(" ");
  if (typeof x === "boolean") return x ? "ano" : "ne";
  return String(x);
}

function naCislo(x) {
  if (x === null || x === undefined || x === "") return null;
  const n = Number(String(x).replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

/**
 * Přirozené porovnání čísel záznamů: `OP-26-0099` má být před `OP-26-0100`.
 * Prosté porovnání textů to zvládne jen díky nulám na začátku – ale u čísel
 * s příponou (`PRO-26-0301-2`) už ne, takže se porovnává po číselných blocích.
 */
function porovnejPrirozene(a, b) {
  const ta = naText(a);
  const tb = naText(b);
  const re = /(\d+)|(\D+)/g;
  const ča = ta.match(re) || [];
  const čb = tb.match(re) || [];
  for (let i = 0; i < Math.max(ča.length, čb.length); i += 1) {
    const xa = ča[i];
    const xb = čb[i];
    if (xa === undefined) return -1;
    if (xb === undefined) return 1;
    const na = Number(xa);
    const nb = Number(xb);
    if (!Number.isNaN(na) && !Number.isNaN(nb)) {
      if (na !== nb) return na - nb;
    } else {
      const c = xa.localeCompare(xb, "cs");
      if (c !== 0) return c;
    }
  }
  return 0;
}

// ---- vyhodnocení jedné podmínky ----
export function splnujePodminku(radek, podminka, sloupce) {
  const { pole, operator, hodnota } = podminka || {};
  if (!pole || !operator) return true;
  const def = sloupce.find((s) => s.klic === pole);
  const typ = def?.typ || "text";
  const surova = hodnotaRadku(radek, pole);

  const jePrazdna =
    surova === null ||
    surova === undefined ||
    surova === "" ||
    (Array.isArray(surova) && surova.length === 0);

  if (operator === "je_prazdne") return jePrazdna;
  if (operator === "neni_prazdne") return !jePrazdna;

  if (typ === "cislo" || typ === "penize") {
    const c = naCislo(surova);
    if (c === null) return false;
    if (operator === "je") return c === naCislo(hodnota);
    if (operator === "vetsi") return c >= (naCislo(hodnota) ?? -Infinity);
    if (operator === "mensi") return c <= (naCislo(hodnota) ?? Infinity);
    if (operator === "mezi") {
      const [od, do_] = Array.isArray(hodnota) ? hodnota : [null, null];
      return c >= (naCislo(od) ?? -Infinity) && c <= (naCislo(do_) ?? Infinity);
    }
    return true;
  }

  if (typ === "datum") {
    const d = naText(surova).slice(0, 10);
    if (!d) return false;
    if (operator === "v_obdobi") {
      const { od, do: doD } = rozsahObdobi(naText(hodnota) || VYCHOZI_OBDOBI);
      return (!od || d >= od) && (!doD || d <= doD);
    }
    if (operator === "je") return d === naText(hodnota).slice(0, 10);
    if (operator === "vetsi") return d >= naText(hodnota).slice(0, 10);
    if (operator === "mensi") return d <= naText(hodnota).slice(0, 10);
    if (operator === "mezi") {
      const [od, do_] = Array.isArray(hodnota) ? hodnota : ["", ""];
      return (!od || d >= naText(od).slice(0, 10)) && (!do_ || d <= naText(do_).slice(0, 10));
    }
    return true;
  }

  if (typ === "ano_ne") {
    const b = surova === true || naText(surova).toLowerCase() === "ano";
    const chce = hodnota === true || naText(hodnota).toLowerCase() === "ano";
    return b === chce;
  }

  if (typ === "seznam") {
    const pole_hodnot = Array.isArray(surova) ? surova.map((x) => naText(x).toLowerCase()) : [];
    const h = naText(hodnota).toLowerCase();
    if (operator === "obsahuje") return pole_hodnot.some((x) => x.includes(h));
    if (operator === "neobsahuje") return !pole_hodnot.some((x) => x.includes(h));
    return true;
  }

  // text a výběr
  const t = naText(surova).toLowerCase();
  if (operator === "je_jeden_z") {
    const seznam = (Array.isArray(hodnota) ? hodnota : [hodnota]).map((x) =>
      naText(x).toLowerCase()
    );
    return seznam.includes(t);
  }
  const h = naText(hodnota).toLowerCase();
  if (operator === "obsahuje") return t.includes(h);
  if (operator === "neobsahuje") return !t.includes(h);
  if (operator === "je") return t === h;
  if (operator === "neni") return t !== h;
  return true;
}

/**
 * Filtr s podporou NEBO (CRM-26).
 *
 * Model, který uživateli stačí a nepotřebuje závorky: podmínky se stejným
 * číslem `skupina` se spojují přes **NEBO**, skupiny navzájem přes **A**.
 * „Stav je Nabídka nebo Vyjednávání, a zároveň hodnota nad milion" = dvě
 * skupiny. Vyjádří se tím všechno, co jde napsat jako součin součtů — a to
 * pokrývá, co lidé od filtru chtějí, bez editoru se závorkami.
 *
 * Podmínka BEZ `skupina` stojí sama (= vlastní skupina), takže starší uložené
 * filtry i rychlé předvolby (CRM-27) se chovají přesně jako dřív. Proto je
 * klíč osamocené podmínky odvozený od jejího pořadí, ne od `null` — jinak by
 * všechny bezskupinové spadly do jedné a začaly se OR-ovat.
 */
export function aplikujFiltr(radky, podminky, sloupce) {
  const aktivni = (podminky || []).filter((p) => p && p.pole && p.operator);
  if (aktivni.length === 0) return radky;

  const skupiny = new Map();
  aktivni.forEach((p, i) => {
    const klic = p.skupina === null || p.skupina === undefined ? `sam-${i}` : `sk-${p.skupina}`;
    if (!skupiny.has(klic)) skupiny.set(klic, []);
    skupiny.get(klic).push(p);
  });

  const bloky = [...skupiny.values()];
  return radky.filter((r) =>
    bloky.every((blok) => blok.some((p) => splnujePodminku(r, p, sloupce)))
  );
}

/**
 * Přečíslování skupin po smazání nebo přesunu podmínky.
 *
 * UI pracuje se spojkami mezi sousedy („tahle podmínka je s předchozí spojená
 * NEBO"), ale ukládá se číslo skupiny. Tahle funkce z pořadí a spojek udělá
 * čísla — a je jediné místo, kde ta konverze žije, aby se pohled UI a uložený
 * tvar nemohly rozejít.
 *
 * `spojky[i]` platí pro podmínku `i` a říká, jak se váže k předchozí.
 */
export function poskupinuj(podminky, spojky) {
  let cislo = 0;
  return (podminky || []).map((p, i) => {
    if (i > 0 && spojky?.[i] === "nebo") return { ...p, skupina: cislo };
    cislo = i === 0 ? 0 : cislo + 1;
    return { ...p, skupina: cislo };
  });
}

/** Zpětně: z čísel skupin odvodí spojky pro UI (`["a", "nebo", …]`). */
export function spojkyZPodminek(podminky) {
  return (podminky || []).map((p, i) => {
    if (i === 0) return "a";
    const predchozi = podminky[i - 1];
    const stejna =
      p?.skupina !== null &&
      p?.skupina !== undefined &&
      p.skupina === predchozi?.skupina;
    return stejna ? "nebo" : "a";
  });
}

/** Víceúrovňové řazení: první klíč hlavní, další rozhodují při shodě. */
export function aplikujRazeni(radky, razeni, sloupce) {
  const klice = (razeni || []).filter((r) => r && r.pole);
  if (klice.length === 0) return radky;
  const kopie = [...radky];
  kopie.sort((a, b) => {
    for (const { pole, smer } of klice) {
      const def = sloupce.find((s) => s.klic === pole);
      const typ = def?.typ || "text";
      const va = hodnotaRadku(a, pole);
      const vb = hodnotaRadku(b, pole);
      // Prázdné hodnoty vždy na konec, ať se nemíchají mezi vyplněné.
      const pa = va === null || va === undefined || va === "";
      const pb = vb === null || vb === undefined || vb === "";
      if (pa && pb) continue;
      if (pa) return 1;
      if (pb) return -1;

      let c;
      if (typ === "cislo" || typ === "penize") {
        c = (naCislo(va) ?? 0) - (naCislo(vb) ?? 0);
      } else if (typ === "datum") {
        c = naText(va).slice(0, 10).localeCompare(naText(vb).slice(0, 10));
      } else if (typ === "ano_ne") {
        c = (va ? 1 : 0) - (vb ? 1 : 0);
      } else {
        c = porovnejPrirozene(va, vb);
      }
      if (c !== 0) return smer === "desc" ? -c : c;
    }
    return 0;
  });
  return kopie;
}

/** Filtr + řazení v jednom (společné pro tabulku i kanban). */
export function zpracujRadky(radky, { podminky, razeni }, sloupce) {
  return aplikujRazeni(aplikujFiltr(radky || [], podminky, sloupce), razeni, sloupce);
}

/** Hodnoty, které se v datech reálně vyskytují – nabídka pro filtr typu výběr. */
export function moznostiSloupce(radky, klic) {
  const set = new Set();
  for (const r of radky || []) {
    const v = hodnotaRadku(r, klic);
    if (Array.isArray(v)) v.forEach((x) => x && set.add(naText(x)));
    else if (v !== null && v !== undefined && v !== "") set.add(naText(v));
  }
  return [...set].sort((a, b) => a.localeCompare(b, "cs"));
}

/** Krátký lidský popis podmínky (do pilulky uloženého filtru). */
export function popisPodminky(podminka, sloupce) {
  const def = sloupce.find((s) => s.klic === podminka.pole);
  const nazev = def?.nazev || podminka.pole;
  const op = (OPERATORY[def?.typ || "text"] || OPERATORY.text).find(
    (o) => o.klic === podminka.operator
  );
  const opNazev = op?.nazev || podminka.operator;
  if (op?.bezHodnoty) return `${nazev} ${opNazev}`;
  // U období se vypisuje jeho lidský název, ne strojový klíč („tento_mesic").
  if (op?.obdobi) return `${nazev}: ${nazevObdobi(naText(podminka.hodnota))}`;
  const h = Array.isArray(podminka.hodnota)
    ? podminka.hodnota.filter(Boolean).join(" – ")
    : naText(podminka.hodnota);
  return `${nazev} ${opNazev} ${h}`.trim();
}
