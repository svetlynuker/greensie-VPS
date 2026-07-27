import { useEffect, useState } from "react";
import GrafOdberu from "./GrafOdberu";
import GrafPrubehu from "./GrafPrubehu";
import {
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
    hodnota: (v) => `${v.nazev} ${String(v.pocet_kusu ?? "").padStart(3, "0")}`,
  },
  {
    klic: "vykon",
    nazev: "Výkon / kapacita",
    vychoziSmer: "desc",
    hodnota: (v) => v.celkovy_vykon_kw ?? null,
  },
  {
    klic: "nova_rez",
    nazev: "Nová rez.",
    vychoziSmer: "asc",
    hodnota: (v) => v.nova_rezervovana_kapacita_kw ?? null,
  },
  {
    klic: "uspora",
    nazev: "Úspora/rok",
    vychoziSmer: "desc",
    hodnota: (v, i, je2027) =>
      je2027
        ? v.ekonomika_2027?.rocni_uspora_bez_aku ?? v.ekonomika_2027?.rocni_uspora ?? null
        : v.rocni_uspora_2026_kc ?? null,
  },
  { klic: "cena", nazev: "Cena", vychoziSmer: "asc", hodnota: (v) => v.cena_celkem_kc ?? null },
  {
    klic: "navratnost",
    nazev: "Návratnost",
    vychoziSmer: "asc",
    hodnota: (v, i, je2027) =>
      je2027 ? v.navratnost_2027 ?? v.navratnost_2027_konzerv ?? null : v.navratnost_roky ?? null,
  },
  { klic: "npv", nazev: "NPV", vychoziSmer: "desc", hodnota: (v) => v.npv_kc ?? null },
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

