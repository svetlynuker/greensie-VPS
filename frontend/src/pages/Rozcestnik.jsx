import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import { logout, nactiDashboard, nactiMe } from "../api";
import { DRUHY_AKTIVITY, fmtDatum } from "../crm";

// Souhrn ke dnešnímu dni. Navigaci obstarává panel vlevo, tady jsou jen čísla
// a to, co potřebuje pozornost. Sekce bez práva backend vůbec nepošle (None),
// takže se nekreslí — stejně jako se skrývají položky v nabídce.

const CASTKA = new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: 0 });

function pozdrav() {
  const h = new Date().getHours();
  if (h < 9) return "Dobré ráno";
  if (h < 12) return "Dobré dopoledne";
  if (h < 18) return "Dobré odpoledne";
  return "Dobrý večer";
}

// „za 3 dny" / „3 dny po termínu" — dni je kladné, když je úkol po termínu.
function popisDnu(dni) {
  if (dni > 0) return `${dni} ${dni === 1 ? "den" : dni < 5 ? "dny" : "dní"} po termínu`;
  const zbyva = -dni;
  if (zbyva === 0) return "dnes";
  return `za ${zbyva} ${zbyva === 1 ? "den" : zbyva < 5 ? "dny" : "dní"}`;
}

function Kpi({ label, hodnota, jednotka, popis, akcent, stav }) {
  return (
    <div className={`gs-kpi${akcent ? " accent" : ""}`}>
      <div className="gs-kpi-label">{label}</div>
      <div className="gs-kpi-value">
        {hodnota}
        {jednotka && <span className="gs-unit">{jednotka}</span>}
      </div>
      {stav ? (
        <div className="gs-kpi-sub">
          <span className={`gs-pill ${stav}`}>
            <span className="gs-dot" />
            {popis}
          </span>
        </div>
      ) : (
        popis && <div className="gs-kpi-sub">{popis}</div>
      )}
    </div>
  );
}

