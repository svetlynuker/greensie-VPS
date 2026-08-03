// Odkaz na vygenerované PDF nabídky. Jedno tlačítko pro seznam, kanban,
// detail nabídky i nabídky na kartě případu — kdyby si to každá obrazovka
// řešila sama, na jedné z nich by odkaz po změně endpointu tiše přestal vést.

import { useState } from "react";

import { nabidkaPdfOtevri } from "../api";

/**
 * `pdf` je to, co vrací API u nabídky: `{ id, nazev, vygenerovano_at, disk_url }`
 * nebo nic, když nabídka PDF ještě nemá.
 *
 * Otevírá se přes fetch a blob URL, protože endpoint chce token v hlavičce
 * a ten `<a href>` poslat neumí.
 */
export default function PdfNabidky({ pdf, kompaktni = false }) {
  const [chyba, setChyba] = useState(null);

  if (!pdf?.id) {
    return kompaktni ? null : <span className="crm-tise">bez PDF</span>;
  }

  async function otevri(e) {
    // V tabulce i na dlaždici je tlačítko uvnitř řádku, který sám na klik
    // někam naviguje – bez tohohle by se otevřelo obojí.
    e.stopPropagation();
    setChyba(null);
    try {
      await nabidkaPdfOtevri(pdf.id);
    } catch (err) {
      setChyba(err.message);
    }
  }

  return (
    <span className="crm-pdf-odkaz">
      <button
        className="fm-btn crm-btn-maly"
        onClick={otevri}
        title={pdf.nazev ? `Otevřít ${pdf.nazev}` : "Otevřít PDF nabídky"}
      >
        📄 PDF
      </button>
      {/* Odkaz na Disk chybí, dokud se PDF nenahrálo (běží fronta konektoru) —
          mrtvý odkaz by byl horší než žádný. */}
      {pdf.disk_url && (
        <a
          className="fm-btn crm-btn-maly"
          href={pdf.disk_url}
          target="_blank"
          rel="noreferrer"
          onClick={(e) => e.stopPropagation()}
          title="Otevřít soubor ve složce nabídky na Disku"
        >
          Disk
        </a>
      )}
      {chyba && <span className="crm-chyba">{chyba}</span>}
    </span>
  );
}
