import { useState } from "react";
import { fmtKcKratce, fmtDatum, nazvyKategorii, tridaBarvy } from "../crm";

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
 */
export default function Kanban({ sloupce, onPresun, onOtevri }) {
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
          {s.soucet_kc ? (
            <div className="crm-kanban-soucet">{fmtKcKratce(s.soucet_kc)}</div>
          ) : (
            <div className="crm-kanban-soucet crm-tise">—</div>
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
                <div className="crm-dlazdice-hlava">
                  <span className="crm-dlazdice-cislo">{z.cislo}</span>
                  {z.hodnota_kc ? (
                    <span className="crm-dlazdice-hodnota">{fmtKcKratce(z.hodnota_kc)}</span>
                  ) : null}
                </div>
                <div className="crm-dlazdice-zakaznik">{z.zakaznik_nazev}</div>
                {z.nazev && <div className="crm-dlazdice-nazev">{z.nazev}</div>}
                <div className="crm-dlazdice-pata">
                  {nazvyKategorii(z.kategorie) || "bez kategorie"}
                  {z.predpokladane_uzavreni ? ` · ${fmtDatum(z.predpokladane_uzavreni)}` : ""}
                </div>
                {z.vlastnik_jmeno && (
                  <div className="crm-dlazdice-vlastnik">{z.vlastnik_jmeno}</div>
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
