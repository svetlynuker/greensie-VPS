// Čistá datová a kreslicí vrstva nitkového grafu průběhu (`GrafPrubehu.jsx`).
//
// Proč zvlášť: jsou to funkce bez Reactu, které se dají otestovat samostatně
// (kreslení stačí pustit s falešným kontextem, který si zapisuje souřadnice) –
// a hlavně by jejich export přímo z komponenty rozbil Fast Refresh při vývoji.

export const MESICE_ZKR = ["led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"];
export const DNY_ZKR = ["ne", "po", "út", "st", "čt", "pá", "so"];

export function dvojcifernne(x) {
  return String(x).padStart(2, "0");
}

// ------------------------------------------------------------ slévání dat
// Koše se drží v typovaných polích, která se mezi překresleními recyklují –
// při posunu grafu se tak každý snímek nealokuje ~900 objektů (a nezahazuje).
function vytvorKose(kapacita) {
  const f = () => new Float32Array(kapacita);
  return {
    kapacita,
    pocet: 0,
    krok: 1,
    t: new Float64Array(kapacita),
    i0: new Int32Array(kapacita),
    i1: new Int32Array(kapacita),
    oMin: f(), oMax: f(), oPrum: f(),
    sMin: f(), sMax: f(), sPrum: f(),
    bMin: f(), bMax: f(), bPrum: f(),
    cPrum: f(),
  };
}

// Z rozsahu indexů udělá koše; každý nese min/max/průměr všech řad. Min/max
// jsou důležitější než průměr: díky nim zůstane špička vidět i z celého roku.
export function agreguj(data, od, doIdx, cil, kose) {
  const O = data.odber_kw, S = data.site_kw, B = data.baterie_kw, C = data.soc_pct, T = data.casy_min;
  const pocet = Math.max(1, doIdx - od);
  const krok = Math.max(1, Math.ceil(pocet / cil));
  const k = kose && kose.kapacita >= Math.ceil(pocet / krok) ? kose : vytvorKose(Math.max(cil, Math.ceil(pocet / krok)));
  let n = 0;
  for (let i = od; i < doIdx; i += krok) {
    const j = Math.min(doIdx, i + krok);
    let oMin = Infinity, oMax = -Infinity, oSum = 0;
    let sMin = Infinity, sMax = -Infinity, sSum = 0;
    let bMin = Infinity, bMax = -Infinity, bSum = 0;
    let cSum = 0;
    for (let x = i; x < j; x++) {
      const o = O[x], s = S[x], b = B[x];
      if (o < oMin) oMin = o;
      if (o > oMax) oMax = o;
      oSum += o;
      if (s < sMin) sMin = s;
      if (s > sMax) sMax = s;
      sSum += s;
      if (b < bMin) bMin = b;
      if (b > bMax) bMax = b;
      bSum += b;
      cSum += C[x];
    }
    const p = j - i;
    k.t[n] = T[i];
    k.i0[n] = i;
    k.i1[n] = j - 1;
    k.oMin[n] = oMin; k.oMax[n] = oMax; k.oPrum[n] = oSum / p;
    k.sMin[n] = sMin; k.sMax[n] = sMax; k.sPrum[n] = sSum / p;
    k.bMin[n] = bMin; k.bMax[n] = bMax; k.bPrum[n] = bSum / p;
    k.cPrum[n] = cSum / p;
    n++;
  }
  k.pocet = n;
  k.krok = krok;
  return k;
}

// Hezký krok mřížky (1/2/5 × 10^n) pro daný rozsah.
function hezkyKrok(rozsah, pocet) {
  const hruby = rozsah / Math.max(1, pocet);
  const rad = Math.pow(10, Math.floor(Math.log10(hruby || 1)));
  for (const n of [1, 2, 2.5, 5, 10]) {
    if (rad * n >= hruby) return rad * n;
  }
  return rad * 10;
}

export function ticky(min, max, pocet = 4) {
  if (!(max > min)) return [min];
  const k = hezkyKrok(max - min, pocet);
  const out = [];
  for (let v = Math.ceil(min / k) * k; v <= max + 1e-9; v += k) out.push(Number(v.toFixed(6)));
  return out;
}

