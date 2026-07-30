import { useEffect, useState } from "react";
import {
  crmAktivitaPridej,
  crmAktivitaSmaz,
  crmAktivitaUprav,
  crmAktivity,
} from "../api";
import {
  DRUHY_AKTIVITY,
  STAVY_AKTIVITY,
  fmtCas,
  fmtDatum,
  jeNaplanovana,
  jePoTerminu,
  nazevStavuAktivity,
} from "../crm";

/**
 * Log práce se záznamem: poznámky, telefonáty, e-maily, schůzky a úkoly.
 *
 * Aktivita s termínem je úkol – nedokončené jdou nahoru a po termínu se
 * zvýrazní. Kvůli tomuhle bude OZ v appce žít; bez logu a dalšího kroku by si
 * stejně vedl zápisky vedle a CRM by zůstalo prázdnou evidencí.
 *
 * Práva: aktivity se řídí přístupem k nadřazenému záznamu (řeší backend).
 */
export default function Aktivity({ entita, zaznamId }) {
  const [seznam, setSeznam] = useState(null);
  const [druh, setDruh] = useState("poznamka");
  const [text, setText] = useState("");
  const [termin, setTermin] = useState("");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function nacti() {
    try {
      setSeznam(await crmAktivity(entita, zaznamId));
    } catch (e) {
      setChyba(e.message);
    }
  }

  useEffect(() => {
    setSeznam(null);
    crmAktivity(entita, zaznamId)
      .then(setSeznam)
      .catch((e) => setChyba(e.message));
  }, [entita, zaznamId]);

  async function pridej() {
    if (!text.trim()) return;
    setUklada(true);
    setChyba(null);
    try {
      await crmAktivitaPridej(entita, zaznamId, {
        druh,
        text: text.trim(),
        termin: termin || null,
      });
      setText("");
      setTermin("");
      await nacti();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /** Uzavření aktivity: proběhla, nebo se nekonala — a s jakým výsledkem.
   *
   *  Výsledek se ptá jen při uzavírání. „Zavolal jsem, chce to po dovolené" je
   *  ta hodnotná informace; bez ní by v CRM zůstalo jen odškrtnuté políčko. */
  async function uzavri(a, stav) {
    const otazka =
      stav === "realizovano"
        ? "Jak to šlo? (nepovinné)"
        : "Proč se to nekonalo? (nepovinné)";
    const vysledek = window.prompt(otazka, a.vysledek || "");
    if (vysledek === null) return; // Escape = nechat být
    try {
      await crmAktivitaUprav(a.id, { stav, vysledek });
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function vratDoPlanu(a) {
    try {
      await crmAktivitaUprav(a.id, { stav: "naplanovano" });
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(a) {
    if (!window.confirm("Smazat tento záznam?")) return;
    try {
      await crmAktivitaSmaz(a.id);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div className="crm-aktivity">
      <div className="crm-aktivita-novy">
        <div className="crm-aktivita-druhy">
          {DRUHY_AKTIVITY.map((d) => (
            <button
              key={d.klic}
              className={`crm-pilulka ${druh === d.klic ? "aktivni" : ""}`}
              onClick={() => setDruh(d.klic)}
              type="button"
              title={d.nazev}
            >
              <span aria-hidden="true">{d.ikona}</span> {d.nazev}
            </button>
          ))}
        </div>
        <textarea
          className="crm-pole"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            druh === "ukol"
              ? "Co je potřeba udělat? (nastav termín a úkol se objeví v tvých úkolech)"
              : "Co se stalo? Zapiš, ať to nezůstane jen v hlavě."
          }
        />
        <div className="crm-aktivita-pata">
          <label className="crm-label" htmlFor="crm-termin">
            Termín {druh === "ukol" ? "(dělá z toho úkol)" : "(nepovinný)"}
          </label>
          <input
            id="crm-termin"
            className="crm-pole crm-pole-uzke"
            type="date"
            value={termin}
            onChange={(e) => setTermin(e.target.value)}
          />
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={pridej}
            disabled={uklada || !text.trim()}
          >
            {uklada ? "Ukládám…" : "Přidat"}
          </button>
        </div>
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {seznam === null ? null : seznam.length === 0 ? (
        <div className="crm-prazdno">
          Zatím žádný záznam. Napiš první poznámku nebo si založ úkol.
        </div>
      ) : (
        <ul className="crm-casova-osa">
          {seznam.map((a) => {
            const d = DRUHY_AKTIVITY.find((x) => x.klic === a.druh);
            const jeUkol = Boolean(a.termin);
            const ceka = jeNaplanovana(a);
            const poTerminu = jeUkol && ceka && jePoTerminu(a.termin);
            const stav = STAVY_AKTIVITY.find((s) => s.klic === a.stav);
            return (
              <li key={a.id} className={`crm-osa-radek ${ceka ? "" : "hotovo"}`}>
                <span className="crm-osa-ikona" aria-hidden="true">
                  {d?.ikona || "•"}
                </span>
                <div className="crm-osa-telo">
                  <div className="crm-osa-text">
                    {a.nazev ? <b>{a.nazev}</b> : null}
                    {a.nazev && a.text ? " — " : ""}
                    {a.text}
                  </div>
                  {a.vysledek && (
                    <div className="crm-osa-vysledek">
                      <b>{a.stav === "nekonalo_se" ? "Nekonalo se:" : "Výsledek:"}</b>{" "}
                      {a.vysledek}
                    </div>
                  )}
                  <div className="crm-osa-meta">
                    {d?.nazev || a.druh}
                    {!ceka && stav ? ` · ${stav.nazev}` : ""}
                    {a.vytvoril_jmeno ? ` · ${a.vytvoril_jmeno}` : ""}
                    {a.vytvoreno_at ? ` · ${fmtDatum(a.vytvoreno_at)}` : ""}
                    {jeUkol && (
                      <span className={poTerminu ? "crm-po-terminu" : "crm-termin-ok"}>
                        {" · termín "}
                        {fmtDatum(a.termin)}
                        {a.zacatek ? ` ${fmtCas(a.zacatek, a.delka_min)}` : ""}
                        {poTerminu ? " (po termínu)" : ""}
                      </span>
                    )}
                    {a.vlastnik_jmeno && jeUkol ? ` · řeší ${a.vlastnik_jmeno}` : ""}
                  </div>
                </div>
                {jeUkol && ceka && (
                  <>
                    <button
                      className="fm-btn crm-btn-maly"
                      onClick={() => uzavri(a, "realizovano")}
                      title="Proběhlo — zapiš, jak to šlo"
                    >
                      Realizováno
                    </button>
                    <button
                      className="fm-btn crm-btn-maly"
                      onClick={() => uzavri(a, "nekonalo_se")}
                      title="Nekonalo se — zapiš proč"
                    >
                      Nekonalo se
                    </button>
                  </>
                )}
                {jeUkol && !ceka && (
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => vratDoPlanu(a)}
                    title={`${nazevStavuAktivity(a.stav)} — vrátit mezi naplánované`}
                  >
                    Vrátit
                  </button>
                )}
                <button
                  className="fm-btn crm-btn-maly crm-btn-smazat"
                  onClick={() => smaz(a)}
                  title="Smazat"
                >
                  ✕
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
