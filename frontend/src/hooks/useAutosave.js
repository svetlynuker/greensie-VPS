import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Automatické ukládání vstupů (debounce po polích).
 *
 * Proč po klíčích, a ne jeden timer pro celý formulář: člověk vyplní termín,
 * hned skočí na poznámku a píše dál. S jedním timerem by psaní do poznámky
 * pořád odkládalo i uložení termínu a při zavření okna by se ztratilo obojí.
 * Každé pole má proto vlastní timer — nové psaní do poznámky zruší jen
 * čekající uložení poznámky.
 *
 * Souběh: pro tentýž klíč nikdy neletí dvě uložení naráz. Kdyby letěla,
 * server je může zapsat v opačném pořadí a ve buňce zůstane starší text.
 * Když ještě jedno běží, poslední hodnota čeká ve frontě a odejde hned po něm.
 *
 * @param {(klic: string, argument: any) => Promise<any>} ulozFn co uloží jedno pole
 * @param {{prodlevaMs?: number}} [nastaveni]
 * @returns {{stav: string, chyba: string|null, kdy: Date|null, naplanuj: Function,
 *            hned: Function, zrus: Function, ceka: boolean}}
 */
export function useAutosave(ulozFn, { prodlevaMs = 600 } = {}) {
  const [stav, setStav] = useState("necinny"); // „necinny“ | „uklada“ | „ulozeno“ | „chyba“
  const [chyba, setChyba] = useState(null);
  const [kdy, setKdy] = useState(null);
  const [ceka, setCeka] = useState(false);

  const timeryRef = useRef(new Map()); // klic -> id čekajícího timeru
  const beziciRef = useRef(new Map()); // klic -> uložení právě letí na server
  const frontaRef = useRef(new Map()); // klic -> hodnota, která pojede po doběhnutí
  const zivyRef = useRef(false); // guard proti setState po odmontování
  const ulozFnRef = useRef(ulozFn);

  // Musí být první efekt: efekty běží v pořadí zápisu, takže `zivyRef` je
  // nastavený dřív, než cokoliv níž může sáhnout na setState.
  useEffect(() => {
    zivyRef.current = true;
    const timery = timeryRef.current;
    return () => {
      zivyRef.current = false;
      // Uklidíme jen timery. Neuložená data si komponenta, která se zavírá,
      // musí poslat sama přes `hned` — tady už je pozdě něco dopisovat.
      timery.forEach((id) => clearTimeout(id));
      timery.clear();
    };
  }, []);

  // `ulozFn` bývá inline funkce z komponenty; přes ref se nemusí přepočítávat
  // celý hook (a hlavně se neztratí naplánované timery) při každém renderu.
  useEffect(() => {
    ulozFnRef.current = ulozFn;
  }, [ulozFn]);

  const prepocti = useCallback(() => {
    if (!zivyRef.current) return;
    setCeka(timeryRef.current.size > 0 || beziciRef.current.size > 0 || frontaRef.current.size > 0);
  }, []);

  // Pojmenovaný function expression — jméno `spust` je vidět zevnitř,
  // takže se dá zavolat rekurzivně pro hodnotu čekající ve frontě.
  const spust = useCallback(
    async function spust(klic, argument) {
      if (beziciRef.current.has(klic)) {
        frontaRef.current.set(klic, argument);
        prepocti();
        return;
      }
      beziciRef.current.set(klic, true);
      frontaRef.current.delete(klic);
      if (zivyRef.current) {
        setStav("uklada");
        setChyba(null);
      }
      prepocti();
      try {
        await ulozFnRef.current(klic, argument);
        if (zivyRef.current) {
          setStav("ulozeno");
          setChyba(null);
          setKdy(new Date());
        }
      } catch (e) {
        if (zivyRef.current) {
          setStav("chyba");
          setChyba(e?.message || "Uložení se nepovedlo");
        }
      } finally {
        beziciRef.current.delete(klic);
        if (frontaRef.current.has(klic)) {
          const dalsi = frontaRef.current.get(klic);
          frontaRef.current.delete(klic);
          prepocti();
          await spust(klic, dalsi);
        } else {
          prepocti();
        }
      }
    },
    [prepocti],
  );

  /** Naplánuje uložení jednoho pole; další psaní do téhož pole čekání resetuje. */
  const naplanuj = useCallback(
    (klic, argument) => {
      const stary = timeryRef.current.get(klic);
      if (stary) clearTimeout(stary);
      const id = setTimeout(() => {
        timeryRef.current.delete(klic);
        spust(klic, argument);
      }, prodlevaMs);
      timeryRef.current.set(klic, id);
      prepocti();
    },
    [prodlevaMs, spust, prepocti],
  );

  /**
   * Uloží okamžitě, bez prodlevy (odchod z pole, zavření okna, „Zkusit znovu“).
   * Vrací promise — komponenta, která se zavírá, si ho může odčekat.
   */
  const hned = useCallback(
    (klic, argument) => {
      const stary = timeryRef.current.get(klic);
      if (stary) {
        clearTimeout(stary);
        timeryRef.current.delete(klic);
      }
      return spust(klic, argument);
    },
    [spust],
  );

  /** Zruší všechna čekající uložení. Co ještě letí na server, doběhne. */
  const zrus = useCallback(() => {
    timeryRef.current.forEach((id) => clearTimeout(id));
    timeryRef.current.clear();
    prepocti();
  }, [prepocti]);

  return { stav, chyba, kdy, naplanuj, hned, zrus, ceka };
}

export default useAutosave;
