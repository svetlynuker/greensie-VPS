// Nitkový graf průběhu peak shavingu: celý rok po 15 minutách, se zoomem od
// přehledu měsíců až na jednotlivé čtvrthodiny. Ukazuje, co se v odběrném
// místě opravdu děje – kolik teče ze sítě, kdy baterie kryje špičku, kdy se
// dobíjí a jak jí přitom klesá stav nabití.
//
// Bez grafové knihovny (projekt žádnou nemá). Kreslí se ve dvou vrstvách:
//  - <canvas> = datové řady (nitky + pásma min–max, mřížka). Dřív to bylo
//    v SVG, jenže jedno překreslení znamenalo předat prohlížeči ~150 kB textu
//    cest k naparsování a rasterizaci – při zoomu a posunu to znatelně
//    zadrhávalo. Canvas kreslí ty samé body řádově rychleji.
//  - <svg> nad ním = popisky os, referenční čáry, značky událostí, kříž
//    kurzoru a interaktivní plochy. Textu je málo, zůstává ostrý a vybíratelný.
//
// Barvy se berou z CSS tokenů --c-* (canvas si je musí přečíst přes
// getComputedStyle) a přečtou se znovu při přepnutí tmavého režimu i
// kompenzace červeno-zelené vady.
//
// Plynulost: všechny vstupy (kolečko, tažení, pohyb myši) se slévají do
// jednoho překreslení na snímek (requestAnimationFrame), takže ani 120 událostí
// za sekundu neudělá 120 překreslení.
//
// Jak je vyřešený objem dat: backend pošle celoroční řady (~35 000 hodnot),
// komponenta si je při každé změně přiblížení slije do košů (jeden na pixel
// šířky) a z každého kreslí pásmo min–max + průměrovou nitku. Špička tak nikdy
// nezmizí zaokrouhlením (což by u peak shavingu byla fatální lež) a při plném
// přiblížení (koš = 1 interval) pásmo splyne s nitkou a vidíš přesné
// čtvrthodinové hodnoty.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  DNY_ZKR,
  MESICE_ZKR,
  agreguj,
  dvojcifernne,
  kresliData,
  kresliPrehled,
  osaCasu,
  ticky,
} from "./grafPrubehuData";

// Nejmenší možný výřez (4 intervaly = 1 hodina), ať se zoom nezacyklí.
const MIN_INTERVALU = 4;

// Strop počtu košů. Víc než jeden bod na pixel nemá co zobrazit.
const MAX_KOSU = 1400;

const KATEGORIE = [
  { klic: "spicka", nazev: "Špičky", token: "--st-serious" },
  { klic: "sedlo", nazev: "Sedla", token: "--c-export" },
  { klic: "baterie", nazev: "Baterie", token: "--brand" },
  { klic: "prekroceni", nazev: "Překročení", token: "--st-crit" },
];

// Tokeny, které canvas potřebuje jako konkrétní barvy. Výchozí hodnoty
// odpovídají světlému motivu – použijí se jen do prvního načtení stylů.
const TOKENY = {
  before: ["--c-before", "#c4cdc7"],
  after: ["--c-after", "#2f9e44"],
  brand: ["--brand", "#2f9e44"],
  refnew: ["--c-refnew", "#d97706"],
  grid: ["--c-grid", "#e9edea"],
  // Spotová cena – modrá jako „export/trh", ať se nemíchá se zelenou (odběr)
  // ani oranžovou (stav nabití).
  cena: ["--c-export", "#1971c2"],
  spicka: ["--st-serious", "#d1652f"],
  sedlo: ["--c-export", "#1971c2"],
  prekroceni: ["--st-crit", "#d03b3b"],
};

function fmtKw(v, des = 1) {
  return `${Number(v).toLocaleString("cs-CZ", { maximumFractionDigits: des })} kW`;
}

function fmtCas(d, sDnem = false) {
  const den = `${d.getDate()}.${d.getMonth() + 1}.`;
  const cas = `${dvojcifernne(d.getHours())}:${dvojcifernne(d.getMinutes())}`;
  return sDnem ? `${DNY_ZKR[d.getDay()]} ${den} ${cas}` : `${den} ${cas}`;
}

// --------------------------------------------------------------- pomůcky
// Šířka kontejneru (kreslíme v pixelech 1:1, ať se nedeformují popisky).
function useSirka(ref, vychozi = 900) {
  const [sirka, setSirka] = useState(vychozi);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const zmer = () => setSirka(Math.max(300, el.clientWidth));
    zmer();
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(zmer);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return sirka;
}

