// Formátovaný text psaný přímo v prvku na papíře.
//
// Postaveno na `contentEditable` + `document.execCommand`. execCommand je sice
// označený za zastaralý, ale ve všech prohlížečích funguje, umí zachovat
// kurzor a výběr a nepotřebuje k tomu 150 kB knihovny navíc. Alternativou by
// byl ProseMirror/TipTap – na to, co nabídka potřebuje (tučné, barvy,
// velikost, zarovnání, odrážky), je to zbytečně velké kladivo.
//
// Zásada: dokud uživatel píše, React do obsahu NESAHÁ. Kdyby se innerHTML
// přepisoval při každém stisku, kurzor by skákal na začátek. Model se přitom
// drží aktuální – ukládá se pročištěná podoba toho, co je v DOM.

import { useEffect, useLayoutEffect, useRef, useState } from "react";

import { vycistiHtml } from "../../vystup/sanitizace";

// Velikosti v bodech – papír je typografie, ne obrazovka.
const VELIKOSTI = [7, 8, 9, 10, 11, 12, 14, 16, 20, 24, 32];

// Barvy odpovídají tokenům appky, plus černá a šedá na běžný text.
const BARVY = [
  { hex: "#1c2321", nazev: "Černá" },
  { hex: "#6a7570", nazev: "Šedá" },
  { hex: "#2f9e44", nazev: "Zelená" },
  { hex: "#1971c2", nazev: "Modrá" },
  { hex: "#c92a2a", nazev: "Červená" },
  { hex: "#e8590c", nazev: "Oranžová" },
];

function prikaz(nazev, hodnota = null) {
  document.execCommand(nazev, false, hodnota);
}

/**
 * Velikost písma. `execCommand("fontSize")` umí jen sedm stupňů a vyrábí
 * zastaralý `<font size>`, který navíc neprojde whitelistem. Použijeme ho
 * tedy jen jako značkovač výběru a hned vzniklé značky přepíšeme na span
 * se skutečnou velikostí v bodech.
 */
function nastavVelikost(korenEl, body) {
  prikaz("fontSize", "7");
  for (const font of korenEl.querySelectorAll('font[size="7"]')) {
    const span = document.createElement("span");
    span.style.fontSize = `${body}pt`;
    while (font.firstChild) span.appendChild(font.firstChild);
    font.replaceWith(span);
  }
}

/** Je výběr uvnitř tohohle prvku? Lišta se nesmí plést do jiného textu. */
function vyberUvnitr(el) {
  const vyber = window.getSelection();
  if (!vyber || !vyber.rangeCount || !el) return false;
  return el.contains(vyber.getRangeAt(0).commonAncestorContainer);
}

/** Plovoucí lišta ukotvená nad prvkem. */
function Lista({ kotva, korenEl, onZmena }) {
  const [pozice, setPozice] = useState(null);

  // Ukotvení počítáme z pozice na obrazovce, ne CSS pozicováním uvnitř
  // stránky – ta je zvětšená zoomem a lišta by se zvětšovala s ní.
  useLayoutEffect(() => {
    function spocitej() {
      if (!kotva) return;
      const r = kotva.getBoundingClientRect();
      setPozice({ left: r.left, top: r.top - 8 });
    }
    spocitej();
    window.addEventListener("scroll", spocitej, true);
    window.addEventListener("resize", spocitej);
    return () => {
      window.removeEventListener("scroll", spocitej, true);
      window.removeEventListener("resize", spocitej);
    };
  }, [kotva]);

  if (!pozice) return null;

  // Kliknutí v liště nesmí sebrat výběr v textu – bez toho by příkaz neměl
  // na co působit.
  const drzVyber = (u) => u.preventDefault();

  function proved(akce) {
    if (!vyberUvnitr(korenEl)) korenEl?.focus();
    akce();
    onZmena();
  }

  return (
    <div
      className="vy-lista np"
      style={{ left: pozice.left, top: pozice.top }}
      onPointerDown={drzVyber}
      onMouseDown={drzVyber}
      role="toolbar"
      aria-label="Formátování textu"
    >
      <button className="vy-lista-b" title="Tučné (Ctrl+B)" onClick={() => proved(() => prikaz("bold"))}>
        <b>B</b>
      </button>
      <button className="vy-lista-b" title="Kurzíva (Ctrl+I)" onClick={() => proved(() => prikaz("italic"))}>
        <i>I</i>
      </button>
      <button
        className="vy-lista-b"
        title="Podtržené (Ctrl+U)"
        onClick={() => proved(() => prikaz("underline"))}
      >
        <u>U</u>
      </button>
      <button
        className="vy-lista-b"
        title="Přeškrtnuté"
        onClick={() => proved(() => prikaz("strikeThrough"))}
      >
        <s>S</s>
      </button>

      <span className="vy-lista-del" />

      <select
        className="vy-lista-s"
        title="Velikost písma"
        defaultValue=""
        onChange={(e) => {
          const body = e.target.value;
          e.target.value = "";
          if (body) proved(() => nastavVelikost(korenEl, body));
        }}
      >
        <option value="">Velikost</option>
        {VELIKOSTI.map((v) => (
          <option key={v} value={v}>
            {v} b
          </option>
        ))}
      </select>

      <span className="vy-lista-del" />

      <span className="vy-lista-barvy">
        {BARVY.map((b) => (
          <button
            key={b.hex}
            className="vy-lista-barva"
            style={{ background: b.hex }}
            title={`Barva písma: ${b.nazev}`}
            aria-label={`Barva písma ${b.nazev}`}
            onClick={() => proved(() => prikaz("foreColor", b.hex))}
          />
        ))}
      </span>

      <span className="vy-lista-del" />

      <button className="vy-lista-b" title="Vlevo" onClick={() => proved(() => prikaz("justifyLeft"))}>
        ⯇
      </button>
      <button className="vy-lista-b" title="Na střed" onClick={() => proved(() => prikaz("justifyCenter"))}>
        ≡
      </button>
      <button className="vy-lista-b" title="Vpravo" onClick={() => proved(() => prikaz("justifyRight"))}>
        ⯈
      </button>

      <span className="vy-lista-del" />

      <button
        className="vy-lista-b"
        title="Odrážky"
        onClick={() => proved(() => prikaz("insertUnorderedList"))}
      >
        •—
      </button>
      <button
        className="vy-lista-b"
        title="Číslování"
        onClick={() => proved(() => prikaz("insertOrderedList"))}
      >
        1.
      </button>

      <span className="vy-lista-del" />

      <button
        className="vy-lista-b"
        title="Zrušit formátování"
        onClick={() => proved(() => prikaz("removeFormat"))}
      >
        ⌫
      </button>
    </div>
  );
}

