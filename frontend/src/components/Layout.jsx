import { logout } from "../api";
import ThemeToggle from "./ThemeToggle";

export default function Layout({ uzivatel, children }) {
  return (
    <div style={{ padding: "16px" }}>
      <header
        className="fm-card"
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "10px 16px",
          marginBottom: "16px",
        }}
      >
        <span
          style={{
            width: 10,
            height: 10,
            borderRadius: "50%",
            background: "var(--fm-brand)",
            display: "inline-block",
          }}
        />
        <strong style={{ fontSize: 15 }}>Greensie</strong>
        <div style={{ flex: 1 }} />
        <ThemeToggle />
        {uzivatel && (
          <>
            <span style={{ color: "var(--fm-muted)", fontSize: 13 }}>
              {uzivatel.jmeno}
            </span>
            <button
              className="fm-btn"
              onClick={() => {
                logout();
                window.location.href = "/";
              }}
            >
              Odhlásit
            </button>
          </>
        )}
      </header>
      {children}
    </div>
  );
}
