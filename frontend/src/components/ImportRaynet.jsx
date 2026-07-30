import { useState } from "react";
import { crmImportRaynet } from "../api";
import { fmtKc } from "../crm";

/**
 * Import klientů a obchodních případů z Raynetu.
 *
 * Používá přístup, který už má nastavený konektor — žádné další heslo. Import
 * je jednosměrný a idempotentní (páruje se na Raynetí id), takže opakované
 * spuštění záznamy aktualizuje, nezdvojí.
 *
 * Náhled se **nespouští sám**: čtení 450 firem a 200 případů stojí API cally
 * a Raynet má denní limit. Uživatel si ho vyžádá kliknutím.
 */
export default function ImportRaynet({ onZavri, onHotovo }) {
  const [nahled, setNahled] = useState(null);
  const [hotovo, setHotovo] = useState(null);
  const [pracuje, setPracuje] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function nacti() {
    setPracuje(true);
    setChyba(null);
    try {
      setNahled(await crmImportRaynet(true));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  async function proved() {
    if (
      !window.confirm(
        `Opravdu naimportovat ${nahled.firem_novych} klientů a ${nahled.pripadu_novych} obchodních případů z Raynetu? Nelze vzít zpět.`
      )
    )
      return;
    setPracuje(true);
    setChyba(null);
    try {
      const r = await crmImportRaynet(false);
      setHotovo(r);
      await onHotovo?.();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  const d = hotovo || nahled;

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Import z Raynetu</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Natáhne <b>klienty</b> a <b>obchodní případy</b> z Raynetu. Jednosměrně
            (Raynet → appka) a idempotentně — opakované spuštění existující záznamy
            aktualizuje, nezdvojí. Použije se přístup nastavený v Konektoru.
          </p>

          {!d && (
            <div className="crm-prazdno">
              {pracuje ? (
                "Čtu z Raynetu…"
              ) : (
                <>
                  Nejdřív si nech ukázat, co by se naimportovalo.
                  <div style={{ marginTop: 10 }}>
                    <button className="fm-btn fm-primary" onClick={nacti}>
                      Zobrazit náhled
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {d && (
            <>
              <dl className="crm-udaje">
                <dt>V Raynetu</dt>
                <dd>
                  {d.firem_v_raynetu} firem, {d.pripadu_v_raynetu} obchodních případů
                </dd>
                <dt>{hotovo ? "Vzniklo klientů" : "Vznikne klientů"}</dt>
                <dd>{d.firem_novych}</dd>
                <dt>{hotovo ? "Aktualizováno klientů" : "Aktualizuje se klientů"}</dt>
                <dd>{d.firem_aktualizovanych}</dd>
                <dt>{hotovo ? "Vzniklo případů" : "Vznikne případů"}</dt>
                <dd>{d.pripadu_novych}</dd>
                {d.pripadu_bez_zakaznika > 0 && (
                  <>
                    <dt>Případů bez firmy</dt>
                    <dd>
                      {d.pripadu_bez_zakaznika}{" "}
                      <span className="crm-tise">(v Raynetu nemají navázanou firmu)</span>
                    </dd>
                  </>
                )}
                <dt>Zbývalo API callů</dt>
                <dd>{d.zbyvalo_api_callu ?? "—"}</dd>
              </dl>

              {(d.ukazka_firem || []).length > 0 && (
                <>
                  <h3 style={{ marginTop: 14 }}>Ukázka firem</h3>
                  <table className="crm-tabulka crm-tabulka-hustá">
                    <thead>
                      <tr>
                        <th>Název</th>
                        <th>IČO</th>
                        <th>Město</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.ukazka_firem.map((f, i) => (
                        <tr key={i}>
                          <td className="crm-silne">{f.nazev}</td>
                          <td>{f.ico || "—"}</td>
                          <td>{f.mesto || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {(d.ukazka_pripadu || []).length > 0 && (
                <>
                  <h3 style={{ marginTop: 14 }}>Ukázka případů</h3>
                  <table className="crm-tabulka crm-tabulka-hustá">
                    <thead>
                      <tr>
                        <th>Raynetí číslo</th>
                        <th>Název</th>
                        <th>Zákazník</th>
                        <th>Fáze v Raynetu</th>
                        <th className="crm-vpravo">Hodnota</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.ukazka_pripadu.map((p, i) => (
                        <tr key={i}>
                          <td className="crm-silne">{p.kod || "—"}</td>
                          <td>{p.nazev}</td>
                          <td>{p.zakaznik}</td>
                          <td>{p.faze || "—"}</td>
                          <td className="crm-vpravo">{fmtKc(p.hodnota)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {(d.nenamapovani_vlastnici || []).length > 0 && (
                <div className="crm-varovani">
                  <b>Tyhle vlastníky z Raynetu neumíme napárovat</b> na uživatele appky, takže
                  jejich záznamy zůstanou <b>bez vlastníka</b> — uvidí je jen ten, kdo má právo
                  vidět všechny záznamy:
                  <div className="crm-volby" style={{ marginTop: 6 }}>
                    {d.nenamapovani_vlastnici.map((x) => (
                      <span key={x} className="crm-znacka">
                        {x}
                      </span>
                    ))}
                  </div>
                  Když těmto lidem založíš účet se stejným jménem (nebo aspoň příjmením)
                  a import spustíš znovu, vlastníci se doplní.
                </div>
              )}

              <div className="crm-varovani">
                <b>Co se nepřenáší:</b> kategorie případu (PPA / prodej / peak shaving) — Raynetí
                fáze ji neobsahuje a hádat ji z názvu by vyrobilo tichý nepořádek. Zůstane prázdná
                a appka se zeptá při vytváření nabídky. Raynetí fáze se zapíše do popisu případu,
                aby se informace neztratila; <b>Raynetí číslo</b> se uloží zvlášť, protože na něm
                stojí párování složek na Disku.
              </div>

              {hotovo && <div className="crm-zprava">Import hotový.</div>}
              {chyba && <div className="crm-chyba">{chyba}</div>}
            </>
          )}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            {hotovo ? "Zavřít" : "Zrušit"}
          </button>
          <span className="crm-mezera" />
          {nahled && !hotovo && (
            <button className="fm-btn fm-primary" onClick={proved} disabled={pracuje}>
              {pracuje ? "Importuji…" : "Provést import"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
