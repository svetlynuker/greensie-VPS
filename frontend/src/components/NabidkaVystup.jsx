// Vykreslení nabídky pro zákazníka z konfigurace (bloky) + resolvnutých hodnot.
// Používá se dvakrát: jako živý náhled v editoru a jako tisková A4 stránka.
// Interní data se sem nedostanou – server posílá jen zákaznická (sablona_katalog).

import GrafVyrobaSpotreba from "./GrafVyrobaSpotreba";
import GrafOdberu from "./GrafOdberu";
import Logo from "./Logo";
import { fmtDatum, SLOUPCU, sirkaPolozky, doRadku } from "../nabidkovac";

// Pole, která v kartě zvýrazníme (úspora = to hlavní, co zákazníka zajímá).
const ZVYRAZNIT = new Set([
  "uspora_kum_kc", "uspora_rok1_kc", "rocni_uspora_2026_kc", "rocni_uspora_2027_kc",
  "pokryti_spotreby_fve", "zisk_spot_kc",
]);

// `format: "text"` = slovní hodnota (název baterie, režim). Na velkém číselném
// stupni by se v úzké dlaždici lámala na tři řádky, proto menší písmo.
function Hodnota({ h }) {
  return (
    <div className={"k-hodnota" + (h.format === "text" ? " slovni" : "")}>{h.hodnota_text}</div>
  );
}

function Karta({ h, zvyraznit }) {
  if (!h) return null;
  return (
    <div className={"vy-karta" + (zvyraznit ? " zvyraznit" : "")}>
      <div className="k-nazev">{h.nazev}</div>
      <Hodnota h={h} />
    </div>
  );
}

/**
 * Náhled dlaždice pro paletu editoru. Je to tatáž karta jako na papíře (včetně
 * zvýraznění), takže obchodník v paletě vidí přesně to, co přetáhne – ne jen
 * název pole.
 */
export function DlazdiceNahled({ klic, h }) {
  if (!h) return null;
  return <Karta h={h} zvyraznit={ZVYRAZNIT.has(klic)} />;
}

function BlokUdaje({ blok, hodnoty, tisk }) {
  // V tisku skryjeme pole bez hodnoty (—), v editoru je necháme (ať je vidět,
  // co se doplní po výpočtu).
  const klice = (blok.pole || []).filter((k) => {
    const h = hodnoty[k];
    if (!h) return false;
    if (tisk && (h.hodnota === null || h.hodnota === undefined)) return false;
    return true;
  });
  if (!klice.length) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Zatím není co zobrazit – spusť výpočet nabídky.</div>
      </div>
    );
  }
  const dvaSloupce = klice.length <= 2 || klice.length === 4;
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      {blok.text && <p className="vy-intro">{blok.text}</p>}
      <div className={"vy-karty" + (dvaSloupce ? " dva" : "")}>
        {klice.map((k) => (
          <Karta key={k} h={hodnoty[k]} zvyraznit={ZVYRAZNIT.has(k)} />
        ))}
      </div>
    </div>
  );
}

/** Jeden graf podle typu řešení – vytažené zvlášť, ať to kombinace může použít dvakrát. */
function JedenGraf({ typ, graf }) {
  if (typ === "ppa") return <GrafVyrobaSpotreba graf={graf} />;
  return (
    /* Který model (2026/2027) se kreslí, rozhoduje server v
       `sablona_katalog.graf_pro_typ` – stejně jako panel v nabídkovači,
       ať v nabídce neskončí jiný graf, než OZ viděl na obrazovce.
       Fallbacky drží funkční i starší uložené výsledky. */
    <GrafOdberu
      mesice={graf.mesice}
      bezBaterie={graf.bez_baterie_kw}
      sBaterii={graf.s_baterii_kw ?? graf.s_baterii_2026_kw}
      rpSoucasna={graf.rp_soucasna_zobrazena_kw ?? graf.rp_soucasna_kw}
      rpNova={graf.rp_nova_zobrazena_kw ?? graf.rp_nova_kw}
      {...(graf.popis_soucasna ? { popisSoucasna: graf.popis_soucasna } : {})}
      {...(graf.popis_nova ? { popisNova: graf.popis_nova } : {})}
    />
  );
}

