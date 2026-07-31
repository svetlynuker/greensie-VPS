// Editor nabídkového výstupu: tři panely (paleta – papír – vlastnosti).
//
// Papír je natvrdo A4 na výšku a stránek je tolik, kolik si obchodník založí.
// Prvky se po něm volně posouvají se snapem na mřížku, text se píše přímo
// v nich. Datový model i operace jsou ve `src/vystup/`, tady se jen skládá
// obrazovka a řeší se komunikace se serverem.

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import Lista from "../components/vystup/Lista";
import Paleta from "../components/vystup/Paleta";
import Papir from "../components/vystup/Papir";
import Vlastnosti from "../components/vystup/Vlastnosti";
import {
  logout,
  nabidkaVystup,
  nabidkaVystupSablonaSmaz,
  nabidkaVystupSablonaUloz,
  nabidkaVystupSablony,
  nabidkaVystupUloz,
  nactiMe,
} from "../api";
import { useEditorVystupu } from "../vystup/editor";
import "../styles/nabidkovac.css";
import "../styles/vystup.css";

const TYP_NAZEV = { ppa: "PPA", peak_shaving: "Peak shaving", kombinace: "Kombinace opatření" };

export default function NabidkaVystupStranka() {
  const { id, typ } = useParams();
  const navigate = useNavigate();

  const [me, setMe] = useState(null);
  const [data, setData] = useState(null);
  const [pripraveno, setPripraveno] = useState(false);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [neulozeno, setNeulozeno] = useState(false);
  const [zoom, setZoom] = useState(0.8);
  const [aktivniStranka, setAktivniStranka] = useState(null);
  const [sablony, setSablony] = useState({ sablony: [], nabidky: [] });
  const [panely, setPanely] = useState({ vlevo: true, vpravo: true });

  const plochaRef = useRef(null);

  const onZmenaStavu = useCallback(() => {
    setNeulozeno(true);
    setZprava(null);
  }, []);

  const editor = useEditorVystupu({ pocatecni: null, onZmenaStavu });

  // ---- načtení ----
  useEffect(() => {
    let zruseno = false;
    Promise.all([nactiMe(), nabidkaVystup(id, typ)])
      .then(([m, d]) => {
        if (zruseno) return;
        if (m.musi_zmenit_heslo) return navigate("/zmena-hesla");
        if (!m.prava?.includes("nabidkovac")) return navigate("/rozcestnik");
        setMe(m);
        setData(d);
        editor.nahradKonfiguraci(d.konfigurace);
        setAktivniStranka(d.konfigurace?.stranky?.[0]?.id || null);
        setNeulozeno(false);
        setPripraveno(true);
      })
      .catch((e) => {
        if (zruseno) return;
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
    return () => {
      zruseno = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, typ]);

  useEffect(() => {
    nabidkaVystupSablony(typ, id)
      .then(setSablony)
      .catch(() => setSablony({ sablony: [], nabidky: [] }));
  }, [id, typ]);

  // Varování před zavřením s neuloženými změnami – rozvržení je práce na
  // desítky minut a ztratit ho omylem by bolelo.
  useEffect(() => {
    if (!neulozeno) return undefined;
    const hlidac = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", hlidac);
    return () => window.removeEventListener("beforeunload", hlidac);
  }, [neulozeno]);

  // Která stránka je „aktivní" (pro tlačítka lišty) – ta, co je nejvíc vidět.
  useEffect(() => {
    const plocha = plochaRef.current;
    if (!plocha || !pripraveno) return undefined;
    const pozorovatel = new IntersectionObserver(
      (zaznamy) => {
        const videna = zaznamy
          .filter((z) => z.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (videna?.target?.dataset?.strankaId) {
          setAktivniStranka(videna.target.dataset.strankaId);
        }
      },
      { root: plocha, threshold: [0.1, 0.5, 0.9] }
    );
    for (const el of plocha.querySelectorAll("[data-stranka-id]")) pozorovatel.observe(el);
    return () => pozorovatel.disconnect();
  }, [pripraveno, editor.konfigurace?.stranky?.length]);

  function skocNaStranku(strankaId) {
    setAktivniStranka(strankaId);
    const el = plochaRef.current?.querySelector(`[data-stranka-id="${strankaId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---- ukládání ----
  async function uloz() {
    setUklada(true);
    setChyba(null);
    setZprava(null);
    try {
      const d = await nabidkaVystupUloz(id, typ, editor.konfigurace);
      setData(d);
      // Server vrací pročištěnou podobu – přebíráme ji, ať editor ukazuje
      // přesně to, co je uložené (třeba po odstranění nepovolené značky).
      editor.nahradKonfiguraci(d.konfigurace, { vymazHistorii: false });
      setNeulozeno(false);
      setZprava("Uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function obnovVychozi() {
    if (
      !window.confirm(
        "Zahodit tohle rozvržení a začít od výchozí předlohy? Uloží se až tlačítkem Uložit."
      )
    ) {
      return;
    }
    setChyba(null);
    try {
      const d = await nabidkaVystup(id, typ, true);
      setData(d);
      editor.nahradKonfiguraci(d.konfigurace);
      setNeulozeno(true);
      setZprava("Načtena výchozí předloha – ulož ji tlačítkem Uložit.");
    } catch (e) {
      setChyba(e.message);
    }
  }

  function pouzijSablonu(hodnota) {
    if (!hodnota) return;
    const [zdroj, sablonaId] = hodnota.split(":");
    if (zdroj === "vychozi") {
      obnovVychozi();
      return;
    }
    const nalez =
      zdroj === "sablona"
        ? sablony.sablony.find((s) => String(s.id) === sablonaId && s.pouzitelna !== false)
        : sablony.nabidky.find((n) => String(n.nabidka_id) === sablonaId);
    if (!nalez) return;
    const popis = zdroj === "sablona" ? `šablonu „${nalez.nazev}"` : `rozvržení z „${nalez.nazev}"`;
    if (!window.confirm(`Použít ${popis}? Přepíše se rozvržení téhle nabídky.`)) return;
    editor.nahradKonfiguraci(nalez.konfigurace);
    setNeulozeno(true);
    setZprava("Šablona použita – ulož ji tlačítkem Uložit.");
  }

  async function ulozJakoSablonu() {
    const nazev = window.prompt("Název šablony (stejný název existující přepíše):", "");
    if (nazev === null) return;
    if (!nazev.trim()) {
      setChyba("Šablona musí mít název.");
      return;
    }
    setChyba(null);
    try {
      await nabidkaVystupSablonaUloz(typ, nazev.trim(), editor.konfigurace);
      setSablony(await nabidkaVystupSablony(typ, id));
      setZprava(`Šablona „${nazev.trim()}" uložena.`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smazSablonu(sablona) {
    if (!window.confirm(`Smazat šablonu „${sablona.nazev}"?`)) return;
    try {
      await nabidkaVystupSablonaSmaz(typ, sablona.id);
      setSablony(await nabidkaVystupSablony(typ, id));
      setZprava(`Šablona „${sablona.nazev}" smazána.`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !data) {
    return <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>;
  }
  if (!me || !data || !pripraveno || !editor.konfigurace) return null;

  return (
    <div className="vystup-page">
      <Lista
        editor={editor}
        nazev={`Nabídka pro zákazníka · ${TYP_NAZEV[typ] || typ}`}
        zoom={zoom}
        onZoom={setZoom}
        onZpetNaNabidku={() => navigate(`/nabidkovac/nabidka/${id}`)}
        onUloz={uloz}
        onTisk={() => window.print()}
        uklada={uklada}
        neulozeno={neulozeno}
        zprava={zprava}
        chyba={chyba}
        aktivniStranka={aktivniStranka}
        onSkocNaStranku={skocNaStranku}
        deti={
          <Sablony
            sablony={sablony}
            onPouzij={pouzijSablonu}
            onUloz={ulozJakoSablonu}
            onSmaz={smazSablonu}
          />
        }
      />

      {!data.existuje_reseni && (
        <div className="nb-warn np" style={{ margin: "8px 16px 0" }}>
          <span>⚠️</span>
          <span>
            Pro tuhle nabídku zatím není spočítané řešení „{TYP_NAZEV[typ] || typ}". Rozvržení
            si připravit můžeš, čísla se doplní po spuštění výpočtu v detailu nabídky.
          </span>
        </div>
      )}

      <div
        className={
          "vystup-layout" +
          (panely.vlevo ? "" : " bez-leveho") +
          (panely.vpravo ? "" : " bez-praveho")
        }
      >
        <aside className={"vystup-panel vlevo np" + (panely.vlevo ? "" : " zabaleny")}>
          <button
            className="panel-prepinac"
            onClick={() => setPanely((p) => ({ ...p, vlevo: !p.vlevo }))}
            title={panely.vlevo ? "Skrýt paletu" : "Zobrazit paletu"}
          >
            {panely.vlevo ? "‹" : "›"}
          </button>
          {panely.vlevo && (
            <div className="panel-obsah">
              <Paleta editor={editor} katalog={data.katalog} hodnoty={data.hodnoty} />
            </div>
          )}
        </aside>

        <main className="vystup-plocha" ref={plochaRef}>
          <Papir konfigurace={editor.konfigurace} data={data} editor={editor} zoom={zoom} />
        </main>

        <aside className={"vystup-panel vpravo np" + (panely.vpravo ? "" : " zabaleny")}>
          <button
            className="panel-prepinac"
            onClick={() => setPanely((p) => ({ ...p, vpravo: !p.vpravo }))}
            title={panely.vpravo ? "Skrýt vlastnosti" : "Zobrazit vlastnosti"}
          >
            {panely.vpravo ? "›" : "‹"}
          </button>
          {panely.vpravo && (
            <div className="panel-obsah">
              <Vlastnosti editor={editor} katalog={data.katalog} nabidkaId={id} />
            </div>
          )}
        </aside>
      </div>

      {/* Do tisku jde papír bez editoru – bez rámečků, úchytů a vodítek. */}
      <div className="vystup-tisk">
        <Papir konfigurace={editor.konfigurace} data={data} tisk />
      </div>
    </div>
  );
}

/** Výběr šablony rozvržení do horní lišty. */
function Sablony({ sablony, onPouzij, onUloz, onSmaz }) {
  const vsechny = sablony?.sablony || [];
  // Šablony z původního modelu nový editor otevřít neumí – k použití se
  // nenabízejí, ale ve výběru „smazat" být musí, jinak by z databáze
  // neexistovala cesta ven.
  const ulozene = vsechny.filter((s) => s.pouzitelna !== false);
  const zNabidek = sablony?.nabidky || [];
  return (
    <div className="vy-sablony">
      <select
        className="vy-sablona-vyber"
        value=""
        onChange={(e) => {
          onPouzij(e.target.value);
          e.target.value = "";
        }}
        aria-label="Použít šablonu"
      >
        <option value="">Použít šablonu…</option>
        <option value="vychozi:0">Výchozí předloha</option>
        {ulozene.length > 0 && (
          <optgroup label="Uložené šablony">
            {ulozene.map((s) => (
              <option key={s.id} value={`sablona:${s.id}`}>
                {s.nazev}
              </option>
            ))}
          </optgroup>
        )}
        {zNabidek.length > 0 && (
          <optgroup label="Z jiné nabídky">
            {zNabidek.map((n) => (
              <option key={n.nabidka_id} value={`nabidka:${n.nabidka_id}`}>
                {n.nazev}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      <button className="fm-btn" onClick={onUloz} title="Uložit tohle rozvržení jako šablonu">
        Uložit jako šablonu…
      </button>
      {vsechny.length > 0 && (
        <select
          className="vy-sablona-vyber"
          value=""
          onChange={(e) => {
            const s = vsechny.find((x) => String(x.id) === e.target.value);
            e.target.value = "";
            if (s) onSmaz(s);
          }}
          aria-label="Smazat šablonu"
        >
          <option value="">Smazat šablonu…</option>
          {vsechny.map((s) => (
            <option key={s.id} value={s.id}>
              {s.nazev}
              {s.pouzitelna === false ? " (starý formát)" : ""}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
