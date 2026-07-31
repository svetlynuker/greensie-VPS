// Kolik řádků tabulka ukáže najednou (CRM-38).
//
// Drží se v prohlížeči, ne v profilu na serveru — na rozdíl od rozvržení
// sloupců (CRM-28) je to volba závislá na TOMHLE displeji: na notebooku chce
// člověk 25 řádků, na velkém monitoru 100. Přenášet ji mezi počítači by byla
// medvědí služba.
//
// Stránkuje se na klientu nad už načtenými řádky, stejně jako se filtruje
// (viz `crmFiltry.js`). Skutečné serverové stránkování je CRM-02 a čeká na
// spouštěč ~300 řádků v seznamu.

const KLIC = "greensie_radku_na_stranku";

/** `0` = bez omezení. Je to poslední volba schválně: dokud jsou seznamy malé,
 *  je „vše" nejpohodlnější, a u velkých si člověk vybere sám. */
export const VELIKOSTI_STRANKY = [25, 50, 100, 0];

export const VYCHOZI_NA_STRANKU = 50;

export function nactiNaStranku() {
  const ulozene = Number(localStorage.getItem(KLIC));
  return VELIKOSTI_STRANKY.includes(ulozene) ? ulozene : VYCHOZI_NA_STRANKU;
}

export function ulozNaStranku(hodnota) {
  localStorage.setItem(KLIC, String(hodnota));
}

export function popisVelikosti(hodnota) {
  return hodnota === 0 ? "vše" : String(hodnota);
}
