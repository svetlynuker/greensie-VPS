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

// Hranice pracovní části a výšky pásem v pixelech.
// POZOR: musí odpovídat --kal-hodina v kalendar.css.
export const PRAC_OD = 7;
export const PRAC_DO = 19;
export const PX_HODINA = 44;
export const PX_NOC = 26; // pás 0:00–7:00
export const PX_VECER = 26; // pás 19:00–23:59

export const VYSKA_DNE = PX_NOC + (PRAC_DO - PRAC_OD) * PX_HODINA + PX_VECER;

// Na kolik minut se tažení zaokrouhluje. Čtvrthodina je nejmenší jednotka, se
// kterou se schůzky reálně plánují — jemnější krok by dělal časy jako 10:07.
export const KROK_MIN = 15;
export const MIN_DELKA = 15;

const OD_MIN = PRAC_OD * 60;
const DO_MIN = PRAC_DO * 60;
const Y_PRAC = PX_NOC;
const Y_VECER = PX_NOC + ((DO_MIN - OD_MIN) / 60) * PX_HODINA;

/** Minuta dne (0–1440) → svislá pozice v pixelech. */
export function yZMinut(min) {
  if (min <= OD_MIN) return (min / OD_MIN) * PX_NOC;
  if (min >= DO_MIN) return Y_VECER + ((min - DO_MIN) / (1440 - DO_MIN)) * PX_VECER;
  return Y_PRAC + ((min - OD_MIN) / 60) * PX_HODINA;
}

/** Svislá pozice v pixelech → minuta dne. Inverze `yZMinut()`. */
export function minutyZY(y) {
  if (y <= Y_PRAC) return (y / PX_NOC) * OD_MIN;
  if (y >= Y_VECER) return DO_MIN + ((y - Y_VECER) / PX_VECER) * (1440 - DO_MIN);
  return OD_MIN + ((y - Y_PRAC) / PX_HODINA) * 60;
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
