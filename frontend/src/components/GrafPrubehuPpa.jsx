// Nitkový graf průběhu výroby a spotřeby: celý rok po 15 minutách, se zoomem od
// přehledu měsíců až na jednotlivé čtvrthodiny. Ukazuje to, co je u PPA podstatné –
// kdy se výroba a odběr opravdu potkávají (a kolik se tím pádem prodá zákazníkovi),
// kdy výroba přetéká do sítě a kdy se dokupuje.
//
// Stejná stavba jako `GrafPrubehu.jsx` u peak shavingu, ale vlastní kreslení:
// tamní pomocníky `agreguj`/`kresliData` mají zadrátované peak-shavingové řady
// (SOC, stropy), takže se přebírají jen ty obecné (osa času, ticky, názvy měsíců).
//
// Bez grafové knihovny (projekt žádnou nemá), dvě vrstvy:
//  - <canvas> = datové řady a mřížka. Kreslí ~35 000 bodů řádově rychleji než SVG.
//  - <svg> nad ním = popisky os, referenční čára, kříž kurzoru a hover plocha.
//
// Objem dat: řady se při každé změně přiblížení slijí do košů (jeden na pixel
// šířky) a z každého se kreslí pásmo min–max + průměrová nitka. Špička tak
// nezmizí zaokrouhlením; při plném přiblížení pásmo splyne s nitkou a vidíš
// přesné čtvrthodinové hodnoty.

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { DNY_ZKR, MESICE_ZKR, dvojcifernne, osaCasu, ticky } from "./grafPrubehuData";

const MIN_INTERVALU = 4; // nejmenší výřez = 1 hodina
const MAX_KOSU = 1400;

// Barvy z CSS tokenů (canvas si je musí přečíst přes getComputedStyle), aby graf
// fungoval ve světlém, tmavém i CVD režimu. Výchozí hodnoty platí do prvního
// načtení stylů.
const TOKENY = {
  spotreba: ["--c-before", "#c4cdc7"],
  samospotreba: ["--c-after", "#2f9e44"],
  pretok: ["--c-export", "#1971c2"],
  orez: ["--c-orez", "#e8590c"],
  soc: ["--c-refnew", "#d97706"],
  mrizka: ["--c-grid", "#e9edea"],
  osa: ["--c-axis", "#4b5852"],
  plocha: ["--surface", "#ffffff"],
};

function nactiBarvy(el) {
  const cs = getComputedStyle(el);
  const out = {};
  for (const [klic, [token, zaloha]] of Object.entries(TOKENY)) {
    out[klic] = (cs.getPropertyValue(token) || "").trim() || zaloha;
  }
  return out;
}

// Sloučení řad do košů (jeden na pixel). Pro každou řadu průměr, pro spotřebu
// a výrobu i min–max, ať se neztratí špička.
function doKosu(data, od, doIdx, cil) {
  const S = data.spotreba_kw;
  const V = data.vyroba_kw;
  const SS = data.samospotreba_kw;
  const P = data.pretok_kw;
  const O = data.orez_kw;
  const C = data.soc_pct || null;
  const T = data.casy_min;

  const pocet = Math.max(1, doIdx - od);
  const krok = Math.max(1, Math.ceil(pocet / cil));
  const n = Math.ceil(pocet / krok);
  const k = {
    pocet: 0,
    t: new Float64Array(n),
    i0: new Int32Array(n),
    i1: new Int32Array(n),
    sAvg: new Float64Array(n),
    sMax: new Float64Array(n),
    vAvg: new Float64Array(n),
    vMax: new Float64Array(n),
    ssAvg: new Float64Array(n),
    pAvg: new Float64Array(n),
    oAvg: new Float64Array(n),
    cAvg: C ? new Float64Array(n) : null,
  };
  let j = 0;
  for (let i = od; i < doIdx; i += krok) {
    const e = Math.min(doIdx, i + krok);
    let sSum = 0, sMax = -Infinity, vSum = 0, vMax = -Infinity;
    let ssSum = 0, pSum = 0, oSum = 0, cSum = 0;
    for (let q = i; q < e; q++) {
      const sv = S[q], vv = V[q];
      sSum += sv; if (sv > sMax) sMax = sv;
      vSum += vv; if (vv > vMax) vMax = vv;
      ssSum += SS[q]; pSum += P[q]; oSum += O[q];
      if (C) cSum += C[q];
    }
    const d = e - i;
    k.t[j] = T[i];
    k.i0[j] = i;
    k.i1[j] = e;
    k.sAvg[j] = sSum / d; k.sMax[j] = sMax;
    k.vAvg[j] = vSum / d; k.vMax[j] = vMax;
    k.ssAvg[j] = ssSum / d;
    k.pAvg[j] = pSum / d;
    k.oAvg[j] = oSum / d;
    if (C) k.cAvg[j] = cSum / d;
    j++;
  }
  k.pocet = j;
  return k;
}

