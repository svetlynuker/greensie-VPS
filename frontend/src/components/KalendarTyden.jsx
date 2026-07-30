import { useMemo } from "react";
import Ikona from "./Ikona";
import { barvaDruhu, barvaTextuNa } from "../barvyAktivit";
import { DRUHY_AKTIVITY } from "../crm";
import { isoDen } from "../datum";

/**
 * Týdenní mřížka: den je sloupec, hodina řádek.
 *
 * ---- Komprimovaná noc a večer (podle předlohy) --------------------------
 * Den se nekreslí celý stejným měřítkem. Osa je:
 *
 *   0:00 ─┬─ jeden zúžený pás (noc)
 *   7:00 ─┘
 *   7:00 … 19:00 po hodinách (pracovní část, plná výška)
 *  19:00 ─┬─ jeden zúžený pás (večer)
 *  23:59 ─┘
 *
 * Řeší to spor mezi „vejde se pracovní den na obrazovku" a „nic se neschová":
 * noční a večerní aktivita zůstane vidět, jen zploštělá. Kdyby se rozsah
 * pevně omezil na 8–20, večerní schůzka by z kalendáře beze slova zmizela.
 *
 * ---- Pozicování ---------------------------------------------------------
 * Události leží ABSOLUTNĚ nad sloupcem dne, ne v buňkách tabulky — jinak by
 * schůzka 9:30–11:00 nešla zobrazit jinak než jako dvě celé buňky. Přepočet
 * „minuta → pixel" proto musí umět všechna tři pásma, viz `yZMinut()`.
 *
 * Souběžné události (dvě schůzky na stejnou hodinu) se dělí na sloupce, aby se
 * nepřekrývaly a šlo kliknout na obě.
 */

const DNY = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"];

// Hranice pracovní části a výšky pásem v pixelech.
const PRAC_OD = 7;
const PRAC_DO = 19;
const PX_HODINA = 44; // musí odpovídat --kal-hodina v CSS
const PX_NOC = 26; // zúžený pás 0:00–7:00
const PX_VECER = 26; // zúžený pás 19:00–23:59

/** Minuta dne (0–1440) → svislá pozice v pixelech. */
function yZMinut(min) {
  const odMin = PRAC_OD * 60;
  const doMin = PRAC_DO * 60;
  if (min <= odMin) return (min / odMin) * PX_NOC;
  if (min >= doMin) {
    return PX_NOC + (doMin - odMin) / 60 * PX_HODINA + ((min - doMin) / (1440 - doMin)) * PX_VECER;
  }
  return PX_NOC + ((min - odMin) / 60) * PX_HODINA;
}

const VYSKA_DNE = PX_NOC + (PRAC_DO - PRAC_OD) * PX_HODINA + PX_VECER;

