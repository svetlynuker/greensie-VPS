import { useMemo } from "react";
import { barvaDruhu, barvaTextuNa } from "../barvyAktivit";
import { isoDen, pondeliTydne, posunDnu } from "../datum";
import { hm } from "../kalendarCas";

/**
 * Měsíční pohled: mřížka 6×7 s dlaždicemi aktivit.
 *
 * Podle rozhodnutí Dana ukazuje **čas a název**, ne jen tečky — nejvíc
 * informací na jednu obrazovku. Přebytek se schová do „+3 další", protože do
 * buňky se vejdou tři dlaždice a nafouknutá buňka by rozhodila celý měsíc.
 *
 * Kliknutí na den přepne na týdenní pohled (a označí ten den); kliknutí na
 * dlaždici otevře detail. Klik na „+N další" taky přepne na týden — tam je
 * vidět všechno.
 *
 * Mřížka má vždy 6 řádků, i když měsíc vyjde na 5: jinak by se výška obsahu
 * měnila podle měsíce a stránka by při přepínání poskakovala.
 */

const DNY = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"];
const MAX_V_DNI = 3;

export default function KalendarMesicniPohled({
  mesic, // Date kdekoli v zobrazovaném měsíci
  udalosti,
  barvy,
  vybranyDen,
  onDen, // (isoDen) → označit
  onTyden, // (isoDen) → přepnout na týdenní pohled
  onUdalost,
}) {
  const dnesIso = isoDen(new Date());

  const dny = useMemo(() => {
    const start = pondeliTydne(new Date(mesic.getFullYear(), mesic.getMonth(), 1));
    return Array.from({ length: 42 }, (_, i) => posunDnu(start, i));
  }, [mesic]);

  /** Aktivity po dnech. Vícedenní se zapíše do každého dne, kterým prochází —
   *  v měsíčním pohledu je důležitější „v tenhle den něco je" než souvislý pruh. */
  const podleDne = useMemo(() => {
    const map = new Map();
    for (const d of dny) map.set(isoDen(d), []);
    for (const u of udalosti || []) {
      const od = (u.termin || "").slice(0, 10);
      const do_ = (u.konec || u.termin || "").slice(0, 10);
      for (const [iso, seznam] of map) {
        if (iso >= od && iso <= do_) seznam.push(u);
      }
    }
    // Uvnitř dne: celodenní nahoru, pak podle času.
    for (const seznam of map.values()) {
      seznam.sort((a, b) => {
        if (a.cely_den !== b.cely_den) return a.cely_den ? -1 : 1;
        return (a.zacatek || "").localeCompare(b.zacatek || "");
      });
    }
    return map;
  }, [dny, udalosti]);

  return (
    <div className="km">
      <div className="km-zahlavi">
        {DNY.map((d) => (
          <div key={d} className="km-zahlavi-den">
            {d}
          </div>
        ))}
      </div>
      <div className="km-mrizka">
        {dny.map((d) => {
          const iso = isoDen(d);
          const seznam = podleDne.get(iso) || [];
          const jinyMesic = d.getMonth() !== mesic.getMonth();
          return (
            <div
              key={iso}
              className={[
                "km-den",
                jinyMesic ? "mimo" : "",
                iso === dnesIso ? "dnes" : "",
                iso === vybranyDen ? "vybrany" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <button
                className="km-cislo"
                onClick={() => onDen?.(iso)}
                onDoubleClick={() => onTyden?.(iso)}
                title="Klik označí den, dvojklik otevře týden"
              >
                {d.getDate()}
              </button>

              <div className="km-udalosti">
                {seznam.slice(0, MAX_V_DNI).map((u) => {
                  const barva = u.kategorie_barva || barvaDruhu(barvy, u.druh);
                  return (
                    <button
                      key={`${iso}-${u.id}`}
                      className={[
                        "km-udalost",
                        u.stav === "realizovano" ? "realizovana" : "",
                        u.stav === "nekonalo_se" ? "zrusena" : "",
                        u.muze_detail ? "" : "blok",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      style={
                        u.muze_detail
                          ? { background: barva, color: barvaTextuNa(barva) }
                          : undefined
                      }
                      onClick={(e) =>
                        onUdalost?.(u, e.currentTarget.getBoundingClientRect())
                      }
                      title={`${u.cely_den ? "celý den" : hm(u.zacatek)} · ${u.nazev}${
                        u.zaznam_nazev ? ` · ${u.zaznam_nazev}` : ""
                      }`}
                    >
                      {!u.cely_den && <span className="km-cas">{hm(u.zacatek)}</span>}
                      <span className="km-nazev">{u.nazev || "(bez názvu)"}</span>
                    </button>
                  );
                })}
                {seznam.length > MAX_V_DNI && (
                  <button className="km-vic" onClick={() => onTyden?.(iso)}>
                    +{seznam.length - MAX_V_DNI} další
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
