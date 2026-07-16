import { useState } from "react";
import { getTheme, toggleTheme } from "../theme";
import { getToken, ulozNastaveni } from "../api";
import Ikona from "./Ikona";

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
      className="gs-icon-btn"
      onClick={prepnout}
      title={tmavy ? "Přepnout na světlý režim" : "Přepnout na tmavý režim"}
    >
      <Ikona jmeno={tmavy ? "slunce" : "mesic"} />
    </button>
  );
}
