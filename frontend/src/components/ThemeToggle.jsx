import { useState } from "react";
import { getTheme, toggleTheme } from "../theme";

export default function ThemeToggle() {
  const [theme, setTheme] = useState(getTheme());
  const tmavy = theme === "dark";
  return (
    <button
      className="fm-btn"
      onClick={() => setTheme(toggleTheme())}
      title="Přepnout světlý / tmavý režim"
    >
      {tmavy ? "☀ Světlý režim" : "🌙 Tmavý režim"}
    </button>
  );
}
