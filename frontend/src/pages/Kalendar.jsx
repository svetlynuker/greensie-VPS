import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import KalendarMesic from "../components/KalendarMesic";
import KalendarTyden from "../components/KalendarTyden";
import KalendarFiltry from "../components/KalendarFiltry";
import AktivitaModal from "../components/AktivitaModal";
import {
  crmAktivitaUprav,
  crmFiltrUloz,
  crmFiltry,
  crmKalendar,
  crmKategorieAktivit,
  crmUzivatele,
  logout,
  nactiMe,
  nactiNastaveni,
  ulozNastaveni,
} from "../api";
import { slucBarvy, vychoziBarvy } from "../barvyAktivit";
import { DRUHY_AKTIVITY } from "../crm";
import { cisloTydne, isoDen, nazevMesice, pondeliTydne, posunDnu } from "../datum";
import "../styles/crm.css";
import "../styles/kalendar.css";

/**
 * Kalendář aktivit — týdenní mřížka, čtvercový měsíc a panel filtrů.
 *
 * Vzhled i chování drží předloha v `docs/moduly/Kalendář/`.
 *
 * Načítá se **širší rozsah než zobrazený týden** (celý měsíc kolem), protože
 * čtvercový měsíc potřebuje vědět, ve kterých dnech něco je, a záložka
 * „Nenaplánováno" má smysl jen nad delším obdobím. Jeden dotaz místo tří;
 * přepnutí týdne uvnitř měsíce pak server nevolá vůbec.
 */

// Osobní volba zobrazení v profilu uživatele (přenáší se mezi počítači).
const KLIC_ZOBRAZENI = "kalendar_zobrazeni";

// Druhy, které se v kalendáři nabízejí. Poznámka je zápis do historie bez
// plánování — do mřížky nepatří.
const DRUHY_V_KALENDARI = DRUHY_AKTIVITY.filter((d) => d.klic !== "poznamka");

