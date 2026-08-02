import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Iniciraly from "./Iniciraly";
import { fmtKcKratce, fmtDatum, jePoTerminu, nazvyKategorii, tridaBarvy } from "../crm";

/**
 * Kanban se sloupci podle stavů pipeline a přetahováním dlaždic.
 *
 * Sloupce nejsou v kódu – přicházejí z tabulky stavů, takže je vedení může
 * měnit v nastavení CRM bez zásahu programátora.
 *
 * Přetahování jde přes nativní HTML5 drag & drop; appka má záměrně nulové UI
 * závislosti, takže se sem netahá knihovna. Klávesová obsluha je zajištěná
 * jinak: dlaždice má na sobě rozbalovací volbu stavu, aby se dal záznam
 * přesunout i bez myši (a na mobilu, kde drag & drop nefunguje).
 *
 * `dlazdice` je volitelný render obsahu dlaždice. Bez něj se kreslí obchodní
 * případ; sekce Nabídky si předá vlastní, aby nemusel existovat druhý kanban.
 *
 * `kategorie` je seznam z `crmKategorie()` – jen k přeložení klíče na název.
 * Kanban si ho sám nenačítá, aby ho stránka nemusela tahat dvakrát.
 *
 * ---- Proč má pole pevnou výšku ------------------------------------------
 * Dřív rostl kanban do výšky podle nejplnějšího sloupce a vodorovný posuvník
 * seděl až pod ním. Při dvaceti případech v jednom sloupci to znamenalo
 * odrolovat celou stránku dolů, jen aby se šlo podívat doprava. Teď má pole
 * výšku okna, roluje se do stran v něm a každý sloupec má vlastní svislý
 * posuvník — dá se tedy hýbat oběma směry, aniž se hne stránka.
 */
