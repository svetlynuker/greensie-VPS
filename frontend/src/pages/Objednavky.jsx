import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import Kanban from "../components/Kanban";
import ZobrazeniPrepinac from "../components/ZobrazeniPrepinac";
import KpiPas from "../components/KpiPas";
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
import { usePritomnost } from "../hooks/usePritomnost";
import { fmtDatum, fmtKc, fmtKcKratce } from "../crm";
import usePouzitFiltr from "../pouzitFiltr";
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
  // Proklik z Přehledu financí (?otevrit=<id>) rovnou otevře kartu objednávky.
  const [hledaneParametry, setHledaneParametry] = useSearchParams();
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

  const f = usePouzitFiltr("obj", radky, sloupce);

  // KPI nad seznamem (CRM-22). Objednávka JE peníze, takže tady součet dává
  // smysl; „bez projektu" je fronta práce, která se ještě nerozjela.
  const kpi = useMemo(() => {
    const r = f.radky || [];
    const soucet = r.reduce((a, o) => a + (Number(o.cena_kc) || 0), 0);
    return {
      pocet: r.length,
      soucet,
      prumer: r.length ? soucet / r.length : 0,
      bezProjektu: r.filter((o) => !o.ma_projekt).length,
    };
  }, [f.radky]);

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

  // ---- Synchronizace mezi lidmi ----
  // Razítko za celý seznam objednávek: jeden levný tik za 8 s přinese podpis
  // poslední změny (včetně přesunu karty v kanbanu), a když se změní, seznam
  // i kanban se natáhnou znovu. Kolečka přítomnosti tu schválně NEJSOU:
  // „pět lidí je v seznamu" je šum a u seznamu se ani neví, kdo drží kterou
  // kartu.
  const { razitko } = usePritomnost({
    entitaTyp: "crm_seznam_obj",
    zapnuto: Boolean(kanban),
  });

  // Rozepsané hledání drží ref, ne závislost efektu: obnovení se musí poslat
  // se STEJNÝM dotazem, jaký má stránka právě teď — jinak by cizí změna
  // člověku zahodila hledání.
  const hledatRef = useRef(hledat);
  hledatRef.current = hledat;

  // První razítko se jen zapamatuje, jinak by se stránka po otevření načetla
  // dvakrát.
  const razitkoRef = useRef(null);
  useEffect(() => {
    if (!razitko) return;
    if (razitkoRef.current === null || razitkoRef.current === razitko) {
      razitkoRef.current = razitko;
      return;
    }
    razitkoRef.current = razitko;
    nacti(hledatRef.current).catch(() => {});
  }, [razitko, nacti]);

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
        const otevrit = hledaneParametry.get("otevrit");
        if (otevrit) {
          setDetail(Number(otevrit));
          // Parametr se z adresy odstraní, ať se karta znovu neotevře
          // po zavření a obnovení stránky.
          setHledaneParametry({}, { replace: true });
        }
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


  return (
    <Layout
      uzivatel={me.uzivatel}
      akce={
        <>
        {me.prava?.includes("crm_nastaveni") && (
          <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
            ⚙ Stavy objednávek
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
            entita="obj"
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
            // Odkaz jen tomu, kdo na Přehled financí smí — jinak by vedl na 403.
            odkaz={
              me.prava?.includes("finance")
                ? { cesta: "/finance", text: "Přehled financí" }
                : undefined
            }
            polozky={[
              { klic: "pocet", hodnota: kpi.pocet, label: "objednávek" },
              { klic: "soucet", pred: "celkem", hodnota: fmtKcKratce(kpi.soucet) },
              { klic: "prumer", pred: "průměr", hodnota: fmtKcKratce(kpi.prumer) },
              kpi.bezProjektu > 0 && {
                klic: "bez_projektu",
                hodnota: kpi.bezProjektu,
                label: "bez projektu",
                tise: true,
                title: "Podepsané objednávky, ke kterým se ještě nerozjela realizace",
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
            exportNazev="objednavky"
            muzeExportovat={me?.prava?.includes("export")}
            onOtevri={(o) => setDetail(o.id)}
            vykresli={(o, sl) => {
              if (sl.klic === "cislo") return <span className="crm-silne">{o.cislo}</span>;
              if (sl.klic === "cena_kc") return fmtKc(o.cena_kc);
              if (sl.klic === "datum_podpisu") return fmtDatum(o.datum_podpisu) || "—";
              if (sl.klic === "datum_dodani") return fmtDatum(o.datum_dodani) || "—";
              if (sl.klic === "stav_nazev")
                return <span className="crm-znacka">{o.stav_nazev}</span>;
              if (sl.klic === "ma_projekt")
                return o.ma_projekt ? (
                  <span className="crm-znacka crm-barva-ok">ano</span>
                ) : (
                  <span className="crm-tise">—</span>
                );
              if (sl.klic === "nabidka_cislo")
                return o.nabidka_cislo || <span className="crm-tise">—</span>;
              if (sl.klic.startsWith("extra:")) return (o.extra_text || {})[sl.klic.slice(6)] ?? "—";
              return o[sl.klic] || "—";
            }}
            prazdneHlaseni={
              hledat || f.podminky.length
                ? "Nic neodpovídá filtru."
                : "Zatím žádné objednávky. Zakládají se z přijaté nabídky na kartě případu."
            }
          />
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