// Barvy z CSS tokenů pro canvas (SVG si je bere samo). Přečtou se znovu při
// přepnutí tmavého režimu i kompenzace červeno-zelené vady.
function useBarvy(ref) {
  const [barvy, setBarvy] = useState(() =>
    Object.fromEntries(Object.entries(TOKENY).map(([k, [, zaloha]]) => [k, zaloha]))
  );
  useLayoutEffect(() => {
    const nacti = () => {
      const styl = getComputedStyle(ref.current || document.documentElement);
      const nove = {};
      for (const [klic, [token, zaloha]] of Object.entries(TOKENY)) {
        nove[klic] = styl.getPropertyValue(token).trim() || zaloha;
      }
      setBarvy((s) => (Object.keys(nove).every((k) => nove[k] === s[k]) ? s : nove));
    };
    nacti();
    const mo = new MutationObserver(nacti);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-cvd"] });
    return () => mo.disconnect();
  }, [ref]);
  return barvy;
}

// Slévá rychlé vstupy (kolečko, tažení, pohyb myši) do jednoho překreslení na
// snímek – jinak by 120 událostí za sekundu dělalo 120 překreslení.
function usePoSnimcich() {
  const cekajici = useRef(null);
  const snimek = useRef(0);
  useEffect(() => () => {
    if (snimek.current) cancelAnimationFrame(snimek.current);
  }, []);
  return useCallback((fn) => {
    cekajici.current = fn;
    if (snimek.current) return;
    snimek.current = requestAnimationFrame(() => {
      snimek.current = 0;
      const f = cekajici.current;
      cekajici.current = null;
      if (f) f();
    });
  }, []);
}

