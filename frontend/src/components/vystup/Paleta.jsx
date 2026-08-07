// Levý panel: prvky k přetažení na papír.
//
// Nahoře stavební prvky (text, kontejner, obrázek, grafika), pod nimi údaje
// z výpočtu rozdělené do skupin podle katalogu. Tahá se pointer eventy –
// stejný mechanismus jako posun po papíře, takže se prvek chová od chvíle
// uchopení až po puštění pořád stejně.

import { useState } from "react";

import { UdajNahled } from "./PrvekObsah";
import { OBSAH_SIRKA } from "../../vystup/model";

// Stavební prvky. `vlastnosti` přepisují výchozí rozměry z modelu.
const PRVKY = [
  {
    druh: "kontejner",
    nazev: "Kontejner",
    popis: "Rámeček, do kterého se skládají další prvky",
    ikona: "▤",
  },
  { druh: "text", nazev: "Text", popis: "Odstavec – píše se přímo na papíře", ikona: "¶" },
  { druh: "graf", nazev: "Graf", popis: "Výroba nebo měsíční špičky", ikona: "▮▯" },
  { druh: "obrazek", nazev: "Obrázek", popis: "Fotka, schéma nebo logo", ikona: "▣" },
  { druh: "cara", nazev: "Čára", popis: "Vodorovný oddělovač", ikona: "─" },
  { druh: "obdelnik", nazev: "Obdélník", popis: "Barevná plocha jako podklad", ikona: "▬" },
  {
    druh: "cislo_stranky",
    nazev: "Číslo stránky",
    popis: "Doplní se samo podle pořadí",
    ikona: "#",
  },
];

/** Rozdělí pole katalogu do sekcí. Pořadí drží server. */
function doSkupin(pole) {
  const out = [];
  for (const p of pole) {
    const nazev = p.skupina || "Ostatní";
    const posledni = out[out.length - 1];
    if (posledni && posledni.nazev === nazev) posledni.pole.push(p);
    else out.push({ nazev, pole: [p] });
  }
  return out;
}

function Polozka({ children, popis, ztlumena, onUchop }) {
  return (
    <div
      className={"pal-polozka" + (ztlumena ? " ztlumena" : "")}
      title={popis}
      onPointerDown={onUchop}
    >
      {children}
    </div>
  );
}

function Skupina({ nazev, pocet, otevrena, onPrepni, children }) {
  return (
    <div className="pal-skupina">
      <button className="pal-skupina-h" onClick={onPrepni} aria-expanded={otevrena}>
        <span className="sipka">{otevrena ? "▾" : "▸"}</span>
        <span className="nazev">{nazev}</span>
        <span className="pocet">{pocet}</span>
      </button>
      {otevrena && <div className="pal-skupina-telo">{children}</div>}
    </div>
  );
}

export default function Paleta({ editor, katalog, hodnoty }) {
  const [otevrene, setOtevrene] = useState({ prvky: true, 0: true });
  const katPole = katalog?.pole || [];
  const skupiny = doSkupin(katPole);
  // Tabulky z katalogu. Starší odpověď serveru registr nemá – pak zbyde jediná
  // roční tabulka, ať paleta nepřijde o prvek úplně.
  const tabulky = katalog?.tabulky?.length
    ? katalog.tabulky
    : [{ klic: "roky", nazev: "Tabulka", sloupce: katalog?.tabulka_sloupce || [] }];

  // Údaje, které na papíře už leží – v paletě je ztlumíme, ať je vidět,
  // co je hotové.
  const polozene = new Set();
  for (const stranka of editor.konfigurace?.stranky || []) {
    for (const p of stranka.prvky || []) {
      if (p.druh === "udaj") polozene.add(p.klic);
      for (const d of p.deti || []) if (d.druh === "udaj") polozene.add(d.klic);
    }
  }

  const prepni = (klic) => setOtevrene((o) => ({ ...o, [klic]: !o[klic] }));

  return (
    <div className="pal">
      <div className="pal-napoveda">
        Chyť prvek a přetáhni ho na papír. Puštěním nad kontejnerem ho vložíš
        dovnitř.
      </div>

      <Skupina
        nazev="Prvky"
        pocet={PRVKY.length + tabulky.length}
        otevrena={otevrene.prvky}
        onPrepni={() => prepni("prvky")}
      >
        <div className="pal-mrizka">
          {PRVKY.map((p) => (
            <Polozka
              key={p.druh}
              popis={p.popis}
              onUchop={(u) =>
                editor.zacniZPalety(u, p.druh, {
                  ...(p.druh === "kontejner" || p.druh === "text"
                    ? { sirka: OBSAH_SIRKA }
                    : {}),
                })
              }
            >
              <span className="pal-ikona" aria-hidden="true">
                {p.ikona}
              </span>
              <span className="pal-nazev">{p.nazev}</span>
            </Polozka>
          ))}
          {/* Každá tabulka je vlastní položka a přijde na papír hotová, se
              všemi svými sloupci. Jedna položka „Tabulka" by po přetažení byla
              prázdná a odkupní tabulka by se musela naklikat ve vlastnostech. */}
          {tabulky.map((t) => (
            <Polozka
              key={t.klic}
              popis={`Tabulka – ${t.nazev}`}
              onUchop={(u) =>
                editor.zacniZPalety(u, "tabulka", {
                  tabulka_klic: t.klic,
                  pole: (t.sloupce || []).map((s) => s.klic),
                })
              }
            >
              <span className="pal-ikona" aria-hidden="true">
                ▦
              </span>
              <span className="pal-nazev">{t.nazev}</span>
            </Polozka>
          ))}
        </div>
      </Skupina>

      {skupiny.map((skupina, i) => (
        <Skupina
          key={skupina.nazev}
          nazev={skupina.nazev}
          pocet={skupina.pole.length}
          otevrena={!!otevrene[i]}
          onPrepni={() => prepni(i)}
        >
          {skupina.pole.map((pole) => (
            <Polozka
              key={pole.klic}
              ztlumena={polozene.has(pole.klic)}
              popis={
                polozene.has(pole.klic)
                  ? "Na papíře už je – další kopii přidat můžeš"
                  : "Přetáhni na papír"
              }
              onUchop={(u) => editor.zacniZPalety(u, "udaj", { klic: pole.klic })}
            >
              <UdajNahled
                klic={pole.klic}
                h={
                  hodnoty?.[pole.klic] || {
                    nazev: pole.nazev,
                    hodnota_text: "—",
                    format: pole.format,
                  }
                }
              />
            </Polozka>
          ))}
        </Skupina>
      ))}
    </div>
  );
}