export default function TextPole({ prvek, editor, pise, tisk, trida = "vy-text" }) {
  const ref = useRef(null);
  const [kotva, setKotva] = useState(null);

  // Obsah se do DOM sype jen tehdy, když se nepíše. Během psaní by přepis
  // innerHTML shodil kurzor na začátek řádku.
  useEffect(() => {
    const el = ref.current;
    if (!el || pise) return;
    const nove = prvek.html || "";
    if (el.innerHTML !== nove) el.innerHTML = nove;
  }, [prvek.html, pise]);

  // Vstup do psaní: kurzor na konec textu, ať se dá rovnou psát.
  useEffect(() => {
    const el = ref.current;
    if (!el || !pise) return;
    setKotva(el.closest("[data-prvek-id]"));
    // styleWithCSS zařídí, že formátování vznikne jako `style`, ne jako
    // zastaralé značky (<font>, <strike>), které whitelist zahazuje.
    try {
      document.execCommand("styleWithCSS", false, true);
    } catch {
      /* starší prohlížeč – formátování bude o něco hrubší, ale funguje */
    }
    el.focus();
    const vyber = window.getSelection();
    const rozsah = document.createRange();
    rozsah.selectNodeContents(el);
    rozsah.collapse(false);
    vyber.removeAllRanges();
    vyber.addRange(rozsah);
  }, [pise]);

  function ulozZDom() {
    const el = ref.current;
    if (!el || !editor) return;
    // Do modelu jde vždy pročištěná podoba, ale DOM se nepřepisuje –
    // uživatel píše dál a kurzor zůstává, kde byl.
    const cisty = vycistiHtml(el.innerHTML);
    if (cisty !== prvek.html) {
      editor.uprav(prvek.id, { html: cisty }, { slouc: `text:${prvek.id}` });
    }
  }

  function naVlozeni(udalost) {
    // Vkládá se jen text s povoleným formátováním – jinak by se na papír
    // dostaly styly z Wordu i s jejich písmy a pozadím.
    udalost.preventDefault();
    const schranka = udalost.clipboardData;
    const html = schranka.getData("text/html");
    const cisty = html ? vycistiHtml(html) : null;
    if (cisty) {
      document.execCommand("insertHTML", false, cisty);
    } else {
      document.execCommand("insertText", false, schranka.getData("text/plain"));
    }
    ulozZDom();
  }

  function naKlavesu(udalost) {
    if (udalost.key === "Escape") {
      udalost.preventDefault();
      ulozZDom();
      editor?.otevriPsani(null);
      return;
    }
    // Enter uvnitř nadpisu kontejneru by rozbil rozvržení – tam je to jeden
    // řádek. V textovém prvku je nový odstavec v pořádku.
    if (udalost.key === "Enter" && prvek.druh === "kontejner" && !udalost.shiftKey) {
      udalost.preventDefault();
      ulozZDom();
      editor?.otevriPsani(null);
    }
  }

  function naOpusteni() {
    ulozZDom();
    editor?.uzavriKrok();
    editor?.otevriPsani(null);
  }

  // Mimo editor (tisk, náhled) je to obyčejný vykreslený text.
  if (!editor || tisk) {
    return (
      <div className={trida} dangerouslySetInnerHTML={{ __html: prvek.html || "" }} />
    );
  }

  return (
    <>
      <div
        ref={ref}
        className={`${trida} vy-editovatelny${pise ? " pise" : ""}`}
        contentEditable={pise}
        suppressContentEditableWarning
        spellCheck={pise}
        onInput={ulozZDom}
        onPaste={naVlozeni}
        onKeyDown={naKlavesu}
        onBlur={naOpusteni}
        // Během psaní si myš řídí text sám – jinak by stisk začal prvek táhnout.
        onPointerDown={pise ? (u) => u.stopPropagation() : undefined}
      />
      {pise && kotva && <Lista kotva={kotva} korenEl={ref.current} onZmena={ulozZDom} />}
    </>
  );
}
