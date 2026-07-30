import { useMemo, useRef, useState } from "react";
import Ikona from "./Ikona";
import { barvaDruhu, barvaTextuNa } from "../barvyAktivit";
import { DRUHY_AKTIVITY } from "../crm";
import { isoDen, posunDnu } from "../datum";
import {
  KROK_MIN,
  MIN_DELKA,
  PRAC_DO,
  PRAC_OD,
  PX_HODINA,
  PX_NOC,
  PX_VECER,
  VYSKA_DNE,
  hm,
  minutyZCasu,
  minutyZY,
  naCas,
  yZMinut,
  zTazeni,
} from "../kalendarCas";

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
  onPresun, // (udalost, {termin, cas, delka_min, konec}) → ulož
}) {
  const dnesIso = isoDen(new Date());
  const refMrizka = useRef(null);
  const refOsa = useRef(null);
  // Probíhající tažení. `posunuto` rozlišuje klik od tažení: bez toho by každé
  // kliknutí na dlaždici skončilo uložením „přesunu" na totéž místo.
  const [tazeni, setTazeni] = useState(null);

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

  // ---- tažení: přesun a změna délky ----------------------------------------
  //
  // Pointer events (ne HTML5 drag&drop): ten neumí plynulý náhled ani tažení za
  // hranu a na dotykovém displeji nefunguje vůbec. `setPointerCapture` drží
  // události u dlaždice, i když kurzor vyjede jinam.

  /** Z pozice kurzoru spočítá, nad kterým dnem a v které minutě je. */
  function miraKurzoru(e) {
    const mrizka = refMrizka.current?.getBoundingClientRect();
    const osa = refOsa.current?.getBoundingClientRect();
    if (!mrizka || !osa) return null;
    const sirkaDne = (mrizka.width - osa.width) / 7;
    const idx = Math.floor((e.clientX - mrizka.left - osa.width) / sirkaDne);
    return {
      denIdx: Math.max(0, Math.min(6, idx)),
      minuty: minutyZY(e.clientY - mrizka.top),
    };
  }

  function zacniTazeni(e, u, rezim) {
    // Cizí blok se přesouvat nesmí a levé tlačítko je jediné, které táhne.
    if (!u.muze_detail || (e.pointerType === "mouse" && e.button !== 0)) return;
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const start = miraKurzoru(e);
    if (!start) return;
    const odMin = u.cely_den ? 0 : minutyZCasu(u.zacatek);
    setTazeni({
      id: u.id,
      rezim,
      celyDen: Boolean(u.cely_den),
      vicedenni: Boolean(u.vicedenni),
      // Kolik dní trvá vícedenní blok – při přesunu se délka zachovává.
      dniDelka:
        u.vicedenni && u.konec
          ? Math.round(
              (new Date(`${u.konec}T12:00:00`) - new Date(`${u.termin}T12:00:00`)) / 86400000
            )
          : 0,
      startMin: start.minuty,
      startDenIdx: start.denIdx,
      puvodOd: odMin,
      puvodDelka: Math.max(u.delka_min || 30, MIN_DELKA),
      puvodDenIdx: dny.findIndex((d) => isoDen(d) === (u.termin || "").slice(0, 10)),
      od: odMin,
      delka: Math.max(u.delka_min || 30, MIN_DELKA),
      denIdx: dny.findIndex((d) => isoDen(d) === (u.termin || "").slice(0, 10)),
      posunuto: false,
    });
  }

  function pokracujTazeni(e) {
    if (!tazeni) return;
    const nyni = miraKurzoru(e);
    if (!nyni) return;
    const deltaMin = nyni.minuty - tazeni.startMin;
    const deltaDen = nyni.denIdx - tazeni.startDenIdx;
    // Práh, aby se z drobného cuknutí při kliknutí nestal přesun.
    const posunuto =
      tazeni.posunuto || Math.abs(deltaMin) >= KROK_MIN / 2 || deltaDen !== 0;

    setTazeni((t) => {
      if (!t) return t;
      // Přepočet je v `kalendarCas.zTazeni` — čistá funkce, ať je testovatelná.
      const nove = zTazeni(t.rezim, t.puvodOd, t.puvodDelka, deltaMin);
      if (t.rezim === "presun") {
        return {
          ...t,
          posunuto,
          denIdx: Math.max(0, Math.min(6, t.puvodDenIdx + deltaDen)),
          od: t.celyDen ? t.od : nove.od,
          delka: nove.delka,
        };
      }
      return { ...t, posunuto, od: nove.od, delka: nove.delka };
    });
  }

  function dokonciTazeni(e, u) {
    if (!tazeni || tazeni.id !== u.id) return;
    const t = tazeni;
    setTazeni(null);
    // Bez posunu je to obyčejné kliknutí → detail.
    if (!t.posunuto) {
      onUdalost?.(u);
      return;
    }
    e.stopPropagation();

    const novyDen = isoDen(dny[t.denIdx]);
    const zmena = { termin: novyDen };
    if (t.celyDen) {
      // Celodenní a vícedenní se jen přesouvají mezi dny; délka ve dnech se
      // zachová, aby se třídenní školení nezkrátilo na jeden den.
      if (t.vicedenni && t.dniDelka > 0) {
        zmena.konec = isoDen(posunDnu(dny[t.denIdx], t.dniDelka));
      }
    } else {
      zmena.cas = naCas(t.od);
      zmena.delka_min = Math.round(t.delka);
    }
    onPresun?.(u, zmena);
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
    const tahnuta = tazeni?.id === u.id && tazeni.posunuto;
    // Úchyty jen tam, kde má změna délky smysl: celodenní a vícedenní aktivita
    // hodinu nemá, takže by se protahovala do prázdna.
    const lzeMenitDelku = u.muze_detail && !u.cely_den && Boolean(onPresun);
    return (
      <button
        className={[
          "kal-udalost",
          u.stav === "realizovano" ? "realizovana" : "",
          u.stav === "nekonalo_se" ? "zrusena" : "",
          u.muze_detail ? "" : "blok",
          kratka ? "kratka" : "",
          u.muze_detail && onPresun ? "tahnutelna" : "",
          tahnuta ? "tahnu" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{ ...styl(u), ...styleExtra }}
        onPointerDown={(e) => onPresun && zacniTazeni(e, u, "presun")}
        onPointerMove={pokracujTazeni}
        onPointerUp={(e) => dokonciTazeni(e, u)}
        onPointerCancel={() => setTazeni(null)}
        // Klik obsluhuje `dokonciTazeni` (rozlišuje klik od tažení). Bez
        // onPresun tažení neexistuje, takže se detail otevírá přímo.
        onClick={onPresun ? undefined : () => onUdalost?.(u)}
        title={popis(u)}
      >
        {lzeMenitDelku && (
          <>
            <span
              className="kal-uchyt horni"
              onPointerDown={(e) => zacniTazeni(e, u, "horni")}
              title="Táhnutím změníš začátek"
            />
            <span
              className="kal-uchyt dolni"
              onPointerDown={(e) => zacniTazeni(e, u, "dolni")}
              title="Táhnutím změníš délku"
            />
          </>
        )}
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
            const t = tazeni?.id === u.id && tazeni.posunuto ? tazeni : null;
            const r = t
              ? {
                  od: t.denIdx,
                  do: Math.min(6, t.denIdx + (t.dniDelka || 0)),
                  pretekaVlevo: false,
                  pretekaVpravo: t.denIdx + (t.dniDelka || 0) > 6,
                }
              : rozsahPruhu(u);
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
      <div className="kal-mrizka" style={{ height: VYSKA_DNE }} ref={refMrizka}>
        <div className="kal-osa" ref={refOsa}>
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
          let seznam = vMrizce.get(iso) || [];
          const vrstva = vrstvy.get(iso);
          // Tažení do jiného dne: dlaždici kreslí cílový sloupec, ne původní.
          if (tazeni?.posunuto && !tazeni.celyDen) {
            const cil = isoDen(dny[tazeni.denIdx]);
            if (iso === cil) {
              const tazena = (udalosti || []).find((x) => x.id === tazeni.id);
              if (tazena && !seznam.some((x) => x.id === tazeni.id)) seznam = [...seznam, tazena];
            } else {
              seznam = seznam.filter((x) => x.id !== tazeni.id);
            }
          }
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
                // Během tažení se kreslí na místo, kam kurzor míří (náhled).
                const t = tazeni?.id === u.id && tazeni.posunuto ? tazeni : null;
                const od = t ? t.od : minutyZCasu(u.zacatek);
                const delka = Math.max(t ? t.delka : u.delka_min || 30, MIN_DELKA);
                const top = yZMinut(od);
                const vyska = Math.max(yZMinut(od + delka) - top, 16);
                const v = vrstva?.get(u.id) || { sloupec: 0, sloupcu: 1 };
                // Tažená dlaždice zabírá celou šířku dne — jinak by při přesunu
                // do jiného sloupce zůstala zúžená podle původního souběhu.
                const sirka = t ? 100 : 100 / v.sloupcu;
                return (
                  <Dlazdice
                    key={u.id}
                    u={u}
                    styleExtra={{
                      top,
                      height: vyska,
                      left: t ? "2px" : `calc(${v.sloupec * sirka}% + 2px)`,
                      width: t ? "calc(100% - 4px)" : `calc(${sirka}% - 4px)`,
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