export default function GrafPrubehuPpa({ data, popis }) {
  const obalRef = useRef(null);
  const canvasRef = useRef(null);
  const [sirka, setSirka] = useState(880);
  const [barvy, setBarvy] = useState(() => ({ ...Object.fromEntries(Object.entries(TOKENY).map(([k, v]) => [k, v[1]])) }));
  const [vyrez, setVyrez] = useState(null); // {od, do} v indexech
  const [kurzor, setKurzor] = useState(null);
  const [serie, setSerie] = useState({ spotreba: true, vyroba: true, pretok: true, soc: true });
  const tahRef = useRef(null);
  const rafRef = useRef(0);

  const pocet = data?.pocet || 0;
  const maSoc = !!(data?.soc_pct && data.soc_pct.length);

  // celý rozsah jako výchozí výřez
  useEffect(() => {
    setVyrez({ od: 0, do: pocet });
  }, [pocet]);

  // šířka podle obalu (responsivně)
  useLayoutEffect(() => {
    const el = obalRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSirka(Math.max(320, el.clientWidth)));
    ro.observe(el);
    setSirka(Math.max(320, el.clientWidth));
    return () => ro.disconnect();
  }, []);

  // barvy z tokenů + reakce na přepnutí motivu / CVD režimu
  useLayoutEffect(() => {
    const el = obalRef.current;
    if (!el) return;
    const prectiZnovu = () => setBarvy(nactiBarvy(el));
    prectiZnovu();
    const mo = new MutationObserver(prectiZnovu);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-cvd"] });
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", prectiZnovu);
    return () => {
      mo.disconnect();
      mq.removeEventListener("change", prectiZnovu);
    };
  }, []);

  const V = 300; // výška plochy grafu
  const mL = 52, mR = maSoc && serie.soc ? 44 : 14, mT = 10, mB = 30;
  const pw = Math.max(10, sirka - mL - mR);
  const ph = V - mT - mB;

  const kose = useMemo(() => {
    if (!data || !vyrez) return null;
    return doKosu(data, vyrez.od, vyrez.do, Math.min(MAX_KOSU, Math.round(pw)));
  }, [data, vyrez, pw]);

  const maxKw = useMemo(() => {
    if (!kose || !kose.pocet) return 1;
    let m = 0;
    for (let i = 0; i < kose.pocet; i++) {
      if (serie.spotreba && kose.sMax[i] > m) m = kose.sMax[i];
      if (serie.vyroba && kose.vMax[i] > m) m = kose.vMax[i];
    }
    const rez = data?.referencni?.rezervovany_vykon_dodavky_kw;
    if (rez && rez > m) m = rez;
    return m > 0 ? m * 1.08 : 1;
  }, [kose, serie.spotreba, serie.vyroba, data]);

  const x = useCallback((t) => {
    if (!kose || !kose.pocet) return mL;
    const t0 = kose.t[0];
    const t1 = kose.t[kose.pocet - 1] || t0 + 1;
    return mL + ((t - t0) / Math.max(1, t1 - t0)) * pw;
  }, [kose, pw, mL]);
  const y = useCallback((v) => mT + ph - (Math.max(0, v) / maxKw) * ph, [maxKw, ph, mT]);
  const ySoc = useCallback((p) => mT + ph - (Math.max(0, Math.min(100, p)) / 100) * ph, [ph, mT]);

  // ---- kreslení
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv || !kose) return;
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(sirka * dpr);
    cv.height = Math.round(V * dpr);
    cv.style.width = `${sirka}px`;
    cv.style.height = `${V}px`;
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, sirka, V);
    const n = kose.pocet;
    if (!n) return;

    // mřížka
    ctx.strokeStyle = barvy.mrizka;
    ctx.lineWidth = 1;
    for (const t of ticky(0, maxKw, 4)) {
      const yy = Math.round(y(t)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(mL, yy);
      ctx.lineTo(mL + pw, yy);
      ctx.stroke();
    }

    // pásmo min–max (jen když koš pokrývá víc intervalů, jinak splyne s nitkou)
    const pasmo = (avgPole, maxPole, barva) => {
      ctx.globalAlpha = 0.18;
      ctx.fillStyle = barva;
      ctx.beginPath();
      for (let i = 0; i < n; i++) ctx.lineTo(x(kose.t[i]), y(maxPole[i]));
      for (let i = n - 1; i >= 0; i--) ctx.lineTo(x(kose.t[i]), y(avgPole[i]));
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
    };

    // samospotřeba jako plocha – to je energie, kterou zákazník opravdu kupuje
    if (serie.vyroba || serie.spotreba) {
      ctx.globalAlpha = 0.35;
      ctx.fillStyle = barvy.samospotreba;
      ctx.beginPath();
      ctx.moveTo(x(kose.t[0]), y(0));
      for (let i = 0; i < n; i++) ctx.lineTo(x(kose.t[i]), y(kose.ssAvg[i]));
      ctx.lineTo(x(kose.t[n - 1]), y(0));
      ctx.closePath();
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    const nitka = (pole, barva, tloustka) => {
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const px = x(kose.t[i]);
        const py = y(pole[i]);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = barva;
      ctx.lineWidth = tloustka;
      ctx.stroke();
    };

    if (serie.spotreba) {
      pasmo(kose.sAvg, kose.sMax, barvy.spotreba);
      nitka(kose.sAvg, barvy.spotreba, 1.6);
    }
    if (serie.pretok) nitka(kose.pAvg, barvy.pretok, 1.4);
    if (serie.vyroba) {
      pasmo(kose.vAvg, kose.vMax, barvy.samospotreba);
      nitka(kose.vAvg, barvy.samospotreba, 2);
    }
    if (maSoc && serie.soc && kose.cAvg) {
      ctx.setLineDash([4, 3]);
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const px = x(kose.t[i]);
        const py = ySoc(kose.cAvg[i]);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.strokeStyle = barvy.soc;
      ctx.lineWidth = 1.4;
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [kose, barvy, maxKw, sirka, pw, mL, x, y, ySoc, serie, maSoc]);

  // ---- interakce: zoom kolečkem, posun tažením
  function naKolecko(e) {
    if (!vyrez) return;
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const rel = Math.min(1, Math.max(0, (e.clientX - rect.left - mL) / pw));
    const sirkaV = vyrez.do - vyrez.od;
    const faktor = e.deltaY > 0 ? 1.25 : 0.8;
    let nova = Math.round(sirkaV * faktor);
    nova = Math.max(MIN_INTERVALU, Math.min(pocet, nova));
    const stred = vyrez.od + rel * sirkaV;
    let od = Math.round(stred - rel * nova);
    od = Math.max(0, Math.min(pocet - nova, od));
    setVyrez({ od, do: od + nova });
  }

  function naStisk(e) {
    if (!vyrez) return;
    tahRef.current = { x: e.clientX, od: vyrez.od };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }
  function naPohyb(e) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    if (tahRef.current && vyrez) {
      const sirkaV = vyrez.do - vyrez.od;
      const posun = Math.round(((tahRef.current.x - e.clientX) / pw) * sirkaV);
      let od = Math.max(0, Math.min(pocet - sirkaV, tahRef.current.od + posun));
      setVyrez({ od, do: od + sirkaV });
      return;
    }
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      if (!kose || !kose.pocet || px < mL || px > mL + pw) {
        setKurzor(null);
        return;
      }
      const rel = (px - mL) / pw;
      const i = Math.min(kose.pocet - 1, Math.max(0, Math.round(rel * (kose.pocet - 1))));
      setKurzor({ i, px });
    });
  }
  function naPusteni(e) {
    tahRef.current = null;
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }

  if (!data || !pocet || !kose) return null;

  const zaklad = new Date(data.od).getTime();
  const tOd = kose.t[0];
  const tDo = kose.t[kose.pocet - 1];
  const popisky = osaCasu(zaklad, tOd, tDo, pw / 880);
  const rez = data.referencni?.rezervovany_vykon_dodavky_kw;
  const intervalu = vyrez.do - vyrez.od;
  const jednoKos = intervalu <= kose.pocet;

  const LEGENDA = [
    { klic: "spotreba", nazev: "Spotřeba", barva: barvy.spotreba },
    { klic: "vyroba", nazev: "Výroba FVE", barva: barvy.samospotreba },
    { klic: "pretok", nazev: "Přetok do sítě", barva: barvy.pretok },
    ...(maSoc ? [{ klic: "soc", nazev: "Nabití baterie", barva: barvy.soc }] : []),
  ];

  return (
    <div ref={obalRef} style={{ width: "100%" }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 14,
          alignItems: "center",
          marginBottom: 8,
          fontSize: 12.5,
        }}
      >
        {LEGENDA.map((l) => (
          <label
            key={l.klic}
            style={{ display: "inline-flex", alignItems: "center", gap: 6, cursor: "pointer" }}
            title="Klikni pro skrytí/zobrazení řady"
          >
            <input
              type="checkbox"
              checked={!!serie[l.klic]}
              onChange={(e) => setSerie((s) => ({ ...s, [l.klic]: e.target.checked }))}
            />
            <span
              aria-hidden="true"
              style={{
                width: 14,
                height: 3,
                borderRadius: 2,
                background: l.barva,
                display: "inline-block",
              }}
            />
            <span>{l.nazev}</span>
          </label>
        ))}
        <span style={{ flex: 1 }} />
        <button
          type="button"
          className="fm-btn"
          style={{ padding: "3px 9px", fontSize: 12 }}
          onClick={() => setVyrez({ od: 0, do: pocet })}
          disabled={vyrez.od === 0 && vyrez.do === pocet}
        >
          Celý rok
        </button>
      </div>

      <div style={{ position: "relative", touchAction: "none" }}>
        <canvas ref={canvasRef} style={{ display: "block", cursor: tahRef.current ? "grabbing" : "crosshair" }} />
        <svg
          width={sirka}
          height={V}
          style={{ position: "absolute", inset: 0 }}
          onWheel={naKolecko}
          onPointerDown={naStisk}
          onPointerMove={naPohyb}
          onPointerUp={naPusteni}
          onPointerLeave={() => setKurzor(null)}
          role="img"
          aria-label="Průběh výroby FVE a spotřeby po 15 minutách. Kolečkem se přibližuje, tažením posouvá."
        >
          {/* osa Y – kW */}
          {ticky(0, maxKw, 4).map((t) => (
            <text
              key={t}
              x={mL - 8}
              y={y(t) + 4}
              textAnchor="end"
              fontSize="11"
              fill="var(--muted)"
              fontFamily="ui-monospace, Menlo, Consolas, monospace"
            >
              {Math.round(t)}
            </text>
          ))}
          <text x={mL - 8} y={mT - 1} textAnchor="end" fontSize="10" fill="var(--muted)">
            kW
          </text>

          {/* osa Y vpravo – SOC */}
          {maSoc && serie.soc && (
            <>
              {[0, 50, 100].map((p) => (
                <text
                  key={p}
                  x={mL + pw + 8}
                  y={ySoc(p) + 4}
                  fontSize="11"
                  fill="var(--muted)"
                  fontFamily="ui-monospace, Menlo, Consolas, monospace"
                >
                  {p}
                </text>
              ))}
              <text x={mL + pw + 8} y={mT - 1} fontSize="10" fill="var(--muted)">
                % SOC
              </text>
            </>
          )}

          {/* referenční čára: strop přetoku do sítě */}
          {rez > 0 && rez <= maxKw && (
            <>
              <line
                x1={mL}
                y1={y(rez)}
                x2={mL + pw}
                y2={y(rez)}
                stroke="var(--c-orez)"
                strokeWidth="1.5"
                strokeDasharray="6 4"
              />
              <text x={mL + 6} y={y(rez) - 5} fontSize="11" fill="var(--c-orez)">
                rezervovaný výkon dodávky {Math.round(rez)} kW
              </text>
            </>
          )}

          {/* osa X */}
          <line x1={mL} y1={mT + ph} x2={mL + pw} y2={mT + ph} stroke="var(--c-axis)" strokeWidth="1" opacity="0.35" />
          {popisky.map((p, i) => (
            <text key={i} x={x(p.t)} y={V - 10} textAnchor="middle" fontSize="11" fill="var(--muted)">
              {p.popis}
            </text>
          ))}

          {/* kříž kurzoru */}
          {kurzor && (
            <line
              x1={kurzor.px}
              y1={mT}
              x2={kurzor.px}
              y2={mT + ph}
              stroke="var(--c-axis)"
              strokeWidth="1"
              opacity="0.45"
            />
          )}
        </svg>

        {kurzor && (
          <Tooltip
            kose={kose}
            i={kurzor.i}
            px={kurzor.px}
            sirka={sirka}
            zaklad={zaklad}
            intervalMin={data.interval_min}
            maSoc={maSoc && serie.soc}
            jedenInterval={jednoKos && kose.i1[kurzor.i] - kose.i0[kurzor.i] === 1}
          />
        )}
      </div>

      <div className="gs-pozn" style={{ marginTop: 8 }}>
        {popis ||
          "Zelená plocha je samospotřeba — energie, kterou zákazník z FVE opravdu odebere a zaplatí. Kolečkem přibliž, tažením posuň."}
      </div>
    </div>
  );
}

