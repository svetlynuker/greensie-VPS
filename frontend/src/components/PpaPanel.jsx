import { useEffect, useState } from "react";
import GrafVyrobaSpotreba from "./GrafVyrobaSpotreba";
import GrafPrubehuPpa from "./GrafPrubehuPpa";
import { ppaPrubeh, ppaProfilSouhrn, ppaVypocet, profilZpracuj } from "../api";

// Panel PPA (výpočet v2 – docs/METODIKA-ppa-v2.md).
//
// Proti v1 je zadání obrácené: OZ nezadává cenu PPA ani délku kontraktu, ale
// cenu, kterou zákazník platí dnes, a cíl samospotřeby. Appka dopočítá velikost
// FVE a **nejnižší cenu PPA**, která projde bankou (DSCR) i investorem (IRR),
// pro každou nabízenou délku kontraktu (10/15/20 let). Délku nedoporučuje –
// vybírá obchodník podle toho, co zákazník podepíše.

function kc(x) {
  return x == null ? "—" : `${Math.round(x).toLocaleString("cs-CZ")} Kč`;
}
function kcMwh(x) {
  return x == null ? "—" : `${Math.round(x).toLocaleString("cs-CZ")} Kč/MWh`;
}
function mwh(x) {
  return x == null ? "—" : `${x.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} MWh`;
}
function pct(x, des = 1) {
  return x == null ? "—" : `${(x * 100).toLocaleString("cs-CZ", { maximumFractionDigits: des })} %`;
}
function cislo(x, des = 2) {
  return x == null ? "—" : x.toLocaleString("cs-CZ", { minimumFractionDigits: des, maximumFractionDigits: des });
}
function fmtDatumCas(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "—";
}
function n(v) {
  const t = String(v).replace(",", ".").trim();
  return t === "" ? null : Number(t);
}

