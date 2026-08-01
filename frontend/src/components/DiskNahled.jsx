import { useEffect, useState } from "react";
import { diskNahledSouboru } from "../api";

/**
 * Soubor z Disku otevřený **v appce**, ne přesměrováním na Disk (přání Dana).
 *
 * ---- Proč se obsah tahá přes appku a ne přes iframe na Disk --------------
 * Vložit `drive.google.com/file/<id>/preview` by bylo o dva řádky kratší, ale
 * fungovalo by to jen tomu, kdo je zrovna přihlášený Googlem a k souboru má
 * přístup. Appka čte Disk service accountem konektoru, takže tady se soubor
 * ukáže každému, kdo má právo `disk` — a nikdo nemusí řešit, jakým účtem je
 * v prohlížeči přihlášený.
 *
 * ---- Blob a proč ---------------------------------------------------------
 * Přihlášení do appky se posílá hlavičkou, kterou `<iframe src>` ani `<img src>`
 * neumí přidat. Obsah se proto stáhne fetchem a vloží jako `blob:` URL. Ta se
 * při zavření okna uvolňuje — jinak by se s každým otevřeným souborem v paměti
 * prohlížeče držela další kopie.
 *
 * Co se v appce zobrazit nedá (zip, dwg, video), sem vůbec nechodí — o tom
 * rozhoduje backend příznakem `lze_nahled` u položky.
 */
export default function DiskNahled({ polozka, onZavri }) {
  const [url, setUrl] = useState(null);
  const [typ, setTyp] = useState("");
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    let zruseno = false;
    let vytvorena = null;
    setUrl(null);
    setChyba(null);
    diskNahledSouboru(polozka.id)
      .then((blob) => {
        if (zruseno) return;
        vytvorena = URL.createObjectURL(blob);
        setUrl(vytvorena);
        setTyp(blob.type || "");
      })
      .catch((e) => !zruseno && setChyba(e.message));
    return () => {
      zruseno = true;
      if (vytvorena) URL.revokeObjectURL(vytvorena);
    };
  }, [polozka.id]);

  // Zavírání Escapem: okno zabírá celou obrazovku, takže sáhnout po klávese je
  // rychlejší než hledat křížek.
  useEffect(() => {
    const naKlavesu = (e) => e.key === "Escape" && onZavri();
    window.addEventListener("keydown", naKlavesu);
    return () => window.removeEventListener("keydown", naKlavesu);
  }, [onZavri]);

  const jeObrazek = typ.startsWith("image/");
  const jeText = typ.startsWith("text/") && !typ.includes("html");

  return (
    <div className="crm-okno-plast dk-nahled-plast" onClick={onZavri}>
      <div className="crm-okno dk-nahled-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2 className="dk-nahled-nazev" title={polozka.nazev}>
            {polozka.nazev}
          </h2>
          <span className="crm-mezera" />
          {url && (
            <a className="fm-btn crm-btn-maly" href={url} download={polozka.nazev}>
              Uložit
            </a>
          )}
          {/* Odkaz na Disk zůstává: tam se soubor dá i upravit, což appka neumí. */}
          <a
            className="fm-btn crm-btn-maly"
            href={polozka.url}
            target="_blank"
            rel="noreferrer"
            title="Otevřít na Google Disku (tam se dá i upravit)"
          >
            Disk ↗
          </a>
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="dk-nahled-telo">
          {chyba && <div className="crm-chyba">{chyba}</div>}
          {!url && !chyba && <p className="dk-prazdno">Otevírám soubor z Disku…</p>}
          {url && !chyba && (
            <>
              {jeObrazek && <img className="dk-nahled-obrazek" src={url} alt={polozka.nazev} />}
              {/* PDF (a Google dokumenty, které přijdou jako PDF) i čistý text
                  umí prohlížeč zobrazit sám — iframe je tady prohlížeč souboru,
                  ne cizí stránka. */}
              {!jeObrazek && (
                <iframe className="dk-nahled-ram" src={url} title={polozka.nazev} />
              )}
              {jeText && (
                <p className="crm-tise dk-nahled-pozn">
                  Textový soubor se zobrazuje tak, jak je — formátování Disk neposílá.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
