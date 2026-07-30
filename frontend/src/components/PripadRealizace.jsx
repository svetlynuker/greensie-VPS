import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ObjednavkaFormular from "./ObjednavkaFormular";
import { crmObjednavky, crmProjekty, crmProjektZaloz, crmSablony } from "../api";
import { fmtDatum, fmtKc } from "../crm";

/**
 * Objednávky a projekty obchodního případu – druhá polovina řetězce.
 *
 * Objednávka se zakládá **z přijaté nabídky** (nabídky bere z případu), projekt
 * pak z objednávky. Projekt jde založit i přímo z případu, protože ne každá
 * zakázka projde objednávkou (servis, dořešení po telefonu) – ale nikdy
 * samostatně mimo případ, aby vždy bylo dohledatelné, z čeho realizace vyšla.
 */
export default function PripadRealizace({ pripad, me, onZmena }) {
  const navigate = useNavigate();
  const [objednavky, setObjednavky] = useState([]);
  const [projekty, setProjekty] = useState([]);
  const [sablony, setSablony] = useState([]);
  const [nova, setNova] = useState(null); // {nabidka} pro novou objednávku
  const [detail, setDetail] = useState(null);
  const [sablonaId, setSablonaId] = useState("");
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async () => {
    const [o, p] = await Promise.all([
      crmObjednavky({ pripadId: pripad.id }),
      crmProjekty({ pripadId: pripad.id }),
    ]);
    setObjednavky(o);
    setProjekty(p);
  }, [pripad.id]);

  useEffect(() => {
    nacti().catch((e) => setChyba(e.message));
    crmSablony().then(setSablony).catch(() => setSablony([]));
  }, [nacti]);

  async function zalozProjektZPripadu() {
    setChyba(null);
    try {
      const projekt = await crmProjektZaloz({
        obchodni_pripad_id: pripad.id,
        sablona_id: sablonaId ? Number(sablonaId) : null,
        nazev: pripad.nazev || "",
      });
      await nacti();
      await onZmena?.();
      navigate(`/projekty/detail/${projekt.id}`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  const nabidky = pripad.nabidky || [];

  return (
    <div className="crm-nabidky">
      {chyba && <div className="crm-chyba">{chyba}</div>}

      {/* ---- Objednávky ---- */}
      <div className="fm-card crm-blok">
        <div className="crm-blok-hlava">
          <h3>Objednávky</h3>
          <span className="crm-mezera" />
          {/* Objednávku zakládáme z nabídky – převezme z ní cenu. Když nabídka
              není, jde založit i prázdná. */}
          {nabidky.length > 0 ? (
            nabidky.map((n) => (
              <button
                key={n.id}
                className="fm-btn"
                onClick={() => setNova({ nabidka: n })}
                title={`Objednávka podle nabídky ${n.cislo || n.id}`}
              >
                + z {n.cislo || `#${n.id}`}
              </button>
            ))
          ) : (
            <button className="fm-btn" onClick={() => setNova({ nabidka: null })}>
              + Objednávka
            </button>
          )}
        </div>

        {objednavky.length === 0 ? (
          <p className="crm-tise">
            Zatím žádná objednávka. Zakládá se z nabídky, kterou zákazník přijal.
          </p>
        ) : (
          <table className="crm-tabulka crm-tabulka-hustá">
            <thead>
              <tr>
                <th>Číslo</th>
                <th>Název</th>
                <th className="crm-vpravo">Cena</th>
                <th>Podpis</th>
                <th>Stav</th>
                <th>Projekt</th>
              </tr>
            </thead>
            <tbody>
              {objednavky.map((o) => (
                <tr key={o.id} onClick={() => setDetail(o.id)} style={{ cursor: "pointer" }}>
                  <td className="crm-silne">{o.cislo}</td>
                  <td>{o.nazev || "—"}</td>
                  <td className="crm-vpravo">{fmtKc(o.cena_kc)}</td>
                  <td>{fmtDatum(o.datum_podpisu) || "—"}</td>
                  <td>
                    <span className="crm-znacka">{o.stav_nazev}</span>
                  </td>
                  <td>
                    {o.ma_projekt ? (
                      <span className="crm-znacka crm-barva-ok">ano</span>
                    ) : (
                      <span className="crm-tise">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ---- Projekty ---- */}
      <div className="fm-card crm-blok">
        <div className="crm-blok-hlava">
          <h3>Projekty</h3>
          <span className="crm-mezera" />
          <select
            className="crm-pole crm-pole-uzke"
            value={sablonaId}
            onChange={(e) => setSablonaId(e.target.value)}
          >
            <option value="">— bez šablony —</option>
            {sablony.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nazev} ({s.kroky.length})
              </option>
            ))}
          </select>
          <button className="fm-btn" onClick={zalozProjektZPripadu}>
            + Projekt z případu
          </button>
        </div>

        {projekty.length === 0 ? (
          <p className="crm-tise">
            Zatím žádný projekt. Obvykle vzniká z podepsané objednávky (tlačítko je v jejím
            detailu); rovnou z případu jde založit u zakázek, které objednávkou neprochází.
          </p>
        ) : (
          <table className="crm-tabulka crm-tabulka-hustá">
            <thead>
              <tr>
                <th>Číslo</th>
                <th>Název</th>
                <th>Stav</th>
                <th>Kroky</th>
                <th>Nejbližší termín</th>
              </tr>
            </thead>
            <tbody>
              {projekty.map((pr) => (
                <tr
                  key={pr.id}
                  onClick={() => navigate(`/projekty/detail/${pr.id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td className="crm-silne">{pr.cislo}</td>
                  <td>{pr.nazev || "—"}</td>
                  <td>
                    <span className="crm-znacka">{pr.stav_nazev}</span>
                  </td>
                  <td>{pr.kroku > 0 ? `${pr.hotovo}/${pr.kroku} (${pr.procent} %)` : "—"}</td>
                  <td>
                    {fmtDatum(pr.nejblizsi_termin) || "—"}
                    {pr.po_terminu > 0 && (
                      <span className="crm-po-terminu"> · {pr.po_terminu} po termínu</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {nova && (
        <ObjednavkaFormular
          pripad={pripad}
          nabidka={nova.nabidka}
          muzeMenitVlastnika={me?.prava?.includes("crm_vse")}
          onZavri={() => setNova(null)}
          onZmena={async () => {
            await nacti();
            await onZmena?.();
          }}
          onProjekt={(projektId) => navigate(`/projekty/detail/${projektId}`)}
        />
      )}

      {detail && (
        <ObjednavkaFormular
          objednavkaId={detail}
          muzeMenitVlastnika={me?.prava?.includes("crm_vse")}
          onZavri={() => setDetail(null)}
          onZmena={async () => {
            await nacti();
            await onZmena?.();
          }}
          onProjekt={(projektId) => navigate(`/projekty/detail/${projektId}`)}
        />
      )}
    </div>
  );
}
