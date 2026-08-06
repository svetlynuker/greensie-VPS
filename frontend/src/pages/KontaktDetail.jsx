import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Layout from "../components/Layout";
import Pritomni from "../components/Pritomni";
import StavUlozeni from "../components/StavUlozeni";
import { crmKontaktDetail, crmKontaktUpravZKarty, logout, nactiMe } from "../api";
import { useZaznamAutosave } from "../hooks/useZaznamAutosave";
import { fmtDatum, fmtDatumCas } from "../crm";
import "../styles/crm.css";

// Pole, která se ukládají sama. `hlavni` tu schválně NENÍ: přehazuje příznak
// i ostatním osobám téže firmy, takže patří na vědomé kliknutí, ne na psaní.
const POLE = ["jmeno", "funkce", "telefon", "email", "poznamka"];

const NAZVY_POLI = {
  jmeno: "Jméno",
  funkce: "Funkce",
  telefon: "Telefon",
  email: "E-mail",
  poznamka: "Poznámka",
};

/**
 * Karta kontaktní osoby.
 *
 * Co tu SCHVÁLNĚ není: aktivity a úkoly. V datech visí na firmě nebo na
 * obchodním případu, ne na člověku, takže by karta jen opisovala kartu
 * zákazníka. Případy firmy jsou tu jako kontext („o čem s ním je řeč"),
 * e-mailová historie naopak patří přímo osobě – ta je navázaná na ni.
 *
 * Úpravy se ukládají samy, pole po poli (`useZaznamAutosave`). Tlačítko
 * „Uložit" tu proto není: posílalo celý objekt, takže dva lidé nad jednou
 * osobou si navzájem přepsali i pole, kterých se ani nedotkli. „Hotovo" jen
 * zavře režim úprav (a dožene, co se ještě nestihlo odeslat).
 */
