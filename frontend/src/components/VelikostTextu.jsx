import { useState } from "react";
import { getVelikost, setVelikost } from "../velikost";
import { getToken, ulozNastaveni } from "../api";

export default function VelikostTextu() {
  const [v, setV] = useState(getVelikost());

  function zmen(nova) {
    setV(setVelikost(nova));
    if (getToken()) ulozNastaveni("velikost", nova).catch(() => {});
  }

  return (
    <label className="fm-btn" style={{ gap: 6, cursor: "pointer" }} title="Velikost textu">
      Text:
      <select
        value={v}
        onChange={(e) => zmen(e.target.value)}
        style={{ border: "none", background: "transparent", font: "inherit", color: "inherit", cursor: "pointer" }}
      >
        <option value="male">Malé</option>
        <option value="stredni">Střední</option>
        <option value="velke">Velké</option>
      </select>
    </label>
  );
}
