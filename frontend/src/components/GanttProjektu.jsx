import { useMemo, useState } from "react";
import { fmtDatum } from "../crm";

/**
 * Ganttův diagram kroků projektu (CRM-21).
 *
 * Kroky už mají všechno potřebné — trvání (`delka_dni`), termín a návaznost
 * (`zavisi_na_id`) — takže se kreslí čistě z detailu projektu, bez dalšího
 * dotazu i bez knihovny. Pruhy jsou obyčejné divy v procentech, což zvládne
 * i tisk a tmavý režim; hotová knihovna by přinesla vlastní styly a další
 * 100 kB do balíku kvůli jedné obrazovce.
 *
 * ---- Kritická cesta ----
 * Řetěz kroků, který určuje, kdy projekt skončí: zpoždění kteréhokoli z nich
 * posune předání. Počítá se jako nejdelší cesta grafem závislostí — ne podle
 * termínů, ale podle **trvání**, protože termín se u ručně nastaveného kroku
 * může lišit od toho, co plyne z návazností.
 *
 * Kroky bez termínu se nekreslí (nemají kde začít) a je to napsané nahlas —
 * tiché vynechání by vypadalo, že projekt má míň práce, než má.
 */

const DEN_MS = 86400000;

function den(iso) {
  if (!iso) return null;
  const d = new Date(`${String(iso).slice(0, 10)}T12:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Kroky na kritické cestě (množina id). */
function kritickaCesta(kroky) {
  const podleId = new Map(kroky.map((k) => [k.id, k]));
  const delkaDo = new Map(); // id → celková délka řetězu končícího tímhle krokem
  const predchudce = new Map();

  function spocti(k, navstivene = new Set()) {
    if (delkaDo.has(k.id)) return delkaDo.get(k.id);
    // Pojistka proti kruhu v datech: bez ní by se funkce zacyklila.
    if (navstivene.has(k.id)) return 0;
    navstivene.add(k.id);

    const rodic = k.zavisi_na_id ? podleId.get(k.zavisi_na_id) : null;
    const zaklad = rodic ? spocti(rodic, navstivene) : 0;
    const celkem = zaklad + Math.max(1, k.delka_dni || 1);
    delkaDo.set(k.id, celkem);
    if (rodic) predchudce.set(k.id, rodic.id);
    return celkem;
  }

  kroky.forEach((k) => spocti(k));
  if (delkaDo.size === 0) return new Set();

  let konec = null;
  let nejdelsi = -1;
  for (const [id, delka] of delkaDo) {
    if (delka > nejdelsi) {
      nejdelsi = delka;
      konec = id;
    }
  }
  const cesta = new Set();
  let kurzor = konec;
  while (kurzor != null && !cesta.has(kurzor)) {
    cesta.add(kurzor);
    kurzor = predchudce.get(kurzor);
  }
  return cesta;
}

export default function GanttProjektu({ projekt }) {
  const [otevreno, setOtevreno] = useState(false);
  const kroky = useMemo(() => projekt?.kroky || [], [projekt]);

  const model = useMemo(() => {
    const sTerminem = kroky.filter((k) => den(k.termin));
    if (sTerminem.length === 0) return null;

    const pruhy = sTerminem.map((k) => {
      const konec = den(k.termin);
      const delka = Math.max(1, k.delka_dni || 1);
      const zacatek = new Date(konec.getTime() - (delka - 1) * DEN_MS);
      return { krok: k, zacatek, konec, delka };
    });

    // Osa: od nejstaršího začátku po nejzazší konec, zarovnaná na celé dny.
    const od = new Date(Math.min(...pruhy.map((p) => p.zacatek.getTime())));
    const do_ = new Date(Math.max(...pruhy.map((p) => p.konec.getTime())));
    const dniCelkem = Math.max(1, Math.round((do_ - od) / DEN_MS) + 1);

    const kriticke = kritickaCesta(sTerminem);
    const dnes = new Date();
    const dnesProcent = ((dnes - od) / DEN_MS / dniCelkem) * 100;

    return {
      pruhy: pruhy.map((p) => ({
        ...p,
        vlevo: (Math.round((p.zacatek - od) / DEN_MS) / dniCelkem) * 100,
        sirka: (p.delka / dniCelkem) * 100,
        kriticky: kriticke.has(p.krok.id),
      })),
      od,
      do: do_,
      dniCelkem,
      dnesProcent: dnesProcent >= 0 && dnesProcent <= 100 ? dnesProcent : null,
      bezTerminu: kroky.length - sTerminem.length,
      kritickychDni: kriticke.size
        ? sTerminem
            .filter((k) => kriticke.has(k.id))
            .reduce((a, k) => a + Math.max(1, k.delka_dni || 1), 0)
        : 0,
    };
  }, [kroky]);

  if (kroky.length === 0) return null;

  return (
    <details
      className="fm-card crm-blok crm-gantt"
      open={otevreno}
      onToggle={(e) => setOtevreno(e.currentTarget.open)}
    >
      <summary>
        Časová osa
        <span className="crm-tise"> — kroky v čase a kritická cesta</span>
      </summary>

      <div className="crm-gantt-telo">
        {!model ? (
          <p className="crm-tise">
            Kroky zatím nemají termíny. Termín se dopočítá ze zahájení projektu a délky
            kroků — vyplň zahájení na kartě projektu.
          </p>
        ) : (
          <>
            <p className="crm-tise crm-gantt-legenda">
              <span className="crm-gantt-vzorek kriticky" /> kritická cesta ({model.kritickychDni}{" "}
              dní) — zpoždění kteréhokoli z těchhle kroků posune předání
              {"  ·  "}
              <span className="crm-gantt-vzorek hotovy" /> hotovo
              {model.bezTerminu > 0 && (
                <>
                  {"  ·  "}
                  <b>{model.bezTerminu}</b> {model.bezTerminu === 1 ? "krok" : "kroky"} bez
                  termínu se nekreslí
                </>
              )}
            </p>

            <div className="crm-gantt-osa">
              <span>{fmtDatum(model.od.toISOString())}</span>
              <span className="crm-mezera" />
              <span>{model.dniCelkem} dní</span>
              <span className="crm-mezera" />
              <span>{fmtDatum(model.do.toISOString())}</span>
            </div>

            <div className="crm-gantt-mrizka">
              {model.pruhy.map((p) => {
                const hotovy = Boolean(p.krok.hotovo_at);
                return (
                  <div key={p.krok.id} className="crm-gantt-radek">
                    <span className="crm-gantt-nazev" title={p.krok.nazev}>
                      {p.krok.nazev}
                    </span>
                    <span className="crm-gantt-plocha">
                      {model.dnesProcent !== null && (
                        <span
                          className="crm-gantt-dnes"
                          style={{ left: `${model.dnesProcent}%` }}
                          title="Dnes"
                        />
                      )}
                      <span
                        className={`crm-gantt-pruh${p.kriticky ? " kriticky" : ""}${
                          hotovy ? " hotovy" : ""
                        }${p.krok.po_terminu && !hotovy ? " po-terminu" : ""}`}
                        style={{ left: `${p.vlevo}%`, width: `${p.sirka}%` }}
                        title={`${p.krok.nazev}: ${fmtDatum(p.zacatek.toISOString())} – ${fmtDatum(
                          p.konec.toISOString()
                        )} (${p.delka} dní)`}
                      >
                        <span className="crm-gantt-popisek">{p.delka} d</span>
                      </span>
                    </span>
                    <span className="crm-gantt-termin">{fmtDatum(p.krok.termin)}</span>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </details>
  );
}
