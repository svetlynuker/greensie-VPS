import { useEffect, useState } from "react";
import { crmNastaveniNotifikaci, crmUlozNastaveniNotifikaci } from "../api";

/**
 * Volba notifikací (CRM-36) — sekce na stránce Nastavení.
 *
 * Dvě zaškrtávátka na událost: **v appce** (zvoneček) a **e-mailem**. Rozdělení
 * je celý smysl téhle obrazovky — bez něj by se člověk musel rozhodnout mezi
 * „vím o všem" a „nechte mě být", a vybral by si druhé.
 *
 * Ukládá se hned po kliknutí, ne přes tlačítko Uložit: je to jedno zaškrtnutí,
 * a formulář s potvrzením by tu byl obřad navíc. Chyba se vypíše a zaškrtnutí
 * se vrátí zpět, aby na obrazovce nezůstal stav, který v DB není.
 */
export default function NotifikaceNastaveni() {
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [uklada, setUklada] = useState(false);

  useEffect(() => {
    crmNastaveniNotifikaci()
      .then(setData)
      .catch((e) => setChyba(e.message));
  }, []);

  async function prepni(klic, kanal, hodnota) {
    if (!data) return;
    const puvodni = data.volby;
    const nove = {
      ...puvodni,
      [klic]: { ...(puvodni[klic] || {}), [kanal]: hodnota },
    };
    setData({ ...data, volby: nove });
    setUklada(true);
    setChyba(null);
    try {
      const odpoved = await crmUlozNastaveniNotifikaci(nove);
      setData(odpoved);
    } catch (e) {
      setData({ ...data, volby: puvodni });
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  if (chyba && !data) {
    return (
      <section className="fm-card">
        <div className="gs-karta-hlava">
          <span className="gs-karta-titulek">Notifikace</span>
        </div>
        <p className="crm-chyba">{chyba}</p>
      </section>
    );
  }
  if (!data) return null;

  return (
    <section className="fm-card">
      <div className="gs-karta-hlava">
        <span className="gs-karta-titulek">Notifikace</span>
        <span className="gs-tb-spacer" />
        {uklada && <span className="crm-tise">Ukládám…</span>}
      </div>
      <p className="gs-karta-popis">
        Co chceš vědět a jak. <b>V appce</b> se objeví u zvonečku nahoře,{" "}
        <b>e-mailem</b> přijde na {" "}
        {data.email_funguje ? "tvoji adresu" : "tvoji adresu — až bude odesílání nastavené"}.
        Nastavení je jen tvoje.
      </p>

      {!data.email_funguje && (
        <p className="crm-tise crm-napoveda">
          ⚠ Odesílání e-mailů zatím není na serveru nastavené (chybí heslo schránky
          v konfiguraci). Volba se uloží, ale e-maily začnou chodit až potom.
        </p>
      )}

      {chyba && <p className="crm-chyba">{chyba}</p>}

      <table className="crm-tabulka nt-nastaveni">
        <thead>
          <tr>
            <th>Událost</th>
            <th className="nt-sloupec-volba">V appce</th>
            <th className="nt-sloupec-volba">E-mailem</th>
          </tr>
        </thead>
        <tbody>
          {data.udalosti.map((u) => {
            const v = data.volby[u.klic] || {};
            return (
              <tr key={u.klic}>
                <td>
                  <div className="crm-nastaveni-nazev">{u.nazev}</div>
                  {u.popis && <div className="crm-tise">{u.popis}</div>}
                </td>
                <td className="nt-sloupec-volba">
                  <input
                    type="checkbox"
                    checked={Boolean(v.appka)}
                    onChange={(e) => prepni(u.klic, "appka", e.target.checked)}
                    aria-label={`${u.nazev} – v appce`}
                  />
                </td>
                <td className="nt-sloupec-volba">
                  <input
                    type="checkbox"
                    checked={Boolean(v.email)}
                    onChange={(e) => prepni(u.klic, "email", e.target.checked)}
                    aria-label={`${u.nazev} – e-mailem`}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
