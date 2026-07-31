import { useState } from "react";
import Iniciraly from "./Iniciraly";
import { fmtKcKratce, fmtDatum, jePoTerminu, nazvyKategorii, tridaBarvy } from "../crm";

/**
 * Kanban se sloupci podle stavů pipeline a přetahováním dlaždic.
 *
 * Sloupce nejsou v kódu – přicházejí z tabulky stavů, takže je vedení může
 * měnit v nastavení CRM bez zásahu programátora.
 *
 * Přetahování jde přes nativní HTML5 drag & drop; appka má záměrně nulové UI
 * závislosti, takže se sem netahá knihovna. Klávesová obsluha je zajištěná
 * jinak: dlaždice má na sobě rozbalovací volbu stavu, aby se dal záznam
 * přesunout i bez myši (a na mobilu, kde drag & drop nefunguje).
 *
 * `dlazdice` je volitelný render obsahu dlaždice. Bez něj se kreslí obchodní
 * případ; sekce Nabídky si předá vlastní, aby nemusel existovat druhý kanban.
 *
 * `kategorie` je seznam z `crmKategorie()` – jen k přeložení klíče na název.
 * Kanban si ho sám nenačítá, aby ho stránka nemusela tahat dvakrát.
 */
export default function Kanban({
  sloupce,
  onPresun,
  onOtevri,
  dlazdice = null,
  kategorie = [],
}) {
  const [nesu, setNesu] = useState(null); // id přetahovaného záznamu
  const [nad, setNad] = useState(null); // klíč stavu, nad kterým visí

  function zacniNest(e, zaznam) {
    setNesu(zaznam.id);
    e.dataTransfer.setData("text/plain", String(zaznam.id));
    e.dataTransfer.effectAllowed = "move";
  }

  function pust(e, stavKlic) {
    e.preventDefault();
    setNad(null);
    const id = Number(e.dataTransfer.getData("text/plain") || nesu);
    setNesu(null);
    if (!id) return;
    // Hledáme, odkud dlaždice přišla – přesun do stejného sloupce nemá smysl.
    const zdroj = sloupce.find((s) => s.zaznamy.some((z) => z.id === id));
    if (zdroj && zdroj.stav.klic === stavKlic) return;
    onPresun(id, stavKlic);
  }

  return (
    <div className="crm-kanban">
      {sloupce.map((s) => (
        <div
          key={s.stav.klic}
          className={`crm-kanban-sloupec ${nad === s.stav.klic ? "nad" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setNad(s.stav.klic);
          }}
          onDragLeave={() => setNad((k) => (k === s.stav.klic ? null : k))}
          onDrop={(e) => pust(e, s.stav.klic)}
        >
          <div className={`crm-kanban-hlava ${tridaBarvy(s.stav.barva)}`}>
            <span className="crm-kanban-nazev">{s.stav.nazev}</span>
            <span className="crm-kanban-pocet">{s.pocet}</span>
          </div>
          {s.soucet_kc != null && (
            <div className="crm-kanban-soucet">{fmtKcKratce(s.soucet_kc)}</div>
          )}

          <div className="crm-kanban-telo">
            {s.zaznamy.map((z) => (
              <article
                key={z.id}
                className={`crm-dlazdice ${nesu === z.id ? "nesu" : ""}`}
                draggable
                onDragStart={(e) => zacniNest(e, z)}
                onDragEnd={() => setNesu(null)}
                onClick={() => onOtevri(z)}
                title="Klikni pro detail, přetáhni pro změnu stavu"
              >
                {dlazdice ? (
                  dlazdice(z)
                ) : (
                  <>
                    <div className="crm-dlazdice-hlava">
                      <span className="crm-dlazdice-cislo">{z.cislo}</span>
                      {z.hodnota_kc ? (
                        <span className="crm-dlazdice-hodnota">{fmtKcKratce(z.hodnota_kc)}</span>
                      ) : null}
                    </div>
                    <div className="crm-dlazdice-zakaznik">{z.zakaznik_nazev}</div>
                    {z.nazev && <div className="crm-dlazdice-nazev">{z.nazev}</div>}
                    <div className="crm-dlazdice-pata">
                      {nazvyKategorii(z.kategorie, kategorie) || "bez kategorie"}
                      {z.predpokladane_uzavreni ? (
                        <span
                          className={
                            jePoTerminu(z.predpokladane_uzavreni) ? "crm-dlazdice-pozde" : undefined
                          }
                        >
                          {" · "}
                          {fmtDatum(z.predpokladane_uzavreni)}
                        </span>
                      ) : (
                        ""
                      )}
                    </div>
                    {/* Iniciály + jak dlouho případ visí v téhle fázi (CRM-44).
                        Dny ve fázi jsou to, co v kanbanu chybělo nejvíc: jinak
                        se nepozná ležák od čerstvého případu. */}
                    <div className="crm-dlazdice-vlastnik">
                      {z.vlastnik_jmeno && <Iniciraly jmeno={z.vlastnik_jmeno} velikost={20} />}
                      <span>{z.vlastnik_jmeno || "bez vlastníka"}</span>
                      <span className="crm-mezera" />
                      {z.dni_ve_fazi > 0 && (
                        <span
                          className={`crm-dni-ve-fazi${z.dni_ve_fazi >= 30 ? " dlouho" : ""}`}
                          title={`V tomhle stavu ${z.dni_ve_fazi} dní`}
                        >
                          {z.dni_ve_fazi} d
                        </span>
                      )}
                    </div>
                  </>
                )}

                {/* Náhrada přetahování pro klávesnici a mobil. */}
                <select
                  className="crm-dlazdice-stav"
                  value={s.stav.klic}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => {
                    e.stopPropagation();
                    if (e.target.value !== s.stav.klic) onPresun(z.id, e.target.value);
                  }}
                  aria-label={`Změnit stav ${z.cislo}`}
                >
                  {sloupce.map((jiny) => (
                    <option key={jiny.stav.klic} value={jiny.stav.klic}>
                      {jiny.stav.nazev}
                    </option>
                  ))}
                </select>
              </article>
            ))}
            {s.zaznamy.length === 0 && <div className="crm-kanban-prazdno">Prázdné</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
