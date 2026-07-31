// Čištění formátovaného textu na straně prohlížeče.
//
// Zrcadlo backendového `vystup_html.py`. Backend je autorita (klientovi se
// nevěří), ale čistit se musí i tady: text se vkládá do contentEditable a
// hned se vykresluje, takže bez toho by vložení z Wordu vneslo na papír cizí
// styly a nepovolené značky ještě předtím, než se cokoli uloží.
//
// Whitelisty se musí držet shodné s backendem – když se mění tady, mění se
// i tam, jinak se text po uložení „sám přeformátuje“.

export const POVOLENE_TAGY = new Set([
  "P", "BR", "DIV", "SPAN", "STRONG", "B", "EM", "I", "U", "S",
  "UL", "OL", "LI", "H1", "H2", "H3", "H4",
]);

export const POLYKANE_TAGY = new Set(["SCRIPT", "STYLE", "TITLE", "TEXTAREA", "NOSCRIPT"]);

export const POVOLENE_STYLY = new Set([
  "color", "background-color", "font-size", "font-weight", "font-style",
  "text-decoration", "text-align", "font-family",
]);

export const POVOLENA_PISMA = [
  "inherit", "sans-serif", "serif", "monospace", "arial", "helvetica",
  "georgia", "times new roman", "courier new",
];

const ZAKAZANE_V_HODNOTE = /url\s*\(|expression|javascript:|@import|\/\*/i;
const HODNOTA_OK = /^[#a-zA-Z0-9 ,.%()'"-]+$/;

export const MAX_DELKA_HTML = 20000;

function stylOk(vlastnost, hodnota) {
  if (!POVOLENE_STYLY.has(vlastnost)) return false;
  if (!hodnota || hodnota.length > 120) return false;
  if (ZAKAZANE_V_HODNOTE.test(hodnota)) return false;
  if (!HODNOTA_OK.test(hodnota)) return false;
  if (vlastnost === "font-family") {
    const prvni = hodnota.split(",")[0].trim().replace(/['"]/g, "").toLowerCase();
    return POVOLENA_PISMA.includes(prvni);
  }
  return true;
}

/** Nechá v `style` jen povolené dvojice. */
function vycistiStyl(el) {
  const puvodni = el.getAttribute("style") || "";
  const kusy = [];
  for (const cast of puvodni.split(";")) {
    const dvojtecka = cast.indexOf(":");
    if (dvojtecka < 0) continue;
    const vlastnost = cast.slice(0, dvojtecka).trim().toLowerCase();
    const hodnota = cast.slice(dvojtecka + 1).trim();
    if (stylOk(vlastnost, hodnota)) kusy.push(`${vlastnost}: ${hodnota}`);
  }
  if (kusy.length) el.setAttribute("style", kusy.join("; "));
  else el.removeAttribute("style");
}

/** Nahradí prvek jeho obsahem – značka pryč, text zůstane. */
function rozbal(el) {
  const rodic = el.parentNode;
  if (!rodic) return;
  while (el.firstChild) rodic.insertBefore(el.firstChild, el);
  rodic.removeChild(el);
}

function projdi(uzel) {
  // Kopie seznamu: procházení mění strom pod rukama.
  for (const dite of Array.from(uzel.childNodes)) {
    if (dite.nodeType === Node.TEXT_NODE) continue;
    if (dite.nodeType !== Node.ELEMENT_NODE) {
      dite.remove(); // komentáře a podobné pryč
      continue;
    }
    const tag = dite.tagName.toUpperCase();
    if (POLYKANE_TAGY.has(tag)) {
      dite.remove(); // i s obsahem – tam je zrovna to nebezpečné
      continue;
    }
    projdi(dite);
    if (!POVOLENE_TAGY.has(tag)) {
      rozbal(dite);
      continue;
    }
    for (const atribut of Array.from(dite.attributes)) {
      if (atribut.name.toLowerCase() !== "style") dite.removeAttribute(atribut.name);
    }
    vycistiStyl(dite);
  }
}

/**
 * Vrátí bezpečnou podobu HTML z editoru.
 * Parsuje se přes `<template>`, takže se nic nenačítá ani nespouští.
 */
export function vycistiHtml(vstup) {
  if (!vstup) return "";
  const sablona = document.createElement("template");
  sablona.innerHTML = String(vstup).slice(0, MAX_DELKA_HTML);
  projdi(sablona.content);
  return sablona.innerHTML;
}

/** Holý text – pro zjištění, jestli je prvek prázdný. */
export function jenText(html) {
  if (!html) return "";
  const sablona = document.createElement("template");
  sablona.innerHTML = String(html);
  return (sablona.content.textContent || "").trim();
}

export function jePrazdny(html) {
  return jenText(html) === "";
}
