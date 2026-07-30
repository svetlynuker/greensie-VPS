import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Kanban from "../components/Kanban";
import ObjednavkaFormular from "../components/ObjednavkaFormular";
import StavyNastaveni from "../components/StavyNastaveni";
import DuvodProhry from "../components/DuvodProhry";
import {
  crmObjednavkaStav,
  crmObjednavky,
  crmObjednavkyKanban,
  crmStavy,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, fmtKcKratce } from "../crm";
import "../styles/crm.css";

/**
 * Sekce Objednávky – potvrzené zakázky mezi nabídkou a realizací.
 *
 * Objednávka vzniká z přijaté nabídky (na kartě případu) a je spouštěčem
 * projektu. Tady je přehled a posouvání stavů; detail se otevře v okně,
 * protože objednávka je jednoduchý záznam – na rozdíl od projektu, který má
 * kroky a vlastní obrazovku.
 */
export default function Objednavky() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zobrazeni, setZobrazeni] = useState("kanban");
  const [kanban, setKanban] = useState(null);
  const [radky, setRadky] = useState([]);
  const [stavy, setStavy] = useState([]);
  const [sloupce, setSloupce] = useState([]);
  const [hledat, setHledat] = useState("");
  const [detail, setDetail] = useState(null);
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [zruseni, setZruseni] = useState(null);
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, s, pole] = await Promise.all([
      crmObjednavkyKanban(),
      crmObjednavky({ hledat: dotaz || undefined }),
      crmStavy("obj"),
      crmVlastniPole("obj").catch(() => []),
    ]);
    setKanban(k);
    setRadky(r);
    setStavy(s);
    setSloupce(pole.filter((x) => x.v_seznamu));
  }, []);

  useEffect(() => {
    nactiMe()
      .then(async (m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("obchodni_pripady")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        await nacti();
      })
      .catch((e) => {
        const msg = String(e.message);
        if (msg.includes("přihlášení") || msg.includes("uživatel")) {
          logout();
          navigate("/");
        } else if (msg.includes("oprávnění")) {
          navigate("/rozcestnik");
        } else {
          setChyba(msg);
        }
      });
  }, [navigate, nacti]);

  useEffect(() => {
    if (!me) return undefined;
    const t = setTimeout(() => {
      crmObjednavky({ hledat: hledat || undefined })
        .then(setRadky)
        .catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me]);

  async function presun(id, novyStav) {
    // Zrušení objednávky si žádá důvod (stejně jako prohra případu).
    const stav = stavy.find((s) => s.klic === novyStav);
    if (stav?.druh === "prohra") {
      setZruseni({ id, stav: novyStav });
      return;
    }
    setChyba(null);
    try {
      await crmObjednavkaStav(id, novyStav);
      await nacti(hledat);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function potvrdZruseni(duvod) {
    const { id, stav } = zruseni;
    setZruseni(null);
    try {
      await crmObjednavkaStav(id, stav, duvod);
      await nacti(hledat);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !kanban) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !kanban) return null;

  const celkem = kanban.sloupce.reduce((s, x) => s + x.pocet, 0);

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <div className="crm-hlava">
          <div>
            <h1>Objednávky</h1>
            <p className="crm-popis">
              Potvrzené zakázky. Objednávka vzniká z přijaté nabídky na kartě případu a je
              spouštěčem projektu — realizace se zakládá z ní.
            </p>
          </div>
          <span className="crm-mezera" />
          {me.prava?.includes("crm_nastaveni") && (
            <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
              ⚙ Stavy objednávek
            </button>
          )}
        </div>

        <div className="crm-toolbar">
          <div className="crm-prepinac">
            <button
              className={`crm-zalozka ${zobrazeni === "kanban" ? "aktivni" : ""}`}
              onClick={() => setZobrazeni("kanban")}
            >
              Kanban
            </button>
            <button
              className={`crm-zalozka ${zobrazeni === "tabulka" ? "aktivni" : ""}`}
              onClick={() => setZobrazeni("tabulka")}
            >
              Tabulka
            </button>
          </div>
          {zobrazeni === "tabulka" && (
            <input
              className="crm-pole crm-hledani"
              placeholder="Hledat podle čísla nebo názvu…"
              value={hledat}
              onChange={(e) => setHledat(e.target.value)}
            />
          )}
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{celkem}</b> objednávek
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={kanban.sloupce}
            onPresun={presun}
            onOtevri={(o) => setDetail(o.id)}
            dlazdice={(o) => (
              <>
                <div className="crm-dlazdice-hlava">
                  <span className="crm-dlazdice-cislo">{o.cislo}</span>
                  {o.cena_kc ? (
                    <span className="crm-dlazdice-hodnota">{fmtKcKratce(o.cena_kc)}</span>
                  ) : null}
                </div>
                <div className="crm-dlazdice-zakaznik">{o.zakaznik_nazev || "—"}</div>
                {o.nazev && <div className="crm-dlazdice-nazev">{o.nazev}</div>}
                <div className="crm-dlazdice-pata">
                  {o.pripad_cislo}
                  {o.datum_podpisu ? ` · podpis ${fmtDatum(o.datum_podpisu)}` : ""}
                  {/* Že z objednávky vznikl projekt, je důležitější než cokoli jiného. */}
                  {o.ma_projekt ? " · projekt založen" : ""}
                </div>
              </>
            )}
          />
        ) : (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Zákazník</th>
                  <th>Název</th>
                  <th>Případ</th>
                  <th>Nabídka</th>
                  <th className="crm-vpravo">Cena</th>
                  <th>Podpis</th>
                  <th>Stav</th>
                  <th>Projekt</th>
                  {sloupce.map((sl) => (
                    <th key={sl.klic}>{sl.nazev}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {radky.map((o) => (
                  <tr key={o.id} onClick={() => setDetail(o.id)}>
                    <td className="crm-silne">{o.cislo}</td>
                    <td>{o.zakaznik_nazev || "—"}</td>
                    <td>{o.nazev || "—"}</td>
                    <td>{o.pripad_cislo}</td>
                    <td>{o.nabidka_cislo || <span className="crm-tise">—</span>}</td>
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
                    {sloupce.map((sl) => (
                      <td key={sl.klic}>{(o.extra_text || {})[sl.klic] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
                {radky.length === 0 && (
                  <tr>
                    <td colSpan={9 + sloupce.length} className="crm-prazdno">
                      {hledat
                        ? "Nic nenalezeno."
                        : "Zatím žádné objednávky. Zakládají se z přijaté nabídky na kartě případu."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {detail && (
        <ObjednavkaFormular
          objednavkaId={detail}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setDetail(null)}
          onZmena={() => nacti(hledat)}
          onProjekt={(projektId) => navigate(`/projekty/detail/${projektId}`)}
        />
      )}

      {nastaveniStavu && (
        <StavyNastaveni
          entita="obj"
          onZavri={() => setNastaveniStavu(false)}
          onZmena={() => nacti(hledat)}
        />
      )}

      {zruseni && (
        <DuvodProhry onZavri={() => setZruseni(null)} onPotvrd={potvrdZruseni} />
      )}
    </Layout>
  );
}
