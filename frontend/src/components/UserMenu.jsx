import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getToken, logout, ulozNastaveni } from "../api";
import { getCvd, getTheme, setCvd, setTheme } from "../theme";
import { getVelikost, setVelikost } from "../velikost";
import Ikona from "./Ikona";

// Iniciály pro kolečko u jména („Daniel Lupínek" → „DL").
function iniciály(jmeno) {
  return (jmeno || "?")
    .trim()
    .split(/\s+/)
    .map((s) => s[0] || "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// Co se ukáže pod jménem v liště: supersprávce, jinak jeho skupina.
function popisRole(uzivatel) {
  if (uzivatel?.je_admin) return "Supersprávce";
  return uzivatel?.skupina || "Bez skupiny";
}

const VELIKOSTI = [
  ["male", "A−", "Malý text", 11],
  ["stredni", "A", "Střední text", 13],
  ["velke", "A+", "Velký text", 15],
];

export default function UserMenu({ uzivatel, prava }) {
  const [otevreno, setOtevreno] = useState(false);
  const [tema, setTemaState] = useState(getTheme());
  const [cvd, setCvdState] = useState(getCvd());
  const [velikost, setVelikostState] = useState(getVelikost());
  const wrap = useRef(null);
  const navigate = useNavigate();

  // Zavřít kliknutím mimo nebo Escapem.
  useEffect(() => {
    if (!otevreno) return;

    function klik(e) {
      if (wrap.current && !wrap.current.contains(e.target)) setOtevreno(false);
    }
    function klavesa(e) {
      if (e.key === "Escape") setOtevreno(false);
    }

    document.addEventListener("mousedown", klik);
    document.addEventListener("keydown", klavesa);
    return () => {
      document.removeEventListener("mousedown", klik);
      document.removeEventListener("keydown", klavesa);
    };
  }, [otevreno]);

  // Volby vzhledu se ukládají i do DB, ať se přenesou mezi zařízeními.
  function uloz(klic, hodnota) {
    if (getToken()) ulozNastaveni(klic, hodnota).catch(() => {});
  }

  function zmenTema(t) {
    setTemaState(setTheme(t));
    uloz("tema", t);
  }

  function zmenCvd(c) {
    setCvdState(setCvd(c));
    uloz("cvd", c);
  }

  function zmenVelikost(v) {
    setVelikostState(setVelikost(v));
    uloz("velikost", v);
  }

  const ini = iniciály(uzivatel?.jmeno);
  const muzeAdmin = (prava || []).includes("admin");

  return (
    <div className="gs-who-wrap" ref={wrap}>
      <button
        className="gs-who"
        onClick={() => setOtevreno((o) => !o)}
        aria-expanded={otevreno}
        aria-haspopup="true"
        title="Účet a nastavení vzhledu"
      >
        <span className="gs-avatar">{ini}</span>
        <span className="gs-who-meta">
          <span className="gs-who-name">{uzivatel?.jmeno}</span>
          <span className="gs-who-role">{popisRole(uzivatel)}</span>
        </span>
        <Ikona jmeno="chevron" velikost={14} />
      </button>

      {otevreno && (
        <div className="gs-menu" role="menu">
          <div className="gs-menu-head">
            <span className="gs-avatar">{ini}</span>
            <span>
              <span className="gs-menu-head-name">{uzivatel?.jmeno}</span>
              <span className="gs-menu-head-mail">{uzivatel?.email}</span>
            </span>
          </div>
          <div className="gs-menu-chip-wrap">
            <span className="gs-chip-role">
              {uzivatel?.je_admin ? "Supersprávce · všechna práva" : popisRole(uzivatel)}
            </span>
          </div>

          <div className="gs-menu-sep" />
          <div className="gs-menu-label">Vzhled</div>

          <div className="gs-menu-row">
            <span className="gs-menu-lbl">
              <Ikona jmeno="mesic" velikost={16} />
              Režim
            </span>
            <span className="gs-seg">
              <button
                onClick={() => zmenTema("light")}
                aria-pressed={tema === "light"}
                title="Světlý režim"
              >
                <Ikona jmeno="slunce" velikost={14} />
              </button>
              <button
                onClick={() => zmenTema("dark")}
                aria-pressed={tema === "dark"}
                title="Tmavý režim"
              >
                <Ikona jmeno="mesic" velikost={14} />
              </button>
            </span>
          </div>

          <div className="gs-menu-row">
            <span className="gs-menu-lbl">
              <Ikona jmeno="oko" velikost={16} />
              Barvosleposti
            </span>
            <span className="gs-seg">
              <button
                onClick={() => zmenCvd("off")}
                aria-pressed={cvd === "off"}
                title="Běžná paleta"
              >
                Vyp
              </button>
              <button
                onClick={() => zmenCvd("on")}
                aria-pressed={cvd === "on"}
                title="Kompenzace červeno-zelené vady zraku"
              >
                Zap
              </button>
            </span>
          </div>

          <div className="gs-menu-row">
            <span className="gs-menu-lbl">
              <Ikona jmeno="pismo" velikost={16} />
              Velikost textu
            </span>
            <span className="gs-seg">
              {VELIKOSTI.map(([klic, popis, titulek, px]) => (
                <button
                  key={klic}
                  onClick={() => zmenVelikost(klic)}
                  aria-pressed={velikost === klic}
                  title={titulek}
                  style={{ fontSize: px }}
                >
                  {popis}
                </button>
              ))}
            </span>
          </div>

          <div className="gs-menu-sep" />

          <button
            className="gs-menu-item"
            role="menuitem"
            onClick={() => {
              setOtevreno(false);
              navigate("/zmena-hesla");
            }}
          >
            <Ikona jmeno="klic" velikost={16} />
            Změnit heslo
          </button>

          {muzeAdmin && (
            <button
              className="gs-menu-item"
              role="menuitem"
              onClick={() => {
                setOtevreno(false);
                navigate("/admin");
              }}
            >
              <Ikona jmeno="admin" velikost={16} />
              Admin nastavení
            </button>
          )}

          <button
            className="gs-menu-item"
            role="menuitem"
            onClick={() => {
              setOtevreno(false);
              navigate("/manual");
            }}
          >
            <Ikona jmeno="manual" velikost={16} />
            Manuál
          </button>

          <div className="gs-menu-sep" />

          <button
            className="gs-menu-item danger"
            role="menuitem"
            onClick={() => {
              logout();
              window.location.href = "/";
            }}
          >
            <Ikona jmeno="odhlasit" velikost={16} />
            Odhlásit se
          </button>
        </div>
      )}
    </div>
  );
}
