import { useEffect, useState } from "react";
import GrafOdberu from "./GrafOdberu";
import GrafPrubehuPpa from "./GrafPrubehuPpa";
import GrafVyrobaSpotreba from "./GrafVyrobaSpotreba";
import {
  crmOdbernaMistaNabidky,
  crmPouzijDiagramProNabidku,
  ppaBessKatalog,
  ppaBessKatalogStav,
  ppaBessProfilSouhrn,
  ppaBessPrubeh,
  ppaBessVypocet,
  nabidkaDetail,
  profilZpracuj,
} from "../api";

/**
 * Panel výpočtu PPA + BESS.
 *
 * Odpovídá na otázku, kterou nabídkovač dosud neumí zodpovědět: kdy se baterie
 * vyplatí na srážení špiček a kdy na zvýšení samospotřeby. Ukazuje proto rozpad
 * přínosu na kilowatty a kilowatthodiny a všechny tři režimy vedle sebe.
 *
 * Zdroj pravdy pro výpočet: `backend/app/nabidkovac/ppa_bess.py`.
 */

// ---------------------------------------------------------------- formátovače
const kc = (x) =>
  x === null || x === undefined
    ? "—"
    : `${Math.round(x).toLocaleString("cs-CZ")} Kč`;
const kcMwh = (x) =>
  x === null || x === undefined ? "—" : `${Math.round(x).toLocaleString("cs-CZ")} Kč/MWh`;
const mwh = (x, des = 1) =>
  x === null || x === undefined ? "—" : `${Number(x).toLocaleString("cs-CZ", { maximumFractionDigits: des })} MWh`;
const kw = (x, des = 0) =>
  x === null || x === undefined ? "—" : `${Number(x).toLocaleString("cs-CZ", { maximumFractionDigits: des })} kW`;
const pct = (x, des = 1) =>
  x === null || x === undefined ? "—" : `${(Number(x) * 100).toFixed(des)} %`;
const cislo = (x, des = 2) =>
  x === null || x === undefined ? "—" : Number(x).toLocaleString("cs-CZ", { maximumFractionDigits: des });

