import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import { crmMujDen, logout, nactiMe } from "../api";
import { DRUHY_AKTIVITY, fmtDatum, fmtKcKratce } from "../crm";
import "../styles/crm.css";

/**
 * Můj den (CRM-16) — jedna obrazovka s tím, co člověka tlačí.
 *
 * Proč vedle Rozcestníku: Rozcestník je souhrn celé appky (matice, financí,
 * nabídek). Tohle je jen obchodní agenda jednoho člověka a přidává dvě věci,
 * které jinak nikdo nehlídá — případy, kde se dlouho nic nestalo, a nabídky
 * odeslané bez reakce. Právě tam se zakázky tichem ztrácejí.
 *
 * Sekce jsou v pořadí naléhavosti a prázdná sekce je taky odpověď („nic není
 * po termínu"), proto se neschovává.
 */

function Sekce({ titulek, popis, pocet, stav, prazdne, deti }) {
  return (
    <section className="fm-card" style={{ padding: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <span className="gs-karta-titulek">{titulek}</span>
        {pocet > 0 && (
          <span className={`gs-pill ${stav}`}>
            <span className="gs-dot" />
            {pocet}
          </span>
        )}
      </div>
      {popis && <p className="gs-karta-popis">{popis}</p>}
      {pocet > 0 ? deti : <p className="crm-tise" style={{ margin: 0 }}>{prazdne}</p>}
    </section>
  );
}

/** Řádek úkolu: druh, název, u čeho visí, jak je po termínu. */
function Ukol({ u, onOtevri }) {
  const d = DRUHY_AKTIVITY.find((x) => x.klic === u.druh);
  return (
    <li className="md-radek" onClick={() => u.cesta && onOtevri(u.cesta)}>
      <span className="md-ikona">{d?.znak || "•"}</span>
      <span className="md-nazev">{u.nazev || u.text || "(bez popisu)"}</span>
      <span className="md-zaznam">{u.zaznam_nazev}</span>
      <span className={`md-termin ${u.dni > 0 ? "pozde" : ""}`}>
        {fmtDatum(u.termin)}
        {u.dni > 0 ? ` · ${u.dni} dní po termínu` : ""}
      </span>
    </li>
  );
}

export default function MujDen() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [d, setD] = useState(null);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    nactiMe()
      .then((m) => {
        if (m.musi_zmenit_heslo) return navigate("/zmena-hesla");
        if (!m.prava?.includes("zakaznici")) return navigate("/rozcestnik");
        setMe(m);
        crmMujDen().then(setD).catch((e) => setChyba(e.message));
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  if (!me) return null;
  const jmeno = (me.uzivatel?.jmeno || "").split(" ")[0];

  return (
    <Layout
      uzivatel={me.uzivatel}
      akce={
        <>
        <button className="fm-btn" onClick={() => navigate("/kalendar")}>
          <Ikona jmeno="kalendar" velikost={15} />
          Kalendář
        </button>
        </>
      }
    >
      {chyba && <div className="crm-chyba">Nepodařilo se načíst: {chyba}</div>}

      {d && (
        <div style={{ display: "grid", gap: 14 }}>
          <Sekce
            titulek="Po termínu"
            popis="Úkoly, kterým už termín uplynul. Nejstarší první."
            pocet={d.po_terminu.length}
            stav="crit"
            prazdne="Nic není po termínu."
            deti={
              <ul className="md-seznam">
                {d.po_terminu.map((u) => (
                  <Ukol key={u.id} u={u} onOtevri={navigate} />
                ))}
              </ul>
            }
          />

          <Sekce
            titulek="Dnes"
            popis="Co má být hotové dneska."
            pocet={d.dnes.length}
            stav="warn"
            prazdne="Na dnes nic naplánované není."
            deti={
              <ul className="md-seznam">
                {d.dnes.map((u) => (
                  <Ukol key={u.id} u={u} onOtevri={navigate} />
                ))}
              </ul>
            }
          />

          <Sekce
            titulek={`Případy, kde se ${d.prahy.pripad_dni} dní nic nestalo`}
            popis="Otevřené případy bez aktivity. Právě tady se zakázky tichem ztrácejí."
            pocet={d.zanedbane_pripady.length}
            stav="serious"
            prazdne="U všech otevřených případů se něco děje."
            deti={
              <ul className="md-seznam">
                {d.zanedbane_pripady.map((p) => (
                  <li
                    key={p.id}
                    className="md-radek"
                    onClick={() => navigate(`/pripady/detail/${p.id}`)}
                  >
                    <span className="md-ikona">📁</span>
                    <span className="md-nazev">
                      <b>{p.cislo}</b> {p.nazev}
                    </span>
                    <span className="md-zaznam">
                      {p.stav}
                      {p.hodnota_kc ? ` · ${fmtKcKratce(p.hodnota_kc)}` : ""}
                    </span>
                    <span className="md-termin pozde">
                      {p.dni == null ? "žádná aktivita" : `${p.dni} dní ticho`}
                    </span>
                  </li>
                ))}
              </ul>
            }
          />

          <Sekce
            titulek={`Nabídky bez reakce déle než ${d.prahy.nabidka_dni} dní`}
            popis="Odeslané zákazníkovi, ale nikdo neodpověděl. Zavolat je levnější než čekat."
            pocet={d.nabidky_bez_reakce.length}
            stav="serious"
            prazdne="Žádná odeslaná nabídka nečeká na odpověď."
            deti={
              <ul className="md-seznam">
                {d.nabidky_bez_reakce.map((n) => (
                  <li
                    key={n.id}
                    className="md-radek"
                    onClick={() => navigate(`/nabidkovac/nabidka/${n.id}`)}
                  >
                    <span className="md-ikona">📄</span>
                    <span className="md-nazev">
                      <b>{n.cislo}</b> {n.zakaznik}
                    </span>
                    <span className="md-zaznam">{n.pripad_cislo}</span>
                    <span className="md-termin pozde">{n.dni} dní bez reakce</span>
                  </li>
                ))}
              </ul>
            }
          />

          {d.nadchazejici.length > 0 && (
            <Sekce
              titulek="Co přijde"
              popis="Nejbližší úkoly, ať víš, co se chystá."
              pocet={d.nadchazejici.length}
              stav="good"
              prazdne=""
              deti={
                <ul className="md-seznam">
                  {d.nadchazejici.map((u) => (
                    <Ukol key={u.id} u={u} onOtevri={navigate} />
                  ))}
                </ul>
              }
            />
          )}
        </div>
      )}
    </Layout>
  );
}
