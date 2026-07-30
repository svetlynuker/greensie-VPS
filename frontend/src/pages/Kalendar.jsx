import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import KalendarMesic from "../components/KalendarMesic";
import KalendarTyden from "../components/KalendarTyden";
import { crmKalendar, logout, nactiMe, nactiNastaveni, ulozNastaveni } from "../api";
import { slucBarvy } from "../barvyAktivit";
import { isoDen, pondeliTydne } from "../datum";
import { DRUHY_AKTIVITY, fmtCas, nazevStavuAktivity } from "../crm";
import "../styles/crm.css";
import "../styles/kalendar.css";

/**
 * Kalendář aktivit — týdenní mřížka a čtvercový měsíc k přeskakování.
 *
 * Načítá se **širší rozsah než zobrazený týden** (celý měsíc kolem), protože
 * čtvercový měsíc potřebuje vědět, ve kterých dnech něco je. Jeden dotaz místo
 * dvou; při přepnutí týdne uvnitř téhož měsíce se pak nemusí volat server.
 *
 * Rozsah hodin (výchozí 8–20) je volba uživatele a ukládá se do jeho profilu —
 * kdo pracuje večer, nemá si ho přepínat po každém přihlášení.
 */

const KLIC_HODINY = "kalendar_hodiny";
const ROZSAHY = {
  pracovni: { odHod: 8, doHod: 20, popis: "8–20" },
  cely: { odHod: 0, doHod: 23, popis: "celý den" },
};

