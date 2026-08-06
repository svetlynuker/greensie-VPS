import { useEffect, useMemo, useRef, useState } from "react";
import {
  crmAres,
  crmUzivatele,
  crmVlastniPole,
  crmZakaznikDetail,
  crmZakaznikZaloz,
} from "../api";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";
import Pritomni from "./Pritomni";
import StavUlozeni from "./StavUlozeni";
import VlastniPoleVstupy from "./VlastniPoleVstupy";

// Pole, která se u existujícího zákazníka ukládají sama. `typ` (lead/klient)
// a vlastnictví tu schválně NEJSOU: přepisují se i jinde (konverze na klienta,
// hromadná změna vlastníka) a mají vedlejší efekty, takže patří na vědomé
// kliknutí, ne na psaní.
const POLE = [
  "nazev",
  "ico",
  "dic",
  "adresa_ulice",
  "adresa_mesto",
  "adresa_psc",
  "adresa_stat",
  "gps_lat",
  "gps_lng",
  "web",
  "telefon",
  "email",
  "zdroj",
  "poznamka",
];

// Čitelné názvy polí. Exportují se, protože je potřebuje i karta zákazníka —
// v kolečkách přítomnosti se ukazuje, na kterém poli kolega právě je, a „adresa_psc“
// nikomu nic neřekne.
export const NAZVY_POLI = {
  nazev: "Název firmy",
  ico: "IČO",
  dic: "DIČ",
  adresa_ulice: "Ulice a číslo",
  adresa_mesto: "Město",
  adresa_psc: "PSČ",
  adresa_stat: "Stát",
  gps_lat: "GPS šířka",
  gps_lng: "GPS délka",
  web: "Web",
  telefon: "Telefon",
  email: "E-mail",
  zdroj: "Zdroj",
  poznamka: "Poznámka",
};

/** Prázdný formulář pro zakládání. */
function prazdny(vychoziTyp) {
  return {
    typ: vychoziTyp,
    nazev: "",
    ico: "",
    dic: "",
    adresa_ulice: "",
    adresa_mesto: "",
    adresa_psc: "",
    adresa_stat: "Česko",
    gps_lat: "",
    gps_lng: "",
    web: "",
    telefon: "",
    email: "",
    zdroj: "",
    poznamka: "",
    vlastnik_user_id: null,
    spoluvlastnici: [],
    extra: {},
  };
}

/**
 * Formulář zákazníka v okně (zakládání i úprava).
 *
 * Dvě cesty v jednom okně, protože je to tentýž formulář:
 *  - **existující zákazník** (přišel `zakaznik` s `id`) se ukládá sám, pole po
 *    poli (`useZaznamAutosave`). Tlačítko „Uložit" tu proto není: posílalo celý
 *    objekt, takže dva lidé nad jednou firmou si navzájem přepsali i pole,
 *    kterých se ani nedotkli — a u vlastních polí (`extra`) chybějící klíč
 *    hodnotu rovnou smazal. „Hotovo" jen dožene poslední znaky a zavře okno;
 *  - **zakládání** jede po staru přes jeden požadavek. Autosave tu být NESMÍ:
 *    záznam ještě neexistuje, není co PATCHovat, a půl vyplněný zákazník by
 *    v seznamu vznikl už při psaní prvního slova.
 *
 * ARES: OZ zadá IČO, appka dotáhne název, DIČ a adresu z veřejného registru.
 * Selhání ARESu NIKDY neblokuje uložení – ukáže se varování a vyplní se ručně.
 * Zároveň se hlásí, jestli firmu s tímto IČO už nevedeme (i cizí záznam), aby
 * ji dva OZ nezaložili dvakrát.
 */
