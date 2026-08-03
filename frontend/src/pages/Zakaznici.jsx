import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import ImportRaynet from "../components/ImportRaynet";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import KpiPas from "../components/KpiPas";
import OdkazRaynet from "../components/OdkazRaynet";
import ZakaznikFormular from "../components/ZakaznikFormular";
import RychleAkce from "../components/RychleAkce";
import { nactiMe, logout, crmVlastniPole, crmZakaznici } from "../api";
import { POHLEDY_ZAKAZNIKU, fmtDatum } from "../crm";
import usePouzitFiltr from "../pouzitFiltr";
import "../styles/rychleAkce.css";
import "../styles/crm.css";

/**
 * Sekce Zákazníci – dva pohledy nad jednou tabulkou (Leady / Klienti).
 *
 * Seznam nefiltruje podle vlastníka: to dělá backend podle práva `crm_vse`,
 * aby se dvě pravidla viditelnosti nemohla rozejít.
 */
export default function Zakaznici() {
  const { pohled = "lead" } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zakaznici, setZakaznici] = useState(null);
  const [hledat, setHledat] = useState("");
  const [chyba, setChyba] = useState(null);
  const [zaklada, setZaklada] = useState(false);
  // Kolečko „+" umí založit lead i klienta bez ohledu na to, který pohled je
  // otevřený; `null` = vezme se typ podle pohledu (tak to dělá tlačítko nahoře).
  const [zakladaTyp, setZakladaTyp] = useState(null);
  // Vlastní pole označená „v seznamu" se ukazují jako další sloupce tabulky.
  const [sloupce, setSloupce] = useState([]);
  const [importRaynet, setImportRaynet] = useState(false);

  const sekce = POHLEDY_ZAKAZNIKU.find((p) => p.klic === pohled);

  // Filtr a řazení; výchozí řazení klientů je podle názvu (číslo nemají).
  const f = usePouzitFiltr("zakaznik", zakaznici || [], sloupce);

  // KPI nad seznamem (CRM-22) — z vyfiltrovaných řádků, ať sedí s tabulkou.
  // U firem nejde o peníze, ale o to, kde má obchod díru: firma bez případu
  // je kontakt, se kterým se nic neděje, a firma bez vlastníka nemá nikoho,
  // kdo by to změnil.
  const kpi = useMemo(() => {
    const r = f.radky || [];
    return {
      pocet: r.length,
      bezPripadu: r.filter((z) => !z.pocet_pripadu).length,
      bezVlastnika: r.filter((z) => !z.vlastnik_jmeno).length,
    };
  }, [f.radky]);

  const nacti = useCallback(
    async (dotaz = "") => {
      const list = await crmZakaznici({ typ: pohled, hledat: dotaz || undefined });
      setZakaznici(list);
    },
    [pohled]
  );

  useEffect(() => {
    if (!sekce) {
      navigate("/zakaznici/lead", { replace: true });
      return;
    }
    Promise.all([nactiMe(), crmZakaznici({ typ: pohled })])
      .then(([m, list]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setZakaznici(list);
        crmVlastniPole("zakaznik")
          .then((pole) => setSloupce(pole.filter((x) => x.v_seznamu)))
          .catch(() => setSloupce([]));
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
  }, [pohled, sekce, navigate]);

  // Hledání se pouští s prodlevou, ať se neposílá dotaz na každý znak.
  useEffect(() => {
    if (!me) return undefined;
    const t = setTimeout(() => {
      nacti(hledat).catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me, nacti]);

  if (!sekce) return null;
  if (chyba && !zakaznici) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !zakaznici) return null;

  return (
    <Layout
      uzivatel={me.uzivatel}
      akce={
        <>
        {/* Import z Raynetu – bez něj je CRM prázdná kostra. */}
        {me.prava?.includes("crm_nastaveni") && (
          <button className="fm-btn" onClick={() => setImportRaynet(true)}>
            ⬇ Import z Raynetu
          </button>
        )}
        <button className="fm-btn fm-primary" onClick={() => setZaklada(true)}>
          + Nový {pohled === "lead" ? "lead" : "klient"}
        </button>
        </>
      }
    >
      <div className="crm-app ra-misto">
        <div className="crm-zalozky">
          {POHLEDY_ZAKAZNIKU.map((p) => (
            <Link
              key={p.klic}
              to={`/zakaznici/${p.klic}`}
              className={`crm-zalozka ${p.klic === pohled ? "aktivni" : ""}`}
            >
              {p.nazev}
            </Link>
          ))}
        </div>

        <div className="crm-toolbar">
          <input
            className="crm-pole crm-hledani"
            placeholder="Hledat podle názvu, IČO, města nebo e-mailu…"
            value={hledat}
            onChange={(e) => setHledat(e.target.value)}
          />
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{f.radky.length}</b>
            {f.skryto > 0 ? ` z ${zakaznici.length}` : ""}{" "}
            {pohled === "lead" ? "leadů" : "klientů"}
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {/* KPI nad seznamem (CRM-22) */}
        <KpiPas
          zobrazit={kpi.pocet > 0}
          filtrovano={f.podminky.length > 0}
          polozky={[
            { klic: "pocet", hodnota: kpi.pocet, label: pohled === "lead" ? "leadů" : "klientů" },
            kpi.bezPripadu > 0 && {
              klic: "bez_pripadu",
              hodnota: kpi.bezPripadu,
              label: "bez případu",
              tise: true,
              title: "Firmy, u kterých zatím není žádný obchodní případ",
            },
            kpi.bezVlastnika > 0 && {
              klic: "bez_vlastnika",
              hodnota: kpi.bezVlastnika,
              label: "bez vlastníka",
              tise: true,
              title: "Firmy, které nemá nikdo přiřazené",
            },
          ].filter(Boolean)}
        />
        {/* CRM-45 */}
        <OdkazRaynet co="firmy" />

        <FiltrPanel
          entita="zakaznik"
          sloupce={f.sloupce}
          vsechnyRadky={zakaznici}
          podminky={f.podminky}
          razeni={f.razeni}
          onPodminky={f.setPodminky}
          onRazeni={f.setRazeni}
          rozvrzeni={f.rozvrzeni}
          onRozvrzeni={f.ulozRozvrzeni}
        />

        <CrmTabulka
          sloupce={f.sloupceTabulky}
            vsechnySloupce={f.sloupce}
            rozvrzeni={f.rozvrzeni}
            onRozvrzeni={f.ulozRozvrzeni}
          radky={f.radky}
          vsechnyRadky={zakaznici}
          razeni={f.razeni}
          onRazeni={f.setRazeni}
          podminky={f.podminky}
          onPodminky={f.setPodminky}
          exportNazev={pohled === "lead" ? "leady" : "klienti"}
          muzeExportovat={me?.prava?.includes("export")}
          onOtevri={(z) => navigate(`/zakaznici/detail/${z.id}`)}
          vykresli={(z, sl) => {
            if (sl.klic === "nazev") return <span className="crm-silne">{z.nazev}</span>;
            if (sl.klic === "vytvoreno_at") return fmtDatum(z.vytvoreno_at);
            if (sl.klic === "pocet_pripadu") return z.pocet_pripadu || 0;
            if (sl.klic.startsWith("extra:")) return (z.extra_text || {})[sl.klic.slice(6)] ?? "—";
            return z[sl.klic] || "—";
          }}
          prazdneHlaseni={
            hledat || f.podminky.length
              ? "Nic neodpovídá filtru."
              : `Zatím žádní ${pohled === "lead" ? "leadi" : "klienti"}. Založ prvního tlačítkem vpravo nahoře.`
          }
        />
      </div>

      {importRaynet && (
        <ImportRaynet
          onZavri={() => setImportRaynet(false)}
          onHotovo={() => nacti(hledat)}
        />
      )}

      {zaklada && (
        <ZakaznikFormular
          vychoziTyp={zakladaTyp || pohled}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => {
            setZaklada(false);
            setZakladaTyp(null);
          }}
          onHotovo={(novy) => {
            setZaklada(false);
            setZakladaTyp(null);
            navigate(`/zakaznici/detail/${novy.id}`);
          }}
        />
      )}

      {/* Rychlé akce – na přehledu zákazníků má smysl zakládat, ne posílat. */}
      <RychleAkce
        titulek="Rychlé akce"
        akce={[
          {
            klic: "novy-lead",
            znak: "🌱",
            nazev: "Nový lead",
            popis: "Firma, se kterou se teprve začíná",
            onClick: () => {
              setZakladaTyp("lead");
              setZaklada(true);
            },
          },
          {
            klic: "novy-klient",
            znak: "🏢",
            nazev: "Nový klient",
            popis: "Firma, se kterou už obchod běží",
            onClick: () => {
              setZakladaTyp("klient");
              setZaklada(true);
            },
          },
          me.prava?.includes("crm_nastaveni") && {
            klic: "import",
            znak: "⬇",
            nazev: "Import z Raynetu",
            popis: "Natáhnout firmy z Raynetu",
            onClick: () => setImportRaynet(true),
          },
        ]}
      />
    </Layout>
  );
}
