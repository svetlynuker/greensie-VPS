// Pravý panel: vlastnosti vybraného prvku, jinak nastavení dokumentu.
//
// Vše, co se nedá pohodlně udělat myší na papíře (přesná čísla, barvy, výběr
// sloupců tabulky, nahrání obrázku), je tady. Co se udělat myší dá, tam je
// taky – ať si obchodník může vybrat.

import { useRef, useState } from "react";

import { nahrajObrazekVystupu } from "../../api";
import { A4_SIRKA, A4_VYSKA, DRUHY, OBSAH_DO, pretekaDolu } from "../../vystup/model";

function Sekce({ nadpis, children }) {
  return (
    <div className="vl-sekce">
      <div className="vl-sekce-t">{nadpis}</div>
      {children}
    </div>
  );
}

/** Číselné pole v milimetrech. */
function Cislo({ popisek, hodnota, onZmena, min = -100, max = 400, krok = 1, jednotka = "mm" }) {
  return (
    <label className="vl-cislo">
      <span className="vl-popisek">{popisek}</span>
      <span className="vl-vstup">
        <input
          type="number"
          value={Math.round((Number(hodnota) || 0) * 10) / 10}
          min={min}
          max={max}
          step={krok}
          onChange={(e) => onZmena(Number(e.target.value))}
        />
        <span className="vl-jednotka">{jednotka}</span>
      </span>
    </label>
  );
}

/** Výběr barvy včetně možnosti „žádná" (průhledné). */
function Barva({ popisek, hodnota, onZmena, umoznitZadnou = true }) {
  return (
    <label className="vl-barva">
      <span className="vl-popisek">{popisek}</span>
      <span className="vl-vstup">
        <input
          type="color"
          value={hodnota || "#ffffff"}
          onChange={(e) => onZmena(e.target.value)}
        />
        {umoznitZadnou && (
          <button
            type="button"
            className="vl-btn maly"
            onClick={() => onZmena("")}
            title="Bez barvy (průhledné)"
          >
            žádná
          </button>
        )}
      </span>
    </label>
  );
}

function Prepinac({ popisek, zapnuto, onZmena, napoveda }) {
  return (
    <label className="vl-prepinac" title={napoveda}>
      <input type="checkbox" checked={!!zapnuto} onChange={(e) => onZmena(e.target.checked)} />
      <span>{popisek}</span>
    </label>
  );
}

/** Poměr šířka/výška nahraného souboru. `null`, když se nepovede změřit. */
function pomerStran(soubor) {
  return new Promise((hotovo) => {
    const url = URL.createObjectURL(soubor);
    const obrazek = new Image();
    obrazek.onload = () => {
      URL.revokeObjectURL(url);
      hotovo(obrazek.naturalHeight ? obrazek.naturalWidth / obrazek.naturalHeight : null);
    };
    obrazek.onerror = () => {
      URL.revokeObjectURL(url);
      hotovo(null); // třeba SVG bez rozměrů – necháme výšku, jak byla
    };
    obrazek.src = url;
  });
}

/** Nahrání obrázku k prvku. */
function ObrazekPole({ prvek, editor, nabidkaId }) {
  const vstup = useRef(null);
  const [nahrava, setNahrava] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function vyber(soubor) {
    if (!soubor) return;
    setChyba(null);
    setNahrava(true);
    try {
      const odpoved = await nahrajObrazekVystupu(nabidkaId, soubor);
      // Poměr stran měříme z nahraného souboru rovnou v prohlížeči – server
      // by na to potřeboval knihovnu na obrázky a stejně by to bylo pomalejší.
      const pomer = await pomerStran(soubor);
      editor.uprav(prvek.id, {
        obrazek: odpoved.cesta,
        auto_vyska: false,
        ...(pomer ? { vyska: Math.round(prvek.sirka / pomer) } : {}),
      });
    } catch (e) {
      setChyba(e.message);
    } finally {
      setNahrava(false);
    }
  }

  return (
    <>
      <input
        ref={vstup}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/svg+xml"
        style={{ display: "none" }}
        onChange={(e) => vyber(e.target.files?.[0])}
      />
      <button className="vl-btn" onClick={() => vstup.current?.click()} disabled={nahrava}>
        {nahrava ? "Nahrávám…" : prvek.obrazek ? "Vyměnit obrázek…" : "Nahrát obrázek…"}
      </button>
      {prvek.obrazek && (
        <button className="vl-btn" onClick={() => editor.uprav(prvek.id, { obrazek: "" })}>
          Odebrat obrázek
        </button>
      )}
      {chyba && <div className="vl-chyba">{chyba}</div>}
      <label className="vl-text">
        <span className="vl-popisek">Popis (pro čtečky)</span>
        <input
          type="text"
          value={prvek.popis || ""}
          onChange={(e) =>
            editor.uprav(prvek.id, { popis: e.target.value }, { slouc: `alt:${prvek.id}` })
          }
        />
      </label>
    </>
  );
}

