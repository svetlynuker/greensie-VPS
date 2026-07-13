import { useState } from "react";

export default function ZobrazeniDropdown({
  faze,
  skryteFaze,
  skryteUkoly,
  onToggleFaze,
  onToggleUkol,
  onZobrazitVse,
}) {
  const [otevreno, setOtevreno] = useState(false);
  const pocetSkrytych = skryteFaze.size + skryteUkoly.size;

  return (
    <span className="fm-dd">
      <button className="fm-btn fm-ghost" onClick={() => setOtevreno((v) => !v)}>
        Zobrazení{pocetSkrytych > 0 ? ` (${pocetSkrytych} skryto)` : ""} ▾
      </button>

      {otevreno && (
        <>
          <div className="fm-dd-backdrop" onClick={() => setOtevreno(false)} />
          <div className="fm-dd-panel">
            <div className="fm-dd-actions">
              <button className="fm-btn fm-ghost" onClick={onZobrazitVse}>
                Zobrazit vše
              </button>
              <button className="fm-btn fm-ghost" onClick={() => setOtevreno(false)}>
                Hotovo
              </button>
            </div>

            {faze.map((f) => (
              <div key={f.todo} className="fm-dd-phase">
                <label className="fm-dd-row fm-dd-phase-row">
                  <input
                    type="checkbox"
                    checked={!skryteFaze.has(f.todo)}
                    onChange={() => onToggleFaze(f.todo)}
                  />
                  <span>{f.todo || "—"}</span>
                </label>
                {f.ukoly.map((u) => (
                  <label key={u.sloupec_id} className="fm-dd-row fm-dd-task">
                    <input
                      type="checkbox"
                      checked={!skryteUkoly.has(u.sloupec_id)}
                      disabled={skryteFaze.has(f.todo)}
                      onChange={() => onToggleUkol(u.sloupec_id)}
                    />
                    <span>{u.nazev}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        </>
      )}
    </span>
  );
}
