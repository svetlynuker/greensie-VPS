// Vykreslení obsahu jednoho prvku podle druhu.
//
// Používá se stejně v editoru i v tisku – co obchodník vidí na papíře, to
// vyjede v PDF. Rozdíly řídí `tisk`: v editoru se ukazují zástupné texty
// („graf se dokreslí po výpočtu"), v tisku prázdné prvky mizí.

import { useEffect, useState } from "react";

import GrafVyrobaSpotreba from "../GrafVyrobaSpotreba";
import GrafOdberu from "../GrafOdberu";
import { nactiObrazekVystupu } from "../../api";

// Pole, která v dlaždici zvýrazníme – úspora je to hlavní, co zákazník hledá.
const ZVYRAZNIT = new Set([
  "uspora_kum_kc", "uspora_rok1_kc", "rocni_uspora_2026_kc", "rocni_uspora_2027_kc",
  "pokryti_spotreby_fve", "zisk_spot_kc",
]);

/** Dlaždice s jednou hodnotou z výpočtu. */
function Udaj({ prvek, hodnoty, tisk }) {
  const h = hodnoty?.[prvek.klic];
  if (!h) {
    return tisk ? null : <div className="vy-prazdno">Údaj „{prvek.klic || "?"}" tu není.</div>;
  }
  // V tisku nemá smysl ukazovat pomlčku – prvek se schová celý.
  if (tisk && (h.hodnota === null || h.hodnota === undefined)) return null;
  return (
    <div className={"vy-udaj" + (ZVYRAZNIT.has(prvek.klic) ? " zvyraznit" : "")}>
      <div className="k-nazev">{prvek.popis || h.nazev}</div>
      <div className={"k-hodnota" + (h.format === "text" ? " slovni" : "")}>
        {h.hodnota_text}
      </div>
    </div>
  );
}

/** Náhled dlaždice pro paletu – tatáž karta jako na papíře. */
export function UdajNahled({ klic, h }) {
  if (!h) return null;
  return (
    <div className={"vy-udaj" + (ZVYRAZNIT.has(klic) ? " zvyraznit" : "")}>
      <div className="k-nazev">{h.nazev}</div>
      <div className={"k-hodnota" + (h.format === "text" ? " slovni" : "")}>
        {h.hodnota_text}
      </div>
    </div>
  );
}

function JedenGraf({ typ, graf }) {
  if (typ === "ppa") return <GrafVyrobaSpotreba graf={graf} />;
  return (
    /* Který model (2026/2027) se kreslí, rozhoduje server v
       `sablona_katalog.graf_pro_typ` – stejně jako panel v nabídkovači,
       ať v nabídce neskončí jiný graf, než OZ viděl na obrazovce. */
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

function Graf({ data, tisk }) {
  const typ = data?.typ_reseni;
  const graf = data?.graf;

  // Kombinace opatření nese OBA grafy – nabídka na obojí má ukázat obojí.
  if (typ === "kombinace" && graf?.kombinace) {
    const ppaOk = (graf.ppa?.mesice?.length || 0) > 0;
    const psOk = (graf.peak_shaving?.mesice?.length || 0) > 0;
    if (!ppaOk && !psOk) {
      return tisk ? null : <div className="vy-prazdno">Grafy se zobrazí po spojení nabídek.</div>;
    }
    return (
      <div className="vy-graf-dvojice">
        {ppaOk && (
          <div className="vy-graf">
            <JedenGraf typ="ppa" graf={graf.ppa} />
          </div>
        )}
        {psOk && (
          <div className="vy-graf">
            <JedenGraf typ="peak_shaving" graf={graf.peak_shaving} />
          </div>
        )}
      </div>
    );
  }

  if (!graf || !(graf.mesice?.length > 0)) {
    return tisk ? null : <div className="vy-prazdno">Graf se dokreslí po spuštění výpočtu.</div>;
  }
  return (
    <div className="vy-graf">
      <JedenGraf typ={typ} graf={graf} />
    </div>
  );
}

function Tabulka({ prvek, tabulka, tisk }) {
  const vybrane = new Set(prvek.pole || []);
  const vsechny = tabulka?.sloupce || [];
  const sloupce = vsechny.filter((s) => vybrane.has(s.klic));
  const indexy = sloupce.map((s) => vsechny.findIndex((x) => x.klic === s.klic));
  const radky = tabulka?.radky || [];
  if (!sloupce.length || !radky.length) {
    return tisk ? null : <div className="vy-prazdno">Tabulka se naplní po spuštění výpočtu.</div>;
  }
  return (
    <table className="vy-tabulka">
      <thead>
        <tr>
          {sloupce.map((s) => (
            <th key={s.klic}>{s.nazev}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {radky.map((r, i) => (
          <tr key={i}>
            {indexy.map((idx, j) => (
              <td key={j}>{r[idx]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Obrazek({ prvek, tisk }) {
  // Endpoint s obrázkem chce token v hlavičce, takže se stahuje přes fetch
  // a do <img> jde blob URL. Cache drží api.js, tady jen čekáme na výsledek.
  const [adresa, setAdresa] = useState(null);
  const [chyba, setChyba] = useState(false);

  useEffect(() => {
    let zruseno = false;
    setChyba(false);
    if (!prvek.obrazek) {
      setAdresa(null);
      return undefined;
    }
    nactiObrazekVystupu(prvek.obrazek)
      .then((url) => !zruseno && setAdresa(url))
      .catch(() => !zruseno && setChyba(true));
    return () => {
      zruseno = true;
    };
  }, [prvek.obrazek]);

  if (!prvek.obrazek) {
    return tisk ? null : (
      <div className="vy-prazdno vy-obrazek-prazdny">
        Obrázek zatím není – nahraj ho ve „Vlastnostech".
      </div>
    );
  }
  if (chyba) {
    return tisk ? null : <div className="vy-prazdno">Obrázek se nepodařilo načíst.</div>;
  }
  if (!adresa) return <div className="vy-obrazek-nacita" aria-hidden="true" />;
  return (
    <img className="vy-obrazek" src={adresa} alt={prvek.popis || ""} draggable={false} />
  );
}

/**
 * Formátovaný text. HTML je už pročištěné (backend při ukládání, editor při
 * psaní i vkládání), takže `dangerouslySetInnerHTML` je tu bezpečné –
 * a jinak se formátovaný text vykreslit nedá.
 */
function Text({ prvek, tisk }) {
  if (!prvek.html) {
    return tisk ? null : (
      <div className="vy-prazdno">Prázdný text – klikni sem dvakrát a piš.</div>
    );
  }
  return <div className="vy-text" dangerouslySetInnerHTML={{ __html: prvek.html }} />;
}

export default function PrvekObsah({ prvek, data, tisk = false, cisloStranky }) {
  switch (prvek.druh) {
    case "text":
      return <Text prvek={prvek} tisk={tisk} />;
    case "udaj":
      return <Udaj prvek={prvek} hodnoty={data?.hodnoty} tisk={tisk} />;
    case "graf":
      return <Graf data={data} tisk={tisk} />;
    case "tabulka":
      return <Tabulka prvek={prvek} tabulka={data?.tabulka} tisk={tisk} />;
    case "obrazek":
      return <Obrazek prvek={prvek} tisk={tisk} />;
    case "cara":
      // Linku kreslí rámeček prvku (styl.barva_ramecku), obsah je prázdný.
      return <div className="vy-cara" aria-hidden="true" />;
    case "obdelnik":
      return null; // jen podkladová plocha
    case "cislo_stranky":
      return <div className="vy-cislo-stranky">{cisloStranky}</div>;
    default:
      return null;
  }
}
