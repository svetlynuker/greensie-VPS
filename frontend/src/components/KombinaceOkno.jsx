import { useEffect, useState } from "react";
import { crmKombinaceZdroje, crmSpojNabidky } from "../api";
import { fmtKc } from "../crm";

/**
 * Spojení PPA a peak shaving nabídky do jedné nabídky pro zákazníka.
 *
 * Nic se nepočítá — berou se dva hotové výsledky a skládá se z nich třetí
 * dokument. Nabízejí se proto jen nabídky se SPOČÍTANÝM řešením; z prázdné
 * nabídky by vznikla kombinace bez čísel.
 *
 * Existující kombinaci lze **aktualizovat ze zdrojů**. Není to automatické
 * schválně: kdyby se kombinace sama přepočítávala, nešlo by dohledat, s jakými
 * čísly nabídka odešla zákazníkovi.
 */
export default function KombinaceOkno({ pripad, onZavri, onHotovo }) {
  const [zdroje, setZdroje] = useState(null);
  const [ppaId, setPpaId] = useState("");
  const [psId, setPsId] = useState("");
  const [cil, setCil] = useState(""); // id existující kombinace k aktualizaci
  const [vysledek, setVysledek] = useState(null);
  const [pracuje, setPracuje] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmKombinaceZdroje(pripad.id)
      .then((z) => {
        setZdroje(z);
        // Předvybereme první spočítanou z každé strany – obvykle je jen jedna.
        const ppa = z.ppa.find((x) => x.spocitana);
        const ps = z.peak_shaving.find((x) => x.spocitana);
        if (ppa) setPpaId(String(ppa.id));
        if (ps) setPsId(String(ps.id));
      })
      .catch((e) => setChyba(e.message));
  }, [pripad.id]);

  async function spoj() {
    setPracuje(true);
    setChyba(null);
    try {
      const r = await crmSpojNabidky(pripad.id, {
        ppaNabidkaId: Number(ppaId),
        psNabidkaId: Number(psId),
        nabidkaId: cil ? Number(cil) : null,
      });
      setVysledek(r);
      await onHotovo?.(r);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  const ppaSpocitane = (zdroje?.ppa || []).filter((x) => x.spocitana);
  const psSpocitane = (zdroje?.peak_shaving || []).filter((x) => x.spocitana);
  const chybiPpa = (zdroje?.ppa || []).length === 0;
  const chybiPs = (zdroje?.peak_shaving || []).length === 0;
  const nespocitane =
    !chybiPpa && !chybiPs && (ppaSpocitane.length === 0 || psSpocitane.length === 0);

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Kombinace opatření</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Spojí hotovou nabídku na <b>PPA</b> a na <b>peak shaving</b> do jednoho dokumentu
            pro zákazníka, který chce obojí. Nic se nepřepočítává — berou se spočítané
            výsledky obou nabídek.
          </p>

          {zdroje === null ? null : chybiPpa || chybiPs ? (
            <div className="crm-prazdno">
              Ke spojení jsou potřeba obě nabídky. Případ zatím nemá
              {chybiPpa ? " nabídku na PPA" : ""}
              {chybiPpa && chybiPs ? " ani " : ""}
              {chybiPs ? " nabídku na peak shaving" : ""}. Založ ji na záložce Nabídky.
            </div>
          ) : nespocitane ? (
            <div className="crm-prazdno">
              Obě nabídky musí mít spuštěný výpočet — z prázdné nabídky by kombinace byla
              bez čísel. Spočítej je na záložce Nabídky a vrať se sem.
            </div>
          ) : (
            <>
              <div className="crm-mrizka">
                <div>
                  <label className="crm-label">Nabídka na PPA</label>
                  <select
                    className="crm-pole"
                    value={ppaId}
                    onChange={(e) => setPpaId(e.target.value)}
                  >
                    {ppaSpocitane.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.cislo}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="crm-label">Nabídka na peak shaving</label>
                  <select
                    className="crm-pole"
                    value={psId}
                    onChange={(e) => setPsId(e.target.value)}
                  >
                    {psSpocitane.map((x) => (
                      <option key={x.id} value={x.id}>
                        {x.cislo}
                      </option>
                    ))}
                  </select>
                </div>
                {(zdroje.kombinace || []).length > 0 && (
                  <div>
                    <label className="crm-label">Kam uložit</label>
                    <select
                      className="crm-pole"
                      value={cil}
                      onChange={(e) => setCil(e.target.value)}
                    >
                      <option value="">— nová kombinovaná nabídka —</option>
                      {zdroje.kombinace.map((k) => (
                        <option key={k.id} value={k.id}>
                          aktualizovat {k.cislo}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>

              {/* Výhrada, kterou musí obchodník znát, než to pošle zákazníkovi. */}
              <div className="crm-varovani">
                <b>Na co si dát pozor:</b> oba výpočty běžely nad původním profilem spotřeby.
                Fotovoltaika přes den snižuje odběr ze sítě, takže skutečné špičky po její
                instalaci mohou být nižší a baterie může být navržená s rezervou. Úspory se
                nesčítají dvakrát za totéž — elektrárna šetří na ceně energie, baterie na
                rezervované kapacitě.
              </div>

              {vysledek && (
                <div className="crm-zprava">
                  Spojeno do nabídky <b>{vysledek.cislo}</b>. Úspora v 1. roce{" "}
                  {fmtKc(vysledek.souhrn?.uspora_rok1_celkem_kc)}, celkem za dobu kontraktu{" "}
                  {fmtKc(vysledek.souhrn?.uspora_kum_celkem_kc)}, investice{" "}
                  {fmtKc(vysledek.souhrn?.investice_zakaznika_kc)}.
                </div>
              )}

              {chyba && <div className="crm-chyba">{chyba}</div>}
            </>
          )}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zavřít
          </button>
          <span className="crm-mezera" />
          {!chybiPpa && !chybiPs && !nespocitane && (
            <button
              className="fm-btn fm-primary"
              onClick={spoj}
              disabled={pracuje || !ppaId || !psId}
            >
              {pracuje ? "Spojuji…" : cil ? "Aktualizovat ze zdrojů" : "Spojit do nabídky"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
