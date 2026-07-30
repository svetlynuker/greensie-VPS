// Barvy druhů aktivit v kalendáři — osobní nastavení každého uživatele.
//
// Proč vůbec nastavitelné: v kalendáři se barvou rozeznává, co za den člověka
// čeká. Jaká barva „znamená" schůzku je ale věc zvyku (a kdo špatně rozlišuje
// červenou a zelenou, potřebuje jinou paletu než ostatní), takže je to volba
// uživatele, ne firemní nastavení.
//
// Uloženo v `uzivatelska_nastaveni` pod klíčem `kalendar_barvy` jako
// {druh: "#rrggbb"}. Tím se přenese mezi počítači — localStorage by zůstal
// na jednom stroji. Chybějící druh spadne na výchozí z `DRUHY_AKTIVITY`.

import { DRUHY_AKTIVITY } from "./crm";

export const KLIC_NASTAVENI = "kalendar_barvy";

/** Výchozí paleta: {druh: barva} z definice druhů aktivit. */
export function vychoziBarvy() {
  return Object.fromEntries(DRUHY_AKTIVITY.map((d) => [d.klic, d.barva]));
}

// Vlastní barvy se ukládají v profilu uživatele, ale číst se musí i tam, kde se
// jen kreslí (dlaždice kalendáře). Cizí ani neplatné hodnoty se zahazují:
// barva jde přímo do CSS, takže sem nesmí propadnout nic jiného než #rrggbb.
const HEX = /^#[0-9a-fA-F]{6}$/;

/** Sloučí uložené nastavení s výchozím a zahodí neplatné hodnoty. */
export function slucBarvy(ulozene) {
  const out = vychoziBarvy();
  for (const [druh, barva] of Object.entries(ulozene || {})) {
    if (druh in out && typeof barva === "string" && HEX.test(barva)) {
      out[druh] = barva;
    }
  }
  return out;
}

/** Barva jednoho druhu; `barvy` je výsledek `slucBarvy()`. */
export function barvaDruhu(barvy, druh) {
  return (barvy || {})[druh] || vychoziBarvy()[druh] || "#7b8794";
}

/**
 * Čitelná barva textu na daném podkladu (černá, nebo bílá).
 *
 * Bez tohohle by světle žlutá dlaždice měla bílý text a nikdo by ji nepřečetl.
 * Použitá je relativní svítivost podle WCAG, ne prostý průměr složek — oko
 * vnímá zelenou mnohem silněji než modrou, takže průměr by u zelených barev
 * volil špatně.
 */
export function barvaTextuNa(pozadi) {
  const m = HEX.test(pozadi || "") ? pozadi.slice(1) : "808080";
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(m.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const L = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  return L > 0.45 ? "#101418" : "#ffffff";
}