function Tooltip({ kose, i, px, sirka, zaklad, intervalMin, maSoc, jedenInterval }) {
  const t = kose.t[i];
  const d = new Date(zaklad + t * 60000);
  const pocetIntervalu = kose.i1[i] - kose.i0[i];
  const cas = jedenInterval
    ? `${dvojcifernne(d.getDate())}. ${MESICE_ZKR[d.getMonth()]} ${DNY_ZKR[d.getDay()]} ${dvojcifernne(
        d.getHours()
      )}:${dvojcifernne(d.getMinutes())}`
    : `${dvojcifernne(d.getDate())}. ${MESICE_ZKR[d.getMonth()]} — průměr z ${pocetIntervalu} intervalů`;
  const vlevo = px > sirka * 0.6;
  const kw = (v) => `${v.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} kW`;

  return (
    <div
      style={{
        position: "absolute",
        left: vlevo ? undefined : px + 12,
        right: vlevo ? sirka - px + 12 : undefined,
        top: 8,
        pointerEvents: "none",
        background: "var(--ink)",
        color: "var(--bg)",
        padding: "8px 11px",
        borderRadius: 8,
        fontSize: 12.5,
        lineHeight: 1.55,
        whiteSpace: "nowrap",
        boxShadow: "0 4px 14px rgba(0,0,0,.22)",
        zIndex: 4,
      }}
    >
      <div style={{ fontWeight: 650, marginBottom: 3 }}>{cas}</div>
      <Radek l="Spotřeba" v={kw(kose.sAvg[i])} />
      <Radek l="Výroba FVE" v={kw(kose.vAvg[i])} />
      <Radek l="Samospotřeba" v={kw(kose.ssAvg[i])} />
      <Radek l="Přetok do sítě" v={kw(kose.pAvg[i])} />
      {kose.oAvg[i] > 0.01 && <Radek l="Ořez" v={kw(kose.oAvg[i])} />}
      {maSoc && kose.cAvg && (
        <Radek l="Nabití baterie" v={`${kose.cAvg[i].toLocaleString("cs-CZ", { maximumFractionDigits: 0 })} %`} />
      )}
      {!jedenInterval && (
        <div style={{ opacity: 0.7, fontSize: 11.5, marginTop: 3 }}>
          Přibliž pro čtvrthodinové hodnoty
        </div>
      )}
    </div>
  );
}

function Radek({ l, v }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
      <span style={{ opacity: 0.8 }}>{l}</span>
      <b style={{ fontFamily: "ui-monospace, Menlo, Consolas, monospace" }}>{v}</b>
    </div>
  );
}
