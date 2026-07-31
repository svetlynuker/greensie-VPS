// Prodej: stejný pracovní stůl jako peak shaving a PPA, ale výpočet zatím není.
// Panel vlevo drží to, co už dnes smysl má (načtení profilu odběru — ukládá se
// k nabídce a použije ho i budoucí návrh), pravý sloupec říká, co se připravuje.
// Vědomě tu NEJSOU vypnutá políčka pro parametry, které backend neumí přijmout:
// vypadala by jako funkce, která jen nejde zapnout.

import { useEffect, useState } from "react";
import { ppaProfilSouhrn, profilZpracuj } from "../api";

function kw(x) {
  return x == null ? "—" : `${x.toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} kW`;
}
function fmtDatumCas(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : "—";
}

// Co bude výpočet potřebovat, až bude metodika hotová. Držíme to tady, ať OZ ví,
// jaké podklady si od zákazníka vyžádat už teď.
const BUDE_POTREBA = [
  "profil odběru (15min export) nebo aspoň roční spotřebu z faktury",
  "požadovaný výkon FVE, nebo plochu a orientaci střechy",
  "jestli má být součástí baterie, a na jaký účel (záloha / špičky)",
  "obchodní marži a délku záruky, které se mají do ceny promítnout",
];

export default function ProdejPanel({ nabidka }) {
  const [souhrn, setSouhrn] = useState(null);
  const [zpracovavaId, setZpracovavaId] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [zprava, setZprava] = useState(null);

  // Profil se parsuje hned při nahrání souboru, proto je v závislostech podpis
  // dokumentů — jinak by panel po nahrání dál tvrdil, že profil chybí.
  const dokPodpis = (nabidka.dokumenty || [])
    .map((d) => `${d.id}:${d.stav_zpracovani}`)
    .join(",");

  useEffect(() => {
    // Endpoint je pojmenovaný podle PPA, ale jen čte tabulku profilu spotřeby
    // dané nabídky a na typ se neváže — pro prodej vrací totéž.
    ppaProfilSouhrn(nabidka.id)
      .then(setSouhrn)
      .catch(() => setSouhrn({ pocet: 0 }));
  }, [nabidka.id, dokPodpis]);

  const profilDoklady = (nabidka.dokumenty || []).filter(
    (d) => d.typ === "spotreba_csv" || d.typ === "jiny"
  );
  const profilOk = souhrn && souhrn.pocet > 0;

  async function nactiProfil(dokId) {
    setZpracovavaId(dokId);
    setChyba(null);
    setZprava(null);
    try {
      const s = await profilZpracuj(nabidka.id, dokId);
      setSouhrn(await ppaProfilSouhrn(nabidka.id));
      setZprava(`Profil načten: ${s.pocet.toLocaleString("cs-CZ")} intervalů.`);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setZpracovavaId(null);
    }
  }

  return (
    <div className="gs-desk">
      <form className="gs-panel" onSubmit={(e) => e.preventDefault()}>
        <div className="gs-panel-h">
          <h3>Vstupy výpočtu</h3>
          <span style={{ flex: 1 }} />
          <span className="nb-badge pozor">připravuje se</span>
        </div>

        <div className="gs-panel-body">
          <section className="gs-step">
            <span className="gs-step-num">1</span>
            <h4>Profil odběru</h4>
            <div className="gs-step-sub">
              Nepovinné, ale vyplatí se: profil se uloží k nabídce a použije ho i budoucí návrh.
            </div>
            {profilOk ? (
              <div className="gs-stav">
                <span aria-hidden="true">✓</span>
                <div>
                  <div>
                    <b>{souhrn.pocet.toLocaleString("cs-CZ")}</b> intervalů ·{" "}
                    {fmtDatumCas(souhrn.od)} – {fmtDatumCas(souhrn.do)}
                  </div>
                  <div style={{ color: "var(--ink-2)" }}>
                    roční spotřeba <b>{souhrn.rocni_spotreba_mwh} MWh</b>
                    {souhrn.max_kw != null && <> · špička {kw(souhrn.max_kw)}</>}
                  </div>
                </div>
              </div>
            ) : (
              <div className="gs-stav chybi">
                <span aria-hidden="true">○</span>
                <div>Profil zatím není načtený.</div>
              </div>
            )}
            {profilDoklady.length === 0 ? (
              <div className="gs-pozn" style={{ marginTop: 8 }}>
                Zatím není nahraný žádný soubor se spotřebou — nahraj ho v sekci Podklady výše.
              </div>
            ) : (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
                {profilDoklady.map((d) => (
                  <button
                    key={d.id}
                    className="fm-btn"
                    style={{ padding: "4px 10px", fontSize: 12 }}
                    onClick={() => nactiProfil(d.id)}
                    disabled={zpracovavaId === d.id}
                  >
                    {zpracovavaId === d.id ? "Načítám…" : `Načíst: ${d.puvodni_nazev}`}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="gs-step">
            <span className="gs-step-num">2</span>
            <h4>
              Parametry návrhu
              <span className="nb-badge pozor">čeká na metodiku</span>
            </h4>
            <div className="gs-step-sub">
              Až bude metodika hotová, budou tady tato pole. Zatím si od zákazníka posbírej
              podklady:
            </div>
            <ul className="gs-chk">
              {BUDE_POTREBA.map((co) => (
                <li key={co}>
                  <span className="gs-chk-mark" aria-hidden="true" style={{ color: "var(--muted)" }}>
                    •
                  </span>
                  <span>{co}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="gs-panel-f">
          <button className="fm-btn fm-primary" disabled title="Výpočet prodeje se připravuje">
            Spočítat návrh
          </button>
          <ul className="gs-chk" style={{ marginTop: 10 }}>
            <li className={profilOk ? "gs-chk-ok" : "gs-chk-no"}>
              <span className="gs-chk-mark" aria-hidden="true">{profilOk ? "✓" : "!"}</span>
              <span>{profilOk ? "Profil odběru načtený" : "Profil odběru (nepovinné)"}</span>
            </li>
            <li className="gs-chk-no">
              <span className="gs-chk-mark" aria-hidden="true">!</span>
              <span>Výpočtová metodika prodeje — připravuje se</span>
            </li>
          </ul>
          {zprava && (
            <div style={{ color: "var(--brand-strong)", fontSize: 12, marginTop: 8 }}>{zprava}</div>
          )}
          {chyba && <div style={{ color: "var(--st-crit)", fontSize: 12, marginTop: 8 }}>{chyba}</div>}
        </div>
      </form>

      <div>
        <div className="gs-res-h">
          <div>
            <div className="gs-nadtitul">Navržené řešení</div>
            <h3>
              Výpočet se připravuje
              <span className="nb-badge pozor">prodej</span>
            </h3>
          </div>
        </div>

        <div className="fm-card" style={{ padding: 24 }}>
          <p style={{ margin: "0 0 12px", fontSize: 13, lineHeight: 1.6 }}>
            Až bude doladěná metodika, objeví se tady <b>navržené řešení</b> — velikost
            elektrárny nebo baterie z katalogu, prodejní cena, marže a návratnost pro zákazníka.
            I ve víc variantách vedle sebe, jako to má peak shaving.
          </p>
          <p style={{ margin: "0 0 16px", fontSize: 13, lineHeight: 1.6, color: "var(--ink-2)" }}>
            Do té doby jde nabídka prodeje připravit ručně: nahraj podklady, načti profil odběru a
            technologii vyber z katalogu.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a
              className="fm-btn"
              href="/nabidkovac/katalog"
              style={{ textDecoration: "none" }}
              title="Katalog technologií — produkty, ceny a parametry"
            >
              Otevřít katalog produktů
            </a>
            <a
              className="fm-btn"
              href="/manual?stranka=nabidkovac"
              target="_blank"
              rel="noreferrer"
              style={{ textDecoration: "none" }}
            >
              Nápověda k nabídkovači
            </a>
          </div>
        </div>

        <details className="gs-meta" style={{ marginTop: 12 }}>
          <summary>Proč tu nejsou aspoň vypnutá políčka</summary>
          <div className="gs-meta-in">
            Šedá políčka, do kterých se nedá psát, vypadají jako funkce, která jen není zapnutá —
            a vedou k dotazům „kdo mi to zapne". Dokud výpočet neexistuje, je poctivější napsat, co
            se připravuje, a co si zatím vyžádat od zákazníka. Rozvržení je přitom stejné jako
            u ostatních linií, takže až parametry přijdou, nastěhují se do panelu vlevo a nic se
            pro OZ nezmění.
          </div>
        </details>
      </div>
    </div>
  );
}
