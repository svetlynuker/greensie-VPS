/**
 * Pás KPI nad seznamem (CRM-22).
 *
 * Vznikl vytažením pásu, který měly původně jen Obchodní případy — pět seznamů
 * by jinak mělo pět skoro stejných kusů JSX a rozešly by se.
 *
 * Dvě pravidla, na kterých pás stojí:
 *   * čísla se počítají z **vyfiltrovaných** řádků, ne ze všech (jinak by tvrdil
 *     něco jiného, než je pod ním v tabulce vidět) — a když filtr běží, řekne to,
 *   * pás se nezobrazí, když není co počítat; prázdná lišta nad prázdnou tabulkou
 *     jen zabírá místo.
 *
 * Položka: `{ klic, label, hodnota, tise, title }`. `label` je text za hodnotou
 * („případů"), `hodnota` už naformátovaná. `tise` = doplňková informace menším
 * písmem (typicky „kolik z toho něco nemá").
 */
export default function KpiPas({ polozky, filtrovano = false, odkaz, zobrazit = true }) {
  const viditelne = (polozky || []).filter((p) => p && p.hodnota !== null && p.hodnota !== undefined);
  if (!zobrazit || viditelne.length === 0) return null;

  return (
    <div className="crm-kpi-pas">
      {viditelne.map((p, i) => (
        <span key={p.klic || i} className={p.tise ? "crm-tise" : undefined} title={p.title}>
          {p.pred ? `${p.pred} ` : ""}
          <b>{p.hodnota}</b>
          {p.label ? ` ${p.label}` : ""}
          {/* „(po filtru)" jen u prvního údaje – u každého by to byl šum. */}
          {i === 0 && filtrovano ? " (po filtru)" : ""}
        </span>
      ))}
      {odkaz && (
        <>
          <span className="crm-mezera" />
          <a className="crm-odkaz" href={odkaz.cesta}>
            {odkaz.text} →
          </a>
        </>
      )}
    </div>
  );
}
