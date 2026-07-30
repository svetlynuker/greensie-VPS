import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Aktivity from "../components/Aktivity";
import KontaktyPanel from "../components/KontaktyPanel";
import PripadFormular from "../components/PripadFormular";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import VlastniPoleVypis from "../components/VlastniPoleVypis";
import ZakaznikFormular from "../components/ZakaznikFormular";
import {
  crmPripady,
  crmZakaznikDetail,
  crmZakaznikKonvertuj,
  crmZakaznikSmaz,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum, fmtKc, nazvyKategorii } from "../crm";
import "../styles/crm.css";

const ZALOZKY = [
  { klic: "prehled", nazev: "Přehled" },
  { klic: "pripady", nazev: "Obchodní případy" },
  { klic: "aktivity", nazev: "Aktivity a úkoly" },
];

/**
 * Karta zákazníka – odtud vede celá cesta zakázky.
 *
 * „Nový obchodní případ" je tady schválně: OZ nemá důvod chodit do jiné sekce,
 * všechno podstatné se zakládá u zákazníka (viz zadání – OZ nemusí sahat na
 * samotný nabídkovač).
 */
export default function ZakaznikDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [z, setZ] = useState(null);
  const [pripady, setPripady] = useState([]);
  const [zalozka, setZalozka] = useState("prehled");
  const [upravuje, setUpravuje] = useState(false);
  const [novyPripad, setNovyPripad] = useState(false);
  const [spravaPoli, setSpravaPoli] = useState(false);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    Promise.all([nactiMe(), crmZakaznikDetail(id), crmPripady({ zakaznikId: id })])
      .then(([m, detail, list]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setZ(detail);
        setPripady(list);
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
  }, [id, navigate]);

  async function konvertuj() {
    try {
      setZ(await crmZakaznikKonvertuj(id));
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz() {
    if (!window.confirm("Opravdu smazat zákazníka? Nelze vzít zpět.")) return;
    try {
      await crmZakaznikSmaz(id);
      navigate(`/zakaznici/${z.typ}`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !z) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !z) return null;

  const adresa = [z.adresa_ulice, z.adresa_psc, z.adresa_mesto].filter(Boolean).join(", ");

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app">
        <Link to={`/zakaznici/${z.typ}`} className="crm-zpet">
          ← Zpět na {z.typ === "lead" ? "Leady" : "Klienty"}
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>{z.nazev}</h1>
            <div className="crm-karta-radek">
              {z.ico ? `IČO ${z.ico}` : "bez IČO"}
              {adresa ? ` · ${adresa}` : ""}
              {z.vlastnik_jmeno ? ` · vlastník ${z.vlastnik_jmeno}` : ""}
            </div>
          </div>
          <span className="crm-mezera" />
          <span className={`crm-znacka ${z.typ === "klient" ? "crm-barva-ok" : "crm-barva-info"}`}>
            {z.typ === "klient" ? "Klient" : "Lead"}
          </span>
          {z.typ === "lead" && (
            <button className="fm-btn" onClick={konvertuj} title="Označit jako klienta">
              Převést na klienta
            </button>
          )}
          <button className="fm-btn" onClick={() => setUpravuje(true)}>
            Upravit
          </button>
          <button className="fm-btn fm-primary" onClick={() => setNovyPripad(true)}>
            + Obchodní případ
          </button>
        </div>

        <div className="crm-zalozky">
          {ZALOZKY.map((zl) => (
            <button
              key={zl.klic}
              className={`crm-zalozka ${zalozka === zl.klic ? "aktivni" : ""}`}
              onClick={() => setZalozka(zl.klic)}
            >
              {zl.nazev}
              {zl.klic === "pripady" && pripady.length > 0 ? ` (${pripady.length})` : ""}
            </button>
          ))}
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zalozka === "prehled" && (
          <div className="crm-dva-sloupce">
            <div className="fm-card crm-blok">
              <h3>Údaje</h3>
              <dl className="crm-udaje">
                <dt>Název</dt>
                <dd>{z.nazev}</dd>
                <dt>IČO / DIČ</dt>
                <dd>
                  {z.ico || "—"} / {z.dic || "—"}
                </dd>
                <dt>Adresa</dt>
                <dd>{adresa || "—"}</dd>
                <dt>Telefon</dt>
                <dd>{z.telefon || "—"}</dd>
                <dt>E-mail</dt>
                <dd>{z.email || "—"}</dd>
                <dt>Web</dt>
                <dd>{z.web || "—"}</dd>
                <dt>GPS</dt>
                <dd>
                  {z.gps_lat != null && z.gps_lng != null
                    ? `${z.gps_lat} N, ${z.gps_lng} E`
                    : "—"}
                </dd>
                <dt>Zdroj</dt>
                <dd>{z.zdroj || "—"}</dd>
                <dt>Vytvořeno</dt>
                <dd>{fmtDatum(z.vytvoreno_at) || "—"}</dd>
                {z.konvertovan_at && (
                  <>
                    <dt>Klientem od</dt>
                    <dd>{fmtDatum(z.konvertovan_at)}</dd>
                  </>
                )}
                {z.raynet_id && (
                  <>
                    {/* Koexistence s Raynetem – ať je vidět, že je záznam spárovaný. */}
                    <dt>Raynet ID</dt>
                    <dd>{z.raynet_id}</dd>
                  </>
                )}
              </dl>
              {z.poznamka && <p className="crm-poznamka">{z.poznamka}</p>}
              <div className="crm-blok-pata">
                <span className="crm-mezera" />
                <button className="fm-btn crm-btn-smazat" onClick={smaz}>
                  Smazat zákazníka
                </button>
              </div>
            </div>

            <div className="crm-sloupec-bloky">
              <VlastniPoleVypis
                pole={z.vlastni_pole}
                hodnoty={z.extra}
                muzeSpravovat={me.prava?.includes("crm_nastaveni")}
                onSprava={() => setSpravaPoli(true)}
              />
              <KontaktyPanel zakaznik={z} onZmena={setZ} />
            </div>
          </div>
        )}

        {zalozka === "pripady" && (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Název</th>
                  <th>Kategorie</th>
                  <th>Stav</th>
                  <th className="crm-vpravo">Hodnota</th>
                  <th>Uzavření</th>
                </tr>
              </thead>
              <tbody>
                {pripady.map((p) => (
                  <tr key={p.id} onClick={() => navigate(`/pripady/detail/${p.id}`)}>
                    <td className="crm-silne">{p.cislo}</td>
                    <td>{p.nazev || "—"}</td>
                    <td>{nazvyKategorii(p.kategorie) || "—"}</td>
                    <td>
                      <span className="crm-znacka">{p.stav_nazev}</span>
                    </td>
                    <td className="crm-vpravo">{fmtKc(p.hodnota_kc)}</td>
                    <td>{fmtDatum(p.predpokladane_uzavreni) || "—"}</td>
                  </tr>
                ))}
                {pripady.length === 0 && (
                  <tr>
                    <td colSpan={6} className="crm-prazdno">
                      Zákazník zatím nemá obchodní případ. Založ ho tlačítkem „+ Obchodní případ".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {zalozka === "aktivity" && <Aktivity entita="zakaznik" zaznamId={z.id} />}
      </div>

      {upravuje && (
        <ZakaznikFormular
          zakaznik={z}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setUpravuje(false)}
          onHotovo={(novy) => {
            setZ(novy);
            setUpravuje(false);
          }}
        />
      )}

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="zakaznik"
          nazevObrazovky="Zákazníci"
          onZavri={() => setSpravaPoli(false)}
          onZmena={() => crmZakaznikDetail(id).then(setZ).catch(() => {})}
        />
      )}

      {novyPripad && (
        <PripadFormular
          zakaznik={z}
          muzeMenitVlastnika={me.prava?.includes("crm_vse")}
          onZavri={() => setNovyPripad(false)}
          onHotovo={(p) => {
            setNovyPripad(false);
            navigate(`/pripady/detail/${p.id}`);
          }}
        />
      )}
    </Layout>
  );
}
