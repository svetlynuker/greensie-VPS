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
  // Velikost vybraná kliknutím v tabulce srovnání (null = navržená).
  const [vybranyKwp, setVybranyKwp] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [pocita, setPocita] = useState(false);
  // Která záložka výsledku je otevřená (stejné rozvržení jako peak shaving).
  const [zalozka, setZalozka] = useState("ekonomika");

  useEffect(() => {
    ppaProfilSouhrn(nabidka.id)
      .then(setSouhrn)
      .catch(() => setSouhrn({ pocet: 0 }));
  }, [nabidka.id]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const profilOk = souhrn && souhrn.pocet > 0;
  const cenaPpaOk = n(cenaPpa) > 0;
  const cenaSilovaOk = n(cenaSilova) > 0;
  const delkaOk = n(delka) > 0;
  const vstupyOk = cenaPpaOk && cenaSilovaOk && delkaOk;
  const vsePripraveno = profilOk && vstupyOk;

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
      setVybranyKwp(null);
      setZalozka("ekonomika");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

  const navrzena = vysledek?.vysledek;
  const varianty = vysledek?.varianty || [];
  // Detail velikosti vybrané kliknutím ve srovnání. Starší uložené výsledky
  // mají u variant jen souhrn (bez `roky`/`graf`) → detail jde zobrazit jen
  // pro navrženou velikost; nové výpočty nesou plná data všech variant.
  const vybrana =
    vybranyKwp != null ? varianty.find((z) => z.kwp === vybranyKwp && z.roky) : null;
  const v = vybrana || navrzena;
  const jeAlternativa = vybrana && vybrana.kwp !== navrzena?.kwp;

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
          <h4>Profil spotřeby</h4>
          <div className="gs-step-sub">
            15minutový export z portálu distributora. Výroba FVE se simuluje, nenahrává.
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
              <div>Profil zatím není načtený — bez něj výpočet nejde spustit.</div>
            </div>
          )}
          {profilDoklady.length === 0 ? (
            <div className="nb-warn" style={{ margin: "8px 0 0" }}>
              <span>⚠️</span>
              <span>Nejdřív nahraj soubor se spotřebou (sekce Podklady výše).</span>
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
        </section>

        {/* 2) Fotovoltaika */}
        <section className="gs-step">
          <span className="gs-step-num">2</span>
          <h4>Fotovoltaika</h4>
          <div className="gs-step-sub">
            Velikost navrhne appka tak, aby výroba nejlépe pokrývala spotřebu. Volitelně ji omez
            střechou, nebo zadej výkon napevno.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-maxkwp">
                Max. dle střechy
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-maxkwp"
                  className="gs-input"
                  value={maxKwp}
                  onChange={(e) => setMaxKwp(e.target.value)}
                  inputMode="decimal"
                  placeholder="strop"
                />
                <span className="gs-unit-txt">kWp</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-kwp">
                Výkon napevno
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-kwp"
                  className="gs-input"
                  value={kwpOverride}
                  onChange={(e) => setKwpOverride(e.target.value)}
                  inputMode="decimal"
                  placeholder="navrhne se"
                />
                <span className="gs-unit-txt">kWp</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-sklon">
                Sklon panelů
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-sklon"
                  className="gs-input"
                  value={sklon}
                  onChange={(e) => setSklon(e.target.value)}
                  inputMode="decimal"
                />
                <span className="gs-unit-txt">°</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-azimut">
                Azimut
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-azimut"
                  className="gs-input"
                  value={azimut}
                  onChange={(e) => setAzimut(e.target.value)}
                  inputMode="decimal"
                />
                <span className="gs-unit-txt">°</span>
              </div>
              <div className="gs-pozn">0 = jih, 90 = západ</div>
            </div>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-capex">
              Náklady na FVE
            </label>
            <select
              id="ppa-capex"
              className="gs-input"
              value={rezimCapex}
              onChange={(e) => setRezimCapex(e.target.value)}
            >
              <option value="cena_kwp">Zjednodušeně (cena za kWp)</option>
              <option value="komponenty">Skutečné (komponenty z katalogu)</option>
            </select>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-rezvykon">
              Max. rezervovaný výkon dodávky <span style={{ fontWeight: 400 }}>(nepovinné)</span>
            </label>
            <div className="gs-unit">
              <input
                id="ppa-rezvykon"
                className="gs-input"
                value={rezVykon}
                onChange={(e) => setRezVykon(e.target.value)}
                inputMode="decimal"
                placeholder="neomezeno"
              />
              <span className="gs-unit-txt">kW</span>
            </div>
          </div>
        </section>

        {/* 3) Smlouva PPA */}
        <section className="gs-step">
          <span className="gs-step-num">3</span>
          <h4>Smlouva PPA</h4>
          <div className="gs-step-sub">
            Cena, za kterou Greensie dodává, proti ceně, které se klient vyhne.
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-cena">
              PPA cena rok 1
            </label>
            <div className="gs-unit">
              <input
                id="ppa-cena"
                className="gs-input"
                value={cenaPpa}
                onChange={(e) => setCenaPpa(e.target.value)}
                inputMode="decimal"
                placeholder="např. 2500"
              />
              <span className="gs-unit-txt">Kč/MWh</span>
            </div>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-silova">
              Silová cena dodavatele
            </label>
            <div className="gs-unit">
              <input
                id="ppa-silova"
                className="gs-input"
                value={cenaSilova}
                onChange={(e) => setCenaSilova(e.target.value)}
                inputMode="decimal"
                placeholder="např. 3200"
              />
              <span className="gs-unit-txt">Kč/MWh</span>
            </div>
            <div className="gs-pozn">
              Jen silová složka. Regulované platby, kterým se klient vyhne, jsou v poli níž.
            </div>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-reg">
              Vyhnutelné regulované <span style={{ fontWeight: 400 }}>(nepovinné)</span>
            </label>
            <div className="gs-unit">
              <input
                id="ppa-reg"
                className="gs-input"
                value={regulovane}
                onChange={(e) => setRegulovane(e.target.value)}
                inputMode="decimal"
                placeholder="z nastavení (~260)"
              />
              <span className="gs-unit-txt">Kč/MWh</span>
            </div>
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-delka">
                Délka kontraktu
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-delka"
                  className="gs-input"
                  value={delka}
                  onChange={(e) => setDelka(e.target.value)}
                  inputMode="numeric"
                />
                <span className="gs-unit-txt">let</span>
              </div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-index">
                Index PPA <span style={{ fontWeight: 400 }}>(volit.)</span>
              </label>
              <input
                id="ppa-index"
                className="gs-input"
                value={indexPpa}
                onChange={(e) => setIndexPpa(e.target.value)}
                inputMode="decimal"
                placeholder="např. 0.03"
              />
            </div>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-indexdod">
              Index dodavatele <span style={{ fontWeight: 400 }}>(volit.)</span>
            </label>
            <input
              id="ppa-indexdod"
              className="gs-input"
              value={indexDod}
              onChange={(e) => setIndexDod(e.target.value)}
              inputMode="decimal"
              placeholder="default = index PPA"
            />
          </div>
          <label className="gs-zaskrt" style={{ margin: "4px 0 10px" }}>
            <input
              type="checkbox"
              checked={prebytekUctovat}
              onChange={(e) => setPrebytekUctovat(e.target.checked)}
            />
            <span>Účtovat přetok do sítě (prodej přebytku)</span>
          </label>
          {prebytekUctovat && (
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-prebytek">
                Cena přebytku
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-prebytek"
                  className="gs-input"
                  value={prebytekCena}
                  onChange={(e) => setPrebytekCena(e.target.value)}
                  inputMode="decimal"
                  placeholder="dle lokality/smlouvy"
                />
                <span className="gs-unit-txt">Kč/MWh</span>
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="gs-panel-f">
        <button className="fm-btn fm-primary" onClick={spocti} disabled={pocita || !vsePripraveno}>
          {pocita ? "Počítám…" : "Spočítat PPA"}
        </button>

        <ul className="gs-chk" style={{ marginTop: 10 }}>
          <li className={profilOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">{profilOk ? "✓" : "!"}</span>
            <span>{profilOk ? "Profil spotřeby načtený" : "Načti 15min profil spotřeby"}</span>
          </li>
          <li className={cenaPpaOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">{cenaPpaOk ? "✓" : "!"}</span>
            <span>{cenaPpaOk ? "PPA cena zadaná" : "Zadej PPA cenu rok 1"}</span>
          </li>
          <li className={cenaSilovaOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">{cenaSilovaOk ? "✓" : "!"}</span>
            <span>{cenaSilovaOk ? "Silová cena zadaná" : "Zadej silovou cenu dodavatele"}</span>
          </li>
          <li className={delkaOk ? "gs-chk-ok" : "gs-chk-no"}>
            <span className="gs-chk-mark" aria-hidden="true">{delkaOk ? "✓" : "!"}</span>
            <span>{delkaOk ? "Délka kontraktu zadaná" : "Zadej délku kontraktu"}</span>
          </li>
        </ul>

        {zprava && (
          <div style={{ color: "var(--brand-strong)", fontSize: 12, marginTop: 8 }}>{zprava}</div>
        )}
        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 12, marginTop: 8 }}>{chyba}</div>}

        <div className="gs-pozn" style={{ marginTop: 10 }}>
          Prázdné indexy a náklady doplní appka z{" "}
          <a
            href="/nabidkovac/katalog"
            style={{ color: "var(--brand-strong)" }}
            title="Katalog a výpočtová nastavení – záložka PPA pro FVE"
          >
            výpočtových nastavení
          </a>
          .
        </div>
      </div>
    </form>
  );

  // ==================== VÝSLEDEK (pravý sloupec) ====================
  let obsahVysledku;
  if (!v) {
    obsahVysledku = (
      <div className="fm-card" style={{ padding: 32, textAlign: "center", color: "var(--muted)" }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: "var(--ink)" }}>
          Výsledek se objeví tady
        </div>
        <div style={{ fontSize: 12.5 }}>
          Vlevo doplň vstupy a spusť výpočet. Panel vlevo zůstane po ruce, takže půjde měnit PPA
          cenu a hned vedle sledovat, co to udělá s návratností.
        </div>
      </div>
    );
  } else {
    obsahVysledku = (
      <>
        <div className="gs-res-h">
          <div>
            <div className="gs-nadtitul">
              {jeAlternativa ? "Zobrazená velikost" : "Navržená velikost"}
              {varianty.length > 1 && (
                <span style={{ fontWeight: 400, textTransform: "none", letterSpacing: 0 }}>
                  {" "}
                  — z {varianty.length} spočítaných
                </span>
              )}
            </div>
            <h3>
              {v.kwp} kWp
              {jeAlternativa ? (
                <span className="nb-badge pozor">
                  alternativa — návrh je {navrzena?.kwp} kWp
                </span>
              ) : vysledek.vstup?.navrzeno_automaticky ? (
                <span
                  className="nb-badge znacka"
                  title="Velikost navrhla appka podle nejlepší ekonomiky (NPV/návratnost)"
                >
                  ekonomický návrh
                </span>
              ) : (
                <span className="nb-badge">ruční výkon</span>
              )}
              {v.doporuceno === false && <span className="nb-badge spatne">nevyplatí se</span>}
            </h3>
          </div>
          <span className="gs-mezera" />
        </div>

        {(vysledek.upozorneni || []).length > 0 && (
          <div className="nb-warn" style={{ margin: "0 0 12px" }}>
            <span>⚠️</span>
            <span>{vysledek.upozorneni.join(" ")}</span>
          </div>
        )}

        {v.doporuceno === false && (
          <div className="nb-warn" style={{ margin: "0 0 12px" }}>
            <span>⚠️</span>
            <span>
              PPA se při těchto parametrech investorovi nevyplatí (záporné NPV při diskontu{" "}
              {pct(v.diskontni_sazba)}). Zvaž vyšší PPA cenu, delší kontrakt nebo levnější CAPEX.
            </span>
          </div>
        )}

        {/* KPI: nahoře to, co zajímá klienta, za tím ekonomika investora */}
        <div className="gs-kpis">
          <div className="gs-kpi accent">
            <div className="gs-kpi-label">Pokrytí spotřeby z FVE</div>
            <div className="gs-kpi-value">{pct(v.pokryti_spotreby_fve)}</div>
            <div className="gs-kpi-sub">
              samospotřeba {mwh(v.samospotreba_rok1_kwh)} z výroby {mwh(v.vyroba_rok1_kwh)}
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">Návratnost investora</div>
            <div className="gs-kpi-value">{roky(v.navratnost_roky)}</div>
            <div className="gs-kpi-sub">
              kontrakt {vysledek.vstup?.delka_kontraktu_roky ?? v.roky?.length ?? "—"} let
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">NPV / IRR</div>
            <div className="gs-kpi-value">{kc(v.npv_kc)}</div>
            <div className="gs-kpi-sub">
              {v.irr == null ? "IRR —" : `IRR ${pct(v.irr)}`} · diskont {pct(v.diskontni_sazba)}
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">Investice (CAPEX)</div>
            <div className="gs-kpi-value">{kc(v.capex_kc)}</div>
            <div className="gs-kpi-sub">
              {v.merny_vynos_kwh_kwp} kWh/kWp · orientace {v.k_orient}
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">Kum. úspora klienta</div>
            <div className="gs-kpi-value">{kc(v.souhrn_klient?.uspora_kum_kc)}</div>
            <div className="gs-kpi-sub">za celou dobu kontraktu</div>
          </div>
        </div>

        <div className="gs-tabs gs-tabs-odsazeni" role="tablist" aria-label="Části výsledku">
          {[
            { klic: "ekonomika", nazev: "Energie a ekonomika" },
            { klic: "graf", nazev: "Výroba vs. spotřeba" },
            { klic: "velikosti", nazev: "Srovnání velikostí", pocet: varianty.length },
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

        {/* ---------- záložka: energie a ekonomika ---------- */}
        {zalozka === "ekonomika" && (
          <div role="tabpanel">
            <div className="gs-dve-karty">
              <div className="fm-card gs-karta">
                <div className="gs-karta-h">
                  <span className="gs-karta-nazev">Energie (rok 1)</span>
                  <span className="gs-mezera" />
                  <span className="nb-badge">{v.kwp} kWp</span>
                </div>
                <table className="nb-table">
                  <tbody>
                    <tr>
                      <td>Roční výroba</td>
                      <td className="n">{mwh(v.vyroba_rok1_kwh)}</td>
                    </tr>
                    <tr>
                      <td>Roční spotřeba klienta</td>
                      <td className="n">{mwh(v.rocni_spotreba_kwh)}</td>
                    </tr>
                    <tr>
                      <td className="dim">Výroba / spotřeba</td>
                      <td className="n dim">{pct(v.pomer_vyroba_spotreba)}</td>
                    </tr>
                    <tr className="soucet">
                      <td>Samospotřeba (fakturuje se)</td>
                      <td className="n">{mwh(v.samospotreba_rok1_kwh)}</td>
                    </tr>
                    <tr>
                      <td className="dim">… z toho podíl výroby</td>
                      <td className="n dim">{pct(v.mira_samospotreby)}</td>
                    </tr>
                    <tr>
                      <td>Přetok do sítě</td>
                      <td className="n">{mwh(v.export_rok1_kwh)}</td>
                    </tr>
                    {v.orez_rok1_kwh > 0 && (
                      <tr>
                        <td className="dim">… ořez výroby</td>
                        <td className="n dim">{mwh(v.orez_rok1_kwh)}</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="fm-card gs-karta">
                <div className="gs-karta-h">
                  <span className="gs-karta-nazev">Ceny a ekonomika</span>
                  <span className="gs-mezera" />
                  <span className="nb-badge">Kč/MWh bez DPH</span>
                </div>
                <table className="nb-table">
                  <tbody>
                    {v.vyhnutelna_cena_rok1_kc_mwh != null && (
                      <>
                        <tr>
                          <td>Silová cena dodavatele</td>
                          <td className="n">
                            {Math.round(v.cena_silova_kc_mwh).toLocaleString("cs-CZ")}
                          </td>
                        </tr>
                        <tr>
                          <td>Vyhnutelné regulované + POZE</td>
                          <td className="n">
                            {Math.round(
                              (v.vyhnutelne_regulovane_kc_mwh || 0) + (v.poze_kc_mwh || 0)
                            ).toLocaleString("cs-CZ")}
                          </td>
                        </tr>
                        <tr className="soucet">
                          <td>Vyhnutelná cena klienta</td>
                          <td className="n">
                            {Math.round(v.vyhnutelna_cena_rok1_kc_mwh).toLocaleString("cs-CZ")}
                          </td>
                        </tr>
                      </>
                    )}
                    <tr>
                      <td>PPA cena rok 1</td>
                      <td className="n">
                        {v.roky?.[0]?.cena_ppa_kc_mwh != null
                          ? Math.round(v.roky[0].cena_ppa_kc_mwh).toLocaleString("cs-CZ")
                          : "—"}
                      </td>
                    </tr>
                    <tr className="soucet">
                      <td>Investice (CAPEX)</td>
                      <td className="n">{kc(v.capex_kc)}</td>
                    </tr>
                    <tr>
                      <td>Návratnost investora</td>
                      <td className="n">{roky(v.navratnost_roky)}</td>
                    </tr>
                    <tr>
                      <td>NPV (diskont {pct(v.diskontni_sazba)})</td>
                      <td className="n">{kc(v.npv_kc)}</td>
                    </tr>
                    <tr>
                      <td className="dim">IRR</td>
                      <td className="n dim">{v.irr == null ? "—" : pct(v.irr)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <details className="gs-meta" style={{ marginTop: 12 }}>
              <summary>Jak se počítá úspora klienta a cash flow investora</summary>
              <div className="gs-meta-in">
                <b>Úspora klienta</b> = samospotřeba × (vyhnutelná cena − PPA cena). Vyhnutelná cena
                je silová složka plus regulované platby, kterým se klient odběrem z FVE vyhne
                (použití sítí, systémové služby, POZE); daň z elektřiny je symetricky mimo.{" "}
                <b>Cash flow investora</b> = platby za samospotřebu
                {v.prebytek_uctovat ? " + prodej přetoku" : ""} − O&amp;M. Velikost FVE navrhuje
                appka podle nejlepší ekonomiky (nejvyšší NPV, resp. nejkratší návratnost) — proto
                nemusí být největší, která se na střechu vejde.
              </div>
            </details>
          </div>
        )}

        {/* ---------- záložka: graf ---------- */}
        {zalozka === "graf" && (
          <div role="tabpanel">
            {v.graf ? (
              <div className="fm-card" style={{ padding: 0 }}>
                <div className="gs-karta-h">
                  <span style={{ fontSize: 13, fontWeight: 700 }}>
                    Výroba FVE vs. spotřeba (měsíčně, rok 1)
                  </span>
                  <span className="gs-mezera" />
                  <span className="nb-badge">{v.kwp} kWp</span>
                </div>
                <div style={{ padding: 14 }}>
                  <GrafVyrobaSpotreba graf={v.graf} />
                </div>
              </div>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                Graf pro tuhle velikost není — u starších výsledků se ukládal jen pro navrženou
                velikost. Spusť „Spočítat PPA“ znovu.
              </div>
            )}
          </div>
        )}

        {/* ---------- záložka: srovnání velikostí ---------- */}
        {zalozka === "velikosti" && (
          <div role="tabpanel">
            {varianty.length > 1 ? (
              <>
                <div className="fm-card" style={{ padding: 0 }}>
                  <div className="gs-karta-h">
                    <span style={{ fontSize: 13, fontWeight: 700 }}>Srovnání velikostí</span>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>
                      ekonomický výběr — navržena velikost s nejlepší ekonomikou
                    </span>
                  </div>
                  <div className="nb-scroll" style={{ border: 0, borderRadius: 0, boxShadow: "none" }}>
                    <table className="nb-table">
                      <thead>
                        <tr>
                          <th>Velikost</th>
                          <th className="n">Pokrytí spotřeby</th>
                          <th className="n">Samospotřeba</th>
                          <th className="n">Výroba</th>
                          <th className="n">CAPEX</th>
                          <th className="n">Návratnost</th>
                          <th className="n">NPV</th>
                        </tr>
                      </thead>
                      <tbody>
                        {varianty.map((z) => (
                          <tr
                            key={z.kwp}
                            onClick={() => z.roky && setVybranyKwp(z.kwp === navrzena?.kwp ? null : z.kwp)}
                            title={
                              z.roky
                                ? "Kliknutím zobrazíš detail této velikosti"
                                : "Starší výsledek – detail variant se uloží až s novým výpočtem"
                            }
                            style={{
                              cursor: z.roky ? "pointer" : "default",
                              ...(z.kwp === v.kwp
                                ? {
                                    fontWeight: 700,
                                    background: "color-mix(in srgb, var(--brand) 9%, transparent)",
                                  }
                                : {}),
                            }}
                          >
                            <td>
                              {z.kwp === v.kwp ? "◄ " : ""}
                              {z.kwp} kWp
                              {z.kwp === navrzena?.kwp && (
                                <span className="nb-badge znacka" style={{ marginLeft: 6 }}>
                                  návrh
                                </span>
                              )}
                            </td>
                            <td className="n">{pct(z.pokryti_spotreby_fve)}</td>
                            <td className="n">{pct(z.mira_samospotreby)}</td>
                            <td className="n">{mwh(z.vyroba_rok1_kwh)}</td>
                            <td className="n">{kc(z.capex_kc)}</td>
                            <td className="n">{roky(z.navratnost_roky)}</td>
                            <td className="n">{kc(z.npv_kc)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="gs-pozn">
                  <b>Kliknutím na řádek se celý výsledek překreslí pro danou velikost</b> (◄ =
                  zobrazená) — čísla jsou nad tabulkou, takže je změna hned vidět.
                </div>
              </>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                Výpočet zvažoval jen jednu velikost — není co srovnávat. Srovnání se objeví, když
                velikost navrhuje appka (pole „Výkon napevno“ nechej prázdné).
              </div>
            )}
          </div>
        )}

        {/* ---------- záložka: po letech ---------- */}
        {zalozka === "roky" && (
          <div role="tabpanel">
            {v.roky?.length > 0 ? (
              <>
                <div className="fm-card" style={{ padding: 0 }}>
                  <div className="gs-karta-h">
                    <span style={{ fontSize: 13, fontWeight: 700 }}>
                      Úspora klienta a návratnost po letech
                    </span>
                    <span className="gs-mezera" />
                    <span className="nb-badge">kontrakt {v.roky.length} let</span>
                  </div>
                  <div className="nb-scroll" style={{ border: 0, borderRadius: 0, boxShadow: "none" }}>
                    <table className="nb-table">
                      <thead>
                        <tr>
                          <th>Rok</th>
                          <th className="n">Výroba</th>
                          <th className="n">Samospotř.</th>
                          <th className="n">Cena PPA</th>
                          <th className="n">Vyhnutelná cena</th>
                          <th className="n">Úspora klienta</th>
                          <th className="n">Kum. úspora</th>
                          <th className="n">CF investora</th>
                          <th className="n">Kum. CF</th>
                        </tr>
                      </thead>
                      <tbody>
                        {v.roky.map((r) => {
                          const paybackRok =
                            v.navratnost_roky != null && r.rok === Math.ceil(v.navratnost_roky);
                          return (
                            <tr
                              key={r.rok}
                              className="staticky"
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
                              <td className="n">{mwh(r.vyroba_kwh)}</td>
                              <td className="n">{mwh(r.samospotreba_kwh)}</td>
                              <td className="n">
                                {Math.round(r.cena_ppa_kc_mwh).toLocaleString("cs-CZ")}
                              </td>
                              <td className="n">
                                {Math.round(r.cena_dodavatel_kc_mwh).toLocaleString("cs-CZ")}
                              </td>
                              <td className="n">{kc(r.uspora_klient_kc)}</td>
                              <td className="n">{kc(r.uspora_klient_kum_kc)}</td>
                              <td className="n">{kc(r.cf_investor_kc)}</td>
                              <td className="n">{kc(r.cf_kum_investor_kc)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
                <div className="gs-pozn">
                  Ceny jsou Kč/MWh. Řádek ◄ = rok návratnosti investora. Úspora klienta =
                  samospotřeba × (vyhnutelná cena − PPA cena).
                </div>
              </>
            ) : (
              <div className="fm-card" style={{ padding: 16, fontSize: 12.5, color: "var(--muted)" }}>
                Rozpis po letech není — u starších výsledků se ukládal jen pro navrženou velikost.
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
      <div>{obsahVysledku}</div>
    </div>
  );
}
