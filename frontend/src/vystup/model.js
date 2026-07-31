// Datový model nabídkového výstupu (verze 2) a operace nad ním.
//
// Dokument = seznam pevných A4 stránek. Na stránce leží prvky na
// milimetrových souřadnicích (volné umístění se snapem na mřížku), uvnitř
// kontejneru stojí prvky pod sebou v pořadí, v jakém jsou v `deti` – tam se
// x/y ignoruje a mění se jen pořadí.
//
// Všechny funkce vracejí NOVOU konfiguraci a vstupní nechávají být (React
// pozná změnu podle reference). Zrcadlí schémata v `backend/app/nabidkovac/
// schemas.py` – když se mění tady, musí se změnit i tam.

// ---- Rozměry papíru (mm) ----------------------------------------------------
export const A4_SIRKA = 210;
export const A4_VYSKA = 297;

// Okraje sazby. Prvek smí jít i mimo ně (barevný pruh přes celou šířku), jsou
// to vodítka a výchozí pozice, ne zeď.
export const OKRAJ_BOK = 16;
export const OBSAH_SIRKA = A4_SIRKA - 2 * OKRAJ_BOK; // 178
export const OBSAH_OD = 34; // pod pruhem se značkou
export const OBSAH_DO = 266; // nad kontaktním zápatím

// Krok přichytávání při tažení. Držet i v `tazeni.js`.
export const MRIZKA = 5;

// Nejmenší rozumný prvek – menší se nedá chytit myší.
export const MIN_SIRKA = 8;
export const MIN_VYSKA = 5;

export const MAX_STRANEK = 50;

// ---- Druhy prvků ------------------------------------------------------------
export const DRUHY = {
  kontejner: { nazev: "Kontejner", popis: "Rámeček, do kterého se skládají prvky" },
  text: { nazev: "Text", popis: "Odstavec, píše se přímo na papíře" },
  udaj: { nazev: "Údaj", popis: "Dlaždice s hodnotou z výpočtu" },
  graf: { nazev: "Graf", popis: "Výroba / měsíční špičky" },
  tabulka: { nazev: "Tabulka", popis: "Vývoj po letech" },
  obrazek: { nazev: "Obrázek", popis: "Nahraná fotka nebo schéma" },
  cara: { nazev: "Čára", popis: "Vodorovný oddělovač" },
  obdelnik: { nazev: "Obdélník", popis: "Barevná plocha jako podklad" },
  cislo_stranky: { nazev: "Číslo stránky", popis: "Doplní se při tisku" },
};

// Prvky, které nedávají smysl uvnitř kontejneru (kontejner do kontejneru
// nepatří a hlídá to i backend).
export const DO_KONTEJNERU_NELZE = new Set(["kontejner"]);

// Výchozí rozměry po přetažení z palety (mm).
const VYCHOZI = {
  kontejner: { sirka: OBSAH_SIRKA, vyska: 40, auto_vyska: true },
  text: { sirka: OBSAH_SIRKA, vyska: 16, auto_vyska: true },
  udaj: { sirka: 56, vyska: 24, auto_vyska: false },
  graf: { sirka: OBSAH_SIRKA, vyska: 80, auto_vyska: false },
  tabulka: { sirka: OBSAH_SIRKA, vyska: 60, auto_vyska: true },
  obrazek: { sirka: 80, vyska: 60, auto_vyska: false },
  cara: { sirka: OBSAH_SIRKA, vyska: 1, auto_vyska: false },
  obdelnik: { sirka: 80, vyska: 30, auto_vyska: false },
  cislo_stranky: { sirka: 30, vyska: 8, auto_vyska: false },
};

// Výchozí styl podle druhu – dlaždice má podklad, obdélník barvu, čára linku.
const VYCHOZI_STYL = {
  udaj: { pozadi: "#f4f6f5", zaobleni: 2, odsazeni: 3 },
  obdelnik: { pozadi: "#e8f3ec", zaobleni: 2 },
  cara: { barva_ramecku: "#c9d3ce", sirka_ramecku: 0.4, odsazeni: 0 },
  kontejner: { odsazeni: 4, mezera: 4 },
};

export function prazdnyStyl(druh = "") {
  return {
    pozadi: "",
    barva_ramecku: "",
    sirka_ramecku: 0,
    zaobleni: 0,
    odsazeni: 4,
    mezera: 4,
    pruhlednost: 1,
    sloupce: 1,
    ...(VYCHOZI_STYL[druh] || {}),
  };
}

let citac = 0;

/** Jedinečné id prvku. Náhoda kvůli slučování šablon, čítač kvůli tomu, aby
 *  se dva prvky vytvořené ve stejné milisekundě nepotkaly. */
export function noveId(druh = "p") {
  citac += 1;
  return `${druh}-${citac}-${Math.random().toString(36).slice(2, 7)}`;
}

