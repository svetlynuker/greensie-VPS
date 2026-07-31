import { useCallback, useEffect, useRef, useState } from "react";
import Layout from "../components/Layout";
import EmailCteni from "../components/EmailCteni";
import EmailNastaveni from "../components/EmailNastaveni";
import EmailPsani from "../components/EmailPsani";
import EmailPravidla from "../components/EmailPravidla";
import {
  emailPripravPreposlani,
  emailPriprevOdpoved,
  emailSlozkaPrepniSync,
  emailSlozky,
  emailSync,
  emailUcet,
  emailZprava,
  emailZpravaDoKose,
  emailZpravaPresun,
  emailZpravaPriznaky,
  emailZpravy,
  nactiMe,
} from "../api";
import "../styles/crm.css";
import "../styles/emaily.css";

/**
 * E-mailový klient v CRM (CRM-33).
 *
 * ---- Proč vlastní klient a ne odkaz na webmail --------------------------
 * Kvůli propojení s CRM. Zpráva se sama napojí na firmu a obchodní případ,
 * takže na kartě zákazníka je vidět komunikace, aniž by ji tam někdo přepisoval.
 * Odkaz na seznam.cz tohle neumí a přepisování ručně nikdo dělat nebude.
 *
 * ---- Kde se pošta bere --------------------------------------------------
 * Seznam zpráv se čte z databáze appky, ne z IMAPu naživo — proto je okamžitý.
 * Stahování dělá **worker mimo web proces** (`greensie-email.service`), takže
 * pomalý IMAP nemůže zpomalit appku. Tlačítko „Zkontrolovat poštu" je pro
 * člověka, který nechce čekat na další cyklus.
 *
 * Automatické obnovení seznamu (`OBNOVA_MS`) je jen dotaz do naší databáze,
 * ne na Seznam — proto se může dít často a nic to nestojí.
 */

// Jak často se přečte seznam zpráv z naší DB. Deset sekund je „živé" a přitom
// je to jeden lehký dotaz; na Seznam se tím nesahá.
const OBNOVA_MS = 10_000;

function fmtKratce(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const dnes = new Date();
  const stejnyDen =
    d.getDate() === dnes.getDate() &&
    d.getMonth() === dnes.getMonth() &&
    d.getFullYear() === dnes.getFullYear();
  // Dnešní pošta ukazuje hodinu (to je to, co člověk hledá), starší datum.
  if (stejnyDen) {
    return d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  }
  if (d.getFullYear() === dnes.getFullYear()) {
    return d.toLocaleDateString("cs-CZ", { day: "numeric", month: "numeric" });
  }
  return d.toLocaleDateString("cs-CZ", { day: "numeric", month: "numeric", year: "2-digit" });
}