/** Výběr sloupců tabulky. */
function SloupceTabulky({ prvek, editor, katalog }) {
  const vybrane = new Set(prvek.pole || []);
  function prepni(klic) {
    const pole = vybrane.has(klic)
      ? (prvek.pole || []).filter((k) => k !== klic)
      : [...(prvek.pole || []), klic];
    editor.uprav(prvek.id, { pole });
  }
  return (
    <>
      {(katalog?.tabulka_sloupce || []).map((s) => (
        <Prepinac
          key={s.klic}
          popisek={s.nazev}
          zapnuto={vybrane.has(s.klic)}
          onZmena={() => prepni(s.klic)}
        />
      ))}
    </>
  );
}

/**
 * Ruční přepis hodnoty dlaždice.
 *
 * Vědomá výjimka z pravidla „čísla v nabídce jsou z výpočtu": při testování
 * a u nabídek, kde se čeká na opravu zadání, je potřeba přepsat jedno číslo
 * bez přepočtu celého řešení. Aby z výjimky nebyl tichý zvyk, je hodnota
 * v editoru barevně označená, lišta hlásí, kolik jich nabídka má, a tisk se
 * na ně zvlášť ptá. Klíč údaje se tím nemění – whitelist zůstává v platnosti.
 */
function RucniHodnota({ prvek, editor, hodnoty }) {
  const h = hodnoty?.[prvek.klic];
  const rucni = prvek.rucni_hodnota || "";
  return (
    <>
      <label className="vl-text">
        <span className="vl-popisek">Ruční hodnota</span>
        <input
          type="text"
          value={rucni}
          maxLength={120}
          placeholder="prázdné = hodnota z výpočtu"
          onChange={(e) =>
            editor.uprav(prvek.id, { rucni_hodnota: e.target.value }, { slouc: `rucni:${prvek.id}` })
          }
        />
      </label>
      {rucni.trim() ? (
        <div className="vl-varovani">
          Tiskne se ručně zadaná hodnota, ne výsledek výpočtu. Z výpočtu vychází{" "}
          <strong>{h?.hodnota_text || "—"}</strong>.
          <button
            className="vl-btn"
            onClick={() => editor.uprav(prvek.id, { rucni_hodnota: "" })}
          >
            Vrátit spočítanou hodnotu
          </button>
        </div>
      ) : (
        <div className="vl-napoveda">
          Vyplněním se hodnota na papíře přepíše i bez přepočtu nabídky. Používej
          jen na to, co se má opravit v zadání později.
        </div>
      )}
    </>
  );
}

/** Výběr, kterou hodnotu dlaždice ukazuje. */
function VyberUdaje({ prvek, editor, katalog }) {
  return (
    <label className="vl-text">
      <span className="vl-popisek">Zobrazená hodnota</span>
      <select value={prvek.klic || ""} onChange={(e) => editor.uprav(prvek.id, { klic: e.target.value })}>
        <option value="">— vyber údaj —</option>
        {(katalog?.pole || []).map((p) => (
          <option key={p.klic} value={p.klic}>
            {p.skupina ? `${p.skupina} · ` : ""}
            {p.nazev}
          </option>
        ))}
      </select>
    </label>
  );
}

function NastaveniDokumentu({ editor }) {
  const k = editor.konfigurace;
  return (
    <>
      <Sekce nadpis="Opakuje se na každé stránce">
        <Prepinac
          popisek="Pruh s logem nahoře"
          zapnuto={k.hlavicka?.zobrazit}
          onZmena={(v) => editor.upravDokument({ hlavicka: { ...k.hlavicka, zobrazit: v } })}
        />
        <label className="vl-text">
          <span className="vl-popisek">Doplňkový text v pruhu</span>
          <input
            type="text"
            value={k.hlavicka?.text || ""}
            placeholder="např. číslo nabídky"
            onChange={(e) =>
              editor.upravDokument({ hlavicka: { ...k.hlavicka, text: e.target.value } })
            }
          />
        </label>

        <Prepinac
          popisek="Kontaktní zápatí dole"
          zapnuto={k.zapati?.zobrazit}
          onZmena={(v) => editor.upravDokument({ zapati: { ...k.zapati, zobrazit: v } })}
        />
        <label className="vl-text">
          <span className="vl-popisek">Doplňkový text v zápatí</span>
          <input
            type="text"
            value={k.zapati?.text || ""}
            onChange={(e) => editor.upravDokument({ zapati: { ...k.zapati, text: e.target.value } })}
          />
        </label>

        <Prepinac
          popisek="Vodoznak se značkou"
          zapnuto={k.vodoznak?.zobrazit}
          onZmena={(v) => editor.upravDokument({ vodoznak: { ...k.vodoznak, zobrazit: v } })}
        />
        {k.vodoznak?.zobrazit && (
          <Cislo
            popisek="Sytost vodoznaku"
            hodnota={(k.vodoznak?.pruhlednost ?? 0.07) * 100}
            min={0}
            max={50}
            krok={1}
            jednotka="%"
            onZmena={(v) =>
              editor.upravDokument({ vodoznak: { ...k.vodoznak, pruhlednost: v / 100 } })
            }
          />
        )}
      </Sekce>

      <Sekce nadpis="Pomůcky editoru">
        <Prepinac
          popisek="Přichytávat k mřížce"
          zapnuto={editor.mrizkaZapnuta}
          onZmena={editor.prepniMrizku}
          napoveda="Vypnutím se dá prvek posadit na libovolný milimetr"
        />
      </Sekce>
    </>
  );
}

