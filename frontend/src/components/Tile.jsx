import Ikona from "./Ikona";

export default function Tile({ nazev, popis, ikona, onClick, zamceno = false }) {
  return (
    <button
      className={`gs-tile${zamceno ? " locked" : ""}`}
      onClick={onClick}
      title={zamceno ? "Zatím nedostupné – nemáš oprávnění tuto sekci otevřít" : undefined}
    >
      <div className="gs-tile-top">
        <span className="gs-tile-icon">
          <Ikona jmeno={ikona} velikost={21} />
        </span>
        {zamceno ? (
          <span className="gs-lockchip" aria-label="Zamčeno">
            <Ikona jmeno="zamek" velikost={12} />
            zamčeno
          </span>
        ) : (
          <span className="gs-tile-arrow">
            <Ikona jmeno="sipka" velikost={18} />
          </span>
        )}
      </div>
      <div>
        <div className="gs-tile-title">{nazev}</div>
        {popis && <div className="gs-tile-sub">{popis}</div>}
      </div>
    </button>
  );
}
