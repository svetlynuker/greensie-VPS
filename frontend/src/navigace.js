// ============================================================
// Jedno místo, kde je popsaná struktura appky: co je v nabídce
// vlevo, jak se která stránka jmenuje v horní liště a která
// stránka manuálu k ní patří.
//
// Právo (`pravo`) je klíč z backendového katalogu práv
// (backend/app/auth/permissions.py → PRAVA). Kdo právo nemá,
// položku vůbec neuvidí. `vzdy: true` = nepotřebuje právo.
// ============================================================

export const NABIDKA = [
  {
    skupina: null,
    polozky: [
      { klic: "rozcestnik", nazev: "Rozcestník", ikona: "domu", cesta: "/rozcestnik", vzdy: true },
    ],
  },
  {
    // CRM: odtud vede celá cesta zakázky (zákazník → případ → nabídka).
    skupina: "Obchod",
    polozky: [
      { klic: "zakaznici", nazev: "Zákazníci", ikona: "zakaznici", cesta: "/zakaznici", pravo: "zakaznici" },
      {
        klic: "obchodni_pripady",
        nazev: "Obchodní případy",
        ikona: "pripady",
        cesta: "/pripady",
        pravo: "obchodni_pripady",
      },
      // Přehled nabídek napříč případy. Jede pod právem Nabídkovače – kdo smí
      // nabídky vytvářet, smí je i vidět v seznamu.
      { klic: "nabidky", nazev: "Nabídky", ikona: "nabidkovac", cesta: "/nabidky", pravo: "nabidkovac" },
      {
        klic: "objednavky",
        nazev: "Objednávky",
        ikona: "objednavky",
        cesta: "/objednavky",
        pravo: "obchodni_pripady",
      },
      // CRM projekty (realizace). Přehled projektů z Freela je zvlášť pod
      // Přehledy – appka ho má časem nahradit, do té doby běží obojí.
      {
        klic: "crm_projekty",
        nazev: "Projekty",
        ikona: "realizace",
        cesta: "/projekty",
        pravo: "obchodni_pripady",
      },
    ],
  },
  {
    skupina: "Přehledy",
    polozky: [
      { klic: "projekty", nazev: "Přehled projektů", ikona: "projekty", cesta: "/prehled-projektu", pravo: "projekty" },
      { klic: "finance", nazev: "Přehled financí", ikona: "finance", cesta: "/finance", pravo: "finance" },
      { klic: "zmeny", nazev: "Přehled změn", ikona: "zmeny", cesta: "/zmeny", pravo: "zmeny" },
    ],
  },
  {
    skupina: "Nabídky",
    polozky: [
      { klic: "nabidkovac", nazev: "Nabídkovač", ikona: "nabidkovac", cesta: "/nabidkovac", pravo: "nabidkovac" },
      {
        klic: "katalog",
        nazev: "Katalog technologií",
        ikona: "katalog",
        cesta: "/nabidkovac/katalog",
        pravo: "nabidkovac_katalog",
      },
    ],
  },
  {
    skupina: "Systém",
    polozky: [
      { klic: "konektor", nazev: "Konektor Raynet ↔ Disk", ikona: "konektor", cesta: "/konektor", pravo: "konektor" },
      { klic: "logy", nazev: "Logy", ikona: "logy", cesta: "/logy", pravo: "logy" },
      { klic: "admin", nazev: "Admin nastavení", ikona: "admin", cesta: "/admin", pravo: "admin" },
    ],
  },
  {
    skupina: "Nápověda",
    polozky: [
      { klic: "manual", nazev: "Manuál", ikona: "manual", cesta: "/manual", vzdy: true },
    ],
  },
];

/** Smí uživatel s těmito právy vidět danou položku nabídky? */
export function smiPolozku(polozka, prava) {
  return Boolean(polozka.vzdy) || (prava || []).includes(polozka.pravo);
}

/** Nabídka profiltrovaná právy — skupiny bez jediné položky vypadnou. */
export function nabidkaPro(prava) {
  return NABIDKA.map((grp) => ({
    ...grp,
    polozky: grp.polozky.filter((p) => smiPolozku(p, prava)),
  })).filter((grp) => grp.polozky.length > 0);
}

