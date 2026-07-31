import { useCallback, useEffect, useState } from "react";
import {
  emailAutomatikaUloz,
  emailPravidla,
  emailPravidloPridej,
  emailPravidloPrepni,
  emailPravidloSmaz,
  emailPravidloUprav,
} from "../api";

/**
 * Pravidla pro příchozí poštu + OOO oznámení + automatické přeposílání.
 *
 * ---- Co musí být z obrazovky poznat -------------------------------------
 * Že **OOO a přeposílání dělá appka, ne Seznam.** Seznam to zdálky nastavit
 * neumí, takže obojí funguje jen když běží stahování pošty na serveru. Kdyby
 * to obrazovka zamlčela, člověk by odjel na dovolenou s tím, že mu appka
 * odpovídá — a ona by třeba neběžela.
 *
 * Pravidla se vyhodnocují **v pořadí** a „zastavit další" funguje jako
 * v Outlooku. Bez toho by zpráva propadla i pravidly, která už platit nemají.
 */

const POLE = [
  { klic: "od", nazev: "Odesílatel" },
  { klic: "predmet", nazev: "Předmět" },
  { klic: "komu", nazev: "Příjemce" },
  { klic: "telo", nazev: "Text zprávy" },
  { klic: "ma_prilohy", nazev: "Má přílohu" },
];

const OPERATORY = [
  { klic: "obsahuje", nazev: "obsahuje" },
  { klic: "neobsahuje", nazev: "neobsahuje" },
  { klic: "je", nazev: "je přesně" },
  { klic: "zacina", nazev: "začíná na" },
  { klic: "konci", nazev: "končí na" },
];

const TYPY_AKCI = [
  { klic: "presun", nazev: "Přesunout do složky" },
  { klic: "oznacit_precteno", nazev: "Označit jako přečtené" },
  { klic: "oznacit", nazev: "Označit vlaječkou" },
  { klic: "preposlat", nazev: "Přeposlat na adresu" },
];

const PRAZDNE = {
  nazev: "",
  aktivni: true,
  poradi: 100,
  spojka: "a",
  podminky: [{ pole: "od", operator: "obsahuje", hodnota: "" }],
  akce: [{ typ: "presun", slozka_id: null, komu: "" }],
  zastavit_dalsi: false,
};

