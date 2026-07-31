import { useEffect, useState } from "react";
import { hodnotaRadku, moznostiSloupce } from "../crmFiltry";
import { stahniCsv } from "../crmExport";
import { nactiNaStranku, ulozNaStranku, VELIKOSTI_STRANKY } from "../nastaveniTabulky";

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
  // Základ názvu exportovaného souboru („pripady" → pripady-2026-07-30.csv).
  // Bez něj se tlačítko exportu nekreslí.
  exportNazev = null,
  // Výběr řádků pro hromadné akce (CRM-19). Bez `onVybrane` se sloupec
  // se zaškrtávátky vůbec nekreslí — v seznamech, kde hromadné akce nejsou,
  // by jen mátl.
  vybrane = null,
  onVybrane = null,
  // Rozvržení sloupců (CRM-28). Bez `onRozvrzeni` se tlačítko nekreslí —
  // tabulka pak funguje přesně jako dřív.
  vsechnySloupce = null,
  rozvrzeni = null,
  onRozvrzeni = null,
}) {
  const [filtryOtevrene, setFiltryOtevrene] = useState(false);
  const [sloupceOtevrene, setSloupceOtevrene] = useState(false);
  // Kolik řádků ukázat (CRM-38). Stránkuje se AŽ PO FILTRU — jinak by se
  // filtrovalo jen v první stránce a seznam by lhal.
  const [naStranku, setNaStranku] = useState(() => nactiNaStranku());
  const [stranka, setStranka] = useState(0);

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

  const vyberAktivni = Boolean(onVybrane);
  const vsechnyVybrane =
    vyberAktivni && radky.length > 0 && radky.every((r) => vybrane?.includes(r.id));

  function prepniRadek(id) {
    const set = new Set(vybrane || []);
    if (set.has(id)) set.delete(id);
    else set.add(id);
    // Pořadí výběru se drží podle POŘADÍ V TABULCE, ne podle kliknutí — na něm
    // závisí, komu vyjde jaký čas při plánování aktivit za sebou.
    onVybrane(radky.filter((r) => set.has(r.id)).map((r) => r.id));
  }

  // Když filtr zúží seznam, je nutné se vrátit na první stránku – jinak by
  // člověk koukal na prázdnou pátou stránku a myslel si, že nic nenašel.
  useEffect(() => {
    setStranka(0);
  }, [radky.length, naStranku]);

  const pocetStranek = naStranku > 0 ? Math.ceil(radky.length / naStranku) : 1;
  const aktualniStranka = Math.min(stranka, Math.max(0, pocetStranek - 1));
  const videt =
    naStranku > 0
      ? radky.slice(aktualniStranka * naStranku, (aktualniStranka + 1) * naStranku)
      : radky;

  function zmenNaStranku(hodnota) {
    setNaStranku(hodnota);
    ulozNaStranku(hodnota);
  }

  function prepniSloupec(klic) {
    const skryte = new Set(rozvrzeni?.skryte || []);
    if (skryte.has(klic)) skryte.delete(klic);
    else skryte.add(klic);
    onRozvrzeni({ ...(rozvrzeni || {}), skryte: [...skryte] });
  }

  /** Posun sloupce o jednu pozici. Pořadí se ukládá jako úplný seznam klíčů,
   *  aby nezáleželo na tom, co se mezitím přidalo do definic. */
  function presunSloupec(klic, smer) {
    const poradi = (vsechnySloupce || []).map((x) => x.klic);
    const ulozene = rozvrzeni?.poradi?.length ? [...rozvrzeni.poradi] : poradi;
    // Doplnit klíče, které v uloženém pořadí ještě nejsou (nové vlastní pole).
    for (const k of poradi) if (!ulozene.includes(k)) ulozene.push(k);
    const i = ulozene.indexOf(klic);
    const j = i + smer;
    if (i < 0 || j < 0 || j >= ulozene.length) return;
    [ulozene[i], ulozene[j]] = [ulozene[j], ulozene[i]];
    onRozvrzeni({ ...(rozvrzeni || {}), poradi: ulozene });
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
        {onRozvrzeni && vsechnySloupce && (
          <button
            className={`fm-btn crm-btn-maly ${sloupceOtevrene ? "fm-primary" : ""}`}
            onClick={() => setSloupceOtevrene((x) => !x)}
            title="Které sloupce vidíš a v jakém pořadí"
          >
            ⋮⋮ Sloupce
            {(rozvrzeni?.skryte || []).length > 0
              ? ` (${vsechnySloupce.length - (rozvrzeni.skryte || []).length}/${vsechnySloupce.length})`
              : ""}
          </button>
        )}
        {exportNazev && (
          <button
            className="fm-btn crm-btn-maly"
            onClick={() => stahniCsv(exportNazev, sloupce, radky, vykresli)}
            disabled={radky.length === 0}
            title={
              radky.length === 0
                ? "Není co exportovat"
                : "Stáhne přesně to, co je v tabulce — se filtrem i řazením"
            }
          >
            ↓ Export CSV ({radky.length})
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

      {sloupceOtevrene && onRozvrzeni && vsechnySloupce && (
        <div className="crm-sloupce-panel">
          <div className="crm-sloupce-hlava">
            <b>Sloupce tabulky</b>
            <span className="crm-tise">
              Zaškrtnuté jsou vidět. Šipky mění pořadí. Ukládá se to k tvému účtu.
            </span>
            <span className="crm-mezera" />
            <button
              className="fm-btn crm-btn-maly"
              onClick={() => onRozvrzeni({ skryte: [], poradi: [] })}
            >
              Vrátit výchozí
            </button>
          </div>
          <ul className="crm-sloupce-seznam">
            {sloupce.concat(
              // Skryté sloupce v `sloupce` nejsou — musí se dobrat z úplného
              // seznamu, jinak by je nešlo zapnout zpátky.
              vsechnySloupce.filter((v) => !sloupce.some((x) => x.klic === v.klic))
            ).map((sl) => {
              const skryty = (rozvrzeni?.skryte || []).includes(sl.klic);
              return (
                <li key={sl.klic} className={skryty ? "skryty" : undefined}>
                  <label className="crm-zaskrtavaci">
                    <input
                      type="checkbox"
                      checked={!skryty}
                      onChange={() => prepniSloupec(sl.klic)}
                    />
                    {sl.nazev}
                  </label>
                  <span className="crm-mezera" />
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => presunSloupec(sl.klic, -1)}
                    title="Posunout doleva"
                  >
                    ←
                  </button>
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => presunSloupec(sl.klic, 1)}
                    title="Posunout doprava"
                  >
                    →
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div className="crm-scroll">
        <table className="crm-tabulka">
          <thead>
            <tr>
              {vyberAktivni && (
                <th className="crm-th-vyber">
                  <input
                    type="checkbox"
                    checked={vsechnyVybrane}
                    onChange={() =>
                      onVybrane(vsechnyVybrane ? [] : radky.map((r) => r.id))
                    }
                    title={vsechnyVybrane ? "Odznačit vše" : "Označit vše, co je vidět"}
                    aria-label="Označit vše"
                  />
                </th>
              )}
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
                {vyberAktivni && <th />}
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
            {videt.map((radek) => (
              <tr
                key={radek.id}
                className={vybrane?.includes(radek.id) ? "crm-radek-vybrany" : undefined}
                onClick={onOtevri ? () => onOtevri(radek) : undefined}
                style={onOtevri ? undefined : { cursor: "default" }}
              >
                {vyberAktivni && (
                  <td
                    className="crm-td-vyber"
                    // Klik na zaškrtávátko nesmí otevřít detail řádku.
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      type="checkbox"
                      checked={vybrane?.includes(radek.id) || false}
                      onChange={() => prepniRadek(radek.id)}
                      aria-label="Označit řádek"
                    />
                  </td>
                )}
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
                <td colSpan={sloupce.length + (vyberAktivni ? 1 : 0)} className="crm-prazdno">
                  {prazdneHlaseni}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Stránkování (CRM-38). Ukazuje se, jen když je co stránkovat — u pěti
          řádků by lišta byla jen šum. */}
      {(radky.length > VELIKOSTI_STRANKY[0] || naStranku > 0) && radky.length > 0 && (
        <div className="crm-strankovani">
          <span className="crm-tise">Řádků na stránku:</span>
          <span className="gs-seg">
            {VELIKOSTI_STRANKY.map((v) => (
              <button
                key={v}
                onClick={() => zmenNaStranku(v)}
                aria-pressed={naStranku === v}
              >
                {v === 0 ? "vše" : v}
              </button>
            ))}
          </span>
          <span className="crm-mezera" />
          {pocetStranek > 1 && (
            <>
              <button
                className="fm-btn crm-btn-maly"
                onClick={() => setStranka(aktualniStranka - 1)}
                disabled={aktualniStranka === 0}
              >
                ← Předchozí
              </button>
              <span className="crm-tise">
                {aktualniStranka * naStranku + 1}–
                {Math.min((aktualniStranka + 1) * naStranku, radky.length)} z {radky.length}
              </span>
              <button
                className="fm-btn crm-btn-maly"
                onClick={() => setStranka(aktualniStranka + 1)}
                disabled={aktualniStranka >= pocetStranek - 1}
              >
                Další →
              </button>
            </>
          )}
        </div>
      )}
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
