import { useEffect, useState } from "react";
import { crmOblibene, crmPrepniOblibeny, crmZaznamenejOtevreni } from "../api";

/**
 * Hvězdička „přišpendlit záznam" na kartě (CRM-37).
 *
 * Kromě přepínání dělá i druhou, neviditelnou věc: při prvním vykreslení
 * **zapíše otevření do historie**. Je to schválně tady a ne v každé kartě
 * zvlášť — jinak by se na to u nové obrazovky zapomnělo a „naposledy otevřené"
 * by mělo díry. Zápis se nikde neprojeví, když selže; je to vedlejší efekt
 * prohlížení, ne účel.
 *
 * Stav se čte ze seznamu oblíbených, ne z detailu záznamu: špendlík je
 * uživatelská věc, která nemá co dělat ve schématu každé entity.
 */
export default function Spendlik({ entita, zaznamId }) {
  const [oblibeny, setOblibeny] = useState(false);
  const [pracuje, setPracuje] = useState(false);

  useEffect(() => {
    if (!entita || !zaznamId) return;
    crmZaznamenejOtevreni(entita, zaznamId).catch(() => {});
    crmOblibene()
      .then((d) =>
        setOblibeny(
          (d?.oblibene || []).some((x) => x.entita === entita && x.zaznam_id === zaznamId)
        )
      )
      .catch(() => {});
  }, [entita, zaznamId]);

  async function prepni() {
    setPracuje(true);
    const cil = !oblibeny;
    setOblibeny(cil); // optimisticky, ať hvězdička nečeká na server
    try {
      await crmPrepniOblibeny(entita, zaznamId, cil);
    } catch {
      setOblibeny(!cil);
    } finally {
      setPracuje(false);
    }
  }

  return (
    <button
      className={`crm-spendlik ${oblibeny ? "aktivni" : ""}`}
      onClick={prepni}
      disabled={pracuje}
      title={
        oblibeny
          ? "Odebrat z oblíbených"
          : "Přišpendlit — bude nahoře v hledání (Ctrl+K)"
      }
      aria-pressed={oblibeny}
      aria-label="Oblíbené"
    >
      {oblibeny ? "★" : "☆"}
    </button>
  );
}
