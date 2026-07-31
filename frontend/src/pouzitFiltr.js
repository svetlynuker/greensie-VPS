// Sdílený stav filtru, řazení a rozvržení sloupců pro jednu sekci CRM.
//
// Jméno začíná na `use` schválně: React na tom prefixu staví (pravidla hooků
// v lintu i devtools), takže `pouzitFiltr` by se sice četlo česky, ale nástroje
// by ho nepovažovaly za hook a přestaly hlídat pravidla volání.
//
// Je to jeden hook, protože filtr má platit ZÁROVEŇ pro tabulku i kanban —
// kdyby si každé zobrazení drželo vlastní stav, uživatel by v každém viděl něco
// jiného a nechápal proč.
//
// Od CRM-28 hook drží i **rozvržení tabulky** (skryté sloupce a jejich pořadí).
// Je to tady schválně, i když s filtrem přímo nesouvisí: obojí je „jak se ta
// sekce dívá na data", ukládá se to na stejné místo a uložený filtr si rozvržení
// nese s sebou. Kdyby to byl druhý hook, musela by ho každá stránka propojit
// s tím prvním — a někde by se to zapomnělo.
//
// POZOR na rozdíl mezi dvěma sadami sloupců:
//   * `sloupce`        = všechny, včetně skrytých → do FILTRU (filtrovat se dá
//                        i podle sloupce, který v tabulce vidět není),
//   * `sloupceTabulky` = jen viditelné, ve zvoleném pořadí → do TABULKY.

import { useCallback, useEffect, useMemo, useState } from "react";
import { sloupceEntity, vychoziRazeni, zpracujRadky } from "./crmFiltry";
import { nactiNastaveni, ulozNastaveni } from "./api";

/** Klíč v uživatelských nastaveních (přenáší se mezi počítači). */
export function klicRozvrzeni(entita) {
  return `crm_sloupce_${entita}`;
}

/** Použije rozvržení na seznam sloupců: nejdřív pořadí, pak skryté pryč. */
export function uplatniRozvrzeni(sloupce, rozvrzeni) {
  const { skryte = [], poradi = [] } = rozvrzeni || {};
  const skryteSet = new Set(skryte);
  // Sloupec, který v uloženém pořadí není (nový, nebo nové vlastní pole),
  // se řadí na konec v původním pořadí — ne že by zmizel.
  const index = new Map(poradi.map((k, i) => [k, i]));
  const serazene = [...sloupce].sort((a, b) => {
    const ia = index.has(a.klic) ? index.get(a.klic) : Number.MAX_SAFE_INTEGER;
    const ib = index.has(b.klic) ? index.get(b.klic) : Number.MAX_SAFE_INTEGER;
    return ia - ib;
  });
  return serazene.filter((s) => !skryteSet.has(s.klic));
}

export default function usePouzitFiltr(entita, radky, vlastniPole = []) {
  const [podminky, setPodminky] = useState([]);
  const [razeni, setRazeni] = useState(() => vychoziRazeni(entita));
  const [rozvrzeni, setRozvrzeni] = useState({ skryte: [], poradi: [] });

  const sloupce = useMemo(() => sloupceEntity(entita, vlastniPole), [entita, vlastniPole]);

  // Rozvržení se načte jednou po otevření sekce. Selhání se polyká: bez
  // uloženého rozvržení se ukáže výchozí tabulka, což je pořád použitelné.
  useEffect(() => {
    let platne = true;
    nactiNastaveni()
      .then((n) => {
        const ulozene = n?.[klicRozvrzeni(entita)];
        if (platne && ulozene && typeof ulozene === "object") {
          setRozvrzeni({ skryte: ulozene.skryte || [], poradi: ulozene.poradi || [] });
        }
      })
      .catch(() => {});
    return () => {
      platne = false;
    };
  }, [entita]);

  const ulozRozvrzeni = useCallback(
    (nove) => {
      setRozvrzeni(nove);
      // Ukládá se na pozadí — čekat na server u zaškrtnutí sloupce by bylo
      // znát. Když se to nepovede, zůstane to aspoň do konce sezení.
      ulozNastaveni(klicRozvrzeni(entita), nove).catch(() => {});
    },
    [entita]
  );

  const sloupceTabulky = useMemo(
    () => uplatniRozvrzeni(sloupce, rozvrzeni),
    [sloupce, rozvrzeni]
  );

  const zpracovane = useMemo(
    () => zpracujRadky(radky || [], { podminky, razeni }, sloupce),
    [radky, podminky, razeni, sloupce]
  );

  /**
   * Kanban se stejným filtrem: sloupce zůstanou, jen se z nich vyhodí dlaždice,
   * které filtr nepustil. Součty a počty se přepočítají, jinak by hlavička
   * sloupce tvrdila jiné číslo, než kolik je vidět dlaždic.
   */
  function filtrujKanban(kanbanSloupce) {
    return (kanbanSloupce || []).map((s) => {
      const zaznamy = zpracujRadky(s.zaznamy || [], { podminky, razeni }, sloupce);
      const soucet = zaznamy.reduce((a, z) => a + (Number(z.hodnota_kc || z.cena_kc) || 0), 0);
      return {
        ...s,
        zaznamy,
        pocet: zaznamy.length,
        soucet_kc: s.soucet_kc == null ? s.soucet_kc : soucet || null,
      };
    });
  }

  return {
    /** Všechny sloupce entity včetně skrytých — pro filtr a řazení. */
    sloupce,
    /** Jen viditelné a přeskládané — pro tabulku. */
    sloupceTabulky,
    rozvrzeni,
    ulozRozvrzeni,
    filtrujKanban,
    podminky,
    setPodminky,
    razeni,
    setRazeni,
    /** Řádky po filtru a řazení – tabulka i kanban berou tohle. */
    radky: zpracovane,
    /** Kolik řádků filtr skryl (do hlášky „5 z 210"). */
    skryto: (radky || []).length - zpracovane.length,
  };
}
