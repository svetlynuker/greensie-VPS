import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import FirmaNastaveni from "../components/FirmaNastaveni";
import {
  nactiMe,
  logout,
  adminCiselniky,
  adminUzivatele,
  adminPridejUzivatele,
  adminUpravUzivatele,
  adminSmazUzivatele,
  adminResetHesla,
  adminSkupiny,
  adminPridejSkupinu,
  adminUpravSkupinu,
  adminSmazSkupinu,
  adminPrihlaseni,
  getSyncNastaveni,
  ulozSyncNastaveni,
} from "../api";

// Záložky = jedno nastavení na záložku. Uživatelé a skupiny jsou systémové,
// synchronizace s Freelem patří modulu Přehled projektů. Až přijdou nastavení
// dalších modulů, přidají se sem jako další záložka.
//
// „Firma" je první schválně: je to identita, ze které vychází všechno ostatní
// (nabídky, podpis pošty, adresa u schůzek).
const ZALOZKY = [
  { klic: "firma", nazev: "Firma" },
  { klic: "uzivatele", nazev: "Uživatelé" },
  { klic: "prihlaseni", nazev: "Přihlášení" },
  { klic: "skupiny", nazev: "Skupiny a práva" },
  { klic: "projekty", nazev: "Přehled projektů" },
];

/* ---------- společný modal ---------- */
function Modal({ nadpis, children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(31,41,51,.45)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 200,
        padding: 16,
      }}
    >
      <div
        className="fm-card"
        onClick={(e) => e.stopPropagation()}
        style={{
          padding: 20,
          width: "min(460px, 100%)",
          maxHeight: "90vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>{nadpis}</h3>
        {children}
      </div>
    </div>
  );
}

/* ---------- výběr práv (zaškrtávátka) ----------
   `zeSkupiny` = práva, která člověk dědí ze své skupiny. Ukazují se
   zaškrtnutá a zamčená, aby bylo vidět, co už má, a nezaškrtávala se podruhé
   jako osobní výjimka — duplikát nic nepřidá, ale později brání odebrání
   práva ze skupiny (viz admin/routes._jen_navic na backendu). */
function PravaVyber({ katalog, vybrana, onZmena, zeSkupiny = [] }) {
  const set = new Set(vybrana);
  const dedene = new Set(zeSkupiny);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {katalog.map((p) => {
        const zdedeno = dedene.has(p.klic);
        return (
          <label
            key={p.klic}
            title={zdedeno ? "Má ze skupiny — odebírá se ve skupině" : undefined}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              cursor: zdedeno ? "default" : "pointer",
            }}
          >
            <input
              type="checkbox"
              checked={zdedeno || set.has(p.klic)}
              disabled={zdedeno}
              onChange={(e) => {
                const nove = new Set(set);
                if (e.target.checked) nove.add(p.klic);
                else nove.delete(p.klic);
                onZmena([...nove]);
              }}
            />
            <span style={{ opacity: zdedeno ? 0.6 : 1 }}>{p.nazev}</span>
            {zdedeno && (
              <span style={{ fontSize: 11, color: "var(--fm-muted)" }}>ze skupiny</span>
            )}
          </label>
        );
      })}
    </div>
  );
}

