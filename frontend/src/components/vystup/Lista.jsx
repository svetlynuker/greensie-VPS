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
  // Přetečení a prázdné dlaždice jsou dvě různé věci: první se v PDF ořízne,
  // druhá z něj beze slova zmizí. Jedna hláška pro obojí by radila špatně.
  const pretekaji = problemy.filter((p) => p.typ !== "prazdny_udaj");
  const prazdne = problemy.filter((p) => p.typ === "prazdny_udaj");
  const rucnich = editor.rucnichHodnot || 0;

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
        <button
          className="fm-btn fm-primary"
          onClick={onTisk}
          disabled={tiskne || uklada}
          title="Vyrobí PDF, uloží ho k nabídce, propíše na Disk a otevře v nové záložce"
        >
          {tiskne ? "Vyrábím PDF…" : "Uložit do PDF"}
        </button>
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

      {pretekaji.length > 0 && (
        <div className="vy-problemy">
          <span>
            ⚠️{" "}
            {tvarPoctu(
              pretekaji.length,
              "Jeden prvek přetéká",
              "prvky přetékají",
              "prvků přetéká"
            )}{" "}
            přes okraj stránky. V PDF se ořízne, co je pod okrajem.
          </span>
          <Skoky problemy={pretekaji} editor={editor} onSkocNaStranku={onSkocNaStranku} />
        </div>
      )}

      {prazdne.length > 0 && (
        <div className="vy-problemy">
          <span>
            ⚠️{" "}
            {tvarPoctu(
              prazdne.length,
              "Jedna dlaždice nemá hodnotu",
              "dlaždice nemají hodnotu",
              "dlaždic nemá hodnotu"
            )}
            . Prázdná dlaždice se do PDF nevytiskne a zůstane po ní prázdné místo –
            buď ji smaž, nebo jí vyplň ruční hodnotu.
          </span>
          <Skoky problemy={prazdne} editor={editor} onSkocNaStranku={onSkocNaStranku} />
        </div>
      )}

      {rucnich > 0 && (
        <div className="vy-problemy rucni">
          <span>
            ✏️{" "}
            {tvarPoctu(
              rucnich,
              "Jedna hodnota je přepsaná ručně",
              "hodnoty jsou přepsané ručně",
              "hodnot je přepsaných ručně"
            )}
            . Do PDF jdou tak, jak jsou zadané, ne jak je spočítal výpočet.
          </span>
        </div>
      )}
    </div>
  );
}

/** České tvary podle počtu: 1 · 2–4 · 5 a víc. */
function tvarPoctu(pocet, jedna, malo, mnoho) {
  if (pocet === 1) return jedna;
  return `${pocet} ${pocet <= 4 ? malo : mnoho}`;
}

/** Odkazy na stránky s problémem – kliknutím se prvek vybere. */
function Skoky({ problemy, editor, onSkocNaStranku }) {
  return problemy.slice(0, 4).map((p) => (
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
  ));
}

function dalsiZoom(z) {
  return ZOOMY.find((x) => x > z) ?? ZOOMY[ZOOMY.length - 1];
}

function predchoziZoom(z) {
  const mensi = ZOOMY.filter((x) => x < z);
  return mensi.length ? mensi[mensi.length - 1] : ZOOMY[0];
}
