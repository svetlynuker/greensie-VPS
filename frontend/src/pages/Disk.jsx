import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import { diskKoren, diskNahraj, diskObsah, logout, nactiMe } from "../api";
import "../styles/crm.css";
import "../styles/disk.css";

/**
 * Modul Disk — firemní Google Disk k procházení a nahrávání přes celou plochu.
 *
 * Je to ta samá věc jako karta „Dokumenty na Disku" na klientovi
 * (`components/DiskSlozka.jsx`), jen o dvě úrovně výš a bez omezení na jeden
 * záznam: začíná se **složkou nad kořenem konektoru** (u nás `8. Raynet`, kde
 * vedle klientů leží i formuláře a návody) a dá se dojít až k poslednímu souboru.
 *
 * Dvě věci, které z toho plynou:
 *
 * 1. **Na každé úrovni je odkaz na Disk** (výslovné Danovo zadání). V drobečkové
 *    navigaci má každý krok svoje ↗, každá složka i soubor v seznamu taky —
 *    takže odkud člověk chce odejít na Disk, odtud odejde, ne jen z kořene.
 * 2. **Nahrává se do právě otevřené složky** — tlačítkem nebo přetažením souboru
 *    na plochu. Soubor u nás nezůstane: projde do Disku a v appce je jen odkaz.
 *    Dvě kopie téhož dokumentu by znamenaly, že nikdo neví, která platí.
 *
 * Strop viditelnosti drží backend: složka nad kořenem konektoru a nic nad ní
 * (`konektor/disk_prochazeni.py`), a to u čtení i u nahrání. Filtrování v liště
 * je jen nad **právě načtenou složkou** — není to hledání přes celý Disk,
 * protože to Drive API neumí bez sahání i tam, kam se z appky vidět nemá.
 */

