import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
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
import pouzitFiltr from "../pouzitFiltr";
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

  // Jeden filtr pro tabulku i kanban.
  const f = pouzitFiltr("nab", radky);

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
            <b>{f.radky.length}</b>
            {f.skryto > 0 ? ` z ${radky.length}` : ""} nabídek
          </span>
        </div>

        <FiltrPanel
          entita="nab"
          sloupce={f.sloupce}
          vsechnyRadky={radky}
          podminky={f.podminky}
          razeni={f.razeni}
          onPodminky={f.setPodminky}
          onRazeni={f.setRazeni}
        />

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={f.filtrujKanban(kanban.sloupce)}
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
          <CrmTabulka
            sloupce={f.sloupce}
            radky={f.radky}
            vsechnyRadky={radky}
            razeni={f.razeni}
            onRazeni={f.setRazeni}
            podminky={f.podminky}
            onPodminky={f.setPodminky}
            exportNazev="nabidky"
            onOtevri={otevri}
            vykresli={(n, sl) => {
              if (sl.klic === "cislo")
                return <span className="crm-silne">{n.cislo || `#${n.id}`}</span>;
              if (sl.klic === "typ") return TYPY[n.typ] || n.typ;
              if (sl.klic === "pripad_cislo")
                return n.pripad_cislo || <span className="crm-tise">bez případu</span>;
              if (sl.klic === "stav_nazev")
                return <span className="crm-znacka">{n.stav_nazev}</span>;
              if (sl.klic === "spocitana")
                return n.spocitana ? (
                  <span className="crm-znacka crm-barva-ok">spočítáno</span>
                ) : (
                  <span className="crm-tise">nespočítáno</span>
                );
              if (sl.klic === "vytvoreno_at") return fmtDatum(n.vytvoreno_at);
              return n[sl.klic] || "—";
            }}
            prazdneHlaseni={
              hledat || f.podminky.length ? "Nic neodpovídá filtru." : "Zatím žádné nabídky."
            }
          />
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
