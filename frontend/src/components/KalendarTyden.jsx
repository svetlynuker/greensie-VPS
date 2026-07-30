import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
 * noční a večerní aktivita zůstane vidět, jen zploštělá.
 *
 * ---- Pozicování ---------------------------------------------------------
 * Události leží ABSOLUTNĚ nad sloupcem dne, ne v buňkách tabulky — jinak by
 * schůzka 9:30–11:00 nešla zobrazit jinak než jako dvě celé buňky.
 *
 * ---- Tažení: proč globální listenery a ne pointer capture ---------------
 * První verze držela události přes `setPointerCapture` na dlaždici a měla dvě
 * chyby, které se projevily hned: dlaždice „zamrzla" jako pořád chycená a šlo
 * s ní hýbat jen v rámci jednoho dne.
 *
 * Příčina byla jedna — `Dlazdice` byla komponenta definovaná UVNITŘ téhle
 * komponenty. Každé překreslení vyrobilo nový typ, React element odmountoval
 * a znovu namountoval, čímž se capture okamžitě ztratil. `pointerup` pak nikdy
 * nedošel, tažení nikdy neskončilo a každý pohyb nad jakoukoli dlaždicí
 * posouval tu původní (odtud „náhodné teleportování"). Přesun do jiného
 * sloupce dne remount vyvolával podruhé.
 *
 * Proto teď:
 *   * `Dlazdice` je modulová komponenta (žádné remounty),
 *   * pohyb a puštění se poslouchá na `window`, takže je jedno, co se s DOM
 *     dlaždice děje,
 *   * data tažení jsou v ref (mutace bez překreslení), ve stavu je jen náhled,
 *   * během tažení se originál NEPŘESOUVÁ — kreslí se poloprůhledný „duch"
 *     v cílovém dni,
 *   * pojistky pro případ, že by se `pointerup` přece jen nedostal:
 *     `e.buttons === 0` při pohybu tažení ukončí, stejně jako Escape,
 *     ztráta fokusu okna a `pointercancel`.
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
    const do_ = od + Math.max(u.delka_min || 30, MIN_DELKA);
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

/** Barva dlaždice: štítek kategorie má přednost před osobní barvou druhu. */
function barvaUdalosti(u, barvy) {
  return u.kategorie_barva || barvaDruhu(barvy, u.druh);
}

function popisUdalosti(u) {
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

/**
 * Dlaždice aktivity. MODULOVÁ komponenta schválně — kdyby byla definovaná
 * uvnitř `KalendarTyden`, React by ji při každém překreslení odmountoval
 * a tažení by se rozbilo (viz docstring výš).
 */
function Dlazdice({
  u,
  barvy,
  styl,
  kratka,
  duch = false,
  ztlumena = false,
  lzeTahnout = false,
  casNahledu = null,
  onZacniTazeni,
  onKlik,
}) {
  const druh = DRUHY_AKTIVITY.find((x) => x.klic === u.druh);
  const barva = barvaUdalosti(u, barvy);
  const lzeMenitDelku = lzeTahnout && !u.cely_den;

  return (
    <div
      className={[
        "kal-udalost",
        u.stav === "realizovano" ? "realizovana" : "",
        u.stav === "nekonalo_se" ? "zrusena" : "",
        u.muze_detail ? "" : "blok",
        kratka ? "kratka" : "",
        lzeTahnout ? "tahnutelna" : "",
        duch ? "duch" : "",
        ztlumena ? "ztlumena" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        ...(u.muze_detail ? { background: barva, color: barvaTextuNa(barva) } : null),
        ...styl,
      }}
      // Duch je jen náhled — nesmí brát kliknutí ani reagovat na tažení.
      onPointerDown={duch ? undefined : (e) => onZacniTazeni?.(e, u, "presun")}
      onClick={
        duch
          ? undefined
          : (e) => onKlik?.(u, e.currentTarget.getBoundingClientRect())
      }
      title={duch ? undefined : popisUdalosti(u)}
      role={duch ? "presentation" : "button"}
      tabIndex={duch ? -1 : 0}
      onKeyDown={
        duch
          ? undefined
          : (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onKlik?.(u, e.currentTarget.getBoundingClientRect());
              }
            }
      }
    >
      {lzeMenitDelku && !duch && (
        <>
          <span
            className="kal-uchyt horni"
            onPointerDown={(e) => onZacniTazeni?.(e, u, "horni")}
            title="Táhnutím změníš začátek"
          />
          <span
            className="kal-uchyt dolni"
            onPointerDown={(e) => onZacniTazeni?.(e, u, "dolni")}
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
        {!u.cely_den && (
          <span className="kal-udalost-cas">{casNahledu || hm(u.zacatek)}</span>
        )}
        <span className="kal-udalost-nazev">{u.nazev || "(bez názvu)"}</span>
        {u.zaznam_nazev && <span className="kal-udalost-zaznam">{u.zaznam_nazev}</span>}
      </span>
    </div>
  );
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

  // Data probíhajícího tažení. V ref, protože se mění při každém pohybu myši
  // a nemá cenu kvůli nim překreslovat celou mřížku.
  const tazeniRef = useRef(null);
  // Ve stavu je jen to, co se kreslí (duch), a příznak pro registraci listenerů.
  const [tahnu, setTahnu] = useState(false);
  const [nahled, setNahled] = useState(null);

  // Callbacky přes ref, aby se globální listenery registrovaly JEDNOU za
  // tažení. Kdyby byly v závislostech efektu, přidávaly a odebíraly by se při
  // každém pohybu.
  const onPresunRef = useRef(onPresun);
  const onUdalostRef = useRef(onUdalost);
  onPresunRef.current = onPresun;
  onUdalostRef.current = onUdalost;

  // Po dokončeném tažení prohlížeč MŮŽE ještě vyvolat `click` na dlaždici — bez
  // pojistky by se po přetažení navíc otevřel detail. Drží se čas, ne boolean:
  // kdyby ten `click` nikdy nepřišel (což se podle prohlížeče stává), zůstal by
  // příznak nastavený a spolkl by až příští opravdové kliknutí.
  const potlacitKlikDoRef = useRef(0);

  const dny = useMemo(
    () => Array.from({ length: 7 }, (_, i) => posunDnu(pondeli, i)),
    [pondeli]
  );
  const dnyRef = useRef(dny);
  dnyRef.current = dny;

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

  /** Z pozice kurzoru spočítá, nad kterým dnem a v které minutě je. */
  const miraKurzoru = useCallback((e) => {
    const mrizka = refMrizka.current?.getBoundingClientRect();
    const osa = refOsa.current?.getBoundingClientRect();
    if (!mrizka || !osa) return null;
    const sirkaDne = (mrizka.width - osa.width) / 7;
    if (!(sirkaDne > 0)) return null;
    const idx = Math.floor((e.clientX - mrizka.left - osa.width) / sirkaDne);
    return {
      denIdx: Math.max(0, Math.min(6, idx)),
      minuty: minutyZY(e.clientY - mrizka.top),
    };
  }, []);

  function zacniTazeni(e, u, rezim) {
    // Cizí blok táhnout nelze a levé tlačítko je jediné, které táhne.
    if (!u.muze_detail || !onPresun) return;
    if (e.pointerType === "mouse" && e.button !== 0) return;
    const start = miraKurzoru(e);
    if (!start) return;
    e.preventDefault();
    e.stopPropagation();

    const denIdx = dny.findIndex((d) => isoDen(d) === (u.termin || "").slice(0, 10));
    const odMin = u.cely_den ? 0 : minutyZCasu(u.zacatek);
    tazeniRef.current = {
      u,
      rezim,
      // Kotva pro popover s detailem. Bere se z DLAŽDICE, ne z `currentTarget` —
      // při chycení za úchyt je currentTarget ten úzký pásek na hraně a popover
      // by se ukotvil ke třem pixelům.
      kotva: e.currentTarget.closest(".kal-udalost")?.getBoundingClientRect() || null,
      celyDen: Boolean(u.cely_den),
      vicedenni: Boolean(u.vicedenni),
      // Kolik dní trvá vícedenní blok — při přesunu se délka zachovává.
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
      puvodDenIdx: denIdx < 0 ? start.denIdx : denIdx,
      od: odMin,
      delka: Math.max(u.delka_min || 30, MIN_DELKA),
      denIdx: denIdx < 0 ? start.denIdx : denIdx,
      posunuto: false,
    };
    setNahled(null);
    setTahnu(true);
  }

  // Globální listenery: registrují se jednou na začátku tažení a jsou nezávislé
  // na tom, co se děje s DOM dlaždice.
  useEffect(() => {
    if (!tahnu) return undefined;

    function ukonci(ulozit) {
      const t = tazeniRef.current;
      tazeniRef.current = null;
      setTahnu(false);
      setNahled(null);
      if (!t) return;
      if (!ulozit) return; // zrušeno Escapem nebo pointercancel
      if (!t.posunuto) {
        // Kliknutí bez posunu → detail. Otevírá se TADY, ne v `onClick`:
        // `zacniTazeni` volá `preventDefault()` na pointerdown (jinak by
        // prohlížeč začal nativní drag a vybíral text), a to v prohlížečích
        // potlačí i následný `click`. Bez tohohle by detail nešel otevřít
        // vůbec — právě na to Dan narazil.
        potlacitKlikDoRef.current = Date.now() + 400;
        onUdalostRef.current?.(t.u, t.kotva);
        return;
      }
      potlacitKlikDoRef.current = Date.now() + 400;
      const dnyNyni = dnyRef.current;
      const cilovyDen = dnyNyni[t.denIdx] || dnyNyni[t.puvodDenIdx];
      const zmena = { termin: isoDen(cilovyDen) };
      if (t.celyDen) {
        if (t.vicedenni && t.dniDelka > 0) {
          zmena.konec = isoDen(posunDnu(cilovyDen, t.dniDelka));
        }
      } else {
        zmena.cas = naCas(t.od);
        zmena.delka_min = Math.round(t.delka);
      }
      onPresunRef.current?.(t.u, zmena);
    }

    function move(e) {
      const t = tazeniRef.current;
      if (!t) return;
      // Pojistka: když už není stisknuté tlačítko, `pointerup` nám utekl.
      // Bez tohohle by dlaždice zůstala „chycená" a jezdila za myší.
      if (e.pointerType === "mouse" && e.buttons === 0) {
        ukonci(true);
        return;
      }
      const nyni = miraKurzoru(e);
      if (!nyni) return;
      const deltaMin = nyni.minuty - t.startMin;
      const deltaDen = nyni.denIdx - t.startDenIdx;
      t.posunuto = t.posunuto || Math.abs(deltaMin) >= KROK_MIN / 2 || deltaDen !== 0;

      const nove = zTazeni(t.rezim, t.puvodOd, t.puvodDelka, deltaMin);
      if (t.rezim === "presun") {
        t.denIdx = Math.max(0, Math.min(6, t.puvodDenIdx + deltaDen));
        if (!t.celyDen) {
          t.od = nove.od;
          t.delka = nove.delka;
        }
      } else {
        t.od = nove.od;
        t.delka = nove.delka;
      }
      setNahled({
        id: t.u.id,
        denIdx: t.denIdx,
        od: t.od,
        delka: t.delka,
        celyDen: t.celyDen,
        vicedenni: t.vicedenni,
        dniDelka: t.dniDelka,
        posunuto: t.posunuto,
      });
    }

    function up() {
      ukonci(true);
    }
    function zrus() {
      ukonci(false);
    }
    function klavesa(e) {
      if (e.key === "Escape") zrus();
    }

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", zrus);
    // Přepnutí okna nebo karty tažení ukončí — jinak by po návratu pokračovalo.
    window.addEventListener("blur", zrus);
    window.addEventListener("keydown", klavesa);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", zrus);
      window.removeEventListener("blur", zrus);
      window.removeEventListener("keydown", klavesa);
    };
  }, [tahnu, miraKurzoru]);

  /** Vícedenní pruh: od kterého do kterého sloupce týdne se táhne. */
  function rozsahPruhu(u) {
    const prvni = isoDen(pondeli);
    const posledni = isoDen(dny[6]);
    const od = (u.termin || "").slice(0, 10);
    const do_ = (u.konec || u.termin || "").slice(0, 10);
    const odIdx = od < prvni ? 0 : dny.findIndex((d) => isoDen(d) === od);
    const doIdx = do_ > posledni ? 6 : dny.findIndex((d) => isoDen(d) === do_);
    const bezpecnyOd = Math.max(odIdx, 0);
    return {
      od: bezpecnyOd,
      do: Math.max(doIdx, bezpecnyOd),
      pretekaVlevo: od < prvni,
      pretekaVpravo: do_ > posledni,
    };
  }

  /** Klik na dlaždici — ale ne ten, který právě dokončil tažení. */
  function klikNaUdalost(u, kotva) {
    // Klik krátce po tažení (nebo po otevření detailu z `pointerup`) se zahodí.
    if (Date.now() < potlacitKlikDoRef.current) return;
    onUdalost?.(u, kotva);
  }

  const lzeTahnout = Boolean(onPresun);
  // Duch se kreslí jen když se opravdu posunulo — jinak by při každém dotyku
  // dlaždice bliknul náhled na tomtéž místě.
  const duchAktivni = nahled?.posunuto ? nahled : null;

  return (
    <div className={`kal-tyden${tahnu ? " tahne-se" : ""}`}>
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
            const n = duchAktivni?.id === u.id ? duchAktivni : null;
            const r = n
              ? {
                  od: n.denIdx,
                  do: Math.min(6, n.denIdx + (n.dniDelka || 0)),
                  pretekaVlevo: false,
                  pretekaVpravo: n.denIdx + (n.dniDelka || 0) > 6,
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
                  barvy={barvy}
                  kratka
                  lzeTahnout={lzeTahnout && u.muze_detail}
                  onZacniTazeni={zacniTazeni}
                  onKlik={klikNaUdalost}
                  styl={{
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

        {dny.map((d, denIdx) => {
          const iso = isoDen(d);
          const seznam = vMrizce.get(iso) || [];
          const vrstva = vrstvy.get(iso);
          // Duch se kreslí v CÍLOVÉM dni; originál zůstává na svém místě
          // ztlumený. Přesouvat originál mezi sloupci by ho odmountovalo.
          const duchTady =
            duchAktivni && !duchAktivni.celyDen && duchAktivni.denIdx === denIdx
              ? duchAktivni
              : null;
          const duchUdalost = duchTady
            ? (udalosti || []).find((x) => x.id === duchTady.id)
            : null;

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
              {/* Zúžená pásma mají jiné pozadí — ať je vidět, že měřítko je jiné. */}
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
                const delka = Math.max(u.delka_min || 30, MIN_DELKA);
                const top = yZMinut(od);
                const vyska = Math.max(yZMinut(od + delka) - top, 16);
                const v = vrstva?.get(u.id) || { sloupec: 0, sloupcu: 1 };
                const sirka = 100 / v.sloupcu;
                return (
                  <Dlazdice
                    key={u.id}
                    u={u}
                    barvy={barvy}
                    lzeTahnout={lzeTahnout && u.muze_detail}
                    ztlumena={duchAktivni?.id === u.id}
                    onZacniTazeni={zacniTazeni}
                    onKlik={klikNaUdalost}
                    kratka={vyska < 30}
                    styl={{
                      top,
                      height: vyska,
                      left: `calc(${v.sloupec * sirka}% + 2px)`,
                      width: `calc(${sirka}% - 4px)`,
                    }}
                  />
                );
              })}

              {duchUdalost && (
                <Dlazdice
                  u={duchUdalost}
                  barvy={barvy}
                  duch
                  casNahledu={naCas(duchTady.od)}
                  kratka={yZMinut(duchTady.od + duchTady.delka) - yZMinut(duchTady.od) < 30}
                  styl={{
                    top: yZMinut(duchTady.od),
                    height: Math.max(
                      yZMinut(duchTady.od + duchTady.delka) - yZMinut(duchTady.od),
                      16
                    ),
                    left: "2px",
                    width: "calc(100% - 4px)",
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
