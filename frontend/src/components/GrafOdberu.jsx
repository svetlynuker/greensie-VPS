// Lehký SVG graf měsíčních maxim odběru (bez baterie vs. s baterií) + čáry
// rezervované kapacity. Bez externí knihovny – projekt žádnou grafovou nemá a
// deploy nedělá `npm install`, tak držíme nulové závislosti.
//
// Barvy výhradně přes CSS tokeny --c-* (global.css): graf tak sám funguje
// ve světlém/tmavém režimu i při kompenzaci červeno-zelené vady.

const MESICE_ZKR = ["led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"];

function kwLabel(v) {
  return `${Math.round(v)} kW`;
}

// Sloupec se zaoblenou horní hranou, ukotvený na základně.
function topRoundRect(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, Math.max(0, h));
  const yb = y + h;
  return (
    `M${x},${yb} L${x},${y + rr} Q${x},${y} ${x + rr},${y} ` +
    `L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${yb} Z`
  );
}

export default function GrafOdberu({ mesice, bezBaterie, sBaterii, rpSoucasna, rpNova }) {
  const W = 760;
  const H = 260;
  const L = 46;
  const R = 96; // místo vpravo na popisky referenčních čar
  const TOP = 10;
  const BOT = 26;
  const x0 = L;
  const x1 = W - R;
  const y0 = TOP;
  const y1 = H - BOT;

  const cisla = [...bezBaterie, ...sBaterii, rpSoucasna, rpNova].filter((v) => v != null);
  const ymax = Math.max(1, ...cisla) * 1.1;
  const n = mesice.length || 1;
  const gw = (x1 - x0) / n;
  const bw = gw * 0.32;
  const y = (v) => y1 - (v / ymax) * (y1 - y0);

  const ticky = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round((ymax * f) / 5) * 5);

  return (
    <div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, marginBottom: 6 }}>
        <span><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "var(--c-before)", verticalAlign: "middle", marginRight: 4 }} />bez baterie</span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: "var(--c-after)", verticalAlign: "middle", marginRight: 4 }} />s baterií</span>
        <span><span style={{ display: "inline-block", width: 14, height: 0, borderTop: "2px dashed var(--c-refnow)", verticalAlign: "middle", marginRight: 4 }} />rezervace nyní ({kwLabel(rpSoucasna)})</span>
        <span><span style={{ display: "inline-block", width: 14, height: 0, borderTop: "2px dashed var(--c-refnew)", verticalAlign: "middle", marginRight: 4 }} />rezervace nová ({kwLabel(rpNova)})</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", maxWidth: "100%" }} role="img">
        {/* osy Y – mřížka + popisky */}
        {ticky.map((t, i) => (
          <g key={i}>
            <line x1={x0} y1={y(t)} x2={x1} y2={y(t)} stroke="var(--c-grid)" strokeWidth="1" />
            <text x={x0 - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="var(--muted)">{t}</text>
          </g>
        ))}
        {/* sloupce po měsících */}
        {mesice.map((m, i) => {
          const gx = x0 + i * gw;
          const cx = gx + gw / 2;
          const bez = bezBaterie[i] ?? 0;
          const sb = sBaterii[i] ?? 0;
          return (
            <g key={m}>
              <path d={topRoundRect(cx - bw - 1, y(bez), bw, y1 - y(bez), 3)} fill="var(--c-before)">
                <title>{`${MESICE_ZKR[m - 1] || m} · bez baterie ${kwLabel(bez)}`}</title>
              </path>
              <path d={topRoundRect(cx + 1, y(sb), bw, y1 - y(sb), 3)} fill="var(--c-after)">
                <title>{`${MESICE_ZKR[m - 1] || m} · s baterií ${kwLabel(sb)}`}</title>
              </path>
              <text x={cx} y={y1 + 14} textAnchor="middle" fontSize="10" fill="var(--muted)">{MESICE_ZKR[m - 1] || m}</text>
            </g>
          );
        })}
        {/* čáry rezervované kapacity + popisky u pravého okraje */}
        {rpSoucasna != null && (
          <g>
            <line x1={x0} y1={y(rpSoucasna)} x2={x1} y2={y(rpSoucasna)} stroke="var(--c-refnow)" strokeWidth="1.5" strokeDasharray="5 3" />
            <text x={x1 + 8} y={y(rpSoucasna) + 3.5} fontSize="11" fontWeight="600" fill="var(--c-refnow)">
              nyní {Math.round(rpSoucasna)}
            </text>
          </g>
        )}
        {rpNova != null && (
          <g>
            <line x1={x0} y1={y(rpNova)} x2={x1} y2={y(rpNova)} stroke="var(--c-refnew)" strokeWidth="1.5" strokeDasharray="5 3" />
            <text x={x1 + 8} y={y(rpNova) + 3.5} fontSize="11" fontWeight="600" fill="var(--c-refnew)">
              nová {Math.round(rpNova)}
            </text>
          </g>
        )}
        {/* základna */}
        <line x1={x0} y1={y1} x2={x1} y2={y1} stroke="var(--c-axis)" strokeWidth="1" opacity="0.4" />
      </svg>
    </div>
  );
}
