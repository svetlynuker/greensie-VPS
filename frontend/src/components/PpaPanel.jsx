import { useEffect, useState } from "react";
import GrafVyrobaSpotreba from "./GrafVyrobaSpotreba";
import { ppaProfilSouhrn, ppaVypocet, profilZpracuj } from "../api";

function kc(x) {
  return x == null ? "—" : `${Math.round(x).toLocaleString("cs-CZ")} Kč`;
}
function mwh(kwh) {
  return kwh == null ? "—" : `${(kwh / 1000).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} MWh`;
}
function roky(x) {
  return x == null ? "—" : `${x.toLocaleString("cs-CZ", { maximumFractionDigits: 2 })} let`;
}
function pct(x) {
  return x == null ? "—" : `${Math.round(x * 100)} %`;
}
function fmtDatumCas(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "—";
}
function n(v) {
  return String(v).replace(",", ".").trim() === "" ? null : Number(String(v).replace(",", "."));
}

export default function PpaPanel({ nabidka }) {
  const [souhrn, setSouhrn] = useState(null);
  const [zpracovavaId, setZpracovavaId] = useState(null);

  // Vstupy FVE + PPA (METODIKA kap. 2). Volitelné indexy necháváme prázdné =
  // backend doplní z manažerského nastavení.
  // Poslední uložený PPA výpočet – z něj předvyplníme vstupy, ať jde po
  // znovuotevření nabídky rovnou přepočítávat (jinak by prázdná pole vypnula tlačítko).
  const _rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "ppa");
  const _posl = _rr.length ? _rr[_rr.length - 1].popis_json : null;
  const _v = _posl?.vstup || {};
  const _r = _posl?.vysledek || {};
  const s = (x) => (x == null ? "" : String(x));

  const [maxKwp, setMaxKwp] = useState(s(_v.max_kwp));
  const [kwpOverride, setKwpOverride] = useState(_v.metoda_navrhu === "rucne" ? s(_v.instalovany_vykon_kwp) : "");
  const [sklon, setSklon] = useState(_v.sklon_st != null ? s(_v.sklon_st) : "35");
  const [azimut, setAzimut] = useState(_v.azimut_st != null ? s(_v.azimut_st) : "0");
  const [cenaPpa, setCenaPpa] = useState(s(_v.cena_ppa_kc_mwh));
  // Silová složka ceny dodavatele (PPA-5); starší výpočty měly klíč cena_dodavatel_kc_mwh.
  const [cenaSilova, setCenaSilova] = useState(s(_v.cena_silova_kc_mwh ?? _v.cena_dodavatel_kc_mwh));
  const [regulovane, setRegulovane] = useState(s(_v.vyhnutelne_regulovane_kc_mwh));
  const [delka, setDelka] = useState(_v.delka_kontraktu_roky != null ? s(_v.delka_kontraktu_roky) : "15");
  const [rezimCapex, setRezimCapex] = useState(_v.rezim_capex || "cena_kwp");
  const [prebytekUctovat, setPrebytekUctovat] = useState(!!_v.prebytek_uctovat);
  const [prebytekCena, setPrebytekCena] = useState(_v.prebytek_uctovat && _r.prebytek_cena_kc_mwh ? s(_r.prebytek_cena_kc_mwh) : "");
  const [rezVykon, setRezVykon] = useState(s(_v.rezervovany_vykon_dodavky_kw));
  const [indexPpa, setIndexPpa] = useState("");
  const [indexDod, setIndexDod] = useState("");

  const [vysledek, setVysledek] = useState(_posl);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [pocita, setPocita] = useState(false);

  useEffect(() => {
    ppaProfilSouhrn(nabidka.id)
      .then(setSouhrn)
      .catch(() => setSouhrn({ pocet: 0 }));
  }, [nabidka.id]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const profilOk = souhrn && souhrn.pocet > 0;
  const vstupyOk = n(cenaPpa) > 0 && n(cenaSilova) > 0 && n(delka) > 0;

  async function nactiProfil(dokId) {
    setZpracovavaId(dokId);
    setChyba(null);
    setZprava(null);
    try {
      await profilZpracuj(dokId);
      const s = await ppaProfilSouhrn(nabidka.id);
      setSouhrn(s);
      setZprava(`Profil načten: ${s.pocet.toLocaleString("cs-CZ")} intervalů, roční spotřeba ${s.rocni_spotreba_mwh} MWh.`);
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
      const r = await ppaVypocet(nabidka.id, {
        instalovany_vykon_kwp: n(kwpOverride),
        max_kwp: n(maxKwp),
        sklon_st: n(sklon) ?? 35,
        azimut_st: n(azimut) ?? 0,
        cena_ppa_kc_mwh: n(cenaPpa),
        cena_silova_kc_mwh: n(cenaSilova),
        vyhnutelne_regulovane_kc_mwh: n(regulovane),
        delka_kontraktu_roky: n(delka),
        rezim_capex: rezimCapex,
        prebytek_uctovat: prebytekUctovat,
        prebytek_cena_kc_mwh: prebytekUctovat ? n(prebytekCena) : null,
        rezervovany_vykon_dodavky_kw: n(rezVykon),
        index_ppa_rocni: n(indexPpa),
        index_dodavatel_rocni: n(indexDod),
      });
      setVysledek(r.popis_json);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

  const v = vysledek?.vysledek;

  return (
    <div className="fm-card" style={{ padding: 18 }}>
      <h3 style={{ margin: "0 0 8px", fontSize: 14 }}>PPA pro FVE – výpočet</h3>

      {/* 1) Profil spotřeby */}
      <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 8px" }}>
        <b>1. Profil spotřeby.</b> Načti 15minutový profil z nahraného souboru (XLS/CSV z portálu distributora). Výroba FVE se simuluje, nenahrává.
      </p>
      {profilOk ? (
        <div style={{ fontSize: 13, marginBottom: 8 }}>
          ✅ Načteno <b>{souhrn.pocet.toLocaleString("cs-CZ")}</b> intervalů, {fmtDatumCas(souhrn.od)} – {fmtDatumCas(souhrn.do)}, roční spotřeba <b>{souhrn.rocni_spotreba_mwh} MWh</b>.
        </div>
      ) : (
        <div style={{ fontSize: 13, marginBottom: 8, color: "var(--fm-muted)" }}>Profil zatím není načtený.</div>
      )}
      {profilDoklady.length === 0 ? (
        <div className="nb-warn" style={{ margin: "0 0 12px" }}>
          <span>⚠️</span>
          <span>Nejdřív nahraj soubor se spotřebou (sekce Podklady výše).</span>
        </div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
          {profilDoklady.map((d) => (
            <button key={d.id} className="fm-btn" onClick={() => nactiProfil(d.id)} disabled={zpracovavaId === d.id}>
              {zpracovavaId === d.id ? "Načítám…" : `Načíst profil: ${d.puvodni_nazev}`}
            </button>
          ))}
        </div>
      )}

      {/* 2) Parametry FVE */}
      <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 8px" }}>
        <b>2. Parametry FVE a PPA.</b> Velikost FVE (kWp) navrhne appka sama tak, aby výroba co nejlépe pokrývala spotřebu. Volitelně omez výkon střechou, nebo ho zadej napevno.
      </p>
      <div className="nb-form-grid" style={{ marginBottom: 8 }}>
        <div>
          <label className="nb-label">Max. výkon dle střechy (kWp, volit.)</label>
          <input className="nb-pole" value={maxKwp} onChange={(e) => setMaxKwp(e.target.value)} inputMode="decimal" placeholder="strop pro auto-návrh" />
        </div>
        <div>
          <label className="nb-label">Výkon napevno (kWp, volit.)</label>
          <input className="nb-pole" value={kwpOverride} onChange={(e) => setKwpOverride(e.target.value)} inputMode="decimal" placeholder="prázdné = navrhne appka" />
        </div>
        <div>
          <label className="nb-label">Sklon panelů (°)</label>
          <input className="nb-pole" value={sklon} onChange={(e) => setSklon(e.target.value)} inputMode="decimal" />
        </div>
        <div>
          <label className="nb-label">Azimut (°, 0 = jih)</label>
          <input className="nb-pole" value={azimut} onChange={(e) => setAzimut(e.target.value)} inputMode="decimal" placeholder="0 = jih, 90 = západ" />
        </div>
        <div>
          <label className="nb-label">PPA cena rok 1 (Kč/MWh)</label>
          <input className="nb-pole" value={cenaPpa} onChange={(e) => setCenaPpa(e.target.value)} inputMode="decimal" placeholder="např. 2500" />
        </div>
        <div>
          <label className="nb-label">Silová cena dodavatele (Kč/MWh)</label>
          <input className="nb-pole" value={cenaSilova} onChange={(e) => setCenaSilova(e.target.value)} inputMode="decimal" placeholder="jen silová složka, např. 3200" />
        </div>
        <div>
          <label className="nb-label">Vyhnutelné regulované (Kč/MWh, volit.)</label>
          <input className="nb-pole" value={regulovane} onChange={(e) => setRegulovane(e.target.value)} inputMode="decimal" placeholder="prázdné = z nastavení (~260)" />
        </div>
        <div>
          <label className="nb-label">Délka kontraktu (roky)</label>
          <input className="nb-pole" value={delka} onChange={(e) => setDelka(e.target.value)} inputMode="numeric" />
        </div>
        <div>
          <label className="nb-label">Náklady na FVE</label>
          <select className="nb-pole" value={rezimCapex} onChange={(e) => setRezimCapex(e.target.value)}>
            <option value="cena_kwp">Zjednodušeně (cena za kWp)</option>
            <option value="komponenty">Skutečné (komponenty z katalogu)</option>
          </select>
        </div>
        <div>
          <label className="nb-label">Max. rez. výkon dodávky (kW)</label>
          <input className="nb-pole" value={rezVykon} onChange={(e) => setRezVykon(e.target.value)} inputMode="decimal" placeholder="prázdné = neomezeno" />
        </div>
        <div>
          <label className="nb-label">Index PPA (%/rok, volitelné)</label>
          <input className="nb-pole" value={indexPpa} onChange={(e) => setIndexPpa(e.target.value)} inputMode="decimal" placeholder="např. 0.03" />
        </div>
        <div>
          <label className="nb-label">Index dodavatele (%/rok, volitelné)</label>
          <input className="nb-pole" value={indexDod} onChange={(e) => setIndexDod(e.target.value)} inputMode="decimal" placeholder="default = index PPA" />
        </div>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, marginBottom: 8 }}>
        <input type="checkbox" checked={prebytekUctovat} onChange={(e) => setPrebytekUctovat(e.target.checked)} />
        Účtovat přetok do sítě (prodej přebytku)
      </label>
      {prebytekUctovat && (
        <div className="nb-form-grid" style={{ marginBottom: 8 }}>
          <div>
            <label className="nb-label">Cena přebytku (Kč/MWh)</label>
            <input className="nb-pole" value={prebytekCena} onChange={(e) => setPrebytekCena(e.target.value)} inputMode="decimal" placeholder="dle lokality/smlouvy" />
          </div>
        </div>
      )}

      <button className="fm-btn fm-primary" onClick={spocti} disabled={pocita || !profilOk || !vstupyOk}>
        {pocita ? "Počítám…" : "Spočítat PPA"}
      </button>
      {zprava && <div style={{ color: "var(--fm-brand-dk)", fontSize: 13, marginTop: 10 }}>{zprava}</div>}
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}

      {/* 3) Výsledek */}
      {v && (
        <div style={{ marginTop: 18 }}>
          <h4 style={{ margin: "0 0 8px", fontSize: 13 }}>
            Navržená FVE: <b>{v.kwp} kWp</b>
            {vysledek.vstup?.navrzeno_automaticky ? (
              <span className="nb-badge" style={{ marginLeft: 8 }} title="Velikost navrhla appka podle nejlepší ekonomiky (NPV/návratnost)">
                ekonomický návrh
              </span>
            ) : (
              <span className="nb-badge" style={{ marginLeft: 8 }}>ruční výkon</span>
            )}
          </h4>
          <div className="fm-card" style={{ padding: 14, marginBottom: 14, background: "var(--fm-bg, #fafafa)" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap", marginBottom: 8 }}>
              <span style={{ fontSize: 26, fontWeight: 700, color: "var(--brand-strong)" }}>{pct(v.pokryti_spotreby_fve)}</span>
              <span style={{ fontSize: 13 }}>spotřeby klienta pokryje elektřina z FVE (samospotřeba)</span>
            </div>
            <div style={{ fontSize: 13, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 6 }}>
              <div>Roční výroba: <b>{mwh(v.vyroba_rok1_kwh)}</b> ({v.merny_vynos_kwh_kwp} kWh/kWp · orientace {v.k_orient})</div>
              <div>Roční spotřeba: <b>{mwh(v.rocni_spotreba_kwh)}</b> (výroba/spotřeba {pct(v.pomer_vyroba_spotreba)})</div>
              <div>Samospotřeba: <b>{mwh(v.samospotreba_rok1_kwh)}</b> ({pct(v.mira_samospotreby)} výroby)</div>
              <div>Přetok do sítě: {mwh(v.export_rok1_kwh)}{v.orez_rok1_kwh > 0 ? `, ořez ${mwh(v.orez_rok1_kwh)}` : ""}</div>
              <div>Investice (CAPEX): <b>{kc(v.capex_kc)}</b></div>
              {v.vyhnutelna_cena_rok1_kc_mwh != null && (
                <div>
                  Vyhnutelná cena klienta: <b>{Math.round(v.vyhnutelna_cena_rok1_kc_mwh).toLocaleString("cs-CZ")} Kč/MWh</b>{" "}
                  (silová {Math.round(v.cena_silova_kc_mwh).toLocaleString("cs-CZ")} + regulované{" "}
                  {Math.round((v.vyhnutelne_regulovane_kc_mwh || 0) + (v.poze_kc_mwh || 0)).toLocaleString("cs-CZ")})
                </div>
              )}
            </div>
          </div>

          <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Ekonomika investora (Greensie)</h4>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 14 }}>
            <div className="fm-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>Návratnost</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{roky(v.navratnost_roky)}</div>
            </div>
            <div className="fm-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>IRR</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{v.irr == null ? "—" : pct(v.irr)}</div>
            </div>
            <div className="fm-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>NPV (diskont {pct(v.diskontni_sazba)})</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{kc(v.npv_kc)}</div>
            </div>
            <div className="fm-card" style={{ padding: 14 }}>
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>Kum. úspora klienta</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{kc(v.souhrn_klient?.uspora_kum_kc)}</div>
            </div>
          </div>

          {(vysledek.varianty || []).length > 1 && (
            <>
              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Srovnání velikostí (ekonomický výběr)</h4>
              <div className="nb-scroll" style={{ marginBottom: 14 }}>
                <table className="nb-table">
                  <thead>
                    <tr><th>Velikost</th><th>Pokrytí spotřeby</th><th>Samospotřeba</th><th>Výroba</th><th>CAPEX</th><th>Návratnost</th><th>NPV</th></tr>
                  </thead>
                  <tbody>
                    {vysledek.varianty.map((z) => (
                      <tr key={z.kwp} style={z.kwp === v.kwp ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" } : undefined}>
                        <td>{z.kwp} kWp{z.kwp === v.kwp ? " ◄" : ""}</td>
                        <td>{pct(z.pokryti_spotreby_fve)}</td>
                        <td>{pct(z.mira_samospotreby)}</td>
                        <td>{mwh(z.vyroba_rok1_kwh)}</td>
                        <td>{kc(z.capex_kc)}</td>
                        <td>{roky(z.navratnost_roky)}</td>
                        <td>{kc(z.npv_kc)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: -8, marginBottom: 14 }}>
                Vybrána velikost s nejlepší ekonomikou (nejvyšší NPV / nejkratší návratnost). Řádek ◄ = navržená.
              </div>
            </>
          )}

          {v.graf && (
            <>
              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Výroba FVE vs. spotřeba (měsíčně, rok 1)</h4>
              <div style={{ marginBottom: 16 }}>
                <GrafVyrobaSpotreba graf={v.graf} />
              </div>
            </>
          )}

          {v.roky?.length > 0 && (
            <>
              <h4 style={{ margin: "0 0 6px", fontSize: 13 }}>Úspora a návratnost po letech</h4>
              <div className="nb-scroll">
                <table className="nb-table">
                  <thead>
                    <tr>
                      <th>Rok</th>
                      <th>Výroba</th>
                      <th>Samospotř.</th>
                      <th>Cena PPA</th>
                      <th>Vyhnutelná cena</th>
                      <th>Úspora klienta</th>
                      <th>Kum. úspora</th>
                      <th>CF investora</th>
                      <th>Kum. CF</th>
                    </tr>
                  </thead>
                  <tbody>
                    {v.roky.map((r) => {
                      const paybackRok = v.navratnost_roky != null && r.rok === Math.ceil(v.navratnost_roky);
                      return (
                        <tr key={r.rok} style={paybackRok ? { fontWeight: 700, background: "color-mix(in srgb, var(--brand) 9%, transparent)" } : undefined}>
                          <td>{r.rok}{paybackRok ? " ◄" : ""}</td>
                          <td>{mwh(r.vyroba_kwh)}</td>
                          <td>{mwh(r.samospotreba_kwh)}</td>
                          <td>{Math.round(r.cena_ppa_kc_mwh).toLocaleString("cs-CZ")}</td>
                          <td>{Math.round(r.cena_dodavatel_kc_mwh).toLocaleString("cs-CZ")}</td>
                          <td>{kc(r.uspora_klient_kc)}</td>
                          <td>{kc(r.uspora_klient_kum_kc)}</td>
                          <td>{kc(r.cf_investor_kc)}</td>
                          <td>{kc(r.cf_kum_investor_kc)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div style={{ fontSize: 11, color: "var(--fm-muted)", marginTop: 4 }}>
                Ceny jsou Kč/MWh. Úspora klienta = samospotřeba × (vyhnutelná cena − PPA cena);
                vyhnutelná cena = silová složka + vyhnutelné regulované platby (použití sítí,
                systémové služby, POZE), daň z elektřiny symetricky mimo. CF investora = platby
                za samospotřebu {v.prebytek_uctovat ? "+ prodej přetoku " : ""}− O&M. Řádek ◄ = rok návratnosti.
              </div>
            </>
          )}

          {(vysledek.upozorneni || []).length > 0 && (
            <div style={{ fontSize: 12, color: "var(--fm-muted)", marginTop: 10 }}>
              {vysledek.upozorneni.map((u, i) => <div key={i}>• {u}</div>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
