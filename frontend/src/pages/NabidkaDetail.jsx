import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import DokumentUpload from "../components/DokumentUpload";
import Pritomni from "../components/Pritomni";
import StavUlozeni from "../components/StavUlozeni";
import PeakShavingPanel from "../components/PeakShavingPanel";
import PpaPanel from "../components/PpaPanel";
import PpaBessPanel from "../components/PpaBessPanel";
import ProdejPanel from "../components/ProdejPanel";
import EmailOkno from "../components/EmailOkno";
import PdfNabidky from "../components/PdfNabidky";
import RozpisPolozek from "../components/RozpisPolozek";
import VlastniPoleNastaveni from "../components/VlastniPoleNastaveni";
import VlastniPoleVstupy from "../components/VlastniPoleVstupy";
import {
  nactiMe,
  logout,
  nabidkaDetail,
  nabidkaSmaz,
  nabidkaPolozky,
  nabidkaUlozPolozky,
  nabidkaPridejZKatalogu,
  nabidkaPdfSeznam,
} from "../api";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";
import { PODSEKCE, STAV_NABIDKY, fmtDatum } from "../nabidkovac";
import "../styles/nabidkovac.css";
// Vlastní pole nesou crm-* třídy (podnadpis, nápověda, zaškrtávátko) – jsou
// všechny prefixované, takže se do nabídkovače nepletou.
import "../styles/crm.css";

/**
 * Pole bloku „Údaje zákazníka“, která backend umí uložit po jednom (whitelist
 * v `crm/pole_zaznamu.py`, entita „nab“). Co tu není, server odmítne se 422,
 * takže seznam musí být stejný jako tam.
 *
 * Vstupy výpočtu (profil spotřeby, sazby, parametry PPA/BESS) sem NEPATŘÍ:
 * nabídka se z nich přepočítává do verzí, takže je ukládá až „Spočítat“.
 */
const POLE = ["zakaznik_nazev", "zakaznik_adresa", "zakaznik_gps_lat", "zakaznik_gps_lng"];

const NAZVY_POLI = {
  zakaznik_nazev: "Název zákazníka",
  zakaznik_adresa: "Adresa",
  zakaznik_gps_lat: "GPS šířka",
  zakaznik_gps_lng: "GPS délka",
};

/** Čitelný název pole – pro kolečka přítomnosti i pro hlášku o kolizi. */
function popisPole(klic) {
  if (!klic) return "";
  // Vlastní pole se hlásí jako „extra:dotace“; klíč je to nejlepší, co tu máme.
  if (klic.startsWith("extra:")) return klic.slice(6);
  return NAZVY_POLI[klic] || klic;
}

