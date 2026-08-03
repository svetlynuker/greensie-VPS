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
  geometrie,
  hm,
  minutyZCasu,
  naCas,
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
 * Zploštělá dlaždice se ale nedá přečíst a do 26px pásu se nedá mířit myší,
 * takže do noční ani večerní hodiny nešlo nic zapsat. Každý pás se proto dá
 * ROZBALIT na plné hodiny (klikem na pás v ose nebo v ploše dne) a zůstane
 * rozbalený — volba se ukládá do profilu jako ostatní volby zobrazení.
 * Geometrie osy proto přichází z `geometrie()`, ne z konstant.
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
 * Vrací pro každou událost `{ sloupec, sloupcu, rozsah }` — bez toho by dvě
 * schůzky na stejnou hodinu ležely přesně na sobě a na spodní by nešlo kliknout.
 *
 * Dvě věci, které naivní verze dělala špatně a Dan si toho všiml:
 *
 *  1. Počet sloupců se počítá zvlášť pro každý SHLUK (řetězec navazujících
 *     souběhů), ne pro celý den. Dřív stačila jedna dvojice schůzek v úterý
 *     dopoledne a všechny ostatní aktivity toho dne — včetně osamocené
 *     odpolední — zůstaly na poloviční šířku, i když je nic neblokovalo.
 *  2. Uvnitř shluku se dlaždice ještě ROZTÁHNE doprava přes sloupce, ve
 *     kterých v jejím čase nikdo není. Souběh 10:30 + 11:00 tak sedí vedle
 *     sebe, ale schůzka v 15:00 zabere celou šířku dne.
 */
