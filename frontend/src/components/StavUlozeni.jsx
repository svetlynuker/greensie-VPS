/**
 * Drobná hláška „ukládám / uloženo / neuloženo“ k automatickému ukládání.
 *
 * Proč to vůbec je vidět: bez tlačítka „Uložit“ nemá člověk jinak jak poznat,
 * že jeho text došel na server. A hlavně: když uložení spadne, musí to vidět
 * hned a mít jedno kliknutí na opakování — jinak zavře okno a text je pryč.
 *
 * @param {object} p
 * @param {"necinny"|"uklada"|"ulozeno"|"chyba"} p.stav
 * @param {string|null} [p.chyba]
 * @param {Date|null} [p.kdy] čas posledního úspěšného uložení
 * @param {Function} [p.onZkusitZnovu] když přijde, ukáže se tlačítko na opakování
 */
const zaklad = { fontSize: 12, display: "inline-flex", alignItems: "center", gap: 6 };

function cas(kdy) {
  const d = kdy instanceof Date ? kdy : kdy ? new Date(kdy) : null;
  if (!d || Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
}

export default function StavUlozeni({ stav, chyba, kdy, onZkusitZnovu }) {
  if (stav === "uklada") {
    return <span style={{ ...zaklad, color: "var(--fm-muted)" }}>Ukládám…</span>;
  }

  if (stav === "ulozeno") {
    const kdyText = cas(kdy);
    return (
      <span style={{ ...zaklad, color: "var(--fm-muted)" }}>
        {kdyText ? `Uloženo v ${kdyText}` : "Uloženo"}
      </span>
    );
  }

  if (stav === "chyba") {
    return (
      <span style={{ ...zaklad, color: "var(--st-crit)" }}>
        <span>Neuloženo: {chyba || "neznámá chyba"}</span>
        {onZkusitZnovu && (
          <button
            type="button"
            onClick={onZkusitZnovu}
            style={{
              fontSize: 12,
              fontFamily: "inherit",
              padding: "1px 6px",
              border: "1px solid var(--st-crit)",
              borderRadius: 6,
              background: "transparent",
              color: "var(--st-crit)",
              cursor: "pointer",
            }}
          >
            Zkusit znovu
          </button>
        )}
      </span>
    );
  }

  // „necinny“ (a cokoliv neznámého) se neukazuje — prázdný řádek by jen skákal.
  return null;
}
