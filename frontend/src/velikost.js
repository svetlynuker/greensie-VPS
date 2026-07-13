// Velikost textu (zobrazovací preference zařízení, uložená v prohlížeči).
// Základ je 14 px; „střední" = +2 body, „velké" = +4 body → proporční zvětšení celé appky.
const KEY = "greensie_velikost";
const HODNOTY = {
  male: 1,
  stredni: 16 / 14,
  velke: 18 / 14,
};

export function getVelikost() {
  const v = localStorage.getItem(KEY);
  return HODNOTY[v] ? v : "male";
}

export function applyVelikost(v) {
  document.documentElement.style.zoom = String(HODNOTY[v] || 1);
}

export function setVelikost(v) {
  localStorage.setItem(KEY, v);
  applyVelikost(v);
  return v;
}

export function initVelikost() {
  applyVelikost(getVelikost());
}
