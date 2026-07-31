// Mozek editoru nabídky: stav dokumentu, výběr, tažení, klávesové zkratky.
//
// Všechno na jednom místě, aby paleta, papír i panel vlastností sahaly na
// stejnou logiku a nemusely si posílat tucet propů. Stránka si hook vytvoří
// a rozdá ho komponentám přes kontext (`KontextEditoru`).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useHistorie } from "./historie";
import {
  DO_KONTEJNERU_NELZE,
  duplikujPrvek,
  duplikujStranku as duplikujStrankuModel,
  najdi,
  novyPrvek,
  pridejStranku as pridejStrankuModel,
  presun,
  presunNaStranku as presunNaStrankuModel,
  presunStranku as presunStrankuModel,
  polozNaStranku,
  smazPrvek,
  smazStranku as smazStrankuModel,
  upravPrvek,
  upravStyl as upravStylModel,
  vlozDoKontejneru,
  zaokrouhli,
  zkontroluj,
  zmenVrstvu,
} from "./model";
import {
  bodVMm,
  cilPodUkazatelem,
  kandidatiSnapu,
  posunKlavesou,
  prichyt,
  pxNaMm,
  vyhodnotPusteni,
  zmenVelikost,
} from "./tazeni";

// Než se tažení „chytne“, musí ukazatel ujet aspoň tolik pixelů. Bez toho by
// každé kliknutí na prvek bylo mikroskopické přetažení o půl milimetru.
const PRAH_TAZENI_PX = 4;

