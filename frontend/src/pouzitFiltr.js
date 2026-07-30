// Sdílený stav filtru a řazení pro jednu sekci CRM.
//
// Je to jeden hook, protože filtr má platit ZÁROVEŇ pro tabulku i kanban —
// kdyby si každé zobrazení drželo vlastní stav, uživatel by v každém viděl něco
// jiného a nechápal proč.

import { useMemo, useState } from "react";
import { sloupceEntity, vychoziRazeni, zpracujRadky } from "./crmFiltry";

export default function pouzitFiltr(entita, radky, vlastniPole = []) {
  const [podminky, setPodminky] = useState([]);
  const [razeni, setRazeni] = useState(() => vychoziRazeni(entita));

  const sloupce = useMemo(() => sloupceEntity(entita, vlastniPole), [entita, vlastniPole]);
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
    sloupce,
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
