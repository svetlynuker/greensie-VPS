import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import DokumentUpload from "./DokumentUpload";
import KombinaceOkno from "./KombinaceOkno";
import PeakShavingPanel from "./PeakShavingPanel";
import PpaPanel from "./PpaPanel";
import ProdejPanel from "./ProdejPanel";
import PdfNabidky from "./PdfNabidky";
import { crmKategorie, crmVytvorNabidku, nabidkaDetail, nabidkaPdfSeznam } from "../api";
import { STAV_NABIDKY } from "../nabidkovac";
import "../styles/nabidkovac.css";

const TYPY = {
  ppa: "PPA",
  prodej: "Prodej",
  peak_shaving: "Peak shaving",
  kombinace: "Kombinace",
  ppa_bess: "PPA + BESS",
};

/**
 * Nabídky obchodního případu — celý výpočet přímo na kartě případu.
 *
 * Proč to nevede do nabídkovače: OZ nemá odcházet z případu, aby nahrál
 * fakturu a spustil výpočet. Podklady se nahrávají tady a hodnoty se vrací
 * rovnou sem. Nabídkovač zůstává jako samostatná cesta (výpočtový nástroj
 * a testování), ale běžná práce se dělá odsud.
 *
 * Výpočtové panely (PPA / peak shaving / prodej) se PŘEBÍRAJÍ z nabídkovače
 * — jsou to tytéž komponenty, jen vložené sem. Kdyby se překreslovaly znovu,
 * musely by se dva pracovní stoly udržovat současně a rozešly by se.
 */
