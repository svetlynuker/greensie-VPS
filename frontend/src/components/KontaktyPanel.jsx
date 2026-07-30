import { useState } from "react";
import { crmKontaktPridej, crmKontaktSmaz, crmKontaktUprav } from "../api";

const PRAZDNY = { jmeno: "", funkce: "", email: "", telefon: "", hlavni: false, poznamka: "" };

/**
 * Kontaktní osoby zákazníka. Hlavní kontakt je jen jeden – backend ostatní
 * automaticky přepne, takže se nemůže stát, že by byli dva „hlavní".
 */
export default function KontaktyPanel({ zakaznik, onZmena }) {
  const [form, setForm] = useState(PRAZDNY);
  const [upravovany, setUpravovany] = useState(null); // id nebo null
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  function zmen(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  function zacniUpravu(k) {
    setUpravovany(k.id);
    setForm({
      jmeno: k.jmeno,
      funkce: k.funkce || "",
      email: k.email || "",
      telefon: k.telefon || "",
      hlavni: Boolean(k.hlavni),
      poznamka: k.poznamka || "",
    });
  }

  function zrus() {
    setUpravovany(null);
    setForm(PRAZDNY);
    setChyba(null);
  }

  async function uloz() {
    if (!form.jmeno.trim()) return;
    setUklada(true);
    setChyba(null);
    try {
      const novy = upravovany
        ? await crmKontaktUprav(upravovany, form)
        : await crmKontaktPridej(zakaznik.id, form);
      onZmena(novy);
      zrus();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function smaz(k) {
    if (!window.confirm(`Smazat kontakt ${k.jmeno}?`)) return;
    try {
      onZmena(await crmKontaktSmaz(k.id));
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div className="fm-card crm-blok">
      <h3>Kontaktní osoby</h3>

      {(zakaznik.kontakty || []).length === 0 ? (
        <p className="crm-tise">Žádný kontakt. Přidej aspoň jednu osobu, ať je s kým mluvit.</p>
      ) : (
        <ul className="crm-kontakty">
          {zakaznik.kontakty.map((k) => (
            <li key={k.id}>
              <div style={{ minWidth: 0 }}>
                <div className="crm-kontakt-jmeno">
                  {k.jmeno}
                  {k.hlavni && <span className="crm-znacka crm-barva-ok">hlavní</span>}
                </div>
                <div className="crm-tise">
                  {[k.funkce, k.telefon, k.email].filter(Boolean).join(" · ") || "—"}
                </div>
              </div>
              <span className="crm-mezera" />
              <button className="fm-btn crm-btn-maly" onClick={() => zacniUpravu(k)}>
                Upravit
              </button>
              <button
                className="fm-btn crm-btn-maly crm-btn-smazat"
                onClick={() => smaz(k)}
                title="Smazat"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="crm-kontakt-form">
        <div className="crm-mrizka">
          <div>
            <label className="crm-label">Jméno *</label>
            <input
              className="crm-pole"
              value={form.jmeno}
              onChange={(e) => zmen("jmeno", e.target.value)}
            />
          </div>
          <div>
            <label className="crm-label">Funkce</label>
            <input
              className="crm-pole"
              value={form.funkce}
              onChange={(e) => zmen("funkce", e.target.value)}
              placeholder="jednatel, energetik…"
            />
          </div>
          <div>
            <label className="crm-label">Telefon</label>
            <input
              className="crm-pole"
              value={form.telefon}
              onChange={(e) => zmen("telefon", e.target.value)}
            />
          </div>
          <div>
            <label className="crm-label">E-mail</label>
            <input
              className="crm-pole"
              value={form.email}
              onChange={(e) => zmen("email", e.target.value)}
            />
          </div>
        </div>
        <label className="crm-zaskrtavaci">
          <input
            type="checkbox"
            checked={form.hlavni}
            onChange={(e) => zmen("hlavni", e.target.checked)}
          />
          Hlavní kontakt
        </label>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <div className="crm-blok-pata">
          {upravovany && (
            <button className="fm-btn" onClick={zrus}>
              Zrušit úpravu
            </button>
          )}
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={uloz}
            disabled={uklada || !form.jmeno.trim()}
          >
            {uklada ? "Ukládám…" : upravovany ? "Uložit kontakt" : "Přidat kontakt"}
          </button>
        </div>
      </div>
    </div>
  );
}
