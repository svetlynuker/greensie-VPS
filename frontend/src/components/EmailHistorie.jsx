import { useEffect, useState } from "react";
import { emailHistorie } from "../api";
import { fmtDatumCas } from "../crm";

/**
 * Historie e-mailové komunikace na kartě zákazníka nebo obchodního případu.
 *
 * Po vzoru Raynetu („rejnetované" e-maily): zpráva, ve které figuruje adresa
 * někoho z CRM, se sama napojí na jeho firmu a je vidět tady — aby komunikace
 * nezapadla v cizí schránce.
 *
 * ---- Co se tu ukazuje a co ne -------------------------------------------
 * Jen **hlavička a náhled**, nikdy celé tělo. Schránky jsou osobní; tohle je
 * ústupek ve prospěch toho, aby kolegové věděli, co už zákazníkovi odešlo.
 * Kdo chce číst celou zprávu, musí být majitel schránky a otevřít si ji
 * v E-mailu — u svých zpráv proto svítí odkaz „otevřít".
 *
 * Do CRM se napojí jen zpráva, jejíž adresa **přesně sedí** na záznam
 * v systému. Osobní pošta od neznámých adres se sem nedostane vůbec.
 */
export default function EmailHistorie({ entita, zaznamId }) {
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    let zivy = true;
    setData(null);
    setChyba(null);
    emailHistorie(entita, zaznamId)
      .then((d) => zivy && setData(d))
      .catch((e) => {
        // „Nenalezeno" (cizí záznam) nebo chybějící právo. Není to chyba,
        // jen se sekce neukáže — proto tichý stav místo červené hlášky.
        if (zivy) {
          const zpr = String(e.message);
          const skryt = zpr.includes("Nenalezeno") || zpr.includes("nemáš oprávnění");
          setChyba(skryt ? "skryto" : e.message);
        }
      });
    return () => {
      zivy = false;
    };
  }, [entita, zaznamId]);

  if (chyba === "skryto") return null;

  return (
    <section className="fm-card crm-blok">
      <h3>
        Komunikace e-mailem
        {data?.celkem ? <span className="crm-tise"> · {data.celkem}</span> : null}
      </h3>
      <p className="crm-tise">
        Zprávy, ve kterých figuruje adresa z tohohle záznamu — spárují se samy.
        Zobrazuje se předmět a náhled; celou zprávu si otevře jen majitel schránky.
      </p>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {data === null && !chyba && <p className="crm-tise">Načítám…</p>}

      {data && data.zpravy.length === 0 && (
        <p className="crm-tise">
          Zatím žádná spárovaná komunikace. Napojí se sama, jakmile přijde nebo
          odejde zpráva na adresu, kterou má tenhle záznam v CRM.
        </p>
      )}

      {data && data.zpravy.length > 0 && (
        <div className="eh-seznam">
          {data.zpravy.map((z) => (
            <div key={z.id} className="eh-radek">
              <span
                className={`eh-smer ${z.smer === "odchozi" ? "eh-ven" : "eh-dovnitr"}`}
                title={z.smer === "odchozi" ? "Odesláno" : "Přijato"}
              >
                {z.smer === "odchozi" ? "↗" : "↘"}
              </span>
              <div className="eh-telo">
                <div className="eh-hlava">
                  <span className="eh-predmet">{z.predmet || "(bez předmětu)"}</span>
                  {z.ma_prilohy && <span title="Příloha">📎</span>}
                  <span className="crm-mezera" style={{ flex: 1 }} />
                  <span className="eh-datum">{fmtDatumCas(z.datum_at)}</span>
                </div>
                <div className="crm-tise">
                  {z.smer === "odchozi"
                    ? `komu ${(z.komu || []).map((a) => a.adresa).join(", ") || "—"}`
                    : `od ${z.od_jmeno || z.od_adresa}`}
                  {z.kontakt_jmeno ? ` · ${z.kontakt_jmeno}` : ""}
                  {z.pripad_cislo ? ` · ${z.pripad_cislo}` : ""}
                  {z.kdo ? ` · schránka: ${z.kdo}` : ""}
                </div>
                {z.vypis && <div className="eh-vypis">{z.vypis}</div>}
              </div>
              {z.moje && (
                <a className="fm-btn crm-btn-maly" href="/emaily" title="Otevřít v E-mailu">
                  Otevřít
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