function rozvrstvi(seznam) {
  const items = seznam
    .map((u) => {
      const od = minutyZCasu(u.zacatek);
      return { u, od, do: od + Math.max(u.delka_min || 30, MIN_DELKA) };
    })
    // Sekundárně podle delší doby trvání: dlouhá schůzka pak drží levý sloupec
    // a krátké se řadí vedle ní, ne naopak.
    .sort((a, b) => a.od - b.od || b.do - a.do);

  const mapa = new Map();
  let shluk = [];
  let konecShluku = -1;

  function uzavriShluk() {
    if (!shluk.length) return;
    // Greedy přiřazení sloupců v rámci shluku.
    const konce = []; // konec poslední události v každém sloupci
    for (const it of shluk) {
      let sloupec = konce.findIndex((k) => k <= it.od);
      if (sloupec === -1) {
        sloupec = konce.length;
        konce.push(it.do);
      } else {
        konce[sloupec] = it.do;
      }
      it.sloupec = sloupec;
    }
    const sloupcu = Math.max(konce.length, 1);
    // Roztažení doprava, dokud v dalším sloupci nic nekoliduje.
    for (const it of shluk) {
      let rozsah = 1;
      for (let s = it.sloupec + 1; s < sloupcu; s++) {
        const obsazeno = shluk.some((x) => x.sloupec === s && x.od < it.do && x.do > it.od);
        if (obsazeno) break;
        rozsah += 1;
      }
      mapa.set(it.u.id, { sloupec: it.sloupec, sloupcu, rozsah });
    }
    shluk = [];
    konecShluku = -1;
  }

  for (const it of items) {
    // Začíná až po konci všeho v shluku → nový shluk, počítá se od jednoho sloupce.
    if (shluk.length && it.od >= konecShluku) uzavriShluk();
    shluk.push(it);
    konecShluku = Math.max(konecShluku, it.do);
  }
  uzavriShluk();
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
  // Kolik dní mřížka kreslí. 7 = týden, 1 = denní pohled. Denní pohled je
  // schválně TATÁŽ komponenta: kdyby byl vlastní, měl by druhou kopii
  // pozicování, tažení i vrstvení souběhů — a ty by se rozešly.
  pocetDnu = 7,
  // Rozbalení krajních pásem: {noc, vecer}. Drží to nadřazená stránka, aby se
  // volba dala uložit do profilu (a nezmizela při přepnutí den/týden).
  pasma,
  onPasma,
}) {
  const dnesIso = isoDen(new Date());
  const g = useMemo(
    () => geometrie(Boolean(pasma?.noc), Boolean(pasma?.vecer)),
    [pasma?.noc, pasma?.vecer]
  );
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
    () => Array.from({ length: pocetDnu }, (_, i) => posunDnu(pondeli, i)),
    [pondeli, pocetDnu]
  );
  const dnyRef = useRef(dny);
  dnyRef.current = dny;

  // Pracovní hodiny s plnou výškou (osa i vodorovné linky).
  const hodiny = useMemo(
    () => Array.from({ length: PRAC_DO - PRAC_OD }, (_, i) => PRAC_OD + i),
    []
  );
  const hodinyNoci = useMemo(() => Array.from({ length: PRAC_OD }, (_, i) => i), []);
  const hodinyVecera = useMemo(
    () => Array.from({ length: 24 - PRAC_DO }, (_, i) => PRAC_DO + i),
    []
  );
  // Do kterých hodin se dá kliknout a založit aktivitu. Rozbalený pás se chová
  // stejně jako pracovní část — o to při rozbalení jde.
  const hodinySlotu = useMemo(
    () => [
      ...(g.nocRozbalena ? hodinyNoci : []),
      ...hodiny,
      ...(g.vecerRozbalena ? hodinyVecera : []),
    ],
    [g.nocRozbalena, g.vecerRozbalena, hodiny, hodinyNoci, hodinyVecera]
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

  function prepniPasmo(ktere) {
    onPasma?.({
      noc: Boolean(pasma?.noc),
      vecer: Boolean(pasma?.vecer),
      [ktere]: !pasma?.[ktere],
    });
  }

  // Kolik aktivit padá do složených pásem — ve složeném stavu je počet u popisky
  // jediné, z čeho je poznat, že tam vůbec něco je.
  const vPasmech = useMemo(() => {
    let noc = 0;
    let vecer = 0;
    for (const seznam of vMrizce.values()) {
      for (const u of seznam) {
        const od = minutyZCasu(u.zacatek);
        if (od < PRAC_OD * 60) noc += 1;
        else if (od >= PRAC_DO * 60) vecer += 1;
      }
    }
    return { noc, vecer };
  }, [vMrizce]);

  /** Z pozice kurzoru spočítá, nad kterým dnem a v které minutě je. */
  const miraKurzoru = useCallback(
    (e) => {
    const mrizka = refMrizka.current?.getBoundingClientRect();
    const osa = refOsa.current?.getBoundingClientRect();
    if (!mrizka || !osa) return null;
    const sirkaDne = (mrizka.width - osa.width) / pocetDnu;
    if (!(sirkaDne > 0)) return null;
    const idx = Math.floor((e.clientX - mrizka.left - osa.width) / sirkaDne);
    return {
      denIdx: Math.max(0, Math.min(pocetDnu - 1, idx)),
        minuty: g.minutyZY(e.clientY - mrizka.top),
      };
    },
    [pocetDnu, g]
  );

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
        t.denIdx = Math.max(0, Math.min(dnyRef.current.length - 1, t.puvodDenIdx + deltaDen));
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
    const posledni = isoDen(dny[dny.length - 1]);
    const od = (u.termin || "").slice(0, 10);
    const do_ = (u.konec || u.termin || "").slice(0, 10);
    const odIdx = od < prvni ? 0 : dny.findIndex((d) => isoDen(d) === od);
    const doIdx = do_ > posledni ? dny.length - 1 : dny.findIndex((d) => isoDen(d) === do_);
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

  // Počet sloupců řídí CSS proměnná, ne pevná trojice pravidel — týden i den
  // tak používají stejnou mřížku. `--kal-noc` posouvá fázi hodinových linek,
  // aby sedly na hodiny i po rozbalení noci.
  const styleMrizky = { "--kal-dnu": pocetDnu, "--kal-noc": `${g.pxNoc}px` };

  return (
    <div className={`kal-tyden${tahnu ? " tahne-se" : ""}`} style={styleMrizky}>
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
                  do: Math.min(dny.length - 1, n.denIdx + (n.dniDelka || 0)),
                  pretekaVlevo: false,
                  pretekaVpravo: n.denIdx + (n.dniDelka || 0) > dny.length - 1,
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
      <div className="kal-mrizka" style={{ height: g.vyska }} ref={refMrizka}>
        <div className="kal-osa" ref={refOsa}>
          {g.nocRozbalena ? (
            <>
              {hodinyNoci.map((h) => (
                <div key={h} className="kal-osa-hodina mimopracovni" style={{ height: PX_HODINA }}>
                  <span>{h}:00</span>
                </div>
              ))}
              <button
                className="kal-osa-sbal horni"
                onClick={() => prepniPasmo("noc")}
                title="Sbalit noční hodiny (0:00–7:00)"
                aria-label="Sbalit noční hodiny"
                aria-expanded="true"
              >
                <span className="kal-osa-sipka">▴</span>
                <span className="kal-osa-pas-popis">0–7</span>
              </button>
            </>
          ) : (
            <button
              className="kal-osa-pas rozbalovaci"
              style={{ height: g.pxNoc }}
              onClick={() => prepniPasmo("noc")}
              title={`Rozbalit noční hodiny 0:00–7:00${
                vPasmech.noc ? ` — je v nich ${vPasmech.noc} aktivit(a)` : " (teď v nich nic není)"
              }`}
              aria-expanded="false"
            >
              <span className="kal-osa-sipka">▾</span>
              <span className="kal-osa-pas-popis">
                0–7{vPasmech.noc ? ` · ${vPasmech.noc}` : ""}
              </span>
            </button>
          )}

          {hodiny.map((h) => (
            <div key={h} className="kal-osa-hodina" style={{ height: PX_HODINA }}>
              <span>{h}:00</span>
            </div>
          ))}

          {g.vecerRozbalena ? (
            <>
              {hodinyVecera.map((h) => (
                <div key={h} className="kal-osa-hodina mimopracovni" style={{ height: PX_HODINA }}>
                  <span>{h}:00</span>
                </div>
              ))}
              <button
                className="kal-osa-sbal dolni"
                onClick={() => prepniPasmo("vecer")}
                title="Sbalit večerní hodiny (19:00–24:00)"
                aria-label="Sbalit večerní hodiny"
                aria-expanded="true"
              >
                <span className="kal-osa-pas-popis">19–24</span>
                <span className="kal-osa-sipka">▾</span>
              </button>
            </>
          ) : (
            <button
              className="kal-osa-pas rozbalovaci"
              style={{ height: g.pxVecer }}
              onClick={() => prepniPasmo("vecer")}
              title={`Rozbalit večerní hodiny 19:00–24:00${
                vPasmech.vecer
                  ? ` — je v nich ${vPasmech.vecer} aktivit(a)`
                  : " (teď v nich nic není)"
              }`}
              aria-expanded="false"
            >
              <span className="kal-osa-sipka">▾</span>
              <span className="kal-osa-pas-popis">
                19–24{vPasmech.vecer ? ` · ${vPasmech.vecer}` : ""}
              </span>
            </button>
          )}
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
              {/* Mimopracovní pásma jsou jemně podbarvená — ať je vidět, že tam
                  den končí. Ve složeném stavu je pás zároveň tlačítko: klik ho
                  rozbalí, protože do 26px se nedá mířit myší. */}
              {g.nocRozbalena ? (
                <div className="kal-pas noc rozbaleny" style={{ height: g.pxNoc }} />
              ) : (
                <button
                  className="kal-pas noc"
                  style={{ height: g.pxNoc }}
                  onClick={() => prepniPasmo("noc")}
                  title="Rozbalit noční hodiny (0:00–7:00)"
                  aria-label="Rozbalit noční hodiny"
                />
              )}
              {g.vecerRozbalena ? (
                <div
                  className="kal-pas vecer rozbaleny"
                  style={{ top: g.yVecer, height: g.pxVecer }}
                />
              ) : (
                <button
                  className="kal-pas vecer"
                  style={{ top: g.yVecer, height: g.pxVecer }}
                  onClick={() => prepniPasmo("vecer")}
                  title="Rozbalit večerní hodiny (19:00–24:00)"
                  aria-label="Rozbalit večerní hodiny"
                />
              )}

              {/* Terče pro zakládání po půlhodinách. V rozbaleném pásmu taky —
                  jinak by rozbalení bylo k ničemu: šlo by koukat, ne zapisovat. */}
              {hodinySlotu.map((h) =>
                [0, 30].map((m) => (
                  <button
                    key={`${h}-${m}`}
                    className="kal-slot"
                    style={{ top: g.yZMinut(h * 60 + m), height: PX_HODINA / 2 }}
                    onClick={() => onPrazdno?.(iso, `${h}:${String(m).padStart(2, "0")}`)}
                    title={`Nová aktivita ${d.getDate()}.${d.getMonth() + 1}. v ${h}:${String(m).padStart(2, "0")}`}
                    aria-label={`Nová aktivita ${h}:${String(m).padStart(2, "0")}`}
                  />
                ))
              )}

              {seznam.map((u) => {
                const od = minutyZCasu(u.zacatek);
                const delka = Math.max(u.delka_min || 30, MIN_DELKA);
                const top = g.yZMinut(od);
                const vyska = Math.max(g.yZMinut(od + delka) - top, 16);
                const v = vrstva?.get(u.id) || { sloupec: 0, sloupcu: 1, rozsah: 1 };
                // Šířka = přidělený sloupec + volné sloupce vpravo (viz `rozvrstvi`).
                const sirka = (100 / v.sloupcu) * (v.rozsah || 1);
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
                      left: `calc(${v.sloupec * (100 / v.sloupcu)}% + 2px)`,
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
                  kratka={g.yZMinut(duchTady.od + duchTady.delka) - g.yZMinut(duchTady.od) < 30}
                  styl={{
                    top: g.yZMinut(duchTady.od),
                    height: Math.max(
                      g.yZMinut(duchTady.od + duchTady.delka) - g.yZMinut(duchTady.od),
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