export default function KontaktDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [k, setK] = useState(null);
  const [upravuje, setUpravuje] = useState(false);
  const [chyba, setChyba] = useState(null);

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
    entita: "kontakt",
    id,
    zaznam: k,
    pole: POLE,
    entitaTyp: "crm_kontakt",
    // Přítomnost („kdo tu je") běží pořád, ne jen v režimu úprav — člověk má
    // vidět kolegu ještě předtím, než klikne na „Upravit".
    zapnuto: Boolean(k),
  });

  function nactiDetail() {
    return crmKontaktDetail(id)
      .then(setK)
      .catch(() => {});
  }

  useEffect(() => {
    Promise.all([nactiMe(), crmKontaktDetail(id)])
      .then(([m, detail]) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("zakaznici")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        setK(detail);
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

  // Razítko se změnilo → někdo (nebo já z jiného okna) osobu upravil, natáhneme
  // ji znovu. První razítko se jen zapamatuje, jinak by se karta po načtení
  // obnovila zbytečně. Rozepsané pole hook nepřepíše, takže to nic nesebere.
  const razitkoRef = useRef(null);
  useEffect(() => {
    if (!razitko) return;
    if (razitkoRef.current === null || razitkoRef.current === razitko) {
      razitkoRef.current = razitko;
      return;
    }
    razitkoRef.current = razitko;
    nactiDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [razitko]);

  // Zrcadla pro `hotovo()`: po `await` je stav z renderu starý, a rozhodovat se
  // podle něj by znamenalo zavřít úpravy nad neuloženým textem.
  const kolizeRef = useRef(kolize);
  kolizeRef.current = kolize;
  const stavRef = useRef(stav);
  stavRef.current = stav;

  /** Konec úprav: dožene neodeslané změny a přinese čerstvá data pro výpis. */
  async function hotovo() {
    if (kolize) {
      setChyba("Nejdřív rozhodni, čí hodnota u kolize platí — pak úpravy zavři.");
      return;
    }
    await dokonci();
    if (kolizeRef.current || stavRef.current === "chyba") {
      setChyba("Něco se neuložilo – režim úprav nechávám otevřený, ať o text nepřijdeš.");
      return;
    }
    setChyba(null);
    setUpravuje(false);
    await nactiDetail();
  }

  /**
   * Hlavní kontakt firmy — vědomá akce, ne autosave.
   *
   * Příznak se přehazuje i ostatním osobám téže firmy, takže se nesmí spustit
   * uprostřed psaní. Jde starou cestou (PUT celého objektu), a proto se před ní
   * dožene rozepsané pole a znovu načtou čerstvé údaje — jinak by PUT vrátil do
   * databáze text, který mezitím někdo přepsal.
   */
  async function prepniHlavni() {
    setChyba(null);
    try {
      await dokonci();
      const cerstvy = await crmKontaktDetail(id);
      setK(
        await crmKontaktUpravZKarty(id, {
          jmeno: cerstvy.jmeno,
          funkce: cerstvy.funkce,
          email: cerstvy.email,
          telefon: cerstvy.telefon,
          poznamka: cerstvy.poznamka,
          hlavni: !cerstvy.hlavni,
        }),
      );
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !k) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !k) return null;

  // V režimu úprav je pravda o jménu v rozepsaném poli, ne v posledním
  // natažení — jinak by nadpis karty ukazoval staré jméno.
  const jmenoNadpis = (upravuje ? hodnoty.jmeno : k.jmeno) || k.jmeno;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app">
        <Link to="/kontakty" className="crm-zpet">
          ← Zpět na Kontaktní osoby
        </Link>

        <div className="crm-karta-hlava">
          <div style={{ minWidth: 0 }}>
            <h1>{jmenoNadpis}</h1>
            <div className="crm-karta-radek">
              {(upravuje ? hodnoty.funkce : k.funkce) || "bez funkce"}
              {" · "}
              <Link to={`/zakaznici/detail/${k.zakaznik_id}`} className="crm-odkaz">
                {k.zakaznik_nazev}
              </Link>
              {k.vlastnik_jmeno ? ` · vlastník firmy ${k.vlastnik_jmeno}` : ""}
            </div>
          </div>
          <span className="crm-mezera" />
          {/* Kdo má kartu otevřenou taky – ať je vidět, s kým se člověk může
              potkat, ještě než napíše první znak. */}
          <Pritomni pritomni={pritomni} popisekPole={(p) => NAZVY_POLI[p] || p} />
          <StavUlozeni stav={stav} chyba={chybaUlozeni} kdy={kdy} />
          {k.hlavni && <span className="crm-znacka crm-barva-ok">hlavní kontakt</span>}
          <span
            className={`crm-znacka ${
              k.zakaznik_typ === "klient" ? "crm-barva-ok" : "crm-barva-info"
            }`}
          >
            {k.zakaznik_typ === "klient" ? "Klient" : "Lead"}
          </span>
          {k.muze_editovat && (
            <button
              className="fm-btn"
              onClick={prepniHlavni}
              title="Příznak se přehodí i ostatním osobám firmy"
            >
              {k.hlavni ? "Zrušit hlavní kontakt" : "Nastavit jako hlavní"}
            </button>
          )}
          {k.muze_editovat && !upravuje && (
            <button className="fm-btn" onClick={() => setUpravuje(true)}>
              Upravit
            </button>
          )}
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        <div className="crm-dva-sloupce">
          <div className="fm-card crm-blok">
            <h3>Údaje</h3>
            {upravuje ? (
              <>
                <div className="crm-mrizka">
                  <div>
                    <label className="crm-label">Jméno *</label>
                    <input
                      className="crm-pole"
                      value={hodnoty.jmeno}
                      onChange={(e) => zmen("jmeno", e.target.value)}
                      onFocus={() => onFokus("jmeno")}
                      onBlur={() => onBlur("jmeno")}
                    />
                    {/* Jméno se neblokuje, jen se na prázdné upozorní: při
                        ukládání za pochodu je rozepsaný (i chvíli prázdný) stav
                        normální, a zamknout vstup by znamenalo, že si člověk
                        jméno nemůže přepsat od začátku. */}
                    {!hodnoty.jmeno.trim() && (
                      <p className="crm-tise" style={{ color: "var(--st-crit)" }}>
                        Bez jména osobu nikdo v seznamu nenajde.
                      </p>
                    )}
                  </div>
                  <div>
                    <label className="crm-label">Funkce</label>
                    <input
                      className="crm-pole"
                      value={hodnoty.funkce}
                      onChange={(e) => zmen("funkce", e.target.value)}
                      onFocus={() => onFokus("funkce")}
                      onBlur={() => onBlur("funkce")}
                      placeholder="jednatel, energetik…"
                    />
                  </div>
                  <div>
                    <label className="crm-label">Telefon</label>
                    <input
                      className="crm-pole"
                      value={hodnoty.telefon}
                      onChange={(e) => zmen("telefon", e.target.value)}
                      onFocus={() => onFokus("telefon")}
                      onBlur={() => onBlur("telefon")}
                    />
                  </div>
                  <div>
                    <label className="crm-label">E-mail</label>
                    <input
                      className="crm-pole"
                      value={hodnoty.email}
                      onChange={(e) => zmen("email", e.target.value)}
                      onFocus={() => onFokus("email")}
                      onBlur={() => onBlur("email")}
                    />
                  </div>
                </div>
                <label className="crm-label" style={{ marginTop: 8 }}>
                  Poznámka
                </label>
                <textarea
                  className="crm-pole"
                  rows={3}
                  value={hodnoty.poznamka}
                  onChange={(e) => zmen("poznamka", e.target.value)}
                  onFocus={() => onFokus("poznamka")}
                  onBlur={() => onBlur("poznamka")}
                />

                {/* Kolize: nic se nepřepsalo, člověk rozhodne, čí hodnota platí. */}
                {kolize && (
                  <div className="crm-kolize">
                    <div>
                      <strong>{NAZVY_POLI[kolize.pole] || kolize.pole}</strong> mezitím změnil
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

                <div className="crm-blok-pata">
                  <span className="crm-tise">
                    Změny se ukládají samy, tlačítko jen zavře úpravy.
                  </span>
                  <span className="crm-mezera" />
                  {/* Stav ukládání je v hlavičce karty — na jednom místě, ať
                      člověk nehledá dvě hlášky, které říkají totéž. */}
                  <button className="fm-btn fm-primary" onClick={hotovo}>
                    Hotovo
                  </button>
                </div>
              </>
            ) : (
              <>
                <dl className="crm-udaje">
                  <dt>Jméno</dt>
                  <dd>{k.jmeno}</dd>
                  <dt>Funkce</dt>
                  <dd>{k.funkce || "—"}</dd>
                  <dt>Telefon</dt>
                  <dd>{k.telefon ? <a href={`tel:${k.telefon}`}>{k.telefon}</a> : "—"}</dd>
                  <dt>E-mail</dt>
                  <dd>{k.email ? <a href={`mailto:${k.email}`}>{k.email}</a> : "—"}</dd>
                  <dt>Vytvořeno</dt>
                  <dd>{fmtDatum(k.vytvoreno_at) || "—"}</dd>
                </dl>
                {k.poznamka && <p className="crm-poznamka">{k.poznamka}</p>}
              </>
            )}
          </div>

          <div className="crm-sloupec-bloky">
            <div className="fm-card crm-blok">
              <h3>Firma</h3>
              <dl className="crm-udaje">
                <dt>Název</dt>
                <dd>
                  <Link to={`/zakaznici/detail/${k.zakaznik_id}`} className="crm-odkaz">
                    {k.zakaznik_nazev}
                  </Link>
                </dd>
                <dt>Město</dt>
                <dd>{k.zakaznik_mesto || "—"}</dd>
                <dt>Telefon firmy</dt>
                <dd>{k.zakaznik_telefon || "—"}</dd>
                <dt>E-mail firmy</dt>
                <dd>{k.zakaznik_email || "—"}</dd>
              </dl>
            </div>

            <div className="fm-card crm-blok">
              <h3>Obchodní případy firmy</h3>
              {k.pripady.length === 0 ? (
                <p className="crm-tise">U firmy zatím není žádný obchodní případ.</p>
              ) : (
                <ul className="crm-kontakty">
                  {k.pripady.map((p) => (
                    <li key={p.id}>
                      <div style={{ minWidth: 0 }}>
                        <div className="crm-kontakt-jmeno">
                          <Link to={`/pripady/detail/${p.id}`} className="crm-odkaz">
                            {p.cislo || `případ #${p.id}`}
                          </Link>
                        </div>
                        <div className="crm-tise">
                          {[p.nazev, p.stav].filter(Boolean).join(" · ") || "—"}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="fm-card crm-blok">
              <h3>E-mailová komunikace</h3>
              {k.emaily.length === 0 ? (
                <p className="crm-tise">
                  S touhle osobou zatím v appce neproběhla žádná e-mailová komunikace. Napojuje se
                  automaticky podle adresy — tedy jen když ji má osoba vyplněnou.
                </p>
              ) : (
                <ul className="crm-kontakty">
                  {k.emaily.map((e) => (
                    <li key={e.zprava_id}>
                      <div style={{ minWidth: 0 }}>
                        <div className="crm-kontakt-jmeno">{e.predmet}</div>
                        <div className="crm-tise">
                          {e.smer === "odchozi" ? "odesláno" : "přijato"}
                          {e.kdy ? ` · ${fmtDatumCas(e.kdy)}` : ""}
                          {e.od_adresa ? ` · ${e.od_adresa}` : ""}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
