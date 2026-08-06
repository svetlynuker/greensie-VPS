import Pritomni from "./Pritomni";

/**
 * Upozornění nad výpočtovými panely nabídkovače: „na téhle nabídce je ještě někdo".
 *
 * Vstupy výpočtu se — na rozdíl od zbytku appky — neukládají za pochodu. Jeden
 * přepočet trvá desítky sekund a nabídka se z těch vstupů skládá do verzí,
 * takže ukládání po každém stisku klávesy by plodilo mezivýpočty z nedopsaných
 * čísel. Rozpracované zadání proto zůstává v prohlížeči (localStorage) a na
 * server jde teprve tlačítkem „Spočítat".
 *
 * Cena té výjimky je ale tichá past: dva lidé nad jednou nabídkou o sobě
 * nevědí a kdo klikne „Spočítat" druhý, přepíše zadání prvního. Tohle je
 * levná pojistka — neřeší to technicky, ale dá lidem šanci se dohodnout
 * dřív, než si práci přepíšou.
 *
 * Když je na nabídce člověk sám, komponenta nevykreslí nic.
 *
 * @param {object} p
 * @param {Array} p.pritomni  seznam z `usePritomnost` (včetně sebe, `ja: true`)
 * @param {"hlavicka"|"tlacitko"} [p.podoba]  kolečka do hlavičky panelu,
 *   nebo věta k tlačítku „Spočítat"
 * @param {string} [p.akce]  jak se v téhle sekci jmenuje přepočet
 */
export default function PritomniVypocet({ pritomni, podoba = "tlacitko", akce = "Přepočet" }) {
  const ostatni = (Array.isArray(pritomni) ? pritomni : []).filter((c) => c && !c.ja);
  if (ostatni.length === 0) return null;

  if (podoba === "hlavicka") {
    return <Pritomni pritomni={pritomni} />;
  }

  const jmena = ostatni.map((c) => c.jmeno || "někdo další").join(", ");
  return (
    <div
      className="nb-badge pozor"
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 10,
        lineHeight: 1.35,
        textAlign: "left",
        whiteSpace: "normal",
      }}
    >
      <Pritomni pritomni={pritomni} />
      <span>
        Nabídku má otevřenou taky <strong>{jmena}</strong>. {akce} uloží tvoje vstupy jako novou
        verzi a přepíše zadání, na kterém možná někdo z nich právě pracuje — radši se nejdřív
        domluvte.
      </span>
    </div>
  );
}
