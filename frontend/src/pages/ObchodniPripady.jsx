import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import Kanban from "../components/Kanban";
import PripadFormular from "../components/PripadFormular";
import StavyNastaveni from "../components/StavyNastaveni";
import DuvodProhry from "../components/DuvodProhry";
import {
  crmKategorie,
  crmPripadStav,
  crmPripady,
  crmPripadyKanban,
  crmStavy,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, fmtKcKratce, nazvyKategorii } from "../crm";
import pouzitFiltr from "../pouzitFiltr";
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
  const [kategorie, setKategorie] = useState([]);
  const [hledat, setHledat] = useState("");
  const [novy, setNovy] = useState(false);
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [prohra, setProhra] = useState(null); // {pripadId, stav}
  const [sloupce, setSloupce] = useState([]);
  const [chyba, setChyba] = useState(null);

  // Filtr a řazení platí zároveň pro tabulku i kanban (jeden stav pro obojí).
  const f = pouzitFiltr("op", radky, sloupce);

  // KPI nad seznamem (CRM-22). Počítá se z VYFILTROVANÝCH řádků, ne ze všech —
  // jinak by čísla nad tabulkou nesouhlasila s tím, co je v ní vidět.
  const kpi = useMemo(() => {
    const r = f.radky || [];
    const hodnoty = r.map((x) => Number(x.hodnota_kc) || 0);
    const soucet = hodnoty.reduce((a, b) => a + b, 0);
    return {
      pocet: r.length,
      soucet,
      prumer: r.length ? soucet / r.length : 0,
      bezHodnoty: r.filter((x) => !x.hodnota_kc).length,
    };
  }, [f.radky]);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, s, pole, kat] = await Promise.all([
      crmPripadyKanban(),
      crmPripady({ hledat: dotaz || undefined }),
      crmStavy("op"),
      crmVlastniPole("op").catch(() => []),
      // Kategorie jsou konfigurovatelné (CRM-03) – tabulka i kanban z nich
      // překládají klíč na název.
      crmKategorie().catch(() => []),
    ]);
    setKanban(k);
    setRadky(r);
    setStavy(s);
    setSloupce(pole.filter((x) => x.v_seznamu));
    setKategorie(kat);
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
            <b>{f.radky.length}</b>
            {f.skryto > 0 ? ` z ${radky.length}` : ""} případů
            {f.skryto > 0 && <span className="crm-tise"> (filtr skryl {f.skryto})</span>}
          </span>
        </div>

        <FiltrPanel
          entita="op"
          sloupce={f.sloupce}
          vsechnyRadky={radky}
          podminky={f.podminky}
          razeni={f.razeni}
          onPodminky={f.setPodminky}
          onRazeni={f.setRazeni}
        />

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {/* KPI nad seznamem (CRM-22). Reaguje na filtr — proto „z vyfiltrovaných". */}
        {kpi.pocet > 0 && (
          <div className="crm-kpi-pas">
            <span>
              <b>{kpi.pocet}</b> případů
              {f.podminky.length ? " (po filtru)" : ""}
            </span>
            <span>
              celkem <b>{fmtKcKratce(kpi.soucet)}</b>
            </span>
            <span>
              průměr <b>{fmtKcKratce(kpi.prumer)}</b>
            </span>
            {kpi.bezHodnoty > 0 && (
              <span className="crm-tise" title="Případy bez hodnoty se do součtu nepočítají">
                {kpi.bezHodnoty}× bez hodnoty
              </span>
            )}
            <span className="crm-mezera" />
            <a className="crm-odkaz" href="/prehled-obchodu">
              Přehled obchodu →
            </a>
          </div>
        )}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={f.filtrujKanban(kanban.sloupce)}
            onPresun={presun}
            onOtevri={(z) => navigate(`/pripady/detail/${z.id}`)}
            kategorie={kategorie}
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
            exportNazev="obchodni-pripady"
            onOtevri={(p) => navigate(`/pripady/detail/${p.id}`)}
            vykresli={(p, sl) => {
              if (sl.klic === "cislo") return <span className="crm-silne">{p.cislo}</span>;
              if (sl.klic === "kategorie") return nazvyKategorii(p.kategorie, kategorie) || "—";
              if (sl.klic === "stav_nazev")
                return <span className="crm-znacka">{p.stav_nazev}</span>;
              if (sl.klic === "hodnota_kc") return fmtKc(p.hodnota_kc);
              if (sl.klic === "pravdepodobnost")
                return p.pravdepodobnost != null ? `${p.pravdepodobnost} %` : "—";
              if (sl.klic === "predpokladane_uzavreni")
                return fmtDatum(p.predpokladane_uzavreni) || "—";
              if (sl.klic.startsWith("extra:"))
                return (p.extra_text || {})[sl.klic.slice(6)] ?? "—";
              return p[sl.klic] || "—";
            }}
            prazdneHlaseni={
              hledat || f.podminky.length
                ? "Nic neodpovídá filtru."
                : "Zatím žádné případy."
            }
          />
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