function VariantaRadek({ v, vybrana, rok, onVyber }) {
  // Úspora a návratnost dle přepínače roku (2027 = NTS odhad; starší uložené
  // výsledky nesou rocni_uspora_bez_aku / navratnost_2027_konzerv – PS-3).
  const je2027 = rok === 2027;
  const uspora = je2027
    ? v.ekonomika_2027?.rocni_uspora_bez_aku ?? v.ekonomika_2027?.rocni_uspora
    : v.rocni_uspora_2026_kc;
  const navratnost = je2027
    ? v.navratnost_2027 ?? v.navratnost_2027_konzerv
    : v.navratnost_roky;
  return (
    <tr
      onClick={onVyber}
      title="Kliknutím zobrazíš detail této varianty"
      style={{
        cursor: "pointer",
        ...(vybrana ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" } : {}),
      }}
    >
      <td>
        {vybrana ? "◄ " : ""}{v.nazev} × {v.pocet_kusu}
        {!v.doporuceno && (
          <span className="nb-badge" style={{ marginLeft: 6, color: "var(--st-crit)" }}>nedoporučeno</span>
        )}
      </td>
      <td>{kw(v.celkovy_vykon_kw)} / {v.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh</td>
      <td>{kw(v.nova_rezervovana_kapacita_kw)}</td>
      <td>{kc(uspora)}</td>
      <td>{kc(v.cena_celkem_kc)}</td>
      <td>{roky(navratnost)}</td>
      <td>{v.npv_kc != null ? kc(v.npv_kc) : "—"}</td>
    </tr>
  );
}

function RokPrepinac({ rok, ma2027, onZmena }) {
  const btn = { padding: "3px 12px", fontSize: 12, lineHeight: 1.5 };
  return (
    <span
      role="group"
      aria-label="Rok zobrazených hodnot"
      style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
    >
      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--fm-muted)" }}>Zobrazit rok</span>
      <span style={{ display: "inline-flex" }}>
        <button
          type="button"
          className="fm-btn"
          aria-pressed={rok === 2026}
          onClick={() => onZmena(2026)}
          style={{ ...btn, borderRadius: "9px 0 0 9px" }}
        >
          2026
        </button>
        <button
          type="button"
          className="fm-btn"
          aria-pressed={rok === 2027}
          onClick={() => onZmena(2027)}
          disabled={!ma2027}
          title={ma2027 ? undefined : "Čeká se na oficiální sazby ERÚ"}
          style={{ ...btn, borderRadius: "0 9px 9px 0", marginLeft: -1 }}
        >
          2027
        </button>
      </span>
    </span>
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
  // Varianta vybraná kliknutím ve srovnání (0 = doporučená).
  const [vybranyIdx, setVybranyIdx] = useState(0);
  // Srovnání: false = 3 nejlepší, true = celý katalog (manažerské rozhodnutí).
  const [vsechnyVarianty, setVsechnyVarianty] = useState(false);
  // Graf/citlivost dopočítané na kliknutí u variant mimo TOP 3: { index: {...} }.
  const [dopoctene, setDopoctene] = useState({});
  const [dopocitava, setDopocitava] = useState(false);
  // Rok zobrazených hodnot (dlaždice, graf, srovnání) – default 2027 (NTS).
  const [rokZobrazeni, setRokZobrazeni] = useState(2027);
  // Graf průběhu (15min řady) se stahuje zvlášť a až na vyžádání – je to
  // ~35 tisíc hodnot na variantu a rok. Cache podle varianty a roku.
  const [prubehOtevren, setPrubehOtevren] = useState(false);
  const [prubehy, setPrubehy] = useState({});
  const [prubehNacita, setPrubehNacita] = useState(false);
  const [prubehChyba, setPrubehChyba] = useState(null);
  // Řazení srovnání variant: klic = null → pořadí ze serveru (dle NPV sestupně).
  const [razeni, setRazeni] = useState({ klic: null, smer: "asc" });

  useEffect(() => {
    sazbySeznam().then(setSazby).catch((e) => setChyba(e.message));
    peakShavingProfilSouhrn(nabidka.id).then(setSouhrn).catch(() => setSouhrn({ pocet: 0 }));
    technologieSeznam()
      .then((t) => setKatalogBaterii(t.filter((x) => x.typ === "baterie" && x.dostupnost)))
      .catch(() => setKatalogBaterii([]));
  }, [nabidka.id]);

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
    };
    try {
      localStorage.setItem(KLIC_ULOZISTE(nabidka.id), JSON.stringify(data));
    } catch {
      // plné/zakázané úložiště nesmí shodit panel
    }
  }, [nabidka.id, distributor, hladina, rezKap, rezPrikon, snizeniRp, maxVykonStridace, baterieIds]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const sazba = (sazby || []).find(
    (s) => s.distributor === distributor && s.napetova_hladina === hladina && s.struktura_tarifu === "stara_2026"
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

  async function nactiProfil(dokId) {
    setZpracovavaId(dokId);
    setChyba(null);
    setZprava(null);
    try {
      const s = await profilZpracuj(dokId);
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
      });
      setVysledek(r.popis_json);
      setVybranyIdx(0);
      setDopoctene({});
      setPrubehy({}); // nový výpočet = staré průběhy už neplatí
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
  const rok = ma2027 ? rokZobrazeni : 2026;
  const je2027 = rok === 2027;
  const uspora2027 = ek27?.rocni_uspora_bez_aku ?? ek27?.rocni_uspora;
  const rpNovy2027 = ek27?.rp_novy_kw ?? ek27?.rezervovana_kapacita_kw;

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

  // Srovnání variant: bez zvoleného sloupce zůstává pořadí ze serveru (dle NPV
  // sestupně). Každý řádek si nese původní index – ten drží odkaz na variantu
  // pro detail i pro dopočet grafu na serveru.
  const sloupecRazeni = SLOUPCE_SROVNANI.find((s) => s.klic === razeni.klic) || null;
  const serazeneVarianty = varianty.map((v, i) => ({ v, i }));
  if (sloupecRazeni) {
    serazeneVarianty.sort((a, b) => {
      const x = sloupecRazeni.hodnota(a.v, a.i, je2027);
      const y = sloupecRazeni.hodnota(b.v, b.i, je2027);
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

  function prepniRazeni(klic) {
    const s = SLOUPCE_SROVNANI.find((x) => x.klic === klic);
    setRazeni((r) =>
      r.klic === klic
        ? { klic, smer: r.smer === "asc" ? "desc" : "asc" }
        : { klic, smer: s?.vychoziSmer || "asc" }
    );
  }
  // Zvýraznění karty vybraného roku v porovnání let.
  const kartaAktivni = { borderColor: "color-mix(in srgb, var(--brand) 45%, var(--line))" };

  return (
    <div className="fm-card" style={{ padding: 18 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>Peak shaving – výpočet</h3>

      {/* 1) Profil spotřeby */}
      <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 8px" }}>
        <b>1. Profil odběru.</b> Načti 15minutový profil z nahraného souboru (XLS/CSV export z portálu distributora).
      </p>
      {profilOk ? (
        <div style={{ fontSize: 13, marginBottom: 8 }}>
          ✅ Načteno <b>{souhrn.pocet.toLocaleString("cs-CZ")}</b> intervalů,{" "}
          {fmtDatumCas(souhrn.od)} – {fmtDatumCas(souhrn.do)}, špička <b>{kw(souhrn.max_kw)}</b>.
        </div>
      ) : (
        <div style={{ fontSize: 13, marginBottom: 8, color: "var(--fm-muted)" }}>
          Profil zatím není načtený.
        </div>
      )}
      {profilDoklady.length === 0 ? (
        <div className="nb-warn" style={{ margin: "0 0 12px" }}>
          <span>⚠️</span>
          <span>Nejdřív nahraj soubor se spotřebou (sekce Podklady výše).</span>
        </div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
          {profilDoklady.map((d) => (
            <button
              key={d.id}
              className="fm-btn"
              onClick={() => nactiProfil(d.id)}
              disabled={zpracovavaId === d.id}
            >
              {zpracovavaId === d.id ? "Načítám…" : `Načíst profil: ${d.puvodni_nazev}`}
            </button>
          ))}
        </div>
      )}

      {/* 2) Vstupy */}
      <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 8px" }}>
        <b>2. Parametry odběrného místa.</b>
      </p>
      <div className="nb-form-grid" style={{ marginBottom: 8 }}>
        <div>
          <label className="nb-label">Distributor</label>
          <select className="nb-pole" value={distributor} onChange={(e) => setDistributor(e.target.value)}>
            {DISTRIB.map((d) => <option key={d.klic} value={d.klic}>{d.nazev}</option>)}
          </select>
        </div>
        <div>
          <label className="nb-label">Napěťová hladina</label>
          <select className="nb-pole" value={hladina} onChange={(e) => setHladina(e.target.value)}>
            {HLADINY.map((h) => <option key={h.klic} value={h.klic}>{h.nazev}</option>)}
          </select>
        </div>
        <div>
          <label className="nb-label">Sjednaná rezervovaná kapacita (kW)</label>
          <input className="nb-pole" value={rezKap} onChange={(e) => setRezKap(e.target.value)} inputMode="decimal" placeholder="z faktury, např. 150" />
        </div>
        <div>
          <label className="nb-label">Rezervovaný příkon (kW, volit.)</label>
          <input className="nb-pole" value={rezPrikon} onChange={(e) => setRezPrikon(e.target.value)} inputMode="decimal" placeholder="ze smlouvy o připojení; pro model 2027" />
        </div>
        <div>
          <label className="nb-label">Max. výkon střídače (kW, volit.)</label>
          <input
            className="nb-pole"
            value={maxVykonStridace}
            onChange={(e) => setMaxVykonStridace(e.target.value)}
            inputMode="decimal"
            placeholder="omezí výkon baterie, např. sdílený PCS"
          />
        </div>
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 8 }}>
        <input type="checkbox" checked={snizeniRp} onChange={(e) => setSnizeniRp(e.target.checked)} />
        V modelu 2027 uvažovat snížení rezervovaného příkonu na novou kapacitu
        <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>(jednosměrná změna smlouvy o připojení)</span>
      </label>

      {/* 2b) Které baterie počítat */}
      <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "10px 0 6px" }}>
        <b>Baterie do výpočtu.</b> Míň produktů = rychlejší výpočet.
      </p>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, marginBottom: 6 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="radio"
            checked={baterieIds === null}
            onChange={() => setBaterieIds(null)}
          />
          Všechny dostupné z katalogu
          {katalogBaterii && <span style={{ color: "var(--fm-muted)" }}>({katalogBaterii.length})</span>}
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <input
            type="radio"
            checked={baterieIds !== null}
            onChange={() => setBaterieIds(baterieIds || [])}
          />
          Jen ručně vybrané
          {baterieIds !== null && (
            <span style={{ color: "var(--fm-muted)" }}>({baterieIds.length} vybráno)</span>
          )}
        </label>
      </div>

      {baterieIds !== null && (
        <div style={{ border: "1px solid var(--line)", borderRadius: 9, padding: 8, marginBottom: 10 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
            <input
              className="nb-pole"
              value={hledaniBaterie}
              onChange={(e) => setHledaniBaterie(e.target.value)}
              placeholder="Hledat v katalogu…"
              style={{ flex: "1 1 180px", minWidth: 140 }}
            />
            <button
              className="fm-btn"
              style={{ padding: "4px 10px", fontSize: 12 }}
              onClick={() => setBaterieIds(viditelneBaterie.map((b) => b.id))}
            >
              Označit zobrazené ({viditelneBaterie.length})
            </button>
            <button
              className="fm-btn"
              style={{ padding: "4px 10px", fontSize: 12 }}
              onClick={() => setBaterieIds([])}
            >
              Zrušit výběr
            </button>
          </div>
          <div style={{ maxHeight: 190, overflowY: "auto" }}>
            {katalogBaterii === null && (
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>Načítám katalog…</div>
            )}
            {katalogBaterii !== null && viditelneBaterie.length === 0 && (
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
                {katalogBaterii.length === 0
                  ? "V katalogu nejsou žádné dostupné baterie."
                  : "Hledání nic nenašlo."}
              </div>
            )}
            {viditelneBaterie.map((b) => (
              <label
                key={b.id}
                style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, padding: "2px 0" }}
              >
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
                <span style={{ color: "var(--fm-muted)" }}>
                  {kw(b.vykon_kw)} / {b.kapacita_kwh?.toLocaleString("cs-CZ")} kWh · {kc(b.cena_kc)}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
      {sazby && !sazbaOk && (
        <div className="nb-warn" style={{ margin: "0 0 12px" }}>
          <span>⚠️</span>
          <span>
            Pro {DISTRIB.find((d) => d.klic === distributor)?.nazev} / {hladina.toUpperCase()} nejsou
            vyplněné sazby 2026. Doplň je v Katalogu a výpočtech (sazby distributorů), nebo zvol jinou kombinaci.
          </span>
        </div>
      )}

      <button
        className="fm-btn fm-primary"
        onClick={spocti}
        disabled={pocita || !profilOk || !rezOk || !sazbaOk || !vyberBateriiOk}
      >
        {pocita ? "Počítám…" : "Spočítat peak shaving"}
      </button>
      {!vyberBateriiOk && (
        <span style={{ fontSize: 12, color: "var(--fm-muted)", marginLeft: 10 }}>
          Vyber aspoň jednu baterii (nebo přepni na celý katalog).
        </span>
      )}
      {zprava && <div style={{ color: "var(--fm-brand-dk)", fontSize: 13, marginTop: 10 }}>{zprava}</div>}
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}

      {/* 3) Výsledek */}
      {vysledek && (
        <div style={{ marginTop: 18 }}>
          {dop ? (
            <>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 10,
                  flexWrap: "wrap",
                  margin: "0 0 8px",
                }}
              >
                <h4 style={{ margin: 0, fontSize: 13 }}>
                  {vybranyIdx === 0 ? "Doporučená varianta" : "Vybraná varianta"}
                  {vybranyIdx !== 0 && (
                    <span className="nb-badge" style={{ marginLeft: 8, color: "color-mix(in srgb, var(--st-warn) 72%, var(--ink))" }}>
                      alternativa — doporučená je {varianty[0]?.nazev} × {varianty[0]?.pocet_kusu}
                    </span>
                  )}
                  {!dop.doporuceno && (
                    <span className="nb-badge" style={{ marginLeft: 8, color: "var(--st-crit)" }}>
                      nad prahem {vysledek.max_navratnost_roky}&nbsp;let – nedoporučeno
                    </span>
                  )}
                </h4>
                <RokPrepinac rok={rok} ma2027={ma2027} onZmena={setRokZobrazeni} />
              </div>
              {/* KPI přehled doporučené varianty — hlavní čísla na první pohled */}
              <div className="gs-kpis" style={{ marginBottom: 12 }}>
                <div className="gs-kpi accent">
                  <div className="gs-kpi-label">Roční úspora ({rok})</div>
                  <div className="gs-kpi-value">{kc(je2027 ? uspora2027 : dop.rocni_uspora_2026_kc)}</div>
                  <div className="gs-kpi-sub">
                    {je2027
                      ? "modelový odhad NTS (výměr ERÚ ~11/2026)"
                      : dop.uspora_bez_investice_2026_kc != null
                        ? `z toho bez investice ${kc(dop.uspora_bez_investice_2026_kc)}`
                        : "bez DPH"}
                  </div>
                </div>
                <div className="gs-kpi">
                  <div className="gs-kpi-label">Návratnost ({rok})</div>
                  <div className="gs-kpi-value">
                    {roky(
                      je2027
                        ? dop.navratnost_2027 ?? dop.navratnost_2027_konzerv
                        : dop.navratnost_2026 ?? dop.navratnost_roky
                    )}
                  </div>
                  <div className="gs-kpi-sub">
                    {je2027
                      ? `z úspory 2027 · práh ${vysledek.max_navratnost_roky} let`
                      : dop.prinos_baterie_2026_kc != null
                        ? `z přínosu baterie · práh ${vysledek.max_navratnost_roky} let`
                        : `práh doporučení ${vysledek.max_navratnost_roky} let`}
                  </div>
                </div>
                {je2027 ? (
                  <div className="gs-kpi">
                    <div className="gs-kpi-label">Rezervovaný příkon</div>
                    <div className="gs-kpi-value">{kw(rpNovy2027)}</div>
                    <div className="gs-kpi-sub">
                      {ek27?.mesicu_s_prekrocenim_rp > 0
                        ? `snížení z ${kw(ek27.rp_soucasny_kw)} · záměrně pod špičku, překročení v ${ek27.mesicu_s_prekrocenim_rp} měs.`
                        : ek27?.rp_soucasny_kw != null && rpNovy2027 !== ek27.rp_soucasny_kw
                        ? `snížení z ${kw(ek27.rp_soucasny_kw)} · platí se RP + měsíční maxima`
                        : "beze změny smlouvy · platí se RP + měsíční maxima"}
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
                  <div className="gs-kpi-label">Baterie</div>
                  <div className="gs-kpi-value" style={{ fontSize: 18 }}>
                    {dop.nazev} × {dop.pocet_kusu}
                  </div>
                  <div className="gs-kpi-sub">
                    {kw(dop.celkovy_vykon_kw)} / {dop.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh · {kc(dop.cena_celkem_kc)}
                  </div>
                </div>
                {dop.npv_kc != null && (
                  <div className="gs-kpi">
                    <div className="gs-kpi-label">NPV ({dop.npv_horizont_roky} let)</div>
                    <div className="gs-kpi-value">{kc(dop.npv_kc)}</div>
                    <div className="gs-kpi-sub">
                      {dop.irr != null ? `IRR ${Math.round(dop.irr * 100)} % · ` : ""}
                      {dop.npv_pouzit_model_2027 ? "rok 1 tarif 2026, dál NTS 2027" : "celý horizont model 2026"}
                      {" · řídí výběr varianty"}
                    </div>
                  </div>
                )}
              </div>

              <div className="fm-card" style={{ padding: 14, marginBottom: 14 }}>
                <div style={{ marginTop: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Návratnost investice dle modelu</div>
                  <table className="nb-table">
                    <tbody>
                      <tr><td>Model 2026 (dnešní tarif)</td><td><b>{roky(dop.navratnost_2026 ?? dop.navratnost_roky)}</b></td></tr>
                      {/* Starší uložené výsledky nesou navratnost_2027_konzerv (PS-3). */}
                      <tr><td>Model 2027 (nová struktura ERÚ)</td><td>{roky(dop.navratnost_2027 ?? dop.navratnost_2027_konzerv)}</td></tr>
                    </tbody>
                  </table>
                  <div style={{ fontSize: 11, color: "color-mix(in srgb, var(--st-warn) 72%, var(--ink))", marginTop: 4 }}>
                    Výběr varianty se řídí modelem 2026. Hodnoty 2027 jsou modelový odhad (závazný výměr ERÚ ~11/2026).
                    Sleva AKU se dle definice ERÚ na peak-shavingovou baterii bez exportu nevztahuje.
                  </div>
                </div>
              </div>

              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Ekonomika – porovnání let</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12, marginBottom: 12 }}>
                {/* Rok 2026 */}
                <div className="fm-card" style={{ padding: 14, ...(je2027 ? {} : kartaAktivni) }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>Rok 2026</div>
                  {dop.ekonomika_2026?.uspora_bez_investice != null ? (
                    /* Rozpad úspory (PS-7): audit RK zdarma + přínos baterie. */
                    <table className="nb-table">
                      <tbody>
                        <tr><td>Roční náklad dnes (RK {kw(vysledek.vstup?.rezervovana_kapacita_kw)})</td><td>{kc(dop.ekonomika_2026.soucasny_naklad_celkem)}</td></tr>
                        <tr>
                          <td>Optimalizace RK bez baterie</td>
                          <td>
                            {kc(dop.ekonomika_2026.naklad_optimalni_bez_baterie)}
                            <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>
                              {" "}(roční RK {kw(dop.ekonomika_2026.optimalni_rk_bez_baterie_kw)}
                              {dop.ekonomika_2026.dokupy_bez_baterie_pocet_mesicu > 0
                                ? ` + měsíční RK v ${dop.ekonomika_2026.dokupy_bez_baterie_pocet_mesicu} měs.`
                                : ""})
                            </span>
                          </td>
                        </tr>
                        <tr><td><b>Úspora hned bez investice</b></td><td><b>{kc(dop.ekonomika_2026.uspora_bez_investice)}</b></td></tr>
                        <tr>
                          <td>Náklad s baterií</td>
                          <td>
                            {kc(dop.ekonomika_2026.novy_naklad_rezervace)}
                            {dop.ekonomika_2026.naklad_ztrat_baterie > 0 && (
                              <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>
                                {" "}+ ztráty {kc(dop.ekonomika_2026.naklad_ztrat_baterie)}
                              </span>
                            )}
                          </td>
                        </tr>
                        <tr><td><b>Přínos baterie</b></td><td><b>{kc(dop.ekonomika_2026.prinos_baterie)}</b></td></tr>
                        <tr><td><b>Celková roční úspora</b></td><td><b>{kc(dop.ekonomika_2026.rocni_uspora)}</b></td></tr>
                      </tbody>
                    </table>
                  ) : (
                    /* Starší uložené výsledky (před PS-7). */
                    <table className="nb-table">
                      <tbody>
                        <tr><td>Roční náklad bez peak shavingu</td><td>{kc(dop.ekonomika_2026?.soucasny_naklad_celkem)}</td></tr>
                        <tr><td>Roční náklad s peak shavingem</td><td>{kc(dop.ekonomika_2026?.novy_naklad_rezervace)}</td></tr>
                        {dop.ekonomika_2026?.naklad_ztrat_baterie > 0 && (
                          <tr><td>− ztráty baterie (cyklování)</td><td>{kc(dop.ekonomika_2026.naklad_ztrat_baterie)}</td></tr>
                        )}
                        <tr><td><b>Roční úspora</b></td><td><b>{kc(dop.ekonomika_2026?.rocni_uspora)}</b></td></tr>
                      </tbody>
                    </table>
                  )}
                  <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 6 }}>
                    Návratnost baterie se počítá z jejího přínosu proti optimalizované RK
                    (kombinace roční + měsíční RK) — úsporu z pouhého snížení RK klient
                    získá i bez investice.
                  </div>
                </div>

                {/* Rok 2027 */}
                <div className="fm-card" style={{ padding: 14, ...(je2027 ? kartaAktivni : {}) }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    Rok 2027
                    {dop.ekonomika_2027?.je_modelovy_odhad && (
                      <span className="nb-badge" style={{ color: "color-mix(in srgb, var(--st-warn) 72%, var(--ink))" }} title="Nezávazný odhad, ne finální cena ERÚ">
                        ⚠ modelový odhad
                      </span>
                    )}
                  </div>
                  {dop.ekonomika_2027?.status === "spocitano" ? (
                    <>
                      <table className="nb-table">
                        <tbody>
                          {/* Starší uložené výsledky (před PS-3) nesou *_bez_aku – zobrazí se
                              konzervativní čísla; sleva AKU pro BTM baterii neexistuje. */}
                          <tr><td>Roční náklad dnes (RP {kw(dop.ekonomika_2027.rp_soucasny_kw)})</td><td>{kc(dop.ekonomika_2027.soucasny_rocni_naklad)}</td></tr>
                          {/* Třetí výpočet: nejlevnější RP bez baterie (fér baseline 2027). */}
                          {dop.ekonomika_2027.naklad_optimalni_bez_baterie != null && (
                            <>
                              <tr>
                                <td>Optimalizace RP bez baterie</td>
                                <td>
                                  {kc(dop.ekonomika_2027.naklad_optimalni_bez_baterie)}
                                  <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>
                                    {" "}(RP {kw(dop.ekonomika_2027.optimalni_rp_bez_baterie_kw)})
                                  </span>
                                </td>
                              </tr>
                              <tr><td><b>Úspora hned bez investice</b></td><td><b>{kc(dop.ekonomika_2027.uspora_optimalizaci_bez_baterie)}</b></td></tr>
                            </>
                          )}
                          <tr><td>Roční náklad s peak shavingem</td><td>{kc(dop.ekonomika_2027.novy_rocni_naklad_bez_aku ?? dop.ekonomika_2027.novy_rocni_naklad)}</td></tr>
                          {dop.ekonomika_2027.mesicu_s_prekrocenim_rp > 0 && (
                            <tr>
                              <td>… z toho vědomé překročení RP</td>
                              <td>
                                {kc(dop.ekonomika_2027.naklad_prekroceni_rp)}
                                <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>
                                  {" "}(v {dop.ekonomika_2027.mesicu_s_prekrocenim_rp} měs. – nižší RP
                                  se i s penalizací vyplatí)
                                </span>
                              </td>
                            </tr>
                          )}
                          {dop.ekonomika_2027.prinos_baterie != null && (
                            <tr><td><b>Přínos baterie</b></td><td><b>{kc(dop.ekonomika_2027.prinos_baterie)}</b></td></tr>
                          )}
                          {dop.ekonomika_2027.naklad_ztrat_baterie > 0 && (
                            <tr><td>… z toho ztráty baterie</td><td>{kc(dop.ekonomika_2027.naklad_ztrat_baterie)}</td></tr>
                          )}
                          <tr><td><b>Roční úspora</b></td><td><b>{kc(dop.ekonomika_2027.rocni_uspora_bez_aku ?? dop.ekonomika_2027.rocni_uspora)}</b></td></tr>
                          <tr><td>Měsíců na tarifu T1 / T2</td><td>{dop.ekonomika_2027.pocet_mesicu_t1} / {dop.ekonomika_2027.pocet_mesicu_t2}</td></tr>
                          {dop.ekonomika_2027.rp_soucasny_kw != null && (
                            <tr>
                              <td>Rezervovaný příkon (RP)</td>
                              <td>
                                {kw(dop.ekonomika_2027.rp_soucasny_kw)}
                                {dop.ekonomika_2027.rp_novy_kw !== dop.ekonomika_2027.rp_soucasny_kw
                                  ? ` → ${kw(dop.ekonomika_2027.rp_novy_kw)} (snížení)`
                                  : " (beze změny smlouvy)"}
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                      <div style={{ fontSize: 11, color: "color-mix(in srgb, var(--st-warn) 72%, var(--ink))", marginTop: 6 }}>
                        Modelový odhad, ne finální cena ERÚ (závazné rozhodnutí ~11/2026). Bez slevy AKU –
                        dle ERÚ se počítá z toku na předávacím místě a pro baterii uvnitř odběru vychází nulová.
                      </div>
                    </>
                  ) : (
                    <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>Čeká se na oficiální sazby ERÚ.</div>
                  )}
                </div>
              </div>

              {dop.ekonomika_2027?.status === "spocitano" && (
                <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 14px", lineHeight: 1.5 }}>
                  <b>Tarif T1</b> (dražší paušál, levná špička) obvykle vyjde levněji při provozu naplno blízko rezervovanému příkonu.{" "}
                  <b>Tarif T2</b> (levný paušál, drahá špička) vyjde levněji při utlumeném provozu nebo velké rezervě.{" "}
                  Zákazník si tarif nevybírá, distributor ho určuje automaticky každý měsíc podle skutečné spotřeby.
                </p>
              )}

              {graf && (
                <>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Odběr ze sítě – měsíční maxima</h4>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                      {je2027 ? "Rok 2027 (srážení po měsících)" : "Rok 2026 (držení ročního stropu)"}
                    </div>
                    <GrafOdberu
                      mesice={graf.mesice}
                      bezBaterie={graf.bez_baterie_kw}
                      sBaterii={je2027 ? graf.s_baterii_2027_kw : graf.s_baterii_2026_kw}
                      rpSoucasna={graf.rp_soucasna_kw}
                      rpNova={graf.rp_nova_kw}
                    />
                  </div>
                </>
              )}
              {!graf && vybranyIdx !== 0 && (
                <div style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 14px" }}>
                  {dopocitava
                    ? "Počítám graf pro tuhle variantu…"
                    : "Graf pro tuhle variantu zatím není — spusť „Spočítat peak shaving“ znovu."}
                </div>
              )}

              {/* Průběh v čase – nitkový graf 15min simulace se zoomem */}
              <div style={{ marginBottom: 16 }}>
                <div
                  style={{
                    display: "flex", alignItems: "center", justifyContent: "space-between",
                    gap: 10, flexWrap: "wrap", marginBottom: 6,
                  }}
                >
                  <h4 style={{ margin: 0, fontSize: 13 }}>
                    Průběh v čase{" "}
                    <span style={{ fontWeight: 400, color: "var(--fm-muted)" }}>
                      (15min simulace – kdy baterie kryje špičku a kdy se dobíjí)
                    </span>
                  </h4>
                  <button
                    className="fm-btn"
                    style={{ padding: "4px 10px", fontSize: 12 }}
                    onClick={() => setPrubehOtevren((s) => !s)}
                  >
                    {prubehOtevren ? "Skrýt průběh" : "Zobrazit průběh v čase"}
                  </button>
                </div>
                {prubehOtevren && (
                  <>
                    {prubehChyba && (
                      <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{prubehChyba}</div>
                    )}
                    {!prubeh && prubehNacita && (
                      <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
                        Počítám 15min simulaci celého roku…
                      </div>
                    )}
                    {prubeh && (
                      <>
                        {prubehNacita && (
                          <div style={{ fontSize: 11, color: "var(--fm-muted)" }}>Přepočítávám…</div>
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
                        <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 6 }}>
                          Za rok baterie dodala {prubeh.souhrn?.vybito_kwh?.toLocaleString("cs-CZ")} kWh,
                          ze sítě si na to vzala {prubeh.souhrn?.nabito_kwh?.toLocaleString("cs-CZ")} kWh
                          (ztráty cyklováním {prubeh.souhrn?.ztraty_kwh?.toLocaleString("cs-CZ")} kWh).
                          Špička odběru {kw(prubeh.souhrn?.max_odber_kw)} → ze sítě {kw(prubeh.souhrn?.max_site_kw)}.
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>

              {citlivost && (
                <div style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 14px" }}>
                  <b>Citlivost návrhu (PS-10):</b> při profilu ±{citlivost.procenta} %
                  by udržitelný strop byl {kw(citlivost.strop_minus_kw)} až{" "}
                  {kw(citlivost.strop_plus_kw)}.{" "}
                  {citlivost.rezerva_pokryje_horni_scenar
                    ? `Rezerva RK (${kw(citlivost.strop_s_rezervou_kw)}) horní scénář pokryje.`
                    : `Rezerva RK (${kw(citlivost.strop_s_rezervou_kw)}) horní scénář nepokryje – při silnějším roce hrozí měsíční dokupy/pokuty.`}
                </div>
              )}

              {dop.roky?.length > 0 ? (
                <>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>
                    Ekonomika po letech (horizont {dop.npv_horizont_roky ?? dop.roky.length} let)
                  </h4>
                  <div className="nb-scroll">
                    <table className="nb-table">
                      <thead>
                        <tr>
                          <th>Rok</th>
                          <th>Tarif</th>
                          <th>Přínos baterie</th>
                          <th>O&M</th>
                          <th>CF roku</th>
                          <th>Kum. úspora</th>
                          <th>Kum. CF vč. investice</th>
                          <th>Kum. disk. CF</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dop.roky.map((r, i) => {
                          // ◄ = rok, kdy kumulovaný CF poprvé pokryje investici.
                          const paybackRok = r.cf_kum_kc >= 0 && (i === 0 || dop.roky[i - 1].cf_kum_kc < 0);
                          return (
                            <tr
                              key={r.rok}
                              style={paybackRok ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" } : undefined}
                            >
                              <td>{r.rok}{paybackRok ? " ◄" : ""}</td>
                              <td>{r.model === "2027" ? "NTS 2027" : "2026"}</td>
                              <td>{kc(r.prinos_kc)}</td>
                              <td>{kc(r.oam_kc)}</td>
                              <td>{kc(r.cf_kc)}</td>
                              <td>{kc(r.uspora_kum_kc)}</td>
                              <td>{kc(r.cf_kum_kc)}</td>
                              <td>{kc(r.cf_kum_disk_kc)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--fm-muted)", margin: "4px 0 14px" }}>
                    Přínos baterie = úspora proti optimalizované RK (rok 1 dle tarifu 2026, dál model
                    NTS 2027), klesá degradací úspor; CF roku = přínos − O&M. Řádek ◄ = kumulovaný CF
                    poprvé pokryje investici; poslední „Kum. disk. CF“ = NPV varianty.
                  </div>
                </>
              ) : (
                <div style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 14px" }}>
                  Rozpis ekonomiky po letech se ukládá až od nové verze výpočtu — spusť „Spočítat peak shaving“ znovu.
                </div>
              )}

              {varianty.length > 1 && (
                <>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                      flexWrap: "wrap",
                      margin: "0 0 6px",
                    }}
                  >
                    <h4 style={{ margin: 0, fontSize: 13 }}>
                      Srovnání variant{" "}
                      <span style={{ fontWeight: 400, color: "var(--fm-muted)" }}>
                        ({zobrazeneVarianty.length} z {varianty.length})
                      </span>
                    </h4>
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
                          ? `Zobrazit jen ${POCET_TOP_VARIANT} nejlepší`
                          : `Zobrazit všechny baterie (${varianty.length})`}
                      </button>
                    )}
                  </div>
                  <div className="nb-scroll">
                    <table className="nb-table">
                      <thead>
                        <tr>
                          {SLOUPCE_SROVNANI.map((s) => (
                            <th
                              key={s.klic}
                              onClick={() => prepniRazeni(s.klic)}
                              title="Kliknutím seřadíš podle tohoto sloupce"
                              style={{ cursor: "pointer", whiteSpace: "nowrap" }}
                            >
                              {s.klic === "uspora" || s.klic === "navratnost"
                                ? `${s.nazev} (${rok})`
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
                            vybrana={i === vybranyIdx}
                            onVyber={() => vyberVariantu(i)}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 4 }}>
                    <b>Kliknutím na řádek se celý detail (čísla, ekonomika, grafy) překreslí pro danou variantu</b> (◄ = zobrazená).
                    {" "}Klik na záhlaví sloupce mění řazení
                    {sloupecRazeni ? (
                      <>
                        {" "}(teď: <b>{sloupecRazeni.nazev}</b>{" "}
                        {razeni.smer === "asc" ? "vzestupně" : "sestupně"} —{" "}
                        <button
                          className="fm-btn"
                          style={{ padding: "0 6px", fontSize: 11 }}
                          onClick={() => setRazeni({ klic: null, smer: "asc" })}
                        >
                          zpět na doporučené pořadí
                        </button>
                        )
                      </>
                    ) : (
                      <> (teď doporučené pořadí dle NPV)</>
                    )}
                    .
                    {!vsechnyVarianty && varianty.length > POCET_TOP_VARIANT && (
                      <>
                        {" "}Spočítané jsou všechny baterie z výběru – tlačítkem výš je ukážeš všechny.
                      </>
                    )}
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="nb-warn" style={{ margin: 0 }}>
              <span>⚠️</span>
              <span>Výpočet nenašel použitelnou variantu. {(vysledek.upozorneni || []).join(" ")}</span>
            </div>
          )}
          {dop && (vysledek.upozorneni || []).length > 0 && (
            <div style={{ fontSize: 12, color: "var(--fm-muted)", marginTop: 10 }}>
              {vysledek.upozorneni.map((u, i) => <div key={i}>• {u}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
