import { useState } from "react";
import { getTheme, toggleTheme } from "../theme";
import { getToken, ulozNastaveni } from "../api";

export default function ThemeToggle() {
  const [theme, setThemeState] = useState(getTheme());
  const tmavy = theme === "dark";

  function prepnout() {
    const novy = toggleTheme();
    setThemeState(novy);
    // uložit do DB jen když jsme přihlášení (na Loginu ještě token není)
    if (getToken()) ulozNastaveni("tema", novy).catch(() => {});
  }

  return (
    <button
      className="fm-btn"
      onClick={prepnout}
      title="Přepnout světlý / tmavý režim"
    >
      {tmavy ? "☀ Světlý režim" : "🌙 Tmavý režim"}
    </button>
  );
}