export function novyPrvek(druh, vlastnosti = {}) {
  const rozmery = VYCHOZI[druh] || { sirka: 60, vyska: 20, auto_vyska: true };
  return {
    id: noveId(druh),
    druh,
    viditelny: true,
    x: OKRAJ_BOK,
    y: OBSAH_OD,
    ...rozmery,
    z: 0,
    zamceno: false,
    styl: prazdnyStyl(druh),
    html: "",
    klic: "",
    pole: [],
    obrazek: "",
    popis: "",
    deti: [],
    ...vlastnosti,
  };
}

export function novaStranka() {
  return { id: noveId("s"), prvky: [] };
}

export function prazdnaKonfigurace() {
  return {
    verze: 2,
    stranky: [novaStranka()],
    hlavicka: { zobrazit: true, text: "" },
    zapati: { zobrazit: true, text: "" },
    vodoznak: { zobrazit: true, pruhlednost: 0.07 },
  };
}

// ---- Čtení ------------------------------------------------------------------

/** Projde všechny prvky (i děti) a zavolá `fn(prvek, stranka, rodic)`. */
export function projdiPrvky(konfigurace, fn) {
  for (const stranka of konfigurace?.stranky || []) {
    for (const prvek of stranka.prvky || []) {
      fn(prvek, stranka, null);
      for (const dite of prvek.deti || []) fn(dite, stranka, prvek);
    }
  }
}

/** Najde prvek podle id. Vrací `{ prvek, stranka, rodic, index }` nebo null. */
export function najdi(konfigurace, id) {
  if (!id) return null;
  for (const stranka of konfigurace?.stranky || []) {
    const i = (stranka.prvky || []).findIndex((p) => p.id === id);
    if (i >= 0) return { prvek: stranka.prvky[i], stranka, rodic: null, index: i };
    for (const prvek of stranka.prvky || []) {
      const j = (prvek.deti || []).findIndex((d) => d.id === id);
      if (j >= 0) return { prvek: prvek.deti[j], stranka, rodic: prvek, index: j };
    }
  }
  return null;
}

export function indexStranky(konfigurace, strankaId) {
  return (konfigurace?.stranky || []).findIndex((s) => s.id === strankaId);
}

/** Nejvyšší vrstva na stránce – nový prvek jde navrch. */
function nejvyssiZ(stranka) {
  return (stranka.prvky || []).reduce((m, p) => Math.max(m, p.z || 0), 0);
}

// ---- Zápis: prvky -----------------------------------------------------------

function mapujStranky(konfigurace, fn) {
  return { ...konfigurace, stranky: (konfigurace.stranky || []).map(fn) };
}

/** Změní vlastnosti prvku (na stránce i v kontejneru). */
export function upravPrvek(konfigurace, id, zmena) {
  return mapujStranky(konfigurace, (s) => ({
    ...s,
    prvky: (s.prvky || []).map((p) => {
      if (p.id === id) return { ...p, ...zmena };
      if ((p.deti || []).some((d) => d.id === id)) {
        return { ...p, deti: p.deti.map((d) => (d.id === id ? { ...d, ...zmena } : d)) };
      }
      return p;
    }),
  }));
}

/** Změní styl prvku (mělké sloučení, ať se nemusí posílat celý objekt). */
export function upravStyl(konfigurace, id, zmenaStylu) {
  const nalez = najdi(konfigurace, id);
  if (!nalez) return konfigurace;
  return upravPrvek(konfigurace, id, {
    styl: { ...prazdnyStyl(nalez.prvek.druh), ...nalez.prvek.styl, ...zmenaStylu },
  });
}

/** Vyjme prvek odkudkoli. Vrací `[konfigurace bez prvku, vyjmutý prvek]`. */
export function vyjmi(konfigurace, id) {
  const nalez = najdi(konfigurace, id);
  if (!nalez) return [konfigurace, null];
  const bez = mapujStranky(konfigurace, (s) => ({
    ...s,
    prvky: (s.prvky || [])
      .filter((p) => p.id !== id)
      .map((p) =>
        (p.deti || []).some((d) => d.id === id)
          ? { ...p, deti: p.deti.filter((d) => d.id !== id) }
          : p
      ),
  }));
  return [bez, nalez.prvek];
}

export function smazPrvek(konfigurace, id) {
  return vyjmi(konfigurace, id)[0];
}

/** Položí prvek přímo na stránku na dané souřadnice. */
export function polozNaStranku(konfigurace, strankaId, prvek, x, y) {
  return mapujStranky(konfigurace, (s) => {
    if (s.id !== strankaId) return s;
    const novy = {
      ...prvek,
      x: zaokrouhli(x),
      y: zaokrouhli(y),
      z: nejvyssiZ(s) + 1,
    };
    return { ...s, prvky: [...(s.prvky || []), novy] };
  });
}

