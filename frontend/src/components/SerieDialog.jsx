/**
 * Volba rozsahu u aktivity, která patří do opakované série.
 *
 * Ptá se, jako se ptá Google Kalendář a Outlook — lidem to bude známé. Bez
 * dotazu by kterákoli varianta někoho překvapila: „jen tuhle" by nutilo
 * překlikat celou sérii při změně času porady, „celou sérii" by zase
 * jednorázovým přesunem rozhodilo všechny ostatní.
 *
 * Volby jsou schválně v tomhle pořadí a s výchozím „jen tuhle" jako první:
 * nejmenší dopad má být nejblíž ruce.
 */
export default function SerieDialog({ popisSerie, akce = "zmenit", onVyber, onZavri }) {
  const slovo = akce === "smazat" ? "Smazat" : "Změnit";
  return (
    <div className="sd-plast" onClick={onZavri}>
      <div className="sd" onClick={(e) => e.stopPropagation()} role="dialog">
        <h3>{akce === "smazat" ? "Smazat opakovanou aktivitu" : "Změnit opakovanou aktivitu"}</h3>
        <p className="crm-tise">
          Tahle aktivita se opakuje{popisSerie ? ` — ${popisSerie}` : ""}. Čeho se má
          {akce === "smazat" ? " smazání" : " změna"} dotknout?
        </p>
        <div className="sd-volby">
          <button className="fm-btn fm-primary" onClick={() => onVyber("jen_tuhle")}>
            {slovo} jen tuhle
          </button>
          <button className="fm-btn" onClick={() => onVyber("tuto_a_dalsi")}>
            {slovo} tuhle a všechny další
          </button>
          <button className="fm-btn" onClick={() => onVyber("celou_serii")}>
            {slovo} celou sérii
          </button>
        </div>
        <button className="fm-btn crm-btn-maly sd-zrusit" onClick={onZavri}>
          Zrušit
        </button>
      </div>
    </div>
  );
}
