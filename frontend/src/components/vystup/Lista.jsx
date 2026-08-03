// Horní lišta editoru: navigace po stránkách, zoom, historie, uložení, tisk.

const ZOOMY = [0.5, 0.65, 0.8, 1, 1.25, 1.5];

export default function Lista({
  editor,
  nazev,
  zoom,
  onZoom,
  onZpetNaNabidku,
  onUloz,
  onTisk,
  // Právo `export` (soubor odchází z appky). Bez něj se tlačítko tisku
  // nekreslí — backend by PDF stejně nevyrobil (403).
  muzeTisknout = false,
  uklada,
  tiskne,
  neulozeno,
  zprava,
  chyba,
  aktivniStranka,
  onSkocNaStranku,
  deti,
}) {
  const stranky = editor.konfigurace?.stranky || [];
  const problemy = editor.problemy || [];

  return (
    <div className="vy-lista-horni np">
      <div className="vy-lista-radek">
        <button className="fm-btn" onClick={onZpetNaNabidku}>
          ← Zpět na nabídku
        </button>
        <h1>{nazev}</h1>

        <span className="sp" />

        <div className="vy-skupina" role="group" aria-label="Historie">
          <button
            className="fm-btn"
            onClick={editor.zpet}
            disabled={!editor.muzeZpet}
            title="Zpět (Ctrl+Z)"
          >
            ↶
          </button>
          <button
            className="fm-btn"
            onClick={editor.vpred}
            disabled={!editor.muzeVpred}
            title="Vpřed (Ctrl+Y)"
          >
            ↷
          </button>
        </div>

        <div className="vy-skupina" role="group" aria-label="Zvětšení">
          <button
            className="fm-btn"
            onClick={() => onZoom(predchoziZoom(zoom))}
            title="Zmenšit"
            disabled={zoom <= ZOOMY[0]}
          >
            −
          </button>
          <select
            className="vy-zoom"
            value={ZOOMY.includes(zoom) ? zoom : ""}
            onChange={(e) => onZoom(Number(e.target.value))}
            aria-label="Zvětšení papíru"
          >
            {!ZOOMY.includes(zoom) && <option value="">{Math.round(zoom * 100)} %</option>}
            {ZOOMY.map((z) => (
              <option key={z} value={z}>
                {Math.round(z * 100)} %
              </option>
            ))}
          </select>
          <button
            className="fm-btn"
            onClick={() => onZoom(dalsiZoom(zoom))}
            title="Zvětšit"
            disabled={zoom >= ZOOMY[ZOOMY.length - 1]}
          >
            +
          </button>
        </div>

        {zprava && <span className="vy-zprava">{zprava}</span>}
        {chyba && <span className="vy-chyba">{chyba}</span>}
        {neulozeno && !zprava && !chyba && (
          <span className="vy-neulozeno" title="Změny zatím nejsou uložené">
            • neuloženo
          </span>
        )}

        <button className="fm-btn" onClick={onUloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit"}
        </button>
        {muzeTisknout ? (
          <button
            className="fm-btn fm-primary"
            onClick={onTisk}
            disabled={tiskne || uklada}
            title="Vyrobí PDF, uloží ho k nabídce, propíše na Disk a otevře v nové záložce"
          >
            {tiskne ? "Vyrábím PDF…" : "Uložit do PDF"}
          </button>
        ) : (
          <span className="crm-tise" title="Rozvržení uložit můžeš, ale PDF vyrobí jen ten, kdo má právo na export dat.">
            bez práva na export
          </span>
        )}
      </div>

      <div className="vy-lista-radek druhy">
        <span className="vy-stranky-popis">Stránky:</span>
        <div className="vy-stranky">
          {stranky.map((s, i) => {
            const maProblem = problemy.some((p) => p.strankaId === s.id);
            return (
              <button
                key={s.id}
                className={
                  "vy-stranka-b" +
                  (s.id === aktivniStranka ? " aktivni" : "") +
                  (maProblem ? " problem" : "")
                }
                onClick={() => onSkocNaStranku(s.id)}
                title={maProblem ? "Na stránce něco přetéká" : `Stránka ${i + 1}`}
              >
                {i + 1}
              </button>
            );
          })}
        </div>

        <div className="vy-skupina">
          <button className="fm-btn" onClick={() => editor.pridejStranku()} title="Přidat stránku na konec">
            + stránka
          </button>
          <button
            className="fm-btn"
            onClick={() => editor.duplikujStranku(aktivniStranka)}
            title="Duplikovat zobrazenou stránku"
          >
            Duplikovat
          </button>
          <button
            className="fm-btn"
            onClick={() => editor.presunStranku(aktivniStranka, -1)}
            title="Posunout stránku výš"
          >
            ↑
          </button>
          <button
            className="fm-btn"
            onClick={() => editor.presunStranku(aktivniStranka, 1)}
            title="Posunout stránku níž"
          >
            ↓
          </button>
          <button
            className="fm-btn nebezpecne"
            onClick={() => {
              if (window.confirm("Smazat tuhle stránku i se vším, co na ní je?")) {
                editor.smazStranku(aktivniStranka);
              }
            }}
            title="Smazat zobrazenou stránku"
          >
            Smazat stránku
          </button>
        </div>

        <span className="sp" />
        {deti}
      </div>

      {problemy.length > 0 && (
        <div className="vy-problemy">
          <span>
            ⚠️ {problemy.length === 1 ? "Jeden prvek přetéká" : `${problemy.length} prvků přetéká`}{" "}
            přes okraj stránky – v PDF se ořízne.
          </span>
          {problemy.slice(0, 4).map((p) => (
            <button
              key={p.prvekId}
              className="vy-problem-b"
              onClick={() => {
                onSkocNaStranku(p.strankaId);
                editor.vyber(p.prvekId);
              }}
            >
              str. {p.cisloStranky}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function dalsiZoom(z) {
  return ZOOMY.find((x) => x > z) ?? ZOOMY[ZOOMY.length - 1];
}

function predchoziZoom(z) {
  const mensi = ZOOMY.filter((x) => x < z);
  return mensi.length ? mensi[mensi.length - 1] : ZOOMY[0];
}
