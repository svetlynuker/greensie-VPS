import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import VlastniPoleVstupy from "./VlastniPoleVstupy";
import RozpisPolozek from "./RozpisPolozek";
import FakturacePanel from "./FakturacePanel";
import Pritomni from "./Pritomni";
import StavUlozeni from "./StavUlozeni";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";
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

// Základní údaje objednávky – jen ty se ukládají samy. `stav`, `duvod_zruseni`
// ani vlastnictví tu nejsou: backend je přes ukládání po polích odmítá (422),
// protože mají vedlejší efekty (automatizace, notifikace, povinná pole).
const POLE_UDAJE = ["nazev", "cena_kc", "datum_podpisu", "datum_dodani", "popis"];

const NAZVY_POLI = {
  nazev: "Název",
  cena_kc: "Cena bez DPH",
  datum_podpisu: "Datum podpisu",
  datum_dodani: "Datum dodání",
  popis: "Popis",
};

/**
 * Detail / založení objednávky v okně.
 *
 * Tři věci se tu dějí na jednom místě, protože k sobě patří: údaje objednávky,
 * vlastní pole a **založení projektu**. Projekt totiž nesmí vzniknout
 * samostatně — objednávka je jeho jediná (spolu s případem) legální cesta na
 * svět, takže tlačítko patří sem.
 *
 * Okno slouží dvěma režimům a ukládá v každém jinak:
 *
 *  - **editace** (přišlo `objednavkaId`): blok základních údajů se ukládá sám,
 *    pole po poli (`useZaznamAutosave`). Dva lidé nad jednou objednávkou si tak
 *    navzájem nepřepíšou pole, kterých se ani nedotkli.
 *  - **zakládání** (bez `objednavkaId`): autosave NEBĚŽÍ. Není co ukládat po
 *    polích, dokud záznam neexistuje — PATCH by neměl kam jít. Formulář proto
 *    drží hodnoty ve svém stavu a odešle je jedním „Založit objednávku“.
 *
 * Ostatní bloky (rozpis položek, fakturace, změna stavu, založení projektu)
 * zůstávají na vědomém potvrzení: každý z nich něco přepočítá nebo vygeneruje
 * další záznamy, což se nesmí spustit uprostřed psaní.
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

  /** Natažení detailu. Používá se stejně pro první otevření i pro obnovu. */
  const nactiDetail = useCallback(() => {
    if (!objednavkaId) return Promise.resolve(null);
    return crmObjednavkaDetail(objednavkaId).then((d) => {
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
      return d;
    });
  }, [objednavkaId]);

  useEffect(() => {
    nactiDetail().catch((e) => setChyba(e.message));
  }, [nactiDetail]);

  // Klíče, které autosave spravuje: základní údaje + vlastní pole (`extra:<klic>`).
  // Vlastní pole nejdou vypsat dopředu, definuje je admin v CRM.
  const poleAutosave = useMemo(
    () => [...POLE_UDAJE, ...(vlastniPole || []).map((p) => `extra:${p.klic}`)],
    [vlastniPole],
  );

  const {
    hodnoty,
    zmen: zmenPolem,
    stav,
    chyba: chybaUlozeni,
    kdy,
    pritomni,
    razitko,
    kolize,
    prepis,
    vezmiJejich,
    dokonci,
    onFokus,
    onBlur,
  } = useZaznamAutosave({
    entita: "obj",
    id: objednavkaId,
    zaznam: o,
    pole: poleAutosave,
    entitaTyp: "crm_obj",
    // TOHLE je ten rozdíl mezi zakládáním a editací: bez `objednavkaId` záznam
    // v databázi neexistuje, takže se nesmí poslat ani jeden PATCH. Hodnoty si
    // v tom případě drží formulář sám a odejdou naráz při založení.
    zapnuto: jeUprava && Boolean(o),
  });

  // Razítko se změnilo → objednávku upravil někdo jiný (nebo já z jiného okna),
  // případně se přepočítal součet rozpisu. Natáhneme ji znovu; rozepsané pole
  // hook nepřepíše, takže to nic nesebere. První razítko se jen zapamatuje,
  // jinak by se okno po otevření obnovilo zbytečně.
  const razitkoRef = useRef(null);
  useEffect(() => {
    if (!razitko) return;
    if (razitkoRef.current === null || razitkoRef.current === razitko) {
      razitkoRef.current = razitko;
      return;
    }
    razitkoRef.current = razitko;
    nactiDetail().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [razitko]);

  // Po každém vlastním uložení natáhneme detail hned, nečekáme na razítko:
  // uložená cena přehodí příznak „zadaná ručně“ a ten se ukazuje pod polem.
  const kdyRef = useRef(null);
  useEffect(() => {
    if (!kdy || kdyRef.current === kdy) return;
    kdyRef.current = kdy;
    nactiDetail().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kdy]);

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

  /** Hodnota pole údajů: v editaci ji drží autosave, při zakládání formulář. */
  function udaj(klic) {
    return (jeUprava ? hodnoty[klic] : form[klic]) ?? "";
  }

  /**
   * Zápis do pole údajů. `ihned` = hotové rozhodnutí (datum, výběr), u kterého
   * nemá smysl čekat na dopsání.
   */
  function zmenUdaj(klic, hodnota, ihned = false) {
    if (jeUprava) zmenPolem(klic, hodnota, ihned);
    else zmen(klic, hodnota);
  }

  /**
   * Fokus a odchod z pole — jen v editaci. Fokus říká kolegům, na čem člověk
   * právě je, odchod doručí i posledních pár znaků, které ještě čekají.
   */
  function fokusPole(klic) {
    if (!jeUprava) return {};
    return { onFocus: () => onFokus(klic), onBlur: () => onBlur(klic) };
  }

  // Vlastní pole: v editaci se hodnoty berou z autosave (klíče `extra:<klic>`),
  // při zakládání z formuláře. Výpočtová pole se jen zrcadlí — jejich vstup se
  // nedá psát, takže se přes autosave nikdy neodešlou.
  const extraHodnoty = useMemo(() => {
    if (!jeUprava) return form.extra;
    const vysledek = {};
    (vlastniPole || []).forEach((p) => {
      vysledek[p.klic] = hodnoty[`extra:${p.klic}`] ?? "";
    });
    return vysledek;
  }, [jeUprava, form.extra, vlastniPole, hodnoty]);

  /** Založení nové objednávky — jedním požadavkem, protože id ještě není. */
  async function zaloz() {
    setUklada(true);
    setChyba(null);
    try {
      await crmObjednavkaZaloz({
        ...form,
        nazev: form.nazev.trim(),
        cena_kc: form.cena_kc.trim() === "" ? null : Number(form.cena_kc.replace(/\s/g, "").replace(",", ".")),
        datum_podpisu: form.datum_podpisu || null,
        datum_dodani: form.datum_dodani || null,
        obchodni_pripad_id: pripad?.id,
        nabidka_id: nabidka?.id,
      });
      await onZmena?.();
      onZavri();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /**
   * Vědomá akce, která musí jít starou cestou (PUT celého záznamu) — vlastnictví
   * a příznak ruční ceny přes ukládání po polích nejdou.
   *
   * Nejdřív se doženou rozepsané změny a vezmou čerstvá data ze serveru, jinak
   * by PUT vrátil do databáze text, který mezitím někdo přepsal.
   */
  async function ulozPresPut(zmeny) {
    setUklada(true);
    setChyba(null);
    try {
      await dokonci();
      const cerstva = await crmObjednavkaDetail(objednavkaId);
      await crmObjednavkaUprav(objednavkaId, {
        nazev: cerstva.nazev || "",
        popis: cerstva.popis || "",
        cena_kc: cerstva.cena_kc,
        cena_rucni: cerstva.cena_rucni,
        datum_podpisu: cerstva.datum_podpisu || null,
        datum_dodani: cerstva.datum_dodani || null,
        vlastnik_user_id: cerstva.vlastnik_user_id,
        spoluvlastnici: cerstva.spoluvlastnici || [],
        extra: cerstva.extra || {},
        ...zmeny,
      });
      await nactiDetail();
      await onZmena?.();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /** Čitelný název pole – i pro vlastní pole (klíč `extra:<klic>`). */
  function nazevPole(klic) {
    if (klic.startsWith("extra:")) {
      const k = klic.slice(6);
      return (vlastniPole || []).find((p) => p.klic === k)?.nazev || k;
    }
    return NAZVY_POLI[klic] || klic;
  }

  /** Konec práce s oknem: dožene neodeslané změny, ať se text neztratí. */
  async function hotovo() {
    if (jeUprava) {
      await dokonci();
      await onZmena?.();
    }
    onZavri();
  }

  async function zalozProjekt() {
    setChyba(null);
    try {
      // Nejdřív dopsat čekající změny. Bez toho by projekt mohl vzniknout
      // s o jednu úpravu starším názvem: kliknutí na tlačítko sice vyvolá
      // `blur` a s ním uložení, ale POST by ho mohl předběhnout.
      await dokonci();
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
    // Zavření okna jde přes `hotovo` – kliknutí mimo okno je taky odchod a
    // posledních pár znaků musí ještě odejít na server.
    <div className="crm-okno-plast" onClick={hotovo}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? `Objednávka ${o?.cislo || ""}` : "Nová objednávka"}</h2>
          <span className="crm-mezera" />
          {jeUprava && (
            <>
              {/* Kdo má objednávku otevřenou taky – ať je kolize vidět dřív, než
                  nastane. Vedle je stav ukládání: bez tlačítka „Uložit“ nemá
                  člověk jinak jak poznat, že text došel na server. */}
              <Pritomni pritomni={pritomni} popisekPole={nazevPole} />
              <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
            </>
          )}
          <button className="crm-zavrit" onClick={hotovo} aria-label="Zavřít">
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
                value={udaj("nazev")}
                onChange={(e) => zmenUdaj("nazev", e.target.value)}
                placeholder="např. Baterie 100 kWh včetně montáže"
                {...fokusPole("nazev")}
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
                value={udaj("cena_kc")}
                onChange={(e) => zmenUdaj("cena_kc", e.target.value)}
                inputMode="decimal"
                {...fokusPole("cena_kc")}
              />
              {/* Cena jde ze součtu rozpisu, dokud ji někdo nepřepíše ručně.
                  Pak má přednost ruční hodnota a appka jen ukáže rozdíl.
                  Uložení ceny přes autosave si příznak „zadaná ručně“ nastaví
                  samo, zpátky na součet ho ale dostane jen tohle tlačítko —
                  příznak sám se po polích měnit nedá (a nemá: je to rozhodnutí,
                  ne rozepsaná věta). */}
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
                    disabled={uklada}
                    onClick={() =>
                      ulozPresPut({ cena_kc: o.soucet_polozek_kc, cena_rucni: false })
                    }
                  >
                    Vrátit na součet rozpisu
                  </button>
                </p>
              )}
            </div>
            <div>
              <label className="crm-label">Datum podpisu</label>
              {/* Datum je hotové rozhodnutí, ne rozepsaná věta – jde na server
                  bez prodlevy (`ihned`). */}
              <input
                className="crm-pole"
                type="date"
                value={udaj("datum_podpisu")}
                onChange={(e) => zmenUdaj("datum_podpisu", e.target.value, true)}
                {...fokusPole("datum_podpisu")}
              />
            </div>
            <div>
              <label className="crm-label">Datum dodání</label>
              <input
                className="crm-pole"
                type="date"
                value={udaj("datum_dodani")}
                onChange={(e) => zmenUdaj("datum_dodani", e.target.value, true)}
                {...fokusPole("datum_dodani")}
              />
            </div>
            {muzeMenitVlastnika && (
              <div>
                <label className="crm-label">Vlastník</label>
                {/* Vlastnictví se přes ukládání po polích měnit nedá (backend ho
                    odmítá): mění, kdo záznam vidí, a rozesílá notifikaci. V
                    editaci proto jde starou cestou — celým PUTem nad čerstvými
                    daty, hned po výběru. */}
                <select
                  className="crm-pole"
                  value={form.vlastnik_user_id || ""}
                  disabled={uklada}
                  onChange={(e) => {
                    const novy = e.target.value ? Number(e.target.value) : null;
                    zmen("vlastnik_user_id", novy);
                    if (jeUprava) ulozPresPut({ vlastnik_user_id: novy });
                  }}
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
                value={udaj("popis")}
                onChange={(e) => zmenUdaj("popis", e.target.value)}
                {...fokusPole("popis")}
              />
            </div>

            {/* Vlastní pole: v editaci se hlásí po jednom (`onZmenaPole`), při
                zakládání celé `extra` naráz. Ukládat celé `extra` po každém
                znaku by přepisovalo i pole, kterých se člověk nedotkl. */}
            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={extraHodnoty}
              onZmena={jeUprava ? undefined : (extra) => zmen("extra", extra)}
              onZmenaPole={
                jeUprava
                  ? (klic, hodnota, ihned) => zmenPolem(`extra:${klic}`, hodnota, ihned)
                  : undefined
              }
            />
          </div>

          {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. */}
          {kolize && (
            <div className="crm-kolize">
              <div>
                <strong>{nazevPole(kolize.pole)}</strong> mezitím změnil
                {kolize.kdo ? ` ${kolize.kdo}` : " někdo jiný"} na{" "}
                <strong>{kolize.aktualni || "prázdné"}</strong>.
                <br />
                Ty píšeš <strong>{kolize.moje || "prázdné"}</strong>.
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="fm-btn fm-primary" onClick={prepis}>
                  Přepsat mojí hodnotou
                </button>
                <button className="fm-btn" onClick={vezmiJejich}>
                  Nechat jejich
                </button>
              </div>
            </div>
          )}

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
          {jeUprava && (
            <span className="crm-tise">
              Údaje se ukládají samy, tlačítko jen zavře okno.
            </span>
          )}
          <span className="crm-mezera" />
          {jeUprava ? (
            <>
              <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
              <button className="fm-btn fm-primary" onClick={hotovo}>
                Hotovo
              </button>
            </>
          ) : (
            <>
              <button className="fm-btn" onClick={onZavri}>
                Zavřít
              </button>
              <button className="fm-btn fm-primary" onClick={zaloz} disabled={uklada}>
                {uklada ? "Ukládám…" : "Založit objednávku"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
