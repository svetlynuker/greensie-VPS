import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Kanban from "../components/Kanban";
import MigraceNabidek from "../components/MigraceNabidek";
import StavyNastaveni from "../components/StavyNastaveni";
import {
  crmNabidkaStav,
  crmNabidky,
  crmNabidkyKanban,
  crmStavy,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum } from "../crm";
import "../styles/crm.css";

const TYPY = { ppa: "PPA", prodej: "Prodej", peak_shaving: "Peak shaving" };

/**
 * Sekce Nabídky – obchodní přehled napříč případy.
 *
 * Tady se s nabídkou NEPOČÍTÁ; to se dělá na kartě obchodního případu. Tahle
 * obrazovka odpovídá na jiné otázky: co je odesláno, co viselo bez reakce
 * a co zákazník přijal. Proto kanban podle obchodních stavů a klik, který vede
 * na případ, kde se dá pracovat.
 */
export default function Nabidky() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zobrazeni, setZobrazeni] = useState("kanban");
  const [kanban, setKanban] = useState(null);
  const [radky, setRadky] = useState([]);
  const [stavy, setStavy] = useState([]);
  const [hledat, setHledat] = useState("");
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [migrace, setMigrace] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, s] = await Promise.all([
      crmNabidkyKanban(),
      crmNabidky({ hledat: dotaz || undefined }),
      crmStavy("nab"),
    ]);
    setKanban(k);
    setRadky(r);
    setStavy(s);
  }, []);

  useEffect(() => {
    nactiMe()
      .then(async (m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("nabidkovac")) {
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
      crmNabidky({ hledat: hledat || undefined })
        .then(setRadky)
        .catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me]);

  async function presun(nabidkaId, novyStav) {
    setChyba(null);
    try {
      await crmNabidkaStav(nabidkaId, novyStav);
      await nacti(hledat);
    } catch (e) {
      setChyba(e.message);
    }
  }

  /** Klik na nabídku vede tam, kde se s ní pracuje – na její obchodní případ. */
  function otevri(n) {
    if (n.pripad_id) navigate(`/pripady/detail/${n.pripad_id}`);
    else navigate(`/nabidkovac/nabidka/${n.id}`);
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
  // Nabídky bez případu visí v přehledu jako #id bez zákazníka – dokud jsou,
  // má smysl nabízet jejich dohledání.
  const bezPripadu = radky.filter((n) => !n.pripad_id).length;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <div className="crm-hlava">
          <div>
            <h1>Nabídky</h1>
            <p className="crm-popis">
              Přehled nabídek napříč obchodními případy — co je odesláno, co čeká na reakci
              a co zákazník přijal. Podklady a výpočet se dělají na kartě případu; klik na
              nabídku tam vede.
            </p>
          </div>
          <span className="crm-mezera" />
          {me.prava?.includes("crm_nastaveni") && (
            <>
              {/* Staré nabídky bez případu – nabídne se jen když nějaké jsou. */}
              {bezPripadu > 0 && (
                <button
                  className="fm-btn"
                  onClick={() => setMigrace(true)}
                  title="Zavěsit nabídky bez obchodního případu na zákazníka a případ"
                >
                  🔗 Dohledat staré ({bezPripadu})
                </button>
              )}
              <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
                ⚙ Stavy nabídek
              </button>
            </>
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
              placeholder="Hledat podle čísla nebo zákazníka…"
              value={hledat}
              onChange={(e) => setHledat(e.target.value)}
            />
          )}
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{celkem}</b> nabídek
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={kanban.sloupce}
            onPresun={presun}
            onOtevri={otevri}
            dlazdice={(n) => (
              <>
                <div className="crm-dlazdice-hlava">
                  <span className="crm-dlazdice-cislo">{n.cislo || `#${n.id}`}</span>
                  <span className="crm-dlazdice-hodnota">{TYPY[n.typ] || n.typ}</span>
                </div>
                <div className="crm-dlazdice-zakaznik">{n.zakaznik_nazev || "—"}</div>
                <div className="crm-dlazdice-pata">
                  {n.pripad_cislo || "bez případu"}
                  {/* Nespočítaná nabídka není co poslat zákazníkovi – ať je to vidět. */}
                  {n.spocitana ? "" : " · nespočítáno"}
                </div>
                {n.vytvoril_jmeno && (
                  <div className="crm-dlazdice-vlastnik">{n.vytvoril_jmeno}</div>
                )}
              </>
            )}
          />
        ) : (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Typ</th>
                  <th>Zákazník</th>
                  <th>Případ</th>
                  <th>Obchodní stav</th>
                  <th>Výpočet</th>
                  <th>Vytvořil</th>
                  <th>Vytvořeno</th>
                </tr>
              </thead>
              <tbody>
                {radky.map((n) => (
                  <tr key={n.id} onClick={() => otevri(n)}>
                    <td className="crm-silne">{n.cislo || `#${n.id}`}</td>
                    <td>{TYPY[n.typ] || n.typ}</td>
                    <td>{n.zakaznik_nazev || "—"}</td>
                    <td>{n.pripad_cislo || <span className="crm-tise">bez případu</span>}</td>
                    <td>
                      <span className="crm-znacka">{n.stav_nazev}</span>
                    </td>
                    <td>
                      {n.spocitana ? (
                        <span className="crm-znacka crm-barva-ok">spočítáno</span>
                      ) : (
                        <span className="crm-tise">nespočítáno</span>
                      )}
                    </td>
                    <td>{n.vytvoril_jmeno || "—"}</td>
                    <td>{fmtDatum(n.vytvoreno_at)}</td>
                  </tr>
                ))}
                {radky.length === 0 && (
                  <tr>
                    <td colSpan={8} className="crm-prazdno">
                      {hledat ? "Nic nenalezeno." : "Zatím žádné nabídky."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {migrace && (
        <MigraceNabidek onZavri={() => setMigrace(false)} onHotovo={() => nacti(hledat)} />
      )}

      {nastaveniStavu && (
        <StavyNastaveni
          entita="nab"
          onZavri={() => setNastaveniStavu(false)}
          onZmena={() => nacti(hledat)}
        />
      )}
    </Layout>
  );
}
