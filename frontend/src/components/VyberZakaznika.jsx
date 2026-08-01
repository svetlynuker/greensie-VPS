import { useEffect, useRef, useState } from "react";
import { crmPripady, crmZakaznici } from "../api";

/**
 * Dialog „připoj zprávy k firmě" — vyhledání zákazníka a volitelně případu.
 *
 * Používá se ze dvou míst (jedna zpráva v panelu čtení, výběr zpráv v seznamu),
 * proto samostatná komponenta a ne dvě skoro stejné kopie.
 *
 * ---- Proč se případ vybírá až po firmě ----------------------------------
 * Případy se načtou teprve pro zvolenou firmu. Seznam všech případů v systému
 * by byl dlouhý a hlavně by šlo připnout zprávu k případu cizí firmy — což
 * backend stejně odmítne, takže by to byla nabídka vedoucí do chyby.
 */
export default function VyberZakaznika({ pocet = 1, onVyber, onZavri }) {
  const [dotaz, setDotaz] = useState("");
  const [nalezeni, setNalezeni] = useState([]);
  const [hleda, setHleda] = useState(false);
  const [vybrany, setVybrany] = useState(null);
  const [pripady, setPripady] = useState([]);
  const [pripadId, setPripadId] = useState("");
  const [chyba, setChyba] = useState(null);
  const casovac = useRef(null);
  const zivy = useRef(true);

  useEffect(() => {
    zivy.current = true;
    return () => {
      zivy.current = false;
      if (casovac.current) clearTimeout(casovac.current);
    };
  }, []);

  useEffect(() => {
    if (casovac.current) clearTimeout(casovac.current);
    const q = dotaz.trim();
    if (q.length < 2) {
      setNalezeni([]);
      return;
    }
    setHleda(true);
    casovac.current = setTimeout(() => {
      crmZakaznici({ hledat: q })
        .then((d) => zivy.current && setNalezeni((d || []).slice(0, 15)))
        .catch((e) => zivy.current && setChyba(e.message))
        .finally(() => zivy.current && setHleda(false));
    }, 250);
  }, [dotaz]);

  function vyber(z) {
    setVybrany(z);
    setPripadId("");
    setPripady([]);
    crmPripady({ zakaznikId: z.id })
      .then((d) => zivy.current && setPripady(d || []))
      // Bez případů se dá zpráva připojit jen k firmě – nesmí to blokovat.
      .catch(() => setPripady([]));
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div
        className="crm-okno"
        style={{ width: "min(520px, 96vw)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="crm-okno-hlava">
          <h2>Připojit ke klientovi{pocet > 1 ? ` (${pocet} zpráv)` : ""}</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          <div className="em-pole">
            <label htmlFor="vz-hledat">Firma</label>
            <input
              id="vz-hledat"
              value={vybrany ? vybrany.nazev : dotaz}
              onChange={(e) => {
                setVybrany(null);
                setDotaz(e.target.value);
              }}
              placeholder="Začni psát název, IČO nebo město…"
              autoFocus
            />
            {hleda && <span className="crm-tise">Hledám…</span>}
          </div>

          {!vybrany && nalezeni.length > 0 && (
            <div className="ns-navrhy" style={{ position: "static", maxHeight: 260 }}>
              {nalezeni.map((z) => (
                <button
                  type="button"
                  key={z.id}
                  className="ns-navrh"
                  onClick={() => vyber(z)}
                >
                  <span className="ns-navrh-znak" aria-hidden="true">
                    {z.typ === "klient" ? "🏢" : "🌱"}
                  </span>
                  <span className="ns-navrh-text">
                    <span className="ns-navrh-jmeno">{z.nazev}</span>
                    <span className="ns-navrh-popis">
                      {z.typ === "klient" ? "klient" : "lead"}
                      {z.ico ? ` · IČO ${z.ico}` : ""}
                      {z.adresa_mesto ? ` · ${z.adresa_mesto}` : ""}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}

          {!vybrany && dotaz.trim().length >= 2 && !hleda && nalezeni.length === 0 && (
            <p className="crm-tise">Nic se nenašlo. Zkus jiný název nebo IČO.</p>
          )}

          {vybrany && (
            <div className="em-pole">
              <label htmlFor="vz-pripad">Obchodní případ (nepovinné)</label>
              <select
                id="vz-pripad"
                value={pripadId}
                onChange={(e) => setPripadId(e.target.value)}
              >
                <option value="">— jen k firmě —</option>
                {pripady.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.cislo}
                    {p.nazev ? ` · ${p.nazev}` : ""}
                  </option>
                ))}
              </select>
              <span className="crm-tise">
                Bez případu se zpráva ukáže na kartě firmy i u jejích případů.
              </span>
            </div>
          )}

          {chyba && <div className="em-chyba">{chyba}</div>}
        </div>

        <div className="crm-okno-pata">
          <button className="fm-btn" onClick={onZavri}>
            Zrušit
          </button>
          <span className="crm-mezera" />
          <button
            className="fm-btn fm-primary"
            disabled={!vybrany}
            onClick={() =>
              onVyber({
                zakaznik_id: vybrany.id,
                nazev: vybrany.nazev,
                pripad_id: pripadId ? Number(pripadId) : null,
              })
            }
          >
            Připojit
          </button>
        </div>
      </div>
    </div>
  );
}
