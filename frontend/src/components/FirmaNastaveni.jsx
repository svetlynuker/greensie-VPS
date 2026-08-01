import { useEffect, useState } from "react";
import { crmAres, crmFirma, crmFirmaUloz, crmInterniKontakty } from "../api";

/**
 * Admin nastavení → Firma: údaje o nás jako o Greensie.
 *
 * Proč to není záznam v Zákaznících: vlastní firma by lezla do každého filtru,
 * do statistik pipeline i do výběru „komu nabídku". Naše identita je
 * konfigurace appky, ne obchodní záznam.
 *
 * Interní kontakty jsou tady jen ke ČTENÍ a berou se z uživatelů appky —
 * druhá ruční evidence lidí by se s tou první rozešla. Kdo přijde nebo odejde,
 * řeší se v záložce Uživatelé a tady se to hned projeví.
 */

// Skupiny polí = jedna sekce formuláře. Data, a ne ručně psané bloky JSX,
// protože sekcí bude přibývat („další věci v budoucnu") a takhle je přidání
// jeden řádek místo dvaceti.
const SEKCE = [
  {
    nazev: "Identifikace",
    pole: [
      { klic: "nazev", nazev: "Název firmy", sirsi: true, placeholder: "Greensie s.r.o." },
      { klic: "ico", nazev: "IČO" },
      { klic: "dic", nazev: "DIČ", placeholder: "CZ…" },
      { klic: "or_soud", nazev: "Zapsáno u soudu", placeholder: "Městský soud v Praze" },
      { klic: "or_spisova_znacka", nazev: "Spisová značka", placeholder: "C 123456" },
    ],
  },
  {
    nazev: "Adresa sídla",
    pole: [
      { klic: "adresa_ulice", nazev: "Ulice a číslo", sirsi: true },
      { klic: "adresa_psc", nazev: "PSČ" },
      { klic: "adresa_mesto", nazev: "Město" },
      { klic: "adresa_stat", nazev: "Stát" },
    ],
  },
  {
    nazev: "Kontakt",
    pole: [
      { klic: "telefon", nazev: "Telefon" },
      { klic: "email", nazev: "E-mail" },
      { klic: "web", nazev: "Web" },
      { klic: "datova_schranka", nazev: "Datová schránka" },
    ],
  },
  {
    nazev: "Bankovní spojení",
    pole: [
      { klic: "banka_nazev", nazev: "Banka" },
      { klic: "cislo_uctu", nazev: "Číslo účtu", placeholder: "123456789/0800" },
      { klic: "iban", nazev: "IBAN" },
      { klic: "swift", nazev: "SWIFT / BIC" },
    ],
  },
  {
    nazev: "Statutární orgán",
    pole: [
      { klic: "statutar_jmeno", nazev: "Jméno" },
      { klic: "statutar_funkce", nazev: "Funkce", placeholder: "jednatel" },
    ],
  },
];

const KORESPONDENCNI = [
  { klic: "koresp_ulice", nazev: "Ulice a číslo", sirsi: true },
  { klic: "koresp_psc", nazev: "PSČ" },
  { klic: "koresp_mesto", nazev: "Město" },
  { klic: "koresp_stat", nazev: "Stát" },
];

