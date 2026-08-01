import { useEffect, useRef, useState } from "react";
import { nactiProfil, ulozProfil } from "../api";

/**
 * Karta „Podpis do e-mailu" v osobním nastavení.
 *
 * Vyplněný profil = **hotový HTML podpis**, který se sám přidává pod každou
 * odchozí zprávu z e-mailového klienta. Nic se nikam nekopíruje; dřív se to
 * dělalo přes samostatný generátor a vkládalo ručně do Outlooku a Seznamu.
 *
 * ---- Náhled se skládá na serveru ---------------------------------------
 * HTML podpisu **negeneruje tahle komponenta**, jen ho zobrazuje. Kdyby si ho
 * frontend skládal sám, měli bychom dvě verze podpisu, které se dřív nebo
 * později rozejdou — a odeslaná pošta by vypadala jinak než náhled.
 *
 * Náhled jede v `<iframe sandbox>` ze stejného důvodu jako čtení pošty: podpis
 * je HTML a nemá mít přístup ke stránce appky. Navíc se tím jeho styly nemíchají
 * se styly nastavení, takže náhled ukazuje opravdu to, co uvidí příjemce.
 */

// Kolik se čeká od posledního úhozu, než se uloží. Karta nemá tlačítko
// „Uložit" — ukládá se sama, jinak lidé odejdou s nevyplněným podpisem.
const PRODLEVA_ULOZENI_MS = 700;

export default function PodpisNastaveni() {
  const [profil, setProfil] = useState(null);
  const [nacita, setNacita] = useState(true);
  const [uklada, setUklada] = useState(false);
  const [chyba, setChyba] = useState(null);
  const casovac = useRef(null);
  const zivy = useRef(true);

  useEffect(() => {
    zivy.current = true;
    nactiProfil()
      .then((p) => zivy.current && setProfil(p))
      .catch((e) => zivy.current && setChyba(e.message))
      .finally(() => zivy.current && setNacita(false));
    return () => {
      zivy.current = false;
      if (casovac.current) clearTimeout(casovac.current);
    };
  }, []);

  function zmen(pole, hodnota) {
    setProfil((p) => {
      const novy = { ...p, [pole]: hodnota };
      naplanujUlozeni(novy);
      return novy;
    });
  }

  function naplanujUlozeni(data) {
    if (casovac.current) clearTimeout(casovac.current);
    casovac.current = setTimeout(async () => {
      setUklada(true);
      setChyba(null);
      try {
        // Odpověď nese přegenerovaný podpis, takže náhled vždy odpovídá tomu,
        // co server opravdu odešle — ne tomu, co si myslí prohlížeč.
        const ulozeny = await ulozProfil({
          jmeno: data.jmeno || "",
          prijmeni: data.prijmeni || "",
          telefon: data.telefon || "",
          funkce: data.funkce || "",
          pozdrav: data.pozdrav || "",
          podpis_zapnuty: data.podpis_zapnuty !== false,
        });
        if (zivy.current) setProfil(ulozeny);
      } catch (e) {
        if (zivy.current) setChyba(e.message);
      } finally {
        if (zivy.current) setUklada(false);
      }
    }, PRODLEVA_ULOZENI_MS);
  }

  if (nacita) {
    return (
      <section className="fm-card">
        <div className="gs-karta-hlava">
          <span className="gs-karta-titulek">Podpis do e-mailu</span>
        </div>
        <p className="gs-karta-popis">Načítám…</p>
      </section>
    );
  }

  if (!profil) {
    return (
      <section className="fm-card">
        <div className="gs-karta-hlava">
          <span className="gs-karta-titulek">Podpis do e-mailu</span>
        </div>
        {chyba && <div className="em-chyba">{chyba}</div>}
      </section>
    );
  }

  return (
    <section className="fm-card">
      <div className="gs-karta-hlava">
        <span className="gs-karta-titulek">Podpis do e-mailu</span>
        <span className="gs-tb-spacer" />
        {uklada && <span className="crm-tise">Ukládám…</span>}
      </div>
      <p className="gs-karta-popis">
        Z těchhle údajů se skládá <b>firemní HTML podpis</b>, který se sám přidá pod
        každou zprávu odeslanou z appky. Nic se nikam nekopíruje — stačí vyplnit.
        Telefon, e-mail i web jsou v podpisu <b>proklikávací</b>.
      </p>

      {chyba && <div className="em-chyba">{chyba}</div>}

      <div className="pn-mrizka">
        <div className="em-pole">
          <label htmlFor="pn-jmeno">Jméno</label>
          <input
            id="pn-jmeno"
            value={profil.jmeno || ""}
            onChange={(e) => zmen("jmeno", e.target.value)}
            placeholder="Daniel"
          />
        </div>
        <div className="em-pole">
          <label htmlFor="pn-prijmeni">Příjmení</label>
          <input
            id="pn-prijmeni"
            value={profil.prijmeni || ""}
            onChange={(e) => zmen("prijmeni", e.target.value)}
            placeholder="Lupínek"
          />
        </div>
        <div className="em-pole">
          <label htmlFor="pn-telefon">Telefon</label>
          <input
            id="pn-telefon"
            type="tel"
            value={profil.telefon || ""}
            /* Do pole se dá napsat cokoli; server si z toho vytáhne devět
               číslic a „+420" doplní až v podpisu. */
            onChange={(e) => zmen("telefon", e.target.value)}
            placeholder="773 492 029"
          />
          <span className="crm-tise">9 číslic, +420 se doplní samo</span>
        </div>
        <div className="em-pole">
          <label htmlFor="pn-funkce">Funkce (nepovinná)</label>
          <input
            id="pn-funkce"
            value={profil.funkce || ""}
            onChange={(e) => zmen("funkce", e.target.value)}
            placeholder="Jednatel"
          />
          <span className="crm-tise">Prázdné = podpis bude bez řádku s funkcí</span>
        </div>
        <div className="em-pole">
          <label htmlFor="pn-pozdrav">Úvodní pozdrav</label>
          <input
            id="pn-pozdrav"
            value={profil.pozdrav || ""}
            onChange={(e) => zmen("pozdrav", e.target.value)}
            placeholder="S pozdravem"
          />
          <span className="crm-tise">Prázdné = podpis bez pozdravu</span>
        </div>
        <div className="em-pole">
          <label htmlFor="pn-adresa">E-mail v podpisu</label>
          <input id="pn-adresa" value={profil.adresa_v_podpisu || ""} readOnly />
          <span className="crm-tise">
            {profil.navrh_adresy && profil.navrh_adresy !== profil.adresa_v_podpisu
              ? `Bere se z připojené schránky. Podle jména by to bylo ${profil.navrh_adresy}.`
              : "Bere se z připojené schránky, aby odpověď přišla tam, odkud píšeš."}
          </span>
        </div>
      </div>

      <label className="pn-prepinac">
        <input
          type="checkbox"
          checked={profil.podpis_zapnuty !== false}
          onChange={(e) => zmen("podpis_zapnuty", e.target.checked)}
        />
        <span>Přidávat podpis pod odchozí zprávy</span>
      </label>

      <div className="pn-nahled-hlava">Náhled — takhle ho uvidí příjemce</div>
      {profil.pripraveny && profil.podpis_html ? (
        <NahledPodpisu html={profil.podpis_html} />
      ) : (
        <div className="pn-nahled-prazdno">
          Vyplň aspoň jméno a podpis se tady ukáže. Dokud je profil prázdný, odchází
          pošta bez podpisu.
        </div>
      )}
    </section>
  );
}

