// Levý panel editoru nabídky: výběr šablony, paleta prvků (tahá se na papír)
// a vlastnosti vybraného prvku. Rozvržení samo drží nadřazená stránka
// (NabidkaVystupStranka), tady se jen hlásí změny přes onZmena.

import { useState } from "react";
import { SLOUPCU } from "../nabidkovac";
import { DlazdiceNahled } from "./NabidkaVystup";

const DRUH_POPIS = {
  hlavicka: "Hlavička",
  text: "Text",
  udaje: "Skupina údajů",
  udaj: "Dlaždice s hodnotou",
  graf: "Graf",
  tabulka: "Tabulka",
  zlom: "Zlom stránky",
};

// Šířky, které dávají v mřížce 12 sloupců smysl (dělitelné beze zbytku).
const SIRKY = [
  { s: 3, nazev: "¼" },
  { s: 4, nazev: "⅓" },
  { s: 6, nazev: "½" },
  { s: 8, nazev: "⅔" },
  { s: SLOUPCU, nazev: "celá" },
];

// Jak prvek pojmenovat v seznamu vypnutých – ať je poznat, co zapínám.
function popisPrvku(blok, katPole) {
  if (blok.nadpis) return blok.nadpis;
  if (blok.druh === "udaj") {
    const p = katPole.find((x) => x.klic === blok.klic);
    return p?.nazev || blok.klic;
  }
  return DRUH_POPIS[blok.druh] || blok.druh;
}

// Rozdělí pole katalogu do sekcí palety. Pořadí sekcí = pořadí, v jakém je
// posílá server (katalog je už seřazený podle skupin).
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

// Prvky bez vazby na katalog hodnot. `sirka` = výchozí šířka po vložení.
const PRVKY = [
  { druh: "text", nazev: "Text", sirka: SLOUPCU, popis: "Odstavec s nadpisem" },
  { druh: "udaje", nazev: "Skupina údajů", sirka: SLOUPCU, popis: "Několik hodnot v kartách" },
  { druh: "graf", nazev: "Graf", sirka: SLOUPCU, popis: "Měsíční špičky / výroba" },
  { druh: "tabulka", nazev: "Tabulka", sirka: SLOUPCU, popis: "Vývoj po letech" },
  { druh: "zlom", nazev: "Zlom stránky", sirka: SLOUPCU, popis: "Od tohohle místa nová stránka" },
];

