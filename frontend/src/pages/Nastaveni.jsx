import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import AutomatizaceNastaveni from "../components/AutomatizaceNastaveni";
import Ikona from "../components/Ikona";
import NotifikaceNastaveni from "../components/NotifikaceNastaveni";
import PodpisNastaveni from "../components/PodpisNastaveni";
import SablonyTextuNastaveni from "../components/SablonyTextuNastaveni";
import { logout, nactiMe, nactiNastaveni, ulozNastaveni } from "../api";
import { getCvd, getTheme, setCvd, setTheme } from "../theme";
import { getVelikost, setVelikost } from "../velikost";
import { DRUHY_AKTIVITY } from "../crm";
import {
  KLIC_NASTAVENI as KLIC_BARVY,
  barvaTextuNa,
  slucBarvy,
  vychoziBarvy,
} from "../barvyAktivit";
import "../styles/crm.css";

/**
 * Nastavení uživatele — jedno místo pro všechny osobní volby.
 *
 * Proč vlastní stránka, když vzhled je i v menu u jména: menu je zkratka pro
 * dvě tři přepnutí, ale barvy kalendáře se v rozbalovací nabídce ladit nedají.
 * Volby jsou tedy na obou místech a **ukládají se stejným způsobem** (klíč
 * v `uzivatelska_nastaveni`), takže se nemohou rozejít.
 *
 * Vše je osobní a přenáší se mezi počítači, protože to nese uživatelský
 * profil v DB, ne prohlížeč. Firemní nastavení (stavy pipeline, kategorie,
 * práva) patří do Admin nastavení — tady schválně není.
 */

const VELIKOSTI = [
  ["male", "Malý", "Základní velikost (14 px)"],
  ["stredni", "Střední", "O dva body větší"],
  ["velke", "Velký", "O čtyři body větší"],
];