function Mrizka({ pole, firma, muzeEditovat, onZmena }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
        gap: 10,
      }}
    >
      {pole.map((p) => (
        <div key={p.klic} style={p.sirsi ? { gridColumn: "span 2", minWidth: 0 } : { minWidth: 0 }}>
          <label className="gs-label">{p.nazev}</label>
          <input
            className="gs-input"
            value={firma[p.klic] ?? ""}
            placeholder={p.placeholder || ""}
            disabled={!muzeEditovat}
            onChange={(e) => onZmena(p.klic, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
}

function UdajeKarta({ firma, setFirma, onUloz, uklada, stav, chyba }) {
  const [aresStav, setAresStav] = useState(null); // null | "hleda" | text chyby
  const muzeEditovat = Boolean(firma.muze_editovat);

  function zmen(klic, hodnota) {
    setFirma((f) => ({ ...f, [klic]: hodnota }));
  }

  // ARES doplní název, DIČ a sídlo podle IČO. Selhání není chyba appky –
  // uživatel dopíše ručně, proto se hlásí jako poznámka, ne jako červená chyba.
  async function doplnZAresu() {
    const ico = (firma.ico || "").trim();
    if (!ico) {
      setAresStav("Nejdřív vyplň IČO.");
      return;
    }
    setAresStav("hleda");
    try {
      const d = await crmAres(ico);
      setFirma((f) => ({
        ...f,
        nazev: d.nazev || f.nazev,
        ico: d.ico || f.ico,
        dic: d.dic || f.dic,
        adresa_ulice: d.adresa_ulice || f.adresa_ulice,
        adresa_mesto: d.adresa_mesto || f.adresa_mesto,
        adresa_psc: d.adresa_psc || f.adresa_psc,
        adresa_stat: d.adresa_stat || f.adresa_stat,
      }));
      setAresStav(null);
    } catch (e) {
      setAresStav(e.message);
    }
  }

  return (
    <div className="fm-card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <p style={{ margin: 0, fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
        Údaje o nás. Appka je používá tam, kde vystupujeme jako firma — adresa sídla je zároveň to,
        co nabídne tlačítko „U nás" u místa konání schůzky.
        {!muzeEditovat && " Měnit je smí vedení (právo „CRM – měnit nastavení“) nebo supersprávce."}
      </p>

      {SEKCE.map((s) => (
        <div key={s.nazev}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--fm-muted)",
              marginBottom: 6,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            {s.nazev}
            {s.nazev === "Identifikace" && muzeEditovat && (
              <>
                <button
                  className="fm-btn"
                  style={{ padding: "3px 10px", fontSize: 12 }}
                  onClick={doplnZAresu}
                  disabled={aresStav === "hleda"}
                >
                  {aresStav === "hleda" ? "Hledám v ARESu…" : "Doplnit z ARES podle IČO"}
                </button>
                {aresStav && aresStav !== "hleda" && (
                  <span style={{ fontWeight: 400, color: "var(--st-warn, var(--fm-muted))" }}>
                    {aresStav}
                  </span>
                )}
              </>
            )}
          </div>
          <Mrizka pole={s.pole} firma={firma} muzeEditovat={muzeEditovat} onZmena={zmen} />
          {s.nazev === "Identifikace" && (
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                fontSize: 14,
                cursor: muzeEditovat ? "pointer" : "default",
                marginTop: 8,
              }}
            >
              <input
                type="checkbox"
                checked={Boolean(firma.platce_dph)}
                disabled={!muzeEditovat}
                onChange={(e) => zmen("platce_dph", e.target.checked)}
              />
              Plátce DPH
            </label>
          )}
        </div>
      ))}

      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 6 }}>
          Korespondenční adresa
        </div>
        <label
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontSize: 14,
            cursor: muzeEditovat ? "pointer" : "default",
            marginBottom: 8,
          }}
        >
          <input
            type="checkbox"
            checked={Boolean(firma.koresp_stejna)}
            disabled={!muzeEditovat}
            onChange={(e) => zmen("koresp_stejna", e.target.checked)}
          />
          Stejná jako sídlo
        </label>
        {/* Když je stejná jako sídlo, políčka se schovají — vyplněná a zároveň
            ignorovaná adresa je past: člověk ji opraví a nic se nezmění. */}
        {!firma.koresp_stejna && (
          <Mrizka
            pole={KORESPONDENCNI}
            firma={firma}
            muzeEditovat={muzeEditovat}
            onZmena={zmen}
          />
        )}
      </div>

      <div>
        <label className="gs-label">Poznámka</label>
        <textarea
          className="gs-input"
          rows={3}
          value={firma.poznamka ?? ""}
          disabled={!muzeEditovat}
          onChange={(e) => zmen("poznamka", e.target.value)}
        />
      </div>

      {muzeEditovat && (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="fm-btn fm-primary" onClick={onUloz} disabled={uklada}>
            {uklada ? "Ukládám…" : "Uložit údaje o firmě"}
          </button>
          {stav === "ok" && <span style={{ color: "var(--fm-brand-dk)", fontSize: 13 }}>Uloženo ✓</span>}
          {chyba && <span style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</span>}
        </div>
      )}

      {firma.aktualizovano_at && (
        <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
          Naposledy upraveno: {new Date(firma.aktualizovano_at).toLocaleString("cs-CZ")}
        </div>
      )}
    </div>
  );
}

