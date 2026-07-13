import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [heslo, setHeslo] = useState("");
  const [chyba, setChyba] = useState(null);
  const navigate = useNavigate();

  async function odeslat(e) {
    e.preventDefault();
    setChyba(null);
    try {
      await login(email, heslo);
      navigate("/rozcestnik");
    } catch (err) {
      setChyba(err.message);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <form
        onSubmit={odeslat}
        className="fm-card"
        style={{ padding: 32, width: 320, display: "flex", flexDirection: "column", gap: 14 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: "var(--fm-brand)",
              display: "inline-block",
            }}
          />
          <strong style={{ fontSize: 17 }}>Greensie</strong>
        </div>

        <label style={{ fontSize: 13, fontWeight: 600 }}>
          E-mail
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={{
              display: "block",
              width: "100%",
              marginTop: 4,
              padding: "8px 10px",
              border: "1px solid var(--fm-line)",
              borderRadius: 8,
              fontSize: 14,
            }}
          />
        </label>

        <label style={{ fontSize: 13, fontWeight: 600 }}>
          Heslo
          <input
            type="password"
            value={heslo}
            onChange={(e) => setHeslo(e.target.value)}
            required
            style={{
              display: "block",
              width: "100%",
              marginTop: 4,
              padding: "8px 10px",
              border: "1px solid var(--fm-line)",
              borderRadius: 8,
              fontSize: 14,
            }}
          />
        </label>

        {chyba && <div style={{ color: "#c92a2a", fontSize: 13 }}>{chyba}</div>}

        <button type="submit" className="fm-btn fm-primary" style={{ marginTop: 6 }}>
          Přihlásit se
        </button>
      </form>
    </div>
  );
}
