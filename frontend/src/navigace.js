// ============================================================
// Jedno místo, kde je popsaná struktura appky: co je v nabídce
// vlevo, jak se která stránka jmenuje v horní liště a která
// stránka manuálu k ní patří.
//
// `barva` skupiny obarvuje ikony v levém panelu (viz layout.css) —
// v nabídce se pak hledá i podle odstínu, nejen podle názvu.
//
// Právo (`pravo`) je klíč z backendového katalogu práv
// (backend/app/auth/permissions.py → PRAVA). Kdo právo nemá,
// položku vůbec neuvidí. `vzdy: true` = nepotřebuje právo.
// ============================================================

export const NABIDKA = [
  {
    skupina: null,
    barva: null,
    polozky: [
      { klic: "rozcestnik", nazev: "Rozcestník", ikona: "domu", cesta: "/rozcestnik", vzdy: true },
    ],
  },
  {
    // Kalendář je nahoře a sám: je to jediná obrazovka, kterou člověk otevírá
    // proto, aby zjistil „co mám dnes", ne aby hledal záznam.
    skupina: "Agenda",
    barva: "modra",
    polozky: [
      // Jede pod právem Zákazníků: aktivity visí na záznamech CRM, takže kdo
      // vidí zákazníky, má co plánovat.
      { klic: "muj_den", nazev: "Můj den", ikona: "ukol", cesta: "/muj-den", pravo: "zakaznici" },
      { klic: "mapa", nazev: "Mapa", ikona: "mapa", cesta: "/mapa", pravo: "zakaznici" },
      { klic: "kalendar", nazev: "Kalendář", ikona: "kalendar", cesta: "/kalendar", pravo: "zakaznici" },
      // E-mailový klient (CRM-33). Patří k Agendě, ne k Obchodu: člověk ho
      // otevírá kvůli „co mi přišlo", ne kvůli hledání záznamu.
      { klic: "emaily", nazev: "E-mail", ikona: "obalka", cesta: "/emaily", pravo: "emaily" },
      // Firemní Google Disk k procházení přímo v appce. Patří k Agendě ze
      // stejného důvodu jako E-mail: člověk ho otevírá kvůli „kde je ten
      // soubor", ne kvůli hledání záznamu v CRM.
      { klic: "disk", nazev: "Disk", ikona: "slozka", cesta: "/disk", pravo: "disk" },
    ],
  },
  {
    // CRM: odtud vede celá cesta zakázky (zákazník → případ → nabídka → objednávka).
    skupina: "Obchod",
    barva: "zelena",
    polozky: [
      { klic: "zakaznici", nazev: "Zákazníci", ikona: "zakaznici", cesta: "/zakaznici", pravo: "zakaznici" },
      // Číselník lidí u zákazníků. Hned pod Zákazníky schválně: je to druhý
      // pohled na tatáž data (osoba se zakládá na kartě firmy), ne vlastní
      // agenda. Jede pod stejným právem — kdo vidí firmy, vidí i jejich lidi.
      {
        klic: "kontakty",
        nazev: "Kontaktní osoby",
        ikona: "zakaznici",
        cesta: "/kontakty",
        pravo: "zakaznici",
      },
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
    ],
  },
  {
    // Realizace zakázky. Oddělené od Obchodu schválně: podepsanou zakázku
    // přebírá technika a je to jiná parta lidí i jiná denní práce.
    skupina: "Technické",
    barva: "fialova",
    polozky: [
      // POZOR na dvojí význam slova „projekt": tohle je CRM projekt (realizace).
      // Přehled projektů z Freela je v Přehledech, dokud ho appka nenahradí.
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
    barva: "jantar",
    polozky: [
      // Čísla obchodu. Jede pod právem Případů — funnel i forecast jsou o nich.
      {
        klic: "prehled_obchodu",
        nazev: "Přehled obchodu",
        ikona: "finance",
        cesta: "/prehled-obchodu",
        pravo: "obchodni_pripady",
      },
      { klic: "projekty", nazev: "Přehled projektů", ikona: "projekty", cesta: "/prehled-projektu", pravo: "projekty" },
      { klic: "finance", nazev: "Přehled financí", ikona: "finance", cesta: "/finance", pravo: "finance" },
      { klic: "zmeny", nazev: "Přehled změn", ikona: "zmeny", cesta: "/zmeny", pravo: "zmeny" },
    ],
  },
  {
    skupina: "Nabídky",
    barva: "tyrkys",
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
    barva: "seda",
    polozky: [
      { klic: "konektor", nazev: "Konektor Raynet ↔ Disk", ikona: "konektor", cesta: "/konektor", pravo: "konektor" },
      { klic: "logy", nazev: "Logy", ikona: "logy", cesta: "/logy", pravo: "logy" },
      { klic: "admin", nazev: "Admin nastavení", ikona: "admin", cesta: "/admin", pravo: "admin" },
    ],
  },
  {
    skupina: "Nápověda",
    barva: "ruzova",
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
  "/kontakty": ["Kontaktní osoby", "Lidé u leadů i klientů"],
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
  "/nabidkovac/ppa_bess": ["Nabídkovač", "PPA + BESS"],
  "/nabidkovac/prodej": ["Nabídkovač", "Prodej FVE"],
  "/nabidkovac/nabidka": ["Nabídka", "Detail zakázky"],
  "/konektor": ["Konektor Raynet ↔ Disk", "Synchronizace klientů a dokumentů"],
  "/logy": ["Logy", "Provoz, chyby a audit"],
  "/admin": ["Admin nastavení", "Uživatelé, skupiny a oprávnění"],
  "/manual": ["Manuál", "Návody modul po modulu"],
  "/muj-den": ["Můj den", "Co tě dnes tlačí"],
  "/mapa": ["Mapa", "Zákazníci a projekty na mapě"],
  "/kalendar": ["Kalendář", "Schůzky, telefonáty a úkoly v týdnu"],
  "/emaily": ["E-mail", "Tvoje schránka propojená s CRM"],
  "/disk": ["Disk", "Firemní Google Disk k procházení"],
  "/prehled-obchodu": ["Přehled obchodu", "Pipeline, forecast a důvody proher"],
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
  if (pathname.startsWith("/kontakty")) return "crm";
  if (pathname.startsWith("/nabidky") || pathname.startsWith("/objednavky")) return "crm";
  if (pathname.startsWith("/projekty")) return "crm";
  if (pathname.startsWith("/kalendar")) return "crm";
  if (pathname.startsWith("/emaily")) return "emaily";
  if (pathname.startsWith("/disk")) return "disk";
  if (pathname.startsWith("/muj-den")) return "crm";
  if (pathname.startsWith("/mapa")) return "crm";
  if (pathname.startsWith("/prehled-obchodu")) return "crm";
  if (pathname.startsWith("/prehled-projektu")) return "prehled-projektu";
  if (pathname.startsWith("/finance")) return "prehled-financi";
  if (pathname.startsWith("/zmeny")) return "prehled-zmen";
  // Kalkulátory mají vlastní stránku manuálu – ta obecná o Nabídkovači
  // nevysvětluje ani jedno políčko výpočtu.
  if (pathname.startsWith("/nabidkovac/peak_shaving")) return "nabidkovac-peak-shaving";
  // PPA + BESS musí být PŘED obecným `/nabidkovac/ppa`, jinak by ho pochytilo
  // ono a podstrčilo manuál k PPA FVE. Vlastní stránka manuálu ještě není,
  // takže zatím vede na PPA FVE – ale vědomě, ne omylem.
  if (pathname.startsWith("/nabidkovac/ppa_bess")) return "nabidkovac-ppa-fve";
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
