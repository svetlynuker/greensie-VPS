import { Fragment, useEffect, useState } from "react";
import {
  crmAutomatizaceAkce,
  crmPravidla,
  crmPravidloPrepni,
  crmPravidloPridej,
  crmPravidloSmaz,
  crmPravidloUprav,
  crmSablony,
  crmUzivatele,
} from "../api";

/**
 * Automatizace CRM (CRM-31) — „když záznam přejde do stavu X, udělej Y".
 *
 * Kroky jako „případ vyhrán → objednávka" nebo „objednávka podepsaná → projekt
 * ze šablony" dělá dneska člověk ručně, pokaždé stejně. Tady se dají navěsit na
 * přesun v kanbanu.
 *
 * ---- Proč je vypínač na prvním místě a historie hned pod pravidlem ----------
 * Automatika, která zakládá záznamy a není vidět, je horší než ruční práce:
 * člověk nepozná, jestli objednávku založil kolega nebo appka, a přestane jí
 * věřit. Proto u každého pravidla svítí, kolikrát zabralo, co konkrétně
 * udělalo, a jde jedním klikem vypnout.
 *
 * ---- Co se z UI nepozná, ale platí -----------------------------------------
 * Pravidlo se u jednoho záznamu spustí **nejvýš jednou** — případ vrácený
 * z „Vyhráno" do „Vyjednávání" a zpátky nevyrobí druhou objednávku. Je to
 * napsané i v nápovědě okna, protože jinak by to působilo jako chyba.
 *
 * Nabídku stavů i katalog akcí dodává backend (`/crm/automatizace/akce`):
 * stavy jsou konfigurovatelné, takže seznam zadrátovaný tady by po přeskládání
 * kanbanu nabízel fáze, které neexistují.
 */
const PRAZDNE = {
  nazev: "",
  spoust_entita: "op",
  spoust_stav: "",
  akce: "objednavka",
  nastaveni: {},
  aktivni: false,
};

const VYSLEDKY = {
  hotovo: "Provedeno",
  preskoceno: "Nebylo co udělat",
  chyba: "Chyba",
};

