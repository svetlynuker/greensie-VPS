import { useCallback, useEffect, useMemo, useState } from "react";
import Ikona from "../components/Ikona";
import { diskPrava, diskPravoOdeber, diskPravoPridej } from "../api";

/**
 * Sdílení složky nebo souboru na Disku — kdo k tomu má přístup (přání Dana).
 *
 * ---- Co tady vědomě NENÍ -------------------------------------------------
 * **„Kdokoli s odkazem".** Veřejný odkaz na firemní dokument je věc, kterou
 * nikdo nevzal zpět, a jedno kliknutí navíc by ji vyrobilo. Kdo ho opravdu
 * potřebuje, udělá si ho na Disku vědomě. Taky tu nejsou role `owner`
 * a `organizer`: na sdíleném disku rozdávají práva dál a přes appku je nejde
 * odebrat zpátky.
 *
 * ---- Tři druhy řádků, které se nedají odebrat ----------------------------
 * 1. **Zděděné** — přístup přišel z nadřazené složky. Google smazání na téhle
 *    úrovni odmítne, takže se u nich tlačítko vůbec neukazuje; jinak by lidé
 *    klikali a dostávali chybu.
 * 2. **Konektor** — service account. Kdyby zmizel, přestane fungovat zakládání
 *    složek, synchronizace i tenhle modul.
 * 3. Cokoli, když člověk nemá právo `disk_sdileni` — pak je okno jen na čtení.
 *
 * Sdílení složky se dědí na celý její obsah. Je to vlastnost Disku, ne naše, ale
 * musí to být napsané — jinak si člověk myslí, že sdílí jednu složku, a sdílí
 * všechny smlouvy v ní.
 *
 * ---- Zděděná oprávnění jsou sbalená --------------------------------------
 * Na sdíleném disku má přístup celý tým, takže i u čerstvé složky je v seznamu
 * dvacet zděděných řádků. Nesbalené by pohřbily to jediné, co člověk hledá:
 * koho k té složce přidal někdo zvlášť.
 *
 * ---- Varuje se u „nového člověka", ne podle domény ----------------------
 * Doménová kontrola (`@greensie.cz`) se neujala: tým používá vlastní gmaily
 * a seznam.cz, takže označovala 17 z 20 kolegů jako cizí. Varování, které svítí
 * vždycky, si člověk odvykne čítat. Backend proto posílá seznam e-mailů, které
 * na Disku už přístup mají, a varuje se jen u adresy, která mezi nimi není.
 */

const POPIS_ROLE = {
  reader: "může číst",
  commenter: "může komentovat",
  writer: "může upravovat",
  // Tyhle appka nenastavuje, ale na sdíleném disku je má většina lidí — bez
  // překladu by se v seznamu ukazovalo anglické „fileOrganizer".
  fileOrganizer: "správce souborů",
  organizer: "správce disku",
  owner: "vlastník",
};