/**
 * Náhled podpisu v izolovaném rámu.
 *
 * Výška se dopočítává z obsahu — rám si ji sám neurčí. Čte se přes `onLoad`
 * z `documentElement.scrollHeight`; jde to proto, že obsah je náš vlastní
 * (`srcDoc`), takže je se stránkou stejného původu i pod sandboxem.
 */
function NahledPodpisu({ html }) {
  const [vyska, setVyska] = useState(180);
  const ram = useRef(null);

  const dokument = `<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;padding:8px;background:#fff;}</style>
</head><body>${html}</body></html>`;

  function zmerVysku() {
    try {
      const d = ram.current?.contentDocument;
      if (d) setVyska(Math.max(120, d.documentElement.scrollHeight + 16));
    } catch {
      // Když se výška změřit nedá, zůstane výchozí — náhled se jen scrolluje.
    }
  }

  return (
    <div className="pn-nahled">
      <iframe
        ref={ram}
        title="Náhled podpisu"
        /* `allow-same-origin` BEZ `allow-scripts`: díky prvnímu si rodič
           přečte výšku obsahu, díky chybějícímu druhému se v rámu nespustí
           žádný skript. Samotné `sandbox=""` by měření výšky znemožnilo
           (cizí origin), a `allow-scripts` by teprve byl problém. */
        sandbox="allow-same-origin"
        srcDoc={dokument}
        onLoad={zmerVysku}
        style={{ width: "100%", height: vyska, border: 0, display: "block" }}
      />
    </div>
  );
}
