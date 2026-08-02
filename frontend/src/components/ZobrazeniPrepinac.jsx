/**
 * Přepínač zobrazení kanban ↔ tabulka jako posuvník.
 *
 * Dřív to byly dvě záložky vedle sebe a nebylo na první pohled vidět, že jde
 * o dva režimy jedné věci, ne o dvě různé sekce. Posuvník ukazuje volbu jako
 * jeden ovladač se dvěma polohami: jezdec se přesune pod vybraný popisek.
 *
 * Ovládání je radiogroup, ne switch — popisky musí být vidět oba naráz, jinak
 * uživatel nepozná, kam ho kliknutí přepne. Šipky vlevo/vpravo přepínají,
 * takže se to dá obsloužit i bez myši.
 */
export default function ZobrazeniPrepinac({
  hodnota,
  onZmena,
  moznosti = [
    { klic: "kanban", popis: "Kanban" },
    { klic: "tabulka", popis: "Tabulka" },
  ],
  popisek = "Zobrazení",
}) {
  const index = Math.max(
    0,
    moznosti.findIndex((m) => m.klic === hodnota),
  );

  function klavesa(e) {
    const smer =
      e.key === "ArrowRight" || e.key === "ArrowDown"
        ? 1
        : e.key === "ArrowLeft" || e.key === "ArrowUp"
          ? -1
          : 0;
    if (!smer) return;
    e.preventDefault();
    // Dokola: z poslední polohy šipkou doprava zpátky na první.
    const dalsi = (index + smer + moznosti.length) % moznosti.length;
    onZmena(moznosti[dalsi].klic);
  }

  return (
    <div
      className="crm-prepinac"
      role="radiogroup"
      aria-label={popisek}
      onKeyDown={klavesa}
      style={{ "--pocet": moznosti.length, "--index": index }}
    >
      <span className="crm-prepinac-jezdec" aria-hidden="true" />
      {moznosti.map((m) => (
        <button
          key={m.klic}
          type="button"
          role="radio"
          aria-checked={m.klic === hodnota}
          // Do tabulátoru patří jen vybraná volba, uvnitř se pak chodí šipkami.
          tabIndex={m.klic === hodnota ? 0 : -1}
          className={`crm-prepinac-volba ${m.klic === hodnota ? "aktivni" : ""}`}
          onClick={() => onZmena(m.klic)}
        >
          {m.popis}
        </button>
      ))}
    </div>
  );
}