// `popisDruheSerie` – co je druhá složka výkonu baterie vedle srážení špičky.
// U peak shavingu je to obchod na spotu, u PPA + BESS ukládání přebytku
// z elektrárny; komponenta je jinak stejná, takže se popisek jen předá.
export default function GrafPrubehu({ data, popisRoku, popisDruheSerie = "obchod" }) {
  const obalRef = useRef(null);
  const canvasRef = useRef(null);
  const prehledCanvasRef = useRef(null);
  const koseRef = useRef(null);
  const prehledKoseRef = useRef(null);
  const sirka = useSirka(obalRef);
  const barvy = useBarvy(obalRef);
  const poSnimcich = usePoSnimcich();

  const n = data.pocet;
  const zaklad = useMemo(() => new Date(data.od).getTime(), [data.od]);
  const intervalMin = data.interval_min || 15;
  const naDen = Math.max(1, Math.round(1440 / intervalMin));
  const uzky = sirka < 620;

  const [rozsah, setRozsah] = useState({ od: 0, do: n });
  const [serie, setSerie] = useState({ bez: true, baterie: true, soc: true, cena: true });
  const [kategorie, setKategorie] = useState({ spicka: true, sedlo: false, baterie: true, prekroceni: true });
  const [vybranaUdalost, setVybranaUdalost] = useState(null);
  const [kurzor, setKurzor] = useState(null);
  const [tah, setTah] = useState(null);

  useEffect(() => {
    setRozsah({ od: 0, do: n });
    setVybranaUdalost(null);
  }, [data, n]);

  const { od, do: doIdx } = rozsah;

  // --- geometrie (na úzkém displeji nižší pásy a menší okraje)
  const OKRAJ = { l: uzky ? 40 : 56, r: uzky ? 10 : 16, t: 12 };
  const V_HLAVNI = uzky ? 186 : 260;
  const V_BATERIE = serie.baterie ? (uzky ? 74 : 104) : 0;
  const V_SOC = serie.soc ? (uzky ? 48 : 66) : 0;
  // Cenový pás má smysl jen v obchodních režimech – bez cen v datech se vůbec
  // nekreslí, takže čistý peak shaving vypadá stejně jako dřív.
  const maCenu = Array.isArray(data.cena_kc_mwh) && data.cena_kc_mwh.length === n;
  const V_CENA = maCenu && serie.cena ? (uzky ? 56 : 78) : 0;
  const V_PREHLED = uzky ? 32 : 42;
  const V_OSA = 20;
  const MEZERA = 8;

  const yHlavni = OKRAJ.t;
  const yBaterie = yHlavni + V_HLAVNI + MEZERA;
  const ySoc = yBaterie + V_BATERIE + (serie.baterie ? MEZERA : 0);
  const yCena = ySoc + V_SOC + (serie.soc ? MEZERA : 0);
  const yOsa = yCena + V_CENA + (V_CENA ? MEZERA : 0);
  const yPrehled = yOsa + V_OSA + MEZERA;
  const vyska = yPrehled + V_PREHLED + 4;
  const x0 = OKRAJ.l;
  const x1 = Math.max(x0 + 60, sirka - OKRAJ.r);
  const sirkaGrafu = x1 - x0;
  const cilKosu = Math.min(MAX_KOSU, Math.max(160, Math.round(sirkaGrafu)));

  const kose = useMemo(() => {
    koseRef.current = agreguj(data, od, doIdx, cilKosu, koseRef.current);
    // Mělká kopie: typovaná pole se recyklují (proto se nealokují), ale obal
    // musí mít pokaždé novou identitu, jinak by React neviděl změnu a canvas
    // by se nepřekreslil.
    return { ...koseRef.current };
  }, [data, od, doIdx, cilKosu]);
  const krok = kose.krok;

  const tOd = data.casy_min[od] ?? 0;
  const tDo = data.casy_min[Math.min(n - 1, doIdx - 1)] ?? 1;
  const rozpetiT = Math.max(1, tDo - tOd);
  const x = useCallback((t) => x0 + ((t - tOd) / rozpetiT) * sirkaGrafu, [x0, tOd, rozpetiT, sirkaGrafu]);

  // Osa Y hlavního pásu se přizpůsobí výřezu (jinak by detail v sedle byl
  // slepený u nuly), vždy ale obsáhne strop a smysluplné referenční čáry.
  const ref_ = data.referencni || {};
  const yMax = useMemo(() => {
    let m = 0;
    for (let i = 0; i < kose.pocet; i++) {
      if (kose.oMax[i] > m) m = kose.oMax[i];
      if (kose.sMax[i] > m) m = kose.sMax[i];
    }
    for (const u of data.useky_stropu || []) {
      if (u.do_index >= od && u.od_index < doIdx && u.strop_kw > m) m = u.strop_kw;
    }
    if (ref_.rk_soucasna_kw && ref_.rk_soucasna_kw > m && ref_.rk_soucasna_kw < m * 1.6) {
      m = ref_.rk_soucasna_kw;
    }
    return (m || 1) * 1.08;
  }, [kose, data.useky_stropu, od, doIdx, ref_.rk_soucasna_kw]);
  const yH = useCallback((v) => yHlavni + V_HLAVNI - (v / yMax) * V_HLAVNI, [yHlavni, V_HLAVNI, yMax]);

  // Osa baterie je symetrická kolem nuly – ať je vidět poměr nabíjení/vybíjení.
  const maxBaterie = useMemo(() => {
    let m = 0.001;
    for (let i = 0; i < kose.pocet; i++) {
      const a = Math.abs(kose.bMax[i]);
      const b = Math.abs(kose.bMin[i]);
      if (a > m) m = a;
      if (b > m) m = b;
    }
    return m;
  }, [kose]);
  const yB = useCallback(
    (v) => yBaterie + V_BATERIE / 2 - (v / (maxBaterie * 1.1)) * (V_BATERIE / 2),
    [yBaterie, V_BATERIE, maxBaterie]
  );
  const yS = useCallback((v) => ySoc + V_SOC - (v / 100) * V_SOC, [ySoc, V_SOC]);

  // Osa ceny musí zvládnout i zápornou spotovou cenu (v roce 2025 jich bylo
  // 323 hodin), takže se počítá z min i max výřezu, ne od nuly.
  const rozsahCeny = useMemo(() => {
    if (!V_CENA) return null;
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < kose.pocet; i++) {
      if (kose.pMin[i] < min) min = kose.pMin[i];
      if (kose.pMax[i] > max) max = kose.pMax[i];
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    const rezerva = Math.max(50, (max - min) * 0.08);
    return { min: Math.min(0, min) - rezerva, max: max + rezerva };
  }, [kose, V_CENA]);
  const yP = useCallback(
    (v) => {
      if (!rozsahCeny) return yCena;
      const podil = (v - rozsahCeny.min) / Math.max(1, rozsahCeny.max - rozsahCeny.min);
      return yCena + V_CENA - podil * V_CENA;
    },
    [rozsahCeny, yCena, V_CENA]
  );

  const tickyY = useMemo(() => ticky(0, yMax, uzky ? 3 : 4), [yMax, uzky]);
  const tickyCasu = useMemo(
    () => osaCasu(zaklad, tOd, tDo, uzky ? 0.5 : 1),
    [zaklad, tOd, tDo, uzky]
  );

  // --- překreslení canvasu (jen datové vrstvy; popisky řeší SVG nad ním)
  useLayoutEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    // Rozlišení kreslicí plochy podle hustoty displeje (CSS velikost drží
    // style prop) – jinak by graf byl na retina displeji rozmazaný.
    const w = Math.round(sirka * dpr);
    const h = Math.round(vyska * dpr);
    if (cv.width !== w || cv.height !== h) {
      cv.width = w;
      cv.height = h;
    }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    kresliData(ctx, {
      kose, x, yH, yB, yS, serie, barvy, sirka, vyska,
      yP: V_CENA ? yP : null,
      mrizka: {
        x0, x1, yOd: yHlavni, yDo: yOsa,
        vodorovne: tickyY.map(yH),
        svisle: tickyCasu.map((t) => x(t.t)),
      },
    });
  }, [kose, x, yH, yB, yS, yP, V_CENA, serie, barvy, sirka, vyska, x0, x1, yHlavni, yOsa, tickyY, tickyCasu]);

  // Přehledová lišta se počítá zvlášť – nemění se se zoomem, jen s daty a šířkou.
  const prehledKose = useMemo(() => {
    prehledKoseRef.current = agreguj(
      data, 0, n, Math.min(600, Math.max(120, Math.round(sirkaGrafu / 2))), prehledKoseRef.current
    );
    return { ...prehledKoseRef.current };
  }, [data, n, sirkaGrafu]);
  const xp = useCallback((i) => x0 + (i / Math.max(1, n - 1)) * sirkaGrafu, [x0, n, sirkaGrafu]);

  useLayoutEffect(() => {
    const cv = prehledCanvasRef.current;
    if (!cv) return;
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(sirka * dpr);
    const h = Math.round(V_PREHLED * dpr);
    if (cv.width !== w || cv.height !== h) {
      cv.width = w;
      cv.height = h;
    }
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    let max = 1;
    for (let i = 0; i < prehledKose.pocet; i++) max = Math.max(max, prehledKose.oMax[i]);
    kresliPrehled(ctx, {
      kose: prehledKose,
      xp,
      yp: (v) => V_PREHLED - (v / (max * 1.05)) * V_PREHLED,
      barva: barvy.before,
      y0: 0,
      vyskaPruhu: V_PREHLED,
      sirka,
    });
  }, [prehledKose, xp, sirka, V_PREHLED, barvy.before]);

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
      setRozsah((s) => (s.od === novyOd && s.do === novyDo ? s : { od: novyOd, do: novyDo }));
    },
    [n]
  );

  const oknoKolem = useCallback(
    (stred, sirkaIntervalu) => {
      const s = Math.min(n, Math.max(MIN_INTERVALU, Math.round(sirkaIntervalu)));
      const a = Math.max(0, Math.min(n - s, Math.round(stred - s / 2)));
      nastavRozsah(a, a + s);
    },
    [n, nastavRozsah]
  );

  // Pozice myši v souřadnicích kreslení = odsazení od levého okraje obalu.
  const myšX = useCallback((e) => {
    const box = obalRef.current.getBoundingClientRect();
    return e.clientX - box.left;
  }, []);

  // Pixel → index intervalu (přes čas, kvůli případným dírám v profilu).
  const indexZX = useCallback(
    (px) => {
      const t = tOd + ((px - x0) / sirkaGrafu) * rozpetiT;
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
  // (jinak by prohlížeč nedovolil zrušit rolování stránky).
  const plochaRef = useRef(null);
  const rozsahRef = useRef(rozsah);
  rozsahRef.current = rozsah;
  useEffect(() => {
    const el = plochaRef.current;
    if (!el) return undefined;
    const naKolecko = (e) => {
      e.preventDefault();
      const box = obalRef.current.getBoundingClientRect();
      const px = e.clientX - box.left;
      const podil = Math.max(0, Math.min(1, (px - x0) / sirkaGrafu));
      poSnimcich(() => {
        // Vychází se z posledního platného rozsahu, ne z toho, který byl
        // aktuální při navěšení posluchače – jinak by se rychlé otáčení
        // kolečkem počítalo pořád dokola ze stejného výřezu.
        const { od: a, do: b } = rozsahRef.current;
        const sirkaOkna = b - a;
        const faktor = e.deltaY > 0 ? 1.35 : 1 / 1.35;
        const nova = Math.max(MIN_INTERVALU, Math.min(n, sirkaOkna * faktor));
        const stred = a + podil * sirkaOkna;
        nastavRozsah(stred - podil * nova, stred + (1 - podil) * nova);
      });
    };
    el.addEventListener("wheel", naKolecko, { passive: false });
    return () => el.removeEventListener("wheel", naKolecko);
  }, [x0, sirkaGrafu, n, nastavRozsah, poSnimcich]);

  function zacniTah(e) {
    const px = myšX(e);
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setTah({ rezim: e.shiftKey || e.button === 1 ? "posun" : "vyber", x0: px, x: px, od, do: doIdx });
  }

  function pokracujTah(e) {
    const px = myšX(e);
    if (tah) {
      if (tah.rezim === "posun") {
        poSnimcich(() => {
          const sirkaOkna = tah.do - tah.od;
          const posun = ((tah.x0 - px) / sirkaGrafu) * sirkaOkna;
          const a = Math.max(0, Math.min(n - sirkaOkna, Math.round(tah.od + posun)));
          nastavRozsah(a, a + sirkaOkna);
        });
      } else {
        poSnimcich(() => setTah((s) => (s ? { ...s, x: px } : s)));
      }
      return;
    }
    if (px < x0 || px > x1) {
      setKurzor(null);
      return;
    }
    poSnimcich(() => {
      const i = indexZX(px);
      // Koš, do kterého index spadá (koše jsou stejně široké → přímý výpočet).
      const poradi = Math.max(0, Math.min(kose.pocet - 1, Math.floor((i - od) / kose.krok)));
      setKurzor({ px, i, poradi });
    });
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
    oknoKolem((od + doIdx) / 2, (doIdx - od) * 2.5);
  }

  function posun(smer) {
    const sirkaOkna = doIdx - od;
    const a = Math.max(0, Math.min(n - sirkaOkna, od + Math.max(1, Math.round(sirkaOkna * 0.8)) * smer));
    nastavRozsah(a, a + sirkaOkna);
  }

  function skocNaUdalost(u) {
    setVybranaUdalost(u);
    oknoKolem(u.index, naDen);
  }

  const UROVNE = [
    { nazev: "Rok", intervalu: n },
    { nazev: "Měsíc", intervalu: naDen * 30 },
    { nazev: "Týden", intervalu: naDen * 7 },
    { nazev: "Den", intervalu: naDen },
    { nazev: "6 hodin", intervalu: Math.round(naDen / 4) },
    { nazev: `${intervalMin} min`, intervalu: MIN_INTERVALU },
  ];

  // --- vrstvy SVG (memoizované, ať pohyb myši nepřekresluje popisky ani osy)
  const vrstvaOs = useMemo(() => {
    const useky = (data.useky_stropu || []).filter((u) => u.do_index >= od && u.od_index < doIdx);
    return (
      <>
        {tickyY.map((t) => (
          <text key={`y${t}`} x={x0 - 8} y={yH(t) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">
            {Math.round(t)}
          </text>
        ))}
        {tickyCasu.map((t) => (
          <text key={`x${t.t}`} x={x(t.t)} y={yOsa + 13} textAnchor="middle" fontSize="10" fill="var(--muted)">
            {t.popis}
          </text>
        ))}
        {useky.map((u, i) => (
          <line
            key={`s${i}`}
            x1={x(data.casy_min[Math.max(u.od_index, od)])}
            x2={x(data.casy_min[Math.min(u.do_index, doIdx - 1)])}
            y1={yH(u.strop_kw)} y2={yH(u.strop_kw)}
            stroke="var(--c-axis)" strokeWidth="1" strokeDasharray="2 3" opacity="0.55"
          />
        ))}
        {[
          { v: ref_.rk_soucasna_kw, barva: "var(--c-refnow)", popis: ref_.popisek_soucasna },
          { v: ref_.rk_nova_kw, barva: "var(--c-refnew)", popis: ref_.popisek_nova },
        ]
          .filter((r) => r.v != null && r.v <= yMax)
          .map((r) => (
            <g key={r.popis}>
              <line x1={x0} y1={yH(r.v)} x2={x1} y2={yH(r.v)} stroke={r.barva} strokeWidth="1.5" strokeDasharray="5 3" />
              <text x={x1 - 4} y={yH(r.v) - 4} textAnchor="end" fontSize="10" fontWeight="600" fill={r.barva}>
                {uzky ? `${Math.round(r.v)} kW` : `${r.popis} ${Math.round(r.v)} kW`}
              </text>
            </g>
          ))}
        {serie.baterie && (
          <>
            <line x1={x0} y1={yB(0)} x2={x1} y2={yB(0)} stroke="var(--c-grid)" strokeWidth="1" />
            <text x={x0 - 8} y={yB(maxBaterie * 1.1) + 9} textAnchor="end" fontSize="9" fill="var(--muted)">
              {Math.round(maxBaterie)}
            </text>
            <text x={x0 - 8} y={yB(0) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">0</text>
            <text x={x0 - 8} y={yB(-maxBaterie * 1.1) - 2} textAnchor="end" fontSize="9" fill="var(--muted)">
              −{Math.round(maxBaterie)}
            </text>
          </>
        )}
        {serie.soc && (
          <>
            <line x1={x0} y1={yS(0)} x2={x1} y2={yS(0)} stroke="var(--c-grid)" strokeWidth="1" />
            <text x={x0 - 8} y={yS(100) + 9} textAnchor="end" fontSize="9" fill="var(--muted)">100 %</text>
            <text x={x0 - 8} y={yS(0) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">0</text>
          </>
        )}
        {V_CENA > 0 && rozsahCeny && (
          <>
            {/* Nula je u ceny důležitá: pod ní se za odběr platí naopak. */}
            {rozsahCeny.min < 0 && (
              <line
                x1={x0} y1={yP(0)} x2={x1} y2={yP(0)}
                stroke="var(--c-grid)" strokeWidth="1" strokeDasharray="4 3"
              />
            )}
            <text x={x0 - 8} y={yP(rozsahCeny.max) + 9} textAnchor="end" fontSize="9" fill="var(--muted)">
              {Math.round(rozsahCeny.max)}
            </text>
            {rozsahCeny.min < 0 && (
              <text x={x0 - 8} y={yP(0) + 3} textAnchor="end" fontSize="9" fill="var(--muted)">0</text>
            )}
            <text x={x0 - 8} y={yP(rozsahCeny.min) - 2} textAnchor="end" fontSize="9" fill="var(--muted)">
              {Math.round(rozsahCeny.min)}
            </text>
            <text
              x={x1 - 4} y={yP(rozsahCeny.max) + 10}
              textAnchor="end" fontSize="9.5" fontWeight="600" fill="var(--c-export)"
            >
              spotová cena Kč/MWh
            </text>
          </>
        )}
      </>
    );
  }, [
    data.useky_stropu, data.casy_min, od, doIdx, tickyY, tickyCasu, x, yH, yB, yS, yP,
    x0, x1, yOsa, yMax, maxBaterie, serie.baterie, serie.soc, uzky, V_CENA, rozsahCeny,
    ref_.rk_soucasna_kw, ref_.rk_nova_kw, ref_.popisek_soucasna, ref_.popisek_nova,
  ]);

  const viditelneUdalosti = useMemo(
    () => (data.udalosti || []).filter((u) => kategorie[u.kategorie] && u.index >= od && u.index < doIdx),
    [data.udalosti, kategorie, od, doIdx]
  );

  const vrstvaUdalosti = useMemo(
    () =>
      viditelneUdalosti.map((u, i) => {
        const px = x(data.casy_min[u.index]);
        const hodnota = u.jednotka === "kW" ? u.hodnota : data.site_kw[u.index];
        const py = yH(hodnota);
        const vybrana = vybranaUdalost && vybranaUdalost.index === u.index && vybranaUdalost.typ === u.typ;
        const barva = `var(${KATEGORIE.find((k) => k.klic === u.kategorie)?.token || "--c-axis"})`;
        return (
          <g key={`u${i}`} style={{ cursor: "pointer" }} onClick={() => setVybranaUdalost(u)}>
            <circle cx={px} cy={py} r={vybrana ? 5 : 3.2} fill={barva} stroke="var(--surface, #fff)" strokeWidth="1" />
            {(vybrana || viditelneUdalosti.length <= 6) && (
              <text
                x={px} y={py - 9}
                textAnchor={px > x1 - 90 ? "end" : px < x0 + 90 ? "start" : "middle"}
                fontSize="10" fontWeight="600" fill={barva}
              >
                {u.jednotka === "kW" ? fmtKw(u.hodnota, 0) : `${u.hodnota} ${u.jednotka}`}
              </text>
            )}
          </g>
        );
      }),
    [viditelneUdalosti, x, yH, data.casy_min, data.site_kw, vybranaUdalost, x0, x1]
  );

  const seznamUdalosti = useMemo(
    () => (data.udalosti || []).filter((u) => kategorie[u.kategorie]),
    [data.udalosti, kategorie]
  );

  const tabulkaUdalosti = useMemo(
    () => (
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
                <td style={{ width: 18, color: `var(${KATEGORIE.find((k) => k.klic === u.kategorie)?.token || "--c-axis"})` }}>●</td>
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
    ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [seznamUdalosti, vybranaUdalost, zaklad, data.casy_min, naDen, n]
  );

  const jednotkaKose = krok === 1
    ? `${intervalMin} min (přesné hodnoty)`
    : krok < 4 ? `${krok * intervalMin} min`
    : krok < naDen ? `${((krok * intervalMin) / 60).toFixed((krok * intervalMin) % 60 ? 1 : 0)} h`
    : `${(krok / naDen).toFixed(krok % naDen ? 1 : 0)} dne`;

  const casOd = new Date(zaklad + tOd * 60000);
  const casDo = new Date(zaklad + tDo * 60000);
  const tlacitko = { padding: "3px 9px", fontSize: 11 };

  return (
    <div>
      {/* ovládání */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fm-muted)" }}>Přiblížení</span>
        {UROVNE.map((u) => (
          <button
            key={u.nazev}
            className="fm-btn"
            style={tlacitko}
            aria-pressed={Math.abs(doIdx - od - u.intervalu) < Math.max(2, u.intervalu * 0.15)}
            onClick={() => (u.intervalu >= n ? nastavRozsah(0, n) : oknoKolem((od + doIdx) / 2, u.intervalu))}
          >
            {u.nazev}
          </button>
        ))}
        <span style={{ display: "inline-flex", gap: 4, marginLeft: 4 }}>
          <button className="fm-btn" style={tlacitko} onClick={() => posun(-1)} title="O výřez zpět">←</button>
          <button className="fm-btn" style={tlacitko} onClick={() => posun(1)} title="O výřez vpřed">→</button>
          <button className="fm-btn" style={tlacitko} onClick={oddal} title="Oddálit">−</button>
          <button className="fm-btn" style={tlacitko} onClick={() => nastavRozsah(0, n)}>Celý rok</button>
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, fontSize: 11, marginBottom: 6 }}>
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
        {maCenu && (
          <label style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <input
              type="checkbox"
              checked={serie.cena}
              onChange={(e) => setSerie((s) => ({ ...s, cena: e.target.checked }))}
            />
            <span style={{ display: "inline-block", width: 12, height: 3, background: "var(--c-export)" }} />{" "}
            spotová cena
          </label>
        )}
      </div>

      <div ref={obalRef} style={{ position: "relative", width: "100%" }}>
        {/* datové vrstvy – canvas kvůli plynulosti při zoomu a posunu */}
        <canvas
          ref={canvasRef}
          style={{ display: "block", width: sirka, height: vyska, pointerEvents: "none" }}
        />
        {/* přehledová lišta (kreslí se jen při změně dat nebo šířky) – musí být
            v DOM před SVG, jinak by překryla klikací plochu výřezu */}
        <canvas
          ref={prehledCanvasRef}
          style={{
            position: "absolute", left: 0, top: yPrehled, width: sirka, height: V_PREHLED,
            pointerEvents: "none",
          }}
        />
        {/* Popisky, referenční čáry, značky a interakce – SVG nad canvasem.
            touchAction pan-y (ne none): vodorovné tažení si bereme na výběr
            výseku, svislé nechává prstu projít na rolování stránky – jinak by
            se na mobilu nešlo přes graf posunout dál. */}
        <svg
          width={sirka}
          height={vyska}
          style={{ position: "absolute", left: 0, top: 0, touchAction: "pan-y", userSelect: "none" }}
          role="img"
          aria-label="Průběh odběru a činnosti baterie v čase"
        >
          {vrstvaOs}
          {vrstvaUdalosti}
          {kurzor && !tah && (
            <line x1={kurzor.px} y1={yHlavni} x2={kurzor.px} y2={yOsa} stroke="var(--c-axis)" strokeWidth="1" opacity="0.45" />
          )}
          {tah && tah.rezim === "vyber" && Math.abs(tah.x - tah.x0) > 2 && (
            <rect
              x={Math.min(tah.x0, tah.x)} y={yHlavni} width={Math.abs(tah.x - tah.x0)} height={yOsa - yHlavni}
              fill="var(--brand)" opacity="0.16" stroke="var(--brand)" strokeWidth="1"
            />
          )}
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
          <rect
            x={xp(od)} y={yPrehled}
            width={Math.max(2, xp(doIdx - 1) - xp(od))} height={V_PREHLED}
            fill="var(--brand)" opacity="0.18" stroke="var(--brand)" strokeWidth="1"
          />
          <rect
            x={x0} y={yPrehled} width={sirkaGrafu} height={V_PREHLED}
            fill="transparent" style={{ cursor: "pointer" }}
            onPointerDown={(e) => {
              const podil = Math.max(0, Math.min(1, (myšX(e) - x0) / sirkaGrafu));
              oknoKolem(podil * n, doIdx - od);
            }}
          />
          <text x={x0} y={yPrehled - 3} fontSize="9" fill="var(--muted)">
            celý rok – klikni pro přesun výřezu
          </text>
        </svg>
        {kurzor && !tah && (
          <div
            style={{
              position: "absolute",
              left: Math.min(Math.max(kurzor.px + 12, 0), Math.max(0, sirka - 202)),
              top: yHlavni + 6,
              width: 190,
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
              <b>
                {krok === 1
                  ? fmtKw(data.site_kw[kurzor.i])
                  : `${Math.round(kose.sMin[kurzor.poradi])} / ${Math.round(kose.sPrum[kurzor.poradi])} / ${Math.round(kose.sMax[kurzor.poradi])} kW`}
              </b>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", color: "var(--fm-muted)" }}>
              <span>bez baterie</span>
              <span>
                {krok === 1
                  ? fmtKw(data.odber_kw[kurzor.i])
                  : `${Math.round(kose.oMin[kurzor.poradi])} / ${Math.round(kose.oPrum[kurzor.poradi])} / ${Math.round(kose.oMax[kurzor.poradi])} kW`}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>baterie</span>
              <b style={{ color: data.baterie_kw[kurzor.i] > 0 ? "var(--brand)" : "var(--c-export)" }}>
                {krok === 1
                  ? data.baterie_kw[kurzor.i] === 0
                    ? "stojí"
                    : `${data.baterie_kw[kurzor.i] > 0 ? "vybíjí" : "nabíjí"} ${fmtKw(Math.abs(data.baterie_kw[kurzor.i]))}`
                  : `${Math.round(kose.bMin[kurzor.poradi])} … ${Math.round(kose.bMax[kurzor.poradi])} kW`}
              </b>
            </div>
            {/* Kolik z výkonu šlo na srážení špičky a kolik na to druhé
                (obchod u peak shavingu, ukládání ze slunce u PPA + BESS) –
                to je jádro rozhodování dvoucílového dispatchu. */}
            {krok === 1 && data.baterie_ps_kw && data.baterie_obchod_kw && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  color: "var(--fm-muted)",
                }}
              >
                <span>z toho špička / {popisDruheSerie}</span>
                <span>
                  {Math.round(data.baterie_ps_kw[kurzor.i])} / {Math.round(data.baterie_obchod_kw[kurzor.i])} kW
                </span>
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>stav nabití</span>
              <span>{Math.round(krok === 1 ? data.soc_pct[kurzor.i] : kose.cPrum[kurzor.poradi])} %</span>
            </div>
            {maCenu && (
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span>spotová cena</span>
                <b style={{ color: "var(--c-export)" }}>
                  {krok === 1
                    ? `${Math.round(data.cena_kc_mwh[kurzor.i]).toLocaleString("cs-CZ")} Kč/MWh`
                    : `${Math.round(kose.pMin[kurzor.poradi])} … ${Math.round(kose.pMax[kurzor.poradi])} Kč/MWh`}
                </b>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ fontSize: 11, color: "var(--fm-muted)", margin: "4px 0 10px" }}>
        Zobrazeno {fmtCas(casOd)} – {fmtCas(casDo)} ({(doIdx - od).toLocaleString("cs-CZ")} intervalů,
        jeden bod = {jednotkaKose}). Kolečkem myši přiblížíš, tažením vybereš výsek,
        se Shiftem posuneš, dvojklikem oddálíš.
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fm-muted)" }}>Události</span>
        {KATEGORIE.map((k) => (
          <button
            key={k.klic}
            className="fm-btn"
            aria-pressed={!!kategorie[k.klic]}
            onClick={() => setKategorie((s) => ({ ...s, [k.klic]: !s[k.klic] }))}
            style={{
              ...tlacitko,
              color: kategorie[k.klic] ? `var(${k.token})` : "var(--fm-muted)",
              fontWeight: kategorie[k.klic] ? 700 : 400,
            }}
          >
            ● {k.nazev}
          </button>
        ))}
      </div>
      <div
        className="nb-scroll"
        style={{ maxHeight: 168, overflowY: "auto", overflowX: "auto", border: "1px solid var(--line)", borderRadius: 9 }}
      >
        {tabulkaUdalosti}
      </div>
      {popisRoku && <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 6 }}>{popisRoku}</div>}
    </div>
  );
}
