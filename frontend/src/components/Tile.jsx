export default function Tile({ nazev, onClick }) {
  return (
    <button
      className="fm-card"
      onClick={onClick}
      style={{
        minWidth: "var(--fm-tile-min-width)",
        borderRadius: "var(--fm-tile-radius)",
        padding: "28px 20px",
        fontSize: 16,
        fontWeight: 700,
        color: "var(--fm-text)",
        cursor: "pointer",
        textAlign: "left",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--fm-brand)")}
      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--fm-line)")}
    >
      {nazev}
    </button>
  );
}
