import { useEffect, useState } from "react";
import {
  crmVlastniPole,
  crmVlastniPolePoradi,
  crmVlastniPolePridej,
  crmVlastniPoleSmaz,
  crmVlastniPoleUprav,
} from "../api";

const TYPY = [
  { klic: "text", nazev: "Text (jeden řádek)" },
  { klic: "dlouhy_text", nazev: "Delší text" },
  { klic: "cislo", nazev: "Číslo" },
  { klic: "datum", nazev: "Datum" },
  { klic: "ano_ne", nazev: "Ano / ne" },
  { klic: "vyber", nazev: "Výběr ze seznamu" },
];

const PRAZDNE = {
  skupina: "",
  zavislost_pole: "",
  zavislost_hodnota: "",
  vzorec: "",
  nazev: "",
  typ: "text",
  volby: "",
  napoveda: "",
  povinne: false,
  v_seznamu: false,
};

/**
 * Správa vlastních polí jedné obrazovky (jen právo `crm_nastaveni`).
 *
 * Pole se přidávají za běhu, bez migrace a nasazení — proto se hodnoty ukládají
 * do JSONB. Smazání pole hodnoty nemaže, jen je přestane zobrazovat; backend
 * po smazání vrátí, kolika záznamů se to týkalo, a my to řekneme nahlas.
 */