export default function Kalendar() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [pondeli, setPondeli] = useState(() => pondeliTydne(new Date()));
  const [mesic, setMesic] = useState(() => new Date());
  const [vybranyDen, setVybranyDen] = useState(() => isoDen(new Date()));
  const [udalosti, setUdalosti] = useState([]);
  const [barvy, setBarvy] = useState(() => slucBarvy(null));
  const [rozsah, setRozsah] = useState("pracovni");
  const [druhy, setDruhy] = useState(() => new Set(DRUHY_AKTIVITY.map((d) => d.klic)));
  const [detail, setDetail] = useState(null);
  const [chyba, setChyba] = useState(null);

  // Načítá se celý měsíc kolem zobrazeného týdne (a přesah, ať jsou pokryté
  // krajní týdny, které do měsíce zasahují).
  const rozsahDotazu = useMemo(() => {
    const od = new Date(mesic.getFullYear(), mesic.getMonth(), 1);
    od.setDate(od.getDate() - 7);
    const do_ = new Date(mesic.getFullYear(), mesic.getMonth() + 1, 0);
    do_.setDate(do_.getDate() + 7);
    return { od: isoDen(od), do: isoDen(do_) };
  }, [mesic]);

  const nacti = useCallback(async () => {
    try {
      const data = await crmKalendar(rozsahDotazu.od, rozsahDotazu.do);
      setUdalosti(data.udalosti || []);
      setChyba(null);
    } catch (e) {
      setChyba(e.message);
    }
  }, [rozsahDotazu]);

  useEffect(() => {
    nactiMe()
      .then((data) => {
        if (data.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!data.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(data);
        nactiNastaveni()
          .then((n) => {
            setBarvy(slucBarvy(n?.kalendar_barvy));
            if (n?.[KLIC_HODINY] in ROZSAHY) setRozsah(n[KLIC_HODINY]);
          })
          .catch(() => {});
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  useEffect(() => {
    if (me) nacti();
  }, [me, nacti]);

  /** Přepnutí týdne. Když nový týden padne do jiného měsíce, přesune se i ten. */
  function posunTyden(oTydny) {
    const novy = new Date(pondeli);
    novy.setDate(novy.getDate() + oTydny * 7);
    setPondeli(novy);
    if (novy.getMonth() !== mesic.getMonth() || novy.getFullYear() !== mesic.getFullYear()) {
      setMesic(new Date(novy.getFullYear(), novy.getMonth(), 1));
    }
  }

  function naDnes() {
    const d = new Date();
    setPondeli(pondeliTydne(d));
    setMesic(new Date(d.getFullYear(), d.getMonth(), 1));
    setVybranyDen(isoDen(d));
  }

  /** Klik na den v měsíci: přepne týden a označí ten den. */
  function vyberDen(iso) {
    setVybranyDen(iso);
    const d = new Date(`${iso}T12:00:00`);
    setPondeli(pondeliTydne(d));
  }

  function zmenRozsah(klic) {
    setRozsah(klic);
    ulozNastaveni(KLIC_HODINY, klic).catch(() => {});
  }

  function prepniDruh(klic) {
    setDruhy((s) => {
      const n = new Set(s);
      if (n.has(klic)) n.delete(klic);
      else n.add(klic);
      // Prázdný filtr by ukázal prázdný kalendář a vypadal jako chyba —
      // odkliknutí posledního druhu proto vrátí všechny.
      return n.size === 0 ? new Set(DRUHY_AKTIVITY.map((d) => d.klic)) : n;
    });
  }

  const filtrovane = useMemo(
    () => udalosti.filter((u) => druhy.has(u.druh)),
    [udalosti, druhy]
  );

  const dnySUdalostmi = useMemo(
    () => new Set(filtrovane.map((u) => (u.termin || "").slice(0, 10))),
    [filtrovane]
  );

  const tydenPopis = useMemo(() => {
    const ne = new Date(pondeli);
    ne.setDate(ne.getDate() + 6);
    const den = (d) => `${d.getDate()}. ${d.getMonth() + 1}.`;
    return `${den(pondeli)} – ${den(ne)} ${ne.getFullYear()}`;
  }, [pondeli]);

  if (!me) return null;
  const r = ROZSAHY[rozsah] || ROZSAHY.pracovni;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="gs-page-head">
        <div>
          <h1 className="gs-page-h1">Kalendář</h1>
          <p className="gs-page-lead">
            Tvoje aktivity a schůzky. Barvy si nastavíš v{" "}
            <a className="crm-odkaz" href="/nastaveni">
              Nastavení
            </a>
            .
          </p>
        </div>
        <span className="gs-tb-spacer" />
        <button className="fm-btn" onClick={() => posunTyden(-1)} title="Předchozí týden">
          ‹ Týden
        </button>
        <button className="fm-btn" onClick={naDnes} title="Skočit na dnešní týden">
          Dnes
        </button>
        <button className="fm-btn" onClick={() => posunTyden(1)} title="Další týden">
          Týden ›
        </button>
      </div>

      {chyba && (
        <div className="crm-chyba">
          Kalendář se nepodařilo načíst: {chyba}
        </div>
      )}

      <div className="kal-lista">
        <span className="crm-label" style={{ margin: 0 }}>
          {tydenPopis}
        </span>
        <span className="crm-mezera" />

        {/* Rychlé filtry podle druhu (etapa K6 přidá uložené filtry). */}
        <div className="crm-volby">
          {DRUHY_AKTIVITY.map((d) => (
            <button
              key={d.klic}
              className={`crm-pilulka ${druhy.has(d.klic) ? "aktivni" : ""}`}
              onClick={() => prepniDruh(d.klic)}
              title={`Zobrazit/skrýt: ${d.nazev}`}
            >
              <span aria-hidden="true">{d.ikona}</span> {d.nazev}
            </button>
          ))}
        </div>

        <span className="gs-seg">
          <button
            onClick={() => zmenRozsah("pracovni")}
            aria-pressed={rozsah === "pracovni"}
            title="Pracovní hodiny 8–20"
          >
            8–20
          </button>
          <button
            onClick={() => zmenRozsah("cely")}
            aria-pressed={rozsah === "cely"}
            title="Rozbalit na celý den"
          >
            Celý den
          </button>
        </span>
      </div>

      <div className="kal-plocha">
        <aside className="kal-bok">
          <KalendarMesic
            mesic={mesic}
            vybranyDen={vybranyDen}
            dnySUdalostmi={dnySUdalostmi}
            onDen={vyberDen}
            onMesic={(m) => setMesic(m)}
          />

          {detail ? (
            <div className="fm-card kal-detail">
              <div className="gs-karta-hlava">
                <span className="gs-karta-titulek">{detail.nazev || "Událost"}</span>
                <span className="gs-tb-spacer" />
                <button className="crm-zavrit" onClick={() => setDetail(null)} aria-label="Zavřít">
                  ✕
                </button>
              </div>
              {detail.muze_detail ? (
                <>
                  <div className="crm-tise">
                    {detail.cely_den ? "Celý den" : fmtCas(detail.zacatek, detail.delka_min)}
                    {" · "}
                    {nazevStavuAktivity(detail.stav)}
                  </div>
                  {detail.zaznam_nazev && (
                    <div style={{ marginTop: 8, fontSize: 13 }}>
                      {detail.cesta ? (
                        <a className="crm-odkaz" href={detail.cesta}>
                          {detail.zaznam_nazev}
                        </a>
                      ) : (
                        detail.zaznam_nazev
                      )}
                    </div>
                  )}
                  {detail.text && (
                    <p style={{ fontSize: 13, whiteSpace: "pre-wrap", marginTop: 8 }}>
                      {detail.text}
                    </p>
                  )}
                  {detail.vysledek && (
                    <div className="crm-osa-vysledek" style={{ marginTop: 8 }}>
                      <b>{detail.stav === "nekonalo_se" ? "Nekonalo se:" : "Výsledek:"}</b>{" "}
                      {detail.vysledek}
                    </div>
                  )}
                  <p className="crm-tise" style={{ marginTop: 10 }}>
                    Uzavřít aktivitu nebo naplánovat další jde zatím na kartě zákazníka či
                    případu — přímo v kalendáři to přidám v další etapě.
                  </p>
                </>
              ) : (
                <p className="crm-tise">
                  {detail.vlastnik_jmeno ? `${detail.vlastnik_jmeno} — ` : ""}
                  v tuhle dobu nemá volno. Podrobnosti téhle události ti appka neukáže.
                </p>
              )}
            </div>
          ) : (
            <div className="fm-card kal-detail">
              <p className="crm-tise" style={{ margin: 0 }}>
                Klikni na událost, ať se ti tu ukáže detail. Kliknutí do prázdného místa bude
                zakládat novou aktivitu v příští etapě.
              </p>
            </div>
          )}
        </aside>

        <div className="kal-hlavni">
          <KalendarTyden
            pondeli={pondeli}
            udalosti={filtrovane}
            barvy={barvy}
            odHod={r.odHod}
            doHod={r.doHod}
            vybranyDen={vybranyDen}
            onDen={setVybranyDen}
            onUdalost={setDetail}
            onPrazdno={(iso) => setVybranyDen(iso)}
          />
        </div>
      </div>

      {filtrovane.length === 0 && !chyba && (
        <section className="fm-card" style={{ marginTop: 12 }}>
          <div className="gs-prazdno">
            <div className="gs-prazdno-znak">
              <Ikona jmeno="kalendar" velikost={22} />
            </div>
            <h3>V tomhle období nemáš nic naplánovaného</h3>
            <p>
              Aktivity s termínem se sem přidají samy — vznikají u zákazníka nebo u obchodního
              případu na záložce <b>Aktivity a úkoly</b>.
            </p>
          </div>
        </section>
      )}
    </Layout>
  );
}
