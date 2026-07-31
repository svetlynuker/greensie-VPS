import { useEffect, useState } from "react";
import {
  crmKategorie,
  crmKategorieAktivit,
  crmKategorieAktivityPridej,
  crmKategorieAktivitySmaz,
  crmKategorieAktivityUprav,
  crmNastaveni,
  crmNastaveniUloz,
  crmKategoriePoradi,
  crmKategoriePridej,
  crmKategorieSmaz,
  crmKategorieUprav,
  crmNavrhStartu,
  crmRaduUprav,
  crmRady,
  crmStavPridej,
  crmStavSmaz,
  crmStavUprav,
  crmStavy,
  crmStavyPole,
  crmStavyPoradi,
} from "../api";

// Do kterého výpočtu nabídkovače kategorie míří. Prázdno je platná volba:
// „Servis" je pořád obchodní případ, ale nabídkovač pro něj nic neumí.
// Klíče se drží TYPY_NABIDKY na backendu (bez „kombinace" – ta nevzniká
// volbou u případu, ale spojením dvou hotových nabídek).
const VYPOCTY = [
  { klic: "", nazev: "bez výpočtu" },
  { klic: "ppa", nazev: "PPA" },
  { klic: "prodej", nazev: "Prodej" },
  { klic: "peak_shaving", nazev: "Peak shaving" },
];

const DRUHY = [
  { klic: "otevreny", nazev: "Otevřený (počítá se do pipeline)" },
  { klic: "vyhra", nazev: "Výhra (uzavírá případ)" },
  { klic: "prohra", nazev: "Prohra (vyžádá důvod)" },
];

const BARVY = [
  { klic: "info", nazev: "Neutrální" },
  { klic: "warn", nazev: "Rozpracované" },
  { klic: "ok", nazev: "Dobré" },
  { klic: "crit", nazev: "Špatné" },
];

/**
 * Nastavení stavů pipeline (sloupců kanbanu) a číselných řad.
 *
 * Sloupce kanbanu jsou data, ne kód – proto je tady může vedení přidat,
 * přejmenovat, přebarvit a přeskládat, aniž by to musel dělat programátor.
 *
 * Číselné řady jsou ve stejném okně schválně: obojí je „jak se to tady
 * počítá a jak se to jmenuje" a obojí smí měnit jen právo `crm_nastaveni`.
 */
