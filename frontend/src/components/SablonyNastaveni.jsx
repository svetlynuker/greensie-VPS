import { useEffect, useState } from "react";
import {
  crmSablonaKrokPridej,
  crmSablonaKrokSmaz,
  crmSablonaPridej,
  crmSablonaSmaz,
  crmSablony,
} from "../api";
import { KATEGORIE_OP } from "../crm";

/**
 * Šablony projektových kroků – „takhle u nás vypadá FVE realizace".
 *
 * Vedení si nachystá posloupnost kroků s trváním a návaznostmi; na projektu se
 * pak rozbalí do konkrétních úkolů s termíny. Bez šablon by kroky psal každý
 * ručně a pokaždé jinak.
 *
 * Návaznost se v šabloně drží jako POŘADÍ předchůdce, ne jeho id — šablona se
 * do projektu kopíruje a tam vznikají nové řádky s novými id, takže odkaz přes
 * id by po kopii nesouhlasil.
 */
export default function SablonyNastaveni({ muzeEditovat = false, onZavri }) {
  const [sablony, setSablony] = useState(null);
  const [vybrana, setVybrana] = useState(null);
  const [novaSablona, setNovaSablona] = useState({ nazev: "", popis: "", kategorie: [] });
  const [novyKrok, setNovyKrok] = useState({ nazev: "", delka_dni: "5", zavisi_na_poradi: "" });
  const [chyba, setChyba] = useState(null);

  async function nacti(zvolit = null) {
    const s = await crmSablony();
    setSablony(s);
    if (zvolit !== null) setVybrana(s.find((x) => x.id === zvolit) || null);
    else if (vybrana) setVybrana(s.find((x) => x.id === vybrana.id) || null);
  }

  useEffect(() => {
    crmSablony()
      .then((s) => {
        setSablony(s);
        setVybrana(s[0] || null);
      })
      .catch((e) => setChyba(e.message));
  }, []);

  async function pridejSablonu() {
    if (!novaSablona.nazev.trim()) return;
    setChyba(null);
    try {
      const s = await crmSablonaPridej({
        nazev: novaSablona.nazev.trim(),
        popis: novaSablona.popis.trim(),
        kategorie: novaSablona.kategorie,
      });
      setNovaSablona({ nazev: "", popis: "", kategorie: [] });
      await nacti(s.id);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function pridejKrok() {
    if (!vybrana || !novyKrok.nazev.trim()) return;
    setChyba(null);
    try {
      const s = await crmSablonaKrokPridej(vybrana.id, {
        nazev: novyKrok.nazev.trim(),
        delka_dni: Number(novyKrok.delka_dni) || 1,
        zavisi_na_poradi:
          novyKrok.zavisi_na_poradi === "" ? null : Number(novyKrok.zavisi_na_poradi),
      });
      setVybrana(s);
      setNovyKrok({ nazev: "", delka_dni: "5", zavisi_na_poradi: "" });
      await nacti(s.id);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smazKrok(krok) {
    setChyba(null);
    try {
      const s = await crmSablonaKrokSmaz(krok.id);
      setVybrana(s);
      await nacti(s.id);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smazSablonu(s) {
    if (
      !window.confirm(
        `Smazat šablonu „${s.nazev}"? Projekty, které z ní vznikly, zůstanou nedotčené.`
      )
    )
      return;
    setChyba(null);
    try {
      await crmSablonaSmaz(s.id);
      setVybrana(null);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  function prepniKategorii(klic) {
    setNovaSablona((n) => ({
      ...n,
      kategorie: n.kategorie.includes(klic)
        ? n.kategorie.filter((k) => k !== klic)
        : [...n.kategorie, klic],
    }));
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Šablony projektových kroků</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Šablona se na projektu rozbalí do kroků s termíny. <b>Trvání</b> je počet dní kroku,
            <b> navazuje na</b> říká, od kterého kroku se termín počítá — když se předchůdce
            zdrží, posunou se kroky za ním.
          </p>

          {sablony === null ? null : (
            <div className="crm-volby" style={{ marginBottom: 12 }}>
              {sablony.map((s) => (
                <button
                  key={s.id}
                  className={`crm-pilulka ${vybrana?.id === s.id ? "aktivni" : ""}`}
                  onClick={() => setVybrana(s)}
                >
                  {s.nazev} ({s.kroky.length})
                </button>
              ))}
              {sablony.length === 0 && <span className="crm-tise">Žádná šablona.</span>}
            </div>
          )}

          {vybrana && (
            <>
              <div className="crm-blok-hlava">
                <h3>{vybrana.nazev}</h3>
                <span className="crm-mezera" />
                {muzeEditovat && (
                  <button
                    className="fm-btn crm-btn-maly crm-btn-smazat"
                    onClick={() => smazSablonu(vybrana)}
                  >
                    Smazat šablonu
                  </button>
                )}
              </div>
              {vybrana.popis && <p className="crm-tise">{vybrana.popis}</p>}
              {vybrana.kategorie?.length > 0 && (
                <p className="crm-tise">
                  Pro kategorie:{" "}
                  {vybrana.kategorie
                    .map((k) => KATEGORIE_OP.find((x) => x.klic === k)?.nazev || k)
                    .join(", ")}
                </p>
              )}

              <table className="crm-tabulka crm-tabulka-hustá">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Krok</th>
                    <th>Trvání</th>
                    <th>Navazuje na</th>
                    {muzeEditovat && <th />}
                  </tr>
                </thead>
                <tbody>
                  {vybrana.kroky.map((k) => {
                    const predchudce =
                      k.zavisi_na_poradi === null
                        ? null
                        : vybrana.kroky.find((x) => x.poradi === k.zavisi_na_poradi);
                    return (
                      <tr key={k.id}>
                        <td className="crm-tise">{k.poradi + 1}</td>
                        <td className="crm-silne">{k.nazev}</td>
                        <td>{k.delka_dni} dní</td>
                        <td>
                          {predchudce ? (
                            predchudce.nazev
                          ) : (
                            <span className="crm-tise">od zahájení</span>
                          )}
                        </td>
                        {muzeEditovat && (
                          <td className="crm-vpravo">
                            <button
                              className="fm-btn crm-btn-maly crm-btn-smazat"
                              onClick={() => smazKrok(k)}
                              title="Smazat krok"
                            >
                              ✕
                            </button>
                          </td>
                        )}
                      </tr>
                    );
                  })}
                  {vybrana.kroky.length === 0 && (
                    <tr>
                      <td colSpan={muzeEditovat ? 5 : 4} className="crm-prazdno">
                        Šablona zatím nemá kroky.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>

              {muzeEditovat && (
                <div className="crm-stav-novy" style={{ marginTop: 10 }}>
                  <input
                    className="crm-pole"
                    value={novyKrok.nazev}
                    onChange={(e) => setNovyKrok((n) => ({ ...n, nazev: e.target.value }))}
                    placeholder="Název kroku"
                  />
                  <input
                    className="crm-pole crm-pole-cislo"
                    type="number"
                    min={1}
                    value={novyKrok.delka_dni}
                    onChange={(e) => setNovyKrok((n) => ({ ...n, delka_dni: e.target.value }))}
                    title="Trvání ve dnech"
                  />
                  <select
                    className="crm-pole crm-pole-uzke"
                    value={novyKrok.zavisi_na_poradi}
                    onChange={(e) =>
                      setNovyKrok((n) => ({ ...n, zavisi_na_poradi: e.target.value }))
                    }
                  >
                    <option value="">— od zahájení —</option>
                    {vybrana.kroky.map((k) => (
                      <option key={k.id} value={k.poradi}>
                        {k.nazev}
                      </option>
                    ))}
                  </select>
                  <button className="fm-btn fm-primary" onClick={pridejKrok}>
                    Přidat krok
                  </button>
                </div>
              )}
            </>
          )}

          {muzeEditovat && (
            <div className="crm-oddelovac" style={{ marginTop: 20, paddingTop: 14 }}>
              <h3>Nová šablona</h3>
              <div className="crm-mrizka">
                <div className="crm-sirka2">
                  <label className="crm-label">Název</label>
                  <input
                    className="crm-pole"
                    value={novaSablona.nazev}
                    onChange={(e) => setNovaSablona((n) => ({ ...n, nazev: e.target.value }))}
                    placeholder="např. Servisní zásah"
                  />
                </div>
                <div>
                  <label className="crm-label">Nabízet u kategorií</label>
                  <div className="crm-volby">
                    {KATEGORIE_OP.map((k) => (
                      <button
                        key={k.klic}
                        type="button"
                        className={`crm-pilulka ${novaSablona.kategorie.includes(k.klic) ? "aktivni" : ""}`}
                        onClick={() => prepniKategorii(k.klic)}
                      >
                        {k.nazev}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="crm-sirka3">
                  <label className="crm-label">Popis</label>
                  <input
                    className="crm-pole"
                    value={novaSablona.popis}
                    onChange={(e) => setNovaSablona((n) => ({ ...n, popis: e.target.value }))}
                  />
                </div>
              </div>
              <div className="crm-blok-pata">
                <span className="crm-mezera" />
                <button
                  className="fm-btn fm-primary"
                  onClick={pridejSablonu}
                  disabled={!novaSablona.nazev.trim()}
                >
                  Vytvořit šablonu
                </button>
              </div>
            </div>
          )}

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <span className="crm-mezera" />
          <button className="fm-btn fm-primary" onClick={onZavri}>
            Hotovo
          </button>
        </div>
      </div>
    </div>
  );
}
