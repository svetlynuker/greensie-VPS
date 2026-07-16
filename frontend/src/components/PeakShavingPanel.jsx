import { useEffect, useState } from "react";
import GrafOdberu from "./GrafOdberu";
import {
  sazbySeznam,
  peakShavingProfilSouhrn,
  peakShavingVypocet,
  profilZpracuj,
} from "../api";

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

function VariantaRadek({ v, hlavni }) {
  return (
    <tr style={hlavni ? { fontWeight: 600 } : undefined}>
      <td>
        {v.nazev} × {v.pocet_kusu}
        {!v.doporuceno && (
          <span className="nb-badge" style={{ marginLeft: 6, color: "var(--st-crit)" }}>nedoporučeno</span>
        )}
      </td>
      <td>{kw(v.celkovy_vykon_kw)} / {v.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh</td>
      <td>{kw(v.nova_rezervovana_kapacita_kw)}</td>
      <td>{kc(v.rocni_uspora_2026_kc)}</td>
      <td>{kc(v.cena_celkem_kc)}</td>
      <td>{roky(v.navratnost_roky)}</td>
      <td>{v.npv_kc != null ? kc(v.npv_kc) : "—"}</td>
    </tr>
  );
}

export default function PeakShavingPanel({ nabidka }) {
  const [sazby, setSazby] = useState(null);
  const [souhrn, setSouhrn] = useState(null);
  const [distributor, setDistributor] = useState("cez");
  const [hladina, setHladina] = useState("vn");
  const [rezKap, setRezKap] = useState("");
  // Rezervovaný příkon ze smlouvy o připojení – pro model 2027 (PS-4).
  const [rezPrikon, setRezPrikon] = useState("");
  const [snizeniRp, setSnizeniRp] = useState(false);
  const [vysledek, setVysledek] = useState(() => {
    const rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "peak_shaving");
    return rr.length ? rr[rr.length - 1].popis_json : null;
  });
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [pocita, setPocita] = useState(false);
  const [zpracovavaId, setZpracovavaId] = useState(null);

  useEffect(() => {
    sazbySeznam().then(setSazby).catch((e) => setChyba(e.message));
    peakShavingProfilSouhrn(nabidka.id).then(setSouhrn).catch(() => setSouhrn({ pocet: 0 }));
  }, [nabidka.id]);

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
      const r = await peakShavingVypocet(nabidka.id, {
        distributor,
        napetova_hladina: hladina,
        rezervovana_kapacita_kw: Number(String(rezKap).replace(",", ".")),
        rezervovany_prikon_kw: rezPrikon.trim() === "" || !(prikon > 0) ? null : prikon,
        uvazovat_snizeni_rp: snizeniRp,
      });
      setVysledek(r.popis_json);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

  const dop = vysledek?.doporucena;

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
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 8 }}>
        <input type="checkbox" checked={snizeniRp} onChange={(e) => setSnizeniRp(e.target.checked)} />
        V modelu 2027 uvažovat snížení rezervovaného příkonu na novou kapacitu
        <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>(jednosměrná změna smlouvy o připojení)</span>
      </label>
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
        disabled={pocita || !profilOk || !rezOk || !sazbaOk}
      >
        {pocita ? "Počítám…" : "Spočítat peak shaving"}
      </button>
      {zprava && <div style={{ color: "var(--fm-brand-dk)", fontSize: 13, marginTop: 10 }}>{zprava}</div>}
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}

      {/* 3) Výsledek */}
      {vysledek && (
        <div style={{ marginTop: 18 }}>
          {dop ? (
            <>
              <h4 style={{ margin: "0 0 8px", fontSize: 13 }}>
                Doporučená varianta
                {!dop.doporuceno && (
                  <span className="nb-badge" style={{ marginLeft: 8, color: "var(--st-crit)" }}>
                    nad prahem {vysledek.max_navratnost_roky}&nbsp;let – nedoporučeno
                  </span>
                )}
              </h4>
              {/* KPI přehled doporučené varianty — hlavní čísla na první pohled */}
              <div className="gs-kpis" style={{ marginBottom: 12 }}>
                <div className="gs-kpi accent">
                  <div className="gs-kpi-label">Roční úspora (2026)</div>
                  <div className="gs-kpi-value">{kc(dop.rocni_uspora_2026_kc)}</div>
                  <div className="gs-kpi-sub">
                    {dop.uspora_bez_investice_2026_kc != null
                      ? `z toho bez investice ${kc(dop.uspora_bez_investice_2026_kc)}`
                      : "bez DPH"}
                  </div>
                </div>
                <div className="gs-kpi">
                  <div className="gs-kpi-label">Návratnost (2026)</div>
                  <div className="gs-kpi-value">{roky(dop.navratnost_2026 ?? dop.navratnost_roky)}</div>
                  <div className="gs-kpi-sub">
                    {dop.prinos_baterie_2026_kc != null
                      ? `z přínosu baterie · práh ${vysledek.max_navratnost_roky} let`
                      : `práh doporučení ${vysledek.max_navratnost_roky} let`}
                  </div>
                </div>
                <div className="gs-kpi">
                  <div className="gs-kpi-label">Nová rez. kapacita</div>
                  <div className="gs-kpi-value">{kw(dop.nova_rezervovana_kapacita_kw)}</div>
                  <div className="gs-kpi-sub">
                    {dop.strop_kw != null
                      ? `roční RK; strop baterie ${kw(dop.strop_kw)}, rezerva ${dop.rezerva_rk_procenta ?? 0} %`
                      : "sjednaný příkon po instalaci"}
                  </div>
                </div>
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
                <div className="fm-card" style={{ padding: 14 }}>
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
                <div className="fm-card" style={{ padding: 14 }}>
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
                          <tr><td>Roční náklad bez peak shavingu</td><td>{kc(dop.ekonomika_2027.soucasny_rocni_naklad)}</td></tr>
                          <tr><td>Roční náklad s peak shavingem</td><td>{kc(dop.ekonomika_2027.novy_rocni_naklad_bez_aku ?? dop.ekonomika_2027.novy_rocni_naklad)}</td></tr>
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

              {vysledek.graf && (
                <>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Odběr ze sítě – měsíční maxima</h4>
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Rok 2026 (držení ročního stropu)</div>
                    <GrafOdberu
                      mesice={vysledek.graf.mesice}
                      bezBaterie={vysledek.graf.bez_baterie_kw}
                      sBaterii={vysledek.graf.s_baterii_2026_kw}
                      rpSoucasna={vysledek.graf.rp_soucasna_kw}
                      rpNova={vysledek.graf.rp_nova_kw}
                    />
                  </div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Rok 2027 (srážení po měsících)</div>
                    <GrafOdberu
                      mesice={vysledek.graf.mesice}
                      bezBaterie={vysledek.graf.bez_baterie_kw}
                      sBaterii={vysledek.graf.s_baterii_2027_kw}
                      rpSoucasna={vysledek.graf.rp_soucasna_kw}
                      rpNova={vysledek.graf.rp_nova_kw}
                    />
                  </div>
                </>
              )}

              {vysledek.varianty?.length > 1 && (
                <>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Srovnání variant</h4>
                  <div className="nb-scroll">
                    <table className="nb-table">
                      <thead>
                        <tr><th>Baterie</th><th>Výkon / kapacita</th><th>Nová rez.</th><th>Úspora/rok</th><th>Cena</th><th>Návratnost</th><th>NPV</th></tr>
                      </thead>
                      <tbody>
                        {vysledek.varianty.map((v, i) => (
                          <VariantaRadek key={`${v.baterie_id}-${v.pocet_kusu}`} v={v} hlavni={i === 0} />
                        ))}
                      </tbody>
                    </table>
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
