import { useEffect, useMemo, useRef, useState } from "react";
import {
  crmKategorie,
  crmPripadDetail,
  crmPripadUprav,
  crmPripadZaloz,
  crmUzivatele,
  crmVlastniPole,
  crmZakaznici,
} from "../api";
import Pritomni from "./Pritomni";
import StavUlozeni from "./StavUlozeni";
import VlastniPoleVstupy from "./VlastniPoleVstupy";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";

/**
 * Pole, která backend umí uložit po jednom (whitelist v `crm/pole_zaznamu.py`,
 * entita „op"). Co tu není, se přes automatické ukládání změnit nedá — server
 * to odmítne se 422, takže seznam musí být stejný jako tam.
 */
const POLE = ["nazev", "popis", "hodnota_kc", "pravdepodobnost", "predpokladane_uzavreni"];

export const NAZVY_POLI = {
  nazev: "Název případu",
  popis: "Popis",
  hodnota_kc: "Hodnota (Kč)",
  pravdepodobnost: "Pravděpodobnost",
  predpokladane_uzavreni: "Předpokládané uzavření",
};

/** Čitelný název pole — pro kolečka přítomnosti i pro hlášku o kolizi. */
export function popisPole(klic) {
  if (!klic) return "";
  // Vlastní pole se hlásí jako „extra:dotace"; klíč je to nejlepší, co tady
  // máme — definice polí zná formulář, ne karta.
  if (klic.startsWith("extra:")) return klic.slice(6);
  return NAZVY_POLI[klic] || klic;
}

/**
 * Formulář obchodního případu.
 *
 * Číslo (OP-RR-NNNN) přiděluje backend z číselné řady – v UI se nezadává,
 * aby nemohly vzniknout dva případy se stejným ID.
 *
 * `raynet_code` je vidět jen při úpravě: je to most na složky Google Disku
 * u případů, které vznikly ještě v Raynetu. U nových se nechává prázdný.
 *
 * Formulář má dva režimy a je to tu to hlavní rozhodnutí:
 *
 *  - **Úprava existujícího případu** (`pripad`) — pole se ukládají sama, každé
 *    zvlášť (`useZaznamAutosave`). Nad případem se schází obchodník, vedoucí
 *    i backoffice, a staré ukládání celého formuláře jedním PUT znamenalo, že
 *    kdo uložil poslední, přepsal i pole, kterých se ani nedotkl. „Hotovo" už
 *    proto neukládá — jen dožene, co se nestihlo odeslat, a zavře okno.
 *  - **Zakládání nového případu** (bez `pripad`) — zůstává tlačítko „Založit
 *    případ" a jeden POST. Automatické ukládání tu není z principu možné:
 *    záznam ještě neexistuje, není co patchovat.
 *
 * Pole, která backend přes ukládání po polích nepovoluje (kategorie, vlastník,
 * Raynetí číslo, přepojení na jiného zákazníka), mají vedlejší efekty
 * (automatizace, notifikace, párování složek). Zůstávají tedy na starém PUT,
 * který se pošle až při „Hotovo" — a to nad ČERSTVĚ načteným záznamem, aby
 * PUT nevrátil do databáze text, který mezitím někdo přepsal.
 */
