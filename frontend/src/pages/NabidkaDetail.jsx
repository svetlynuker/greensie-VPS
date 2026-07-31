import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import DokumentUpload from "../components/DokumentUpload";
import PeakShavingPanel from "../components/PeakShavingPanel";
import PpaPanel from "../components/PpaPanel";
import ProdejPanel from "../components/ProdejPanel";
import EmailOkno from "../components/EmailOkno";
import RozpisPolozek from "../components/RozpisPolozek";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import VlastniPoleVstupy from "../components/VlastniPoleVstupy";
import {
  nactiMe,
  logout,
  nabidkaDetail,
  nabidkaUprav,
  nabidkaSmaz,
  nabidkaPolozky,
  nabidkaUlozPolozky,
  nabidkaPridejZKatalogu,
} from "../api";
import { PODSEKCE, STAV_NABIDKY, fmtDatum } from "../nabidkovac";
import "../styles/nabidkovac.css";
// Vlastní pole nesou crm-* třídy (podnadpis, nápověda, zaškrtávátko) – jsou
// všechny prefixované, takže se do nabídkovače nepletou.
import "../styles/crm.css";

export default function NabidkaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [nabidka, setNabidka] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [zprava, setZprava] = useState(null);
  // Údaje zákazníka a podklady se rozbalují na vyžádání – u rozpracované
  // nabídky by jen zabíraly místo, které patří výpočtu. U nové nabídky se
  // otevřou samy (viz useEffect níž), protože tam se teprve vyplňují.
  const [upravaZakaznika, setUpravaZakaznika] = useState(false);
  const [podkladyOtevrene, setPodkladyOtevrene] = useState(false);
  // Rozpis se načítá až po rozbalení – katalog má stovky položek a u nabídky,
  // kde se jen počítá, by se tahal zbytečně.
  const [rozpisOtevreny, setRozpisOtevreny] = useState(false);

  // editovatelná pole zákazníka
  const [nazev, setNazev] = useState("");
  const [adresa, setAdresa] = useState("");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  // Hodnoty vlastních polí (CRM-04). Ukládají se spolu se zbytkem formuláře,
  // ne zvlášť – jinak by při chybě zůstala nabídka uložená jen napůl.
  const [extra, setExtra] = useState({});
  const [spravaPoli, setSpravaPoli] = useState(false);
  // Odeslání nabídky zákazníkovi e-mailem (CRM-10).
  const [posilaEmail, setPosilaEmail] = useState(false);

  function naplnFormular(n) {
    setNazev(n.zakaznik_nazev || "");
    setAdresa(n.zakaznik_adresa || "");
    setLat(n.zakaznik_gps_lat != null ? String(n.zakaznik_gps_lat) : "");
    setLng(n.zakaznik_gps_lng != null ? String(n.zakaznik_gps_lng) : "");
    setExtra(n.extra || {});
  }

  async function nactiZnovu() {
    const n = await nabidkaDetail(id);
    setNabidka(n);
    return n;
  }

  useEffect(() => {
    Promise.all([nactiMe(), nabidkaDetail(id)])
      .then(([m, n]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("nabidkovac")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setNabidka(n);
        naplnFormular(n);
        // Čerstvě založená nabídka: otevři to, co se v ní teprve vyplňuje.
        if (!n.zakaznik_nazev) setUpravaZakaznika(true);
        if (!(n.dokumenty || []).length) setPodkladyOtevrene(true);
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

  async function uloz() {
    setUklada(true);
    setChyba(null);
    setZprava(null);
    try {
      const n = await nabidkaUprav(id, {
        zakaznik_nazev: nazev.trim(),
        zakaznik_adresa: adresa.trim(),
        zakaznik_gps_lat: lat.trim() === "" ? null : Number(lat.replace(",", ".")),
        zakaznik_gps_lng: lng.trim() === "" ? null : Number(lng.replace(",", ".")),
        extra,
      });
      setNabidka(n);
      setExtra(n.extra || {});
      setZprava("Uloženo.");
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  async function smaz() {
    if (!window.confirm("Opravdu smazat celou nabídku včetně nahraných dokumentů?")) return;
    try {
      await nabidkaSmaz(id);
      navigate(`/nabidkovac/${nabidka.typ}`);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !nabidka) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !nabidka) return null;

  const sekce = PODSEKCE.find((s) => s.klic === nabidka.typ);
  const pocetDokumentu = (nabidka.dokumenty || []).length;

  return (
    <Layout uzivatel={me.uzivatel}>
      {/* Pracovní stůl (vstupy + výsledek vedle sebe) potřebuje šířku na dva
          sloupce — mají ho všechny tři linie, takže platí pro celý detail. */}
      <div className="nb-app siroky">
        <Link to={`/nabidkovac/${nabidka.typ}`} className="nb-backlink">
          ← Zpět na {sekce?.nazev || "seznam"}
        </Link>

        {/* Zákazník: jeden řádek, formulář se rozbalí až na vyžádání. Do adresy
            a GPS se sahá jednou na začátku, takže tu nemusí trvale zabírat
            místo, které patří vstupům výpočtu a výsledku. */}
        <div className="nb-zakaznik">
          <div style={{ minWidth: 0 }}>
            <h1>{nabidka.zakaznik_nazev || "Nová nabídka"}</h1>
            <div className="nb-zakaznik-radek">
              {nabidka.zakaznik_adresa || "adresa nevyplněná"}
              {nabidka.zakaznik_gps_lat != null && nabidka.zakaznik_gps_lng != null && (
                <> · {nabidka.zakaznik_gps_lat} N, {nabidka.zakaznik_gps_lng} E</>
              )}
              {" · založil "}
              {nabidka.vytvoril_jmeno || "—"} {fmtDatum(nabidka.vytvoreno_at)}
            </div>
          </div>
          <span className="nb-mezera" />
          <span className="nb-badge">{sekce?.nazev || nabidka.typ}</span>
          <span className="nb-badge">{STAV_NABIDKY[nabidka.stav] || nabidka.stav}</span>
          <button className="fm-btn" onClick={() => setUpravaZakaznika((s) => !s)}>
            {upravaZakaznika ? "Zavřít údaje" : "Upravit zákazníka"}
          </button>
          <button className="fm-btn" onClick={() => setPosilaEmail(true)}>
            ✉ Poslat e-mail
          </button>
          {/* Nabídka pro zákazníka (PDF) – jen tam, kde už je výpočet. */}
          {(nabidka.typ === "ppa" || nabidka.typ === "peak_shaving") && (
            <button
              className="fm-btn fm-primary"
              onClick={() => navigate(`/nabidkovac/nabidka/${nabidka.id}/vystup/${nabidka.typ}`)}
              title="Sestav a uprav nabídkovou stránku (jen zákaznická data) a ulož ji do PDF"
            >
              Nabídka pro zákazníka
            </button>
          )}
        </div>

        {upravaZakaznika && (
          <div className="fm-card" style={{ padding: 18, marginBottom: 14 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>Údaje zákazníka</h3>
            <div className="nb-form-grid">
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="nb-label">Název zákazníka</label>
                <input className="nb-pole" value={nazev} onChange={(e) => setNazev(e.target.value)} placeholder="např. Firma s.r.o." />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="nb-label">Adresa</label>
                <input className="nb-pole" value={adresa} onChange={(e) => setAdresa(e.target.value)} placeholder="Ulice, město" />
              </div>
              <div>
                <label className="nb-label">GPS šířka (lat) – pro budoucí PVGIS</label>
                <input className="nb-pole" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="např. 50.087" inputMode="decimal" />
              </div>
              <div>
                <label className="nb-label">GPS délka (lng) – pro budoucí PVGIS</label>
                <input className="nb-pole" value={lng} onChange={(e) => setLng(e.target.value)} placeholder="např. 14.421" inputMode="decimal" />
              </div>

              {/* Vlastní pole nabídky – definuje je admin v CRM, ukládají se
                  spolu s údaji zákazníka jedním tlačítkem níž. */}
              <VlastniPoleVstupy
                styl="nb"
                pole={nabidka.vlastni_pole}
                hodnoty={extra}
                onZmena={setExtra}
              />
            </div>
            {zprava && <div style={{ color: "var(--fm-brand-dk)", fontSize: 13, marginTop: 10 }}>{zprava}</div>}
            {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
                {uklada ? "Ukládám…" : "Uložit"}
              </button>
              {/* Správa polí je vidět jen adminovi – běžnému OZ by nabízela
                  nastavení, do kterého stejně nesmí. */}
              {me.prava?.includes("crm_nastaveni") && (
                <button
                  className="fm-btn"
                  onClick={() => setSpravaPoli(true)}
                  title="Přidat nebo upravit vlastní pole nabídek"
                >
                  ⚙ Vlastní pole
                </button>
              )}
              <span style={{ flex: 1 }} />
              <button className="fm-btn" style={{ color: "var(--st-crit)" }} onClick={smaz}>
                Smazat nabídku
              </button>
            </div>
          </div>
        )}

        {/* Podklady: sbalené, když už je co nahráno – profil se načítá ve vstupech
            výpočtu, takže sem OZ chodí jen při zakládání nabídky. */}
        <details
          className="fm-card nb-sbal"
          open={podkladyOtevrene}
          onToggle={(e) => setPodkladyOtevrene(e.currentTarget.open)}
        >
          <summary>
            Podklady
            <span className="nb-badge">
              {pocetDokumentu === 0
                ? "nic nenahráno"
                : `${pocetDokumentu} ${pocetDokumentu === 1 ? "soubor" : pocetDokumentu < 5 ? "soubory" : "souborů"}`}
            </span>
            <span className="nb-mezera" />
            <span style={{ fontSize: 12, fontWeight: 400, color: "var(--fm-muted)" }}>
              faktura za elektřinu (PDF), diagram spotřeby (XLS/CSV)
            </span>
          </summary>
          <div className="nb-sbal-in">
            <p style={{ fontSize: 12, color: "var(--fm-muted)", margin: "0 0 12px" }}>
              Nahraj fakturu za elektřinu (PDF) a/nebo diagram spotřeby (CSV). Soubory se zatím jen
              uloží – automatické zpracování (extrakce z faktury, parsování spotřeby) se připravuje.
            </p>
            <DokumentUpload nabidkaId={nabidka.id} dokumenty={nabidka.dokumenty} onZmena={nactiZnovu} />
          </div>
        </details>

        {/* Navržená řešení — všechny tři linie mají stejný pracovní stůl */}
        {nabidka.typ === "peak_shaving" ? (
          <PeakShavingPanel nabidka={nabidka} />
        ) : nabidka.typ === "ppa" ? (
          <PpaPanel nabidka={nabidka} />
        ) : (
          <ProdejPanel nabidka={nabidka} />
        )}

        {/* Rozpis položek (CRM-08). Je pod výpočtem schválně a je na něm
            nezávislý: výpočet říká, co se zákazníkovi vyplatí, rozpis z čeho
            se skládá cena. Při vzniku objednávky se rozpis překlopí do ní. */}
        <details
          className="nb-sbal"
          open={rozpisOtevreny}
          onToggle={(e) => setRozpisOtevreny(e.currentTarget.open)}
          style={{ marginTop: 16 }}
        >
          <summary>
            Rozpis položek
            <span className="nb-mezera" />
            <span style={{ fontSize: 12, fontWeight: 400, color: "var(--fm-muted)" }}>
              panely, měnič, montáž, doprava — z katalogu i vlastní text
            </span>
          </summary>
          <div className="nb-sbal-in">
            {rozpisOtevreny && (
              <RozpisPolozek
                nadpis="Rozpis nabídky"
                nacti={() => nabidkaPolozky(nabidka.id)}
                uloz={(polozky) => nabidkaUlozPolozky(nabidka.id, polozky)}
                pridejZKatalogu={(ids) => nabidkaPridejZKatalogu(nabidka.id, ids)}
              />
            )}
          </div>
        </details>
      </div>

      {posilaEmail && (
        <EmailOkno
          entita="nab"
          zaznamId={nabidka.id}
          nazev={nabidka.cislo || `#${nabidka.id}`}
          onZavri={() => setPosilaEmail(false)}
          onOdeslano={() => nactiZnovu().then(naplnFormular)}
        />
      )}

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="nab"
          nazevObrazovky="Nabídky"
          onZavri={() => setSpravaPoli(false)}
          // Po změně definic se musí přenačíst detail, jinak by formulář
          // vykresloval pole podle staré definice.
          onZmena={() => nactiZnovu().then(naplnFormular)}
        />
      )}
    </Layout>
  );
}
