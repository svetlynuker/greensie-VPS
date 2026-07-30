// ============================================================
// Export seznamu CRM do CSV (CRM-13).
//
// Exportuje se PŘESNĚ to, co je vidět: sloupce v zobrazeném pořadí a řádky už
// profiltrované a seřazené. Kdyby export tahal data znovu z API, člověk by
// dostal jiný soubor, než jaký měl na obrazovce — a nepoznal by proč.
//
// Soubor je vyladěný pro Excel v české lokalizaci, protože v něm to vedení
// otevře:
//   * BOM na začátku, jinak Excel zobrazí diakritiku jako „ÄŤ",
//   * oddělovač `;` — český Excel bere čárku jako desetinné znaménko,
//   * čísla s desetinnou ČÁRKOU, aby s nimi šlo hned počítat,
//   * konce řádků CRLF.
// ============================================================

import { hodnotaRadku } from "./crmFiltry";

/** Hodnoty, které by Excel vyhodnotil jako formuli, se musí odzbrojit.
 *
 * Telefon „+420 777…" nebo text začínající `=` by se v Excelu stal výpočtem
 * (u `=` dokonce s možností spustit odkaz na jiný soubor). Apostrof na začátku
 * z toho udělá text; Excel ho sám nezobrazuje.
 */
function odzbroj(text) {
  return /^[=+\-@\t\r]/.test(text) ? `'${text}` : text;
}

function uvozovky(text) {
  // Uvozovky uvnitř se zdvojují – to je celý CSV escaping podle RFC 4180.
  return `"${String(text).replaceAll('"', '""')}"`;
}

/** ISO datum → 30.07.2026 (co Excel v CZ pochopí jako datum). */
function datumCz(hodnota) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(hodnota || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(hodnota ?? "");
}

/** Jedna buňka jako čistý text podle typu sloupce.
 *
 * `vykresli` je tatáž funkce, kterou používá tabulka. Používá se jen tehdy,
 * když vrátí text — u sloupců, které kreslí JSX (barevná značka stavu, tučné
 * číslo), by se do CSV dostal objekt, takže se pro ně bere surová hodnota.
 */
export function bunkaProExport(radek, sloupec, vykresli) {
  if (vykresli) {
    const v = vykresli(radek, sloupec);
    if (typeof v === "string" || typeof v === "number") {
      // „—" je zástupka pro prázdno v UI; v tabulce dat nemá co dělat.
      return v === "—" ? "" : String(v);
    }
  }

  const surova = hodnotaRadku(radek, sloupec.klic);
  if (surova === null || surova === undefined || surova === "") return "";

  const typ = sloupec.typ || "text";
  if (typ === "datum") return datumCz(surova);
  if (typ === "ano_ne") return surova === true || surova === "ano" ? "ano" : "ne";
  if (typ === "cislo" || typ === "penize") {
    const n = Number(surova);
    return Number.isFinite(n) ? String(n).replace(".", ",") : String(surova);
  }
  if (Array.isArray(surova)) return surova.join(" + ");
  return String(surova);
}

/** Celý CSV obsah včetně hlavičky. */
export function naCsv(sloupce, radky, vykresli) {
  const hlavicka = sloupce.map((s) => uvozovky(s.nazev)).join(";");
  const telo = radky.map((r) =>
    sloupce.map((s) => uvozovky(odzbroj(bunkaProExport(r, s, vykresli)))).join(";")
  );
  return `﻿${[hlavicka, ...telo].join("\r\n")}\r\n`;
}

/** Název souboru s datem, ať se soubory ve stažených nepřepisují. */
export function nazevSouboru(zaklad) {
  const d = new Date();
  const cast = (x) => String(x).padStart(2, "0");
  return `${zaklad}-${d.getFullYear()}-${cast(d.getMonth() + 1)}-${cast(d.getDate())}.csv`;
}

/** Stáhne CSV z prohlížeče (bez volání serveru — data už tu jsou). */
export function stahniCsv(zaklad, sloupce, radky, vykresli) {
  const obsah = naCsv(sloupce, radky, vykresli);
  const blob = new Blob([obsah], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nazevSouboru(zaklad);
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Bez uvolnění by objekt držel data v paměti až do zavření karty.
  URL.revokeObjectURL(url);
}
