// Lehký SVG graf měsíčních maxim odběru (bez baterie vs. s baterií) + čáry
// rezervované kapacity. Bez externí knihovny – projekt žádnou grafovou nemá a
// deploy nedělá `npm install`, tak držíme nulové závislosti.

const MESICE_ZKR = ["led", "úno", "bře", "dub", "kvě", "čvn", "čvc", "srp", "zář", "říj", "lis", "pro"];

function kwLabel(v) {
  return `${Math.round(v)} kW`;
}

export default function GrafOdberu({ mesice, bezBaterie, sBaterii, rpSoucasna, rpNova }) {
  const W = 680;
  const H = 260;
  const L = 46;
  const R = 12;
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
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: "#ced4da", verticalAlign: "middle", marginRight: 4 }} />bez baterie</span>
        <span><span style={{ display: "inline-block", width: 12, height: 12, background: "#2f9e44", verticalAlign: "middle", marginRight: 4 }} />s baterií</span>
        <span><span style={{ display: "inline-block", width: 14, height: 0, borderTop: "2px dashed #e8590c", verticalAlign: "middle", marginRight: 4 }} />rezervace nyní ({kwLabel(rpSoucasna)})</span>
        <span><span style={{ display: "inline-block", width: 14, height: 0, borderTop: "2px dashed #1971c2", verticalAlign: "middle", marginRight: 4 }} />rezervace nová ({kwLabel(rpNova)})</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block", maxWidth: "100%" }} role="img">
        {/* osy Y – mřížka + popisky */}
        {ticky.map((t, i) => (
          <g key={i}>
            <line x1={x0} y1={y(t)} x2={x1} y2={y(t)} stroke="#e9ecef" strokeWidth="1" />
            <text x={x0 - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="#868e96">{t}</text>
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
              <rect x={cx - bw - 1} y={y(bez)} width={bw} height={y1 - y(bez)} fill="#ced4da" />
              <rect x={cx + 1} y={y(sb)} width={bw} height={y1 - y(sb)} fill="#2f9e44" />
              <text x={cx} y={y1 + 14} textAnchor="middle" fontSize="10" fill="#868e96">{MESICE_ZKR[m - 1] || m}</text>
            </g>
          );
        })}
        {/* čáry rezervované kapacity */}
        {rpSoucasna != null && (
          <line x1={x0} y1={y(rpSoucasna)} x2={x1} y2={y(rpSoucasna)} stroke="#e8590c" strokeWidth="1.5" strokeDasharray="5 3" />
        )}
        {rpNova != null && (
          <line x1={x0} y1={y(rpNova)} x2={x1} y2={y(rpNova)} stroke="#1971c2" strokeWidth="1.5" strokeDasharray="5 3" />
        )}
      </svg>
    </div>
  );
}
