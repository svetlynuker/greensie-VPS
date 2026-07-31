import { useCallback, useEffect, useRef, useState } from "react";
import { emailAdresar } from "../api";

/**
 * Políčko adres s našeptáváním z adresáře CRM.
 *
 * Adresy jsou „žetony" (chip), ne text oddělený čárkami. Důvod: v textovém poli
 * se nedá poznat rozepsaná adresa od hotové a smazat jednu z pěti znamená
 * trefovat se kurzorem doprostřed řetězce. Žeton se smaže jedním klikem.
 *
 * Zdroj napovídání je **adresář CRM** — kontaktní osoby zákazníků, obecné
 * adresy firem a kolegové z appky. Nikde se neduplikuje: je to pohled na data,
 * která už v CRM jsou, takže opravená adresa na kartě firmy platí i tady.
 *
 * Napovídá se od dvou znaků a s prodlevou (`PRODLEVA_MS`) — bez ní by každé
 * písmeno znamenalo dotaz na server.
 */

const PRODLEVA_MS = 220;
const MIN_ZNAKU = 2;

const ZNAKY_DRUHU = { kontakt: "👤", zakaznik: "🏢", kolega: "★" };

export default function AdresarNaseptavac({
  hodnota = [],
  onZmena,
  popisek,
  id,
  placeholder = "Začni psát jméno nebo firmu…",
}) {
  const [text, setText] = useState("");
  const [navrhy, setNavrhy] = useState([]);
  const [oteveno, setOteveno] = useState(false);
  const [zvyrazneny, setZvyrazneny] = useState(0);
  const obal = useRef(null);
  const casovac = useRef(null);
  // Aby pomalejší starší odpověď nepřepsala novější (uživatel píše dál).
  const posledniDotaz = useRef("");

  const pridej = useCallback(
    (adresa) => {
      const cista = String(adresa || "").trim().toLowerCase();
      if (!cista.includes("@")) return;
      if (!hodnota.includes(cista)) onZmena([...hodnota, cista]);
      setText("");
      setNavrhy([]);
      setOteveno(false);
    },
    [hodnota, onZmena],
  );

  function odeber(adresa) {
    onZmena(hodnota.filter((a) => a !== adresa));
  }

  useEffect(() => {
    const dotaz = text.trim();
    if (casovac.current) clearTimeout(casovac.current);
    if (dotaz.length < MIN_ZNAKU) {
      setNavrhy([]);
      setOteveno(false);
      return undefined;
    }
    casovac.current = setTimeout(() => {
      posledniDotaz.current = dotaz;
      emailAdresar(dotaz)
        .then((d) => {
          if (posledniDotaz.current !== dotaz) return;
          setNavrhy(d || []);
          setZvyrazneny(0);
          setOteveno((d || []).length > 0);
        })
        // Nefunkční našeptávač nesmí zablokovat psaní – adresa se dá napsat ručně.
        .catch(() => setNavrhy([]));
    }, PRODLEVA_MS);
    return () => {
      if (casovac.current) clearTimeout(casovac.current);
    };
  }, [text]);

  useEffect(() => {
    function mimo(e) {
      if (obal.current && !obal.current.contains(e.target)) setOteveno(false);
    }
    document.addEventListener("mousedown", mimo);
    return () => document.removeEventListener("mousedown", mimo);
  }, []);

  function klavesa(e) {
    if (oteveno && navrhy.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setZvyrazneny((i) => (i + 1) % navrhy.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setZvyrazneny((i) => (i - 1 + navrhy.length) % navrhy.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        pridej(navrhy[zvyrazneny]?.adresa);
        return;
      }
      if (e.key === "Escape") {
        setOteveno(false);
        return;
      }
    }
    // Čárka, středník i Enter potvrzují ručně napsanou adresu — lidé jsou
    // zvyklí na všechny tři a hádat, kterou zrovna použijí, nemá smysl.
    if (e.key === "Enter" || e.key === "," || e.key === ";") {
      if (text.trim()) {
        e.preventDefault();
        pridej(text);
      }
      return;
    }
    // Backspace na prázdném poli maže poslední žeton (chování všech klientů).
    if (e.key === "Backspace" && !text && hodnota.length > 0) {
      odeber(hodnota[hodnota.length - 1]);
    }
  }

  return (
    <div className="em-pole" ref={obal}>
      {popisek && <label htmlFor={id}>{popisek}</label>}
      <div className="ns-obal">
        {hodnota.map((a) => (
          <span key={a} className="ns-zeton">
            {a}
            <button
              type="button"
              className="ns-zeton-x"
              onClick={() => odeber(a)}
              aria-label={`Odebrat ${a}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          className="ns-vstup"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={klavesa}
          // Rozepsaná adresa se při opuštění pole nesmí ztratit – to je
          // nejčastější způsob, jak lidé o příjemce přijdou.
          onBlur={() => {
            if (text.trim().includes("@")) pridej(text);
          }}
          placeholder={hodnota.length === 0 ? placeholder : ""}
          autoComplete="off"
          role="combobox"
          aria-expanded={oteveno}
          aria-autocomplete="list"
        />
      </div>

      {oteveno && navrhy.length > 0 && (
        <div className="ns-navrhy" role="listbox">
          {navrhy.map((n, i) => (
            <button
              type="button"
              key={n.adresa}
              className={`ns-navrh ${i === zvyrazneny ? "ns-navrh-aktivni" : ""}`}
              role="option"
              aria-selected={i === zvyrazneny}
              onMouseEnter={() => setZvyrazneny(i)}
              onClick={() => pridej(n.adresa)}
            >
              <span className="ns-navrh-znak" aria-hidden="true">
                {ZNAKY_DRUHU[n.druh] || "✉"}
              </span>
              <span className="ns-navrh-text">
                <span className="ns-navrh-jmeno">{n.jmeno || n.adresa}</span>
                <span className="ns-navrh-popis">
                  {n.adresa}
                  {n.popis ? ` · ${n.popis}` : ""}
                </span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
