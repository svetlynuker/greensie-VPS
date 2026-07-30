import { useState } from "react";
import { OPERATORY, hodnotaRadku, moznostiSloupce } from "../crmFiltry";

/**
 * Tabulka CRM s řazením kliknutím na hlavičku a filtrem u každého sloupce.
 *
 * Jedna komponenta pro všechny sekce – jinak by se hlavička, filtr a řazení
 * v pěti tabulkách rozešly. Sloupce jsou deklarativní (`crmFiltry.js`), takže
 * co je ve filtru, je i v tabulce, a naopak.
 *
 * Filtry sloupců a uložené filtry jsou TÉŽ podmínky: řádek filtrů jen zapisuje
 * do stejného seznamu, který používá uložený filtr. Díky tomu se dá cokoli
 * naklikaného uložit jako vlastní filtr, aniž by se to muselo zadávat znovu.
 */
export default function CrmTabulka({
  sloupce,
  radky,
  vsechnyRadky,
  razeni,
  onRazeni,
  podminky,
  onPodminky,
  onOtevri,
  vykresli,
  prazdneHlaseni = "Nic k zobrazení.",
}) {
  const [filtryOtevrene, setFiltryOtevrene] = useState(false);

  /** Klik na hlavičku: bez shiftu nastaví jediný klíč, se shiftem přidá další
   *  úroveň – tím se dá řadit „podle stavu, pak podle čísla" bez editoru. */
  function prepniRazeni(klic, shift) {
    const stavajici = (razeni || []).find((r) => r.pole === klic);
    const novy = { pole: klic, smer: stavajici?.smer === "asc" ? "desc" : "asc" };
    if (!shift) {
      onRazeni([novy]);
      return;
    }
    const ostatni = (razeni || []).filter((r) => r.pole !== klic);
    onRazeni([...ostatni, novy]);
  }

  function nastavFiltr(klic, zmena) {
    const bez = (podminky || []).filter((p) => p.pole !== klic || p.zdroj !== "sloupec");
    if (!zmena) {
      onPodminky(bez);
      return;
    }
    onPodminky([...bez, { ...zmena, pole: klic, zdroj: "sloupec" }]);
  }

  const filtrSloupce = (klic) =>
    (podminky || []).find((p) => p.pole === klic && p.zdroj === "sloupec");

  const pocetFiltruSloupcu = (podminky || []).filter((p) => p.zdroj === "sloupec").length;

  return (
    <>
      <div className="crm-tabulka-lista">
        <button
          className={`fm-btn crm-btn-maly ${filtryOtevrene ? "fm-primary" : ""}`}
          onClick={() => setFiltryOtevrene((s) => !s)}
          title="Filtr u každého sloupce"
        >
          ⌕ Filtry sloupců{pocetFiltruSloupcu > 0 ? ` (${pocetFiltruSloupcu})` : ""}
        </button>
        {pocetFiltruSloupcu > 0 && (
          <button
            className="fm-btn crm-btn-maly"
            onClick={() => onPodminky((podminky || []).filter((p) => p.zdroj !== "sloupec"))}
          >
            Zrušit filtry sloupců
          </button>
        )}
        <span className="crm-mezera" />
        {(razeni || []).length > 0 && (
          <span className="crm-tise">
            Řazení:{" "}
            {razeni
              .map((r, i) => {
                const def = sloupce.find((s) => s.klic === r.pole);
                return `${i + 1}. ${def?.nazev || r.pole} ${r.smer === "desc" ? "↓" : "↑"}`;
              })
              .join(" · ")}
            {" — "}
            <span title="Shift + klik na hlavičku přidá další úroveň řazení">
              shift+klik = další úroveň
            </span>
          </span>
        )}
      </div>

      <div className="crm-scroll">
        <table className="crm-tabulka">
          <thead>
            <tr>
              {sloupce.map((s) => {
                const r = (razeni || []).find((x) => x.pole === s.klic);
                const uroven = (razeni || []).findIndex((x) => x.pole === s.klic);
                return (
                  <th
                    key={s.klic}
                    className={`crm-th-razeni ${s.vpravo ? "crm-vpravo" : ""}`}
                    onClick={(e) => prepniRazeni(s.klic, e.shiftKey)}
                    title="Klik = řadit, shift+klik = přidat další úroveň řazení"
                  >
                    {s.nazev}
                    {r && (
                      <span className="crm-razeni-znak">
                        {r.smer === "desc" ? "↓" : "↑"}
                        {(razeni || []).length > 1 && <sup>{uroven + 1}</sup>}
                      </span>
                    )}
                  </th>
                );
              })}
            </tr>
            {filtryOtevrene && (
              <tr className="crm-radek-filtru">
                {sloupce.map((s) => (
                  <th key={s.klic}>
                    <FiltrSloupce
                      sloupec={s}
                      hodnota={filtrSloupce(s.klic)}
                      moznosti={
                        s.typ === "vyber" || s.typ === "seznam"
                          ? moznostiSloupce(vsechnyRadky, s.klic)
                          : []
                      }
                      onZmena={(z) => nastavFiltr(s.klic, z)}
                    />
                  </th>
                ))}
              </tr>
            )}
          </thead>
          <tbody>
            {radky.map((radek) => (
              <tr
                key={radek.id}
                onClick={onOtevri ? () => onOtevri(radek) : undefined}
                style={onOtevri ? undefined : { cursor: "default" }}
              >
                {sloupce.map((s) => (
                  <td key={s.klic} className={s.vpravo ? "crm-vpravo" : undefined}>
                    {vykresli
                      ? vykresli(radek, s)
                      : String(hodnotaRadku(radek, s.klic) ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
            {radky.length === 0 && (
              <tr>
                <td colSpan={sloupce.length} className="crm-prazdno">
                  {prazdneHlaseni}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Filtr jednoho sloupce – tvar podle typu (text, číslo/datum od-do, výběr). */
function FiltrSloupce({ sloupec, hodnota, moznosti, onZmena }) {
  const typ = sloupec.typ || "text";

  if (typ === "vyber" || typ === "seznam") {
    return (
      <select
        className="crm-pole crm-filtr-pole"
        value={hodnota?.hodnota ?? ""}
        onChange={(e) =>
          onZmena(
            e.target.value
              ? { operator: typ === "seznam" ? "obsahuje" : "je", hodnota: e.target.value }
              : null
          )
        }
        onClick={(e) => e.stopPropagation()}
      >
        <option value="">vše</option>
        {moznosti.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    );
  }

  if (typ === "ano_ne") {
    return (
      <select
        className="crm-pole crm-filtr-pole"
        value={hodnota?.hodnota === undefined ? "" : hodnota.hodnota ? "ano" : "ne"}
        onChange={(e) =>
          onZmena(e.target.value ? { operator: "je", hodnota: e.target.value === "ano" } : null)
        }
        onClick={(e) => e.stopPropagation()}
      >
        <option value="">vše</option>
        <option value="ano">ano</option>
        <option value="ne">ne</option>
      </select>
    );
  }

  if (typ === "cislo" || typ === "penize" || typ === "datum") {
    const [od = "", do_ = ""] = Array.isArray(hodnota?.hodnota) ? hodnota.hodnota : ["", ""];
    const zmen = (novyOd, novyDo) => {
      if (!novyOd && !novyDo) onZmena(null);
      else onZmena({ operator: "mezi", hodnota: [novyOd, novyDo] });
    };
    return (
      <div className="crm-filtr-rozsah" onClick={(e) => e.stopPropagation()}>
        <input
          className="crm-pole crm-filtr-pole"
          type={typ === "datum" ? "date" : "number"}
          value={od}
          placeholder="od"
          onChange={(e) => zmen(e.target.value, do_)}
        />
        <input
          className="crm-pole crm-filtr-pole"
          type={typ === "datum" ? "date" : "number"}
          value={do_}
          placeholder="do"
          onChange={(e) => zmen(od, e.target.value)}
        />
      </div>
    );
  }

  return (
    <input
      className="crm-pole crm-filtr-pole"
      value={hodnota?.hodnota ?? ""}
      placeholder="obsahuje…"
      onChange={(e) => onZmena(e.target.value ? { operator: "obsahuje", hodnota: e.target.value } : null)}
      onClick={(e) => e.stopPropagation()}
    />
  );
}
