import { useEffect, useRef, useState } from "react";
import { useAutosave } from "../hooks/useAutosave";
import Pritomni from "./Pritomni";
import StavUlozeni from "./StavUlozeni";

const poleStyl = {
  width: "100%",
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
  fontFamily: "inherit",
};

const labelStyl = { display: "block", fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 4 };

const POLE = ["stav", "termin", "osoba", "poznamka"];

const NAZVY_POLI = {
  stav: "Stav",
  termin: "Termín",
  osoba: "Odpovědná osoba",
  poznamka: "Poznámka",
};

// Popisky hodnot pro hlášku o kolizi – „done" nikomu nic neřekne.
const POPIS_STAVU = { "": "prázdné", done: "Hotovo", todo: "Nehotovo" };

function zBunky(bunka) {
  return {
    stav: bunka?.stav || "",
    termin: bunka?.termin || "",
    osoba: bunka?.osoba || "",
    poznamka: bunka?.poznamka || "",
  };
}

function popisHodnoty(pole, hodnota) {
  if (!hodnota) return "prázdné";
  if (pole === "stav") return POPIS_STAVU[hodnota] || hodnota;
  return hodnota;
}

/**
 * Editace buňky matice s automatickým ukládáním.
 *
 * Tlačítko „Uložit" tu schválně není: každé pole se ukládá samo, a to zvlášť.
 * Dřív se posílala celá buňka naráz, takže kdo měl otevřený popup a uložil,
 * přepsal i pole, kterých se nedotkl – včetně cizí poznámky, tiše.
 *
 * Dvě pravidla, bez kterých by automatické ukládání škodilo:
 *  1) pole, ve kterém člověk právě píše (nebo má nedoručenou změnu), se
 *     aktualizací ze serveru NIKDY nepřepíše – jinak by mu text mizel pod rukama;
 *  2) když server ohlásí kolizi (409), nic se nepřepíše a člověk dostane na
 *     výběr, čí hodnota platí.
 */
