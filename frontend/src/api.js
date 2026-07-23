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

export function zmenHeslo(nove_heslo) {
  return zavolej("/auth/heslo", { method: "PUT", body: JSON.stringify({ nove_heslo }) });
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
export async function nabidkaNahrajDokument(nabidkaId, typ, file) {
  const token = getToken();
  const form = new FormData();
  form.append("typ", typ);
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

// ---- Přehled změn (Pohled 3) ----
export function nactiZmeny({ od, do: doDatum } = {}) {
  const p = new URLSearchParams();
  if (od) p.set("od", od);
  if (doDatum) p.set("do", doDatum);
  const q = p.toString();
  return zavolej(`/zmeny${q ? `?${q}` : ""}`);
}
