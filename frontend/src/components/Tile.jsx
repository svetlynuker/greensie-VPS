export default function Tile({ nazev, onClick, zamceno = false }) {
  return (
    <button
      className="fm-card"
      onClick={onClick}
      title={zamceno ? "Zatím nedostupné – nemáš oprávnění tuto sekci otevřít" : undefined}
      style={{
        minWidth: "var(--fm-tile-min-width)",
        borderRadius: "var(--fm-tile-radius)",
        padding: "28px 20px",
        fontSize: 16,
        fontWeight: 700,
        color: zamceno ? "var(--fm-muted)" : "var(--fm-text)",
        cursor: "pointer",
        textAlign: "left",
        opacity: zamceno ? 0.6 : 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 10,
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--fm-brand)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--fm-line)")}
    >
      <span>{nazev}</span>
      {zamceno && (
        <span title="Zamčeno" aria-label="Zamčeno" style={{ fontSize: 15 }}>
          🔒
        </span>
      )}
    </button>
  );
}