export default function PpaPanel({ nabidka }) {
  const [souhrn, setSouhrn] = useState(null);
  const [zpracovavaId, setZpracovavaId] = useState(null);

  // Poslední uložený PPA výpočet – z něj předvyplníme vstupy, ať jde po
  // znovuotevření nabídky rovnou přepočítávat.
  const _rr = (nabidka.reseni || []).filter((x) => x.typ_reseni === "ppa");
  const _posl = _rr.length ? _rr[_rr.length - 1].popis_json : null;
  // Starší (v1) výsledky mají úplně jiná pole – nebudeme je zkoušet vykreslit.
  const _jeV2 = _posl?.verze === 2;
  const _v = (_jeV2 && _posl?.vstup) || {};
  const s = (x) => (x == null ? "" : String(x));

  const [cenaSilova, setCenaSilova] = useState(s(_v.cena_silova_kc_mwh));
  const [regulovane, setRegulovane] = useState(s(_v.vyhnutelne_regulovane_kc_mwh));
  const [cilSs, setCilSs] = useState(
    _v.cil_mira_samospotreby != null ? String(Math.round(_v.cil_mira_samospotreby * 100)) : "80"
  );
  const [cenaExportu, setCenaExportu] = useState(s(_v.cena_exportu_kc_mwh ?? 0));
  const [maxKwp, setMaxKwp] = useState(s(_v.max_kwp));
  const [sklon, setSklon] = useState(_v.sklon_st != null ? s(_v.sklon_st) : "35");
  const [azimut, setAzimut] = useState(_v.azimut_st != null ? s(_v.azimut_st) : "0");
  const [rezVykon, setRezVykon] = useState(s(_v.rezervovany_vykon_dodavky_kw));
  const [sBaterii, setSBaterii] = useState(!!_v.s_baterii);
  const [batKapacita, setBatKapacita] = useState("");
  const [batVykon, setBatVykon] = useState("");
  const [batCena, setBatCena] = useState("");

  const [vysledek, setVysledek] = useState(_jeV2 ? _posl : null);
  const [staryVysledek] = useState(_posl && !_jeV2 ? _posl : null);
  const [varianta, setVarianta] = useState("bez_baterie");
  const [delka, setDelka] = useState(null);
  const [zalozka, setZalozka] = useState("ekonomika");
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [pocita, setPocita] = useState(false);
  // Průběh se tahá zvlášť (na vyžádání), ať se ~35 tis. hodnot nenosí v každé
  // odpovědi výpočtu. Klíč = varianta, aby se přepnutím nezobrazila cizí data.
  const [prubeh, setPrubeh] = useState(null);
  const [prubehChyba, setPrubehChyba] = useState(null);
  const [prubehNacita, setPrubehNacita] = useState(false);

  useEffect(() => {
    ppaProfilSouhrn(nabidka.id)
      .then(setSouhrn)
      .catch(() => setSouhrn({ pocet: 0 }));
  }, [nabidka.id]);

  // Průběh se načte teprve při otevření záložky (a znovu po přepnutí varianty),
  // ať se celoroční řady netahají zbytečně.
  useEffect(() => {
    if (zalozka !== "prubeh" || !vysledek || prubeh || prubehNacita) return;
    let zruseno = false;
    setPrubehNacita(true);
    setPrubehChyba(null);
    ppaPrubeh(nabidka.id, varianta)
      .then((d) => {
        if (!zruseno) setPrubeh(d);
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
  }, [zalozka, varianta, vysledek, prubeh, prubehNacita, nabidka.id]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const profilOk = souhrn && souhrn.pocet > 0;
  const cenaSilovaOk = n(cenaSilova) > 0;
  const cilOk = n(cilSs) > 0 && n(cilSs) <= 100;
  const vsePripraveno = profilOk && cenaSilovaOk && cilOk;

  async function nactiProfil(dokumentId) {
    setChyba(null);
    setZprava(null);
    setZpracovavaId(dokumentId);
    try {
      await profilZpracuj(nabidka.id, dokumentId);
      const sh = await ppaProfilSouhrn(nabidka.id);
      setSouhrn(sh);
      setZprava(`Profil načten: ${sh.pocet.toLocaleString("cs-CZ")} intervalů.`);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZpracovavaId(null);
    }
  }

  async function spocitat() {
    setChyba(null);
    setZprava(null);
    setPocita(true);
    try {
      const data = {
        hladina: "VN",
        cena_silova_kc_mwh: n(cenaSilova),
        vyhnutelne_regulovane_kc_mwh: n(regulovane),
        cil_mira_samospotreby: n(cilSs) != null ? n(cilSs) / 100 : null,
        cena_exportu_kc_mwh: n(cenaExportu),
        max_kwp: n(maxKwp),
        sklon_st: n(sklon) ?? 35,
        azimut_st: n(azimut) ?? 0,
        rezervovany_vykon_dodavky_kw: n(rezVykon),
        s_baterii: sBaterii,
        baterie_kapacita_kwh: sBaterii ? n(batKapacita) : null,
        baterie_vykon_kw: sBaterii ? n(batVykon) : null,
        baterie_nakladova_cena_kc: sBaterii ? n(batCena) : null,
      };
      const odpoved = await ppaVypocet(nabidka.id, data);
      setVysledek(odpoved.popis_json);
      setVarianta(odpoved.popis_json.bez_baterie ? "bez_baterie" : "s_baterii");
      setDelka(null);
      setPrubeh(null);
      setPrubehChyba(null);
      setZprava("Spočítáno a uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPocita(false);
    }
  }

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

        {/* 2) Co zákazník platí dnes */}
        <section className="gs-step">
          <span className="gs-step-num">2</span>
          <h4>Co zákazník platí dnes</h4>
          <div className="gs-step-sub">
            Silová složka z faktury. PPA nahradí ji a navíc část regulovaných složek za použití
            sítí — samospotřebovaná energie neprochází distribucí. Součet obou je cena, proti
            které se počítá sleva.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-silova">
                Silová složka
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-silova"
                  className="gs-input"
                  value={cenaSilova}
                  onChange={(e) => setCenaSilova(e.target.value)}
                  inputMode="decimal"
                  placeholder="např. 3500"
                />
                <span className="gs-unit-txt">Kč/MWh</span>
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
                  placeholder="z nastavení"
                />
                <span className="gs-unit-txt">Kč/MWh</span>
              </div>
              <div className="gs-pozn">Prázdné = z manažerského nastavení (260)</div>
            </div>
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-hladina">
              Napěťová hladina
            </label>
            <select id="ppa-hladina" className="gs-input" value="VN" disabled>
              <option value="VN">VN</option>
              <option value="NN">NN (zatím nepodporováno)</option>
            </select>
            <div className="gs-pozn">NN se doplní později, sazby na něj nejsou nakalibrované.</div>
          </div>
        </section>

        {/* 3) Elektrárna */}
        <section className="gs-step">
          <span className="gs-step-num">3</span>
          <h4>Elektrárna</h4>
          <div className="gs-step-sub">
            Velikost dopočítá appka tak, aby se zadaný podíl výroby spotřeboval na místě.
            Strop použij, když je omezená střecha nebo připojení.
          </div>
          <div className="gs-dva">
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-cil">
                Cíl samospotřeby
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-cil"
                  className="gs-input"
                  value={cilSs}
                  onChange={(e) => setCilSs(e.target.value)}
                  inputMode="decimal"
                />
                <span className="gs-unit-txt">%</span>
              </div>
              <div className="gs-pozn">Podíl z výroby, ne z odběru</div>
            </div>
            <div className="gs-pole">
              <label className="gs-label" htmlFor="ppa-maxkwp">
                Max. velikost FVE <span style={{ fontWeight: 400 }}>(nepovinné)</span>
              </label>
              <div className="gs-unit">
                <input
                  id="ppa-maxkwp"
                  className="gs-input"
                  value={maxKwp}
                  onChange={(e) => setMaxKwp(e.target.value)}
                  inputMode="decimal"
                  placeholder="bez omezení"
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
            <div className="gs-pozn">Strop přetoku do sítě — co se nevejde, ořízne se.</div>
          </div>
        </section>

        {/* 4) Přetoky */}
        <section className="gs-step">
          <span className="gs-step-num">4</span>
          <h4>Přetoky do sítě</h4>
          <div className="gs-step-sub">
            Výchozí <b>0 Kč</b> — dokud není sjednaný výkup nebo sdílení, přebytek propadá a
            cenu PPA musí pokrýt sám zákazník. Zadanou cenu za export cena PPA naopak sníží.
          </div>
          <div className="gs-pole">
            <label className="gs-label" htmlFor="ppa-export">
              Cena za přetok
            </label>
            <div className="gs-unit">
              <input
                id="ppa-export"
                className="gs-input"
                value={cenaExportu}
                onChange={(e) => setCenaExportu(e.target.value)}
                inputMode="decimal"
                placeholder="0"
              />
              <span className="gs-unit-txt">Kč/MWh</span>
            </div>
          </div>
        </section>

        {/* 5) Baterie */}
        <section className="gs-step">
          <span className="gs-step-num">5</span>
          <h4>Baterie <span style={{ fontWeight: 400, color: "var(--muted)" }}>(volitelně)</span></h4>
          <div className="gs-step-sub">
            Baterie se zákazníkovi účtuje <b>měsíčním nájmem</b>, ne v ceně za kWh. Zvedne
            samospotřebu, takže dovolí větší elektrárnu — ale nájem může úsporu přebít.
            Peak shaving ani bateriové služby tenhle výpočet nezná, ty řeší vlastní modul.
          </div>
          <label className="gs-zaskrt">
            <input type="checkbox" checked={sBaterii} onChange={(e) => setSBaterii(e.target.checked)} />
            <span>Spočítat i variantu s baterií</span>
          </label>
          {sBaterii && (
            <div className="gs-dva" style={{ marginTop: 8 }}>
              <div className="gs-pole">
                <label className="gs-label" htmlFor="ppa-bat-kap">
                  Kapacita
                </label>
                <div className="gs-unit">
                  <input
                    id="ppa-bat-kap"
                    className="gs-input"
                    value={batKapacita}
                    onChange={(e) => setBatKapacita(e.target.value)}
                    inputMode="decimal"
                    placeholder="navrhne se"
                  />
                  <span className="gs-unit-txt">kWh</span>
                </div>
              </div>
              <div className="gs-pole">
                <label className="gs-label" htmlFor="ppa-bat-vykon">
                  Výkon
                </label>
                <div className="gs-unit">
                  <input
                    id="ppa-bat-vykon"
                    className="gs-input"
                    value={batVykon}
                    onChange={(e) => setBatVykon(e.target.value)}
                    inputMode="decimal"
                    placeholder="½ kapacity"
                  />
                  <span className="gs-unit-txt">kW</span>
                </div>
              </div>
              <div className="gs-pole">
                <label className="gs-label" htmlFor="ppa-bat-cena">
                  Nákladová cena
                </label>
                <div className="gs-unit">
                  <input
                    id="ppa-bat-cena"
                    className="gs-input"
                    value={batCena}
                    onChange={(e) => setBatCena(e.target.value)}
                    inputMode="decimal"
                    placeholder="např. 800000"
                  />
                  <span className="gs-unit-txt">Kč</span>
                </div>
                <div className="gs-pozn">Bez ní nejsou čísla varianty platná</div>
              </div>
            </div>
          )}
        </section>

        <div className="gs-panel-f">
          <button className="fm-btn primary" onClick={spocitat} disabled={!vsePripraveno || pocita}>
            {pocita ? "Počítám…" : "Spočítat PPA"}
          </button>
          {!profilOk && <span className="gs-pozn">Chybí profil spotřeby.</span>}
          {profilOk && !cenaSilovaOk && <span className="gs-pozn">Zadej silovou složku ceny.</span>}
          {profilOk && cenaSilovaOk && !cilOk && (
            <span className="gs-pozn">Cíl samospotřeby musí být 1–100 %.</span>
          )}
        </div>

        {chyba && (
          <div className="nb-warn" style={{ marginTop: 10 }}>
            <span>⚠️</span>
            <span>{chyba}</span>
          </div>
        )}
        {zprava && !chyba && (
          <div className="gs-pozn" style={{ marginTop: 10, color: "var(--brand-strong)" }}>
            {zprava}
          </div>
        )}
      </div>
    </form>
  );

  // ==================== VÝSLEDEK ====================
  let obsahVysledku;

  if (!vysledek) {
    obsahVysledku = (
      <div className="fm-card" style={{ padding: 18 }}>
        {staryVysledek ? (
          <>
            <h3 style={{ marginTop: 0 }}>Uložený výpočet je ze starší verze</h3>
            <p style={{ color: "var(--ink-2)", fontSize: 13.5 }}>
              PPA se teď počítá jinak — cenu a délku kontraktu dopočítává appka, dřív je zadával
              obchodník. Starý výsledek proto nejde zobrazit v nové tabulce. Zadej vstupy vlevo a
              spusť <b>Spočítat PPA</b>; starý výpočet zůstane v historii nabídky.
            </p>
          </>
        ) : (
          <>
            <h3 style={{ marginTop: 0 }}>Zatím nespočítáno</h3>
            <p style={{ color: "var(--ink-2)", fontSize: 13.5 }}>
              Vlevo zadej, co zákazník platí dnes, a spusť výpočet. Appka navrhne velikost FVE a
              spočítá nejnižší cenu za kWh, se kterou projekt projde bankou i investorem — pro
              10, 15 a 20 let.
            </p>
          </>
        )}
      </div>
    );
  } else {
    const dostupne = ["bez_baterie", "s_baterii"].filter((k) => vysledek[k]);
    const aktivni = vysledek[varianta] ? varianta : dostupne[0];
    const blok = vysledek[aktivni];
    const delky = blok.po_delkach || [];
    const vybrana = delky.find((x) => x.delka_kontraktu_roky === delka) || delky[0];
    const vst = vysledek.vstup || {};

    const ZALOZKY = [
      { klic: "ekonomika", label: "Přehled" },
      { klic: "roky", label: "Po letech" },
      { klic: "odkup", label: "Odkup" },
      { klic: "graf", label: "Graf" },
      { klic: "prubeh", label: "Průběh" },
    ];

    obsahVysledku = (
      <>
        {/* přepínač varianty technologie */}
        {dostupne.length > 1 && (
          <div className="gs-tabs gs-tabs-odsazeni" role="tablist" aria-label="Varianta technologie">
            {dostupne.map((k) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={aktivni === k}
                onClick={() => {
                  setVarianta(k);
                  setDelka(null);
                  setPrubeh(null);
                  setPrubehChyba(null);
                }}
              >
                {k === "bez_baterie" ? "FVE" : "FVE + baterie"}
              </button>
            ))}
          </div>
        )}

        {/* headline čísla */}
        <div className="gs-kpis">
          <div className="gs-kpi">
            <div className="gs-kpi-label">Velikost FVE</div>
            <div className="gs-kpi-value">{cislo(blok.kwp, 0)} kWp</div>
            <div className="gs-kpi-sub">
              výroba {mwh(vybrana?.energie?.vyroba_rok1_mwh)} v prvním roce
              {blok.omezeno_max_kwp ? " · omezeno stropem" : ""}
            </div>
          </div>
          <div className="gs-kpi accent">
            <div className="gs-kpi-label">Cena PPA · {vybrana?.delka_kontraktu_roky} let</div>
            <div className="gs-kpi-value">{cislo(vybrana?.cena_ppa_kc_kwh, 3)} Kč/kWh</div>
            <div className="gs-kpi-sub">
              sleva {pct(vybrana?.sleva_zakaznikovi)} proti {kcMwh(vybrana?.cena_vyhnutelna_kc_mwh)}
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">Pokrytí spotřeby z FVE</div>
            <div className="gs-kpi-value">{pct(vybrana?.energie?.pokryti_spotreby_fve, 0)}</div>
            <div className="gs-kpi-sub">
              samospotřeba {pct(vybrana?.energie?.mira_samospotreby)} výroby
            </div>
          </div>
          <div className="gs-kpi">
            <div className="gs-kpi-label">Úspora zákazníka celkem</div>
            <div className="gs-kpi-value">{kc(vybrana?.uspora_kumulativni_kc)}</div>
            <div className="gs-kpi-sub">za {vybrana?.delka_kontraktu_roky} let kontraktu</div>
          </div>
        </div>

        {/* upozornění */}
        {(vysledek.upozorneni || []).length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, margin: "12px 0" }}>
            {vysledek.upozorneni.map((u, i) => (
              <div className="nb-warn" key={i}>
                <span>⚠️</span>
                <span dangerouslySetInnerHTML={{ __html: zvyrazni(u) }} />
              </div>
            ))}
          </div>
        )}

        <div className="gs-tabs gs-tabs-odsazeni" role="tablist" aria-label="Části výsledku">
          {ZALOZKY.map((z) => (
            <button
              key={z.klic}
              type="button"
              role="tab"
              aria-selected={zalozka === z.klic}
              onClick={() => setZalozka(z.klic)}
            >
              {z.label}
            </button>
          ))}
        </div>

        {/* --- Přehled: nabídka délek kontraktu --- */}
        {zalozka === "ekonomika" && (
          <>
            <div className="nb-scroll">
              <table className="nb-table">
                <thead>
                  <tr>
                    <th>Délka</th>
                    <th className="n">Cena PPA</th>
                    <th className="n">Sleva</th>
                    <th>Drží cenu</th>
                    <th className="n">DSCR</th>
                    <th className="n">IRR</th>
                    <th className="n">Splátka</th>
                    <th className="n">Úspora zákazníka</th>
                  </tr>
                </thead>
                <tbody>
                  {delky.map((x) => {
                    const jeVybrana = x.delka_kontraktu_roky === vybrana?.delka_kontraktu_roky;
                    return (
                      <tr
                        key={x.delka_kontraktu_roky}
                        onClick={() => setDelka(x.delka_kontraktu_roky)}
                        style={{
                          cursor: "pointer",
                          background: jeVybrana ? "var(--brand-wash)" : undefined,
                        }}
                        title="Klikni pro detail téhle délky"
                      >
                        <td>
                          <b>{x.delka_kontraktu_roky} let</b>
                        </td>
                        <td className="n">{cislo(x.cena_ppa_kc_kwh, 3)} Kč/kWh</td>
                        <td className="n">{pct(x.sleva_zakaznikovi)}</td>
                        <td>
                          <span className={x.cena_limituje === "dscr" ? "nb-badge" : "nb-badge pozor"}>
                            {x.cena_limituje === "dscr"
                              ? "banka"
                              : x.cena_limituje === "irr"
                                ? "investor"
                                : "nedosažitelné"}
                          </span>
                        </td>
                        <td className="n">{cislo(x.vysledek_investora?.dscr_min)}</td>
                        <td className="n">{pct(x.vysledek_investora?.irr, 2)}</td>
                        <td className="n">{kc(x.financovani?.splatka_mesicni_kc)}/měs</td>
                        <td className="n">{kc(x.uspora_kumulativni_kc)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Délku nedoporučujeme — vyber podle toho, co zákazník podepíše. Delší kontrakt =
              nižší splátka = nižší cena a větší sleva. „Drží cenu“ říká, která podmínka je ta
              těsná: u krátkého kontraktu banka (DSCR), u dlouhého investor (cílové IRR).
            </div>

            {vybrana && (
              <div className="gs-dva" style={{ marginTop: 14 }}>
                <div className="fm-card" style={{ padding: 14 }}>
                  <h4 style={{ margin: "0 0 8px" }}>Energie (rok 1)</h4>
                  <Radek l="Spotřeba zákazníka" v={mwh(vybrana.energie.spotreba_mwh)} />
                  <Radek l="Výroba FVE" v={mwh(vybrana.energie.vyroba_rok1_mwh)} />
                  <Radek l="Samospotřeba" v={mwh(vybrana.energie.samospotreba_mwh)} />
                  <Radek l="Přetok do sítě" v={mwh(vybrana.energie.export_mwh)} />
                  {vybrana.energie.orez_mwh > 0 && (
                    <Radek l="Ořez (nad rez. výkonem)" v={mwh(vybrana.energie.orez_mwh)} />
                  )}
                  <Radek l="Dokup ze sítě" v={mwh(vybrana.energie.dokup_mwh)} />
                </div>
                <div className="fm-card" style={{ padding: 14 }}>
                  <h4 style={{ margin: "0 0 8px" }}>Projekt a financování</h4>
                  <Radek l="Nákladová cena" v={kc(vybrana.financovani.nakladova_cena_kc)} />
                  <Radek l="CAPEX (prodej do SPV)" v={kc(vybrana.financovani.capex_kc)} />
                  <Radek l="Provize obchodníka" v={kc(vybrana.financovani.provize_kc)} />
                  <Radek l="Zisk Greensie hned" v={kc(vybrana.financovani.zisk_greensie_kc)} />
                  <Radek l="Vlastní kapitál" v={kc(vybrana.financovani.vlastni_kapital_kc)} />
                  <Radek l="Úvěr" v={kc(vybrana.financovani.uver_kc)} />
                  {vybrana.baterie && (
                    <Radek l="Nájem baterie" v={`${kc(vybrana.baterie.najem_kc_mesic)}/měs`} />
                  )}
                </div>
              </div>
            )}

            <div className="gs-pozn" style={{ marginTop: 10 }}>
              Počítáno s DSCR ≥ {cislo(vst.dscr_min)} a cílovým IRR {pct(vst.irr_cil, 1)}; cena za
              přetok {kcMwh(vst.cena_exportu_kc_mwh)}. Obojí se mění v Katalogu → nastavení PPA.
            </div>
          </>
        )}

        {/* --- Po letech --- */}
        {zalozka === "roky" && vybrana && (
          <>
            <div className="nb-scroll">
              <table className="nb-table">
                <thead>
                  <tr>
                    <th>Rok</th>
                    <th className="n">Výroba</th>
                    <th className="n">Samospotřeba</th>
                    <th className="n">Cena PPA</th>
                    <th className="n">Platba zákazníka</th>
                    <th className="n">Za přetok</th>
                    <th className="n">Zdroje</th>
                    <th className="n">Splátka</th>
                    <th className="n">DSCR</th>
                    <th className="n">Zisk po splátkách</th>
                  </tr>
                </thead>
                <tbody>
                  {vybrana.roky_investor.map((r) => (
                    <tr key={r.rok}>
                      <td>{r.rok}</td>
                      <td className="n">{mwh(r.vyroba_mwh)}</td>
                      <td className="n">{mwh(r.samospotreba_mwh)}</td>
                      <td className="n">{Math.round(r.cena_ppa_kc_mwh).toLocaleString("cs-CZ")}</td>
                      <td className="n">{kc(r.prodej_zakaznik_kc)}</td>
                      <td className="n">{kc(r.prodej_sdileni_kc)}</td>
                      <td className="n">{kc(r.zdroje_kc)}</td>
                      <td className="n">{kc(r.splatka_kc)}</td>
                      <td className="n">{cislo(r.dscr)}</td>
                      <td className="n">{kc(r.zisk_po_splatkach_kc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Ceny jsou Kč/MWh. „Zdroje“ = platby zákazníka + přetok + nájem baterie − provozní
              náklady; DSCR = zdroje ÷ splátka.
            </div>

            <h4 style={{ margin: "16px 0 8px" }}>Úspora zákazníka</h4>
            <div className="nb-scroll">
              <table className="nb-table">
                <thead>
                  <tr>
                    <th>Rok</th>
                    <th className="n">Vyhnutelná cena</th>
                    <th className="n">Cena PPA</th>
                    <th className="n">Samospotřeba</th>
                    <th className="n">Nájem baterie</th>
                    <th className="n">Úspora</th>
                    <th className="n">Kumulativně</th>
                  </tr>
                </thead>
                <tbody>
                  {vybrana.roky_klient.map((r) => (
                    <tr key={r.rok}>
                      <td>{r.rok}</td>
                      <td className="n">
                        {Math.round(r.cena_vyhnutelna_kc_mwh).toLocaleString("cs-CZ")}
                      </td>
                      <td className="n">{Math.round(r.cena_ppa_kc_mwh).toLocaleString("cs-CZ")}</td>
                      <td className="n">{mwh(r.samospotreba_mwh)}</td>
                      <td className="n">{r.najem_baterie_kc ? kc(r.najem_baterie_kc) : "—"}</td>
                      <td className="n">{kc(r.uspora_kc)}</td>
                      <td className="n">{kc(r.uspora_kumulativni_kc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* --- Odkupní tabulka --- */}
        {zalozka === "odkup" && vybrana && (
          <>
            <div className="nb-scroll">
              <table className="nb-table">
                <thead>
                  <tr>
                    <th>Rok</th>
                    <th className="n">Odkupní cena</th>
                    <th className="n">Zůstatek úvěru</th>
                    <th className="n">Poplatek za předčasné splacení</th>
                    <th className="n">Zisk SPV</th>
                  </tr>
                </thead>
                <tbody>
                  {vybrana.odkupni_tabulka.map((r) => (
                    <tr key={r.rok}>
                      <td>{r.rok}</td>
                      <td className="n">
                        <b>{kc(r.odkupni_cena_kc)}</b>
                      </td>
                      <td className="n">{kc(r.zustatek_uveru_kc)}</td>
                      <td className="n">{kc(r.poplatek_predcasne_splaceni_kc)}</td>
                      <td className="n">{kc(r.zisk_spv_kc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Za kolik si zákazník technologii odkoupí, když kontrakt ukončí dřív. Odkupní cena se
              odvozuje od zbývající hodnoty celé technologie, ne jen ze zůstatku úvěru.
            </div>
          </>
        )}

        {/* --- Graf --- */}
        {zalozka === "graf" && vybrana && (
          <>
            <div className="fm-card" style={{ padding: 14 }}>
              <GrafVyrobaSpotreba graf={vybrana.graf} />
            </div>
            <div className="gs-pozn">
              Levý sloupec každého měsíce je spotřeba (samospotřeba + dokup), pravý výroba
              (samospotřeba + přetok + ořez). V zimě výroba nepokryje ani základ, v létě přetéká.
            </div>
          </>
        )}

        {/* --- Nitkový průběh po 15 minutách --- */}
        {zalozka === "prubeh" && (
          <div className="fm-card" style={{ padding: 14 }}>
            {prubehNacita && <div className="gs-pozn">Načítám celoroční průběh…</div>}
            {prubehChyba && (
              <div className="nb-warn">
                <span>⚠️</span>
                <span>{prubehChyba}</span>
              </div>
            )}
            {prubeh && !prubehChyba && (
              <GrafPrubehuPpa
                data={prubeh}
                popis={
                  prubeh.baterie
                    ? "Zelená plocha je samospotřeba — energie, kterou zákazník z FVE odebere a zaplatí. Čárkovaně stav nabití baterie. Kolečkem přibliž, tažením posuň."
                    : "Zelená plocha je samospotřeba — energie, kterou zákazník z FVE odebere a zaplatí. Kde výroba přeleze spotřebu, teče přebytek do sítě. Kolečkem přibliž, tažením posuň."
                }
              />
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

// Řádek „popisek — hodnota“ v přehledových kartách.
function Radek({ l, v }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "3px 0",
        fontSize: 13,
      }}
    >
      <span style={{ color: "var(--ink-2)" }}>{l}</span>
      <b>{v}</b>
    </div>
  );
}

// Upozornění z backendu používají **tučně** pro klíčové části. Převedeme jen
// tenhle jeden vzor a zbytek escapujeme, ať se do stránky nedostane cizí HTML.
function zvyrazni(text) {
  const esc = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return esc.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
