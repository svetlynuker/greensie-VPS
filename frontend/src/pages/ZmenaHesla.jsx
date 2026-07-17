import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { nactiMe, zmenHeslo, logout } from "../api";
import Ikona from "../components/Ikona";

const inputStyl = {
  display: "block",
  width: "100%",
  marginTop: 4,
  padding: "8px 10px",
  border: "1px solid var(--fm-line)",
  borderRadius: 8,
  fontSize: 14,
};

export default function ZmenaHesla() {
  const [jmeno, setJmeno] = useState("");
  const [nove, setNove] = useState("");
  const [znovu, setZnovu] = useState("");
  const [chyba, setChyba] = useState(null);
  const [uklada, setUklada] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    nactiMe()
      .then((me) => setJmeno(me.uzivatel.jmeno))
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  async function odeslat(e) {
    e.preventDefault();
    setChyba(null);
    if (nove.length < 6) {
      setChyba("Heslo musí mít alespoň 6 znaků.");
      return;
    }
    if (nove !== znovu) {
      setChyba("Hesla se neshodují.");
      return;
    }
    setUklada(true);
    try {
      await zmenHeslo(nove);
      navigate("/rozcestnik");
    } catch (err) {
      setChyba(err.message);
      setUklada(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <form
        onSubmit={odeslat}
        className="fm-card"
        style={{ padding: 32, width: 360, display: "flex", flexDirection: "column", gap: 14 }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="gs-brand-mark">
            <Ikona jmeno="logo" velikost={15} />
          </span>
          <strong style={{ fontSize: 17 }}>Nastav si nové heslo</strong>
        </div>
        <div style={{ fontSize: 13, color: "var(--fm-muted)" }}>
          {jmeno ? `${jmeno}, ` : ""}pro pokračování je potřeba změnit heslo z jednorázového na vlastní.
        </div>

        <label style={{ fontSize: 13, fontWeight: 600 }}>
          Nové heslo
          <input type="password" value={nove} onChange={(e) => setNove(e.target.value)} required style={inputStyl} />
        </label>
        <label style={{ fontSize: 13, fontWeight: 600 }}>
          Nové heslo znovu
          <input type="password" value={znovu} onChange={(e) => setZnovu(e.target.value)} required style={inputStyl} />
        </label>

        {chyba && <div style={{ color: "var(--st-crit)", fontSize: 13 }}>{chyba}</div>}

        <button type="submit" className="fm-btn fm-primary" style={{ marginTop: 6 }} disabled={uklada}>
          {uklada ? "Ukládám…" : "Uložit nové heslo"}
        </button>
        <button
          type="button"
          className="fm-btn"
          onClick={() => {
            logout();
            navigate("/");
          }}
        >
          Odhlásit
        </button>
      </form>
    </div>
  );
}
