import { useEffect, useState } from "react";
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
          <span className="nb-badge" style={{ marginLeft: 6, color: "#c92a2a" }}>nedoporučeno</span>
        )}
      </td>
      <td>{kw(v.celkovy_vykon_kw)} / {v.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh</td>
      <td>{kw(v.nova_rezervovana_kapacita_kw)}</td>
      <td>{kc(v.rocni_uspora_2026_kc)}</td>
      <td>{kc(v.cena_celkem_kc)}</td>
      <td>{roky(v.navratnost_roky)}</td>
    </tr>
  );
}

export default function PeakShavingPanel({ nabidka }) {
  const [sazby, setSazby] = useState(null);
  const [souhrn, setSouhrn] = useState(null);
  const [distributor, setDistributor] = useState("cez");
  const [hladina, setHladina] = useState("vn");
  const [rezKap, setRezKap] = useState("");
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
  const sazbaOk =
    sazba &&
    sazba.parametry &&
    sazba.parametry.cena_rezervovana_kapacita_kc_kw_rok != null &&
    sazba.parametry.cena_prekroceni_kc_kw != null;
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
      const r = await peakShavingVypocet(nabidka.id, {
        distributor,
        napetova_hladina: hladina,
        rezervovana_kapacita_kw: Number(String(rezKap).replace(",", ".")),
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
      </div>
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
      {chyba && <div style={{ color: "#c92a2a", fontSize: 13, marginTop: 10 }}>{chyba}</div>}

      {/* 3) Výsledek */}
      {vysledek && (
        <div style={{ marginTop: 18 }}>
          {dop ? (
            <>
              <h4 style={{ margin: "0 0 8px", fontSize: 13 }}>
                Doporučená varianta
                {!dop.doporuceno && (
                  <span className="nb-badge" style={{ marginLeft: 8, color: "#c92a2a" }}>
                    nad prahem {vysledek.max_navratnost_roky}&nbsp;let – nedoporučeno
                  </span>
                )}
              </h4>
              <div className="fm-card" style={{ padding: 14, marginBottom: 14, background: "var(--fm-bg, #fafafa)" }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
                  {dop.nazev} × {dop.pocet_kusu} — návratnost {roky(dop.navratnost_roky)}
                </div>
                <div style={{ fontSize: 13, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 6 }}>
                  <div>Baterie: {kw(dop.celkovy_vykon_kw)} / {dop.celkova_kapacita_kwh?.toLocaleString("cs-CZ")} kWh</div>
                  <div>Cena baterie: {kc(dop.cena_celkem_kc)}</div>
                  <div>Nová rez. kapacita: {kw(dop.nova_rezervovana_kapacita_kw)}</div>
                  <div>Roční úspora (2026): <b>{kc(dop.rocni_uspora_2026_kc)}</b></div>
                </div>
              </div>

              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Ekonomika 2026</h4>
              <table className="nb-table" style={{ marginBottom: 14 }}>
                <tbody>
                  <tr><td>Současný náklad – rezervace</td><td>{kc(dop.ekonomika_2026?.soucasny_naklad_rezervace)}</td></tr>
                  <tr><td>Současný náklad – pokuty za překročení</td><td>{kc(dop.ekonomika_2026?.soucasny_naklad_prekroceni)}</td></tr>
                  <tr><td><b>Současný náklad celkem</b></td><td><b>{kc(dop.ekonomika_2026?.soucasny_naklad_celkem)}</b></td></tr>
                  <tr><td>Nový náklad (rezervace na {kw(dop.nova_rezervovana_kapacita_kw)})</td><td>{kc(dop.ekonomika_2026?.novy_naklad_rezervace)}</td></tr>
                  <tr><td><b>Roční úspora</b></td><td><b>{kc(dop.ekonomika_2026?.rocni_uspora)}</b></td></tr>
                </tbody>
              </table>

              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Ekonomika 2027 (nová struktura ERÚ)</h4>
              <div style={{ fontSize: 13, marginBottom: 14 }}>
                {dop.ekonomika_2027?.status === "spocitano"
                  ? <>Odhad ročního nákladu 2027: <b>{kc(dop.ekonomika_2027.rocni_naklad)}</b></>
                  : <span style={{ color: "var(--fm-muted)" }}>Čeká se na oficiální sazby ERÚ.</span>}
              </div>

              {vysledek.varianty?.length > 1 && (
                <>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Srovnání variant</h4>
                  <div className="nb-scroll">
                    <table className="nb-table">
                      <thead>
                        <tr><th>Baterie</th><th>Výkon / kapacita</th><th>Nová rez.</th><th>Úspora/rok</th><th>Cena</th><th>Návratnost</th></tr>
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
