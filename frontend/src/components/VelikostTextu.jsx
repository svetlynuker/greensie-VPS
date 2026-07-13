import { useState } from "react";
import { getVelikost, setVelikost } from "../velikost";

export default function VelikostTextu() {
  const [v, setV] = useState(getVelikost());
  return (
    <label className="fm-btn" style={{ gap: 6, cursor: "pointer" }} title="Velikost textu">
      Text:
      <select
        value={v}
        onChange={(e) => setV(setVelikost(e.target.value))}
        style={{ border: "none", background: "transparent", font: "inherit", color: "inherit", cursor: "pointer" }}
      >
        <option value="male">Malé</option>
        <option value="stredni">Střední</option>
        <option value="velke">Velké</option>
      </select>
    </label>
  );
}