export function useEditorVystupu({ pocatecni, onZmenaStavu }) {
  const historie = useHistorie(pocatecni);
  const konfigurace = historie.stav;

  const [vybranyId, setVybranyId] = useState(null);
  const [editovanyId, setEditovanyId] = useState(null); // prvek v režimu psaní
  const [mrizkaZapnuta, setMrizkaZapnuta] = useState(true);
  const [tazeni, setTazeni] = useState(null); // { rezim, prvekId, linky, cil }

  // Rychlá data tažení – mění se při každém pohybu myši, překreslovat kvůli
  // nim celý editor by bylo zbytečné.
  const stopa = useRef(null);
  // Aktuální hodnoty pro obsluhu událostí. Posluchače tažení se registrují
  // jednou za život komponenty – kdyby v závislostech visela historie nebo
  // konfigurace, odpojovaly a připojovaly by se při každém pohybu myší.
  const konfiguraceRef = useRef(konfigurace);
  konfiguraceRef.current = konfigurace;
  const historieRef = useRef(historie);
  historieRef.current = historie;
  const mrizkaRef = useRef(mrizkaZapnuta);
  mrizkaRef.current = mrizkaZapnuta;

  // ---- ohlašování změn ven (příznak „neuloženo") ----
  // Ne každá změna konfigurace je úprava uživatele: naměřené výšky prvků se
  // do modelu zapisují taky, a kdyby se hlásily, dokument by byl „neuložený"
  // hned po otevření, aniž by se na něj kdokoli sáhl.
  const prvniBeh = useRef(true);
  const tichaZmena = useRef(false);
  useEffect(() => {
    if (prvniBeh.current) {
      prvniBeh.current = false;
      return;
    }
    if (tichaZmena.current) {
      tichaZmena.current = false;
      return;
    }
    if (onZmenaStavu) onZmenaStavu(konfigurace);
  }, [konfigurace, onZmenaStavu]);

  // ---- základní operace ----
  const uprav = useCallback(
    (id, zmena, volby) => historie.nastav((k) => upravPrvek(k, id, zmena), volby),
    [historie]
  );

  const upravStyl = useCallback(
    (id, zmena, volby) => historie.nastav((k) => upravStylModel(k, id, zmena), volby),
    [historie]
  );

  const smaz = useCallback(
    (id) => {
      historie.nastav((k) => smazPrvek(k, id));
      setVybranyId((v) => (v === id ? null : v));
      setEditovanyId((e) => (e === id ? null : e));
    },
    [historie]
  );

  const duplikuj = useCallback(
    (id) => {
      let noveId = null;
      historie.nastav((k) => {
        const [nova, vzniklo] = duplikujPrvek(k, id);
        noveId = vzniklo;
        return nova;
      });
      if (noveId) setVybranyId(noveId);
    },
    [historie]
  );

  const vrstva = useCallback(
    (id, smer) => historie.nastav((k) => zmenVrstvu(k, id, smer)),
    [historie]
  );

  const presunNaStranku = useCallback(
    (id, smer) => historie.nastav((k) => presunNaStrankuModel(k, id, smer)),
    [historie]
  );

  // ---- stránky ----
  const pridejStranku = useCallback(
    (zaIndexem) => historie.nastav((k) => pridejStrankuModel(k, zaIndexem)),
    [historie]
  );
  const smazStranku = useCallback(
    (strankaId) => historie.nastav((k) => smazStrankuModel(k, strankaId)),
    [historie]
  );
  const duplikujStranku = useCallback(
    (strankaId) => historie.nastav((k) => duplikujStrankuModel(k, strankaId)),
    [historie]
  );
  const presunStranku = useCallback(
    (strankaId, smer) => historie.nastav((k) => presunStrankuModel(k, strankaId, smer)),
    [historie]
  );

  const upravDokument = useCallback(
    (zmena) => historie.nastav((k) => ({ ...k, ...zmena })),
    [historie]
  );

  // ---- naměřená výška prvků s automatickou výškou ----
  // Výšku textu a kontejneru zná až prohlížeč. Ukládáme ji do modelu, aby se
  // dalo poznat přetečení a aby snap mířil na skutečné hrany. Zapisuje se
  // bez zápisu do historie – není to úprava uživatele.
  const nahlasVysku = useCallback(
    (id, vyskaMm) => {
      const k = konfiguraceRef.current;
      const nalez = najdi(k, id);
      if (!nalez || !nalez.prvek.auto_vyska) return;
      if (Math.abs((nalez.prvek.vyska || 0) - vyskaMm) < 0.5) return;
      tichaZmena.current = true;
      historie.nahrad(upravPrvek(k, id, { vyska: zaokrouhli(vyskaMm) }), {
        vymazHistorii: false,
      });
    },
    [historie]
  );

  // ---- tažení -------------------------------------------------------------

  /** Začátek tažení prvku, který na papíře už leží. */
  const zacniPresun = useCallback(
    (udalost, prvekId, elementStranky) => {
      const nalez = najdi(konfiguraceRef.current, prvekId);
      if (!nalez || nalez.prvek.zamceno) return;
      udalost.preventDefault();
      stopa.current = {
        rezim: "presun",
        prvekId,
        // Prvek v kontejneru se tahá jako celek: bere se rovnou ven a od
        // začátku se chová jako volný, ať ho jde pustit kamkoli.
        zRodice: nalez.rodic?.id || null,
        puvodni: { ...nalez.prvek },
        strankaId: nalez.stranka.id,
        startX: udalost.clientX,
        startY: udalost.clientY,
        elementStranky,
        chyceno: false,
      };
      setVybranyId(prvekId);
    },
    []
  );

  /** Začátek tažení nového prvku z palety. */
  const zacniZPalety = useCallback((udalost, druh, vlastnosti = {}) => {
    udalost.preventDefault();
    const prvek = novyPrvek(druh, vlastnosti);
    stopa.current = {
      rezim: "novy",
      prvek,
      startX: udalost.clientX,
      startY: udalost.clientY,
      chyceno: false,
    };
    setTazeni({ rezim: "novy", druh, linky: [], nahled: null });
  }, []);

  /** Začátek změny velikosti za úchyt. */
  const zacniVelikost = useCallback((udalost, prvekId, uchop, elementStranky) => {
    const nalez = najdi(konfiguraceRef.current, prvekId);
    if (!nalez || nalez.prvek.zamceno) return;
    udalost.preventDefault();
    udalost.stopPropagation();
    stopa.current = {
      rezim: "velikost",
      prvekId,
      uchop,
      puvodni: { ...nalez.prvek },
      strankaId: nalez.stranka.id,
      startX: udalost.clientX,
      startY: udalost.clientY,
      elementStranky,
      chyceno: true, // úchyt se chytá hned, žádný práh
    };
    setVybranyId(prvekId);
  }, []);

  // Posluchače pohybu a puštění visí na okně, ne na prvku – prst i myš běžně
  // vyjedou mimo a tažení nesmí uváznout v půli.
  useEffect(() => {
    function pohyb(udalost) {
      const s = stopa.current;
      if (!s) return;
      const dxPx = udalost.clientX - s.startX;
      const dyPx = udalost.clientY - s.startY;
      if (!s.chyceno) {
        if (Math.hypot(dxPx, dyPx) < PRAH_TAZENI_PX) return;
        s.chyceno = true;
      }

      const k = konfiguraceRef.current;

      if (s.rezim === "novy") {
        const cil = cilPodUkazatelem(udalost, null);
        let nahled = null;
        if (cil?.typ === "stranka") {
          const el = cil.element;
          const bod = bodVMm(udalost, el);
          const stranka = k.stranky.find((x) => x.id === cil.strankaId);
          const p = prichyt(
            bod.x - s.prvek.sirka / 2,
            bod.y - s.prvek.vyska / 2,
            s.prvek.sirka,
            s.prvek.vyska,
            kandidatiSnapu(stranka, null),
            mrizkaRef.current
          );
          nahled = { strankaId: cil.strankaId, ...p, sirka: s.prvek.sirka, vyska: s.prvek.vyska };
          s.cil = { typ: "stranka", strankaId: cil.strankaId, x: p.x, y: p.y };
          setTazeni({ rezim: "novy", druh: s.prvek.druh, linky: p.linky, nahled, cil: s.cil });
          return;
        }
        if (cil?.typ === "kontejner" && !DO_KONTEJNERU_NELZE.has(s.prvek.druh)) {
          s.cil = { typ: "kontejner", kontejnerId: cil.kontejnerId, index: cil.index };
          setTazeni({ rezim: "novy", druh: s.prvek.druh, linky: [], cil: s.cil });
          return;
        }
        s.cil = null;
        setTazeni({ rezim: "novy", druh: s.prvek.druh, linky: [], cil: null });
        return;
      }

      const pomer = pxNaMm(s.elementStranky);
      const dx = dxPx / pomer;
      const dy = dyPx / pomer;

      if (s.rezim === "velikost") {
        const stranka = k.stranky.find((x) => x.id === s.strankaId);
        const novy = zmenVelikost(
          s.puvodni,
          s.uchop,
          dx,
          dy,
          kandidatiSnapu(stranka, s.prvekId),
          mrizkaRef.current
        );
        // Ruční změna výšky vypne automatiku – uživatel si výšku určil sám.
        const meniVysku = s.uchop.includes("s") || s.uchop.includes("j");
        historieRef.current.nastav(
          (kk) =>
            upravPrvek(kk, s.prvekId, {
              x: novy.x,
              y: novy.y,
              sirka: novy.sirka,
              vyska: novy.vyska,
              ...(meniVysku ? { auto_vyska: false } : {}),
            }),
          { slouc: `velikost:${s.prvekId}` }
        );
        setTazeni({ rezim: "velikost", prvekId: s.prvekId, linky: novy.linky });
        return;
      }

      // rezim === "presun"
      const cil = cilPodUkazatelem(udalost, s.prvekId);
      if (cil?.typ === "kontejner" && !DO_KONTEJNERU_NELZE.has(s.puvodni.druh)) {
        s.cil = { typ: "kontejner", kontejnerId: cil.kontejnerId, index: cil.index };
        setTazeni({ rezim: "presun", prvekId: s.prvekId, linky: [], cil: s.cil });
        return;
      }

      const strankaId = cil?.typ === "stranka" ? cil.strankaId : s.strankaId;
      const element = cil?.element || s.elementStranky;
      const stranka = k.stranky.find((x) => x.id === strankaId);
      // Prvek vytažený z kontejneru nemá vlastní x/y – položí se pod ukazatel.
      let cilX;
      let cilY;
      if (s.zRodice) {
        const bod = bodVMm(udalost, element);
        cilX = bod.x - s.puvodni.sirka / 2;
        cilY = bod.y - s.puvodni.vyska / 2;
      } else {
        cilX = s.puvodni.x + dx;
        cilY = s.puvodni.y + dy;
      }
      const p = prichyt(
        cilX,
        cilY,
        s.puvodni.sirka,
        s.puvodni.vyska,
        kandidatiSnapu(stranka, s.prvekId),
        mrizkaRef.current
      );
      s.cil = { typ: "stranka", strankaId, x: p.x, y: p.y };

      // Dokud se prvek nepřestěhoval na jinou stránku ani ven z kontejneru,
      // stačí posouvat souřadnice – vypadá to plynule a nemíchá se pořadí.
      if (!s.zRodice && strankaId === s.strankaId) {
        historieRef.current.nastav((kk) => upravPrvek(kk, s.prvekId, { x: p.x, y: p.y }), {
          slouc: `presun:${s.prvekId}`,
        });
      }
      setTazeni({
        rezim: "presun",
        prvekId: s.prvekId,
        linky: p.linky,
        cil: s.cil,
        nahled:
          s.zRodice || strankaId !== s.strankaId
            ? { strankaId, x: p.x, y: p.y, sirka: s.puvodni.sirka, vyska: s.puvodni.vyska }
            : null,
      });
    }

    function pusteni(udalost) {
      const s = stopa.current;
      stopa.current = null;
      setTazeni(null);
      if (!s) return;
      if (!s.chyceno) return; // bylo to jen kliknutí

      if (s.rezim === "novy") {
        const cil = s.cil || vyhodnotPusteni(cilPodUkazatelem(udalost, null), { x: 0, y: 0 }, s.prvek);
        if (!cil) return;
        if (cil.typ === "kontejner") {
          historieRef.current.nastav((k) => vlozDoKontejneru(k, cil.kontejnerId, s.prvek, cil.index));
        } else {
          historieRef.current.nastav((k) => polozNaStranku(k, cil.strankaId, s.prvek, cil.x, cil.y));
        }
        setVybranyId(s.prvek.id);
        // Čerstvě položený text rovnou otevřeme k psaní – jinak by uživatel
        // musel hádat, že se do něj kliká dvakrát.
        if (s.prvek.druh === "text") setEditovanyId(s.prvek.id);
        historieRef.current.uzavriKrok();
        return;
      }

      if (s.rezim === "presun" && s.cil) {
        const meniRodice = s.zRodice || s.cil.typ === "kontejner";
        const meniStranku = s.cil.typ === "stranka" && s.cil.strankaId !== s.strankaId;
        if (meniRodice || meniStranku) {
          historieRef.current.nastav((k) => presun(k, s.prvekId, s.cil));
        }
      }
      historieRef.current.uzavriKrok();
    }

    function zrusenoKlavesou(udalost) {
      // Escape uprostřed tažení vrátí prvek tam, kde byl.
      if (udalost.key !== "Escape" || !stopa.current) return;
      const s = stopa.current;
      stopa.current = null;
      setTazeni(null);
      if (s.rezim === "presun" || s.rezim === "velikost") {
        historieRef.current.nastav((k) =>
          upravPrvek(k, s.prvekId, {
            x: s.puvodni.x,
            y: s.puvodni.y,
            sirka: s.puvodni.sirka,
            vyska: s.puvodni.vyska,
            auto_vyska: s.puvodni.auto_vyska,
          })
        );
        historieRef.current.uzavriKrok();
      }
    }

    window.addEventListener("pointermove", pohyb);
    window.addEventListener("pointerup", pusteni);
    window.addEventListener("pointercancel", pusteni);
    window.addEventListener("keydown", zrusenoKlavesou);
    return () => {
      window.removeEventListener("pointermove", pohyb);
      window.removeEventListener("pointerup", pusteni);
      window.removeEventListener("pointercancel", pusteni);
      window.removeEventListener("keydown", zrusenoKlavesou);
    };
  }, []);

  // ---- klávesové zkratky ----------------------------------------------------
  useEffect(() => {
    function klavesa(udalost) {
      // V textovém poli patří klávesy textu, ne editoru.
      const cil = udalost.target;
      const pise =
        cil?.isContentEditable ||
        ["INPUT", "TEXTAREA", "SELECT"].includes(cil?.tagName);

      const ctrl = udalost.ctrlKey || udalost.metaKey;
      if (ctrl && udalost.key.toLowerCase() === "z" && !udalost.shiftKey) {
        if (pise) return;
        udalost.preventDefault();
        historie.zpet();
        return;
      }
      if (ctrl && (udalost.key.toLowerCase() === "y" ||
          (udalost.key.toLowerCase() === "z" && udalost.shiftKey))) {
        if (pise) return;
        udalost.preventDefault();
        historie.vpred();
        return;
      }

      if (pise || !vybranyId) return;

      if (ctrl && udalost.key.toLowerCase() === "d") {
        udalost.preventDefault();
        duplikuj(vybranyId);
        return;
      }
      if (udalost.key === "Delete" || udalost.key === "Backspace") {
        udalost.preventDefault();
        smaz(vybranyId);
        return;
      }
      if (udalost.key === "Escape") {
        setVybranyId(null);
        return;
      }
      const posun = posunKlavesou(udalost.key, udalost.shiftKey);
      if (posun) {
        const nalez = najdi(konfiguraceRef.current, vybranyId);
        if (!nalez || nalez.rodic || nalez.prvek.zamceno) return;
        udalost.preventDefault();
        uprav(
          vybranyId,
          {
            x: zaokrouhli(nalez.prvek.x + posun.dx),
            y: zaokrouhli(nalez.prvek.y + posun.dy),
          },
          { slouc: `klavesy:${vybranyId}` }
        );
      }
    }
    window.addEventListener("keydown", klavesa);
    return () => window.removeEventListener("keydown", klavesa);
  }, [historie, vybranyId, duplikuj, smaz, uprav]);

  const vybrany = useMemo(() => najdi(konfigurace, vybranyId), [konfigurace, vybranyId]);
  const problemy = useMemo(() => zkontroluj(konfigurace), [konfigurace]);

  return {
    konfigurace,
    nahradKonfiguraci: historie.nahrad,
    vybranyId,
    vybrany: vybrany?.prvek || null,
    vybranyRodic: vybrany?.rodic || null,
    vyber: setVybranyId,
    editovanyId,
    otevriPsani: setEditovanyId,
    mrizkaZapnuta,
    prepniMrizku: () => setMrizkaZapnuta((m) => !m),
    tazeni,
    problemy,

    uprav,
    upravStyl,
    upravDokument,
    smaz,
    duplikuj,
    vrstva,
    presunNaStranku,
    nahlasVysku,

    pridejStranku,
    smazStranku,
    duplikujStranku,
    presunStranku,

    zacniPresun,
    zacniZPalety,
    zacniVelikost,

    zpet: historie.zpet,
    vpred: historie.vpred,
    muzeZpet: historie.muzeZpet,
    muzeVpred: historie.muzeVpred,
    uzavriKrok: historie.uzavriKrok,
  };
}
