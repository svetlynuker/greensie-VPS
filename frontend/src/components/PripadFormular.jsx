import { useEffect, useState } from "react";
import {
  crmPripadUprav,
  crmPripadZaloz,
  crmUzivatele,
  crmVlastniPole,
  crmZakaznici,
} from "../api";
import { KATEGORIE_OP } from "../crm";
import VlastniPoleVstupy from "./VlastniPoleVstupy";

/**
 * Formulář obchodního případu.
 *
 * Číslo (OP-RR-NNNN) přiděluje backend z číselné řady – v UI se nezadává,
 * aby nemohly vzniknout dva případy se stejným ID.
 *
 * `raynet_code` je vidět jen při úpravě: je to most na složky Google Disku
 * u případů, které vznikly ještě v Raynetu. U nových se nechává prázdný.
 */
export default function PripadFormular({
  pripad = null,
  zakaznik = null,
  muzeMenitVlastnika = false,
  onZavri,
  onHotovo,
}) {
  const jeUprava = Boolean(pripad);
  const [form, setForm] = useState(() => ({
    zakaznik_id: pripad?.zakaznik_id || zakaznik?.id || null,
    nazev: pripad?.nazev || "",
    popis: pripad?.popis || "",
    kategorie: pripad?.kategorie || [],
    hodnota_kc: pripad?.hodnota_kc != null ? String(pripad.hodnota_kc) : "",
    pravdepodobnost: pripad?.pravdepodobnost != null ? String(pripad.pravdepodobnost) : "",
    predpokladane_uzavreni: (pripad?.predpokladane_uzavreni || "").slice(0, 10),
    vlastnik_user_id: pripad?.vlastnik_user_id || null,
    spoluvlastnici: pripad?.spoluvlastnici || [],
    raynet_code: pripad?.raynet_code || "",
    extra: pripad?.extra || {},
  }));
  const [zakaznici, setZakaznici] = useState(zakaznik ? [zakaznik] : []);
  const [vlastniPole, setVlastniPole] = useState(pripad?.vlastni_pole || []);
  const [lidi, setLidi] = useState([]);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    // Výběr zákazníka nabízíme jen tam, kde není předvybraný (sekce Případy).
    if (zakaznik) return;
    crmZakaznici()
      .then(setZakaznici)
      .catch(() => setZakaznici([]));
  }, [zakaznik]);

  useEffect(() => {
    if (pripad?.vlastni_pole) return;
    crmVlastniPole("op")
      .then(setVlastniPole)
      .catch(() => setVlastniPole([]));
  }, [pripad]);

  useEffect(() => {
    if (!muzeMenitVlastnika) return;
    crmUzivatele()
      .then(setLidi)
      .catch(() => setLidi([]));
  }, [muzeMenitVlastnika]);

  function zmen(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  function prepniKategorii(klic) {
    setForm((f) => ({
      ...f,
      kategorie: f.kategorie.includes(klic)
        ? f.kategorie.filter((k) => k !== klic)
        : [...f.kategorie, klic],
    }));
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      const data = {
        ...form,
        nazev: form.nazev.trim(),
        hodnota_kc:
          form.hodnota_kc.trim() === "" ? null : Number(form.hodnota_kc.replace(",", ".")),
        pravdepodobnost:
          form.pravdepodobnost.trim() === "" ? null : Number(form.pravdepodobnost),
        predpokladane_uzavreni: form.predpokladane_uzavreni || null,
      };
      const vysledek = jeUprava
        ? await crmPripadUprav(pripad.id, data)
        : await crmPripadZaloz(data);
      onHotovo(vysledek);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? `Úprava ${pripad.cislo}` : "Nový obchodní případ"}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          {!jeUprava && (
            <p className="crm-tise">
              Číslo případu (OP-RR-NNNN) přidělí appka sama při založení.
            </p>
          )}

          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Zákazník *</label>
              {zakaznik ? (
                <input className="crm-pole" value={zakaznik.nazev} disabled />
              ) : (
                <select
                  className="crm-pole"
                  value={form.zakaznik_id || ""}
                  onChange={(e) =>
                    zmen("zakaznik_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">— vyber zákazníka —</option>
                  {zakaznici.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.nazev}
                      {z.ico ? ` (${z.ico})` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="crm-label">Název případu</label>
              <input
                className="crm-pole"
                value={form.nazev}
                onChange={(e) => zmen("nazev", e.target.value)}
                placeholder="např. FVE na střeše výrobní haly"
              />
            </div>

            {/* Kategorie je schválně víc než jedna: případ může být PPA
                i peak shaving současně a podle toho pak míří do výpočtů. */}
            <div className="crm-sirka3">
              <label className="crm-label">Kategorie (můžeš vybrat víc)</label>
              <div className="crm-volby">
                {KATEGORIE_OP.map((k) => (
                  <button
                    key={k.klic}
                    type="button"
                    className={`crm-pilulka ${form.kategorie.includes(k.klic) ? "aktivni" : ""}`}
                    onClick={() => prepniKategorii(k.klic)}
                    title={k.popis}
                  >
                    {k.nazev}
                  </button>
                ))}
              </div>
              <p className="crm-tise" style={{ marginTop: 6 }}>
                Podle kategorie pozná appka, kam poslat výpočet nabídky. Když necháš prázdné,
                zeptá se při vytvoření nabídky.
              </p>
            </div>

            <div>
              <label className="crm-label">Hodnota (Kč)</label>
              <input
                className="crm-pole"
                value={form.hodnota_kc}
                onChange={(e) => zmen("hodnota_kc", e.target.value)}
                inputMode="decimal"
                placeholder="např. 1500000"
              />
            </div>
            <div>
              <label className="crm-label">Pravděpodobnost (%)</label>
              <input
                className="crm-pole"
                value={form.pravdepodobnost}
                onChange={(e) => zmen("pravdepodobnost", e.target.value)}
                inputMode="numeric"
                placeholder="0–100"
              />
            </div>
            <div>
              <label className="crm-label">Předpokládané uzavření</label>
              <input
                className="crm-pole"
                type="date"
                value={form.predpokladane_uzavreni}
                onChange={(e) => zmen("predpokladane_uzavreni", e.target.value)}
              />
            </div>

            {muzeMenitVlastnika && (
              <div>
                <label className="crm-label">Vlastník případu</label>
                <select
                  className="crm-pole"
                  value={form.vlastnik_user_id || ""}
                  onChange={(e) =>
                    zmen("vlastnik_user_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">— já —</option>
                  {lidi.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.jmeno}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {jeUprava && (
              <div>
                <label className="crm-label">Raynetí číslo (koexistence)</label>
                <input
                  className="crm-pole"
                  value={form.raynet_code}
                  onChange={(e) => zmen("raynet_code", e.target.value)}
                  placeholder="OP-26-0223"
                />
                <p className="crm-tise" style={{ marginTop: 6 }}>
                  Vyplň u případů, které vznikly v Raynetu – přes tohle číslo se páruje
                  složka dokumentů na Disku.
                </p>
              </div>
            )}

            <div className="crm-sirka3">
              <label className="crm-label">Popis</label>
              <textarea
                className="crm-pole"
                rows={3}
                value={form.popis}
                onChange={(e) => zmen("popis", e.target.value)}
              />
            </div>

            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={form.extra}
              onZmena={(extra) => zmen("extra", extra)}
            />
          </div>

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={uloz}
            disabled={uklada || !form.zakaznik_id}
          >
            {uklada ? "Ukládám…" : jeUprava ? "Uložit změny" : "Založit případ"}
          </button>
        </div>
      </div>
    </div>
  );
}
