import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Formátovací editor těla e-mailu — písmo, barvy, odrážky, číslování, zarovnání.
 *
 * ---- Proč vlastní editor a ne knihovna ----------------------------------
 * Dva důvody, každý sám o sobě dostatečný:
 *
 * 1. Projekt má **záměrně nulové UI závislosti** (viz `Ikona.jsx`). TipTap ani
 *    Quill by nepřidaly stovky kilobajtů do balíku jen kvůli jedné obrazovce.
 * 2. Moderní editory vyrábějí moderní HTML. **Poštovní klienti ho neumí** —
 *    Outlook renderuje přes Word, takže potřebuje jednoduché značky a inline
 *    styly. To, co je pro web zaostalé, je pro e-mail jediné funkční.
 *
 * Stojí to na `contentEditable` + `document.execCommand`. Ano, `execCommand` je
 * označený za zastaralý, ale funguje ve všech prohlížečích, nic ho nenahrazuje
 * (`ContentEditable API` nikdy nedošlo do standardu) a pro e-mailové HTML
 * dělá přesně to, co má.
 *
 * ---- Dvě věci, které se snadno rozbijí ----------------------------------
 * * **Ztráta výběru při kliknutí na tlačítko.** Kliknutí přesouvá fokus a výběr
 *   v textu zmizí, takže by se formátování nemělo na co použít. Řeší to
 *   `onMouseDown` s `preventDefault()` na každém tlačítku lišty.
 * * **Vkládání z Wordu.** Přináší kilometry `mso-` stylů a `<o:p>` značek.
 *   Vložený obsah se proto čistí hned při vložení; server ho pro jistotu čistí
 *   ještě jednou (`email_html.py`), protože prohlížeči se věřit nedá.
 */

const PISMA = [
  ["Arial", "Arial, Helvetica, sans-serif"],
  ["Times New Roman", "'Times New Roman', Times, serif"],
  ["Georgia", "Georgia, serif"],
  ["Verdana", "Verdana, Geneva, sans-serif"],
  ["Tahoma", "Tahoma, Geneva, sans-serif"],
  ["Courier New", "'Courier New', Courier, monospace"],
];

// `fontSize` v execCommand bere 1–7, ne pixely. Popisky jsou orientační
// velikosti, jak je lidé znají z Wordu.
const VELIKOSTI = [
  ["Malé", "2"],
  ["Normální", "3"],
  ["Větší", "4"],
  ["Velké", "5"],
  ["Nadpis", "6"],
];

const BARVY = [
  ["Černá", "#000000"], ["Šedá", "#4b5852"], ["Zelená", "#2f9e44"],
  ["Modrá", "#1971c2"], ["Červená", "#d03b3b"], ["Oranžová", "#e8590c"],
  ["Fialová", "#7048e8"], ["Bílá", "#ffffff"],
];

const ZVYRAZNENI = [
  ["Žlutá", "#fff3bf"], ["Zelená", "#d3f9d8"], ["Modrá", "#d0ebff"],
  ["Růžová", "#ffdeeb"], ["Bez zvýraznění", "transparent"],
];

/** Odstraní z vloženého HTML to, co do e-mailu nepatří (hlavně balast z Wordu). */
function vycistiVlozene(html) {
  return String(html || "")
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<\/?(?:script|style|meta|link|head|title|o:p|xml|w:[a-z]+)[^>]*>/gi, "")
    .replace(/\sclass="[^"]*"/gi, "")
    .replace(/\s(?:lang|xmlns[^=]*)="[^"]*"/gi, "")
    .replace(/\son[a-z]+="[^"]*"/gi, "")
    // `mso-` deklarace uvnitř style="…" – Word jich vkládá desítky na značku.
    .replace(/style="([^"]*)"/gi, (_c, styl) => {
      const cisty = styl
        .split(";")
        .filter((d) => d.includes(":") && !/^\s*(mso-|-ms-|panose|tab-stops)/i.test(d))
        .join(";");
      return cisty.trim() ? `style="${cisty}"` : "";
    });
}