/** Vloží prvek do kontejneru na pozici `index` (na konec, když je mimo). */
export function vlozDoKontejneru(konfigurace, kontejnerId, prvek, index) {
  return mapujStranky(konfigurace, (s) => ({
    ...s,
    prvky: (s.prvky || []).map((p) => {
      if (p.id !== kontejnerId) return p;
      const deti = [...(p.deti || [])];
      const kam = Math.max(0, Math.min(index ?? deti.length, deti.length));
      // Uvnitř kontejneru se souřadnice neuplatní, ale ať v datech nezůstane
      // pozice z papíru a prvek se po vytažení ven neobjevil na divném místě.
      deti.splice(kam, 0, { ...prvek, x: 0, y: 0 });
      return { ...p, deti };
    }),
  }));
}

/**
 * Přesune prvek na nové místo. `cil` je jedno z:
 *   { typ: "stranka", strankaId, x, y }
 *   { typ: "kontejner", kontejnerId, index }
 * Přesun do vlastního potomka ani sám do sebe nedává smysl a vrátí původní
 * konfiguraci beze změny.
 */
export function presun(konfigurace, id, cil) {
  if (!cil) return konfigurace;
  if (cil.typ === "kontejner" && cil.kontejnerId === id) return konfigurace;
  const nalez = najdi(konfigurace, id);
  if (!nalez) return konfigurace;
  if (cil.typ === "kontejner" && DO_KONTEJNERU_NELZE.has(nalez.prvek.druh)) {
    return konfigurace;
  }

  // Přeuspořádání uvnitř téhož kontejneru: index se počítá v seznamu VČETNĚ
  // taženého prvku, takže po vyjmutí je potřeba korekce – jinak prvek tažený
  // dopředu skončí o místo dál, než kam ho uživatel pustil.
  let index = cil.index;
  if (
    cil.typ === "kontejner" &&
    nalez.rodic?.id === cil.kontejnerId &&
    typeof index === "number" &&
    nalez.index < index
  ) {
    index -= 1;
  }

  const [bez, prvek] = vyjmi(konfigurace, id);
  if (!prvek) return konfigurace;
  if (cil.typ === "kontejner") {
    return vlozDoKontejneru(bez, cil.kontejnerId, prvek, index);
  }
  return polozNaStranku(bez, cil.strankaId, prvek, cil.x, cil.y);
}

/** Kopie prvku (i s dětmi) s novými id – pro Ctrl+D. */
export function kopiePrvku(prvek, posun = 5) {
  return {
    ...prvek,
    id: noveId(prvek.druh),
    x: zaokrouhli((prvek.x || 0) + posun),
    y: zaokrouhli((prvek.y || 0) + posun),
    deti: (prvek.deti || []).map((d) => ({ ...d, id: noveId(d.druh) })),
  };
}

export function duplikujPrvek(konfigurace, id) {
  const nalez = najdi(konfigurace, id);
  if (!nalez) return [konfigurace, null];
  const kopie = kopiePrvku(nalez.prvek);
  if (nalez.rodic) {
    return [
      vlozDoKontejneru(konfigurace, nalez.rodic.id, kopie, nalez.index + 1),
      kopie.id,
    ];
  }
  return [polozNaStranku(konfigurace, nalez.stranka.id, kopie, kopie.x, kopie.y), kopie.id];
}

// ---- Vrstvy -----------------------------------------------------------------

/** Posune prvek ve vrstvách. `smer`: 1 dopředu, -1 dozadu, Infinity úplně nahoru. */
export function zmenVrstvu(konfigurace, id, smer) {
  const nalez = najdi(konfigurace, id);
  if (!nalez || nalez.rodic) return konfigurace; // v kontejneru vrstvy neřešíme
  const stranka = nalez.stranka;
  const serazene = [...stranka.prvky].sort((a, b) => (a.z || 0) - (b.z || 0));
  const i = serazene.findIndex((p) => p.id === id);
  if (i < 0) return konfigurace;
  let j;
  if (smer === Infinity) j = serazene.length - 1;
  else if (smer === -Infinity) j = 0;
  else j = Math.max(0, Math.min(serazene.length - 1, i + smer));
  if (i === j) return konfigurace;
  const [p] = serazene.splice(i, 1);
  serazene.splice(j, 0, p);
  // Vrstvy přečíslujeme od nuly – držíme je husté, ať nerostou donekonečna.
  const noveZ = Object.fromEntries(serazene.map((x, k) => [x.id, k]));
  return mapujStranky(konfigurace, (s) =>
    s.id !== stranka.id
      ? s
      : { ...s, prvky: s.prvky.map((x) => ({ ...x, z: noveZ[x.id] ?? x.z })) }
  );
}

