// Nitkový graf průběhu peak shavingu: celý rok po 15 minutách, se zoomem od
// přehledu měsíců až na jednotlivé čtvrthodiny. Ukazuje, co se v odběrném
// místě opravdu děje – kolik teče ze sítě, kdy baterie kryje špičku, kdy se
// dobíjí a jak jí přitom klesá stav nabití.
//
// Bez grafové knihovny (projekt žádnou nemá) – SVG + CSS tokeny --c-*, takže
// graf sám funguje ve světlém i tmavém režimu.
//
// Jak je vyřešený objem dat: backend pošle celoroční řady (~35 000 hodnot),
// komponenta si je při každé změně přiblížení sama slije do ~900 „košů“ a
// z každého kreslí pásmo min–max + průměrovou nitku. Špička tak nikdy
// nezmizí zaokrouhlením (což by u peak shavingu byla fatální lež) a při
// plném přiblížení (koš = 1 interval) pásmo splyne s nitkou a vidíš přesné
// čtvrthodinové hodnoty.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

const MESICE_ZKR = ["led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"];
const DNY_ZKR = ["ne", "po", "út", "st", "čt", "pá", "so"];

// Rozměry pásů grafu (v px, SVG kreslíme 1:1 se šířkou kontejneru).
const OKRAJ = { l: 56, r: 16, t: 12 };
const V_HLAVNI = 260; // odběr / síť (kW)
const V_BATERIE = 104; // výkon baterie ± (kW)
const V_SOC = 66; // stav nabití (%)
const V_PREHLED = 42; // přehledová lišta s výřezem
const V_OSA = 20; // pruh s popisky času
const MEZERA = 8;

// Na kolik bodů se řada slévá. ~900 stačí na pixel-přesný obrázek i na
// širokém monitoru a zoom zůstává svižný.
const CIL_BODU = 900;

// Nejmenší možný výřez (4 intervaly = 1 hodina), ať se zoom nezacyklí.
const MIN_INTERVALU = 4;

const KATEGORIE = [
  { klic: "spicka", nazev: "Špičky", barva: "var(--st-serious)" },
  { klic: "sedlo", nazev: "Sedla", barva: "var(--c-export)" },
  { klic: "baterie", nazev: "Baterie", barva: "var(--brand)" },
  { klic: "prekroceni", nazev: "Překročení", barva: "var(--st-crit)" },
];

function barvaKategorie(k) {
  return KATEGORIE.find((x) => x.klic === k)?.barva || "var(--c-axis)";
}

function fmtKw(v, des = 1) {
  return `${Number(v).toLocaleString("cs-CZ", { maximumFractionDigits: des })} kW`;
}

function dvojcifernne(x) {
  return String(x).padStart(2, "0");
}

function fmtCas(d, sSekundami = false) {
  const den = `${d.getDate()}.${d.getMonth() + 1}.`;
  const cas = `${dvojcifernne(d.getHours())}:${dvojcifernne(d.getMinutes())}`;
  return sSekundami ? `${DNY_ZKR[d.getDay()]} ${den} ${cas}` : `${den} ${cas}`;
}

// ------------------------------------------------------------ slévání dat
// Z rozsahu indexů udělá ~`cil` košů; každý nese min/max/průměr všech řad.
// Min/max jsou důležitější než průměr: díky nim zůstane špička vidět i při
// pohledu na celý rok.
function agreguj(data, od, doIdx, cil) {
  const O = data.odber_kw;
  const S = data.site_kw;
  const B = data.baterie_kw;
  const C = data.soc_pct;
  const T = data.casy_min;
  const pocet = Math.max(1, doIdx - od);
  const krok = Math.max(1, Math.ceil(pocet / cil));
  const body = [];
  for (let i = od; i < doIdx; i += krok) {
    const j = Math.min(doIdx, i + krok);
    let oMin = Infinity, oMax = -Infinity, oSum = 0;
    let sMin = Infinity, sMax = -Infinity, sSum = 0;
    let bMin = Infinity, bMax = -Infinity, bSum = 0;
    let cMin = Infinity, cMax = -Infinity, cSum = 0;
    let iMaxSite = i;
    for (let k = i; k < j; k++) {
      const o = O[k], s = S[k], b = B[k], c = C[k];
      if (o < oMin) oMin = o;
      if (o > oMax) oMax = o;
      oSum += o;
      if (s < sMin) sMin = s;
      if (s > sMax) { sMax = s; iMaxSite = k; }
      sSum += s;
      if (b < bMin) bMin = b;
      if (b > bMax) bMax = b;
      bSum += b;
      if (c < cMin) cMin = c;
      if (c > cMax) cMax = c;
      cSum += c;
    }
    const p = j - i;
    body.push({
      i0: i, i1: j - 1, iMaxSite,
      t: T[i], t1: T[j - 1],
      oMin, oMax, oPrum: oSum / p,
      sMin, sMax, sPrum: sSum / p,
      bMin, bMax, bPrum: bSum / p,
      cMin, cMax, cPrum: cSum / p,
    });
  }
  return { krok, body };
}