export default function PripadNabidky({ pripad, onZmena }) {
  const navigate = useNavigate();
  // `null` = nic nevybráno, jinak detail nabídky (panely potřebují dokumenty
  // a spočítaná řešení, ne jen souhrn ze seznamu na případu).
  const [aktivni, setAktivni] = useState(null);
  const [nacitam, setNacitam] = useState(false);
  const [zaklada, setZaklada] = useState(null); // typ, který se právě zakládá
  const [kombinace, setKombinace] = useState(false);
  const [kategorie, setKategorie] = useState([]);
  // Poslední vytištěné PDF vybrané nabídky. Načítá se zvlášť od detailu:
  // detail se obnovuje po každém výpočtu, PDF se mění jen tiskem.
  const [pdf, setPdf] = useState(null);
  const [chyba, setChyba] = useState(null);

  const nabidky = pripad.nabidky || [];

  const vyber = useCallback(async (id) => {
    setNacitam(true);
    setChyba(null);
    try {
      setAktivni(await nabidkaDetail(id));
    } catch (e) {
      setChyba(e.message);
    } finally {
      setNacitam(false);
    }
  }, []);

  // Když případ nabídku má, otevři ji hned — OZ jde na kartu případu proto,
  // aby na ní pracoval, ne aby ještě někam klikal.
  //
  // `zkusenoRef` je tu proti smyčce: `pripad.nabidky` je při každém renderu
  // nové pole, takže efekt běží znovu, a dokud se první načtení nedokončí,
  // `aktivni` je pořád null — bez téhle pojistky by se detail tahal opakovaně.
  const zkusenoRef = useRef(null);
  useEffect(() => {
    if (aktivni || nabidky.length === 0) return;
    const prvni = nabidky[0].id;
    if (zkusenoRef.current === prvni) return;
    zkusenoRef.current = prvni;
    vyber(prvni);
  }, [aktivni, nabidky, vyber]);

  // Kategorie určují, jaké nabídky se dají z případu založit. Načítají se
  // z appky (CRM-03) a berou se jen ty, které do nějakého výpočtu míří —
  // u kategorie bez výpočtu (např. Servis) by tlačítko vedlo do prázdna.
  useEffect(() => {
    crmKategorie()
      .then(setKategorie)
      .catch(() => setKategorie([]));
  }, []);

  useEffect(() => {
    if (!aktivni?.id) {
      setPdf(null);
      return;
    }
    nabidkaPdfSeznam(aktivni.id)
      .then((seznam) => setPdf(seznam[0] || null))
      .catch(() => setPdf(null));
  }, [aktivni?.id]);

  async function zaloz(typ) {
    setZaklada(typ);
    setChyba(null);
    try {
      const nova = await crmVytvorNabidku(pripad.id, typ);
      await onZmena?.(); // ať se nabídka objeví v seznamu na případu
      await vyber(nova.id);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZaklada(null);
    }
  }

  /** Znovu načte detail aktivní nabídky (po nahrání podkladu, po výpočtu). */
  async function obnovAktivni() {
    if (!aktivni) return null;
    const detail = await nabidkaDetail(aktivni.id);
    setAktivni(detail);
    return detail;
  }

  // Kombinaci má smysl nabízet jen tam, kde existuje PPA i peak shaving nabídka.
  const maPpaIPs =
    nabidky.some((n) => n.typ === "ppa") && nabidky.some((n) => n.typ === "peak_shaving");

  // Nabídku lze založit v kterémkoli typu; kategorie případu jdou první,
  // protože to je ta obvyklá volba.
  const sVypoctem = kategorie.filter((k) => k.typ_nabidky);
  const zKategorii = sVypoctem.filter((k) => (pripad.kategorie || []).includes(k.klic));
  const ostatni = sVypoctem.filter(
    (k) => k.aktivni && !(pripad.kategorie || []).includes(k.klic)
  );

  return (
    <div className="crm-nabidky">
      <div className="crm-nabidky-lista">
        {nabidky.length > 0 && (
          <div className="crm-volby">
            {nabidky.map((n) => (
              <button
                key={n.id}
                className={`crm-pilulka ${aktivni?.id === n.id ? "aktivni" : ""}`}
                onClick={() => vyber(n.id)}
                title={`${TYPY[n.typ] || n.typ} · ${n.pocet_reseni} spočítaných řešení`}
              >
                {n.cislo || `#${n.id}`} · {TYPY[n.typ] || n.typ}
              </button>
            ))}
          </div>
        )}

        <span className="crm-mezera" />

        {/* Spojení dvou hotových nabídek do jedné pro zákazníka, který chce obojí.
            Nabízí se jen tam, kde je co spojovat. */}
        {maPpaIPs && (
          <button className="fm-btn" onClick={() => setKombinace(true)} title="Spojit PPA a peak shaving do jedné nabídky">
            ⇄ Kombinace
          </button>
        )}

        {/* Založení nabídky = jedno kliknutí, žádný dialog a žádné přesměrování. */}
        {[...zKategorii, ...ostatni].map((k) => (
          <button
            key={k.klic}
            className={`fm-btn ${zKategorii.includes(k) ? "fm-primary" : ""}`}
            onClick={() => zaloz(k.typ_nabidky)}
            disabled={Boolean(zaklada)}
            title={k.popis}
          >
            {zaklada === k.typ_nabidky ? "Zakládám…" : `+ ${k.nazev}`}
          </button>
        ))}
      </div>

      {chyba && <div className="crm-chyba">{chyba}</div>}

      {nabidky.length === 0 && !zaklada && (
        <div className="crm-prazdno">
          K případu zatím není nabídka. Založ ji tlačítkem vpravo nahoře — podklady nahraješ
          a výpočet spustíš rovnou tady, do nabídkovače chodit nemusíš.
        </div>
      )}

      {nacitam && !aktivni && <div className="crm-prazdno">Načítám nabídku…</div>}

      {kombinace && (
        <KombinaceOkno
          pripad={pripad}
          onZavri={() => setKombinace(false)}
          onHotovo={async (r) => {
            await onZmena?.();
            await vyber(r.id);
          }}
        />
      )}

      {aktivni && (
        <>
          <div className="crm-nabidka-hlava">
            <div>
              <b>{aktivni.cislo || `Nabídka #${aktivni.id}`}</b>
              <span className="crm-znacka">{TYPY[aktivni.typ] || aktivni.typ}</span>
              <span className="crm-znacka">{STAV_NABIDKY[aktivni.stav] || aktivni.stav}</span>
            </div>
            <span className="crm-mezera" />
            {/* Sestavení dokumentu pro zákazníka je samostatná obrazovka
                (papír, náhled, tisk do PDF) – tam přesměrování dává smysl. */}
            {(aktivni.typ === "ppa" || aktivni.typ === "peak_shaving" || aktivni.typ === "kombinace") && (
              <button
                className="fm-btn"
                onClick={() =>
                  navigate(`/nabidkovac/nabidka/${aktivni.id}/vystup/${aktivni.typ}`)
                }
                title="Sestavit nabídkovou stránku pro zákazníka a uložit do PDF"
              >
                Nabídka pro zákazníka (PDF)
              </button>
            )}
            {/* Naposledy vytištěné PDF — bez odbočky do editoru výstupu. */}
            {pdf && <PdfNabidky pdf={pdf} />}
            <button
              className="fm-btn"
              onClick={() => navigate(`/nabidkovac/nabidka/${aktivni.id}`)}
              title="Otevřít tuto nabídku v nabídkovači (stejná data, samostatná obrazovka)"
            >
              Otevřít v nabídkovači
            </button>
          </div>

          {/* Podklady: otevřené, dokud není co nahráno – bez faktury a diagramu
              spotřeby se výpočet nerozjede, takže to má být první, co OZ vidí. */}
          <details className="fm-card nb-sbal" open={(aktivni.dokumenty || []).length === 0}>
            <summary>
              Podklady
              <span className="crm-znacka">
                {(aktivni.dokumenty || []).length === 0
                  ? "nic nenahráno"
                  : `${aktivni.dokumenty.length} souborů`}
              </span>
              <span className="nb-mezera" />
              <span style={{ fontSize: 12, fontWeight: 400, color: "var(--fm-muted)" }}>
                faktura za elektřinu (PDF), diagram spotřeby (XLS/CSV)
              </span>
            </summary>
            <div className="nb-sbal-in">
              <DokumentUpload
                nabidkaId={aktivni.id}
                dokumenty={aktivni.dokumenty}
                onZmena={obnovAktivni}
              />
            </div>
          </details>

          {/* Pracovní stůl: vstupy vlevo, spočítané hodnoty vpravo. Tytéž
              komponenty jako v nabídkovači, jen tady na kartě případu. */}
          {aktivni.typ === "kombinace" ? (
            /* Kombinace nemá vlastní výpočet – čísla přebírá ze spojených
               nabídek. Pracuje se s ní přes „Nabídka pro zákazníka (PDF)"
               a přes „⇄ Kombinace", kde se dá aktualizovat ze zdrojů. */
            <div className="fm-card crm-blok">
              <h3>Kombinovaná nabídka</h3>
              <p className="crm-tise">
                Tahle nabídka spojuje PPA a peak shaving — vlastní výpočet nemá, čísla
                přebírá z obou zdrojových nabídek. Když se zdroje přepočítají, spoj je
                znovu tlačítkem <b>⇄ Kombinace</b> (nabídne „aktualizovat"). Dokument pro
                zákazníka sestavíš přes <b>Nabídka pro zákazníka (PDF)</b>.
              </p>
              {(aktivni.reseni || []).length === 0 && (
                <p className="crm-tise">Zatím bez spojených dat — spusť spojení.</p>
              )}
            </div>
          ) : aktivni.typ === "peak_shaving" ? (
            <PeakShavingPanel nabidka={aktivni} />
          ) : aktivni.typ === "ppa" ? (
            <PpaPanel nabidka={aktivni} />
          ) : (
            <ProdejPanel nabidka={aktivni} />
          )}
        </>
      )}
    </div>
  );
}