export default function ZakaznikFormular({
  zakaznik = null,
  vychoziTyp = "lead",
  muzeMenitVlastnika = false,
  onZavri,
  onHotovo,
}) {
  // Rozhoduje `id`, ne jen přítomnost objektu: bez id není co ukládat po polích.
  const jeUprava = Boolean(zakaznik?.id);
  // Stav pro ZAKLÁDÁNÍ. U existujícího záznamu se nepoužívá vůbec — hodnoty tam
  // drží `useZaznamAutosave` a dvě kopie téhož by se dřív nebo později rozešly.
  const [form, setForm] = useState(() => prazdny(vychoziTyp));
  const [lidi, setLidi] = useState([]);
  // Definice vlastních polí: u úpravy přijdou s detailem, u nového zákazníka
  // se musí dotáhnout zvlášť.
  const [vlastniPole, setVlastniPole] = useState(zakaznik?.vlastni_pole || []);
  const [aresStav, setAresStav] = useState(null); // {druh, zprava}
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  // Vlastní pole se dotahují až za běhu, takže seznam spravovaných klíčů roste.
  // Hook to zvládne (nové klíče si dopočítá ze záznamu), ale nesmí se přepočítat
  // při každém renderu — jinak by efekt uvnitř běžel pořád.
  const poleAutosave = useMemo(
    () => [...POLE, ...(vlastniPole || []).map((p) => `extra:${p.klic}`)],
    [vlastniPole],
  );

  const {
    hodnoty,
    zmen,
    stav,
    chyba: chybaUlozeni,
    kdy,
    pritomni,
    kolize,
    prepis,
    vezmiJejich,
    dokonci,
    onFokus,
    onBlur,
  } = useZaznamAutosave({
    entita: "zakaznik",
    id: zakaznik?.id ?? 0,
    zaznam: jeUprava ? zakaznik : null,
    pole: poleAutosave,
    entitaTyp: "crm_zakaznik",
    // Zakládání: nic se neukládá ani neohlašuje — záznam ještě neexistuje.
    zapnuto: jeUprava,
  });

  useEffect(() => {
    if (zakaznik?.vlastni_pole) return;
    crmVlastniPole("zakaznik")
      .then(setVlastniPole)
      .catch(() => setVlastniPole([]));
  }, [zakaznik]);

  useEffect(() => {
    if (!muzeMenitVlastnika || jeUprava) return;
    crmUzivatele()
      .then(setLidi)
      .catch(() => setLidi([]));
  }, [muzeMenitVlastnika, jeUprava]);

  // Zrcadla stavu pro `hotovo()` — viz komentář tam.
  const kolizeRef = useRef(kolize);
  kolizeRef.current = kolize;
  const stavRef = useRef(stav);
  stavRef.current = stav;

  /** Hodnota pole pro zobrazení: u úpravy z autosave, u zakládání z formuláře. */
  function v(klic) {
    return (jeUprava ? hodnoty[klic] : form[klic]) ?? "";
  }

  /** Zápis pole: u úpravy jde na server, u zakládání jen do formuláře. */
  function zapis(klic, hodnota, ihned = false) {
    if (jeUprava) zmen(klic, hodnota, ihned);
    else setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  // Hodnoty vlastních polí pro `VlastniPoleVstupy`. U úpravy se skládají
  // z autosave hodnot (`extra:<klic>`), aby existovala jediná pravda.
  const extraHodnoty = useMemo(() => {
    if (!jeUprava) return form.extra;
    const vysledek = {};
    (vlastniPole || []).forEach((p) => {
      const text = hodnoty[`extra:${p.klic}`] ?? "";
      // Zaškrtávátko se vrací na pravda/nepravda: podmíněná viditelnost polí
      // (CRM-33) porovnává hodnotu jako text, a „1“ by se s tím, co si admin
      // napsal do podmínky (a co porovnává backend), nepotkalo.
      vysledek[p.klic] = p.typ === "ano_ne" ? Boolean(text) : text;
    });
    return vysledek;
  }, [jeUprava, form.extra, vlastniPole, hodnoty]);

  async function dotahniZAresu() {
    setAresStav({ druh: "hledam", zprava: "Hledám v ARESu…" });
    try {
      const d = await crmAres(v("ico"));
      // Prázdná hodnota z registru NEMAŽE, co už je vyplněné — ARES nemusí mít
      // všechno (typicky DIČ u neplátce).
      const dotazene = {
        nazev: d.nazev,
        ico: d.ico,
        dic: d.dic,
        adresa_ulice: d.adresa_ulice,
        adresa_mesto: d.adresa_mesto,
        adresa_psc: d.adresa_psc,
        adresa_stat: d.adresa_stat,
      };
      if (jeUprava) {
        // Každé dotažené pole se ukládá vlastním požadavkem a HNED, ne pěti
        // nezávislými prodlevami: z registru přijde hotový údaj, ne rozepsaná
        // věta, a čekat na „dopsání“ by u pěti polí naráz znamenalo, že člověk
        // zavře okno dřív, než se stihnou odeslat.
        //
        // Jedno po druhém (`await`), ne všech pět naráz: odpověď na uložení
        // nese CELÝ záznam a hook z ní přebírá zbytek polí. Pět souběžných
        // požadavků by se mohlo vrátit v jiném pořadí, než odešly, a starší
        // odpověď by přepsala novější adresu zpátky na tu z registru před
        // chvílí. Kontrola kolizí tím netrpí — hodnoty se mění výhradně přes
        // `zmen`, takže si hook drží správné `puvodni` (to, co server naposledy
        // potvrdil) a souběh s cizí změnou pořád pozná.
        for (const [klic, hodnota] of Object.entries(dotazene)) {
          if (!hodnota || hodnota === hodnoty[klic]) continue;
          zmen(klic, hodnota);
          // `dokonci` čekající uložení vytlačí hned a vrátí promise, na kterou
          // se dá počkat — proto se tu nepoužívá `zmen(..., true)`.
          await dokonci(klic);
        }
      } else {
        setForm((f) => {
          const dalsi = { ...f };
          Object.entries(dotazene).forEach(([klic, hodnota]) => {
            if (hodnota) dalsi[klic] = hodnota;
          });
          return dalsi;
        });
      }
      if (d.duplikat_id) {
        setAresStav({
          druh: "varovani",
          zprava: `Pozor: firmu s tímto IČO už vedeme („${d.duplikat_nazev}"). Zkontroluj, ať nevznikne duplikát.`,
        });
      } else {
        setAresStav({ druh: "ok", zprava: "Údaje doplněny z ARESu." });
      }
    } catch (e) {
      setAresStav({ druh: "varovani", zprava: e.message });
    }
  }

  /** Zakládání: jeden požadavek, jeden záznam. */
  async function zaloz() {
    setUklada(true);
    setChyba(null);
    try {
      const data = {
        ...form,
        nazev: form.nazev.trim(),
        gps_lat: form.gps_lat.trim() === "" ? null : Number(form.gps_lat.replace(",", ".")),
        gps_lng: form.gps_lng.trim() === "" ? null : Number(form.gps_lng.replace(",", ".")),
      };
      onHotovo(await crmZakaznikZaloz(data));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  /** Konec úprav: dožene neodeslané změny a vrátí kartě čerstvá data. */
  async function hotovo() {
    if (kolize) {
      setChyba("Nejdřív rozhodni, čí hodnota u kolize platí — pak okno zavři.");
      return;
    }
    setUklada(true);
    setChyba(null);
    await dokonci();
    // Neuložený text nesmí zmizet se zavřeným oknem. Po `await` je stav
    // z renderu starý, proto se čte ze zrcadel.
    if (kolizeRef.current || stavRef.current === "chyba") {
      setChyba("Něco se neuložilo – okno nechávám otevřené, ať o text nepřijdeš.");
      setUklada(false);
      return;
    }
    // Server si za našimi zády dopočítává výpočtová vlastní pole, takže karta
    // potřebuje celý záznam, ne jen to, co jsme poslali. Když se dotažení
    // nepovede, okno se přesto zavře — data jsou uložená a karta si je natáhne
    // sama (razítko přítomnosti).
    const novy = await crmZakaznikDetail(zakaznik.id).catch(() => null);
    setUklada(false);
    if (novy) onHotovo(novy);
    else onZavri();
  }

  return (
    <div className="crm-okno-plast" onClick={jeUprava ? hotovo : onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? "Úprava zákazníka" : form.typ === "lead" ? "Nový lead" : "Nový klient"}</h2>
          <span className="crm-mezera" />
          {/* Kdo tuhle firmu edituje taky — ať se dva lidé nepotkají naslepo. */}
          <Pritomni pritomni={pritomni} popisekPole={(p) => NAZVY_POLI[p] || p} />
          <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
          <button className="crm-zavrit" onClick={jeUprava ? hotovo : onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          {/* IČO nahoře schválně: je to nejrychlejší cesta ke správným údajům. */}
          <div className="crm-ares">
            <div style={{ flex: "0 0 190px" }}>
              <label className="crm-label">IČO</label>
              <input
                className="crm-pole"
                value={v("ico")}
                onChange={(e) => zapis("ico", e.target.value)}
                onFocus={() => onFokus("ico")}
                onBlur={() => onBlur("ico")}
                placeholder="8 číslic"
                inputMode="numeric"
              />
            </div>
            <button
              className="fm-btn"
              onClick={dotahniZAresu}
              disabled={!v("ico").trim() || aresStav?.druh === "hledam"}
            >
              {aresStav?.druh === "hledam" ? "Hledám…" : "Doplnit z ARESu"}
            </button>
            {aresStav && aresStav.druh !== "hledam" && (
              <span className={aresStav.druh === "ok" ? "crm-ares-ok" : "crm-ares-varovani"}>
                {aresStav.zprava}
              </span>
            )}
          </div>

          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Název firmy *</label>
              <input
                className="crm-pole"
                value={v("nazev")}
                onChange={(e) => zapis("nazev", e.target.value)}
                onFocus={() => onFokus("nazev")}
                onBlur={() => onBlur("nazev")}
                placeholder="např. Firma s.r.o."
              />
              {/* U existujícího zákazníka se název nedá „zamknout“ — ukládá se za
                  pochodu, takže i prázdný stav je platný mezikrok. Jen se na něj
                  upozorní; při zakládání dál blokuje tlačítko. */}
              {jeUprava && !v("nazev").trim() && (
                <p className="crm-tise" style={{ color: "var(--st-crit)" }}>
                  Bez názvu firmu nikdo v seznamu nenajde.
                </p>
              )}
            </div>
            {/* Typ se dá vybrat jen při zakládání. Přepnutí lead → klient je
                vědomý krok s vedlejšími efekty (razítko konverze, jiný seznam),
                proto zůstává na tlačítku „Převést na klienta" na kartě. */}
            {!jeUprava && (
              <div>
                <label className="crm-label">Typ</label>
                <select
                  className="crm-pole"
                  value={form.typ}
                  onChange={(e) => zapis("typ", e.target.value)}
                >
                  <option value="lead">Lead</option>
                  <option value="klient">Klient</option>
                </select>
              </div>
            )}
            <div>
              <label className="crm-label">DIČ</label>
              <input
                className="crm-pole"
                value={v("dic")}
                onChange={(e) => zapis("dic", e.target.value)}
                onFocus={() => onFokus("dic")}
                onBlur={() => onBlur("dic")}
              />
            </div>
            <div className="crm-sirka2">
              <label className="crm-label">Ulice a číslo</label>
              <input
                className="crm-pole"
                value={v("adresa_ulice")}
                onChange={(e) => zapis("adresa_ulice", e.target.value)}
                onFocus={() => onFokus("adresa_ulice")}
                onBlur={() => onBlur("adresa_ulice")}
              />
            </div>
            <div>
              <label className="crm-label">Město</label>
              <input
                className="crm-pole"
                value={v("adresa_mesto")}
                onChange={(e) => zapis("adresa_mesto", e.target.value)}
                onFocus={() => onFokus("adresa_mesto")}
                onBlur={() => onBlur("adresa_mesto")}
              />
            </div>
            <div>
              <label className="crm-label">PSČ</label>
              <input
                className="crm-pole"
                value={v("adresa_psc")}
                onChange={(e) => zapis("adresa_psc", e.target.value)}
                onFocus={() => onFokus("adresa_psc")}
                onBlur={() => onBlur("adresa_psc")}
              />
            </div>
            <div>
              <label className="crm-label">Telefon</label>
              <input
                className="crm-pole"
                value={v("telefon")}
                onChange={(e) => zapis("telefon", e.target.value)}
                onFocus={() => onFokus("telefon")}
                onBlur={() => onBlur("telefon")}
              />
            </div>
            <div>
              <label className="crm-label">E-mail</label>
              <input
                className="crm-pole"
                value={v("email")}
                onChange={(e) => zapis("email", e.target.value)}
                onFocus={() => onFokus("email")}
                onBlur={() => onBlur("email")}
              />
            </div>
            <div>
              <label className="crm-label">Web</label>
              <input
                className="crm-pole"
                value={v("web")}
                onChange={(e) => zapis("web", e.target.value)}
                onFocus={() => onFokus("web")}
                onBlur={() => onBlur("web")}
              />
            </div>
            <div>
              <label className="crm-label">Zdroj (odkud lead přišel)</label>
              <input
                className="crm-pole"
                value={v("zdroj")}
                onChange={(e) => zapis("zdroj", e.target.value)}
                onFocus={() => onFokus("zdroj")}
                onBlur={() => onBlur("zdroj")}
                placeholder="doporučení, web, výstava…"
              />
            </div>
            {/* GPS se propíše do PPA výpočtu (poloha elektrárny). */}
            <div>
              <label className="crm-label">GPS šířka</label>
              <input
                className="crm-pole"
                value={v("gps_lat")}
                onChange={(e) => zapis("gps_lat", e.target.value)}
                onFocus={() => onFokus("gps_lat")}
                onBlur={() => onBlur("gps_lat")}
                placeholder="50.087"
                inputMode="decimal"
              />
            </div>
            <div>
              <label className="crm-label">GPS délka</label>
              <input
                className="crm-pole"
                value={v("gps_lng")}
                onChange={(e) => zapis("gps_lng", e.target.value)}
                onFocus={() => onFokus("gps_lng")}
                onBlur={() => onBlur("gps_lng")}
                placeholder="14.421"
                inputMode="decimal"
              />
            </div>

            {/* Vlastníka se při úpravě nemění: přehazuje viditelnost záznamu
                ostatním lidem, takže na to je hromadná akce v seznamu. */}
            {muzeMenitVlastnika && !jeUprava && (
              <div>
                <label className="crm-label">Vlastník záznamu</label>
                <select
                  className="crm-pole"
                  value={form.vlastnik_user_id || ""}
                  onChange={(e) =>
                    zapis("vlastnik_user_id", e.target.value ? Number(e.target.value) : null)
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
              <label className="crm-label">Poznámka</label>
              <textarea
                className="crm-pole"
                rows={3}
                value={v("poznamka")}
                onChange={(e) => zapis("poznamka", e.target.value)}
                onFocus={() => onFokus("poznamka")}
                onBlur={() => onBlur("poznamka")}
              />
            </div>

            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={extraHodnoty}
              // Úprava hlásí změnu po jednom poli (ukládá se samo), zakládání
              // předává celé `extra` — pošle se v jednom požadavku se záznamem.
              onZmena={jeUprava ? undefined : (extra) => setForm((f) => ({ ...f, extra }))}
              onZmenaPole={
                jeUprava
                  ? (klic, hodnota, ihned) => zmen(`extra:${klic}`, hodnota, ihned)
                  : undefined
              }
            />
          </div>

          {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. */}
          {kolize && (
            <div className="crm-kolize">
              <div>
                <strong>{NAZVY_POLI[kolize.pole] || kolize.pole}</strong> mezitím změnil
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

          {jeUprava && (
            <p className="crm-tise" style={{ marginTop: 10 }}>
              Typ (lead/klient) a vlastníka tady nezměníš: typ přehodíš tlačítkem „Převést na
              klienta“ na kartě, vlastníka hromadnou akcí v seznamu. Obojí sahá i na jiné
              záznamy, takže to nepatří na ukládání za pochodu.
            </p>
          )}

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          {jeUprava ? (
            <>
              <span className="crm-tise">Změny se ukládají samy, tlačítko jen zavře okno.</span>
              <span className="crm-mezera" />
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
                disabled={uklada || !form.nazev.trim()}
              >
                {uklada ? "Ukládám…" : "Založit"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