function minutyZCasu(iso) {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

function hm(iso) {
  const d = new Date(iso);
  return `${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
}

/**
 * Rozdělí překrývající se události do sloupců.
 * Vrací pro každou událost `{ sloupec, sloupcu }` — bez toho by dvě schůzky na
 * stejnou hodinu ležely přesně na sobě a na spodní by nešlo kliknout.
 */
function rozvrstvi(seznam) {
  const s = [...seznam].sort((a, b) => minutyZCasu(a.zacatek) - minutyZCasu(b.zacatek));
  const konce = []; // konec poslední události v každém sloupci
  const mapa = new Map();
  for (const u of s) {
    const od = minutyZCasu(u.zacatek);
    const do_ = od + Math.max(u.delka_min || 30, 15);
    let sloupec = konce.findIndex((k) => k <= od);
    if (sloupec === -1) {
      sloupec = konce.length;
      konce.push(do_);
    } else {
      konce[sloupec] = do_;
    }
    mapa.set(u.id, { sloupec });
  }
  const sloupcu = Math.max(konce.length, 1);
  for (const v of mapa.values()) v.sloupcu = sloupcu;
  return mapa;
}

export default function KalendarTyden({
  pondeli,
  udalosti,
  barvy,
  vybranyDen,
  onDen,
  onUdalost,
  onPrazdno, // (isoDen, "HH:MM")
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
    () => Array.from({ length: PRAC_DO - PRAC_OD }, (_, i) => PRAC_OD + i),
    []
  );

  // Rozdělení: vícedenní a celodenní jdou do pruhu nahoře, ostatní do mřížky.
  const { pruh, vMrizce } = useMemo(() => {
    const pruh = [];
    const vMrizce = new Map();
    for (const d of dny) vMrizce.set(isoDen(d), []);
    for (const u of udalosti || []) {
      if (u.vicedenni || u.cely_den) {
        pruh.push(u);
        continue;
      }
      const klic = (u.termin || "").slice(0, 10);
      if (vMrizce.has(klic)) vMrizce.get(klic).push(u);
    }
    return { pruh, vMrizce };
  }, [dny, udalosti]);

  const vrstvy = useMemo(() => {
    const out = new Map();
    for (const [iso, seznam] of vMrizce) out.set(iso, rozvrstvi(seznam));
    return out;
  }, [vMrizce]);

  /** Vícedenní pruh: od kterého do kterého sloupce týdne se táhne. */
  function rozsahPruhu(u) {
    const prvni = isoDen(pondeli);
    const posledni = isoDen(dny[6]);
    const od = (u.termin || "").slice(0, 10);
    const do_ = (u.konec || u.termin || "").slice(0, 10);
    const odIdx = od < prvni ? 0 : dny.findIndex((d) => isoDen(d) === od);
    const doIdx = do_ > posledni ? 6 : dny.findIndex((d) => isoDen(d) === do_);
    return {
      od: Math.max(odIdx, 0),
      do: Math.max(doIdx, odIdx < 0 ? 0 : odIdx),
      pretekaVlevo: od < prvni,
      pretekaVpravo: do_ > posledni,
    };
  }

  function styl(u) {
    // Kategorie má přednost před barvou druhu: když si někdo aktivitu označí
    // štítkem, čeká, že se podle něj obarví. Bez štítku padá na osobní barvu
    // druhu z Nastavení (`barvaDruhu` ošetří i chybějící a neplatné hodnoty).
    const barva = u.kategorie_barva || barvaDruhu(barvy, u.druh);
    return u.muze_detail
      ? { background: barva, color: barvaTextuNa(barva) }
      : undefined;
  }

  function popis(u) {
    if (!u.muze_detail) return `${u.nazev}${u.vlastnik_jmeno ? ` · ${u.vlastnik_jmeno}` : ""}`;
    return [
      u.cely_den ? "Celý den" : `${hm(u.zacatek)} · ${u.nazev}`,
      u.zaznam_nazev,
      u.misto,
      u.kategorie_nazev,
      u.vysledek ? `Výsledek: ${u.vysledek}` : "",
    ]
      .filter(Boolean)
      .join("\n");
  }

  function Dlazdice({ u, styleExtra, kratka }) {
    const druh = DRUHY_AKTIVITY.find((x) => x.klic === u.druh);
    return (
      <button
        className={[
          "kal-udalost",
          u.stav === "realizovano" ? "realizovana" : "",
          u.stav === "nekonalo_se" ? "zrusena" : "",
          u.muze_detail ? "" : "blok",
          kratka ? "kratka" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{ ...styl(u), ...styleExtra }}
        onClick={() => onUdalost?.(u)}
        title={popis(u)}
      >
        <span className="kal-udalost-radek">
          {u.priorita === "vysoka" && (
            <span className="kal-priorita" title="Vysoká priorita">
              !
            </span>
          )}
          {u.muze_detail && druh && <Ikona jmeno={druh.ikona} velikost={11} />}
          {!u.cely_den && <span className="kal-udalost-cas">{hm(u.zacatek)}</span>}
          <span className="kal-udalost-nazev">{u.nazev || "(bez názvu)"}</span>
          {u.zaznam_nazev && <span className="kal-udalost-zaznam">{u.zaznam_nazev}</span>}
        </span>
      </button>
    );
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
              <span className="kal-den-nazev">
                {DNY[(d.getDay() + 6) % 7].slice(0, 2).toUpperCase()}
              </span>
              <span className="kal-den-cislo">{d.getDate()}</span>
            </button>
          );
        })}
      </div>

      {/* ---- pruh vícedenních a celodenních ---- */}
      <div className="kal-vicedenni">
        <div className="kal-vicedenni-label">vícedenní</div>
        <div className="kal-vicedenni-plocha">
          {pruh.length === 0 && <div className="kal-vicedenni-prazdno" />}
          {pruh.map((u) => {
            const r = rozsahPruhu(u);
            return (
              <div
                key={u.id}
                className="kal-vicedenni-radek"
                style={{ gridColumn: `${r.od + 1} / ${r.do + 2}` }}
              >
                <Dlazdice
                  u={u}
                  kratka
                  styleExtra={{
                    borderTopLeftRadius: r.pretekaVlevo ? 0 : undefined,
                    borderBottomLeftRadius: r.pretekaVlevo ? 0 : undefined,
                    borderTopRightRadius: r.pretekaVpravo ? 0 : undefined,
                    borderBottomRightRadius: r.pretekaVpravo ? 0 : undefined,
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>

      {/* ---- mřížka hodin ---- */}
      <div className="kal-mrizka" style={{ height: VYSKA_DNE }}>
        <div className="kal-osa">
          <div className="kal-osa-pas" style={{ height: PX_NOC }}>
            <span className="kal-osa-cas horni">0:00</span>
            <span className="kal-osa-cas dolni">7:00</span>
          </div>
          {hodiny.map((h) => (
            <div key={h} className="kal-osa-hodina" style={{ height: PX_HODINA }}>
              <span>{h}:00</span>
            </div>
          ))}
          <div className="kal-osa-pas" style={{ height: PX_VECER }}>
            <span className="kal-osa-cas horni">19:00</span>
            <span className="kal-osa-cas dolni">23:59</span>
          </div>
        </div>

        {dny.map((d) => {
          const iso = isoDen(d);
          const seznam = vMrizce.get(iso) || [];
          const vrstva = vrstvy.get(iso);
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
              {/* Zúžená pásma mají jiné pozadí – ať je vidět, že měřítko je jiné. */}
              <div className="kal-pas noc" style={{ height: PX_NOC }} />
              <div
                className="kal-pas vecer"
                style={{ top: PX_NOC + (PRAC_DO - PRAC_OD) * PX_HODINA, height: PX_VECER }}
              />

              {/* Terče pro zakládání po půlhodinách (jen pracovní část). */}
              {hodiny.map((h) =>
                [0, 30].map((m) => (
                  <button
                    key={`${h}-${m}`}
                    className="kal-slot"
                    style={{ top: yZMinut(h * 60 + m), height: PX_HODINA / 2 }}
                    onClick={() => onPrazdno?.(iso, `${h}:${String(m).padStart(2, "0")}`)}
                    title={`Nová aktivita ${d.getDate()}.${d.getMonth() + 1}. v ${h}:${String(m).padStart(2, "0")}`}
                    aria-label={`Nová aktivita ${h}:${String(m).padStart(2, "0")}`}
                  />
                ))
              )}

              {seznam.map((u) => {
                const od = minutyZCasu(u.zacatek);
                const top = yZMinut(od);
                const vyska = Math.max(yZMinut(od + Math.max(u.delka_min || 30, 15)) - top, 16);
                const v = vrstva?.get(u.id) || { sloupec: 0, sloupcu: 1 };
                const sirka = 100 / v.sloupcu;
                return (
                  <Dlazdice
                    key={u.id}
                    u={u}
                    styleExtra={{
                      top,
                      height: vyska,
                      left: `calc(${v.sloupec * sirka}% + 2px)`,
                      width: `calc(${sirka}% - 4px)`,
                    }}
                    kratka={vyska < 30}
                  />
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
