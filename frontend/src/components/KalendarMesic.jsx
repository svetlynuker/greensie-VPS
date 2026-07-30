import { useMemo } from "react";
import { isoDen, pondeliTydne } from "../datum";

/**
 * Čtvercový přehled měsíce vedle týdenní mřížky.
 *
 * Slouží k přeskakování: kliknutím na datum se hlavní kalendář přepne na ten
 * týden a den se v něm označí. Sám žádné události nevypisuje — na to je malý;
 * jen tečkou naznačí, že v ten den něco je, aby bylo vidět, kde je nabito.
 *
 * Týden začíná pondělím (ČR). Mřížka má vždy 6 řádků, i když měsíc vyjde na 5 —
 * jinak by dlaždice měnila výšku podle měsíce a obsah vedle ní by poskakoval.
 */

const DNY_ZKRATKY = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"];
const MESICE = [
  "leden",
  "únor",
  "březen",
  "duben",
  "květen",
  "červen",
  "červenec",
  "srpen",
  "září",
  "říjen",
  "listopad",
  "prosinec",
];

export default function KalendarMesic({
  mesic, // Date kdekoli v zobrazovaném měsíci
  vybranyDen, // ISO den, který je označený
  zobrazenyTyden, // Date – pondělí týdne, který je v hlavní mřížce
  dnySUdalostmi, // Set ISO dnů, kde něco je
  onDen,
  onMesic, // (Date) → přepnout zobrazovaný měsíc
}) {
  const dnesIso = isoDen(new Date());
  // Celý zobrazený týden je podbarvený (podle předlohy) – je tak vidět, kde
  // v měsíci se člověk nachází, ne jen na kterém dni stojí kurzor.
  const tydenOd = zobrazenyTyden ? isoDen(pondeliTydne(zobrazenyTyden)) : null;
  const tydenDo = zobrazenyTyden
    ? isoDen(new Date(pondeliTydne(zobrazenyTyden).getTime() + 6 * 86400000))
    : null;

  // 6 × 7 dnů počínaje pondělím týdne, do kterého padá první den měsíce.
  const dny = useMemo(() => {
    const prvni = new Date(mesic.getFullYear(), mesic.getMonth(), 1);
    const start = pondeliTydne(prvni);
    return Array.from({ length: 42 }, (_, i) => {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      return d;
    });
  }, [mesic]);

  function posun(o) {
    onMesic(new Date(mesic.getFullYear(), mesic.getMonth() + o, 1));
  }

  return (
    <div className="kal-mesic">
      <div className="kal-mesic-hlava">
        <button className="fm-btn kal-btn-ikona" onClick={() => posun(-1)} title="Předchozí měsíc">
          ‹
        </button>
        <span className="kal-mesic-nazev">
          {MESICE[mesic.getMonth()]} {mesic.getFullYear()}
        </span>
        <button className="fm-btn kal-btn-ikona" onClick={() => posun(1)} title="Další měsíc">
          ›
        </button>
      </div>

      <div className="kal-mesic-mrizka" role="grid">
        {DNY_ZKRATKY.map((d) => (
          <div key={d} className="kal-mesic-zahlavi" role="columnheader">
            {d}
          </div>
        ))}

        {dny.map((d) => {
          const iso = isoDen(d);
          const jinyMesic = d.getMonth() !== mesic.getMonth();
          const vTydnu = tydenOd && iso >= tydenOd && iso <= tydenDo;
          const trida = [
            "kal-mesic-den",
            jinyMesic ? "mimo" : "",
            vTydnu ? "vtydnu" : "",
            iso === vybranyDen ? "vybrany" : "",
            iso === dnesIso ? "dnes" : "",
          ]
            .filter(Boolean)
            .join(" ");
          return (
            <button
              key={iso}
              className={trida}
              onClick={() => onDen(iso)}
              title={iso === dnesIso ? "Dnes" : `Přejít na ${d.getDate()}. ${d.getMonth() + 1}.`}
            >
              {d.getDate()}
              {dnySUdalostmi?.has(iso) && <span className="kal-tecka" aria-hidden="true" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
