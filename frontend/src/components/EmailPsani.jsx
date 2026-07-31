import { useEffect, useRef, useState } from "react";
import AdresarNaseptavac from "./AdresarNaseptavac";
import { emailOdeslat } from "../api";

/**
 * Okno psaní zprávy – nová, odpověď i přeposlání.
 *
 * Předvyplnění (citace, `Re:`/`Fwd:`, odhození vlastní adresy z příjemců) dělá
 * **backend** a sem přijde hotové v `vychozi`. Frontend by ta pravidla musel
 * duplikovat a časem by se rozešla.
 *
 * ---- Proč se okno nezavírá klikem vedle ---------------------------------
 * Ostatní dialogy v appce se zavírají klikem na pozadí. Tady ne: rozepsaný
 * e-mail je práce na deset minut a ztratit ho omylem míněným klikem je horší
 * než nutnost trefit křížek. Zavření s rozepsaným textem se navíc ptá.
 */
export default function EmailPsani({ vychozi, podpis = "", onZavri, onOdeslano }) {
  const [komu, setKomu] = useState(vychozi?.komu || []);
  const [kopie, setKopie] = useState(vychozi?.kopie || []);
  const [skrytaKopie, setSkrytaKopie] = useState([]);
  const [predmet, setPredmet] = useState(vychozi?.predmet || "");
  const [telo, setTelo] = useState(vychozi?.telo || "");
  const [prilohy, setPrilohy] = useState([]);
  const [ukazKopie, setUkazKopie] = useState(
    (vychozi?.kopie || []).length > 0,
  );
  const [odesila, setOdesila] = useState(false);
  const [chyba, setChyba] = useState(null);
  const souborVstup = useRef(null);

  // U odpovědi je kurzor nahoře nad citací – tam se píše.
  const teloRef = useRef(null);
  useEffect(() => {
    const el = teloRef.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(0, 0);
    el.scrollTop = 0;
  }, []);

  const rozepsano = predmet.trim() || telo.trim() !== (vychozi?.telo || "").trim();

  function zavri() {
    if (
      rozepsano &&
      !window.confirm("Zavřít okno? Rozepsaná zpráva se ztratí.")
    ) {
      return;
    }
    onZavri();
  }

  function pridejSoubory(seznam) {
    const nove = Array.from(seznam || []);
    if (nove.length === 0) return;
    setPrilohy((p) => [...p, ...nove]);
  }

  async function odesli() {
    setOdesila(true);
    setChyba(null);
    try {
      const v = await emailOdeslat({
        komu,
        kopie,
        skrytaKopie,
        predmet,
        telo,
        odpovedNaId: vychozi?.odpoved_na_id || null,
        zakaznikId: vychozi?.zakaznik_id || null,
        pripadId: vychozi?.pripad_id || null,
        prilohy,
      });
      onOdeslano(v);
    } catch (e) {
      setChyba(e.message);
      setOdesila(false);
    }
  }

  const celkemB = prilohy.reduce((s, f) => s + (f.size || 0), 0);
  const muzeOdeslat =
    komu.length > 0 && predmet.trim() && telo.trim() && !odesila;

  return (
    <div className="crm-okno-plast" onClick={(e) => e.stopPropagation()}>
      <div className="crm-okno em-okno-psani" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>
            {vychozi?.odpoved_na_id
              ? "Odpověď"
              : predmet.toLowerCase().startsWith("fwd:")
                ? "Přeposlat"
                : "Nová zpráva"}
          </h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={zavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          <AdresarNaseptavac
            id="ep-komu"
            popisek="Komu *"
            hodnota={komu}
            onZmena={setKomu}
          />

          {!ukazKopie ? (
            <button
              className="fm-btn"
              style={{ alignSelf: "flex-start" }}
              onClick={() => setUkazKopie(true)}
            >
              + Kopie / skrytá kopie
            </button>
          ) : (
            <>
              <AdresarNaseptavac
                id="ep-kopie"
                popisek="Kopie"
                hodnota={kopie}
                onZmena={setKopie}
              />
              <AdresarNaseptavac
                id="ep-bcc"
                popisek="Skrytá kopie"
                hodnota={skrytaKopie}
                onZmena={setSkrytaKopie}
                placeholder="Ostatní příjemci tyhle adresy neuvidí"
              />
            </>
          )}

          <div className="em-pole">
            <label htmlFor="ep-predmet">Předmět *</label>
            <input
              id="ep-predmet"
              value={predmet}
              onChange={(e) => setPredmet(e.target.value)}
            />
          </div>

          <div className="em-pole">
            <label htmlFor="ep-telo">Text *</label>
            <textarea
              id="ep-telo"
              ref={teloRef}
              rows={14}
              value={telo}
              onChange={(e) => setTelo(e.target.value)}
            />
            {podpis && (
              <p className="em-tise">
                Pod text se přidá tvůj podpis ze Nastavení schránky.
              </p>
            )}
          </div>

          <div className="em-pole">
            <label>Přílohy</label>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button className="fm-btn" onClick={() => souborVstup.current?.click()}>
                📎 Připojit soubor
              </button>
              <input
                ref={souborVstup}
                type="file"
                multiple
                style={{ display: "none" }}
                onChange={(e) => {
                  pridejSoubory(e.target.files);
                  // Reset, ať jde připojit tentýž soubor znovu.
                  e.target.value = "";
                }}
              />
              {prilohy.map((f, i) => (
                <span key={`${f.name}-${i}`} className="ns-zeton">
                  {f.name}
                  <button
                    type="button"
                    className="ns-zeton-x"
                    onClick={() => setPrilohy((p) => p.filter((_, j) => j !== i))}
                    aria-label={`Odebrat ${f.name}`}
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
            {celkemB > 15 * 1024 * 1024 && (
              <p className="em-tise" style={{ color: "var(--st-warn)" }}>
                Přílohy mají {(celkemB / (1024 * 1024)).toFixed(1)} MB. Nad 18 MB
                zprávu poštovní server odmítne — velké soubory pošli odkazem na Disk.
              </p>
            )}
          </div>

          {chyba && <div className="em-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={zavri} disabled={odesila}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button className="fm-btn fm-primary" onClick={odesli} disabled={!muzeOdeslat}>
            {odesila ? "Odesílám…" : "Odeslat"}
          </button>
        </div>
      </div>
    </div>
  );
}