export default function Nastaveni() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [tema, setTemaState] = useState(getTheme());
  const [cvd, setCvdState] = useState(getCvd());
  const [velikost, setVelikostState] = useState(getVelikost());
  const [barvy, setBarvy] = useState(() => vychoziBarvy());
  const [ulozeno, setUlozeno] = useState(null); // co se naposled uložilo
  const [chyba, setChyba] = useState(null);
  // Šablony (CRM-32) jsou firemní, ne osobní – proto jen pro `crm_nastaveni`.
  const [sablony, setSablony] = useState(false);
  // Automatizace (CRM-31) taky: pravidlo zakládá záznamy celé firmě.
  const [automatizace, setAutomatizace] = useState(false);

  useEffect(() => {
    nactiMe()
      .then((data) => {
        if (data.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        setMe(data);
        // Barvy se čtou z DB, ne z prohlížeče – proto až po přihlášení.
        nactiNastaveni()
          .then((n) => setBarvy(slucBarvy(n?.[KLIC_BARVY])))
          .catch(() => setBarvy(vychoziBarvy()));
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  /** Uloží volbu do profilu a krátce to potvrdí. */
  function uloz(klic, hodnota, popis) {
    setChyba(null);
    ulozNastaveni(klic, hodnota)
      .then(() => {
        setUlozeno(popis);
        window.setTimeout(() => setUlozeno(null), 1800);
      })
      .catch((e) => setChyba(e.message));
  }

  function zmenTema(t) {
    setTemaState(setTheme(t));
    uloz("tema", t, "Režim zobrazení");
  }

  function zmenCvd(c) {
    setCvdState(setCvd(c));
    uloz("cvd", c, "Režim pro barvoslepé");
  }

  function zmenVelikost(v) {
    setVelikostState(setVelikost(v));
    uloz("velikost", v, "Velikost textu");
  }

  function zmenBarvu(druh, barva) {
    const nove = { ...barvy, [druh]: barva };
    setBarvy(nove);
    uloz(KLIC_BARVY, nove, "Barvy v kalendáři");
  }

  function vratVychoziBarvy() {
    const nove = vychoziBarvy();
    setBarvy(nove);
    uloz(KLIC_BARVY, nove, "Barvy v kalendáři (výchozí)");
  }

  if (!me) return null;

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="gs-page-head">
        <div>
          <h1 className="gs-page-h1">Nastavení</h1>
          <p className="gs-page-lead">
            Tvoje osobní volby. Ukládají se k účtu, takže platí i na jiném počítači.
          </p>
        </div>
        <span className="gs-tb-spacer" />
        {ulozeno && (
          <span className="gs-pill good">
            <span className="gs-dot" />
            {ulozeno} uloženo
          </span>
        )}
      </div>

      {chyba && (
        <div className="fm-card" style={{ padding: 14, marginBottom: 16 }}>
          <span className="gs-pill warn">
            <span className="gs-dot" />
            Nastavení se nepodařilo uložit
          </span>
          <div style={{ marginTop: 8, fontSize: 13, color: "var(--muted)" }}>{chyba}</div>
        </div>
      )}

      <div style={{ display: "grid", gap: 16 }}>
        {/* ---- vzhled ---- */}
        <section className="fm-card">
          <div className="gs-karta-hlava">
            <span className="gs-karta-titulek">Vzhled</span>
          </div>
          <p className="gs-karta-popis">
            Totéž najdeš i v nabídce u svého jména vpravo nahoře — je to jedno nastavení.
          </p>

          <div className="crm-nastaveni-radek">
            <div>
              <div className="crm-nastaveni-nazev">Režim zobrazení</div>
              <div className="crm-tise">Světlý na den, tmavý na večer.</div>
            </div>
            <span className="gs-seg">
              <button onClick={() => zmenTema("light")} aria-pressed={tema === "light"}>
                <Ikona jmeno="slunce" velikost={14} /> Světlý
              </button>
              <button onClick={() => zmenTema("dark")} aria-pressed={tema === "dark"}>
                <Ikona jmeno="mesic" velikost={14} /> Tmavý
              </button>
            </span>
          </div>

          <div className="crm-nastaveni-radek">
            <div>
              <div className="crm-nastaveni-nazev">Velikost textu</div>
              <div className="crm-tise">Zvětší celou appku, ne jen písmo.</div>
            </div>
            <span className="gs-seg">
              {VELIKOSTI.map(([klic, popis, titulek]) => (
                <button
                  key={klic}
                  onClick={() => zmenVelikost(klic)}
                  aria-pressed={velikost === klic}
                  title={titulek}
                >
                  {popis}
                </button>
              ))}
            </span>
          </div>

          <div className="crm-nastaveni-radek">
            <div>
              <div className="crm-nastaveni-nazev">Režim pro barvoslepé</div>
              <div className="crm-tise">
                Vymění stavové barvy a grafy za paletu, která nestojí na rozlišení červené
                a zelené.
              </div>
            </div>
            <span className="gs-seg">
              <button onClick={() => zmenCvd("off")} aria-pressed={cvd === "off"}>
                Vypnuto
              </button>
              <button onClick={() => zmenCvd("on")} aria-pressed={cvd === "on"}>
                Zapnuto
              </button>
            </span>
          </div>
        </section>

        {/* ---- barvy v kalendáři ---- */}
        <section className="fm-card">
          <div className="gs-karta-hlava">
            <span className="gs-karta-titulek">Barvy v kalendáři</span>
            <span className="gs-tb-spacer" />
            <button className="fm-btn crm-btn-maly" onClick={vratVychoziBarvy}>
              Vrátit výchozí
            </button>
          </div>
          <p className="gs-karta-popis">
            Podle barvy poznáš v kalendáři na první pohled, co tě čeká. Nastavení je jen
            tvoje — kolegům se kalendář nepřebarví.
          </p>

          <div className="crm-barvy-mrizka">
            {DRUHY_AKTIVITY.map((d) => (
              <label key={d.klic} className="crm-barva-volba">
                <span
                  className="crm-barva-nahled"
                  style={{ background: barvy[d.klic], color: barvaTextuNa(barvy[d.klic]) }}
                >
                  <span aria-hidden="true">{d.ikona}</span> {d.nazev}
                </span>
                <input
                  type="color"
                  className="crm-barva-pole"
                  value={barvy[d.klic]}
                  onChange={(e) => zmenBarvu(d.klic, e.target.value)}
                  aria-label={`Barva pro ${d.nazev}`}
                />
              </label>
            ))}
          </div>
        </section>

        {/* ---- notifikace (CRM-36) – zatím jen pro interní testování ---- */}
        {me.novinky && <NotifikaceNastaveni />}

        {/* ---- šablony textů (CRM-32), jen pro správce nastavení ---- */}
        {me.novinky && me.prava?.includes("crm_nastaveni") && (
          <section className="fm-card">
            <div className="gs-karta-hlava">
              <span className="gs-karta-titulek">Šablony e-mailů a poznámek</span>
              <span className="gs-tb-spacer" />
              <button className="fm-btn crm-btn-maly" onClick={() => setSablony(true)}>
                Spravovat
              </button>
            </div>
            <p className="gs-karta-popis">
              Předpřipravené texty, které si každý vloží při psaní e-mailu nebo poznámky.
              Na rozdíl od ostatních voleb na téhle stránce jsou <b>společné pro celou
              firmu</b> — proto je spravuje jen správce nastavení.
            </p>
          </section>
        )}

        {/* ---- automatizace (CRM-31), jen pro správce nastavení ---- */}
        {me.novinky && me.prava?.includes("crm_nastaveni") && (
          <section className="fm-card">
            <div className="gs-karta-hlava">
              <span className="gs-karta-titulek">Automatizace</span>
              <span className="gs-tb-spacer" />
              <button className="fm-btn crm-btn-maly" onClick={() => setAutomatizace(true)}>
                Spravovat
              </button>
            </div>
            <p className="gs-karta-popis">
              Kroky, které se dneska dělají ručně pokaždé stejně: <b>případ vyhrán →
              objednávka</b>, <b>objednávka podepsaná → projekt ze šablony</b>, <b>nabídka
              odeslána → za týden zavolat</b>. Appka je udělá sama a napíše to do poznámek
              u záznamu. Pravidla se zakládají vypnutá a kdykoli se dají vypnout zpátky.
            </p>
          </section>
        )}

        {/* ---- podpis do e-mailu (CRM-33) ----
            Osobní věc každého, takže patří sem, ne do Admin nastavení.
            Jede pod přepínačem novinek jako zbytek e-mailového klienta. */}
        {me.novinky && <PodpisNastaveni />}

        {/* ---- účet ---- */}
        <section className="fm-card">
          <div className="gs-karta-hlava">
            <span className="gs-karta-titulek">Účet</span>
          </div>
          <div className="crm-nastaveni-radek">
            <div>
              <div className="crm-nastaveni-nazev">{me.uzivatel?.jmeno}</div>
              <div className="crm-tise">
                {me.uzivatel?.email}
                {me.uzivatel?.je_admin
                  ? " · Supersprávce (všechna práva)"
                  : me.uzivatel?.skupina
                    ? ` · skupina ${me.uzivatel.skupina}`
                    : " · bez skupiny"}
              </div>
            </div>
            <button className="fm-btn" onClick={() => navigate("/zmena-hesla")}>
              <Ikona jmeno="klic" velikost={15} />
              Změnit heslo
            </button>
          </div>
        </section>
      </div>

      {sablony && <SablonyTextuNastaveni onZavri={() => setSablony(false)} />}
      {automatizace && <AutomatizaceNastaveni onZavri={() => setAutomatizace(false)} />}
    </Layout>
  );
}
