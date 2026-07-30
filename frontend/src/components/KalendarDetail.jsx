import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Ikona from "./Ikona";
import { barvaDruhu, barvaTextuNa } from "../barvyAktivit";
import { DRUHY_AKTIVITY, fmtDatum } from "../crm";
import { hm } from "../kalendarCas";

/**
 * Detail aktivity jako popover ukotvený u dlaždice — podle předlohy
 * `detail události.png`.
 *
 * Proč popover a ne okno na středu: člověk klikl na konkrétní místo v týdnu
 * a potřebuje vidět kalendář kolem. Okno na středu překryje kontext a po
 * zavření se ztratí, kde vlastně byl.
 *
 * Karta se sama překlopí, aby se vešla do okna — jinak by u schůzky v pátek
 * odpoledne vylezla mimo obrazovku a nešla by přečíst.
 *
 * Akce v patičce (Mám hotovo / Zrušit / Přesunout) se rozbalí do řádku PŘÍMO
 * v kartě, ne do dalšího dialogu. Uzavření aktivity je věc dvou kliknutí
 * a hodnotné je na něm to, co se stalo — proto se výsledek ptá hned tady.
 */

const SIRKA = 340;
const MEZERA = 10;

export default function KalendarDetail({
  udalost,
  kotva, // DOMRect dlaždice, u které se má karta ukotvit
  barvy,
  lide = [],
  onZavri,
  onZmena, // (id, {stav, vysledek} | {termin, cas}) → ulož a obnov
  onUprav,
  onSmaz,
}) {
  const ref = useRef(null);
  const [pozice, setPozice] = useState({ top: 0, left: 0 });
  // Rozbalený řádek akce: "hotovo" | "zrusit" | "presunout" | "vic" | null
  const [akce, setAkce] = useState(null);
  const [vysledek, setVysledek] = useState(udalost?.vysledek || "");
  const [novyDen, setNovyDen] = useState((udalost?.termin || "").slice(0, 10));
  const [novyCas, setNovyCas] = useState(
    udalost?.zacatek ? hm(udalost.zacatek).padStart(5, "0") : "09:00"
  );
  const [pracuje, setPracuje] = useState(false);

  // useLayoutEffect, ne useEffect: pozici je nutné spočítat před vykreslením,
  // jinak karta bliknutím poskočí z levého horního kouta na místo.
  useLayoutEffect(() => {
    if (!kotva) return;
    const vyska = ref.current?.offsetHeight || 380;
    const doprava = kotva.right + MEZERA;
    const doleva = kotva.left - SIRKA - MEZERA;
    const left =
      doprava + SIRKA <= window.innerWidth
        ? doprava
        : doleva >= 0
          ? doleva
          : Math.max(MEZERA, window.innerWidth - SIRKA - MEZERA);
    const top = Math.min(
      Math.max(MEZERA, kotva.top - 8),
      Math.max(MEZERA, window.innerHeight - vyska - MEZERA)
    );
    setPozice({ top, left });
  }, [kotva, akce]);

  useEffect(() => {
    function klavesa(e) {
      if (e.key === "Escape") onZavri?.();
    }
    window.addEventListener("keydown", klavesa);
    return () => window.removeEventListener("keydown", klavesa);
  }, [onZavri]);

  if (!udalost) return null;

  const druh = DRUHY_AKTIVITY.find((d) => d.klic === udalost.druh);
  const barva = udalost.kategorie_barva || barvaDruhu(barvy, udalost.druh);
  const jmenaUcastniku = (udalost.ucastnici || [])
    .map((id) => lide.find((u) => u.id === id)?.jmeno || `#${id}`)
    .join(", ");

  const casovyPopis = udalost.cely_den
    ? `${fmtDatum(udalost.termin)} · celý den`
    : `${fmtDatum(udalost.termin)} ${hm(udalost.zacatek)} – ${hm(
        new Date(new Date(udalost.zacatek).getTime() + (udalost.delka_min || 30) * 60000)
      )}`;

  async function proved(zmena) {
    setPracuje(true);
    try {
      await onZmena?.(udalost.id, zmena);
      onZavri?.();
    } finally {
      setPracuje(false);
    }
  }

  return (
    <>
      {/* Průhledná plocha, která zavře kartu kliknutím kamkoli jinam. */}
      <div className="kd-zaves" onClick={onZavri} />
      <div
        className="kd"
        ref={ref}
        style={{ top: pozice.top, left: pozice.left, width: SIRKA }}
        role="dialog"
        aria-label={udalost.nazev || "Detail aktivity"}
      >
        <div className="kd-hlava">
          <span
            className="kd-ikona"
            style={{ background: barva, color: barvaTextuNa(barva) }}
            aria-hidden="true"
          >
            <Ikona jmeno={druh?.ikona || "kalendar"} velikost={16} />
          </span>
          <div className="kd-titulky">
            <h3>{udalost.nazev || "(bez názvu)"}</h3>
            {udalost.zaznam_nazev && (
              <span className="kd-stitek">
                <Ikona jmeno="zakaznici" velikost={12} />
                {udalost.cesta ? (
                  <a className="crm-odkaz" href={udalost.cesta}>
                    {udalost.zaznam_nazev}
                  </a>
                ) : (
                  udalost.zaznam_nazev
                )}
              </span>
            )}
          </div>
          {udalost.muze_detail && (
            <button className="kd-btn-ikona" onClick={() => onUprav?.(udalost)} title="Upravit">
              ✎
            </button>
          )}
          <button className="kd-btn-ikona" onClick={onZavri} title="Zavřít" aria-label="Zavřít">
            ✕
          </button>
        </div>

        {!udalost.muze_detail ? (
          <div className="kd-telo">
            <p className="crm-tise">
              {udalost.vlastnik_jmeno ? `${udalost.vlastnik_jmeno} — ` : ""}
              v tuhle dobu nemá volno. Podrobnosti téhle aktivity ti appka neukáže.
            </p>
            <div className="kd-radek">
              <Ikona jmeno="zmeny" velikost={14} />
              <span>{casovyPopis}</span>
            </div>
          </div>
        ) : (
          <>
            <div className="kd-telo">
              {udalost.kategorie_nazev && (
                <div className="kd-radek">
                  <span
                    className="kd-ctverecek"
                    style={{ background: udalost.kategorie_barva }}
                    aria-hidden="true"
                  />
                  <span>{udalost.kategorie_nazev}</span>
                </div>
              )}

              <div className="kd-radek">
                <Ikona jmeno="zmeny" velikost={14} />
                <span>
                  {casovyPopis}
                  {udalost.vicedenni ? ` → ${fmtDatum(udalost.konec)}` : ""}
                </span>
              </div>

              {udalost.misto && (
                <div className="kd-radek">
                  <Ikona jmeno="zakaznici" velikost={14} />
                  <span>{udalost.misto}</span>
                </div>
              )}

              <div className="kd-radek">
                <Ikona jmeno="zakaznici" velikost={14} />
                <span>
                  <b>{udalost.vlastnik_jmeno || "—"}</b>
                  {jmenaUcastniku && (
                    <>
                      {" → "}
                      <span className="kd-ucastnici">{jmenaUcastniku}</span>
                    </>
                  )}
                </span>
              </div>

              {udalost.stav !== "naplanovano" && (
                <div className="kd-radek">
                  <span className={`gs-pill ${udalost.stav === "realizovano" ? "good" : "crit"}`}>
                    <span className="gs-dot" />
                    {udalost.stav === "realizovano" ? "Realizováno" : "Nekonalo se"}
                  </span>
                </div>
              )}

              {udalost.text && <p className="kd-text">{udalost.text}</p>}
              {udalost.vysledek && (
                <div className="crm-osa-vysledek">
                  <b>{udalost.stav === "nekonalo_se" ? "Nekonalo se:" : "Výsledek:"}</b>{" "}
                  {udalost.vysledek}
                </div>
              )}

              {/* ---- rozbalené akce ---- */}
              {(akce === "hotovo" || akce === "zrusit") && (
                <div className="kd-formular">
                  <label className="crm-label">
                    {akce === "hotovo" ? "Jak to šlo?" : "Proč se to nekonalo?"}
                  </label>
                  <textarea
                    className="crm-pole"
                    rows={3}
                    value={vysledek}
                    onChange={(e) => setVysledek(e.target.value)}
                    placeholder={
                      akce === "hotovo"
                        ? "Např. chce to probrat po dovolené"
                        : "Např. zákazník schůzku zrušil"
                    }
                    autoFocus
                  />
                  <div className="kd-formular-pata">
                    <button
                      className="fm-btn fm-primary crm-btn-maly"
                      disabled={pracuje}
                      onClick={() =>
                        proved({
                          stav: akce === "hotovo" ? "realizovano" : "nekonalo_se",
                          vysledek,
                        })
                      }
                    >
                      {pracuje ? "Ukládám…" : "Potvrdit"}
                    </button>
                    <button className="fm-btn crm-btn-maly" onClick={() => setAkce(null)}>
                      Zpět
                    </button>
                  </div>
                </div>
              )}

              {akce === "presunout" && (
                <div className="kd-formular">
                  <label className="crm-label">Nový termín</label>
                  <div className="kd-presun">
                    <input
                      className="crm-pole"
                      type="date"
                      value={novyDen}
                      onChange={(e) => setNovyDen(e.target.value)}
                    />
                    {!udalost.cely_den && (
                      <input
                        className="crm-pole"
                        type="time"
                        value={novyCas}
                        onChange={(e) => setNovyCas(e.target.value)}
                      />
                    )}
                  </div>
                  <div className="kd-formular-pata">
                    <button
                      className="fm-btn fm-primary crm-btn-maly"
                      disabled={pracuje || !novyDen}
                      onClick={() =>
                        proved({
                          termin: novyDen,
                          ...(udalost.cely_den ? {} : { cas: novyCas }),
                        })
                      }
                    >
                      {pracuje ? "Přesouvám…" : "Přesunout"}
                    </button>
                    <button className="fm-btn crm-btn-maly" onClick={() => setAkce(null)}>
                      Zpět
                    </button>
                  </div>
                </div>
              )}

              {akce === "vic" && (
                <div className="kd-formular">
                  <button
                    className="fm-btn crm-btn-maly"
                    onClick={() => onUprav?.(udalost)}
                    style={{ width: "100%" }}
                  >
                    ✎ Upravit celou aktivitu
                  </button>
                  {udalost.stav !== "naplanovano" && (
                    <button
                      className="fm-btn crm-btn-maly"
                      style={{ width: "100%", marginTop: 6 }}
                      disabled={pracuje}
                      onClick={() => proved({ stav: "naplanovano", vysledek: "" })}
                    >
                      ↩ Vrátit mezi naplánované
                    </button>
                  )}
                  <button
                    className="fm-btn crm-btn-maly crm-btn-smazat"
                    style={{ width: "100%", marginTop: 6 }}
                    onClick={() => {
                      if (window.confirm(`Smazat aktivitu „${udalost.nazev}"?`)) {
                        onSmaz?.(udalost);
                      }
                    }}
                  >
                    ✕ Smazat aktivitu
                  </button>
                </div>
              )}
            </div>

            {/* ---- akční lišta ---- */}
            {!akce && (
              <div className="kd-pata">
                {udalost.stav === "naplanovano" ? (
                  <>
                    <button className="kd-akce hotovo" onClick={() => setAkce("hotovo")}>
                      ✓ Mám hotovo
                    </button>
                    <button className="kd-akce" onClick={() => setAkce("zrusit")}>
                      ✕ Zrušit
                    </button>
                    <button className="kd-akce" onClick={() => setAkce("presunout")}>
                      <Ikona jmeno="kalendar" velikost={13} /> Přesunout
                    </button>
                  </>
                ) : (
                  <button className="kd-akce" onClick={() => setAkce("presunout")}>
                    <Ikona jmeno="kalendar" velikost={13} /> Přesunout
                  </button>
                )}
                <span className="crm-mezera" />
                <button className="kd-akce kruh" onClick={() => setAkce("vic")} title="Další akce">
                  …
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
