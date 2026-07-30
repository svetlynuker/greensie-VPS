import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Kanban from "../components/Kanban";
import PripadFormular from "../components/PripadFormular";
import StavyNastaveni from "../components/StavyNastaveni";
import DuvodProhry from "../components/DuvodProhry";
import {
  crmPripadStav,
  crmPripady,
  crmPripadyKanban,
  crmStavy,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, nazvyKategorii } from "../crm";
import "../styles/crm.css";

/**
 * Sekce Obchodní případy – kanban (výchozí, kvůli posouvání stavů) a tabulka.
 *
 * Kanban je výchozí schválně: hlavní denní práce s případy je posouvat je
 * fázemi, ne je čtou v tabulce. Tabulka zůstává pro hledání a přehled čísel.
 */
export default function ObchodniPripady() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zobrazeni, setZobrazeni] = useState("kanban");
  const [kanban, setKanban] = useState(null);
  const [radky, setRadky] = useState([]);
  const [stavy, setStavy] = useState([]);
  const [hledat, setHledat] = useState("");
  const [novy, setNovy] = useState(false);
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [prohra, setProhra] = useState(null); // {pripadId, stav}
  const [sloupce, setSloupce] = useState([]);
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, s, pole] = await Promise.all([
      crmPripadyKanban(),
      crmPripady({ hledat: dotaz || undefined }),
      crmStavy("op"),
      crmVlastniPole("op").catch(() => []),
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
      crmPripady({ hledat: hledat || undefined })
        .then(setRadky)
        .catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me]);

  /**
   * Přesun v kanbanu. U stavu druhu „prohra" se nejdřív zeptáme na důvod –
   * bez důvodů proher nemá statistika pipeline žádnou vypovídací hodnotu
   * (a backend prohru bez důvodu odmítne).
   */
  async function presun(pripadId, novyStav) {
    const stav = stavy.find((s) => s.klic === novyStav);
    if (stav?.druh === "prohra") {
      setProhra({ pripadId, stav: novyStav });
      return;
    }
    setChyba(null);
    try {
      await crmPripadStav(pripadId, novyStav);
      await nacti(hledat);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function potvrdProhru(duvod) {
    const { pripadId, stav } = prohra;
    setProhra(null);
    try {
      await crmPripadStav(pripadId, stav, duvod);
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

  const muzeNastaveni = me.prava?.includes("crm_nastaveni");
  const celkem = kanban.sloupce.reduce((s, x) => s + x.pocet, 0);

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <div className="crm-hlava">
          <div>
            <h1>Obchodní případy</h1>
            <p className="crm-popis">
              Zakázka od poptávky po výhru. Případ zastřešuje nabídky, objednávku a projekt;
              posouvej ho fázemi přetažením dlaždice.
            </p>
          </div>
          <span className="crm-mezera" />
          {muzeNastaveni && (
            <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
              ⚙ Stavy pipeline
            </button>
          )}
          <button className="fm-btn fm-primary" onClick={() => setNovy(true)}>
            + Nový případ
          </button>
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
              placeholder="Hledat podle čísla, názvu nebo zákazníka…"
              value={hledat}
              onChange={(e) => setHledat(e.target.value)}
            />
          )}
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{celkem}</b> případů
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={kanban.sloupce}
            onPresun={presun}
            onOtevri={(z) => navigate(`/pripady/detail/${z.id}`)}
          />
        ) : (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Zákazník</th>
                  <th>Název</th>
                  <th>Kategorie</th>
                  <th>Stav</th>
                  <th className="crm-vpravo">Hodnota</th>
                  <th>Uzavření</th>
                  <th>Vlastník</th>
                  {sloupce.map((sl) => (
                    <th key={sl.klic}>{sl.nazev}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {radky.map((p) => (
                  <tr key={p.id} onClick={() => navigate(`/pripady/detail/${p.id}`)}>
                    <td className="crm-silne">{p.cislo}</td>
                    <td>{p.zakaznik_nazev}</td>
                    <td>{p.nazev || "—"}</td>
                    <td>{nazvyKategorii(p.kategorie) || "—"}</td>
                    <td>
                      <span className="crm-znacka">{p.stav_nazev}</span>
                    </td>
                    <td className="crm-vpravo">{fmtKc(p.hodnota_kc)}</td>
                    <td>{fmtDatum(p.predpokladane_uzavreni) || "—"}</td>
                    <td>{p.vlastnik_jmeno || "—"}</td>
                    {sloupce.map((sl) => (
                      <td key={sl.klic}>{(p.extra_text || {})[sl.klic] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
                {radky.length === 0 && (
                  <tr>
                    <td colSpan={8 + sloupce.length} className="crm-prazdno">
                      {hledat ? "Nic nenalezeno." : "Zatím žádné případy."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {novy && (
        <PripadFormular
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setNovy(false)}
          onHotovo={(p) => {
            setNovy(false);
            navigate(`/pripady/detail/${p.id}`);
          }}
        />
      )}

      {nastaveniStavu && (
        <StavyNastaveni
          entita="op"
          onZavri={() => setNastaveniStavu(false)}
          onZmena={() => nacti(hledat)}
        />
      )}

      {prohra && (
        <DuvodProhry onZavri={() => setProhra(null)} onPotvrd={potvrdProhru} />
      )}
    </Layout>
  );
}
