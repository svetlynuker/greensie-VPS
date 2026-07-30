import { useEffect, useState } from "react";
import {
  crmFiltrSmaz,
  crmFiltrUloz,
  crmFiltrUprav,
  crmFiltry,
} from "../api";
import { OPERATORY, moznostiSloupce, popisPodminky, vychoziRazeni } from "../crmFiltry";

/**
 * Lišta uložených filtrů + editor víceúrovňového filtru.
 *
 * Filtr = několik podmínek (vyhodnocují se jako AND) a víceúrovňové řazení.
 * Platí současně pro tabulku i kanban dané sekce, protože obojí filtruje nad
 * stejnými řádky — jinak by uživatel viděl v každém zobrazení něco jiného.
 *
 * Cizí filtr, který někdo nasdílel, se dá použít, ale ne přepsat; kdo si ho
 * chce upravit, uloží si vlastní kopii („Uložit jako nový").
 */
export default function FiltrPanel({
  entita,
  sloupce,
  vsechnyRadky,
  podminky,
  razeni,
  onPodminky,
  onRazeni,
  onVychoziNacten,
}) {
  const [filtry, setFiltry] = useState([]);
  const [aktivni, setAktivni] = useState(null); // id použitého uloženého filtru
  const [editor, setEditor] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    let zrušeno = false;
    crmFiltry(entita)
      .then((f) => {
        if (zrušeno) return;
        setFiltry(f);
        // Výchozí filtr se použije sám – proto si ho člověk nastavuje.
        const vych = f.find((x) => x.vychozi);
        if (vych) {
          setAktivni(vych.id);
          onVychoziNacten?.(vych);
        }
      })
      .catch(() => setFiltry([]));
    return () => {
      zrušeno = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entita]);

  function pouzij(f) {
    setAktivni(f.id);
    onPodminky(f.podminky || []);
    onRazeni((f.razeni || []).length ? f.razeni : vychoziRazeni(entita));
  }

  function zrus() {
    setAktivni(null);
    onPodminky([]);
    onRazeni(vychoziRazeni(entita));
  }

  async function nacti() {
    setFiltry(await crmFiltry(entita));
  }

  const pocetPodminek = (podminky || []).length;

  return (
    <div className="crm-filtr-lista">
      <span className="crm-label" style={{ margin: 0 }}>
        Filtry
      </span>

      {filtry.map((f) => (
        <button
          key={f.id}
          className={`crm-pilulka ${aktivni === f.id ? "aktivni" : ""}`}
          onClick={() => (aktivni === f.id ? zrus() : pouzij(f))}
          title={
            (f.podminky || []).map((p) => popisPodminky(p, sloupce)).join(" · ") ||
            "bez podmínek"
          }
        >
          {f.nazev}
          {f.sdileny && !f.muj && <span className="crm-tise"> · {f.vlastnik_jmeno}</span>}
          {f.vychozi && " ★"}
        </button>
      ))}

      <button className="fm-btn crm-btn-maly" onClick={() => setEditor(true)}>
        {pocetPodminek > 0 ? `✎ Upravit filtr (${pocetPodminek})` : "+ Vlastní filtr"}
      </button>

      {pocetPodminek > 0 && (
        <button className="fm-btn crm-btn-maly" onClick={zrus} title="Zrušit filtr i řazení">
          ✕ Zrušit
        </button>
      )}

      {chyba && <span className="crm-ares-varovani">{chyba}</span>}

      {editor && (
        <FiltrEditor
          entita={entita}
          sloupce={sloupce}
          vsechnyRadky={vsechnyRadky}
          podminky={podminky}
          razeni={razeni}
          ulozeny={filtry.find((f) => f.id === aktivni) || null}
          onZavri={() => setEditor(false)}
          onPouzij={(p, r) => {
            onPodminky(p);
            onRazeni(r);
          }}
          onUlozeno={async (novy) => {
            await nacti();
            if (novy) setAktivni(novy.id);
          }}
          onSmazano={async () => {
            await nacti();
            zrus();
          }}
          onChyba={setChyba}
        />
      )}
    </div>
  );
}

