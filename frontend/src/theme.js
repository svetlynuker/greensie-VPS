const KEY = "greensie_theme";

export function getTheme() {
  return localStorage.getItem(KEY) === "dark" ? "dark" : "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function toggleTheme() {
  const novy = getTheme() === "dark" ? "light" : "dark";
  localStorage.setItem(KEY, novy);
  applyTheme(novy);
  return novy;
}

// Zavolat při startu appky, ať se uložená volba použije hned.
export function initTheme() {
  applyTheme(getTheme());
}
