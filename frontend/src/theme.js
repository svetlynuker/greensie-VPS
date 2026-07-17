const KEY = "greensie_theme";
const KEY_CVD = "greensie_cvd";

export function getTheme() {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

// Nastaví konkrétní téma (localStorage = rychlá lokální paměť, aby při startu
// appky neproblikla špatná varianta). Do DB se ukládá zvlášť z komponent.
export function setTheme(theme) {
  const t = theme === "dark" ? "dark" : "light";
  localStorage.setItem(KEY, t);
  applyTheme(t);
  return t;
}

export function toggleTheme() {
  return setTheme(getTheme() === "dark" ? "light" : "dark");
}

// ---- Kompenzace červeno-zelené vady (deuteranopie/protanopie) ----
// Přepíná atribut data-cvd na <html>; CSS pak vymění stavové barvy a barvy
// grafů za paletu čitelnou bez rozlišení červená/zelená (viz global.css).

export function getCvd() {
  return localStorage.getItem(KEY_CVD) === "on" ? "on" : "off";
}

export function applyCvd(cvd) {
  if (cvd === "on") {
    document.documentElement.setAttribute("data-cvd", "on");
  } else {
    document.documentElement.removeAttribute("data-cvd");
  }
}

export function setCvd(cvd) {
  const c = cvd === "on" ? "on" : "off";
  localStorage.setItem(KEY_CVD, c);
  applyCvd(c);
  return c;
}

export function toggleCvd() {
  return setCvd(getCvd() === "on" ? "off" : "on");
}

// Zavolat při startu appky, ať se uložené volby použijí hned.
export function initTheme() {
  applyTheme(getTheme());
  applyCvd(getCvd());
}
