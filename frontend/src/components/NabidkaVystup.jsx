// Vykreslení nabídky pro zákazníka z konfigurace (bloky) + resolvnutých hodnot.
// Používá se dvakrát: jako živý náhled v editoru a jako tisková A4 stránka.
// Interní data se sem nedostanou – server posílá jen zákaznická (sablona_katalog).

import GrafVyrobaSpotreba from "./GrafVyrobaSpotreba";
import GrafOdberu from "./GrafOdberu";
import { fmtDatum } from "../nabidkovac";

// Pole, která v kartě zvýrazníme (úspora = to hlavní, co zákazníka zajímá).
const ZVYRAZNIT = new Set([
  "uspora_kum_kc", "uspora_rok1_kc", "rocni_uspora_2026_kc", "pokryti_spotreby_fve",
]);

function Karta({ h, zvyraznit }) {
  if (!h) return null;
  return (
    <div className={"vy-karta" + (zvyraznit ? " zvyraznit" : "")}>
      <div className="k-nazev">{h.nazev}</div>
      <div className="k-hodnota">{h.hodnota_text}</div>
    </div>
  );
}

function BlokUdaje({ blok, hodnoty, tisk }) {
  // V tisku skryjeme pole bez hodnoty (—), v editoru je necháme (ať je vidět,
  // co se doplní po výpočtu).
  const klice = (blok.pole || []).filter((k) => {
    const h = hodnoty[k];
    if (!h) return false;
    if (tisk && (h.hodnota === null || h.hodnota === undefined)) return false;
    return true;
  });
  if (!klice.length) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Zatím není co zobrazit – spusť výpočet nabídky.</div>
      </div>
    );
  }
  const dvaSloupce = klice.length <= 2 || klice.length === 4;
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      {blok.text && <p className="vy-intro">{blok.text}</p>}
      <div className={"vy-karty" + (dvaSloupce ? " dva" : "")}>
        {klice.map((k) => (
          <Karta key={k} h={hodnoty[k]} zvyraznit={ZVYRAZNIT.has(k)} />
        ))}
      </div>
    </div>
  );
}

function BlokGraf({ blok, typReseni, graf, tisk }) {
  const maData = graf && (graf.mesice?.length || 0) > 0;
  if (!maData) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Graf se zobrazí po spuštění výpočtu.</div>
      </div>
    );
  }
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      <div className="vy-graf">
        {typReseni === "ppa" ? (
          <GrafVyrobaSpotreba graf={graf} />
        ) : (
          <GrafOdberu
            mesice={graf.mesice}
            bezBaterie={graf.bez_baterie_kw}
            sBaterii={graf.s_baterii_2026_kw}
            rpSoucasna={graf.rp_soucasna_kw}
            rpNova={graf.rp_nova_kw}
          />
        )}
      </div>
    </div>
  );
}

function BlokTabulka({ blok, tabulka, tisk }) {
  const vybrane = new Set(blok.pole || []);
  const sloupce = (tabulka?.sloupce || []).filter((s) => vybrane.has(s.klic));
  const indexy = sloupce.map((s) => (tabulka.sloupce || []).findIndex((x) => x.klic === s.klic));
  const radky = tabulka?.radky || [];
  if (!sloupce.length || !radky.length) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Tabulka se naplní po spuštění výpočtu.</div>
      </div>
    );
  }
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      <table className="vy-tabulka">
        <thead>
          <tr>{sloupce.map((s) => <th key={s.klic}>{s.nazev}</th>)}</tr>
        </thead>
        <tbody>
          {radky.map((r, i) => (
            <tr key={i}>{indexy.map((idx, j) => <td key={j}>{r[idx]}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BlokHlavicka({ blok, zakaznik }) {
  return (
    <div className="vy-hlavicka">
      {/* Branding obrázky zatím vynechány – jen jasně označené místo pro logo. */}
      <div className="vy-logo">MÍSTO PRO LOGO</div>
      <h1>{blok.nadpis || "Nabídka"}</h1>
      {blok.text && <div className="podnadpis">{blok.text}</div>}
      <div className="vy-prijemce">
        <span className="lbl">Nabídka pro: </span>
        <b>{zakaznik?.nazev || "—"}</b>
        {zakaznik?.adresa ? <span> · {zakaznik.adresa}</span> : null}
        {zakaznik?.datum ? (
          <div className="lbl" style={{ marginTop: 2 }}>Datum: {fmtDatum(zakaznik.datum)}</div>
        ) : null}
      </div>
    </div>
  );
}

export default function NabidkaVystup({ data, konfigurace, tisk = false }) {
  if (!data) return null;
  const bloky = (konfigurace?.bloky || []).filter((b) => b.viditelny);
  return (
    <div className={"vystup-sheet" + (tisk ? " vystup-tisk" : "")}>
      {bloky.map((blok) => {
        switch (blok.druh) {
          case "hlavicka":
            return <BlokHlavicka key={blok.id} blok={blok} zakaznik={data.zakaznik} />;
          case "text":
            return (
              <div className="vy-blok" key={blok.id}>
                {blok.nadpis && <h2>{blok.nadpis}</h2>}
                {blok.text && <p className="vy-text">{blok.text}</p>}
              </div>
            );
          case "udaje":
            return <BlokUdaje key={blok.id} blok={blok} hodnoty={data.hodnoty || {}} tisk={tisk} />;
          case "graf":
            return (
              <BlokGraf key={blok.id} blok={blok} typReseni={data.typ_reseni}
                graf={data.graf} tisk={tisk} />
            );
          case "tabulka":
            return <BlokTabulka key={blok.id} blok={blok} tabulka={data.tabulka} tisk={tisk} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
