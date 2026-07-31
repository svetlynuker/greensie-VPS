import { useCallback, useEffect, useRef, useState } from "react";
import { crmSlozka, crmSlozkaNahraj, crmSlozkaObsah, crmSlozkuZaloz } from "../api";

/**
 * Dokumenty záznamu na Google Disku (CRM-05) — průzkumník s nahráváním.
 *
 * Soubory appka nehostuje: leží na Disku, kde s nimi lidé pracují dál a kde je
 * firemní struktura složek. Tady se dají **procházet a přidávat**, aby člověk
 * kvůli smlouvě nemusel odcházet na Disk a hledat cestu.
 *
 * Dvě věci, které z toho plynou a nejsou zřejmé:
 *
 * 1. Nahraný soubor **u nás nezůstane**. Projde do Disku a v appce je jen odkaz.
 *    Dvě kopie téhož dokumentu by znamenaly, že nikdo neví, která platí.
 * 2. Do podsložky se leze přes její ID, které jde z prohlížeče — backend proto
 *    u každého požadavku ověřuje, že složka patří pod tenhle záznam. Jinak by se
 *    přes appku dal přečíst celý firemní Disk.
 *
 * Složka se zakládá tlačítkem, ne automaticky (rozhodnutí Dana).
 */

function velikost(b) {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${Math.round(b / 1024)} kB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export default function DiskSlozka({ entita, zaznamId, popisZaznamu }) {
  const [zaklad, setZaklad] = useState(null); // {existuje, url, nazev}
  const [obsah, setObsah] = useState(null); // {folder_id, cesta, polozky, je_koren}
  const [kde, setKde] = useState(null);
  const [zaklada, setZaklada] = useState(false);
  const [nahrava, setNahrava] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [nadSebou, setNadSebou] = useState(false); // přetahování souboru nad kartou
  const vstup = useRef(null);

  const nactiObsah = useCallback(
    async (folderId = null) => {
      try {
        const d = await crmSlozkaObsah(entita, zaznamId, folderId);
        setObsah(d);
        setKde(d.folder_id);
        setChyba(null);
      } catch (e) {
        setChyba(e.message);
      }
    },
    [entita, zaznamId]
  );

  useEffect(() => {
    let zruseno = false;
    crmSlozka(entita, zaznamId)
      .then((d) => {
        if (zruseno) return;
        setZaklad(d);
        if (d.existuje) nactiObsah(null);
      })
      .catch((e) => !zruseno && setChyba(e.message));
    return () => {
      zruseno = true;
    };
  }, [entita, zaznamId, nactiObsah]);

  async function zaloz() {
    setZaklada(true);
    setChyba(null);
    try {
      await crmSlozkuZaloz(entita, zaznamId);
      setZaklad(await crmSlozka(entita, zaznamId));
      await nactiObsah(null);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZaklada(false);
    }
  }

  /** Nahraje soubory do právě otevřené složky (jeden po druhém). */
  async function nahraj(soubory) {
    const seznam = [...(soubory || [])];
    if (!seznam.length || !zaklad?.existuje) return;
    setNahrava(true);
    setChyba(null);
    const cil = obsah?.je_koren ? null : kde;
    try {
      for (const f of seznam) {
        await crmSlozkaNahraj(entita, zaznamId, f, cil);
      }
      await nactiObsah(cil);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setNahrava(false);
      if (vstup.current) vstup.current.value = "";
    }
  }

  return (
    <div
      className={`ds ${nadSebou ? "nad-sebou" : ""}`}
      onDragOver={(e) => {
        if (!zaklad?.existuje) return;
        e.preventDefault();
        setNadSebou(true);
      }}
      onDragLeave={() => setNadSebou(false)}
      onDrop={(e) => {
        if (!zaklad?.existuje) return;
        e.preventDefault();
        setNadSebou(false);
        nahraj(e.dataTransfer.files);
      }}
    >
      <div className="ds-hlava">
        <span className="gs-karta-titulek">Dokumenty na Disku</span>
        <span className="crm-mezera" />
        {zaklad?.existuje && (
          <>
            <button
              className="fm-btn crm-btn-maly fm-primary"
              onClick={() => vstup.current?.click()}
              disabled={nahrava}
            >
              {nahrava ? "Nahrávám…" : "+ Nahrát"}
            </button>
            <a
              className="fm-btn crm-btn-maly"
              href={zaklad.url}
              target="_blank"
              rel="noreferrer"
              title="Otevřít na Google Disku"
            >
              Disk ↗
            </a>
          </>
        )}
      </div>

      <input
        ref={vstup}
        type="file"
        multiple
        style={{ display: "none" }}
        onChange={(e) => nahraj(e.target.files)}
      />

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {zaklad === null && !chyba && <p className="crm-tise">Zjišťuji…</p>}

      {zaklad && !zaklad.existuje && (
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

      {zaklad?.existuje && obsah && (
        <>
          {/* Drobečková navigace — bez ní se člověk v podsložkách ztratí. */}
          <div className="ds-cesta">
            <button
              className={`ds-krok ${obsah.je_koren ? "aktivni" : ""}`}
              onClick={() => nactiObsah(null)}
            >
              {zaklad.nazev || "Složka záznamu"}
            </button>
            {obsah.cesta.map((k, i) => (
              <span key={k.id}>
                <span className="ds-sipka">›</span>
                <button
                  className={`ds-krok ${i === obsah.cesta.length - 1 ? "aktivni" : ""}`}
                  onClick={() => nactiObsah(k.id)}
                >
                  {k.nazev}
                </button>
              </span>
            ))}
          </div>

          {obsah.polozky.length === 0 ? (
            <p className="crm-tise">
              Složka je prázdná. Přetáhni sem soubor, nebo použij <b>+ Nahrát</b>.
            </p>
          ) : (
            <ul className="ds-seznam">
              {obsah.polozky.map((f) =>
                f.je_slozka ? (
                  <li key={f.id}>
                    <button className="ds-radek" onClick={() => nactiObsah(f.id)} title={f.nazev}>
                      <span className="ds-ikona" aria-hidden="true">
                        📁
                      </span>
                      <span className="ds-nazev">{f.nazev}</span>
                      <span className="ds-sipka">›</span>
                    </button>
                  </li>
                ) : (
                  <li key={f.id}>
                    <a
                      className="ds-radek"
                      href={f.url}
                      target="_blank"
                      rel="noreferrer"
                      title={f.nazev}
                    >
                      <span className="ds-ikona" aria-hidden="true">
                        📄
                      </span>
                      <span className="ds-nazev">{f.nazev}</span>
                      <span className="crm-tise">{velikost(f.velikost)}</span>
                    </a>
                  </li>
                )
              )}
            </ul>
          )}

          {obsah.zkraceno && (
            <p className="crm-tise">Zobrazeno prvních 60 položek — zbytek je vidět na Disku.</p>
          )}
          <p className="crm-tise">
            Soubory {popisZaznamu ? `k ${popisZaznamu} ` : ""}leží na Disku, ne v appce.
            Nahraný soubor jde přímo tam — tady zůstane odkaz.
          </p>
        </>
      )}
    </div>
  );
}
