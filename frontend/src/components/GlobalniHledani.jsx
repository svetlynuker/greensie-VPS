import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { crmHledat, crmOblibene } from "../api";

/**
 * Globální hledání v horní liště (CRM-24).
 *
 * Jedno pole pro zákazníky, případy, nabídky, objednávky i projekty — dnes se
 * hledá v každé sekci zvlášť, takže „kde je ten klient z Berouna" znamená
 * proklikat pět obrazovek.
 *
 * Tři věci, které z hledání dělají použitelnou věc:
 *
 * 1. **Ctrl+K odkudkoli.** Kdo hledá často, nechce mířit myší do lišty.
 * 2. **Dotaz se posílá se zpožděním** (250 ms po dopsání). Bez toho by každé
 *    písmeno znamenalo dotaz na server a výsledky by přeskakovaly, jak by se
 *    odpovědi vracely v jiném pořadí, než odešly.
 * 3. **Klávesy ↑ ↓ a Enter.** Ruka zůstane na klávesnici až do otevření záznamu.
 *
 * Prohledávaná pole (zadání Dana): názvy a čísla záznamů, IČO, telefon, e-mail
 * a město. Text aktivit ne — výsledků by bylo mnoho a hledání by zpomalilo.
 */
export default function GlobalniHledani() {
  const [dotaz, setDotaz] = useState("");
  const [data, setData] = useState(null);
  const [otevreno, setOtevreno] = useState(false);
  const [aktivni, setAktivni] = useState(0);
  const [hleda, setHleda] = useState(false);
  // Oblíbené a naposledy otevřené (CRM-37). Ukazují se v prázdném poli —
  // je to místo, kam už dnes lidé chodí hledat záznam, takže návrat k tomu,
  // s čím zrovna pracují, patří sem, ne na další novou obrazovku.
  const [zkratky, setZkratky] = useState(null);
  const pole = useRef(null);
  const obal = useRef(null);
  const navigate = useNavigate();

  // Ctrl+K / Cmd+K odkudkoli; Escape zavře.
  useEffect(() => {
    function klavesa(e) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        pole.current?.focus();
        setOtevreno(true);
      }
      if (e.key === "Escape") setOtevreno(false);
    }
    window.addEventListener("keydown", klavesa);
    return () => window.removeEventListener("keydown", klavesa);
  }, []);

  // Zavření kliknutím mimo.
  useEffect(() => {
    if (!otevreno) return undefined;
    function klik(e) {
      if (obal.current && !obal.current.contains(e.target)) setOtevreno(false);
    }
    document.addEventListener("mousedown", klik);
    return () => document.removeEventListener("mousedown", klik);
  }, [otevreno]);

  // Zkratky se načtou při každém otevření prázdného pole — po návratu z karty
  // má být nahoře to, co člověk právě zavřel.
  useEffect(() => {
    if (!otevreno || dotaz.trim().length >= 2) return;
    crmOblibene()
      .then(setZkratky)
      .catch(() => setZkratky(null));
  }, [otevreno, dotaz]);

  // Zpožděný dotaz. `zruseno` brání tomu, aby pomalejší starší odpověď
  // přepsala novější — jinak výsledky poskakují.
  useEffect(() => {
    if (dotaz.trim().length < 2) {
      setData(null);
      return undefined;
    }
    let zruseno = false;
    setHleda(true);
    const t = setTimeout(() => {
      crmHledat(dotaz)
        .then((d) => {
          if (zruseno) return;
          setData(d);
          setAktivni(0);
        })
        .catch(() => !zruseno && setData(null))
        .finally(() => !zruseno && setHleda(false));
    }, 250);
    return () => {
      zruseno = true;
      clearTimeout(t);
    };
  }, [dotaz]);

  const plocho = (data?.sekce || []).flatMap((s) =>
    s.vysledky.map((v) => ({ ...v, sekce: s.nazev }))
  );

  function otevri(v) {
    setOtevreno(false);
    setDotaz("");
    setData(null);
    navigate(v.cesta);
  }

  return (
    <div className="gh" ref={obal}>
      <input
        ref={pole}
        className="gh-pole"
        value={dotaz}
        onChange={(e) => {
          setDotaz(e.target.value);
          setOtevreno(true);
        }}
        onFocus={() => setOtevreno(true)}
        onKeyDown={(e) => {
          if (!plocho.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setAktivni((i) => (i + 1) % plocho.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setAktivni((i) => (i - 1 + plocho.length) % plocho.length);
          } else if (e.key === "Enter") {
            e.preventDefault();
            otevri(plocho[aktivni]);
          }
        }}
        placeholder="Hledat… (Ctrl+K)"
        aria-label="Globální hledání"
      />

      {/* Prázdné pole: oblíbené a naposledy otevřené (CRM-37). */}
      {otevreno && dotaz.trim().length < 2 && (zkratky?.oblibene?.length || zkratky?.nedavne?.length) ? (
        <div className="gh-vysledky">
          {zkratky.oblibene.length > 0 && (
            <div>
              <div className="gh-sekce">★ Oblíbené</div>
              {zkratky.oblibene.map((z) => (
                <button
                  key={`o-${z.entita}-${z.zaznam_id}`}
                  className="gh-radek"
                  onClick={() => otevri(z)}
                >
                  <span className="gh-titulek">{z.nazev}</span>
                </button>
              ))}
            </div>
          )}
          {zkratky.nedavne.length > 0 && (
            <div>
              <div className="gh-sekce">Naposledy otevřené</div>
              {zkratky.nedavne.map((z) => (
                <button
                  key={`n-${z.entita}-${z.zaznam_id}`}
                  className="gh-radek"
                  onClick={() => otevri(z)}
                >
                  <span className="gh-titulek">{z.nazev}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ) : null}

      {otevreno && dotaz.trim().length >= 2 && (
        <div className="gh-vysledky">
          {hleda && !data && <div className="gh-hlaska">Hledám…</div>}
          {data && plocho.length === 0 && (
            <div className="gh-hlaska">
              Nic jsem nenašel. Zkus část názvu, číslo případu, IČO nebo telefon.
            </div>
          )}
          {(data?.sekce || []).map((s) => (
            <div key={s.klic}>
              <div className="gh-sekce">
                {s.nazev}
                {s.vic && <span className="crm-tise"> · víc jich je</span>}
              </div>
              {s.vysledky.map((v) => {
                const i = plocho.findIndex((x) => x.cesta === v.cesta && x.id === v.id);
                return (
                  <button
                    key={`${s.klic}-${v.id}`}
                    className={`gh-radek ${i === aktivni ? "aktivni" : ""}`}
                    onClick={() => otevri(v)}
                    onMouseEnter={() => setAktivni(i)}
                  >
                    <span className="gh-titulek">{v.titulek}</span>
                    {v.popis && <span className="gh-popis">{v.popis}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