export default function Kalendar() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [pondeli, setPondeli] = useState(() => pondeliTydne(new Date()));
  const [mesic, setMesic] = useState(() => new Date());
  const [vybranyDen, setVybranyDen] = useState(() => isoDen(new Date()));
  const [udalosti, setUdalosti] = useState([]);
  const [barvy, setBarvy] = useState(() => vychoziBarvy());
  const [kategorie, setKategorie] = useState([]);
  const [lide, setLide] = useState([]);
  const [ulozeneFiltry, setUlozeneFiltry] = useState([]);
  const [detail, setDetail] = useState(null);
  // Modál: {vychozi: {termin, cas}} pro novou, {aktivita} pro úpravu.
  const [modal, setModal] = useState(null);
  const [chyba, setChyba] = useState(null);

  // ---- stav filtrů ----
  const [vybraniLide, setVybraniLide] = useState(() => new Set());
  const [druhy, setDruhy] = useState(() => new Set(DRUHY_V_KALENDARI.map((d) => d.klic)));
  const [vybraneKategorie, setVybraneKategorie] = useState(() => new Set());
  const [schovatRealizovane, setSchovatRealizovane] = useState(false);
  const [zobrazitZrusene, setZobrazitZrusene] = useState(false);

  const rozsahDotazu = useMemo(() => {
    const od = posunDnu(new Date(mesic.getFullYear(), mesic.getMonth(), 1), -7);
    const do_ = posunDnu(new Date(mesic.getFullYear(), mesic.getMonth() + 1, 0), 7);
    return { od: isoDen(od), do: isoDen(do_) };
  }, [mesic]);

  const nacti = useCallback(async () => {
    try {
      const data = await crmKalendar(rozsahDotazu.od, rozsahDotazu.do, [...vybraniLide]);
      setUdalosti(data.udalosti || []);
      setChyba(null);
    } catch (e) {
      setChyba(e.message);
    }
  }, [rozsahDotazu, vybraniLide]);

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
        setVybraniLide(new Set([data.uzivatel.id]));

        nactiNastaveni()
          .then((n) => {
            setBarvy(slucBarvy(n?.kalendar_barvy));
            const z = n?.[KLIC_ZOBRAZENI];
            if (z && typeof z === "object") {
              setSchovatRealizovane(Boolean(z.schovat_realizovane));
              setZobrazitZrusene(Boolean(z.zobrazit_zrusene));
            }
          })
          .catch(() => {});
        crmKategorieAktivit()
          .then(setKategorie)
          .catch(() => setKategorie([]));
        crmUzivatele()
          .then(setLide)
          .catch(() => setLide([]));
        crmFiltry("kalendar")
          .then(setUlozeneFiltry)
          .catch(() => setUlozeneFiltry([]));
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  useEffect(() => {
    if (me && vybraniLide.size) nacti();
  }, [me, nacti, vybraniLide]);

  /** Volby zobrazení jsou nastavení, ne pracovní krok — patří do profilu. */
  function ulozZobrazeni(zmena) {
    ulozNastaveni(KLIC_ZOBRAZENI, {
      schovat_realizovane: schovatRealizovane,
      zobrazit_zrusene: zobrazitZrusene,
      ...zmena,
    }).catch(() => {});
  }

  function posunTyden(oTydny) {
    const novy = posunDnu(pondeli, oTydny * 7);
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

  function vyberDen(iso) {
    setVybranyDen(iso);
    setPondeli(pondeliTydne(new Date(`${iso}T12:00:00`)));
  }

  /**
   * Uloží přesun nebo změnu délky z tažení v mřížce.
   *
   * Překreslí se HNED (optimisticky) a teprve pak se volá server — jinak by
   * dlaždice po puštění skočila zpátky a doskočila až s odpovědí, což vypadá
   * jako porucha. Když uložení selže, vrátí se původní stav a řekne se proč.
   */
  async function presunAktivitu(u, zmena) {
    const puvodni = udalosti;
    setUdalosti((seznam) =>
      seznam.map((x) =>
        x.id === u.id
          ? {
              ...x,
              termin: zmena.termin ?? x.termin,
              konec: zmena.konec ?? x.konec,
              zacatek:
                zmena.cas !== undefined
                  ? `${zmena.termin ?? x.termin}T${zmena.cas.padStart(5, "0")}:00`
                  : x.zacatek,
              delka_min: zmena.delka_min ?? x.delka_min,
            }
          : x
      )
    );
    try {
      await crmAktivitaUprav(u.id, zmena);
      await nacti();
    } catch (e) {
      setUdalosti(puvodni);
      setChyba(`Přesun se nepodařilo uložit: ${e.message}`);
    }
  }

  // ---- filtrování ----
  const filtrovane = useMemo(
    () =>
      (udalosti || []).filter((u) => {
        if (!druhy.has(u.druh)) return false;
        // Blok bez detailu kategorii nezná. Filtrovat ho podle kategorie by
        // znamenalo, že se v cizím kalendáři „vypaří obsazený čas" — proto se
        // takové bloky nechávají vždycky.
        if (vybraneKategorie.size && u.muze_detail && !vybraneKategorie.has(u.kategorie_id)) {
          return false;
        }
        if (schovatRealizovane && u.stav === "realizovano") return false;
        if (!zobrazitZrusene && u.stav === "nekonalo_se") return false;
        return true;
      }),
    [udalosti, druhy, vybraneKategorie, schovatRealizovane, zobrazitZrusene]
  );

  /** Jen to, co zasahuje do zobrazeného týdne (vícedenní může začít dřív). */
  const vTydnu = useMemo(() => {
    const od = isoDen(pondeli);
    const do_ = isoDen(posunDnu(pondeli, 6));
    return filtrovane.filter((u) => {
      const t = (u.termin || "").slice(0, 10);
      const k = (u.konec || u.termin || "").slice(0, 10);
      return t <= do_ && k >= od;
    });
  }, [filtrovane, pondeli]);

  const dnySUdalostmi = useMemo(
    () => new Set(filtrovane.map((u) => (u.termin || "").slice(0, 10))),
    [filtrovane]
  );

  // „Nenaplánováno" = má termín, ale ne hodinu (a není to vícedenní blok).
  const nenaplanovane = useMemo(
    () => filtrovane.filter((u) => u.cely_den && !u.vicedenni && u.muze_detail),
    [filtrovane]
  );

  const maFiltr =
    vybraneKategorie.size > 0 ||
    schovatRealizovane ||
    zobrazitZrusene ||
    druhy.size !== DRUHY_V_KALENDARI.length ||
    vybraniLide.size > 1;

  async function ulozitFiltr() {
    const nazev = window.prompt("Jak se má filtr jmenovat?", "");
    if (!nazev?.trim()) return;
    try {
      // Uložené filtry kalendáře jedou přes stejnou tabulku jako filtry seznamů
      // (entita „kalendar"), takže sdílení i výchozí pohled fungují bez dalšího
      // mechanismu. Celý stav panelu se ukládá jako jedna podmínka — formát
      // seznamových podmínek (pole/operátor/hodnota) by tu neměl co popisovat.
      await crmFiltrUloz("kalendar", {
        nazev: nazev.trim(),
        podminky: [
          {
            pole: "kalendar",
            operator: "je",
            hodnota: JSON.stringify({
              druhy: [...druhy],
              kategorie: [...vybraneKategorie],
              lide: [...vybraniLide],
              schovat_realizovane: schovatRealizovane,
              zobrazit_zrusene: zobrazitZrusene,
            }),
          },
        ],
        razeni: [],
        sdileny: false,
        vychozi: false,
      });
      setUlozeneFiltry(await crmFiltry("kalendar"));
    } catch (e) {
      setChyba(e.message);
    }
  }

  function pouzijFiltr(f) {
    try {
      const stav = JSON.parse(f.podminky?.[0]?.hodnota || "{}");
      if (stav.druhy?.length) setDruhy(new Set(stav.druhy));
      setVybraneKategorie(new Set(stav.kategorie || []));
      if (stav.lide?.length) setVybraniLide(new Set(stav.lide));
      setSchovatRealizovane(Boolean(stav.schovat_realizovane));
      setZobrazitZrusene(Boolean(stav.zobrazit_zrusene));
    } catch {
      setChyba("Uložený filtr se nepodařilo přečíst.");
    }
  }

  function vycisti() {
    setDruhy(new Set(DRUHY_V_KALENDARI.map((d) => d.klic)));
    setVybraneKategorie(new Set());
    setSchovatRealizovane(false);
    setZobrazitZrusene(false);
    setVybraniLide(new Set([me.uzivatel.id]));
    ulozZobrazeni({ schovat_realizovane: false, zobrazit_zrusene: false });
  }

  if (!me) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      {/* ---- horní lišta ---- */}
      <div className="kal-lista-hlavni">
        <select
          className="kal-select"
          value=""
          onChange={(e) => {
            const f = ulozeneFiltry.find((x) => String(x.id) === e.target.value);
            if (f) pouzijFiltr(f);
          }}
          title="Použít uložený filtr"
          aria-label="Moje filtry"
        >
          <option value="">Moje filtry</option>
          {ulozeneFiltry.map((f) => (
            <option key={f.id} value={f.id}>
              {f.nazev}
              {f.sdileny && !f.muj ? ` · ${f.vlastnik_jmeno}` : ""}
            </option>
          ))}
        </select>

        <div className="kal-navigace">
          <button onClick={() => posunTyden(-1)} aria-label="Předchozí týden" title="Předchozí týden">
            ‹
          </button>
          <button className="kal-dnes" onClick={naDnes}>
            Dnes
          </button>
          <button onClick={() => posunTyden(1)} aria-label="Další týden" title="Další týden">
            ›
          </button>
        </div>

        <h1 className="kal-titulek">
          {cisloTydne(pondeli)}. týden – {nazevMesice(pondeli.getMonth())} {pondeli.getFullYear()}
        </h1>

        <span className="crm-mezera" />
        <span className="kal-zobrazeni" title="Zatím jen týdenní pohled">
          Týden
        </span>
        <button
          className="kal-plus"
          onClick={() => setModal({ vychozi: { termin: vybranyDen, cas: "9:00" } })}
          title="Nová aktivita"
          aria-label="Nová aktivita"
        >
          +
        </button>
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      <div className="kal-plocha">
        <aside className="kal-bok">
          <KalendarMesic
            mesic={mesic}
            vybranyDen={vybranyDen}
            zobrazenyTyden={pondeli}
            dnySUdalostmi={dnySUdalostmi}
            onDen={vyberDen}
            onMesic={setMesic}
          />

          <KalendarFiltry
            lide={lide}
            vybraniLide={vybraniLide}
            onLide={setVybraniLide}
            jaId={me.uzivatel.id}
            druhy={druhy}
            onDruhy={setDruhy}
            kategorie={kategorie}
            vybraneKategorie={vybraneKategorie}
            onKategorie={setVybraneKategorie}
            schovatRealizovane={schovatRealizovane}
            onSchovatRealizovane={(v) => {
              setSchovatRealizovane(v);
              ulozZobrazeni({ schovat_realizovane: v });
            }}
            zobrazitZrusene={zobrazitZrusene}
            onZobrazitZrusene={(v) => {
              setZobrazitZrusene(v);
              ulozZobrazeni({ zobrazit_zrusene: v });
            }}
            nenaplanovane={nenaplanovane}
            onUdalost={setDetail}
            onUlozitFiltr={ulozitFiltr}
            onVycistit={vycisti}
            maFiltr={maFiltr}
          />
        </aside>

        <div className="kal-hlavni">
          <KalendarTyden
            pondeli={pondeli}
            udalosti={vTydnu}
            barvy={barvy}
            vybranyDen={vybranyDen}
            onDen={setVybranyDen}
            onUdalost={setDetail}
            onPrazdno={(iso, cas) => {
              setVybranyDen(iso);
              setModal({ vychozi: { termin: iso, cas } });
            }}
            onPresun={presunAktivitu}
          />
        </div>
      </div>

      {/* ---- detail aktivity (plný popover s akcemi přijde v etapě K4c) ---- */}
      {detail && (
        <div className="kal-detail-plast" onClick={() => setDetail(null)}>
          <div className="kal-detail-karta" onClick={(e) => e.stopPropagation()}>
            <div className="kal-detail-hlava">
              <span
                className="kal-detail-ikona"
                style={{ background: detail.kategorie_barva || barvy[detail.druh] || "#d3d9de" }}
              >
                <Ikona
                  jmeno={DRUHY_AKTIVITY.find((d) => d.klic === detail.druh)?.ikona || "kalendar"}
                  velikost={16}
                />
              </span>
              <h2>{detail.nazev || "Aktivita"}</h2>
              <span className="crm-mezera" />
              <button className="crm-zavrit" onClick={() => setDetail(null)} aria-label="Zavřít">
                ✕
              </button>
            </div>

            <div className="kal-detail-telo">
              {detail.muze_detail ? (
                <>
                  {detail.zaznam_nazev && (
                    <div className="kal-detail-stitek">
                      <Ikona jmeno="zakaznici" velikost={13} />
                      {detail.cesta ? (
                        <a className="crm-odkaz" href={detail.cesta}>
                          {detail.zaznam_nazev}
                        </a>
                      ) : (
                        detail.zaznam_nazev
                      )}
                    </div>
                  )}
                  <dl className="crm-udaje" style={{ marginTop: 10 }}>
                    <dt>Termín</dt>
                    <dd>
                      {detail.cely_den
                        ? `${detail.termin} · celý den`
                        : `${detail.termin} · ${detail.zacatek.slice(11, 16)} (${detail.delka_min} min)`}
                      {detail.vicedenni ? ` → ${detail.konec}` : ""}
                    </dd>
                    {detail.kategorie_nazev && (
                      <>
                        <dt>Kategorie</dt>
                        <dd>
                          <span
                            className="kalf-barva-tecka"
                            style={{ background: detail.kategorie_barva }}
                          />{" "}
                          {detail.kategorie_nazev}
                        </dd>
                      </>
                    )}
                    {detail.misto && (
                      <>
                        <dt>Místo</dt>
                        <dd>{detail.misto}</dd>
                      </>
                    )}
                    <dt>Stav</dt>
                    <dd>
                      {detail.stav === "realizovano"
                        ? "Realizováno"
                        : detail.stav === "nekonalo_se"
                          ? "Nekonalo se"
                          : "Naplánováno"}
                      {detail.priorita === "vysoka" ? " · vysoká priorita" : ""}
                    </dd>
                  </dl>
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
                  <div className="kal-detail-akce">
                    <button
                      className="fm-btn"
                      onClick={() => {
                        setModal({ aktivita: detail });
                        setDetail(null);
                      }}
                    >
                      ✎ Upravit
                    </button>
                    <span className="crm-tise">
                      Mám hotovo / Zrušit / Přesunout přidám v další etapě.
                    </span>
                  </div>
                </>
              ) : (
                <p className="crm-tise">
                  {detail.vlastnik_jmeno ? `${detail.vlastnik_jmeno} — ` : ""}
                  v tuhle dobu nemá volno. Podrobnosti téhle aktivity ti appka neukáže.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
      {modal && (
        <AktivitaModal
          vychozi={modal.vychozi}
          aktivita={modal.aktivita}
          jaId={me.uzivatel.id}
          jaJmeno={me.uzivatel.jmeno}
          udalostiDne={udalosti}
          onZmenDen={(iso) => setVybranyDen(iso)}
          onZavri={() => setModal(null)}
          onHotovo={async (ulozena, otevrit) => {
            setModal(null);
            await nacti();
            // „Uložit a otevřít" nechá aktivitu hned na očích – u schůzky, ke
            // které se dopisují body k projednání, je to ta obvyklá cesta.
            if (otevrit && ulozena) {
              setVybranyDen((ulozena.termin || "").slice(0, 10) || vybranyDen);
            }
          }}
        />
      )}
    </Layout>
  );
}
