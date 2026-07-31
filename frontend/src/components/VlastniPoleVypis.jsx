/**
 * Výpis vlastních (admin definovaných) polí v detailu záznamu.
 *
 * Karta se ukáže i když ještě žádné pole neexistuje — ale jen tomu, kdo je smí
 * spravovat, aby věděl, že tahle možnost existuje. Běžnému uživateli se prázdná
 * karta nepletla do cesty, tak se mu vůbec nezobrazí.
 */
import { doSkupin, poleViditelne } from "./VlastniPoleVstupy";

function formatuj(pole, hodnota) {
  if (hodnota === null || hodnota === undefined || hodnota === "") return "—";
  if (pole.typ === "ano_ne") return hodnota ? "Ano" : "Ne";
  if (pole.typ === "datum") {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(hodnota));
    return m ? `${Number(m[3])}.${Number(m[2])}.${m[1]}` : String(hodnota);
  }
  if (pole.typ === "cislo") {
    const n = Number(hodnota);
    return Number.isFinite(n) ? n.toLocaleString("cs-CZ") : String(hodnota);
  }
  return String(hodnota);
}

export default function VlastniPoleVypis({
  pole,
  hodnoty,
  muzeSpravovat = false,
  onSprava,
  nadpis = "Doplňující údaje",
  // Běžná pole záznamu pro podmíněnou viditelnost (CRM-33).
  zaznam = null,
}) {
  const zdroj = { ...(zaznam || {}), ...(hodnoty || {}) };
  const seznam = (pole || []).filter((p) => poleViditelne(p, zdroj));
  if (seznam.length === 0 && !muzeSpravovat) return null;

  return (
    <div className="fm-card crm-blok">
      <div className="crm-blok-hlava">
        <h3>{nadpis}</h3>
        <span className="crm-mezera" />
        {muzeSpravovat && (
          <button
            className="fm-btn crm-btn-maly"
            onClick={onSprava}
            title="Přidat nebo upravit vlastní pole této obrazovky"
          >
            ⚙ Upravit pole
          </button>
        )}
      </div>

      {seznam.length === 0 ? (
        <p className="crm-tise">
          Zatím tu nic není. Přes „⚙ Upravit pole" si můžeš přidat vlastní údaj, který
          chceš u těchto záznamů sledovat — bez zásahu do kódu.
        </p>
      ) : (
        doSkupin(seznam).map((skupina) => (
          <div key={skupina.nazev || "_zakladni"}>
            {/* Nadpis skupiny (CRM-33) jen tam, kde skupina opravdu je —
                jinak by nad každým výpisem visel prázdný mezinadpis. */}
            {skupina.nazev && <h4 className="crm-podnadpis">{skupina.nazev}</h4>}
            <dl className="crm-udaje">
              {skupina.pole.map((p) => (
                <div key={p.klic} style={{ display: "contents" }}>
                  <dt title={p.vzorec ? `Počítá se: ${p.vzorec}` : p.napoveda || undefined}>
                    {p.nazev}
                    {p.vzorec ? " ∑" : ""}
                  </dt>
                  <dd>{formatuj(p, (hodnoty || {})[p.klic])}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))
      )}
    </div>
  );
}