function fmtDatumCas(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}` : "";
}

/** Vstup → číslo (čárka jako desetinná, prázdné → null). */
function n(v) {
  const s = String(v ?? "").trim().replace(",", ".");
  if (s === "") return null;
  const x = Number(s);
  return Number.isFinite(x) ? x : null;
}

const DISTRIB = [
  { klic: "cez", nazev: "ČEZ Distribuce" },
  { klic: "egd", nazev: "EG.D" },
  { klic: "pre", nazev: "PREdistribuce" },
];
const HLADINY = [
  { klic: "vn", nazev: "VN" },
  { klic: "vvn", nazev: "VVN" },
];
const MESICE_NAZVY = [
  "leden", "únor", "březen", "duben", "květen", "červen",
  "červenec", "srpen", "září", "říjen", "listopad", "prosinec",
];

const KLIC_ULOZISTE = (nabidkaId) => `gs-ppabess-vstup-${nabidkaId}`;

/** Předvyplnění: základ z posledního uloženého řešení, navrch localStorage. */
function nactiUlozeneVstupy(nabidka) {
  const rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "ppa_bess");
  const posl = rr.length ? rr[rr.length - 1].popis_json : null;
  const v = (posl && posl.vstup) || {};
  const zaklad = {
    distributor: v.distributor || "cez",
    hladina: v.napetova_hladina || "vn",
    rezKapacita: v.rezervovana_kapacita_kw ?? "",
    rezPrikon: v.rezervovany_prikon_kw ?? "",
    cenaSilova: v.cena_silova_kc_mwh ?? "",
    regulovane: v.vyhnutelne_regulovane_kc_mwh ?? "",
    maxKwp: v.max_kwp ?? "",
    cilSs: v.cil_mira_samospotreby ? String(Math.round(v.cil_mira_samospotreby * 100)) : "80",
    sklon: v.sklon_st ?? "35",
    azimut: v.azimut_st ?? "0",
    cenaExportu: v.cena_exportu_kc_mwh ?? "",
    rezVykonDodavky: v.rezervovany_vykon_dodavky_kw ?? "",
    najemRucne: v.najem_kc_mesic_rucne ?? "",
    baterieRucne: !!v.baterie_rucne,
    // Rozpad na pole se ukládá do výsledku (`elektrarna.pole`), ne do vstupu –
    // proto se předvyplňuje odtud.
    pole: ((posl && posl.elektrarna && posl.elektrarna.pole) || []).map((f) => ({
      kwp: String(f.kwp ?? ""),
      sklon: String(f.sklon_st ?? "35"),
      azimut: String(f.azimut_st ?? "0"),
    })),
  };
  try {
    const ulozene = JSON.parse(localStorage.getItem(KLIC_ULOZISTE(nabidka.id)) || "null");
    return ulozene ? { ...zaklad, ...ulozene } : zaklad;
  } catch {
    return zaklad;
  }
}

export default function PpaBessPanel({ nabidka }) {
  const u = nactiUlozeneVstupy(nabidka);

  // ---- vstupy
  const [distributor, setDistributor] = useState(u.distributor);
  const [hladina, setHladina] = useState(u.hladina);
  const [rezKapacita, setRezKapacita] = useState(String(u.rezKapacita ?? ""));
  const [rezPrikon, setRezPrikon] = useState(String(u.rezPrikon ?? ""));
  const [cenaSilova, setCenaSilova] = useState(String(u.cenaSilova ?? ""));
  const [regulovane, setRegulovane] = useState(String(u.regulovane ?? ""));
  const [maxKwp, setMaxKwp] = useState(String(u.maxKwp ?? ""));
  const [cilSs, setCilSs] = useState(String(u.cilSs ?? "80"));
  const [sklon, setSklon] = useState(String(u.sklon ?? "35"));
  const [azimut, setAzimut] = useState(String(u.azimut ?? "0"));
  const [cenaExportu, setCenaExportu] = useState(String(u.cenaExportu ?? ""));
  const [rezVykonDodavky, setRezVykonDodavky] = useState(String(u.rezVykonDodavky ?? ""));
  // Rozpad elektrárny na pole. Prázdný seznam = velikost se navrhne z cíle
  // samospotřeby nad jednou orientací (sklon/azimut výše).
  const [pole, setPole] = useState(u.pole || []);
  // Jak se vybírá baterie: "heuristika" (návrh z přebytku, počítá hned),
  // "rucne" (zadám konkrétní), "katalog" (prohledat celý katalog na pozadí).
  const [zdrojBaterie, setZdrojBaterie] = useState(
    u.baterieRucne ? "rucne" : u.zdrojBaterie || "heuristika"
  );
  // Parametry ruční baterie (platí, když `zdrojBaterie === "rucne"`).
  const [batKapacita, setBatKapacita] = useState(String(u.batKapacita ?? ""));
  const [batVykon, setBatVykon] = useState(String(u.batVykon ?? ""));
  const [batUcinnost, setBatUcinnost] = useState(String(u.batUcinnost ?? ""));
  const [batPodil, setBatPodil] = useState(String(u.batPodil ?? ""));
  const [batCena, setBatCena] = useState(String(u.batCena ?? ""));
  const [najemRucne, setNajemRucne] = useState(String(u.najemRucne ?? ""));

  // ---- UI stav
  const rrPosl = (nabidka.reseni || []).filter((x) => x.typ_reseni === "ppa_bess");
  const [vysledek, setVysledek] = useState(
    rrPosl.length ? rrPosl[rrPosl.length - 1].popis_json : null
  );
  const [pocita, setPocita] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [souhrn, setSouhrn] = useState(null);
  const [mistaKlienta, setMistaKlienta] = useState([]);
  const [zpracovavaId, setZpracovavaId] = useState(null);
  const [beremeDiagramId, setBeremeDiagramId] = useState(null);
  const [zalozka, setZalozka] = useState("rozpad");
  const [vybranyRezim, setVybranyRezim] = useState(null);
  const [delka, setDelka] = useState(null);
  const [prubehy, setPrubehy] = useState({});
  const [prubehNacita, setPrubehNacita] = useState(false);
  const [prubehChyba, setPrubehChyba] = useState(null);
  // Úloha prohledání katalogu na pozadí + jestli služba, která ji odbaví, běží.
  const [uloha, setUloha] = useState(null);
  const [sluzbaBezi, setSluzbaBezi] = useState(true);

  const dokumenty = nabidka.dokumenty || [];
  const dokPodpis = dokumenty.map((d) => `${d.id}:${d.stav_zpracovani}`).join(",");

  useEffect(() => {
    ppaBessProfilSouhrn(nabidka.id).then(setSouhrn).catch(() => setSouhrn(null));
    crmOdbernaMistaNabidky(nabidka.id)
      .then((r) => setMistaKlienta(r?.mista || []))
      .catch(() => setMistaKlienta([]));
  }, [nabidka.id, dokPodpis]);

  // Uložení vstupů, ať se po přepnutí obrazovky nepřepisují ručně znovu.
  useEffect(() => {
    try {
      localStorage.setItem(
        KLIC_ULOZISTE(nabidka.id),
        JSON.stringify({
          distributor, hladina, rezKapacita, rezPrikon, cenaSilova, regulovane,
          maxKwp, cilSs, sklon, azimut, cenaExportu, rezVykonDodavky, pole,
          zdrojBaterie, batKapacita, batVykon, batUcinnost, batPodil, batCena, najemRucne,
        })
      );
    } catch {
      /* localStorage může být plný nebo zakázaný – vstupy se pak jen nepamatují */
    }
  }, [
    nabidka.id, distributor, hladina, rezKapacita, rezPrikon, cenaSilova, regulovane,
    maxKwp, cilSs, sklon, azimut, cenaExportu, rezVykonDodavky, pole,
    zdrojBaterie, batKapacita, batVykon, batUcinnost, batPodil, batCena, najemRucne,
  ]);

  const profilDoklady = dokumenty.filter(
    (d) => d.typ === "spotreba_csv" || d.stav_zpracovani === "zpracovano"
  );
  const diagramyMist = (mistaKlienta || []).flatMap((m) =>
    (m.diagramy || [])
      .filter((d) => d.stav === "zpracovano")
      .map((d) => ({ misto: m, diagram: d }))
  );

  // ---- validace (derivovaná, žádná knihovna)
  const baterieRucne = zdrojBaterie === "rucne";
  const jdeNaPozadi = zdrojBaterie === "katalog";
  const ulohaBezi = !!uloha && ["ceka", "bezi"].includes(uloha.stav);

  const profilOk = !!souhrn && souhrn.pocet > 0;
  const cenaOk = (n(cenaSilova) || 0) > 0;
  const rkOk = (n(rezKapacita) || 0) > 0;
  // Cíl samospotřeby řídí velikost jen tehdy, když se velikost navrhuje.
  // U ručního rozpadu na pole je velikost daná a cíl se neuplatní.
  const polePlatna = pole.filter((f) => (n(f.kwp) || 0) > 0);
  const maPole = polePlatna.length > 0;
  const kwpZPoli = polePlatna.reduce((s, f) => s + (n(f.kwp) || 0), 0);
  const cilOk = maPole || ((n(cilSs) || 0) > 0 && (n(cilSs) || 0) <= 100);
  const batOk = !baterieRucne || ((n(batKapacita) || 0) > 0 && (n(batVykon) || 0) > 0);
  const vsePripraveno = profilOk && cenaOk && rkOk && cilOk && batOk;

  function upravPole(idx, klic, hodnota) {
    setPole((p) => p.map((f, i) => (i === idx ? { ...f, [klic]: hodnota } : f)));
  }
  function pridejPole() {
    setPole((p) => [...p, { kwp: "", sklon: "35", azimut: "0" }]);
  }
  function odeberPole(idx) {
    setPole((p) => p.filter((_, i) => i !== idx));
  }

  async function nactiProfil(dokumentId) {
    setZpracovavaId(dokumentId);
    setChyba(null);
    try {
      await profilZpracuj(nabidka.id, dokumentId);
      setSouhrn(await ppaBessProfilSouhrn(nabidka.id));
      setZprava("Profil načtený.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZpracovavaId(null);
    }
  }

  async function vezmiZMista(diagramId) {
    setBeremeDiagramId(diagramId);
    setChyba(null);
    try {
      await crmPouzijDiagramProNabidku(nabidka.id, diagramId);
      setSouhrn(await ppaBessProfilSouhrn(nabidka.id));
      setZprava("Diagram převzatý z odběrného místa.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setBeremeDiagramId(null);
    }
  }

  /** Vstup pro backend – sestavuje se stejně pro synchronní i frontovou cestu. */
  function sestavData() {
    const data = {
      distributor,
      napetova_hladina: hladina,
      rezervovana_kapacita_kw: n(rezKapacita),
      rezervovany_prikon_kw: n(rezPrikon),
      cena_silova_kc_mwh: n(cenaSilova),
      vyhnutelne_regulovane_kc_mwh: n(regulovane),
      max_kwp: n(maxKwp),
      cil_mira_samospotreby: (n(cilSs) || 80) / 100,
      sklon_st: n(sklon) ?? 35,
      azimut_st: n(azimut) ?? 0,
      cena_exportu_kc_mwh: n(cenaExportu),
      rezervovany_vykon_dodavky_kw: n(rezVykonDodavky),
      baterie_najem_kc_mesic: n(najemRucne),
      pole: maPole
        ? polePlatna.map((f) => ({
            kwp: n(f.kwp),
            sklon_st: n(f.sklon) ?? 35,
            azimut_st: n(f.azimut) ?? 0,
          }))
        : null,
    };
    if (baterieRucne) {
      data.baterie_kapacita_kwh = n(batKapacita);
      data.baterie_vykon_kw = n(batVykon);
      data.baterie_ucinnost_rt = n(batUcinnost);
      data.baterie_vyuzitelny_podil = n(batPodil) === null ? null : n(batPodil) / 100;
      data.baterie_nakladova_cena_kc = n(batCena);
    }
    return data;
  }

  async function spocitat() {
    setPocita(true);
    setChyba(null);
    setZprava(null);
    try {
      if (zdrojBaterie === "katalog") {
        // Dlouhá cesta: úloha jde do fronty, výsledek dorazí, až doběhne.
        const r = await ppaBessKatalog(nabidka.id, sestavData());
        setUloha(r);
        setZprava(
          r.jiz_bezela
            ? "Výpočet už pro tuhle nabídku běží — připojuji se k němu."
            : "Zařazeno do fronty. Prohledání katalogu trvá pár minut."
        );
      } else {
        const odpoved = await ppaBessVypocet(nabidka.id, sestavData());
        setVysledek(odpoved.popis_json);
        setVybranyRezim(null);
        setDelka(null);
        setPrubehy({});
        setZalozka("rozpad");
        setZprava("Spočítáno a uloženo.");
      }
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

  // Stav úlohy na pozadí: jednou při otevření (kdyby výpočet běžel z jiné
  // obrazovky) a pak v intervalu, dokud běží.
  useEffect(() => {
    let zruseno = false;
    let timer = null;

    async function zjisti() {
      try {
        const r = await ppaBessKatalogStav(nabidka.id);
        if (zruseno) return;
        setSluzbaBezi(r.sluzba_bezi !== false);
        setUloha(r.uloha || null);
        const bezi = r.uloha && ["ceka", "bezi"].includes(r.uloha.stav);
        if (bezi) {
          // Dvě sekundy: worker propisuje pokrok stejně často, takže se
          // ukazatel hýbe a přitom to nezatěžuje ani appku, ani databázi.
          timer = setTimeout(zjisti, 2000);
        } else if (r.uloha?.stav === "hotovo" && r.uloha.reseni_id) {
          // Dobehlo – dotáhni hotové řešení do panelu.
          const detail = await nabidkaDetail(nabidka.id);
          if (zruseno) return;
          const nase = (detail.reseni || []).filter((x) => x.typ_reseni === "ppa_bess");
          if (nase.length) {
            setVysledek(nase[nase.length - 1].popis_json);
            setVybranyRezim(null);
            setDelka(null);
            setPrubehy({});
            setZprava("Katalog prohledán, výsledek je níž.");
          }
        }
      } catch {
        /* stav se nepodařilo zjistit – zkusí se při další akci */
      }
    }

    zjisti();
    return () => {
      zruseno = true;
      if (timer) clearTimeout(timer);
    };
  }, [nabidka.id, uloha?.id, uloha?.stav]);

  // ---- derivace z výsledku
  const rezimy = vysledek?.rezimy || [];
  const aktivniRezim =
    rezimy.find((r) => r.rezim === (vybranyRezim || vysledek?.doporuceny_rezim)) || rezimy[0];
  const delkyRezimu = aktivniRezim?.po_delkach || [];
  const vybranaDelka =
    delkyRezimu.find((d) => d.delka_roky === delka) || delkyRezimu[0] || null;
  const rozpadDelky =
    vybranaDelka && aktivniRezim?.prinos_po_delkach
      ? aktivniRezim.prinos_po_delkach[String(vybranaDelka.delka_roky)]
      : null;

  // Průběh se načítá až po otevření záložky (35 tis. hodnot na řadu).
  useEffect(() => {
    if (zalozka !== "prubeh" || !aktivniRezim) return;
    const klic = aktivniRezim.rezim;
    if (prubehy[klic]) return;
    let zruseno = false;
    setPrubehNacita(true);
    setPrubehChyba(null);
    ppaBessPrubeh(nabidka.id, klic)
      .then((d) => {
        if (!zruseno) setPrubehy((p) => ({ ...p, [klic]: d }));
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
  }, [zalozka, aktivniRezim?.rezim, nabidka.id]);

  // ==================== VSTUPNÍ PANEL ====================
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
        {/* 1) Profil */}
        <section className="gs-step">
          <span className="gs-step-num">1</span>
          <h4>Odběrový diagram</h4>
          <div className="gs-step-sub">
            15minutový export z portálu distributora, ideálně celý rok. Výroba elektrárny se
            simuluje, nenahrává se.
          </div>
          {profilOk ? (
            <div className="gs-stav">
              <span aria-hidden="true">✓</span>
              <div>
                <div>
                  <b>{souhrn.pocet.toLocaleString("cs-CZ")}</b> intervalů ·{" "}
                  {fmtDatumCas(souhrn.od)} – {fmtDatumCas(souhrn.do)}
                </div>
                <div style={{ color: "var(--ink-2)" }}>
                  roční spotřeba <b>{souhrn.rocni_spotreba_mwh} MWh</b>
                </div>
              </div>
            </div>
          ) : (
            <div className="gs-stav chybi">
              <span aria-hidden="true">○</span>
              <div>Diagram zatím není načtený — bez něj výpočet nejde spustit.</div>
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
          {diagramyMist.length > 0 && (
            <div style={{ marginTop: 10 }}>
              <div className="gs-step-sub">Diagramy odběrných míst klienta:</div>
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

        {/* 2) Odběrné místo a sazby */}
        <section className="gs-step">
          <span className="gs-step-num">2</span>
          <h4>Odběrné místo</h4>
          <div className="gs-step-sub">
            Určuje sazby za kilowatty. Bez nich se srážení špiček nedá ocenit a spočítá se
            jen elektrárna se samospotřebou.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-distrib">Distributor</label>
              <select
                id="pb-distrib"
                className="gs-input"
                value={distributor}
                onChange={(e) => setDistributor(e.target.value)}
              >
                {DISTRIB.map((d) => (
                  <option key={d.klic} value={d.klic}>{d.nazev}</option>
                ))}
              </select>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-hladina">Napěťová hladina</label>
              <select
                id="pb-hladina"
                className="gs-input"
                value={hladina}
                onChange={(e) => setHladina(e.target.value)}
              >
                {HLADINY.map((h) => (
                  <option key={h.klic} value={h.klic}>{h.nazev}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-rk">Rezervovaná kapacita</label>
              <div className="gs-unit">
                <input
                  id="pb-rk" className="gs-input" inputMode="decimal" placeholder="např. 900"
                  value={rezKapacita} onChange={(e) => setRezKapacita(e.target.value)}
                />
                <span className="gs-unit-txt">kW</span>
              </div>
              <div className="gs-pozn">Z distribuční smlouvy.</div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-rp">
                Rezervovaný příkon <span style={{ fontWeight: 400 }}>(nepovinné)</span>
              </label>
              <div className="gs-unit">
                <input
                  id="pb-rp" className="gs-input" inputMode="decimal" placeholder="např. 950"
                  value={rezPrikon} onChange={(e) => setRezPrikon(e.target.value)}
                />
                <span className="gs-unit-txt">kW</span>
              </div>
              <div className="gs-pozn">
                Ze smlouvy o připojení. Prázdné = použije se rezervovaná kapacita, ale přínos
                baterie pak může být podhodnocený.
              </div>
            </div>
          </div>
        </section>

        {/* 3) Co zákazník platí dnes */}
        <section className="gs-step">
          <span className="gs-step-num">3</span>
          <h4>Co zákazník platí dnes</h4>
          <div className="gs-step-sub">
            Silová složka z faktury. PPA nahradí ji a navíc část regulovaných složek za použití
            sítí — samospotřebovaná energie neprochází distribucí.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-silova">Silová složka</label>
              <div className="gs-unit">
                <input
                  id="pb-silova" className="gs-input" inputMode="decimal" placeholder="např. 3500"
                  value={cenaSilova} onChange={(e) => setCenaSilova(e.target.value)}
                />
                <span className="gs-unit-txt">Kč/MWh</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-reg">
                Vyhnutelné regulované <span style={{ fontWeight: 400 }}>(nepovinné)</span>
              </label>
              <div className="gs-unit">
                <input
                  id="pb-reg" className="gs-input" inputMode="decimal" placeholder="z nastavení (260)"
                  value={regulovane} onChange={(e) => setRegulovane(e.target.value)}
                />
                <span className="gs-unit-txt">Kč/MWh</span>
              </div>
            </div>
          </div>
        </section>

        {/* 4) Elektrárna */}
        <section className="gs-step">
          <span className="gs-step-num">4</span>
          <h4>Elektrárna</h4>
          <div className="gs-step-sub">
            Buď se velikost navrhne z cíle samospotřeby nad jednou orientací, nebo zadáš
            rozpad na pole a velikost je tím daná.
          </div>

          {!maPole && (
            <>
              <div className="gs-dva">
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-maxkwp">Strop velikosti</label>
                  <div className="gs-unit">
                    <input
                      id="pb-maxkwp" className="gs-input" inputMode="decimal" placeholder="např. 1000"
                      value={maxKwp} onChange={(e) => setMaxKwp(e.target.value)}
                    />
                    <span className="gs-unit-txt">kWp</span>
                  </div>
                </div>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-cil">Cíl samospotřeby</label>
                  <div className="gs-unit">
                    <input
                      id="pb-cil" className="gs-input" inputMode="decimal"
                      value={cilSs} onChange={(e) => setCilSs(e.target.value)}
                    />
                    <span className="gs-unit-txt">% výroby</span>
                  </div>
                </div>
              </div>
              <div className="gs-dva">
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-sklon">Sklon</label>
                  <div className="gs-unit">
                    <input
                      id="pb-sklon" className="gs-input" inputMode="decimal"
                      value={sklon} onChange={(e) => setSklon(e.target.value)}
                    />
                    <span className="gs-unit-txt">°</span>
                  </div>
                </div>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-azimut">Azimut</label>
                  <div className="gs-unit">
                    <input
                      id="pb-azimut" className="gs-input" inputMode="decimal"
                      value={azimut} onChange={(e) => setAzimut(e.target.value)}
                    />
                    <span className="gs-unit-txt">° (0 = jih)</span>
                  </div>
                </div>
              </div>
            </>
          )}

          {/* Rozpad na pole – když je střecha rozdělená na víc orientací.
              Východ-západ má plošší výrobu než jih, takže se jinak potká
              se spotřebou a jinak zbyde na baterii. */}
          <div className="gs-step-sub" style={{ marginTop: maPole ? 0 : 12 }}>
            {maPole ? (
              <>
                Rozpad na pole — velikost je{" "}
                <b>{cislo(kwpZPoli, 0)} kWp</b> a cíl samospotřeby se neuplatní.
              </>
            ) : (
              "Znáš rozpad střechy? Zadej pole a velikost se nebude navrhovat."
            )}
          </div>
          {pole.map((f, i) => (
            <div
              key={i}
              style={{ display: "flex", gap: 6, alignItems: "flex-end", marginTop: 6 }}
            >
              <div className="gs-pole" style={{ flex: 1 }}>
                {i === 0 && <label className="gs-label">Výkon</label>}
                <div className="gs-unit">
                  <input
                    className="gs-input" inputMode="decimal" placeholder="kWp"
                    value={f.kwp} onChange={(e) => upravPole(i, "kwp", e.target.value)}
                    aria-label={`Výkon pole ${i + 1} v kWp`}
                  />
                  <span className="gs-unit-txt">kWp</span>
                </div>
              </div>
              <div className="gs-pole" style={{ flex: 1 }}>
                {i === 0 && <label className="gs-label">Azimut</label>}
                <div className="gs-unit">
                  <input
                    className="gs-input" inputMode="decimal" placeholder="0"
                    value={f.azimut} onChange={(e) => upravPole(i, "azimut", e.target.value)}
                    aria-label={`Azimut pole ${i + 1} ve stupních`}
                  />
                  <span className="gs-unit-txt">°</span>
                </div>
              </div>
              <div className="gs-pole" style={{ flex: 1 }}>
                {i === 0 && <label className="gs-label">Sklon</label>}
                <div className="gs-unit">
                  <input
                    className="gs-input" inputMode="decimal" placeholder="35"
                    value={f.sklon} onChange={(e) => upravPole(i, "sklon", e.target.value)}
                    aria-label={`Sklon pole ${i + 1} ve stupních`}
                  />
                  <span className="gs-unit-txt">°</span>
                </div>
              </div>
              <button
                type="button"
                className="fm-btn"
                style={{ padding: "6px 10px" }}
                onClick={() => odeberPole(i)}
                title="Odebrat pole"
                aria-label={`Odebrat pole ${i + 1}`}
              >
                ✕
              </button>
            </div>
          ))}
          <button
            type="button"
            className="fm-btn"
            style={{ padding: "4px 10px", fontSize: 12, marginTop: 8 }}
            onClick={pridejPole}
          >
            + Přidat pole
          </button>
          <div className="gs-pozn" style={{ marginTop: 6 }}>
            Azimut: 0 = jih, −90 = východ, +90 = západ. Například jih 200 kWp, východ
            100 kWp, západ 100 kWp.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-export">
                Cena za přetok <span style={{ fontWeight: 400 }}>(nepovinné)</span>
              </label>
              <div className="gs-unit">
                <input
                  id="pb-export" className="gs-input" inputMode="decimal" placeholder="0 = neinkasuje se"
                  value={cenaExportu} onChange={(e) => setCenaExportu(e.target.value)}
                />
                <span className="gs-unit-txt">Kč/MWh</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="pb-dodavka">
                Rezervovaný výkon dodávky <span style={{ fontWeight: 400 }}>(nepovinné)</span>
              </label>
              <div className="gs-unit">
                <input
                  id="pb-dodavka" className="gs-input" inputMode="decimal" placeholder="neomezeno"
                  value={rezVykonDodavky} onChange={(e) => setRezVykonDodavky(e.target.value)}
                />
                <span className="gs-unit-txt">kW</span>
              </div>
              <div className="gs-pozn">Limit pro dodávku do sítě. 0 = nic do sítě nesmí.</div>
            </div>
          </div>
        </section>

        {/* 5) Baterie */}
        <section className="gs-step">
          <span className="gs-step-num">5</span>
          <h4>Baterie</h4>
          <div className="gs-step-sub">
            Baterie je pronájem od Greensie — zákazník ji prvních {vysledek?.baterie?.doba_najmu_roky || 10}{" "}
            let neinvestuje, platí paušál. Pak si ji odkoupí za zbytkovou cenu.
          </div>
          <label className="gs-volba">
            <input
              type="radio" name="pb-bat" checked={zdrojBaterie === "heuristika"}
              onChange={() => setZdrojBaterie("heuristika")}
            />
            <span>
              Navrhnout velikost odhadem{" "}
              <span style={{ color: "var(--muted)" }}>(spočítá hned, umí přestřelit)</span>
            </span>
          </label>
          <label className="gs-volba">
            <input
              type="radio" name="pb-bat" checked={zdrojBaterie === "katalog"}
              onChange={() => setZdrojBaterie("katalog")}
            />
            <span>
              Prohledat celý katalog{" "}
              <span style={{ color: "var(--muted)" }}>(pár minut na pozadí, najde nejlepší)</span>
            </span>
          </label>
          <label className="gs-volba">
            <input
              type="radio" name="pb-bat" checked={zdrojBaterie === "rucne"}
              onChange={() => setZdrojBaterie("rucne")}
            />
            <span>Zadám konkrétní baterii</span>
          </label>

          {jdeNaPozadi && !sluzbaBezi && (
            <div className="nb-warn" style={{ margin: "8px 0 0" }}>
              <span>⚠️</span>
              <span>
                Služba, která výpočty na pozadí odbavuje, neběží — úloha by zůstala ve
                frontě. Spusť ji přes <code>systemctl start greensie-vypocty</code>, nebo
                zvol návrh odhadem.
              </span>
            </div>
          )}

          {baterieRucne && (
            <>
              <div className="gs-dva" style={{ marginTop: 8 }}>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-batkap">Kapacita</label>
                  <div className="gs-unit">
                    <input
                      id="pb-batkap" className="gs-input" inputMode="decimal" placeholder="např. 300"
                      value={batKapacita} onChange={(e) => setBatKapacita(e.target.value)}
                    />
                    <span className="gs-unit-txt">kWh</span>
                  </div>
                </div>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-batvyk">Výkon</label>
                  <div className="gs-unit">
                    <input
                      id="pb-batvyk" className="gs-input" inputMode="decimal" placeholder="např. 150"
                      value={batVykon} onChange={(e) => setBatVykon(e.target.value)}
                    />
                    <span className="gs-unit-txt">kW</span>
                  </div>
                </div>
              </div>
              <div className="gs-dva">
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-batucin">
                    Účinnost <span style={{ fontWeight: 400 }}>(nepovinné)</span>
                  </label>
                  <div className="gs-unit">
                    <input
                      id="pb-batucin" className="gs-input" inputMode="decimal" placeholder="88"
                      value={batUcinnost} onChange={(e) => setBatUcinnost(e.target.value)}
                    />
                    <span className="gs-unit-txt">% round-trip</span>
                  </div>
                </div>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-batpodil">
                    Využitelná kapacita <span style={{ fontWeight: 400 }}>(nepovinné)</span>
                  </label>
                  <div className="gs-unit">
                    <input
                      id="pb-batpodil" className="gs-input" inputMode="decimal" placeholder="90"
                      value={batPodil} onChange={(e) => setBatPodil(e.target.value)}
                    />
                    <span className="gs-unit-txt">% (SOC okno)</span>
                  </div>
                </div>
              </div>
              <div className="gs-dva">
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-batcena">
                    Nákladová cena <span style={{ fontWeight: 400 }}>(nepovinné)</span>
                  </label>
                  <div className="gs-unit">
                    <input
                      id="pb-batcena" className="gs-input" inputMode="decimal" placeholder="za kolik ji kupujeme"
                      value={batCena} onChange={(e) => setBatCena(e.target.value)}
                    />
                    <span className="gs-unit-txt">Kč</span>
                  </div>
                  <div className="gs-pozn">Z ní se dopočítá nájem (marže + anuita 10 let + EMS).</div>
                </div>
                <div className="gs-pole">
                  <label className="gs-label" htmlFor="pb-najem">
                    Sjednaný nájem <span style={{ fontWeight: 400 }}>(nepovinné)</span>
                  </label>
                  <div className="gs-unit">
                    <input
                      id="pb-najem" className="gs-input" inputMode="decimal" placeholder="dopočítá se z ceny"
                      value={najemRucne} onChange={(e) => setNajemRucne(e.target.value)}
                    />
                    <span className="gs-unit-txt">Kč/měs</span>
                  </div>
                  <div className="gs-pozn">
                    Když vyplníš obojí, výpočet ukáže, jak se rozcházejí a co to dělá s DSCR.
                  </div>
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      <div className="gs-panel-f">
        <button
          className="fm-btn fm-primary"
          onClick={spocitat}
          disabled={!vsePripraveno || pocita || ulohaBezi}
        >
          {pocita
            ? "Počítám…"
            : ulohaBezi
              ? "Počítá se na pozadí…"
              : jdeNaPozadi
                ? "Prohledat katalog na pozadí"
                : "Spočítat PPA + BESS"}
        </button>

        {/* Pokrok úlohy na pozadí. Ukazuje se i po znovuotevření obrazovky,
            protože stav se čte ze serveru, ne ze stavu komponenty. */}
        {uloha && ulohaBezi && (
          <div style={{ marginTop: 10 }}>
            <div className="gs-pozn">
              {uloha.stav === "ceka" ? "Ve frontě…" : uloha.zprava || "Počítám…"}
              {uloha.celkem_variant > 0 && (
                <>
                  {" "}
                  — {uloha.hotovo_variant} z {uloha.celkem_variant} konfigurací
                </>
              )}
            </div>
            <div className="gs-pruh" style={{ marginTop: 6 }}>
              <i
                style={{
                  width:
                    uloha.celkem_variant > 0
                      ? `${Math.min(100, (100 * uloha.hotovo_variant) / uloha.celkem_variant)}%`
                      : "8%",
                }}
              />
            </div>
            <div className="gs-pozn" style={{ marginTop: 4 }}>
              Můžeš odejít na jinou obrazovku, výpočet běží dál.
            </div>
          </div>
        )}
        {uloha && uloha.stav === "chyba" && (
          <div className="nb-warn" style={{ marginTop: 10 }}>
            <span>⚠️</span>
            <span>Prohledání katalogu se nepovedlo: {uloha.chyba || "neznámá chyba"}</span>
          </div>
        )}
        <ul className="gs-chk">
          <li className={profilOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark">{profilOk ? "✓" : "!"}</span>
            Odběrový diagram
          </li>
          <li className={rkOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark">{rkOk ? "✓" : "!"}</span>
            Rezervovaná kapacita
          </li>
          <li className={cenaOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark">{cenaOk ? "✓" : "!"}</span>
            Silová složka ceny
          </li>
          <li className={cilOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark">{cilOk ? "✓" : "!"}</span>
            {maPole
              ? `Rozpad na pole (${cislo(kwpZPoli, 0)} kWp)`
              : "Cíl samospotřeby 1–100 %"}
          </li>
          {baterieRucne && (
            <li className={batOk ? "gs-chk-ok" : "gs-chk-no"}>
              <span className="gs-chk-mark">{batOk ? "✓" : "!"}</span>
              Kapacita i výkon baterie
            </li>
          )}
        </ul>
        {chyba && (
          <div className="nb-warn" style={{ marginTop: 10 }}>
            <span>⚠️</span>
            <span>{chyba}</span>
          </div>
        )}
        {zprava && (
          <div className="gs-pozn" style={{ color: "var(--brand-strong)", marginTop: 8 }}>
            {zprava}
          </div>
        )}
      </div>
    </form>
  );

  // ==================== VÝSLEDEK ====================
  let obsah;
  if (!vysledek || !rezimy.length) {
    obsah = (
      <div className="fm-card" style={{ padding: 24 }}>
        <h3 style={{ marginTop: 0 }}>Zatím nespočítáno</h3>
        <p style={{ color: "var(--ink-2)", margin: 0 }}>
          Vyplň vlevo odběrový diagram, rezervovanou kapacitu a cenu, kterou zákazník platí
          dnes. Kalkulačka navrhne elektrárnu i baterii a ukáže, kolik peněz přinese srážení
          špiček a kolik zvýšení samospotřeby.
        </p>
      </div>
    );
  } else {
    const el = vysledek.elektrarna || {};
    const bat = vysledek.baterie;
    const prinos = aktivniRezim.prinos || {};
    const energie = aktivniRezim.energie || {};
    const vykon = aktivniRezim.vykon || {};
    const ek = aktivniRezim.ekonomika_vykonu || {};
    const ekSnizeni = aktivniRezim.ekonomika_vykonu_se_snizenim || {};
    const maSazby = ek.status === "spocitano";
    const fin = vybranaDelka?.financovani || {};
    const cistyKZobrazeni = rozpadDelky
      ? rozpadDelky.cisty_bez_snizeni_rp_kc
      : prinos.cisty_bez_snizeni_rp_kc;
    const energieKZobrazeni = rozpadDelky ? rozpadDelky.z_energie_kc : prinos.z_energie_kc;
    const prubehData = prubehy[aktivniRezim.rezim];
    const rpJeFallbackRk = !n(rezPrikon);

    obsah = (
      <>
        {/* ---- hlavička ---- */}
        <div className="gs-res-h">
          <div>
            <div className="gs-nadtitul">
              Doporučené řešení
              {vybranaDelka ? ` · kontrakt na ${vybranaDelka.delka_roky} let` : ""}
            </div>
            <h3 style={{ margin: 0 }}>
              {cislo(el.kwp, 0)} kWp elektrárna
              {bat
                ? ` + baterie ${cislo(bat.kapacita_kwh, 0)} kWh / ${cislo(bat.vykon_kw, 0)} kW`
                : ""}
            </h3>
          </div>
          <span className="gs-mezera" style={{ flex: 1 }} />
          <span className={cistyKZobrazeni > 0 ? "nb-badge dobre" : "nb-badge spatne"}>
            {cistyKZobrazeni > 0 ? "✓ vydělá" : "nevyplatí se"}
          </span>
        </div>

        {/* ---- dlaždice: co to zákazníkovi přinese a odkud ---- */}
        <div className="gs-kpis">
          <div className="gs-kpi accent" data-druh="penize">
            <div className="gs-kpi-label">Čistý přínos zákazníka</div>
            <div className="gs-kpi-value">{kc(cistyKZobrazeni)}</div>
            <div className="gs-kpi-sub">
              za rok, po zaplacení nájmu baterie
              {vybranaDelka ? ` · celkem ${kc(vybranaDelka.uspora_celkem_kc)}` : ""}
            </div>
          </div>
          <div className="gs-kpi" data-druh="penize">
            <div className="gs-kpi-label">Z kilowatthodin (elektrárna)</div>
            <div className="gs-kpi-value">{kc(energieKZobrazeni)}</div>
            <div className="gs-kpi-sub">
              {mwh(energie.samospotreba_mwh)} levnější energie
              {vybranaDelka?.cena_ppa_kc_mwh
                ? ` · sleva ${pct(vybranaDelka.sleva)}`
                : ""}
            </div>
          </div>
          <div className="gs-kpi" data-druh="penize">
            <div className="gs-kpi-label">Z kilowattů (srážení špiček)</div>
            <div className="gs-kpi-value">{kc(prinos.z_vykonu_bez_snizeni_rp_kc)}</div>
            <div className="gs-kpi-sub">
              špička {kw(vykon.maximum_bez_baterie_kw)} → {kw(vykon.maximum_po_baterii_kw)} (o{" "}
              {kw(vykon.sraz_kw)} níž)
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">
              {maSazby && ek.rp_novy_kw !== ek.rp_soucasny_kw
                ? "Nová rezervovaná kapacita"
                : "Rezervovaný příkon"}
            </div>
            <div className="gs-kpi-value">
              {maSazby ? kw(ek.rp_novy_kw ?? ek.rp_soucasny_kw) : kw(n(rezPrikon) || n(rezKapacita))}
            </div>
            <div className="gs-kpi-sub">
              {maSazby && ek.rp_novy_kw !== ek.rp_soucasny_kw
                ? `dnes ${kw(ek.rp_soucasny_kw)} · lze snížit o ${kw(
                    ek.rp_soucasny_kw - ek.rp_novy_kw
                  )}`
                : "beze změny smlouvy o připojení"}
            </div>
          </div>
          <div className="gs-kpi" data-druh="riziko">
            <div className="gs-kpi-label">Nájem baterie</div>
            <div className="gs-kpi-value">
              {bat ? kc(bat.najem_kc_mesic) : "—"}
              {bat ? <span style={{ fontSize: 14 }}> /měs</span> : null}
            </div>
            <div className="gs-kpi-sub">
              {bat
                ? `fixní ${bat.doba_najmu_roky} let, pak odkup za ${kc(
                    vybranaDelka?.odkupni_cena_baterie_kc
                  )}`
                : "bez baterie"}
            </div>
          </div>
          <div className="gs-kpi" data-druh="cas">
            <div className="gs-kpi-label">Pokrytí spotřeby</div>
            <div className="gs-kpi-value">{pct(energie.pokryti_spotreby, 0)}</div>
            <div className="gs-kpi-sub">
              z elektrárny · samospotřeba {pct(energie.mira_samospotreby)} výroby
            </div>
          </div>
        </div>

        {/* ---- upozornění ---- */}
        {(vysledek.upozorneni || []).length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, margin: "12px 0" }}>
            {vysledek.upozorneni.map((z, i) => (
              <div className="nb-warn" key={i}>
                <span>⚠️</span>
                <span dangerouslySetInnerHTML={{ __html: zvyrazni(z) }} />
              </div>
            ))}
          </div>
        )}

        {/* ---- záložky ---- */}
        <div className="gs-tabs gs-tabs-odsazeni" role="tablist" aria-label="Části výsledku">
          {[
            ["prehled", "Přehled"],
            ["spicky", "Srážení špiček"],
            ["elektrarna", "Elektrárna"],
            ["roky", "Po letech"],
            ["rezimy", "Co má baterie dělat"],
            ["prubeh", "Průběh"],
            ...(vysledek.katalog ? [["katalog", "Katalog baterií"]] : []),
          ].map(([klic, nazev]) => (
            <button
              key={klic}
              type="button"
              role="tab"
              aria-selected={zalozka === klic}
              onClick={() => setZalozka(klic)}
            >
              {nazev}
            </button>
          ))}
        </div>

        {/* ================= PŘEHLED ================= */}
        {zalozka === "prehled" && (
          <>
            <div className="gs-scroll">
              <table className="gs-table">
                <thead>
                  <tr>
                    <th>Délka</th>
                    <th className="n">Cena PPA</th>
                    <th className="n">Sleva</th>
                    <th>Drží cenu</th>
                    <th className="n">DSCR</th>
                    <th className="n">IRR</th>
                    <th className="n">Úspora rok 1</th>
                    <th className="n">Úspora celkem</th>
                  </tr>
                </thead>
                <tbody>
                  {delkyRezimu.map((d) => (
                    <tr
                      key={d.delka_roky}
                      onClick={() => setDelka(d.delka_roky)}
                      style={{
                        cursor: "pointer",
                        background:
                          vybranaDelka?.delka_roky === d.delka_roky
                            ? "var(--brand-wash)"
                            : undefined,
                      }}
                      title="Klikni pro detail téhle délky"
                    >
                      <td>
                        <b>{d.delka_roky} let</b>
                      </td>
                      <td className="n">{kcMwh(d.cena_ppa_kc_mwh)}</td>
                      <td className="n">{d.sleva === null ? "—" : pct(d.sleva)}</td>
                      <td>
                        <span
                          className={
                            d.limitujici === "dscr"
                              ? "nb-badge"
                              : d.limitujici === "irr"
                                ? "nb-badge pozor"
                                : "nb-badge spatne"
                          }
                        >
                          {d.limitujici === "dscr"
                            ? "banka"
                            : d.limitujici === "irr"
                              ? "investor"
                              : "nedosažitelné"}
                        </span>
                      </td>
                      <td className="n">{cislo(d.dscr_min, 2)}</td>
                      <td className="n">{d.irr === null ? "—" : pct(d.irr, 2)}</td>
                      <td className="n">{kc(d.uspora_rok1_kc)}</td>
                      <td className="n">{kc(d.uspora_celkem_kc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Délku nedoporučujeme — vyber podle toho, co zákazník podepíše. Delší kontrakt =
              nižší splátka = nižší cena a větší sleva. „Drží cenu" říká, která podmínka je
              ta těsná: u krátkého kontraktu banka (DSCR 1,30), u dlouhého investor (cílové
              IRR). U kontraktu na 10 let k odkupu baterie nedojde — nájem skončí s kontraktem.
            </div>

            <div className="gs-dva" style={{ marginTop: 14 }}>
              <div className="fm-card" style={{ padding: 14 }}>
                <h4 style={{ margin: "0 0 8px" }}>Přínos zákazníkovi (rok 1)</h4>
                <Radek l="Z levnější energie (kWh)" v={kc(energieKZobrazeni)} />
                <Radek
                  l="Ze srážení špiček (kW)"
                  v={kc(prinos.z_vykonu_bez_snizeni_rp_kc)}
                />
                {maSazby &&
                  prinos.z_vykonu_se_snizenim_rp_kc !== prinos.z_vykonu_bez_snizeni_rp_kc && (
                    <Radek
                      l="… se snížením příkonu"
                      v={kc(prinos.z_vykonu_se_snizenim_rp_kc)}
                    />
                  )}
                <Radek l="Nájem baterie" v={`− ${kc(prinos.najem_baterie_kc)}`} />
                {energie.ztraty_ze_site_mwh > 0 && (
                  <Radek
                    l="Ztráty síťového dobíjení"
                    v={mwh(energie.ztraty_ze_site_mwh, 2)}
                  />
                )}
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: "2px solid var(--line)" }}>
                  <Radek l={<b>Čistý přínos za rok</b>} v={<b>{kc(cistyKZobrazeni)}</b>} />
                </div>
              </div>
              <div className="fm-card" style={{ padding: 14 }}>
                <h4 style={{ margin: "0 0 8px" }}>Projekt a financování</h4>
                <Radek l="CAPEX celkem (prodej do SPV)" v={kc(fin.capex_celkem_kc)} />
                <Radek l="… z toho elektrárna" v={kc(fin.capex_fve_kc)} />
                <Radek l="… z toho baterie" v={kc(fin.capex_bess_kc)} />
                <Radek l="Vlastní kapitál" v={kc(fin.vlastni_kapital_kc)} />
                <Radek l="Úvěr" v={kc(fin.uver_kc)} />
                <Radek l="Provize obchodníka" v={kc(fin.provize_kc)} />
                <Radek l="Zisk Greensie hned" v={kc(fin.zisk_greensie_kc)} />
                <Radek l="Splátka (rok 1)" v={`${kc(fin.splatka_rok1_kc)}/rok`} />
                <Radek l="Provozní náklady (rok 1)" v={`${kc(fin.provozni_naklady_rok1_kc)}/rok`} />
              </div>
            </div>

            {bat && (
              <div className="fm-card" style={{ padding: 14, marginTop: 14 }}>
                <h4 style={{ margin: "0 0 8px" }}>
                  Baterie
                  {bat.z_katalogu ? (
                    <span className="nb-badge dobre" style={{ marginLeft: 6 }}>
                      z katalogu
                    </span>
                  ) : (
                    <span className="nb-badge pozor" style={{ marginLeft: 6 }}>
                      {bat.nakladova_cena_kc > 0 ? "zadaná ručně" : "bez ceny"}
                    </span>
                  )}
                  {vysledek.katalog && (
                    <span className="nb-badge dobre" style={{ marginLeft: 6 }}>
                      vybraná z {vysledek.katalog.prohledano_konfiguraci} konfigurací
                    </span>
                  )}
                </h4>
                <div className="gs-dva">
                  <div>
                    {bat.nazev && (
                      <Radek
                        l="Produkt"
                        v={bat.pocet_kusu > 1 ? `${bat.nazev} × ${bat.pocet_kusu}` : bat.nazev}
                      />
                    )}
                    <Radek l="Kapacita (jmenovitá)" v={`${cislo(bat.kapacita_kwh, 0)} kWh`} />
                    <Radek
                      l="Kapacita (využitelná)"
                      v={`${cislo(bat.vyuzitelna_kapacita_kwh, 0)} kWh`}
                    />
                    <Radek l="Výkon" v={kw(bat.vykon_kw)} />
                    <Radek l="Účinnost (round-trip)" v={pct(bat.ucinnost_round_trip)} />
                  </div>
                  <div>
                    <Radek l="Nákladová cena" v={kc(bat.nakladova_cena_kc)} />
                    <Radek l="CAPEX do SPV" v={kc(bat.capex_kc)} />
                    <Radek l="Nájem" v={`${kc(bat.najem_kc_mesic)}/měs`} />
                    {bat.najem_zadan_rucne && (
                      <Radek
                        l="… z ceny by vyšel"
                        v={`${kc(bat.najem_z_ceny_kc_mesic)}/měs`}
                      />
                    )}
                    <Radek l="Doba nájmu" v={`${bat.doba_najmu_roky} let`} />
                    <Radek l="Cyklů za rok" v={cislo(energie.cyklu_rok, 0)} />
                  </div>
                </div>
                {bat.cena_je_doporucena && (
                  <div className="gs-pozn pozor" style={{ marginTop: 8 }}>
                    Ceník u téhle konfigurace neuvádí dealerskou cenu, takže nákladová cena
                    vychází z doporučené prodejní — nájem je tím nadhodnocený.
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ================= SRÁŽENÍ ŠPIČEK ================= */}
        {zalozka === "spicky" && (
          <>
            {!maSazby ? (
              <div className="fm-card" style={{ padding: 18 }}>
                <div className="nb-warn">
                  <span>⚠️</span>
                  <span>
                    Sazby NTS 2027 pro tuhle hladinu a distributora nejsou v sazebníku, takže
                    srážení špiček se nedá ocenit. Doplň je v Katalogu a výpočtech.
                  </span>
                </div>
              </div>
            ) : (
              <>
                <div className="fm-card" style={{ padding: 0 }}>
                  <div className="gs-karta-h" style={{ padding: "10px 14px" }}>
                    <span className="gs-karta-nazev">
                      Rozpad úspory na rezervované kapacitě (model NTS 2027)
                    </span>
                    <span className="gs-mezera" style={{ flex: 1 }} />
                    {vysledek.sazby_2027_modelovy_odhad && (
                      <span className="nb-badge pozor">sazby jsou modelový odhad</span>
                    )}
                  </div>
                  <div className="gs-scroll" style={{ border: 0, boxShadow: "none" }}>
                    <table className="gs-table">
                      <tbody>
                        <tr>
                          <td>
                            Náklad dnes{" "}
                            <span style={{ color: "var(--muted)" }}>
                              (RP {kw(ek.rp_soucasny_kw)})
                            </span>
                            {rpJeFallbackRk && (
                              <div className="gs-pozn pozor">
                                Příkon ze smlouvy nezadán → dosazena rezervovaná kapacita.
                                Skutečný RP bývá vyšší, takže náklad i úspora jsou
                                podhodnocené.
                              </div>
                            )}
                          </td>
                          <td className="n">{kc(ek.soucasny_rocni_naklad)}</td>
                        </tr>
                        {ek.naklad_optimalni_bez_baterie != null && (
                          <>
                            <tr>
                              <td>
                                Optimalizace příkonu bez baterie{" "}
                                <span style={{ color: "var(--muted)" }}>
                                  (RP {kw(ek.optimalni_rp_bez_baterie_kw)})
                                </span>
                              </td>
                              <td className="n">{kc(ek.naklad_optimalni_bez_baterie)}</td>
                            </tr>
                            <tr className="soucet">
                              <td>Úspora hned bez investice</td>
                              <td className="n">{kc(ek.uspora_optimalizaci_bez_baterie)}</td>
                            </tr>
                            {/* Symetrická pojistka jako u peak shavingu: optimalizace
                                nese rezervu, dnešní RP ze smlouvy ne — u zákazníka
                                s velkým příkonem tak může vyjít dráž než nedělat nic. */}
                            {ek.naklad_optimalni_bez_baterie > ek.soucasny_rocni_naklad && (
                              <tr>
                                <td colSpan={2} className="dim" style={{ fontSize: 11 }}>
                                  Optimalizované RP (s rezervou{" "}
                                  {cislo(vysledek.vstup?.rezerva_rk_procenta, 0)} %) by bylo
                                  dražší než dnešní příkon ze smlouvy — bez investice není co
                                  ušetřit, takže se přínos baterie počítá proti dnešnímu
                                  nákladu.
                                </td>
                              </tr>
                            )}
                          </>
                        )}
                        <tr>
                          <td>Náklad s baterií</td>
                          <td className="n">{kc(ek.novy_rocni_naklad)}</td>
                        </tr>
                        {ek.mesicu_s_prekrocenim_rp > 0 && (
                          <tr>
                            <td className="dim">
                              … z toho vědomé překročení RP{" "}
                              <span style={{ fontSize: 11 }}>
                                (v {ek.mesicu_s_prekrocenim_rp} měs. — nižší RP se i
                                s penalizací vyplatí)
                              </span>
                            </td>
                            <td className="n dim">{kc(ek.naklad_prekroceni_rp)}</td>
                          </tr>
                        )}
                        {/* Ztráty cyklování se sem musí dopsat zvlášť: `ekonomika_2027`
                            je nepočítá, protože jí předáváme hotová měsíční maxima
                            z našeho dispatchu (viz peak_shaving.py:802–805). */}
                        {energie.ztraty_ze_site_mwh > 0 && (
                          <tr>
                            <td className="dim">
                              … z toho ztráty síťového dobíjení{" "}
                              <span style={{ fontSize: 11 }}>
                                ({mwh(energie.ztraty_ze_site_mwh, 2)} se v baterii ztratí)
                              </span>
                            </td>
                            <td className="n dim">
                              {kc(
                                (energie.ztraty_ze_site_mwh || 0) *
                                  (vysledek.vstup?.cena_zakaznika_kc_mwh || 0)
                              )}
                            </td>
                          </tr>
                        )}
                        <tr className="soucet">
                          <td>Přínos baterie na výkonu</td>
                          <td className="n">{kc(ek.prinos_baterie)}</td>
                        </tr>
                        <tr className="soucet">
                          <td>Roční úspora na kilowattech celkem</td>
                          <td className="n">{kc(ek.rocni_uspora)}</td>
                        </tr>
                        <tr>
                          <td className="dim">Měsíců na tarifu T1 / T2</td>
                          <td className="n dim">
                            {ek.pocet_mesicu_t1} / {ek.pocet_mesicu_t2}
                          </td>
                        </tr>
                        <tr>
                          <td>
                            <b>Rezervovaný příkon (RP)</b>
                          </td>
                          <td className="n">
                            <b>
                              {kw(ek.rp_soucasny_kw)}
                              {ek.rp_novy_kw !== ek.rp_soucasny_kw
                                ? ` → ${kw(ek.rp_novy_kw)} (${
                                    ek.rp_novy_kw < ek.rp_soucasny_kw ? "snížení" : "navýšení"
                                  })`
                                : " (beze změny smlouvy)"}
                            </b>
                          </td>
                        </tr>
                        {ekSnizeni.status === "spocitano" &&
                          ekSnizeni.rp_novy_kw !== ek.rp_novy_kw && (
                            <tr>
                              <td className="dim">
                                Se snížením příkonu na {kw(ekSnizeni.rp_novy_kw)}{" "}
                                <span style={{ fontSize: 11 }}>
                                  (jednosměrná změna smlouvy o připojení)
                                </span>
                              </td>
                              <td className="n dim">{kc(ekSnizeni.prinos_baterie)}</td>
                            </tr>
                          )}
                      </tbody>
                    </table>
                  </div>
                  <div className="gs-pozn" style={{ padding: "10px 14px" }}>
                    Baseline není dnešní stav, ale <b>nejlevnější příkon bez investice</b> —
                    přínos baterie se tak nepočítá proti předimenzovanému RP ze smlouvy.
                    Volba RP nese rezervu {cislo(vysledek.vstup?.rezerva_rk_procenta, 0)} %,
                    protože strop je nalezený z jednoho historického roku.
                  </div>
                </div>

                {aktivniRezim.graf_maxima && (
                  <div className="fm-card" style={{ marginTop: 14 }}>
                    <h4 style={{ margin: "0 0 8px" }}>Měsíční maxima odběru</h4>
                    <GrafOdberu
                      mesice={aktivniRezim.graf_maxima.mesice}
                      bezBaterie={aktivniRezim.graf_maxima.bez_baterie_kw}
                      sBaterii={aktivniRezim.graf_maxima.s_baterii_kw}
                      rpSoucasna={ek.rp_soucasny_kw}
                      rpNova={ek.rp_novy_kw}
                      popisSoucasna="rezervovaný příkon nyní"
                      popisNova="nový rezervovaný příkon"
                    />
                    <div className="gs-pozn" style={{ marginTop: 8 }}>
                      Sloupce „bez baterie" jsou už <b>po odečtení výroby elektrárny</b> —
                      tedy co by zákazník naměřil, kdyby si postavil jen elektrárnu. Proti
                      tomu se poctivě poměřuje, co přidala baterie.
                    </div>
                  </div>
                )}

                <div className="fm-card" style={{ padding: 0, marginTop: 14 }}>
                  <div className="gs-scroll okno" style={{ border: 0, boxShadow: "none" }}>
                    <table className="gs-table">
                      <thead>
                        <tr>
                          <th>Měsíc</th>
                          <th className="n">Maximum bez baterie</th>
                          <th className="n">Zvolený strop</th>
                          <th className="n">Maximum po baterii</th>
                          <th className="n">Nejnižší možný</th>
                          <th className="n">Sražení</th>
                          <th className="n">Na špičky</th>
                          <th className="n">Cyklů</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(aktivniRezim.mesice || []).map((m) => (
                          <tr key={m.mesic}>
                            <td>{MESICE_NAZVY[m.mesic - 1] || m.mesic}</td>
                            <td className="n">{kw(m.maximum_bez_baterie_kw)}</td>
                            <td className="n">{kw(m.strop_kw)}</td>
                            <td className="n">{kw(m.maximum_po_baterii_kw)}</td>
                            <td className="n">{kw(m.nejnizsi_udrzitelny_kw)}</td>
                            <td className="n">
                              {kw(m.maximum_bez_baterie_kw - m.maximum_po_baterii_kw)}
                            </td>
                            <td className="n">{cislo(m.na_spicky_kwh, 0)} kWh</td>
                            <td className="n">{cislo(m.cyklu, 1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="gs-pozn" style={{ padding: "10px 14px" }}>
                    Zvolený strop se u kombinovaného režimu hledá <b>ekonomicky</b>: pustit
                    špičku výš znamená zaplatit víc za výkon, ale získat víc kapacity na
                    uložení přebytku. Výchozím bodem je vždy nejnižší možný strop, tedy
                    chování čistého peak shavingu — kombinace proto nestartuje z horší pozice.
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* ================= ELEKTRÁRNA ================= */}
        {zalozka === "elektrarna" && (
          <>
            {aktivniRezim.graf && (
              <div className="fm-card">
                <h4 style={{ margin: "0 0 8px" }}>Výroba elektrárny vs. spotřeba po měsících</h4>
                <GrafVyrobaSpotreba graf={aktivniRezim.graf} />
                <div className="gs-pozn" style={{ marginTop: 8 }}>
                  Levý sloupec je spotřeba (kolik z ní kryje elektrárna a kolik se dokupuje),
                  pravý výroba (kolik se spotřebuje na místě, kolik přeteče do sítě a kolik se
                  ořízne). Do samospotřeby se počítá i energie, která k zákazníkovi dorazila
                  přes baterii.
                </div>
              </div>
            )}

            <div className="gs-dva" style={{ marginTop: 14 }}>
              <div className="fm-card" style={{ padding: 14 }}>
                <h4 style={{ margin: "0 0 8px" }}>Energetická bilance (rok 1)</h4>
                <Radek l="Spotřeba zákazníka" v={mwh(souhrn?.rocni_spotreba_mwh, 0)} />
                <Radek l="Výroba elektrárny" v={mwh(el.vyroba_mwh, 0)} />
                <Radek
                  l="Samospotřeba celkem"
                  v={`${mwh(energie.samospotreba_mwh)} (${pct(energie.mira_samospotreby)} výroby)`}
                />
                <Radek l="… přímo z elektrárny" v={mwh(energie.prima_samospotreba_mwh)} />
                <Radek l="… přes baterii" v={mwh(energie.z_fve_pres_baterii_mwh)} />
                <Radek l="Přetok do sítě" v={mwh(energie.export_mwh)} />
                <Radek l="Pokrytí spotřeby z elektrárny" v={pct(energie.pokryti_spotreby)} />
                <Radek
                  l="Dokup ze sítě"
                  v={mwh(
                    (souhrn?.rocni_spotreba_mwh || 0) - (energie.samospotreba_mwh || 0),
                    0
                  )}
                />
              </div>
              <div className="fm-card" style={{ padding: 14 }}>
                <h4 style={{ margin: "0 0 8px" }}>Elektrárna</h4>
                <Radek
                  l={el.velikost_zadana_rucne ? "Zadaný výkon" : "Navržený výkon"}
                  v={`${cislo(el.kwp, 0)} kWp`}
                />
                {!el.velikost_zadana_rucne && (
                  <>
                    <Radek
                      l="Bez baterie by vyšlo"
                      v={`${cislo(el.kwp_bez_baterie, 0)} kWp`}
                    />
                    {el.omezeno_max_kwp && (
                      <Radek
                        l="Bez stropu by vyšlo"
                        v={`${cislo(el.kwp_bez_stropu, 0)} kWp`}
                      />
                    )}
                  </>
                )}
                <Radek
                  l="Měrný výnos"
                  v={
                    el.kwp > 0
                      ? `${cislo((el.vyroba_mwh * 1000) / el.kwp, 0)} kWh/kWp`
                      : "—"
                  }
                />
                {(el.pole || []).length > 0 ? (
                  <div style={{ marginTop: 8 }}>
                    <div className="gs-pozn" style={{ marginBottom: 4 }}>
                      Rozpad na pole:
                    </div>
                    {el.pole.map((f, i) => (
                      <Radek
                        key={i}
                        l={`${f.orientace}, sklon ${cislo(f.sklon_st, 0)}°`}
                        v={`${cislo(f.kwp, 0)} kWp → ${mwh(f.vyroba_mwh, 0)}`}
                      />
                    ))}
                  </div>
                ) : (
                  <>
                    <Radek l="Sklon" v={`${cislo(vysledek.vstup?.sklon_st, 0)}°`} />
                    <Radek
                      l="Azimut"
                      v={`${cislo(vysledek.vstup?.azimut_st, 0)}° (0 = jih)`}
                    />
                  </>
                )}
                {el.optimum?.kwp ? (
                  <>
                    <Radek l="Ekonomické optimum" v={`${cislo(el.optimum.kwp, 0)} kWp`} />
                    <div className="gs-pozn" style={{ marginTop: 6 }}>
                      {el.optimum.poznamka}
                    </div>
                  </>
                ) : null}
              </div>
            </div>
          </>
        )}

        {/* ================= PO LETECH ================= */}
        {zalozka === "roky" && vybranaDelka && (
          <div className="fm-card" style={{ padding: 0 }}>
            <div className="gs-scroll okno" style={{ border: 0, boxShadow: "none" }}>
              <table className="gs-table">
                <thead>
                  <tr>
                    <th>Rok</th>
                    <th className="n">Výroba</th>
                    <th className="n">Samospotřeba</th>
                    <th className="n">Cena PPA</th>
                    <th className="n">Z kWh</th>
                    <th className="n">Z kW</th>
                    <th className="n">Nájem</th>
                    <th className="n">Ztráty</th>
                    <th className="n">Provoz</th>
                    <th className="n">Odkup</th>
                    <th className="n">Čistý přínos</th>
                    <th className="n">DSCR</th>
                  </tr>
                </thead>
                <tbody>
                  {(vybranaDelka.roky || []).map((r) => (
                    <tr key={r.rok} className={r.vydaj_odkup_kc > 0 ? "soucet" : undefined}>
                      <td>{r.rok}</td>
                      <td className="n">{mwh(r.vyroba_mwh, 0)}</td>
                      <td className="n">{mwh(r.samospotreba_mwh, 0)}</td>
                      <td className="n">{cislo(r.cena_ppa_kc_mwh, 0)}</td>
                      <td className="n">{kc(r.uspora_energie_kc)}</td>
                      <td className="n">{kc(r.uspora_vykon_kc)}</td>
                      <td className="n">
                        {r.najem_baterie_kc ? `−${cislo(r.najem_baterie_kc, 0)}` : "—"}
                      </td>
                      <td className="n">
                        {r.naklad_ztrat_kc ? `−${cislo(r.naklad_ztrat_kc, 0)}` : "—"}
                      </td>
                      <td className="n">
                        {r.naklad_provozu_zakaznika_kc
                          ? `−${cislo(r.naklad_provozu_zakaznika_kc, 0)}`
                          : "—"}
                      </td>
                      <td className="n">
                        {r.vydaj_odkup_kc ? `−${cislo(r.vydaj_odkup_kc, 0)}` : "—"}
                      </td>
                      <td className="n">
                        <b>{kc(r.cisty_prinos_kc)}</b>
                      </td>
                      <td className="n">{cislo(r.dscr, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn" style={{ padding: "10px 14px" }}>
              {vybranaDelka.rok_odkupu ? (
                <>
                  V roce {vybranaDelka.rok_odkupu} skončí nájem, klesne splátka a zákazník
                  baterii odkoupí za {kc(vybranaDelka.odkupni_cena_baterie_kc)} — od té chvíle
                  si platí servis a EMS sám. Odkup je kapitálový výdaj, do DSCR nevstupuje.
                </>
              ) : (
                <>
                  U kontraktu na {vybranaDelka.delka_roky} let k odkupu baterie nedojde — nájem
                  skončí s kontraktem.
                </>
              )}{" "}
              Přínos ze srážení špiček klesá s degradací baterie, cena PPA se každé tři roky
              skokově indexuje.
            </div>
          </div>
        )}

        {/* ================= REŽIMY ================= */}
        {zalozka === "rezimy" && (
          <>
            <div className="gs-scroll">
              <table className="gs-table">
                <thead>
                  <tr>
                    <th>Režim</th>
                    <th className="n">Z kilowatthodin</th>
                    <th className="n">Z kilowattů</th>
                    <th className="n">Nájem</th>
                    <th className="n">Čistý přínos</th>
                    <th className="n">Sražení špičky</th>
                    <th className="n">Samospotřeba</th>
                    <th className="n">Cyklů/rok</th>
                  </tr>
                </thead>
                <tbody>
                  {rezimy.map((r) => {
                    const jeAktivni = r.rezim === aktivniRezim.rezim;
                    const rd =
                      vybranaDelka && r.prinos_po_delkach
                        ? r.prinos_po_delkach[String(vybranaDelka.delka_roky)]
                        : null;
                    return (
                      <tr
                        key={r.rezim}
                        onClick={() => setVybranyRezim(r.rezim)}
                        style={{
                          cursor: "pointer",
                          background: jeAktivni
                            ? "color-mix(in srgb, var(--brand) 9%, transparent)"
                            : undefined,
                        }}
                        title="Kliknutím přepneš celý výsledek na tenhle režim"
                      >
                        <td>
                          {jeAktivni ? "◄ " : ""}
                          {r.nazev}
                          {r.doporuceny && (
                            <span className="nb-badge dobre" style={{ marginLeft: 6 }}>
                              doporučeno
                            </span>
                          )}
                        </td>
                        <td className="n">
                          {kc(rd ? rd.z_energie_kc : r.prinos.z_energie_kc)}
                        </td>
                        <td className="n">{kc(r.prinos.z_vykonu_bez_snizeni_rp_kc)}</td>
                        <td className="n">−{cislo(r.prinos.najem_baterie_kc, 0)}</td>
                        <td className="n">
                          <b>
                            {kc(
                              rd ? rd.cisty_bez_snizeni_rp_kc : r.prinos.cisty_bez_snizeni_rp_kc
                            )}
                          </b>
                        </td>
                        <td className="n">{kw(r.vykon.sraz_kw)}</td>
                        <td className="n">{pct(r.energie.mira_samospotreby, 0)}</td>
                        <td className="n">{cislo(r.energie.cyklu_rok, 0)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Kombinovaný režim si drží rezervu na špičky a přebytek z elektrárny ukládá jen do
              zbytku kapacity. Doporučuje se ten režim, který zákazníkovi <b>skutečně</b>{" "}
              vydělá nejvíc — není to vždy kombinace, protože volba stropu se rozhoduje podle
              odhadu ceny PPA a ten se s realitou rozejít může. Kliknutím na řádek přepneš
              celý výsledek (dlaždice, grafy, tabulky) na jiný režim.
            </div>
          </>
        )}

        {/* ================= PRŮBĚH ================= */}
        {zalozka === "prubeh" && (
          <div className="fm-card">
            {prubehNacita && <div className="gs-pozn">Načítám průběh…</div>}
            {prubehChyba && (
              <div className="nb-warn">
                <span>⚠️</span>
                <span>{prubehChyba}</span>
              </div>
            )}
            {prubehData && (
              <GrafPrubehuPpa
                data={{
                  ...prubehData,
                  referencni: {
                    rezervovany_vykon_dodavky_kw:
                      prubehData.referencni?.rezervovany_prikon_kw ?? null,
                  },
                }}
                popis={`Režim „${aktivniRezim.nazev}“. Čárkovaná čára je rezervovaný příkon, tečkovaná stav nabití baterie. Kolečkem přiblížíš, tažením posuneš.`}
              />
            )}
          </div>
        )}

        {/* ================= KATALOG ================= */}
        {zalozka === "katalog" && vysledek.katalog && (
          <div className="fm-card" style={{ padding: 0 }}>
            <div className="gs-scroll okno" style={{ border: 0, boxShadow: "none" }}>
              <table className="gs-table">
                <thead>
                  <tr>
                    <th>Baterie</th>
                    <th className="n">Kusů</th>
                    <th className="n">Kapacita</th>
                    <th className="n">Výkon</th>
                    <th className="n">Nákladová cena</th>
                    <th className="n">Nájem</th>
                    <th className="n">Sražení špičky</th>
                    <th className="n">Cyklů/rok</th>
                    <th className="n">Pořadí</th>
                  </tr>
                </thead>
                <tbody>
                  {vysledek.katalog.varianty.map((v, i) => {
                    const jeVitez =
                      bat && v.produkt_id === bat.produkt_id && v.pocet_kusu === bat.pocet_kusu;
                    return (
                      <tr
                        key={`${v.produkt_id}-${v.pocet_kusu}`}
                        style={{
                          background: jeVitez
                            ? "color-mix(in srgb, var(--brand) 9%, transparent)"
                            : undefined,
                        }}
                      >
                        <td>
                          {jeVitez ? "◄ " : ""}
                          {v.nazev}
                          {v.cena_je_doporucena && (
                            <span className="nb-badge pozor" style={{ marginLeft: 6 }}>
                              cena z doporučené
                            </span>
                          )}
                        </td>
                        <td className="n">{v.pocet_kusu}</td>
                        <td className="n">{cislo(v.kapacita_kwh, 0)} kWh</td>
                        <td className="n">{kw(v.vykon_kw)}</td>
                        <td className="n">{kc(v.nakladova_cena_kc)}</td>
                        <td className="n">{kc(v.najem_kc_mesic)}</td>
                        <td className="n">{kw(v.sraz_kw)}</td>
                        <td className="n">{cislo(v.cyklu_rok, 0)}</td>
                        <td className="n">{i + 1}.</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn" style={{ padding: "10px 14px" }}>
              Prohledáno {vysledek.katalog.prohledano_konfiguraci} konfigurací z{" "}
              {vysledek.katalog.produktu_v_katalogu} produktů. {vysledek.katalog.poznamka}{" "}
              Sloupec „pořadí" je ze screeningu — vítěz (◄) je ten, který po plném dopočtu
              vyšel nejlépe, takže nemusí být první.
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <div className="gs-desk">
      {panelVstupu}
      <div>{obsah}</div>
    </div>
  );
}

/** Řádek „popisek — hodnota“ v kartě detailu. */
function Radek({ l, v }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "4px 0",
        borderBottom: "1px solid var(--line-soft)",
      }}
    >
      <span style={{ color: "var(--ink-2)" }}>{l}</span>
      <span style={{ fontVariantNumeric: "tabular-nums", textAlign: "right" }}>{v}</span>
    </div>
  );
}

/** Escapuje HTML a `**tučně**` převede na <b> – pro texty upozornění. */
function zvyrazni(text) {
  const esc = String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
