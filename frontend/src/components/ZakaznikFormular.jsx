import { useEffect, useState } from "react";
import { crmAres, crmUzivatele, crmVlastniPole, crmZakaznikUprav, crmZakaznikZaloz } from "../api";
import VlastniPoleVstupy from "./VlastniPoleVstupy";

/**
 * Formulář zákazníka v okně (zakládání i úprava).
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
  const jeUprava = Boolean(zakaznik);
  const [form, setForm] = useState(() => ({
    typ: zakaznik?.typ || vychoziTyp,
    nazev: zakaznik?.nazev || "",
    ico: zakaznik?.ico || "",
    dic: zakaznik?.dic || "",
    adresa_ulice: zakaznik?.adresa_ulice || "",
    adresa_mesto: zakaznik?.adresa_mesto || "",
    adresa_psc: zakaznik?.adresa_psc || "",
    adresa_stat: zakaznik?.adresa_stat || "Česko",
    gps_lat: zakaznik?.gps_lat != null ? String(zakaznik.gps_lat) : "",
    gps_lng: zakaznik?.gps_lng != null ? String(zakaznik.gps_lng) : "",
    web: zakaznik?.web || "",
    telefon: zakaznik?.telefon || "",
    email: zakaznik?.email || "",
    zdroj: zakaznik?.zdroj || "",
    poznamka: zakaznik?.poznamka || "",
    vlastnik_user_id: zakaznik?.vlastnik_user_id || null,
    spoluvlastnici: zakaznik?.spoluvlastnici || [],
    extra: zakaznik?.extra || {},
  }));
  const [lidi, setLidi] = useState([]);
  // Definice vlastních polí: u úpravy přijdou s detailem, u nového zákazníka
  // se musí dotáhnout zvlášť.
  const [vlastniPole, setVlastniPole] = useState(zakaznik?.vlastni_pole || []);
  const [aresStav, setAresStav] = useState(null); // {druh, zprava}
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    if (zakaznik?.vlastni_pole) return;
    crmVlastniPole("zakaznik")
      .then(setVlastniPole)
      .catch(() => setVlastniPole([]));
  }, [zakaznik]);

  useEffect(() => {
    if (!muzeMenitVlastnika) return;
    crmUzivatele()
      .then(setLidi)
      .catch(() => setLidi([]));
  }, [muzeMenitVlastnika]);

  function zmen(klic, hodnota) {
    setForm((f) => ({ ...f, [klic]: hodnota }));
  }

  async function dotahniZAresu() {
    setAresStav({ druh: "hledam", zprava: "Hledám v ARESu…" });
    try {
      const d = await crmAres(form.ico);
      setForm((f) => ({
        ...f,
        nazev: d.nazev || f.nazev,
        ico: d.ico || f.ico,
        dic: d.dic || f.dic,
        adresa_ulice: d.adresa_ulice || f.adresa_ulice,
        adresa_mesto: d.adresa_mesto || f.adresa_mesto,
        adresa_psc: d.adresa_psc || f.adresa_psc,
        adresa_stat: d.adresa_stat || f.adresa_stat,
      }));
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

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      const data = {
        ...form,
        nazev: form.nazev.trim(),
        gps_lat: form.gps_lat.trim() === "" ? null : Number(form.gps_lat.replace(",", ".")),
        gps_lng: form.gps_lng.trim() === "" ? null : Number(form.gps_lng.replace(",", ".")),
      };
      const vysledek = jeUprava
        ? await crmZakaznikUprav(zakaznik.id, data)
        : await crmZakaznikZaloz(data);
      onHotovo(vysledek);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>{jeUprava ? "Úprava zákazníka" : form.typ === "lead" ? "Nový lead" : "Nový klient"}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
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
                value={form.ico}
                onChange={(e) => zmen("ico", e.target.value)}
                placeholder="8 číslic"
                inputMode="numeric"
              />
            </div>
            <button
              className="fm-btn"
              onClick={dotahniZAresu}
              disabled={!form.ico.trim() || aresStav?.druh === "hledam"}
            >
              {aresStav?.druh === "hledam" ? "Hledám…" : "Doplnit z ARESu"}
            </button>
            {aresStav && aresStav.druh !== "hledam" && (
              <span
                className={aresStav.druh === "ok" ? "crm-ares-ok" : "crm-ares-varovani"}
              >
                {aresStav.zprava}
              </span>
            )}
          </div>

          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Název firmy *</label>
              <input
                className="crm-pole"
                value={form.nazev}
                onChange={(e) => zmen("nazev", e.target.value)}
                placeholder="např. Firma s.r.o."
              />
            </div>
            <div>
              <label className="crm-label">Typ</label>
              <select
                className="crm-pole"
                value={form.typ}
                onChange={(e) => zmen("typ", e.target.value)}
              >
                <option value="lead">Lead</option>
                <option value="klient">Klient</option>
              </select>
            </div>
            <div>
              <label className="crm-label">DIČ</label>
              <input
                className="crm-pole"
                value={form.dic}
                onChange={(e) => zmen("dic", e.target.value)}
              />
            </div>
            <div className="crm-sirka2">
              <label className="crm-label">Ulice a číslo</label>
              <input
                className="crm-pole"
                value={form.adresa_ulice}
                onChange={(e) => zmen("adresa_ulice", e.target.value)}
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
              <label className="crm-label">PSČ</label>
              <input
                className="crm-pole"
                value={form.adresa_psc}
                onChange={(e) => zmen("adresa_psc", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Telefon</label>
              <input
                className="crm-pole"
                value={form.telefon}
                onChange={(e) => zmen("telefon", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">E-mail</label>
              <input
                className="crm-pole"
                value={form.email}
                onChange={(e) => zmen("email", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Web</label>
              <input
                className="crm-pole"
                value={form.web}
                onChange={(e) => zmen("web", e.target.value)}
              />
            </div>
            <div>
              <label className="crm-label">Zdroj (odkud lead přišel)</label>
              <input
                className="crm-pole"
                value={form.zdroj}
                onChange={(e) => zmen("zdroj", e.target.value)}
                placeholder="doporučení, web, výstava…"
              />
            </div>
            {/* GPS se propíše do PPA výpočtu (poloha elektrárny). */}
            <div>
              <label className="crm-label">GPS šířka</label>
              <input
                className="crm-pole"
                value={form.gps_lat}
                onChange={(e) => zmen("gps_lat", e.target.value)}
                placeholder="50.087"
                inputMode="decimal"
              />
            </div>
            <div>
              <label className="crm-label">GPS délka</label>
              <input
                className="crm-pole"
                value={form.gps_lng}
                onChange={(e) => zmen("gps_lng", e.target.value)}
                placeholder="14.421"
                inputMode="decimal"
              />
            </div>

            {muzeMenitVlastnika && (
              <div>
                <label className="crm-label">Vlastník záznamu</label>
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
              <label className="crm-label">Poznámka</label>
              <textarea
                className="crm-pole"
                rows={3}
                value={form.poznamka}
                onChange={(e) => zmen("poznamka", e.target.value)}
              />
            </div>

            <VlastniPoleVstupy
              pole={vlastniPole}
              hodnoty={form.extra}
              onZmena={(extra) => zmen("extra", extra)}
            />
          </div>

          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            onClick={uloz}
            disabled={uklada || !form.nazev.trim()}
          >
            {uklada ? "Ukládám…" : jeUprava ? "Uložit změny" : "Založit"}
          </button>
        </div>
      </div>
    </div>
  );
}
