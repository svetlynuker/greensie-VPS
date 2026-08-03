// Příprava podkladu pro PDF: z živé stránky se udělá samostatný HTML dokument,
// který server pošle Chromiu k vytištění.
//
// ---- Proč to sestavuje prohlížeč a ne server ------------------------------
//
// Papír nabídky vykresluje React: rozvržení v mm, grafy jako SVG, hodnoty
// dopočítané z řešení. Jediné místo, kde dokument existuje ve finální podobě,
// je tedy prohlížeč. Kdyby si ho server skládal sám, vznikl by druhý renderer,
// který se s editorem začne rozcházet – a nikdo by nepoznal, která podoba je
// ta pravá. Takhle je PDF doslova to, co obchodník viděl na obrazovce.
//
// ---- Co se posílá --------------------------------------------------------
//
// Celé CSS appky + tiskový klon papíru + obrázky převedené na data: URI.
// Server nesmí nic dotahovat ze sítě: běží bez přihlášení k appce, takže by se
// obrázky nabídky prostě nenačetly a v PDF by zůstaly bílé rámečky.

/** Posbírá pravidla ze všech stylů stránky do jednoho textu. */
function vsechnoCss() {
  const casti = [];
  for (const sheet of document.styleSheets) {
    // Sheet z jiné domény vyhodí při čtení pravidel výjimku. Naše všechny
    // z jedné domény jsou, ale spadnout kvůli tomu tisk nesmí.
    try {
      for (const pravidlo of sheet.cssRules) casti.push(pravidlo.cssText);
    } catch {
      /* nepřečtený sheet přeskočíme */
    }
  }
  return casti.join("\n");
}

/** Obrázek (blob:/http:) → data: URI, ať v PDF nechybí. */
async function naDataUri(adresa) {
  const odpoved = await fetch(adresa);
  const blob = await odpoved.blob();
  return await new Promise((hotovo, chyba) => {
    const cist = new FileReader();
    cist.onload = () => hotovo(String(cist.result));
    cist.onerror = () => chyba(new Error("Obrázek se nepodařilo přečíst."));
    cist.readAsDataURL(blob);
  });
}

/**
 * Sestaví samostatný HTML dokument s papírem k tisku.
 *
 * `korenSelektor` je obal, ve kterém je tisková kopie papíru (bez editoru,
 * úchytů a vodítek) – tedy přesně to, co se dnes tiskne přes Ctrl+P.
 */
export async function sestavTiskoveHtml(korenSelektor = ".vystup-tisk") {
  const zdroj = document.querySelector(korenSelektor);
  if (!zdroj) throw new Error("Papír k tisku se na stránce nenašel.");

  const klon = zdroj.cloneNode(true);

  // Obrázky se do editoru načítají jako blob: URL (endpoint chce token, který
  // <img src> poslat neumí). Blob URL platí jen v tomhle okně, takže se musí
  // převést na data: URI ještě tady.
  const obrazky = [...klon.querySelectorAll("img[src]")];
  await Promise.all(
    obrazky.map(async (img) => {
      const adresa = img.getAttribute("src") || "";
      if (adresa.startsWith("data:")) return;
      try {
        img.setAttribute("src", await naDataUri(adresa));
      } catch {
        // Radši nabídka bez jednoho obrázku než žádné PDF; prázdné místo je
        // v náhledu vidět a dá se opravit a vytisknout znovu.
        img.removeAttribute("src");
      }
    })
  );

  // Papír je bílý list, takže se tiskne vždy ve světlých tokenech. V tmavém
  // režimu je `--fm-muted` světlá šedá – na bílém papíře by zmizely popisky.
  // Kompenzaci barvosleposti (`data-cvd`) naopak ponecháváme: to je vědomá
  // volba uživatele o barvách grafu, ne o vzhledu obrazovky.
  const cvd = document.documentElement.getAttribute("data-cvd");
  const atributy = ['lang="cs"', 'data-theme="light"'];
  if (cvd) atributy.push(`data-cvd="${cvd}"`);

  return (
    `<!doctype html><html ${atributy.join(" ")}><head><meta charset="utf-8">` +
    `<style>${vsechnoCss()}</style></head>` +
    // Třídy na <body> a obal `.vystup-page` musí zůstat: tiskové CSS je na ně
    // navěšené (`@media print .vystup-tisk { display: block }`).
    `<body><div class="vystup-page">${klon.outerHTML}</div></body></html>`
  );
}
