import { useState } from "react";
import { getCvd, toggleCvd } from "../theme";
import { getToken, ulozNastaveni } from "../api";
import Ikona from "./Ikona";

// Kompenzace červeno-zelené vady zraku: přepne stavové barvy a grafy na
// paletu čitelnou při deuteranopii/protanopii (modrá = v pořádku, závažnost
// odlišená jasem). Ukládá se k uživateli do DB, přenáší se mezi zařízeními.
export default function CvdToggle() {
  const [cvd, setCvdState] = useState(getCvd());
  const zapnuto = cvd === "on";

  function prepnout() {
    const novy = toggleCvd();
    setCvdState(novy);
    // uložit do DB jen když jsme přihlášení (na Loginu ještě token není)
    if (getToken()) ulozNastaveni("cvd", novy).catch(() => {});
  }

  return (
    <button
      className="gs-icon-btn"
      onClick={prepnout}
      aria-pressed={zapnuto}
      title={
        zapnuto
          ? "Kompenzace červeno-zelené vady: zapnuto"
          : "Kompenzace barev pro červeno-zelenou vadu zraku"
      }
    >
      <Ikona jmeno="oko" />
    </button>
  );
}