export default function EmailPravidla({ ucet, slozky = [], onZmenaUctu, onZavri }) {
  const [seznam, setSeznam] = useState([]);
  const [formular, setFormular] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [hlaska, setHlaska] = useState("");

  // ---- OOO a přeposílání ----
  const [ooo, setOoo] = useState({
    ooo_zapnuto: ucet?.ooo_zapnuto || false,
    ooo_od: ucet?.ooo_od ? String(ucet.ooo_od).slice(0, 10) : "",
    ooo_do: ucet?.ooo_do ? String(ucet.ooo_do).slice(0, 10) : "",
    ooo_predmet: ucet?.ooo_predmet || "",
    ooo_text: ucet?.ooo_text || "",
    preposilani_zapnuto: ucet?.preposilani_zapnuto || false,
    preposilani_komu: ucet?.preposilani_komu || "",
    preposilani_nechat_kopii: ucet?.preposilani_nechat_kopii ?? true,
  });
  const [ukladaOoo, setUkladaOoo] = useState(false);

  const nacti = useCallback(() => {
    emailPravidla()
      .then(setSeznam)
      .catch((e) => setChyba(e.message));
  }, []);

  useEffect(() => {
    nacti();
  }, [nacti]);

  async function ulozPravidlo() {
    setChyba(null);
    const data = {
      ...formular,
      // Prázdné hodnoty by na serveru spadly na validaci – uklidíme je tady.
      podminky: formular.podminky.filter(
        (p) => p.pole === "ma_prilohy" || (p.hodnota || "").trim(),
      ),
      akce: formular.akce.filter(
        (a) =>
          (a.typ !== "presun" || a.slozka_id) && (a.typ !== "preposlat" || (a.komu || "").includes("@")),
      ),
    };
    try {
      if (formular.id) await emailPravidloUprav(formular.id, data);
      else await emailPravidloPridej(data);
      setFormular(null);
      nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(p) {
    if (!window.confirm(`Smazat pravidlo „${p.nazev}“?`)) return;
    try {
      await emailPravidloSmaz(p.id);
      nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function prepni(p) {
    try {
      await emailPravidloPrepni(p.id);
      nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function ulozOoo() {
    setUkladaOoo(true);
    setChyba(null);
    setHlaska("");
    try {
      const novy = await emailAutomatikaUloz(ooo);
      setHlaska("Uloženo.");
      if (onZmenaUctu) onZmenaUctu(novy);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUkladaOoo(false);
    }
  }

  function upravPodminku(i, zmena) {
    setFormular((f) => ({
      ...f,
      podminky: f.podminky.map((p, j) => (i === j ? { ...p, ...zmena } : p)),
    }));
  }

  function upravAkci(i, zmena) {
    setFormular((f) => ({
      ...f,
      akce: f.akce.map((a, j) => (i === j ? { ...a, ...zmena } : a)),
    }));
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div
        className="crm-okno em-okno-psani"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="crm-okno-hlava">
          <h2>Pravidla a automatika</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          {chyba && <div className="em-chyba">{chyba}</div>}
          {hlaska && <div className="em-hlaska-ok">{hlaska}</div>}

          <div className="em-obrazky-lista">
            <span>
              <strong>Pozor:</strong> oznámení o nepřítomnosti i přeposílání dělá tahle
              appka, ne Seznam — funguje to jen když na serveru běží stahování pošty.
              Na delší dovolenou si to radši nastav i přímo na seznam.cz.
            </span>
          </div>

          {/* ---- OOO ---- */}
          <section className="fm-card" style={{ padding: 14 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>
              Oznámení o nepřítomnosti
            </h3>
            <label className="em-tise" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={ooo.ooo_zapnuto}
                onChange={(e) => setOoo((o) => ({ ...o, ooo_zapnuto: e.target.checked }))}
              />
              Automaticky odpovídat na příchozí poštu
            </label>

            {ooo.ooo_zapnuto && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>
                <div className="em-pole-dva" style={{ gridTemplateColumns: "1fr 1fr" }}>
                  <div className="em-pole">
                    <label htmlFor="ooo-od">Od (nepovinné)</label>
                    <input
                      id="ooo-od"
                      type="date"
                      value={ooo.ooo_od}
                      onChange={(e) => setOoo((o) => ({ ...o, ooo_od: e.target.value }))}
                    />
                  </div>
                  <div className="em-pole">
                    <label htmlFor="ooo-do">Do (nepovinné)</label>
                    <input
                      id="ooo-do"
                      type="date"
                      value={ooo.ooo_do}
                      onChange={(e) => setOoo((o) => ({ ...o, ooo_do: e.target.value }))}
                    />
                  </div>
                </div>
                <div className="em-pole">
                  <label htmlFor="ooo-predmet">Předmět odpovědi</label>
                  <input
                    id="ooo-predmet"
                    value={ooo.ooo_predmet}
                    onChange={(e) => setOoo((o) => ({ ...o, ooo_predmet: e.target.value }))}
                    placeholder="Jsem mimo kancelář"
                  />
                </div>
                <div className="em-pole">
                  <label htmlFor="ooo-text">Text odpovědi *</label>
                  <textarea
                    id="ooo-text"
                    rows={4}
                    value={ooo.ooo_text}
                    onChange={(e) => setOoo((o) => ({ ...o, ooo_text: e.target.value }))}
                    placeholder="Dobrý den, do 15. 8. jsem mimo kancelář. V naléhavých věcech se obraťte na…"
                  />
                  <p className="em-tise">
                    Jedné adrese odejde odpověď nejvýš jednou za 24 hodin a robotům
                    (newsletterům, automatům) se neodpovídá vůbec — jinak by si dva
                    automaty psaly donekonečna.
                  </p>
                </div>
              </div>
            )}
          </section>

          {/* ---- přeposílání ---- */}
          <section className="fm-card" style={{ padding: 14 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>Automatické přeposílání</h3>
            <label className="em-tise" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={ooo.preposilani_zapnuto}
                onChange={(e) =>
                  setOoo((o) => ({ ...o, preposilani_zapnuto: e.target.checked }))
                }
              />
              Přeposílat příchozí poštu dál
            </label>
            {ooo.preposilani_zapnuto && (
              <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>
                <div className="em-pole">
                  <label htmlFor="prep-komu">Přeposílat na *</label>
                  <input
                    id="prep-komu"
                    type="email"
                    value={ooo.preposilani_komu}
                    onChange={(e) =>
                      setOoo((o) => ({ ...o, preposilani_komu: e.target.value }))
                    }
                    placeholder="kolega@greensie.cz"
                  />
                </div>
                <label className="em-tise" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={ooo.preposilani_nechat_kopii}
                    onChange={(e) =>
                      setOoo((o) => ({ ...o, preposilani_nechat_kopii: e.target.checked }))
                    }
                  />
                  Nechat kopii ve své schránce
                </label>
                <p className="em-tise">
                  Přílohy se automatickým přeposláním nepřenášejí a newslettery se
                  nepřeposílají vůbec (jinak by cíl zahltily).
                </p>
              </div>
            )}
          </section>

          <button
            className="fm-btn fm-primary"
            onClick={ulozOoo}
            disabled={ukladaOoo}
            style={{ alignSelf: "flex-start" }}
          >
            {ukladaOoo ? "Ukládám…" : "Uložit oznámení a přeposílání"}
          </button>

          {/* ---- pravidla ---- */}
          <section className="fm-card" style={{ padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <h3 style={{ margin: 0, fontSize: 14 }}>Pravidla pro třídění pošty</h3>
              <span className="crm-mezera" style={{ flex: 1 }} />
              <button className="fm-btn" onClick={() => setFormular({ ...PRAZDNE })}>
                + Nové pravidlo
              </button>
            </div>
            <p className="em-tise" style={{ marginTop: 0 }}>
              Vyhodnocují se shora dolů na nově příchozí poštu. Na starou poštu se
              zpětně nepoužijí.
            </p>

            {seznam.length === 0 && (
              <p className="em-tise">Zatím žádné pravidlo.</p>
            )}

            {seznam.map((p) => (
              <div
                key={p.id}
                style={{
                  borderTop: "1px solid var(--line)",
                  padding: "9px 0",
                  display: "flex",
                  gap: 8,
                  alignItems: "flex-start",
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {p.nazev}
                    {!p.aktivni && <span className="em-tise"> · vypnuté</span>}
                  </div>
                  <div className="em-tise">{p.popis}</div>
                  {p.pocet_pouziti > 0 && (
                    <div className="em-tise">Použito {p.pocet_pouziti}×</div>
                  )}
                </div>
                <button className="fm-btn" onClick={() => prepni(p)} aria-pressed={p.aktivni}>
                  {p.aktivni ? "Vypnout" : "Zapnout"}
                </button>
                <button
                  className="fm-btn"
                  onClick={() =>
                    setFormular({
                      ...p,
                      podminky: p.podminky.length ? p.podminky : PRAZDNE.podminky,
                      akce: p.akce.length ? p.akce : PRAZDNE.akce,
                    })
                  }
                >
                  Upravit
                </button>
                <button className="fm-btn" onClick={() => smaz(p)}>
                  Smazat
                </button>
              </div>
            ))}
          </section>

          {/* ---- formulář pravidla ---- */}
          {formular && (
            <section className="fm-card" style={{ padding: 14 }}>
              <h3 style={{ margin: "0 0 10px", fontSize: 14 }}>
                {formular.id ? "Úprava pravidla" : "Nové pravidlo"}
              </h3>

              <div className="em-pole">
                <label htmlFor="pr-nazev">Název *</label>
                <input
                  id="pr-nazev"
                  value={formular.nazev}
                  onChange={(e) => setFormular((f) => ({ ...f, nazev: e.target.value }))}
                  placeholder="Faktury do složky Účetnictví"
                />
              </div>

              <div style={{ marginTop: 12 }}>
                <label className="em-tise" style={{ fontWeight: 600 }}>Když</label>
                <select
                  className="em-hledat"
                  style={{ width: "auto", marginLeft: 8 }}
                  value={formular.spojka}
                  onChange={(e) => setFormular((f) => ({ ...f, spojka: e.target.value }))}
                >
                  <option value="a">platí všechny podmínky</option>
                  <option value="nebo">platí aspoň jedna</option>
                </select>
              </div>

              {formular.podminky.map((p, i) => (
                <div key={i} style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                  <select
                    className="em-hledat"
                    style={{ width: "auto" }}
                    value={p.pole}
                    onChange={(e) => upravPodminku(i, { pole: e.target.value })}
                  >
                    {POLE.map((x) => (
                      <option key={x.klic} value={x.klic}>{x.nazev}</option>
                    ))}
                  </select>
                  {p.pole === "ma_prilohy" ? (
                    <select
                      className="em-hledat"
                      style={{ width: "auto" }}
                      value={p.operator}
                      onChange={(e) => upravPodminku(i, { operator: e.target.value })}
                    >
                      <option value="ano">ano</option>
                      <option value="ne">ne</option>
                    </select>
                  ) : (
                    <>
                      <select
                        className="em-hledat"
                        style={{ width: "auto" }}
                        value={p.operator}
                        onChange={(e) => upravPodminku(i, { operator: e.target.value })}
                      >
                        {OPERATORY.map((x) => (
                          <option key={x.klic} value={x.klic}>{x.nazev}</option>
                        ))}
                      </select>
                      <input
                        className="em-hledat"
                        style={{ flex: 1, minWidth: 140 }}
                        value={p.hodnota}
                        onChange={(e) => upravPodminku(i, { hodnota: e.target.value })}
                        placeholder="např. faktura"
                      />
                    </>
                  )}
                  {formular.podminky.length > 1 && (
                    <button
                      className="fm-btn"
                      onClick={() =>
                        setFormular((f) => ({
                          ...f,
                          podminky: f.podminky.filter((_, j) => j !== i),
                        }))
                      }
                      aria-label="Odebrat podmínku"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              <button
                className="fm-btn"
                style={{ marginTop: 6 }}
                onClick={() =>
                  setFormular((f) => ({
                    ...f,
                    podminky: [...f.podminky, { pole: "od", operator: "obsahuje", hodnota: "" }],
                  }))
                }
              >
                + Podmínka
              </button>

              <div style={{ marginTop: 14 }}>
                <label className="em-tise" style={{ fontWeight: 600 }}>Pak</label>
              </div>
              {formular.akce.map((a, i) => (
                <div key={i} style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                  <select
                    className="em-hledat"
                    style={{ width: "auto" }}
                    value={a.typ}
                    onChange={(e) => upravAkci(i, { typ: e.target.value })}
                  >
                    {TYPY_AKCI.map((x) => (
                      <option key={x.klic} value={x.klic}>{x.nazev}</option>
                    ))}
                  </select>
                  {a.typ === "presun" && (
                    <select
                      className="em-hledat"
                      style={{ flex: 1, minWidth: 140 }}
                      value={a.slozka_id || ""}
                      onChange={(e) => upravAkci(i, { slozka_id: Number(e.target.value) || null })}
                    >
                      <option value="">— vyber složku —</option>
                      {slozky.map((s) => (
                        <option key={s.id} value={s.id}>{s.nazev}</option>
                      ))}
                    </select>
                  )}
                  {a.typ === "preposlat" && (
                    <input
                      className="em-hledat"
                      style={{ flex: 1, minWidth: 140 }}
                      type="email"
                      value={a.komu || ""}
                      onChange={(e) => upravAkci(i, { komu: e.target.value })}
                      placeholder="kolega@greensie.cz"
                    />
                  )}
                  {formular.akce.length > 1 && (
                    <button
                      className="fm-btn"
                      onClick={() =>
                        setFormular((f) => ({ ...f, akce: f.akce.filter((_, j) => j !== i) }))
                      }
                      aria-label="Odebrat akci"
                    >
                      ×
                    </button>
                  )}
                </div>
              ))}
              <button
                className="fm-btn"
                style={{ marginTop: 6 }}
                onClick={() =>
                  setFormular((f) => ({
                    ...f,
                    akce: [...f.akce, { typ: "oznacit_precteno", slozka_id: null, komu: "" }],
                  }))
                }
              >
                + Akce
              </button>

              <label
                className="em-tise"
                style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 12 }}
              >
                <input
                  type="checkbox"
                  checked={formular.zastavit_dalsi}
                  onChange={(e) =>
                    setFormular((f) => ({ ...f, zastavit_dalsi: e.target.checked }))
                  }
                />
                Když tohle pravidlo zabere, další už nezkoušet
              </label>

              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="fm-btn" onClick={() => setFormular(null)}>
                  Zrušit
                </button>
                <button
                  className="fm-btn fm-primary"
                  onClick={ulozPravidlo}
                  disabled={!formular.nazev.trim()}
                >
                  Uložit pravidlo
                </button>
              </div>
            </section>
          )}
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