// ---- Stránky ----------------------------------------------------------------

export function pridejStranku(konfigurace, zaIndexem) {
  if ((konfigurace.stranky || []).length >= MAX_STRANEK) return konfigurace;
  const stranky = [...konfigurace.stranky];
  const kam = zaIndexem === undefined ? stranky.length : zaIndexem + 1;
  stranky.splice(kam, 0, novaStranka());
  return { ...konfigurace, stranky };
}

export function smazStranku(konfigurace, strankaId) {
  const stranky = (konfigurace.stranky || []).filter((s) => s.id !== strankaId);
  // Dokument bez stránky nedává smysl – poslední se nemaže, jen vyprázdní.
  if (!stranky.length) return { ...konfigurace, stranky: [novaStranka()] };
  return { ...konfigurace, stranky };
}

export function duplikujStranku(konfigurace, strankaId) {
  const i = indexStranky(konfigurace, strankaId);
  if (i < 0 || (konfigurace.stranky || []).length >= MAX_STRANEK) return konfigurace;
  const zdroj = konfigurace.stranky[i];
  const kopie = {
    id: noveId("s"),
    prvky: zdroj.prvky.map((p) => kopiePrvku(p, 0)),
  };
  const stranky = [...konfigurace.stranky];
  stranky.splice(i + 1, 0, kopie);
  return { ...konfigurace, stranky };
}

export function presunStranku(konfigurace, strankaId, smer) {
  const i = indexStranky(konfigurace, strankaId);
  const j = i + smer;
  if (i < 0 || j < 0 || j >= konfigurace.stranky.length) return konfigurace;
  const stranky = [...konfigurace.stranky];
  [stranky[i], stranky[j]] = [stranky[j], stranky[i]];
  return { ...konfigurace, stranky };
}

/** Přesune prvek na sousední stránku – řešení přetečení jedním kliknutím. */
export function presunNaStranku(konfigurace, id, smer) {
  const nalez = najdi(konfigurace, id);
  if (!nalez) return konfigurace;
  const korenId = nalez.rodic ? nalez.rodic.id : id;
  const koren = nalez.rodic || nalez.prvek;
  const i = indexStranky(konfigurace, nalez.stranka.id);
  let cilova = konfigurace.stranky[i + smer];
  let konfigurace2 = konfigurace;
  if (!cilova) {
    if (smer < 0) return konfigurace;
    konfigurace2 = pridejStranku(konfigurace, i);
    cilova = konfigurace2.stranky[i + 1];
  }
  const [bez, prvek] = vyjmi(konfigurace2, korenId);
  if (!prvek) return konfigurace;
  // Na nové stránce začne nahoře v sazbě, ať není hned zase mimo.
  return polozNaStranku(bez, cilova.id, prvek, koren.x, OBSAH_OD);
}

// ---- Geometrie --------------------------------------------------------------

export function zaokrouhli(mm) {
  return Math.round((Number(mm) || 0) * 10) / 10;
}

export function naMrizku(mm, krok = MRIZKA) {
  if (!krok) return zaokrouhli(mm);
  return zaokrouhli(Math.round(mm / krok) * krok);
}

/** Ořízne prvek tak, aby nezmizel úplně mimo papír (kus přesahu se toleruje). */
export function omezNaPapir(x, y, sirka, vyska) {
  return {
    x: zaokrouhli(Math.max(-sirka + 10, Math.min(x, A4_SIRKA - 10))),
    y: zaokrouhli(Math.max(-vyska + 5, Math.min(y, A4_VYSKA - 5))),
  };
}

/** Přetéká prvek přes spodní hranu sazby? Podklad pro varování v editoru. */
export function pretekaDolu(prvek) {
  return (prvek.y || 0) + (prvek.vyska || 0) > OBSAH_DO + 0.5;
}

export function mimoPapir(prvek) {
  return (
    (prvek.x || 0) < -0.5 ||
    (prvek.y || 0) < -0.5 ||
    (prvek.x || 0) + (prvek.sirka || 0) > A4_SIRKA + 0.5 ||
    (prvek.y || 0) + (prvek.vyska || 0) > A4_VYSKA + 0.5
  );
}

/** Seznam problémů dokumentu pro horní lištu. */
export function zkontroluj(konfigurace) {
  const problemy = [];
  (konfigurace?.stranky || []).forEach((stranka, i) => {
    for (const prvek of stranka.prvky || []) {
      if (!prvek.viditelny) continue;
      if (pretekaDolu(prvek) || mimoPapir(prvek)) {
        problemy.push({
          strankaId: stranka.id,
          cisloStranky: i + 1,
          prvekId: prvek.id,
          druh: prvek.druh,
          typ: mimoPapir(prvek) ? "mimo" : "pretece",
        });
      }
    }
  });
  return problemy;
}