export default function PripadFormular({
  pripad = null,
  zakaznik = null,
  muzeMenitVlastnika = false,
  // Kdo má kartu otevřenou (posílá karta případu — jeden tik na záznam).
  pritomni = [],
  // Karta případu si tím drží „na jakém poli člověk stojí" pro přítomnost.
  onFokusPole,
  onZavri,
  onHotovo,
}) {
  const jeUprava = Boolean(pripad);
  const [form, setForm] = useState(() => ({
    zakaznik_id: pripad?.zakaznik_id || zakaznik?.id || null,
    nazev: pripad?.nazev || "",
    popis: pripad?.popis || "",
    kategorie: pripad?.kategorie || [],
    hodnota_kc: pripad?.hodnota_kc != null ? String(pripad.hodnota_kc) : "",
    pravdepodobnost: pripad?.pravdepodobnost != null ? String(pripad.pravdepodobnost) : "",
    predpokladane_uzavreni: (pripad?.predpokladane_uzavreni || "").slice(0, 10),
    vlastnik_user_id: pripad?.vlastnik_user_id || null,
    spoluvlastnici: pripad?.spoluvlastnici || [],
    raynet_code: pripad?.raynet_code || "",
    extra: pripad?.extra || {},
  }));
  const [zakaznici, setZakaznici] = useState(zakaznik ? [zakaznik] : []);
  const [kategorie, setKategorie] = useState([]);
  const [vlastniPole, setVlastniPole] = useState(pripad?.vlastni_pole || []);
  const [lidi, setLidi] = useState([]);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  // Výpočtové pole (CRM-34) se nevyplňuje, jen zobrazuje — do automatického
  // ukládání nepatří, hodnotu si stejně přepočítá backend.
  const poleAutosave = useMemo(
    () => [
      ...POLE,
      ...(vlastniPole || [])
        .filter((p) => !(p.vzorec || "").trim())
        .map((p) => `extra:${p.klic}`),
    ],
    [vlastniPole],
  );

  const {
    hodnoty,
    zmen: zmenAutosave,
    stav,
    chyba: chybaUlozeni,
    kdy,
    ceka,
    kolize,
    prepis,
    vezmiJejich,
    dokonci,
    onFokus,
    onBlur,
  } = useZaznamAutosave({
    entita: "op",
    id: pripad?.id,
    zaznam: pripad,
    pole: poleAutosave,
    // `entitaTyp` tu schválně NENÍ: přítomnost hlásí karta případu, jedním
    // tikem na záznam. Druhý tik ze stejné stránky by kolegům přepisoval pole,
    // na kterém člověk zrovna stojí (v tabulce je jeden řádek na uživatele).
    zapnuto: jeUprava,
  });

  // Zrcadla pro `hotovo()`: uzavřené hodnoty z renderu by po `await` byly
  // staré, a právě tehdy potřebujeme vědět, jak dopadlo poslední uložení.
  const stavRef = useRef(stav);
  stavRef.current = stav;
  const kolizeRef = useRef(kolize);
  kolizeRef.current = kolize;
  const cekaRef = useRef(ceka);
  cekaRef.current = ceka;

  // Stav ručních polí při otevření okna. Porovnává se s tímhle, ne s aktuálním
  // `pripad`: kdyby kategorii mezitím změnil kolega, formulář by se proti
  // čerstvému záznamu tvářil „změněný" a PUT by mu jeho volbu přepsal zpátky.
  const puvodniRucni = useRef({
    zakaznik_id: pripad?.zakaznik_id ?? null,
    kategorie: (pripad?.kategorie || []).join("|"),
    vlastnik_user_id: pripad?.vlastnik_user_id ?? null,
    raynet_code: (pripad?.raynet_code || "").trim().toUpperCase(),
  });

  const rucniZmeneno =
    jeUprava &&
    ((form.zakaznik_id ?? null) !== puvodniRucni.current.zakaznik_id ||
      (form.kategorie || []).join("|") !== puvodniRucni.current.kategorie ||
      (form.vlastnik_user_id ?? null) !== puvodniRucni.current.vlastnik_user_id ||
      form.raynet_code.trim().toUpperCase() !== puvodniRucni.current.raynet_code);

  useEffect(() => {
    // Výběr zákazníka nabízíme jen tam, kde není předvybraný (sekce Případy).
    if (zakaznik) return;
    crmZakaznici()
      .then(setZakaznici)
      .catch(() => setZakaznici([]));
  }, [zakaznik]);

  useEffect(() => {
    if (pripad?.vlastni_pole) return;
    crmVlastniPole("op")
      .then(setVlastniPole)
      .catch(() => setVlastniPole([]));
  }, [pripad]);

  // Kategorie jsou konfigurovatelné (CRM-03), takže se načítají z appky.
  // Vypnuté se nenabízejí – kromě těch, které tenhle případ už má, jinak by
  // se při uložení tiše ztratily.
  useEffect(() => {
    crmKategorie()
      .then(setKategorie)
      .catch(() => setKategorie([]));
  }, []);

  useEffect(() => {
    if (!muzeMenitVlastnika) return;
    crmUzivatele()
      .then(setLidi)
      .catch(() => setLidi([]));
  }, [muzeMenitVlastnika]);

  function zmenForm(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  /**
   * Zápis do pole, které backend umí uložit samostatně. Při úpravě jde na
   * server sám, při zakládání jen do formuláře — tam se pošle celý POST.
   */
  function zmenUdaj(klic, hodnota, ihned = false) {
    if (jeUprava) zmenAutosave(klic, hodnota, ihned);
    else zmenForm(klic, hodnota);
  }

  /** Hodnota autosave pole: v úpravě ji drží hook, při zakládání formulář. */
  function udaj(klic) {
    return (jeUprava ? hodnoty[klic] : form[klic]) ?? "";
  }

  function fokus(klic) {
    if (!jeUprava) return;
    onFokus(klic);
    if (onFokusPole) onFokusPole(klic);
  }

  function odchod(klic) {
    if (!jeUprava) return;
    onBlur(klic);
    if (onFokusPole) onFokusPole("");
  }

  // Vlastní pole: základ z posledního načtení (kvůli výpočtovým polím, která
  // hook nespravuje), navrch to, co má člověk rozepsané.
  const extraHodnoty = useMemo(() => {
    if (!jeUprava) return form.extra;
    const vysledek = { ...(pripad?.extra || {}) };
    (vlastniPole || []).forEach((p) => {
      const klic = `extra:${p.klic}`;
      if (klic in hodnoty) vysledek[p.klic] = hodnoty[klic];
    });
    return vysledek;
  }, [jeUprava, form.extra, pripad, vlastniPole, hodnoty]);

  function prepniKategorii(klic) {
    setForm((f) => ({
      ...f,
      kategorie: f.kategorie.includes(klic)
        ? f.kategorie.filter((k) => k !== klic)
        : [...f.kategorie, klic],
    }));
  }

  /** Zakládání nového případu – jeden POST, jak to bylo vždycky. */
  async function zaloz() {
    setUklada(true);
    setChyba(null);
    try {
      const data = {
        ...form,
        nazev: form.nazev.trim(),
        hodnota_kc:
          form.hodnota_kc.trim() === "" ? null : Number(form.hodnota_kc.replace(",", ".")),
        pravdepodobnost:
          form.pravdepodobnost.trim() === "" ? null : Number(form.pravdepodobnost),
        predpokladane_uzavreni: form.predpokladane_uzavreni || null,
      };
      onHotovo(await crmPripadZaloz(data));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /**
   * Ruční pole (kategorie, vlastník, Raynetí číslo, přepojení zákazníka)
   * starým PUT — ale nad čerstvě načteným záznamem.
   *
   * PUT přepisuje CELÝ případ z toho, co dostane, a `extra` navíc staví nanovo
   * (chybějící klíč se smaže). Kdyby se poslala data z formuláře, vrátil by do
   * databáze text, který mezitím uložil někdo jiný — přesně to, čemu se
   * ukládáním po polích vyhýbáme.
   */
  function ulozRucni(cerstvy) {
    return crmPripadUprav(pripad.id, {
      zakaznik_id: form.zakaznik_id,
      kategorie: form.kategorie,
      vlastnik_user_id: form.vlastnik_user_id,
      raynet_code: form.raynet_code,
      // Zbytek jde zpátky tak, jak ho má právě teď databáze.
      nazev: cerstvy.nazev || "",
      popis: cerstvy.popis || "",
      hodnota_kc: cerstvy.hodnota_kc ?? null,
      pravdepodobnost: cerstvy.pravdepodobnost ?? null,
      predpokladane_uzavreni: (cerstvy.predpokladane_uzavreni || "").slice(0, 10) || null,
      spoluvlastnici: cerstvy.spoluvlastnici || [],
      extra: cerstvy.extra || {},
    });
  }

  /**
   * Počká, než dojedou uložení, která už letí na server (max 2 sekundy).
   *
   * Kliknutí na „Hotovo" vyvolá nejdřív `blur` posledního pole, takže se
   * hodnota posílá sama a `dokonci()` u ní už nemá co dohánět — odpověď ale
   * ještě nedošla. Bez tohohle čekání by se záznam natáhl BEZ posledního
   * znaku a karta by pod formulářem ukázala starou hodnotu.
   */
  async function pockejNaOdeslani() {
    for (let i = 0; i < 40 && cekaRef.current; i += 1) {
      // eslint-disable-next-line no-await-in-loop
      await new Promise((dal) => setTimeout(dal, 50));
    }
  }

  /**
   * Konec úprav. Neukládá to, co se ukládá samo — jen dožene neodeslané změny,
   * dopíše ruční pole a zavře okno. Když se něco nepovedlo, okno zůstává
   * otevřené: zavřít ho s neuloženým textem znamená ten text zahodit.
   */
  async function hotovo() {
    // Kliknutí mimo okno i tlačítko vedou na totéž; podruhé se to nesmí spustit.
    if (uklada) return;
    if (kolize) {
      setChyba("Nejdřív rozhodni, čí hodnota u kolize platí — pak okno zavři.");
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      await dokonci();
      await pockejNaOdeslani();
      // Čerstvý záznam potřebujeme tak jako tak (pro kartu i pro ruční pole).
      // Cesta na server zároveň dá Reactu čas překreslit, takže refy níž už
      // vědí, jak dopadlo poslední uložení.
      const cerstvy = await crmPripadDetail(pripad.id);
      if (kolizeRef.current || stavRef.current === "chyba") {
        setChyba("Něco se neuložilo – okno nechávám otevřené, ať o text nepřijdeš.");
        return;
      }
      onHotovo(rucniZmeneno ? await ulozRucni(cerstvy) : cerstvy);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  // Zavírací gesta (✕, kliknutí mimo okno) v úpravě neznamenají „zruš to" —
  // pole už jsou uložená. Musí tedy jít stejnou cestou jako „Hotovo", jinak by
  // se zahodily posledních pár znaků a nedopsaná ruční pole.
  const zavri = jeUprava ? hotovo : onZavri;

  return (
    <div className="crm-okno-plast" onClick={zavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? `Úprava ${pripad.cislo}` : "Nový obchodní případ"}</h2>
          <span className="crm-mezera" />
          {/* Kdo má případ otevřený taky – ať je vidět, s kým se člověk může
              potkat, ještě než napíše první znak. */}
          {jeUprava && <Pritomni pritomni={pritomni} popisekPole={popisPole} />}
          {/* Hláška o ukládání je v patičce okna – ta je vidět pořád, takže
              druhá kopie v hlavičce by jen skákala. */}
          <button className="crm-zavrit" onClick={zavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          {!jeUprava && (
            <p className="crm-tise">
              Číslo případu (OP-RR-NNNN) přidělí appka sama při založení.
            </p>
          )}
          {jeUprava && (
            <p className="crm-tise">
              Údaje se ukládají samy, pole po poli – kolega nad stejným případem ti nic
              nepřepíše. Kategorie, vlastník a Raynetí číslo spouštějí automatizace
              a přiřazení, takže se pošlou až tlačítkem <b>Hotovo</b>.
            </p>
          )}

          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Zákazník *</label>
              {zakaznik ? (
                <input className="crm-pole" value={zakaznik.nazev} disabled />
              ) : (
                <select
                  className="crm-pole"
                  value={form.zakaznik_id || ""}
                  onChange={(e) =>
                    zmenForm("zakaznik_id", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">— vyber zákazníka —</option>
                  {zakaznici.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.nazev}
                      {z.ico ? ` (${z.ico})` : ""}
                    </option>
                  ))}
                </select>
              )}
            </div>
            <div>
              <label className="crm-label">Název případu</label>
              <input
                className="crm-pole"
                value={udaj("nazev")}
                onChange={(e) => zmenUdaj("nazev", e.target.value)}
                onFocus={() => fokus("nazev")}
                onBlur={() => odchod("nazev")}
                placeholder="např. FVE na střeše výrobní haly"
              />
            </div>

            {/* Kategorie je schválně víc než jedna: případ může být PPA
                i peak shaving současně a podle toho pak míří do výpočtů. */}
            <div className="crm-sirka3">
              <label className="crm-label">Kategorie (můžeš vybrat víc)</label>
              <div className="crm-volby">
                {kategorie
                  .filter((k) => k.aktivni || form.kategorie.includes(k.klic))
                  .map((k) => (
                    <button
                      key={k.klic}
                      type="button"
                      className={`crm-pilulka ${form.kategorie.includes(k.klic) ? "aktivni" : ""}`}
                      onClick={() => prepniKategorii(k.klic)}
                      title={k.typ_nabidky ? k.popis : `${k.popis} (bez výpočtu nabídky)`}
                    >
                      {k.nazev}
                    </button>
                  ))}
              </div>
              <p className="crm-tise" style={{ marginTop: 6 }}>
                Podle kategorie pozná appka, kam poslat výpočet nabídky. Když necháš prázdné,
                zeptá se při vytvoření nabídky.
              </p>
            </div>

            <div>
              <label className="crm-label">Hodnota (Kč)</label>
              <input
                className="crm-pole"
                value={udaj("hodnota_kc")}
                onChange={(e) => zmenUdaj("hodnota_kc", e.target.value)}
                onFocus={() => fokus("hodnota_kc")}
                onBlur={() => odchod("hodnota_kc")}
                inputMode="decimal"
                placeholder="např. 1500000"
              />
            </div>
            <div>
              <label className="crm-label">Pravděpodobnost (%)</label>
              <input
                className="crm-pole"
                value={udaj("pravdepodobnost")}
                onChange={(e) => zmenUdaj("pravdepodobnost", e.target.value)}
                onFocus={() => fokus("pravdepodobnost")}
                onBlur={() => odchod("pravdepodobnost")}
                inputMode="numeric"
                placeholder="0–100"
              />
            </div>
            <div>
              <label className="crm-label">Předpokládané uzavření</label>
              {/* Datum je hotové rozhodnutí, ne rozepsaná věta – jde na server
                  hned, bez čekání na prodlevu. */}
              <input
                className="crm-pole"
                type="date"
                value={String(udaj("predpokladane_uzavreni")).slice(0, 10)}
                onChange={(e) => zmenUdaj("predpokladane_uzavreni", e.target.value, true)}
                onFocus={() => fokus("predpokladane_uzavreni")}
                onBlur={() => odchod("predpokladane_uzavreni")}
              />
            </div>

            {muzeMenitVlastnika && (
              <div>
                <label className="crm-label">Vlastník případu</label>
                <select
                  className="crm-pole"
                  value={form.vlastnik_user_id || ""}
                  onChange={(e) =>
                    zmenForm("vlastnik_user_id", e.target.value ? Number(e.target.value) : null)
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

            {jeUprava && (
              <div>
                <label className="crm-label">Raynetí číslo (koexistence)</label>
                <input
                  className="crm-pole"
                  value={form.raynet_code}
                  onChange={(e) => zmenForm("raynet_code", e.target.value)}
                  placeholder="OP-26-0223"
                />
                <p className="crm-tise" style={{ marginTop: 6 }}>
                  Vyplň u případů, které vznikly v Raynetu – přes tohle číslo se páruje
                  složka dokumentů na Disku.
                </p>
              </div>
            )}

            <div className="crm-sirka3">
              <label className="crm-label">Popis</label>
              <textarea
                className="crm-pole"
                rows={3}
                value={udaj("popis")}
                onChange={(e) => zmenUdaj("popis", e.target.value)}
                onFocus={() => fokus("popis")}
                onBlur={() => odchod("popis")}
              />
            </div>

            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={extraHodnoty}
              // Při zakládání se posílá celé `extra` v jednom POST, při úpravě
              // se ukládá pole po poli — celé `extra` by přepsalo i klíče,
              // kterých se člověk nedotkl.
              onZmena={jeUprava ? undefined : (extra) => zmenForm("extra", extra)}
              onZmenaPole={
                jeUprava
                  ? (klic, hodnota, ihned) => zmenAutosave(`extra:${klic}`, hodnota, ihned)
                  : undefined
              }
            />
          </div>

          {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. */}
          {kolize && (
            <div className="crm-kolize">
              <div>
                <strong>{popisPole(kolize.pole)}</strong> mezitím změnil
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

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          {jeUprava ? (
            <>
              <span className="crm-tise">Změny se ukládají samy, tlačítko jen zavře okno.</span>
              <span className="crm-mezera" />
              <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
              <button className="fm-btn fm-primary" onClick={hotovo} disabled={uklada}>
                {uklada ? "Dokončuji…" : "Hotovo"}
              </button>
            </>
          ) : (
            <>
              <button className="fm-btn" onClick={onZavri}>
                Zrušit
              </button>
              <span className="crm-mezera" />
              <button
                className="fm-btn fm-primary"
                onClick={zaloz}
                disabled={uklada || !form.zakaznik_id}
              >
                {uklada ? "Ukládám…" : "Založit případ"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
