import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import KalendarMesic from "../components/KalendarMesic";
import KalendarTyden from "../components/KalendarTyden";
import KalendarFiltry from "../components/KalendarFiltry";
import AktivitaModal from "../components/AktivitaModal";
import KalendarDetail from "../components/KalendarDetail";
import SerieDialog from "../components/SerieDialog";
import KalendarMesicniPohled from "../components/KalendarMesicniPohled";
import {
  crmAktivitaSmaz,
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

// Osobní volby v profilu uživatele (přenášejí se mezi počítači).
const KLIC_ZOBRAZENI = "kalendar_zobrazeni";
const KLIC_POHLED = "kalendar_pohled";

const POHLEDY = [
  { klic: "den", nazev: "Den" },
  { klic: "tyden", nazev: "Týden" },
  { klic: "mesic", nazev: "Měsíc" },
];

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
  // Detail nese i „kotvu" = pozici dlaždice, u které se popover ukotví.
  const [pohled, setPohled] = useState("tyden");
  const [detail, setDetail] = useState(null);
  // Modál: {vychozi: {termin, cas}} pro novou, {aktivita} pro úpravu.
  const [modal, setModal] = useState(null);
  // Čekající změna na aktivitě ze série — čeká na volbu rozsahu.
  // {u, zmena, akce: "zmenit"|"smazat"}
  const [serie, setSerie] = useState(null);
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
            if (POHLEDY.some((x) => x.klic === n?.[KLIC_POHLED])) {
              setPohled(n[KLIC_POHLED]);
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

  /** Šipky posouvají to, co je zobrazené: den, týden, nebo měsíc. */
  function posun(o) {
    if (pohled === "mesic") {
      const novy = new Date(mesic.getFullYear(), mesic.getMonth() + o, 1);
      setMesic(novy);
      setPondeli(pondeliTydne(novy));
      return;
    }
    const krok = pohled === "den" ? 1 : 7;
    const novy = posunDnu(pohled === "den" ? new Date(`${vybranyDen}T12:00:00`) : pondeli, o * krok);
    if (pohled === "den") setVybranyDen(isoDen(novy));
    setPondeli(pohled === "den" ? novy : posunDnu(pondeli, o * 7));
    if (novy.getMonth() !== mesic.getMonth() || novy.getFullYear() !== mesic.getFullYear()) {
      setMesic(new Date(novy.getFullYear(), novy.getMonth(), 1));
    }
  }

  function zmenPohled(klic) {
    setPohled(klic);
    ulozNastaveni(KLIC_POHLED, klic).catch(() => {});
    // Denní pohled kreslí mřížku od `pondeli`, takže musí ukazovat vybraný den.
    if (klic === "den") setPondeli(new Date(`${vybranyDen}T12:00:00`));
    if (klic === "tyden") setPondeli(pondeliTydne(new Date(`${vybranyDen}T12:00:00`)));
  }

  function naDnes() {
    const d = new Date();
    setPondeli(pohled === "den" ? d : pondeliTydne(d));
    setMesic(new Date(d.getFullYear(), d.getMonth(), 1));
    setVybranyDen(isoDen(d));
  }

  function vyberDen(iso) {
    setVybranyDen(iso);
    const d = new Date(`${iso}T12:00:00`);
    setPondeli(pohled === "den" ? d : pondeliTydne(d));
  }

  /**
   * Uloží přesun nebo změnu délky z tažení v mřížce.
   *
   * Překreslí se HNED (optimisticky) a teprve pak se volá server — jinak by
   * dlaždice po puštění skočila zpátky a doskočila až s odpovědí, což vypadá
   * jako porucha. Když uložení selže, vrátí se původní stav a řekne se proč.
   */
  /** Změna z popoveru (uzavření s výsledkem, přesun, vrácení do plánu).
   *
   *  U aktivity ze série se nejdřív zeptáme na rozsah — proto ta mezizastávka
   *  v `setSerie`. Bez ní by se každá změna tiše dotkla jen jedné instance
   *  a změna času celé porady by se musela odklikat osmkrát.
   */
  async function zmenAktivitu(id, zmena, u = null) {
    const aktivita = u || detail?.u;
    if (aktivita?.serie_id) {
      setSerie({ u: aktivita, zmena, akce: "zmenit" });
      return;
    }
    await provedZmenu(id, zmena, null);
  }

  async function provedZmenu(id, zmena, rozsah) {
    try {
      await crmAktivitaUprav(id, zmena, rozsah);
      await nacti();
      setChyba(null);
    } catch (e) {
      setChyba(`Změnu se nepodařilo uložit: ${e.message}`);
    }
  }

  async function smazAktivitu(u) {
    if (u.serie_id) {
      setSerie({ u, akce: "smazat" });
      return;
    }
    await provedSmazani(u, null);
  }

  async function provedSmazani(u, rozsah) {
    try {
      await crmAktivitaSmaz(u.id, rozsah);
      setDetail(null);
      await nacti();
    } catch (e) {
      setChyba(`Smazat se nepodařilo: ${e.message}`);
    }
  }

  async function presunAktivitu(u, zmena) {
    // Přetažení instance ze série je typicky „tuhle jednu jinam" — ale ptáme se
    // stejně, protože „porada se od teď posouvá" je taky běžné.
    if (u.serie_id) {
      setSerie({ u, zmena, akce: "zmenit" });
      return;
    }
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

  /** Jen zobrazený den (denní pohled). */
  const vDni = useMemo(() => {
    const iso = isoDen(pondeli);
    return filtrovane.filter((u) => {
      const t = (u.termin || "").slice(0, 10);
      const k = (u.konec || u.termin || "").slice(0, 10);
      return t <= iso && k >= iso;
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

  const titulek = useMemo(() => {
    if (pohled === "mesic") {
      return `${nazevMesice(mesic.getMonth())} ${mesic.getFullYear()}`;
    }
    if (pohled === "den") {
      const d = new Date(`${vybranyDen}T12:00:00`);
      const DNY = ["Pondělí", "Úterý", "Středa", "Čtvrtek", "Pátek", "Sobota", "Neděle"];
      return `${DNY[(d.getDay() + 6) % 7]} ${d.getDate()}. ${nazevMesice(d.getMonth()).toLowerCase()} ${d.getFullYear()}`;
    }
    return `${cisloTydne(pondeli)}. týden – ${nazevMesice(pondeli.getMonth())} ${pondeli.getFullYear()}`;
  }, [pohled, mesic, pondeli, vybranyDen]);

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
          <button onClick={() => posun(-1)} aria-label="Předchozí" title="Předchozí">
            ‹
          </button>
          <button className="kal-dnes" onClick={naDnes}>
            Dnes
          </button>
          <button onClick={() => posun(1)} aria-label="Další" title="Další">
            ›
          </button>
        </div>

        <h1 className="kal-titulek">{titulek}</h1>

        <span className="crm-mezera" />
        <span className="gs-seg">
          {POHLEDY.map((p) => (
            <button
              key={p.klic}
              onClick={() => zmenPohled(p.klic)}
              aria-pressed={pohled === p.klic}
            >
              {p.nazev}
            </button>
          ))}
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
            onUdalost={(u, kotva) => setDetail({ u, kotva })}
            onUlozitFiltr={ulozitFiltr}
            onVycistit={vycisti}
            maFiltr={maFiltr}
          />
        </aside>

        <div className="kal-hlavni">
          {pohled === "mesic" ? (
            <KalendarMesicniPohled
              mesic={mesic}
              udalosti={filtrovane}
              barvy={barvy}
              vybranyDen={vybranyDen}
              onDen={setVybranyDen}
              onTyden={(iso) => {
                setVybranyDen(iso);
                setPondeli(pondeliTydne(new Date(`${iso}T12:00:00`)));
                zmenPohled("tyden");
              }}
              onUdalost={(u, kotva) => setDetail({ u, kotva })}
            />
          ) : (
            <KalendarTyden
              pondeli={pondeli}
              udalosti={pohled === "den" ? vDni : vTydnu}
              barvy={barvy}
              pocetDnu={pohled === "den" ? 1 : 7}
              vybranyDen={vybranyDen}
              onDen={setVybranyDen}
              onUdalost={(u, kotva) => setDetail({ u, kotva })}
              onPrazdno={(iso, cas) => {
                setVybranyDen(iso);
                setModal({ vychozi: { termin: iso, cas } });
              }}
              onPresun={presunAktivitu}
            />
          )}
        </div>
      </div>

      {detail && (
        <KalendarDetail
          udalost={detail.u}
          kotva={detail.kotva}
          barvy={barvy}
          lide={lide}
          onZavri={() => setDetail(null)}
          onZmena={zmenAktivitu}
          onUprav={(u) => {
            setDetail(null);
            setModal({ aktivita: u });
          }}
          onSmaz={smazAktivitu}
        />
      )}

      {serie && (
        <SerieDialog
          popisSerie={serie.u.serie_popis}
          akce={serie.akce}
          onZavri={() => setSerie(null)}
          onVyber={async (rozsah) => {
            const { u, zmena, akce } = serie;
            setSerie(null);
            if (akce === "smazat") await provedSmazani(u, rozsah);
            else await provedZmenu(u.id, zmena, rozsah);
          }}
        />
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
          onSerie={(u, zmena) => setSerie({ u, zmena, akce: "zmenit" })}
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
