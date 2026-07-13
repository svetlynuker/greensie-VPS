const KEY = "greensie_theme";

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

// Zavolat při startu appky, ať se uložená volba použije hned.
export function initTheme() {
  applyTheme(getTheme());
}
