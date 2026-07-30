import { fmtKcKratce } from "../crm";

/**
 * Grafy obchodu: pipeline funnel, forecast a rozpad důvodů proher.
 *
 * Bez knihovny (appka má záměrně nulové UI závislosti) a bez vlastní palety —
 * barvy jsou tokeny appky, takže drží světlý, tmavý i barvoslepý režim.
 *
 * ---- Proč tak málo barev --------------------------------------------------
 * Hodnotu nese DÉLKA pruhu a název fáze je vždy přímo u něj, takže barva
 * nemusí rozlišovat identitu. Zůstala jen na druh fáze (otevřená / výhra /
 * prohra) — a i tam je vždy doplněná textem, ne sama.
 *
 * Ověřoval jsem to validátorem palety a byl to dobrý nápad: zelená a oranžová
 * z tokenů appky mají pro protanopii odstupnou vzdálenost 2,8 (potřeba ≥ 8),
 * takže jako sada barev pro fáze by nefungovaly. Tři barvy s popisky ano.
 *
 * Žádný graf tu nemá dvě osy: forecast má hrubou a váženou hodnotu ve stejné
 * jednotce (Kč), takže je to jeden žebřík, ne dvě stupnice.
 */

const PRAZDNO = "Zatím není z čeho počítat.";

/** Vodorovný pruh s názvem, hodnotou a počtem. */
function Pruh({ nazev, popis, sirkaPct, trida, hodnota, pocet }) {
  return (
    <div className="go-radek">
      <div className="go-nazev" title={nazev}>
        {nazev}
        {popis && <span className="go-popis"> {popis}</span>}
      </div>
      <div className="go-drazka">
        <div
          className={`go-pruh ${trida}`}
          style={{ width: `${Math.max(sirkaPct, sirkaPct > 0 ? 1.5 : 0)}%` }}
        />
      </div>
      <div className="go-cislo">
        {hodnota}
        {pocet != null && <span className="go-pocet"> · {pocet}×</span>}
      </div>
    </div>
  );
}

export function GrafFunnel({ data }) {
  const max = Math.max(...(data || []).map((f) => f.hodnota_kc), 1);
  const celkem = (data || []).reduce((s, f) => s + f.pocet, 0);
  if (!celkem) return <p className="crm-tise">{PRAZDNO}</p>;

  return (
    <div className="go">
      {data.map((f) => (
        <Pruh
          key={f.klic}
          nazev={f.nazev}
          popis={f.druh === "vyhra" ? "· vyhráno" : f.druh === "prohra" ? "· prohráno" : ""}
          sirkaPct={(f.hodnota_kc / max) * 100}
          trida={f.druh === "vyhra" ? "ok" : f.druh === "prohra" ? "crit" : "otevreny"}
          hodnota={fmtKcKratce(f.hodnota_kc)}
          pocet={f.pocet}
        />
      ))}
    </div>
  );
}

/**
 * Forecast: sloupce po měsících. Vážená hodnota (× pravděpodobnost) je plný
 * sloupec, hrubá jen světlejší podklad — s tou váženou se dá počítat, hrubý
 * součet pipeline je vždycky optimističtější než realita.
 */
export function GrafForecast({ data, bezTerminu }) {
  const max = Math.max(...(data || []).map((m) => m.hodnota_kc), 1);
  const neco = (data || []).some((m) => m.pocet > 0);

  return (
    <div className="go-forecast">
      <div className="go-legenda">
        <span>
          <span className="go-vzorek vazena" /> očekávané (× pravděpodobnost)
        </span>
        <span>
          <span className="go-vzorek hruba" /> celá hodnota v pipeline
        </span>
      </div>

      {!neco ? (
        <p className="crm-tise">{PRAZDNO}</p>
      ) : (
        <div className="go-sloupce">
          {data.map((m) => {
            const [rok, mes] = m.mesic.split("-");
            return (
              <div className="go-sloupec" key={m.mesic}>
                <div className="go-sloupec-plocha">
                  <div
                    className="go-sl hruba"
                    style={{ height: `${(m.hodnota_kc / max) * 100}%` }}
                    title={`Celá hodnota: ${fmtKcKratce(m.hodnota_kc)}`}
                  />
                  <div
                    className="go-sl vazena"
                    style={{ height: `${(m.vazena_kc / max) * 100}%` }}
                    title={`Očekávané: ${fmtKcKratce(m.vazena_kc)}`}
                  />
                </div>
                <div className="go-sloupec-hodnota">{fmtKcKratce(m.vazena_kc)}</div>
                <div className="go-sloupec-label">
                  {Number(mes)}/{rok.slice(2)}
                  {m.pocet ? <span className="go-pocet"> · {m.pocet}×</span> : null}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {bezTerminu?.pocet > 0 && (
        <p className="crm-tise go-poznamka">
          <b>{bezTerminu.pocet}</b> otevřených případů nemá předpokládané uzavření
          ({fmtKcKratce(bezTerminu.hodnota_kc)}) — ve forecastu nejsou. Doplň jim datum
          a objeví se tady.
        </p>
      )}
    </div>
  );
}

export function GrafDuvodyProher({ data }) {
  if (!(data || []).length) return <p className="crm-tise">Žádná prohra — zatím dobře.</p>;
  const max = Math.max(...data.map((d) => d.pocet), 1);
  return (
    <div className="go">
      {data.map((d) => (
        <Pruh
          key={d.duvod}
          nazev={d.duvod}
          sirkaPct={(d.pocet / max) * 100}
          trida="crit"
          hodnota={fmtKcKratce(d.hodnota_kc)}
          pocet={d.pocet}
        />
      ))}
    </div>
  );
}
