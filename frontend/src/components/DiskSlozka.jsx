import { useEffect, useState } from "react";
import { crmSlozka, crmSlozkuZaloz } from "../api";

/**
 * Dokumenty záznamu na Google Disku (CRM-05).
 *
 * Appka soubory nehostuje — leží na Disku, kde s nimi lidé už pracují. Tady je
 * jen odkaz a výpis, aby se k nim šlo dostat z karty zákazníka nebo případu
 * a nemuselo se hledat ve struktuře Disku.
 *
 * Složka se zakládá TLAČÍTKEM, ne sama (rozhodnutí Dana): u případu, který za
 * dva dny skončí jako „nezajímavé", by automat nechal na Disku prázdnou složku.
 *
 * Zakládání kopíruje celý vzor — pár sekund a desítky volání na Disk. Proto je
 * tlačítko po dobu běhu zablokované a chyba se ukazuje konkrétně; tichý
 * polovytvořený strom složek by byl horší než chybová zpráva.
 */
export default function DiskSlozka({ entita, zaznamId, popisZaznamu }) {
  const [stav, setStav] = useState(null);
  const [zaklada, setZaklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    let zruseno = false;
    crmSlozka(entita, zaznamId)
      .then((d) => !zruseno && setStav(d))
      .catch((e) => !zruseno && setChyba(e.message));
    return () => {
      zruseno = true;
    };
  }, [entita, zaznamId]);

  async function zaloz() {
    setZaklada(true);
    setChyba(null);
    try {
      await crmSlozkuZaloz(entita, zaznamId);
      setStav(await crmSlozka(entita, zaznamId));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZaklada(false);
    }
  }

  return (
    <div className="ds">
      <div className="ds-hlava">
        <span className="gs-karta-titulek">Dokumenty na Disku</span>
        <span className="crm-mezera" />
        {stav?.existuje && (
          <a className="fm-btn crm-btn-maly" href={stav.url} target="_blank" rel="noreferrer">
            Otevřít složku ↗
          </a>
        )}
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {stav === null && !chyba && <p className="crm-tise">Zjišťuji…</p>}

      {stav && !stav.existuje && (
        <>
          <p className="crm-tise">
            Tenhle záznam ještě nemá složku na Disku. Založí se podle firemního vzoru —
            se stejnou strukturou, jakou mají zakázky z Raynetu.
          </p>
          <button className="fm-btn fm-primary" onClick={zaloz} disabled={zaklada}>
            {zaklada ? "Zakládám na Disku…" : "Založit složku na Disku"}
          </button>
          {zaklada && (
            <p className="crm-tise" style={{ marginTop: 6 }}>
              Kopíruje se celý vzor, chvíli to trvá. Nezavírej stránku.
            </p>
          )}
        </>
      )}

      {stav?.existuje && (
        <>
          <p className="crm-tise ds-cesta">{stav.nazev}</p>
          {stav.chyba ? (
            <p className="crm-tise">
              Obsah složky se nepodařilo načíst ({stav.chyba}). Odkaz výš funguje.
            </p>
          ) : stav.soubory.length === 0 ? (
            <p className="crm-tise">Složka je zatím prázdná.</p>
          ) : (
            <ul className="ds-seznam">
              {stav.soubory.map((f) => (
                <li key={f.id}>
                  <a href={f.url} target="_blank" rel="noreferrer" title={f.nazev}>
                    <span className="ds-ikona" aria-hidden="true">
                      {f.je_slozka ? "📁" : "📄"}
                    </span>
                    {f.nazev}
                  </a>
                </li>
              ))}
            </ul>
          )}
          <p className="crm-tise">
            Soubory {popisZaznamu ? `k ${popisZaznamu} ` : ""}patří na Disk, ne do appky —
            nahrává se tam, appka na ně jen odkazuje.
          </p>
        </>
      )}
    </div>
  );
}
