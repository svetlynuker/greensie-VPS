import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { patchPoleZaznamu } from "../api";
import { useAutosave } from "./useAutosave";
import { usePritomnost } from "./usePritomnost";

/**
 * Automatické ukládání celého formuláře záznamu — pole po poli.
 *
 * Zobecnění logiky z `BunkaDialog` na N polí. Tři pravidla, bez kterých by
 * automatické ukládání škodilo víc, než pomůže:
 *  1) pole, ve kterém člověk právě píše (nebo má nedoručenou změnu), se
 *     aktualizací ze serveru NIKDY nepřepíše — jinak by mu text mizel pod
 *     rukama uprostřed věty;
 *  2) posílá se `puvodni` = to, co server naposledy potvrdil. Když do pole
 *     mezitím zapsal někdo jiný, server vrátí 409 a nic se nepřepíše —
 *     člověk dostane na výběr, čí hodnota platí;
 *  3) odpověď serveru je pravda o ZBYTKU záznamu. Server si za klientovými
 *     zády dopočítává další pole (termíny navazujících kroků, cenu
 *     objednávky…), takže se z odpovědi přebírá všechno kromě polí, která má
 *     člověk pod rukama.
 *
 * `usazeno` je druhý půl obrázku: průběžné (debounce) ukládání jen zapisuje
 * hodnotu, teprve `usazeno: true` říká serveru „člověk to dopsal, spusť
 * automatizace“. Takový požadavek MUSÍ dorazit, proto ho hook posílá při
 * odchodu z pole (`onBlur`/`dokonci`) i při zavírání formuláře (`dokonci()`
 * bez argumentu) a hlídá si, u kterých polí ho ještě neposlal.
 *
 * @param {object} p
 * @param {string} p.entita     klíč pro API („zakaznik“ | „op“ | „obj“ | „pro“ |
 *                              „kontakt“ | „om“ | „nab“)
 * @param {string|number} p.id  id záznamu
 * @param {object} p.zaznam     aktuální data ze serveru (mění se, když si
 *                              stránka natáhne nová)
 * @param {string[]} p.pole     klíče, které hook spravuje; `extra:<k>` čte
 *                              hodnotu z `zaznam.extra[k]`
 * @param {string} [p.entitaTyp] klíč pro přítomnost (např. „crm_op“); když
 *                              chybí, přítomnost se nesleduje
 * @param {boolean} [p.zapnuto] false = hodnoty se drží, ale nic se neukládá
 * @returns {{hodnoty: object, zmen: Function, stav: string, chyba: string|null,
 *            kdy: Date|null, ceka: boolean, pritomni: Array, razitko: any,
 *            kolize: object|null, prepis: Function, vezmiJejich: Function,
 *            dokonci: Function, onFokus: Function, onBlur: Function,
 *            chybaHlaska: string|null}}
 */

/** Hodnoty držíme jako text — vstupy v prohlížeči jinak neumí. */
function naText(hodnota) {
  if (hodnota === null || hodnota === undefined) return "";
  // Zaškrtávátko: „1“ / „“ je pořád text, ale `Boolean(hodnota)` na druhé
  // straně vyjde správně. Kdyby se posílalo „false“, checkbox by se po
  // návratu ze serveru zaškrtnul (neprázdný text je pravda).
  if (typeof hodnota === "boolean") return hodnota ? "1" : "";
  return typeof hodnota === "string" ? hodnota : String(hodnota);
}

/** Vytáhne ze záznamu hodnotu jednoho spravovaného klíče. */
function zeZaznamu(zaznam, klic) {
  if (!zaznam) return "";
  if (klic.startsWith("extra:")) return naText(zaznam.extra?.[klic.slice(6)]);
  return naText(zaznam[klic]);
}

function vsechnyZeZaznamu(zaznam, klice) {
  const vysledek = {};
  klice.forEach((k) => {
    vysledek[k] = zeZaznamu(zaznam, k);
  });
  return vysledek;
}

