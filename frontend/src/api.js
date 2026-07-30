// Prázdný basePath = relativní volání (/api/...). V produkci to Caddy
// nasměruje na backend, ve vývoji si nastav proxy nebo plnou adresu.
const API_BASE = "/api";
const TOKEN_KEY = "greensie_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  zapomenMe();
}

export async function login(email, heslo) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, heslo }),
  });
  if (!res.ok) {
    throw new Error("Nesprávný e-mail nebo heslo");
  }
  const data = await res.json();
  setToken(data.access_token);
}

export async function nactiMe() {
  const token = getToken();
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error("Nepodařilo se načíst uživatele");
  }
  return res.json();
}

// Sdílené /auth/me pro rámec appky (nabídka vlevo, uživatel vpravo nahoře).
// Stránky si dál načítají svoje `me` samy; tohle je jen aby se rámec nemusel
// dotazovat znovu při každém přechodu mezi stránkami. Krátká platnost, ať se
// změna práv projeví bez odhlášení.
const ME_PLATNOST_MS = 60_000;
let mePromise = null;
let meCas = 0;

export function nactiMeSdilene() {
  const nyni = Date.now();
  if (!mePromise || nyni - meCas > ME_PLATNOST_MS) {
    meCas = nyni;
    mePromise = nactiMe().catch((chyba) => {
      mePromise = null; // ať se po chybě zkusí znovu, ne že se zapamatuje selhání
      throw chyba;
    });
  }
  return mePromise;
}

export function zapomenMe() {
  mePromise = null;
  meCas = 0;
}

// ---- Souhrn pro úvodní stránku ----
export function nactiDashboard() {
  return zavolej("/dashboard");
}

export function zmenHeslo(nove_heslo) {
  return zavolej("/auth/heslo", { method: "PUT", body: JSON.stringify({ nove_heslo }) });
}

// ---- Manuál (znalostní báze v UI) ----
export function nactiManual() {
  return zavolej("/manual");
}

