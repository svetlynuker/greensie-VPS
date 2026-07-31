// Tažení a změna velikosti prvků na papíře.
//
// Postavené na pointer events (jeden kód pro myš i dotyk) místo HTML5
// drag-and-drop: HTML5 tažení neumí průběžně hlásit pozici v milimetrech,
// nejde u něj rozumně kreslit vodicí linky a v prohlížečích se chová pokaždé
// trochu jinak. Tady si pozici počítáme sami, takže snap i náhled sedí přesně.
//
// Souřadnice jsou vždy v mm vůči stránce. Převod z pixelů dělá poměr změřený
// na skutečné šířce vykreslené stránky – tím se samo zohlední i zoom.

import {
  A4_SIRKA,
  A4_VYSKA,
  MIN_SIRKA,
  MIN_VYSKA,
  MRIZKA,
  OBSAH_DO,
  OBSAH_OD,
  OKRAJ_BOK,
  naMrizku,
  omezNaPapir,
  zaokrouhli,
} from "./model";

// Jak blízko (v mm) musí hrana být, aby se přichytila k sousedovi.
const TOLERANCE_SNAPU = 2;

/** Kolik pixelů má jeden milimetr na vykreslené stránce (počítá i zoom). */
export function pxNaMm(elementStranky) {
  if (!elementStranky) return 1;
  const sirkaPx = elementStranky.getBoundingClientRect().width;
  return sirkaPx > 0 ? sirkaPx / A4_SIRKA : 1;
}

/** Pozice ukazatele v mm vůči levému hornímu rohu stránky. */
export function bodVMm(udalost, elementStranky) {
  const r = elementStranky.getBoundingClientRect();
  const pomer = pxNaMm(elementStranky);
  return {
    x: (udalost.clientX - r.left) / pomer,
    y: (udalost.clientY - r.top) / pomer,
  };
}

/**
 * Linky, ke kterým se přichytává: okraje sazby a hrany ostatních prvků.
 * `krome` je id taženého prvku – sám na sebe se nepřichytává.
 */
export function kandidatiSnapu(stranka, krome) {
  const svisle = [OKRAJ_BOK, A4_SIRKA / 2, A4_SIRKA - OKRAJ_BOK];
  const vodorovne = [OBSAH_OD, A4_VYSKA / 2, OBSAH_DO];
  for (const p of stranka?.prvky || []) {
    if (p.id === krome || !p.viditelny) continue;
    svisle.push(p.x, p.x + p.sirka / 2, p.x + p.sirka);
    vodorovne.push(p.y, p.y + p.vyska / 2, p.y + p.vyska);
  }
  return { svisle, vodorovne };
}

/** Najde nejbližší linku k některé z hran. Vrací posun a linku, nebo null. */
function nejblizsi(hrany, linky) {
  let nej = null;
  for (const hrana of hrany) {
    for (const linka of linky) {
      const rozdil = linka - hrana;
      if (Math.abs(rozdil) <= TOLERANCE_SNAPU) {
        if (!nej || Math.abs(rozdil) < Math.abs(nej.posun)) {
          nej = { posun: rozdil, linka };
        }
      }
    }
  }
  return nej;
}

/**
 * Přichytí pozici prvku. Nejdřív se zkusí hrany sousedů (to je to, co
 * uživatel opravdu chce – zarovnat na sebe), a teprve když nic není
 * nablízku, spadne se na mřížku.
 *
 * Vrací `{ x, y, linky }`, kde `linky` jsou vodítka k vykreslení.
 */
export function prichyt(x, y, sirka, vyska, kandidati, mrizkaZapnuta = true) {
  const linky = [];
  let vysledekX = x;
  let vysledekY = y;

  const snapX = nejblizsi([x, x + sirka / 2, x + sirka], kandidati.svisle);
  if (snapX) {
    vysledekX = x + snapX.posun;
    linky.push({ smer: "svisle", pozice: snapX.linka });
  } else if (mrizkaZapnuta) {
    vysledekX = naMrizku(x);
  }

  const snapY = nejblizsi([y, y + vyska / 2, y + vyska], kandidati.vodorovne);
  if (snapY) {
    vysledekY = y + snapY.posun;
    linky.push({ smer: "vodorovne", pozice: snapY.linka });
  } else if (mrizkaZapnuta) {
    vysledekY = naMrizku(y);
  }

  return { x: zaokrouhli(vysledekX), y: zaokrouhli(vysledekY), linky };
}

// Které hrany úchyt posouvá. `s` = sever (nahoře), `v` = východ (vpravo)…
export const UCHOPY = ["sz", "s", "sv", "v", "jv", "j", "jz", "z"];

/**
 * Spočítá nový obdélník při tažení za úchyt. Prvek se nikdy nepřevrátí –
 * pod minimem se zastaví, takže tažení „skrz“ protější hranu jen zmenšuje.
 */
