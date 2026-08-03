// Přepočty času a pixelů pro týdenní mřížku kalendáře.
//
// Mimo komponentu schválně: je to čistá matematika, na které stojí pozicování
// dlaždic i tažení, a chce být testovatelná bez prohlížeče. Kdyby žila
// v komponentě, jediný způsob ověření by byl „kliknout a koukat".
//
// ---- Proč to není jen `minuta * konstanta` --------------------------------
// Den se nekreslí jedním měřítkem (podle předlohy kalendáře): noc a večer jsou
// zúžené pásy, pracovní část běží po hodinách. Přepočet proto musí umět tři
// pásma a `yZMinut` s `minutyZY` musí být přesné inverze — jinak by dlaždice
// po přetažení skočila o pár minut jinam, než kam ji člověk pustil.
//
// ---- Proč je geometrie funkce, a ne konstanty -----------------------------
// Zúžený pás je kompromis: pracovní den se vejde na obrazovku, ale do noci ani
// do večera se nedá pořádně kliknout a dlaždice v nich jsou zploštělé na
// nečitelnou čárku. Proto se každý krajní pás dá ROZBALIT do plných hodin —
// a jakmile je rozbalení volba uživatele, přestává být výška pásu konstanta.
// Celá osa se počítá v `geometrie()` a komponenta si ji drží podle stavu.

// Hranice pracovní části a výšky pásem v pixelech.
// POZOR: PX_HODINA musí odpovídat --kal-hodina v kalendar.css.
export const PRAC_OD = 7;
export const PRAC_DO = 19;
export const PX_HODINA = 44;
// Složený pás (0:00–7:00, 19:00–23:59). 30 px, ne 26: pás nese tlačítko na
// rozbalení a na 26 px z něj byl terč, který se hledal.
// POZOR: musí odpovídat fallbacku --kal-noc v kalendar.css.
export const PX_PAS = 30;

// Na kolik minut se tažení zaokrouhluje. Čtvrthodina je nejmenší jednotka, se
// kterou se schůzky reálně plánují — jemnější krok by dělal časy jako 10:07.
export const KROK_MIN = 15;
export const MIN_DELKA = 15;

const OD_MIN = PRAC_OD * 60;
const DO_MIN = PRAC_DO * 60;

/**
 * Geometrie svislé osy pro dané rozbalení krajních pásem.
 *
 * Vrací výšky pásem, celkovou výšku dne a dvojici vzájemně inverzních přepočtů
 * `yZMinut` / `minutyZY`. Rozbalený pás má výšku „počet hodin × hodina", takže
 * tytéž lineární vzorce platí pro složený i rozbalený stav — netřeba dvě
 * varianty výpočtu, které by se stejně po čase rozešly.
 */
export function geometrie(nocRozbalena = false, vecerRozbalena = false) {
  const pxNoc = nocRozbalena ? PRAC_OD * PX_HODINA : PX_PAS;
  const pxVecer = vecerRozbalena ? (24 - PRAC_DO) * PX_HODINA : PX_PAS;
  const yPrac = pxNoc;
  const yVecer = pxNoc + (PRAC_DO - PRAC_OD) * PX_HODINA;
  const vyska = yVecer + pxVecer;

  /** Minuta dne (0–1440) → svislá pozice v pixelech. */
  function yZMinut(min) {
    if (min <= OD_MIN) return (min / OD_MIN) * pxNoc;
    if (min >= DO_MIN) return yVecer + ((min - DO_MIN) / (1440 - DO_MIN)) * pxVecer;
    return yPrac + ((min - OD_MIN) / 60) * PX_HODINA;
  }

  /** Svislá pozice v pixelech → minuta dne. Inverze `yZMinut()`. */
  function minutyZY(y) {
    if (y <= yPrac) return (y / pxNoc) * OD_MIN;
    if (y >= yVecer) return DO_MIN + ((y - yVecer) / pxVecer) * (1440 - DO_MIN);
    return OD_MIN + ((y - yPrac) / PX_HODINA) * 60;
  }

  return {
    nocRozbalena,
    vecerRozbalena,
    pxNoc,
    pxVecer,
    yPrac,
    yVecer,
    vyska,
    yZMinut,
    minutyZY,
  };
}

/** Zaokrouhlí minutu na krok tažení a udrží ji v rámci dne. */
export function snap(min) {
  return Math.max(0, Math.min(1440 - KROK_MIN, Math.round(min / KROK_MIN) * KROK_MIN));
}

/** Minuta dne → „9:30" pro odeslání na server. */
export function naCas(min) {
  const h = Math.floor(min / 60);
  return `${h}:${String(Math.round(min % 60)).padStart(2, "0")}`;
}

/** „2026-08-03T09:30:00" → minuta dne. */
export function minutyZCasu(iso) {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

/** „2026-08-03T09:30:00" → „9:30" pro dlaždici. */
export function hm(iso) {
  const d = new Date(iso);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/**
 * Nový začátek a délka podle režimu tažení.
 *
 * `horni` mění začátek a KONEC nechává na místě — to je to, co člověk od tažení
 * za horní hranu čeká. Naivní „posuň začátek" by celou schůzku prodloužilo
 * i zkrátilo současně a konec by ujel.
 */
export function zTazeni(rezim, puvodOd, puvodDelka, deltaMin) {
  if (rezim === "horni") {
    const konec = puvodOd + puvodDelka;
    const od = Math.max(0, Math.min(snap(puvodOd + deltaMin), konec - MIN_DELKA));
    return { od, delka: konec - od };
  }
  if (rezim === "dolni") {
    return { od: puvodOd, delka: Math.max(MIN_DELKA, snap(puvodDelka + deltaMin)) };
  }
  // přesun: délka se nemění, začátek se posune (a nepřeteče přes konec dne)
  const od = Math.min(snap(puvodOd + deltaMin), 1440 - puvodDelka);
  return { od: Math.max(0, od), delka: puvodDelka };
}