function BlokGraf({ blok, typReseni, graf, tisk }) {
  // Kombinace opatření nese OBA grafy (elektrárna i špičky) – nabídka na obojí
  // má ukázat obojí, ne si jedno vybrat.
  if (typReseni === "kombinace" && graf?.kombinace) {
    const ppaOk = (graf.ppa?.mesice?.length || 0) > 0;
    const psOk = (graf.peak_shaving?.mesice?.length || 0) > 0;
    if (!ppaOk && !psOk) {
      return tisk ? null : (
        <div className="vy-blok">
          {blok.nadpis && <h2>{blok.nadpis}</h2>}
          <div className="vy-prazdno">Grafy se zobrazí po spojení nabídek.</div>
        </div>
      );
    }
    return (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        {ppaOk && (
          <>
            <h3 className="vy-podnadpis">Výroba elektrárny vs. vaše spotřeba</h3>
            <div className="vy-graf">
              <JedenGraf typ="ppa" graf={graf.ppa} />
            </div>
          </>
        )}
        {psOk && (
          <>
            <h3 className="vy-podnadpis">Měsíční špičky odběru – dnes vs. s baterií</h3>
            <div className="vy-graf">
              <JedenGraf typ="peak_shaving" graf={graf.peak_shaving} />
            </div>
          </>
        )}
      </div>
    );
  }

  const maData = graf && (graf.mesice?.length || 0) > 0;
  if (!maData) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Graf se zobrazí po spuštění výpočtu.</div>
      </div>
    );
  }
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      <div className="vy-graf">
        <JedenGraf typ={typReseni} graf={graf} />
      </div>
    </div>
  );
}