export default function Kanban({
  sloupce,
  onPresun,
  onOtevri,
  dlazdice = null,
  kategorie = [],
}) {
  const [nesu, setNesu] = useState(null); // id přetahovaného záznamu
  const [nad, setNad] = useState(null); // klíč stavu, nad kterým visí
  const poleRef = useRef(null);

  /**
   * Dopočítá výšku pole: co zbylo v okně od jeho horní hrany dolů.
   * V CSS to spočítat nejde — nad kanbanem je na každé stránce něco jiného
   * (KPI pás, lišta, rozbalený filtr), takže žádná konstanta nesedí všude.
   *
   * Zapisuje se jen skutečná změna. Změna výšky pole mění výšku stránky
   * a ta zpátky spustí ResizeObserver; bez téhle pojistky by se ti dva
   * překřikovali donekonečna.
   */
  useLayoutEffect(() => {
    const pole = poleRef.current;
    if (!pole) return undefined;

    let posledni = null;
    const dopocitej = () => {
      // Pozice v DOKUMENTU, ne ve viewportu: `getBoundingClientRect` sám
      // vrací hodnotu poníženou o odrolování, takže odrolovaná stránka by
      // dala vyšší pole → delší stránku → ještě víc rolování. Přičtením
      // scrollY je výpočet na odrolování nezávislý.
      const shora = pole.getBoundingClientRect().top + window.scrollY;
      // Rezerva dole = spodní odsazení obsahu (--pad-obsah) plus pár pixelů,
      // aby po kanbanu stránka nezačala rolovat kvůli poslednímu paddingu.
      const zbytek = Math.round(window.innerHeight - shora - 24);
      const vyska = Math.max(320, Math.min(window.innerHeight - 24, zbytek));
      if (posledni !== null && Math.abs(vyska - posledni) < 2) return;
      posledni = vyska;
      pole.style.setProperty("--kanban-v", `${vyska}px`);
    };

    dopocitej();
    window.addEventListener("resize", dopocitej);
    // Obsah nad kanbanem se za běhu mění (filtr se rozbalí, KPI pás naskočí).
    const sledovac = new ResizeObserver(dopocitej);
    sledovac.observe(document.body);
    return () => {
      window.removeEventListener("resize", dopocitej);
      sledovac.disconnect();
    };
  }, []);

  /**
   * Přetažení dlaždice k okraji pole s ním popojede. Bez toho se dlaždice
   * nedá přesunout do sloupce, který zrovna není vidět — a to je při pěti
   * sloupcích na užším monitoru většina z nich.
   */
  useEffect(() => {
    const pole = poleRef.current;
    if (!pole || !nesu) return undefined;

    let bezi = 0;
    const najedi = (e) => {
      const r = pole.getBoundingClientRect();
      const pasmo = 70; // jak blízko k okraji se začne popojíždět
      let smer = 0;
      if (e.clientX < r.left + pasmo) smer = -1;
      else if (e.clientX > r.right - pasmo) smer = 1;

      if (!smer) {
        cancelAnimationFrame(bezi);
        bezi = 0;
        return;
      }
      if (bezi) return;
      const krok = () => {
        pole.scrollLeft += smer * 14;
        bezi = requestAnimationFrame(krok);
      };
      bezi = requestAnimationFrame(krok);
    };
    const stop = () => {
      cancelAnimationFrame(bezi);
      bezi = 0;
    };

    // Na `dragleave` se schválně neposlouchá: bublá i při přechodu mezi
    // sloupci uvnitř pole, takže by popojíždění pořád škublo a znovu se
    // rozjelo. Že kurzor odjel z okraje, pozná `najedi` sám (smer === 0).
    pole.addEventListener("dragover", najedi);
    pole.addEventListener("drop", stop);
    document.addEventListener("dragend", stop);
    return () => {
      stop();
      pole.removeEventListener("dragover", najedi);
      pole.removeEventListener("drop", stop);
      document.removeEventListener("dragend", stop);
    };
  }, [nesu]);

  function zacniNest(e, zaznam) {
    setNesu(zaznam.id);
    e.dataTransfer.setData("text/plain", String(zaznam.id));
    e.dataTransfer.effectAllowed = "move";
  }

  function pust(e, stavKlic) {
    e.preventDefault();
    setNad(null);
    const id = Number(e.dataTransfer.getData("text/plain") || nesu);
    setNesu(null);
    if (!id) return;
    // Hledáme, odkud dlaždice přišla – přesun do stejného sloupce nemá smysl.
    const zdroj = sloupce.find((s) => s.zaznamy.some((z) => z.id === id));
    if (zdroj && zdroj.stav.klic === stavKlic) return;
    onPresun(id, stavKlic);
  }

  return (
    <div className="crm-kanban" ref={poleRef}>
      {sloupce.map((s) => (
        <div
          key={s.stav.klic}
          className={`crm-kanban-sloupec ${nad === s.stav.klic ? "nad" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setNad(s.stav.klic);
          }}
          onDragLeave={() => setNad((k) => (k === s.stav.klic ? null : k))}
          onDrop={(e) => pust(e, s.stav.klic)}
        >
          <div className={`crm-kanban-hlava ${tridaBarvy(s.stav.barva)}`}>
            <span className="crm-kanban-nazev">{s.stav.nazev}</span>
            <span className="crm-kanban-pocet">{s.pocet}</span>
          </div>
          {s.soucet_kc != null && (
            <div className="crm-kanban-soucet">{fmtKcKratce(s.soucet_kc)}</div>
          )}

          <div className="crm-kanban-telo">
            {s.zaznamy.map((z) => (
              <article
                key={z.id}
                className={`crm-dlazdice ${nesu === z.id ? "nesu" : ""}`}
                draggable
                onDragStart={(e) => zacniNest(e, z)}
                onDragEnd={() => setNesu(null)}
                onClick={() => onOtevri(z)}
                title="Klikni pro detail, přetáhni pro změnu stavu"
              >
                {dlazdice ? (
                  dlazdice(z)
                ) : (
                  <>
                    <div className="crm-dlazdice-hlava">
                      <span className="crm-dlazdice-cislo">{z.cislo}</span>
                      {z.hodnota_kc ? (
                        <span className="crm-dlazdice-hodnota">{fmtKcKratce(z.hodnota_kc)}</span>
                      ) : null}
                    </div>
                    <div className="crm-dlazdice-zakaznik">{z.zakaznik_nazev}</div>
                    {z.nazev && <div className="crm-dlazdice-nazev">{z.nazev}</div>}
                    <div className="crm-dlazdice-pata">
                      {nazvyKategorii(z.kategorie, kategorie) || "bez kategorie"}
                      {z.predpokladane_uzavreni ? (
                        <span
                          className={
                            jePoTerminu(z.predpokladane_uzavreni) ? "crm-dlazdice-pozde" : undefined
                          }
                        >
                          {" · "}
                          {fmtDatum(z.predpokladane_uzavreni)}
                        </span>
                      ) : (
                        ""
                      )}
                    </div>
                    {/* Iniciály + jak dlouho případ visí v téhle fázi (CRM-44).
                        Dny ve fázi jsou to, co v kanbanu chybělo nejvíc: jinak
                        se nepozná ležák od čerstvého případu. */}
                    <div className="crm-dlazdice-vlastnik">
                      {z.vlastnik_jmeno && <Iniciraly jmeno={z.vlastnik_jmeno} velikost={16} />}
                      <span>{z.vlastnik_jmeno || "bez vlastníka"}</span>
                      <span className="crm-mezera" />
                      {z.dni_ve_fazi > 0 && (
                        <span
                          className={`crm-dni-ve-fazi${z.dni_ve_fazi >= 30 ? " dlouho" : ""}`}
                          title={`V tomhle stavu ${z.dni_ve_fazi} dní`}
                        >
                          {z.dni_ve_fazi} d
                        </span>
                      )}
                    </div>
                  </>
                )}

                {/* Náhrada přetahování pro klávesnici a mobil. */}
                <select
                  className="crm-dlazdice-stav"
                  value={s.stav.klic}
                  onClick={(e) => e.stopPropagation()}
                  onChange={(e) => {
                    e.stopPropagation();
                    if (e.target.value !== s.stav.klic) onPresun(z.id, e.target.value);
                  }}
                  aria-label={`Změnit stav ${z.cislo}`}
                >
                  {sloupce.map((jiny) => (
                    <option key={jiny.stav.klic} value={jiny.stav.klic}>
                      {jiny.stav.nazev}
                    </option>
                  ))}
                </select>
              </article>
            ))}
            {s.zaznamy.length === 0 && <div className="crm-kanban-prazdno">Prázdné</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