function velikost(b) {
  if (!b) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${Math.round(b / 1024)} kB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

export default function Disk() {
  const [me, setMe] = useState(null);
  const [koren, setKoren] = useState(null); // {id, nazev, url}
  const [obsah, setObsah] = useState(null); // {folder_id, nazev, url, cesta, polozky, …}
  const [nacita, setNacita] = useState(true);
  const [chyba, setChyba] = useState(null);
  const [filtr, setFiltr] = useState("");
  const [nahrava, setNahrava] = useState(false);
  const [hlaska, setHlaska] = useState("");
  const [nadSebou, setNadSebou] = useState(false); // přetahování souboru nad plochou
  const vstup = useRef(null);
  const zivy = useRef(true);
  const navigate = useNavigate();

  useEffect(() => {
    zivy.current = true;
    return () => {
      zivy.current = false;
    };
  }, []);

  // Vypršelé přihlášení → na login; zbytek se ukáže jako hláška (stejný vzor
  // jako ostatní stránky).
  const osetriChybu = useCallback(
    (e) => {
      const m = String(e.message || e);
      if (m.includes("přihlášení") || m.includes("uživatel")) {
        logout();
        navigate("/");
        return;
      }
      if (zivy.current) setChyba(m);
    },
    [navigate]
  );

  /** Načte složku (prázdné id = kořen konektoru). */
  const otevri = useCallback(
    async (folderId = null) => {
      setNacita(true);
      setChyba(null);
      try {
        const d = await diskObsah(folderId);
        if (!zivy.current) return;
        setObsah(d);
        // Filtr platí pro jednu složku — po přechodu jinam by jen schovával
        // obsah, který člověk chtěl vidět.
        setFiltr("");
        setHlaska("");
      } catch (e) {
        osetriChybu(e);
      } finally {
        if (zivy.current) setNacita(false);
      }
    },
    [osetriChybu]
  );

  /** Znovu načte právě otevřenou složku (po nahrání, nebo na „Obnovit"). */
  const obnov = useCallback(() => {
    otevri(obsah?.je_koren ? null : obsah?.folder_id);
  }, [otevri, obsah]);

  /** Nahraje soubory do právě otevřené složky, jeden po druhém. */
  async function nahraj(soubory) {
    const seznam = [...(soubory || [])];
    if (!seznam.length || !obsah) return;
    setNahrava(true);
    setChyba(null);
    setHlaska("");
    // Do výchozí složky se posílá prázdné id — backend si ji dosadí sám, ať
    // se ID stropu nemusí posílat z prohlížeče.
    const cil = obsah.je_koren ? null : obsah.folder_id;
    try {
      for (const f of seznam) {
        await diskNahraj(f, cil);
      }
      if (!zivy.current) return;
      setHlaska(
        seznam.length === 1 ? `Nahráno: ${seznam[0].name}` : `Nahráno ${seznam.length} souborů.`
      );
      otevri(cil);
    } catch (e) {
      osetriChybu(e);
    } finally {
      if (zivy.current) setNahrava(false);
      if (vstup.current) vstup.current.value = "";
    }
  }

  useEffect(() => {
    nactiMe().then(setMe).catch(osetriChybu);
  }, [osetriChybu]);

  useEffect(() => {
    diskKoren()
      .then((k) => {
        if (!zivy.current) return;
        setKoren(k);
        otevri(null);
      })
      .catch((e) => {
        osetriChybu(e);
        if (zivy.current) setNacita(false);
      });
  }, [otevri, osetriChybu]);

  // O úroveň výš: předposlední krok cesty, nebo kořen.
  const nadrazena = () => {
    const c = obsah?.cesta || [];
    otevri(c.length >= 2 ? c[c.length - 2].id : null);
  };

  const hledej = filtr.trim().toLowerCase();
  const vypis = (obsah?.polozky || []).filter(
    (p) => !hledej || p.nazev.toLowerCase().includes(hledej)
  );
  const pocetSlozek = vypis.filter((p) => p.je_slozka).length;
  const pocetSouboru = vypis.length - pocetSlozek;

  // 404 z backendu = modul pro uživatele není zapnutý (novinky / právo `disk`).
  // Hláška „Nenalezeno" by ho poslala hledat chybu, která tam není.
  const nedostupny = chyba && chyba.includes("Nenalezeno");

  return (
    <Layout uzivatel={me}>
      {nedostupny ? (
        <div className="fm-card dk-hlaska">
          <p>Modul Disk pro tebe zatím není zapnutý.</p>
          <p className="crm-tise">
            Otevře se každému, kdo má právo <b>Disk</b> — přidělí se v Admin nastavení.
          </p>
        </div>
      ) : (
        <div
          className={`dk ${nadSebou ? "nad-sebou" : ""}`}
          // Přetažení souboru na plochu = nahrání do otevřené složky. Rychlejší
          // než dialog a lidé to od průzkumníka čekají.
          onDragOver={(e) => {
            if (!obsah) return;
            e.preventDefault();
            setNadSebou(true);
          }}
          onDragLeave={() => setNadSebou(false)}
          onDrop={(e) => {
            if (!obsah) return;
            e.preventDefault();
            setNadSebou(false);
            nahraj(e.dataTransfer.files);
          }}
        >
          <div className="dk-lista">
            <button
              className="fm-btn crm-btn-maly"
              onClick={nadrazena}
              disabled={!obsah || obsah.je_koren}
              title="O úroveň výš"
            >
              ← Zpět
            </button>

            {/* Drobečková navigace. Každý krok má vedle sebe ↗ na Disk, takže
                se dá odejít z té úrovně, na které člověk právě je. */}
            <div className="dk-cesta">
              <button
                className={`dk-krok ${obsah?.je_koren ? "aktivni" : ""}`}
                onClick={() => otevri(null)}
                title={koren?.nazev || "Kořenová složka konektoru"}
              >
                <Ikona jmeno="slozka" velikost={14} />
                {koren?.nazev || "Disk"}
              </button>
              {koren?.url && (
                <a
                  className="dk-krok-odkaz"
                  href={koren.url}
                  target="_blank"
                  rel="noreferrer"
                  title={`Otevřít „${koren.nazev}“ na Google Disku`}
                >
                  ↗
                </a>
              )}
              {(obsah?.cesta || []).map((k, i) => (
                <span className="dk-krok-obal" key={k.id}>
                  <span className="dk-sipka">›</span>
                  <button
                    className={`dk-krok ${i === obsah.cesta.length - 1 ? "aktivni" : ""}`}
                    onClick={() => otevri(k.id)}
                    title={k.nazev}
                  >
                    {k.nazev}
                  </button>
                  {k.url && (
                    <a
                      className="dk-krok-odkaz"
                      href={k.url}
                      target="_blank"
                      rel="noreferrer"
                      title={`Otevřít „${k.nazev}“ na Google Disku`}
                    >
                      ↗
                    </a>
                  )}
                </span>
              ))}
            </div>

            <span className="crm-mezera" />

            <input
              className="dk-filtr"
              type="search"
              value={filtr}
              onChange={(e) => setFiltr(e.target.value)}
              placeholder="Filtrovat v této složce…"
            />
            <button
              className="fm-btn crm-btn-maly"
              onClick={obnov}
              disabled={nacita}
              title="Načíst obsah znovu z Disku"
            >
              {nacita ? "Načítám…" : "Obnovit"}
            </button>
            <button
              className="fm-btn crm-btn-maly fm-primary"
              onClick={() => vstup.current?.click()}
              disabled={!obsah || nahrava}
              title="Nahrát soubor do právě otevřené složky"
            >
              {nahrava ? "Nahrávám…" : "+ Nahrát"}
            </button>
            {obsah?.url && (
              <a
                className="fm-btn crm-btn-maly"
                href={obsah.url}
                target="_blank"
                rel="noreferrer"
                title="Otevřít tuhle složku na Google Disku"
              >
                Otevřít na Disku ↗
              </a>
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
          {hlaska && !chyba && <div className="dk-hlaska-radek">{hlaska}</div>}

          <div className="fm-card dk-obsah">
            {!obsah && nacita && <p className="dk-prazdno">Načítám Disk…</p>}

            {obsah && vypis.length === 0 && (
              <p className="dk-prazdno">
                {hledej ? (
                  "Nic tomu tady neodpovídá."
                ) : (
                  <>
                    Tahle složka je prázdná. Přetáhni sem soubor, nebo použij <b>+ Nahrát</b>.
                  </>
                )}
              </p>
            )}

            {vypis.length > 0 && (
              <ul className="dk-seznam">
                {vypis.map((p) => (
                  <li className="dk-radek" key={p.id}>
                    {p.je_slozka ? (
                      <button className="dk-cil" onClick={() => otevri(p.id)} title={p.nazev}>
                        <span className="dk-ikona dk-ikona-slozka" aria-hidden="true">
                          <Ikona jmeno="slozka" velikost={17} />
                        </span>
                        <span className="dk-nazev">{p.nazev}</span>
                        <span className="dk-sipka">›</span>
                      </button>
                    ) : (
                      <a
                        className="dk-cil"
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        title={p.nazev}
                      >
                        <span className="dk-ikona" aria-hidden="true">
                          📄
                        </span>
                        <span className="dk-nazev">{p.nazev}</span>
                        <span className="crm-tise">{velikost(p.velikost)}</span>
                      </a>
                    )}
                    {/* U složky vede řádek dovnitř, takže odkaz na Disk musí být
                        zvlášť. U souboru je to totéž místo — ať je sloupec ↗
                        na všech řádcích na stejném místě. */}
                    <a
                      className="dk-odkaz"
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      title={`Otevřít „${p.nazev}“ na Google Disku`}
                    >
                      ↗
                    </a>
                  </li>
                ))}
              </ul>
            )}

            {obsah && (
              <div className="dk-pata">
                <span className="crm-tise">
                  {pocetSlozek} {pocetSlozek === 1 ? "složka" : pocetSlozek < 5 ? "složky" : "složek"}
                  {" · "}
                  {pocetSouboru}{" "}
                  {pocetSouboru === 1 ? "soubor" : pocetSouboru < 5 ? "soubory" : "souborů"}
                  {hledej ? ` (z ${obsah.polozky.length} položek)` : ""}
                </span>
                {obsah.zkraceno && (
                  <span className="crm-tise">
                    Složka má víc položek, než se sem posílá — zbytek je vidět na Disku.
                  </span>
                )}
                <span className="crm-mezera" />
                <span className="crm-tise">
                  Soubory leží na Disku, ne v appce. Nahraný soubor jde přímo tam — tady
                  zůstane odkaz.
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </Layout>
  );
}
