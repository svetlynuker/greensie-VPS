export default function FreeloDialog({ bezi, onVyber, onClose }) {
  return (
    <div
      onClick={bezi ? undefined : onClose}
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
        style={{ padding: 20, width: "min(480px, 100%)", display: "flex", flexDirection: "column", gap: 14 }}
      >
        <h3 style={{ margin: 0, fontSize: 15 }}>Načíst z Freela</h3>
        <p style={{ margin: 0, fontSize: 13, color: "var(--fm-muted)", lineHeight: 1.5 }}>
          Zdrojem pravdy zůstává tato tabulka. Vyber, jak se mají data z Freela promítnout. Poznámky
          se nikdy nepřepisují a úkoly, které Freelo nemá, zůstanou zachované.
        </p>

        <button
          className="fm-btn fm-primary"
          disabled={bezi}
          onClick={() => onVyber("prepsat")}
          style={{ textAlign: "left", padding: "12px 14px", display: "block" }}
        >
          <strong>Přepsat vše z Freela</strong>
          <div style={{ fontSize: 12, fontWeight: 400, marginTop: 3 }}>
            Aktualizuje i ručně upravené úkoly (stav, termín, osoba). Poznámky zůstávají.
          </div>
        </button>

        <button
          className="fm-btn"
          disabled={bezi}
          onClick={() => onVyber("bez_prepsani")}
          style={{ textAlign: "left", padding: "12px 14px", display: "block" }}
        >
          <strong>Načíst bez přepsání</strong>
          <div style={{ fontSize: 12, fontWeight: 400, marginTop: 3 }}>
            Doplní jen nové úkoly z Freela. Existující (i ručně upravené) nechá být.
          </div>
        </button>

        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button className="fm-btn fm-ghost" onClick={onClose} disabled={bezi}>
            {bezi ? "Načítám z Freela…" : "Zrušit"}
          </button>
        </div>
      </div>
    </div>
  );
}