// ---- Matice (Přehled projektů) ----
async function zavolej(cesta, moznosti = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${cesta}`, {
    ...moznosti,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(moznosti.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `Chyba ${res.status}`;
    try {
      const chyba = await res.json();
      if (chyba.detail) detail = chyba.detail;
    } catch {
      // ponech výchozí hlášku
    }
    throw new Error(detail);
  }
  return res.json();
}

export function nactiMatici() {
  return zavolej("/matice");
}

export function ulozBunku(data) {
  return zavolej("/matice/bunka", { method: "PUT", body: JSON.stringify(data) });
}

export function pridejProjekt(data) {
  return zavolej("/matice/projekt", { method: "POST", body: JSON.stringify(data) });
}

export function pridejSloupec(data) {
  return zavolej("/matice/sloupec", { method: "POST", body: JSON.stringify(data) });
}

export function nacistZFreela(rezim) {
  return zavolej("/matice/freelo/nacist", { method: "POST", body: JSON.stringify({ rezim }) });
}

export function getSyncNastaveni() {
  return zavolej("/matice/sync-nastaveni");
}

export function ulozSyncNastaveni(data) {
  return zavolej("/matice/sync-nastaveni", { method: "PUT", body: JSON.stringify(data) });
}

export function ulozBarvy(data) {
  return zavolej("/matice/barvy", { method: "PUT", body: JSON.stringify(data) });
}

export function nastavZobrazeniProjektu(id, skryty) {
  return zavolej(`/matice/projekt/${id}/zobrazeni`, {
    method: "PUT",
    body: JSON.stringify({ skryty }),
  });
}

// Ruční odkaz na složku dokumentů projektu (prázdné url = smazat ruční odkaz).
export function ulozDiskOdkaz(id, url) {
  return zavolej(`/matice/projekt/${id}/disk`, {
    method: "PUT",
    body: JSON.stringify({ url }),
  });
}

// Hromadné spárování projektů se složkami na Disku (přes číslo OP v názvu).
// vse=true přepočítá i projekty, které už odkaz mají (kromě ručních).
export function sparujDisk(vse = false) {
  return zavolej(`/matice/disk/sparovat${vse ? "?vse=true" : ""}`, { method: "POST" });
}

// ---- Finance (Přehled financí – Pohled 2) ----
export function nactiFinance() {
  return zavolej("/finance");
}

export function ulozFakturu(id, data) {
  return zavolej(`/finance/faktura/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function pridejFakturu(projektId) {
  return zavolej(`/finance/projekt/${projektId}/faktura`, { method: "POST" });
}

export function smazFakturu(id) {
  return zavolej(`/finance/faktura/${id}`, { method: "DELETE" });
}

export function synchronizujPohodu() {
  return zavolej("/finance/pohoda/synchronizovat", { method: "POST" });
}

// ---- Nabídkovač ----
export function nabidkySeznam(typ) {
  const q = typ ? `?typ=${encodeURIComponent(typ)}` : "";
  return zavolej(`/nabidkovac/nabidky${q}`);
}

export function nabidkaZaloz(data) {
  return zavolej("/nabidkovac/nabidky", { method: "POST", body: JSON.stringify(data) });
}

export function nabidkaDetail(id) {
  return zavolej(`/nabidkovac/nabidky/${id}`);
}

export function nabidkaUprav(id, data) {
  return zavolej(`/nabidkovac/nabidky/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function nabidkaSmaz(id) {
  return zavolej(`/nabidkovac/nabidky/${id}`, { method: "DELETE" });
}

// Upload souboru = multipart, proto NEposíláme Content-Type ani JSON.
// Typ dokumentu je volitelný – bez něj si ho backend odvodí z přípony.
export async function nabidkaNahrajDokument(nabidkaId, file, typ = null) {
  const token = getToken();
  const form = new FormData();
  if (typ) form.append("typ", typ);
  form.append("soubor", file);
  const res = await fetch(`${API_BASE}/nabidkovac/nabidky/${nabidkaId}/dokumenty`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) {
    let detail = `Chyba ${res.status}`;
    try {
      const chyba = await res.json();
      if (chyba.detail) detail = chyba.detail;
    } catch {
      // ponech výchozí hlášku
    }
    throw new Error(detail);
  }
  return res.json();
}

export function nabidkaSmazDokument(id) {
  return zavolej(`/nabidkovac/dokumenty/${id}`, { method: "DELETE" });
}

// Ruční oprava typu, když automat podle přípony minul.
export function nabidkaZmenTypDokumentu(id, typ) {
  return zavolej(`/nabidkovac/dokumenty/${id}`, { method: "PATCH", body: JSON.stringify({ typ }) });
}

export function technologieSeznam() {
  return zavolej("/nabidkovac/technologie");
}

export function technologiePridej(data) {
  return zavolej("/nabidkovac/technologie", { method: "POST", body: JSON.stringify(data) });
}

export function technologieUprav(id, data) {
  return zavolej(`/nabidkovac/technologie/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function technologieSmaz(id) {
  return zavolej(`/nabidkovac/technologie/${id}`, { method: "DELETE" });
}

export function katalogSloupceSeznam() {
  return zavolej("/nabidkovac/katalog-sloupce");
}

export function katalogSloupecPridej(data) {
  return zavolej("/nabidkovac/katalog-sloupce", { method: "POST", body: JSON.stringify(data) });
}

export function katalogSloupecUprav(id, data) {
  return zavolej(`/nabidkovac/katalog-sloupce/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function katalogSloupecSmaz(id) {
  return zavolej(`/nabidkovac/katalog-sloupce/${id}`, { method: "DELETE" });
}

export function vypoctovaNastaveniSeznam() {
  return zavolej("/nabidkovac/vypoctova-nastaveni");
}

export function vypoctovaNastaveniUloz(data) {
  return zavolej("/nabidkovac/vypoctova-nastaveni", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ---- Sazby distributorů (peak shaving) ----
export function sazbySeznam() {
  return zavolej("/nabidkovac/sazby");
}

export function sazbaPridej(data) {
  return zavolej("/nabidkovac/sazby", { method: "POST", body: JSON.stringify(data) });
}

export function sazbaUprav(id, data) {
  return zavolej(`/nabidkovac/sazby/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function sazbaSmaz(id) {
  return zavolej(`/nabidkovac/sazby/${id}`, { method: "DELETE" });
}

export function peakShavingVypocet(nabidkaId, data) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/peak-shaving/vypocet`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Graf + citlivost pro variantu mimo TOP 3 (počítá se až na vyžádání).
export function peakShavingVariantaDetail(nabidkaId, index) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/peak-shaving/varianta-detail`, {
    method: "POST",
    body: JSON.stringify({ index }),
  });
}

// Rozepsaná 15min simulace pro nitkový graf průběhu (odběr / síť / baterie /
// SOC + události). Do uloženého řešení se neukládá – počítá se na vyžádání.
export function peakShavingPrubeh(nabidkaId, index, rok) {
  return zavolej(
    `/nabidkovac/nabidky/${nabidkaId}/peak-shaving/prubeh?varianta=${index}&rok=${rok}`
  );
}

export function peakShavingProfilSouhrn(nabidkaId) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/peak-shaving/profil-souhrn`);
}

export function profilZpracuj(dokumentId) {
  return zavolej(`/nabidkovac/dokumenty/${dokumentId}/zpracuj-profil`, { method: "POST" });
}

// ---- PPA pro FVE ----
export function ppaVypocet(nabidkaId, data) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/ppa/vypocet`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function ppaProfilSouhrn(nabidkaId) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/ppa/profil-souhrn`);
}

// 15min průběh výroby/spotřeby pro nitkový graf. Neukládá se do řešení (~35 tis.
// hodnot), počítá se na vyžádání ze stejné fyziky jako ekonomika.
export function ppaPrubeh(nabidkaId, varianta = "bez_baterie") {
  return zavolej(
    `/nabidkovac/nabidky/${nabidkaId}/ppa/prubeh?varianta=${encodeURIComponent(varianta)}`
  );
}

// ---- Nabídkový výstup (šablona pro zákazníka / PDF) ----
export function nabidkaVystup(nabidkaId, typReseni, vychozi = false) {
  const q = vychozi ? "?vychozi=1" : "";
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/vystup/${typReseni}${q}`);
}

export function nabidkaVystupUloz(nabidkaId, typReseni, konfigurace) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/vystup/${typReseni}`, {
    method: "PUT",
    body: JSON.stringify(konfigurace),
  });
}

// Pojmenované šablony rozvržení nabídky (napříč nabídkami) + rozvržení
// převzatá z už hotových nabídek stejného typu řešení.
export function nabidkaVystupSablony(typReseni, kromeNabidky) {
  const q = kromeNabidky ? `?krome_nabidky=${kromeNabidky}` : "";
  return zavolej(`/nabidkovac/vystup-sablony/${typReseni}${q}`);
}

export function nabidkaVystupSablonaUloz(typReseni, nazev, konfigurace) {
  return zavolej(`/nabidkovac/vystup-sablony/${typReseni}`, {
    method: "POST",
    body: JSON.stringify({ nazev, konfigurace }),
  });
}

export function nabidkaVystupSablonaSmaz(typReseni, sablonaId) {
  return zavolej(`/nabidkovac/vystup-sablony/${typReseni}/${sablonaId}`, { method: "DELETE" });
}

// ---- Uživatelská nastavení (pohledy + vzhled, uložená v DB) ----
export function nactiNastaveni() {
  return zavolej("/nastaveni");
}

export function ulozNastaveni(klic, hodnota) {
  return zavolej(`/nastaveni/${klic}`, {
    method: "PUT",
    body: JSON.stringify({ hodnota }),
  });
}

// ---- Admin nastavení (správa uživatelů, skupin a práv) ----
export function adminCiselniky() {
  return zavolej("/admin/ciselniky");
}

export function adminUzivatele() {
  return zavolej("/admin/uzivatele");
}

export function adminPridejUzivatele(data) {
  return zavolej("/admin/uzivatele", { method: "POST", body: JSON.stringify(data) });
}

export function adminUpravUzivatele(id, data) {
  return zavolej(`/admin/uzivatele/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function adminSmazUzivatele(id) {
  return zavolej(`/admin/uzivatele/${id}`, { method: "DELETE" });
}

// nove_heslo = null → server vygeneruje náhodné; jinak nastaví zadané
export function adminResetHesla(id, nove_heslo) {
  return zavolej(`/admin/uzivatele/${id}/reset-hesla`, {
    method: "POST",
    body: JSON.stringify({ nove_heslo: nove_heslo || null }),
  });
}

export function adminSkupiny() {
  return zavolej("/admin/skupiny");
}

export function adminPridejSkupinu(data) {
  return zavolej("/admin/skupiny", { method: "POST", body: JSON.stringify(data) });
}

export function adminUpravSkupinu(id, data) {
  return zavolej(`/admin/skupiny/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function adminSmazSkupinu(id) {
  return zavolej(`/admin/skupiny/${id}`, { method: "DELETE" });
}

// ---- Logy (provoz, chyby, audit) ----
export function nactiLogy({ typ, hledej, limit } = {}) {
  const p = new URLSearchParams();
  if (typ) p.set("typ", typ);
  if (hledej) p.set("hledej", hledej);
  if (limit) p.set("limit", String(limit));
  const q = p.toString();
  return zavolej(`/logy${q ? `?${q}` : ""}`);
}

export function smazLogy(starsiNezDni) {
  const q = starsiNezDni != null ? `?starsi_nez_dni=${starsiNezDni}` : "";
  return zavolej(`/logy${q}`, { method: "DELETE" });
}

// ---- Konektor (RAYNET ↔ Google Drive) ----
export function konektorNastaveni() {
  return zavolej("/konektor/nastaveni");
}

export function konektorUlozNastaveni(data) {
  return zavolej("/konektor/nastaveni", { method: "PUT", body: JSON.stringify(data) });
}

export function konektorTestSpojeni() {
  return zavolej("/konektor/test-spojeni", { method: "POST" });
}

export function konektorLogy({ uroven, hledej, limit } = {}) {
  const p = new URLSearchParams();
  if (uroven) p.set("uroven", uroven);
  if (hledej) p.set("hledej", hledej);
  if (limit) p.set("limit", String(limit));
  const q = p.toString();
  return zavolej(`/konektor/logy${q ? `?${q}` : ""}`);
}

export function konektorSmazLogy() {
  return zavolej("/konektor/logy", { method: "DELETE" });
}

export function konektorVytvorSlozku(companyId) {
  return zavolej(`/konektor/klient/${companyId}/slozka`, { method: "POST" });
}

export function konektorStromVzoru(folderId) {
  const q = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return zavolej(`/konektor/vzor/strom${q}`, { method: "POST" });
}

export function konektorDokumentyNahled(folderId) {
  const q = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return zavolej(`/konektor/dokumenty/nahled${q}`, { method: "POST" });
}

export function konektorDokumentyTestOdkaz() {
  return zavolej("/konektor/dokumenty/test-odkaz", { method: "POST" });
}

export function konektorImportRozsah() {
  return zavolej("/konektor/import/rozsah", { method: "POST" });
}

export function konektorImportSpustit() {
  return zavolej("/konektor/import", { method: "POST" });
}

export function konektorReconcile() {
  return zavolej("/konektor/reconcile", { method: "POST" });
}

export function konektorWatchStav() {
  return zavolej("/konektor/watch");
}

export function konektorWatchRegistruj() {
  return zavolej("/konektor/watch", { method: "POST" });
}

export function konektorWatchZrus() {
  return zavolej("/konektor/watch", { method: "DELETE" });
}

export function konektorDokumentNaDisk(documentId, companyId) {
  const q = companyId ? `?company_id=${companyId}` : "";
  return zavolej(`/konektor/dokument/${documentId}/na-disk${q}`, { method: "POST" });
}

export function konektorZrcadlit() {
  return zavolej("/konektor/zrcadlit", { method: "POST" });
}

export function konektorDmsSken() {
  return zavolej("/konektor/dms-sken", { method: "POST" });
}

// ---- Přehled změn (Pohled 3) ----
export function nactiZmeny({ od, do: doDatum } = {}) {
  const p = new URLSearchParams();
  if (od) p.set("od", od);
  if (doDatum) p.set("do", doDatum);
  const q = p.toString();
  return zavolej(`/zmeny${q ? `?${q}` : ""}`);
}

// ============================================================
// CRM: Zákazníci (leady/klienti) → Obchodní případy
//
// Viditelnost záznamů řeší backend (kdo nemá právo `crm_vse`, dostane jen
// svoje). Frontend nic nefiltruje – jinak by se dvě pravidla rozešla.
// ============================================================

export function crmZakaznici({ typ, hledat } = {}) {
  const p = new URLSearchParams();
  if (typ) p.set("typ", typ);
  if (hledat) p.set("hledat", hledat);
  const q = p.toString();
  return zavolej(`/crm/zakaznici${q ? `?${q}` : ""}`);
}

export function crmZakaznikDetail(id) {
  return zavolej(`/crm/zakaznici/${id}`);
}

export function crmZakaznikZaloz(data) {
  return zavolej("/crm/zakaznici", { method: "POST", body: JSON.stringify(data) });
}

export function crmZakaznikUprav(id, data) {
  return zavolej(`/crm/zakaznici/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmZakaznikSmaz(id) {
  return zavolej(`/crm/zakaznici/${id}`, { method: "DELETE" });
}

export function crmZakaznikKonvertuj(id) {
  return zavolej(`/crm/zakaznici/${id}/konvertuj`, { method: "POST" });
}

// Doplnění firmy z ARESu podle IČO. Selhání není chyba appky – uživatel
// vyplní ručně, proto to volající chytá jako varování.
export function crmAres(ico) {
  return zavolej(`/crm/ares/${encodeURIComponent(ico)}`);
}

export function crmKontaktPridej(zakaznikId, data) {
  return zavolej(`/crm/zakaznici/${zakaznikId}/kontakty`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmKontaktUprav(id, data) {
  return zavolej(`/crm/kontakty/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmKontaktSmaz(id) {
  return zavolej(`/crm/kontakty/${id}`, { method: "DELETE" });
}

export function crmPripady({ stav, zakaznikId, hledat } = {}) {
  const p = new URLSearchParams();
  if (stav) p.set("stav", stav);
  if (zakaznikId) p.set("zakaznik_id", String(zakaznikId));
  if (hledat) p.set("hledat", hledat);
  const q = p.toString();
  return zavolej(`/crm/pripady${q ? `?${q}` : ""}`);
}

export function crmPripadyKanban() {
  return zavolej("/crm/pripady/kanban");
}

export function crmPripadDetail(id) {
  return zavolej(`/crm/pripady/${id}`);
}

export function crmPripadZaloz(data) {
  return zavolej("/crm/pripady", { method: "POST", body: JSON.stringify(data) });
}

export function crmPripadUprav(id, data) {
  return zavolej(`/crm/pripady/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmPripadStav(id, stav, duvodProhry = "") {
  return zavolej(`/crm/pripady/${id}/stav`, {
    method: "POST",
    body: JSON.stringify({ stav, duvod_prohry: duvodProhry }),
  });
}

export function crmPripadHistorie(id) {
  return zavolej(`/crm/pripady/${id}/historie`);
}

export function crmPripadSmaz(id) {
  return zavolej(`/crm/pripady/${id}`, { method: "DELETE" });
}

export function crmAktivity(entita, zaznamId) {
  return zavolej(`/crm/aktivity/${entita}/${zaznamId}`);
}

export function crmAktivitaPridej(entita, zaznamId, data) {
  return zavolej(`/crm/aktivity/${entita}/${zaznamId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmAktivitaUprav(id, data) {
  return zavolej(`/crm/aktivity/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function crmAktivitaSmaz(id) {
  return zavolej(`/crm/aktivity/${id}`, { method: "DELETE" });
}

export function crmMojeUkoly() {
  return zavolej("/crm/ukoly");
}

export function crmUzivatele() {
  return zavolej("/crm/uzivatele");
}

export function crmStavy(entita) {
  return zavolej(`/crm/stavy/${entita}`);
}

export function crmStavPridej(entita, data) {
  return zavolej(`/crm/stavy/${entita}`, { method: "POST", body: JSON.stringify(data) });
}

export function crmStavUprav(id, data) {
  return zavolej(`/crm/stavy/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmStavyPoradi(entita, poradi) {
  return zavolej(`/crm/stavy/${entita}/poradi`, {
    method: "PUT",
    body: JSON.stringify({ poradi }),
  });
}

export function crmStavSmaz(id) {
  return zavolej(`/crm/stavy/${id}`, { method: "DELETE" });
}

export function crmRady() {
  return zavolej("/crm/rady");
}

export function crmRaduUprav(entita, data) {
  return zavolej(`/crm/rady/${entita}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmNavrhStartu(entita) {
  return zavolej(`/crm/rady/${entita}/navrh-startu`);
}

// Vytvoření nabídky z obchodního případu. Zákazníka, adresu a GPS doplní
// backend z karty klienta – v UI se neopisují.
export function crmVytvorNabidku(pripadId, typ) {
  return zavolej(`/crm/pripady/${pripadId}/nabidka`, {
    method: "POST",
    body: JSON.stringify({ typ }),
  });
}

// ---- CRM: vlastní (admin definovaná) pole na obrazovkách ----
// Čtení smí každý, kdo vidí CRM (z definic se kreslí formulář i sloupce);
// měnit je smí jen právo `crm_nastaveni`.
export function crmVlastniPole(entita) {
  return zavolej(`/crm/vlastni-pole/${entita}`);
}

export function crmVlastniPolePridej(entita, data) {
  return zavolej(`/crm/vlastni-pole/${entita}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmVlastniPoleUprav(id, data) {
  return zavolej(`/crm/vlastni-pole/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmVlastniPolePoradi(entita, poradi) {
  return zavolej(`/crm/vlastni-pole/${entita}/poradi`, {
    method: "PUT",
    body: JSON.stringify({ poradi }),
  });
}

export function crmVlastniPoleSmaz(id) {
  return zavolej(`/crm/vlastni-pole/${id}`, { method: "DELETE" });
}

// ---- CRM: sekce Nabídky (obchodní pipeline) ----
// Data o nabídkách zůstávají v nabídkovači; tyhle endpointy jim přidávají
// obchodní stav a přehled napříč případy.
export function crmNabidky({ stav, typ, hledat } = {}) {
  const p = new URLSearchParams();
  if (stav) p.set("stav", stav);
  if (typ) p.set("typ", typ);
  if (hledat) p.set("hledat", hledat);
  const q = p.toString();
  return zavolej(`/crm/nabidky${q ? `?${q}` : ""}`);
}

export function crmNabidkyKanban() {
  return zavolej("/crm/nabidky/kanban");
}

export function crmNabidkaStav(id, stav) {
  return zavolej(`/crm/nabidky/${id}/stav`, {
    method: "POST",
    body: JSON.stringify({ stav }),
  });
}
