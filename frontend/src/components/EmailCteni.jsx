import { useMemo, useState } from "react";
import { emailPrilohaStahni } from "../api";
import { fmtDatumCas } from "../crm";

/**
 * Panel čtení jedné zprávy.
 *
 * ---- Proč HTML pošta jede v iframu se sandboxem -------------------------
 * Tělo e-mailu je **cizí HTML od kohokoli na internetu**. Vložit ho přes
 * `dangerouslySetInnerHTML` do appky by znamenalo, že si kdokoli pošle skript,
 * který běží v přihlášené session — přečte token z localStorage a odešle si ho.
 * To není teoretická hrozba, je to nejběžnější způsob, jak se webová pošta
 * hackuje.
 *
 * Proto: `<iframe sandbox>` bez `allow-scripts` a bez `allow-same-origin`.
 * Rám nemá přístup k naší stránce ani k tokenu a skripty se v něm nespustí,
 * i kdyby v mailu byly. Povolené je jen otevírání odkazů do nového okna —
 * bez toho by v mailech nešlo kliknout na nic.
 *
 * Sanitizace značek běží **navíc** k sandboxu, ne místo něj: dvě nezávislé
 * pojistky, protože jedna se dá obejít překlepem.
 *
 * ---- Proč jsou vzdálené obrázky blokované -------------------------------
 * Obrázek stahovaný z cizího serveru je sledovací pixel: prozradí odesílateli,
 * že jsi mail otevřel, kdy a z jaké IP. Zablokované jsou proto všechny vzdálené
 * obrázky a člověk si je pustí kliknutím. Tohle dělá Gmail i Outlook.
 */

