import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import CrmTabulka from "../components/CrmTabulka";
import FiltrPanel from "../components/FiltrPanel";
import KpiPas from "../components/KpiPas";
import { nactiMe, logout, crmKontakty } from "../api";
import { fmtDatum } from "../crm";
import usePouzitFiltr from "../pouzitFiltr";
import "../styles/crm.css";

/**
 * Číselník Kontaktní osoby – všichni lidé u zákazníků na jednom místě.
 *
 * Data jsou tatáž jako v panelu kontaktů na kartě zákazníka; tohle je jen
 * pohled napříč firmami. Druhá tabulka lidí by znamenala, že se opravený
 * telefon objeví jen na jednom místě.
 *
 * Seznam nefiltruje podle vlastníka: to dělá backend (kdo nevidí firmu, nevidí
 * ani její lidi), aby se dvě pravidla viditelnosti nemohla rozejít.
 */
export default function KontaktniOsoby() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [kontakty, setKontakty] = useState(null);
  const [hledat, setHledat] = useState("");
  const [chyba, setChyba] = useState(null);

  // Typ firmy jako čitelný text: filtr i tabulka pracují s tím, co je v řádku,
  // a „lead“ na obrazovce nikomu nic neřekne.
  const radky = useMemo(
    () =>
      (kontakty || []).map((k) => ({
        ...k,
        zakaznik_typ_nazev: k.zakaznik_typ === "klient" ? "Klient" : "Lead",
      })),
    [kontakty]
  );

  const f = usePouzitFiltr("kontakt", radky);

  // KPI: kde je v adresáři díra. Osoba bez e-mailu se nedá oslovit poštou
  // a firma bez hlavního kontaktu znamená, že OZ nikdo nenapoví, komu volat.
  const kpi = useMemo(() => {
    const r = f.radky || [];
    const firmyBezHlavniho = new Set();
    const firmy = new Map();
    for (const k of r) {
      if (!firmy.has(k.zakaznik_id)) firmy.set(k.zakaznik_id, false);
      if (k.hlavni) firmy.set(k.zakaznik_id, true);
    }
    for (const [id, maHlavni] of firmy) if (!maHlavni) firmyBezHlavniho.add(id);
    return {
      pocet: r.length,
      firmy: firmy.size,
      bezEmailu: r.filter((k) => !k.email).length,
      bezHlavniho: firmyBezHlavniho.size,
    };
  }, [f.radky]);

  const nacti = useCallback(async (dotaz = "") => {
    setKontakty(await crmKontakty({ hledat: dotaz || undefined }));
  }, []);

  useEffect(() => {
    Promise.all([nactiMe(), crmKontakty()])
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
        setKontakty(list);
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
  }, [navigate]);

  // Hledání s prodlevou, ať se neposílá dotaz na každý znak.
  useEffect(() => {
    if (!me) return undefined;
    const t = setTimeout(() => {
      nacti(hledat).catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me, nacti]);

  if (chyba && !kontakty) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !kontakty) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app">
        <div className="crm-toolbar">
          <input
            className="crm-pole crm-hledani"
            placeholder="Hledat podle jména, firmy, funkce, telefonu nebo e-mailu…"
            value={hledat}
            onChange={(e) => setHledat(e.target.value)}
          />
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{f.radky.length}</b>
            {f.skryto > 0 ? ` z ${radky.length}` : ""} osob
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <KpiPas
          zobrazit={kpi.pocet > 0}
          filtrovano={f.podminky.length > 0}
          polozky={[
            { klic: "pocet", hodnota: kpi.pocet, label: "osob" },
            { klic: "firmy", hodnota: kpi.firmy, label: "firem", tise: true },
            kpi.bezEmailu > 0 && {
              klic: "bez_emailu",
              hodnota: kpi.bezEmailu,
              label: "bez e-mailu",
              tise: true,
              title: "Osoby, kterým nejde napsat — chybí adresa",
            },
            kpi.bezHlavniho > 0 && {
              klic: "bez_hlavniho",
              hodnota: kpi.bezHlavniho,
              label: "firem bez hlavního kontaktu",
              tise: true,
              title: "Firmy, u kterých appka nenapoví, komu volat první",
            },
          ].filter(Boolean)}
        />

        <FiltrPanel
          entita="kontakt"
          sloupce={f.sloupce}
          vsechnyRadky={radky}
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
          vsechnyRadky={radky}
          razeni={f.razeni}
          onRazeni={f.setRazeni}
          podminky={f.podminky}
          onPodminky={f.setPodminky}
          exportNazev="kontaktni-osoby"
          onOtevri={(k) => navigate(`/kontakty/detail/${k.id}`)}
          vykresli={(k, sl) => {
            if (sl.klic === "jmeno") return <span className="crm-silne">{k.jmeno}</span>;
            if (sl.klic === "zakaznik_nazev") {
              // Proklik na firmu přímo z řádku; `stopPropagation`, ať kliknutí
              // neotevře zároveň kartu osoby.
              return (
                <Link
                  to={`/zakaznici/detail/${k.zakaznik_id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="crm-odkaz"
                >
                  {k.zakaznik_nazev}
                </Link>
              );
            }
            if (sl.klic === "hlavni")
              return k.hlavni ? <span className="crm-znacka crm-barva-ok">hlavní</span> : "—";
            if (sl.klic === "posledni_email_at")
              return k.posledni_email_at ? fmtDatum(k.posledni_email_at) : "—";
            if (sl.klic === "vytvoreno_at") return fmtDatum(k.vytvoreno_at);
            if (sl.klic === "pocet_emailu") return k.pocet_emailu || 0;
            return k[sl.klic] || "—";
          }}
          prazdneHlaseni={
            hledat || f.podminky.length
              ? "Nic neodpovídá filtru."
              : "Zatím žádné kontaktní osoby. Zakládají se na kartě zákazníka."
          }
        />
      </div>
    </Layout>
  );
}
