// Undo/redo pro editor nabídky.
//
// Bez historie je editor s tažením myší nepoužitelný – jeden omyl a rozvržení
// je pryč. Ukládá se celá konfigurace (je to malý JSON), takže krok zpět je
// prosté přepnutí reference; žádné počítání rozdílů.
//
// Průběžné změny (tažení, psaní) se do historie SLUČUJÍ: jinak by jedno
// přetažení prvku přes papír nadělalo stovky kroků a Ctrl+Z by se prokousával
// pixel po pixelu. Slučuje se podle `klic` – dokud se nemění, přepisuje se
// poslední záznam; jakmile se změní (jiný prvek, jiná akce), založí se nový.

import { useCallback, useRef, useState } from "react";

const MAX_KROKU = 100;

export function useHistorie(pocatecni) {
  const [stav, setStav] = useState(pocatecni);
  // Historie žije v ref – překreslení kvůli ní nepotřebujeme, jen kvůli
  // příznakům `muzeZpet`/`muzeVpred`.
  const zpetne = useRef([]);
  const vpredne = useRef([]);
  const slucovaciKlic = useRef(null);
  const [priznaky, setPriznaky] = useState({ muzeZpet: false, muzeVpred: false });

  const obnovPriznaky = useCallback(() => {
    setPriznaky({
      muzeZpet: zpetne.current.length > 0,
      muzeVpred: vpredne.current.length > 0,
    });
  }, []);

  /**
   * Nastaví novou konfiguraci. `volby.slouc` je klíč slučování – volání se
   * stejným klíčem za sebou zaberou v historii jediné místo.
   */
  const nastav = useCallback(
    (novyNeboFn, volby = {}) => {
      setStav((puvodni) => {
        const novy =
          typeof novyNeboFn === "function" ? novyNeboFn(puvodni) : novyNeboFn;
        if (novy === puvodni) return puvodni;

        const slouc = volby.slouc || null;
        const pokracujeme = slouc !== null && slucovaciKlic.current === slouc;
        if (!pokracujeme) {
          zpetne.current = [...zpetne.current, puvodni].slice(-MAX_KROKU);
          vpredne.current = [];
        }
        slucovaciKlic.current = slouc;
        return novy;
      });
      obnovPriznaky();
    },
    [obnovPriznaky]
  );

  /** Ukončí slučování – další změna založí nový krok historie. */
  const uzavriKrok = useCallback(() => {
    slucovaciKlic.current = null;
  }, []);

  const zpet = useCallback(() => {
    setStav((puvodni) => {
      const historie = zpetne.current;
      if (!historie.length) return puvodni;
      const predchozi = historie[historie.length - 1];
      zpetne.current = historie.slice(0, -1);
      vpredne.current = [...vpredne.current, puvodni];
      slucovaciKlic.current = null;
      return predchozi;
    });
    obnovPriznaky();
  }, [obnovPriznaky]);

  const vpred = useCallback(() => {
    setStav((puvodni) => {
      const historie = vpredne.current;
      if (!historie.length) return puvodni;
      const dalsi = historie[historie.length - 1];
      vpredne.current = historie.slice(0, -1);
      zpetne.current = [...zpetne.current, puvodni];
      slucovaciKlic.current = null;
      return dalsi;
    });
    obnovPriznaky();
  }, [obnovPriznaky]);

  /** Nahradí stav bez zápisu do historie (načtení ze serveru, šablona). */
  const nahrad = useCallback(
    (novy, { vymazHistorii = true } = {}) => {
      if (vymazHistorii) {
        zpetne.current = [];
        vpredne.current = [];
      }
      slucovaciKlic.current = null;
      setStav(novy);
      obnovPriznaky();
    },
    [obnovPriznaky]
  );

  return {
    stav,
    nastav,
    nahrad,
    uzavriKrok,
    zpet,
    vpred,
    muzeZpet: priznaky.muzeZpet,
    muzeVpred: priznaky.muzeVpred,
  };
}
