import { useEffect, useState } from "react";
import { crmMigraceStareNabidky } from "../api";

const TYPY = { ppa: "PPA", prodej: "Prodej", peak_shaving: "Peak shaving", kombinace: "Kombinace" };

/**
 * Dohledání starých nabídek: zavěšení na zákazníka a obchodní případ.
 *
 * Nabídky z doby před CRM nemají číslo ani případ, takže v přehledech visí
 * jako `#21` bez zákazníka. Tohle jim podle jména zákazníka založí klienta
 * a případ a doplní číslo.
 *
 * Nejdřív se vždy ukáže **náhled** (server nic nemění) a teprve druhé kliknutí
 * migraci provede. Je to nevratné, takže se to nesmí stát jedním omylem.
 */
export default function MigraceNabidek({ onZavri, onHotovo }) {
  const [nahled, setNahled] = useState(null);
  const [hotovo, setHotovo] = useState(null);
  const [pracuje, setPracuje] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmMigraceStareNabidky(true)
      .then(setNahled)
      .catch((e) => setChyba(e.message));
  }, []);

  async function proved() {
    if (
      !window.confirm(
        `Opravdu zavěsit ${nahled.zpracovano} nabídek? Vznikne ${nahled.novych_zakazniku} nových klientů a ${nahled.zpracovano} obchodních případů. Nelze vzít zpět.`
      )
    )
      return;
    setPracuje(true);
    setChyba(null);
    try {
      const r = await crmMigraceStareNabidky(false);
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
          <h2>Dohledat staré nabídky</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Nabídky vytvořené přímo v nabídkovači (před CRM) nemají zákazníka ani obchodní
            případ. Podle jména zákazníka z nabídky se jim založí <b>klient</b> a{" "}
            <b>obchodní případ</b> a doplní se <b>číslo</b>. Vlastníkem se stane autor
            nabídky, ne ty — jinak by staré zakázky spadly všechny na jednoho.
          </p>

          {d === null ? (
            <div className="crm-prazdno">Načítám náhled…</div>
          ) : (
            <>
              <dl className="crm-udaje">
                <dt>Nabídek bez případu</dt>
                <dd>{d.nabidek_bez_pripadu}</dd>
                <dt>{hotovo ? "Zavěšeno" : "Zavěsí se"}</dt>
                <dd>{d.zpracovano}</dd>
                <dt>{hotovo ? "Vzniklo klientů" : "Vznikne klientů"}</dt>
                <dd>{d.novych_zakazniku}</dd>
                <dt>Přeskočeno</dt>
                <dd>{d.preskoceno.length}</dd>
              </dl>

              {d.plan.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>
                    {hotovo ? "Zavěšené nabídky" : "Co se zavěsí"}
                  </h3>
                  <table className="crm-tabulka crm-tabulka-hustá">
                    <thead>
                      <tr>
                        <th>Nabídka</th>
                        <th>Typ</th>
                        <th>Zákazník</th>
                        <th>Případ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.plan.map((x) => (
                        <tr key={x.nabidka_id}>
                          <td className="crm-silne">{x.cislo}</td>
                          <td>{TYPY[x.typ] || x.typ}</td>
                          <td>
                            {x.zakaznik}
                            {x.zakaznik_novy && (
                              <span className="crm-znacka">nový klient</span>
                            )}
                          </td>
                          <td>{x.pripad}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              {d.preskoceno.length > 0 && (
                <>
                  <h3 style={{ marginTop: 16 }}>Přeskočené</h3>
                  <p className="crm-tise">
                    Tyhle nabídky nemají jméno zákazníka, takže nemají kam patřit —
                    zakládat pro ně prázdné klienty by jen zaneslo evidenci. Buď je smaž
                    v nabídkovači, nebo jim jméno doplň a spusť dohledání znovu.
                  </p>
                  <div className="crm-volby">
                    {d.preskoceno.map((x) => (
                      <span key={x.id} className="crm-znacka">
                        #{x.id} · {TYPY[x.typ] || x.typ}
                      </span>
                    ))}
                  </div>
                </>
              )}

              {hotovo && <div className="crm-zprava">Hotovo. Nabídky jsou zavěšené.</div>}
              {chyba && <div className="crm-chyba">{chyba}</div>}
            </>
          )}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            {hotovo ? "Zavřít" : "Zrušit"}
          </button>
          <span className="crm-mezera" />
          {!hotovo && d && d.zpracovano > 0 && (
            <button className="fm-btn fm-primary" onClick={proved} disabled={pracuje}>
              {pracuje ? "Zavěšuji…" : `Zavěsit ${d.zpracovano} nabídek`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