function BlokTabulka({ blok, tabulka, tisk }) {
  const vybrane = new Set(blok.pole || []);
  const sloupce = (tabulka?.sloupce || []).filter((s) => vybrane.has(s.klic));
  const indexy = sloupce.map((s) => (tabulka.sloupce || []).findIndex((x) => x.klic === s.klic));
  const radky = tabulka?.radky || [];
  if (!sloupce.length || !radky.length) {
    return tisk ? null : (
      <div className="vy-blok">
        {blok.nadpis && <h2>{blok.nadpis}</h2>}
        <div className="vy-prazdno">Tabulka se naplní po spuštění výpočtu.</div>
      </div>
    );
  }
  return (
    <div className="vy-blok">
      {blok.nadpis && <h2>{blok.nadpis}</h2>}
      <table className="vy-tabulka">
        <thead>
          <tr>{sloupce.map((s) => <th key={s.klic}>{s.nazev}</th>)}</tr>
        </thead>
        <tbody>
          {radky.map((r, i) => (
            <tr key={i}>{indexy.map((idx, j) => <td key={j}>{r[idx]}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BlokHlavicka({ blok, zakaznik }) {
  return (
    <div className="vy-hlavicka">
      <h1>{blok.nadpis || "Nabídka"}</h1>
      {blok.text && <div className="podnadpis">{blok.text}</div>}
      <div className="vy-prijemce">
        <span className="lbl">Nabídka pro: </span>
        <b>{zakaznik?.nazev || "—"}</b>
        {zakaznik?.adresa ? <span> · {zakaznik.adresa}</span> : null}
        {zakaznik?.datum ? (
          <div className="lbl" style={{ marginTop: 2 }}>Datum: {fmtDatum(zakaznik.datum)}</div>
        ) : null}
      </div>
    </div>
  );
}

// Kontakt firmy do zápatí. Adresa a telefon jsou z hlavičkového papíru
// (grafika/papiry, varianta Bedřichovská); e-mail je oproti papíru novější —
// papír má ještě instalace@, nabídky mají chodit na info@.
const FIRMA = {
  nazev: "GREENSIE",
  ulice: "Bedřichovská 2183/16",
  mesto: "182 00 Praha 8 – Libeň",
  telefon: "+420 222 703 031",
  email: "info@greensie.cz",
};

// Pás se značkou = záhlaví, které se opakuje na každé stránce (viz <thead> níž).
// Logo je vektorové, takže se v PDF vytiskne ostře v každé velikosti.
function Pas({ zakaznik }) {
  return (
    <div className="vy-pas">
      <span className="vy-logo">
        <Logo vyska={34} title="Greensie" />
      </span>
      <span className="vy-pas-info">
        {zakaznik?.nazev ? <span>{zakaznik.nazev}</span> : null}
        {zakaznik?.datum ? <span>{fmtDatum(zakaznik.datum)}</span> : null}
      </span>
    </div>
  );
}

function Zapati() {
  return (
    <div className="vy-zapati">
      <span className="vy-zapati-znacka">
        <Logo jen="znacka" vyska={26} />
      </span>
      <span className="vy-zapati-adresa">
        <b>{FIRMA.nazev}</b>
        <span>
          {FIRMA.ulice} · {FIRMA.mesto}
        </span>
      </span>
      <span className="vy-zapati-kontakt">
        <span>{FIRMA.telefon}</span>
        <span>{FIRMA.email}</span>
      </span>
    </div>
  );
}

// Jedna dlaždice s hodnotou (druh „udaj") – tahá se z palety editoru.
// Nadpis si obchodník může přepsat, jinak se použije název z katalogu.
function BlokUdaj({ blok, hodnoty, tisk }) {
  const h = hodnoty[blok.klic];
  if (!h) return null;
  if (tisk && (h.hodnota === null || h.hodnota === undefined)) return null;
  return (
    <div className={"vy-karta" + (ZVYRAZNIT.has(blok.klic) ? " zvyraznit" : "")}>
      <div className="k-nazev">{blok.nadpis || h.nazev}</div>
      <Hodnota h={h} />
    </div>
  );
}

function Polozka({ blok, data, tisk }) {
  switch (blok.druh) {
    case "hlavicka":
      return <BlokHlavicka blok={blok} zakaznik={data.zakaznik} />;
    case "text": {
      // Čerstvě přetažený text je prázdný – v editoru ho označíme, ať není
      // na papíře vidět jen prázdné místo. Do tisku placeholder nejde.
      const prazdny = !blok.nadpis && !blok.text;
      return (
        <div className="vy-blok">
          {blok.nadpis && <h2>{blok.nadpis}</h2>}
          {blok.text && <p className="vy-text">{blok.text}</p>}
          {prazdny && !tisk && (
            <div className="vy-prazdno">Prázdný text – nadpis a text napiš ve „Vlastnostech“.</div>
          )}
        </div>
      );
    }
    case "udaje":
      return <BlokUdaje blok={blok} hodnoty={data.hodnoty || {}} tisk={tisk} />;
    case "udaj":
      return <BlokUdaj blok={blok} hodnoty={data.hodnoty || {}} tisk={tisk} />;
    case "graf":
      return (
        <BlokGraf blok={blok} typReseni={data.typ_reseni} graf={data.graf} tisk={tisk} />
      );
    case "tabulka":
      return <BlokTabulka blok={blok} tabulka={data.tabulka} tisk={tisk} />;
    case "zlom":
      // V tisku jen zlomí stránku, na obrazovce je z něj vidět čárka s popiskem.
      return (
        <div className="vy-zlom" aria-hidden="true">
          <span>zlom stránky</span>
        </div>
      );
    default:
      return null;
  }
}

/**
 * `editor` (nepovinné) zapne ovládání na papíru – tahání, výběr, vkládání.
 * Bez něj je komponenta čistě vykreslovací (tisk i náhled).
 */
export default function NabidkaVystup({ data, konfigurace, tisk = false, editor = null }) {
  if (!data) return null;
  // V editoru kreslíme i vypnuté prvky (ztlumené), ať je uživatel vidí a může
  // s nimi pracovat; do tisku a náhledu jdou jen viditelné.
  // Na papíře je vždy jen to, co se vytiskne – vypnuté prvky spravuje levý
  // panel („Vypnuté prvky"), aby náhled nelhal o výsledném PDF.
  const polozky = (konfigurace?.bloky || []).filter((b) => b.viditelny);
  const radky = doRadku(polozky);
  return (
    <div className={"vystup-sheet" + (tisk ? " vystup-tisk" : "") + (editor ? " vystup-editace" : "") + (editor?.tahame ? " vystup-tahame" : "")}>
      {/* Vodoznak leží pod obsahem a nic nepřekrývá (pointer-events: none).
          V tisku je position: fixed, takže ho Chrome vykreslí vycentrovaný
          na každé stránce. */}
      <div className="vy-vodoznak" aria-hidden="true">
        <Logo jen="znacka" vyska={420} />
      </div>
      {/* Tabulka je tu jen kvůli stránkování tisku – jinak by záhlaví i zápatí
          zůstalo jen na první stránce. Prohlížeč totiž <thead> opakuje na
          každé stránce (odtud pás se značkou) a pro <tfoot> na každé stránce
          drží místo (odtud mezera pod obsahem, do které padne zápatí). */}
      <table className="vy-list" role="presentation">
        <thead>
          <tr>
            <td>
              <Pas zakaznik={data.zakaznik} />
            </td>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              {radky.map((radek, i) => (
                <Radek
                  key={radek.polozky[0]?.id || i}
                  radek={radek}
                  data={data}
                  tisk={tisk}
                  editor={editor}
                />
              ))}
              {editor ? <MistoVlozeni editor={editor} index={polozky.length} konec /> : null}
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td>
              <div className="vy-zapati-mezera" aria-hidden="true" />
            </td>
          </tr>
        </tfoot>
      </table>
      <Zapati />
    </div>
  );
}

// Jeden řádek mřížky. Buňky dělí šířku podle `sirka` (flex-grow = počet
// sloupců), zbytek do dvanáctky vyplní mezera, aby jedna třetinová dlaždice
// nezabrala celý řádek.
function Radek({ radek, data, tisk, editor }) {
  const zbytek = SLOUPCU - radek.sirkaCelkem;
  const viceBunek = radek.polozky.length > 1;
  return (
    <div className={"vy-radek" + (viceBunek ? " vy-radek-nelamat" : "")}>
      {radek.polozky.map((blok) => (
        <Bunka key={blok.id} blok={blok} data={data} tisk={tisk} editor={editor} />
      ))}
      {zbytek > 0 && (
        <div className="vy-mezera" style={{ "--s": zbytek }} aria-hidden="true" />
      )}
    </div>
  );
}

function Bunka({ blok, data, tisk, editor }) {
  const obsah = <Polozka blok={blok} data={data} tisk={tisk} />;
  const styl = { "--s": sirkaPolozky(blok) };
  if (!editor) {
    return (
      <div className="vy-bunka" style={styl}>
        {obsah}
      </div>
    );
  }
  const vybrany = editor.vybranyId === blok.id;
  return (
    <>
      <MistoVlozeni editor={editor} index={editor.indexPodleId(blok.id)} />
      <div
        className={"vy-bunka ed-polozka" + (vybrany ? " vybrana" : "")}
        style={styl}
        draggable
        onDragStart={(e) => editor.zacniTahat(e, blok.id)}
        onDragEnd={editor.dotahni}
        onClick={(e) => {
          e.stopPropagation();
          editor.vyber(blok.id);
        }}
      >
        <span className="ed-uchop" title="Přetáhni na jiné místo">⠿</span>
        {obsah}
      </div>
    </>
  );
}

// Cíl pro puštění prvku: úzký pásek mezi buňkami, který se při tahání zvýrazní.
function MistoVlozeni({ editor, index, konec = false }) {
  const aktivni = editor.mistoVlozeni === index;
  return (
    <div
      className={"ed-misto" + (aktivni ? " aktivni" : "") + (konec ? " konec" : "")}
      onDragOver={(e) => {
        e.preventDefault();
        editor.nastavMisto(index);
      }}
      onDragLeave={() => editor.nastavMisto(null)}
      onDrop={(e) => {
        e.preventDefault();
        editor.pust(e, index);
      }}
      aria-hidden="true"
    />
  );
}
