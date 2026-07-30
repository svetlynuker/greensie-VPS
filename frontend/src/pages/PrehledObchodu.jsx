import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../components/Layout";
import Ikona from "../components/Ikona";
import { GrafDuvodyProher, GrafForecast, GrafFunnel } from "../components/GrafyObchodu";
import { crmStatistiky, logout, nactiMe } from "../api";
import { fmtDatum, fmtKcKratce } from "../crm";
import "../styles/crm.css";
import "../styles/grafyObchodu.css";

/**
 * Přehled obchodu — čísla, po kterých vedení pozná, jak si firma stojí.
 *
 * Data se berou z jednoho endpointu (`/crm/statistiky`), takže „otevřený případ"
 * je definovaný na jednom místě a graf nad tabulkou s tabulkou souhlasí.
 *
 * Viditelnost je stejná jako v seznamech: OZ vidí svoje čísla, vedení
 * (`crm_vse`) čísla firmy. Nadpis to říká nahlas, aby si nikdo nemyslel, že
 * kouká na celou firmu, když kouká na sebe.
 *
 * ---- Proč je tu poznámka o rozsahu dat (CRM-45) --------------------------
 * Import z Raynetu se dělat nebude, takže appka zná jen zakázky založené od
 * svého spuštění. Bez té poznámky by graf vypadal, jako že obchod spadl na
 * nulu — a to je horší než chybějící graf.
 */

function Kpi({ label, hodnota, jednotka, popis, stav }) {
  return (
    <div className="gs-kpi">
      <div className="gs-kpi-label">{label}</div>
      <div className="gs-kpi-value">
        {hodnota}
        {jednotka && <span className="gs-unit">{jednotka}</span>}
      </div>
      {stav ? (
        <div className="gs-kpi-sub">
          <span className={`gs-pill ${stav}`}>
            <span className="gs-dot" />
            {popis}
          </span>
        </div>
      ) : (
        popis && <div className="gs-kpi-sub">{popis}</div>
      )}
    </div>
  );
}

function Karta({ titulek, popis, deti }) {
  return (
    <section className="fm-card" style={{ padding: 16 }}>
      <div className="gs-karta-hlava" style={{ padding: 0, border: 0, boxShadow: "none", background: "none", marginBottom: 8 }}>
        <span className="gs-karta-titulek">{titulek}</span>
      </div>
      {popis && <p className="gs-karta-popis">{popis}</p>}
      {deti}
    </section>
  );
}

export default function PrehledObchodu() {
  const navigate = useNavigate();
  const [me, setMe] = useState(null);
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);

  useEffect(() => {
    nactiMe()
      .then((m) => {
        if (m.musi_zmenit_heslo) {
          navigate("/zmena-hesla");
          return;
        }
        if (!m.prava?.includes("obchodni_pripady")) {
          navigate("/rozcestnik");
          return;
        }
        setMe(m);
        crmStatistiky()
          .then(setData)
          .catch((e) => setChyba(e.message));
      })
      .catch(() => {
        logout();
        navigate("/");
      });
  }, [navigate]);

  if (!me) return null;
  const s = data?.souhrn;
  const vsechno = me.prava?.includes("crm_vse");

  return (
    <Layout uzivatel={me.uzivatel}>
      <div className="gs-page-head">
        <div>
          <h1 className="gs-page-h1">Přehled obchodu</h1>
          <p className="gs-page-lead">
            {vsechno ? "Čísla celé firmy." : "Tvoje čísla."}
            {s?.data_od ? ` Appka má data od ${fmtDatum(s.data_od)}.` : ""}
          </p>
        </div>
      </div>

      {chyba && <div className="crm-chyba">Statistiky se nepodařilo načíst: {chyba}</div>}

      {/* Poznámka o koexistenci s Raynetem — bez ní vypadá graf jako propad. */}
      <div className="fm-card" style={{ padding: "10px 14px", marginBottom: 14 }}>
        <span className="crm-tise">
          <b>Pozor na výklad:</b> v appce jsou jen zakázky založené tady. Starší obchod
          dojíždí v Raynetu, takže tohle není celý byznys firmy — a čísla budou růst,
          jak se sem budou zakládat nové zakázky.
        </span>
      </div>

      {s && (
        <div className="gs-kpis" style={{ marginBottom: 14 }}>
          <Kpi
            label="Otevřené případy"
            hodnota={s.otevrenych}
            popis={`${fmtKcKratce(s.hodnota_otevrenych_kc)} v pipeline`}
          />
          <Kpi
            label="Vyhráno"
            hodnota={s.vyhranych}
            popis={fmtKcKratce(s.hodnota_vyhranych_kc)}
            stav={s.vyhranych > 0 ? "good" : undefined}
          />
          <Kpi
            label="Prohráno"
            hodnota={s.prohranych}
            popis={fmtKcKratce(s.hodnota_prohranych_kc)}
            stav={s.prohranych > 0 ? "serious" : undefined}
          />
          <Kpi
            label="Úspěšnost"
            hodnota={s.uspesnost_pct == null ? "—" : s.uspesnost_pct}
            jednotka={s.uspesnost_pct == null ? "" : "%"}
            popis={
              s.uspesnost_pct == null
                ? "Zatím není uzavřený případ"
                : `z ${s.vyhranych + s.prohranych} uzavřených`
            }
          />
        </div>
      )}

      <div style={{ display: "grid", gap: 14 }}>
        <Karta
          titulek="Pipeline podle fází"
          popis="Kolik případů a kolik peněz stojí v které fázi. Délka pruhu je hodnota, číslo za ním počet."
          deti={data ? <GrafFunnel data={data.funnel} /> : null}
        />

        <Karta
          titulek="Forecast na 6 měsíců"
          popis="Podle předpokládaného uzavření. Očekávaná hodnota je vynásobená pravděpodobností — s ní se dá počítat, hrubý součet pipeline je vždycky optimističtější."
          deti={
            data ? (
              <GrafForecast data={data.forecast} bezTerminu={data.forecast_bez_terminu} />
            ) : null
          }
        />

        <Karta
          titulek="Důvody proher"
          popis="Kvůli tomuhle se u prohry vynucuje důvod — za měsíc si ho už nikdo nevybaví."
          deti={data ? <GrafDuvodyProher data={data.duvody_proher} /> : null}
        />
      </div>

      {!data && !chyba && (
        <section className="fm-card" style={{ marginTop: 14 }}>
          <div className="gs-prazdno">
            <div className="gs-prazdno-znak">
              <Ikona jmeno="finance" velikost={22} />
            </div>
            <h3>Načítám čísla…</h3>
          </div>
        </section>
      )}
    </Layout>
  );
}