// Výpis úkolů, které potřebují pozornost. Prázdný stav je taky odpověď.
function VypisUkolu({ nazev, popis, radky, stav, prazdne, onProjekty }) {
  return (
    <section className="fm-card" style={{ overflow: "hidden" }}>
      <div className="gs-karta-hlava">
        <span className="gs-karta-titulek">{nazev}</span>
        <span className="gs-tb-spacer" />
        {radky.length > 0 && (
          <button className="fm-btn" onClick={onProjekty}>
            Otevřít Přehled projektů
          </button>
        )}
      </div>

      {radky.length === 0 ? (
        <div className="gs-prazdno">
          <div className="gs-prazdno-znak">
            <Ikona jmeno="zmeny" velikost={22} />
          </div>
          <h3>{prazdne}</h3>
        </div>
      ) : (
        <>
          <p className="gs-karta-popis">{popis}</p>
          <div className="gs-tabulka-obal">
            <table className="gs-tabulka">
              <thead>
                <tr>
                  <th>Projekt</th>
                  <th>Úkol</th>
                  <th>Kdo</th>
                  <th className="ta-r">Termín</th>
                </tr>
              </thead>
              <tbody>
                {radky.map((r, i) => (
                  <tr key={`${r.projekt_id}-${r.ukol}-${i}`}>
                    <td className="gs-cell-name">{r.projekt_nazev}</td>
                    <td>{r.ukol}</td>
                    <td>{r.osoba || <span style={{ color: "var(--muted)" }}>nikdo</span>}</td>
                    <td className="ta-r">
                      <span className={`gs-pill ${stav}`}>
                        <span className="gs-dot" />
                        {popisDnu(r.dni)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

// Moje úkoly z CRM. Jiná tabulka než výpis z matice výš: úkol tu nevisí na
// projektu, ale na libovolném záznamu CRM (zákazník, případ, nabídka…), takže
// se musí ukázat U ČEHO je — a kliknutím se tam jít dá.
function VypisCrmUkolu({ radky, celkem, onZaznam, onPripady }) {
  return (
    <section className="fm-card" style={{ overflow: "hidden" }}>
      <div className="gs-karta-hlava">
        <span className="gs-karta-titulek">Moje úkoly v CRM</span>
        <span className="gs-tb-spacer" />
        <button className="fm-btn" onClick={onPripady}>
          Otevřít Obchodní případy
        </button>
      </div>

      {radky.length === 0 ? (
        <div className="gs-prazdno">
          <div className="gs-prazdno-znak">
            <Ikona jmeno="pripady" velikost={22} />
          </div>
          <h3>Žádný úkol s termínem tě nečeká</h3>
          <p>
            Úkol vznikne tak, že u zákazníka nebo případu přidáš aktivitu a dáš jí termín.
          </p>
        </div>
      ) : (
        <>
          <p className="gs-karta-popis">
            Nehotové úkoly s termínem, které patří tobě. Nejbližší termín první.
            {celkem > radky.length && ` Zobrazeno ${radky.length} z ${celkem}.`}
          </p>
          <div className="gs-tabulka-obal">
            <table className="gs-tabulka">
              <thead>
                <tr>
                  <th>U čeho</th>
                  <th>Úkol</th>
                  <th className="ta-r">Termín</th>
                </tr>
              </thead>
              <tbody>
                {radky.map((r) => {
                  const poTerminu = r.dni > 0;
                  const dnes = r.dni === 0;
                  const ikona = DRUHY_AKTIVITY.find((d) => d.klic === r.druh)?.ikona || "";
                  return (
                    <tr
                      key={r.id}
                      onClick={r.cesta ? () => onZaznam(r.cesta) : undefined}
                      style={r.cesta ? { cursor: "pointer" } : undefined}
                      title={r.cesta ? "Otevřít záznam" : "Tenhle záznam nemá vlastní stránku"}
                    >
                      <td className="gs-cell-name">{r.zaznam_nazev}</td>
                      <td>
                        {ikona && <span style={{ marginRight: 6 }}>{ikona}</span>}
                        {r.text || <span style={{ color: "var(--muted)" }}>bez popisu</span>}
                      </td>
                      <td className="ta-r">
                        <span className={`gs-pill ${poTerminu ? "crit" : dnes ? "warn" : "good"}`}>
                          <span className="gs-dot" />
                          {popisDnu(r.dni)}
                        </span>
                        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                          {fmtDatum(r.termin)}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}

export default function Rozcestnik() {
  const [me, setMe] = useState(null);
  const [souhrn, setSouhrn] = useState(null);
  const [chyba, setChyba] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    // Uživatel je podmínka pro zobrazení stránky — když se nenačte, jde se
    // na přihlášení. Souhrn je navíc: když spadne, stránka zůstane a jen
    // hlásí, že čísla chybí.
    nactiMe()
      .then((data) => {
        if (data.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setMe(data);
        nactiDashboard()
          .then(setSouhrn)
          .catch((e) => setChyba(e.message));
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  if (!me) return null;

  const jmeno = (me.uzivatel?.jmeno || "").split(" ")[0];
  const p = souhrn?.projekty;
  const f = souhrn?.finance;
  const n = souhrn?.nabidky;
  const c = souhrn?.crm;
  const muzeNabidkovac = (me.prava || []).includes("nabidkovac");

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="gs-page-head">
        <div>
          <h1 className="gs-page-h1">
            {pozdrav()}
            {jmeno ? `, ${jmeno}` : ""}
          </h1>
          <p className="gs-page-lead">
            Stav ke dnešnímu dni. Sekce vlevo se řídí tvými oprávněními.
          </p>
        </div>
        <span className="gs-tb-spacer" />
        {muzeNabidkovac && (
          <button className="fm-btn fm-primary" onClick={() => navigate("/nabidkovac")}>
            <Ikona jmeno="nabidkovac" velikost={15} />
            Nová nabídka
          </button>
        )}
      </div>

      {chyba && (
        <div className="fm-card" style={{ padding: 14, marginBottom: 16 }}>
          <span className="gs-pill warn">
            <span className="gs-dot" />
            Souhrn se nepodařilo načíst
          </span>
          <div style={{ marginTop: 8, fontSize: 13, color: "var(--muted)" }}>{chyba}</div>
        </div>
      )}

      {(p || f || n || c) && (
        <div className="gs-kpis" style={{ marginBottom: 16 }}>
          {/* Moje úkoly první — je to jediné číslo na stránce, které je osobní. */}
          {c && (
            <Kpi
              label="Moje úkoly v CRM"
              hodnota={c.celkem}
              popis={
                c.po_terminu > 0
                  ? `${c.po_terminu} po termínu`
                  : c.dnes > 0
                    ? `${c.dnes} na dnes`
                    : c.celkem === 0
                      ? "Nic nevisí"
                      : "Nic po termínu"
              }
              stav={c.po_terminu > 0 ? "crit" : c.dnes > 0 ? "warn" : "good"}
            />
          )}
          {p && (
            <>
              <Kpi label="Aktivní projekty" hodnota={p.aktivni} popis="V matici (nezakryté)" akcent />
              <Kpi
                label="Úkoly po termínu"
                hodnota={p.po_terminu}
                popis={p.po_terminu === 0 ? "Nic nevisí" : "Vyžaduje pozornost"}
                stav={p.po_terminu === 0 ? "good" : "crit"}
              />
              <Kpi
                label="Termín do 14 dnů"
                hodnota={p.blizi_se}
                popis={p.bez_terminu > 0 ? `${p.bez_terminu} úkolů bez termínu` : "Všechno má termín"}
              />
            </>
          )}
          {f && (
            <Kpi
              label="Neuhrazené faktury"
              hodnota={CASTKA.format(Math.round(f.neuhrazeno_kc))}
              jednotka="Kč"
              popis={
                f.po_splatnosti_pocet === 0
                  ? `${f.neuhrazeno_pocet} faktur, žádná po splatnosti`
                  : `${f.po_splatnosti_pocet} po splatnosti, nejstarší ${f.nejstarsi_dni} dní`
              }
              stav={f.po_splatnosti_pocet === 0 ? undefined : "serious"}
            />
          )}
          {n && (
            <Kpi
              label="Nabídky v přípravě"
              hodnota={n.rozpracovane}
              popis={`${n.celkem} celkem, ${n.nove_30_dni} nových za 30 dní`}
            />
          )}
        </div>
      )}

      {c && (
        <div style={{ display: "grid", gap: 16, marginBottom: p ? 16 : 0 }}>
          <VypisCrmUkolu
            radky={souhrn.crm_ukoly || []}
            celkem={c.celkem}
            onZaznam={(cesta) => navigate(cesta)}
            onPripady={() => navigate("/pripady")}
          />
        </div>
      )}

      {p && (
        <div style={{ display: "grid", gap: 16 }}>
          <VypisUkolu
            nazev="Potřebuje pozornost"
            popis="Nehotové úkoly, kterým už termín uplynul. Nejstarší první."
            radky={souhrn.po_terminu}
            stav="crit"
            prazdne="Nic není po termínu"
            onProjekty={() => navigate("/prehled-projektu")}
          />
          <VypisUkolu
            nazev="Blíží se termín"
            popis="Nehotové úkoly s termínem v následujících 14 dnech."
            radky={souhrn.blizi_se}
            stav="warn"
            prazdne="V příštích 14 dnech nic nekončí"
            onProjekty={() => navigate("/prehled-projektu")}
          />
        </div>
      )}

      {!p && !f && !n && !c && !chyba && (
        <section className="fm-card">
          <div className="gs-prazdno">
            <div className="gs-prazdno-znak">
              <Ikona jmeno="napoveda" velikost={22} />
            </div>
            <h3>Zatím tu pro tebe nic není</h3>
            <p>
              Souhrn se skládá z modulů, na které máš oprávnění. Zkus Manuál vlevo, nebo si
              o přístup řekni správci.
            </p>
          </div>
        </section>
      )}
    </Layout>
  );
}
