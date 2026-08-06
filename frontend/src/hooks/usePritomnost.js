import { useCallback, useEffect, useRef, useState } from "react";
import { odchodPritomnost, tikPritomnost } from "../api";

/**
 * „Kdo má tenhle záznam otevřený“ — přítomnost na entitě.
 *
 * Proč vůbec: dva lidé si otevřou stejnou nabídku, jeden přepíše druhému
 * hodnotu a nikdo neví, že se to stalo. Kolečka s iniciálami tomu předejdou
 * dřív, než se to stane — člověk sám zavolá, než začne psát do stejného pole.
 *
 * Proč dotaz za pár sekund, a ne websocket: osm lidí a krátká okna nad
 * záznamem. Jeden levný dotaz za 8 s je řádově méně práce (na serveru
 * i na údržbě) než držet spojení, a zpoždění do 8 s tady nikomu nevadí.
 * Když je záložka skrytá, neposílá se nic — appka nechaná otevřená přes noc
 * by jinak nasypala tisíce zbytečných dotazů a držela by uživatele „přítomného“
 * v záznamu, u kterého už dávno nesedí.
 *
 * @param {object} p
 * @param {string} p.entitaTyp   druh záznamu (např. „nabidka“, „projekt“)
 * @param {string|number} p.entitaId  id záznamu
 * @param {string} p.pole        klíč právě editovaného pole (nepovinné)
 * @param {number} p.intervalMs  jak často se ohlašovat
 * @param {boolean} p.zapnuto    false = nesleduje se vůbec
 * @returns {{pritomni: Array, razitko: any, chyba: string|null}}
 */
export function usePritomnost({
  entitaTyp,
  entitaId = "",
  pole = "",
  intervalMs = 8000,
  zapnuto = true,
}) {
  const [pritomni, setPritomni] = useState([]);
  const [razitko, setRazitko] = useState(null);
  const [chyba, setChyba] = useState(null);

  // Aktuální pole drží ref, ne dep pole efektu. Kdyby bylo `pole` v závislostech
  // intervalu, každé přeskočení mezi buňkami by interval zrušilo a založilo
  // znovu — při rychlém proklikávání by tik nikdy nedoběhl.
  const poleRef = useRef(pole);
  // Guard proti setState po odmontování.
  const zivyRef = useRef(false);
  // Aby se tiky nekupily, když server odpovídá pomaleji než interval.
  const beziRef = useRef(false);

  const aktivni = Boolean(zapnuto && entitaTyp);

  // Musí být první efekt v souboru: efekty běží v pořadí zápisu, takže
  // `zivyRef` je nastavený dřív, než níž položený efekt pošle první tik.
  useEffect(() => {
    zivyRef.current = true;
    return () => {
      zivyRef.current = false;
    };
  }, []);

  const tik = useCallback(async () => {
    if (!aktivni) return;
    if (document.hidden) return;
    if (beziRef.current) return;
    beziRef.current = true;
    try {
      const data = await tikPritomnost({
        entita_typ: entitaTyp,
        entita_id: String(entitaId ?? ""),
        pole: poleRef.current || "",
      });
      if (!zivyRef.current) return;
      setPritomni(Array.isArray(data?.pritomni) ? data.pritomni : []);
      setRazitko(data?.razitko ?? null);
      setChyba(null);
    } catch (e) {
      // Přítomnost je doplněk. Když spadne, nesmí to shodit stránku ani
      // zastavit další tikání — chybu jen podržíme a jede se dál.
      if (zivyRef.current) setChyba(e?.message || "Přítomnost se nepodařilo ohlásit");
    } finally {
      beziRef.current = false;
    }
  }, [aktivni, entitaTyp, entitaId]);

  // Tik hned po namontování a hned při každé změně editovaného pole — kolegové
  // musí vidět správný sloupec teď, ne až za 8 sekund.
  useEffect(() => {
    poleRef.current = pole || "";
    if (!aktivni) return;
    tik();
  }, [pole, aktivni, tik]);

  // Pravidelné ohlašování + okamžitý tik při návratu na záložku.
  useEffect(() => {
    if (!aktivni) {
      setPritomni([]);
      setRazitko(null);
      return undefined;
    }
    const t = setInterval(tik, Math.max(1000, intervalMs));
    document.addEventListener("visibilitychange", tik);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", tik);
    };
  }, [aktivni, intervalMs, tik]);

  // Odchod ohlásíme sami, ať kolečko zmizí okamžitě a ne až vyprší server.
  useEffect(() => {
    if (!aktivni) return undefined;
    return () => {
      odchodPritomnost({
        entita_typ: entitaTyp,
        entita_id: String(entitaId ?? ""),
      }).catch(() => {});
    };
  }, [aktivni, entitaTyp, entitaId]);

  return { pritomni: aktivni ? pritomni : [], razitko, chyba };
}

export default usePritomnost;