export function zmenVelikost(puvodni, uchop, dx, dy, kandidati, mrizkaZapnuta) {
  let { x, y, sirka, vyska } = puvodni;

  if (uchop.includes("z")) {
    const novaSirka = Math.max(MIN_SIRKA, puvodni.sirka - dx);
    x = puvodni.x + (puvodni.sirka - novaSirka);
    sirka = novaSirka;
  }
  if (uchop.includes("v")) {
    sirka = Math.max(MIN_SIRKA, puvodni.sirka + dx);
  }
  if (uchop.includes("s")) {
    const novaVyska = Math.max(MIN_VYSKA, puvodni.vyska - dy);
    y = puvodni.y + (puvodni.vyska - novaVyska);
    vyska = novaVyska;
  }
  if (uchop.includes("j")) {
    vyska = Math.max(MIN_VYSKA, puvodni.vyska + dy);
  }

  // Přichytáváme hranu, kterou uživatel drží – ne celý prvek.
  const linky = [];
  if (mrizkaZapnuta || kandidati) {
    if (uchop.includes("z")) {
      const snap = nejblizsi([x], kandidati.svisle);
      const cil = snap ? snap.linka : naMrizku(x);
      sirka = Math.max(MIN_SIRKA, sirka + (x - cil));
      x = cil;
      if (snap) linky.push({ smer: "svisle", pozice: snap.linka });
    }
    if (uchop.includes("v")) {
      const snap = nejblizsi([x + sirka], kandidati.svisle);
      const cil = snap ? snap.linka : naMrizku(x + sirka);
      sirka = Math.max(MIN_SIRKA, cil - x);
      if (snap) linky.push({ smer: "svisle", pozice: snap.linka });
    }
    if (uchop.includes("s")) {
      const snap = nejblizsi([y], kandidati.vodorovne);
      const cil = snap ? snap.linka : naMrizku(y);
      vyska = Math.max(MIN_VYSKA, vyska + (y - cil));
      y = cil;
      if (snap) linky.push({ smer: "vodorovne", pozice: snap.linka });
    }
    if (uchop.includes("j")) {
      const snap = nejblizsi([y + vyska], kandidati.vodorovne);
      const cil = snap ? snap.linka : naMrizku(y + vyska);
      vyska = Math.max(MIN_VYSKA, cil - y);
      if (snap) linky.push({ smer: "vodorovne", pozice: snap.linka });
    }
  }

  return {
    x: zaokrouhli(x),
    y: zaokrouhli(y),
    sirka: zaokrouhli(Math.min(sirka, A4_SIRKA * 1.5)),
    vyska: zaokrouhli(Math.min(vyska, A4_VYSKA * 1.5)),
    linky,
  };
}

/**
 * Co je pod ukazatelem: stránka, případně kontejner a místo v něm.
 *
 * Čte se z DOM (`elementsFromPoint`) místo počítání z modelu, protože výšku
 * prvků s automatickou výškou zná jen prohlížeč – ten už je vykreslil.
 * Tažený prvek musí mít po dobu tažení `pointer-events: none`, jinak by
 * clona zakryla všechno pod sebou.
 */
export function cilPodUkazatelem(udalost, tazenyId) {
  const pod = document.elementsFromPoint(udalost.clientX, udalost.clientY);

  const kontejnerEl = pod.find(
    (el) => el.dataset?.kontejnerId && el.dataset.kontejnerId !== tazenyId
  );
  if (kontejnerEl) {
    return {
      typ: "kontejner",
      kontejnerId: kontejnerEl.dataset.kontejnerId,
      index: indexVKontejneru(kontejnerEl, udalost.clientY, tazenyId),
      element: kontejnerEl,
    };
  }

  const strankaEl = pod.find((el) => el.dataset?.strankaId);
  if (strankaEl) {
    return { typ: "stranka", strankaId: strankaEl.dataset.strankaId, element: strankaEl };
  }
  return null;
}

/** Kam mezi děti kontejneru prvek patří – podle svislé pozice ukazatele. */
function indexVKontejneru(kontejnerEl, clientY, tazenyId) {
  const deti = Array.from(kontejnerEl.querySelectorAll("[data-prvek-id]")).filter(
    (el) => el.dataset.prvekId !== tazenyId
  );
  for (let i = 0; i < deti.length; i += 1) {
    const r = deti[i].getBoundingClientRect();
    if (clientY < r.top + r.height / 2) return i;
  }
  return deti.length;
}

/**
 * Kam se prvek položí, když ho uživatel pustí. Souřadnice pro stránku se
 * počítají tak, aby prvek zůstal „pod prstem“ tam, kde ho uživatel chytil.
 */
export function vyhodnotPusteni(cil, pozice, rozmery) {
  if (!cil) return null;
  if (cil.typ === "kontejner") {
    return { typ: "kontejner", kontejnerId: cil.kontejnerId, index: cil.index };
  }
  const omezene = omezNaPapir(pozice.x, pozice.y, rozmery.sirka, rozmery.vyska);
  return { typ: "stranka", strankaId: cil.strankaId, x: omezene.x, y: omezene.y };
}

/** Posun šipkami: jemný po 1 mm, se Shiftem po kroku mřížky. */
export function posunKlavesou(klavesa, sShiftem) {
  const krok = sShiftem ? MRIZKA : 1;
  switch (klavesa) {
    case "ArrowLeft":
      return { dx: -krok, dy: 0 };
    case "ArrowRight":
      return { dx: krok, dy: 0 };
    case "ArrowUp":
      return { dx: 0, dy: -krok };
    case "ArrowDown":
      return { dx: 0, dy: krok };
    default:
      return null;
  }
}
