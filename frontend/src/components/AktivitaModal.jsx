import { useEffect, useMemo, useState } from "react";
import Ikona from "./Ikona";
import {
  crmAktivitaUprav,
  crmKategorieAktivit,
  crmNabidky,
  crmNastaveni,
  crmPripady,
  crmUdalostPridej,
  crmUzivatele,
  crmZakaznici,
} from "../api";
import { DRUHY_AKTIVITY, FREKVENCE_OPAKOVANI, PRIORITY_AKTIVITY } from "../crm";
import { isoDen, posunDnu } from "../datum";
import { MIN_DELKA, hm, minutyZCasu, naCas } from "../kalendarCas";
import "../styles/aktivitaModal.css";

/**
 * Modál pro založení a úpravu aktivity — podle předlohy `nová událost.png`.
 *
 * Vlevo je náhled dne, do kterého se aktivita zakládá, aby bylo vidět, jestli
 * se nepere s něčím jiným. Bez toho člověk plánuje naslepo a schůzky se mu
 * srazí; kalendář za modálem není vidět.
 *
 * Formulář nemá „Uložit" zakázané dokud není vše vyplněné. Povinné je jen
 * datum a název — u telefonátu, který se má vyřídit za deset minut, nemá cenu
 * nutit lidi vyplňovat místo a kategorii.
 *
 * ---- „Čeho se to týká" -----------------------------------------------------
 * Aktivita může viset na zákazníkovi, případu, nabídce, objednávce nebo
 * projektu — ale taky na ničem, když je soukromá. Vazba je nepovinná schválně:
 * „zavolat na úřad" je legitimní úkol bez klienta.
 *
 * Zaškrtnutí „soukromá" vazbu odebere a schová celou sekci: soukromá aktivita
 * se nesmí objevit u klienta, protože její obsah nevidí ani vedení.
 */

// Trvání v nabídce. Delší schůzky se zadají přes „vlastní" (minuty).
const TRVANI = [15, 30, 45, 60, 90, 120, 180, 240, 480];

// Na co lze aktivitu navázat. Klíče se drží ENTITY_AKTIVIT na backendu.
const ENTITY = [
  { klic: "zakaznik", nazev: "Zákazník" },
  { klic: "op", nazev: "Obchodní případ" },
  { klic: "nab", nazev: "Nabídka" },
];

function ctvrthodinaNahoru(min) {
  return Math.min(1440 - MIN_DELKA, Math.ceil(min / 15) * 15);
}

