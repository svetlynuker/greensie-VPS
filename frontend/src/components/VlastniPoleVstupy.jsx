/**
 * Vykreslení vlastních (admin definovaných) polí do formuláře.
 *
 * Definice přicházejí z backendu (`vlastni_pole`), hodnoty jsou v `extra`.
 * Komponenta sama nic neukládá — jen hlásí změny nahoru. Hlásit je umí dvěma
 * způsoby a záleží jen na tom, který prop formulář pošle:
 *
 *  - `onZmena(cele_extra)` — celý objekt `extra` naráz. To je pro formuláře
 *    s tlačítkem „Uložit“: záznam se pak ukládá jedním požadavkem a při chybě
 *    nezůstane půl uložený.
 *  - `onZmenaPole(klic, hodnota, ihned)` — jedno pole zvlášť, pro formuláře
 *    s automatickým ukládáním (`useZaznamAutosave`). Ukládat celé `extra` po
 *    každém znaku by přepisovalo i pole, kterých se člověk nedotkl — včetně
 *    cizích změn, tiše.
 *
 * `ihned` říká, jestli se má uložit bez prodlevy: u výběru, zaškrtávátka,
 * data a čísla je změna hotové rozhodnutí, u textu je to rozepsaná věta a má
 * smysl počkat, než člověk dopíše.
 *
 * Když přijdou oba propy, zavolají se oba (formulář může držet lokální kopii
 * `extra` a zároveň ukládat po polích).
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

/** Splňuje záznam podmínku viditelnosti pole? (CRM-33)
 *
 *  Stejná logika jako na backendu (`vlastni_pole.viditelne`) — porovnává se
 *  jako text bez ohledu na velikost písmen. Kdyby se lišila, pole by šlo
 *  vyplnit, ale neuložit (nebo naopak), a nebylo by poznat proč.
 *
 *  `zdroj` jsou i vlastní pole záznamu i jeho běžná pole (kategorie, typ…),
 *  aby šlo podmínit i na tom, co není vlastní pole.
 */
export function poleViditelne(p, zdroj) {
  const klic = (p.zavislost_pole || "").trim();
  if (!klic) return true;
  const ocekavana = (p.zavislost_hodnota || "").trim().toLowerCase();
  const skutecna = (zdroj || {})[klic];
  if (Array.isArray(skutecna)) {
    return skutecna.some((x) => String(x).trim().toLowerCase() === ocekavana);
  }
  return String(skutecna ?? "").trim().toLowerCase() === ocekavana;
}

/** Pole rozdělená do skupin v pořadí, v jakém se mají vykreslit (CRM-33). */
export function doSkupin(pole) {
  const skupiny = [];
  for (const p of pole || []) {
    const nazev = (p.skupina || "").trim();
    let cil = skupiny.find((s) => s.nazev === nazev);
    if (!cil) {
      cil = { nazev, pole: [] };
      skupiny.push(cil);
    }
    cil.pole.push(p);
  }
  return skupiny;
}

// Typy, u kterých je změna hotové rozhodnutí, ne rozepsaná věta — ukládají se
// bez prodlevy. Číslo se sem vejde taky: mění se přes vstup, ale člověk ho
// buď zadá celé, nebo vůbec, a čekat na dopsání nemá u čeho.
const IHNED_TYPY = new Set(["ano_ne", "vyber", "datum", "cislo"]);

export default function VlastniPoleVstupy({
  pole,
  hodnoty,
  onZmena,
  // Nepovinný: hlášení změny po jednom poli (automatické ukládání).
  onZmenaPole,
  nadpis = "Doplňující údaje",
  styl = "crm",
  // Hodnoty běžných polí záznamu (kategorie, typ…) pro podmíněnou viditelnost.
  zaznam = null,
}) {
  const t = STYLY[styl] || STYLY.crm;
  const zdroj = { ...(zaznam || {}), ...(hodnoty || {}) };
  // Skryté pole se nevykresluje ani nevaliduje — backend to má stejně.
  const videt = (pole || []).filter((p) => poleViditelne(p, zdroj));
  if (videt.length === 0) return null;

  // Bere celou definici pole, ne jen klíč: z typu se pozná, jestli se má
  // uložit hned. Kdyby se `ihned` psalo na každém volání zvlášť, dřív nebo
  // později by u jednoho vstupu chybělo a ten by se ukládal s prodlevou.
  function zmen(p, hodnota) {
    if (onZmena) onZmena({ ...(hodnoty || {}), [p.klic]: hodnota });
    if (onZmenaPole) onZmenaPole(p.klic, hodnota, IHNED_TYPY.has(p.typ));
  }

  return (
    <>
      {doSkupin(videt).map((skupina) => (
        <div key={skupina.nazev || "_zakladni"} style={{ display: "contents" }}>
      <div className={`${t.sirka} crm-oddelovac`}>
        <h4 className={t.nadpis}>{skupina.nazev || nadpis}</h4>
      </div>
      {skupina.pole.map((p) => {
        const hodnota = (hodnoty || {})[p.klic];
        const popisek = `${p.nazev}${p.povinne ? " *" : ""}`;
        // Výpočtové pole (CRM-34) se nevyplňuje — ukáže se výsledek, který
        // spočítal backend. Editovatelné pole by svádělo k přepsání hodnoty,
        // která se stejně při dalším načtení přepočítá.
        if ((p.vzorec || "").trim()) {
          return (
            <div key={p.klic}>
              <label className={t.label}>{p.nazev}</label>
              <div className="crm-pole-vypocet" title={`Počítá se: ${p.vzorec}`}>
                {hodnota === undefined || hodnota === null || hodnota === ""
                  ? "—"
                  : String(hodnota)}
              </div>
              {p.napoveda && <p className="crm-tise crm-napoveda">{p.napoveda}</p>}
            </div>
          );
        }

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
                onChange={(e) => zmen(p, e.target.value)}
              />
            ) : p.typ === "ano_ne" ? (
              <label className="crm-zaskrtavaci">
                <input
                  id={`vp-${p.klic}`}
                  type="checkbox"
                  checked={Boolean(hodnota)}
                  onChange={(e) => zmen(p, e.target.checked)}
                />
                {hodnota ? "Ano" : "Ne"}
              </label>
            ) : p.typ === "vyber" ? (
              <select
                id={`vp-${p.klic}`}
                className={t.pole}
                value={hodnota ?? ""}
                onChange={(e) => zmen(p, e.target.value)}
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
                onChange={(e) => zmen(p, e.target.value)}
              />
            )}

            {p.napoveda && <p className="crm-tise crm-napoveda">{p.napoveda}</p>}
          </div>
        );
      })}
        </div>
      ))}
    </>
  );
}