export default function Emaily() {
  const [me, setMe] = useState(null);
  const [ucet, setUcet] = useState(null);
  const [nactenUcet, setNactenUcet] = useState(false);
  const [nastaveni, setNastaveni] = useState(false);

  const [slozky, setSlozky] = useState([]);
  const [slozkaId, setSlozkaId] = useState(null);
  const [zpravy, setZpravy] = useState([]);
  const [celkem, setCelkem] = useState(0);
  const [strana, setStrana] = useState(1);
  const [hledat, setHledat] = useState("");
  const [jenNeprectene, setJenNeprectene] = useState(false);

  const [otevrena, setOtevrena] = useState(null);
  const [nacitaZpravu, setNacitaZpravu] = useState(false);
  const [synchronizuje, setSynchronizuje] = useState(false);
  // `null` = zavřeno. Jinak předvyplněná data okna psaní (přijdou z backendu).
  const [psani, setPsani] = useState(null);
  const [pravidla, setPravidla] = useState(false);
  const [hlaska, setHlaska] = useState("");
  const [chyba, setChyba] = useState(null);

  // Aby doběhlá odpověď nepřepsala novější stav (uživatel mezitím klikl dál).
  const zivy = useRef(true);
  useEffect(() => () => { zivy.current = false; }, []);

  useEffect(() => {
    nactiMe().then(setMe).catch(() => {});
  }, []);

  const nactiUcet = useCallback(async () => {
    try {
      const u = await emailUcet();
      if (!zivy.current) return;
      setUcet(u);
      // Bez schránky nemá smysl ukazovat prázdné panely – rovnou nastavení.
      if (!u) setNastaveni(true);
    } catch (e) {
      if (zivy.current) setChyba(e.message);
    } finally {
      if (zivy.current) setNactenUcet(true);
    }
  }, []);

  useEffect(() => {
    nactiUcet();
  }, [nactiUcet]);

  const nactiSlozky = useCallback(async () => {
    if (!ucet) return;
    try {
      const s = await emailSlozky();
      if (!zivy.current) return;
      setSlozky(s);
      setSlozkaId((soucasna) => {
        if (soucasna && s.some((x) => x.id === soucasna)) return soucasna;
        const inbox = s.find((x) => x.druh === "inbox");
        return inbox ? inbox.id : s[0]?.id || null;
      });
    } catch (e) {
      if (zivy.current) setChyba(e.message);
    }
  }, [ucet]);

  useEffect(() => {
    nactiSlozky();
  }, [nactiSlozky]);

  const nactiZpravy = useCallback(
    async (tise = false) => {
      if (!ucet || !slozkaId) return;
      if (!tise) setChyba(null);
      try {
        const d = await emailZpravy({ slozkaId, hledat, jenNeprectene, strana });
        if (!zivy.current) return;
        setZpravy(d.zpravy || []);
        setCelkem(d.celkem || 0);
      } catch (e) {
        // Tiché obnovení nesmí přebít obrazovku chybou – uživatel by dostal
        // hlášku, aniž by o něco žádal.
        if (zivy.current && !tise) setChyba(e.message);
      }
    },
    [ucet, slozkaId, hledat, jenNeprectene, strana],
  );

  useEffect(() => {
    nactiZpravy();
  }, [nactiZpravy]);

  // Živé obnovení: seznam i počty nepřečtených. Čte se z naší DB, ne ze Seznamu.
  useEffect(() => {
    if (!ucet) return undefined;
    const t = setInterval(() => {
      nactiZpravy(true);
      emailSlozky()
        .then((s) => zivy.current && setSlozky(s))
        .catch(() => {});
    }, OBNOVA_MS);
    return () => clearInterval(t);
  }, [ucet, nactiZpravy]);

  async function otevri(z) {
    setNacitaZpravu(true);
    setChyba(null);
    try {
      const detail = await emailZprava(z.id, true);
      if (!zivy.current) return;
      setOtevrena(detail);
      // Přečtení se projeví v seznamu hned, ať to nevypadá, že klik nezabral.
      setZpravy((seznam) =>
        seznam.map((x) => (x.id === detail.id ? { ...x, precteno: true } : x)),
      );
      nactiSlozky();
    } catch (e) {
      if (zivy.current) setChyba(e.message);
    } finally {
      if (zivy.current) setNacitaZpravu(false);
    }
  }

  async function zkontrolujPostu() {
    setSynchronizuje(true);
    setChyba(null);
    setHlaska("");
    try {
      const v = await emailSync(true);
      if (!zivy.current) return;
      setHlaska(v.zprava || "Hotovo.");
      await nactiSlozky();
      await nactiZpravy();
      await nactiUcet();
    } catch (e) {
      if (zivy.current) setChyba(e.message);
    } finally {
      if (zivy.current) setSynchronizuje(false);
    }
  }

  async function zmenPriznaky(z, zmena) {
    try {
      const novy = await emailZpravaPriznaky(z.id, zmena);
      if (!zivy.current) return;
      setZpravy((seznam) => seznam.map((x) => (x.id === novy.id ? { ...x, ...novy } : x)));
      setOtevrena((o) => (o && o.id === novy.id ? { ...o, ...novy } : o));
      nactiSlozky();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function presun(z, cilId) {
    try {
      await emailZpravaPresun(z.id, cilId);
      if (!zivy.current) return;
      // Přesunutá zpráva dostane v cílové složce nové UID, takže z tohohle
      // seznamu prostě zmizí – dotáhne se při další synchronizaci.
      setZpravy((seznam) => seznam.filter((x) => x.id !== z.id));
      setOtevrena((o) => (o && o.id === z.id ? null : o));
      nactiSlozky();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function doKose(z) {
    try {
      await emailZpravaDoKose(z.id);
      if (!zivy.current) return;
      setZpravy((seznam) => seznam.filter((x) => x.id !== z.id));
      setOtevrena((o) => (o && o.id === z.id ? null : o));
      nactiSlozky();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function otevriPsani(pripravit) {
    setChyba(null);
    try {
      const vychozi = await pripravit();
      if (zivy.current) setPsani(vychozi);
    } catch (e) {
      if (zivy.current) setChyba(e.message);
    }
  }

  async function prepniSyncSlozky(s) {
    try {
      await emailSlozkaPrepniSync(s.id);
      nactiSlozky();
    } catch (e) {
      setChyba(e.message);
    }
  }

  const aktivniSlozka = slozky.find((s) => s.id === slozkaId);
  const stran = Math.max(1, Math.ceil(celkem / 50));

  // ---- nastavení / první připojení ----
  if (nastaveni || (nactenUcet && !ucet)) {
    return (
      <Layout uzivatel={me}>
        <EmailNastaveni
          ucet={ucet}
          onHotovo={async () => {
            setNastaveni(false);
            await nactiUcet();
            await nactiSlozky();
          }}
          onZrusit={ucet ? () => setNastaveni(false) : null}
        />
      </Layout>
    );
  }

  if (!nactenUcet) {
    return (
      <Layout uzivatel={me}>
        <div className="em-prazdno">Načítám schránku…</div>
      </Layout>
    );
  }

  return (
    <Layout uzivatel={me}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
          flexWrap: "wrap",
        }}
      >
        <button className="fm-btn fm-primary" onClick={zkontrolujPostu} disabled={synchronizuje}>
          {synchronizuje ? "Kontroluji…" : "Zkontrolovat poštu"}
        </button>
        <span className="em-tise">
          <span
            className={`em-stav-kolecko ${
              ucet.stav === "ok" ? "em-stav-ok" : ucet.stav === "chyba" ? "em-stav-chyba" : ""
            }`}
          />
          {ucet.adresa}
          {ucet.posledni_sync_at
            ? ` · naposledy ${fmtKratce(ucet.posledni_sync_at)}`
            : " · ještě se nestahovalo"}
        </span>
        {hlaska && <span className="em-tise">{hlaska}</span>}
        <span style={{ flex: 1 }} />
        <button
          className="fm-btn"
          onClick={() =>
            setPsani({ komu: [], kopie: [], predmet: "", telo: "" })
          }
        >
          ✎ Napsat
        </button>
        <button className="fm-btn" onClick={() => setPravidla(true)}>
          Pravidla a automatika
          {(ucet.ooo_zapnuto || ucet.preposilani_zapnuto) && (
            /* Zapnuté OOO nebo přeposílání musí být vidět z hlavní obrazovky —
               zapomenutá auto-odpověď po dovolené je trapas. */
            <span className="em-slozka-pocet" style={{ marginLeft: 6 }}>
              {ucet.ooo_zapnuto ? "OOO" : "→"}
            </span>
          )}
        </button>
        <button className="fm-btn" onClick={() => setNastaveni(true)}>
          Nastavení schránky
        </button>
      </div>

      {ucet.stav === "chyba" && ucet.posledni_chyba && (
        <div className="em-chyba" style={{ margin: "0 0 10px" }}>
          Schránka hlásí chybu: {ucet.posledni_chyba}
        </div>
      )}
      {chyba && (
        <div className="em-chyba" style={{ margin: "0 0 10px" }}>
          {chyba}
        </div>
      )}

      <div className="em-app" data-mobil={otevrena ? "cteni" : "seznam"}>
        {/* ---- složky ---- */}
        <div className="em-panel em-panel-slozky">
          <div className="em-panel-hlava">
            <span className="em-panel-nazev">Složky</span>
          </div>
          <div className="em-panel-telo">
            {slozky.map((s) => (
              <button
                key={s.id}
                className={`em-slozka ${s.sync_zapnuto ? "" : "em-slozka-vypnuta"}`}
                aria-current={s.id === slozkaId}
                onClick={() => {
                  setSlozkaId(s.id);
                  setStrana(1);
                  setOtevrena(null);
                }}
                onDoubleClick={() => prepniSyncSlozky(s)}
                title={
                  s.sync_zapnuto
                    ? "Dvojklik vypne stahování téhle složky"
                    : "Složka se nestahuje – dvojklikem zapneš"
                }
              >
                <span className="em-slozka-nazev">{s.nazev}</span>
                {s.nepreectenych > 0 && (
                  <span className="em-slozka-pocet">{s.nepreectenych}</span>
                )}
              </button>
            ))}
            {slozky.length === 0 && (
              <div className="em-prazdno">
                Složky se ještě nenačetly.
                <br />
                Klikni na „Zkontrolovat poštu".
              </div>
            )}
          </div>
        </div>

        {/* ---- seznam zpráv ---- */}
        <div className="em-panel em-panel-seznam">
          <div className="em-panel-hlava">
            <input
              className="em-hledat"
              value={hledat}
              onChange={(e) => {
                setHledat(e.target.value);
                setStrana(1);
              }}
              placeholder={`Hledat v ${aktivniSlozka?.nazev || "poště"}…`}
              aria-label="Hledat v poště"
            />
            <button
              className="fm-btn"
              aria-pressed={jenNeprectene}
              title="Jen nepřečtené"
              onClick={() => {
                setJenNeprectene((p) => !p);
                setStrana(1);
              }}
            >
              ●
            </button>
          </div>
          <div className="em-panel-telo">
            {zpravy.map((z) => (
              <button
                key={z.id}
                className={`em-zprava ${z.precteno ? "" : "em-zprava-neprectena"}`}
                aria-current={otevrena?.id === z.id}
                onClick={() => otevri(z)}
              >
                <div className="em-zprava-radek">
                  {!z.precteno && <span className="em-tecka-neprectena" aria-label="nepřečtená" />}
                  <span className="em-zprava-od">
                    {z.smer === "odchozi"
                      ? `Komu: ${z.komu?.[0]?.jmeno || z.komu?.[0]?.adresa || "—"}`
                      : z.od_jmeno || z.od_adresa}
                  </span>
                  <span className="em-znacky">
                    {z.oznaceno && <span className="em-vlajka" title="Označeno">★</span>}
                    {z.ma_prilohy && <span className="em-sponka" title="Příloha">📎</span>}
                  </span>
                  <span className="em-zprava-datum">{fmtKratce(z.datum_at)}</span>
                </div>
                <div className="em-zprava-predmet">{z.predmet || "(bez předmětu)"}</div>
                {z.vypis && <div className="em-zprava-vypis">{z.vypis}</div>}
                {z.zakaznik_nazev && (
                  <div className="em-firma">
                    {z.zakaznik_nazev}
                    {z.pripad_cislo ? ` · ${z.pripad_cislo}` : ""}
                  </div>
                )}
              </button>
            ))}
            {zpravy.length === 0 && (
              <div className="em-prazdno">
                {hledat || jenNeprectene
                  ? "Nic neodpovídá filtru."
                  : ucet.posledni_sync_at
                    ? "Ve složce nic není."
                    : "Pošta se ještě nestahovala. Klikni na „Zkontrolovat poštu“."}
              </div>
            )}
          </div>
          {stran > 1 && (
            <div className="em-cteni-nastroje">
              <button
                className="fm-btn"
                disabled={strana <= 1}
                onClick={() => setStrana((s) => Math.max(1, s - 1))}
              >
                ←
              </button>
              <span className="em-tise">
                {strana} / {stran} · {celkem} zpráv
              </span>
              <button
                className="fm-btn"
                disabled={strana >= stran}
                onClick={() => setStrana((s) => s + 1)}
              >
                →
              </button>
            </div>
          )}
        </div>

        {/* ---- čtení ---- */}
        {nacitaZpravu && !otevrena ? (
          <div className="em-panel em-panel-cteni">
            <div className="em-prazdno">Otevírám zprávu…</div>
          </div>
        ) : (
          <EmailCteni
            zprava={otevrena}
            slozky={slozky}
            onPriznaky={zmenPriznaky}
            onPresun={presun}
            onDoKose={doKose}
            onZavri={() => setOtevrena(null)}
            onOdpovedet={(z, vsem) =>
              otevriPsani(() => emailPriprevOdpoved(z.id, vsem))
            }
            onPreposlat={(z) => otevriPsani(() => emailPripravPreposlani(z.id))}
          />
        )}
      </div>

      {pravidla && (
        <EmailPravidla
          ucet={ucet}
          slozky={slozky}
          onZmenaUctu={(novy) => setUcet(novy)}
          onZavri={() => setPravidla(false)}
        />
      )}

      {psani && (
        <EmailPsani
          vychozi={psani}
          podpis={ucet.podpis}
          onZavri={() => setPsani(null)}
          onOdeslano={(v) => {
            setPsani(null);
            setHlaska(
              v.poznamka
                ? `Odesláno. ${v.poznamka}`
                : "Zpráva odešla a uložila se do Odeslaných.",
            );
            // Odpověď má na serveru příznak \Answered – projeví se po obnovení.
            nactiZpravy();
            nactiSlozky();
          }}
        />
      )}
    </Layout>
  );
}
