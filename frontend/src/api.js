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

// ---- Katalog produktů (dřív katalog technologií, CRM-08) ----
export function technologieSeznam(jenAktivni = false) {
  return zavolej(`/nabidkovac/technologie${jenAktivni ? "?jen_aktivni=true" : ""}`);
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

export function katalogKategorie() {
  return zavolej("/nabidkovac/technologie/kategorie");
}

export function katalogHromadne(data) {
  return zavolej("/nabidkovac/technologie/hromadne", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Přílohy položky katalogu – technický list, foto, certifikát. Nahrává se
// víc souborů najednou (multipart, proto bez JSON hlaviček).
export async function katalogNahrajPrilohy(technologieId, files) {
  const token = getToken();
  const form = new FormData();
  for (const f of files) form.append("soubory", f);
  const res = await fetch(`${API_BASE}/nabidkovac/technologie/${technologieId}/prilohy`, {
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

export function katalogPrilohaUprav(id, data) {
  return zavolej(`/nabidkovac/prilohy/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function katalogPrilohaSmaz(id) {
  return zavolej(`/nabidkovac/prilohy/${id}`, { method: "DELETE" });
}

// Stáhne soubor přílohy a vrátí blob URL. Přes fetch, ne přímý odkaz –
// endpoint chce token v hlavičce a ten <img src> ani <a href> poslat neumí.
// Volající je zodpovědný za URL.revokeObjectURL, až náhled zmizí.
export async function katalogPrilohaBlobUrl(id) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/nabidkovac/prilohy/${id}/soubor`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Přílohu se nepodařilo načíst (chyba ${res.status})`);
  return URL.createObjectURL(await res.blob());
}

// Stažení přílohy do počítače pod původním názvem.
export async function katalogStahniPrilohu(id, nazev) {
  const url = await katalogPrilohaBlobUrl(id);
  const a = document.createElement("a");
  a.href = url;
  a.download = nazev || "priloha";
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Uvolnit až po kliknutí, jinak si prohlížeč nestihne soubor vyzvednout.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// ---- Rozpis položek nabídky (CRM-08) ----
export function nabidkaPolozky(nabidkaId) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/polozky`);
}

export function nabidkaUlozPolozky(nabidkaId, polozky) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/polozky`, {
    method: "PUT",
    body: JSON.stringify({ polozky }),
  });
}

export function nabidkaPridejZKatalogu(nabidkaId, ids) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/polozky/z-katalogu`, {
    method: "POST",
    body: JSON.stringify(ids),
  });
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

// Nabídka je v cestě schválně: backend ověří, že dokument opravdu patří jí.
// Dřív se posílalo jen id dokumentu a záměna id (nabídka vs. dokument) tiše
// zapsala profil do cizí nabídky — viz komentář u endpointu.
export function profilZpracuj(nabidkaId, dokumentId) {
  return zavolej(`/nabidkovac/nabidky/${nabidkaId}/dokumenty/${dokumentId}/zpracuj-profil`, {
    method: "POST",
  });
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

// ---- Obrázky vložené do nabídkového výstupu ----
// Nahrávají se zvlášť, do rozvržení jde jen cesta – JSON v DB tak zůstane
// malý a stejný obrázek se dá na papír položit vícekrát.
export async function nahrajObrazekVystupu(nabidkaId, soubor) {
  const token = getToken();
  const formular = new FormData();
  formular.append("soubor", soubor);
  const res = await fetch(`${API_BASE}/nabidkovac/nabidky/${nabidkaId}/vystup-obrazky`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formular,
  });
  if (!res.ok) {
    const telo = await res.json().catch(() => ({}));
    throw new Error(telo.detail || `Obrázek se nepodařilo nahrát (chyba ${res.status})`);
  }
  return res.json();
}

// Načtené obrázky si držíme podle cesty: stejná fotka bývá na papíře i
// vícekrát a při každém překreslení ji stahovat znovu by blikalo.
// Cache žije po dobu záložky – obrázky jsou neměnné (v názvu mají uuid),
// takže zastarat nemůže.
const obrazkyVystupu = new Map();

/** Blob URL obrázku výstupu. Endpoint chce token, `<img src>` ho neumí poslat. */
export function nactiObrazekVystupu(cesta) {
  if (!cesta) return Promise.resolve(null);
  if (obrazkyVystupu.has(cesta)) return obrazkyVystupu.get(cesta);
  const token = getToken();
  const nacitani = fetch(`${API_BASE}/nabidkovac/vystup-obrazky/${cesta}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((res) => {
      if (!res.ok) throw new Error(`Obrázek se nepodařilo načíst (chyba ${res.status})`);
      return res.blob();
    })
    .then((blob) => URL.createObjectURL(blob))
    .catch((chyba) => {
      obrazkyVystupu.delete(cesta); // ať se po chybě zkusí znovu
      throw chyba;
    });
  obrazkyVystupu.set(cesta, nacitani);
  return nacitani;
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

// ---- číselník Kontaktní osoby ----
// Pohled na tatáž data jako panel kontaktů na kartě zákazníka, jen napříč
// firmami. Viditelnost se dědí z firmy – řeší ji backend.

export function crmKontakty({ typ, hledat } = {}) {
  const p = new URLSearchParams();
  if (typ) p.set("typ", typ);
  if (hledat) p.set("hledat", hledat);
  const q = p.toString();
  return zavolej(`/crm/kontakty${q ? `?${q}` : ""}`);
}

export function crmKontaktDetail(id) {
  return zavolej(`/crm/kontakty/detail/${id}`);
}

// Úprava z karty osoby. Vrací kartu osoby (na rozdíl od `crmKontaktUprav`,
// který vrací kartu firmy, protože ho volá panel u zákazníka).
export function crmKontaktUpravZKarty(id, data) {
  return zavolej(`/crm/kontakty/detail/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

// ---- naše firma (Admin nastavení → Firma) ----

export function crmFirma() {
  return zavolej("/crm/firma");
}

export function crmFirmaUloz(data) {
  return zavolej("/crm/firma", { method: "PUT", body: JSON.stringify(data) });
}

export function crmInterniKontakty() {
  return zavolej("/crm/firma/interni-kontakty");
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

// `rozsah` platí jen u aktivity z opakované série: jen_tuhle (výchozí) /
// tuto_a_dalsi / celou_serii.
export function crmAktivitaUprav(id, data, rozsah = null) {
  const q = rozsah ? `?rozsah=${rozsah}` : "";
  return zavolej(`/crm/aktivity/${id}${q}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function crmAktivitaSmaz(id, rozsah = null) {
  const q = rozsah ? `?rozsah=${rozsah}` : "";
  return zavolej(`/crm/aktivity/${id}${q}`, { method: "DELETE" });
}

export function crmMojeUkoly() {
  return zavolej("/crm/ukoly");
}

export function crmUzivatele() {
  return zavolej("/crm/uzivatele");
}

// Kalendář: události v rozsahu dnů. `uzivatele` je pole ID pro srovnávání
// kalendářů — z cizích událostí se vrací jen tolik, kolik dovolují pravidla
// viditelnosti (soukromé cizí nevidí ani vedení, viz backend crm/kalendar.py).
export function crmKalendar(od, do_, uzivatele = null) {
  const q = new URLSearchParams();
  if (od) q.set("od", od);
  if (do_) q.set("do", do_);
  if (uzivatele?.length) q.set("uzivatele", uzivatele.join(","));
  const dotaz = q.toString();
  return zavolej(`/crm/kalendar${dotaz ? `?${dotaz}` : ""}`);
}

export function crmUdalostPridej(data) {
  return zavolej("/crm/kalendar/udalost", { method: "POST", body: JSON.stringify(data) });
}

// Barevné štítky aktivit (jiná věc než kategorie obchodního případu —
// tohle jsou škatulky v kalendáři, kterými se filtruje).
// Firemní nastavení CRM (naše adresa pro „U nás"). Čtení smí každý, změnu
// jen právo crm_nastaveni.
// Souhrny pro Přehled obchodu (funnel, forecast, důvody proher, KPI).
// Můj den: úkoly po termínu, dnešní, zanedbané případy, nabídky bez reakce.
// Dokumenty na Disku (CRM-05). `entita` je "zakaznik" nebo "op".
export function crmSlozka(entita, zaznamId) {
  return zavolej(`/crm/slozka/${entita}/${zaznamId}`);
}

export function crmSlozkuZaloz(entita, zaznamId) {
  return zavolej(`/crm/slozka/${entita}/${zaznamId}`, { method: "POST" });
}

// Obsah složky (nebo podsložky) na Disku + cesta pro navigaci.
export function crmSlozkaObsah(entita, zaznamId, folderId = null) {
  const q = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return zavolej(`/crm/slozka/${entita}/${zaznamId}/obsah${q}`);
}

// Nahrání souboru na Disk. Jde přes appku, ale neukládá se u nás — v CRM
// zůstane jen odkaz, aby neexistovaly dvě kopie téhož dokumentu.
//
// Vlastní fetch, ne `zavolej`: ten posílá Content-Type application/json, což by
// multipart rozbilo. Stejný vzor jako `nabidkaNahrajDokument` níž.
export async function crmSlozkaNahraj(entita, zaznamId, soubor, folderId = null) {
  const token = getToken();
  const form = new FormData();
  form.append("soubor", soubor);
  if (folderId) form.append("folder_id", folderId);
  const res = await fetch(`${API_BASE}/crm/slozka/${entita}/${zaznamId}/soubor`, {
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

// Hromadné akce nad vybranými záznamy (CRM-19). Vrací počty a u aktivit i plán,
// kdo dostal jaký čas.
export function crmHromadnyVlastnik(data) {
  return zavolej("/crm/hromadne/vlastnik", { method: "POST", body: JSON.stringify(data) });
}

export function crmHromadnyStav(data) {
  return zavolej("/crm/hromadne/stav", { method: "POST", body: JSON.stringify(data) });
}

export function crmHromadnaAktivita(data) {
  return zavolej("/crm/hromadne/aktivita", { method: "POST", body: JSON.stringify(data) });
}

// Globální hledání napříč CRM (CRM-24). Od dvou znaků.
// Timeline zákazníka (CRM-18) — aktivity, případy, nabídky, objednávky,
// projekty a změny stavů na jedné ose.
export function crmTimeline(zakaznikId) {
  return zavolej(`/crm/timeline/zakaznik/${zakaznikId}`);
}

export function crmHledat(dotaz) {
  return zavolej(`/crm/hledat?q=${encodeURIComponent(dotaz)}`);
}

export function crmMujDen() {
  return zavolej("/crm/muj-den");
}

export function crmStatistiky() {
  return zavolej("/crm/statistiky");
}

export function crmNastaveni() {
  return zavolej("/crm/nastaveni");
}

export function crmNastaveniUloz(data) {
  return zavolej("/crm/nastaveni", { method: "PUT", body: JSON.stringify(data) });
}

export function crmKategorieAktivit() {
  return zavolej("/crm/kategorie-aktivit");
}

export function crmKategorieAktivityPridej(data) {
  return zavolej("/crm/kategorie-aktivit", { method: "POST", body: JSON.stringify(data) });
}

export function crmKategorieAktivityUprav(id, data) {
  return zavolej(`/crm/kategorie-aktivit/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmKategorieAktivitySmaz(id) {
  return zavolej(`/crm/kategorie-aktivit/${id}`, { method: "DELETE" });
}

export function crmStavy(entita) {
  return zavolej(`/crm/stavy/${entita}`);
}

// Co lze u stavu označit jako povinné (systémová + vlastní pole, CRM-30).
export function crmStavyPole() {
  return zavolej("/crm/stavy-pole");
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

// Kategorie obchodního případu. Nejsou to konstanty ve kódu, ale data (CRM-03):
// vedení si přidá „Servis" bez nasazení. `typ_nabidky` prázdný = ke kategorii
// výpočet neexistuje, takže se u ní nenabízí tlačítko „+ nabídka".
export function crmKategorie() {
  return zavolej("/crm/kategorie");
}

export function crmKategoriePridej(data) {
  return zavolej("/crm/kategorie", { method: "POST", body: JSON.stringify(data) });
}

export function crmKategorieUprav(id, data) {
  return zavolej(`/crm/kategorie/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmKategoriePoradi(poradi) {
  return zavolej("/crm/kategorie/poradi", {
    method: "PUT",
    body: JSON.stringify({ poradi }),
  });
}

export function crmKategorieSmaz(id) {
  return zavolej(`/crm/kategorie/${id}`, { method: "DELETE" });
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

// ---- CRM: objednávky ----
export function crmObjednavky({ hledat, pripadId } = {}) {
  const p = new URLSearchParams();
  if (hledat) p.set("hledat", hledat);
  if (pripadId) p.set("pripad_id", String(pripadId));
  const q = p.toString();
  return zavolej(`/crm/objednavky${q ? `?${q}` : ""}`);
}

export function crmObjednavkyKanban() {
  return zavolej("/crm/objednavky/kanban");
}

export function crmObjednavkaDetail(id) {
  return zavolej(`/crm/objednavky/${id}`);
}

export function crmObjednavkaZaloz(data) {
  return zavolej("/crm/objednavky", { method: "POST", body: JSON.stringify(data) });
}

export function crmObjednavkaUprav(id, data) {
  return zavolej(`/crm/objednavky/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmObjednavkaStav(id, stav, duvodZruseni = "") {
  return zavolej(`/crm/objednavky/${id}/stav`, {
    method: "POST",
    body: JSON.stringify({ stav, duvod_zruseni: duvodZruseni }),
  });
}

export function crmObjednavkaSmaz(id) {
  return zavolej(`/crm/objednavky/${id}`, { method: "DELETE" });
}

// ---- CRM: rozpis položek objednávky (CRM-08) ----
export function crmObjednavkaPolozky(id) {
  return zavolej(`/crm/objednavky/${id}/polozky`);
}

export function crmObjednavkaUlozPolozky(id, polozky) {
  return zavolej(`/crm/objednavky/${id}/polozky`, {
    method: "PUT",
    body: JSON.stringify({ polozky }),
  });
}

export function crmObjednavkaPridejZKatalogu(id, ids) {
  return zavolej(`/crm/objednavky/${id}/polozky/z-katalogu`, {
    method: "POST",
    body: JSON.stringify(ids),
  });
}

export function crmObjednavkaPrekloopZNabidky(id) {
  return zavolej(`/crm/objednavky/${id}/polozky/z-nabidky`, { method: "POST" });
}

// ---- CRM: fakturace objednávky (CRM-09) ----
export function crmSplatkoveSablony() {
  return zavolej("/crm/splatkove-sablony");
}

export function crmObjednavkaFaktury(id) {
  return zavolej(`/crm/objednavky/${id}/faktury`);
}

export function crmFakturaPridej(objednavkaId, data) {
  return zavolej(`/crm/objednavky/${objednavkaId}/faktury`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmFakturyZeSablony(objednavkaId, data) {
  return zavolej(`/crm/objednavky/${objednavkaId}/faktury/ze-sablony`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmFakturyPrepocitat(objednavkaId) {
  return zavolej(`/crm/objednavky/${objednavkaId}/faktury/prepocitat`, { method: "POST" });
}

export function crmFakturaUprav(id, data) {
  return zavolej(`/crm/faktury/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmFakturaSmaz(id) {
  return zavolej(`/crm/faktury/${id}`, { method: "DELETE" });
}

// ---- CRM: projekty, kroky a šablony ----
export function crmProjekty({ hledat, pripadId } = {}) {
  const p = new URLSearchParams();
  if (hledat) p.set("hledat", hledat);
  if (pripadId) p.set("pripad_id", String(pripadId));
  const q = p.toString();
  return zavolej(`/crm/projekty${q ? `?${q}` : ""}`);
}

export function crmProjektyKanban() {
  return zavolej("/crm/projekty/kanban");
}

export function crmProjektDetail(id) {
  return zavolej(`/crm/projekty/${id}`);
}

export function crmProjektZaloz(data) {
  return zavolej("/crm/projekty", { method: "POST", body: JSON.stringify(data) });
}

export function crmProjektUprav(id, data) {
  return zavolej(`/crm/projekty/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmProjektStav(id, stav) {
  return zavolej(`/crm/projekty/${id}/stav`, { method: "POST", body: JSON.stringify({ stav }) });
}

export function crmProjektSmaz(id) {
  return zavolej(`/crm/projekty/${id}`, { method: "DELETE" });
}

export function crmProjektPouzijSablonu(projektId, sablonaId) {
  return zavolej(`/crm/projekty/${projektId}/sablona/${sablonaId}`, { method: "POST" });
}

export function crmKrokPridej(projektId, data) {
  return zavolej(`/crm/projekty/${projektId}/kroky`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmKrokUprav(id, data) {
  return zavolej(`/crm/kroky/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function crmKrokSmaz(id) {
  return zavolej(`/crm/kroky/${id}`, { method: "DELETE" });
}

export function crmSablony() {
  return zavolej("/crm/sablony");
}

export function crmSablonaPridej(data) {
  return zavolej("/crm/sablony", { method: "POST", body: JSON.stringify(data) });
}

export function crmSablonaKrokPridej(sablonaId, data) {
  return zavolej(`/crm/sablony/${sablonaId}/kroky`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmSablonaKrokSmaz(krokId) {
  return zavolej(`/crm/sablony/kroky/${krokId}`, { method: "DELETE" });
}

export function crmSablonaSmaz(id) {
  return zavolej(`/crm/sablony/${id}`, { method: "DELETE" });
}

// ---- CRM: kombinace opatření (spojení PPA + peak shaving nabídky) ----
export function crmKombinaceZdroje(pripadId) {
  return zavolej(`/crm/pripady/${pripadId}/kombinace-zdroje`);
}

export function crmSpojNabidky(pripadId, { ppaNabidkaId, psNabidkaId, nabidkaId = null }) {
  return zavolej(`/crm/pripady/${pripadId}/kombinace`, {
    method: "POST",
    body: JSON.stringify({
      ppa_nabidka_id: ppaNabidkaId,
      ps_nabidka_id: psNabidkaId,
      nabidka_id: nabidkaId,
    }),
  });
}

// Dohledání starých nabídek (bez případu). `nasucho=true` jen vrátí náhled.
export function crmMigraceStareNabidky(nasucho = true) {
  return zavolej(`/crm/migrace/stare-nabidky?nasucho=${nasucho ? "true" : "false"}`, {
    method: "POST",
  });
}

// Import klientů a případů z Raynetu. `nasucho=true` jen vrátí náhled.
export function crmImportRaynet(nasucho = true) {
  return zavolej(`/crm/import/raynet?nasucho=${nasucho ? "true" : "false"}`, { method: "POST" });
}

// ---- CRM: uživatelské filtry (definice; filtruje se na klientu) ----
export function crmFiltry(entita) {
  return zavolej(`/crm/filtry/${entita}`);
}

export function crmFiltrUloz(entita, data) {
  return zavolej(`/crm/filtry/${entita}`, { method: "POST", body: JSON.stringify(data) });
}

export function crmFiltrUprav(id, data) {
  return zavolej(`/crm/filtry/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmFiltrSmaz(id) {
  return zavolej(`/crm/filtry/${id}`, { method: "DELETE" });
}

// ---- CRM: odběrná místa (CRM-46) ----
// Stejné pole na kartě klienta i obchodního případu: `entita` je "zakaznik"
// nebo "op", `zaznamId` id té karty. Místa vždy patří zákazníkovi — u případu
// je to druhý vchod do téhož seznamu (viz backend `crm/odberna_mista.py`).
export function crmOdbernaMista(entita, zaznamId) {
  return zavolej(`/crm/odberna-mista/${entita}/${zaznamId}`);
}

export function crmOdberneMistoPridej(entita, zaznamId, data) {
  return zavolej(`/crm/odberna-mista/${entita}/${zaznamId}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function crmOdberneMistoUprav(mistoId, data) {
  return zavolej(`/crm/odberna-mista/${mistoId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

// Bez `potvrzeno` jen vrátí náhled, co by smazání odneslo (diagramy, případy).
export function crmOdberneMistoSmaz(mistoId, potvrzeno = false) {
  return zavolej(`/crm/odberna-mista/${mistoId}?potvrzeno=${potvrzeno ? "true" : "false"}`, {
    method: "DELETE",
  });
}

// `mistoId = null` vazbu případu na místo zruší.
export function crmPripadOdberneMisto(pripadId, mistoId) {
  return zavolej(`/crm/pripady/${pripadId}/odberne-misto`, {
    method: "PUT",
    body: JSON.stringify({ odberne_misto_id: mistoId }),
  });
}

// ---- CRM: 15minutové diagramy odběru u odběrného místa (CRM-46) ----
// Diagram patří místu, ne nabídce: nahraje se jednou a použije se pro všechny
// nabídky té provozovny. Backend ho parsuje hned při nahrání, takže odpověď už
// nese souhrn (období, počet intervalů, spotřebu, maximum).
export async function crmDiagramNahraj(mistoId, file, { popis = "", pripadId = null } = {}) {
  const token = getToken();
  const fd = new FormData();
  fd.append("soubor", file);
  if (popis) fd.append("popis", popis);
  if (pripadId) fd.append("obchodni_pripad_id", String(pripadId));
  const res = await fetch(`${API_BASE}/crm/diagramy/misto/${mistoId}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!res.ok) {
    let hlaska = `Nahrání selhalo (chyba ${res.status})`;
    try {
      const d = await res.json();
      if (d.detail) hlaska = d.detail;
    } catch {
      /* odpověď nebyla JSON – zůstane obecná hláška */
    }
    throw new Error(hlaska);
  }
  return res.json();
}

export function crmDiagramSmaz(diagramId) {
  return zavolej(`/crm/diagramy/${diagramId}`, { method: "DELETE" });
}

// Stažení původního souboru (token jde v hlavičce, proto přes fetch + blob).
export async function crmDiagramStahni(diagramId, nazev) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/crm/diagramy/${diagramId}/soubor`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Soubor se nepodařilo stáhnout (chyba ${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = nazev || "diagram";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// Zapíše řadu z diagramu do profilu spotřeby nabídky (nabídka si drží kopii).
export function crmPouzijDiagramProNabidku(nabidkaId, diagramId) {
  return zavolej(`/crm/nabidky/${nabidkaId}/pouzij-diagram/${diagramId}`, { method: "POST" });
}

// Odběrná místa a jejich diagramy použitelné pro tuhle nabídku. Nabídka bez
// obchodního případu vrátí prázdný seznam (nabídkovač jde otevřít i samostatně).
export function crmOdbernaMistaNabidky(nabidkaId) {
  return zavolej(`/crm/nabidky/${nabidkaId}/odberna-mista`);
}

// ---- CRM: notifikace (CRM-10) a jejich volba (CRM-36) ----
// Zvoneček se ptá pravidelně, takže tohle volání musí zůstat levné — vrací
// posledních pár zpráv, ne celou historii.
export function crmNotifikace() {
  return zavolej("/crm/notifikace");
}

// Bez `ids` označí za přečtené všechny nepřečtené.
export function crmNotifikacePrecteno(ids) {
  return zavolej("/crm/notifikace/precteno", {
    method: "POST",
    body: JSON.stringify({ ids: ids || null }),
  });
}

export function crmNastaveniNotifikaci() {
  return zavolej("/crm/notifikace/nastaveni");
}

export function crmUlozNastaveniNotifikaci(volby) {
  return zavolej("/crm/notifikace/nastaveni", {
    method: "PUT",
    body: JSON.stringify({ volby }),
  });
}

// ---- CRM: šablony e-mailů a poznámek (CRM-32) ----
// Pozor na názvy: `crmSablony`/`crmSablonaPridej` už patří ŠABLONÁM
// PROJEKTOVÝCH KROKŮ (jiná věc, starší). Tyhle mají proto `...Textu`.
// `vse=true` vrací i vypnuté šablony — to je pro obrazovku správy, ne pro výběr.
export function crmSablonyTextu({ druh, entita, vse } = {}) {
  const q = new URLSearchParams();
  if (druh) q.set("druh", druh);
  if (entita) q.set("entita", entita);
  if (vse) q.set("vse", "true");
  const dotaz = q.toString();
  return zavolej(`/crm/sablony-textu${dotaz ? `?${dotaz}` : ""}`);
}

// Vrátí text šablony s doplněnými symboly pro konkrétní záznam.
export function crmSablonaTextuPouzij(id, { entita, zaznamId } = {}) {
  const q = new URLSearchParams();
  if (entita) q.set("entita", entita);
  if (zaznamId) q.set("zaznam_id", String(zaznamId));
  const dotaz = q.toString();
  return zavolej(`/crm/sablony-textu/${id}/pouzit${dotaz ? `?${dotaz}` : ""}`);
}

export function crmSablonaTextuPridej(data) {
  return zavolej("/crm/sablony-textu", { method: "POST", body: JSON.stringify(data) });
}

export function crmSablonaTextuUprav(id, data) {
  return zavolej(`/crm/sablony-textu/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmSablonaTextuSmaz(id) {
  return zavolej(`/crm/sablony-textu/${id}`, { method: "DELETE" });
}

// ---- CRM: odeslání e-mailu z appky (CRM-10) ----
// `entita` + `zaznamId` zapíšou odeslání jako aktivitu k záznamu (log komunikace).
export function crmPosliEmail({ komu, predmet, telo, entita, zaznamId }) {
  return zavolej("/crm/email", {
    method: "POST",
    body: JSON.stringify({
      komu,
      predmet,
      telo,
      entita: entita || "",
      zaznam_id: zaznamId || null,
    }),
  });
}

// ---- CRM: oblíbené a naposledy otevřené (CRM-37) ----
export function crmOblibene() {
  return zavolej("/crm/oblibene");
}

export function crmPrepniOblibeny(entita, zaznamId, oblibene) {
  return zavolej(`/crm/oblibene/${entita}/${zaznamId}`, {
    method: "POST",
    body: JSON.stringify({ oblibene }),
  });
}

// Zápis do historie „naposledy otevřené". Volá se z detailu; chyba se ignoruje,
// je to vedlejší efekt prohlížení.
export function crmZaznamenejOtevreni(entita, zaznamId) {
  return zavolej(`/crm/oblibene/${entita}/${zaznamId}/otevreno`, { method: "POST" });
}

// ---- CRM: audit log změn (CRM-12) ----
export function crmAudit(entita, zaznamId) {
  return zavolej(`/crm/audit/${entita}/${zaznamId}`);
}

// ---- CRM: mapa zákazníků (CRM-20) ----
export function crmMapa() {
  return zavolej("/crm/mapa");
}

// ---- CRM: automatizace (CRM-31) ----
// Katalog akcí i nabídku stavů dodává backend, ne konstanta tady: stavy jsou
// konfigurovatelné (`crm_stavy`), takže seznam ve frontendu by po přeskládání
// kanbanu nabízel neexistující fáze.
export function crmAutomatizaceAkce() {
  // Cesta je `/katalog`, ne `/akce`: backend endpoint přejmenoval, když začal
  // vracet i pole a volby, ne jen seznam akcí. Frontend za tím zaostal a
  // obrazovka automatizace padala na 404 — opraveno 31. 7. 2026.
  return zavolej("/crm/automatizace/katalog");
}

export function crmPravidla() {
  return zavolej("/crm/automatizace");
}

export function crmPravidloPridej(data) {
  return zavolej("/crm/automatizace", { method: "POST", body: JSON.stringify(data) });
}

export function crmPravidloUprav(id, data) {
  return zavolej(`/crm/automatizace/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function crmPravidloPrepni(id) {
  return zavolej(`/crm/automatizace/${id}/prepni`, { method: "POST" });
}

export function crmPravidloSmaz(id) {
  return zavolej(`/crm/automatizace/${id}`, { method: "DELETE" });
}

// ---- E-mailový klient (CRM-33) ----
// Schránka je vždycky ta přihlášeného člověka – v žádné adrese není ID účtu.
// Není to zjednodušení: kdyby se účet bral z URL, dala by se cizí pošta
// otevřít hádáním čísla (viz backend app/crm/email_routes.py).
export function emailUcet() {
  return zavolej("/crm/emaily/ucet");
}

export function emailUcetUloz(data) {
  return zavolej("/crm/emaily/ucet", { method: "PUT", body: JSON.stringify(data) });
}

export function emailUcetOtestuj(data) {
  return zavolej("/crm/emaily/ucet/test", { method: "POST", body: JSON.stringify(data) });
}

export function emailUcetOdpoj() {
  return zavolej("/crm/emaily/ucet", { method: "DELETE" });
}

export function emailSlozky() {
  return zavolej("/crm/emaily/slozky");
}

export function emailSlozkaPrepniSync(slozkaId) {
  return zavolej(`/crm/emaily/slozky/${slozkaId}/sync-prepnout`, { method: "POST" });
}

// `jenInbox` = rychlé „zkontrolovat poštu". Plný průběh přes všechny složky
// trvá desítky sekund, takže se na něj nečeká při každém kliknutí.
export function emailSync(jenInbox = true) {
  return zavolej(`/crm/emaily/sync?jen_inbox=${jenInbox ? "true" : "false"}`, { method: "POST" });
}

export function emailZpravy({
  slozkaId = null,
  hledat = "",
  jenNeprectene = false,
  jenOznacene = false,
  zakaznikId = null,
  strana = 1,
  naStranu = 50,
} = {}) {
  const p = new URLSearchParams();
  if (slozkaId) p.set("slozka_id", slozkaId);
  if (hledat) p.set("hledat", hledat);
  if (jenNeprectene) p.set("jen_neprectene", "true");
  if (jenOznacene) p.set("jen_oznacene", "true");
  if (zakaznikId) p.set("zakaznik_id", zakaznikId);
  p.set("strana", strana);
  p.set("na_stranu", naStranu);
  return zavolej(`/crm/emaily/zpravy?${p.toString()}`);
}

// `oznacitPrecteno=false` je pro náhled bez „přečtení" (např. na kartě firmy).
export function emailZprava(id, oznacitPrecteno = true) {
  return zavolej(`/crm/emaily/zpravy/${id}?oznacit_precteno=${oznacitPrecteno ? "true" : "false"}`);
}

export function emailZpravaPriznaky(id, data) {
  return zavolej(`/crm/emaily/zpravy/${id}/priznaky`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function emailZpravaPresun(id, slozkaId) {
  return zavolej(`/crm/emaily/zpravy/${id}/presun`, {
    method: "POST",
    body: JSON.stringify({ slozka_id: slozkaId }),
  });
}

export function emailZpravaDoKose(id) {
  return zavolej(`/crm/emaily/zpravy/${id}`, { method: "DELETE" });
}

export function emailAdresar(dotaz, limit = 12) {
  return zavolej(`/crm/emaily/adresar?q=${encodeURIComponent(dotaz)}&limit=${limit}`);
}

// Přílohu nejde stáhnout přes <a href>, protože požadavek potřebuje token
// v hlavičce. Stahuje se proto do blobu a klikne se za uživatele.
export async function emailPrilohaStahni(prilohaId, nazev) {
  const token = getToken();
  const res = await fetch(`${API_BASE}/crm/emaily/prilohy/${prilohaId}`, {
    headers: { Authorization: `Bearer ${token}` },
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
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const odkaz = document.createElement("a");
  odkaz.href = url;
  odkaz.download = nazev || "priloha";
  document.body.appendChild(odkaz);
  odkaz.click();
  odkaz.remove();
  // Uvolnit až po kliknutí, jinak Safari stahování zruší.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// Předvyplnění okna psaní dělá backend (citace, Re:/Fwd:, odhození vlastní
// adresy) — pravidla mají být na jednom místě, ne duplikovaná v prohlížeči.
export function emailPriprevOdpoved(zpravaId, vsem = false) {
  return zavolej(`/crm/emaily/zpravy/${zpravaId}/odpoved?vsem=${vsem ? "true" : "false"}`);
}

export function emailPripravPreposlani(zpravaId) {
  return zavolej(`/crm/emaily/zpravy/${zpravaId}/preposlani`);
}

// Odesílá se jako multipart kvůli přílohám (base64 v JSONu by požadavek
// nafoukl o třetinu). Vlastní fetch, ne `zavolej`: ten posílá JSON hlavičku.
export async function emailOdeslat({
  komu = [],
  kopie = [],
  skrytaKopie = [],
  predmet = "",
  telo = "",
  teloHtml = "",
  odpovedNaId = null,
  zakaznikId = null,
  pripadId = null,
  prilohy = [],
}) {
  const token = getToken();
  const form = new FormData();
  form.append("komu", komu.join(","));
  form.append("kopie", kopie.join(","));
  form.append("skryta_kopie", skrytaKopie.join(","));
  form.append("predmet", predmet);
  form.append("telo", telo);
  form.append("telo_html", teloHtml);
  if (odpovedNaId) form.append("odpoved_na_id", odpovedNaId);
  if (zakaznikId) form.append("zakaznik_id", zakaznikId);
  if (pripadId) form.append("pripad_id", pripadId);
  for (const f of prilohy) form.append("prilohy", f);

  const res = await fetch(`${API_BASE}/crm/emaily/odeslat`, {
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

// ---- pravidla pošty, OOO a přeposílání (CRM-33, dávka E4) ----
export function emailPravidla() {
  return zavolej("/crm/emaily/pravidla");
}

export function emailPravidloPridej(data) {
  return zavolej("/crm/emaily/pravidla", { method: "POST", body: JSON.stringify(data) });
}

export function emailPravidloUprav(id, data) {
  return zavolej(`/crm/emaily/pravidla/${id}`, { method: "PUT", body: JSON.stringify(data) });
}

export function emailPravidloPrepni(id) {
  return zavolej(`/crm/emaily/pravidla/${id}/prepni`, { method: "POST" });
}

export function emailPravidloSmaz(id) {
  return zavolej(`/crm/emaily/pravidla/${id}`, { method: "DELETE" });
}

// OOO oznámení a automatické přeposílání. Dělá to appka, ne Seznam — funguje
// to tedy jen když na serveru běží stahování pošty (greensie-email.service).
export function emailAutomatikaUloz(data) {
  return zavolej("/crm/emaily/automatika", { method: "PUT", body: JSON.stringify(data) });
}

// ---- profil pro e-mailový podpis (CRM-33) ----
// HTML podpisu skládá backend a vrací ho i v odpovědi na uložení — frontend si
// ho nikdy nesestavuje sám, jinak by náhled a odeslaná pošta mohly být jiné.
export function nactiProfil() {
  return zavolej("/auth/profil");
}

export function ulozProfil(data) {
  return zavolej("/auth/profil", { method: "PUT", body: JSON.stringify(data) });
}

// ---- hromadné akce a napojení pošty na CRM (CRM-33) ----
// Akce: precteno | neprecteno | oznacit | odznacit | presun | do_kose
export function emailHromadne(ids, akce, slozkaId = null) {
  return zavolej("/crm/emaily/hromadne", {
    method: "POST",
    body: JSON.stringify({ ids, akce, slozka_id: slozkaId }),
  });
}

// Historie komunikace na kartě zákazníka („zakaznik") nebo případu („op").
// Vrací jen hlavičky a náhled — obsah zprávy zůstává majiteli schránky.
export function emailHistorie(entita, zaznamId, limit = 50) {
  return zavolej(`/crm/emaily/historie/${entita}/${zaznamId}?limit=${limit}`);
}

export function emailVazba(zpravaId, data) {
  return zavolej(`/crm/emaily/zpravy/${zpravaId}/vazba`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Ruční připojení víc zpráv k firmě naráz (nebo jejich odpojení z karet).
// Automatika zvládne jen adresy, které v CRM jsou; zbytek připojí člověk.
export function emailHromadnaVazba(ids, { zakaznikId = null, pripadId = null, odpojit = false } = {}) {
  return zavolej("/crm/emaily/hromadne-vazba", {
    method: "POST",
    body: JSON.stringify({
      ids,
      zakaznik_id: zakaznikId,
      pripad_id: pripadId,
      odpojit,
    }),
  });
}

// ---- modul Disk (procházení firemního Google Disku) ----
// Kořen je složka nastavená v konektoru; ta je zároveň strop viditelnosti,
// výš se z appky nedostaneš (backend to u každého požadavku ověřuje).
export function diskKoren() {
  return zavolej("/disk/koren");
}

// Obsah složky + cesta ke kořeni. Prázdné `folderId` = kořen konektoru.
export function diskObsah(folderId = null) {
  const q = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
  return zavolej(`/disk/obsah${q}`);
}