/* ---------- editor uživatele ---------- */
function UzivatelEditor({ uzivatel, ciselniky, skupiny, onSave, onClose }) {
  const novy = !uzivatel;
  const [jmeno, setJmeno] = useState(uzivatel?.jmeno || "");
  const [email, setEmail] = useState(uzivatel?.email || "");
  const [jeAdmin, setJeAdmin] = useState(uzivatel?.je_admin || false);
  const [skupinaId, setSkupinaId] = useState(uzivatel?.skupina_id ?? "");
  const [extraPrava, setExtraPrava] = useState(uzivatel?.extra_prava || []);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  // Co člověk dědí ze zvolené skupiny, a co bude mít výsledně (skupina + navíc).
  const pravaSkupiny =
    skupinaId === "" ? [] : skupiny.find((s) => s.id === Number(skupinaId))?.prava || [];
  const jenNavic = extraPrava.filter((p) => !pravaSkupiny.includes(p));
  const vysledna = [...new Set([...pravaSkupiny, ...jenNavic])];

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({
        jmeno,
        email,
        je_admin: jeAdmin,
        skupina_id: skupinaId === "" ? null : Number(skupinaId),
        // Posílá se jen to, co je opravdu nad rámec skupiny (backend to hlídá taky).
        extra_prava: jenNavic,
      });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={novy ? "Přidat uživatele" : "Upravit uživatele"} onClose={onClose}>
      <div>
        <label className="gs-label">Jméno</label>
        <input className="gs-input" value={jmeno} onChange={(e) => setJmeno(e.target.value)} placeholder="Jan Novák" />
      </div>
      <div>
        <label className="gs-label">E-mail</label>
        <input className="gs-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jan@greensie.cz" />
      </div>
      {novy && (
        <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
          Heslo se vygeneruje automaticky a pošle uživateli. Při prvním přihlášení si zvolí vlastní.
        </div>
      )}
      <div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
          <input type="checkbox" checked={jeAdmin} onChange={(e) => setJeAdmin(e.target.checked)} />
          <strong>Supersprávce</strong> – plný přístup ke všemu
        </label>
        <div style={{ fontSize: 12, color: "var(--fm-muted)", marginTop: 4 }}>
          {jeAdmin
            ? "Supersprávce vidí a otevře vše; skupina a práva navíc se ignorují."
            : "Na jednotlivé moduly ho nepotřebuješ — stačí zaškrtnout právo níž."}
        </div>
      </div>
      <div style={{ opacity: jeAdmin ? 0.5 : 1, pointerEvents: jeAdmin ? "none" : "auto" }}>
        <label className="gs-label">Skupina</label>
        <select className="gs-input" value={skupinaId} onChange={(e) => setSkupinaId(e.target.value)}>
          <option value="">— žádná —</option>
          {skupiny.map((s) => (
            <option key={s.id} value={s.id}>{s.nazev}</option>
          ))}
        </select>
        <label className="gs-label" style={{ marginTop: 12 }}>Práva</label>
        <div style={{ fontSize: 12, color: "var(--fm-muted)", marginBottom: 6 }}>
          Zaškrtnuté právo modul opravdu otevře — nic dalšího se zapínat nemusí.
          Co má člověk ze skupiny, je zamčené a odebírá se ve skupině.
        </div>
        <PravaVyber
          katalog={ciselniky.prava}
          vybrana={extraPrava}
          onZmena={setExtraPrava}
          zeSkupiny={pravaSkupiny}
        />
        <div style={{ fontSize: 12, color: "var(--fm-muted)", marginTop: 8 }}>
          Výsledně bude mít <b>{vysledna.length}</b>{" "}
          {vysledna.length === 1 ? "právo" : vysledna.length >= 2 && vysledna.length <= 4 ? "práva" : "práv"}
          {pravaSkupiny.length > 0 && ` (${pravaSkupiny.length} ze skupiny, ${jenNavic.length} navíc)`}.
        </div>
      </div>
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- dialog resetu hesla ---------- */
function ResetDialog({ uzivatel, onReset, onClose }) {
  const [rezim, setRezim] = useState("generovat"); // "generovat" | "vlastni"
  const [heslo, setHeslo] = useState("");
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onReset(uzivatel.id, rezim === "vlastni" ? heslo : null);
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={`Reset hesla – ${uzivatel.jmeno}`} onClose={onClose}>
      <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>
        Po resetu si uživatel při dalším přihlášení nastaví vlastní heslo.
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
        <input type="radio" checked={rezim === "generovat"} onChange={() => setRezim("generovat")} />
        Vygenerovat nové heslo
      </label>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, cursor: "pointer" }}>
        <input type="radio" checked={rezim === "vlastni"} onChange={() => setRezim("vlastni")} />
        Zadat vlastní heslo
      </label>
      {rezim === "vlastni" && (
        <input
          className="gs-input"
          type="text"
          value={heslo}
          onChange={(e) => setHeslo(e.target.value)}
          placeholder="alespoň 6 znaků"
        />
      )}
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Resetuji…" : "Resetovat heslo"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- výsledek s heslem (po vytvoření / resetu) ---------- */
function HesloVysledekModal({ vysledek, onClose }) {
  const { uzivatel, heslo, email_odeslan, email_poznamka } = vysledek;
  const odkaz = window.location.origin;
  const [zkopirovano, setZkopirovano] = useState(false);

  function kopiruj() {
    const text = `Přihlášení: ${odkaz}\nE-mail: ${uzivatel.email}\nHeslo: ${heslo}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        setZkopirovano(true);
        setTimeout(() => setZkopirovano(false), 1500);
      });
    }
  }

  return (
    <Modal nadpis="Přihlašovací údaje" onClose={onClose}>
      <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>
        Jednorázové heslo pro <strong>{uzivatel.jmeno}</strong>. Zobrazí se jen teď – zkopíruj si ho.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, background: "var(--fm-head)", borderRadius: 8, padding: 12 }}>
        <div style={{ fontSize: 13 }}><span style={{ color: "var(--fm-muted)" }}>Odkaz: </span>{odkaz}</div>
        <div style={{ fontSize: 13 }}><span style={{ color: "var(--fm-muted)" }}>E-mail: </span>{uzivatel.email}</div>
        <div style={{ fontSize: 16, fontWeight: 700, fontFamily: "monospace" }}>{heslo}</div>
      </div>
      <div style={{ fontSize: 13, color: email_odeslan ? "var(--fm-brand-dk)" : "var(--fm-muted)" }}>
        {email_odeslan ? "✓ Odesláno e-mailem uživateli." : email_poznamka || "E-mail nebyl odeslán."}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={kopiruj}>{zkopirovano ? "Zkopírováno ✓" : "Kopírovat údaje"}</button>
        <button className="fm-btn fm-primary" onClick={onClose}>Hotovo</button>
      </div>
    </Modal>
  );
}

/* ---------- editor skupiny ---------- */
function SkupinaEditor({ skupina, ciselniky, onSave, onClose }) {
  const novy = !skupina;
  const [nazev, setNazev] = useState(skupina?.nazev || "");
  const [prava, setPrava] = useState(skupina?.prava || []);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await onSave({ nazev, prava });
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  return (
    <Modal nadpis={novy ? "Přidat skupinu" : "Upravit skupinu"} onClose={onClose}>
      <div>
        <label className="gs-label">Název skupiny</label>
        <input className="gs-input" value={nazev} onChange={(e) => setNazev(e.target.value)} placeholder="např. Projektoví manažeři" />
      </div>
      <div>
        <label className="gs-label">Co smí členové skupiny</label>
        <PravaVyber katalog={ciselniky.prava} vybrana={prava} onZmena={setPrava} />
      </div>
      {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
        <button className="fm-btn" onClick={onClose} disabled={uklada}>Zrušit</button>
        <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit"}
        </button>
      </div>
    </Modal>
  );
}

/* ---------- barevný štítek práva ---------- */
function Chip({ children }) {
  return (
    <span
      className="gs-pill znacka">{children}</span>
  );
}

/* ---------- karta: synchronizace s Freelem ---------- */
const SYNC_POLE = [
  { klic: "sync_stav", nazev: "Stav (hotovo / nehotovo)", popis: "Když je úkol ve Freelu hotový a v tabulce ne, přepíše se v tabulce na hotovo." },
  { klic: "sync_nove_ukoly", nazev: "Nové úkoly z Freela", popis: "Úkoly, které ve Freelu přibyly, se doplní jako nové sloupce/buňky." },
  { klic: "sync_nove_projekty", nazev: "Nové projekty z Freela", popis: "Projekty, které ve Freelu přibyly, se přidají jako nové řádky." },
  { klic: "sync_terminy", nazev: "Termíny", popis: "Přepíše termín podle Freela – i ručně zadaný." },
  { klic: "sync_osoby", nazev: "Odpovědné osoby", popis: "Přepíše odpovědnou osobu podle Freela – i ručně zadanou." },
];

function SynchronizaceKarta() {
  const [nast, setNast] = useState(null);
  const [uklada, setUklada] = useState(false);
  const [stav, setStav] = useState(null); // "ok" | null
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    getSyncNastaveni()
      .then(setNast)
      .catch((e) => setChyba(e.message));
  }, []);

  function nastav(klic, hodnota) {
    setNast((n) => ({ ...n, [klic]: hodnota }));
    setStav(null);
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      const ulozene = await ulozSyncNastaveni({
        auto_zapnuto: nast.auto_zapnuto,
        interval_min: Number(nast.interval_min),
        sync_stav: nast.sync_stav,
        zapis_stav_do_freela: nast.zapis_stav_do_freela,
        sync_nove_ukoly: nast.sync_nove_ukoly,
        sync_nove_projekty: nast.sync_nove_projekty,
        sync_terminy: nast.sync_terminy,
        sync_osoby: nast.sync_osoby,
      });
      setNast(ulozene);
      setStav("ok");
      setTimeout(() => setStav(null), 1800);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setUklada(false);
    }
  }

  const bunkaStyl = { display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 0" };

  return (
    <div className="fm-card" style={{ padding: 16 }}>
      <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
        Server sám v nastaveném intervalu stáhne data z Freela a promítne je do Přehledu projektů.
        Zaškrtnuté pole se přepíše hodnotou z Freela (i kdyby bylo v tabulce zadané ručně), ostatní
        zůstane beze změny. Poznámky se nepřepisují nikdy.
      </p>

      {!nast ? (
        chyba ? (
          <div style={{ color: "var(--st-crit)", fontSize: 13 }}>Chyba: {chyba}</div>
        ) : (
          <div style={{ color: "var(--fm-muted)", fontSize: 13 }}>Načítám…</div>
        )
      ) : (
        <>
          <label style={{ ...bunkaStyl, alignItems: "center" }}>
            <input
              type="checkbox"
              checked={nast.auto_zapnuto}
              onChange={(e) => nastav("auto_zapnuto", e.target.checked)}
            />
            <span style={{ fontWeight: 600 }}>Zapnout automatickou synchronizaci</span>
          </label>

          <div style={{ ...bunkaStyl, alignItems: "center", opacity: nast.auto_zapnuto ? 1 : 0.5 }}>
            <span style={{ fontSize: 14 }}>Spouštět každých</span>
            <input
              type="number"
              min={5}
              step={5}
              disabled={!nast.auto_zapnuto}
              value={nast.interval_min}
              onChange={(e) => nastav("interval_min", e.target.value)}
              className="gs-input" style={{ width: 90, padding: "6px 8px" }}
            />
            <span style={{ fontSize: 14 }}>minut (nejméně 5)</span>
          </div>

          <div style={{ height: 1, background: "var(--fm-line)", margin: "8px 0" }} />
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 2 }}>
            Co stahovat z Freela do tabulky
          </div>
          {SYNC_POLE.map((pole) => (
            <label key={pole.klic} style={bunkaStyl}>
              <input
                type="checkbox"
                checked={!!nast[pole.klic]}
                onChange={(e) => nastav(pole.klic, e.target.checked)}
                style={{ marginTop: 3 }}
              />
              <span>
                <span style={{ fontWeight: 600 }}>{pole.nazev}</span>
                <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>{pole.popis}</div>
              </span>
            </label>
          ))}

          <div style={{ height: 1, background: "var(--fm-line)", margin: "8px 0" }} />
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--fm-muted)", marginBottom: 2 }}>
            Zápis z tabulky zpět do Freela
          </div>
          <label style={bunkaStyl}>
            <input
              type="checkbox"
              checked={!!nast.zapis_stav_do_freela}
              onChange={(e) => nastav("zapis_stav_do_freela", e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              <span style={{ fontWeight: 600 }}>Zapisovat změnu stavu zpět do Freela</span>
              <div style={{ fontSize: 12, color: "var(--fm-muted)" }}>
                Když v tabulce označíš úkol jako hotový/nehotový, změní se stav i ve Freelu. Spolu se
                stahováním stavu (nahoře) tak stav funguje obousměrně. Píše se do reálného Freela.
              </div>
            </span>
          </label>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <button className="fm-btn fm-primary" onClick={uloz} disabled={uklada}>
              {uklada ? "Ukládám…" : "Uložit nastavení"}
            </button>
            {stav === "ok" && <span style={{ color: "var(--fm-brand-dk)", fontSize: 13 }}>Uloženo ✓</span>}
            {chyba && <span style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</span>}
          </div>

          <div style={{ marginTop: 12, fontSize: 12, color: "var(--fm-muted)" }}>
            Naposledy proběhlo:{" "}
            {nast.posledni_beh
              ? new Date(nast.posledni_beh).toLocaleString("cs-CZ")
              : "zatím neproběhlo"}
            {nast.posledni_vysledek ? ` — ${nast.posledni_vysledek}` : ""}
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- karta: historie přihlášení ---------- */
// „Kdy naposledy" v lidské řeči. Přesný čas zůstává v title atributu — v přehledu
// se čte líp „před 2 h" než datum, které si musí člověk porovnat s dneškem.
function predJakDlouho(iso) {
  if (!iso) return null;
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "právě teď";
  if (min < 60) return `před ${min} min`;
  const hod = Math.round(min / 60);
  if (hod < 24) return `před ${hod} h`;
  const dni = Math.round(hod / 24);
  if (dni < 31) return `před ${dni} dny`;
  return new Date(iso).toLocaleDateString("cs-CZ");
}

function casPresne(iso) {
  try {
    return new Date(iso).toLocaleString("cs-CZ");
  } catch {
    return iso;
  }
}

const OBDOBI = [
  { klic: 7, nazev: "posledních 7 dní" },
  { klic: 30, nazev: "posledních 30 dní" },
  { klic: 90, nazev: "posledních 90 dní" },
  { klic: 0, nazev: "celá historie" },
];

function PrihlaseniKarta({ uzivatele, vyber, onVyber }) {
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [jenNeuspesne, setJenNeuspesne] = useState(false);
  const [dni, setDni] = useState(30);
  const [hledej, setHledej] = useState("");
  const [hledejQ, setHledejQ] = useState("");

  // hledání se neposílá na každý úhoz, ale až 400 ms po dopsání
  useEffect(() => {
    const id = setTimeout(() => setHledejQ(hledej), 400);
    return () => clearTimeout(id);
  }, [hledej]);

  useEffect(() => {
    let platne = true;
    adminPrihlaseni({
      uzivatelId: vyber || undefined,
      jenNeuspesne,
      dni: dni || undefined,
      hledej: hledejQ || undefined,
      limit: 500,
    })
      .then((d) => {
        if (!platne) return;
        setData(d);
        setChyba(null);
      })
      .catch((e) => platne && setChyba(e.message));
    return () => {
      platne = false;
    };
  }, [vyber, jenNeuspesne, dni, hledejQ]);

  const zaznamy = data?.zaznamy || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div
        className="fm-card"
        style={{ padding: 12, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}
      >
        <select
          className="gs-input"
          style={{ padding: "6px 8px" }}
          value={vyber || ""}
          onChange={(e) => onVyber(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Všichni uživatelé</option>
          {uzivatele.map((u) => (
            <option key={u.id} value={u.id}>
              {u.jmeno}
            </option>
          ))}
        </select>

        <select
          className="gs-input"
          style={{ padding: "6px 8px" }}
          value={dni}
          onChange={(e) => setDni(Number(e.target.value))}
        >
          {OBDOBI.map((o) => (
            <option key={o.klic} value={o.klic}>
              {o.nazev}
            </option>
          ))}
        </select>

        <input
          type="text"
          className="gs-input"
          placeholder="Hledat ve jménu, e-mailu, IP nebo zařízení…"
          value={hledej}
          onChange={(e) => setHledej(e.target.value)}
          style={{ padding: "6px 8px", minWidth: 240, flex: "1 1 240px" }}
        />

        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
          <input
            type="checkbox"
            checked={jenNeuspesne}
            onChange={(e) => setJenNeuspesne(e.target.checked)}
          />
          Jen nepovedené pokusy
        </label>
      </div>

      {data && data.neuspechy_24h > 0 && (
        <div className="fm-card" style={{ padding: "8px 12px", fontSize: 13 }}>
          <span style={{ color: "var(--st-warn)", fontWeight: 600 }}>
            ⚠ Za posledních 24 hodin: {data.neuspechy_24h} nepovedených pokusů o přihlášení.
          </span>{" "}
          <span style={{ color: "var(--muted)" }}>
            Většinou jde o překlep v hesle. Když se ale opakují z neznámé IP, stojí za to
            dotyčnému resetovat heslo.
          </span>
        </div>
      )}

      {chyba && (
        <div className="fm-card" style={{ padding: 12, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      )}

      <div className="gs-scroll okno" style={{ "--gs-okno": "calc(100vh - 330px)" }}>
        <table className="gs-table">
          <thead>
            <tr>
              <th>Kdy</th>
              <th>Kdo</th>
              <th>Výsledek</th>
              <th>Odkud (IP)</th>
              <th>Zařízení</th>
            </tr>
          </thead>
          <tbody>
            {zaznamy.map((z) => (
              <tr key={z.id} className="staticky">
                <td style={{ whiteSpace: "nowrap" }} title={casPresne(z.cas)}>
                  {casPresne(z.cas)}
                </td>
                <td>
                  <span style={{ fontWeight: 600 }}>{z.uzivatel_jmeno || "—"}</span>
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>{z.uzivatel_email || "neznámý účet"}</div>
                </td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {z.uspech ? (
                    <span style={{ color: "var(--st-good)", fontWeight: 600 }}>✓ přihlášen</span>
                  ) : (
                    <span style={{ color: "var(--st-crit)", fontWeight: 600 }}>
                      ✕ nepovedlo se
                      {z.duvod ? <span style={{ fontWeight: 400 }}> — {z.duvod}</span> : null}
                    </span>
                  )}
                </td>
                <td style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{z.ip || "—"}</td>
                <td style={{ color: "var(--muted)" }}>{z.zarizeni || "—"}</td>
              </tr>
            ))}
            {data && zaznamy.length === 0 && (
              <tr className="staticky">
                <td colSpan={5} className="gs-empty">Za zvolené období tu nic není.</td>
              </tr>
            )}
            {!data && !chyba && (
              <tr className="staticky">
                <td colSpan={5} className="gs-empty">Načítám…</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="gs-pozn">
        Zaznamenává se každé přihlášení i každý nepovedený pokus. Na rozdíl od Logů se tyhle
        záznamy nemažou — otázka „kdo se sem kdy dostal" se řeší většinou až zpětně.
        U záznamů z doby před zavedením přehledu chybí IP a zařízení.
      </div>
    </div>
  );
}

export default function AdminNastaveni() {
  const [uzivatel, setUzivatel] = useState(null);
  const [ciselniky, setCiselniky] = useState(null);
  const [uzivatele, setUzivatele] = useState([]);
  const [skupiny, setSkupiny] = useState([]);
  const [chyba, setChyba] = useState(null);
  const [editUzivatel, setEditUzivatel] = useState(null); // {} = nový, obj = úprava
  const [editSkupina, setEditSkupina] = useState(null);
  const [resetUzivatel, setResetUzivatel] = useState(null);
  const [hesloVysledek, setHesloVysledek] = useState(null);
  const [zalozka, setZalozka] = useState("firma");
  // filtr historie přihlášení; drží ho stránka, ať přežije proklik z uživatelů
  const [prihlaseniUzivatel, setPrihlaseniUzivatel] = useState(null);
  const navigate = useNavigate();

  const nazvyPrav = (klice) => {
    if (!ciselniky) return [];
    return ciselniky.prava.filter((p) => klice.includes(p.klic)).map((p) => p.nazev);
  };
  const nazevSkupiny = (id) => skupiny.find((s) => s.id === id)?.nazev || "—";

  async function nactiVse() {
    const [c, u, s] = await Promise.all([adminCiselniky(), adminUzivatele(), adminSkupiny()]);
    setCiselniky(c);
    setUzivatele(u);
    setSkupiny(s);
  }

  useEffect(() => {
    nactiMe()
      .then((me) => {
        if (me.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setUzivatel(me.uzivatel);
        return nactiVse();
      })
      .catch((e) => {
        const m = String(e.message);
        if (m.includes("přihlášení")) {
          logout();
          navigate("/");
        } else {
          setChyba(m); // typicky 403 = nemáš na admin právo
        }
      });
  }, [navigate]);

  async function ulozUzivatele(data) {
    if (editUzivatel && editUzivatel.id) {
      await adminUpravUzivatele(editUzivatel.id, data);
      setEditUzivatel(null);
      await nactiVse();
    } else {
      const vysledek = await adminPridejUzivatele(data);
      setEditUzivatel(null);
      await nactiVse();
      setHesloVysledek(vysledek); // zobrazí jednorázové heslo + odkaz
    }
  }
  async function provedReset(id, noveHeslo) {
    const vysledek = await adminResetHesla(id, noveHeslo);
    setResetUzivatel(null);
    await nactiVse();
    setHesloVysledek(vysledek);
  }
  async function smazUzivatele(u) {
    if (!window.confirm(`Opravdu smazat uživatele ${u.jmeno}?`)) return;
    try {
      await adminSmazUzivatele(u.id);
      await nactiVse();
    } catch (e) {
      alert(e.message);
    }
  }
  async function ulozSkupinu(data) {
    if (editSkupina && editSkupina.id) await adminUpravSkupinu(editSkupina.id, data);
    else await adminPridejSkupinu(data);
    setEditSkupina(null);
    await nactiVse();
  }
  async function smazSkupinu(s) {
    if (!window.confirm(`Opravdu smazat skupinu „${s.nazev}"? Členům se skupina odebere.`)) return;
    try {
      await adminSmazSkupinu(s.id);
      await nactiVse();
    } catch (e) {
      alert(e.message);
    }
  }

  if (chyba) {
    return (
      <Layout uzivatel={uzivatel}>
        <Link to="/rozcestnik" className="fm-btn" style={{ textDecoration: "none" }}>← Zpět na rozcestník</Link>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!ciselniky) return null;

  return (
    <Layout uzivatel={uzivatel}>
      <div className="gs-modul">
        <Link to="/rozcestnik" className="gs-backlink">
          ← Zpět na rozcestník
        </Link>

        {/* Nadpis stránky nese horní lišta rámce, tady rovnou záložky. */}
        <div className="gs-tabs" role="tablist" aria-label="Nastavení">
          {ZALOZKY.map((z) => (
            <button
              key={z.klic}
              type="button"
              role="tab"
              aria-selected={zalozka === z.klic}
              onClick={() => setZalozka(z.klic)}
            >
              {z.nazev}
              {z.klic === "uzivatele" && <span className="gs-tab-cnt"> ({uzivatele.length})</span>}
              {z.klic === "skupiny" && <span className="gs-tab-cnt"> ({skupiny.length})</span>}
            </button>
          ))}
        </div>

        {/* ---------- záložka: firma (údaje o nás) ---------- */}
        {zalozka === "firma" && (
          <div role="tabpanel">
            <FirmaNastaveni onUzivatele={() => setZalozka("uzivatele")} />
          </div>
        )}

        {/* ---------- záložka: uživatelé ---------- */}
        {zalozka === "uzivatele" && (
          <div role="tabpanel">
            <div className="gs-sekce-t">
              Uživatelé a přístupy
              <span className="gs-mezera" />
              <button className="fm-btn fm-primary" onClick={() => setEditUzivatel({})}>+ Přidat uživatele</button>
            </div>
            <div className="gs-scroll okno" style={{ "--gs-okno": "calc(100vh - 260px)" }}>
              <table className="gs-table">
                <thead>
                  <tr>
                    <th>Jméno</th>
                    <th>E-mail</th>
                    <th>Přístup</th>
                    <th>Naposledy přihlášen</th>
                    <th>Skupina</th>
                    <th>Práva navíc</th>
                    <th className="n">Akce</th>
                  </tr>
                </thead>
                <tbody>
                  {uzivatele.map((u) => (
                    <tr key={u.id} className="staticky">
                      <td style={{ fontWeight: 600 }}>{u.jmeno}</td>
                      <td style={{ color: "var(--muted)" }}>{u.email}</td>
                      <td>
                        {u.je_admin ? <Chip>Supersprávce</Chip> : <span style={{ color: "var(--muted)" }}>Uživatel</span>}
                        {u.musi_zmenit_heslo && (
                          <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>🔑 čeká na změnu hesla</div>
                        )}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {u.posledni_prihlaseni ? (
                          <button
                            type="button"
                            title={`${casPresne(u.posledni_prihlaseni)} — zobrazit historii`}
                            onClick={() => {
                              setPrihlaseniUzivatel(u.id);
                              setZalozka("prihlaseni");
                            }}
                            style={{ background: "none", border: 0, padding: 0, cursor: "pointer", color: "inherit", textDecoration: "underline dotted" }}
                          >
                            {predJakDlouho(u.posledni_prihlaseni)}
                          </button>
                        ) : (
                          <span style={{ color: "var(--muted)" }}>nikdy</span>
                        )}
                      </td>
                      <td>{u.skupina_id ? nazevSkupiny(u.skupina_id) : <span style={{ color: "var(--muted)" }}>—</span>}</td>
                      <td>
                        <span style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {u.extra_prava.length ? nazvyPrav(u.extra_prava).map((n) => <Chip key={n}>{n}</Chip>) : <span style={{ color: "var(--muted)" }}>—</span>}
                        </span>
                      </td>
                      <td className="n" style={{ whiteSpace: "nowrap" }}>
                        <button className="fm-btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setEditUzivatel(u)}>Upravit</button>{" "}
                        <button className="fm-btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setResetUzivatel(u)}>Reset hesla</button>{" "}
                        <button className="fm-btn" style={{ padding: "4px 10px", fontSize: 12, color: "var(--st-crit)" }} onClick={() => smazUzivatele(u)}>Smazat</button>
                      </td>
                    </tr>
                  ))}
                  {uzivatele.length === 0 && (
                    <tr className="staticky"><td colSpan={7} className="gs-empty">Zatím žádní uživatelé.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="gs-pozn">
              Nový uživatel dostane jednorázové heslo, které si při prvním přihlášení změní.
              Supersprávce vidí vše bez ohledu na skupinu.
            </div>
          </div>
        )}

        {/* ---------- záložka: historie přihlášení ---------- */}
        {zalozka === "prihlaseni" && (
          <div role="tabpanel">
            <div className="gs-sekce-t">Historie přihlášení</div>
            <PrihlaseniKarta
              uzivatele={uzivatele}
              vyber={prihlaseniUzivatel}
              onVyber={setPrihlaseniUzivatel}
            />
          </div>
        )}

        {/* ---------- záložka: skupiny a práva ---------- */}
        {zalozka === "skupiny" && (
          <div role="tabpanel">
            <div className="gs-sekce-t">
              Skupiny a práva
              <span className="gs-mezera" />
              <button className="fm-btn fm-primary" onClick={() => setEditSkupina({})}>+ Přidat skupinu</button>
            </div>
            {skupiny.length === 0 ? (
              <div className="fm-card gs-empty">
                Zatím žádné skupiny. Skupina sdružuje uživatele se stejnými právy – vytvoř si třeba
                „Vedení" a zaškrtni, co smí otevřít.
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {skupiny.map((s) => (
                  <div
                    key={s.id}
                    className="fm-card"
                    style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 14px", flexWrap: "wrap" }}
                  >
                    <div style={{ minWidth: 140 }}>
                      <div style={{ fontWeight: 700 }}>{s.nazev}</div>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>{s.pocet_clenu} členů</div>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, flex: 1 }}>
                      {s.prava.length ? nazvyPrav(s.prava).map((n) => <Chip key={n}>{n}</Chip>) : <span style={{ color: "var(--muted)", fontSize: 13 }}>žádná práva</span>}
                    </div>
                    <button className="fm-btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => setEditSkupina(s)}>Upravit</button>
                    <button className="fm-btn" style={{ padding: "4px 10px", fontSize: 12, color: "var(--st-crit)" }} onClick={() => smazSkupinu(s)}>Smazat</button>
                  </div>
                ))}
              </div>
            )}
            <div className="gs-pozn">
              Právo lze dát i jednotlivci mimo skupinu — v úpravě uživatele jako „práva navíc".
              Skrytí sekce v levém panelu je pohodlí, ne ochrana: každý modul si právo hlídá i na serveru.
            </div>
          </div>
        )}

        {/* ---------- záložka: nastavení modulu Přehled projektů ---------- */}
        {zalozka === "projekty" && (
          <div role="tabpanel">
            <div className="gs-sekce-t">Přehled projektů — synchronizace s Freelem</div>
            <SynchronizaceKarta />
          </div>
        )}
      </div>

      {editUzivatel && (
        <UzivatelEditor
          uzivatel={editUzivatel.id ? editUzivatel : null}
          ciselniky={ciselniky}
          skupiny={skupiny}
          onSave={ulozUzivatele}
          onClose={() => setEditUzivatel(null)}
        />
      )}
      {editSkupina && (
        <SkupinaEditor
          skupina={editSkupina.id ? editSkupina : null}
          ciselniky={ciselniky}
          onSave={ulozSkupinu}
          onClose={() => setEditSkupina(null)}
        />
      )}
      {resetUzivatel && (
        <ResetDialog
          uzivatel={resetUzivatel}
          onReset={provedReset}
          onClose={() => setResetUzivatel(null)}
        />
      )}
      {hesloVysledek && (
        <HesloVysledekModal vysledek={hesloVysledek} onClose={() => setHesloVysledek(null)} />
      )}
    </Layout>
  );
}