// Značky, které v poště nemají co dělat ani v izolovaném rámu.
const NEBEZPECNE_ZNACKY = /<\s*(script|iframe|object|embed|applet|form|link|meta|base)\b[^>]*>/gi;
const NEBEZPECNE_UZAVIRACI = /<\s*\/\s*(script|iframe|object|embed|applet|form)\s*>/gi;
// `onclick=`, `onerror=` a spol. — bez skriptů jsou nefunkční, ale ať tam nejsou.
const UDALOSTI = /\son[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi;
// `href="javascript:…"` — sandbox to zastaví, sanitizace je druhá pojistka.
const JS_ODKAZY = /(href|src)\s*=\s*(["'])\s*javascript:[^"']*\2/gi;

/** Vzdálené `src` schová do `data-em-src`, aby se obrázek nestahoval. */
function zablokujObrazky(html) {
  return html.replace(
    /(<img\b[^>]*?)\ssrc\s*=\s*(["'])(https?:\/\/[^"']*)\2/gi,
    (_cely, zacatek, uvozovka, url) => `${zacatek} data-em-src=${uvozovka}${url}${uvozovka}`,
  );
}

function uklidHtml(html, pustitObrazky) {
  let cisty = String(html || "")
    .replace(NEBEZPECNE_ZNACKY, "")
    .replace(NEBEZPECNE_UZAVIRACI, "")
    .replace(UDALOSTI, "")
    .replace(JS_ODKAZY, "$1=\"#\"");
  if (!pustitObrazky) cisty = zablokujObrazky(cisty);
  return cisty;
}

/** Obsahuje mail vzdálené obrázky? (Podle toho se ukáže lišta „Zobrazit obrázky".) */
function maVzdaleneObrazky(html) {
  return /<img\b[^>]*\ssrc\s*=\s*["']https?:\/\//i.test(String(html || ""));
}

function dokumentPro(html, pustitObrazky) {
  const telo = uklidHtml(html, pustitObrazky);
  // `base target=_blank` — odkazy z mailu se otevírají v novém okně, ne
  // uvnitř rámu (tam by uživatel uvízl bez navigace).
  // CSP v rámu je třetí pojistka: i kdyby sanitizace i sandbox selhaly,
  // prohlížeč nespustí skript a nepustí ven žádný požadavek kromě obrázků.
  const csp = pustitObrazky
    ? "default-src 'none'; img-src http: https: data: cid:; style-src 'unsafe-inline'"
    : "default-src 'none'; img-src data:; style-src 'unsafe-inline'";
  return `<!doctype html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${csp}">
<base target="_blank">
<style>
  html,body{margin:0;padding:0;background:#fff;color:#16211c;
    font:13.5px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;}
  body{padding:4px;}
  img{max-width:100%;height:auto;}
  table{max-width:100%;}
  a{color:#237a34;}
  /* Zablokovaný obrázek nesmí zmizet bez vysvětlení — ať je vidět místo. */
  img[data-em-src]{min-width:16px;min-height:16px;outline:1px dashed #cfd6d1;}
</style></head><body>${telo}</body></html>`;
}

function velikost(bajtu) {
  if (!bajtu) return "";
  if (bajtu < 1024) return `${bajtu} B`;
  if (bajtu < 1024 * 1024) return `${Math.round(bajtu / 1024)} kB`;
  return `${(bajtu / (1024 * 1024)).toFixed(1)} MB`;
}

function adresyText(seznam) {
  return (seznam || [])
    .map((a) => (a.jmeno ? `${a.jmeno} <${a.adresa}>` : a.adresa))
    .join(", ");
}

export default function EmailCteni({
  zprava,
  slozky = [],
  onPriznaky,
  onPresun,
  onDoKose,
  onZavri,
  onOdpovedet,
  onPreposlat,
}) {
  const [pustitObrazky, setPustitObrazky] = useState(false);
  const [chybaPrilohy, setChybaPrilohy] = useState(null);

  const maObrazky = useMemo(
    () => (zprava ? maVzdaleneObrazky(zprava.telo_html) : false),
    [zprava],
  );
  const dokument = useMemo(
    () => (zprava && zprava.telo_html ? dokumentPro(zprava.telo_html, pustitObrazky) : ""),
    [zprava, pustitObrazky],
  );

  if (!zprava) {
    return (
      <div className="em-panel em-panel-cteni">
        <div className="em-prazdno">
          Vyber zprávu vlevo.
          <br />
          <span className="em-tise">Pošta se stahuje na pozadí, nemusíš nic obnovovat.</span>
        </div>
      </div>
    );
  }

  // Přílohy vložené do těla (podpisy, loga) nejsou „příloha" v očích člověka.
  const prilohy = (zprava.prilohy || []).filter((p) => !p.vlozeny);

  async function stahni(p) {
    setChybaPrilohy(null);
    try {
      await emailPrilohaStahni(p.id, p.nazev);
    } catch (e) {
      setChybaPrilohy(e.message);
    }
  }

  return (
    <div className="em-panel em-panel-cteni">
      <div className="em-cteni-nastroje">
        <button className="fm-btn" onClick={() => onOdpovedet && onOdpovedet(zprava, false)}>
          Odpovědět
        </button>
        {(zprava.komu || []).length + (zprava.kopie || []).length > 1 && (
          <button className="fm-btn" onClick={() => onOdpovedet && onOdpovedet(zprava, true)}>
            Odpovědět všem
          </button>
        )}
        <button className="fm-btn" onClick={() => onPreposlat && onPreposlat(zprava)}>
          Přeposlat
        </button>
        <span className="em-mezera" />
        <button
          className="fm-btn"
          aria-pressed={!zprava.precteno}
          title="Označit jako nepřečtené (změní se i na seznam.cz)"
          onClick={() => onPriznaky && onPriznaky(zprava, { precteno: !zprava.precteno })}
        >
          {zprava.precteno ? "Označit nepřečtené" : "Označit přečtené"}
        </button>
        <button
          className="fm-btn"
          aria-pressed={zprava.oznaceno}
          title="Vlaječka"
          onClick={() => onPriznaky && onPriznaky(zprava, { oznaceno: !zprava.oznaceno })}
        >
          {zprava.oznaceno ? "★" : "☆"}
        </button>
        <select
          className="em-hledat"
          style={{ width: "auto" }}
          defaultValue=""
          aria-label="Přesunout do složky"
          onChange={(e) => {
            const id = Number(e.target.value);
            e.target.value = "";
            if (id && onPresun) onPresun(zprava, id);
          }}
        >
          <option value="">Přesunout do…</option>
          {slozky
            .filter((s) => s.id !== zprava.slozka_id)
            .map((s) => (
              <option key={s.id} value={s.id}>
                {s.nazev}
              </option>
            ))}
        </select>
        <button
          className="fm-btn"
          title="Přesunout do Koše (natrvalo se nemaže nic)"
          onClick={() => onDoKose && onDoKose(zprava)}
        >
          Do koše
        </button>
        <button className="fm-btn" onClick={onZavri} aria-label="Zavřít zprávu">
          ×
        </button>
      </div>

      <div className="em-cteni-hlava">
        <h2 className="em-cteni-predmet">{zprava.predmet || "(bez předmětu)"}</h2>
        <div className="em-cteni-radek">
          <strong>{zprava.od_jmeno || zprava.od_adresa}</strong>
          {zprava.od_jmeno ? ` <${zprava.od_adresa}>` : ""}
          {" · "}
          {fmtDatumCas(zprava.datum_at)}
        </div>
        {(zprava.komu || []).length > 0 && (
          <div className="em-cteni-radek">Komu: {adresyText(zprava.komu)}</div>
        )}
        {(zprava.kopie || []).length > 0 && (
          <div className="em-cteni-radek">Kopie: {adresyText(zprava.kopie)}</div>
        )}
        {zprava.zakaznik_nazev && (
          <div className="em-cteni-radek">
            <a href={`/zakaznici/detail/${zprava.zakaznik_id}`} className="em-firma">
              {zprava.zakaznik_nazev}
              {zprava.pripad_cislo ? ` · ${zprava.pripad_cislo}` : ""}
            </a>
          </div>
        )}
      </div>

      <div className="em-telo">
        {maObrazky && !pustitObrazky && (
          <div className="em-obrazky-lista">
            <span>
              Obrázky z internetu jsou zablokované — prozradily by odesílateli, že jsi
              zprávu otevřel.
            </span>
            <span className="em-mezera" />
            <button className="fm-btn" onClick={() => setPustitObrazky(true)}>
              Zobrazit obrázky
            </button>
          </div>
        )}
        {zprava.telo_html ? (
          <iframe
            className="em-telo-html"
            title="Obsah zprávy"
            /* Bez allow-scripts a bez allow-same-origin: skripty z mailu se
               nespustí a rám nevidí do appky ani na přihlašovací token. */
            sandbox="allow-popups allow-popups-to-escape-sandbox"
            srcDoc={dokument}
            /* Rám si výšku sám nespočítá (nemáme do něj přístup — a to je
               záměr), takže dostane pevnou. Uvnitř se scrolluje. */
            style={{ height: "min(calc(100vh - 420px), 900px)", minHeight: 260 }}
          />
        ) : (
          <pre className="em-telo-text">{zprava.telo_text || "(prázdná zpráva)"}</pre>
        )}
      </div>

      {chybaPrilohy && <div className="em-chyba">{chybaPrilohy}</div>}

      {prilohy.length > 0 && (
        <div className="em-prilohy">
          {prilohy.map((p) => (
            <button key={p.id} className="em-priloha" onClick={() => stahni(p)}>
              📎 {p.nazev}
              <span className="em-priloha-velikost">{velikost(p.velikost)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