export function useZaznamAutosave({ entita, id, zaznam, pole, entitaTyp, zapnuto = true }) {
  const [hodnoty, setHodnoty] = useState(() => vsechnyZeZaznamu(zaznam, pole || []));
  const [kolize, setKolize] = useState(null);
  // Které pole má fokus — stav (ne jen ref), protože ho potřebuje přítomnost,
  // aby kolegům ukázala, na čem člověk právě je.
  const [fokusovane, setFokusovane] = useState("");

  // Co server naposledy potvrdil. Posílá se jako `puvodni`, aby server poznal,
  // že do pole mezitím zapsal někdo jiný.
  const serverRef = useRef(vsechnyZeZaznamu(zaznam, pole || []));
  // Zrcadlo `hodnoty` pro callbacky — `dokonci` se volá z onBlur a zavírání
  // formuláře, kde by uzavřená stará hodnota poslala na server starý text.
  const hodnotyRef = useRef(serverRef.current);
  const fokusRef = useRef("");
  // Klíče s nedoručenou změnou (server o ní ještě neví, nebo ji odmítl).
  const rozepsaneRef = useRef(new Set());
  // Klíče, u kterých ještě neodešlo `usazeno: true`. Bez tohohle seznamu by se
  // po doběhnutí debounce hodnota rovnala serveru a „usadit“ by se už nemělo
  // podle čeho — automatizace by se nikdy nespustily.
  const neusazeneRef = useRef(new Set());
  const zivyRef = useRef(false);
  const identitaRef = useRef(`${entita}:${id}`);

  // `pole` bývá inline literál, takže se každý render mění identita. Do
  // závislostí efektu jde proto textový podpis, samotný seznam přes ref.
  const poleKlice = pole || [];
  const podpisPoli = poleKlice.join("|");
  const kliceRef = useRef(poleKlice);
  kliceRef.current = poleKlice;

  // Musí být první efekt: efekty běží v pořadí zápisu, takže `zivyRef` je
  // nastavený dřív, než níž položený efekt sáhne na setState.
  useEffect(() => {
    zivyRef.current = true;
    return () => {
      zivyRef.current = false;
    };
  }, []);

  /**
   * Převezme data ze serveru — kromě polí, která má člověk pod rukama.
   * Používá se stejně pro polling (nový `zaznam`) i pro odpověď na uložení.
   */
  const prevezmi = useCallback((novyZaznam) => {
    // Bez záznamu se nepřebírá NIC. Prázdný objekt by se přeložil na samá
    // prázdná pole a vymazal by rozepsaný formulář — a to jak při prvním
    // renderu (data ještě nedošla), tak kdyby odpověď na uložení záznam
    // z nějakého důvodu neobsahovala.
    if (!novyZaznam || typeof novyZaznam !== "object") return;
    const klice = kliceRef.current;
    const nove = vsechnyZeZaznamu(novyZaznam, klice);
    const server = { ...serverRef.current };
    const dalsi = { ...hodnotyRef.current };
    let zmena = false;
    klice.forEach((k) => {
      if (fokusRef.current === k || rozepsaneRef.current.has(k)) return;
      server[k] = nove[k];
      if (!(k in dalsi) || dalsi[k] !== nove[k]) {
        dalsi[k] = nove[k];
        zmena = true;
      }
    });
    serverRef.current = server;
    if (!zmena) return;
    hodnotyRef.current = dalsi;
    if (zivyRef.current) setHodnoty(dalsi);
  }, []);

  const uloz = useCallback(
    async (klic, { hodnota, puvodni, usazeno }) => {
      try {
        const data = await patchPoleZaznamu({ entita, id, pole: klic, hodnota, puvodni, usazeno });
        serverRef.current = { ...serverRef.current, [klic]: hodnota };
        // Rozepsané pole uklidíme jen tehdy, když člověk mezitím nenapsal něco
        // dalšího — jinak by mu to server přepsal potvrzenou starší hodnotou.
        if (hodnotyRef.current[klic] === hodnota) rozepsaneRef.current.delete(klic);
        if (zivyRef.current) setKolize((k) => (k && k.pole === klic ? null : k));
        // Zbytek záznamu je po uložení čerstvější než to, co drží stránka.
        prevezmi(data?.zaznam);
        return data;
      } catch (e) {
        if (e?.status === 409) {
          const d = e.data || {};
          if (zivyRef.current) {
            setKolize({
              pole: d.pole || klic,
              moje: hodnota,
              aktualni: naText(d.aktualni),
              kdo: d.kdo || "",
              kdy: d.kdy || null,
              zprava: d.zprava || "",
            });
          }
          // Kolizi hlásíme i jako neuloženo — protože uloženo NENÍ.
          throw new Error("Neuloženo – mezitím to změnil někdo jiný.");
        }
        throw e;
      }
    },
    [entita, id, prevezmi],
  );

  const { stav, chyba, kdy, naplanuj, hned, ceka } = useAutosave(uloz);

  // Data ze serveru (první načtení i každé další). Efekt schválně visí na
  // `zaznam`, ne na `hodnoty` — jinak by se zacyklil sám na sobě.
  useEffect(() => {
    const identita = `${entita}:${id}`;
    if (identitaRef.current !== identita) {
      // Jiný záznam = čistý stůl. Držet rozepsané pole z předchozího záznamu
      // by znamenalo doslat cizí text do právě otevřeného.
      identitaRef.current = identita;
      fokusRef.current = "";
      rozepsaneRef.current.clear();
      neusazeneRef.current.clear();
      const nove = vsechnyZeZaznamu(zaznam, kliceRef.current);
      serverRef.current = nove;
      hodnotyRef.current = nove;
      setFokusovane("");
      setKolize(null);
      setHodnoty(nove);
      return;
    }
    prevezmi(zaznam);
  }, [zaznam, entita, id, podpisPoli, prevezmi]);

  /**
   * Zápis do pole. `ihned` = bez prodlevy; hotová rozhodnutí (výběr,
   * zaškrtávátko, datum) nemá smysl odkládat, a protože u nich není co dopisovat,
   * jdou na server rovnou jako usazená.
   */
  const zmen = useCallback(
    (klic, hodnota, ihned = false) => {
      const text = naText(hodnota);
      const dalsi = { ...hodnotyRef.current, [klic]: text };
      hodnotyRef.current = dalsi;
      setHodnoty(dalsi);
      rozepsaneRef.current.add(klic);
      if (!zapnuto) return;
      const argument = { hodnota: text, puvodni: serverRef.current[klic] ?? "", usazeno: Boolean(ihned) };
      if (ihned) {
        neusazeneRef.current.delete(klic);
        hned(klic, argument);
      } else {
        neusazeneRef.current.add(klic);
        naplanuj(klic, argument);
      }
    },
    [zapnuto, hned, naplanuj],
  );

  /**
   * „Člověk s polem skončil.“ Bez argumentu dožene všechna pole — to volá
   * formulář, který se zavírá, jinak by posledních pár znaků zmizelo.
   * Nedotčené pole nic neposílá (byl by to požadavek zbytečně).
   */
  const dokonci = useCallback(
    (klic) => {
      if (!zapnuto) return Promise.resolve([]);
      const kandidati = klic ? [klic] : [...neusazeneRef.current];
      const cekajici = kandidati.filter((k) => neusazeneRef.current.has(k));
      if (cekajici.length === 0) return Promise.resolve([]);
      return Promise.allSettled(
        cekajici.map((k) => {
          neusazeneRef.current.delete(k);
          return hned(k, {
            hodnota: hodnotyRef.current[k] ?? "",
            puvodni: serverRef.current[k] ?? "",
            usazeno: true,
          });
        }),
      );
    },
    [zapnuto, hned],
  );

  const onFokus = useCallback((klic) => {
    fokusRef.current = klic;
    setFokusovane(klic);
  }, []);

  const onBlur = useCallback(
    (klic) => {
      if (fokusRef.current === klic) {
        fokusRef.current = "";
        setFokusovane("");
      }
      return dokonci(klic);
    },
    [dokonci],
  );

  /** Člověk viděl cizí hodnotu a přesto chce svou → uložíme bez kontroly. */
  const prepis = useCallback(() => {
    if (!kolize) return;
    const { pole: klic, moje } = kolize;
    setKolize(null);
    rozepsaneRef.current.add(klic);
    neusazeneRef.current.delete(klic);
    hned(klic, { hodnota: moje, puvodni: null, usazeno: true });
  }, [kolize, hned]);

  /** Vezmi hodnotu ze serveru — moje se zahodí, včetně čekajícího uložení. */
  const vezmiJejich = useCallback(() => {
    if (!kolize) return;
    const { pole: klic, aktualni } = kolize;
    setKolize(null);
    rozepsaneRef.current.delete(klic);
    neusazeneRef.current.delete(klic);
    serverRef.current = { ...serverRef.current, [klic]: aktualni };
    const dalsi = { ...hodnotyRef.current, [klic]: aktualni };
    hodnotyRef.current = dalsi;
    setHodnoty(dalsi);
  }, [kolize]);

  const { pritomni, razitko } = usePritomnost({
    entitaTyp: entitaTyp || "",
    entitaId: String(id ?? ""),
    pole: fokusovane,
    zapnuto: Boolean(zapnuto && entitaTyp),
  });

  // Hotová věta o kolizi. Komponenta si z `kolize` může složit vlastní
  // (s čitelným názvem pole), tahle je pro případ, že to nepotřebuje řešit.
  const chybaHlaska = useMemo(() => {
    if (!kolize) return null;
    const kdo = kolize.kdo || "někdo jiný";
    return (
      `Pole „${kolize.pole}“ mezitím změnil ${kdo} na „${kolize.aktualni || "prázdné"}“. ` +
      `Ty píšeš „${kolize.moje || "prázdné"}“.`
    );
  }, [kolize]);

  return {
    hodnoty,
    zmen,
    stav,
    chyba,
    kdy,
    ceka,
    pritomni,
    razitko,
    kolize,
    prepis,
    vezmiJejich,
    dokonci,
    onFokus,
    onBlur,
    chybaHlaska,
  };
}

export default useZaznamAutosave;
