import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import NabidkaVystup from "../components/NabidkaVystup";
import NabidkaVystupEditor from "../components/NabidkaVystupEditor";
import {
  nactiMe,
  logout,
  nabidkaVystup,
  nabidkaVystupUloz,
  nabidkaVystupSablony,
  nabidkaVystupSablonaUloz,
  nabidkaVystupSablonaSmaz,
} from "../api";
import { SLOUPCU, vlozPolozku, presunPolozku } from "../nabidkovac";
import "../styles/nabidkovac.css";
import "../styles/vystup.css";

const TYP_NAZEV = { ppa: "PPA", peak_shaving: "Peak shaving" };

// Nový prvek na papír. `id` musí být v rámci nabídky jedinečné (React key
// i pořadí bloků), proto náhodná přípona.
function novaPolozka({ druh, klic = "", sirka = SLOUPCU }) {
  return {
    id: `${druh}-${Math.random().toString(36).slice(2, 8)}`,
    druh,
    viditelny: true,
    nadpis: "",
    text: "",
    pole: [],
    klic,
    sirka,
  };
}

export default function NabidkaVystupStranka() {
  const { id, typ } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [data, setData] = useState(null);
  const [konfigurace, setKonfigurace] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);
  const [uklada, setUklada] = useState(false);
  // Editace papíru: co je vybrané, kam se zrovna pouští, co se táhne.
  const [vybranyId, setVybranyId] = useState(null);
  const [mistoVlozeni, setMistoVlozeni] = useState(null);
  // Během tahání se cíle pro puštění rozšíří, aby se do nich dalo pohodlně mířit.
  const [tahame, setTahame] = useState(false);
  const tazene = useRef(null);
  const [sablony, setSablony] = useState({ sablony: [], nabidky: [] });

  async function nacti(vychozi = false) {
    const d = await nabidkaVystup(id, typ, vychozi);
    setData(d);
    setKonfigurace(d.konfigurace);
    return d;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nabidkaVystup(id, typ)])
      .then(([m, d]) => {
        if (m.musi_zmenit_heslo) return navigate("/zmena-hesla");
        if (!m.prava?.includes("nabidkovac")) return navigate("/rozcestnik");
        setMe(m);
        setData(d);
        setKonfigurace(d.konfigurace);
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, typ]);

  // Seznam šablon (pojmenované + rozvržení jiných nabídek) se dotahuje zvlášť,
  // ať se hlavní náhled nezdrží; když selže, editor jen nemá co nabídnout.
  function nactiSablony() {
    nabidkaVystupSablony(typ, id)
      .then(setSablony)
      .catch(() => setSablony({ sablony: [], nabidky: [] }));
  }

  useEffect(() => {
    nactiSablony();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, typ]);

  // ---- editace papíru (tahání z palety i po papíře) ----
  const bloky = konfigurace?.bloky || [];

  function zmenBloky(nove) {
    setKonfigurace((k) => ({ ...(k || {}), bloky: nove }));
  }

  const editor = {
    vybranyId,
    mistoVlozeni,
    tahame,
    indexPodleId: (blokId) => bloky.findIndex((b) => b.id === blokId),
    vyber: setVybranyId,
    nastavMisto: setMistoVlozeni,
    zacniTahat: (e, blokId) => {
      tazene.current = { zdroj: "papir", id: blokId };
      setTahame(true);
      e.dataTransfer.effectAllowed = "move";
      // Bez setData Firefox tahání nespustí.
      e.dataTransfer.setData("text/plain", blokId);
    },
    dotahni: () => {
      tazene.current = null;
      setTahame(false);
      setMistoVlozeni(null);
    },
    pust: (e, index) => {
      const t = tazene.current;
      tazene.current = null;
      setTahame(false);
      setMistoVlozeni(null);
      if (!t) return;
      if (t.zdroj === "paleta") {
        const polozka = novaPolozka(t.polozka);
        zmenBloky(vlozPolozku(bloky, polozka, index));
        setVybranyId(polozka.id);
      } else {
        zmenBloky(presunPolozku(bloky, t.id, index));
      }
    },
  };

  function tahejNovy(e, polozka) {
    tazene.current = { zdroj: "paleta", polozka };
    setTahame(true);
    e.dataTransfer.effectAllowed = "copy";
    e.dataTransfer.setData("text/plain", polozka.druh);
  }

  // ---- šablony ----
  function pouzijSablonu(nalez, zdroj) {
    if (!nalez) return;
    if (zdroj === "vychozi") {
      obnovVychozi();
      return;
    }
    const popis = zdroj === "sablona" ? `šablonu „${nalez.nazev}"` : `rozvržení z „${nalez.nazev}"`;
    if (!window.confirm(`Použít ${popis}? Přepíše se rozvržení téhle nabídky (uloží se až tlačítkem Uložit).`)) return;
    setKonfigurace(nalez.konfigurace);
    setVybranyId(null);
    setZprava("Šablona použita – ulož ji tlačítkem Uložit.");
  }

  async function ulozJakoSablonu() {
    const nazev = window.prompt("Název šablony (stejný název existující šablonu přepíše):", "");
    if (nazev === null) return;
    if (!nazev.trim()) {
      setChyba("Šablona musí mít název.");
      return;
    }
    setChyba(null);
    setZprava(null);
    try {
      await nabidkaVystupSablonaUloz(typ, nazev.trim(), konfigurace);
      nactiSablony();
      setZprava(`Šablona „${nazev.trim()}" uložena.`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smazSablonu(sablona) {
    if (!window.confirm(`Smazat šablonu „${sablona.nazev}"? Nabídky, které z ní vznikly, to neovlivní.`)) return;
    setChyba(null);
    try {
      await nabidkaVystupSablonaSmaz(typ, sablona.id);
      nactiSablony();
      setZprava(`Šablona „${sablona.nazev}" smazána.`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    setZprava(null);
    try {
      const d = await nabidkaVystupUloz(id, typ, konfigurace);
      setData(d);
      setKonfigurace(d.konfigurace);
      setZprava("Uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function obnovVychozi() {
    if (!window.confirm("Obnovit výchozí předlohu? Neuložené i uložené úpravy této nabídky se přepíšou až po uložení.")) return;
    setChyba(null);
    setZprava(null);
    try {
      await nacti(true);
      setZprava("Načtena výchozí předloha – ulož ji tlačítkem Uložit.");
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !data) {
    return <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>;
  }
  if (!me || !data || !konfigurace) return null;

  return (
    <div className="vystup-page">
      <div className="vystup-bar np">
        <button className="fm-btn" onClick={() => navigate(`/nabidkovac/nabidka/${id}`)}>← Zpět na nabídku</button>
        <h1>Nabídka pro zákazníka · {TYP_NAZEV[typ] || typ}</h1>
        <span className="sp" />
        {zprava && <span style={{ color: "var(--fm-brand-dk)", fontSize: 13 }}>{zprava}</span>}
        {chyba && <span style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</span>}
        <button className="fm-btn" onClick={obnovVychozi}>Obnovit výchozí</button>
        <button className="fm-btn" onClick={uloz} disabled={uklada}>{uklada ? "Ukládám…" : "Uložit"}</button>
        <button className="fm-btn fm-primary" onClick={() => window.print()}>Uložit do PDF</button>
      </div>

      {!data.existuje_reseni && (
        <div className="nb-warn np" style={{ margin: "12px 20px 0" }}>
          <span>⚠️</span>
          <span>
            Pro tuto nabídku zatím není spočítané řešení „{TYP_NAZEV[typ] || typ}". Šablonu si můžeš
            připravit, ale čísla se doplní až po spuštění výpočtu v detailu nabídky.
          </span>
        </div>
      )}

      <div className="vystup-layout">
        <div className="vystup-editor np">
          <div style={{ fontSize: 12, color: "var(--fm-muted)", marginBottom: 8 }}>
            Prvky z palety přetáhni na papír a klikni na ně, když chceš změnit šířku nebo text.
            V nabídce jsou dostupná jen zákaznická data.
          </div>
          <NabidkaVystupEditor
            konfigurace={konfigurace}
            katalog={data.katalog}
            onZmena={setKonfigurace}
            vybranyId={vybranyId}
            onVyber={setVybranyId}
            onTahejNovy={tahejNovy}
            sablony={sablony}
            onPouzijSablonu={pouzijSablonu}
            onUlozSablonu={ulozJakoSablonu}
            onSmazSablonu={smazSablonu}
          />
        </div>
        {/* Klik mimo prvek zruší výběr, ať se dá „odkliknout“ bez mazání. */}
        <div className="vystup-nahled-wrap" onClick={() => setVybranyId(null)}>
          <NabidkaVystup data={data} konfigurace={konfigurace} editor={editor} />
        </div>
      </div>
    </div>
  );
}