/** Okno pro sestavení filtru: podmínky + víceúrovňové řazení + uložení. */
function FiltrEditor({
  entita,
  sloupce,
  vsechnyRadky,
  podminky,
  razeni,
  ulozeny,
  onZavri,
  onPouzij,
  onUlozeno,
  onSmazano,
  onChyba,
}) {
  const [p, setP] = useState(() =>
    (podminky || []).map((x) => ({ ...x, zdroj: undefined }))
  );
  const [r, setR] = useState(() => [...(razeni || [])]);
  const [nazev, setNazev] = useState(ulozeny?.nazev || "");
  const [sdileny, setSdileny] = useState(Boolean(ulozeny?.sdileny));
  const [vychozi, setVychozi] = useState(Boolean(ulozeny?.vychozi));
  const [pracuje, setPracuje] = useState(false);
  const [chyba, setChyba] = useState(null);

  const prvniSloupec = sloupce[0]?.klic || "";

  function pridejPodminku() {
    const typ = sloupce[0]?.typ || "text";
    setP([...p, { pole: prvniSloupec, operator: (OPERATORY[typ] || OPERATORY.text)[0].klic, hodnota: "" }]);
  }

  function zmenPodminku(i, zmena) {
    setP(p.map((x, j) => (j === i ? { ...x, ...zmena } : x)));
  }

  function pridejRazeni() {
    setR([...r, { pole: prvniSloupec, smer: "asc" }]);
  }

  async function uloz(jakoNovy) {
    if (!nazev.trim()) {
      setChyba("Filtr potřebuje název.");
      return;
    }
    setPracuje(true);
    setChyba(null);
    try {
      const telo = {
        nazev: nazev.trim(),
        podminky: p.filter((x) => x.pole && x.operator),
        razeni: r.filter((x) => x.pole),
        sdileny,
        vychozi,
      };
      const vysledek =
        ulozeny && !jakoNovy && ulozeny.muj
          ? await crmFiltrUprav(ulozeny.id, telo)
          : await crmFiltrUloz(entita, telo);
      await onUlozeno?.(vysledek);
      onPouzij(telo.podminky, telo.razeni);
      onZavri();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  async function smaz() {
    if (!window.confirm(`Smazat filtr „${ulozeny.nazev}"?`)) return;
    try {
      await crmFiltrSmaz(ulozeny.id);
      await onSmazano?.();
      onZavri();
    } catch (e) {
      onChyba?.(e.message);
      onZavri();
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Vlastní filtr</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Podmínky se sčítají — musí platit <b>všechny</b>. Filtr platí zároveň pro tabulku
            i kanban. Řazení je víceúrovňové: první klíč je hlavní, další rozhodují při shodě.
          </p>

          <h3>Podmínky</h3>
          {p.length === 0 && <p className="crm-tise">Žádná podmínka — zobrazí se všechno.</p>}
          {p.map((x, i) => {
            const def = sloupce.find((s) => s.klic === x.pole) || sloupce[0];
            const operatory = OPERATORY[def?.typ || "text"] || OPERATORY.text;
            const op = operatory.find((o) => o.klic === x.operator) || operatory[0];
            const moznosti =
              def?.typ === "vyber" || def?.typ === "seznam"
                ? moznostiSloupce(vsechnyRadky, def.klic)
                : [];
            return (
              <div className="crm-podminka" key={i}>
                <select
                  className="crm-pole crm-pole-uzke"
                  value={x.pole}
                  onChange={(e) => {
                    const novyDef = sloupce.find((s) => s.klic === e.target.value);
                    const noveOp = OPERATORY[novyDef?.typ || "text"] || OPERATORY.text;
                    zmenPodminku(i, {
                      pole: e.target.value,
                      operator: noveOp[0].klic,
                      hodnota: "",
                    });
                  }}
                >
                  {sloupce.map((s) => (
                    <option key={s.klic} value={s.klic}>
                      {s.nazev}
                    </option>
                  ))}
                </select>

                <select
                  className="crm-pole crm-pole-uzke"
                  value={x.operator}
                  onChange={(e) => zmenPodminku(i, { operator: e.target.value, hodnota: "" })}
                >
                  {operatory.map((o) => (
                    <option key={o.klic} value={o.klic}>
                      {o.nazev}
                    </option>
                  ))}
                </select>

                {!op.bezHodnoty &&
                  (op.dvojice ? (
                    <div className="crm-filtr-rozsah">
                      <input
                        className="crm-pole crm-pole-cislo"
                        type={def?.typ === "datum" ? "date" : "number"}
                        value={(Array.isArray(x.hodnota) ? x.hodnota[0] : "") || ""}
                        onChange={(e) =>
                          zmenPodminku(i, {
                            hodnota: [e.target.value, Array.isArray(x.hodnota) ? x.hodnota[1] : ""],
                          })
                        }
                      />
                      <input
                        className="crm-pole crm-pole-cislo"
                        type={def?.typ === "datum" ? "date" : "number"}
                        value={(Array.isArray(x.hodnota) ? x.hodnota[1] : "") || ""}
                        onChange={(e) =>
                          zmenPodminku(i, {
                            hodnota: [Array.isArray(x.hodnota) ? x.hodnota[0] : "", e.target.value],
                          })
                        }
                      />
                    </div>
                  ) : moznosti.length > 0 ? (
                    <select
                      className="crm-pole crm-pole-uzke"
                      value={x.hodnota ?? ""}
                      onChange={(e) => zmenPodminku(i, { hodnota: e.target.value })}
                    >
                      <option value="">—</option>
                      {moznosti.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                  ) : def?.typ === "ano_ne" ? (
                    <select
                      className="crm-pole crm-pole-uzke"
                      value={x.hodnota === true ? "ano" : "ne"}
                      onChange={(e) => zmenPodminku(i, { hodnota: e.target.value === "ano" })}
                    >
                      <option value="ano">ano</option>
                      <option value="ne">ne</option>
                    </select>
                  ) : (
                    <input
                      className="crm-pole crm-pole-uzke"
                      type={def?.typ === "datum" ? "date" : "text"}
                      value={x.hodnota ?? ""}
                      onChange={(e) => zmenPodminku(i, { hodnota: e.target.value })}
                    />
                  ))}

                <button
                  className="fm-btn crm-btn-maly crm-btn-smazat"
                  onClick={() => setP(p.filter((_, j) => j !== i))}
                  title="Odebrat podmínku"
                >
                  ✕
                </button>
              </div>
            );
          })}
          <button className="fm-btn crm-btn-maly" onClick={pridejPodminku}>
            + Podmínka
          </button>

          <h3 style={{ marginTop: 18 }}>Řazení</h3>
          {r.map((x, i) => (
            <div className="crm-podminka" key={i}>
              <span className="crm-tise" style={{ minWidth: 18 }}>
                {i + 1}.
              </span>
              <select
                className="crm-pole crm-pole-uzke"
                value={x.pole}
                onChange={(e) => setR(r.map((y, j) => (j === i ? { ...y, pole: e.target.value } : y)))}
              >
                {sloupce.map((s) => (
                  <option key={s.klic} value={s.klic}>
                    {s.nazev}
                  </option>
                ))}
              </select>
              <select
                className="crm-pole crm-pole-uzke"
                value={x.smer}
                onChange={(e) => setR(r.map((y, j) => (j === i ? { ...y, smer: e.target.value } : y)))}
              >
                <option value="asc">vzestupně</option>
                <option value="desc">sestupně</option>
              </select>
              <button
                className="fm-btn crm-btn-maly crm-btn-smazat"
                onClick={() => setR(r.filter((_, j) => j !== i))}
              >
                ✕
              </button>
            </div>
          ))}
          <button className="fm-btn crm-btn-maly" onClick={pridejRazeni}>
            + Úroveň řazení
          </button>

          <div className="crm-oddelovac" style={{ marginTop: 18, paddingTop: 14 }}>
            <h3>Uložení</h3>
            <div className="crm-mrizka">
              <div className="crm-sirka2">
                <label className="crm-label">Název filtru</label>
                <input
                  className="crm-pole"
                  value={nazev}
                  onChange={(e) => setNazev(e.target.value)}
                  placeholder="např. Moje otevřené PPA nad milion"
                />
              </div>
              <div>
                <label className="crm-zaskrtavaci">
                  <input
                    type="checkbox"
                    checked={sdileny}
                    onChange={(e) => setSdileny(e.target.checked)}
                  />
                  Nasdílet ostatním
                </label>
                <label className="crm-zaskrtavaci">
                  <input
                    type="checkbox"
                    checked={vychozi}
                    onChange={(e) => setVychozi(e.target.checked)}
                  />
                  Použít po otevření sekce
                </label>
              </div>
            </div>
          </div>

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          {ulozeny?.muj && (
            <button className="fm-btn crm-btn-smazat" onClick={smaz}>
              Smazat filtr
            </button>
          )}
          <span className="crm-mezera" />
          <button
            className="fm-btn"
            onClick={() => {
              onPouzij(
                p.filter((x) => x.pole && x.operator),
                r.filter((x) => x.pole)
              );
              onZavri();
            }}
          >
            Jen použít
          </button>
          {ulozeny?.muj && (
            <button className="fm-btn" onClick={() => uloz(true)} disabled={pracuje}>
              Uložit jako nový
            </button>
          )}
          <button className="fm-btn fm-primary" onClick={() => uloz(false)} disabled={pracuje}>
            {pracuje ? "Ukládám…" : ulozeny?.muj ? "Uložit změny" : "Uložit filtr"}
          </button>
        </div>
      </div>
    </div>
  );
}
