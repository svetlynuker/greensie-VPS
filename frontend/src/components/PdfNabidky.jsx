// Odkaz na vygenerované PDF nabídky. Jedno tlačítko pro seznam, kanban,
// detail nabídky i nabídky na kartě případu — kdyby si to každá obrazovka
// řešila sama, na jedné z nich by odkaz po změně endpointu tiše přestal vést.

import { useState } from "react";

import { nabidkaPdfOtevri, nabidkaSouborStahni } from "../api";

/**
 * `pdf` je to, co vrací API u nabídky:
 * `{ id, nazev, format, vygenerovano_at, disk_url }` nebo nic, když nabídka
 * soubor ještě nemá.
 *
 * `format` rozlišuje nabídku pro zákazníka (`pdf`) od interního výpočtového
 * modelu (`xlsx`). Popisek i ikona se liší schválně – v Excelu jsou marže
 * a zisk, takže se nesmí splést s tím, co se posílá klientovi.
 *
 * Otevírá se přes fetch a blob URL, protože endpoint chce token v hlavičce
 * a ten `<a href>` poslat neumí.
 */
export default function PdfNabidky({ pdf, kompaktni = false, muzeExportovat = false }) {
  const [chyba, setChyba] = useState(null);

  if (!pdf?.id) {
    return kompaktni ? null : <span className="crm-tise">bez PDF</span>;
  }

  // Bez práva `export` se soubor nevydá (backend vrátí 403), takže se
  // neukazuje ani tlačítko. Schválně se ale říká, že soubor existuje —
  // „bez PDF" by byla lež a člověk by ho zkoušel vyrobit znovu.
  if (!muzeExportovat) {
    return kompaktni ? null : (
      <span className="crm-tise" title="Soubor existuje, ale na export dat nemáš oprávnění.">
        {pdf.format === "xlsx" ? "📊" : "📄"} bez práva na export
      </span>
    );
  }

  const jeExcel = pdf.format === "xlsx";
  const popisek = jeExcel ? "📊 Excel" : "📄 PDF";
  const popis = jeExcel
    ? "Stáhnout interní výpočtový model (jen pro nás – jsou v něm marže a zisk)"
    : "Otevřít nabídku pro zákazníka v PDF";

  async function otevri(e) {
    // V tabulce i na dlaždici je tlačítko uvnitř řádku, který sám na klik
    // někam naviguje – bez tohohle by se otevřelo obojí.
    e.stopPropagation();
    setChyba(null);
    try {
      if (jeExcel) await nabidkaSouborStahni(pdf.id, pdf.nazev);
      else await nabidkaPdfOtevri(pdf.id);
    } catch (err) {
      setChyba(err.message);
    }
  }

  return (
    <span className="crm-pdf-odkaz">
      <button
        className="fm-btn crm-btn-maly"
        onClick={otevri}
        title={pdf.nazev ? `${popis} (${pdf.nazev})` : popis}
      >
        {popisek}
      </button>
      {/* Odkaz na Disk chybí, dokud se soubor nenahrál (běží fronta konektoru) —
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
