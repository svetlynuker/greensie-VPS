import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Kanban from "../components/Kanban";
import SablonyNastaveni from "../components/SablonyNastaveni";
import StavyNastaveni from "../components/StavyNastaveni";
import {
  crmProjektStav,
  crmProjekty,
  crmProjektyKanban,
  crmStavy,
  crmVlastniPole,
  logout,
  nactiMe,
} from "../api";
import { fmtDatum } from "../crm";
import "../styles/crm.css";

/**
 * Sekce Projekty – realizace zakázek.
 *
 * Projekt nelze založit odsud: vzniká z objednávky nebo z obchodního případu
 * (zadání Dana), takže tady je jen přehled a posouvání stavů. Klik otevře
 * detail s kroky.
 */
export default function Projekty() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [zobrazeni, setZobrazeni] = useState("kanban");
  const [kanban, setKanban] = useState(null);
  const [radky, setRadky] = useState([]);
  const [sloupce, setSloupce] = useState([]);
  const [hledat, setHledat] = useState("");
  const [nastaveniStavu, setNastaveniStavu] = useState(false);
  const [sablony, setSablony] = useState(false);
  const [chyba, setChyba] = useState(null);

  const nacti = useCallback(async (dotaz = "") => {
    const [k, r, pole] = await Promise.all([
      crmProjektyKanban(),
      crmProjekty({ hledat: dotaz || undefined }),
      crmVlastniPole("pro").catch(() => []),
    ]);
    setKanban(k);
    setRadky(r);
    setSloupce(pole.filter((x) => x.v_seznamu));
  }, []);

  useEffect(() => {
    nactiMe()
      .then(async (m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("obchodni_pripady")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        await nacti();
        await crmStavy("pro").catch(() => []);
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
  }, [navigate, nacti]);

  useEffect(() => {
    if (!me) return undefined;
    const t = setTimeout(() => {
      crmProjekty({ hledat: hledat || undefined })
        .then(setRadky)
        .catch((e) => setChyba(e.message));
    }, 300);
    return () => clearTimeout(t);
  }, [hledat, me]);

  async function presun(id, novyStav) {
    setChyba(null);
    try {
      await crmProjektStav(id, novyStav);
      await nacti(hledat);
    } catch (e) {
      setChyba(e.message);
    }
  }

  if (chyba && !kanban) {
    return (
      <Layout uzivatel={me?.uzivatel}>
        <div style={{ padding: 24, color: "var(--st-crit)" }}>Chyba: {chyba}</div>
      </Layout>
    );
  }
  if (!me || !kanban) return null;

  const celkem = kanban.sloupce.reduce((s, x) => s + x.pocet, 0);
  const muzeNastaveni = me.prava?.includes("crm_nastaveni");

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="crm-app siroky">
        <div className="crm-hlava">
          <div>
            <h1>Projekty</h1>
            <p className="crm-popis">
              Realizace zakázek. Projekt vzniká z objednávky (nebo z obchodního případu) —
              samostatně ho založit nelze, aby vždy bylo dohledatelné, z čeho realizace vyšla.
            </p>
          </div>
          <span className="crm-mezera" />
          <button className="fm-btn" onClick={() => setSablony(true)}>
            📋 Šablony kroků
          </button>
          {muzeNastaveni && (
            <button className="fm-btn" onClick={() => setNastaveniStavu(true)}>
              ⚙ Stavy projektů
            </button>
          )}
        </div>

        <div className="crm-toolbar">
          <div className="crm-prepinac">
            <button
              className={`crm-zalozka ${zobrazeni === "kanban" ? "aktivni" : ""}`}
              onClick={() => setZobrazeni("kanban")}
            >
              Kanban
            </button>
            <button
              className={`crm-zalozka ${zobrazeni === "tabulka" ? "aktivni" : ""}`}
              onClick={() => setZobrazeni("tabulka")}
            >
              Tabulka
            </button>
          </div>
          {zobrazeni === "tabulka" && (
            <input
              className="crm-pole crm-hledani"
              placeholder="Hledat podle čísla nebo názvu…"
              value={hledat}
              onChange={(e) => setHledat(e.target.value)}
            />
          )}
          <span className="crm-mezera" />
          <span className="crm-pocet">
            <b>{celkem}</b> projektů
          </span>
        </div>

        {chyba && <div className="crm-chyba">{chyba}</div>}

        {zobrazeni === "kanban" ? (
          <Kanban
            sloupce={kanban.sloupce}
            onPresun={presun}
            onOtevri={(p) => navigate(`/projekty/detail/${p.id}`)}
            dlazdice={(p) => (
              <>
                <div className="crm-dlazdice-hlava">
                  <span className="crm-dlazdice-cislo">{p.cislo}</span>
                  {p.kroku > 0 && (
                    <span className="crm-dlazdice-hodnota">
                      {p.hotovo}/{p.kroku}
                    </span>
                  )}
                </div>
                <div className="crm-dlazdice-zakaznik">{p.zakaznik_nazev || "—"}</div>
                {p.nazev && <div className="crm-dlazdice-nazev">{p.nazev}</div>}
                {/* Postup kroků na první pohled – to je u realizace to hlavní. */}
                {p.kroku > 0 && (
                  <div className="crm-pruh">
                    <span style={{ width: `${p.procent}%` }} />
                  </div>
                )}
                <div className="crm-dlazdice-pata">
                  {p.nejblizsi_termin ? `nejblíž ${fmtDatum(p.nejblizsi_termin)}` : "bez termínu"}
                  {p.po_terminu > 0 && (
                    <span className="crm-po-terminu"> · {p.po_terminu} po termínu</span>
                  )}
                </div>
              </>
            )}
          />
        ) : (
          <div className="crm-scroll">
            <table className="crm-tabulka">
              <thead>
                <tr>
                  <th>Číslo</th>
                  <th>Zákazník</th>
                  <th>Název</th>
                  <th>Případ</th>
                  <th>Objednávka</th>
                  <th>Stav</th>
                  <th>Kroky</th>
                  <th>Nejbližší termín</th>
                  {sloupce.map((sl) => (
                    <th key={sl.klic}>{sl.nazev}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {radky.map((p) => (
                  <tr key={p.id} onClick={() => navigate(`/projekty/detail/${p.id}`)}>
                    <td className="crm-silne">{p.cislo}</td>
                    <td>{p.zakaznik_nazev || "—"}</td>
                    <td>{p.nazev || "—"}</td>
                    <td>{p.pripad_cislo}</td>
                    <td>{p.objednavka_cislo || <span className="crm-tise">—</span>}</td>
                    <td>
                      <span className="crm-znacka">{p.stav_nazev}</span>
                    </td>
                    <td>
                      {p.kroku > 0 ? `${p.hotovo}/${p.kroku} (${p.procent} %)` : "—"}
                    </td>
                    <td>
                      {fmtDatum(p.nejblizsi_termin) || "—"}
                      {p.po_terminu > 0 && (
                        <span className="crm-po-terminu"> · {p.po_terminu} po termínu</span>
                      )}
                    </td>
                    {sloupce.map((sl) => (
                      <td key={sl.klic}>{(p.extra_text || {})[sl.klic] ?? "—"}</td>
                    ))}
                  </tr>
                ))}
                {radky.length === 0 && (
                  <tr>
                    <td colSpan={8 + sloupce.length} className="crm-prazdno">
                      {hledat
                        ? "Nic nenalezeno."
                        : "Zatím žádné projekty. Zakládají se z objednávky nebo z karty případu."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {nastaveniStavu && (
        <StavyNastaveni
          entita="pro"
          onZavri={() => setNastaveniStavu(false)}
          onZmena={() => nacti(hledat)}
        />
      )}

      {sablony && (
        <SablonyNastaveni
          muzeEditovat={muzeNastaveni}
          onZavri={() => setSablony(false)}
        />
      )}
    </Layout>
  );
}