export default function BunkaDialog({
  projektNazev,
  ukolNazev,
  bunka,
  pritomni = [],
  onUlozPole,
  onClose,
}) {
  const [hodnoty, setHodnoty] = useState(() => zBunky(bunka));
  // Co server naposledy potvrdil – posílá se jako `puvodni`, aby poznal, že
  // do pole mezitím zapsal někdo jiný.
  const serverRef = useRef(zBunky(bunka));
  const fokusRef = useRef("");
  const rozepsaneRef = useRef(new Set());
  const [kolize, setKolize] = useState(null);

  const autosave = useAutosave(async (pole, { hodnota, puvodni }) => {
    try {
      await onUlozPole(pole, hodnota, puvodni);
      serverRef.current = { ...serverRef.current, [pole]: hodnota };
      rozepsaneRef.current.delete(pole);
    } catch (e) {
      if (e?.status === 409) {
        // Kolizi ukážeme a hlásíme i jako neuloženo – protože uloženo NENÍ.
        setKolize({
          pole,
          moje: hodnota,
          aktualni: e.data?.aktualni ?? "",
          kdo: e.data?.kdo || "",
          kdy: e.data?.kdy || null,
        });
        throw new Error("Neuloženo – mezitím to změnil někdo jiný.");
      }
      throw e;
    }
  });

  // Aktualizace ze serveru (poslal ji polling). Pole, které má člověk pod
  // rukama, zůstává nedotčené – i jeho `puvodni`, aby se kolize poznala.
  useEffect(() => {
    const nove = zBunky(bunka);
    setHodnoty((stare) => {
      const vysledek = { ...stare };
      POLE.forEach((p) => {
        if (fokusRef.current === p || rozepsaneRef.current.has(p)) return;
        vysledek[p] = nove[p];
      });
      return vysledek;
    });
    POLE.forEach((p) => {
      if (fokusRef.current === p || rozepsaneRef.current.has(p)) return;
      serverRef.current = { ...serverRef.current, [p]: nove[p] };
    });
  }, [bunka]);

  function zmen(pole, hodnota, ihned = false) {
    rozepsaneRef.current.add(pole);
    setHodnoty((h) => ({ ...h, [pole]: hodnota }));
    const argument = { hodnota, puvodni: serverRef.current[pole] };
    // Výběr ze seznamu a datum jsou hotová rozhodnutí, ne rozepsaný text –
    // nemá smysl u nich čekat na prodlevu.
    if (ihned) autosave.hned(pole, argument);
    else autosave.naplanuj(pole, argument);
  }

  async function zavri() {
    // Čekající změny musí odejít, jinak by zavření popupu zahodilo posledních
    // pár napsaných znaků.
    const cekajici = [...rozepsaneRef.current];
    fokusRef.current = "";
    await Promise.allSettled(
      cekajici.map((pole) =>
        autosave.hned(pole, { hodnota: hodnoty[pole], puvodni: serverRef.current[pole] })
      )
    );
    onClose();
  }

  function prepis() {
    // Člověk viděl cizí hodnotu a přesto chce svou → uložíme bez kontroly.
    const pole = kolize.pole;
    setKolize(null);
    autosave.hned(pole, { hodnota: kolize.moje, puvodni: null });
  }

  function vezmiJejich() {
    const { pole, aktualni } = kolize;
    setKolize(null);
    rozepsaneRef.current.delete(pole);
    serverRef.current = { ...serverRef.current, [pole]: aktualni };
    setHodnoty((h) => ({ ...h, [pole]: aktualni }));
  }

  const naBunce = pritomni.filter((p) => !p.ja);

  return (
    <div
      onClick={zavri}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(31,41,51,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: 16,
      }}
    >
      <div
        className="fm-card"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") zavri();
        }}
        style={{ padding: 20, width: "min(440px, 100%)", display: "flex", flexDirection: "column", gap: 12 }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <h3 style={{ margin: "0 0 2px", fontSize: 15 }}>{ukolNazev}</h3>
            <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>{projektNazev}</div>
          </div>
          {/* Kdo má tuhle buňku otevřenou taky – ať je vidět, s kým se člověk
              může potkat, ještě než napíše první znak. */}
          <Pritomni pritomni={naBunce} />
        </div>

        <div>
          <label style={labelStyl}>Stav</label>
          <select
            style={poleStyl}
            value={hodnoty.stav}
            onFocus={() => (fokusRef.current = "stav")}
            onBlur={() => (fokusRef.current = "")}
            onChange={(e) => zmen("stav", e.target.value, true)}
          >
            <option value="">— (prázdné / neexistuje)</option>
            <option value="todo">Nehotovo</option>
            <option value="done">Hotovo</option>
          </select>
        </div>

        <div>
          <label style={labelStyl}>Termín</label>
          <input
            type="date"
            style={poleStyl}
            value={hodnoty.termin || ""}
            onFocus={() => (fokusRef.current = "termin")}
            onBlur={() => (fokusRef.current = "")}
            onChange={(e) => zmen("termin", e.target.value, true)}
          />
        </div>

        <div>
          <label style={labelStyl}>Odpovědná osoba</label>
          <input
            type="text"
            style={poleStyl}
            value={hodnoty.osoba}
            placeholder="jméno"
            onFocus={() => (fokusRef.current = "osoba")}
            onBlur={() => (fokusRef.current = "")}
            onChange={(e) => zmen("osoba", e.target.value)}
          />
        </div>

        <div>
          <label style={labelStyl}>Poznámka</label>
          <textarea
            rows={5}
            style={{ ...poleStyl, resize: "vertical" }}
            value={hodnoty.poznamka}
            placeholder="Napiš poznámku…"
            onFocus={() => (fokusRef.current = "poznamka")}
            onBlur={() => (fokusRef.current = "")}
            onChange={(e) => zmen("poznamka", e.target.value)}
          />
        </div>

        {bunka?.url && (
          <div style={{ fontSize: 12 }}>
            <a href={bunka.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--fm-brand-dk)" }}>
              Otevřít úkol ve Freelu ↗
            </a>
          </div>
        )}

        {kolize && (
          <div
            style={{
              border: "1px solid var(--st-crit)",
              borderRadius: 8,
              padding: 10,
              fontSize: 13,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <div>
              <strong>{NAZVY_POLI[kolize.pole] || kolize.pole}</strong> mezitím změnil
              {kolize.kdo ? ` ${kolize.kdo}` : " někdo jiný"} na{" "}
              <strong>{popisHodnoty(kolize.pole, kolize.aktualni)}</strong>.
              <br />
              Ty píšeš <strong>{popisHodnoty(kolize.pole, kolize.moje)}</strong>.
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

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
            marginTop: 4,
          }}
        >
          <StavUlozeni stav={autosave.stav} chyba={autosave.chyba} kdy={autosave.kdy} />
          <button className="fm-btn" onClick={zavri}>
            Hotovo
          </button>
        </div>
        <div style={{ fontSize: 11, color: "var(--fm-muted)" }}>
          Změny se ukládají samy, tlačítko jen zavře okno.
        </div>
      </div>
    </div>
  );
}