export default function AutomatizaceNastaveni({ onZavri }) {
  const [pravidla, setPravidla] = useState(null);
  const [katalog, setKatalog] = useState({ akce: [], entity: [] });
  const [sablony, setSablony] = useState([]);
  const [uzivatele, setUzivatele] = useState([]);
  const [novy, setNovy] = useState(PRAZDNE);
  const [upravovane, setUpravovane] = useState(null);
  const [rozbaleny, setRozbaleny] = useState(null); // id pravidla s otevřenou historií
  const [chyba, setChyba] = useState(null);

  async function nacti() {
    setPravidla(await crmPravidla());
  }

  useEffect(() => {
    crmAutomatizaceAkce()
      .then((k) => {
        setKatalog(k);
        // Předvyplní se první stav entity, aby nové pravidlo nešlo uložit
        // s prázdným spouštěčem.
        const prvni = (k.entity || []).find((e) => e.klic === PRAZDNE.spoust_entita);
        if (prvni?.stavy?.length) {
          setNovy((n) => ({ ...n, spoust_stav: n.spoust_stav || prvni.stavy[0].klic }));
        }
      })
      .catch((e) => setChyba(e.message));
    nacti().catch((e) => setChyba(e.message));
    // Šablony kroků a uživatelé jsou parametry akcí – bez nich by se pravidlo
    // dalo složit, ale nešlo by u něj vybrat šablonu ani řešitele.
    crmSablony()
      .then(setSablony)
      .catch(() => setSablony([]));
    crmUzivatele()
      .then(setUzivatele)
      .catch(() => setUzivatele([]));
  }, []);

  const formular = upravovane || novy;
  const zmen = (zmeny) =>
    upravovane ? setUpravovane({ ...upravovane, ...zmeny }) : setNovy({ ...novy, ...zmeny });
  const zmenNastaveni = (zmeny) =>
    zmen({ nastaveni: { ...(formular.nastaveni || {}), ...zmeny } });

  const definiceAkce = (katalog.akce || []).find((a) => a.klic === formular.akce);
  const entita = (katalog.entity || []).find((e) => e.klic === formular.spoust_entita);
  // Akce, které od zvolené entity nemají co dělat, se nenabízejí — backend by je
  // stejně odmítl a chybová hláška je horší než volba, která tam není.
  const dostupneAkce = (katalog.akce || []).filter((a) =>
    (a.entity || []).includes(formular.spoust_entita)
  );

  function prepniEntitu(klic) {
    const nova = (katalog.entity || []).find((e) => e.klic === klic);
    const akce = (katalog.akce || []).filter((a) => (a.entity || []).includes(klic));
    zmen({
      spoust_entita: klic,
      spoust_stav: nova?.stavy?.[0]?.klic || "",
      // Když dosavadní akce u nové entity nefunguje, přepne se na první možnou.
      akce: akce.some((a) => a.klic === formular.akce) ? formular.akce : akce[0]?.klic || "",
      nastaveni: {},
    });
  }

  async function uloz() {
    setChyba(null);
    const data = {
      nazev: (formular.nazev || "").trim(),
      spoust_entita: formular.spoust_entita,
      spoust_stav: formular.spoust_stav,
      akce: formular.akce,
      nastaveni: formular.nastaveni || {},
      aktivni: Boolean(formular.aktivni),
    };
    try {
      if (upravovane) {
        await crmPravidloUprav(upravovane.id, data);
        setUpravovane(null);
      } else {
        await crmPravidloPridej(data);
        setNovy({ ...PRAZDNE, spoust_stav: entita?.stavy?.[0]?.klic || "" });
      }
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function prepni(p) {
    setChyba(null);
    try {
      await crmPravidloPrepni(p.id);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  async function smaz(p) {
    // Vypnutí je skoro vždycky lepší než smazání: historie běhů je jediné
    // vysvětlení, odkud se vzaly staré automaticky založené záznamy.
    if (
      !window.confirm(
        `Smazat pravidlo „${p.nazev}“ i jeho historii?\n\n` +
          "Objednávky a projekty, které založilo, zůstanou — zmizí jen záznam o tom, " +
          "že je založila appka. Když chceš pravidlo jen zastavit, stačí ho vypnout."
      )
    )
      return;
    setChyba(null);
    try {
      await crmPravidloSmaz(p.id);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    }
  }

  function popisPravidla(p) {
    return `${p.entita_nazev} → ${p.spoust_stav_nazev}`;
  }

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2>Automatizace</h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          <p className="crm-tise">
            Pravidlo se spustí, když někdo přesune záznam do zvoleného stavu — v kanbanu,
            na kartě i hromadnou akcí. Co appka udělala, zapíše <b>do poznámek u záznamu</b>{" "}
            a do historie níž, takže je vždycky vidět, že to nebyl člověk.
          </p>
          <p className="crm-tise crm-napoveda">
            <b>Každé pravidlo zabere u jednoho záznamu jen jednou.</b> Případ vrácený
            z Vyhráno a znovu vyhraný tedy nevyrobí druhou objednávku. Nová pravidla se
            zakládají <b>vypnutá</b> — nejdřív si je projdi, pak zapni.
          </p>

          {chyba && <div className="crm-chyba">{chyba}</div>}

          {pravidla === null ? null : pravidla.length === 0 ? (
            <div className="crm-prazdno">Zatím žádné pravidlo.</div>
          ) : (
            <table className="crm-tabulka crm-tabulka-hustá">
              <thead>
                <tr>
                  <th>Pravidlo</th>
                  <th>Kdy</th>
                  <th>Co udělá</th>
                  <th>Zabralo</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pravidla.map((p) => (
                  // Fragment s klíčem, ne `<>`: pravidlo je DVA řádky (řádek
                  // a rozbalená historie) a bez klíče na obalu React překreslí
                  // celou tabulku při každé změně.
                  <Fragment key={p.id}>
                    <tr className={p.aktivni ? "" : "crm-radek-vypnuty"}>
                      <td>
                        <div className="crm-silne">{p.nazev}</div>
                        <div className="crm-tise">{p.aktivni ? "zapnuté" : "vypnuté"}</div>
                      </td>
                      <td>{popisPravidla(p)}</td>
                      <td>
                        {p.akce_nazev}
                        {p.akce === "ukol" && p.nastaveni?.za_dni != null && (
                          <div className="crm-tise">
                            za {p.nastaveni.za_dni} dní: {p.nastaveni.nazev}
                          </div>
                        )}
                        {p.akce === "projekt" && (
                          <div className="crm-tise">
                            {p.nastaveni?.sablona_id
                              ? (sablony.find((s) => s.id === p.nastaveni.sablona_id) || {})
                                  .nazev || "zvolená šablona"
                              : "šablona podle kategorie případu"}
                          </div>
                        )}
                      </td>
                      <td>
                        {p.behu > 0 ? (
                          <button
                            className="fm-btn crm-btn-maly"
                            onClick={() => setRozbaleny(rozbaleny === p.id ? null : p.id)}
                          >
                            {p.behu}× {rozbaleny === p.id ? "▲" : "▼"}
                          </button>
                        ) : (
                          <span className="crm-tise">—</span>
                        )}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="fm-btn crm-btn-maly" onClick={() => prepni(p)}>
                          {p.aktivni ? "Vypnout" : "Zapnout"}
                        </button>{" "}
                        <button
                          className="fm-btn crm-btn-maly"
                          onClick={() => setUpravovane({ ...p, nastaveni: p.nastaveni || {} })}
                        >
                          Upravit
                        </button>{" "}
                        <button
                          className="fm-btn crm-btn-maly crm-btn-smazat"
                          onClick={() => smaz(p)}
                        >
                          Smazat
                        </button>
                      </td>
                    </tr>
                    {rozbaleny === p.id && (
                      <tr>
                        <td colSpan={5}>
                          <div className="crm-tise" style={{ marginBottom: 6 }}>
                            Co pravidlo udělalo (od nejnovějšího):
                          </div>
                          <table className="crm-tabulka crm-tabulka-hustá">
                            <tbody>
                              {(p.behy || []).map((b) => (
                                <tr key={b.id}>
                                  <td style={{ whiteSpace: "nowrap" }}>
                                    {b.kdy ? new Date(b.kdy).toLocaleString("cs-CZ") : ""}
                                  </td>
                                  <td>{VYSLEDKY[b.vysledek] || b.vysledek}</td>
                                  <td>{b.popis}</td>
                                  <td className="crm-tise">{b.kdo || ""}</td>
                                </tr>
                              ))}
                              {(p.behy || []).length === 0 && (
                                <tr>
                                  <td className="crm-tise">Zatím nic.</td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}

          <h3 style={{ marginTop: 18 }}>{upravovane ? "Úprava pravidla" : "Nové pravidlo"}</h3>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="au-nazev">
              Název *
            </label>
            <input
              id="au-nazev"
              className="crm-pole"
              value={formular.nazev}
              onChange={(e) => zmen({ nazev: e.target.value })}
              placeholder="např. Případ vyhrán → objednávka"
            />
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="au-entita">
              Když se přesune
            </label>
            <select
              id="au-entita"
              className="crm-pole"
              value={formular.spoust_entita}
              onChange={(e) => prepniEntitu(e.target.value)}
            >
              {(katalog.entity || []).map((e) => (
                <option key={e.klic} value={e.klic}>
                  {e.nazev}
                </option>
              ))}
            </select>
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="au-stav">
              do stavu
            </label>
            <select
              id="au-stav"
              className="crm-pole"
              value={formular.spoust_stav}
              onChange={(e) => zmen({ spoust_stav: e.target.value })}
            >
              {(entita?.stavy || []).map((s) => (
                <option key={s.klic} value={s.klic}>
                  {s.nazev}
                </option>
              ))}
            </select>
          </div>

          <div className="crm-pole-radek">
            <label className="crm-label" htmlFor="au-akce">
              tak appka
            </label>
            <select
              id="au-akce"
              className="crm-pole"
              value={formular.akce}
              onChange={(e) => zmen({ akce: e.target.value, nastaveni: {} })}
            >
              {dostupneAkce.map((a) => (
                <option key={a.klic} value={a.klic}>
                  {a.nazev}
                </option>
              ))}
            </select>
          </div>

          {definiceAkce && <p className="crm-tise crm-napoveda">{definiceAkce.popis}</p>}

          {formular.akce === "projekt" && (
            <div className="crm-pole-radek">
              <label className="crm-label" htmlFor="au-sablona">
                Šablona kroků
              </label>
              <select
                id="au-sablona"
                className="crm-pole"
                value={formular.nastaveni?.sablona_id || ""}
                onChange={(e) =>
                  zmenNastaveni({
                    sablona_id: e.target.value ? Number(e.target.value) : null,
                  })
                }
              >
                <option value="">Podle kategorie případu</option>
                {sablony.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.nazev}
                  </option>
                ))}
              </select>
            </div>
          )}

          {formular.akce === "ukol" && (
            <>
              <div className="crm-pole-radek">
                <label className="crm-label" htmlFor="au-dni">
                  Termín za (dní)
                </label>
                <input
                  id="au-dni"
                  className="crm-pole"
                  type="number"
                  min="0"
                  max="365"
                  value={formular.nastaveni?.za_dni ?? 7}
                  onChange={(e) => zmenNastaveni({ za_dni: Number(e.target.value) })}
                />
              </div>
              <div className="crm-pole-radek">
                <label className="crm-label" htmlFor="au-ukol-nazev">
                  Název úkolu *
                </label>
                <input
                  id="au-ukol-nazev"
                  className="crm-pole"
                  value={formular.nastaveni?.nazev || ""}
                  onChange={(e) => zmenNastaveni({ nazev: e.target.value })}
                  placeholder="Zavolat zákazníkovi kvůli nabídce"
                />
              </div>
              <div className="crm-pole-radek">
                <label className="crm-label" htmlFor="au-ukol-text">
                  Popis
                </label>
                <textarea
                  id="au-ukol-text"
                  className="crm-pole"
                  rows={3}
                  value={formular.nastaveni?.text || ""}
                  onChange={(e) => zmenNastaveni({ text: e.target.value })}
                  placeholder="Ozvat se a zjistit, jak se k nabídce staví."
                />
              </div>
              <div className="crm-pole-radek">
                <label className="crm-label" htmlFor="au-komu">
                  Řešitel
                </label>
                <select
                  id="au-komu"
                  className="crm-pole"
                  value={formular.nastaveni?.komu_user_id || ""}
                  onChange={(e) =>
                    zmenNastaveni({
                      komu_user_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                >
                  <option value="">Vlastník záznamu</option>
                  {uzivatele.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.jmeno}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}

          <label className="crm-zaskrtavaci">
            <input
              type="checkbox"
              checked={Boolean(formular.aktivni)}
              onChange={(e) => zmen({ aktivni: e.target.checked })}
            />
            Zapnuté (pravidlo se opravdu spouští)
          </label>
        </div>

        <div className="crm-okno-pata">
          <button
            className="fm-btn fm-primary"
            onClick={uloz}
            disabled={!(formular.nazev || "").trim() || !formular.spoust_stav || !formular.akce}
          >
            {upravovane ? "Uložit změny" : "Přidat pravidlo"}
          </button>
          {upravovane && (
            <button className="fm-btn" onClick={() => setUpravovane(null)}>
              Zrušit úpravu
            </button>
          )}
          <span className="crm-mezera" />
          <button className="fm-btn" onClick={onZavri}>
            Hotovo
          </button>
        </div>
      </div>
    </div>
  );
}
