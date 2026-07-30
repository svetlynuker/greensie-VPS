/**
 * Vykreslení vlastních (admin definovaných) polí do formuláře.
 *
 * Definice přicházejí z backendu (`vlastni_pole`), hodnoty jsou v `extra`.
 * Komponenta nic neukládá — jen hlásí změny nahoru, aby se uložily spolu se
 * zbytkem formuláře (jinak by se záznam ukládal na dvakrát a při chybě by
 * zůstal půl uložený).
 */
export default function VlastniPoleVstupy({ pole, hodnoty, onZmena, nadpis = "Doplňující údaje" }) {
  if (!pole || pole.length === 0) return null;

  function zmen(klic, hodnota) {
    onZmena({ ...(hodnoty || {}), [klic]: hodnota });
  }

  return (
    <>
      <div className="crm-sirka3 crm-oddelovac">
        <h4 className="crm-podnadpis">{nadpis}</h4>
      </div>
      {pole.map((p) => {
        const hodnota = (hodnoty || {})[p.klic];
        const popisek = `${p.nazev}${p.povinne ? " *" : ""}`;
        return (
          <div key={p.klic} className={p.typ === "dlouhy_text" ? "crm-sirka3" : undefined}>
            <label className="crm-label" htmlFor={`vp-${p.klic}`}>
              {popisek}
            </label>

            {p.typ === "dlouhy_text" ? (
              <textarea
                id={`vp-${p.klic}`}
                className="crm-pole"
                rows={3}
                value={hodnota ?? ""}
                onChange={(e) => zmen(p.klic, e.target.value)}
              />
            ) : p.typ === "ano_ne" ? (
              <label className="crm-zaskrtavaci">
                <input
                  id={`vp-${p.klic}`}
                  type="checkbox"
                  checked={Boolean(hodnota)}
                  onChange={(e) => zmen(p.klic, e.target.checked)}
                />
                {hodnota ? "Ano" : "Ne"}
              </label>
            ) : p.typ === "vyber" ? (
              <select
                id={`vp-${p.klic}`}
                className="crm-pole"
                value={hodnota ?? ""}
                onChange={(e) => zmen(p.klic, e.target.value)}
              >
                <option value="">— nevybráno —</option>
                {(p.volby || []).map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id={`vp-${p.klic}`}
                className="crm-pole"
                type={p.typ === "datum" ? "date" : "text"}
                inputMode={p.typ === "cislo" ? "decimal" : undefined}
                value={hodnota ?? ""}
                onChange={(e) => zmen(p.klic, e.target.value)}
              />
            )}

            {p.napoveda && <p className="crm-tise crm-napoveda">{p.napoveda}</p>}
          </div>
        );
      })}
    </>
  );
}