export default function DiskPrava({ polozka, onZavri }) {
  const [data, setData] = useState(null);
  const [chyba, setChyba] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("reader");
  // Zapnuté: adresy bez účtu Google (u nás většina @greensie.cz) Google bez
  // pozvánky odmítne přidat vůbec.
  const [oznamit, setOznamit] = useState(true);
  const [pracuje, setPracuje] = useState(false);
  const [ukazZdedena, setUkazZdedena] = useState(false);
  const [zprava, setZprava] = useState("");

  const nacti = useCallback(async () => {
    try {
      setData(await diskPrava(polozka.id));
      setChyba(null);
    } catch (e) {
      setChyba(e.message);
    }
  }, [polozka.id]);

  useEffect(() => {
    nacti();
  }, [nacti]);

  useEffect(() => {
    const naKlavesu = (e) => e.key === "Escape" && onZavri();
    window.addEventListener("keydown", naKlavesu);
    return () => window.removeEventListener("keydown", naKlavesu);
  }, [onZavri]);

  async function pridej() {
    const komu = email.trim();
    if (!komu) return;
    setPracuje(true);
    setChyba(null);
    setZprava("");
    try {
      const v = await diskPravoPridej(polozka.id, komu, role, oznamit);
      setEmail("");
      // Google vyšší přístup nepřepíše: kdo už má na sdíleném disku „upravovat",
      // ten ho má dál, i když se mu tady dalo „číst". Tvrdit něco jiného by byla
      // lež, kterou by nikdo neodhalil, dokud by na tom nezáleželo.
      if (v.pozadovana_role && v.role !== v.pozadovana_role) {
        setZprava(
          `${v.email} má na Disku už roli „${POPIS_ROLE[v.role] || v.role}“ — ` +
            `vyšší přístup zůstává, „${POPIS_ROLE[v.pozadovana_role] || v.pozadovana_role}“ ho nepřepíše.`
        );
      } else {
        setZprava(`Nasdíleno: ${v.email}`);
      }
      await nacti();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  async function odeber(clovek) {
    setPracuje(true);
    setChyba(null);
    try {
      await diskPravoOdeber(polozka.id, clovek.id);
      await nacti();
    } catch (e) {
      setChyba(e.message);
    } finally {
      setPracuje(false);
    }
  }

  // Varování se ukazuje už při psaní — až po odeslání by bylo pozdě.
  const novyClovek =
    email.includes("@") && !(data?.znami || []).includes(email.trim().toLowerCase());

  const vlastni = useMemo(
    () => (data?.lide || []).filter((c) => !c.zdedene),
    [data]
  );
  const zdedena = useMemo(() => (data?.lide || []).filter((c) => c.zdedene), [data]);

  return (
    <div className="crm-okno-plast" onClick={onZavri}>
      <div className="crm-okno crm-okno-uzke" onClick={(e) => e.stopPropagation()}>
        <div className="crm-okno-hlava">
          <h2 className="dk-nahled-nazev" title={polozka.nazev}>
            Sdílení: {polozka.nazev}
          </h2>
          <span className="crm-mezera" />
          <button className="crm-zavrit" onClick={onZavri} aria-label="Zavřít">
            ×
          </button>
        </div>

        <div className="crm-okno-telo">
          {chyba && <div className="crm-chyba">{chyba}</div>}
          {zprava && !chyba && <div className="dk-hlaska-radek">{zprava}</div>}
          {!data && !chyba && <p className="crm-tise">Zjišťuji na Disku…</p>}

          {data && (
            <>
              <p className="crm-tise">
                {data.je_slozka ? (
                  <>
                    Sdílení složky platí <b>na všechno v ní</b>, i na podsložky — tak to má
                    Google Disk.
                  </>
                ) : (
                  <>Přístup k tomuhle jednomu souboru.</>
                )}
              </p>

              {/* Radek jednoho člověka. Stejný pro přidané i zděděné, jen
                  u zděděných chybí tlačítko — mazat je musí ten, kdo je dal. */}
              <ul className="dk-prava-seznam">
                {vlastni.length === 0 && (
                  <li className="crm-tise">
                    Nikdo přidaný zvlášť — přístup mají ti, kdo ho mají na sdíleném disku
                    (viz níž).
                  </li>
                )}
                {vlastni.map((c) => (
                  <li className="dk-pravo" key={c.id}>
                    <span className="dk-pravo-kdo">
                      <span className="dk-pravo-email">{c.email || c.jmeno || c.typ}</span>
                      {c.jmeno && c.email && <span className="crm-tise"> · {c.jmeno}</span>}
                      <span className="dk-pravo-znacky">
                        {c.novy && !c.sluzebni && (
                          <span className="dk-znacka dk-znacka-var">jinde na Disku není</span>
                        )}
                        {c.sluzebni && <span className="dk-znacka">konektor</span>}
                      </span>
                    </span>
                    <span className="crm-tise">{POPIS_ROLE[c.role] || c.role}</span>
                    {data.smim_menit && !c.sluzebni ? (
                      <button
                        className="fm-btn crm-btn-maly"
                        onClick={() => odeber(c)}
                        disabled={pracuje}
                        title={`Odebrat přístup ${c.email}`}
                      >
                        Odebrat
                      </button>
                    ) : (
                      <span className="dk-pravo-misto" aria-hidden="true" />
                    )}
                  </li>
                ))}
              </ul>

              {/* Zděděná oprávnění sbalená: na sdíleném disku je má celý tým,
                  takže rozbalená by pohřbila to, co člověk hledá. */}
              {zdedena.length > 0 && (
                <div className="dk-zdedena">
                  <button className="dk-rozbal" onClick={() => setUkazZdedena(!ukazZdedena)}>
                    <span className={`dk-rozbal-sipka ${ukazZdedena ? "dolu" : ""}`}>›</span>
                    Přístup ze sdíleného disku a nadřazených složek ({zdedena.length})
                  </button>
                  {ukazZdedena && (
                    <ul className="dk-prava-seznam">
                      {zdedena.map((c) => (
                        <li className="dk-pravo" key={c.id}>
                          <span className="dk-pravo-kdo">
                            <span className="dk-pravo-email">
                              {c.email || c.jmeno || c.typ}
                            </span>
                            <span className="dk-pravo-znacky">
                              {c.sluzebni && <span className="dk-znacka">konektor</span>}
                            </span>
                          </span>
                          <span className="crm-tise">{POPIS_ROLE[c.role] || c.role}</span>
                          <span className="dk-pravo-misto" aria-hidden="true" />
                        </li>
                      ))}
                    </ul>
                  )}
                  {ukazZdedena && (
                    <p className="crm-tise dk-prava-pozn">
                      Tyhle přístupy se odebírají tam, kde byly dané — na sdíleném disku nebo
                      u nadřazené složky, ne tady.
                    </p>
                  )}
                </div>
              )}

              {data.smim_menit ? (
                <div className="dk-prava-pridat">
                  <input
                    className="dk-filtr"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && pridej()}
                    placeholder="e-mail člověka…"
                  />
                  <select
                    className="dk-filtr dk-role"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    {(data.role || []).map((r) => (
                      <option key={r} value={r}>
                        {POPIS_ROLE[r] || r}
                      </option>
                    ))}
                  </select>
                  <button
                    className="fm-btn crm-btn-maly fm-primary"
                    onClick={pridej}
                    disabled={!email.trim() || pracuje}
                  >
                    {pracuje ? "Pracuji…" : "Nasdílet"}
                  </button>
                  <label className="crm-tise dk-oznamit" title="Adresy bez účtu Google Disk bez pozvánky nepřijme">
                    <input
                      type="checkbox"
                      checked={oznamit}
                      onChange={(e) => setOznamit(e.target.checked)}
                    />{" "}
                    poslat pozvánku e-mailem
                  </label>
                  {novyClovek && (
                    <div className="dk-varovani">
                      <Ikona jmeno="zamek" velikost={14} /> Tuhle adresu na Disku nikdo jiný
                      nemá — sdílíš firemní dokument někomu novému. Zkontroluj ji po znaku.
                    </div>
                  )}
                  {!oznamit && (
                    <p className="crm-tise dk-prava-pozn">
                      Bez pozvánky se člověk nedozví sám — a adresu, která nemá účet Google
                      (u nás většina @greensie.cz), Disk takhle nepřijme vůbec.
                    </p>
                  )}
                </div>
              ) : (
                <p className="crm-tise">
                  Sdílení měnit nemůžeš — potřebuješ právo <b>Disk – měnit sdílení</b>.
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
