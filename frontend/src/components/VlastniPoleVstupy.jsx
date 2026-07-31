/**
 * Vykreslení vlastních (admin definovaných) polí do formuláře.
 *
 * Definice přicházejí z backendu (`vlastni_pole`), hodnoty jsou v `extra`.
 * Komponenta nic neukládá — jen hlásí změny nahoru, aby se uložily spolu se
 * zbytkem formuláře (jinak by se záznam ukládal na dvakrát a při chybě by
 * zůstal půl uložený).
 */
// Nabídkovač má vlastní sadu tříd (nb-*) a jinou mřížku než CRM. Kdyby se sem
// natvrdo psaly crm-* třídy, pole by v detailu nabídky vypadala cize a přetekla
// by mimo mřížku formuláře.
const STYLY = {
  crm: { pole: "crm-pole", label: "crm-label", sirka: "crm-sirka3", nadpis: "crm-podnadpis" },
  // Vstupy v nabídkovači nesou nb-* (sedí do jeho mřížky), podnadpis zůstává
  // crm-* – je to tentýž prvek a nemá smysl mít pro něj dvě stejná pravidla.
  nb: { pole: "nb-pole", label: "nb-label", sirka: "nb-sirka2", nadpis: "crm-podnadpis" },
};

export default function VlastniPoleVstupy({
  pole,
  hodnoty,
  onZmena,
  nadpis = "Doplňující údaje",
  styl = "crm",
}) {
  if (!pole || pole.length === 0) return null;
  const t = STYLY[styl] || STYLY.crm;

  function zmen(klic, hodnota) {
    onZmena({ ...(hodnoty || {}), [klic]: hodnota });
  }

  return (
    <>
      <div className={`${t.sirka} crm-oddelovac`}>
        <h4 className={t.nadpis}>{nadpis}</h4>
      </div>
      {pole.map((p) => {
        const hodnota = (hodnoty || {})[p.klic];
        const popisek = `${p.nazev}${p.povinne ? " *" : ""}`;
        return (
          <div key={p.klic} className={p.typ === "dlouhy_text" ? t.sirka : undefined}>
            <label className={t.label} htmlFor={`vp-${p.klic}`}>
              {popisek}
            </label>

            {p.typ === "dlouhy_text" ? (
              <textarea
                id={`vp-${p.klic}`}
                className={t.pole}
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
                className={t.pole}
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
                className={t.pole}
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