export default function NabidkaDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [nabidka, setNabidka] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [uklada, setUklada] = useState(false);
  // Údaje zákazníka a podklady se rozbalují na vyžádání – u rozpracované
  // nabídky by jen zabíraly místo, které patří výpočtu. U nové nabídky se
  // otevřou samy (viz useEffect níž), protože tam se teprve vyplňují.
  const [upravaZakaznika, setUpravaZakaznika] = useState(false);
  const [podkladyOtevrene, setPodkladyOtevrene] = useState(false);
  // Rozpis se načítá až po rozbalení – katalog má stovky položek a u nabídky,
  // kde se jen počítá, by se tahal zbytečně.
  const [rozpisOtevreny, setRozpisOtevreny] = useState(false);

  const [spravaPoli, setSpravaPoli] = useState(false);
  // Odeslání nabídky zákazníkovi e-mailem (CRM-10).
  const [posilaEmail, setPosilaEmail] = useState(false);
  // Vygenerované soubory nabídky (nejnovější první) – PDF pro zákazníka
  // i interní výpočtový Excel. Historie se nemaže: musí být poznat, co přesně
  // zákazník dostal a kdy.
  const [pdfka, setPdfka] = useState([]);
  const posledniPdf = pdfka.find((z) => z.format !== "xlsx");
  const posledniXlsx = pdfka.find((z) => z.format === "xlsx");

  const nactiZnovu = useCallback(async () => {
    const n = await nabidkaDetail(id);
    setNabidka(n);
    return n;
  }, [id]);

  // ---- Automatické ukládání údajů zákazníka ----
  // Nad jednou nabídkou se schází obchodník i backoffice a staré ukládání
  // celého bloku jedním PUT znamenalo, že kdo uložil poslední, přepsal
  // i hodnoty, kterých se ani nedotkl. Ukládá se proto pole po poli.
  //
  // Výpočtové vlastní pole (CRM-34) se nevyplňuje, jen zobrazuje – do
  // automatického ukládání nepatří, hodnotu si stejně přepočítá backend.
  const vlastniPole = nabidka?.vlastni_pole;
  const poleAutosave = useMemo(
    () => [
      ...POLE,
      ...(vlastniPole || [])
        .filter((p) => !(p.vzorec || "").trim())
        .map((p) => `extra:${p.klic}`),
    ],
    [vlastniPole],
  );

  const {
    hodnoty,
    zmen,
    stav,
    chyba: chybaUlozeni,
    kdy,
    pritomni,
    razitko,
    kolize,
    prepis,
    vezmiJejich,
    dokonci,
    onFokus,
    onBlur,
  } = useZaznamAutosave({
    entita: "nab",
    id,
    zaznam: nabidka,
    pole: poleAutosave,
    entitaTyp: "crm_nab",
    zapnuto: Boolean(nabidka),
  });

  // Razítko se změnilo → nabídku upravil někdo jiný (nebo já z druhého okna),
  // natáhneme ji znovu. První razítko se jen zapamatuje, jinak by se detail po
  // otevření načetl dvakrát. Rozepsané pole hook nepřepíše (viz
  // `useZaznamAutosave`), takže to nikomu nesebere text pod rukama.
  const razitkoRef = useRef(null);
  useEffect(() => {
    if (!razitko) return;
    if (razitkoRef.current === null || razitkoRef.current === razitko) {
      razitkoRef.current = razitko;
      return;
    }
    razitkoRef.current = razitko;
    nactiZnovu().catch(() => {});
  }, [razitko, nactiZnovu]);

  // Vlastní pole: základ z posledního načtení (kvůli výpočtovým polím, která
  // hook nespravuje), navrch to, co má člověk rozepsané.
  const extraHodnoty = useMemo(() => {
    const vysledek = { ...(nabidka?.extra || {}) };
    (vlastniPole || []).forEach((p) => {
      const klic = `extra:${p.klic}`;
      if (klic in hodnoty) vysledek[p.klic] = hodnoty[klic];
    });
    return vysledek;
  }, [nabidka, vlastniPole, hodnoty]);

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

  // PDF se dotahují zvlášť: detail nabídky se načítá při každé změně a tenhle
  // seznam se mění jen tlačítkem „Uložit do PDF" v editoru výstupu.
  useEffect(() => {
    nabidkaPdfSeznam(id)
      .then(setPdfka)
      .catch(() => setPdfka([]));
  }, [id]);

  /**
   * „Hotovo“ už neukládá – pole se ukládají sama. Jen dožene, co se nestihlo
   * odeslat (posledních pár znaků z rozepsaného pole), natáhne čerstvý záznam
   * a blok zavře. Při nerozhodnuté kolizi zůstává otevřený: zavřít ho
   * s neuloženým textem znamená ten text zahodit.
   */
  async function hotovo() {
    if (uklada) return;
    if (kolize) {
      setChyba("Nejdřív rozhodni, čí hodnota u kolize platí — pak blok zavři.");
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      await dokonci();
      await nactiZnovu();
      setUpravaZakaznika(false);
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
          {/* Kdo má nabídku otevřenou taky – ať je vidět, s kým se člověk může
              potkat, ještě než napíše první znak. Popisek u kolečka řekne i to,
              na kterém poli kolega stojí. */}
          <Pritomni pritomni={pritomni} popisekPole={popisPole} />
          {/* Údaje zákazníka se ukládají samy – bez téhle hlášky by nebylo jak
              poznat, že text došel na server. */}
          <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
          <span className="nb-badge">{sekce?.nazev || nabidka.typ}</span>
          <span className="nb-badge">{STAV_NABIDKY[nabidka.stav] || nabidka.stav}</span>
          <button className="fm-btn" onClick={() => setUpravaZakaznika((s) => !s)}>
            {upravaZakaznika ? "Zavřít údaje" : "Upravit zákazníka"}
          </button>
          <button className="fm-btn" onClick={() => setPosilaEmail(true)}>
            ✉ Poslat e-mail
          </button>
          {/* Nabídka pro zákazníka (PDF) – jen tam, kde už je výpočet. */}
          {(nabidka.typ === "ppa" ||
            nabidka.typ === "peak_shaving" ||
            nabidka.typ === "ppa_bess") && (
            <button
              className="fm-btn fm-primary"
              onClick={() => navigate(`/nabidkovac/nabidka/${nabidka.id}/vystup/${nabidka.typ}`)}
              title="Sestav a uprav nabídkovou stránku (jen zákaznická data) a ulož ji do PDF"
            >
              Nabídka pro zákazníka
            </button>
          )}
          {/* Ručně přepsané hodnoty se v PDF nijak neoznačí (na papíře mají
              vypadat jako každé jiné číslo), takže je musí být poznat aspoň
              tady – než nabídka odejde zákazníkovi. */}
          {nabidka.vystup_rucnich_hodnot > 0 && (
            <span
              className="nb-badge"
              title="V rozvržení nabídky jsou hodnoty zadané ručně, ne spočítané. Uprav je v editoru nabídky."
            >
              ✏️ ručně přepsané hodnoty: {nabidka.vystup_rucnich_hodnot}
            </span>
          )}
          {/* Poslední vytištěné PDF a poslední výpočtový Excel – ať se za nimi
              nemusí do editoru. Každý formát zvlášť: kdyby se bralo prostě to
              nejnovější, po tisku by tu místo nabídky visel interní model. */}
          {posledniPdf && <PdfNabidky pdf={posledniPdf} />}
          {posledniXlsx && <PdfNabidky pdf={posledniXlsx} />}
        </div>

        {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. Je to
            nad blokem schválně – kdyby panel byl uvnitř, po sbalení „Údajů
            zákazníka“ by rozhodnutí zmizelo a hodnota by zůstala neuložená. */}
        {kolize && (
          <div className="crm-kolize">
            <div>
              <strong>{popisPole(kolize.pole)}</strong> mezitím změnil
              {kolize.kdo ? ` ${kolize.kdo}` : " někdo jiný"} na{" "}
              <strong>{kolize.aktualni || "prázdné"}</strong>.
              <br />
              Ty píšeš <strong>{kolize.moje || "prázdné"}</strong>.
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button className="fm-btn fm-primary" onClick={prepis}>
                Přepsat mojí hodnotou
              </button>
              <button className="fm-btn" onClick={vezmiJejich}>
                Nechat jejich
              </button>
            </div>
          </div>
        )}

        {pdfka.length > 0 && (
          <div className="fm-card nb-pdf-historie">
            <h3>Vygenerované soubory</h3>
            <ul>
              {pdfka.slice(0, 5).map((z) => (
                <li key={z.id}>
                  <PdfNabidky pdf={z} kompaktni />
                  <span>{z.nazev}</span>
                  <span className="crm-tise">{fmtDatum(z.vygenerovano_at)}</span>
                  {z.vygeneroval_jmeno && (
                    <span className="crm-tise">{z.vygeneroval_jmeno}</span>
                  )}
                  {/* Dokud PDF není na Disku, běží fronta konektoru (pár
                      sekund) – nebo se nahrát nepovedlo a je to vidět. */}
                  {!z.na_disku && <span className="crm-tise">propisuje se na Disk…</span>}
                </li>
              ))}
            </ul>
            {pdfka.length > 5 && (
              <div className="crm-tise">…a dalších {pdfka.length - 5} starších</div>
            )}
          </div>
        )}

        {upravaZakaznika && (
          <div className="fm-card" style={{ padding: 18, marginBottom: 14 }}>
            <h3 style={{ margin: "0 0 12px", fontSize: 14 }}>Údaje zákazníka</h3>
            <p className="crm-tise" style={{ margin: "0 0 12px" }}>
              Údaje se ukládají samy, pole po poli – kolega nad stejnou nabídkou ti nic
              nepřepíše. Tlačítko <b>Hotovo</b> blok jen zavře.
            </p>
            <div className="nb-form-grid">
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="nb-label">Název zákazníka</label>
                <input
                  className="nb-pole"
                  value={hodnoty.zakaznik_nazev ?? ""}
                  onChange={(e) => zmen("zakaznik_nazev", e.target.value)}
                  onFocus={() => onFokus("zakaznik_nazev")}
                  onBlur={() => onBlur("zakaznik_nazev")}
                  placeholder="např. Firma s.r.o."
                />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="nb-label">Adresa</label>
                <input
                  className="nb-pole"
                  value={hodnoty.zakaznik_adresa ?? ""}
                  onChange={(e) => zmen("zakaznik_adresa", e.target.value)}
                  onFocus={() => onFokus("zakaznik_adresa")}
                  onBlur={() => onBlur("zakaznik_adresa")}
                  placeholder="Ulice, město"
                />
              </div>
              <div>
                <label className="nb-label">GPS šířka (lat) – pro budoucí PVGIS</label>
                <input
                  className="nb-pole"
                  value={hodnoty.zakaznik_gps_lat ?? ""}
                  onChange={(e) => zmen("zakaznik_gps_lat", e.target.value)}
                  onFocus={() => onFokus("zakaznik_gps_lat")}
                  onBlur={() => onBlur("zakaznik_gps_lat")}
                  placeholder="např. 50.087"
                  inputMode="decimal"
                />
              </div>
              <div>
                <label className="nb-label">GPS délka (lng) – pro budoucí PVGIS</label>
                <input
                  className="nb-pole"
                  value={hodnoty.zakaznik_gps_lng ?? ""}
                  onChange={(e) => zmen("zakaznik_gps_lng", e.target.value)}
                  onFocus={() => onFokus("zakaznik_gps_lng")}
                  onBlur={() => onBlur("zakaznik_gps_lng")}
                  placeholder="např. 14.421"
                  inputMode="decimal"
                />
              </div>

              {/* Vlastní pole nabídky – definuje je admin v CRM. Ukládají se
                  taky po jednom: celé `extra` by přepsalo i klíče, kterých se
                  člověk nedotkl (včetně cizích změn, tiše). */}
              <VlastniPoleVstupy
                styl="nb"
                pole={nabidka.vlastni_pole}
                hodnoty={extraHodnoty}
                onZmenaPole={(klic, hodnota, ihned) => zmen(`extra:${klic}`, hodnota, ihned)}
              />
            </div>
            {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13, marginTop: 10 }}>{chyba}</div>}
            <div style={{ display: "flex", gap: 8, marginTop: 14, alignItems: "center" }}>
              {/* Hláška o ukládání je v hlavičce nabídky – ta je vidět pořád,
                  takže druhá kopie tady by jen skákala. */}
              <button className="fm-btn fm-primary" onClick={hotovo} disabled={uklada}>
                {uklada ? "Dokončuji…" : "Hotovo"}
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

        {/* Navržená řešení — všechny tři linie mají stejný pracovní stůl.
            `pritomni` se předává schválně: vstupy výpočtu se neukládají za
            pochodu, takže „Spočítat" umí přepsat cizí zadání. Panel na to
            aspoň upozorní (viz PritomniVypocet). */}
        {nabidka.typ === "peak_shaving" ? (
          <PeakShavingPanel nabidka={nabidka} pritomni={pritomni} />
        ) : nabidka.typ === "ppa_bess" ? (
          <PpaBessPanel nabidka={nabidka} pritomni={pritomni} />
        ) : nabidka.typ === "ppa" ? (
          <PpaPanel nabidka={nabidka} pritomni={pritomni} />
        ) : (
          <ProdejPanel nabidka={nabidka} pritomni={pritomni} />
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
          onOdeslano={nactiZnovu}
        />
      )}

      {spravaPoli && (
        <VlastniPoleNastaveni
          entita="nab"
          nazevObrazovky="Nabídky"
          onZavri={() => setSpravaPoli(false)}
          // Po změně definic se musí přenačíst detail, jinak by formulář
          // vykresloval pole podle staré definice.
          onZmena={nactiZnovu}
        />
      )}
    </Layout>
  );
}
