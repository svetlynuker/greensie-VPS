import { useEffect, useState } from "react";
import GrafOdberu from "./GrafOdberu";
import GrafPrubehu from "./GrafPrubehu";
import {
  crmOdbernaMistaNabidky,
  crmPouzijDiagramProNabidku,
  sazbySeznam,
  peakShavingProfilSouhrn,
  peakShavingPrubeh,
  peakShavingVariantaDetail,
  peakShavingVypocet,
  profilZpracuj,
  technologieSeznam,
} from "../api";

// Kolik variant se ukáže ve „zkráceném" srovnání (zbytek po přepnutí na vše).
const POCET_TOP_VARIANT = 3;

// Ručně zadané vstupy se pamatují per nabídka (prohlížeč), ať je OZ nemusí
// psát znovu při každém přepočtu. Nezamykají se – jde je kdykoli přepsat.
const KLIC_ULOZISTE = (nabidkaId) => `gs-ps-vstup-${nabidkaId}`;

function nactiUlozeneVstupy(nabidka) {
  // Základ = vstup posledního výpočtu (drží se u nabídky, funguje i na jiném
  // počítači), navrch rozepsané hodnoty z tohoto prohlížeče.
  let hodnoty = {};
  const rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "peak_shaving");
  const v = rr.length ? rr[rr.length - 1].popis_json?.vstup : null;
  if (v) {
    hodnoty = {
      distributor: v.distributor,
      hladina: v.napetova_hladina,
      rezKap: v.rezervovana_kapacita_kw != null ? String(v.rezervovana_kapacita_kw) : "",
      rezPrikon: v.rezervovany_prikon_kw != null ? String(v.rezervovany_prikon_kw) : "",
      snizeniRp: !!v.uvazovat_snizeni_rp,
      maxVykonStridace: v.max_vykon_stridace_kw != null ? String(v.max_vykon_stridace_kw) : "",
      baterieIds: v.baterie_ids || null,
      rezim: v.rezim || "peak_shaving",
      maxExport: v.max_export_kw != null ? String(v.max_export_kw) : "",
    };
  }
  try {
    const s = JSON.parse(localStorage.getItem(KLIC_ULOZISTE(nabidka.id)) || "null");
    if (s && typeof s === "object") hodnoty = { ...hodnoty, ...s };
  } catch {
    // poškozený zápis v úložišti prostě ignorujeme
  }
  return hodnoty;
}

// Sloupce srovnání, podle kterých jde řadit. `hodnota` vrací číslo nebo text
// (null = řadí se nakonec, ať prázdné návratnosti nepředbíhají spočítané).
const SLOUPCE_SROVNANI = [
  {
    klic: "nazev",
    nazev: "Baterie",
    vychoziSmer: "asc",
    cislo: false,
    hodnota: (v) => `${v.nazev} ${String(v.pocet_kusu ?? "").padStart(3, "0")}`,
  },
  {
    klic: "vykon",
    nazev: "Výkon / kapacita",
    vychoziSmer: "desc",
    cislo: true,
    hodnota: (v) => v.celkovy_vykon_kw ?? null,
  },
  {
    klic: "nova_rez",
    nazev: "Nová rez.",
    vychoziSmer: "asc",
    cislo: true,
    hodnota: (v) => v.nova_rezervovana_kapacita_kw ?? null,
  },
  {
    klic: "uspora",
    nazev: "Úspora/rok",
    vychoziSmer: "desc",
    cislo: true,
    hodnota: (v, i, je2027) =>
      je2027
        ? v.ekonomika_2027?.rocni_uspora_bez_aku ?? v.ekonomika_2027?.rocni_uspora ?? null
        : v.rocni_uspora_2026_kc ?? null,
  },
  {
    klic: "cena",
    nazev: "Cena",
    vychoziSmer: "asc",
    cislo: true,
    hodnota: (v) => v.cena_celkem_kc ?? null,
  },
  {
    // Reálná návratnost – stejné číslo, které rozhoduje o odznaku
    // „nedoporučeno" ve stejném řádku. Starší výsledky ji nemají → prostá.
    klic: "navratnost",
    nazev: "Návratnost",
    vychoziSmer: "asc",
    cislo: true,
    // Řadí se podle čísla, které je v řádku vidět – včetně dopočtu za horizontem,
    // jinak by varianty s odhadem padaly na konec bez ohledu na svou hodnotu.
    hodnota: (v, i, je2027, zaklad) => {
      const prosta = je2027
        ? v.navratnost_2027 ?? v.navratnost_2027_konzerv
        : v.navratnost_roky;
      return navratnostKZobrazeni(npvDleZakladu(v, zaklad), prosta)?.hodnota ?? null;
    },
  },
  {
    klic: "npv",
    nazev: "NPV",
    vychoziSmer: "desc",
    cislo: true,
    hodnota: (v, i, je2027, zaklad) => npvDleZakladu(v, zaklad).npv_kc ?? null,
  },
];

const DISTRIB = [
  { klic: "cez", nazev: "ČEZ Distribuce" },
  { klic: "egd", nazev: "EG.D" },
  { klic: "pre", nazev: "PRE distribuce" },
];
const HLADINY = [
  { klic: "vn", nazev: "VN" },
  { klic: "vvn", nazev: "VVN" },
];

// Názvy měsíců pro tabulku rozhodnutí obchodu (graf používá vlastní zkratky).
const MESICE_NAZVY = [
  "Leden",
  "Únor",
  "Březen",
  "Duben",
  "Květen",
  "Červen",
  "Červenec",
  "Srpen",
  "Září",
  "Říjen",
  "Listopad",
  "Prosinec",
];

// Co má baterie dělat (drží se `spot_arbitraz.REZIMY` na backendu).
const REZIMY = [
  {
    klic: "peak_shaving",
    nazev: "Peak shaving",
    popis: "baterie jen sráží špičky a šetří na platbě za výkon",
  },
  {
    klic: "kombinace",
    nazev: "Kombinace",
    popis:
      "sráží špičky a ve zbytku obchoduje; model si u každého měsíce sám vybere, co vydělá víc",
  },
  {
    klic: "spot",
    nazev: "Spot",
    popis: "baterie jen obchoduje, rezervovaná kapacita zůstává jak je",
  },
];

function kc(x) {
  return x == null ? "—" : `${Math.round(x).toLocaleString("cs-CZ")} Kč`;
}
function kw(x) {
  return x == null ? "—" : `${x.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} kW`;
}
function roky(x) {
  return x == null ? "—" : `${x.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} let`;
}
function fmtDatumCas(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "—";
}

// Hodnoty NPV/návratnosti pro zvolený základ. Starší uložené výsledky
// `npv_varianty` nemají – tam se použijí plochá pole (jediná, která existují).
function npvDleZakladu(v, zaklad) {
  const z = v?.npv_varianty?.[zaklad];
  if (z) return z;
  return {
    npv_kc: v?.npv_kc,
    irr: v?.irr,
    payback_roky: v?.payback_roky,
    doporuceno: v?.doporuceno,
    pouzit_model_2027: v?.npv_pouzit_model_2027,
    roky: v?.roky,
  };
}

// Reálnou návratnost počítá server jen do horizontu NPV (default 10 let); co se
// v něm nevrátí, nese `payback_roky = null`. Místo „nevrátí se" dopočítáme rok
// za horizontem z rozpisu po letech: chybějící část investice se dělí cash flow
// dalších let, které dál klesá stejným tempem jako na konci rozpisu (degradace
// úspor). Je to odhad za hranicí modelu – v UI se proto značí vlnovkou.
function navratnostZaHorizontem(rozpis) {
  if (!rozpis?.length) return null;
  const posledni = rozpis[rozpis.length - 1];
  if (posledni.cf_kum_kc >= 0) return null; // vrátila se v horizontu (má payback)
  let cf = posledni.cf_kc;
  if (!(cf > 0)) return null; // úspora nepokryje ani provoz – nevrátí se nikdy
  // Tempo poklesu z posledních dvou let rozpisu. Rostoucí CF neextrapolujeme
  // (byl by to optimismus navíc), počítáme s ním jako s konstantním.
  const predchozi = rozpis.length > 1 ? rozpis[rozpis.length - 2].cf_kc : null;
  let q = predchozi > 0 ? cf / predchozi : 1;
  if (!(q > 0) || q > 1) q = 1;
  let dluh = -posledni.cf_kum_kc;
  // Klesající řada má konečný součet cf·q/(1−q); když na dluh nestačí, nevrátí se.
  if (q < 1 && (cf * q) / (1 - q) <= dluh) return null;
  let let_ = rozpis.length;
  for (let i = 0; i < 200 && dluh > 0; i++) {
    cf *= q;
    if (dluh <= cf) {
      let_ += dluh / cf;
      dluh = 0;
    } else {
      dluh -= cf;
      let_ += 1;
    }
  }
  return dluh > 0 ? null : let_;
}

// Návratnost k zobrazení – vždy číslo, ať už spočítané serverem, dopočítané za
// horizontem, nebo (když ani to nejde, protože úspora nepokryje provoz) prostá.
// `druh` říká, o které z těch tří jde, ať se dá číslo správně popsat.
function navratnostKZobrazeni(npv, prosta) {
  if (npv?.payback_roky != null) return { hodnota: npv.payback_roky, druh: "realna" };
  if (npv?.payback_roky === undefined) {
    // Starší uložený výsledek reálnou návratnost vůbec nemá.
    return prosta != null ? { hodnota: prosta, druh: "prosta" } : null;
  }
  const odhad = navratnostZaHorizontem(npv.roky);
  if (odhad != null) return { hodnota: odhad, druh: "odhad" };
  return prosta != null ? { hodnota: prosta, druh: "prosta" } : null;
}

// Text návratnosti: vlnovka u odhadu za horizontem, „prostá" u posledního
// fallbacku, ať je z čísla poznat, jak vzniklo.
function navratnostText(n) {
  if (!n) return "—";
  if (n.druh === "odhad") return `~${roky(n.hodnota)}`;
  if (n.druh === "prosta") return `${roky(n.hodnota)} (prostá)`;
  return roky(n.hodnota);
}

function navratnostTitulek(n, horizont) {
  if (!n) return undefined;
  if (n.druh === "odhad") {
    return `Investice se v horizontu ${horizont ?? 10} let nevrátí. Číslo je dopočítané za horizont modelu z klesajícího cash flow posledních let – orientační.`;
  }
  if (n.druh === "prosta") {
    return "Reálná návratnost neexistuje – roční úspora nepokryje ani provozní náklady (O&M). Ukazuje se proto prostá návratnost (cena ÷ úspora jednoho roku), která O&M ani degradaci nezná.";
  }
  return undefined;
}