export default function NabidkaVystupEditor({
  konfigurace,
  katalog,
  hodnoty,
  onZmena,
  vybranyId,
  onVyber,
  onTahejNovy,
  sablony,
  onPouzijSablonu,
  onUlozSablonu,
  onSmazSablonu,
}) {
  const bloky = konfigurace?.bloky || [];
  const katPole = katalog?.pole || [];
  const katSloupce = katalog?.tabulka_sloupce || [];
  const katHodnoty = hodnoty || {};
  const vybrany = bloky.find((b) => b.id === vybranyId) || null;
  const vybranyIdx = bloky.findIndex((b) => b.id === vybranyId);

  // Pole už položená na papíře jako dlaždice – v paletě je ztlumíme, ať je
  // vidět, co tam obchodník už má. Seznamy jsou krátké (jednotky až desítky
  // položek), takže se počítají při každém překreslení a memo netřeba.
  const polozene = new Set(bloky.filter((b) => b.druh === "udaj").map((b) => b.klic));
  const skupiny = doSkupin(katPole);
  const vypnute = bloky.filter((b) => !b.viditelny);

  function zmenVybrany(zmena) {
    if (vybranyIdx < 0) return;
    onZmena({
      ...konfigurace,
      bloky: bloky.map((b, i) => (i === vybranyIdx ? { ...b, ...zmena } : b)),
    });
  }

  function odeberVybrany() {
    if (vybranyIdx < 0) return;
    onZmena({ ...konfigurace, bloky: bloky.filter((_, i) => i !== vybranyIdx) });
    onVyber(null);
  }

  function prepniPole(klic) {
    const pole = vybrany?.pole || [];
    zmenVybrany({
      pole: pole.includes(klic) ? pole.filter((k) => k !== klic) : [...pole, klic],
    });
  }

  function presunPole(poleIdx, smer) {
    const pole = [...(vybrany?.pole || [])];
    const j = poleIdx + smer;
    if (j < 0 || j >= pole.length) return;
    [pole[poleIdx], pole[j]] = [pole[j], pole[poleIdx]];
    zmenVybrany({ pole });
  }

  return (
    <div>
      <Sablony
        sablony={sablony}
        onPouzij={onPouzijSablonu}
        onUloz={onUlozSablonu}
        onSmaz={onSmazSablonu}
      />

      <div className="ed-sekce">
        <div className="ed-sekce-t">Paleta — přetáhni na papír</div>
        <div className="ed-napoveda">
          Náhledy ukazují, jak prvek vypadá na papíře. Uchop ho za <b>⠿</b> a pusť
          na papír tam, kde ho chceš; šířku a texty nastavíš níž ve „Vlastnostech“.
        </div>
        {PRVKY.map((p) => (
          <PaletaPolozka
            key={p.druh}
            popisek={p.nazev}
            title={p.popis}
            nahled={<NahledPrvku druh={p.druh} />}
            onTahej={(e) => onTahejNovy(e, { druh: p.druh, sirka: p.sirka })}
          />
        ))}
      </div>

      {skupiny.map((skupina, i) => (
        <SkupinaPoli
          key={skupina.nazev}
          skupina={skupina}
          polozene={polozene}
          hodnoty={katHodnoty}
          onTahej={onTahejNovy}
          /* S grafickými náhledy je paleta vysoká – otevřená zůstane první
             sekce, ostatní se rozbalí na kliknutí. */
          vychoziOtevreno={i === 0}
        />
      ))}

      {vypnute.length > 0 && (
        <div className="ed-sekce">
          <div className="ed-sekce-t">Vypnuté prvky</div>
          <div className="ed-napoveda">
            Na papíře nejsou, protože se nemají tisknout. Zaškrtnutím je vrátíš.
          </div>
          {vypnute.map((b) => (
            <label className="ed-checkbox" key={b.id}>
              <input
                type="checkbox"
                checked={false}
                onChange={() =>
                  onZmena({
                    ...konfigurace,
                    bloky: bloky.map((x) => (x.id === b.id ? { ...x, viditelny: true } : x)),
                  })
                }
              />
              <span className="sp">{popisPrvku(b, katPole)}</span>
            </label>
          ))}
        </div>
      )}

      <div className="ed-sekce">
        <div className="ed-sekce-t">Vlastnosti</div>
        {!vybrany && (
          <div className="ed-napoveda">Klikni na prvek na papíře a uprav ho tady.</div>
        )}
        {vybrany && (
          <div className="ed-blok">
            <div className="ed-hlava">
              <span className="druh">{DRUH_POPIS[vybrany.druh] || vybrany.druh}</span>
              <span className="sp" />
              <button className="ed-btn" onClick={odeberVybrany} title="Odebrat z nabídky">
                Odebrat
              </button>
            </div>

            <label className="ed-checkbox">
              <input
                type="checkbox"
                checked={!!vybrany.viditelny}
                onChange={(e) => zmenVybrany({ viditelny: e.target.checked })}
              />
              <span className="sp">Zobrazit v nabídce</span>
            </label>

            {vybrany.druh !== "zlom" && (
              <>
                <div className="ed-sekce-nadpis">Šířka</div>
                <div className="ed-sirky">
                  {SIRKY.map((v) => (
                    <button
                      key={v.s}
                      className={"ed-btn" + (vybrany.sirka === v.s ? " aktivni" : "")}
                      onClick={() => zmenVybrany({ sirka: v.s })}
                    >
                      {v.nazev}
                    </button>
                  ))}
                </div>
              </>
            )}

            {vybrany.druh !== "zlom" && (
              <input
                className="nb-pole ed-pole-nadpis"
                value={vybrany.nadpis || ""}
                placeholder={
                  vybrany.druh === "hlavicka"
                    ? "Titulek nabídky"
                    : vybrany.druh === "udaj"
                    ? "Popisek dlaždice (prázdné = z katalogu)"
                    : "Nadpis"
                }
                onChange={(e) => zmenVybrany({ nadpis: e.target.value })}
              />
            )}

            {(vybrany.druh === "text" ||
              vybrany.druh === "hlavicka" ||
              vybrany.druh === "udaje") && (
              <textarea
                className="nb-pole ed-textarea"
                value={vybrany.text || ""}
                placeholder={
                  vybrany.druh === "hlavicka"
                    ? "Podnadpis (nepovinné)"
                    : vybrany.druh === "udaje"
                    ? "Úvodní věta nad údaji (nepovinné)"
                    : "Text odstavce"
                }
                onChange={(e) => zmenVybrany({ text: e.target.value })}
              />
            )}

            {vybrany.druh === "udaje" && (
              <PoleVyber
                vybrana={vybrany.pole || []}
                katalog={katPole}
                onPrepni={prepniPole}
                onPresun={presunPole}
              />
            )}

            {vybrany.druh === "tabulka" && (
              <SloupceVyber
                vybrane={vybrany.pole || []}
                katalog={katSloupce}
                onPrepni={prepniPole}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- Šablony (uložená rozvržení k opakovanému použití) ----------------------
function Sablony({ sablony, onPouzij, onUloz, onSmaz }) {
  const [volba, setVolba] = useState("");
  const ulozene = sablony?.sablony || [];
  const zNabidek = sablony?.nabidky || [];

  function pouzij(hodnota) {
    setVolba(hodnota);
    if (!hodnota) return;
    const [zdroj, id] = hodnota.split(":");
    const nalez =
      zdroj === "sablona"
        ? ulozene.find((s) => String(s.id) === id)
        : zdroj === "nabidka"
        ? zNabidek.find((n) => String(n.nabidka_id) === id)
        : { vychozi: true };
    if (onPouzij) onPouzij(nalez, zdroj);
    setVolba("");
  }

  return (
    <div className="ed-sekce">
      <div className="ed-sekce-t">Šablona</div>
      <select
        className="nb-pole"
        value={volba}
        onChange={(e) => pouzij(e.target.value)}
        aria-label="Vybrat šablonu"
      >
        <option value="">Vybrat šablonu…</option>
        <option value="vychozi:0">Výchozí předloha (z kódu)</option>
        {ulozene.length > 0 && (
          <optgroup label="Uložené šablony">
            {ulozene.map((s) => (
              <option key={s.id} value={`sablona:${s.id}`}>
                {s.nazev}
              </option>
            ))}
          </optgroup>
        )}
        {zNabidek.length > 0 && (
          <optgroup label="Z jiné nabídky">
            {zNabidek.map((n) => (
              <option key={n.nabidka_id} value={`nabidka:${n.nabidka_id}`}>
                {n.nazev}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      <div className="ed-napoveda">
        Vybráním se přepíše rozvržení téhle nabídky (zákaznická čísla zůstanou její).
        Uloží se až tlačítkem <b>Uložit</b> nahoře.
      </div>
      <button className="ed-btn" onClick={onUloz} style={{ marginTop: 6 }}>
        Uložit jako šablonu…
      </button>
      {ulozene.length > 0 && (
        <>
          <div className="ed-sekce-nadpis">Uložené šablony</div>
          {ulozene.map((s) => (
            <div className="ed-checkbox" key={s.id}>
              <span className="sp">{s.nazev}</span>
              <button
                className="ed-btn"
                onClick={() => onSmaz && onSmaz(s)}
                title="Smazat šablonu"
              >
                ✕
              </button>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function SkupinaPoli({ skupina, polozene, hodnoty, onTahej, vychoziOtevreno }) {
  const [otevreno, setOtevreno] = useState(vychoziOtevreno);
  return (
    <div className="ed-sekce">
      <button className="ed-skupina" onClick={() => setOtevreno((o) => !o)}>
        <span>{otevreno ? "▾" : "▸"}</span>
        <span className="sp">{skupina.nazev}</span>
        <span className="pocet">{skupina.pole.length}</span>
      </button>
      {otevreno &&
        skupina.pole.map((p) => (
          <PaletaPolozka
            key={p.klic}
            ztlumene={polozene.has(p.klic)}
            title={polozene.has(p.klic) ? "Na papíře už je" : "Přetáhni na papír"}
            nahled={<DlazdiceNahled klic={p.klic} h={hodnoty[p.klic] || { nazev: p.nazev, hodnota_text: "—", format: p.format }} />}
            onTahej={(e) => onTahej(e, { druh: "udaj", klic: p.klic, sirka: 4 })}
          />
        ))}
    </div>
  );
}

// Miniatura strukturního prvku: skutečné třídy papíru zmenšené na šířku panelu,
// aby bylo vidět, jak prvek vypadá, ne jen jak se jmenuje. Výška výřezu je
// pevná (obsah se ustřihne), obsah má šířku sloupce textu jako na papíře.
function NahledPrvku({ druh }) {
  const obsah = {
    text: (
      <div className="vy-blok">
        <h2>Nadpis odstavce</h2>
        <p className="vy-text">
          Text nabídky, který si napíšeš sám. Klidně na několik řádků – na papíře
          se zalomí podle šířky, kterou prvku dáš.
        </p>
      </div>
    ),
    udaje: (
      <div className="vy-blok">
        <h2>Nadpis skupiny</h2>
        <div className="vy-karty">
          {[
            ["Údaj", "123 kW"],
            ["Údaj", "456 kWh"],
            ["Údaj", "789 Kč"],
          ].map(([n, h], i) => (
            <div className={"vy-karta" + (i === 2 ? " zvyraznit" : "")} key={i}>
              <div className="k-nazev">{n}</div>
              <div className="k-hodnota">{h}</div>
            </div>
          ))}
        </div>
      </div>
    ),
    graf: (
      <div className="vy-blok">
        <h2>Nadpis grafu</h2>
        <div className="vy-graf">
          {/* Plochý poměr stran schválně: miniatura se vejde do výřezu palety,
              jinak by se spodní (zelené) sloupce ustřihly. */}
          <svg viewBox="0 0 300 56" style={{ display: "block", width: "100%" }} aria-hidden="true">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <g key={i}>
                <rect x={12 + i * 48} y={56 - (34 + (i % 3) * 6)} width="18" height={34 + (i % 3) * 6} fill="#d5dbd7" />
                <rect x={32 + i * 48} y={56 - 22} width="18" height="22" fill="#2f9e44" />
              </g>
            ))}
            <line x1="0" y1="22" x2="300" y2="22" stroke="#43514c" strokeDasharray="6 4" />
          </svg>
        </div>
      </div>
    ),
    tabulka: (
      <div className="vy-blok">
        <h2>Nadpis tabulky</h2>
        <table className="vy-tabulka">
          <thead>
            <tr><th>Rok</th><th>Úspora v roce</th><th>Kumulativně</th></tr>
          </thead>
          <tbody>
            {[1, 2, 3].map((r) => (
              <tr key={r}><td>{r}. rok</td><td>412 000 Kč</td><td>{r * 412} tis. Kč</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    ),
    zlom: (
      <div className="vy-zlom">
        <span>zlom stránky</span>
      </div>
    ),
  }[druh];
  return (
    <div className={"ed-nahled ed-nahled-" + druh}>
      <div className="ed-nahled-obsah">{obsah}</div>
    </div>
  );
}

function PaletaPolozka({ popisek, nahled, ztlumene = false, onTahej, title }) {
  return (
    <div
      className={"ed-paleta-polozka" + (ztlumene ? " ztlumene" : "")}
      draggable
      onDragStart={onTahej}
      title={title}
    >
      <span className="ed-uchop">⠿</span>
      <div className="ed-paleta-telo">
        {nahled}
        {popisek && <div className="ed-paleta-popisek">{popisek}</div>}
      </div>
    </div>
  );
}

// Výběr údajů do skupiny: nahoře vybraná pole (s pořadím ↑↓), dole nabídka.
function PoleVyber({ vybrana, katalog, onPrepni, onPresun }) {
  const mapa = Object.fromEntries(katalog.map((p) => [p.klic, p]));
  const nevybrana = katalog.filter((p) => !vybrana.includes(p.klic));
  return (
    <div>
      <div className="ed-sekce-nadpis">Zobrazené údaje (pořadí ↑↓)</div>
      {vybrana.length === 0 && <div className="vy-prazdno">Žádné – vyber níže.</div>}
      {vybrana.map((klic, i) => (
        <div className="ed-checkbox" key={klic}>
          <span className="sp">{mapa[klic]?.nazev || klic}</span>
          <button className="ed-btn" onClick={() => onPresun(i, -1)} disabled={i === 0}>↑</button>
          <button className="ed-btn" onClick={() => onPresun(i, 1)} disabled={i === vybrana.length - 1}>↓</button>
          <button className="ed-btn" onClick={() => onPrepni(klic)} title="Odebrat">✕</button>
        </div>
      ))}
      {nevybrana.length > 0 && (
        <>
          <div className="ed-sekce-nadpis">Přidat údaj</div>
          {nevybrana.map((p) => (
            <label className="ed-checkbox" key={p.klic}>
              <input type="checkbox" checked={false} onChange={() => onPrepni(p.klic)} />
              <span className="sp">{p.nazev}</span>
            </label>
          ))}
        </>
      )}
    </div>
  );
}

function SloupceVyber({ vybrane, katalog, onPrepni }) {
  return (
    <div>
      <div className="ed-sekce-nadpis">Sloupce tabulky</div>
      {katalog.map((s) => (
        <label className="ed-checkbox" key={s.klic}>
          <input
            type="checkbox"
            checked={vybrane.includes(s.klic)}
            onChange={() => onPrepni(s.klic)}
          />
          <span className="sp">{s.nazev}</span>
        </label>
      ))}
    </div>
  );
}