export default function AktivitaModal({
  // Předvyplnění z kliknutí do mřížky: {termin, cas} nebo existující aktivita.
  vychozi = null,
  aktivita = null, // režim úpravy
  jaId,
  jaJmeno,
  onZavri,
  onHotovo, // (ulozenaAktivita, otevritDetail) → nadřazená stránka se obnoví
  onSerie, // (aktivita, zmena) → úprava aktivity ze série se musí zeptat na rozsah
  udalostiDne = [], // pro náhled dne vlevo
  onZmenDen, // (isoDen) → přepnout náhled i datum
}) {
  const jeUprava = Boolean(aktivita);

  const [druh, setDruh] = useState(aktivita?.druh || "schuzka");
  const [nazev, setNazev] = useState(aktivita?.nazev || "");
  const [text, setText] = useState(aktivita?.text || "");
  const [priorita, setPriorita] = useState(aktivita?.priorita || "stredni");
  const [den, setDen] = useState(
    (aktivita?.termin || vychozi?.termin || isoDen(new Date())).slice(0, 10)
  );
  const [cas, setCas] = useState(() => {
    if (aktivita?.zacatek) return hm(aktivita.zacatek);
    if (vychozi?.cas) return vychozi.cas;
    return "9:00";
  });
  const [celyDen, setCelyDen] = useState(
    jeUprava ? Boolean(aktivita.cely_den) : false
  );
  const [delka, setDelka] = useState(aktivita?.delka_min || 30);
  const [misto, setMisto] = useState(aktivita?.misto || "");
  const [kategorieId, setKategorieId] = useState(aktivita?.kategorie_id || "");
  const [proběhla, setProběhla] = useState(
    aktivita ? aktivita.stav === "realizovano" : false
  );
  const [soukroma, setSoukroma] = useState(Boolean(aktivita?.soukroma));
  const [ucastnici, setUcastnici] = useState(aktivita?.ucastnici || []);
  const [entita, setEntita] = useState(aktivita?.entita || "");
  const [zaznamId, setZaznamId] = useState(aktivita?.zaznam_id || "");
  // Opakování se zadává jen u NOVÉ aktivity. Změnit pravidlo u existující série
  // by znamenalo přepočítat a přeskládat všechny instance včetně těch, které
  // někdo ručně přesunul — to je vlastní funkce, ne políčko ve formuláři.
  const [opakovat, setOpakovat] = useState(false);
  const [frekvence, setFrekvence] = useState("tydne");
  const [intervalDni, setIntervalDni] = useState(14);
  const [konecTyp, setKonecTyp] = useState("pocet"); // "pocet" | "datum"
  const [pocetOpakovani, setPocetOpakovani] = useState(10);
  const [doData, setDoData] = useState("");

  const [kategorie, setKategorie] = useState([]);
  const [lide, setLide] = useState([]);
  const [zaznamy, setZaznamy] = useState([]);
  const [naseAdresa, setNaseAdresa] = useState("");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmKategorieAktivit()
      .then((k) => setKategorie(k.filter((x) => x.aktivni || x.id === aktivita?.kategorie_id)))
      .catch(() => setKategorie([]));
    crmUzivatele()
      .then(setLide)
      .catch(() => setLide([]));
    // Naše adresa pro tlačítko „U nás" — firemní nastavení, ne konstanta v kódu.
    crmNastaveni()
      .then((n) => setNaseAdresa(n?.nase_adresa || ""))
      .catch(() => setNaseAdresa(""));
  }, [aktivita?.kategorie_id]);

  // Seznam záznamů pro vybraný typ vazby. Načítá se až po volbě typu — než
  // člověk řekne „zákazník", nemá cenu tahat stovky případů.
  useEffect(() => {
    if (!entita) {
      setZaznamy([]);
      return;
    }
    const nacti =
      entita === "zakaznik"
        ? crmZakaznici()
        : entita === "op"
          ? crmPripady({})
          : crmNabidky();
    nacti
      .then((list) =>
        setZaznamy(
          (list || []).map((x) => ({
            id: x.id,
            popis: [x.cislo, x.nazev || x.zakaznik_nazev].filter(Boolean).join(" · ") || `#${x.id}`,
          }))
        )
      )
      .catch(() => setZaznamy([]));
  }, [entita]);

  const druhDef = DRUHY_AKTIVITY.find((d) => d.klic === druh);

  /** Placeholder nadpisu se mění podle typu — jako v předloze. */
  const placeholderNazvu = useMemo(() => {
    const podle = {
      ukol: "Co je potřeba udělat?",
      schuzka: "Doplňte předmět schůzky",
      udalost: "Doplňte název události",
      telefon: "O čem budete telefonovat?",
      dopis: "Co posíláte?",
      email: "Předmět e-mailu",
      poznamka: "Co si chcete zapsat?",
    };
    return podle[druh] || "Doplňte předmět";
  }, [druh]);

  function posunCas(o) {
    const min = ctvrthodinaNahoru(minutyZCasu(`2000-01-01T${cas.padStart(5, "0")}:00`) + o);
    setCas(naCas(Math.max(0, min)));
  }

  function zmenDen(novy) {
    setDen(novy);
    onZmenDen?.(novy);
  }

  async function uloz(otevrit) {
    const jmeno = nazev.trim();
    if (!jmeno) {
      setChyba("Aktivita potřebuje název.");
      return;
    }
    if (!den) {
      setChyba("Vyber datum.");
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      const telo = {
        druh,
        nazev: jmeno,
        text: text.trim(),
        termin: den,
        cas: celyDen ? "" : cas,
        delka_min: celyDen ? null : Number(delka) || 30,
        priorita,
        misto: misto.trim(),
        kategorie_id: kategorieId ? Number(kategorieId) : null,
        stav: proběhla ? "realizovano" : "naplanovano",
        soukroma,
        entita: soukroma ? null : entita || null,
        zaznam_id: soukroma || !entita ? null : Number(zaznamId) || null,
        ucastnici,
        opakovani:
          !jeUprava && opakovat
            ? {
                frekvence,
                interval_dni: frekvence === "vlastni" ? Number(intervalDni) || 1 : null,
                // Konec je povinný — posílá se právě jedna z variant.
                pocet: konecTyp === "pocet" ? Number(pocetOpakovani) || 1 : null,
                do_data: konecTyp === "datum" ? doData || null : null,
              }
            : null,
      };
      // Aktivita ze série: rozsah řeší nadřazená stránka dialogem, sem se
      // změna jen předá. Jinak by se uložila jen tahle instance bez dotazu.
      if (jeUprava && aktivita.serie_id && onSerie) {
        onSerie(aktivita, {
          nazev: telo.nazev,
          text: telo.text,
          termin: telo.termin,
          cas: telo.cas,
          delka_min: telo.delka_min,
          priorita: telo.priorita,
          misto: telo.misto,
          kategorie_id: telo.kategorie_id ?? -1,
          stav: telo.stav,
          ucastnici: telo.ucastnici,
        });
        onZavri?.();
        return;
      }

      const vysledek = jeUprava
        ? await crmAktivitaUprav(aktivita.id, {
            // Úprava posílá jen to, co modál umí měnit; -1 u kategorie znamená
            // „odeber" (null by znamenalo „neměnit", viz AktivitaUprava).
            nazev: telo.nazev,
            text: telo.text,
            termin: telo.termin,
            cas: telo.cas,
            delka_min: telo.delka_min,
            priorita: telo.priorita,
            misto: telo.misto,
            kategorie_id: telo.kategorie_id ?? -1,
            stav: telo.stav,
            ucastnici: telo.ucastnici,
          })
        : await crmUdalostPridej(telo);
      onHotovo?.(vysledek, otevrit);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  // ---- náhled dne vlevo ----
  /**
   * Které hodiny náhled pruhu pokrývá.
   *
   * Základ je pracovní část 7–20, ale rozsah se rozšíří na cokoli, co se
   * do dne plánuje — jinak by aktivita ve 23:00 (nebo v 6:00) skončila „za
   * hranou" pruhu a člověk by při zapisování nočního hovoru neviděl, do čeho
   * ho dává.
   */
  const rozsahNahledu = useMemo(() => {
    let odH = 7;
    let doH = 20;
    const zapoj = (odMin, delkaMin) => {
      odH = Math.min(odH, Math.floor(odMin / 60));
      doH = Math.max(doH, Math.ceil((odMin + (delkaMin || 30)) / 60));
    };
    if (!celyDen) {
      zapoj(minutyZCasu(`2000-01-01T${cas.padStart(5, "0")}:00`), Number(delka) || 30);
    }
    for (const u of udalostiDne || []) {
      if (u.cely_den || (u.termin || "").slice(0, 10) !== den) continue;
      zapoj(minutyZCasu(u.zacatek), u.delka_min);
    }
    odH = Math.max(0, odH);
    doH = Math.min(24, Math.max(doH, odH + 1));
    return { odH, doH, start: odH * 60, rozsah: (doH - odH) * 60 };
  }, [cas, delka, celyDen, udalostiDne, den]);

  const nahledDne = useMemo(() => {
    const { start, rozsah } = rozsahNahledu;
    return (udalostiDne || [])
      .filter((u) => !u.cely_den && (u.termin || "").slice(0, 10) === den)
      .map((u) => {
        const od = minutyZCasu(u.zacatek);
        return {
          ...u,
          top: ((od - start) / rozsah) * 100,
          vyska: Math.max(((u.delka_min || 30) / rozsah) * 100, 3),
        };
      });
  }, [udalostiDne, den, rozsahNahledu]);

  const novaTop = useMemo(() => {
    if (celyDen) return null;
    const od = minutyZCasu(`2000-01-01T${cas.padStart(5, "0")}:00`);
    const { start, rozsah } = rozsahNahledu;
    return {
      top: ((od - start) / rozsah) * 100,
      vyska: Math.max(((Number(delka) || 30) / rozsah) * 100, 3),
    };
  }, [cas, delka, celyDen, rozsahNahledu]);

  const denObj = new Date(`${den}T12:00:00`);
  const DNY = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"];

  return (
    <div className="am-plast" onClick={onZavri}>
      <div className="am-okno" onClick={(e) => e.stopPropagation()}>
        {/* ---- náhled dne ---- */}
        <aside className="am-nahled">
          <div className="am-nahled-hlava">
            <button
              className="am-nahled-sipka"
              onClick={() => zmenDen(isoDen(posunDnu(denObj, -1)))}
              aria-label="Předchozí den"
            >
              ‹
            </button>
            <span className="am-nahled-den">
              {DNY[(denObj.getDay() + 6) % 7]} {denObj.getDate()}.{denObj.getMonth() + 1}.
            </span>
            <button
              className="am-nahled-sipka"
              onClick={() => zmenDen(isoDen(posunDnu(denObj, 1)))}
              aria-label="Další den"
            >
              ›
            </button>
          </div>
          <div
            className="am-nahled-pruh"
            style={{ "--am-hodin": rozsahNahledu.doH - rozsahNahledu.odH }}
          >
            {Array.from(
              { length: rozsahNahledu.doH - rozsahNahledu.odH },
              (_, i) => rozsahNahledu.odH + i
            ).map((h) => (
              <div key={h} className="am-nahled-hodina">
                <span>{h}:00</span>
              </div>
            ))}
            {nahledDne.map((u) => (
              <div
                key={u.id}
                className="am-nahled-udalost"
                style={{
                  top: `${u.top}%`,
                  height: `${u.vyska}%`,
                  background: u.kategorie_barva || "#d3d9de",
                }}
                title={`${hm(u.zacatek)} ${u.nazev}`}
              >
                {hm(u.zacatek)} {u.nazev}
              </div>
            ))}
            {novaTop && (
              <div
                className="am-nahled-udalost nova"
                style={{ top: `${novaTop.top}%`, height: `${novaTop.vyska}%` }}
              >
                {cas} {nazev || placeholderNazvu}
              </div>
            )}
          </div>
        </aside>

        {/* ---- formulář ---- */}
        <div className="am-telo">
          <div className="am-hlava">
            <input
              className="am-nazev"
              value={nazev}
              onChange={(e) => setNazev(e.target.value)}
              placeholder={placeholderNazvu}
              autoFocus
            />
            <button className="am-zavrit" onClick={onZavri} aria-label="Zavřít">
              ✕
            </button>
          </div>

          <div className="am-obsah">
            <div className="am-hlavni">
              {/* typ + priorita */}
              <div className="am-radek-typu">
                <div className="am-typy">
                  {DRUHY_AKTIVITY.filter((d) => d.klic !== "poznamka" && d.klic !== "email").map(
                    (d) => (
                      <button
                        key={d.klic}
                        className={`am-typ ${druh === d.klic ? "aktivni" : ""}`}
                        onClick={() => setDruh(d.klic)}
                        title={d.nazev}
                        type="button"
                      >
                        <Ikona jmeno={d.ikona} velikost={17} />
                        {druh === d.klic && <span className="am-typ-nazev">{d.nazev}</span>}
                      </button>
                    )
                  )}
                </div>

                <div className="am-priorita">
                  <span className="am-label">Priorita</span>
                  <div className="am-priorita-volby">
                    {PRIORITY_AKTIVITY.map((p) => (
                      <button
                        key={p.klic}
                        className={`am-priorita-volba ${priorita === p.klic ? "aktivni" : ""}`}
                        onClick={() => setPriorita(p.klic)}
                        title={p.nazev}
                        type="button"
                      >
                        {p.znak}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* termín */}
              <div className="am-mrizka">
                <div>
                  <span className="am-label">Datum</span>
                  <input
                    className="crm-pole"
                    type="date"
                    value={den}
                    onChange={(e) => zmenDen(e.target.value)}
                  />
                </div>
                <div>
                  <span className="am-label">Začátek</span>
                  <div className="am-cas">
                    <input
                      className="crm-pole"
                      type="time"
                      value={cas.padStart(5, "0")}
                      disabled={celyDen}
                      onChange={(e) => setCas(e.target.value)}
                    />
                    <div className="am-cas-sipky">
                      <button onClick={() => posunCas(15)} disabled={celyDen} aria-label="O 15 minut později">
                        ▲
                      </button>
                      <button onClick={() => posunCas(-15)} disabled={celyDen} aria-label="O 15 minut dříve">
                        ▼
                      </button>
                    </div>
                  </div>
                </div>
                <div>
                  <span className="am-label">Trvání</span>
                  <div className="am-trvani">
                    <select
                      className="crm-pole"
                      value={delka}
                      disabled={celyDen}
                      onChange={(e) => setDelka(Number(e.target.value))}
                    >
                      {TRVANI.map((m) => (
                        <option key={m} value={m}>
                          {m < 60 ? `${m} minut` : m === 60 ? "1 hodina" : `${m / 60} hodiny`}
                        </option>
                      ))}
                    </select>
                    <label className="am-celyden" title="Aktivita bez konkrétní hodiny">
                      <input
                        type="checkbox"
                        checked={celyDen}
                        onChange={(e) => setCelyDen(e.target.checked)}
                      />
                      celý den
                    </label>
                  </div>
                </div>
              </div>

              {/* místo */}
              <div className="am-blok">
                <span className="am-label">Místo konání</span>
                <div className="am-misto">
                  <span className="am-misto-ikona" aria-hidden="true">
                    <Ikona jmeno="zakaznici" velikost={14} />
                  </span>
                  <input
                    className="crm-pole"
                    value={misto}
                    onChange={(e) => setMisto(e.target.value)}
                    placeholder="Doplňte adresu nebo jiné označení"
                  />
                  {naseAdresa && (
                    <button
                      className="am-unas"
                      onClick={() => setMisto(naseAdresa)}
                      type="button"
                      title={naseAdresa}
                    >
                      U nás
                    </button>
                  )}
                </div>
              </div>

              {/* kategorie */}
              <div className="am-blok">
                <span className="am-label">Kategorie</span>
                <div className="am-kategorie">
                  <span className="am-tecky" aria-hidden="true">
                    {kategorie.slice(0, 6).map((k) => (
                      <span key={k.id} className="am-tecka" style={{ background: k.barva }} />
                    ))}
                  </span>
                  <select
                    className="crm-pole"
                    value={kategorieId}
                    onChange={(e) => setKategorieId(e.target.value)}
                  >
                    <option value="">– Vyberte kategorii –</option>
                    {kategorie.map((k) => (
                      <option key={k.id} value={k.id}>
                        {k.nazev}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* poznámky */}
              <div className="am-blok">
                <span className="am-label">
                  {druh === "schuzka" || druh === "udalost"
                    ? "Otázky k projednání"
                    : "Poznámky"}
                </span>
                <textarea
                  className="crm-pole"
                  rows={5}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                />
              </div>

              {/* opakování — jen u nové aktivity */}
              {!jeUprava && (
                <div className="am-blok">
                  <label className="crm-zaskrtavaci" style={{ margin: 0 }}>
                    <input
                      type="checkbox"
                      checked={opakovat}
                      onChange={(e) => setOpakovat(e.target.checked)}
                    />
                    Opakovat
                  </label>
                  {opakovat && (
                    <div className="am-opakovani">
                      <select
                        className="crm-pole"
                        value={frekvence}
                        onChange={(e) => setFrekvence(e.target.value)}
                      >
                        {FREKVENCE_OPAKOVANI.map((f) => (
                          <option key={f.klic} value={f.klic}>
                            {f.nazev}
                          </option>
                        ))}
                      </select>
                      {frekvence === "vlastni" && (
                        <label className="am-opak-radek">
                          každých
                          <input
                            className="crm-pole crm-pole-cislo"
                            type="number"
                            min={1}
                            max={365}
                            value={intervalDni}
                            onChange={(e) => setIntervalDni(e.target.value)}
                          />
                          dní
                        </label>
                      )}
                      <div className="am-opak-radek">
                        <select
                          className="crm-pole crm-pole-uzke"
                          value={konecTyp}
                          onChange={(e) => setKonecTyp(e.target.value)}
                        >
                          <option value="pocet">celkem opakování</option>
                          <option value="datum">do data</option>
                        </select>
                        {konecTyp === "pocet" ? (
                          <input
                            className="crm-pole crm-pole-cislo"
                            type="number"
                            min={1}
                            max={520}
                            value={pocetOpakovani}
                            onChange={(e) => setPocetOpakovani(e.target.value)}
                          />
                        ) : (
                          <input
                            className="crm-pole"
                            type="date"
                            value={doData}
                            min={den}
                            onChange={(e) => setDoData(e.target.value)}
                          />
                        )}
                      </div>
                      <p className="crm-tise" style={{ margin: 0 }}>
                        Opakování musí mít konec — appka vytvoří jednotlivé události dopředu,
                        takže je pak jde po jedné přesouvat i rušit. Nejvýš dva roky.
                      </p>
                    </div>
                  )}
                </div>
              )}
              {jeUprava && aktivita?.serie_popis && (
                <p className="crm-tise">
                  Aktivita patří do opakované série ({aktivita.serie_popis}). Změna se při
                  uložení zeptá, jestli platí pro tuhle, pro tuhle a další, nebo pro celou sérii.
                </p>
              )}

              {/* zaškrtávátka */}
              <label className="crm-zaskrtavaci">
                <input
                  type="checkbox"
                  checked={proběhla}
                  onChange={(e) => setProběhla(e.target.checked)}
                />
                {druhDef?.nazev || "Aktivita"} už proběhla
              </label>
              <label className="crm-zaskrtavaci">
                <input
                  type="checkbox"
                  checked={soukroma}
                  onChange={(e) => {
                    setSoukroma(e.target.checked);
                    if (e.target.checked) {
                      setEntita("");
                      setZaznamId("");
                    }
                  }}
                />
                Soukromá aktivita – bez vazby na klienta
              </label>
              {soukroma && (
                <p className="crm-tise" style={{ marginTop: 4 }}>
                  Obsah soukromé aktivity neuvidí nikdo další — ani vedení, ani správce.
                  V cizím kalendáři se ukáže jen jako obsazený čas.
                </p>
              )}
            </div>

            {/* pravý sloupec */}
            <div className="am-bok">
              <div className="am-bok-sekce">
                <span className="am-label">Kdo se zúčastní</span>
                <div className="am-ucastnik">
                  <span className="kalf-avatar" aria-hidden="true">
                    {(jaJmeno || "?")
                      .split(/\s+/)
                      .map((x) => x[0] || "")
                      .join("")
                      .slice(0, 2)
                      .toUpperCase()}
                  </span>
                  <span>
                    <b>{jaJmeno}</b>
                    <span className="crm-tise" style={{ display: "block" }}>
                      Vlastník
                    </span>
                  </span>
                </div>
                {ucastnici.map((id) => {
                  const u = lide.find((x) => x.id === id);
                  return (
                    <div className="am-ucastnik" key={id}>
                      <span className="kalf-avatar" aria-hidden="true">
                        {(u?.jmeno || "?")
                          .split(/\s+/)
                          .map((x) => x[0] || "")
                          .join("")
                          .slice(0, 2)
                          .toUpperCase()}
                      </span>
                      <span>{u?.jmeno || `#${id}`}</span>
                      <span className="crm-mezera" />
                      <button
                        className="kalf-odebrat"
                        onClick={() => setUcastnici((s) => s.filter((x) => x !== id))}
                        title="Odebrat účastníka"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
                <select
                  className="crm-pole"
                  value=""
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    if (id) setUcastnici((s) => [...new Set([...s, id])]);
                  }}
                >
                  <option value="">+ Přidat účastníka</option>
                  {lide
                    .filter((u) => u.id !== jaId && !ucastnici.includes(u.id))
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.jmeno}
                      </option>
                    ))}
                </select>
              </div>

              {!soukroma && (
                <div className="am-bok-sekce">
                  <span className="am-label">Čeho se to týká</span>
                  <select
                    className="crm-pole"
                    value={entita}
                    onChange={(e) => {
                      setEntita(e.target.value);
                      setZaznamId("");
                    }}
                  >
                    <option value="">– nepovinné –</option>
                    {ENTITY.map((x) => (
                      <option key={x.klic} value={x.klic}>
                        {x.nazev}
                      </option>
                    ))}
                  </select>
                  {entita && (
                    <select
                      className="crm-pole"
                      style={{ marginTop: 6 }}
                      value={zaznamId}
                      onChange={(e) => setZaznamId(e.target.value)}
                    >
                      <option value="">– vyber záznam –</option>
                      {zaznamy.map((z) => (
                        <option key={z.id} value={z.id}>
                          {z.popis}
                        </option>
                      ))}
                    </select>
                  )}
                  {entita && !zaznamId && (
                    <p className="crm-tise" style={{ marginTop: 4 }}>
                      Vyber konkrétní záznam, nebo typ vazby zruš.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {chyba && <div className="crm-chyba">{chyba}</div>}

          <div className="am-pata">
            <button
              className="fm-btn fm-primary"
              onClick={() => uloz(true)}
              disabled={uklada}
            >
              {uklada ? "Ukládám…" : "Uložit a otevřít"}
            </button>
            <button className="fm-btn am-ulozit" onClick={() => uloz(false)} disabled={uklada}>
              Uložit
            </button>
            <span className="crm-mezera" />
            {soukroma && (
              <span className="am-zamek" title="Soukromá aktivita — obsah nikdo další neuvidí">
                <Ikona jmeno="klic" velikost={15} />
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
