import { useEffect, useState } from "react";
import {
  crmFakturaPridej,
  crmFakturaSmaz,
  crmFakturaUprav,
  crmFakturyPrepocitat,
  crmFakturyZeSablony,
  crmObjednavkaFaktury,
  crmSplatkoveSablony,
} from "../api";

// Fakturace CRM objednávky – řetěz objednávka → faktura → zaplaceno (CRM-09).
//
// Faktury žijí v téže tabulce jako faktury Freelo projektů v Přehledu financí,
// jen mají jiného rodiče. Editují se ale jen tady, na kartě objednávky, kde
// platí práva CRM – v Přehledu financí jsou pro čtení.

const STAVY = [
  { klic: "potreba_vystavit", nazev: "Potřeba vystavit" },
  { klic: "vystaveno", nazev: "Vystaveno" },
  { klic: "zaplaceno", nazev: "Zaplaceno" },
  { klic: "nefakturuje", nazev: "Nefakturuje se" },
];

function kc(v) {
  return v == null ? "—" : `${Math.round(v).toLocaleString("cs-CZ")} Kč`;
}

function fmtDatum(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${Number(m[3])}. ${Number(m[2])}. ${m[1]}` : "";
}

export default function FakturacePanel({ objednavkaId, onZmena }) {
  const [data, setData] = useState(null);
  const [sablony, setSablony] = useState([]);
  const [sablona, setSablona] = useState("");
  const [prvniTermin, setPrvniTermin] = useState("");
  const [chyba, setChyba] = useState(null);
  const [pracuje, setPracuje] = useState(false);

  useEffect(() => {
    crmObjednavkaFaktury(objednavkaId).then(setData).catch((e) => setChyba(e.message));
    crmSplatkoveSablony().then(setSablony).catch(() => setSablony([]));
  }, [objednavkaId]);

  async function proved(akce) {
    setPracuje(true);
    setChyba(null);
    try {
      setData(await akce());
      await onZmena?.();
    } catch (e) {
      setChyba(e.message);
    }
    setPracuje(false);
  }

  function rozepis(nahradit) {
    if (!sablona) {
      setChyba("Vyber splátkový kalendář.");
      return;
    }
    return proved(() =>
      crmFakturyZeSablony(objednavkaId, {
        sablona,
        prvni_termin: prvniTermin || null,
        nahradit,
      })
    );
  }

  function zmenFakturu(f, zmeny) {
    return proved(() =>
      crmFakturaUprav(f.id, {
        nazev: f.nazev,
        stav: f.stav,
        castka: f.castka,
        podil_procent: f.podil_procent,
        termin: f.termin,
        variabilni_symbol: f.variabilni_symbol,
        poznamka: f.poznamka,
        ...zmeny,
      })
    );
  }

  async function smaz(f) {
    if (!window.confirm(`Smazat fakturu „${f.nazev || `#${f.poradi}`}“?`)) return;
    await proved(() => crmFakturaSmaz(f.id));
  }

  if (chyba && data == null) return <div className="crm-chyba">{chyba}</div>;
  if (data == null) return <p className="crm-tise">Načítám fakturaci…</p>;

  const s = data.souhrn || {};
  const maFaktury = (data.faktury || []).length > 0;

  return (
    <div className="crm-oddelovac" style={{ marginTop: 16, paddingTop: 14 }}>
      <h3>Fakturace</h3>

      {!maFaktury && (
        <p className="crm-tise">
          K objednávce zatím nejsou žádné faktury. Rozepiš cenu do splátek, nebo přidej
          jednu fakturu ručně.
        </p>
      )}

      {maFaktury && (
        <>
          <div className="crm-scroll">
            <table className="gs-table">
              <thead>
                <tr>
                  <th>#</th><th>Název</th><th className="n">Částka</th><th className="n">Podíl</th>
                  <th>Termín</th><th>VS</th><th>Stav</th><th></th>
                </tr>
              </thead>
              <tbody>
                {data.faktury.map((f) => (
                  <tr key={f.id} className="staticky">
                    <td>{f.poradi}</td>
                    <td>
                      <input
                        className="crm-pole"
                        style={{ minWidth: 120 }}
                        defaultValue={f.nazev}
                        onBlur={(e) =>
                          e.target.value !== f.nazev && zmenFakturu(f, { nazev: e.target.value })
                        }
                      />
                    </td>
                    <td className="n">
                      <input
                        className="crm-pole"
                        style={{ width: 110, textAlign: "right" }}
                        defaultValue={f.castka ?? ""}
                        inputMode="decimal"
                        onBlur={(e) => {
                          const v = e.target.value.trim();
                          const cislo = v === "" ? null : Number(v.replace(/\s/g, "").replace(",", "."));
                          if (cislo !== f.castka) zmenFakturu(f, { castka: cislo });
                        }}
                      />
                    </td>
                    <td className="n">{f.podil_procent != null ? `${f.podil_procent} %` : "—"}</td>
                    <td>
                      <input
                        className="crm-pole"
                        type="date"
                        style={{ width: 140 }}
                        defaultValue={(f.termin || "").slice(0, 10)}
                        onBlur={(e) =>
                          e.target.value !== (f.termin || "") &&
                          zmenFakturu(f, { termin: e.target.value || null })
                        }
                      />
                      {f.po_terminu && (
                        <span className="gs-pill spatne" title="Termín utekl a faktura není zaplacená">
                          po termínu
                        </span>
                      )}
                    </td>
                    <td>
                      <input
                        className="crm-pole"
                        style={{ width: 100 }}
                        defaultValue={f.variabilni_symbol || ""}
                        placeholder="VS"
                        onBlur={(e) =>
                          e.target.value !== (f.variabilni_symbol || "") &&
                          zmenFakturu(f, { variabilni_symbol: e.target.value || null })
                        }
                      />
                    </td>
                    <td>
                      <select
                        className="crm-pole"
                        style={{ width: 150 }}
                        value={f.stav}
                        onChange={(e) => zmenFakturu(f, { stav: e.target.value })}
                      >
                        {STAVY.map((x) => <option key={x.klic} value={x.klic}>{x.nazev}</option>)}
                      </select>
                      {f.pohoda_potvrzeno && (
                        <span className="gs-pill dobre" title={`POHODA: vystaveno ${fmtDatum(f.pohoda_datum_vystaveni)}`}>
                          POHODA
                        </span>
                      )}
                    </td>
                    <td className="n">
                      <button
                        type="button"
                        onClick={() => smaz(f)}
                        title="Smazat fakturu"
                        style={{ background: "none", border: "none", cursor: "pointer", color: "var(--st-crit)", fontWeight: 700 }}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, margin: "10px 0" }}>
            <span>Cena objednávky: <b>{kc(data.cena_objednavky_kc)}</b></span>
            <span>Vyfakturováno: <b>{kc(s.vyfakturovano_kc)}</b></span>
            <span>Zaplaceno: <b>{kc(s.zaplaceno_kc)}</b></span>
            <span>Zbývá rozepsat: <b>{kc(s.zbyva_fakturovat_kc)}</b></span>
            {s.po_terminu_kc > 0 && (
              <span style={{ color: "var(--st-crit)" }}>Po termínu: <b>{kc(s.po_terminu_kc)}</b></span>
            )}
          </div>

          {s.nesedi_soucet && (
            <p className="crm-tise" style={{ color: "var(--st-warn, #b26a00)" }}>
              Součet faktur neodpovídá ceně objednávky (rozdíl {kc(s.zbyva_fakturovat_kc)}).
              {" "}
              <button
                className="fm-btn crm-btn-maly"
                onClick={() => proved(() => crmFakturyPrepocitat(objednavkaId))}
                disabled={pracuje}
              >
                Přepočítat podle podílů
              </button>
              {" "}Přepočítají se jen faktury, které ještě nejsou vystavené.
            </p>
          )}
        </>
      )}

      <div className="crm-stav-novy" style={{ marginTop: 10, flexWrap: "wrap" }}>
        <select className="crm-pole" value={sablona} onChange={(e) => setSablona(e.target.value)} style={{ maxWidth: 260 }}>
          <option value="">— splátkový kalendář —</option>
          {sablony.map((x) => <option key={x.klic} value={x.klic}>{x.nazev}</option>)}
        </select>
        <input
          className="crm-pole"
          type="date"
          value={prvniTermin}
          onChange={(e) => setPrvniTermin(e.target.value)}
          title="Termín první splátky (další po měsíci)"
          style={{ maxWidth: 160 }}
        />
        <button className="fm-btn fm-primary" onClick={() => rozepis(false)} disabled={pracuje}>
          Rozepsat splátky
        </button>
        {maFaktury && (
          <button
            className="fm-btn"
            onClick={() => rozepis(true)}
            disabled={pracuje}
            title="Zahodí zatím nevystavené faktury a rozepíše je znovu"
          >
            Rozepsat znovu
          </button>
        )}
        <button
          className="fm-btn"
          onClick={() => proved(() => crmFakturaPridej(objednavkaId, { nazev: "Faktura" }))}
          disabled={pracuje}
        >
          + Jedna faktura
        </button>
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}
    </div>
  );
}