// Popisky časové osy podle šířky výřezu (rok → měsíce, den → hodiny…).
export function osaCasu(zaklad, tOd, tDo, hustota = 1) {
  const d0 = new Date(zaklad + tOd * 60000);
  const d1 = new Date(zaklad + tDo * 60000);
  const dnu = (d1 - d0) / 86400000;
  const out = [];
  const pridej = (d, popis) => out.push({ t: (d - zaklad) / 60000, popis });

  if (dnu > 70) {
    const d = new Date(d0.getFullYear(), d0.getMonth(), 1);
    const kazdy = dnu > 260 && hustota < 1 ? 2 : 1; // na úzkém displeji ob měsíc
    let i = 0;
    while (d <= d1) {
      if (d >= d0 && i % kazdy === 0) pridej(d, MESICE_ZKR[d.getMonth()]);
      d.setMonth(d.getMonth() + 1);
      i++;
    }
  } else if (dnu > 3) {
    const zaklKrok = dnu > 40 ? 7 : dnu > 16 ? 3 : dnu > 8 ? 2 : 1;
    const krokDnu = hustota < 1 ? zaklKrok * 2 : zaklKrok;
    const d = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate());
    if (d < d0) d.setDate(d.getDate() + 1);
    while (d <= d1) {
      pridej(d, `${DNY_ZKR[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`);
      d.setDate(d.getDate() + krokDnu);
    }
  } else if (dnu > 0.3) {
    const zaklKrok = dnu > 2 ? 6 : dnu > 1 ? 4 : 2;
    const krokH = hustota < 1 ? zaklKrok * 2 : zaklKrok;
    const d = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate(), d0.getHours());
    if (d < d0) d.setHours(d.getHours() + 1);
    while (d <= d1) {
      if (d.getHours() % krokH === 0) {
        pridej(d, d.getHours() === 0 ? `${d.getDate()}.${d.getMonth() + 1}.` : `${dvojcifernne(d.getHours())}:00`);
      }
      d.setHours(d.getHours() + 1);
    }
  } else {
    const minut = dnu * 1440;
    const zaklKrok = minut > 240 ? 60 : minut > 120 ? 30 : 15;
    const krokM = hustota < 1 ? zaklKrok * 2 : zaklKrok;
    const d = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate(), d0.getHours(), 0);
    while (d <= d1) {
      if (d >= d0 && d.getMinutes() % krokM === 0) {
        pridej(d, `${dvojcifernne(d.getHours())}:${dvojcifernne(d.getMinutes())}`);
      }
      d.setMinutes(d.getMinutes() + 15);
    }
  }
  return out;
}

// ------------------------------------------------------------- kreslení
// Kreslení datových vrstev do canvasu. Vytažené z komponenty ven, aby se dalo
// otestovat s falešným kontextem, který si zapisuje souřadnice.
export function kresliData(ctx, k) {
  const { kose, x, yH, yB, yS, serie, barvy, mrizka, sirka, vyska } = k;
  const n = kose.pocet;
  ctx.clearRect(0, 0, sirka, vyska);
  if (n === 0) return;

  const nitka = (pole, y, barva, tloustka) => {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const px = x(kose.t[i]);
      const py = y(pole[i]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.strokeStyle = barva;
    ctx.lineWidth = tloustka;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();
  };
  const pasmo = (poleMin, poleMax, y, barva, alfa) => {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const px = x(kose.t[i]);
      const py = y(poleMax[i]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    for (let i = n - 1; i >= 0; i--) ctx.lineTo(x(kose.t[i]), y(poleMin[i]));
    ctx.closePath();
    ctx.globalAlpha = alfa;
    ctx.fillStyle = barva;
    ctx.fill();
    ctx.globalAlpha = 1;
  };

  // mřížka pod daty
  ctx.strokeStyle = barvy.grid;
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (const c of mrizka.vodorovne) {
    ctx.moveTo(mrizka.x0, Math.round(c) + 0.5);
    ctx.lineTo(mrizka.x1, Math.round(c) + 0.5);
  }
  for (const c of mrizka.svisle) {
    ctx.moveTo(Math.round(c) + 0.5, mrizka.yOd);
    ctx.lineTo(Math.round(c) + 0.5, mrizka.yDo);
  }
  ctx.stroke();

  // odběr bez baterie (co by teklo ze sítě dnes)
  if (serie.bez) {
    pasmo(kose.oMin, kose.oMax, yH, barvy.before, 0.4);
    nitka(kose.oPrum, yH, barvy.before, 1.2);
  }
  // odběr ze sítě po instalaci baterie – hlavní nitka
  pasmo(kose.sMin, kose.sMax, yH, barvy.after, 0.2);
  nitka(kose.sPrum, yH, barvy.after, 1.6);

  // výkon baterie: nad nulou vybíjení, pod nulou nabíjení
  if (serie.baterie) {
    pasmo(kose.bMin, kose.bMax, yB, barvy.brand, 0.18);
    nitka(kose.bPrum, yB, barvy.brand, 1.3);
  }
  // stav nabití
  if (serie.soc) {
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const px = x(kose.t[i]);
      const py = yS(kose.cPrum[i]);
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    }
    ctx.lineTo(x(kose.t[n - 1]), yS(0));
    ctx.lineTo(x(kose.t[0]), yS(0));
    ctx.closePath();
    ctx.globalAlpha = 0.16;
    ctx.fillStyle = barvy.refnew;
    ctx.fill();
    ctx.globalAlpha = 1;
    nitka(kose.cPrum, yS, barvy.refnew, 1.3);
  }
}

// Přehledová lišta (celý rok v malém) – kreslí se jen při změně dat/šířky.
export function kresliPrehled(ctx, k) {
  const { kose, xp, yp, barva, y0, vyskaPruhu } = k;
  const n = kose.pocet;
  if (!n) return;
  ctx.clearRect(0, y0, k.sirka, vyskaPruhu + 1);
  ctx.beginPath();
  ctx.moveTo(xp(kose.i0[0]), yp(0));
  for (let i = 0; i < n; i++) ctx.lineTo(xp(kose.i0[i]), yp(kose.oMax[i]));
  ctx.lineTo(xp(kose.i1[n - 1]), yp(0));
  ctx.closePath();
  ctx.globalAlpha = 0.5;
  ctx.fillStyle = barva;
  ctx.fill();
  ctx.globalAlpha = 1;
}

