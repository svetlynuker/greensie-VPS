import { useState } from "react";
import { emailUcetOdpoj, emailUcetOtestuj, emailUcetUloz } from "../api";

/**
 * Připojení schránky (Seznam.cz) – jednorázové nastavení.
 *
 * ---- Proč se sem zadává heslo od schránky -------------------------------
 * Seznam Email nemá OAuth ani „hesla pro aplikace": IMAP a SMTP jsou trvale
 * zapnuté a přihlašuje se přímo heslem od schránky. Nedá se to obejít, takže
 * to musí být řečeno na rovinu — proto ta poznámka u políčka. Heslo se ukládá
 * zašifrované a **z appky se nedá přečíst**; API vrací jen „nastaveno".
 *
 * ---- Proč je „Otestovat" před „Uložit" ----------------------------------
 * Špatné heslo se pozná až při připojení k serveru. Kdyby se dalo jen uložit,
 * člověk by odešel s pocitem, že to funguje, a schránka by tiše nefungovala
 * (nebo by ho Seznam po pár pokusech začal blokovat). Test proto nic neukládá
 * a dá odpověď hned.
 */
export default function EmailNastaveni({ ucet, onHotovo, onZrusit }) {
  const [adresa, setAdresa] = useState(ucet?.adresa || "");
  const [heslo, setHeslo] = useState("");
  const [jmeno, setJmeno] = useState(ucet?.jmeno_odesilatele || "");
  const [imapHost, setImapHost] = useState(ucet?.imap_host || "imap.seznam.cz");
  const [imapPort, setImapPort] = useState(ucet?.imap_port || 993);
  const [smtpHost, setSmtpHost] = useState(ucet?.smtp_host || "smtp.seznam.cz");
  // 587 (STARTTLS) je výchozí schválně: Hetzner blokuje odchozí port 465,
  // takže by odesílání jen timeoutovalo. Viz backend app/mailer.py.
  const [smtpPort, setSmtpPort] = useState(ucet?.smtp_port || 587);
  const [podpis, setPodpis] = useState(ucet?.podpis || "");
  const [prvniPocet, setPrvniPocet] = useState(ucet?.prvni_sync_pocet || 300);
  const [pokrocile, setPokrocile] = useState(false);

  const [testuje, setTestuje] = useState(false);
  const [uklada, setUklada] = useState(false);
  const [vysledekTestu, setVysledekTestu] = useState(null);
  const [chyba, setChyba] = useState(null);

  const heslo_ulozene = Boolean(ucet?.heslo_nastaveno);
  const klic_chybi = ucet ? ucet.klic_dostupny === false : false;

  function data() {
    return {
      adresa: adresa.trim(),
      jmeno_odesilatele: jmeno.trim(),
      imap_host: imapHost.trim(),
      imap_port: Number(imapPort) || 993,
      smtp_host: smtpHost.trim(),
      smtp_port: Number(smtpPort) || 587,
      // `null` = nechat uložené heslo. Prázdný řetězec by ho smazal, což při
      // úpravě podpisu není to, co člověk chce.
      heslo: heslo ? heslo : null,
      aktivni: true,
      sync_zapnuto: true,
      prvni_sync_pocet: Number(prvniPocet) || 300,
      podpis,
    };
  }

  async function otestuj() {
    setTestuje(true);
    setChyba(null);
    setVysledekTestu(null);
    try {
      const v = await emailUcetOtestuj(data());
      setVysledekTestu(v);
    } catch (e) {
      setChyba(e.message);
    } finally {
      setTestuje(false);
    }
  }

  async function uloz() {
    setUklada(true);
    setChyba(null);
    try {
      await emailUcetUloz(data());
      onHotovo();
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  async function odpoj() {
    if (
      !window.confirm(
        "Odpojit schránku? Z appky zmizí stažená pošta. Na seznam.cz se nesmaže nic.",
      )
    ) {
      return;
    }
    setUklada(true);
    setChyba(null);
    try {
      await emailUcetOdpoj();
      onHotovo();
    } catch (e) {
      setChyba(e.message);
      setUklada(false);
    }
  }

  const muzeUlozit = adresa.includes("@") && (heslo || heslo_ulozene) && !uklada;

  return (
    <div className="fm-card" style={{ padding: 20 }}>
      <div className="em-nastaveni">
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 16 }}>
            {ucet ? "Nastavení schránky" : "Připojit schránku"}
          </h2>
          <p className="em-tise" style={{ margin: 0 }}>
            Pošta zůstává na seznam.cz — appka je do ní jen okno. Co uděláš tady
            (přečteno, přesun do složky), se projeví i v mobilu a na webu Seznamu.
          </p>
        </div>

        {klic_chybi && (
          <div className="em-chyba">
            Na serveru chybí šifrovací klíč (<code>APP_ENC_KEY</code> nebo{" "}
            <code>KONEKTOR_ENC_KEY</code> v <code>.env</code>). Bez něj se heslo ke
            schránce nedá bezpečně uložit — musí ho doplnit správce serveru.
          </div>
        )}

        <div className="em-pole">
          <label htmlFor="em-adresa">E-mailová adresa *</label>
          <input
            id="em-adresa"
            type="email"
            value={adresa}
            onChange={(e) => setAdresa(e.target.value)}
            placeholder="jmeno@greensie.cz"
            autoComplete="username"
          />
        </div>

        <div className="em-pole">
          <label htmlFor="em-heslo">
            Heslo ke schránce {heslo_ulozene ? "(uložené — vyplň jen při změně)" : "*"}
          </label>
          <input
            id="em-heslo"
            type="password"
            value={heslo}
            onChange={(e) => setHeslo(e.target.value)}
            placeholder={heslo_ulozene ? "•••••••• (ponech prázdné)" : ""}
            autoComplete="new-password"
          />
          <p className="em-tise">
            Seznam nenabízí zvláštní „heslo pro aplikace", takže se sem zadává
            opravdové heslo od schránky. Ukládá se zašifrované a z appky se už
            nedá přečíst. Když si heslo na Seznamu změníš, přepiš ho i tady.
          </p>
        </div>

        <div className="em-pole">
          <label htmlFor="em-jmeno">Jméno odesílatele</label>
          <input
            id="em-jmeno"
            value={jmeno}
            onChange={(e) => setJmeno(e.target.value)}
            placeholder="Jak tě uvidí příjemce (prázdné = jméno z appky)"
          />
        </div>

        <div className="em-pole">
          <label htmlFor="em-podpis">Podpis</label>
          <textarea
            id="em-podpis"
            rows={4}
            value={podpis}
            onChange={(e) => setPodpis(e.target.value)}
            placeholder={"Jan Novák\nGreensie s.r.o.\n+420 …"}
          />
        </div>

        <button
          className="fm-btn"
          onClick={() => setPokrocile((p) => !p)}
          aria-expanded={pokrocile}
          style={{ alignSelf: "flex-start" }}
        >
          {pokrocile ? "Skrýt pokročilé" : "Pokročilé (servery, první stažení)"}
        </button>

        {pokrocile && (
          <>
            <div className="em-pole">
              <label>Server příchozí pošty (IMAP)</label>
              <div className="em-pole-dva">
                <input value={imapHost} onChange={(e) => setImapHost(e.target.value)} />
                <input
                  type="number"
                  value={imapPort}
                  onChange={(e) => setImapPort(e.target.value)}
                  aria-label="IMAP port"
                />
              </div>
            </div>
            <div className="em-pole">
              <label>Server odchozí pošty (SMTP)</label>
              <div className="em-pole-dva">
                <input value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
                <input
                  type="number"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(e.target.value)}
                  aria-label="SMTP port"
                />
              </div>
            </div>
            <div className="em-pole">
              <label htmlFor="em-prvni">Kolik zpráv stáhnout při prvním připojení</label>
              <input
                id="em-prvni"
                type="number"
                min={20}
                max={2000}
                value={prvniPocet}
                onChange={(e) => setPrvniPocet(e.target.value)}
              />
              <p className="em-tise">
                Nejnovějších N zpráv v každé složce. Víc znamená delší první stažení;
                na starou poštu je pořád web Seznamu.
              </p>
            </div>
          </>
        )}

        {vysledekTestu && (
          <div className={vysledekTestu.ok ? "em-hlaska-ok" : "em-chyba"}>
            {vysledekTestu.zprava}
            {vysledekTestu.ok && vysledekTestu.slozky?.length > 0 && (
              <div className="em-tise" style={{ marginTop: 4 }}>
                Složky: {vysledekTestu.slozky.slice(0, 12).join(", ")}
                {vysledekTestu.slozky.length > 12 ? " …" : ""}
              </div>
            )}
          </div>
        )}

        {chyba && <div className="em-chyba">{chyba}</div>}

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button
            className="fm-btn"
            onClick={otestuj}
            disabled={testuje || !adresa.includes("@") || (!heslo && !heslo_ulozene)}
          >
            {testuje ? "Zkouším připojit…" : "Otestovat připojení"}
          </button>
          <button className="fm-btn fm-primary" onClick={uloz} disabled={!muzeUlozit}>
            {uklada ? "Ukládám…" : "Uložit"}
          </button>
          <span className="em-mezera" style={{ flex: 1 }} />
          {ucet && (
            <button className="fm-btn" onClick={odpoj} disabled={uklada}>
              Odpojit schránku
            </button>
          )}
          {onZrusit && (
            <button className="fm-btn" onClick={onZrusit} disabled={uklada}>
              Zavřít
            </button>
          )}
        </div>

        {ucet?.posledni_chyba && (
          <div className="em-chyba">
            Poslední chyba při stahování: {ucet.posledni_chyba}
          </div>
        )}
      </div>
    </div>
  );
}