export default function Vlastnosti({ editor, katalog, hodnoty, nabidkaId }) {
  const prvek = editor.vybrany;
  const vKontejneru = !!editor.vybranyRodic;

  if (!prvek) {
    return (
      <div className="vl">
        <div className="vl-napoveda">
          Klikni na prvek na papíře a uprav ho tady. Bez výběru se nastavuje celý
          dokument.
        </div>
        <NastaveniDokumentu editor={editor} />
      </div>
    );
  }

  const styl = prvek.styl || {};
  // Táhnutí posuvníkem nebo držení šipky u číselníku nasype desítky změn za
  // sekundu. Slučovací klíč zařídí, že v historii z nich bude jeden krok –
  // Ctrl+Z pak vrátí celou úpravu, ne poslední milimetr.
  const zmen = (zmena, klic) =>
    editor.uprav(prvek.id, zmena, { slouc: `vl:${prvek.id}:${klic}` });
  const zmenStyl = (zmena, klic) =>
    editor.upravStyl(prvek.id, zmena, { slouc: `vls:${prvek.id}:${klic}` });
  const preteka = !vKontejneru && pretekaDolu(prvek);

  return (
    <div className="vl">
      <div className="vl-hlava">
        <span className="vl-druh">{DRUHY[prvek.druh]?.nazev || prvek.druh}</span>
        {vKontejneru && <span className="vl-znacka">v kontejneru</span>}
      </div>

      {preteka && (
        <div className="vl-varovani">
          Prvek přetéká pod okraj sazby ({Math.round(prvek.y + prvek.vyska)} mm z{" "}
          {OBSAH_DO} mm).
          <button className="vl-btn" onClick={() => editor.presunNaStranku(prvek.id, 1)}>
            Přesunout na další stránku
          </button>
        </div>
      )}

      <Sekce nadpis="Obsah">
        {prvek.druh === "udaj" && (
          <>
            <VyberUdaje prvek={prvek} editor={editor} katalog={katalog} />
            <label className="vl-text">
              <span className="vl-popisek">Vlastní popisek</span>
              <input
                type="text"
                value={prvek.popis || ""}
                placeholder="prázdné = název z katalogu"
                onChange={(e) => zmen({ popis: e.target.value }, "popis")}
              />
            </label>
            <RucniHodnota prvek={prvek} editor={editor} hodnoty={hodnoty} />
          </>
        )}
        {prvek.druh === "tabulka" && (
          <SloupceTabulky prvek={prvek} editor={editor} katalog={katalog} />
        )}
        {prvek.druh === "obrazek" && (
          <ObrazekPole prvek={prvek} editor={editor} nabidkaId={nabidkaId} />
        )}
        {(prvek.druh === "text" || prvek.druh === "kontejner") && (
          <div className="vl-napoveda">
            {prvek.druh === "kontejner"
              ? "Nadpis kontejneru napíšeš dvojklikem na jeho horní okraj."
              : "Text se píše dvojklikem přímo na papíře."}
          </div>
        )}
        {prvek.druh === "graf" && (
          <div className="vl-napoveda">
            Graf se kreslí z výsledků výpočtu téhle nabídky. Měnit se dá jen
            velikost a umístění.
          </div>
        )}
        {prvek.druh === "cislo_stranky" && (
          <div className="vl-napoveda">Číslo se doplní samo podle pořadí stránky.</div>
        )}
        <Prepinac
          popisek="Tisknout"
          zapnuto={prvek.viditelny}
          onZmena={(v) => editor.uprav(prvek.id, { viditelny: v })}
          napoveda="Vypnutý prvek zůstane v editoru, ale do PDF nejde"
        />
      </Sekce>

      {prvek.druh === "kontejner" && (
        <Sekce nadpis="Uspořádání uvnitř">
          <Cislo
            popisek="Sloupců vedle sebe"
            hodnota={styl.sloupce || 1}
            min={1}
            max={6}
            jednotka=""
            onZmena={(v) => zmenStyl({ sloupce: Math.max(1, Math.min(6, Math.round(v))) }, "sloupce")}
          />
          <Cislo
            popisek="Mezera mezi prvky"
            hodnota={styl.mezera ?? 4}
            min={0}
            max={40}
            onZmena={(v) => zmenStyl({ mezera: v }, "mezera")}
          />
          <div className="vl-napoveda">
            Kontejner obsahuje {(prvek.deti || []).length} prvků. Přetahováním
            uvnitř měníš jejich pořadí.
          </div>
        </Sekce>
      )}

      {!vKontejneru && (
        <Sekce nadpis="Umístění a velikost">
          <div className="vl-dvojice">
            <Cislo popisek="Zleva" hodnota={prvek.x} max={A4_SIRKA} onZmena={(v) => zmen({ x: v }, "x")} />
            <Cislo popisek="Shora" hodnota={prvek.y} max={A4_VYSKA} onZmena={(v) => zmen({ y: v }, "y")} />
          </div>
          <div className="vl-dvojice">
            <Cislo
              popisek="Šířka"
              hodnota={prvek.sirka}
              min={8}
              max={A4_SIRKA}
              onZmena={(v) => zmen({ sirka: v }, "sirka")}
            />
            <Cislo
              popisek="Výška"
              hodnota={prvek.vyska}
              min={5}
              max={A4_VYSKA}
              onZmena={(v) => zmen({ vyska: v, auto_vyska: false }, "vyska")}
            />
          </div>
          <Prepinac
            popisek="Výška podle obsahu"
            zapnuto={prvek.auto_vyska}
            onZmena={(v) => editor.uprav(prvek.id, { auto_vyska: v })}
            napoveda="Prvek se sám roztáhne podle toho, kolik je v něm textu"
          />
          <Prepinac
            popisek="Zamknout proti posunu"
            zapnuto={prvek.zamceno}
            onZmena={(v) => editor.uprav(prvek.id, { zamceno: v })}
          />
        </Sekce>
      )}

      <Sekce nadpis="Vzhled">
        <Barva popisek="Pozadí" hodnota={styl.pozadi} onZmena={(v) => zmenStyl({ pozadi: v }, "pozadi")} />
        <Barva
          popisek="Rámeček"
          hodnota={styl.barva_ramecku}
          onZmena={(v) =>
            zmenStyl({ barva_ramecku: v, sirka_ramecku: v ? styl.sirka_ramecku || 0.3 : 0 }, "ramecek")
          }
        />
        {styl.barva_ramecku && (
          <Cislo
            popisek="Tloušťka rámečku"
            hodnota={styl.sirka_ramecku}
            min={0}
            max={5}
            krok={0.1}
            onZmena={(v) => zmenStyl({ sirka_ramecku: v }, "tloustka")}
          />
        )}
        <Cislo
          popisek="Zaoblení rohů"
          hodnota={styl.zaobleni}
          min={0}
          max={20}
          krok={0.5}
          onZmena={(v) => zmenStyl({ zaobleni: v }, "zaobleni")}
        />
        <Cislo
          popisek="Vnitřní okraj"
          hodnota={styl.odsazeni}
          min={0}
          max={40}
          krok={0.5}
          onZmena={(v) => zmenStyl({ odsazeni: v }, "odsazeni")}
        />
      </Sekce>

      <Sekce nadpis="Pořadí a akce">
        {!vKontejneru && (
          <div className="vl-tlacitka">
            <button className="vl-btn" onClick={() => editor.vrstva(prvek.id, Infinity)} title="Úplně dopředu">
              ⤒ dopředu
            </button>
            <button className="vl-btn" onClick={() => editor.vrstva(prvek.id, -Infinity)} title="Úplně dozadu">
              ⤓ dozadu
            </button>
          </div>
        )}
        <div className="vl-tlacitka">
          <button className="vl-btn" onClick={() => editor.duplikuj(prvek.id)}>
            Duplikovat
          </button>
          <button className="vl-btn nebezpecne" onClick={() => editor.smaz(prvek.id)}>
            Smazat
          </button>
        </div>
        {!vKontejneru && (
          <div className="vl-tlacitka">
            <button className="vl-btn" onClick={() => editor.presunNaStranku(prvek.id, -1)}>
              ↑ na předchozí stránku
            </button>
            <button className="vl-btn" onClick={() => editor.presunNaStranku(prvek.id, 1)}>
              ↓ na další stránku
            </button>
          </div>
        )}
      </Sekce>
    </div>
  );
}