export default function StavyNastaveni({ entita, onZavri, onZmena }) {
  const [stavy, setStavy] = useState(null);
  const [rady, setRady] = useState([]);
  const [novy, setNovy] = useState({ nazev: "", druh: "otevreny", barva: "info" });
  const [navrh, setNavrh] = useState(null);
  const [kategorie, setKategorie] = useState(null);
  const [novaKat, setNovaKat] = useState({ nazev: "", typ_nabidky: "" });
  // Barevné štítky aktivit pro kalendář + firemní adresa pro „U nás".
  const [stitky, setStitky] = useState(null);
  const [novyStitek, setNovyStitek] = useState({ nazev: "", barva: "#b9e6c9" });
  const [naseAdresa, setNaseAdresa] = useState("");
  // CRM-30: která pole lze označit jako povinná, a u kterého stavu je právě
  // rozbalené nastavení.
  const [pole, setPole] = useState([]);
  const [rozbaleny, setRozbaleny] = useState(null);
  const [chyba, setChyba] = useState(null);

  // Kategorie se spravují jen u obchodního případu – u nabídky, objednávky
  // ani projektu nemají význam (kategorie je vlastnost zakázky, ne dokumentu).
  const jeOp = entita === "op";

  async function nacti() {
    const [s, r] = await Promise.all([crmStavy(entita), crmRady()]);
    setStavy(s);
    setRady(r);
    if (jeOp) {
      setKategorie(await crmKategorie().catch(() => []));
      setStitky(await crmKategorieAktivit().catch(() => []));
    }
  }

  useEffect(() => {
    Promise.all([
      crmStavy(entita),
      crmRady(),
      crmNavrhStartu(entita).catch(() => null),
      entita === "op" ? crmKategorie().catch(() => []) : Promise.resolve(null),
      entita === "op" ? crmKategorieAktivit().catch(() => []) : Promise.resolve(null),
      entita === "op" ? crmNastaveni().catch(() => null) : Promise.resolve(null),
      crmStavyPole().catch(() => []),
    ])
      .then(([s, r, n, k, st, nast, pol]) => {
        setStavy(s);
        setRady(r);
        setNavrh(n);
        setKategorie(k);
        setStitky(st);
        setNaseAdresa(nast?.nase_adresa || "");
        setPole(pol || []);
      })
      .catch((e) => setChyba(e.message));
  }, [entita]);

  function hlas(e) {
    setChyba(e.message);
  }

  async function pridej() {
    if (!novy.nazev.trim()) return;
    try {
      await crmStavPridej(entita, novy);
      setNovy({ nazev: "", druh: "otevreny", barva: "info" });
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function uprav(s, zmeny) {
    try {
      await crmStavUprav(s.id, {
        nazev: zmeny.nazev ?? s.nazev,
        barva: zmeny.barva ?? s.barva,
        druh: zmeny.druh ?? s.druh,
        povinna_pole: zmeny.povinna_pole ?? s.povinna_pole ?? [],
      });
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function posun(index, o) {
    const novePoradi = [...stavy];
    const cil = index + o;
    if (cil < 0 || cil >= novePoradi.length) return;
    [novePoradi[index], novePoradi[cil]] = [novePoradi[cil], novePoradi[index]];
    try {
      await crmStavyPoradi(
        entita,
        novePoradi.map((s) => s.id)
      );
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function smaz(s) {
    if (!window.confirm(`Smazat stav „${s.nazev}"?`)) return;
    try {
      await crmStavSmaz(s.id);
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function ulozRadu(rada, zmeny) {
    try {
      await crmRaduUprav(rada.entita, zmeny);
      await nacti();
    } catch (e) {
      hlas(e);
    }
  }

  // ---- barevné štítky aktivit (kalendář) ----
  async function pridejStitek() {
    if (!novyStitek.nazev.trim()) return;
    try {
      await crmKategorieAktivityPridej({
        nazev: novyStitek.nazev.trim(),
        barva: novyStitek.barva,
      });
      setNovyStitek({ nazev: "", barva: "#b9e6c9" });
      await nacti();
    } catch (e) {
      hlas(e);
    }
  }

  async function upravStitek(k, zmeny) {
    try {
      await crmKategorieAktivityUprav(k.id, {
        nazev: zmeny.nazev ?? k.nazev,
        barva: zmeny.barva ?? k.barva,
        aktivni: zmeny.aktivni ?? k.aktivni,
      });
      await nacti();
    } catch (e) {
      hlas(e);
    }
  }

  async function smazStitek(k) {
    if (!window.confirm(`Smazat kategorii „${k.nazev}"? Aktivity zůstanou, jen bez štítku.`)) {
      return;
    }
    try {
      const out = await crmKategorieAktivitySmaz(k.id);
      await nacti();
      if (out?.aktivit_bez_kategorie) {
        setChyba(
          `Kategorie smazána. ${out.aktivit_bez_kategorie} aktivit zůstalo bez štítku.`
        );
      }
    } catch (e) {
      hlas(e);
    }
  }

  async function ulozAdresu(hodnota) {
    try {
      await crmNastaveniUloz({ nase_adresa: hodnota });
      setNaseAdresa(hodnota);
    } catch (e) {
      hlas(e);
    }
  }

  // ---- kategorie případu ----
  async function pridejKategorii() {
    if (!novaKat.nazev.trim()) return;
    try {
      await crmKategoriePridej({ nazev: novaKat.nazev.trim(), typ_nabidky: novaKat.typ_nabidky });
      setNovaKat({ nazev: "", typ_nabidky: "" });
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function upravKategorii(k, zmeny) {
    try {
      await crmKategorieUprav(k.id, {
        nazev: zmeny.nazev ?? k.nazev,
        popis: zmeny.popis ?? k.popis,
        typ_nabidky: zmeny.typ_nabidky ?? k.typ_nabidky,
        aktivni: zmeny.aktivni ?? k.aktivni,
      });
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function posunKategorii(index, o) {
    const nove = [...kategorie];
    const cil = index + o;
    if (cil < 0 || cil >= nove.length) return;
    [nove[index], nove[cil]] = [nove[cil], nove[index]];
    try {
      await crmKategoriePoradi(nove.map((k) => k.id));
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e);
    }
  }

  async function smazKategorii(k) {
    if (!window.confirm(`Smazat kategorii „${k.nazev}"?`)) return;
    try {
      await crmKategorieSmaz(k.id);
      await nacti();
      onZmena?.();
    } catch (e) {
      hlas(e); // backend odmítne kategorii, kterou případy používají
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeOp ? "Nastavení pipeline, kategorií a číslování" : "Nastavení pipeline a číslování"}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <h3>Stavy (sloupce kanbanu)</h3>
          <p className="crm-tise">
            Pořadí určuje pořadí sloupců. Stav, ve kterém něco je, nelze smazat – nejdřív
            záznamy přesuň.
          </p>

          {stavy === null ? null : (
            <ul className="crm-stavy">
              {stavy.map((s, i) => (
                <li key={s.id}>
                  <input
                    className="crm-pole"
                    defaultValue={s.nazev}
                    onBlur={(e) => {
                      if (e.target.value.trim() && e.target.value !== s.nazev) {
                        uprav(s, { nazev: e.target.value.trim() });
                      }
                    }}
                  />
                  <select
                    className="crm-pole crm-pole-uzke"
                    value={s.druh}
                    onChange={(e) => uprav(s, { druh: e.target.value })}
                  >
                    {DRUHY.map((d) => (
                      <option key={d.klic} value={d.klic}>
                        {d.nazev}
                      </option>
                    ))}
                  </select>
                  <select
                    className="crm-pole crm-pole-uzke"
                    value={s.barva || "info"}
                    onChange={(e) => uprav(s, { barva: e.target.value })}
                  >
                    {BARVY.map((b) => (
                      <option key={b.klic} value={b.klic}>
                        {b.nazev}
                      </option>
                    ))}
                  </select>
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => posun(i, -1)}
                    disabled={i === 0}
                    title="Posunout vlevo"
                  >
                    ↑
                  </button>
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => posun(i, 1)}
                    disabled={i === stavy.length - 1}
                    title="Posunout vpravo"
                  >
                    ↓
                  </button>
                  <button
                    className={`fm-btn crm-btn-maly ${
                      (s.povinna_pole || []).length ? "fm-primary" : ""
                    }`}
                    onClick={() => setRozbaleny(rozbaleny === s.id ? null : s.id)}
                    title="Pole povinná pro přechod do tohoto stavu"
                  >
                    Povinné
                    {(s.povinna_pole || []).length ? ` (${s.povinna_pole.length})` : ""}
                  </button>
                  <button
                    className="fm-btn crm-btn-maly crm-btn-smazat"
                    onClick={() => smaz(s)}
                    title="Smazat stav"
                  >
                    ✕
                  </button>
                  {rozbaleny === s.id && (
                    <div className="crm-povinna">
                      <p className="crm-tise" style={{ margin: "0 0 6px" }}>
                        Bez těchto polí se případ do stavu <b>{s.nazev}</b> nedostane.
                        Kontroluje se až přechod, ne uložení — případ se zakládá
                        rozpracovaný.
                      </p>
                      <div className="crm-povinna-mrizka">
                        {pole.map((f) => {
                          const zapnuto = (s.povinna_pole || []).includes(f.klic);
                          return (
                            <label key={f.klic} className="crm-zaskrtavaci">
                              <input
                                type="checkbox"
                                checked={zapnuto}
                                onChange={() => {
                                  const set = new Set(s.povinna_pole || []);
                                  if (zapnuto) set.delete(f.klic);
                                  else set.add(f.klic);
                                  uprav(s, { povinna_pole: [...set] });
                                }}
                              />
                              {f.nazev}
                              {f.vlastni && <span className="crm-tise"> · vlastní pole</span>}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}

          <div className="crm-stav-novy">
            <input
              className="crm-pole"
              value={novy.nazev}
              onChange={(e) => setNovy((n) => ({ ...n, nazev: e.target.value }))}
              placeholder="Název nového stavu"
            />
            <select
              className="crm-pole crm-pole-uzke"
              value={novy.druh}
              onChange={(e) => setNovy((n) => ({ ...n, druh: e.target.value }))}
            >
              {DRUHY.map((d) => (
                <option key={d.klic} value={d.klic}>
                  {d.nazev}
                </option>
              ))}
            </select>
            <button className="fm-btn fm-primary" onClick={pridej} disabled={!novy.nazev.trim()}>
              Přidat stav
            </button>
          </div>

          {jeOp && (
            <>
              <h3 style={{ marginTop: 22 }}>Kategorie obchodního případu</h3>
              <p className="crm-tise">
                Čím zakázka je – a do kterého <b>výpočtu</b> míří nabídka. Kategorie
                {" "}<i>bez výpočtu</i> je platná (např. servis): na kartě případu se u ní
                tlačítko „+ nabídka" nenabídne. Kategorii, kterou už případy mají, nelze
                smazat – <b>vypni</b> ji, ať se nenabízí u nových.
              </p>

              {kategorie === null ? null : (
                <table className="crm-tabulka crm-tabulka-hustá">
                  <thead>
                    <tr>
                      <th>Název</th>
                      <th>Výpočet nabídky</th>
                      <th>Nabízet</th>
                      <th className="crm-vpravo">Pořadí</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {kategorie.map((k, i) => (
                      <tr key={k.id}>
                        <td>
                          <input
                            className="crm-pole"
                            defaultValue={k.nazev}
                            onBlur={(e) => {
                              if (e.target.value.trim() && e.target.value !== k.nazev) {
                                upravKategorii(k, { nazev: e.target.value.trim() });
                              }
                            }}
                          />
                          <div className="crm-tise" style={{ marginTop: 2 }}>
                            <code>{k.klic}</code>
                          </div>
                        </td>
                        <td>
                          <select
                            className="crm-pole crm-pole-uzke"
                            value={k.typ_nabidky || ""}
                            onChange={(e) => upravKategorii(k, { typ_nabidky: e.target.value })}
                          >
                            {VYPOCTY.map((v) => (
                              <option key={v.klic} value={v.klic}>
                                {v.nazev}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <label className="crm-tise" style={{ display: "flex", gap: 6 }}>
                            <input
                              type="checkbox"
                              checked={k.aktivni}
                              onChange={(e) => upravKategorii(k, { aktivni: e.target.checked })}
                            />
                            {k.aktivni ? "ano" : "ne"}
                          </label>
                        </td>
                        <td className="crm-vpravo">
                          <button
                            className="fm-btn crm-btn-maly"
                            onClick={() => posunKategorii(i, -1)}
                            disabled={i === 0}
                            title="Nahoru"
                          >
                            ↑
                          </button>
                          <button
                            className="fm-btn crm-btn-maly"
                            onClick={() => posunKategorii(i, 1)}
                            disabled={i === kategorie.length - 1}
                            title="Dolů"
                          >
                            ↓
                          </button>
                        </td>
                        <td>
                          <button
                            className="fm-btn crm-btn-maly crm-btn-smazat"
                            onClick={() => smazKategorii(k)}
                            title="Smazat kategorii"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div className="crm-stav-novy">
                <input
                  className="crm-pole"
                  value={novaKat.nazev}
                  onChange={(e) => setNovaKat((n) => ({ ...n, nazev: e.target.value }))}
                  placeholder="Název nové kategorie (např. Servis)"
                />
                <select
                  className="crm-pole crm-pole-uzke"
                  value={novaKat.typ_nabidky}
                  onChange={(e) => setNovaKat((n) => ({ ...n, typ_nabidky: e.target.value }))}
                >
                  {VYPOCTY.map((v) => (
                    <option key={v.klic} value={v.klic}>
                      {v.nazev}
                    </option>
                  ))}
                </select>
                <button
                  className="fm-btn fm-primary"
                  onClick={pridejKategorii}
                  disabled={!novaKat.nazev.trim()}
                >
                  Přidat kategorii
                </button>
              </div>
            </>
          )}

          {jeOp && (
            <>
              <h3 style={{ marginTop: 22 }}>Kategorie aktivit (barvy v kalendáři)</h3>
              <p className="crm-tise">
                Barevné škatulky, kterými se v kalendáři třídí schůzky a úkoly — a podle
                kterých se dá filtrovat. <b>Není to totéž jako kategorie případu výš:</b> ta
                říká, do kterého výpočtu míří nabídka. Smazání štítku aktivity nesmaže, jen
                jim štítek odebere.
              </p>

              {stitky === null ? null : (
                <table className="crm-tabulka crm-tabulka-hustá">
                  <thead>
                    <tr>
                      <th>Název</th>
                      <th>Barva</th>
                      <th>Nabízet</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {stitky.map((k) => (
                      <tr key={k.id}>
                        <td>
                          <input
                            className="crm-pole"
                            defaultValue={k.nazev}
                            onBlur={(e) => {
                              if (e.target.value.trim() && e.target.value !== k.nazev) {
                                upravStitek(k, { nazev: e.target.value.trim() });
                              }
                            }}
                          />
                        </td>
                        <td>
                          <input
                            type="color"
                            className="crm-barva-pole"
                            value={k.barva}
                            onChange={(e) => upravStitek(k, { barva: e.target.value })}
                            aria-label={`Barva pro ${k.nazev}`}
                          />
                        </td>
                        <td>
                          <label className="crm-tise" style={{ display: "flex", gap: 6 }}>
                            <input
                              type="checkbox"
                              checked={k.aktivni}
                              onChange={(e) => upravStitek(k, { aktivni: e.target.checked })}
                            />
                            {k.aktivni ? "ano" : "ne"}
                          </label>
                        </td>
                        <td>
                          <button
                            className="fm-btn crm-btn-maly crm-btn-smazat"
                            onClick={() => smazStitek(k)}
                            title="Smazat kategorii"
                          >
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              <div className="crm-stav-novy">
                <input
                  className="crm-pole"
                  value={novyStitek.nazev}
                  onChange={(e) => setNovyStitek((n) => ({ ...n, nazev: e.target.value }))}
                  placeholder="Název nové kategorie (např. Reklamace)"
                />
                <input
                  type="color"
                  className="crm-barva-pole"
                  value={novyStitek.barva}
                  onChange={(e) => setNovyStitek((n) => ({ ...n, barva: e.target.value }))}
                  aria-label="Barva nové kategorie"
                />
                <button
                  className="fm-btn fm-primary"
                  onClick={pridejStitek}
                  disabled={!novyStitek.nazev.trim()}
                >
                  Přidat kategorii
                </button>
              </div>

              <h3 style={{ marginTop: 22 }}>Naše adresa</h3>
              <p className="crm-tise">
                Vyplní se tlačítkem <b>U nás</b> u místa konání, když se schůzka koná
                u nás. Prázdné = tlačítko se nenabízí.
              </p>
              <input
                className="crm-pole"
                defaultValue={naseAdresa}
                placeholder="např. Bedřichovská 2183/16, Praha 8, 182 00"
                onBlur={(e) => {
                  if (e.target.value.trim() !== naseAdresa) ulozAdresu(e.target.value.trim());
                }}
              />
            </>
          )}

          <h3 style={{ marginTop: 22 }}>Číselné řady</h3>
          <p className="crm-tise">
            Viditelná ID záznamů. Řada se každý rok restartuje. Dokud běží Raynet, drž
            {" "}<b>další číslo nad jeho nejvyšším</b> – jinak by dvě různé zakázky nesly stejné
            číslo.
            {navrh?.navrh ? ` Doporučení podle Raynetu: začít od ${navrh.navrh}.` : ""}
          </p>

          <table className="crm-tabulka crm-tabulka-hustá">
            <thead>
              <tr>
                <th>Entita</th>
                <th>Příští číslo</th>
                <th>Šířka</th>
                <th>Další číslo</th>
                <th className="crm-vpravo">Vydáno letos</th>
              </tr>
            </thead>
            <tbody>
              {rady.map((r) => (
                <tr key={r.entita}>
                  <td className="crm-silne">{r.prefix}</td>
                  <td>
                    <code>{r.ukazka}</code>
                  </td>
                  <td>
                    <input
                      className="crm-pole crm-pole-cislo"
                      type="number"
                      min={1}
                      max={8}
                      defaultValue={r.sirka}
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (v && v !== r.sirka) ulozRadu(r, { sirka: v });
                      }}
                    />
                  </td>
                  <td>
                    <input
                      className="crm-pole crm-pole-cislo"
                      type="number"
                      min={1}
                      defaultValue={r.dalsi_cislo}
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (v && v !== r.dalsi_cislo) ulozRadu(r, { dalsi_cislo: v });
                      }}
                    />
                  </td>
                  <td className="crm-vpravo">{r.pouzito}</td>
                </tr>
              ))}
            </tbody>
          </table>

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