// Hezký krok mřížky (1/2/5 × 10^n) pro daný rozsah.
function hezkyKrok(rozsah, pocet) {
  const hrubý = rozsah / Math.max(1, pocet);
  const rad = Math.pow(10, Math.floor(Math.log10(hrubý || 1)));
  for (const n of [1, 2, 2.5, 5, 10]) {
    if (rad * n >= hrubý) return rad * n;
  }
  return rad * 10;
}

function ticky(min, max, pocet = 4) {
  if (!(max > min)) return [min];
  const k = hezkyKrok(max - min, pocet);
  const out = [];
  for (let v = Math.ceil(min / k) * k; v <= max + 1e-9; v += k) out.push(Number(v.toFixed(6)));
  return out;
}

// Popisky časové osy podle šířky výřezu (rok → měsíce, den → hodiny…).
function osaCasu(zaklad, tOd, tDo) {
  const d0 = new Date(zaklad + tOd * 60000);
  const d1 = new Date(zaklad + tDo * 60000);
  const dnu = (d1 - d0) / 86400000;
  const out = [];
  const pridej = (d, popis) => out.push({ t: (d - zaklad) / 60000, popis });

  if (dnu > 70) {
    const d = new Date(d0.getFullYear(), d0.getMonth(), 1);
    while (d <= d1) {
      if (d >= d0) pridej(d, MESICE_ZKR[d.getMonth()]);
      d.setMonth(d.getMonth() + 1);
    }
  } else if (dnu > 3) {
    const krokDnu = dnu > 40 ? 7 : dnu > 16 ? 3 : dnu > 8 ? 2 : 1;
    const d = new Date(d0.getFullYear(), d0.getMonth(), d0.getDate());
    if (d < d0) d.setDate(d.getDate() + 1);
    while (d <= d1) {
      pridej(d, `${DNY_ZKR[d.getDay()]} ${d.getDate()}.${d.getMonth() + 1}.`);
      d.setDate(d.getDate() + krokDnu);
    }
  } else if (dnu > 0.3) {
    const krokH = dnu > 2 ? 6 : dnu > 1 ? 4 : 2;
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
    const krokM = minut > 240 ? 60 : minut > 120 ? 30 : 15;
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

// Šířka kontejneru (SVG kreslíme v pixelech 1:1, ať se nedeformují popisky).
function useSirka(ref, vychozi = 900) {
  const [sirka, setSirka] = useState(vychozi);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const zmer = () => setSirka(Math.max(360, el.clientWidth));
    zmer();
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(zmer);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return sirka;
}

// Cesta pro nitku (průměry) a pásmo (min–max) přes koše.
function cestaNitky(body, x, y, klicPrumeru) {
  let d = "";
  for (let i = 0; i < body.length; i++) {
    const b = body[i];
    d += `${i === 0 ? "M" : "L"}${x(b.t).toFixed(1)},${y(b[klicPrumeru]).toFixed(1)}`;
  }
  return d;
}

function cestaPasma(body, x, y, klicMin, klicMax) {
  if (!body.length) return "";
  let nahoru = "";
  let dolu = "";
  for (let i = 0; i < body.length; i++) {
    const b = body[i];
    const px = x(b.t).toFixed(1);
    nahoru += `${i === 0 ? "M" : "L"}${px},${y(b[klicMax]).toFixed(1)}`;
    const z = body[body.length - 1 - i];
    dolu += `L${x(z.t).toFixed(1)},${y(z[klicMin]).toFixed(1)}`;
  }
  return `${nahoru}${dolu}Z`;
}

export default function GrafPrubehu({ data, popisRoku }) {
  const obalRef = useRef(null);
  const sirka = useSirka(obalRef);
  const n = data.pocet;
  const zaklad = useMemo(() => new Date(data.od).getTime(), [data.od]);
  const intervalMin = data.interval_min || 15;
  const naDen = Math.max(1, Math.round(1440 / intervalMin));

  const [rozsah, setRozsah] = useState({ od: 0, do: n });
  const [serie, setSerie] = useState({ bez: true, baterie: true, soc: true });
  const [kategorie, setKategorie] = useState({ spicka: true, sedlo: false, baterie: true, prekroceni: true });
  const [vybranaUdalost, setVybranaUdalost] = useState(null);
  const [kurzor, setKurzor] = useState(null); // {x, bod}
  const [tah, setTah] = useState(null); // probíhající výběr/posun myší

  // Nová data (jiná varianta nebo rok) = zpět na celoroční pohled.
  useEffect(() => {
    setRozsah({ od: 0, do: n });
    setVybranaUdalost(null);
  }, [data, n]);

  const { od, do: doIdx } = rozsah;
  const { krok, body } = useMemo(() => agreguj(data, od, doIdx, CIL_BODU), [data, od, doIdx]);

  // --- geometrie
  const vyskaBaterie = serie.baterie ? V_BATERIE : 0;
  const vyskaSoc = serie.soc ? V_SOC : 0;
  const yHlavni = OKRAJ.t;
  const yBaterie = yHlavni + V_HLAVNI + MEZERA;
  const ySoc = yBaterie + vyskaBaterie + (serie.baterie ? MEZERA : 0);
  const yOsa = ySoc + vyskaSoc + (serie.soc ? MEZERA : 0);
  const yPrehled = yOsa + V_OSA + MEZERA;
  const vyska = yPrehled + V_PREHLED + 4;
  const x0 = OKRAJ.l;
  const x1 = Math.max(x0 + 60, sirka - OKRAJ.r);
  const sirkaGrafu = x1 - x0;

  const tOd = data.casy_min[od] ?? 0;
  const tDo = data.casy_min[Math.min(n - 1, doIdx - 1)] ?? 1;
  const rozpetiT = Math.max(1, tDo - tOd);
  const x = useCallback((t) => x0 + ((t - tOd) / rozpetiT) * sirkaGrafu, [x0, tOd, rozpetiT, sirkaGrafu]);

  // Osa Y hlavního pásu: přizpůsobí se výřezu (jinak by detail v sedle byl
  // slepený u nuly), vždy ale obsáhne referenční čáry, pokud do rozsahu patří.
  const ref_ = data.referencni || {};
  const maxViditelny = useMemo(() => {
    let m = 0;
    for (const b of body) {
      if (b.oMax > m) m = b.oMax;
      if (b.sMax > m) m = b.sMax;
    }
    for (const u of data.useky_stropu || []) {
      if (u.do_index >= od && u.od_index < doIdx && u.strop_kw > m) m = u.strop_kw;
    }
    if (ref_.rk_soucasna_kw && ref_.rk_soucasna_kw > m && ref_.rk_soucasna_kw < m * 1.6) m = ref_.rk_soucasna_kw;
    return m || 1;
  }, [body, data.useky_stropu, od, doIdx, ref_.rk_soucasna_kw]);
  const yMax = maxViditelny * 1.08;
  const yH = useCallback((v) => yHlavni + V_HLAVNI - (v / yMax) * V_HLAVNI, [yHlavni, yMax]);

  // Osa baterie je symetrická kolem nuly – ať je vidět poměr nabíjení/vybíjení.
  const maxBaterie = useMemo(() => {
    let m = 0.001;
    for (const b of body) m = Math.max(m, Math.abs(b.bMax), Math.abs(b.bMin));
    return m;
  }, [body]);
  const yB = useCallback(
    (v) => yBaterie + vyskaBaterie / 2 - (v / (maxBaterie * 1.1)) * (vyskaBaterie / 2),
    [yBaterie, vyskaBaterie, maxBaterie]
  );
  const yS = useCallback((v) => ySoc + vyskaSoc - (v / 100) * vyskaSoc, [ySoc, vyskaSoc]);

  // --- pohyb v grafu
  const nastavRozsah = useCallback(
    (a, b) => {
      let novyOd = Math.max(0, Math.round(a));
      let novyDo = Math.min(n, Math.round(b));
      if (novyDo - novyOd < MIN_INTERVALU) {
        const stred = (novyOd + novyDo) / 2;
        novyOd = Math.max(0, Math.round(stred - MIN_INTERVALU / 2));
        novyDo = Math.min(n, novyOd + MIN_INTERVALU);
        novyOd = Math.max(0, novyDo - MIN_INTERVALU);
      }
      setRozsah({ od: novyOd, do: novyDo });
    },
    [n]
  );

  const oknoKolem = useCallback(
    (stred, sirkaIntervalu) => {
      const s = Math.min(n, Math.max(MIN_INTERVALU, Math.round(sirkaIntervalu)));
      let a = Math.round(stred - s / 2);
      a = Math.max(0, Math.min(n - s, a));
      nastavRozsah(a, a + s);
    },
    [n, nastavRozsah]
  );

  // Pixel → index intervalu (přes čas, kvůli případným dírám v profilu).
  const indexZX = useCallback(
    (px) => {
      const t = tOd + ((px - x0) / sirkaGrafu) * rozpetiT;
      // binární hledání nejbližšího času
      let lo = 0;
      let hi = n - 1;
      while (lo < hi) {
        const s = (lo + hi) >> 1;
        if (data.casy_min[s] < t) lo = s + 1;
        else hi = s;
      }
      return Math.max(od, Math.min(doIdx - 1, lo));
    },
    [tOd, x0, sirkaGrafu, rozpetiT, n, data.casy_min, od, doIdx]
  );

  // Kolečko myši = zoom k pozici kurzoru. Nativní posluchač kvůli passive:false
  // (jinak by React nedovolil zrušit rolování stránky).
  const plochaRef = useRef(null);
  useEffect(() => {
    const el = plochaRef.current;
    if (!el) return undefined;
    const naKolecko = (e) => {
      e.preventDefault();
      // Souřadnice se počítají vůči obalu (SVG kreslíme 1:1 v px od jeho
      // levého okraje), ne vůči obdélníku, na kterém událost visí.
      const box = obalRef.current.getBoundingClientRect();
      const px = e.clientX - box.left;
      const podil = Math.max(0, Math.min(1, (px - x0) / sirkaGrafu));
      const sirkaOkna = doIdx - od;
      const faktor = e.deltaY > 0 ? 1.35 : 1 / 1.35;
      const nova = Math.max(MIN_INTERVALU, Math.min(n, sirkaOkna * faktor));
      const stred = od + podil * sirkaOkna;
      nastavRozsah(stred - podil * nova, stred + (1 - podil) * nova);
    };
    el.addEventListener("wheel", naKolecko, { passive: false });
    return () => el.removeEventListener("wheel", naKolecko);
  }, [x0, sirkaGrafu, od, doIdx, n, nastavRozsah]);

  // Pozice myši v souřadnicích SVG = odsazení od levého okraje obalu.
  function myšX(e) {
    const box = obalRef.current.getBoundingClientRect();
    return e.clientX - box.left;
  }

  function zacniTah(e) {
    const px = myšX(e);
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setTah({ rezim: e.shiftKey || e.button === 1 ? "posun" : "vyber", x0: px, x: px, od, do: doIdx });
  }

  function pokracujTah(e) {
    const px = myšX(e);
    if (tah) {
      if (tah.rezim === "posun") {
        const sirkaOkna = tah.do - tah.od;
        const posun = ((tah.x0 - px) / sirkaGrafu) * sirkaOkna;
        let a = Math.max(0, Math.min(n - sirkaOkna, Math.round(tah.od + posun)));
        setRozsah({ od: a, do: a + sirkaOkna });
      } else {
        setTah({ ...tah, x: px });
      }
      return;
    }
    // Bez tažení jen crosshair + bublina s hodnotami.
    if (px < x0 || px > x1) {
      setKurzor(null);
      return;
    }
    const i = indexZX(px);
    const bod = body.find((b) => i >= b.i0 && i <= b.i1) || body[body.length - 1];
    setKurzor({ px, i, bod });
  }

  function ukonciTah(e) {
    if (tah && tah.rezim === "vyber") {
      const a = Math.min(tah.x0, tah.x);
      const b = Math.max(tah.x0, tah.x);
      if (b - a > 5) nastavRozsah(indexZX(a), indexZX(b) + 1);
    }
    setTah(null);
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }

  function oddal() {
    const sirkaOkna = doIdx - od;
    const stred = (od + doIdx) / 2;
    oknoKolem(stred, sirkaOkna * 2.5);
  }

  const stredAktualni = (od + doIdx) / 2;
  const UROVNE = [
    { nazev: "Rok", intervalu: n },
    { nazev: "Měsíc", intervalu: naDen * 30 },
    { nazev: "Týden", intervalu: naDen * 7 },
    { nazev: "Den", intervalu: naDen },
    { nazev: "6 hodin", intervalu: Math.round(naDen / 4) },
    { nazev: `${intervalMin} min`, intervalu: MIN_INTERVALU },
  ];

  function posun(smer) {
    const sirkaOkna = doIdx - od;
    const krokPosunu = Math.max(1, Math.round(sirkaOkna * 0.8)) * smer;
    let a = Math.max(0, Math.min(n - sirkaOkna, od + krokPosunu));
    setRozsah({ od: a, do: a + sirkaOkna });
  }

  function skocNaUdalost(u) {
    setVybranaUdalost(u);
    // Kolem události ukážeme ±půl dne, ať je vidět kontext špičky.
    oknoKolem(u.index, naDen);
  }

  // --- statické vrstvy grafu (memoizované, ať tooltip nepřekresluje cesty)
  const kresba = useMemo(() => {
    const tickyY = ticky(0, yMax, 4);
    const tickyCasu = osaCasu(zaklad, tOd, tDo);
    const useky = (data.useky_stropu || []).filter((u) => u.do_index >= od && u.od_index < doIdx);
    return (
      <>
        {/* vodorovná mřížka + popisky kW */}
        {tickyY.map((t) => (
          <g key={`y${t}`}>
            <line x1={x0} y1={yH(t)} x2={x1} y2={yH(t)} stroke="var(--c-grid)" strokeWidth="1" />
            <text x={x0 - 8} y={yH(t) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">
              {Math.round(t)}
            </text>
          </g>
        ))}
        {/* svislá mřížka + popisky času */}
        {tickyCasu.map((t) => (
          <g key={`x${t.t}`}>
            <line
              x1={x(t.t)} y1={yHlavni} x2={x(t.t)} y2={yOsa}
              stroke="var(--c-grid)" strokeWidth="1"
            />
            <text x={x(t.t)} y={yOsa + 13} textAnchor="middle" fontSize="10" fill="var(--muted)">
              {t.popis}
            </text>
          </g>
        ))}

        {/* odběr bez baterie – co by teklo ze sítě dnes */}
        {serie.bez && (
          <>
            <path d={cestaPasma(body, x, yH, "oMin", "oMax")} fill="var(--c-before)" opacity="0.35" />
            <path
              d={cestaNitky(body, x, yH, "oPrum")}
              fill="none" stroke="var(--c-before)" strokeWidth="1.2"
              strokeLinejoin="round" strokeLinecap="round"
            />
          </>
        )}

        {/* odběr ze sítě po instalaci baterie – hlavní nitka */}
        <path d={cestaPasma(body, x, yH, "sMin", "sMax")} fill="var(--c-after)" opacity="0.18" />
        <path
          d={cestaNitky(body, x, yH, "sPrum")}
          fill="none" stroke="var(--c-after)" strokeWidth="1.6"
          strokeLinejoin="round" strokeLinecap="round"
        />

        {/* strop, který baterie drží (v modelu 2027 se mění po měsících) */}
        {useky.map((u, i) => (
          <line
            key={`s${i}`}
            x1={x(data.casy_min[Math.max(u.od_index, od)])}
            x2={x(data.casy_min[Math.min(u.do_index, doIdx - 1)])}
            y1={yH(u.strop_kw)} y2={yH(u.strop_kw)}
            stroke="var(--c-axis)" strokeWidth="1" strokeDasharray="2 3" opacity="0.55"
          />
        ))}

        {/* referenční čáry rezervace */}
        {[
          { v: ref_.rk_soucasna_kw, barva: "var(--c-refnow)", popis: ref_.popisek_soucasna },
          { v: ref_.rk_nova_kw, barva: "var(--c-refnew)", popis: ref_.popisek_nova },
        ]
          .filter((r) => r.v != null && r.v <= yMax)
          .map((r) => (
            <g key={r.popis}>
              <line x1={x0} y1={yH(r.v)} x2={x1} y2={yH(r.v)} stroke={r.barva} strokeWidth="1.5" strokeDasharray="5 3" />
              <text x={x1 - 4} y={yH(r.v) - 4} textAnchor="end" fontSize="10" fontWeight="600" fill={r.barva}>
                {r.popis} {Math.round(r.v)} kW
              </text>
            </g>
          ))}

        {/* pás výkonu baterie: nad nulou vybíjení, pod nulou nabíjení */}
        {serie.baterie && (
          <>
            <line x1={x0} y1={yB(0)} x2={x1} y2={yB(0)} stroke="var(--c-grid)" strokeWidth="1" />
            <path
              d={`${cestaPasma(body, x, yB, "bMin", "bMax")}`}
              fill="var(--brand)" opacity="0.16"
            />
            <path
              d={cestaNitky(body, x, yB, "bPrum")}
              fill="none" stroke="var(--brand)" strokeWidth="1.3" strokeLinejoin="round"
            />
            <text x={x0 - 8} y={yB(maxBaterie * 1.1) + 9} textAnchor="end" fontSize="9" fill="var(--muted)">
              {Math.round(maxBaterie)}
            </text>
            <text x={x0 - 8} y={yB(0) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">0</text>
            <text x={x0 - 8} y={yB(-maxBaterie * 1.1) - 2} textAnchor="end" fontSize="9" fill="var(--muted)">
              −{Math.round(maxBaterie)}
            </text>
          </>
        )}

        {/* pás stavu nabití */}
        {serie.soc && (
          <>
            <line x1={x0} y1={yS(0)} x2={x1} y2={yS(0)} stroke="var(--c-grid)" strokeWidth="1" />
            <path
              d={`${cestaNitky(body, x, yS, "cPrum")}L${x(body[body.length - 1]?.t ?? tDo)},${yS(0)}L${x(body[0]?.t ?? tOd)},${yS(0)}Z`}
              fill="var(--c-refnew)" opacity="0.14"
            />
            <path
              d={cestaNitky(body, x, yS, "cPrum")}
              fill="none" stroke="var(--c-refnew)" strokeWidth="1.3" strokeLinejoin="round"
            />
            <text x={x0 - 8} y={yS(100) + 9} textAnchor="end" fontSize="9" fill="var(--muted)">100 %</text>
            <text x={x0 - 8} y={yS(0) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">0</text>
          </>
        )}
      </>
    );
  }, [
    body, data.useky_stropu, data.casy_min, od, doIdx, serie.bez, serie.baterie, serie.soc,
    x, yH, yB, yS, x0, x1, yHlavni, yOsa, yMax, maxBaterie, zaklad, tOd, tDo,
    ref_.rk_soucasna_kw, ref_.rk_nova_kw, ref_.popisek_soucasna, ref_.popisek_nova,
  ]);

  // Přehledová lišta: celý rok v malém + výřez, který je teď vidět.
  const prehled = useMemo(() => {
    const { body: hrube } = agreguj(data, 0, n, Math.max(120, Math.round(sirkaGrafu / 3)));
    let m = 1;
    for (const b of hrube) m = Math.max(m, b.oMax);
    const xp = (i) => x0 + (i / Math.max(1, n - 1)) * sirkaGrafu;
    const yp = (v) => yPrehled + V_PREHLED - (v / (m * 1.05)) * V_PREHLED;
    let d = "";
    for (let i = 0; i < hrube.length; i++) {
      d += `${i === 0 ? "M" : "L"}${xp(hrube[i].i0).toFixed(1)},${yp(hrube[i].oMax).toFixed(1)}`;
    }
    d += `L${xp(n - 1).toFixed(1)},${yp(0)}L${xp(0).toFixed(1)},${yp(0)}Z`;
    return { d, xp };
  }, [data, n, sirkaGrafu, x0, yPrehled]);

  const viditelneUdalosti = (data.udalosti || []).filter(
    (u) => kategorie[u.kategorie] && u.index >= od && u.index < doIdx
  );
  const seznamUdalosti = (data.udalosti || []).filter((u) => kategorie[u.kategorie]);

  const jednotkaKose = krok === 1
    ? `${intervalMin} min (přesné hodnoty)`
    : krok < 4 ? `${krok * intervalMin} min`
    : krok < naDen ? `${(krok * intervalMin / 60).toFixed(krok * intervalMin % 60 ? 1 : 0)} h`
    : `${(krok / naDen).toFixed(krok % naDen ? 1 : 0)} dne`;

  const casOd = new Date(zaklad + tOd * 60000);
  const casDo = new Date(zaklad + tDo * 60000);

  return (
    <div>
      {/* ovládání */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fm-muted)" }}>Přiblížení</span>
        {UROVNE.map((u) => (
          <button
            key={u.nazev}
            className="fm-btn"
            style={{ padding: "3px 9px", fontSize: 11 }}
            aria-pressed={Math.abs(doIdx - od - u.intervalu) < Math.max(2, u.intervalu * 0.15)}
            onClick={() => (u.intervalu >= n ? setRozsah({ od: 0, do: n }) : oknoKolem(stredAktualni, u.intervalu))}
          >
            {u.nazev}
          </button>
        ))}
        <span style={{ display: "inline-flex", gap: 4, marginLeft: 4 }}>
          <button className="fm-btn" style={{ padding: "3px 9px", fontSize: 11 }} onClick={() => posun(-1)} title="O výřez zpět">←</button>
          <button className="fm-btn" style={{ padding: "3px 9px", fontSize: 11 }} onClick={() => posun(1)} title="O výřez vpřed">→</button>
          <button className="fm-btn" style={{ padding: "3px 9px", fontSize: 11 }} onClick={oddal} title="Oddálit">−</button>
          <button className="fm-btn" style={{ padding: "3px 9px", fontSize: 11 }} onClick={() => setRozsah({ od: 0, do: n })}>Celý rok</button>
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, fontSize: 11, marginBottom: 6 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <input type="checkbox" checked={serie.bez} onChange={(e) => setSerie((s) => ({ ...s, bez: e.target.checked }))} />
          <span style={{ display: "inline-block", width: 12, height: 3, background: "var(--c-before)" }} /> odběr bez baterie
        </label>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ display: "inline-block", width: 12, height: 3, background: "var(--c-after)" }} /> odběr ze sítě s baterií
        </span>
        <label style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <input type="checkbox" checked={serie.baterie} onChange={(e) => setSerie((s) => ({ ...s, baterie: e.target.checked }))} />
          <span style={{ display: "inline-block", width: 12, height: 3, background: "var(--brand)" }} /> výkon baterie (+ vybíjí / − nabíjí)
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <input type="checkbox" checked={serie.soc} onChange={(e) => setSerie((s) => ({ ...s, soc: e.target.checked }))} />
          <span style={{ display: "inline-block", width: 12, height: 3, background: "var(--c-refnew)" }} /> stav nabití
        </label>
      </div>

      <div ref={obalRef} style={{ position: "relative", width: "100%" }}>
        <svg
          width={sirka}
          height={vyska}
          style={{ display: "block", touchAction: "none", userSelect: "none" }}
          role="img"
          aria-label="Průběh odběru a činnosti baterie v čase"
        >
          {kresba}

          {/* značky událostí v aktuálním výřezu */}
          {viditelneUdalosti.map((u, i) => {
            const px = x(data.casy_min[u.index]);
            const hodnota = u.jednotka === "kW" ? u.hodnota : data.site_kw[u.index];
            const py = yH(hodnota);
            const vybrana = vybranaUdalost && vybranaUdalost.index === u.index && vybranaUdalost.typ === u.typ;
            const popisek = vybrana || viditelneUdalosti.length <= 6;
            return (
              <g key={`u${i}`} style={{ cursor: "pointer" }} onClick={() => setVybranaUdalost(u)}>
                <circle cx={px} cy={py} r={vybrana ? 5 : 3.2} fill={barvaKategorie(u.kategorie)} stroke="var(--surface, #fff)" strokeWidth="1" />
                {popisek && (
                  <text
                    x={px} y={py - 9} textAnchor={px > x1 - 90 ? "end" : px < x0 + 90 ? "start" : "middle"}
                    fontSize="10" fontWeight="600" fill={barvaKategorie(u.kategorie)}
                  >
                    {u.jednotka === "kW" ? fmtKw(u.hodnota, 0) : `${u.hodnota} ${u.jednotka}`}
                  </text>
                )}
              </g>
            );
          })}

          {/* crosshair */}
          {kurzor && !tah && (
            <line x1={kurzor.px} y1={yHlavni} x2={kurzor.px} y2={yOsa} stroke="var(--c-axis)" strokeWidth="1" opacity="0.45" />
          )}

          {/* rámeček táhnutého výběru */}
          {tah && tah.rezim === "vyber" && Math.abs(tah.x - tah.x0) > 2 && (
            <rect
              x={Math.min(tah.x0, tah.x)} y={yHlavni} width={Math.abs(tah.x - tah.x0)} height={yOsa - yHlavni}
              fill="var(--brand)" opacity="0.16" stroke="var(--brand)" strokeWidth="1"
            />
          )}

          {/* interaktivní plocha (zoom kolečkem, výběr tažením, posun se Shiftem) */}
          <rect
            ref={plochaRef}
            x={x0} y={yHlavni} width={sirkaGrafu} height={yOsa - yHlavni}
            fill="transparent"
            style={{ cursor: tah?.rezim === "posun" ? "grabbing" : "crosshair" }}
            onPointerDown={zacniTah}
            onPointerMove={pokracujTah}
            onPointerUp={ukonciTah}
            onPointerLeave={() => setKurzor(null)}
            onDoubleClick={oddal}
          />

          {/* přehledová lišta s výřezem */}
          <path d={prehled.d} fill="var(--c-before)" opacity="0.5" />
          <rect
            x={prehled.xp(od)} y={yPrehled}
            width={Math.max(2, prehled.xp(doIdx - 1) - prehled.xp(od))} height={V_PREHLED}
            fill="var(--brand)" opacity="0.18" stroke="var(--brand)" strokeWidth="1"
          />
          <rect
            x={x0} y={yPrehled} width={sirkaGrafu} height={V_PREHLED}
            fill="transparent" style={{ cursor: "pointer" }}
            onPointerDown={(e) => {
              const px = myšX(e);
              const podil = Math.max(0, Math.min(1, (px - x0) / sirkaGrafu));
              oknoKolem(podil * n, doIdx - od);
            }}
          />
          <text x={x0} y={yPrehled - 3} fontSize="9" fill="var(--muted)">
            celý rok – klikni pro přesun výřezu
          </text>
        </svg>

        {/* bublina s hodnotami pod kurzorem */}
        {kurzor && !tah && (
          <div
            style={{
              position: "absolute",
              left: Math.min(Math.max(kurzor.px + 12, 0), Math.max(0, sirka - 210)),
              top: yHlavni + 6,
              width: 198,
              background: "var(--surface, #fff)",
              border: "1px solid var(--line)",
              borderRadius: 8,
              padding: "6px 8px",
              fontSize: 11,
              lineHeight: 1.5,
              pointerEvents: "none",
              boxShadow: "0 6px 18px rgba(0,0,0,.12)",
            }}
          >
            <div style={{ fontWeight: 700, marginBottom: 2 }}>
              {fmtCas(new Date(zaklad + data.casy_min[kurzor.i] * 60000), true)}
            </div>
            <div style={{ color: "var(--fm-muted)" }}>
              {krok === 1 ? "přesná čtvrthodina" : `koš ${jednotkaKose} – min/⌀/max`}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>ze sítě</span>
              <b>{krok === 1 ? fmtKw(data.site_kw[kurzor.i]) : `${Math.round(kurzor.bod.sMin)} / ${Math.round(kurzor.bod.sPrum)} / ${Math.round(kurzor.bod.sMax)} kW`}</b>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fm-muted)" }}>
              <span>bez baterie</span>
              <span>{krok === 1 ? fmtKw(data.odber_kw[kurzor.i]) : `${Math.round(kurzor.bod.oMin)} / ${Math.round(kurzor.bod.oPrum)} / ${Math.round(kurzor.bod.oMax)} kW`}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>baterie</span>
              <b style={{ color: data.baterie_kw[kurzor.i] > 0 ? "var(--brand)" : "var(--c-export)" }}>
                {krok === 1
                  ? data.baterie_kw[kurzor.i] === 0
                    ? "stojí"
                    : `${data.baterie_kw[kurzor.i] > 0 ? "vybíjí" : "nabíjí"} ${fmtKw(Math.abs(data.baterie_kw[kurzor.i]))}`
                  : `${Math.round(kurzor.bod.bMin)} … ${Math.round(kurzor.bod.bMax)} kW`}
              </b>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>stav nabití</span>
              <span>{Math.round(krok === 1 ? data.soc_pct[kurzor.i] : kurzor.bod.cPrum)} %</span>
            </div>
          </div>
        )}
      </div>

      <div style={{ fontSize: 11, color: "var(--fm-muted)", margin: "4px 0 10px" }}>
        Zobrazeno {fmtCas(casOd)} – {fmtCas(casDo)} ({(doIdx - od).toLocaleString("cs-CZ")} intervalů,
        jeden bod = {jednotkaKose}). Kolečkem myši přiblížíš, tažením vybereš výsek,
        se Shiftem posuneš, dvojklikem oddálíš.
      </div>

      {/* události */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fm-muted)" }}>Události</span>
        {KATEGORIE.map((k) => (
          <button
            key={k.klic}
            className="fm-btn"
            aria-pressed={!!kategorie[k.klic]}
            onClick={() => setKategorie((s) => ({ ...s, [k.klic]: !s[k.klic] }))}
            style={{
              padding: "3px 9px", fontSize: 11,
              color: kategorie[k.klic] ? k.barva : "var(--fm-muted)",
              fontWeight: kategorie[k.klic] ? 700 : 400,
            }}
          >
            ● {k.nazev}
          </button>
        ))}
      </div>
      <div className="nb-scroll" style={{ maxHeight: 168, overflowY: "auto", border: "1px solid var(--line)", borderRadius: 9 }}>
        <table className="nb-table">
          <tbody>
            {seznamUdalosti.map((u, i) => {
              const vybrana = vybranaUdalost && vybranaUdalost.index === u.index && vybranaUdalost.typ === u.typ;
              return (
                <tr
                  key={`${u.typ}-${u.index}-${i}`}
                  onClick={() => skocNaUdalost(u)}
                  title="Kliknutím se graf přiblíží na tenhle okamžik"
                  style={{
                    cursor: "pointer",
                    ...(vybrana ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" } : {}),
                  }}
                >
                  <td style={{ width: 18, color: barvaKategorie(u.kategorie) }}>●</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {u.mesic ? `${MESICE_ZKR[u.mesic - 1]} · ` : ""}
                    {fmtCas(new Date(zaklad + data.casy_min[u.index] * 60000), true)}
                  </td>
                  <td>{u.popis}</td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <b>{u.jednotka === "kW" ? fmtKw(u.hodnota) : `${u.hodnota} ${u.jednotka}`}</b>
                  </td>
                </tr>
              );
            })}
            {seznamUdalosti.length === 0 && (
              <tr><td style={{ color: "var(--fm-muted)" }}>Vyber aspoň jednu kategorii událostí.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {popisRoku && (
        <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 6 }}>{popisRoku}</div>
      )}
    </div>
  );
}