/** Která položka nabídky je k dané adrese aktivní (nejdelší shoda cesty vyhrává). */
export function aktivniKlic(pathname) {
  let nejlepsi = null;
  for (const grp of NABIDKA) {
    for (const p of grp.polozky) {
      if (pathname === p.cesta || pathname.startsWith(`${p.cesta}/`)) {
        if (!nejlepsi || p.cesta.length > nejlepsi.cesta.length) nejlepsi = p;
      }
    }
  }
  return nejlepsi ? nejlepsi.klic : null;
}

// Nadpis a podtitulek v horní liště. Klíč = začátek adresy; hledá se
// nejdelší shoda, takže /nabidkovac/katalog přebije /nabidkovac.
const POPISY = {
  "/rozcestnik": ["Rozcestník", "Přehled dne"],
  "/zakaznici": ["Zákazníci", "Leady a klienti"],
  "/pripady": ["Obchodní případy", "Pipeline zakázek"],
  "/nabidky": ["Nabídky", "Co je odesláno a co zákazník přijal"],
  "/prehled-projektu": ["Přehled projektů", "Matice úkolů a fází"],
  "/objednavky": ["Objednávky", "Potvrzené zakázky"],
  "/projekty": ["Projekty", "Realizace zakázek"],
  "/finance": ["Přehled financí", "Faktury a párování POHODA"],
  "/zmeny": ["Přehled změn", "Co se pohnulo za období"],
  "/nabidkovac": ["Nabídkovač", "Nabídky FVE, PPA a peak shaving"],
  "/nabidkovac/katalog": ["Katalog technologií", "Ceny, parametry a výpočty"],
  "/nabidkovac/ppa": ["Nabídkovač", "PPA pro FVE"],
  "/nabidkovac/peak_shaving": ["Nabídkovač", "Peak shaving"],
  "/nabidkovac/prodej": ["Nabídkovač", "Prodej FVE"],
  "/nabidkovac/nabidka": ["Nabídka", "Detail zakázky"],
  "/konektor": ["Konektor Raynet ↔ Disk", "Synchronizace klientů a dokumentů"],
  "/logy": ["Logy", "Provoz, chyby a audit"],
  "/admin": ["Admin nastavení", "Uživatelé, skupiny a oprávnění"],
  "/manual": ["Manuál", "Návody modul po modulu"],
  "/nastaveni": ["Nastavení", "Tvoje osobní volby"],
  "/zmena-hesla": ["Změna hesla", "Zabezpečení účtu"],
};

export function popisStranky(pathname) {
  let nejlepsi = "";
  for (const cesta of Object.keys(POPISY)) {
    if ((pathname === cesta || pathname.startsWith(`${cesta}/`)) && cesta.length > nejlepsi.length) {
      nejlepsi = cesta;
    }
  }
  return POPISY[nejlepsi] || ["Greensie", ""];
}

/** Která stránka manuálu patří ke které adrese (kontextová nápověda „?"). */
export function strankaManualu(pathname) {
  if (pathname.startsWith("/zakaznici") || pathname.startsWith("/pripady")) return "crm";
  if (pathname.startsWith("/nabidky") || pathname.startsWith("/objednavky")) return "crm";
  if (pathname.startsWith("/projekty")) return "crm";
  if (pathname.startsWith("/prehled-projektu")) return "prehled-projektu";
  if (pathname.startsWith("/finance")) return "prehled-financi";
  if (pathname.startsWith("/zmeny")) return "prehled-zmen";
  // Kalkulátory mají vlastní stránku manuálu – ta obecná o Nabídkovači
  // nevysvětluje ani jedno políčko výpočtu.
  if (pathname.startsWith("/nabidkovac/peak_shaving")) return "nabidkovac-peak-shaving";
  if (pathname.startsWith("/nabidkovac/ppa")) return "nabidkovac-ppa-fve";
  if (pathname.startsWith("/nabidkovac")) return "nabidkovac";
  if (pathname.startsWith("/admin")) return "admin-nastaveni";
  if (pathname.startsWith("/logy")) return "logy";
  if (pathname.startsWith("/konektor")) return "konektor-raynet-gdrive";
  return "uvod";
}

/** Kam poslat uživatele po přihlášení / z nedostupné stránky. */
export function prvniDostupnaCesta(prava) {
  const grp = nabidkaPro(prava);
  const prvni = grp.flatMap((g) => g.polozky).find((p) => p.klic !== "manual");
  return prvni ? prvni.cesta : "/manual";
}