function VariantaRadek({ v, vybrana, rok, zakladNpv, onVyber }) {
  // Úspora a návratnost dle přepínače roku (2027 = NTS odhad; starší uložené
  // výsledky nesou rocni_uspora_bez_aku / navratnost_2027_konzerv – PS-3).
  const je2027 = rok === 2027;
  const uspora = je2027
    ? v.ekonomika_2027?.rocni_uspora_bez_aku ?? v.ekonomika_2027?.rocni_uspora
    : v.rocni_uspora_2026_kc;
  const npv = npvDleZakladu(v, zakladNpv);
  // Reálná návratnost (drží odznak „nedoporučeno" ve stejném řádku); starší
  // uložené výsledky ji nemají, tam se ukáže prostá návratnost roku.
  const prosta = je2027 ? v.navratnost_2027 ?? v.navratnost_2027_konzerv : v.navratnost_roky;
  const navratnost = navratnostKZobrazeni(npv, prosta);
  return (
    <tr
      onClick={onVyber}
      title="Kliknutím zobrazíš detail této varianty"
      style={{
        cursor: "pointer",
        ...(vybrana
          ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" }
          : {}),
      }}
    >
      <td>
        {vybrana ? "◄ " : ""}
        {v.nazev} × {v.pocet_kusu}
        {!npv.doporuceno && (
          <span className="nb-badge spatne" style={{ marginLeft: 6 }}>
            nedoporučeno
          </span>
        )}
      </td>
      <td className="n">
        {kw(v.celkovy_vykon_kw)} / {v.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh
      </td>
      <td className="n">{kw(v.nova_rezervovana_kapacita_kw)}</td>
      <td className="n">{kc(uspora)}</td>
      <td className="n">{kc(v.cena_celkem_kc)}</td>
      <td
        className="n"
        title={
          navratnostTitulek(navratnost, v.npv_horizont_roky) ||
          (prosta != null ? `prostá návratnost ${roky(prosta)}` : undefined)
        }
      >
        {navratnostText(navratnost)}
      </td>
      <td className="n">{npv.npv_kc != null ? kc(npv.npv_kc) : "—"}</td>
    </tr>
  );
}

// Z čeho se počítá NPV, reálná návratnost a doporučení. Obě sady spočítal
// backend (`npv_varianty`), přepínač jen volí, kterou uživatel vidí – žádný
// přepočet, žádné volání serveru.
const ZAKLADY_NPV = [
  {
    klic: "uspora",
    nazev: "celé úspory",
    popis:
      "Celý rozdíl proti dnešnímu stavu („dnešní faktura → faktura po instalaci“), " +
      "včetně úspory ze souběžné úpravy rezervace. Ekonomika projektu jako celku.",
  },
  {
    klic: "prinos_baterie",
    nazev: "přínosu baterie",
    popis:
      "Jen to, co přinese sama baterie nad rámec toho, co klient získá i bez investice " +
      "(pouhou úpravou rezervace). Přísnější pohled na samotnou investici.",
  },
];

// Segmentovaný přepínač zobrazení (styl .gs-seg z global.css). Používá se
// jen na volby, které překreslují už spočítaná data – nic nepočítá.
function SegPrepinac({ popis, aria, volby, hodnota, onZmena }) {
  return (
    <span className="gs-prepinac">
      <span className="gs-ctrl-label">{popis}</span>
      <span className="gs-seg" role="group" aria-label={aria}>
        {volby.map((v) => (
          <button
            key={String(v.klic)}
            type="button"
            aria-pressed={hodnota === v.klic}
            disabled={!!v.zakazano}
            title={v.title}
            onClick={() => onZmena(v.klic)}
          >
            {v.nazev}
          </button>
        ))}
      </span>
    </span>
  );
}

// Rozpad úspory za rok 2026 (dnešní tarif) – jen informativní srovnání.
function Ekonomika2026({ dop, vysledek }) {
  const e = dop.ekonomika_2026;
  // Starší uložené výsledky (před PS-7) rozpad úspory nenesou.
  if (e?.uspora_bez_investice == null) {
    return (
      <table className="nb-table">
        <tbody>
          <tr>
            <td>Roční náklad bez peak shavingu</td>
            <td className="n">{kc(e?.soucasny_naklad_celkem)}</td>
          </tr>
          <tr>
            <td>Roční náklad s peak shavingem</td>
            <td className="n">{kc(e?.novy_naklad_rezervace)}</td>
          </tr>
          {e?.naklad_ztrat_baterie > 0 && (
            <tr>
              <td className="dim">− ztráty baterie (cyklování)</td>
              <td className="n dim">{kc(e.naklad_ztrat_baterie)}</td>
            </tr>
          )}
          <tr className="soucet">
            <td>Roční úspora</td>
            <td className="n">{kc(e?.rocni_uspora)}</td>
          </tr>
        </tbody>
      </table>
    );
  }
  return (
    <table className="nb-table">
      <tbody>
        <tr>
          <td>
            Náklad dnes{" "}
            <span style={{ color: "var(--muted)" }}>
              (RK {kw(vysledek.vstup?.rezervovana_kapacita_kw)})
            </span>
          </td>
          <td className="n">{kc(e.soucasny_naklad_celkem)}</td>
        </tr>
        <tr>
          <td>
            Optimalizace kapacity bez baterie{" "}
            <span style={{ color: "var(--muted)" }}>
              (roční RK {kw(e.optimalni_rk_bez_baterie_kw)}
              {e.dokupy_bez_baterie_pocet_mesicu > 0
                ? ` + měsíční RK v ${e.dokupy_bez_baterie_pocet_mesicu} měs.`
                : ""}
              )
            </span>
          </td>
          <td className="n">{kc(e.naklad_optimalni_bez_baterie)}</td>
        </tr>
        <tr className="soucet">
          <td>Úspora hned bez investice</td>
          <td className="n">{kc(e.uspora_bez_investice)}</td>
        </tr>
        {/* Optimalizace nese bezpečnostní rezervu nad naměřená maxima, dnešní RK
            ne – s drahou rezervou umí vyjít dráž než nedělat nic. Pak je
            baseline dnešní stav a přínos baterie se počítá proti němu. */}
        {e.naklad_optimalni_bez_baterie > e.soucasny_naklad_celkem && (
          <tr>
            <td colSpan={2} className="dim" style={{ fontSize: 11 }}>
              Optimalizovaná RK (s rezervou {dop.rezerva_rk_procenta ?? 0} % nad naměřená maxima) by
              byla o {kc(e.naklad_optimalni_bez_baterie - e.soucasny_naklad_celkem)} dražší než
              dnešní stav — zákazník dnes vědomě riskuje pokuty a vyplácí se mu to. Bez investice
              tedy nemá co ušetřit a přínos baterie se počítá proti dnešnímu nákladu.
            </td>
          </tr>
        )}
        <tr>
          <td>
            Náklad s baterií
            {e.naklad_ztrat_baterie > 0 && (
              <span style={{ color: "var(--muted)", fontSize: 11 }}>
                {" "}
                + ztráty {kc(e.naklad_ztrat_baterie)}
              </span>
            )}
          </td>
          <td className="n">{kc(e.novy_naklad_rezervace)}</td>
        </tr>
        <tr className="soucet">
          <td>Přínos baterie</td>
          <td className="n">{kc(e.prinos_baterie)}</td>
        </tr>
        <tr className="soucet">
          <td>Roční úspora celkem</td>
          <td className="n">{kc(e.rocni_uspora)}</td>
        </tr>
      </tbody>
    </table>
  );
}

// Rozpad úspory v nové struktuře ERÚ (2027) – tenhle rok rozhoduje.
function Ekonomika2027({ dop, rpJeFallbackRk }) {
  const e = dop.ekonomika_2027;
  if (e?.status !== "spocitano") {
    return (
      <div style={{ padding: 14, fontSize: 13, color: "var(--muted)" }}>
        Čeká se na oficiální sazby ERÚ.
      </div>
    );
  }
  return (
    <table className="nb-table">
      <tbody>
        {/* Starší uložené výsledky (před PS-3) nesou *_bez_aku – zobrazí se
            konzervativní čísla; sleva AKU pro BTM baterii neexistuje. */}
        <tr>
          <td>
            Náklad dnes <span style={{ color: "var(--muted)" }}>(RP {kw(e.rp_soucasny_kw)})</span>
            {rpJeFallbackRk && (
              <div className="gs-pozn pozor">
                Příkon ze smlouvy nezadán → dosazena RK. Skutečný RP bývá vyšší, náklad 2027 i
                úspora jsou tak podhodnocené.
              </div>
            )}
          </td>
          <td className="n">{kc(e.soucasny_rocni_naklad)}</td>
        </tr>
        {/* Třetí výpočet: nejlevnější RP bez baterie (fér baseline 2027). */}
        {e.naklad_optimalni_bez_baterie != null && (
          <>
            <tr>
              <td>
                Optimalizace příkonu bez baterie{" "}
                <span style={{ color: "var(--muted)" }}>
                  (RP {kw(e.optimalni_rp_bez_baterie_kw)})
                </span>
              </td>
              <td className="n">{kc(e.naklad_optimalni_bez_baterie)}</td>
            </tr>
            <tr className="soucet">
              <td>Úspora hned bez investice</td>
              <td className="n">{kc(e.uspora_optimalizaci_bez_baterie)}</td>
            </tr>
            {/* Stejná úvaha jako u roku 2026: optimalizace nese rezervu,
                dnešní RP ze smlouvy ne – může vyjít dráž než nechat vše být. */}
            {e.naklad_optimalni_bez_baterie > e.soucasny_rocni_naklad && (
              <tr>
                <td colSpan={2} className="dim" style={{ fontSize: 11 }}>
                  Optimalizované RP (s rezervou {dop.rezerva_rk_procenta ?? 0} %) by bylo dražší než
                  dnešní příkon ze smlouvy — bez investice není co ušetřit, přínos baterie se počítá
                  proti dnešnímu nákladu.
                </td>
              </tr>
            )}
          </>
        )}
        <tr>
          <td>Náklad s peak shavingem</td>
          <td className="n">{kc(e.novy_rocni_naklad_bez_aku ?? e.novy_rocni_naklad)}</td>
        </tr>
        {e.mesicu_s_prekrocenim_rp > 0 && (
          <tr>
            <td className="dim">
              … z toho vědomé překročení RP{" "}
              <span style={{ fontSize: 11 }}>
                (v {e.mesicu_s_prekrocenim_rp} měs. – nižší RP se i s penalizací vyplatí)
              </span>
            </td>
            <td className="n dim">{kc(e.naklad_prekroceni_rp)}</td>
          </tr>
        )}
        {e.naklad_ztrat_baterie > 0 && (
          <tr>
            <td className="dim">… z toho ztráty baterie</td>
            <td className="n dim">{kc(e.naklad_ztrat_baterie)}</td>
          </tr>
        )}
        {e.prinos_baterie != null && (
          <tr className="soucet">
            <td>Přínos baterie</td>
            <td className="n">{kc(e.prinos_baterie)}</td>
          </tr>
        )}
        <tr className="soucet">
          <td>Roční úspora celkem</td>
          <td className="n">{kc(e.rocni_uspora_bez_aku ?? e.rocni_uspora)}</td>
        </tr>
        <tr>
          <td className="dim">Měsíců na tarifu T1 / T2</td>
          <td className="n dim">
            {e.pocet_mesicu_t1} / {e.pocet_mesicu_t2}
          </td>
        </tr>
        {e.rp_soucasny_kw != null && (
          <tr>
            <td className="dim">Rezervovaný příkon (RP)</td>
            <td className="n dim">
              {kw(e.rp_soucasny_kw)}
              {e.rp_novy_kw !== e.rp_soucasny_kw
                ? ` → ${kw(e.rp_novy_kw)} (${
                    e.rp_novy_kw < e.rp_soucasny_kw ? "snížení" : "navýšení"
                  })`
                : " (beze změny smlouvy)"}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

export default function PeakShavingPanel({ nabidka }) {
  // Zapamatované vstupy (poslední výpočet + rozepsané hodnoty z prohlížeče).
  const [ulozene] = useState(() => nactiUlozeneVstupy(nabidka));
  const [sazby, setSazby] = useState(null);
  const [souhrn, setSouhrn] = useState(null);
  const [distributor, setDistributor] = useState(ulozene.distributor || "cez");
  const [hladina, setHladina] = useState(ulozene.hladina || "vn");
  const [rezKap, setRezKap] = useState(ulozene.rezKap || "");
  // Rezervovaný příkon ze smlouvy o připojení – pro model 2027 (PS-4).
  const [rezPrikon, setRezPrikon] = useState(ulozene.rezPrikon || "");
  const [snizeniRp, setSnizeniRp] = useState(!!ulozene.snizeniRp);
  // Ruční override max. AC výkonu střídače (kW) – omezuje výkon modulárních
  // baterií, kde kapacita roste s počtem kusů, ale výkon drží sdílený PCS.
  const [maxVykonStridace, setMaxVykonStridace] = useState(ulozene.maxVykonStridace || "");
  // Co má baterie dělat (viz REZIMY) + limit dodávky do sítě pro obchodování.
  const [rezim, setRezim] = useState(ulozene.rezim || "peak_shaving");
  const [maxExport, setMaxExport] = useState(ulozene.maxExport || "");
  // Které baterie se mají počítat: null = celý katalog, pole id = ruční výběr.
  const [baterieIds, setBaterieIds] = useState(ulozene.baterieIds || null);
  const [katalogBaterii, setKatalogBaterii] = useState(null);
  const [hledaniBaterie, setHledaniBaterie] = useState("");
  const [vysledek, setVysledek] = useState(() => {
    const rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "peak_shaving");
    return rr.length ? rr[rr.length - 1].popis_json : null;
  });
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [pocita, setPocita] = useState(false);
  const [zpracovavaId, setZpracovavaId] = useState(null);
  // Odběrná místa klienta a jejich diagramy (CRM-46). Prázdné u nabídky bez
  // obchodního případu — nabídkovač jde otevřít i samostatně jako kalkulačka.
  const [mistaKlienta, setMistaKlienta] = useState([]);
  const [beremeDiagramId, setBeremeDiagramId] = useState(null);
  // Varianta vybraná kliknutím ve srovnání (0 = doporučená).
  const [vybranyIdx, setVybranyIdx] = useState(0);
  // Srovnání: false = 3 nejlepší, true = celý katalog (manažerské rozhodnutí).
  const [vsechnyVarianty, setVsechnyVarianty] = useState(false);
  // Graf/citlivost dopočítané na kliknutí u variant mimo TOP 3: { index: {...} }.
  const [dopoctene, setDopoctene] = useState({});
  const [dopocitava, setDopocitava] = useState(false);
  // Rok zobrazených hodnot (dlaždice, graf, srovnání) – default 2027 (NTS).
  const [rokZobrazeni, setRokZobrazeni] = useState(2027);
  // Která záložka výsledku je otevřená. Výsledek býval jedna dlouhá rolovačka
  // (~2500 px), takže se srovnání variant nepotkalo s čísly, která přepisuje.
  const [zalozka, setZalozka] = useState("ekonomika");
  // Základ NPV/návratnosti – volba OZ, pamatuje se per prohlížeč (bez přepočtu).
  const [zakladNpv, setZakladNpv] = useState(() => {
    try {
      const s = localStorage.getItem("gs-ps-zaklad-npv");
      return ZAKLADY_NPV.some((z) => z.klic === s) ? s : "uspora";
    } catch {
      return "uspora";
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem("gs-ps-zaklad-npv", zakladNpv);
    } catch {
      // plné/zakázané úložiště nesmí shodit panel
    }
  }, [zakladNpv]);
  // Graf průběhu (15min řady) se stahuje zvlášť a až na vyžádání – je to
  // ~35 tisíc hodnot na variantu a rok. Cache podle varianty a roku.
  const [prubehOtevren, setPrubehOtevren] = useState(false);
  const [prubehy, setPrubehy] = useState({});
  const [prubehNacita, setPrubehNacita] = useState(false);
  const [prubehChyba, setPrubehChyba] = useState(null);
  // Řazení srovnání variant: klic = null → pořadí ze serveru (dle NPV sestupně).
  const [razeni, setRazeni] = useState({ klic: null, smer: "asc" });

  // Profil se parsuje hned při nahrání souboru — podpis dokumentů v závislostech
  // zajistí, že panel po nahrání souhrn dotáhne a nezůstane u „profil chybí“.
  const dokPodpis = (nabidka.dokumenty || [])
    .map((d) => `${d.id}:${d.stav_zpracovani}`)
    .join(",");

  useEffect(() => {
    sazbySeznam().then(setSazby).catch((e) => setChyba(e.message));
    peakShavingProfilSouhrn(nabidka.id).then(setSouhrn).catch(() => setSouhrn({ pocet: 0 }));
    // Do simulace jdou jen baterie z ceníku BESS – u komponent z prodejního
    // ceníku (BMS, racky, kabeláž) chybí výkon i kapacita a backend je stejně
    // odfiltruje. Tady se schovají, aby se v nabídce ani neukazovaly.
    technologieSeznam()
      .then((t) =>
        setKatalogBaterii(
          t.filter(
            (x) =>
              x.typ === "baterie" && x.aktivni && x.vykon_kw != null && x.kapacita_kwh != null
          )
        )
      )
      .catch(() => setKatalogBaterii([]));
    crmOdbernaMistaNabidky(nabidka.id)
      .then((d) => setMistaKlienta(d.mista || []))
      .catch(() => setMistaKlienta([]));
  }, [nabidka.id, dokPodpis]);

  // Zpracované diagramy všech míst klienta, plocho a s vlastníkem u sebe.
  // Místo, kterého se případ týká, jde první — obvykle je to to správné.
  const diagramyMist = [...mistaKlienta]
    .sort((a, b) => Number(b.vybrane_pro_pripad) - Number(a.vybrane_pro_pripad))
    .flatMap((misto) =>
      (misto.diagramy || [])
        .filter((diagram) => diagram.stav === "zpracovano")
        .map((diagram) => ({ misto, diagram }))
    );

  // Ruční vstupy si pamatujeme, ať je OZ nemusí psát znovu (bez zamykání).
  useEffect(() => {
    const data = {
      distributor,
      hladina,
      rezKap,
      rezPrikon,
      snizeniRp,
      maxVykonStridace,
      baterieIds,
      rezim,
      maxExport,
    };
    try {
      localStorage.setItem(KLIC_ULOZISTE(nabidka.id), JSON.stringify(data));
    } catch {
      // plné/zakázané úložiště nesmí shodit panel
    }
  }, [
    nabidka.id,
    distributor,
    hladina,
    rezKap,
    rezPrikon,
    snizeniRp,
    maxVykonStridace,
    baterieIds,
    rezim,
    maxExport,
  ]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const sazba = (sazby || []).find(
    (s) =>
      s.distributor === distributor &&
      s.napetova_hladina === hladina &&
      s.struktura_tarifu === "stara_2026"
  );
  // Pokuta za překročení se odvozuje z měsíční RK (1,5×, bod 4.24 výměru);
  // starší pole cena_prekroceni_kc_kw drží jen ručně založené sazby.
  const sazbaOk =
    sazba &&
    sazba.parametry &&
    sazba.parametry.cena_rezervovana_kapacita_kc_kw_rok != null &&
    (sazba.parametry.cena_mesicni_rk_kc_kw_mesic != null ||
      sazba.parametry.cena_prekroceni_kc_kw != null);
  const profilOk = souhrn && souhrn.pocet > 0;
  const rezOk = Number(String(rezKap).replace(",", ".")) > 0;
  // Ruční výběr baterií: co projde hledáním, a jestli je z čeho počítat.
  const viditelneBaterie = (katalogBaterii || []).filter((b) =>
    `${b.nazev} ${b.model || ""}`.toLowerCase().includes(hledaniBaterie.trim().toLowerCase())
  );
  const vyberBateriiOk = baterieIds === null || baterieIds.length > 0;
  const nazevDistributora = DISTRIB.find((d) => d.klic === distributor)?.nazev;
  const vsePripraveno = profilOk && rezOk && sazbaOk && vyberBateriiOk;

  /** Vezme diagram z odběrného místa klienta a přenese i parametry místa.
   *
   * Parametry se přepisují jen tam, kde místo hodnotu má — prázdné pole na
   * místě nesmí smazat to, co OZ v panelu zadal ručně (backend proto posílá
   * jen vyplněné, viz `odberna_mista.parametry_pro_vypocet`).
   */
  async function vezmiZMista(diagramId) {
    setBeremeDiagramId(diagramId);
    setChyba(null);
    setZprava(null);
    try {
      const v = await crmPouzijDiagramProNabidku(nabidka.id, diagramId);
      setSouhrn(await peakShavingProfilSouhrn(nabidka.id));
      const p = v.parametry_mista || {};
      if (p.distributor) setDistributor(p.distributor);
      if (p.napetova_hladina) setHladina(p.napetova_hladina);
      if (p.rezervovana_kapacita_kw != null) setRezKap(String(p.rezervovana_kapacita_kw));
      if (p.rezervovany_prikon_kw != null) setRezPrikon(String(p.rezervovany_prikon_kw));
      const prevzato = Object.keys(p).length
        ? ` Z místa „${v.odberne_misto}" převzato: ${Object.keys(p).length} parametrů.`
        : "";
      setZprava(`Profil načten: ${(v.pocet || 0).toLocaleString("cs-CZ")} intervalů.${prevzato}`);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setBeremeDiagramId(null);
    }
  }

  async function nactiProfil(dokId) {
    setZpracovavaId(dokId);
    setChyba(null);
    setZprava(null);
    try {
      const s = await profilZpracuj(nabidka.id, dokId);
      setSouhrn(s);
      setZprava(`Profil načten: ${s.pocet.toLocaleString("cs-CZ")} intervalů.`);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZpracovavaId(null);
    }
  }

  async function spocti() {
    setPocita(true);
    setChyba(null);
    setZprava(null);
    try {
      const prikon = Number(String(rezPrikon).replace(",", "."));
      const maxVykon = Number(String(maxVykonStridace).replace(",", "."));
      const r = await peakShavingVypocet(nabidka.id, {
        distributor,
        napetova_hladina: hladina,
        rezervovana_kapacita_kw: Number(String(rezKap).replace(",", ".")),
        rezervovany_prikon_kw: rezPrikon.trim() === "" || !(prikon > 0) ? null : prikon,
        uvazovat_snizeni_rp: snizeniRp,
        max_vykon_stridace_kw:
          maxVykonStridace.trim() === "" || !(maxVykon > 0) ? null : maxVykon,
        baterie_ids: baterieIds && baterieIds.length ? baterieIds : null,
        rezim,
        // Prázdné = výkon baterie; „0" je platná volba (bez dodávky do sítě).
        max_export_kw:
          rezim === "peak_shaving" || String(maxExport).trim() === ""
            ? null
            : Number(String(maxExport).replace(",", ".")),
      });
      setVysledek(r.popis_json);
      setVybranyIdx(0);
      setDopoctene({});
      setPrubehy({}); // nový výpočet = staré průběhy už neplatí
      setZalozka("ekonomika");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

  // Zobrazená varianta: kliknutím ve srovnání se přepne (0 = doporučená).
  // Starší uložené výsledky nesou graf/citlivost jen na nejvyšší úrovni
  // (pro doporučenou) – u alternativ se pak grafy skryjí.
  const varianty = vysledek?.varianty || [];
  const dop = varianty[vybranyIdx] || vysledek?.doporucena;
  const graf =
    dop?.graf || dopoctene[vybranyIdx]?.graf || (vybranyIdx === 0 ? vysledek?.graf : null);
  const citlivost =
    dop?.citlivost_stropu ||
    dopoctene[vybranyIdx]?.citlivost_stropu ||
    (vybranyIdx === 0 ? vysledek?.citlivost_stropu : null);

  // Kliknutí ve srovnání: u variant mimo TOP 3 si graf + citlivost doberem
  // ze serveru (dopočítat je pro celý ceník rovnou by výpočet výrazně zdržel).
  async function vyberVariantu(i) {
    setVybranyIdx(i);
    const v = varianty[i];
    if (!v || v.graf || dopoctene[i]) return;
    setDopocitava(true);
    setChyba(null);
    try {
      const d = await peakShavingVariantaDetail(nabidka.id, i);
      setDopoctene((s) => ({ ...s, [i]: d }));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setDopocitava(false);
    }
  }

  // Bez spočítané ekonomiky 2027 (čeká se na sazby ERÚ) se hodnoty roku 2027
  // ukázat nedají – zobrazení spadne na 2026 a tlačítko 2027 se zakáže.
  const ek27 = dop?.ekonomika_2027;
  const ma2027 = ek27?.status === "spocitano";
  // Ekonomika obchodování na spotu – u čistého peak shavingu chybí (null).
  const spot = dop?.ekonomika_spot || null;
  const rezimVysledku = dop?.rezim || vysledek?.vstup?.rezim || "peak_shaving";
  const rok = ma2027 ? rokZobrazeni : 2026;
  const je2027 = rok === 2027;
  // NPV / reálná návratnost / doporučení dle zvoleného základu (bez přepočtu).
  const npvDop = npvDleZakladu(dop, zakladNpv);
  // Prostá návratnost zobrazeného roku („cena ÷ úspora jednoho roku") – jen
  // orientační doplněk k reálné návratnosti.
  const prostaNavratnost = je2027
    ? dop?.navratnost_2027 ?? dop?.navratnost_2027_konzerv
    : dop?.navratnost_2026 ?? dop?.navratnost_roky;
  // Návratnost k zobrazení – vždy číslo (viz navratnostKZobrazeni výš).
  const navratnostDop = navratnostKZobrazeni(npvDop, prostaNavratnost);
  const zakladPopis = ZAKLADY_NPV.find((z) => z.klic === zakladNpv);
  const uspora2027 = ek27?.rocni_uspora_bez_aku ?? ek27?.rocni_uspora;
  const rpNovy2027 = ek27?.rp_novy_kw ?? ek27?.rezervovana_kapacita_kw;
  // Rezervovaný příkon OZ nezadal → model 2027 jede na RK (fallback RP = RK).
  const rpZeSmlouvy = vysledek?.vstup?.rezervovany_prikon_kw ?? null;
  const rpJeFallbackRk = ma2027 && !rpZeSmlouvy;

  // Referenční čáry grafu měsíčních maxim patří k zobrazenému roku: 2026 se
  // platí z rezervované kapacity, 2027 z rezervovaného příkonu (jiná čísla,
  // jiná optimalizace). Starší uložené výsledky nesou jen sadu 2026 – tam se
  // hodnoty doberou z ekonomiky 2027, kterou varianta má vždy.
  const refCaryGrafu = je2027
    ? {
        rpSoucasna: graf?.rp_soucasna_2027_kw ?? ek27?.rp_soucasny_kw ?? graf?.rp_soucasna_kw,
        rpNova: graf?.rp_nova_2027_kw ?? rpNovy2027 ?? graf?.rp_nova_kw,
        popisSoucasna: "rezervovaný příkon nyní",
        popisNova: "rezervovaný příkon po instalaci",
      }
    : {
        rpSoucasna: graf?.rp_soucasna_kw,
        rpNova: graf?.rp_nova_kw,
        popisSoucasna: "rezervovaná kapacita nyní",
        popisNova: "nová rezervovaná kapacita",
      };

  // Průběh v čase: stáhne se po otevření sekce a pak při každé změně varianty
  // nebo roku (jiný model = jiná simulace). Jednou stažené se drží v paměti.
  const prubehKlic = `${vybranyIdx}-${rok}`;
  const prubeh = prubehy[prubehKlic] || null;
  useEffect(() => {
    if (!prubehOtevren || !vysledek || prubehy[prubehKlic]) return undefined;
    let zruseno = false;
    setPrubehNacita(true);
    setPrubehChyba(null);
    peakShavingPrubeh(nabidka.id, vybranyIdx, rok)
      .then((d) => {
        if (!zruseno) setPrubehy((s) => ({ ...s, [prubehKlic]: d }));
      })
      .catch((e) => {
        if (!zruseno) setPrubehChyba(e.message);
      })
      .finally(() => {
        if (!zruseno) setPrubehNacita(false);
      });
    return () => {
      zruseno = true;
    };
  }, [prubehOtevren, prubehKlic, vysledek, prubehy, nabidka.id, vybranyIdx, rok]);

  // Srovnání variant: bez zvoleného sloupce se řadí dle NPV zvoleného základu
  // (tie-break reálná návratnost – stejný klíč jako na serveru). Při výchozím
  // základu to dá přesně pořadí ze serveru; po přepnutí se přeřadí bez
  // přepočtu. Každý řádek si nese původní index – ten drží odkaz na variantu
  // pro detail i pro dopočet grafu na serveru.
  const sloupecRazeni = SLOUPCE_SROVNANI.find((s) => s.klic === razeni.klic) || null;
  const serazeneVarianty = varianty.map((v, i) => ({ v, i }));
  if (!sloupecRazeni) {
    serazeneVarianty.sort((a, b) => {
      const x = npvDleZakladu(a.v, zakladNpv);
      const y = npvDleZakladu(b.v, zakladNpv);
      const rozdilNpv = (y.npv_kc ?? -Infinity) - (x.npv_kc ?? -Infinity);
      if (rozdilNpv) return rozdilNpv;
      return (x.payback_roky ?? Infinity) - (y.payback_roky ?? Infinity);
    });
  } else {
    serazeneVarianty.sort((a, b) => {
      const x = sloupecRazeni.hodnota(a.v, a.i, je2027, zakladNpv);
      const y = sloupecRazeni.hodnota(b.v, b.i, je2027, zakladNpv);
      if (x == null && y == null) return a.i - b.i;
      if (x == null) return 1; // prázdné hodnoty vždy na konec
      if (y == null) return -1;
      const smer = razeni.smer === "asc" ? 1 : -1;
      if (typeof x === "string" || typeof y === "string") {
        return smer * String(x).localeCompare(String(y), "cs");
      }
      return x === y ? a.i - b.i : smer * (x - y);
    });
  }
  const zobrazeneVarianty = vsechnyVarianty
    ? serazeneVarianty
    : serazeneVarianty.slice(0, POCET_TOP_VARIANT);
  // Kolikátá je zobrazená varianta v právě platném řazení. Index `vybranyIdx`
  // drží pořadí ze serveru, které po přepnutí základu NPV nebo řazení sloupce
  // už neplatí – proto se pořadí čte odsud, ne z indexu.
  const poradiVybrane = serazeneVarianty.findIndex((x) => x.i === vybranyIdx) + 1;

  function prepniRazeni(klic) {
    const s = SLOUPCE_SROVNANI.find((x) => x.klic === klic);
    setRazeni((r) =>
      r.klic === klic
        ? { klic, smer: r.smer === "asc" ? "desc" : "asc" }
        : { klic, smer: s?.vychoziSmer || "asc" }
    );
  }

  // Varianty k rozhodnutí. Tabulka srovnání odpovídá na „která je nejlepší podle
  // NPV"; tyhle karty na otázky, které klade zákazník — co doporučujeme a co je
  // nejlevnější. Vítěz se hledá nezávisle na řazení tabulky (to si uživatel mění
  // po svém). Kritérium „největší osekání špiček" tu bylo taky, ale nejnižší
  // rezervace sama o sobě o ničem nevypovídá – jen ukazovala na nejdražší baterii.
  const novaRezervace = (v) =>
    je2027
      ? v.ekonomika_2027?.rp_novy_kw ?? v.nova_rezervovana_kapacita_kw
      : v.nova_rezervovana_kapacita_kw;
  // Nejvyšší NPV napříč variantami – měřítko pro pruh na kartě.
  const npvMax = Math.max(
    0,
    ...varianty.map((v) => npvDleZakladu(v, zakladNpv).npv_kc ?? 0)
  );
  const kartyVariant = (() => {
    if (varianty.length < 2) return [];
    const vse = varianty.map((v, i) => ({ v, i }));
    // Nejmenší / největší podle hodnoty; varianty bez hodnoty se nepočítají.
    const nej = (hodnota, sestupne) => {
      const s = vse.filter((x) => hodnota(x.v) != null);
      if (!s.length) return null;
      return s.reduce((a, b) =>
        (sestupne ? hodnota(b.v) > hodnota(a.v) : hodnota(b.v) < hodnota(a.v)) ? b : a
      );
    };
    const kriteria = [
      {
        popis: "◆ Nejvhodnější",
        detail: "nejvyšší NPV — tuhle doporučujeme",
        vitez: nej((v) => npvDleZakladu(v, zakladNpv).npv_kc, true),
      },
      {
        popis: "Nejlevnější",
        detail: "nejnižší investice",
        vitez: nej((v) => v.cena_celkem_kc, false),
      },
    ].filter((k) => k.vitez);
    // Když je jedna varianta vítěz ve víc kritériích, ukáže se jednou a nese
    // všechny štítky – dvě stejné karty vedle sebe by nikomu nepomohly.
    const podleIndexu = new Map();
    for (const k of kriteria) {
      const zapis = podleIndexu.get(k.vitez.i) || { ...k.vitez, kriteria: [] };
      zapis.kriteria.push(k);
      podleIndexu.set(k.vitez.i, zapis);
    }
    return [...podleIndexu.values()];
  })();

  // ==================== VSTUPNÍ PANEL (levý sloupec) ====================
  const panelVstupu = (
    <form className="gs-panel" onSubmit={(e) => e.preventDefault()}>
      <div className="gs-panel-h">
        <h3>Vstupy výpočtu</h3>
        <span style={{ flex: 1 }} />
        {vsePripraveno ? (
          <span className="nb-badge dobre">✓ připraveno</span>
        ) : (
          <span className="nb-badge pozor">chybí vstupy</span>
        )}
      </div>

      <div className="gs-panel-body">
        {/* 1) Profil spotřeby */}
        <section className="gs-step">
          <span className="gs-step-num">1</span>
          <h4>Profil odběru</h4>
          <div className="gs-step-sub">15minutový export z portálu distributora.</div>
          {profilOk ? (
            <div className="gs-stav">
              <span aria-hidden="true">✓</span>
              <div>
                <div>
                  <b>{souhrn.pocet.toLocaleString("cs-CZ")}</b> intervalů ·{" "}
                  {fmtDatumCas(souhrn.od)} – {fmtDatumCas(souhrn.do)}
                </div>
                <div style={{ color: "var(--ink-2)" }}>
                  špička <b>{kw(souhrn.max_kw)}</b>
                </div>
              </div>
            </div>
          ) : (
            <div className="gs-stav chybi">
              <span aria-hidden="true">○</span>
              <div>Profil zatím není načtený — bez něj výpočet nejde spustit.</div>
            </div>
          )}
          {profilDoklady.length === 0 && diagramyMist.length === 0 ? (
            <div className="nb-warn" style={{ margin: "8px 0 0" }}>
              <span>⚠️</span>
              <span>
                Nejdřív nahraj soubor se spotřebou (sekce Podklady výše), nebo diagram
                k odběrnému místu na kartě klienta.
              </span>
            </div>
          ) : (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
              {profilDoklady.map((d) => (
                <button
                  key={d.id}
                  className="fm-btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={() => nactiProfil(d.id)}
                  disabled={zpracovavaId === d.id}
                  title={`Naparsuje 15min profil ze souboru ${d.puvodni_nazev}. Nahradí celý dosavadní profil nabídky.`}
                >
                  {zpracovavaId === d.id ? "Načítám…" : `Načíst: ${d.puvodni_nazev}`}
                </button>
              ))}
            </div>
          )}

          {/* Diagramy z odběrných míst zákazníka (CRM-46). Nahrané u klienta,
              použitelné pro každou nabídku té provozovny — a s nimi se
              předvyplní i distributor, hladina a rezervovaná kapacita. */}
          {diagramyMist.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="gs-step-sub">
                Diagramy odběrných míst klienta — použitím se z místa převezme i distributor,
                hladina a rezervovaná kapacita:
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 6 }}>
                {diagramyMist.map(({ misto, diagram }) => (
                  <button
                    key={diagram.id}
                    className="fm-btn"
                    style={{ padding: "4px 10px", fontSize: 12 }}
                    onClick={() => vezmiZMista(diagram.id)}
                    disabled={beremeDiagramId === diagram.id}
                    title={`${diagram.puvodni_nazev} · ${misto.nazev}. Nahradí celý dosavadní profil nabídky.`}
                  >
                    {beremeDiagramId === diagram.id
                      ? "Beru…"
                      : `${misto.nazev}: ${diagram.puvodni_nazev}`}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>

        {/* 2) Parametry odběrného místa */}
        <section className="gs-step">
          <span className="gs-step-num">2</span>
          <h4>Odběrné místo</h4>
          <div className="gs-step-sub">Ze smlouvy o připojení a z faktury za elektřinu.</div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="nb-label" htmlFor="ps-distributor">
                Distributor
              </label>
              <select
                id="ps-distributor"
                className="nb-pole"
                value={distributor}
                onChange={(e) => setDistributor(e.target.value)}
              >
                {DISTRIB.map((d) => (
                  <option key={d.klic} value={d.klic}>
                    {d.nazev}
                  </option>
                ))}
              </select>
            </div>
            <div className="gs-pole">
              <label className="nb-label" htmlFor="ps-hladina">
                Hladina
              </label>
              <select
                id="ps-hladina"
                className="nb-pole"
                value={hladina}
                onChange={(e) => setHladina(e.target.value)}
              >
                {HLADINY.map((h) => (
                  <option key={h.klic} value={h.klic}>
                    {h.nazev}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="gs-pole">
            <label className="nb-label" htmlFor="ps-rk">
              Rezervovaná kapacita <span style={{ fontWeight: 400 }}>(z faktury)</span>
            </label>
            <div className="gs-unit">
              <input
                id="ps-rk"
                className="nb-pole"
                value={rezKap}
                onChange={(e) => setRezKap(e.target.value)}
                inputMode="decimal"
                placeholder="např. 150"
              />
              <span className="gs-unit-txt">kW</span>
            </div>
          </div>
          <div className="gs-pole">
            <label className="nb-label" htmlFor="ps-rp">
              Rezervovaný příkon <span style={{ fontWeight: 400 }}>(ze smlouvy o připojení)</span>
            </label>
            <div className="gs-unit">
              <input
                id="ps-rp"
                className="nb-pole"
                value={rezPrikon}
                onChange={(e) => setRezPrikon(e.target.value)}
                inputMode="decimal"
                placeholder={rezOk ? `nezadáno → použije se RK ${rezKap}` : "pro model 2027"}
              />
              <span className="gs-unit-txt">kW</span>
            </div>
            {/* Prázdné pole není neutrální volba: RP ze smlouvy o připojení bývá
                výrazně vyšší než RK, takže fallback podhodnotí náklad 2027 i úsporu. */}
            <div className="gs-pozn">
              Řídí model 2027. Necháš-li prázdné, počítá se{" "}
              <b>RP = RK{rezOk ? ` (${rezKap} kW)` : ""}</b> — skutečný příkon bývá vyšší, náklad
              2027 i úspora pak vyjdou podhodnocené.
            </div>
          </div>
          <label className="gs-zaskrt" style={{ margin: "4px 0 12px" }}>
            <input
              type="checkbox"
              checked={snizeniRp}
              onChange={(e) => setSnizeniRp(e.target.checked)}
            />
            <span>
              V modelu 2027 uvažovat snížení rezervovaného příkonu na novou kapacitu{" "}
              <span style={{ color: "var(--muted)" }}>
                (jednosměrná změna smlouvy o připojení)
              </span>
            </span>
          </label>
          <div className="gs-pole">
            <label className="nb-label" htmlFor="ps-stridac">
              Max. výkon střídače <span style={{ fontWeight: 400 }}>(nepovinné)</span>
            </label>
            <div className="gs-unit">
              <input
                id="ps-stridac"
                className="nb-pole"
                value={maxVykonStridace}
                onChange={(e) => setMaxVykonStridace(e.target.value)}
                inputMode="decimal"
                placeholder="např. sdílený PCS"
              />
              <span className="gs-unit-txt">kW</span>
            </div>
          </div>
        </section>

        {/* 3) Co má baterie dělat – peak shaving / kombinace / spot */}
        <section className="gs-step">
          <span className="gs-step-num">3</span>
          <h4>Co má baterie dělat</h4>
          <div className="gs-step-sub">
            Kromě srážení špiček umí baterie obchodovat na spotovém trhu — nakupovat v levných
            hodinách a dodávat v drahých.
          </div>
          {REZIMY.map((r) => (
            <label key={r.klic} className="gs-volba">
              <input type="radio" checked={rezim === r.klic} onChange={() => setRezim(r.klic)} />
              <span>
                <b>{r.nazev}</b>
                <span style={{ color: "var(--muted)" }}> — {r.popis}</span>
              </span>
            </label>
          ))}
          {rezim !== "peak_shaving" && (
            <>
              <div className="gs-pole" style={{ marginTop: 10 }}>
                <label className="nb-label" htmlFor="ps-export">
                  Max. dodávka do sítě <span style={{ fontWeight: 400 }}>(nepovinné)</span>
                </label>
                <div className="gs-unit">
                  <input
                    id="ps-export"
                    className="nb-pole"
                    value={maxExport}
                    onChange={(e) => setMaxExport(e.target.value)}
                    inputMode="decimal"
                    placeholder="prázdné = výkon baterie, 0 = bez dodávky"
                  />
                  <span className="gs-unit-txt">kW</span>
                </div>
                <div className="gs-pozn">
                  Vybít do vlastní spotřeby je <b>cennější než dodat do sítě</b> — zákazník se
                  vyhne celé nákupní ceně včetně distribuce, kdežto za dodávku dostane jen spot
                  mínus marže obchodníka. Dodávka do sítě navíc potřebuje licenci a rezervovaný
                  výkon pro dodávku; zadej 0, pokud se má jen posouvat vlastní spotřeba.
                </div>
              </div>
              <div className="gs-pozn">
                Marže obchodníka i regulované složky za odebranou MWh se berou z výpočtových
                nastavení (admin). Model počítá <b>skutečnou cenu, kterou zákazník zaplatí a
                kterou dostane</b>, a odečítá opotřebení baterie obchodními cykly.
              </div>
              <div className="gs-pozn">
                Obchodní režimy počítají ~0,6 s na produkt (u každého měsíce se hledá nejlepší
                strop), takže u celého katalogu je to skoro minuta — <b>vyplatí se zúžit výběr
                baterií</b> v sekci níž.
              </div>
            </>
          )}
        </section>

        {/* 4) Které baterie počítat */}
        <section className="gs-step">
          <span className="gs-step-num">4</span>
          <h4>
            Baterie do výpočtu
            {katalogBaterii && <span className="nb-badge">{katalogBaterii.length}</span>}
          </h4>
          <div className="gs-step-sub">Míň produktů = rychlejší výpočet.</div>
          <label className="gs-volba">
            <input type="radio" checked={baterieIds === null} onChange={() => setBaterieIds(null)} />
            <span>Všechny dostupné z katalogu</span>
          </label>
          <label className="gs-volba">
            <input
              type="radio"
              checked={baterieIds !== null}
              onChange={() => setBaterieIds(baterieIds || [])}
            />
            <span>
              Jen ručně vybrané
              {baterieIds !== null && (
                <span style={{ color: "var(--muted)" }}> ({baterieIds.length} vybráno)</span>
              )}
            </span>
          </label>

          {baterieIds !== null && (
            <div className="nb-katalog" style={{ marginTop: 8 }}>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                <input
                  className="nb-pole"
                  value={hledaniBaterie}
                  onChange={(e) => setHledaniBaterie(e.target.value)}
                  placeholder="Hledat v katalogu…"
                  style={{ flex: "1 1 120px", minWidth: 110 }}
                  aria-label="Hledat baterii v katalogu"
                />
                <button
                  className="fm-btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={() => setBaterieIds(viditelneBaterie.map((b) => b.id))}
                >
                  Označit ({viditelneBaterie.length})
                </button>
                <button
                  className="fm-btn"
                  style={{ padding: "4px 10px", fontSize: 12 }}
                  onClick={() => setBaterieIds([])}
                >
                  Zrušit
                </button>
              </div>
              <div className="nb-katalog-seznam">
                {katalogBaterii === null && (
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>Načítám katalog…</div>
                )}
                {katalogBaterii !== null && viditelneBaterie.length === 0 && (
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    {katalogBaterii.length === 0
                      ? "V katalogu nejsou žádné dostupné baterie."
                      : "Hledání nic nenašlo."}
                  </div>
                )}
                {viditelneBaterie.map((b) => (
                  <label key={b.id} className="nb-katalog-radek">
                    <input
                      type="checkbox"
                      checked={baterieIds.includes(b.id)}
                      onChange={(e) =>
                        setBaterieIds((s) =>
                          e.target.checked ? [...s, b.id] : s.filter((x) => x !== b.id)
                        )
                      }
                    />
                    <span style={{ fontWeight: 600 }}>{b.nazev}</span>
                    <span style={{ color: "var(--muted)" }}>
                      {kw(b.vykon_kw)} / {b.kapacita_kwh?.toLocaleString("cs-CZ")} kWh ·{" "}
                      {kc(b.cena_kc)}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      {/* Patička panelu: akce + co ještě chybí */}
      <div className="gs-panel-f">
        <button className="fm-btn fm-primary" onClick={spocti} disabled={pocita || !vsePripraveno}>
          {pocita ? "Počítám…" : "Spočítat peak shaving"}
        </button>

        {/* Zakázané tlačítko samo neřekne, co chybí – proto tenhle seznam. */}
        <ul className="gs-chk" style={{ marginTop: 10 }}>
          <li className={profilOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">
              {profilOk ? "✓" : "!"}
            </span>
            <span>{profilOk ? "Profil odběru načtený" : "Načti 15min profil odběru"}</span>
          </li>
          <li className={rezOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">
              {rezOk ? "✓" : "!"}
            </span>
            <span>
              {rezOk ? "Rezervovaná kapacita zadaná" : "Zadej rezervovanou kapacitu z faktury"}
            </span>
          </li>
          <li className={sazbaOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">
              {sazbaOk ? "✓" : "!"}
            </span>
            <span>
              {sazbaOk
                ? `Sazby ${nazevDistributora} / ${hladina.toUpperCase()} vyplněné`
                : `Chybí sazby 2026 pro ${nazevDistributora} / ${hladina.toUpperCase()} — doplň je v Katalogu a výpočtech, nebo zvol jinou kombinaci`}
            </span>
          </li>
          {!vyberBateriiOk && (
            <li className="gs-chk-no">
              <span className="gs-chk-mark" aria-hidden="true">
                !
              </span>
              <span>Vyber aspoň jednu baterii (nebo přepni na celý katalog)</span>
            </li>
          )}
        </ul>

        {zprava && (
          <div style={{ color: "var(--fm-brand-dk)", fontSize: 12, marginTop: 8 }}>{zprava}</div>
        )}
        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 12, marginTop: 8 }}>{chyba}</div>}

        <div className="gs-pozn" style={{ marginTop: 10 }}>
          Vstupy se pamatují u nabídky —{" "}
          <a
            href="/manual?stranka=nabidkovac-peak-shaving"
            target="_blank"
            rel="noreferrer"
            style={{ color: "var(--brand-strong)" }}
            title="Návod k výpočtu: co která hodnota znamená, RK vs. RP, tři čísla návratnosti"
          >
            nápověda k výpočtu
          </a>
        </div>
      </div>
    </form>
  );

  // ==================== VÝSLEDEK (pravý sloupec) ====================
  let vysledekObsah;
  if (!vysledek) {
    vysledekObsah = (
      <div className="fm-card" style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: "var(--ink)" }}>
          Výsledek se objeví tady
        </div>
        <div style={{ fontSize: 12.5 }}>
          Vlevo doplň vstupy a spusť výpočet. Panel vlevo zůstane po ruce, takže půjde měnit
          rezervaci a hned vedle sledovat, co to udělá s návratností.
        </div>
      </div>
    );
  } else if (!dop) {
    vysledekObsah = (
      <div className="nb-warn" style={{ margin: 0 }}>
        <span>⚠️</span>
        <span>
          Výpočet nenašel použitelnou variantu. {(vysledek.upozorneni || []).join(" ")}
        </span>
      </div>
    );
  } else {
    vysledekObsah = (
      <>
        {/* --- hlavička výsledku + přepínače zobrazení --- */}
        <div className="gs-res-h">
          <div>
            <div className="gs-nadtitul">
              {vybranyIdx === 0 ? "Doporučená varianta" : "Vybraná varianta"}
              {varianty.length > 1 && poradiVybrane > 0 && (
                <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>
                  {" "}
                  — {poradiVybrane}. z {varianty.length}{" "}
                  {sloupecRazeni
                    ? `podle ${sloupecRazeni.nazev.toLowerCase()}`
                    : "podle NPV"}
                </span>
              )}
            </div>
            <h3>
              {dop.nazev} × {dop.pocet_kusu}
              {npvDop.doporuceno ? (
                <span className="nb-badge dobre">doporučeno</span>
              ) : (
                <span className="nb-badge spatne">
                  nad prahem {vysledek.max_navratnost_roky} let – nedoporučeno
                </span>
              )}
              {vybranyIdx !== 0 && (
                <span className="nb-badge pozor">
                  alternativa — doporučená je {varianty[0]?.nazev} × {varianty[0]?.pocet_kusu}
                </span>
              )}
            </h3>
          </div>
          <span className="gs-mezera" />
          <div className="gs-prepinace">
            <SegPrepinac
              popis="Rok"
              aria="Rok zobrazených hodnot"
              hodnota={rok}
              onZmena={setRokZobrazeni}
              volby={[
                { klic: 2026, nazev: "2026" },
                {
                  klic: 2027,
                  nazev: "2027",
                  zakazano: !ma2027,
                  title: ma2027 ? undefined : "Čeká se na oficiální sazby ERÚ",
                },
              ]}
            />
            <SegPrepinac
              popis="Návratnost z"
              aria="Z čeho počítat návratnost a NPV"
              hodnota={zakladNpv}
              onZmena={setZakladNpv}
              volby={ZAKLADY_NPV.map((z) => ({ klic: z.klic, nazev: z.nazev, title: z.popis }))}
            />
          </div>
        </div>

        {(vysledek.upozorneni || []).length > 0 && (
          <div className="nb-warn" style={{ margin: "0 0 12px" }}>
            <span>⚠️</span>
            <span>{vysledek.upozorneni.join(" ")}</span>
          </div>
        )}

        {/* --- KPI: hlavní čísla na první pohled --- */}
        <div className="gs-kpis">
          {spot && (
            <div className="gs-kpi accent">
              <div className="gs-kpi-label">Zisk z obchodu (rok)</div>
              <div className="gs-kpi-value">{kc(spot.zisk_kc)}</div>
              <div className="gs-kpi-sub">
                {`${Math.round(spot.zisk_kc_kwh_rok)} Kč/kWh baterie · ${Math.round(
                  spot.obchodnich_cyklu
                )} cyklů · po opotřebení ${kc(spot.naklad_opotrebeni_kc)}`}
              </div>
            </div>
          )}
          <div className="gs-kpi accent">
            <div className="gs-kpi-label">Roční úspora ({rok})</div>
            <div className="gs-kpi-value">
              {kc(je2027 ? uspora2027 : dop.rocni_uspora_2026_kc)}
            </div>
            <div className="gs-kpi-sub">
              {je2027
                ? ek27?.uspora_optimalizaci_bez_baterie != null
                  ? `z toho ${kc(ek27.uspora_optimalizaci_bez_baterie)} i bez investice`
                  : "modelový odhad NTS (výměr ERÚ ~11/2026)"
                : dop.uspora_bez_investice_2026_kc != null
                  ? `z toho bez investice ${kc(dop.uspora_bez_investice_2026_kc)}`
                  : "bez DPH"}
            </div>
          </div>
          <div className="gs-kpi">
            {/* Hlavní číslo = REÁLNÁ návratnost (ta, která rozhoduje o
                doporučení a mění se s přepínačem základu). Prostá návratnost
                je jen orientační – nezná O&M ani degradaci a počítá se vždy
                z celé úspory, takže se přepínačem nehnula a působilo to jako
                rozpor. */}
            <div className="gs-kpi-label">
              {navratnostDop?.druh === "prosta" ? "Návratnost (prostá)" : "Reálná návratnost"}
            </div>
            <div
              className="gs-kpi-value"
              title={navratnostTitulek(navratnostDop, dop.npv_horizont_roky)}
            >
              {navratnostDop?.druh === "prosta"
                ? roky(navratnostDop.hodnota)
                : navratnostText(navratnostDop)}
            </div>
            <div className="gs-kpi-sub">
              {navratnostDop?.druh === "odhad"
                ? `dopočet za horizont ${dop.npv_horizont_roky ?? 10} let · prostá ${roky(prostaNavratnost)} · práh ${vysledek.max_navratnost_roky} let`
                : navratnostDop?.druh === "prosta"
                  ? `úspora nepokryje ani O&M, reálná návratnost neexistuje · práh ${vysledek.max_navratnost_roky} let`
                  : `vč. O&M a degradace · prostá ${roky(prostaNavratnost)} · práh ${vysledek.max_navratnost_roky} let`}
            </div>
          </div>
          {npvDop.npv_kc != null && (
            <div className="gs-kpi">
              <div className="gs-kpi-label">NPV ({dop.npv_horizont_roky} let)</div>
              <div className="gs-kpi-value">{kc(npvDop.npv_kc)}</div>
              <div className="gs-kpi-sub">
                {npvDop.irr != null ? `IRR ${Math.round(npvDop.irr * 100)} % · ` : ""}
                {npvDop.pouzit_model_2027 === false
                  ? "chybí sazby 2027 → model 2026"
                  : "celý horizont NTS 2027"}
                {" · řídí výběr varianty"}
              </div>
            </div>
          )}
          {je2027 ? (
            <div className="gs-kpi">
              <div className="gs-kpi-label">Rezervovaný příkon</div>
              <div className="gs-kpi-value">{kw(rpNovy2027)}</div>
              <div className="gs-kpi-sub">
                {/* „snížení" jen když nové RP je opravdu nižší – optimalizace
                    nad maximy + rezervou umí vyjít i vyšší než dnešní RP. */}
                {ek27?.rp_soucasny_kw == null || rpNovy2027 === ek27.rp_soucasny_kw
                  ? "beze změny smlouvy · platí se RP + měsíční maxima"
                  : `${rpNovy2027 < ek27.rp_soucasny_kw ? "snížení" : "navýšení"} z ${kw(ek27.rp_soucasny_kw)}${
                      rpZeSmlouvy ? "" : " (= RK, příkon ze smlouvy nezadán)"
                    } · ${
                      ek27?.mesicu_s_prekrocenim_rp > 0
                        ? `záměrně pod špičku, překročení v ${ek27.mesicu_s_prekrocenim_rp} měs.`
                        : "platí se RP + měsíční maxima"
                    }`}
              </div>
            </div>
          ) : (
            <div className="gs-kpi">
              <div className="gs-kpi-label">Nová rez. kapacita</div>
              <div className="gs-kpi-value">{kw(dop.nova_rezervovana_kapacita_kw)}</div>
              <div className="gs-kpi-sub">
                {dop.strop_kw != null
                  ? `roční RK; strop baterie ${kw(dop.strop_kw)}, rezerva ${dop.rezerva_rk_procenta ?? 0} %`
                  : "sjednaný příkon po instalaci"}
              </div>
            </div>
          )}
          <div className="gs-kpi">
            <div className="gs-kpi-label">Investice</div>
            <div className="gs-kpi-value">{kc(dop.cena_celkem_kc)}</div>
            <div className="gs-kpi-sub">
              {kw(dop.celkovy_vykon_kw)} /{" "}
              {dop.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh · bez DPH
            </div>
          </div>
        </div>

        {/* --- tři varianty k rozhodnutí, každá podle jiného kritéria --- */}
        {kartyVariant.length > 1 && (
          <>
            <div className="gs-sekce-t" style={{ marginTop: 20 }}>
              Varianty k rozhodnutí
              <span className="gs-mezera" />
              <button
                className="fm-btn"
                style={{ padding: "4px 10px", fontSize: 12 }}
                onClick={() => setZalozka("varianty")}
              >
                Všech {varianty.length} v tabulce
              </button>
            </div>
            <div className="gs-varianty">
              {kartyVariant.map((k) => {
                const npv = npvDleZakladu(k.v, zakladNpv);
                const uspora = je2027
                  ? k.v.ekonomika_2027?.rocni_uspora_bez_aku ?? k.v.ekonomika_2027?.rocni_uspora
                  : k.v.rocni_uspora_2026_kc;
                const prosta = je2027
                  ? k.v.navratnost_2027 ?? k.v.navratnost_2027_konzerv
                  : k.v.navratnost_roky;
                const navratnost = navratnostKZobrazeni(npv, prosta);
                // Pruh má smysl jen když je vůbec nějaké kladné NPV, ke kterému
                // se dá poměřovat; záporná NPV se kreslí jako nulový pruh.
                const podil = npvMax > 0 ? Math.max(0, ((npv.npv_kc ?? 0) / npvMax) * 100) : null;
                return (
                  <button
                    type="button"
                    key={k.i}
                    className={"gs-varianta" + (k.i === vybranyIdx ? " vybrana" : "")}
                    onClick={() => vyberVariantu(k.i)}
                    title="Kliknutím se celý výsledek překreslí pro tuhle variantu"
                  >
                    <div className="gs-varianta-lb">
                      {k.kriteria.map((x) => x.popis).join(" · ")}
                      {!npv.doporuceno && <span className="nb-badge spatne">nad prahem</span>}
                    </div>
                    <h4>
                      {k.v.nazev} × {k.v.pocet_kusu}
                    </h4>
                    <div className="gs-varianta-spec">
                      {kw(k.v.celkovy_vykon_kw)} /{" "}
                      {k.v.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh · nová rezervace{" "}
                      {kw(novaRezervace(k.v))}
                    </div>
                    <dl>
                      <dt>Úspora {rok}</dt>
                      <dd className={k.i === vybranyIdx ? "hlavni" : undefined}>{kc(uspora)}</dd>
                      <dt>Investice</dt>
                      <dd>{kc(k.v.cena_celkem_kc)}</dd>
                      <dt>Návratnost</dt>
                      <dd title={navratnostTitulek(navratnost, k.v.npv_horizont_roky)}>
                        {navratnostText(navratnost)}
                      </dd>
                      <dt>NPV{npv.irr != null ? " / IRR" : ""}</dt>
                      <dd>
                        {npv.npv_kc != null ? kc(npv.npv_kc) : "—"}
                        {npv.irr != null ? ` · ${Math.round(npv.irr * 100)} %` : ""}
                      </dd>
                    </dl>
                    {podil != null && (
                      <>
                        <div className="gs-pruh">
                          <i style={{ width: `${Math.min(100, podil)}%` }} />
                        </div>
                        <div className="gs-pruh-popis">
                          <span>{k.kriteria[0].detail}</span>
                          <span>{Math.round(podil)} % NPV nejlepší</span>
                        </div>
                      </>
                    )}
                  </button>
                );
              })}
            </div>
          </>
        )}

        {/* --- záložky výsledku --- */}
        <div className="gs-tabs gs-tabs-odsazeni" role="tablist" aria-label="Části výsledku">
          {[
            { klic: "ekonomika", nazev: "Ekonomika" },
            ...(spot ? [{ klic: "spot", nazev: "Obchod na spotu" }] : []),
            { klic: "grafy", nazev: "Grafy odběru" },
            { klic: "varianty", nazev: "Srovnání variant", pocet: varianty.length },
            { klic: "roky", nazev: "Po letech" },
          ].map((z) => (
            <button
              key={z.klic}
              type="button"
              role="tab"
              aria-selected={zalozka === z.klic}
              onClick={() => setZalozka(z.klic)}
            >
              {z.nazev}
              {z.pocet > 1 && <span className="gs-tab-cnt"> ({z.pocet})</span>}
            </button>
          ))}
        </div>

        {/* ---------- záložka: ekonomika ---------- */}
        {zalozka === "ekonomika" && (
          <div role="tabpanel">
            <div className="gs-dve-karty">
              <div className={"fm-card gs-karta" + (je2027 ? " aktivni" : "")}>
                <div className="gs-karta-h">
                  <span className="gs-karta-nazev">2027</span>
                  <span className="nb-badge znacka">rozhoduje</span>
                  <span className="gs-mezera" />
                  {dop.ekonomika_2027?.je_modelovy_odhad && (
                    <span className="nb-badge pozor" title="Nezávazný odhad, ne finální cena ERÚ">
                      ⚠ modelový odhad
                    </span>
                  )}
                </div>
                <Ekonomika2027 dop={dop} rpJeFallbackRk={rpJeFallbackRk} />
              </div>

              <div className={"fm-card gs-karta" + (je2027 ? "" : " aktivni")}>
                <div className="gs-karta-h">
                  <span className="gs-karta-nazev">2026</span>
                  <span className="gs-mezera" />
                  <span
                    className="nb-badge"
                    title="Instalace i spuštění spadá už do NTS 2027 – tahle karta je jen srovnání „co by to bylo dnes“"
                  >
                    informativní
                  </span>
                </div>
                <Ekonomika2026 dop={dop} vysledek={vysledek} />
              </div>
            </div>

            <div className="gs-sekce-t">
              Tři čísla návratnosti
              <span className="gs-mezera" />
              <span className="nb-badge">práh doporučení {vysledek.max_navratnost_roky} let</span>
            </div>
            <div className="fm-card" style={{ padding: 0 }}>
              <table className="nb-table">
                <tbody>
                  {npvDop.payback_roky !== undefined && navratnostDop && (
                    <tr
                      className="soucet"
                      style={{ background: "color-mix(in srgb, var(--brand) 9%, transparent)" }}
                    >
                      <td>
                        Reálná{" "}
                        <span style={{ fontWeight: 400, color: "var(--muted)" }}>
                          — celý horizont v NTS 2027, z{" "}
                          {zakladNpv === "prinos_baterie" ? "přínosu baterie" : "celé roční úspory"},
                          vč. O&amp;M a degradace
                        </span>
                        <div className="gs-pozn">
                          Tohle rozhoduje o doporučení i o výběru varianty.
                          {navratnostDop.druh === "odhad" && (
                            <>
                              {" "}
                              Investice se do {dop.npv_horizont_roky ?? 10} let nevrátí — číslo je{" "}
                              <b>dopočtené za horizont modelu</b> z klesajícího cash flow posledních
                              let, takže je orientační.
                            </>
                          )}
                          {navratnostDop.druh === "prosta" && (
                            <>
                              {" "}
                              Roční úspora nepokryje ani provozní náklady, takže reálná návratnost
                              neexistuje — ukazuje se <b>prostá</b>, která O&amp;M ani degradaci
                              nezná.
                            </>
                          )}
                        </div>
                      </td>
                      <td
                        className="n"
                        style={{ fontSize: 15 }}
                        title={navratnostTitulek(navratnostDop, dop.npv_horizont_roky)}
                      >
                        {navratnostText(navratnostDop)}
                      </td>
                    </tr>
                  )}
                  {/* Starší uložené výsledky nesou navratnost_2027_konzerv (PS-3). */}
                  <tr>
                    <td>
                      Prostá 2027{" "}
                      <span style={{ color: "var(--muted)" }}>— cena ÷ úspora jednoho roku</span>
                    </td>
                    <td className="n">{roky(dop.navratnost_2027 ?? dop.navratnost_2027_konzerv)}</td>
                  </tr>
                  <tr>
                    <td className="dim">
                      Prostá 2026{" "}
                      <span style={{ color: "var(--muted)" }}>
                        — dnešní tarif, do rozhodování nevstupuje
                      </span>
                    </td>
                    <td className="n dim">{roky(dop.navratnost_2026 ?? dop.navratnost_roky)}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <details className="gs-meta" style={{ marginTop: 10 }}>
              <summary>Proč se čísla liší a co do rozhodování vstupuje</summary>
              <div className="gs-meta-in">
                Vítěznou variantu vybírá <b>NPV</b>, práh doporučení se poměřuje s{" "}
                <b>reálnou návratností</b> — obojí počítá <b>celý horizont v NTS 2027</b>, protože co
                se dnes nabízí, se instaluje a spouští už v nové struktuře. Základem je{" "}
                <b>{zakladPopis?.nazev}</b> ({zakladPopis?.popis}) — přepínač je v hlavičce
                výsledku, obě varianty jsou spočítané, přepnutí nic nepřepočítává. Reálné číslo je
                delší než prostá návratnost proto, že odečítá O&amp;M a degradaci úspor. Karta roku
                2026 je jen srovnávací základ „co by to bylo dnes“. Hodnoty 2027 jsou modelový odhad
                (závazný výměr ERÚ ~11/2026). Sleva AKU se dle definice ERÚ na peak-shavingovou
                baterii bez exportu nevztahuje.
                {dop.ekonomika_2027?.status === "spocitano" && (
                  <>
                    {" "}
                    <b>Tarif T1</b> (dražší paušál, levná špička) obvykle vyjde levněji při provozu
                    naplno blízko rezervovanému příkonu, <b>tarif T2</b> (levný paušál, drahá
                    špička) při utlumeném provozu nebo velké rezervě. Zákazník si tarif nevybírá,
                    distributor ho určuje automaticky každý měsíc podle skutečné spotřeby.
                  </>
                )}
              </div>
            </details>
          </div>
        )}

        {/* ---------- záložka: grafy ---------- */}
        {/* ---------- záložka: obchod na spotu ---------- */}
        {zalozka === "spot" && spot && (
          <div role="tabpanel">
            <div className="fm-card" style={{ marginBottom: 12 }}>
              <div className="gs-karta-h">
                <span className="gs-karta-nazev">Co obchod přinesl</span>
                <span className="gs-mezera" />
                <span className="nb-badge">
                  {`ceny ${spot.info_cen?.rok_cen ?? "?"} · ${
                    REZIMY.find((r) => r.klic === rezimVysledku)?.nazev ?? rezimVysledku
                  }`}
                </span>
              </div>
              <table className="fm-tabulka">
                <tbody>
                  <tr>
                    <td className="dim">Vyhnutý nákup a dodávka do sítě</td>
                    <td className="cislo">{kc(spot.zisk_energie_kc)}</td>
                  </tr>
                  <tr>
                    <td className="dim">
                      Opotřebení baterie obchodními cykly
                      <div className="gs-pozn">
                        {`${Math.round(spot.opotrebeni_kc_mwh)} Kč/MWh × ${Math.round(
                          spot.obchodni_vybito_kwh / 1000
                        ).toLocaleString("cs-CZ")} MWh`}
                      </div>
                    </td>
                    <td className="cislo">−{kc(spot.naklad_opotrebeni_kc)}</td>
                  </tr>
                  <tr className="soucet">
                    <td>Zisk z obchodu za rok</td>
                    <td className="cislo">{kc(spot.zisk_kc)}</td>
                  </tr>
                  <tr>
                    <td className="dim">Kdyby měl peak shaving absolutní prioritu</td>
                    <td className="cislo">{kc(spot.zisk_pri_prioritnim_ps_kc)}</td>
                  </tr>
                </tbody>
              </table>
              <div className="gs-pozn" style={{ padding: "0 14px 12px" }}>
                Model v každém měsíci porovnal, co vydělá víc: srazit špičku (a šetřit na platbě
                za výkon), nebo obchodovat. Rozdíl proti řádku „absolutní priorita" je to, co
                získal tím, že v některých měsících špičku vědomě pustil výš — celkový přínos je
                pak vždy vyšší, jinak by u nejnižšího stropu zůstal.
              </div>
            </div>

            <div className="fm-card" style={{ marginBottom: 12 }}>
              <div className="gs-karta-h">
                <span className="gs-karta-nazev">Energie</span>
              </div>
              <table className="fm-tabulka">
                <tbody>
                  <tr>
                    <td className="dim">Nabito ze sítě</td>
                    <td className="cislo">
                      {(spot.ze_site_kwh / 1000).toLocaleString("cs-CZ", {
                        maximumFractionDigits: 1,
                      })}{" "}
                      MWh
                    </td>
                  </tr>
                  <tr>
                    <td className="dim">Vybito do vlastní spotřeby</td>
                    <td className="cislo">
                      {(spot.do_odberu_kwh / 1000).toLocaleString("cs-CZ", {
                        maximumFractionDigits: 1,
                      })}{" "}
                      MWh
                    </td>
                  </tr>
                  <tr>
                    <td className="dim">Dodáno do sítě</td>
                    <td className="cislo">
                      {(spot.do_site_kwh / 1000).toLocaleString("cs-CZ", {
                        maximumFractionDigits: 1,
                      })}{" "}
                      MWh
                    </td>
                  </tr>
                  <tr>
                    <td className="dim">Obchodních cyklů za rok</td>
                    <td className="cislo">{Math.round(spot.obchodnich_cyklu)}</td>
                  </tr>
                </tbody>
              </table>
              <div className="gs-pozn" style={{ padding: "0 14px 12px" }}>
                Vybít do vlastní spotřeby je cennější než dodat do sítě: zákazník se vyhne celé
                nákupní ceně včetně distribuce, za dodávku dostane jen spot mínus marže
                obchodníka. U velkého odběru proto model do sítě téměř nedodává.
              </div>
            </div>

            <div className="fm-card">
              <div className="gs-karta-h">
                <span className="gs-karta-nazev">Rozhodnutí po měsících</span>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="fm-tabulka">
                  <thead>
                    <tr>
                      <th>Měsíc</th>
                      <th className="cislo">Cílový strop</th>
                      <th className="cislo">Nejnižší udržitelný</th>
                      <th className="cislo">Maximum bez baterie</th>
                      <th className="cislo">Zisk obchodu</th>
                      <th className="cislo">Při prioritě PS</th>
                      <th className="cislo">Cyklů</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(spot.mesice || []).map((m) => {
                      const pusteno = m.strop_kw > m.strop_nejnizsi_udrzitelny_kw + 0.5;
                      return (
                        <tr key={m.mesic}>
                          <td>
                            {MESICE_NAZVY[m.mesic - 1] || m.mesic}
                            {pusteno && (
                              <span className="nb-badge" style={{ marginLeft: 6 }}>
                                strop puštěn výš
                              </span>
                            )}
                          </td>
                          <td className="cislo">{kw(m.strop_kw)}</td>
                          <td className="cislo">{kw(m.strop_nejnizsi_udrzitelny_kw)}</td>
                          <td className="cislo">{kw(m.maximum_bez_baterie_kw)}</td>
                          <td className="cislo">{kc(m.zisk_obchodu_kc)}</td>
                          <td className="cislo">{kc(m.zisk_pri_nejnizsim_stropu_kc)}</td>
                          <td className="cislo">{Math.round(m.obchodnich_cyklu)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="gs-pozn" style={{ padding: "10px 14px 12px" }}>
                Cílový strop je maximum, na které se odběr v daném měsíci sráží. Kde je vyšší než
                nejnižší udržitelný, tam model usoudil, že obchod vydělá víc, než stojí vyšší
                platba za výkon — typicky v měsících, jejichž maximum roční rezervaci neurčuje.
              </div>
            </div>
          </div>
        )}

        {zalozka === "grafy" && (
          <div role="tabpanel">
            {graf ? (
              <div className="fm-card" style={{ padding: 0 }}>
                <div className="gs-karta-h">
                  <span style={{ fontSize: 13, fontWeight: 700 }}>
                    Odběr ze sítě — měsíční maxima
                  </span>
                  <span className="gs-mezera" />
                  <span className="nb-badge">
                    {je2027 ? "2027 · srážení po měsících" : "2026 · držení ročního stropu"}
                  </span>
                </div>
                <div style={{ padding: 14 }}>
                  <GrafOdberu
                    mesice={graf.mesice}
                    bezBaterie={graf.bez_baterie_kw}
                    sBaterii={je2027 ? graf.s_baterii_2027_kw : graf.s_baterii_2026_kw}
                    {...refCaryGrafu}
                  />
                </div>
              </div>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                {dopocitava
                  ? "Počítám graf pro tuhle variantu…"
                  : "Graf pro tuhle variantu zatím není — spusť „Spočítat peak shaving“ znovu."}
              </div>
            )}

            {citlivost && (
              <>
                <div className="gs-sekce-t">Citlivost návrhu na sílu roku</div>
                <div className="fm-card" style={{ padding: 14, fontSize: 12.5 }}>
                  Při profilu ±{citlivost.procenta} % by udržitelný strop byl{" "}
                  <b>
                    {kw(citlivost.strop_minus_kw)} až {kw(citlivost.strop_plus_kw)}
                  </b>
                  .{" "}
                  {citlivost.rezerva_pokryje_horni_scenar ? (
                    <>Rezerva RK ({kw(citlivost.strop_s_rezervou_kw)}) horní scénář pokryje.</>
                  ) : (
                    <>
                      Rezerva RK ({kw(citlivost.strop_s_rezervou_kw)}) horní scénář{" "}
                      <b>nepokryje</b> – při silnějším roce hrozí měsíční dokupy nebo pokuty.
                    </>
                  )}
                </div>
              </>
            )}

            {/* Průběh v čase – nitkový graf 15min simulace se zoomem */}
            <div className="gs-sekce-t">
              Průběh v čase
              <span style={{ fontWeight: 400, color: "var(--muted)" }}>
                (kdy baterie kryje špičku a kdy se dobíjí)
              </span>
              <span className="gs-mezera" />
              <button
                className="fm-btn"
                style={{ padding: "4px 10px", fontSize: 12 }}
                onClick={() => setPrubehOtevren((s) => !s)}
              >
                {prubehOtevren ? "Skrýt průběh" : "Zobrazit 15min simulaci roku"}
              </button>
            </div>
            {prubehOtevren ? (
              <div className="fm-card" style={{ padding: 14 }}>
                {prubehChyba && (
                  <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{prubehChyba}</div>
                )}
                {!prubeh && prubehNacita && (
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    Počítám 15min simulaci celého roku…
                  </div>
                )}
                {prubeh && (
                  <>
                    {prubehNacita && (
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>Přepočítávám…</div>
                    )}
                    <GrafPrubehu
                      key={`${prubeh.varianta_index}-${prubeh.rok}`}
                      data={prubeh}
                      popisRoku={
                        prubeh.rok === 2027
                          ? "Model 2027: baterie sráží špičku v každém měsíci tak hluboko, jak to zvládne (platí se za měsíční maximum)."
                          : "Model 2026: baterie drží jeden roční strop, na který je nasmlouvaná rezervovaná kapacita."
                      }
                    />
                    <div className="gs-pozn">
                      Za rok baterie dodala {prubeh.souhrn?.vybito_kwh?.toLocaleString("cs-CZ")} kWh,
                      ze sítě si na to vzala {prubeh.souhrn?.nabito_kwh?.toLocaleString("cs-CZ")} kWh
                      (ztráty cyklováním {prubeh.souhrn?.ztraty_kwh?.toLocaleString("cs-CZ")} kWh).
                      Špička odběru {kw(prubeh.souhrn?.max_odber_kw)} → ze sítě{" "}
                      {kw(prubeh.souhrn?.max_site_kw)}.
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="fm-card" style={{ padding: 14, fontSize: 12.5, color: "var(--muted)" }}>
                Nitkový graf se dopočítává na vyžádání — je to ~35 tisíc hodnot na variantu a rok.
              </div>
            )}
          </div>
        )}

        {/* ---------- záložka: srovnání variant ---------- */}
        {zalozka === "varianty" && (
          <div role="tabpanel">
            {varianty.length > 1 ? (
              <>
                <div className="fm-card" style={{ padding: 0 }}>
                  <div className="gs-karta-h">
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Srovnání variant</span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>
                      {zobrazeneVarianty.length} z {varianty.length} ·{" "}
                      {sloupecRazeni
                        ? `řazeno podle ${sloupecRazeni.nazev.toLowerCase()} ${
                            razeni.smer === "asc" ? "vzestupně" : "sestupně"
                          }`
                        : `řazeno podle NPV z ${
                            zakladNpv === "prinos_baterie" ? "přínosu baterie" : "celé úspory"
                          }`}
                    </span>
                    <span className="gs-mezera" />
                    {sloupecRazeni && (
                      <button
                        className="fm-btn"
                        style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => setRazeni({ klic: null, smer: "asc" })}
                      >
                        Zpět na doporučené pořadí
                      </button>
                    )}
                    {varianty.length > POCET_TOP_VARIANT && (
                      <button
                        className="fm-btn"
                        style={{ padding: "4px 10px", fontSize: 12 }}
                        onClick={() => {
                          // Zpět na užší výběr: když vybraná varianta mezi
                          // zobrazenými nezůstane, vrať se na první řádek.
                          const zustane = serazeneVarianty
                            .slice(0, POCET_TOP_VARIANT)
                            .some((x) => x.i === vybranyIdx);
                          if (vsechnyVarianty && !zustane) {
                            vyberVariantu(serazeneVarianty[0]?.i ?? 0);
                          }
                          setVsechnyVarianty((s) => !s);
                        }}
                      >
                        {vsechnyVarianty
                          ? `Jen ${POCET_TOP_VARIANT} nejlepší`
                          : `Zobrazit všechny (${varianty.length})`}
                      </button>
                    )}
                  </div>
                  <div className="nb-scroll" style={{ border: 0, borderRadius: 0, boxShadow: "none" }}>
                    <table className="nb-table">
                      <thead>
                        <tr>
                          {SLOUPCE_SROVNANI.map((s) => (
                            <th
                              key={s.klic}
                              className={s.cislo ? "n" : undefined}
                              onClick={() => prepniRazeni(s.klic)}
                              title="Kliknutím seřadíš podle tohoto sloupce"
                              style={{ cursor: "pointer", whiteSpace: "nowrap" }}
                            >
                              {/* Návratnost ve srovnání je REÁLNÁ (jede vždy na
                                  modelu 2027) – nemá tedy v hlavičce rok jako
                                  úspora, která se přepínačem roku mění. */}
                              {s.klic === "uspora"
                                ? `${s.nazev} (${rok})`
                                : s.klic === "navratnost"
                                  ? "Návratnost (reálná)"
                                  : s.nazev}
                              <span style={{ opacity: razeni.klic === s.klic ? 1 : 0.25 }}>
                                {" "}
                                {razeni.klic === s.klic && razeni.smer === "asc" ? "▲" : "▼"}
                              </span>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {zobrazeneVarianty.map(({ v, i }) => (
                          <VariantaRadek
                            key={`${v.baterie_id}-${v.pocet_kusu}`}
                            v={v}
                            rok={rok}
                            zakladNpv={zakladNpv}
                            vybrana={i === vybranyIdx}
                            onVyber={() => vyberVariantu(i)}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="gs-pozn">
                  <b>Kliknutím na řádek se celý výsledek překreslí pro danou variantu</b> (◄ =
                  zobrazená) — čísla jsou nad tabulkou, takže je změna hned vidět. Klik na záhlaví
                  sloupce mění řazení.
                  {!vsechnyVarianty && varianty.length > POCET_TOP_VARIANT && (
                    <> Spočítané jsou všechny baterie z výběru, tlačítkem výš je ukážeš všechny.</>
                  )}
                </div>
              </>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                Výpočet našel jen jednu použitelnou variantu — není co srovnávat.
              </div>
            )}
          </div>
        )}

        {/* ---------- záložka: ekonomika po letech ---------- */}
        {zalozka === "roky" && (
          <div role="tabpanel">
            {npvDop.roky?.length > 0 ? (
              <>
                <div className="fm-card" style={{ padding: 0 }}>
                  <div className="gs-karta-h">
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Ekonomika po letech</span>
                    <span className="gs-mezera" />
                    <span className="nb-badge">
                      horizont {dop.npv_horizont_roky ?? npvDop.roky.length} let
                    </span>
                  </div>
                  <div className="nb-scroll" style={{ border: 0, borderRadius: 0, boxShadow: "none" }}>
                    <table className="nb-table">
                      <thead>
                        <tr>
                          <th>Rok</th>
                          <th>Tarif</th>
                          <th className="n">Roční úspora</th>
                          <th className="n">O&amp;M</th>
                          <th className="n">CF roku</th>
                          <th className="n">Kum. úspora</th>
                          <th className="n">Kum. CF vč. investice</th>
                          <th className="n">Kum. disk. CF</th>
                        </tr>
                      </thead>
                      <tbody>
                        {npvDop.roky.map((r, i) => {
                          // ◄ = rok, kdy kumulovaný CF poprvé pokryje investici.
                          const paybackRok =
                            r.cf_kum_kc >= 0 && (i === 0 || npvDop.roky[i - 1].cf_kum_kc < 0);
                          return (
                            <tr
                              key={r.rok}
                              style={
                                paybackRok
                                  ? {
                                      fontWeight: 700,
                                      background: "color-mix(in srgb, var(--brand) 9%, transparent)",
                                    }
                                  : undefined
                              }
                            >
                              <td>
                                {r.rok}
                                {paybackRok ? " ◄" : ""}
                              </td>
                              <td>{r.model === "2027" ? "NTS 2027" : "2026"}</td>
                              <td className="n">{kc(r.prinos_kc)}</td>
                              <td className="n">{kc(r.oam_kc)}</td>
                              <td className="n">{kc(r.cf_kc)}</td>
                              <td className="n">{kc(r.uspora_kum_kc)}</td>
                              <td className="n">{kc(r.cf_kum_kc)}</td>
                              <td className="n">{kc(r.cf_kum_disk_kc)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="gs-pozn">
                  Roční úspora = celý rozdíl proti dnešnímu stavu v modelu NTS 2027 (celý horizont),
                  klesá degradací úspor; CF roku = úspora − O&amp;M. Řádek ◄ = kumulovaný CF poprvé
                  pokryje investici; poslední „Kum. disk. CF“ = NPV varianty.
                </div>
              </>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                Rozpis ekonomiky po letech se ukládá až od nové verze výpočtu — spusť „Spočítat peak
                shaving“ znovu.
              </div>
            )}
          </div>
        )}
      </>
    );
  }

  return (
    <div className="gs-desk">
      {panelVstupu}
      <div>{vysledekObsah}</div>
    </div>
  );
}