export default function VlastniPoleNastaveni({ entita, nazevObrazovky, onZavri, onZmena }) {
  const [pole, setPole] = useState(null);
  const [novy, setNovy] = useState(PRAZDNE);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);

  async function nacti() {
    setPole(await crmVlastniPole(entita));
  }

  useEffect(() => {
    crmVlastniPole(entita)
      .then(setPole)
      .catch((e) => setChyba(e.message));
  }, [entita]);

  function volbyNaPole(text) {
    // Volby píše admin po řádcích — je to čitelnější než čárkami u delších názvů.
    return String(text || "")
      .split("\n")
      .map((v) => v.trim())
      .filter(Boolean);
  }

  async function pridej() {
    if (!novy.nazev.trim()) return;
    setChyba(null);
    setZprava(null);
    try {
      await crmVlastniPolePridej(entita, {
        nazev: novy.nazev.trim(),
        typ: novy.typ,
        volby: volbyNaPole(novy.volby),
        napoveda: novy.napoveda.trim(),
        povinne: novy.povinne,
        v_seznamu: novy.v_seznamu,
        skupina: novy.skupina.trim(),
        zavislost_pole: novy.zavislost_pole.trim(),
        zavislost_hodnota: novy.zavislost_hodnota.trim(),
        vzorec: novy.vzorec.trim(),
      });
      setNovy(PRAZDNE);
      await nacti();
      onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function uprav(p, zmeny) {
    setChyba(null);
    try {
      await crmVlastniPoleUprav(p.id, zmeny);
      await nacti();
      onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function posun(index, o) {
    const nove = [...pole];
    const cil = index + o;
    if (cil < 0 || cil >= nove.length) return;
    [nove[index], nove[cil]] = [nove[cil], nove[index]];
    try {
      await crmVlastniPolePoradi(
        entita,
        nove.map((p) => p.id)
      );
      await nacti();
      onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(p) {
    if (
      !window.confirm(
        `Smazat pole „${p.nazev}"? Vyplněné hodnoty se nesmažou, jen se přestanou zobrazovat — když pole založíš znovu pod stejným názvem, vrátí se.`
      )
    )
      return;
    setChyba(null);
    try {
      const r = await crmVlastniPoleSmaz(p.id);
      await nacti();
      onZmena?.();
      setZprava(
        r.zaznamu_s_hodnotou > 0
          ? `Pole „${p.nazev}" smazáno. Hodnotu mělo vyplněnou ${r.zaznamu_s_hodnotou} záznamů — data zůstala uložená.`
          : `Pole „${p.nazev}" smazáno.`
      );
    } catch (e) {
      setChyba(e.message);
    }
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Vlastní pole — {nazevObrazovky}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ✕
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Pole, která si přidáš, se objeví ve formuláři i v detailu záznamu. Hodnoty se
            ukládají ke každému záznamu zvlášť. <b>Název</b> se dá kdykoli přejmenovat;
            vnitřní klíč zůstává, takže o vyplněná data nepřijdeš.
          </p>

          {pole === null ? null : pole.length === 0 ? (
            <div className="crm-prazdno">Zatím žádné vlastní pole.</div>
          ) : (
            <table className="crm-tabulka crm-tabulka-hustá">
              <thead>
                <tr>
                  <th>Název</th>
                  <th>Typ</th>
                  <th>Povinné</th>
                  <th>V seznamu</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pole.map((p, i) => (
                  <tr key={p.id}>
                    <td>
                      <input
                        className="crm-pole"
                        defaultValue={p.nazev}
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          if (v && v !== p.nazev) uprav(p, { nazev: v });
                        }}
                      />
                      {p.napoveda && <div className="crm-tise">{p.napoveda}</div>}
                      {p.typ === "vyber" && (
                        <div className="crm-tise">volby: {(p.volby || []).join(", ")}</div>
                      )}
                    </td>
                    <td>
                      <select
                        className="crm-pole crm-pole-uzke"
                        value={p.typ}
                        onChange={(e) => uprav(p, { typ: e.target.value })}
                      >
                        {TYPY.map((t) => (
                          <option key={t.klic} value={t.klic}>
                            {t.nazev}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={p.povinne}
                        onChange={(e) => uprav(p, { povinne: e.target.checked })}
                        aria-label={`${p.nazev} je povinné`}
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={p.v_seznamu}
                        onChange={(e) => uprav(p, { v_seznamu: e.target.checked })}
                        aria-label={`${p.nazev} zobrazit v seznamu`}
                        title="Zobrazit jako sloupec v tabulce"
                      />
                    </td>
                    <td className="crm-vpravo">
                      <button
                        className="fm-btn crm-btn-maly"
                        onClick={() => posun(i, -1)}
                        disabled={i === 0}
                        title="Posunout výš"
                      >
                        ↑
                      </button>
                      <button
                        className="fm-btn crm-btn-maly"
                        onClick={() => posun(i, 1)}
                        disabled={i === pole.length - 1}
                        title="Posunout níž"
                      >
                        ↓
                      </button>
                      <button
                        className="fm-btn crm-btn-maly crm-btn-smazat"
                        onClick={() => smaz(p)}
                        title="Smazat pole"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 style={{ marginTop: 20 }}>Přidat pole</h3>
          <div className="crm-mrizka">
            <div className="crm-sirka2">
              <label className="crm-label">Název *</label>
              <input
                className="crm-pole"
                value={novy.nazev}
                onChange={(e) => setNovy((n) => ({ ...n, nazev: e.target.value }))}
                placeholder="např. Číslo odběrného místa"
              />
            </div>
            <div>
              <label className="crm-label">Typ</label>
              <select
                className="crm-pole"
                value={novy.typ}
                onChange={(e) => setNovy((n) => ({ ...n, typ: e.target.value }))}
              >
                {TYPY.map((t) => (
                  <option key={t.klic} value={t.klic}>
                    {t.nazev}
                  </option>
                ))}
              </select>
            </div>
            {novy.typ === "vyber" && (
              <div className="crm-sirka3">
                <label className="crm-label">Volby (jedna na řádek)</label>
                <textarea
                  className="crm-pole"
                  rows={3}
                  value={novy.volby}
                  onChange={(e) => setNovy((n) => ({ ...n, volby: e.target.value }))}
                  placeholder={"NN\nVN\nVVN"}
                />
              </div>
            )}
            <div>
              <label className="crm-label">Skupina (nepovinné)</label>
              <input
                className="crm-pole"
                value={novy.skupina}
                onChange={(e) => setNovy((n) => ({ ...n, skupina: e.target.value }))}
                placeholder="např. Technické údaje"
              />
              <p className="crm-tise crm-napoveda">
                Pole se stejnou skupinou se na kartě zobrazí pod společným nadpisem.
              </p>
            </div>

            <div>
              <label className="crm-label">Vzorec (nepovinné)</label>
              <input
                className="crm-pole"
                value={novy.vzorec}
                onChange={(e) => setNovy((n) => ({ ...n, vzorec: e.target.value }))}
                placeholder="např. cena_kc - nakup"
              />
              <p className="crm-tise crm-napoveda">
                Když vyplníš, pole se nevyplňuje ručně, ale <b>počítá</b> — z čísel a jiných
                číselných polí, znaky + − * / a závorky. Výsledek se přepočítá při každém
                zobrazení, takže nezastará.
              </p>
            </div>

            <div>
              <label className="crm-label">Ukázat, jen když… (nepovinné)</label>
              <div className="crm-filtr-rozsah">
                <input
                  className="crm-pole"
                  value={novy.zavislost_pole}
                  onChange={(e) => setNovy((n) => ({ ...n, zavislost_pole: e.target.value }))}
                  placeholder="pole (např. kategorie)"
                />
                <input
                  className="crm-pole"
                  value={novy.zavislost_hodnota}
                  onChange={(e) => setNovy((n) => ({ ...n, zavislost_hodnota: e.target.value }))}
                  placeholder="má hodnotu (např. ppa)"
                />
              </div>
              <p className="crm-tise crm-napoveda">
                Necháš-li prázdné, pole je vidět vždycky. Skryté pole se nevyžaduje, ani když
                je označené jako povinné.
              </p>
            </div>

            <div className="crm-sirka2">
              <label className="crm-label">Nápověda pod polem (nepovinné)</label>
              <input
                className="crm-pole"
                value={novy.napoveda}
                onChange={(e) => setNovy((n) => ({ ...n, napoveda: e.target.value }))}
                placeholder="Krátké vysvětlení, odkud údaj vzít"
              />
            </div>
            <div>
              <label className="crm-zaskrtavaci">
                <input
                  type="checkbox"
                  checked={novy.povinne}
                  onChange={(e) => setNovy((n) => ({ ...n, povinne: e.target.checked }))}
                />
                Povinné
              </label>
              <label className="crm-zaskrtavaci">
                <input
                  type="checkbox"
                  checked={novy.v_seznamu}
                  onChange={(e) => setNovy((n) => ({ ...n, v_seznamu: e.target.checked }))}
                />
                Zobrazit i v seznamu
              </label>
            </div>
          </div>

          {zprava && <div className="crm-zprava">{zprava}</div>}
          {chyba && <div className="crm-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn fm-primary" onClick={pridej} disabled={!novy.nazev.trim()}>
            Přidat pole
          </button>
          <span className="crm-mezera" />
          <button className="fm-btn" onClick={onZavri}>
            Hotovo
          </button>
        </div>
      </div>
    </div>
  );
}
