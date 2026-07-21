// Grafický editor nabídkové šablony: seznam bloků (zapnout/vypnout, přesunout,
// upravit nadpis a text, vybrat zobrazená pole). Změny hlásí přes onZmena;
// stav drží nadřazená stránka (NabidkaVystupStranka), která zajišťuje náhled.

const DRUH_POPIS = {
  hlavicka: "Hlavička",
  text: "Text",
  udaje: "Údaje",
  graf: "Graf",
  tabulka: "Tabulka",
};

export default function NabidkaVystupEditor({ konfigurace, katalog, onZmena }) {
  const bloky = konfigurace?.bloky || [];
  const katPole = katalog?.pole || [];
  const katSloupce = katalog?.tabulka_sloupce || [];

  function zmenBlok(idx, zmena) {
    const noveBloky = bloky.map((b, i) => (i === idx ? { ...b, ...zmena } : b));
    onZmena({ ...konfigurace, bloky: noveBloky });
  }

  function presun(idx, smer) {
    const j = idx + smer;
    if (j < 0 || j >= bloky.length) return;
    const noveBloky = [...bloky];
    [noveBloky[idx], noveBloky[j]] = [noveBloky[j], noveBloky[idx]];
    onZmena({ ...konfigurace, bloky: noveBloky });
  }

  function presunPole(idx, poleIdx, smer) {
    const b = bloky[idx];
    const j = poleIdx + smer;
    const pole = [...(b.pole || [])];
    if (j < 0 || j >= pole.length) return;
    [pole[poleIdx], pole[j]] = [pole[j], pole[poleIdx]];
    zmenBlok(idx, { pole });
  }

  function prepniPole(idx, klic) {
    const b = bloky[idx];
    const pole = b.pole || [];
    const nove = pole.includes(klic) ? pole.filter((k) => k !== klic) : [...pole, klic];
    zmenBlok(idx, { pole: nove });
  }

  return (
    <div>
      {bloky.map((blok, idx) => (
        <div key={blok.id} className={"ed-blok" + (blok.viditelny ? "" : " skryty")}>
          <div className="ed-hlava">
            <label className="ed-checkbox" title="Zobrazit v nabídce">
              <input
                type="checkbox"
                checked={!!blok.viditelny}
                onChange={(e) => zmenBlok(idx, { viditelny: e.target.checked })}
              />
            </label>
            <span className="druh">{DRUH_POPIS[blok.druh] || blok.druh}</span>
            <span className="sp" />
            <button className="ed-btn" onClick={() => presun(idx, -1)} disabled={idx === 0} title="Nahoru">↑</button>
            <button className="ed-btn" onClick={() => presun(idx, 1)} disabled={idx === bloky.length - 1} title="Dolů">↓</button>
          </div>

          {/* Nadpis (u hlavičky = titulek nabídky) */}
          {blok.druh !== "graf" && (
            <input
              className="nb-pole ed-pole-nadpis"
              value={blok.nadpis || ""}
              placeholder="Nadpis bloku"
              onChange={(e) => zmenBlok(idx, { nadpis: e.target.value })}
            />
          )}
          {blok.druh === "graf" && (
            <input
              className="nb-pole ed-pole-nadpis"
              value={blok.nadpis || ""}
              placeholder="Nadpis grafu"
              onChange={(e) => zmenBlok(idx, { nadpis: e.target.value })}
            />
          )}

          {/* Text: hlavička = podnadpis, text blok = odstavec, údaje = úvodní věta */}
          {(blok.druh === "text" || blok.druh === "hlavicka" || blok.druh === "udaje") && (
            <textarea
              className="nb-pole ed-textarea"
              value={blok.text || ""}
              placeholder={
                blok.druh === "hlavicka"
                  ? "Podnadpis (nepovinné)"
                  : blok.druh === "udaje"
                  ? "Úvodní věta nad údaji (nepovinné)"
                  : "Text odstavce"
              }
              onChange={(e) => zmenBlok(idx, { text: e.target.value })}
            />
          )}

          {/* Výběr zobrazených údajů */}
          {blok.druh === "udaje" && (
            <PoleVyber
              vybrana={blok.pole || []}
              katalog={katPole}
              onPrepni={(klic) => prepniPole(idx, klic)}
              onPresun={(poleIdx, smer) => presunPole(idx, poleIdx, smer)}
            />
          )}

          {/* Výběr sloupců tabulky */}
          {blok.druh === "tabulka" && (
            <SloupceVyber
              vybrane={blok.pole || []}
              katalog={katSloupce}
              onPrepni={(klic) => prepniPole(idx, klic)}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// Výběr údajů: nahoře vybraná pole (s pořadím ↑↓), dole nabídka k přidání.
function PoleVyber({ vybrana, katalog, onPrepni, onPresun }) {
  const mapa = Object.fromEntries(katalog.map((p) => [p.klic, p]));
  const nevybrana = katalog.filter((p) => !vybrana.includes(p.klic));
  return (
    <div>
      <div className="ed-sekce-nadpis">Zobrazené údaje (pořadí ↑↓)</div>
      {vybrana.length === 0 && <div className="vy-prazdno">Žádné – vyber níže.</div>}
      {vybrana.map((klic, i) => (
        <div className="ed-checkbox" key={klic}>
          <span className="sp">{mapa[klic]?.nazev || klic}</span>
          <button className="ed-btn" onClick={() => onPresun(i, -1)} disabled={i === 0}>↑</button>
          <button className="ed-btn" onClick={() => onPresun(i, 1)} disabled={i === vybrana.length - 1}>↓</button>
          <button className="ed-btn" onClick={() => onPrepni(klic)} title="Odebrat">✕</button>
        </div>
      ))}
      {nevybrana.length > 0 && (
        <>
          <div className="ed-sekce-nadpis">Přidat údaj</div>
          {nevybrana.map((p) => (
            <label className="ed-checkbox" key={p.klic}>
              <input type="checkbox" checked={false} onChange={() => onPrepni(p.klic)} />
              <span className="sp">{p.nazev}</span>
            </label>
          ))}
        </>
      )}
    </div>
  );
}

function SloupceVyber({ vybrane, katalog, onPrepni }) {
  return (
    <div>
      <div className="ed-sekce-nadpis">Sloupce tabulky</div>
      {katalog.map((s) => (
        <label className="ed-checkbox" key={s.klic}>
          <input
            type="checkbox"
            checked={vybrane.includes(s.klic)}
            onChange={() => onPrepni(s.klic)}
          />
          <span className="sp">{s.nazev}</span>
        </label>
      ))}
    </div>
  );
}
