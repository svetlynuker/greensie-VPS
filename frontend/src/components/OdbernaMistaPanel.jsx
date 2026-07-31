import { useCallback, useEffect, useState } from "react";
import {
  crmOdbernaMista,
  crmOdberneMistoPridej,
  crmOdberneMistoSmaz,
  crmOdberneMistoUprav,
  crmPripadOdberneMisto,
} from "../api";
import VlastniPoleNastaveni from "./VlastniPoleNastaveni";
import VlastniPoleVstupy from "./VlastniPoleVstupy";

/**
 * Odběrná místa zákazníka — jedno pole na dvou obrazovkách (CRM-46).
 *
 * Stejná komponenta jede na kartě klienta i na kartě obchodního případu; liší se
 * jen `entita`. Místa VŽDY patří zákazníkovi, takže co OZ založí u případu, vidí
 * i na kartě firmy a použijí to i další případy téže firmy. To je celý smysl:
 * 15minutový diagram odběru se stahuje z portálu distributora jednou, ne ke
 * každé nabídce znovu.
 *
 * Na kartě případu je navíc vazba „tohoto místa se případ týká" — z ní si pak
 * nabídka vezme diagram i distribuční parametry (etapa 3).
 *
 * Proč tu jsou distributor, hladina a rezervovaná kapacita: přesně tyhle tři
 * hodnoty OZ dosud vypisoval ručně do každého peak shaving výpočtu, a jsou to
 * vlastnosti MÍSTA, ne nabídky. GPS je vlastní schválně — FVE se staví na
 * provozovně, kdežto adresa firmy bývá fakturační.
 */

const DISTRIB = [
  { klic: "", nazev: "— nevím —" },
  { klic: "cez", nazev: "ČEZ Distribuce" },
  { klic: "egd", nazev: "EG.D" },
  { klic: "pre", nazev: "PRE distribuce" },
];
const HLADINY = [
  { klic: "", nazev: "— nevím —" },
  { klic: "vn", nazev: "VN" },
  { klic: "vvn", nazev: "VVN" },
];

const PRAZDNY = {
  nazev: "",
  ean: "",
  adresa_ulice: "",
  adresa_mesto: "",
  adresa_psc: "",
  gps_lat: "",
  gps_lng: "",
  distributor: "",
  napetova_hladina: "",
  rezervovana_kapacita_kw: "",
  rezervovany_prikon_kw: "",
  poznamka: "",
  aktivni: true,
  extra: {},
};

