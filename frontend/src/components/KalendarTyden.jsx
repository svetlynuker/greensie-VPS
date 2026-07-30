import { useMemo } from "react";
import { barvaDruhu, barvaTextuNa } from "../barvyAktivit";
import { DRUHY_AKTIVITY, fmtCas } from "../crm";
import { isoDen } from "../datum";

/**
 * Týdenní mřížka: den je sloupec, hodina řádek.
 *
 * Události se nekreslí do buněk tabulky, ale **absolutně nad sloupcem dne** —
 * jinak by schůzka od 9:30 do 11:00 nešla zobrazit jinak než jako celé dvě
 * buňky a půlhodiny by se ztratily.
 *
 * Celodenní úkoly (aktivita s termínem, ale bez hodiny) mají vlastní pruh nad
 * mřížkou. Kdyby se nacpaly na osmou ráno, tvrdily by čas, který nikdo nezadal.
 *
 * `odHod`/`doHod` je zobrazený rozsah (výchozí 8–20). Události mimo rozsah se
 * nezahazují — připnou se na kraj a označí šipkou, aby nezmizely bez varování.
 */

const DNY = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"];
// Výška jedné hodiny v pixelech. Musí odpovídat --kal-hodina v CSS.
const PX_HODINA = 44;

function hm(d) {
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function KalendarTyden({
  pondeli, // Date – první den zobrazeného týdne
  udalosti,
  barvy,
  odHod = 8,
  doHod = 20,
  vybranyDen,
  onDen,
  onUdalost,
  onPrazdno, // (isoDen, "HH:MM") → klik do prázdna (etapa K4)
}) {
  const dnesIso = isoDen(new Date());

  const dny = useMemo(
    () =>
      Array.from({ length: 7 }, (_, i) => {
        const d = new Date(pondeli);
        d.setDate(pondeli.getDate() + i);
        return d;
      }),
    [pondeli]
  );

  const hodiny = useMemo(
    () => Array.from({ length: doHod - odHod + 1 }, (_, i) => odHod + i),
    [odHod, doHod]
  );

  // Události rozdělené po dnech, zvlášť celodenní a zvlášť ty s hodinou.
  const podleDne = useMemo(() => {
    const map = new Map();
    for (const d of dny) map.set(isoDen(d), { celodenni: [], casove: [] });
    for (const u of udalosti || []) {
      const klic = (u.termin || "").slice(0, 10);
      const cil = map.get(klic);
      if (!cil) continue;
      (u.cely_den ? cil.celodenni : cil.casove).push(u);
    }
    return map;
  }, [dny, udalosti]);

  /** Pozice a výška dlaždice v pixelech podle času a délky. */
  function pozice(u) {
    const start = new Date(u.zacatek);
    const minutyOdZacatku = start.getHours() * 60 + start.getMinutes() - odHod * 60;
    const delka = Math.max(u.delka_min || 30, 20); // pod 20 min by byl text nečitelný
    const celkem = (doHod - odHod + 1) * 60;

    const nadRozsah = minutyOdZacatku < 0;
    const podRozsah = minutyOdZacatku > celkem;
    const top = Math.min(Math.max(minutyOdZacatku, 0), celkem - 20);
    const vyska = Math.min(delka, celkem - top);
    return {
      top: (top / 60) * PX_HODINA,
      vyska: Math.max((vyska / 60) * PX_HODINA, 18),
      mimo: nadRozsah ? "pred" : podRozsah ? "po" : "",
    };
  }

  return (
    <div className="kal-tyden">
      {/* ---- hlavička dnů ---- */}
      <div className="kal-tyden-hlava">
        <div className="kal-osa-rohu" />
        {dny.map((d) => {
          const iso = isoDen(d);
          return (
            <button
              key={iso}
              className={[
                "kal-den-hlava",
                iso === dnesIso ? "dnes" : "",
                iso === vybranyDen ? "vybrany" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => onDen?.(iso)}
              title={`${DNY[(d.getDay() + 6) % 7]} ${d.getDate()}. ${d.getMonth() + 1}.`}
            >
              <span className="kal-den-nazev">{DNY[(d.getDay() + 6) % 7].slice(0, 2)}</span>
              <span className="kal-den-cislo">{d.getDate()}.</span>
            </button>
          );
        })}
      </div>

      {/* ---- pruh celodenních (úkoly bez hodiny) ---- */}
      <div className="kal-celodenni">
        <div className="kal-celodenni-label" title="Úkoly s termínem, ale bez konkrétní hodiny">
          Celý den
        </div>
        {dny.map((d) => {
          const iso = isoDen(d);
          const seznam = podleDne.get(iso)?.celodenni || [];
          return (
            <div key={iso} className="kal-celodenni-den">
              {seznam.map((u) => (
                <button
                  key={u.id}
                  className={`kal-udalost celodenni ${u.stav !== "naplanovano" ? "uzavrena" : ""}`}
                  style={{
                    background: barvaDruhu(barvy, u.druh),
                    color: barvaTextuNa(barvaDruhu(barvy, u.druh)),
                  }}
                  onClick={() => onUdalost?.(u)}
                  title={u.muze_detail ? `${u.nazev}${u.zaznam_nazev ? ` · ${u.zaznam_nazev}` : ""}` : u.nazev}
                >
                  {u.nazev || "(bez názvu)"}
                </button>
              ))}
            </div>
          );
        })}
      </div>

      {/* ---- mřížka hodin ---- */}
      <div className="kal-mrizka">
        <div className="kal-osa">
          {hodiny.map((h) => (
            <div key={h} className="kal-osa-hodina">
              <span>{h}:00</span>
            </div>
          ))}
        </div>

        {dny.map((d) => {
          const iso = isoDen(d);
          const seznam = podleDne.get(iso)?.casove || [];
          return (
            <div
              key={iso}
              className={[
                "kal-den",
                iso === dnesIso ? "dnes" : "",
                iso === vybranyDen ? "vybrany" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {/* Prázdné půlhodiny jako terče pro zakládání (etapa K4). */}
              {hodiny.map((h) =>
                [0, 30].map((m) => (
                  <button
                    key={`${h}-${m}`}
                    className="kal-slot"
                    style={{ top: ((h - odHod) * 60 + m) * (PX_HODINA / 60), height: PX_HODINA / 2 }}
                    onClick={() => onPrazdno?.(iso, `${h}:${String(m).padStart(2, "0")}`)}
                    title={`Nová událost ${d.getDate()}.${d.getMonth() + 1}. v ${h}:${String(m).padStart(2, "0")}`}
                    aria-label={`Nová událost ${h}:${String(m).padStart(2, "0")}`}
                  />
                ))
              )}

              {seznam.map((u) => {
                const p = pozice(u);
                const barva = barvaDruhu(barvy, u.druh);
                const ikona = DRUHY_AKTIVITY.find((x) => x.klic === u.druh)?.ikona || "";
                return (
                  <button
                    key={u.id}
                    className={[
                      "kal-udalost",
                      u.stav !== "naplanovano" ? "uzavrena" : "",
                      u.muze_detail ? "" : "blok",
                      p.mimo ? `mimo-${p.mimo}` : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    style={{
                      top: p.top,
                      height: p.vyska,
                      background: u.muze_detail ? barva : undefined,
                      color: u.muze_detail ? barvaTextuNa(barva) : undefined,
                    }}
                    onClick={() => onUdalost?.(u)}
                    title={
                      u.muze_detail
                        ? [
                            `${fmtCas(u.zacatek, u.delka_min)} ${u.nazev}`,
                            u.zaznam_nazev,
                            u.vysledek ? `Výsledek: ${u.vysledek}` : "",
                          ]
                            .filter(Boolean)
                            .join("\n")
                        : `${u.nazev} · ${u.vlastnik_jmeno || ""}`
                    }
                  >
                    <span className="kal-udalost-cas">
                      {p.mimo === "pred" ? "↑ " : ""}
                      {hm(new Date(u.zacatek))}
                      {p.mimo === "po" ? " ↓" : ""}
                    </span>
                    <span className="kal-udalost-nazev">
                      {ikona && u.muze_detail ? `${ikona} ` : ""}
                      {u.nazev || "(bez názvu)"}
                    </span>
                    {u.zaznam_nazev && p.vyska > 40 && (
                      <span className="kal-udalost-zaznam">{u.zaznam_nazev}</span>
                    )}
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