function InterniKontaktyKarta({ lide, onUzivatele }) {
  return (
    <div className="fm-card" style={{ padding: 16 }}>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
        Naši lidé. Seznam se plní <strong>sám</strong> z uživatelů appky — kdo přijde nebo odejde,
        řeší se v záložce Uživatelé. Funkce a telefon jsou z osobního profilu (ten, který si člověk
        vyplňuje pro podpis do e-mailu), takže se nikde nezadávají dvakrát.
      </p>
      <div className="gs-scroll okno" style={{ "--gs-okno": "calc(100vh - 420px)" }}>
        <table className="gs-table">
          <thead>
            <tr>
              <th>Jméno</th>
              <th>Funkce</th>
              <th>Telefon</th>
              <th>E-mail</th>
              <th>Skupina</th>
            </tr>
          </thead>
          <tbody>
            {lide.map((c) => (
              <tr key={c.user_id} className="staticky">
                <td style={{ fontWeight: 600 }}>
                  {c.jmeno}
                  {c.je_admin && <span className="gs-pill znacka" style={{ marginLeft: 6 }}>správce</span>}
                </td>
                <td>{c.funkce || <span style={{ color: "var(--muted)" }}>—</span>}</td>
                <td>{c.telefon || <span style={{ color: "var(--muted)" }}>—</span>}</td>
                <td style={{ color: "var(--muted)" }}>{c.email}</td>
                <td>{c.skupina || <span style={{ color: "var(--muted)" }}>—</span>}</td>
              </tr>
            ))}
            {lide.length === 0 && (
              <tr className="staticky">
                <td colSpan={5} className="gs-empty">
                  Zatím žádní uživatelé appky.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="gs-pozn">
        Prázdná funkce nebo telefon znamená, že si člověk ještě nevyplnil profil (Nastavení →
        Podpis). Lidi se přidávají a odebírají v{" "}
        <button
          className="fm-btn"
          style={{ padding: "2px 8px", fontSize: 12 }}
          onClick={onUzivatele}
        >
          záložce Uživatelé
        </button>
        .
      </div>
    </div>
  );
}

export default function FirmaNastaveni({ onUzivatele }) {
  const [firma, setFirma] = useState(null);
  const [lide, setLide] = useState([]);
  const [uklada, setUklada] = useState(false);
  const [stav, setStav] = useState(null);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    crmFirma()
      .then(setFirma)
      .catch((e) => setChyba(e.message));
    // Interní kontakty jsou doplněk – když se nenačtou, formulář firmy má pořád
    // smysl, proto se chyba polyká.
    crmInterniKontakty()
      .then(setLide)
      .catch(() => setLide([]));
  }, []);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      setFirma(await crmFirmaUloz(firma));
      setStav("ok");
      setTimeout(() => setStav(null), 1800);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  if (!firma) {
    return chyba ? (
      <div className="fm-card" style={{ padding: 16, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
    ) : (
      <div className="fm-card" style={{ padding: 16, color: "var(--fm-muted)" }}>Načítám…</div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="gs-sekce-t">Údaje o firmě</div>
      <UdajeKarta
        firma={firma}
        setFirma={setFirma}
        onUloz={uloz}
        uklada={uklada}
        stav={stav}
        chyba={chyba}
      />

      <div className="gs-sekce-t">
        Interní kontakty
        <span className="gs-tab-cnt"> ({lide.length})</span>
      </div>
      <InterniKontaktyKarta lide={lide} onUzivatele={onUzivatele} />
    </div>
  );
}
