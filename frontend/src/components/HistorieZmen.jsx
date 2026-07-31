import { useEffect, useState } from "react";
import { crmAudit } from "../api";
import { fmtDatumCas } from "../crm";

/**
 * Historie změn záznamu (CRM-12).
 *
 * Odpovídá na „kdo změnil cenu z 2,5 na 1,9 milionu" — na rozdíl od timeline,
 * která ukazuje *co se dělo* (aktivity, posuny stavů). Proto je to samostatný
 * sbalený panel a ne další proud v timeline: změna jedné čárky v popisu je
 * záznam, který nemá zaplevelit přehled o zakázce.
 *
 * Načítá se **až po rozbalení**. U karty, kterou člověk otevře kvůli něčemu
 * jinému, by to byl dotaz navíc při každém zobrazení.
 */
function popisRadku(z) {
  if (z.druh === "vznik") return "Záznam vznikl";
  if (z.druh === "smazani") return "Záznam smazán";
  return z.pole_nazev || z.pole;
}

export default function HistorieZmen({ entita, zaznamId }) {
  const [otevreno, setOtevreno] = useState(false);
  const [zaznamy, setZaznamy] = useState(null);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    if (!otevreno || zaznamy !== null) return;
    crmAudit(entita, zaznamId)
      .then(setZaznamy)
      .catch((e) => setChyba(e.message));
  }, [otevreno, zaznamy, entita, zaznamId]);

  return (
    <details
      className="fm-card crm-blok crm-historie"
      open={otevreno}
      onToggle={(e) => setOtevreno(e.currentTarget.open)}
    >
      <summary>
        Historie změn
        <span className="crm-tise"> — kdo co kdy upravil</span>
      </summary>

      <div className="crm-historie-telo">
        {chyba && <div className="crm-chyba">{chyba}</div>}
        {!chyba && zaznamy === null && <p className="crm-tise">Načítám…</p>}
        {zaznamy?.length === 0 && (
          <p className="crm-tise">
            Zatím žádná změna. Historie se sbírá od chvíle, kdy se funkce zapnula —
            starší úpravy v ní nejsou.
          </p>
        )}
        {zaznamy?.length > 0 && (
          <ul className="crm-historie-seznam">
            {zaznamy.map((z) => (
              <li key={z.id}>
                <span className="crm-historie-kdy">{fmtDatumCas(z.kdy)}</span>
                <span className="crm-historie-pole">{popisRadku(z)}</span>
                {z.druh === "zmena" && (
                  <span className="crm-historie-hodnoty">
                    <span className="crm-historie-stara">{z.stara || "—"}</span>
                    {" → "}
                    <b>{z.nova || "—"}</b>
                  </span>
                )}
                <span className="crm-historie-kdo">{z.kdo || "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}