export default function TextovyEditor({ hodnota, onZmena, minVyska = 260 }) {
  const plocha = useRef(null);
  const [stav, setStav] = useState({});
  // Nastavené jen jednou: obsah řídí `contentEditable`, ne React. Kdyby se
  // překresloval z propsy při každém úhozu, skákal by kurzor na začátek.
  const nastaveno = useRef(false);

  useEffect(() => {
    if (nastaveno.current || !plocha.current) return;
    plocha.current.innerHTML = hodnota || "";
    nastaveno.current = true;
    // Barvy a velikosti chceme jako inline styly, ne jako <font> značky —
    // inline styly zvládne víc poštovních klientů.
    try {
      document.execCommand("styleWithCSS", false, true);
    } catch {
      // Starší prohlížeč to neumí; formátování bude přes <font>, což taky projde.
    }
  }, [hodnota]);

  const ohlas = useCallback(() => {
    if (plocha.current && onZmena) onZmena(plocha.current.innerHTML);
  }, [onZmena]);

  /** Zjistí, které formátování je pod kurzorem – lišta pak zvýrazní aktivní. */
  const obnovStav = useCallback(() => {
    const zjisti = (prikaz) => {
      try {
        return document.queryCommandState(prikaz);
      } catch {
        return false;
      }
    };
    setStav({
      bold: zjisti("bold"),
      italic: zjisti("italic"),
      underline: zjisti("underline"),
      strikeThrough: zjisti("strikeThrough"),
      insertUnorderedList: zjisti("insertUnorderedList"),
      insertOrderedList: zjisti("insertOrderedList"),
      justifyLeft: zjisti("justifyLeft"),
      justifyCenter: zjisti("justifyCenter"),
      justifyRight: zjisti("justifyRight"),
    });
  }, []);

  useEffect(() => {
    document.addEventListener("selectionchange", obnovStav);
    return () => document.removeEventListener("selectionchange", obnovStav);
  }, [obnovStav]);

  function prikaz(jmeno, hodnotaPrikazu = null) {
    plocha.current?.focus();
    try {
      document.execCommand(jmeno, false, hodnotaPrikazu);
    } catch {
      // Neznámý příkaz nesmí shodit psaní zprávy.
    }
    ohlas();
    obnovStav();
  }

  function vlozOdkaz() {
    const vyber = window.getSelection()?.toString();
    const url = window.prompt(
      "Adresa odkazu:",
      vyber && /^https?:\/\//i.test(vyber) ? vyber : "https://",
    );
    if (!url) return;
    // `javascript:` odkaz by v mailu nefungoval a je to typický pokus o útok.
    if (!/^(https?:\/\/|mailto:|tel:)/i.test(url)) {
      window.alert("Odkaz musí začínat https://, mailto: nebo tel:");
      return;
    }
    prikaz("createLink", url);
  }

  function vlozit(e) {
    // Vlastní vkládání: prohlížeč by jinak vložil syrové HTML z Wordu i s balastem.
    e.preventDefault();
    const data = e.clipboardData;
    const html = data?.getData("text/html");
    const text = data?.getData("text/plain") || "";
    if (html) {
      document.execCommand("insertHTML", false, vycistiVlozene(html));
    } else {
      // Prostý text: zalomení řádků musí přežít, jinak se odstavce slijí.
      const bezpecny = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\r\n/g, "\n")
        .replace(/\n/g, "<br>");
      document.execCommand("insertHTML", false, bezpecny);
    }
    ohlas();
  }

  function klavesa(e) {
    // Ctrl+Shift+V = vložit bez formátování (jako ve Wordu i v prohlížečích).
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === "v") {
      return; // necháme projít nativní chování, `onPaste` si to přebere
    }
    // Enter v seznamu má dělat další odrážku – to execCommand řeší sám.
  }

  const T = ({ prikazJmeno, popis, znak, aktivni, akce }) => (
    <button
      type="button"
      className="te-tlacitko"
      title={popis}
      aria-label={popis}
      aria-pressed={aktivni ? true : undefined}
      // Bez tohohle klik odebere výběr v textu a formátovat se nemá co.
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => (akce ? akce() : prikaz(prikazJmeno))}
    >
      {znak}
    </button>
  );

  return (
    <div className="te-obal">
      <div className="te-lista" role="toolbar" aria-label="Formátování textu">
        <T prikazJmeno="undo" popis="Zpět (Ctrl+Z)" znak="↶" />
        <T prikazJmeno="redo" popis="Znovu (Ctrl+Y)" znak="↷" />
        <span className="te-oddelovac" />

        <select
          className="te-vyber"
          title="Písmo"
          aria-label="Písmo"
          defaultValue=""
          onMouseDown={(e) => e.stopPropagation()}
          onChange={(e) => {
            if (e.target.value) prikaz("fontName", e.target.value);
            e.target.value = "";
          }}
        >
          <option value="">Písmo</option>
          {PISMA.map(([nazev, css]) => (
            <option key={nazev} value={css}>{nazev}</option>
          ))}
        </select>

        <select
          className="te-vyber"
          title="Velikost písma"
          aria-label="Velikost písma"
          defaultValue=""
          onChange={(e) => {
            if (e.target.value) prikaz("fontSize", e.target.value);
            e.target.value = "";
          }}
        >
          <option value="">Velikost</option>
          {VELIKOSTI.map(([nazev, v]) => (
            <option key={v} value={v}>{nazev}</option>
          ))}
        </select>

        <span className="te-oddelovac" />
        <T prikazJmeno="bold" popis="Tučně (Ctrl+B)" znak={<b>B</b>} aktivni={stav.bold} />
        <T prikazJmeno="italic" popis="Kurzíva (Ctrl+I)" znak={<i>I</i>} aktivni={stav.italic} />
        <T
          prikazJmeno="underline"
          popis="Podtržení (Ctrl+U)"
          znak={<u>U</u>}
          aktivni={stav.underline}
        />
        <T
          prikazJmeno="strikeThrough"
          popis="Přeškrtnuto"
          znak={<s>S</s>}
          aktivni={stav.strikeThrough}
        />

        <span className="te-oddelovac" />
        <select
          className="te-vyber te-barvy"
          title="Barva písma"
          aria-label="Barva písma"
          defaultValue=""
          onChange={(e) => {
            if (e.target.value) prikaz("foreColor", e.target.value);
            e.target.value = "";
          }}
        >
          <option value="">Barva ▾</option>
          {BARVY.map(([nazev, kod]) => (
            <option key={kod} value={kod}>{nazev}</option>
          ))}
        </select>
        <select
          className="te-vyber te-barvy"
          title="Zvýraznění textu"
          aria-label="Zvýraznění textu"
          defaultValue=""
          onChange={(e) => {
            if (e.target.value) prikaz("hiliteColor", e.target.value);
            e.target.value = "";
          }}
        >
          <option value="">Zvýraznit ▾</option>
          {ZVYRAZNENI.map(([nazev, kod]) => (
            <option key={kod} value={kod}>{nazev}</option>
          ))}
        </select>

        <span className="te-oddelovac" />
        <T
          prikazJmeno="insertUnorderedList"
          popis="Odrážky"
          znak="•—"
          aktivni={stav.insertUnorderedList}
        />
        <T
          prikazJmeno="insertOrderedList"
          popis="Číslování"
          znak="1."
          aktivni={stav.insertOrderedList}
        />
        <T prikazJmeno="outdent" popis="Zmenšit odsazení" znak="⇤" />
        <T prikazJmeno="indent" popis="Zvětšit odsazení" znak="⇥" />

        <span className="te-oddelovac" />
        <T prikazJmeno="justifyLeft" popis="Zarovnat vlevo" znak="⬱" aktivni={stav.justifyLeft} />
        <T
          prikazJmeno="justifyCenter"
          popis="Zarovnat na střed"
          znak="≡"
          aktivni={stav.justifyCenter}
        />
        <T prikazJmeno="justifyRight" popis="Zarovnat vpravo" znak="⬲" aktivni={stav.justifyRight} />

        <span className="te-oddelovac" />
        <T popis="Vložit odkaz" znak="🔗" akce={vlozOdkaz} />
        <T prikazJmeno="unlink" popis="Zrušit odkaz" znak="⛓" />
        <T
          popis="Vodorovná čára"
          znak="―"
          akce={() => prikaz("insertHorizontalRule")}
        />
        <T
          popis="Odstranit formátování"
          znak="✕ª"
          akce={() => prikaz("removeFormat")}
        />
      </div>

      <div
        ref={plocha}
        className="te-plocha"
        style={{ minHeight: minVyska }}
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        aria-label="Text zprávy"
        onInput={ohlas}
        onBlur={ohlas}
        onPaste={vlozit}
        onKeyDown={klavesa}
        onMouseUp={obnovStav}
        onKeyUp={obnovStav}
      />
      <div className="te-napoveda">
        Formátování funguje i klávesovými zkratkami (Ctrl+B, Ctrl+I, Ctrl+U).
        Vložit bez formátování: Ctrl+Shift+V.
      </div>
    </div>
  );
}