/** Prázdné pole → null, ať se z „nevyplněno" nestane nula. */
function cislo(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(String(v).replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function text(v) {
  return v === null || v === undefined ? "" : String(v);
}

function nazevDistrib(klic) {
  return DISTRIB.find((d) => d.klic === klic)?.nazev || klic;
}

/** Souhrn místa na jeden řádek — co je vyplněné, to se ukáže. */
function popisMista(m) {
  const casti = [];
  if (m.adresa_text) casti.push(m.adresa_text);
  if (m.ean) casti.push(`EAN ${m.ean}`);
  if (m.distributor) {
    casti.push(
      [nazevDistrib(m.distributor), (m.napetova_hladina || "").toUpperCase()]
        .filter(Boolean)
        .join(" ")
    );
  }
  if (m.rezervovana_kapacita_kw != null) {
    casti.push(`rezervovaná kapacita ${m.rezervovana_kapacita_kw.toLocaleString("cs-CZ")} kW`);
  }
  return casti.join(" · ") || "Zatím jen název — doplň EAN a distributora, ať jde počítat.";
}

export default function OdbernaMistaPanel({ entita, zaznamId, onZmenaVazby, muzeSpravovatPole }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState(PRAZDNY);
  const [otevreny, setOtevreny] = useState(false);
  const [upravovany, setUpravovany] = useState(null); // id nebo null
  const [uklada, setUklada] = useState(false);
  const [spravaPoli, setSpravaPoli] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async () => {
    try {
      setData(await crmOdbernaMista(entita, zaznamId));
      setChyba(null);
    } catch (e) {
      setChyba(e.message);
    }
  }, [entita, zaznamId]);

  useEffect(() => {
    nacti();
  }, [nacti]);

  function zmen(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  function zavri() {
    setOtevreny(false);
    setUpravovany(null);
    setForm(PRAZDNY);
    setChyba(null);
  }

  function zacniUpravu(m) {
    setUpravovany(m.id);
    setOtevreny(true);
    setForm({
      nazev: m.nazev || "",
      ean: m.ean || "",
      adresa_ulice: m.adresa_ulice || "",
      adresa_mesto: m.adresa_mesto || "",
      adresa_psc: m.adresa_psc || "",
      gps_lat: text(m.gps_lat),
      gps_lng: text(m.gps_lng),
      distributor: m.distributor || "",
      napetova_hladina: m.napetova_hladina || "",
      rezervovana_kapacita_kw: text(m.rezervovana_kapacita_kw),
      rezervovany_prikon_kw: text(m.rezervovany_prikon_kw),
      poznamka: m.poznamka || "",
      aktivni: m.aktivni !== false,
      extra: m.extra || {},
    });
  }

  async function uloz() {
    if (!form.nazev.trim()) return;
    setUklada(true);
    setChyba(null);
    const telo = {
      ...form,
      nazev: form.nazev.trim(),
      gps_lat: cislo(form.gps_lat),
      gps_lng: cislo(form.gps_lng),
      rezervovana_kapacita_kw: cislo(form.rezervovana_kapacita_kw),
      rezervovany_prikon_kw: cislo(form.rezervovany_prikon_kw),
    };
    try {
      if (upravovany) await crmOdberneMistoUprav(upravovany, telo);
      else await crmOdberneMistoPridej(entita, zaznamId, telo);
      await nacti();
      // Založení z karty případu si místo rovnou přiřadí (když případ žádné
      // nemá) — karta o tom musí vědět, jinak by ukazovala prázdný popisek.
      if (!upravovany && entita === "op" && onZmenaVazby) onZmenaVazby();
      zavri();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /** Mazání na dvě fáze: backend nejdřív řekne, co by se ztratilo. */
  async function smaz(m) {
    setChyba(null);
    try {
      const nahled = await crmOdberneMistoSmaz(m.id, false);
      if (!window.confirm(`${nahled.co_se_stane}\n\nSmazat?`)) return;
      await crmOdberneMistoSmaz(m.id, true);
      await nacti();
      if (entita === "op" && onZmenaVazby) onZmenaVazby();
    } catch (e) {
      setChyba(e.message);
    }
  }

  /** Vazba případu na místo (jen na kartě případu). */
  async function prepniVazbu(m) {
    setChyba(null);
    try {
      const je = data?.vybrane_id === m.id;
      setData(await crmPripadOdberneMisto(zaznamId, je ? null : m.id));
      if (onZmenaVazby) onZmenaVazby();
    } catch (e) {
      setChyba(e.message);
    }
  }

  const mista = data?.mista || [];
  const muze = data?.muze_editovat !== false;

  return (
    <div className="fm-card crm-blok">
      <div className="crm-karta-radek">
        <h3 style={{ margin: 0 }}>Odběrná místa</h3>
        <span className="crm-mezera" />
        {muzeSpravovatPole && (
          <button
            className="fm-btn crm-btn-maly"
            onClick={() => setSpravaPoli(true)}
            title="Přidat vlastní pole na odběrná místa (bez zásahu do databáze)"
          >
            Doplňující pole
          </button>
        )}
        {muze && !otevreny && (
          <button className="fm-btn crm-btn-maly fm-primary" onClick={() => setOtevreny(true)}>
            + Přidat místo
          </button>
        )}
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}
      {data === null && !chyba && <p className="crm-tise">Načítám…</p>}

      {data !== null && mista.length === 0 && !otevreny && (
        <p className="crm-tise">
          Zákazník nemá žádné odběrné místo. Zaloz ho podle faktury — z místa se pak předvyplní
          distributor, hladina i rezervovaná kapacita a nahrají se k němu 15minutové diagramy
          odběru.
        </p>
      )}

      {mista.length > 0 && (
        <ul className="crm-om-seznam">
          {mista.map((m) => (
            <li key={m.id} className={m.vybrane_pro_pripad ? "vybrane" : undefined}>
              <div style={{ minWidth: 0 }}>
                <div className="crm-om-nazev">
                  {m.nazev}
                  {m.vybrane_pro_pripad && (
                    <span className="crm-znacka crm-barva-ok">tohoto se případ týká</span>
                  )}
                  {!m.aktivni && <span className="crm-znacka crm-barva-warn">neaktivní</span>}
                  {m.diagramu > 0 ? (
                    <span className="crm-znacka crm-barva-info">
                      {m.diagramu} {m.diagramu === 1 ? "diagram" : m.diagramu < 5 ? "diagramy" : "diagramů"}
                    </span>
                  ) : (
                    <span className="crm-znacka">bez diagramu</span>
                  )}
                </div>
                <div className="crm-tise">{popisMista(m)}</div>
                {m.poznamka && <div className="crm-tise">{m.poznamka}</div>}
              </div>
              <span className="crm-mezera" />
              {entita === "op" && muze && (
                <button
                  className="fm-btn crm-btn-maly"
                  onClick={() => prepniVazbu(m)}
                  title={
                    m.vybrane_pro_pripad
                      ? "Zrušit vazbu případu na tohle místo"
                      : "Případ se týká tohoto místa"
                  }
                >
                  {m.vybrane_pro_pripad ? "Odpojit" : "Vybrat pro případ"}
                </button>
              )}
              {muze && (
                <>
                  <button className="fm-btn crm-btn-maly" onClick={() => zacniUpravu(m)}>
                    Upravit
                  </button>
                  <button
                    className="fm-btn crm-btn-maly crm-btn-smazat"
                    onClick={() => smaz(m)}
                    title="Smazat místo"
                  >
                    ✕
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {otevreny && (
        <div className="crm-kontakt-form">
          <div className="crm-mrizka">
            <div>
              <label className="crm-label">Název místa *</label>
              <input
                className="crm-pole"
                value={form.nazev}
                onChange={(e) => zmen("nazev", e.target.value)}
                placeholder="Hala Kolín, Sídlo – Praha 9…"
              />
            </div>
            <div>
              <label className="crm-label">EAN odběrného místa</label>
              <input
                className="crm-pole"
                value={form.ean}
                onChange={(e) => zmen("ean", e.target.value)}
                placeholder="859182400100123456"
                title="18 číslic z faktury nebo portálu distributora; mezery můžeš nechat"
              />
            </div>
            <div>
              <label className="crm-label">Ulice a číslo</label>
              <input
                className="crm-pole"
                value={form.adresa_ulice}
                onChange={(e) => zmen("adresa_ulice", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">PSČ</label>
              <input
                className="crm-pole"
                value={form.adresa_psc}
                onChange={(e) => zmen("adresa_psc", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Město</label>
              <input
                className="crm-pole"
                value={form.adresa_mesto}
                onChange={(e) => zmen("adresa_mesto", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Distributor</label>
              <select
                className="crm-pole"
                value={form.distributor}
                onChange={(e) => zmen("distributor", e.target.value)}
              >
                {DISTRIB.map((d) => (
                  <option key={d.klic} value={d.klic}>
                    {d.nazev}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="crm-label">Napěťová hladina</label>
              <select
                className="crm-pole"
                value={form.napetova_hladina}
                onChange={(e) => zmen("napetova_hladina", e.target.value)}
              >
                {HLADINY.map((h) => (
                  <option key={h.klic} value={h.klic}>
                    {h.nazev}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="crm-label">Rezervovaná kapacita (kW)</label>
              <input
                className="crm-pole crm-pole-cislo"
                value={form.rezervovana_kapacita_kw}
                onChange={(e) => zmen("rezervovana_kapacita_kw", e.target.value)}
                placeholder="z faktury za distribuci"
              />
            </div>
            <div>
              <label className="crm-label">Rezervovaný příkon (kW)</label>
              <input
                className="crm-pole crm-pole-cislo"
                value={form.rezervovany_prikon_kw}
                onChange={(e) => zmen("rezervovany_prikon_kw", e.target.value)}
                placeholder="ze smlouvy o připojení"
              />
            </div>
            <div>
              <label className="crm-label">GPS – šířka</label>
              <input
                className="crm-pole crm-pole-cislo"
                value={form.gps_lat}
                onChange={(e) => zmen("gps_lat", e.target.value)}
                placeholder="50.0271"
                title="Poloha provozovny (ne fakturační adresy) — počítá se z ní výroba FVE"
              />
            </div>
            <div>
              <label className="crm-label">GPS – délka</label>
              <input
                className="crm-pole crm-pole-cislo"
                value={form.gps_lng}
                onChange={(e) => zmen("gps_lng", e.target.value)}
                placeholder="15.2005"
              />
            </div>
            <div className="crm-sirka3">
              <label className="crm-label">Poznámka</label>
              <textarea
                className="crm-pole"
                rows={2}
                value={form.poznamka}
                onChange={(e) => zmen("poznamka", e.target.value)}
              />
            </div>

            <VlastniPoleVstupy
              pole={data?.vlastni_pole}
              hodnoty={form.extra}
              onZmena={(h) => zmen("extra", h)}
            />
          </div>

          <label className="crm-zaskrtavaci">
            <input
              type="checkbox"
              checked={form.aktivni}
              onChange={(e) => zmen("aktivni", e.target.checked)}
            />
            Aktivní místo (neaktivní se nenabízí k novým nabídkám, ale diagramy zůstanou)
          </label>

          <div className="crm-blok-pata">
            <button className="fm-btn" onClick={zavri} disabled={uklada}>
              Zrušit
            </button>
            <span className="crm-mezera" />
            <button
              className="fm-btn fm-primary"
              onClick={uloz}
              disabled={uklada || !form.nazev.trim()}
            >
              {uklada ? "Ukládám…" : upravovany ? "Uložit místo" : "Přidat místo"}
            </button>
          </div>
        </div>
      )}

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="om"
          nazevObrazovky="Odběrná místa"
          onZavri={() => setSpravaPoli(false)}
          onZmena={nacti}
        />
      )}
    </div>
  );
}
