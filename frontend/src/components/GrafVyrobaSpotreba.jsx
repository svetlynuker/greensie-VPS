// Lehký SVG graf měsíční výroby FVE vs. spotřeby klienta (METODIKA-ppa-fve.md
// kap. 6.1). Bez externí knihovny – projekt žádnou grafovou nemá a deploy nedělá
// `npm install`, tak držíme nulové závislosti (stejně jako GrafOdberu.jsx).
//
// Pro každý měsíc dva sloupce:
//  - spotřeba = samospotřeba (z FVE) + dokup ze sítě,
//  - výroba   = samospotřeba + přetok do sítě + ořez.

const MESICE_ZKR = ["led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"];

const BARVA = {
  samospotreba: "#2f9e44", // zeleně krytá spotřeba z FVE
  dokup: "#ced4da", // dokup ze sítě
  export: "#1971c2", // přetok do sítě
  orez: "#e8590c", // ořez (nad rez. výkonem dodávky)
};

function mwh(kwh) {
  return `${(kwh / 1000).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} MWh`;
}

export default function GrafVyrobaSpotreba({ graf }) {
  if (!graf || !graf.mesice?.length) return null;
  const { mesice, spotreba_kwh, vyroba_kwh, samospotreba_kwh, export_kwh, orez_kwh, dokup_kwh } = graf;

  const W = 680;
  const H = 280;
  const L = 52;
  const R = 12;
  const TOP = 10;
  const BOT = 26;
  const x0 = L;
  const x1 = W - R;
  const y0 = TOP;
  const y1 = H - BOT;

  const maxKwh = Math.max(1, ...spotreba_kwh, ...vyroba_kwh) * 1.1;
  const n = mesice.length || 1;
  const gw = (x1 - x0) / n;
  const bw = gw * 0.32;
  const y = (v) => y1 - (v / maxKwh) * (y1 - y0);
  const h = (v) => (v / maxKwh) * (y1 - y0);

  const ticky = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round((maxKwh * f) / 1000) * 1000);

  // Vykreslí stohovaný sloupec (odspodu) ze segmentů [{v, barva}].
  function Sloupec({ cx, segmenty }) {
    let base = y1;
    return segmenty.map((s, i) => {
      const vyska = h(s.v);
      base -= vyska;
      return <rect key={i} x={cx} y={base} width={bw} height={Math.max(0, vyska)} fill={s.barva} />;
    });
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, marginBottom: 6 }}>
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: BARVA.samospotreba, verticalAlign: "middle", marginRight: 4 }} />samospotřeba z FVE</span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: BARVA.dokup, verticalAlign: "middle", marginRight: 4 }} />dokup ze sítě</span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: BARVA.export, verticalAlign: "middle", marginRight: 4 }} />přetok do sítě</span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: BARVA.orez, verticalAlign: "middle", marginRight: 4 }} />ořez</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", maxWidth: "100%" }} role="img">
        {ticky.map((t, i) => (
          <g key={i}>
            <line x1={x0} y1={y(t)} x2={x1} y2={y(t)} stroke="#e9ecef" strokeWidth="1" />
            <text x={x0 - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="#868e96">
              {Math.round(t / 1000)}
            </text>
          </g>
        ))}
        <text x={x0 - 6} y={y0 - 1} textAnchor="end" fontSize="9" fill="#adb5bd">MWh</text>
        {mesice.map((m, i) => {
          const gx = x0 + i * gw;
          const cx = gx + gw / 2;
          return (
            <g key={m}>
              {/* levý sloupec = spotřeba (samospotřeba + dokup) */}
              <Sloupec
                cx={cx - bw - 1}
                segmenty={[
                  { v: samospotreba_kwh[i] ?? 0, barva: BARVA.samospotreba },
                  { v: dokup_kwh[i] ?? 0, barva: BARVA.dokup },
                ]}
              />
              {/* pravý sloupec = výroba (samospotřeba + přetok + ořez) */}
              <Sloupec
                cx={cx + 1}
                segmenty={[
                  { v: samospotreba_kwh[i] ?? 0, barva: BARVA.samospotreba },
                  { v: export_kwh[i] ?? 0, barva: BARVA.export },
                  { v: orez_kwh[i] ?? 0, barva: BARVA.orez },
                ]}
              />
              <text x={cx} y={y1 + 14} textAnchor="middle" fontSize="10" fill="#868e96">
                {MESICE_ZKR[m - 1] || m}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 4 }}>
        Levý sloupec = spotřeba, pravý = výroba (rok 1). Celkem za rok: spotřeba{" "}
        {mwh(spotreba_kwh.reduce((a, b) => a + b, 0))}, výroba {mwh(vyroba_kwh.reduce((a, b) => a + b, 0))}.
      </div>
    </div>
  );
}
