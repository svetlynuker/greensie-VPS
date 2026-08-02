import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import Kanban from "../components/Kanban";
import PripadFormular from "../components/PripadFormular";
import StavyNastaveni from "../components/StavyNastaveni";
import DuvodProhry from "../components/DuvodProhry";
import HromadneAkce from "../components/HromadneAkce";
import KpiPas from "../components/KpiPas";
import OdkazRaynet from "../components/OdkazRaynet";
import RychleAkce from "../components/RychleAkce";
import {
  crmKategorie,
  crmPripadStav,
  crmPripady,
  crmPripadyKanban,
  crmStavy,
  crmUzivatele,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, fmtKcKratce, nazvyKategorii } from "../crm";
import usePouzitFiltr from "../pouzitFiltr";
import "../styles/crm.css";
import "../styles/rychleAkce.css";

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
  const [vybrane, setVybrane] = useState([]);
  const [lide, setLide] = useState([]);
  const [hledat, setHledat] = useState("");
  const [novy, setNovy] = useState(false);
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [prohra, setProhra] = useState(null); // {pripadId, stav}
  const [sloupce, setSloupce] = useState([]);
  const [chyba, setChyba] = useState(null);
  // Co udělala automatizace (CRM-31) při poslední hromadné změně stavu.
  const [automatika, setAutomatika] = useState([]);

  // Filtr a řazení platí zároveň pro tabulku i kanban (jeden stav pro obojí).
  const f = usePouzitFiltr("op", radky, sloupce);

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
    crmUzivatele()
      .then(setLide)
      .catch(() => setLide([]));
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
    <Layout
      uzivatel={me.uzivatel}
      akce={
        <>
          {muzeNastaveni && (
            <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
              ⚙ Stavy pipeline
            </button>
          )}
          <button className="fm-btn fm-primary" onClick={() => setNovy(true)}>
            + Nový případ
          </button>
        </>
      }
    >
      <div className="crm-app siroky ra-misto">
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
          rozvrzeni={f.rozvrzeni}
          onRozvrzeni={f.ulozRozvrzeni}
          mojeJmeno={me?.uzivatel?.jmeno || ""}
          otevreneStavy={stavy.filter((s) => s.druh === "otevreny").map((s) => s.nazev)}
        />

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {/* CRM-31: co při hromadné změně stavu udělala automatika. Bez téhle
            hlášky by objednávky vznikaly tiše a člověk by nevěděl, že už je
            nemá zakládat sám. */}
        {automatika.length > 0 && (
          <div className="crm-hlaska-automatika">
            <b>Automatizace:</b> {automatika.join(" · ")}
          </div>
        )}

        {/* KPI nad seznamem (CRM-22). Reaguje na filtr — proto „z vyfiltrovaných". */}
        <KpiPas
          zobrazit={kpi.pocet > 0}
          filtrovano={f.podminky.length > 0}
          odkaz={{ cesta: "/prehled-obchodu", text: "Přehled obchodu" }}
          polozky={[
            { klic: "pocet", hodnota: kpi.pocet, label: "případů" },
            { klic: "soucet", pred: "celkem", hodnota: fmtKcKratce(kpi.soucet) },
            { klic: "prumer", pred: "průměr", hodnota: fmtKcKratce(kpi.prumer) },
            kpi.bezHodnoty > 0 && {
              klic: "bez",
              hodnota: `${kpi.bezHodnoty}×`,
              label: "bez hodnoty",
              tise: true,
              title: "Případy bez hodnoty se do součtu nepočítají",
            },
          ].filter(Boolean)}
        />
        {/* CRM-45: appka nemá historii — bez téhle věty vypadá součet jako propad. */}
        <OdkazRaynet />

        <HromadneAkce
          entita="op"
          vybrane={vybrane}
          lide={lide}
          stavy={stavy}
          onZrus={() => setVybrane([])}
          onHotovo={async (out) => {
            setVybrane([]);
            setAutomatika(out?.automatika || []);
            await nacti(hledat);
          }}
        />

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={f.filtrujKanban(kanban.sloupce)}
            onPresun={presun}
            onOtevri={(z) => navigate(`/pripady/detail/${z.id}`)}
            kategorie={kategorie}
          />
        ) : (
          <CrmTabulka
            sloupce={f.sloupceTabulky}
            vsechnySloupce={f.sloupce}
            rozvrzeni={f.rozvrzeni}
            onRozvrzeni={f.ulozRozvrzeni}
            radky={f.radky}
            vsechnyRadky={radky}
            razeni={f.razeni}
            onRazeni={f.setRazeni}
            podminky={f.podminky}
            onPodminky={f.setPodminky}
            exportNazev="obchodni-pripady"
            vybrane={vybrane}
            onVybrane={setVybrane}
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

      {/* Na přehledu případů je relevantní zakládat případ; e-mail ne — není
          jasné, komu by se posílal. */}
      <RychleAkce
        titulek="Rychlé akce"
        akce={[
          {
            klic: "novy-pripad",
            znak: "📁",
            nazev: "Nový obchodní případ",
            popis: "Zakázka pro existující firmu",
            onClick: () => setNovy(true),
          },
          {
            klic: "novy-zakaznik",
            znak: "🏢",
            nazev: "Nový zákazník",
            popis: "Firma v CRM ještě není",
            onClick: () => navigate("/zakaznici/lead"),
          },
          me.prava?.includes("crm_nastaveni") && {
            klic: "stavy",
            znak: "⚙",
            nazev: "Nastavení stavů",
            popis: "Sloupce kanbanu",
            onClick: () => setNastaveniStavu(true),
          },
        ]}
      />
    </Layout>
  );
}
