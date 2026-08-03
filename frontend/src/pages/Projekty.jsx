import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import Kanban from "../components/Kanban";
import ZobrazeniPrepinac from "../components/ZobrazeniPrepinac";
import KpiPas from "../components/KpiPas";
import SablonyNastaveni from "../components/SablonyNastaveni";
import StavyNastaveni from "../components/StavyNastaveni";
import {
  crmProjektStav,
  crmProjekty,
  crmProjektyKanban,
  crmStavy,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum } from "../crm";
import usePouzitFiltr from "../pouzitFiltr";
import "../styles/crm.css";

/**
 * Sekce Projekty – realizace zakázek.
 *
 * Projekt nelze založit odsud: vzniká z objednávky nebo z obchodního případu
 * (zadání Dana), takže tady je jen přehled a posouvání stavů. Klik otevře
 * detail s kroky.
 */
export default function Projekty() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zobrazeni, setZobrazeni] = useState("kanban");
  const [kanban, setKanban] = useState(null);
  const [radky, setRadky] = useState([]);
  const [sloupce, setSloupce] = useState([]);
  const [hledat, setHledat] = useState("");
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [sablony, setSablony] = useState(false);
  const [chyba, setChyba] = useState(null);

  const f = usePouzitFiltr("pro", radky, sloupce);

  // KPI nad seznamem (CRM-22). U realizace nejde o peníze, ale o čas: co je
  // po termínu, se musí řešit dnes, a průměrná hotovost říká, jak daleko
  // projekty celkově jsou.
  const kpi = useMemo(() => {
    const r = f.radky || [];
    return {
      pocet: r.length,
      poTerminu: r.filter((p) => (p.po_terminu || 0) > 0).length,
      hotovoProcent: r.length
        ? Math.round(r.reduce((a, p) => a + (Number(p.procent) || 0), 0) / r.length)
        : 0,
    };
  }, [f.radky]);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, pole] = await Promise.all([
      crmProjektyKanban(),
      crmProjekty({ hledat: dotaz || undefined }),
      crmVlastniPole("pro").catch(() => []),
    ]);
    setKanban(k);
    setRadky(r);
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
        await crmStavy("pro").catch(() => []);
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
      crmProjekty({ hledat: hledat || undefined })
        .then(setRadky)
        .catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me]);

  async function presun(id, novyStav) {
    setChyba(null);
    try {
      await crmProjektStav(id, novyStav);
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
        <button className="fm-btn" onClick={() => setSablony(true)}>
          📋 Šablony kroků
        </button>
        {muzeNastaveni && (
          <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
            ⚙ Stavy projektů
          </button>
        )}
        </>
      }
    >
      <div className="crm-app siroky">
        {/* Přepínač zobrazení, filtry a čísla v jedné liště. */}
        <div className="crm-lista-hlavni">
          <div className="crm-toolbar">
            <ZobrazeniPrepinac hodnota={zobrazeni} onZmena={setZobrazeni} />
            {zobrazeni === "tabulka" && (
              <input
                className="crm-pole crm-hledani"
                placeholder="Hledat podle čísla nebo názvu…"
                value={hledat}
                onChange={(e) => setHledat(e.target.value)}
              />
            )}
            {/* Počet nese KPI pás vedle; tady zbývá jen to, co on neví. */}
            {f.skryto > 0 && (
              <span className="crm-tise crm-pocet">filtr skryl {f.skryto} z {radky.length}</span>
            )}
          </div>

          <FiltrPanel
            entita="pro"
            sloupce={f.sloupce}
            vsechnyRadky={radky}
            podminky={f.podminky}
            razeni={f.razeni}
            onPodminky={f.setPodminky}
            onRazeni={f.setRazeni}
            rozvrzeni={f.rozvrzeni}
            onRozvrzeni={f.ulozRozvrzeni}
          />

          <KpiPas
            zobrazit={kpi.pocet > 0}
            filtrovano={f.podminky.length > 0}
            polozky={[
              { klic: "pocet", hodnota: kpi.pocet, label: "projektů" },
              { klic: "hotovo", pred: "hotovo průměrně", hodnota: `${kpi.hotovoProcent} %` },
              kpi.poTerminu > 0 && {
                klic: "po_terminu",
                hodnota: kpi.poTerminu,
                label: "s krokem po termínu",
                tise: true,
                title: "Projekty, ve kterých je aspoň jeden krok po termínu",
              },
            ].filter(Boolean)}
          />
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {/* KPI nad seznamem (CRM-22) */}
        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={f.filtrujKanban(kanban.sloupce)}
            onPresun={presun}
            onOtevri={(p) => navigate(`/projekty/detail/${p.id}`)}
            dlazdice={(p) => (
              <>
                <div className="crm-dlazdice-hlava">
                  <span className="crm-dlazdice-cislo">{p.cislo}</span>
                  {p.kroku > 0 && (
                    <span className="crm-dlazdice-hodnota">
                      {p.hotovo}/{p.kroku}
                    </span>
                  )}
                </div>
                <div className="crm-dlazdice-zakaznik">{p.zakaznik_nazev || "—"}</div>
                {p.nazev && <div className="crm-dlazdice-nazev">{p.nazev}</div>}
                {/* Postup kroků na první pohled – to je u realizace to hlavní. */}
                {p.kroku > 0 && (
                  <div className="crm-pruh">
                    <span style={{ width: `${p.procent}%` }} />
                  </div>
                )}
                <div className="crm-dlazdice-pata">
                  {p.nejblizsi_termin ? `nejblíž ${fmtDatum(p.nejblizsi_termin)}` : "bez termínu"}
                  {p.po_terminu > 0 && (
                    <span className="crm-po-terminu"> · {p.po_terminu} po termínu</span>
                  )}
                </div>
              </>
            )}
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
            exportNazev="projekty"
            muzeExportovat={me?.prava?.includes("export")}
            onOtevri={(p) => navigate(`/projekty/detail/${p.id}`)}
            vykresli={(p, sl) => {
              if (sl.klic === "cislo") return <span className="crm-silne">{p.cislo}</span>;
              if (sl.klic === "stav_nazev")
                return <span className="crm-znacka">{p.stav_nazev}</span>;
              if (sl.klic === "procent")
                return p.kroku > 0 ? `${p.hotovo}/${p.kroku} (${p.procent} %)` : "—";
              if (sl.klic === "po_terminu")
                return p.po_terminu > 0 ? (
                  <span className="crm-po-terminu">{p.po_terminu}</span>
                ) : (
                  "—"
                );
              if (sl.klic === "nejblizsi_termin") return fmtDatum(p.nejblizsi_termin) || "—";
              if (sl.klic === "objednavka_cislo")
                return p.objednavka_cislo || <span className="crm-tise">—</span>;
              if (sl.klic.startsWith("extra:")) return (p.extra_text || {})[sl.klic.slice(6)] ?? "—";
              return p[sl.klic] || "—";
            }}
            prazdneHlaseni={
              hledat || f.podminky.length
                ? "Nic neodpovídá filtru."
                : "Zatím žádné projekty. Zakládají se z objednávky nebo z karty případu."
            }
          />
        )}
      </div>

      {nastaveniStavu && (
        <StavyNastaveni
          entita="pro"
          onZavri={() => setNastaveniStavu(false)}
          onZmena={() => nacti(hledat)}
        />
      )}

      {sablony && (
        <SablonyNastaveni
          muzeEditovat={muzeNastaveni}
          onZavri={() => setSablony(false)}
        />
      )}
    </Layout>
  );
}
