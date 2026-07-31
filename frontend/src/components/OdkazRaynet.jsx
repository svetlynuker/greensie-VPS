/**
 * Přiznání, že Raynet ještě jede (CRM-45).
 *
 * Import z Raynetu se dělat nebude — stávající zakázky tam dojedou a do appky
 * se zakládají jen nové. Bez téhle věty vypadá každý seznam a součet jako
 * propad obchodu, i když se nic nestalo: appka prostě zná jen část byznysu.
 *
 * Druhá polovina věty je pravidlo, kvůli kterému to celé je: **nová věc se
 * zakládá vždycky tady**, do Raynetu už ne. Kdyby to nebylo napsané u seznamu,
 * lidé by ho dál používali podle zvyku.
 */
const RAYNET_URL = "https://app.raynet.cz";

export default function OdkazRaynet({ co = "zakázky" }) {
  return (
    <div className="crm-raynet-pas">
      <span className="crm-tise">
        V appce jsou jen {co} založené tady. Starší dojíždějí v Raynetu —{" "}
        <b>nové se ale zakládají vždycky v appce</b>, do Raynetu už ne.
      </span>
      <span className="crm-mezera" />
      <a className="crm-odkaz" href={RAYNET_URL} target="_blank" rel="noreferrer">
        Otevřít Raynet →
      </a>
    </div>
  );
}
