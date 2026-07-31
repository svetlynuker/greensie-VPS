import { useEffect, useState } from "react";
import VlastniPoleVstupy from "./VlastniPoleVstupy";
import RozpisPolozek from "./RozpisPolozek";
import FakturacePanel from "./FakturacePanel";
import {
  crmObjednavkaDetail,
  crmObjednavkaPolozky,
  crmObjednavkaPrekloopZNabidky,
  crmObjednavkaPridejZKatalogu,
  crmObjednavkaSmaz,
  crmObjednavkaUlozPolozky,
  crmObjednavkaUprav,
  crmObjednavkaZaloz,
  crmProjektZaloz,
  crmSablony,
  crmUzivatele,
} from "../api";
import { fmtDatum } from "../crm";

/**
 * Detail / založení objednávky v okně.
 *
 * Tři věci se tu dějí na jednom místě, protože k sobě patří: údaje objednávky,
 * vlastní pole a **založení projektu**. Projekt totiž nesmí vzniknout
 * samostatně — objednávka je jeho jediná (spolu s případem) legální cesta na
 * svět, takže tlačítko patří sem.
 */
export default function ObjednavkaFormular({
  objednavkaId = null,
  pripad = null,
  nabidka = null,
  muzeMenitVlastnika = false,
  onZavri,
  onZmena,
  onProjekt,
}) {
  const jeUprava = Boolean(objednavkaId);
  const [o, setO] = useState(null);
  const [form, setForm] = useState({
    nazev: nabidka?.cislo ? `Podle nabídky ${nabidka.cislo}` : "",
    popis: "",
    cena_kc: "",
    datum_podpisu: "",
    datum_dodani: "",
    vlastnik_user_id: null,
    spoluvlastnici: [],
    extra: {},
  });
  const [vlastniPole, setVlastniPole] = useState([]);
  const [lidi, setLidi] = useState([]);
  const [sablony, setSablony] = useState([]);
  const [sablonaId, setSablonaId] = useState("");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    if (!objednavkaId) return;
    crmObjednavkaDetail(objednavkaId)
      .then((d) => {
        setO(d);
        setVlastniPole(d.vlastni_pole || []);
        setForm({
          nazev: d.nazev || "",
          popis: d.popis || "",
          cena_kc: d.cena_kc != null ? String(d.cena_kc) : "",
          datum_podpisu: (d.datum_podpisu || "").slice(0, 10),
          datum_dodani: (d.datum_dodani || "").slice(0, 10),
          vlastnik_user_id: d.vlastnik_user_id,
          spoluvlastnici: d.spoluvlastnici || [],
          extra: d.extra || {},
        });
      })
      .catch((e) => setChyba(e.message));
  }, [objednavkaId]);

  useEffect(() => {
    if (!muzeMenitVlastnika) return;
    crmUzivatele().then(setLidi).catch(() => setLidi([]));
  }, [muzeMenitVlastnika]);

  useEffect(() => {
    crmSablony().then(setSablony).catch(() => setSablony([]));
  }, []);

  function zmen(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      const data = {
        ...form,
        nazev: form.nazev.trim(),
        cena_kc: form.cena_kc.trim() === "" ? null : Number(form.cena_kc.replace(/\s/g, "").replace(",", ".")),
        datum_podpisu: form.datum_podpisu || null,
        datum_dodani: form.datum_dodani || null,
        obchodni_pripad_id: pripad?.id,
        nabidka_id: nabidka?.id,
      };
      const vysledek = jeUprava
        ? await crmObjednavkaUprav(objednavkaId, data)
        : await crmObjednavkaZaloz(data);
      setO(vysledek);
      await onZmena?.();
      if (!jeUprava) onZavri();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function zalozProjekt() {
    setChyba(null);
    try {
      const projekt = await crmProjektZaloz({
        objednavka_id: o.id,
        sablona_id: sablonaId ? Number(sablonaId) : null,
        nazev: o.nazev || "",
      });
      await onZmena?.();
      onProjekt?.(projekt.id);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz() {
    if (!window.confirm(`Smazat objednávku ${o.cislo}?`)) return;
    try {
      await crmObjednavkaSmaz(o.id);
      await onZmena?.();
      onZavri();
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? `Objednávka ${o?.cislo || ""}` : "Nová objednávka"}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          {!jeUprava && (
            <p className="crm-tise">
              Číslo (OBJ-RR-NNNN) přidělí appka.
              {nabidka?.cislo
                ? ` Objednávka vznikne z nabídky ${nabidka.cislo} a převezme z ní cenu, pokud ji umíme určit.`
                : ""}
            </p>
          )}

          {jeUprava && o && (
            <dl className="crm-udaje" style={{ marginBottom: 14 }}>
              <dt>Zákazník</dt>
              <dd>{o.zakaznik_nazev || "—"}</dd>
              <dt>Případ</dt>
              <dd>{o.pripad_cislo}</dd>
              <dt>Z nabídky</dt>
              <dd>{o.nabidka_cislo || "—"}</dd>
              <dt>Stav</dt>
              <dd>
                {o.stav_nazev}
                {o.duvod_zruseni ? ` · důvod: ${o.duvod_zruseni}` : ""}
              </dd>
            </dl>
          )}

          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Název</label>
              <input
                className="crm-pole"
                value={form.nazev}
                onChange={(e) => zmen("nazev", e.target.value)}
                placeholder="např. Baterie 100 kWh včetně montáže"
              />
            </div>
            <div>
              <label className="crm-label">
                Cena bez DPH (Kč)
                {o?.soucet_polozek_kc != null && (
                  <span className="crm-tise" style={{ fontWeight: 400 }}>
                    {" "}· rozpis: {Math.round(o.soucet_polozek_kc).toLocaleString("cs-CZ")}
                  </span>
                )}
              </label>
              <input
                className="crm-pole"
                value={form.cena_kc}
                onChange={(e) => zmen("cena_kc", e.target.value)}
                inputMode="decimal"
              />
              {/* Cena jde ze součtu rozpisu, dokud ji někdo nepřepíše ručně.
                  Pak má přednost ruční hodnota a appka jen ukáže rozdíl. */}
              {o?.cena_rucni && o?.soucet_polozek_kc != null && (
                <p className="crm-tise" style={{ margin: "4px 0 0" }}>
                  Cena je zadaná ručně
                  {Math.abs((o.cena_kc || 0) - o.soucet_polozek_kc) > 0.5
                    ? ` (o ${Math.round(
                        (o.cena_kc || 0) - o.soucet_polozek_kc
                      ).toLocaleString("cs-CZ")} Kč jinak než součet rozpisu)`
                    : ""}
                  .{" "}
                  <button
                    type="button"
                    className="fm-btn crm-btn-maly"
                    onClick={() => {
                      zmen("cena_kc", String(o.soucet_polozek_kc));
                      setForm((f) => ({ ...f, cena_rucni: false }));
                    }}
                  >
                    Vrátit na součet rozpisu
                  </button>
                </p>
              )}
            </div>
            <div>
              <label className="crm-label">Datum podpisu</label>
              <input
                className="crm-pole"
                type="date"
                value={form.datum_podpisu}
                onChange={(e) => zmen("datum_podpisu", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Datum dodání</label>
              <input
                className="crm-pole"
                type="date"
                value={form.datum_dodani}
                onChange={(e) => zmen("datum_dodani", e.target.value)}
              />
            </div>
            {muzeMenitVlastnika && (
              <div>
                <label className="crm-label">Vlastník</label>
                <select
                  className="crm-pole"
                  value={form.vlastnik_user_id || ""}
                  onChange={(e) =>
                    zmen("vlastnik_user_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">— já —</option>
                  {lidi.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.jmeno}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="crm-sirka3">
              <label className="crm-label">Popis</label>
              <textarea
                className="crm-pole"
                rows={3}
                value={form.popis}
                onChange={(e) => zmen("popis", e.target.value)}
              />
            </div>

            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={form.extra}
              onZmena={(extra) => zmen("extra", extra)}
            />
          </div>

          {/* Rozpis položek (CRM-08) a fakturace (CRM-09). Obojí dává smysl až
              u existující objednávky – nová se nejdřív musí založit, aby měla id. */}
          {jeUprava && o && (
            <div className="crm-oddelovac" style={{ marginTop: 16, paddingTop: 14 }}>
              <RozpisPolozek
                nadpis="Rozpis položek objednávky"
                nacti={() => crmObjednavkaPolozky(o.id)}
                uloz={(polozky) => crmObjednavkaUlozPolozky(o.id, polozky)}
                pridejZKatalogu={(ids) => crmObjednavkaPridejZKatalogu(o.id, ids)}
                prekloopZNabidky={o.nabidka_id ? () => crmObjednavkaPrekloopZNabidky(o.id) : null}
                onZmena={onZmena}
              />
            </div>
          )}

          {jeUprava && o && <FakturacePanel objednavkaId={o.id} onZmena={onZmena} />}

          {/* Projekt vzniká z objednávky – proto je tlačítko tady. */}
          {jeUprava && o && (
            <div className="crm-oddelovac" style={{ marginTop: 16, paddingTop: 14 }}>
              <h3>Realizace</h3>
              {o.projekt_id ? (
                <p className="crm-tise">
                  Projekt <b>{o.projekt_cislo}</b> už z této objednávky vznikl.{" "}
                  <button className="fm-btn crm-btn-maly" onClick={() => onProjekt?.(o.projekt_id)}>
                    Otevřít projekt
                  </button>
                </p>
              ) : (
                <>
                  <p className="crm-tise">
                    Z objednávky se zakládá projekt. Vyber šablonu kroků a appka rozbalí
                    úkoly s termíny podle návazností — nebo nech prázdné a kroky si přidáš sám.
                  </p>
                  <div className="crm-stav-novy">
                    <select
                      className="crm-pole"
                      value={sablonaId}
                      onChange={(e) => setSablonaId(e.target.value)}
                    >
                      <option value="">— bez šablony —</option>
                      {sablony.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.nazev} ({s.kroky.length} kroků)
                        </option>
                      ))}
                    </select>
                    <button className="fm-btn fm-primary" onClick={zalozProjekt}>
                      Založit projekt
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          {jeUprava && o && (
            <button className="fm-btn crm-btn-smazat" onClick={smaz}>
              Smazat
            </button>
          )}
          <span className="crm-mezera" />
          <button className="fm-btn" onClick={onZavri}>
            Zavřít
          </button>
          <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
            {uklada ? "Ukládám…" : jeUprava ? "Uložit změny" : "Založit objednávku"}
          </button>
        </div>
      </div>
    </div>
  );
}
